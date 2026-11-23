"""Leer lo que pasó en un hilo: sus últimos turnos, en texto, para otro hilo o la otra máquina.

Un turno empieza con lo que escribió la persona (o el mensaje que le llegó al hilo) y sigue con
lo que hizo y contestó el agente. Las herramientas van en una línea cada una —cuál y sobre qué—,
nunca con su salida: la conversación de un día entero pesa megas, y lo que se quiere saber es qué
se pidió y qué se respondió.

La fuente es la conversación que deja el mod de telar en la casilla, si es la principal del hilo y el mod
vive (telar/mod/); si no, la conversación anotada del agente, la primera que tenga archivo (la elige y la lee
`telar.conversacion`, el mismo lector que usa la web). Si no hay ninguna
(un hilo sin agente, uno remoto cuya conversación vive en la otra máquina), el scrollback del
panel, si sigue vivo.

Todo tiene tope: cuántos turnos, cuánto texto por mensaje y cuánto en total. Al pasarse del total
se sueltan los turnos más viejos, y si uno solo no cabe, se corta su texto.

Lo que el agente le pregunta a la persona con opciones (AskUserQuestion) viaja en el mensaje de esa herramienta,
en `pregunta`: lo preguntado, lo respondido y su estado. La que espera respuesta es `contestable` si el mod de
telar tiene su diálogo abierto: entonces `responder` le deja la respuesta en la casilla del hilo y el mod la
entrega al diálogo, que se cierra como si la hubieran elegido en la terminal.
"""

from __future__ import annotations

import fnmatch
import json
import os
import time
from pathlib import Path

#: cuántos turnos sin decir, y el máximo que se puede pedir
POR_DEFECTO = 5
MAX_TURNOS = 50
#: caracteres por mensaje y en total (lo que cabe en una respuesta del enlace sin volcar megas)
MAX_MENSAJE = 4000
MAX_TOTAL = 60_000
#: líneas del panel cuando no hay conversación
LINEAS_PANEL = 300


class ErrorDeHistoria(Exception):
    """No hay de dónde leer. El mensaje es lo que se le dice a quien pidió."""


def turnos(mensajes: list[dict]) -> list[list[dict]]:
    """Agrupa los mensajes en turnos: uno nuevo con cada mensaje de la persona."""
    salida: list[list[dict]] = []
    for m in mensajes:
        if m.get("quien") == "usuario" or not salida:
            salida.append([])
        salida[-1].append(m)
    return salida


def _cortar(texto: str, tope: int) -> str:
    return texto if len(texto) <= tope else texto[:tope].rstrip() + f" […{len(texto) - tope} caracteres más]"


def _peso(turno: list[dict]) -> int:
    return sum(len(m.get("texto", "")) for m in turno)


