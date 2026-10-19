"""Lo pendiente: las casillas de los documentos de los hilos (con `repo`, de todas las unidades) y,
con `proveedores`, lo que dan las fuentes declaradas (telar.ordenes.pendientes).

    from telar.servicios import pendientes
    r = pendientes.pendientes(ctx, repo=True)

Lo usan `telar pendientes --json` y `GET /pendientes`; llevar uno a su hilo o cambiar su casilla
(`telar pendiente`), `POST /pendiente/llevar` y `POST /pendiente/casilla`.
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


class Llevado(BaseModel):
    """Lo que pasó (docs/contratos.md, «telar pendiente --json»): `{ref, texto, destino, …}`."""

    model_config = ConfigDict(extra="allow")


def llevar(ctx, ref: str, *, nuevo: bool = False, donde: bool = False, texto: str = "", enviar: bool = False,
           proveedor: str = "") -> Llevado:
    """Al hilo donde se trabaja: le pone el foco y le deja la frase escrita al agente, sin enviarla (salvo
    `enviar`); si duerme, lo retoma; sin proyecto, se le encarga al agente de `[agentes] sin_proyecto`."""
    from telar.ordenes import pendiente

    datos, _ = pendiente.llevar(ctx, ref, nuevo=nuevo, donde=donde, texto=texto, enviar=enviar, proveedor=proveedor)
    return Llevado(**datos)


def casilla(ctx, ref: str, *, hecho: bool = False, responsable: str | None = None, linea: bool = False,
            esperado: str = "", proveedor: str = "") -> Llevado:
    """Una casilla en su documento: marcarla hecha, cambiar quién la hace o ubicarla. Con `esperado` (el
    texto que se vio), no se toca si el documento cambió."""
    from telar.ordenes import pendiente

    datos, _ = pendiente.en_su_documento(ctx, ref, hecho=hecho, responsable=responsable, linea=linea,
                                         esperado=esperado, proveedor=proveedor)
    return Llevado(**datos)
