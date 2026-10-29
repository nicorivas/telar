"""Hilos remotos: el agente vive en otra máquina y el hilo local es la ventana que lo mira.

Allá, el hilo es una **ventana de la sesión del telar** (`[remotos.<x>] sesion`), como cualquier
hilo de esa máquina. Aquí, una ventana local que corre

    mosh usuario@servidor -- bash -lc '<guion_ver>'

y el guion se engancha a una sesión agrupada con la de allá, fija en esa ventana (ver
`telar.movil.ordenes_ver`): cada máquina que mira elige su ventana sin mover la de las demás.
Crear el hilo es un paso aparte, por ssh, que devuelve su dirección.

La dirección de un hilo remoto es `@338/1a2b3c4d`: la ventana de tmux allá y su marca
(`@telar_id`). tmux reusa los `@N` al reiniciarse; la marca no, y el guion no mira una ventana
cuya marca no coincide. Se guarda en el estado (`remotos.json`), así que renombrar el hilo no la
pierde. Cerrar la ventana local deja vivo el hilo de allá; cerrarlo desde telar mata los dos. Un hilo
anotado sin dirección (vacía) está muerto allá: abrirlo abre una ventana nueva.
"""

from __future__ import annotations

import platform
import re
import shlex
import subprocess
from pathlib import PurePosixPath

from telar.config import Remoto

#: cuánto se espera a la otra máquina para matar una sesión o para `doctor`.
ESPERA = 15
SEP_FORMATO = "\x1f"



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
    ruta dentro del hogar de aquí (`~/vida`, `/Users/ana/vida`) es la misma bajo el hogar de
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
import gzip, os, re, sys
carpeta, sid, esperado = sys.argv[1], sys.argv[2], int(sys.argv[3])
base = os.path.abspath(os.path.expanduser(carpeta))
destino = os.path.join(os.path.expanduser("~/.claude/projects"), re.sub(r"[^A-Za-z0-9]", "-", base))
os.makedirs(destino, exist_ok=True)
ruta = os.path.join(destino, sid + ".jsonl")
if os.path.exists(ruta):
    sys.exit("ya hay una conversación con ese id allá: " + ruta)
datos = gzip.decompress(sys.stdin.buffer.read())
if len(datos) != esperado:
    sys.exit(f"llegaron {len(datos)} de {esperado} bytes: no la guardo (una conversación cortada no se retoma)")
with open(ruta + ".tmp", "wb") as f:
    f.write(datos)
os.chmod(ruta + ".tmp", 0o600)
os.rename(ruta + ".tmp", ruta)
print(ruta)
"""


#: lo que corre allá para saber qué conversación retomar: las que el telar de allá anotó
#: para el hilo (sus ganchos ven lo que pasa dentro de Claude, este lado no), después las
#: que se anotaron aquí, y de todas la primera que tenga archivo. Imprime el id, o nada.
_CONVERSACION = r"""
import glob, json, os, sys
hilo, candidatas = sys.argv[1], sys.argv[2:]
estado = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "telar")
try:
    alla = json.load(open(os.path.join(estado, "sesiones.json"))).get(hilo) or []
    alla = [alla] if isinstance(alla, str) else list(alla)
except (OSError, ValueError, AttributeError):
    alla = []
proyectos = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "projects")
for sid in dict.fromkeys(alla + candidatas):
    if sid and glob.glob(os.path.join(proyectos, "*", glob.escape(sid) + ".jsonl")):
        print(sid)
        break
