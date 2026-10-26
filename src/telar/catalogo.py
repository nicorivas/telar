"""El catálogo de módulos: dónde encontrarlos, revisados, para instalarlos por su nombre.

Un catálogo es un archivo con nombre fijo, `.telar/catalogo.toml`, en la raíz de un repositorio (al lado de
`perfil.yaml` y `equipo.yaml`): el oficial (`nicorivas/telar-modulos`), el de un equipo (el suyo, en su repo) o
cualquier otro. Su forma (docs/modulos.md):

    version = 1                              # la del formato

    [modulos.nino34]
    descripcion = "El índice del Niño 3.4, cada mañana."
    fuente = "https://github.com/nicorivas/telar-nino34"
    version = "v0.1.0"                       # una etiqueta o un commit: lo que se instala es esto, no la rama
    autor = "nicorivas"
    etiquetas = ["clima", "datos"]
    telar = ">=0.6"                          # la versión mínima de telar (opcional)

    [modulos.nino34.permisos]                # lo que pide, como en su modulo.toml (se compara al revisarlo)
    red = ["psl.noaa.gov"]

De dónde se leen, en orden (el primero que nombra un módulo gana):

    oficial      el de telar, `CATALOGO_OFICIAL` (se baja con caché de `CADA` segundos): «revisado»
    equipo       el `.telar/catalogo.toml` de cada repo de `[repos]` (y de la raíz): «del equipo»
    los demás    `[catalogos] fuentes` en la configuración, una URL o una ruta: «sin revisar»

`[catalogos] oficial = false` deja fuera el oficial. La página instala solo de un catálogo revisado o del
equipo; uno sin revisar se instala desde la terminal (`telar modulos instalar <nombre>`).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import tomllib
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

#: dónde vive un catálogo en un repositorio
NOMBRE_ARCHIVO = ".telar/catalogo.toml"
#: el catálogo de telar: lo que se mergea ahí, lo revisó quien mantiene telar
CATALOGO_OFICIAL = "https://raw.githubusercontent.com/nicorivas/telar-modulos/main/.telar/catalogo.toml"
#: el repositorio del oficial: a él van los PR de `telar modulos publicar`
REPO_OFICIAL = "nicorivas/telar-modulos"
#: cada cuánto se baja de nuevo uno remoto, si nadie fuerza (segundos)
CADA = 3600
#: la versión del formato que entiende este telar
FORMATO = 1
#: un nombre de módulo: el de su orden (`telar <nombre> …`)
NOMBRE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
#: lo que puede ser `version`: una etiqueta (sin espacios ni `..`) o un commit
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
CLAVES = ("descripcion", "fuente", "version", "autor", "etiquetas", "telar", "permisos")


class ErrorDeCatalogo(ValueError):
    """Un catálogo que no se lee, o una entrada que no sirve. El mensaje es para la persona."""


@dataclass(frozen=True)
class Entrada:
    nombre: str
    descripcion: str
    fuente: str
    version: str
    autor: str = ""
    etiquetas: tuple[str, ...] = ()
    telar: str = ""
    permisos: dict | None = field(default=None, compare=False, hash=False)
    #: de qué catálogo vino: «oficial», «equipo:<repo>» o la ubicación de otro
    catalogo: str = ""
    #: oficial, equipo o sin revisar
    confianza: str = "sin revisar"

    def como_json(self) -> dict:
        return {"nombre": self.nombre, "descripcion": self.descripcion, "fuente": self.fuente, "version": self.version,
                "autor": self.autor, "etiquetas": list(self.etiquetas), "telar": self.telar, "permisos": self.permisos,
                "catalogo": self.catalogo, "confianza": self.confianza}


def _version_min(texto: str) -> tuple[int, ...]:
    m = re.fullmatch(r">=\s*(\d+(?:\.\d+){0,2})", texto.strip())
    if not m:
        raise ErrorDeCatalogo(f"telar: se esperaba «>=0.6», llegó «{texto}»")
    return tuple(int(x) for x in m.group(1).split("."))


def le_sirve(e: Entrada, version_telar: str) -> bool:
    """Si este telar tiene la versión que el módulo pide (`telar = ">=0.6"`); sin pedido, sí."""
    if not e.telar:
        return True
    try:
        pide = _version_min(e.telar)
        tiene = tuple(int(x) for x in version_telar.split(".")[:3])
    except (ErrorDeCatalogo, ValueError):
        return False
    return tiene[:len(pide)] >= pide


def leer_texto(texto: str, *, catalogo: str = "", confianza: str = "sin revisar") -> tuple[list[Entrada], list[str]]:
    """Las entradas válidas de un catálogo y los problemas, una frase por cosa. ErrorDeCatalogo si el archivo
    entero no se lee (no es TOML, o es de un formato más nuevo)."""
    try:
        datos = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as e:
        raise ErrorDeCatalogo(f"no es TOML: {e}") from None
    formato = datos.get("version", FORMATO)
    if formato != FORMATO:
        raise ErrorDeCatalogo(f"version {formato!r}: este telar entiende el formato {FORMATO}")
    sobra = set(datos) - {"version", "modulos"}
    problemas = [f"«{k}»: no lo conozco (¿de un telar más nuevo?): se ignora" for k in sorted(sobra)]
    modulos = datos.get("modulos", {})
    if not isinstance(modulos, dict):
        raise ErrorDeCatalogo("[modulos] tiene que ser una tabla: [modulos.<nombre>]")
    entradas = []
    for nombre, d in modulos.items():
        try:
            entradas.append(_entrada(nombre, d, catalogo, confianza))
        except ErrorDeCatalogo as e:
            problemas.append(f"{nombre}: {e}: se deja fuera")
    return entradas, problemas


def _entrada(nombre: str, d, catalogo: str, confianza: str) -> Entrada:
    if not NOMBRE.fullmatch(str(nombre)):
        raise ErrorDeCatalogo("el nombre va en minúsculas, números, - y _, empezando por una letra")
    if not isinstance(d, dict):
        raise ErrorDeCatalogo("se esperaba una tabla")
    sobra = set(d) - set(CLAVES)
    if sobra:
        raise ErrorDeCatalogo(f"claves que no conozco: {', '.join(sorted(sobra))}")
    texto = lambda k, obligatorio=True: _texto(d, k, obligatorio)  # noqa: E731
    fuente, version = texto("fuente"), texto("version")
    if not re.match(r"^(https://|git@|ssh://)", fuente):
        raise ErrorDeCatalogo(f"fuente: se esperaba la URL de un repositorio git (https://…), llegó «{fuente}»")
    if not REF.fullmatch(version) or ".." in version:
        raise ErrorDeCatalogo(f"version: una etiqueta o un commit, llegó «{version}»")
    etiquetas = d.get("etiquetas", [])
    if not isinstance(etiquetas, list) or not all(isinstance(x, str) and x.strip() for x in etiquetas):
        raise ErrorDeCatalogo("etiquetas: una lista de palabras")
    minima = texto("telar", False)
    if minima:
        _version_min(minima)
    permisos = d.get("permisos")
    if permisos is not None and not isinstance(permisos, dict):
        raise ErrorDeCatalogo("permisos: una tabla, como la de su modulo.toml")
    return Entrada(nombre=nombre, descripcion=texto("descripcion"), fuente=fuente, version=version,
                   autor=texto("autor", False), etiquetas=tuple(x.strip() for x in etiquetas), telar=minima,
                   permisos=permisos, catalogo=catalogo, confianza=confianza)


def _texto(d: dict, k: str, obligatorio: bool) -> str:
    v = d.get(k, "")
    if not isinstance(v, str) or (obligatorio and not v.strip()):
        raise ErrorDeCatalogo(f"{k}: se esperaba un texto" + ("" if not obligatorio else ", y falta"))
    if any(ord(c) < 32 for c in v):
        raise ErrorDeCatalogo(f"{k}: trae caracteres de control")
    return v.strip()


# ── de dónde se leen ───────────────────────────────────────────────────────────

def fuentes(config) -> list[tuple[str, str, str]]:
    """(nombre, ubicación, confianza) de los catálogos que se leen, en orden: el oficial, los de los repos
    (y la raíz) y los de `[catalogos] fuentes`."""
    salida: list[tuple[str, str, str]] = []
    if getattr(config, "catalogos_oficial", True):
        salida.append(("oficial", CATALOGO_OFICIAL, "oficial"))
    from telar import perfil as mod_perfil

    vistos = set()
    raiz = Path(getattr(config, "raiz", ".")).expanduser()
    repos = [("raíz", raiz)]
    for r in getattr(config, "repos", ()) or ():
        try:
            repos.append((r.nombre, mod_perfil.carpeta_de_repo(config, r)))
        except (OSError, ValueError):
            continue
    for nombre, carpeta in repos:
        archivo = Path(carpeta) / NOMBRE_ARCHIVO
        try:
            real = archivo.resolve()
        except OSError:
            continue
        if real in vistos or not archivo.is_file():
            continue
        vistos.add(real)
        salida.append((f"equipo:{nombre}", str(archivo), "equipo"))
    for f in getattr(config, "catalogos_fuentes", ()) or ():
        salida.append((f, f, "sin revisar"))
    return salida


def _bajar(url: str) -> str:
    pedido = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "telar"})
    with urllib.request.urlopen(pedido, timeout=10) as r:  # noqa: S310 - las URL son de la configuración
        return r.read().decode("utf-8")


def _texto_de(config, ubicacion: str, *, forzar: bool, ahora: float, bajar=None) -> tuple[str, str]:
    """(texto, problema) de un catálogo: una ruta se lee; una URL, de la caché si es reciente. Si una URL no
    responde, la caché vieja sirve, con el problema dicho."""
    if not ubicacion.startswith(("https://", "http://")):
        try:
            return Path(ubicacion).expanduser().read_text(encoding="utf-8"), ""
        except OSError as e:
            return "", f"no se lee: {e}"
    cache = Path(config.estado) / "catalogos" / (hashlib.sha1(ubicacion.encode()).hexdigest()[:16] + ".json")
    try:
        guardado = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardado = {}
    if not forzar and guardado.get("texto") is not None and ahora - float(guardado.get("cuando", 0)) < CADA:
        return guardado["texto"], ""
    try:
        texto = (bajar or _bajar)(ubicacion)
    except Exception as e:  # noqa: BLE001 - sin red, queda lo de antes
        problema = f"no responde ({type(e).__name__}: {e})"[:200]
        return guardado.get("texto") or "", problema + ("; uso lo de antes" if guardado.get("texto") else "")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"texto": texto, "cuando": ahora}), encoding="utf-8")
    except OSError:
        pass
    return texto, ""


def cargar(config, *, forzar: bool = False, ahora: float | None = None, bajar=None) -> dict:
    """{entradas: [Entrada], problemas: [texto], catalogos: [{nombre, ubicacion, confianza, problema}]}. Un
    nombre que aparece en dos catálogos queda con el primero, y se dice."""
    ahora = ahora if ahora is not None else time.time()
    entradas: dict[str, Entrada] = {}
    problemas, catalogos = [], []
    for nombre, ubicacion, confianza in fuentes(config):
        texto, problema = _texto_de(config, ubicacion, forzar=forzar, ahora=ahora, bajar=bajar)
        catalogos.append({"nombre": nombre, "ubicacion": ubicacion, "confianza": confianza, "problema": problema})
        if problema:
            problemas.append(f"{nombre}: {problema}")
        if not texto:
            continue
        try:
            leidas, malas = leer_texto(texto, catalogo=nombre, confianza=confianza)
        except ErrorDeCatalogo as e:
            problemas.append(f"{nombre}: {e}")
            continue
        problemas.extend(f"{nombre}: {x}" for x in malas)
        for e in leidas:
            if e.nombre in entradas:
                problemas.append(f"{nombre}: «{e.nombre}» ya viene de {entradas[e.nombre].catalogo}: queda ese")
                continue
            entradas[e.nombre] = e
    return {"entradas": list(entradas.values()), "problemas": problemas, "catalogos": catalogos}


def buscar(config, nombre: str, **kw) -> Entrada | None:
    return next((e for e in cargar(config, **kw)["entradas"] if e.nombre == nombre), None)


# ── revisar uno: lo que corre la acción del repositorio de un catálogo ──────────

def revisar_archivo(ruta: Path, *, resolver: bool = False) -> list[str]:
    """Los problemas de un catálogo, para quien lo mantiene (y para la revisión de un PR). Con `resolver`, además
    baja cada módulo en su versión y comprueba que su `modulo.toml` se lea, se llame igual, traiga `[permisos]` y
    que lo que el catálogo dice que pide sea lo que pide. Vacío: está bien."""
    try:
        entradas, problemas = leer_texto(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ErrorDeCatalogo) as e:
        return [f"{ruta}: {e}"]
    if not resolver:
        return problemas
    from telar import modulos as mod_modulos

    for e in entradas:
        try:
            m, anotar = mod_modulos.preparar(e.fuente, nombre=e.nombre, ref=e.version)
        except mod_modulos.ErrorDeModulo as ex:
            problemas.append(f"{e.nombre}: no se baja en {e.version}: {ex}")
            continue
        try:
            if m.permisos is None:
                problemas.append(f"{e.nombre}: su modulo.toml no trae [permisos]: no entra a un catálogo")
            elif e.permisos is not None and mod_modulos.permisos_json(mod_modulos._permisos(e.nombre, e.permisos)) \
                    != mod_modulos.permisos_json(m.permisos):
                problemas.append(f"{e.nombre}: lo que el catálogo dice que pide no es lo que pide su modulo.toml "
                                 f"({'; '.join(m.pide)})")
        finally:
            import shutil

            shutil.rmtree(anotar.get("provisorio", ""), ignore_errors=True) if anotar.get("provisorio") else None
    return problemas


def entrada_toml(e: dict) -> str:
    """Una entrada como va en el catálogo: para `telar modulos publicar`."""
    lineas = [f"[modulos.{e['nombre']}]"]
    for k in ("descripcion", "fuente", "version", "autor"):
        if e.get(k):
            lineas.append(f"{k} = {json.dumps(e[k], ensure_ascii=False)}")
    if e.get("etiquetas"):
        lineas.append(f"etiquetas = {json.dumps(list(e['etiquetas']), ensure_ascii=False)}")
    if e.get("telar"):
        lineas.append(f"telar = {json.dumps(e['telar'])}")
    permisos = e.get("permisos") or {}
    if permisos:
        lineas += ["", f"[modulos.{e['nombre']}.permisos]"]
        for k, v in permisos.items():
            if k in ("otros",) or v in (None, [], {}):
                continue
            lineas.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lineas) + "\n"
