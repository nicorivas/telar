"""La ficha de un hilo: lo que telar sabe de él, si es seguro escribirle y las acciones del perfil
(telar.ordenes.ficha; docs/contratos.md, «telar ficha --json»).

Lo usan `telar ficha --json` y `GET /hilos/{hilo}/ficha`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio


class FichaDeHilo(BaseModel):
    model_config = ConfigDict(extra="allow")

    hilo: dict
    seguro: bool
    acciones: list[dict]
    perfil: str


def ficha(ctx, hilo: str = "") -> FichaDeHilo:
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx)
    if hilo:
        h, problema = _comun.resolver(tel, hilo)
        if h is None:
            raise ErrorDeServicio(problema, 404)
    else:
        h = _comun.hilo_actual(tel)
        if h is None:
            raise ErrorDeServicio("¿de qué hilo? fuera de un hilo, di cuál: telar ficha <hilo>", 404)
    acciones = [{"nombre": a.nombre, "descripcion": a.descripcion, "tecla": a.tecla, "donde": a.donde,
                 "confirmar": a.confirmar} for a in ctx.perfil.acciones]
    return FichaDeHilo(hilo=_comun.json_hilo(h, tel), seguro=_comun.seguro(tel), acciones=acciones,
                       perfil=ctx.perfil.nombre)
