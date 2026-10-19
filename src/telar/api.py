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

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from telar import __version__
from telar.cli import Contexto
from telar.config import cargar as cargar_config
from telar.config import ruta_config
from telar.servicios import ErrorDeServicio, Pagina
from telar.servicios import bloques as servicio_bloques
from telar.servicios import config as servicio_config
from telar.servicios import hilos as servicio_hilos
from telar.servicios import hoy as servicio_hoy
from telar.servicios import resultados as servicio_resultados
from telar.servicios import tareas as servicio_tareas

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


@app.get("/hilos", response_model=servicio_hilos.Hilos, response_model_exclude_unset=True)
def get_hilos(vivos: bool = False, red: bool = False, ficha: bool = True, orden: str = "",
              ctx: Contexto = Depends(contexto)):
    """Los hilos de la sesión (`telar hilos --json`). `ficha=false` no lee los documentos (más rápido);
    `red=true` suma los de las otras máquinas, del registro del bus."""
    if orden and orden not in servicio_hilos.ORDENES:
        raise HTTPException(422, f"orden: una de {', '.join(servicio_hilos.ORDENES)}")
    return servicio_hilos.hilos(ctx, vivos=vivos, red=red, con_ficha=ficha, orden=orden)


@app.get("/config", response_model=servicio_config.ConfigResuelta, response_model_exclude_unset=True)
def get_config(ctx: Contexto = Depends(contexto)):
    """La configuración resuelta de esta máquina (`telar config --json`)."""
    return servicio_config.resuelta(ctx)


@app.exception_handler(ErrorDeServicio)
async def _error_de_servicio(_req: Request, e: ErrorDeServicio):
    """Lo que no se pudo hacer, con el mismo mensaje que daría la CLI."""
    return JSONResponse(status_code=e.codigo, content={"detail": str(e)})


# ── las tareas de un proveedor: su ficha y sus acciones ───────────────────────

class PedidoAccion(BaseModel):
    """Qué acción correr: por su número (`n`) o por su `rol` (hecha, fecha…), y lo escrito si la pide."""

    n: int | None = None
    rol: str = ""
    texto: str = ""
    proveedor: str = "tareas"
    #: la versión de la ficha que se leyó: si la tarea cambió desde entonces, 409 y no se hace
    version: str | None = None


@app.get("/tareas/{id:path}", response_model=Pagina, response_model_exclude_unset=True)
def get_tarea(id: str, proveedor: str = "tareas", ctx: Contexto = Depends(contexto)):
    """La ficha de una tarea, con sus acciones (`telar tarea <id> --json`)."""
    return servicio_tareas.ficha(ctx, id, proveedor)


@app.post("/tareas/{id:path}/accion", response_model=servicio_tareas.AccionHecha)
def post_accion(id: str, pedido: PedidoAccion, ctx: Contexto = Depends(contexto)):
    """Correr una acción de la ficha (`telar tarea <id> --accion N | --rol R`). El comando lo da el
    proveedor, nunca quien pide."""
    return servicio_tareas.accion(ctx, id, pedido.proveedor, n=pedido.n, rol=pedido.rol, texto=pedido.texto,
                                  version=pedido.version)


# ── los bloques del día ───────────────────────────────────────────────────────

@app.get("/bloques/{clave}", response_model=Pagina, response_model_exclude_unset=True)
def get_bloque(clave: str, ctx: Contexto = Depends(contexto)):
    """La página de un bloque del día (`telar bloque <clave> --json`)."""
    return servicio_bloques.pagina(ctx, clave)


@app.get("/bloques/{clave}/items/{id:path}", response_model=servicio_bloques.Detalle)
def get_item(clave: str, id: str, ctx: Contexto = Depends(contexto)):
    """El detalle de un ítem de un bloque: el cuerpo de un correo (`telar bloque <clave> --item <id>`)."""
    return servicio_bloques.item(ctx, clave, id)


@app.post("/bloques/{clave}/abrir", response_model=servicio_bloques.Abierto)
def post_abrir(clave: str, mensaje: str = Body(...), nombre: str = Body(""), ctx: Contexto = Depends(contexto)):
    """Un hilo nuevo con el agente y ese mensaje, para una fila del bloque (`telar bloque <clave> --abrir`)."""
    return servicio_bloques.abrir(ctx, clave, mensaje, nombre)


# ── lo que dejan las skills por día ──────────────────────────────────────────

@app.get("/resultados/{clave}", response_model=servicio_resultados.Resultado, response_model_exclude_unset=True)
def get_resultado(clave: str, dia: str = "", ctx: Contexto = Depends(contexto)):
    """Lo que una skill dejó ese día (por defecto, hoy), leído donde vive (`telar resultado <clave> --json`)."""
    return servicio_resultados.leer(ctx, clave, dia)


