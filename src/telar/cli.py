"""La CLI de telar: solo el despachador.

Aquí no vive ninguna orden. Este archivo resuelve las banderas globales, arma el
contexto (configuración y perfil) y le pasa el resto a la orden, que vive en su
propio módulo `telar.ordenes.<nombre>`. Cada orden expone:

    def main(argv: list[str], ctx: Contexto) -> int

`argv` son los argumentos que quedaron después del nombre de la orden; el entero
que devuelve es el código de salida. Una orden que no existe todavía se dice en
voz alta y sale con 2: es un esqueleto, no un misterio.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

from telar import __version__, salida
from telar.config import Config, ErrorDeConfig
from telar.config import cargar as cargar_config
from telar.perfil import ErrorDePerfil, Perfil
from telar.perfil import cargar as cargar_perfil

__all__ = ["Contexto", "ORDENES", "main"]

#: Las órdenes que telar va a tener, con su línea de ayuda. El módulo de cada una
#: es `telar.ordenes.<nombre>`; mientras no exista, el despachador lo dice.
ORDENES: dict[str, str] = {
    "init": "Escribir la configuración y preparar el estado.",
    "doctor": "Revisar multiplexor, sesión, perfil, proveedores y ganchos.",
    "tejer": "Levantar la sesión, o reengancharla si ya está viva.",
    "hilos": "Los hilos de la sesión, con su estado.",
    "hilo": "Vincular, renombrar, priorizar, archivar: actuar sobre un hilo.",
    "ficha": "Lo que el documento de un hilo dice de sí mismo.",
    "ir": "Poner el foco en un hilo.",
    "vincular": "Asociar un hilo a una carpeta del repositorio.",
    "pendientes": "Lo que está por hacer, junto y con su hilo al lado.",
    "pendiente": "Llevar un pendiente al hilo donde se trabaja.",
    "hoy": "El día en una pantalla: agenda, quién te espera, qué falta.",
    "atencion": "Qué dice el agente de cada hilo: trabajando, espera, terminó.",
    "agente": "El agente que corre en un hilo: sus ganchos, sus conversaciones.",
    "tiempo": "Cuánto estuvo arriba cada hilo, medido por el foco.",
    "accion": "Correr una acción declarada por el perfil.",
    "config": "Mostrar la configuración resuelta y de dónde salió.",
    "perfil": "Mostrar el perfil del repositorio y qué documentos alcanza.",
}

AYUDA = f"""\
telar {__version__} — un telar para hilos de trabajo.

  telar [banderas] <orden> [argumentos]

Banderas globales:
  -c, --config RUTA   archivo de configuración (por defecto, $TELAR_CONFIG o
                      ~/.config/telar/config.toml)
  -r, --raiz RUTA     raíz del repositorio de trabajo (pisa la de la configuración)
  -V, --version       la versión y nada más
  -h, --help          esto

Órdenes:
{chr(10).join(f"  {n:<12}{d}" for n, d in ORDENES.items())}

Cada orden explica lo suyo con --help, y lo que imprime con --json es un contrato:
está escrito en docs/contratos.md.

telar no decide qué es un proyecto: eso lo declara el repositorio de trabajo en su
telar-perfil.yaml. Ver docs/perfil.md.
"""


@dataclass(slots=True)
class Contexto:
    """Lo que toda orden recibe. El perfil se lee la primera vez que se pide."""

    config: Config
    _perfil: Perfil | None = None

    @property
    def perfil(self) -> Perfil:
        if self._perfil is None:
            self._perfil = cargar_perfil(self.config.raiz, ruta=self.config.perfil)
        return self._perfil

    @property
    def raiz(self) -> Path:
        return self.config.raiz


def _error(mensaje: str) -> int:
    print(f"telar: {mensaje}", file=sys.stderr)
    return 2


def _banderas(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    """Separa las banderas globales del resto. La primera palabra suelta es la orden.

    Se hace a mano y no con argparse porque las banderas de cada orden son de cada
    orden: aquí no se conocen y no hay que tocarlas.
    """
    opciones: dict[str, str] = {}
    resto: list[str] = []
    i = 0
    con_valor = {"-c": "config", "--config": "config", "-r": "raiz", "--raiz": "raiz"}
    solas = {"-h": "ayuda", "--help": "ayuda", "-V": "version", "--version": "version"}

    while i < len(argv):
        arg = argv[i]
        if arg in con_valor:
            if i + 1 >= len(argv):
                raise ValueError(f"{arg} necesita un valor")
            opciones[con_valor[arg]] = argv[i + 1]
            i += 2
            continue
        if arg in solas:
            opciones[solas[arg]] = "sí"
            i += 1
            continue
        if arg.startswith("-") and arg != "-":
            raise ValueError(f"bandera desconocida: {arg}")
        # la primera palabra suelta es la orden; de ahí en adelante, es de ella
        resto = argv[i:]
        break

    return opciones, resto


def main(argv: list[str] | None = None) -> int:
    """El punto de entrada de la consola. Devuelve el código de salida."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # Antes de imprimir nada, ni siquiera la ayuda: todo lo que telar dice trae
    # acentos, comillas «así» y símbolos, y una salida que no sea UTF-8 mataría la
    # orden con una traza. Ver `telar.salida`.
    salida.preparar()

    try:
        opciones, resto = _banderas(argv)
    except ValueError as e:
        return _error(f"{e}\nPrueba: telar --help")

    if "version" in opciones:
        print(f"telar {__version__}")
        return 0

    if "ayuda" in opciones or not resto:
        print(AYUDA, end="")
        return 0 if "ayuda" in opciones else 1

    orden, argumentos = resto[0], resto[1:]
    if orden not in ORDENES:
        parecidas = [n for n in ORDENES if n.startswith(orden[:2])]
        pista = f" ¿Quisiste decir {' o '.join(parecidas)}?" if parecidas else ""
        return _error(f"no conozco la orden '{orden}'.{pista}\nPrueba: telar --help")

    try:
        config = cargar_config(Path(opciones["config"]) if "config" in opciones else None)
        if "raiz" in opciones:
            from dataclasses import replace

            config = replace(config, raiz=Path(opciones["raiz"]).expanduser())
    except ErrorDeConfig as e:
        return _error(str(e))

    ruta_modulo = f"telar.ordenes.{orden}"
    try:
        modulo = importlib.import_module(ruta_modulo)
    except ModuleNotFoundError as e:
        # Solo si falta la orden misma. Si a la orden le falta OTRA cosa, que se vea.
        if e.name not in (ruta_modulo, "telar.ordenes"):
            raise
        return _error(f"la orden '{orden}' está declarada pero todavía no implementada")

    try:
        return int(modulo.main(argumentos, Contexto(config=config)))
    except (ErrorDeConfig, ErrorDePerfil) as e:
        return _error(str(e))
    except KeyboardInterrupt:  # pragma: no cover - depende de la terminal
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
