"""Las tareas que te tocan: de dónde salen, cuáles urgen, y a qué hilo van.

Este módulo tiene dos mitades, y conviene no confundirlas:

  * **el núcleo** (`urgencia`, `urgentes`, `hilo_de_tarea`, `etiqueta_calza`): qué
    tarea pide la mano primero y en qué hilo se trabaja. No depende de dónde
    salieron las tareas y sirve igual para las tres implementaciones;
  * **las implementaciones** (`markdown`, `comando`, `ninguno`): de dónde salen.

La pieza común es `Tarea`. Cumple el protocolo `Fuente` de `telar.proveedores`
—`consultar(dia) -> list[Item]`— y además ofrece `activas(dia) -> list[Tarea]`,
que es lo mismo sin perder la prioridad, la fecha ni a quién espera.

Ninguna implementación sale de red. `markdown` lee archivos de la máquina;
`comando` corre el programa que la configuración le diga, y nada más.

Cómo se enciende, en `~/.config/telar/config.toml`:

    [proveedores.tareas]
    tipo  = "markdown"                  # markdown | comando | ninguno
    raiz  = "~/trabajo"                 # por defecto, $TELAR_RAIZ o el directorio actual
    rutas = ["proyectos/*/README.md"]   # globs relativos a `raiz`
    encabezado = '^##\\s+Pendientes'    # opcional: solo esa sección del documento

    [proveedores.tareas]
    tipo    = "comando"
    comando = ["mis-tareas", "--json", "--dia", "{dia}"]

Importar este módulo lo deja disponible en `telar.proveedores.REGISTRO`; que se
consulte o no lo sigue decidiendo la configuración.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator, Protocol, runtime_checkable

from telar import proveedores
from telar.config import Proveedor as ConfigProveedor
from telar.modelo import Hilo, Item, Pendiente, Prioridad
from telar.proveedores import ErrorDeProveedor

__all__ = [
    "NOMBRE",
    "Tarea",
    "FuenteDeTareas",
    "NIVELES",
    "SIN_PRIORIDAD",
    "nivel",
    "urgencia",
    "urgentes",
    "GENERICAS",
    "etiqueta_calza",
    "hilo_de_tarea",
    "IMPLEMENTACIONES",
    "construir",
    "registrar",
]

#: Cómo se llama en la configuración: `[proveedores.tareas]`.
NOMBRE = "tareas"


# ── la pieza común ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Tarea:
    """Una tarea activa, venga de donde venga.

    `espera` es a quién le toca ahora si no es a ti ("@quien", "legal"): una tarea
    que espera a otro sigue viva pero no entra en lo urgente, porque no depende de
    ti. `origen` es de dónde salió —la ruta del documento, el nombre del programa—
    y es lo que permite enrutarla al hilo correcto sin adivinar.
    """

    id: str
    texto: str
    prioridad: Prioridad | None = None
    vence: date | None = None
    etiquetas: tuple[str, ...] = ()
    enlace: str = ""
    espera: str = ""
    hecha: bool = False
    en_curso: bool = False
    origen: str = ""
    #: lo último que dejó un agente que la trabajó solo («preparado 2026-09-25»): el estado y
    #: la fecha. telar no lo interpreta; lo muestra.
    avance: str = ""
    #: a qué parte de la vida pertenece («trabajo», «personal»): el dashboard filtra por aquí
    area: str = ""
    #: el color de la palabra de `avance` (azul, verde, rojo…); vacío, el de fábrica
    #: quién la hace, si no es la persona («Nataly»); vacío es suya. El dashboard filtra «mías / de otros».
    dueno: str = ""
    color: str = ""
    #: el proveedor la destaca (la más alta prioridad, o marcada): va siempre en la vista corta
    destacada: bool = False
    #: la persona la marcó con estrella
    estrella: bool = False

    @property
    def activa(self) -> bool:
        return not self.hecha

    @property
    def tuya(self) -> bool:
        """Activa y sin esperar a nadie: depende de ti y de nadie más."""
        return not self.hecha and not self.espera

    def item(self, *, proveedor: str = NOMBRE, hilo: str = "") -> Item:
        """La misma tarea en la moneda de `telar.proveedores`."""
        return Item(
            proveedor=proveedor,
            id=self.id,
            titulo=self.texto,
            cuando=datetime.combine(self.vence, time.min) if self.vence else None,
            clase="tarea",
            hilo=hilo,
            url=self.enlace,
            datos={
                "prioridad": self.prioridad.value if self.prioridad else None,
                "etiquetas": list(self.etiquetas),
                "espera": self.espera,
                "hecha": self.hecha,
                "en_curso": self.en_curso,
                "origen": self.origen,
                "avance": self.avance,
                "area": self.area,
                "color": self.color,
                "dueno": self.dueno,
                "destacada": self.destacada,
                "estrella": self.estrella,
            },
        )

    def pendiente(self) -> Pendiente:
        """La misma tarea como viñeta de una ficha."""
        return Pendiente(
            texto=self.texto,
            hecho=self.hecha,
            en_curso=self.en_curso,
            id=self.id,
            origen=self.origen,
        )


@runtime_checkable
class FuenteDeTareas(Protocol):
    """Un proveedor de tareas: `Fuente` más la vista que no pierde los campos."""

    nombre: str
    alcance: str

    def activas(self, dia: date) -> list[Tarea]:
        """Las tareas vivas ese día. Solo lee."""
        ...

    def consultar(self, dia: date) -> list[Item]:
        ...


# ── el núcleo: qué urge ─────────────────────────────────────────────────────────

#: Prioridad → cuánto suma al peso. El nivel es una distancia desde lo más urgente,
#: no el número de la prioridad: así `Prioridad.ALTA` no paga nada.
NIVELES: dict[Prioridad, int] = {Prioridad.ALTA: 0, Prioridad.MEDIA: 1, Prioridad.BAJA: 2}

#: Lo que suma una tarea sin prioridad declarada: una más que la más baja.
SIN_PRIORIDAD = 3


def nivel(prioridad: Prioridad | None) -> int:
    return NIVELES[prioridad] if prioridad is not None else SIN_PRIORIDAD


def _orden_id(id: str) -> tuple[int, str]:
    """Clave de desempate estable: el número del id si lo tiene, y el id."""
    m = re.search(r"\d+", id or "")
    return (int(m.group()) if m else 0, id or "")


def urgencia(tarea: Tarea, hoy: date) -> tuple[int, str, tuple[int, str]]:
    """Días que faltan, con lo vencido contando como hoy, más 2 por nivel de prioridad.

    Una tarea sin fecha cuenta como si venciera hoy, así que una de prioridad alta
    sin fecha pesa 0 y va arriba. La suma mezcla plazo y prioridad a propósito: una
    tarea media que vence mañana (1 + 2 = 3) le gana a una baja vencida (0 + 4 = 4)
    y a una alta que vence en cuatro días (4 + 0 = 4).

    La lección que lo justifica: ordenar primero por prioridad y después por fecha
    dejaba fuera de una lista corta lo que vencía mañana, y una tarea de prioridad
    alta sin fecha no entraba nunca.

    Menor es más urgente: se usa como `key` de `sorted`.
    """
    dias = max((tarea.vence - hoy).days, 0) if tarea.vence else 0
    fecha = tarea.vence.isoformat() if tarea.vence else hoy.isoformat()
    return (dias + 2 * nivel(tarea.prioridad), fecha, _orden_id(tarea.id))


def urgentes(tareas: Iterable[Tarea], hoy: date, *, dias: int = 7) -> list[Tarea]:
    """Las que piden la mano ahora, ya ordenadas por urgencia.

    Entran las vencidas, las que vencen dentro de `dias`, y las de prioridad alta
    sin fecha. No entran las que esperan a otro: siguen vivas, pero no dependen
    de ti, y llenar la lista con ellas es la forma más rápida de que nadie la mire.
    """
    limite = hoy + timedelta(days=dias)
    candidatas = (
        t
        for t in tareas
        if t.tuya and ((t.vence and t.vence <= limite) or (t.prioridad is Prioridad.ALTA and not t.vence))
    )
    return sorted(candidatas, key=lambda t: urgencia(t, hoy))


# ── el núcleo: a qué hilo va ────────────────────────────────────────────────────
#
# Abrir un hilo nuevo por cada tarea deja dos agentes trabajando sobre la misma
# carpeta sin saber el uno del otro. La tarea casi siempre sabe de qué unidad es:
# salió de un documento que vive ahí, o trae una etiqueta que la nombra. Esto lo
# lee y devuelve el hilo donde se trabaja; abrir uno nuevo es la última opción.

#: Palabras que aparecen en nombres de hilo o como etiqueta sin decir de qué unidad
#: se trata. Cada repositorio tiene las suyas: se pasan por parámetro.
GENERICAS = frozenset(
    {"proyecto", "proyectos", "cliente", "clientes", "tarea", "tareas",
     "nota", "notas", "pendiente", "pendientes", "general", "varios"}
)

_EPOCA = 0.0


def _norm(texto: str) -> str:
    return re.sub(r"[^0-9a-záéíóúñü]", "", texto.lower())


def etiqueta_calza(etiqueta: str, nombre: str, rel: str, *, genericas: Iterable[str] = GENERICAS) -> int:
    """Cuánto calza una etiqueta con un hilo: 2 exacto, 1 parcial, 0 nada.

    2 si la etiqueta **es** el hilo (`#faro` ↔ un hilo «faro», `#faronorte` ↔ la
    carpeta `faro-norte`); 1 si es el comienzo de su carpeta (`#molino` ↔
    `molino-de-viento`) o una palabra propia de su nombre (`#molino` ↔ «Proyecto
    Molino»); 0 si no.

    Lo que no calza, a propósito: `#faro-norte` con `faro` (es más específica que
    el hilo, no menos) y `#faro` con `puerto-faro` (calza el final, no el comienzo).
    Una palabra de `genericas` no calza a medias con nadie, porque nombra a todos y
    por eso a ninguno; si alguien llamó a su hilo exactamente así, el calce exacto
    manda igual.
    """
    base = PurePosixPath(str(rel).strip("/")).name.lower()
    tag = etiqueta.lower().lstrip("#")
    partes_tag, partes_base = tag.split("-"), base.split("-")

    if _norm(tag) in (_norm(nombre), _norm(base)):
        return 2
    if _norm(tag) in {_norm(g) for g in genericas}:
        return 0
    if len(partes_tag) < len(partes_base) and partes_base[: len(partes_tag)] == partes_tag:
        return 1
    if "-" not in tag and len(tag) >= 4 and tag in {_norm(p) for p in re.findall(r"\w+", nombre)}:
        return 1
    return 0


def _relativa(ruta: Path, raiz: Path | None) -> str:
    p = Path(ruta)
    if raiz is not None:
        try:
            p = p.relative_to(Path(raiz))
        except ValueError:
            pass
    return p.as_posix().strip("/")


def hilo_de_tarea(
    tarea: Tarea,
    hilos: Iterable[Hilo],
    *,
    raiz: Path | None = None,
    incluir_archivados: bool = False,
    profundidad_minima: int = 0,
    genericas: Iterable[str] = GENERICAS,
) -> Hilo | None:
    """El hilo donde se trabaja esta tarea, o None si ninguno le corresponde.

    En orden: el hilo que ya es de la tarea (su id aparece en el nombre); si no, el
    hilo cuya carpeta aparece en el texto, el enlace o el origen de la tarea, y
    gana la más específica; si no, aquel con el que calce una etiqueta. Los
    empates se rompen por el hilo que ya tiene un agente, el que no está
    archivado, el de foco más reciente y el nombre.

    `raiz` es contra qué se relativizan las rutas de los hilos; sin ella, una ruta
    absoluta rara vez va a aparecer en el texto y solo quedan las etiquetas.
    `profundidad_minima` descarta los hilos vinculados a carpetas contenedoras: con
    1, una carpeta de primer nivel no compite con los proyectos que tiene adentro.
    """
    candidatos = [h for h in hilos if incluir_archivados or not h.archivado]

    if tarea.id:
        propio = re.compile(rf"(?:^|[^\w-]){re.escape(tarea.id)}(?![\w-])")
        for h in candidatos:
            if propio.search(h.nombre):
                return h

    texto = " ".join(x for x in (tarea.texto, tarea.enlace, tarea.origen) if x)
    mejor: tuple[tuple, Hilo] | None = None
    for h in candidatos:
        if h.ruta is None:
            continue
        rel = _relativa(h.ruta, raiz)
        if not rel or rel == ".":
            continue
        if rel.count("/") < profundidad_minima:
            continue
        dicha = re.search(rf"(?<![\w/.-]){re.escape(rel)}(?=[/\s)]|$)", texto)
        tag = max((etiqueta_calza(e, h.nombre, rel, genericas=genericas) for e in tarea.etiquetas), default=0)
        if not (dicha or tag):
            continue
        clave = (
            len(rel) if dicha else 0,
            tag,
            bool(h.sesiones),
            not h.archivado,
            h.visto.timestamp() if h.visto else _EPOCA,
            h.nombre,
        )
        if mejor is None or clave > mejor[0]:
            mejor = (clave, h)
    return mejor[1] if mejor else None


# ── lo común a las tres implementaciones ────────────────────────────────────────

class _Base:
    """`consultar` sale de `activas`: una implementación solo escribe `activas`."""

    nombre = NOMBRE
    alcance = ""

    def activas(self, dia: date) -> list[Tarea]:  # pragma: no cover - lo cumple cada una
        raise NotImplementedError

    def consultar(self, dia: date) -> list[Item]:
        return [t.item(proveedor=self.nombre) for t in self.activas(dia)]


def _derivar_id(origen: str, texto: str) -> str:
    """Un id estable para una tarea que no trae uno propio.

    Sale del origen y del texto, así que sobrevive a que la tarea cambie de lugar
    en el archivo pero no a que se reescriba. Un id puesto a mano sobrevive a las
    dos cosas; por eso conviene escribirlo cuando la tarea va a durar.
    """
    huella = hashlib.sha1(f"{origen}\n{texto}".encode("utf-8")).hexdigest()[:8]
    return f"auto-{huella}"


def _prioridad(valor: object, contexto: str) -> Prioridad | None:
    """Acepta "alta"/"media"/"baja" o 1/2/3; nada más."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, str):
        nombres = {"alta": Prioridad.ALTA, "media": Prioridad.MEDIA, "baja": Prioridad.BAJA}
        clave = valor.strip().lower()
        if clave in nombres:
            return nombres[clave]
        raise ErrorDeProveedor(f"{contexto}: {valor!r} no es alta, media ni baja")
    if isinstance(valor, int) and not isinstance(valor, bool):
        try:
            return Prioridad(valor)
        except ValueError as e:
            raise ErrorDeProveedor(f"{contexto}: {valor!r} no es 1, 2 ni 3") from e
    raise ErrorDeProveedor(f"{contexto}: se esperaba una prioridad, llegó {valor!r}")


