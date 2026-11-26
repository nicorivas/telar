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

from telar import objetos
from telar.ordenes import _comun

AYUDA = "Lo que está por hacer, junto y con su hilo al lado."


def juntar(ctx, tel: _comun.Telar, *, repo: bool = False, hechos: bool = False) -> list[dict]:
    """Los pendientes de los documentos: los de cada hilo, y con `repo`, los de todos.

    Devuelve diccionarios ya listos para JSON, con `ref`, `hilo` y `ruta`: es la
    misma lista que dibuja la terminal, para que no haya dos verdades.
    """
    salida: list[dict] = []
    vistos: set[str] = set()

    # varios hilos pueden estar en la misma carpeta (el del proyecto y los de una minuta, un tema, un hijo): su
    # documento es uno, así que sus casillas van una vez, con uno de ellos. Antes iban una vez por hilo, y un
    # proyecto con cuatro hilos mostraba cada pendiente cuatro veces (y una casilla con id daba el 409 de «el id
    # se copió con la línea»). Va con el que está vivo, si hay uno: es donde se trabaja
    for hilo in sorted(tel.hilos, key=lambda h: h.nombre not in tel.vivos):
        ficha = hilo.ficha
        if ficha is None or not ficha.pendientes:
            continue
        relativa = tel.relativa(hilo.ruta)
        if relativa in vistos:
            continue
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
    # una casilla con id (telar.vinetas) se nombra por él y no por su lugar: `faro:c-1a2b3c` sigue siendo la
    # misma aunque se agreguen casillas arriba; sin id, su lugar en el documento (`faro:2`), como siempre
    ident = getattr(pendiente, "id_casilla", "")
    if ident:
        ref = f"{ref.rsplit(':', 1)[0]}:{ident}"
    cuerpo = _comun.json_pendiente(pendiente, ref=ref)
    cuerpo["hilo"] = hilo  # vacío si la unidad no tiene hilo abierto: la clave va igual
    cuerpo["ruta"] = ruta
    cuerpo["proveedor"] = ""
    # y su dirección, `pendiente:c-1a2b3c`, que no cambia aunque el documento cambie. Sin id, ninguna: su `ref`
    # sirve para el minuto siguiente, no para guardarla
    cuerpo["direccion"] = objetos.direccion_de("pendiente", ident) if ident else ""
    # si otras casillas del documento dicen lo mismo, cuál es de ellas (telar.lectura): con eso se le escribe
    # a esta y no a otra. None si es la única con ese texto
    de = getattr(pendiente, "de", 0)
    cuerpo["repetida"] = {"cual": pendiente.cual, "de": de} if de > 1 else None
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


def con_mundo(config, filas: list[dict]) -> list[dict]:
    """El mundo de cada fila (telar.mundos, `[mundos]`): una tarea de un proveedor, por su área y su proyecto; una
    casilla de un documento, por la carpeta del documento. Va antes de `con_area`, que inventa un área de la ruta del
    hilo al que se llevaría la tarea (y ese hilo sale de su título)."""
    from telar import mundos

    for f in filas:
        f["mundo"] = mundos.de_fila(config, f)
    return filas


def _carpeta_de(origen: str) -> str:
    """El origen de una tarea, si es una carpeta del repositorio («trabajo/negocio/x»); "" si es otra
    cosa (un correo, una url, una ruta absoluta)."""
    origen = origen.strip().split("#")[0]
    if not origen or ":" in origen or origen.startswith(("/", ".", "~")) or " " in origen:
        return ""
    return origen.strip("/")


def _de_otro(datos: dict) -> dict:
    """A quién espera una tarea (`espera`, sin la @), desde cuándo la tiene otro (`desde`) y lo último que le pasó
    (`ultimo`: fecha, clase y texto), lo que el proveedor diga; nada de lo que no diga, para no engordar cada fila."""
    salida: dict = {}
    espera = str(datos.get("espera") or "").strip().lstrip("@")
    if espera:
        salida["espera"] = espera
    if datos.get("desde"):
        salida["desde"] = str(datos["desde"])
    u = datos.get("ultimo")
    if isinstance(u, dict) and u.get("texto"):
        salida["ultimo"] = {"fecha": str(u.get("fecha") or ""), "tipo": str(u.get("tipo") or ""), "texto": str(u["texto"])}
    return salida


