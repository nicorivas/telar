"""Buscar sobre todo junto: lo que espera, las tareas, las casillas, los hilos, los proyectos, los objetos de cada tipo
de un módulo que sabe listarlos (los documentos de un grafo, las decisiones de un registro) y lo de cada bloque del día
(el correo, la mensajería), en una sola respuesta. Es lo que usa Todo, el modo de ver y buscar todo
(docs/propuestas/orden-por-modos.md).

    from telar.servicios import buscar
    r = buscar.buscar(ctx, "vitrina")
    r = buscar.buscar(ctx, "vitrina", fuentes=("tareas", "bloque:correo", "objeto:doc"), mundos=("trabajo",), limite=20)
    r = buscar.buscar(ctx, "vitrina", primero="personal", limite=30)   # lo de personal (y lo sin clasificar) antes del tope
    buscar.preparar(ctx)          # que empiecen a leerse, sin esperar: lo pide Todo al abrirse

Lo usan `telar buscar` (telar.ordenes.buscar) y `GET /buscar` (telar.api). La forma es la de docs/contratos.md,
«telar buscar --json».

Se busca sin tildes ni mayúsculas, y todas las palabras tienen que estar (en el título o en lo que acompaña: dónde
vive, lo que dice). Cada fuente va aparte, con cuántas calzan, y si falla lo dice sin tumbar a las demás. Dentro de
una, primero lo que lo tiene en el título, después lo vigente antes de lo que ya pasó (hecho, archivado), y lo más
nuevo antes. Con `[mundos]`, cada cosa dice el suyo: el mundo no filtra salvo que se pida (`mundos`), y Todo lo usa
para ordenar, no para esconder. Por eso `primero` (el mundo puesto en Todo) pone delante, en cada fuente, lo de ese
mundo y lo sin clasificar antes de cortar al `limite`: sin él, una fuente con mucho de un mundo (los documentos de un
repositorio grande) llena el tope y lo del otro, que también calza, no llega. No esconde nada: solo cambia qué entra.

Nunca se espera a una fuente lenta más de `tope` (TOPE, segundo y medio): cada una se lee aparte, en su propio hilo
de ejecución, y lo leído se guarda en este proceso (en `telar serve`, el índice de la página). Dentro de su vigencia
(VIGENCIA; la de un bloque, que corre un comando, VIGENCIA_BLOQUE) no se vuelve a leer: buscar letra a letra no relee
todo. Pasada, se relee: la búsqueda espera a la lectura nueva hasta el tope, salvo la de una fuente que ya se sabe
lenta (la última vez tardó más que el tope) y tiene algo guardado, que sale al tiro con lo de antes. La que no llega
sale con lo último que se leyó de ella (`leida` dice cuándo) o, si nunca se leyó, vacía y con `tarde`; sigue leyéndose
aparte, y la búsqueda siguiente la trae. Una fuente se lee de a una vez: buscar seguido no apila lecturas, y la lectura
que empezó otra búsqueda tiene su tope desde que empezó (la que ya se pasó no atrasa a las búsquedas que siguen).

La página de un bloque que ya se leyó en este proceso (su pestaña, `telar.servicios.bloques`) sirve igual: buscar no
corre de nuevo su comando.

Un tipo de objeto de un módulo que declara `listar` (telar.objetos, «Los de un tipo») es una fuente, `objeto:<tipo>`,
con su `plural` de nombre y la vigencia de un bloque (corre una consulta del módulo). Cada objeto calza por su título,
su id y su resumen, y dice dónde vive con `campos.ruta`. Si vive en un archivo, su mundo es el de esa ruta:
`campos.ruta_abs` (absoluta: la de un repositorio anidado es relativa a él, no a la raíz) o `campos.archivo` (una
dirección `archivo:<ruta>`). Con `ruta_abs`, el objeto es ese documento: va en `datos` y Todo lo abre en el visor.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio

__all__ = ["Hallado", "Fuente", "Busqueda", "buscar", "preparar", "leyendo", "olvidar", "FUENTES", "TOPE"]


class Hallado(BaseModel):
    """Una cosa que calza."""

    fuente: str
    #: su dirección de objeto (`tarea:T42`, `hilo:Faro`, `proyecto:…`, `pendiente:…`, `permiso:…`), la que abre `telar
    #: objeto`; "" si no tiene (una casilla que nadie ha escrito, la fila de un bloque)
    direccion: str = ""
    #: lo que la agarra si no tiene dirección: la `ref` de una casilla, el id de la fila de un bloque
    id: str = ""
    titulo: str
    #: dónde vive, corto: su proyecto, su documento, su carpeta, de quién viene
    donde: str = ""
    #: cuándo, si se sabe (ISO): desde cuándo espera, cuándo vence, la última actividad, la fecha de la fila
    cuando: str = ""
    #: su estado, en una palabra (activa, hecha, te espera, archivado…), o su clase
    estado: str = ""
    #: ya pasó (hecha, descartada, archivado): va después
    pasada: bool = False
    #: la parte de la vida a la que pertenece (`[mundos]`); "" si no calza en ninguna o no se declaran
    mundo: str = ""
    #: el agente residente del que es (su clave), con `[mundos]`: el de un hilo, el de una espera, o aquel en cuya
    #: carpeta vive (`mundos.agente_de_ruta`, si declara su mundo); "" si de ninguno. La página no muestra lo de un
    #: agente de otro mundo que el puesto, ni en el modo todo (donde lo demás de otro mundo va al final)
    agente: str = ""
    #: lo de su fuente que hace falta para abrirla (de un bloque: `mensaje` y `nombre`, como en su pestaña)
    datos: dict[str, Any] = Field(default_factory=dict)


class Fuente(BaseModel):
    clave: str
    nombre: str
    #: cuántas calzan; `hallados` trae hasta `limite`
    total: int = 0
    hallados: list[Hallado] = Field(default_factory=list)
    #: por qué no se pudo leer ("" si se leyó). Con `leida`, lo que trae es de una lectura anterior
    falla: str = ""
    #: no terminó de leerse dentro del tope: trae lo de la lectura anterior (`leida`) o nada, y sigue leyéndose
    tarde: bool = False
    #: cuándo se leyó lo que trae (ISO, hora local); "" si nunca se pudo leer
    leida: str = ""


class Busqueda(BaseModel):
    q: str
    fuentes: list[Fuente] = Field(default_factory=list)
    #: los mundos declarados, en su orden (vacío sin `[mundos]`)
    mundos: list[str] = Field(default_factory=list)
    #: el mundo cuyo contenido va primero en cada fuente, antes del tope ("" ninguno: lo que se pidió, si se declara)
    primero: str = ""


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if not unicodedata.combining(c)).lower()


def _corto(direccion: str) -> str:
    """`proyecto:casa/vitrina` → «vitrina», `hilo:Vitrina` → «Vitrina»."""
    return direccion.split(":", 1)[-1].rstrip("/").rsplit("/", 1)[-1] if direccion else ""


# ── cada fuente: sus candidatos, cada uno con el texto donde se busca ──

Candidato = tuple[Hallado, str]


def _esperas(ctx) -> list[Candidato]:
    from telar.servicios import esperas as servicio

    r = servicio.esperas(ctx)
    return [(Hallado(fuente="esperas", direccion=e.direccion, titulo=e.titulo or e.direccion,
                     donde=_corto(e.enlaces[0]) if e.enlaces else "", cuando=e.desde, estado=e.clase, mundo=e.mundo or "",
                     agente=e.agente or ""),
             " ".join([e.resumen, e.direccion, *e.enlaces])) for e in r.esperas]


def _tareas(ctx) -> list[Candidato]:
    from telar import mundos
    from telar.servicios import tipos

    r = tipos.lista(ctx, "tarea", todas=True)
    salida = []
    for t in r.tareas:  # TareaConVersion, aquí o traída de la máquina donde viven: `cerrada_ya` es una propiedad
        salida.append((Hallado(fuente="tareas", direccion=t.direccion, id=t.id, titulo=t.titulo, donde=_corto(t.proyecto),
                               cuando=t.vence or t.creada, estado=t.estado, pasada=t.cerrada_ya, mundo=t.mundo,
                               agente=mundos.agente_de_ruta(ctx.config, t.proyecto) if t.proyecto else ""),
                       " ".join([t.id, t.proyecto, t.area, t.contexto, t.avance, *t.etiquetas])))
    return salida


def _casillas(ctx) -> list[Candidato]:
    from telar import mundos
    from telar.servicios import pendientes

    r = pendientes.pendientes(ctx, repo=True, hechos=True)
    salida = []
    for p in r.pendientes:
        f = p.model_dump()
        salida.append((Hallado(fuente="casillas", direccion=f.get("direccion") or "", id=str(f.get("ref") or ""),
                               titulo=str(f.get("texto") or ""), donde=str(f.get("ruta") or f.get("hilo") or ""),
                               cuando=str(f.get("cuando") or ""), estado="hecha" if f.get("hecho") else "",
                               pasada=bool(f.get("hecho")), mundo=str(f.get("mundo") or ""),
                               agente=mundos.agente_de_ruta(ctx.config, str(f.get("ruta") or ""))),
                       " ".join(str(f.get(k) or "") for k in ("hilo", "ruta", "dueno"))))
    return salida


def _hilos(ctx) -> list[Candidato]:
    from telar.servicios import hilos

    r = hilos.hilos(ctx, con_ficha=False)
    # el agente de cada uno: el suyo y, si no tiene, el del hilo del que cuelga (un hijo suyo)
    padres = {h.nombre: str(getattr(h, "padre", "") or "") for h in r.hilos}
    propios = {h.nombre: str(getattr(h, "agente", "") or "") for h in r.hilos}
    agentes: dict[str, str] = {}
    for h in r.hilos:
        n, vistos = h.nombre, set()
        while n and n not in vistos and not propios.get(n):
            vistos.add(n)
            n = padres.get(n, "")
        agentes[h.nombre] = propios.get(n, "") if n else ""
    salida = []
    for h in r.hilos:
        estado = "archivado" if h.archivado else (h.atencion if h.atencion != "ninguna" else ("" if h.vivo else "cerrado"))
        salida.append((Hallado(fuente="hilos", direccion=h.direccion or f"hilo:{h.nombre}", titulo=h.nombre, donde=h.relativa,
                               cuando=h.actividad or "", estado=estado, pasada=h.archivado, mundo=h.mundo,
                               agente=agentes.get(h.nombre, "")),
                       " ".join([h.relativa, h.arquetipo, h.repo])))
    return salida


def _proyectos(ctx) -> list[Candidato]:
    from telar import mundos
    from telar.ordenes import _comun
    from telar.ordenes.proyectos import listar

    tel = _comun.tejer(ctx, con_ficha=False)
    salida = []
    for u in listar(ctx, tel):
        ruta = str(u.get("ruta") or "")
        salida.append((Hallado(fuente="proyectos", direccion=str(u.get("direccion") or f"proyecto:{ruta}"),
                               titulo=str(u.get("nombre") or ruta), donde=ruta, cuando=str(u.get("modificado") or ""),
                               estado=str(u.get("estado") or ""), mundo=mundos.de_ruta(ctx.config, ruta),
                               agente=mundos.agente_de_ruta(ctx.config, ruta)),
                       " ".join(str(u.get(k) or "") for k in ("ruta", "cliente", "area", "arquetipo"))))
    return salida


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _de_archivo(valor) -> str:
    """La ruta de una dirección `archivo:<ruta>` (o `archivo:<máquina>:<ruta>`); "" si no es una."""
    from telar import objetos

    if not _texto(valor).startswith("archivo:"):
        return ""
    try:
        ruta = objetos.leer(_texto(valor)).id
    except Exception:  # noqa: BLE001 - una dirección que no se entiende no dice dónde vive
        return ""
    m = re.match(r"[A-Za-z0-9][\w-]*:(?!//)(.+)", ruta)
    return m.group(1) if m else ruta


def _objetos(ctx, tipo: str) -> list[Candidato]:
    """Los objetos de un tipo de un módulo, de su consulta `listar` (telar.objetos.DeModulo.listar). Si no trae
    ninguno y dice por qué (sus `fallas`), es una falla; si trae algunos, lo que no pudo leer queda en su `--listar`."""
    from telar import mundos, objetos

    t = objetos.tipos(ctx).get(tipo)
    if t is None or not t.lista:
        raise ErrorDeServicio(f"el tipo «{tipo}» ya no lista los suyos", 404)
    r = t.listar(ctx)
    if not r.objetos and r.fallas:
        raise ErrorDeServicio("; ".join(r.fallas[:3]), 502)
    salida = []
    for o in r.objetos:
        campos = o.campos if isinstance(o.campos, dict) else {}
        ruta_abs = _texto(campos.get("ruta_abs"))
        ruta_abs = ruta_abs if os.path.isabs(ruta_abs) else ""
        lugar = ruta_abs or _de_archivo(campos.get("archivo"))
        salida.append((Hallado(fuente=f"objeto:{tipo}", direccion=o.direccion, id=o.id, titulo=o.titulo or o.id,
                               donde=_texto(campos.get("ruta")), estado=o.estado,
                               mundo=mundos.de_ruta(ctx.config, lugar) if lugar else "",
                               agente=mundos.agente_de_ruta(ctx.config, lugar) if lugar else "",
                               datos={"ruta_abs": ruta_abs} if ruta_abs else {}),
                       f"{o.id} {o.resumen}"))
    return salida


def _de_modulos(ctx) -> list[tuple[str, str]]:
    """(tipo, su nombre en plural) de cada tipo de objeto de un módulo que sabe listar los suyos, en su orden."""
    from telar import objetos

    if not getattr(ctx.config, "modulos", ()):
        return []
    return [(nombre, getattr(t, "plural", "") or nombre) for nombre, t in objetos.tipos(ctx).items()
            if isinstance(t, objetos.DeModulo) and t.lista]


def _filas(clave: str, pagina) -> list[Candidato]:
    """Las filas de la página de un bloque que tienen título, como candidatos."""
    salida = []
    for b in pagina.bloques:
        for i in b.get("items") or []:
            if not isinstance(i, dict) or not str(i.get("titulo") or "").strip():
                continue
            datos = {k: i[k] for k in ("mensaje", "nombre") if isinstance(i.get(k), str) and i[k]}
            salida.append((Hallado(fuente=f"bloque:{clave}", id=str(i.get("id") or ""), titulo=str(i["titulo"]),
                                   donde=str(i.get("texto") or ""), cuando=str(i.get("fecha") or ""),
                                   pasada=i.get("marca") == "✓", datos={"bloque": clave, **datos}),
                           str(b.get("titulo") or "")))
    return salida


def _bloque(ctx, clave: str) -> list[Candidato]:
    """Corre el comando del bloque (telar.servicios.bloques, que guarda la página para su pestaña y para aquí)."""
    from telar.servicios import bloques

    return _filas(clave, bloques.pagina(ctx, clave))


def _bloque_guardado(ctx, clave: str) -> tuple[float, list[Candidato]] | None:
    """La página del bloque que ya se leyó en este proceso (la abrió su pestaña, o una búsqueda), sin correr nada."""
    from telar.servicios import bloques

    guardada = bloques.guardada(ctx, clave)
    return (guardada[0], _filas(clave, guardada[1])) if guardada else None


@dataclass(frozen=True)
class _Fuente:
    clave: str
    nombre: str
    #: lee sus candidatos (puede tardar: corre en su propio hilo de ejecución)
    dar: Callable[[Any], list[Candidato]]
    #: cuánto vale lo leído
    vigencia: float
    #: lo que ya se leyó por otro lado, sin leer nada: (cuándo, en time.monotonic; candidatos), o None
    guardado: Callable[[Any], tuple[float, list[Candidato]] | None] | None = None


def _fuentes(ctx) -> list[_Fuente]:
    """Las fuentes, en el orden en que se muestran: lo que espera, lo propio, lo de los agentes, lo de los módulos y lo
    de afuera."""
    # las tareas, solo si esta máquina dice dónde viven (`[tipos.tarea]`): si no, no son una fuente que falla
    hay_tareas = any(t.clave == "tarea" for t in getattr(ctx.config, "tipos", ()) or ())
    fijas = [_Fuente("esperas", "te esperan", _esperas, VIGENCIA),
             *([_Fuente("tareas", "tareas", _tareas, VIGENCIA)] if hay_tareas else []),
             _Fuente("casillas", "casillas", _casillas, VIGENCIA), _Fuente("hilos", "hilos", _hilos, VIGENCIA),
             _Fuente("proyectos", "proyectos", _proyectos, VIGENCIA)]
    # cada tipo de objeto de un módulo que sabe listar: corre una consulta suya, como un bloque su comando
    de_modulos = [_Fuente(f"objeto:{tipo}", plural, lambda c, t=tipo: _objetos(c, t), VIGENCIA_BLOQUE)
                  for tipo, plural in _de_modulos(ctx)]
    de_bloques = [_Fuente(f"bloque:{b.clave}", b.nombre or b.clave, lambda c, k=b.clave: _bloque(c, k), VIGENCIA_BLOQUE,
                          lambda c, k=b.clave: _bloque_guardado(c, k))
                  for b in getattr(ctx.config, "bloques", ()) or ()]
    return fijas + de_modulos + de_bloques


#: las claves de las fuentes fijas (los bloques se piden como `bloque:<clave>`; los tipos de un módulo, `objeto:<tipo>`)
FUENTES = ("esperas", "tareas", "casillas", "hilos", "proyectos")

#: cuánto espera una búsqueda a sus fuentes, en segundos: la que no llega sale con lo de antes, o vacía y `tarde`
TOPE = 1.5
#: cuánto vale lo leído de una fuente: dentro de esto, buscar no la relee
VIGENCIA = 30.0
#: lo de un bloque, que corre un comando (y lo de un tipo de un módulo, que corre una consulta suya)
VIGENCIA_BLOQUE = 120.0


# ── lo leído, guardado en este proceso: una lectura por fuente a la vez ──

#: un candidato con su título y lo demás ya sin tildes ni mayúsculas: se normaliza al leer, no en cada búsqueda
_Indexado = tuple[Hallado, str, str]


@dataclass
class _Lectura:
    """Lo último que se leyó de una fuente, y la lectura en curso si la hay. Se toca con `_CERROJO`."""

    #: lo leído; None si nunca se pudo leer
    candidatos: list[_Indexado] | None = None
    #: cuándo se leyó (time.monotonic) y su hora, para decirla
    leida: float = 0.0
    hora: str = ""
    #: cuándo terminó la última lectura, buena o no (time.monotonic): con la vigencia, si toca releer
    revisada: float | None = None
    #: cuánto tardó la última lectura: una fuente lenta con algo guardado no se espera
    duracion: float = 0.0
    #: por qué falló la última lectura ("" si salió bien)
    falla: str = ""
    #: la lectura en curso: se marca al terminar; y cuándo empezó (time.monotonic)
    en_curso: threading.Event | None = None
    desde: float = 0.0


_LECTURAS: dict[tuple[str, str, str], _Lectura] = {}
_CERROJO = threading.Lock()


def leyendo() -> bool:
    """Si alguna fuente se está leyendo todavía en este proceso."""
    with _CERROJO:
        return any(x.en_curso is not None for x in _LECTURAS.values())


def olvidar() -> None:
    """Olvida todo lo leído (las lecturas en curso terminan, pero lo suyo ya no se guarda)."""
    with _CERROJO:
        _LECTURAS.clear()


def _llave(ctx, clave: str) -> tuple[str, str, str]:
    return (str(getattr(ctx.config, "origen", "") or ""), str(getattr(ctx.config, "raiz", "") or ""), clave)


def _indexar(candidatos: list[Candidato]) -> list[_Indexado]:
    return [(h, _norm(h.titulo), _norm(f"{h.donde} {resto}")) for h, resto in candidatos]


def _motivo(e: Exception) -> str:
    return (str(e) if isinstance(e, ErrorDeServicio) else f"{type(e).__name__}: {e}")[:300]


def _leer(ctx, f: _Fuente, lectura: _Lectura, listo: threading.Event) -> None:
    """Lee una fuente y guarda lo leído en su `_Lectura` (si no se olvidó mientras). Corre en su propio hilo."""
    inicio = time.monotonic()
    try:
        candidatos, falla = _indexar(f.dar(ctx)), ""
    except Exception as e:  # noqa: BLE001 - una fuente que falla se dice; las demás siguen
        candidatos, falla = None, _motivo(e)
    fin = time.monotonic()
    with _CERROJO:
        if candidatos is not None:
            lectura.candidatos, lectura.leida, lectura.hora = candidatos, fin, _ahora()
        lectura.revisada, lectura.duracion, lectura.falla, lectura.en_curso = fin, fin - inicio, falla, None
    listo.set()


def _ahora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _hora_de(momento: float) -> str:
    """La hora local de un momento de time.monotonic."""
    return (dt.datetime.now() - dt.timedelta(seconds=max(0.0, time.monotonic() - momento))).isoformat(timespec="seconds")


def _pedir(ctx, f: _Fuente, ahora: float, releer: bool) -> tuple[_Lectura, threading.Event | None]:
    """La lectura de una fuente, y lo que hay que esperar de ella: la lectura en curso, una nueva si lo guardado ya no
    vale (o `releer`), o nada si vale. Se llama con `_CERROJO` tomado."""
    lectura = _LECTURAS.setdefault(_llave(ctx, f.clave), _Lectura())
    if f.guardado is not None and lectura.en_curso is None:
        # lo que ya se leyó por otro lado (la pestaña de un bloque), si es más nuevo que lo de aquí
        try:
            otro = f.guardado(ctx)
        except Exception:  # noqa: BLE001 - sin eso, se lee como siempre
            otro = None
        if otro is not None and otro[0] > max(lectura.leida, lectura.revisada or 0.0):
            lectura.candidatos, lectura.leida, lectura.hora = _indexar(otro[1]), otro[0], _hora_de(otro[0])
            lectura.revisada, lectura.falla = otro[0], ""
    if lectura.en_curso is not None:
        return lectura, lectura.en_curso
    if not releer and lectura.revisada is not None and ahora - lectura.revisada < f.vigencia:
        return lectura, None
    listo = lectura.en_curso = threading.Event()
    lectura.desde = ahora
    # un hilo de ejecución suelto (daemon), no un pool: una orden que termina no espera a la fuente lenta
    threading.Thread(target=_leer, args=(ctx, f, lectura, listo), name=f"buscar {f.clave}", daemon=True).start()
    return lectura, listo


def preparar(ctx) -> list[str]:
    """Empieza a leer las fuentes cuyo guardado ya no vale, sin esperar a ninguna: Todo lo pide al abrirse, y mientras
    se escribe, se lee. Las claves de las que se están leyendo."""
    ahora = time.monotonic()
    with _CERROJO:
        pedidos = [(f.clave, _pedir(ctx, f, ahora, False)[1]) for f in _fuentes(ctx)]
    return [clave for clave, listo in pedidos if listo is not None]


def _calza(palabras: list[str], titulo: str, resto: str) -> int | None:
    """Cuánto calza (título y resto ya normalizados): 0 si todas las palabras están en el título, 1 si están entre el
    título y lo demás; None si no."""
    if all(p in titulo for p in palabras):
        return 0
    if all(p in titulo or p in resto for p in palabras):
        return 1
    return None


def _segundos(s: float) -> str:
    return f"{s:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def buscar(ctx, q: str, *, fuentes: tuple[str, ...] = (), mundos: tuple[str, ...] = (), limite: int = 50,
           tope: float = TOPE, releer: bool = False, primero: str = "", si_hay: bool = False) -> Busqueda:
    """Lo que calza con `q` en cada fuente (o solo en `fuentes`), y en los mundos pedidos (todos, si ninguno). No tarda
    más que `tope` (segundos) en total; `releer` lee todas de nuevo aunque lo guardado valga. Con `primero` (un mundo),
    en cada fuente va antes lo de ese mundo y lo sin clasificar, y después lo de los otros, y recién ahí se corta al
    `limite`; un mundo que no se declara no ordena nada (la página puede traer uno de antes de cambiar `[mundos]`).
    Una fuente pedida que aquí no hay es un error (404); con `si_hay`, se deja fuera sin más (⌘K pide sus tres de una
    vez, y una máquina puede no tener tareas, o ningún módulo que liste documentos)."""
    from telar import mundos as mod_mundos

    q = " ".join(str(q or "").split())
    palabras = [p for p in _norm(q).split() if p]
    if not palabras or len(q) < 2:
        raise ErrorDeServicio("¿qué busco? (dos letras o más)", 422)
    filtro = mod_mundos.pedidos(ctx.config, mundos)
    primero = str(primero or "").strip()
    primero = primero if primero in mod_mundos.declarados(ctx.config) else ""
    todas = _fuentes(ctx)
    pedidas = [f for f in todas if not fuentes or f.clave in fuentes]
    if fuentes and not si_hay:
        raras = [f for f in fuentes if f not in {x.clave for x in todas}]
        if raras:
            raise ErrorDeServicio(f"no hay una fuente «{raras[0]}»: {', '.join(x.clave for x in todas)}", 404)

    # cada fuente lee lo suyo (los hilos, los documentos, un comando, otra máquina), a la par y cada una en lo suyo
    inicio = time.monotonic()
    tope = max(0.0, float(tope))
    with _CERROJO:
        pedidos = [(f, *_pedir(ctx, f, inicio, releer)) for f in pedidas]
    for f, lectura, listo in pedidos:
        # la que ya se sabe lenta y tiene algo guardado no se espera: sale con eso, y se relee aparte
        if listo is None or not (releer or lectura.candidatos is None or lectura.duracion <= tope):
            continue
        # una lectura que empezó otra búsqueda (la letra anterior) tiene el tope desde que empezó, no uno más: la que
        # ya se pasó no atrasa a esta
        listo.wait(max(0.0, min(inicio, lectura.desde) + tope - time.monotonic()))

    resultado = []
    for f, lectura, _listo in pedidos:
        with _CERROJO:
            candidatos, hora, falla, tarde = lectura.candidatos, lectura.hora, lectura.falla, lectura.en_curso is not None
        if candidatos is None:
            if tarde:
                falla = f"tardó más de {_segundos(tope)} s: sigue leyéndose, y la próxima búsqueda la trae"
            resultado.append(Fuente(clave=f.clave, nombre=f.nombre, falla=falla, tarde=tarde))
            continue
        hallados = []
        for h, titulo, resto in candidatos:
            cuanto = _calza(palabras, titulo, resto)
            if cuanto is not None and mod_mundos.calza(h.mundo, filtro):
                hallados.append((cuanto, h))
        # lo que lo tiene en el título, lo vigente, lo más nuevo; con `primero`, antes que todo lo de ese mundo (y lo sin
        # clasificar, que se ve en todos): el tope no lo deja afuera por lo de los otros
        hallados.sort(key=lambda x: x[1].cuando or "", reverse=True)
        hallados.sort(key=lambda x: (bool(primero) and x[1].mundo not in (primero, ""), x[0], x[1].pasada))
        resultado.append(Fuente(clave=f.clave, nombre=f.nombre, total=len(hallados), falla=falla, tarde=tarde, leida=hora,
                                hallados=[h for _, h in hallados[:max(0, limite) or None]]))
    return Busqueda(q=q, fuentes=resultado, mundos=list(mod_mundos.declarados(ctx.config)), primero=primero)
