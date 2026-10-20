"""La carpeta de un hilo y uno de sus archivos (su documento, si no se pide otro), para leerlos en la página:
lo que en VS Code son la ficha y la vista de carpeta. Solo lee.

Nada fuera de la carpeta del hilo (tampoco por un enlace simbólico que apunte afuera), nada oculto ni
`node_modules`, y hasta 1 MB por archivo. Un `.md` va como markdown (la página lo convierte); el resto,
como texto; un binario no se muestra.

Sin hilo, la base es la raíz del repositorio (`[telar] raiz`): un archivo o una carpeta cualquiera de ahí, lo que
el dashboard abre (un README, la carpeta de un proyecto). Lo que no se muestra (un binario, uno grande) trae
`descarga`, su ruta, para bajarlo (`GET /archivos/bajar`).

Lo usa `GET /hilos/documento` de la API (las vistas `doc:<hilo>` y `arch:<ruta>` de la página).
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

TOPE = 1 << 20


class Entrada(BaseModel):
    nombre: str
    ruta: str


class Documento(BaseModel):
    hilo: str
    titulo: str
    error: str = ""
    carpeta: str = "."
    archivo: str = ""
    #: la carpeta de arriba, relativa a la del hilo; None si ya es la del hilo
    subir: str | None = None
    archivos: list[Entrada] = []
    markdown: str = ""
    texto: str = ""
    #: la ruta del archivo elegido cuando no se muestra (binario o grande): para bajarlo
    descarga: str = ""


def _dentro(p: Path, base: Path) -> bool:
    return p == base or base in p.parents


def documento(ctx, hilo: str = "", archivo: str = "") -> Documento:
    if not hilo:
        return _en_la_raiz(ctx, archivo)
    from telar.servicios import ErrorDeServicio
    from telar.servicios import fichas

    try:
        h = fichas.ficha(ctx, hilo).hilo
    except ErrorDeServicio as e:
        return Documento(hilo=hilo, titulo=hilo, error=str(e))
    ficha = h.get("ficha") or {}
    titulo = ficha.get("titulo") or hilo
    ruta = h.get("ruta") or ""
    if not h.get("vinculado") or not ruta or not os.path.isdir(ruta):
        return Documento(hilo=hilo, titulo=titulo, error=f"«{hilo}» no tiene una carpeta en esta máquina")
    base = Path(ruta).resolve()
    if archivo:
        elegido = (base / archivo).resolve()
    elif ficha.get("documento"):
        elegido = Path(ficha["documento"]).resolve()
    else:
        elegido = None
    return _leer(hilo, titulo, base, elegido)


def _en_la_raiz(ctx, archivo: str) -> Documento:
    """Un archivo o una carpeta de la raíz del repositorio (`archivo`: absoluto o relativo a ella)."""
    base = Path(ctx.config.raiz).expanduser().resolve()
    elegido = (base / archivo).resolve() if archivo else base
    titulo = os.path.relpath(elegido, base) if elegido != base and (base in elegido.parents) else base.name
    return _leer("", titulo, base, elegido)


def _leer(hilo: str, titulo: str, base: Path, elegido: Path | None) -> Documento:
    # resolve() ya siguió los enlaces: si apunta afuera, se nota aquí
    if elegido is not None and not _dentro(elegido, base):
        return Documento(hilo=hilo, titulo=titulo, error="ese archivo no es de la carpeta del hilo" if hilo
                         else "ese archivo está fuera de la raíz del repositorio")
    es_carpeta = elegido is not None and elegido.is_dir()
    carpeta = elegido if es_carpeta else elegido.parent if elegido is not None else base
    try:
        entradas = [e for e in os.scandir(carpeta) if not e.name.startswith(".") and e.name != "node_modules"]
    except OSError:
        entradas = []
    entradas.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
    archivos = [Entrada(nombre=e.name + ("/" if e.is_dir() else ""), ruta=os.path.relpath(e.path, base)) for e in entradas]
    doc = Documento(hilo=hilo, titulo=titulo, carpeta=os.path.relpath(carpeta, base), archivos=archivos,
                    subir=(os.path.relpath(carpeta.parent, base) if carpeta != base else None))
    if elegido is None or es_carpeta:
        return doc
    doc.archivo = os.path.relpath(elegido, base)
    try:
        tamano = elegido.stat().st_size
    except OSError:
        doc.texto = "no existe"
        return doc
    if tamano > TOPE:
        doc.texto = f"pesa {round(tamano / 1024)} KB: no se muestra aquí"
        doc.descarga = str(elegido)
        return doc
    crudo = elegido.read_bytes()
    if b"\0" in crudo:
        doc.texto = "es un archivo binario: no se muestra aquí"
        doc.descarga = str(elegido)
    elif elegido.suffix.lower() == ".md":
        doc.markdown = crudo.decode("utf-8", "replace")
    else:
        doc.texto = crudo.decode("utf-8", "replace")
    return doc
