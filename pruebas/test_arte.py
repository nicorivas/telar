"""El arte de cada mundo (la tarjeta de la ventana de mundos, ⌘M): `[mundos.<n>] arte` se lee, se escribe desde
⚙ mundos como el color y el tema y llega a la página; y los artes de la raíz (`<raiz>/.telar/arte/<clave>.txt`, telar.arte)
se entregan con su texto tal cual por `GET /arte`, sin los que no sirven, que se dicen."""

from __future__ import annotations

import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import arte
from telar import config as cfg
from telar import mundos

ARCHIVO = """raiz = "{raiz}"
estado = "{estado}"

[mundos.trabajo]
rutas = ["empresa/"]
arte = "telar"

[mundos.personal]
rutas = ["casa/"]
"""


class Base(Prueba):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        self.ruta = self.raiz / "config.toml"
        self.ruta.write_text(ARCHIVO.format(raiz=self.raiz, estado=self.raiz / "estado"))

    def config(self) -> cfg.Config:
        return cfg.cargar(self.ruta)

    def leer(self) -> dict:
        return tomllib.loads(self.ruta.read_text())["mundos"]


class ElArteDeUnMundo(Base):
    def test_se_lee_y_llega_a_la_pagina(self):
        c = self.config()
        self.assertEqual([(m.nombre, m.arte) for m in c.mundos], [("trabajo", "telar"), ("personal", "")])
        self.assertEqual([m["arte"] for m in mundos.para_la_pagina(c)], ["telar", ""], "sin arte: \"\", el que le toca")

    def test_una_clave_que_no_sirve_es_un_error(self):
        for malo in ('"Telar Grande"', '"a/b"', "3", '"-x"'):
            self.ruta.write_text(ARCHIVO.format(raiz=self.raiz, estado=self.raiz / "estado").replace('"telar"', malo))
            with self.assertRaises(cfg.ErrorDeConfig, msg=malo) as e:
                self.config()
            self.assertIn("mundos.trabajo.arte", str(e.exception))

    def test_una_clave_que_no_hay_no_es_un_error(self):
        """Que exista lo sabe la página (tiene los de fábrica, y lee los de la raíz): uno que no hay lleva el que le toca."""
        self.ruta.write_text(ARCHIVO.format(raiz=self.raiz, estado=self.raiz / "estado").replace('"telar"', '"faro"'))
        self.assertEqual(self.config().mundos[0].arte, "faro")

    def test_se_escribe_desde_ajustes_como_el_tema(self):
        mundos.ajustar(self.ruta, "personal", {"arte": " cielo "})
        self.assertEqual(self.leer()["personal"]["arte"], "cielo")
        self.assertEqual(self.config().mundos[1].arte, "cielo")
        mundos.ajustar(self.ruta, "personal", {"arte": ""})
        self.assertNotIn("arte", self.leer()["personal"], "vacío quita la línea: el que le toca")
        with self.assertRaises(cfg.ErrorDeConfig):
            mundos.ajustar(self.ruta, "personal", {"arte": "Con Espacios"})
        self.assertNotIn("arte", self.leer()["personal"], "lo que no sirve no se escribe")
        self.assertIn("arte", mundos.CAMPOS)


class LosDeLaRaiz(Base):
    def escribir(self, nombre: str, texto: str | bytes) -> None:
        carpeta = self.raiz / ".telar" / "arte"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / nombre).write_bytes(texto if isinstance(texto, bytes) else texto.encode())

    def test_sin_carpeta_no_hay_ninguno(self):
        d = arte.de_la_raiz(self.config())
        self.assertEqual((d["artes"], d["errores"]), ([], {}))
        self.assertEqual(d["carpeta"], str(self.raiz / ".telar" / "arte"))

    def test_cada_uno_con_su_texto_tal_cual_y_los_que_no_sirven_dichos(self):
        self.escribir("faro.txt", "fps: 4\n---\n  /\\\n /  \\\n---\n  ||\n")
        self.escribir("ola.txt", "~~~\n")
        self.escribir("Mi Arte.txt", "x")
        self.escribir("grande.txt", "x" * (arte.TOPE + 1))
        self.escribir("roto.txt", b"\xff\xfe\xfa")
        self.escribir("notas.md", "no es un arte")
        d = arte.de_la_raiz(self.config())
        self.assertEqual([a["nombre"] for a in d["artes"]], ["faro", "ola"], "en orden, solo los .txt que sirven")
        self.assertEqual(d["artes"][0]["texto"], "fps: 4\n---\n  /\\\n /  \\\n---\n  ||\n", "el texto, tal cual: lo lee la página")
        self.assertEqual(set(d["errores"]), {"Mi Arte.txt", "grande", "roto"})
        self.assertIn("minúsculas", d["errores"]["Mi Arte.txt"])
        self.assertIn("64 KB", d["errores"]["grande"])
        self.assertIn("UTF-8", d["errores"]["roto"])

    def test_sin_raiz(self):
        self.assertEqual(arte.de_la_raiz(SimpleNamespace(raiz=None)), {"carpeta": "", "artes": [], "errores": {}})

    def test_get_arte(self):
        if not HAY_FASTAPI:
            self.skipTest("sin el extra «serve»")
        from fastapi.testclient import TestClient

        from telar import api

        self.escribir("faro.txt", "  /\\\n")
        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg.cargar(self.ruta))
        self.addCleanup(api.app.dependency_overrides.clear)
        c = TestClient(api.app)
        r = c.get("/arte")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["artes"], [{"nombre": "faro", "texto": "  /\\\n"}])
        r = c.patch("/mundos/personal", json={"valores": {"arte": "faro"}})
        self.assertEqual((r.status_code, r.json()["mundos"][1]["arte"]), (200, "faro"))
        self.assertEqual(c.patch("/mundos/personal", json={"valores": {"arte": "No"}}).status_code, 422)
