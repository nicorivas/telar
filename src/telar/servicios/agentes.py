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
        # los hilos que abrió (no los suyos: los que empezó para otra cosa), los que telar todavía conoce
        abrio = [{"hilo": n, "vivo": bool(tel.por_nombre(n) and tel.vivo(tel.por_nombre(n))),
                  "archivado": bool(tel.por_nombre(n) and tel.por_nombre(n).archivado), "cuando": r.get("cuando", "")}
                 for n, r in (tel.estado.abiertos_por() if tel.estado else {}).items()
                 if r.get("agente") == a.clave and tel.por_nombre(n) is not None]
        salida.append({"agente": f["agente"], "maquina": "", "aqui": True, "abrio": abrio,
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


def abrir_aqui(ctx, agente: str) -> dict:
    """Abrir el hilo de un agente que vive aquí, retomando su conversación si tiene una (lo que hace el nodo con los
    que están para siempre). Sin motor (`[agente] nombre`), 409 diciendo cómo elegirlo."""
    from telar import agentes as mod_agentes
    from telar import encargos

    a = mod_agentes.buscar(ctx.config, agente)
    if a is None:
        raise ErrorDeServicio(f"no hay un agente «{agente}»", 404)
    if not ctx.config.agente.nombre:
        raise ErrorDeServicio("falta elegir con qué se abren los agentes (el motor): ⚙ agente › motor, "
                              "o [agente] nombre = \"claude-code\" en la configuración", 409)
    if encargos._donde(ctx, a.nombre) is not None:
        # abierto, pero quizás solo con una shell: lo que queda si se abrió antes de elegir el motor. Una shell que no
        # corre nada se reemplaza por el agente; si corre algo, se deja (puede ser él, o trabajo a medias)
        if not _solo_shell(ctx, a.nombre):
            return {"ok": True, "hilo": a.nombre, "hecho": "ya estaba abierto"}
    try:
        encargos._abrir(ctx, a, "")
    except Exception as e:  # noqa: BLE001 - el motor no arrancó: se dice por qué
        raise ErrorDeServicio(f"no pude abrir a {a.nombre}: {e}", 409) from e
    return {"ok": True, "hilo": a.nombre, "hecho": "abierto"}


def _donde_vive(ctx, agente: str) -> str:
    """La máquina donde vive un agente ("" si aquí o no se sabe): la de encargarle (telar.servicios.encargos)."""
    from telar.servicios import encargos as servicio_encargos

    try:
        return servicio_encargos.donde_vive(ctx, agente)
    except ErrorDeServicio:
        return ""


def _solo_shell(ctx, hilo: str) -> bool:
    """Si el tab vivo de `hilo` es una shell que no corre nada; si lo es, lo cierra (para abrir ahí al agente)."""
    from telar.agente import lanzar
    from telar.ordenes import _comun

    try:
        tel = _comun.tejer(ctx, con_ficha=False)
        h = tel.por_nombre(hilo)
        if h is None or tel.mux is None or not tel.vivo(h) or lanzar.panel_ocioso(tel.mux.panes(h.id)) is None:
            return False
        tel.mux.cerrar_tab(h.id)
        return True
    except Exception:  # noqa: BLE001 - lo que no se sabe no se cierra
        return False


def abrir(ctx, agente: str, maquina: str = "") -> dict:
    """En la máquina donde vive (la que se diga, o la de su `en`)."""
    from telar import bus as mod_bus

    maquina = maquina or _donde_vive(ctx, agente)
    if not maquina or maquina in ("aqui", "local") or (mod_bus.hay_bus(ctx.config) and maquina == mod_bus.maquina(ctx.config)):
        return abrir_aqui(ctx, agente)
    r = mod_bus.pedir(ctx.config, maquina, "agentes", {"abrir": agente}, espera=60)
    if not r.get("ok"):
        raise ErrorDeServicio(str(r.get("error") or f"{maquina} no respondió"), int(r.get("codigo") or 502))
    return r


def eliminar_aqui(ctx, agente: str) -> dict:
    """Eliminar a un agente de aquí (`telar agentes eliminar`): sus hilos al archivo, su carpeta a `_eliminados`."""
    import json

    from telar.servicios import en_proceso

    c = en_proceso.correr(ctx, "agentes", ["eliminar", agente, "--si", "--json"])
    if c.codigo != 0:
        raise ErrorDeServicio((c.error or c.salida).strip().splitlines()[-1] if (c.error or c.salida).strip() else "no se pudo", 409)
    return {"ok": True, **json.loads(c.salida)}


def eliminar(ctx, agente: str, maquina: str = "") -> dict:
    """En la máquina donde vive (su nodo es el que lo mantiene abierto: apartarlo en otra lo dejaría vivo allá)."""
    from telar import bus as mod_bus

    maquina = maquina or _donde_vive(ctx, agente)
    if not maquina or maquina in ("aqui", "local") or (mod_bus.hay_bus(ctx.config) and maquina == mod_bus.maquina(ctx.config)):
        return eliminar_aqui(ctx, agente)
    r = mod_bus.pedir(ctx.config, maquina, "agentes", {"eliminar": agente}, espera=90)
    if not r.get("ok"):
        raise ErrorDeServicio(str(r.get("error") or f"{maquina} no respondió"), int(r.get("codigo") or 502))
    return r


def nuevo(ctx, nombre: str, para: str = "", icono: str = "") -> dict:
    """Un agente residente nuevo aquí (telar.agentes.crear); 409 si no se puede."""
    from telar import agentes as mod_agentes
    from telar.config import ruta_config

    try:
        return {"ok": True, **mod_agentes.crear(ctx.config, ctx.config.origen or ruta_config(), nombre, para=para,
                                                icono=icono)}
    except (ValueError, OSError) as e:
        raise ErrorDeServicio(str(e), 409) from e
