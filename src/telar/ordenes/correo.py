"""`telar correo` — el correo entre agentes de las máquinas de `[remotos]`.

    telar correo                     por máquina: la dirección y los pendientes de cada hilo,
                                     y las conversaciones entre agentes
    telar correo --json
    telar correo --cuerpos --json    lo mismo, con el texto de cada correo
    telar correo --remoto casa       solo esa máquina
    echo "cuerpo" | telar correo enviar usuario+hilo@servidor -s "asunto" [--responde "<id>"]
                                     escribirle a un hilo de otra persona o de otra máquina

Lee por ssh la Maildir del usuario, el registro de su cartero y, si `[remotos.<n>]` declara
`correo_archivo`, la casilla común. No entrega ni borra nada. Ver docs/propuestas/correo-y-celular.md.
"""

from __future__ import annotations

import shlex

from telar import correo as mod_correo
from telar.ordenes import _comun

AYUDA = "El correo entre agentes de las máquinas remotas: direcciones, pendientes, conversaciones."


def resumen(ctx, tel, remoto, *, cuerpos: bool = False) -> dict:
    buzon = mod_correo.leer(remoto, con_cuerpo=cuerpos, archivo=remoto.correo_archivo)
    suyos = [h.nombre for h in tel.hilos if h.remoto == remoto.nombre]
    pend = mod_correo.por_hilo(mod_correo.pendientes(buzon), suyos, buzon.usuario)
    bandejas = mod_correo.por_hilo(list(buzon.correos), suyos, buzon.usuario)
    leidos = tel.estado.leidos()
    hilos = {}
    for n in suyos:
        bandeja = sorted(bandejas.get(n, []), key=lambda c: c.archivo)
        hilos[n] = {"direccion": mod_correo.direccion(remoto, n),
                    "pendientes": [mod_correo.json_correo(c) for c in pend.get(n, [])],
                    # la bandeja: lo que llegó a la dirección del hilo, y cuánto de eso no se vio
                    "correos": [{**mod_correo.json_correo(c), "leido": c.id in leidos.get(n, set())}
                                for c in bandeja],
                    "no_leidos": sum(1 for c in bandeja if c.id and c.id not in leidos.get(n, set()))}
    convs = []
    for grupo in mod_correo.conversaciones(list(buzon.correos)):
        estados = {c.estado for c in grupo if c.estado}
        convs.append({
            "id": grupo[0].id or grupo[0].asunto,
            "asunto": grupo[0].asunto,
            "participantes": sorted({c.de for c in grupo if c.de} | {u for c in grupo for u in _usuarios(c.para)}),
            "mensajes": len(grupo),
            "ultima": grupo[-1].fecha,
            "estado": "retenido" if "retenido" in estados else "sin sesión" if "sin sesión" in estados
                      else "entregado" if "entregado" in estados else "",
            "correos": [mod_correo.json_correo(c) for c in grupo],
        })
    return {"remoto": remoto.nombre, "usuario": buzon.usuario, "error": buzon.error,
            "sabe_pendientes": buzon.sabe_pendientes, "cartero": bool(buzon.lineas), "archivo_comun": bool(remoto.correo_archivo),
            "hilos": hilos, "conversaciones": convs}


def _usuarios(direcciones: str) -> set[str]:
    """Las personas de un To/Cc: `<ana+pizza@servidor>, otro@servidor` → {ana, otro}."""
    import re

    return {m.split("+", 1)[0] for m in re.findall(r"([A-Za-z0-9._+-]+)@", direcciones)}


_DIRECCION = r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+"


