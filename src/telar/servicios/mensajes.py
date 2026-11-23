"""Los mensajes entre hilos que pasaron por el bus, de todas las máquinas (telar.bus.registro).

Lo usan `telar mensaje` (enviar, `--registro`, `--soltar`, `--descartar`) y `GET /mensajes`, `POST /mensajes`,
`POST /mensajes/{id}/soltar`, `POST /mensajes/{id}/descartar`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from telar.servicios import ErrorDeServicio


class Mensajes(BaseModel):
    mensajes: list[dict] = Field(default_factory=list)


def registro(ctx, n: int = 40, *, retenidos: bool = False) -> Mensajes:
    from telar import bus as mod_bus
    from telar.ordenes.mensaje import VENTANA_RETENIDOS
    from telar.ordenes.mensaje import retenidos as solo_retenidos

    try:
        # los retenidos, en la misma ventana que `--soltar` y la bandeja (telar esperas)
        lista = mod_bus.registro(ctx.config, max(n, VENTANA_RETENIDOS if retenidos else 0))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 502) from e
    return Mensajes(mensajes=solo_retenidos(lista) if retenidos else lista)


class Enviado(BaseModel):
    """El mensaje como quedó: con su `id`, y `estado` «retenido» y su `motivo` si no se entregó."""

    model_config = ConfigDict(extra="allow")


def enviar(ctx, para: str, texto: str, *, tipo: str = "mensaje", de: str = "", modo: str = "pedido",
           plazo: str = "") -> Enviado:
    """Un mensaje para un hilo o un agente, por el bus. `de` vacío: el hilo de quien escribe o la persona.
    `modo`: aviso, pedido (el de siempre) o encargo, que trae `encargo` y su `direccion`."""
    from telar import bus as mod_bus
    from telar import casilla
    from telar import encargo
    from telar.ordenes.mensaje import enviar as mandar

    if not para.strip():
        raise ErrorDeServicio("¿para quién? telar mensaje <hilo> \"texto\"", 422)
    if modo == "consulta":
        raise ErrorDeServicio("una consulta no se manda: en qué anda un hilo lo dicen telar ficha <hilo> y "
                              "telar hilo leer <hilo> (GET /ficha?hilo=…, GET /hilos/leer?hilo=…)", 422)
    if not texto.strip():
        raise ErrorDeServicio("¿qué le digo? el texto está vacío", 422)
    # el modo y el plazo se validan aquí: lo que pide quien manda es un 422; un ValueError de más adentro, un 500
    if modo not in casilla.MODOS:
        raise ErrorDeServicio(f"el modo «{modo}» no se manda: {', '.join(casilla.MODOS)}", 422)
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
        from telar.ordenes.mensaje import Ambiguo, NoHayHilo

        codigo = 404 if isinstance(e, NoHayHilo) else 409 if isinstance(e, Ambiguo) else 502
        raise ErrorDeServicio(str(e), codigo) from e


class Consulta(BaseModel):
    """`--modo consulta`, retirado: el hilo como objeto (`hilo:<nombre>`, telar.objetos) y lo último de su
    conversación (`telar hilo leer`), o `problema` si eso no se pudo leer. No le llega nada al hilo. Responde lo
    mismo que antes para quien ya lo llama; lo nuevo usa `telar ficha` y `telar hilo leer`."""

    modo: str = "consulta"
    para: str
    objeto: dict
    ultimos: dict | None = None
    problema: str = ""


#: cuántos turnos trae una consulta
TURNOS_CONSULTA = 3


def consultar(ctx, para: str) -> Consulta:
    """En qué anda un hilo (o el de un agente, por su carpeta o su nombre), sin entrar a su conversación: lo que
    hacen `telar ficha` y `telar hilo leer`, juntos. Retirado (`--modo consulta`, `GET /mensajes/consulta`): queda
    para quien ya lo llama."""
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


def descartar(ctx, mid: str, quien: str = "") -> Enviado:
    """Que un mensaje retenido no salga: lo decidió la persona. Queda en el registro como descartado (quién y cuándo),
    y a quien lo mandó le llega un aviso (`aviso`, su id; o `sin_aviso`, por qué no salió). 404 si no hay un retenido
    con ese id (no está, o ya se soltó o se descartó); 502 si el bus no responde."""
    from telar import bus as mod_bus
    from telar.ordenes.mensaje import descartar as quitar

    try:
        return Enviado(**quitar(ctx, mid, quien=quien))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 404 if "no hay un mensaje retenido" in str(e) else 502) from e
