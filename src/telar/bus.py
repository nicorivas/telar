"""El bus entre máquinas: mensajes que esperan y estado que se avisa (docs/arquitectura.md, «Entre máquinas: el bus»).

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

El hilo va en los temas con su nombre como extensión (`telar.casilla.extension`: «Gestión» →
`gestion`), porque un tema no admite espacios ni puntos. Las direcciones no dependen de la máquina:
mudar un hilo cambia su estado, no su casilla.

Sin `[bus] url` no hay bus y nada de esto corre: telar sigue trabajando con una sola máquina.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import socket
import time
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
            saltos: int = 0, modo: str = "pedido", extra: dict | None = None) -> dict:
    """`persona`: de quién es el hilo que lo manda. `saltos`: cuántos mensajes entre hilos lleva la
    cadena sin que la persona hablara (0: lo empezó ella, o un periódico). `modo` (telar.casilla): va en el
    mensaje solo si no es `pedido`, así un pedido queda como siempre; `extra`, lo que lleva un modo (el id del
    encargo, su plazo, a quién responder)."""
    from telar import casilla

    m = {"id": mid or casilla.nuevo_id(), "de": de, "para": para, "tipo": tipo, "texto": texto,
         "persona": persona, "saltos": saltos,
         "creado": datetime.now().astimezone().isoformat(timespec="seconds")}
    if modo and modo != "pedido":
        m["modo"] = modo
    m.update({k: v for k, v in (extra or {}).items() if k not in m and v not in ("", None)})
    return m


def _token(config) -> str:
    if not config.bus.token:
        return ""
    try:
        return Path(config.bus.token).expanduser().read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ErrorDeBus(f"no puedo leer el token del bus ({config.bus.token}): {e}") from e


async def _callar(_e) -> None:
    """Sin esto, nats-py imprime la traza de cada falla de conexión; la falla la cuenta ErrorDeBus."""


#: cada cuánto se repite en el registro del nodo una misma falla del bus (segundos): en el medio, se cuenta
AVISO_CADA = 600


class Avisador:
    """Las fallas del bus que cuenta nats-py en una conexión que no se rinde (la del nodo), una línea cada
    una. Sin esto, nats-py imprime la traza entera de cada una (unas cuarenta líneas), y con el laptop
    dormido o sin red son cientos por hora: el registro de `telar serve` llegó a 100 mil líneas, casi todas
    `nats: timeout` al reintentar el vigía del estado y conexiones rechazadas. La misma falla (su tipo y su
    texto) se escribe una vez cada `AVISO_CADA` segundos; las de en medio se cuentan y salen con la
    siguiente. Una «slow consumer» se agrupa por su tema, no por el número de la suscripción."""

    MAX_DISTINTAS = 200

    def __init__(self, escribir=None, *, cada: float = AVISO_CADA, reloj=time.monotonic, prefijo: str = "bus"):
        self.escribir = escribir or (lambda t: print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {t}", flush=True))
        self.cada, self.reloj, self.prefijo = cada, reloj, prefijo
        #: (tipo, texto) → [cuándo se escribió, cuántas se callaron desde entonces]
        self.vistas: dict[tuple[str, str], list] = {}
        #: la conexión que avisa (la pone `conectar`): un cierre ordenado también llama a `cortado`
        self.nc = None
        #: desde cuándo está cortada (None: conectada), y si ese corte se calló
        self.cortada_desde: float | None = None
        self.corte_callado = False

    @staticmethod
    def clave(e: BaseException) -> tuple[str, str]:
        nombre = type(e).__name__
        if "SlowConsumer" in nombre:
            return nombre, f"se descartaron mensajes de {getattr(e, 'subject', '') or '?'} (el nodo no alcanzó a atenderlos)"
        return nombre, (str(e) or nombre)[:160]

    def anotar(self, e: BaseException) -> bool:
        """Si la escribió (True) o la contó para después (False)."""
        clave = self.clave(e)
        return self._anotar(clave, f"{clave[0]}: {clave[1]}")

    def _anotar(self, clave: tuple[str, str], texto: str) -> bool:
        ahora = self.reloj()
        vista = self.vistas.get(clave)
        if vista is not None and ahora - vista[0] < self.cada:
            vista[1] += 1
            return False
        if len(self.vistas) >= self.MAX_DISTINTAS:
            self.vistas.clear()  # muchas distintas: se empieza de nuevo antes que crecer sin fin
        calladas = vista[1] if vista else 0
        self.vistas[clave] = [ahora, 0]
        extra = f" (y {calladas} igual{'es' if calladas > 1 else ''} desde la anterior)" if calladas else ""
        self.escribir(f"{self.prefijo}: {texto}{extra}")
        return True

    async def __call__(self, e) -> None:
        self.anotar(e)

    #: una vuelta que tarda menos que esto después de un corte callado también se calla (segundos)
    CORTE_BREVE = 60

    async def cortado(self) -> None:
        """nats-py llama a esto al perder la conexión, y también al cerrarla en orden (`nc.close()`, al
        apagar el nodo): esa no es un corte. Un hotspot que se cae y vuelve seguido daría dos líneas cada
        vez: el corte va con el mismo tope que una falla, y su vuelta se calla con él si fue breve."""
        if getattr(self.nc, "is_closed", False):
            return
        self.cortada_desde = self.reloj()
        self.corte_callado = not self._anotar(("corte", ""), "se cortó la conexión; reintentando")

    async def de_vuelta(self) -> None:
        desde, self.cortada_desde = self.cortada_desde, None
        duro = self.reloj() - desde if desde is not None else 0
        if self.corte_callado and duro < self.CORTE_BREVE:
            return  # el corte tampoco se escribió: va contado en el próximo
        self.corte_callado = False
        self.escribir(f"{self.prefijo}: conectado de nuevo" + (f" (tras {duro:.0f} s)" if duro >= 1 else ""))


#: la espera entre intentos de la primera conexión del demonio: crece del primero al último y se queda ahí
ESPERAS_PRIMERA = (2, 5, 10, 30, 60)


async def conectar(config, *, para_siempre: bool = False, dormir=None):
    """Una conexión al bus, con la cuenta de esta persona (telar.cuentas: su nombre y su secreto).
    `para_siempre`: no se rinde nunca (el demonio). Tampoco en la primera conexión: nats-py reconecta una
    conexión que ya tuvo, pero si la primera falla, se rinde; aquí se reintenta con esperas que crecen
    (`ESPERAS_PRIMERA`). Así un nodo que arranca con el bus caído, o con una cuenta que todavía no se aprueba
    (`telar instalar --unirse`), entra solo cuando puede. Sin `para_siempre`, falla rápido."""
    try:
        import nats
    except ImportError as e:
        raise ErrorDeBus("falta el cliente del bus: instala telar con el extra «bus» (nats-py)") from e
    opciones = {"name": f"telar-{maquina(config)}", "connect_timeout": 5}
    token = _token(config)
    if token:
        opciones.update(user=persona(config), password=token)
    if not para_siempre:
        opciones.update(max_reconnect_attempts=0, allow_reconnect=False, error_cb=_callar)
        try:
            return await nats.connect(config.bus.url, **opciones)
        except Exception as e:  # noqa: BLE001 - cualquier falla de conexión es «el bus no responde»
            raise ErrorDeBus(f"el bus ({config.bus.url}) no responde: {e}") from e
    # las fallas, en una línea cada una y sin repetirse (Avisador), no con su traza entera
    avisos = Avisador()
    opciones.update(max_reconnect_attempts=-1, reconnect_time_wait=2, allow_reconnect=True,
                    error_cb=avisos.__call__, disconnected_cb=avisos.cortado,
                    reconnected_cb=avisos.de_vuelta)  # nats-py exige funciones async: un objeto llamable no le sirve
    dormir = dormir or asyncio.sleep
    intento = 0
    while True:
        try:
            nc = await nats.connect(config.bus.url, **opciones)
        except Exception as e:  # noqa: BLE001 - se reintenta: el bus o la cuenta pueden llegar después
            espera = ESPERAS_PRIMERA[min(intento, len(ESPERAS_PRIMERA) - 1)]
            if "authorization" in str(e).lower():
                avisos._anotar(("primera", "clave"), f"el bus ({config.bus.url}) no acepta la cuenta "
                               f"«{persona(config)}» todavía (¿un pedido sin aprobar, o otra clave?): reintento "
                               f"cada {ESPERAS_PRIMERA[-1]} s")
            else:
                avisos._anotar(("primera", type(e).__name__), f"el bus ({config.bus.url}) no responde ({e}): "
                               f"reintento cada {ESPERAS_PRIMERA[-1]} s")
            intento += 1
            await dormir(espera)
            continue
        avisos.nc = nc  # para que un cierre ordenado no se anote como corte
        if intento:
            avisos.escribir(f"bus: conectado, al intento {intento + 1}")
        return nc


def _es_plazo(e: BaseException) -> bool:
    """Si es un plazo que se agotó con la conexión ya abierta (un pedido al bus que no volvió a tiempo).
    `nats.errors.TimeoutError` hereda del de asyncio; una falla al conectar es ErrorDeBus y no cuenta."""
    return not isinstance(e, ErrorDeBus) and (isinstance(e, asyncio.TimeoutError) or "Timeout" in type(e).__name__)


#: lo que tiene que quedar del plazo para intentar otra vez (segundos): conectar y un pedido por Tailscale
REINTENTO_MINIMO = 1.0


def _con_reintento(fabrica, plazo: float, intentos: int = 2):
    """`asyncio.run` de la corrutina que arma `fabrica`, con `plazo` segundos, y otra vez si se agotó un
    plazo con el bus ya conectado: un pedido que se perdió en la red (el laptop por Tailscale, un hotspot)
    suele salir a la segunda. Solo para lo que se puede repetir sin efecto doble: leer, o publicar con
    `Nats-Msg-Id` (el bus descarta el repetido). Si no conectó, no se insiste: el bus no está, y esperar
    otra vez solo demora el aviso.

    El reintento va dentro del mismo `plazo`, con lo que quedó: quien espera (`telar hilos`, la página)
    nunca espera más que sin él. Por eso solo se intenta otra vez si un pedido de adentro se agotó antes
    (el de nats-py, de cinco a ocho segundos) y queda al menos REINTENTO_MINIMO; si el que se cumplió es el
    plazo entero (conectando, o un pedido que no volvió nunca), no queda nada y sube tal cual."""
    async def correr():
        reloj = asyncio.get_running_loop().time
        fin = reloj() + plazo
        for intento in range(intentos):
            try:
                return await asyncio.wait_for(fabrica(), max(0.0, fin - reloj()))
            except Exception as e:  # noqa: BLE001 - lo que no es un plazo sube tal cual
                if intento + 1 < intentos and _es_plazo(e) and fin - reloj() >= REINTENTO_MINIMO:
                    continue
                raise

    return asyncio.run(correr())


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
           mid: str = "", retener: str = "", modo: str = "pedido", extra: dict | None = None) -> dict:
    """Publica un mensaje para el hilo `para` (de esta persona, o de `quien`). Devuelve el mensaje.

    Con `retener` (el motivo) no va a la casilla: queda solo en el registro, retenido, hasta que la
    persona lo suelte (`telar mensaje --soltar`). `modo` y `extra`, como en `mensaje`."""
    if not hay_bus(config):
        raise ErrorDeBus("no hay bus: [bus] url en la configuración")
    m = mensaje(texto, de=de, para=para, tipo=tipo, mid=mid, persona=persona(config), saltos=saltos, modo=modo,
                extra=extra)
    #: cuántas veces se alcanzó a pedir la publicación en la casilla (la del reintento incluida)
    publicaciones = []

    async def _enviar():
        nc = await conectar(config)
        try:
            js = nc.jetstream()
            await asegurar(js)
            copia = {**m, "estado": "retenido", "motivo": retener} if retener else {**m, "estado": "enviado"}
            ack = None
            if not retener:
                publicaciones.append(1)
                ack = await js.publish(tema_casilla(config, para, quien), json.dumps(m, ensure_ascii=False).encode(),
                                       headers={"Nats-Msg-Id": m["id"]}, timeout=ESPERA)
            # con id también la copia, para que un reintento no la deje dos veces; con su estado, porque soltar
            # un retenido publica otra copia del mismo mensaje («enviado»), que no es repetida
            await js.publish(f"registro.{quien or persona(config)}", json.dumps(copia, ensure_ascii=False).encode(),
                             headers={"Nats-Msg-Id": f"{m['id']}.{copia['estado']}"}, timeout=ESPERA)
            return ack
        finally:
            await nc.close()

    try:
        # un reintento si el bus no confirmó a tiempo: con el mismo id, si el primero sí llegó, el bus lo descarta
        ack = _con_reintento(_enviar, ESPERA + 5)
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorDeBus(f"el bus no recibió el mensaje: {e}") from e
    # repetido en el reintento, si el primero alcanzó a pedir la publicación, es que ese sí había llegado. Si
    # el primero se agotó antes (conectando a JetStream, asegurando el stream), el repetido es de antes: el
    # mismo id ya se había mandado. Lo que no se distingue: un id repetido de antes, con un primer intento
    # que también lo publicó; se cuenta como no repetido
    duplicado = bool(getattr(ack, "duplicate", False)) and len(publicaciones) == 1
    return {**m, "secuencia": getattr(ack, "seq", None), "duplicado": duplicado,
            **({"estado": "retenido", "motivo": retener} if retener else {})}


def escribir_a(config, persona_destino: str, hilo: str, texto: str, *, de: str, asunto: str = "") -> dict:
    """Un correo a un hilo de otra persona (telar.entre_personas): lo recibe su nodo, que lo guarda en su
    casilla y responde. Devuelve su respuesta (`{"ok": true, "id": …}`). Levanta ErrorDeBus si nadie lo
    atiende (esa persona no tiene nodo en el bus, o no hay cuenta suya) o si lo rechazó."""
    from telar import cuentas

    pedido = {"para": hilo, "texto": texto, "de": de, "asunto": asunto}

    async def _pedir():
        nc = await conectar(config)
        try:
            r = await nc.request(cuentas.CORREO.format(persona_destino), json.dumps(pedido, ensure_ascii=False).encode(),
                                 timeout=ESPERA)
            return json.loads(r.data or b"{}")
        finally:
            await nc.close()

    try:
        respuesta = asyncio.run(asyncio.wait_for(_pedir(), ESPERA + 5))
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001 - sin nadie que responda: nats-py levanta NoRespondersError o timeout
        raise ErrorDeBus(f"nadie atiende el correo de {persona_destino} en el bus ({type(e).__name__})") from e
    if not respuesta.get("ok"):
        raise ErrorDeBus(f"{persona_destino} no lo aceptó: {respuesta.get('error', 'sin motivo')}")
    return respuesta


def registro(config, n: int = 100) -> list[dict]:
    """Los últimos `n` mensajes entre hilos de esta persona, del más viejo al más nuevo."""
    async def _leer():
        nc = await conectar(config)
        try:
            js = nc.jetstream()
            await asegurar(js)
            info = await js.stream_info(REGISTRO)
            ultimo, primero = info.state.last_seq, info.state.first_seq
            if not ultimo:
                return []
            # las últimas n*4 secuencias, y de ellas los últimos n de esta persona. De una vez, con un
            # consumidor efímero que filtra por su tema: pedirlas de a una era un viaje por mensaje
            # (17 s por 60 desde el laptop; 200 no alcanzaban a llegar antes del plazo)
            desde = max(primero, 1, ultimo - n * 4 + 1)
            from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

            sub = await js.pull_subscribe(
                f"registro.{persona(config)}", stream=REGISTRO,
                config=ConsumerConfig(deliver_policy=DeliverPolicy.BY_START_SEQUENCE, opt_start_seq=desde,
                                      ack_policy=AckPolicy.NONE, inactive_threshold=30.0, mem_storage=True))
            salida: list[dict] = []
            try:
                while True:
                    try:
                        lote = await sub.fetch(batch=256, timeout=2)
                    except asyncio.TimeoutError:
                        break  # no queda nada en la ventana
                    for r in lote:
                        try:
                            salida.append(json.loads(r.data))
                        except ValueError:
                            pass
                    if not lote or lote[-1].metadata.num_pending == 0:
                        break
            finally:
                try:
                    await sub.unsubscribe()
                except Exception:  # noqa: BLE001 - el consumidor efímero se borra solo
                    pass
            return salida[-n:] if n else salida
        finally:
            await nc.close()

    try:
        return _con_reintento(_leer, ESPERA + 10)
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorDeBus(f"no pude leer el registro del bus: {e or type(e).__name__}") from e


def maquina_de(config, hilo: str) -> str:
    """En qué máquina vive un hilo, según el estado que publica su nodo; "" si el bus no lo sabe."""
    async def _leer():
        nc = await conectar(config)
        try:
            kv = await nc.jetstream().key_value(ESTADO)
            try:
                e = await kv.get(clave_estado(config, hilo))
            except Exception:  # noqa: BLE001 - no está, o fue borrado
                return ""
            return str(json.loads(e.value or b"{}").get("maquina") or "")
        finally:
            await nc.close()

    try:
        return _con_reintento(_leer, ESPERA)
    except Exception:  # noqa: BLE001 - sin bus, no se sabe
        return ""


def estados(config) -> dict:
    """El estado de todos los hilos de esta persona, como lo tiene el bus: {hilo: {...}}."""
    async def _leer():
        nc = await conectar(config)
        try:
            js = nc.jetstream()
            await asegurar(js)
            await js.key_value(ESTADO)
            # el último valor de cada clave de esta persona, de una vez: un consumidor efímero sobre el
            # stream del almacén, filtrado por su prefijo. Pedirlas de a una (`kv.get`) era un viaje por
            # hilo, y con cien hilos y la red de Tailscale se pasaba del plazo
            from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

            sub = await js.pull_subscribe(
                f"$KV.{ESTADO}.{persona(config)}.>", stream=f"KV_{ESTADO}",
                config=ConsumerConfig(deliver_policy=DeliverPolicy.LAST_PER_SUBJECT, ack_policy=AckPolicy.NONE,
                                      inactive_threshold=30.0, mem_storage=True))
            salida = {}
            try:
                while True:
                    try:
                        lote = await sub.fetch(batch=256, timeout=2)
                    except asyncio.TimeoutError:
                        break
                    for r in lote:
                        if (r.headers or {}).get("KV-Operation") in ("DEL", "PURGE"):
                            continue  # borrada: el hilo ya no está
                        k = r.subject.removeprefix(f"$KV.{ESTADO}.")
                        try:
                            d = json.loads(r.data)
                            salida[d.get("nombre") or k] = d
                        except (ValueError, AttributeError):
                            continue
                    if not lote or lote[-1].metadata.num_pending == 0:
                        break
            finally:
                try:
                    await sub.unsubscribe()
                except Exception:  # noqa: BLE001 - el consumidor efímero se borra solo
                    pass
            return salida
        finally:
            await nc.close()

    try:
        return _con_reintento(_leer, ESPERA + 5)
    except ErrorDeBus:
        raise
    except Exception as e:  # noqa: BLE001
        raise ErrorDeBus(f"no pude leer el estado del bus: {e or type(e).__name__}") from e


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


# ── la conexión del nodo, para los pedidos de este proceso ──
#
# En `telar serve --nodo`, el nodo y la API viven en el mismo proceso: el nodo tiene una conexión al bus
# abierta todo el tiempo, y los pedidos de la API (que corren en sus hilos de trabajo) la usan en vez de
# abrir y cerrar una por pedido. Fuera de ese proceso (una orden suelta), cada pedido abre la suya.

_viva: tuple | None = None  # (conexión, su bucle)


def registrar_conexion(nc, bucle) -> None:
    """La conexión abierta del nodo de este proceso (o None al cerrarla)."""
    global _viva
    _viva = (nc, bucle) if nc is not None else None


def _conexion_viva():
    """(conexión, bucle) si hay una abierta y se puede usar desde este hilo; si no, None."""
    import threading

    if _viva is None:
        return None
    nc, bucle = _viva
    if not getattr(nc, "is_connected", False) or bucle.is_closed() or not bucle.is_running():
        return None
    # desde el hilo del propio bucle no se puede esperar una corrutina suya: ahí, una conexión aparte
    if getattr(bucle, "_thread_id", None) == threading.get_ident():
        return None
    return nc, bucle


def pedir(config, a_maquina: str, verbo: str, datos: dict, *, espera: float = 30) -> dict:
    """Un pedido con respuesta al nodo de otra máquina (`rpc.<persona>.<maquina>.<verbo>`). Siempre
    devuelve un dict con `ok`; si nadie responde a tiempo, `ok: False` con el motivo."""
    if not hay_bus(config):
        return {"ok": False, "error": "no hay bus: [bus] url en la configuración"}
    tema, cuerpo = tema_rpc(config, a_maquina, verbo), json.dumps(datos, ensure_ascii=False).encode()

    async def _por(nc):
        r = await nc.request(tema, cuerpo, timeout=espera)
        return json.loads(r.data)

    async def _pedir():
        nc = await conectar(config)
        try:
            return await _por(nc)
        finally:
            await nc.close()

    try:
        viva = _conexion_viva()
        if viva is not None:
            nc, bucle = viva
            return asyncio.run_coroutine_threadsafe(asyncio.wait_for(_por(nc), espera + 5), bucle).result(espera + 10)
        return asyncio.run(asyncio.wait_for(_pedir(), espera + 5))
    except ErrorDeBus as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001 - sin respuesta a tiempo, o una que no es JSON
        nombre = type(e).__name__
        if "NoResponders" in nombre:
            # nadie escucha ese tema: o la máquina no tiene su nodo, o su telar no conoce ese pedido
            return {"ok": False, "sin_servicio": True,
                    "error": f"{a_maquina} no atiende «{verbo}» (¿sin su nodo, o con un telar más viejo?)"}
        motivo = "no respondió a tiempo (¿está apagada o sin su nodo?)" if "Timeout" in nombre else f"{nombre}: {e}"
        return {"ok": False, "error": f"{a_maquina} {motivo}"[:300]}
