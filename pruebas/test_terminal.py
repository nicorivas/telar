"""La terminal de un hilo en la página: el motivo que va en el cierre cuando no se pudo abrir
(telar.terminal.motivo), que los hipervínculos lleguen (`telar mirar --enlaces`) y que el tamaño que manda la página le
llegue a tmux (`terminal.con_terminal`).

Un enlace de markdown que escribe Claude Code (`[Doc](https://…)`) dentro de un tmux 3.4 o más nuevo sale como un
hipervínculo OSC 8: a la vista, solo «Doc»; la dirección, en la secuencia. tmux lo guarda, pero solo se lo pasa a
una terminal que declara entenderlos, y la de la página (xterm.js) se presenta como xterm-256color, que no lo
declara: llegaba «Doc» sin dirección, y no había nada que abrir. La prueba de integración lo mira contra un tmux de
verdad, en un servidor propio (`TMUX_TMPDIR`), con lo mismo que corre `mirar`.
"""

from __future__ import annotations

import asyncio
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from comun import Prueba, matar_tmux  # noqa: E402  (pone src/ en el camino)

from telar import movil, terminal


class ElMotivoDelCierre(Prueba):
    def test_la_ultima_linea_sin_colores_ni_telar(self):
        salida = "\x1b[1mtelar: no hay un hilo «◌ un rato 10/28 10:00»\x1b[0m\r\n"
        self.assertEqual(terminal.motivo(salida), "no hay un hilo «◌ un rato 10/28 10:00»")

    def test_cabe_en_el_cierre_de_un_websocket(self):
        self.assertLessEqual(len(terminal.motivo("é" * 300).encode("utf-8")), 123)
        self.assertEqual(terminal.motivo("\r\n  \r\n"), "no se pudo abrir")


class LosRasgosDeQuienMira(Prueba):
    def test_un_tmux_que_guarda_enlaces_los_pasa(self):
        for version in ("tmux 3.4", "tmux 3.8", "tmux 3.10a", "tmux 4.0", "tmux next-3.6", "tmux master"):
            self.assertEqual(movil.rasgos_con_enlaces(version), ["-T", "hyperlinks"], version)

    def test_uno_viejo_o_mudo_no_recibe_banderas(self):
        # antes de 3.4 tmux no guarda los enlaces (y antes de 3.2 no conoce -T): nada que pedirle
        for version in ("tmux 3.3a", "tmux 3.2", "tmux 2.9a", "", "  "):
            self.assertEqual(movil.rasgos_con_enlaces(version), [], version)

    def test_la_pagina_mira_con_enlaces(self):
        """El PTY de la página corre `telar mirar … --enlaces`: es xterm.js, que los entiende y los abre."""
        visto: dict = {}

        async def falso(*args, **kw):
            visto["args"] = args
            return mock.Mock(returncode=None)

        async def abrir():
            with mock.patch.object(asyncio, "create_subprocess_exec", falso):
                return await terminal.abrir("Faro", 80, 24)

        _proceso, fd = asyncio.run(abrir())
        os.close(fd)
        self.assertIn("mirar", visto["args"])
        self.assertIn("--enlaces", visto["args"])

    def test_la_pagina_mira_con_el_pty_como_su_terminal(self):
        """`mirar` corre con el PTY como su terminal de control: si no, los cambios de tamaño no le llegan a tmux."""
        visto: dict = {}

        async def falso(*args, **kw):
            visto["args"], visto["kw"] = args, kw
            return mock.Mock(returncode=None)

        async def abrir():
            with mock.patch.object(asyncio, "create_subprocess_exec", falso):
                return await terminal.abrir("Faro", 80, 24)

        _proceso, fd = asyncio.run(abrir())
        os.close(fd)
        args, n = list(visto["args"]), len(terminal.con_terminal([]))
        self.assertEqual(args, terminal.con_terminal(args[n:]))
        self.assertEqual(args[n:n + 3], [sys.executable, "-m", "telar"])
        self.assertTrue(visto["kw"].get("start_new_session"))


#: un hijo que dice el tamaño de su terminal cada vez que el núcleo le avisa que cambió (SIGWINCH)
AVISADO = """import fcntl, signal, struct, sys, termios, time
def dijo(*_):
    filas, columnas = struct.unpack("HHHH", fcntl.ioctl(0, termios.TIOCGWINSZ, bytes(8)))[:2]
    print(f"tamano {columnas}x{filas}", flush=True)
signal.signal(signal.SIGWINCH, dijo)
print("listo", flush=True)
time.sleep(5)
"""


