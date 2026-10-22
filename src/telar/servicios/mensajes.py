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


def enviar(ctx, para: str, texto: str, *, tipo: str = "mensaje", de: str = "", modo: str = "pedido",
           plazo: str = "") -> Enviado:
    """Un mensaje para un hilo o un agente, por el bus. `de` vacío: el hilo de quien escribe o la persona.
    `modo`: aviso, pedido (el de siempre) o encargo, que trae `encargo` y su `direccion`; la consulta no se
    manda (`consultar`)."""
    from telar import bus as mod_bus
    from telar import casilla
    from telar import encargo
    from telar.ordenes.mensaje import enviar as mandar

    if not para.strip():
        raise ErrorDeServicio("¿para quién? telar mensaje <hilo> \"texto\"", 422)
    if modo == "consulta":
        raise ErrorDeServicio("una consulta no se manda: se lee (telar mensaje <hilo> --modo consulta, "
                              "GET /mensajes/consulta?para=…)", 422)
    if not texto.strip():
        raise ErrorDeServicio("¿qué le digo? el texto está vacío", 422)
    # el modo y el plazo se validan aquí: lo que pide quien manda es un 422; un ValueError de más adentro, un 500
    if modo not in casilla.MODOS:
        raise ErrorDeServicio(f"el modo «{modo}» no se manda: {', '.join(casilla.MODOS)} (la consulta no viaja)", 422)
    if plazo and modo != "encargo":
        raise ErrorDeServicio("el plazo es de un encargo: --modo encargo --plazo …", 422)
    try:
        plazo = encargo.plazo_valido(plazo)
    except ValueError as e:
        raise ErrorDeServicio(str(e), 422) from e
    try:
        # el modo, solo si no es el de siempre: un pedido se manda exactamente como antes
        con_modo = {k: v for k, v in (("modo", modo), ("plazo", plazo)) if v and v != "pedido"}
        return Enviado(**mandar(ctx, para, texto, tipo=tipo, de=de, **con_modo))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 502) from e


class Consulta(BaseModel):
    """`--modo consulta`: el hilo como objeto (`hilo:<nombre>`, telar.objetos) y lo último de su conversación
    (`telar hilo leer`), o `problema` si eso no se pudo leer. No le llega nada al hilo."""

    modo: str = "consulta"
    para: str
    objeto: dict
    ultimos: dict | None = None
    problema: str = ""


#: cuántos turnos trae una consulta
TURNOS_CONSULTA = 3


def consultar(ctx, para: str) -> Consulta:
    """En qué anda un hilo (o el de un agente, por su carpeta o su nombre), sin entrar a su conversación: lo que
    hacen `telar ficha` y `telar hilo leer`, juntos."""
    from telar import agentes as mod_agentes
    from telar import bus as mod_bus
    from telar import objetos
    from telar.ordenes.mensaje import _por_nombre
    from telar.servicios import historias

    if not para.strip():
        raise ErrorDeServicio("¿de quién? telar mensaje <hilo> --modo consulta", 422)
    try:
        nombre = _por_nombre(ctx, para.strip())
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 404) from e
    agente = next((a for a in mod_agentes.descubrir(ctx.config) if nombre in (a.clave, a.nombre)), None)
    nombre = agente.nombre if agente is not None else nombre
    objeto = objetos.ver(ctx, objetos.direccion_de("hilo", nombre))
    ultimos, problema = None, ""
    try:
        ultimos = historias.leer(ctx, objeto.id, ultimos=TURNOS_CONSULTA, maquina=objeto.maquina).model_dump(mode="json")
    except ErrorDeServicio as e:
        problema = str(e)
    return Consulta(para=objeto.id, objeto=objeto.model_dump(mode="json"), ultimos=ultimos, problema=problema)


def soltar(ctx, mid: str) -> Enviado:
    """Manda un mensaje retenido: lo decidió la persona."""
    from telar import bus as mod_bus
    from telar.ordenes.mensaje import soltar as mandar

    try:
        return Enviado(**mandar(ctx, mid))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 404 if "no hay un mensaje retenido" in str(e) else 502) from e
