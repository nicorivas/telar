"""El estado de las iniciativas (el trabajo propio, sin cliente: las unidades que un modo llama `iniciativas`), con el
vocabulario que declara `[iniciativas]` de la configuración, y cambiarlo en su ficha.

    from telar import iniciativas
    iniciativas.canonico(config.iniciativas, "Activo")       # ("en curso", True): un sinónimo vale como el suyo
    iniciativas.fuente(config.iniciativas, frontmatter)      # la fuente que manda su estado («Sheet»), o ""
    iniciativas.escribir_estado(documento, "en pausa", "2026-11-18")

El vocabulario es cerrado: cambiar el estado desde telar escribe uno de `estados`. Lo que ya está escrito puede ser un
sinónimo (`sinonimos`: «activo» vale como «en curso»), que se muestra y se cuenta como el suyo sin reescribir el
archivo, o algo que no está en el vocabulario, que se muestra tal cual, marcado. Una ficha dice de dónde sale su estado
con `estado_fuente:` (`sheet`: una planilla que la sincroniza); esas no se cambian aquí, las manda la otra fuente, y
`fuentes` solo dice cómo se nombra cada una. Una ficha también puede decir por qué está en su estado (`estado_nota:`).

Escribir toca dos líneas del frontmatter de la ficha, `estado:` y `estado_desde:` (la fecha del cambio), y nada más
(`estado_nota:` y `estado_fuente:` quedan como estaban):
el resto del archivo queda byte a byte como estaba (los comentarios, el orden de los campos, las comillas de cada
valor, los finales de línea). Si no tiene esas líneas, se agregan al final del frontmatter (o tras `estado:`); si no
tiene frontmatter, se le pone uno arriba con las dos. Se escribe como `telar.vinetas` (a un temporal y se renombra; un
archivo de solo lectura no se toca) y sin commitear: el repositorio de la ficha tiene su propio flujo.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

#: las clases de estado, que dicen cómo se dibuja cada uno (el círculo y su color, en la página): las de una iniciativa
#: de punta a punta. Un estado del vocabulario es de la que declare `clases`, o de la que se deduce de su nombre
#: (`clase_de`); si no se deduce, de ninguna, y se dibuja neutro.
CLASES = ("idea", "preparacion", "curso", "pausa", "terminada", "descartada")


class ErrorDeEstado(Exception):
    """El estado no se puede escribir en esa ficha (su frontmatter no lo deja, o el archivo no se puede tocar)."""


def normalizar(texto: str) -> str:
    """Para comparar: sin tildes ni mayúsculas, y los espacios de más en uno («En  Curso» = «en curso»). La misma regla
    que `normalizar` de la página (estilo.ts), más los espacios."""
    sin = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if not 0x300 <= ord(c) <= 0x36F)
    return " ".join(sin.lower().split())


def canonico(ini, escrito: str) -> tuple[str, bool]:
    """(cómo se muestra y se cuenta, si es del vocabulario). Uno del vocabulario, con la forma de la configuración; un
    sinónimo, el suyo; lo demás, tal cual (y False). Sin vocabulario, todo tal cual y True: no hay de qué estar fuera."""
    t = str(escrito or "").strip()
    if not t or not ini.estados:
        return t, True
    n = normalizar(t)
    for e in ini.estados:
        if normalizar(e) == n:
            return e, True
    for de, a in ini.sinonimos:
        if normalizar(de) == n:
            return a, True
    return t, False


def del_vocabulario(ini, pedido: str) -> str | None:
    """El estado del vocabulario que se pidió (o el de un sinónimo), con la forma de la configuración; None si no es."""
    valor, dentro = canonico(ini, pedido)
    return valor if dentro and valor and ini.estados else None


def fuente(ini, frontmatter: dict) -> str:
    """La fuente externa que manda el estado de una iniciativa: su `estado_fuente`, con el nombre que le da `fuentes`
    («sheet» → «Sheet»; uno que `fuentes` no nombra, tal cual). "" si no dice: su estado se cambia aquí."""
    escrito = str(frontmatter.get("estado_fuente", "") or "").strip()
    if not escrito:
        return ""
    n = normalizar(escrito)
    return next((nombre for de, nombre in ini.fuentes if normalizar(de) == n), escrito)


def arquetipos(config) -> set[str]:
    """Los arquetipos que algún modo llama iniciativas (`iniciativas` de `[modos.<n>]`, con lo heredado), en minúsculas."""
    from telar import modos

    salida: set[str] = set()
    for m in modos.todos(config):
        salida.update(x.strip().lower() for x in str(m["valores"].get("iniciativas", "") or "").split(",") if x.strip())
    return salida


def para_la_pagina(ini) -> dict:
    """Lo que la página necesita para mostrar y cambiar los estados (`GET /proyectos`, `iniciativas`)."""
    return {
        "estados": list(ini.estados),
        "sinonimos": dict(ini.sinonimos),
        "clases": dict(ini.clases),
        "fuentes": dict(ini.fuentes),
    }


# ── escribir en la ficha ───────────────────────────────────────────────────────────────────────────────────────────

#: una línea `clave: valor` de primer nivel (sin sangría), como la lee telar.ordenes.proyectos.frontmatter_de
_CLAVE = re.compile(r"^([A-Za-z_][\w-]*)[ \t]*:")
#: lo que en YAML no puede ir sin comillas al comienzo de un valor
_INICIO_RARO = set("-?:,[]{}#&*!|>'\"%@`")
#: palabras que YAML no lee como texto
_NO_TEXTO = {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}


def _final(linea: str) -> tuple[str, str]:
    """(la línea sin su final, el final: `\\r\\n`, `\\n` o "")."""
    if linea.endswith("\r\n"):
        return linea[:-2], "\r\n"
    if linea.endswith("\n"):
        return linea[:-1], "\n"
    return linea, ""


def _partir_valor(resto: str) -> tuple[str, str, str]:
    """Lo que sigue a `clave:` y sus espacios: (el valor como está escrito, sus comillas — `"`, `'` o "" —, lo que va
    después: espacios y el comentario). Un valor entre comillas termina en su comilla de cierre; uno sin comillas, en
    el primer « #». Sin valor y con un comentario («estado:   # falta»), el valor es "" y el comentario va después."""
    if resto.startswith("#"):
        return "", "", " " + resto
    if resto[:1] in ('"', "'"):
        q = resto[0]
        i = 1
        while i < len(resto):
            if q == '"' and resto[i] == "\\":
                i += 2
                continue
            if resto[i] == q:
                if q == "'" and resto[i + 1:i + 2] == "'":
                    i += 2
                    continue
                return resto[: i + 1], q, resto[i + 1:]
            i += 1
        return resto, "", ""  # sin cerrar: se trata como sin comillas, entero
    m = re.search(r"[ \t]+#", resto)
    valor = resto[: m.start()] if m else resto
    sin_espacio = valor.rstrip(" \t")
    return sin_espacio, "", resto[len(sin_espacio):]


