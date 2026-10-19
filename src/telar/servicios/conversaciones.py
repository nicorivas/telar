"""Una conversación del agente, entera, para leerla (docs/contratos.md, «telar agente conversacion»).

Lo usan `telar agente conversacion <id> --json` y `GET /conversaciones/{id}`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio


class Conversacion(BaseModel):
    conversacion: str
    archivo: str = ""
    hilo: str = ""
    mensajes: list[dict] = Field(default_factory=list)


def conversacion(ctx, sid: str) -> Conversacion:
    from telar import estado as mod_estado
    from telar.agente import ErrorDeAgente
    from telar.ordenes.agente import _construir

    sid = sid.strip()
    if not sid:
        raise ErrorDeServicio("¿cuál? telar agente conversacion <id>", 422)
    try:
        agente = _construir(ctx.config.agente.nombre, ctx.config)
    except ErrorDeAgente as e:
        raise ErrorDeServicio(str(e), 502) from e
    mensajes = agente.mensajes(sid)
    if mensajes is None:
        raise ErrorDeServicio(f"no encuentro la conversación {sid}", 404)
    archivo = agente.archivo_de(sid)
    hilo = mod_estado.abrir(ctx.config).hilo_de(sid) or ""
    return Conversacion(conversacion=sid, archivo=str(archivo or ""), hilo=hilo, mensajes=mensajes)
