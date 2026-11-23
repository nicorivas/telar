"""El bus contra un nats-server de verdad: corre solo si `TELAR_NATS_SERVER` dice dónde está el binario.

    TELAR_NATS_SERVER=/ruta/nats-server python3 -m pytest pruebas/test_bus.py
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as m
from telar import config as mod_config

BINARIO = os.environ.get("TELAR_NATS_SERVER", "")


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(BINARIO and Path(BINARIO).exists(), "sin TELAR_NATS_SERVER: el bus se prueba contra uno de verdad")
class ContraUnServidor(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        puerto = _puerto_libre()
        token = Path(self.tmp.name) / "token"
        token.write_text("secreto-de-ana-0123456789abcdef")
        # una cuenta por persona, como el bus de verdad (telar.cuentas)
        from telar import cuentas

        conf = Path(self.tmp.name) / "servidor.conf"
        conf.write_text(cuentas.configuracion({"ana": cuentas.hashear("secreto-de-ana-0123456789abcdef")}))
        self.proc = subprocess.Popen([BINARIO, "-a", "127.0.0.1", "-p", str(puerto), "--js", "--store_dir",
                                      str(Path(self.tmp.name) / "datos"), "-c", str(conf)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.proc.kill)
        time.sleep(0.5)
        self.config = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                        bus=mod_config.Bus(url=f"nats://127.0.0.1:{puerto}", token=str(token),
                                                           persona="ana", maquina="servidor"))

    def test_lo_publicado_espera_y_llega_en_orden_sin_duplicar(self):
        a = m.enviar(self.config, "Faro", "uno: canción", de="Secretaría")
        m.enviar(self.config, "Faro", "dos", de="Secretaría")
        self.assertFalse(a["duplicado"])

        async def recoger():
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            sub = await js.pull_subscribe(m.tema_casilla(self.config, "Faro"), durable="c-ana-faro", stream=m.STREAM)
            msgs = await sub.fetch(10, timeout=2)
            textos = [json.loads(x.data)["texto"] for x in msgs]
            for x in msgs:
                await x.ack()
            await nc.close()
            return textos

        self.assertEqual(asyncio.run(recoger()), ["uno: canción", "dos"])

    def test_una_respuesta_mas_grande_que_lo_que_lleva_el_bus_llega_comprimida(self):
        import threading

        grande = {"ok": True, "salida": "la vitrina de la feria " * 70_000}  # 1,6 MB: más que el max_payload de 1 MB

        async def escuchar():
            nc = await m.conectar(self.config)

            async def atender(msg):
                await msg.respond(m.empacar(grande, m.maximo_de(msg)))

            await nc.subscribe(m.tema_rpc(self.config, "servidor", "tipo"), cb=atender)
            return nc

        bucle = asyncio.new_event_loop()
        hilo = threading.Thread(target=bucle.run_forever, daemon=True)
        hilo.start()
        nc = asyncio.run_coroutine_threadsafe(escuchar(), bucle).result(5)
        try:
            r = m.pedir(self.config, "servidor", "tipo", {}, espera=10)
        finally:
            asyncio.run_coroutine_threadsafe(nc.close(), bucle).result(5)
            bucle.call_soon_threadsafe(bucle.stop)
            hilo.join(2)
            bucle.close()
        self.assertEqual(r, grande)

    def test_el_estado_se_lee_por_hilo(self):
        async def publicar():
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            await m.asegurar(js)
            kv = await js.key_value(m.ESTADO)
            await kv.put(m.clave_estado(self.config, "Secretaría"), json.dumps({"nombre": "Secretaría", "atencion": "espera"}).encode())
            await nc.close()

        asyncio.run(publicar())
        self.assertEqual(m.estados(self.config)["Secretaría"]["atencion"], "espera")

    def test_una_cadena_larga_se_retiene_y_la_persona_la_suelta(self):
        from unittest import mock

        from telar import casilla
        from telar.ordenes import mensaje

        ctx = SimpleNamespace(config=self.config)
        casilla.anotar_cadena(self.config, "Faro", casilla.TOPE_SALTOS)  # Faro ya está al final de una cadena
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Faro"}):
            r = mensaje.enviar(ctx, "Secretaría", "¿seguimos?")
        self.assertEqual(r["estado"], "retenido")
        self.assertEqual(r["saltos"], casilla.TOPE_SALTOS + 1)
        retenidos = mensaje.retenidos(m.registro(self.config))
        self.assertEqual([x["id"] for x in retenidos], [r["id"]])
        mensaje.soltar(ctx, r["id"])
        self.assertEqual(mensaje.retenidos(m.registro(self.config)), [])

        async def recoger():
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            sub = await js.pull_subscribe(m.tema_casilla(self.config, "Secretaría"), durable="c-ana-secretaria", stream=m.STREAM)
            msgs = await sub.fetch(5, timeout=2)
            await nc.close()
            return [json.loads(x.data) for x in msgs]

        llegados = asyncio.run(recoger())
        self.assertEqual([(x["texto"], x["saltos"], x["persona"]) for x in llegados], [("¿seguimos?", 0, "ana")])

    def test_un_hilo_suma_un_salto_a_su_cadena(self):
        from unittest import mock

        from telar import casilla
        from telar.ordenes import mensaje

        casilla.anotar_cadena(self.config, "Faro", 2)
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Faro"}):
            r = mensaje.enviar(SimpleNamespace(config=self.config), "Secretaría", "hola")
        self.assertEqual((r["saltos"], r.get("estado")), (3, None))
        self.assertEqual(m.registro(self.config)[-1]["estado"], "enviado")

    def test_un_id_de_hilo_se_vuelve_su_nombre(self):
        """`telar mensaje @144` iba a la casilla «144», que nadie lee, y salía como entregado."""
        from unittest import mock

        from telar.ordenes import mensaje

        ctx = SimpleNamespace(config=self.config)
        tel = SimpleNamespace(hilos=[SimpleNamespace(id="@144", nombre="Bebidas RRHH")])
        with mock.patch.object(mensaje._comun, "tejer", return_value=tel):
            self.assertEqual(mensaje._por_nombre(ctx, "@144"), "Bebidas RRHH")
            self.assertEqual(mensaje._por_nombre(ctx, "144"), "Bebidas RRHH")
            self.assertEqual(mensaje._por_nombre(ctx, "Secretaría"), "Secretaría")  # un nombre no se toca
            with self.assertRaises(m.ErrorDeBus):
                mensaje._por_nombre(ctx, "@999")

    def test_al_apartado_se_le_publica_en_su_tema_y_su_estado_se_lee_de_su_clave(self):
        """Un hilo cuyo nombre choca con otro (telar.casilla.apartar) publica su estado con su ficha apartada: quien le
        escribe por su nombre exacto la encuentra ahí, y lo que no está en el estado (la clave que no existe, como la
        dice nats de verdad) va a la de siempre."""
        from telar import casilla

        apartada = casilla.apartada("Faro")

        async def publicar():
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            await m.asegurar(js)
            kv = await js.key_value(m.ESTADO)
            await kv.put(f"ana.{apartada}", json.dumps({"nombre": "Faro", "maquina": "laptop"}).encode())
            await kv.put("ana.faro", json.dumps({"nombre": "faro", "maquina": "servidor"}).encode())
            await nc.close()

        asyncio.run(publicar())
        m.enviar(self.config, "Faro", "para Faro", de="Telar")
        m.enviar(self.config, "faro", "para faro", de="Telar")
        m.enviar(self.config, "Molino", "para Molino", de="Telar")
        self.assertEqual(m.estado_de(self.config, "Faro")["maquina"], "laptop")
        self.assertEqual(m.estado_de(self.config, "faro")["maquina"], "servidor")
        self.assertEqual(m.estado_de(self.config, "Molino"), {})

        async def recoger(ficha):
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            sub = await js.pull_subscribe(f"casilla.ana.{ficha}", durable=f"c-ana-{ficha}", stream=m.STREAM)
            try:
                msgs = await sub.fetch(10, timeout=2)
            except Exception:  # noqa: BLE001 - nada que recoger: nats-py termina por tiempo
                msgs = []
            for x in msgs:
                await x.ack()
            await nc.close()
            return [json.loads(x.data)["texto"] for x in msgs]

        self.assertEqual(asyncio.run(recoger(apartada)), ["para Faro"])
        self.assertEqual(asyncio.run(recoger("faro")), ["para faro"])
        self.assertEqual(asyncio.run(recoger("molino")), ["para Molino"])

    def test_sin_servidor_el_error_se_entiende(self):
        cfg = mod_config.Config(bus=mod_config.Bus(url="nats://127.0.0.1:1"))
        with self.assertRaises(m.ErrorDeBus):
            m.enviar(cfg, "Faro", "x", de="y")


class LaConexionDelNodo(unittest.TestCase):
    """En `telar serve --nodo`, los pedidos de la API van por la conexión abierta del nodo."""

    def test_un_pedido_desde_otro_hilo_usa_la_conexion_viva(self):
        import asyncio
        import threading

        from telar import bus as m

        class Falsa:
            is_connected = True

            async def request(self, tema, cuerpo, timeout):
                return type("R", (), {"data": json.dumps({"ok": True, "tema": tema}).encode()})()

        bucle = asyncio.new_event_loop()
        hilo = threading.Thread(target=bucle.run_forever, daemon=True)
        hilo.start()
        try:
            m.registrar_conexion(Falsa(), bucle)
            config = type("C", (), {"bus": type("B", (), {"url": "nats://x", "persona": "ana", "maquina": "laptop", "token": ""})()})()
            with mock.patch.object(m, "conectar", side_effect=AssertionError("no debía abrir otra")):
                r = m.pedir(config, "servidor", "ping", {})
            self.assertEqual(r, {"ok": True, "tema": "rpc.ana.servidor.ping"})
        finally:
            m.registrar_conexion(None, None)
            bucle.call_soon_threadsafe(bucle.stop)
            hilo.join(2)
            bucle.close()


class LaRespuestaGrande(unittest.TestCase):
    """Una respuesta que pasa de lo que lleva el servidor de nats (`max_payload`) va comprimida, y el que pidió la abre;
    la que ni así cabe es un error que lo dice. Antes no salía, y el que la pidió esperaba hasta su plazo."""

    GRANDE = {"ok": True, "salida": json.dumps({"tareas": [{"id": f"T{i}", "contexto": "la vitrina de la feria " * 20}
                                                           for i in range(400)]})}

    def test_la_chica_va_tal_cual_y_la_grande_comprimida(self):
        self.assertEqual(m.empacar({"ok": True}, 1_048_576), json.dumps({"ok": True}).encode())
        datos = m.empacar(self.GRANDE, 20_000)
        self.assertLess(len(json.dumps(self.GRANDE).encode()), 1_048_576)
        self.assertGreater(len(json.dumps(self.GRANDE).encode()), 20_000)
        self.assertEqual(datos[:2], b"\x1f\x8b")
        self.assertLessEqual(len(datos), 20_000 - m.HOLGURA_ENCABEZADOS)
        self.assertEqual(m.desempacar(datos), self.GRANDE)
        self.assertEqual(m.desempacar(json.dumps({"ok": True}).encode()), {"ok": True})

    def test_la_que_no_cabe_ni_comprimida_es_un_error(self):
        import base64
        import os

        r = json.loads(m.empacar({"ok": True, "salida": base64.b64encode(os.urandom(60_000)).decode()}, 20_000))
        self.assertFalse(r["ok"])
        self.assertIn("más de lo que lleva el bus", r["error"])

    def test_pedir_abre_la_comprimida(self):
        import asyncio
        import threading

        grande = self.GRANDE

        class Falsa:
            is_connected = True

            async def request(self, tema, cuerpo, timeout):
                return type("R", (), {"data": m.empacar(grande, 20_000)})()

        bucle = asyncio.new_event_loop()
        hilo = threading.Thread(target=bucle.run_forever, daemon=True)
        hilo.start()
        try:
            m.registrar_conexion(Falsa(), bucle)
            config = type("C", (), {"bus": type("B", (), {"url": "nats://x", "persona": "ana", "maquina": "laptop", "token": ""})()})()
            self.assertEqual(m.pedir(config, "servidor", "tipo", {}), grande)
        finally:
            m.registrar_conexion(None, None)
            bucle.call_soon_threadsafe(bucle.stop)
            hilo.join(2)
            bucle.close()

    def test_el_nodo_contesta_comprimido_lo_que_no_cabe(self):
        import asyncio
        from types import SimpleNamespace

        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        contestado = []

        async def respond(datos):
            contestado.append(datos)

        pedido = SimpleNamespace(data=b"{}", _client=SimpleNamespace(max_payload=20_000), respond=respond)
        asyncio.run(n._responder(pedido, lambda p: self.GRANDE))
        self.assertEqual(contestado[0][:2], b"\x1f\x8b")
        self.assertEqual(m.desempacar(contestado[0]), self.GRANDE)
        self.assertEqual(m.maximo_de(SimpleNamespace(_client=mock.MagicMock())), 1_048_576, "lo que no se sabe: 1 MB")


class NadieEscucha(unittest.TestCase):
    """Si nadie escucha un pedido (NoResponders), puede ser un nodo que se está reiniciando: se repite una vez, al rato,
    y recién después se dice «no atiende». Repetirlo no duplica nada: el primero no le llegó a nadie."""

    def _con(self, respuestas):
        import asyncio
        import threading

        class NoRespondersError(Exception):
            pass

        pedidos = []

        class Falsa:
            is_connected = True

            async def request(self, tema, cuerpo, timeout):
                pedidos.append(tema)
                r = respuestas.pop(0)
                if r is None:
                    raise NoRespondersError()
                return type("R", (), {"data": json.dumps(r).encode()})()

        bucle = asyncio.new_event_loop()
        hilo = threading.Thread(target=bucle.run_forever, daemon=True)
        hilo.start()
        m.registrar_conexion(Falsa(), bucle)
        config = type("C", (), {"bus": type("B", (), {"url": "nats://x", "persona": "ana", "maquina": "laptop", "token": ""})()})()
        try:
            with mock.patch.object(m, "REINTENTO_SIN_SERVICIO", 0.01):
                return m.pedir(config, "servidor", "proveedor", {}), pedidos
        finally:
            m.registrar_conexion(None, None)
            bucle.call_soon_threadsafe(bucle.stop)
            hilo.join(2)
            bucle.close()

    def test_un_nodo_que_vuelve_responde_al_segundo_intento(self):
        r, pedidos = self._con([None, {"ok": True, "items": 91}])
        self.assertEqual(r, {"ok": True, "items": 91})
        self.assertEqual(len(pedidos), 2)

    def test_si_sigue_sin_nadie_dice_que_no_atiende(self):
        r, pedidos = self._con([None, None])
        self.assertFalse(r["ok"])
        self.assertTrue(r["sin_servicio"])
        self.assertIn("no atiende «proveedor»", r["error"])
        self.assertEqual(len(pedidos), 2)
