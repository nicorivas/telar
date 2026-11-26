"""Lo pesado que solo lee, en un proceso aparte del servicio: la lista de proyectos y los pendientes de todo el
repositorio (`GET /proyectos`, `GET /pendientes?repo=true`).

`telar serve` atiende cada pedido en un hilo del mismo proceso, y Python corre uno a la vez (el GIL): mientras la lista
de proyectos leía cientos de documentos, la de hilos y la configuración, que la página necesita para dibujarse,
esperaban su turno (26-nov-2026: `/api/hilos` de 3 a 29 s, `/api/config` hasta 35 s, con la CLI en 0,9 y 0,3). Esos
dos cálculos, los que más CPU piden y no dependen de nada del servicio, van a un proceso propio (uno solo, que se
levanta la primera vez que se pide y queda): ahí su CPU no le quita turno a nadie. Lo que el proceso guarda (el YAML de
cada frontmatter, por su texto: telar.mapas) es suyo y nunca sirve lo de antes.

Fuera del servicio (la CLI, las pruebas) ACTIVO es falso y se calcula en el proceso de quien pide, con su contexto. Si el
proceso aparte se cae, se calcula aquí, y el siguiente pedido levanta otro.

    from telar import aparte
    r = await aparte.correr("proyectos", ctx)
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import multiprocessing
import os
import threading
import time

from telar.cli import Contexto
from telar.config import cargar as cargar_config
from telar.config import ruta_config

log = logging.getLogger("telar.aparte")

#: si lo pesado va al proceso aparte: lo enciende `telar serve`
ACTIVO = False


class ContextoDelServicio:
    """La configuración de esta máquina, leída una vez y de nuevo cuando el archivo (o `modulos.toml`) cambia."""

    def __init__(self) -> None:
        self._config = None
        self._marca: list | None = None

    def __call__(self) -> Contexto:
        ruta = ruta_config()
        # la configuración y los módulos instalados (`modulos.toml`, al lado): instalar, activar o quitar uno desde la
        # página cambia el segundo, y la configuración se relee igual
        marca = []
        # y los de la raíz (`<raiz>/.telar/temas.toml`, telar.temas; `mundos.toml`, telar.mundos_raiz): los que llegan de
        # otra máquina con un pull
        de_la_raiz = [getattr(self._config, a, None) for a in ("temas_archivo", "mundos_archivo")] if self._config is not None else []
        for archivo in (ruta, ruta.parent / "modulos.toml", *(x for x in de_la_raiz if x)):
            try:
                marca.append(archivo.stat().st_mtime)
            except OSError:
                marca.append(None)
        if self._config is None or marca != self._marca:
            self._config, self._marca = cargar_config(), marca
        return Contexto(config=self._config)


def _servicio(nombre: str):
    from telar.servicios import pendientes, proyectos

    return {"proyectos": proyectos.lista, "pendientes": pendientes.pendientes}[nombre]


# ── en el proceso aparte ──

_contexto_aparte: ContextoDelServicio | None = None


def _en_el_aparte(nombre: str, opciones: dict) -> dict:
    """Lo que corre en el proceso aparte: el servicio con el contexto de allá (la misma configuración, leída allá), y
    su respuesta como datos (se la vuelve a validar al llegar)."""
    global _contexto_aparte
    _contexto_aparte = _contexto_aparte or ContextoDelServicio()
    return _servicio(nombre)(_contexto_aparte(), **opciones).model_dump(mode="json")


def _seguir_al_servicio(servicio: int, cada: float = 1.0) -> None:
    """En el proceso aparte, al arrancar: que salga cuando el servicio ya no está. Un servicio que se apaga por una
    señal no alcanza a terminarlo (uvicorn la vuelve a lanzar al terminar, y el proceso muere ahí), y uno que muere de
    golpe tampoco: el proceso aparte quedaba huérfano, con su `resource_tracker`."""
    def mirar() -> None:
        while os.getppid() == servicio:
            time.sleep(cada)
        os._exit(0)

    threading.Thread(target=mirar, name="telar-aparte-servicio", daemon=True).start()


# ── en el servicio ──

_pool: concurrent.futures.ProcessPoolExecutor | None = None
_candado = threading.Lock()


def _el_pool() -> concurrent.futures.ProcessPoolExecutor:
    global _pool
    with _candado:
        if _pool is None:
            # «spawn»: un proceso nuevo, no una copia de este (con sus hilos y el bucle de asyncio a medias)
            _pool = concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"),
                                                           initializer=_seguir_al_servicio, initargs=(os.getpid(),))
        return _pool


def _botar(pool) -> None:
    global _pool
    with _candado:
        if _pool is pool:
            _pool = None
    pool.shutdown(wait=False, cancel_futures=True)


def apagar() -> None:
    """Al apagar el servicio: el proceso aparte, también, aunque esté a medio cálculo. Sin terminarlo, Python, al salir,
    espera a que termine lo que está calculando (concurrent.futures junta sus hilos al salir), y si no termina nunca, el
    servicio no sale."""
    global _pool
    with _candado:
        pool, _pool = _pool, None
    if pool is not None:
        procesos = list((getattr(pool, "_processes", None) or {}).values())
        pool.shutdown(wait=False, cancel_futures=True)
        for p in procesos:
            try:
                p.terminate()
            except Exception:  # noqa: BLE001 - uno que ya salió
                pass


async def correr(nombre: str, ctx, **opciones):
    """`nombre` ("proyectos": `proyectos.lista`; "pendientes": `pendientes.pendientes`) con esas opciones: en el proceso
    aparte si ACTIVO (con la configuración de esta máquina; `ctx` no viaja), y si no, aquí con `ctx`, en un hilo."""
    if not ACTIVO:
        return await asyncio.to_thread(_servicio(nombre), ctx, **opciones)
    pool = _el_pool()
    try:
        return await asyncio.wrap_future(pool.submit(_en_el_aparte, nombre, opciones))
    except concurrent.futures.process.BrokenProcessPool as e:
        log.warning("el proceso aparte se cayó (%s): %s se calcula aquí", e, nombre)
        _botar(pool)
        return await asyncio.to_thread(_servicio(nombre), ctx, **opciones)
