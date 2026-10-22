"""Lo que una máquina le entrega a otra por el bus: un aviso en pantalla y un archivo en su carpeta de
entrada. Reemplaza a los verbos `notificar` y `archivo` de la puerta (telar.enlace), que iban por ssh.

    telar aviso "terminó" --titulo telar          a las otras máquinas en línea (o a una: --a laptop)
    telar archivo foto.png --a laptop             a la carpeta de entrada de esa máquina

Lo que llega es dato de otra máquina: el nombre del archivo se limpia y nunca escapa de la carpeta de
entrada, un archivo nunca pisa a otro, los tamaños tienen tope, y el texto de un aviso va al programa
que lo muestra por variables de entorno, no dentro de su guion.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

#: un aviso, en caracteres
MAX_AVISO = 500
#: un archivo por el bus, en bytes: un mensaje de NATS lleva hasta 1 MB, y en base64 el archivo crece un tercio
MAX_ARCHIVO = 700 * 1024            # lo que cabe en un mensaje del bus: el tamaño de un trozo
MAX_TOTAL = 25 * 1024 * 1024        # un archivo entero, mandado en trozos


class ErrorDeEntrega(Exception):
    """Lo que llegó no se puede entregar. El mensaje es lo que se le dice a quien lo mandó."""


def nombre_de_archivo(crudo: str) -> str:
    """El nombre que puede tener un archivo que llega: sin carpetas, sin puntos delante, sin rarezas."""
    base = os.path.basename(crudo.replace("\\", "/"))
    limpio = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .")[:100]
    return limpio or "archivo"


def carpeta_de_entrada(config) -> Path:
    """`[bus] entrada` (o, de antes, `[enlace] entrada`); por defecto `~/telar-entrada`."""
    return Path(getattr(config.bus, "entrada", "") or getattr(config.puerta, "entrada", "") or "~/telar-entrada").expanduser()


def guardar_archivo(config, nombre: str, datos: bytes, *, tope: int | None = None) -> Path:
    """Deja el archivo en la carpeta de entrada. Nunca pisa uno que ya esté: agrega -1, -2…"""
    tope = tope or MAX_ARCHIVO
    if len(datos) > tope:
        raise ErrorDeEntrega(f"el archivo pesa más de {tope // 1024} KB")
    if not datos:
        raise ErrorDeEntrega("el archivo llegó vacío")
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
    raise ErrorDeEntrega("no encontré un nombre libre para ese archivo")


def mostrar_aviso(titulo: str, texto: str) -> dict:
    """Un aviso en la pantalla de esta máquina (macOS: osascript; Linux: notify-send)."""
    texto = texto.strip()[:MAX_AVISO]
    if not texto:
        raise ErrorDeEntrega("no hay texto que mostrar")
    titulo = (titulo or "telar")[:60]
    # el texto va por variables de entorno, no dentro del guion: no hay nada que escapar
    entorno = {**os.environ, "TELAR_TEXTO": texto, "TELAR_TITULO": titulo}
    if sys.platform == "darwin" and shutil.which("osascript"):
        orden = ["osascript", "-e", 'display notification (system attribute "TELAR_TEXTO") '
                 'with title (system attribute "TELAR_TITULO")']
    elif shutil.which("notify-send"):
        orden = ["notify-send", "--", titulo, texto]
    else:
        raise ErrorDeEntrega("esta máquina no sabe mostrar avisos")
    r = subprocess.run(orden, env=entorno, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise ErrorDeEntrega(f"el aviso no salió: {(r.stderr or '').strip()[-200:]}")
    return {"titulo": titulo, "caracteres": len(texto)}


# ── del lado de quien manda ──

def _otras_en_linea(config) -> list[str]:
    """Las otras máquinas de esta persona que publicaron su foto y siguen en línea."""
    from telar import bus as mod_bus
    from telar import espejo

    yo = mod_bus.maquina(config)
    return [f["nombre"] for f in espejo.leer_todos(config) if f.get("en_linea") and f.get("nombre") != yo]


def aviso(config, texto: str, *, titulo: str = "telar", a: str = "") -> dict:
    """El aviso en la máquina `a`, o en todas las otras que están en línea. {máquina: "" o el error}."""
    from telar import bus as mod_bus

    if not mod_bus.hay_bus(config):
        raise ErrorDeEntrega("sin bus no hay a quién avisar: [bus] url en la configuración")
    destinos = [a] if a else _otras_en_linea(config)
    salida = {}
    for m in destinos:
        r = mod_bus.pedir(config, m, "aviso", {"titulo": titulo, "texto": texto[:MAX_AVISO]}, espera=15)
        salida[m] = "" if r.get("ok") else r.get("error", "no respondió")
    return salida


def archivo(config, ruta: Path, *, a: str, nombre: str = "") -> dict:
    """El archivo en la carpeta de entrada de la máquina `a`: {ruta, bytes} allá."""
    from telar import bus as mod_bus

    datos = Path(ruta).expanduser().read_bytes()
    if len(datos) > MAX_TOTAL:
        raise ErrorDeEntrega(f"por el bus va hasta {MAX_TOTAL // 1024 // 1024} MB; para más, git o el panel")
    nombre = nombre or Path(ruta).name
    trozos = [datos[i:i + MAX_ARCHIVO] for i in range(0, len(datos), MAX_ARCHIVO)] or [b""]
    carga = {"nombre": nombre}
    if len(trozos) > 1:
        carga.update(id=uuid.uuid4().hex, total=len(trozos), bytes=len(datos))
    r: dict = {}
    for n, t in enumerate(trozos):
        r = mod_bus.pedir(config, a, "archivo", {**carga, "parte": n, "datos": base64.b64encode(t).decode("ascii")}, espera=30)
        if not r.get("ok"):
            raise ErrorDeEntrega(f"{a}: {r.get('error', 'no respondió')}")
    return {"ruta": r.get("ruta", ""), "bytes": len(datos)}


# ── del lado de quien recibe (lo que responde el nodo) ──

def recibir_aviso(p: dict) -> dict:
    try:
        return {"ok": True, **mostrar_aviso(str(p.get("titulo", "telar")), str(p.get("texto", "")))}
    except (ErrorDeEntrega, OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": str(e)}


def _parcial(config, p: dict, trozo: bytes) -> bytes | None:
    """Junta los trozos de un archivo grande; devuelve el archivo entero con el último, y None antes."""
    ident = str(p.get("id", ""))
    if not re.fullmatch(r"[0-9a-f]{32}", ident):
        raise ErrorDeEntrega("trozo sin identificador válido")
    parte, total = int(p.get("parte", 0)), int(p.get("total", 1))
    if not 0 <= parte < total or total * MAX_ARCHIVO > MAX_TOTAL + MAX_ARCHIVO:
        raise ErrorDeEntrega("trozo fuera de rango")
    carpeta = carpeta_de_entrada(config) / ".parciales"
    carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
    ahora = time.time()
    for viejo in carpeta.glob("*.parte"):  # lo abandonado hace más de una hora
        if ahora - viejo.stat().st_mtime > 3600:
            viejo.unlink(missing_ok=True)
    archivo_parcial = carpeta / f"{ident}.parte"
    if parte == 0:
        archivo_parcial.write_bytes(b"")
    elif not archivo_parcial.exists() or archivo_parcial.stat().st_size != parte * MAX_ARCHIVO:
        raise ErrorDeEntrega("faltó un trozo anterior; se manda de nuevo")
    with open(archivo_parcial, "ab") as f:
        f.write(trozo)
    if parte < total - 1:
        return None
    datos = archivo_parcial.read_bytes()
    archivo_parcial.unlink(missing_ok=True)
    return datos


def recibir_archivo(config, p: dict) -> dict:
    try:
        datos = base64.b64decode(str(p.get("datos", "")), validate=True)
        if p.get("id"):
            datos = _parcial(config, p, datos)
            if datos is None:
                return {"ok": True, "parcial": True}
        destino = guardar_archivo(config, str(p.get("nombre", "archivo")), datos, tope=MAX_TOTAL)
    except (ErrorDeEntrega, ValueError, OSError) as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "ruta": str(destino), "bytes": len(datos)}