def enviar(ctx, direccion: str, asunto: str, cuerpo: str, *, responde: str = "", remoto: str = "") -> tuple[str, str]:
    """Manda un correo entre agentes. Devuelve (por dónde salió, error o "").

    Desde una máquina con cartero, con `mail`; desde otra, por ssh a la máquina de la
    dirección (su remitente queda verificado como el usuario de ssh). Lo que va en las
    cabeceras no puede traer saltos de línea: con uno se inyectan cabeceras nuevas.
    """
    import re
    import subprocess

    from telar.ordenes.agente import _cartero_aqui

    if not re.fullmatch(_DIRECCION, direccion):
        return "", f"«{direccion}» no es una dirección usuario[+hilo]@servidor"
    if not asunto.strip() or any(c in asunto for c in "\r\n"):
        return "", "el asunto va en una sola línea, y no vacío"
    if responde and not re.fullmatch(r"<[^<>\s]+>", responde.strip()):
        return "", f"«{responde}» no es un Message-Id (<algo@servidor>)"
    orden = ["mail", "-s", asunto.strip()]
    if responde:
        orden += ["-a", f"In-Reply-To: {responde.strip()}", "-a", f"References: {responde.strip()}"]
    orden.append(direccion)
    servidor = direccion.rsplit("@", 1)[1].split(".")[0]
    elegido = next((r for r in ctx.config.remotos if r.nombre == remoto), None) if remoto else next(
        (r for r in ctx.config.remotos if r.destino.rpartition("@")[2].split(".")[0] == servidor), None)
    if remoto and elegido is None:
        return "", f"no hay remoto «{remoto}»"
    if elegido is None and not _cartero_aqui():
        return "", f"no sé cómo llegar a {servidor}: ninguna máquina de [remotos] se llama así"
    comando = orden if elegido is None else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                                              elegido.destino, shlex.join(orden)]
    try:
        r = subprocess.run(comando, input=cuerpo, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", str(e)
    via = "aquí" if elegido is None else elegido.destino
    return via, "" if r.returncode == 0 else (r.stderr.strip() or f"mail salió con {r.returncode}")[-300:]


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("correo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", choices=("enviar", "leido"),
                   help="enviar: escribirle a un hilo · leido: marcar vista la bandeja de un hilo")
    p.add_argument("direccion", nargs="?", default="", help="con enviar: usuario+hilo@servidor")
    p.add_argument("-s", "--asunto", default="", help="con enviar: el asunto")
    p.add_argument("--responde", default="", help="con enviar: el Message-Id al que se responde")
    p.add_argument("--ids", nargs="*", default=[], help="con leido: cuáles (por defecto, toda la bandeja)")
    p.add_argument("--remoto", default="", help="solo esa máquina de [remotos]")
    p.add_argument("--cuerpos", action="store_true", help="con el texto de cada correo")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "leido":
        # `telar correo leido <hilo> [--ids <id> …]`: sin ids, todo lo que tiene hoy su bandeja
        hilo = o.direccion
        if not hilo:
            return _comun.queja("¿de qué hilo? telar correo leido <hilo>")
        tel = _comun.tejer(ctx, con_ficha=False)
        ids = list(o.ids)
        if not ids:
            for r in ctx.config.remotos:
                ids += [c["id"] for c in resumen(ctx, tel, r)["hilos"].get(hilo, {}).get("correos", [])]
        tel.estado.marcar_leidos(hilo, ids)
        if o.json:
            return _comun.escribir_json({"hilo": hilo, "leidos": len(ids)})
        print(f"«{hilo}»: {len(ids)} correo(s) marcados como leídos")
        return 0
    if o.verbo == "enviar":
        import sys

        if not o.direccion:
            return _comun.queja("¿a quién? telar correo enviar usuario+hilo@servidor -s \"asunto\" (el cuerpo por stdin)")
        cuerpo = "" if sys.stdin.isatty() else sys.stdin.read()
        via, problema = enviar(ctx, o.direccion, o.asunto, cuerpo, responde=o.responde, remoto=o.remoto)
        if problema:
            return _comun.queja(f"no se envió: {problema}")
        if o.json:
            return _comun.escribir_json({"enviado": True, "a": o.direccion, "via": via})
        print(f"enviado a {o.direccion} (por {via})")
        return 0
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
