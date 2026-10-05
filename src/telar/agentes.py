"""Agentes residentes: carpetas de un repositorio donde vive un agente con su memoria y su bitácora.

Con `[agentes] carpeta = "agentes"`, cada subcarpeta de esa carpeta que tenga un `CLAUDE.md` es un
agente (las que empiezan con `_` o `.`, como una plantilla, no). telar lo muestra como una sección
más de la lista, dentro del grupo «agentes»: sus hilos debajo y un home que telar arma solo, sin
que el agente escriba nada:

    quién es     el primer párrafo de su CLAUDE.md
    bitácora     sus entradas, la más nueva arriba («## AAAA-MM-DD HH:MM — título» con su cuerpo,
                 o una línea «AAAA-MM-DD HH:MM — texto» por encargo)
    memoria      el índice memoria/MEMORY.md, cada recuerdo con su archivo
    archivos     CLAUDE.md, README.md, bitácora e índice, para abrirlos

Sus hilos son el que lleva su nombre, los vinculados a su carpeta (no a una subcarpeta) y los que declare
`[agentes.<carpeta>] hilos` (un nombre exacto, o un prefijo si termina en `*`). `[agentes.<carpeta>]
home` es un comando que imprime una página (docs/contratos.md): sus bloques van arriba de los que
arma telar. El nombre del agente es el título del README de su carpeta, o el de la carpeta.

Un agente parte en su carpeta, no donde diga `[agente] carpeta`: así carga su CLAUDE.md al arrancar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: el prefijo de la clave de sección de un agente: `agente:gestion`
PREFIJO = "agente:"
#: cuántas entradas de bitácora muestra el home, y cuánto de cada cuerpo
ENTRADAS = 40
CUERPO = 1200

_ENTRADA = re.compile(r"^(?:#{2,3}\s+|-\s+)?(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?\s*[—–-]\s*(.+?)\s*$")
_RECUERDO = re.compile(r"^\s*[-*]\s+\[([^\]]+)\]\(([^)]+)\)\s*(?:[—–-]\s*(.*))?$")


@dataclass(frozen=True)
class Agente:
    clave: str
    nombre: str
    carpeta: Path
    hilos: tuple[str, ...] = ()
    home: tuple[str, ...] = ()
    argumentos: tuple[str, ...] = ()

    @property
    def seccion(self) -> str:
        return PREFIJO + self.clave


def base(config) -> Path | None:
    carpeta = getattr(config, "agentes_carpeta", "")
    if not carpeta:
        return None
    ruta = Path(carpeta).expanduser()
    return ruta if ruta.is_absolute() else Path(config.raiz) / ruta


def _nombre(carpeta: Path) -> str:
    try:
        primera = next((l for l in (carpeta / "README.md").read_text(encoding="utf-8").splitlines() if l.startswith("# ")), "")
    except OSError:
        primera = ""
    nombre = primera[2:].strip().strip("`").rstrip("/").strip()
    return nombre if nombre and nombre.lower() != carpeta.name.lower() else carpeta.name.capitalize()


def descubrir(config, vinculos: dict[str, str] | None = None) -> list[Agente]:
    """Los agentes del repositorio. `vinculos` (hilo → carpeta relativa a la raíz) suma sus hilos."""
    b = base(config)
    if b is None or not b.is_dir():
        return []
    extras = {s.clave: s for s in getattr(config, "agentes_extra", ())}
    raiz = Path(config.raiz)
    salida = []
    for d in sorted(b.iterdir(), key=lambda x: x.name):
        if not d.is_dir() or d.name.startswith(("_", ".")) or not (d / "CLAUDE.md").is_file():
            continue
        nombre = _nombre(d)
        extra = extras.get(d.name)
        hilos = [nombre, *(extra.hilos if extra else ())]
        real = d.resolve()
        for hilo, rel in (vinculos or {}).items():
            try:
                destino = (raiz / rel).resolve()
            except OSError:
                continue
            # solo el vínculo a su casa: un proyecto que vive en una subcarpeta suya no es él
            if destino == real and hilo not in hilos:
                hilos.append(hilo)
        salida.append(Agente(clave=d.name, nombre=nombre, carpeta=d, hilos=tuple(hilos),
                             home=tuple(extra.home) if extra else (), argumentos=tuple(extra.argumentos) if extra else ()))
    return salida


def de_carpeta(config, carpeta: Path | None) -> Agente | None:
    """El agente cuya casa es exactamente esa carpeta, si hay uno (una subcarpeta suya es otra cosa)."""
    if carpeta is None:
        return None
    try:
        real = Path(carpeta).resolve()
    except OSError:
        return None
    for a in descubrir(config):
        if real == a.carpeta.resolve():
            return a
    return None


# ── el home ────────────────────────────────────────────────────────────────────

def _quien(carpeta: Path) -> str:
    """El primer párrafo de su CLAUDE.md: lo que dice de sí mismo antes de cualquier detalle."""
    try:
        lineas = (carpeta / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    parrafo: list[str] = []
    for l in lineas:
        if l.startswith(("#", "@")) or not l.strip():
            if parrafo:
                break
            continue
        parrafo.append(l.strip())
    return " ".join(parrafo)


def bitacora(carpeta: Path) -> list[dict]:
    """Las entradas de su bitácora, la más nueva primero."""
    try:
        lineas = (carpeta / "bitacora.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entradas: list[dict] = []
    for l in lineas:
        m = _ENTRADA.match(l)
        if m:
            fecha = m.group(1) + (f"T{m.group(2)}" if m.group(2) else "")
            entradas.append({"titulo": m.group(3)[:160], "fecha": fecha, "texto": ""})
        elif entradas and not l.startswith("# "):
            entradas[-1]["texto"] += l + "\n"
    for e in entradas:
        cuerpo = e["texto"].strip()
        e["texto"] = cuerpo if len(cuerpo) <= CUERPO else cuerpo[:CUERPO].rstrip() + " […]"
        if not e["texto"]:
            del e["texto"]
    entradas.reverse()
    return entradas[:ENTRADAS]


def memoria(carpeta: Path) -> list[dict]:
    """El índice de su memoria: cada recuerdo con su archivo, para abrirlo."""
    indice = carpeta / "memoria" / "MEMORY.md"
    try:
        lineas = indice.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items = []
    for l in lineas:
        m = _RECUERDO.match(l)
        if not m:
            continue
        destino = m.group(2)
        item = {"titulo": m.group(1)}
        if m.group(3):
            item["texto"] = m.group(3).strip()
        if not re.match(r"^[a-z]+://", destino):
            destino = str((indice.parent / destino).resolve())
        item["enlace"] = destino
        items.append(item)
    return items


def pagina(a: Agente) -> dict:
    """El home de un agente, con la forma del contrato de una página (docs/contratos.md)."""
    from telar.ordenes.seccion import correr

    bloques: list[dict] = []
    subtitulo = ""
    if a.home:
        propia, problema = correr(a.home, f"el home de {a.nombre}")
        if propia:
            subtitulo = propia.get("subtitulo", "")
            bloques.extend(propia.get("bloques", []))
        else:
            bloques.append({"titulo": "su home", "texto": problema, "color": "rojo"})
    quien = _quien(a.carpeta)
    if quien and not a.home:
        bloques.insert(0, {"texto": quien})
    entradas = bitacora(a.carpeta)
    bloques.append({"titulo": f"bitácora · {len(entradas)}" if entradas else "bitácora",
                    **({"items": entradas} if entradas else {"texto": "todavía nada: una línea por encargo en bitacora.md"})})
    recuerdos = memoria(a.carpeta)
    bloques.append({"titulo": f"memoria · {len(recuerdos)}" if recuerdos else "memoria",
                    **({"items": recuerdos} if recuerdos else {"texto": "su índice, memoria/MEMORY.md, está vacío"})})
    archivos = [(n, a.carpeta / r) for n, r in (("CLAUDE.md: quién es", "CLAUDE.md"), ("README.md: su mapa", "README.md"),
                                                ("bitácora", "bitacora.md"), ("índice de su memoria", "memoria/MEMORY.md"))]
    bloques.append({"titulo": "archivos", "items": [{"titulo": n, "enlace": str(r)} for n, r in archivos if r.exists()]})
    return {"titulo": a.nombre, "subtitulo": subtitulo or str(a.carpeta), "bloques": bloques}
