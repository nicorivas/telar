"""Volver a encontrar un trozo de texto comentado después de que el documento cambió (telar.comentarios).

Guardar «línea 42» no sirve: en cuanto alguien reescribe el documento, las líneas se corren. Se guarda la **cita** (el
texto comentado) más hasta 48 caracteres de contexto a cada lado, y aquí se la busca de nuevo. Cinco intentos, del más
seguro al más desesperado:

1. **exacto** — la cita aparece una sola vez.
2. **contexto** — aparece varias veces; gana la que conserva el mismo vecindario.
3. **normalizado** — aparece si se colapsan los espacios (un párrafo re-envuelto).
4. **aproximado** — el prefijo y el sufijo más largos que sobreviven, verificados por parecido de bigramas (umbral 0,6).
5. **vecindario** — la cita se reescribió entera pero lo que la rodeaba sigue ahí: el comentario se ancla en el hueco
   (el caso de «arreglé justo lo que me pediste»).

Si los cinco fallan, el hilo queda **sin ancla** y se dice: no se adivina un lugar. Cada resolución viaja con su método
y su confianza, para que quien la muestra diga cuándo el ancla es una certeza y cuándo una apuesta.

Es el mismo algoritmo, con las mismas constantes, que el de la extensión de editor que escribe este formato de archivo
(docs/contratos.md, «Los comentarios de un archivo»): dos implementaciones que dijeran cosas distintas del mismo
archivo serían peor que ninguna. Una diferencia, a propósito: aquí se trabaja en puntos de código (lo que indexa un
`str`), y el archivo guarda las posiciones como las cuenta JavaScript (unidades UTF-16); `a_utf16` y `de_utf16`
convierten en el borde. Las posiciones del archivo son una pista, no una verdad: solo desempatan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["CONTEXTO", "Ancla", "Resolucion", "a_utf16", "de_utf16", "derivar", "linea_de", "recortar_blancos",
           "resolver", "similitud"]

#: los caracteres de contexto que se guardan a cada lado de la cita
CONTEXTO = 48
#: bajo esta similitud, una coincidencia aproximada se descarta
UMBRAL_APROXIMADO = 0.6
#: bajo este largo, una cita no tiene material para el paso 4
MINIMO_APROXIMADO = 12
#: los caracteres con contenido que debe tener un lado para servir de referencia (paso 5)
MINIMO_VECINDARIO = 10

_BLANCO = re.compile(r"\s")
_BLANCOS = re.compile(r"\s+")


@dataclass
class Ancla:
    """Dónde vive un comentario: la cita y su vecindario. `inicio` y `fin`, en puntos de código del texto de cuando se
    ancló (una pista)."""

    cita: str
    antes: str = ""
    despues: str = ""
    inicio: int = 0
    fin: int = 0


@dataclass
class Resolucion:
    """Dónde está hoy un ancla: el tramo (en puntos de código), cómo se encontró y cuánto se le cree (0 a 1)."""

    inicio: int
    fin: int
    metodo: str
    confianza: float


# ── las posiciones como las cuenta JavaScript ─────────────────────────────────────────────────────────────────────


def a_utf16(texto: str, i: int) -> int:
    """La posición `i` (en puntos de código) contada en unidades UTF-16, como la guarda el archivo."""
    i = max(0, min(i, len(texto)))
    return i + sum(1 for c in texto[:i] if ord(c) > 0xFFFF)


def de_utf16(texto: str, u: int) -> int:
    """La posición `u` (en unidades UTF-16) contada en puntos de código. Una que cae en medio de un carácter de dos
    unidades va al principio de ese carácter."""
    if u <= 0:
        return 0
    unidades = 0
    for i, c in enumerate(texto):
        ancho = 2 if ord(c) > 0xFFFF else 1
        if unidades + ancho > u:
            return i
        unidades += ancho
    return len(texto)


# ── tomar el ancla ────────────────────────────────────────────────────────────────────────────────────────────────


def recortar_blancos(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    """Encoge un tramo hasta que empiece y termine en texto de verdad: al seleccionar arrastrando, el mouse casi
    siempre se lleva el salto de línea del final, y un ancla que empieza o termina en espacios es peor ancla. Un tramo
    todo blanco vuelve intacto: no es tarea de esta función decidir que no hay nada que comentar."""
    i = max(0, min(inicio, len(texto)))
    f = max(i, min(fin, len(texto)))
    while i < f and _BLANCO.match(texto[i]):
        i += 1
    while f > i and _BLANCO.match(texto[f - 1]):
        f -= 1
    return (i, f) if i < f else (inicio, fin)


def derivar(texto: str, inicio: int, fin: int) -> Ancla:
    """La foto del ancla: la cita y su vecindario, tal como están ahora."""
    i = max(0, min(inicio, len(texto)))
    f = max(i, min(fin, len(texto)))
    return Ancla(cita=texto[i:f], antes=texto[max(0, i - CONTEXTO):i], despues=texto[f:f + CONTEXTO], inicio=i, fin=f)


# ── volver a encontrarla ──────────────────────────────────────────────────────────────────────────────────────────


def resolver(texto: str, ancla: Ancla) -> Resolucion | None:
    """Dónde está hoy el ancla, o None si ya no se puede afirmar."""
    cita = ancla.cita
    if not cita:  # un ancla sin texto (una posición): se respeta, acotada
        i = max(0, min(ancla.inicio, len(texto)))
        return Resolucion(i, i, "exacto", 1.0)
    exactas = ocurrencias(texto, cita)
    if len(exactas) == 1:
        return Resolucion(exactas[0], exactas[0] + len(cita), "exacto", 1.0)
    if len(exactas) > 1:
        mejor = _mejor_por_contexto(texto, cita, ancla, exactas)
        return Resolucion(mejor, mejor + len(cita), "contexto", 0.9)
    return _normalizado(texto, cita, ancla) or _aproximar(texto, ancla) or _por_vecindario(texto, ancla)


def ocurrencias(texto: str, aguja: str, tope: int = 400) -> list[int]:
    """Todas las posiciones donde aparece `aguja` (también encimadas), hasta un tope."""
    salida: list[int] = []
    if not aguja:
        return salida
    i = texto.find(aguja)
    while i != -1 and len(salida) < tope:
        salida.append(i)
        i = texto.find(aguja, i + 1)
    return salida


def _mejor_por_contexto(texto: str, cita: str, ancla: Ancla, candidatas: list[int]) -> int:
    """Entre varias apariciones idénticas, la que conserva el vecindario: cuántos caracteres de contexto calzan a cada
    lado; la cercanía a la posición vieja solo desempata (vale menos de un punto)."""
    mejor, puntaje_mejor = candidatas[0], float("-inf")
    for i in candidatas:
        antes = texto[max(0, i - CONTEXTO):i]
        despues = texto[i + len(cita):i + len(cita) + CONTEXTO]
        puntaje = _sufijo_comun(antes, ancla.antes) + _prefijo_comun(despues, ancla.despues) + 1 / (1 + abs(i - ancla.inicio))
        if puntaje > puntaje_mejor:
            mejor, puntaje_mejor = i, puntaje
    return mejor


def _normalizado(texto: str, cita: str, ancla: Ancla) -> Resolucion | None:
    cita_norm = _BLANCOS.sub(" ", cita).strip()
    if len(cita_norm) < 4:
        return None
    norm, mapa = _normalizar_con_mapa(texto)
    halladas = ocurrencias(norm, cita_norm, 50)
    if not halladas:
        return None
    if len(halladas) == 1:
        j = halladas[0]
    else:  # varias: la más cercana a la posición guardada
        j = min(halladas, key=lambda p: abs(mapa[p] - ancla.inicio))
    inicio = mapa[j]
    fin = mapa[j + len(cita_norm) - 1] + 1
    if fin <= inicio:
        return None
    return Resolucion(inicio, fin, "normalizado", 0.85)


def _aproximar(texto: str, ancla: Ancla) -> Resolucion | None:
    """El prefijo y el sufijo más largos de la cita que todavía existen, y que lo de en medio se parezca de verdad a lo
    que se comentó: sin esa verificación, esto anclaría en cualquier parte."""
    cita = ancla.cita
    if len(cita) < MINIMO_APROXIMADO:
        return None
    inicio = _extremo_mas_largo(texto, cita, "prefijo", ancla.inicio)
    fin = _extremo_mas_largo(texto, cita, "sufijo", ancla.fin)
    if inicio is not None and fin is not None and fin > inicio:
        desde, hasta = inicio, fin
    elif inicio is not None:
        desde, hasta = inicio, min(len(texto), inicio + len(cita))
    elif fin is not None:
        desde, hasta = max(0, fin - len(cita)), fin
    else:
        return None
    # un tramo desbocado (el prefijo calzó arriba y el sufijo mucho más abajo) no es la misma frase
    proporcion = (hasta - desde) / len(cita)
    if proporcion < 0.4 or proporcion > 2.5:
        return None
    confianza = similitud(texto[desde:hasta], cita)
    if confianza < UMBRAL_APROXIMADO:
        return None
    return Resolucion(desde, hasta, "aproximado", confianza)


def _por_vecindario(texto: str, ancla: Ancla) -> Resolucion | None:
    """La cita se reescribió entera pero su vecindario sobrevivió: casi siempre, porque se atendió. Con los dos lados,
    el tramo entre ellos; con uno, una marca sin ancho pegada a ese lado, de confianza baja y declarada."""
    izquierda, derecha = ancla.antes[-32:], ancla.despues[:32]
    sirve_izq = len(izquierda.strip()) >= MINIMO_VECINDARIO
    sirve_der = len(derecha.strip()) >= MINIMO_VECINDARIO
    if not sirve_izq and not sirve_der:
        return None
    ventana = max(400, len(ancla.cita) * 3)
    if sirve_izq and sirve_der:
        mejor, dist_mejor = None, float("inf")
        for i in ocurrencias(texto, izquierda, 50):
            inicio = i + len(izquierda)
            j = texto[inicio:inicio + ventana].find(derecha)
            if j == -1:
                continue
            dist = abs(inicio - ancla.inicio)
            if dist < dist_mejor:
                mejor, dist_mejor = Resolucion(inicio, inicio + j, "vecindario", 0.5), dist
        if mejor:
            return mejor
    if sirve_izq:
        i = _mas_cercano([p + len(izquierda) for p in ocurrencias(texto, izquierda, 50)], ancla.inicio)
        if i is not None:
            return Resolucion(i, i, "vecindario", 0.3)
    if sirve_der:
        i = _mas_cercano(ocurrencias(texto, derecha, 50), ancla.fin)
        if i is not None:
            return Resolucion(i, i, "vecindario", 0.3)
    return None


def _mas_cercano(posiciones: list[int], objetivo: int) -> int | None:
    if not posiciones:
        return None
    mejor, dist_mejor = posiciones[0], float("inf")
    for p in posiciones:
        if abs(p - objetivo) < dist_mejor:
            mejor, dist_mejor = p, abs(p - objetivo)
    return mejor


def _extremo_mas_largo(texto: str, cita: str, cual: str, objetivo: int) -> int | None:
    """El prefijo (o el sufijo) más largo de `cita` que aparece tal cual en `texto`: el inicio del tramo (prefijo) o
    su fin (sufijo), el más cercano a `objetivo`."""
    n = len(cita) - 1
    while n >= MINIMO_APROXIMADO:
        trozo = cita[:n] if cual == "prefijo" else cita[len(cita) - n:]
        halladas = ocurrencias(texto, trozo, 50)
        if halladas:
            puntos = halladas if cual == "prefijo" else [p + len(trozo) for p in halladas]
            return _mas_cercano(puntos, objetivo)
        n = int(n * 0.75)
    return None


# ── texto ─────────────────────────────────────────────────────────────────────────────────────────────────────────


def _sufijo_comun(a: str, b: str) -> int:
    n = 0
    while n < len(a) and n < len(b) and a[len(a) - 1 - n] == b[len(b) - 1 - n]:
        n += 1
    return n


def _prefijo_comun(a: str, b: str) -> int:
    n = 0
    while n < len(a) and n < len(b) and a[n] == b[n]:
        n += 1
    return n


def _normalizar_con_mapa(texto: str) -> tuple[str, list[int]]:
    """Colapsa los espacios y anota, para cada carácter del texto normalizado, de qué posición del original vino: se
    busca en el normalizado y se devuelve la posición en el archivo de verdad."""
    salida: list[str] = []
    mapa: list[int] = []
    en_espacio = False
    for i, c in enumerate(texto):
        if _BLANCO.match(c):
            if en_espacio:
                continue
            en_espacio = True
            salida.append(" ")
        else:
            en_espacio = False
            salida.append(c)
        mapa.append(i)
    return "".join(salida), mapa


def similitud(a: str, b: str) -> float:
    """El coeficiente de Dice sobre los bigramas de caracteres: 1, idénticos; 0, nada en común."""
    if a == b:
        return 1.0
    if len(a) < 2 or len(b) < 2:
        return 0.0
    bolsa: dict[str, int] = {}
    for i in range(len(a) - 1):
        g = a[i:i + 2]
        bolsa[g] = bolsa.get(g, 0) + 1
    comunes = 0
    for i in range(len(b) - 1):
        g = b[i:i + 2]
        if bolsa.get(g, 0) > 0:
            bolsa[g] -= 1
            comunes += 1
    return 2 * comunes / (len(a) - 1 + len(b) - 1)


def linea_de(texto: str, i: int) -> int:
    """El número de línea (desde 1) de la posición `i`."""
    return texto.count("\n", 0, max(0, min(i, len(texto)))) + 1
