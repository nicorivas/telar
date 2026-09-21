"""`telar pendientes` — todo lo que está por hacer, junto y con su hilo al lado.

Los pendientes no los inventa telar: salen de la sección que el perfil declara
`pendientes` en cada documento, y de los proveedores que la configuración
encienda. Aquí se juntan, se les pone el hilo al que le tocan y se les da una
referencia con que agarrarlos:

    telar pendientes                   los de los hilos que hay
    telar pendientes --repo            los de todas las unidades del repositorio
    telar pendientes --proveedores     además, los que digan las fuentes declaradas
    telar pendientes --json            para una barra, un editor u otro agente

La referencia (`faro:2`) es lo que entiende `telar pendiente`, que se lleva ese
pendiente al hilo donde se trabaja. Los de un proveedor vienen con su propia
referencia estable, la que use el proveedor.
"""

from __future__ import annotations

import datetime as dt
import shutil

from telar.ordenes import _comun
from telar.proveedores import consultar

AYUDA = "Lo que está por hacer, junto y con su hilo al lado."


def juntar(ctx, tel: _comun.Telar, *, repo: bool = False, hechos: bool = False) -> list[dict]:
    """Los pendientes de los documentos: los de cada hilo, y con `repo`, los de todos.

    Devuelve diccionarios ya listos para JSON, con `ref`, `hilo` y `ruta`: es la
    misma lista que dibuja la terminal, para que no haya dos verdades.
    """
    salida: list[dict] = []
    vistos: set[str] = set()

    for hilo in tel.hilos:
        ficha = hilo.ficha
        if ficha is None or not ficha.pendientes:
            continue
        relativa = _comun.ruta_relativa(hilo.ruta, tel.raiz)
        vistos.add(relativa)
        for i, pendiente in enumerate(ficha.pendientes, 1):
            if pendiente.hecho and not hechos:
                continue
            salida.append(
                _fila(pendiente, ref=f"{hilo.nombre}:{i}", hilo=hilo.nombre, ruta=relativa)
            )

    if repo:
        for relativa, (arquetipo, documento) in sorted(tel.unidades.items()):
            if relativa in vistos:
                continue
            ficha = _comun.leer_ficha(documento, arquetipo)
            for i, pendiente in enumerate(ficha.pendientes, 1):
                if pendiente.hecho and not hechos:
                    continue
                salida.append(_fila(pendiente, ref=f"{relativa}:{i}", hilo="", ruta=relativa))

    return salida


def _fila(pendiente, *, ref: str, hilo: str, ruta: str) -> dict:
    cuerpo = _comun.json_pendiente(pendiente, ref=ref)
    cuerpo["hilo"] = hilo  # vacío si la unidad no tiene hilo abierto: la clave va igual
    cuerpo["ruta"] = ruta
    cuerpo["proveedor"] = ""
    cuerpo["cuando"] = None
    cuerpo["url"] = ""
    return cuerpo


def de_proveedores(ctx, tel: _comun.Telar, dia: dt.date) -> tuple[list[dict], list[str]]:
    """Lo que aportan las fuentes declaradas, ya enrutado al hilo que le toca."""
    _comun.asegurar_proveedores(ctx.config)
    items, fallas = consultar(list(ctx.config.proveedores_activos()), dia)
    filas = []
    for item in items:
        destino = _comun.enrutar(tel, f"{item.titulo} {item.id}", hilo=item.hilo)
        filas.append(
            {
                "texto": item.titulo,
                "hecho": False,
                "en_curso": False,
                "id": item.id,
                "origen": item.proveedor,
                "ref": item.id or f"{item.proveedor}:{item.titulo[:24]}",
                "hilo": destino.nombre if destino else "",
                "ruta": _comun.ruta_relativa(destino.ruta, tel.raiz) if destino else "",
                "proveedor": item.proveedor,
                "cuando": item.cuando.isoformat(timespec="minutes") if item.cuando else None,
                "url": item.url,
            }
        )
    return filas, fallas


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("pendientes", AYUDA)
    p.epilog = __doc__
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    p.add_argument("--repo", action="store_true", help="también los de las unidades sin hilo")
    p.add_argument("--hechos", action="store_true", help="incluir los ya marcados")
    p.add_argument("--proveedores", action="store_true", help="consultar las fuentes declaradas")
    p.add_argument("--hilo", default="", help="solo los de un hilo")
    p.add_argument("--limite", type=int, default=0, metavar="N", help="cuántos mostrar")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx)
    filas = juntar(ctx, tel, repo=o.repo, hechos=o.hechos)
    fallas: list[str] = []
    if o.proveedores:
        externos, fallas = de_proveedores(ctx, tel, dt.date.today())
        filas += externos

    if o.hilo:
        hilo, problema = _comun.resolver(tel, o.hilo)
        if hilo is None:
            return _comun.queja(problema)
        filas = [f for f in filas if f["hilo"] == hilo.nombre]

    filas.sort(key=lambda f: (not f["en_curso"], f["hilo"] or "~", f["ref"]))
    if o.limite:
        filas = filas[: o.limite]

    if o.json:
        return _comun.escribir_json(
            {
                "dia": dt.date.today().isoformat(),
                "raiz": str(tel.raiz),
                "pendientes": filas,
                "fallas": fallas,
            }
        )

    if not filas:
        print(_comun.tenue("nada pendiente en lo que telar alcanza a ver."))
        print(_comun.tenue("  `--repo` mira todas las unidades del perfil, no solo los hilos."))
        return 0

    ancho = shutil.get_terminal_size((100, 24)).columns
    en_curso = sum(1 for f in filas if f["en_curso"])
    print(_comun.fuerte(f"{len(filas)} pendientes") + _comun.tenue(f"  ·  {en_curso} en curso"))
    for fila in filas:
        casilla = "▣" if fila["en_curso"] else ("✓" if fila["hecho"] else "☐")
        ref = fila["ref"][:20]
        cola = fila["hilo"] or fila["ruta"] or fila["proveedor"]
        resto = max(ancho - 34 - len(cola), 20)
        print(f"  {_comun.tenue(f'{ref:<20}')} {casilla} {fila['texto'][:resto]:<{resto}} {_comun.tenue(cola)}")
    for falla in fallas:
        print(_comun.tenue(f"  (proveedor caído · {falla})"))
    return 0
