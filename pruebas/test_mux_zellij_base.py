"""zellij habla el vocabulario de la base: tabs y paneles, no solo hilos.

Con un doble que contesta el JSON que da `list-panes -j`: lo que se prueba es la
traducción, no zellij. Lo que zellij no puede hacer —mover paneles entre tabs— se
prueba que lo diga claro, que es la otra mitad de implementar una interfaz.
"""
import json
import unittest

from pruebas import comun  # noqa: F401  (pone src/ en el path)

from telar.mux import ErrorDeMux
from telar.mux.base import MultiplexorBase, Pane, Tab
from telar.mux.zellij import Zellij

PANELES = [
    {"id": 1, "tab_id": 3, "tab_name": "arboleda", "tab_position": 0, "is_plugin": False,
     "title": "✳ una conversación", "pane_command": "claude --resume abc", "pane_cwd": "/tmp/arboleda",
     "is_focused": True, "is_floating": False, "exited": False},
    {"id": 2, "tab_id": 3, "tab_name": "arboleda", "tab_position": 0, "is_plugin": False,
     "title": "ficha", "pane_command": "python3", "pane_cwd": "/tmp/arboleda",
     "is_focused": False, "is_floating": True, "exited": False},
    {"id": 7, "tab_id": 4, "tab_name": "faro", "tab_position": 1, "is_plugin": False,
     "title": "", "pane_command": "/bin/zsh", "pane_cwd": "", "is_focused": True,
     "is_floating": False, "exited": True},
]


class ZellijFalso(Zellij):
    """Contesta lo enlatado y anota lo que se le pidió."""

    def __init__(self, tab_activo=3):
        super().__init__("taller")
        self.ordenes: list[list[str]] = []
        self._activo = tab_activo

    def _accion(self, *argumentos, espera=None):
        self.ordenes.append(list(argumentos))
        if argumentos[0] == "list-panes":
            return json.dumps(PANELES)
        return ""

    def _correr(self, argumentos, *, espera=None):
        # el tab activo se pregunta por aquí, no por _accion: `current-tab-info -j`
        self.ordenes.append(list(argumentos))
        if "current-tab-info" in argumentos:
            return 0, json.dumps({"tab_id": self._activo, "name": "arboleda"}), ""
        return 0, "", ""

    def viva(self) -> bool:
        return True

    def una(self, orden: str) -> list[str]:
        return next(o for o in self.ordenes if o and o[0] == orden)


class Interfaz(unittest.TestCase):
    def test_zellij_es_un_multiplexor_base_completo(self):
        self.assertTrue(issubclass(Zellij, MultiplexorBase))
        self.assertFalse(getattr(Zellij, "__abstractmethods__", set()))


class Traduccion(unittest.TestCase):
    def setUp(self):
        self.mux = ZellijFalso()

    def test_tabs_salen_ordenados_y_con_su_cuenta_de_paneles(self):
        tabs = self.mux.tabs()
        self.assertEqual([(t.id, t.nombre, t.posicion, t.paneles) for t in tabs],
                         [("3", "arboleda", 0, 2), ("4", "faro", 1, 1)])
        self.assertTrue(isinstance(tabs[0], Tab))

    def test_el_tab_activo_sale_de_current_tab_info(self):
        self.assertEqual((self.mux.tab_activo() or Tab("", 0, "")).id, "3")
        mux = ZellijFalso(tab_activo=4)
        self.assertEqual((mux.tab_activo() or Tab("", 0, "")).id, "4")

    def test_los_paneles_llevan_lo_que_hace_falta_para_reconocer_al_agente(self):
        panes = self.mux.panes("arboleda")
        self.assertTrue(all(isinstance(p, Pane) for p in panes))
        cabeza = panes[0]
        self.assertEqual((cabeza.id, cabeza.tab, cabeza.comando), ("terminal_1", "3", "claude --resume abc"))
        self.assertTrue(cabeza.foco)
        self.assertTrue(panes[1].flotante)

    def test_un_panel_terminado_se_nota(self):
        faro = [p for p in self.mux.panes() if p.tab == "4"][0]
        self.assertTrue(faro.terminado)
        self.assertFalse(faro.vivo)
        self.assertIsNone(faro.ruta)

    def test_escribir_sin_enviar_no_admite_saltos(self):
        with self.assertRaises(ErrorDeMux):
            self.mux.escribir_pane("terminal_1", "hola\n")
        self.mux.escribir_pane("terminal_1", "hola")
        self.assertEqual(self.mux.una("write-chars"), ["write-chars", "-p", "terminal_1", "--", "hola"])

    def test_enviar_manda_el_retorno_aparte(self):
        self.mux.escribir_pane("terminal_1", "hola", enviar=True)
        self.assertEqual(self.mux.una("write"), ["write", "-p", "terminal_1", "--", "13"])

    def test_ir_a_tab_apunta_por_id(self):
        self.mux.ir_a_tab("arboleda")
        self.assertEqual(self.mux.una("go-to-tab-by-id"), ["go-to-tab-by-id", "3"])

    def test_mover_un_panel_entre_tabs_dice_que_no_puede_y_por_que(self):
        with self.assertRaises(ErrorDeMux) as e:
            self.mux.mover_pane("terminal_1", tab="faro")
        self.assertIn("tmux", str(e.exception))


if __name__ == "__main__":
    unittest.main()