def _fecha(valor: object, contexto: str) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor[:10])
        except ValueError as e:
            raise ErrorDeProveedor(f"{contexto}: {valor!r} no es una fecha AAAA-MM-DD") from e
    raise ErrorDeProveedor(f"{contexto}: se esperaba una fecha, llegó {valor!r}")


# ── markdown: las casillas de los documentos ────────────────────────────────────
#
# La sintaxis es la de cualquier lista de casillas, más unos pocos tokens que se
# pueden escribir o no. Todo lo que no se reconoce se queda en el texto: nadie
# tiene que aprender un formato para que su documento se lea.
#
#   - [ ] Medir el alcance real  vence:2026-06-30  !alta  #faro  <!-- id: T84 -->
#   - [>] Ajustar el giro  espera:@electricista
#   - [x] Desmontar la lámpara vieja

CASILLA = re.compile(r"^\s*[-*+]\s+\[(.)\]\s+(.*)$")
ENCABEZADO = re.compile(r"^(#{1,6})\s+")
ID_HTML = re.compile(r"<!--\s*id:\s*([^\s<>]+?)\s*-->", re.IGNORECASE)
VENCE = re.compile(r"(?<![\w-])vence:(\d{4}-\d{2}-\d{2})(?![\w-])")
ESPERA = re.compile(r"(?<![\w-])espera:(@?[^\s·]+)")
NIVEL_TXT = re.compile(r"(?<![\w-])!(alta|media|baja)(?![\w-])", re.IGNORECASE)
ETIQUETA = re.compile(r"(?<![\w&#])#([A-Za-zÀ-ɏ][\wÀ-ɏ-]*)")
ENLACE_MD = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")

