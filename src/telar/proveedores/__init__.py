"""Proveedores: lo que llega de afuera y le toca a un hilo.

Una agenda, un gestor de tareas, un correo. Cada proveedor es opcional y **no
existe hasta que la configuración lo declara**: telar no abre una conexión que
nadie pidió, y no trae ninguno puesto de fábrica.

Un proveedor cumple tres reglas:

  1. se enciende solo desde `[proveedores.<nombre>]` en la configuración;
  2. declara en `alcance` qué toca del mundo, para que se pueda leer antes de
     encenderlo (`"lee la agenda local"`, `"consulta la API de X"`);
  3. devuelve `telar.modelo.Item` y nada más. Si falla, lanza `ErrorDeProveedor`
     y telar sigue sin él: un proveedor caído no puede apagar el telar.

telar no manda nada a ninguna parte por su cuenta: no hay telemetría, ni informes
de uso, ni actualizaciones automáticas.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from telar.config import Proveedor as ConfigProveedor
from telar.modelo import Item

__all__ = ["Fuente", "ErrorDeProveedor", "REGISTRO", "registrar", "obtener", "consultar"]


class ErrorDeProveedor(Exception):
    """El proveedor no pudo responder. Nunca es fatal para telar."""


@runtime_checkable
class Fuente(Protocol):
    """Un proveedor de ítems."""

    #: cómo se llama en la configuración.
    nombre: str
    #: qué toca del mundo, en una frase, para que se pueda leer antes de encenderlo.
    alcance: str

    def consultar(self, dia: date) -> list[Item]:
        """Los ítems que le importan a ese día. Sin efectos: solo lee."""
        ...


#: nombre → fábrica `(ConfigProveedor) -> Fuente`. Se llena con `registrar`.
REGISTRO: dict[str, object] = {}


def registrar(nombre: str, fabrica) -> None:
    """Deja disponible un proveedor. Encenderlo sigue siendo cosa de la configuración."""
    if nombre in REGISTRO:
        raise ValueError(f"ya hay un proveedor llamado {nombre!r}")
    REGISTRO[nombre] = fabrica


def obtener(cfg: ConfigProveedor) -> Fuente:
    """Construye un proveedor declarado en la configuración."""
    fabrica = REGISTRO.get(cfg.nombre)
    if fabrica is None:
        conocidos = ", ".join(sorted(REGISTRO)) or "ninguno"
        raise ErrorDeProveedor(
            f"no hay un proveedor llamado {cfg.nombre!r}; registrados: {conocidos}"
        )
    return fabrica(cfg)  # type: ignore[operator]


def consultar(proveedores: list[ConfigProveedor], dia: date) -> tuple[list[Item], list[str]]:
    """Consulta a todos los proveedores encendidos.

    Devuelve lo que se pudo juntar y la lista de fallas en texto. Uno que se cae no
    se lleva a los demás, y quien dibuje decide si muestra las fallas o las calla.
    """
    items: list[Item] = []
    fallas: list[str] = []
    for cfg in proveedores:
        if not cfg.activo:
            continue
        try:
            items.extend(obtener(cfg).consultar(dia))
        except ErrorDeProveedor as e:
            fallas.append(f"{cfg.nombre}: {e}")
        except Exception as e:  # un proveedor ajeno no tiene por qué ser prolijo
            fallas.append(f"{cfg.nombre}: {type(e).__name__}: {e}")
    return items, fallas
