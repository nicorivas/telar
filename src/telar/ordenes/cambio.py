"""`telar cambio <tema>` — avisar que algo cambió, para que quien lo muestra lo relea ya.

    telar cambio tareas            las tareas cambiaron (las creó /correo, las cerró un agente…)
    telar cambio tareas --visto    cuándo llegó el último aviso de ese tema a esta máquina (ISO, o vacío)

Con bus, el aviso va a todas las máquinas de la persona: el nodo de cada una lo anota en
`<estado>/cambios/<tema>`, y el dashboard de VS Code, que lo mira cada pocos segundos, relee sin
esperar su vuelta de cinco minutos. Sin bus, se anota solo aquí.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from telar.ordenes import _comun

AYUDA = "Avisar que algo cambió (las tareas), para que el dashboard lo relea ya."


def archivo(config, tema: str) -> Path:
    return Path(config.estado) / "cambios" / tema


def anotar(config, tema: str) -> None:
    """Deja la marca del aviso en esta máquina: el archivo con la hora."""
    f = archivo(config, tema)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("cambio", AYUDA)
    p.epilog = __doc__
    p.add_argument("tema", help="qué cambió: tareas")
    p.add_argument("--visto", action="store_true", help="cuándo llegó aquí el último aviso de ese tema")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if not re.fullmatch(r"[a-z0-9-]{1,40}", o.tema):
        return _comun.queja(f"«{o.tema}» no es un tema: letras, números y guiones")
    if o.visto:
        f = archivo(ctx.config, o.tema)
        print(f.read_text(encoding="utf-8").strip() if f.exists() else "")
        return 0
    from telar import bus as mod_bus

    anotar(ctx.config, o.tema)
    if mod_bus.hay_bus(ctx.config):
        r = mod_bus.anunciar(ctx.config, o.tema)
        if not r.get("ok"):
            return _comun.queja(f"anotado aquí, pero el bus no lo llevó: {r.get('error', '')}")
    print(f"aviso: cambiaron las {o.tema}" if o.tema.endswith("s") else f"aviso: cambió {o.tema}")
    return 0