def _sin_comillas(valor: str, q: str) -> str:
    if not q:
        return valor.strip()
    dentro = valor[1:-1]
    return dentro.replace("''", "'") if q == "'" else dentro.replace('\\"', '"').replace("\\\\", "\\")


def _necesita_comillas(v: str) -> bool:
    if not v or v != v.strip() or v[0] in _INICIO_RARO or v.lower() in _NO_TEXTO:
        return True
    if ": " in v or " #" in v or v.endswith(":") or "\t" in v:
        return True
    return bool(re.fullmatch(r"[-+]?(\d[\d_]*)?\.?\d+([eE][-+]?\d+)?", v))


def _con_comillas(v: str, q: str) -> str:
    """El valor escrito con esas comillas; sin comillas, solo si YAML lo lee como el mismo texto (si no, dobles)."""
    if q == "'":
        return "'" + v.replace("'", "''") + "'"
    if q == '"' or _necesita_comillas(v):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


def _reemplazar(linea: str, valor: str, clave: str) -> tuple[str, str]:
    """La línea `clave: …` con otro valor, y el que tenía. Queda como estaba lo demás: cómo se escribió la clave y
    sus espacios, las comillas del valor, el comentario del final y el final de línea. ErrorDeEstado si su valor no es
    de una línea (un bloque `|`, una lista o un mapa)."""
    cuerpo, fin = _final(linea)
    m = re.match(rf"^({re.escape(clave)}[ \t]*:[ \t]*)(.*)$", cuerpo)
    if not m:  # pragma: no cover - quien llama ya la reconoció
        raise ErrorDeEstado(f"{clave}: no es una línea «{clave}: valor»")
    prefijo, resto = m.groups()
    escrito, q, despues = _partir_valor(resto)
    if not q and escrito[:1] in ("|", ">", "[", "{", "&", "*", "!"):
        raise ErrorDeEstado(f"`{clave}:` de su frontmatter no es un valor de una línea ({escrito[:20]}…): no lo toco")
    if not prefijo.endswith((" ", "\t")):
        prefijo += " "
    return prefijo + _con_comillas(valor, q) + despues + fin, _sin_comillas(escrito, q)


