"""La forma de una dirección (`tipo:id[@máquina]`, telar.objetos): escribirla y reconocerla en un texto.

Aparte de telar.objetos para que la pueda usar quien no necesita los objetos (el contexto que un gancho le da al
agente en cada sesión): aquí no hay pydantic ni servicios, y se importa en milisegundos.
"""

from __future__ import annotations

import re
from typing import NamedTuple

#: un tipo y su id, y quizás la máquina: lo que se reconoce en un texto como dirección
_DIRECCION = re.compile(r"(?<![\w/@.-])(?P<tipo>[a-z][a-z0-9-]*):(?P<id>[^\s`'\"<>()\[\]{},;]+?)(?:@(?P<maquina>[a-z0-9][\w-]*))?"
                        r"(?=$|[\s`'\"<>()\[\]{},;]|[.:!?](?:\s|$))")


#: lo que un id no puede llevar tal cual: `@` (se leería como la máquina), `%` (el escape mismo), los
#: espacios y lo que corta una dirección dentro de un texto (`buscar`)
_ESCAPAR = re.compile(r"[%@\s`'\"<>()\[\]{},;]")


def _escapar(id: str) -> str:
    return _ESCAPAR.sub(lambda m: "".join(f"%{b:02X}" for b in m.group().encode()), id)


class Direccion(NamedTuple):
    #: el id va tal cual (`◌ un rato`); escapado, solo en el texto de la dirección
    tipo: str
    id: str
    maquina: str = ""

    def __str__(self) -> str:
        return f"{self.tipo}:{_escapar(self.id)}" + (f"@{self.maquina}" if self.maquina else "")


def direccion_de(tipo: str, id: str, maquina: str = "") -> str:
    """La dirección de un objeto, como la escriben sus tipos y la llevan las salidas JSON que lo nombran
    (`telar hilos`, `telar proyectos`, `telar pendientes`, `telar tipo tarea`): `hilo:Faro`, `tarea:T84`.
    Un proyecto va por su ruta sin barras en los bordes, que es como lo encuentra `ver`. Lo que el id no puede
    llevar tal cual va escapado (`hilo:Faro%40casa`); `leer` y `buscar` lo devuelven a como era."""
    if tipo == "proyecto":
        id = id.strip("/")
    return str(Direccion(tipo, id, maquina))
