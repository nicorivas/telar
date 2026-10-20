"""`telar mirar` — engancharse a la ventana de un hilo sin tocar lo que ven los demás.

    telar mirar «Faro»                     en esta terminal, la ventana del hilo
    telar mirar «Faro» --vista ver-3-web1  con ese nombre para la sesión que mira

Arma una sesión agrupada con la del telar, fija en la ventana del hilo (la misma forma que usan
las otras máquinas y el celular, `movil.ordenes_ver`), y se engancha a ella. Cambiar de ventana
ahí no le cambia nada a quien mira la sesión del telar; si la ventana muere, la vista suelta a
quien mira; y cuando nadie mira, tmux la borra. Es lo que corre la terminal de un hilo en la
página de telar (telar.terminal, `/pty` de `telar serve --web`).

La vista le da su tamaño a la ventana, como cualquier terminal: con `window-size latest`, manda la
pantalla que se usó último. (Antes, si alguien miraba la sesión del telar, como una terminal de VS Code,
la vista no opinaba del tamaño; con la página como pantalla de trabajo, la ventana quedaba con el tamaño
de esa terminal y tmux rellenaba con puntos lo que sobraba en el navegador.) `--sin-tamano` lo de antes.

Un hilo de otra máquina se mira por su ventana de aquí (la que corre la conexión con allá): si
no tiene, no está abierto en esta máquina, y se dice.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from telar import movil
from telar.ordenes import _comun

AYUDA = "Engancharse a la ventana de un hilo en esta terminal, sin tocar lo que ven los demás."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("mirar", AYUDA)
    p.epilog = __doc__
    p.add_argument("hilo", help="cuál")
    p.add_argument("--vista", default="", help="el nombre de la sesión que mira (uno nuevo por cada terminal)")
    p.add_argument("--sin-tamano", dest="sin_tamano", action="store_true",
                   help="no cambiarle el tamaño a la ventana (lo deja a las otras terminales que la miran)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if not shutil.which("tmux"):
        return _comun.queja("mirar necesita tmux")
    tel = _comun.tejer(ctx, con_ficha=False)
    hilo = tel.por_nombre(o.hilo)
    if hilo is None:
        return _comun.queja(f"no hay un hilo «{o.hilo}»")
    if not tel.vivo(hilo):
        return _comun.queja(f"«{hilo.nombre}» no tiene ventana abierta en esta máquina: retómalo primero")
    ventana = hilo.id
    vista = o.vista or f"ver-{ventana.lstrip('@')}-{os.getpid()}"
    # sin la barra de estado de tmux (la lista de todas las ventanas): la vista es de un solo hilo
    ordenes = [*movil.ordenes_ver(ctx.config.sesion, vista, ventana), ["set-option", "-t", f"={vista}:", "status", "off"]]
    for orden in ordenes:
        r = subprocess.run(["tmux", *orden], capture_output=True, text=True)
        if r.returncode != 0:
            subprocess.run(["tmux", "kill-session", "-t", f"={vista}"], capture_output=True)
            return _comun.queja(f"no pude armar la vista de «{hilo.nombre}»: {r.stderr.strip()}")
    # la vista le da su tamaño a la ventana (manda la pantalla que se usó último), salvo con --sin-tamano.
    # El attach reemplaza a este proceso: la terminal queda conectada a tmux, sin Python en medio
    os.execvp("tmux", ["tmux", *movil.enganchar(vista, sin_tamano=o.sin_tamano)])
    return 0  # no se llega
