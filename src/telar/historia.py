"""Leer lo que pasó en un hilo: sus últimos turnos, en texto, para otro hilo o la otra máquina.

Un turno empieza con lo que escribió la persona (o el mensaje que le llegó al hilo) y sigue con
lo que hizo y contestó el agente. Las herramientas van en una línea cada una —cuál y sobre qué—,
nunca con su salida: la conversación de un día entero pesa megas, y lo que se quiere saber es qué
se pidió y qué se respondió.

La fuente es la conversación anotada del agente, la primera que tenga archivo (la elige y la lee
`telar.conversacion`, el mismo lector que usa la web). Si no hay ninguna
(un hilo sin agente, uno remoto cuya conversación vive en la otra máquina), el scrollback del
panel, si sigue vivo.

Todo tiene tope: cuántos turnos, cuánto texto por mensaje y cuánto en total. Al pasarse del total
se sueltan los turnos más viejos, y si uno solo no cabe, se corta su texto.
"""

from __future__ import annotations

import fnmatch

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

    try:
        sid, mensajes, _ = conversacion.mensajes_del_hilo(ctx.config, list(hilo.sesiones))
    except conversacion.ErrorDeConversacion:
        pass  # sin conversación aquí: el panel, si sigue vivo
    else:
        todos = turnos(mensajes)
        elegidos, cortado = recortar(todos, ultimos)
        return {"hilo": hilo.nombre, "fuente": "conversacion", "conversacion": sid,
                "total_turnos": len(todos), "turnos": elegidos, "recortado": cortado}
    if tel.mux is not None and tel.vivo(hilo):
        panel = tel.mux.pane_de(hilo.id)
        texto = tel.mux.capturar_pane(panel.id, LINEAS_PANEL) if panel is not None else None
        if texto is not None:
            texto = "\n".join(l.rstrip() for l in texto.rstrip().splitlines())
            return {"hilo": hilo.nombre, "fuente": "panel", "texto": texto[-MAX_TOTAL:],
                    "recortado": len(texto) > MAX_TOTAL}
    raise ErrorDeHistoria(f"«{hilo.nombre}» no tiene conversación en esta máquina ni panel vivo que leer")


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
            else:
                lineas.append(f"\n{m['quien']}{' ' + hora if hora else ''}:\n{m['texto']}")
    return "\n".join(lineas)
