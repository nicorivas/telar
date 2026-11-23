"""`telar actuar` — una instrucción: mandarle a un hilo o a un agente lo que se pide, con el contexto de una entidad.

    telar actuar proyecto:operacion/faro --skill pm                  a su hilo (se abre si no está)
    telar actuar tarea:T84 --skill tarea                             al hilo de su proyecto (o al agente de los pendientes)
    telar actuar tarea:T84 --nuevo --nota "empieza por el índice"    a un hilo nuevo para ella, en su carpeta
    telar actuar proyecto:operacion/faro --nota "revisa el plan" --a Secretaría
    telar actuar tarea:T84 --skill revisar --a Faro --escribir       queda escrito en su entrada, sin mandar
    telar actuar --a Secretaría --nota "revisa el correo"            sin entidad: solo lo pedido
    telar actuar --nuevo --nombre "✉ el informe" --nota "/correo 1a0d9"   sin entidad: un hilo nuevo en la raíz
    telar actuar --a Vigía --contexto - --titulo "Chat del equipo" < chat.txt
                                                                     sin nota: le pide procesar ese texto, entero
    telar actuar tarea:T84 --donde                                   adónde iría, sin mandar nada
    telar actuar … --json

El prompt es la skill (si hay), lo que se pide y el contexto de la entidad: su dirección y lo que `telar objeto`
sabe de ella. Con `--contexto`, además, un texto entero y con sus líneas debajo (lo que mostraba la pestaña de un
módulo); con él, la skill y la nota son opcionales. Lo que se manda sobre una tarea queda en su historia. Es lo que
hace la ventana «instrucción» de la página (docs/propuestas/instruccion.md).
"""

from __future__ import annotations

import sys

from telar.ordenes import _comun

AYUDA = "Una instrucción: mandarle a un hilo o a un agente lo que se pide, con el contexto de una entidad (y una skill)."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("actuar", AYUDA)
    p.add_argument("direccion", nargs="?", default="", help="la entidad: proyecto:…, tarea:…, hilo:…, archivo:…")
    p.add_argument("--skill", default="", help="la skill que corre (sin /)")
    p.add_argument("--nota", default="", help="lo que se le pide")
    p.add_argument("--a", default="", help="el hilo o el agente; sin él, el hilo de la entidad")
    p.add_argument("--nuevo", action="store_true", help="a un hilo nuevo para la entidad, en su carpeta (sin ella, en la raíz)")
    p.add_argument("--nombre", default="", help="sin entidad, con --nuevo: cómo se llama el hilo nuevo")
    p.add_argument("--escribir", action="store_true", help="dejarlo escrito en su entrada, sin mandarlo")
    p.add_argument("--contexto", default="", help="un texto que va entero debajo de lo pedido; «-» lo lee de la entrada")
    p.add_argument("--titulo", default="", help="con --contexto: cómo se llama lo que se manda")
    p.add_argument("--origen", default="", help="con --contexto: de dónde viene, en palabras")
    p.add_argument("--donde", action="store_true", help="decir adónde iría sin --a (su hilo), sin mandar nada")
    p.add_argument("--json", action="store_true", help="lo que pasó, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    from telar.servicios import ErrorDeServicio
    from telar.servicios import actuar as servicio

    try:
        if o.donde:
            d = servicio.adonde(ctx, o.direccion)
            if o.json:
                return _comun.escribir_json(d.model_dump(mode="json"))
            if d.falta:
                print(d.falta)
            else:
                donde = f"«{d.destino}»" if d.destino else f"un hilo nuevo en {d.carpeta or 'la raíz'}"
                print(f"{donde}{' en ' + d.maquina if d.maquina else ''}: {d.como}")
            if d.contexto:
                print(_comun.tenue(f"  {d.contexto}"))
            return 0
        texto = sys.stdin.read() if o.contexto == "-" else o.contexto
        libre = {"texto": texto, "titulo": o.titulo, "origen": o.origen} if texto.strip() else None
        r = servicio.actuar(ctx, o.direccion, a=o.a, nuevo=o.nuevo, skill=o.skill, nota=o.nota, escribir=o.escribir,
                            nombre=o.nombre, contexto=libre)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    print(f"«{r.destino}»{' en ' + r.maquina if r.maquina else ''}: {r.como}")
    # con un contexto largo, la primera línea y cuántas más: el texto entero ya lo tiene el agente
    primera, *resto = r.prompt.split("\n")
    print(_comun.tenue(f"  {primera}" + (f" (+{len(resto)} líneas de contexto)" if resto else "")))
    if r.aviso:
        print(r.aviso)
    return 0
