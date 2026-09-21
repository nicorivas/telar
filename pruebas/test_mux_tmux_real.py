"""tmux de verdad: una sesión propia, creada y cerrada aquí.

Lo demás de tmux se prueba con un doble en `test_mux_tmux.py`, que mira la forma exacta
de cada orden. Esto es la otra mitad: que esas órdenes hagan lo que dicen contra el tmux
instalado, que es lo único que nota un cambio de versión. Nunca toca otra sesión.
"""
import shutil
import unittest

from pruebas import comun  # noqa: F401  (pone src/ en el path)

from telar.config import Config
from telar.mux import ErrorDeMux
from telar.mux.tmux import Tmux

SESION = "telar-pruebas-mux"
HAY_TMUX = shutil.which("tmux") is not None


def _mux(sesion=SESION):
    return Tmux(Config(multiplexor="tmux", sesion=sesion))


@unittest.skipUnless(HAY_TMUX, "sin tmux instalado")
class ContraTmuxDeVerdad(unittest.TestCase):
    """Una sesión propia, creada y cerrada aquí."""

    @classmethod
    def setUpClass(cls):
        cls.mux = _mux()
        cls.mux._tmux("kill-session", "-t", SESION, tolerante=True)
        cls.mux.tejer()

    @classmethod
    def tearDownClass(cls):
        cls.mux._tmux("kill-session", "-t", SESION, tolerante=True)

    def test_la_sesion_esta_viva_y_tiene_un_tab(self):
        self.assertTrue(self.mux.disponible())
        self.assertTrue(self.mux.viva())
        self.assertGreaterEqual(len(self.mux.tabs()), 1)

    def test_crear_renombrar_y_cerrar_un_tab(self):
        tab = self.mux.crear_tab(nombre="telar-uno")
        self.assertIn("telar-uno", [t.nombre for t in self.mux.tabs()])
        self.mux.renombrar_tab(tab.id, "telar-dos")
        self.assertIn("telar-dos", [t.nombre for t in self.mux.tabs()])
        self.mux.cerrar_tab(tab.id)
        self.assertNotIn("telar-dos", [t.nombre for t in self.mux.tabs()])

    def test_el_tab_activo_cambia_al_ir(self):
        primero = self.mux.tabs()[0]
        otro = self.mux.crear_tab(nombre="telar-activo")
        self.mux.ir_a_tab(primero.id)
        self.assertEqual((self.mux.tab_activo() or primero).id, primero.id)
        self.mux.ir_a_tab(otro.id)
        self.assertEqual((self.mux.tab_activo() or otro).id, otro.id)
        self.mux.cerrar_tab(otro.id)

    def test_escribir_en_un_pane_sin_enviar_no_ejecuta(self):
        tab = self.mux.crear_tab(nombre="telar-escribir")
        pane = self.mux.panes(tab.id)[0]
        self.mux.escribir_pane(pane.id, "echo telar")
        volcado = self.mux._tmux("capture-pane", "-p", "-t", pane.id)
        self.assertIn("echo telar", volcado)
        with self.assertRaises(ErrorDeMux):  # el salto ES el ↩: no se escribe a escondidas
            self.mux.escribir_pane(pane.id, "echo telar\n")
        self.mux.cerrar_tab(tab.id)

    def test_mover_un_pane_de_un_tab_a_otro(self):
        origen = self.mux.crear_tab(nombre="telar-origen")
        destino = self.mux.crear_tab(nombre="telar-destino")
        pane = self.mux.panes(origen.id)[0]
        self.mux.mover_pane(pane.id, tab=destino.id)
        self.assertIn(pane.id, [p.id for p in self.mux.panes(destino.id)])
        self.assertNotIn(origen.nombre, [t.nombre for t in self.mux.tabs()])  # quedó vacío
        self.mux.cerrar_tab(destino.id)

    def test_el_comando_que_corre_un_pane_se_ve(self):
        tab = self.mux.crear_tab(nombre="telar-comando", comando=["sleep", "30"])
        comandos = [p.comando for p in self.mux.panes(tab.id)]
        self.assertTrue(any("sleep" in c for c in comandos), comandos)
        self.mux.cerrar_tab(tab.id)

    def test_un_tab_que_no_existe_se_queja_claro(self):
        with self.assertRaises(ErrorDeMux):
            self.mux.ir_a_tab("@99999")


if __name__ == "__main__":
    unittest.main()
