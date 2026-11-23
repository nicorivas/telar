"""Los colores principales de un tema y los temas propios (telar.temas, `[temas.<tema>]`, `GET`/`PUT`/`PATCH`/`DELETE
/temas`): se leen con la configuración (un tema, un color o una base que no sirven es un error), `telar config --json`
los dice, y ⚙ temas los cambia línea por línea, sin tocar lo demás del archivo; vacío vuelve al de fábrica, y una tabla
de uno de fábrica que queda sin nada se quita. Un tema propio parte de uno de fábrica (`base`), se elige en un modo o un
mundo como los otros, y mientras uno lo tenga puesto no se borra. Un color que se lee mal se escribe igual: la página lo
avisa (pagina/pruebas/temas.mjs lo prueba)."""

from __future__ import annotations

import re
import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import temas
from telar.modos import TEMAS

ARCHIVO = """# mi configuración
raiz = "{raiz}"
estado = "{estado}"

# de noche, el acento en salvia
[temas.brasa]
azul = "#7DAE9A"   # el de antes no combinaba
violeta = "#c9a"

[hilos]
directorios = ["empresa"]
"""


class Base(Prueba):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        raiz = Path(self._tmp.name)
        self.ruta = raiz / "config.toml"
        self.ruta.write_text(ARCHIVO.format(raiz=raiz, estado=raiz / "estado"))

    def leer(self) -> dict:
        return tomllib.loads(self.ruta.read_text()).get("temas", {})

    def config(self) -> cfg.Config:
        return cfg.cargar(self.ruta)


