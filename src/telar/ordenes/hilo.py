"""`telar hilo` — actuar sobre un hilo: vincularlo, renombrarlo, priorizarlo, archivarlo.

Todo lo que se le hace a un hilo suelto vive aquí, con un verbo por operación:

    telar hilo vincular proyectos/faro     asociarlo a una carpeta del repositorio
    telar hilo desvincular                 soltar esa asociación
    telar hilo renombrar «Faro»            renombrarlo, y mover con él lo que telar sabía
    telar hilo adoptar [«faro»]            recoger el estado que quedó en otro nombre
    telar hilo prioridad 1|2|3|ninguna     prioridad manual, para ordenar
    telar hilo archivar [--cerrar]         sacarlo de la lista sin perderlo
    telar hilo desarchivar
    telar hilo olvidar                     borrar lo que telar sabía de él
    telar hilo ver                         lo mismo que `telar hilos` para uno solo

`adoptar` es la salida del único agujero que tiene guardar el estado por nombre:
renombrar un tab desde el multiplexor (`prefix + ,`) deja el vínculo, la prioridad y
la atención colgados del nombre viejo, que ya no es ningún tab. Adoptar se los pasa a
este hilo y no pisa nada de lo suyo. Sin nombre, busca uno solo: un hilo sin ventana
cuyo vínculo apunte a la carpeta donde está este tab.

Sin `--hilo`, actúa sobre el hilo actual: `$TELAR_HILO` si el multiplexor lo
exportó y, si no, el del foco —que es una suposición—. El foco lo mueve la persona
mientras un agente trabaja en otra parte, así que renombrar o archivar «el de
arriba» le toca al hilo equivocado más seguido de lo que parece.
"""

from __future__ import annotations

from pathlib import Path

from telar import lectura
from telar.modelo import Prioridad
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Vincular, renombrar, priorizar, archivar: actuar sobre un hilo."

