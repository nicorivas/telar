"""El estado de un hilo: cómo va la cosa, en una forma que cualquiera puede cumplir.

Un hilo tiene una carpeta, la carpeta tiene un documento y el documento dice cómo
va. Este módulo lo pregunta y devuelve siempre la misma forma —el contrato de
`docs/contratos.md`— venga de donde venga:

  `documento`  lee el markdown del hilo, guiado por el perfil del repositorio.
  `comando`    corre un programa que la configuración declara y lee su JSON.

Un proveedor de estado **no es una `telar.proveedores.Fuente`**: una Fuente trae
ítems del mundo para un día, esto responde por un documento. Por eso tiene su propio
protocolo y su propio registro.

Leer el markdown es cosa de `telar.lectura`, que cumple lo que el perfil declaró
sección por sección. Lo que se agrega aquí es el paso siguiente, el que convierte
esas secciones en un estado: **la cascada**. Cada campo del contrato tiene una lista
de orígenes y se toma el primero que dé algo, así que un README que pone el estado
en un párrafo, otro que lo pone en una fila de tabla y otro que no lo pone en
ninguna parte se leen con la misma configuración y sin excepciones.

Aquí tampoco hay ningún nombre de sección escrito a fuego: la cascada se arma con lo
que el arquetipo declaró, y la configuración la puede desarmar entera.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from telar import lectura
from telar.config import Proveedor as ConfigProveedor
from telar.modelo import Ficha, Pendiente
from telar.perfil import PERFIL_MINIMO, Arquetipo
from telar.proveedores import ErrorDeProveedor

__all__ = [
    "CONTRATO",
    "CAMPOS_CASCADA",
    "MARCAS",
    "MESES",
    "Espera",
    "Hito",
    "Enlace",
    "Estado",
    "FuenteDeEstado",
    "Documento",
    "Comando",
    "REGISTRO",
    "registrar",
    "obtener",
    "leer",
    "cascada_por_defecto",
    "fecha_en",
]

#: Los campos del contrato, en orden. Lo demás que lleve un `Estado` es procedencia:
#: de dónde salió y qué faltó, no lo que el documento dice.
CONTRATO = ("titulo", "resumen", "campos", "pendientes", "esperando", "hitos", "enlaces")

#: Los que la cascada puede gobernar. `enlaces` no está: un enlace no tiene sección,
#: sale del documento entero.
CAMPOS_CASCADA = ("titulo", "resumen", "campos", "pendientes", "esperando", "hitos")

#: Cómo se marca lo hecho y lo que está en curso, si el repositorio no dice otra
#: cosa. Sale de lo que el perfil ya define para el tipo `casillas`: `[x]` hecha,
#: `[>]` en curso. Lo que se declare se suma a eso, como prefijo del texto.
MARCAS: dict[str, tuple[str, ...]] = {"hecho": (), "en_curso": ()}

#: Meses en tres letras, para las fechas escritas a mano («12-mar»). Un repositorio
#: que escriba en otro idioma pasa su propio mapa en `opciones.meses`.
MESES = {
    abrev: numero
    for numero, par in enumerate(
        zip(
            "ene feb mar abr may jun jul ago sep oct nov dic".split(),
            "jan feb mar apr may jun jul aug sep oct nov dec".split(),
        ),
        1,
    )
    for abrev in par
}


# ── el contrato ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Espera:
    """Algo que el hilo no puede mover porque depende de otro."""

    texto: str
    #: la fecha que traía el texto, si traía alguna.
    cuando: date | None = None
    #: la sección de la que salió.
    origen: str = ""


@dataclass(frozen=True, slots=True)
class Hito:
    """Una fecha con nombre: una entrega, un inicio, un vencimiento."""

    que: str
    cuando: date | None = None
    origen: str = ""


@dataclass(frozen=True, slots=True)
class Enlace:
    """Un enlace del documento, con el texto que lo nombraba."""

    texto: str
    destino: str
    origen: str = ""


@dataclass(frozen=True, slots=True)
class Estado:
    """Lo que se sabe de un hilo. La forma entera está en `docs/contratos.md`.

    Los siete primeros campos son el contrato, y los cumple cualquier proveedor. Los
    cuatro últimos son procedencia: de qué archivo salió, cuándo se leyó, por qué
    salió flaco y qué secciones prometidas no estaban. Un programa externo puede
    omitirlos.
    """

    titulo: str = ""
    resumen: str = ""
    campos: dict[str, str] = field(default_factory=dict)
    pendientes: tuple[Pendiente, ...] = ()
    esperando: tuple[Espera, ...] = ()
    hitos: tuple[Hito, ...] = ()
    enlaces: tuple[Enlace, ...] = ()

    documento: Path | None = None
    leido: datetime | None = None
    #: por qué está vacío o incompleto, en una frase legible.
    nota: str = ""
    #: secciones que el arquetipo declaraba `requerida` y no estaban.
    faltan: tuple[str, ...] = ()

    @property
    def vacio(self) -> bool:
        return not any(getattr(self, campo) for campo in CONTRATO)

    def a_dict(self) -> dict[str, object]:
        """La forma JSON del contrato: la que imprime un proveedor `comando`."""
        return {
            "titulo": self.titulo,
            "resumen": self.resumen,
            "campos": dict(self.campos),
            "pendientes": [
                {
                    "texto": p.texto,
                    "hecho": p.hecho,
                    "en_curso": p.en_curso,
                    "id": p.id,
                    "origen": p.origen,
                }
                for p in self.pendientes
            ],
            "esperando": [
                {"texto": x.texto, "cuando": _iso(x.cuando), "origen": x.origen}
                for x in self.esperando
            ],
            "hitos": [
                {"que": h.que, "cuando": _iso(h.cuando), "origen": h.origen} for h in self.hitos
            ],
            "enlaces": [
                {"texto": x.texto, "destino": x.destino, "origen": x.origen} for x in self.enlaces
            ],
            "documento": str(self.documento) if self.documento else None,
            "leido": _iso(self.leido),
            "nota": self.nota,
            "faltan": list(self.faltan),
        }

    def a_ficha(self) -> Ficha:
        """El mismo estado en el vocabulario de `telar.modelo`.

        El `resumen` pasa a ser el `estado` de la ficha, y lo que no tiene lugar
        propio ahí —campos, esperas, hitos, enlaces— viaja en `secciones`, ya en
        JSON, para que quien dibuje no tenga que conocer estas clases.
        """
        crudo = self.a_dict()
        return Ficha(
            documento=self.documento,
            titulo=self.titulo,
            estado=self.resumen,
            pendientes=self.pendientes,
            secciones={
                clave: crudo[clave]
                for clave in ("campos", "esperando", "hitos", "enlaces")
                if crudo[clave]
            },
            leida=self.leido,
            nota=self.nota,
        )

    @classmethod
    def desde_dict(cls, datos: object, *, documento: Path | None = None) -> Estado:
        """Arma un `Estado` desde la forma JSON del contrato.

        Lo que no está en el contrato se ignora en vez de romper: el programa que
        imprimió esto puede llevar campos suyos, y telar no es quién para opinar. Lo
        que sí está tiene que tener la forma que dice el contrato.
        """
        if not isinstance(datos, dict):
            raise ErrorDeProveedor(
                f"el estado tenía que ser un objeto JSON, llegó {type(datos).__name__}"
            )

        ruta = _cadena(datos.get("documento"), "documento") or (str(documento) if documento else "")
        return cls(
            titulo=_cadena(datos.get("titulo"), "titulo"),
            resumen=_cadena(datos.get("resumen"), "resumen"),
            campos={
                _cadena(clave, "campos"): _cadena(valor, f"campos.{clave}")
                for clave, valor in _objeto(datos.get("campos", {}), "campos").items()
            },
            pendientes=tuple(
                Pendiente(
                    texto=_cadena(p.get("texto"), "pendientes[].texto"),
                    hecho=bool(p.get("hecho", False)),
                    en_curso=bool(p.get("en_curso", False)),
                    id=_cadena(p.get("id"), "pendientes[].id"),
                    origen=_cadena(p.get("origen"), "pendientes[].origen"),
                )
                for p in _objetos(datos.get("pendientes", []), "pendientes")
            ),
            esperando=tuple(
                Espera(
                    texto=_cadena(x.get("texto"), "esperando[].texto"),
                    cuando=_dia(x.get("cuando"), "esperando[].cuando"),
                    origen=_cadena(x.get("origen"), "esperando[].origen"),
                )
                for x in _objetos(datos.get("esperando", []), "esperando")
            ),
            hitos=tuple(
                Hito(
                    que=_cadena(h.get("que"), "hitos[].que"),
                    cuando=_dia(h.get("cuando"), "hitos[].cuando"),
                    origen=_cadena(h.get("origen"), "hitos[].origen"),
                )
                for h in _objetos(datos.get("hitos", []), "hitos")
            ),
            enlaces=tuple(
                Enlace(
                    texto=_cadena(x.get("texto"), "enlaces[].texto"),
                    destino=_cadena(x.get("destino"), "enlaces[].destino"),
                    origen=_cadena(x.get("origen"), "enlaces[].origen"),
                )
                for x in _objetos(datos.get("enlaces", []), "enlaces")
            ),
            documento=Path(ruta) if ruta else None,
            leido=_instante(datos.get("leido"), "leido"),
            nota=_cadena(datos.get("nota"), "nota"),
            faltan=tuple(
                _cadena(f, "faltan[]") for f in _secuencia(datos.get("faltan", []), "faltan")
            ),
        )


@runtime_checkable
class FuenteDeEstado(Protocol):
    """Quien sepa decir cómo va un hilo."""

    #: cómo se llama en la configuración.
    nombre: str
    #: qué toca del mundo, en una frase, para leerlo antes de encenderlo.
    alcance: str

    def leer(self, documento: Path, arquetipo: Arquetipo | None = None) -> Estado:
        """El estado del hilo cuyo documento es ese. Solo lee."""
        ...


# ── validación de la forma JSON ─────────────────────────────────────────────────

def _iso(valor: date | datetime | None) -> str | None:
    return valor.isoformat() if valor is not None else None


def _cadena(valor: object, contexto: str) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise ErrorDeProveedor(f"{contexto}: se esperaba texto, llegó {valor!r}")
    return valor


def _objeto(valor: object, contexto: str) -> dict:
    if not isinstance(valor, dict):
        raise ErrorDeProveedor(f"{contexto}: se esperaba un objeto, llegó {valor!r}")
    return valor


def _secuencia(valor: object, contexto: str) -> list:
    if not isinstance(valor, list):
        raise ErrorDeProveedor(f"{contexto}: se esperaba una lista, llegó {valor!r}")
    return valor


def _objetos(valor: object, contexto: str) -> list[dict]:
    items = _secuencia(valor, contexto)
    for item in items:
        _objeto(item, f"{contexto}[]")
    return items


def _dia(valor: object, contexto: str) -> date | None:
    if valor in (None, ""):
        return None
    texto = _cadena(valor, contexto)
    try:
        return date.fromisoformat(texto[:10])
    except ValueError as e:
        raise ErrorDeProveedor(
            f"{contexto}: se esperaba una fecha AAAA-MM-DD, llegó {texto!r}"
        ) from e


def _instante(valor: object, contexto: str) -> datetime | None:
    if valor in (None, ""):
        return None
    texto = _cadena(valor, contexto)
    try:
        return datetime.fromisoformat(texto)
    except ValueError as e:
        raise ErrorDeProveedor(f"{contexto}: se esperaba una fecha ISO, llegó {texto!r}") from e


# ── fechas, enlaces y front matter ──────────────────────────────────────────────

_ENLACE = re.compile(r"\[([^\]]*)\]\(\s*<?([^)\s>]+)>?[^)]*\)")
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

_ISO_FECHA = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DMA = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_DMES = re.compile(r"\b(\d{1,2})[ /-]([^\W\d_]{3,})\.?(?:[ /-](\d{4}))?\b")


def fecha_en(texto: str, *, meses: dict[str, int] = MESES, hoy: date | None = None) -> date | None:
    """La primera fecha reconocible del texto, o None.

    Entiende `AAAA-MM-DD`, `DD-MM-AAAA` y `DD-mes` con el mes en tres letras. La
    última sin año se resuelve con el año en curso, que es una suposición: en
    diciembre, un «5-ene» quiere decir el próximo, y esto va a decir que es el de
    este año. Quien necesite exactitud escribe la fecha entera.
    """
    if m := _ISO_FECHA.search(texto):
        return _armar(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if m := _DMA.search(texto):
        return _armar(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    # «5-ene» calza igual que «30 álamos»: se prueban todas y gana la que traiga mes.
    for m in _DMES.finditer(texto):
        if mes := meses.get(m.group(2)[:3].lower()):
            anio = int(m.group(3)) if m.group(3) else (hoy or date.today()).year
            return _armar(anio, mes, int(m.group(1)))
    return None


def _armar(anio: int, mes: int, dia: int) -> date | None:
    # Un `meses` mal escrito en la configuración da una fecha imposible, no una caída.
    try:
        return date(anio, mes, dia)
    except (ValueError, TypeError):
        return None


def _front_matter(texto: str) -> dict[str, str]:
    """Los pares `clave: valor` de la cabecera YAML, si la hay.

    A propósito no se llama a un parser de YAML: aquí solo interesan las líneas
    sueltas de la cabecera, y un front matter con estructura no es un campo.
    """
    m = _FRONT.match(texto)
    if not m:
        return {}
    pares: dict[str, str] = {}
    for linea in m.group(1).splitlines():
        if linea.startswith((" ", "\t", "-", "#")) or ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        valor = valor.strip().strip("\"'")
        if clave.strip() and valor:
            pares[clave.strip()] = valor
    return pares


def _enlaces_en(texto: str) -> list[Enlace]:
    """Los enlaces del documento, en orden y sin repetir destino."""
    vistos: set[str] = set()
    salida: list[Enlace] = []
    for m in _ENLACE.finditer(texto):
        destino = m.group(2)
        if destino in vistos:
            continue
        vistos.add(destino)
        salida.append(Enlace(texto=lectura.limpiar(m.group(1)) or destino, destino=destino))
    return salida


# ── la cascada ──────────────────────────────────────────────────────────────────

def cascada_por_defecto(arquetipo: Arquetipo) -> dict[str, tuple[str, ...]]:
    """De dónde sale cada campo del contrato cuando nadie lo dice.

    Se arma con lo que el arquetipo declaró: primero los tres nombres que telar ya
    entiende (`titulo`, `estado`, `pendientes`), después las demás secciones por su
    tipo. Un `esperando` o un `hitos` valen por su nombre, y esa es la única licencia
    que se toma este módulo: la configuración la puede desarmar entera.
    """
    nombres = {s.nombre for s in arquetipo.secciones}

    def de_tipo(*tipos: str, salvo: set[str]) -> tuple[str, ...]:
        return tuple(
            s.nombre for s in arquetipo.secciones if s.tipo in tipos and s.nombre not in salvo
        )

    esperando = ("esperando",) if "esperando" in nombres else ()
    hitos = ("hitos",) if "hitos" in nombres else ()
    reservadas = {"titulo", "estado", "pendientes", *esperando, *hitos}

    return {
        "titulo": ("titulo",) if "titulo" in nombres else (),
        "resumen": (("estado",) if "estado" in nombres else ())
        + de_tipo("parrafo", "linea", "texto", salvo=reservadas),
        "campos": de_tipo("tabla", salvo=set()),
        "pendientes": (("pendientes",) if "pendientes" in nombres else ())
        + de_tipo("casillas", "lista", salvo=reservadas),
        "esperando": esperando,
        "hitos": hitos,
    }


# ── proveedor `documento`: el markdown del hilo ─────────────────────────────────

class Documento:
    """Lee el documento del hilo y lo devuelve en la forma del contrato.

    El markdown lo parsea `telar.lectura`, que cumple lo que el perfil declaró; aquí
    se decide qué significa cada sección para el estado de un hilo.

    Opciones (van en `[proveedores.<nombre>]`, tal cual, sin que telar las interprete):

      `cascada`  mapa campo → lista de orígenes. Un origen es el nombre de una
                 sección del perfil, o `campo:Clave` para una fila de la tabla de
                 campos. Pisa entero el campo que nombre; lo que no nombre queda como
                 lo armó `cascada_por_defecto`.
      `marcas`   `hecho` y `en_curso`: qué más cuenta como marca, además de la
                 casilla del perfil (`✅`, `⏳`, `▶`).
      `maximo`   tope de elementos por campo. 0 = sin tope.
      `meses`    mapa de tres letras → número, para las fechas escritas a mano.
    """

    nombre = "documento"
    alcance = "lee archivos del repositorio de trabajo; no abre red ni escribe nada"

    def __init__(
        self,
        *,
        cascada: object = None,
        marcas: object = None,
        maximo: object = 0,
        meses: dict[str, int] | None = None,
    ) -> None:
        self.cascada = _validar_cascada(cascada)
        self.marcas = _validar_marcas(marcas)
        self.maximo = _validar_tope(maximo)
        self.meses = dict(meses) if meses else MESES

    @classmethod
    def desde_config(cls, cfg: ConfigProveedor) -> "Documento":
        opciones = dict(cfg.opciones)
        sobra = set(opciones) - {"cascada", "marcas", "maximo", "meses"}
        if sobra:
            raise ErrorDeProveedor(
                f"proveedores.{cfg.nombre}: opciones que el proveedor documento no conoce: "
                f"{', '.join(sorted(sobra))}"
            )
        return cls(
            cascada=opciones.get("cascada"),
            marcas=opciones.get("marcas"),
            maximo=opciones.get("maximo", 0),
            meses=opciones.get("meses"),  # type: ignore[arg-type]
        )

    # ── lectura ──
    def leer(self, documento: Path, arquetipo: Arquetipo | None = None) -> Estado:
        ruta = Path(documento)
        ahora = datetime.now()
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            # Un documento que no está no es una falla del proveedor: es un hilo sin
            # cara, y el telar tiene que poder mostrarlo igual.
            return Estado(
                documento=ruta, leido=ahora, nota=f"no se pudo leer {ruta}: {e.strerror or e}"
            )
        return self.desde_texto(texto, arquetipo, documento=ruta, leido=ahora)

    def desde_texto(
        self,
        texto: str,
        arquetipo: Arquetipo | None = None,
        *,
        documento: Path | None = None,
        leido: datetime | None = None,
    ) -> Estado:
        """El estado de un documento que ya se tiene en la mano, sin volver al disco."""
        arq = arquetipo or PERFIL_MINIMO.arquetipos[0]
        ahora = leido or datetime.now()
        ficha = lectura.parsear(texto, arq, documento=documento, leida=ahora)

        # `lectura` promueve los tres nombres conocidos a campos de la ficha; para la
        # cascada todo se mira igual, por el nombre que le puso el perfil.
        valores: dict[str, object] = dict(ficha.secciones)
        valores["titulo"] = ficha.titulo
        valores["estado"] = ficha.estado
        valores["pendientes"] = ficha.pendientes

        cascada = dict(cascada_por_defecto(arq))
        cascada.update(self.cascada)

        campos = self._campos(valores, cascada["campos"], _front_matter(texto))
        titulo = self._primero(valores, campos, cascada["titulo"])
        faltan = tuple(
            s.nombre for s in arq.secciones if s.requerida and not valores.get(s.nombre)
        )

        estado = Estado(
            titulo=titulo or self._titulo_por_ruta(documento, arq),
            resumen=self._primero(valores, campos, cascada["resumen"]),
            campos=campos,
            pendientes=tuple(self._pendientes(valores, cascada["pendientes"])),
            esperando=tuple(self._esperando(valores, cascada["esperando"])),
            hitos=tuple(self._hitos(valores, cascada["hitos"], campos)),
            enlaces=tuple(self._tope(_enlaces_en(texto))),
            documento=documento,
            leido=ahora,
            faltan=faltan,
        )
        return _con_nota(estado, arq, ficha.nota)

    # ── cada campo ──
    def _campos(
        self, valores: dict[str, object], origenes: tuple[str, ...], frente: dict[str, str]
    ) -> dict[str, str]:
        """Las tablas declaradas, en orden, y después el front matter para lo que falte."""
        campos: dict[str, str] = {}
        for origen in origenes:
            tabla = valores.get(origen)
            if isinstance(tabla, dict):
                for clave, valor in tabla.items():
                    campos.setdefault(str(clave), str(valor))
        for clave, valor in frente.items():
            campos.setdefault(clave, valor)
        return campos

    def _primero(
        self, valores: dict[str, object], campos: dict[str, str], origenes: tuple[str, ...]
    ) -> str:
        """La cascada de un campo singular: el primer origen que dé algo, y se acabó."""
        for origen in origenes:
            if origen.startswith("campo:"):
                clave = origen[len("campo:"):]
                if valor := campos.get(clave):
                    return f"{clave}: {valor}"
                continue
            valor = valores.get(origen)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
            if isinstance(valor, (tuple, list)) and valor:
                primero = valor[0]
                if isinstance(primero, str) and primero.strip():
                    return primero.strip()
                if isinstance(primero, Pendiente) and primero.texto:
                    return primero.texto
        return ""

    def _pendientes(self, valores: dict[str, object], origenes: tuple[str, ...]) -> list[Pendiente]:
        """Los orígenes se suman en orden; un mismo texto en dos secciones va una vez."""
        salida: list[Pendiente] = []
        vistos: set[str] = set()
        for origen in origenes:
            valor = valores.get(origen)
            if not isinstance(valor, (tuple, list)):
                continue
            for item in valor:
                pendiente = self._pendiente(item, origen)
                if pendiente is None or pendiente.texto in vistos:
                    continue
                vistos.add(pendiente.texto)
                salida.append(pendiente)
        return self._tope(salida)

    def _pendiente(self, item: object, origen: str) -> Pendiente | None:
        """Un ítem de sección como pendiente, con las marcas que el repositorio use."""
        if isinstance(item, Pendiente):
            base = item
        elif isinstance(item, str) and item.strip():
            base = Pendiente(texto=item.strip(), origen=origen)
        else:
            return None
        hecho, en_curso, texto = _marcar(base.texto, self.marcas)
        if not texto:
            return None
        return replace(base, texto=texto, hecho=base.hecho or hecho, en_curso=base.en_curso or en_curso)

    def _esperando(self, valores: dict[str, object], origenes: tuple[str, ...]) -> list[Espera]:
        salida: list[Espera] = []
        vistos: set[str] = set()
        for origen in origenes:
            for texto in self._textos(valores.get(origen)):
                if texto in vistos:
                    continue
                vistos.add(texto)
                salida.append(
                    Espera(texto=texto, cuando=fecha_en(texto, meses=self.meses), origen=origen)
                )
        return self._tope(salida)

    def _hitos(
        self, valores: dict[str, object], origenes: tuple[str, ...], campos: dict[str, str]
    ) -> list[Hito]:
        """Lo fechado: la sección de hitos, si la hay, y los campos que traen fecha."""
        salida: list[Hito] = []
        vistos: set[tuple[str, date | None]] = set()
        for origen in origenes:
            for texto in self._textos(valores.get(origen)):
                cuando = fecha_en(texto, meses=self.meses)
                if (texto, cuando) not in vistos:
                    vistos.add((texto, cuando))
                    salida.append(Hito(que=texto, cuando=cuando, origen=origen))
        for clave, valor in campos.items():
            cuando = fecha_en(valor, meses=self.meses)
            if cuando and (clave, cuando) not in vistos:
                vistos.add((clave, cuando))
                salida.append(Hito(que=clave, cuando=cuando, origen="campos"))
        salida.sort(key=lambda h: (h.cuando is None, h.cuando or date.max))
        return self._tope(salida)

    def _textos(self, valor: object) -> list[str]:
        """Las cadenas de una sección, venga como lista, como casillas o suelta.

        Lo marcado como hecho no sale: una espera cumplida ya no es una espera, y un
        hito cumplido lo dice quien lleva el calendario, no el README.
        """
        if isinstance(valor, str):
            return [valor.strip()] if valor.strip() else []
        if isinstance(valor, dict):
            return [f"{clave}: {v}" for clave, v in valor.items()]
        if not isinstance(valor, (tuple, list)):
            return []
        salida = []
        for item in valor:
            crudo = item.texto if isinstance(item, Pendiente) else item
            if not isinstance(crudo, str) or not crudo.strip():
                continue
            if isinstance(item, Pendiente) and item.hecho:
                continue
            hecho, _, texto = _marcar(crudo, self.marcas)
            if not hecho and texto:
                salida.append(texto)
        return salida

    def _tope(self, items: list) -> list:
        return items[: self.maximo] if self.maximo else items

    @staticmethod
    def _titulo_por_ruta(documento: Path | None, arquetipo: Arquetipo) -> str:
        """Sin título en el documento, el nombre de la carpeta (o del archivo) sirve."""
        if documento is None:
            return ""
        return documento.parent.name if arquetipo.por_carpeta else documento.stem


def _marcar(texto: str, marcas: dict[str, tuple[str, ...]]) -> tuple[bool, bool, str]:
    """Si el texto viene marcado como hecho o en curso, y el texto sin la marca.

    La casilla la resuelve `telar.lectura`; esto es lo que el repositorio marque
    además, al principio del texto. Solo valen las marcas que no son ASCII: si
    valiera la `x`, una viñeta que empieza con «xilófonos» quedaría hecha.
    """
    hecho = en_curso = False
    cambio = True
    while cambio:
        cambio = False
        pelado = texto.lstrip()
        for clave, marcados in (("hecho", marcas.get("hecho", ())), ("en_curso", marcas.get("en_curso", ()))):
            for prefijo in marcados:
                if prefijo and not prefijo.isascii() and pelado.startswith(prefijo):
                    texto = pelado[len(prefijo):]
                    hecho = hecho or clave == "hecho"
                    en_curso = en_curso or clave == "en_curso"
                    cambio = True
                    break
            if cambio:
                break
    return hecho, en_curso, texto.strip()


def _con_nota(estado: Estado, arquetipo: Arquetipo, nota: str) -> Estado:
    """Le pone al estado la razón de su flacura, si la tiene."""
    if nota:
        return replace(estado, nota=nota)
    if estado.vacio:
        return replace(
            estado,
            nota=f"el documento no trae ninguna de las secciones de «{arquetipo.nombre}»",
        )
    return estado


# ── proveedor `comando`: un programa que imprime el contrato ────────────────────

class Comando:
    """Corre un programa declarado y lee de su salida el JSON del contrato.

    Es la puerta para todo lo que telar no sabe leer: un gestor de tareas, una base
    de datos, un documento que no es markdown. El programa recibe la ruta del
    documento y devuelve por la salida estándar el objeto de `docs/contratos.md`.

    Opciones (`[proveedores.<nombre>]`):

      `comando`  lista de palabras, nunca una línea de shell. Marcadores que se
                 reemplazan en cada palabra: `{documento}`, `{ruta}` (la carpeta del
                 hilo), `{hilo}` (su nombre), `{arquetipo}`.
      `tiempo`   segundos antes de darlo por colgado. Por defecto, 10.

    Corre sin shell y con la carpeta del hilo por `cwd`. Lo que imprima por el error
    estándar no se interpreta: solo se cita si el programa falla.
    """

    nombre = "comando"
    alcance = "corre el programa que la configuración declara y lee su salida"

    def __init__(self, comando: object, *, tiempo: object = 10.0) -> None:
        if isinstance(comando, str) or not isinstance(comando, (list, tuple)) or not comando:
            raise ErrorDeProveedor("comando: se esperaba una lista de palabras, no una línea de shell")
        if not all(isinstance(palabra, str) for palabra in comando):
            raise ErrorDeProveedor("comando: todas las palabras tienen que ser texto")
        if isinstance(tiempo, bool) or not isinstance(tiempo, (int, float)) or tiempo <= 0:
            raise ErrorDeProveedor(f"tiempo: se esperaba un número positivo, llegó {tiempo!r}")
        self.comando = tuple(comando)
        self.tiempo = float(tiempo)

    @classmethod
    def desde_config(cls, cfg: ConfigProveedor) -> "Comando":
        opciones = dict(cfg.opciones)
        sobra = set(opciones) - {"comando", "tiempo"}
        if sobra:
            raise ErrorDeProveedor(
                f"proveedores.{cfg.nombre}: opciones que el proveedor comando no conoce: "
                f"{', '.join(sorted(sobra))}"
            )
        if "comando" not in opciones:
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}: falta `comando`")
        return cls(opciones["comando"], tiempo=opciones.get("tiempo", 10.0))

    def leer(self, documento: Path, arquetipo: Arquetipo | None = None) -> Estado:
        ruta = Path(documento)
        carpeta = ruta.parent
        marcadores = {
            "{documento}": str(ruta),
            "{ruta}": str(carpeta),
            "{hilo}": carpeta.name,
            "{arquetipo}": arquetipo.nombre if arquetipo else "",
        }
        linea = [_reemplazar(palabra, marcadores) for palabra in self.comando]

        try:
            corrida = subprocess.run(
                linea,
                capture_output=True,
                text=True,
                timeout=self.tiempo,
                cwd=str(carpeta) if carpeta.is_dir() else None,
            )
        except FileNotFoundError as e:
            raise ErrorDeProveedor(f"no se pudo correr {linea[0]!r}: {e.strerror or e}") from e
        except subprocess.TimeoutExpired as e:
            raise ErrorDeProveedor(f"{linea[0]!r} no respondió en {self.tiempo:g} s") from e
        except OSError as e:
            raise ErrorDeProveedor(f"no se pudo correr {linea[0]!r}: {e}") from e

        if corrida.returncode != 0:
            dicho = (corrida.stderr or corrida.stdout or "").strip().splitlines()
            raise ErrorDeProveedor(
                f"{linea[0]!r} salió con {corrida.returncode}: "
                f"{dicho[-1] if dicho else 'sin decir por qué'}"
            )

        try:
            datos = json.loads(corrida.stdout or "{}")
        except json.JSONDecodeError as e:
            raise ErrorDeProveedor(f"{linea[0]!r} no imprimió el JSON del contrato: {e}") from e

        return Estado.desde_dict(datos, documento=ruta)


def _reemplazar(palabra: str, marcadores: dict[str, str]) -> str:
    for marcador, valor in marcadores.items():
        palabra = palabra.replace(marcador, valor)
    return palabra


# ── validación de opciones ──────────────────────────────────────────────────────

def _validar_cascada(cascada: object) -> dict[str, tuple[str, ...]]:
    if cascada is None:
        return {}
    if not isinstance(cascada, dict):
        raise ErrorDeProveedor(f"cascada: se esperaba un mapa campo → orígenes, llegó {cascada!r}")
    salida: dict[str, tuple[str, ...]] = {}
    for campo, origenes in cascada.items():
        if campo not in CAMPOS_CASCADA:
            razon = (
                "los enlaces salen del documento entero, no de una sección"
                if campo == "enlaces"
                else f"no es un campo del contrato ({', '.join(CAMPOS_CASCADA)})"
            )
            raise ErrorDeProveedor(f"cascada.{campo}: {razon}")
        if isinstance(origenes, str) or not isinstance(origenes, (list, tuple)):
            raise ErrorDeProveedor(f"cascada.{campo}: se esperaba una lista de orígenes")
        if not all(isinstance(o, str) and o for o in origenes):
            raise ErrorDeProveedor(
                f"cascada.{campo}: cada origen es el nombre de una sección o `campo:Clave`"
            )
        salida[campo] = tuple(origenes)
    return salida


def _validar_marcas(marcas: object) -> dict[str, tuple[str, ...]]:
    if marcas is None:
        return dict(MARCAS)
    if not isinstance(marcas, dict):
        raise ErrorDeProveedor(
            f"marcas: se esperaba un mapa con `hecho` y `en_curso`, llegó {marcas!r}"
        )
    sobra = set(marcas) - {"hecho", "en_curso"}
    if sobra:
        raise ErrorDeProveedor(f"marcas: solo `hecho` y `en_curso`; sobra {', '.join(sorted(sobra))}")
    salida = dict(MARCAS)
    for clave, valores in marcas.items():
        if isinstance(valores, str) or not isinstance(valores, (list, tuple)):
            raise ErrorDeProveedor(f"marcas.{clave}: se esperaba una lista de marcas")
        if not all(isinstance(v, str) and v for v in valores):
            raise ErrorDeProveedor(f"marcas.{clave}: cada marca es un texto")
        salida[clave] = tuple(dict.fromkeys(salida[clave] + tuple(valores)))
    return salida


def _validar_tope(maximo: object) -> int:
    if isinstance(maximo, bool) or not isinstance(maximo, int) or maximo < 0:
        raise ErrorDeProveedor(f"maximo: se esperaba un entero ≥ 0, llegó {maximo!r}")
    return maximo


# ── registro ────────────────────────────────────────────────────────────────────

#: nombre → fábrica `(config.Proveedor) -> FuenteDeEstado`. Es un registro aparte del
#: de `telar.proveedores`: aquello trae ítems del día, esto responde por un documento.
REGISTRO: dict[str, object] = {
    "documento": Documento.desde_config,
    "comando": Comando.desde_config,
}


def registrar(nombre: str, fabrica) -> None:
    """Deja disponible otro proveedor de estado."""
    if nombre in REGISTRO:
        raise ValueError(f"ya hay un proveedor de estado llamado {nombre!r}")
    REGISTRO[nombre] = fabrica


def obtener(cfg: ConfigProveedor) -> FuenteDeEstado:
    """Construye el proveedor de estado que la configuración declara."""
    fabrica = REGISTRO.get(cfg.nombre)
    if fabrica is None:
        conocidos = ", ".join(sorted(REGISTRO)) or "ninguno"
        raise ErrorDeProveedor(
            f"no hay un proveedor de estado llamado {cfg.nombre!r}; registrados: {conocidos}"
        )
    return fabrica(cfg)  # type: ignore[operator]


def leer(documento: Path, arquetipo: Arquetipo | None = None, **opciones: object) -> Estado:
    """Atajo para el caso de siempre: el documento de un hilo, leído con su perfil.

    Es el proveedor `documento` sin pasar por la configuración. Leer un archivo del
    repositorio que el usuario ya señaló no es salir al mundo, así que no hace falta
    declararlo; el `comando`, que corre un programa, sí.
    """
    return Documento(**opciones).leer(Path(documento), arquetipo)  # type: ignore[arg-type]
