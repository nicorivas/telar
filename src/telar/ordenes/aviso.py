"""`telar aviso` — un aviso en la pantalla de otra máquina, por el bus.

    telar aviso "terminó el respaldo" --titulo telar     a las otras máquinas en línea
    telar aviso "listo" --a laptop                       a esa
"""

from __future__ import annotations

from telar import entrega
from telar.ordenes import _comun

AYUDA = "Un aviso en la pantalla de otra máquina, por el bus."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("aviso", AYUDA)
    p.epilog = __doc__
    p.add_argument("texto", nargs="+")
    p.add_argument("--titulo", default="telar")
    p.add_argument("--a", default="", metavar="MAQUINA", help="a esa máquina (por defecto, a las otras en línea)")
    p.add_argument("--json", action="store_true")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        r = entrega.aviso(ctx.config, " ".join(o.texto), titulo=o.titulo, a=o.a)
    except entrega.ErrorDeEntrega as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json({"maquinas": r})
    if not r:
        return _comun.queja("no hay otra máquina en línea a quien avisar")
    for m, error in r.items():
        print(f"{m}: {error or 'avisado'}")
    return 1 if any(r.values()) else 0
