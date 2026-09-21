"""La forma de un multiplexor: qué se le pregunta, qué se le pide, qué devuelve.

`telar.mux` declara el contrato mínimo que el resto de telar usa (`Multiplexor`:
hilos, foco, escribir). Este módulo es el escalón de abajo: el vocabulario completo
—tabs *y* paneles— que hace falta para implementarlo de verdad, más el trabajo que
ninguna implementación debería repetir.

La división, en una línea: arriba se habla de **hilos** (una unidad de trabajo), aquí
abajo se habla de **tabs y paneles** (lo que el programa de terminal tiene de verdad).
Un hilo es un tab; adentro de un tab hay paneles, y en uno de ellos corre el agente.

Por qué los paneles están en la interfaz y no escondidos en cada implementación:

  · para saber si un hilo tiene un agente trabajando hay que mirar el **proceso** que
    corre en su panel, nunca el título (un título miente en cuanto alguien lo renombra);
  · para dejarle una frase escrita al agente hay que apuntarle a un panel, no al tab;
  · las vistas auxiliares (una ficha al costado, un markdown abierto) son paneles con
    título propio, y el sistema necesita preguntar «¿ya hay una ficha en este tab?»
    antes de abrir la segunda.

Quien escriba un multiplexor nuevo hereda de `MultiplexorBase`, implementa los métodos
abstractos —que son los primitivos, los que de verdad hablan con el programa— y recibe
gratis los del contrato de arriba, ya derivados de esos primitivos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from telar.modelo import Hilo
from telar.mux import ErrorDeMux

__all__ = [
    "Tab",
    "Pane",
    "Direccion",
    "DIRECCIONES",
    "MultiplexorBase",
    "ErrorDeMux",
    "SinPrograma",
    "SinSesion",
    "NoExiste",
    "comprobar_direccion",
]

#: Hacia dónde se abre un panel respecto del que ya estaba.
Direccion = Literal["derecha", "izquierda", "arriba", "abajo"]

DIRECCIONES: tuple[str, ...] = ("derecha", "izquierda", "arriba", "abajo")


class SinPrograma(ErrorDeMux):
    """El programa del multiplexor no está instalado, o no está en el `PATH`."""


class SinSesion(ErrorDeMux):
    """La sesión que pide la configuración no existe todavía. Se levanta con `tejer`."""


class NoExiste(ErrorDeMux):
    """Se nombró un tab o un panel que el multiplexor no conoce."""


def comprobar_direccion(direccion: str) -> Direccion:
    """Deja pasar una dirección válida; si no lo es, dice cuáles lo son."""
    if direccion not in DIRECCIONES:
        conocidas = ", ".join(DIRECCIONES)
        raise ErrorDeMux(f"dirección {direccion!r} desconocida; se puede: {conocidas}")
    return direccion  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Tab:
    """Un tab del multiplexor, tal como el multiplexor lo ve.

    `id` es la llave con la que se le habla: en tmux el identificador de ventana
    (`@3`) y en zellij el id del tab, los dos estables mientras la sesión viva. `posicion`
    es el lugar en la barra, empezando por donde empiece el programa (tmux respeta su
    `base-index`), y sirve para ordenar y para mostrar, nunca para identificar.
    """

    id: str
    posicion: int
    nombre: str
    #: es el tab que la sesión tiene por actual.
    activo: bool = False
    #: cuántos paneles tiene, si el multiplexor lo dice sin costo.
    paneles: int = 0


@dataclass(frozen=True, slots=True)
class Pane:
    """Un panel dentro de un tab.

    `comando` es el proceso que corre ahí ahora mismo, y es el único campo en el que
    se puede confiar para reconocer a un agente. `titulo` es lo que el panel dice
    llamarse: lo pone quien lo abrió o el programa que corre adentro, y es cómodo para
    encontrar las vistas que telar mismo abrió, pero cualquiera lo cambia.

    `foco` es el foco **dentro de su tab**: en una sesión con diez tabs hay diez
    paneles con `foco`, uno por tab. El que tiene el foco de verdad es el del tab
    activo, y para eso está `MultiplexorBase.pane_activo`.
    """

    id: str
    #: el `Tab.id` al que pertenece.
    tab: str
    titulo: str = ""
    #: el proceso en ejecución; vacío si el multiplexor no lo sabe.
    comando: str = ""
    #: el directorio de trabajo del panel, si el multiplexor lo expone.
    ruta: Path | None = None
    foco: bool = False
    #: flotante por encima del resto (zellij); tmux no tiene paneles flotantes.
    flotante: bool = False
    #: el programa terminó y el panel quedó en pantalla.
    terminado: bool = False

    @property
    def vivo(self) -> bool:
        return not self.terminado


class MultiplexorBase(ABC):
    """El esqueleto de una implementación: lo primitivo es abstracto, lo demás se deriva.

    Las reglas que valen para todas las implementaciones:

      · nada inventa. Si la sesión no existe, `tabs` y `panes` devuelven listas vacías
        y `viva` es falso; la única operación que crea algo sin pedir permiso es `tejer`;
      · los errores son `ErrorDeMux` y dicen qué se le pidió al programa y qué contestó;
      · `escribir` deja el texto puesto y **no** lo envía salvo que se lo pidan, porque
        del otro lado hay un agente trabajando y la última palabra es de la persona.
    """

    #: el nombre con que se declara en la configuración ("tmux", "zellij").
    nombre: str = ""

    # ── la sesión ────────────────────────────────────────────────────────────────

    @abstractmethod
    def disponible(self) -> bool:
        """¿Está instalado el programa? Es una pregunta sobre la máquina, no sobre la sesión.

        Nunca levanta excepción: se usa para decidir si vale la pena seguir.
        """

    @abstractmethod
    def viva(self) -> bool:
        """¿Existe la sesión que dice la configuración? Tampoco levanta excepción."""

    @abstractmethod
    def tejer(self) -> None:
        """Levanta la sesión si no está; si está, no toca nada."""

    #: la versión con la que se probó esta implementación; "" si no se declara.
    version_minima: str = ""

    def version(self) -> str:
        """La versión instalada del multiplexor, tal como él la dice. "" si no se sabe."""
        return ""

    def huella(self) -> str:
        """Algo que identifique a ESTA encarnación de la sesión, o "" si no se sabe.

        Los ids de tab son estables mientras la sesión vive y se reciclan cuando el
        programa arranca de nuevo: el `@0` de hoy no es el `@0` de ayer. Quien guarde
        algo indexado por id necesita saber cuándo dejó de valer, y para eso está esto.
        """
        return ""

    # ── tabs ─────────────────────────────────────────────────────────────────────

    @abstractmethod
    def tabs(self) -> list[Tab]:
        """Los tabs de la sesión, en el orden en que el multiplexor los muestra."""

    @abstractmethod
    def tab_activo(self) -> Tab | None:
        """El tab que tiene el foco, o None si la sesión no está viva."""

    @abstractmethod
    def ir_a_tab(self, tab: str) -> None:
        """Pone el foco en un tab."""

    @abstractmethod
    def crear_tab(
        self,
        nombre: str,
        *,
        ruta: Path | None = None,
        comando: Sequence[str] | None = None,
        foco: bool = True,
    ) -> Tab:
        """Abre un tab nuevo y lo devuelve ya identificado.

        `comando` es siempre una lista de palabras, nunca una línea de shell; si hace
        falta un shell se pide explícito (`["sh", "-c", "…"]`). Es la misma regla que
        `telar.perfil.Accion`, y por el mismo motivo: una línea de shell armada a mano
        es una inyección esperando su turno.
        """

    @abstractmethod
    def renombrar_tab(self, tab: str, nombre: str) -> None:
        """Le cambia el nombre a un tab. El nombre puesto a mano manda sobre el automático."""

    @abstractmethod
    def cerrar_tab(self, tab: str) -> None:
        """Cierra un tab con todo lo que tenga adentro."""

    # ── paneles ──────────────────────────────────────────────────────────────────

    @abstractmethod
    def panes(self, tab: str | None = None) -> list[Pane]:
        """Los paneles de un tab, o los de toda la sesión si no se nombra ninguno."""

    @abstractmethod
    def enfocar_pane(self, pane: str) -> None:
        """Pone el foco en un panel, y de paso en el tab donde vive."""

    @abstractmethod
    def escribir_pane(self, pane: str, texto: str, *, enviar: bool = False) -> None:
        """Escribe `texto` en la entrada de un panel.

        Con `enviar=False` el texto queda puesto y sin ejecutar. Un salto de línea es
        un ↩: escribir sin enviar no admite saltos, y quien lo intente recibe un error
        en vez de una sorpresa.
        """

    @abstractmethod
    def abrir_pane(
        self,
        comando: Sequence[str] | None = None,
        *,
        junto_a: str | None = None,
        reemplaza: str | None = None,
        direccion: Direccion = "derecha",
        tamano: int | None = None,
        ruta: Path | None = None,
        titulo: str = "",
        foco: bool = True,
    ) -> Pane:
        """Abre un panel y lo devuelve.

        Dos formas, excluyentes entre sí:

          · `junto_a`: parte ese panel y se instala al lado, en `direccion`, ocupando
            `tamano` por ciento del espacio. Sin `junto_a`, parte el panel con el foco;
          · `reemplaza`: ocupa el lugar de ese panel, con su misma geometría. Es lo que
            se quiere cuando una vista se refresca y no debe mover el resto de la pantalla.
        """

    @abstractmethod
    def cerrar_pane(self, pane: str) -> None:
        """Cierra un panel. Si era el último de su tab, el tab se va con él."""

    @abstractmethod
    def mover_pane(
        self,
        pane: str,
        *,
        tab: str | None = None,
        junto_a: str | None = None,
        direccion: Direccion = "derecha",
        tamano: int | None = None,
        nombre: str = "",
        foco: bool = True,
    ) -> Pane:
        """Muda un panel de tab, sin reiniciar lo que corre adentro.

        Tres destinos: `junto_a` otro panel, adentro de un `tab` (queda al lado del
        panel activo de ese tab), o —si no se nombra ninguno— **a un tab nuevo**, que
        se llamará `nombre` si se le da uno. El panel conserva su identidad: el `id`
        que devuelve es el mismo que entró.
        """

    # ── derivados: el contrato de `telar.mux.Multiplexor` ────────────────────────
    #
    # Nada de aquí abajo habla con el programa: todo sale de los primitivos de arriba.
    # Una implementación puede pisarlos si su multiplexor lo hace más barato de un tiro.

    def buscar_tab(self, tab: str) -> Tab:
        """El tab, buscado por id, por nombre o por posición. Si no está, dice cuáles hay."""
        aguja = str(tab).strip()
        if not aguja:
            raise NoExiste("no se nombró ningún tab")
        candidatos = self.tabs()
        for t in candidatos:
            if t.id == aguja or t.nombre == aguja or str(t.posicion) == aguja:
                return t
        hay = ", ".join(f"{t.id} ({t.nombre})" for t in candidatos) or "ninguno"
        raise NoExiste(f"no hay un tab {aguja!r}; hay: {hay}")

    def pane_de(self, tab: str) -> Pane | None:
        """El panel de ese tab al que hay que hablarle: el que tiene el foco adentro.

        Si ninguno lo tiene —pasa cuando el multiplexor no lo informa— sirve el primero
        que siga vivo; y si todos terminaron, el primero, para poder decir algo del tab.
        """
        panes = [p for p in self.panes(tab) if not p.flotante]
        if not panes:
            return None
        for p in panes:
            if p.foco and p.vivo:
                return p
        for p in panes:
            if p.vivo:
                return p
        return panes[0]

    def pane_activo(self) -> Pane | None:
        """El panel con el foco de la sesión: el panel enfocado del tab activo."""
        tab = self.tab_activo()
        if tab is None:
            return None
        return self.pane_de(tab.id)

    def hilo_de(self, tab: Tab, panes: Sequence[Pane] = ()) -> Hilo:
        """Arma el `Hilo` con lo único que el multiplexor sabe de un tab.

        Prioridad, atención, ficha y tiempo los pone quien los sepa, más arriba: aquí
        se rellena `ruta` con el directorio de trabajo del panel que manda en el tab,
        y nada más. Un campo inventado acá se vuelve una mentira allá.
        """
        ruta: Path | None = None
        vivos = [p for p in panes if not p.flotante]
        for p in vivos:
            if p.foco and p.ruta is not None:
                ruta = p.ruta
                break
        else:
            for p in vivos:
                if p.ruta is not None:
                    ruta = p.ruta
                    break
        return Hilo(id=tab.id, nombre=tab.nombre, ruta=ruta, activo=tab.activo)

    def hilos(self) -> list[Hilo]:
        tabs = self.tabs()
        if not tabs:
            return []
        por_tab: dict[str, list[Pane]] = {}
        for p in self.panes():
            por_tab.setdefault(p.tab, []).append(p)
        return [self.hilo_de(t, por_tab.get(t.id, ())) for t in tabs]

    def activo(self) -> Hilo | None:
        tab = self.tab_activo()
        if tab is None:
            return None
        return self.hilo_de(tab, self.panes(tab.id))

    def ir(self, hilo: str) -> None:
        self.ir_a_tab(hilo)

    def crear(
        self,
        nombre: str,
        ruta: Path | None = None,
        comando: list[str] | None = None,
    ) -> Hilo:
        tab = self.crear_tab(nombre, ruta=ruta, comando=comando)
        return self.hilo_de(tab, self.panes(tab.id))

    def renombrar(self, hilo: str, nombre: str) -> None:
        self.renombrar_tab(hilo, nombre)

    def cerrar(self, hilo: str) -> None:
        self.cerrar_tab(hilo)

    def escribir(self, hilo: str, texto: str, *, enviar: bool = False) -> None:
        pane = self.pane_de(hilo)
        if pane is None:
            raise NoExiste(f"el hilo {hilo!r} no tiene ningún panel donde escribir")
        self.escribir_pane(pane.id, texto, enviar=enviar)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}({self.nombre!r})"
