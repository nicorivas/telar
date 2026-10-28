"""Cómo se ve la terminal de un hilo (`[terminal]`): su ancho, su posición y su fondo, que puede ser un módulo."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config, modulos

try:
    from fastapi.testclient import TestClient

    from telar import api

    HAY_SERVE = True
except ImportError:
    HAY_SERVE = False


class LaTabla(Prueba):
    def test_de_fabrica(self):
        t = config.desde_dict({}).terminal
        self.assertEqual((t.columnas, t.posicion, t.fondo), (130, "centro", "telar"))

    def test_valores_que_sirven_y_que_no(self):
        t = config.desde_dict({"terminal": {"columnas": "todo", "posicion": "Derecha", "fondo": "#1e1e2e"}}).terminal
        self.assertEqual((t.columnas, t.posicion, t.fondo), (0, "derecha", "#1e1e2e"))
        for tabla in ({"columnas": 10}, {"columnas": 999}, {"columnas": True}, {"posicion": "arriba"},
                      {"fondo": "#12"}, {"fondo": ""}, {"ancho": 100}):
            with self.assertRaises(config.ErrorDeConfig, msg=str(tabla)):
                config.desde_dict({"terminal": tabla})


class UnModuloComoFondo(Prueba):
    def test_su_fondo_es_una_pagina_de_su_carpeta(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d).resolve()  # en macOS, /var es /private/var
            (d / "modulo.toml").write_text('descripcion = "Estrellas."\n[fondo]\narchivo = "web/fondo.html"\nnombre = "estrellas"\n')
            m = modulos.leer("estrellas", d)
            self.assertEqual(m.fondo, {"archivo": str(d / "web" / "fondo.html"), "nombre": "estrellas"})
            self.assertIn("fondo de la terminal", m.aporta)
            (d / "modulo.toml").write_text('descripcion = "x"\n[fondo]\narchivo = "fondo.js"\n')
            with self.assertRaises(modulos.ErrorDeModulo):
                modulos.leer("estrellas", d)


class LaApi(Prueba):
    def setUp(self):
        super().setUp()
        if not HAY_SERVE:
            self.skipTest("sin el extra «serve»")
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        mod = self.dir / "estrellas"
        (mod / "web").mkdir(parents=True)
        (mod / "web" / "fondo.html").write_text("<canvas></canvas><script src='cielo.js'></script>")
        (mod / "web" / "cielo.js").write_text("// estrellas")
        (self.dir / "secreto.txt").write_text("no")
        self.modulo = SimpleNamespace(nombre="estrellas", descripcion="Estrellas.",
                                      fondo={"archivo": str(mod / "web" / "fondo.html"), "nombre": "estrellas"})
        self.cfg_ruta = self.dir / "config.toml"
        self.cfg_ruta.write_text(f'raiz = "{self.dir}"\n')
        self.poner()
        self.addCleanup(api.app.dependency_overrides.clear)

    def tearDown(self):
        self._tmp.cleanup()
        super().tearDown()

    def poner(self, **terminal):
        t = config.Terminal(**terminal)
        cfg = SimpleNamespace(modulos=(self.modulo,), terminal=t, origen=self.cfg_ruta)
        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg)

    def test_los_fondos_que_se_pueden_elegir(self):
        d = TestClient(api.app).get("/terminal/fondos").json()
        self.assertEqual([f["valor"] for f in d["fondos"]], ["telar", "ninguno", "estrellas"])
        self.assertEqual(d["actual"], {"columnas": 130, "posicion": "centro", "fondo": "telar"})

    def test_escribir_un_ajuste(self):
        c = TestClient(api.app)
        with mock.patch.object(config, "desde_dict", wraps=config.desde_dict):
            r = c.put("/config/terminal/columnas", json={"valor": "todo"})
        self.assertEqual((r.status_code, r.json()["valor"]), (200, 0))
        self.assertIn("columnas = 0", self.cfg_ruta.read_text())
        self.assertEqual(c.put("/config/terminal/fondo", json={"valor": "estrellas"}).status_code, 200)
        self.assertEqual(c.put("/config/terminal/fondo", json={"valor": "nadie"}).status_code, 422)
        self.assertEqual(c.put("/config/terminal/posicion", json={"valor": "arriba"}).status_code, 422)
        self.assertEqual(c.put("/config/terminal/fondo", json={"valor": "imagen:/no/existe.png"}).status_code, 422)

    def test_el_modulo_de_fondo_sirve_su_pagina_y_lo_suyo_nada_mas(self):
        self.poner(fondo="estrellas")
        c = TestClient(api.app)
        r = c.get("/terminal/fondo/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("canvas", r.text)
        self.assertIn("sandbox", r.headers["content-security-policy"])
        self.assertEqual(c.get("/terminal/fondo/cielo.js").status_code, 200)
        self.assertEqual(c.get("/terminal/fondo/../../secreto.txt").status_code, 404)
        self.poner(fondo="telar")
        self.assertEqual(c.get("/terminal/fondo/").status_code, 404)

    def test_una_imagen_de_la_maquina(self):
        img = self.dir / "nebulosa.png"
        img.write_bytes(b"\x89PNG\r\n")
        self.poner(fondo=f"imagen:{img}")
        r = TestClient(api.app).get("/terminal/imagen")
        self.assertEqual((r.status_code, r.headers["content-type"]), (200, "image/png"))
        self.poner(fondo="imagen:https://example.org/a.png")
        self.assertEqual(TestClient(api.app).get("/terminal/imagen").status_code, 404)
