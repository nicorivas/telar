"""La copia de una conversación a otra máquina de a pedazos (telar.replica): solo lo que allá falta, retomable si se
corta, verificada al final, con su carpeta `<sid>/`, y la copia de allá aparte si se siguió por su lado.

Las dos máquinas son dos carpetas de Claude (`CLAUDE_CONFIG_DIR`) y dos de estado en este proceso; el bus, una función
que le pasa cada pedido a lo que contesta el nodo de allá (sin red: la red de verdad, en scripts/probar_mudanza.py)."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import replica, rutas

SID = "0f3c2a9e-1111-2222-3333-444455556666"


def linea(tipo: str, **extra) -> bytes:
    return json.dumps({"type": tipo, **extra}).encode() + b"\n"


def conversacion(n: int, semilla: int = 1, *, con_imagenes: bool = True) -> bytes:
    """Unas `n` líneas con la forma de una conversación: texto y, de vez en cuando, una imagen (lo que no comprime)."""
    rnd = random.Random(semilla)
    salida = []
    for i in range(n):
        if con_imagenes and i % 7 == 3:
            salida.append(linea("user", imagen=base64.b64encode(rnd.randbytes(3000)).decode()))
        else:
            salida.append(linea(rnd.choice(["user", "assistant"]), n=i, texto="la conversación viaja " * 20))
    return b"".join(salida)


class _DosMaquinas(Prueba):
    """Aquí y allá: cada una con su carpeta de Claude, su estado y su raíz (donde arranca el agente)."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        d = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.aqui_claude, self.alla_claude = d / "aqui-claude", d / "alla-claude"
        self.alla_raiz = d / "alla-raiz"
        self.alla_raiz.mkdir()
        self.ctx_alla = SimpleNamespace(config=SimpleNamespace(estado=str(d / "alla-estado"), raiz=str(self.alla_raiz)))
        self.destino = {"carpeta": str(self.alla_raiz)}
        # la conversación de aquí, donde Claude la deja al arrancar en /aqui/vida
        with self.en(self.aqui_claude):
            self.proy_aqui = rutas.proyecto(d / "aqui-vida")
        self.proy_aqui.mkdir(parents=True)
        self.archivo = self.proy_aqui / f"{SID}.jsonl"
        with self.en(self.alla_claude):
            self.proy_alla = rutas.proyecto(self.alla_raiz)
        self.pedidos: list[str] = []
        self.cortar_en: int | None = None  # el pedazo (contando desde 1) en que se corta la red

    def en(self, claude: Path):
        return mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude)})

    def corrida(self, hacer):
        """Lo que haría `_corrida` con una conexión al bus: cada pedido, contestado por lo de allá."""
        escritos = [0]

        async def pedir(verbo: str, cuerpo: bytes, espera: float) -> bytes:
            self.pedidos.append(verbo)
            with self.en(self.alla_claude):
                if verbo == replica.VERBO_ESTADO:
                    r = replica.estado(self.ctx_alla, json.loads(cuerpo))
                elif verbo == replica.VERBO_ESCRIBIR:
                    escritos[0] += 1
                    if self.cortar_en is not None and escritos[0] >= self.cortar_en:
                        raise ConnectionResetError("se cortó la red")
                    meta, datos = replica.recibir(cuerpo)
                    r = replica.escribir(self.ctx_alla.config, meta, datos)
                elif verbo == replica.VERBO_CERRAR:
                    r = replica.cerrar(self.ctx_alla, json.loads(cuerpo))
                else:
                    raise AssertionError(verbo)
            return json.dumps(r).encode()

        return asyncio.run(hacer(pedir, 1 << 20))

    def mandar(self, **k) -> dict:
        k.setdefault("pausas", ())
        return replica.mandar(SimpleNamespace(), "telar", SID, self.archivo, self.destino, corrida=self.corrida, **k)

    def alla(self, ruta: str = f"{SID}.jsonl") -> Path:
        return self.proy_alla / ruta

    def escribir(self, ruta: Path, datos: bytes) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos)


