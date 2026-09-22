"""El nombre en pantalla de una unidad: `etiqueta` en el perfil, armada con la ficha."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.lectura import etiqueta

PLANTILLA = "{campo:Cliente} · {titulo}"


def ficha(titulo="", **campos):
    return SimpleNamespace(titulo=titulo, secciones={"campos": campos})


class LaEtiqueta(Prueba):
    def test_cliente_y_titulo(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Adopción IA", Cliente="Grupo Anasac")),
                         "Grupo Anasac · Adopción IA")

    def test_sin_parentesis_ni_lo_que_sigue_a_una_raya_o_coma(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Reportes", Cliente="Aguas Pacífico (agua desalada; Quintero)")),
                         "Aguas Pacífico · Reportes")
        self.assertEqual(etiqueta(PLANTILLA, ficha("Ideas", Cliente="Antofagasta Minerals — grupo minero")),
                         "Antofagasta Minerals · Ideas")

    def test_si_el_titulo_ya_nombra_al_cliente_no_se_repite(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("AquaChile — Campaña de Ideas", Cliente="AquaChile")),
                         "AquaChile — Campaña de Ideas")

    def test_sin_cliente_queda_el_titulo_sin_separador_colgando(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Club de IA")), "Club de IA")

    def test_sin_plantilla_el_titulo(self):
        self.assertEqual(etiqueta("", ficha("Faro")), "Faro")

    def test_sin_nada_vacia(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha()), "")
        self.assertEqual(etiqueta(PLANTILLA, None), "")


class ElPerfilLaDeclara(Prueba):
    def test_se_lee_del_arquetipo(self):
        from telar.perfil import desde_dict
        per = desde_dict({"version": 1, "arquetipos": {"proyecto": {"ruta": "p/*/", "etiqueta": PLANTILLA}}})
        self.assertEqual(per.arquetipos[0].etiqueta, PLANTILLA)


if __name__ == "__main__":
    unittest.main()
