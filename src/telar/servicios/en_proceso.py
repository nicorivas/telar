"""Correr una orden de la CLI dentro de este proceso, con su salida capturada: el puente para las que
todavía imprimen en vez de devolver un modelo (los verbos de `telar hilo`, `telar tejer`).

No hay lógica repetida: es la misma orden, sin abrir un proceso. Capturar la salida cambia `sys.stdout`
para todo el proceso, así que las corridas van de a una (un candado), y por eso las largas no pasan por
aquí (`telar hilo llevar` copia una conversación por ssh: minutos). Una orden que pasa a devolver un
modelo deja el puente y tiene su servicio, como las demás.
"""

from __future__ import annotations

import importlib
import io
import threading
from contextlib import redirect_stderr, redirect_stdout

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio

#: las órdenes que se pueden correr así, y nada más
ORDENES = ("hilo", "tejer", "remotos", "periodicos")

_candado = threading.Lock()


class Corrida(BaseModel):
    codigo: int
    salida: str = ""
    error: str = ""


def correr(ctx, orden: str, argv: list[str]) -> Corrida:
    if orden not in ORDENES:
        raise ErrorDeServicio(f"«{orden}» no se corre en el proceso", 422)
    mod = importlib.import_module(f"telar.ordenes.{orden}")
    out, err = io.StringIO(), io.StringIO()
    with _candado, redirect_stdout(out), redirect_stderr(err):
        try:
            codigo = mod.main(list(argv), ctx)
        except SystemExit as e:  # argparse sale así con un argumento que no calza
            codigo = e.code if isinstance(e.code, int) else 2
    return Corrida(codigo=int(codigo or 0), salida=out.getvalue(), error=err.getvalue())


def o_falla(c: Corrida, que: str) -> Corrida:
    """La corrida, o su queja como error del servicio (409) si salió con error."""
    if c.codigo != 0:
        linea = (c.error.strip().splitlines() or c.salida.strip().splitlines() or [f"«{que}» falló"])[-1]
        raise ErrorDeServicio(linea.removeprefix("telar: "), 409, {"salida": c.salida, "codigo": c.codigo})
    return c
