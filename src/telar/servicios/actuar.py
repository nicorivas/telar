"""Actuar sobre una entidad: mandarle a un hilo o a un agente un prompt con el contexto de esa entidad, con una skill o
sin ella (docs/propuestas/acciones.md, «Acción…»).

    from telar.servicios import actuar
    actuar.actuar(ctx, "proyecto:operacion/faro", a="", skill="pm", nota="revisa el cronograma")

El prompt es una línea: la skill (`/pm`), lo que se pide, y el contexto como la dirección de la entidad y lo que se
sabe de ella (`telar objeto`), para que el agente la abra si necesita más. A dónde va:

- `a` vacío: el hilo de la entidad (de un proyecto: su hilo, o uno nuevo que arranca con el prompt);
- un agente residente: se le encarga (`telar encargar`);
- un hilo de esta máquina: se le escribe en su entrada y se manda (con `escribir`, queda escrito sin mandar);
- un hilo de otra máquina: le llega por el bus, a su casilla.

Lo usan `telar actuar` y `POST /actuar`.
"""

from __future__ import annotations

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio


class Actuado(BaseModel):
    destino: str
    #: «encargado», «enviado», «escrito» (sin mandar), «abierto» (un hilo nuevo que arrancó con el prompt) o
    #: «por el bus»
    como: str
    prompt: str
    maquina: str = ""


def prompt_de(objeto: dict, *, skill: str = "", nota: str = "") -> str:
    """La línea que se le manda al agente: la skill, lo pedido y el contexto de la entidad."""
    partes = [objeto.get("titulo") or objeto.get("id") or "", objeto.get("direccion", "")]
    if objeto.get("tipo") in ("proyecto", "archivo") and objeto.get("id"):
        partes.append(f"carpeta {objeto['id']}" if objeto["tipo"] == "proyecto" else objeto["id"])
    if objeto.get("estado"):
        partes.append(f"estado {objeto['estado']}")
    contexto = " · ".join(p for p in partes if p)
    pedido = " ".join(x for x in (f"/{skill.lstrip('/')}" if skill else "", nota.strip()) if x)
    linea = f"{pedido} [contexto: {contexto}; más con `telar objeto {objeto.get('direccion', '')}`]".strip()
    return " ".join(linea.split())  # una sola línea: se escribe en la entrada del agente


def actuar(ctx, direccion: str, *, a: str = "", skill: str = "", nota: str = "", escribir: bool = False) -> Actuado:
    from telar import objetos
    from telar.mux import ErrorDeMux
    from telar.ordenes import _comun
    from telar.ordenes.pendiente import destino_elegido

    if not skill and not nota.strip():
        raise ErrorDeServicio("¿qué le pido? una skill, o lo que quieres (nota)", 422)
    objeto = objetos.ver(ctx, direccion).model_dump()
    texto = prompt_de(objeto, skill=skill, nota=nota)
    tel = _comun.tejer(ctx, con_ficha=False)

    if not a:
        # el hilo de la entidad: el de un proyecto se abre si no está, y arranca con el prompt
        if objeto.get("tipo") != "proyecto":
            raise ErrorDeServicio(f"«{direccion}» no tiene un hilo propio: di a quién (un hilo o un agente)", 422)
        if tel.mux is None or not tel.viva:
            raise ErrorDeServicio(tel.aviso or "la sesión no está viva: primero telar tejer", 409)
        from telar.ordenes.proyectos import abrir

        try:
            r = abrir(ctx, tel, objeto["id"], texto=texto)
        except ValueError as e:
            raise ErrorDeServicio(str(e), 404) from e
        if r["hecho"] == "abierto":
            return Actuado(destino=r["hilo"], como="abierto", prompt=texto)
        a = r["hilo"]  # ya estaba abierto: se le escribe, como a cualquier hilo

    destino, alla, agente = destino_elegido(ctx, tel, a)
    if agente is not None:
        from telar.servicios import encargos

        encargos.encargar(ctx, agente.nombre, texto)  # por su nombre: encargar no recibe el objeto
        return Actuado(destino=agente.nombre, como="encargado", prompt=texto)
    if alla is not None:
        from telar import bus as mod_bus

        nombre, maquina = alla
        try:
            mod_bus.enviar(ctx.config, nombre, texto, de="el dashboard", tipo="persona")
        except mod_bus.ErrorDeBus as e:
            raise ErrorDeServicio(f"«{nombre}» vive en {maquina} y el bus no lo llevó: {e}", 502) from e
        return Actuado(destino=nombre, como="por el bus", prompt=texto, maquina=maquina)
    if tel.mux is None:
        raise ErrorDeServicio(tel.aviso or "no hay multiplexor con el que hablar", 409)
    try:
        tel.mux.escribir(destino.id, texto, enviar=not escribir)
    except ErrorDeMux as e:
        raise ErrorDeServicio(f"no pude escribirle a «{destino.nombre}»: {e}", 502) from e
    return Actuado(destino=destino.nombre, como="escrito" if escribir else "enviado", prompt=texto)
