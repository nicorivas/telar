"""`telar hoy` — el día en una pantalla: qué hay, quién te espera, qué está por hacer.

Junta lo que ya saben las otras órdenes y lo pone en el orden en que sirve a las
nueve de la mañana: primero lo que tiene hora, después quién te está esperando,
después lo que está por hacer, y al final cuánto llevas.

    telar hoy              todo, consultando los proveedores declarados
    telar hoy --local      sin salir a la red: solo lo que hay en disco
    telar hoy --json       para una barra o un editor (docs/contratos.md)

Sin proveedores declarados no hay agenda, y está bien: telar no sabe de tu
calendario hasta que tu configuración nombra una fuente que lo lea.
"""

from __future__ import annotations

import datetime as dt
import shutil

from telar.modelo import Atencion
from telar.ordenes import _comun, pendientes as orden_pendientes

AYUDA = "El día en una pantalla."

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

#: Las atenciones que piden algo de la persona, en el orden en que lo piden.
LLAMAN = (Atencion.ESPERA, Atencion.TERMINO, Atencion.TRABAJANDO)


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hoy", AYUDA)
    p.epilog = __doc__
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    p.add_argument("--local", action="store_true", help="sin red: no se consulta a los proveedores")
    p.add_argument("--limite", type=int, default=8, metavar="N", help="cuántos pendientes mostrar")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    ahora = dt.datetime.now()
    hoy = ahora.date()
    tel = _comun.tejer(ctx)

    llaman = [h for h in tel.hilos if h.atencion in LLAMAN]
    llaman.sort(key=lambda h: (LLAMAN.index(h.atencion), h.nombre))

    filas = orden_pendientes.juntar(ctx, tel)
    filas.sort(key=lambda f: (not f["en_curso"], f["hilo"] or "~", f["ref"]))

    agenda: list[dict] | None = None
    fallas: list[str] = []
    declarados = [pr.nombre for pr in ctx.config.proveedores_activos()]
    if not o.local and declarados:
        externos, fallas = orden_pendientes.de_proveedores(ctx, tel, hoy)
        agenda = [e for e in externos if e["cuando"]]
        agenda.sort(key=lambda e: e["cuando"])
        filas += [e for e in externos if not e["cuando"]]

    tiempos = {h.nombre: round(h.tiempo, 1) for h in tel.hilos if h.tiempo}

    if o.json:
        return _comun.escribir_json(
            {
                "ahora": ahora.isoformat(timespec="seconds"),
                "dia": DIAS[hoy.weekday()],
                "fecha": hoy.isoformat(),
                "semana": hoy.isocalendar()[1],
                "local": o.local,
                "agenda": agenda,
                "atencion": [_comun.json_hilo(h, tel, con_ficha=False) for h in llaman],
                "pendientes": filas,
                "tiempo": {"total": round(sum(tiempos.values()), 1), "hilos": tiempos},
                "proveedores": {"declarados": declarados, "fallas": fallas},
            }
        )

    ancho = shutil.get_terminal_size((100, 24)).columns
    print(
        _comun.fuerte(f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]}")
        + _comun.tenue(f"  ·  semana {hoy.isocalendar()[1]}  ·  {ahora:%H:%M}")
    )

    print()
    print(_comun.fuerte("AGENDA"))
    if agenda is None:
        pista = "--local: no se consultó nada" if o.local else "ningún proveedor declarado"
        print(_comun.tenue(f"  {pista}"))
    elif not agenda:
        print(_comun.tenue("  nada con hora"))
    else:
        for item in agenda:
            hora = (item["cuando"] or "")[11:16]
            print(f"  {hora:>5}  {item['texto'][:ancho - 20]}  {_comun.tenue(item['hilo'])}")

    print()
    print(_comun.fuerte("TE ESPERAN"))
    if not llaman:
        print(_comun.tenue("  nadie"))
    for hilo in llaman:
        simbolo = _comun.SIMBOLO.get(hilo.atencion, " ")
        print(f"  {simbolo} {hilo.nombre[:22]:<22} {_comun.tenue(hilo.atencion.value)}")

    print()
    print(_comun.fuerte("PENDIENTES"))
    if not filas:
        print(_comun.tenue("  nada que los documentos declaren pendiente"))
    for fila in filas[: o.limite]:
        casilla = "▣" if fila["en_curso"] else "☐"
        ref = fila["ref"][:18]
        print(f"  {_comun.tenue(f'{ref:<18}')} {casilla} {fila['texto'][:ancho - 30]}")
    if len(filas) > o.limite:
        resto = len(filas) - o.limite
        print(_comun.tenue(f"  … y {resto} más (telar pendientes)"))

    if tiempos:
        total = _comun.duracion(sum(tiempos.values()))
        arriba = sorted(tiempos.items(), key=lambda kv: -kv[1])[:4]
        detalle = ", ".join(f"{n} {_comun.duracion(s)}" for n, s in arriba)
        print()
        print(_comun.fuerte("HOY") + f"  {total}  " + _comun.tenue(detalle))

    for falla in fallas:
        print(_comun.tenue(f"(proveedor caído · {falla})"))
    return 0
