"""Leer un documento como lo declara el perfil, y devolver una `Ficha`.

El perfil dice qué secciones tiene un documento y de qué tipo es cada una; aquí se
cumple esa declaración sobre el texto real. Nada de esto sabe qué es un proyecto:
recibe un `Arquetipo` y un archivo, y devuelve `telar.modelo.Ficha`.

Dos formas de encontrar una sección:

  * **anclada** — la sección declara `encabezado`, una expresión regular contra la
    línea del encabezado. El cuerpo llega hasta el siguiente encabezado de nivel
    igual o mayor (`## Estado` termina en el siguiente `##` o `#`, y se queda con
    sus `###`).
  * **sin anclar** — la sección no declara `encabezado`: se busca en todo el
    documento lo primero que calce con el tipo. Es lo que hace posible la
    convención mínima, que no sabe cómo se llaman las secciones de nadie.

El front matter YAML (`---` … `---` al principio) se descuenta antes de leer: si
no, el primer párrafo de cualquier documento sería su metadata.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from telar.modelo import Ficha, Pendiente
from telar.perfil import Arquetipo, Perfil, Seccion

__all__ = [
    "leer",
    "parsear",
    "limpiar",
    "indice",
    "ubicar",
    "ficha_de",
]

_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$")
_VINETA = re.compile(r"^\s*[-*+]\s+(?:\[([ xX>~])\]\s*)?(.*)$")
_FILA = re.compile(r"^\s*\|(.+)\|\s*$")
_SEPARADOR = re.compile(r"^[\s|:-]+$")
_FRONT = re.compile(r"\A---\n.*?\n---\n", re.S)


def limpiar(texto: str) -> str:
    """Saca el adorno de markdown que estorba para leer: negritas, enlaces, comentarios."""
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    texto = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"(?<!\w)[_*](\S.*?\S)[_*](?!\w)", r"\1", texto)
    return texto.strip(" \t`*_>").strip()


# ── partir el documento ─────────────────────────────────────────────────────────

def _sin_front(texto: str) -> str:
    return _FRONT.sub("", texto, count=1)


def _bloques(lineas: list[str]) -> list[tuple[int, str, list[str]]]:
    """(nivel, línea del encabezado, cuerpo) por cada sección, más el preámbulo.

    El preámbulo —lo que va antes del primer encabezado— es un bloque de nivel 0 con
    encabezado vacío. El cuerpo de un encabezado llega hasta el siguiente de nivel
    igual o mayor, así que una sección se queda con sus subsecciones.
    """
    bloques: list[tuple[int, str, list[str]]] = []
    nivel, encabezado, cuerpo = 0, "", []
    for linea in lineas:
        m = _ENCABEZADO.match(linea)
        if m:
            bloques.append((nivel, encabezado, cuerpo))
            nivel, encabezado, cuerpo = len(m.group(1)), linea, []
            continue
        cuerpo.append(linea)
    bloques.append((nivel, encabezado, cuerpo))

    # el cuerpo de cada bloque absorbe los bloques de nivel mayor que le siguen
    salida: list[tuple[int, str, list[str]]] = []
    for i, (niv, enc, cue) in enumerate(bloques):
        completo = list(cue)
        for niv2, enc2, cue2 in bloques[i + 1:]:
            if niv2 <= niv or niv == 0:
                break
            completo.append(enc2)
            completo.extend(cue2)
        salida.append((niv, enc, completo))
    return salida


# ── extraer cada tipo ───────────────────────────────────────────────────────────

def _es_texto(linea: str) -> bool:
    t = linea.strip()
    return bool(t) and not t.startswith(("-", "*", "+", "|", ">", "#", "<!--", "```"))


def _linea(cuerpo: list[str]) -> str:
    for linea in cuerpo:
        if _es_texto(linea):
            return limpiar(linea)
    return ""


def _parrafo(cuerpo: list[str]) -> str:
    juntas: list[str] = []
    for linea in cuerpo:
        if _es_texto(linea):
            juntas.append(linea.strip())
        elif juntas:
            break
    return limpiar(" ".join(juntas))


def _texto(cuerpo: list[str]) -> str:
    return "\n".join(cuerpo).strip()


def _lista(cuerpo: list[str], maximo: int) -> tuple[str, ...]:
    salida = []
    for linea in cuerpo:
        m = _VINETA.match(linea)
        if m:
            valor = limpiar(m.group(2))
            if valor:
                salida.append(valor)
    return tuple(salida[:maximo] if maximo else salida)


def _casillas(cuerpo: list[str], maximo: int, origen: str) -> tuple[Pendiente, ...]:
    salida = []
    for linea in cuerpo:
        m = _VINETA.match(linea)
        if not m or m.group(1) is None:
            continue
        marca = m.group(1).lower()
        valor = limpiar(m.group(2))
        if not valor:
            continue
        salida.append(
            Pendiente(
                texto=valor,
                hecho=marca == "x",
                en_curso=marca == ">",
                origen=origen,
            )
        )
    return tuple(salida[:maximo] if maximo else salida)


def _tabla(cuerpo: list[str], maximo: int) -> dict[str, str]:
    filas: list[list[str]] = []
    for linea in cuerpo:
        m = _FILA.match(linea)
        if not m:
            if filas:
                break  # la tabla terminó; otra tabla más abajo no es esta
            continue
        if _SEPARADOR.match(linea):
            continue
        celdas = [limpiar(c) for c in m.group(1).split("|")]
        if len(celdas) >= 2 and celdas[0]:
            filas.append(celdas)
    if len(filas) > 1:
        # la primera fila es cabecera solo si la de abajo era el separador `|---|---|`
        indices = [i for i, l in enumerate(cuerpo) if _FILA.match(l)]
        if len(indices) > 1 and _SEPARADOR.match(cuerpo[indices[1]]):
            filas = filas[1:]
    if maximo:
        filas = filas[:maximo]
    return {f[0]: f[1] for f in filas}


def _valor(seccion: Seccion, cuerpo: list[str], captura: str | None):
    if seccion.tipo == "linea":
        return limpiar(captura) if captura else _linea(cuerpo)
    if seccion.tipo == "parrafo":
        return _parrafo(cuerpo)
    if seccion.tipo == "texto":
        return _texto(cuerpo)
    if seccion.tipo == "lista":
        return _lista(cuerpo, seccion.maximo)
    if seccion.tipo == "casillas":
        return _casillas(cuerpo, seccion.maximo, seccion.nombre)
    if seccion.tipo == "tabla":
        return _tabla(cuerpo, seccion.maximo)
    return _texto(cuerpo)  # pragma: no cover - `perfil` no deja llegar otro tipo


def _vacio(valor) -> bool:
    return valor in ("", (), {}, None)


def _buscar(seccion: Seccion, bloques: list[tuple[int, str, list[str]]]):
    """El valor de una sección: anclada por su encabezado, o lo primero que calce."""
    patron = seccion.patron
    if patron is not None:
        for _, encabezado, cuerpo in bloques:
            m = patron.search(encabezado) if encabezado else None
            if m:
                captura = m.group(1) if m.re.groups else None
                return _valor(seccion, cuerpo, captura)
        return None

    # sin anclar: el documento entero para `texto`, y si no, lo primero que calce
    if seccion.tipo == "texto":
        todo = [l for _, enc, cue in bloques for l in ([enc] if enc else []) + cue]
        return _valor(seccion, todo, None)
    for _, encabezado, cuerpo in bloques:
        if seccion.tipo == "linea" and encabezado:
            m = _ENCABEZADO.match(encabezado)
            return limpiar(m.group(2)) if m else ""
        valor = _valor(seccion, cuerpo, None)
        if not _vacio(valor):
            return valor
    return None


# ── la ficha ────────────────────────────────────────────────────────────────────

def parsear(
    texto: str,
    arquetipo: Arquetipo,
    *,
    documento: Path | None = None,
    leida: datetime | None = None,
) -> Ficha:
    """Arma la `Ficha` de un texto según las secciones que declara el arquetipo."""
    bloques = _bloques(_sin_front(texto).splitlines())

    titulo, estado = "", ""
    pendientes: tuple[Pendiente, ...] = ()
    secciones: dict[str, object] = {}
    faltan: list[str] = []

    for seccion in arquetipo.secciones:
        valor = _buscar(seccion, bloques)
        if valor is None or _vacio(valor):
            if seccion.requerida:
                faltan.append(seccion.nombre)
            if valor is None:
                continue
        if seccion.nombre == "titulo":
            titulo = valor if isinstance(valor, str) else str(valor)
        elif seccion.nombre == "estado":
            estado = valor if isinstance(valor, str) else str(valor)
        elif seccion.nombre == "pendientes":
            pendientes = _como_pendientes(valor, seccion.nombre)
        else:
            secciones[seccion.nombre] = valor

    nota = ""
    if faltan:
        nota = "falta la sección requerida: " + ", ".join(faltan)
    elif not arquetipo.secciones:
        nota = f"el arquetipo «{arquetipo.nombre}» no declara secciones"

    return Ficha(
        documento=documento,
        titulo=titulo,
        estado=estado,
        pendientes=pendientes,
        secciones=secciones,
        leida=leida or datetime.now(),
        nota=nota,
    )


def _como_pendientes(valor, origen: str) -> tuple[Pendiente, ...]:
    """`pendientes` puede declararse `casillas` (lo normal) o `lista`; ambas sirven."""
    if isinstance(valor, tuple) and all(isinstance(v, Pendiente) for v in valor):
        return valor
    if isinstance(valor, (tuple, list)):
        return tuple(Pendiente(texto=str(v), origen=origen) for v in valor)
    if isinstance(valor, str) and valor:
        return (Pendiente(texto=valor, origen=origen),)
    return ()


def leer(documento: Path, arquetipo: Arquetipo) -> Ficha:
    """La ficha de un documento. Si no se puede leer, una ficha vacía que dice por qué."""
    documento = Path(documento)
    if not documento.is_file():
        return Ficha(documento=documento, nota=f"no existe {documento}")
    try:
        texto = documento.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return Ficha(documento=documento, nota=f"no se pudo leer: {e}")
    return parsear(texto, arquetipo, documento=documento)


# ── de una ruta a su arquetipo ──────────────────────────────────────────────────

def indice(perfil: Perfil, raiz: Path) -> dict[str, tuple[Arquetipo, Path]]:
    """Las unidades de trabajo del repositorio: ruta relativa → (arquetipo, documento).

    La clave es lo que se vincula a un hilo: la carpeta, en los arquetipos por
    carpeta; el archivo mismo, en los demás. Resolver el glob cuesta, así que quien
    necesite esto varias veces lo pide una y lo guarda.
    """
    raiz = Path(raiz)
    salida: dict[str, tuple[Arquetipo, Path]] = {}
    for arquetipo in perfil.arquetipos:
        for documento in arquetipo.documentos(raiz):
            unidad = arquetipo.carpeta_de(documento) if arquetipo.por_carpeta else documento
            try:
                clave = unidad.relative_to(raiz).as_posix()
            except ValueError:  # pragma: no cover - el glob no sale de la raíz
                continue
            salida.setdefault(clave, (arquetipo, documento))
    return salida


def ubicar(
    perfil: Perfil,
    raiz: Path,
    ruta: str | Path,
    *,
    mapa: dict[str, tuple[Arquetipo, Path]] | None = None,
) -> tuple[Arquetipo | None, Path | None]:
    """Qué arquetipo le toca a una ruta del repositorio, y cuál es su documento.

    Acepta la ruta relativa a la raíz o absoluta. Si la ruta no es ninguna unidad
    declarada, devuelve `(None, None)`: el hilo está vinculado a una carpeta que el
    perfil no reconoce, y eso hay que decirlo, no adivinarlo.
    """
    if not ruta:
        return None, None
    mapa = indice(perfil, raiz) if mapa is None else mapa
    camino = Path(ruta)
    claves = [camino.as_posix().strip("/")]
    try:
        # una ruta puede venir ya unida a la raíz, y la raíz puede ser relativa
        claves.append(camino.resolve().relative_to(Path(raiz).resolve()).as_posix())
    except (ValueError, OSError):
        pass
    for clave in claves:
        if clave in mapa:
            return mapa[clave]
    return None, None


def ficha_de(
    perfil: Perfil,
    raiz: Path,
    ruta: str | Path,
    *,
    mapa: dict[str, tuple[Arquetipo, Path]] | None = None,
) -> tuple[Arquetipo | None, Ficha | None]:
    """El arquetipo y la ficha de una ruta vinculada. `(None, None)` si no es una unidad."""
    arquetipo, documento = ubicar(perfil, raiz, ruta, mapa=mapa)
    if arquetipo is None or documento is None:
        return None, None
    return arquetipo, leer(documento, arquetipo)


# ── el nombre en pantalla ──────────────────────────────────────────────────────────

_MARCADOR = re.compile(r"\{([^{}]+)\}")
_SEPARADORES = "·—–-|:/"


def etiqueta(plantilla: str, ficha) -> str:
    """El nombre para mostrar de una unidad, según la `etiqueta` de su arquetipo.

    `{titulo}` es el título de la ficha y `{campo:Cliente}` una fila de su tabla de
    campos. Tres reglas, cada una contra un nombre feo que salía:

    - De un campo queda solo el nombre: sin paréntesis y cortado en la primera raya, coma o
      punto y coma. «Aguas Pacífico (agua desalada; Quintero…)» es «Aguas Pacífico».
    - Si un valor ya está dentro de otro, no se repite: con el título «AquaChile — Campaña
      de Ideas», el cliente «AquaChile» sobra.
    - Un marcador vacío se lleva su separador: sin cliente, «{campo:Cliente} · {titulo}»
      es solo el título.

    Sin plantilla, el título. Si al final no queda nada, "" (quien dibuja usa el nombre
    del hilo).
    """
    if ficha is None:
        return ""
    titulo = (getattr(ficha, "titulo", "") or "").strip()
    if not plantilla:
        return titulo
    campos = (getattr(ficha, "secciones", {}) or {}).get("campos") or {}

    def valor(marcador: str) -> str:
        marcador = marcador.strip()
        if marcador == "titulo":
            return titulo
        if marcador.startswith("campo:"):
            crudo = str(campos.get(marcador[len("campo:"):].strip(), "") or "")
            sin_parentesis = re.sub(r"\s*\([^)]*\)?", "", crudo)
            # un campo trae a veces su explicación pegada: «AquaChile, Gerencia de…»,
            # «Antofagasta Minerals — grupo minero». El nombre es lo de antes.
            return re.split(r"\s+[—–]\s+|;|,", sin_parentesis)[0].strip()
        return ""

    marcadores = _MARCADOR.findall(plantilla)
    valores = {m: valor(m) for m in marcadores}
    for m, v in list(valores.items()):
        if v and any(v != otro and _plano(v) in _plano(otro) for otro in valores.values() if otro):
            valores[m] = ""
    texto = _MARCADOR.sub(lambda mm: valores.get(mm.group(1), ""), plantilla)
    # los separadores que quedaron huérfanos al vaciarse un marcador
    sep = re.escape(_SEPARADORES)
    texto = re.sub(rf"^[\s{sep}]+|[\s{sep}]+$", "", texto)
    texto = re.sub(rf"\s+([{sep}])(?:\s*[{sep}])+\s+", r" \1 ", texto)
    return re.sub(r"\s{2,}", " ", texto).strip()


def _plano(texto: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()

