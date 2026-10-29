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
import json
import logging
import os
import subprocess
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from telar import __version__
from telar.cli import Contexto
from telar.config import cargar as cargar_config
from telar.config import ruta_config
from telar.servicios import archivos as servicio_archivos
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
    """La configuración de esta máquina, leída una vez y de nuevo cuando el archivo (o `modulos.toml`) cambia."""

    def __init__(self) -> None:
        self._config = None
        self._marca: list | None = None

    def __call__(self) -> Contexto:
        ruta = ruta_config()
        # la configuración y los módulos instalados (`modulos.toml`, al lado): instalar, activar o quitar uno desde la
        # página cambia el segundo, y la configuración se relee igual
        marca = []
        for archivo in (ruta, ruta.parent / "modulos.toml"):
            try:
                marca.append(archivo.stat().st_mtime)
            except OSError:
                marca.append(None)
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
    #: el mensaje de la acción, a este hilo o agente (su nombre) y no al de la tarea; 404 si no existe
    hilo: str = ""


@app.get("/tareas/{id:path}", response_model=Pagina, response_model_exclude_unset=True)
def get_tarea(id: str, proveedor: str = "tareas", ctx: Contexto = Depends(contexto)):
    """La ficha de una tarea, con sus acciones (`telar tarea <id> --json`)."""
    return servicio_tareas.ficha(ctx, id, proveedor)


@app.post("/tareas/{id:path}/accion", response_model=servicio_tareas.AccionHecha)
def post_accion(id: str, pedido: PedidoAccion, ctx: Contexto = Depends(contexto)):
    """Correr una acción de la ficha (`telar tarea <id> --accion N | --rol R`). El comando lo da el
    proveedor, nunca quien pide."""
    return servicio_tareas.accion(ctx, id, pedido.proveedor, n=pedido.n, rol=pedido.rol, texto=pedido.texto,
                                  version=pedido.version, hilo=pedido.hilo)


# ── los bloques del día ───────────────────────────────────────────────────────

@app.get("/bloques/{clave}", response_model=Pagina, response_model_exclude_unset=True)
def get_bloque(clave: str, ctx: Contexto = Depends(contexto)):
    """La página de un bloque del día (`telar bloque <clave> --json`)."""
    return servicio_archivos.anotar_lienzos(servicio_bloques.pagina(ctx, clave))


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
from telar.servicios import actuar as servicio_actuar
from telar.servicios import fechas as servicio_fechas
from telar.servicios import lienzos as servicio_lienzos
from telar.servicios import proyectos as servicio_proyectos


@app.get("/espejos", response_model=servicio_espejos.Espejos)
def get_espejos(ctx: Contexto = Depends(contexto)):
    """Las fotos de las otras máquinas: sus hilos, como los ve cada una (`telar espejo ver --json`)."""
    return servicio_espejos.ver(ctx)


@app.get("/proyectos", response_model=servicio_proyectos.Proyectos)
def get_proyectos(ctx: Contexto = Depends(contexto)):
    """Las unidades del repositorio y si tienen hilo (`telar proyectos --json`)."""
    return servicio_proyectos.lista(ctx)


@app.post("/lienzo/pedir")
def post_lienzo_pedir(pedido: servicio_lienzos.Pedido, ctx: Contexto = Depends(contexto)):
    """Lo que la página de un módulo pide que telar haga por ella (`window.lienzo.pedir`): solo lo que el módulo declaró
    y la persona le concedió; si falta la concesión, un 403 con `permiso` (telar.servicios.lienzos)."""
    return servicio_lienzos.pedir(ctx, pedido.origen, pedido.orden, pedido.datos)


@app.get("/permisos")
def get_permisos(ctx: Contexto = Depends(contexto)):
    """Lo que la persona le concedió o negó a cada módulo (telar.concesiones)."""
    from telar import concesiones

    return concesiones.leer(ctx.config)


@app.post("/permisos")
def post_permisos(c: servicio_lienzos.Concesion, ctx: Contexto = Depends(contexto)):
    """Anotar lo que la persona decidió sobre lo que pide un módulo: «concedido» o «negado»."""
    return servicio_lienzos.conceder(ctx, c.modulo, c.orden, c.decision)


class PedidoActuar(BaseModel):
    direccion: str
    a: str = ""
    skill: str = ""
    nota: str = ""
    escribir: bool = False


@app.post("/actuar", response_model=servicio_actuar.Actuado)
def post_actuar(p: PedidoActuar, ctx: Contexto = Depends(contexto)):
    """Mandarle a un hilo o a un agente un prompt sobre una entidad, con su contexto (`telar actuar`)."""
    return servicio_actuar.actuar(ctx, p.direccion, a=p.a, skill=p.skill, nota=p.nota, escribir=p.escribir)


class CambioDeFecha(BaseModel):
    id: str
    inicio: dt.date | None = None
    fin: dt.date | None = None
    version: str = ""


@app.post("/fecha", response_model=servicio_fechas.Fecha)
def post_fecha(cambio: CambioDeFecha, ctx: Contexto = Depends(contexto)):
    """Cambiar una fecha donde vive (`telar fecha <id> --inicio … --json`)."""
    return servicio_fechas.escribir(ctx, cambio.id, inicio=cambio.inicio, fin=cambio.fin, version=cambio.version)


