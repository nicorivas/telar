"""Hilos remotos: el agente vive en otra máquina y el hilo local es la ventana que lo mira.

Un hilo remoto es una ventana local que corre

    mosh usuario@servidor -- tmux new-session -A -s <sesion> bash -lc '<cd; agente>'

contra una sesión tmux **propia de ese hilo** en la otra máquina. `-A` hace que la misma
línea sirva para crear y para reconectar: si la sesión remota sigue viva (el laptop se
cerró, el tmux local se reinició), se engancha a ella y el comando del agente no corre
otra vez. Cerrar la ventana local por accidente deja viva la remota; cerrar el hilo desde
telar mata las dos.

La sesión remota se llama `telar-<8 hex>`, elegida al crear y guardada en el estado: no
depende del nombre del hilo, que se puede renombrar, ni de su id local, que no existe
todavía cuando se arma el comando.

Ver docs/propuestas/hilos-remotos.md.
"""

from __future__ import annotations

import shlex
import subprocess
import uuid
from pathlib import PurePosixPath

from telar.config import Remoto

#: cuánto se espera a la otra máquina para matar una sesión o para `doctor`.
ESPERA = 15


def sesion_nueva() -> str:
    """Un nombre de sesión tmux para un hilo remoto nuevo: sin `.` ni `:`, que tmux no admite."""
    return f"telar-{uuid.uuid4().hex[:8]}"


def ruta_remota(remoto: Remoto, relativa: str = "") -> str:
    """La carpeta del hilo en la otra máquina: su vínculo, traducido a la raíz de allá.

    Un vínculo relativo a la raíz local es la misma relativa bajo la raíz remota. Uno
    absoluto (fuera de la raíz local) no tiene traducción, y el agente arranca en la raíz.
    """
    rel = (relativa or "").strip().strip("/")
    if not rel or rel == "." or rel.startswith("..") or relativa.startswith("/"):
        return remoto.raiz
    return str(PurePosixPath(remoto.raiz) / rel)


def carpeta_remota(config, remoto: Remoto, relativa: str = "") -> str:
    """Dónde arranca el agente allá: lo mismo que `[agente] carpeta` dice para aquí.

    «hilo» es la carpeta del hilo traducida a la raíz de allá; «raiz», la raíz de allá; una
    ruta dentro del hogar de aquí (`~/Life`, `/Users/ana/Life`) es la misma bajo el hogar de
    allá. Importa porque hay agentes cuya memoria cuelga de dónde arrancan.
    """
    from pathlib import Path

    donde = getattr(getattr(config, "agente", None), "carpeta", "hilo") or "hilo"
    if donde == "hilo":
        return ruta_remota(remoto, relativa)
    if donde == "raiz":
        return remoto.raiz
    if donde.startswith("~"):
        return donde
    try:
        return "~/" + Path(donde).expanduser().resolve().relative_to(Path.home().resolve()).as_posix()
    except (ValueError, OSError):
        return donde


#: lo que corre allá para dejar una conversación donde Claude Code la busca: la carpeta de
#: proyecto que corresponde al directorio donde va a arrancar (la ruta con todo lo que no es
#: letra o número hecho «-»). `--resume <id>` la encuentra igual desde otra carpeta, pero así
#: queda donde Claude mismo la habría puesto. No pisa una que ya esté.
_DEJAR = r"""
import os, re, sys
carpeta, sid = sys.argv[1], sys.argv[2]
base = os.path.abspath(os.path.expanduser(carpeta))
destino = os.path.join(os.path.expanduser("~/.claude/projects"), re.sub(r"[^A-Za-z0-9]", "-", base))
os.makedirs(destino, exist_ok=True)
ruta = os.path.join(destino, sid + ".jsonl")
if os.path.exists(ruta):
    sys.exit("ya hay una conversación con ese id allá: " + ruta)
datos = sys.stdin.buffer.read()
with open(ruta + ".tmp", "wb") as f:
    f.write(datos)
os.chmod(ruta + ".tmp", 0o600)
os.rename(ruta + ".tmp", ruta)
print(ruta)
"""