class Leerlos(Base):
    def test_cada_tinta_normalizada(self):
        self.assertEqual(self.config().temas, {"brasa": {"azul": "#7dae9a", "violeta": "#cc99aa"}})

    def test_lo_que_no_sirve_es_un_error(self):
        for malo, dice in (({"neon": {"azul": "#fff"}}, "temas.neon"),
                           ({"brasa": {"naranjo": "#fff"}}, "temas.brasa.naranjo: no existe"),
                           ({"brasa": {"azul": "azul"}}, "temas.brasa.azul: un color"),
                           ({"brasa": {"azul": "#12345"}}, "temas.brasa.azul: un color"),
                           ({"brasa": "#fff"}, "temas.brasa")):
            with self.subTest(malo=malo), self.assertRaises(cfg.ErrorDeConfig) as e:
                cfg.desde_dict({"temas": malo})
            self.assertIn(dice, str(e.exception))

    def test_sin_temas_nada(self):
        self.assertEqual(cfg.desde_dict({}).temas, {})
        self.assertEqual(temas.para_la_pagina(cfg.desde_dict({})), {})

    def test_lo_que_ve_la_configuracion_cada_tema_en_su_orden(self):
        d = temas.para_la_configuracion(self.config())
        self.assertEqual([t["clave"] for t in d["temas"]], list(TEMAS))
        self.assertEqual(next(t for t in d["temas"] if t["clave"] == "brasa")["propios"]["azul"], "#7dae9a")
        self.assertEqual(next(t for t in d["temas"] if t["clave"] == "telar")["propios"], {})
        self.assertEqual(d["tintas"], list(temas.TINTAS))
        self.assertEqual(d["fondos"], ["bg", "bg-barra", "linea", "sel"])
        self.assertTrue(all(t["de_fabrica"] and t["base"] == "" for t in d["temas"]))

    def test_los_fondos_tambien(self):
        c = cfg.desde_dict({"temas": {"latte": {"bg": "#FFF", "bg-barra": "#eeeeee", "linea": "#ccc", "sel": "#ddd"}}})
        self.assertEqual(c.temas["latte"], {"bg": "#ffffff", "bg-barra": "#eeeeee", "linea": "#cccccc", "sel": "#dddddd"})

    def test_uno_propio_parte_de_uno_de_fabrica(self):
        c = cfg.desde_dict({"temas": {"noche-azul": {"base": "brasa", "bg": "#141820"}}})
        self.assertEqual(c.temas["noche-azul"], {"base": "brasa", "bg": "#141820"})
        self.assertEqual(temas.propios(c), {"noche-azul": "brasa"})
        self.assertEqual(temas.que_hay(c), (*TEMAS, "noche-azul"))
        d = temas.para_la_configuracion(c)
        nuevo = d["temas"][-1]
        self.assertEqual(nuevo, {"clave": "noche-azul", "propios": {"bg": "#141820"}, "base": "brasa", "de_fabrica": False,
                                 "vive": "maquina", "en_raiz": [], "en_maquina": ["bg"]})
        # sin colores también es uno (es su base, con otro nombre), y `telar config --json` lo dice con su base
        c = cfg.desde_dict({"temas": {"copia": {"base": "latte"}}})
        self.assertEqual(temas.para_la_pagina(c), {"copia": {"base": "latte"}})

    def test_lo_que_no_sirve_de_uno_propio(self):
        for malo, dice in (({"noche": {"bg": "#000"}}, "temas.noche.base"),
                           ({"noche": {"base": "noche-azul"}}, "temas.noche.base"),
                           ({"Noche": {"base": "brasa"}}, "temas.Noche: «Noche»: un tema propio se llama en minúsculas"),
                           ({"brasa": {"base": "latte"}}, "temas.brasa.base: solo un tema propio")):
            with self.subTest(malo=malo), self.assertRaises(cfg.ErrorDeConfig) as e:
                cfg.desde_dict({"temas": malo})
            self.assertIn(dice, str(e.exception))

    def test_un_modo_y_un_mundo_lo_pueden_llevar(self):
        datos = {"temas": {"noche-azul": {"base": "brasa"}}, "modos": {"lectura": {"tema": "noche-azul"}},
                 "mundos": {"personal": {"tema": "noche-azul"}}}
        c = cfg.desde_dict(datos)
        self.assertEqual(c.mundos[0].tema, "noche-azul")
        self.assertEqual(c.modos["lectura"]["valores"]["tema"], "noche-azul")
        sin = {k: v for k, v in datos.items() if k != "temas"}
        for quita in ("modos", "mundos"):
            with self.subTest(quita=quita), self.assertRaises(cfg.ErrorDeConfig) as e:
                cfg.desde_dict({k: v for k, v in sin.items() if k != quita})
            self.assertIn("noche-azul", str(e.exception))

    def test_las_tintas_son_las_de_la_pagina(self):
        """Las mismas, en el mismo orden, que EDITABLES de componentes/temas.ts, y cada una un primitivo de los temas."""
        raiz = Path(__file__).resolve().parents[1] / "pagina"
        ts = (raiz / "src" / "componentes" / "temas.ts").read_text(encoding="utf-8")
        bloque = re.search(r"export const EDITABLES[^=]*=\s*\[(.*?)\n\];", ts, re.S)
        self.assertIsNotNone(bloque, "EDITABLES en componentes/temas.ts")
        self.assertEqual(tuple(re.findall(r"tinta: '([\w-]+)'", bloque.group(1))), temas.TINTAS)
        tokens = (raiz / "media" / "css" / "tokens.css").read_text(encoding="utf-8")
        for t in temas.TINTAS:
            self.assertRegex(tokens, rf"--{t}:\s*#", t)
        # los fondos y las líneas: los mismos de FONDOS, cada uno un token de los temas (el fondo y las barras, primitivos;
        # las líneas y la selección, derivados del texto)
        bloque = re.search(r"export const FONDOS[^=]*=\s*\[(.*?)\n\];", ts, re.S)
        self.assertIsNotNone(bloque, "FONDOS en componentes/temas.ts")
        self.assertEqual(tuple(re.findall(r"tinta: '([\w-]+)'", bloque.group(1))), temas.FONDOS)
        for t in temas.FONDOS:
            self.assertRegex(tokens, rf"--{t}:", t)


