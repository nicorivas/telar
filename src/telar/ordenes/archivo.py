"""`telar archivo` — mandar un archivo a la carpeta de entrada de otra máquina, por el bus.

    telar archivo foto.png --a laptop           queda en `[bus] entrada` de esa máquina (nunca pisa otro)

Hasta 700 KB (lo que cabe en un mensaje del bus); para más, git o el panel.
"""

from __future__ import annotations

from pathlib import Path

from telar import entrega
from telar.ordenes import _comun

AYUDA = "Mandar un archivo a la carpeta de entrada de otra máquina, por el bus."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("archivo", AYUDA)
    p.epilog = __doc__
    p.add_argument("ruta")
    p.add_argument("--a", required=True, metavar="MAQUINA")
    p.add_argument("--nombre", default="", help="con otro nombre allá")
    p.add_argument("--json", action="store_true")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        r = entrega.archivo(ctx.config, Path(o.ruta), a=o.a, nombre=o.nombre)
    except (entrega.ErrorDeEntrega, OSError) as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    print(f"{o.a}: {r['ruta']} ({r['bytes']} bytes)")
    return 0
