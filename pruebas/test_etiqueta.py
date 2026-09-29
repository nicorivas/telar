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

    def test_si_el_titulo_ya_nombra_al_cliente_va_primero_y_no_se_repite(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("AquaChile — Campaña de Ideas", Cliente="AquaChile")),
                         "AquaChile · Campaña de Ideas")
        self.assertEqual(etiqueta(PLANTILLA, ficha("Reportabilidad con IA — Mar Azul", Cliente="Mar Azul")),
                         "Mar Azul · Reportabilidad con IA")

    def test_el_cliente_escrito_distinto_en_el_titulo_tampoco_se_repite(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Gobernanza de IA — Banco Faro", Cliente="Banco Faro Chile")),
                         "Banco Faro Chile · Gobernanza de IA")
        self.assertEqual(etiqueta(PLANTILLA, ficha("Gestión del conocimiento para Faro", Cliente="Faro")),
                         "Faro · Gestión del conocimiento")

    def test_el_cliente_con_una_aclaracion_entre_parentesis_tambien_se_quita(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Licitación Copilot — Faro (vía OTIC)", Cliente="Faro")),
                         "Faro · Licitación Copilot")

    def test_el_cliente_con_dos_puntos_al_comienzo_o_con_coma_al_final(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Faro: Jornadas de Finanzas", Cliente="Faro")),
                         "Faro · Jornadas de Finanzas")
        self.assertEqual(etiqueta(PLANTILLA, ficha("Coaching IA en Procesos, Faro", Cliente="Faro")),
                         "Faro · Coaching IA en Procesos")

    def test_un_titulo_que_es_solo_el_cliente_no_se_repite(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Faro", Cliente="Faro")), "Faro")

    def test_una_palabra_suelta_del_cliente_no_se_come_el_titulo(self):
        self.assertEqual(etiqueta(PLANTILLA, ficha("Faro de IA — Diagnóstico", Cliente="Faro")),
                         "Faro · Faro de IA — Diagnóstico")

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
