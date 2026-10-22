"""Cambiar una viñeta con casilla en su documento: marcarla hecha, o decir quién la hace.

Una viñeta nace sin id: su referencia (`faro:2`) es su lugar en el documento, que cambia cuando el
documento cambia. Por eso, mientras no tenga id, se la busca por su texto —el que mostró quien pide el
cambio, ya limpio de marcas— y se toca solo si hay exactamente una casilla abierta con ese texto. Si el
documento cambió y ya no está, o hay dos iguales, no se escribe nada y se dice.

La primera vez que telar escribe una casilla le deja un id al final de la línea, `<!-- id: c-1a2b3c -->`
(`nuevo_id`), y desde ahí se la busca por ese id: su dirección, `pendiente:c-1a2b3c` (telar.objetos), sigue
sirviendo aunque el documento cambie alrededor. Un id que ya está no se reescribe nunca, sea de telar o no.

Se cambia una línea y nada más; el resto del archivo queda byte a byte como estaba (los finales de
línea `\\r\\n` también). Si no se puede escribir, el documento queda como estaba.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
from pathlib import Path

from telar import lectura


class ErrorDeVineta(Exception):
    """La viñeta no está, o no se puede saber cuál es."""


#: el id que telar le pone a una casilla: `c-` y seis cifras hexadecimales en minúscula (`c-1a2b3c`). La
#: `c` es de casilla, y la forma no se confunde con un id de tarea (`T84`: mayúscula y números, sin guion),
#: así que un `<!-- id: … -->` dice de un vistazo si lo puso telar en una casilla o es el de una tarea. Seis
#: cifras son 16 millones: dentro de un documento, `nuevo_id` evita las que ya están.
FORMA_ID = re.compile(r"c-[0-9a-f]{6}")


def _texto(linea: str) -> str | None:
    """El texto de una línea con casilla, como lo muestra telar; None si no es una casilla."""
    m = lectura._VINETA.match(linea.rstrip("\r\n"))  # el `\r` de un final `\r\n` no es del texto
    if not m or m.group(1) is None:
        return None
    return lectura.marcas(lectura.limpiar(m.group(2)))[0]


def id_de(linea: str) -> str:
    """El id de una casilla (`<!-- id: … -->`), o "" si su línea no tiene."""
    m = lectura.ID_CASILLA.search(linea)
    return m.group(1) if m else ""


def _abierta(linea: str) -> bool:
    return lectura._VINETA.match(linea).group(1).lower() != "x"


def buscar(lineas: list[str], texto: str, *, abierta: bool = True) -> int:
    """El índice de la única casilla (abierta, salvo que se diga) cuyo texto es `texto`."""
    hallados = []
    for i, linea in enumerate(lineas):
        if _texto(linea) != texto:
            continue
        if abierta and not _abierta(linea):
            continue
        hallados.append(i)
    if not hallados:
        raise ErrorDeVineta(f"no encuentro la casilla «{texto[:60]}»: el documento cambió, o ya está hecha")
    if len(hallados) > 1:
        raise ErrorDeVineta(f"hay {len(hallados)} casillas con el texto «{texto[:60]}»: ábrelo y elige a mano")
    return hallados[0]


def buscar_id(lineas: list[str], ident: str, *, abierta: bool = True) -> int:
    """El índice de la casilla con el id `ident`. Dos con el mismo id (una línea copiada con su comentario) no
    se adivinan: se dice, para que alguien le borre el id a la copia."""
    hallados = [i for i, linea in enumerate(lineas) if _texto(linea) is not None and id_de(linea) == ident]
    if not hallados:
        raise ErrorDeVineta(f"no encuentro la casilla con el id {ident}: la borraron, o le borraron el id")
    if len(hallados) > 1:
        raise ErrorDeVineta(f"hay {len(hallados)} casillas con el id {ident}: ábrelo y bórrale el id a las copias")
    if abierta and not _abierta(lineas[hallados[0]]):
        raise ErrorDeVineta(f"la casilla {ident} ya está hecha")
    return hallados[0]


def nuevo_id(contenido: str) -> str:
    """Un id de casilla (`FORMA_ID`) que no esté ya en `contenido`, en ninguna línea."""
    usados = {x.lower() for x in lectura.ID_CASILLA.findall(contenido)}
    while True:
        ident = f"c-{secrets.token_hex(3)}"
        if ident not in usados:
            return ident


def con_id(linea: str, ident: str) -> str:
    """La misma línea con `<!-- id: … -->` al final (antes del salto de línea). Si ya tiene uno, tal cual."""
    if id_de(linea):
        return linea
    fin = linea[len(linea.rstrip("\r\n")):]
    return linea.rstrip("\r\n").rstrip(" \t") + f" <!-- id: {ident} -->" + fin


def hecha(linea: str) -> str:
    """La misma línea con la casilla marcada: `[ ]` o `[>]` pasa a `[x]`."""
    return re.sub(r"\[[ >~]\]", "[x]", linea, count=1)


#: lo que dice quién hace una viñeta: `@owner(…)` y sus sinónimos, con la flecha que a veces los anuncia
_QUIEN_MARCA = re.compile(r"\s*(?:->|→)?\s*@(owner|due[nñ]o|responsable|para)\([^)]*\)", re.I)


def con_responsable(linea: str, nombre: str) -> str:
    """La misma línea diciendo que la hace `nombre` (`@owner(nombre)` al final, antes del id de la casilla
    y del salto de línea), sin lo que decía antes: ni otro `@owner(…)`, ni `@para(…)`, ni «@Nombre:» al
    comienzo. `nombre` vacío o «none» la deja sin responsable."""
    fin = linea[len(linea.rstrip("\r\n")):]
    cuerpo = linea.rstrip("\r\n")
    # el id, si cierra la línea, se queda cerrándola: no se mueve ni se reescribe
    cola = ""
    if (i := lectura.ID_CASILLA.search(cuerpo)) and not cuerpo[i.end():].strip():
        cuerpo, cola = cuerpo[:i.start()], " " + cuerpo[i.start():].rstrip()
    cuerpo = _QUIEN_MARCA.sub("", cuerpo)
    m = lectura._VINETA.match(cuerpo)
    if m and m.group(2):
        inicio = m.start(2)
        sin_quien = re.sub(r"^@[A-ZÁÉÍÓÚÑ][\w.'-]*(?:\s+[A-ZÁÉÍÓÚÑ][\w.'-]*){0,3}\s*:\s+", "", cuerpo[inicio:])
        cuerpo = cuerpo[:inicio] + sin_quien
    cuerpo = cuerpo.rstrip()
    nombre = nombre.strip()
    if nombre and nombre.lower() != "none":
        cuerpo += f" @owner({nombre})"
    return cuerpo + cola + fin


def _leer(documento: Path) -> str:
    """El documento tal cual: sin traducir los finales de línea (`read_text` pasa `\\r\\n` a `\\n`)."""
    try:
        return documento.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        raise ErrorDeVineta(f"{documento.name} no está en UTF-8: no lo toco") from e


def _lineas(contenido: str) -> list[str]:
    """Las líneas con su final (`\\n` o `\\r\\n`). Se parte solo en `\\n`: `splitlines` también parte en
    caracteres que en un documento son texto (U+2028, el salto de página), y la línea n sería otra."""
    partes = contenido.split("\n")
    return [p + "\n" for p in partes[:-1]] + ([partes[-1]] if partes[-1] else [])


def _guardar(documento: Path, contenido: str) -> None:
    """Escribe a un temporal al lado y lo renombra: un corte no deja medio archivo, y si algo falla el
    documento queda como estaba (y el temporal no queda)."""
    tmp = documento.with_name(f".{documento.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(contenido)
        try:
            shutil.copymode(documento, tmp)
        except OSError:
            pass  # sin los permisos de antes, pero con el contenido bien
        os.replace(tmp, documento)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def escribir(documento: Path, cambio, *, texto: str = "", id: str = "", abierta: bool = True,
             estable: bool = True) -> tuple[int, str]:
    """Aplica `cambio` (línea → línea) a una casilla de `documento` y lo guarda. (número de línea desde 1,
    id de la casilla, o "" si no tiene).

    Con `id`, la casilla es la que tiene ese id, y si se da `texto` tiene que seguir diciendo eso; sin `id`,
    la única con ese `texto`. Con `estable`, una casilla sin id que se cambia recibe uno (`nuevo_id`), en la
    misma escritura. Si el cambio no cambia nada, no se escribe (ni se pone el id)."""
    documento = documento.resolve()  # un enlace se escribe en su destino, no se reemplaza por un archivo
    contenido = _leer(documento)
    lineas = _lineas(contenido)
    if id:
        i = buscar_id(lineas, id, abierta=abierta)
        if texto and _texto(lineas[i]) != texto:
            raise ErrorDeVineta(f"la casilla {id} ya no dice «{texto[:60]}»: el documento cambió, vuelve a mirarlo")
    else:
        i = buscar(lineas, texto, abierta=abierta)
    nueva = cambio(lineas[i])
    ident = id_de(lineas[i])
    if nueva != lineas[i]:
        if estable and not ident:
            ident = nuevo_id(contenido)
            nueva = con_id(nueva, ident)
        lineas[i] = nueva
        _guardar(documento, "".join(lineas))
    return i + 1, ident


def cambiar(documento: Path, texto: str, cambio, *, abierta: bool = True) -> int:
    """Como `escribir`, por el texto y sin ponerle id: el número de línea (desde 1)."""
    return escribir(documento, cambio, texto=texto, abierta=abierta, estable=False)[0]


def linea(documento: Path, texto: str, *, id: str = "") -> int:
    """El número de línea (desde 1) de la casilla `texto` (o la del id `id`), abierta o hecha."""
    lineas = _lineas(_leer(documento))
    if id:
        return buscar_id(lineas, id, abierta=False) + 1
    return buscar(lineas, texto, abierta=False) + 1
