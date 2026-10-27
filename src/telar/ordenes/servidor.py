"""`telar servidor` — un lugar para ti en el servidor, que alberga hilos de varias personas (telar.alojamiento).

    telar servidor pedir [--llave RUTA]   pedir un lugar: tu usuario en el servidor, con tu propio telar y tu nodo
    telar servidor estado                 cómo va el tuyo
    telar servidor pedidos [--todos]      (quien administra) los alojamientos pedidos y su estado
    telar servidor aprobar PERSONA        (quien administra) crearle el lugar; tarda unos minutos
    telar servidor rechazar PERSONA       (quien administra)
    telar servidor quitar PERSONA         (quien administra) cerrarle el lugar; su carpeta se conserva
    telar servidor topes [PERSONA] --memoria 4G --cpu 200%
                                          (quien administra) los topes de un alojado (se aplican ya), o sin PERSONA,
                                          los de los nuevos
    telar servidor agregar DIRECCION      anotar un servidor por su dirección (IP, nombre o https://…), viendo que
                                          haya un telar ahí; después, `telar instalar --servidor DIRECCION` pide
                                          entrar a su bus (lo mismo que «pedir entrar» en «máquinas»)
    telar servidor agregados              los anotados, y en qué va el pedido para entrar a cada uno

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

VERBOS = ("pedir", "estado", "pedidos", "aprobar", "rechazar", "quitar", "topes", "agregar", "agregados")
ESTADOS = {"pendiente": "esperando que lo apruebe quien administra", "preparando": "preparando tu lugar…",
           "activo": "listo", "falló": "falló al prepararse", "rechazado": "rechazado", "quitado": "cerrado"}


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("servidor", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=VERBOS)
    p.add_argument("persona", nargs="?", default="")
    p.add_argument("--llave", default="", help="en pedir: tu llave pública ssh (el texto o su archivo)")
    p.add_argument("--todos", action="store_true", help="en pedidos: también los cerrados y rechazados")
    p.add_argument("--memoria", default="", help="en topes: la memoria (2500M, 4G)")
    p.add_argument("--cpu", default="", help="en topes: la CPU, en % de un núcleo (100%%)")
    p.add_argument("--json", action="store_true", help="lo que hay, en JSON")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo in ("agregar", "agregados"):
        return _agregados(ctx, o)
    pedido: dict = {"accion": "estado" if o.verbo == "estado" else "ver" if o.verbo == "pedidos" else o.verbo}
    if o.verbo == "pedir":
        try:
            pedido.update(_datos_de_pedir(ctx.config, o.llave))
        except ValueError as e:
            return _comun.queja(str(e))
    elif o.verbo == "topes":
        if not o.memoria or not o.cpu:
            return _comun.queja("telar servidor topes [PERSONA] --memoria 4G --cpu 200%")
        pedido.update(persona=o.persona, memoria=o.memoria, cpu=o.cpu)
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


ENTRAR = {"sin-pedir": "sin pedir entrar (telar instalar --servidor {url})", "pidiendo": "pidiendo entrar…",
          "pendiente": "pediste entrar: espera que te aprueben", "rechazado": "no te aprobaron",
          "falló": "el pedido no se hizo", "en-su-bus": "estás en su bus", "otro-bus": "estás en otro bus"}


def _agregados(ctx, o) -> int:
    from telar import servidores

    try:
        if o.verbo == "agregar":
            if not o.persona:
                return _comun.queja("¿qué dirección? telar servidor agregar 100.66.75.117 (o su nombre, o su https://…)")
            s = servidores.agregar(ctx.config, o.persona)
            if o.json:
                return _comun.escribir_json(s)
            print(f"{s['nombre']}: un servidor de telar ({s['version']}), de {s['administra'] or '?'}, bus {s['bus']}"
                  f"{' · aloja a otras personas' if s['aloja'] else ''}")
            print(_comun.tenue(f"    para pedir entrar: telar instalar --servidor {s['url']}"))
            return 0
        lista = servidores.lista(ctx.config)
    except servidores.ErrorDeServidores as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json({"servidores": lista})
    if not lista:
        print(_comun.tenue("ningún servidor agregado: telar servidor agregar DIRECCION"))
    for s in lista:
        print(f"{s['nombre']:14} {s['url']:36} {ENTRAR.get(s['estado'], s['estado']).format(url=s['url'])}")
    return 0
