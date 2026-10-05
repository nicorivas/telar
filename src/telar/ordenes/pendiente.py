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
nada. Si el hilo del proyecto está dormido (archivado, o sin ventana), se **retoma** con su
conversación y la frase como primer mensaje, aquí o en la máquina donde vive; y un pendiente
sin proyecto, con `[agentes] sin_proyecto = "gestion"`, se le encarga a ese agente residente
(`telar encargar`) en vez de abrir un hilo.
"""

from __future__ import annotations

import datetime as dt
import re

from telar.agente import ErrorDeAgente
from telar.agente import lanzar
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
    agente = ctx.config.agente
    texto = o.texto or mensaje(agente.pendiente, fila)
    primero = o.texto or mensaje(agente.pendiente_nuevo, fila)

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
        general = _agente_general(ctx) if destino is None and not o.nuevo else None
        if general is not None:
            print(f"{fila['ref']} → «{general.nombre}» (sin proyecto: se le encarga al agente)")
            return 0
        adonde = f"«{destino.nombre}»" if destino else "un hilo nuevo"
        vivo = "" if destino and tel.vivo(destino) and not o.nuevo else " (habría que abrirlo)"
        print(f"{fila['ref']} → {adonde}{vivo}")
        return 0

    if tel.mux is None:
        return _comun.queja(tel.aviso or "no hay multiplexor con el que hablar")

    general = _agente_general(ctx) if destino is None and not o.nuevo else None
    if general is not None:
        return _al_agente(ctx, general, fila, primero, como_json=o.json)

    hilo, creado, problema = _llevar(ctx, tel, destino, fila, nuevo=o.nuevo, primero=primero)
    if hilo is None:
        return _comun.queja(problema)

    # un hilo recién abierto con su agente ya recibió el mensaje al arrancar: escribirle
    # ahora lo haría en una terminal donde el agente todavía no está
    con_agente = creado and bool(agente.nombre)
    if con_agente:
        texto = primero
    try:
        tel.mux.ir(hilo.id)
        if not con_agente:
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
                "enviado": o.enviar or con_agente,
            }
        )
    modo = "abierto con el agente trabajándolo" if con_agente else "enviado" if o.enviar else "escrito, sin enviar"
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


def mensaje(plantilla: str, fila: dict) -> str:
    """La plantilla llena. Un pendiente sin id (los de los documentos) no tiene con qué
    llenar {id}: para ese, el texto, que es lo único que lo nombra sin ambigüedad."""
    if "{id}" in plantilla and not fila.get("id"):
        plantilla = "{texto}"
    valores = {"texto": fila.get("texto", ""), "ref": fila.get("ref", ""), "id": fila.get("id", "")}
    return re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), plantilla).strip()


def _llevar(
    ctx, tel: _comun.Telar, destino: Hilo | None, fila: dict, *, nuevo: bool, primero: str = ""
) -> tuple[Hilo | None, bool, str]:
    """El hilo donde escribir: el que ya hay, el que se revive, o uno nuevo.

    Uno nuevo nace con el agente configurado y `primero` como su primer mensaje, en la
    carpeta que diga `[agente] carpeta`. Sin agente, una shell en la carpeta del pendiente.
    """
    if destino is not None and tel.vivo(destino) and not nuevo:
        if destino.archivado:
            tel.estado.desarchivar(destino.nombre)
        return destino, False, ""
    if destino is not None and not nuevo:
        revivido, problema = _retomar(ctx, tel, destino, primero)
        if revivido is not None or problema:
            return revivido, revivido is not None, problema

    nombre = _nombre_libre(tel, destino, fila, nuevo=nuevo)
    ruta = None
    if destino is not None and destino.ruta is not None:
        ruta = destino.ruta
    elif fila.get("ruta"):
        ruta = tel.raiz / fila["ruta"]
    carpeta_hilo = ruta if ruta is not None and ruta.is_dir() else None
    lanz = None
    try:
        if ctx.config.agente.nombre:
            from telar import agente as mod_agente

            palabras, sid = mod_agente.obtener(ctx.config.agente.nombre, ctx.config).nuevo_con_id(primero)
            lanz = lanzar.Lanzamiento(
                comando=lanzar.envolver(palabras, nombre),
                carpeta=lanzar.carpeta(ctx.config, carpeta_hilo),
                nueva=sid,
            )
        abierto = tel.mux.crear(nombre, ruta=lanz.carpeta if lanz else ruta,
                                comando=lanz.comando if lanz else None)
    except (ErrorDeMux, ErrorDeAgente) as e:
        return None, False, f"no pude abrir un hilo: {e}"
    if ruta is not None:
        tel.estado.vincular(abierto.nombre, _comun.ruta_relativa(ruta, tel.raiz))
    tel.estado.desarchivar(abierto.nombre)
    if lanz is not None:
        lanzar.anotar(ctx.config, abierto.nombre, lanz)
    return abierto, True, ""


def _retomar(ctx, tel: _comun.Telar, destino: Hilo, primero: str) -> tuple[Hilo | None, str]:
    """Revivir el hilo dormido de un proyecto con su conversación y `primero` como mensaje.

    (None, "") si no tiene conversación que retomar: entonces se abre como siempre."""
    from telar import remoto as mod_remoto
    from telar.ordenes.hilo import _remoto_de

    anotado = tel.estado.remotos().get(destino.nombre)
    remoto = _remoto_de(ctx, anotado["remoto"]) if anotado else None
    if remoto is not None:
        conversacion, _ = mod_remoto.conversacion_alla(remoto, destino.nombre, list(destino.sesiones))
        if conversacion is None:
            conversacion = destino.sesiones[0] if destino.sesiones else ""
        try:
            mod_remoto.abrir(ctx, tel, destino.nombre, remoto,
                             relativa=tel.estado.vinculos().get(destino.nombre, ""),
                             sesion=anotado.get("sesion", ""), conversacion=conversacion, aviso=primero)
        except (ErrorDeMux, ErrorDeAgente) as e:
            return None, f"no pude retomar «{destino.nombre}» en {remoto.destino}: {e}"
    else:
        if not destino.sesiones or not ctx.config.agente.nombre:
            return None, ""
        try:
            lanz = lanzar.para_hilo(ctx.config, destino.nombre, destino.ruta if destino.ruta and destino.ruta.is_dir() else None,
                                    mensaje=primero)
            if lanz is None or not lanz.retoma:
                return None, ""
            tel.mux.crear(destino.nombre, ruta=lanz.carpeta, comando=lanz.comando)
        except (ErrorDeMux, ErrorDeAgente) as e:
            return None, f"no pude retomar «{destino.nombre}»: {e}"
    tel.estado.desarchivar(destino.nombre)
    revivido = next((h for h in tel.mux.hilos() if h.nombre == destino.nombre), None)
    return (revivido, "") if revivido is not None else (None, f"retomé «{destino.nombre}» pero no lo veo en la sesión")


def _agente_general(ctx):
    """El agente residente que recibe los pendientes sin proyecto (`[agentes] sin_proyecto`)."""
    clave = getattr(ctx.config, "agentes_sin_proyecto", "")
    if not clave:
        return None
    from telar import agentes as mod_agentes

    return next((a for a in mod_agentes.descubrir(ctx.config) if clave in (a.clave, a.nombre)), None)


def _al_agente(ctx, agente, fila: dict, primero: str, *, como_json: bool) -> int:
    """Le encarga el pendiente al agente y lleva a su hilo (lo trae si vive en otra máquina)."""
    import io
    import json
    from contextlib import redirect_stdout

    from telar.ordenes import encargar, remotos

    salida = io.StringIO()
    with redirect_stdout(salida):
        codigo = encargar.main([agente.clave, primero, "--json"], ctx)
    if codigo != 0:
        return codigo
    try:
        r = json.loads(salida.getvalue().strip().splitlines()[-1])
    except (ValueError, IndexError):
        r = {}
    if ctx.config.agentes_en:
        with redirect_stdout(io.StringIO()):
            remotos.main(["traer", "--remoto", ctx.config.agentes_en], ctx)
    tel = _comun.tejer(ctx, con_ficha=False)
    hilo = tel.por_nombre(agente.nombre)
    if hilo is not None and tel.mux is not None and tel.vivo(hilo):
        try:
            tel.mux.ir(hilo.id)
        except ErrorDeMux:
            pass
    if como_json:
        return _comun.escribir_json({"ref": fila["ref"], "texto": primero, "destino": agente.nombre,
                                     "creado": r.get("estado") == "abierto", "enviado": True,
                                     "encargo": r.get("estado", "")})
    print(f"{fila['ref']} → «{agente.nombre}»: encargado ({r.get('estado', '')})")
    return 0


def _nombre_libre(tel: _comun.Telar, destino: Hilo | None, fila: dict, *, nuevo: bool) -> str:
    base = (destino.nombre if destino is not None else "") or _hoja(fila) or _con_nombre(fila)
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


def _con_nombre(fila: dict) -> str:
    """El nombre de un hilo abierto solo para un pendiente: su código y de qué se trata.

    «T118» a secas no dice nada en la lista. Lo que va antes de los dos puntos suele ser el
    tema («Faro 2026: coordinar…»); si no hay, las primeras palabras.
    """
    ref = fila.get("ref", "")
    texto = " ".join(str(fila.get("texto", "")).replace("*", "").replace("`", "").split())
    tema = texto.split(":", 1)[0] if ":" in texto[:40] else texto
    if len(tema) > 28:
        tema = tema[:28].rsplit(" ", 1)[0] + "…"
    return f"{ref} {tema}".strip() if tema else ref


def _hoja(fila: dict) -> str:
    ruta = fila.get("ruta", "")
    return ruta.rstrip("/").rsplit("/", 1)[-1] if ruta else ""
