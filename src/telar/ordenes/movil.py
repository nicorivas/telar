"""`telar movil` — telar en el celular: la lista de hilos de esta máquina, pensada para
una pantalla chica, y entrar a uno sin quedar encerrado.

    mosh usuario@servidor -- ~/.local/bin/telar movil

Corre en el servidor. Flechas o el número eligen, ⏎ o un toque entran, c el correo,
r recarga, q sale. Dentro de un hilo: F12, o tocar «◀ telar» en la barra de arriba, vuelve
aquí; tocar «✉ N» abre el correo encima. Ver `telar.movil` para cómo se consigue sin tocar
lo que ve el laptop, y docs/configuracion.md para la tecla F12 en Termux.

    telar movil --correo     solo el correo entre agentes, para leer (lo que abre «✉ N»)
    telar movil --lista      la lista una vez, sin interfaz (para probar)
"""

from __future__ import annotations

import curses
import os

from telar import correo as mod_correo
from telar import movil as mod_movil
from telar.ordenes import _comun

AYUDA = "telar en el celular: los hilos de esta máquina, y entrar a uno sin quedar encerrado."


def _pendientes(nombres: list[str]) -> dict[str, int]:
    buzon = mod_correo.leer_local()
    return {n: len(cs) for n, cs in mod_correo.por_hilo(mod_correo.pendientes(buzon), nombres).items()}


def _texto_correo() -> str:
    buzon = mod_correo.leer_local(con_cuerpo=True)
    if buzon.error:
        return f"no se pudo leer el correo: {buzon.error}"
    lineas = [f"correo de {buzon.usuario} · {len(buzon.correos)} mensajes", ""]
    for grupo in mod_correo.conversaciones(list(buzon.correos))[:30]:
        lineas.append(f"== {grupo[0].asunto or '(sin asunto)'}")
        for c in grupo:
            lineas.append(f"-- {c.de or '(sistema)'} · {c.fecha[:22]}{' · ' + c.estado if c.estado else ''}")
            lineas += [f"   {l}" for l in (c.cuerpo or "").strip().splitlines()[:40]]
        lineas.append("")
    return "\n".join(lineas)


def _mostrar(pantalla, texto: str) -> None:
    """Un texto largo, con flechas para desplazarse y cualquier otra tecla para salir."""
    lineas = texto.splitlines()
    arriba = 0
    while True:
        pantalla.erase()
        alto, ancho = pantalla.getmaxyx()
        for i, l in enumerate(lineas[arriba:arriba + alto - 1]):
            pantalla.addnstr(i, 0, l, ancho - 1)
        pantalla.addnstr(alto - 1, 0, "↑↓ desplaza · otra tecla vuelve", ancho - 1, curses.A_DIM)
        k = pantalla.getch()
        if k in (curses.KEY_DOWN, ord("j")):
            arriba = min(arriba + 1, max(len(lineas) - alto + 1, 0))
        elif k in (curses.KEY_UP, ord("k")):
            arriba = max(arriba - 1, 0)
        elif k == curses.KEY_NPAGE:
            arriba = min(arriba + alto - 1, max(len(lineas) - alto + 1, 0))
        elif k == curses.KEY_PPAGE:
            arriba = max(arriba - alto + 1, 0)
        elif k != curses.KEY_MOUSE:
            return


def _menu(pantalla) -> tuple[str, object]:
    """Dibuja la lista hasta que se elige algo: ("entrar", hilo), ("correo", None) o ("salir", None)."""
    curses.curs_set(0)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    elegido = 0
    hilos = mod_movil.hilos()
    pend = _pendientes([h.nombre for h in hilos])
    while True:
        pantalla.erase()
        alto, ancho = pantalla.getmaxyx()
        total = sum(pend.values())
        pantalla.addnstr(0, 0, f"telar{f'  ✉ {total}' if total else ''}", ancho - 1, curses.A_BOLD)
        if not hilos:
            pantalla.addnstr(2, 0, "no hay hilos en esta máquina", ancho - 1, curses.A_DIM)
        for i, h in enumerate(hilos[: alto - 3]):
            marca = "●" if h.clientes else "·"
            correo = f" ✉{pend[h.nombre]}" if pend.get(h.nombre) else ""
            linea = f"{i + 1:>2} {marca} {h.nombre}{correo}"
            pantalla.addnstr(2 + i, 0, linea.ljust(ancho - 1), ancho - 1,
                             curses.A_REVERSE if i == elegido else curses.A_NORMAL)
        pantalla.addnstr(alto - 1, 0, "⏎ entra · c correo · r recarga · q sale", ancho - 1, curses.A_DIM)
        k = pantalla.getch()
        if k in (ord("q"), 27):
            return "salir", None
        if k == ord("c"):
            return "correo", None
        if k == ord("r"):
            hilos = mod_movil.hilos()
            pend = _pendientes([h.nombre for h in hilos])
            elegido = min(elegido, max(len(hilos) - 1, 0))
        elif k in (curses.KEY_DOWN, ord("j")) and hilos:
            elegido = (elegido + 1) % len(hilos)
        elif k in (curses.KEY_UP, ord("k")) and hilos:
            elegido = (elegido - 1) % len(hilos)
        elif k in (10, 13, curses.KEY_ENTER) and hilos:
            return "entrar", (hilos[elegido], pend.get(hilos[elegido].nombre, 0))
        elif ord("1") <= k <= ord("9") and k - ord("1") < len(hilos):
            h = hilos[k - ord("1")]
            return "entrar", (h, pend.get(h.nombre, 0))
        elif k == curses.KEY_MOUSE:
            try:
                _, _, y, _, estado = curses.getmouse()
            except curses.error:
                continue
            i = y - 2
            if 0 <= i < len(hilos) and estado & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_RELEASED):
                return "entrar", (hilos[i], pend.get(hilos[i].nombre, 0))


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("movil", AYUDA)
    p.epilog = __doc__
    p.add_argument("--correo", action="store_true", help="solo el correo entre agentes")
    p.add_argument("--lista", action="store_true", help="la lista una vez, sin interfaz")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.lista:
        hilos = mod_movil.hilos()
        pend = _pendientes([h.nombre for h in hilos])
        for h in hilos:
            print(f"{'●' if h.clientes else '·'} {h.nombre}" + (f" ✉{pend[h.nombre]}" if pend.get(h.nombre) else "")
                  + _comun.tenue(f"  {h.sesion}"))
        return 0
    if o.correo:
        curses.wrapper(lambda s: _mostrar(s, _texto_correo()))
        return 0
    if os.environ.get("TMUX"):
        return _comun.queja("telar movil se abre fuera de tmux: es lo que tmux muestra, no algo que corre adentro")
    # el comando que abre «✉ N» desde la barra: este mismo telar, sin depender del PATH
    import shlex
    import sys
    correo_cmd = shlex.join([sys.executable, "-m", "telar", "movil", "--correo"])
    while True:
        accion, dato = curses.wrapper(_menu)
        if accion == "salir":
            return 0
        if accion == "correo":
            curses.wrapper(lambda s: _mostrar(s, _texto_correo()))
            continue
        hilo, pendientes = dato
        try:
            mod_movil.entrar(hilo, pendientes, correo_cmd)
        except RuntimeError as e:
            print(f"no pude entrar a «{hilo.nombre}»: {e}")
            input("⏎ para volver")
