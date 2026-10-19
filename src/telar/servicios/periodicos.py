"""Los procesos periódicos (`telar periodicos`): verlos, su horario y su log, y cambiarlos. Viven en una
máquina (`[periodicos] en`): desde otra, se le piden a su nodo por el bus.

Lo usan la API (`/periodicos`) y el panel; la CLI es `telar periodicos`. Correr uno de una vez (`correr`)
espera a que termine: por la API se pide `ahora`, que lo suelta y vuelve.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio

#: los verbos que se piden por la API: todos menos `correr` (espera a que el proceso termine)
VERBOS = ("ver", "horario", "skills", "log", "ahora", "aplicar", "zona", "nuevo", "editar", "pausar", "activar", "borrar")


class Respuesta(BaseModel):
    """Lo que `telar periodicos <verbo> --json` imprime, tal cual."""

    model_config = ConfigDict(extra="allow")


def orden(ctx, argv: list[str]) -> Respuesta:
    from telar import alla
    from telar import bus as mod_bus
    from telar.ordenes.periodicos import sin_en
    from telar.servicios import en_proceso

    if not argv or argv[0] not in VERBOS:
        raise ErrorDeServicio(f"periodicos: uno de {', '.join(VERBOS)}", 422)
    argv = [*argv, "--json"]
    en = ctx.config.periodicos_en
    if en and en != "aqui" and en != mod_bus.maquina(ctx.config):
        if not mod_bus.hay_bus(ctx.config):
            raise ErrorDeServicio(f"los periódicos viven en {en} y no hay bus: pídeselos desde una terminal", 502)
        r = mod_bus.pedir(ctx.config, en, "periodicos", {"argv": sin_en(argv)}, espera=alla.ESPERA * 2 + 10)
        if not r.get("ok"):
            raise ErrorDeServicio(f"los periódicos viven en {en} y no respondió: {r.get('error', '')}", 502)
        codigo, salida, error = int(r.get("codigo", 1)), r.get("salida", ""), r.get("error_salida", "")
    else:
        c = en_proceso.correr(ctx, "periodicos", [*argv, "--en", "aqui"])
        codigo, salida, error = c.codigo, c.salida, c.error
    if codigo != 0:
        linea = (error.strip().splitlines() or [f"telar periodicos {argv[0]} falló"])[-1]
        raise ErrorDeServicio(linea.removeprefix("telar: "), 409)
    try:
        return Respuesta(**json.loads(salida.strip().splitlines()[-1]))
    except (ValueError, IndexError) as e:
        raise ErrorDeServicio(f"telar periodicos {argv[0]} no devolvió JSON", 502) from e
