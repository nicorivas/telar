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
    return JSONResponse(status_code=e.codigo, content={"detail": str(e), **e.datos})


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

from telar.servicios import tipos as servicio_tipos
from telar.servicios.tipos import Borrada, TareaConVersion, Tareas


class PedidoTarea(BaseModel):
    """Los parámetros de la acción (`nota`, `fecha`, `quien`…) y la versión que se leyó."""

    params: dict = {}
    version: str | None = None


@app.get("/tipos/tarea", response_model=Tareas)
def get_tareas(abiertas: bool = True, area: str = "", proyecto: str = "", dueno: str | None = None,
               vence_hasta: str = "", ctx: Contexto = Depends(contexto)):
    """Las tareas, desde el índice. Filtros: `abiertas` (por defecto), `area`, `proyecto`, `dueno` («» es
    sin dueño) y `vence_hasta` (AAAA-MM-DD)."""
    return servicio_tipos.lista(ctx, todas=not abiertas, area=area, proyecto=proyecto, dueno=dueno,
                                vence_hasta=vence_hasta)


@app.post("/tipos/tarea", response_model=TareaConVersion)
def post_tarea_nueva(pedido: PedidoTarea, ctx: Contexto = Depends(contexto)):
    """Una tarea nueva (`params`: `titulo` y lo que acepta telar.tipos.tarea.nueva). El número lo elige
    este servidor, el único que las escribe."""
    return servicio_tipos.crear(ctx, pedido.params)


@app.get("/tipos/tarea/{id}", response_model=TareaConVersion)
def get_tarea_tipo(id: str, ctx: Contexto = Depends(contexto)):
    """Una tarea y su versión."""
    return servicio_tipos.obtener(ctx, id)


@app.delete("/tipos/tarea/{id}", response_model=Borrada)
def delete_tarea_tipo(id: str, version: str | None = None, ctx: Contexto = Depends(contexto)):
    """Borra el archivo de la tarea; con `version`, solo si no cambió."""
    return servicio_tipos.borrar(ctx, id, version=version)


@app.post("/tipos/tarea/{id}/{accion}", response_model=TareaConVersion)
def post_tarea_accion(id: str, accion: str, pedido: PedidoTarea, ctx: Contexto = Depends(contexto)):
    """Una acción sobre la tarea (`completar`, `reagendar`, `esperar`…), con la versión que se leyó: si el
    archivo cambió desde entonces, 409 y la versión de ahora. Este servidor es el único que la escribe."""
    return servicio_tipos.aplicar(ctx, id, accion, pedido.params, version=pedido.version)


# ── espejos, proyectos y pendientes ───────────────────────────────────────────

from telar.servicios import espejos as servicio_espejos
from telar.servicios import pendientes as servicio_pendientes
from telar.servicios import proyectos as servicio_proyectos


@app.get("/espejos", response_model=servicio_espejos.Espejos)
def get_espejos(ctx: Contexto = Depends(contexto)):
    """Las fotos de las otras máquinas: sus hilos, como los ve cada una (`telar espejo ver --json`)."""
    return servicio_espejos.ver(ctx)


@app.get("/proyectos", response_model=servicio_proyectos.Proyectos)
def get_proyectos(ctx: Contexto = Depends(contexto)):
    """Las unidades del repositorio y si tienen hilo (`telar proyectos --json`)."""
    return servicio_proyectos.lista(ctx)


@app.get("/pendientes", response_model=servicio_pendientes.Pendientes)
def get_pendientes(repo: bool = False, hechos: bool = False, proveedores: bool = False, hilo: str = "",
                   limite: int = 0, ctx: Contexto = Depends(contexto)):
    """Lo pendiente en los documentos (con `repo`, de todas las unidades) y, con `proveedores`, de las
    fuentes declaradas (`telar pendientes --json`)."""
    return servicio_pendientes.pendientes(ctx, repo=repo, hechos=hechos, proveedores=proveedores, hilo=hilo,
                                          limite=limite)


# ── páginas, la ficha de un hilo y las notas del día ─────────────────────────

from telar.servicios import fichas as servicio_fichas
from telar.servicios import notas as servicio_notas
from telar.servicios import paginas as servicio_paginas


@app.get("/secciones/{clave}", response_model=Pagina, response_model_exclude_unset=True)
def get_seccion(clave: str, ctx: Contexto = Depends(contexto)):
    """El home de una sección o de un agente (`agente:<nombre>`), validado (`telar seccion <clave> --json`)."""
    return servicio_paginas.seccion(ctx, clave)


@app.get("/apps", response_model=servicio_paginas.Apps)
def get_apps(ctx: Contexto = Depends(contexto)):
    """Las apps declaradas (`telar app --json`)."""
    return servicio_paginas.apps(ctx)


