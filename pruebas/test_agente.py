"""El contrato con el agente: qué queda escrito cuando avisa, y qué no se toca.

Lo que importa aquí no es que un enum tenga seis valores. Es que `sigue` desmienta un
«te espera» y no invente un «empecé»; que el hilo salga del panel y jamás del foco; que
cerrar la sesión borre el semáforo y **no** la conversación —que es justo lo que se va
a querer retomar mañana—; y que instalar los ganchos no le pise a nadie los suyos.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import agente as mod_agente
from telar import config, estado as mod_estado
from telar.agente import Agente, Conversacion, ErrorDeAgente
from telar.agente import base
from telar.agente.base import Aviso, Evento
from telar.agente.claude_code import ClaudeCode
from telar.modelo import Atencion, Hilo


class ConEstado(Prueba):
    """Cada prueba, su carpeta de estado y su carpeta de Claude Code. Nada del disco de nadie."""

    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name)
        self.config = config.Config(raiz=self.carpeta, estado=self.carpeta / "estado")
        self.est = mod_estado.abrir(self.config)
        self._claude = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.carpeta / "claude")
        self.addCleanup(self._devolver_claude)

    def _devolver_claude(self) -> None:
        if self._claude is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self._claude

    def agente(self) -> ClaudeCode:
        return ClaudeCode(self.config)


# ── la traducción, que es todo el cálculo ───────────────────────────────────────


class Traduccion(unittest.TestCase):
    def test_cada_evento_deja_su_atencion(self):
        self.assertIs(base.atencion_de(Evento.EMPIEZA), Atencion.TRABAJANDO)
        self.assertIs(base.atencion_de(Evento.ESPERA), Atencion.ESPERA)
        self.assertIs(base.atencion_de(Evento.TERMINA), Atencion.TERMINO)

    def test_lo_mismo_dos_veces_no_se_escribe(self):
        # del otro lado hay una barra vigilando el archivo
        self.assertIsNone(base.atencion_de(Evento.EMPIEZA, Atencion.TRABAJANDO))
        self.assertIsNone(base.atencion_de(Evento.ESPERA, Atencion.ESPERA))

    def test_sigue_desmiente_la_espera_y_nada_mas(self):
        self.assertIs(base.atencion_de(Evento.SIGUE, Atencion.ESPERA), Atencion.TRABAJANDO)
        self.assertIsNone(base.atencion_de(Evento.SIGUE, Atencion.TRABAJANDO))
        self.assertIsNone(base.atencion_de(Evento.SIGUE, Atencion.NINGUNA))
        self.assertIsNone(base.atencion_de(Evento.SIGUE, Atencion.TERMINO))

    def test_abrir_no_habla_de_atencion(self):
        self.assertIsNone(base.atencion_de(Evento.ABRE, Atencion.TRABAJANDO))

    def test_cerrar_borra_lo_que_haya_y_nada_si_no_hay(self):
        self.assertIs(base.atencion_de(Evento.CIERRA, Atencion.TRABAJANDO), Atencion.NINGUNA)
        self.assertIsNone(base.atencion_de(Evento.CIERRA, Atencion.NINGUNA))

    def test_el_panel_sale_del_entorno_de_cada_multiplexor(self):
        self.assertEqual(base.panel_del_entorno("zellij", {"ZELLIJ_PANE_ID": "7"}), "terminal_7")
        self.assertEqual(base.panel_del_entorno("tmux", {"TMUX_PANE": "%3"}), "%3")
        self.assertEqual(base.panel_del_entorno("zellij", {}), "")
        # lo explícito manda sobre lo que exporte el multiplexor
        self.assertEqual(
            base.panel_del_entorno("zellij", {"ZELLIJ_PANE_ID": "7", "TELAR_PANEL": "p9"}), "p9"
        )


# ── aplicar: lo que queda escrito ───────────────────────────────────────────────


class Aplicar(ConEstado):
    def test_abrir_anota_la_conversacion_en_el_hilo(self):
        aviso = Aviso(evento=Evento.ABRE, sesion="s1", panel="terminal_3")
        efecto = base.aplicar(self.est, aviso, hilo="faro")
        self.assertEqual(efecto.anotada, "s1")
        self.assertEqual(self.est.hilo_de("s1"), "faro")
        self.assertEqual(self.est.paneles(), {"terminal_3": "s1"})

    def test_abrir_desarchiva(self):
        self.est.archivar("faro")
        base.aplicar(self.est, Aviso(evento=Evento.ABRE, sesion="s1"), hilo="faro")
        self.assertNotIn("faro", self.est.archivados())

    def test_una_conversacion_nueva_en_el_mismo_panel_saca_a_la_anterior(self):
        base.aplicar(self.est, Aviso(evento=Evento.ABRE, sesion="s1", panel="p1"), hilo="faro")
        base.aplicar(self.est, Aviso(evento=Evento.ABRE, sesion="s2", panel="p1"), hilo="faro")
        self.assertEqual(self.est.sesiones()["faro"], ("s2",))

    def test_la_secuencia_de_un_turno(self):
        base.aplicar(self.est, Aviso(evento=Evento.EMPIEZA), hilo="faro")
        self.assertIs(self.est.atencion("faro"), Atencion.TRABAJANDO)
        base.aplicar(self.est, Aviso(evento=Evento.ESPERA), hilo="faro")
        self.assertIs(self.est.atencion("faro"), Atencion.ESPERA)
        base.aplicar(self.est, Aviso(evento=Evento.SIGUE), hilo="faro")
        self.assertIs(self.est.atencion("faro"), Atencion.TRABAJANDO)
        base.aplicar(self.est, Aviso(evento=Evento.TERMINA), hilo="faro")
        self.assertIs(self.est.atencion("faro"), Atencion.TERMINO)

    def test_lo_que_no_cambia_no_se_escribe(self):
        base.aplicar(self.est, Aviso(evento=Evento.EMPIEZA), hilo="faro")
        efecto = base.aplicar(self.est, Aviso(evento=Evento.EMPIEZA), hilo="faro")
        self.assertTrue(efecto.vacio)
        self.assertIsNone(efecto.atencion)

    def test_cerrar_apaga_el_semaforo_y_conserva_la_conversacion(self):
        base.aplicar(self.est, Aviso(evento=Evento.ABRE, sesion="s1", panel="p1"), hilo="faro")
        base.aplicar(self.est, Aviso(evento=Evento.EMPIEZA), hilo="faro")
        base.aplicar(self.est, Aviso(evento=Evento.CIERRA, sesion="s1"), hilo="faro")
        self.assertIs(self.est.atencion("faro"), Atencion.NINGUNA)
        # sigue anotada: es exactamente la que se va a querer retomar
        self.assertEqual(self.est.hilo_de("s1"), "faro")
        self.assertEqual(self.est.paneles(), {"p1": "s1"})

    def test_cerrar_con_olvidar_la_saca_de_todos_lados(self):
        base.aplicar(self.est, Aviso(evento=Evento.ABRE, sesion="s1", panel="p1"), hilo="faro")
        base.aplicar(
            self.est, Aviso(evento=Evento.CIERRA, sesion="s1"), hilo="faro", olvidar_al_cerrar=True
        )
        self.assertEqual(self.est.hilo_de("s1"), "")
        self.assertEqual(self.est.paneles(), {})

    def test_sin_hilo_no_se_inventa_nada(self):
        with self.assertRaises(ErrorDeAgente):
            base.aplicar(self.est, Aviso(evento=Evento.EMPIEZA), hilo="")


# ── resolver el hilo: el orden es la lección ────────────────────────────────────


class MuxFalso:
    """Un multiplexor de mentira: un panel, un tab, y un foco puesto en otra parte."""

    def __init__(self) -> None:
        self.preguntas = 0

    def hilos(self):
        return [Hilo(id="3", nombre="faro"), Hilo(id="4", nombre="molino", activo=True)]

    def paneles(self):
        self.preguntas += 1
        return [{"id": 7, "tab_id": 3, "tab_name": "faro"}]

    def activo(self):
        return Hilo(id="4", nombre="molino", activo=True)


class Resolver(ConEstado):
    def test_lo_pedido_a_mano_manda(self):
        aviso = Aviso(evento=Evento.EMPIEZA, hilo="dicho")
        self.assertEqual(base.resolver_hilo(self.est, aviso, entorno={"TELAR_HILO": "otro"}), "dicho")

    def test_despues_la_variable_del_tab(self):
        aviso = Aviso(evento=Evento.EMPIEZA, sesion="s1")
        self.est.anotar_sesion("molino", "s1")
        self.assertEqual(
            base.resolver_hilo(self.est, aviso, entorno={"TELAR_HILO": "faro"}), "faro"
        )

    def test_sin_variable_sirve_la_conversacion_anotada(self):
        self.est.anotar_sesion("faro", "s1")
        aviso = Aviso(evento=Evento.EMPIEZA, sesion="s1")
        self.assertEqual(base.resolver_hilo(self.est, aviso, entorno={}), "faro")

    def test_al_abrir_gana_el_panel_aunque_la_conversacion_estuviera_en_otro_tab(self):
        # una conversación que se retoma en otro tab se muda con él: eso lo dice el panel
        self.est.anotar_sesion("molino", "s1")
        aviso = Aviso(evento=Evento.ABRE, sesion="s1", panel="terminal_7")
        hilo = base.resolver_hilo(self.est, aviso, mux=MuxFalso(), entorno={})
        self.assertEqual(hilo, "faro")

    def test_nunca_el_foco(self):
        # el mux tiene «molino» activo; sin panel ni nada anotado, se prefiere no saber
        mux = MuxFalso()
        aviso = Aviso(evento=Evento.EMPIEZA, sesion="s9")
        self.assertEqual(base.resolver_hilo(self.est, aviso, mux=mux, entorno={}), "")

    def test_el_panel_de_un_zellij_se_reconoce_con_y_sin_prefijo(self):
        self.assertEqual(base.hilo_del_panel(MuxFalso(), "terminal_7"), "faro")
        self.assertEqual(base.hilo_del_panel(MuxFalso(), "7"), "faro")
        self.assertEqual(base.hilo_del_panel(MuxFalso(), "terminal_9"), "")

    def test_un_multiplexor_que_revienta_no_tumba_el_gancho(self):
        class Roto:
            def hilos(self):
                raise RuntimeError("zellij no está")

        self.assertEqual(base.hilo_del_panel(Roto(), "terminal_7"), "")


# ── el adaptador de Claude Code ─────────────────────────────────────────────────


class Adaptador(ConEstado):
    def test_cumple_el_protocolo(self):
        self.assertIsInstance(self.agente(), Agente)

    def test_se_reconoce_por_el_proceso_no_por_el_titulo(self):
        a = self.agente()
        self.assertTrue(a.corriendo("claude"))
        self.assertTrue(a.corriendo("node /opt/homebrew/bin/claude --resume x"))
        self.assertFalse(a.corriendo("vim README.md"))
        self.assertFalse(a.corriendo(""))

    def test_traduce_los_momentos_de_claude_code(self):
        a = self.agente()
        aviso = a.leer_aviso(
            {
                "hook_event_name": "Notification",
                "session_id": "abc",
                "cwd": "/tmp/faro",
                "transcript_path": "/tmp/abc.jsonl",
            }
        )
        self.assertIs(aviso.evento, Evento.ESPERA)
        self.assertEqual(aviso.sesion, "abc")
        self.assertEqual(aviso.ruta, Path("/tmp/faro"))
        self.assertEqual(aviso.agente, "claude-code")

    def test_un_momento_desconocido_se_dice_en_voz_alta(self):
        with self.assertRaises(ErrorDeAgente):
            self.agente().leer_aviso({"hook_event_name": "AlgoNuevo"})

    def test_el_evento_se_puede_forzar(self):
        aviso = self.agente().leer_aviso({"session_id": "x"}, evento=Evento.TERMINA)
        self.assertIs(aviso.evento, Evento.TERMINA)

    def test_los_comandos_se_devuelven_sin_correrlos(self):
        a = self.agente()
        self.assertEqual(a.retomar(Conversacion("abc")), ["claude", "--resume", "abc"])
        self.assertEqual(a.nuevo(), ["claude"])
        with self.assertRaises(ErrorDeAgente):
            a.retomar(Conversacion(""))

    def test_la_conversacion_se_busca_por_nombre_no_por_receta(self):
        proyectos = self.carpeta / "claude" / "projects" / "-tmp-faro"
        proyectos.mkdir(parents=True)
        (proyectos / "abc.jsonl").write_text("{}\n", encoding="utf-8")
        a = self.agente()
        self.assertEqual(a.archivo_de("abc"), proyectos / "abc.jsonl")
        self.assertIsNone(a.archivo_de("no-existe"))

    def test_las_conversaciones_del_hilo_salen_del_estado(self):
        self.est.anotar_sesion("faro", "s1")
        conversaciones = self.agente().conversaciones("faro")
        self.assertEqual([c.id for c in conversaciones], ["s1"])
        self.assertEqual(conversaciones[0].hilo, "faro")

    def test_el_registro_lo_trae_por_nombre(self):
        self.assertIsInstance(mod_agente.obtener("claude-code", self.config), ClaudeCode)
        with self.assertRaises(ErrorDeAgente):
            mod_agente.obtener("no-existe", self.config)


# ── el instalador, que escribe en casa ajena ────────────────────────────────────


class Instalador(ConEstado):
    def setUp(self) -> None:
        super().setUp()
        self.ajustes = self.carpeta / "claude" / "settings.json"
        self.ajustes.parent.mkdir(parents=True, exist_ok=True)

    def leer(self) -> dict:
        return json.loads(self.ajustes.read_text(encoding="utf-8"))

    def test_deja_los_seis_ganchos(self):
        hecho = self.agente().instalar(ruta=self.ajustes)
        self.assertTrue(hecho.escrito)
        hooks = self.leer()["hooks"]
        self.assertEqual(
            sorted(hooks),
            ["Notification", "PostToolUse", "SessionEnd", "SessionStart", "Stop", "UserPromptSubmit"],
        )
        comando = hooks["Stop"][0]["hooks"][0]["command"]
        self.assertIn("agente aviso claude-code", comando)
        self.assertEqual(hooks["PostToolUse"][0]["matcher"], "*")

    def test_no_le_pisa_los_ganchos_a_nadie(self):
        ajeno = {"type": "command", "command": "mi-script.sh"}
        self.ajustes.write_text(
            json.dumps({"modelo": "opus", "hooks": {"Stop": [{"hooks": [ajeno]}]}}),
            encoding="utf-8",
        )
        self.agente().instalar(ruta=self.ajustes)
        datos = self.leer()
        self.assertEqual(datos["modelo"], "opus")
        comandos = [g["command"] for e in datos["hooks"]["Stop"] for g in e["hooks"]]
        self.assertIn("mi-script.sh", comandos)
        self.assertEqual(len(comandos), 2)

    def test_instalar_dos_veces_no_duplica(self):
        a = self.agente()
        a.instalar(ruta=self.ajustes)
        hecho = a.instalar(ruta=self.ajustes)
        self.assertIn("Stop", hecho.reemplazados)
        self.assertEqual(len(self.leer()["hooks"]["Stop"][0]["hooks"]), 1)

    def test_deja_un_respaldo_antes_de_tocar_nada(self):
        self.ajustes.write_text(json.dumps({"modelo": "opus"}), encoding="utf-8")
        hecho = self.agente().instalar(ruta=self.ajustes)
        self.assertIsNotNone(hecho.respaldo)
        self.assertEqual(json.loads(hecho.respaldo.read_text(encoding="utf-8")), {"modelo": "opus"})

    def test_un_segundo_respaldo_no_pisa_al_primero(self):
        self.ajustes.write_text(json.dumps({"modelo": "opus"}), encoding="utf-8")
        a = self.agente()
        primero = a.instalar(ruta=self.ajustes).respaldo
        segundo = a.instalar(ruta=self.ajustes).respaldo
        self.assertNotEqual(primero, segundo)
        # el retrato de lo que había antes de telar es el que hay que poder volver a poner
        self.assertEqual(json.loads(primero.read_text(encoding="utf-8")), {"modelo": "opus"})
        self.assertIn("agente aviso claude-code", segundo.read_text(encoding="utf-8"))

    def test_desinstalar_no_se_come_el_respaldo_de_antes(self):
        self.ajustes.write_text(json.dumps({"modelo": "opus"}), encoding="utf-8")
        a = self.agente()
        antes = a.instalar(ruta=self.ajustes).respaldo
        hecho = a.desinstalar(ruta=self.ajustes)
        self.assertNotEqual(hecho.respaldo, antes)
        self.assertEqual(json.loads(antes.read_text(encoding="utf-8")), {"modelo": "opus"})

    def test_el_respaldo_hereda_los_permisos_del_original(self):
        self.ajustes.write_text(json.dumps({"modelo": "opus"}), encoding="utf-8")
        self.ajustes.chmod(0o600)
        hecho = self.agente().instalar(ruta=self.ajustes)
        self.assertEqual(hecho.respaldo.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.ajustes.stat().st_mode & 0o777, 0o600)

    def test_seco_no_escribe(self):
        hecho = self.agente().instalar(ruta=self.ajustes, seco=True)
        self.assertFalse(hecho.escrito)
        self.assertFalse(self.ajustes.exists())
        self.assertIn("SessionStart", hecho.texto)

    def test_desinstalar_saca_lo_nuestro_y_deja_lo_ajeno(self):
        ajeno = {"type": "command", "command": "mi-script.sh"}
        self.ajustes.write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [ajeno]}]}}), encoding="utf-8"
        )
        a = self.agente()
        a.instalar(ruta=self.ajustes)
        hecho = a.desinstalar(ruta=self.ajustes)
        self.assertTrue(hecho.escrito)
        datos = self.leer()
        self.assertEqual(
            [g["command"] for e in datos["hooks"]["Stop"] for g in e["hooks"]], ["mi-script.sh"]
        )
        self.assertNotIn("SessionStart", datos["hooks"])

    def test_desinstalar_sin_nada_puesto_no_escribe(self):
        self.ajustes.write_text(json.dumps({"modelo": "opus"}), encoding="utf-8")
        hecho = self.agente().desinstalar(ruta=self.ajustes)
        self.assertFalse(hecho.escrito)
        self.assertEqual(hecho.reemplazados, ())

    def test_un_json_roto_no_se_pisa(self):
        self.ajustes.write_text("{ esto no es json", encoding="utf-8")
        with self.assertRaises(ErrorDeAgente):
            self.agente().instalar(ruta=self.ajustes)
        self.assertEqual(self.ajustes.read_text(encoding="utf-8"), "{ esto no es json")

    def test_el_comando_se_puede_fijar_a_mano(self):
        self.agente().instalar(ruta=self.ajustes, ejecutable=["/opt/telar/bin/telar"])
        comando = self.leer()["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertEqual(comando, "/opt/telar/bin/telar agente aviso claude-code")


# ── pedir permiso antes de escribir en casa ajena ───────────────────────────────


class _Terminal(io.StringIO):
    """Una entrada estándar que dice ser una terminal, que es lo que habilita preguntar."""

    def isatty(self) -> bool:
        return True


class Permiso(ConEstado):
    """`instalar` toca la configuración de otro programa: no lo hace a espaldas de nadie.

    Un gancho mal puesto no se nota al ponerlo —se nota meses después, en cada evento
    de un agente que llama a un ejecutable que ya no está—, así que aquí se prueba lo
    que evita llegar a eso: que se pregunte, y que un telar de paso no se escriba.
    """

    #: un ejecutable que existe en cualquier máquina donde corra esto y no se va a ir.
    ESTABLE = "/bin/sh"

    def setUp(self) -> None:
        super().setUp()
        self.ajustes = self.carpeta / "claude" / "settings.json"
        self.ajustes.parent.mkdir(parents=True, exist_ok=True)

    def correr(self, argv: list[str], *, responde: str | None = None) -> tuple[int, str]:
        import builtins

        from telar.cli import Contexto
        from telar.ordenes import agente as orden

        viejo, salida = sys.stdin, io.StringIO()
        sys.stdin = _Terminal() if responde is not None else io.StringIO()
        preguntar = builtins.input
        builtins.input = lambda *_: responde or ""
        try:
            sys.stdout, previo = salida, sys.stdout
            try:
                codigo = orden.main(argv, Contexto(config=self.config))
            finally:
                sys.stdout = previo
        finally:
            builtins.input = preguntar
            sys.stdin = viejo
        return codigo, salida.getvalue()

    def instalar(self, *extra: str, responde: str | None = None) -> tuple[int, str]:
        argv = ["instalar", "--ajustes", str(self.ajustes), "--ejecutable", self.ESTABLE, *extra]
        return self.correr(argv, responde=responde)

    def test_sin_nadie_a_quien_preguntarle_no_escribe(self):
        codigo, _ = self.instalar()
        self.assertEqual(codigo, 2)
        self.assertFalse(self.ajustes.exists())

    def test_pregunta_y_un_no_deja_el_archivo_como_estaba(self):
        codigo, texto = self.instalar(responde="n")
        self.assertEqual(codigo, 1)
        self.assertFalse(self.ajustes.exists())
        self.assertIn(str(self.ajustes), texto)  # la ruta se dice ANTES de escribir
        self.assertIn("SessionStart", texto)  # y lo que cambiaría, también

    def test_un_si_escribe(self):
        codigo, _ = self.instalar(responde="s")
        self.assertEqual(codigo, 0)
        self.assertIn("SessionStart", json.loads(self.ajustes.read_text(encoding="utf-8"))["hooks"])

    def test_la_bandera_salta_la_pregunta(self):
        codigo, _ = self.instalar("--si")
        self.assertEqual(codigo, 0)
        self.assertTrue(self.ajustes.exists())

    def test_seco_no_pregunta_ni_escribe(self):
        codigo, texto = self.instalar("--seco")
        self.assertEqual(codigo, 0)
        self.assertFalse(self.ajustes.exists())
        self.assertIn("SessionStart", texto)

    def test_lo_ya_escrito_no_se_vuelve_a_escribir(self):
        self.instalar("--si")
        codigo, _ = self.instalar()  # sin tty: si tuviera algo que escribir, se quejaría
        self.assertEqual(codigo, 0)
        # un segundo paso habría dejado su respaldo al lado; no hay nada que respaldar
        self.assertEqual(list(self.ajustes.parent.glob("*.bak")), [])

    def test_no_deja_ganchos_que_apunten_a_un_telar_de_paso(self):
        pasajero = self.carpeta / "venv" / "bin" / "telar"
        pasajero.parent.mkdir(parents=True, exist_ok=True)
        pasajero.write_text("#!/bin/sh\n", encoding="utf-8")
        argv = ["instalar", "--ajustes", str(self.ajustes), "--ejecutable", str(pasajero)]
        codigo, _ = self.correr([*argv, "--json"])  # ni siquiera --json lo autoriza
        self.assertEqual(codigo, 2)
        self.assertFalse(self.ajustes.exists())
        self.assertEqual(self.correr([*argv, "--si"])[0], 0)  # insistir sí

    def test_tampoco_uno_que_ya_no_existe(self):
        codigo, _ = self.correr(
            ["instalar", "--ajustes", str(self.ajustes), "--ejecutable", "/opt/se-fue/telar"]
        )
        self.assertEqual(codigo, 2)
        self.assertFalse(self.ajustes.exists())


class RutaDelGancho(unittest.TestCase):
    """`ruta_inestable` es quien sabe si un comando va a seguir estando mañana."""

    def test_un_temporal_no_sirve(self):
        with tempfile.TemporaryDirectory() as carpeta:
            binario = Path(carpeta) / "telar"
            binario.write_text("", encoding="utf-8")
            self.assertIn("temporal", base.ruta_inestable([str(binario), "agente", "aviso"]))

    def test_lo_que_no_existe_no_sirve(self):
        self.assertIn("no existe", base.ruta_inestable(["/opt/telar/bin/telar"]))

    def test_un_ejecutable_de_siempre_sirve(self):
        self.assertEqual(base.ruta_inestable(["/bin/sh", "agente", "aviso"]), "")

    def test_sin_nada_que_llamar_lo_dice(self):
        self.assertNotEqual(base.ruta_inestable([]), "")


# ── la orden, que es lo que corre el gancho ─────────────────────────────────────


class Orden(ConEstado):
    def correr(self, argv: list[str], entrada: str = "") -> tuple[int, str]:
        from telar.cli import Contexto
        from telar.ordenes import agente as orden

        viejo, salida = sys.stdin, io.StringIO()
        sys.stdin = io.StringIO(entrada)
        try:
            sys.stdout, previo = salida, sys.stdout
            try:
                codigo = orden.main(argv, Contexto(config=self.config))
            finally:
                sys.stdout = previo
        finally:
            sys.stdin = viejo
        return codigo, salida.getvalue()

    def test_el_aviso_escribe_la_atencion(self):
        os.environ["TELAR_HILO"] = "faro"
        carga = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "s1"})
        codigo, texto = self.correr(["aviso"], carga)
        self.assertEqual(codigo, 0)
        self.assertEqual(texto, "")  # callado: hay agentes que se leen la salida del gancho
        self.assertIs(self.est.atencion("faro"), Atencion.TRABAJANDO)

    def test_el_aviso_anota_la_conversacion_al_abrir(self):
        os.environ["TELAR_HILO"] = "faro"
        carga = json.dumps({"hook_event_name": "SessionStart", "session_id": "s1"})
        self.correr(["aviso", "--panel", "p1"], carga)
        self.assertEqual(self.est.hilo_de("s1"), "faro")

    def test_una_carga_rota_no_es_un_error_para_quien_llamo(self):
        os.environ["TELAR_HILO"] = "faro"
        codigo, texto = self.correr(["aviso"], "esto no es json")
        self.assertEqual(codigo, 0)
        self.assertEqual(texto, "")

    def test_sin_hilo_el_aviso_se_calla_y_no_escribe(self):
        codigo, _ = self.correr(
            ["aviso"], json.dumps({"hook_event_name": "Stop", "session_id": "s9"})
        )
        self.assertEqual(codigo, 0)
        self.assertEqual(self.est.atenciones(), {})

    def test_con_json_se_puede_mirar_lo_que_hizo(self):
        os.environ["TELAR_HILO"] = "faro"
        carga = json.dumps({"hook_event_name": "Stop", "session_id": "s1"})
        _, texto = self.correr(["aviso", "--json"], carga)
        self.assertEqual(json.loads(texto)["atencion"], "termino")

    def test_un_agente_que_telar_no_conoce_avisa_sin_adaptador(self):
        os.environ["TELAR_HILO"] = "faro"
        codigo, _ = self.correr(["aviso", "--evento", "abre", "--sesion", "z9", "--panel", "p1"])
        self.assertEqual(codigo, 0)
        self.assertEqual(self.est.hilo_de("z9"), "faro")
        self.correr(["aviso", "--evento", "espera"])
        self.assertIs(self.est.atencion("faro"), Atencion.ESPERA)

    def test_retomar_imprime_el_comando_y_no_lo_corre(self):
        os.environ["TELAR_HILO"] = "faro"
        self.est.anotar_sesion("faro", "s1")
        codigo, texto = self.correr(["retomar"])
        self.assertEqual(codigo, 0)
        self.assertEqual(texto.strip(), "claude --resume s1")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
