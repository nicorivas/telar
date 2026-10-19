"""`telar espejo` — los hilos de otra máquina, vistos desde esta (ver `telar.espejo`).

    telar espejo ver                 qué fotos hay, de quién y cuánto hace que llegaron

La foto de los hilos de cada máquina la publica su nodo (`telar nodo`) en el bus, cada 30 s: solo viajan
los hilos, con su semáforo y su carpeta, ninguna conversación. Antes se empujaba por ssh (`publicar`,
`recibir`) o se pedía por la puerta (`traer`); el bus lo reemplazó y esos caminos se retiraron.
"""

from __future__ import annotations

from telar.ordenes import _comun

AYUDA = "Los hilos de otra máquina, vistos desde esta."


def _edad(seg: float | None) -> str:
    if seg is None:
        return "—"
    if seg < 90:
        return f"{int(seg)} s"
    if seg < 5400:
        return f"{round(seg / 60)} min"
    return f"{round(seg / 3600)} h" if seg < 172800 else f"{round(seg / 86400)} d"


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("espejo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=("ver", "publicar"), help="ver (publicar ya no hace falta: lo hace el nodo)")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    if o.verbo == "publicar":
        from telar import bus as mod_bus

        if not mod_bus.hay_bus(ctx.config):
            return _comun.queja("la foto la publica `telar nodo` por el bus, y aquí no hay bus ([bus] url)")
        if o.json:
            return _comun.escribir_json({"publicado": True, "por": "bus", "maquina": "", "remoto": "", "error": ""})
        print("la foto la publica `telar nodo` por el bus; no hace falta empujarla")
        return 0

    from telar.servicios import espejos as servicio

    r = servicio.ver(ctx)
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    fotos = [f.model_dump() for f in r.espejos]
    if not fotos:
        print(_comun.tenue("ninguna máquina ha publicado aquí todavía"))
    for f in fotos:
        estado = f.get("error") or f"{'en línea' if f['en_linea'] else 'apagado'} · hace {_edad(f['edad'])} · {len(f['hilos'])} hilos"
        print(f"{f['nombre']:<16} {estado}")
    return 0
