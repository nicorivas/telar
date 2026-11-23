"""Dormir un hilo inactivo (telar.dormir): lo que se lee de su pantalla, las reglas que lo protegen (cada excepción, una
por una), lo que se mira, dormirlo y despertarlo con un multiplexor falso, que un mensaje lo despierte, y todo eso en
un tmux de verdad, en un servidor propio (`TMUX_TMPDIR` aparte, matado con `-S`), con un agente de mentira."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import comun
from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import casilla
from telar import config as mod_config
from telar import dormir
from telar import espejo
from telar import estado as mod_estado
from telar.modelo import Atencion, Hilo

E = "\x1b"
REGLA = "─" * 60
#: la caja de escribir quieta, con la sugerencia de Claude Code (tenue) adentro
QUIETA = (f"{E}[38;5;246m⏺ Listo: lo dejé commiteado.{E}[39m\n\n"
          f"{E}[38;5;244m{REGLA}\n"
          f"{E}[39m❯ {E}[2mconvierte también el paper 3 a .md{E}[0m   \n"
          f"{E}[38;5;244m{REGLA}\n"
          "  Faro   ctx 9%\n"
          "  ⏵⏵ auto mode on (shift+tab to cycle) · ← 2 agents\n\n\n")
#: con algo escrito y sin enviar (en su color, no tenue)
ESCRITO = QUIETA.replace(f"{E}[2mconvierte también el paper 3 a .md{E}[0m", "hola prueba")
TRABAJANDO = QUIETA.replace("← 2 agents", "esc to interrupt · ← 2 agents")
CON_SHELL = QUIETA.replace("auto mode on (shift+tab to cycle)", "auto mode on · 1 shell")
PERMISO = ("⏺ Bash(rm -rf build)\n\n"
           " Bash command\n   rm -rf build\n\n Do you want to proceed?\n"
           " ❯ 1. Yes\n   2. Yes, and don't ask again for rm commands\n   3. No, and tell Claude what to do differently (esc)\n")


def config_de(tmp: Path, tras: float = 1800, **kw) -> mod_config.Config:
    return mod_config.Config(raiz=tmp, estado=tmp / "estado", agente=mod_config.Agente(nombre="claude-code", carpeta="hilo"),
                             hilos=mod_config.Hilos(dormir_tras=tras), **kw)


# ── la pantalla ───────────────────────────────────────────────────────────────

class Pantalla(unittest.TestCase):
    def test_quieta_con_la_sugerencia_tenue(self):
        self.assertEqual(dormir.leer_pantalla(QUIETA),
                         {"caja": True, "escrito": "", "trabajando": False, "fondo": "", "pregunta": False})

    def test_lo_escrito_sin_enviar(self):
        self.assertEqual(dormir.leer_pantalla(ESCRITO)["escrito"], "hola prueba")

    def test_escrito_en_varias_lineas(self):
        texto = QUIETA.replace(f"{E}[39m❯ {E}[2mconvierte también el paper 3 a .md{E}[0m   \n",
                               f"{E}[39m❯ primera línea\n  segunda\n")
        self.assertEqual(dormir.leer_pantalla(texto)["escrito"], "primera línea\n  segunda")

    def test_trabajando_y_en_segundo_plano(self):
        self.assertTrue(dormir.leer_pantalla(TRABAJANDO)["trabajando"])
        self.assertEqual(dormir.leer_pantalla(CON_SHELL)["fondo"], "1 shell")
        # «← 2 agents» está siempre: no es algo en segundo plano
        self.assertEqual(dormir.leer_pantalla(QUIETA)["fondo"], "")

    def test_una_pregunta_no_es_la_caja(self):
        p = dormir.leer_pantalla(PERMISO)
        self.assertFalse(p["caja"])
        self.assertTrue(p["pregunta"])

    def test_la_caja_de_mas_arriba_no_cuenta(self):
        # un mensaje viejo de la persona, con su «❯», y una conversación larga abajo: la caja de abajo no está
        abajo = "\n".join(f"⏺ línea {i}" for i in range(20))
        p = dormir.leer_pantalla(f"{REGLA}\n❯ un mensaje viejo\n{REGLA}\n{abajo}\n")
        self.assertFalse(p["caja"])

    def test_nada(self):
        self.assertFalse(dormir.leer_pantalla("")["caja"])
        self.assertFalse(dormir.leer_pantalla(None)["caja"])
        self.assertFalse(dormir.leer_pantalla("$ ls\nREADME.md\n$ ")["caja"])


# ── los procesos y la conversación ───────────────────────────────────────────

class Procesos(unittest.TestCase):
    def test_edad(self):
        self.assertEqual(dormir._edad("05:03"), 303)
        self.assertEqual(dormir._edad("1:00:00"), 3600)
        self.assertEqual(dormir._edad("2-01:00:00"), 2 * 86400 + 3600)

    def test_el_agente_del_panel(self):
        tabla = {10: dormir.Proceso(10, 1, 50, ("sh", "-c", "claude --resume x; exec zsh -l")),
                 11: dormir.Proceso(11, 10, 50, ("claude", "--resume", "x")),
                 20: dormir.Proceso(20, 1, 50, ("sh", "-c", "mosh telar")),
                 21: dormir.Proceso(21, 20, 50, ("mosh-client", "telar")),
                 30: dormir.Proceso(30, 1, 50, ("/bin/sh", "/tmp/claude", "--resume", "y"))}
        self.assertEqual(dormir.agente_del_panel(tabla, 10, "claude").pid, 11)
        self.assertIsNone(dormir.agente_del_panel(tabla, 20, "claude"))
        # un guion que se llama como el agente (el de las pruebas): también
        self.assertEqual(dormir.agente_del_panel(tabla, 30, "/tmp/claude").pid, 30)
        self.assertIsNone(dormir.agente_del_panel(tabla, 99, "claude"))

    def test_el_agente_de_un_residente_va_envuelto_dos_veces(self):
        """El hilo de un agente residente se abre con `bash -lc cd <su carpeta>; sh -c '…claude…'; exec bash -l`: su agente
        es nieto del panel, y antes no se lo veía («su panel no corre su agente»): los agentes residentes y los hilos de
        los periódicos del servidor nunca se dormían (22-nov-2026)."""
        tabla = {40: dormir.Proceso(40, 1, 50, ("bash", "-lc", "cd /casa/agentes/cocina; sh -c '…'; exec bash -l")),
                 41: dormir.Proceso(41, 40, 50, ("sh", "-c", "export TELAR_HILO=Cocina; claude --resume x; exec sh -l")),
                 42: dormir.Proceso(42, 41, 50, ("claude", "--resume", "x")),
                 # dentro de algo que no es una shell, no: un mosh que lanza un «claude» allá no es el agente de aquí
                 50: dormir.Proceso(50, 1, 50, ("bash", "-lc", "mosh telar")),
                 51: dormir.Proceso(51, 50, 50, ("mosh-client", "telar")),
                 52: dormir.Proceso(52, 51, 50, ("claude",)),
                 # ni más hondo que unas pocas shells
                 60: dormir.Proceso(60, 1, 50, ("sh",)), 61: dormir.Proceso(61, 60, 50, ("sh",)),
                 62: dormir.Proceso(62, 61, 50, ("sh",)), 63: dormir.Proceso(63, 62, 50, ("sh",)),
                 64: dormir.Proceso(64, 63, 50, ("claude",))}
        self.assertEqual(dormir.agente_del_panel(tabla, 40, "claude").pid, 42)
        self.assertIsNone(dormir.agente_del_panel(tabla, 50, "claude"))
        self.assertIsNone(dormir.agente_del_panel(tabla, 60, "claude"))

    def test_reconoce_al_que_espera(self):
        p = dormir.programa("Faro")
        tabla = {5: dormir.Proceso(5, 1, 3, tuple(" ".join(p).split()))}
        self.assertTrue(dormir.es_dormido(tabla, 5))
        self.assertFalse(dormir.es_dormido({5: dormir.Proceso(5, 1, 3, ("claude",))}, 5))

    def test_ps_que_corta_un_caracter_a_la_mitad(self):
        # ps corta los args largos por bytes: «—» (e2 80 94) queda en «\xe2» y la línea no es UTF-8 válido
        with tempfile.TemporaryDirectory() as carpeta:
            ps = Path(carpeta) / "ps"
            ps.write_bytes(b"#!/bin/sh\nprintf '  7     1    05:03 claude --resume x \\342\\n  8     7    00:10 zsh\\n'\n")
            ps.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": f"{carpeta}{os.pathsep}{os.environ['PATH']}"}):
                tabla = dormir.procesos()
        self.assertEqual(sorted(tabla), [7, 8])
        self.assertEqual(tabla[7].args[:3], ("claude", "--resume", "x"))
        self.assertEqual(tabla[8].ppid, 7)


class Conversacion(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="telar-dormir-conv-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.archivo = self.tmp / "s.jsonl"
        dormir._LEIDAS.clear()

    def escribir(self, *llamadas):
        lineas = [json.dumps({"type": "user", "message": {"content": "hola"}})]
        for cuando, nombre, entrada in llamadas:
            lineas.append(json.dumps({"type": "assistant", "timestamp": datetime.fromtimestamp(cuando).astimezone().isoformat(),
                                      "message": {"content": [{"type": "tool_use", "name": nombre, "input": entrada}]}}))
        self.archivo.write_text("\n".join(lineas) + "\n")

    def test_sin_nada_programado(self):
        self.escribir()
        self.assertEqual(dormir.programado(self.archivo, 0, time.time()), "")

    def test_un_scheduleWakeup_pendiente_y_uno_que_ya_sono(self):
        ahora = time.time()
        self.escribir((ahora - 600, "ScheduleWakeup", {"delaySeconds": 1800, "prompt": "/loop x"}))
        self.assertIn("ScheduleWakeup", dormir.programado(self.archivo, ahora - 3600, ahora))
        self.escribir((ahora - 7200, "ScheduleWakeup", {"delaySeconds": 600}))
        self.assertEqual(dormir.programado(self.archivo, ahora - 9000, ahora), "")

    def test_un_loop_detenido(self):
        ahora = time.time()
        self.escribir((ahora - 900, "ScheduleWakeup", {"delaySeconds": 1800}), (ahora - 600, "ScheduleWakeup", {"stop": True}))
        self.assertEqual(dormir.programado(self.archivo, ahora - 3600, ahora), "")

    def test_un_cron_sin_borrar_y_uno_borrado(self):
        ahora = time.time()
        self.escribir((ahora - 900, "CronCreate", {"cron": "*/5 * * * *", "prompt": "x"}))
        self.assertIn("cron", dormir.programado(self.archivo, ahora - 3600, ahora))
        self.escribir((ahora - 900, "CronCreate", {"cron": "*/5 * * * *"}), (ahora - 800, "CronDelete", {"id": "a"}))
        self.assertEqual(dormir.programado(self.archivo, ahora - 3600, ahora), "")

    def test_lo_de_antes_de_que_arrancara_el_agente_murio_con_el_otro(self):
        ahora = time.time()
        self.escribir((ahora - 900, "CronCreate", {"cron": "*/5 * * * *"}), (ahora - 800, "ScheduleWakeup", {"delaySeconds": 3600}))
        self.assertEqual(dormir.programado(self.archivo, ahora - 60, ahora), "")
        # salvo un cron que dura
        self.escribir((ahora - 900, "CronCreate", {"cron": "*/5 * * * *", "durable": True}))
        self.assertIn("cron", dormir.programado(self.archivo, ahora - 60, ahora))

    def test_ultima_escritura_cuenta_sus_subagentes(self):
        self.escribir()
        os.utime(self.archivo, (1000, 1000))
        self.assertEqual(dormir.ultima_escritura(self.archivo), 1000)  # sin líneas con hora: la fecha del archivo
        sub = self.tmp / "s" / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-a.jsonl").write_text("{}\n")
        os.utime(sub / "agent-a.jsonl", (5000, 5000))
        self.assertEqual(dormir.ultima_escritura(self.archivo), 5000)
        self.assertIsNone(dormir.ultima_escritura(None))

    def test_la_hora_de_su_ultima_linea_no_la_fecha_del_archivo(self):
        # Claude Code toca la conversación cada tanto sin escribir nada: lo que vale es la hora de su última línea
        ahora = time.time()
        self.escribir((ahora - 7200, "Bash", {"command": "ls"}))
        with open(self.archivo, "a") as f:
            f.write(json.dumps({"type": "atis-latch", "atis": ""}) + "\n")
        os.utime(self.archivo, (ahora - 60, ahora - 60))
        self.assertAlmostEqual(dormir.ultima_escritura(self.archivo), ahora - 7200, delta=2)


# ── las reglas ───────────────────────────────────────────────────────────────

AHORA = 1_800_000_000.0


def quieto(**kw) -> dormir.Observacion:
    """Uno que se puede dormir: todo quieto hace una hora. Cada prueba le cambia una cosa."""
    hace = datetime.fromtimestamp(AHORA - 3600)
    o = dormir.Observacion(nombre="Faro", id="@1", paneles=1, panel="%1",
                           agente=dormir.Proceso(11, 10, AHORA - 7200, ("claude",)), conversacion="s1", archivo=Path("/x/s1.jsonl"),
                           atencion=Atencion.TERMINO, atencion_desde=hace, actividad=hace, visto=hace,
                           escrito_en=AHORA - 3600, pantalla=dormir.leer_pantalla(QUIETA), programado="")
    for k, v in kw.items():
        setattr(o, k, v)
    return o


class Reglas(unittest.TestCase):
    def no(self, o, *palabras, tras=1800):
        motivo = dormir.por_que_no(o, tras, AHORA)
        self.assertTrue(motivo, "debía no dormirse")
        for p in palabras:
            self.assertIn(p, motivo)

    def test_el_quieto_se_duerme(self):
        self.assertEqual(dormir.por_que_no(quieto(), 1800, AHORA), "")

    def test_nunca_con_dormir_tras_cero(self):
        self.no(quieto(), "0", tras=0)

    def test_lo_que_no_es_de_aqui_o_no_corre_su_agente(self):
        self.no(quieto(dormido=True), "duerme")
        self.no(quieto(remoto="servidor"), "otra máquina")
        self.no(quieto(archivado=True), "archivado")
        self.no(quieto(paneles=2), "2 paneles")
        self.no(quieto(agente=None), "agente")
        self.no(quieto(conversacion=""), "conversación")
        self.no(quieto(archivo=None), "disco")
        self.no(quieto(siempre=True), "siempre")

    def test_a_mitad_de_turno_o_esperando(self):
        self.no(quieto(atencion=Atencion.TRABAJANDO), "trabajando")
        self.no(quieto(atencion=Atencion.ESPERA), "espera")
        self.no(quieto(pantalla=dormir.leer_pantalla(TRABAJANDO)), "trabajando")

    def test_a_la_vista(self):
        self.no(quieto(vista="abierto en la página"), "a la vista", "página")

    def test_cualquier_actividad_reciente(self):
        hace = datetime.fromtimestamp(AHORA - 300)
        self.no(quieto(atencion_desde=hace), "activo hace 5 min")
        self.no(quieto(actividad=hace), "activo")
        self.no(quieto(visto=hace), "activo")
        self.no(quieto(escrito_en=AHORA - 300), "activo")
        # un agente recién despertado, aunque su conversación sea vieja
        self.no(quieto(agente=dormir.Proceso(11, 10, AHORA - 120, ("claude",))), "activo hace 2 min")
        sin = quieto(atencion_desde=None, actividad=None, visto=None, escrito_en=None, agente=None)
        self.assertIn("agente", dormir.por_que_no(sin, 1800, AHORA))

    def test_algo_en_segundo_plano(self):
        self.no(quieto(hijos=["zsh"]), "segundo plano", "zsh")
        self.no(quieto(hijos=["caffeinate"]), "caffeinate")
        self.assertEqual(dormir.por_que_no(quieto(hijos=["node"]), 1800, AHORA), "")  # un MCP no cuenta
        self.no(quieto(pantalla=dormir.leer_pantalla(CON_SHELL)), "1 shell")
        self.no(quieto(programado="un cron de la sesión (CronCreate) sin borrar"), "cron")
        self.no(quieto(programado=None), "no se pudo leer")

    def test_texto_sin_enviar_o_una_pregunta(self):
        self.no(quieto(pantalla=dormir.leer_pantalla(ESCRITO)), "sin enviar")
        self.no(quieto(pantalla=dormir.leer_pantalla(PERMISO)), "pregunta")
        self.no(quieto(pantalla=None), "pantalla")

    def test_mensajes_por_entregar_o_rotando(self):
        self.no(quieto(por_entregar=2), "2 mensaje")
        self.no(quieto(rotando=True), "rotando")

    def test_a_mano_no_mira_el_tiempo_ni_la_vista_pero_si_lo_demas(self):
        reciente = quieto(vista="abierto en la página", escrito_en=AHORA - 5, atencion_desde=datetime.fromtimestamp(AHORA - 5))
        self.assertEqual(dormir.por_que_no(reciente, 1800, AHORA, forzar=True), "")
        self.assertEqual(dormir.por_que_no(quieto(), 0, AHORA, forzar=True), "")
        self.assertIn("sin enviar", dormir.por_que_no(quieto(pantalla=dormir.leer_pantalla(ESCRITO)), 1800, AHORA, forzar=True))
        self.assertIn("trabajando", dormir.por_que_no(quieto(atencion=Atencion.TRABAJANDO), 1800, AHORA, forzar=True))
        # lo que Claude Code deja corriendo un rato después de trabajar no frena a la persona; una tarea de fondo, sí
        self.assertEqual(dormir.por_que_no(quieto(hijos=["caffeinate"]), 1800, AHORA, forzar=True), "")
        self.assertIn("zsh", dormir.por_que_no(quieto(hijos=["zsh"]), 1800, AHORA, forzar=True))


# ── lo que se mira ───────────────────────────────────────────────────────────

class Mirando(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="telar-dormir-mira-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.config = config_de(self.tmp, bus=mod_config.Bus(maquina="laptop"))
        hilos = [Hilo(id="@1", nombre="Faro"), Hilo(id="@2", nombre="Molino"), Hilo(id="@3", nombre="Secretaría", remoto="telar"),
                 Hilo(id="@4", nombre="Cosecha")]
        est = mod_estado.abrir(self.config)
        self.tel = SimpleNamespace(hilos=hilos, vivo=lambda h: True, estado=est,
                                   por_nombre=lambda n: next((h for h in hilos if h.nombre == n), None))

    def vista(self, **kw):
        kw.setdefault("lista_clientes", [])
        kw.setdefault("fotos", [])
        return dormir.a_la_vista(self.config, self.tel, AHORA, **kw)

    def test_lo_que_dicen_las_paginas(self):
        dormir.anotar_mirando(self.config, "p1", "Faro", cuando=AHORA - 10)
        dormir.anotar_mirando(self.config, "p2", "Molino", cuando=AHORA - 200)  # hace mucho: ya no se mira
        dormir.anotar_mirando(self.config, "p3", "Cosecha", "telar", cuando=AHORA - 5)  # el de otra máquina
        self.assertEqual(self.vista(), {"Faro": "abierto en la página"})

    def test_las_terminales_de_la_pagina_que_no_se_ven(self):
        clientes = [("ver-web-aa", "@1"), ("ver-web-bb", "@2")]
        # sin noticias de ninguna página, las dos se miran
        self.assertEqual(set(self.vista(lista_clientes=clientes)), {"Faro", "Molino"})
        # la página dice que muestra Faro: la terminal de Molino está guardada, oculta
        dormir.anotar_mirando(self.config, "p1", "Faro", cuando=AHORA)
        self.assertEqual(set(self.vista(lista_clientes=clientes)), {"Faro"})

    def test_una_terminal_de_verdad_siempre_se_mira(self):
        dormir.anotar_mirando(self.config, "p1", "", cuando=AHORA)
        for sesion in ("trabajo", "movil-1a2b3c4d", "ver-2-48123"):
            self.assertIn("Molino", self.vista(lista_clientes=[(sesion, "@2")]), sesion)

    def test_la_que_mira_desde_otra_maquina(self):
        clientes = [("ver-2-macbook-de-ana", "@2")]
        # sin su foto: se mira
        self.assertIn("Molino", self.vista(lista_clientes=clientes))
        foto = {"nombre": "servidor", "vista": "macbook-de-ana", "en_linea": True, "edad": 10, "mirando": []}
        # con su foto al día, lo que diga: allá no muestran Molino
        self.assertEqual(self.vista(lista_clientes=clientes, fotos=[foto]), {})
        foto["mirando"] = [{"maquina": "laptop", "hilo": "Molino"}]
        self.assertIn("servidor", self.vista(lista_clientes=clientes, fotos=[foto])["Molino"])
        # un telar de antes (sin `mirando`): se mira
        viejo = {k: v for k, v in foto.items() if k != "mirando"}
        self.assertIn("Molino", self.vista(lista_clientes=clientes, fotos=[viejo]))
        # una máquina apagada hace rato: nadie mira desde allá
        apagada = {**foto, "en_linea": False, "edad": dormir.APAGADA + 60}
        self.assertEqual(self.vista(lista_clientes=clientes, fotos=[apagada]), {})

    def test_lo_que_se_mira_aqui_para_la_foto(self):
        dormir.anotar_mirando(self.config, "p1", "Secretaría", cuando=AHORA)  # la ventana de aquí de uno del servidor
        dormir.anotar_mirando(self.config, "p2", "Telar", "telar", cuando=AHORA)  # uno de allá, desde la página
        lista = dormir.mirando_de_aqui(self.config, self.tel, AHORA, lista_clientes=[("trabajo", "@1"), ("ver-web-x", "@2")])
        self.assertEqual(lista, [{"maquina": "laptop", "hilo": "Faro"}, {"maquina": "telar", "hilo": "Secretaría"},
                                 {"maquina": "telar", "hilo": "Telar"}])

    def test_viaja_en_la_foto(self):
        tel = SimpleNamespace(hilos=[], sesion="trabajo")
        crudo = espejo.foto(tel, maquina="laptop", mirando=[{"maquina": "telar", "hilo": "Secretaría"}], vista="macbook")
        limpia = espejo.validar(json.loads(json.dumps(crudo)), "laptop")
        self.assertEqual(limpia["mirando"], [{"maquina": "telar", "hilo": "Secretaría"}])
        self.assertEqual(limpia["vista"], "macbook")
        espejo.guardar(self.config, "laptop", json.dumps(crudo))
        leida = espejo.leer_todos(self.config)[0]
        self.assertEqual((leida["mirando"], leida["vista"]), (limpia["mirando"], "macbook"))
        # sin `mirando` (no se supo), no viaja: allá cuenta como que se mira
        self.assertNotIn("mirando", espejo.foto(tel, maquina="laptop"))


# ── dormir y despertar, con un multiplexor falso ─────────────────────────────

class FalsoMux:
    """Una ventana por hilo con un panel; `abrir_pane(reemplaza=…)` lo cambia por uno nuevo, como tmux."""

    def __init__(self, nombres):
        self.ventanas = {f"@{i}": n for i, n in enumerate(nombres, 1)}
        self.paneles = {f"@{i}": [(f"%{i}", 100 * i)] for i in range(1, len(nombres) + 1)}
        self.pantallas = {f"%{i}": QUIETA for i in range(1, len(nombres) + 1)}
        self.abiertos, self.escritos = [], []
        self.siguiente = 50

    def hilos(self):
        return [Hilo(id=v, nombre=n) for v, n in self.ventanas.items()]

    def panes(self, tab=None):
        return [SimpleNamespace(id=p, tab=v, pid=pid, flotante=False, terminado=False)
                for v, ps in self.paneles.items() if tab in (None, v) for p, pid in ps]

    def capturar_pane_con_escapes(self, panel, lineas=60):
        return self.pantallas.get(panel, "")

    def abrir_pane(self, comando, *, reemplaza, ruta=None, foco=True):
        self.siguiente += 1
        nuevo = f"%{self.siguiente}"
        for v, ps in self.paneles.items():
            if any(p == reemplaza for p, _ in ps):
                self.paneles[v] = [(nuevo, 1000 + self.siguiente)]
        self.abiertos.append((reemplaza, list(comando)))
        return SimpleNamespace(id=nuevo)

    def escribir(self, hilo, texto, enviar=False):
        self.escritos.append((hilo, texto, enviar))


class ConMux(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="telar-dormir-mux-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        claude = self.tmp / "claude-config"
        entorno = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude)})
        entorno.start()
        self.addCleanup(entorno.stop)
        dormir._LEIDAS.clear()
        self.config = config_de(self.tmp)
        self.est = mod_estado.abrir(self.config)
        self.mux = FalsoMux(["Faro", "Molino"])
        self.tabla = {}
        hace = datetime.now() - timedelta(hours=2)
        for i, (nombre, sid) in enumerate([("Faro", "s-faro"), ("Molino", "s-molino")], 1):
            self.est.anotar_sesion(nombre, sid, panel=f"%{i}")
            self.est.anotar_atencion(nombre, Atencion.TERMINO, hace)
            archivo = claude / "projects" / "p" / f"{sid}.jsonl"
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text('{"type":"user","message":{"content":"hola"}}\n')
            os.utime(archivo, (time.time() - 7200, time.time() - 7200))
            self.tabla[100 * i] = dormir.Proceso(100 * i, 1, time.time() - 7200, ("sh", "-c", "claude …"))
            self.tabla[100 * i + 1] = dormir.Proceso(100 * i + 1, 100 * i, time.time() - 7200, ("claude", "--resume", sid))
        # Molino tiene algo escrito y sin enviar: no se duerme (lo que importa en cada prueba es Faro)
        self.mux.pantallas["%2"] = ESCRITO
        self.tel = self.telar()

    def telar(self):
        hilos = self.mux.hilos()
        return SimpleNamespace(mux=self.mux, estado=self.est, hilos=hilos, vivo=lambda h: True,
                               por_nombre=lambda n: next((h for h in hilos if h.nombre == n), None))

    def mirar(self, vistos=None):
        return dormir.mirar(self.config, self.tel, tabla=self.tabla, vistos=vistos or {})

    def test_duerme_al_quieto_y_deja_su_ventana_esperando(self):
        cambios = self.mirar()
        self.assertEqual(len(cambios), 1)
        self.assertIn("«Faro» se durmió", cambios[0])
        panel, comando = self.mux.abiertos[0]
        self.assertEqual(panel, "%1")
        self.assertIn(dormir.MARCA, comando[-1])
        self.assertIn("duerme desde", comando[-1])
        d = self.est.dormidos()["Faro"]
        self.assertEqual((d["conversacion"], d["atencion"], d["panel"]), ("s-faro", "termino", "%51"))
        self.assertNotIn("Molino", self.est.dormidos())

    def test_no_duerme_al_que_se_mira_ni_dos_veces(self):
        self.assertEqual(self.mirar(vistos={"Faro": "abierto en la página", "Molino": "abierto en la página"}), [])
        self.assertEqual(self.mux.abiertos, [])
        self.mirar()
        self.tel = self.telar()
        self.tabla[1051] = dormir.Proceso(1051, 1, 5, tuple(dormir.programa("Faro")))
        self.tabla[1052] = dormir.Proceso(1052, 1, 5, tuple(dormir.programa("Molino")))
        self.assertEqual(self.mirar(), [])

    def test_con_dormir_tras_cero_no(self):
        self.config = config_de(self.tmp, tras=0)
        self.assertEqual(self.mirar(), [])

    def test_despertar_retoma_su_conversacion_en_la_misma_ventana(self):
        self.mirar()
        self.tel = self.telar()
        hecho = dormir.despertar(self.config, "Faro", mensaje="↯ mensaje nuevo", mux=self.mux)
        self.assertIn("«Faro» despertó (conversación s-faro", hecho)
        panel, comando = self.mux.abiertos[-1]
        self.assertEqual(panel, "%51")  # el panel del que dormía, en su misma ventana
        self.assertIn("--resume s-faro", comando[-1])
        self.assertIn("mensaje nuevo", comando[-1])
        self.assertNotIn("Faro", self.est.dormidos())
        # despertar al que no duerme no hace nada
        self.assertEqual(dormir.despertar(self.config, "Molino", mux=self.mux), "")

    def test_escribirle_al_dormido_lo_despierta_con_eso(self):
        self.mirar()
        h = self.tel.por_nombre("Faro")
        dormir.escribir(self.config, self.tel, h, "git merge main", enviar=True)
        self.assertIn("'git merge main'", self.mux.abiertos[-1][1][-1])
        self.assertEqual(self.mux.escritos, [])  # nada tecleado en el panel que espera
        # despierto, se teclea como siempre
        dormir.escribir(self.config, self.tel, self.tel.por_nombre("Molino"), "hola", enviar=True)
        self.assertEqual(self.mux.escritos, [("@2", "hola", True)])

    def test_un_mensaje_del_bus_lo_despierta(self):
        from telar.ordenes import nodo as mod_nodo

        self.mirar()
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.ctx, n.config, n.yo = SimpleNamespace(config=self.config), self.config, "laptop"
        n.anotado = []
        n.anotar = n.anotado.append
        casilla.dejar(self.config, "Faro", {"id": "m1", "texto": "git merge main", "de": "Telar", "para": "Faro"})
        with mock.patch("telar.mux.obtener", return_value=self.mux):
            dicho = n.avisar("Faro", {"residente": ""})
        self.assertEqual(dicho, "despertado")
        self.assertIn("--resume s-faro", self.mux.abiertos[-1][1][-1])
        self.assertIn("mensaje nuevo", self.mux.abiertos[-1][1][-1])
        self.assertEqual(self.est.atencion("Faro"), Atencion.TRABAJANDO)

    def test_su_mod_no_cuenta_mientras_duerme(self):
        (casilla.carpeta(self.config, "Faro")).mkdir(parents=True, exist_ok=True)
        (casilla.carpeta(self.config, "Faro") / casilla.MOD).write_text("")
        self.assertTrue(casilla.mod_vivo(self.config, "Faro"))
        self.mirar()
        self.assertFalse(casilla.mod_vivo(self.config, "Faro"))

    def test_mensajes_por_entregar_lo_mantienen_despierto(self):
        casilla.dejar(self.config, "Faro", {"id": "m1", "texto": "hola", "de": "Telar", "para": "Faro"})
        self.assertNotIn("Faro", "".join(self.mirar()))

    def test_ordenar_olvida_al_que_perdio_su_ventana_y_devuelve_su_atencion(self):
        self.mirar()
        self.tel = self.telar()
        self.tabla[1051] = dormir.Proceso(1051, 1, 5, tuple(" ".join(dormir.programa("Faro")).split()))
        # el gancho de cierre de su agente le borró la atención: vuelve la que tenía («terminó, sin ver»)
        self.est.anotar_atencion("Faro", Atencion.NINGUNA)
        dormir.ordenar(self.config, self.tel, tabla=self.tabla)
        self.assertEqual(self.est.atencion("Faro"), Atencion.TERMINO)
        # su ventana se cerró: ya no duerme
        del self.mux.ventanas["@1"], self.mux.paneles["@1"]
        self.tel = self.telar()
        cambios = dormir.ordenar(self.config, self.tel, tabla=self.tabla)
        self.assertIn("ya no duerme", cambios[0])
        self.assertNotIn("Faro", self.est.dormidos())

    def test_lo_dice_su_json(self):
        from telar.ordenes import _comun

        self.mirar()
        tel = SimpleNamespace(**vars(self.tel), dormidos=self.est.dormidos())
        self.assertEqual(_comun._dormido(tel, self.tel.por_nombre("Faro"))["conversacion"], "s-faro")
        self.assertIsNone(_comun._dormido(tel, self.tel.por_nombre("Molino")))


class Estado(Prueba):
    def test_renombrar_y_olvidar(self):
        tmp = Path(tempfile.mkdtemp(prefix="telar-dormir-est-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        est = mod_estado.abrir(config_de(tmp))
        est.anotar_dormido("Faro", {"desde": "2026-11-19T10:00:00"})
        est.renombrar("Faro", "Faro Norte")
        self.assertIn("Faro Norte", est.dormidos())
        est.olvidar("Faro Norte")
        self.assertEqual(est.dormidos(), {})


class Config(unittest.TestCase):
    def test_dormir_tras(self):
        self.assertEqual(mod_config.duracion("30m"), 1800)
        self.assertEqual(mod_config.duracion("1h30m"), 5400)
        self.assertEqual(mod_config.duracion("45 min"), 2700)
        self.assertEqual(mod_config.duracion(20), 1200)
        self.assertEqual(mod_config.duracion("0"), 0)
        self.assertEqual(mod_config.duracion("nunca"), 0)
        for malo in ("x", "30x", -1, True, "m"):
            with self.assertRaises(ValueError):
                mod_config.duracion(malo)
        self.assertEqual(mod_config.Hilos().dormir_tras, 1800)

    def test_en_el_archivo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "config.toml"
            ruta.write_text('raiz = "/tmp"\n[hilos]\ndormir_tras = "1h"\n')
            self.assertEqual(mod_config.cargar(ruta).hilos.dormir_tras, 3600)
            ruta.write_text('raiz = "/tmp"\n[hilos]\ndormir_tras = "pronto"\n')
            with self.assertRaises(mod_config.ErrorDeConfig):
                mod_config.cargar(ruta)


try:
    from fastapi.testclient import TestClient

    from telar import api
except ImportError:  # pragma: no cover - sin el extra serve
    api = None


@unittest.skipIf(api is None, "sin fastapi")
class Api(Prueba):
    """Lo que la página pide: decir lo que muestra (`POST /mirando`) y despertar al que abre (`POST /despertar`)."""

    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="telar-dormir-api-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        ruta = self.tmp / "config.toml"
        ruta.write_text(f'raiz = "{self.tmp}"\nestado = "{self.tmp / "estado"}"\n')
        entorno = mock.patch.dict(os.environ, {"TELAR_CONFIG": str(ruta)})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.config = mod_config.cargar(ruta)

    def test_mirando(self):
        r = TestClient(api.app).post("/mirando", json={"pagina": "p1", "hilo": "Faro"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(dormir.paginas(self.config), [{"hilo": "Faro", "maquina": ""}])
        TestClient(api.app).post("/mirando", json={"pagina": "p1", "hilo": "", "maquina": ""})
        self.assertEqual(dormir.paginas(self.config), [{"hilo": "", "maquina": ""}])

    def test_despertar(self):
        with mock.patch.object(dormir, "despertar_pedido", return_value={"hecho": "«Faro» despertó (conversación s-faro)"}) as d:
            r = TestClient(api.app).post("/despertar", json={"hilo": "Faro", "maquina": "servidor"})
        self.assertEqual(r.json(), {"hecho": "«Faro» despertó (conversación s-faro)"})
        self.assertEqual(d.call_args.args[1:], ("Faro", "servidor"))
        self.assertEqual(d.call_args.kwargs, {"texto": "", "cola": False}, "abrirlo no deja nada en cola")
        # el botón: con texto y en cola si su máquina está fuera de línea (telar.alcance)
        with mock.patch.object(dormir, "despertar_pedido", return_value={"hecho": "…", "en_cola": True}) as d:
            r = TestClient(api.app).post("/despertar", json={"hilo": "Faro", "maquina": "laptop", "texto": "sigue", "cola": True})
        self.assertTrue(r.json()["en_cola"])
        self.assertEqual(d.call_args.kwargs, {"texto": "sigue", "cola": True})
        with mock.patch.object(dormir, "despertar_pedido", side_effect=RuntimeError("no se pudo")):
            self.assertEqual(TestClient(api.app).post("/despertar", json={"hilo": "Faro"}).status_code, 502)


# ── en un tmux de verdad ──────────────────────────────────────────────────────

#: el agente de mentira: dice con qué lo abrieron y dibuja la caja quieta de Claude Code
AGENTE = """#!/bin/sh
echo "agente: $*"
printf '%s\\n' "────────────────────────────────────────" "❯ " "────────────────────────────────────────" "  faro   ctx 1%"
while :; do read x || sleep 1; done
"""


@unittest.skipUnless(shutil.which("tmux"), "sin tmux instalado")
class EnTmuxDeVerdad(Prueba):
    """Dormir y despertar contra tmux: un servidor propio (`TMUX_TMPDIR` aparte, sin `TMUX`), un agente de mentira que se
    llama `claude` y un `telar` de esta copia en el PATH, que es lo que corre el ⏎ del que duerme."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="telar-dormir-tmux-"))
        cls.entorno = {k: os.environ.get(k) for k in ("TMUX_TMPDIR", "TMUX", "PATH", "CLAUDE_CONFIG_DIR")}
        os.environ["TMUX_TMPDIR"] = str(cls.tmp / "tmux")
        (cls.tmp / "tmux").mkdir()
        os.environ.pop("TMUX", None)
        cls.claude_config = cls.tmp / "claude-config"
        os.environ["CLAUDE_CONFIG_DIR"] = str(cls.claude_config)
        cls.agente = cls.tmp / "claude"
        cls.agente.write_text(AGENTE)
        cls.agente.chmod(0o755)
        cls.ruta_config = cls.tmp / "config.toml"
        cls.ruta_config.write_text(
            f'multiplexor = "tmux"\nsesion = "telar-pruebas-dormir"\nraiz = "{cls.tmp}"\nestado = "{cls.tmp / "estado"}"\n'
            f'[agente]\nnombre = "claude-code"\ncarpeta = "{cls.tmp}"\n[hilos]\ndormir_tras = "30m"\n')
        bin_ = cls.tmp / "bin"
        bin_.mkdir()
        src = Path(__file__).resolve().parent.parent / "src"
        (bin_ / "telar").write_text(
            f"#!/bin/sh\nexport PYTHONPATH={src} TELAR_CONFIG={cls.ruta_config} TELAR_CLAUDE={cls.agente} "
            f"CLAUDE_CONFIG_DIR={cls.claude_config}\nexec {sys.executable} -m telar \"$@\"\n")
        (bin_ / "telar").chmod(0o755)
        os.environ["PATH"] = f"{bin_}:{os.environ.get('PATH', '')}"

    @classmethod
    def tearDownClass(cls):
        comun.matar_tmux(cls.tmp / "tmux")
        for k, v in cls.entorno.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        super().setUp()
        os.environ["TELAR_CONFIG"] = str(self.ruta_config)
        os.environ["TELAR_CLAUDE"] = str(self.agente)
        from telar.mux.tmux import Tmux

        self.config = mod_config.cargar(self.ruta_config)
        self.mux = Tmux(self.config)
        if not self.mux.viva():
            self.mux.tejer()
        self.est = mod_estado.abrir(self.config)
        dormir._LEIDAS.clear()

    def abrir(self, nombre: str, sid: str):
        from telar.agente import lanzar

        archivo = self.claude_config / "projects" / "p" / f"{sid}.jsonl"
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text('{"type":"user","message":{"content":"hola"}}\n')
        os.utime(archivo, (time.time() - 7200, time.time() - 7200))
        self.est.anotar_sesion(nombre, sid)
        lanz = lanzar.para_hilo(self.config, nombre, None)
        self.assertIn("--resume", " ".join(lanz.comando))
        self.mux.crear_tab(nombre, ruta=self.tmp, comando=lanz.comando, foco=False)
        self.esperar(nombre, "agente: --resume")

    def panel(self, nombre: str):
        ventana = next(h.id for h in self.mux.hilos() if h.nombre == nombre)
        return ventana, self.mux.panes(ventana)[0]

    def pantalla(self, nombre: str) -> str:
        return self.mux.capturar_pane(str(self.panel(nombre)[1].id), 40) or ""

    def esperar(self, nombre: str, texto: str, plazo: float = 15) -> str:
        fin = time.time() + plazo
        visto = ""
        while time.time() < fin:
            try:
                visto = self.pantalla(nombre)
            except Exception:  # noqa: BLE001 - el panel se está reemplazando
                visto = ""
            if texto in visto:
                return visto
            time.sleep(0.1)
        self.fail(f"«{texto}» no apareció en «{nombre}»:\n{visto}")

    def tel(self):
        from telar.ordenes import _comun

        return _comun.tejer(SimpleNamespace(config=self.config, perfil=None), con_ficha=False)

    def test_se_duerme_y_un_enter_lo_despierta_con_lo_escrito(self):
        self.abrir("Faro", "s-faro-1")
        ventana, antes = self.panel("Faro")
        # pasó la hora: nadie lo mira, su conversación es de hace dos horas; el agente arrancó hace un momento, así
        # que se le da una hora de más al reloj
        tel = self.tel()
        cambios = dormir.mirar(self.config, tel, time.time() + 3600, vistos={})
        motivos = [(o.nombre, dormir.por_que_no(o, 1800, time.time() + 3600))
                   for o in dormir.observar(self.config, tel, time.time() + 3600, vistos={}, completo=True)]
        self.assertTrue(any("«Faro» se durmió" in c for c in cambios), (cambios, motivos))
        self.esperar("Faro", "duerme desde")
        ventana2, ahora = self.panel("Faro")
        self.assertEqual(ventana, ventana2)  # la misma ventana, en su lugar
        self.assertNotEqual(antes.id, ahora.id)
        self.assertTrue(dormir.es_dormido(dormir.procesos(), ahora.pid))
        self.assertIn("Faro", self.est.dormidos())
        # el json lo dice
        from telar.ordenes import _comun

        tel = self.tel()
        self.assertEqual(_comun.json_hilo(tel.por_nombre("Faro"), tel, con_ficha=False)["dormido"]["conversacion"], "s-faro-1")
        # lo que se teclea en su ventana no llega a una shell: con el ⏎, despierta y le llega como primer mensaje
        self.mux.escribir(ventana, "git merge main", enviar=True)
        visto = self.esperar("Faro", "agente: --resume s-faro-1 git merge main", plazo=30)
        self.assertNotIn("command not found", visto)
        self.assertNotIn("Faro", self.est.dormidos())

    def test_si_no_puede_despertar_su_ventana_sigue_esperando(self):
        # un telar que no entiende `despertar` (uno de antes, tras volver atrás un despliegue): el panel no se cierra
        self.abrir("Cosecha", "s-cosecha-1")
        dormir.dormir_uno(self.config, self.tel(), "Cosecha", forzar=True)
        self.esperar("Cosecha", "duerme desde")
        ventana, panel = self.panel("Cosecha")
        telar = self.tmp / "bin" / "telar"
        bueno = telar.read_text()
        telar.write_text("#!/bin/sh\necho 'telar: argument verbo: invalid choice' >&2\nexit 2\n")
        self.addCleanup(telar.write_text, bueno)
        self.mux.escribir(ventana, "hola", enviar=True)
        self.esperar("Cosecha", "no se pudo despertar")
        self.assertEqual(self.panel("Cosecha")[1].id, panel.id)
        # con el telar de esta copia, el ⏎ siguiente lo despierta
        telar.write_text(bueno)
        self.mux.escribir(ventana, "", enviar=True)
        self.esperar("Cosecha", "agente: --resume s-cosecha-1")

    def test_despertar_desde_afuera(self):
        self.abrir("Molino", "s-molino-1")
        dormir.dormir_uno(self.config, self.tel(), "Molino", forzar=True)
        self.esperar("Molino", "duerme desde")
        ventana, _ = self.panel("Molino")
        hecho = dormir.despertar(self.config, "Molino", mensaje="↯ mensaje nuevo")
        self.assertIn("despertó", hecho)
        self.esperar("Molino", "agente: --resume s-molino-1 ↯ mensaje nuevo")
        self.assertEqual(self.panel("Molino")[0], ventana)
        self.assertEqual(self.est.dormidos(), {})


if __name__ == "__main__":
    unittest.main()