#: Casillas que siguen vivas. Cualquier otra marca —`[x]`, `[~]`, `[-]`— es cerrada.
ABIERTAS = {" ": False, ">": True}


def _limpiar(texto: str) -> str:
    """Junta los espacios que dejaron los tokens y saca los separadores sueltos."""
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto.strip(" ·-—|").strip()


def _tarea_de_linea(marca: str, cuerpo: str, origen: str) -> Tarea:
    id = ""
    if m := ID_HTML.search(cuerpo):
        id, cuerpo = m.group(1), cuerpo[: m.start()] + cuerpo[m.end() :]
    cuerpo = re.sub(r"<!--.*?-->", " ", cuerpo, flags=re.DOTALL)

    vence = None
    if m := VENCE.search(cuerpo):
        vence = date.fromisoformat(m.group(1))
        cuerpo = cuerpo[: m.start()] + cuerpo[m.end() :]

    espera = ""
    if m := ESPERA.search(cuerpo):
        espera = m.group(1)
        cuerpo = cuerpo[: m.start()] + cuerpo[m.end() :]

    prioridad = None
    if m := NIVEL_TXT.search(cuerpo):
        prioridad = {"alta": Prioridad.ALTA, "media": Prioridad.MEDIA, "baja": Prioridad.BAJA}[
            m.group(1).lower()
        ]
        cuerpo = cuerpo[: m.start()] + cuerpo[m.end() :]

    enlace = ""
    if m := ENLACE_MD.search(cuerpo):
        enlace = m.group(2)
        cuerpo = cuerpo[: m.start()] + m.group(1) + cuerpo[m.end() :]

    etiquetas = tuple(e.lower() for e in ETIQUETA.findall(cuerpo))
    cuerpo = ETIQUETA.sub(" ", cuerpo)

    texto = _limpiar(cuerpo)
    return Tarea(
        id=id or _derivar_id(origen, texto),
        texto=texto,
        prioridad=prioridad,
        vence=vence,
        etiquetas=etiquetas,
        enlace=enlace,
        espera=espera,
        hecha=marca not in ABIERTAS,
        en_curso=ABIERTAS.get(marca, False),
        origen=origen,
    )


