"""`telar fecha` — cambiar una fecha donde vive (telar.fechas, docs/propuestas/fechas.md «Editarlas donde viven»).

    telar fecha <id> --inicio 2026-11-20            moverla (el fin se corre lo mismo)
    telar fecha <id> --fin 2026-12-01               cambiar solo su fin
    telar fecha <id> --inicio … --version 3f2a…     solo si no cambió desde que se leyó
    telar fecha <id> … --json                       la fecha como quedó

El `id` es el de `telar fechas`. Una fila de un documento cambia sus celdas, con su forma, y nada más (queda sin
commitear); una tarea, con la acción de fecha de su proveedor; la de un programa, con su `escribir`. Lo que no se
puede escribir (una plantilla, una fuente de solo lectura) lo dice y no toca nada.
"""

from __future__ import annotations

from datetime import date

from telar.ordenes import _comun

AYUDA = "Cambiar una fecha (su inicio, su fin) donde vive: la celda de su documento, su tarea, su programa."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("fecha", AYUDA)
    p.add_argument("id", help="el de telar fechas")
    p.add_argument("--inicio", default="", help="AAAA-MM-DD")
    p.add_argument("--fin", default="", help="AAAA-MM-DD")
    p.add_argument("--version", default="", help="la que traía la fecha: si cambió desde entonces, no se escribe")
    p.add_argument("--json", action="store_true", help="la fecha como quedó, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        inicio = date.fromisoformat(o.inicio) if o.inicio else None
        fin = date.fromisoformat(o.fin) if o.fin else None
    except ValueError:
        return _comun.queja("las fechas van como AAAA-MM-DD")

    from telar.servicios import ErrorDeServicio
    from telar.servicios import fechas as servicio

    try:
        r = servicio.escribir(ctx, o.id, inicio=inicio, fin=fin, version=o.version)
    except ErrorDeServicio as e:
        if o.json:
            _comun.escribir_json({"error": str(e), "codigo": e.codigo})
            return 1
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    f = r.model_dump()
    print(f"{f['id']} · {f['inicio']}" + ("" if f["fin"] == f["inicio"] else f" → {f['fin']}") + f" · {f['titulo']}")
    return 0
