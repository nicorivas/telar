"""`telar vincular` — asociar un hilo a una carpeta del repositorio.

Es el atajo de `telar hilo vincular`, y existe porque es lo primero que se hace
con un hilo y lo que más se repite:

    telar vincular proyectos/faro          este hilo
    telar vincular proyectos/faro --hilo 3 otro

Vincular no mueve ni escribe nada en el repositorio: telar anota, en su propio
estado, que ese hilo es esa carpeta.
"""

from __future__ import annotations

from telar.ordenes import _comun, hilo as orden_hilo

AYUDA = "Asociar un hilo a una carpeta del repositorio."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("vincular", AYUDA)
    p.add_argument("ruta", nargs="?", default=".", help="carpeta, relativa a la raíz")
    p.add_argument("--hilo", default="", help="cuál vincular (por defecto, este)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    resto = ["vincular", o.ruta] + (["--hilo", o.hilo] if o.hilo else [])
    return orden_hilo.main(resto, ctx)