@app.post("/resultados/{clave}/comentario", response_model=servicio_resultados.Comentario, response_model_exclude_unset=True)
def post_comentario(clave: str, dia: str = Body(...), texto: str = Body(...), ctx: Contexto = Depends(contexto)):
    """Un comentario sobre el resultado de un día, atendido donde vive (`telar resultado … --comentar`)."""
    return servicio_resultados.comentar(ctx, clave, dia, texto)


# ── los tipos: objetos sobre archivos (telar.tipos), desde el índice en memoria ───────

from telar.tipos import ErrorDeFormato
from telar.tipos import tarea as tipo_tarea
from telar.tipos.carpeta import Carpeta, ErrorDeVersion, NoExiste
from telar.tipos.indice import Indice

_indices: dict[tuple[str, str], Indice] = {}


def _indice_de(ctx: Contexto, clave: str) -> Indice:
    """El índice del tipo en esta máquina: uno por carpeta, y vive lo que vive el proceso."""
    t = next((x for x in ctx.config.tipos if x.clave == clave), None)
    if t is None or not t.carpeta:
        raise ErrorDeServicio(f"esta máquina no declara dónde viven los objetos «{clave}» ([tipos.{clave}] carpeta)", 404)
    llave = (clave, t.carpeta)
    if llave not in _indices:
        # el mismo índice que usan los proveedores de este proceso (telar.tipos.indice.compartido)
        from telar.tipos.indice import compartido

        _indices[llave] = compartido(t.carpeta, tipo_tarea.ARCHIVO)
    return _indices[llave]


class TareaConVersion(tipo_tarea.Tarea):
    """Una tarea y la versión de su archivo: la que se devuelve con una acción para no pisar a otro."""

    version: str


class Tareas(BaseModel):
    tareas: list[TareaConVersion]
    fallas: dict[str, str] = {}


class PedidoTarea(BaseModel):
    """Los parámetros de la acción (`nota`, `fecha`, `quien`…) y la versión que se leyó."""

    params: dict = {}
    version: str | None = None


def _con_version(par) -> TareaConVersion:
    t, v = par
    return TareaConVersion(**t.model_dump(), version=v)


@app.get("/tipos/tarea", response_model=Tareas)
def get_tareas(abiertas: bool = True, area: str = "", proyecto: str = "", dueno: str | None = None,
               vence_hasta: str = "", ctx: Contexto = Depends(contexto)):
    """Las tareas, desde el índice. Filtros: `abiertas` (por defecto), `area`, `proyecto`, `dueno` («» es
    sin dueño) y `vence_hasta` (AAAA-MM-DD)."""
    def pasa(t) -> bool:
        return ((not abiertas or not t.cerrada_ya) and (not area or t.area == area)
                and (not proyecto or t.proyecto == proyecto) and (dueno is None or t.dueno == dueno)
                and (not vence_hasta or (t.vence and t.vence <= vence_hasta)))
    ind = _indice_de(ctx, "tarea")
    return Tareas(tareas=[_con_version(x) for x in ind.consultar(pasa)], fallas=dict(ind.fallas))


@app.get("/tipos/tarea/{id}", response_model=TareaConVersion)
def get_tarea_tipo(id: str, ctx: Contexto = Depends(contexto)):
    """Una tarea y su versión."""
    try:
        return _con_version(_indice_de(ctx, "tarea").obtener(id))
    except NoExiste as e:
        raise ErrorDeServicio(str(e), 404) from e


@app.post("/tipos/tarea/{id}/{accion}", response_model=TareaConVersion)
def post_tarea_accion(id: str, accion: str, pedido: PedidoTarea, ctx: Contexto = Depends(contexto)):
    """Una acción sobre la tarea (`completar`, `reagendar`, `esperar`…), con la versión que se leyó: si el
    archivo cambió desde entonces, 409 y la versión de ahora. Este servidor es el único que la escribe."""
    fn = tipo_tarea.ACCIONES.get(accion)
    if fn is None:
        raise ErrorDeServicio(f"no hay una acción «{accion}»: {', '.join(tipo_tarea.ACCIONES)}", 422)
    try:
        return _con_version(_indice_de(ctx, "tarea").aplicar(id, fn, version=pedido.version, **pedido.params))
    except NoExiste as e:
        raise ErrorDeServicio(str(e), 404) from e
    except ErrorDeVersion as e:
        return JSONResponse(status_code=409, content={"detail": str(e), "version": e.actual})
    except tipo_tarea.ErrorDeAccion as e:
        raise ErrorDeServicio(str(e), 409) from e
    except TypeError as e:
        raise ErrorDeServicio(f"«{accion}» no lleva esos parámetros: {e}", 422) from e
    except ErrorDeFormato as e:
        raise ErrorDeServicio(str(e), 422) from e


@app.get("/salud")
def get_salud() -> dict:
    return {"ok": True, "version": __version__}


def socket_por_defecto() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    # en una carpeta propia: `telar serve` la deja solo para su dueño (0700)
    return (Path(base) if base else Path.home() / ".local" / "state") / "telar" / "serve" / "telar.sock"
