"""Encargos a un agente residente: escribirle a su hilo de siempre en vez de abrir uno nuevo.

Un encargo es un pedido para un agente (`telar encargar gestion "/avanzar"`, o un proceso periódico con
`agente = "gestion"`). Es siempre un Encargo como objeto (`encargo:e-…`, telar.encargo): queda en la casilla
del agente y tiene estado (pedido → corriendo → hecho | falló | cancelado), lo cierra el agente con su
resultado y ese resultado le llega a quien lo pidió. Con bus, el mensaje va por el bus a la casilla del agente
(telar.servicios.encargos); sin bus, aquí (`encargar`). Y entonces:

    vivo y libre        se le teclea el aviso de su casilla («↯ mensaje nuevo»), salvo que su mod lo avise
    vivo y trabajando   espera en su casilla: el gancho `Stop` se lo entrega al terminar el turno
    sin sesión          se abre retomando su última conversación, con el aviso como primer mensaje; si esa
                        conversación pesa más de `[agentes] rotar_mb`, otra, que empieza leyendo su relevo

Abrir un hilo respeta `[agente] max_vivos`: si ya hay tantos hilos vivos, se cierran antes los que llevan más
rato ociosos y sin nadie mirando (`liberar`), los residentes al final y los de `residente = "siempre"` nunca.
Su conversación queda en disco y se retoma cuando haga falta: cerrar un hilo ocioso es liberar memoria, no
perder nada. Lo que pasó, en `<estado>/encargos.log`.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from telar.modelo import Atencion


class ErrorDeEncargo(Exception):
    """Un encargo que no se pudo hacer. El mensaje es para la persona."""


def _anotar(config, texto: str) -> None:
    try:
        ruta = Path(config.estado) / "encargos.log"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")
    except OSError:
        pass


# ── el tope de sesiones vivas ─────────────────────────────────────────────────

def liberar(config, nuevas: int = 1, *, cuidar: tuple[str, ...] = ()) -> list[str]:
    """Cierra hilos ociosos hasta que quepan `nuevas` bajo `[agente] max_vivos`.

    Ociosa es sin nadie mirando y sin el agente trabajando. Primero las de paso, después los
    residentes (todos los agentes residentes, y los de `cuidar`), y de cada grupo la que lleva más rato
    quieta. Devuelve los hilos cerrados."""
    tope = getattr(config.agente, "max_vivos", 0)
    if not tope:
        return []
    from telar import estado as mod_estado
    from telar import movil

    # las ventanas de la sesión del telar cuentan solo donde nadie la mira directo (un servidor)
    vivos = movil.hilos(config.sesion if movil.sin_mirar(config.sesion) else "")
    sobran = len(vivos) + nuevas - tope
    if sobran <= 0:
        return []
    est = mod_estado.abrir(config)
    atenciones = est.atenciones()
    # los residentes, al final: un periódico que abre algo de paso no cierra a Gestión para hacerse lugar. Y los
    # que están para siempre (`residente = "siempre"`), nunca: el nodo los volvería a abrir
    from telar import agentes as mod_agentes

    try:
        agentes = mod_agentes.descubrir(config, est.vinculos())
    except Exception:  # noqa: BLE001 - sin poder leerlos, al menos los de `cuidar`
        agentes = []
    residentes = {h for a in agentes if a.residente for h in a.hilos}
    siempre = {h for a in agentes if a.presencia == "siempre" for h in a.hilos}
    cuidar = (*cuidar, *residentes)
    candidatos = []
    for h in vivos:
        atencion, desde = atenciones.get(h.nombre, (Atencion.NINGUNA, None))
        if h.clientes or atencion == Atencion.TRABAJANDO or h.nombre in siempre:
            continue
        candidatos.append((h.nombre in cuidar, desde.isoformat() if desde else "", h))
    candidatos.sort(key=lambda x: (x[0], x[1]))
    cerrados = []
    for _, _, h in candidatos[:sobran]:
        try:
            movil._tmux("kill-window", "-t", h.objetivo)
        except Exception as e:  # noqa: BLE001 - una que no se deja cerrar no tumba al resto
            _anotar(config, f"no pude cerrar «{h.nombre}» ({h.direccion}): {e}")
            continue
        est.anotar_atencion(h.nombre, Atencion.NINGUNA)
        cerrados.append(h.nombre)
        _anotar(config, f"cerré «{h.nombre}» ({h.direccion}) por el tope de {tope} hilos vivos")
    return cerrados


# ── dónde vive su hilo ─────────────────────────────────────────────────────────

def _donde(ctx, hilo: str):
    """Cómo escribirle al hilo vivo de un agente: una función (texto) → None, o None si no está vivo.

    Su hilo es uno de la lista: un tab en el laptop, una ventana de la sesión del telar en un servidor."""
    from telar.ordenes import _comun

    try:
        tel = _comun.tejer(ctx, con_ficha=False)
        h = tel.por_nombre(hilo)
        if h is not None and tel.mux is not None and tel.vivo(h):
            return lambda texto: tel.mux.escribir(h.id, texto, enviar=True)
    except Exception:  # noqa: BLE001 - sin multiplexor no hay hilo vivo al que escribirle
        pass
    return None


# ── encargar y repartir ───────────────────────────────────────────────────────

def encargar(ctx, agente, texto: str, *, de: str = "") -> dict:
    """Le encarga `texto` al hilo de `agente` (un `telar.agentes.Agente`) en esta máquina, sin bus: el Encargo en
    su casilla, y que se entere (o abrir su sesión). Devuelve {hilo, estado, encargo, direccion}."""
    from telar import bus as mod_bus
    from telar import casilla
    from telar import encargo as mod_encargo
    from telar import estado as mod_estado

    texto = texto.strip()
    if not texto:
        raise ErrorDeEncargo("un encargo sin texto")
    hilo = agente.nombre
    quien = de or os.environ.get("TELAR_HILO", "").strip()
    eid = mod_encargo.nuevo_id()
    m = mod_bus.mensaje(texto, de=quien or mod_bus.persona(ctx.config), para=hilo, tipo="encargo", modo="encargo",
                        extra={"encargo": eid, "responder_a": quien})
    casilla.dejar(ctx.config, hilo, m)
    mod_encargo.anotar_enviado(ctx.config, eid, para=hilo, texto=texto, de=quien)
    salida = {"hilo": hilo, "encargo": eid, "direccion": f"encargo:{eid}", "id": m["id"]}
    est = mod_estado.abrir(ctx.config)
    escribir = _donde(ctx, hilo)
    if escribir is not None:
        if est.atencion(hilo) == Atencion.TRABAJANDO:
            _anotar(ctx.config, f"«{hilo}» trabajando: en su casilla (encargo:{eid}) · {texto[:80]}")
            return {**salida, "estado": "en su casilla"}
        if casilla.mod_vivo(ctx.config, hilo):
            _anotar(ctx.config, f"«{hilo}» libre: lo avisa su mod (encargo:{eid}) · {texto[:80]}")
            return {**salida, "estado": "avisado"}
        escribir(casilla.aviso(ctx.config, hilo))
        est.anotar_atencion(hilo, Atencion.TRABAJANDO)
        _anotar(ctx.config, f"«{hilo}» libre: avisado (encargo:{eid}) · {texto[:80]}")
        return {**salida, "estado": "avisado"}
    return {**_abrir(ctx, agente, casilla.aviso(ctx.config, hilo)), **salida}


def _abrir(ctx, agente, texto: str) -> dict:
    from telar import agente as mod_agente
    from telar import estado as mod_estado
    from telar import movil
    from telar.agente import ErrorDeAgente, lanzar

    if not ctx.config.agente.nombre:
        raise ErrorDeEncargo("encargar necesita un agente: [agente] nombre en config.toml")
    hilo = agente.nombre
    try:
        ag = mod_agente.obtener(ctx.config.agente.nombre, ctx.config)
    except ErrorDeAgente as e:
        raise ErrorDeEncargo(str(e)) from e
    from telar import rotacion

    est = mod_estado.abrir(ctx.config)
    retoma, nueva = "", ""
    for sid in est.sesiones().get(hilo, ()):
        archivo = ag.archivo_de(sid)
        if archivo is None or not Path(archivo).exists():
            continue
        if rotacion.pesada(ctx.config, archivo):
            # en frío: otra conversación, que empieza leyendo su último relevo (telar.rotacion)
            _anotar(ctx.config, f"«{hilo}»: su conversación {sid[:8]} pasó de "
                                f"{rotacion.tope(ctx.config) // (1024 * 1024)} MB; empiezo otra, con su relevo")
            texto = rotacion.con_relevo(ctx.config, agente.clave, texto)
            break
        retoma = sid
        break
    est.anotar_agente(hilo, agente.clave)
    if retoma:
        # sin texto (el nodo abre a uno que está para siempre): retoma callado, sin pedirle nada
        palabras = [*ag.retomar(mod_agente.Conversacion(id=retoma, hilo=hilo)), *([texto] if texto else [])]
    else:
        palabras, nueva = ag.nuevo_con_id(texto)
    # después del prompt: hay banderas que se tragan lo que sigue. El modelo de su agente.toml, y los
    # `argumentos` de esta máquina, que ganan si ya traen el modelo
    from telar import agentes as mod_agentes

    palabras = [*palabras, *mod_agentes.argumentos_de(agente, ag)]
    if getattr(ctx.config, "agentes_abrir", "sesion") == "tab":
        # un hilo más de la lista (el laptop): se ve y se entra como a cualquiera
        from telar.mux import ErrorDeMux
        from telar.ordenes import _comun

        tel = _comun.tejer(ctx, con_ficha=False)
        if tel.mux is None or not tel.viva:
            raise ErrorDeEncargo(tel.aviso or "la sesión no está viva: primero telar tejer")
        try:
            tel.mux.crear_tab(hilo, ruta=agente.carpeta.resolve(), comando=lanzar.envolver(palabras, hilo), foco=False)
        except ErrorDeMux as e:
            raise ErrorDeEncargo(f"no pude abrir el hilo de {hilo}: {e}") from e
        if nueva:
            lanzar.anotar(ctx.config, hilo, lanzar.Lanzamiento(comando=[], carpeta=agente.carpeta, nueva=nueva), tel.mux)
        tel.estado.vincular(hilo, _comun.ruta_relativa(agente.carpeta, tel.raiz))
        tel.estado.desarchivar(hilo)
        est.anotar_atencion(hilo, Atencion.TRABAJANDO if texto else Atencion.NINGUNA)
        _anotar(ctx.config, f"«{hilo}» sin hilo: abierto en la lista ({'retoma ' + retoma[:8] if retoma else 'conversación nueva'}) · {texto[:80]}")
        return {"hilo": hilo, "estado": "abierto", "retoma": retoma, "cerrados": []}
    cerrados = liberar(ctx.config, 1, cuidar=(hilo,))
    try:
        h = movil.crear(hilo, str(agente.carpeta.resolve()), lanzar.envolver(palabras, hilo), ctx.config.sesion)
    except (RuntimeError, OSError) as e:
        raise ErrorDeEncargo(f"no pude abrir el hilo de {hilo}: {e}") from e
    if nueva:
        lanzar.anotar(ctx.config, hilo, lanzar.Lanzamiento(comando=[], carpeta=agente.carpeta, nueva=nueva))
    est.anotar_atencion(hilo, Atencion.TRABAJANDO if texto else Atencion.NINGUNA)
    _anotar(ctx.config, f"«{hilo}» sin sesión: abierto ({'retoma ' + retoma[:8] if retoma else 'conversación nueva'})"
                        f"{' · cerré ' + ', '.join(cerrados) if cerrados else ''} · {texto[:80]}")
    return {"hilo": hilo, "estado": "abierto", "sesion": h.direccion, "retoma": retoma, "cerrados": cerrados}
