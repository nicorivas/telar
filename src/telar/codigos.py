"""Los códigos de una carpeta y de una conversación (docs/propuestas/codigos.md): `H3`, `PEN-07`, `REQ-03`, `T84`.

Un hilo que lleva un proyecto ordena su trabajo con códigos, los define en sus documentos y después los nombra en la
conversación. Nadie los declara: aquí se reconocen las tres formas en que un documento **define** uno,

    ### H3 — El equipo adopta si el piloto le ahorra tiempo      un título: su texto es la sección
    | PEN-07 | Mandar el acta | Ana | 12-nov |                  una fila con el código en la primera columna
    - **R2** — el proveedor no entrega a tiempo                  una viñeta en negrita

y dónde se **nombra** cada uno. De todo lo definido quedan solo los que salen de su archivo: los que se nombran en
otro documento de la carpeta o en la conversación. Los demás son rótulos de un documento (cada entrevista numera a su
gente desde `P01`), no cosas del proyecto.

Su **clase** es el prefijo (`PEN-`, `H`), con el nombre de la sección donde están la mayoría de sus definiciones
(«Pendientes»): así `H` es «Hipótesis» en un proyecto e «Hitos» en otro sin que nadie lo diga.

Cada archivo se lee una vez y se vuelve a leer solo si cambió su fecha o su tamaño (`_cache`); lo de una carpeta se
arma de eso en cada consulta. Sin red ni estado: lo usan `telar.servicios.codigos` (la orden, la API y el bus).
"""

from __future__ import annotations

import os
import re
import threading
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["CODIGO", "definiciones", "nombrados", "carpeta", "en_conversacion", "clase_de", "normalizar"]

#: un código: una a cuatro mayúsculas, quizás un guion, uno a cuatro dígitos (`H3`, `PEN-07`, `IND-020`, `T458`)
CODIGO = r"[A-Z]{1,4}-?\d{1,4}"
#: un código suelto en un texto: sin letras, dígitos ni guiones pegados (ni `ISO-14001`, ni `aH3`, ni `H3-b`)
_SUELTO = re.compile(rf"(?<![\w-])({CODIGO})(?![\w-])")
_TITULO = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
#: un título que empieza con un código: `### H3 — …`, `## **PEN-07**: …`
_DEF_TITULO = re.compile(rf"^(#{{1,6}})\s+(?:\*\*|`)?({CODIGO})(?:\*\*|`)?(?![\w-])(.*)$")
#: una fila de tabla con el código solo en la primera celda
_DEF_FILA = re.compile(rf"^\s*\|\s*(?:\*\*|`)?({CODIGO})(?:\*\*|`)?\s*\|")
#: una viñeta (o un ítem numerado) que empieza con el código en negrita: `- **R2** — …`, `1. **R2 — corto**: …`
_DEF_VINETA = re.compile(rf"^(\s*)(?:[-*+]|\d+[.)])\s+\*\*({CODIGO})(?![\w-])([^*]*)\*\*(.*)$")
_SEPARADOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_CERCO = re.compile(r"^\s*(```|~~~)")

#: cuánto texto se guarda de una definición (una sección larga se corta)
MAX_TEXTO = 4000
#: cuántas líneas de un archivo se anotan por código nombrado
MAX_LINEAS = 5
#: cuántos archivos se recorren en una carpeta, a lo más
MAX_ARCHIVOS = 5000
#: las carpetas que no se recorren (además de las ocultas)
SALTAR = frozenset({"node_modules", "__pycache__", "venv", "dist", "build"})