VERBOS = (
    "ver",
    "vincular",
    "desvincular",
    "renombrar",
    "adoptar",
    "prioridad",
    "archivar",
    "desarchivar",
    "olvidar",
)


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hilo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=VERBOS, help="qué hacerle")
    p.add_argument(
        "valor",
        nargs="?",
        default="",
        help="la carpeta, el nombre nuevo, el hilo que se adopta o la prioridad",
    )
    p.add_argument("--hilo", default="", help="sobre cuál actuar (por defecto, este)")
    p.add_argument("--cerrar", action="store_true", help="al archivar, cerrar además el hilo")
    p.add_argument("--json", action="store_true", help="el hilo resultante, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx, con_ficha=o.verbo in ("ver", "vincular"))
    if o.hilo:
        # un hilo puede existir antes de que telar lo vea: aquí se anota igual
        hilo, aviso = _comun.hilo_o_nombre(tel, o.hilo)
        if hilo is None:
            return _comun.queja(aviso)
        if aviso and not o.json and o.verbo != "ver":
            print(_comun.tenue(f"({aviso})"))
    else:
        hilo = _comun.hilo_actual(tel)
        if hilo is None:
            return _comun.queja(
                "no sé en qué hilo estoy; dime cuál con --hilo"
                + (f"\n{tel.aviso}" if tel.aviso else "")
            )

    est = tel.estado
    salida = 0
    if o.verbo == "ver":
        pass
    elif o.verbo == "vincular":
        relativa, problema = _ruta_en_raiz(o.valor or ".", ctx.config.raiz)
        if relativa is None:
            return _comun.queja(problema)
        est.vincular(hilo.nombre, relativa)
        arquetipo, _ = lectura.ubicar(ctx.perfil, ctx.config.raiz, relativa, mapa=tel.unidades)
        print(f"«{hilo.nombre}» → {relativa}")
        if arquetipo is None:
            print(
                _comun.tenue(
                    "  ojo: el perfil no declara esa ruta como unidad de trabajo,"
                    " así que no habrá ficha. `telar perfil --documentos` dice cuáles sí."
                )
            )
        else:
            print(_comun.tenue(f"  arquetipo: {arquetipo.nombre}"))
    elif o.verbo == "desvincular":
        est.desvincular(hilo.nombre)
        print(f"«{hilo.nombre}» queda sin carpeta")
    elif o.verbo == "renombrar":
        if not o.valor:
            return _comun.queja("telar hilo renombrar <nombre nuevo>")
        salida = _renombrar(tel, hilo, o.valor)
    elif o.verbo == "adoptar":
        salida = _adoptar(tel, hilo, o.valor)
    elif o.verbo == "prioridad":
        salida = _prioridad(est, hilo, o.valor)
    elif o.verbo == "archivar":
        est.archivar(hilo.nombre)
        print(f"archivado «{hilo.nombre}»" + _sesiones(hilo))
        if o.cerrar:
            salida = _cerrar(tel, hilo)
        else:
            print(_comun.tenue("  sigue abierto; --cerrar además lo cierra en el multiplexor"))
    elif o.verbo == "desarchivar":
        est.desarchivar(hilo.nombre)
        print(f"de vuelta en la lista «{hilo.nombre}»")
    elif o.verbo == "olvidar":
        est.olvidar(hilo.nombre)
        print(f"telar olvidó «{hilo.nombre}» (el registro de foco queda: es historia)")

    if o.json:
        tel = _comun.tejer(ctx)
        actual = tel.por_nombre(o.valor if o.verbo == "renombrar" else hilo.nombre)
        return _comun.escribir_json(
            {"hilo": _comun.json_hilo(actual, tel) if actual else None, "codigo": salida}
        )
    if o.verbo == "ver" and salida == 0:
        _ver(hilo, tel)
    return salida


def _ver(hilo, tel: _comun.Telar) -> None:
    print(_comun.fuerte(hilo.nombre) + "  " + _comun.tenue(f"id {hilo.id}"))
    print(f"  carpeta: {_comun.ruta_relativa(hilo.ruta, tel.raiz) or '— sin vincular'}")
    print(f"  vivo: {'sí' if tel.vivo(hilo) else 'no'}" + ("  ·  archivado" if hilo.archivado else ""))
    print(f"  atención: {hilo.atencion.value}")
    if hilo.prioridad:
        print(f"  prioridad: {int(hilo.prioridad)}")
    if hilo.sesiones:
        print(f"  conversaciones: {', '.join(hilo.sesiones)}")
    if hilo.ficha and hilo.ficha.estado:
        print(f"  estado: {hilo.ficha.estado}")


def _ruta_en_raiz(valor: str, raiz: Path) -> tuple[str | None, str]:
    """La ruta que se vincula, relativa a la raíz. Nadie vincula fuera del repositorio."""
    camino = Path(valor).expanduser()
    if not camino.is_absolute():
        camino = (Path.cwd() / camino) if valor in (".", "..") or valor.startswith(("./", "../")) else (raiz / camino)
    try:
        relativa = camino.resolve().relative_to(Path(raiz).resolve()).as_posix()
    except ValueError:
        return None, f"«{valor}» está fuera de la raíz ({raiz}); un hilo se vincula dentro"
    if not camino.exists():
        return None, f"no existe {camino}"
    return relativa or ".", ""


def _prioridad(est, hilo, valor: str) -> int:
    crudo = (valor or "").strip().lower()
    if crudo in ("ninguna", "none", "0", ""):
        est.prioridad(hilo.nombre, None)
        print(f"«{hilo.nombre}»: sin prioridad (al final, al ordenar por prioridad)")
        return 0
    try:
        numero = Prioridad(int(crudo))
    except (ValueError, TypeError):
        return _comun.queja("la prioridad es 1 (alta), 2, 3 (baja) o «ninguna»")
    est.prioridad(hilo.nombre, numero)
    print(f"«{hilo.nombre}»: prioridad {int(numero)} ({numero.name.lower()})")
    return 0


def _renombrar(tel: _comun.Telar, hilo, nuevo: str) -> int:
    """Renombra en el multiplexor y mueve el estado. Si algo falla, se dice cuál quedó."""
    ocupa = tel.por_nombre(nuevo)
    if ocupa is not None:
        # el caso feo: el que ocupa el nombre no es un tab, es el estado que quedó
        # colgado cuando ese tab se renombró desde el multiplexor. Renombrar no es lo
        # que se quiere ahí —sería mover un nombre encima de otro—, sino recogerlo
        salida = f"ya hay un hilo llamado «{nuevo}»"
        if not tel.vivo(ocupa):
            salida += (
                "; el multiplexor no lo muestra, así que es estado sin ventana:"
                f" `telar hilo adoptar {nuevo} --hilo {hilo.nombre}` se lo pasa a este hilo"
            )
        return _comun.queja(salida)
    movido = False
    if tel.mux is not None and tel.vivo(hilo):
        try:
            tel.mux.renombrar(hilo.id, nuevo)
            movido = True
        except ErrorDeMux as e:
            return _comun.queja(f"el multiplexor no lo renombró: {e}")
    tel.estado.renombrar(hilo.nombre, nuevo)
    print(f"«{hilo.nombre}» → «{nuevo}»")
    if not movido:
        print(_comun.tenue("  (solo en telar: el hilo no está vivo en el multiplexor)"))
    print(
        _comun.tenue(
            "  el tiempo anterior al cambio queda con el nombre anterior:"
            " el registro de foco es historia y no se reescribe"
        )
    )
    return 0


def _adoptar(tel: _comun.Telar, hilo, viejo: str) -> int:
    """Le pasa a `hilo` el estado que quedó colgado de otro nombre sin ventana.

    Es la reconciliación de lo que el multiplexor puede romper sin avisar: un
    `prefix + ,` renombra el tab y el vínculo, la prioridad, la atención y las
    conversaciones se quedan con el nombre anterior. Se fusiona, no se pisa: lo que
    este hilo ya tenía gana, y del huérfano se toma lo que falte.
    """
    if not viejo:
        candidatos = _misma_carpeta(tel, hilo)
        if not candidatos:
            return _comun.queja(
                "no veo ningún hilo sin ventana que apunte a la carpeta de este;"
                " dime cuál adoptar: telar hilo adoptar <nombre>"
            )
        if len(candidatos) > 1:
            cuales = ", ".join(f"«{h.nombre}»" for h in candidatos[:6])
            return _comun.queja(f"hay varios que calzan ({cuales}); nombra uno")
        viejo = candidatos[0].nombre

    fuente, problema = _comun.resolver(tel, viejo)
    if fuente is None:
        return _comun.queja(problema)
    if fuente.nombre == hilo.nombre:
        return _comun.queja(f"«{fuente.nombre}» ya es este hilo")
    if tel.vivo(fuente):
        return _comun.queja(
            f"«{fuente.nombre}» está vivo en el multiplexor: adoptar es para el estado"
            " que se quedó sin ventana, no para juntar dos tabs abiertos"
        )

    # lo de este hilo, ANTES de fusionar: `hilo.ruta` puede ser el cwd de su panel, que
    # no es un vínculo, y lo archivado no se hereda
    archivado = hilo.archivado
    tenia_vinculo = bool(tel.estado.vinculo(hilo.nombre))
    tel.estado.renombrar(fuente.nombre, hilo.nombre, fusionar=True)
    if not archivado:
        # el huérfano podía estar archivado, y eso no se hereda: este tab está abierto
        tel.estado.desarchivar(hilo.nombre)
    print(f"«{hilo.nombre}» adoptó lo que telar sabía de «{fuente.nombre}»")
    # el vínculo solo se hereda si este hilo no tenía uno: lo suyo manda, y decir que
    # adoptó una carpeta que no adoptó sería peor que no decir nada
    relativa = _comun.ruta_relativa(fuente.ruta, tel.raiz)
    if relativa and not tenia_vinculo:
        print(_comun.tenue(f"  carpeta: {relativa}"))
    print(
        _comun.tenue(
            "  el registro de foco no se toca: el tiempo anterior al cambio"
            f" sigue contado bajo «{fuente.nombre}»"
        )
    )
    return 0


def _misma_carpeta(tel: _comun.Telar, hilo) -> list:
    """Los hilos sin ventana cuyo vínculo apunta a donde está este tab.

    Es la única pista automática que hay: un tab renombrado conserva el directorio de
    trabajo de su panel, y el huérfano conserva el vínculo que apuntaba ahí.
    """
    aqui = _resolver_ruta(hilo.ruta)
    if aqui is None:
        return []
    return [
        h
        for h in tel.hilos
        if h.nombre != hilo.nombre
        and not tel.vivo(h)
        and h.vinculado
        and _resolver_ruta(h.ruta) == aqui
    ]


def _resolver_ruta(ruta: Path | None) -> Path | None:
    if ruta is None:
        return None
    try:
        return Path(ruta).resolve()
    except OSError:  # pragma: no cover - depende del sistema de archivos
        return Path(ruta)


def _cerrar(tel: _comun.Telar, hilo) -> int:
    if tel.mux is None or not tel.vivo(hilo):
        print(_comun.tenue("  no está vivo: no hay nada que cerrar"))
        return 0
    try:
        tel.mux.cerrar(hilo.id)
    except ErrorDeMux as e:
        return _comun.queja(f"no pude cerrarlo: {e}")
    print("  cerrado en el multiplexor")
    return 0


def _sesiones(hilo) -> str:
    if not hilo.sesiones:
        return ""
    return f"; conversación anotada: {hilo.sesiones[0]}"
