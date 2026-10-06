"""`telar mensaje` — un mensaje para un hilo o un agente, en la máquina que sea, por el bus.

    telar mensaje Gestión "¿quedó la nota en T185?"
    telar mensaje gestion -              el texto por la entrada estándar (sin tope de largo práctico)
    telar mensaje Faro "…" --tipo encargo

El mensaje espera en la casilla del hilo hasta que la máquina donde vive lo recoja (`telar nodo`) y
entra a la conversación por sus ganchos, entero, sin teclearlo. Un agente se nombra por su carpeta o
su nombre; cualquier otro nombre es un hilo, viva donde viva. Necesita `[bus] url`.
"""

from __future__ import annotations

import os
import sys

from telar import bus as mod_bus
from telar.ordenes import _comun

AYUDA = "Un mensaje para un hilo o un agente, en la máquina que sea, por el bus."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("mensaje", AYUDA)
    p.epilog = __doc__
    p.add_argument("para", help="el hilo (su nombre) o el agente (su carpeta o su nombre)")
    p.add_argument("texto", nargs="*", help="el mensaje (o «-» para leerlo de la entrada)")
    p.add_argument("--tipo", choices=("mensaje", "encargo"), default="mensaje")
    p.add_argument("--de", default="", help="quién lo manda (por defecto, este hilo o esta máquina)")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    texto = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
    if not texto.strip():
        return _comun.queja("¿qué le digo? telar mensaje <hilo> \"texto\" (o «-» para la entrada)")
    try:
        r = enviar(ctx, o.para, texto, tipo=o.tipo, de=o.de)
    except mod_bus.ErrorDeBus as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    print(f"«{r['para']}»: en su casilla" + (" (ya estaba: no se duplicó)" if r.get("duplicado") else "") + f" · id {r['id']}")
    return 0


def remitente(ctx, de: str = "") -> str:
    return de or os.environ.get("TELAR_HILO", "").strip() or f"{mod_bus.persona(ctx.config)}@{mod_bus.maquina(ctx.config)}"


def enviar(ctx, para: str, texto: str, *, tipo: str = "mensaje", de: str = "") -> dict:
    """Publica para `para` (un agente por su carpeta o nombre, o un hilo por su nombre)."""
    from telar import agentes as mod_agentes

    agente = next((a for a in mod_agentes.descubrir(ctx.config) if para in (a.clave, a.nombre)), None)
    nombre = agente.nombre if agente is not None else para
    return mod_bus.enviar(ctx.config, nombre, texto.strip(), de=remitente(ctx, de), tipo=tipo)
