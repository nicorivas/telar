"""`telar ir` — poner el foco en un hilo.

Además de cambiar el foco, lo anota: el registro de foco es lo que después
convierte `telar tiempo` en horas por proyecto. Anotar aquí no alcanza (el foco
también se mueve a mano, y eso lo anota `telar tiempo marcar` desde el
multiplexor), pero lo que pasa por telar no se pierde.
"""

from __future__ import annotations

from pathlib import Path

from telar.agente import ErrorDeAgente
from telar.agente import lanzar
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
    # sin carpeta, el tab nace donde esté parado el servidor del multiplexor, que suele ser
    # «/»: un hilo en la raíz del disco no sirve para nada. Y nace con su agente, como los
    # que abre `tejer`: un hilo es un lugar de trabajo, no una shell.
    ruta = hilo.ruta if hilo is not None and hilo.ruta is not None else None
    try:
        lanz = lanzar.para_hilo(ctx.config, nombre, ruta)
    except ErrorDeAgente as e:
        print(_comun.tenue(f"  sin agente: {e}"))
        lanz = None
    carpeta = lanz.carpeta if lanz is not None else (ruta or Path(ctx.config.raiz))
    try:
        nuevo = tel.mux.crear(nombre, ruta=carpeta, comando=lanz.comando if lanz else None)
    except ErrorDeMux as e:
        return _comun.queja(f"no pude abrirlo: {e}")
    tel.estado.desarchivar(nombre)
    tel.estado.marcar(nombre)
    lanzar.anotar(ctx.config, nombre, lanz, tel.mux)
    print(f"→ «{nuevo.nombre}» (nuevo)" + (f" · {carpeta}" if carpeta else ""))
    return 0