@app.get("/fechas", response_model=servicio_fechas.Fechas)
def get_fechas(proyecto: str = "", desde: dt.date | None = None, hasta: dt.date | None = None,
               ctx: Contexto = Depends(contexto)):
    """Lo que tiene día, venga de donde venga (`telar fechas --json`)."""
    return servicio_fechas.lista(ctx, proyecto=proyecto, desde=desde, hasta=hasta)


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
    return servicio_archivos.anotar_lienzos(servicio_paginas.seccion(ctx, clave))


@app.get("/apps", response_model=servicio_paginas.Apps)
def get_apps(ctx: Contexto = Depends(contexto)):
    """Las apps declaradas (`telar app --json`)."""
    return servicio_paginas.apps(ctx)


@app.get("/apps/{clave}", response_model=Pagina, response_model_exclude_unset=True)
def get_app(clave: str, ctx: Contexto = Depends(contexto)):
    """La página de una app (`telar app <clave> --json`)."""
    return servicio_archivos.anotar_lienzos(servicio_paginas.app(ctx, clave))


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


@app.get("/mensajes/consulta", response_model=servicio_mensajes.Consulta)
def get_consulta(para: str, ctx: Contexto = Depends(contexto)):
    """En qué anda un hilo, sin mandarle nada (`telar mensaje <hilo> --modo consulta --json`)."""
    return servicio_mensajes.consultar(ctx, para)


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
    #: aviso, pedido (el de siempre) o encargo (docs/propuestas/mensajes-con-modos.md)
    modo: str = "pedido"
    #: con modo encargo: para cuándo (2026-10-24)
    plazo: str = ""


@app.post("/mensajes", response_model=servicio_mensajes.Enviado)
def post_mensaje(pedido: PedidoMensaje, ctx: Contexto = Depends(contexto)):
    """Un mensaje para un hilo o un agente de cualquier máquina, por el bus (`telar mensaje`)."""
    return servicio_mensajes.enviar(ctx, pedido.para, pedido.texto, tipo=pedido.tipo, de=pedido.de, modo=pedido.modo,
                                    plazo=pedido.plazo)


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
               "archivar", "desarchivar", "publicar", "privar", "retomar", "olvidar")


class PedidoHilo(BaseModel):
    hilo: str
    valor: str = ""
    #: con archivar: además, cerrarlo en el multiplexor
    cerrar: bool = False


class PedidoLlevarHilo(BaseModel):
    hilo: str
    #: a cuál de [remotos]; vacío, la única que haya
    maquina: str = ""
    #: seguir aunque aquí haya trabajo sin subir (la primera vez sin esto, la queja lo dice)
    si: bool = False


from telar.servicios import llevar as servicio_llevar  # noqa: E402


@app.post("/hilo/llevar", response_model=servicio_llevar.Llevado)
def post_hilo_llevar(pedido: PedidoLlevarHilo, ctx: Contexto = Depends(contexto)):
    """Llevar un hilo a otra máquina (`telar hilo llevar`). Tarda minutos con una conversación grande: si no
    termina en unos segundos, responde `en_curso` y sigue solo. Con trabajo sin subir, 409 hasta que `si`."""
    return servicio_llevar.llevar(ctx, pedido.hilo, pedido.maquina, pedido.si)


@app.get("/mudanza")
def get_mudanza(hilo: str, ctx: Contexto = Depends(contexto)):
    """En qué va la mudanza de un hilo a otra máquina (telar.mudanza.progreso): su paso, a dónde, cuánto pesa, y lo
    que haya que decir. {} si no hay ninguna."""
    import json

    from telar import mudanza

    ruta = mudanza.ruta_progreso(ctx.config, hilo)
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@app.post("/hilo/traer", response_model=servicio_llevar.Llevado)
def post_hilo_traer(pedido: PedidoLlevarHilo, ctx: Contexto = Depends(contexto)):
    """Traer a esta máquina un hilo que vive en otra de la persona (`maquina`): esa lo lleva aquí por el bus. Con
    trabajo sin subir allá, 409 hasta que `si`."""
    return servicio_llevar.traer(ctx, pedido.hilo, pedido.maquina, pedido.si)


@app.post("/hilo/{verbo}", response_model=en_proceso.Corrida)
def post_hilo(verbo: str, pedido: PedidoHilo, ctx: Contexto = Depends(contexto)):
    """Vincular, renombrar, priorizar, archivar, cerrar… un hilo (`telar hilo <verbo> [valor] --hilo <hilo>`)."""
    if verbo not in VERBOS_HILO:
        raise ErrorDeServicio(f"«{verbo}» no se pide por aquí: uno de {', '.join(VERBOS_HILO)}", 422)
    argv = [verbo, *([pedido.valor] if pedido.valor else []), "--hilo", pedido.hilo, *(["--cerrar"] if pedido.cerrar else [])]
    return en_proceso.o_falla(en_proceso.correr(ctx, "hilo", argv), f"telar hilo {verbo}")


class PedidoReunion(BaseModel):
    titulo: str
    hora: str
    fecha: str = ""
    enlace: str = ""
    evento: str = ""
    asistentes: list[str] = []
    proyecto: str = ""
    preguntar: bool = False
    donde: bool = False
    hilo_nuevo: bool = False


class Reunion(BaseModel):
    """Lo que dice `telar reunion --json`: el hilo, el proyecto, el mensaje y qué se hizo."""

    model_config = ConfigDict(extra="allow")


