"""El espejo: los hilos de otra máquina, vistos desde esta.

Un laptop se apaga; un servidor no. Para ver desde el servidor (y desde la web del celular)
qué hilos tiene el laptop y cuáles esperan algo, el laptop **empuja una foto** de sus hilos y
el servidor la guarda con la hora en que llegó:

    laptop:    telar espejo publicar      →  ssh servidor  telar espejo recibir --de laptop
    servidor:  ~/.local/state/telar/espejos/laptop.json

Se empuja y no se va a buscar por tres razones. El servidor no necesita entrar al laptop, así
que un servidor comprometido no abre una puerta hacia él. Con el laptop apagado nadie espera un
tiempo de espera: quien lee solo mira un archivo. Y el servidor no necesita saber nada de la
red del laptop.

La foto lleva lo que sirve para *mirar* —nombre, semáforo, carpeta, prioridad, tiempo y el
título del documento del hilo— y nada de lo que hay dentro: ni conversaciones ni el estado del
proyecto (que suele traer lo que no se cuenta afuera). Es de solo lectura: ver un hilo del
laptop no lo toca, y entrar a su terminal no es posible desde aquí (su agente vive allá).

Una foto es **vigente** mientras tenga menos de `VIGENTE` segundos; pasado eso el laptop se
da por apagado y se sigue mostrando la última, atenuada y con su edad. El contrato está en
docs/contratos.md.
"""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
import time
from datetime import datetime
from pathlib import Path

VERSION = 1
#: cuánto vive una foto como «en línea» (segundos). El laptop publica cada ~30 s.
VIGENTE = 120.0
#: lo más que se acepta de una foto: un telar con cientos de hilos pesa decenas de KB.
MAXIMO = 2 * 1024 * 1024
NOMBRE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

#: qué campos de cada hilo viajan (el resto —ruta absoluta, sesiones, conversaciones— se queda allá)
CAMPOS = ("nombre", "atencion", "vivo", "activo", "prioridad", "tiempo", "visto", "relativa", "arquetipo", "remoto")


class ErrorDeEspejo(ValueError):
    """Una foto que no se acepta, o un nombre que no sirve."""


def carpeta(config) -> Path:
    return Path(config.estado) / "espejos"


def nombre_de_esta_maquina() -> str:
    """El nombre corto y en minúsculas de esta máquina, apto para nombre de archivo."""
    return nombre_valido(socket.gethostname().split(".")[0]) or "maquina"


def nombre_valido(texto: str) -> str:
    """`MacBook de Nico` → `macbook-de-nico`; «» si no queda nada aprovechable."""
    limpio = re.sub(r"[^a-z0-9_-]+", "-", texto.lower()).strip("-_")[:32]
    return limpio if NOMBRE.match(limpio) else ""


def foto(tel, *, maquina: str, version_telar: str = "") -> dict:
    """La foto de los hilos de este telar, lista para viajar. Sin los archivados."""
    from telar.ordenes import _comun

    hilos = []
    for h in tel.hilos:
        if h.archivado:
            continue
        crudo = _comun.json_hilo(h, tel, con_ficha=True)
        hilo = {k: crudo.get(k) for k in CAMPOS}
        ficha = crudo.get("ficha") or {}
        hilo["resumen"] = ficha.get("etiqueta") or ficha.get("titulo") or ""
        hilos.append(hilo)
    return {
        "version": VERSION, "maquina": maquina, "telar": version_telar,
        "publicado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sesion": getattr(tel, "sesion", ""), "hilos": hilos,
    }


def validar(datos: object, de: str) -> dict:
    """Lo que llega por la red no se confía: forma conocida, campos conocidos, nada más.

    Devuelve la foto limpia (solo lo que este módulo sabe leer). Levanta `ErrorDeEspejo`."""
    if not NOMBRE.match(de or ""):
        raise ErrorDeEspejo(f"«{de}» no es un nombre de máquina válido (a-z, 0-9, - y _; hasta 32)")
    if not isinstance(datos, dict) or datos.get("version") != VERSION:
        raise ErrorDeEspejo(f"foto de otra versión (esta entiende la {VERSION})")
    crudos = datos.get("hilos")
    if not isinstance(crudos, list):
        raise ErrorDeEspejo("la foto no trae una lista de hilos")
    hilos = []
    for h in crudos:
        if not isinstance(h, dict) or not isinstance(h.get("nombre"), str) or not h["nombre"]:
            raise ErrorDeEspejo("un hilo de la foto no tiene nombre")
        limpio = {k: h.get(k) for k in (*CAMPOS, "resumen") if k in h}
        for k in ("nombre", "atencion", "relativa", "arquetipo", "remoto", "resumen", "visto"):
            if limpio.get(k) is not None and not isinstance(limpio[k], str):
                raise ErrorDeEspejo(f"el campo «{k}» de «{h['nombre']}» no es texto")
        hilos.append(limpio)
    return {
        "version": VERSION, "maquina": de, "telar": str(datos.get("telar", ""))[:20],
        "publicado": str(datos.get("publicado", ""))[:40], "sesion": str(datos.get("sesion", ""))[:60], "hilos": hilos,
    }


def guardar(config, de: str, crudo: str) -> dict:
    """Recibe una foto (JSON) de la máquina `de` y la guarda con la hora de llegada.

    La hora es la de *este* reloj, no la que diga la foto: la edad se mide donde se lee, y un
    laptop con la hora corrida no puede hacerse pasar por vigente. Se escribe a un temporal y
    se renombra, así que quien lea nunca ve medio archivo."""
    if len(crudo.encode()) > MAXIMO:
        raise ErrorDeEspejo(f"la foto pesa más de {MAXIMO // 1024} KB")
    try:
        datos = json.loads(crudo)
    except ValueError as e:
        raise ErrorDeEspejo(f"la foto no es JSON: {e}") from e
    limpia = validar(datos, de)
    limpia["recibido"] = time.time()
    dest = carpeta(config)
    dest.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest, prefix=".espejo.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(limpia, f, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest / f"{de}.json")
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return limpia


def leer_todos(config, ahora: float | None = None) -> list[dict]:
    """Las fotos guardadas, con su edad y si siguen vigentes. Un archivo roto se dice, no se esconde."""
    ahora = time.time() if ahora is None else ahora
    salida = []
    for ruta in sorted(carpeta(config).glob("*.json")):
        nombre = ruta.stem
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            recibido = float(datos["recibido"])
        except (OSError, ValueError, KeyError, TypeError) as e:
            salida.append({"nombre": nombre, "error": f"no se pudo leer: {e}", "en_linea": False, "edad": None, "hilos": []})
            continue
        edad = max(0.0, ahora - recibido)
        salida.append({
            "nombre": nombre, "en_linea": edad < VIGENTE, "edad": round(edad, 1),
            "recibido": recibido, "publicado": datos.get("publicado", ""), "telar": datos.get("telar", ""),
            "sesion": datos.get("sesion", ""), "hilos": datos.get("hilos", []),
        })
    return salida
