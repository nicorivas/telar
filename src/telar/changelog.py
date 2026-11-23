"""El CHANGELOG por fragmentos: cada hijo con rama propia escribe su entrada en un archivo suyo, y `telar hilo fusionar`
la junta en la sección [Unreleased] del CHANGELOG al fusionar.

Si dos ramas escribieran en CHANGELOG.md chocarían siempre (las dos agregan arriba, en [Unreleased]). Con fragmentos,
cada rama agrega un archivo distinto (`changelog.d/<rama>.md`), que no choca con nada, y la fusión lo mueve. Lo usa
`telar.ramas.fusionar`; un repositorio lo declara en `.telar/changelog.yaml` (docs/perfil.md, «El CHANGELOG por
fragmentos»). Sin la declaración no pasa nada distinto.

    decl = changelog.declaracion(texto_del_yaml)               # {archivo, carpeta, secciones, ancho, negrita}
    entradas = changelog.leer_fragmento(texto, "changelog.d/x.md", decl)  # {"Added": [líneas], …}
    nuevo = changelog.juntar(texto_del_changelog, [entradas], decl)

Un fragmento es un pedazo del CHANGELOG tal cual, con una o más secciones:

    ### Added

    - **La primera oración, en negrita.** Lo demás, con las líneas
      siguientes sangradas en dos espacios.

Cada sección va arriba de la suya en [Unreleased] (lo más nuevo, primero); si no está, se crea en el orden de
`secciones`, y si no hay [Unreleased], también.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

#: dónde un repositorio declara que su CHANGELOG va por fragmentos, desde su raíz
DECLARACION = Path(".telar") / "changelog.yaml"
#: las secciones de Keep a Changelog, en su orden
SECCIONES = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
#: lo que en la carpeta de los fragmentos no es un fragmento: lo que la explica
NO_FRAGMENTOS = {"readme.md"}

_SECCION = re.compile(r"^###\s+(.+?)\s*$")
_VERSION = re.compile(r"^##\s")
_UNRELEASED = re.compile(r"^##\s+\[unreleased\]", re.IGNORECASE)


class ErrorDeChangelog(ValueError):
    """Una declaración o un fragmento que no se entiende. `errores`: cada problema, con su archivo y su línea."""

    def __init__(self, mensaje: str, errores: list[str] | None = None) -> None:
        super().__init__(mensaje)
        self.errores = list(errores or [])


def declaracion(texto: str | None) -> dict | None:
    """Lo que dice `.telar/changelog.yaml` (su texto; None si no está): {archivo, carpeta, secciones, ancho, negrita}.
    None si no está. ErrorDeChangelog si está y no se entiende.

        archivo: CHANGELOG.md      # el changelog, desde la raíz del repositorio
        carpeta: changelog.d       # los fragmentos, uno por rama
        ancho: 120                 # opcional: el largo máximo de una línea
        negrita: true              # opcional: cada entrada empieza con su primera oración en negrita
        secciones: [Added, …]      # opcional: las que valen, en su orden (por defecto, las de Keep a Changelog)
    """
    if texto is None:
        return None
    import yaml

    try:
        datos = yaml.safe_load(texto) or {}
    except yaml.YAMLError as e:
        raise ErrorDeChangelog(f"{DECLARACION}: no lo entiendo ({e})") from None
    if not isinstance(datos, dict):
        raise ErrorDeChangelog(f"{DECLARACION}: tiene que ser un mapa con `archivo` y `carpeta`")
    salida = {}
    for clave in ("archivo", "carpeta"):
        valor = str(datos.get(clave) or "").strip().rstrip("/")
        if not valor:
            raise ErrorDeChangelog(f"{DECLARACION}: falta `{clave}`")
        if PurePosixPath(valor).is_absolute() or ".." in PurePosixPath(valor).parts:
            raise ErrorDeChangelog(f"{DECLARACION}: `{clave}` («{valor}») tiene que estar dentro del repositorio")
        salida[clave] = PurePosixPath(valor).as_posix()
    secciones = datos.get("secciones") or list(SECCIONES)
    if not isinstance(secciones, list) or not all(isinstance(s, str) and s.strip() for s in secciones):
        raise ErrorDeChangelog(f"{DECLARACION}: `secciones` es una lista de nombres")
    salida["secciones"] = [s.strip() for s in secciones]
    ancho = datos.get("ancho")
    if ancho is not None and (isinstance(ancho, bool) or not isinstance(ancho, int) or ancho < 20):
        raise ErrorDeChangelog(f"{DECLARACION}: `ancho` es un número (de 20 para arriba)")
    salida["ancho"] = ancho
    salida["negrita"] = bool(datos.get("negrita"))
    return salida


def de_la_carpeta(raiz: Path | str) -> dict | None:
    """La declaración de la copia de trabajo cuya raíz es `raiz` (lo que hay en disco, no en git); None si no hay, o si
    no se entiende (eso lo dice `telar hilo fusionar`)."""
    ruta = Path(raiz) / DECLARACION
    if not ruta.is_file():
        return None
    try:
        return declaracion(ruta.read_text(encoding="utf-8"))
    except (OSError, ErrorDeChangelog):
        return None


def es_fragmento(ruta: str, decl: dict) -> bool:
    """Si `ruta` (desde la raíz del repositorio) es un fragmento: un `.md` justo en la carpeta, que no sea su README."""
    p = PurePosixPath(ruta)
    return (p.parent.as_posix() == decl["carpeta"] and p.suffix.lower() == ".md"
            and p.name.lower() not in NO_FRAGMENTOS)


def leer_fragmento(texto: str, ruta: str, decl: dict) -> dict[str, list[str]]:
    """Las entradas de un fragmento, por sección y en su orden: {"Added": [líneas], …}, sin líneas en blanco.
    ErrorDeChangelog con cada problema (`errores`, «ruta:línea: qué») si está mal formado."""
    errores: list[str] = []
    secciones: dict[str, list[str]] = {}
    actual: str | None = None
    en_entrada = seccion_mala = False
    for n, linea in enumerate(texto.splitlines(), 1):
        linea = linea.rstrip()
        if not linea:
            continue

        def mal(que: str) -> None:
            errores.append(f"{ruta}:{n}: {que}")

        if decl.get("ancho") and len(linea) > decl["ancho"]:
            mal(f"la línea tiene {len(linea)} caracteres; el máximo es {decl['ancho']}")
        m = _SECCION.match(linea)
        if m:
            nombre = m.group(1)
            if nombre not in decl["secciones"]:
                mal(f"«### {nombre}» no es una sección: van {', '.join(decl['secciones'])}")
                actual, seccion_mala = None, True
            else:
                actual, seccion_mala = nombre, False
                secciones.setdefault(nombre, [])
            en_entrada = False
            continue
        if linea.startswith("#"):
            mal("en un fragmento solo van secciones («### Added»), no otros títulos")
            continue
        if actual is None:
            if not seccion_mala:
                mal("antes de la primera sección («### Added», «### Fixed»…) no va nada")
            continue
        if linea.startswith("- "):
            if decl.get("negrita") and not re.match(r"^- \*\*\S.*?\*\*", linea):
                mal("la entrada empieza con su primera oración en negrita: «- **Lo que cambió.** …»")
            secciones[actual].append(linea)
            en_entrada = True
        elif linea.startswith("  ") and en_entrada:
            secciones[actual].append(linea)
        else:
            mal("cada entrada empieza con «- » y sus líneas siguientes van sangradas en dos espacios")
    for nombre, lineas in secciones.items():
        if not lineas:
            errores.append(f"{ruta}: la sección «### {nombre}» no tiene entradas")
    if not secciones and not errores:
        errores.append(f"{ruta}: está vacío: lleva al menos una sección («### Added») con una entrada")
    if errores:
        raise ErrorDeChangelog(f"{ruta}: el fragmento del CHANGELOG está mal formado", errores)
    return secciones


def juntar(texto: str, fragmentos: list[dict[str, list[str]]], decl: dict) -> str:
    """El CHANGELOG (`texto`) con las entradas de cada fragmento arriba de su sección en [Unreleased], en el orden de
    los fragmentos; la sección que falta se crea en el orden de `secciones`, y [Unreleased], arriba de la primera
    versión si no está."""
    por_seccion: dict[str, list[str]] = {}
    for f in fragmentos:
        for seccion, lineas in f.items():
            por_seccion.setdefault(seccion, []).extend(lineas)
    if not por_seccion:
        return texto
    final = "\n" if texto.endswith("\n") else ""
    lineas = texto.splitlines()
    inicio = next((i for i, l in enumerate(lineas) if _UNRELEASED.match(l)), None)
    if inicio is None:
        # arriba de la primera versión; si no hay ninguna, al final
        primera = next((i for i, l in enumerate(lineas) if _VERSION.match(l)), None)
        if primera is None:
            while lineas and not lineas[-1].strip():
                lineas.pop()
            lineas += ["", "## [Unreleased]"]
            inicio = len(lineas) - 1
        else:
            lineas[primera:primera] = ["## [Unreleased]", ""]
            inicio = primera
        final = "\n"
    orden = {s: i for i, s in enumerate(decl["secciones"])}
    for seccion in sorted(por_seccion, key=lambda s: orden.get(s, len(orden))):
        nuevas = por_seccion[seccion]
        fin = next((i for i in range(inicio + 1, len(lineas)) if _VERSION.match(lineas[i])), len(lineas))
        titulos = [(i, _SECCION.match(lineas[i]).group(1)) for i in range(inicio + 1, fin) if _SECCION.match(lineas[i])]
        propia = next((i for i, nombre in titulos if nombre == seccion), None)
        if propia is not None:
            # arriba de lo que ya tiene: después del título y sus líneas en blanco
            donde = propia + 1
            while donde < fin and not lineas[donde].strip():
                donde += 1
            lineas[donde:donde] = nuevas
            continue
        # la sección no está: antes de la primera que va después de ella, o al final de [Unreleased]
        despues = next((i for i, nombre in titulos if orden.get(nombre, len(orden)) > orden.get(seccion, len(orden))),
                       None)
        bloque = [f"### {seccion}", "", *nuevas, ""]
        if despues is not None:
            lineas[despues:despues] = bloque
        else:
            # después de lo último que tiene [Unreleased], y una línea en blanco antes de lo que sigue
            donde = fin
            while donde > inicio + 1 and not lineas[donde - 1].strip():
                donde -= 1
            lineas[donde:donde] = ["", *bloque[:-1]]
            sigue = donde + len(bloque)
            if sigue < len(lineas) and lineas[sigue].strip():
                lineas.insert(sigue, "")
    return "\n".join(lineas) + final
