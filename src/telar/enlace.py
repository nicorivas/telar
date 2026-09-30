"""La puerta: llamar de una máquina a otra sin abrirle un shell a nadie.

El laptop se apaga y el servidor no; el servidor corre agentes y el laptop tiene lo que a veces
hace falta (una carpeta, un hilo, la pantalla). Para que el servidor pueda pedirle cosas al
laptop hay una **puerta con una sola llave**:

    servidor:  ssh -i ~/.ssh/telar_enlace laptop  ping
    laptop:    authorized_keys:  restrict,command="/…/telar enlace servir"  ssh-ed25519 AAAA… telar-enlace

La llave del servidor solo puede ejecutar `telar enlace servir` en el laptop —eso lo impone sshd, no
esta librería—, y `servir` solo cumple lo que está en `VERBOS_ENLACE` y en `[enlace] verbos`. No hay
shell, ni ejecución de comandos, ni lectura de archivos: un servidor comprometido puede pedir
esos cinco verbos y nada más. `restrict` apaga además el terminal, los túneles y el agente ssh.

    ping         ¿estás? — responde quién es y qué verbos tiene
    hilos        la foto de sus hilos (la misma del espejo)
    archivo N    recibe un archivo por la entrada estándar y lo deja en `[enlace] entrada`
    enviar H     escribe el texto de la entrada estándar en el hilo H (con `enter`, y lo manda)
    notificar    muestra un aviso en pantalla con el texto de la entrada estándar

Todo lo que llega es dato hostil: los nombres de archivo se limpian y nunca escapan de la carpeta de
entrada, un archivo nunca pisa a otro, los tamaños tienen tope, y a un hilo solo se le escribe si
existe y está vivo. Cada petición queda anotada en `<estado>/enlace.log`. El contrato está en
docs/contratos.md.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from telar import __version__
from telar import espejo
from telar.config import VERBOS_ENLACE

#: los topes de lo que entra por la entrada estándar (bytes), por verbo
MAX_ARCHIVO = 100 * 1024 * 1024
MAX_TEXTO = 8000
MAX_AVISO = 500
LIMITE = {"archivo": MAX_ARCHIVO, "enviar": MAX_TEXTO * 4, "notificar": MAX_AVISO * 4}


class ErrorDePuerta(Exception):
    """Una petición que la puerta no cumple. El mensaje es lo que se le dice a quien llamó."""


# ── lo que llega, limpio ───────────────────────────────────

def nombre_de_archivo(crudo: str) -> str:
    """El nombre que puede tener un archivo que llega: sin carpetas, sin puntos delante, sin rarezas."""
    base = os.path.basename(crudo.replace("\\", "/"))
    limpio = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .")[:100]
    return limpio or "archivo"


def carpeta_de_entrada(config) -> Path:
    return Path(config.puerta.entrada).expanduser()


def guardar_archivo(config, nombre: str, datos: bytes) -> Path:
    """Deja el archivo en la carpeta de entrada. Nunca pisa uno que ya esté: agrega -1, -2…"""
    if len(datos) > MAX_ARCHIVO:
        raise ErrorDePuerta(f"el archivo pesa más de {MAX_ARCHIVO // (1024 * 1024)} MB")
    if not datos:
        raise ErrorDePuerta("el archivo llegó vacío")
    carpeta = carpeta_de_entrada(config)
    carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
    limpio = nombre_de_archivo(nombre)
    raiz, punto, ext = limpio.rpartition(".")
    base, sufijo = (raiz, punto + ext) if raiz else (limpio, "")
    for n in range(0, 1000):
        destino = carpeta / (limpio if n == 0 else f"{base}-{n}{sufijo}")
        try:
            fd = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # EXCL: si ya está, no lo toca
        except FileExistsError:
            continue
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        return destino
    raise ErrorDePuerta("no encontré un nombre libre para ese archivo")


# ── los verbos ─────────────────────────────────────────────

def _sin_argumentos(verbo: str, args: list[str]) -> None:
    if args:
        raise ErrorDePuerta(f"«{verbo}» no lleva argumentos")


def _ping(ctx, args, entrada):
    _sin_argumentos("ping", args)
    return {"maquina": espejo.nombre_de_esta_maquina(), "telar": __version__,
            "hora": datetime.now().astimezone().isoformat(timespec="seconds"), "verbos": list(ctx.config.puerta.verbos)}


def _hilos(ctx, args, entrada):
    _sin_argumentos("hilos", args)
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx)
    return {"foto": espejo.foto(tel, maquina=espejo.nombre_de_esta_maquina(), version_telar=__version__)}


def _archivo(ctx, args, entrada):
    if len(args) != 1:
        raise ErrorDePuerta("«archivo» lleva un argumento: el nombre")
    destino = guardar_archivo(ctx.config, args[0], entrada)
    return {"ruta": str(destino), "bytes": len(entrada), "sha256": hashlib.sha256(entrada).hexdigest()}


def _enviar(ctx, args, entrada):
    if not args or len(args) > 2 or (len(args) == 2 and args[1] != "enter"):
        raise ErrorDePuerta("«enviar» lleva el hilo y, si quieres mandarlo, «enter»")
    try:
        texto = entrada.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ErrorDePuerta("el texto no es UTF-8") from e
    if not texto.strip():
        raise ErrorDePuerta("no hay nada que escribir")
    if len(texto) > MAX_TEXTO:
        raise ErrorDePuerta(f"el texto pasa de {MAX_TEXTO} caracteres")
    enter = len(args) == 2
    if ("\n" in texto or "\r" in texto) and not enter:
        raise ErrorDePuerta("un texto con saltos de línea solo se puede mandar con «enter»")
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx, con_ficha=False)
    hilo = tel.por_nombre(args[0])
    if hilo is None or not tel.vivo(hilo):
        raise ErrorDePuerta(f"no hay un hilo vivo que se llame «{args[0]}»")
    if tel.mux is None:
        raise ErrorDePuerta(tel.aviso or "no hay multiplexor donde escribir")
    tel.mux.escribir(hilo.nombre, texto, enviar=enter)
    return {"hilo": hilo.nombre, "caracteres": len(texto), "enviado": enter}


def _notificar(ctx, args, entrada):
    if len(args) > 1:
        raise ErrorDePuerta("«notificar» lleva, si acaso, un título")
    texto = entrada.decode("utf-8", "replace").strip()[:MAX_AVISO]
    if not texto:
        raise ErrorDePuerta("no hay texto que mostrar")
    titulo = (args[0] if args else "telar")[:60]
    # el texto va por variables de entorno, no dentro del script: no hay nada que escapar
    entorno = {**os.environ, "TELAR_TEXTO": texto, "TELAR_TITULO": titulo}
    if sys.platform == "darwin" and shutil.which("osascript"):
        orden = ["osascript", "-e", 'display notification (system attribute "TELAR_TEXTO") '
                 'with title (system attribute "TELAR_TITULO")']
    elif shutil.which("notify-send"):
        orden = ["notify-send", "--", titulo, texto]
    else:
        raise ErrorDePuerta("esta máquina no sabe mostrar avisos")
    r = subprocess.run(orden, env=entorno, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise ErrorDePuerta(f"el aviso no salió: {(r.stderr or '').strip()[-200:]}")
    return {"titulo": titulo, "caracteres": len(texto)}


VERBO = {"ping": _ping, "hilos": _hilos, "archivo": _archivo, "enviar": _enviar, "notificar": _notificar}
assert set(VERBO) == set(VERBOS_ENLACE)


def verbo_de(pedido: str) -> str:
    """El verbo de una petición, o "" si no se entiende. Sirve para saber cuánto leer de la entrada."""
    try:
        partes = shlex.split(pedido or "")
    except ValueError:
        return ""
    return partes[0] if partes else ""


def servir(ctx, pedido: str, entrada: bytes = b"") -> dict:
    """Cumple una petición (la línea que dijo quien llamó) o dice por qué no. Siempre devuelve un dict
    con `ok`; nunca levanta: quien llama por ssh solo ve lo que se imprime."""
    verbo = ""
    try:
        try:
            partes = shlex.split(pedido or "")
        except ValueError as e:
            raise ErrorDePuerta("petición mal formada") from e
        if not partes:
            raise ErrorDePuerta("no dijiste qué querías: esta puerta no da terminal")
        verbo, args = partes[0], partes[1:]
        if verbo not in VERBO or verbo not in ctx.config.puerta.verbos:
            hay = ", ".join(v for v in VERBOS_ENLACE if v in ctx.config.puerta.verbos)
            raise ErrorDePuerta(f"esta puerta no hace «{verbo[:40]}» (hace: {hay})")
        if len(entrada) > LIMITE.get(verbo, 0):
            raise ErrorDePuerta("lo que mandaste pesa más de lo que este verbo acepta")
        respuesta = {"ok": True, "verbo": verbo, **VERBO[verbo](ctx, args, entrada)}
        _anotar(ctx, verbo, "ok", len(entrada))
        return respuesta
    except ErrorDePuerta as e:
        _anotar(ctx, verbo or "?", f"no: {e}", len(entrada))
        return {"ok": False, "verbo": verbo, "error": str(e)}
    except Exception as e:  # noqa: BLE001 - un fallo interno se dice, no revienta con traza hacia afuera
        _anotar(ctx, verbo or "?", f"falló: {type(e).__name__}", len(entrada))
        return {"ok": False, "verbo": verbo, "error": f"falló por dentro: {type(e).__name__}: {e}"[:300]}


def _anotar(ctx, verbo: str, resultado: str, tamano: int) -> None:
    """Una línea por petición en `<estado>/enlace.log`. Si no se puede escribir, la puerta sigue."""
    try:
        ruta = Path(ctx.config.estado) / "enlace.log"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().astimezone().isoformat(timespec='seconds')}\t{verbo}\t{tamano}\t{resultado[:200]}\n")
    except OSError:
        pass


# ── el lado que llama (el servidor) ────────────────────────

def llamar(enlace, verbo: str, args: list[str] | None = None, entrada: bytes | None = None,
           *, espera: float | None = None) -> dict:
    """Pide algo a la otra máquina. Siempre devuelve un dict con `ok`; los fallos de red van en `error`."""
    orden_remota = shlex.join([verbo, *(args or [])])
    llave = str(Path(enlace.llave).expanduser())
    if not Path(llave).exists():
        return {"ok": False, "verbo": verbo, "error": f"no existe la llave {llave}: `telar enlace instalar` la crea"}
    if espera is None:
        espera = 20 + len(entrada or b"") / 150_000  # ~150 KB/s como piso: un archivo grande necesita más
    orden = ["ssh", "-i", llave, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
             "-o", "StrictHostKeyChecking=accept-new", enlace.destino, orden_remota]
    try:
        r = subprocess.run(orden, input=entrada if entrada is not None else b"", capture_output=True, timeout=espera)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "verbo": verbo, "error": f"{enlace.destino} no responde: {e}"}
    import json

    try:
        cuerpo = json.loads(r.stdout.decode("utf-8", "replace"))
        if isinstance(cuerpo, dict) and "ok" in cuerpo:
            return cuerpo
    except ValueError:
        pass
    detalle = (r.stderr.decode("utf-8", "replace").strip() or r.stdout.decode("utf-8", "replace").strip()
               or f"ssh salió con {r.returncode}")[-300:]
    return {"ok": False, "verbo": verbo, "error": detalle}


# ── autorizar la llave (el laptop) ─────────────────────────

CLAVE = re.compile(r"^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) ([A-Za-z0-9+/=]{20,})(?: .*)?$")
COMANDO_SEGURO = re.compile(r"^[A-Za-z0-9_./+-]+$")
MARCA = "enlace servir"


def linea_autorizada(clave_publica: str, telar_ruta: str) -> tuple[str, str]:
    """La línea de `authorized_keys` que ata esa llave al único comando `telar enlace servir`.

    Devuelve (línea, blob de la llave). Lo que no se puede citar sin ambigüedad se rechaza."""
    m = CLAVE.match((clave_publica or "").strip())
    if not m or "\n" in clave_publica.strip():
        raise ErrorDePuerta("eso no parece una llave pública (ssh-ed25519 AAAA… comentario)")
    if not COMANDO_SEGURO.match(telar_ruta):
        raise ErrorDePuerta(f"la ruta de telar ({telar_ruta}) tiene caracteres que no se pueden citar en authorized_keys")
    return f'restrict,command="{telar_ruta} {MARCA}" {m.group(1)} {m.group(2)} telar-enlace', m.group(2)


def autorizar(clave_publica: str, telar_ruta: str, authorized_keys: Path) -> str:
    """Escribe (o reemplaza) la línea de esa llave. Devuelve "nueva" o "actualizada". Guarda una copia."""
    linea, blob = linea_autorizada(clave_publica, telar_ruta)
    authorized_keys.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    actuales = authorized_keys.read_text(encoding="utf-8").splitlines() if authorized_keys.exists() else []
    if authorized_keys.exists():
        shutil.copy2(authorized_keys, authorized_keys.with_name(authorized_keys.name + ".bak-telar"))
    resto = [l for l in actuales if blob not in l]
    tenia = len(resto) != len(actuales)
    tmp = authorized_keys.with_name(authorized_keys.name + ".telar.tmp")
    tmp.write_text("\n".join([*resto, linea]) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, authorized_keys)
    return "actualizada" if tenia else "nueva"


def revocar(authorized_keys: Path) -> int:
    """Quita toda llave atada a `telar enlace servir`. Devuelve cuántas quitó."""
    if not authorized_keys.exists():
        return 0
    actuales = authorized_keys.read_text(encoding="utf-8").splitlines()
    resto = [l for l in actuales if f'command="' not in l or MARCA not in l]
    if len(resto) == len(actuales):
        return 0
    shutil.copy2(authorized_keys, authorized_keys.with_name(authorized_keys.name + ".bak-telar"))
    tmp = authorized_keys.with_name(authorized_keys.name + ".telar.tmp")
    tmp.write_text(("\n".join(resto) + "\n") if resto else "", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, authorized_keys)
    return len(actuales) - len(resto)
