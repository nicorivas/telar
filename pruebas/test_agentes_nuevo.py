"""`telar agentes nuevo`: la carpeta de un agente, y `[agentes] carpeta` si faltaba (telar.agentes.crear)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import agentes, config


class AgenteNuevo(Prueba):
    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()
        super().tearDown()

    def _cfg(self, extra: str = "") -> Path:
        ruta = self.dir / "config.toml"
        ruta.write_text(f'raiz = "{self.dir}"\n{extra}', encoding="utf-8")
        return ruta

    def test_crea_la_carpeta_y_configura(self):
        ruta = self._cfg()
        r = agentes.crear(config.cargar(ruta), ruta, "Faro Ñandú", para="Mira los proyectos.", icono="☼")
        self.assertEqual(r["clave"], "faro-nandu")
        self.assertTrue(r["configurado"])
        d = self.dir / "agentes" / "faro-nandu"
        for f in ("CLAUDE.md", "README.md", "agente.toml", "bitacora.md", "memoria/MEMORY.md"):
            self.assertTrue((d / f).is_file(), f)
        self.assertIn('carpeta = "agentes"', ruta.read_text())
        c = config.cargar(ruta)
        [a] = agentes.descubrir(c)
        self.assertEqual((a.nombre, a.para, a.icono), ("Faro Ñandú", "Mira los proyectos.", "☼"))
        with self.assertRaisesRegex(ValueError, "ya hay"):
            agentes.crear(c, ruta, "faro ñandú")

    def test_respeta_la_carpeta_configurada(self):
        ruta = self._cfg('[agentes]\ncarpeta = "gente"\n')
        r = agentes.crear(config.cargar(ruta), ruta, "Vigía")
        self.assertFalse(r["configurado"])
        self.assertEqual(Path(r["carpeta"]), self.dir / "gente" / "vigia")

    def test_tabla_agentes_sin_carpeta(self):
        ruta = self._cfg('[agentes]\nabrir = "tab"\n\n[dashboard]\norden = ["ahora"]\n')
        agentes.crear(config.cargar(ruta), ruta, "Vigía")
        self.assertEqual(config.cargar(ruta).agentes_carpeta, "agentes")

    def test_repo_de_equipo_va_al_home(self):
        repo = self.dir / "repo"
        (repo / ".telar").mkdir(parents=True)
        (repo / ".telar" / "equipo.yaml").write_text("nombre: x\n")
        ruta = self.dir / "config.toml"
        ruta.write_text(f'raiz = "{repo}"\n', encoding="utf-8")
        with mock.patch.object(Path, "home", lambda: self.dir / "casa"):
            r = agentes.crear(config.cargar(ruta), ruta, "Vigía")
        self.assertEqual(Path(r["carpeta"]), self.dir / "casa" / "agentes" / "vigia")
        self.assertIn('carpeta = "~/agentes"', ruta.read_text())

    def test_nombres_que_no_sirven(self):
        ruta = self._cfg()
        for nombre in ("", "   ", "!!!", "ab" * 40):
            with self.subTest(nombre=nombre), self.assertRaises(ValueError):
                agentes.crear(config.cargar(ruta), ruta, nombre)
