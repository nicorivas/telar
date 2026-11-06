"""Los códigos de un hilo (docs/propuestas/codigos.md, docs/contratos.md «telar codigos»): los que define su carpeta y
salen de su archivo, y los que nombra su conversación, con lo que son.

Se calcula en la máquina donde vive el hilo, que es donde están su carpeta y su conversación (telar.codigos); de otra,
se le pide a su nodo por el bus (el verbo `codigos`). Lo usan `telar codigos`, `GET /codigos` y la hoja «códigos» de
la barra de la derecha de la página (web/codigos.ts).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from telar.servicios import ErrorDeServicio

#: cuántos códigos de la conversación se dan, a lo más (los últimos nombrados)
MAX_CONVERSACION = 60
#: una tarea que la persona no nombró entra si el agente la nombró en al menos estas respuestas: las tareas son de
#: todos los proyectos, y una nombrada de pasada («también está T433») no es de este hilo
MIN_RESPUESTAS_TAREA = 2


class Codigos(BaseModel):
    """`{hilo, carpeta, archivos, truncado, clases, codigos, conversacion, …}`; con `codigo`, también `detalle`."""

    model_config = ConfigDict(extra="allow")

    hilo: str
    maquina: str = ""
    #: la carpeta vinculada del hilo (`~/…` si está bajo la casa); "" si no tiene una que se recorra
    carpeta: str = ""
    archivos: int = 0
    truncado: bool = False
    clases: list[dict] = Field(default_factory=list)
    codigos: list[dict] = Field(default_factory=list)
    conversacion: list[dict] = Field(default_factory=list)
    #: dónde viven las tareas si no es aquí: sus títulos se piden aparte (`telar objeto tarea:T84`)
    tareas_en: str = ""
    aviso: str = ""


def _corta(ruta: Path) -> str:
    try:
        return "~/" + str(ruta.relative_to(Path.home()))
    except ValueError:
        return str(ruta)


def _tareas(ctx):
    """(el índice de las tareas si viven aquí, la máquina donde viven si es otra): (None, "") si no hay tareas."""
    from telar.servicios import tipos as servicio_tipos

    t = next((x for x in getattr(ctx.config, "tipos", ()) if x.clave == "tarea"), None)
    if t is None:
        return None, ""
    if t.carpeta:
        try:
            return servicio_tipos.indice(ctx, "tarea"), ""
        except ErrorDeServicio:
            return None, ""
    return None, t.en or ""


def _es_tarea(codigo: str) -> bool:
    from telar.tipos import tarea

    return codigo.startswith(tarea.PREFIJO) and codigo[len(tarea.PREFIJO):].isdigit() and len(codigo) > len(tarea.PREFIJO) + 1


def de_hilo(ctx, hilo: str = "", *, maquina: str = "", codigo: str = "", buscar: str = "", de_otra: bool = False) -> Codigos:
    """Los códigos del hilo. Con `maquina` (otra), se le piden a esa por el bus. `de_otra`: lo pide otra máquina
    por el bus, y lo que `[bus] no_leer` veta no le muestra su conversación."""
    from telar import bus as mod_bus

    if maquina and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config):
        if not hilo:
            raise ErrorDeServicio("¿qué hilo de esa máquina? telar codigos «Faro» --maquina servidor", 422)
        r = mod_bus.pedir(ctx.config, maquina, "codigos", {"hilo": hilo, "codigo": codigo, "buscar": buscar}, espera=30)
        if not r.get("ok"):
            raise ErrorDeServicio(r.get("error") or f"{maquina} no respondió", int(r.get("codigo") or 502))
        return Codigos(**{**r["codigos"], "maquina": maquina})
    return _aqui(ctx, hilo, codigo=codigo, buscar=buscar, de_otra=de_otra)


def para_otra(ctx, pedido: dict) -> dict:
    """Lo que responde el nodo al verbo `codigos`: los códigos del hilo, o el error con su código."""
    try:
        r = de_hilo(ctx, str(pedido.get("hilo", "")), codigo=str(pedido.get("codigo", "")),
                    buscar=str(pedido.get("buscar", "")), de_otra=True)
        return {"ok": True, "codigos": r.model_dump(mode="json")}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}


def _aqui(ctx, hilo: str, *, codigo: str, buscar: str, de_otra: bool) -> Codigos:
    from telar import codigos as mod
    from telar import conversacion, historia
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx, con_ficha=False)
    if hilo:
        h, problema = _comun.resolver(tel, hilo)
        if h is None:
            raise ErrorDeServicio(problema, 404)
    else:
        h = _comun.hilo_actual(tel)
        if h is None:
            raise ErrorDeServicio("¿qué hilo? fuera de un hilo, di cuál: telar codigos <hilo>", 404)

    salida = Codigos(hilo=h.nombre)
    # la carpeta: la vinculada, y no la raíz entera (recorrer un repositorio entero no tiene sentido)
    c = None
    raiz = Path(ctx.config.raiz).expanduser().resolve() if getattr(ctx.config, "raiz", "") else None
    if h.vinculo is not None:
        v = Path(h.vinculo).expanduser()
        if not v.is_dir():
            salida.aviso = f"su carpeta, {_corta(v)}, no está en esta máquina"
        elif raiz is not None and v.resolve() == raiz:
            salida.aviso = "está vinculado a la raíz: solo los códigos de su conversación que son tareas"
        else:
            c = mod.carpeta(v)
            salida.carpeta, salida.archivos, salida.truncado = _corta(v), c.archivos, c.truncado
            if c.truncado:
                salida.aviso = f"la carpeta tiene más de {mod.MAX_ARCHIVOS} documentos: se leyeron los primeros"
    else:
        salida.aviso = "sin carpeta vinculada: solo los códigos de su conversación que son tareas"

    # la conversación
    nombrados: list = []
    vetado = de_otra and historia.vetado(historia.no_leer(ctx.config), h.nombre, tel.estado.vinculos().get(h.nombre, ""))
    if h.sesiones and not vetado:
        try:
            _, mensajes, _ = conversacion.mensajes_del_hilo(ctx.config, list(h.sesiones))
            nombrados = mod.en_conversacion(mensajes)
        except conversacion.ErrorDeConversacion:
            nombrados = []

    indice, tareas_en = _tareas(ctx)
    salida.tareas_en = tareas_en
    definidos = c.defs if c else {}
    en_conv = {n.codigo: n for n in nombrados}

    def tarea_de(codigo: str) -> dict | None:
        """La tarea de ese código, si lo es: con su título y estado si viven aquí; sin ellos, si viven en otra."""
        if codigo in definidos or not _es_tarea(codigo) or (indice is None and not tareas_en):
            return None
        if indice is None:
            return {"tipo": "tarea", "direccion": f"tarea:{codigo}"}
        try:
            t, _ = indice.obtener(codigo)
        except Exception:  # noqa: BLE001 - no hay tal tarea: no es un código de nada
            return None
        return {"tipo": "tarea", "direccion": f"tarea:{codigo}", "titulo": t.titulo, "estado": t.estado}

    conv: list[dict] = []
    for n in nombrados:
        if len(conv) >= MAX_CONVERSACION:
            break
        base = {"codigo": n.codigo, "veces": n.veces, "ultimo": n.ultimo, "extracto": n.extracto}
        if n.codigo in definidos:
            d = c.principal(n.codigo)
            conv.append({**base, "tipo": "codigo", "titulo": d.titulo, "archivo": d.archivo, "linea": d.linea})
        elif (n.persona or n.agente >= MIN_RESPUESTAS_TAREA or n.codigo in h.nombre.split()) and (t := tarea_de(n.codigo)):
            conv.append({**base, **t})

    # los del proyecto: los que salen de su archivo (a otro documento, o a la conversación)
    del_proyecto = (c.viajan() | (set(en_conv) & set(definidos))) if c else set()
    filas = []
    for cod in mod.ordenados(del_proyecto):
        ds = definidos[cod]
        d = c.principal(cod)
        fila = {"codigo": cod, "clase": mod.clase_de(cod), "titulo": d.titulo, "archivo": d.archivo, "linea": d.linea,
                "forma": d.forma, "definiciones": len(ds), "nombrado_en": len(c.fuera(cod))}
        resumen = " ".join(d.texto.split())[:240]
        if resumen and resumen != d.titulo:
            fila["resumen"] = resumen
        if cod in en_conv:
            fila["en_conversacion"] = en_conv[cod].veces
        filas.append(fila)
    salida.clases = mod.clases(c, del_proyecto) if c else []

    if buscar.strip():
        nombres = {k["prefijo"]: k["nombre"] for k in salida.clases}
        filas = [f for f in filas if mod.coincide(buscar, f["codigo"], f["titulo"], f.get("resumen", ""), nombres.get(f["clase"], ""))]
        conv = [x for x in conv if mod.coincide(buscar, x["codigo"], x.get("titulo", ""), x.get("extracto", ""))]
    salida.codigos, salida.conversacion = filas, conv

    if codigo:
        salida.detalle = _detalle(c, codigo.strip(), en_conv.get(codigo.strip()), tarea_de(codigo.strip()))
    return salida


def _detalle(c, codigo: str, nombrado, tarea: dict | None) -> dict:
    defs = c.defs.get(codigo, []) if c else []
    if not defs and not tarea:
        raise ErrorDeServicio(f"«{codigo}» no está definido en la carpeta del hilo", 404)
    d: dict = {"codigo": codigo}
    if defs:
        d["tipo"] = "codigo"
        primera = c.principal(codigo)
        d["definiciones"] = [x.como_json() for x in [primera, *[x for x in defs if x is not primera]][:10]]
        d["nombrado_en"] = [{"archivo": a, "lineas": ls} for a, ls in sorted(c.fuera(codigo).items())][:30]
    else:
        d.update(tarea)
    if nombrado is not None:
        d["conversacion"] = {"veces": nombrado.veces, "ultimo": nombrado.ultimo, "extracto": nombrado.extracto}
    return d
