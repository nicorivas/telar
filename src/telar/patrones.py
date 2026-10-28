"""Patrones de fecha de Unicode (LDML, el de CLDR, ICU, Java e `Intl`): leer y escribir una fecha con la forma que
dice un patrón, en las dos direcciones (telar.mapas, docs/propuestas/fechas.md).

    p = Patron("EEE d-MMM", idioma="es")
    p.leer("jue 18-jun", anio=2026)      → date(2026, 6, 18)
    p.escribir(date(2026, 11, 17))       → "mar 17-nov"

Lo que entiende: `d` `dd` (día), `M` `MM` (mes en número), `MMM` `MMMM` y `LLL` `LLLL` (mes en palabras, corto o
largo), `y` `yy` `yyyy` (año), `E` `EEE` `EEEE` (día de la semana: se lee y no se usa, se escribe recalculado),
`H` `HH` `m` `mm` (hora), y el texto entre comillas simples (`'de'`). Lo demás del patrón es literal.

Los nombres de meses y días salen de los datos de CLDR del idioma si Babel está instalado; si no, en castellano y en
inglés vienen aquí. Al leer se toleran las variantes de la escritura a mano: con o sin punto, con o sin tilde,
mayúsculas, y el mes por sus tres primeras letras («sep» y «sept»).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

__all__ = ["Patron", "ErrorDePatron"]


class ErrorDePatron(ValueError):
    """El patrón no se entiende, o el texto no calza con él."""


_MESES = {
    "es": (("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
           ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
            "noviembre", "diciembre")),
    "en": (("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
           ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
            "november", "december")),
}
#: lunes primero, como `date.weekday()`
_DIAS = {
    "es": (("lun", "mar", "mié", "jue", "vie", "sáb", "dom"),
           ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")),
    "en": (("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
           ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")),
}

#: las letras de campo, en tiradas: `dd`, `MMM`, `yyyy`… (y lo literal entre comillas)
_TOKEN = re.compile(r"'(?:[^']|'')*'|([dMLyEHm])\1*")


def _sin_tilde(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _nombres(idioma: str) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], tuple[tuple[str, ...], tuple[str, ...]]]:
    """(meses cortos y largos, días cortos y largos) del idioma: de CLDR si hay Babel, si no los de aquí."""
    try:
        from babel import Locale
        from babel.dates import get_day_names, get_month_names

        Locale.parse(idioma)
        meses = tuple(tuple(str(get_month_names(ancho, locale=idioma)[i]).lower().rstrip(".") for i in range(1, 13))
                      for ancho in ("abbreviated", "wide"))
        dias = tuple(tuple(str(get_day_names(ancho, locale=idioma)[i]).lower().rstrip(".") for i in range(7))
                     for ancho in ("abbreviated", "wide"))
        return meses, dias  # type: ignore[return-value]
    except Exception:  # noqa: BLE001 - sin Babel, o un idioma que no conoce: los de aquí
        base = idioma.split("_")[0].split("-")[0].lower()
        if base not in _MESES:
            raise ErrorDePatron(f"idioma {idioma!r}: sin Babel instalado, solo es y en (pip install babel)") from None
        return _MESES[base], _DIAS[base]


class Patron:
    """Un patrón de fecha (o de hora) ya compilado, para leer y escribir."""

    def __init__(self, patron: str, *, idioma: str = "es") -> None:
        if not isinstance(patron, str) or not patron.strip():
            raise ErrorDePatron("el patrón está vacío")
        self.patron = patron
        self.idioma = idioma
        (self._mes_corto, self._mes_largo), (self._dia_corto, self._dia_largo) = _nombres(idioma)
        self._piezas = self._partir(patron)
        self._regex = re.compile(self._expresion(self._piezas), re.I)
        # para la primera mitad de un rango («17» de «17–28 nov»): el patrón sin sus últimas piezas, del más largo al
        # más corto; lo que le falta lo pone la otra mitad
        self._recortes = [re.compile(self._expresion(self._piezas[:n]), re.I)
                          for n in range(len(self._piezas) - 1, 0, -1) if self._piezas[n - 1][0] == "campo"]

    @staticmethod
    def _partir(patron: str) -> list[tuple[str, str]]:
        """El patrón en piezas: ("campo", "dd") o ("literal", "-")."""
        piezas: list[tuple[str, str]] = []
        i = 0
        for m in _TOKEN.finditer(patron):
            if m.start() > i:
                piezas.append(("literal", patron[i:m.start()]))
            if m.group(0).startswith("'"):
                piezas.append(("literal", m.group(0)[1:-1].replace("''", "'") or "'"))
            else:
                piezas.append(("campo", m.group(0)))
            i = m.end()
        if i < len(patron):
            piezas.append(("literal", patron[i:]))
        if not any(k == "campo" for k, _ in piezas):
            raise ErrorDePatron(f"«{patron}» no tiene ningún campo de fecha (d, M, y, E, H, m)")
        return piezas

    def _alternativas(self, nombres: tuple[str, ...]) -> str:
        """Los nombres como alternativas: cada uno sin tilde y cada comienzo suyo de tres letras o más («sep», «sept»,
        «septiembre»), del más largo al más corto, con un punto opcional."""
        variantes = {_sin_tilde(n)[:k] for n in nombres for k in range(3, len(n) + 1)} | {_sin_tilde(n) for n in nombres}
        return "(?:" + "|".join(re.escape(v) for v in sorted(variantes, key=len, reverse=True)) + r")\.?"

    def _expresion(self, piezas: list[tuple[str, str]]) -> str:
        partes = []
        for tipo, valor in piezas:
            if tipo == "literal":
                valor = _sin_tilde(valor)
                partes.append(r"\s*".join(re.escape(x) for x in valor.split()) if valor.strip() else r"\s*")
                continue
            letra, n = valor[0], len(valor)
            if letra == "d":
                partes.append(r"(?P<d>\d{1,2})")
            elif letra in "ML" and n <= 2:
                partes.append(r"(?P<M>\d{1,2})")
            elif letra in "ML":
                partes.append(f"(?P<Mn>{self._alternativas(self._mes_corto + self._mes_largo)})")
            elif letra == "y":
                partes.append(r"(?P<y>\d{2})" if n == 2 else r"(?P<y>\d{4})")
            elif letra == "E":
                partes.append(f"(?:{self._alternativas(self._dia_corto + self._dia_largo)})")
            elif letra == "H":
                partes.append(r"(?P<H>\d{1,2})")
            elif letra == "m":
                partes.append(r"(?P<m>\d{2})")
        return r"\s*" + "".join(partes) + r"\s*"

    def _mes_de(self, texto: str) -> int:
        t = _sin_tilde(texto).rstrip(".")
        for nombres in (self._mes_largo, self._mes_corto):
            for i, n in enumerate(nombres, 1):
                if t == _sin_tilde(n) or (len(t) >= 3 and _sin_tilde(n).startswith(t)):
                    return i
        raise ErrorDePatron(f"«{texto}» no es un mes")

    def partes(self, texto: str, *, parcial: bool = False) -> dict[str, int]:
        """Lo que trae el texto, campo por campo (`d`, `M`, `y`, `H`, `m`): solo lo que el patrón tiene. Con `parcial`,
        también un comienzo del patrón («17» con `d MMM`), para la primera mitad de un rango."""
        limpio = _sin_tilde(texto)
        m = self._regex.fullmatch(limpio)
        if not m and parcial:
            m = next((r.fullmatch(limpio) for r in self._recortes if r.fullmatch(limpio)), None)
        if not m:
            raise ErrorDePatron(f"«{texto}» no calza con «{self.patron}»")
        g = {k: v for k, v in m.groupdict().items() if v is not None}
        salida: dict[str, int] = {}
        if "d" in g:
            salida["d"] = int(g["d"])
        if "M" in g:
            salida["M"] = int(g["M"])
        if "Mn" in g:
            salida["M"] = self._mes_de(g["Mn"])
        if "y" in g:
            anio = int(g["y"])
            salida["y"] = anio + 2000 if len(g["y"]) == 2 else anio
        for k in ("H", "m"):
            if k in g:
                salida[k] = int(g[k])
        return salida

    def leer(self, texto: str, *, anio: int | None = None) -> date:
        """La fecha del texto. Si el patrón no trae año, `anio` (si falta, error)."""
        p = self.partes(texto)
        if "d" not in p or "M" not in p:
            raise ErrorDePatron(f"«{self.patron}» no trae día y mes")
        y = p.get("y", anio)
        if y is None:
            raise ErrorDePatron(f"«{texto}» no trae año y el mapa no dice cuál (año:)")
        try:
            return date(y, p["M"], p["d"])
        except ValueError:
            raise ErrorDePatron(f"«{texto}» no es un día que exista") from None

    def hora(self, texto: str) -> str:
        """La hora del texto como `HH:MM`."""
        p = self.partes(texto)
        if "H" not in p:
            raise ErrorDePatron(f"«{self.patron}» no trae hora")
        return f"{p['H']:02d}:{p.get('m', 0):02d}"

    def escribir(self, dia: date) -> str:
        """La fecha con la forma del patrón: lo que se escribe de vuelta en la celda."""
        salida = []
        for tipo, valor in self._piezas:
            if tipo == "literal":
                salida.append(valor)
                continue
            letra, n = valor[0], len(valor)
            if letra == "d":
                salida.append(f"{dia.day:0{min(n, 2)}d}")
            elif letra in "ML":
                salida.append(f"{dia.month:0{n}d}" if n <= 2 else
                              (self._mes_corto if n == 3 else self._mes_largo)[dia.month - 1])
            elif letra == "y":
                salida.append(f"{dia.year % 100:02d}" if n == 2 else str(dia.year))
            elif letra == "E":
                salida.append((self._dia_largo if n >= 4 else self._dia_corto)[dia.weekday()])
            else:
                raise ErrorDePatron(f"«{self.patron}» tiene hora: no escribe un día")
        return "".join(salida)
