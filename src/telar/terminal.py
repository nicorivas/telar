"""La terminal de un hilo en el navegador: `telar mirar <hilo>` en un PTY de esta máquina, conectado a la
página por un WebSocket (`/pty` de `telar.api_web`; en la página, xterm.js).

Mirar arma una sesión agrupada propia sobre la ventana del hilo: escribir aquí es escribir en el hilo, pero
no mueve lo que ven los demás. Al cerrarse la página se cierra el PTY, `mirar` termina y tmux borra la
vista (destroy-unattached).

El protocolo es el que usaba el panel en Node: del servidor salen los bytes de la terminal como texto; de
la página llega JSON, `{"d": "…"}` para teclear y `{"r": [columnas, filas]}` para cambiar el tamaño.
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import json
import os
import pty
import secrets
import signal
import struct
import sys
import termios

#: los límites del tamaño que se acepta de la página
COLUMNAS = (20, 400)
FILAS = (5, 200)


def _medida(valor, limites: tuple[int, int], defecto: int) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return defecto
    return max(limites[0], min(limites[1], n))


def _tamano(fd: int, columnas: int, filas: int) -> None:
    with contextlib.suppress(OSError):
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", filas, columnas, 0, 0))


def _entorno() -> dict[str, str]:
    from telar.mux import tmux

    env = tmux.entorno_para_abrir()
    env["TERM"] = "xterm-256color"
    env.setdefault("LANG", os.environ.get("LANG") or "es_CL.UTF-8")
    return env


async def abrir(hilo: str, columnas: int, filas: int):
    """`telar mirar` en un PTY nuevo, del tamaño pedido: (proceso, fd del lado de telar)."""
    principal, secundario = pty.openpty()
    _tamano(principal, columnas, filas)
    vista = f"ver-web-{secrets.token_hex(3)}"
    try:
        proceso = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "telar", "mirar", hilo, "--vista", vista,
            stdin=secundario, stdout=secundario, stderr=secundario,
            start_new_session=True, cwd=os.path.expanduser("~"), env=_entorno())
    except BaseException:
        os.close(principal)
        raise
    finally:
        os.close(secundario)
    os.set_blocking(principal, False)
    return proceso, principal


def _terminar(proceso) -> None:
    """Cierra la terminal entera (mirar y lo que haya abierto): su grupo de procesos, como al colgar."""
    if proceso.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proceso.pid, signal.SIGHUP)


async def puente(ws, hilo: str, columnas, filas) -> None:
    """Une el WebSocket (ya aceptado) con `telar mirar <hilo>` hasta que uno de los dos se cierre."""
    from starlette.websockets import WebSocketDisconnect

    proceso, fd = await abrir(hilo, _medida(columnas, COLUMNAS, 100), _medida(filas, FILAS, 30))
    bucle = asyncio.get_running_loop()
    salida: asyncio.Queue[bytes | None] = asyncio.Queue()

    def legible() -> None:
        try:
            datos = os.read(fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            datos = b""  # EIO: el proceso cerró la terminal
        if not datos:
            bucle.remove_reader(fd)
            salida.put_nowait(None)
            return
        salida.put_nowait(datos)

    bucle.add_reader(fd, legible)

    async def hacia_la_pagina() -> None:
        # un decodificador incremental: una letra de varios bytes puede venir partida entre dos lecturas
        import codecs

        texto = codecs.getincrementaldecoder("utf-8")("replace")
        while (datos := await salida.get()) is not None:
            await ws.send_text(texto.decode(datos))

    async def desde_la_pagina() -> None:
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                try:
                    m = json.loads(await ws.receive_text())
                except ValueError:
                    continue
                if not isinstance(m, dict):
                    continue
                if isinstance(m.get("d"), str):
                    datos = m["d"].encode("utf-8")
                    while datos:
                        try:
                            datos = datos[os.write(fd, datos):]
                        except BlockingIOError:
                            await asyncio.sleep(0.01)
                        except OSError:
                            return
                r = m.get("r")
                if isinstance(r, list) and len(r) == 2:
                    _tamano(fd, _medida(r[0], COLUMNAS, 100), _medida(r[1], FILAS, 30))

    tareas = [asyncio.create_task(hacia_la_pagina()), asyncio.create_task(desde_la_pagina())]
    try:
        await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tareas:
            t.cancel()
        with contextlib.suppress(ValueError, OSError):
            bucle.remove_reader(fd)
        _terminar(proceso)
        with contextlib.suppress(OSError):
            os.close(fd)
        with contextlib.suppress(asyncio.TimeoutError, ProcessLookupError):
            await asyncio.wait_for(proceso.wait(), 5)
        if proceso.returncode is None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(proceso.pid, signal.SIGKILL)
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await ws.close()
