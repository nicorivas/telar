"""Fechas: lo que tiene día, venga de donde venga (docs/propuestas/fechas.md, docs/contratos.md «telar fechas»).

Una **fecha** es una cosa con día: una actividad que dura semanas, un hito, una sesión, una entrega. Tiene una
sola forma (`Fecha`, y su JSON) y sale de varias partes: las tablas de cronograma de los documentos, que se leen
aquí, y los proveedores con `como = "fechas"` (telar.proveedores.fechas), que traen las de afuera. Quien las
dibuja (un Gantt, el calendario) no sabe de dónde vino cada una.

De un documento se lee la sección `## Cronograma` (o `###`, `####`): su tabla, por el **nombre** de cada columna y
no por su lugar. Una fila sin fecha que se entienda no es una fecha, y se dice por qué (`Leidas.saltadas`), para que
quien escribió el documento lo pueda arreglar.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from telar.mapas import CAMPOS, POR_DEFECTO, Campo, Mapa, Mapas, anio_de, frontmatter
from telar.patrones import ErrorDePatron
from telar.proveedores.estado import fecha_en

__all__ = ["Fecha", "Leidas", "CLASES", "ESTADOS", "leer_documento", "de_json", "unidad_de", "filtrar"]

#: qué es cada fecha, que dice cómo se dibuja: una actividad dura días (una barra); el plazo es el del proyecto mismo
#: (su barra en un Gantt, de su inicio a su fin); las demás son un día
CLASES = ("actividad", "plazo", "hito", "sesion", "entrega", "evento", "tarea")
ESTADOS = ("pendiente", "en-curso", "hecho", "cancelado")

#: cada campo, por cómo puede llamarse su columna (se compara el comienzo, sin tildes ni mayúsculas)
COLUMNAS = {
    "titulo": ("actividad", "tarea", "hito", "sesion", "nombre", "fase", "que"),
    "inicio": ("inicio", "desde", "fecha", "comienzo", "start"),
    "fin": ("fin", "hasta", "termino", "end"),
    "responsable": ("responsable", "quien", "dueno", "owner"),
    "depende": ("depende",),
    "estado": ("estado", "status"),
    "clase": ("clase", "tipo"),
    "hora": ("hora",),
}

#: el estado, por su marca o su palabra (el comienzo de la palabra, sin tildes)
_MARCAS_ESTADO = (("✅", "hecho"), ("✔", "hecho"), ("🔄", "en-curso"), ("⏳", "en-curso"), ("⬜", "pendiente"),
                  ("❌", "cancelado"))
_PALABRAS_ESTADO = (("cancel", "cancelado"), ("descart", "cancelado"), ("complet", "hecho"), ("hech", "hecho"),
                    ("listo", "hecho"), ("termin", "hecho"), ("done", "hecho"), ("curso", "en-curso"),
                    ("progres", "en-curso"), ("pendiente", "pendiente"))


@dataclass(frozen=True, slots=True)
class Fecha:
    """Una cosa con día. Los campos son los del contrato; `inicio` y `fin` van como `date`."""

    id: str
    titulo: str
    inicio: date
    fin: date
    hora: str = ""
    clase: str = "actividad"
    proyecto: str = ""
    estado: str = "pendiente"
    responsable: str = ""
    depende: tuple[str, ...] = ()
    fuente: str = ""
    enlace: str = ""
    #: los campos que su fuente sabe escribir; vacío, de solo lectura (escribir es un paso que viene)
    editable: tuple[str, ...] = ()
    #: lo que cambia si la fecha cambia: un cambio que la trae se hace solo si sigue igual
    version: str = ""
    #: por qué no se puede mover (su inicio no es editable), en palabras; "" si se puede
    bloqueo: str = ""

    def a_json(self) -> dict:
        return {"id": self.id, "titulo": self.titulo, "inicio": self.inicio.isoformat(), "fin": self.fin.isoformat(),
                "hora": self.hora, "clase": self.clase, "proyecto": self.proyecto, "estado": self.estado,
                "responsable": self.responsable, "depende": list(self.depende), "fuente": self.fuente,
                "enlace": self.enlace, "editable": list(self.editable), "version": self.version, "bloqueo": self.bloqueo}


@dataclass(slots=True)
class Leidas:
    """Lo que salió de una fuente: las fechas, y las filas que parecían una y no se entendieron («archivo:línea:
    por qué»)."""

    fechas: list[Fecha] = field(default_factory=list)
    saltadas: list[str] = field(default_factory=list)

    def sumar(self, otras: Leidas) -> None:
        self.fechas.extend(otras.fechas)
        self.saltadas.extend(otras.saltadas)


def _norm(texto: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn").strip()


def estado_de(texto: str) -> str:
    """El estado de una celda: su marca (✅ 🔄 ⬜) o su palabra; `pendiente` si no dice nada que se entienda."""
    for marca, estado in _MARCAS_ESTADO:
        if marca in texto:
            return estado
    palabra = _norm(texto)
    return next((e for p, e in _PALABRAS_ESTADO if p in palabra), "pendiente")


#: el id que telar le pone a una fila la primera vez que la escribe (como a una casilla, telar.vinetas)
_ID_FILA = re.compile(r"\s*<!--\s*id:\s*(f-[0-9a-z]+)\s*-->")


def _celdas(linea: str) -> list[str]:
    return [_ID_FILA.sub("", c).strip() for c in linea.strip().strip("|").split("|")]


def _es_separador(celdas: list[str]) -> bool:
    return all(re.fullmatch(r":?-{1,}:?", c) for c in celdas if c) and any(celdas)


def _tablas(lineas: list[str], mapa: Mapa) -> list[list[tuple[int, list[str]]]]:
    """Las tablas de las secciones que el mapa dice que son cronogramas: cada una, sus filas con su número de línea
    (desde 1), la cabecera primero y sin la línea de guiones. La sección llega hasta el próximo encabezado de su nivel
    o mayor. Con `patron`, cada línea que calza es una fila y sus grupos con nombre, las columnas."""
    tablas: list[list[tuple[int, list[str]]]] = []
    nivel = 0
    actual: list[tuple[int, list[str]]] = []
    grupos = list(mapa.patron.groupindex) if mapa.patron else []

    def cerrar() -> None:
        nonlocal actual
        if actual and (not mapa.patron or len(actual) > 1):
            tablas.append(actual)
        actual = [(0, grupos)] if mapa.patron else []

    cerrar()
    for n, linea in enumerate(lineas, 1):
        if m := re.match(r"^(#{1,6})\s", linea):
            cerrar()
            if nivel and len(m.group(1)) <= nivel:
                nivel = 0
            if not nivel and any(r.match(linea.rstrip()) for r in mapa.secciones):
                nivel = len(m.group(1))
            continue
        if not nivel:
            continue
        if mapa.patron:
            if g := mapa.patron.match(linea):
                actual.append((n, [(g.group(x) or "").strip() for x in grupos]))
        elif linea.strip().startswith("|"):
            celdas = _celdas(linea)
            if not _es_separador(celdas):
                actual.append((n, celdas))
        elif actual:
            cerrar()
    cerrar()
    return tablas


def _columnas(cabecera: list[str]) -> dict[str, int]:
    """Qué columna es cada campo, por su nombre. Una columna sirve a un solo campo, el primero que la reclame."""
    nombres = [_norm(re.sub(r"[*_`]", "", c)) for c in cabecera]
    salida: dict[str, int] = {}
    for campo, opciones in COLUMNAS.items():
        for i, nombre in enumerate(nombres):
            if i not in salida.values() and any(nombre.startswith(o) for o in opciones):
                salida[campo] = i
                break
    return salida


def _dia_o_mes(texto: str, hoy: date | None) -> tuple[date | None, date | None]:
    """El día de una celda, y hasta cuándo llega: el mismo día, o el último del mes si la celda es un mes entero
    (`2026-08`). (None, None) si no trae una fecha que se entienda."""
    if m := re.fullmatch(r"\s*(\d{4})-(\d{1,2})\s*", texto):
        anio, mes = int(m.group(1)), int(m.group(2))
        if 1 <= mes <= 12:
            siguiente = date(anio + mes // 12, mes % 12 + 1, 1)
            return date(anio, mes, 1), date.fromordinal(siguiente.toordinal() - 1)
    dia = fecha_en(texto, hoy=hoy) if texto else None
    return dia, dia


def _version(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]


@dataclass(slots=True)
class Lector:
    """Lo que hace falta saber del repositorio para leer un documento: sus unidades, y cómo encontrar una por una clave
    de su frontmatter (`buscar:` en un mapa)."""

    unidades: set[str] = field(default_factory=set)
    #: (clave, valor) → la unidad cuyo frontmatter dice ese valor en esa clave, o ""
    buscar: Callable[[str, str], str] = lambda clave, valor: ""
    hoy: date = field(default_factory=date.today)


_ENLACE = re.compile(r"\]\(\s*<?([^)\s>]+)")


def _unidad_por_enlace(linea: str, archivo: str, unidades: set[str]) -> str:
    """La unidad a la que apunta un enlace de la fila (`[Faro](../faro/README.md)`), o ""."""
    for destino in _ENLACE.findall(linea):
        if re.match(r"^[a-z]+:", destino) or destino.startswith("#"):
            continue
        ruta = posixpath.normpath(posixpath.join(posixpath.dirname(archivo), destino.split("#")[0]))
        if u := unidad_de(ruta, unidades):
            return u
    return ""


def _por_nombre(cabecera_norm: list[str], nombre: str) -> int | None:
    nombre = _norm(nombre)
    for i, c in enumerate(cabecera_norm):
        if c == nombre:
            return i
    return next((i for i, c in enumerate(cabecera_norm) if c.startswith(nombre)), None)


def _rango(texto: str, campo: Campo | None, fm: dict, hoy: date) -> tuple[date, date] | None:
    """El día (o los días) de una celda, con el patrón del mapa si lo dice. None si no trae ninguno; un ErrorDePatron
    si trae algo que no calza con el patrón."""
    partes = texto.split(campo.rango, 1) if campo and campo.rango and campo.rango in texto else [texto]
    if campo and campo.formato:
        anio = anio_de(campo, fm, hoy)
        ultimo = campo.formato.leer(partes[-1], anio=anio)
        if len(partes) == 1:
            return ultimo, ultimo
        p = campo.formato.partes(partes[0], parcial=True)
        try:
            primero = date(p.get("y", ultimo.year), p.get("M", ultimo.month), p["d"])
        except (KeyError, ValueError):
            raise ErrorDePatron(f"«{partes[0]}» no es un día") from None
        return primero, max(primero, ultimo)
    if len(partes) == 2:
        a, b = _dia_o_mes(partes[0], hoy)[0], _dia_o_mes(partes[1], hoy)[1]
        return (a, max(a, b)) if a and b else None
    a, b = _dia_o_mes(texto, hoy)
    return (a, b) if a and b else None


def leer_documento(texto: str, *, archivo: str, proyecto: str, mapa: Mapa | None = None, lector: Lector | None = None,
                   es_de_unidad: bool = True, hoy: date | None = None) -> Leidas:
    """Las fechas de las tablas de cronograma de un documento, traducidas con su mapa (sin mapa, `## Cronograma` y
    cada campo por el nombre de su columna). `archivo` es su ruta relativa a la raíz (con ella se nombra cada fila,
    `archivo:línea`) y `proyecto`, la unidad que lo contiene. En un documento que no es el de una unidad (un calendario
    compartido), cada fila es de la unidad a la que apunta su enlace, si tiene uno."""
    mapa = mapa or POR_DEFECTO
    lector = lector or Lector()
    hoy = hoy or lector.hoy
    fm = frontmatter(texto) if texto.startswith("---") else {}
    leidas = Leidas()
    lineas = texto.splitlines()
    for tabla in _tablas(lineas, mapa):
        (n_cab, cabecera), filas = tabla[0], tabla[1:]
        cab = [_norm(re.sub(r"[*_`]", "", c)) for c in cabecera]
        defecto = _columnas(cabecera)
        indice: dict[str, int | None] = {}
        for c in CAMPOS:
            campo = mapa.campos.get(c)
            indice[c] = _por_nombre(cab, campo.columna) if campo and campo.columna else defecto.get(c)
        if indice["inicio"] is None and not (mapa.campos.get("inicio") and mapa.campos["inicio"].constante):
            leidas.saltadas.append(f"{archivo}:{n_cab}: la tabla no tiene una columna de fecha (Inicio, Fecha, Desde)"
                                   if not mapa.campos.get("inicio") else
                                   f"{archivo}:{n_cab}: no hay una columna «{mapa.campos['inicio'].columna}»")
            continue
        if indice["titulo"] is None and "titulo" not in mapa.campos:
            indice["titulo"] = 0

        por_nombre: dict[str, str] = {}
        crudas: list[tuple[list[str], Fecha]] = []
        for n, f in filas:
            def valor(c: str) -> str:
                campo = mapa.campos.get(c)
                if campo and campo.constante is not None:
                    crudo = campo.constante
                elif campo and campo.plantilla:
                    crudo = _plantilla(campo.plantilla, cab, f)
                else:
                    i = indice.get(c)
                    crudo = f[i].strip() if i is not None and i < len(f) else ""
                if campo and campo.valores:
                    crudo = campo.valores.get(_norm(crudo), crudo)
                return crudo

            texto_inicio = valor("inicio")
            try:
                dias = _rango(texto_inicio, mapa.campos.get("inicio"), fm, hoy)
            except ErrorDePatron as e:
                leidas.saltadas.append(f"{archivo}:{n}: {e}")
                continue
            if dias is None:
                # «por definir», «pendiente»: todavía no tiene fecha, y eso no es un error. Lo que trae un número y no
                # se entiende («6 a 10 de julio»), sí: se dice, para arreglarlo o para que un mapa lo lea
                if re.search(r"\d", texto_inicio):
                    leidas.saltadas.append(f"{archivo}:{n}: «{texto_inicio}» no es una fecha que se entienda")
                continue
            inicio, fin = dias
            texto_fin = valor("fin")
            if texto_fin:
                try:
                    otros = _rango(texto_fin, mapa.campos.get("fin") or mapa.campos.get("inicio"), fm, hoy)
                except ErrorDePatron:
                    otros = None
                fin = otros[1] if otros else fin
            hora = ""
            if texto_hora := valor("hora"):
                campo_hora = mapa.campos.get("hora")
                lado = texto_hora.split(campo_hora.rango, 1)[0] if campo_hora and campo_hora.rango else texto_hora
                try:
                    hora = campo_hora.formato.hora(lado) if campo_hora and campo_hora.formato else _hora(lado)
                except ErrorDePatron:
                    hora = ""
            clase = _norm(valor("clase"))
            clase = clase if clase in CLASES else ("actividad" if fin > inicio else "evento")
            estado = valor("estado")
            estado = estado if estado in ESTADOS else estado_de(estado)
            # de qué unidad es: la que diga el mapa (por una clave del frontmatter, o la ruta en la celda); si no, en
            # un documento compartido, la de su enlace; si no, la que contiene el documento
            de = proyecto
            campo_p = mapa.campos.get("proyecto")
            if campo_p and campo_p.buscar:
                buscado = valor("proyecto")
                encontrada = lector.buscar(campo_p.buscar, buscado) if buscado else ""
                if buscado and not encontrada:
                    leidas.saltadas.append(f"{archivo}:{n}: leída sin proyecto: ninguna unidad dice {campo_p.buscar}: {buscado}")
                de = encontrada or de
            elif campo_p:
                buscado = valor("proyecto").strip("/")
                de = buscado if buscado in lector.unidades else (_unidad_por_enlace(buscado, archivo, lector.unidades)
                                                                  or de)
            elif not es_de_unidad:
                de = _unidad_por_enlace(lineas[n - 1], archivo, lector.unidades) or de
            # una fila que telar ya escribió tiene su id (`<!-- id: f-1a2b3c -->`) y se nombra por él, que no cambia
            # aunque el documento cambie; si no, por su lugar
            fid = _ID_FILA.search(lineas[n - 1])
            ident = f"{archivo}#{fid.group(1)}" if fid else f"{archivo}:{n}"
            titulo = re.sub(r"\*\*|__", "", valor("titulo")).strip()
            razones = {c: (_por_que_no(c, mapa, indice, f, valor("inicio")) if not mapa.patron
                           else "viene de una lista leída con el patrón del mapa") for c in ("inicio", "fin")}
            editable = tuple(c for c, razon in razones.items() if not razon)
            fecha = Fecha(id=ident, titulo=titulo, inicio=inicio, fin=max(inicio, fin), hora=hora, clase=clase,
                          proyecto=de, estado=estado, responsable=valor("responsable"), fuente=f"{archivo}:{n}",
                          enlace=valor("enlace"), editable=editable, version=_version(lineas[n - 1]),
                          bloqueo=razones["inicio"])
            por_nombre.setdefault(_norm(titulo), ident)
            crudas.append(([x for x in re.split(r"[,;]", valor("depende")) if x.strip()], fecha))
        # «Depende de» nombra otras filas de la misma tabla por su título: se guarda su id; lo que no calza se pierde
        for nombres, fecha in crudas:
            ids = tuple(por_nombre[_norm(x)] for x in nombres if _norm(x) in por_nombre)
            leidas.fechas.append(replace(fecha, depende=ids) if ids else fecha)
    return leidas


_DIA_SEMANA = r"(?P<sem>(?:lun|mar|mi[eé]|jue|vie|s[aá]b|dom|mon|tue|wed|thu|fri|sat|sun)[a-záéíóú]*\.?)\s+"
#: las fechas que telar sabe reescribir dentro de una celda, sin tocar lo que las rodea («2026-08-12 10:00»,
#: «~2026-11-03», «lunes 5-oct», «15/07/2026 (revisado)»): una sola por celda
_FORMAS = (
    ("iso", re.compile(r"(?<![\d-])(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?![\d-])")),
    ("dma", re.compile(r"(?<![\d/-])(?P<d>\d{1,2})(?P<sep>[-/])(?P<m>\d{1,2})(?P=sep)(?P<y>\d{4})(?![\d/-])")),
    ("dmes", re.compile(r"(?:" + _DIA_SEMANA + r")?(?<!\d)(?P<d>\d{1,2})(?P<sep>[- ])(?P<mes>[a-záéíóú]{3,})(?P<punto>\.?)"
                        r"(?:(?P<sep2>[- ])(?P<y>\d{4}))?(?![\w])", re.I)),
)


class _Forma:
    """La forma de la fecha de una celda, para escribir otra igual: la celda entera con el día cambiado (`celda`), o
    solo el día con esa forma (`solo`, para una celda de fin vacía)."""

    def __init__(self, texto: str, tipo: str, m: re.Match[str]) -> None:
        self.texto, self.tipo, self.m = texto, tipo, m

    def solo(self, d: date) -> str:
        g = self.m.groupdict()
        if self.tipo == "iso":
            return d.isoformat()
        if self.tipo == "dma":
            ancho = 2 if len(g["d"]) == 2 else 1
            return f"{d.day:0{ancho}d}{g['sep']}{d.month:0{len(g['m'])}d}{g['sep']}{d.year}"
        from telar.patrones import _DIAS, _MESES

        mes = g["mes"]
        idioma = "en" if _norm(mes)[:3] in ("jan", "apr", "aug", "dec") or (g.get("sem") or "")[:3].lower() in (
            "mon", "tue", "wed", "thu", "fri", "sat", "sun") else "es"
        cortos, largos = _MESES[idioma]
        nombre = (largos if len(mes) > 4 else cortos)[d.month - 1]
        nombre = nombre.capitalize() if mes[:1].isupper() else nombre
        texto = f"{d.day}{g['sep']}{nombre}{g['punto']}" + (f"{g['sep2']}{d.year}" if g.get("y") else "")
        if g.get("sem"):
            sem = g["sem"]
            dias_cortos, dias_largos = _DIAS[idioma]
            nuevo = (dias_largos if len(sem.rstrip(".")) > 3 else dias_cortos)[d.weekday()]
            nuevo = (nuevo.capitalize() if sem[:1].isupper() else nuevo) + ("." if sem.endswith(".") else "")
            texto = f"{nuevo} {texto}"
        return texto

    def celda(self, d: date) -> str:
        return self.texto[: self.m.start()] + self.solo(d) + self.texto[self.m.end():]


def _forma(texto: str) -> _Forma | None:
    """La forma de la única fecha de una celda, si telar sabe reescribirla; None si no trae ninguna, trae más de
    una, o es otra cosa (un mes entero, «Q4 2026»)."""
    texto = texto.strip()
    for tipo, regex in _FORMAS:
        hallados = list(regex.finditer(texto))
        if tipo == "dmes":
            from telar.proveedores.estado import MESES

            hallados = [m for m in hallados if _norm(m.group("mes"))[:3] in MESES]
        if len(hallados) == 1:
            return _Forma(texto, tipo, hallados[0])
        if len(hallados) > 1:
            return None
    return None


def _por_que_no(c: str, mapa: Mapa, indice: dict, fila: list[str], texto_inicio: str) -> str:
    """Por qué telar no sabe escribir ese campo de esa fila, o "" si sabe: sale de una sola columna, sin plantilla,
    constante, rango ni vocabulario propio, y su fecha tiene una forma que se puede reescribir (el `formato` del mapa,
    o una de `_FORMAS`, dentro de lo que diga la celda). Un `fin` vacío se escribe con la forma del inicio."""
    campo = mapa.campos.get(c)
    if campo and campo.constante is not None:
        return f"su {c} es un valor fijo del mapa «{mapa.nombre}»"
    if campo and campo.plantilla:
        return f"su {c} sale de una plantilla del mapa «{mapa.nombre}»"
    if campo and campo.rango:
        return f"su {c} viene en una celda con inicio y fin («{texto_inicio}»)"
    if campo and campo.valores:
        return f"su {c} pasa por el vocabulario del mapa «{mapa.nombre}»"
    i = indice.get(c)
    if i is None or i >= len(fila):
        return f"la tabla no tiene una columna de {c}"
    if (campo and campo.formato) or (c == "fin" and (inicio := mapa.campos.get("inicio")) and inicio.formato):
        return ""
    celda = fila[i] or texto_inicio
    if _forma(celda) is not None:
        return ""
    if re.fullmatch(r"\s*\d{4}-\d{1,2}\s*", celda):
        return f"la celda es un mes entero («{celda.strip()}»): moverlo por días cambiaría lo que dice"
    return f"telar no sabe reescribir «{celda.strip()}» sin perder lo que dice"


def _plantilla(plantilla: str, cab: list[str], fila: list[str]) -> str:
    """«{Cliente} · {Programa}» con lo de esa fila; lo que queda vacío no deja separadores sueltos."""
    def llenar(m: re.Match[str]) -> str:
        i = _por_nombre(cab, m.group(1))
        return fila[i].strip() if i is not None and i < len(fila) else ""

    texto = re.sub(r"\{([^}]+)\}", llenar, plantilla)
    texto = re.sub(r"(\s*[·|,;–—-]\s*)(?=\s*[·|,;–—-]|\s*$)", "", texto)
    return re.sub(r"^\s*[·|,;–—-]\s*", "", texto).strip()


def _hora(texto: str) -> str:
    m = re.search(r"\b(\d{1,2})[:.h](\d{2})\b", texto)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""


def de_json(datos: object, origen: str) -> Fecha:
    """Una fecha que imprimió un programa (un proveedor `comando`). `titulo` e `inicio` son obligatorios; lo que
    no se entiende es un ValueError que dice qué."""
    if not isinstance(datos, dict):
        raise ValueError(f"{origen}: se esperaba un objeto, llegó {type(datos).__name__}")

    def texto(clave: str) -> str:
        v = datos.get(clave, "")
        return v.strip() if isinstance(v, str) else ""

    def dia(clave: str) -> date | None:
        v = texto(clave)
        if not v:
            return None
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            raise ValueError(f"{origen}: {clave} se esperaba AAAA-MM-DD, llegó {v!r}") from None

    titulo, inicio = texto("titulo"), dia("inicio")
    if not titulo or inicio is None:
        raise ValueError(f"{origen}: falta titulo o inicio")
    fin = dia("fin") or inicio
    clase = texto("clase") or ("actividad" if fin > inicio else "evento")
    if clase not in CLASES:
        raise ValueError(f"{origen}: clase es una de {', '.join(CLASES)}; llegó {clase!r}")
    estado = texto("estado") or "pendiente"
    if estado not in ESTADOS:
        estado = estado_de(estado)
    depende = datos.get("depende", [])
    return Fecha(id=texto("id") or origen, titulo=titulo, inicio=inicio, fin=max(inicio, fin), hora=texto("hora"),
                 clase=clase, proyecto=texto("proyecto").strip("/"), estado=estado, responsable=texto("responsable"),
                 depende=tuple(str(x) for x in depende) if isinstance(depende, list) else (),
                 fuente=texto("fuente") or origen, enlace=texto("enlace"), bloqueo=texto("bloqueo"))


def unidad_de(ruta: str, unidades: list[str] | set[str]) -> str:
    """La unidad más honda que contiene `ruta` (relativa a la raíz), o "". Una fecha de
    `operacion/faro/seguimiento.md` es de `operacion/faro`, no de `operacion`, aunque las dos la contengan."""
    mejor = ""
    for u in unidades:
        if (ruta == u or ruta.startswith(f"{u}/")) and len(u) > len(mejor):
            mejor = u
    return mejor


def documentos(raiz: Path, unidades: dict[str, tuple[object, Path]], rutas: tuple[str, ...] = (), *,
               solo_rutas: bool = False, mapas: Mapas | None = None, hoy: date | None = None) -> Leidas:
    """Las fechas de los documentos del repositorio: el de cada unidad, los que nombran los `.telar/fechas.yaml`
    (`documentos:`) y los que calcen con `rutas` (globs desde la raíz, los de un proveedor `fechas` de tipo
    `markdown`). Cada documento se lee con su mapa (`telar.mapas`: el de su frontmatter, el de `documentos:`, o el
    de por defecto). Con `solo_rutas`, solo los de `rutas` (lo de un proveedor: lo demás ya se leyó)."""
    mapas = mapas or Mapas()
    raiz = raiz.resolve()
    leidas = Leidas()
    archivos: dict[str, Path] = {}
    de_unidad: set[str] = set()
    for _, (_, documento) in unidades.items():
        relativa = Path(documento).resolve().relative_to(raiz).as_posix()
        if not solo_rutas:
            archivos.setdefault(relativa, Path(documento))
        de_unidad.add(relativa)
    for glob in (*(() if solo_rutas else mapas.con_documentos()), *rutas):
        for p in sorted(raiz.glob(glob)):
            if p.is_file():
                archivos.setdefault(p.resolve().relative_to(raiz).as_posix(), p)
    claves = set(unidades)
    lector = Lector(unidades=claves, buscar=buscador(raiz, unidades), hoy=hoy or date.today())
    for relativa, ruta in sorted(archivos.items()):
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = frontmatter(texto) if texto.startswith("---") else {}
        mapa = mapas.para(relativa, fm)
        if mapa is None and "ronograma" not in texto:  # lo barato primero: casi ningún documento tiene uno
            continue
        leidas.sumar(leer_documento(texto, archivo=relativa, proyecto=unidad_de(relativa, claves), mapa=mapa,
                                    lector=lector, es_de_unidad=relativa in de_unidad))
    return leidas


def buscador(raiz: Path, unidades: dict[str, tuple[object, Path]]) -> Callable[[str, str], str]:
    """`buscar(clave, valor)`: la unidad cuyo frontmatter dice ese valor en esa clave (`pmo: 70`). Los frontmatter se
    leen la primera vez que se busca, una sola vez."""
    indice: dict[str, dict[str, str]] = {}

    def buscar(clave: str, valor: str) -> str:
        if clave not in indice:
            tabla: dict[str, str] = {}
            for unidad, (_, documento) in unidades.items():
                try:
                    with open(documento, encoding="utf-8", errors="replace") as f:
                        cabeza = f.read(4000)
                except OSError:
                    continue
                v = frontmatter(cabeza).get(clave)
                if v not in (None, ""):
                    tabla.setdefault(_norm(str(v)), unidad)
            indice[clave] = tabla
        return indice[clave].get(_norm(valor), "")

    return buscar


def filtrar(fechas: list[Fecha], *, proyecto: str = "", desde: date | None = None,
            hasta: date | None = None) -> list[Fecha]:
    """Las de un proyecto (y lo que tiene adentro) y las que tocan el intervalo, ordenadas por inicio."""
    proyecto = proyecto.strip("/")
    salida = [f for f in fechas
              if (not proyecto or f.proyecto == proyecto or f.proyecto.startswith(f"{proyecto}/"))
              and (desde is None or f.fin >= desde) and (hasta is None or f.inicio <= hasta)]
    return sorted(salida, key=lambda f: (f.inicio, f.fin, f.proyecto, f.titulo))


class ErrorDeFecha(ValueError):
    """Un cambio que no se puede hacer: con su código, como en la API (404 no está, 409 cambió, 422 no se escribe)."""

    def __init__(self, mensaje: str, codigo: int = 422) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def escribir_en_documento(raiz: Path, ident: str, *, inicio: date | None = None, fin: date | None = None,
                          version: str = "", mapas: Mapas | None = None, unidades: dict | None = None) -> Fecha:
    """Cambia el inicio o el fin de una fila de cronograma, en su documento: solo esas celdas, con la forma que tienen
    (el patrón de su mapa, o la de la celda), y nada más del documento. La primera vez le pone a la fila su id
    (`<!-- id: f-… -->`), para encontrarla aunque el documento cambie. Con `version`, solo si la fila sigue como se
    leyó (si no, 409). Devuelve la fecha como quedó; el cambio queda sin commitear."""
    import secrets

    mapas = mapas or Mapas()
    unidades = unidades or {}
    if "#" in ident:
        archivo, fid = ident.rsplit("#", 1)
        n = None
    else:
        archivo, _, linea = ident.rpartition(":")
        fid, n = "", int(linea) if linea.isdigit() else 0
        if not n:
            raise ErrorDeFecha(f"{ident}: no es una fila de un documento (archivo:línea o archivo#id)", 404)
    ruta = (Path(raiz) / archivo).resolve()
    if not ruta.is_relative_to(Path(raiz).resolve()) or not ruta.is_file():
        raise ErrorDeFecha(f"{archivo}: no existe", 404)
    texto = ruta.read_text(encoding="utf-8")
    lineas = texto.split("\n")
    if fid:
        n = next((i for i, x in enumerate(lineas, 1) if f"id: {fid}" in x and _ID_FILA.search(x)), None)
        if n is None:
            raise ErrorDeFecha(f"{ident}: la fila ya no está en {archivo}", 404)
    if n > len(lineas):
        raise ErrorDeFecha(f"{ident}: {archivo} ya no tiene esa línea", 409)
    if version and _version(lineas[n - 1]) != version:
        raise ErrorDeFecha(f"{ident}: la fila cambió desde que se leyó; vuelve a leerla", 409)
    claves = set(unidades)
    de_unidad = {Path(d).resolve().relative_to(Path(raiz).resolve()).as_posix() for _, d in unidades.values()}
    mapa = mapas.para(archivo, frontmatter(texto) if texto.startswith("---") else {}) or POR_DEFECTO
    actual = next((f for f in leer_documento(texto, archivo=archivo, proyecto=unidad_de(archivo, claves), mapa=mapa,
                                             lector=Lector(unidades=claves), es_de_unidad=archivo in de_unidad).fechas
                   if f.fuente == f"{archivo}:{n}"), None)
    if actual is None:
        raise ErrorDeFecha(f"{ident}: esa línea no es una fila de cronograma", 404)
    pedido = {"inicio": inicio, "fin": fin}
    for c, v in pedido.items():
        if v is not None and c not in actual.editable and v != getattr(actual, c):
            razon = actual.bloqueo if c == "inicio" and actual.bloqueo else "telar no sabe escribirlo en esa fila"
            raise ErrorDeFecha(f"{ident}: su {c} no se puede cambiar: {razon}", 422)
    nuevo_inicio = inicio or actual.inicio
    nuevo_fin = fin or (actual.fin + (nuevo_inicio - actual.inicio) if inicio and not fin else actual.fin)
    if nuevo_fin < nuevo_inicio:
        raise ErrorDeFecha(f"{ident}: el fin queda antes del inicio", 422)
    if nuevo_fin != nuevo_inicio and "fin" not in actual.editable:
        raise ErrorDeFecha(f"{ident}: la fila no tiene una columna de fin donde escribir que dura más de un día", 422)

    # la tabla de la fila: su cabecera, para saber qué celda es cada campo
    tabla = next(t for t in _tablas(lineas, mapa) if any(x == n for x, _ in t))
    cab = [_norm(re.sub(r"[*_`]", "", c)) for c in tabla[0][1]]
    defecto = _columnas(tabla[0][1])
    indice = {c: (_por_nombre(cab, mapa.campos[c].columna) if c in mapa.campos and mapa.campos[c].columna else defecto.get(c))
              for c in ("inicio", "fin")}
    partes = lineas[n - 1].split("|")  # [antes, celda, celda, …, después]
    celdas = _celdas(lineas[n - 1])

    def con_forma(c: str, d: date) -> str:
        """La celda nueva: la fecha con su forma, y lo demás de la celda como estaba («2026-08-12 10:00»)."""
        campo = mapa.campos.get(c) or (mapa.campos.get("inicio") if c == "fin" else None)
        if campo and campo.formato:
            return campo.formato.escribir(d)
        if celdas[indice[c]]:
            forma = _forma(celdas[indice[c]])
            return forma.celda(d) if forma else d.isoformat()
        # un fin vacío: solo el día, con la forma del inicio (sin su hora ni su nota)
        forma = _forma(celdas[indice["inicio"]])
        return forma.solo(d) if forma else d.isoformat()

    cambios = {"inicio": nuevo_inicio}
    if indice["fin"] is not None and "fin" in actual.editable:
        # un fin igual al inicio en una celda que estaba vacía se deja vacío: sigue siendo un día
        if not (nuevo_fin == nuevo_inicio and not celdas[indice["fin"]]):
            cambios["fin"] = nuevo_fin
    for c, d in cambios.items():
        i = indice[c]
        viejo = partes[i + 1]
        izq = viejo[: len(viejo) - len(viejo.lstrip())] or " "
        der = viejo[len(viejo.rstrip()):] or " "
        comentario = _ID_FILA.search(viejo)
        partes[i + 1] = f"{izq}{con_forma(c, d)}{der}" + (comentario.group(0) if comentario else "")
    if not fid:
        fid = "f-" + secrets.token_hex(3)
        ultima = -2 if lineas[n - 1].rstrip().endswith("|") else -1
        partes[ultima] = partes[ultima].rstrip() + f" <!-- id: {fid} -->" + (" " if ultima == -2 else "")
    lineas[n - 1] = "|".join(partes)
    temporal = ruta.with_name(f".{ruta.name}.telar")
    temporal.write_text("\n".join(lineas), encoding="utf-8")
    temporal.replace(ruta)
    texto = ruta.read_text(encoding="utf-8")
    quedo = next((f for f in leer_documento(texto, archivo=archivo, proyecto=actual.proyecto, mapa=mapa,
                                            lector=Lector(unidades=claves), es_de_unidad=archivo in de_unidad).fechas
                  if f.id == f"{archivo}#{fid}"), None)
    if quedo is None:  # pragma: no cover - lo que se escribió no se lee: no debería pasar
        raise ErrorDeFecha(f"{ident}: se escribió, pero no se pudo leer de vuelta", 500)
    return replace(quedo, proyecto=actual.proyecto)
