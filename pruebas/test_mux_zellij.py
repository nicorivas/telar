"""zellij: que se le hable por id, que no se le pregunte al cliente equivocado,
y que lo que no se puede hacer se diga en vez de hacerse a medias.

No hace falta un zellij instalado: `Zellij._correr` es la única costura con el
sistema, y aquí se reemplaza por respuestas enlatadas. Lo que se prueba, entonces,
es lo único que telar controla: qué comando arma, cómo lee la respuesta y qué
decide con ella.
"""

from __future__ import annotations

import json
import os
import unittest

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.config import Config
from telar.mux import ErrorDeMux, Multiplexor
from telar.mux import zellij as z


def panel(**campos) -> dict:
    """Un panel como los describe `list-panes -t -c -s -j`, con lo mínimo puesto."""
    base = {
        "id": 0,
        "is_plugin": False,
        "is_focused": False,
        "is_floating": False,
        "is_suppressed": False,
        "exited": False,
        "title": "",
        "pane_command": "/bin/zsh",
        "pane_cwd": "/taller",
        "tab_id": 0,
        "tab_position": 0,
        "tab_name": "faro",
    }
    base.update(campos)
    return base


PANELES = [
    panel(id=1, tab_id=7, tab_position=0, tab_name="faro", pane_cwd="/taller/faro", is_focused=True),
    panel(id=2, tab_id=7, tab_position=0, tab_name="faro", pane_cwd="/otra", is_floating=True),
    panel(id=3, tab_id=4, tab_position=1, tab_name="molino", pane_cwd="/taller/molino"),
    panel(id=4, tab_id=9, tab_position=2, tab_name="arboleda", is_plugin=True, pane_cwd=""),
]


class ZellijFalso(z.Zellij):
    """Un zellij de mentira: contesta lo enlatado y anota todo lo que se le pidió."""

    def __init__(self, sesion="taller", *, paneles=None, activo=7, sesiones="taller\n"):
        super().__init__(sesion, binario="zellij")
        self.llamadas: list[list[str]] = []
        self.paneles_falsos = PANELES if paneles is None else paneles
        self.tab_activo_falso = activo
        self.sesiones = sesiones
        self.respuestas: dict[str, tuple[int, str, str]] = {}
        #: panel que aparece recién DESPUÉS de un `new-pane`, como en la sesión de verdad.
        self.panel_nuevo: dict | None = None

    def _correr(self, argumentos, *, espera=None):
        self.llamadas.append(list(argumentos))
        orden = argumentos[3] if argumentos[:1] == ["-s"] else argumentos[0]
        if orden == "new-pane" and self.panel_nuevo is not None:
            self.paneles_falsos = list(self.paneles_falsos) + [self.panel_nuevo]
            self.panel_nuevo = None
        if orden in self.respuestas:
            return self.respuestas[orden]
        if orden == "list-sessions":
            return (0, self.sesiones, "") if self.sesiones else (1, "", "No active zellij sessions")
        if orden == "list-panes":
            return 0, json.dumps(self.paneles_falsos), ""
        if orden == "current-tab-info":
            if self.tab_activo_falso is None:
                return 2, "", "No active tab found for current client"
            return 0, json.dumps({"name": "faro", "tab_id": self.tab_activo_falso}), ""
        return 0, "", ""

    def acciones(self) -> list[list[str]]:
        """Las llamadas, sin el prefijo `-s <sesión> action`."""
        return [a[3:] for a in self.llamadas if a[:1] == ["-s"]]


class LaSesion(Prueba):
    def test_viva_es_estar_en_la_lista(self):
        self.assertTrue(ZellijFalso(sesiones="otra\ntaller\n").viva())
        self.assertFalse(ZellijFalso(sesiones="otra\n").viva())

    def test_una_sesion_muerta_no_esta_viva(self):
        muerta = ZellijFalso(sesiones="taller [Created 2h ago] (EXITED - attach to resurrect)\n")
        self.assertFalse(muerta.viva())

    def test_sin_ninguna_sesion_no_es_un_error(self):
        self.assertFalse(ZellijFalso(sesiones="").viva())

    def test_las_acciones_van_dirigidas_a_la_sesion(self):
        m = ZellijFalso()
        m.hilos()
        for llamada in m.llamadas:
            if llamada[0] != "list-sessions":
                self.assertEqual(llamada[:2], ["-s", "taller"])

    def test_el_entorno_no_lleva_las_variables_de_zellij(self):
        os.environ["ZELLIJ_SESSION_NAME"] = "otra"
        os.environ["ZELLIJ_PANE_ID"] = "3"
        try:
            entorno = ZellijFalso()._entorno()
        finally:
            del os.environ["ZELLIJ_SESSION_NAME"], os.environ["ZELLIJ_PANE_ID"]
        self.assertFalse([k for k in entorno if k.startswith("ZELLIJ")])


