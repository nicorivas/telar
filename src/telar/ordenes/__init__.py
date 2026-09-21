"""Las órdenes de la CLI, una por módulo.

Cada módulo de esta carpeta expone:

    def main(argv: list[str], ctx: telar.cli.Contexto) -> int

`argv` es lo que quedó después del nombre de la orden —el despachador no toca las
banderas de nadie— y el entero es el código de salida: 0 bien, 2 error de uso o de
entorno. Lo que comparten está en `_comun`, que no es una orden y por eso empieza
con guion bajo.

Una orden nueva se escribe aquí y se declara en `telar.cli.ORDENES`; el
despachador la carga sola, y mientras el módulo no exista lo dice en voz alta.
"""

from __future__ import annotations

__all__: list[str] = []
