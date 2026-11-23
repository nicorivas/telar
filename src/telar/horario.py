"""El horario de un mundo (`[mundos.<nombre>] horario`, docs/configuracion.md): días y horas en que rige.

    from telar import horario
    t = horario.leer_tramo("lun-vie 9:00-19:00")     # Tramo(dias=(1, 2, 3, 4, 5), desde=540, hasta=1140, …)
    horario.leer_horario(["lun-vie 9-13", "lun-vie 14-19"])

Un tramo dice los días y las horas, y cualquiera de los dos puede faltar: «lun-vie 9:00-19:00», «sáb-dom» (el día
entero), «lun,mié,vie 8:30-12», «20:00-23:00» (todos los días), «todos». Un día se escribe con sus tres primeras letras o
más, con o sin tilde. Un tramo cuya hora de fin es menor que la de inicio pasa la medianoche: «vie 22:00-2:00» es la
noche del viernes y la madrugada del sábado. Lo que no se entiende es un ValueError con lo que se esperaba.

Qué mundo rige a cada hora lo calcula la página, con la hora del navegador (pagina/src/componentes/modos-mundos.ts,
`mundoAhora`, con la misma gramática): aquí se valida y se entrega lo declarado. Si dos horarios se pisan, a esa hora no
rige ninguno de los dos (rige el de `fuera`): `choques` dice dónde, para no escribirlos (⚙ mundos) y para que doctor lo
avise en lo que ya está escrito (la misma cuenta que `choques` de pagina/src/componentes/horario-editor.ts).

    horario.choques({"trabajo": tramos_a, "estudio": tramos_b})
    # [{"mundos": ["trabajo", "estudio"], "dia": 1, "desde": 540, "hasta": 600}]
    horario.decir_choque(c)       # "«trabajo» y «estudio» se pisan el lunes de 9:00 a 10:00"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

__all__ = ["Tramo", "leer_tramo", "leer_horario", "intervalos", "choques", "decir_choque", "hora"]

#: los días por su nombre entero, desde el domingo (0), como `getDay` de la página
DIAS = ("domingo", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado")
#: los días como se dicen, desde el domingo (0)
NOMBRES = ("domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado")
DIA_ENTERO = 24 * 60
SEMANA = 7 * DIA_ENTERO


@dataclass(frozen=True, slots=True)
class Tramo:
    """Los días (0 domingo … 6 sábado) y de qué minuto a qué minuto del día; `texto`, como se declaró."""

    dias: tuple[int, ...]
    desde: int
    hasta: int
    texto: str = ""

    def json(self) -> dict:
        return {"texto": self.texto, "dias": list(self.dias), "desde": self.desde, "hasta": self.hasta}


def _sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c)).lower()


def _dia(t: str, todo: str) -> int:
    n = _sin_tildes(t.strip())
    for i, d in enumerate(DIAS):
        if len(n) >= 3 and d.startswith(n):
            return i
    raise ValueError(f"«{todo}»: «{t}» no es un día (lun, mar, mié, jue, vie, sáb, dom)")


def _hora(t: str, todo: str) -> int:
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", t.strip())
    h, mi = (int(m.group(1)), int(m.group(2) or 0)) if m else (-1, 0)
    if not m or h > 24 or mi > 59 or (h == 24 and mi):
        raise ValueError(f"«{todo}»: «{t}» no es una hora (9, 9:00, 19:30)")
    return h * 60 + mi


_TRAMO = re.compile(r"(?:([^\d]+?))?\s*(\d{1,2}(?::\d{2})?\s*-\s*\d{1,2}(?::\d{2})?)?", re.IGNORECASE)


def leer_tramo(texto: str) -> Tramo:
    """Un tramo como se escribe en la configuración (ver arriba)."""
    t = str(texto).strip()
    m = _TRAMO.fullmatch(t)
    if not t or not m or not (m.group(1) or m.group(2)):
        raise ValueError(f"«{texto}»: se esperaba algo como «lun-vie 9:00-19:00»")
    dias = list(range(7))
    d = (m.group(1) or "").strip()
    if d and _sin_tildes(d) != "todos":
        dias = []
        for parte in (x.strip() for x in d.split(",") if x.strip()):
            a, _, b = parte.partition("-")
            i = _dia(a, texto)
            if not b.strip():
                if "-" in parte:
                    raise ValueError(f"«{texto}»: «{parte}» no es un rango de días")
                dias.append(i)
                continue
            f = _dia(b, texto)
            k = i
            while True:
                dias.append(k)
                if k == f:
                    break
                k = (k + 1) % 7
    desde, hasta = 0, DIA_ENTERO
    if m.group(2):
        a, _, b = m.group(2).partition("-")
        desde, hasta = _hora(a, texto), _hora(b, texto)
        if desde == hasta:
            raise ValueError(f"«{texto}»: el tramo empieza y termina a la misma hora")
    return Tramo(dias=tuple(sorted(set(dias))), desde=desde, hasta=hasta, texto=t)


def leer_horario(valor) -> tuple[Tramo, ...]:
    """`horario`: un texto (un tramo) o una lista de textos."""
    if valor is None:
        return ()
    if isinstance(valor, str):
        return (leer_tramo(valor),)
    if isinstance(valor, list) and all(isinstance(x, str) for x in valor):
        return tuple(leer_tramo(x) for x in valor)
    raise ValueError(f"se esperaba un texto o una lista de textos, llegó {valor!r}")



def hora(minuto: int) -> str:
    """Un minuto del día como se dice: 540 → «9:00», 1440 → «24:00»."""
    return f"{minuto // 60}:{minuto % 60:02d}"


def intervalos(t: Tramo) -> list[tuple[int, int]]:
    """Los minutos de la semana que cubre un tramo (desde el domingo a las 0:00), en intervalos [a, b) que no pasan del
    sábado a medianoche: uno que pasa la medianoche del sábado sigue el domingo de madrugada."""
    salida = []
    for d in t.dias:
        inicio = d * DIA_ENTERO
        if t.desde < t.hasta:
            salida.append((inicio + t.desde, inicio + t.hasta))
            continue
        salida.append((inicio + t.desde, inicio + DIA_ENTERO))
        if t.hasta:
            siguiente = ((d + 1) % 7) * DIA_ENTERO
            salida.append((siguiente, siguiente + t.hasta))
    return salida


def choques(por_mundo: dict) -> list[dict]:
    """Dónde se pisan los horarios de dos mundos o más (mundo → sus tramos): cada pedazo de un día en que rigen varios, con
    cuáles (en el orden en que vienen), el día (0 domingo … 6 sábado) y de qué minuto a qué minuto. Los tramos de un mismo
    mundo que se pisan entre sí no son un choque."""
    nombres = list(por_mundo)
    marcas = [0] * SEMANA
    for i, nombre in enumerate(nombres):
        bit = 1 << i
        for t in por_mundo[nombre] or ():
            for a, b in intervalos(t):
                for k in range(a, b):
                    marcas[k] |= bit
    salida = []
    for d in range(7):
        k, fin = d * DIA_ENTERO, (d + 1) * DIA_ENTERO
        while k < fin:
            m = marcas[k]
            if m & (m - 1):
                j = k
                while j < fin and marcas[j] == m:
                    j += 1
                salida.append({"mundos": [n for i, n in enumerate(nombres) if m >> i & 1], "dia": d,
                               "desde": k - d * DIA_ENTERO, "hasta": j - d * DIA_ENTERO})
                k = j
            else:
                k += 1
    return salida


def decir_choque(c: dict) -> str:
    """Un choque en una frase: «trabajo» y «estudio» se pisan el lunes de 9:00 a 10:00."""
    nombres = [f"«{n}»" for n in c["mundos"]]
    quienes = f"{', '.join(nombres[:-1])} y {nombres[-1]}"
    return f"{quienes} se pisan el {NOMBRES[c['dia']]} de {hora(c['desde'])} a {hora(c['hasta'])}"
