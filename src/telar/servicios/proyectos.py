"""Las unidades del repositorio (proyectos, áreas, clientes…) y si tienen hilo (telar.ordenes.proyectos).

    from telar.servicios import proyectos
    r = proyectos.lista(ctx)

Lo usan `telar proyectos --json` y `GET /proyectos`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Proyecto(BaseModel):
    """Una unidad, con los campos de docs/contratos.md («telar proyectos --json»), tal cual."""

    model_config = ConfigDict(extra="allow")


class Proyectos(BaseModel):
    raiz: str
    proyectos: list[Proyecto] = Field(default_factory=list)
    #: las áreas en el orden en que se muestran (`areas` del perfil)
    areas: list[str] = Field(default_factory=list)


def lista(ctx) -> Proyectos:
    from telar.ordenes import _comun
    from telar.ordenes.proyectos import listar

    tel = _comun.tejer(ctx, con_ficha=False)
    return Proyectos(raiz=str(ctx.config.raiz), proyectos=listar(ctx, tel), areas=list(ctx.perfil.areas))
