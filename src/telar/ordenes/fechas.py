"""`telar fechas` — lo que tiene día, venga de donde venga (telar.fechas, docs/propuestas/fechas.md).

    telar fechas                                 todas, por orden de inicio
    telar fechas --proyecto operacion/faro       las de una unidad (y lo que tiene adentro)
    telar fechas --desde 2026-11-01 --hasta 2026-12-31
    telar fechas --json                          para un Gantt, el calendario u otro agente
    telar fechas probar <archivo>                cómo se lee un documento: con qué mapa, qué filas, cuáles no y por qué

Salen de las tablas `## Cronograma` de los documentos de las unidades, de los documentos que nombran los
`.telar/fechas.yaml` (con su mapa, que traduce su formato), y de los proveedores con `como = "fechas"` (otros
documentos, o un programa que las imprime). Las filas que parecían una fecha y no se
entendieron se dicen al final, con su archivo y su línea.
"""

from __future__ import annotations

from datetime import date

from telar.ordenes import _comun

AYUDA = "Lo que tiene día (actividades, hitos, sesiones), venga de donde venga."


def _dia(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValueError(f"se esperaba AAAA-MM-DD, llegó {texto!r}") from None


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("fechas", AYUDA)
    p.add_argument("verbo", nargs="?", choices=("probar",), help="probar: cómo se lee un documento")
    p.add_argument("archivo", nargs="?", default="", help="con probar: el documento")
    p.add_argument("--proyecto", default="", help="solo las de esa unidad (ruta relativa a la raíz)")
    p.add_argument("--desde", default="", help="solo las que terminan ese día o después (AAAA-MM-DD)")
    p.add_argument("--hasta", default="", help="solo las que empiezan ese día o antes (AAAA-MM-DD)")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        desde = _dia(o.desde) if o.desde else None
        hasta = _dia(o.hasta) if o.hasta else None
    except ValueError as e:
        return _comun.queja(str(e))

    from telar.servicios import fechas as servicio

    if o.verbo == "probar":
        return _probar(ctx, o)
    r = servicio.lista(ctx, proyecto=o.proyecto, desde=desde, hasta=hasta)
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    filas = [x.model_dump() for x in r.fechas]
    for f in filas:
        cuando = f["inicio"] if f["inicio"] == f["fin"] else f"{f['inicio']} → {f['fin']}"
        quien = f" · {f['responsable']}" if f["responsable"] else ""
        print(f"{cuando:<25} {f['titulo']}{quien}  " + _comun.tenue(f"{f['clase']} · {f['estado']} · {f['proyecto']}"))
    print(_comun.tenue(f"{len(filas)} fechas"))
    for s in r.saltadas:
        print(_comun.tenue(f"  saltada · {s}"))
    for falla in r.fallas:
        print(f"  caída · {falla}")
    return 0


def _probar(ctx, o) -> int:
    from telar.servicios import ErrorDeServicio
    from telar.servicios import fechas as servicio

    if not o.archivo:
        return _comun.queja("¿cuál? telar fechas probar <archivo>")
    try:
        r = servicio.probar(ctx, o.archivo)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    print(f"{r.archivo} · " + (f"mapa «{r.mapa}»" if r.mapa else "sin mapa (## Cronograma, por el nombre de cada columna)"))
    for f in (x.model_dump() for x in r.fechas):
        cuando = f["inicio"] if f["inicio"] == f["fin"] else f"{f['inicio']} → {f['fin']}"
        hora = f" {f['hora']}" if f["hora"] else ""
        linea = f["fuente"].rsplit(":", 1)[-1]
        print(f"  {linea:>4}  {cuando}{hora}  {f['titulo']}  "
              + _comun.tenue(f"{f['clase']} · {f['estado']} · {f['responsable'] or '—'} · {f['proyecto'] or 'sin proyecto'}"))
    print(_comun.tenue(f"{len(r.fechas)} leídas, {len(r.saltadas)} saltadas"))
    for s in r.saltadas:
        print(f"  saltada · {s}")
    for falla in r.fallas:
        print(f"  falla · {falla}")
    return 0