class LaPrimeraVez(_DosMaquinas):
    def test_va_entera_con_su_carpeta_y_queda_donde_claude_la_busca(self):
        self.escribir(self.archivo, conversacion(300))
        self.escribir(self.proy_aqui / SID / "tool-results" / "toolu_01.txt", b"una salida larga\n" * 500)
        self.escribir(self.proy_aqui / SID / "subagents" / "agent-a1.jsonl", conversacion(40, 2))
        r = self.mandar()
        self.assertEqual(r["archivos"], 3)
        total = sum(p.stat().st_size for p in [self.archivo, *(self.proy_aqui / SID).rglob("*.txt"),
                                                *(self.proy_aqui / SID).rglob("*.jsonl")])
        self.assertEqual((r["bytes"], r["mandados"]), (total, total))
        self.assertLess(r["red"], r["mandados"], "el texto viaja comprimido")
        self.assertEqual(Path(r["conversacion"]), self.alla())
        for rel in (f"{SID}.jsonl", f"{SID}/tool-results/toolu_01.txt", f"{SID}/subagents/agent-a1.jsonl"):
            self.assertEqual(self.alla(rel).read_bytes(), (self.proy_aqui / rel).read_bytes(), rel)
        self.assertEqual(oct(self.alla().stat().st_mode & 0o777), "0o600")
        self.assertFalse((replica.carpeta_llegadas(self.ctx_alla.config) / SID).exists(), "lo juntado se va")
        self.assertEqual(r["aparte"], [])

    def test_sin_tope_de_tamano_y_de_a_pedazos(self):
        # el tope de 25 MB del bus no existe aquí: cuántos pedazos, lo dice el tamaño
        self.escribir(self.archivo, conversacion(800))
        with mock.patch.object(replica, "TROZO", 32 * 1024):
            r = self.mandar()
        n = self.pedidos.count(replica.VERBO_ESCRIBIR)
        self.assertGreaterEqual(n, self.archivo.stat().st_size // (32 * 1024))
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())
        self.assertEqual(r["mandados"], self.archivo.stat().st_size)


class DeVueltaSoloLoQueFalta(_DosMaquinas):
    def test_si_alla_hay_un_comienzo_va_solo_la_cola(self):
        antes = conversacion(300)
        # allá quedó la de cuando se fue, más lo que Claude anotó al cerrarse (su costo, el último prompt)
        self.escribir(self.alla(), antes + linea("last-prompt") + linea("cost-state"))
        cola = conversacion(20, 9)
        self.escribir(self.archivo, antes + cola)
        r = self.mandar()
        self.assertEqual(r["mandados"], len(cola))
        self.assertEqual(self.alla().read_bytes(), antes + cola)
        self.assertEqual(list(self.proy_alla.glob("*.bak")), [], "la de allá se siguió aquí: no queda aparte")

    def test_igual_entera_no_manda_nada(self):
        self.escribir(self.archivo, conversacion(100))
        self.escribir(self.alla(), self.archivo.read_bytes())
        r = self.mandar()
        self.assertEqual(r["mandados"], 0)
        self.assertNotIn(replica.VERBO_ESCRIBIR, self.pedidos)
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())

    def test_su_carpeta_tambien_solo_lo_que_falta(self):
        self.escribir(self.archivo, conversacion(100))
        self.escribir(self.alla(), self.archivo.read_bytes())
        sub = conversacion(50, 3)
        self.escribir(self.proy_aqui / SID / "tool-results" / "viejo.txt", b"x" * 5000)
        self.escribir(self.alla(f"{SID}/tool-results/viejo.txt"), b"x" * 5000)
        self.escribir(self.proy_aqui / SID / "subagents" / "agent-1.jsonl", sub + linea("user", mas=1))
        self.escribir(self.alla(f"{SID}/subagents/agent-1.jsonl"), sub)
        self.escribir(self.proy_aqui / SID / "tool-results" / "nuevo.txt", b"y" * 700)
        r = self.mandar()
        self.assertEqual(r["mandados"], len(linea("user", mas=1)) + 700)
        for rel in (f"{SID}/tool-results/viejo.txt", f"{SID}/subagents/agent-1.jsonl", f"{SID}/tool-results/nuevo.txt"):
            self.assertEqual(self.alla(rel).read_bytes(), (self.proy_aqui / rel).read_bytes(), rel)

    def test_lo_de_alla_que_no_esta_aqui_no_se_borra(self):
        self.escribir(self.archivo, conversacion(50))
        self.escribir(self.alla(f"{SID}/tool-results/solo-alla.txt"), b"de alla")
        self.mandar()
        self.assertEqual(self.alla(f"{SID}/tool-results/solo-alla.txt").read_bytes(), b"de alla")

    def test_una_copia_en_otra_carpeta_de_proyecto_sirve_y_no_queda_repetida(self):
        # allá el agente arrancaba en otra parte: su copia sirve de comienzo, y al llegar no quedan dos con el mismo id
        antes = conversacion(200)
        otra = self.alla_claude / "projects" / "-otra-carpeta" / f"{SID}.jsonl"
        self.escribir(otra, antes)
        self.escribir(self.archivo, antes + linea("user", nuevo=1))
        r = self.mandar()
        self.assertEqual(r["mandados"], len(linea("user", nuevo=1)))
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())
        self.assertFalse(otra.exists())
        with self.en(self.alla_claude):
            self.assertEqual(rutas.conversacion(SID), self.alla())


