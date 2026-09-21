"""El multiplexor de terminal: la única parte de telar que habla con tmux o zellij.

Todo lo demás trabaja con `telar.modelo.Hilo` y no sabe qué programa hay debajo.
Un multiplexor nuevo se agrega escribiendo un módulo aquí que cumpla `Multiplexor`
y registrándolo en `IMPLEMENTACIONES`; nada fuera de esta carpeta cambia.

Lo que un multiplexor tiene que saber hacer es poco a propósito: listar sus tabs,
decir cuál tiene el foco, ir a uno, renombrarlo, crear uno, cerrarlo, y escribir
texto en un panel sin enviarlo. Ese último es el que permite dejarle una frase
puesta al agente que ya está trabajando ahí, en vez de abrirle otro.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from telar.config import Config
from telar.modelo import Hilo

__all__ = ["Multiplexor", "ErrorDeMux", "IMPLEMENTACIONES", "obtener"]

#: multiplexor → módulo de esta carpeta que lo implementa.
IMPLEMENTACIONES: dict[str, str] = {
    "tmux": "telar.mux.tmux",
    "zellij": "telar.mux.zellij",
}


class ErrorDeMux(Exception):
    """El multiplexor no está, no responde, o no sabe hacer lo que se le pidió."""


@runtime_checkable
class Multiplexor(Protocol):
    """Lo que telar le pide a un multiplexor de terminal.

    Ninguna de estas operaciones inventa: si la sesión no existe, `hilos` devuelve
    una lista vacía y `viva` es falso. Levantar la sesión es `tejer`, y es la única
    que crea algo sin que se lo pidan dos veces.
    """

    #: el nombre con que se declara en la configuración ("tmux", "zellij").
    nombre: str

    def viva(self) -> bool:
        """¿Existe la sesión que dice la configuración?"""
        ...

    def tejer(self) -> None:
        """Levanta la sesión si no está; si está, no toca nada."""
        ...

    def hilos(self) -> list[Hilo]:
        """Los tabs de la sesión, en el orden del multiplexor.

        Devuelve `Hilo` con lo que el multiplexor sabe: `id`, `nombre`, `activo` y
        la `ruta` si el panel tiene un `cwd`. Prioridad, atención, ficha y tiempo
        los pone quien los sepa, más arriba.
        """
        ...

    def activo(self) -> Hilo | None:
        """El hilo con el foco, o None si la sesión no está viva."""
        ...

    def ir(self, hilo: str) -> None:
        """Pone el foco en un hilo, por id."""
        ...

    def crear(self, nombre: str, ruta: Path | None = None, comando: list[str] | None = None) -> Hilo:
        """Abre un hilo nuevo y lo devuelve ya identificado."""
        ...

    def renombrar(self, hilo: str, nombre: str) -> None: ...

    def cerrar(self, hilo: str) -> None: ...

    def escribir(self, hilo: str, texto: str, *, enviar: bool = False) -> None:
        """Deja `texto` escrito en el panel del hilo.

        Con `enviar=False` queda puesto y sin ejecutar: la persona decide. Es el
        modo por defecto porque telar le escribe a agentes, no por ellos.
        """
        ...


def obtener(config: Config) -> Multiplexor:
    """El multiplexor que declara la configuración, ya construido.

    Cada implementación expone `construir(config) -> Multiplexor`.
    """
    import importlib

    ruta = IMPLEMENTACIONES.get(config.multiplexor)
    if ruta is None:
        conocidos = ", ".join(sorted(IMPLEMENTACIONES))
        raise ErrorDeMux(f"no conozco el multiplexor {config.multiplexor!r}; conozco: {conocidos}")

    try:
        modulo = importlib.import_module(ruta)
    except ModuleNotFoundError as e:
        if e.name != ruta:
            raise
        raise ErrorDeMux(f"el soporte de {config.multiplexor} todavía no está escrito") from e

    return modulo.construir(config)
