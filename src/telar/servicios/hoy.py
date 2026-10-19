"""El día en una pantalla: la agenda, quién te espera, qué está por hacer y cuánto llevas.

    from telar.servicios import hoy
    dia = hoy.hoy(ctx)                       # hoy, consultando los proveedores
    dia = hoy.hoy(ctx, dia=date(2026, 10, 8), local=True)

Lo usan `telar hoy` (telar.ordenes.hoy) y `GET /hoy` (telar.api). La forma es la de
docs/contratos.md, «telar hoy --json».
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from telar.modelo import Atencion

__all__ = ["Hoy", "Fila", "HiloEnAtencion", "Proveedores", "Tiempo", "hoy", "DIAS", "LLAMAN"]

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

#: Las atenciones que piden algo de la persona, en el orden en que lo piden.
LLAMAN = (Atencion.ESPERA, Atencion.TERMINO, Atencion.TRABAJANDO)


class Fila(BaseModel):
    """Un pendiente o un evento de la agenda. Los campos que no se nombran aquí (los que agrega cada
    proveedor: `fin`, `lugar`, `asistentes`…) viajan igual."""

    model_config = ConfigDict(extra="allow")

    texto: str
    ref: str = ""
    hilo: str = ""
    en_curso: bool = False
    hecho: bool = False
    id: str = ""
    origen: str = ""
    cuando: str | None = None
    clase: str = ""
    area: str = ""


class HiloEnAtencion(BaseModel):
    """Un hilo que pide algo (te espera, terminó, trabaja): el de `telar hilos --json`, sin su ficha."""

    model_config = ConfigDict(extra="allow")

    nombre: str
    atencion: str
    vivo: bool = False


class Tiempo(BaseModel):
    total: float = 0.0
    hilos: dict[str, float] = Field(default_factory=dict)


class Proveedores(BaseModel):
    declarados: list[str] = Field(default_factory=list)
    fallas: list[str] = Field(default_factory=list)


class Hoy(BaseModel):
    """El día. `agenda` es None si no se consultó a nadie (`local`, o ningún proveedor declarado), y
    una lista vacía si se consultó y no hay nada con hora. `del_repo`: no hay hilos vinculados, y los
    pendientes salen de todas las unidades del repositorio."""

    ahora: str
    dia: str
    fecha: str
    semana: int
    local: bool
    agenda: list[Fila] | None
    atencion: list[HiloEnAtencion]
    pendientes: list[Fila]
    tiempo: Tiempo
    proveedores: Proveedores
    del_repo: bool = False


def hoy(ctx, dia: dt.date | None = None, local: bool = False) -> Hoy:
    """El día `dia` (por defecto, hoy). Con `local`, sin salir a la red: solo lo que hay en disco."""
    from telar.ordenes import _comun
    from telar.ordenes import pendientes as orden_pendientes

    ahora = dt.datetime.now()
    dia = dia or ahora.date()
    tel = _comun.tejer(ctx)

    llaman = [h for h in tel.hilos if h.atencion in LLAMAN]
    llaman.sort(key=lambda h: (LLAMAN.index(h.atencion), h.nombre))

    filas = orden_pendientes.juntar(ctx, tel)
    # sin ningún hilo vinculado, la pantalla que debería mostrar el día salía vacía teniendo los
    # documentos delante: se cae al repositorio y se dice que es eso
    del_repo = False
    if not filas:
        filas = orden_pendientes.juntar(ctx, tel, repo=True)
        del_repo = bool(filas)
    filas.sort(key=lambda f: (not f["en_curso"], f["hilo"] or "~", f["ref"]))

    agenda: list[dict] | None = None
    fallas: list[str] = []
    declarados = [pr.nombre for pr in ctx.config.proveedores_activos()]
    if not local and declarados:
        externos, fallas = orden_pendientes.de_proveedores(ctx, tel, dia)
        # la agenda son los eventos, no todo lo que trae fecha: una tarea vence un día y no por eso
        # ocupa una hora
        def es_evento(e: dict) -> bool:
            return e.get("clase") == "evento" or (not e.get("clase") and bool(e["cuando"]))

        agenda = sorted((e for e in externos if es_evento(e)), key=lambda e: e["cuando"] or "")
        filas += [e for e in externos if not es_evento(e)]
    orden_pendientes.con_area(filas)

    tiempos = {h.nombre: round(h.tiempo, 1) for h in tel.hilos if h.tiempo}
    return Hoy(
        ahora=ahora.isoformat(timespec="seconds"),
        dia=DIAS[dia.weekday()],
        fecha=dia.isoformat(),
        semana=dia.isocalendar()[1],
        local=local,
        agenda=agenda,
        atencion=[_comun.json_hilo(h, tel, con_ficha=False) for h in llaman],
        pendientes=filas,
        tiempo=Tiempo(total=round(sum(tiempos.values()), 1), hilos=tiempos),
        proveedores=Proveedores(declarados=declarados, fallas=fallas),
        del_repo=del_repo,
    )