def normalizar(texto: str) -> str:
    """Para buscar: sin tildes, sin mayúsculas."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if unicodedata.category(c) != "Mn")


def clase_de(codigo: str) -> str:
    """El prefijo de un código: `PEN-07` → `PEN-`, `H3` → `H`."""
    return re.sub(r"\d+$", "", codigo)


def _numero(codigo: str) -> int:
    m = re.search(r"(\d+)$", codigo)
    return int(m.group(1)) if m else 0


def _limpio(texto: str) -> str:
    """Un pedazo de markdown como texto de una línea: sin énfasis, código, enlaces ni separadores al principio."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texto)
    t = re.sub(r"[*_`]{1,3}", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = " ".join(t.split())
    return t.lstrip(" —–-:.)|·").strip()


def _celdas(linea: str) -> list[str]:
    s = linea.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [_limpio(c) for c in re.split(r"(?<!\\)\|", s)]


#: las columnas que nombran lo que es una fila (la primera que calce, por su encabezado)
_COLUMNA_TITULO = re.compile(r"^(nombre|t[ií]tulo|qu[eé]|descripci[oó]n|pendiente|promesa|indicador|hip[oó]tesis|"
                             r"riesgo|requisito|decisi[oó]n|tema|asunto|acci[oó]n|tarea|name|title|description)\b", re.I)


def _titulo_de_fila(celdas: list[str], encabezado: list[str]) -> str:
    """Lo que es una fila: la celda de la columna que la nombra, si el encabezado tiene una; si no, la primera con
    algo después del código."""
    for j, nombre in enumerate(encabezado[1:], start=1):
        if _COLUMNA_TITULO.match(nombre) and j < len(celdas) and celdas[j]:
            return celdas[j]
    return next((c for c in celdas[1:] if c), "")


@dataclass
class Definicion:
    codigo: str
    #: dónde: la ruta del archivo (relativa a la carpeta, al armarla) y la línea (desde 1)
    archivo: str
    linea: int
    #: titulo, fila o viñeta
    forma: str
    #: lo que es, en una línea
    titulo: str
    #: la sección donde está (la de arriba que no es otro código): con ella se nombra su clase
    seccion: str = ""
    #: el texto de la definición: la sección entera, la viñeta con sus líneas, o la fila
    texto: str = ""
    #: en una fila, sus columnas con el nombre del encabezado
    campos: dict[str, str] = field(default_factory=dict)

    def como_json(self, *, con_texto: bool = True) -> dict:
        d = {"codigo": self.codigo, "archivo": self.archivo, "linea": self.linea, "forma": self.forma,
             "titulo": self.titulo, "seccion": self.seccion}
        if con_texto:
            d["texto"] = self.texto
            if self.campos:
                d["campos"] = self.campos
        return d


def definiciones(texto: str, archivo: str = "") -> list[Definicion]:
    """Los códigos que define un markdown, en orden, en sus tres formas. Lo de un bloque de código no cuenta."""
    lineas = texto.splitlines()
    salida: list[Definicion] = []
    #: los títulos abiertos: (nivel, texto, es un código)
    pila: list[tuple[int, str, bool]] = []
    #: la tabla en curso: su encabezado (None si la tabla no tiene)
    encabezado: list[str] | None = None
    en_tabla = False
    cerco = ""

    def seccion() -> str:
        return next((t for _, t, es in reversed(pila) if not es), "")

    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if (m := _CERCO.match(linea)) and (not cerco or m.group(1) == cerco):
            cerco = "" if cerco else m.group(1)
            en_tabla = False
            i += 1
            continue
        if cerco:
            i += 1
            continue
        # una tabla: su primera fila es el encabezado si la sigue un separador
        if linea.lstrip().startswith("|"):
            if not en_tabla:
                en_tabla = True
                if i + 1 < len(lineas) and _SEPARADOR.match(lineas[i + 1]):
                    encabezado = _celdas(linea)
                    i += 2
                    continue
                encabezado = None
            if (m := _DEF_FILA.match(linea)) and not _SEPARADOR.match(linea):
                celdas = _celdas(linea)
                nombres = encabezado or []
                campos = {}
                for j, valor in enumerate(celdas[1:], start=1):
                    if not valor:
                        continue
                    nombre = nombres[j] if j < len(nombres) and nombres[j] else f"columna {j + 1}"
                    campos[nombre] = valor
                titulo = _titulo_de_fila(celdas, nombres)
                salida.append(Definicion(m.group(1), archivo, i + 1, "fila", titulo[:160], seccion(),
                                         " · ".join(f"{k}: {v}" for k, v in campos.items())[:MAX_TEXTO], campos))
            i += 1
            continue
        en_tabla = False
        if (t := _TITULO.match(linea)):
            nivel = len(t.group(1))
            while pila and pila[-1][0] >= nivel:
                pila.pop()
            d = _DEF_TITULO.match(linea)
            if d:
                # su texto: hasta el próximo título de su nivel o más alto (fuera de un bloque de código)
                fin, adentro = i + 1, ""
                while fin < len(lineas):
                    if (c := _CERCO.match(lineas[fin])) and (not adentro or c.group(1) == adentro):
                        adentro = "" if adentro else c.group(1)
                    elif not adentro and (u := _TITULO.match(lineas[fin])) and len(u.group(1)) <= nivel:
                        break
                    fin += 1
                cuerpo = "\n".join(lineas[i + 1:fin]).strip()
                salida.append(Definicion(d.group(2), archivo, i + 1, "titulo", _limpio(d.group(3))[:160] or d.group(2),
                                         seccion(), cuerpo[:MAX_TEXTO]))
            pila.append((nivel, _limpio(t.group(2))[:60], bool(d)))
            i += 1
            continue
        # una viñeta que nombra varios en su negrita («**T309 y T159**: …») habla de ellos, no define uno
        if (v := _DEF_VINETA.match(linea)) and not _SUELTO.search(v.group(3)):
            sangria = len(v.group(1))
            corto, resto = _limpio(v.group(3)).rstrip(" :;.—–-"), _limpio(v.group(4))
            titulo = f"{corto}: {resto}" if corto and resto else (corto or resto)
            # sus líneas de continuación: las que siguen más adentro que la viñeta, hasta una línea en blanco o
            # la próxima viñeta de su nivel
            fin = i + 1
            while fin < len(lineas) and lineas[fin].strip() and (len(lineas[fin]) - len(lineas[fin].lstrip())) > sangria:
                fin += 1
            texto_v = "\n".join([titulo, *[x.strip() for x in lineas[i + 1:fin]]]).strip()
            salida.append(Definicion(v.group(2), archivo, i + 1, "viñeta", titulo[:160] or v.group(2), seccion(),
                                     texto_v[:MAX_TEXTO]))
        i += 1
    return salida


def nombrados(texto: str) -> dict[str, list[int]]:
    """Los códigos que nombra un texto, cada uno con las primeras líneas donde aparece (desde 1). Lo de un bloque de
    código también: ahí se nombran (una tabla de texto, un diagrama)."""
    salida: dict[str, list[int]] = {}
    for n, linea in enumerate(texto.splitlines(), start=1):
        for c in _SUELTO.findall(linea):
            lineas = salida.setdefault(c, [])
            if len(lineas) < MAX_LINEAS and (not lineas or lineas[-1] != n):
                lineas.append(n)
    return salida


# ── una carpeta ─────────────────────────────────────────────────────────────────────────────────

@dataclass
class _Leido:
    mtime: int
    tamano: int
    defs: list[Definicion]
    menciones: dict[str, list[int]]


#: ruta absoluta → lo leído de ella, mientras no cambie
_cache: dict[str, _Leido] = {}
_candado = threading.Lock()


def _leer(ruta: str, st: os.stat_result) -> _Leido:
    with _candado:
        previo = _cache.get(ruta)
    if previo and previo.mtime == st.st_mtime_ns and previo.tamano == st.st_size:
        return previo
    try:
        texto = Path(ruta).read_text(encoding="utf-8", errors="replace")
    except OSError:
        texto = ""
    leido = _Leido(st.st_mtime_ns, st.st_size, definiciones(texto), nombrados(texto))
    with _candado:
        _cache[ruta] = leido
    return leido


def _archivos(raiz: Path) -> tuple[list[tuple[str, os.stat_result]], bool]:
    """Los .md de la carpeta (sin las ocultas ni las de `SALTAR`), con su stat; y si se cortó en `MAX_ARCHIVOS`."""
    salida: list[tuple[str, os.stat_result]] = []
    for d, ds, fs in os.walk(raiz):
        ds[:] = sorted(x for x in ds if not x.startswith(".") and x not in SALTAR)
        for f in sorted(fs):
            if not f.endswith(".md"):
                continue
            p = os.path.join(d, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            salida.append((p, st))
            if len(salida) >= MAX_ARCHIVOS:
                return salida, True
    return salida, False


@dataclass
class Carpeta:
    """Lo de una carpeta: por código, sus definiciones (la del archivo más reciente primero) y dónde se nombra."""
    raiz: Path
    archivos: int
    truncado: bool
    #: código → sus definiciones, la del archivo más reciente primero
    defs: dict[str, list[Definicion]]
    #: código → {archivo relativo: líneas} de los archivos que lo nombran
    menciones: dict[str, dict[str, list[int]]]
    #: prefijo → el archivo donde se define la mayor parte de su clase (lo calcula `principal`)
    _de_clase: dict[str, str] | None = None

    def fuera(self, codigo: str) -> dict[str, list[int]]:
        """Los archivos que lo nombran sin definirlo, con sus líneas."""
        propios = {d.archivo for d in self.defs.get(codigo, ())}
        return {a: ls for a, ls in self.menciones.get(codigo, {}).items() if a not in propios}

    def viajan(self) -> set[str]:
        """Los códigos definidos que se nombran fuera de su archivo."""
        return {c for c in self.defs if self.fuera(c)}

    def principal(self, codigo: str) -> Definicion:
        """La definición que vale de un código con varias: la del archivo donde se define la mayor parte de su clase
        (las promesas viven en `promesas.md`, aunque una reunión numere sus cadenas `P-01`), y si no está ahí, la del
        archivo más reciente."""
        ds = self.defs[codigo]
        if len(ds) > 1:
            if self._de_clase is None:
                cuenta: dict[str, Counter[str]] = defaultdict(Counter)
                for c, xs in self.defs.items():
                    for d in xs:
                        cuenta[clase_de(c)][d.archivo] += 1
                self._de_clase = {k: v.most_common(1)[0][0] for k, v in cuenta.items()}
            casa = self._de_clase.get(clase_de(codigo))
            return next((d for d in ds if d.archivo == casa), ds[0])
        return ds[0]


def carpeta(raiz: Path) -> Carpeta:
    raiz = Path(raiz)
    lista, truncado = _archivos(raiz)
    defs: dict[str, list[tuple[int, Definicion]]] = defaultdict(list)
    menciones: dict[str, dict[str, list[int]]] = defaultdict(dict)
    for ruta, st in lista:
        leido = _leer(ruta, st)
        rel = os.path.relpath(ruta, raiz)
        for d in leido.defs:
            defs[d.codigo].append((st.st_mtime_ns, Definicion(**{**d.__dict__, "archivo": rel})))
        for c, ls in leido.menciones.items():
            menciones[c][rel] = ls
    ordenadas = {c: [d for _, d in sorted(xs, key=lambda x: (-x[0], x[1].archivo, x[1].linea))] for c, xs in defs.items()}
    return Carpeta(raiz, len(lista), truncado, ordenadas, dict(menciones))


# ── una conversación ───────────────────────────────────────────────────────────────────────────

@dataclass
class Nombrado:
    codigo: str
    #: cuántos mensajes lo nombran, y el índice del último
    veces: int
    ultimo: int
    #: lo que decía el último mensaje que lo nombra, alrededor del código
    extracto: str


def _extracto(texto: str, codigo: str, ancho: int = 220) -> str:
    m = re.search(rf"(?<![\w-]){re.escape(codigo)}(?![\w-])", texto)
    if not m:
        return ""
    a = max(0, m.start() - ancho // 2)
    b = min(len(texto), m.end() + ancho // 2)
    t = " ".join(texto[a:b].split())
    return ("…" if a else "") + t + ("…" if b < len(texto) else "")


def en_conversacion(mensajes: list[dict]) -> list[Nombrado]:
    """Los códigos que nombra una conversación (`[{quien, texto}…]`), todos, el último nombrado primero."""
    veces: Counter[str] = Counter()
    ultimo: dict[str, int] = {}
    for n, m in enumerate(mensajes):
        for c in set(_SUELTO.findall(str(m.get("texto", "")))):
            veces[c] += 1
            ultimo[c] = n
    salida = [Nombrado(c, veces[c], ultimo[c], _extracto(str(mensajes[ultimo[c]].get("texto", "")), c)) for c in veces]
    return sorted(salida, key=lambda x: (-x.ultimo, x.codigo))


# ── lo que se muestra ──────────────────────────────────────────────────────────────────────────

def clases(c: Carpeta, codigos: set[str]) -> list[dict]:
    """Las clases de esos códigos: su prefijo, el nombre de la sección donde están la mayoría, su archivo y cuántos."""
    por: dict[str, list[Definicion]] = defaultdict(list)
    for codigo in codigos:
        if c.defs.get(codigo):
            por[clase_de(codigo)].append(c.principal(codigo))
    salida = []
    for prefijo, ds in por.items():
        secciones = Counter(d.seccion for d in ds if d.seccion)
        archivos = Counter(d.archivo for d in ds)
        salida.append({"prefijo": prefijo, "nombre": secciones.most_common(1)[0][0] if secciones else "",
                       "archivo": archivos.most_common(1)[0][0], "cuantos": len(ds)})
    return sorted(salida, key=lambda x: (-x["cuantos"], x["prefijo"]))


def ordenados(codigos) -> list[str]:
    """En el orden de lectura: por prefijo, y dentro de uno por número (`H2` antes que `H10`)."""
    return sorted(codigos, key=lambda c: (clase_de(c), _numero(c), c))


def coincide(consulta: str, *textos: str) -> bool:
    """Si todas las palabras de la consulta están en alguno de los textos (sin tildes ni mayúsculas)."""
    palabras = normalizar(consulta).split()
    junto = normalizar(" ".join(textos))
    return all(p in junto for p in palabras)
