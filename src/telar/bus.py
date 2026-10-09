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
    registro.<persona>                 copia de cada mensaje (y de los retenidos), para ver quién le
                                       dijo qué a quién: no se consume, dura dos semanas.

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
#: la foto de los hilos de cada máquina (la de telar.espejo), clave <persona>.<maquina>
ESPEJO = "TELAR_ESPEJO"
#: copia de cada mensaje entre hilos, para verlos después (`registro.<persona>`, dos semanas)
REGISTRO = "TELAR_REGISTRO"
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


def mensaje(texto: str, *, de: str, para: str, tipo: str = "mensaje", mid: str = "", persona: str = "",
            saltos: int = 0) -> dict:
    """`persona`: de quién es el hilo que lo manda. `saltos`: cuántos mensajes entre hilos lleva la
    cadena sin que la persona hablara (0: lo empezó ella, o un periódico)."""
    from telar import casilla

    return {"id": mid or casilla.nuevo_id(), "de": de, "para": para, "tipo": tipo, "texto": texto,
            "persona": persona, "saltos": saltos,
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
        await js.stream_info(REGISTRO)
    except Exception:  # noqa: BLE001
        await js.add_stream(StreamConfig(name=REGISTRO, subjects=["registro.>"], max_age=14 * 24 * 3600, max_msgs=20_000))
    for bucket in (ESTADO, ESPEJO):
        try:
            await js.key_value(bucket)
        except Exception:  # noqa: BLE001
            await js.create_key_value(bucket=bucket, history=1)


def enviar(config, para: str, texto: str, *, de: str, tipo: str = "mensaje", quien: str = "", saltos: int = 0,
           mid: str = "", retener: str = "") -> dict:
    """Publica un mensaje para el hilo `para` (de esta persona, o de `quien`). Devuelve el mensaje.

    Con `retener` (el motivo) no va a la casilla: queda solo en el registro, retenido, hasta que la
    persona lo suelte (`telar mensaje --soltar`)."""
    if not hay_bus(config):
        raise ErrorDeBus("no hay bus: [bus] url en la configuración")
    m = mensaje(texto, de=de, para=para, tipo=tipo, mid=mid, persona=persona(config), saltos=saltos)

    async def _enviar():
        nc = await conectar(config)
        try:
            js = nc.jetstream()
            await asegurar(js)
            copia = {**m, "estado": "retenido", "motivo": retener} if retener else {**m, "estado": "enviado"}
            ack = None
            if not retener:
                ack = await js.publish(tema_casilla(config, para, quien), json.dumps(m, ensure_ascii=False).encode(),
                                       headers={"Nats-Msg-Id": m["id"]}, timeout=ESPERA)
            await js.publish(f"registro.{quien or persona(config)}", json.dumps(copia, ensure_ascii=False).encode(),
                             timeout=ESPERA)
            return ack
        finally:
            await nc.close()

    try:
        ack = asyncio.run(asyncio.wait_for(_enviar(), ESPERA + 5))
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorDeBus(f"el bus no recibió el mensaje: {e}") from e
    return {**m, "secuencia": getattr(ack, "seq", None), "duplicado": bool(getattr(ack, "duplicate", False)),
            **({"estado": "retenido", "motivo": retener} if retener else {})}


def registro(config, n: int = 100) -> list[dict]:
    """Los últimos `n` mensajes entre hilos de esta persona, del más viejo al más nuevo."""
    async def _leer():
        nc = await conectar(config)
        try:
            js = nc.jetstream()
            await asegurar(js)
            info = await js.stream_info(REGISTRO)
            ultimo, primero = info.state.last_seq, info.state.first_seq
            salida, seq = [], ultimo
            # hacia atrás, hasta juntar n de esta persona o llegar al principio
            while seq >= max(primero, 1) and len(salida) < n and ultimo - seq < n * 4:
                try:
                    r = await js.get_msg(REGISTRO, seq)
                except Exception:  # noqa: BLE001 - un hueco (borrado por edad)
                    seq -= 1
                    continue
                if r.subject == f"registro.{persona(config)}":
                    try:
                        salida.append(json.loads(r.data))
                    except ValueError:
                        pass
                seq -= 1
            return list(reversed(salida))
        finally:
            await nc.close()

    try:
        return asyncio.run(asyncio.wait_for(_leer(), ESPERA + 10))
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorDeBus(f"no pude leer el registro del bus: {e}") from e


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


def tema_cambio(config, tema: str = "*", quien: str = "") -> str:
    """Donde se avisa que algo cambió (`telar cambio`): todas las máquinas de la persona lo oyen."""
    return f"cambio.{quien or persona(config)}.{tema}"


def anunciar(config, tema: str) -> dict:
    """Avisa a todas las máquinas que `tema` cambió (sin respuesta: el que no está, no se entera)."""
    if not hay_bus(config):
        return {"ok": False, "error": "no hay bus: [bus] url en la configuración"}

    async def _anunciar():
        nc = await conectar(config)
        try:
            await nc.publish(tema_cambio(config, tema), json.dumps({"de": maquina(config)}).encode())
            await nc.flush(timeout=5)
        finally:
            await nc.close()

    try:
        asyncio.run(asyncio.wait_for(_anunciar(), 15))
        return {"ok": True}
    except Exception as e:  # noqa: BLE001 - sin bus a mano: el aviso no llega, y se dice
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}


def pedir(config, a_maquina: str, verbo: str, datos: dict, *, espera: float = 30) -> dict:
    """Un pedido con respuesta al nodo de otra máquina (`rpc.<persona>.<maquina>.<verbo>`). Siempre
    devuelve un dict con `ok`; si nadie responde a tiempo, `ok: False` con el motivo."""
    if not hay_bus(config):
        return {"ok": False, "error": "no hay bus: [bus] url en la configuración"}

    async def _pedir():
        nc = await conectar(config)
        try:
            r = await nc.request(tema_rpc(config, a_maquina, verbo), json.dumps(datos, ensure_ascii=False).encode(),
                                 timeout=espera)
            return json.loads(r.data)
        finally:
            await nc.close()

    try:
        return asyncio.run(asyncio.wait_for(_pedir(), espera + 5))
    except ErrorDeBus as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001 - sin respuesta a tiempo, o una que no es JSON
        nombre = type(e).__name__
        motivo = "no respondió a tiempo (¿está apagada o sin su nodo?)" if "Timeout" in nombre or "NoResponders" in nombre else f"{nombre}: {e}"
        return {"ok": False, "error": f"{a_maquina} {motivo}"[:300]}
