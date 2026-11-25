"""Dónde guarda Claude Code las conversaciones en esta máquina, calculado en un solo lugar.

Claude Code guarda cada conversación en `<su carpeta>/projects/<la carpeta donde arrancó, aplanada>/<id>.jsonl`, y
junto a ella una carpeta `<id>/` (resultados guardados, subagentes). La carpeta aplanada es la ruta con todo lo que no
es letra o número hecho «-»: `/Users/ana/vida` es `-Users-ana-vida`, y `/home/ana/vida`, `-home-ana-vida`. Por eso
la misma conversación vive en carpetas distintas en el laptop y en el servidor, y quien la mueve de una máquina a otra
tiene que calcular la de destino allá. Antes se calculaba en tres lugares (la llegada por el bus, el guion que corre
allá por ssh y la carpeta remota); ahora se calcula aquí.

    claude()                      ~/.claude, o lo que diga $CLAUDE_CONFIG_DIR
    proyectos()                   su carpeta projects/
    aplanar(ruta)                 el nombre de la carpeta de un proyecto
    proyecto(inicio)              la carpeta de las conversaciones del agente que arranca en `inicio`
    conversacion(sid)             el .jsonl de una conversación, donde esté (o None)
    de_aqui(ruta)                 una ruta de otra máquina (`/home/ana/…` en el laptop), como sería aquí
"""

from __future__ import annotations

import os
import re
from pathlib import Path

#: lo que Claude Code reemplaza por «-» al aplanar la carpeta de un proyecto
NO_LETRA = re.compile(r"[^A-Za-z0-9]")


def claude() -> Path:
    """Dónde guarda Claude Code lo suyo en esta máquina."""
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(base).expanduser() if base else Path.home() / ".claude"


def proyectos() -> Path:
    return claude() / "projects"


def aplanar(ruta: str | Path) -> str:
    """El nombre de la carpeta de proyecto que Claude Code le da a `ruta` (absoluta)."""
    return NO_LETRA.sub("-", str(ruta))


def proyecto(inicio: str | Path) -> Path:
    """La carpeta donde Claude Code guarda las conversaciones de un agente que arranca en `inicio`: la ruta real (como
    la ve el proceso, sin enlaces), aplanada."""
    return proyectos() / aplanar(Path(inicio).expanduser().resolve())


def conversacion(sid: str, preferida: Path | None = None) -> Path | None:
    """El `.jsonl` de la conversación `sid` en esta máquina: en `preferida` (una carpeta de proyecto) si está ahí, y si
    no, en la primera carpeta de proyecto que la tenga. None si no está."""
    if not sid:
        return None
    if preferida is not None and (preferida / f"{sid}.jsonl").is_file():
        return preferida / f"{sid}.jsonl"
    try:
        return next((p for p in proyectos().glob(f"*/{sid}.jsonl") if p.is_file()), None)
    except OSError:
        return None


#: el comienzo del hogar de una persona, en Linux o en macOS
HOGAR = re.compile(r"^/(?:home|Users)/[^/]+(?=/|$)")


def de_aqui(ruta: str | Path) -> Path:
    """Una ruta que puede venir de otra máquina (la conversación de un hilo que vivió en el servidor nombra
    `/home/ana/vida/x.md`; aquí es `/Users/ana/vida/x.md`): si no existe tal cual y empieza en un hogar, la misma bajo
    el hogar de aquí, si eso existe (o su carpeta). Si no, tal cual."""
    p = Path(ruta)
    if p.exists() or not HOGAR.match(str(p)):
        return p
    otra = Path(HOGAR.sub(lambda _: str(Path.home()), str(p), count=1))
    return otra if otra.exists() or otra.parent.exists() else p
