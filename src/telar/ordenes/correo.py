"""`telar correo` — el correo entre agentes de las máquinas de `[remotos]`.

    telar correo                     por máquina: la dirección y los pendientes de cada hilo,
                                     y las conversaciones entre agentes
    telar correo --json
    telar correo --cuerpos --json    lo mismo, con el texto de cada correo
    telar correo --remoto casa       solo esa máquina

Lee por ssh la Maildir del usuario, el registro de su cartero y, si `[remotos.<n>]` declara
`correo_archivo`, la casilla común. No entrega ni borra nada. Ver docs/propuestas/correo-y-celular.md.
"""

from __future__ import annotations

from telar import correo as mod_correo
from telar.ordenes import _comun

AYUDA = "El correo entre agentes de las máquinas remotas: direcciones, pendientes, conversaciones."


def resumen(ctx, tel, remoto, *, cuerpos: bool = False) -> dict:
    buzon = mod_correo.leer(remoto, con_cuerpo=cuerpos, archivo=remoto.correo_archivo)
    suyos = [h.nombre for h in tel.hilos if h.remoto == remoto.nombre]
    pend = mod_correo.por_hilo(mod_correo.pendientes(buzon), suyos)
    hilos = {n: {"direccion": mod_correo.direccion(remoto, n),
                 "pendientes": [mod_correo.json_correo(c) for c in pend.get(n, [])]} for n in suyos}
    convs = []
    for grupo in mod_correo.conversaciones(list(buzon.correos)):
        estados = {c.estado for c in grupo if c.estado}
        convs.append({
            "id": grupo[0].id or grupo[0].asunto,
            "asunto": grupo[0].asunto,
            "participantes": sorted({c.de for c in grupo if c.de} | {c.para.split("@")[0] for c in grupo if c.para}),
            "mensajes": len(grupo),
            "ultima": grupo[-1].fecha,
            "estado": "retenido" if "retenido" in estados else "sin sesión" if "sin sesión" in estados
                      else "entregado" if "entregado" in estados else "",
            "correos": [mod_correo.json_correo(c) for c in grupo],
        })
    return {"remoto": remoto.nombre, "usuario": buzon.usuario, "error": buzon.error,
            "sabe_pendientes": buzon.sabe_pendientes, "cartero": bool(buzon.lineas), "archivo_comun": bool(remoto.correo_archivo),
            "hilos": hilos, "conversaciones": convs}


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("correo", AYUDA)
    p.epilog = __doc__
    p.add_argument("--remoto", default="", help="solo esa máquina de [remotos]")
    p.add_argument("--cuerpos", action="store_true", help="con el texto de cada correo")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    remotos = [r for r in ctx.config.remotos if not o.remoto or r.nombre == o.remoto]
    if not remotos:
        return _comun.queja("no hay máquinas en [remotos]" if not o.remoto else f"no hay remoto «{o.remoto}»")
    tel = _comun.tejer(ctx, con_ficha=False)
    datos = [resumen(ctx, tel, r, cuerpos=o.cuerpos) for r in remotos]
    if o.json:
        return _comun.escribir_json({"remotos": datos})
    for d in datos:
        print(_comun.fuerte(f"{d['remoto']}") + _comun.tenue(f" · {d['usuario']}"))
        if d["error"]:
            print(f"  no se pudo leer: {d['error']}")
            continue
        if not d["cartero"]:
            print(_comun.tenue("  sin cartero: el correo de este usuario no se entrega a sus agentes, queda en la Maildir"))
        elif not d["sabe_pendientes"]:
            print(_comun.tenue("  el cartero no anota el Message-Id: no se saben los pendientes"))
        for n, h in d["hilos"].items():
            marca = f"✉ {len(h['pendientes'])}" if h["pendientes"] else "  "
            print(f"  {marca} {n}  " + _comun.tenue(h["direccion"]))
        for c in d["conversaciones"][:15]:
            print(f"  · {c['asunto']}  " + _comun.tenue(f"{', '.join(c['participantes'])} · {c['mensajes']} · {c['estado'] or '?'}"))
    return 0
