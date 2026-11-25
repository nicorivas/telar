"""Las ventanas que un módulo pide abrir en la página (`[ventanas]` de su modulo.toml, telar.servicios.ventanas): lo que
se lee del manifiesto, lo que se le pregunta al módulo (con el mundo puesto) y lo que llega a la página (lo de otro
mundo, nunca), lo que corre un botón (solo lo declarado), el «no molestar» y la API. Con un módulo de mentira que
escribe lo que le piden en su carpeta: nada sale de aquí."""

from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import modulos
from telar.servicios import ErrorDeServicio
from telar.servicios import ventanas as servicio

MANIFIESTO = """nombre = "avisos"
descripcion = "avisa"

[ordenes.esperan]
comando = ["bin/a", "esperan"]
consulta = true

[ordenes.hecho]
comando = ["bin/a", "hecho"]
consulta = true

[ordenes.suelta]
comando = ["bin/a", "suelta"]

[ventanas]
consulta = "esperan"
acciones = ["hecho"]
"""

# el módulo: `esperan` da las ventanas de ventanas.json (y anota con qué se le preguntó); `hecho`, lo que recibió
PROGRAMA = r"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
aqui = Path(os.environ["TELAR_MODULO"])
p = json.loads(sys.stdin.read() or "{}")
with open(aqui / "pedidos.log", "a") as f:
    f.write(json.dumps({"verbo": sys.argv[1], "p": p, "mundos": os.environ.get("TELAR_MUNDOS", "")}) + "\n")
if sys.argv[1] == "esperan":
    v = json.loads((aqui / "ventanas.json").read_text())
    # manda todas (aquí se prueba que telar descarta lo de otro mundo); cuenta las del mundo puesto
    n = sum(1 for x in v if not p.get("mundo") or x.get("mundo") in ("", p["mundo"]))
    print(json.dumps({"cuantas": n} if p.get("solo_cuantas") else {"ventanas": v, "cuantas": n}))
else:
    print(json.dumps({"hecho": p}))
