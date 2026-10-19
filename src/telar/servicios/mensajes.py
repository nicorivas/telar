"""Los mensajes entre hilos que pasaron por el bus, de todas las máquinas (telar.bus.registro).

Lo usan `telar mensaje` (enviar, `--registro`, `--soltar`) y `GET /mensajes`, `POST /mensajes`,
`POST /mensajes/{id}/soltar`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

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


class Enviado(BaseModel):
    """El mensaje como quedó: con su `id`, y `estado` «retenido» y su `motivo` si no se entregó."""

    model_config = ConfigDict(extra="allow")


def enviar(ctx, para: str, texto: str, *, tipo: str = "mensaje", de: str = "") -> Enviado:
    """Un mensaje para un hilo o un agente, por el bus. `de` vacío: el hilo de quien escribe o la persona."""
    from telar import bus as mod_bus
    from telar.ordenes.mensaje import enviar as mandar

    if not para.strip():
        raise ErrorDeServicio("¿para quién? telar mensaje <hilo> \"texto\"", 422)
    if not texto.strip():
        raise ErrorDeServicio("¿qué le digo? el texto está vacío", 422)
    try:
        return Enviado(**mandar(ctx, para, texto, tipo=tipo, de=de))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 502) from e


def soltar(ctx, mid: str) -> Enviado:
    """Manda un mensaje retenido: lo decidió la persona."""
    from telar import bus as mod_bus
    from telar.ordenes.mensaje import soltar as mandar

    try:
        return Enviado(**mandar(ctx, mid))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 404 if "no hay un mensaje retenido" in str(e) else 502) from e
