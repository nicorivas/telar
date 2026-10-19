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

from telar.ordenes import _comun
from telar.servicios import ErrorDeServicio
from telar.servicios import bloques as servicio

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
    if not o.clave:
        for b in ctx.config.bloques:
            print(f"{b.clave}  {b.nombre}  " + _comun.tenue(" ".join(b.comando)))
        if not ctx.config.bloques:
            print(_comun.tenue("no hay bloques: se declaran en la configuración, [bloques.<clave>]"))
        return 0
    try:
        if o.abrir:
            r = servicio.abrir(ctx, o.clave, o.abrir, o.nombre)
            if o.json:
                return _comun.escribir_json(r.model_dump(mode="json"))
            print(f"{r.hilo} · {r.mensaje}")
            return 0
        if o.item:
            d = servicio.item(ctx, o.clave, o.item)
            if o.json:
                return _comun.escribir_json(d.model_dump(mode="json"))
            print(d.texto)
            return 0
        pagina = servicio.pagina(ctx, o.clave)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(pagina.model_dump(mode="json", exclude_unset=True))
    for bl in pagina.bloques:
        for x in bl.get("items", []):
            print(f"{x.get('marca', '·'):2} {x.get('fecha', '')[11:16]}  {x.get('texto', '')}  {x.get('titulo', '')}")
    return 0
