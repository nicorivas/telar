"""Cambiar una casilla en su documento: marcarla hecha y decir quién la hace, tocando solo esa línea."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import vinetas


class Lineas(unittest.TestCase):
    def test_marcar_hecha(self):
        self.assertEqual(vinetas.hecha("- [ ] Mandar la propuesta\n"), "- [x] Mandar la propuesta\n")
        self.assertEqual(vinetas.hecha("  * [>] En curso @owner(Ana)"), "  * [x] En curso @owner(Ana)")

    def test_el_responsable_reemplaza_lo_que_decia(self):
        con = vinetas.con_responsable
        self.assertEqual(con("- [ ] Agendar -> @para(Nico) @deadline(2026-09-05)\n", "Marcelo"),
                         "- [ ] Agendar @deadline(2026-09-05) @owner(Marcelo)\n")
        self.assertEqual(con("- [ ] @Francisco Martínez: el levantamiento", "Ana Pérez"),
                         "- [ ] el levantamiento @owner(Ana Pérez)")
        self.assertEqual(con("- [ ] Revisar @owner(Ana)", "none"), "- [ ] Revisar")


class EnElDocumento(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.doc = Path(self.tmp.name) / "README.md"
        self.doc.write_text("# Faro\n\n## Pendientes\n\n- [ ] **Mandar** la propuesta @deadline(2026-10-14)\n"
                            "- [ ] Revisar el NDA -> @para(Nico)\n- [x] Algo hecho\n\nFin.\n")

    def test_solo_cambia_la_linea_de_esa_casilla(self):
        antes = self.doc.read_text().splitlines()
        n = vinetas.cambiar(self.doc, "Revisar el NDA", vinetas.hecha)
        despues = self.doc.read_text().splitlines()
        self.assertEqual(n, 6)
        self.assertEqual(despues[5], "- [x] Revisar el NDA -> @para(Nico)")
        self.assertEqual([a for i, a in enumerate(antes) if i != 5], [d for i, d in enumerate(despues) if i != 5])

    def test_se_busca_por_el_texto_que_muestra_telar(self):
        # sin negritas ni marcas: el texto que se vio en el dashboard
        n = vinetas.cambiar(self.doc, "Mandar la propuesta", lambda l: vinetas.con_responsable(l, "Ana"))
        self.assertEqual(self.doc.read_text().splitlines()[n - 1],
                         "- [ ] **Mandar** la propuesta @deadline(2026-10-14) @owner(Ana)")

    def test_si_no_esta_o_ya_esta_hecha_no_se_escribe(self):
        antes = self.doc.read_text()
        for texto in ("No existe", "Algo hecho"):
            with self.assertRaises(vinetas.ErrorDeVineta):
                vinetas.cambiar(self.doc, texto, vinetas.hecha)
        self.assertEqual(self.doc.read_text(), antes)
        self.assertEqual(vinetas.linea(self.doc, "Algo hecho"), 7)

    def test_dos_iguales_no_se_adivina(self):
        self.doc.write_text("- [ ] Llamar\n- [ ] Llamar\n")
        with self.assertRaises(vinetas.ErrorDeVineta):
            vinetas.cambiar(self.doc, "Llamar", vinetas.hecha)
