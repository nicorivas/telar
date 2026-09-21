"""`telar tejer` — levantar la sesión, o reengancharla si ya está viva.

Es la única orden que crea algo sin que se lo pidan dos veces. Si la sesión ya
existe, no toca nada: reengancharse a lo que hay es más seguro que rehacerlo, y un
telar que se rearma solo pierde hilos.
"""

from __future__ import annotations

from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Levantar la sesión, o reengancharla si ya está viva."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("tejer", AYUDA)
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None:
        return _comun.queja(tel.aviso or "no hay multiplexor con el que hablar")

    ya_estaba = tel.viva
    if not ya_estaba:
        try:
            tel.mux.tejer()
        except ErrorDeMux as e:
            return _comun.queja(f"no pude levantar la sesión: {e}")

    try:
        hilos = tel.mux.hilos()
    except ErrorDeMux:
        hilos = []

    if o.json:
        return _comun.escribir_json(
            {
                "sesion": ctx.config.sesion,
                "multiplexor": ctx.config.multiplexor,
                "ya_estaba": ya_estaba,
                "hilos": len(hilos),
            }
        )

    if ya_estaba:
        print(f"la sesión «{ctx.config.sesion}» ya estaba viva, con {len(hilos)} hilos")
    else:
        print(f"tejida la sesión «{ctx.config.sesion}» ({ctx.config.multiplexor})")
    return 0
