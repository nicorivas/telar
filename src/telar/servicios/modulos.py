"""Preguntarle algo a un módulo (una orden suya con `consulta = true`, ver telar.modulos): en esta máquina o
en otra, por el bus a su nodo, que la corre con el módulo instalado allá.

Lo usan `GET /modulos/<modulo>/<verbo>` de la API (la página) y el nodo (`rpc … modulo`).
"""

from __future__ import annotations

from telar.servicios import ErrorDeServicio


def consultar(ctx, modulo: str, verbo: str, params: dict, maquina: str = "") -> dict:
    from telar import bus as mod_bus
    from telar import modulos as mod_modulos

    if maquina and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config):
        r = mod_bus.pedir(ctx.config, maquina, "modulo", {"modulo": modulo, "verbo": verbo, "params": params},
                          espera=mod_modulos.ESPERA_CONSULTA + 10)
        if not r.get("ok"):
            raise ErrorDeServicio(r.get("error") or f"{maquina} no pudo", int(r.get("codigo") or 502))
        return r.get("respuesta") or {}
    try:
        return mod_modulos.consultar(ctx.config, modulo, verbo, params)
    except mod_modulos.ErrorDeModulo as e:
        texto = str(e)
        raise ErrorDeServicio(texto, 404 if texto.startswith("aquí no está") or "no tiene la consulta" in texto else 502) from None


def para_otra(ctx, pedido: dict) -> dict:
    """Lo que responde el nodo a `modulo`: la respuesta del módulo, o el error con su código."""
    try:
        params = pedido.get("params") if isinstance(pedido.get("params"), dict) else {}
        return {"ok": True, "respuesta": consultar(ctx, str(pedido.get("modulo", "")), str(pedido.get("verbo", "")), params)}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}
