"""El perfil que publica el repositorio de trabajo: `.telar/perfil.yaml`.

Este es el límite de telar. telar sabe tejer hilos, leer documentos y llamar
órdenes; **no sabe qué es un proyecto**. Eso lo declara cada repositorio en su
perfil: qué carpetas son unidades de trabajo (los *arquetipos*), qué archivo es la
cara de cada una, qué secciones de ese archivo se leen y cómo, y qué acciones
ofrece el repositorio sobre un hilo.

Así un repositorio de consultoría, uno de investigación y uno de código pueden
usar el mismo telar sin que telar sepa nada de ninguno.

Sin perfil, rige una convención mínima que casi cualquier README cumple:

  * el título es el primer encabezado;
  * el estado es el primer párrafo;
  * los pendientes son la primera lista de casillas.

Lo que un repositorio le dice a telar vive en su carpeta `.telar/`, como `.github/` o `.claude/`: el perfil
(`perfil.yaml`) y, de cada persona y fuera de git, `local.yaml`, que se lee encima del perfil (un valor suyo
reemplaza al del equipo, un mapa se mezcla clave por clave y un `null` quita la clave).

El esquema entero está en `docs/perfil.md`, y esa página manda.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "TIPOS",
    "Seccion",
    "Arquetipo",
    "Accion",
    "Perfil",
    "PERFIL_MINIMO",
    "cargar",
    "desde_dict",
    "ErrorDePerfil",
    "NOMBRE_ARCHIVO",
    "NOMBRE_LOCAL",
    "CARPETA",
]

#: la carpeta de telar en un repositorio, y lo que telar busca en ella
CARPETA = ".telar"
NOMBRE_ARCHIVO = f"{CARPETA}/perfil.yaml"
#: lo de cada persona, encima del perfil del equipo; no va en git
NOMBRE_LOCAL = f"{CARPETA}/local.yaml"

#: Versión del esquema que este módulo entiende.
VERSION = 1

#: Cómo se lee una sección. El nombre dice qué devuelve, no dónde está.
#:
#:   linea     una línea suelta (el grupo 1 del `encabezado`, o la primera línea del cuerpo).
#:   parrafo   el primer párrafo de texto del cuerpo, con los saltos unidos.
#:   texto     el cuerpo entero, tal cual.
#:   lista     las viñetas del cuerpo, en orden.
#:   casillas  las viñetas con casilla: `[ ]` pendiente, `[x]` hecha, `[>]` en curso.
#:   tabla     las filas `| clave | valor |` del cuerpo, como diccionario.
TIPOS = ("linea", "parrafo", "texto", "lista", "casillas", "tabla")

#: Los tres nombres de sección que telar entiende sin que se los expliquen.
SECCIONES_CONOCIDAS = ("titulo", "estado", "pendientes")


class ErrorDePerfil(Exception):
    """El perfil existe pero no se puede usar. El mensaje dice qué línea lo rompe."""


@dataclass(frozen=True, slots=True)
class Seccion:
    """Una parte del documento que el repositorio declara legible.

    `encabezado` es una expresión regular contra la línea del encabezado
    (`## Estado`, `# Título`). Si tiene un grupo de captura y el tipo es `linea`,
    el valor es ese grupo: así el título sale del propio encabezado.

    Sin `encabezado`, la sección no está anclada: se busca lo primero del documento
    que calce con el tipo (el primer párrafo, la primera lista de casillas). Es lo
    que hace posible la convención mínima.
    """

    nombre: str
    tipo: str = "texto"
    encabezado: str | None = None
    #: tope de elementos para los tipos que devuelven varios. 0 = sin tope.
    maximo: int = 0
    #: si es falso, la sección puede faltar sin que el documento se considere roto.
    requerida: bool = False

    @property
    def patron(self) -> re.Pattern[str] | None:
        """El `encabezado` compilado, o None si la sección no está anclada."""
        return re.compile(self.encabezado) if self.encabezado else None

    @property
    def multiple(self) -> bool:
        return self.tipo in ("lista", "casillas", "tabla")


@dataclass(frozen=True, slots=True)
class Arquetipo:
    """Una forma de unidad de trabajo del repositorio: un proyecto, una nota, un cliente.

    `ruta` es un glob relativo a la raíz. Si termina en `/`, cada coincidencia es
    una carpeta y el documento es `documento` dentro de ella; si no, cada
    coincidencia es el documento mismo.
    """

    nombre: str
    ruta: str
    documento: str = "README.md"
    secciones: tuple[Seccion, ...] = ()
    #: descripción libre, para que la interfaz pueda decir qué es esto.
    descripcion: str = ""
    #: cómo se llama una unidad de este tipo en pantalla: `{titulo}`, `{campo:Clave}`
    #: (una fila de la tabla de campos o del frontmatter). Vacía: el título del documento.
    etiqueta: str = ""
    #: de qué repositorio de `[repos]` viene (cargar_todos); "" es el de la raíz
    repo: str = ""

    @property
    def por_carpeta(self) -> bool:
        return self.ruta.endswith("/")

    def seccion(self, nombre: str) -> Seccion | None:
        return next((s for s in self.secciones if s.nombre == nombre), None)

    def documentos(self, raiz: Path) -> list[Path]:
        """Los documentos de este arquetipo bajo `raiz`, ordenados y existentes.

        No lee ninguno: resuelve el glob y filtra lo que no está, y lo que vive en una
        carpeta que empieza con `_` o `.`. Parsear es de otro módulo; esto solo dice
        dónde mirar.
        """
        raiz = Path(raiz)
        patron = self.ruta.rstrip("/") if self.por_carpeta else self.ruta
        salida: list[Path] = []
        for hallazgo in sorted(raiz.glob(patron)):
            # `_perdidos/`, `.git/`: lo que empieza con _ o . es de la casa, no una unidad
            # de trabajo. Y además telar reserva las claves con _ en su estado, así que un
            # hilo así llamado perdería su conversación al archivarlo.
            if any(parte.startswith(("_", ".")) for parte in hallazgo.relative_to(raiz).parts):
                continue
            destino = hallazgo / self.documento if self.por_carpeta else hallazgo
            if destino.is_file():
                salida.append(destino)
        return salida

    def carpeta_de(self, documento: Path) -> Path:
        """La carpeta del hilo al que pertenece un documento de este arquetipo."""
        return documento.parent


@dataclass(frozen=True, slots=True)
class Accion:
    """Algo que el repositorio ofrece hacer sobre un hilo.

    telar no adivina órdenes: corre las que el perfil declare, con el `cwd` que
    diga `donde` ("hilo": la carpeta del hilo; "raiz": la raíz del repositorio).
    `comando` es una lista (nunca una cadena para la shell), y admite los marcadores
    `{ruta}`, `{hilo}` y `{documento}`.
    """

    nombre: str
    comando: tuple[str, ...]
    descripcion: str = ""
    #: tecla sugerida para la interfaz; una sola letra o vacía.
    tecla: str = ""
    donde: str = "hilo"
    #: si es verdadero, la interfaz pide confirmación antes de correrla.
    confirmar: bool = False


@dataclass(frozen=True, slots=True)
class Perfil:
    """Lo que el repositorio de trabajo declara de sí mismo."""

    nombre: str = ""
    version: int = VERSION
    arquetipos: tuple[Arquetipo, ...] = ()
    acciones: tuple[Accion, ...] = ()
    #: las áreas en el orden en que se muestran (el `area:` del frontmatter); una que no esté va después
    areas: tuple[str, ...] = ()
    #: los clientes que son la casa misma («Interno», el nombre del equipo): en el dashboard no dicen nada, y va
    #: el nombre del proyecto en su lugar
    internos: tuple[str, ...] = ()
    #: de qué archivo salió; None si es el perfil mínimo.
    origen: Path | None = None

    @property
    def minimo(self) -> bool:
        return self.origen is None

    def arquetipo(self, nombre: str) -> Arquetipo | None:
        return next((a for a in self.arquetipos if a.nombre == nombre), None)

    def accion(self, nombre: str) -> Accion | None:
        return next((a for a in self.acciones if a.nombre == nombre), None)

    def documentos(self, raiz: Path) -> dict[str, list[Path]]:
        """Todos los documentos del repositorio, por arquetipo."""
        return {a.nombre: a.documentos(raiz) for a in self.arquetipos}


#: La convención cuando el repositorio no declara nada: una carpeta con README, y
#: dentro, lo primero de cada forma. Con esto telar sirve sin configurar nada.
PERFIL_MINIMO = Perfil(
    nombre="de casa",
    arquetipos=(
        # Las tres formas en que la gente guarda proyectos, sin pedirle que declare nada:
        # carpetas en la raíz, carpetas un nivel adentro (proyectos/, projects/, clients/)
        # y el README de la raíz, que en un repo de un solo proyecto es todo lo que hay.
        Arquetipo(
            nombre="proyecto",
            ruta="*/",
            documento="README.md",
            descripcion="Una carpeta de la raíz con README.",
        secciones=(
            Seccion(nombre="titulo", tipo="linea", encabezado=r"^#\s+(.+)$"),
            # sin anclar a propósito: sin perfil no se sabe cómo titula este repositorio sus
            # secciones, y el primer párrafo y la primera lista de casillas los cumple casi
            # cualquier README. Anclarlas es justo lo que se gana al escribir un perfil.
            Seccion(nombre="estado", tipo="parrafo"),
            Seccion(nombre="pendientes", tipo="casillas", maximo=6),
        ),
        ),
        Arquetipo(
            nombre="proyecto anidado",
            ruta="*/*/",
            documento="README.md",
            descripcion="Una carpeta un nivel más adentro (proyectos/…, projects/…).",
        secciones=(
            Seccion(nombre="titulo", tipo="linea", encabezado=r"^#\s+(.+)$"),
            # sin anclar a propósito: sin perfil no se sabe cómo titula este repositorio sus
            # secciones, y el primer párrafo y la primera lista de casillas los cumple casi
            # cualquier README. Anclarlas es justo lo que se gana al escribir un perfil.
            Seccion(nombre="estado", tipo="parrafo"),
            Seccion(nombre="pendientes", tipo="casillas", maximo=6),
        ),
        ),
        Arquetipo(
            nombre="repositorio",
            ruta="README.md",
            descripcion="El README de la raíz: en un repo de un solo proyecto, es la unidad.",
        secciones=(
            Seccion(nombre="titulo", tipo="linea", encabezado=r"^#\s+(.+)$"),
            # sin anclar a propósito: sin perfil no se sabe cómo titula este repositorio sus
            # secciones, y el primer párrafo y la primera lista de casillas los cumple casi
            # cualquier README. Anclarlas es justo lo que se gana al escribir un perfil.
            Seccion(nombre="estado", tipo="parrafo"),
            Seccion(nombre="pendientes", tipo="casillas", maximo=6),
        ),
        ),
    ),
)


# ── lectura del YAML ────────────────────────────────────────────────────────────

def _texto(valor: object, contexto: str, *, obligatorio: bool = True) -> str:
    if valor is None and not obligatorio:
        return ""
    if not isinstance(valor, str) or (obligatorio and not valor.strip()):
        raise ErrorDePerfil(f"{contexto}: se esperaba texto, llegó {valor!r}")
    return valor

def _mapa(valor: object, contexto: str) -> dict:
    if not isinstance(valor, dict):
        raise ErrorDePerfil(f"{contexto}: se esperaba un mapa, llegó {valor!r}")
    return valor


def _seccion(nombre: str, cuerpo: object) -> Seccion:
    contexto = f"secciones.{nombre}"
    cuerpo = _mapa(cuerpo, contexto)

    sobra = set(cuerpo) - {"tipo", "encabezado", "maximo", "requerida"}
    if sobra:
        raise ErrorDePerfil(f"{contexto}: claves que telar no conoce: {', '.join(sorted(sobra))}")

    tipo = cuerpo.get("tipo", "texto")
    if tipo not in TIPOS:
        raise ErrorDePerfil(f"{contexto}.tipo: {tipo!r} no es uno de: {', '.join(TIPOS)}")

    encabezado = cuerpo.get("encabezado")
    if encabezado is not None:
        encabezado = _texto(encabezado, f"{contexto}.encabezado")
        try:
            re.compile(encabezado)
        except re.error as e:
            raise ErrorDePerfil(f"{contexto}.encabezado: expresión regular inválida: {e}") from e

    maximo = cuerpo.get("maximo", 0)
    if not isinstance(maximo, int) or isinstance(maximo, bool) or maximo < 0:
        raise ErrorDePerfil(f"{contexto}.maximo: se esperaba un entero ≥ 0, llegó {maximo!r}")

    requerida = cuerpo.get("requerida", False)
    if not isinstance(requerida, bool):
        raise ErrorDePerfil(f"{contexto}.requerida: se esperaba true o false")

    return Seccion(
        nombre=nombre,
        tipo=tipo,
        encabezado=encabezado,
        maximo=maximo,
        requerida=requerida,
    )


def _arquetipo(nombre: str, cuerpo: object) -> Arquetipo:
    contexto = f"arquetipos.{nombre}"
    cuerpo = _mapa(cuerpo, contexto)

    sobra = set(cuerpo) - {"ruta", "documento", "descripcion", "secciones", "etiqueta"}
    if sobra:
        raise ErrorDePerfil(f"{contexto}: claves que telar no conoce: {', '.join(sorted(sobra))}")

    ruta = _texto(cuerpo.get("ruta"), f"{contexto}.ruta")
    if ruta.startswith("/") or ".." in Path(ruta).parts:
        raise ErrorDePerfil(f"{contexto}.ruta: debe ser relativa a la raíz y no salir de ella")

    documento = cuerpo.get("documento", "README.md")
    documento = _texto(documento, f"{contexto}.documento")

    secciones = _mapa(cuerpo.get("secciones", {}), f"{contexto}.secciones")
    return Arquetipo(
        nombre=nombre,
        ruta=ruta,
        documento=documento,
        descripcion=_texto(cuerpo.get("descripcion", ""), f"{contexto}.descripcion", obligatorio=False),
        etiqueta=_texto(cuerpo.get("etiqueta", ""), f"{contexto}.etiqueta", obligatorio=False),
        secciones=tuple(_seccion(n, c) for n, c in secciones.items()),
    )


def _accion(cuerpo: object, indice: int) -> Accion:
    contexto = f"acciones[{indice}]"
    cuerpo = _mapa(cuerpo, contexto)

    sobra = set(cuerpo) - {"nombre", "comando", "descripcion", "tecla", "donde", "confirmar"}
    if sobra:
        raise ErrorDePerfil(f"{contexto}: claves que telar no conoce: {', '.join(sorted(sobra))}")

    nombre = _texto(cuerpo.get("nombre"), f"{contexto}.nombre")
    comando = cuerpo.get("comando")
    if not isinstance(comando, list) or not comando or not all(isinstance(x, str) for x in comando):
        raise ErrorDePerfil(
            f"{contexto}.comando: se esperaba una lista de palabras, no una línea de shell"
        )

    donde = cuerpo.get("donde", "hilo")
    if donde not in ("hilo", "raiz"):
        raise ErrorDePerfil(f"{contexto}.donde: se esperaba 'hilo' o 'raiz', llegó {donde!r}")

    tecla = _texto(cuerpo.get("tecla", ""), f"{contexto}.tecla", obligatorio=False)
    if len(tecla) > 1:
        raise ErrorDePerfil(f"{contexto}.tecla: se esperaba una sola letra, llegó {tecla!r}")

    confirmar = cuerpo.get("confirmar", False)
    if not isinstance(confirmar, bool):
        raise ErrorDePerfil(f"{contexto}.confirmar: se esperaba true o false")

    return Accion(
        nombre=nombre,
        comando=tuple(comando),
        descripcion=_texto(cuerpo.get("descripcion", ""), f"{contexto}.descripcion", obligatorio=False),
        tecla=tecla,
        donde=donde,
        confirmar=confirmar,
    )


def desde_dict(datos: dict, *, origen: Path | None = None) -> Perfil:
    """Arma un `Perfil` desde el YAML ya parseado, validando lo que llegó."""
    datos = _mapa(datos, "el perfil")

    sobra = set(datos) - {"version", "nombre", "arquetipos", "acciones", "areas", "internos"}
    if sobra:
        raise ErrorDePerfil(f"claves que telar no conoce: {', '.join(sorted(sobra))}")

    version = datos.get("version", VERSION)
    if version != VERSION:
        raise ErrorDePerfil(f"version: este telar entiende la {VERSION}, el perfil dice {version!r}")

    arquetipos = _mapa(datos.get("arquetipos", {}), "arquetipos")
    if not arquetipos:
        raise ErrorDePerfil("arquetipos: un perfil sin arquetipos no declara nada; bórralo mejor")

    acciones = datos.get("acciones", [])
    if not isinstance(acciones, list):
        raise ErrorDePerfil("acciones: se esperaba una lista")

    return Perfil(
        nombre=_texto(datos.get("nombre", ""), "nombre", obligatorio=False),
        version=version,
        arquetipos=tuple(_arquetipo(n, c) for n, c in arquetipos.items()),
        acciones=tuple(_accion(c, i) for i, c in enumerate(acciones)),
        areas=_nombres(datos.get("areas", []), "areas"),
        internos=_nombres(datos.get("internos", []), "internos"),
        origen=origen,
    )


def _nombres(valor, contexto: str) -> tuple[str, ...]:
    """Una lista de nombres (las áreas, los clientes internos), sin repetidos y en su orden."""
    if not isinstance(valor, list) or not all(isinstance(v, str) and v.strip() for v in valor):
        raise ErrorDePerfil(f"{contexto}: se esperaba una lista de nombres")
    return tuple(dict.fromkeys(v.strip() for v in valor))


def cargar(raiz: Path, *, ruta: Path | None = None) -> Perfil:
    """Lee el perfil del repositorio. Sin archivo, devuelve `PERFIL_MINIMO`.

    `ruta` explícita manda; si esa ruta no existe, es un error, porque alguien la
    pidió a propósito.
    """
    explicita = ruta is not None
    destino = Path(ruta) if ruta is not None else Path(raiz) / NOMBRE_ARCHIVO
    local = None if explicita else Path(raiz) / NOMBRE_LOCAL

    if not destino.exists():
        if explicita:
            raise ErrorDePerfil(f"no existe el perfil: {destino}")
        return PERFIL_MINIMO

    datos = _yaml(destino)
    if local is not None and local.exists():
        datos = mezclar(datos, _yaml(local))
    return desde_dict(datos, origen=destino)


def _yaml(destino: Path) -> dict:
    try:
        import yaml
    except ModuleNotFoundError as e:  # pragma: no cover - depende del entorno
        raise ErrorDePerfil(
            f"{destino} existe pero falta PyYAML para leerlo (pip install PyYAML)"
        ) from e
    try:
        datos = yaml.safe_load(destino.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErrorDePerfil(f"{destino}: YAML mal formado: {e}") from e
    except OSError as e:
        raise ErrorDePerfil(f"{destino}: no se pudo leer: {e}") from e
    if not isinstance(datos, dict):
        raise ErrorDePerfil(f"{destino}: se esperaba un mapa (clave: valor) arriba de todo")
    return datos


def mezclar(base: dict, encima: dict) -> dict:
    """`encima` sobre `base`: un mapa se mezcla clave por clave, cualquier otro valor reemplaza, y `null` quita
    la clave. Es lo que hace `local.yaml` sobre el perfil del equipo."""
    salida = dict(base)
    for clave, valor in encima.items():
        if valor is None:
            salida.pop(clave, None)
        elif isinstance(valor, dict) and isinstance(salida.get(clave), dict):
            salida[clave] = mezclar(salida[clave], valor)
        else:
            salida[clave] = valor
    return salida


def cargar_todos(config) -> Perfil:
    """El perfil de la raíz junto con los de los repositorios de `[repos]` que están dentro de ella.

    Cada repo describe sus carpetas con su perfil, en rutas relativas a sí mismo; aquí pasan a ser relativas
    a la raíz. Si dos perfiles reconocen la misma carpeta, gana el del repo más profundo: el de un repo
    del equipo dentro del de vida describe lo suyo, aunque el de vida también lo nombre (el índice se queda
    con el primer arquetipo que la reconoce, y los más profundos van primero). Un repo sin perfil no aporta
    nada: su perfil mínimo reconocería cualquier carpeta. Un repo fuera de la raíz todavía no se suma.
    """
    from dataclasses import replace

    raiz = Path(config.raiz).expanduser()
    base = cargar(raiz, ruta=getattr(config, "perfil", None))
    partes: list[tuple[str, str, Perfil]] = []
    for repo in getattr(config, "repos", ()) or ():
        try:
            relativa = carpeta_de_repo(config, repo).relative_to(raiz.resolve()).as_posix()
        except (ValueError, OSError):
            continue  # fuera de la raíz: todavía no (telar doctor lo dice)
        if relativa in ("", "."):
            continue  # es la raíz misma: su perfil es el de la base
        perfil = cargar(carpeta_de_repo(config, repo), ruta=Path(repo.perfil).expanduser() if repo.perfil else None)
        if not perfil.minimo:
            partes.append((repo.nombre, relativa, perfil))
    if not partes:
        return base
    partes.sort(key=lambda x: x[1].count("/"), reverse=True)
    arquetipos = [replace(a, ruta=f"{rel}/{a.ruta}", repo=nombre) for nombre, rel, p in partes for a in p.arquetipos]
    acciones, vistas = [], set()
    for a in [x for _, _, p in partes for x in p.acciones] + list(base.acciones):
        if a.nombre not in vistas:
            vistas.add(a.nombre)
            acciones.append(a)
    # las áreas y los clientes internos de todos, los de los repos más profundos primero
    areas = tuple(dict.fromkeys(x for p in [*(p for _, _, p in partes), base] for x in p.areas))
    internos = tuple(dict.fromkeys(x for p in [*(p for _, _, p in partes), base] for x in p.internos))
    return replace(base, arquetipos=(*arquetipos, *base.arquetipos), acciones=tuple(acciones), areas=areas,
                   internos=internos)


def ruta_de_repo(config, repo) -> Path:
    """La ruta de un repo de `[repos]` como la entregan las salidas (`telar config --json`, `TELAR_REPOS`):
    absoluta, con una relativa leída desde la raíz, pero sin resolver enlaces (`~/vida/equipo` sigue siéndolo)."""
    ruta = Path(repo.ruta).expanduser()
    return ruta if ruta.is_absolute() else Path(config.raiz).expanduser() / ruta


def carpeta_de_repo(config, repo) -> Path:
    """La carpeta de un repo de `[repos]`, absoluta y resuelta. Una `ruta` relativa se lee desde la raíz y
    no desde el directorio de trabajo: si no, el repo de un hilo cambiaría según desde dónde se corra la
    orden o el servidor. Así la dan también `telar config --json` y `TELAR_REPOS`, la de los módulos."""
    ruta = Path(repo.ruta).expanduser()
    if not ruta.is_absolute():
        ruta = Path(config.raiz).expanduser() / ruta
    return ruta.resolve()


def repo_de(config, ruta: str | Path) -> str:
    """De qué repositorio de `[repos]` es una carpeta (relativa a la raíz o absoluta): el más profundo que la
    contiene. "" si de ninguno declarado (es de la raíz)."""
    raiz = Path(config.raiz).expanduser()
    camino = Path(ruta).expanduser()
    camino = (camino if camino.is_absolute() else raiz / camino).resolve()
    mejor, largo = "", -1
    for repo in getattr(config, "repos", ()) or ():
        base = carpeta_de_repo(config, repo)
        if camino == base or base in camino.parents:
            if len(base.parts) > largo:
                mejor, largo = repo.nombre, len(base.parts)
    return mejor

