"""`telar atencion` — el contrato con el agente que corre en un hilo.

telar no adivina en qué anda un agente: el agente lo dice. Son dos órdenes y un
vocabulario de cuatro palabras:

    telar atencion set trabajando    arranqué, no me interrumpas
    telar atencion set espera        te necesito: hay algo que decidir
    telar atencion set termino       terminé, pasa a ver
    telar atencion set ninguna       olvídalo, aquí no hay nadie

    telar atencion get [hilo]        qué dijo cada uno, y hace cuánto

Quién llama a `set` es cosa del agente y de sus ganchos: al arrancar una respuesta,
al pedir permiso, al terminar. Lo que telar garantiza es que queda anotado por
hilo y con hora, para que la lista de hilos pueda mostrar quién te espera.

El hilo, como siempre, sale de `$TELAR_HILO`: un agente sabe su propio hilo porque
el multiplexor se lo exportó, no porque mire cuál tiene el foco —cuando el agente
escribe, la persona ya se fue a otro tab—.
"""

from __future__ import annotations

from datetime import datetime

from telar.modelo import Atencion
from telar.ordenes import _comun

AYUDA = "Qué dice el agente de cada hilo: trabajando, espera, terminó."

ESTADOS = tuple(a.value for a in Atencion)


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("atencion", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", choices=("get", "set"), default="get")
    p.add_argument("valor", nargs="?", default="", help="con set, uno de: " + ", ".join(ESTADOS))
    p.add_argument("--hilo", default="", help="sobre cuál (por defecto, este)")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx, con_ficha=False)
    est = tel.estado

    if o.verbo == "set":
        if o.valor not in ESTADOS:
            return _comun.queja(f"«{o.valor or ''}» no es una atención; hay: {', '.join(ESTADOS)}")
        hilo = _elegir(tel, o.hilo)
        if hilo is None:
            return _comun.queja(
                f"no sé en qué hilo estoy: exporta ${_comun.VARIABLE_HILO} o usa --hilo"
            )
        est.anotar_atencion(hilo, Atencion(o.valor))
        if o.json:
            return _comun.escribir_json({"hilo": hilo, "atencion": o.valor})
        print(f"«{hilo}»: {o.valor}")
        return 0

    anotadas = est.atenciones()
    if o.hilo:
        hilo = _elegir(tel, o.hilo)
        atencion, desde = anotadas.get(hilo, (Atencion.NINGUNA, None))
        if o.json:
            return _comun.escribir_json(
                {"hilo": hilo, "atencion": atencion.value, "desde": _iso(desde)}
            )
        print(f"«{hilo}»: {atencion.value}{_hace(desde)}")
        return 0

    if o.json:
        return _comun.escribir_json(
            {
                "hilos": {
                    hilo: {"atencion": a.value, "desde": _iso(d)}
                    for hilo, (a, d) in sorted(anotadas.items())
                }
            }
        )

    if not anotadas:
        print(_comun.tenue("nadie ha dicho nada. Los agentes lo dicen con `telar atencion set`."))
        return 0
    orden = {Atencion.ESPERA: 0, Atencion.TERMINO: 1, Atencion.TRABAJANDO: 2, Atencion.NINGUNA: 3}
    for hilo, (atencion, desde) in sorted(anotadas.items(), key=lambda kv: (orden[kv[1][0]], kv[0])):
        simbolo = _comun.SIMBOLO.get(atencion, " ")
        print(f"  {simbolo} {hilo:<20} {atencion.value:<11}{_comun.tenue(_hace(desde))}")
    return 0


def _elegir(tel: _comun.Telar, referencia: str) -> str | None:
    """El nombre del hilo sobre el que se actúa. Un nombre que telar no conoce vale igual.

    Un agente puede anotar su atención antes de que el hilo aparezca en ninguna
    lista; rechazarlo por desconocido sería perder justo el primer aviso.
    """
    if referencia:
        hilo, _ = _comun.resolver(tel, referencia)
        return hilo.nombre if hilo else referencia
    actual = _comun.hilo_actual(tel)
    return actual.nombre if actual else None


def _iso(momento: datetime | None) -> str | None:
    return momento.isoformat(timespec="seconds") if momento else None


def _hace(desde: datetime | None) -> str:
    if desde is None:
        return ""
    minutos = int((datetime.now() - desde).total_seconds() // 60)
    if minutos < 1:
        return "  recién"
    if minutos < 90:
        return f"  hace {minutos} min"
    return f"  hace {minutos // 60} h"
