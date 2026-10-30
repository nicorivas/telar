"""Dos tareas que son la misma: una se une a la otra (telar.servicios.tipos.unir)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)


class Unir(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text(f'estado = "{Path(self.tmp.name) / "estado"}"\n[tipos.tarea]\ncarpeta = "{Path(self.tmp.name) / "tareas"}"\n')
        os.environ["TELAR_CONFIG"] = str(ruta)
        from telar.cli import Contexto
        from telar.config import cargar as cargar_config
        from telar.servicios import tipos as st

        self.st = st
        self.ctx = Contexto(config=cargar_config(None))
        self.a = st.crear(self.ctx, {"titulo": "Mathiesen: actualizar la propuesta", "contexto": "Lo pidió Félix."})
        self.b = st.crear(self.ctx, {"titulo": "Mathiesen: armar la propuesta", "contexto": "Dueño: Nico.",
                                     "proyecto": "proyectos/mathiesen", "tamano": "larga"})

    def test_una_se_une_a_la_otra(self):
        from telar import objetos

        h = objetos.hacer(self.ctx, f"tarea:{self.b.id}", "unir", {"con": self.a.id})
        a = self.st.obtener(self.ctx, self.a.id)
        self.assertEqual(h.objeto.id, self.a.id)
        self.assertIn(f"De {self.b.id}", a.contexto)
        self.assertIn("Dueño: Nico.", a.contexto)
        self.assertTrue(a.contexto.startswith("Lo pidió Félix."))
        self.assertEqual((a.proyecto, a.tamano), ("proyectos/mathiesen", "larga"))
        self.assertIn(f"`absorbe` [{self.b.id}]", a.conexiones[0])
        b = self.st.obtener(self.ctx, self.b.id)
        self.assertEqual(b.estado, "descartada")
        self.assertIn(f"unida a {self.a.id}", b.historia[-1].texto)

    def test_lo_que_no_se_une(self):
        from telar.servicios import ErrorDeServicio

        for con in ("", self.b.id):
            with self.assertRaises(ErrorDeServicio):
                self.st.unir(self.ctx, con, self.b.id)
        self.st.aplicar(self.ctx, self.a.id, "completar", {})
        with self.assertRaises(ErrorDeServicio):
            self.st.unir(self.ctx, self.a.id, self.b.id)