class SiAllaSeSiguioPorSuLado(_DosMaquinas):
    def test_va_entera_y_la_de_alla_queda_aparte_con_su_fecha(self):
        comun = conversacion(100)
        self.escribir(self.alla(), comun + linea("assistant", alla=1))
        self.escribir(self.archivo, comun + linea("assistant", aqui=1))
        r = self.mandar()
        self.assertEqual(r["mandados"], self.archivo.stat().st_size)
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())
        (aparte,) = self.proy_alla.glob(f"{SID}.antes-*.jsonl.bak")
        self.assertIn(b'"alla": 1', aparte.read_bytes())
        self.assertEqual(r["aparte"], [aparte.name])
        self.assertIn("por su lado", r["aviso"])

    def test_una_huella_que_calza_por_azar_no_engana(self):
        # la cola de allá es igual a la de aquí, pero más atrás difieren: el sha256 del final lo ve, y se manda entera
        aqui = conversacion(200)
        alla = bytearray(aqui)
        alla[100:110] = b"X" * 10
        self.escribir(self.archivo, aqui + linea("user", mas=1))
        self.escribir(self.alla(), bytes(alla))
        r = self.mandar()
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())
        self.assertEqual(self.pedidos.count(replica.VERBO_CERRAR), 2, "la primera vez no calzó: de nuevo, entera")
        self.assertEqual(len(list(self.proy_alla.glob("*.bak"))), 1, "la de allá no se pierde")
        self.assertGreaterEqual(r["mandados"], self.archivo.stat().st_size)


class UnCorteAMitad(_DosMaquinas):
    def test_el_siguiente_intento_sigue_desde_lo_que_llego(self):
        self.escribir(self.archivo, conversacion(600))
        total = self.archivo.stat().st_size
        with mock.patch.object(replica, "TROZO", 16 * 1024):
            self.cortar_en = 6
            with self.assertRaisesRegex(replica.ErrorDeReplica, "el próximo intento sigue desde ahí"):
                self.mandar(intentos=1)
            juntado = replica.carpeta_llegadas(self.ctx_alla.config) / SID / f"{SID}.jsonl"
            self.assertEqual(juntado.stat().st_size, 5 * 16 * 1024, "lo que llegó queda allá")
            self.assertFalse(self.alla().exists(), "nada en su lugar hasta verificarla")
            self.cortar_en = None
            r = self.mandar()
        self.assertEqual(r["mandados"], total - 5 * 16 * 1024)
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())

    def test_si_se_corta_lo_intenta_otra_vez_solo(self):
        self.escribir(self.archivo, conversacion(400))
        cortes = iter([4])

        def corrida(hacer):
            self.cortar_en = next(cortes, None)
            return self.corrida(hacer)

        with mock.patch.object(replica, "TROZO", 16 * 1024):
            r = replica.mandar(SimpleNamespace(), "telar", SID, self.archivo, self.destino, corrida=corrida, pausas=())
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())
        self.assertEqual(self.pedidos.count(replica.VERBO_ESTADO), 2)
        self.assertEqual(r["mandados"], self.archivo.stat().st_size, "lo de los dos intentos, sin repetir")

    def test_aqui_siguio_creciendo_entre_intentos(self):
        # el agente escribió algo más entre un intento y el otro: lo juntado allá sigue siendo un comienzo
        self.escribir(self.archivo, conversacion(300))
        with mock.patch.object(replica, "TROZO", 16 * 1024):
            self.cortar_en = 3
            with self.assertRaises(replica.ErrorDeReplica):
                self.mandar(intentos=1)
            with self.archivo.open("ab") as f:
                f.write(linea("assistant", despues=1))
            self.cortar_en = None
            self.mandar()
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())

    def test_un_telar_de_antes_alla_no_se_reintenta(self):
        self.escribir(self.archivo, conversacion(10))

        def corrida(hacer):
            raise replica.SinReplica("telar no atiende «replica-estado»")

        with self.assertRaises(replica.SinReplica):
            replica.mandar(SimpleNamespace(), "telar", SID, self.archivo, self.destino, corrida=corrida, pausas=())


