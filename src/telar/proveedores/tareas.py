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
            hilo=hilo,
            url=self.enlace,
            datos={
                "prioridad": self.prioridad.value if self.prioridad else None,
                "etiquetas": list(self.etiquetas),
                "espera": self.espera,
                "hecha": self.hecha,
                "en_curso": self.en_curso,
                "origen": self.origen,
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
          "espera": "@quien", "hecha": false, "en_curso": false}]

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
    )


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
