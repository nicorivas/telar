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
    en = o.en if o.en is not None else ctx.config.agentes_en
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
