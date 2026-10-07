"""El calendario de la página web (`telar web`): lo mismo que el calendario del dashboard de VS Code.

Lee un día —los eventos de `telar hoy --dia`, las notas de `telar evento notas`, el plan del día y el agente que
recibe lo sin proyecto— y deja hacer tres cosas sobre un evento: una nota (`telar evento nota`), preparar o
sacar la minuta de la reunión (`telar reunion`) y escribirle al agente general con la reunión como contexto.

La página nombra un evento por su **id** y el día; título, hora, enlace e invitados salen siempre de la agenda
que lee el servidor, nunca de lo que mande la página. Todo se corre con `telar …` como subproceso, sin shell.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

DIA = re.compile(r"\d{4}-\d{2}-\d{2}")
HORA = re.compile(r"\d{2}:\d{2}")
MAX_TEXTO = 4000
VIGENCIA = 60.0
_cache: dict[str, tuple[float, dict]] = {}
_candado = threading.Lock()
_ultimo = [0.0]
ENTRE_ESCRITURAS = 1.0


def _telar(args: list[str], entrada: str | None = None, timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "telar", *args], input=entrada, capture_output=True, text=True, timeout=timeout)


def _json(args: list[str], timeout: int = 90) -> dict:
    r = _telar([*args, "--json"], timeout=timeout)
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(detalle[-1] if detalle else f"telar {args[0]} salió con {r.returncode}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def general(config) -> dict | None:
    """El agente que recibe lo que no tiene proyecto (`[agentes] sin_proyecto`): `{clave, nombre}`."""
    clave = getattr(config, "agentes_sin_proyecto", "")
    if not clave:
        return None
    from telar import agentes as mod_agentes

    a = next((x for x in mod_agentes.descubrir(config) if clave in (x.clave, x.nombre)), None)
    return {"clave": a.clave, "nombre": a.nombre} if a else None


def _plan_de(plan_dir: Path | None, fecha: str) -> dict | None:
    """El plan JSON de ese día, si hay (los de formato markdown no llevan agenda estructurada)."""
    if plan_dir is None:
        return None
    archivo = plan_dir / f"{fecha}.json"
    try:
        return json.loads(archivo.read_text(encoding="utf-8")) if archivo.is_file() else None
    except (OSError, ValueError):
        return None


def dia(config, plan_dir: Path | None, fecha: str, fresco: bool = False) -> tuple[int, dict]:
    """`GET /api/calendario?dia=`: la agenda del día, sus notas, su plan y el agente general. `fecha` vacía es hoy."""
    if fecha and not DIA.fullmatch(fecha):
        return 400, {"error": "el día tiene que ser AAAA-MM-DD"}
    clave = fecha or "hoy"
    with _candado:
        hora, cuerpo = _cache.get(clave, (0.0, {}))
        if cuerpo and not fresco and time.monotonic() - hora < VIGENCIA:
            return 200, cuerpo
    try:
        hoy = _json(["hoy", *(["--dia", fecha] if fecha else [])])
        notas = _json(["evento", "notas", *([fecha] if fecha else [])], timeout=30)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
        return 502, {"error": f"no pude leer el calendario: {str(e)[:160]}"}
    real = hoy.get("fecha") or fecha or dt.date.today().isoformat()
    cuerpo = {
        "dia": real, "hoy": dt.date.today().isoformat(), "agenda": hoy.get("agenda"),
        "fallas": (hoy.get("proveedores") or {}).get("fallas", []),
        "notas": notas.get("eventos", {}) if notas.get("ok") else {},
        "aviso": "" if notas.get("ok") else str(notas.get("error", ""))[:160],
        "plan": _plan_de(plan_dir, real), "general": general(config),
    }
    with _candado:
        _cache[clave] = (time.monotonic(), cuerpo)
    return 200, cuerpo


def _evento(config, plan_dir, fecha: str, id_: str) -> tuple[dict | None, dict | None]:
    """El evento `id_` de la agenda de ese día y el bloque de su plan (si lo hay). Lee la agenda aquí."""
    codigo, d = dia(config, plan_dir, fecha)
    if codigo != 200:
        return None, None
    e = next((x for x in d.get("agenda") or [] if x.get("id") == id_ and not x.get("todo_el_dia")), None)
    if e is None:
        return None, None
    ini = (e.get("cuando") or "")[11:16]
    x = next((p for p in (d.get("plan") or {}).get("agenda", [])
              if p.get("evento") == id_ or (str(p.get("inicio", ""))[:5] == ini and _parecidos(e.get("texto", ""), str(p.get("titulo", "")))) ), None)
    return e, x


def _normal(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in s if not unicodedata.combining(c)))).strip()


def _parecidos(a: str, b: str) -> bool:
    x = {w for w in _normal(a).split() if len(w) > 3}
    return any(w in x for w in _normal(b).split() if len(w) > 3)


def _validar(datos: object, *claves: str) -> str:
    if not isinstance(datos, dict) or not all(isinstance(datos.get(k, ""), str) for k in claves):
        return "faltan o no son válidos " + ", ".join(claves)
    if not DIA.fullmatch(datos.get("dia", "")):
        return "el día tiene que ser AAAA-MM-DD"
    ident = datos.get("id", "")
    if not ident or len(ident) > 300 or not ident.isprintable():
        return "falta el evento"
    return ""


def _espaciar() -> str:
    with _candado:
        ahora = time.monotonic()
        if ahora - _ultimo[0] < ENTRE_ESCRITURAS:
            return "muy rápido: una cosa a la vez"
        _ultimo[0] = ahora
    return ""


def _invalidar(fecha: str) -> None:
    with _candado:
        _cache.pop(fecha, None)
        _cache.pop("hoy", None)


def nota(config, plan_dir, datos: object) -> tuple[int, dict]:
    """`POST /api/evento/nota {dia, id, texto}`: una nota de Nico sobre un evento, donde viven las notas."""
    malo = _validar(datos, "dia", "id", "texto")
    if malo:
        return 400, {"ok": False, "error": malo}
    texto = datos["texto"].strip()
    if not texto:
        return 400, {"ok": False, "error": "la nota está vacía"}
    if len(texto) > MAX_TEXTO:
        return 413, {"ok": False, "error": f"la nota pasa de {MAX_TEXTO} caracteres"}
    e, _ = _evento(config, plan_dir, datos["dia"], datos["id"])
    if e is None:
        return 404, {"ok": False, "error": "no encuentro ese evento en el calendario de ese día"}
    if (r := _espaciar()):
        return 429, {"ok": False, "error": r}
    return _dejar_nota(e, datos["dia"], texto)


def _dejar_nota(e: dict, fecha: str, texto: str) -> tuple[int, dict]:
    try:
        r = _json(["evento", "nota", e["id"], texto, "--de", "Nico", "--titulo", e.get("texto", ""),
                   "--inicio", (e.get("cuando") or "")[11:16], "--dia", fecha], timeout=30)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as ex:
        return 502, {"ok": False, "error": f"la nota no se guardó: {str(ex)[:160]}"}
    _invalidar(fecha)
    return (200, {"ok": True}) if r.get("ok", True) else (502, {"ok": False, "error": str(r.get("error", ""))[:160]})


def reunion(config, plan_dir, datos: object, proyectos: set[str]) -> tuple[int, dict]:
    """`POST /api/evento/reunion {dia, id[, proyecto]}`: prepara la reunión (o saca su minuta, según la hora).

    Sin `proyecto`, si no se deduce de qué es, no abre nada y devuelve los candidatos (`hecho: "preguntar"`) para que
    la página deje elegir; con `proyecto` (la ruta de un candidato o de un proyecto, o «gestion») lo recuerda y abre."""
    malo = _validar(datos, "dia", "id", "proyecto")
    if malo:
        return 400, {"ok": False, "error": malo}
    e, _ = _evento(config, plan_dir, datos["dia"], datos["id"])
    if e is None:
        return 404, {"ok": False, "error": "no encuentro ese evento en el calendario de ese día"}
    proyecto = datos.get("proyecto", "")
    if proyecto and proyecto != "gestion" and proyecto not in proyectos:
        return 404, {"ok": False, "error": "esa carpeta no es una unidad de `telar proyectos`"}
    if (r := _espaciar()):
        return 429, {"ok": False, "error": r}
    args = ["reunion", e.get("texto", ""), (e.get("cuando") or "")[11:16], "--evento", e["id"]]
    if e.get("url"):
        args += ["--enlace", e["url"]]
    if e.get("asistentes"):
        args += ["--asistentes", ",".join(e["asistentes"])]
    if datos["dia"] != dt.date.today().isoformat():
        args += ["--fecha", datos["dia"]]
    args += ["--proyecto", proyecto] if proyecto else ["--preguntar"]
    try:
        r = _json(args, timeout=60)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as ex:
        return 502, {"ok": False, "error": f"no pude abrir la reunión: {str(ex)[:160]}"}
    return 200, {"ok": True, **r}


def escribir(config, plan_dir, datos: object) -> tuple[int, dict]:
    """`POST /api/evento/escribir {dia, id, texto}`: le escribe al agente general sobre una reunión, con todo lo que
    necesita para no preguntar (la reunión, su proyecto, lo que dicen el plan y las notas); queda una nota en el evento."""
    malo = _validar(datos, "dia", "id", "texto")
    if malo:
        return 400, {"ok": False, "error": malo}
    texto = datos["texto"].strip()
    if not texto:
        return 400, {"ok": False, "error": "el mensaje está vacío"}
    if len(texto) > MAX_TEXTO:
        return 413, {"ok": False, "error": f"el mensaje pasa de {MAX_TEXTO} caracteres"}
    agente = general(config)
    if agente is None:
        return 409, {"ok": False, "error": "no hay un agente que reciba lo sin proyecto ([agentes] sin_proyecto)"}
    fecha = datos["dia"]
    e, p = _evento(config, plan_dir, fecha, datos["id"])
    if e is None:
        return 404, {"ok": False, "error": "no encuentro ese evento en el calendario de ese día"}
    if (r := _espaciar()):
        return 429, {"ok": False, "error": r}
    hm = (e.get("cuando") or "")[11:16]
    fin = (e.get("fin") or "")[11:16]
    proyecto = "Proyecto: ninguno deducido."
    try:
        d = _json(["reunion", e.get("texto", ""), hm, "--evento", e["id"], "--preguntar", "--donde",
                   *(["--enlace", e["url"]] if e.get("url") else []),
                   *(["--asistentes", ",".join(e["asistentes"])] if e.get("asistentes") else [])], timeout=40)
        if d.get("destino") and d["destino"] != "gestion":
            proyecto = f"Proyecto: {d['destino']}" + (" (elegido por Nico para esta serie)." if d.get("recordado") else " (deducido).")
        elif d.get("candidatos"):
            proyecto = "Proyecto: no está claro; candidatos: " + "; ".join(
                f"{c['ruta']} ({', '.join(c.get('motivos', []))})" for c in d["candidatos"][:3]) + "."
    except (RuntimeError, ValueError, subprocess.TimeoutExpired):
        pass
    notas = (_notas_de(e, hm, fecha))
    f = (p or {}).get("ficha") or {}
    lineas = [
        f"[Nico, desde el calendario de la web] {texto}", "",
        f"Contexto. La reunión: «{e.get('texto', '')}», {fecha} de {hm} a {fin}" + (f", {e['lugar']}" if e.get("lugar") else "") + ".",
        f"Asistentes: {', '.join(e['asistentes'])}." if e.get("asistentes") else "",
        proyecto,
        f"El plan del día dice: {p['nota']}" if p and p.get("nota") else "",
        f"Decisión que pide el plan: {f['decision']}" if f.get("decision") else "",
        f"Notas del evento: {' | '.join(notas)}" if notas else "",
        f"Id del evento: {e['id']}. Si lo que hagas es de esta reunión, déjale una nota: telar evento nota \"{e['id']}\" \"…\" "
        f"--de {agente['clave']} --titulo \"{e.get('texto', '')}\" --inicio {hm} --dia {fecha}",
    ]
    r = _telar(["encargar", agente["clave"], "-", "--json"], entrada="\n".join(x for x in lineas if x), timeout=40)
    if r.returncode != 0:
        return 502, {"ok": False, "error": f"no llegó a {agente['nombre']}: {(r.stderr or r.stdout).strip()[-160:]}"}
    _dejar_nota(e, fecha, f"A {agente['nombre']}: {texto}")
    return 200, {"ok": True, "hilo": agente["nombre"]}


def _notas_de(e: dict, hm: str, fecha: str) -> list[str]:
    try:
        n = _json(["evento", "notas", fecha], timeout=30).get("eventos", {})
    except (RuntimeError, ValueError, subprocess.TimeoutExpired):
        return []
    x = n.get(e["id"]) or next((v for v in n.values() if v.get("inicio") == hm and _parecidos(v.get("titulo", ""), e.get("texto", ""))), None)
    return [f"{m.get('de', '')}: {m.get('texto', '')}" for m in (x or {}).get("notas", [])]
