"""Lo que una skill deja por día (`[resultados.<clave>]`), leído de la máquina donde vive, y los
comentarios sobre un día.

    from telar.servicios import resultados
    r = resultados.leer(ctx, "plan")                     # el de hoy
    r = resultados.leer(ctx, "plan", "2026-10-06")
    c = resultados.comentar(ctx, "plan", "2026-10-06", "falta la reunión de las 10")

Lo usan `telar resultado` (telar.ordenes.resultado) y `/resultados/{clave}` (telar.api). Cómo se lee y
se comenta (en la máquina donde vive, por el bus) está en telar.resultados.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

__all__ = ["Resultado", "Comentario", "leer", "comentar"]


class Resultado(BaseModel):
    """El resultado de un día. Siempre trae `ok`; si no salió, `error`. `contenido` es lo que escribió la
    skill (JSON o markdown), como venga; `comentable`, si la máquina donde vive atiende comentarios."""

    model_config = ConfigDict(extra="allow")

    ok: bool
    error: str = ""
    aviso: str = ""
    desde: str = ""
    clave: str = ""
    nombre: str = ""
    dia: str = ""
    dias: list[str] = []
    formato: str = ""
    contenido: Any = None
    comentable: bool = False


class Comentario(BaseModel):
    """Lo que pasó con un comentario: lo que abrió (un hilo, normalmente) o por qué no salió."""

    ok: bool
    abrio: str = ""
    error: str = ""


def leer(ctx, clave: str, dia: str = "") -> Resultado:
    from telar import resultados as mod

    return Resultado(**mod.leer(ctx.config, clave, dia))


def comentar(ctx, clave: str, dia: str, texto: str) -> Comentario:
    from telar import resultados as mod

    return Comentario(**mod.comentar(ctx.config, clave, dia, texto))
