r"""`telar imagen` — llevar una imagen de este computador a la máquina donde corre el hilo.

    telar imagen                    la imagen que hay en el portapapeles
    telar imagen captura.png        un archivo
    telar imagen --remoto telar     a qué máquina de [remotos] (por defecto, la única)
    telar imagen --pegar %3         lo que hace Ctrl+V en un hilo de otra máquina (ver abajo)

Para que Ctrl+V funcione tal cual en un hilo que vive en otra máquina, el tmux de ESTE computador lo
engancha (`~/.tmux.conf`): si el panel corre mosh, `--pegar` sube la imagen del portapapeles y
**escribe su ruta en el panel**; si no hay imagen, sale con 1 y el atajo manda el Ctrl+V de siempre:

    bind -n C-v if-shell -F '#{==:#{pane_current_command},mosh-client}' \
        "run-shell -b \"telar imagen --pegar #{pane_id} || tmux send-keys -t #{pane_id} C-v\"" "send-keys C-v"

Claude Code pega imágenes (Ctrl+V) leyendo el portapapeles de la máquina donde corre; un hilo que
vive en el servidor no ve el de tu laptop, y un terminal solo transporta texto. Esto sube la imagen
por ssh a `~/telar-entrada/` de la otra máquina, imprime la ruta que tiene allá y la deja en tu
portapapeles: pégala en el hilo (Cmd+V) y Claude la lee como cualquier archivo.
"""

from __future__ import annotations

import datetime
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from telar.ordenes import _comun

AYUDA = "Llevar una imagen del portapapeles (o un archivo) a la máquina donde corre el hilo."
CARPETA = "telar-entrada"
MAX_BYTES = 20 * 1024 * 1024
FORMATOS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def del_portapapeles(destino: Path) -> str:
    """Guarda en `destino` (PNG) la imagen del portapapeles. "" si lo logró; si no, por qué no."""
    if sys.platform == "darwin":
        if shutil.which("pngpaste"):
            r = subprocess.run(["pngpaste", str(destino)], capture_output=True, text=True)
        else:  # sin Homebrew: AppleScript lee el portapapeles como PNG
            r = subprocess.run(["osascript",
                                "-e", f'set f to open for access POSIX file "{destino}" with write permission',
                                "-e", "try", "-e", "write (the clipboard as «class PNGf») to f", "-e", "on error",
                                "-e", "close access f", "-e", 'error "no hay imagen en el portapapeles"', "-e", "end try",
                                "-e", "close access f"], capture_output=True, text=True)
    elif shutil.which("wl-paste"):
        r = subprocess.run(f"wl-paste --type image/png > {shlex.quote(str(destino))}", shell=True, capture_output=True, text=True)
    elif shutil.which("xclip"):
        r = subprocess.run(f"xclip -selection clipboard -t image/png -o > {shlex.quote(str(destino))}", shell=True, capture_output=True, text=True)
    else:
        return "no sé leer el portapapeles de este sistema: pásame el archivo (telar imagen archivo.png)"
    if r.returncode != 0 or not destino.exists() or destino.stat().st_size == 0:
        return (r.stderr.strip().splitlines() or ["no hay una imagen en el portapapeles"])[-1]
    return ""


def con_sufijo(nombre: str, n: int) -> str:
    """`informe.pdf` con su sufijo `n`: `informe-2.pdf`. Lo que se usa cuando ya hay uno con ese nombre."""
    p = Path(nombre)
    return f"{p.stem}-{n}{p.suffix}"


