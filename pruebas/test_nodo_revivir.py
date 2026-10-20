"""nodo: un hilo archivado aquí que vuelve a trabajar allá se desarchiva, y si no, se dice por qué no."""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace as N

import comun  # noqa: F401 (src/ en el camino)

from telar.ordenes.nodo import Nodo


class FalsoEstado:
    def __init__(self, archivados, cuando=None):
        self._a = set(archivados)
        self._cuando = cuando

    def archivados(self):
        return set(self._a)

    def archivado_en(self, hilo):
        return self._cuando

    def desarchivar(self, hilo):
        self._a.discard(hilo)


class Revivir(unittest.TestCase):
    def nodo(self):
        n = Nodo.__new__(Nodo)
        n.lineas = []
        n.anotar = n.lineas.append
        return n

    def corre(self, estado, desde):
        n = self.nodo()
        d = {"vivo": True, "desde": desde.isoformat(timespec="seconds") if desde else ""}
        n._revivir(N(estado=estado), "T380 Anglo", d, "telar")
        return n.lineas

    def test_actividad_posterior_al_archivo_lo_desarchiva(self):
        arch = datetime(2026, 10, 20, 15, 42)
        est = FalsoEstado({"T380 Anglo"}, arch)
        lineas = self.corre(est, arch + timedelta(hours=1))
        self.assertNotIn("T380 Anglo", est.archivados())
        self.assertIn("lo desarchivé", lineas[0])

    def test_sin_actividad_nueva_sigue_archivado_y_lo_dice(self):
        arch = datetime(2026, 10, 20, 15, 42)
        est = FalsoEstado({"T380 Anglo"}, arch)
        lineas = self.corre(est, arch - timedelta(hours=1))
        self.assertIn("T380 Anglo", est.archivados())
        self.assertIn("sigue archivado", lineas[0])

    def test_sin_fecha_de_archivo_no_se_reabre_y_lo_dice(self):
        est = FalsoEstado({"T380 Anglo"}, None)
        lineas = self.corre(est, datetime(2026, 10, 20, 16, 52))
        self.assertIn("T380 Anglo", est.archivados())
        self.assertIn("sin fecha de archivo", lineas[0])

    def test_un_hilo_que_no_esta_archivado_no_se_toca(self):
        est = FalsoEstado(set(), None)
        self.assertEqual(self.corre(est, datetime(2026, 10, 20, 16, 52)), [])


if __name__ == "__main__":
    unittest.main()
