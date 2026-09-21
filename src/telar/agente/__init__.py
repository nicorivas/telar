"""El agente que corre en un hilo: reconocerlo, ubicar su conversación, hablarle.

Un hilo suele tener un agente de línea de comandos trabajando dentro. telar no lo
lanza ni lo pilota: lo reconoce por el proceso que corre en el panel, guarda el
vínculo hilo → conversación, y sabe dejarle una frase escrita en su entrada sin
enviarla.

La lección que justifica este módulo: al resucitar una sesión, el multiplexor
vuelve a lanzar el comando que había, y el agente arranca **una conversación
nueva**. Las conversaciones no se pierden —están en disco— pero el vínculo con el
hilo sí, y sin ese vínculo veinte hilos en la misma carpeta son indistinguibles.
Por eso el vínculo se anota cuando el agente arranca, no cuando se necesita.

Un adaptador de agente cumple `Agente`; qué agentes hay, lo dice `REGISTRO`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from telar.modelo import Atencion

__all__ = [
    "Agente",
    "Conversacion",
    "ErrorDeAgente",
    "REGISTRO",
    "INCLUIDOS",
    "registrar",
    "obtener",
]


class ErrorDeAgente(Exception):
    """No se pudo reconocer o alcanzar al agente de un hilo."""


class Conversacion:
    """El vínculo hilo → conversación, con lo mínimo para volver a abrirla.

    `id` es del agente; `archivo` es dónde la guarda, si la guarda en disco.
    """

    __slots__ = ("id", "archivo", "hilo")

    def __init__(self, id: str, hilo: str = "", archivo: Path | None = None) -> None:
        self.id = id
        self.hilo = hilo
        self.archivo = archivo

    def __repr__(self) -> str:  # pragma: no cover
        return f"Conversacion({self.id!r}, hilo={self.hilo!r})"


@runtime_checkable
class Agente(Protocol):
    """Lo que telar le pide a un agente de línea de comandos."""

    #: cómo se llama en la configuración y en el registro.
    nombre: str

    def corriendo(self, comando: str) -> bool:
        """¿Ese comando de panel es este agente?

        Se decide por el proceso que corre ahora, no por el título del panel: un
        título miente en cuanto alguien lo renombra.
        """
        ...

    def conversaciones(self, hilo: str) -> list[Conversacion]:
        """Las conversaciones anotadas para un hilo, la principal primero."""
        ...

    def anotar(self, hilo: str, conversacion: Conversacion) -> None:
        """Guarda el vínculo hilo → conversación. Se llama cuando el agente arranca."""
        ...

    def retomar(self, conversacion: Conversacion) -> list[str]:
        """El comando que vuelve a abrir esa conversación, sin correrlo."""
        ...

    def nuevo(self, ruta: Path | None = None) -> list[str]:
        """El comando que abre una conversación nueva, sin correrlo."""
        ...

    def atencion(self, hilo: str) -> Atencion:
        """En qué está el agente de ese hilo, si se puede saber."""
        ...


#: nombre → fábrica `(Config) -> Agente`.
REGISTRO: dict[str, object] = {}

#: Los adaptadores que vienen con telar: nombre → módulo que los registra al importarse.
#: Un agente de afuera no necesita estar aquí; le basta con llamar a `registrar`.
INCLUIDOS: dict[str, str] = {
    "claude-code": "telar.agente.claude_code",
}


def registrar(nombre: str, fabrica) -> None:
    if nombre in REGISTRO:
        raise ValueError(f"ya hay un agente llamado {nombre!r}")
    REGISTRO[nombre] = fabrica


def obtener(nombre: str, config) -> Agente:
    """El agente que se llama así, construido. Los incluidos se importan al pedirlos.

    Importar perezosamente es lo que permite que `telar.agente` no sepa nada de ningún
    agente concreto: la dependencia va del adaptador al contrato, nunca al revés.
    """
    if nombre not in REGISTRO and nombre in INCLUIDOS:
        import importlib

        importlib.import_module(INCLUIDOS[nombre])
    fabrica = REGISTRO.get(nombre)
    if fabrica is None:
        conocidos = ", ".join(sorted(set(REGISTRO) | set(INCLUIDOS))) or "ninguno"
        raise ErrorDeAgente(f"no hay un agente llamado {nombre!r}; registrados: {conocidos}")
    return fabrica(config)  # type: ignore[operator]
