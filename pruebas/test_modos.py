"""Los modos de la página (telar.modos): su catálogo, los de fábrica, los de `[modos]`, y guardarlos o quitarlos."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config, modos

try:
    from fastapi.testclient import TestClient

    from telar import api

    HAY_SERVE = True
except ImportError:
    HAY_SERVE = False


class LosModos(Prueba):
    def test_de_fabrica_estandar_toma_la_terminal_de_su_tabla(self):
        c = config.desde_dict({"terminal": {"columnas": 120, "fondo": "#112233"}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertEqual(list(m), ["estandar", "foco"])
        self.assertEqual((m["estandar"]["valores"]["columnas"], m["estandar"]["valores"]["fondo"]), (120, "#112233"))
        self.assertEqual(m["estandar"]["valores"]["escribir"], "oculta")
        foco = m["foco"]["valores"]
        self.assertEqual((foco["barra"], foco["cabecera"], foco["escribir"], foco["posicion"], foco["fondo"]),
                         ("oculta", "oculta", "oculta", "centro", "ninguno"))
        self.assertFalse(m["foco"]["cambiado"])

    def test_los_de_la_configuracion_pisan_y_suman(self):
        c = config.desde_dict({"modos": {"foco": {"columnas": "todo"}, "lectura": {"nombre": "Lectura", "barra": "plegada"}}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertEqual(m["foco"]["valores"]["columnas"], 0)
        self.assertEqual(m["foco"]["valores"]["cabecera"], "oculta")  # lo demás de foco, de fábrica
        self.assertTrue(m["foco"]["cambiado"])
        self.assertEqual((m["lectura"]["nombre"], m["lectura"]["valores"]["barra"]), ("Lectura", "plegada"))
        self.assertEqual(m["lectura"]["valores"]["cabecera"], "visible")  # lo que no dice, de estándar

    def test_lo_que_no_sirve(self):
        for tabla in ({"X": {}}, {"a": {"barra": "rara"}}, {"a": {"inventado": 1}}, {"a": {"columnas": 5}},
                      {"a": {"fondo": "#1"}}, {"a": "no es tabla"}):
            with self.assertRaises(config.ErrorDeConfig, msg=str(tabla)):
                config.desde_dict({"modos": tabla})

    def test_guardar_y_borrar_en_el_archivo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "config.toml"
            ruta.write_text(f'raiz = "{d}"\n# mi config\n[terminal]\ncolumnas = 120\n')
            modos.guardar(ruta, "lectura", {"barra": "plegada", "pantalla_completa": True}, "lectura")
            modos.guardar(ruta, "lectura", {"barra": "oculta"})  # reemplaza la tabla entera
            c = config.cargar(ruta)
            self.assertEqual(c.modos["lectura"]["valores"], {"barra": "oculta"})
            self.assertIn("# mi config", ruta.read_text())
            self.assertTrue(modos.borrar(ruta, "lectura"))
            self.assertNotIn("modos.lectura", ruta.read_text())
            self.assertFalse(modos.borrar(ruta, "lectura"))
            self.assertEqual(config.cargar(ruta).terminal.columnas, 120)


class LaApi(Prueba):
    def setUp(self):
        super().setUp()
        if not HAY_SERVE:
            self.skipTest("sin el extra «serve»")
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self._tmp.name) / "config.toml"
        self.ruta.write_text(f'raiz = "{self._tmp.name}"\n')
        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=config.cargar(self.ruta))
        self.addCleanup(api.app.dependency_overrides.clear)

    def tearDown(self):
        self._tmp.cleanup()
        super().tearDown()

    def test_ver_guardar_y_borrar(self):
        c = TestClient(api.app)
        d = c.get("/modos").json()
        self.assertIn("barra", [a["clave"] for a in d["catalogo"]])
        self.assertEqual([m["clave"] for m in d["modos"]], ["estandar", "foco"])
        r = c.put("/modos/lectura", json={"valores": {"barra": "plegada", "fondo": "ninguno"}, "nombre": "lectura"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("lectura", [m["clave"] for m in r.json()["modos"]])
        self.assertEqual(c.put("/modos/lectura", json={"valores": {"barra": "rara"}}).status_code, 422)
        self.assertEqual(c.delete("/modos/lectura").status_code, 200)
        self.assertEqual(c.delete("/modos/lectura").status_code, 404)
