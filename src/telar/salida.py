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
import os
import stat
import sys
import unicodedata
from datetime import datetime

__all__ = ["MANEJADOR", "RESERVA", "alcanza", "empobrecer", "preparar", "visible"]

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


def visible(texto: str) -> str:
    """El texto con sus caracteres de control a la vista: un ESC, un retorno o un NUL salen como `\\x1b`.

    Para lo que escribe otro y se muestra donde se decide algo (lo que pide un módulo antes de instalarlo, lo
    que pide un agente): una secuencia de la terminal (`\\x1b[2K`, `\\x1b[1A`, `\\r`) podría borrar o tapar
    la línea de al lado. Se escapan en vez de quitarse, para que se vea que estaban."""
    return "".join(f"\\x{ord(c):02x}" if unicodedata.category(c) == "Cc" else c for c in texto)


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


# ── el registro de un servicio ───────────────────────────────────────────────
#
# Bajo launchd, `telar serve` escribe su salida y sus errores a un archivo (`StandardOutPath`,
# ~/Library/Logs/telar-serve.log) que nadie rota: crece mientras el servicio viva. systemd los manda a
# journald, que sí tiene tope, y ahí la salida no es un archivo y no hay nada que hacer.

#: desde qué tamaño se recorta el registro del servicio; se deja la última mitad
MAX_REGISTRO = 4 * 1024 * 1024


def _ruta_de(fd: int) -> str:
    """La ruta del archivo abierto en `fd`: F_GETPATH en macOS, /proc en Linux. "" si no se sabe."""
    import fcntl

    if hasattr(fcntl, "F_GETPATH"):
        try:
            return os.fsdecode(fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024)).split(b"\0", 1)[0])
        except OSError:
            return ""
    try:
        return os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return ""


def recortar_registro(fd: int | None = None, maximo: int = MAX_REGISTRO) -> bool:
    """Si la salida estándar es un archivo de registro que pasó de `maximo`, lo deja con su última mitad
    (desde un salto de línea), como telar.periodicos hace con los suyos. Devuelve si recortó.

    Solo si es un archivo abierto para agregar al final (O_APPEND, lo que hacen launchd y `>>`): ahí, después
    de vaciarlo, cada escritura sigue al final del archivo nuevo. Uno abierto sin O_APPEND (`>`) seguiría
    escribiendo en su posición vieja y dejaría un hueco: no se toca, ni una terminal, una tubería o journald.
    Lo que se escriba entre leer la cola y vaciarlo se pierde; son milisegundos de un registro. Nunca falla."""
    try:
        import fcntl

        if fd is None:
            for flujo in (sys.stdout, sys.stderr):
                try:
                    flujo.flush()
                except (AttributeError, OSError, ValueError):
                    pass
            fd = sys.stdout.fileno()
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size <= maximo:
            return False
        if not fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_APPEND:
            return False
        ruta = _ruta_de(fd)
        if not ruta:
            return False
        actual = os.stat(ruta)
        if (actual.st_dev, actual.st_ino) != (st.st_dev, st.st_ino):
            return False  # la ruta que dio no es la de este archivo: no se recorta uno ajeno
        with open(ruta, "rb") as f:
            f.seek(max(0, actual.st_size - maximo // 2))
            cola = f.read()
        cola = cola[cola.find(b"\n") + 1:]
        os.ftruncate(fd, 0)
        datos = f"── {datetime.now():%Y-%m-%d %H:%M:%S} · registro recortado: queda lo último ──\n".encode() + cola
        while datos:
            datos = datos[os.write(fd, datos):]
        return True
    except (ImportError, OSError, ValueError, AttributeError):
        return False
