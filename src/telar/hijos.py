"""Los hilos hijos de un agente: una tarea que se le lleva a un agente abre su propio hilo, en vez de entrar en cola en el
hilo de siempre del agente (donde se mezclaban todas y no se podía seguir ninguna).

    from telar import hijos
    r = hijos.abrir(ctx, agente, "T454", "Hacer el test Hogan", "/tarea T454")   # {"hilo", "maquina", "nuevo"}

El hijo se llama `«agente» › «ref» «título corto»` («Gestión › T454 Hacer el test Hogan»): con ese nombre la barra lo
cuelga de su agente, en cualquier máquina, sin más registro. Nace en la carpeta del agente (sus instrucciones y su
memoria), con una conversación nueva, y en la máquina donde vive el agente: si es otra, se le pide por el bus
(`hilo-hijo`). Si ya hay un hijo vivo para esa tarea, se usa ese.
"""

from __future__ import annotations

import re

VERBO = "hilo-hijo"
#: lo que separa al agente del resto en el nombre de un hijo
SEPARADOR = " › "


def nombre(agente: str, ref: str, titulo: str) -> str:
    """«Gestión › T454 Hacer el test Hogan»: el título corto, hasta unas 28 letras y sin cortar una palabra."""
    corto = " ".join(re.sub(rf"^{re.escape(ref)}\s*[:·-]?\s*", "", titulo or "").split())
    if len(corto) > 28:
        corto = corto[:28].rsplit(" ", 1)[0].rstrip(",;:·-") + "…"
    return f"{agente}{SEPARADOR}{ref}" + (f" {corto}" if corto else "")


def de(agente: str, hilo: str) -> bool:
    """¿Es `hilo` un hijo de `agente`?"""
    return hilo.startswith(f"{agente}{SEPARADOR}")


def abrir(ctx, agente, ref: str, titulo: str, texto: str) -> dict:
    """Un hilo hijo de `agente` (su objeto, de telar.agentes) para trabajar `ref`, con `texto` como primer mensaje, en
    la máquina donde vive el agente. {"hilo", "maquina" ("" si es esta), "nuevo"}."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios.encargos import donde_vive

    hijo = nombre(agente.nombre, ref, titulo)
    alla = donde_vive(ctx, agente.clave)
    if not alla:
        return {**abrir_aqui(ctx, agente.clave, hijo, ref, texto), "maquina": ""}
    from telar import bus as mod_bus

    try:
        r = mod_bus.pedir(ctx.config, alla, VERBO, {"agente": agente.clave, "hilo": hijo, "ref": ref, "texto": texto}, espera=60)
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(f"{agente.nombre} vive en {alla} y el bus no llegó: {e}", 502) from e
    if not r.get("ok"):
        raise ErrorDeServicio(f"en {alla}: {r.get('error') or 'no pude abrir el hilo'}", int(r.get("codigo") or 502))
    return {"hilo": r.get("hilo", hijo), "nuevo": bool(r.get("nuevo")), "maquina": alla}


def abrir_aqui(ctx, clave: str, hijo: str, ref: str, texto: str) -> dict:
    """Lo de `abrir`, en esta máquina (la del agente). Si ya hay un hijo vivo para `ref`, se le escribe a ese."""
    from telar import agentes as mod_agentes
    from telar.agente import lanzar
    from telar.ordenes import _comun
    from telar.servicios import ErrorDeServicio

    agente = next((a for a in mod_agentes.descubrir(ctx.config) if clave in (a.clave, a.nombre)), None)
    if agente is None:
        raise ErrorDeServicio(f"aquí no hay un agente «{clave}»", 404)
    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None:
        raise ErrorDeServicio(tel.aviso or "aquí no hay multiplexor", 409)
    if not tel.viva:
        tel.mux.tejer()
        tel = _comun.tejer(ctx, con_ficha=False)
    # el de esa tarea, si ya está abierto (con otro título corto, también): se le escribe ahí
    previo = next((h for h in tel.hilos if tel.vivo(h) and (h.nombre == hijo or h.nombre.startswith(f"{agente.nombre}{SEPARADOR}{ref} ")
                                                             or h.nombre == f"{agente.nombre}{SEPARADOR}{ref}")), None)
    if previo is not None:
        tel.mux.escribir(previo.id, texto, enviar=True)
        return {"ok": True, "hilo": previo.nombre, "nuevo": False}
    try:
        lanz = lanzar.para_hilo(ctx.config, hijo, agente.carpeta, mensaje=texto)
        tel.mux.crear_tab(hijo, ruta=lanz.carpeta if lanz else agente.carpeta, comando=lanz.comando if lanz else None, foco=False)
    except Exception as e:  # noqa: BLE001 - lo que falle al abrir se dice a quien pidió
        raise ErrorDeServicio(f"no pude abrir «{hijo}»: {e}", 502) from e
    lanzar.anotar(ctx.config, hijo, lanz, tel.mux)
    from telar import estado as mod_estado

    mod_estado.abrir(ctx.config).anotar_abierto_por(hijo, agente.nombre, agente.clave)
    return {"ok": True, "hilo": hijo, "nuevo": True}
