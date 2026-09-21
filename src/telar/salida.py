"""La salida de la terminal: que la codificación no tumbe una orden.

telar dibuja con símbolos —`·`, `✓`, `✗`, `☐`, `▣`, `●`, `○`— y habla en
castellano, con comillas «así» y con eñes. Nada de eso cabe en ASCII, y la salida
estándar no siempre es UTF-8: basta un `PYTHONIOENCODING` heredado de un wrapper,
una consola en cp1252 o un entorno que fije la codificación para que el primer
`print` termine en un `UnicodeEncodeError` con su traza. Es lo peor de los dos
mundos: una falla de terminal contada como un error de programador, y la orden
muerta antes de decir nada.

Aquí se resuelve en un solo lugar, antes de que ninguna orden imprima:

  * `preparar()` le pone a la salida un manejador de errores propio. No revienta,
    y tampoco se conforma con `?`: translitera lo que no cabe (`«`→ `"`, `✓`→ `+`,
    `á`→ `a`), así que en una consola pobre el texto se lee igual, solo que más
    feo. Degradar es el trabajo; callarse o morirse, no.
  * `alcanza()` dice si un texto pasa tal cual. Es lo que `--json` necesita saber
    para elegir entre escribir los caracteres o escaparlos: un contrato no se
    translitera, se escapa, que es reversible.

No se toca `stdin` ni se cambia la codificación de nadie: solo qué hacer con lo
que no entra.
"""

from __future__ import annotations

import codecs
import sys
import unicodedata

__all__ = ["MANEJADOR", "RESERVA", "alcanza", "empobrecer", "preparar"]

#: El nombre con que se registra el manejador de errores de codificación.
MANEJADOR = "telar"

#: Con qué se reemplaza lo que una salida pobre no sabe escribir. Solo va aquí lo
#: que no se arregla quitándole los acentos: comillas, rayas, flechas y los
#: símbolos con que telar dibuja.
RESERVA = {
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "—": "-",
    "–": "-",
    "…": "...",
    "·": "-",
    "•": "*",
    "→": "->",
    "←": "<-",
    "↩": "<-",
    "↺": "~",
    "≥": ">=",
    "≤": "<=",
    "≠": "!=",
    "✓": "+",
    "✗": "x",
    "●": "*",
    "○": "o",
    "☐": "-",
    "▣": ">",
    "▪": "*",
    "─": "-",
    "│": "|",
    "└": "+",
    "├": "+",
}


def empobrecer(texto: str) -> str:
    """El mismo texto en ASCII: sin acentos, con la reserva, y `?` para lo demás.

    Se usa carácter por carácter desde el manejador de errores, de modo que solo
    paga lo que no cupo. Lo que devuelve es ASCII puro a propósito: el manejador
    lo vuelve a codificar, y una reserva que tampoco quepa sería un ciclo.
    """
    return "".join(_ascii(c) for c in texto)


def _ascii(caracter: str) -> str:
    reserva = RESERVA.get(caracter)
    if reserva is not None:
        return reserva
    # NFKD separa la letra de su acento: «á» → «a» + tilde, y la tilde se cae.
    plano = unicodedata.normalize("NFKD", caracter)
    plano = "".join(c for c in plano if not unicodedata.combining(c) and c.isascii())
    return plano or "?"


def _reemplazar(error: UnicodeError):
    """El manejador: lo que no se pudo codificar, empobrecido y adelante."""
    if not isinstance(error, UnicodeEncodeError):  # pragma: no cover - no lo registramos para decodificar
        raise error
    return empobrecer(error.object[error.start : error.end]), error.end


codecs.register_error(MANEJADOR, _reemplazar)


def preparar(*flujos) -> None:
    """Que un carácter que la consola no sabe escribir no mate el proceso.

    Por defecto, la salida y el error estándar. No falla nunca: si el flujo no es
    de los que se pueden reconfigurar —una prueba que capturó la salida en
    memoria, alguien que reemplazó `sys.stdout`— se lo deja como está, que es lo
    que esa capa haya decidido.
    """
    for flujo in flujos or (sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is None:
            continue
        try:
            reconfigurar(errors=MANEJADOR)
        except (AttributeError, LookupError, OSError, ValueError):  # pragma: no cover
            continue


def alcanza(texto: str, flujo=None) -> bool:
    """¿Este texto sale tal cual por ese flujo, sin perder un carácter?

    Un flujo sin codificación —el que escribe en memoria— alcanza para todo: ahí
    no hay bytes todavía, y quien los escriba después verá lo suyo.
    """
    flujo = sys.stdout if flujo is None else flujo
    codificacion = getattr(flujo, "encoding", None)
    if not codificacion:
        return True
    try:
        texto.encode(codificacion, errors="strict")
    except (LookupError, UnicodeEncodeError):
        return False
    return True
