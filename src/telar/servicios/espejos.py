"""Las fotos que publican las otras máquinas: sus hilos, como los ve cada una (telar.espejo).

    from telar.servicios import espejos
    r = espejos.ver(ctx)            # una foto por máquina, con su edad y si sigue en línea

Lo usan `telar espejo ver` y `GET /espejos`; el panel lo pide cada 30 s para el grupo de cada máquina.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Espejo(BaseModel):
    """La foto de una máquina, tal como la publicó (docs/contratos.md, «telar espejo ver --json»)."""

    model_config = ConfigDict(extra="allow")


class Espejos(BaseModel):
    espejos: list[Espejo] = Field(default_factory=list)
    vigente: int | float = 0


def ver(ctx) -> Espejos:
    from telar import espejo as mod

    return Espejos(espejos=mod.leer_todos(ctx.config), vigente=mod.VIGENTE)