class LoQueRecibeAlla(_DosMaquinas):
    def escribir_pedazo(self, **meta):
        datos = meta.pop("datos", b"")
        with self.en(self.alla_claude):
            return replica.escribir(self.ctx_alla.config, {"sesion": SID, "ruta": f"{SID}.jsonl", **meta}, datos)

    def test_cada_pedazo_va_al_final_del_anterior_y_repetido_no_duplica(self):
        self.assertTrue(self.escribir_pedazo(desde=0, nuevo=1, datos=b"abc")["ok"])
        self.assertTrue(self.escribir_pedazo(desde=3, datos=b"def")["ok"])
        r = self.escribir_pedazo(desde=3, datos=b"def")
        self.assertTrue(r["ok"] and r.get("repetido"), r)
        r = self.escribir_pedazo(desde=9, datos=b"ghi")
        self.assertFalse(r["ok"])
        self.assertEqual(r["bytes"], 6, "dice cuánto tiene, para que quien manda vuelva a preguntar")
        juntado = replica.carpeta_llegadas(self.ctx_alla.config) / SID / f"{SID}.jsonl"
        self.assertEqual(juntado.read_bytes(), b"abcdef")

    def test_lo_que_no_es_de_la_conversacion_no_se_acepta(self):
        for ruta in ("../x.jsonl", "/etc/passwd", f"{SID}/../../x", f"otro-sid-1234/{SID}.jsonl", f"{SID}/a b.txt", f"{SID}"):
            with self.subTest(ruta):
                self.assertFalse(replica.ruta_valida(SID, ruta))
                with self.en(self.alla_claude):
                    self.assertFalse(replica.escribir(self.ctx_alla.config, {"sesion": SID, "ruta": ruta, "desde": 0}, b"x")["ok"])
        self.assertFalse(replica.estado(self.ctx_alla, {"sesion": SID, "rutas": ["../x"], **self.destino})["ok"])
        self.assertFalse(replica.cerrar(self.ctx_alla, {"sesion": SID, "archivos": {"../x": [1, "a"]}, **self.destino})["ok"])
        self.assertFalse(replica.estado(self.ctx_alla, {"sesion": "../..", "rutas": [], **self.destino})["ok"])
        # la base es un nombre suelto de carpeta de proyecto, no una ruta
        r = self.escribir_pedazo(desde=5, nuevo=1, base="../../etc", datos=b"x")
        self.assertFalse(r["ok"])

    def test_un_pedazo_comprimido_que_crece_de_mas_no_se_acepta(self):
        import zlib

        bomba = zlib.compress(b"\0" * (3 * replica.TROZO))
        r = self.escribir_pedazo(desde=0, nuevo=1, z=1, datos=bomba)
        self.assertFalse(r["ok"])
        self.assertIn("más grande", r["error"])

    def test_al_cerrar_lo_que_no_calza_no_se_mueve(self):
        self.escribir_pedazo(desde=0, nuevo=1, datos=b'{"type":"user"}\n')
        with self.en(self.alla_claude):
            r = replica.cerrar(self.ctx_alla, {"sesion": SID, **self.destino,
                                               "archivos": {f"{SID}.jsonl": [100, "0" * 64]}})
        self.assertFalse(r["ok"])
        self.assertEqual(r["problemas"], {f"{SID}.jsonl": "incompleto"})
        self.assertFalse(self.alla().exists())

    def test_las_llegadas_viejas_se_borran(self):
        import time

        vieja = replica.carpeta_llegadas(self.ctx_alla.config) / "abandonada-0000"
        vieja.mkdir(parents=True)
        os.utime(vieja, (time.time() - replica.VIEJA - 10,) * 2)
        with self.en(self.alla_claude):
            replica.estado(self.ctx_alla, {"sesion": SID, "rutas": [], **self.destino})
        self.assertFalse(vieja.exists())


