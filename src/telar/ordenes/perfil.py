"""`telar perfil` — qué declara de sí mismo el repositorio de trabajo.

Es la frontera de telar puesta por escrito: qué carpetas son unidades de trabajo,
qué archivo es su cara, qué se lee de ese archivo y qué acciones ofrece. Sin
`telar-perfil.yaml` rige la convención mínima, y esta orden lo dice en la primera
línea para que nadie crea que su perfil se está leyendo cuando no.

    telar perfil                 lo declarado
    telar perfil --documentos    y qué documentos alcanza hoy, arquetipo por arquetipo
    telar perfil --json          para quien lo consuma
"""

from __future__ import annotations

from telar.ordenes import _comun

AYUDA = "Mostrar el perfil del repositorio y qué documentos alcanza."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("perfil", AYUDA)
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    p.add_argument("--documentos", action="store_true", help="listar los documentos que alcanza")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    perfil = ctx.perfil
    raiz = ctx.config.raiz
    alcance = {a.nombre: [str(d) for d in a.documentos(raiz)] for a in perfil.arquetipos}

    if o.json:
        return _comun.escribir_json(
            {
                "nombre": perfil.nombre,
                "version": perfil.version,
                "minimo": perfil.minimo,
                "origen": str(perfil.origen) if perfil.origen else "",
                "raiz": str(raiz),
                "arquetipos": [
                    {
                        "nombre": a.nombre,
                        "descripcion": a.descripcion,
                        "ruta": a.ruta,
                        "documento": a.documento,
                        "por_carpeta": a.por_carpeta,
                        "documentos": [
                            _comun.ruta_relativa(d, raiz) for d in a.documentos(raiz)
                        ],
                        "secciones": [
                            {
                                "nombre": s.nombre,
                                "tipo": s.tipo,
                                "encabezado": s.encabezado or "",
                                "maximo": s.maximo,
                                "requerida": s.requerida,
                            }
                            for s in a.secciones
                        ],
                    }
                    for a in perfil.arquetipos
                ],
                "acciones": [
                    {
                        "nombre": a.nombre,
                        "descripcion": a.descripcion,
                        "comando": list(a.comando),
                        "tecla": a.tecla,
                        "donde": a.donde,
                        "confirmar": a.confirmar,
                    }
                    for a in perfil.acciones
                ],
            }
        )

    if perfil.minimo:
        print(_comun.fuerte("convención mínima") + _comun.tenue(f"  ·  no hay telar-perfil.yaml en {raiz}"))
        print(_comun.tenue("  el título es el primer encabezado; el estado, el primer párrafo;"))
        print(_comun.tenue("  los pendientes, la primera lista de casillas. Ver docs/perfil.md."))
    else:
        print(_comun.fuerte(perfil.nombre or "sin nombre") + _comun.tenue(f"  ·  {perfil.origen}"))

    for a in perfil.arquetipos:
        documentos = alcance[a.nombre]
        print()
        print(f"  {_comun.fuerte(a.nombre)}  {_comun.tenue(a.ruta)}  ({_comun.plural(len(documentos), "documento")})")
        if a.descripcion:
            print(f"    {a.descripcion}")
        for s in a.secciones:
            marcas = " · ".join(
                filter(None, [s.tipo, "requerida" if s.requerida else "", f"máx {s.maximo}" if s.maximo else ""])
            )
            print(f"    {s.nombre:<12} {_comun.tenue(marcas)}")
        if o.documentos:
            for d in documentos:
                print(f"      {_comun.ruta_relativa(d, raiz)}")

    if perfil.acciones:
        print()
        print(_comun.fuerte("acciones"))
        for a in perfil.acciones:
            print(f"  {a.nombre:<14} {_comun.tenue(' '.join(a.comando))}")
    return 0