@app.post("/reunion", response_model=Reunion)
def post_reunion(pedido: PedidoReunion, ctx: Contexto = Depends(contexto)):
    """Preparar una reunión, o hacer su minuta: un hilo con el agente ya trabajando en ella (`telar reunion`)."""
    argv = [pedido.titulo, pedido.hora, *(["--fecha", pedido.fecha] if pedido.fecha else []),
            *(["--enlace", pedido.enlace] if pedido.enlace else []), *(["--evento", pedido.evento] if pedido.evento else []),
            *(["--asistentes", ",".join(pedido.asistentes)] if pedido.asistentes else []),
            *(["--proyecto", pedido.proyecto] if pedido.proyecto else []), *(["--preguntar"] if pedido.preguntar else []),
            *(["--donde"] if pedido.donde else []), *(["--hilo-nuevo"] if pedido.hilo_nuevo else []), "--json"]
    c = en_proceso.o_falla(en_proceso.correr(ctx, "reunion", argv), "telar reunion")
    try:
        return Reunion(**json.loads(c.salida.strip().splitlines()[-1]))
    except (ValueError, IndexError) as e:
        raise ErrorDeServicio(f"telar reunion no respondió JSON: {c.salida[-200:]!r}", 502) from e


class PedidoTejer(BaseModel):
    sumar: bool = False
    vacia: bool = False


@app.post("/tejer", response_model=en_proceso.Corrida)
def post_tejer(pedido: PedidoTejer, ctx: Contexto = Depends(contexto)):
    """Levantar la sesión, o reengancharla; con `sumar`, abrir los hilos de [hilos] que falten (`telar tejer`)."""
    argv = [*(["--sumar"] if pedido.sumar else []), *(["--vacia"] if pedido.vacia else [])]
    return en_proceso.o_falla(en_proceso.correr(ctx, "tejer", argv), "telar tejer")


# ── ajustes, compartir, leer un hilo, skills ──────────────────────────────────

from telar.servicios import compartir as servicio_compartir
from telar.servicios import historias as servicio_historias
from telar.servicios import skills as servicio_skills


class PedidoAjuste(BaseModel):
    valor: str = ""


@app.put("/config/{ajuste}", response_model=servicio_config.Escrito)
def put_ajuste(ajuste: str, pedido: PedidoAjuste, ctx: Contexto = Depends(contexto)):
    """Un ajuste escrito en la configuración (`telar config --directorios|--reunion|--proyecto|--calendario`):
    `directorios` («a,b»), `reunion` y `proyecto` (la plantilla; vacía, la de fábrica), `calendario`
    (`gws`, `ninguno` o una dirección iCal)."""
    if ajuste == "directorios":
        return servicio_config.directorios(ctx, pedido.valor)
    if ajuste in ("reunion", "proyecto"):
        return servicio_config.plantilla(ctx, ajuste, pedido.valor)
    if ajuste == "calendario":
        if not pedido.valor.strip():
            raise ErrorDeServicio("calendario: gws, ninguno o la dirección de un calendario", 422)
        return servicio_config.calendario(ctx, pedido.valor)
    raise ErrorDeServicio(f"no hay un ajuste «{ajuste}»: directorios, reunion, proyecto, calendario o pestanas", 404)


# ── la terminal de los hilos: su ancho, su posición y su fondo (`[terminal]`) ───────────────

#: los fondos de siempre, además de un color, una imagen o un módulo
FONDOS = (("telar", "telar", "el de siempre: un telar tenue que teje"), ("ninguno", "ninguno", "nada: el fondo de la página"))
IMAGENES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
            ".svg": "image/svg+xml"}


def _modulo_fondo(ctx, nombre: str):
    return next((m for m in getattr(ctx.config, "modulos", ()) if m.nombre == nombre and m.fondo), None)


@app.get("/terminal/fondos")
def get_terminal_fondos(ctx: Contexto = Depends(contexto)) -> dict:
    """Los fondos que se pueden elegir para la terminal: los de siempre y los de los módulos que traen `[fondo]`;
    además vale un color (#rrggbb) o una imagen (imagen:ruta o imagen:https://…)."""
    salida = [{"valor": v, "nombre": n, "descripcion": d, "tipo": "propio"} for v, n, d in FONDOS]
    salida += [{"valor": m.nombre, "nombre": m.fondo.get("nombre") or m.nombre, "descripcion": m.descripcion,
                "tipo": "modulo"} for m in getattr(ctx.config, "modulos", ()) if m.fondo]
    t = ctx.config.terminal
    return {"fondos": salida, "actual": {"columnas": t.columnas, "posicion": t.posicion, "fondo": t.fondo}}


class PedidoTerminal(BaseModel):
    valor: str | int


