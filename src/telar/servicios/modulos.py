"""Los módulos para la página y la API: preguntarle algo a uno (`consultar`, una orden suya con `consulta = true`,
aquí o en otra máquina por el bus); los instalados con de dónde vienen y si están activos (también
`telar modulos --json`); los del catálogo, y las acciones (instalar uno del catálogo, actualizar, activar,
desactivar, quitar).

`consultar` lo usan `GET /modulos/<modulo>/<verbo>` (la página) y el nodo (`rpc … modulo`).

Desde la página se instala solo lo de un catálogo revisado (el oficial) o del equipo: uno sin revisar, desde la
terminal (`telar modulos instalar <url>`), donde se ve lo que corre antes de decir que sí.
"""

from __future__ import annotations

import contextlib
import io

from pydantic import BaseModel, ConfigDict, Field

from telar.servicios import ErrorDeServicio

ACCIONES = ("instalar", "actualizar", "activar", "desactivar", "quitar")


class Instalados(BaseModel):
    """`modulos`: [{nombre, activo, carpeta, descripcion, aporta, fuente, version, ref, catalogo, confianza,
    enlazado, instalado, permisos, pide, a_mano, nueva}]."""

    model_config = ConfigDict(extra="allow")
    modulos: list[dict] = Field(default_factory=list)


def instalados(ctx, *, con_catalogo: bool = False) -> Instalados:
    """Los activos (los que cargó la configuración) y los apagados; con `con_catalogo`, si el catálogo trae una
    versión distinta de la instalada (`nueva`)."""
    from telar import modulos as mod_modulos

    anotados = mod_modulos.leer_instalados(mod_modulos.ruta_instalados(ctx.config.origen))
    entradas = {}
    if con_catalogo:
        from telar import catalogo

        entradas = {e.nombre: e for e in catalogo.cargar(ctx.config)["entradas"]}
    salida = []
    for m in ctx.config.modulos:
        d = anotados.get(m.nombre, {})
        p = mod_modulos.procedencia(d or None)
        e = entradas.get(m.nombre)
        salida.append({"nombre": m.nombre, "activo": True, "carpeta": str(m.carpeta), "descripcion": m.descripcion,
                       "aporta": m.aporta, "fuente": p["fuente"], "version": p["version"], "ref": str(d.get("ref") or ""),
                       "catalogo": str(d.get("catalogo") or ""), "enlazado": p["enlazado"],
                       "instalado": str(d.get("instalado") or ""), "a_mano": not d,
                       "permisos": mod_modulos.permisos_json(m.permisos), "pide": m.pide,
                       "confianza": e.confianza if e else ("" if not d.get("catalogo") else "sin revisar"),
                       "nueva": e.version if (e and d.get("catalogo") and e.version != d.get("ref")) else ""})
    for nombre, d in sorted(anotados.items()):
        if d.get("activo") is not False:
            continue
        p = mod_modulos.procedencia(d)
        salida.append({"nombre": nombre, "activo": False, "carpeta": str(d.get("carpeta") or ""), "descripcion": "",
                       "aporta": [], "fuente": p["fuente"], "version": p["version"], "ref": str(d.get("ref") or ""),
                       "catalogo": str(d.get("catalogo") or ""), "enlazado": p["enlazado"],
                       "instalado": str(d.get("instalado") or ""), "a_mano": False, "permisos": None,
                       "pide": [str(x) for x in d.get("pide") or []], "confianza": "", "nueva": ""})
    return Instalados(modulos=salida)


class Catalogo(BaseModel):
    """`disponibles`: [{nombre, descripcion, fuente, version, autor, etiquetas, telar, permisos, catalogo,
    confianza, instalado, le_sirve}], `catalogos` y `problemas`."""

    model_config = ConfigDict(extra="allow")
    disponibles: list[dict] = Field(default_factory=list)
    catalogos: list[dict] = Field(default_factory=list)
    problemas: list[str] = Field(default_factory=list)


