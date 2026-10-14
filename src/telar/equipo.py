"""El equipo: lo que una persona de confianza puede ver de tus tareas y pedirte.

Marcelo (u otra persona) mira el estado de las tareas que marcaste para el equipo y te
**sugiere** subir una prioridad. Nada más: no escribe en tus archivos ni habla con tus agentes.
Las sugerencias quedan en una bandeja (un JSONL) que tú decides: aceptar cambia la prioridad
con el CLI de tareas; rechazar la cierra con una nota para quien la hizo.

Qué se comparte, a propósito poco: de cada tarea con la etiqueta `equipo` (o la que diga
`[equipo] etiqueta`), el título, estado, prioridad, fecha, proyecto y la línea de `avance`. **Nunca**
el cuerpo ni la historia de la tarea: ahí está el contexto privado.

Se configura en `~/.config/telar/config.toml`:

    [equipo]
    tareas   = "~/Life/nico/proyectos/tareas"     # una tarea por archivo, con front-matter
    todo     = "~/Life/nico/proyectos/todo"       # el CLI que acepta una sugerencia
    etiqueta = "equipo"
    puerto   = 8766
    [equipo.personas]
    marcelo = "un-token-largo"                    # quién entra y con qué llave
"""

from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from telar import config as mod_config

PUERTO = 8766
#: tareas cerradas que siguen a la vista (días), para que Marcelo vea que se hizo lo que preguntó
RECIENTES = 14
MAX_MOTIVO = 500
_ID = re.compile(r"^T\d{1,5}$")
_CAMPO = re.compile(r"^([a-zñ_]+):\s*(.*)$")


@dataclass(frozen=True)
class Equipo:
    tareas: Path
    todo: Path | None
    etiqueta: str = "equipo"
    puerto: int = PUERTO
    personas: dict[str, str] = field(default_factory=dict)
    bandeja: Path = Path("sugerencias.jsonl")


def cargar(ruta: Path | None = None, *, estado: Path | None = None) -> Equipo:
    """`[equipo]` del config. Falta o está incompleto → ValueError con qué falta."""
    ruta = ruta or mod_config.ruta_config()
    datos = tomllib.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    tabla = datos.get("equipo")
    if not isinstance(tabla, dict) or not tabla.get("tareas"):
        raise ValueError("falta [equipo] tareas = \"…\" en el config")
    raiz_estado = estado or Path(os.path.expanduser(str(datos.get("estado", "~/.local/state/telar"))))
    personas = tabla.get("personas", {})
    if not isinstance(personas, dict):
        raise ValueError("[equipo.personas] debe ser una tabla nombre = \"token\"")
    todo = tabla.get("todo")
    return Equipo(
        tareas=Path(os.path.expanduser(str(tabla["tareas"]))),
        todo=Path(os.path.expanduser(str(todo))) if todo else None,
        etiqueta=str(tabla.get("etiqueta", "equipo")).lower(),
        puerto=int(tabla.get("puerto", PUERTO)),
        personas={str(k).lower(): str(v) for k, v in personas.items() if str(v)},
        bandeja=raiz_estado / "equipo" / "sugerencias.jsonl",
    )


def quien(eq: Equipo, token: str) -> str:
    """El nombre de la persona dueña de ese token, o ""."""
    for nombre, esperado in eq.personas.items():
        if token and secrets.compare_digest(token, esperado):
            return nombre
    return ""


def _front(texto: str) -> dict[str, str]:
    """El front-matter, como texto por clave. El cuerpo no se lee."""
    lineas = texto.split("\n")
    if not lineas or lineas[0].strip() != "---":
        return {}
    campos: dict[str, str] = {}
    for linea in lineas[1:]:
        if linea.strip() == "---":
            break
        m = _CAMPO.match(linea)
        if m:
            campos[m.group(1)] = m.group(2).strip()
    return campos


def tareas_visibles(eq: Equipo, hoy: datetime.date | None = None) -> list[dict]:
    """Las tareas marcadas para el equipo, solo con los campos que se comparten."""
    hoy = hoy or datetime.date.today()
    salida: list[dict] = []
    if not eq.tareas.is_dir():
        return salida
    for archivo in sorted(eq.tareas.glob("T*.md")):
        if not _ID.match(archivo.stem):
            continue
        try:
            c = _front(archivo.read_text(encoding="utf-8"))
        except OSError:
            continue
        etiquetas = [e.strip().lower() for e in re.split(r"[,\s]+", c.get("etiquetas", "")) if e.strip()]
        if eq.etiqueta not in etiquetas:
            continue
        estado = c.get("estado", "")
        if estado == "hecha":
            try:
                if (hoy - datetime.date.fromisoformat(c.get("cerrada", ""))).days > RECIENTES:
                    continue
            except ValueError:
                continue
        elif estado not in ("activa", "espera"):
            continue
        try:
            prioridad = int(c.get("prioridad", ""))
        except ValueError:
            prioridad = None
        salida.append({
            "id": archivo.stem, "titulo": c.get("titulo", ""), "estado": estado, "prioridad": prioridad,
            "vence": c.get("vence") or None, "proyecto": Path(c["proyecto"]).name if c.get("proyecto") else None,
            "avance": c.get("avance") or None, "espera": c.get("espera") or None,
        })
    salida.sort(key=lambda t: (t["estado"] == "hecha", 9 if t["prioridad"] is None else t["prioridad"], t["id"]))
    return salida