"""


def conversacion_alla(remoto: Remoto, hilo: str, candidatas) -> tuple[str | None, str]:
    """La conversación de un hilo remoto que se puede retomar allá: (id, error o "").

    El id que se anotó aquí al abrir puede no ser el que quedó: si dentro de Claude se
    hizo `/resume` de otra, Claude escribe en el archivo de esa y el id de aquí nunca
    llega a tener archivo, y `--resume` falla con «No conversation found». Id "" es que
    la otra máquina respondió y no hay ninguna; None, que no respondió y no se sabe.
    """
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino,
             shlex.join(["python3", "-c", _CONVERSACION, hilo, *candidatas])]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"{remoto.destino} no responde: {e}"
    if r.returncode != 0:
        return None, (r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:]
    return r.stdout.strip(), ""


#: lo que corre allá para saber en qué anda cada hilo: el semáforo que anotan sus ganchos.
def copiar_conversacion(remoto: Remoto, archivo, sid: str, carpeta: str) -> tuple[str, str]:
    """Lleva el `.jsonl` de una conversación a la otra máquina. (ruta allá, error o "")."""
    try:
        datos = open(archivo, "rb").read()
    except OSError as e:
        return "", f"no pude leer la conversación: {e}"
    import gzip

    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino,
             shlex.join(["python3", "-c", _DEJAR, carpeta, sid, str(len(datos))])]
    # viaja comprimida: es texto (con imágenes en base64) y pesa la mitad o menos; con la subida de un
    # laptop, 12 MB tardaban cuatro minutos. Allá se descomprime y se revisa el tamaño de lo descomprimido
    comprimida = gzip.compress(datos, 6)
    # una conversación larga pesa decenas de MB y un laptop sube lento: un minuto fijo la cortaba
    # a la mitad. Diez minutos, o 20 KB/s como piso, lo que sea más
    espera = max(600, len(comprimida) / 20_000)
    try:
        r = subprocess.run(orden, input=comprimida, capture_output=True, timeout=espera)
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
    """Lo que corre el hilo: ir a la carpeta, el agente, y una shell al salir.

    La shell del final es para que el hilo no muera si el agente termina: se vuelve a ella y
    sigue ahí.
    """
    partes = [f"{_cd(ruta)} 2>/dev/null", f"export TELAR_HILO={shlex.quote(hilo)}"]
    if palabras:
        partes.append(shlex.join(palabras))
    partes.append("exec bash -l")
    return "; ".join(partes)


def vista(direccion: str) -> str:
    """El nombre de la sesión que mira esa ventana desde aquí: una por ventana y por máquina que
    mira, para que reabrir la ventana local vuelva a la misma en vez de juntar sesiones."""
    from telar import movil

    ventana, _ = movil.partir_direccion(direccion)
    aqui = re.sub(r"[^a-z0-9-]", "", platform.node().split(".")[0].lower())[:20] or "aqui"
    return f"{movil.PREFIJO_VER}{ventana.lstrip('@')}-{aqui}"


def guion_ver(direccion: str, nombre: str) -> str:
    """Lo que corre allá la ventana local de un hilo remoto: mirar su ventana por una sesión fija.

    Revisa la marca antes de armar nada (un `@N` reusado no es el hilo), arma la sesión si no
    está (si está, otra ventana de aquí la dejó y se vuelve a ella) y se engancha. Si la ventana
    ya no existe, lo dice y sale: la ventana local se cierra y nadie mira otro hilo creyendo que
    es este."""
    from telar import movil

    ventana, marca = movil.partir_direccion(direccion)
    v, n = vista(direccion), shlex.quote(nombre)
    hook = f"if-shell -F '#{{!=:#{{window_id}},{ventana}}}' 'detach-client -s ={v}'"
    return "; ".join([
        f"w={ventana}; v={v}",
        "if ! tmux has-session -t \"=$v\" 2>/dev/null; then "
        f"if [ \"$(tmux display -p -t \"$w\" '#{{{movil.OPCION_ID}}}' 2>/dev/null)\" != {marca} ]; then "
        f"echo «{n}» ya no está allá; sleep 5; exit 1; fi; "
        "g=$(tmux display -p -t \"$w\" '#{session_name}'); "
        "tmux new-session -d -t \"=$g\" -s \"$v\" && tmux select-window -t \"=$v:$w\" && "
        f"tmux set-hook -t \"=$v:\" session-window-changed {shlex.quote(hook)} || "
        f"{{ tmux kill-session -t \"=$v\" 2>/dev/null; echo no pude mirar «{n}»; sleep 5; exit 1; }}; fi",
        "exec tmux attach-session -t \"=$v\" \\; set-option -t \"=$v:\" destroy-unattached on",
    ])


def comando(remoto: Remoto, direccion: str, nombre: str = "") -> list[str]:
    """El comando de la ventana local: el transporte hasta la otra máquina, y allá, mirar la ventana
    del hilo (`direccion`, «@338/marca»)."""
    remoto_cmd = ["bash", "-lc", guion_ver(direccion, nombre or direccion)]
    if remoto.transporte == "ssh":
        # ssh junta sus argumentos en una sola línea para la shell remota: va citada entera
        return ["ssh", "-t", remoto.destino, shlex.join(remoto_cmd)]
    return ["mosh", remoto.destino, "--", *remoto_cmd]


def _ssh(remoto: Remoto, guion: str, espera: int = ESPERA) -> tuple[int, str, str]:
    """Corre `guion` (bash) en la otra máquina. (código, salida, error); 255 si no se pudo hablar."""
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino, shlex.join(["bash", "-lc", guion])]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=espera)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 255, "", f"no pude hablar con {remoto.destino}: {e}"
    return r.returncode, r.stdout, r.stderr


def principal(config, remoto: Remoto) -> str:
    """La sesión del telar allá: la que dice `[remotos.<x>] sesion`, o la misma de aquí."""
    return remoto.sesion or config.sesion


def crear_alla(config, remoto: Remoto, nombre: str, linea_remota: str) -> str:
    """Abre el hilo allá como ventana de la sesión del telar y devuelve su dirección («@338/marca»).

    Si la sesión del telar no existe allá, nace con esta ventana. Lanza ErrorDeMux si no se pudo."""
    from telar import movil
    from telar.mux import ErrorDeMux

    p, marca = principal(config, remoto), movil.marca_nueva()
    nueva = shlex.join(movil.ordenes_ventana(p, nombre, "", None, viva=True)[:-1] + [linea_remota])
    primera = shlex.join(movil.ordenes_ventana(p, nombre, "", None, viva=False)[:-1] + [linea_remota])
    guion = (f"if tmux has-session -t {shlex.quote('=' + p)} 2>/dev/null; then w=$(tmux {nueva}); "
             f"else w=$(tmux {primera}); fi && tmux set-option -w -t \"$w\" {movil.OPCION_ID} {marca} && echo \"$w\"")
    codigo, salida, error = _ssh(remoto, guion)
    ventana = salida.strip().splitlines()[-1] if salida.strip() else ""
    if codigo != 0 or not ventana.startswith("@"):
        raise ErrorDeMux(f"no pude abrir «{nombre}» en {remoto.destino}: {(error.strip() or salida.strip())[-300:]}")
    return f"{ventana}/{marca}"


def vive(remoto: Remoto, direccion: str) -> bool | None:
    """¿Sigue allá el hilo de esa dirección? None si no se pudo preguntar."""
    from telar import movil

    ventana, marca = movil.partir_direccion(direccion)
    if not ventana:
        return False  # sin dirección: no hay nada vivo allá que mirar
    guion = f"tmux display -p -t {ventana} '#{{{movil.OPCION_ID}}}' 2>/dev/null"
    codigo, salida, _ = _ssh(remoto, guion)
    if codigo == 255:
        return None
    return salida.strip() == marca


def matar(remoto: Remoto, direccion: str) -> str:
    """Cierra allá la ventana de un hilo. Devuelve "" si salió bien, o por qué no.

    Una ventana que ya no existe (o un hilo sin dirección) cuenta como bien: el objetivo era que no
    estuviera. Solo se cierra si su marca es la de la dirección: un `@N` reusado es otro hilo.
    """
    from telar import movil

    ventana, marca = movil.partir_direccion(direccion)
    if not ventana:
        return ""
    guion = (f"[ \"$(tmux display -p -t {ventana} '#{{{movil.OPCION_ID}}}' 2>/dev/null)\" = {marca} ] "
             f"&& tmux kill-window -t {ventana}; true")
    codigo, _, error = _ssh(remoto, guion, ESPERA + 5)
    return "" if codigo == 0 else (error.strip() or f"ssh salió con {codigo}")[-300:]


def nombrar(remoto: Remoto, direccion: str, hilo: str) -> str:
    """Le pone el nombre nuevo a la ventana del hilo allá (al renombrarlo aquí). "" si salió bien, o si
    el hilo no tiene dirección (no hay ventana que nombrar)."""
    from telar import movil

    ventana, marca = movil.partir_direccion(direccion)
    if not ventana:
        return ""
    guion = (f"[ \"$(tmux display -p -t {ventana} '#{{{movil.OPCION_ID}}}' 2>/dev/null)\" = {marca} ] "
             f"&& tmux rename-window -t {ventana} {shlex.quote(hilo)}")
    codigo, _, error = _ssh(remoto, guion)
    return "" if codigo == 0 else (error.strip() or "la ventana de allá ya no es ese hilo")[-300:]


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

    Con `sesion` (la dirección que se guardó) y el hilo vivo allá, solo se vuelve a mirarlo. Si
    no, se abre allá una ventana nueva en la sesión del telar; con `conversacion`, el agente la
    retoma (`--resume`). Devuelve la dirección del hilo allá.
    """
    from telar import agente as mod_agente
    from telar.agente import lanzar

    if sesion and vive(remoto, sesion):
        traer(tel, remoto, sesion, nombre, foco=True)
        return sesion
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
    sesion = crear_alla(ctx.config, remoto, nombre, linea(carpeta_remota(ctx.config, remoto, relativa), palabras, nombre))
    # apenas nace allá, el nodo de aquí puede enterarse por el bus y traer su ventana (`traer`) antes que esta línea:
    # bajo el mismo candado, y si ya está, se usa esa (si no, quedaban dos ventanas iguales del mismo hilo)
    with tel.estado.bajo_candado():
        abierta = ventana_abierta(tel, nombre)
        if abierta is None:
            tab = tel.mux.crear_tab(nombre, comando=comando(remoto, sesion, nombre), foco=True)
            # por id, no por nombre: si ya hay otra ventana con ese nombre, la marca y el foco irían a ella
            tel.mux.marcar_remoto(tab.id, remoto.nombre)
            abierta = tab.id
        tel.estado.anotar_remoto(nombre, remoto.nombre, sesion)
    lanzar.anotar(ctx.config, nombre, lanz, tel.mux)
    tel.mux.ir(abierta)
    return sesion


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


