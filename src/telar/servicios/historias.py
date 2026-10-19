"""Lo último de un hilo, para leerlo como conversación, sin moverle nada: ni foco, ni atención, ni estado
(telar.historia). De otra máquina, lo lee su nodo y responde por el bus.

Lo usan `telar hilo leer --json` y `GET /hilos/leer`; el panel, para el teléfono.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio


class Historia(BaseModel):
    """`{hilo, turnos: [[{quien, texto}…]…], …}` (docs/contratos.md, «telar hilo leer»), y `maquina` si es de otra."""

    model_config = ConfigDict(extra="allow")


def leer(ctx, hilo: str = "", *, ultimos: int = 0, maquina: str = "") -> Historia:
    from telar import bus as mod_bus
    from telar import historia
    from telar.ordenes import _comun

    ultimos = ultimos or historia.POR_DEFECTO
    if maquina and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config):
        if not hilo:
            raise ErrorDeServicio("¿qué hilo de esa máquina? telar hilo leer «Faro» --maquina laptop", 422)
        r = mod_bus.pedir(ctx.config, maquina, "leer", {"hilo": hilo, "ultimos": ultimos}, espera=30)
        if not r.get("ok"):
            raise ErrorDeServicio(r.get("error", f"{maquina} no respondió"), 502)
        return Historia(**{**r["historia"], "maquina": maquina})
    tel = _comun.tejer(ctx, con_ficha=False)
    if hilo:
        h, problema = _comun.resolver(tel, hilo)
        if h is None:
            raise ErrorDeServicio(problema, 404)
    else:
        h = _comun.hilo_actual(tel)
        if h is None:
            raise ErrorDeServicio("¿qué hilo? fuera de un hilo, di cuál: telar hilo leer <hilo>", 404)
    if not 1 <= ultimos <= historia.MAX_TURNOS:
        raise ErrorDeServicio(f"--ultimos va de 1 a {historia.MAX_TURNOS}", 422)
    try:
        return Historia(**historia.leer(ctx, tel, h, ultimos))
    except historia.ErrorDeHistoria as e:
        raise ErrorDeServicio(str(e), 502) from e
