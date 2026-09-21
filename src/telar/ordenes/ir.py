"""`telar ir` — poner el foco en un hilo.

Además de cambiar el foco, lo anota: el registro de foco es lo que después
convierte `telar tiempo` en horas por proyecto. Anotar aquí no alcanza (el foco
también se mueve a mano, y eso lo anota `telar tiempo marcar` desde el
multiplexor), pero lo que pasa por telar no se pierde.
"""

from __future__ import annotations

from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Poner el foco en un hilo."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("ir", AYUDA)
    p.add_argument("hilo", help="id o nombre del hilo")
    p.add_argument("--crear", action="store_true", help="si no existe, abrirlo")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None:
        return _comun.queja(tel.aviso or "no hay multiplexor con el que hablar")

    hilo, problema = _comun.resolver(tel, o.hilo)
    if hilo is not None and tel.vivo(hilo):
        try:
            tel.mux.ir(hilo.id)
        except ErrorDeMux as e:
            return _comun.queja(str(e))
        tel.estado.marcar(hilo.nombre)
        print(f"→ «{hilo.nombre}»")
        return 0

    if not o.crear:
        pista = "" if hilo is None else " (está archivado o la sesión no lo muestra)"
        return _comun.queja(f"{problema or 'ese hilo no está vivo'}{pista}. `--crear` lo abre.")

    nombre = hilo.nombre if hilo is not None else o.hilo
    ruta = hilo.ruta if hilo is not None else None
    try:
        nuevo = tel.mux.crear(nombre, ruta=ruta)
    except ErrorDeMux as e:
        return _comun.queja(f"no pude abrirlo: {e}")
    tel.estado.desarchivar(nombre)
    tel.estado.marcar(nombre)
    print(f"→ «{nuevo.nombre}» (nuevo)")
    return 0