class DondeSePuedeCortar(Prueba):
    def test_su_largo_y_lo_que_anota_claude_al_cerrarse(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            mensajes = linea("user", n=1) + linea("assistant", n=2)
            p.write_bytes(mensajes + linea("last-prompt") + linea("cost-state") + b'{"type":"cost-st')
            c = replica.cortes(p)
            self.assertEqual(c[0], p.stat().st_size)
            self.assertIn(len(mensajes), c)
            self.assertEqual(c[-1], len(mensajes), "no corta antes del último mensaje")
            p.write_bytes(mensajes)
            self.assertEqual(replica.cortes(p), [len(mensajes)])
            q = Path(d) / "r.txt"
            q.write_bytes(b"x\n" + linea("cost-state"))
            self.assertEqual(replica.cortes(q), [q.stat().st_size], "otro archivo, solo su largo")

    def test_continua(self):
        with tempfile.TemporaryDirectory() as d:
            vieja, nueva = Path(d) / "v.jsonl", Path(d) / "n.jsonl"
            base = linea("user", n=1)
            vieja.write_bytes(base + linea("cost-state"))
            nueva.write_bytes(base + linea("assistant", n=2))
            self.assertTrue(replica.continua(vieja, nueva))
            vieja.write_bytes(base + linea("assistant", n=9))
            self.assertFalse(replica.continua(vieja, nueva))


class LasRutasDeClaude(Prueba):
    def test_aplanar_y_donde_esta(self):
        self.assertEqual(rutas.aplanar("/Users/ana/vida"), "-Users-ana-vida")
        self.assertEqual(rutas.aplanar("/home/ana/mi vida.x"), "-home-ana-mi-vida-x")
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": d}):
            self.assertEqual(rutas.proyectos(), Path(d) / "projects")
            uno = Path(d) / "projects" / "-a" / f"{SID}.jsonl"
            dos = Path(d) / "projects" / "-b" / f"{SID}.jsonl"
            for p in (uno, dos):
                p.parent.mkdir(parents=True)
                p.write_text("{}")
            self.assertEqual(rutas.conversacion(SID, dos.parent), dos)
            self.assertIn(rutas.conversacion(SID), (uno, dos))
            self.assertIsNone(rutas.conversacion("no-esta-1234"))


class LoQueAtiendeElNodo(_DosMaquinas):
    """Los pedidos de la copia en el nodo (telar.ordenes.nodo): un pedazo llega como bytes crudos detrás de su línea
    JSON, no como un pedido JSON; el progreso de una mudanza se lee desde la máquina que pidió traer el hilo."""

    class Mensaje:
        def __init__(self, data: bytes):
            self.data, self.reply, self.subject = data, "_INBOX.1", "rpc.ana.servidor.x"
            self.respuestas: list = []

        async def respond(self, datos):
            from telar import bus as mod_bus

            self.respuestas.append(mod_bus.desempacar(datos))

    def nodo(self):
        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.config, n.ctx = self.ctx_alla.config, self.ctx_alla
        return n

    def test_un_pedazo_crudo(self):
        n = self.nodo()
        cuerpo, _ = replica._pedazo({"sesion": SID, "ruta": f"{SID}.jsonl", "desde": 0, "nuevo": 1}, b"x" * 10_000)
        m = self.Mensaje(cuerpo)
        with self.en(self.alla_claude):
            asyncio.run(n._replica_escribir(m))
        self.assertEqual(m.respuestas, [{"ok": True, "bytes": 10_000}])
        juntado = replica.carpeta_llegadas(self.ctx_alla.config) / SID / f"{SID}.jsonl"
        self.assertEqual(juntado.read_bytes(), b"x" * 10_000)
        m = self.Mensaje(b"no es una cabecera")
        asyncio.run(n._replica_escribir(m))
        self.assertFalse(m.respuestas[0]["ok"])

    def test_el_progreso_de_una_mudanza_de_aqui(self):
        from telar import mudanza

        n = self.nodo()
        mudanza.progreso(self.ctx_alla.config, "Faro", "copiar", por_mandar=10, mandados=5)
        m = self.Mensaje(json.dumps({"hilo": "Faro"}).encode())
        asyncio.run(n._mudanza_progreso(m))
        self.assertEqual((m.respuestas[0]["progreso"]["paso"], m.respuestas[0]["progreso"]["mandados"]), ("copiar", 5))


class LoJuntadoDeOtraVez(_DosMaquinas):
    def test_lo_juntado_que_no_sirve_no_traba_la_copia(self):
        # allá quedó algo juntado que no es un comienzo de la de aquí (de otra máquina, otra vez), y allá ya tienen la
        # conversación igual: no se manda nada, y lo juntado se va
        self.escribir(self.archivo, conversacion(80))
        self.escribir(self.alla(), self.archivo.read_bytes())
        juntado = replica.carpeta_llegadas(self.ctx_alla.config) / SID / f"{SID}.jsonl"
        self.escribir(juntado, b"otra cosa\n" * 10)
        r = self.mandar()
        self.assertEqual(r["mandados"], 0)
        self.assertEqual(self.pedidos.count(replica.VERBO_CERRAR), 1)
        self.assertFalse(juntado.exists())
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())

    def test_lo_juntado_que_no_sirve_se_reemplaza(self):
        self.escribir(self.archivo, conversacion(80))
        juntado = replica.carpeta_llegadas(self.ctx_alla.config) / SID / f"{SID}.jsonl"
        self.escribir(juntado, b"otra cosa\n" * 10)
        r = self.mandar()
        self.assertEqual(r["mandados"], self.archivo.stat().st_size)
        self.assertEqual(self.alla().read_bytes(), self.archivo.read_bytes())
