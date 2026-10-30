"""Lo que la página de un módulo (un lienzo, aislado y sin red) le pide a telar que haga por ella.

    from telar.servicios import lienzos
    lienzos.pedir(ctx, "bloque:gantt", "fecha", {"id": "…", "inicio": "2026-11-20"})

Un lienzo llama `window.lienzo.pedir(orden, datos)`; la página lo manda aquí (`POST /lienzo/pedir`) con de dónde vino
(`bloque:<clave>` o `app:<clave>`). telar lo corre solo si: (1) ese lienzo es de un módulo, (2) el módulo declaró la
orden en su `[permisos] ordenes`, y (3) la persona se la concedió (telar.concesiones). Si falta la concesión, un 403
con `permiso` dice qué preguntar; la página pregunta y la anota (`POST /permisos`). Lo que se puede pedir así está en
`ORDENES`: una a una, a medida que hagan falta.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class Pedido(BaseModel):
    origen: str
    orden: str
    datos: dict = {}


class Concesion(BaseModel):
    modulo: str
    orden: str
    decision: str


def _fecha(ctx, d: dict) -> dict:
    from telar.servicios import fechas

    dia = lambda k: date.fromisoformat(str(d[k])) if d.get(k) else None  # noqa: E731
    return fechas.escribir(ctx, str(d.get("id", "")), inicio=dia("inicio"), fin=dia("fin"),
                           version=str(d.get("version") or "")).model_dump(mode="json")


def _idea(ctx, d: dict) -> dict:
    """Crear una idea (con `producto` y `titulo`) o cambiar una (con `direccion` y sus `campos`): telar.productos."""
    from telar import productos
    from telar.servicios import ErrorDeServicio

    campos = {str(k): str(v) for k, v in (d.get("campos") or {}).items()}
    try:
        if d.get("accion") == "tarea":
            return productos.nueva_tarea(ctx, str(d.get("direccion") or ""), str(d.get("titulo") or ""),
                                         vence=str(d.get("vence") or ""))
        if d.get("direccion"):
            return productos.cambiar(ctx, str(d["direccion"]), campos, version=str(d.get("version") or "") or None,
                                     nota=str(d.get("nota") or ""))
        return productos.crear(ctx, str(d.get("producto") or ""), str(d.get("titulo") or ""), campos, str(d.get("texto") or ""))
    except productos.ErrorDeProductos as e:
        raise ErrorDeServicio(str(e), e.codigo) from e


#: lo que un lienzo puede pedir: la orden (como se declara en `[permisos] ordenes`) → qué hace y en palabras
ORDENES = {
    "fecha": (_fecha, "cambiar fechas donde viven: las celdas de los cronogramas en tus documentos, la fecha de tus "
                      "tareas (telar fecha)"),
    "idea": (_idea, "crear y mover las ideas de tus productos (un archivo por idea en la carpeta de cada producto), "
                    "y abrir tareas desde ellas (telar productos)"),
}


def modulo_de(ctx, origen: str):
    """El módulo que dibujó ese lienzo: el que trae ese bloque (su pestaña) o esa app. None si no es de un módulo."""
    tipo, _, clave = origen.partition(":")
    for m in getattr(ctx.config, "modulos", ()):
        if m.nombre == clave and ((tipo == "bloque" and m.pestana) or (tipo == "app" and m.app)):
            return m
    return None


def pedir(ctx, origen: str, orden: str, datos: dict) -> dict:
    from telar import concesiones
    from telar.servicios import ErrorDeServicio

    if orden not in ORDENES:
        raise ErrorDeServicio(f"un lienzo no puede pedir «{orden}» (puede: {', '.join(sorted(ORDENES))})", 400)
    m = modulo_de(ctx, origen)
    if m is None:
        raise ErrorDeServicio(f"{origen}: no es la página de un módulo; solo un módulo puede pedir órdenes", 403)
    declaradas = (m.permisos or {}).get("ordenes", ())
    if orden not in declaradas:
        raise ErrorDeServicio(f"el módulo «{m.nombre}» no declara «{orden}» en su [permisos] ordenes", 403)
    decision = concesiones.decision(ctx.config, m.nombre, orden)
    if decision != "concedido":
        raise ErrorDeServicio(
            f"el módulo «{m.nombre}» pide {ORDENES[orden][1]}" + ("; se le negó" if decision == "negado" else ""), 403,
            {"permiso": {"modulo": m.nombre, "orden": orden, "descripcion": ORDENES[orden][1], "decision": decision}})
    return {"orden": orden, "datos": ORDENES[orden][0](ctx, datos)}


def conceder(ctx, modulo: str, orden: str, decision: str) -> dict:
    from telar import concesiones
    from telar.servicios import ErrorDeServicio

    if orden not in ORDENES:
        raise ErrorDeServicio(f"«{orden}» no es algo que un lienzo pueda pedir", 400)
    if not any(m.nombre == modulo for m in getattr(ctx.config, "modulos", ())):
        raise ErrorDeServicio(f"no hay un módulo «{modulo}»", 404)
    if decision == "olvidar":  # «solo esta vez»: se corrió, y la próxima se vuelve a preguntar
        concesiones.quitar(ctx.config, modulo, orden)
        return concesiones.leer(ctx.config)
    try:
        concesiones.decidir(ctx.config, modulo, orden, decision)
    except ValueError as e:
        raise ErrorDeServicio(str(e), 400) from None
    return concesiones.leer(ctx.config)