def recortar(todos: list[list[dict]], ultimos: int) -> tuple[list[list[dict]], bool]:
    """Los últimos `ultimos` turnos, con los topes. (turnos, si se cortó algo)."""
    elegidos = [[{**m, "texto": _cortar(m.get("texto", ""), MAX_MENSAJE)} for m in t] for t in todos[-ultimos:]]
    cortado = any(len(m["texto"]) != len(o.get("texto", ""))
                  for t, ot in zip(elegidos, todos[-ultimos:]) for m, o in zip(t, ot))
    while len(elegidos) > 1 and sum(_peso(t) for t in elegidos) > MAX_TOTAL:
        elegidos.pop(0)
        cortado = True
    if elegidos and _peso(elegidos[0]) > MAX_TOTAL:
        # un turno solo que no cabe: el reparto parejo entre sus mensajes
        cada = max(200, MAX_TOTAL // max(1, len(elegidos[0])))
        elegidos[0] = [{**m, "texto": _cortar(m["texto"], cada)} for m in elegidos[0]]
        cortado = True
    return elegidos, cortado


def leer(ctx, tel, hilo, ultimos: int = POR_DEFECTO) -> dict:
    """Lo último de un hilo. Levanta ErrorDeHistoria si no hay conversación ni panel."""
    ultimos = max(1, min(int(ultimos), MAX_TURNOS))
    # los mensajes los lee `telar.conversacion`, el único lector: la misma conversación que ve la web
    from telar import conversacion

    del_mod = _del_mod(ctx.config, hilo)
    try:
        sid, mensajes, origen = (*del_mod, "mod") if del_mod else (
            *conversacion.mensajes_del_hilo(ctx.config, list(hilo.sesiones))[:2], "registro")
    except conversacion.ErrorDeConversacion:
        pass  # sin conversación aquí: el panel, si sigue vivo
    else:
        todos = turnos(_con_preguntas(ctx.config, tel, hilo, mensajes))
        elegidos, cortado = recortar(todos, ultimos)
        return {"hilo": hilo.nombre, "fuente": "conversacion", "conversacion": sid, "origen": origen,
                "total_turnos": len(todos), "turnos": elegidos, "recortado": cortado}
    if tel.mux is not None and tel.vivo(hilo):
        panel = tel.mux.pane_de(hilo.id)
        texto = tel.mux.capturar_pane(panel.id, LINEAS_PANEL) if panel is not None else None
        if texto is not None:
            texto = "\n".join(l.rstrip() for l in texto.rstrip().splitlines())
            return {"hilo": hilo.nombre, "fuente": "panel", "texto": texto[-MAX_TOTAL:],
                    "recortado": len(texto) > MAX_TOTAL}
    raise ErrorDeHistoria(f"«{hilo.nombre}» no tiene conversación en esta máquina ni panel vivo que leer")


def _con_preguntas(config, tel, hilo, mensajes: list[dict]) -> list[dict]:
    """Los mensajes con sus preguntas al día. Una pregunta sin resultado sigue «pendiente» solo si nada vino después
    (ni la persona ni el agente) y su hilo sigue abierto: si no, quedó sin contestar. La que espera es `contestable`
    si el mod la tiene abierta (mod/pregunta.json). Lo leído no se toca (puede ser lo guardado de la conversación):
    las que cambian van copiadas."""
    if not any(m.get("pregunta") for m in mensajes):
        return mensajes
    vivo = tel.vivo(hilo) if getattr(tel, "mux", None) is not None else True
    despues = [False] * len(mensajes)  # si después de cada uno habló la persona o el agente
    hablo = False
    for i in range(len(mensajes) - 1, -1, -1):
        despues[i] = hablo
        hablo = hablo or mensajes[i].get("quien") in ("usuario", "agente")
    abierta = pregunta_abierta(config, hilo.nombre)
    salida = []
    for i, m in enumerate(mensajes):
        p = m.get("pregunta")
        if isinstance(p, dict) and p.get("estado") == "pendiente":
            p = {**p, "estado": "cancelada"} if despues[i] or not vivo else \
                {**p, "contestable": bool(abierta and abierta.get("id") == p.get("id"))}
            m = {**m, "pregunta": p}
        salida.append(m)
    return salida


def _carpeta_mod(config, hilo: str) -> Path:
    from telar import casilla

    return casilla.carpeta(config, hilo) / "mod"


def pregunta_abierta(config, hilo: str) -> dict | None:
    """La pregunta que el mod de telar tiene abierta en el diálogo de un hilo (mod/pregunta.json): `{id, preguntas,
    desde}`, con las preguntas como las hizo el agente. None si no hay, si se cerró o si el mod no vive."""
    from telar import casilla

    if not getattr(config, "estado", None) or not casilla.mod_vivo(config, hilo):
        return None
    try:
        d = json.loads((_carpeta_mod(config, hilo) / "pregunta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("estado") == "abierta" and d.get("id") else None


class ErrorDeRespuesta(ErrorDeHistoria):
    """No se pudo dejar la respuesta. `codigo`: como lo diría la API (409 si la pregunta ya no está abierta, 422 si
    la respuesta no sirve)."""

    def __init__(self, mensaje: str, codigo: int = 409):
        super().__init__(mensaje)
        self.codigo = codigo


#: cuánto se espera a que el mod tome la respuesta (mira cada medio segundo)
ESPERA_RESPUESTA = 6.0


def responder(config, hilo: str, id: str, respuestas: dict, *, esperar: float = ESPERA_RESPUESTA) -> dict:
    """Contestar la pregunta abierta de un hilo de esta máquina: `respuestas` es `{pregunta: respuesta}`, una por
    pregunta (con varias, separadas por coma; lo escrito a mano, tal cual). Deja mod/respuesta.json y espera a que el
    mod la tome. `{ok, tomada, por}`: `tomada` si cerró el diálogo con ella; si antes la contestaron en la terminal,
    `por: "terminal"`. Levanta `ErrorDeRespuesta`."""
    abierta = pregunta_abierta(config, hilo)
    if abierta is None or abierta.get("id") != id:
        raise ErrorDeRespuesta("esa pregunta ya no está abierta (¿la contestaron en la terminal?)")
    textos = [str(q.get("question", "")) for q in abierta.get("preguntas") or [] if isinstance(q, dict)]
    if not isinstance(respuestas, dict) or not textos:
        raise ErrorDeRespuesta("la respuesta va como {pregunta: respuesta}", 422)
    limpias = {str(k): str(v).strip() for k, v in respuestas.items()}
    sobran = [k for k in limpias if k not in textos]
    faltan = [t for t in textos if not limpias.get(t)]
    if sobran or faltan:
        raise ErrorDeRespuesta(f"falta contestar: {', '.join(faltan)}" if faltan
                               else f"eso no se preguntó: {', '.join(sobran)}", 422)
    if any(len(v) > 4000 for v in limpias.values()):
        raise ErrorDeRespuesta("una respuesta de más de 4000 caracteres: mejor, un mensaje", 422)
    carpeta = _carpeta_mod(config, hilo)
    ruta = carpeta / "respuesta.json"
    temporal = carpeta / f".respuesta-{os.getpid()}.json"
    temporal.write_text(json.dumps({"id": id, "respuestas": limpias, "hora": time.time()}, ensure_ascii=False),
                        encoding="utf-8")
    os.replace(temporal, ruta)  # entera o nada: el mod la lee mientras tanto
    hasta = time.monotonic() + esperar
    while True:
        try:
            d = json.loads((carpeta / "pregunta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        if isinstance(d, dict) and d.get("id") == id and d.get("estado") == "cerrada":
            ruta.unlink(missing_ok=True)
            por = str(d.get("por") or "")
            return {"ok": True, "tomada": por == "afuera", "por": por}
        if time.monotonic() >= hasta:
            return {"ok": True, "tomada": False, "por": ""}
        time.sleep(0.1)


def _del_mod(config, hilo) -> tuple[str, list[dict]] | None:
    """La conversación que dejó el mod de telar en la casilla (telar/mod/), si es de la conversación principal
    del hilo y el mod sigue vivo: (id, mensajes). Si no, None, y se lee el registro del agente."""
    import json

    from telar import casilla

    if not hilo.sesiones or not getattr(config, "estado", None) or not casilla.mod_vivo(config, hilo.nombre):
        return None
    try:
        datos = json.loads((casilla.carpeta(config, hilo.nombre) / "mod" / "conversacion.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # todavía no la escribe, o se lee a medio escribir: el registro, esta vez
    if not isinstance(datos, dict) or datos.get("sesion") != hilo.sesiones[0]:
        return None
    from telar.agente.claude_code import mensajes_del_mod

    return hilo.sesiones[0], mensajes_del_mod(datos)


def no_leer(config) -> tuple[str, ...]:
    """Los hilos que otra máquina no puede leer: `[bus] no_leer` (y, de antes, `[enlace] no_leer`)."""
    return tuple(dict.fromkeys([*getattr(config.bus, "no_leer", ()), *getattr(config.puerta, "no_leer", ())]))


def vetado(patrones, nombre: str, carpeta: str) -> bool:
    """Si un hilo está fuera de lo que se puede leer por la puerta (`[enlace] no_leer`).

    Cada patrón (estilo glob, sin distinguir mayúsculas) se prueba contra el nombre del hilo y
    contra su carpeta vinculada; `personal` veta también lo que esté debajo."""
    for p in patrones:
        p = p.strip().casefold()
        if not p:
            continue
        for valor in (nombre.casefold(), carpeta.strip("/").casefold()):
            if valor and (fnmatch.fnmatchcase(valor, p) or fnmatch.fnmatchcase(valor, p.rstrip("/") + "/*")):
                return True
    return False


def _hora_local(iso: str) -> str:
    """«HH:MM» en la hora de esta máquina; el transcript las guarda en UTC."""
    from datetime import datetime

    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except ValueError:
        return iso[11:16]


def como_texto(datos: dict) -> str:
    """Lo leído, para una terminal o para pegar en otra conversación."""
    if datos.get("fuente") == "panel":
        cabeza = f"«{datos['hilo']}» · lo último de su panel (no hay conversación que leer)"
        return f"{cabeza}\n\n{datos['texto']}"
    n, total = len(datos["turnos"]), datos.get("total_turnos", 0)
    lineas = [f"«{datos['hilo']}» · {n} de {total} turno(s) · conversación {datos['conversacion'][:8]}"
              + (" · recortado" if datos.get("recortado") else "")]
    for turno in datos["turnos"]:
        lineas.append("")
        lineas.append("─" * 40)
        for m in turno:
            hora = _hora_local(m.get("hora") or "")
            if m["quien"] == "herramienta":
                lineas.append(f"  › {m['texto']}")
                p = m.get("pregunta") or {}
                if p.get("estado") == "respondida":
                    lineas.extend(f"    → {r}" for r in (p.get("respuestas") or {}).values())
                elif p.get("estado") == "pendiente":
                    lineas.append("    (espera tu respuesta)")
            else:
                lineas.append(f"\n{m['quien']}{' ' + hora if hora else ''}:\n{m['texto']}")
    return "\n".join(lineas)
