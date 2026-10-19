"""Lo pendiente: las casillas de los documentos de los hilos (con `repo`, de todas las unidades) y,
con `proveedores`, lo que dan las fuentes declaradas (telar.ordenes.pendientes).

    from telar.servicios import pendientes
    r = pendientes.pendientes(ctx, repo=True)

Lo usan `telar pendientes --json` y `GET /pendientes`.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from telar.servicios import ErrorDeServicio


class Pendiente(BaseModel):
    """Un pendiente, con los campos de docs/contratos.md («telar pendientes --json»), tal cual."""

    model_config = ConfigDict(extra="allow")


class Pendientes(BaseModel):
    dia: str
    raiz: str
    pendientes: list[Pendiente] = Field(default_factory=list)
    fallas: list[str] = Field(default_factory=list)


def pendientes(ctx, *, repo: bool = False, hechos: bool = False, proveedores: bool = False, hilo: str = "",
               limite: int = 0) -> Pendientes:
    from telar.ordenes import _comun
    from telar.ordenes.pendientes import con_area, de_proveedores, juntar

    tel = _comun.tejer(ctx)
    filas = juntar(ctx, tel, repo=repo, hechos=hechos)
    fallas: list[str] = []
    if proveedores:
        externos, fallas = de_proveedores(ctx, tel, dt.date.today())
        filas += externos
    con_area(filas)
    if hilo:
        encontrado, problema = _comun.resolver(tel, hilo)
        if encontrado is None:
            raise ErrorDeServicio(problema, 404)
        filas = [f for f in filas if f["hilo"] == encontrado.nombre]
    filas.sort(key=lambda f: (not f["en_curso"], f["hilo"] or "~", f["ref"]))
    if limite:
        filas = filas[:limite]
    return Pendientes(dia=dt.date.today().isoformat(), raiz=str(tel.raiz), pendientes=filas, fallas=fallas)