@app.put("/config/terminal/{clave}")
def put_terminal(clave: str, pedido: PedidoTerminal, ctx: Contexto = Depends(contexto)) -> dict:
    """Cambiar cómo se ve la terminal: `columnas` (40–400, o 0: todo el ancho), `posicion` (izquierda, centro,
    derecha) o `fondo` (telar, ninguno, #rrggbb, imagen:…, o un módulo con `[fondo]`). Se escribe en `[terminal]`."""
    from telar import config as mod_config

    try:
        valor = mod_config.validar_terminal(clave, pedido.valor)
        if clave == "fondo" and isinstance(valor, str) and valor not in ("telar", "ninguno") \
                and not valor.startswith(("#", "imagen:")) and _modulo_fondo(ctx, valor) is None:
            raise mod_config.ErrorDeConfig(f"no hay un módulo «{valor}» con [fondo]: telar, ninguno, #rrggbb, imagen:… "
                                           f"o uno de GET /terminal/fondos")
        if clave == "fondo" and isinstance(valor, str) and valor.startswith("imagen:") and "://" not in valor:
            ruta = Path(valor[len("imagen:"):]).expanduser()
            if ruta.suffix.lower() not in IMAGENES or not ruta.is_file():
                raise mod_config.ErrorDeConfig(f"{ruta}: no es una imagen de esta máquina ({', '.join(IMAGENES)})")
        mod_config.escribir_clave("terminal", clave, valor, ctx.config.origen)
    except mod_config.ErrorDeConfig as e:
        raise ErrorDeServicio(str(e), 422) from e
    return {"ok": True, "clave": clave, "valor": valor}


@app.get("/terminal/imagen")
def get_terminal_imagen(ctx: Contexto = Depends(contexto)):
    """La imagen de esta máquina que es el fondo de la terminal (`fondo = "imagen:<ruta>"`)."""
    from fastapi.responses import FileResponse

    f = ctx.config.terminal.fondo
    if not f.startswith("imagen:") or "://" in f:
        raise ErrorDeServicio("el fondo no es una imagen de esta máquina", 404)
    ruta = Path(f[len("imagen:"):]).expanduser()
    tipo = IMAGENES.get(ruta.suffix.lower())
    if tipo is None or not ruta.is_file():
        raise ErrorDeServicio(f"no encuentro {ruta}", 404)
    return FileResponse(ruta, media_type=tipo, headers={"Cache-Control": "no-cache"})


@app.get("/terminal/fondo/{ruta:path}")
def get_terminal_fondo(ruta: str, ctx: Contexto = Depends(contexto)):
    """El módulo que es el fondo de la terminal: su página (`/terminal/fondo/`) y lo que ella pida de su carpeta.
    Se dibuja aislado (un iframe sin el origen de la página): no ve la página ni la API. Sin llave en la página
    (web/api_web.py), porque desde ese iframe el navegador no manda la cookie: son los archivos del módulo."""
    from fastapi.responses import FileResponse

    m = _modulo_fondo(ctx, ctx.config.terminal.fondo)
    if m is None:
        raise ErrorDeServicio("el fondo de la terminal no es un módulo", 404)
    principal = Path(m.fondo["archivo"]).resolve()
    carpeta = principal.parent
    destino = principal if not ruta else (carpeta / ruta).resolve()
    if not destino.is_relative_to(carpeta) or not destino.is_file():
        raise ErrorDeServicio("no hay eso en el fondo", 404)
    return FileResponse(destino, headers={"Cache-Control": "no-cache",
                                          "Content-Security-Policy": "sandbox allow-scripts"})


# ── los modos de la página (telar.modos) ──────────────────────────────────────────


class PedidoModo(BaseModel):
    valores: dict = {}
    nombre: str = ""


@app.get("/modos")
def get_modos(ctx: Contexto = Depends(contexto)) -> dict:
    """Los modos de la página (de fábrica y los de `[modos]`), cada uno con todos sus valores, y el catálogo de
    ajustes que un modo puede decir. Cuál está puesto lo sabe el navegador."""
    from telar import modos

    return {"catalogo": modos.catalogo(), "modos": modos.todos(ctx.config)}


@app.put("/modos/{clave}")
def put_modo(clave: str, pedido: PedidoModo, ctx: Contexto = Depends(contexto)) -> dict:
    """Crear o cambiar un modo: escribe `[modos.<clave>]` con esos valores (lo que no diga, de «estándar»)."""
    from telar import config as mod_config
    from telar import modos

    try:
        modos.guardar(ctx.config.origen, clave, pedido.valores, pedido.nombre)
    except mod_config.ErrorDeConfig as e:
        raise ErrorDeServicio(str(e), 422) from e
    return {"ok": True, "modos": modos.todos(mod_config.cargar(ctx.config.origen))}


@app.delete("/modos/{clave}")
def delete_modo(clave: str, ctx: Contexto = Depends(contexto)) -> dict:
    """Quitar `[modos.<clave>]`: uno propio desaparece; uno de fábrica vuelve a ser el de fábrica."""
    from telar import config as mod_config
    from telar import modos

    try:
        hubo = modos.borrar(ctx.config.origen, clave)
    except mod_config.ErrorDeConfig as e:
        raise ErrorDeServicio(str(e), 422) from e
    if not hubo:
        raise ErrorDeServicio(f"no hay [modos.{clave}] en la configuración", 404)
    return {"ok": True, "modos": modos.todos(mod_config.cargar(ctx.config.origen))}


@app.get("/compartir/destinos", response_model=servicio_compartir.Destinos)
def get_destinos(ctx: Contexto = Depends(contexto)):
    """Los proveedores que reciben algo compartido (`telar compartir --destinos`)."""
    return servicio_compartir.destinos(ctx)


class PedidoCompartir(BaseModel):
    a: str
    url: str = ""
    texto: str = ""
    titulo: str = ""


