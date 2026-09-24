"""Los datos que telar se pasa entre módulos. Sin E/S, sin subprocesos, sin red.

Un módulo que lee algo del mundo (el multiplexor, un README, un proveedor) devuelve
estas piezas; un módulo que dibuja o actúa recibe estas piezas. Así se puede probar
todo lo demás con datos inventados, y por eso este archivo no importa nada fuera de
la biblioteca estándar.

El vocabulario, de una vez:

  hilo        una unidad de trabajo viva: un tab del multiplexor.
  documento   el archivo que ese hilo tiene por cara (normalmente un README).
  ficha       lo que se leyó del documento, ya parseado, según el perfil.
  atención    en qué está el agente del hilo: trabajando, esperándote, terminó.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

__all__ = [
    "Atencion",
    "Prioridad",
    "Pendiente",
    "Ficha",
    "Hilo",
    "Marca",
    "Item",
]


class Atencion(str, Enum):
    """Semáforo de un hilo: qué hace ahora el agente que corre ahí.

    Es `str` para que serialice a JSON sin ayuda y se compare con un literal.
    """

    NINGUNA = "ninguna"
    TRABAJANDO = "trabajando"
    ESPERA = "espera"
    TERMINO = "termino"


class Prioridad(int, Enum):
    """Prioridad manual de un hilo. Sin prioridad, el hilo va al final."""

    ALTA = 1
    MEDIA = 2
    BAJA = 3


@dataclass(frozen=True, slots=True)
class Pendiente:
    """Una viñeta del documento, o una tarea que aportó un proveedor."""

    texto: str
    hecho: bool = False
    en_curso: bool = False
    #: identificador estable si vino de un proveedor (p. ej. "T84"); vacío si salió del texto.
    id: str = ""
    #: de dónde salió: el nombre de la sección del perfil o del proveedor.
    origen: str = ""


@dataclass(frozen=True, slots=True)
class Ficha:
    """Lo que el documento de un hilo dice de sí mismo, ya parseado.

    `secciones` son las declaradas en el perfil (`telar.perfil.Seccion.nombre` →
    valor); `titulo`, `estado` y `pendientes` son los tres nombres que telar
    entiende por convención y muestra sin preguntar. Todo lo demás queda en
    `secciones` y lo dibuja quien sepa qué significa.
    """

    documento: Path | None = None
    titulo: str = ""
    estado: str = ""
    pendientes: tuple[Pendiente, ...] = ()
    secciones: dict[str, object] = field(default_factory=dict)
    #: cuándo se leyó el documento, para saber si la ficha está rancia.
    leida: datetime | None = None
    #: por qué la ficha salió vacía, si salió vacía (ruta inexistente, sin secciones…).
    nota: str = ""
    #: el nombre para mostrar, armado con la `etiqueta` del arquetipo. Vacío: no hay.
    etiqueta: str = ""

    @property
    def vacia(self) -> bool:
        return not (self.titulo or self.estado or self.pendientes or self.secciones)


@dataclass(frozen=True, slots=True)
class Hilo:
    """Un tab del multiplexor, con lo que telar sabe de él.

    `id` es la llave del multiplexor (`@3` en tmux, el id del tab en zellij): la
    usan las órdenes, y es lo que permite seguir un tab cuando lo renombran. `nombre` es lo que se muestra.
    """

    id: str
    nombre: str
    #: carpeta del hilo: la que el usuario vinculó o, si no vinculó ninguna, el `cwd`
    #: de su panel principal. Sirve para trabajar; no dice que alguien haya decidido nada.
    ruta: Path | None = None
    #: la carpeta que el usuario VINCULÓ (estado), y solo esa. None si nadie vinculó nada.
    vinculo: Path | None = None
    #: el arquetipo del perfil que le calzó, si alguno.
    arquetipo: str = ""
    activo: bool = False
    archivado: bool = False
    prioridad: Prioridad | None = None
    atencion: Atencion = Atencion.NINGUNA
    #: última vez que el hilo tuvo el foco.
    visto: datetime | None = None
    #: segundos con el foco en el día en curso.
    tiempo: float = 0.0
    ficha: Ficha | None = None
    #: sesiones de agente asociadas al hilo, en orden (la primera es la principal).
    sesiones: tuple[str, ...] = ()
    #: dónde vive su agente: "" es aquí; si no, el nombre de un `[remotos]`, o "?" si la
    #: ventana corre un mosh/ssh que telar no armó (se sabe que es remoto, no adónde).
    remoto: str = ""

    @property
    def vinculado(self) -> bool:
        """¿Alguien vinculó este hilo a una carpeta?

        No es «tiene ruta»: un tab abierto en cualquier parte trae el `cwd` de su panel,
        y eso no es una decisión de nadie. Antes decía `true` para cualquier tab, que es
        justo lo contrario de lo que la palabra promete.
        """
        return self.vinculo is not None



@dataclass(frozen=True, slots=True)
class Marca:
    """Un cambio de foco anotado en el tiempo: quién tenía la atención, y desde cuándo."""

    cuando: datetime
    hilo: str


@dataclass(frozen=True, slots=True)
class Item:
    """Lo que devuelve un proveedor: algo del mundo que le toca a un hilo.

    Un evento de agenda, un mensaje sin responder, una tarea de un gestor externo.
    telar no interpreta `datos`; lo pasa a quien lo dibuje.
    """

    proveedor: str
    id: str
    titulo: str
    cuando: datetime | None = None
    hilo: str = ""
    url: str = ""
    #: qué clase de cosa es: "evento" ocupa una hora del día, "tarea" pide hacerse.
    #: Lo dice el proveedor, porque tener fecha no alcanza: una tarea vence un día y no
    #: por eso es una reunión. Vacío: quien lo dibuje decide.
    clase: str = ""
    datos: dict[str, object] = field(default_factory=dict)
