"""Cambiar una viñeta con casilla en su documento: marcarla hecha, o decir quién la hace.

Una viñeta no tiene id: su referencia (`faro:2`) es su lugar en el documento, que cambia cuando el
documento cambia. Por eso aquí se la busca por su texto —el que mostró quien pide el cambio, ya
limpio de marcas— y se toca solo si hay exactamente una casilla abierta con ese texto. Si el
documento cambió y ya no está, o hay dos iguales, no se escribe nada y se dice.

Se cambia una línea y nada más; el resto del archivo queda byte a byte como estaba.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from telar import lectura


class ErrorDeVineta(Exception):
    """La viñeta no está, o no se puede saber cuál es."""


def _texto(linea: str) -> str | None:
    """El texto de una línea con casilla, como lo muestra telar; None si no es una casilla."""
    m = lectura._VINETA.match(linea)
    if not m or m.group(1) is None:
        return None
    return lectura.marcas(lectura.limpiar(m.group(2)))[0]


def buscar(lineas: list[str], texto: str, *, abierta: bool = True) -> int:
    """El índice de la única casilla (abierta, salvo que se diga) cuyo texto es `texto`."""
    hallados = []
    for i, linea in enumerate(lineas):
        if _texto(linea) != texto:
            continue
        marca = lectura._VINETA.match(linea).group(1).lower()
        if abierta and marca == "x":
            continue
        hallados.append(i)
    if not hallados:
        raise ErrorDeVineta(f"no encuentro la casilla «{texto[:60]}»: el documento cambió, o ya está hecha")
    if len(hallados) > 1:
        raise ErrorDeVineta(f"hay {len(hallados)} casillas con el texto «{texto[:60]}»: ábrelo y elige a mano")
    return hallados[0]


def hecha(linea: str) -> str:
    """La misma línea con la casilla marcada: `[ ]` o `[>]` pasa a `[x]`."""
    return re.sub(r"\[[ >~]\]", "[x]", linea, count=1)


#: lo que dice quién hace una viñeta: `@owner(…)` y sus sinónimos, con la flecha que a veces los anuncia
_QUIEN_MARCA = re.compile(r"\s*(?:->|→)?\s*@(owner|due[nñ]o|responsable|para)\([^)]*\)", re.I)


def con_responsable(linea: str, nombre: str) -> str:
    """La misma línea diciendo que la hace `nombre` (`@owner(nombre)` al final, antes de un salto de
    línea), sin lo que decía antes: ni otro `@owner(…)`, ni `@para(…)`, ni «@Nombre:» al comienzo.
    `nombre` vacío o «none» la deja sin responsable."""
    fin = linea[len(linea.rstrip("\r\n")):]
    cuerpo = _QUIEN_MARCA.sub("", linea.rstrip("\r\n"))
    m = lectura._VINETA.match(cuerpo)
    if m and m.group(2):
        inicio = m.start(2)
        sin_quien = re.sub(r"^@[A-ZÁÉÍÓÚÑ][\w.'-]*(?:\s+[A-ZÁÉÍÓÚÑ][\w.'-]*){0,3}\s*:\s+", "", cuerpo[inicio:])
        cuerpo = cuerpo[:inicio] + sin_quien
    cuerpo = cuerpo.rstrip()
    nombre = nombre.strip()
    if nombre and nombre.lower() != "none":
        cuerpo += f" @owner({nombre})"
    return cuerpo + fin


def cambiar(documento: Path, texto: str, cambio, *, abierta: bool = True) -> int:
    """Aplica `cambio` (línea → línea) a la casilla `texto` de `documento` y lo guarda. Devuelve el
    número de línea (desde 1). Escribe a un temporal y lo renombra: un corte no deja medio archivo."""
    contenido = documento.read_text(encoding="utf-8")
    lineas = contenido.splitlines(keepends=True)
    i = buscar(lineas, texto, abierta=abierta)
    nueva = cambio(lineas[i])
    if nueva != lineas[i]:
        lineas[i] = nueva
        tmp = documento.with_name(f".{documento.name}.{os.getpid()}.tmp")
        tmp.write_text("".join(lineas), encoding="utf-8")
        os.replace(tmp, documento)
    return i + 1


def linea(documento: Path, texto: str) -> int:
    """El número de línea (desde 1) de la casilla `texto`, abierta o hecha."""
    lineas = documento.read_text(encoding="utf-8").splitlines()
    return buscar(lineas, texto, abierta=False) + 1
