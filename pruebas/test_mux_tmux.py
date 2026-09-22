"""tmux: que lo que se lee se lea entero, que lo que se cita no se ejecute, y que
lo que se nombra apunte al tab que se nombró y no al de al lado.

tmux es el multiplexor por defecto y la implementación de referencia, así que se
prueba en dos capas, que miran cosas distintas a propósito:

  · **las funciones puras** (`_linea`, `_tamano`, `_banderas`, `_tab`, `_pane_desde`,
    los objetivos, la traducción de la queja) y **la forma de las órdenes**, con un
    tmux de mentira que anota lo que se le pidió. Corren en cualquier máquina, no
    dependen de que haya un tmux ni de qué versión sea, y son las que dicen *qué
    comando arma telar*;

  · **la integración contra un tmux de verdad**, que es la única capa que puede
    notar que una versión nueva cambió el nombre de una bandera o el texto de un
    error. Se saltea sola si la máquina no tiene tmux; el CI lo instala.

La sesión de las pruebas de integración vive en un servidor propio: `TMUX_TMPDIR`
decide dónde está el socket, así que con un directorio recién hecho el tmux que
levantan las pruebas no ve —ni puede tocar— el que la persona tenga abierto.
"""

from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.config import Config
from telar.mux import IMPLEMENTACIONES, ErrorDeMux, Multiplexor, obtener
from telar.mux import tmux as t
from telar.mux.base import NoExiste, SinPrograma, SinSesion


def fila_tab(ident="@3", indice="2", nombre="faro", activo="1", paneles="1") -> str:
    """Un renglón como el que devuelve `list-windows -F`, con los campos ya pegados."""
    return t.SEP.join([ident, indice, nombre, activo, paneles])


def fila_pane(
    ident="%7",
    ventana="@3",
    titulo="ficha",
    comando="sh",
    ruta="/taller",
    activo="1",
    muerto="0",
    pid="4242",
) -> str:
    """Un renglón como el que devuelve `list-panes -F`."""
    return t.SEP.join([ident, ventana, titulo, comando, ruta, activo, muerto, pid])


def mux(sesion="taller") -> t.Tmux:
    """Un `Tmux` sin nada alrededor, para las funciones que no hablan con el programa."""
    return t.Tmux(Config(sesion=sesion))


# ── capa 1: las funciones puras ──────────────────────────────────────────────────


class Citar(Prueba):
    """`_linea`: el comando entra como lista de palabras y sale como una sola palabra."""

    def test_sin_comando_no_hay_linea(self):
        self.assertEqual(t._linea(None), "")
        self.assertEqual(t._linea([]), "")

    def test_las_palabras_siguen_siendo_las_mismas(self):
        self.assertEqual(t._linea(["agente", "--retomar"]), "agente --retomar")

    def test_una_palabra_con_espacios_no_se_parte_en_dos(self):
        linea = t._linea(["echo", "hola mundo"])
        self.assertEqual(linea, "echo 'hola mundo'")

    def test_un_punto_y_coma_queda_citado_y_no_se_ejecuta(self):
        linea = t._linea(["echo", "uno; rm -rf /"])
        self.assertIn("'uno; rm -rf /'", linea)
        # el `;` va adentro de las comillas: el shell lo ve como texto, no como separador.
        self.assertFalse(linea.endswith("/"))

    def test_una_comilla_tampoco_escapa(self):
        self.assertNotIn("$(", t._linea(["echo", "'; touch /tmp/x; '"]))

    def test_una_linea_de_shell_no_se_acepta(self):
        with self.assertRaises(ErrorDeMux) as e:
            t._linea("ls -l")
        self.assertIn("sh", str(e.exception))

    def test_lo_que_no_es_texto_se_vuelve_texto(self):
        self.assertEqual(t._linea(["cat", Path("/taller/nota.md")]), "cat /taller/nota.md")