"""


def ventana(id: str, mundo: str = "", **extra) -> dict:
    return {"id": id, "version": "1", "mundo": mundo, "titulo": f"chat {id}", "ayuda": "1 nuevo", "desde": f"2026-11-23T10:0{id[-1]}:00",
            "lineas": [{"de": "Ana", "ts": "2026-11-23T10:00:00", "texto": "hola", "nueva": True}],
            "responder": {"verbo": "hecho", "params": {"chat": id}, "placeholder": "responder…", "despues": {"verbo": "hecho", "params": {}}},
            "acciones": [{"texto": "15 min", "tecla": "1", "verbo": "hecho", "params": {"por": "15m"}},
                         {"texto": "abrir", "abrir": "pestana:avisos", "item": id, "en": "cabecera"},
                         {"texto": "mandar a…", "instruccion": {"verbo": "esperan", "params": {}}, "en": "cabecera"}],
            "escape": 0, **extra}


class Base(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name) / "avisos"
        (self.carpeta / "bin").mkdir(parents=True)
        a = self.carpeta / "bin" / "a"
        a.write_text(PROGRAMA)
        a.chmod(a.stat().st_mode | stat.S_IEXEC)
        self.estado = Path(self.tmp.name) / "estado"
        self.estado.mkdir()
        servicio._cache.clear()
        self.addCleanup(servicio._cache.clear)
        self.poner([])

    def poner(self, ventanas: list) -> None:
        (self.carpeta / "ventanas.json").write_text(json.dumps(ventanas, ensure_ascii=False))
        servicio._cache.clear()

    def ctx(self, manifiesto: str = MANIFIESTO, mundos=()):
        (self.carpeta / "modulo.toml").write_text(manifiesto)
        m = modulos.leer("avisos", self.carpeta)
        return SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None,
                                                      estado=self.estado, mundos=mundos))

    def pedidos(self) -> list[dict]:
        ruta = self.carpeta / "pedidos.log"
        return [json.loads(x) for x in ruta.read_text().splitlines()] if ruta.exists() else []


class ElManifiesto(Base):
    def test_se_lee_y_se_dice_lo_que_aporta(self):
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO)
        m = modulos.leer("avisos", self.carpeta)
        self.assertEqual(m.ventanas, {"consulta": "esperan", "acciones": ("hecho",)})
        self.assertIn("ventanas", m.aporta)
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO.split("[ventanas]")[0])
        self.assertEqual(modulos.leer("avisos", self.carpeta).ventanas, {})

    def test_solo_consultas_suyas_y_lo_que_entiende(self):
        for malo in ('consulta = "nada"', 'consulta = "suelta"', "consulta = 3", 'otra = "x"'):
            with self.subTest(malo=malo), self.assertRaises(modulos.ErrorDeModulo) as e:
                self.ctx(MANIFIESTO.replace('consulta = "esperan"', malo))
            self.assertIn("[ventanas]", str(e.exception))
        with self.assertRaises(modulos.ErrorDeModulo):
            self.ctx(MANIFIESTO.replace('acciones = ["hecho"]', 'acciones = ["suelta"]'))

    def test_el_modulo_sabe_los_mundos_de_telar(self):
        ctx = self.ctx(mundos=(SimpleNamespace(nombre="trabajo", etiquetas=("oficina",)), SimpleNamespace(nombre="personal", etiquetas=())))
        servicio.listar(ctx, "trabajo")
        self.assertEqual(json.loads(self.pedidos()[0]["mundos"]),
                         [{"nombre": "trabajo", "etiquetas": ["oficina"]}, {"nombre": "personal", "etiquetas": []}])


class LoQueEspera(Base):
    def test_lo_de_otro_mundo_no_llega_aunque_el_modulo_lo_mande(self):
        ctx = self.ctx()
        self.poner([ventana("v1", "trabajo"), ventana("v2", "personal"), ventana("v3", "")])
        r = servicio.listar(ctx, "trabajo")
        self.assertEqual([v["id"] for v in r["ventanas"]], ["v1", "v3"], "lo sin mundo sale en todos")
        self.assertNotIn("v2", json.dumps(r))
        self.assertEqual(self.pedidos()[-1]["p"], {"mundo": "trabajo"}, "al módulo se le dice el mundo puesto")
        self.assertEqual([v["id"] for v in servicio.listar(ctx, "")["ventanas"]], ["v1", "v2", "v3"], "con ambos, todas")
        self.assertEqual(r["silencio"], {"a_mano": False, "desde": ""})
        self.assertEqual((r["ventanas"][0]["modulo"], r["ventanas"][0]["escape"]), ("avisos", 0))

    def test_solo_cuantas(self):
        ctx = self.ctx()
        self.poner([ventana("v1"), ventana("v2")])
        r = servicio.listar(ctx, "trabajo", solo_cuantas=True)
        self.assertEqual((r["ventanas"], r["cuantas"]), ([], 2))
        self.assertEqual(self.pedidos()[-1]["p"], {"mundo": "trabajo", "solo_cuantas": True})

    def test_una_ventana_que_pide_lo_no_declarado_no_sale(self):
        ctx = self.ctx()
        mala = ventana("v2")
        mala["acciones"].append({"texto": "borrar todo", "verbo": "suelta"})
        sin_hacer = ventana("v3")
        sin_hacer["acciones"].append({"texto": "nada"})
        self.poner([ventana("v1"), mala, sin_hacer, {"titulo": "sin id"}])
        r = servicio.listar(ctx)
        self.assertEqual([v["id"] for v in r["ventanas"]], ["v1"])
        self.assertEqual(len(r["fallas"]), 3)
        self.assertIn("«suelta» no es de sus [ventanas] acciones", r["fallas"][0]["error"])

    def test_los_borradores_de_una_ventana(self):
        ctx = self.ctx()
        v = ventana("v1", borradores=[{"id": "b1", "de": "un agente", "texto": "Agente: voy", "motivo": "preguntó", "sale": "08:30",
                                       "editable": True, "aprobar": {"verbo": "hecho", "params": {"id": "b1"}, "despues": {"verbo": "hecho", "params": {}}},
                                       "descartar": {"verbo": "hecho", "params": {"id": "b1", "accion": "descartar"}}}])
        malo = ventana("v2", borradores=[{"id": "b2", "texto": "x", "aprobar": {"verbo": "suelta", "params": {}}}])
        self.poner([v, malo])
        r = servicio.listar(ctx)
        self.assertEqual([x["id"] for x in r["ventanas"]], ["v1"], "un borrador que corre algo no declarado: la ventana no sale")
        (b,) = r["ventanas"][0]["borradores"]
        self.assertEqual((b["id"], b["de"], b["sale"], b["editable"], b["aprobar"]["campo"]), ("b1", "un agente", "08:30", True, "texto"))
        self.assertEqual(b["descartar"], {"verbo": "hecho", "params": {"id": "b1", "accion": "descartar"}})

    def test_lo_largo_se_recorta_y_lo_raro_se_descarta(self):
        ctx = self.ctx()
        v = ventana("v1", titulo="x" * 500, icono="<script>", escape=9)
        v["lineas"] = [{"de": "Ana", "texto": "y" * 9000, "nueva": "sí"}] * 200
        self.poner([v])
        (r,) = servicio.listar(ctx)["ventanas"]
        self.assertEqual(len(r["titulo"]), servicio.TOPES["titulo"])
        self.assertEqual(len(r["lineas"]), servicio.TOPES["lineas"])
        self.assertEqual(len(r["lineas"][0]["texto"]), servicio.TOPES["texto"])
        self.assertIs(r["lineas"][0]["nueva"], False, "solo true es true")
        self.assertEqual((r["icono"], r["escape"]), ("", None))
        self.assertEqual(r["acciones"][1], {"texto": "abrir", "tecla": "", "en": "cabecera", "despues": None,
                                            "abrir": "pestana:avisos", "item": "v1"})

    def test_el_icono_de_cada_boton_y_cuantos_nuevos(self):
        ctx = self.ctx()
        v = ventana("v1", nuevos=3)
        v["acciones"][0].update(icono="aplazar", corto="15m")
        v["acciones"][1].update(icono="<b>", corto="x")
        v2 = ventana("v2", nuevos=True)
        v2["acciones"][0].update(icono="enviar", corto="y" * 50)
        self.poner([v, v2])
        a, b = servicio.listar(ctx)["ventanas"]
        self.assertEqual((a["acciones"][0]["icono"], a["acciones"][0]["corto"]), ("aplazar", "15m"))
        self.assertNotIn("icono", a["acciones"][1], "un nombre raro se descarta: va la palabra")
        self.assertNotIn("corto", a["acciones"][1], "sin ícono, el corto no va")
        self.assertEqual(a["nuevos"], 3)
        self.assertEqual(b["nuevos"], 0, "solo un entero")
        self.assertEqual(len(b["acciones"][0]["corto"]), 12)

    def test_lo_leido_vale_unos_segundos(self):
        ctx = self.ctx()
        self.poner([ventana("v1")])
        servicio._cache.clear()
        servicio.listar(ctx, "trabajo")
        servicio.listar(ctx, "trabajo")
        self.assertEqual(len(self.pedidos()), 1, "dos pestañas a la vez: una consulta")
        servicio.listar(ctx, "personal")
        self.assertEqual(len(self.pedidos()), 2, "otro mundo, otra")
        with mock.patch.object(servicio, "VIGENCIA", 0):
            servicio.listar(ctx, "trabajo")
        self.assertEqual(len(self.pedidos()), 3)

    def test_un_modulo_que_falla_no_tumba_nada(self):
        ctx = self.ctx()
        (self.carpeta / "ventanas.json").write_text("no es json")
        r = servicio.listar(ctx)
        self.assertEqual(r["ventanas"], [])
        self.assertEqual(r["fallas"][0]["modulo"], "avisos")


class LosBotones(Base):
    def test_corre_solo_lo_declarado_y_avisa_a_las_otras_pestanas(self):
        ctx = self.ctx()
        self.poner([ventana("v1")])
        servicio.listar(ctx)
        r = servicio.accion(ctx, "avisos", "hecho", {"por": "15m"})
        self.assertEqual(r, {"hecho": {"por": "15m"}})
        self.assertTrue((self.estado / "ventanas" / "cambio").exists(), "/eventos lo ve: las otras pestañas preguntan de nuevo")
        self.assertEqual(servicio._cache, {}, "lo leído ya no vale")
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.accion(ctx, "avisos", "suelta", {})
        self.assertEqual(e.exception.codigo, 403)
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.accion(ctx, "otro", "hecho", {})
        self.assertEqual(e.exception.codigo, 404)


class ElSilencio(Base):
    def test_no_molestar_a_mano_en_esta_maquina(self):
        ctx = self.ctx()
        self.assertFalse(servicio.silencio(ctx)["a_mano"])
        s = servicio.silenciar(ctx, True)
        self.assertTrue(s["a_mano"] and s["desde"])
        self.assertEqual(servicio.silenciar(ctx, True)["desde"], s["desde"], "ponerlo de nuevo no lo corre")
        self.assertTrue(servicio.listar(ctx)["silencio"]["a_mano"])
        # en silencio, ninguna página recibe el contenido: al módulo se le piden solo cuántas
        self.poner([ventana("v1")])
        r = servicio.listar(ctx, "trabajo")
        self.assertEqual((r["ventanas"], r["cuantas"]), ([], 1))
        self.assertEqual(self.pedidos()[-1]["p"], {"mundo": "trabajo", "solo_cuantas": True})
        self.assertFalse(servicio.silenciar(ctx, False)["a_mano"])
        self.assertEqual(len(servicio.listar(ctx, "trabajo")["ventanas"]), 1)
        self.assertFalse((self.estado / "ventanas" / "silencio.json").exists())


try:
    from fastapi.testclient import TestClient

    from telar import api
except ImportError:  # sin el extra «serve»
    api = None


@unittest.skipIf(api is None, "sin fastapi")
class LaApi(Base):
    def test_las_rutas(self):
        ctx = self.ctx()
        api.app.dependency_overrides[api.contexto] = lambda: ctx
        self.addCleanup(api.app.dependency_overrides.clear)
        self.poner([ventana("v1", "trabajo"), ventana("v2", "personal")])
        c = TestClient(api.app)
        j = c.get("/ventanas?mundo=trabajo").json()
        self.assertEqual([v["id"] for v in j["ventanas"]], ["v1"])
        self.assertEqual(c.get("/ventanas?mundo=trabajo&solo_cuantas=true").json()["cuantas"], 1)
        r = c.post("/ventanas/accion", json={"modulo": "avisos", "verbo": "hecho", "params": {"texto": "ñandú " * 900}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["hecho"]["texto"], "ñandú " * 900, "lo largo va en el cuerpo, no en la dirección")
        self.assertEqual(c.post("/ventanas/accion", json={"modulo": "avisos", "verbo": "suelta"}).status_code, 403)
        self.assertTrue(c.post("/ventanas/silencio", json={"si": True}).json()["a_mano"])
        self.assertTrue(c.get("/ventanas").json()["silencio"]["a_mano"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


OBJETOS = MANIFIESTO + """
[ordenes.chats]
comando = ["bin/a", "chats"]
consulta = true

