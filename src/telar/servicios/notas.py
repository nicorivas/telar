"""Las notas que las skills y la persona le dejan a los eventos del día (telar.notas).

Lo usan `telar evento notas|nota --json` y `GET /notas`, `POST /notas`. Si viven en otra máquina, se le piden a ella.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Notas(BaseModel):
    """`{ok, dia, eventos: {id: {titulo, inicio, notas: [...]}}, aviso?}`, o `{ok: false, error}`: como
    la CLI, que lo imprime igual en los dos casos."""

    model_config = ConfigDict(extra="allow")

    ok: bool = True


def notas(ctx, dia: str = "") -> Notas:
    from telar import notas as mod

    return Notas(**mod.leer(ctx.config, dia))


def agregar(ctx, evento: str, texto: str, *, de: str, titulo: str = "", inicio: str = "", dia: str = "") -> Notas:
    """Una nota en un evento del día: `{ok, dia, en?}`, o `{ok: false, error}`."""
    from telar import notas as mod

    return Notas(**mod.agregar(ctx.config, dia, evento, texto, de=de, titulo=titulo, inicio=inicio))