def _leer_hasta(fd: int, fin: bytes, tope: float = 4.0, antes=None) -> bytes:
    """Lo que sale del PTY hasta que aparece `fin` (o el tope); `antes` es (marca, qué hacer) al ver la marca."""
    salida, limite, hecho = b"", time.monotonic() + tope, False
    while time.monotonic() < limite and fin not in salida:
        listos, _, _ = select.select([fd], [], [], 0.05)
        if listos:
            try:
                salida += os.read(fd, 65536)
            except OSError:
                break
        if antes and not hecho and antes[0] in salida:
            antes[1]()
            hecho = True
    return salida


class ElTamanoLeLlega(Prueba):
    """Lo que hace la página al cambiar el tamaño (`_tamano` sobre el PTY) le llega al hijo como SIGWINCH."""

    def correr(self, orden: list[str]) -> bytes:
        principal, secundario = pty.openpty()
        terminal._tamano(principal, 100, 30)
        proceso = subprocess.Popen(orden, stdin=secundario, stdout=secundario, stderr=secundario, start_new_session=True)
        os.close(secundario)
        try:
            return _leer_hasta(principal, b"tamano", antes=(b"listo", lambda: terminal._tamano(principal, 126, 40)))
        finally:
            proceso.kill()
            proceso.wait()
            os.close(principal)

    def test_con_el_pty_como_su_terminal_le_llega(self):
        salida = self.correr(terminal.con_terminal([sys.executable, "-c", AVISADO]))
        self.assertIn(b"tamano 126x40", salida)

    def test_sin_tomarlo_no_le_llega(self):
        """La causa: con `start_new_session` solo, el PTY heredado no es su terminal y el aviso no le llega a nadie."""
        salida = self.correr([sys.executable, "-c", AVISADO])
        self.assertIn(b"listo", salida)
        self.assertNotIn(b"tamano", salida)


VERSION = movil.version_tmux()
HAY_TMUX_CON_ENLACES = bool(shutil.which("tmux")) and bool(movil.rasgos_con_enlaces(VERSION))

#: lo que escribe Claude Code por `[Doc](…)` cuando cree que la terminal entiende hipervínculos (dentro de tmux ≥ 3.4)
URL = "https://docs.google.com/document/d/1AbC-dEf_gh/edit"
ENLACE = f"\x1b]8;;{URL}\x07Doc\x1b]8;;\x07"
#: la misma línea, para el printf de la ventana
PRINTF = ENLACE.replace("\x1b", "\\033").replace("\x07", "\\007")


@unittest.skipUnless(HAY_TMUX_CON_ENLACES, f"sin un tmux 3.4 o más nuevo ({VERSION or 'no hay'})")
class ElEnlaceLlegaALaPagina(Prueba):
    """Una ventana que escribe un enlace como Claude Code, mirada como la mira la página: una sesión agrupada
    (`movil.ordenes_ver`), y el attach de `mirar` en un PTY con TERM=xterm-256color."""

    def setUp(self) -> None:
        super().setUp()
        self.carpeta = tempfile.mkdtemp(prefix="telar-enlaces-")
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)
        self.entorno = {k: v for k, v in os.environ.items() if k != "TMUX"}
        self.entorno.update(TMUX_TMPDIR=self.carpeta, TERM="xterm-256color")
        self.addCleanup(matar_tmux, self.carpeta)
        # sin la configuración de quien corre la prueba (-f /dev/null): la de fábrica, la que no pasa enlaces
        self.tmux("-f", "/dev/null", "new-session", "-d", "-s", "telar", "-x", "100", "-y", "20",
                  f"printf '{PRINTF} fin\\n'; sleep 30")
        self.ventana = self.tmux("display-message", "-p", "-t", "=telar:", "#{window_id}").strip()

    def tmux(self, *args: str) -> str:
        return subprocess.run(["tmux", *args], capture_output=True, text=True, env=self.entorno, timeout=10).stdout

    def mirar(self, vista: str, rasgos: list[str]) -> bytes:
        """Lo que le llega a la terminal de la página hasta que se dibuja la línea («fin», después del enlace)."""
        for orden in movil.ordenes_ver("telar", vista, self.ventana):
            self.tmux(*orden)
        principal, secundario = pty.openpty()
        proceso = subprocess.Popen(["tmux", *rasgos, *movil.enganchar(vista)], stdin=secundario, stdout=secundario,
                                   stderr=secundario, env=self.entorno, start_new_session=True)
        os.close(secundario)
        salida, fin = b"", time.monotonic() + 3
        try:
            while time.monotonic() < fin and b" fin" not in salida:
                listos, _, _ = select.select([principal], [], [], 0.1)
                if listos:
                    try:
                        salida += os.read(principal, 65536)
                    except OSError:
                        break
        finally:
            proceso.kill()
            proceso.wait()
            os.close(principal)
        return salida

    def test_con_enlaces_llega_la_direccion(self):
        salida = self.mirar("ver-con", movil.rasgos_con_enlaces(VERSION))
        self.assertIn(b"Doc", salida)
        # tmux lo reescribe con su id: ESC ] 8 ; id=… ; <url> ESC \
        self.assertRegex(salida, re.compile(rb"\x1b\]8;[^;]*;" + re.escape(URL.encode())))

    def test_sin_enlaces_llega_solo_el_texto(self):
        """La causa: sin declararlo, tmux se come la dirección y deja «Doc» (lo que veía la página)."""
        salida = self.mirar("ver-sin", [])
        self.assertIn(b"Doc", salida)
        self.assertNotIn(URL.encode(), salida)


