"""`telar actuar` — mandarle a un hilo o a un agente un prompt sobre una entidad, con su contexto.

    telar actuar proyecto:operacion/faro --skill pm                  a su hilo (se abre si no está)
    telar actuar proyecto:operacion/faro --nota "revisa el plan" --a Gestión
    telar actuar tarea:T84 --skill revisar --a Faro --escribir       queda escrito en su entrada, sin mandar
    telar actuar … --json

El prompt es la skill (si hay), lo que se pide y el contexto de la entidad: su dirección y lo que `telar objeto`
sabe de ella. Es lo que hace «Acción…» en el menú de una entidad, en la página (docs/propuestas/acciones.md).
"""

from __future__ import annotations

from telar.ordenes import _comun

AYUDA = "Mandarle a un hilo o a un agente un prompt sobre una entidad, con su contexto (y una skill, si se quiere)."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("actuar", AYUDA)
    p.add_argument("direccion", help="la entidad: proyecto:…, tarea:…, hilo:…, archivo:…")
    p.add_argument("--skill", default="", help="la skill que corre (sin /)")
    p.add_argument("--nota", default="", help="lo que se le pide")
    p.add_argument("--a", default="", help="el hilo o el agente; sin él, el hilo de la entidad (un proyecto)")
    p.add_argument("--escribir", action="store_true", help="dejarlo escrito en su entrada, sin mandarlo")
    p.add_argument("--json", action="store_true", help="lo que pasó, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    from telar.servicios import ErrorDeServicio
    from telar.servicios import actuar as servicio

    try:
        r = servicio.actuar(ctx, o.direccion, a=o.a, skill=o.skill, nota=o.nota, escribir=o.escribir)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    print(f"«{r.destino}»{' en ' + r.maquina if r.maquina else ''}: {r.como}")
    print(_comun.tenue(f"  {r.prompt}"))
    return 0