def subir(remoto, ruta: Path, nombre: str, espera: float = 60) -> tuple[str, str]:
    """Copia `ruta` a ~/telar-entrada/<nombre> en la otra máquina, sin pisar uno que ya esté ahí: si el nombre
    está tomado, `con_sufijo` (-2, -3…). (ruta allá, "") o ("", por qué no). `espera`: los segundos que puede
    tardar la copia entera (un archivo grande por una red lenta tarda más que una captura)."""
    p = Path(nombre)
    # el archivo se crea con noclobber (set -C): crearlo y ver que no existía es una sola operación, así dos
    # copias a la vez no eligen el mismo nombre
    guion = (f"mkdir -p ~/{CARPETA} && cd ~/{CARPETA} && n={shlex.quote(nombre)} && i=2 && "
             f"until (set -C; : > \"$n\") 2>/dev/null; do "
             f"[ $i -le 999 ] || {{ echo 'no hay un nombre libre en ~/{CARPETA}' >&2; exit 1; }}; "
             f"n={shlex.quote(p.stem)}-$i{shlex.quote(p.suffix)}; i=$((i+1)); done && "
             f"cat > \"$n\" && echo \"$HOME/{CARPETA}/$n\"")
    try:
        with ruta.open("rb") as f:
            r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino,
                                shlex.join(["bash", "-lc", guion])], stdin=f, capture_output=True, text=True, timeout=espera)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", f"no pude hablar con {remoto.destino}: {e}"
    if r.returncode != 0:
        return "", (r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:]
    return r.stdout.strip().splitlines()[-1], ""


def al_portapapeles(texto: str) -> bool:
    for orden in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(orden[0]):
            return subprocess.run(orden, input=texto, text=True).returncode == 0
    return False


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("imagen", AYUDA)
    p.epilog = __doc__
    p.add_argument("archivo", nargs="?", default="", help="una imagen; sin él, la del portapapeles")
    p.add_argument("--remoto", default="", help="la máquina de [remotos] (por defecto, la única)")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    p.add_argument("--pegar", default="", metavar="PANEL",
                   help="como Ctrl+V: sube la imagen del portapapeles y escribe su ruta en ese panel de tmux; sin imagen, sale con 1")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    remotos = [r for r in ctx.config.remotos if not o.remoto or r.nombre == o.remoto]
    if len(remotos) != 1:
        return _comun.queja("no hay máquinas en [remotos]" if not remotos else
                            f"hay varias máquinas ({', '.join(r.nombre for r in remotos)}): elige con --remoto")
    ahora = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    with tempfile.TemporaryDirectory() as tmp:
        if o.archivo:
            origen = Path(o.archivo).expanduser()
            if not origen.is_file() or origen.suffix.lower() not in FORMATOS:
                return _comun.queja(f"«{o.archivo}» no es una imagen ({', '.join(sorted(FORMATOS))})")
            nombre = f"{origen.stem}-{ahora}{origen.suffix.lower()}".replace(" ", "-")
        else:
            origen = Path(tmp) / "portapapeles.png"
            problema = del_portapapeles(origen)
            if problema:
                return 1 if o.pegar else _comun.queja(problema)  # sin imagen, --pegar deja que el Ctrl+V siga
            nombre = f"portapapeles-{ahora}.png"
        if origen.stat().st_size > MAX_BYTES:
            return _comun.queja(f"la imagen pesa más de {MAX_BYTES // (1024 * 1024)} MB")
        ruta, problema = subir(remotos[0], origen, nombre)
    if problema:
        if o.pegar:  # no hay a quién quejarse: el atajo corre sin terminal
            subprocess.run(["tmux", "display-message", "-d", "4000", f"telar imagen: no se subió: {problema}"], capture_output=True)
            return 0
        return _comun.queja(f"no se subió: {problema}")
    if o.pegar:
        # la ruta como texto, sin Enter: la persona la ve en su input y decide
        return subprocess.run(["tmux", "send-keys", "-t", o.pegar, "-l", ruta], capture_output=True).returncode
    copiada = al_portapapeles(ruta)
    if o.json:
        return _comun.escribir_json({"ruta": ruta, "remoto": remotos[0].nombre, "portapapeles": copiada})
    print(ruta)
    print("(la ruta está en tu portapapeles: pégala en el hilo)" if copiada else "(copia la ruta y pégala en el hilo)", file=sys.stderr)
    return 0
