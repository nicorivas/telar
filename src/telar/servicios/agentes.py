"""Los agentes residentes para la página: la ficha de uno (`GET /agentes/del-hilo?hilo=…`: su definición, su
CLAUDE.md, su último relevo y cuánto pesa su conversación), que usa la barra de la derecha al ver el hilo de un
agente; la lista de todos con su estado y sus encargos (`GET /agentes`, la vista de agentes del dashboard), y
rotar a uno ya (`POST /agentes/rotar`). Lo de un agente que vive en otra máquina se le pide a esa por el bus.

El CLAUDE.md, la definición y la carpeta se leen de aquí (el repositorio está en todas las máquinas); el relevo y el
peso de la conversación, también: son de esta máquina, así que para el hilo de un agente que vive en otra no se
saben todavía (`aqui: false`).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio

#: lo más que se manda de un CLAUDE.md o de un relevo (caracteres)
MAX_TEXTO = 120_000


class FichaAgente(BaseModel):
    """`agente` (lo de `telar agentes --json`), `claude_md`, `relevo` ({texto, cuando} o null), `conversacion`
    ({id, peso, tope}), `rotacion` (la fase si está rotando, o ""), `aqui` (si vive en esta máquina)."""

    model_config = ConfigDict(extra="allow")


def _texto(ruta: Path) -> str:
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")[:MAX_TEXTO]
    except OSError:
        return ""


def del_hilo(ctx, hilo: str, *, maquina: str = "") -> FichaAgente:
    from telar import agente as mod_agente
    from telar import agentes as mod_agentes
    from telar import bus as mod_bus
    from telar import estado as mod_estado
    from telar import rotacion

    a = mod_agentes.del_hilo(ctx.config, hilo)
    if a is None:
        raise ErrorDeServicio(f"«{hilo}» no es el hilo de un agente", 404)
    aqui = not maquina or maquina in ("aqui", "local") or (mod_bus.hay_bus(ctx.config) and maquina == mod_bus.maquina(ctx.config))
    ficha: dict = {"agente": mod_agentes.como_json(a), "claude_md": _texto(a.carpeta / "CLAUDE.md"),
                   "definicion_texto": _texto(a.definicion) if a.definicion else "", "aqui": aqui,
                   "relevo": None, "conversacion": None, "rotacion": ""}
    corto = lambda e: {k: e.get(k) for k in ("id", "estado", "texto", "de", "creado", "actualizado", "resultado")}  # noqa: E731
    if not aqui:
        # sus encargos viven en su máquina: se le preguntan por el bus (si no responde, sin ellos)
        r = mod_bus.pedir(ctx.config, maquina, "encargo", {"lista": a.nombre}, espera=8) \
            if mod_bus.hay_bus(ctx.config) else {}
        ficha["encargos"] = [corto(e) for e in (r.get("encargos") or [])][:10] if r.get("ok") else []
        return FichaAgente(**ficha)
    from telar import encargo as mod_encargo

    ficha["encargos"] = [corto(e) for e in mod_encargo.de_hilo(ctx.config, a.nombre)][:10]
    relevo = rotacion.ruta_relevo(ctx.config, a.clave)
    if relevo.is_file():
        ficha["relevo"] = {"texto": _texto(relevo), "ruta": str(relevo),
                           "cuando": datetime.fromtimestamp(relevo.stat().st_mtime).astimezone().isoformat(timespec="seconds")}
    est = mod_estado.abrir(ctx.config)
    sid = (est.sesiones().get(hilo) or ("",))[0]
    if sid and ctx.config.agente.nombre:
        try:
            archivo = mod_agente.obtener(ctx.config.agente.nombre, ctx.config).archivo_de(sid)
            peso = Path(archivo).stat().st_size if archivo else 0
        except Exception:  # noqa: BLE001 - sin el archivo, no se sabe el peso
            peso = 0
        ficha["conversacion"] = {"id": sid, "peso": peso, "tope": rotacion.tope(ctx.config)}
    ficha["rotacion"] = (rotacion.leer(ctx.config).get(hilo) or {}).get("fase", "")
    return FichaAgente(**ficha)


class Agentes(BaseModel):
    """`agentes`: [{agente, maquina, aqui, vivo, atencion, conversacion, rotacion, relevo, encargos}], y `problemas`
    (una máquina que no respondió)."""

    model_config = ConfigDict(extra="allow")


def _de_aqui(a, config) -> bool:
    return (a.en or getattr(config, "agentes_en", "")) in ("", "aqui")


def estado_local(ctx) -> list[dict]:
    """El estado de los agentes que viven en esta máquina: vivo, atención, peso de su conversación, rotación,
    relevo y sus encargos abiertos (y los últimos cerrados)."""
    from telar import agentes as mod_agentes
    from telar import encargo as mod_encargo
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx, con_ficha=False)
    salida = []
    for a in mod_agentes.descubrir(ctx.config, tel.estado.vinculos() if tel.estado else None):
        if not _de_aqui(a, ctx.config):
            continue
        f = del_hilo(ctx, a.nombre).model_dump()
        h = tel.por_nombre(a.nombre)
        todos = mod_encargo.de_hilo(ctx.config, a.nombre)
        abiertos = [e for e in todos if e.get("estado") not in mod_encargo.CERRADOS]
        cerrados = [e for e in todos if e.get("estado") in mod_encargo.CERRADOS][:5]
        resumen = lambda e: {k: e.get(k) for k in ("id", "estado", "texto", "de", "creado", "actualizado", "resultado")}  # noqa: E731
        salida.append({"agente": f["agente"], "maquina": "", "aqui": True,
                       "vivo": bool(h and tel.vivo(h)), "atencion": h.atencion.value if h else "ninguna",
                       "conversacion": f["conversacion"], "rotacion": f["rotacion"],
                       "relevo": {"cuando": f["relevo"]["cuando"]} if f["relevo"] else None,
                       "encargos": [resumen(e) for e in abiertos] + [resumen(e) for e in cerrados]})
    return salida


def lista(ctx) -> Agentes:
    """Todos los agentes: los de aquí con su estado, y los de otras máquinas preguntándole a cada una por el bus."""
    from telar import agentes as mod_agentes
    from telar import bus as mod_bus

    salida = estado_local(ctx)
    problemas = []
    vistos = {x["agente"]["clave"] for x in salida}
    otros = [a for a in mod_agentes.descubrir(ctx.config) if a.clave not in vistos]
    maquinas = sorted({a.en or ctx.config.agentes_en for a in otros} - {"", "aqui"})
    for maquina in maquinas:
        r = mod_bus.pedir(ctx.config, maquina, "agentes", {}) if mod_bus.hay_bus(ctx.config) else \
            {"ok": False, "error": "sin bus"}
        if r.get("ok"):
            for x in r.get("agentes") or []:
                if x["agente"]["clave"] not in vistos:
                    vistos.add(x["agente"]["clave"])
                    salida.append({**x, "maquina": maquina, "aqui": False})
        else:
            problemas.append(f"{maquina}: {r.get('error', 'no respondió')}")
    # los que no aparecen en ninguna (su máquina no respondió): con lo que dice su definición
    for a in otros:
        if a.clave not in vistos:
            salida.append({"agente": mod_agentes.como_json(a), "maquina": a.en or ctx.config.agentes_en, "aqui": False,
                           "vivo": False, "atencion": "ninguna", "conversacion": None, "rotacion": "", "relevo": None,
                           "encargos": [], "sin_noticias": True})
    salida.sort(key=lambda x: x["agente"]["nombre"].casefold())
    return Agentes(agentes=salida, problemas=problemas)


def rotar_aqui(ctx, hilo: str) -> dict:
    """Rotar ya la conversación del agente de `hilo`, que vive aquí: su pedido de relevo, a su casilla."""
    from telar import agentes as mod_agentes
    from telar import bus as mod_bus
    from telar import casilla, encargos, rotacion
    from telar import estado as mod_estado
    from telar.modelo import Atencion

    a = mod_agentes.del_hilo(ctx.config, hilo)
    if a is None:
        raise ErrorDeServicio(f"«{hilo}» no es el hilo de un agente", 404)
    est = mod_estado.abrir(ctx.config)
    sesion = (est.sesiones().get(a.nombre) or ("",))[0]
    escribir = encargos._donde(ctx, a.nombre)
    if escribir is None or not sesion:
        raise ErrorDeServicio(f"«{a.nombre}» no tiene sesión abierta aquí: no hay conversación que rotar", 409)
    texto = rotacion.forzar(ctx.config, a.nombre, a.clave, sesion)
    casilla.dejar(ctx.config, a.nombre, mod_bus.mensaje(texto, de="telar", para=a.nombre))
    if est.atencion(a.nombre) != Atencion.TRABAJANDO and not casilla.mod_vivo(ctx.config, a.nombre):
        escribir(casilla.aviso(ctx.config, a.nombre))
    return {"ok": True, "hilo": a.nombre, "hecho": "se le pidió su relevo: al terminar ese turno rota"}


def rotar(ctx, hilo: str, maquina: str = "") -> dict:
    from telar import bus as mod_bus

    if not maquina or maquina in ("aqui", "local") or (mod_bus.hay_bus(ctx.config) and maquina == mod_bus.maquina(ctx.config)):
        return rotar_aqui(ctx, hilo)
    r = mod_bus.pedir(ctx.config, maquina, "agentes", {"rotar": hilo})
    if not r.get("ok"):
        raise ErrorDeServicio(str(r.get("error") or f"{maquina} no respondió"), int(r.get("codigo") or 502))
    return r
