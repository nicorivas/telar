"""El índice de una carpeta de objetos: los objetos en memoria, al día con sus archivos.

    from telar.tipos.indice import Indice
    tareas = Indice(Carpeta("~/notas/tareas", tarea.ARCHIVO))
    abiertas = tareas.consultar(lambda t: not t.cerrada_ya)
    t, version = tareas.aplicar("T84", tarea.completar, version=version)

Los archivos son la única verdad; el índice es una copia para consultar rápido, y **nadie escribe en él**:

- se arma leyendo todos los archivos, y se mantiene al día por la fecha y el tamaño de cada uno (mirar
  cientos de fechas toma milisegundos): antes de cada consulta, se relee solo lo que cambió y se saca lo
  que ya no está;
- una acción escribe el archivo (telar.tipos.carpeta) y después el índice relee ese archivo: nunca toma
  del pedido el valor que se quiso escribir;
- se puede tirar y rearmar en cualquier momento: si el proceso se reinicia, se rearma.

Un archivo que no se puede leer no se cae con los demás: queda en `fallas`, con su motivo.
"""

from __future__ import annotations

import os
import threading
from typing import Callable

from telar.tipos.carpeta import Carpeta, NoExiste

__all__ = ["Indice", "compartido"]


class Indice:
    def __init__(self, carpeta: Carpeta) -> None:
        self.carpeta = carpeta
        self._objetos: dict[str, tuple[object, str]] = {}      # id → (objeto, versión)
        self._marcas: dict[str, tuple[int, int]] = {}           # id → (fecha en ns, tamaño)
        self.fallas: dict[str, str] = {}                        # id → por qué no se pudo leer
        self._candado = threading.Lock()

    def refrescar(self) -> int:
        """Relee lo que cambió desde la última vez y saca lo que ya no está. Devuelve cuántos releyó."""
        with self._candado:
            vistos: dict[str, tuple[int, int]] = {}
            try:
                entradas = list(os.scandir(self.carpeta.ruta))
            except FileNotFoundError:
                entradas = []
            for e in entradas:
                if not e.name.endswith(".md") or not e.is_file():
                    continue
                id = e.name[:-3]
                if not self.carpeta._id.fullmatch(id) or id.upper() == "README":
                    continue
                st = e.stat()
                vistos[id] = (st.st_mtime_ns, st.st_size)
            releidos = 0
            for id, marca in vistos.items():
                if self._marcas.get(id) == marca:
                    continue
                try:
                    self._objetos[id] = self.carpeta.leer(id)
                    self.fallas.pop(id, None)
                except (NoExiste, OSError):
                    continue  # se borró entre mirar y leer: la próxima vuelta lo saca
                except Exception as error:  # noqa: BLE001 - un archivo roto no se lleva a los demás
                    self.fallas[id] = f"{type(error).__name__}: {error}"
                    self._objetos.pop(id, None)
                self._marcas[id] = marca
                releidos += 1
            for id in set(self._marcas) - set(vistos):
                self._marcas.pop(id, None)
                self._objetos.pop(id, None)
                self.fallas.pop(id, None)
            return releidos

    def obtener(self, id: str):
        """(el objeto, su versión), al día."""
        self.refrescar()
        with self._candado:
            if id not in self._objetos:
                raise NoExiste(f"no hay {id}")
            return self._objetos[id]

    def consultar(self, filtro: Callable[[object], bool] | None = None) -> list[tuple[object, str]]:
        """Los (objeto, versión) que pasan el filtro, al día, en el orden de sus identificadores."""
        self.refrescar()
        with self._candado:
            return [v for _, v in sorted(self._objetos.items()) if filtro is None or filtro(v[0])]

    def aplicar(self, id: str, accion, *args, version: str | None = None, **kwargs):
        """Aplica la acción en el archivo (con su versión) y relee ese archivo para el índice."""
        objeto, nueva = self.carpeta.aplicar(id, accion, *args, version=version, **kwargs)
        self.refrescar()
        return objeto, nueva


_compartidos: dict[tuple[str, int], Indice] = {}
_candado_compartidos = threading.Lock()


def compartido(ruta, formato) -> Indice:
    """El índice de esa carpeta en este proceso, uno solo: lo usan la API y los proveedores, y vive lo que
    vive el proceso (en `telar serve` y en el nodo, siempre; en una orden suelta, lo que dura la orden)."""
    from pathlib import Path

    llave = (str(Path(ruta).expanduser()), id(formato))
    with _candado_compartidos:
        if llave not in _compartidos:
            _compartidos[llave] = Indice(Carpeta(ruta, formato))
        return _compartidos[llave]