[objetos.chat]
ver = "chats"
listar = "chats"
plural = "chats"
buscador = true
"""


class EnElBuscador(Base):
    """`[objetos.<tipo>] buscador`: los de un tipo de un módulo que también se buscan en ⌘K (los chats de whatsapp, con la
    acción de marcarlos de foco), y el mundo que dice el objeto (`campos.mundo`) cuando no vive en un archivo."""

    def test_se_declara_con_listar_y_lo_dice_la_configuracion(self):
        from telar.servicios import config as servicio_config

        ctx = self.ctx(OBJETOS)
        self.assertTrue(ctx.config.modulos[0].objetos["chat"]["buscador"])
        (m,) = servicio_config._modulos(SimpleNamespace(modulos=ctx.config.modulos, origen=None))
        self.assertEqual(m["buscables"], [{"tipo": "chat", "plural": "chats"}])
        with self.assertRaises(modulos.ErrorDeModulo):
            self.ctx(OBJETOS.replace('listar = "chats"\n', ""))
        with self.assertRaises(modulos.ErrorDeModulo):
            self.ctx(OBJETOS.replace("buscador = true", 'buscador = "si"'))
        self.assertNotIn("buscador", self.ctx(OBJETOS.replace("buscador = true\n", "")).config.modulos[0].objetos["chat"])

    def test_el_mundo_que_dice_el_objeto(self):
        from telar import objetos
        from telar.servicios import buscar

        ctx = self.ctx(OBJETOS, mundos=(SimpleNamespace(nombre="trabajo", etiquetas=(), rutas=(), areas=()),))
        lista = objetos.Objetos(tipo="chat", objetos=[
            objetos.Objeto(direccion="chat:a", tipo="chat", id="a", titulo="Ana", campos={"mundo": "trabajo"}),
            objetos.Objeto(direccion="chat:b", tipo="chat", id="b", titulo="Beto", campos={"mundo": "marte"}),
            objetos.Objeto(direccion="chat:c", tipo="chat", id="c", titulo="Carla")])
        tipo = SimpleNamespace(lista=True, listar=lambda c: lista)
        with mock.patch.object(objetos, "tipos", return_value={"chat": tipo}):
            r = {h.titulo: h.mundo for h, _ in buscar._objetos(ctx, "chat")}
        self.assertEqual(r, {"Ana": "trabajo", "Beto": "", "Carla": ""}, "solo un mundo declarado; si no, sin clasificar")


class UnoLento(Base):
    def test_no_se_le_espera_mas_de_la_cuenta(self):
        import time as reloj

        ctx = self.ctx()
        self.poner([ventana("v1")])
        lento = lambda *a, **k: reloj.sleep(2) or {"ventanas": [], "fallas": [], "cuantas": 0}  # noqa: E731
        with mock.patch.object(servicio, "ESPERA", 0.2), mock.patch.object(servicio, "_de_un_modulo", side_effect=lento):
            antes = reloj.monotonic()
            r = servicio.listar(ctx, "x")
        self.assertLess(reloj.monotonic() - antes, 1.5, "la respuesta no espera al lento")
        self.assertIn("no contestó", r["fallas"][0]["error"])
