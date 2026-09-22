"""Los eventos del agente, y en qué se convierten: atención por hilo, conversación por panel.

Un agente de línea de comandos que trabaja dentro de un hilo sabe cosas que telar no
puede ver desde afuera: cuándo arrancó a responder, cuándo se quedó esperando una
decisión, cuándo terminó, y qué conversación es la que está viva ahí adentro. Este
módulo declara **seis eventos** y qué hace telar con cada uno. Nada más: quien traduce
los avisos de un agente concreto a estos seis es su adaptador (`claude_code.py` es el
que viene incluido).

    evento      cuándo lo manda el agente            qué deja en telar
    ────────────────────────────────────────────────────────────────────────────
    abre        arranca una conversación             hilo → conversación, y el panel
    empieza     se puso a trabajar                   atención: trabajando
    espera      necesita a la persona                atención: espera
    sigue       dio señales de vida (una herramienta) desmiente un «espera» anterior
    termina     acabó la respuesta                   atención: terminó
    cierra      la sesión se acabó                   atención: ninguna

Los cuatro del medio son exactamente lo que escribe `telar atencion set`: el evento es
la forma automática de lo mismo que un agente puede decir a mano. `abre` y `cierra` no
hablan de atención sino del **registro de conversación por panel**, que es lo que
permite volver a abrir mañana la conversación que hoy vive en este tab.

Cuatro lecciones, aprendidas a golpes y escritas aquí para no volver a pagarlas:

1. **El hilo no sale del foco.** La persona se cambia de tab mientras un agente
   arranca, y anotar «el que tiene el foco» le pone la conversación al tab
   equivocado. Sale, en orden: de `$TELAR_HILO`, del panel donde corre el agente, o
   de la conversación ya anotada. Nunca del foco.
2. **Se escribe solo si algo cambió.** Del otro lado hay una barra vigilando estos
   archivos: reescribir «trabajando» sobre «trabajando» la despierta para nada.
3. **`sigue` no afirma, desmiente.** Una herramienta ejecutada no significa
   «empecé»; significa «si te dije que te esperaba, ya no». Cualquier otra lectura
   pisa un `espera` legítimo que todavía no se resolvió.
4. **Un gancho jamás frena al agente.** Rápido, callado y con código de salida 0
   pase lo que pase: el precio de que telar se equivoque no puede ser que la persona
   pierda su conversación.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from telar import estado as mod_estado
from telar.agente import Conversacion, ErrorDeAgente
from telar.modelo import Atencion

__all__ = [
    "Evento",
    "EVENTOS",
    "ATENCION",
    "Aviso",
    "Efecto",
    "Gancho",
    "Instalacion",
    "AgenteBase",
    "atencion_de",
    "aplicar",
    "resolver_hilo",
    "panel_del_entorno",
    "hilo_del_panel",
    "comando_aviso",
    "ejecutable_telar",
    "ruta_inestable",
    "VARIABLE_PANEL",
    "VARIABLE_HILO",
    "VARIABLE_AGENTE",
]

#: Con qué se identifica un hilo ante telar. Lo exporta el multiplexor al abrir el tab.
VARIABLE_HILO = "TELAR_HILO"

#: El panel donde corre el agente, si algo se lo dijo explícitamente.
VARIABLE_PANEL = "TELAR_PANEL"

#: Qué agente usar cuando no se nombra ninguno.
VARIABLE_AGENTE = "TELAR_AGENTE"


class Evento(str, Enum):
    """Lo que un agente puede avisar. Seis palabras, y ninguna más."""

    #: arrancó una conversación en este panel
    ABRE = "abre"
    #: se puso a trabajar
    EMPIEZA = "empieza"
    #: necesita a la persona para seguir
    ESPERA = "espera"
    #: dio señales de vida sin decir nada nuevo (corrió una herramienta)
    SIGUE = "sigue"
    #: acabó la respuesta
    TERMINA = "termina"
    #: la sesión se acabó
    CIERRA = "cierra"


#: Los nombres de los eventos, para quien los reciba por línea de comandos.
EVENTOS: tuple[str, ...] = tuple(e.value for e in Evento)

#: La atención que deja cada evento. `None` significa «este evento no habla de atención».
ATENCION: dict[Evento, Atencion | None] = {
    Evento.ABRE: None,
    Evento.EMPIEZA: Atencion.TRABAJANDO,
    Evento.ESPERA: Atencion.ESPERA,
    Evento.SIGUE: None,  # caso aparte: ver `atencion_de`
    Evento.TERMINA: Atencion.TERMINO,
    Evento.CIERRA: Atencion.NINGUNA,
}


@dataclass(frozen=True, slots=True)
class Aviso:
    """Un evento del agente, ya traducido al vocabulario de telar.

    Es lo único que el adaptador de un agente tiene que saber construir: de aquí en
    adelante, todos los agentes se parecen. `datos` lleva lo que el agente mande de
    más —telar no lo interpreta, pero lo deja a mano para depurar—.
    """

    evento: Evento
    #: qué agente lo manda ("claude-code"); informativo.
    agente: str = ""
    #: id de la conversación, si el agente tiene una.
    sesion: str = ""
    #: el hilo, si el agente lo sabe de primera mano; si no, se resuelve.
    hilo: str = ""
    #: el panel del multiplexor donde corre; es lo que desempata cuando hay dudas.
    panel: str = ""
    #: desde dónde corre el agente, si lo dice.
    ruta: Path | None = None
    #: cuándo pasó; sin esto, el momento en que telar lo anota.
    cuando: datetime | None = None
    datos: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Efecto:
    """Qué cambió de verdad al aplicar un aviso. Vacío quiere decir «nada que hacer»."""

    hilo: str = ""
    #: la atención que quedó escrita, o None si no hubo nada que escribir.
    atencion: Atencion | None = None
    #: la conversación que quedó anotada en el hilo.
    anotada: str = ""
    #: las conversaciones del hilo después del cambio, la principal primero.
    conversaciones: tuple[str, ...] = ()
    #: la conversación se sacó de todos lados (el agente se despidió del todo).
    olvidada: bool = False

    @property
    def vacio(self) -> bool:
        return self.atencion is None and not self.anotada and not self.olvidada


@dataclass(frozen=True, slots=True)
class Gancho:
    """Un evento nativo del agente enganchado a un evento de telar.

    `nativo` es cómo lo llama el agente en su propia configuración; `filtro` es lo que
    ese agente quiera para acotarlo (en Claude Code, el `matcher` de las herramientas).
    """

    evento: Evento
    nativo: str
    filtro: str = ""
    #: a los ganchos que se disparan a cada rato conviene ponerles un tope de espera.
    espera: int = 5


@dataclass(frozen=True, slots=True)
class Instalacion:
    """Qué hizo (o qué haría) `telar agente instalar`."""

    ruta: Path
    ganchos: tuple[str, ...] = ()
    escrito: bool = False
    respaldo: Path | None = None
    #: el archivo como quedaría, para poder mirarlo antes de escribirlo.
    texto: str = ""
    #: qué se encontró de antes y se reemplazó.
    reemplazados: tuple[str, ...] = ()
    #: el archivo como está ahora, para poder mostrar la diferencia antes de tocarlo.
    antes: str = ""
    #: con qué palabras quedaría llamado telar desde el gancho.
    comando: tuple[str, ...] = ()


# ── el cálculo, que no toca disco ───────────────────────────────────────────────


def atencion_de(evento: Evento, actual: Atencion = Atencion.NINGUNA) -> Atencion | None:
    """La atención que hay que escribir, o `None` si no hay nada que escribir.

    Dos reglas viven aquí y en ninguna otra parte: que `sigue` solo desmiente un
    `espera` anterior, y que una atención igual a la que ya estaba no se escribe —del
    otro lado hay una barra vigilando el archivo—.
    """
    if evento is Evento.SIGUE:
        return Atencion.TRABAJANDO if actual is Atencion.ESPERA else None
    nueva = ATENCION.get(evento)
    if nueva is None or nueva == actual:
        return None
    return nueva


def panel_del_entorno(multiplexor: str = "", entorno: Mapping[str, str] | None = None) -> str:
    """El panel donde corre este proceso, según las variables que exportó el multiplexor.

    `$TELAR_PANEL` manda sobre todo: es la forma de decirlo sin que telar tenga que
    conocer al multiplexor. Si no está, se usa lo que cada uno exporta por su cuenta.
    """
    entorno = os.environ if entorno is None else entorno
    propio = (entorno.get(VARIABLE_PANEL) or "").strip()
    if propio:
        return propio
    variable, molde = PANELES.get(multiplexor, ("", "{}"))
    crudo = (entorno.get(variable) or "").strip() if variable else ""
    return molde.format(crudo) if crudo else ""


#: Cómo llama cada multiplexor al panel actual en el entorno, y cómo se escribe su id.
PANELES: dict[str, tuple[str, str]] = {
    "zellij": ("ZELLIJ_PANE_ID", "terminal_{}"),
    "tmux": ("TMUX_PANE", "{}"),
}


def hilo_del_panel(mux, panel: str) -> str:
    """El hilo donde vive un panel, preguntándole al multiplexor. Vacío si no se sabe.

    Cuesta un par de subprocesos, así que se pregunta solo cuando hace falta de
    verdad: al abrir una conversación. Los eventos que se disparan a cada rato
    (`sigue`, `empieza`) se resuelven con lo que ya está anotado.

    Aguanta las dos formas que hay hoy de listar paneles —objetos `Pane` y los
    diccionarios crudos de zellij— y ante cualquier tropiezo devuelve vacío: no saber
    en qué tab está un panel no es motivo para tumbar un gancho.
    """
    if mux is None or not panel:
        return ""
    try:
        tabs = {h.id: h.nombre for h in mux.hilos()}
    except Exception:  # noqa: BLE001 - un gancho no se cae por esto
        return ""

    paneles = getattr(mux, "panes", None)
    if callable(paneles):
        try:
            for p in paneles():
                if str(getattr(p, "id", "")) == panel:
                    return tabs.get(str(getattr(p, "tab", "")), "")
        except Exception:  # noqa: BLE001
            return ""

    crudos = getattr(mux, "paneles", None)
    if callable(crudos):
        try:
            for p in crudos():
                if not isinstance(p, dict):
                    continue
                if panel in _ids_de_panel(p):
                    nombre = str(p.get("tab_name") or "")
                    return nombre or tabs.get(str(p.get("tab_id", "")), "")
        except Exception:  # noqa: BLE001
            return ""
    return ""


def _ids_de_panel(panel: dict) -> tuple[str, ...]:
    """Las formas en que se puede escribir el id de un panel crudo de zellij."""
    crudo = panel.get("id")
    if crudo is None:
        return ()
    prefijo = "plugin" if panel.get("is_plugin") else "terminal"
    return (str(crudo), f"{prefijo}_{crudo}")


def resolver_hilo(
    est: mod_estado.Estado,
    aviso: Aviso,
    *,
    mux=None,
    multiplexor: str = "",
    entorno: Mapping[str, str] | None = None,
) -> str:
    """En qué hilo pasó esto. Vacío si no hay manera de saberlo.

    El orden importa y es la lección de la que salió este módulo:

      1. lo que dijo quien llama (`--hilo`), que es una decisión, no una pista;
      2. `$TELAR_HILO`, que el multiplexor exportó al abrir el tab y el agente heredó;
      3. **al abrir**, el panel: una conversación que se retoma en otro tab tiene que
         mudarse con él, y el panel es lo único que lo dice;
      4. la conversación ya anotada, que para todo lo demás es exacta y gratis;
      5. el panel, como último recurso, si hay multiplexor a quien preguntarle.

    El foco no aparece en la lista. Nunca: la persona se va a otro tab mientras el
    agente trabaja, y ese es justamente el momento en que se dispara un evento.
    """
    entorno = os.environ if entorno is None else entorno
    if aviso.hilo:
        return aviso.hilo
    del_entorno = (entorno.get(VARIABLE_HILO) or "").strip()
    if del_entorno:
        return del_entorno

    panel = aviso.panel or panel_del_entorno(multiplexor, entorno)
    if aviso.evento is Evento.ABRE:
        por_panel = hilo_del_panel(mux, panel)
        if por_panel:
            return por_panel
    if aviso.sesion:
        anotado = est.hilo_de(aviso.sesion)
        if anotado:
            return anotado
    return hilo_del_panel(mux, panel)


# ── escribirlo ──────────────────────────────────────────────────────────────────


def aplicar(
    est: mod_estado.Estado,
    aviso: Aviso,
    *,
    hilo: str,
    panel: str = "",
    olvidar_al_cerrar: bool = False,
) -> Efecto:
    """Deja el aviso escrito en el estado. Devuelve qué cambió de verdad.

    Al **cerrar** se borra la atención pero **no** la conversación: sigue en disco y es
    exactamente la que se va a querer retomar mañana. Tampoco se borra el panel, que es
    lo que permite darse cuenta de que la conversación de antes murió cuando arranque
    otra ahí mismo. Quien quiera olvidarla del todo lo pide (`olvidar_al_cerrar`).
    """
    if not hilo:
        raise ErrorDeAgente(
            "no sé en qué hilo pasó esto: exporta $TELAR_HILO en el tab o pásame --hilo"
        )

    anotada = ""
    conversaciones: tuple[str, ...] = ()
    olvidada = False

    if aviso.evento is Evento.ABRE and aviso.sesion:
        conversaciones = est.anotar_sesion(hilo, aviso.sesion, panel=panel or aviso.panel)
        anotada = aviso.sesion
    elif aviso.evento is Evento.CIERRA and aviso.sesion and olvidar_al_cerrar:
        est.olvidar_sesion(aviso.sesion)
        olvidada = True

    nueva = atencion_de(aviso.evento, est.atencion(hilo))
    if nueva is not None:
        est.anotar_atencion(hilo, nueva, aviso.cuando)

    return Efecto(
        hilo=hilo,
        atencion=nueva,
        anotada=anotada,
        conversaciones=conversaciones,
        olvidada=olvidada,
    )


# ── cómo se llama a telar desde un gancho ───────────────────────────────────────


def ejecutable_telar() -> list[str]:
    """Con qué palabras se invoca a telar desde afuera.

    El gancho corre con el entorno del agente, que puede no tener el `PATH` de este
    proceso: por eso se escribe la ruta absoluta que se encuentre ahora, y solo si no
    hay ninguna se cae al intérprete que está corriendo esto.
    """
    ruta = shutil.which("telar")
    if ruta:
        return [ruta]
    return [sys.executable, "-m", "telar.cli"]


#: por aquí se reconoce un gancho de telar dentro de la configuración de otro programa.
MARCA_AVISO = "agente aviso"


def comando_aviso(agente: str, *, ejecutable: Sequence[str] | None = None) -> list[str]:
    """El comando que un gancho tiene que correr para avisarle a telar.

    Un solo comando para todos los eventos: cuál fue viene en el JSON que el agente le
    manda por la entrada estándar, y el adaptador sabe leerlo.
    """
    base = list(ejecutable) if ejecutable else ejecutable_telar()
    return [*base, "agente", "aviso", agente]


def _carpetas_temporales() -> tuple[Path, ...]:
    """Las carpetas de esta máquina cuyo contenido no está prometido para mañana."""
    carpetas: list[Path] = []
    for cruda in (tempfile.gettempdir(), "/tmp", "/var/tmp"):
        try:
            resuelta = Path(cruda).resolve()
        except OSError:  # pragma: no cover - una carpeta temporal ilegible
            continue
        if resuelta not in carpetas:
            carpetas.append(resuelta)
    return tuple(carpetas)


def ruta_inestable(palabras: Sequence[str]) -> str:
    """Por qué ese comando no serviría dentro de un mes. Vacío si se ve estable.

    Un gancho se escribe una vez y se dispara durante meses: la ruta que se le deje
    tiene que seguir existiendo mucho después de la orden que la escribió. Un telar
    que hoy vive en un venv temporal —una prueba, un `pipx run`, un arenero— es la
    forma más fácil de dejarle a alguien seis ganchos rotos en la configuración de
    otro programa, y el error aparece recién cuando el temporal se borra.
    """
    primera = next((str(p) for p in palabras if p), "")
    if not primera:
        return "no hay con qué llamar a telar"
    ruta = Path(primera)
    if not ruta.is_absolute():
        if shutil.which(primera):
            return ""
        return f"«{primera}» no está en el PATH"
    try:
        resuelta = ruta.resolve()
        existe = resuelta.exists()
    except OSError:  # pragma: no cover - un camino que el sistema no deja mirar
        return ""
    if not existe:
        return f"«{ruta}» no existe"
    for temporal in _carpetas_temporales():
        if resuelta == temporal or temporal in resuelta.parents:
            return f"«{ruta}» está dentro de {temporal}, que es una carpeta temporal"
    return ""


# ── el esqueleto de un adaptador ────────────────────────────────────────────────


class AgenteBase(ABC):
    """Lo que todo adaptador de agente hereda hecho.

    Queda por implementar lo único que es de cada agente: cómo se llama su ejecutable,
    cómo se lee el aviso que manda, y con qué comando se abre o se retoma una
    conversación. El resto —dónde se anota, cómo se traduce a atención, cómo se busca
    el hilo— es de arriba y es igual para todos.
    """

    #: cómo se declara en la configuración y en el registro.
    nombre: str = ""

    #: los ejecutables que delatan a este agente en el panel.
    comandos: tuple[str, ...] = ()

    def __init__(self, config) -> None:
        self.config = config
        self.estado = mod_estado.abrir(config)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}({self.nombre!r})"

    # ── reconocerlo ─────────────────────────────────────────────────────────────

    def corriendo(self, comando: str) -> bool:
        """¿Ese comando de panel es este agente?

        Se mira el proceso, nunca el título del panel. Y se mira palabra por palabra,
        porque muchos agentes se distribuyen como un script que arranca otra cosa
        (`node …/claude`), y el nombre que importa no siempre es el primero.
        """
        if not comando or not self.comandos:
            return False
        return any(Path(palabra).name in self.comandos for palabra in comando.split())

    # ── conversaciones ──────────────────────────────────────────────────────────

    def conversaciones(self, hilo: str) -> list[Conversacion]:
        """Las conversaciones anotadas para un hilo, la principal primero."""
        return [
            Conversacion(id=sid, hilo=hilo, archivo=self.archivo_de(sid))
            for sid in self.estado.sesiones().get(hilo, ())
        ]

    def anotar(self, hilo: str, conversacion: Conversacion, *, panel: str = "") -> None:
        """Guarda el vínculo hilo → conversación. Se llama cuando el agente arranca."""
        self.estado.anotar_sesion(hilo, conversacion.id, panel=panel)

    def atencion(self, hilo: str) -> Atencion:
        return self.estado.atencion(hilo)

    def archivo_de(self, conversacion: Conversacion | str) -> Path | None:
        """Dónde guarda el agente esa conversación, si la guarda en disco."""
        return None

    # ── lo que cada agente sabe de sí mismo ─────────────────────────────────────

    @abstractmethod
    def leer_aviso(self, crudo: Mapping[str, object], *, evento: Evento | None = None) -> Aviso:
        """Traduce lo que el agente manda por su gancho a un `Aviso` de telar.

        Con `evento` se fuerza cuál es, para los agentes que no lo dicen en su carga o
        que enganchan un comando distinto por evento.
        """

    @abstractmethod
    def retomar(self, conversacion: Conversacion) -> list[str]:
        """El comando que vuelve a abrir esa conversación, sin correrlo."""

    def nuevo_con_id(self, mensaje: str = "") -> tuple[list[str], str]:
        """Una conversación nueva cuyo id se sabe antes de abrirla: (comando, id).

        Es lo que permite archivar un hilo y retomarlo después sin depender de ganchos:
        quien la abre guarda el id junto al hilo. El agente que no sepa fijar el id
        devuelve "", y entonces su conversación solo se conoce si un gancho la anota.
        """
        palabras = self.nuevo()
        return ([*palabras, mensaje] if mensaje else palabras), ""

    def con_mensaje(self, mensaje: str) -> list[str]:
        """Una conversación nueva que arranca diciendo `mensaje`. Sin correrla.

        La mayoría de los agentes de línea de comandos aceptan el primer mensaje como
        argumento; el que no, que lo sobrescriba.
        """
        return [*self.nuevo(), mensaje]

    @abstractmethod
    def nuevo(self, ruta: Path | None = None) -> list[str]:
        """El comando que abre una conversación nueva, sin correrlo."""

    def comandos_instalados(self) -> tuple[str, ...]:
        """Los comandos de telar que hoy están puestos en la configuración del agente.

        Sirve para comprobar que siguen apuntando a un telar que existe: la ruta se
        escribe absoluta a propósito, y un venv rehecho la deja muerta en silencio.
        Quien no sepa mirar su configuración devuelve vacío y no pasa nada.
        """
        return ()

    def ganchos(self) -> tuple[Gancho, ...]:
        """Qué eventos nativos hay que enganchar para que telar se entere de todo."""
        return ()

    # ── instalarse en la configuración del agente ───────────────────────────────

    def ruta_ajustes(self) -> Path:
        """Dónde vive la configuración de este agente en esta máquina."""
        raise ErrorDeAgente(f"{self.nombre}: no sé dónde guarda su configuración")

    def instalar(
        self,
        *,
        ruta: Path | None = None,
        ejecutable: Sequence[str] | None = None,
        seco: bool = False,
    ) -> Instalacion:
        """Deja los ganchos escritos en la configuración del agente."""
        raise ErrorDeAgente(
            f"{self.nombre}: no se instala solo; hay que enganchar a mano"
            " `telar agente aviso` (ver docs/agentes.md)"
        )

    def desinstalar(self, *, ruta: Path | None = None, seco: bool = False) -> Instalacion:
        """Saca los ganchos de telar de la configuración del agente."""
        raise ErrorDeAgente(f"{self.nombre}: no se instala solo, así que no hay nada que sacar")