def traer(tel, remoto: Remoto, sesion: str, nombre: str, *, foco: bool = False) -> None:
    """Abre aquí la ventana de un hilo que vive allá (su dirección en `sesion`), sin quitarle el
    foco a nadie salvo que se pida. Allá no corre nada nuevo: solo se lo mira."""
    # Varias instancias reabren a la vez (el nodo, el sondeo de la página, un `retomar`): sin el candado,
    # cada una ve que «no hay ventana» antes de que la otra la cree y se abren N iguales
    with tel.estado.bajo_candado():
        abierta = ventana_abierta(tel, nombre)
        if abierta is None:
            tab = tel.mux.crear_tab(nombre, comando=comando(remoto, sesion, nombre), foco=foco)
            # se marca la ventana que se acaba de crear, por su id: buscarla por nombre encuentra la primera con
            # ese nombre, que puede ser otra
            tel.mux.marcar_remoto(tab.id, remoto.nombre)
            abierta = tab.id
        tel.estado.anotar_remoto(nombre, remoto.nombre, sesion)
    if foco:
        tel.mux.ir(abierta)


def ventana_abierta(tel, nombre: str) -> str | None:
    """El id de la ventana viva de un hilo remoto con ese nombre, o None.

    Cuenta la que telar marcó y también la que corre un mosh/ssh sin marca (`remoto == "?"`): las dos ya miran
    la sesión de allá, y abrir otra solo duplica la vista."""
    return next((h.id for h in tel.mux.hilos() if h.nombre == nombre and h.remoto), None)

