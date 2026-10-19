"""Encargarle algo a un agente residente (telar.ordenes.encargar).

Con bus, el encargo va a la casilla del agente y lo recoge su máquina, esté donde esté. Sin bus (o si el
bus no responde), se encarga aquí si el agente vive aquí. Los caminos viejos a otra máquina (por la
puerta o por ssh) siguen en la CLI.

Lo usan `telar encargar` y `POST /encargos`; el atajo de un agente (`telar atajo`) también.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio


class Encargo(BaseModel):
    """`{hilo, estado, id}` por el bus («en su casilla (bus)», o «retenido» con su `motivo`); aquí,
    `{hilo, estado, en_cola?, cerrados?}`."""

    model_config = ConfigDict(extra="allow")

    hilo: str = ""
    estado: str = ""


class BusCaido(ErrorDeServicio):
    """El bus no recibió el encargo: quien llama decide si va por otro camino."""


def _agente(ctx, nombre: str):
    from telar import agentes as residentes

    hay = residentes.descubrir(ctx.config)
    a = next((x for x in hay if nombre in (x.clave, x.nombre)), None)
    if a is None:
        raise ErrorDeServicio(f"«{nombre}» no es un agente residente (hay: {', '.join(sorted(x.nombre for x in hay))}). "
                              "Para escribirle a un hilo cualquiera: telar mensaje", 404)
    return a


def por_el_bus(ctx, agente: str, texto: str) -> Encargo:
    """Por el bus, a la casilla del agente. `BusCaido` si el bus no lo recibió."""
    from telar import bus as mod_bus
    from telar.ordenes import mensaje

    _agente(ctx, agente)
    try:
        r = mensaje.enviar(ctx, agente, texto, tipo="encargo")
    except mod_bus.ErrorDeBus as e:
        raise BusCaido(f"el bus no recibió el encargo ({e})", 502) from e
    if r.get("estado") == "retenido":
        return Encargo(hilo=r["para"], estado="retenido", motivo=r["motivo"], id=r["id"])
    return Encargo(hilo=r["para"], estado="en su casilla (bus)", id=r["id"])


def aqui(ctx, agente: str, texto: str) -> Encargo:
    """En esta máquina: el agente lo recibe en su hilo (o en su cola, si está ocupado)."""
    from telar import encargos

    a = _agente(ctx, agente)
    try:
        return Encargo(**encargos.encargar(ctx, a, texto))
    except encargos.ErrorDeEncargo as e:
        raise ErrorDeServicio(str(e), 409) from e


def donde_vive(ctx, agente: str) -> str:
    """La máquina del agente si no es esta (`[agentes.<carpeta>] en` o `[agentes] en`); "" si es aquí."""
    a = _agente(ctx, agente)
    en = (a.en if getattr(a, "en", "") else "") or ctx.config.agentes_en
    return "" if en in ("", "aqui") else en


def encargar(ctx, agente: str, texto: str) -> Encargo:
    from telar import bus as mod_bus

    if not texto.strip():
        raise ErrorDeServicio("¿qué le encargo? el texto está vacío", 422)
    if mod_bus.hay_bus(ctx.config):
        try:
            return por_el_bus(ctx, agente, texto)
        except BusCaido:
            if donde_vive(ctx, agente):
                raise
    elif donde_vive(ctx, agente):
        raise ErrorDeServicio(f"{agente} vive en {donde_vive(ctx, agente)} y no hay bus: encárgaselo desde una "
                              "terminal (telar encargar), que sabe ir por ssh", 502)
    return aqui(ctx, agente, texto)
