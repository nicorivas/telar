"""El estado derivado: lo que telar sabe de un hilo y el multiplexor no.

El multiplexor sabe qué tabs hay, cómo se llaman y cuál tiene el foco. Todo lo
demás —a qué carpeta está vinculado un hilo, qué prioridad le puso el usuario, si
está archivado, en qué anda su agente, cuánto tiempo estuvo arriba— lo guarda
telar aquí, fuera del repositorio de trabajo.

Es **derivado y desechable**: borrar esta carpeta pierde los vínculos y el tiempo
medido, no el trabajo. Por eso vive en `~/.local/state/telar` (o donde diga
`estado` en la configuración) y nunca dentro de `raiz`.

Cada cosa en su archivo, casi todos JSON de una sola forma (`hilo` → valor):

    vinculos.json     hilo → carpeta, relativa a la raíz del repositorio
    prioridades.json  hilo → 1, 2 o 3
    archivados.json   lista de hilos archivados
    atencion.json     hilo → {"atencion": …, "desde": ISO}
    sesiones.json     hilo → [id de conversación, …], la principal primero
    paneles.json      panel del multiplexor → conversación que corre ahí ahora
    orden             una palabra: cómo se ordena la lista de hilos
    foco.log          una línea `ISO<TAB>hilo` por cambio de foco

La llave de todo es el **nombre** del hilo, no su `id`. El `id` es posicional en
tmux —abrir un tab al principio corre todos los índices— y el nombre es lo que el
usuario puso y reconoce. El precio es que renombrar hay que acompañarlo, y de eso
se encarga `Estado.renombrar()`.

Ese precio se paga de verdad cuando el nombre lo cambia **otro**: un `prefix + ,` en
el multiplexor y el estado queda colgado del nombre viejo, que ya no es ningún tab.
Dos cosas lo hacen recuperable, y las dos viven fuera de aquí: `repartir()` separa lo
que el multiplexor muestra ahora de lo que telar solo recuerda —para que un nombre
huérfano no se cuente como hilo abierto— y `telar hilo adoptar` le devuelve ese
estado al tab que sí está, con `Estado.renombrar(…, fusionar=True)`.

Escribir es leer-modificar-escribir bajo candado: varias instancias del agente
escriben estos archivos a la vez, y sin candado la última pisa a todas. Hay
operaciones que tocan tres archivos y tienen que verse como una (`anotar`,
`renombrar`, `olvidar`): esas toman además el candado de la carpeta entera, que
siempre se pide ANTES que el de un archivo, nunca después.

El cálculo —recortar intervalos, sumar tiempo, ordenar, vestir un hilo con lo que
el estado sabe de él— son funciones puras de este módulo: reciben lo ya leído y
devuelven datos nuevos. Se prueban sin tocar disco, y quien dibuja las usa sin
volver a leer.

Los avisos del reloj: las horas se guardan en hora local ingenua (es el registro de
uso de una máquina, no un dato que viaje), y nadie avisa «me fui del computador»,
así que un intervalo sin cambio de foco se recorta a `intervalos.foco_maximo`.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Container, Iterable, Iterator, Mapping, Sequence
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from telar.config import Config
from telar.modelo import Atencion, Hilo, Marca, Prioridad

__all__ = [
    "Estado",
    "ErrorDeEstado",
    "Orden",
    "abrir",
    "ARCHIVOS",
    "FOCO",
    "ORDEN",
    "CANDADO",
    "marcas_desde",
    "intervalos_de",
    "tiempo_por_hilo",
    "tiempo_por_dia",
    "ultimo_foco",
    "agrupar",
    "vestir",
    "ordenar",
    "partir",
    "repartir",
]

#: Los archivos JSON del estado, por lo que guardan.
ARCHIVOS = {
    "vinculos": "vinculos.json",
    "prioridades": "prioridades.json",
    "archivados": "archivados.json",
    "atencion": "atencion.json",
    "sesiones": "sesiones.json",
    "paneles": "paneles.json",
    "ids": "ids.json",
}

#: El registro de cambios de foco, que no es JSON sino un log que solo crece.
FOCO = "foco.log"

#: El criterio de orden: una palabra suelta, para que se pueda cambiar con `echo`.
ORDEN = "orden"

#: El candado de la carpeta entera, para lo que toca varios archivos a la vez.
CANDADO = ".candado"


class ErrorDeEstado(Exception):
    """No se pudo leer o escribir el estado (permisos, disco, JSON roto)."""


class Orden(str, Enum):
    """Cómo se ordena la lista de hilos. Es una preferencia, no un dato del mundo."""

    #: el orden que reporta el multiplexor (creación); no se toca nada
    MUX = "mux"
    ALFA = "alfa"
    #: última vez que el hilo tuvo el foco, lo más reciente arriba
    RECIENTE = "reciente"
    #: 1 alta … 3 baja; sin prioridad, al final
    PRIORIDAD = "prioridad"


def _candado(ruta: Path):
    """Un candado exclusivo sobre `ruta`, o nada donde no haya `fcntl`.

    Sin `fcntl` (Windows) se sigue igual: el riesgo es perder una escritura
    simultánea, no corromper nada, porque el archivo se reemplaza entero.
    """
    try:
        import fcntl
    except ModuleNotFoundError:  # pragma: no cover - depende del sistema
        from contextlib import nullcontext

        return nullcontext()

    class _Candado:
        def __enter__(self):
            ruta.parent.mkdir(parents=True, exist_ok=True)
            self.fh = open(ruta, "w")
            fcntl.flock(self.fh, fcntl.LOCK_EX)
            return self

        def __exit__(self, *_):
            fcntl.flock(self.fh, fcntl.LOCK_UN)
            self.fh.close()
            return False

    return _Candado()


# ── Funciones puras ───────────────────────────────────────────────────────────
# De aquí hasta `Estado` no se toca el disco: entran datos, salen datos. Es todo el
# cálculo del módulo, y es lo que se puede probar con datos inventados.


def marcas_desde(lineas: Iterable[str]) -> list[Marca]:
    """Parsea líneas `ISO<TAB>hilo` a marcas, ordenadas por hora.

    Una línea que no se entiende se salta: el registro solo crece, y una escritura
    a medias no debe invalidar los diez días anteriores.
    """
    salida: list[Marca] = []
    for linea in lineas:
        cuando, tabulador, hilo = linea.rstrip("\n").partition("\t")
        if not tabulador or not hilo:
            continue
        fecha = _fecha(cuando)
        if fecha is not None:
            salida.append(Marca(cuando=fecha, hilo=hilo))
    salida.sort(key=lambda m: m.cuando)
    return salida


def intervalos_de(
    marcas: Sequence[Marca], tope: float, *, ahora: datetime | None = None
) -> Iterator[tuple[datetime, str, float]]:
    """(inicio, hilo, segundos) por cada intervalo entre marcas, ya recortado a `tope`.

    Una marca abre un intervalo que cierra la siguiente; la última cierra en
    `ahora`. El recorte es lo que compensa que nadie avise cuando se va: sin él,
    salir a almorzar le regala dos horas al hilo que quedó arriba.
    """
    if tope <= 0:
        raise ValueError(f"el tope tiene que ser positivo, llegó {tope!r}")
    fin_ultimo = ahora or datetime.now()
    for i, marca in enumerate(marcas):
        fin = marcas[i + 1].cuando if i + 1 < len(marcas) else fin_ultimo
        segundos = min((fin - marca.cuando).total_seconds(), tope)
        if segundos > 0:
            yield marca.cuando, marca.hilo, segundos


def tiempo_por_hilo(
    marcas: Sequence[Marca],
    tope: float,
    *,
    desde: date | None = None,
    hasta: date | None = None,
    ahora: datetime | None = None,
) -> dict[str, float]:
    """Segundos con el foco por hilo, entre dos fechas inclusive, de mayor a menor.

    Un intervalo cuenta entero en el día en que EMPEZÓ. Cruzar la medianoche es raro
    y partirlo costaría más de lo que aclara.
    """
    total: dict[str, float] = defaultdict(float)
    for inicio, hilo, segundos in intervalos_de(marcas, tope, ahora=ahora):
        dia = inicio.date()
        if (desde and dia < desde) or (hasta and dia > hasta):
            continue
        total[hilo] += segundos
    return dict(sorted(total.items(), key=lambda kv: -kv[1]))


def tiempo_por_dia(
    marcas: Sequence[Marca],
    tope: float,
    *,
    desde: date | None = None,
    hasta: date | None = None,
    ahora: datetime | None = None,
) -> dict[date, dict[str, float]]:
    """Lo mismo que `tiempo_por_hilo`, abierto por día."""
    total: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for inicio, hilo, segundos in intervalos_de(marcas, tope, ahora=ahora):
        dia = inicio.date()
        if (desde and dia < desde) or (hasta and dia > hasta):
            continue
        total[dia][hilo] += segundos
    return {d: dict(v) for d, v in sorted(total.items())}


def ultimo_foco(marcas: Sequence[Marca]) -> dict[str, datetime]:
    """Última vez que cada hilo tuvo el foco."""
    visto: dict[str, datetime] = {}
    for marca in marcas:
        if marca.cuando >= visto.get(marca.hilo, marca.cuando):
            visto[marca.hilo] = marca.cuando
    return visto


def agrupar(tiempos: Mapping[str, float], vinculos: Mapping[str, str]) -> dict[str, float]:
    """Suma el tiempo de los hilos que apuntan a la misma carpeta.

    Dos hilos abiertos sobre el mismo proyecto son un proyecto. Lo que no está
    vinculado queda con su propio nombre, que es todo lo que se sabe de él.
    """
    total: dict[str, float] = defaultdict(float)
    for hilo, segundos in tiempos.items():
        total[vinculos.get(hilo) or hilo] += segundos
    return dict(sorted(total.items(), key=lambda kv: -kv[1]))


def vestir(
    hilos: Iterable[Hilo],
    *,
    raiz: Path | None = None,
    vinculos: Mapping[str, str] | None = None,
    prioridades: Mapping[str, Prioridad] | None = None,
    archivados: Iterable[str] = (),
    atenciones: Mapping[str, Atencion] | None = None,
    sesiones: Mapping[str, Sequence[str]] | None = None,
    tiempos: Mapping[str, float] | None = None,
    vistos: Mapping[str, datetime] | None = None,
) -> tuple[Hilo, ...]:
    """Le pone a cada hilo del multiplexor lo que el estado sabe de él.

    El multiplexor devuelve `Hilo` con lo suyo (id, nombre, activo, el cwd del
    panel); aquí se le agrega el vínculo, la prioridad, el archivo, la atención, las
    conversaciones, el tiempo y el último foco. El vínculo del estado gana sobre el
    cwd del panel: el cwd es dónde quedó una shell, el vínculo es lo que el usuario
    decidió. Lo que no está en el estado se deja como venía.
    """
    vinculos = vinculos or {}
    archivados = set(archivados)
    vestidos: list[Hilo] = []
    for hilo in hilos:
        nombre = hilo.nombre
        crudo = vinculos.get(nombre, "")
        ruta = Path(crudo).expanduser() if crudo else None
        if ruta is not None and raiz is not None and not ruta.is_absolute():
            ruta = Path(raiz) / ruta
        vestidos.append(
            Hilo(
                id=hilo.id,
                nombre=nombre,
                ruta=ruta or hilo.ruta,
                vinculo=ruta,
                arquetipo=hilo.arquetipo,
                activo=hilo.activo,
                archivado=nombre in archivados,
                prioridad=(prioridades or {}).get(nombre, hilo.prioridad),
                atencion=(atenciones or {}).get(nombre, hilo.atencion),
                visto=(vistos or {}).get(nombre, hilo.visto),
                tiempo=(tiempos or {}).get(nombre, hilo.tiempo),
                ficha=hilo.ficha,
                sesiones=tuple((sesiones or {}).get(nombre, hilo.sesiones)),
            )
        )
    return tuple(vestidos)


def ordenar(hilos: Iterable[Hilo], criterio: Orden | str = Orden.MUX) -> tuple[Hilo, ...]:
    """Ordena los hilos por un criterio. El del multiplexor se deja como viene."""
    criterio = Orden(criterio)
    lista = list(hilos)
    if criterio is Orden.MUX:
        return tuple(lista)
    if criterio is Orden.ALFA:
        return tuple(sorted(lista, key=lambda h: h.nombre.casefold()))
    if criterio is Orden.RECIENTE:
        # sin foco registrado, al final: no es «hace mucho», es «no se sabe»
        return tuple(sorted(lista, key=lambda h: (h.visto or datetime.min), reverse=True))
    ultima = max(p.value for p in Prioridad) + 1
    return tuple(
        sorted(
            lista,
            key=lambda h: (h.prioridad.value if h.prioridad else ultima, h.nombre.casefold()),
        )
    )


def partir(hilos: Iterable[Hilo]) -> tuple[tuple[Hilo, ...], tuple[Hilo, ...]]:
    """Separa los hilos que están en la lista de los archivados, sin reordenar.

    Separa por lo que el usuario decidió (`archivado`), que **no** es lo mismo que
    estar abierto: quien tenga a mano lo que el multiplexor muestra ahora quiere
    `repartir`, que distingue las tres cosas.
    """
    lista = list(hilos)
    return (
        tuple(h for h in lista if not h.archivado),
        tuple(h for h in lista if h.archivado),
    )


def repartir(
    hilos: Iterable[Hilo], vivos: Container[str]
) -> tuple[tuple[Hilo, ...], tuple[Hilo, ...], tuple[Hilo, ...]]:
    """Separa en (abiertos, sin ventana, archivados), sin reordenar ninguno.

    `vivos` son los nombres que el multiplexor muestra **ahora**. Un hilo archivado
    va al cajón aunque su tab siga abierto: archivarlo fue una decisión. De los
    demás, los que el multiplexor no muestra quedan aparte, y ese aparte es la
    diferencia que importa: telar recuerda hilos que no tienen ventana —archivados,
    de una sesión que todavía no se levanta, o un nombre que quedó huérfano porque
    el tab se renombró desde el multiplexor— y contarlos entre los abiertos anuncia
    cuatro hilos con tres ventanas.
    """
    lista = list(hilos)
    return (
        tuple(h for h in lista if not h.archivado and h.nombre in vivos),
        tuple(h for h in lista if not h.archivado and h.nombre not in vivos),
        tuple(h for h in lista if h.archivado),
    )


class Estado:
    """El estado de una carpeta. Construirlo no toca el disco."""

    __slots__ = ("carpeta",)

    def __init__(self, carpeta: Path | str) -> None:
        self.carpeta = Path(carpeta).expanduser()

    def __repr__(self) -> str:  # pragma: no cover
        return f"Estado({str(self.carpeta)!r})"

    # ── el disco, en un solo lugar ──────────────────────────────────────────────

    def ruta(self, nombre: str) -> Path:
        return self.carpeta / ARCHIVOS.get(nombre, nombre)

    @property
    def existe(self) -> bool:
        return self.carpeta.is_dir()

    def preparar(self) -> Path:
        """Crea la carpeta de estado si falta. Devuelve la carpeta."""
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ErrorDeEstado(f"no pude crear {self.carpeta}: {e}") from e
        return self.carpeta

    def _leer(self, nombre: str, defecto):
        ruta = self.ruta(nombre)
        if not ruta.exists():
            return defecto
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8") or "null")
        except json.JSONDecodeError as e:
            raise ErrorDeEstado(f"{ruta}: JSON roto ({e}). Bórralo: es derivado.") from e
        except OSError as e:
            raise ErrorDeEstado(f"{ruta}: no se pudo leer: {e}") from e
        if datos is None or type(datos) is not type(defecto):
            return defecto
        return datos

    def _escribir(self, nombre: str, datos) -> None:
        ruta = self.ruta(nombre)
        self.preparar()
        texto = json.dumps(datos, ensure_ascii=False, indent=2) + "\n"
        try:
            # a un temporal y luego `replace`: nadie lee un archivo a medio escribir
            fd, tmp = tempfile.mkstemp(dir=str(ruta.parent), prefix=ruta.name, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(texto)
            os.replace(tmp, ruta)
        except OSError as e:
            raise ErrorDeEstado(f"{ruta}: no se pudo escribir: {e}") from e

    def _actualizar(self, nombre: str, cambio, defecto):
        """Leer-modificar-escribir bajo candado. `cambio(d)` muta `d` y no devuelve nada."""
        self.preparar()
        with _candado(self.ruta(nombre).with_suffix(".lock")):
            datos = self._leer(nombre, defecto)
            cambio(datos)
            self._escribir(nombre, datos)
        return datos

    def bajo_candado(self):
        """Candado de la carpeta entera, para lo que toca varios archivos a la vez.

        Se pide SIEMPRE antes que el de un archivo y nunca después: con ese orden,
        anidarlo con `_actualizar` no se traba. Sin esto, `renombrar` se podía
        quedar a medio camino y dejar el vínculo con un nombre y la prioridad con
        el otro.
        """
        self.preparar()
        return _candado(self.carpeta / CANDADO)

    # ── vínculos: hilo → carpeta del repositorio ───────────────────────────────

    def vinculos(self) -> dict[str, str]:
        """hilo → ruta relativa a la raíz. Las claves con `_` delante se ignoran."""
        d = self._leer("vinculos", {})
        return {k: str(v) for k, v in d.items() if not k.startswith("_") and isinstance(v, str)}

    def vinculo(self, hilo: str) -> str:
        return self.vinculos().get(hilo, "")

    def vincular(self, hilo: str, ruta: str) -> None:
        # una ruta absoluta (fuera de la raíz) conserva su «/» inicial: sin ella se
        # leería como relativa a la raíz y apuntaría a otra parte
        crudo = str(ruta).strip()
        limpia = "/" + crudo.strip("/") if crudo.startswith("/") else crudo.strip("/")
        self._actualizar("vinculos", lambda d: d.__setitem__(hilo, limpia), {})

    def desvincular(self, hilo: str) -> None:
        self._actualizar("vinculos", lambda d: d.pop(hilo, None), {})

    # ── prioridad manual ───────────────────────────────────────────────────────

    def prioridades(self) -> dict[str, Prioridad]:
        salida: dict[str, Prioridad] = {}
        for hilo, valor in self._leer("prioridades", {}).items():
            try:
                salida[hilo] = Prioridad(int(valor))
            except (ValueError, TypeError):
                continue
        return salida

    def prioridad(self, hilo: str, valor: Prioridad | int | None) -> None:
        """Pone o quita la prioridad de un hilo. `None` la quita: el hilo va al final."""
        if valor is None:
            self._actualizar("prioridades", lambda d: d.pop(hilo, None), {})
            return
        p = Prioridad(int(valor))
        self._actualizar("prioridades", lambda d: d.__setitem__(hilo, int(p)), {})

    # ── archivados ─────────────────────────────────────────────────────────────

    def archivados(self) -> set[str]:
        return {h for h in self._leer("archivados", []) if isinstance(h, str)}

    def archivar(self, hilo: str) -> None:
        def cambio(lista):
            if hilo not in lista:
                lista.append(hilo)

        self._actualizar("archivados", cambio, [])

    def desarchivar(self, hilo: str) -> None:
        def cambio(lista):
            while hilo in lista:
                lista.remove(hilo)

        self._actualizar("archivados", cambio, [])

    # ── atención: el contrato con el agente ────────────────────────────────────

    def atenciones(self) -> dict[str, tuple[Atencion, datetime | None]]:
        salida: dict[str, tuple[Atencion, datetime | None]] = {}
        for hilo, cuerpo in self._leer("atencion", {}).items():
            if not isinstance(cuerpo, dict):
                continue
            try:
                atencion = Atencion(cuerpo.get("atencion", "ninguna"))
            except ValueError:
                atencion = Atencion.NINGUNA
            salida[hilo] = (atencion, _fecha(cuerpo.get("desde")))
        return salida

    def atencion(self, hilo: str) -> Atencion:
        return self.atenciones().get(hilo, (Atencion.NINGUNA, None))[0]

    def anotar_atencion(self, hilo: str, atencion: Atencion, cuando: datetime | None = None) -> None:
        """Deja dicho en qué anda el agente de un hilo. `ninguna` borra la anotación."""
        marca = (cuando or datetime.now()).isoformat(timespec="seconds")
        if atencion == Atencion.NINGUNA:
            self._actualizar("atencion", lambda d: d.pop(hilo, None), {})
            return
        cuerpo = {"atencion": atencion.value, "desde": marca}
        self._actualizar("atencion", lambda d: d.__setitem__(hilo, cuerpo), {})

    # ── sesiones de agente, y en qué panel corre cada una ──────────────────────

    def sesiones(self) -> dict[str, tuple[str, ...]]:
        """hilo → conversaciones, la principal primero. Acepta `"x"` y `["x", …]`."""
        salida: dict[str, tuple[str, ...]] = {}
        for hilo, valor in self._leer("sesiones", {}).items():
            if hilo.startswith("_"):
                continue
            ids = _ids(valor)
            if ids:
                salida[hilo] = ids
        return salida

    def hilo_de(self, sesion: str) -> str:
        """En qué hilo vive una conversación. Vacío si no está anotada.

        Lo usa quien recibe un aviso del agente y solo conoce el id de la sesión.
        """
        for hilo, ids in self.sesiones().items():
            if sesion in ids:
                return hilo
        return ""

    def paneles(self) -> dict[str, str]:
        """panel del multiplexor → conversación que corre ahí ahora.

        Un panel corre una conversación a la vez. Este mapa es lo único que permite
        darse cuenta de que la de antes se fue (un `/clear`, o salir y abrir otra):
        sin él, un hilo acumula conversaciones muertas y `retomar` abre la
        equivocada.
        """
        return {
            str(panel): str(sesion)
            for panel, sesion in self._leer("paneles", {}).items()
            if not str(panel).startswith("_") and sesion
        }

    def anotar_sesion(
        self,
        hilo: str,
        sesion: str,
        *,
        panel: str = "",
        principal: bool = True,
        revivir: bool = True,
    ) -> tuple[str, ...]:
        """Anota que una conversación vive en un hilo. Devuelve las del hilo.

        Se llama cuando el agente arranca, no cuando se necesita. Tres reglas, que
        son las que hacen que el mapa no mienta:

        1. una conversación vive en UN hilo: entra aquí y sale de donde estuviera;
        2. un panel corre UNA conversación: la que corría antes en este panel, si no
           quedó viva en otro, sale de su hilo (para eso está `paneles.json`);
        3. `revivir`: si el hilo estaba archivado, que su agente vuelva lo desarchiva.

        Sin `panel` se aplican la 1 y la 3: es lo que se puede saber sin él.
        """
        if not sesion:
            raise ErrorDeEstado("anotar_sesion: hace falta el id de la conversación")
        with self.bajo_candado():
            paneles = self.paneles()
            previa = paneles.get(panel) if panel else ""
            # ¿la de antes quedó viva en otro panel? si no, ya no está en ninguna parte
            huerfana = bool(previa) and previa != sesion and not any(
                s == previa for p, s in paneles.items() if p != panel
            )
            fuera = {sesion} | ({previa} if huerfana else set())

            def cambio(d):
                # primero sale de todas partes (de aquí también), después entra aquí
                for donde in list(d):
                    if donde.startswith("_"):
                        continue
                    ids = [i for i in _ids(d[donde]) if i not in fuera]
                    if ids:
                        d[donde] = ids
                    else:
                        d.pop(donde)
                aqui = list(d.get(hilo) or [])
                d[hilo] = [sesion] + aqui if principal else aqui + [sesion]

            quedan = self._actualizar("sesiones", cambio, {})

            if panel:

                def cambio_panel(d):
                    # esta conversación corre aquí y en ningún otro panel
                    for otro in [p for p, s in list(d.items()) if s == sesion and p != panel]:
                        d.pop(otro)
                    d[panel] = sesion

                self._actualizar("paneles", cambio_panel, {})

            if revivir:
                self.desarchivar(hilo)
        return _ids(quedan.get(hilo))

    def olvidar_sesion(self, sesion: str) -> None:
        """Saca una conversación de todos lados. Se llama cuando la sesión termina."""
        with self.bajo_candado():

            def cambio(d):
                for hilo in list(d):
                    if hilo.startswith("_"):
                        continue
                    ids = [i for i in _ids(d[hilo]) if i != sesion]
                    if ids:
                        d[hilo] = ids
                    else:
                        d.pop(hilo)

            self._actualizar("sesiones", cambio, {})

            def cambio_panel(d):
                for panel in [p for p, s in list(d.items()) if s == sesion]:
                    d.pop(panel)

            self._actualizar("paneles", cambio_panel, {})

    # ── foco y tiempo ──────────────────────────────────────────────────────────

    def ultima_marca(self) -> Marca | None:
        """La última línea del registro. (Para «cuándo tuvo el foco cada hilo», la
        función pura `ultimo_foco(marcas)`.)"""
        marcas = self.marcas()
        return marcas[-1] if marcas else None

    def marcar(self, hilo: str, cuando: datetime | None = None) -> bool:
        """Anota que el foco pasó a `hilo`. Devuelve si hubo cambio que anotar.

        Se llama todo el tiempo (una barra, un gancho del multiplexor): anotar el
        mismo hilo dos veces seguidas solo engorda el log sin decir nada nuevo, y le
        quitaría el recorte de encima al intervalo que ya estaba abierto.
        """
        ultimo = self.ultima_marca()
        if ultimo is not None and ultimo.hilo == hilo:
            return False
        self.preparar()
        linea = f"{(cuando or datetime.now()).isoformat(timespec='seconds')}\t{hilo}\n"
        try:
            with open(self.ruta(FOCO), "a", encoding="utf-8") as fh:
                fh.write(linea)
        except OSError as e:
            raise ErrorDeEstado(f"{self.ruta(FOCO)}: no se pudo escribir: {e}") from e
        return True

    def marcas(self) -> list[Marca]:
        """Todo el registro de foco, parseado. El cálculo es de las funciones puras."""
        ruta = self.ruta(FOCO)
        if not ruta.exists():
            return []
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise ErrorDeEstado(f"{ruta}: no se pudo leer: {e}") from e
        return marcas_desde(texto.splitlines())

    def intervalos(self, tope: float, *, ahora: datetime | None = None):
        """(inicio, hilo, segundos) por cada intervalo entre marcas, ya recortado.

        Nadie avisa «me fui del computador»: un intervalo sin cambio de foco se
        recorta a `tope` segundos. Sin eso, salir a almorzar le regala dos horas al
        hilo que quedó arriba. El tope sale de `intervalos.foco_maximo`.
        """
        return intervalos_de(self.marcas(), tope, ahora=ahora)

    def tiempos(
        self,
        desde: date,
        hasta: date,
        tope: float,
        *,
        ahora: datetime | None = None,
    ) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
        """Segundos por hilo y por día, entre dos fechas inclusive."""
        marcas = self.marcas()
        por_hilo = tiempo_por_hilo(marcas, tope, desde=desde, hasta=hasta, ahora=ahora)
        por_dia = tiempo_por_dia(marcas, tope, desde=desde, hasta=hasta, ahora=ahora)
        return por_hilo, {d.isoformat(): v for d, v in por_dia.items()}

    def hoy(self, tope: float, *, dia: date | None = None) -> dict[str, float]:
        dia = dia or date.today()
        return self.tiempos(dia, dia, tope)[0]

    def vistos(self) -> dict[str, datetime]:
        """Última vez que cada hilo tuvo el foco."""
        return ultimo_foco(self.marcas())

    # ── el orden de la lista ───────────────────────────────────────────────────

    def orden(self) -> Orden:
        """El criterio elegido. Sin archivo, o con una palabra que no se entiende, el
        del multiplexor: un archivo raro no es motivo para no dibujar la lista."""
        ruta = self.carpeta / ORDEN
        try:
            crudo = ruta.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return Orden.MUX
        except OSError as e:
            raise ErrorDeEstado(f"{ruta}: no se pudo leer: {e}") from e
        try:
            return Orden(crudo)
        except ValueError:
            return Orden.MUX

    def ordenar_por(self, criterio: Orden | str) -> Orden:
        """Deja escrito el criterio. Es una palabra suelta a propósito: se cambia con
        `echo alfa > orden` y quien dibuja lo relee al instante."""
        elegido = Orden(criterio)
        self.preparar()
        ruta = self.carpeta / ORDEN
        with _candado(ruta.with_suffix(".lock")):
            try:
                ruta.write_text(elegido.value + "\n", encoding="utf-8")
            except OSError as e:
                raise ErrorDeEstado(f"{ruta}: no se pudo escribir: {e}") from e
        return elegido

    # ── todo de una vez ────────────────────────────────────────────────────────

    def foto(self, *, tope: float, dia: date | None = None) -> dict[str, object]:
        """Todo el estado leído de una vez, listo para `vestir(hilos, **foto)`.

        Leído de una vez y bajo candado para que nadie dibuje media lista de antes y
        media de después. Lo que sale de aquí ya no toca el disco.
        """
        with self.bajo_candado():
            marcas = self.marcas()
            return {
                "vinculos": self.vinculos(),
                "prioridades": self.prioridades(),
                "archivados": self.archivados(),
                "atenciones": {h: a for h, (a, _) in self.atenciones().items()},
                "sesiones": self.sesiones(),
                "tiempos": tiempo_por_hilo(
                    marcas, tope, desde=dia or date.today(), hasta=dia or date.today()
                ),
                "vistos": ultimo_foco(marcas),
            }

    # ── renombrar y olvidar ────────────────────────────────────────────────────

    def ids(self) -> dict[str, str]:
        """id del multiplexor → nombre que tenía la última vez que se lo vio.

        `_huella` no es un id: identifica la encarnación de la sesión (ver `reconciliar`).
        """
        return {
            k: str(v)
            for k, v in self._leer("ids", {}).items()
            if isinstance(v, str) and k != "_huella"
        }

    def reconciliar(self, hilos: Iterable[Hilo], huella: str = "") -> list[tuple[str, str]]:
        """Sigue los renombres del multiplexor para que el estado no se quede huérfano.

        El estado se guarda por NOMBRE, que es lo único que sobrevive a cerrar la sesión;
        pero el nombre lo cambia cualquiera con dos teclas (`prefix ,` en tmux), y entonces
        el vínculo, la prioridad y la atención se quedaban colgando del nombre viejo, que
        además aparecía como un hilo fantasma. El id del multiplexor (`@3` en tmux, el id
        del tab en zellij) sí es estable mientras la sesión vive: recordarlo permite ver el
        renombre y mover el estado detrás. Devuelve los cambios que hizo.
        """
        vistos = {h.id: h.nombre for h in hilos if h.id and h.nombre and h.id != h.nombre}
        if not vistos:
            return []
        guardado = self._leer("ids", {})
        antes = {k: str(v) for k, v in guardado.items() if isinstance(v, str) and k != "_huella"}
        anterior = guardado.get("_huella", "")
        if huella and anterior and huella != anterior:
            # otra encarnación de la sesión: los ids se reciclaron y no dicen nada.
            # Sin esto, el @0 de la sesión de hoy se leía como el @0 de la de ayer y el
            # estado se mudaba a un tab que no tenía nada que ver.
            antes = {}
        cambios: list[tuple[str, str]] = []
        for ident, nombre in vistos.items():
            viejo = antes.get(ident)
            if viejo and viejo != nombre and self.conoce(viejo):
                self.renombrar(viejo, nombre, fusionar=True)
                cambios.append((viejo, nombre))
        nuevo = {**antes, **vistos}
        if huella:
            nuevo["_huella"] = huella
        if nuevo != guardado:
            self._escribir("ids", nuevo)
        return cambios

    def conoce(self, hilo: str) -> bool:
        """¿El estado guarda algo de este hilo? (vínculo, prioridad, archivo o atención)"""
        return (
            hilo in self.vinculos()
            or hilo in self.prioridades()
            or hilo in self.archivados()
            or hilo in self.atenciones()
            or bool(self.sesiones().get(hilo))
        )

    def renombrar(self, viejo: str, nuevo: str, *, fusionar: bool = False) -> None:
        """Mueve todo lo que sabe de `viejo` a `nuevo`.

        El registro de foco NO se reescribe: es historia, y reescribir historia para
        que cuadre un total es peor que un total repartido en dos nombres. El tiempo
        anterior al cambio queda con el nombre anterior, y `telar tiempo` lo muestra
        así.
        """
        if viejo == nuevo:
            return
        if not nuevo:
            raise ErrorDeEstado("renombrar: el nombre nuevo no puede ser vacío")

        def mover(d):
            if viejo not in d:
                return
            valor = d.pop(viejo)
            if nuevo not in d or not fusionar:
                d[nuevo] = valor

        def mover_sesiones(d):
            if viejo not in d:
                return
            valor = list(_ids(d.pop(viejo)))
            actuales = list(_ids(d.get(nuevo)))
            d[nuevo] = actuales + [s for s in valor if s not in actuales] if fusionar else valor

        def mover_archivados(lista):
            if viejo not in lista:
                return
            while viejo in lista:
                lista.remove(viejo)
            if nuevo not in lista:
                lista.append(nuevo)

        # los cinco archivos de una sola vez: a medio camino, el hilo tendría el
        # vínculo con un nombre y la prioridad con el otro. `paneles.json` no se toca:
        # está indexado por panel, no por hilo, así que un renombre no lo alcanza.
        with self.bajo_candado():
            for nombre in ("vinculos", "prioridades", "atencion"):
                self._actualizar(nombre, mover, {})
            self._actualizar("sesiones", mover_sesiones, {})
            self._actualizar("archivados", mover_archivados, [])

    def olvidar(self, hilo: str) -> None:
        """Borra todo lo que telar sabía de un hilo, menos el registro de foco.

        El tiempo que se trabajó ahí ya se trabajó: un informe de la semana pasada no
        debería cambiar porque se cerró un tab.
        """
        with self.bajo_candado():
            for nombre in ("vinculos", "prioridades", "atencion", "sesiones"):
                self._actualizar(nombre, lambda d: d.pop(hilo, None), {})
            self.desarchivar(hilo)


def _fecha(valor: object) -> datetime | None:
    if not isinstance(valor, str) or not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


def _ids(valor: object) -> tuple[str, ...]:
    """Acepta `"x"` y `["x", "y"]`, devuelve siempre una tupla. Se escribe lista."""
    if isinstance(valor, str):
        return (valor,) if valor else ()
    if isinstance(valor, (list, tuple)):
        return tuple(str(v) for v in valor if v)
    return ()


def abrir(config: Config) -> Estado:
    """El estado que declara la configuración. No toca el disco hasta que se escribe."""
    return Estado(config.estado)
