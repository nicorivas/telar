"""Los tipos: un esquema sobre archivos de texto (docs/arquitectura.md, «Los tipos»).

Un tipo tiene tres partes:

- **el modelo** (Pydantic): sus campos;
- **las acciones**: funciones sobre el modelo, sin texto, que anotan un cambio en su historia;
- **los formatos** (lentes): cómo se lee y se escribe el modelo en una clase de texto.

Un formato cumple dos promesas, que sus pruebas verifican contra archivos reales:

1. leer y escribir sin cambios da los mismos bytes;
2. escribir un cambio toca solo las líneas de los campos que cambiaron, y releer da el valor nuevo.

Los archivos son la única verdad: se editan a mano, y lo que el formato no reconoce se conserva tal cual.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

__all__ = ["Formato", "ErrorDeFormato"]

M = TypeVar("M", bound=BaseModel)


class ErrorDeFormato(ValueError):
    """El texto no se puede leer como ese tipo, o un cambio no cabe en ese formato."""


class Formato(Protocol, Generic[M]):
    """Una lente: lee un texto a un modelo y escribe en ese texto, al mínimo, lo que cambió."""

    def leer(self, texto: str, id: str = "") -> M: ...

    def escribir(self, texto: str, antes: M, despues: M) -> str: ...

    # opcional: el texto de un objeto que todavía no existe (Carpeta.crear)
    # def nuevo(self, objeto: M) -> str: ...
