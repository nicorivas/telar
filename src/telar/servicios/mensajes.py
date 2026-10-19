"""Los mensajes entre hilos que pasaron por el bus, de todas las máquinas (telar.bus.registro).

Lo usan `telar mensaje --registro --json` y `GET /mensajes`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio


class Mensajes(BaseModel):
    mensajes: list[dict] = Field(default_factory=list)


def registro(ctx, n: int = 40, *, retenidos: bool = False) -> Mensajes:
    from telar import bus as mod_bus
    from telar.ordenes.mensaje import retenidos as solo_retenidos

    try:
        lista = mod_bus.registro(ctx.config, max(n, 200 if retenidos else 0))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 502) from e
    return Mensajes(mensajes=solo_retenidos(lista) if retenidos else lista)
