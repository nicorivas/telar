"""Las fechas de todos lados, juntas (telar.fechas, docs/contratos.md «telar fechas»).

    from telar.servicios import fechas
    r = fechas.lista(ctx, proyecto="operacion/faro", desde=date(2026, 11, 1))

Los cronogramas de los documentos de las unidades, siempre; además, lo que traigan los proveedores con
`como = "fechas"`. Una fuente que falla va a `fallas` y las demás llegan igual. Lo usan `telar fechas --json` y
`GET /fechas`.
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Fecha(BaseModel):
    """Una fecha, con los campos de docs/contratos.md («telar fechas --json»), tal cual."""

    model_config = ConfigDict(extra="allow")


class Fechas(BaseModel):
    fechas: list[Fecha] = Field(default_factory=list)
    #: las filas que parecían una fecha y no se entendieron: «archivo:línea: por qué»
    saltadas: list[str] = Field(default_factory=list)
    #: las fuentes que no contestaron: «nombre: por qué»
    fallas: list[str] = Field(default_factory=list)


def lista(ctx, *, proyecto: str = "", desde: date | None = None, hasta: date | None = None,
          tareas: bool = True) -> Fechas:
    from telar import fechas as mod_fechas
    from telar import lectura, mapas, proveedores
    from telar.ordenes import _comun

    raiz = ctx.config.raiz
    unidades = lectura.indice(ctx.perfil, raiz)
    los_mapas = mapas.cargar(ctx.config)
    leidas = mod_fechas.documentos(raiz, unidades, mapas=los_mapas)
    fallas: list[str] = []
    _comun.asegurar_proveedores(ctx.config)
    for cfg in ctx.config.proveedores_activos():
        if proveedores.clase(cfg) != "fechas":
            continue
        try:
            leidas.sumar(proveedores.obtener(cfg).leer(raiz, unidades, los_mapas))
        except proveedores.ErrorDeProveedor as e:
            fallas.append(f"{cfg.nombre}: {e}")
        except Exception as e:  # noqa: BLE001 - una fuente ajena no tiene por qué ser prolija
            fallas.append(f"{cfg.nombre}: {type(e).__name__}: {e}")
    if tareas:
        leidas.sumar(_de_tareas(ctx, set(unidades), fallas))
    fallas = [*los_mapas.fallas, *fallas]  # los mapas mal escritos, y los documentos que nombran uno que no hay
    elegidas = mod_fechas.filtrar(leidas.fechas, proyecto=proyecto, desde=desde, hasta=hasta)
    saltadas = leidas.saltadas
    if proyecto.strip("/"):
        saltadas = [x for x in saltadas if x.startswith(f"{proyecto.strip('/')}/")]
    return Fechas(fechas=[Fecha(**f.a_json()) for f in elegidas], saltadas=saltadas, fallas=fallas)


def _de_tareas(ctx, unidades: set[str], fallas: list[str]):
    """Las tareas con fecha de vencimiento, como fechas de clase `tarea`: las de los proveedores de tareas encendidos
    (aquí, o en la máquina de su `en`, telar.alla), sin los que tienen `pestana` (un feed no son tareas). De la unidad
    que dice su origen."""
    from datetime import date as _date

    from telar import alla, proveedores
    from telar import fechas as mod_fechas
    from telar.ordenes.pendientes import _carpeta_de

    leidas = mod_fechas.Leidas()
    activos = [p for p in ctx.config.proveedores_activos()
               if proveedores.clase(p) == "tareas" and not p.opciones.get("pestana")]
    if not activos:
        return leidas
    items, caidas = alla.consultar(ctx.config, activos, _date.today())
    fallas.extend(caidas)
    for item in items:
        if item.clase != "tarea" or item.cuando is None or (item.datos or {}).get("hecha"):
            continue
        dia = item.cuando.date()
        carpeta = _carpeta_de(str((item.datos or {}).get("origen") or ""))
        ident = f"{item.proveedor}:{item.id}" if item.id else f"{item.proveedor}:{item.titulo[:24]}"
        con_ficha = next((p for p in activos if p.nombre == item.proveedor), None)
        movible = bool(con_ficha and (con_ficha.opciones.get("detalle") or con_ficha.opciones.get("tipo") == "tipo"))
        leidas.fechas.append(mod_fechas.Fecha(
            id=ident, titulo=item.titulo, inicio=dia, fin=dia, clase="tarea", editable=("inicio",) if movible else (),
            bloqueo="" if movible else f"su proveedor de tareas («{item.proveedor}») no tiene una acción para cambiar la fecha",
            proyecto=mod_fechas.unidad_de(carpeta, unidades) if carpeta else "",
            estado="en-curso" if (item.datos or {}).get("en_curso") else "pendiente",
            responsable=str((item.datos or {}).get("dueno") or ""), fuente=ident, enlace=item.url or ""))
    return leidas


class Prueba(BaseModel):
    """`telar fechas probar <archivo>`: cómo se lee un documento, para escribir o arreglar su mapa."""

    archivo: str
    #: el nombre del mapa con que se leyó; "" si con el de por defecto (`## Cronograma`)
    mapa: str = ""
    fechas: list[Fecha] = Field(default_factory=list)
    saltadas: list[str] = Field(default_factory=list)
    fallas: list[str] = Field(default_factory=list)


def probar(ctx, archivo: str) -> Prueba:
    """Lee un solo documento con su mapa y dice qué filas leyó y cuáles saltó y por qué."""
    from pathlib import Path

    from telar import fechas as mod_fechas
    from telar import lectura, mapas
    from telar.servicios import ErrorDeServicio

    raiz = Path(ctx.config.raiz).resolve()
    ruta = Path(archivo).expanduser()
    ruta = (ruta if ruta.is_absolute() else Path.cwd() / ruta).resolve()
    if not ruta.is_file():
        ruta = (raiz / archivo).resolve()
    try:
        relativa = ruta.relative_to(raiz).as_posix()
    except ValueError:
        raise ErrorDeServicio(f"{archivo}: no está dentro de la raíz ({raiz})", 400) from None
    if not ruta.is_file():
        raise ErrorDeServicio(f"{archivo}: no existe", 404)
    unidades = lectura.indice(ctx.perfil, raiz)
    los_mapas = mapas.cargar(ctx.config)
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    mapa = los_mapas.para(relativa, mapas.frontmatter(texto))
    de_unidad = {Path(d).resolve().relative_to(raiz).as_posix() for _, d in unidades.values()}
    lector = mod_fechas.Lector(unidades=set(unidades), buscar=mod_fechas.buscador(raiz, unidades))
    leidas = mod_fechas.leer_documento(texto, archivo=relativa, proyecto=mod_fechas.unidad_de(relativa, set(unidades)),
                                       mapa=mapa, lector=lector, es_de_unidad=relativa in de_unidad)
    return Prueba(archivo=relativa, mapa=mapa.nombre if mapa else "", fechas=[Fecha(**f.a_json()) for f in leidas.fechas],
                  saltadas=leidas.saltadas, fallas=los_mapas.fallas)



def escribir(ctx, id: str, *, inicio: date | None = None, fin: date | None = None, version: str = "") -> Fecha:
    """Cambia una fecha donde vive (docs/propuestas/fechas.md, «Editarlas donde viven»): la celda de su documento, la
    tarea de su proveedor (su acción de `rol: fecha`), o el programa de su fuente (`escribir`). Lo que no se puede
    es un ErrorDeServicio con su código: 404 no está, 409 cambió desde que se leyó, 422 no se escribe."""
    from telar import fechas as mod_fechas
    from telar import lectura, mapas, proveedores
    from telar.ordenes import _comun
    from telar.servicios import ErrorDeServicio

    if inicio is None and fin is None:
        raise ErrorDeServicio("¿qué cambia? --inicio, --fin o los dos", 400)
    raiz = ctx.config.raiz
    unidades = lectura.indice(ctx.perfil, raiz)
    try:
        # una fila de un documento: «archivo:línea» o «archivo#f-…»
        if re.match(r"^[^:#]+\.(md|markdown)(:\d+|#f-[0-9a-z]+)$", id):
            f = mod_fechas.escribir_en_documento(raiz, id, inicio=inicio, fin=fin, version=version,
                                                 mapas=mapas.cargar(ctx.config), unidades=unidades)
            return Fecha(**f.a_json())
        _comun.asegurar_proveedores(ctx.config)
        # una tarea: «proveedor:id», con su acción de fecha
        proveedor, _, tarea = id.partition(":")
        cfg = ctx.config.proveedores.get(proveedor)
        if cfg is not None and proveedores.clase(cfg) == "tareas":
            if fin not in (None, inicio):
                raise ErrorDeServicio(f"{id}: una tarea vence un día; se mueve con --inicio", 422)
            from telar.servicios import tareas as servicio_tareas

            servicio_tareas.accion(ctx, tarea, proveedor, rol="fecha", texto=inicio.isoformat() if inicio else "")
            nueva = next((x for x in lista(ctx).fechas if x.model_dump()["id"] == id), None)
            if nueva is None:
                raise ErrorDeServicio(f"{id}: se movió, pero ya no aparece entre las fechas", 404)
            return nueva
        # la de un programa: se le pregunta a cada fuente con `escribir` si la tiene
        for cfg in ctx.config.proveedores_activos():
            if proveedores.clase(cfg) != "fechas":
                continue
            fuente = proveedores.obtener(cfg)
            if not getattr(fuente, "escribir", ()):
                continue
            actual = next((x for x in fuente.leer(raiz, unidades).fechas if x.id == id), None)
            if actual is None:
                continue
            cambio = {"id": id, "version": version or actual.version,
                      **({"inicio": inicio.isoformat()} if inicio else {}), **({"fin": fin.isoformat()} if fin else {})}
            return Fecha(**fuente.cambiar(raiz, unidades, cambio).a_json())
    except mod_fechas.ErrorDeFecha as e:
        raise ErrorDeServicio(str(e), e.codigo) from None
    except proveedores.ErrorDeProveedor as e:
        raise ErrorDeServicio(str(e), 502) from None
    raise ErrorDeServicio(f"{id}: no es una fecha que se pueda escribir (ni de un documento, ni de una tarea, ni de una"
                          " fuente con escribir)", 404)
