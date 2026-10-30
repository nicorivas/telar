"""Un registro: un archivo markdown con frontmatter de campos sueltos (docs/propuestas/productos.md).

    ---
    titulo: Sección de gestión del cambio en la página de aterrizaje
    estado: idea
    valor: alto
    ---
    Lo que se propone y por qué.

    ## Historia
    - 2026-10-29 16:40 [creada]

Los campos no están fijos: son los que diga el frontmatter, en su orden, y quien los usa decide cuáles le importan
(las ideas de un producto, `telar.productos`). Es el formato de un tipo que declara cada repositorio, no telar.

Cumple las dos promesas de un formato (telar.tipos): leer y escribir sin cambios da los mismos bytes, y un cambio
toca solo las líneas de sus campos (y agrega una línea a la historia). Una línea del frontmatter que no es `clave:
valor` (un comentario, una lista) se conserva y no entra a los campos.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from telar.tipos import ErrorDeFormato

__all__ = ["Registro", "REGISTRO", "cambiar", "anotar", "nuevo"]

_CAMPO = re.compile(r"^([A-Za-z_][\w-]*)[ \t]*:[ \t]?(.*)$")
_HISTORIA = re.compile(r"^##\s+Historia\s*$", re.M)


class Registro(BaseModel):
    id: str = ""
    #: los campos del frontmatter, en su orden, como texto (sin comillas)
    campos: dict[str, str] = Field(default_factory=dict)
    #: lo que va entre el frontmatter y la historia, tal cual
    cuerpo: str = ""
    #: las líneas de la historia, sin el «- »
    historia: list[str] = Field(default_factory=list)


def _valor(crudo: str) -> str:
    v = crudo.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    # un comentario al final («idea   # idea · evaluando»), solo si no va entre comillas
    return re.sub(r"\s+#.*$", "", v)


def _escrito(valor: str) -> str:
    """Un valor como se escribe: entre comillas si vacío o si se leería distinto."""
    if valor == "" or valor != valor.strip() or re.search(r"(^[\"'#\[{>|*&!%@`-])|(:\s)|(\s#)", valor):
        return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return valor


def _partes(texto: str) -> tuple[str, list[str], str, str]:
    """(el salto de línea, las líneas del frontmatter, el resto después del cierre, lo de antes del primer ---)."""
    nl = "\r\n" if "\r\n" in texto else "\n"
    lineas = texto.split(nl)
    inicio = 1 if lineas and lineas[0].lstrip("﻿") == "---" else None
    if inicio is None:
        return nl, [], texto, ""
    for i in range(1, len(lineas)):
        if lineas[i] == "---":
            return nl, lineas[1:i], nl.join(lineas[i + 1:]), lineas[0]
    raise ErrorDeFormato("el frontmatter no se cierra (falta la línea ---)")


class _Formato:
    def leer(self, texto: str, id: str = "") -> Registro:
        nl, fm, resto, _ = _partes(texto)
        campos: dict[str, str] = {}
        for linea in fm:
            m = _CAMPO.match(linea)
            if m and m.group(1) not in campos:
                campos[m.group(1)] = _valor(m.group(2))
        cuerpo, historia = resto, []
        h = _HISTORIA.search(resto.replace(nl, "\n"))
        if h:
            normal = resto.replace(nl, "\n")
            cuerpo = normal[:h.start()].replace("\n", nl)
            historia = [x[2:].rstrip() for x in normal[h.end():].split("\n") if x.startswith("- ")]
        return Registro(id=id, campos=campos, cuerpo=cuerpo.strip(), historia=historia)

    def escribir(self, texto: str, antes: Registro, despues: Registro) -> str:
        nl, fm, resto, abre = _partes(texto)
        if not abre:
            abre, fm = "---", []
        cambiados = {k: v for k, v in despues.campos.items() if antes.campos.get(k) != v}
        nuevas = list(fm)
        for k, v in cambiados.items():
            i = next((j for j, linea in enumerate(nuevas) if (m := _CAMPO.match(linea)) and m.group(1) == k), None)
            if i is None:
                nuevas.append(f"{k}: {_escrito(v)}")
            else:
                nuevas[i] = f"{k}: {_escrito(v)}"
        if despues.cuerpo != antes.cuerpo:
            raise ErrorDeFormato("el cuerpo de un registro no se cambia con una acción")
        agregadas = despues.historia[len(antes.historia):]
        if despues.historia[:len(antes.historia)] != antes.historia:
            raise ErrorDeFormato("la historia de un registro solo crece")
        if agregadas:
            lineas = [f"- {x}" for x in agregadas]
            normal = resto.replace(nl, "\n")
            if _HISTORIA.search(normal):
                normal = normal.rstrip("\n") + "\n" + "\n".join(lineas) + "\n"
            else:
                normal = normal.rstrip("\n") + "\n\n## Historia\n" + "\n".join(lineas) + "\n"
            resto = normal.replace("\n", nl)
        return nl.join([abre, *nuevas, "---"]) + nl + resto

    def nuevo(self, r: Registro) -> str:
        texto = "\n".join(["---", *(f"{k}: {_escrito(v)}" for k, v in r.campos.items()), "---"]) + "\n"
        cuerpo = r.cuerpo.strip()
        if cuerpo:
            texto += cuerpo + "\n"
        if r.historia:
            texto += ("\n" if cuerpo else "") + "## Historia\n" + "".join(f"- {x}\n" for x in r.historia)
        return texto


REGISTRO = _Formato()


def _hora() -> str:
    from datetime import datetime

    return f"{datetime.now():%Y-%m-%d %H:%M}"


def cambiar(r: Registro, campos: dict[str, str], nota: str = "") -> Registro:
    """Cambia unos campos, y anota en la historia qué cambió («estado: idea → priorizada»)."""
    nuevos = {k: str(v) for k, v in campos.items() if r.campos.get(k) != str(v)}
    if not nuevos and not nota:
        return r
    dicho = ", ".join(f"{k}: {r.campos.get(k, '') or '—'} → {v or '—'}" for k, v in nuevos.items())
    linea = f"{_hora()} [cambio] {dicho}" + (f" · {nota}" if nota and dicho else nota)
    return r.model_copy(update={"campos": {**r.campos, **nuevos}, "historia": [*r.historia, linea]})


def anotar(r: Registro, texto: str) -> Registro:
    texto = " ".join(texto.split())
    if not texto:
        return r
    return r.model_copy(update={"historia": [*r.historia, f"{_hora()} [nota] {texto}"]})


def nuevo(campos: dict[str, str], cuerpo: str = "", como: str = "creada") -> Registro:
    return Registro(campos={k: str(v) for k, v in campos.items()}, cuerpo=cuerpo.strip(), historia=[f"{_hora()} [{como}]"])
