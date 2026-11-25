"""Un dueño por hilo, con época (docs/propuestas/mudanza-de-hilos.md, B2: la etapa 3).

El registro de cada hilo en el bus (almacén `TELAR_HILOS`, clave `<persona>.<ficha>`) dice quién lo tiene:

    dueno     la máquina donde vive (en un registro de antes, su `maquina`)
    epoca     un número que sube con cada traspaso
    cede      mientras su dueño lo está pasando a otra máquina: a cuál (su agente ya se detuvo)
    mudanza   el traspaso en curso, para que cualquier página lo vea: {a, de, paso, pid, maquina, hora}
    tomado_de, hasta, seguido   si se siguió aquí con su dueña apagada (etapa 4, telar.seguir): de cuál, el largo de
              la copia con que se siguió y cuándo. Quedan hasta el traspaso siguiente: la que vuelve los lee para ceder

Se escribe **condicionado a la revisión que se leyó** (`kv.update(..., last=…)`): si alguien escribió entre medio,
se vuelve a leer y se decide de nuevo. Así nunca hay dos dueños, aunque una máquina vuelva de dormir sin saber nada:

- El nodo publica sus hilos solo si el registro es suyo (`puede_publicar`), y lleva adelante lo del traspaso
  (`cede`, `mudanza`), que escribe quien lo conduce. Si es de otra máquina, no lo publica.
- El traspaso (telar.mudanza): el dueño lo **cede** (`ceder`: `cede = B`, y detiene a su agente), la conversación
  viaja, y la que recibe lo **toma** (`tomar`: `dueno = B`, `epoca + 1`, solo si sigue cedido a ella con esa época).
  Si algo falla antes, el dueño **se echa atrás** (`abortar`: `epoca + 1`, sin `cede`) y despierta a su agente. Los dos
  escriben condicionado: si la que recibe ya lo tomó, echarse atrás no puede, y al revés. Lo que hace imposible tener
  dos vivos es esa escritura, no un plazo.
- Con la dueña apagada (etapa 4, telar.seguir), otra máquina que tiene una copia de la conversación lo **sigue**
  (`seguir`: `dueno = B`, `epoca + 1`, `tomado_de`, `hasta`), solo si sigue siendo de la apagada con la época que se
  leyó. La que vuelve ve el registro de otra con su conversación y cede sola.

    de(registro) -> str                  su dueño
    puede_publicar(actual, yo, info)     si el nodo de `yo` puede publicar este hilo, y con qué época
    Registro(kv, yo)                     lo que publica el nodo, condicionado
    ceder / abortar / tomar / abierto / leer   el traspaso, con `con_almacen` (la conexión del nodo, o una propia)

La escritura de antes (`kv.put`, sin condición) queda con `[bus] publicar = "simple"`, por si la nueva falla: igual no
publica un hilo de otro dueño.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime

#: lo del traspaso: lo escribe quien lo conduce, y el nodo lo lleva adelante al publicar
PROTOCOLO = ("cede", "mudanza")
#: lo que deja seguirlo con su dueña apagada (`seguir`): el nodo lo lleva adelante, y el traspaso siguiente lo borra
SEGUIDO = ("tomado_de", "hasta", "seguido")
#: cuántas veces se vuelve a leer y a escribir cuando otro escribió entre medio
INTENTOS = 12


class ErrorDeDueno(Exception):
    """El hilo no es de esta máquina, o el traspaso ya no vale. El mensaje es para la persona."""


def de(registro: dict | None) -> str:
    """El dueño de un registro: `dueno`, o en uno de antes, su `maquina`. "" si no se sabe."""
    if not isinstance(registro, dict):
        return ""
    return str(registro.get("dueno") or registro.get("maquina") or "")


def epoca(registro: dict | None) -> int:
    try:
        return int((registro or {}).get("epoca") or 0)
    except (TypeError, ValueError):
        return 0


def puede_publicar(actual: dict | None, yo: str, info: dict) -> tuple[bool, int]:
    """Si el nodo de `yo` puede publicar `info` sobre el registro `actual`, y con qué época. Sí, si es suyo (o no hay
    registro). Si es de otra máquina, solo si allá está muerto, sin traspaso en curso, y lo de aquí es otro hilo que se
    llama igual (otra conversación) abierto aquí: entonces lo toma con la época siguiente, como antes se pisaba. Un hilo
    que se fue de aquí y aquí se abrió otra vez con su conversación vieja no lo toma: vive allá."""
    if actual is None:
        return True, 0
    if de(actual) == yo:
        return True, epoca(actual)
    otro_hilo = not actual.get("conversacion") or actual.get("conversacion") != info.get("conversacion")
    if info.get("vivo") and not actual.get("vivo") and not actual.get("cede") and not actual.get("mudanza") and otro_hilo:
        return True, epoca(actual) + 1
    return False, epoca(actual)


def _cas(e: BaseException) -> bool:
    """Si lo que falló es que otro escribió entre medio (la revisión ya no es la que se leyó)."""
    return "WrongLastSequence" in type(e).__name__ or "wrong last sequence" in str(e).lower()


def _no_esta(e: BaseException) -> bool:
    return type(e).__name__ in ("KeyNotFoundError", "KeyDeletedError", "NotFoundError")


async def leer(kv, clave: str) -> tuple[int, dict | None]:
    """(revisión, registro) de una clave; (0, None) si no está."""
    try:
        e = await kv.get(clave)
    except Exception as x:  # noqa: BLE001
        if _no_esta(x):
            return 0, None
        raise
    try:
        d = json.loads(e.value or b"null")
    except ValueError:
        d = None
    return int(e.revision or 0), d if isinstance(d, dict) else None


def _ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


async def _escribir(kv, clave: str, rev: int, actual: dict | None, valor: dict) -> int:
    datos = json.dumps({**valor, "actualizado": _ahora()}, ensure_ascii=False).encode()
    if actual is None:
        return await kv.create(clave, datos)
    return await kv.update(clave, datos, last=rev)


async def _cambiar(kv, clave: str, cambio) -> object:
    """Lee, decide (`cambio(actual) -> (valor nuevo o None, resultado)`) y escribe condicionado; si otro escribió entre
    medio, de nuevo. Devuelve el resultado de la última decisión."""
    for _ in range(INTENTOS):
        rev, actual = await leer(kv, clave)
        valor, resultado = cambio(actual)
        if valor is None:
            return resultado
        try:
            await _escribir(kv, clave, rev, actual, valor)
            return resultado
        except Exception as e:  # noqa: BLE001
            if not _cas(e):
                raise
    raise ErrorDeDueno(f"el registro de {clave} cambia sin parar: no lo pude escribir")


def _sin(d: dict, *campos: str) -> dict:
    return {k: v for k, v in d.items() if k not in campos and k != "actualizado"}


async def ceder(kv, clave: str, *, hilo: str, yo: str, a: str, pid: int | None = None) -> int:
    """El dueño empieza a pasarlo a `a`: `cede = a`, y el traspaso a la vista. Devuelve la época con que se cede.
    ErrorDeDueno si el hilo no es de esta máquina, o ya se está yendo a otra."""
    def cambio(actual):
        if actual is not None and de(actual) != yo:
            raise ErrorDeDueno(f"«{hilo}» vive en {de(actual)} según el bus, no aquí")
        if actual and actual.get("cede") and actual["cede"] != a:
            raise ErrorDeDueno(f"«{hilo}» ya se está yendo a {actual['cede']}")
        base = _sin(actual or {"nombre": hilo, "maquina": yo, "vivo": False})
        e = epoca(actual)
        return {**base, "dueno": yo, "epoca": e, "cede": a,
                "mudanza": {"a": a, "de": yo, "paso": "ceder", "pid": pid or os.getpid(), "maquina": yo,
                            "hora": time.time()}}, e

    return await _cambiar(kv, clave, cambio)


async def paso(kv, clave: str, *, yo: str, paso_: str) -> None:
    """En qué va el traspaso que conduce `yo` (lo ve cualquier página). Si ya no es suyo, nada."""
    def cambio(actual):
        if actual is None or de(actual) != yo or not isinstance(actual.get("mudanza"), dict):
            return None, None
        return {**_sin(actual), "mudanza": {**actual["mudanza"], "paso": paso_, "hora": time.time()}}, None

    await _cambiar(kv, clave, cambio)


async def abortar(kv, clave: str, *, yo: str, epoca_: int) -> bool:
    """El dueño se echa atrás: la época sube y el hilo deja de estar cedido, así que la que recibía ya no puede
    tomarlo. True si sigue siendo suyo (despierta a su agente); False si la otra ya lo tomó (vive allá)."""
    def cambio(actual):
        if actual is None:
            return None, True
        if de(actual) != yo:
            return None, False
        if epoca(actual) != epoca_ or not actual.get("cede"):
            return None, True  # ya se echó atrás (otro intento, el nodo)
        return {**_sin(actual, *PROTOCOLO), "epoca": epoca_ + 1}, True

    return bool(await _cambiar(kv, clave, cambio))


async def tomar(kv, clave: str, *, yo: str, de_: str, epoca_: int, valor: dict) -> bool:
    """La que recibe lo toma: `dueno = yo`, la época siguiente, y el traspaso en «abrir» hasta que lo abra. Solo si
    sigue cedido a ella por `de_` con esa época: si allá se echaron atrás, False y no se abre."""
    def cambio(actual):
        if actual is None or de(actual) != de_ or epoca(actual) != epoca_ or actual.get("cede") != yo:
            return None, False
        nuevo = {**_sin(actual, *PROTOCOLO, *SEGUIDO), **valor, "dueno": yo, "maquina": yo, "epoca": epoca_ + 1,
                 "mudanza": {"de": de_, "a": yo, "paso": "abrir", "maquina": yo, "pid": os.getpid(), "hora": time.time()}}
        return nuevo, True

    return bool(await _cambiar(kv, clave, cambio))


async def seguir(kv, clave: str, *, yo: str, de_: str, epoca_: int, hasta: int, valor: dict | None = None) -> bool:
    """Seguir aquí un hilo cuya dueña `de_` está apagada (etapa 4, telar.seguir), desde la copia de aquí, que llega hasta
    `hasta` bytes: `dueno = yo`, la época siguiente, `tomado_de`, `hasta`, y el traspaso en «abrir» hasta que lo abra.
    Solo si sigue siendo de `de_` con esa época y sin un traspaso en curso: si allá volvió y escribió, u otra lo tomó
    antes, False y no se abre."""
    def cambio(actual):
        if actual is None or de(actual) != de_ or epoca(actual) != epoca_ or actual.get("cede") or actual.get("mudanza"):
            return None, False
        ahora = time.time()
        nuevo = {**_sin(actual, *PROTOCOLO, *SEGUIDO), **(valor or {}), "dueno": yo, "maquina": yo, "epoca": epoca_ + 1,
                 "vivo": False, "tomado_de": de_, "hasta": int(hasta), "seguido": ahora,
                 "mudanza": {"de": de_, "a": yo, "paso": "abrir", "maquina": yo, "pid": os.getpid(), "hora": ahora}}
        return nuevo, True

    return bool(await _cambiar(kv, clave, cambio))


async def abierto(kv, clave: str, *, yo: str) -> None:
    """La que lo tomó ya lo abrió: el traspaso terminó."""
    def cambio(actual):
        if actual is None or de(actual) != yo or "mudanza" not in actual:
            return None, None
        return _sin(actual, *PROTOCOLO), None

    await _cambiar(kv, clave, cambio)


def con_almacen(config, hacer):
    """`hacer(kv)` (una corrutina) con el almacén del estado: por la conexión del nodo de este proceso si la hay (la
    llegada corre dentro del nodo), o por una propia que se cierra al terminar."""
    from telar import bus as mod_bus

    async def con(nc):
        kv = await nc.jetstream(timeout=10).key_value(mod_bus.ESTADO)
        return await hacer(kv)

    async def propia():
        nc = await mod_bus.conectar(config)
        try:
            return await con(nc)
        finally:
            try:
                await nc.close()
            except Exception:  # noqa: BLE001
                pass

    viva = mod_bus._conexion_viva()
    if viva is not None:
        nc, bucle = viva
        return asyncio.run_coroutine_threadsafe(con(nc), bucle).result(60)
    return asyncio.run(propia())


def clave(config, hilo: str) -> str:
    from telar import bus as mod_bus

    return mod_bus.clave_estado(config, hilo)


def registro(config, hilo: str) -> dict:
    """El registro de un hilo en el bus, como está ahora; {} si no está o no hay bus."""
    from telar import bus as mod_bus

    if not mod_bus.hay_bus(config):
        return {}
    try:
        return con_almacen(config, lambda kv: leer(kv, clave(config, hilo)))[1] or {}
    except Exception:  # noqa: BLE001 - sin bus, no se sabe
        return {}


class Registro:
    """Lo que publica el nodo de sus hilos, condicionado a la revisión que vio (`[bus] publicar = "simple"`: sin
    condición, como antes). Recuerda la última revisión de cada clave que escribió; si otro escribió entre medio, lee de
    nuevo y decide otra vez (`puede_publicar`)."""

    def __init__(self, kv, yo: str, *, simple: bool = False, anotar=None):
        self.kv, self.yo, self.simple = kv, yo, simple
        self.anotar = anotar or (lambda texto: None)
        #: clave → (revisión, lo que hay) de lo que escribió o leyó este nodo
        self.vistas: dict[str, tuple[int, dict | None]] = {}
        #: las claves que se dijo que son de otra máquina, con su dueño (se dice una vez)
        self.ajenas: dict[str, str] = {}

    async def publicar(self, clave: str, info: dict) -> bool:
        """Publica `info` (lo que el nodo sabe del hilo) si el registro es de esta máquina, con su época y lo del
        traspaso en curso. False si es de otra: no lo publica."""
        for _ in range(INTENTOS):
            if clave not in self.vistas:
                self.vistas[clave] = await leer(self.kv, clave)
            rev, actual = self.vistas[clave]
            puede, e = puede_publicar(actual, self.yo, info)
            if not puede:
                self.vistas.pop(clave, None)
                if self.ajenas.get(clave) != de(actual):
                    self.ajenas[clave] = de(actual)
                    self.anotar(f"«{info.get('nombre')}»: el bus dice que vive en {de(actual)} (época {e}): aquí no lo "
                                "publico")
                return False
            self.ajenas.pop(clave, None)
            if actual is not None and de(actual) != self.yo:
                self.anotar(f"«{info.get('nombre')}»: allá en {de(actual)} estaba cerrado y aquí se abrió otro con su "
                            f"nombre: ahora es de aquí (época {e})")
            arrastre = {k: actual[k] for k in (*PROTOCOLO, *SEGUIDO) if actual and de(actual) == self.yo and k in actual}
            valor = {**_sin(info, "dueno", "epoca", *PROTOCOLO, *SEGUIDO), "dueno": self.yo, "epoca": e, **arrastre}
            try:
                if self.simple:
                    rev_nueva = await self.kv.put(clave, json.dumps({**valor, "actualizado": _ahora()},
                                                                    ensure_ascii=False).encode())
                else:
                    rev_nueva = await _escribir(self.kv, clave, rev, actual, valor)
            except Exception as x:  # noqa: BLE001
                if _cas(x):
                    self.vistas.pop(clave, None)
                    continue
                raise
            self.vistas[clave] = (int(rev_nueva or 0), valor)
            return True
        return False

    def olvidar(self, clave: str) -> None:
        """Lo que vio de esa clave ya no vale (el vigía trajo otra cosa): la próxima vez, se lee."""
        self.vistas.pop(clave, None)
