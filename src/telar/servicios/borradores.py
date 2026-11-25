"""Los borradores de un hilo (telar.borradores; docs/contratos.md «telar hilo borradores»): verlos, escribirlos,
borrarlos y mandárselos a su hilo.

Viven en la máquina del hilo: de otra, se le piden a su nodo por el bus (el verbo `borradores`, con la `accion`). Lo
usan `telar hilo borradores`, `GET|POST|DELETE /hilos/borradores`, `POST /hilos/borradores/mandar` y el bloque de
borradores de la barra de la derecha de la página (web/borradores.ts).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio

#: cuánto se espera a la otra máquina
ESPERA = 30


class Borrador(BaseModel):
    """Un próximo prompt: `al_terminar` es «escribir» o «enviar» si sale solo cuando el agente termine su turno."""

    id: str
    texto: str
    creado: str = ""
    cambiado: str = ""
    al_terminar: str = ""


class Borradores(BaseModel):
    """`{hilo, maquina, borradores, ocupado}`: los de un hilo, en orden, y si su agente está en lo suyo ahora
    («trabajando», «espera» o "")."""

    hilo: str
    maquina: str = ""
    borradores: list[Borrador] = Field(default_factory=list)
    ocupado: str = ""


class Mandado(BaseModel):
    """Lo que pasó al mandarlo: `como` es «escrito», «enviado» o «en espera» (con `al_terminar`)."""

    hilo: str
    id: str
    como: str
    al_terminar: str = ""
    maquina: str = ""


def _de_otra(ctx, maquina: str) -> bool:
    from telar import bus as mod_bus

    return bool(maquina) and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config)


def _pedir(ctx, maquina: str, pedido: dict) -> dict:
    from telar import bus as mod_bus

    r = mod_bus.pedir(ctx.config, maquina, "borradores", pedido, espera=ESPERA)
    if not r.get("ok"):
        raise ErrorDeServicio(r.get("error") or f"{maquina} no respondió", int(r.get("codigo") or 502),
                              datos=r.get("datos") if isinstance(r.get("datos"), dict) else None)
    return r


def _estado(ctx):
    from telar import estado as mod_estado

    return mod_estado.abrir(ctx.config)


def _nombre(est, hilo: str) -> str:
    hilo = (hilo or "").strip()
    if not hilo:
        raise ErrorDeServicio("¿de qué hilo? --hilo, o el nombre", 422)
    return est.nombre_actual(hilo)


def _error(e) -> ErrorDeServicio:
    return ErrorDeServicio(str(e), e.codigo, datos=e.datos)


def de_hilo(ctx, hilo: str, *, maquina: str = "") -> Borradores:
    """Los borradores de un hilo, y si su agente está ocupado."""
    from telar import borradores as mod

    if _de_otra(ctx, maquina):
        return Borradores(**{**_pedir(ctx, maquina, {"accion": "ver", "hilo": hilo})["borradores"], "maquina": maquina})
    est = _estado(ctx)
    nombre = _nombre(est, hilo)
    return Borradores(hilo=nombre, borradores=[Borrador(**_campos(b)) for b in est.borradores(nombre)],
                      ocupado=mod.ocupado(est, nombre))


def _campos(b: dict) -> dict:
    return {k: b[k] for k in ("id", "texto", "creado", "cambiado", "al_terminar") if isinstance(b.get(k), str)}


def guardar(ctx, hilo: str, texto: str, *, id: str = "", maquina: str = "") -> Borrador:
    """Escribe uno: sin `id`, nuevo al final; con él, el mismo con este texto."""
    from telar import borradores as mod

    if _de_otra(ctx, maquina):
        return Borrador(**_pedir(ctx, maquina, {"accion": "guardar", "hilo": hilo, "texto": texto, "id": id})["borrador"])
    est = _estado(ctx)
    try:
        return Borrador(**_campos(mod.guardar(est, _nombre(est, hilo), texto, id)))
    except mod.ErrorDeBorrador as e:
        raise _error(e) from e


def borrar(ctx, hilo: str, id: str, *, maquina: str = "") -> Borrador:
    """Lo saca de la lista. 404 si ya no estaba."""
    if _de_otra(ctx, maquina):
        return Borrador(**_pedir(ctx, maquina, {"accion": "borrar", "hilo": hilo, "id": id})["borrador"])
    est = _estado(ctx)
    nombre = _nombre(est, hilo)
    b = est.quitar_borrador(nombre, id)
    if b is None:
        raise ErrorDeServicio(f"el borrador {id} de «{nombre}» ya no está: se mandó o se borró", 404)
    return Borrador(**_campos(b))


def no_esperar(ctx, hilo: str, id: str, *, maquina: str = "") -> Borrador:
    """Le quita la espera: ya no sale solo al terminar el turno."""
    if _de_otra(ctx, maquina):
        return Borrador(**_pedir(ctx, maquina, {"accion": "no-esperar", "hilo": hilo, "id": id})["borrador"])
    est = _estado(ctx)
    nombre = _nombre(est, hilo)
    try:
        return Borrador(**_campos(est.esperar_borrador(nombre, id, "")))
    except KeyError:
        raise ErrorDeServicio(f"el borrador {id} de «{nombre}» ya no está: se mandó o se borró", 404) from None


def mandar(ctx, hilo: str, id: str, *, enviar: bool = False, esperar: bool = False, maquina: str = "") -> Mandado:
    """Escribirlo en la entrada de su hilo (con `enviar`, y ⏎), o dejarlo en espera del fin del turno (`esperar`).
    Ocupado y sin `esperar`: 409 con `ocupado`."""
    from telar import borradores as mod
    from telar.ordenes import _comun

    if _de_otra(ctx, maquina):
        r = _pedir(ctx, maquina, {"accion": "mandar", "hilo": hilo, "id": id, "enviar": enviar, "esperar": esperar})
        return Mandado(**{**r["mandado"], "maquina": maquina})
    tel = _comun.tejer(ctx, con_ficha=False)
    try:
        return Mandado(**mod.mandar(ctx.config, tel, _nombre(tel.estado, hilo), id, enviar=enviar, esperar=esperar))
    except mod.ErrorDeBorrador as e:
        raise _error(e) from e


def para_otra(ctx, pedido: dict) -> dict:
    """Lo que responde el nodo al verbo `borradores`, según su `accion`: lo pedido, o el error con su código."""
    accion, hilo, id = str(pedido.get("accion", "")), str(pedido.get("hilo", "")), str(pedido.get("id", ""))
    try:
        if accion == "ver":
            return {"ok": True, "borradores": de_hilo(ctx, hilo).model_dump(mode="json")}
        if accion == "guardar":
            return {"ok": True, "borrador": guardar(ctx, hilo, str(pedido.get("texto", "")), id=id).model_dump(mode="json")}
        if accion == "borrar":
            return {"ok": True, "borrador": borrar(ctx, hilo, id).model_dump(mode="json")}
        if accion == "no-esperar":
            return {"ok": True, "borrador": no_esperar(ctx, hilo, id).model_dump(mode="json")}
        if accion == "mandar":
            r = mandar(ctx, hilo, id, enviar=bool(pedido.get("enviar")), esperar=bool(pedido.get("esperar")))
            return {"ok": True, "mandado": r.model_dump(mode="json")}
        return {"ok": False, "error": f"«{accion}» no es una acción de los borradores", "codigo": 422}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo, "datos": e.datos}