def copiar_conversacion(remoto: Remoto, archivo, sid: str, carpeta: str) -> tuple[str, str]:
    """Lleva el `.jsonl` de una conversación a la otra máquina. (ruta allá, error o "")."""
    try:
        datos = open(archivo, "rb").read()
    except OSError as e:
        return "", f"no pude leer la conversación: {e}"
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino,
             shlex.join(["python3", "-c", _DEJAR, carpeta, sid])]
    try:
        r = subprocess.run(orden, input=datos, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", f"{remoto.destino} no responde: {e}"
    if r.returncode != 0:
        return "", (r.stderr.decode(errors="replace").strip() or f"ssh salió con {r.returncode}")[-300:]
    return r.stdout.decode().strip(), ""


def _cd(ruta: str) -> str:
    """`cd` a una ruta remota, con `~` sin citar para que la shell de allá lo expanda."""
    if ruta == "~":
        return "cd ~"
    if ruta.startswith("~/"):
        return f"cd ~/{shlex.quote(ruta[2:])}"
    return f"cd {shlex.quote(ruta)}"


def linea(ruta: str, palabras: list[str] | None, hilo: str) -> str:
    """Lo que corre la sesión remota: ir a la carpeta, el agente, y una shell al salir.

    La shell del final es para que la sesión remota no muera si el agente termina: se
    vuelve a ella y el hilo sigue ahí.
    """
    # lo primero: la sesión se anota su propio nombre (`@telar_hilo`). Desde adentro no hace
    # falta objetivo ni otra conexión; encadenarlo en la línea de tmux no sobrevivía a mosh.
    partes = [f"tmux set-option {OPCION_HILO} {shlex.quote(hilo)} 2>/dev/null",
              f"{_cd(ruta)} 2>/dev/null", f"export TELAR_HILO={shlex.quote(hilo)}"]
    if palabras:
        partes.append(shlex.join(palabras))
    partes.append("exec bash -l")
    return "; ".join(partes)


#: la opción de sesión tmux, allá, con el nombre del hilo: la leen el cartero (para entregar
#: el correo de `usuario+hilo@servidor` a esta sesión) y `telar movil` (para mostrar nombres).
OPCION_HILO = "@telar_hilo"


def comando(remoto: Remoto, sesion: str, linea_remota: str) -> list[str]:
    """El comando de la ventana local: el transporte hasta la otra máquina y su tmux."""
    tmux = ["tmux", "new-session", "-A", "-s", sesion, "bash", "-lc", linea_remota]
    if remoto.transporte == "ssh":
        # ssh junta sus argumentos en una sola línea para la shell remota: va citada entera
        return ["ssh", "-t", remoto.destino, shlex.join(tmux)]
    return ["mosh", remoto.destino, "--", *tmux]


def matar(remoto: Remoto, sesion: str) -> str:
    """Termina la sesión remota de un hilo. Devuelve "" si salió bien, o por qué no.

    Una sesión que ya no existe cuenta como bien: el objetivo era que no estuviera.
    """
    orden = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={ESPERA}", remoto.destino,
             shlex.join(["tmux", "kill-session", "-t", f"={sesion}"])]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=ESPERA + 5)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"no pude hablar con {remoto.destino}: {e}"
    if r.returncode == 0 or "can't find session" in r.stderr or "no server running" in r.stderr:
        return ""
    return (r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:]


def nombrar(remoto: Remoto, sesion: str, hilo: str) -> str:
    """Actualiza `@telar_hilo` en la sesión de allá (al renombrar el hilo). "" si salió bien."""
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino,
             shlex.join(["tmux", "set-option", "-t", f"={sesion}:", OPCION_HILO, hilo])]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"no pude hablar con {remoto.destino}: {e}"
    return "" if r.returncode == 0 else (r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:]


def revisar(remoto: Remoto) -> list[tuple[bool, str]]:
    """Lo que `telar doctor` dice de un remoto: (bien, qué) por cada cosa que mira."""
    import shutil

    salida: list[tuple[bool, str]] = []
    local = "mosh" if remoto.transporte == "mosh" else "ssh"
    salida.append((shutil.which(local) is not None, f"{local} en esta máquina"))
    guion = "command -v tmux >/dev/null && echo tmux-si; tmux show -gv status 2>/dev/null; " + (
        "command -v mosh-server >/dev/null && echo mosh-si" if remoto.transporte == "mosh" else "true")
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino, guion]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [*salida, (False, f"{remoto.destino} no responde: {e}")]
    if r.returncode != 0:
        return [*salida, (False, f"{remoto.destino} no responde por ssh: {r.stderr.strip()[-200:]}")]
    lineas = r.stdout.split()
    salida.append((True, f"{remoto.destino} responde"))
    salida.append(("tmux-si" in lineas, "tmux en la otra máquina"))
    if remoto.transporte == "mosh":
        salida.append(("mosh-si" in lineas, "mosh-server en la otra máquina"))
    if "on" in lineas:
        salida.append((False, "el tmux de allá muestra su barra: `set -g status off` y `set -g prefix None` "
                              "en su ~/.tmux.conf, para que no se vean dos barras ni se coma el prefijo"))
    return salida