def de_proveedores(ctx, tel: _comun.Telar, dia: dt.date, *, solo: tuple[str, ...] | None = None) -> tuple[list[dict], list[str]]:
    """Lo que aportan las fuentes declaradas, ya enrutado al hilo que le toca.

    `solo` limita la consulta a esos proveedores: buscar una tarea no necesita bajar el calendario."""
    _comun.asegurar_proveedores(ctx.config)
    activos = [p for p in ctx.config.proveedores_activos() if solo is None or p.nombre in solo]
    # un proveedor que vive en otra máquina (`en`) se le pide a ella: sus archivos están allá (ver telar.alla)
    from telar import alla

    items, fallas = alla.consultar(ctx.config, activos, dia)
    # los proveedores que dan ficha (`detalle`, o los del tipo `tarea`, que la arman ellos): un clic en su
    # tarea la abre en vez de ir al hilo
    con_ficha = {p.nombre for p in ctx.config.proveedores_activos()
                 if p.opciones.get("detalle") or p.opciones.get("tipo") == "tipo"}
    # los del tipo `tarea` dan objetos con dirección (`tarea:T84`, telar.objetos); los demás, ítems sueltos
    del_tipo = {p.nombre for p in ctx.config.proveedores_activos() if p.opciones.get("tipo") == "tipo"}
    # un proveedor con `pestana` no suma pendientes: sus ítems van a una pestaña propia (un feed)
    pestanas = {p.nombre: str(p.opciones.get("pestana") or "") for p in ctx.config.proveedores_activos()}
    # el área de los ítems que no traen la suya (un calendario del trabajo): con ella, su mundo (`[mundos] areas`)
    areas = {p.nombre: str(p.opciones.get("area") or "") for p in ctx.config.proveedores_activos()}
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
                "direccion": objetos.direccion_de("tarea", item.id) if item.proveedor in del_tipo and item.id else "",
                "hilo": destino.nombre if destino else "",
                "ruta": tel.relativa(destino.ruta) if destino else "",
                # la carpeta que la tarea dice que es su proyecto, haya o no un hilo ahí (la vista de proyectos)
                "proyecto": _carpeta_de(str((item.datos or {}).get("origen") or "")),
                "proveedor": item.proveedor,
                "cuando": _local(item.cuando),
                "clase": item.clase,
                "url": item.url,
                "avance": str((item.datos or {}).get("avance") or ""),
                "ficha": item.proveedor in con_ficha,
                "area": str((item.datos or {}).get("area") or areas.get(item.proveedor, "")),
                "dueno": str((item.datos or {}).get("dueno") or ""),
                # cuánto toma: «rapida» o «larga» («foco» las separa en gestión y concentración); "" sin decir
                "tamano": str((item.datos or {}).get("tamano") or ""),
                # va siempre en la vista corta («esta semana»): la destaca el proveedor, o tiene estrella
                "destacada": bool((item.datos or {}).get("destacada")),
                "estrella": bool((item.datos or {}).get("estrella")),
                # de P0 (la más alta) a P3; None si el proveedor no la dice
                "prioridad": (item.datos or {}).get("nivel") if (item.datos or {}).get("nivel") in (0, 1, 2, 3) else None,
                # sus etiquetas: «equipo» la comparte con el equipo (la vista pinta ◉ u ○)
                "etiquetas": [str(e) for e in (item.datos or {}).get("etiquetas") or []],
                "color": str((item.datos or {}).get("color") or ""),
                "pestana": pestanas.get(item.proveedor, ""),
                # quién lo dejó y de cuándo es (AAAA-MM-DD), si el proveedor lo dice: una pestaña de lectura se ordena
                # con ellos (lo que se mandó la persona primero, lo más nuevo arriba)
                "de": str((item.datos or {}).get("de") or ""),
                "fecha": str((item.datos or {}).get("fecha") or ""),
                # a quién espera, desde cuándo la tiene otro y lo último que pasó (la vista «esperando»: lo que otros le
                # deben a la persona); solo si el proveedor lo dice
                **_de_otro(item.datos or {}),
                # un evento: cuándo termina y dónde, para dibujarlo en su alto (el calendario del dashboard), y lo que
                # la persona respondió a la invitación («aceptada», «rechazada», «tentativa», «sin_responder»; "" si no aplica)
                **({"fin": str((item.datos or {}).get("fin") or ""), "lugar": str((item.datos or {}).get("lugar") or ""),
                    "todo_el_dia": bool((item.datos or {}).get("todo_el_dia")),
                    "asistentes": list((item.datos or {}).get("asistentes") or []),
                    "respuesta": str((item.datos or {}).get("respuesta") or "")} if item.clase == "evento" else {}),
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
    p.add_argument("--mundo", action="append", default=[], metavar="MUNDO",
                   help="solo los de ese mundo de [mundos] (sin-clasificar: los que no calzan en ninguno); se repite")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    from telar.servicios import ErrorDeServicio
    from telar.servicios import pendientes as servicio

    try:
        r = servicio.pendientes(ctx, repo=o.repo, hechos=o.hechos, proveedores=o.proveedores, hilo=o.hilo,
                                limite=o.limite, mundos=tuple(o.mundo))
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    filas = [f.model_dump() for f in r.pendientes]
    fallas = r.fallas

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