# --- la bandeja -----------------------------------------------------------------------------

def leer_bandeja(eq: Equipo) -> list[dict]:
    if not eq.bandeja.exists():
        return []
    registros = []
    for linea in eq.bandeja.read_text(encoding="utf-8").splitlines():
        try:
            registros.append(json.loads(linea))
        except ValueError:
            continue
    return registros


def _escribir_bandeja(eq: Equipo, registros: list[dict]) -> None:
    eq.bandeja.parent.mkdir(parents=True, exist_ok=True)
    tmp = eq.bandeja.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros), encoding="utf-8")
    os.replace(tmp, eq.bandeja)


def sugerir(eq: Equipo, persona: str, tarea: str, motivo: str, *, ahora: datetime.datetime | None = None) -> tuple[dict | None, str]:
    """Anota que `persona` sugiere subirle la prioridad a `tarea`. (registro, "") o (None, por qué no)."""
    motivo = " ".join(motivo.split())
    if not 5 <= len(motivo) <= MAX_MOTIVO:
        return None, f"el motivo va de 5 a {MAX_MOTIVO} caracteres"
    visible = next((t for t in tareas_visibles(eq) if t["id"] == tarea), None)
    if visible is None or visible["estado"] == "hecha":
        return None, "esa tarea no está entre las que se comparten"
    if visible["prioridad"] == 0:
        return None, "esa tarea ya es de la prioridad más alta"
    registros = leer_bandeja(eq)
    if any(r["persona"] == persona and r["tarea"] == tarea and r["estado"] == "pendiente" for r in registros):
        return None, "ya hay una sugerencia tuya pendiente para esa tarea"
    ahora = ahora or datetime.datetime.now()
    registro = {
        "id": secrets.token_hex(4), "cuando": ahora.isoformat(timespec="seconds"), "persona": persona,
        "tarea": tarea, "titulo": visible["titulo"], "prioridad": visible["prioridad"],
        "motivo": motivo, "estado": "pendiente", "nota": "",
    }
    registros.append(registro)
    _escribir_bandeja(eq, registros)
    return registro, ""


def resolver(eq: Equipo, ident: str, decision: str, nota: str = "") -> tuple[dict | None, str]:
    """Acepta (sube la prioridad un nivel con el CLI de tareas) o rechaza una sugerencia pendiente."""
    if decision not in ("aceptar", "rechazar"):
        return None, "la decisión es aceptar o rechazar"
    registros = leer_bandeja(eq)
    r = next((x for x in registros if x["id"] == ident and x["estado"] == "pendiente"), None)
    if r is None:
        return None, f"no hay sugerencia pendiente «{ident}»"
    if decision == "aceptar":
        actual = next((t for t in tareas_visibles(eq) if t["id"] == r["tarea"]), None)
        if actual is None or actual["prioridad"] is None:
            return None, "la tarea ya no se comparte o no tiene prioridad"
        nueva = max(0, actual["prioridad"] - 1)
        if eq.todo is None:
            return None, "falta [equipo] todo = \"…\" para cambiar la prioridad"
        p = subprocess.run([str(eq.todo), "edit", r["tarea"], "--pri", str(nueva)], capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            return None, (p.stderr.strip() or p.stdout.strip() or "todo falló")[-300:]
        subprocess.run([str(eq.todo), "nota", r["tarea"], f"prioridad {actual['prioridad']} → {nueva}, sugerida por {r['persona']}: {r['motivo']}"],
                       capture_output=True, text=True, timeout=30)
        r["prioridad_nueva"] = nueva
    r["estado"] = "aceptada" if decision == "aceptar" else "rechazada"
    r["nota"] = " ".join(nota.split())[:MAX_MOTIVO]
    r["resuelta"] = datetime.datetime.now().isoformat(timespec="seconds")
    _escribir_bandeja(eq, registros)
    return r, ""


def avisar(titulo: str, texto: str) -> None:
    """Una notificación al laptop por la puerta (`telar enlace notificar`). Nunca lanza."""
    try:
        subprocess.run(["telar", "enlace", "notificar", texto, "--titulo", titulo], capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        pass