def catalogo(ctx, *, forzar: bool = False, buscar: str = "") -> Catalogo:
    from telar import __version__
    from telar import catalogo as mod_catalogo
    from telar import modulos as mod_modulos

    c = mod_catalogo.cargar(ctx.config, forzar=forzar)
    anotados = mod_modulos.leer_instalados(mod_modulos.ruta_instalados(ctx.config.origen))
    hay = {m.nombre for m in ctx.config.modulos} | set(anotados)
    texto = buscar.strip().lower()
    disponibles = []
    for e in c["entradas"]:
        if texto and texto not in " ".join([e.nombre, e.descripcion, *e.etiquetas, e.autor]).lower():
            continue
        disponibles.append({**e.como_json(), "instalado": e.nombre in hay,
                            "le_sirve": mod_catalogo.le_sirve(e, __version__)})
    return Catalogo(disponibles=disponibles, catalogos=c["catalogos"], problemas=c["problemas"])


class Hecho(BaseModel):
    accion: str
    nombre: str
    salida: str = ""
    codigo: int = 0


def hacer(ctx, accion: str, nombre: str) -> Hecho:
    """Lo que hacen los botones de la página. Instalar: solo uno del catálogo oficial o del equipo, y ya con el sí
    (la página mostró antes lo que pide)."""
    from telar import catalogo as mod_catalogo
    from telar.ordenes import modulos as orden

    if accion not in ACCIONES:
        raise ErrorDeServicio(f"«{accion}» no es una acción: {', '.join(ACCIONES)}", 404)
    argv = [accion, nombre]
    if accion == "instalar":
        e = mod_catalogo.buscar(ctx.config, nombre)
        if e is None:
            raise ErrorDeServicio(f"«{nombre}» no está en ningún catálogo", 404)
        if e.confianza == "sin revisar":
            raise ErrorDeServicio(f"«{nombre}» viene de un catálogo sin revisar ({e.catalogo}): instálalo desde la "
                                  f"terminal, donde se ve lo que corre: telar modulos instalar {nombre}", 403)
        argv.append("--si")
    if accion == "quitar":
        argv.append("--si")
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
        codigo = orden.main(argv, ctx)
    texto = salida.getvalue().strip()
    if codigo != 0:
        raise ErrorDeServicio((texto.splitlines() or [f"telar modulos {accion} falló"])[-1].removeprefix("telar: "), 409)
    return Hecho(accion=accion, nombre=nombre, salida=texto, codigo=codigo)


# ── preguntarle algo a un módulo ───────────────────────────────────────────────

def consultar(ctx, modulo: str, verbo: str, params: dict, maquina: str = "") -> dict:
    from telar import bus as mod_bus
    from telar import modulos as mod_modulos

    if maquina and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config):
        r = mod_bus.pedir(ctx.config, maquina, "modulo", {"modulo": modulo, "verbo": verbo, "params": params},
                          espera=mod_modulos.ESPERA_CONSULTA + 10)
        if not r.get("ok"):
            # una máquina que no atiende consultas de módulos es como una sin el módulo: 404, no una falla
            raise ErrorDeServicio(r.get("error") or f"{maquina} no pudo", 404 if r.get("sin_servicio") else int(r.get("codigo") or 502))
        return r.get("respuesta") or {}
    config = ctx.config
    if mod_modulos.buscar(config, modulo) is None and getattr(config, "origen", None):
        # instalado después de que arrancó telar serve: se relee la configuración, sin reiniciarlo
        from telar import config as mod_config

        try:
            config = mod_config.cargar(config.origen)
        except mod_config.ErrorDeConfig:
            pass
    try:
        return mod_modulos.consultar(config, modulo, verbo, params)
    except mod_modulos.ErrorDeModulo as e:
        texto = str(e)
        raise ErrorDeServicio(texto, 404 if texto.startswith("aquí no está") or "no tiene la consulta" in texto else 502) from None


def para_otra(ctx, pedido: dict) -> dict:
    """Lo que responde el nodo a `modulo`: la respuesta del módulo, o el error con su código."""
    try:
        params = pedido.get("params") if isinstance(pedido.get("params"), dict) else {}
        return {"ok": True, "respuesta": consultar(ctx, str(pedido.get("modulo", "")), str(pedido.get("verbo", "")), params)}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}
