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


def sin_maquina(ctx, nombre: str) -> str:
    """`Gerencia@telar` → `Gerencia`, si lo de antes de la arroba es un agente: su casilla es la del agente, viva
    donde viva (como en `telar mensaje`). Cualquier otro nombre, tal cual."""
    from telar import agentes as residentes
    from telar.ordenes.mensaje import _con_maquina

    m = _con_maquina(nombre or "")
    if m is None:
        return nombre
    corto = m.group("nombre").strip()
    try:
        hay = residentes.descubrir(ctx.config)
    except Exception:  # noqa: BLE001 - sin poder leer los agentes, tal cual
        return nombre
    return corto if any(corto in (x.clave, x.nombre) for x in hay) else nombre


def _agente(ctx, nombre: str):
    from telar import agentes as residentes

    nombre = sin_maquina(ctx, nombre)
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
        r = mensaje.enviar(ctx, sin_maquina(ctx, agente), texto, tipo="encargo", modo="encargo")
    except mod_bus.ErrorDeBus as e:
        raise BusCaido(f"el bus no recibió el encargo ({e})", 502) from e
    if r.get("estado") == "retenido":
        return Encargo(hilo=r["para"], estado="retenido", motivo=r["motivo"], id=r["id"],
                       encargo=r.get("encargo", ""), direccion=r.get("direccion", ""))
    return Encargo(hilo=r["para"], estado="en su casilla (bus)", id=r["id"], encargo=r.get("encargo", ""),
                   direccion=r.get("direccion", ""))


def aqui(ctx, agente: str, texto: str) -> Encargo:
    """En esta máquina, sin bus: el encargo en su casilla, y que se entere (telar.encargos)."""
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


def encargar_y_ir(ctx, agente, texto: str) -> Encargo:
    """Le encarga `texto` al agente residente (su objeto, de telar.agentes) y lleva a su hilo de siempre. Si
    vive en otra máquina, su ventana la trae el nodo (`telar nodo`, al ver su estado en el bus): si todavía
    no llegó, el encargo igual quedó en su casilla. Lo usan los atajos, los pendientes sin proyecto y las
    reuniones."""
    from telar.mux import ErrorDeMux
    from telar.ordenes import _comun

    r = encargar(ctx, agente.clave, texto)
    tel = _comun.tejer(ctx, con_ficha=False)
    hilo = tel.por_nombre(agente.nombre)
    if hilo is not None and tel.mux is not None and tel.vivo(hilo):
        try:
            tel.mux.ir(hilo.id)
        except ErrorDeMux:
            pass
    return r