@app.get("/apps/{clave}", response_model=Pagina, response_model_exclude_unset=True)
def get_app(clave: str, ctx: Contexto = Depends(contexto)):
    """La página de una app (`telar app <clave> --json`)."""
    return servicio_paginas.app(ctx, clave)


@app.get("/ficha", response_model=servicio_fichas.FichaDeHilo)
def get_ficha(hilo: str, ctx: Contexto = Depends(contexto)):
    """La ficha de un hilo (`telar ficha <hilo> --json`)."""
    return servicio_fichas.ficha(ctx, hilo)


@app.get("/notas", response_model=servicio_notas.Notas)
def get_notas(dia: str = "", ctx: Contexto = Depends(contexto)):
    """Las notas de los eventos de un día (`telar evento notas --json`)."""
    return servicio_notas.notas(ctx, dia)


from telar.servicios import conversaciones as servicio_conversaciones
from telar.servicios import mensajes as servicio_mensajes


@app.get("/mensajes", response_model=servicio_mensajes.Mensajes)
def get_mensajes(n: int = 40, retenidos: bool = False, ctx: Contexto = Depends(contexto)):
    """Los últimos `n` mensajes entre hilos, de todas las máquinas (`telar mensaje --registro N --json`)."""
    return servicio_mensajes.registro(ctx, n, retenidos=retenidos)


@app.get("/conversaciones/{sid}", response_model=servicio_conversaciones.Conversacion)
def get_conversacion(sid: str, ctx: Contexto = Depends(contexto)):
    """Una conversación del agente, entera (`telar agente conversacion <id> --json`)."""
    return servicio_conversaciones.conversacion(ctx, sid)


# ── lo que escribe: mensajes, notas, pestañas ─────────────────────────────────

class PedidoMensaje(BaseModel):
    para: str
    texto: str
    tipo: str = "mensaje"
    #: quién lo manda; vacío, la persona (el panel escribe como ella: «persona»)
    de: str = ""


@app.post("/mensajes", response_model=servicio_mensajes.Enviado)
def post_mensaje(pedido: PedidoMensaje, ctx: Contexto = Depends(contexto)):
    """Un mensaje para un hilo o un agente de cualquier máquina, por el bus (`telar mensaje`)."""
    return servicio_mensajes.enviar(ctx, pedido.para, pedido.texto, tipo=pedido.tipo, de=pedido.de)


@app.post("/mensajes/{mid}/soltar", response_model=servicio_mensajes.Enviado)
def post_soltar(mid: str, ctx: Contexto = Depends(contexto)):
    """Manda un mensaje retenido (`telar mensaje --soltar`)."""
    return servicio_mensajes.soltar(ctx, mid)


class PedidoNota(BaseModel):
    evento: str
    texto: str
    de: str
    titulo: str = ""
    inicio: str = ""
    dia: str = ""


@app.post("/notas", response_model=servicio_notas.Notas)
def post_nota(pedido: PedidoNota, ctx: Contexto = Depends(contexto)):
    """Una nota en un evento del día (`telar evento nota`)."""
    return servicio_notas.agregar(ctx, pedido.evento, pedido.texto, de=pedido.de, titulo=pedido.titulo,
                                  inicio=pedido.inicio, dia=pedido.dia)


class PedidoPestanas(BaseModel):
    #: «hoy,plan,-correo»: el orden, y con «-» las que se esconden; vacío, todas en su orden
    valor: str = ""


@app.put("/config/pestanas", response_model=servicio_config.Pestanas)
def put_pestanas(pedido: PedidoPestanas, ctx: Contexto = Depends(contexto)):
    """El orden de las pestañas del dashboard, escrito en la configuración (`telar config --pestanas`)."""
    return servicio_config.pestanas(ctx, pedido.valor)


# ── lo que abre hilos: atajos, encargos, unidades ────────────────────────────

from telar.servicios import atajos as servicio_atajos
from telar.servicios import encargos as servicio_encargos


@app.get("/atajos", response_model=servicio_atajos.Atajos)
def get_atajos(ctx: Contexto = Depends(contexto)):
    """Los atajos del dashboard (`telar atajo --json`)."""
    return servicio_atajos.lista(ctx)


@app.post("/atajos/{tecla}", response_model=servicio_atajos.AtajoHecho)
def post_atajo(tecla: str, ctx: Contexto = Depends(contexto)):
    """Correr un atajo: un hilo nuevo con su mensaje, o el encargo a su agente (`telar atajo <tecla>`)."""
    return servicio_atajos.correr(ctx, tecla)


class PedidoEncargo(BaseModel):
    agente: str
    texto: str


@app.post("/encargos", response_model=servicio_encargos.Encargo)
def post_encargo(pedido: PedidoEncargo, ctx: Contexto = Depends(contexto)):
    """Encargarle algo a un agente residente (`telar encargar`)."""
    return servicio_encargos.encargar(ctx, pedido.agente, pedido.texto)


