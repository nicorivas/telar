"""Las fallas del bus: el registro del nodo con tope, las suscripciones que no se atrasan y los reintentos.

Lo que se veía antes: el registro de `telar serve` en el laptop crecía sin fin (cien mil líneas, casi todas
la traza de un `nats: timeout`), los pedidos a un mismo verbo esperaban en fila hasta pasarse de su plazo, y
el vigía del estado hacía tmux y archivos evento por evento. Nada de esto toca un NATS de verdad: el cliente
es un falso (los módulos `nats` y la conexión), y el nodo se arma sin conectarse.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar import salida
from telar.ordenes import nodo as mod_nodo


class FalsoTimeoutError(Exception):
    """Como `nats.errors.TimeoutError`: lo que levanta un pedido al bus que no volvió a tiempo."""


def config_con_bus():
    return SimpleNamespace(bus=SimpleNamespace(url="nats://bus", persona="ana", maquina="laptop", token=""))


# ── el registro del nodo ─────────────────────────────────────────────────────


class LasFallasEnUnaLinea(Prueba):
    def avisador(self):
        lineas, ahora = [], [1000.0]
        a = mod_bus.Avisador(lineas.append, cada=600, reloj=lambda: ahora[0])
        return a, lineas, ahora

    def test_la_misma_falla_se_escribe_una_vez_y_las_demas_se_cuentan(self):
        a, lineas, ahora = self.avisador()
        for _ in range(50):
            asyncio.run(a(FalsoTimeoutError("nats: timeout")))
        self.assertEqual(lineas, ["bus: FalsoTimeoutError: nats: timeout"])
        ahora[0] += 601
        asyncio.run(a(FalsoTimeoutError("nats: timeout")))
        self.assertEqual(len(lineas), 2)
        self.assertIn("y 49 iguales desde la anterior", lineas[1])
        # una sola línea cada una: nada de trazas
        self.assertTrue(all("\n" not in x and "Traceback" not in x for x in lineas))

    def test_fallas_distintas_se_escriben_cada_una(self):
        a, lineas, _ = self.avisador()
        asyncio.run(a(FalsoTimeoutError("nats: timeout")))
        asyncio.run(a(ConnectionRefusedError("Connect call failed")))
        self.assertEqual(len(lineas), 2)
        self.assertIn("ConnectionRefusedError", lineas[1])

    def test_una_slow_consumer_se_agrupa_por_su_tema(self):
        class SlowConsumerError(Exception):
            def __init__(self, subject, sid):
                super().__init__(f"nats: slow consumer, messages dropped subject: {subject}, sid: {sid}")
                self.subject, self.sid = subject, sid

        a, lineas, _ = self.avisador()
        for sid in range(5):
            asyncio.run(a(SlowConsumerError("cambio.ana.hoy", sid)))
        asyncio.run(a(SlowConsumerError("directorio.beto", 9)))
        self.assertEqual(len(lineas), 2)
        self.assertIn("cambio.ana.hoy", lineas[0])
        self.assertNotIn("sid", lineas[0])

    def test_no_guarda_fallas_distintas_sin_fin(self):
        a, lineas, _ = self.avisador()
        for i in range(mod_bus.Avisador.MAX_DISTINTAS + 10):
            a.anotar(ValueError(f"falla {i}"))
        self.assertLessEqual(len(a.vistas), mod_bus.Avisador.MAX_DISTINTAS)
        self.assertEqual(len(lineas), mod_bus.Avisador.MAX_DISTINTAS + 10)

    def test_el_corte_y_la_vuelta_son_una_linea(self):
        a, lineas, _ = self.avisador()
        asyncio.run(a.cortado())
        asyncio.run(a.de_vuelta())
        self.assertEqual(lineas, ["bus: se cortó la conexión; reintentando", "bus: conectado de nuevo"])


class FalsoNats:
    """El módulo `nats`: `connect` anota con qué se llamó."""

    def __init__(self):
        self.llamadas = []

    async def connect(self, url, **opciones):
        self.llamadas.append(opciones)
        return SimpleNamespace(url=url)


class LaConexionDelNodo(Prueba):
    def conectar(self, **kw):
        falso = FalsoNats()
        with mock.patch.dict(sys.modules, {"nats": falso}):
            asyncio.run(mod_bus.conectar(config_con_bus(), **kw))
        return falso.llamadas[-1]

    def test_la_del_nodo_cuenta_sus_fallas_con_el_avisador(self):
        opciones = self.conectar(para_siempre=True)
        self.assertIsInstance(opciones["error_cb"], mod_bus.Avisador)
        self.assertEqual(opciones["disconnected_cb"], opciones["error_cb"].cortado)
        self.assertEqual(opciones["reconnected_cb"], opciones["error_cb"].de_vuelta)
        self.assertEqual(opciones["max_reconnect_attempts"], -1)

    def test_la_de_una_orden_sigue_callada(self):
        opciones = self.conectar()
        self.assertIs(opciones["error_cb"], mod_bus._callar)
        self.assertNotIn("disconnected_cb", opciones)


class ElRegistroConTope(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "telar-serve.log"
        self.ruta.write_text("".join(f"línea {i}\n" for i in range(3000)), encoding="utf-8")

    def abrir(self, flags):
        fd = os.open(self.ruta, flags)
        self.addCleanup(os.close, fd)
        return fd

    def test_uno_que_pasa_del_tope_queda_con_su_ultima_mitad(self):
        fd = self.abrir(os.O_WRONLY | os.O_APPEND)
        self.assertTrue(salida.recortar_registro(fd, maximo=8000))
        os.write(fd, b"lo que sigue\n")
        lineas = self.ruta.read_text(encoding="utf-8").splitlines()
        self.assertIn("registro recortado", lineas[0])
        self.assertTrue(lineas[1].startswith("línea "))  # desde un salto de línea, no a media línea
        self.assertEqual(lineas[-2:], ["línea 2999", "lo que sigue"])
        self.assertLess(self.ruta.stat().st_size, 8000)

    def test_uno_bajo_el_tope_no_se_toca(self):
        fd = self.abrir(os.O_WRONLY | os.O_APPEND)
        antes = self.ruta.read_bytes()
        self.assertFalse(salida.recortar_registro(fd, maximo=len(antes) + 1))
        self.assertEqual(self.ruta.read_bytes(), antes)

    def test_sin_o_append_no_se_toca(self):
        # abierto con `>`: después de vaciarlo seguiría escribiendo en su posición vieja, con un hueco
        fd = self.abrir(os.O_WRONLY)
        antes = self.ruta.read_bytes()
        self.assertFalse(salida.recortar_registro(fd, maximo=100))
        self.assertEqual(self.ruta.read_bytes(), antes)

    def test_una_tuberia_no_se_toca(self):
        r, w = os.pipe()
        self.addCleanup(os.close, r)
        self.addCleanup(os.close, w)
        self.assertFalse(salida.recortar_registro(w, maximo=0))

    def test_movido_se_recorta_el_suyo_y_no_el_que_quedo_en_su_lugar(self):
        # la ruta se pide al archivo abierto, no se arma: uno nuevo con el nombre de antes no es el suyo
        fd = self.abrir(os.O_WRONLY | os.O_APPEND)
        viejo = self.ruta.with_suffix(".viejo")
        self.ruta.rename(viejo)
        self.ruta.write_text("otro\n", encoding="utf-8")
        self.assertTrue(salida.recortar_registro(fd, maximo=8000))
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), "otro\n")
        self.assertLess(viejo.stat().st_size, 8000)

    def test_si_no_se_sabe_su_ruta_no_se_toca(self):
        fd = self.abrir(os.O_WRONLY | os.O_APPEND)
        antes = self.ruta.read_bytes()
        with mock.patch.object(salida, "_ruta_de", return_value=""):
            self.assertFalse(salida.recortar_registro(fd, maximo=100))
        # ni si la ruta que da es de otro archivo
        otro = Path(self.tmp.name) / "otro.log"
        otro.write_text("otro\n", encoding="utf-8")
        with mock.patch.object(salida, "_ruta_de", return_value=str(otro)):
            self.assertFalse(salida.recortar_registro(fd, maximo=100))
        self.assertEqual(self.ruta.read_bytes(), antes)
        self.assertEqual(otro.read_text(encoding="utf-8"), "otro\n")

    def test_el_nodo_lo_anota_cuando_recorta(self):
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        anotado = []
        n.anotar = anotado.append
        with mock.patch.object(salida, "recortar_registro", return_value=True):
            self.assertTrue(n.recortar_registro())
        with mock.patch.object(salida, "recortar_registro", return_value=False):
            self.assertFalse(n.recortar_registro())
        self.assertEqual(len(anotado), 1)


# ── los reintentos ───────────────────────────────────────────────────────────


class LosReintentos(Prueba):
    def test_un_plazo_agotado_se_intenta_otra_vez(self):
        intentos = []

        async def leer():
            intentos.append(1)
            if len(intentos) == 1:
                raise FalsoTimeoutError("nats: timeout")
            return "ok"

        self.assertEqual(mod_bus._con_reintento(leer, 5), "ok")
        self.assertEqual(len(intentos), 2)

    def test_solo_una_vez(self):
        intentos = []

        async def leer():
            intentos.append(1)
            raise asyncio.TimeoutError()

        with self.assertRaises(asyncio.TimeoutError):
            mod_bus._con_reintento(leer, 5)
        self.assertEqual(len(intentos), 2)

    def test_si_no_conecto_no_se_insiste(self):
        intentos = []

        async def leer():
            intentos.append(1)
            raise mod_bus.ErrorDeBus("el bus no responde")

        with self.assertRaises(mod_bus.ErrorDeBus):
            mod_bus._con_reintento(leer, 5)
        self.assertEqual(len(intentos), 1)

    def test_otra_falla_tampoco(self):
        intentos = []

        async def leer():
            intentos.append(1)
            raise ValueError("no es JSON")

        with self.assertRaises(ValueError):
            mod_bus._con_reintento(leer, 5)
        self.assertEqual(len(intentos), 1)

    def test_donde_vive_un_hilo_se_pregunta_otra_vez(self):
        pedidos = []

        class Kv:
            async def get(self, clave):
                return SimpleNamespace(value=json.dumps({"maquina": "servidor"}).encode())

        class Js:
            async def key_value(self, nombre):
                pedidos.append(nombre)
                if len(pedidos) == 1:
                    raise FalsoTimeoutError("nats: timeout")
                return Kv()

        class Nc:
            def jetstream(self):
                return Js()

            async def close(self):
                pass

        async def conectar(_config):
            return Nc()

        with mock.patch.object(mod_bus, "conectar", conectar):
            self.assertEqual(mod_bus.maquina_de(config_con_bus(), "Faro"), "servidor")
        self.assertEqual(len(pedidos), 2)


class ElEnvioSeRepiteSinDuplicar(Prueba):
    def enviar(self, fallas: int, **kw):
        publicados = []

        class Js:
            async def publish(self, tema, datos, headers=None, timeout=None):
                publicados.append((tema, json.loads(datos), dict(headers or {})))
                if len(publicados) <= fallas:
                    raise FalsoTimeoutError("nats: timeout")
                # el bus descarta el repetido: el mismo id que ya había llegado
                ids = [h.get("Nats-Msg-Id") for t, _, h in publicados[:-1] if t == tema]
                return SimpleNamespace(seq=len(publicados), duplicate=headers.get("Nats-Msg-Id") in ids)

        class Nc:
            def jetstream(self):
                return Js()

            async def close(self):
                pass

        async def conectar(_config):
            return Nc()

        async def asegurar(_js):
            return None

        with mock.patch.object(mod_bus, "conectar", conectar), mock.patch.object(mod_bus, "asegurar", asegurar):
            r = mod_bus.enviar(config_con_bus(), "Faro", "hola", de="Ana", **kw)
        return r, publicados

    def test_la_copia_del_registro_lleva_id_con_su_estado(self):
        r, publicados = self.enviar(0)
        (t1, _, h1), (t2, copia, h2) = publicados
        self.assertEqual(t1, "casilla.ana.faro")
        self.assertEqual(h1["Nats-Msg-Id"], r["id"])
        self.assertEqual(t2, "registro.ana")
        self.assertEqual(h2["Nats-Msg-Id"], f"{r['id']}.enviado")
        self.assertEqual(copia["estado"], "enviado")
        self.assertFalse(r["duplicado"])

    def test_un_retenido_lleva_otro_id_que_el_que_lo_suelta(self):
        _, publicados = self.enviar(0, retener="cadena larga")
        ((tema, copia, h),) = publicados  # no va a la casilla
        self.assertEqual(tema, "registro.ana")
        self.assertTrue(h["Nats-Msg-Id"].endswith(".retenido"))

    def test_si_el_bus_no_confirmo_se_manda_otra_vez_con_el_mismo_id(self):
        r, publicados = self.enviar(1)
        casillas = [h["Nats-Msg-Id"] for t, _, h in publicados if t.startswith("casilla.")]
        self.assertEqual(casillas, [r["id"], r["id"]])
        self.assertEqual(len([t for t, _, _ in publicados if t.startswith("registro.")]), 1)
        # repetido en el reintento es el primero que sí había llegado: no estaba antes
        self.assertFalse(r["duplicado"])

    def test_dos_veces_sin_confirmar_es_un_error_para_la_persona(self):
        with self.assertRaises(mod_bus.ErrorDeBus):
            self.enviar(5)


# ── las suscripciones del nodo ───────────────────────────────────────────────


def nodo():
    n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
    n.config, n.yo, n.persona = config_con_bus(), "laptop", "ana"
    n.atendiendo, n.turnos = set(), None
    n.anotado = []
    n.anotar = n.anotado.append
    return n


class Pedido:
    def __init__(self, n=0, reply="_INBOX.1", subject="rpc.ana.laptop.tarea"):
        self.n, self.reply, self.subject = n, reply, subject
        self.respuestas = []

    async def respond(self, datos):
        self.respuestas.append(json.loads(datos))


class LosPedidosNoEsperanEnFila(Prueba):
    def test_uno_lento_no_atrasa_al_siguiente(self):
        n, orden = nodo(), []

        async def cb(m):
            if m.n == 0:
                await asyncio.sleep(0.2)
            orden.append(m.n)

        async def correr():
            atender = n._aparte(cb)
            await atender(Pedido(0))
            await atender(Pedido(1))
            await asyncio.gather(*list(n.atendiendo))

        asyncio.run(correr())
        self.assertEqual(orden, [1, 0])

    def test_en_fila_van_de_a_uno_y_en_orden_sin_que_nats_espere(self):
        n, orden, a_la_vez, maximo = nodo(), [], [0], [0]

        async def cb(m):
            a_la_vez[0] += 1
            maximo[0] = max(maximo[0], a_la_vez[0])
            await asyncio.sleep(0.05 if m.n == 0 else 0.001)
            orden.append(m.n)
            a_la_vez[0] -= 1

        async def correr():
            atender = n._aparte(cb, asyncio.Lock())
            antes = asyncio.get_running_loop().time()
            for i in range(3):
                await atender(Pedido(i))
            # el callback de nats-py volvió al tiro: la espera es de la tarea, no de su lectura
            self.assertLess(asyncio.get_running_loop().time() - antes, 0.04)
            await asyncio.gather(*list(n.atendiendo))

        asyncio.run(correr())
        self.assertEqual(orden, [0, 1, 2])
        self.assertEqual(maximo[0], 1)

    def test_no_mas_de_los_que_se_atienden_a_la_vez(self):
        n, a_la_vez, maximo = nodo(), [0], [0]

        async def cb(m):
            a_la_vez[0] += 1
            maximo[0] = max(maximo[0], a_la_vez[0])
            await asyncio.sleep(0.01)
            a_la_vez[0] -= 1

        async def correr():
            atender = n._aparte(cb)
            for i in range(mod_nodo.PEDIDOS_A_LA_VEZ * 3):
                await atender(Pedido(i))
            await asyncio.gather(*list(n.atendiendo))

        asyncio.run(correr())
        self.assertEqual(maximo[0], mod_nodo.PEDIDOS_A_LA_VEZ)
        self.assertEqual(n.atendiendo, set())

    def test_con_la_fila_llena_contesta_que_esta_ocupada(self):
        n, suelta = nodo(), None

        async def correr():
            nonlocal suelta
            suelta = asyncio.Event()

            async def cb(m):
                await suelta.wait()

            atender = n._aparte(cb)
            for i in range(mod_nodo.PEDIDOS_EN_ESPERA):
                await atender(Pedido(i))
            de_mas = Pedido(99)
            await atender(de_mas)
            sin_respuesta = Pedido(100, reply="")
            await atender(sin_respuesta)
            suelta.set()
            await asyncio.gather(*list(n.atendiendo))
            return de_mas, sin_respuesta

        de_mas, sin_respuesta = asyncio.run(correr())
        self.assertEqual(len(de_mas.respuestas), 1)
        self.assertFalse(de_mas.respuestas[0]["ok"])
        self.assertTrue(de_mas.respuestas[0]["ocupada"])
        self.assertIn("laptop está ocupada", de_mas.respuestas[0]["error"])
        self.assertEqual(sin_respuesta.respuestas, [])

    def test_uno_que_falla_se_anota_y_no_tumba_a_los_demas(self):
        n, hechos = nodo(), []

        async def cb(m):
            if m.n == 0:
                raise RuntimeError("se cayó")
            hechos.append(m.n)

        async def correr():
            atender = n._aparte(cb)
            await atender(Pedido(0))
            await atender(Pedido(1))
            await asyncio.gather(*list(n.atendiendo))

        asyncio.run(correr())
        self.assertEqual(hechos, [1])
        self.assertEqual(len(n.anotado), 1)
        self.assertIn("se cayó", n.anotado[0])


class FalsaConexion:
    def __init__(self):
        self.suscritas = []

    async def subscribe(self, tema, cb=None, **opciones):
        self.suscritas.append((tema, cb, opciones))


class LasSuscripcionesDelNodo(Prueba):
    def suscritas(self):
        n, nc = nodo(), FalsaConexion()
        asyncio.run(n.suscribirse(nc))
        return n, {tema: (cb, opciones) for tema, cb, opciones in nc.suscritas}

    def test_todas_tienen_tope_de_lo_que_espera(self):
        _, suscritas = self.suscritas()
        for tema, (_, opciones) in suscritas.items():
            self.assertEqual(opciones["pending_msgs_limit"], mod_nodo.PENDIENTES_MSGS, tema)
            self.assertEqual(opciones["pending_bytes_limit"], mod_nodo.PENDIENTES_BYTES, tema)

    def test_los_mismos_temas_que_antes(self):
        _, suscritas = self.suscritas()
        verbos = {t.rsplit(".", 1)[-1] for t in suscritas if t.startswith("rpc.ana.laptop.")}
        self.assertEqual(verbos, {"ping", "leer", "resultado", "resultado-comentar", "proveedor", "tarea", "tipo",
                                  "periodicos", "hilo", "equipo", "aviso", "archivo", "archivo-leer", "modulo",
                                  "notas", "nota", "serie", "serie-recordar"})
        self.assertIn("cambio.ana.*", suscritas)
        from telar import cuentas

        self.assertEqual(suscritas[cuentas.CORREO.format("ana")][1]["queue"], "correo")
        self.assertIn(cuentas.DIRECTORIO.format("*"), suscritas)

    def test_el_ping_y_los_avisos_se_atienden_en_orden_y_los_pedidos_aparte(self):
        n, suscritas = self.suscritas()
        from telar import cuentas

        # en orden: el callback es el método mismo
        self.assertEqual(suscritas["rpc.ana.laptop.ping"][0], n._ping)
        self.assertEqual(suscritas["cambio.ana.*"][0], n._cambio)
        self.assertEqual(suscritas[cuentas.DIRECTORIO.format("*")][0], n._directorio)
        # aparte: el envoltorio de `_aparte`
        for verbo in ("leer", "tarea", "tipo", "hilo", "archivo-leer"):
            self.assertEqual(suscritas[f"rpc.ana.laptop.{verbo}"][0].__qualname__, "Nodo._aparte.<locals>.atender")
        self.assertEqual(suscritas[cuentas.CORREO.format("ana")][0].__qualname__, "Nodo._aparte.<locals>.atender")

    def test_los_que_escriben_van_en_fila_y_los_que_leen_no(self):
        import inspect

        _, suscritas = self.suscritas()

        def fila(tema):
            return inspect.getclosurevars(suscritas[tema][0]).nonlocals["fila"]

        for verbo in mod_nodo.SOLO_LEEN:
            self.assertIsNone(fila(f"rpc.ana.laptop.{verbo}"), verbo)
        for verbo in ("hilo", "tarea", "tipo", "periodicos", "equipo", "nota", "serie-recordar", "resultado-comentar",
                      "archivo", "modulo", "aviso"):
            self.assertIsInstance(fila(f"rpc.ana.laptop.{verbo}"), asyncio.Lock, verbo)
        # una fila por verbo, no una para todos
        self.assertIsNot(fila("rpc.ana.laptop.hilo"), fila("rpc.ana.laptop.tarea"))


# ── el vigía del estado ──────────────────────────────────────────────────────


class Vigia:
    """`kv.watch`: entrega los eventos con una pausa entre uno y otro, y avisa cuando entregó todos."""

    def __init__(self, eventos):
        self.eventos = list(eventos)
        self.entregados = threading.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0.02)
        if not self.eventos:
            self.entregados.set()
            raise StopAsyncIteration
        return self.eventos.pop(0)


def evento(nombre, **d):
    return SimpleNamespace(key=f"ana.{nombre.lower()}", value=json.dumps({"nombre": nombre, "maquina": "servidor",
                                                                         **d}).encode())


class ElVigiaNoSeAtrasa(Prueba):
    def test_una_ventana_lenta_no_frena_al_vigia_y_una_rafaga_se_atiende_con_lo_ultimo(self):
        vistas = []

        def ventana_de(d):
            # la primera tarda hasta que el vigía entregó todo: si el vigía la esperara, no terminaría nunca
            if not vistas:
                self.assertTrue(vigia_ref[0].entregados.wait(5), "el vigía esperó a la ventana")
            vistas.append((d["nombre"], d["atencion"]))

        vigia_ref = []
        eventos = [evento("Faro", atencion="trabajando"), evento("Faro", atencion="esperando"),
                   evento("Faro", atencion="inactivo"), evento("Molino", atencion="trabajando")]
        n = nodo()
        n.vistos, n.ajenos_listos, n.ajenos_escritos = {}, False, None
        n.ventana_de = ventana_de
        vigia = Vigia(eventos)
        vigia_ref.append(vigia)

        async def watch(_):
            return vigia

        with mock.patch("telar.estado.abrir", return_value=SimpleNamespace(remotos=lambda: {})):
            asyncio.run(n._vigilar(SimpleNamespace(watch=watch)))
        # la primera, después lo último de Faro (la del medio se la saltó), y Molino
        self.assertEqual(vistas, [("Faro", "trabajando"), ("Faro", "inactivo"), ("Molino", "trabajando")])
        # y lo que el nodo sabe de cada uno es lo último, al instante
        self.assertEqual(n.vistos["ana.faro"]["atencion"], "inactivo")
        self.assertEqual(n.por_atender, {})

    def test_un_hilo_que_se_borro_antes_de_atenderlo_no_se_atiende(self):
        vistas = []

        def ventana_de(d):
            if not vistas:
                self.assertTrue(vigia_ref[0].entregados.wait(5))
            vistas.append(d["nombre"])

        vigia_ref = []
        borrado = SimpleNamespace(key="ana.molino", value=b"")
        n = nodo()
        n.vistos, n.ajenos_listos, n.ajenos_escritos = {}, False, None
        n.ventana_de = ventana_de
        vigia = Vigia([evento("Faro", atencion="trabajando"), evento("Molino", atencion="trabajando"), borrado])
        vigia_ref.append(vigia)

        async def watch(_):
            return vigia

        with mock.patch("telar.estado.abrir", return_value=SimpleNamespace(remotos=lambda: {})):
            asyncio.run(n._vigilar(SimpleNamespace(watch=watch)))
        self.assertEqual(vistas, ["Faro"])
        self.assertNotIn("ana.molino", n.vistos)

    def test_una_atencion_que_no_se_pudo_anotar_no_tumba_al_vigia(self):
        vistas = []
        n = nodo()
        n.vistos, n.ajenos_listos, n.ajenos_escritos = {}, False, None
        n.ventana_de = lambda d: vistas.append(d["nombre"])
        vigia = Vigia([evento("Faro", atencion="trabajando"), evento("Molino", atencion="trabajando")])

        async def watch(_):
            return vigia

        with mock.patch("telar.estado.abrir", side_effect=OSError("disco lleno")):
            asyncio.run(n._vigilar(SimpleNamespace(watch=watch)))
        self.assertEqual(sorted(vistas), ["Faro", "Molino"])
        self.assertTrue(any("disco lleno" in x for x in n.anotado))


if __name__ == "__main__":
    unittest.main()