def leer_markdown(texto: str, origen: str = "", *, encabezado: re.Pattern[str] | None = None) -> list[Tarea]:
    """Las tareas de un documento, en el orden en que están escritas.

    Con `encabezado`, solo las de esa sección: se empieza a leer en el encabezado
    que calce y se para en el siguiente del mismo nivel o más alto.
    """
    salida: list[Tarea] = []
    dentro = encabezado is None
    nivel_seccion = 0

    for linea in texto.splitlines():
        if enc := ENCABEZADO.match(linea):
            profundidad = len(enc.group(1))
            if encabezado is not None:
                if encabezado.search(linea):
                    dentro, nivel_seccion = True, profundidad
                elif dentro and profundidad <= nivel_seccion:
                    dentro = False
            continue
        if not dentro:
            continue
        if m := CASILLA.match(linea):
            salida.append(_tarea_de_linea(m.group(1), m.group(2), origen))
    return salida


class DeMarkdown(_Base):
    """Las listas de casillas que ya están escritas en los documentos del trabajo.

    No escribe nada: el documento es la fuente, y se corrige en el documento.
    """

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        opciones = cfg.opciones
        self.raiz = _raiz(opciones.get("raiz"), f"proveedores.{cfg.nombre}.raiz")
        self.rutas = _globs(opciones.get("rutas", ["*/README.md"]), f"proveedores.{cfg.nombre}.rutas")
        cabecera = opciones.get("encabezado")
        if cabecera is not None and not isinstance(cabecera, str):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.encabezado: se esperaba una expresión regular")
        try:
            self.encabezado = re.compile(cabecera) if cabecera else None
        except re.error as e:
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.encabezado: expresión inválida: {e}") from e
        donde = ", ".join(self.rutas)
        self.alcance = f"lee las listas de casillas de {donde} bajo {self.raiz}; no sale de la máquina"

    def documentos(self) -> Iterator[Path]:
        vistos: set[Path] = set()
        for glob in self.rutas:
            for ruta in sorted(self.raiz.glob(glob)):
                if ruta.is_file() and ruta not in vistos:
                    vistos.add(ruta)
                    yield ruta

    def activas(self, dia: date) -> list[Tarea]:
        if not self.raiz.is_dir():
            raise ErrorDeProveedor(f"{self.raiz}: no existe la carpeta de donde salen las tareas")
        salida: list[Tarea] = []
        for ruta in self.documentos():
            try:
                texto = ruta.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue  # un archivo ilegible no puede vaciar la lista entera
            origen = ruta.relative_to(self.raiz).as_posix()
            salida.extend(t for t in leer_markdown(texto, origen, encabezado=self.encabezado) if t.activa)
        return salida


def _raiz(valor: object, contexto: str) -> Path:
    if valor is None:
        valor = os.environ.get("TELAR_RAIZ") or os.getcwd()
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorDeProveedor(f"{contexto}: se esperaba una ruta, llegó {valor!r}")
    return Path(valor).expanduser()


