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

_RAYA = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")


def _es_texto(linea: str) -> bool:
    """¿Es una línea de prosa? Una viñeta es `-`, `*` o `+` seguido de espacio: `**Vendido.**`
    abre en negrita y es texto (descartarla dejaba vacío el `## Estado` que abre así)."""
    t = linea.strip()
    if not t or _VINETA.match(t) or _RAYA.match(t):
        return False
    return not t.startswith(("|", ">", "#", "<!--", "```"))


def _prosa(cuerpo: list[str]):
    """Las líneas del cuerpo, cada una con si es prosa. La continuación sangrada de una viñeta
    es parte de la viñeta, no un párrafo: no cuenta como texto."""
    en_vineta = False
    for linea in cuerpo:
        if _VINETA.match(linea):
            en_vineta = True
            yield linea, False
            continue
        if en_vineta and linea.strip() and linea[:1] in (" ", "\t"):
            yield linea, False
            continue
        if linea.strip():
            en_vineta = False
        yield linea, _es_texto(linea)


def _linea(cuerpo: list[str]) -> str:
    for linea, texto in _prosa(cuerpo):
        if texto:
            return limpiar(linea)
    return ""


def _parrafo(cuerpo: list[str]) -> str:
    juntas: list[str] = []
    for linea, texto in _prosa(cuerpo):
        if texto:
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


#: una marca entre paréntesis en una viñeta: `@owner(Ana Pérez)`, `@deadline(2026-10-14)`, `@prioridad(P1)`
_MARCA = re.compile(r"\s*(?:->|→)?\s*@(owner|due[nñ]o|responsable|para|deadline|vence|desde|prioridad|priority)\(([^)]*)\)", re.I)
#: quién al comienzo, como lo escribe la gente: «@Ana Pérez: revisar el NDA» (nombres con mayúscula)
_QUIEN = re.compile(r"^@([A-ZÁÉÍÓÚÑ][\w.'-]*(?:\s+[A-ZÁÉÍÓÚÑ][\w.'-]*){0,3})\s*:\s+")


def marcas(texto: str) -> tuple[str, str, str]:
    """(texto sin marcas, responsable, fecha límite) de una viñeta.

    El responsable sale de `@owner(…)` en cualquier parte o de `@Nombre Apellido:` al comienzo; la
    fecha, de `@deadline(AAAA-MM-DD)`. `@para(…)` también dice quién («-> @para(Ana)»). Las marcas no
    se muestran (tampoco `@prioridad(…)` ni `@desde(…)`), ni la flecha que las anuncia: el texto
    queda como lo leería una persona."""
    dueno, vence = "", ""
    for clave, valor in _MARCA.findall(texto):
        clave, valor = clave.lower(), valor.strip()
        if clave in ("owner", "dueño", "dueno", "responsable", "para") and valor:
            dueno = dueno or valor
        elif clave in ("deadline", "vence") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            vence = vence or valor
    texto = _MARCA.sub("", texto).strip()
    m = _QUIEN.match(texto)
    if m:
        dueno = dueno or m.group(1)
        texto = texto[m.end():].strip()
    return texto, dueno, vence


def _casillas(cuerpo: list[str], maximo: int, origen: str) -> tuple[Pendiente, ...]:
    salida = []
    for linea in cuerpo:
        m = _VINETA.match(linea)
        if not m or m.group(1) is None:
            continue
        marca = m.group(1).lower()
        valor, dueno, vence = marcas(limpiar(m.group(2)))
        if not valor:
            continue
        salida.append(
            Pendiente(
                texto=valor,
                hecho=marca == "x",
                en_curso=marca == ">",
                origen=origen,
                dueno=dueno,
                vence=vence,
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
    # el cliente (un campo) va donde dice la plantilla, y se saca del título si ya venía ahí:
    # «Reportes con IA — Faro Sur» con cliente «Faro Sur» es
    # «Faro Sur · Reportes con IA», no el título solo con el cliente al final
    campos_puestos = [v for m, v in valores.items() if m.startswith("campo:") and v]
    if "titulo" in valores and campos_puestos:
        valores["titulo"] = _sin_menciones(valores["titulo"], campos_puestos)
    texto = _MARCADOR.sub(lambda mm: valores.get(mm.group(1), ""), plantilla)
    # los separadores que quedaron huérfanos al vaciarse un marcador
    sep = re.escape(_SEPARADORES)
    texto = re.sub(rf"^[\s{sep}]+|[\s{sep}]+$", "", texto)
    texto = re.sub(rf"\s+([{sep}])(?:\s*[{sep}])+\s+", r" \1 ", texto)
    return re.sub(r"\s{2,}", " ", texto).strip()


def _sin_menciones(titulo: str, nombres: list[str]) -> str:
    """El título sin el trozo que nombra a alguien que ya va aparte: un tramo entre rayas o
    puntos medios («… — Banco Faro»), un «X:» al comienzo, o un «para X» o «, X» al final. Se compara sin tildes ni
    mayúsculas y por palabras enteras: el tramo tiene que ser el nombre o una forma más corta
    de él («Banco Faro» de «Banco Faro Chile»); un tramo que solo lo contiene («Faro
    de IA» con el cliente «Faro») es parte del título y se queda. Si el título era solo el
    cliente, queda vacío: la etiqueta dice el cliente una vez."""
    def mismo(tramo: str, nombre: str) -> bool:
        # sin lo que va entre paréntesis: «Faro (vía un tercero)» nombra a Faro
        pt, pn = _plano(re.sub(r"\s*\([^)]*\)?", "", tramo)).strip(), _plano(nombre).strip()
        return len(pt) >= 3 and re.search(rf"\b{re.escape(pt)}\b", pn) is not None

    # «Faro: Jornadas…», «Faro, sistema de…» — el cliente antes de dos puntos o coma
    m = re.match(r"^([^:,]{2,40})[:,]\s+(.+)$", titulo)
    if m and any(mismo(m.group(1), n) for n in nombres):
        titulo = m.group(2)
    tramos = re.split(r"\s+[—–·|]\s+|\s+-\s+", titulo)
    quedan = [t for t in tramos if not any(mismo(t, n) for n in nombres)]
    if not quedan:
        return ""   # el título era solo el cliente: la etiqueta lo dice una vez
    if len(quedan) < len(tramos):
        titulo = " — ".join(quedan)
    # «… para Faro», «Alianza con X», «…, Faro» — el cliente al final, sin raya
    m = re.match(r"^(.*\S)(?:\s+(?:para|de|en|con)|,)\s+(.+)$", titulo)
    if m and any(mismo(m.group(2), n) for n in nombres):
        titulo = m.group(1)
    return titulo.strip()


def _plano(texto: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()

