"""`telar ir` — poner el foco en un hilo.

Además de cambiar el foco, lo anota: el registro de foco es lo que después
convierte `telar tiempo` en horas por proyecto. Anotar aquí no alcanza (el foco
también se mueve a mano, y eso lo anota `telar tiempo marcar` desde el
multiplexor), pero lo que pasa por telar no se pierde.
"""

from __future__ import annotations

from telar.ordenes import _comun

AYUDA = "Poner el foco en un hilo."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("ir", AYUDA)
    p.add_argument("hilo", help="id o nombre del hilo")
    p.add_argument("--crear", action="store_true", help="si no existe, abrirlo")
    p.add_argument("--remoto", default="", help="con --crear: abrirlo en esa máquina de [remotos]")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    from telar.servicios import ErrorDeServicio
    from telar.servicios import ir as servicio

    try:
        r = servicio.ir(ctx, o.hilo, crear=o.crear, remoto=o.remoto)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if r.aviso:
        print(_comun.tenue(f"  {r.aviso}"))
    if r.hecho == "foco":
        print(f"→ «{r.hilo}»")
    elif r.hecho == "nuevo-remoto":
        print(f"→ «{r.hilo}» (nuevo, en {r.destino} · sesión {r.sesion})")
    else:
        print(f"→ «{r.hilo}» (nuevo)" + (f" · {r.carpeta}" if r.carpeta else ""))
    return 0