@app.post("/compartir", response_model=servicio_compartir.Compartido)
def post_compartir(pedido: PedidoCompartir, ctx: Contexto = Depends(contexto)):
    """Llevar algo compartido a un hilo (`hilo:<nombre>`) o a un proveedor (`telar compartir`)."""
    return servicio_compartir.llevar(ctx, pedido.a, url=pedido.url, texto=pedido.texto, titulo=pedido.titulo)


@app.get("/hilos/leer", response_model=servicio_historias.Historia)
def get_leer(hilo: str, ultimos: int = 0, maquina: str = "", ctx: Contexto = Depends(contexto)):
    """Lo último de un hilo, de esta máquina o de otra por el bus (`telar hilo leer <hilo> --json`)."""
    return servicio_historias.leer(ctx, hilo, ultimos=ultimos, maquina=maquina)


from telar.servicios import documentos as servicio_documentos


@app.get("/hilos/documento", response_model=servicio_documentos.Documento)
def get_documento(hilo: str = "", archivo: str = "", ctx: Contexto = Depends(contexto)):
    """La carpeta de un hilo y uno de sus archivos (su documento, si no se pide otro), para leerlos. Sin hilo,
    un archivo o una carpeta de la raíz del repositorio."""
    return servicio_documentos.documento(ctx, hilo, archivo)


@app.get("/skills", response_model=servicio_skills.Skills)
def get_skills(hilo: str = "", carpeta: str = "", ctx: Contexto = Depends(contexto)):
    """Las skills del agente de un hilo, y cuántas veces usó cada una (`telar agente skills --json`); con `carpeta`
    y sin hilo, las de un hilo nuevo ahí."""
    return servicio_skills.skills(ctx, hilo, carpeta)


# ── los procesos periódicos: aquí, o en la máquina de `[periodicos] en` por el bus ───

from telar.servicios import periodicos as servicio_periodicos


@app.get("/periodicos", response_model=servicio_periodicos.Respuesta)
def get_periodicos(ctx: Contexto = Depends(contexto)):
    """Los procesos periódicos, con su horario y su última corrida (`telar periodicos ver --json`)."""
    return servicio_periodicos.orden(ctx, ["ver"])


class PedidoPeriodicos(BaseModel):
    #: el verbo y sus argumentos, como en la CLI: ["log", "correo", "--lineas", "200"], ["pausar", "correo"]…
    argv: list[str]


@app.post("/periodicos", response_model=servicio_periodicos.Respuesta)
def post_periodicos(pedido: PedidoPeriodicos, ctx: Contexto = Depends(contexto)):
    """Un verbo de `telar periodicos` (`log`, `horario`, `skills`, `ahora`, `pausar`, `editar`…; no `correr`)."""
    return servicio_periodicos.orden(ctx, pedido.argv)


# ── la bandeja del equipo, del lado de su dueño (la página del equipo es otra app: telar.api_equipo) ──

from telar.servicios import equipo as servicio_equipo


@app.get("/equipo/bandeja", response_model=servicio_equipo.Bandeja)
def get_bandeja(todas: bool = False, maquina: str = "", ctx: Contexto = Depends(contexto)):
    """Lo que el equipo sugirió o pidió y falta decidir (`telar equipo sugerencias`); `maquina`, donde vive."""
    return servicio_equipo.bandeja(ctx, todas=todas, maquina=maquina)


class PedidoDecision(BaseModel):
    nota: str = ""
    #: con «existe»: la tarea que ya existe (T123)
    tarea: str = ""
    maquina: str = ""


@app.post("/equipo/{ident}/revisando", response_model=servicio_equipo.Sugerencia)
def post_revisando(ident: str, pedido: PedidoDecision, quien: str = "gestion", ctx: Contexto = Depends(contexto)):
    """Anotar que alguien la está revisando (`telar equipo revisando`)."""
    return servicio_equipo.revisando(ctx, ident, quien=quien, maquina=pedido.maquina)


@app.post("/equipo/{ident}/{decision}", response_model=servicio_equipo.Sugerencia)
def post_decision(ident: str, decision: str, pedido: PedidoDecision, ctx: Contexto = Depends(contexto)):
    """Aceptar, rechazar o decir que ya existe (`telar equipo aceptar|rechazar|existe`)."""
    return servicio_equipo.decidir(ctx, ident, decision, nota=pedido.nota, tarea=pedido.tarea, maquina=pedido.maquina)


# ── los hilos de las otras personas, y escribirles (telar.entre_personas) ─────────

from telar.servicios import directorio as servicio_directorio


@app.get("/directorio", response_model=servicio_directorio.Directorio)
def get_directorio(ctx: Contexto = Depends(contexto)):
    """Los hilos que publican las otras personas del bus (`telar directorio`): nombre, si vive, carpeta, una línea."""
    return servicio_directorio.ver(ctx)


class PedidoEscribir(BaseModel):
    persona: str
    #: la palabra del hilo (`ext` en el directorio)
    hilo: str
    texto: str
    asunto: str = ""


@app.post("/directorio/escribir", response_model=servicio_directorio.Escrito)
def post_directorio_escribir(pedido: PedidoEscribir, ctx: Contexto = Depends(contexto)):
    """Un mensaje a un hilo de otra persona, a su casilla (`telar correo enviar persona+hilo@…`)."""
    return servicio_directorio.escribir(ctx, pedido.persona, pedido.hilo, pedido.texto, asunto=pedido.asunto)