class Medir(Prueba):
    """`_tamano`, `_banderas`, `_entero`, `_carpeta`: lo que se valida antes de pedir."""

    def test_sin_tamano_no_va_la_bandera(self):
        self.assertEqual(t._tamano(None), [])

    def test_el_tamano_es_un_porcentaje(self):
        self.assertEqual(t._tamano(30), ["-l", "30%"])
        self.assertEqual(t._tamano(1), ["-l", "1%"])
        self.assertEqual(t._tamano(100), ["-l", "100%"])

    def test_un_tamano_fuera_de_rango_se_dice(self):
        for malo in (0, -1, 101, 1000):
            with self.subTest(tamano=malo), self.assertRaises(ErrorDeMux):
                t._tamano(malo)

    def test_un_tamano_que_no_es_entero_se_dice(self):
        for malo in (30.0, "30", True):
            with self.subTest(tamano=malo), self.assertRaises(ErrorDeMux):
                t._tamano(malo)

    def test_cada_direccion_tiene_sus_banderas(self):
        self.assertEqual(t._banderas("derecha"), ("-h",))
        self.assertEqual(t._banderas("izquierda"), ("-h", "-b"))
        self.assertEqual(t._banderas("abajo"), ("-v",))
        self.assertEqual(t._banderas("arriba"), ("-v", "-b"))

    def test_una_direccion_que_no_existe_dice_cuales_hay(self):
        with self.assertRaises(ErrorDeMux) as e:
            t._banderas("diagonal")
        self.assertIn("derecha", str(e.exception))

    def test_un_numero_que_no_es_numero_dice_que_campo_era(self):
        self.assertEqual(t._entero("3", "el índice del tab"), 3)
        with self.assertRaises(ErrorDeMux) as e:
            t._entero("dos", "el índice del tab")
        self.assertIn("el índice del tab", str(e.exception))

    def test_sin_carpeta_no_va_la_bandera(self):
        self.assertEqual(t._carpeta(None), [])

    def test_una_carpeta_que_esta_va_con_su_ruta(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(t._carpeta(Path(d)), ["-c", d])

    def test_una_carpeta_que_no_esta_se_dice_antes_de_pedirsela_a_tmux(self):
        with self.assertRaises(NoExiste):
            t._carpeta(Path(tempfile.gettempdir()) / "telar-no-existe-jamas")

    def test_la_virgulilla_se_expande(self):
        with self.assertRaises(NoExiste) as e:
            t._carpeta(Path("~/telar-no-existe-jamas"))
        self.assertNotIn("~", str(e.exception))


class LeerLoQueContesta(Prueba):
    """`_tab` y `_pane_desde`: el recuento de campos es el que dice si la fila sirve."""

    def test_un_tab_completo_se_lee_entero(self):
        tab = mux()._tab(fila_tab(ident="@3", indice="2", nombre="faro", activo="1", paneles="4"))
        self.assertEqual(tab.id, "@3")
        self.assertEqual(tab.posicion, 2)
        self.assertEqual(tab.nombre, "faro")
        self.assertTrue(tab.activo)
        self.assertEqual(tab.paneles, 4)

    def test_el_tab_que_no_esta_activo_lo_dice(self):
        self.assertFalse(mux()._tab(fila_tab(activo="0")).activo)

    def test_un_nombre_con_espacios_sigue_siendo_un_campo(self):
        # Es todo el motivo de partir por \x1f y no por espacios ni tabuladores.
        tab = mux()._tab(fila_tab(nombre="el faro de la punta"))
        self.assertEqual(tab.nombre, "el faro de la punta")

    def test_un_nombre_con_tabulador_tampoco_parte_la_fila(self):
        self.assertEqual(mux()._tab(fila_tab(nombre="faro\tviejo")).nombre, "faro\tviejo")

    def test_faltando_un_campo_es_un_error_no_un_renglon_que_se_adivina(self):
        corta = t.SEP.join(["@3", "2", "faro", "1"])
        with self.assertRaises(ErrorDeMux) as e:
            mux()._tab(corta)
        self.assertIn("4", str(e.exception))
        self.assertIn(str(len(t.CAMPOS_TAB)), str(e.exception))

    def test_sobrando_un_campo_tambien(self):
        larga = fila_tab() + t.SEP + "extra"
        with self.assertRaises(ErrorDeMux):
            mux()._tab(larga)

    def test_un_indice_que_no_es_numero_se_dice(self):
        with self.assertRaises(ErrorDeMux):
            mux()._tab(fila_tab(indice="segundo"))

    def test_una_cuenta_de_paneles_que_no_es_numero_se_dice(self):
        with self.assertRaises(ErrorDeMux):
            mux()._tab(fila_tab(paneles="muchos"))

    def test_un_panel_completo_se_lee_entero(self):
        pane = mux()._pane_desde(fila_pane(comando="claude", ruta="/taller/faro"))
        self.assertEqual(pane.id, "%7")
        self.assertEqual(pane.tab, "@3")
        self.assertEqual(pane.titulo, "ficha")
        self.assertEqual(pane.comando, "claude")
        self.assertEqual(pane.ruta, Path("/taller/faro"))
        self.assertTrue(pane.foco)
        self.assertTrue(pane.vivo)

    def test_un_panel_sin_ruta_no_inventa_una(self):
        self.assertIsNone(mux()._pane_desde(fila_pane(ruta="")).ruta)

    def test_un_panel_terminado_lo_dice(self):
        pane = mux()._pane_desde(fila_pane(muerto="1"))
        self.assertTrue(pane.terminado)
        self.assertFalse(pane.vivo)

    def test_en_tmux_ningun_panel_es_flotante(self):
        self.assertFalse(mux()._pane_desde(fila_pane()).flotante)

    def test_un_panel_con_campos_de_menos_o_de_mas_es_un_error(self):
        with self.assertRaises(ErrorDeMux):
            mux()._pane_desde(t.SEP.join(["%7", "@3", "ficha", "sh", "/taller", "1"]))
        with self.assertRaises(ErrorDeMux):
            mux()._pane_desde(fila_pane() + t.SEP + "extra")

    def test_un_titulo_vacio_no_corre_los_campos(self):
        pane = mux()._pane_desde(fila_pane(titulo="", comando="sh"))
        self.assertEqual(pane.titulo, "")
        self.assertEqual(pane.comando, "sh")


class Apuntar(Prueba):
    """`_objetivo_tab`: `@3` es un id, `3` un índice, lo demás un nombre exacto."""

    def test_un_id_va_tal_cual(self):
        self.assertEqual(mux()._objetivo_tab("@3"), "@3")

    def test_un_numero_es_el_indice_de_la_sesion(self):
        self.assertEqual(mux()._objetivo_tab("3"), "=taller:3")

    def test_cualquier_otra_cosa_es_un_nombre_exacto(self):
        # El `=` de adelante es el candado: sin él, `trabajo` también calza con
        # `trabajo-viejo` y uno termina cerrando el tab de al lado.
        self.assertEqual(mux()._objetivo_tab("trabajo"), "=taller:=trabajo")

    def test_los_espacios_de_los_bordes_no_cuentan(self):
        self.assertEqual(mux()._objetivo_tab("  @3  "), "@3")

    def test_no_nombrar_ningun_tab_se_dice(self):
        for vacio in ("", "   "):
            with self.subTest(tab=vacio), self.assertRaises(NoExiste):
                mux()._objetivo_tab(vacio)

    def test_un_panel_va_tal_cual_pero_no_puede_estar_vacio(self):
        self.assertEqual(mux()._objetivo_pane(" %7 "), "%7")
        with self.assertRaises(NoExiste):
            mux()._objetivo_pane("")

    def test_la_sesion_entera_lleva_los_dos_puntos(self):
        self.assertEqual(mux()._objetivo_sesion, "=taller:")


class TraducirLaQueja(Prueba):
    """`_queja`: cada cosa que dice tmux se vuelve el error que corresponde."""

    def test_sin_servidor_es_que_la_sesion_no_esta_tejida(self):
        error = mux()._queja(("list-windows",), "no server running on /tmp/tmux-1000/default")
        self.assertIsInstance(error, SinSesion)

    def test_una_sesion_que_no_existe_es_sin_sesion_no_no_existe(self):
        for dijo in ("can't find session: taller", "session not found: taller"):
            with self.subTest(dijo=dijo):
                self.assertIsInstance(mux()._queja(("list-windows",), dijo), SinSesion)

    def test_un_tab_que_no_existe_es_no_existe(self):
        error = mux()._queja(("kill-window", "-t", "@9"), "can't find window: @9")
        self.assertIsInstance(error, NoExiste)
        self.assertNotIsInstance(error, SinSesion)

    def test_cualquier_otra_cosa_es_un_error_de_mux_con_lo_que_dijo(self):
        error = mux()._queja(("move-pane", "-s", "%7"), "no space for new pane")
        self.assertIs(type(error), ErrorDeMux)
        self.assertIn("no space for new pane", str(error))

    def test_el_error_dice_que_se_le_pidio(self):
        error = mux()._queja(("kill-window", "-t", "@9"), "algo se rompió")
        self.assertIn("kill-window -t @9", str(error))

    def test_de_varios_renglones_se_queda_con_el_ultimo_util(self):
        error = mux()._queja(("x",), "ambiguous option\n\ncan't find window: @9\n\n")
        self.assertIsInstance(error, NoExiste)

    def test_sin_detalle_igual_se_dice_algo(self):
        self.assertIn("sin detalle", str(mux()._queja(("x",), "")))


class SinElPrograma(Prueba):
    """Que tmux no esté, o no conteste, se dice; no se cuelga ni se cae de cualquier modo."""

    NOMBRE_IMPOSIBLE = "tmux-que-no-existe-en-ninguna-parte"

    def test_sin_tmux_instalado_no_se_intenta_nada(self):
        with mock.patch.object(t, "PROGRAMA", self.NOMBRE_IMPOSIBLE):
            m = mux()
            self.assertFalse(m.disponible())
            self.assertFalse(m.viva())
            with self.assertRaises(SinPrograma):
                m.tejer()
            with self.assertRaises(SinPrograma):
                m._tmux("list-windows")

    def test_una_pregunta_de_si_o_no_no_levanta_excepcion(self):
        with mock.patch.object(t, "PROGRAMA", self.NOMBRE_IMPOSIBLE):
            self.assertFalse(mux()._ok("has-session", "-t", "=taller"))

    def test_si_tmux_no_contesta_se_dice_en_vez_de_esperar_para_siempre(self):
        falla = subprocess.TimeoutExpired(cmd=[t.PROGRAMA], timeout=t.TIEMPO_LIMITE)
        with mock.patch("subprocess.run", side_effect=falla):
            with self.assertRaises(ErrorDeMux) as e:
                mux()._tmux("list-windows", "-t", "=taller")
        self.assertIn("list-windows -t =taller", str(e.exception))

    def test_tolerante_se_traga_el_error_y_devuelve_vacio(self):
        with mock.patch.object(t, "PROGRAMA", self.NOMBRE_IMPOSIBLE):
            # ni siquiera `tolerante` inventa un tmux: si el programa no está, se dice.
            with self.assertRaises(SinPrograma):
                mux()._tmux("list-clients", tolerante=True)


class ElMultiplexorPorDefecto(Prueba):
    """tmux es lo que telar usa si nadie dijo otra cosa; eso también se prueba."""

    def test_es_el_valor_por_defecto_de_la_configuracion(self):
        self.assertEqual(Config().multiplexor, "tmux")

    def test_esta_registrado_y_la_fabrica_lo_construye(self):
        self.assertIn("tmux", IMPLEMENTACIONES)
        self.assertIsInstance(obtener(Config()), t.Tmux)

    def test_construir_le_pasa_la_configuracion(self):
        config = Config(sesion="otra")
        armado = t.construir(config)
        self.assertIsInstance(armado, t.Tmux)
        self.assertEqual(armado.sesion, "otra")
        self.assertIs(armado.config, config)

    def test_se_llama_tmux_y_cumple_el_protocolo(self):
        self.assertEqual(t.Tmux.nombre, "tmux")
        self.assertIsInstance(mux(), Multiplexor)


# ── capa 2: la forma de las órdenes ──────────────────────────────────────────────


class TmuxFalso(t.Tmux):
    """Un tmux de mentira: anota lo que se le pidió y contesta lo enlatado.

    Sirve para mirar la forma exacta de la orden —qué banderas, en qué orden, contra
    qué objetivo— sin depender de que la máquina tenga tmux. Lo que de verdad hace
    tmux con esa orden lo prueba la capa de integración, más abajo.
    """

    def __init__(self, sesion="taller", *, viva=True, respuestas=None):
        super().__init__(Config(sesion=sesion))
        self.llamadas: list[list[str]] = []
        self.viva_falsa = viva
        self.respuestas: dict[str, str] = {
            "display-message": fila_pane(),
            "new-window": fila_tab(),
            "new-session": fila_tab(),
            "split-window": "%9\n",
            "break-pane": "%7\n",
            **(respuestas or {}),
        }

    def disponible(self) -> bool:
        return True

    def _tmux(self, *args: str, tolerante: bool = False, entorno=None) -> str:
        self.llamadas.append(list(args))
        return self.respuestas.get(args[0], "")

    def _ok(self, *args: str) -> bool:
        self.llamadas.append(list(args))
        return self.viva_falsa

    def ordenes(self, nombre: str) -> list[list[str]]:
        return [ll for ll in self.llamadas if ll and ll[0] == nombre]

    def una(self, nombre: str) -> list[str]:
        ordenes = self.ordenes(nombre)
        assert len(ordenes) == 1, f"se esperaba un solo «{nombre}», hubo {len(ordenes)}"
        return ordenes[0]


class TejerLaSesion(Prueba):
    def test_viva_pregunta_por_la_sesion_exacta(self):
        m = TmuxFalso()
        self.assertTrue(m.viva())
        self.assertEqual(m.una("has-session"), ["has-session", "-t", "=taller"])

    def test_tejer_una_sesion_que_ya_esta_no_toca_nada(self):
        m = TmuxFalso(viva=True)
        m.tejer()
        self.assertEqual(m.ordenes("new-session"), [])

    def test_tejer_una_sesion_que_no_esta_la_levanta_sin_cliente(self):
        m = TmuxFalso(viva=False)
        m.tejer()
        orden = m.una("new-session")
        self.assertEqual(orden[:4], ["new-session", "-d", "-s", "taller"])


class ApuntarAlTabQueSeNombro(Prueba):
    def test_cerrar_por_id_por_indice_y_por_nombre(self):
        casos = {"@3": "@3", "3": "=taller:3", "faro": "=taller:=faro"}
        for nombrado, objetivo in casos.items():
            with self.subTest(tab=nombrado):
                m = TmuxFalso()
                m.cerrar_tab(nombrado)
                self.assertEqual(m.una("kill-window"), ["kill-window", "-t", objetivo])

    def test_renombrar_siempre_apunta_al_tab_y_no_al_foco(self):
        m = TmuxFalso()
        m.renombrar_tab("faro", "molino")
        self.assertEqual(
            m.una("rename-window"), ["rename-window", "-t", "=taller:=faro", "molino"]
        )

    def test_un_tab_sin_nombre_no_se_acepta(self):
        m = TmuxFalso()
        with self.assertRaises(ErrorDeMux):
            m.renombrar_tab("@3", "   ")
        self.assertEqual(m.ordenes("rename-window"), [])

    def test_los_tabs_se_piden_con_el_formato_de_campos(self):
        m = TmuxFalso(respuestas={"list-windows": fila_tab() + "\n" + fila_tab(ident="@4")})
        tabs = m.tabs()
        self.assertEqual([x.id for x in tabs], ["@3", "@4"])
        self.assertIn(t.FORMATO_TAB, m.una("list-windows"))

    def test_un_renglon_en_blanco_no_es_un_tab(self):
        m = TmuxFalso(respuestas={"list-windows": fila_tab() + "\n\n"})
        self.assertEqual(len(m.tabs()), 1)

    def test_sin_tab_activo_se_devuelve_none_en_vez_de_inventarlo(self):
        # Con la sesión sin tejer, `display-message` contesta los campos vacíos.
        vacio = t.SEP * (len(t.CAMPOS_TAB) - 1)
        m = TmuxFalso(respuestas={"display-message": vacio})
        self.assertIsNone(m.tab_activo())


class CambiarDeTab(Prueba):
    def _con_tmux(self, valor="/dev/ttys004"):
        """Como si el comando saliera de adentro de tmux: hay un cliente al que apuntar."""
        previo = os.environ.get("TMUX")
        os.environ["TMUX"] = "/tmp/tmux-1000/default,1234,0"

        def restaurar():
            if previo is None:
                os.environ.pop("TMUX", None)
            else:
                os.environ["TMUX"] = previo

        self.addCleanup(restaurar)
        return TmuxFalso(respuestas={"display-message": valor + "\n"})

    def test_se_mueve_la_sesion_y_tambien_el_cliente_que_pregunto(self):
        m = self._con_tmux("/dev/ttys004")
        m.ir_a_tab("@3")
        self.assertEqual(m.una("select-window"), ["select-window", "-t", "@3"])
        self.assertEqual(
            m.una("switch-client"), ["switch-client", "-c", "/dev/ttys004", "-t", "@3"]
        )

    def test_sin_nadie_mirando_alcanza_con_mover_la_sesion(self):
        m = TmuxFalso(respuestas={"display-message": "", "list-clients": ""})
        os.environ.pop("TMUX", None)
        m.ir_a_tab("faro")
        self.assertEqual(m.una("select-window"), ["select-window", "-t", "=taller:=faro"])
        self.assertEqual(m.ordenes("switch-client"), [])

    def test_desde_afuera_se_busca_un_cliente_de_esta_sesion_y_no_de_otra(self):
        os.environ.pop("TMUX", None)
        clientes = "\n".join(
            [
                t.SEP.join(["/dev/ttys001", "otra"]),
                t.SEP.join(["/dev/ttys002", "taller"]),
            ]
        )
        m = TmuxFalso(respuestas={"list-clients": clientes})
        m.ir_a_tab("@3")
        self.assertEqual(m.una("switch-client")[2], "/dev/ttys002")


class Escribir(Prueba):
    def test_el_texto_va_literal_y_detras_de_un_doble_guion(self):
        m = TmuxFalso()
        m.escribir_pane("%7", "Veamos T84")
        # `-l` es lo que impide que la palabra «Enter» de un texto se vuelva un ↩.
        self.assertEqual(
            m.una("send-keys"), ["send-keys", "-t", "%7", "-l", "--", "Veamos T84"]
        )

    def test_por_defecto_no_se_envia(self):
        m = TmuxFalso()
        m.escribir_pane("%7", "hola")
        self.assertEqual(len(m.ordenes("send-keys")), 1)

    def test_enviar_agrega_el_retorno_despues_del_texto(self):
        m = TmuxFalso()
        m.escribir_pane("%7", "hola", enviar=True)
        self.assertEqual(m.ordenes("send-keys")[-1], ["send-keys", "-t", "%7", "Enter"])

    def test_enviar_sin_texto_es_solo_el_retorno(self):
        m = TmuxFalso()
        m.escribir_pane("%7", "", enviar=True)
        self.assertEqual(m.ordenes("send-keys"), [["send-keys", "-t", "%7", "Enter"]])

    def test_un_texto_que_empieza_con_guion_no_se_lee_como_bandera(self):
        m = TmuxFalso()
        m.escribir_pane("%7", "--version")
        self.assertEqual(m.una("send-keys")[-2:], ["--", "--version"])

    def test_un_salto_sin_enviar_se_dice_en_vez_de_ejecutarse(self):
        for texto in ("dos\nlineas", "con\rretorno"):
            with self.subTest(texto=texto):
                m = TmuxFalso()
                with self.assertRaises(ErrorDeMux):
                    m.escribir_pane("%7", texto)
                self.assertEqual(m.ordenes("send-keys"), [])

    def test_con_enviar_el_texto_entero_si_puede_llevar_saltos(self):
        m = TmuxFalso()
        m.escribir_pane("%7", "dos\nlineas", enviar=True)
        self.assertEqual(m.ordenes("send-keys")[0][-1], "dos\nlineas")


class AbrirUnPanel(Prueba):
    def test_junto_a_otro_panel_con_su_direccion_y_su_tamano(self):
        m = TmuxFalso()
        with tempfile.TemporaryDirectory() as d:
            m.abrir_pane(["sh"], junto_a="%2", direccion="izquierda", tamano=30, ruta=Path(d))
            orden = m.una("split-window")
            self.assertEqual(orden[:6], ["split-window", "-t", "%2", "-P", "-F", "#{pane_id}"])
            self.assertIn("-b", orden)
            self.assertEqual(orden[orden.index("-l") + 1], "30%")
            self.assertEqual(orden[orden.index("-c") + 1], d)

    def test_sin_junto_a_se_parte_el_panel_con_el_foco_de_la_sesion(self):
        m = TmuxFalso()
        m.abrir_pane(["sh"])
        self.assertEqual(m.una("split-window")[2], "=taller:")

    def test_el_comando_va_al_final_como_una_sola_palabra(self):
        m = TmuxFalso()
        m.abrir_pane(["sh", "-c", "echo hola; sleep 1"])
        orden = m.una("split-window")
        self.assertEqual(orden[-2], "--")
        self.assertEqual(orden[-1], "sh -c 'echo hola; sleep 1'")

    def test_sin_foco_va_la_bandera_de_quedarse_donde_se_estaba(self):
        m = TmuxFalso()
        m.abrir_pane(["sh"], foco=False)
        self.assertIn("-d", m.una("split-window"))

    def test_el_titulo_se_pone_aparte_sobre_el_panel_recien_abierto(self):
        m = TmuxFalso()
        m.abrir_pane(["sh"], titulo="ficha")
        self.assertEqual(m.una("select-pane"), ["select-pane", "-t", "%9", "-T", "ficha"])

    def test_reemplazar_no_parte_nada_y_mata_lo_que_corria(self):
        m = TmuxFalso()
        m.abrir_pane(["agente"], reemplaza="%2")
        self.assertEqual(m.ordenes("split-window"), [])
        orden = m.una("respawn-pane")
        self.assertEqual(orden[:4], ["respawn-pane", "-k", "-t", "%2"])
        self.assertEqual(orden[-2:], ["--", "agente"])

    def test_junto_a_y_reemplaza_a_la_vez_no_se_acepta(self):
        m = TmuxFalso()
        with self.assertRaises(ErrorDeMux):
            m.abrir_pane(["sh"], junto_a="%2", reemplaza="%3")
        self.assertEqual(m.llamadas, [])

    def test_si_tmux_no_dice_que_panel_abrio_se_dice(self):
        m = TmuxFalso(respuestas={"split-window": "\n"})
        with self.assertRaises(ErrorDeMux):
            m.abrir_pane(["sh"])

    def test_si_despues_no_sabe_describirlo_tampoco_se_inventa(self):
        m = TmuxFalso(respuestas={"display-message": ""})
        with self.assertRaises(NoExiste):
            m.abrir_pane(["sh"])


class MoverUnPanel(Prueba):
    def test_sin_destino_se_lo_saca_a_un_tab_propio(self):
        m = TmuxFalso()
        m.mover_pane("%7", nombre="ficha", foco=False)
        orden = m.una("break-pane")
        self.assertEqual(orden[:6], ["break-pane", "-s", "%7", "-P", "-F", "#{pane_id}"])
        self.assertEqual(orden[orden.index("-n") + 1], "ficha")
        self.assertIn("-d", orden)
        self.assertEqual(m.ordenes("move-pane"), [])

    def test_a_un_tab_se_usa_el_objetivo_del_tab(self):
        m = TmuxFalso()
        m.mover_pane("%7", tab="molino", direccion="abajo")
        orden = m.una("move-pane")
        self.assertEqual(orden[:5], ["move-pane", "-s", "%7", "-t", "=taller:=molino"])
        self.assertIn("-v", orden)
        self.assertEqual(m.ordenes("break-pane"), [])

    def test_junto_a_otro_panel_se_usa_el_panel(self):
        m = TmuxFalso()
        m.mover_pane("%7", junto_a="%2", tamano=40)
        orden = m.una("move-pane")
        self.assertEqual(orden[4], "%2")
        self.assertEqual(orden[orden.index("-l") + 1], "40%")

    def test_el_panel_se_muda_con_su_identidad_puesta(self):
        m = TmuxFalso()
        self.assertEqual(m.mover_pane("%7", tab="molino").id, "%7")


# ── capa 3: contra un tmux de verdad ─────────────────────────────────────────────

TIENE_TMUX = shutil.which("tmux") is not None

#: para que cada prueba trabaje sobre una sesión que nadie más tocó.
CONTADOR = itertools.count()


@unittest.skipUnless(TIENE_TMUX, "no hay tmux instalado en esta máquina")
class ContraUnTmuxDeVerdad(Prueba):
    """Lo mismo, pero hablándole al programa: es la capa que nota un cambio de versión.

    Cada prueba teje su propia sesión y la mata al salir; el servidor entero —que es
    de estas pruebas y de nadie más, por el `TMUX_TMPDIR` de la clase— se mata al final.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.socket = tempfile.mkdtemp(prefix="telar-mux-")
        cls.entorno = {clave: os.environ.get(clave) for clave in ("TMUX_TMPDIR", "TMUX")}
        os.environ["TMUX_TMPDIR"] = cls.socket
        # Si las pruebas corren adentro de tmux, `TMUX` haría que `_cliente` le preguntara
        # al servidor de afuera, que con este TMUX_TMPDIR ni siquiera está a la vista.
        os.environ.pop("TMUX", None)

    @classmethod
    def tearDownClass(cls) -> None:
        subprocess.run(["tmux", "kill-server"], capture_output=True, text=True)
        for clave, valor in cls.entorno.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor
        shutil.rmtree(cls.socket, ignore_errors=True)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.raiz = Path(tempfile.mkdtemp(prefix="telar-raiz-"))
        self.addCleanup(shutil.rmtree, self.raiz, ignore_errors=True)
        self.sesion = f"telar-pruebas-{os.getpid()}-{next(CONTADOR)}"
        self.addCleanup(self._matar_la_sesion)
        self.mux = t.Tmux(Config(sesion=self.sesion, raiz=self.raiz))

    def _matar_la_sesion(self) -> None:
        subprocess.run(
            ["tmux", "kill-session", "-t", f"={self.sesion}"], capture_output=True, text=True
        )

    # ── utilidades ───────────────────────────────────────────────────────────────

    def _esperar(self, condicion, mensaje, limite=8.0):
        """Le da tiempo a que tmux arranque un proceso. Un `sleep` fijo miente en las dos
        direcciones: de más en una máquina suelta, de menos en un CI cargado."""
        fin = time.monotonic() + limite
        while time.monotonic() < fin:
            valor = condicion()
            if valor:
                return valor
            time.sleep(0.05)
        self.fail(mensaje)

    def _pantalla(self, pane: str) -> str:
        hecho = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", pane], capture_output=True, text=True
        )
        return hecho.stdout

    def _tab_con_shell(self, nombre="faro"):
        return self.mux.crear_tab(nombre, ruta=self.raiz, comando=["sh"])

    # ── la sesión ────────────────────────────────────────────────────────────────

    def test_tmux_esta_y_la_sesion_todavia_no(self):
        self.assertTrue(self.mux.disponible())
        self.assertFalse(self.mux.viva())

    def test_tejer_levanta_la_sesion_y_tejerla_de_nuevo_no_la_toca(self):
        self.mux.tejer()
        self.assertTrue(self.mux.viva())
        antes = [x.id for x in self.mux.tabs()]
        self.mux.tejer()
        self.assertEqual([x.id for x in self.mux.tabs()], antes)

    def test_una_sesion_que_no_esta_no_tiene_nada_y_no_es_un_error(self):
        # Con el servidor vivo pero esta sesión sin tejer: el caso que rompía `panes`.
        self.mux.tejer()
        fantasma = t.Tmux(Config(sesion=f"{self.sesion}-fantasma", raiz=self.raiz))
        self.assertFalse(fantasma.viva())
        self.assertEqual(fantasma.tabs(), [])
        self.assertEqual(fantasma.panes(), [])
        self.assertIsNone(fantasma.tab_activo())
        self.assertEqual(fantasma.hilos(), [])

    # ── tabs ─────────────────────────────────────────────────────────────────────

    def test_el_primer_tab_no_deja_un_shell_huerfano_al_lado(self):
        # Tejer y después abrir el tab dejaría una ventana de más en el índice 0.
        creado = self._tab_con_shell("faro")
        self.assertEqual([x.id for x in self.mux.tabs()], [creado.id])
        self.assertEqual(creado.nombre, "faro")

    def test_el_id_que_devuelve_es_con_el_que_despues_se_le_habla(self):
        creado = self._tab_con_shell("faro")
        self.assertTrue(creado.id.startswith("@"))
        self.mux.renombrar_tab(creado.id, "molino")
        self.assertEqual([x.nombre for x in self.mux.tabs()], ["molino"])

    def test_el_indice_se_reparte_de_nuevo_y_el_id_no(self):
        """Por qué la llave es el `@3` y no el índice.

        Al cerrar un tab su índice queda libre, y el próximo tab que se abra se lo
        queda: el «1» que ayer era un tab hoy es otro. El id no se reparte: mientras
        el tab viva, `@2` es ese tab y ningún otro.
        """
        uno = self._tab_con_shell("uno")
        dos = self.mux.crear_tab("dos", ruta=self.raiz, comando=["sh"], foco=False)
        tres = self.mux.crear_tab("tres", ruta=self.raiz, comando=["sh"], foco=False)
        indice_de_dos = {x.id: x.posicion for x in self.mux.tabs()}[dos.id]

        self.mux.cerrar_tab(dos.id)
        cuatro = self.mux.crear_tab("cuatro", ruta=self.raiz, comando=["sh"], foco=False)

        quedan = {x.id: x for x in self.mux.tabs()}
        self.assertEqual(sorted(quedan), sorted([uno.id, tres.id, cuatro.id]))
        self.assertNotIn(dos.id, quedan)
        # el índice que era de «dos» ahora es de otro tab; el id de «tres» sigue siendo suyo.
        self.assertEqual(quedan[cuatro.id].posicion, indice_de_dos)
        self.assertEqual(quedan[tres.id].nombre, "tres")

        self.mux.ir_a_tab(tres.id)
        self.assertEqual(self.mux.tab_activo().nombre, "tres")
        self.mux.ir_a_tab(str(indice_de_dos))
        self.assertEqual(self.mux.tab_activo().nombre, "cuatro")

    def test_un_nombre_con_espacios_vuelve_entero(self):
        nombre = "el faro de la punta"
        creado = self.mux.crear_tab(nombre, ruta=self.raiz, comando=["sh"])
        self.assertEqual(creado.nombre, nombre)
        self.assertEqual([x.nombre for x in self.mux.tabs()], [nombre])
        self.assertEqual(self.mux.tab_activo().nombre, nombre)

    def test_ir_por_id_por_indice_y_por_nombre_exacto(self):
        uno = self._tab_con_shell("uno")
        dos = self.mux.crear_tab("dos", ruta=self.raiz, comando=["sh"], foco=False)

        self.mux.ir_a_tab(dos.id)
        self.assertEqual(self.mux.tab_activo().id, dos.id)

        self.mux.ir_a_tab("uno")
        self.assertEqual(self.mux.tab_activo().id, uno.id)

        posicion = {x.id: x.posicion for x in self.mux.tabs()}[dos.id]
        self.mux.ir_a_tab(str(posicion))
        self.assertEqual(self.mux.tab_activo().id, dos.id)

    def test_un_nombre_no_calza_con_el_del_tab_de_al_lado(self):
        # Sin el `=` del objetivo, «trabajo» calzaría con «trabajo-viejo» por prefijo.
        self._tab_con_shell("trabajo-viejo")
        with self.assertRaises(NoExiste):
            self.mux.ir_a_tab("trabajo")

    def test_lo_que_no_existe_se_dice_en_vez_de_hacerse_a_medias(self):
        self._tab_con_shell("faro")
        for nombrado in ("@99999", "trabajo", "99"):
            with self.subTest(tab=nombrado), self.assertRaises(NoExiste):
                self.mux.cerrar_tab(nombrado)

    def test_cerrar_el_tab_se_lleva_lo_que_tenia_adentro(self):
        uno = self._tab_con_shell("uno")
        self.mux.crear_tab("dos", ruta=self.raiz, comando=["sh"], foco=False)
        self.mux.abrir_pane(["sh"], junto_a=self.mux.pane_de(uno.id).id, ruta=self.raiz)
        self.assertEqual(len(self.mux.panes(uno.id)), 2)

        self.mux.cerrar_tab(uno.id)
        self.assertNotIn(uno.id, [x.id for x in self.mux.tabs()])
        self.assertNotIn(uno.id, [p.tab for p in self.mux.panes()])

    # ── paneles ──────────────────────────────────────────────────────────────────

    def test_el_panel_dice_que_proceso_corre_adentro_no_que_titulo_tiene(self):
        tab = self._tab_con_shell("faro")
        abierto = self.mux.abrir_pane(
            ["cat"], junto_a=self.mux.pane_de(tab.id).id, ruta=self.raiz, titulo="ficha"
        )
        self.assertEqual(abierto.titulo, "ficha")
        self.assertEqual(abierto.tab, tab.id)
        self.assertEqual(abierto.ruta, Path(self.raiz).resolve())
        self.assertFalse(abierto.flotante)  # tmux no tiene paneles flotantes
        self.assertTrue(abierto.vivo)

        self._esperar(
            lambda: self._buscar_pane(abierto.id).comando == "cat",
            "el panel nunca dijo que adentro corre «cat»",
        )

    def _buscar_pane(self, ident):
        for p in self.mux.panes():
            if p.id == ident:
                return p
        self.fail(f"se perdió el panel {ident}")

    def test_los_paneles_de_un_tab_y_los_de_toda_la_sesion(self):
        uno = self._tab_con_shell("uno")
        dos = self.mux.crear_tab("dos", ruta=self.raiz, comando=["sh"], foco=False)
        self.mux.abrir_pane(["sh"], junto_a=self.mux.pane_de(uno.id).id, ruta=self.raiz)

        self.assertEqual(len(self.mux.panes(uno.id)), 2)
        self.assertEqual(len(self.mux.panes(dos.id)), 1)
        self.assertEqual(len(self.mux.panes()), 3)
        self.assertEqual({p.tab for p in self.mux.panes()}, {uno.id, dos.id})

    def test_cerrar_un_panel_deja_el_tab_en_pie(self):
        tab = self._tab_con_shell("faro")
        abierto = self.mux.abrir_pane(["sh"], junto_a=self.mux.pane_de(tab.id).id)
        self.mux.cerrar_pane(abierto.id)
        self.assertEqual(len(self.mux.panes(tab.id)), 1)
        self.assertIn(tab.id, [x.id for x in self.mux.tabs()])

    def test_enfocar_un_panel_de_otro_tab_tambien_cambia_de_tab(self):
        uno = self._tab_con_shell("uno")
        dos = self.mux.crear_tab("dos", ruta=self.raiz, comando=["sh"], foco=False)
        self.assertEqual(self.mux.tab_activo().id, uno.id)

        self.mux.enfocar_pane(self.mux.pane_de(dos.id).id)
        self.assertEqual(self.mux.tab_activo().id, dos.id)
        self.assertEqual(self.mux.pane_activo().tab, dos.id)

    # ── escribir ─────────────────────────────────────────────────────────────────

    def test_escribir_deja_el_texto_puesto_y_no_lo_ejecuta(self):
        tab = self._tab_con_shell("faro")
        pane = self.mux.pane_de(tab.id).id
        marca = self.raiz / "marca.txt"

        self.mux.escribir_pane(pane, f"touch {marca}")
        self._esperar(
            lambda: "touch" in self._pantalla(pane),
            "el texto nunca apareció en el panel",
        )
        self.assertFalse(marca.exists(), "el texto se ejecutó sin que nadie lo enviara")

        self.mux.escribir_pane(pane, "", enviar=True)
        self._esperar(marca.exists, "el ↩ no ejecutó lo que estaba escrito")

    def test_la_palabra_enter_no_se_vuelve_un_retorno(self):
        tab = self._tab_con_shell("faro")
        pane = self.mux.pane_de(tab.id).id
        self.mux.escribir_pane(pane, "Enter")
        self._esperar(
            lambda: "Enter" in self._pantalla(pane),
            "el texto «Enter» nunca apareció; se lo tomó como tecla",
        )

    # ── mover ────────────────────────────────────────────────────────────────────

    def test_mover_un_panel_a_otro_tab_conserva_su_identidad(self):
        uno = self._tab_con_shell("uno")
        dos = self.mux.crear_tab("dos", ruta=self.raiz, comando=["sh"], foco=False)
        abierto = self.mux.abrir_pane(["cat"], junto_a=self.mux.pane_de(uno.id).id)

        movido = self.mux.mover_pane(abierto.id, tab=dos.id)

        self.assertEqual(movido.id, abierto.id)
        self.assertEqual(movido.tab, dos.id)
        self.assertEqual(len(self.mux.panes(uno.id)), 1)
        self.assertIn(movido.id, {p.id for p in self.mux.panes(dos.id)})
        self.assertEqual(len(self.mux.panes(dos.id)), 2)

    def test_mover_junto_a_un_panel_concreto(self):
        uno = self._tab_con_shell("uno")
        dos = self.mux.crear_tab("dos", ruta=self.raiz, comando=["sh"], foco=False)
        abierto = self.mux.abrir_pane(["sh"], junto_a=self.mux.pane_de(uno.id).id)

        movido = self.mux.mover_pane(abierto.id, junto_a=self.mux.pane_de(dos.id).id)

        self.assertEqual(movido.id, abierto.id)
        self.assertEqual(movido.tab, dos.id)

    def test_sin_destino_el_panel_se_va_a_un_tab_propio_con_su_nombre(self):
        uno = self._tab_con_shell("uno")
        abierto = self.mux.abrir_pane(["cat"], junto_a=self.mux.pane_de(uno.id).id)

        movido = self.mux.mover_pane(abierto.id, nombre="ficha")

        self.assertEqual(movido.id, abierto.id)
        self.assertNotEqual(movido.tab, uno.id)
        self.assertEqual(len(self.mux.panes(uno.id)), 1)
        nuevos = {x.id: x for x in self.mux.tabs()}
        self.assertEqual(nuevos[movido.tab].nombre, "ficha")
        # break-pane no reinicia lo que corría: el `cat` sigue ahí.
        self._esperar(
            lambda: self._buscar_pane(movido.id).comando == "cat",
            "el proceso no sobrevivió a la mudanza",
        )

    # ── el contrato de arriba, derivado de todo esto ──────────────────────────────

    def test_los_hilos_salen_de_los_tabs_con_la_ruta_de_su_panel(self):
        uno = self.mux.crear_tab("uno", ruta=self.raiz, comando=["sh"])
        hilos = self.mux.hilos()
        self.assertEqual([h.id for h in hilos], [uno.id])
        self.assertEqual(hilos[0].nombre, "uno")
        self.assertEqual(hilos[0].ruta, Path(self.raiz).resolve())
        self.assertTrue(hilos[0].activo)
        self.assertEqual(self.mux.activo().id, uno.id)


class UnTmuxQueDisfrazaElSeparador(Prueba):
    """Hasta 3.4, tmux pasa por `vis()` todo lo que imprime: el 0x1f sale como `\\037`.

    Se descubrió en el CI de Linux, donde las veinte pruebas de integración cayeron con
    «tmux devolvió 1 campos donde iban 5» mientras en macOS —tmux 3.7— pasaban todas.
    """

    @staticmethod
    def _con_salida(texto: str):
        hecho = mock.Mock(returncode=0, stdout=texto, stderr="")
        return mock.patch.object(t.subprocess, "run", return_value=hecho)

    def test_el_separador_en_octal_se_lee_igual_que_el_byte(self):
        escapado = fila_tab(nombre="telar-escribir").replace(t.SEP, t.SEP_EN_OCTAL)
        with self._con_salida(escapado + "\n"):
            tabs = mux().tabs()
        self.assertEqual([(x.id, x.nombre, x.paneles) for x in tabs], [("@3", "telar-escribir", 1)])

    def test_tambien_un_panel(self):
        escapado = fila_pane(comando="claude").replace(t.SEP, t.SEP_EN_OCTAL)
        with self._con_salida(escapado + "\n"):
            pane = mux()._pane("%7")
        self.assertEqual(pane.comando, "claude")

    def test_el_nombre_con_acento_vuelve_entero(self):
        # `utf8_stravis` deja pasar el UTF-8 válido; solo disfraza los de control.
        escapado = fila_tab(nombre="reunión").replace(t.SEP, t.SEP_EN_OCTAL)
        with self._con_salida(escapado + "\n"):
            self.assertEqual(mux().tabs()[0].nombre, "reunión")

    def test_si_el_byte_de_verdad_vino_no_se_toca_nada(self):
        # Un tmux nuevo no disfraza: entonces esos cuatro caracteres son un nombre.
        with self._con_salida(fila_tab(nombre=r"raro\037raro") + "\n"):
            self.assertEqual(mux().tabs()[0].nombre, r"raro\037raro")

    def test_lo_que_no_trae_separador_pasa_derecho(self):
        self.assertEqual(t._descamuflar("tmux 3.4\n"), "tmux 3.4\n")


if __name__ == "__main__":
    unittest.main()
