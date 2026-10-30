"""`telar pendiente` — llevar un pendiente al hilo donde se trabaja.

Un pendiente no se «abre»: se va a trabajar donde ese trabajo ya vive. Por eso
esta orden no crea un hilo por tarea; busca el hilo del proyecto al que le toca, le
pone el foco y le deja la frase escrita al agente que ya está ahí, **sin
enviarla**: quien decide apretar Enter es la persona.

    telar pendiente faro:2            al hilo del proyecto (o lo abre, si no está vivo)
    telar pendiente faro:2 --donde    solo dice adónde iría
    telar pendiente faro:2 --nuevo    fuerza un hilo nuevo aunque el proyecto tenga el suyo
    telar pendiente T84 --texto "…"   otra frase, en vez del texto del pendiente
    telar pendiente faro:2 --hecho              marca la casilla en su documento ([ ] → [x])
    telar pendiente faro:2 --responsable "Ana"  dice quién la hace (@owner(Ana)); «none» lo quita
    telar pendiente faro:2 --linea              en qué archivo y línea está
    telar pendiente c-1a2b3c --hecho            una casilla con id, por su id (o `pendiente:c-1a2b3c`)

Abrir siempre un hilo nuevo dejaba dos agentes trabajando el mismo proyecto sin
saber uno del otro. Esa es la razón de que el destino se busque antes de crear
nada. Si el hilo del proyecto está dormido (archivado, o sin ventana), se **retoma** con su
conversación y la frase como primer mensaje, aquí o en la máquina donde vive; y un pendiente
sin proyecto, con `[agentes] sin_proyecto = "gestion"`, se le encarga a ese agente residente
(`telar encargar`) en vez de abrir un hilo.

La primera vez que telar escribe una casilla (`--hecho`, `--responsable`) le pone un id al final de la línea,
`<!-- id: c-1a2b3c -->` (telar.vinetas): desde ahí se la encuentra por ese id aunque el documento cambie, y
su dirección es `pendiente:c-1a2b3c` (`telar objeto`).
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


def main(argv: list[str], ctx, *, fila: dict | None = None) -> int:
    """`fila`: el pendiente ya encontrado (lo pasa `telar tarea` cuando la acción lo cierra antes de
    llevar el mensaje: cerrado, su proveedor ya no lo lista y no se lo encontraría)."""
    p = _comun.analizador("pendiente", AYUDA)
    p.epilog = __doc__
    p.add_argument("ref", help="la referencia que muestra `telar pendientes` (faro:2, T84…)")
    p.add_argument("--nuevo", action="store_true", help="abrir un hilo nuevo aunque haya uno")
    p.add_argument("--donde", action="store_true", help="decir adónde iría, sin tocar nada")
    p.add_argument("--texto", default="", help="qué escribirle, en vez del texto del pendiente")
    p.add_argument("--enviar", action="store_true", help="además de escribirlo, enviarlo")
    p.add_argument("--proveedor", default="", help="de qué proveedor es (más rápido: no pregunta a los demás)")
    p.add_argument("--hecho", action="store_true", help="una casilla de un documento: marcarla hecha")
    p.add_argument("--responsable", default=None, metavar="NOMBRE",
                   help="una casilla de un documento: quién la hace (@owner); «none» lo quita")
    p.add_argument("--linea", action="store_true", help="una casilla de un documento: en qué archivo y línea está")
    p.add_argument("--esperado", default="", metavar="TEXTO",
                   help="el texto que se vio: si la casilla ya no dice eso, no se toca (el documento cambió)")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    from telar.servicios import ErrorDeServicio

    try:
        if o.hecho or o.responsable is not None or o.linea:
            datos, linea = en_su_documento(ctx, o.ref, hecho=o.hecho, responsable=o.responsable, linea=o.linea,
                                           esperado=o.esperado, proveedor=o.proveedor, fila=fila)
        else:
            datos, linea = llevar(ctx, o.ref, nuevo=o.nuevo, donde=o.donde, texto=o.texto, enviar=o.enviar,
                                  proveedor=o.proveedor, fila=fila)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(datos)
    print(linea)
    return 0


def _encontrar(ctx, tel, ref: str, proveedor: str, fila: dict | None) -> dict:
    from telar.servicios import ErrorDeServicio

    fila = fila or _buscar(ctx, tel, ref, proveedor=proveedor)
    if fila is None:
        raise ErrorDeServicio(f"no encuentro el pendiente «{ref}». `telar pendientes` los lista con su referencia.", 404)
    return fila


def llevar(ctx, ref: str, *, nuevo: bool = False, donde: bool = False, texto: str = "", enviar: bool = False,
           proveedor: str = "", fila: dict | None = None, a: str = "") -> tuple[dict, str]:
    """Lleva el pendiente al hilo donde se trabaja (o solo dice adónde, con `donde`). (lo que pasó, en el
    contrato de `--json`; y en una línea, para la terminal). `ErrorDeServicio` si no se pudo.

    Con `a`, a ese hilo o agente (su nombre exacto, de esta máquina o de otra) y no al de la tarea."""
    from telar.servicios import ErrorDeServicio

    tel = _comun.tejer(ctx)
    fila = _encontrar(ctx, tel, ref, proveedor, fila)
    elegido = None
    if a:
        destino, alla, elegido = destino_elegido(ctx, tel, a)
    else:
        destino = _destino(tel, fila)
        # sin hilo aquí, el de otra máquina (la foto de su espejo): se le escribe por el bus
        alla = _destino_remoto(ctx, fila) if destino is None and not nuevo else None
    agente = ctx.config.agente
    fila = _con_direccion(ctx, fila)
    primero = texto or mensaje(agente.pendiente_nuevo, fila)
    texto = texto or mensaje(agente.pendiente, fila)

    if alla is not None:
        nombre, maquina = alla
        if donde:
            return ({"ref": fila["ref"], "texto": texto, "destino": nombre, "maquina": maquina, "vivo": True,
                     "ruta": fila.get("ruta", ""), "nuevo": False}, f"{fila['ref']} → «{nombre}» (en {maquina}: por el bus)")
        from telar import bus as mod_bus

        try:
            m = mod_bus.enviar(ctx.config, nombre, texto, de="el dashboard", tipo="persona")
        except mod_bus.ErrorDeBus as e:
            raise ErrorDeServicio(f"«{nombre}» vive en {maquina} y el bus no lo llevó: {e}", 502) from e
        return ({"ref": fila["ref"], "texto": texto, "destino": nombre, "maquina": maquina, "creado": False,
                 "enviado": True, "id": m["id"]}, f"{fila['ref']} → «{nombre}» en {maquina}: en su casilla (bus)")

    general = elegido if a else _agente_general(ctx) if destino is None and not nuevo else None
    if donde:
        datos = {"ref": fila["ref"], "texto": texto, "destino": destino.nombre if destino else "",
                 "vivo": bool(destino and tel.vivo(destino)), "ruta": fila.get("ruta", ""),
                 "nuevo": bool(nuevo or destino is None)}
        if general is not None:
            return datos, f"{fila['ref']} → «{general.nombre}» (sin proyecto: se le encarga al agente)"
        adonde = f"«{destino.nombre}»" if destino else "un hilo nuevo"
        vivo = "" if destino and tel.vivo(destino) and not nuevo else " (habría que abrirlo)"
        return datos, f"{fila['ref']} → {adonde}{vivo}"

    if tel.mux is None:
        raise ErrorDeServicio(tel.aviso or "no hay multiplexor con el que hablar", 409)
    if general is not None and a:
        # elegido a mano («Acción…» a un agente): se le encarga, en su hilo de siempre
        from telar.servicios import encargos

        r = encargos.encargar_y_ir(ctx, general, primero)
        return ({"ref": fila["ref"], "texto": primero, "destino": general.nombre, "creado": r.estado == "abierto",
                 "enviado": True, "encargo": r.estado}, f"{fila['ref']} → «{general.nombre}»: encargado ({r.estado})")
    if general is not None:
        # sin proyecto, al agente de los pendientes: un hilo hijo suyo para esta tarea (telar.hijos), no la cola de su
        # hilo de siempre, donde se mezclaban todas
        from telar import hijos

        r = hijos.abrir(ctx, general, fila["ref"], fila.get("texto", ""), primero)
        donde = f" en {r['maquina']}" if r["maquina"] else ""
        return ({"ref": fila["ref"], "texto": primero, "destino": r["hilo"], "maquina": r["maquina"], "creado": r["nuevo"],
                 "enviado": True, "hijo_de": general.nombre},
                f"{fila['ref']} → «{r['hilo']}»{donde}: {'hilo nuevo, hijo de ' + general.nombre if r['nuevo'] else 'su hilo, ya abierto'}")

    hilo, creado, problema = _llevar(ctx, tel, destino, fila, nuevo=nuevo, primero=primero)
    if hilo is None:
        raise ErrorDeServicio(problema, 502)
    # un hilo recién abierto con su agente ya recibió el mensaje al arrancar: escribirle
    # ahora lo haría en una terminal donde el agente todavía no está
    con_agente = creado and bool(agente.nombre)
    if con_agente:
        texto = primero
    try:
        tel.mux.ir(hilo.id)
        if not con_agente:
            tel.mux.escribir(hilo.id, texto, enviar=enviar)
    except ErrorDeMux as e:
        raise ErrorDeServicio(f"llegué al hilo pero no pude escribirle: {e}", 502) from e
    tel.estado.marcar(hilo.nombre)
    modo = "abierto con el agente trabajándolo" if con_agente else "enviado" if enviar else "escrito, sin enviar"
    return ({"ref": fila["ref"], "texto": texto, "destino": hilo.nombre, "creado": creado,
             "enviado": enviar or con_agente}, f"{fila['ref']} → «{hilo.nombre}»{' (nuevo)' if creado else ''}: {modo}")


def _buscar(ctx, tel: _comun.Telar, ref: str, *, proveedor: str = "") -> dict | None:
    """El pendiente que nombra `ref`. Los documentos primero; la red, solo si hace falta.

    Los proveedores se consultan de a uno (el que se nombró, primero) y se para en el primero que
    lo tiene: consultarlos todos juntos bajaba el calendario entero para encontrar una tarea."""
    def calza(f):
        return ref in (f["ref"], f["id"]) or (f["id"] and f["id"].casefold() == ref.casefold())

    if proveedor:
        externos, _ = orden_pendientes.de_proveedores(ctx, tel, dt.date.today(), solo=(proveedor,))
        hallado = next((f for f in externos if calza(f)), None)
        if hallado is not None:
            return hallado
    filas = orden_pendientes.juntar(ctx, tel, repo=True, hechos=True)
    directo = next((f for f in filas if f["ref"] == ref), None)
    if directo is not None:
        return directo
    # una ref por lugar (`faro:2`) de una casilla que desde entonces tiene id, y por eso se llama `faro:c-1a2b3c`:
    # la que sigue estando en ese lugar del documento (las filas vienen en su orden, hechas incluidas)
    if (m := re.fullmatch(r"(.+):(\d+)", ref)):
        de_ahi = [f for f in filas if not f.get("proveedor") and f["ref"].rsplit(":", 1)[0] == m.group(1)]
        if 0 < int(m.group(2)) <= len(de_ahi):
            return de_ahi[int(m.group(2)) - 1]
    # una casilla con id, por su dirección (`pendiente:c-1a2b3c`) o por el id solo, si tiene la forma de los
    # que pone telar (`c-1a2b3c`): uno puesto a mano (`<!-- id: T84 -->`) no le gana a la tarea T84 de un
    # proveedor; se lo nombra con su dirección, o se llega a él al final, si ningún proveedor lo tiene
    from telar import vinetas

    if ref.startswith("pendiente:") or vinetas.FORMA_ID.fullmatch(ref):
        pordireccion = por_direccion(filas, ref)
        if pordireccion is not None:
            return pordireccion
    porid = next((f for f in filas if f["id"] and f["id"].casefold() == ref.casefold()), None)
    if porid is not None:
        return porid
    for p in ctx.config.proveedores_activos():
        if p.nombre == proveedor:
            continue
        externos, _ = orden_pendientes.de_proveedores(ctx, tel, dt.date.today(), solo=(p.nombre,))
        hallado = next((f for f in externos if calza(f)), None)
        if hallado is not None:
            return hallado
    return por_direccion(filas, ref)


def por_direccion(filas: list[dict], ref: str) -> dict | None:
    """La fila de la casilla con id que nombra `ref` (su dirección, `pendiente:c-1a2b3c`, o el id solo); None
    si no hay. El id es único dentro de un documento, no entre documentos: una línea copiada con su comentario
    a otro proyecto (o un README de plantilla) deja dos con el mismo. Esas no se adivinan —escribir la primera
    que aparece podía marcar la del documento equivocado—: `ErrorDeServicio` 409, con dónde está cada una."""
    from telar import objetos
    from telar.servicios import ErrorDeServicio

    estable = ref if ref.startswith("pendiente:") else objetos.direccion_de("pendiente", ref)
    halladas = [f for f in filas if f.get("direccion") and not f.get("proveedor") and f["direccion"] == estable]
    if len(halladas) > 1:
        donde = ", ".join(sorted({f.get("ruta") or f["ref"] for f in halladas}))
        raise ErrorDeServicio(f"hay {len(halladas)} casillas con la dirección {estable} (en {donde}): el id se copió "
                              "con la línea. Nómbrala por su ref (`telar pendientes --repo`) o bórrale el id a la copia", 409)
    return halladas[0] if halladas else None


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
    por_enlace = _por_enlace([(h, _comun.ruta_relativa(h.ruta, tel.raiz), tel.vivo(h)) for h in tel.hilos], fila.get("url", ""))
    if por_enlace is not None:
        return por_enlace
    return _comun.enrutar(tel, f"{fila['texto']} {ruta}")


def _por_enlace(candidatos: list[tuple[object, str, bool]], url: str):
    """El hilo cuya carpeta contiene el archivo al que apunta el pendiente (su `url`, si es una ruta
    de la casa): la más específica gana, y entre iguales la viva. Una carpeta de un solo nivel
    («trabajo») es un área, no un proyecto: no decide."""
    if not url or "://" in url or url.startswith("/"):
        return None
    rel = url.strip().lstrip("./")
    mejores = [(len(r), vivo, x) for x, r, vivo in candidatos
               if r and "/" in r and not r.startswith("..") and (rel == r or rel.startswith(r.rstrip("/") + "/"))]
    if not mejores:
        return None
    return max(mejores, key=lambda t: (t[0], t[1]))[2]


def _destino_remoto(ctx, fila: dict) -> tuple[str, str] | None:
    """(hilo, máquina) de otra máquina donde se trabaja este pendiente, según la foto que publicó su
    nodo (`telar.espejo`). Solo con bus: es el que lleva el mensaje hasta allá."""
    from telar import bus as mod_bus
    from telar import espejo

    if not mod_bus.hay_bus(ctx.config):
        return None
    candidatos = []
    for foto in espejo.leer_todos(ctx.config):
        if not foto.get("en_linea") and foto.get("edad") is not None and foto["edad"] > 24 * 3600:
            continue
        for h in foto.get("hilos", []):
            if h.get("remoto"):
                continue  # una ventana allá de un hilo que vive en otra parte (quizás aquí)
            candidatos.append(((h.get("nombre", ""), foto["nombre"]), h.get("relativa", ""), bool(h.get("vivo"))))
    if fila.get("hilo"):
        exacto = next((c[0] for c in candidatos if c[0][0] == fila["hilo"]), None)
        if exacto is not None:
            return exacto
    ruta = fila.get("ruta", "")
    if ruta:
        exacto = next((c[0] for c in candidatos if c[1] == ruta), None)
        if exacto is not None:
            return exacto
    return _por_enlace(candidatos, fila.get("url", ""))


def _con_direccion(ctx, fila: dict) -> dict:
    """La fila con su dirección: la que trae, o la de su tarea si es de un proveedor del tipo `tarea` y
    llegó sin ella (la armó una máquina de antes, o quien la pasa entera, como la API)."""
    if fila.get("direccion") or not fila.get("id") or not fila.get("proveedor"):
        return fila
    from telar import objetos

    if any(p.nombre == fila["proveedor"] and p.opciones.get("tipo") == "tipo" for p in ctx.config.proveedores_activos()):
        return {**fila, "direccion": objetos.direccion_de("tarea", fila["id"])}
    return fila


def mensaje(plantilla: str, fila: dict) -> str:
    """La plantilla llena. Un pendiente sin id (los de los documentos) no tiene con qué
    llenar {id}: para ese, el texto, que es lo único que lo nombra sin ambigüedad. Lo mismo
    con {direccion} (`tarea:T84`, telar.objetos) para uno sin dirección: una casilla de un
    documento, o el ítem de un proveedor que no es del tipo `tarea`. Con los dos, basta que falte uno: no
    se llena a medias (`/tarea X1 ()`).

    Una casilla con id llena {direccion} con la suya (`pendiente:c-1a2b3c`): quien recibe el mensaje la abre
    con `telar objeto`. Sin id, no tiene, y la plantilla cae a {texto}."""
    direccion = fila.get("direccion", "")
    if ("{id}" in plantilla and not fila.get("id")) or ("{direccion}" in plantilla and not direccion):
        plantilla = "{texto}"
    valores = {"texto": fila.get("texto", ""), "ref": fila.get("ref", ""), "id": fila.get("id", ""),
               "direccion": direccion}
    return re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), plantilla).strip()


def en_su_documento(ctx, ref: str, *, hecho: bool = False, responsable: str | None = None, linea: bool = False,
                    esperado: str = "", proveedor: str = "", fila: dict | None = None) -> tuple[dict, str]:
    """Marcar hecha, cambiar el responsable o ubicar una casilla en el documento de donde salió."""
    from telar import vinetas
    from telar.servicios import ErrorDeServicio

    tel = _comun.tejer(ctx)
    fila = _encontrar(ctx, tel, ref, proveedor, fila)
    if fila.get("proveedor"):
        raise ErrorDeServicio(f"«{fila['ref']}» es de {fila['proveedor']}: eso se cambia con sus acciones (telar tarea)", 409)
    unidad = tel.unidades.get(fila.get("ruta", ""))
    if unidad is None:
        raise ErrorDeServicio(f"no sé de qué documento es «{fila['ref']}»", 404)
    documento = unidad[1]
    texto = esperado.strip() or fila["texto"]
    if esperado.strip() and esperado.strip() != fila["texto"]:
        raise ErrorDeServicio(f"«{fila['ref']}» ya no dice «{esperado.strip()[:60]}»: el documento cambió, vuelve a mirarlo", 409)
    # con id, la casilla se busca por él (no se mueve con el documento); sin id, por su texto, y al escribirla
    # recibe uno (telar.vinetas): desde ahí su dirección es `pendiente:<id>`. Sin id y con otras que dicen lo
    # mismo, la fila dice cuál es de ellas (`repetida`), y se le escribe a esa
    ident = id_casilla(fila)
    lugar = lugar_casilla(fila)
    try:
        if linea:
            que, n = "", vinetas.linea(documento, texto, id=ident, **lugar)
        elif hecho:
            que = "marcada hecha"
            n, ident = vinetas.escribir(documento, vinetas.hecha, texto=texto, id=ident, **lugar)
        else:
            nombre = (responsable or "").strip()
            que = "sin responsable" if nombre.lower() in ("", "none") else f"responsable: {nombre}"
            n, ident = vinetas.escribir(documento, lambda l: vinetas.con_responsable(l, nombre), texto=texto,
                                        id=ident, **lugar)
    except (vinetas.ErrorDeVineta, OSError) as e:
        raise ErrorDeServicio(str(e), 409) from e
    from telar import objetos

    relativa = _comun.ruta_relativa(documento, tel.raiz)
    direccion = objetos.direccion_de("pendiente", ident) if ident else ""
    return ({"ref": fila["ref"], "archivo": str(documento), "relativa": relativa, "linea": n, "hecho": que,
             "direccion": direccion}, f"{relativa}:{n}" + (f" · {que}" if que else ""))


def lugar_casilla(fila: dict) -> dict:
    """Cuál es la casilla de la fila entre las de su documento que dicen lo mismo, como lo piden
    telar.vinetas.escribir y linea (`cual`, `de`); vacío si es la única, o si la fila no dice."""
    repetida = fila.get("repetida") or {}
    if fila.get("proveedor") or not isinstance(repetida, dict):
        return {}
    try:
        return {"cual": int(repetida["cual"]), "de": int(repetida["de"])}
    except (KeyError, TypeError, ValueError):
        return {}


def id_casilla(fila: dict) -> str:
    """El id de la casilla de una fila de documento, si tiene (lo dice su dirección, `pendiente:c-1a2b3c`); ""."""
    direccion = fila.get("direccion") or ""
    if fila.get("proveedor") or not direccion.startswith("pendiente:"):
        return ""
    from telar import objetos

    return objetos.leer(direccion).id


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


def destino_elegido(ctx, tel: _comun.Telar, nombre: str):
    """(hilo de aquí, (hilo, máquina) de otra, agente residente) para un nombre que eligió la persona: uno de
    los tres, los otros None. `ErrorDeServicio` 404 si no hay ningún hilo ni agente que se llame así."""
    from telar import agentes as mod_agentes
    from telar.servicios import ErrorDeServicio

    agente = next((x for x in mod_agentes.descubrir(ctx.config) if nombre in (x.clave, x.nombre)), None)
    if agente is not None:
        return None, None, agente
    aqui = next((h for h in tel.hilos if h.nombre == nombre), None)
    if aqui is not None and not aqui.remoto:
        return aqui, None, None
    from telar import bus as mod_bus
    from telar import espejo

    if mod_bus.hay_bus(ctx.config):
        for foto in espejo.leer_todos(ctx.config):
            if any(h.get("nombre") == nombre and not h.get("remoto") for h in foto.get("hilos", [])):
                return None, (nombre, foto["nombre"]), None
    raise ErrorDeServicio(f"no hay ningún hilo ni agente que se llame «{nombre}»", 404)


def _agente_general(ctx):
    """El agente residente que recibe los pendientes sin proyecto (`[agentes] sin_proyecto`)."""
    clave = getattr(ctx.config, "agentes_sin_proyecto", "")
    if not clave:
        return None
    from telar import agentes as mod_agentes

    return next((a for a in mod_agentes.descubrir(ctx.config) if clave in (a.clave, a.nombre)), None)


def encargar_y_ir(ctx, agente, texto: str) -> tuple[int, dict]:
    """Le encarga `texto` al agente y lleva a su hilo (telar.servicios.encargos). (0, lo que respondió), o
    (2, {}) con la queja dicha. Lo usa `telar reunion`."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import encargos

    try:
        return 0, encargos.encargar_y_ir(ctx, agente, texto).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e)), {}


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
