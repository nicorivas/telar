"""`telar hoy` — el día en una pantalla: qué hay, quién te espera, qué está por hacer.

Junta lo que ya saben las otras órdenes y lo pone en el orden en que sirve a las
nueve de la mañana: primero lo que tiene hora, después quién te está esperando,
después lo que está por hacer, y al final cuánto llevas.

    telar hoy              todo, consultando los proveedores declarados
    telar hoy --local      sin salir a la red: solo lo que hay en disco
    telar hoy --json       para una barra o un editor (docs/contratos.md)
    telar hoy --dia 2026-10-08   la agenda de otro día

Sin proveedores declarados no hay agenda, y está bien: telar no sabe de tu
calendario hasta que tu configuración nombra una fuente que lo lea.
"""

from __future__ import annotations

import datetime as dt
import shutil

from telar.ordenes import _comun
from telar.servicios import hoy as servicio

AYUDA = "El día en una pantalla."

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
#: compatibilidad: quien los importaba de aquí los sigue encontrando
DIAS, LLAMAN = servicio.DIAS, servicio.LLAMAN


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hoy", AYUDA)
    p.epilog = __doc__
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    p.add_argument("--local", action="store_true", help="sin red: no se consulta a los proveedores")
    p.add_argument("--limite", type=int, default=8, metavar="N", help="cuántos pendientes mostrar")
    p.add_argument("--dia", default="", metavar="AAAA-MM-DD", help="otro día: la agenda de esa fecha (el calendario del dashboard)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    dia = None
    if o.dia:
        try:
            dia = dt.date.fromisoformat(o.dia)
        except ValueError:
            return _comun.queja(f"«{o.dia}» no es un día (AAAA-MM-DD)")

    r = servicio.hoy(ctx, dia=dia, local=o.local)
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json", exclude_unset=True))
    _imprimir(r, o.limite)
    return 0


def _imprimir(r: servicio.Hoy, limite: int) -> None:
    ancho = shutil.get_terminal_size((100, 24)).columns
    fecha = dt.date.fromisoformat(r.fecha)
    print(
        _comun.fuerte(f"{r.dia} {fecha.day} de {MESES[fecha.month - 1]}")
        + _comun.tenue(f"  ·  semana {r.semana}  ·  {r.ahora[11:16]}")
    )

    print()
    print(_comun.fuerte("AGENDA"))
    if r.agenda is None:
        pista = "--local: no se consultó nada" if r.local else "ningún proveedor declarado"
        print(_comun.tenue(f"  {pista}"))
    elif not r.agenda:
        print(_comun.tenue("  nada con hora"))
    else:
        for item in r.agenda:
            hora = (item.cuando or "")[11:16]
            print(f"  {hora:>5}  {item.texto[:ancho - 20]}  {_comun.tenue(item.hilo)}")

    print()
    print(_comun.fuerte("TE ESPERAN"))
    if not r.atencion:
        print(_comun.tenue("  nadie"))
    for hilo in r.atencion:
        simbolo = _comun.SIMBOLO.get(_comun.Atencion(hilo.atencion), " ")
        print(f"  {simbolo} {hilo.nombre[:22]:<22} {_comun.tenue(hilo.atencion)}")

    print()
    print(
        _comun.fuerte("PENDIENTES")
        + (_comun.tenue("  ·  del repositorio: ningún hilo vinculado todavía") if r.del_repo else "")
    )
    if not r.pendientes:
        print(_comun.tenue("  nada que los documentos declaren pendiente"))
    for fila in r.pendientes[:limite]:
        casilla = "▣" if fila.en_curso else "☐"
        ref = fila.ref[:18]
        print(f"  {_comun.tenue(f'{ref:<18}')} {casilla} {fila.texto[:ancho - 30]}")
    if len(r.pendientes) > limite:
        print(_comun.tenue(f"  … y {len(r.pendientes) - limite} más (telar pendientes)"))

    if r.tiempo.hilos:
        arriba = sorted(r.tiempo.hilos.items(), key=lambda kv: -kv[1])[:4]
        detalle = ", ".join(f"{n} {_comun.duracion(s)}" for n, s in arriba)
        print()
        print(_comun.fuerte("HOY") + f"  {_comun.duracion(r.tiempo.total)}  " + _comun.tenue(detalle))

    for falla in r.proveedores.fallas:
        print(_comun.tenue(f"(proveedor caído · {falla})"))
