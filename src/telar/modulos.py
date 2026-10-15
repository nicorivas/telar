"""Módulos: una carpeta con un `modulo.toml` que declara lo que aporta, y que se instala de una vez.

Una pestaña del dashboard, una app, procesos periódicos y un resultado diario suelen ser una sola
cosa (un gráfico que un periódico baja y una pestaña dibuja). Sin módulos, cada pieza se declara
por separado, en dos máquinas. Con un módulo, la carpeta lo dice todo y la configuración solo
nombra la carpeta:

    [modulos.nino34]
    carpeta = "~/proyectos/nino34"

El manifiesto (`<carpeta>/modulo.toml`):

    descripcion = "la temperatura del mar en Niño 3.4"

    [pestana]                      # una pestaña del dashboard: un bloque (`[bloques]`)
    nombre = "niño 3.4"
    comando = ["bin/nino34", "pagina"]

    [app]                          # algo que se abre en el panel (`[apps]`): pagina, archivo o url
    archivo = "dist/app.html"

    [periodicos.bajar]             # corre donde viven los periódicos (`telar periodicos`)
    cuando = "30 7,15 * * *"
    comando = "bin/nino34 bajar"

    [resultado]                    # lo que el periódico deja por día (`[resultados]`)
    carpeta = "~/.local/state/nino34"

Las rutas relativas son de la carpeta del módulo, y sus periódicos corren en ella. Todo lo que
aporta toma el nombre del módulo: la pestaña es el bloque `nino34`, el resultado `nino34`, y un
periódico `nino34-bajar` (o `nino34` si se llama como el módulo). El resultado se lee donde corren
los periódicos (`[periodicos] en`). telar los junta con lo declarado a mano al leer la
configuración; el resto de telar no distingue de dónde vino cada pieza.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MANIFIESTO = "modulo.toml"
NOMBRE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_RAIZ = {"nombre", "descripcion", "pestana", "app", "periodicos", "resultado"}


class ErrorDeModulo(ValueError):
    """El manifiesto no está, o dice algo que telar no entiende."""


@dataclass(frozen=True, slots=True)
class Modulo:
    nombre: str
    carpeta: Path
    descripcion: str = ""
    pestana: dict = field(default_factory=dict)
    app: dict = field(default_factory=dict)
    #: nombre del proceso (ya con el del módulo) → su tabla
    periodicos: dict = field(default_factory=dict)
    resultado: dict = field(default_factory=dict)

    @property
    def aporta(self) -> list[str]:
        """Lo que trae, en palabras: «pestaña», «app», «periódico nino34», «resultado»."""
        return ([*(["pestaña"] if self.pestana else []), *(["app"] if self.app else []),
                 *[f"periódico {n}" for n in self.periodicos], *(["resultado"] if self.resultado else [])])


def _ruta(carpeta: Path, valor: str) -> str:
    """Una ruta del manifiesto: relativa a la carpeta del módulo, o absoluta, o con ~."""
    p = Path(valor).expanduser()
    return str(p if p.is_absolute() else carpeta / p)


def _comando(carpeta: Path, comando: list[str]) -> list[str]:
    """El primer elemento de un comando, si es un archivo del módulo, va con su ruta absoluta."""
    primero = comando[0]
    if not Path(primero).is_absolute() and (carpeta / primero).exists():
        primero = str(carpeta / primero)
    return [primero, *comando[1:]]


def leer(nombre: str, carpeta: Path) -> Modulo:
    """El módulo de esa carpeta, con sus rutas ya resueltas."""
    if not NOMBRE.fullmatch(nombre):
        raise ErrorDeModulo(f"«{nombre}»: el nombre de un módulo va en minúsculas, sin espacios")
    carpeta = carpeta.expanduser().resolve()
    archivo = carpeta / MANIFIESTO
    try:
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErrorDeModulo(f"{nombre}: no hay {archivo}") from None
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ErrorDeModulo(f"{nombre}: {archivo}: {e}") from None
    sobra = set(datos) - _RAIZ
    if sobra:
        raise ErrorDeModulo(f"{nombre}: {MANIFIESTO} no conoce «{sorted(sobra)[0]}»")
    for clave in ("pestana", "app", "periodicos", "resultado"):
        if not isinstance(datos.get(clave, {}), dict):
            raise ErrorDeModulo(f"{nombre}: [{clave}] tiene que ser una tabla")

    pestana = dict(datos.get("pestana", {}))
    if pestana:
        if not isinstance(pestana.get("comando"), list) or not pestana["comando"]:
            raise ErrorDeModulo(f"{nombre}: [pestana] comando: se esperaba una lista de palabras")
        pestana["comando"] = _comando(carpeta, pestana["comando"])
        pestana.setdefault("nombre", nombre)

    app = dict(datos.get("app", {}))
    if app:
        if isinstance(app.get("pagina"), list) and app["pagina"]:
            app["pagina"] = _comando(carpeta, app["pagina"])
        for campo in ("archivo", "memoria"):
            if isinstance(app.get(campo), str) and app[campo]:
                app[campo] = _ruta(carpeta, app[campo])
        app.setdefault("nombre", nombre)

    periodicos = {}
    for sub, cuerpo in datos.get("periodicos", {}).items():
        if not isinstance(cuerpo, dict):
            raise ErrorDeModulo(f"{nombre}: [periodicos.{sub}] tiene que ser una tabla")
        periodicos[nombre if sub == nombre else f"{nombre}-{sub}"] = dict(cuerpo)

    resultado = dict(datos.get("resultado", {}))
    if resultado and isinstance(resultado.get("carpeta"), str):
        resultado["carpeta"] = _ruta(carpeta, resultado["carpeta"]) if not resultado["carpeta"].startswith("~") else resultado["carpeta"]

    descripcion = datos.get("descripcion", "")
    if not isinstance(descripcion, str):
        raise ErrorDeModulo(f"{nombre}: descripcion: se esperaba un texto")
    return Modulo(nombre=nombre, carpeta=carpeta, descripcion=descripcion.strip(), pestana=pestana, app=app,
                  periodicos=periodicos, resultado=resultado)
