"""Mapas de fechas: cómo se traduce el formato de un documento a fechas (telar.fechas, docs/propuestas/fechas.md).

Un mapa dice qué secciones de un documento son cronogramas y, para cada campo de una fecha, de dónde sale: de una
columna (con su patrón de fecha, su vocabulario, su rango), de una plantilla sobre varias columnas, o una
constante. Lo que el mapa no dice se busca por el nombre de la columna, como sin mapa. Se declaran en el
`.telar/fechas.yaml` de un repositorio, con nombre, y se usan desde ahí (`documentos:`) o desde el frontmatter de un
documento (`fechas: <mapa>`):

    # .telar/fechas.yaml
    version: 1
    mapas:
      sesiones:
        secciones: '^##\\s+\\w+$'
        campos:
          clase: sesion
          inicio: { columna: Fecha, formato: "EEE d-MMM", año: "frontmatter:actualizado" }
          hora: { columna: Hora, formato: "HH:mm", rango: "–" }
          titulo: "{Cliente} · {Programa}"
          estado: { columna: Estado, valores: { dictado: hecho, confirmado: pendiente } }
          proyecto: { columna: Proyecto, buscar: pmo }
    documentos:
      - { ruta: operacion/ia/calendario-cursos.md, mapa: sesiones }
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from telar.patrones import ErrorDePatron, Patron

__all__ = ["Campo", "Mapa", "Mapas", "ErrorDeMapa", "POR_DEFECTO", "mapa_de", "cargar", "frontmatter"]

ARCHIVO = Path(".telar") / "fechas.yaml"
CAMPOS = ("titulo", "inicio", "fin", "hora", "clase", "proyecto", "estado", "responsable", "depende", "enlace")
_CLAVES_CAMPO = {"columna", "formato", "idioma", "rango", "año", "anio", "valores", "buscar"}


class ErrorDeMapa(ValueError):
    """Un mapa mal escrito: dice dónde y qué."""


@dataclass(frozen=True, slots=True)
class Campo:
    """De dónde sale un campo: una `columna` (o la que se llame como el campo, si no la dice), una `plantilla` o una
    `constante`."""

    columna: str = ""
    plantilla: str = ""
    constante: str | None = None
    formato: Patron | None = None
    rango: str = ""
    #: el año cuando el patrón no lo trae: un número, o «frontmatter:<clave>» (el año de esa clave del documento)
    anio: int | str | None = None
    valores: dict[str, str] = field(default_factory=dict)
    #: la clave del frontmatter de las unidades que se busca con el valor de la celda (`proyecto`)
    buscar: str = ""


@dataclass(frozen=True, slots=True)
class Mapa:
    nombre: str
    secciones: tuple[re.Pattern[str], ...]
    campos: dict[str, Campo] = field(default_factory=dict)
    #: para listas en vez de tablas: cada línea que calza es una fila, y sus grupos con nombre son sus columnas
    patron: re.Pattern[str] | None = None


#: sin mapa: las secciones `## Cronograma`, cada campo por el nombre de su columna
POR_DEFECTO = Mapa(nombre="", secciones=(re.compile(r"^#{2,4}\s+Cronograma\s*$", re.I),))


def _norm(texto: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn").strip()


def _campo(nombre: str, valor: object, donde: str) -> Campo:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        valor = str(valor)
    if isinstance(valor, str):
        return Campo(plantilla=valor) if "{" in valor else Campo(constante=valor)
    if not isinstance(valor, dict):
        raise ErrorDeMapa(f"{donde}.{nombre}: una columna ({{columna: …}}), una plantilla («{{A}} · {{B}}») o un valor")
    sobra = set(valor) - _CLAVES_CAMPO
    if sobra:
        raise ErrorDeMapa(f"{donde}.{nombre}: no conoce «{sorted(sobra)[0]}»")
    idioma = str(valor.get("idioma", "es"))
    formato = None
    if valor.get("formato"):
        try:
            formato = Patron(str(valor["formato"]), idioma=idioma)
        except ErrorDePatron as e:
            raise ErrorDeMapa(f"{donde}.{nombre}.formato: {e}") from None
    anio = valor.get("año", valor.get("anio"))
    if anio is not None and not (isinstance(anio, int) or (isinstance(anio, str) and anio.startswith("frontmatter:"))):
        raise ErrorDeMapa(f"{donde}.{nombre}.año: un número, o «frontmatter:<clave>»")
    valores = valor.get("valores", {})
    if not isinstance(valores, dict):
        raise ErrorDeMapa(f"{donde}.{nombre}.valores: un mapa de lo que dice la celda a lo que significa")
    return Campo(columna=str(valor.get("columna", "")), formato=formato, rango=str(valor.get("rango", "")), anio=anio,
                 valores={_norm(k): str(v) for k, v in valores.items()}, buscar=str(valor.get("buscar", "")))


def mapa_de(nombre: str, datos: object, donde: str = "") -> Mapa:
    """Un mapa leído de YAML (un dict), validado."""
    donde = donde or f"mapas.{nombre}"
    if not isinstance(datos, dict):
        raise ErrorDeMapa(f"{donde}: se esperaba un mapa con secciones y campos")
    sobra = set(datos) - {"secciones", "campos", "patron", "mapa"}
    if sobra:
        raise ErrorDeMapa(f"{donde}: no conoce «{sorted(sobra)[0]}»")
    secciones = datos.get("secciones")
    if secciones is None:
        regex = POR_DEFECTO.secciones
    else:
        lista = [secciones] if isinstance(secciones, str) else secciones
        if not isinstance(lista, list) or not lista or not all(isinstance(x, str) and x for x in lista):
            raise ErrorDeMapa(f"{donde}.secciones: una expresión (o una lista) para la línea del encabezado")
        try:
            regex = tuple(re.compile(x if x.startswith("^") else f"^{re.escape(x)}\\s*$", re.I) for x in lista)
        except re.error as e:
            raise ErrorDeMapa(f"{donde}.secciones: {e}") from None
    campos = datos.get("campos", {}) or {}
    if not isinstance(campos, dict):
        raise ErrorDeMapa(f"{donde}.campos: un mapa de campo a su origen")
    for c in campos:
        if c not in CAMPOS:
            raise ErrorDeMapa(f"{donde}.campos.{c}: no es un campo de una fecha ({', '.join(CAMPOS)})")
    patron = None
    if datos.get("patron"):
        try:
            patron = re.compile(str(datos["patron"]))
        except re.error as e:
            raise ErrorDeMapa(f"{donde}.patron: {e}") from None
        if not patron.groupindex:
            raise ErrorDeMapa(f"{donde}.patron: necesita grupos con nombre, (?P<inicio>…)")
    return Mapa(nombre=nombre, secciones=regex, campos={c: _campo(c, v, f"{donde}.campos") for c, v in campos.items()},
                patron=patron)


@dataclass(slots=True)
class Mapas:
    """Los mapas con nombre de los `.telar/fechas.yaml`, y qué documentos (globs desde la raíz) se leen con cuál."""

    por_nombre: dict[str, Mapa] = field(default_factory=dict)
    documentos: list[tuple[str, str]] = field(default_factory=list)
    #: lo que no se pudo leer: «archivo: por qué»
    fallas: list[str] = field(default_factory=list)

    def para(self, relativa: str, fm: dict) -> Mapa | None:
        """El mapa de un documento: el de su frontmatter (`fechas:`), si no el de `documentos:` que calce, si no
        ninguno (None: el de por defecto). Un nombre que no existe es una falla, y se lee sin mapa."""
        declarado = fm.get("fechas")
        if declarado is not None:
            try:
                return self._de_frontmatter(declarado)
            except ErrorDeMapa as e:
                self.fallas.append(f"{relativa}: {e}")
                return None
        for glob, nombre in self.documentos:
            if Path(relativa).match(glob) or relativa == glob:
                return self.por_nombre.get(nombre)
        return None

    def _de_frontmatter(self, declarado: object) -> Mapa:
        if isinstance(declarado, str):
            if declarado not in self.por_nombre:
                raise ErrorDeMapa(f"fechas: no hay un mapa «{declarado}» en .telar/fechas.yaml")
            return self.por_nombre[declarado]
        if isinstance(declarado, dict) and "mapa" in declarado:
            base = self._de_frontmatter(str(declarado["mapa"]))
            otro = mapa_de(base.nombre, {k: v for k, v in declarado.items() if k != "mapa"}, "fechas")
            return Mapa(nombre=base.nombre, secciones=otro.secciones if "secciones" in declarado else base.secciones,
                        campos={**base.campos, **otro.campos}, patron=otro.patron or base.patron)
        return mapa_de("(frontmatter)", declarado, "fechas")

    def con_documentos(self) -> list[str]:
        return [g for g, _ in self.documentos]


def cargar(config) -> Mapas:
    """Los `.telar/fechas.yaml` de la raíz y de los repositorios de `[repos]` que están dentro de ella: sus rutas pasan
    a ser relativas a la raíz. Un archivo mal escrito va a `fallas` y no se lleva a los demás."""
    from telar.perfil import carpeta_de_repo

    raiz = Path(config.raiz).expanduser().resolve()
    lugares: list[tuple[str, Path]] = [("", raiz)]
    for repo in getattr(config, "repos", ()) or ():
        try:
            carpeta = carpeta_de_repo(config, repo)
            relativa = carpeta.relative_to(raiz).as_posix()
        except (ValueError, OSError):
            continue
        if relativa not in ("", "."):
            lugares.append((relativa, carpeta))
    mapas = Mapas()
    for relativa, carpeta in lugares:
        archivo = carpeta / ARCHIVO
        if not archivo.is_file():
            continue
        nombre_archivo = f"{relativa}/{ARCHIVO}" if relativa else str(ARCHIVO)
        try:
            datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
            _sumar(mapas, datos, relativa)
        except (OSError, yaml.YAMLError, ErrorDeMapa) as e:
            mapas.fallas.append(f"{nombre_archivo}: {e}")
    return mapas


def _sumar(mapas: Mapas, datos: object, prefijo: str) -> None:
    if not isinstance(datos, dict):
        raise ErrorDeMapa("se esperaba un mapa con «mapas» y «documentos»")
    sobra = set(datos) - {"version", "mapas", "documentos"}
    if sobra:
        raise ErrorDeMapa(f"no conoce «{sorted(sobra)[0]}»")
    for nombre, cuerpo in (datos.get("mapas") or {}).items():
        mapas.por_nombre[str(nombre)] = mapa_de(str(nombre), cuerpo)
    for i, d in enumerate(datos.get("documentos") or []):
        if not isinstance(d, dict) or not isinstance(d.get("ruta"), str) or not isinstance(d.get("mapa"), str):
            raise ErrorDeMapa(f"documentos[{i}]: {{ruta: <glob>, mapa: <nombre>}}")
        if d["mapa"] not in mapas.por_nombre:
            raise ErrorDeMapa(f"documentos[{i}]: no hay un mapa «{d['mapa']}»")
        if d["ruta"].startswith("/") or ".." in Path(d["ruta"]).parts:
            raise ErrorDeMapa(f"documentos[{i}].ruta: relativa al repositorio, sin «..»")
        mapas.documentos.append((f"{prefijo}/{d['ruta']}" if prefijo else d["ruta"], d["mapa"]))


_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def frontmatter(texto: str) -> dict:
    """El frontmatter YAML de un documento, o {} si no tiene o no se entiende."""
    m = _FRONT.match(texto)
    if not m:
        return {}
    try:
        datos = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return datos if isinstance(datos, dict) else {}


def anio_de(campo: Campo, fm: dict, hoy: date) -> int:
    """El año que se le pone a una fecha que no lo trae."""
    if isinstance(campo.anio, int):
        return campo.anio
    if isinstance(campo.anio, str):
        valor = fm.get(campo.anio.split(":", 1)[1])
        if isinstance(valor, date):
            return valor.year
        if m := re.search(r"\b(\d{4})\b", str(valor or "")):
            return int(m.group(1))
    return hoy.year
