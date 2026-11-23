"""Lo que muestra un bloque del día (`[bloques.<clave>]`): su página, el detalle de un ítem, y abrir un
hilo para una fila.

    from telar.servicios import bloques
    pagina = bloques.pagina(ctx, "correo")
    guardada = bloques.guardada(ctx, "correo")             # (cuándo, Pagina): la última que se leyó aquí, o None
    detalle = bloques.item(ctx, "correo", "1a0d9")         # {"texto": "…"}, el cuerpo de un correo
    abierto = bloques.abrir(ctx, "correo", "/correo 1a0d9", nombre="✉ Re: el informe")

Lo usan `telar bloque` (telar.ordenes.bloque) y `/bloques/{clave}` (telar.api). La última página que se leyó de cada
bloque queda guardada en el proceso: buscar (telar.servicios.buscar) la usa sin correr de nuevo el comando.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import time

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio, Pagina

__all__ = ["Detalle", "Abierto", "pagina", "guardada", "item", "abrir"]


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


#: la última página de cada bloque que se leyó en este proceso, con cuándo (time.monotonic)
_GUARDADAS: dict[tuple[str, str], tuple[float, Pagina]] = {}


def _llave(ctx, clave: str) -> tuple[str, str]:
    return (str(getattr(ctx.config, "origen", "") or ""), clave)


def pagina(ctx, clave: str) -> Pagina:
    """Corre el comando del bloque y devuelve su página, validada (el contrato de una sección). Queda guardada."""
    from telar.modulos import entorno_de
    from telar.ordenes.seccion import correr

    datos, problema = correr(_bloque(ctx, clave).comando, f"el bloque «{clave}»", entorno_de(ctx.config, clave, "pestana"))
    if problema:
        raise ErrorDeServicio(problema, 502)
    leida = Pagina(**datos)
    _GUARDADAS[_llave(ctx, clave)] = (time.monotonic(), leida)
    return leida


def guardada(ctx, clave: str) -> tuple[float, Pagina] | None:
    """La última página de ese bloque que se leyó en este proceso, con cuándo (time.monotonic); None si ninguna. No
    corre nada."""
    return _GUARDADAS.get(_llave(ctx, clave))


def item(ctx, clave: str, id: str) -> Detalle:
    """El detalle de un ítem: el comando del bloque con `--item <id>` al final."""
    from telar.modulos import entorno_de

    b = _bloque(ctx, clave)
    try:
        r = subprocess.run([*b.comando, "--item", id], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
                           env=entorno_de(ctx.config, clave, "pestana"))
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
