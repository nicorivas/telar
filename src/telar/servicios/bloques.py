"""Lo que muestra un bloque del día (`[bloques.<clave>]`): su página, el detalle de un ítem, y abrir un
hilo para una fila.

    from telar.servicios import bloques
    pagina = bloques.pagina(ctx, "correo")
    detalle = bloques.item(ctx, "correo", "1a0d9")         # {"texto": "…"}, el cuerpo de un correo
    abierto = bloques.abrir(ctx, "correo", "/correo 1a0d9", nombre="✉ Re: el informe")

Lo usan `telar bloque` (telar.ordenes.bloque) y `/bloques/{clave}` (telar.api).
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio, Pagina

__all__ = ["Detalle", "Abierto", "pagina", "item", "abrir"]


class Detalle(BaseModel):
    """El detalle de un ítem de un bloque (el cuerpo de un correo)."""

    texto: str


class Abierto(BaseModel):
    """El hilo que se abrió para una fila, y el primer mensaje que recibió su agente."""

    hilo: str
    mensaje: str


def _bloque(ctx, clave: str):
    b = next((x for x in ctx.config.bloques if x.clave == clave), None)
    if b is None:
        raise ErrorDeServicio(f"no hay bloque «{clave}»", 404)
    return b


def pagina(ctx, clave: str) -> Pagina:
    """Corre el comando del bloque y devuelve su página, validada (el contrato de una sección)."""
    from telar.ordenes.seccion import correr

    datos, problema = correr(_bloque(ctx, clave).comando, f"el bloque «{clave}»")
    if problema:
        raise ErrorDeServicio(problema, 502)
    return Pagina(**datos)


def item(ctx, clave: str, id: str) -> Detalle:
    """El detalle de un ítem: el comando del bloque con `--item <id>` al final."""
    b = _bloque(ctx, clave)
    try:
        r = subprocess.run([*b.comando, "--item", id], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        detalle = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        raise ErrorDeServicio(f"el detalle de {id} no corrió: {e}", 502) from e
    if not isinstance(detalle, dict) or not isinstance(detalle.get("texto"), str):
        raise ErrorDeServicio(f"el bloque «{clave}» no dio el detalle de {id}: {r.stderr.strip()[-200:]}", 502)
    return Detalle(texto=detalle["texto"])


def abrir(ctx, clave: str, mensaje: str, nombre: str = "") -> Abierto:
    """Un hilo nuevo con el agente y `mensaje` como primer prompt, para una fila del bloque."""
    from telar.ordenes.atajo import abrir as abrir_hilo

    b = _bloque(ctx, clave)
    if not mensaje.strip():
        raise ErrorDeServicio("¿qué mensaje?")
    nombre = " ".join(nombre.split())[:48] or f"{b.nombre} {dt.datetime.now():%m/%d %H:%M}"
    problema = abrir_hilo(ctx, nombre, mensaje)
    if problema:
        raise ErrorDeServicio(problema, 502)
    return Abierto(hilo=nombre, mensaje=mensaje)
