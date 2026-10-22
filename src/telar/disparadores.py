"""Disparadores: lo que corre un comando o manda un mensaje solo, por un reloj, una tecla o un cambio.

Se declaran en la configuración, uno por tabla (docs/propuestas/disparadores.md):

    [disparadores.resumen]             # un reloj: lo de periodicos.toml
    cuando = "30 8 * * 1-5"
    comando = "~/bin/resumen --corto"

    [disparadores.correo]              # una tecla del dashboard: lo de [atajos]
    tecla = "m"
    mensaje = "/correo"
    hilo = "⚑ correo"                  # el nombre del hilo (en [atajos], `nombre`)
    aparece = "correo"                 # dónde se muestra la tecla (en [atajos], `en`)

    [disparadores.tablero]             # al cambiar: cuando alguna máquina anuncia `telar cambio tareas`
    al = "cambio:tareas"
    comando = "~/bin/tablero --rehacer"

El reloj y la tecla se traducen al leer a lo de hoy, que se sigue leyendo: un reloj es un proceso más de
`telar periodicos` (`telar.periodicos.completo`), y una tecla, un `[atajos.<tecla>]` (`telar.config`). El
cambio lo despacha el nodo de la máquina donde corren los periódicos (`Despacho`): cuando llega su tema,
corre igual que un periódico (`telar.periodicos.correr`), con freno para las ráfagas y para el que se
dispara a sí mismo.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

#: el nombre va en el crontab y en `<estado>/periodicos/<nombre>.json`, como el de un periódico
NOMBRE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
#: un tema de `telar cambio` (telar.ordenes.cambio)
TEMA = re.compile(r"^[a-z0-9-]{1,40}$")
#: las tres maneras de decir cuándo, y la que dice cada una
CUANDO = {"cuando": "reloj", "tecla": "tecla", "al": "cambio"}
#: lo que acepta cada una, además de su clave de cuándo
_CLAVES = {
    "reloj": {"comando", "mensaje", "agente", "hilo", "max_abiertos", "argumentos", "carpeta", "descripcion", "activo"},
    "cambio": {"comando", "mensaje", "agente", "hilo", "max_abiertos", "argumentos", "carpeta", "descripcion", "activo"},
    "tecla": {"mensaje", "agente", "hilo", "descripcion", "aparece", "activo"},
}

#: el freno de «al cambiar» (docs/propuestas/disparadores.md, «El freno»): segundos entre dos corridas del
#: mismo disparador, cuántas puede haber en una hora y cuántos corren a la vez en todo el nodo
PAUSA = 30.0
TOPE_POR_HORA = 12
A_LA_VEZ = 2


@dataclass(frozen=True, slots=True)
class Disparador:
    nombre: str
    #: una de las tres, las otras vacías: el horario cron, la tecla o lo que espera («cambio:<tema>»)
    cuando: str = ""
    tecla: str = ""
    al: str = ""
    comando: str = ""
    mensaje: str = ""
    agente: str = ""
    hilo: str = ""
    max_abiertos: int = 1
    argumentos: tuple[str, ...] = ()
    carpeta: str = ""
    descripcion: str = ""
    #: solo la tecla: dónde se muestra («hoy», la clave de una vista o «seccion:<clave>»)
    aparece: str = ""
    activo: bool = True

    @property
    def tipo(self) -> str:
        return "reloj" if self.cuando else "tecla" if self.tecla else "cambio"

    @property
    def tema(self) -> str:
        """El tema de `telar cambio` que espera uno de cambio; "" los demás."""
        return self.al.split(":", 1)[1] if self.al.startswith("cambio:") else ""

    def proceso(self):
        """El de reloj o el de cambio como un proceso de `telar periodicos`: así corre y anota igual."""
        from telar.periodicos import Proceso

        return Proceso(nombre=self.nombre, cuando=self.cuando, comando=self.comando, mensaje=self.mensaje,
                       agente=self.agente, hilo=self.hilo, max_abiertos=self.max_abiertos,
                       argumentos=self.argumentos, carpeta=self.carpeta, descripcion=self.descripcion,
                       activo=self.activo, disparador=True)

    def atajo(self) -> dict:
        """El de tecla como el `[atajos.<tecla>]` que da lo mismo, para la validación de siempre."""
        cuerpo = {"nombre": self.hilo or self.nombre, "mensaje": self.mensaje}
        for clave, valor in (("descripcion", self.descripcion), ("agente", self.agente), ("en", self.aparece)):
            if valor:
                cuerpo[clave] = valor
        return cuerpo


def _error(texto: str):
    from telar.config import ErrorDeConfig

    return ErrorDeConfig(texto)


def uno(nombre: str, cuerpo: object) -> Disparador:
    """Un `[disparadores.x]`, validado. Los errores nombran el disparador (`disparadores.x.cuando: …`)."""
    donde = f"disparadores.{nombre}"
    if not isinstance(cuerpo, dict):
        raise _error(f"{donde}: se esperaba una tabla, llegó {cuerpo!r}")
    if not NOMBRE.match(nombre):
        raise _error(f"{donde}: el nombre va en minúsculas, con letras, números, - y _ (va en el crontab)")
    cuales = [c for c in CUANDO if c in cuerpo]
    if len(cuales) != 1:
        dice = f"llegaron {' y '.join(cuales)}" if cuales else "falta"
        raise _error(f"{donde}: cuándo, una sola de cuando (un horario cron), tecla o al (\"cambio:<tema>\"): {dice}")
    tipo = CUANDO[cuales[0]]
    validas = _CLAVES[tipo] | {cuales[0]}
    for clave in sorted(set(cuerpo) - validas):
        todas = set().union(*_CLAVES.values()) | set(CUANDO)
        raise _error(f"{donde}.{clave}: " + (f"no va con {cuales[0]}" if clave in todas else "no existe"))
    campos: dict = {}
    for clave, valor in cuerpo.items():
        if clave == "max_abiertos":
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
                raise _error(f"{donde}.max_abiertos: un número entero desde 1, llegó {valor!r}")
        elif clave == "argumentos":
            if not isinstance(valor, list) or not all(isinstance(x, str) for x in valor):
                raise _error(f"{donde}.argumentos: se esperaba una lista de textos, llegó {valor!r}")
            valor = tuple(valor)
        elif clave == "activo":
            if not isinstance(valor, bool):
                raise _error(f"{donde}.activo: true o false, llegó {valor!r}")
        elif not isinstance(valor, str):
            raise _error(f"{donde}.{clave}: se esperaba un texto, llegó {valor!r}")
        else:
            valor = valor.strip() if clave not in ("comando", "mensaje") else valor
            if clave == "aparece" and not valor:
                raise _error(f"{donde}.aparece: «hoy», la clave de una vista o «seccion:<clave>», llegó {cuerpo[clave]!r}")
        campos[clave] = valor
    d = Disparador(nombre=nombre, **campos)
    if tipo == "reloj":
        from telar.periodicos import ErrorDePeriodicos, Horario

        try:
            Horario(d.cuando)
        except ErrorDePeriodicos as e:
            raise _error(f"{donde}.cuando: {e}") from None
    elif tipo == "tecla":
        if len(d.tecla) != 1:
            raise _error(f"{donde}.tecla: un solo carácter, llegó {d.tecla!r}")
        if not d.mensaje.strip():
            raise _error(f"{donde}: una tecla abre un hilo con un mensaje: falta mensaje")
    elif not d.tema or not TEMA.match(d.tema):
        raise _error(f"{donde}.al: \"cambio:<tema>\", con el tema de `telar cambio` (letras, números y guiones);"
                     f" llegó {d.al!r}")
    if tipo != "tecla":
        if bool(d.comando.strip()) == bool(d.mensaje.strip()):
            raise _error(f"{donde}: lleva comando o mensaje, uno de los dos")
        if d.agente and not d.mensaje.strip():
            raise _error(f"{donde}.agente: va con mensaje (lo que se le encarga)")
        if "\n" in d.comando:
            raise _error(f"{donde}.comando: va en una línea")
    return d


def leer(tabla: object) -> tuple[Disparador, ...]:
    """Los `[disparadores]` de la configuración, en el orden del archivo. Dos con la misma tecla son un error."""
    if not isinstance(tabla, dict):
        raise _error(f"disparadores: se esperaba una tabla, llegó {tabla!r}")
    salida = tuple(uno(nombre, cuerpo) for nombre, cuerpo in tabla.items())
    teclas: dict[str, str] = {}
    for d in salida:
        if d.tecla and d.activo:
            if d.tecla in teclas:
                raise _error(f"disparadores.{d.nombre}.tecla: «{d.tecla}» ya es la de disparadores.{teclas[d.tecla]}")
            teclas[d.tecla] = d.nombre
    return salida


def como_disparador(atajo) -> dict:
    """El `[disparadores.x]` que reemplaza a un `[atajos.<tecla>]` ya leído: lo que sugiere `telar doctor`."""
    d: dict = {"tecla": atajo.tecla, "mensaje": atajo.mensaje, "hilo": atajo.nombre}
    if atajo.descripcion:
        d["descripcion"] = atajo.descripcion
    if atajo.agente:
        d["agente"] = atajo.agente
    if atajo.en != "hoy":
        d["aparece"] = atajo.en
    return d


def nombre_para(atajo, ocupados) -> str:
    """Un nombre de disparador para un atajo: el de su hilo en minúsculas, sin lo que no va en el nombre."""
    import unicodedata

    base = unicodedata.normalize("NFKD", atajo.nombre).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9_-]+", "-", base).strip("-_")[:40] or f"tecla-{ord(atajo.tecla):x}"
    nombre, n = base, 2
    while nombre in ocupados:
        nombre, n = f"{base}-{n}", n + 1
    return nombre


# ── dónde corren ────────────────────────────────────────────────────────────────

def corren_aqui(config, maquina: str = "") -> bool:
    """Si los de reloj y los de cambio corren en esta máquina: la de los periódicos (`[periodicos] en`), o esta
    si no dice (docs/propuestas/disparadores.md, decisión 2)."""
    en = getattr(config, "periodicos_en", "")
    if en in ("", "aqui"):
        return True
    if not maquina:
        from telar import bus as mod_bus

        maquina = mod_bus.maquina(config)
    return en == maquina


def de_cambio(config, maquina: str = "") -> list[Disparador]:
    """Los de cambio activos que despacha el nodo de esta máquina."""
    if not corren_aqui(config, maquina):
        return []
    from telar import periodicos

    # el que se llama como un periódico queda fuera (telar.periodicos.choques; lo dice `telar doctor`)
    chocan = {nombre for nombre, _ in periodicos.choques_aqui(config)}
    return [d for d in getattr(config, "disparadores", ()) if d.tipo == "cambio" and d.activo and d.nombre not in chocan]


def correr(ctx, d: Disparador) -> dict:
    """Corre uno de reloj o de cambio una vez, como un periódico. Devuelve lo anotado."""
    from telar import periodicos

    return periodicos.correr(ctx, d.proceso())


# ── el despacho de «al cambiar» ─────────────────────────────────────────────────

class Despacho:
    """Qué disparadores de cambio corren y cuándo, con el freno (docs/propuestas/disparadores.md). No corre
    nada: dice cuáles salen ahora (`llego`, `listos`) y se entera de cuándo terminan (`termino`). Así se
    prueba sin bus ni procesos; el nodo es quien los corre. `ahora` es un reloj que no salta (segundos)."""

    def __init__(self, disparadores, *, pausa: float = PAUSA, tope: int = TOPE_POR_HORA, a_la_vez: int = A_LA_VEZ):
        self.por_nombre = {d.nombre: d for d in disparadores}
        self.pausa, self.tope, self.a_la_vez = pausa, tope, a_la_vez
        #: los que esperan correr, en el orden en que llegó su cambio (un dict como conjunto ordenado)
        self.pendientes: dict[str, None] = {}
        self.corriendo: set[str] = set()
        self.ultima: dict[str, float] = {}
        self.corridas: dict[str, deque] = {}
        #: los frenados por el tope, ya anotados: no se repite la línea en cada cambio
        self.frenados: set[str] = set()
        #: lo que el nodo tiene que anotar en su registro (lo vacía quien lo lee)
        self.avisos: list[str] = []

    def __bool__(self) -> bool:
        return bool(self.por_nombre)

    def temas(self) -> set[str]:
        return {d.tema for d in self.por_nombre.values()}

    def llego(self, tema: str, ahora: float) -> list[Disparador]:
        """Llegó un cambio de `tema`: los que lo esperan quedan pendientes (uno por disparador, aunque lleguen
        diez), y sale lo que puede salir ya."""
        for d in self.por_nombre.values():
            if d.tema == tema:
                self.pendientes[d.nombre] = None
        return self.listos(ahora)

    def listos(self, ahora: float) -> list[Disparador]:
        """Los pendientes que salen ahora, ya marcados como corriendo: los que no corren, ya cumplieron su pausa
        y no pasaron su tope, mientras haya lugar en el nodo."""
        salen = []
        for nombre in list(self.pendientes):
            if len(self.corriendo) >= self.a_la_vez:
                break
            if nombre in self.corriendo or ahora - self.ultima.get(nombre, float("-inf")) < self.pausa:
                continue
            hechas = self.corridas.setdefault(nombre, deque())
            while hechas and ahora - hechas[0] >= 3600:
                hechas.popleft()
            if len(hechas) >= self.tope:
                if nombre not in self.frenados:
                    self.frenados.add(nombre)
                    self.avisos.append(f"disparador «{nombre}»: {self.tope} corridas en una hora, ¿se dispara a sí"
                                       f" mismo? lo que llegue espera a que se cumpla la hora")
                continue
            self.frenados.discard(nombre)
            del self.pendientes[nombre]
            self.corriendo.add(nombre)
            self.ultima[nombre] = ahora
            hechas.append(ahora)
            salen.append(self.por_nombre[nombre])
        return salen

    def termino(self, nombre: str) -> None:
        self.corriendo.discard(nombre)
