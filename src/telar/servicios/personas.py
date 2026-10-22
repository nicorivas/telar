"""La gestión de personas del bus para la API (telar.personas): `GET /personas` y `POST /personas/<accion>`.

Lo que hay (las cuentas con su rol y los pedidos de entrada) y decidirlo, desde la máquina del bus o desde
cualquier otra del dueño o de un admin: telar.personas lo pide donde corresponde.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio


class Personas(BaseModel):
    """`dueno`, `quien` y su `rol`, `personas` [{nombre, rol}], `pedidos` [{id, persona, estado, cuando, …}],
    `roles`; después de una acción, `hecho` y `falta`."""

    model_config = ConfigDict(extra="allow")


def _pedir(ctx, pedido: dict) -> Personas:
    from telar import personas

    try:
        return Personas(**personas.pedir(ctx.config, pedido))
    except personas.ErrorDePersonas as e:
        raise ErrorDeServicio(str(e), e.codigo) from e


def ver(ctx) -> Personas:
    return _pedir(ctx, {"accion": "ver"})


def hacer(ctx, accion: str, *, pedido: str = "", nombre: str = "", rol: str = "") -> Personas:
    from telar import personas

    if accion not in personas.ACCIONES or accion == "ver":
        raise ErrorDeServicio(f"«{accion}» no es una acción: aprobar, rechazar, quitar o rol", 404)
    return _pedir(ctx, {"accion": accion, "pedido": pedido, "nombre": nombre, "rol": rol})
