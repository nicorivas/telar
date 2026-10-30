"""`telar productos` — lo que se vende y sus ideas (telar.productos, docs/propuestas/productos.md).

    telar productos                                         los productos, con cuántas ideas tiene cada uno por estado
    telar productos --json                                  todo: los productos, sus campos y sus ideas
    telar productos crear <producto> "título" [--campo valor=alto] [--texto "…"]
    telar productos cambiar idea:<producto>/I03 --campo estado=priorizada [--version V] [--nota "…"]
    telar productos ver idea:<producto>/I03
    telar productos desde-tarea T84 <producto> [--campo valor=alto]    una tarea que es una idea: pasa al backlog
    telar productos tarea idea:<producto>/I03 ["título"] [--vence AAAA-MM-DD]   una tarea que nace de una idea

Un producto es una unidad del perfil del arquetipo que declara `.telar/productos.yaml`; una idea, un archivo con
frontmatter en su carpeta (`backlog/I03.md`). Cambiar una idea anota en su historia qué cambió; con `--version`,
solo si el archivo no cambió desde que se leyó.
"""

from __future__ import annotations

from telar.ordenes import _comun

AYUDA = "Lo que se vende y sus ideas: la lista, el backlog y el tablero; crear y mover una idea."


def _campos(pares: list[str]) -> dict[str, str]:
    salida = {}
    for par in pares:
        if "=" not in par:
            raise ValueError(f"--campo va como clave=valor, llegó {par!r}")
        k, v = par.split("=", 1)
        salida[k.strip()] = v.strip()
    return salida


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("productos", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", choices=("crear", "cambiar", "ver", "desde-tarea", "tarea"),
                   help="crear, cambiar o ver una idea; llevar una tarea al backlog; una tarea desde una idea")
    p.add_argument("objetivo", nargs="?", default="", help="el producto (crear), la idea (cambiar, ver, tarea) o la tarea (desde-tarea)")
    p.add_argument("titulo", nargs="?", default="", help="con crear o tarea: el título; con desde-tarea: el producto")
    p.add_argument("--vence", default="", help="con tarea: cuándo vence (AAAA-MM-DD)")
    p.add_argument("--campo", action="append", default=[], metavar="CLAVE=VALOR", help="un campo de la idea (se repite)")
    p.add_argument("--texto", default="", help="con crear: lo que se propone y por qué")
    p.add_argument("--version", default="", help="con cambiar: la versión que se leyó")
    p.add_argument("--nota", default="", help="con cambiar: una línea para su historia")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    from telar import productos

    try:
        campos = _campos(o.campo)
        if o.verbo == "crear":
            r = productos.crear(ctx, o.objetivo, o.titulo, campos, o.texto)
        elif o.verbo == "cambiar":
            r = productos.cambiar(ctx, o.objetivo, campos, version=o.version or None, nota=o.nota)
        elif o.verbo == "desde-tarea":
            r = productos.desde_tarea(ctx, o.objetivo, o.titulo, campos)
        elif o.verbo == "tarea":
            r = productos.nueva_tarea(ctx, o.objetivo, o.titulo, vence=o.vence)
        elif o.verbo == "ver":
            r = productos.ver(ctx, o.objetivo)
        else:
            r = productos.listar(ctx)
    except (productos.ErrorDeProductos, ValueError) as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    if o.verbo:
        print(f"{r['direccion']}  {r['titulo']}  " + _comun.tenue(f"{r['estado']} · {r['archivo']}"))
        if r.get("tarea"):
            print(_comun.tenue(f"  {'la tarea ' + r['tarea'] + ' quedó descartada' if o.verbo == 'desde-tarea' else 'nació la tarea ' + r['tarea']}"))
        return 0
    for f in r["fallas"]:
        print(_comun.tenue(f"· {f}"))
    if not r["declaraciones"]:
        print(_comun.tenue("ningún repositorio declara productos (.telar/productos.yaml)"))
        return 0
    for x in r["productos"]:
        cuenta: dict[str, int] = {}
        for i in x["ideas"]:
            cuenta[i["estado"]] = cuenta.get(i["estado"], 0) + 1
        resumen = " · ".join(f"{n} {e}" for e, n in cuenta.items()) or "sin ideas"
        print(f"{x['titulo']:<44} " + _comun.tenue(f"{resumen} · {x['ruta']}"))
    return 0
