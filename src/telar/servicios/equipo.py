"""La bandeja del equipo, del lado de su dueño: lo que una persona sugirió o pidió, y decidirlo
(telar.equipo). Vive en la máquina que tiene las tareas; desde otra, se le pide a su nodo por el bus.

Lo usan `telar equipo sugerencias|aceptar|rechazar|existe|revisando` y la API de su dueño (`/equipo/…`),
nunca la página del equipo: esa es otra app (telar.api_equipo).
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio

DECISIONES = ("aceptar", "rechazar", "existe")


class Bandeja(BaseModel):
    sugerencias: list[dict]


class Sugerencia(BaseModel):
    sugerencia: dict


def _alla(ctx, maquina: str) -> str:
    from telar import bus as mod_bus

    if not maquina or maquina in ("local", "aqui") or maquina == mod_bus.maquina(ctx.config):
        return ""
    if not mod_bus.hay_bus(ctx.config):
        raise ErrorDeServicio(f"la bandeja vive en {maquina} y no hay bus: pídesela desde una terminal (--remoto)", 502)
    return maquina


def _pedir_alla(ctx, maquina: str, argv: list[str]) -> dict:
    from telar import alla
    from telar import bus as mod_bus

    r = mod_bus.pedir(ctx.config, maquina, "equipo", {"argv": [*argv, "--json"]}, espera=alla.ESPERA + 10)
    if not r.get("ok"):
        raise ErrorDeServicio(f"la bandeja vive en {maquina} y no respondió: {r.get('error', '')}", 502)
    if int(r.get("codigo", 1)) != 0:
        linea = (r.get("error_salida", "").strip().splitlines() or [f"{maquina} no pudo"])[-1]
        raise ErrorDeServicio(linea.removeprefix("telar: "), 409)
    try:
        return json.loads(r.get("salida", "").strip().splitlines()[-1])
    except (ValueError, IndexError) as e:
        raise ErrorDeServicio(f"{maquina} no devolvió JSON", 502) from e


def _cargar():
    from telar import equipo as mod_equipo

    try:
        return mod_equipo.cargar()
    except ValueError as e:
        raise ErrorDeServicio(str(e), 404) from e


def bandeja(ctx, *, todas: bool = False, maquina: str = "") -> Bandeja:
    """Lo que falta decidir (con `todas`, también lo resuelto)."""
    from telar import equipo as mod_equipo

    if (en := _alla(ctx, maquina)):
        return Bandeja(**_pedir_alla(ctx, en, ["sugerencias", *(["--todas"] if todas else [])]))
    eq = _cargar()
    return Bandeja(sugerencias=[r for r in mod_equipo.leer_bandeja(eq) if todas or r["estado"] == "pendiente"])


def decidir(ctx, ident: str, decision: str, *, nota: str = "", tarea: str = "", maquina: str = "") -> Sugerencia:
    """Aceptar (sube la prioridad un nivel, o agrega la tarea pedida), rechazar, o decir que un pedido ya
    existe (`tarea`: cuál): quien lo hizo ve la nota."""
    from telar import equipo as mod_equipo

    if decision not in DECISIONES:
        raise ErrorDeServicio(f"la decisión es {', '.join(DECISIONES)}", 422)
    if (en := _alla(ctx, maquina)):
        return Sugerencia(**_pedir_alla(ctx, en, [decision, ident, *(["--nota", nota] if nota else []),
                                                  *(["--tarea", tarea] if tarea else [])]))
    r, problema = mod_equipo.resolver(_cargar(), ident, decision, nota, tarea)
    if r is None:
        raise ErrorDeServicio(problema, 409)
    return Sugerencia(sugerencia=r)


def revisando(ctx, ident: str, *, quien: str = "gestion", maquina: str = "") -> Sugerencia:
    """Anotar que alguien la está revisando: sigue pendiente, pero la lista lo muestra."""
    from telar import equipo as mod_equipo

    if (en := _alla(ctx, maquina)):
        return Sugerencia(**_pedir_alla(ctx, en, ["revisando", ident, "--quien", quien]))
    r, problema = mod_equipo.marcar_revision(_cargar(), ident, quien)
    if r is None:
        raise ErrorDeServicio(problema, 409)
    return Sugerencia(sugerencia=r)