# ── la ficha de un agente, para la barra de la derecha (telar.servicios.agentes) ──

from telar.servicios import agentes as servicio_agentes


@app.get("/agentes", response_model=servicio_agentes.Agentes)
def get_agentes(ctx: Contexto = Depends(contexto)):
    """Todos los agentes residentes con su estado: vivo, atención, el peso de su conversación, si rota y sus
    encargos. Los de otra máquina se le piden a esa por el bus."""
    return servicio_agentes.lista(ctx)


class PedidoRotar(BaseModel):
    hilo: str
    maquina: str = ""


@app.post("/agentes/rotar")
def post_agentes_rotar(pedido: PedidoRotar, ctx: Contexto = Depends(contexto)) -> dict:
    """Rotar ya la conversación de un agente, con relevo: se le pide escribirlo, y al terminar ese turno rota."""
    return servicio_agentes.rotar(ctx, pedido.hilo, pedido.maquina)


class PedidoAgenteNuevo(BaseModel):
    nombre: str
    para: str = ""
    icono: str = ""


@app.post("/agentes/nuevo")
def post_agentes_nuevo(pedido: PedidoAgenteNuevo, ctx: Contexto = Depends(contexto)) -> dict:
    """Un agente residente nuevo, en esta máquina: su carpeta en `[agentes] carpeta` (que se configura si faltaba)."""
    return servicio_agentes.nuevo(ctx, pedido.nombre, pedido.para, pedido.icono)


@app.get("/agentes/del-hilo", response_model=servicio_agentes.FichaAgente)
def get_agente_del_hilo(hilo: str, maquina: str = "", ctx: Contexto = Depends(contexto)):
    """El agente residente del que es ese hilo: su definición, su CLAUDE.md, su último relevo y el peso de su
    conversación. 404 si el hilo no es de un agente."""
    return servicio_agentes.del_hilo(ctx, hilo, maquina=maquina)


# ── el alojamiento del servidor, para quien lo administra (telar.alojamiento) ──────────


class PedidoTopes(BaseModel):
    #: a quién (vacío: los topes con que nacen los alojados nuevos)
    persona: str = ""
    memoria: str
    cpu: str


def _alojamiento(ctx, pedido: dict) -> dict:
    from telar import alojamiento

    try:
        return alojamiento.pedir(ctx.config, pedido)
    except alojamiento.ErrorDeAlojamiento as e:
        raise ErrorDeServicio(str(e), e.codigo) from None


@app.get("/alojamiento")
def get_alojamiento(ctx: Contexto = Depends(contexto)) -> dict:
    """Los alojados del servidor, con sus topes, y los topes con que nacen los nuevos. Solo para quien lo administra:
    desde la máquina que sea, por el bus."""
    return _alojamiento(ctx, {"accion": "ver"})


@app.post("/alojamiento/topes")
def post_alojamiento_topes(pedido: PedidoTopes, ctx: Contexto = Depends(contexto)) -> dict:
    """Cambiar los topes de memoria y CPU de un alojado (se aplican ya), o los de los nuevos (sin `persona`)."""
    return _alojamiento(ctx, {"accion": "topes", "persona": pedido.persona, "memoria": pedido.memoria, "cpu": pedido.cpu})


class PedidoActualizarAlojado(BaseModel):
    persona: str
    #: vacía: la de este telar
    version: str = ""


@app.post("/alojamiento/actualizar")
def post_alojamiento_actualizar(pedido: PedidoActualizarAlojado, ctx: Contexto = Depends(contexto)) -> dict:
    """Actualizar el telar de un alojado (a la versión de este, si no se dice): corre aparte, un par de minutos;
    `GET /alojamiento` dice cuándo terminó."""
    return _alojamiento(ctx, {"accion": "actualizar", "persona": pedido.persona, "version": pedido.version})


# ── la gestión de personas del bus (telar.personas) ───────────────────────────────

from telar.servicios import personas as servicio_personas


@app.get("/personas", response_model=servicio_personas.Personas)
def get_personas(ctx: Contexto = Depends(contexto)):
    """Quién tiene cuenta en el bus y con qué rol, y quién pidió entrar (`telar bus personas|pedidos`). Solo para el
    dueño del bus y los admin."""
    return servicio_personas.ver(ctx)


class PedidoPersonas(BaseModel):
    #: con aprobar y rechazar: el id del pedido
    pedido: str = ""
    #: con quitar y rol: su nombre en el bus
    nombre: str = ""
    #: con rol: admin o miembro; con aprobar, el rol con que entra (miembro si no se dice)
    rol: str = ""


@app.post("/personas/{accion}", response_model=servicio_personas.Personas)
def post_personas(accion: str, pedido: PedidoPersonas, ctx: Contexto = Depends(contexto)):
    """Aprobar o rechazar un pedido, quitar una cuenta o cambiarle el rol (`telar bus aprobar|rechazar|quitar|rol`).
    Devuelve lo que hay después, con `hecho`."""
    return servicio_personas.hacer(ctx, accion, pedido=pedido.pedido, nombre=pedido.nombre, rol=pedido.rol)


# ── archivos de esta máquina, para la página (telar.servicios.archivos) ───────────



