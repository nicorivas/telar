"""Las unidades del repositorio (proyectos, áreas, clientes…) y si tienen hilo (telar.ordenes.proyectos).

    from telar.servicios import proyectos
    r = proyectos.lista(ctx)

Lo usan `telar proyectos --json` y `GET /proyectos`; cambiar el estado de una iniciativa (`cambiar_estado`),
`telar proyectos estado` y `POST /proyectos/estado`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Proyecto(BaseModel):
    """Una unidad, con los campos de docs/contratos.md («telar proyectos --json»), tal cual."""

    model_config = ConfigDict(extra="allow")


class Proyectos(BaseModel):
    raiz: str
    proyectos: list[Proyecto] = Field(default_factory=list)
    #: las áreas en el orden en que se muestran (`areas` del perfil)
    areas: list[str] = Field(default_factory=list)
    #: las fuentes de fechas que no contestaron al buscar los plazos: «nombre: por qué»
    fallas: list[str] = Field(default_factory=list)
    #: el vocabulario de estados de las iniciativas (`[iniciativas]`, telar.iniciativas.para_la_pagina): `estados`,
    #: `sinonimos`, `clases` y `fuentes`
    iniciativas: dict = Field(default_factory=dict)


#: cuál plazo gana si una unidad trae varios: el que está en curso, después el que viene, después el que terminó
_RANGO = {"en-curso": 0, "pendiente": 1, "hecho": 2, "cancelado": 3}


def plazos(ctx) -> tuple[dict[str, dict], list[str]]:
    """El plazo de cada unidad (`telar fechas`, clase `plazo`): ruta → {inicio, fin, estado, etapa, avance, aviso,
    fuente, enlace}, y las fuentes que fallaron. Sin las tareas de los proveedores: un plazo no es una tarea, y
    preguntarles demora."""
    from telar.servicios import fechas

    r = fechas.lista(ctx, tareas=False)
    salida: dict[str, dict] = {}
    for f in r.fechas:
        d = f.model_dump()
        if d.get("clase") != "plazo" or not d.get("proyecto"):
            continue
        actual = salida.get(d["proyecto"])
        clave = (_RANGO.get(d.get("estado", ""), 9), -date.fromisoformat(d["fin"]).toordinal())
        if actual is None or clave < (_RANGO.get(actual["estado"], 9), -date.fromisoformat(actual["fin"]).toordinal()):
            salida[d["proyecto"]] = {k: d.get(k) for k in ("inicio", "fin", "estado", "etapa", "avance", "aviso",
                                                            "fuente", "enlace")}
    return salida, list(r.fallas)


def lista(ctx) -> Proyectos:
    from telar.ordenes import _comun
    from telar.ordenes.proyectos import listar

    tel = _comun.tejer(ctx, con_ficha=False)
    unidades = listar(ctx, tel)
    try:
        de_cada, fallas = plazos(ctx)
    except Exception as e:  # noqa: BLE001 - sin plazos la lista sirve igual; se dice por qué
        de_cada, fallas = {}, [f"fechas: {type(e).__name__}: {e}"]
    from telar import mundos

    hay_mundos = bool(mundos.declarados(ctx.config))
    for u in unidades:
        u["plazo"] = de_cada.get(u["ruta"])
        # su mundo, por su carpeta (con `[mundos]`): la página muestra los del mundo puesto
        if hay_mundos:
            u["mundo"] = mundos.de_ruta(ctx.config, u["ruta"])
    from telar import iniciativas

    return Proyectos(raiz=str(ctx.config.raiz), proyectos=unidades, areas=list(ctx.perfil.areas), fallas=fallas,
                     iniciativas=iniciativas.para_la_pagina(ctx.config.iniciativas))


class EstadoCambiado(BaseModel):
    """Lo que quedó al cambiar el estado de una iniciativa: su ficha (relativa a la raíz), el estado de antes y el de
    ahora, desde cuándo, y si se escribió (`cambio`: False si ya estaba en ese estado, contando sus sinónimos)."""

    ruta: str
    archivo: str
    estado: str
    estado_desde: str
    antes: str
    cambio: bool


def cambiar_estado(ctx, ruta: str, estado: str, *, hoy: date | None = None) -> EstadoCambiado:
    """Cambia el estado de una iniciativa en su ficha: `estado:` y `estado_desde:` (hoy) de su frontmatter, y nada más
    del archivo, sin commitear (telar.iniciativas). Solo uno del vocabulario (`[iniciativas] estados`, o un sinónimo:
    se escribe el suyo), solo en una unidad que algún modo llama iniciativa, y no en una de fuente externa (su ficha
    dice `estado_fuente:`): esa la manda la otra fuente. `estado_nota:` y `estado_fuente:` no se tocan. Si ya estaba en
    ese estado, no se escribe nada."""
    from telar import iniciativas, lectura
    from telar.ordenes.proyectos import frontmatter_de
    from telar.servicios import ErrorDeServicio

    ini = ctx.config.iniciativas
    if not ini.estados:
        raise ErrorDeServicio("no hay un vocabulario de estados: [iniciativas] estados, en la configuración", 422)
    relativa = ruta.strip().strip("/")
    unidades = lectura.indice(ctx.perfil, ctx.config.raiz)
    if relativa not in unidades:
        raise ErrorDeServicio(f"«{ruta}» no es una unidad del perfil", 404)
    arquetipo, documento = unidades[relativa]
    tipos = iniciativas.arquetipos(ctx.config)
    if arquetipo.nombre.lower() not in tipos:
        raise ErrorDeServicio(f"«{relativa}» es un {arquetipo.nombre}, no una iniciativa (`iniciativas` de un modo: "
                              f"{', '.join(sorted(tipos)) or 'ninguno las declara'})", 422)
    if not Path(documento).is_file():
        raise ErrorDeServicio(f"«{relativa}» no tiene su ficha ({Path(documento).name})", 404)
    fm = frontmatter_de(Path(documento))
    fuente = iniciativas.fuente(ini, fm)
    if fuente:
        raise ErrorDeServicio(f"el estado de «{relativa}» lo manda {fuente} (estado_fuente: {fm.get('estado_fuente')}): "
                              "se cambia allá, no aquí", 409)
    nuevo = iniciativas.del_vocabulario(ini, estado)
    if nuevo is None:
        raise ErrorDeServicio(f"«{estado}» no es un estado de las iniciativas: {', '.join(ini.estados)}", 422)
    raiz, doc = Path(ctx.config.raiz).resolve(), Path(documento).resolve()
    archivo = doc.relative_to(raiz).as_posix() if doc.is_relative_to(raiz) else str(doc)
    escrito = fm.get("estado", "")
    if escrito and iniciativas.canonico(ini, escrito)[0] == nuevo:
        return EstadoCambiado(ruta=relativa, archivo=archivo, estado=nuevo, estado_desde=fm.get("estado_desde", ""),
                              antes=escrito, cambio=False)
    desde = (hoy or date.today()).isoformat()
    try:
        antes = iniciativas.escribir_estado(Path(documento), nuevo, desde)
    except iniciativas.ErrorDeEstado as e:
        raise ErrorDeServicio(f"{archivo}: {e}", 422) from e
    except PermissionError as e:
        raise ErrorDeServicio(f"{archivo}: es de solo lectura: no lo toco", 409) from e
    return EstadoCambiado(ruta=relativa, archivo=archivo, estado=nuevo, estado_desde=desde, antes=antes, cambio=True)
