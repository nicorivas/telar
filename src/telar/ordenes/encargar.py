"""`telar encargar` — pedirle algo a un agente residente, en su hilo de siempre.

    telar encargar gestion "/avanzar T84"    un encargo (`encargo:e-…`) en su casilla: se entera si está libre,
                                             se lo entrega su gancho si trabaja, o se abre su sesión
    telar encargar --liberar                 cerrar sesiones ociosas hasta caber bajo [agente] max_vivos

El agente es la carpeta de `[agentes] carpeta` (gestion) o su nombre (Gestión). Con `[agentes] en`
(o `--en <remoto>`) se encarga en esa máquina, por ssh: los agentes suelen vivir en el servidor.
Ver `telar.encargos`.
"""

from __future__ import annotations

import sys

from telar import agentes as mod_agentes
from telar import encargos
from telar.ordenes import _comun

AYUDA = "Pedirle algo a un agente residente, en su hilo de siempre."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("encargar", AYUDA)
    p.epilog = __doc__
    p.add_argument("agente", nargs="?", default="", help="su carpeta o su nombre")
    p.add_argument("texto", nargs="*", help="el encargo (o «-» para leerlo de la entrada)")
    p.add_argument("--liberar", action="store_true", help="cerrar sesiones ociosas hasta caber bajo el tope")
    p.add_argument("--en", default=None, metavar="REMOTO", help="hacerlo en esa máquina de [remotos]; «aqui» para esta")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    # con bus, el encargo va a la casilla del agente y lo recoge su máquina, esté donde esté. Si el
    # bus no responde, por el camino de siempre (y se dice)
    if o.en is None and not o.liberar and o.agente and o.texto:
        from telar import bus as mod_bus

        if mod_bus.hay_bus(ctx.config):
            from telar.servicios import ErrorDeServicio
            from telar.servicios import encargos as servicio

            # un encargo es para un agente residente: a un nombre que no lo es, nadie lo recogería
            texto_bus = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
            try:
                r = servicio.por_el_bus(ctx, o.agente, texto_bus)
                if r.estado == "retenido":
                    if o.json:
                        return _comun.escribir_json(r.model_dump(mode="json"))
                    print(f"{r.hilo}: RETENIDO, no se entregó ({r.motivo}). Cuéntale a tu persona; ella lo suelta "
                          f"con: telar mensaje --soltar {r.id}", file=sys.stderr)
                    return 3
                if o.json:
                    return _comun.escribir_json(r.model_dump(mode="json"))
                print(f"{r.hilo}: en su casilla (bus) · {getattr(r, 'direccion', '') or 'id ' + r.id}")
                return 0
            except servicio.BusCaido as e:
                print(f"telar: {e}; voy por el camino de siempre", file=sys.stderr)
                if o.texto == ["-"]:
                    o.texto = [texto_bus]
            except ErrorDeServicio as e:
                return _comun.queja(str(e))
    if o.en is not None:
        en = o.en
    else:
        # el agente puede vivir en otra parte que los demás (`[agentes.<carpeta>] en`)
        propio = next((a for a in mod_agentes.descubrir(ctx.config) if o.agente and o.agente in (a.clave, a.nombre)), None)
        en = (propio.en if propio and propio.en else "") or ctx.config.agentes_en
    if en and en != "aqui":
        from telar.ordenes.periodicos import en_otra

        return en_otra(ctx, en, "encargar", argv)
    if o.liberar:
        cerrados = encargos.liberar(ctx.config, 0)
        if o.json:
            return _comun.escribir_json({"cerrados": cerrados})
        print(f"cerré {', '.join(cerrados)}" if cerrados else "nada que cerrar: caben bajo el tope (o no hay tope)")
        return 0
    todos = mod_agentes.descubrir(ctx.config)
    agente = next((a for a in todos if o.agente in (a.clave, a.nombre)), None)
    if agente is None:
        hay = ", ".join(a.clave for a in todos) or "ninguno: [agentes] carpeta en la configuración"
        return _comun.queja(f"no hay un agente «{o.agente}» (hay: {hay})")
    texto = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
    try:
        r = encargos.encargar(ctx, agente, texto)
    except encargos.ErrorDeEncargo as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    print(f"{agente.nombre}: {r['estado']} · {r.get('direccion', '')}"
          + (f" · cerré {', '.join(r['cerrados'])}" if r.get("cerrados") else ""))
    return 0
