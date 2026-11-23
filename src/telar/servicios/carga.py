"""Lo que carga el contexto de un hilo (docs/contratos.md, «telar hilo contexto»): cuánto pesa su conversación ahora,
desde cuándo, y de qué está hecho — lo que todo hilo carga sin pedirlo (los CLAUDE.md, la memoria, los hooks, la
lista de skills, los MCP), lo que carga al entrar a carpetas, lo que leyó, lo que se repite en cada mensaje y lo que
le llegó de otros hilos —, cada cosa con su ruta, su tamaño y cuántas veces entró. Nunca su contenido.

Se calcula en la máquina donde vive la conversación (telar.conversacion.carga, con lo que sabe su agente:
telar.agente.carga_claude); de otra, se le pide a su nodo por el bus (el verbo `contexto`). Lo usan
`telar hilo contexto`, `GET /contexto` y la hoja «contexto» de la barra de la derecha de la página (web/carga.ts).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from telar.servicios import ErrorDeServicio


class CargaDeHilo(BaseModel):
    """`{hilo, maquina, agente, conversacion, carpeta, casa, desde, total, medido, grupos, items, …}`."""

    model_config = ConfigDict(extra="allow")

    hilo: str
    maquina: str = ""
    #: el agente que lo lee (claude-code)
    agente: str = ""
    #: el id de la conversación que se leyó (la de ahora: la primera de las del hilo que está en disco)
    conversacion: str = ""
    #: la carpeta vinculada del hilo y la casa de su máquina, para mostrar las rutas cortas
    carpeta: str = ""
    casa: str = ""
    desde: dict = Field(default_factory=dict)
    compactaciones: int = 0
    total: int = 0
    medido: bool = False
    hora: str = ""
    modelo: str = ""
    al_empezar: int | None = None
    caracteres_por_token: float = 0
    grupos: list[dict] = Field(default_factory=list)
    items: list[dict] = Field(default_factory=list)
    truncado: bool = False


def de_hilo(ctx, hilo: str = "", *, maquina: str = "", de_otra: bool = False) -> CargaDeHilo:
    """Lo que carga el contexto del hilo. Con `maquina` (otra), se le pide a esa por el bus. `de_otra`: lo pide
    otra máquina, y lo que `[bus] no_leer` veta no se le muestra."""
    from telar import bus as mod_bus

    if maquina and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config):
        if not hilo:
            raise ErrorDeServicio("¿qué hilo de esa máquina? telar hilo contexto «Faro» --maquina servidor", 422)
        r = mod_bus.pedir(ctx.config, maquina, "contexto", {"hilo": hilo}, espera=30)
        if not r.get("ok"):
            raise ErrorDeServicio(r.get("error") or f"{maquina} no respondió", int(r.get("codigo") or 502))
        return CargaDeHilo(**{**r["contexto"], "maquina": maquina})
    return _aqui(ctx, hilo, de_otra=de_otra)


def para_otra(ctx, pedido: dict) -> dict:
    """Lo que responde el nodo al verbo `contexto`: lo que carga el hilo, o el error con su código."""
    try:
        r = de_hilo(ctx, str(pedido.get("hilo", "")), de_otra=True)
        return {"ok": True, "contexto": r.model_dump(mode="json")}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}


def _aqui(ctx, hilo: str, *, de_otra: bool) -> CargaDeHilo:
    from telar import conversacion, historia
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx, con_ficha=False)
    if hilo:
        h, problema = _comun.resolver(tel, hilo)
        if h is None:
            raise ErrorDeServicio(problema, 404)
    else:
        h = _comun.hilo_actual(tel)
        if h is None:
            raise ErrorDeServicio("¿qué hilo? fuera de un hilo, di cuál: telar hilo contexto <hilo>", 404)
    if de_otra and historia.vetado(historia.no_leer(ctx.config), h.nombre, tel.estado.vinculos().get(h.nombre, "")):
        raise ErrorDeServicio(f"«{h.nombre}» no se lee desde otra máquina ([bus] no_leer)", 403)
    agente = getattr(ctx.config.agente, "nombre", "") or ""
    if not h.sesiones:
        raise ErrorDeServicio(f"«{h.nombre}» no tiene una conversación que telar sepa leer: no se sabe qué cargó"
                              + (" (¿la abrió otro agente?)" if agente else ""), 404)
    try:
        sid, resumen = conversacion.carga(ctx.config, list(h.sesiones))
    except conversacion.ErrorDeConversacion as e:
        raise ErrorDeServicio(str(e), 404) from e
    carpeta = str(Path(h.vinculo).expanduser()) if h.vinculo is not None else ""
    return CargaDeHilo(hilo=h.nombre, agente=agente, conversacion=sid, carpeta=carpeta, casa=str(Path.home()), **resumen)
