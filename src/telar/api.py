"""La API de telar (`telar serve`): los mismos datos que la CLI, por HTTP, desde un proceso que no se va.

Cada ruta es una cáscara alrededor de una función de `telar.servicios`, igual que la orden de la CLI
que le corresponde: la lógica vive una vez. FastAPI valida los parámetros y documenta las respuestas
con sus modelos (`/docs`, `/openapi.json`).

Por qué un proceso que se queda: lo lento de telar no es abrir un proceso sino lo que se espera de la
red (el calendario). Aquí la configuración se lee una vez (y de nuevo cuando cambia), lo interpretado
queda en memoria, y una tarea de fondo mantiene fresca la copia del calendario: quien pide `/hoy`
recibe el día sin esperar la descarga.

Escucha en un socket Unix (`<estado>/serve/telar.sock`) dentro de una carpeta solo para su dueño: en
una máquina compartida, nadie más puede leer tu día. Para probar: `curl --unix-socket <socket> http://telar/hoy`.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI

from telar import __version__
from telar.cli import Contexto
from telar.config import cargar as cargar_config
from telar.config import ruta_config
from telar.servicios import hoy as servicio_hoy

log = logging.getLogger("telar.api")

#: cada cuánto se refresca lo lento (el calendario) aunque nadie lo pida, en segundos: menos que lo
#: que vale su copia (600 s por defecto), así quien pide la encuentra fresca
REFRESCO = 240.0


class _Contexto:
    """La configuración de esta máquina, leída una vez y de nuevo cuando el archivo cambia."""

    def __init__(self) -> None:
        self._config = None
        self._marca: float | None = None

    def __call__(self) -> Contexto:
        ruta = ruta_config()
        try:
            marca = ruta.stat().st_mtime
        except OSError:
            marca = None
        if self._config is None or marca != self._marca:
            self._config, self._marca = cargar_config(), marca
        return Contexto(config=self._config)


contexto = _Contexto()


async def _refrescar() -> None:
    """Mantiene fresco lo que se baja de la red: pide el día cada tanto, como lo pediría un cliente."""
    while True:
        try:
            await asyncio.to_thread(servicio_hoy.hoy, contexto())
        except Exception as e:  # noqa: BLE001 - una vuelta que falla no detiene las siguientes
            log.warning("refresco: %s", e)
        await asyncio.sleep(REFRESCO)


@contextlib.asynccontextmanager
async def _vida(_app: FastAPI):
    tarea = asyncio.create_task(_refrescar())
    try:
        yield
    finally:
        tarea.cancel()


app = FastAPI(title="telar", version=__version__, lifespan=_vida,
              description="Los datos de telar: los mismos contratos que `telar <orden> --json`.")


@app.get("/hoy", response_model=servicio_hoy.Hoy, response_model_exclude_unset=True)
def get_hoy(dia: dt.date | None = None, local: bool = False, ctx: Contexto = Depends(contexto)):
    """El día: la agenda, quién te espera, qué está por hacer y cuánto llevas (`telar hoy --json`)."""
    return servicio_hoy.hoy(ctx, dia=dia, local=local)


@app.get("/salud")
def get_salud() -> dict:
    return {"ok": True, "version": __version__}


def socket_por_defecto() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    # en una carpeta propia: `telar serve` la deja solo para su dueño (0700)
    return (Path(base) if base else Path.home() / ".local" / "state") / "telar" / "serve" / "telar.sock"
