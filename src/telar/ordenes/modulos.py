"""`telar modulos` — los módulos instalados y lo que aporta cada uno.

    telar modulos           la lista: nombre, carpeta y lo que trae (pestaña, app, periódicos, resultado)
    telar modulos --json

Un módulo es una carpeta con un `modulo.toml` (ver telar.modulos y docs/configuracion.md,
`[modulos]`). Se instala nombrándolo en la configuración de cada máquina que lo usa: la que
muestra su pestaña y la que corre sus periódicos. En esta última, después de instalarlo o
cambiar su manifiesto, `telar periodicos aplicar` lo pone en el crontab.
"""

from __future__ import annotations

from telar.ordenes import _comun

AYUDA = "Los módulos instalados (una carpeta con modulo.toml) y lo que aporta cada uno."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("modulos", AYUDA)
    p.epilog = __doc__
    p.add_argument("--json", action="store_true", help="la lista, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    modulos = ctx.config.modulos
    if o.json:
        return _comun.escribir_json({"modulos": [
            {"nombre": m.nombre, "carpeta": str(m.carpeta), "descripcion": m.descripcion, "aporta": m.aporta}
            for m in modulos]})
    if not modulos:
        print(_comun.tenue("no hay módulos: se instalan en la configuración, [modulos.<nombre>] carpeta = \"…\""))
    for m in modulos:
        print(f"{m.nombre}  " + _comun.tenue(str(m.carpeta)))
        if m.descripcion:
            print(f"    {m.descripcion}")
        print(_comun.tenue("    aporta: " + (", ".join(m.aporta) or "nada")))
    return 0