def con_estado(texto: str, estado: str, desde: str) -> tuple[str, str]:
    """El texto de una ficha con `estado:` y `estado_desde:` cambiados (o agregados), y el estado que decía antes ("" si
    no decía). Pura: no lee ni escribe. ErrorDeEstado si su frontmatter no deja escribirlo."""
    bom = "﻿" if texto.startswith("﻿") else ""
    cuerpo = texto[len(bom):]
    partes = cuerpo.split("\n")
    lineas = [p + "\n" for p in partes[:-1]] + ([partes[-1]] if partes[-1] else [])
    fin = "\r\n" if lineas and lineas[0].endswith("\r\n") else "\n"
    cierre = None
    if lineas and _final(lineas[0])[0].rstrip(" \t") == "---":
        cierre = next((i for i in range(1, len(lineas)) if _final(lineas[i])[0].rstrip(" \t") == "---"), None)
        if cierre is None:
            raise ErrorDeEstado("su frontmatter no se cierra (falta el `---` de abajo): no lo toco")
    if cierre is None:
        # sin frontmatter: uno nuevo, arriba, con las dos líneas
        nuevo = f"---{fin}estado: {_con_comillas(estado, '')}{fin}estado_desde: {desde}{fin}---{fin}"
        return bom + nuevo + cuerpo, ""

    def buscar(clave: str) -> int | None:
        for i in range(1, cierre):
            m = _CLAVE.match(lineas[i])
            if m and m.group(1) == clave:
                # un valor vacío con líneas con sangría debajo es una lista o un mapa: no es de una línea
                vacio = not _final(lineas[i])[0][m.end():].split("#", 1)[0].strip()
                siguiente = lineas[i + 1] if i + 1 < cierre else ""
                if vacio and siguiente[:1] in (" ", "\t", "-"):
                    raise ErrorDeEstado(f"`{clave}:` de su frontmatter no es un valor de una línea: no lo toco")
                return i
        return None

    i_estado, i_desde = buscar("estado"), buscar("estado_desde")
    antes = ""
    if i_estado is not None:
        lineas[i_estado], antes = _reemplazar(lineas[i_estado], estado, "estado")
    if i_desde is not None:
        lineas[i_desde], _ = _reemplazar(lineas[i_desde], desde, "estado_desde")
    # las que faltan: `estado_desde:` justo después de `estado:`; `estado:` justo antes de `estado_desde:`; las dos, al
    # final del frontmatter. Con el final de línea de la ficha
    nueva_estado = f"estado: {_con_comillas(estado, '')}{fin}"
    nueva_desde = f"estado_desde: {desde}{fin}"
    if i_estado is not None and i_desde is None:
        lineas.insert(i_estado + 1, nueva_desde)
    elif i_estado is None and i_desde is not None:
        lineas.insert(i_desde, nueva_estado)
    elif i_estado is None and i_desde is None:
        # la línea de antes del cierre puede no terminar en un final (un frontmatter sin nada más): no pasa, el cierre
        # siempre viene después de un `\n`
        lineas[cierre:cierre] = [nueva_estado, nueva_desde]
    return bom + "".join(lineas), antes


def escribir_estado(documento: Path, estado: str, desde: str) -> str:
    """Escribe `estado:` y `estado_desde:` en el frontmatter de `documento` (`con_estado`), sin commitear. El estado que
    decía antes. Si no cambia nada, no se escribe. ErrorDeEstado si no se puede (el frontmatter, la codificación);
    PermissionError si el archivo es de solo lectura."""
    from telar import vinetas

    documento = documento.resolve()  # un enlace se escribe en su destino
    with vinetas._ESCRIBIENDO:
        try:
            contenido = vinetas._leer(documento)
        except vinetas.ErrorDeVineta as e:
            raise ErrorDeEstado(str(e)) from e
        nuevo, antes = con_estado(contenido, estado, desde)
        if nuevo != contenido:
            vinetas._guardar(documento, nuevo)
    return antes