@app.get("/archivos", response_model=servicio_archivos.Archivo)
def get_archivo(ruta: str, maquina: str = "", ctx: Contexto = Depends(contexto)):
    """Un archivo de la raíz o de un repo de `[repos]` (o declarado por una app), hasta 2 MB. Con `maquina`
    (o una ruta `máquina:ruta`), el de otra máquina, que su nodo lee por el bus con sus propios límites."""
    return servicio_archivos.leer_en(ctx, ruta, maquina)


@app.get("/archivos/md", response_model=servicio_archivos.Hallados)
def get_archivos_md(carpeta: str, hondo: int = 3, ctx: Contexto = Depends(contexto)):
    """Los .md de una carpeta de la raíz, hasta `hondo` niveles, con su fecha."""
    return servicio_archivos.buscar_md(ctx, carpeta, min(max(hondo, 0), 5))


class PedidoArchivo(BaseModel):
    ruta: str
    texto: str


@app.get("/archivos/ver")
def get_ver(ruta: str, maquina: str = "", ctx: Contexto = Depends(contexto)):
    """Un .html para verlo dibujado (en un iframe de la página), de esta máquina o de otra (como GET /archivos).
    Va con `sandbox`: corre sus scripts en un origen propio, sin la llave de la página ni su API."""
    from fastapi.responses import HTMLResponse

    a = servicio_archivos.leer_en(ctx, ruta, maquina)
    if not a.ruta.lower().endswith((".html", ".htm")):
        raise ErrorDeServicio(f"{a.ruta}: solo un .html se ve dibujado", 415)
    return HTMLResponse(a.texto, headers={"Content-Security-Policy": "sandbox allow-scripts allow-popups",
                                          "X-Content-Type-Options": "nosniff"})


class PedidoObjeto(BaseModel):
    params: dict = {}
    #: la versión que se leyó: si el objeto cambió desde entonces, 409 y no se hace
    version: str = ""


@app.get("/objetos/tipos")
def get_objetos_tipos(ctx: Contexto = Depends(contexto)):
    """Los tipos de objeto que hay: los de fábrica y los de los módulos instalados."""
    from telar import objetos

    return {"tipos": [{"tipo": n, "descripcion": t.descripcion, "modulo": getattr(t, "modulo", "")}
                      for n, t in sorted(objetos.tipos(ctx).items())]}


@app.get("/objetos/{direccion:path}")
def get_objeto(direccion: str, ctx: Contexto = Depends(contexto)):
    """Un objeto por su dirección (`tarea:T366`, `hilo:Telar`…): sus campos, enlaces y acciones."""
    from telar import objetos

    return objetos.ver(ctx, direccion)


@app.post("/objetos/{direccion:path}/acciones/{accion}")
def post_objeto_accion(direccion: str, accion: str, pedido: PedidoObjeto, ctx: Contexto = Depends(contexto)):
    """Una acción sobre un objeto, con sus parámetros y la versión que se leyó."""
    from telar import objetos

    return objetos.hacer(ctx, direccion, accion, pedido.params, pedido.version)


# ── los módulos: los instalados, el catálogo y sus acciones (telar.servicios.modulos) ──

@app.get("/modulos")
def get_modulos(ctx: Contexto = Depends(contexto)) -> dict:
    """Los módulos instalados, activos y apagados, con de dónde vienen y si el catálogo trae una versión nueva."""
    from telar.servicios import modulos as servicio_modulos

    return servicio_modulos.instalados(ctx, con_catalogo=True).model_dump(mode="json")


@app.get("/modulos/catalogo")
def get_modulos_catalogo(forzar: bool = False, buscar: str = "", ctx: Contexto = Depends(contexto)) -> dict:
    """Lo que hay en los catálogos (el oficial, los del equipo, los de `[catalogos] fuentes`): `forzar` los baja ya."""
    from telar.servicios import modulos as servicio_modulos

    return servicio_modulos.catalogo(ctx, forzar=forzar, buscar=buscar).model_dump(mode="json")


class PedidoModulo(BaseModel):
    nombre: str


@app.post("/modulos/{accion}")
def post_modulos(accion: str, pedido: PedidoModulo, ctx: Contexto = Depends(contexto)) -> dict:
    """Instalar (solo del catálogo oficial o del equipo), actualizar, activar, desactivar o quitar un módulo."""
    from telar.servicios import modulos as servicio_modulos

    return servicio_modulos.hacer(ctx, accion, pedido.nombre).model_dump(mode="json")


@app.get("/modulos/{modulo}/{verbo}")
def get_modulo(modulo: str, verbo: str, request: Request, maquina: str = "", ctx: Contexto = Depends(contexto)):
    """Una consulta a un módulo (una orden suya con `consulta = true`): los parámetros de la dirección van
    como un objeto JSON a su entrada, y vuelve el objeto JSON que da. Con `maquina`, al de esa máquina."""
    from telar.servicios import modulos as servicio_modulos

    params = {k: v for k, v in request.query_params.items() if k != "maquina"}
    return servicio_modulos.consultar(ctx, modulo, verbo, params, maquina)


@app.get("/archivos/bajar")
def get_bajar(ruta: str, ctx: Contexto = Depends(contexto)):
    """Un archivo entero, para bajarlo (lo que la página no muestra)."""
    from fastapi.responses import FileResponse

    p = servicio_archivos.para_bajar(ctx, ruta)
    return FileResponse(p, filename=p.name)