class LosHilos(Prueba):
    def test_un_hilo_por_tab_en_el_orden_de_zellij(self):
        hilos = ZellijFalso().hilos()
        self.assertEqual([h.id for h in hilos], ["7", "4", "9"])
        self.assertEqual([h.nombre for h in hilos], ["faro", "molino", "arboleda"])

    def test_el_id_es_el_tab_id_estable_no_la_posicion(self):
        hilos = ZellijFalso().hilos()
        self.assertEqual(hilos[1].id, "4")  # posición 1, id 4

    def test_la_ruta_sale_del_panel_principal_no_del_flotante(self):
        faro = ZellijFalso().hilos()[0]
        self.assertEqual(str(faro.ruta), "/taller/faro")

    def test_un_tab_de_puro_plugin_existe_pero_sin_ruta(self):
        arboleda = ZellijFalso().hilos()[2]
        self.assertIsNone(arboleda.ruta)

    def test_el_activo_lo_dice_zellij_no_el_primer_cliente(self):
        m = ZellijFalso(activo=4)
        activo = m.activo()
        self.assertEqual(activo.id, "4")
        self.assertEqual(sum(1 for h in m.hilos() if h.activo), 1)
        self.assertNotIn(["list-clients"], m.acciones())

    def test_sin_tab_activo_no_hay_activo_y_no_se_cae(self):
        m = ZellijFalso(activo=None)
        self.assertIsNone(m.activo())
        self.assertEqual(len(m.hilos()), 3)

    def test_una_sesion_que_no_esta_no_tiene_hilos_y_no_es_un_error(self):
        m = ZellijFalso(sesiones="")
        m.respuestas["list-panes"] = (1, "", "Session 'taller' not found.")
        self.assertEqual(m.hilos(), [])

    def test_si_la_sesion_esta_viva_el_fallo_de_list_panes_se_dice(self):
        m = ZellijFalso()
        m.respuestas["list-panes"] = (1, "", "algo se rompió")
        with self.assertRaises(ErrorDeMux):
            m.hilos()

    def test_una_respuesta_que_no_es_json_se_dice(self):
        m = ZellijFalso()
        m.respuestas["list-panes"] = (0, "no soy json", "")
        with self.assertRaises(ErrorDeMux):
            m.paneles()


class ApuntarPorId(Prueba):
    def test_ir_usa_el_id_estable(self):
        m = ZellijFalso()
        m.ir("7")
        self.assertIn(["go-to-tab-by-id", "7"], m.acciones())

    def test_tambien_se_puede_llamar_por_nombre(self):
        m = ZellijFalso()
        m.ir("molino")
        self.assertIn(["go-to-tab-by-id", "4"], m.acciones())

    def test_cerrar_usa_close_tab_by_id(self):
        m = ZellijFalso()
        m.cerrar("faro")
        self.assertIn(["close-tab-by-id", "7"], m.acciones())

    def test_renombrar_siempre_apunta_al_tab(self):
        m = ZellijFalso()
        m.renombrar("faro", "-molino")
        self.assertIn(["rename-tab", "-t", "7", "--", "-molino"], m.acciones())

    def test_un_hilo_que_no_existe_se_dice_con_los_que_hay(self):
        with self.assertRaises(ErrorDeMux) as e:
            ZellijFalso().ir("puerto")
        self.assertIn("faro", str(e.exception))


