"""Renombrar un tab en el multiplexor no debe huerfanar su estado."""
import tempfile
import unittest
from pathlib import Path

from pruebas import comun  # noqa: F401  (pone src/ en el path)

from telar import estado as mod_estado
from telar.modelo import Atencion, Hilo, Prioridad


class Reconciliar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.est = mod_estado.Estado(Path(self.tmp.name))
        self.est.preparar()
        self.est.vincular("arboleda", "proyectos/arboleda")
        self.est.prioridad("arboleda", Prioridad.ALTA)
        self.est.anotar_atencion("arboleda", Atencion.ESPERA)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sigue_el_renombre_y_no_deja_fantasma(self):
        # se vio el tab con su nombre viejo…
        self.est.reconciliar([Hilo(id="@1", nombre="arboleda")])
        # …y ahora el multiplexor lo muestra renombrado
        cambios = self.est.reconciliar([Hilo(id="@1", nombre="arb2")])

        self.assertEqual(cambios, [("arboleda", "arb2")])
        self.assertEqual(self.est.vinculo("arb2"), "proyectos/arboleda")
        self.assertEqual(self.est.prioridad_de("arb2") if hasattr(self.est, "prioridad_de")
                         else self.est.prioridades().get("arb2"), Prioridad.ALTA)
        self.assertEqual(self.est.atencion("arb2"), Atencion.ESPERA)
        self.assertEqual(self.est.vinculo("arboleda"), "")
        self.assertNotIn("arboleda", self.est.prioridades())
        self.assertFalse(self.est.conoce("arboleda"))

    def test_un_tab_nuevo_con_un_nombre_usado_no_mueve_nada(self):
        # sin haber visto ese id antes, no hay renombre que seguir
        cambios = self.est.reconciliar([Hilo(id="@9", nombre="otro")])
        self.assertEqual(cambios, [])
        self.assertEqual(self.est.vinculo("arboleda"), "proyectos/arboleda")

    def test_sin_id_propio_no_inventa_renombres(self):
        # el caso «sin multiplexor»: el id ES el nombre, así que no dice nada
        self.assertEqual(self.est.reconciliar([Hilo(id="arboleda", nombre="arboleda")]), [])
        self.assertTrue(self.est.conoce("arboleda"))


if __name__ == "__main__":
    unittest.main()
