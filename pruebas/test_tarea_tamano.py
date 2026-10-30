"""El tamaño de una tarea: rápida (se despacha entre otras cosas) o larga (necesita un bloque de concentración)."""

from __future__ import annotations

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.tipos import tarea

TEXTO = """---
titulo: Escribir el informe
estado: activa
prioridad: 2
vence: 2026-11-03
area: brinca
creada: 2026-10-29
---
## Historia
- 2026-10-29 [creada] a mano
"""


class ElTamano(Prueba):
    def test_sin_decir_queda_vacio_y_se_lee_igual(self):
        t = tarea.ARCHIVO.leer(TEXTO, "T1")
        self.assertEqual(t.tamano, "")
        self.assertEqual(tarea.ARCHIVO.escribir(TEXTO, t, t), TEXTO)

    def test_se_lee_con_tilde_o_sin_ella_y_con_sinonimos(self):
        for linea, esperado in (("tamaño: rápida", "rapida"), ("tamano: larga", "larga"), ("tamaño: Corta", "rapida"),
                                ("tamaño: grande", "larga")):
            t = tarea.ARCHIVO.leer(TEXTO.replace("area: brinca", f"area: brinca\n{linea}"), "T1")
            self.assertEqual(t.tamano, esperado, linea)

    def test_editarlo_escribe_su_linea_junto_a_la_fecha(self):
        t = tarea.ARCHIVO.leer(TEXTO, "T1")
        nueva = tarea.editar(t, tamano="larga")
        texto = tarea.ARCHIVO.escribir(TEXTO, t, nueva)
        self.assertIn("vence: 2026-11-03\ntamaño: larga\n", texto)
        self.assertEqual(tarea.ARCHIVO.leer(texto, "T1").tamano, "larga")
        with self.assertRaises(tarea.ErrorDeAccion):
            tarea.editar(t, tamano="enorme")
        self.assertEqual(tarea.nueva("Llamar", tamano="rápida").tamano, "rapida")