class Escribir(Prueba):
    def test_escribe_en_el_panel_por_id_sin_mover_el_foco(self):
        m = ZellijFalso()
        m.escribir("faro", "Veamos T84")
        self.assertIn(["write-chars", "-p", "terminal_1", "--", "Veamos T84"], m.acciones())
        self.assertFalse([a for a in m.acciones() if a[0] in ("focus-pane-id", "move-focus")])

    def test_por_defecto_no_envia(self):
        m = ZellijFalso()
        m.escribir("faro", "hola")
        self.assertFalse([a for a in m.acciones() if a[0] == "write"])

    def test_enviar_manda_el_retorno(self):
        m = ZellijFalso()
        m.escribir("faro", "hola", enviar=True)
        self.assertIn(["write", "-p", "terminal_1", "--", "13"], m.acciones())

    def test_un_texto_con_guion_no_se_lee_como_bandera(self):
        m = ZellijFalso()
        m.escribir("faro", "--version")
        escritura = [a for a in m.acciones() if a[0] == "write-chars"][0]
        self.assertEqual(escritura[-2:], ["--", "--version"])

    def test_no_se_le_escribe_a_un_panel_muerto(self):
        m = ZellijFalso(paneles=[panel(id=1, tab_id=7, exited=True)])
        with self.assertRaises(ErrorDeMux):
            m.escribir("7", "hola")


class Crear(Prueba):
    def test_el_nombre_y_la_ruta_van_pegados_a_la_bandera(self):
        m = ZellijFalso()
        m.respuestas["new-tab"] = (0, "7\n", "")
        hilo = m.crear("faro", ruta="/taller/faro")
        creacion = [a for a in m.acciones() if a[0] == "new-tab"][0]
        self.assertIn("--name=faro", creacion)
        self.assertIn("--cwd=/taller/faro", creacion)
        self.assertEqual(hilo.id, "7")

    def test_el_comando_va_despues_del_doble_guion(self):
        m = ZellijFalso()
        m.respuestas["new-tab"] = (0, "7\n", "")
        m.crear("faro", comando=["agente", "--retomar"])
        creacion = [a for a in m.acciones() if a[0] == "new-tab"][0]
        self.assertEqual(creacion[-3:], ["--", "agente", "--retomar"])

    def test_si_zellij_no_dice_que_tab_creo_se_dice(self):
        m = ZellijFalso(paneles=[])
        m.respuestas["new-tab"] = (0, "", "")
        with self.assertRaises(ErrorDeMux):
            m.crear("puerto")


class Reemplazar(Prueba):
    def test_reemplaza_en_el_lugar_y_cierra_lo_reemplazado(self):
        m = ZellijFalso()
        m.respuestas["new-pane"] = (0, "terminal_9\n", "")
        nuevo = m.reemplazar("faro", ["agente"], ruta="/taller/faro")
        orden = [a for a in m.acciones() if a[0] == "new-pane"][0]
        self.assertEqual(nuevo, "terminal_9")
        self.assertIn("--in-place", orden)
        self.assertIn("--close-replaced-pane", orden)
        self.assertIn("--pane-id=terminal_1", orden)

    def test_si_no_imprime_el_id_se_busca_el_panel_nuevo(self):
        m = ZellijFalso()
        m.respuestas["new-pane"] = (0, "", "")  # pasa al reemplazar un panel terminado
        m.panel_nuevo = panel(id=42, tab_id=7, tab_name="faro")
        dormir = z.time.sleep
        z.time.sleep = lambda _s: None
        try:
            self.assertEqual(m.reemplazar("faro", ["agente"]), "terminal_42")
        finally:
            z.time.sleep = dormir


class LoQueNoSePuede(Prueba):
    def test_mover_panes_no_se_puede_y_explica_por_que(self):
        with self.assertRaises(z.NoSoportado) as e:
            ZellijFalso().mover_panes("faro", "molino")
        mensaje = str(e.exception)
        self.assertIn("plugin", mensaje)
        self.assertIn("zellij pipe", mensaje)

    def test_no_soportado_sigue_siendo_un_error_de_mux(self):
        self.assertTrue(issubclass(z.NoSoportado, ErrorDeMux))

    def test_es_el_multiplexor_que_pide_la_configuracion(self):
        self.assertEqual(z.Zellij("taller").nombre, "zellij")
        self.assertEqual(z.Zellij(Config(sesion="taller").sesion).sesion, "taller")

    def test_cumple_el_protocolo_del_multiplexor(self):
        self.assertIsInstance(z.Zellij("taller"), Multiplexor)


if __name__ == "__main__":
    unittest.main()
