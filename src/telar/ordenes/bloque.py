"""`telar bloque` — lo que muestra un bloque del día (`[bloques.<clave>]`).

    telar bloque              los bloques declarados
    telar bloque correo --json
    telar bloque correo --abrir "/correo 1a0d9" --nombre "✉ Re: el informe"

Corre el comando del bloque y devuelve su página, validada con el mismo contrato que la de
una sección (docs/contratos.md). El dashboard lo pide con el ritmo de la red.

Un ítem con `mensaje` se abre: `--abrir` crea un hilo nuevo con el agente y ese mensaje
como primer prompt, como un atajo pero para una fila (procesar un correo, no todos).
"""

from __future__ import annotations

import datetime as dt

from telar.ordenes import _comun
from telar.ordenes.atajo import abrir
from telar.ordenes.seccion import correr

AYUDA = "Lo que muestra un bloque del día: corre su comando y devuelve su página."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("bloque", AYUDA)
    p.epilog = __doc__
    p.add_argument("clave", nargs="?", default="", help="cuál; sin ella, la lista")
    p.add_argument("--json", action="store_true", help="la página, en una línea")
    p.add_argument("--abrir", metavar="MENSAJE", default="", help="abrir un hilo con el agente y este mensaje")
    p.add_argument("--nombre", default="", help="el nombre de ese hilo (el del bloque y la hora si falta)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    bloques = {b.clave: b for b in ctx.config.bloques}
    if not o.clave:
        for b in bloques.values():
            print(f"{b.clave}  {b.nombre}  " + _comun.tenue(" ".join(b.comando)))
        if not bloques:
            print(_comun.tenue("no hay bloques: se declaran en la configuración, [bloques.<clave>]"))
        return 0
    b = bloques.get(o.clave)
    if b is None:
        return _comun.queja(f"no hay bloque «{o.clave}»")
    if o.abrir:
        nombre = " ".join(o.nombre.split())[:48] or f"{b.nombre} {dt.datetime.now():%m/%d %H:%M}"
        problema = abrir(ctx, nombre, o.abrir)
        if problema:
            return _comun.queja(problema)
        if o.json:
            return _comun.escribir_json({"hilo": nombre, "mensaje": o.abrir})
        print(f"{nombre} · {o.abrir}")
        return 0
    datos, problema = correr(b.comando, f"el bloque «{o.clave}»")
    if problema:
        return _comun.queja(problema)
    if o.json:
        return _comun.escribir_json(datos)
    for bl in datos.get("bloques", []):
        for x in bl.get("items", []):
            print(f"{x.get('marca', '·'):2} {x.get('fecha', '')[11:16]}  {x.get('texto', '')}  {x.get('titulo', '')}")
    return 0
