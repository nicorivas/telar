"""Llevar algo compartido (una dirección, un texto) a un hilo o a un proveedor que recibe (telar.ordenes.compartir).

Lo usan `telar compartir` y `GET /compartir/destinos`, `POST /compartir`; el panel, desde el teléfono.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Destinos(BaseModel):
    destinos: list[dict]


class Compartido(BaseModel):
    """`{ok: true, dicho}` o `{ok: false, error}`: como la CLI, que lo imprime igual en los dos casos."""

    model_config = ConfigDict(extra="allow")

    ok: bool


def destinos(ctx) -> Destinos:
    from telar.ordenes.compartir import receptores

    return Destinos(destinos=receptores(ctx.config))


def llevar(ctx, a: str, *, url: str = "", texto: str = "", titulo: str = "") -> Compartido:
    from telar.ordenes.compartir import _llevar

    return Compartido(**_llevar(ctx, a.strip(), url.strip(), texto.strip(), titulo.strip()))
