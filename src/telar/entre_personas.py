"""Entre personas, por el bus: el correo a un hilo de otra persona y el directorio de sus hilos.

Cada persona tiene su cuenta en el bus (telar.cuentas) y entre cuentas cruza solo esto:

    correo.<persona>       un servicio: otra persona le deja un mensaje a un hilo suyo. Lo atiende su
                           nodo, que lo guarda en su casilla (durable, como cualquier mensaje) y responde.
                           El servidor le dice de qué cuenta vino (`Nats-Request-Info`): nadie escribe
                           a nombre de otro.
    directorio.<persona>   sus hilos, que publica su nodo cada tanto: a quién se le puede escribir.

Este módulo es lo que no depende de la conexión: qué se publica, cómo se guarda lo de los demás y qué se
acepta de un correo que llega. El nodo (telar.ordenes.nodo) y `telar correo enviar` lo usan.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from telar import casilla

#: lo más largo que se acepta en un correo entre personas
MAX_TEXTO = 60_000
#: un directorio más viejo que esto ya no se muestra como al día (segundos)
VIEJO = 15 * 60


class CorreoInvalido(ValueError):
    """Un correo que llega y no se acepta. El mensaje vuelve a quien lo mandó."""


def directorio(foto: dict, persona: str) -> dict:
    """Lo que se publica de los hilos propios: nombre, la palabra para escribirle, si vive, su carpeta y una
    línea. Nada más: lo ve otra persona. Y solo de los que la persona hizo públicos (`telar hilo publicar`):
    por defecto, un hilo es privado y no sale."""
    hilos = [{"nombre": h.get("nombre", ""), "ext": casilla.extension(h.get("nombre", "")),
              "vivo": bool(h.get("vivo")), "carpeta": h.get("relativa") or "", "resumen": h.get("resumen") or ""}
             for h in foto.get("hilos", []) if h.get("nombre") and not h.get("remoto") and h.get("publico") is True]
    return {"persona": persona, "maquina": foto.get("maquina", ""), "hilos": hilos,
            "publicado": datetime.now().astimezone().isoformat(timespec="seconds")}


def _archivo(config) -> Path:
    return Path(config.estado) / "directorio-bus.json"


def guardar(config, persona: str, datos: dict) -> None:
    """Guarda el directorio que publicó otra persona, por persona y máquina."""
    ruta = _archivo(config)
    try:
        todos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        todos = {}
    maquina = str(datos.get("maquina") or "")
    hilos = [h for h in datos.get("hilos", []) if isinstance(h, dict) and isinstance(h.get("nombre"), str)]
    todos.setdefault(persona, {})[maquina] = {"hilos": hilos, "publicado": str(datos.get("publicado") or ""),
                                              "visto": datetime.now().astimezone().isoformat(timespec="seconds")}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(todos, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ruta)


def leer(config) -> dict:
    """{persona: {maquina: {hilos, publicado, visto}}} de las demás personas, como llegó por el bus."""
    try:
        return json.loads(_archivo(config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def correo(pedido: dict, de_cuenta: str) -> dict:
    """Lo que se acepta de un correo que llega: para qué hilo, qué dice, de quién. Levanta CorreoInvalido."""
    if not de_cuenta:
        raise CorreoInvalido("el bus no dijo de qué cuenta viene")
    para = casilla.extension(str(pedido.get("para") or ""))
    if not para:
        raise CorreoInvalido("¿para qué hilo?")
    texto = str(pedido.get("texto") or "").strip()
    if not texto:
        raise CorreoInvalido("el correo viene vacío")
    if len(texto) > MAX_TEXTO:
        raise CorreoInvalido(f"el correo pasa de {MAX_TEXTO} caracteres")
    de = str(pedido.get("de") or "").strip()[:80]
    asunto = str(pedido.get("asunto") or "").strip().replace("\n", " ")[:200]
    cuerpo = f"Asunto: {asunto}\n\n{texto}" if asunto else texto
    return {"para": para, "texto": cuerpo, "de": f"{de_cuenta}:{de}" if de else de_cuenta, "persona": de_cuenta}
