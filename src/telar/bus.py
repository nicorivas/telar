"""El bus entre máquinas: mensajes que esperan y estado que se avisa (docs/propuestas/bus.md).

Un servidor NATS con JetStream en la máquina que no se apaga; cada máquina habla con él por una
conexión saliente (`telar nodo`). Tres cosas viajan por ahí:

    casilla.<persona>.<hilo>           los mensajes para un hilo. Esperan hasta que lo recoja la
                                       máquina donde vive ahora (cola durable, uno por hilo); quien
                                       lo recoge lo deja en su casilla local (telar.casilla) y lo
                                       confirma. El mismo id dos veces no se guarda dos veces.
    estado (clave <persona>.<hilo>)    dónde vive cada hilo y en qué anda: máquina, atención, desde
                                       cuándo, conversación. Cada máquina publica los suyos y se
                                       entera de los demás al instante, sin sondear.
    rpc.<persona>.<maquina>.<verbo>    pedidos con respuesta a una máquina (leer un hilo, ping).

El hilo va en los temas con su nombre como extensión (`telar.correo.extension`: «Gestión» →
`gestion`), porque un tema no admite espacios ni puntos. Las direcciones no dependen de la máquina:
mudar un hilo cambia su estado, no su casilla.

Sin `[bus] url` no hay bus y nada de esto corre: telar sigue trabajando con una sola máquina.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import socket
from datetime import datetime
from pathlib import Path

#: el stream de las casillas y el almacén del estado, en el servidor del bus
STREAM = "TELAR_CASILLAS"
ESTADO = "TELAR_HILOS"
#: lo que se espera al bus para una orden de una sola vez (enviar, ver): más es que no está
ESPERA = 8


class ErrorDeBus(Exception):
    """El bus no está configurado, no responde o rechazó algo. El mensaje es para la persona."""


def hay_bus(config) -> bool:
    return bool(getattr(getattr(config, "bus", None), "url", ""))


def persona(config) -> str:
    return config.bus.persona or getpass.getuser()


def maquina(config) -> str:
    if config.bus.maquina:
        return config.bus.maquina
    from telar import espejo

    return espejo.nombre_de_esta_maquina() or socket.gethostname().split(".")[0]


def ficha(hilo: str) -> str:
    """El hilo como parte de un tema o de una clave: «Gestión» → `gestion`."""
    from telar import casilla

    return casilla.nombre_de_carpeta(hilo)


def tema_casilla(config, hilo: str, quien: str = "") -> str:
    return f"casilla.{quien or persona(config)}.{ficha(hilo)}"


def clave_estado(config, hilo: str, quien: str = "") -> str:
    return f"{quien or persona(config)}.{ficha(hilo)}"


def tema_rpc(config, quien_maquina: str, verbo: str, quien: str = "") -> str:
    return f"rpc.{quien or persona(config)}.{quien_maquina}.{verbo}"


def mensaje(texto: str, *, de: str, para: str, tipo: str = "mensaje", mid: str = "") -> dict:
    from telar import casilla

    return {"id": mid or casilla.nuevo_id(), "de": de, "para": para, "tipo": tipo, "texto": texto,
            "creado": datetime.now().astimezone().isoformat(timespec="seconds")}


def _token(config) -> str:
    if not config.bus.token:
        return ""
    try:
        return Path(config.bus.token).expanduser().read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ErrorDeBus(f"no puedo leer el token del bus ({config.bus.token}): {e}") from e


async def conectar(config, *, para_siempre: bool = False):
    """Una conexión al bus. `para_siempre`: reconecta sin rendirse (el demonio); si no, falla rápido."""
    try:
        import nats
    except ImportError as e:
        raise ErrorDeBus("falta el cliente del bus: instala telar con el extra «bus» (nats-py)") from e
    opciones = {"name": f"telar-{maquina(config)}", "connect_timeout": 5}
    token = _token(config)
    if token:
        opciones["token"] = token
    if para_siempre:
        opciones.update(max_reconnect_attempts=-1, reconnect_time_wait=2, allow_reconnect=True)
    else:
        opciones.update(max_reconnect_attempts=0, allow_reconnect=False)
    try:
        return await nats.connect(config.bus.url, **opciones)
    except Exception as e:  # noqa: BLE001 - cualquier falla de conexión es «el bus no responde»
        raise ErrorDeBus(f"el bus ({config.bus.url}) no responde: {e}") from e


async def asegurar(js) -> None:
    """El stream de las casillas y el almacén del estado, si todavía no existen."""
    from nats.js.api import RetentionPolicy, StreamConfig

    try:
        await js.stream_info(STREAM)
    except Exception:  # noqa: BLE001 - no existe todavía
        # cola de trabajo: un mensaje confirmado se borra; los no recogidos esperan (hasta 30 días)
        await js.add_stream(StreamConfig(name=STREAM, subjects=["casilla.>"], retention=RetentionPolicy.WORK_QUEUE,
                                         max_age=30 * 24 * 3600, duplicate_window=3600))
    try:
        await js.key_value(ESTADO)
    except Exception:  # noqa: BLE001
        await js.create_key_value(bucket=ESTADO, history=1)


def enviar(config, para: str, texto: str, *, de: str, tipo: str = "mensaje", quien: str = "") -> dict:
    """Publica un mensaje para el hilo `para` (de esta persona, o de `quien`). Devuelve el mensaje."""
    if not hay_bus(config):
        raise ErrorDeBus("no hay bus: [bus] url en la configuración")
    m = mensaje(texto, de=de, para=para, tipo=tipo)

    async def _enviar():
        nc = await conectar(config)
        try:
            js = nc.jetstream()
            await asegurar(js)
            ack = await js.publish(tema_casilla(config, para, quien), json.dumps(m, ensure_ascii=False).encode(),
                                   headers={"Nats-Msg-Id": m["id"]}, timeout=ESPERA)
            return ack
        finally:
            await nc.close()

    try:
        ack = asyncio.run(asyncio.wait_for(_enviar(), ESPERA + 5))
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorDeBus(f"el bus no recibió el mensaje: {e}") from e
    return {**m, "secuencia": getattr(ack, "seq", None), "duplicado": bool(getattr(ack, "duplicate", False))}


def estados(config) -> dict:
    """El estado de todos los hilos de esta persona, como lo tiene el bus: {hilo: {...}}."""
    async def _leer():
        nc = await conectar(config)
        try:
            js = nc.jetstream()
            await asegurar(js)
            kv = await js.key_value(ESTADO)
            salida = {}
            try:
                claves = await kv.keys()
            except Exception:  # noqa: BLE001 - un almacén vacío no tiene claves
                claves = []
            for k in claves:
                if not k.startswith(persona(config) + "."):
                    continue
                e = await kv.get(k)
                try:
                    d = json.loads(e.value)
                    salida[d.get("nombre") or k] = d
                except (ValueError, AttributeError):
                    continue
            return salida
        finally:
            await nc.close()

    try:
        return asyncio.run(asyncio.wait_for(_leer(), ESPERA + 5))
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorDeBus(f"no pude leer el estado del bus: {e}") from e
