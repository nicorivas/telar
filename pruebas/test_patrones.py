"""Los patrones de fecha de Unicode (telar.patrones): leer y escribir una fecha con la forma de un patrón."""

from __future__ import annotations

import unittest
from datetime import date

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.patrones import ErrorDePatron, Patron


class LeerYEscribir(Prueba):
    def test_dia_de_la_semana_y_mes_en_palabras(self):
        p = Patron("EEE d-MMM", idioma="es")
        for texto in ("jue 18-jun", "Jue 18-Jun.", "jue 18-junio"):
            self.assertEqual(p.leer(texto, anio=2026), date(2026, 6, 18), texto)
        self.assertEqual(p.leer("mié 1-jul", anio=2026), date(2026, 7, 1))  # con tilde, o sin ella
        self.assertEqual(p.leer("mie 1-jul", anio=2026), date(2026, 7, 1))
        self.assertEqual(p.leer("mar 15-sept", anio=2026), p.leer("mar 15-sep", anio=2026))
        # al escribir, el día de la semana se recalcula
        self.assertEqual(p.escribir(date(2026, 11, 17)), "mar 17-nov")

    def test_numeros_texto_entre_comillas_y_anio_de_dos_cifras(self):
        self.assertEqual(Patron("dd/MM/yyyy").leer("17/11/2026"), date(2026, 11, 17))
        self.assertEqual(Patron("dd/MM/yyyy").escribir(date(2026, 1, 5)), "05/01/2026")
        self.assertEqual(Patron("d 'de' MMMM 'de' yyyy").leer("5 de noviembre de 2026"), date(2026, 11, 5))
        self.assertEqual(Patron("d.M.yy").leer("5.11.26"), date(2026, 11, 5))
        self.assertEqual(Patron("MMM d", idioma="en").leer("Nov 5", anio=2026), date(2026, 11, 5))

    def test_lo_que_no_calza_o_no_existe_es_un_error_que_dice_que(self):
        p = Patron("d-MMM")
        with self.assertRaises(ErrorDePatron):
            p.leer("18 de junio", anio=2026)
        with self.assertRaisesRegex(ErrorDePatron, "año"):
            p.leer("18-jun")
        with self.assertRaisesRegex(ErrorDePatron, "no es un día"):
            p.leer("31-feb", anio=2026)
        with self.assertRaises(ErrorDePatron):
            Patron("--/--")  # sin ningún campo (las letras sueltas sí son campos: lo literal va entre comillas)

    def test_horas_y_la_primera_mitad_de_un_rango(self):
        self.assertEqual(Patron("HH:mm").hora("9:30"), "09:30")
        p = Patron("d MMM")
        self.assertEqual(p.partes("17", parcial=True), {"d": 17})
        with self.assertRaises(ErrorDePatron):
            p.partes("17")


if __name__ == "__main__":
    unittest.main()