def _globs(valor: object, contexto: str) -> tuple[str, ...]:
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list) or not valor or not all(isinstance(x, str) and x.strip() for x in valor):
        raise ErrorDeProveedor(f"{contexto}: se esperaba una lista de globs, llegó {valor!r}")
    for glob in valor:
        if glob.startswith("/") or ".." in PurePosixPath(glob).parts:
            raise ErrorDeProveedor(f"{contexto}: {glob!r} debe ser relativo a la raíz y no salir de ella")
    return tuple(valor)


# ── comando: un programa externo que imprime JSON ───────────────────────────────

class DeComando(_Base):
    """Un programa de afuera dice qué hay pendiente, en JSON.

    Es la salida para cualquier gestor de tareas: quien lo use escribe el puente
    de tres líneas y telar no tiene que aprender su API. El programa recibe el día
    en `$TELAR_DIA` y en cualquier palabra que diga `{dia}`, y tiene que imprimir
    una lista (o un objeto con la clave `tareas`) de objetos así:

        [{"id": "T84", "texto": "Medir el alcance", "prioridad": "alta",
          "vence": "2026-06-30", "etiquetas": ["faro"], "enlace": "https://…",
          "espera": "@quien", "hecha": false, "en_curso": false,
          "avance": "preparado 2026-09-25", "area": "trabajo"}]

    De todo eso, solo `texto` es obligatorio.
    """

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        opciones = cfg.opciones
        comando = opciones.get("comando")
        if (
            not isinstance(comando, list)
            or not comando
            or not all(isinstance(x, str) for x in comando)
        ):
            raise ErrorDeProveedor(
                f"proveedores.{cfg.nombre}.comando: se esperaba una lista de palabras, "
                "no una línea de shell (si hace falta shell, pídela: [\"sh\", \"-c\", \"…\"])"
            )
        self.comando = tuple(comando)
        self.donde = _raiz(opciones["donde"], f"proveedores.{cfg.nombre}.donde") if "donde" in opciones else None
        espera = opciones.get("tiempo_maximo", 10)
        if isinstance(espera, bool) or not isinstance(espera, (int, float)) or espera <= 0:
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tiempo_maximo: se esperaba un número positivo")
        self.tiempo_maximo = float(espera)
        detalle = opciones.get("detalle")
        if detalle is not None and (not isinstance(detalle, list) or not detalle
                                    or not all(isinstance(x, str) for x in detalle)):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.detalle: se esperaba una lista de palabras con {{id}}")
        #: la ficha de una tarea (`telar tarea`): una página con acciones; ver docs/contratos.md
        self.detalle = tuple(detalle or ())
        self.alcance = f"corre `{' '.join(self.comando)}` y lee su JSON"

    def _salida(self, dia: date) -> str:
        palabras = [p.replace("{dia}", dia.isoformat()) for p in self.comando]
        entorno = dict(os.environ, TELAR_DIA=dia.isoformat())
        try:
            r = subprocess.run(
                palabras,
                capture_output=True,
                text=True,
                timeout=self.tiempo_maximo,
                cwd=str(self.donde) if self.donde else None,
                env=entorno,
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError as e:
            raise ErrorDeProveedor(f"no existe el programa {palabras[0]!r}") from e
        except subprocess.TimeoutExpired as e:
            raise ErrorDeProveedor(f"{palabras[0]} no respondió en {self.tiempo_maximo:g} s") from e
        except OSError as e:
            raise ErrorDeProveedor(f"{palabras[0]}: no se pudo correr: {e}") from e
        if r.returncode != 0:
            queja = (r.stderr or "").strip().splitlines()
            detalle = f": {queja[0]}" if queja else ""
            raise ErrorDeProveedor(f"{palabras[0]} salió con {r.returncode}{detalle}")
        return r.stdout

    def activas(self, dia: date) -> list[Tarea]:
        salida = self._salida(dia)
        try:
            datos = json.loads(salida or "[]")
        except json.JSONDecodeError as e:
            raise ErrorDeProveedor(f"{self.comando[0]} no imprimió JSON: {e}") from e
        if isinstance(datos, dict):
            datos = datos.get("tareas", [])
        if not isinstance(datos, list):
            raise ErrorDeProveedor(f"{self.comando[0]}: se esperaba una lista de tareas")
        origen = self.comando[0]
        tareas = [_tarea_de_json(d, origen, i) for i, d in enumerate(datos)]
        return [t for t in tareas if t.activa]


def _tarea_de_json(datos: object, origen: str, indice: int) -> Tarea:
    contexto = f"{origen}[{indice}]"
    if not isinstance(datos, dict):
        raise ErrorDeProveedor(f"{contexto}: se esperaba un objeto, llegó {datos!r}")

    texto = datos.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        raise ErrorDeProveedor(f"{contexto}: falta 'texto'")
    texto = texto.strip()

    etiquetas = datos.get("etiquetas", [])
    if isinstance(etiquetas, str):
        etiquetas = [etiquetas]
    if not isinstance(etiquetas, list) or not all(isinstance(e, str) for e in etiquetas):
        raise ErrorDeProveedor(f"{contexto}.etiquetas: se esperaba una lista de textos")

    def texto_de(clave: str) -> str:
        valor = datos.get(clave, "")
        if valor in (None, ""):
            return ""
        if not isinstance(valor, str):
            raise ErrorDeProveedor(f"{contexto}.{clave}: se esperaba texto, llegó {valor!r}")
        return valor

    def bandera(clave: str) -> bool:
        valor = datos.get(clave, False)
        if not isinstance(valor, bool):
            raise ErrorDeProveedor(f"{contexto}.{clave}: se esperaba true o false")
        return valor

    id = texto_de("id")
    return Tarea(
        id=id or _derivar_id(origen, texto),
        texto=texto,
        prioridad=_prioridad(datos.get("prioridad"), f"{contexto}.prioridad"),
        vence=_fecha(datos.get("vence"), f"{contexto}.vence"),
        etiquetas=tuple(e.lstrip("#").lower() for e in etiquetas),
        enlace=texto_de("enlace"),
        espera=texto_de("espera"),
        hecha=bandera("hecha"),
        en_curso=bandera("en_curso"),
        origen=texto_de("origen") or origen,
        avance=texto_de("avance"),
        area=texto_de("area"),
        color=texto_de("color"),
        dueno=texto_de("dueno"),
        destacada=bandera("destacada"),
        estrella=bandera("estrella"),
    )


# ── tipo: las tareas del tipo `tarea` (telar.tipos), desde su carpeta ──────────────

class DeTipo(_Base):
    """Las tareas del tipo `tarea`, un archivo por tarea en una carpeta (docs/arquitectura.md, «Los tipos»), leídas
    con el índice en memoria del proceso: en `telar serve` y en el nodo se leen una vez y se mantienen al día.

        [proveedores.tareas]
        tipo    = "tipo"
        carpeta = "~/notas/tareas"        # la misma de [tipos.tarea]
        detalle = ["…", "--ver", "{id}"]  # opcional: la ficha (ver `comando`)
        gmail   = { personal = "yo@gmail.com", "*" = "yo@trabajo.com" }   # opcional

    Entran las que no están cerradas ni en «algún día». En la ficha, un origen `gmail:<id>` se abre como el
    correo en Gmail, con la cuenta de su área (`gmail`, o `*` para las demás), y una ruta relativa como
    archivo de la raíz (la del repositorio git de las tareas, o `raiz`).
    """

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        opciones = cfg.opciones
        carpeta = opciones.get("carpeta")
        if not isinstance(carpeta, str) or not carpeta.strip():
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.carpeta: falta (la de [tipos.tarea])")
        self.carpeta = Path(carpeta).expanduser()
        detalle = opciones.get("detalle")
        if detalle is not None and (not isinstance(detalle, list) or not all(isinstance(x, str) for x in detalle)):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.detalle: se esperaba una lista de palabras con {{id}}")
        self.detalle = tuple(detalle or ())
        gmail = opciones.get("gmail", {})
        if not isinstance(gmail, dict) or not all(isinstance(v, str) for v in gmail.values()):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.gmail: se esperaba una tabla área → cuenta")
        self.gmail = dict(gmail)
        # contra qué se resuelve una ruta relativa (un origen «proyectos/x/README.md»): `raiz`, o la raíz
        # del repositorio git donde viven las tareas
        raiz = opciones.get("raiz") or ""
        if not raiz:
            from telar import git as mod_git

            raiz = str(mod_git.repositorio(self.carpeta) or self.carpeta)
        self.raiz = Path(raiz).expanduser()
        self.alcance = f"lee las tareas de {self.carpeta}; no sale de la máquina"
        self._opciones = dict(opciones)

    # ── la ficha: la página de una tarea, con las acciones del tipo ──

    #: el color de la propuesta del agente, por su estado
    COLOR_PROPUESTA = {"preparado": "verde", "cerrar": "cian", "pregunta": "amarillo", "choca": "rojo"}
    #: un archivo nombrado en un texto, relativo a la raíz: lo que «abrir lo preparado» abre
    ARCHIVO_NOMBRADO = re.compile(r"(?<![\w/])([\w.-]+/[\w./áéíóúñÁÉÍÓÚÑ-]+\.(?:md|docx|pptx|xlsx|html|pdf|csv))")

    def _opcion(self, clave: str, defecto: str = "") -> str:
        v = getattr(self, "_opciones", {}).get(clave, defecto)
        return v if isinstance(v, str) else defecto

    def ficha(self, id: str) -> tuple[dict, str]:
        """(la página de la tarea, su versión): la propuesta del agente arriba, el contexto, los enlaces, las
        conexiones y la historia; y las acciones que le tocan, como acciones del tipo (`accion` y `params`).
        Lo propio de una casa va en las opciones: `agente` (quién propone), `escribir_a` (a quién se le
        escribe en un hilo), `mensaje_procesar` y `mensaje_escribir` (qué recibe el hilo; `{id}`, `{texto}`),
        y `equipo` (a quién se puede asignar)."""
        from telar.tipos import tarea as tipo
        from telar.tipos.indice import compartido

        indice = compartido(self.carpeta, tipo.ARCHIVO)
        t, version = indice.obtener(id)
        agente = self._opcion("agente", "el agente")
        prop = _propuesta(t)
        partes = [t.estado, f"P{t.prioridad}"]
        if t.vence:
            partes.append(f"vence {t.vence}")
        if t.espera:
            partes.append(f"espera a {t.espera}")
        if t.dueno:
            partes.append(f"la hace {t.dueno}")
        if t.proyecto:
            partes.append(t.proyecto.split("/")[-1])
        bloques: list[dict] = []
        if prop:
            como = {"hecha": "hecha", "caduca": "caducó", "descartada": "descartada"}.get(prop["como"], prop["como"])
            verbo = {"cerrar": f"cerrar ({como})", "preparado": "lo dejó preparado", "pregunta": "pregunta",
                     "choca": "chocó al subir"}.get(prop["estado"], prop["estado"])
            bloques.append({"titulo": f"{agente} · {verbo} · {prop['fecha']}", "texto": prop["texto"],
                            "destacado": True, "color": self.COLOR_PROPUESTA.get(prop["estado"], "azul")})
        if t.contexto:
            bloques.append({"texto": t.contexto})
        enlaces = [{"titulo": f"{nombre}: {uri}", "enlace": self._enlace(uri, t.area)}
                   for nombre, uri in (("origen", t.origen), ("trabajo", t.trabajo)) if uri]
        archivo = self.carpeta / f"{id}.md"
        try:
            relativa = str(archivo.relative_to(self.raiz))
        except ValueError:
            relativa = str(archivo)
        enlaces.append({"titulo": f"la tarea: {relativa}", "enlace": str(archivo)})
        bloques.append({"titulo": "enlaces", "items": enlaces})
        if t.conexiones:
            bloques.append({"titulo": "conexiones", "texto": "\n".join(t.conexiones)})
        historia = [{"titulo": c.tipo, "texto": c.texto, "fecha": f"{c.fecha}T{c.hora or '00:00'}"}
                    for c in reversed(t.historia) if c.fecha]
        if historia:
            bloques.append({"titulo": "historia", "items": historia})
        return ({"titulo": f"{id} · {t.titulo}", "subtitulo": " · ".join(partes), "bloques": bloques,
                 "acciones": _recortar(self._acciones(t, prop, agente), 12), "version": version}, version)

    def _acciones(self, t, prop, agente: str) -> list[dict]:
        from telar.tipos import tarea as tipo

        procesar = self._opcion("mensaje_procesar")
        escribir = self._opcion("mensaje_escribir")
        escribir_a = self._opcion("escribir_a", "el agente")
        cerrada = t.estado in tipo.TERMINALES

        def accion(nombre: str, que: str, **params) -> dict:
            return {"nombre": nombre, "accion": que, "params": params}

        def y_procesar(a: dict) -> dict:
            # que sus secuelas se hagan ya, en el hilo donde se trabaja la tarea (el de su proyecto o el
            # agente de lo que no tiene proyecto), no en uno nuevo que no sabe nada del proyecto
            return {**a, "mensaje": procesar.replace("{id}", t.id), "al_hilo": True}

        acciones: list[dict] = []
        if prop and prop["estado"] == "cerrar" and prop["como"] in tipo.TERMINALES:
            etiqueta = {"hecha": "hecha", "caduca": "caducó", "descartada": "descartada"}[prop["como"]]
            nota = f"aceptada la propuesta de {agente} del {prop['fecha']}"
            acciones.append({**accion(f"✓ de acuerdo: {etiqueta}", "cerrar", como=prop["como"], nota=nota), "principal": True})
            if procesar:
                acciones.append(y_procesar(accion("✓ de acuerdo y procesar ahora", "cerrar", como=prop["como"], nota=nota)))
            acciones.append({**accion("no, sigue viva", "responder", texto="no, sigue viva: {texto}"), "pide": "por qué sigue viva"})
        elif prop and prop["estado"] == "preparado":
            hecho = next((m for m in self.ARCHIVO_NOMBRADO.findall(prop["texto"]) if (self.raiz / m).exists()), "")
            if hecho:
                acciones.append({"nombre": "abrir lo preparado", "tipo": "abrir", "enlace": str(self.raiz / hecho), "principal": True})
            acciones.append({"nombre": "seguir en un hilo", "tipo": "hilo", "principal": not hecho})
            acciones.append({**accion("responder", "responder", texto="{texto}"), "pide": "tu respuesta o la decisión"})
        elif prop and prop["estado"] == "pregunta":
            acciones.append({**accion("responder", "responder", texto="{texto}"), "pide": "tu respuesta", "principal": True})
        if not any(a.get("tipo") == "hilo" for a in acciones):
            acciones.append({"nombre": "trabajar en un hilo", "tipo": "hilo", "principal": not acciones})
        if not cerrada:
            if escribir:
                # queda anotado en la tarea, y va al hilo donde se trabaja
                acciones.append({**accion(f"↩ escribirle a {escribir_a}", "anotar", texto=f"le escribí a {escribir_a} en un hilo: {{texto}}"),
                                 "pide": f"qué le dices a {escribir_a}", "mensaje": escribir.replace("{id}", t.id), "al_hilo": True})
            acciones.append({**accion("nota", "anotar", texto="{texto}"), "pide": "la nota"})
            acciones.append({**accion("nueva fecha…", "reagendar", fecha="{texto}"), "pide": "la nueva fecha (AAAA-MM-DD o +Nd)", "rol": "fecha"})
            acciones.append({**accion("esperar a…", "esperar", quien="{texto}"), "pide": "a quién («none»: deja de esperar)",
                             "rol": "espera", "opciones": self._personas()})
            acciones.append({**accion("prioridad…", "editar", prioridad="{texto}"), "pide": "la prioridad (P0 la más alta, P3)",
                             "rol": "prioridad", "opciones": [f"P{n}" for n in range(4)]})
            acciones.append({**accion("responsable…", "asignar", persona="{texto}"), "pide": "quién la hace («none»: sin asignar)",
                             "rol": "dueno", "opciones": self._personas()})
            for etiqueta, rol, si, no in (("estrella", "estrella", "★ quitar la estrella", "☆ marcar con estrella"),
                                          ("equipo", "equipo", "◉ dejar de compartir con el equipo", "○ compartir con el equipo")):
                tiene = etiqueta in t.etiquetas
                nuevas = [e for e in t.etiquetas if e != etiqueta] if tiene else [*t.etiquetas, etiqueta]
                acciones.append({**accion(si if tiene else no, "editar", etiquetas=nuevas), "rol": rol})
            acciones.append({**accion("✓ hecha", "completar"), "confirmar": True, "rol": "hecha"})
            if procesar and not (prop and prop["estado"] == "cerrar"):
                acciones.append(y_procesar(accion("✓ hecha y procesar ahora", "completar")))
            acciones.append({**accion("descartar", "cerrar", como="descartada"), "confirmar": True})
        return acciones

    def _personas(self) -> list[str]:
        """A quién se le puede asignar: el `equipo` declarado y todo el que ya es dueño de alguna."""
        from telar.tipos import tarea as tipo
        from telar.tipos.indice import compartido

        equipo = getattr(self, "_opciones", {}).get("equipo", [])
        vistos = {p.casefold(): p for p in equipo if isinstance(p, str)}
        for t, _ in compartido(self.carpeta, tipo.ARCHIVO).consultar():
            if t.dueno and t.dueno not in ("none", "~", "null", '""'):
                vistos.setdefault(t.dueno.casefold(), t.dueno)
        return sorted(vistos.values(), key=str.casefold)

    def _enlace(self, uri: str, area: str) -> str:
        if not uri:
            return ""
        if uri.startswith("gmail:"):
            cuenta = self.gmail.get(area) or self.gmail.get("*") or "0"
            return f"https://mail.google.com/mail/?authuser={cuenta}#all/{uri[6:]}"
        if uri.startswith(("http://", "https://")):
            return uri
        ruta = self.raiz / uri.split("#")[0]
        return str(ruta) if ruta.exists() else ""

    def activas(self, dia: date) -> list[Tarea]:
        from telar.tipos import tarea as tipo
        from telar.tipos.indice import compartido

        indice = compartido(self.carpeta, tipo.ARCHIVO)
        salida = []
        for t, _version in indice.consultar(lambda x: not x.cerrada_ya and x.estado != "algun-dia"):
            etiquetas = tuple(e.lstrip("#").lower() for e in t.etiquetas)
            salida.append(Tarea(
                id=t.id, texto=t.titulo.strip() or t.id,
                prioridad=_prioridad({0: "alta", 1: "alta", 2: "media", 3: "baja"}.get(t.prioridad), f"{t.id}.prioridad"),
                vence=_fecha(t.vence or None, f"{t.id}.vence"),
                etiquetas=etiquetas,
                # en la lista, el enlace como está escrito (el de la ficha se abre: `_enlace`)
                enlace=t.trabajo or t.origen,
                espera=("@" + (t.espera or "alguien").lstrip("@")) if t.estado == "espera" else "",
                origen=t.proyecto,
                avance=t.avance, area=t.area, dueno=t.dueno,
                estrella="estrella" in etiquetas,
                destacada=t.prioridad == 0 or "estrella" in etiquetas,
            ))
        return salida


def _propuesta(t) -> dict | None:
    """Lo último que dejó un agente para decidir (`avance`: «cerrar:hecha 2026-10-05»), con su texto (la
    última línea `[avance]` de la historia), o None si no hay nada vigente."""
    if not t.avance:
        return None
    estado, _, fecha = t.avance.partition(" ")
    estado, _, como = estado.partition(":")
    texto = next((c.texto for c in reversed(t.historia) if c.tipo == "avance"), "")
    return {"estado": estado, "como": como, "fecha": fecha, "texto": re.sub(r"^[\w:]+: ", "", texto)}


def _recortar(acciones: list[dict], tope: int) -> list[dict]:
    """Las primeras `tope` sin `rol`, sin perder la principal: sobran las últimas sin rol. Las que tienen `rol`
    no cuentan: la ficha las pone donde se ven (la fecha, el dueño, la estrella), no en la lista numerada."""
    salida = list(acciones)
    while sum(1 for a in salida if not a.get("rol")) > tope:
        sin_rol = [i for i, a in enumerate(salida) if not a.get("rol") and not a.get("principal")]
        if not sin_rol:
            break
        salida.pop(sin_rol[-1])
    return salida


# ── ninguno: la forma explícita de no tener tareas ──────────────────────────────

class Ninguno(_Base):
    """Apagado, pero dicho. Sirve para dejar la sección escrita sin que consulte nada."""

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        self.alcance = "no toca nada"

    def activas(self, dia: date) -> list[Tarea]:
        return []


# ── de dónde sale la implementación ─────────────────────────────────────────────

IMPLEMENTACIONES = {
    "markdown": DeMarkdown,
    "comando": DeComando,
    "tipo": DeTipo,
    "ninguno": Ninguno,
}


def construir(cfg: ConfigProveedor) -> FuenteDeTareas:
    """La implementación que dice `tipo`. Sin `tipo`, se dice en voz alta."""
    tipo = cfg.opciones.get("tipo")
    if tipo is None:
        conocidas = ", ".join(sorted(IMPLEMENTACIONES))
        raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tipo: falta; es una de: {conocidas}")
    clase = IMPLEMENTACIONES.get(tipo) if isinstance(tipo, str) else None
    if clase is None:
        conocidas = ", ".join(sorted(IMPLEMENTACIONES))
        raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tipo: {tipo!r} no es una de: {conocidas}")
    return clase(cfg)


def registrar() -> None:
    """Deja este proveedor disponible. Encenderlo sigue siendo de la configuración."""
    if NOMBRE not in proveedores.REGISTRO:
        proveedores.registrar(NOMBRE, construir)


registrar()