class PedidoUnidad(BaseModel):
    ruta: str


@app.post("/proyectos/abrir", response_model=servicio_atajos.Abierto)
def post_abrir_unidad(pedido: PedidoUnidad, ctx: Contexto = Depends(contexto)):
    """Ir al hilo de una unidad o abrirle uno (`telar proyectos abrir <ruta>`)."""
    return servicio_atajos.abrir_unidad(ctx, pedido.ruta)


from telar.servicios import ir as servicio_ir


class PedidoIr(BaseModel):
    hilo: str
    crear: bool = False
    remoto: str = ""


@app.post("/ir", response_model=servicio_ir.Ido)
def post_ir(pedido: PedidoIr, ctx: Contexto = Depends(contexto)):
    """El foco en un hilo; con `crear`, lo abre si no está vivo (aquí, o en `remoto`) (`telar ir`)."""
    return servicio_ir.ir(ctx, pedido.hilo, crear=pedido.crear, remoto=pedido.remoto)


class PedidoLlevar(BaseModel):
    ref: str
    nuevo: bool = False
    donde: bool = False
    texto: str = ""
    enviar: bool = False
    proveedor: str = ""


@app.post("/pendiente/llevar", response_model=servicio_pendientes.Llevado)
def post_llevar(pedido: PedidoLlevar, ctx: Contexto = Depends(contexto)):
    """Llevar un pendiente al hilo donde se trabaja (`telar pendiente <ref>`)."""
    return servicio_pendientes.llevar(ctx, pedido.ref, nuevo=pedido.nuevo, donde=pedido.donde, texto=pedido.texto,
                                      enviar=pedido.enviar, proveedor=pedido.proveedor)


class PedidoCasilla(BaseModel):
    ref: str
    hecho: bool = False
    responsable: str | None = None
    linea: bool = False
    esperado: str = ""
    proveedor: str = ""


@app.post("/pendiente/casilla", response_model=servicio_pendientes.Llevado)
def post_casilla(pedido: PedidoCasilla, ctx: Contexto = Depends(contexto)):
    """Una casilla en su documento: hecha, responsable o dónde está (`telar pendiente <ref> --hecho`…)."""
    return servicio_pendientes.casilla(ctx, pedido.ref, hecho=pedido.hecho, responsable=pedido.responsable,
                                       linea=pedido.linea, esperado=pedido.esperado, proveedor=pedido.proveedor)


# ── los verbos de un hilo y tejer: la misma orden, en el proceso (telar.servicios.en_proceso) ──

from telar.servicios import en_proceso

#: los verbos de `telar hilo` que se corren por la API; `llevar` (minutos, por ssh) y `leer`/`caidos` no
VERBOS_HILO = ("ver", "vincular", "desvincular", "renombrar", "adoptar", "prioridad", "mudar", "cerrar",
               "archivar", "desarchivar", "retomar", "olvidar")


class PedidoHilo(BaseModel):
    hilo: str
    valor: str = ""
    #: con archivar: además, cerrarlo en el multiplexor
    cerrar: bool = False


@app.post("/hilo/{verbo}", response_model=en_proceso.Corrida)
def post_hilo(verbo: str, pedido: PedidoHilo, ctx: Contexto = Depends(contexto)):
    """Vincular, renombrar, priorizar, archivar, cerrar… un hilo (`telar hilo <verbo> [valor] --hilo <hilo>`)."""
    if verbo not in VERBOS_HILO:
        raise ErrorDeServicio(f"«{verbo}» no se pide por aquí: uno de {', '.join(VERBOS_HILO)}", 422)
    argv = [verbo, *([pedido.valor] if pedido.valor else []), "--hilo", pedido.hilo, *(["--cerrar"] if pedido.cerrar else [])]
    return en_proceso.o_falla(en_proceso.correr(ctx, "hilo", argv), f"telar hilo {verbo}")


class PedidoTejer(BaseModel):
    sumar: bool = False
    vacia: bool = False


@app.post("/tejer", response_model=en_proceso.Corrida)
def post_tejer(pedido: PedidoTejer, ctx: Contexto = Depends(contexto)):
    """Levantar la sesión, o reengancharla; con `sumar`, abrir los hilos de [hilos] que falten (`telar tejer`)."""
    argv = [*(["--sumar"] if pedido.sumar else []), *(["--vacia"] if pedido.vacia else [])]
    return en_proceso.o_falla(en_proceso.correr(ctx, "tejer", argv), "telar tejer")


@app.get("/salud")
def get_salud() -> dict:
    return {"ok": True, "version": __version__}


def socket_por_defecto() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    # en una carpeta propia: `telar serve` la deja solo para su dueño (0700)
    return (Path(base) if base else Path.home() / ".local" / "state") / "telar" / "serve" / "telar.sock"
