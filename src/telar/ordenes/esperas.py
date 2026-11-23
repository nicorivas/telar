"""`telar esperas` — lo que espera una decisión tuya, junto y de lo más viejo a lo más nuevo.

    telar esperas                    una línea por espera: desde cuándo, su clase, su dirección y su título
    telar esperas --json             docs/contratos.md, «telar esperas --json» (también GET /esperas)
    telar esperas --tipo tarea       solo las de un tipo (se repite: --tipo permiso --tipo mensaje)
    telar esperas --mundo trabajo    solo las de un mundo de [mundos] (se repite; sin-clasificar, las que no calzan)

Junta lo que cada tipo de objeto dice que te espera (telar.objetos, `esperando`): el permiso o la pregunta en vivo
de un hilo (`permiso:Faro`), lo que un agente dejó para decidir en una tarea (su `avance`: `tarea:T84`), un mensaje
retenido por el freno de cadenas (`mensaje:2026…`) y lo que declare un módulo. Es de solo lectura: cada cosa se
contesta donde vive (`telar objeto <dirección>` dice cómo). Una fuente que no se pudo leer se dice al final, y las
demás salen igual. Al final, en una línea, las tareas que contestaste y que esperan al agente (su próxima pasada): no
te esperan a ti.

Si la configuración declara mundos (`[mundos]`: trabajo, personal…), salen en tandas, una por mundo en el orden en que
se declaran, y al final las que no calzan en ninguno («sin clasificar»).
"""

from __future__ import annotations

import shutil
from datetime import datetime

from telar.ordenes import _comun
from telar.servicios import ErrorDeServicio

AYUDA = "Lo que espera una decisión tuya: permisos y preguntas de los hilos, propuestas en tareas, mensajes retenidos."


def hace(desde: str, ahora: datetime | None = None) -> str:
    """`2026-11-10T09:00:00` → «7 d»: cuánto lleva esperando, corto. Vacío si no se sabe."""
    try:
        cuando = datetime.fromisoformat(desde) if desde else None
    except ValueError:
        cuando = None
    if cuando is None:
        return ""
    minutos = int(((ahora or datetime.now()) - cuando).total_seconds() // 60)
    if minutos < 1:
        return "recién"
    if minutos < 60:
        return f"{minutos} min"
    if minutos < 60 * 24:
        return f"{minutos // 60} h"
    if minutos < 60 * 24 * 14:
        return f"{minutos // (60 * 24)} d"
    return f"{minutos // (60 * 24 * 7)} sem"


def main(argv: list[str], ctx) -> int:
    from telar.servicios import esperas as servicio

    p = _comun.analizador("esperas", AYUDA)
    p.epilog = __doc__
    p.add_argument("--tipo", action="append", default=[], metavar="TIPO",
                   help="solo las de ese tipo de objeto (permiso, tarea, mensaje o el de un módulo); se repite")
    p.add_argument("--mundo", action="append", default=[], metavar="MUNDO",
                   help="solo las de ese mundo de [mundos] (sin-clasificar: las que no calzan en ninguno); se repite")
    p.add_argument("--json", action="store_true", help="los datos, en una línea (docs/contratos.md)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        r = servicio.esperas(ctx, tipos=tuple(o.tipo), mundos=tuple(o.mundo))
    except ErrorDeServicio as e:
        if o.json:
            _comun.escribir_json({"error": str(e), "codigo": e.codigo})
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    if not r.esperas:
        print("nada te espera" + ("" if not r.fallas else ", de lo que se pudo leer"))
    else:
        ancho = shutil.get_terminal_size((100, 20)).columns
        clase = max(len(e.clase) for e in r.esperas)
        direccion = min(max(len(e.direccion) for e in r.esperas), 28)
        for mundo, suyas in tandas(r.esperas, r.mundos):
            if mundo is not None:
                print(_comun.fuerte(mundo or "sin clasificar") + _comun.tenue(f"  {len(suyas)}"))
            for e in suyas:
                cabeza = f"{hace(e.desde):>6}  {e.clase:<{clase}}  {_comun.recortar(e.direccion, direccion):<{direccion}}  "
                print(_comun.tenue(cabeza[:8]) + cabeza[8:] + _comun.recortar(e.titulo, ancho - len(cabeza)))
        print(_comun.tenue(f"{_comun.plural(len(r.esperas), 'espera')}: " + ", ".join(
            f"{n} {c}" for c, n in _contar(r.esperas))))
    if r.contestadas:
        print(_comun.tenue(f"{_comun.plural(len(r.contestadas), 'contestada')} esperando al agente: ") + ", ".join(
            f"{c.direccion.removeprefix('tarea:')}" + (f" ({hace(c.cuando)})" if hace(c.cuando) else "") for c in r.contestadas))
    for tipo, motivo in r.fallas.items():
        print(_comun.amarillo(f"{tipo}: no se pudo leer entero: {motivo}"))
    return 0


def tandas(esperas, mundos) -> list[tuple[str | None, list]]:
    """Las esperas en tandas, una por mundo en el orden de la configuración y al final las sin clasificar (""), sin
    las vacías. Sin mundos declarados, una sola tanda sin nombre (None)."""
    if not mundos:
        return [(None, list(esperas))]
    salida = [(m, [e for e in esperas if e.mundo == m]) for m in mundos]
    salida.append(("", [e for e in esperas if e.mundo not in mundos]))
    return [(m, suyas) for m, suyas in salida if suyas]


def _contar(esperas) -> list[tuple[str, int]]:
    cuenta: dict[str, int] = {}
    for e in esperas:
        cuenta[e.clase] = cuenta.get(e.clase, 0) + 1
    return sorted(cuenta.items(), key=lambda x: -x[1])
