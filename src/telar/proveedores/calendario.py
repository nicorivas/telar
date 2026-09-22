"""La agenda del día: qué hay a qué hora, y dónde se entra.

Un día de trabajo no se ordena solo por lo pendiente: hay horas ya comprometidas,
y saber cuáles son cambia qué se puede empezar ahora. Este proveedor responde una
sola pregunta —qué hay hoy— y la responde con cuatro datos: cuándo empieza, cuándo
termina, cómo se llama y por dónde se entra.

Cuatro implementaciones:

  * `ics`      un calendario en formato iCalendar, archivo local o URL. Es el
               formato que exportan todos: no hace falta una cuenta ni una API.
  * `gws`      Google Calendar con la CLI `gws`, con la cuenta que ya tenga conectada.
               Sin dirección que pegar ni secreto que guardar.
  * `comando`  un programa externo que imprime JSON. Para todo lo demás.
  * `ninguno`  la forma explícita de no tener agenda.

Solo `ics` con `url` sale a la red, y lo dice en su `alcance` antes de que nadie
lo encienda. Con `archivo`, no se abre ningún socket.

Cómo se enciende, en `~/.config/telar/config.toml`:

    [proveedores.calendario]
    tipo = "ics"
    url  = "https://…/basic.ics"     # o bien: archivo = "~/agenda.ics"

    [proveedores.calendario]
    tipo    = "comando"
    comando = ["mi-agenda", "--json", "{dia}"]

Importar este módulo lo deja disponible en `telar.proveedores.REGISTRO`; que se
consulte o no lo sigue decidiendo la configuración.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telar import proveedores
from telar.config import Proveedor as ConfigProveedor
from telar.modelo import Item
from telar.proveedores import ErrorDeProveedor

__all__ = [
    "NOMBRE",
    "Evento",
    "FuenteDeCalendario",
    "leer_ics",
    "eventos_del_dia",
    "IMPLEMENTACIONES",
    "construir",
    "registrar",
]

#: Cómo se llama en la configuración: `[proveedores.calendario]`.
NOMBRE = "calendario"

#: Tope de lo que se baja de una URL. Una agenda no pesa esto ni de lejos; el tope
#: está para que un servidor equivocado no se lleve la memoria de la máquina.
TOPE_DESCARGA = 8 * 1024 * 1024


def tapar(url: str) -> str:
    """Una dirección iCal sin su parte secreta: se ve de dónde es, no cómo entrar.

    Las direcciones privadas de Google llevan la clave en el camino (`private-…`), y
    quien la tiene ve la agenda entera. Se deja el servidor y el primer tramo, lo justo
    para reconocerla en un mensaje o en una pantalla.
    """
    from urllib.parse import urlsplit

    partes = urlsplit(url)
    if not partes.scheme or not partes.netloc:
        return "…"
    tramo = next((p for p in partes.path.split("/") if p), "")
    return f"{partes.scheme}://{partes.netloc}/{tramo}/…" if tramo else f"{partes.scheme}://{partes.netloc}/…"


def _zona_local() -> timezone:
    """La zona del reloj de esta máquina, ya resuelta a un offset fijo del momento."""
    return datetime.now().astimezone().tzinfo  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Evento:
    """Algo que ocupa una hora del día.

    `inicio` y `fin` son siempre con zona horaria: un evento sin zona miente en
    cuanto el calendario cruza un huso. Los de día completo empiezan a la medianoche
    local y traen `todo_el_dia`, para que quien dibuje no escriba «00:00».
    """

    id: str
    titulo: str
    inicio: datetime
    fin: datetime | None = None
    enlace: str = ""
    todo_el_dia: bool = False
    lugar: str = ""
    origen: str = ""

    @property
    def duracion(self) -> timedelta | None:
        return self.fin - self.inicio if self.fin else None

    def item(self, *, proveedor: str = NOMBRE, hilo: str = "") -> Item:
        """El mismo evento en la moneda de `telar.proveedores`."""
        return Item(
            proveedor=proveedor,
            id=self.id,
            titulo=self.titulo,
            cuando=self.inicio,
            clase="evento",
            hilo=hilo,
            url=self.enlace,
            datos={
                "fin": self.fin.isoformat() if self.fin else None,
                "todo_el_dia": self.todo_el_dia,
                "lugar": self.lugar,
                "origen": self.origen,
            },
        )


@runtime_checkable
class FuenteDeCalendario(Protocol):
    """Un proveedor de agenda: `Fuente` más la vista que conserva las horas."""

    nombre: str
    alcance: str

    def eventos(self, dia: date) -> list[Evento]:
        """Los eventos de ese día, ordenados por hora de inicio. Solo lee."""
        ...

    def consultar(self, dia: date) -> list[Item]:
        ...


class _Base:
    """`consultar` sale de `eventos`: una implementación solo escribe `eventos`."""

    nombre = NOMBRE
    alcance = ""

    def eventos(self, dia: date) -> list[Evento]:  # pragma: no cover - lo cumple cada una
        raise NotImplementedError

    def consultar(self, dia: date) -> list[Item]:
        return [e.item(proveedor=self.nombre) for e in self.eventos(dia)]


# ── iCalendar: leer el .ics ─────────────────────────────────────────────────────
#
# Se lee a mano y con la biblioteca estándar: un calendario es texto plegado en
# líneas de 75 octetos, y para la única pregunta que nos importa —qué hay hoy—
# alcanza con desplegarlo, quedarse con los VEVENT y saber si la regla de repetición
# cae en la fecha. Lo que NO se entiende, dicho de frente: las instancias
# modificadas de una serie (RECURRENCE-ID), BYSETPOS, BYMONTHDAY y BYDAY con
# ordinal (`3TH`), y los husos definidos dentro del propio archivo (VTIMEZONE): un
# TZID se resuelve contra la base de datos del sistema.

@dataclass(slots=True)
class _Vevento:
    """Un VEVENT ya leído, antes de saber si cae en el día que se pregunta."""

    uid: str = ""
    titulo: str = ""
    inicio: datetime | None = None
    duracion: timedelta = timedelta(0)
    todo_el_dia: bool = False
    enlace: str = ""
    lugar: str = ""
    cancelado: bool = False
    regla: dict[str, str] = field(default_factory=dict)
    excluidas: set[date] = field(default_factory=set)
    #: si este VEVENT es la excepción de una serie (RECURRENCE-ID), el día de la
    #: instancia que reemplaza. La serie no debe generar ese día por su cuenta.
    reemplaza: date | None = None


def desplegar(texto: str) -> list[str]:
    """Deshace el plegado de líneas del formato: una continuación empieza con espacio."""
    lineas: list[str] = []
    for cruda in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if cruda[:1] in (" ", "\t") and lineas:
            lineas[-1] += cruda[1:]
        else:
            lineas.append(cruda)
    return lineas


def _propiedad(linea: str) -> tuple[str, dict[str, str], str] | None:
    """`NOMBRE;PARAM=VALOR:valor` → (NOMBRE, {PARAM: VALOR}, valor).

    El primer `:` manda, salvo que venga dentro de comillas (un TZID puede traerlas).
    """
    comillas = False
    corte = -1
    for i, c in enumerate(linea):
        if c == '"':
            comillas = not comillas
        elif c == ":" and not comillas:
            corte = i
            break
    if corte < 0:
        return None
    cabeza, valor = linea[:corte], linea[corte + 1 :]
    partes = cabeza.split(";")
    nombre = partes[0].strip().upper()
    params: dict[str, str] = {}
    for p in partes[1:]:
        clave, _, v = p.partition("=")
        params[clave.strip().upper()] = v.strip().strip('"')
    return nombre, params, valor


def _desescapar(valor: str) -> str:
    salida, i = [], 0
    while i < len(valor):
        c = valor[i]
        if c == "\\" and i + 1 < len(valor):
            siguiente = valor[i + 1]
            salida.append({"n": "\n", "N": "\n"}.get(siguiente, siguiente))
            i += 2
            continue
        salida.append(c)
        i += 1
    return "".join(salida)


def _zona(tzid: str | None, local: timezone) -> object:
    if not tzid:
        return local
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return local  # un huso que esta máquina no conoce vale menos que no mostrar nada


def _momento(valor: str, params: dict[str, str], local: timezone) -> tuple[datetime, bool]:
    """Un DTSTART/DTEND → (datetime con zona, si es de día completo)."""
    crudo = valor.strip().split(",")[0]
    if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", crudo):
        d = datetime.strptime(crudo[:8], "%Y%m%d").date()
        return datetime.combine(d, time.min, tzinfo=local), True
    m = re.fullmatch(r"(\d{8})T(\d{6})(Z)?", crudo)
    if not m:
        raise ValueError(f"no entiendo la fecha {crudo!r}")
    d = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    zona = timezone.utc if m.group(3) else _zona(params.get("TZID"), local)
    return d.replace(tzinfo=zona), False  # type: ignore[arg-type]


DURACION = re.compile(
    r"^(?P<signo>[+-])?P(?:(?P<sem>\d+)W)?(?:(?P<dia>\d+)D)?"
    r"(?:T(?:(?P<hora>\d+)H)?(?:(?P<min>\d+)M)?(?:(?P<seg>\d+)S)?)?$"
)


def _duracion(valor: str) -> timedelta:
    m = DURACION.fullmatch(valor.strip())
    if not m:
        raise ValueError(f"no entiendo la duración {valor!r}")
    n = {k: int(v) for k, v in m.groupdict().items() if k != "signo" and v}
    d = timedelta(
        weeks=n.get("sem", 0), days=n.get("dia", 0),
        hours=n.get("hora", 0), minutes=n.get("min", 0), seconds=n.get("seg", 0),
    )
    return -d if m.group("signo") == "-" else d


def leer_ics(texto: str, *, local: timezone | None = None) -> list[_Vevento]:
    """Los VEVENT de un calendario, sin interpretar todavía las repeticiones.

    Lo que no se entiende de un evento suelto lo descarta a él y no al archivo: un
    calendario grande casi siempre trae alguna línea rara.
    """
    local = local or _zona_local()
    salida: list[_Vevento] = []
    pila: list[str] = []
    actual: _Vevento | None = None
    fin: datetime | None = None
    duracion: timedelta | None = None
    roto = False

    for linea in desplegar(texto):
        p = _propiedad(linea)
        if p is None:
            continue
        nombre, params, valor = p

        if nombre == "BEGIN":
            pila.append(valor.strip().upper())
            if pila[-1] == "VEVENT":
                actual, fin, duracion, roto = _Vevento(), None, None, False
            continue
        if nombre == "END":
            cerrado = pila.pop() if pila else ""
            if cerrado == "VEVENT" and actual is not None:
                if not roto and actual.inicio is not None:
                    if duracion is not None:
                        actual.duracion = duracion
                    elif fin is not None:
                        actual.duracion = max(fin - actual.inicio, timedelta(0))
                    elif actual.todo_el_dia:
                        actual.duracion = timedelta(days=1)
                    salida.append(actual)
                actual = None
            continue

        if actual is None or pila[-1:] != ["VEVENT"]:
            continue  # propiedades del calendario, o de un VALARM adentro del evento

        try:
            if nombre == "UID":
                actual.uid = _desescapar(valor).strip()
            elif nombre == "SUMMARY":
                actual.titulo = _desescapar(valor).strip()
            elif nombre == "LOCATION":
                actual.lugar = _desescapar(valor).strip()
            elif nombre == "URL":
                actual.enlace = valor.strip()
            elif nombre == "STATUS":
                actual.cancelado = valor.strip().upper() == "CANCELLED"
            elif nombre == "DTSTART":
                actual.inicio, actual.todo_el_dia = _momento(valor, params, local)
            elif nombre == "DTEND":
                fin, _ = _momento(valor, params, local)
            elif nombre == "DURATION":
                duracion = _duracion(valor)
            elif nombre == "RRULE":
                actual.regla = {
                    k.strip().upper(): v.strip()
                    for k, _, v in (p.partition("=") for p in valor.split(";"))
                    if k.strip()
                }
            elif nombre == "RECURRENCE-ID":
                actual.reemplaza = _momento(valor, params, local)[0].date()
            elif nombre == "EXDATE":
                for trozo in valor.split(","):
                    if trozo.strip():
                        actual.excluidas.add(_momento(trozo, params, local)[0].date())
        except ValueError:
            roto = True

    return salida


def _serie(inicio: date, freq: str, intervalo: int, bydays: list[int], limite: date, tope: int = 4000):
    """Las fechas que genera la regla, en orden, hasta `limite` inclusive.

    Con tope de pasos: una regla mal escrita no puede colgar el telar.
    """
    if freq == "DAILY":
        d = inicio
        while d <= limite and tope > 0:
            yield d
            d += timedelta(days=intervalo)
            tope -= 1
    elif freq == "WEEKLY":
        dias = sorted(set(bydays)) or [inicio.weekday()]
        semana = inicio - timedelta(days=inicio.weekday())
        while semana <= limite and tope > 0:
            for wd in dias:
                d = semana + timedelta(days=wd)
                if inicio <= d <= limite:
                    yield d
            semana += timedelta(weeks=intervalo)
            tope -= 1
    elif freq in ("MONTHLY", "YEARLY"):
        paso_meses = intervalo if freq == "MONTHLY" else intervalo * 12
        y, m = inicio.year, inicio.month
        while tope > 0:
            try:
                d = date(y, m, inicio.day)
            except ValueError:
                d = None  # el 31 en un mes que no lo tiene: esa vuelta no genera nada
            if d is not None:
                if d > limite:
                    return
                if d >= inicio:
                    yield d
            total = (y * 12 + m - 1) + paso_meses
            y, m = divmod(total, 12)
            m += 1
            if date(y, m, 1) > limite:
                return
            tope -= 1


def _hasta(bruto: str) -> date | datetime:
    """El UNTIL de una regla: una fecha, o un instante si trae hora (`…T045959Z`)."""
    crudo = bruto.strip()
    if "T" not in crudo:
        return datetime.strptime(crudo[:8], "%Y%m%d").date()
    if crudo.endswith("Z"):
        return datetime.strptime(crudo[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    return datetime.strptime(crudo[:15], "%Y%m%dT%H%M%S").replace(tzinfo=_zona_local())


def _ocurre(v: _Vevento, fecha: date) -> bool:
    """¿La serie del evento tiene una ocurrencia que empiece ese día, en su zona?"""
    assert v.inicio is not None
    base = v.inicio.date()
    if fecha in v.excluidas:
        return False
    if not v.regla:
        return fecha == base
    if fecha < base:
        return False

    freq = v.regla.get("FREQ", "").upper()
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        return fecha == base

    try:
        intervalo = max(int(v.regla.get("INTERVAL", "1")), 1)
    except ValueError:
        intervalo = 1
    if hasta := v.regla.get("UNTIL", ""):
        try:
            tope = _hasta(hasta)
            if isinstance(tope, date) and not isinstance(tope, datetime):
                if fecha > tope:
                    return False
            elif v.inicio is not None:
                # comparar solo la fecha daba una instancia de más: Google cierra una serie
                # semanal con UNTIL a las 04:59:59Z, que es la noche del día anterior
                arranque = datetime.combine(fecha, v.inicio.time(), tzinfo=v.inicio.tzinfo)
                if arranque > tope:
                    return False
            elif fecha > tope.date():
                return False
        except ValueError:
            pass
    cuenta = None
    if bruto := v.regla.get("COUNT", ""):
        try:
            cuenta = int(bruto)
        except ValueError:
            cuenta = None

    semana = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
    bydays = [semana[d[-2:].upper()] for d in v.regla.get("BYDAY", "").split(",")
              if d[-2:].upper() in semana and d[:-2] in ("", "+", "-")]

    for i, d in enumerate(_serie(base, freq, intervalo, bydays, fecha)):
        if cuenta is not None and i >= cuenta:
            return False
        if d == fecha:
            return True
    return False


def eventos_del_dia(
    veventos: Iterable[_Vevento], dia: date, *, origen: str = "", local: timezone | None = None
) -> list[Evento]:
    """Los eventos que ocupan algo de ese día, ordenados por hora.

    Un evento cuenta si su tramo pisa el día, no solo si empieza en él: una reunión
    que arrancó anoche y termina en la mañana es parte de hoy. Por eso se prueban
    también los días anteriores, tantos como dure el evento más largo.
    """
    local = local or _zona_local()
    desde = datetime.combine(dia, time.min, tzinfo=local)
    hasta = desde + timedelta(days=1)
    salida: dict[tuple[str, datetime], Evento] = {}

    # una excepción (RECURRENCE-ID) reemplaza a la instancia de su serie: si no, la reunión
    # que se movió una hora aparece dos veces, en su hora vieja y en la nueva
    reemplazadas = {
        (v.uid, v.reemplaza) for v in veventos if v.reemplaza is not None and v.uid
    }

    for v in veventos:
        if v.cancelado or v.inicio is None:
            continue
        # la ventana hacia atrás cubre lo que dura el evento, más un día por el desfase
        # entre la zona del calendario y la de esta máquina.
        atras = min(max(v.duracion.days, 0), 31) + 1
        for n in range(-atras, 2):
            arranque = dia + timedelta(days=n)
            if not _ocurre(v, arranque):
                continue
            if v.reemplaza is None and (v.uid, arranque) in reemplazadas:
                continue
            inicio = datetime.combine(arranque, v.inicio.time(), tzinfo=v.inicio.tzinfo)
            inicio = inicio.astimezone(local)
            fin = (inicio + v.duracion) if v.duracion else None
            dentro = inicio < hasta and (fin > desde if fin else inicio >= desde)
            if not dentro:
                continue
            id = f"{v.uid or v.titulo}@{arranque.isoformat()}"
            salida[(v.uid or v.titulo, inicio)] = Evento(
                id=id,
                titulo=v.titulo,
                inicio=inicio,
                fin=fin,
                enlace=v.enlace,
                todo_el_dia=v.todo_el_dia,
                lugar=v.lugar,
                origen=origen,
            )

    return sorted(salida.values(), key=lambda e: (e.inicio, e.titulo))


class DeICS(_Base):
    """Un calendario iCalendar: un archivo de la máquina, o una URL que lo publica.

    Con `archivo` no se abre ningún socket. Con `url` se baja cada vez que se
    consulta, y el intervalo con que se consulta lo pone `intervalos.proveedores`.
    """

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        opciones = cfg.opciones
        archivo, url = opciones.get("archivo"), opciones.get("url")
        if bool(archivo) == bool(url):
            raise ErrorDeProveedor(
                f"proveedores.{cfg.nombre}: se esperaba exactamente uno de 'archivo' o 'url'"
            )
        self.archivo: Path | None = None
        self.url = ""
        if archivo:
            if not isinstance(archivo, str) or not archivo.strip():
                raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.archivo: se esperaba una ruta")
            self.archivo = Path(archivo).expanduser()
            self.alcance = f"lee el archivo {self.archivo}; no sale de la máquina"
        else:
            if not isinstance(url, str) or not url.strip():
                raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.url: se esperaba una URL")
            if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
                raise ErrorDeProveedor(
                    f"proveedores.{cfg.nombre}.url: solo http(s); para un archivo local, usa 'archivo'"
                )
            self.url = url.strip()
            self.alcance = f"descarga {tapar(self.url)} cada vez que se consulta"

        espera = opciones.get("tiempo_maximo", 10)
        if isinstance(espera, bool) or not isinstance(espera, (int, float)) or espera <= 0:
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tiempo_maximo: se esperaba un número positivo")
        self.tiempo_maximo = float(espera)

    def _texto(self) -> str:
        if self.archivo is not None:
            try:
                return self.archivo.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                raise ErrorDeProveedor(f"{self.archivo}: no se pudo leer: {e}") from e
        peticion = urllib.request.Request(self.url, headers={"Accept": "text/calendar"})
        try:
            with urllib.request.urlopen(peticion, timeout=self.tiempo_maximo) as r:  # noqa: S310
                crudo = r.read(TOPE_DESCARGA + 1)
        except urllib.error.HTTPError as e:
            raise ErrorDeProveedor(f"{tapar(self.url)}: el servidor respondió {e.code}") from e
        except (urllib.error.URLError, OSError) as e:
            raise ErrorDeProveedor(f"{tapar(self.url)}: no se pudo bajar: {e}") from e
        if len(crudo) > TOPE_DESCARGA:
            raise ErrorDeProveedor(f"{tapar(self.url)}: pesa más de {TOPE_DESCARGA // (1024 * 1024)} MiB")
        return crudo.decode("utf-8", errors="replace")

    def eventos(self, dia: date) -> list[Evento]:
        origen = str(self.archivo) if self.archivo is not None else tapar(self.url)
        return eventos_del_dia(leer_ics(self._texto()), dia, origen=origen)


# ── comando: un programa externo que imprime JSON ───────────────────────────────

class DeComando(_Base):
    """Un programa de afuera dice qué hay hoy, en JSON.

    Recibe el día en `$TELAR_DIA` y en cualquier palabra que diga `{dia}`, y tiene
    que imprimir una lista (o un objeto con la clave `eventos`) de objetos así:

        [{"id": "a1", "titulo": "Comité", "inicio": "2026-09-18T10:00:00-03:00",
          "fin": "2026-09-18T11:00:00-03:00", "enlace": "https://…",
          "lugar": "sala 2", "todo_el_dia": false}]

    De todo eso, solo `titulo` e `inicio` son obligatorios. Una hora sin zona se
    entiende como la de esta máquina.
    """

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        opciones = cfg.opciones
        comando = opciones.get("comando")
        if (
            not isinstance(comando, list)
            or not comando
            or not all(isinstance(x, str) for x in comando)
        ):
            raise ErrorDeProveedor(
                f"proveedores.{cfg.nombre}.comando: se esperaba una lista de palabras, "
                "no una línea de shell (si hace falta shell, pídela: [\"sh\", \"-c\", \"…\"])"
            )
        self.comando = tuple(comando)
        donde = opciones.get("donde")
        if donde is not None and (not isinstance(donde, str) or not donde.strip()):
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.donde: se esperaba una ruta")
        self.donde = Path(donde).expanduser() if donde else None
        espera = opciones.get("tiempo_maximo", 10)
        if isinstance(espera, bool) or not isinstance(espera, (int, float)) or espera <= 0:
            raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tiempo_maximo: se esperaba un número positivo")
        self.tiempo_maximo = float(espera)
        self.alcance = f"corre `{' '.join(self.comando)}` y lee su JSON"

    def eventos(self, dia: date) -> list[Evento]:
        palabras = [p.replace("{dia}", dia.isoformat()) for p in self.comando]
        entorno = dict(os.environ, TELAR_DIA=dia.isoformat())
        try:
            r = subprocess.run(
                palabras,
                capture_output=True,
                text=True,
                timeout=self.tiempo_maximo,
                cwd=str(self.donde) if self.donde else None,
                env=entorno,
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError as e:
            raise ErrorDeProveedor(f"no existe el programa {palabras[0]!r}") from e
        except subprocess.TimeoutExpired as e:
            raise ErrorDeProveedor(f"{palabras[0]} no respondió en {self.tiempo_maximo:g} s") from e
        except OSError as e:
            raise ErrorDeProveedor(f"{palabras[0]}: no se pudo correr: {e}") from e
        if r.returncode != 0:
            queja = (r.stderr or "").strip().splitlines()
            detalle = f": {queja[0]}" if queja else ""
            raise ErrorDeProveedor(f"{palabras[0]} salió con {r.returncode}{detalle}")

        try:
            datos = json.loads(r.stdout or "[]")
        except json.JSONDecodeError as e:
            raise ErrorDeProveedor(f"{palabras[0]} no imprimió JSON: {e}") from e
        if isinstance(datos, dict):
            datos = datos.get("eventos", [])
        if not isinstance(datos, list):
            raise ErrorDeProveedor(f"{palabras[0]}: se esperaba una lista de eventos")

        eventos = [_evento_de_json(d, palabras[0], i) for i, d in enumerate(datos)]
        return sorted(eventos, key=lambda e: (e.inicio, e.titulo))


def _hora(valor: object, contexto: str, local: timezone) -> datetime:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorDeProveedor(f"{contexto}: se esperaba una hora en ISO 8601, llegó {valor!r}")
    try:
        d = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    except ValueError as e:
        raise ErrorDeProveedor(f"{contexto}: {valor!r} no es una hora en ISO 8601") from e
    return d if d.tzinfo else d.replace(tzinfo=local)


def _evento_de_json(datos: object, origen: str, indice: int) -> Evento:
    contexto = f"{origen}[{indice}]"
    if not isinstance(datos, dict):
        raise ErrorDeProveedor(f"{contexto}: se esperaba un objeto, llegó {datos!r}")
    local = _zona_local()

    titulo = datos.get("titulo")
    if not isinstance(titulo, str) or not titulo.strip():
        raise ErrorDeProveedor(f"{contexto}: falta 'titulo'")

    def texto_de(clave: str) -> str:
        valor = datos.get(clave, "")
        if valor in (None, ""):
            return ""
        if not isinstance(valor, str):
            raise ErrorDeProveedor(f"{contexto}.{clave}: se esperaba texto, llegó {valor!r}")
        return valor

    todo_el_dia = datos.get("todo_el_dia", False)
    if not isinstance(todo_el_dia, bool):
        raise ErrorDeProveedor(f"{contexto}.todo_el_dia: se esperaba true o false")

    inicio = _hora(datos.get("inicio"), f"{contexto}.inicio", local)
    fin = _hora(datos["fin"], f"{contexto}.fin", local) if datos.get("fin") else None
    if fin is not None and fin < inicio:
        raise ErrorDeProveedor(f"{contexto}: termina antes de empezar")

    return Evento(
        id=texto_de("id") or f"{origen}:{indice}",
        titulo=titulo.strip(),
        inicio=inicio,
        fin=fin,
        enlace=texto_de("enlace"),
        todo_el_dia=todo_el_dia,
        lugar=texto_de("lugar"),
        origen=texto_de("origen") or origen,
    )


# ── ninguno: la forma explícita de no tener agenda ──────────────────────────────

class DeGws(_Base):
    """Google Calendar a través de `gws`, la CLI de Google Workspace.

    No pide ninguna dirección ni guarda ningún secreto: usa la cuenta con la que `gws` ya
    está conectado en esta máquina. Es el camino cuando el administrador del dominio
    desactivó la dirección iCal secreta, y el que sirve para más cosas que la agenda
    (`gws` también lee el correo).

        [proveedores.calendario]
        tipo = "gws"
        calendario = "primary"   # opcional: el id de otro calendario de la cuenta

    Se descartan los eventos cancelados y los que la persona rechazó: no ocupan su hora.
    """

    tiempo_maximo = 40.0

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        opciones = cfg.opciones
        self.programa = str(opciones.get("programa") or "gws")
        self.calendario = str(opciones.get("calendario") or "primary")
        self.alcance = (
            f"consulta Google Calendar con `{self.programa}`, con la cuenta que tenga conectada"
        )

    def eventos(self, dia: date) -> list[Evento]:
        local = _zona_local()
        desde = datetime.combine(dia, time.min, tzinfo=local)
        hasta = desde + timedelta(days=1)
        params = {
            "calendarId": self.calendario,
            "timeMin": desde.isoformat(),
            "timeMax": hasta.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
        }
        palabras = [self.programa, "calendar", "events", "list",
                    "--params", json.dumps(params), "--format", "json"]
        try:
            r = subprocess.run(palabras, capture_output=True, text=True,
                               timeout=self.tiempo_maximo, stdin=subprocess.DEVNULL)
        except FileNotFoundError as e:
            raise ErrorDeProveedor(f"no está instalado {self.programa!r}") from e
        except subprocess.TimeoutExpired as e:
            raise ErrorDeProveedor(f"{self.programa} no respondió en {self.tiempo_maximo:g} s") from e
        if r.returncode != 0:
            queja = [x for x in (r.stderr or r.stdout or "").splitlines() if x.strip()]
            raise ErrorDeProveedor(f"{self.programa} salió con {r.returncode}"
                                   + (f": {queja[-1].strip()}" if queja else ""))
        return eventos_de_gws(r.stdout, local)


def eventos_de_gws(salida: str, local: timezone | None = None) -> list[Evento]:
    """La respuesta de `gws calendar events list`, en eventos de telar."""
    local = local or _zona_local()
    inicio_json = salida.find("{")
    if inicio_json < 0:
        raise ErrorDeProveedor("gws no devolvió JSON")
    try:
        datos = json.loads(salida[inicio_json:])
    except json.JSONDecodeError as e:
        raise ErrorDeProveedor(f"gws devolvió algo que no es JSON: {e}") from e
    eventos: list[Evento] = []
    for e in datos.get("items", []) or []:
        if e.get("status") == "cancelled":
            continue
        yo = next((a for a in e.get("attendees", []) or [] if a.get("self")), {})
        if yo.get("responseStatus") == "declined":
            continue
        ini, fin = e.get("start") or {}, e.get("end") or {}
        if "dateTime" in ini:
            comienzo = datetime.fromisoformat(ini["dateTime"])
            final = datetime.fromisoformat(fin["dateTime"]) if "dateTime" in fin else None
            todo = False
        elif "date" in ini:
            comienzo = datetime.combine(date.fromisoformat(ini["date"]), time.min, tzinfo=local)
            final, todo = None, True
        else:
            continue
        video = next((p.get("uri", "") for p in ((e.get("conferenceData") or {}).get("entryPoints") or [])
                      if p.get("entryPointType") == "video"), "")
        eventos.append(Evento(
            id=str(e.get("id", "")),
            titulo=e.get("summary") or "(sin título)",
            inicio=comienzo,
            fin=final,
            enlace=e.get("hangoutLink") or video or e.get("htmlLink", ""),
            todo_el_dia=todo,
            lugar=e.get("location", ""),
            origen="gws",
        ))
    return sorted(eventos, key=lambda x: (x.inicio, x.titulo))


class Ninguno(_Base):
    """Apagado, pero dicho. Sirve para dejar la sección escrita sin que consulte nada."""

    def __init__(self, cfg: ConfigProveedor) -> None:
        self.nombre = cfg.nombre
        self.alcance = "no toca nada"

    def eventos(self, dia: date) -> list[Evento]:
        return []


# ── de dónde sale la implementación ─────────────────────────────────────────────

IMPLEMENTACIONES = {
    "ics": DeICS,
    "gws": DeGws,
    "comando": DeComando,
    "ninguno": Ninguno,
}


def construir(cfg: ConfigProveedor) -> FuenteDeCalendario:
    """La implementación que dice `tipo`. Sin `tipo`, se dice en voz alta."""
    tipo = cfg.opciones.get("tipo")
    if tipo is None:
        conocidas = ", ".join(sorted(IMPLEMENTACIONES))
        raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tipo: falta; es una de: {conocidas}")
    clase = IMPLEMENTACIONES.get(tipo) if isinstance(tipo, str) else None
    if clase is None:
        conocidas = ", ".join(sorted(IMPLEMENTACIONES))
        raise ErrorDeProveedor(f"proveedores.{cfg.nombre}.tipo: {tipo!r} no es una de: {conocidas}")
    return clase(cfg)


def registrar() -> None:
    """Deja este proveedor disponible. Encenderlo sigue siendo de la configuración."""
    if NOMBRE not in proveedores.REGISTRO:
        proveedores.registrar(NOMBRE, construir)


registrar()
