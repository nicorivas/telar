"""Dos hilos cuyos nombres solo difieren en mayúsculas, tildes o espacios no comparten casilla.

Lo que pasó: había un hilo «faro» y se abrió un hijo «Faro». La casilla de un hilo se llamaba como la forma
normalizada de su nombre (`telar.casilla.nombre_de_carpeta`, minúsculas y sin tildes: los dos dan `faro`), y el tema
y la clave de estado en el bus también. Lo que se le escribió a «Faro» lo entregó el gancho de «faro»; ese se lo
reenvió por su id, el id se volvió el nombre, el nombre la misma casilla, y le volvió a llegar a él. No era el disco:
la forma normalizada ya los juntaba, en cualquier disco.

Ahora uno se queda con la forma y el otro se aparta (`faro_3f9a1c`, un sufijo que sale de su nombre exacto): su
carpeta, su tema y su clave son suyos, quien le escribe por nombre exacto o por id lo encuentra, y lo que esperaba
en la casilla compartida pasa a la suya. `telar hilo hijo` y `telar hilo renombrar` se niegan a un nombre que choca. Nada de esto
toca un bus ni un tmux de verdad: el bus es un falso, el estado una carpeta temporal.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)
from test_ordenes import Orden

from telar import bus as mod_bus
from telar import casilla
from telar import entre_personas


class ConEstado(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = SimpleNamespace(estado=Path(self.tmp.name) / "estado",
                                      bus=SimpleNamespace(url="nats://bus", persona="ana", maquina="laptop", token=""))

    def mensaje(self, mid: str, para: str, texto: str = "", **mas) -> dict:
        return {"id": mid, "para": para, "de": "Telar", "texto": texto or f"para {para}", **mas}

    def ids(self, hilo: str) -> list[str]:
        return [m["id"] for m in casilla.pendientes(self.config, hilo)]


class LaCausa(Prueba):
    def test_la_forma_normalizada_junta_a_los_que_solo_difieren_en_mayusculas_tildes_o_espacios(self):
        # la causa, en cualquier disco: antes, esta era la carpeta, el tema y la clave de los cuatro
        nombres = ["Faro", "faro", "Fáro", "FARO "]
        self.assertEqual({casilla.nombre_de_carpeta(n) for n in nombres}, {"faro"})
        self.assertTrue(all(casilla.chocan("faro", n) for n in ("Faro", "Fáro", "FARO ")))
        self.assertFalse(casilla.chocan("Faro", "Faro"))  # un nombre no choca consigo mismo
        self.assertFalse(casilla.chocan("Faro", "Faro Norte"))

    def test_la_ficha_apartada_es_estable_y_no_es_la_de_ningun_nombre(self):
        self.assertEqual(casilla.apartada("Faro"), casilla.apartada("Faro"))
        self.assertNotEqual(casilla.apartada("Faro"), casilla.apartada("FARO"))
        self.assertRegex(casilla.apartada("Faro"), r"^faro_[0-9a-f]{6}$")
        self.assertTrue(casilla.es_apartada(casilla.apartada("Faro Norte")))
        # la forma normalizada nunca lleva guion bajo: «Faro 3f9a1c» no puede dar la ficha apartada de «Faro»
        self.assertFalse(casilla.es_apartada(casilla.nombre_de_carpeta(f"Faro {casilla.sufijo('Faro')}")))
        # una «á» de un carácter y una de dos (a + tilde) son el mismo nombre
        self.assertEqual(casilla.apartada("Fáro"), casilla.apartada("Fáro"))

    def test_otro_nombre_propone_uno_que_no_choca(self):
        self.assertEqual(casilla.otro_nombre("Faro", ["faro"]), "Faro 2")
        self.assertEqual(casilla.otro_nombre("Faro", ["faro", "faro 2", "Molino"]), "Faro 3")
        self.assertEqual(casilla.otro_nombre("Faro 2", ["faro 2"]), "Faro 3")


class LaCasillaDeCadaUno(ConEstado):
    def test_sin_choque_la_casilla_es_la_de_siempre(self):
        self.assertEqual(casilla.carpeta(self.config, "Faro Norte").name, "faro-norte")
        self.assertEqual(casilla.separar(self.config, ["Faro Norte", "Molino"]), [])
        self.assertFalse((self.config.estado / "casillas" / casilla.FICHAS).exists())

    def test_el_que_llego_despues_se_aparta_y_se_lleva_lo_suyo(self):
        # la casilla compartida, como quedó: lo de «faro» desde antes, y lo de «Faro» mezclado
        casilla.dejar(self.config, "faro", self.mensaje("20261001090000-a", "faro"))
        casilla.marcar_entregados(self.config, "faro", ["20261001090000-a"])
        casilla.dejar(self.config, "faro", self.mensaje("20261117140343-b", "Faro"))
        casilla.dejar(self.config, "faro", self.mensaje("20261117140400-c", "faro"))
        casilla.dejar(self.config, "faro", self.mensaje("20261117140500-d", "Faro", modo="aviso"))
        self.assertEqual(len(casilla.pendientes(self.config, "Faro")), 3)  # la misma casilla: el error

        self.assertEqual(casilla.separar(self.config, ["faro", "Faro"]), ["Faro"])
        # «faro» tenía la casilla desde antes (su mensaje es el más viejo): se queda con ella, y con su historia
        self.assertEqual(casilla.ficha(self.config, "faro"), "faro")
        self.assertEqual(casilla.ficha(self.config, "Faro"), casilla.apartada("Faro"))
        self.assertEqual(self.ids("faro"), ["20261117140400-c"])
        self.assertEqual(self.ids("Faro"), ["20261117140343-b", "20261117140500-d"])
        self.assertTrue((casilla.carpeta(self.config, "faro") / "entregados" / "20261001090000-a.json").exists())
        # lo que llega después va a cada uno, y el gancho de cada uno entrega solo lo suyo
        casilla.dejar(self.config, "Faro", self.mensaje("20261117150000-e", "Faro", "solo para Faro"))
        salida = json.loads(casilla.para_gancho(self.config, "faro", "Stop"))
        self.assertNotIn("Faro", salida["reason"].replace("para faro", ""))
        salida = json.loads(casilla.para_gancho(self.config, "Faro", "Stop"))
        self.assertIn("solo para Faro", salida["reason"])
        # y separar otra vez no cambia nada
        self.assertEqual(casilla.separar(self.config, ["faro", "Faro"]), [])

    def test_lo_que_un_gancho_del_otro_tenia_en_camino_vuelve_a_esperar_para_el_suyo(self):
        conversacion = Path(self.tmp.name) / "conversacion.jsonl"
        conversacion.write_text("")
        casilla.dejar(self.config, "faro", self.mensaje("20261117140343-b", "Faro"))
        casilla.para_gancho(self.config, "faro", "Stop", conversacion=str(conversacion))  # el gancho equivocado
        self.assertEqual([m["id"] for m in casilla.en_camino(self.config, "faro")], ["20261117140343-b"])
        casilla.apartar(self.config, "Faro")
        self.assertEqual(casilla.en_camino(self.config, "faro"), [])
        (m,) = casilla.pendientes(self.config, "Faro")
        self.assertNotIn("entrega", m)  # para él es la primera vez: sin «otra vez»

    def test_lo_que_el_gancho_del_apartado_ya_imprimio_sigue_en_camino_y_no_se_entrega_dos_veces(self):
        # su propio gancho lo tomó antes de apartarlo: lo que corresponde es ver si entró en su conversación
        self.config.estado.mkdir(parents=True)
        (self.config.estado / "sesiones.json").write_text(json.dumps({"Faro": ["s-faro"], "faro": ["s-otro"]}))
        conversacion = Path(self.tmp.name) / "s-faro.jsonl"
        conversacion.write_text("")
        casilla.dejar(self.config, "Faro", self.mensaje("x1", "Faro"))
        casilla.para_gancho(self.config, "Faro", "Stop", conversacion=str(conversacion))
        casilla.apartar(self.config, "Faro")
        self.assertEqual(casilla.pendientes(self.config, "Faro"), [])
        (m,) = casilla.en_camino(self.config, "Faro")
        self.assertEqual(m["entrega"]["conversacion"], str(conversacion))
        conversacion.write_text("[mensaje de Telar, 2026-11-17 14:03, id x1]\nhola\n")
        self.assertEqual(casilla.revisar(self.config, "Faro")["entraron"], ["x1"])

    def test_lo_que_llega_por_la_casilla_compartida_va_al_apartado_si_esta_vivo(self):
        # de un telar de antes, que publica todo en la forma normalizada: el nodo lo desvía por su `para` exacto
        casilla.apartar(self.config, "Faro")
        mensaje = self.mensaje("x1", "Faro")
        self.assertEqual(casilla.destinatario(self.config, "faro", mensaje, vivos=["faro", "Faro"]), "Faro")
        # a uno archivado no: lo que se le escribía por su nombre lo leía el vivo, y lo sigue leyendo él
        self.assertEqual(casilla.destinatario(self.config, "faro", mensaje, vivos=["faro"]), "faro")
        # y lo que es del dueño de la forma, o de un nombre que no está apartado, se queda
        self.assertEqual(casilla.destinatario(self.config, "faro", self.mensaje("x2", "faro"), ["faro", "Faro"]), "faro")
        self.assertEqual(casilla.destinatario(self.config, "faro", self.mensaje("x3", "FARO"), ["faro", "Faro"]), "faro")

    def test_se_queda_con_la_forma_el_que_la_lee(self):
        # el archivado tenía la casilla desde antes, pero lo que espera en el bus con la forma normalizada (de antes de
        # actualizar, o de un telar de antes) solo lo recoge uno vivo: el archivado se aparta
        casilla.dejar(self.config, "faro", self.mensaje("20261001090000-a", "faro"))
        self.assertEqual(casilla.separar(self.config, ["faro", "Faro"], leen=["Faro"]), ["faro"])
        self.assertEqual(casilla.ficha(self.config, "Faro"), "faro")
        # y lo que esperaba en la compartida a nombre del archivado se queda: lo leía el vivo, como hasta ahora
        self.assertEqual((self.ids("Faro"), self.ids("faro")), (["20261001090000-a"], []))

    def test_un_correo_de_otra_persona_va_a_la_casilla_por_la_que_llego(self):
        # su `para` es la palabra del directorio («Faro» → `faro`), no el nombre del apartado «faro»
        casilla.apartar(self.config, "faro")
        correo = {"id": "c1", "para": "faro", "tipo": "correo", "texto": "hola"}
        self.assertEqual(casilla.destinatario(self.config, "Faro", correo), "Faro")
        self.assertEqual(casilla.destinatario(self.config, "Faro", {**correo, "tipo": "mensaje"}, ["faro", "Faro"]),
                         "faro")

    def test_si_la_forma_la_tiene_otra_maquina_el_de_aqui_se_aparta(self):
        self.assertEqual(casilla.separar(self.config, ["Faro"], {"faro": "faro"}), ["Faro"])
        # el mismo hilo publicado allá (se está mudando) no es otro
        self.assertEqual(casilla.separar(self.config, ["Molino"], {"molino": "Molino"}), [])

    def test_un_disco_que_no_distingue_mayusculas_no_los_junta(self):
        """Simulado: cada carpeta se crea con su nombre en minúsculas, como la ve un disco que no distingue
        mayúsculas (APFS, por defecto). Dos carpetas que solo difieren en mayúsculas serían la misma."""
        nombres = ["faro", "Faro", "FARO", "Fáro"]
        for n in nombres[1:]:
            casilla.apartar(self.config, n)
        carpetas = {n: casilla.carpeta(self.config, n).name for n in nombres}
        self.assertEqual(len({c.casefold() for c in carpetas.values()}), len(nombres))
        ficha = casilla.ficha
        with mock.patch.object(casilla, "ficha", lambda config, hilo: ficha(config, hilo).casefold()):
            for i, n in enumerate(nombres):
                casilla.dejar(self.config, n, self.mensaje(f"m{i}", n))
            for i, n in enumerate(nombres):
                self.assertEqual(self.ids(n), [f"m{i}"], n)
        # y con la forma de antes, la de un solo nombre para los cuatro, se juntaban
        self.assertEqual(len({casilla.nombre_de_carpeta(n).casefold() for n in nombres}), 1)

    def test_renombrar_lleva_lo_que_esperaba_y_suelta_la_ficha_apartada(self):
        casilla.apartar(self.config, "Faro")
        casilla.dejar(self.config, "Faro", self.mensaje("x1", "Faro"))
        self.assertEqual(casilla.mudar(self.config, "Faro", "Faro Norte"), 1)
        casilla.soltar_ficha(self.config, "Faro")
        self.assertEqual(self.ids("Faro Norte"), ["x1"])
        self.assertEqual(casilla.ficha(self.config, "Faro"), "faro")
        self.assertEqual(casilla.ficha(self.config, "Faro Norte"), "faro-norte")


# ── el bus: a quién se le publica ──────────────────────────────────────────────────────────────────────────


class KeyNotFoundError(Exception):
    """La de nats-py cuando una clave del estado no está (aquí sin nats-py instalado)."""


class Kv:
    def __init__(self, entradas: dict[str, dict] | None = None):
        self.entradas = dict(entradas or {})

    async def get(self, clave):
        if clave not in self.entradas:
            raise KeyNotFoundError(clave)
        return SimpleNamespace(value=json.dumps(self.entradas[clave]).encode())


class BusFalso:
    """`conectar` y `asegurar` del bus: lo que se publica queda en `publicados`; el estado es `kv`."""

    def __init__(self, kv: Kv):
        self.kv, self.publicados = kv, []
        bus = self

        class Js:
            async def key_value(self, nombre):
                return bus.kv

            async def publish(self, tema, datos, headers=None, timeout=None):
                bus.publicados.append((tema, json.loads(datos)))
                return SimpleNamespace(seq=len(bus.publicados), duplicate=False)

        class Nc:
            def jetstream(self):
                return Js()

            async def close(self):
                pass

        async def conectar(_config):
            return Nc()

        async def asegurar(_js):
            return None

        self.parches = [mock.patch.object(mod_bus, "conectar", conectar),
                        mock.patch.object(mod_bus, "asegurar", asegurar)]

    def __enter__(self):
        for p in self.parches:
            p.start()
        return self

    def __exit__(self, *_):
        for p in self.parches:
            p.stop()

    def temas(self) -> list[str]:
        return [t for t, _ in self.publicados if t.startswith("casilla.")]


class AQuienSePublica(ConEstado):
    def test_un_hilo_apartado_aqui_tiene_su_tema_y_su_clave(self):
        casilla.apartar(self.config, "Faro")
        self.assertEqual(mod_bus.tema_casilla(self.config, "Faro"), f"casilla.ana.{casilla.apartada('Faro')}")
        self.assertEqual(mod_bus.clave_estado(self.config, "Faro"), f"ana.{casilla.apartada('Faro')}")
        self.assertEqual(mod_bus.tema_casilla(self.config, "faro"), "casilla.ana.faro")
        # de otra persona no se saben sus apartados: la forma de siempre
        self.assertEqual(mod_bus.tema_casilla(self.config, "Faro", "bea"), "casilla.bea.faro")

    def test_al_apartado_de_otra_maquina_se_lo_encuentra_por_su_nombre_exacto_en_el_estado(self):
        kv = Kv({f"ana.{casilla.apartada('Faro')}": {"nombre": "Faro", "maquina": "servidor"},
                 "ana.faro": {"nombre": "faro", "maquina": "servidor"}})
        with BusFalso(kv) as bus:
            mod_bus.enviar(self.config, "Faro", "hola", de="Telar")
            mod_bus.enviar(self.config, "faro", "hola", de="Telar")
            mod_bus.enviar(self.config, "Molino", "hola", de="Telar")
            self.assertEqual(mod_bus.estado_de(self.config, "Faro"), {"nombre": "Faro", "maquina": "servidor"})
            self.assertEqual(mod_bus.estado_de(self.config, "faro")["nombre"], "faro")
        self.assertEqual(bus.temas(),
                         [f"casilla.ana.{casilla.apartada('Faro')}", "casilla.ana.faro", "casilla.ana.molino"])

    def test_una_clave_apartada_con_otro_nombre_no_cuenta(self):
        kv = Kv({f"ana.{casilla.apartada('Faro')}": {"nombre": "otro", "maquina": "servidor"}})
        with BusFalso(kv) as bus:
            mod_bus.enviar(self.config, "Faro", "hola", de="Telar")
        self.assertEqual(bus.temas(), ["casilla.ana.faro"])

    def test_si_el_estado_no_responde_se_reintenta_y_no_queda_en_la_de_siempre(self):
        """Si quedara en la de siempre, el reintento (con el mismo id, en otro tema) lo descartaría el bus por
        repetido, y el mensaje se quedaría donde el apartado no lo lee."""
        kv = Kv({f"ana.{casilla.apartada('Faro')}": {"nombre": "Faro", "maquina": "servidor"}})
        fallas = [TimeoutError("nats: timeout")]

        class AlSegundo(Kv):
            async def get(self, clave):
                if fallas:
                    raise fallas.pop()
                return await kv.get(clave)

        with BusFalso(AlSegundo()) as bus:
            mod_bus.enviar(self.config, "Faro", "hola", de="Telar")
        self.assertEqual(bus.temas(), [f"casilla.ana.{casilla.apartada('Faro')}"])

    def test_si_el_estado_no_responde_nunca_no_se_publica_y_se_dice(self):
        class Roto(Kv):
            async def get(self, clave):
                raise RuntimeError("el estado no responde")

        with BusFalso(Roto()) as bus:
            with self.assertRaises(mod_bus.ErrorDeBus):
                mod_bus.enviar(self.config, "Faro", "hola", de="Telar")
            self.assertEqual(mod_bus.estado_de(self.config, "Faro"), {})  # leer el estado no se cae
        self.assertEqual(bus.temas(), [])

    def test_si_quedaron_las_dos_claves_vale_la_ultima(self):
        # «Faro» estuvo apartado y dejó de estarlo (o al revés): su clave de antes quedó en el estado
        apartada = {"nombre": "Faro", "maquina": "servidor", "actualizado": "2026-11-17T10:00:00-03:00"}
        llana = {"nombre": "Faro", "maquina": "servidor", "actualizado": "2026-11-17T14:00:00+00:00"}  # 11:00 aquí
        with BusFalso(Kv({f"ana.{casilla.apartada('Faro')}": apartada, "ana.faro": llana})) as bus:
            mod_bus.enviar(self.config, "Faro", "hola", de="Telar")
        self.assertEqual(bus.temas(), ["casilla.ana.faro"])
        with BusFalso(Kv({f"ana.{casilla.apartada('Faro')}": {**apartada, "actualizado": "2026-11-17T12:00:00-03:00"},
                          "ana.faro": llana})) as bus:
            mod_bus.enviar(self.config, "Faro", "hola", de="Telar")
        self.assertEqual(bus.temas(), [f"casilla.ana.{casilla.apartada('Faro')}"])


class PorIdOPorNombre(ConEstado):
    """`telar mensaje @2` llega a ese hilo aunque otro tenga un nombre que choca; un nombre que no es exactamente el
    de ninguno y se parece a varios se rechaza."""

    def setUp(self):
        super().setUp()
        self.hilos = [SimpleNamespace(id="@1", nombre="faro", remoto="", archivado=False),
                      SimpleNamespace(id="@2", nombre="Faro", remoto="", archivado=False)]
        tel = SimpleNamespace(hilos=self.hilos, vivo=lambda h: True,
                              estado=SimpleNamespace(ajenos=lambda viejos=False: {}))
        for p in (mock.patch("telar.ordenes._comun.tejer", return_value=tel),
                  mock.patch("telar.agentes.descubrir", return_value=[])):
            p.start()
            self.addCleanup(p.stop)
        self.ctx = SimpleNamespace(config=self.config)
        casilla.apartar(self.config, "Faro")

    def enviar(self, para: str) -> list[str]:
        from telar.ordenes import mensaje

        with BusFalso(Kv()) as bus:
            mensaje.enviar(self.ctx, para, "hola")
        return bus.temas()

    def test_por_id_llega_a_ese_hilo(self):
        self.assertEqual(self.enviar("@2"), [f"casilla.ana.{casilla.apartada('Faro')}"])
        self.assertEqual(self.enviar("@1"), ["casilla.ana.faro"])

    def test_por_nombre_exacto_tambien(self):
        self.assertEqual(self.enviar("Faro"), [f"casilla.ana.{casilla.apartada('Faro')}"])
        self.assertEqual(self.enviar("faro"), ["casilla.ana.faro"])

    def test_un_nombre_que_se_parece_a_varios_se_rechaza(self):
        from telar.ordenes import mensaje

        with self.assertRaises(mensaje.Ambiguo) as e:
            self.enviar("FARO")
        self.assertIn("«Faro»", str(e.exception))
        self.assertIn("«faro»", str(e.exception))

    def test_un_nombre_que_se_parece_a_uno_solo_es_ese(self):
        self.hilos.pop(0)
        self.assertEqual(self.enviar("FARO"), [f"casilla.ana.{casilla.apartada('Faro')}"])

    def test_entre_uno_vivo_y_uno_archivado_el_nombre_va_al_vivo(self):
        """Como hasta ahora, cuando compartían casilla y la leía el vivo: «faro», «FARO» o «Faro» van a «Faro». Al
        archivado se llega por su dirección (o su id)."""
        self.hilos[0].archivado = True  # «faro», archivado; «Faro», vivo
        for nombre in ("faro", "FARO", "Faro", "Fáro"):
            self.assertEqual(self.enviar(nombre), [f"casilla.ana.{casilla.apartada('Faro')}"], nombre)
        self.assertEqual(self.enviar("hilo:faro"), ["casilla.ana.faro"])

    def test_entre_archivados_el_exacto(self):
        for h in self.hilos:
            h.archivado = True
        self.assertEqual(self.enviar("faro"), ["casilla.ana.faro"])
        self.assertEqual(self.enviar("Faro"), [f"casilla.ana.{casilla.apartada('Faro')}"])


# ── el nodo ───────────────────────────────────────────────────────────────────────────────────────────────


class Msg:
    def __init__(self, datos: dict):
        self.data = json.dumps(datos).encode()
        self.confirmado = False

    async def ack(self):
        self.confirmado = True


class Sub:
    def __init__(self, msgs):
        self.msgs = list(msgs)

    async def fetch(self, n, timeout=None):
        salida, self.msgs = self.msgs, []
        return salida


class KvNodo:
    def __init__(self, entradas: dict[str, dict] | None = None):
        self.entradas, self.borrados = dict(entradas or {}), []

    async def get(self, k):
        if k not in self.entradas:
            raise KeyNotFoundError(k)
        return SimpleNamespace(value=json.dumps(self.entradas[k]).encode())

    async def delete(self, k):
        self.borrados.append(k)
        self.entradas.pop(k, None)


class ElNodo(ConEstado):
    def nodo(self):
        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.config, n.persona, n.yo = self.config, "ana", "laptop"
        n.publicado, n.vistos, n.subs, n.renombrados = {}, {}, {}, {}
        n.lineas = []
        n.anotar = n.lineas.append
        n.avisos = []
        n.avisar = lambda nombre, info, encargo=False: n.avisos.append(nombre) or "avisado"
        return n

    def test_lo_que_llega_por_la_compartida_para_un_apartado_archivado_lo_lee_el_vivo(self):
        casilla.apartar(self.config, "Faro")
        n = self.nodo()
        n.subs = {"faro": Sub([Msg(self.mensaje("x1", "Faro"))])}
        asyncio.run(n._recoger({"faro": {}}))  # «Faro» no está vivo: el nodo no lo suscribe
        self.assertEqual((self.ids("faro"), self.ids("Faro")), (["x1"], []))

    def test_aparta_al_de_aqui_si_la_forma_la_tiene_otra_maquina(self):
        n = self.nodo()
        n.vistos = {"ana.faro": {"nombre": "faro", "maquina": "servidor"}}
        self.assertEqual(n.separar(["Faro", "Molino"]), ["Faro"])
        self.assertIn(casilla.apartada("Faro"), n.lineas[0])

    def test_lo_que_llega_por_la_casilla_compartida_va_al_apartado_y_se_le_avisa_a_el(self):
        casilla.apartar(self.config, "Faro")
        n = self.nodo()
        para_faro, para_el_otro = Msg(self.mensaje("x1", "Faro")), Msg(self.mensaje("x2", "faro"))
        n.subs = {"faro": Sub([para_faro, para_el_otro]), casilla.apartada("Faro"): Sub([])}
        asyncio.run(n._recoger({"faro": {}, "Faro": {}}))
        self.assertEqual((self.ids("faro"), self.ids("Faro")), (["x2"], ["x1"]))
        self.assertEqual(sorted(n.avisos), ["Faro", "faro"])
        self.assertTrue(para_faro.confirmado and para_el_otro.confirmado)

    def test_al_arrancar_cuenta_lo_que_quedo_de_las_otras_maquinas(self):
        # antes de que el vigía traiga lo del bus: lo que el nodo dejó la última vez en ajenos.json
        self.config.estado.mkdir(parents=True)
        (self.config.estado / "ajenos.json").write_text(json.dumps({"faro": {"maquina": "servidor"}}))
        self.assertEqual(self.nodo().separar(["Faro"]), ["Faro"])

    def test_uno_apartado_alla_no_ocupa_la_forma_de_aqui(self):
        # su nodo publica su ficha: el de aquí se queda con la forma normalizada (si no, nadie la tendría)
        self.config.estado.mkdir(parents=True)
        (self.config.estado / "ajenos.json").write_text(
            json.dumps({"Faro": {"maquina": "servidor", "ficha": casilla.apartada("Faro")}}))
        n = self.nodo()
        n.vistos = {f"ana.{casilla.apartada('Faro')}": {"nombre": "Faro", "maquina": "servidor"}}
        self.assertEqual(n.separar(["faro"]), [])
        self.assertEqual(casilla.ficha(self.config, "faro"), "faro")

    def test_la_clave_de_estado_de_antes_del_apartado_se_suelta(self):
        n = self.nodo()
        antes = {"nombre": "Faro", "vivo": True}
        n.publicado = {"ana.faro": json.dumps(antes)}
        casilla.apartar(self.config, "Faro")
        kv = KvNodo({"ana.faro": antes})
        asyncio.run(n._soltar_claves_movidas(kv, {"Faro": {}}))
        self.assertEqual((kv.borrados, n.publicado), (["ana.faro"], {}))
        # si ahí ya publica el dueño de la forma (en otra máquina: se pisaban), no se le borra
        n.publicado = {"ana.faro": json.dumps(antes)}
        kv = KvNodo({"ana.faro": {"nombre": "faro", "maquina": "servidor"}})
        asyncio.run(n._soltar_claves_movidas(kv, {"Faro": {}}))
        self.assertEqual((kv.borrados, n.publicado), ([], {}))
        # y la apartada de uno que dejó de estarlo (se renombró): que quien le escriba a otro «Faro» no vaya ahí
        casilla.soltar_ficha(self.config, "Faro")
        n.publicado = {f"ana.{casilla.apartada('Faro')}": json.dumps(antes)}
        kv = KvNodo({f"ana.{casilla.apartada('Faro')}": antes})
        asyncio.run(n._soltar_claves_movidas(kv, {"Faro Norte": {}}))
        self.assertEqual((kv.borrados, n.publicado), ([f"ana.{casilla.apartada('Faro')}"], {}))
        casilla.apartar(self.config, "Faro")
        # si el dueño de la forma también vive aquí, la clave es suya: no se borra, la vuelve a publicar él
        n.publicado = {"ana.faro": json.dumps(antes)}
        kv = KvNodo({"ana.faro": antes})
        asyncio.run(n._soltar_claves_movidas(kv, {"Faro": {}, "faro": {}}))
        self.assertEqual((kv.borrados, n.publicado), ([], {}))


# ── entre personas ────────────────────────────────────────────────────────────────────────────────────────


class EntrePersonas(ConEstado):
    def test_el_directorio_publica_la_palabra_del_apartado_y_el_correo_la_respeta(self):
        casilla.apartar(self.config, "Faro")
        foto = {"maquina": "laptop",
                "hilos": [{"nombre": "Faro", "publico": True}, {"nombre": "faro", "publico": True}]}
        d = entre_personas.directorio(foto, "ana", self.config)
        self.assertEqual([h["ext"] for h in d["hilos"]], [casilla.apartada("Faro"), "faro"])
        c = entre_personas.correo({"para": casilla.apartada("Faro"), "texto": "hola"}, "bea")
        self.assertEqual(c["para"], casilla.apartada("Faro"))
        self.assertEqual(entre_personas.correo({"para": "Faro Norte", "texto": "hola"}, "bea")["para"], "faro-norte")


# ── las órdenes: un nombre que choca no se acepta ─────────────────────────────────────────────────────────


class UnNombreQueChoca(Orden):
    def config(self):
        return SimpleNamespace(estado=Path(os.environ["TELAR_ESTADO"]))

    def test_hijo_se_niega_y_dice_con_cual_y_propone_otro(self):
        self.vincular_faro()
        codigo, _, error = self.correr("hilo", "hijo", "Faro", "--hilo", "molino", "--texto", "algo")
        self.assertEqual(codigo, 2)
        self.assertIn("«Faro» choca con «faro»", error)
        self.assertIn("«Faro 2»", error)
        # archivado, también
        self.correr("hilo", "archivar", "--hilo", "faro")
        codigo, _, error = self.correr("hilo", "hijo", "Fáro", "--hilo", "molino", "--texto", "algo")
        self.assertEqual(codigo, 2)
        self.assertIn("choca con «faro» (archivado", error)

    def test_hijo_se_niega_si_choca_con_uno_de_otra_maquina_segun_el_bus(self):
        estado = Path(os.environ["TELAR_ESTADO"])
        estado.mkdir(parents=True, exist_ok=True)
        (estado / "ajenos.json").write_text(json.dumps({"FARO": {"maquina": "servidor", "archivado": False}}))
        codigo, _, error = self.correr("hilo", "hijo", "Faro", "--hilo", "molino", "--texto", "algo")
        self.assertEqual(codigo, 2)
        self.assertIn("choca con «FARO» (en servidor)", error)
        # aunque el nodo ya no lo refresque: un nombre no caduca
        viejo = time.time() - 3600
        os.utime(estado / "ajenos.json", (viejo, viejo))
        codigo, _, error = self.correr("hilo", "hijo", "Faro", "--hilo", "molino", "--texto", "algo")
        self.assertIn("choca con «FARO»", error)

    def test_renombrar_se_niega_si_choca_con_otro_pero_no_consigo_mismo(self):
        self.vincular_faro()
        self.correr("vincular", "proyectos/molino", "--hilo", "molino")
        codigo, _, error = self.correr("hilo", "renombrar", "FARO", "--hilo", "molino")
        self.assertEqual(codigo, 2)
        self.assertIn("«FARO» choca con «faro»", error)
        self.assertIn("«FARO 2»", error)
        codigo, _, error = self.correr("hilo", "renombrar", "Faro", "--hilo", "faro")
        self.assertEqual(codigo, 0, error)

    def test_renombrar_lleva_su_casilla(self):
        self.vincular_faro()
        casilla.dejar(self.config(), "faro", {"id": "x1", "para": "faro", "texto": "hola"})
        codigo, salida, error = self.correr("hilo", "renombrar", "Faro Norte", "--hilo", "faro")
        self.assertEqual(codigo, 0, error)
        self.assertIn("1 mensaje(s)", salida)
        self.assertEqual([m["id"] for m in casilla.pendientes(self.config(), "Faro Norte")], ["x1"])
        self.assertEqual(casilla.pendientes(self.config(), "faro"), [])
