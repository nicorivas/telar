"""`telar pendiente` — llevar un pendiente al hilo donde se trabaja.

Un pendiente no se «abre»: se va a trabajar donde ese trabajo ya vive. Por eso
esta orden no crea un hilo por tarea; busca el hilo del proyecto al que le toca, le
pone el foco y le deja la frase escrita al agente que ya está ahí, **sin
enviarla**: quien decide apretar Enter es la persona.

    telar pendiente faro:2            al hilo del proyecto (o lo abre, si no está vivo)
    telar pendiente faro:2 --donde    solo dice adónde iría
    telar pendiente faro:2 --nuevo    fuerza un hilo nuevo aunque el proyecto tenga el suyo
    telar pendiente T84 --texto "…"   otra frase, en vez del texto del pendiente

Abrir siempre un hilo nuevo dejaba dos agentes trabajando el mismo proyecto sin
saber uno del otro. Esa es la razón de que el destino se busque antes de crear
nada.
"""

from __future__ import annotations

import datetime as dt

from telar.modelo import Hilo
from telar.mux import ErrorDeMux
from telar.ordenes import _comun, pendientes as orden_pendientes

AYUDA = "Llevar un pendiente al hilo donde se trabaja."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("pendiente", AYUDA)
    p.epilog = __doc__
    p.add_argument("ref", help="la referencia que muestra `telar pendientes` (faro:2, T84…)")
    p.add_argument("--nuevo", action="store_true", help="abrir un hilo nuevo aunque haya uno")
    p.add_argument("--donde", action="store_true", help="decir adónde iría, sin tocar nada")
    p.add_argument("--texto", default="", help="qué escribirle, en vez del texto del pendiente")
    p.add_argument("--enviar", action="store_true", help="además de escribirlo, enviarlo")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx)
    fila = _buscar(ctx, tel, o.ref)
    if fila is None:
        return _comun.queja(
            f"no encuentro el pendiente «{o.ref}». `telar pendientes` los lista con su referencia."
        )

    destino = _destino(tel, fila)
    texto = o.texto or fila["texto"]

    if o.donde:
        if o.json:
            return _comun.escribir_json(
                {
                    "ref": fila["ref"],
                    "texto": texto,
                    "destino": destino.nombre if destino else "",
                    "vivo": bool(destino and tel.vivo(destino)),
                    "ruta": fila.get("ruta", ""),
                    "nuevo": bool(o.nuevo or destino is None),
                }
            )
        adonde = f"«{destino.nombre}»" if destino else "un hilo nuevo"
        vivo = "" if destino and tel.vivo(destino) and not o.nuevo else " (habría que abrirlo)"
        print(f"{fila['ref']} → {adonde}{vivo}")
        return 0

    if tel.mux is None:
        return _comun.queja(tel.aviso or "no hay multiplexor con el que hablar")

    hilo, creado, problema = _llevar(tel, destino, fila, nuevo=o.nuevo)
    if hilo is None:
        return _comun.queja(problema)

    try:
        tel.mux.ir(hilo.id)
        tel.mux.escribir(hilo.id, texto, enviar=o.enviar)
    except ErrorDeMux as e:
        return _comun.queja(f"llegué al hilo pero no pude escribirle: {e}")
    tel.estado.marcar(hilo.nombre)

    if o.json:
        return _comun.escribir_json(
            {
                "ref": fila["ref"],
                "texto": texto,
                "destino": hilo.nombre,
                "creado": creado,
                "enviado": o.enviar,
            }
        )
    modo = "enviado" if o.enviar else "escrito, sin enviar"
    print(f"{fila['ref']} → «{hilo.nombre}»{' (nuevo)' if creado else ''}: {modo}")
    return 0


def _buscar(ctx, tel: _comun.Telar, ref: str) -> dict | None:
    """El pendiente que nombra `ref`. Los documentos primero; la red, solo si hace falta."""
    filas = orden_pendientes.juntar(ctx, tel, repo=True, hechos=True)
    directo = next((f for f in filas if f["ref"] == ref), None)
    if directo is not None:
        return directo
    porid = next((f for f in filas if f["id"] and f["id"].casefold() == ref.casefold()), None)
    if porid is not None:
        return porid
    if not ctx.config.proveedores_activos():
        return None
    externos, _ = orden_pendientes.de_proveedores(ctx, tel, dt.date.today())
    return next(
        (f for f in externos if ref in (f["ref"], f["id"]) or f["id"].casefold() == ref.casefold()),
        None,
    )


def _destino(tel: _comun.Telar, fila: dict) -> Hilo | None:
    if fila.get("hilo"):
        hilo, _ = _comun.resolver(tel, fila["hilo"])
        if hilo is not None:
            return hilo
    ruta = fila.get("ruta", "")
    if ruta:
        porruta = next(
            (h for h in tel.hilos if _comun.ruta_relativa(h.ruta, tel.raiz) == ruta), None
        )
        if porruta is not None:
            return porruta
    return _comun.enrutar(tel, f"{fila['texto']} {ruta}")


def _llevar(
    tel: _comun.Telar, destino: Hilo | None, fila: dict, *, nuevo: bool
) -> tuple[Hilo | None, bool, str]:
    """El hilo donde escribir: el que ya hay, el que se revive, o uno nuevo."""
    if destino is not None and tel.vivo(destino) and not nuevo:
        if destino.archivado:
            tel.estado.desarchivar(destino.nombre)
        return destino, False, ""

    nombre = _nombre_libre(tel, destino, fila, nuevo=nuevo)
    ruta = None
    if destino is not None and destino.ruta is not None:
        ruta = destino.ruta
    elif fila.get("ruta"):
        ruta = tel.raiz / fila["ruta"]
    try:
        abierto = tel.mux.crear(nombre, ruta=ruta)
    except ErrorDeMux as e:
        return None, False, f"no pude abrir un hilo: {e}"
    if ruta is not None:
        tel.estado.vincular(abierto.nombre, _comun.ruta_relativa(ruta, tel.raiz))
    tel.estado.desarchivar(abierto.nombre)
    return abierto, True, ""


def _nombre_libre(tel: _comun.Telar, destino: Hilo | None, fila: dict, *, nuevo: bool) -> str:
    base = (destino.nombre if destino is not None else "") or _hoja(fila) or fila["ref"]
    # revivir un hilo que telar ya conoce es volver a su nombre, no inventar otro
    if not nuevo and (destino is not None or tel.por_nombre(base) is None):
        return base
    if tel.por_nombre(base) is None:
        return base
    for i in range(2, 30):
        candidato = f"{base} {i}"
        if tel.por_nombre(candidato) is None:
            return candidato
    return f"{base} {fila['ref']}"  # pragma: no cover - treinta hilos iguales no pasa


def _hoja(fila: dict) -> str:
    ruta = fila.get("ruta", "")
    return ruta.rstrip("/").rsplit("/", 1)[-1] if ruta else ""
