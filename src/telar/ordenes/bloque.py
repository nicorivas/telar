"""`telar bloque` — lo que muestra un bloque del día (`[bloques.<clave>]`).

    telar bloque              los bloques declarados
    telar bloque correo --json
    telar bloque correo --abrir "/correo 1a0d9" --nombre "✉ Re: el informe"

Corre el comando del bloque y devuelve su página, validada con el mismo contrato que la de
una sección (docs/contratos.md). El dashboard lo pide con el ritmo de la red.

Un ítem con `mensaje` se abre: `--abrir` crea un hilo nuevo con el agente y ese mensaje
como primer prompt, como un atajo pero para una fila (procesar un correo, no todos).

    telar bloque correo --item 1a0d9 --json

El detalle de un ítem con `id` (el cuerpo de un correo), que el dashboard pide al abrirlo y no
en cada lectura: corre el comando del bloque con `--item <id>` al final, que imprime
`{"texto": "…"}`. Un bloque que no lo sabe hacer sale con error, y el dashboard no lo muestra.
"""

from __future__ import annotations

import json
import subprocess

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
    p.add_argument("--item", metavar="ID", default="", help="el detalle de un ítem (su cuerpo): el comando con --item ID")
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
    if o.item:
        try:
            r = subprocess.run([*b.comando, "--item", o.item], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
            detalle = json.loads(r.stdout) if r.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired, ValueError) as e:
            return _comun.queja(f"el detalle de {o.item} no corrió: {e}")
        if not isinstance(detalle, dict) or not isinstance(detalle.get("texto"), str):
            return _comun.queja(f"el bloque «{o.clave}» no dio el detalle de {o.item}: {r.stderr.strip()[-200:]}")
        if o.json:
            return _comun.escribir_json({"texto": detalle["texto"]})
        print(detalle["texto"])
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
