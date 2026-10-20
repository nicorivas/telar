"""`/config` dice dónde vive la bandeja del equipo: la página en el navegador lo lee como su ajuste equipoRemoto."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.servicios import config as servicio


class LaBandejaDelEquipo(Prueba):
    def _con(self, texto: str) -> str:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        ruta = Path(d.name) / "config.toml"
        ruta.write_text(texto, encoding="utf-8")
        return servicio._equipo(SimpleNamespace(origen=ruta))

    def test_aqui_otra_maquina_o_nada(self):
        self.assertEqual(self._con('[equipo]\ntareas = "~/tareas"\n'), "aqui")
        self.assertEqual(self._con('[equipo]\ntareas = "~/tareas"\nen = "telar"\n'), "telar")
        self.assertEqual(self._con('[telar]\nraiz = "~"\n'), "")
        self.assertEqual(self._con('[equipo]\netiqueta = "equipo"\n'), "")
        self.assertEqual(servicio._equipo(SimpleNamespace(origen=None)), "")
