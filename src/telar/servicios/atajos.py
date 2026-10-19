"""Los atajos del dashboard (`[atajos.<tecla>]`) y abrir el hilo de una unidad (telar.ordenes.atajo,
telar.ordenes.proyectos).

Un atajo abre un hilo nuevo con el agente y su mensaje como primer prompt, o, si es de un agente residente,
le encarga el mensaje y lleva a su hilo. Abrir una unidad va a su hilo, o le abre uno.

Lo usan `telar atajo`, `telar proyectos abrir` y `POST /atajos/{tecla}`, `POST /proyectos/abrir`.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio


class Atajos(BaseModel):
    atajos: list[dict]


class AtajoHecho(BaseModel):
    """`{hilo, mensaje}`, y `encargo` (cómo quedó) si fue a un agente residente."""

    model_config = ConfigDict(extra="allow")

    hilo: str
    mensaje: str


class Abierto(BaseModel):
    hilo: str
    ruta: str
    mensaje: str = ""
    hecho: str


def lista(ctx) -> Atajos:
    return Atajos(atajos=[{"tecla": a.tecla, "nombre": a.nombre, "mensaje": a.mensaje, "descripcion": a.descripcion}
                          for a in ctx.config.atajos])


def correr(ctx, tecla: str) -> AtajoHecho:
    from telar.ordenes.atajo import abrir

    atajo = next((a for a in ctx.config.atajos if a.tecla == tecla), None)
    if atajo is None:
        raise ErrorDeServicio(f"no hay atajo en «{tecla}»: `telar atajo` lista los que hay", 404)
    if atajo.agente:
        return _al_agente(ctx, atajo)
    nombre = f"{atajo.nombre} {dt.datetime.now():%m/%d %H:%M}"
    problema = abrir(ctx, nombre, atajo.mensaje)
    if problema:
        raise ErrorDeServicio(problema, 409)
    return AtajoHecho(hilo=nombre, mensaje=atajo.mensaje)


def _al_agente(ctx, atajo) -> AtajoHecho:
    """Le encarga el mensaje al agente y lleva a su hilo de siempre. Si vive en otra máquina, su ventana se
    trae aquí si todavía no estaba (`telar remotos traer`)."""
    import io
    from contextlib import redirect_stdout

    from telar import agentes as mod_agentes
    from telar.mux import ErrorDeMux
    from telar.ordenes import _comun, remotos
    from telar.servicios import encargos

    agente = next((a for a in mod_agentes.descubrir(ctx.config) if atajo.agente in (a.clave, a.nombre)), None)
    if agente is None:
        raise ErrorDeServicio(f"el atajo «{atajo.tecla}» le encarga a «{atajo.agente}», que no está en [agentes] carpeta", 404)
    r = encargos.encargar(ctx, agente.clave, atajo.mensaje)
    tel = _comun.tejer(ctx, con_ficha=False)
    hilo = tel.por_nombre(agente.nombre)
    if ctx.config.agentes_en and not (hilo is not None and tel.vivo(hilo)):
        with redirect_stdout(io.StringIO()):
            remotos.main(["traer", "--remoto", ctx.config.agentes_en], ctx)
        tel = _comun.tejer(ctx, con_ficha=False)
        hilo = tel.por_nombre(agente.nombre)
    if hilo is not None and tel.mux is not None and tel.vivo(hilo):
        try:
            tel.mux.ir(hilo.id)
        except ErrorDeMux:
            pass
    return AtajoHecho(hilo=agente.nombre, mensaje=atajo.mensaje, encargo=r.estado)


def abrir_unidad(ctx, ruta: str) -> Abierto:
    """Ir al hilo de esa unidad (una carpeta del perfil, relativa a la raíz) o abrirle uno."""
    from telar.agente import ErrorDeAgente
    from telar.mux import ErrorDeMux
    from telar.ordenes import _comun
    from telar.ordenes.proyectos import abrir

    if not ruta.strip():
        raise ErrorDeServicio("¿cuál? la unidad, relativa a la raíz", 422)
    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None or not tel.viva:
        raise ErrorDeServicio(tel.aviso or "la sesión no está viva: primero telar tejer", 409)
    try:
        return Abierto(**abrir(ctx, tel, ruta))
    except ValueError as e:
        raise ErrorDeServicio(str(e), 404) from e
    except (ErrorDeMux, ErrorDeAgente) as e:
        raise ErrorDeServicio(f"no pude abrirlo: {e}", 502) from e
