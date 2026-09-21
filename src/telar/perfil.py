"""El perfil que publica el repositorio de trabajo: `telar-perfil.yaml`.

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
]

#: El archivo que telar busca en la raíz del repositorio de trabajo.
NOMBRE_ARCHIVO = "telar-perfil.yaml"

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

    @property
    def por_carpeta(self) -> bool:
        return self.ruta.endswith("/")

    def seccion(self, nombre: str) -> Seccion | None:
        return next((s for s in self.secciones if s.nombre == nombre), None)

    def documentos(self, raiz: Path) -> list[Path]:
        """Los documentos de este arquetipo bajo `raiz`, ordenados y existentes.

        No lee ninguno: resuelve el glob y filtra lo que no está. Parsear es de
        otro módulo; esto solo dice dónde mirar.
        """
        raiz = Path(raiz)
        patron = self.ruta.rstrip("/") if self.por_carpeta else self.ruta
        salida: list[Path] = []
        for hallazgo in sorted(raiz.glob(patron)):
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
    nombre="mínimo",
    arquetipos=(
        Arquetipo(
            nombre="proyecto",
            ruta="*/",
            documento="README.md",
            descripcion="Una carpeta con README, leída por convención.",
            secciones=(
                Seccion(nombre="titulo", tipo="linea", encabezado=r"^#\s+(.+)$"),
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

    sobra = set(cuerpo) - {"ruta", "documento", "descripcion", "secciones"}
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

    sobra = set(datos) - {"version", "nombre", "arquetipos", "acciones"}
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
        origen=origen,
    )


def cargar(raiz: Path, *, ruta: Path | None = None) -> Perfil:
    """Lee el perfil del repositorio. Sin archivo, devuelve `PERFIL_MINIMO`.

    `ruta` explícita manda; si esa ruta no existe, es un error, porque alguien la
    pidió a propósito.
    """
    explicita = ruta is not None
    destino = Path(ruta) if ruta is not None else Path(raiz) / NOMBRE_ARCHIVO

    if not destino.exists():
        if explicita:
            raise ErrorDePerfil(f"no existe el perfil: {destino}")
        return PERFIL_MINIMO

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

    return desde_dict(datos, origen=destino)