@app.put("/archivos", response_model=servicio_archivos.Escrito)
def put_archivo(pedido: PedidoArchivo, ctx: Contexto = Depends(contexto)):
    """La memoria de un lienzo: un .json de la raíz o declarado por una app."""
    return servicio_archivos.escribir(ctx, pedido.ruta, pedido.texto)


class PedidoEntrada(BaseModel):
    #: para qué hilo (se anota); la máquina del hilo ('' o la de aquí: esta) y la ruta del archivo, en esta
    hilo: str = ""
    maquina: str = ""
    ruta: str


@app.post("/archivos/entrada", response_model=servicio_archivos.Entrada)
async def post_entrada(request: Request, ctx: Contexto = Depends(contexto)):
    """Un archivo arrastrado a un hilo, en `~/telar-entrada/` de la máquina del hilo (servicios/archivos.py). Con
    JSON `{hilo, maquina, ruta}`, un archivo de esta máquina que se copia por ssh a la del hilo; con
    multipart (`hilo`, `maquina` y `archivo`), lo que subió la página, hasta 200 MB. Responde dónde quedó."""
    from starlette.concurrency import run_in_threadpool

    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        try:
            pedido = PedidoEntrada.model_validate(await request.json())
        except ValueError as e:
            raise ErrorDeServicio("se espera {hilo, maquina, ruta} o un archivo (multipart)", 422) from e
        log.info("entrada para %s: %s → %s", pedido.hilo or "?", pedido.ruta, pedido.maquina or "aquí")
        return await run_in_threadpool(servicio_archivos.desde_ruta, ctx, pedido.maquina, pedido.ruta)
    # el tope, antes de leer nada: el cuerpo trae además los campos y los separadores, de ahí el margen
    largo = request.headers.get("content-length", "")
    if not largo.isdigit():
        raise ErrorDeServicio("falta el largo del pedido (Content-Length)", 411)
    if int(largo) > servicio_archivos.TOPE_ENTRADA + 1024 * 1024:
        raise ErrorDeServicio(f"pasa de {servicio_archivos.TOPE_ENTRADA // (1024 * 1024)} MB", 413)
    try:
        formulario = await request.form(max_files=1, max_fields=4)
    except AssertionError as e:  # starlette sin python-multipart (el extra «serve» de antes no lo traía)
        raise ErrorDeServicio("esta máquina no sabe recibir archivos: falta python-multipart "
                              "(pip install 'telar[serve]' de nuevo)", 501) from e
    try:
        archivo = formulario.get("archivo")
        if archivo is None or isinstance(archivo, str):
            raise ErrorDeServicio("¿qué archivo? (el campo «archivo»)", 422)
        maquina, hilo = str(formulario.get("maquina") or ""), str(formulario.get("hilo") or "")
        log.info("entrada para %s: %s (subido) → %s", hilo or "?", archivo.filename, maquina or "aquí")
        return await run_in_threadpool(servicio_archivos.desde_bytes, ctx, maquina, archivo.filename or "", archivo.file)
    finally:
        await formulario.close()


# ── versiones nuevas (telar.actualizar) ───────────────────────────────────────────


@app.get("/version")
def get_version(forzar: bool = False, ctx: Contexto = Depends(contexto)) -> dict:
    """Qué versión corre, cuál es la última en PyPI y si un clic la instala (`puede`). La última se pregunta a lo
    más una vez por hora; `forzar` pregunta ya."""
    from telar import actualizar

    return actualizar.ver(ctx.config, forzar=forzar)


class PedidoActualizar(BaseModel):
    #: la versión que se anunció: se instala esa exacta, y solo si es la última y más nueva que la que corre
    version: str


@app.post("/actualizar")
def post_actualizar(pedido: PedidoActualizar, ctx: Contexto = Depends(contexto)) -> dict:
    """Instalar la versión nueva y reiniciar el servicio, en un proceso aparte. Devuelve su progreso; después,
    `GET /actualizar` dice en qué va (y `/salud`, qué versión contesta)."""
    from telar import actualizar

    try:
        return actualizar.empezar(ctx.config, pedido.version)
    except actualizar.ErrorDeActualizar as e:
        raise ErrorDeServicio(str(e), 409) from e
    except (OSError, subprocess.SubprocessError) as e:
        raise ErrorDeServicio(f"no pude lanzar la actualización: {e}", 500) from e


@app.get("/actualizar")
def get_actualizar(ctx: Contexto = Depends(contexto)) -> dict:
    """En qué va la última actualización: {version, estado: corriendo|listo|fallo, desde, hasta, error, log}."""
    from telar import actualizar

    return actualizar.progreso(ctx.config)


@app.get("/salud")
def get_salud(ctx: Contexto = Depends(contexto)) -> dict:
    """Que contesta, con qué versión y quién es: la máquina (su nombre en el bus, o su hostname) y el host.
    La página lo muestra arriba, para saber en qué máquina se está (hay una página por máquina)."""
    import socket

    from telar import bus as mod_bus

    return {"ok": True, "version": __version__, "maquina": mod_bus.maquina(ctx.config), "host": socket.gethostname()}


def socket_por_defecto() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    # en una carpeta propia: `telar serve` la deja solo para su dueño (0700)
    return (Path(base) if base else Path.home() / ".local" / "state") / "telar" / "serve" / "telar.sock"
