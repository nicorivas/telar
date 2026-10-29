"""Las skills del agente de un hilo: las de su carpeta (y las de más arriba), las del usuario y las de los
plugins; y cuántas veces usó cada una en la conversación que tiene anotada (telar.ordenes.agente).

Lo usan `telar agente skills --json` y `GET /skills`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio


class Skills(BaseModel):
    hilo: str
    carpeta: str
    conversacion: str
    remoto: bool
    skills: list[dict]


def skills(ctx, hilo: str = "", carpeta: str = "") -> Skills:
    """Las del agente del hilo; o, con `carpeta` (relativa a la raíz) y sin hilo, las que tendría un hilo nuevo ahí
    (telar actuar: el hilo de un proyecto que todavía no está abierto)."""
    from telar.agente import ErrorDeAgente
    from telar.ordenes import _comun
    from telar.ordenes.agente import _construir

    try:
        agente = _construir(ctx.config.agente.nombre, ctx.config)
    except ErrorDeAgente as e:
        raise ErrorDeServicio(str(e), 502) from e
    if not hasattr(agente, "skills"):
        raise ErrorDeServicio(f"el agente {ctx.config.agente.nombre} no sabe listar sus skills", 501)
    tel = _comun.tejer(ctx, con_ficha=False)
    h = None
    if hilo:
        h, aviso = _comun.hilo_o_nombre(tel, hilo)
        if h is None:
            raise ErrorDeServicio(aviso, 404)
    elif not carpeta:
        h = _comun.hilo_actual(tel)
    if carpeta and h is None:
        donde = (Path(ctx.config.raiz) / carpeta.strip("/")).resolve()
        if not donde.is_relative_to(Path(ctx.config.raiz).resolve()):
            raise ErrorDeServicio(f"{carpeta}: fuera de la raíz", 400)
        carpeta = donde
    else:
        carpeta = h.ruta if h is not None and h.ruta else Path(ctx.config.raiz)
    remoto = bool(h is not None and tel.estado.remotos().get(h.nombre))
    conversacion = h.sesiones[0] if h is not None and h.sesiones else ""
    usadas = agente.usadas(conversacion) if conversacion and not remoto else {}
    lista = agente.skills(carpeta)
    for s in lista:
        s["usada"] = usadas.get(s["nombre"], 0)
    # lo que se usó y no está en disco (una skill del sistema, una ya borrada) también cuenta
    for nombre, n in usadas.items():
        if not any(s["nombre"] == nombre for s in lista):
            lista.append({"nombre": nombre, "descripcion": "", "origen": "otra", "alcance": "", "ruta": "", "usada": n})
    return Skills(hilo=h.nombre if h is not None else "", carpeta=str(carpeta), conversacion=conversacion,
                  remoto=remoto, skills=lista)