class TelarConfig(Base):
    def test_config_json_lo_dice(self):
        from telar.servicios import config as servicio

        r = servicio.resuelta(SimpleNamespace(config=self.config()))
        self.assertEqual(r.model_dump()["temas"], {"brasa": {"azul": "#7dae9a", "violeta": "#cc99aa"}})


class Cambiarlos(Base):
    def test_ajustar_escribe_solo_esas_lineas(self):
        temas.ajustar(self.ruta, "brasa", {"amarillo": "#E5B96A"})
        self.assertEqual(self.leer()["brasa"], {"azul": "#7DAE9A", "violeta": "#c9a", "amarillo": "#e5b96a"})
        texto = self.ruta.read_text()
        self.assertIn("# el de antes no combinaba", texto, "lo demás del archivo queda como estaba")
        self.assertIn("# de noche, el acento en salvia", texto)

    def test_otro_tema_su_tabla(self):
        temas.ajustar(self.ruta, "rescoldo", {"fg": "#ddd"})
        self.assertEqual(self.config().temas["rescoldo"], {"fg": "#dddddd"})
        self.assertEqual(self.config().temas["brasa"]["azul"], "#7dae9a")

    def test_vacio_vuelve_al_de_fabrica_y_la_tabla_vacia_se_va(self):
        temas.ajustar(self.ruta, "brasa", {"azul": None})
        self.assertEqual(self.leer()["brasa"], {"violeta": "#c9a"})
        temas.ajustar(self.ruta, "brasa", {"violeta": ""})
        self.assertNotIn("brasa", self.leer())
        self.assertNotIn("[temas.brasa]", self.ruta.read_text())
        self.assertIn("[hilos]", self.ruta.read_text())

    def test_lo_que_no_sirve_no_escribe_nada(self):
        antes = self.ruta.read_text()
        with self.assertRaises(KeyError):
            temas.ajustar(self.ruta, "neon", {"azul": "#fff"})
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.ajustar(self.ruta, "brasa", {"amarillo": "#fff", "azul": "verde"})
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.ajustar(self.ruta, "brasa", {"naranjo": "#fff"})
        self.assertEqual(self.ruta.read_text(), antes)

    def test_un_color_que_se_lee_mal_se_escribe_igual(self):
        temas.ajustar(self.ruta, "brasa", {"azul": "#201810"})   # casi el fondo: la página lo avisa
        self.assertEqual(self.config().temas["brasa"]["azul"], "#201810")

    def test_los_fondos_linea_por_linea(self):
        temas.ajustar(self.ruta, "brasa", {"bg": "#1C1510", "bg-barra": "#151009"})
        self.assertEqual(self.leer()["brasa"]["bg-barra"], "#151009")
        self.assertIn('bg-barra = "#151009"', self.ruta.read_text())
        temas.ajustar(self.ruta, "brasa", {"bg": None})
        self.assertNotIn("bg", self.leer()["brasa"])

    def test_borrar(self):
        self.assertTrue(temas.borrar(self.ruta, "brasa"))
        self.assertEqual(self.config().temas, {})
        self.assertIn("[hilos]", self.ruta.read_text())
        self.assertNotIn("de noche, el acento", self.ruta.read_text(), "su comentario se va con ella")
        self.assertFalse(temas.borrar(self.ruta, "brasa"))


