"""`telar evento` — las notas de los eventos del día (`[notas]`, ver `telar.notas`).

    telar evento notas [AAAA-MM-DD] [--json]        las notas de ese día (hoy por defecto)
    telar evento nota <id> "texto" --de planear     dejarle una nota a un evento
        [--titulo "Comité"] [--inicio 10:00] [--dia AAAA-MM-DD]

El evento se nombra por su id en el calendario; el título y la hora van al lado para que la nota se
pueda mostrar aunque el id cambie. El texto también puede llegar por la entrada («-»).
"""

from __future__ import annotations

import sys

from telar import notas as mod
from telar.ordenes import _comun

AYUDA = "Las notas de los eventos del día: verlas y dejarle una a un evento."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("evento", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=("notas", "nota"))
    p.add_argument("args", nargs="*")
    p.add_argument("--de", default="", help="nota: quién la deja (una skill, un hilo, la persona)")
    p.add_argument("--titulo", default="", help="nota: el título del evento")
    p.add_argument("--inicio", default="", help="nota: la hora del evento (HH:MM)")
    p.add_argument("--dia", default="", help="nota: el día (AAAA-MM-DD); por defecto, hoy")
    p.add_argument("--json", action="store_true", help="en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "notas":
        r = mod.leer(ctx.config, o.args[0] if o.args else "")
        if o.json:
            return _comun.escribir_json(r)
        if not r.get("ok"):
            return _comun.queja(r.get("error", "no salió"))
        if r.get("aviso"):
            print(_comun.tenue(r["aviso"]))
        eventos = r.get("eventos", {})
        if not eventos:
            print(_comun.tenue(f"sin notas el {r['dia']}"))
        for eid, e in sorted(eventos.items(), key=lambda x: x[1].get("inicio") or ""):
            print(_comun.fuerte(f"{e.get('inicio', '')} {e.get('titulo') or eid}"))
            for n in e.get("notas", []):
                print(f"  {_comun.tenue(n.get('de', ''))}  {n.get('texto', '')}")
        return 0
    if len(o.args) < 2:
        return _comun.queja('nota lleva el evento y el texto: telar evento nota <id> "texto" --de planear (o «-»)')
    texto = sys.stdin.read() if o.args[1:] == ["-"] else " ".join(o.args[1:])
    r = mod.agregar(ctx.config, o.dia, o.args[0], texto, de=o.de or _de(), titulo=o.titulo, inicio=o.inicio)
    if o.json:
        return _comun.escribir_json(r)
    if not r.get("ok"):
        return _comun.queja(r.get("error", "no salió"))
    print(f"nota en «{o.titulo or o.args[0]}» ({r['dia']})" + (f", guardada en {r['en']}" if r.get("en") else ""))
    return 0


def _de() -> str:
    import os

    return os.environ.get("TELAR_HILO", "").strip() or "alguien"