def abrir(ctx, tel, nombre: str, remoto: Remoto, *, relativa: str = "", sesion: str = "",
          conversacion: str = "", aviso: str = "") -> str:
    """Abre (o reabre) la ventana local de un hilo remoto, con su marca y su estado.

    Sin `sesion`, es un hilo nuevo: se elige una. Con `conversacion`, el agente la retoma
    (`--resume`) si la sesión remota hay que crearla; si sigue viva, `-A` se engancha a
    ella y el comando no corre. Devuelve el nombre de la sesión remota.
    """
    from telar import agente as mod_agente
    from telar.agente import lanzar

    sesion = sesion or sesion_nueva()
    palabras: list[str] | None = None
    lanz = None
    if ctx.config.agente.nombre:
        agente = mod_agente.obtener(ctx.config.agente.nombre, ctx.config)
        if conversacion:
            palabras = agente.retomar(mod_agente.Conversacion(id=conversacion, hilo=nombre))
            if aviso:
                palabras = [*palabras, aviso]  # el primer mensaje al volver (Claude Code lo acepta así)
        else:
            palabras, sid = agente.nuevo_con_id(aviso)
            lanz = lanzar.Lanzamiento(comando=[], carpeta=None, nueva=sid)
    ventana = comando(remoto, sesion, linea(carpeta_remota(ctx.config, remoto, relativa), palabras, nombre))
    tel.mux.crear_tab(nombre, comando=ventana, foco=True)
    hilo = next((h for h in tel.mux.hilos() if h.nombre == nombre), None)
    if hilo is not None:
        tel.mux.marcar_remoto(hilo.id, remoto.nombre)
    tel.estado.anotar_remoto(nombre, remoto.nombre, sesion)
    lanzar.anotar(ctx.config, nombre, lanz, tel.mux)
    if hilo is not None:
        tel.mux.ir(hilo.id)
    return sesion


def sesiones(remoto: Remoto) -> tuple[list[tuple[str, str]], str]:
    """Las sesiones de hilo que hay allá: (sesión, nombre del hilo), y un error o "".

    Cuenta la que se llama `telar-…` y tiene `@telar_hilo`: la que armó telar desde aquí o
    la que nació allá (un reloj, el celular) siguiendo la misma convención.
    """
    sep = "\x1f"
    formato = sep.join(["#{session_name}", f"#{{{OPCION_HILO}}}"])
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino,
             shlex.join(["tmux", "list-sessions", "-F", formato])]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], f"{remoto.destino} no responde: {e}"
    if r.returncode != 0:
        if "no server running" in r.stderr or "no sessions" in r.stderr:
            return [], ""
        return [], (r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:]
    salida = []
    for renglon in r.stdout.splitlines():
        # algunos tmux devuelven el separador como texto octal (ver telar.mux.tmux.SEP_EN_OCTAL)
        partes = (renglon if sep in renglon else renglon.replace("\\037", sep)).split(sep)
        if len(partes) == 2 and partes[0].startswith("telar-") and partes[1].strip():
            salida.append((partes[0], partes[1].strip()))
    return salida, ""


def nuevas(conocidas: set[str], de_alla: list[tuple[str, str]], nombres: set[str]) -> list[tuple[str, str, str]]:
    """Las sesiones de allá que telar no conoce, con el nombre que tendrá su hilo aquí.

    Una sesión conocida (anotada en el estado, aunque su hilo esté archivado) no se vuelve a
    traer: archivar un hilo remoto no es pedir que reaparezca. Si el nombre ya lo usa otro
    hilo, se le agrega «· 2», «· 3»…  Devuelve (sesión, nombre de allá, nombre de aquí).
    """
    salida, usados = [], set(nombres)
    for sesion, hilo in de_alla:
        if sesion in conocidas:
            continue
        nombre, n = hilo, 2
        while nombre in usados:
            nombre, n = f"{hilo} · {n}", n + 1
        usados.add(nombre)
        salida.append((sesion, hilo, nombre))
    return salida


def traer(tel, remoto: Remoto, sesion: str, nombre: str) -> None:
    """Abre aquí la ventana de una sesión que nació allá, sin quitarle el foco a nadie.

    La línea remota no corre: `-A` se engancha a la sesión que ya existe."""
    tel.mux.crear_tab(nombre, comando=comando(remoto, sesion, "exec bash -l"), foco=False)
    hilo = next((h for h in tel.mux.hilos() if h.nombre == nombre), None)
    if hilo is not None:
        tel.mux.marcar_remoto(hilo.id, remoto.nombre)
    tel.estado.anotar_remoto(nombre, remoto.nombre, sesion)

