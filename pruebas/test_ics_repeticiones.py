"""iCal: una serie que se repite, su excepción y dónde termina.

Los dos casos salieron del calendario real de una persona, y los dos mostraban de más:
una reunión semanal movida una hora aparecía en la hora vieja y en la nueva, y una serie
cerrada con `UNTIL:…T045959Z` daba una instancia el día siguiente al último.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta, timezone

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.proveedores.calendario import eventos_del_dia, leer_ics

SERIE = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:coord
DTSTART;TZID=America/Bogota:20260922T110000
DTEND;TZID=America/Bogota:20260922T120000
RRULE:FREQ=WEEKLY;UNTIL=20260929T045959Z;BYDAY=TU
SUMMARY:Coordinación interna ANASAC
END:VEVENT
BEGIN:VEVENT
UID:coord
DTSTART;TZID=America/Bogota:20260922T100000
DTEND;TZID=America/Bogota:20260922T110000
RECURRENCE-ID;TZID=America/Bogota:20260922T110000
SUMMARY:Coordinación interna ANASAC
END:VEVENT
END:VCALENDAR
"""

VIEJA = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:coord-vieja
DTSTART;TZID=America/Bogota:20260908T110000
DTEND;TZID=America/Bogota:20260908T120000
RRULE:FREQ=WEEKLY;UNTIL=20260922T045959Z;BYDAY=TU
SUMMARY:Coordinación interna ANASAC
END:VEVENT
END:VCALENDAR
"""


#: la zona del calendario, fija para que la prueba diga lo mismo en cualquier máquina
BOGOTA = timezone(timedelta(hours=-5))


def horas(ics: str, dia: date) -> list[str]:
    eventos = eventos_del_dia(leer_ics(ics, local=BOGOTA), dia, local=BOGOTA)
    return [e.inicio.strftime("%H:%M") for e in eventos]


class UnaExcepcionReemplazaASuInstancia(Prueba):
    def test_la_reunion_movida_aparece_una_sola_vez(self):
        self.assertEqual(horas(SERIE, date(2026, 9, 22)), ["10:00"])

    def test_la_excepcion_no_borra_los_demas_martes(self):
        self.assertEqual(horas(SERIE, date(2026, 9, 15)), [])   # la serie empieza el 22
        # y termina con él: UNTIL 2026-09-29T04:59:59Z es la noche del 28 en Bogotá
        self.assertEqual(horas(SERIE, date(2026, 9, 29)), [])

    def test_sin_la_excepcion_la_serie_da_su_hora(self):
        sin_excepcion = SERIE[: SERIE.index("BEGIN:VEVENT", 20)] + "END:VCALENDAR\n"
        self.assertEqual(horas(sin_excepcion, date(2026, 9, 22)), ["11:00"])


class DondeTerminaLaSerie(Prueba):
    def test_until_con_hora_no_alcanza_al_dia_siguiente(self):
        # UNTIL 2026-09-22T04:59:59Z es la noche del 21 en Bogotá: el último martes es el 15
        self.assertEqual(horas(VIEJA, date(2026, 9, 15)), ["11:00"])
        self.assertEqual(horas(VIEJA, date(2026, 9, 22)), [])


if __name__ == "__main__":
    unittest.main()