class LosPropios(Base):
    def test_crear_desde_uno_de_fabrica(self):
        self.assertEqual(temas.crear(self.ruta, "noche-azul", "rescoldo"), {"base": "rescoldo"})
        self.assertEqual(self.config().temas["noche-azul"], {"base": "rescoldo"})
        self.assertIn("[temas.noche-azul]", self.ruta.read_text())
        self.assertIn("# el de antes no combinaba", self.ruta.read_text(), "lo demás del archivo queda como estaba")

    def test_crear_desde_uno_propio_lo_copia(self):
        temas.crear(self.ruta, "uno", "brasa")
        temas.ajustar(self.ruta, "uno", {"bg": "#101010", "azul": "#88aa99"})
        temas.crear(self.ruta, "dos", "uno")
        self.assertEqual(self.config().temas["dos"], {"base": "brasa", "bg": "#101010", "azul": "#88aa99"})

    def test_el_nombre_no_pisa_nada(self):
        antes = self.ruta.read_text()
        for malo in ("brasa", "telar", "Noche", "noche azul", "1noche", "", "a" * 25, "noche/x"):
            with self.subTest(malo=malo), self.assertRaises(cfg.ErrorDeConfig):
                temas.crear(self.ruta, malo, "brasa")
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.crear(self.ruta, "noche", "neon")
        self.assertEqual(self.ruta.read_text(), antes, "nada se escribe")
        temas.crear(self.ruta, "noche", "brasa")
        with self.assertRaises(FileExistsError):
            temas.crear(self.ruta, "noche", "latte")

    def test_modificar_y_volver_a_su_base(self):
        temas.crear(self.ruta, "noche", "brasa")
        temas.ajustar(self.ruta, "noche", {"bg": "#101418", "fg": "#e0e0e0"})
        self.assertEqual(self.config().temas["noche"], {"base": "brasa", "bg": "#101418", "fg": "#e0e0e0"})
        # todo de vuelta al de su base: queda el tema, con su base y nada más
        temas.ajustar(self.ruta, "noche", {"bg": None, "fg": None})
        self.assertEqual(self.config().temas["noche"], {"base": "brasa"})
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.ajustar(self.ruta, "noche", {"base": "latte"})

    def test_borrar_uno_propio(self):
        temas.crear(self.ruta, "noche", "brasa")
        self.assertTrue(temas.borrar(self.ruta, "noche"))
        self.assertNotIn("noche", self.config().temas)
        with self.assertRaises(KeyError):
            temas.ajustar(self.ruta, "noche", {"bg": "#000"})

    def test_en_uso_no_se_borra(self):
        temas.crear(self.ruta, "noche", "brasa")
        cfg.escribir_clave("mundos.personal", "tema", "noche", self.ruta)
        with self.assertRaises(temas.EnUso) as e:
            temas.borrar(self.ruta, "noche")
        self.assertIn("el mundo «personal»", str(e.exception))
        self.assertIn("noche", self.config().temas)
        cfg.escribir_clave("mundos.personal", "tema", None, self.ruta)
        self.assertTrue(temas.borrar(self.ruta, "noche"))

    def test_un_mundo_lo_elige_por_su_ajuste(self):
        from telar import mundos

        cfg.escribir_clave("mundos.personal", "rutas", ["casa/"], self.ruta)
        with self.assertRaises(cfg.ErrorDeConfig):
            mundos.ajustar(self.ruta, "personal", {"tema": "noche"})
        temas.crear(self.ruta, "noche", "brasa")
        mundos.ajustar(self.ruta, "personal", {"tema": "noche"})
        self.assertEqual(self.config().mundos[0].tema, "noche")
        self.assertIn("noche", mundos.para_la_configuracion(self.config(), etiquetas={})["temas"])


