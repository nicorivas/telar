"""Lo que toda prueba necesita antes de importar telar.

Dos cosas: que `src/` esté en el camino aunque nadie haya instalado el paquete
(para poder correr las pruebas en un clon recién bajado), y que las variables
`TELAR_*` del que corre las pruebas no se cuelen adentro — una configuración
heredada del entorno es la forma más silenciosa de que una prueba mienta.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLO = RAIZ / "ejemplo"

if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))


class Prueba(unittest.TestCase):
    """Caso base: el entorno queda limpio de `TELAR_*` mientras dure la prueba."""

    def setUp(self) -> None:
        super().setUp()
        self._entorno = {k: v for k, v in os.environ.items() if k.startswith("TELAR_")}
        for clave in self._entorno:
            del os.environ[clave]
        # Un HOME de verdad haría que `cargar()` leyera la config del que corre las
        # pruebas. Se apunta a una ruta que no existe y listo.
        self._hogar = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(RAIZ / "pruebas" / "no-existe")

    def tearDown(self) -> None:
        for clave in [k for k in os.environ if k.startswith("TELAR_")]:
            del os.environ[clave]
        os.environ.update(self._entorno)
        if self._hogar is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._hogar
        super().tearDown()
