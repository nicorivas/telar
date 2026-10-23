"""`telar servidor` — un lugar para ti en el servidor, que alberga hilos de varias personas (telar.alojamiento).

    telar servidor pedir [--llave RUTA]   pedir un lugar: tu usuario en el servidor, con tu propio telar y tu nodo
    telar servidor estado                 cómo va el tuyo
    telar servidor pedidos [--todos]      (quien administra) los alojamientos pedidos y su estado
    telar servidor aprobar PERSONA        (quien administra) crearle el lugar; tarda unos minutos
    telar servidor rechazar PERSONA       (quien administra)
    telar servidor quitar PERSONA         (quien administra) cerrarle el lugar; su carpeta se conserva

Hace falta estar en el bus (`telar instalar --unirse`). Con un lugar, el servidor es una máquina más tuya: tus hilos
nacen y viven ahí (se siguen abriendo con «hilo nuevo» en esa máquina, o `telar ir X --crear --maquina …`) y los ves
desde tu laptop por el bus. Lo de cada persona queda aparte: su usuario, sus archivos, su cuenta del bus. `pedir`
manda a ese servidor tu secreto del bus (`[bus] token`) —una vez, por el bus—, porque tu nodo allá lo necesita; el
servidor lo comprueba contra tu cuenta y lo borra al instalarlo. `--llave` suma una llave ssh para entrar además por
ssh/mosh (opcional: la página del servidor alcanza para abrir tus hilos).
"""

from __future__ import annotations

import json
import time

from telar import alojamiento
from telar import bus as mod_bus
from telar.ordenes import _comun

AYUDA = "Un lugar para ti en el servidor, que alberga hilos de varias personas."

VERBOS = ("pedir", "estado", "pedidos", "aprobar", "rechazar", "quitar")
ESTADOS = {"pendiente": "esperando que lo apruebe quien administra", "preparando": "preparando tu lugar…",
           "activo": "listo", "falló": "falló al prepararse", "rechazado": "rechazado", "quitado": "cerrado"}


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("servidor", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=VERBOS)
    p.add_argument("persona", nargs="?", default="")
    p.add_argument("--llave", default="", help="en pedir: tu llave pública ssh (el texto o su archivo)")
    p.add_argument("--todos", action="store_true", help="en pedidos: también los cerrados y rechazados")
    p.add_argument("--json", action="store_true", help="lo que hay, en JSON")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    pedido: dict = {"accion": "estado" if o.verbo == "estado" else "ver" if o.verbo == "pedidos" else o.verbo}
    if o.verbo == "pedir":
        try:
            pedido.update(_datos_de_pedir(ctx.config, o.llave))
        except ValueError as e:
            return _comun.queja(str(e))
    elif o.verbo in ("aprobar", "rechazar", "quitar"):
        if not o.persona:
            return _comun.queja(f"¿quién? telar servidor {o.verbo} PERSONA (telar servidor pedidos los lista)")
        pedido["persona"] = o.persona
    try:
        r = alojamiento.pedir(ctx.config, pedido)
    except alojamiento.ErrorDeAlojamiento as e:
        return _comun.queja(str(e))
    if o.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0
    if r.get("hecho"):
        print(f"{r['hecho']}.")
    if o.verbo == "pedir":
        print(_comun.tenue("cuando lo apruebe, telar servidor estado te dice; tu laptop ve la máquina nueva sola"))
        return 0
    if o.verbo == "aprobar":
        print(_comun.tenue("telar servidor pedidos muestra cuándo termina"))
        return 0
    if o.verbo in ("rechazar", "quitar"):
        return 0
    _mostrar(r, todos=o.todos, propio=o.verbo == "estado", yo=mod_bus.persona(ctx.config))
    return 0


def _datos_de_pedir(config, llave: str) -> dict:
    return alojamiento.datos_de_pedir(config, llave)


def _mostrar(r: dict, *, todos: bool, propio: bool, yo: str) -> None:
    filas = [a for a in r["alojamientos"] if todos or a["estado"] not in ("rechazado", "quitado")]
    if propio:
        filas = [a for a in r["alojamientos"] if a["persona"] == yo]
        if not filas:
            print(_comun.tenue("no has pedido un lugar: telar servidor pedir"))
            return
    for a in filas:
        cuando = time.strftime("%d-%m %H:%M", time.localtime(a.get("cuando", 0)))
        extra = f" · puerto {a['puerto']}" if a.get("puerto") and a["estado"] in ("preparando", "activo") else ""
        print(f"{a['persona']:<16} {a['estado']:<11} {cuando}  " + _comun.tenue(ESTADOS.get(a["estado"], "") + extra))
        if a.get("error"):
            print(f"{'':<16} {_comun.rojo(a['error'])}")
    if not filas:
        print(_comun.tenue("nadie pidió un lugar" if not r["alojamientos"] else "nada vigente (--todos: también los cerrados)"))
