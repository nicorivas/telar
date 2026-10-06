"""`telar encargar` — pedirle algo a un agente residente, en su hilo de siempre.

    telar encargar gestion "/avanzar T84"    se lo escribe si está libre, lo deja en cola si trabaja,
                                             o abre su sesión retomando su conversación
    telar encargar gestion --cola            lo que espera en su cola
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
    p.add_argument("--cola", action="store_true", help="ver lo que espera en su cola")
    p.add_argument("--liberar", action="store_true", help="cerrar sesiones ociosas hasta caber bajo el tope")
    p.add_argument("--en", default=None, metavar="REMOTO", help="hacerlo en esa máquina de [remotos]; «aqui» para esta")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    # con bus, el encargo va a la casilla del agente y lo recoge su máquina, esté donde esté. Si el
    # bus no responde, por el camino de siempre (y se dice)
    if o.en is None and not o.cola and not o.liberar and o.agente and o.texto:
        from telar import bus as mod_bus

        if mod_bus.hay_bus(ctx.config):
            from telar.ordenes import mensaje

            texto_bus = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
            try:
                r = mensaje.enviar(ctx, o.agente, texto_bus, tipo="encargo")
                salida = {"hilo": r["para"], "estado": "en su casilla (bus)", "id": r["id"]}
                if o.json:
                    return _comun.escribir_json(salida)
                print(f"{r['para']}: en su casilla (bus) · id {r['id']}")
                return 0
            except mod_bus.ErrorDeBus as e:
                print(f"telar: el bus no recibió el encargo ({e}); voy por el camino de siempre", file=sys.stderr)
                if o.texto == ["-"]:
                    o.texto = [texto_bus]
    if o.en is not None:
        en = o.en
    else:
        # el agente puede vivir en otra parte que los demás (`[agentes.<carpeta>] en`)
        propio = next((a for a in mod_agentes.descubrir(ctx.config) if o.agente and o.agente in (a.clave, a.nombre)), None)
        en = (propio.en if propio and propio.en else "") or ctx.config.agentes_en
    if en and en != "aqui":
        if any(e.nombre == en for e in ctx.config.enlaces):
            return _por_la_puerta(ctx, en, o)
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
    if o.cola:
        cola = encargos.pendientes(ctx.config, agente.nombre)
        if o.json:
            return _comun.escribir_json({"agente": agente.clave, "cola": cola})
        for x in cola:
            print(f"{x.get('desde', '')[5:16].replace('T', ' ')}  {x.get('texto', '')}")
        if not cola:
            print(_comun.tenue(f"{agente.nombre} no tiene nada en cola"))
        return 0
    import sys

    texto = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
    try:
        r = encargos.encargar(ctx, agente, texto)
    except encargos.ErrorDeEncargo as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    print(f"{agente.nombre}: {r['estado']}" + (f" ({r['en_cola']} en cola)" if r.get("en_cola") else "")
          + (f" · cerré {', '.join(r['cerrados'])}" if r.get("cerrados") else ""))
    return 0


def _por_la_puerta(ctx, nombre: str, o) -> int:
    """El agente vive al otro lado de la puerta (`[enlaces]`): el servidor le encarga al laptop."""
    import sys

    from telar import enlace as mod_enlace

    enlace = next(e for e in ctx.config.enlaces if e.nombre == nombre)
    if o.cola or o.liberar:
        return _comun.queja("por la puerta solo se encarga: la cola se mira en esa máquina")
    texto = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
    r = mod_enlace.llamar(enlace, "encargar", [o.agente], texto.encode("utf-8"))
    if not r.get("ok"):
        return _comun.queja(f"{enlace.nombre}: {r.get('error', 'no salió')}")
    r = {k: v for k, v in r.items() if k not in ("ok", "verbo")}
    if o.json:
        return _comun.escribir_json(r)
    print(f"{r.get('hilo', o.agente)}: {r.get('estado', '')} (en {enlace.nombre})" + (f" ({r['en_cola']} en cola)" if r.get("en_cola") else ""))
    return 0
