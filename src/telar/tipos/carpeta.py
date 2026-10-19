"""Una carpeta de objetos, un archivo por objeto: leerlos con su versión y aplicarles una acción.

    from telar.tipos.carpeta import Carpeta
    from telar.tipos import tarea

    tareas = Carpeta("~/notas/tareas", tarea.ARCHIVO)
    t, version = tareas.leer("T84")
    t, version = tareas.aplicar("T84", tarea.completar, version=version)

**La versión** es la huella del archivo. Quien lee recibe la versión, y la devuelve con la acción: si el
archivo cambió desde entonces (lo editó una persona, otro agente, un `git pull`), la acción se rechaza
(`ErrorDeVersion`) y quien la pidió relee y decide. Nadie pisa sin saberlo el cambio de otro. Sin versión,
la acción se aplica sobre lo que haya.

**Un escritor a la vez**: escribir toma un candado de la carpeta; la escritura es atómica (un archivo
temporal que reemplaza al otro), y se escribe solo lo que cambió (ver las lentes en telar.tipos).
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
from pathlib import Path
from typing import Callable

from telar.tipos import ErrorDeFormato

__all__ = ["Carpeta", "ErrorDeVersion", "NoExiste", "version_de"]


class ErrorDeVersion(Exception):
    """El archivo cambió desde que se leyó: la acción no se aplicó."""

    def __init__(self, id: str, esperada: str, actual: str) -> None:
        super().__init__(f"{id} cambió desde que se leyó (versión {esperada}, ahora {actual}): reléela y decide")
        self.actual = actual


class NoExiste(LookupError):
    pass


def version_de(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


class Carpeta:
    """Los objetos de una carpeta, un archivo `<id>.md` cada uno, leídos y escritos con un formato."""

    def __init__(self, ruta, formato, *, id_valido: str = r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}") -> None:
        self.ruta = Path(ruta).expanduser()
        self.formato = formato
        self._id = re.compile(id_valido)

    def _archivo(self, id: str) -> Path:
        # un id es un nombre de archivo, nunca una ruta: nada de «../»
        if not self._id.fullmatch(id or ""):
            raise NoExiste(f"«{id}» no es un identificador")
        return self.ruta / f"{id}.md"

    def leer(self, id: str):
        """(el objeto, su versión)."""
        archivo = self._archivo(id)
        try:
            texto = archivo.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise NoExiste(f"no hay {id}") from e
        return self.formato.leer(texto, id), version_de(texto)

    def ids(self) -> list[str]:
        return sorted(p.stem for p in self.ruta.glob("*.md") if self._id.fullmatch(p.stem) and p.stem.upper() != "README")

    def aplicar(self, id: str, accion: Callable, *args, version: str | None = None, **kwargs):
        """Aplica `accion(objeto, *args, **kwargs)` y escribe el cambio. (el objeto nuevo, su versión).

        Con `version`, solo si el archivo sigue en esa versión. La acción decide si se puede (su
        precondición); el formato escribe solo lo que cambió."""
        archivo = self._archivo(id)
        self.ruta.mkdir(parents=True, exist_ok=True)
        with open(self.ruta / ".telar-escribe.lock", "w") as candado:
            fcntl.flock(candado, fcntl.LOCK_EX)
            try:
                texto = archivo.read_text(encoding="utf-8")
            except FileNotFoundError as e:
                raise NoExiste(f"no hay {id}") from e
            actual = version_de(texto)
            if version is not None and version != actual:
                raise ErrorDeVersion(id, version, actual)
            antes = self.formato.leer(texto, id)
            despues = accion(antes, *args, **kwargs)
            if despues == antes:
                return antes, actual
            nuevo = self.formato.escribir(texto, antes, despues)
            # lo escrito tiene que leerse como lo que se quiso escribir: si no, no se escribe
            releido = self.formato.leer(nuevo, id)
            ignora = set(getattr(self.formato, "IGNORA", ()))
            if releido.model_dump(exclude={"duplicadas", *ignora}) != despues.model_dump(exclude={"duplicadas", *ignora}):
                raise ErrorDeFormato(f"{id}: lo escrito no se relee igual; no se escribió")
            temporal = archivo.with_suffix(".md.tmp")
            temporal.write_text(nuevo, encoding="utf-8")
            os.replace(temporal, archivo)
            return releido, version_de(nuevo)