HAY_TMUX = bool(shutil.which("tmux"))


@unittest.skipUnless(HAY_TMUX, "sin tmux")
class LaVentanaTomaElTamano(Prueba):
    """Lo que se vio: arrastraba el borde de la terminal, la página mandaba el tamaño nuevo y la ventana del hilo
    seguía igual. Una ventana de un tmux propio mirada como la mira la página (una vista agrupada, el attach en un PTY
    en una sesión nueva) y el tamaño cambiado como lo cambia la página."""

    def setUp(self) -> None:
        super().setUp()
        self.carpeta = tempfile.mkdtemp(prefix="telar-tamano-")
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)
        self.entorno = {k: v for k, v in os.environ.items() if k != "TMUX"}
        self.entorno.update(TMUX_TMPDIR=self.carpeta, TERM="xterm-256color")
        self.addCleanup(matar_tmux, self.carpeta)
        self.tmux("-f", "/dev/null", "new-session", "-d", "-s", "telar", "-x", "100", "-y", "30", "sleep 60")
        self.tmux("set-option", "-g", "status", "off")   # sin la barra de estado: la ventana, del alto de la vista
        self.ventana = self.tmux("display-message", "-p", "-t", "=telar:", "#{window_id}").strip()

    def tmux(self, *args: str) -> str:
        return subprocess.run(["tmux", *args], capture_output=True, text=True, env=self.entorno, timeout=10).stdout

    def ancho_tras_cambiar(self, vista: str, envolver) -> str:
        """El tamaño de la ventana después de abrirla en 100×30 y pasarla a 126×40, como la página."""
        for orden in movil.ordenes_ver("telar", vista, self.ventana):
            self.tmux(*orden)
        principal, secundario = pty.openpty()
        terminal._tamano(principal, 100, 30)
        proceso = subprocess.Popen(envolver(["tmux", *movil.enganchar(vista)]), stdin=secundario, stdout=secundario,
                                   stderr=secundario, env=self.entorno, start_new_session=True)
        os.close(secundario)
        medida = lambda: self.tmux("display-message", "-p", "-t", self.ventana, "#{window_width}x#{window_height}").strip()
        try:
            limite = time.monotonic() + 3
            while time.monotonic() < limite and not self.tmux("list-clients", "-t", f"={vista}").strip():
                _leer_hasta(principal, b"\x00", tope=0.1)
            terminal._tamano(principal, 126, 40)
            limite = time.monotonic() + 3
            while time.monotonic() < limite and medida() != "126x40":
                _leer_hasta(principal, b"\x00", tope=0.1)   # que tmux pueda escribir: si nadie lee, se traba
            return medida()
        finally:
            proceso.kill()
            proceso.wait()
            os.close(principal)

    def test_la_ventana_toma_el_tamano_nuevo(self):
        self.assertEqual(self.ancho_tras_cambiar("ver-web-1", terminal.con_terminal), "126x40")

    def test_sin_el_pty_como_su_terminal_se_queda_como_estaba(self):
        """Lo de antes: la ventana quedaba del tamaño con que se abrió la vista."""
        self.assertEqual(self.ancho_tras_cambiar("ver-web-2", lambda orden: orden), "100x30")