class LaApi(Base):
    def setUp(self):
        super().setUp()
        if not HAY_FASTAPI:
            self.skipTest("sin el extra «serve»")
        from fastapi.testclient import TestClient

        from telar import api

        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg.cargar(self.ruta))
        self.addCleanup(api.app.dependency_overrides.clear)
        self.c = TestClient(api.app)

    def propios(self, d: dict, tema: str) -> dict:
        return next(t for t in d["temas"] if t["clave"] == tema)["propios"]

    def test_ver(self):
        d = self.c.get("/temas").json()
        self.assertEqual(self.propios(d, "brasa"), {"azul": "#7dae9a", "violeta": "#cc99aa"})
        self.assertIn("fg", d["tintas"])

    def test_patch_escribe_solo_lo_que_se_le_da(self):
        r = self.c.patch("/temas/brasa", json={"valores": {"violeta": "#D19FB6", "azul": None}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(self.propios(r.json(), "brasa"), {"violeta": "#d19fb6"}, "devuelve lo que quedó escrito")
        self.assertEqual(self.c.patch("/temas/neon", json={"valores": {"azul": "#fff"}}).status_code, 404)
        r = self.c.patch("/temas/brasa", json={"valores": {"azul": "salvia"}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("temas.brasa.azul", r.json()["detail"])
        self.assertEqual(self.c.patch("/temas/brasa", json={"valores": {"naranjo": "#fff"}}).status_code, 422)
        r = self.c.patch("/temas/latte", json={"valores": {"azul": "#3366aa"}})
        self.assertEqual(self.propios(r.json(), "latte"), {"azul": "#3366aa"})

    def test_volver_todo_al_de_fabrica(self):
        r = self.c.delete("/temas/brasa")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.propios(r.json(), "brasa"), {})
        self.assertEqual(self.c.delete("/temas/brasa").status_code, 404)

    def test_crear_modificar_volver_y_borrar_uno_propio(self):
        r = self.c.put("/temas/noche-azul", json={"base": "brasa"})
        self.assertEqual(r.status_code, 200, r.text)
        nuevo = next(t for t in r.json()["temas"] if t["clave"] == "noche-azul")
        self.assertEqual((nuevo["base"], nuevo["de_fabrica"], nuevo["propios"]), ("brasa", False, {}))
        self.assertEqual(self.c.put("/temas/noche-azul", json={"base": "latte"}).status_code, 409)
        # sus colores, como los de uno de fábrica
        r = self.c.patch("/temas/noche-azul", json={"valores": {"bg": "#141820", "linea": "#2A3040", "azul": "#88AACC"}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.propios(r.json(), "noche-azul"), {"bg": "#141820", "linea": "#2a3040", "azul": "#88aacc"})
        # todo a su base: PATCH con null; el tema sigue
        r = self.c.patch("/temas/noche-azul", json={"valores": {"bg": None, "linea": None, "azul": None}})
        self.assertEqual(self.propios(r.json(), "noche-azul"), {})
        self.assertIn("noche-azul", [t["clave"] for t in r.json()["temas"]])
        # un mundo lo tiene puesto: no se borra (409, con quién); sin él, sí
        cfg.escribir_clave("mundos.personal", "tema", "noche-azul", self.ruta)
        r = self.c.delete("/temas/noche-azul")
        self.assertEqual(r.status_code, 409, r.text)
        self.assertIn("personal", r.json()["detail"])
        cfg.escribir_clave("mundos.personal", "tema", None, self.ruta)
        r = self.c.delete("/temas/noche-azul")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("noche-azul", [t["clave"] for t in r.json()["temas"]])
        self.assertEqual(self.c.patch("/temas/noche-azul", json={"valores": {"bg": "#000"}}).status_code, 404)

    def test_nombre_invalido_422(self):
        antes = self.ruta.read_text()
        for malo in ("brasa", "Noche", "noche%20azul", "ñandú"):
            with self.subTest(malo=malo):
                r = self.c.put(f"/temas/{malo}", json={"base": "brasa"})
                self.assertEqual(r.status_code, 422, r.text)
        r = self.c.put("/temas/brasa", json={"base": "latte"})
        self.assertIn("de fábrica", r.json()["detail"])
        self.assertEqual(self.c.put("/temas/noche", json={"base": "neon"}).status_code, 422)
        self.assertEqual(self.ruta.read_text(), antes)

    def test_los_modos_ofrecen_los_propios(self):
        self.c.put("/temas/noche", json={"base": "brasa"})
        from telar import api

        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg.cargar(self.ruta))
        tema = next(a for a in self.c.get("/modos").json()["catalogo"] if a["clave"] == "tema")
        self.assertEqual(tema["opciones"][-1], "noche")
