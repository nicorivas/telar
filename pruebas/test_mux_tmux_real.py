"""tmux de verdad: una sesión propia, creada y cerrada aquí.

Lo demás de tmux se prueba con un doble en `test_mux_tmux.py`, que mira la forma exacta
de cada orden. Esto es la otra mitad: que esas órdenes hagan lo que dicen contra el tmux
instalado, que es lo único que nota un cambio de versión. Nunca toca otra sesión, ni el
servidor de la persona: corre en uno propio (`TMUX_TMPDIR` en una carpeta nueva, sin
`TMUX`), porque tejer también le limpia el entorno global al servidor.
"""
import os
import shutil
import tempfile
import time
import unittest

from pruebas import comun  # pone src/ en el path

from telar.config import Config
from telar.mux import ErrorDeMux
from telar.mux.tmux import Tmux

SESION = "telar-pruebas-mux"
HAY_TMUX = shutil.which("tmux") is not None


def _mux(sesion=SESION):
    return Tmux(Config(multiplexor="tmux", sesion=sesion))


@unittest.skipUnless(HAY_TMUX, "sin tmux instalado")
class ContraTmuxDeVerdad(comun.Prueba):
    """Una sesión propia, creada y cerrada aquí. Sin `TELAR_*` (`comun.Prueba`): corridas desde un hilo, con su
    `TELAR_HILO`, telar se cree un agente y no mueve el foco, y las pruebas de ir a un tab fallaban."""

    @classmethod
    def setUpClass(cls):
        cls.socket = tempfile.mkdtemp(prefix="telar-mux-real-")
        cls.entorno = {clave: os.environ.get(clave) for clave in ("TMUX_TMPDIR", "TMUX")}
        os.environ["TMUX_TMPDIR"] = cls.socket
        os.environ.pop("TMUX", None)  # dentro de tmux, apuntaría al servidor de la persona
        cls.mux = _mux()
        cls.mux.tejer()

    @classmethod
    def tearDownClass(cls):
        comun.matar_tmux(cls.socket)
        for clave, valor in cls.entorno.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor
        shutil.rmtree(cls.socket, ignore_errors=True)

    def test_la_sesion_esta_viva_y_tiene_un_tab(self):
        self.assertTrue(self.mux.disponible())
        self.assertTrue(self.mux.viva())
        self.assertGreaterEqual(len(self.mux.tabs()), 1)

    def test_la_sesion_tiene_los_ganchos_del_foco(self):
        from telar.mux.tmux import GANCHOS_FOCO, ejecutable_telar

        if not ejecutable_telar():
            self.skipTest("sin telar en el PATH: no hay a quién avisarle")
        ganchos = self.mux._tmux("show-hooks", "-t", f"={SESION}:")
        for gancho in GANCHOS_FOCO:
            self.assertIn(gancho, ganchos)
        self.assertIn("tiempo marcar", ganchos)

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
        # el proceso tarda un parpadeo en reemplazar a la shell: se espera, no se adivina
        comandos: list[str] = []
        for _ in range(20):
            comandos = [p.comando for p in self.mux.panes(tab.id)]
            if any("sleep" in c for c in comandos):
                break
            time.sleep(0.1)
        self.assertTrue(any("sleep" in c for c in comandos), comandos)
        self.mux.cerrar_tab(tab.id)

    def test_un_tab_que_no_existe_se_queja_claro(self):
        with self.assertRaises(ErrorDeMux):
            self.mux.ir_a_tab("@99999")


if __name__ == "__main__":
    unittest.main()
