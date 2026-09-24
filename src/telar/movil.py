"""telar en el celular: los hilos de esta máquina, y entrar a uno sin quedar encerrado.

Corre **en el servidor** (`mosh usuario@servidor -- telar movil`). Los hilos remotos son
sesiones tmux de esta máquina (`telar-1a2b3c4d`), cada una con su nombre en `@telar_hilo`.

El problema que resuelve: el tmux de aquí va sin barra y sin prefijo, para ser invisible
cuando se lo mira desde el tmux del laptop. Si el celular se engancha a esa sesión, Claude
ocupa toda la pantalla y no hay cómo volver. Por eso el celular no se engancha a la sesión
del hilo sino a una **sesión agrupada** con ella (`movil-1a2b3c4d`): comparte las ventanas
—el mismo Claude— pero tiene opciones propias. Esa sesión tiene barra arriba, mouse, y su
**propia tabla de teclas**: F12 o tocar «◀ telar» vuelven al menú, y el laptop, enganchado
a la sesión original, no ve nada de eso. Al volver, la agrupada se mata; la del hilo sigue.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

#: la tabla de teclas de las sesiones del celular: lo que se ata aquí no toca al laptop.
TABLA = "telar-movil"
PREFIJO = "movil-"
OPCION_HILO = "@telar_hilo"


@dataclass(frozen=True, slots=True)
class HiloMovil:
    sesion: str
    nombre: str
    clientes: int = 0
    ventanas: int = 1


def _tmux(*args: str, tolerante: bool = False) -> str:
    r = subprocess.run(["tmux", *args], capture_output=True, text=True)
    if r.returncode != 0 and not tolerante:
        raise RuntimeError(r.stderr.strip() or f"tmux {args[0]} salió con {r.returncode}")
    return r.stdout


def hilos() -> list[HiloMovil]:
    """Las sesiones de esta máquina que son hilos: las que tienen `@telar_hilo`, o se llaman
    `telar-…`. Las sesiones del propio celular (`movil-…`) no cuentan."""
    sep = "\x1f"
    salida = _tmux("list-sessions", "-F", sep.join(
        ["#{session_name}", f"#{{{OPCION_HILO}}}", "#{session_attached}", "#{session_windows}"]), tolerante=True)
    lista = []
    for renglon in salida.splitlines():
        # algunos tmux devuelven el separador como texto octal (ver telar.mux.tmux.SEP_EN_OCTAL)
        partes = (renglon if sep in renglon else renglon.replace("\\037", sep)).split(sep)
        if len(partes) != 4:
            continue
        sesion, nombre, clientes, ventanas = partes
        if sesion.startswith(PREFIJO) or not (nombre or sesion.startswith("telar-")):
            continue
        lista.append(HiloMovil(sesion=sesion, nombre=nombre or sesion,
                               clientes=int(clientes) if clientes.isdigit() else 0,
                               ventanas=int(ventanas) if ventanas.isdigit() else 1))
    lista.sort(key=lambda h: h.nombre.casefold())
    return lista


def barra(nombre: str, correos: int = 0) -> str:
    """La línea de arriba en el celular: «◀ telar · ✉ 2 · Pizza», con rangos tocables."""
    correo = f" · #[range=user|correo]✉ {correos}#[norange]" if correos else ""
    nombre_seguro = nombre.replace("#", "##")  # un # en el nombre no es un formato de tmux
    return f"#[range=user|volver]#[reverse] ◀ telar #[noreverse]#[norange]{correo} · {nombre_seguro}"


def ordenes_grupo(sesion: str, grupo: str, nombre: str, correos: int = 0, correo_cmd: str = "") -> list[list[str]]:
    """Los comandos tmux que arman la sesión agrupada del celular. Puros: se prueban sin tmux."""
    t = f"={grupo}:"  # set-option apunta a un panel: sin los dos puntos, tmux no resuelve la sesión
    ordenes = [
        ["new-session", "-d", "-t", f"={sesion}", "-s", grupo],
        ["set-option", "-t", t, "status", "on"],
        ["set-option", "-t", t, "status-position", "top"],
        ["set-option", "-t", t, "status-left-length", "80"],
        ["set-option", "-t", t, "status-left", barra(nombre, correos)],
        ["set-option", "-t", t, "status-right", ""],
        ["set-option", "-t", t, "window-status-format", ""],
        ["set-option", "-t", t, "window-status-current-format", ""],
        ["set-option", "-t", t, "mouse", "on"],
        ["set-option", "-t", t, "key-table", TABLA],
        # la tabla es global al servidor tmux, pero solo la usan las sesiones que la eligen
        ["bind-key", "-T", TABLA, "F12", "detach-client"],
        # tocar la barra: «◀ telar» vuelve al menú; «✉ N» abre el correo encima, sin salir
        ["bind-key", "-T", TABLA, "MouseDown1Status",
         "if-shell", "-F", "#{==:#{mouse_status_range},volver}", "detach-client",
         *([f"if-shell -F '#{{==:#{{mouse_status_range}},correo}}' "
            f"\"display-popup -E -w 100% -h 100% '{correo_cmd}'\""] if correo_cmd else [])],
        # la rueda del mouse sigue desplazando lo que hay en pantalla
        ["bind-key", "-T", TABLA, "WheelUpPane", "if-shell", "-F", "#{mouse_any_flag}",
         "send-keys -M", "copy-mode -e; send-keys -M"],
    ]
    return ordenes


def entrar(h: HiloMovil, correos: int = 0, correo_cmd: str = "") -> None:
    """Engancha el celular al hilo por una sesión agrupada; vuelve cuando se sale de ella."""
    grupo = f"{PREFIJO}{h.sesion.removeprefix('telar-')}"
    _tmux("kill-session", "-t", f"={grupo}", tolerante=True)  # una que quedó de otra vez
    try:
        for orden in ordenes_grupo(h.sesion, grupo, h.nombre, correos, correo_cmd):
            _tmux(*orden)
        subprocess.run(["tmux", "attach-session", "-t", f"={grupo}"])
    finally:
        _tmux("kill-session", "-t", f"={grupo}", tolerante=True)
