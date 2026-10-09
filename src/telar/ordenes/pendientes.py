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

    fuente = _comun.fuente_ficha(ctx.config)
    if repo:
        for relativa, (arquetipo, documento) in sorted(tel.unidades.items()):
            if relativa in vistos:
                continue
            ficha = _comun.leer_ficha(documento, arquetipo, fuente)
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
    # la fecha límite que dice la viñeta (`@deadline(…)`): así vence como una tarea
    cuerpo["cuando"] = f"{pendiente.vence}T00:00" if getattr(pendiente, "vence", "") else None
    cuerpo["url"] = ""
    return cuerpo


def _local(cuando) -> str | None:
    """La hora de un ítem, en la hora de esta máquina y sin zona.

    Un proveedor de calendario entrega datetimes CON zona; escribirlos tal cual mezclaba
    en la misma lista «09:00» de aquí con «09:00» de otro huso, y `hoy` ordena y muestra
    esas cadenas. Traducir primero es lo único que hace comparable una agenda.
    """
    if cuando is None:
        return None
    if getattr(cuando, "tzinfo", None) is not None:
        cuando = cuando.astimezone().replace(tzinfo=None)
    return cuando.isoformat(timespec="minutes")


def con_area(filas: list[dict]) -> list[dict]:
    """El área de cada fila: la que dio el proveedor o, si no dio ninguna, la primera carpeta
    de su ruta (un pendiente de `trabajo/proyectos/faro/README.md` es de «trabajo»)."""
    for f in filas:
        if not f.get("area"):
            f["area"] = (f.get("ruta") or "").split("/")[0]
    return filas


def _carpeta_de(origen: str) -> str:
    """El origen de una tarea, si es una carpeta del repositorio («brinca/negocio/x»); "" si es otra
    cosa (un correo, una url, una ruta absoluta)."""
    origen = origen.strip().split("#")[0]
    if not origen or ":" in origen or origen.startswith(("/", ".", "~")) or " " in origen:
        return ""
    return origen.strip("/")


def de_proveedores(ctx, tel: _comun.Telar, dia: dt.date, *, solo: tuple[str, ...] | None = None) -> tuple[list[dict], list[str]]:
    """Lo que aportan las fuentes declaradas, ya enrutado al hilo que le toca.

    `solo` limita la consulta a esos proveedores: buscar una tarea no necesita bajar el calendario."""
    _comun.asegurar_proveedores(ctx.config)
    activos = [p for p in ctx.config.proveedores_activos() if solo is None or p.nombre in solo]
    # un proveedor que vive en otra máquina (`en`) se le pide a ella: sus archivos están allá (ver telar.alla)
    from telar import alla

    items, fallas = alla.consultar(ctx.config, activos, dia)
    # los proveedores que dan ficha (`detalle`): un clic en su tarea la abre en vez de ir al hilo
    con_ficha = {p.nombre for p in ctx.config.proveedores_activos() if p.opciones.get("detalle")}
    # un proveedor con `pestana` no suma pendientes: sus ítems van a una pestaña propia (un feed)
    pestanas = {p.nombre: str(p.opciones.get("pestana") or "") for p in ctx.config.proveedores_activos()}
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
                # la carpeta que la tarea dice que es su proyecto, haya o no un hilo ahí (la vista de proyectos)
                "proyecto": _carpeta_de(str((item.datos or {}).get("origen") or "")),
                "proveedor": item.proveedor,
                "cuando": _local(item.cuando),
                "clase": item.clase,
                "url": item.url,
                "avance": str((item.datos or {}).get("avance") or ""),
                "ficha": item.proveedor in con_ficha,
                "area": str((item.datos or {}).get("area") or ""),
                "dueno": str((item.datos or {}).get("dueno") or ""),
                # va siempre en la vista corta («esta semana»): la destaca el proveedor, o tiene estrella
                "destacada": bool((item.datos or {}).get("destacada")),
                "estrella": bool((item.datos or {}).get("estrella")),
                "color": str((item.datos or {}).get("color") or ""),
                "pestana": pestanas.get(item.proveedor, ""),
                # un evento: cuándo termina y dónde, para dibujarlo en su alto (el calendario del dashboard)
                **({"fin": str((item.datos or {}).get("fin") or ""), "lugar": str((item.datos or {}).get("lugar") or ""),
                    "todo_el_dia": bool((item.datos or {}).get("todo_el_dia")),
                    "asistentes": list((item.datos or {}).get("asistentes") or [])} if item.clase == "evento" else {}),
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
    con_area(filas)

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
