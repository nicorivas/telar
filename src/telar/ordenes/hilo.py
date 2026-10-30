"""`telar hilo` — actuar sobre un hilo: vincularlo, renombrarlo, priorizarlo, archivarlo.

Todo lo que se le hace a un hilo suelto vive aquí, con un verbo por operación:

    telar hilo vincular proyectos/faro     asociarlo a una carpeta del repositorio
    telar hilo desvincular                 soltar esa asociación
    telar hilo renombrar «Faro»            renombrarlo, y mover con él lo que telar sabía
    telar hilo adoptar [«faro»]            recoger el estado que quedó en otro nombre
    telar hilo prioridad 1|2|3|ninguna     prioridad manual, para ordenar
    telar hilo mudar «Agrosur»               llevarse este panel (y su conversación) a ese hilo
    telar hilo cerrar                      cerrar su tab (y lo que corra adentro) y
                                           olvidarlo: sale de la lista. Para guardarlo
                                           está `archivar`
    telar hilo archivar [--cerrar]         sacarlo de la lista sin perderlo
    telar hilo desarchivar
    telar hilo publicar                    que las otras personas del bus lo vean en su directorio (por
                                           defecto, un hilo es privado: no sale)
    telar hilo privar                      volver a privado
    telar hilo retomar                     desarchivarlo y reabrirlo, con su agente retomando
                                           la conversación que tenía
    telar hilo olvidar                     borrar lo que telar sabía de él
    telar hilo caidos [--horas N] [--seco] reabrir de una vez, con su conversación, los hilos que
                                           estaban vivos en esta máquina y ya no tienen ventana
                                           (tmux se cayó, la máquina se reinició). Los cuenta el
                                           nodo cada 30 s; --horas, qué tan reciente (6)
    telar hilo llevar [máquina] [--sesion ID]  pasar su conversación a otra máquina: una de [remotos]
                                           (por ssh) o una tuya del bus, como tu lugar en un
                                           servidor (por el bus, telar.mudanza). Se cierra aquí y
                                           sigue allá, retomada. Con --sesion, esa conversación
                                           aunque telar no la tenga anotada
    telar hilo ver                         lo mismo que `telar hilos` para uno solo
    telar hilo leer [«Faro»] [--ultimos N] [--maquina M]   lo último que pasó en ese hilo (de esa máquina, por el bus): lo que se le pidió y
                                           lo que respondió su agente (5 turnos si no se dice)

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

import sys
from pathlib import Path
from types import SimpleNamespace

from telar import lectura
from telar.modelo import Hilo, Prioridad
from telar.agente import ErrorDeAgente
from telar.agente.base import panel_del_entorno
from telar.agente import lanzar
from telar.mux import ErrorDeMux
from telar import remoto as mod_remoto
from telar.ordenes import _comun

AYUDA = "Vincular, renombrar, priorizar, archivar: actuar sobre un hilo."

VERBOS = (
    "ver",
    "vincular",
    "desvincular",
    "renombrar",
    "adoptar",
    "prioridad",
    "mudar",
    "cerrar",
    "archivar",
    "desarchivar",
    "publicar",
    "privar",
    "retomar",
    "olvidar",
    "llevar",
    "leer",
    "caidos",
)


#: los verbos que cambian el registro de un hilo: sobre uno que vive en otra máquina, se le piden a su
#: dueño por el bus (docs/propuestas/un-dueno-por-hilo.md), que los aplica y los vuelve a publicar
AL_DUENO = ("vincular", "desvincular", "renombrar", "prioridad", "archivar", "desarchivar", "publicar", "privar",
            "cerrar", "olvidar")

#: los verbos que no llevan valor: el nombre suelto que se les dé es el hilo sobre el que actúan
SIN_VALOR = ("ver", "desvincular", "cerrar", "archivar", "desarchivar", "publicar", "privar", "retomar", "olvidar")


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hilo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=VERBOS, help="qué hacerle")
    p.add_argument(
        "valor",
        nargs="?",
        default="",
        help="la carpeta, el nombre nuevo, el hilo que se adopta o la prioridad; en los verbos sin valor, el hilo",
    )
    p.add_argument("--hilo", default="", help="sobre cuál actuar (por defecto, este)")
    p.add_argument("--cerrar", action="store_true", help="al archivar, cerrar además el hilo")
    p.add_argument("--si", action="store_true", help="con llevar: seguir aunque haya trabajo sin subir")
    p.add_argument("--sesion", default="",
                   help="con llevar: el id de la conversación, si telar no la tiene anotada (salida de emergencia)")
    p.add_argument("--ultimos", type=int, default=0, metavar="N", help="con leer: cuántos turnos")
    p.add_argument("--maquina", default="", metavar="NOMBRE", help="con leer: un hilo de otra máquina, por el bus")
    p.add_argument("--json", action="store_true", help="el hilo resultante, en una línea")
    p.add_argument("--horas", type=float, default=6, help="con caidos: vistos vivos en estas últimas horas")
    p.add_argument("--seco", action="store_true", help="con caidos: solo decir cuáles reabriría")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "leer":
        return _leer(ctx, o)
    if o.verbo == "caidos":
        return _caidos(ctx, o)
    if o.valor and o.verbo in SIN_VALOR:
        # `telar hilo olvidar X` actuaba sobre el hilo actual e ignoraba X: lo suelto es el hilo
        if o.hilo:
            return _comun.queja(f"«{o.verbo}» no lleva valor: «{o.valor}» sobra (el hilo ya es «{o.hilo}»)")
        o.hilo = o.valor

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
            return _comun.sin_hilo("hilo", tel)

    est = tel.estado
    salida = 0
    # si es un hilo remoto, lo que le pase cambia lo que su máquina publica en el directorio
    remoto_antes = est.remotos().get(hilo.nombre, {}).get("remoto", "")
    # un hilo de otra máquina: el cambio lo hace su dueño, y su registro (vínculo, archivo) lo guarda él:
    # aquí se lee de lo que publica (telar.estado, «hilos ajenos»). Si allá salió bien, lo de aquí se
    # ajusta igual: la ventana que lo mira, su nombre en ella, y la copia de su registro, que es lo que
    # vale mientras el dueño no publique ese campo (un telar de antes allá, el nodo de aquí apagado)
    dueno = _dueno(ctx, hilo) if o.verbo in AL_DUENO else ""
    if dueno:
        problema = _al_dueno(ctx, dueno, o, hilo.nombre)
        if problema:
            return _comun.queja(problema)
        # lo que el dueño ya aceptó, en lo que se lee de él: la respuesta (--json) y la página lo
        # muestran ya, sin esperar a que el nodo recoja lo que el dueño vuelve a publicar
        _adelantar(est, o, hilo.nombre, ctx.config.raiz)
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
                    "  el perfil no declara esa ruta como unidad de trabajo: la ficha será"
                    " solo su README. `telar perfil --documentos` dice cuáles sí son unidades."
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
        if salida == 0:
            # un hilo remoto lleva su nombre también en su ventana de allá: se renombra con él
            anotado = tel.estado.remotos().get(o.valor.strip())
            remoto = _remoto_de(ctx, anotado["remoto"]) if anotado and not dueno else None
            if remoto is not None and anotado.get("sesion"):
                problema = mod_remoto.nombrar(remoto, anotado["sesion"], o.valor.strip())
                if problema:
                    print(_comun.tenue(f"  la ventana de {remoto.destino} sigue con el nombre viejo: {problema}"))
    elif o.verbo == "adoptar":
        salida = _adoptar(tel, hilo, o.valor)
    elif o.verbo == "prioridad":
        salida = _prioridad(est, hilo, o.valor)
    elif o.verbo == "mudar":
        salida = _mudar(tel, hilo, o.valor or "", ctx)
    elif o.verbo == "cerrar":
        # cerrar es descartar: el tab se va y telar lo olvida, así que sale de la lista.
        # Lo que se quiere guardar se archiva. La conversación sigue en disco, donde la
        # deja el agente; solo se pierde el vínculo que permitía retomarla de un clic.
        # el estado se guarda por nombre: si otra ventana viva se llama igual, olvidar el
        # nombre le borraría a esa su conversación, su vínculo y su prioridad (le pasó a un
        # hilo real: cerrar su duplicado lo dejó sin conversación que llevar)
        gemelos = [h for h in tel.hilos if h.nombre == hilo.nombre and h.id != hilo.id and tel.vivo(h)]
        # si lo cerró su dueño, la ventana de aquí (la que solo lo miraba) se cierra ya, sin volver a pedirle nada a
        # la otra máquina: esperar a que el nodo vea el cambio dejaba la fila viva un rato, o para siempre si el
        # aviso del bus se perdía
        salida = _cerrar_vista(tel, hilo) if dueno else _cerrar(ctx, tel, hilo)
        if salida == 0 and gemelos:
            print(f"cerrado; «{hilo.nombre}» sigue vivo en otra ventana y telar no lo olvida")
        elif salida == 0:
            est.olvidar(hilo.nombre)
            print(f"cerrado y olvidado «{hilo.nombre}»")
    elif o.verbo == "archivar":
        est.archivar(hilo.nombre)
        print(f"archivado «{hilo.nombre}»" + _sesiones(hilo))
        if o.cerrar and dueno:
            salida = _cerrar_vista(tel, hilo)
        elif o.cerrar:
            salida = _cerrar(ctx, tel, hilo)
        else:
            print(_comun.tenue("  sigue abierto; --cerrar además lo cierra en el multiplexor"))
    elif o.verbo == "desarchivar":
        est.desarchivar(hilo.nombre)
        print(f"de vuelta en la lista «{hilo.nombre}»")
    elif o.verbo == "publicar":
        est.publicar(hilo.nombre)
        print(f"«{hilo.nombre}» es público: las otras personas del bus lo ven en su directorio (su nombre, su carpeta "
              f"y una línea; nunca la conversación) y pueden escribirle")
    elif o.verbo == "privar":
        est.privar(hilo.nombre)
        print(f"«{hilo.nombre}» es privado: sale del directorio de las otras personas")
    elif o.verbo == "retomar":
        salida = _retomar(ctx, tel, hilo)
    elif o.verbo == "llevar":
        salida = _llevar(ctx, tel, hilo, o.valor, o.si, o.sesion)
    elif o.verbo == "olvidar":
        est.olvidar(hilo.nombre)
        print(f"telar olvidó «{hilo.nombre}» (el registro de foco queda: es historia)")

    if remoto_antes and salida == 0 and o.verbo in ("renombrar", "cerrar", "archivar", "desarchivar", "retomar", "olvidar"):
        from telar import directorio as mod_directorio

        mod_directorio.publicar_callado(ctx, tel, remoto_antes)
    if o.json:
        tel = _comun.tejer(ctx)
        nombre = o.valor if o.verbo == "renombrar" else hilo.nombre
        # si telar no lo conoce (un hilo que todavía no abrió, o que ya se olvidó), se
        # devuelve el que se nombró: en texto se imprime igual, y dos salidas de la misma
        # orden que no dicen lo mismo son una trampa para quien programa contra el JSON
        actual = tel.por_nombre(nombre) or Hilo(id=hilo.id or nombre, nombre=nombre)
        return _comun.escribir_json({"hilo": _comun.json_hilo(actual, tel), "codigo": salida})
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
    """La ruta que se vincula: relativa a la raíz si está adentro, absoluta si no.

    Afuera de la raíz también se puede: hay trabajo que no vive en el repositorio (otro
    repo, una carpeta suelta). El perfil no sabe leerlo, así que su ficha es solo el
    README de esa carpeta.
    """
    camino = Path(valor).expanduser()
    if not camino.is_absolute():
        camino = (Path.cwd() / camino) if valor in (".", "..") or valor.startswith(("./", "../")) else (raiz / camino)
    if not camino.exists():
        return None, f"no existe {camino}"
    try:
        relativa = camino.resolve().relative_to(Path(raiz).resolve()).as_posix()
    except ValueError:
        return camino.resolve().as_posix(), ""
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


def _dueno(ctx, hilo) -> str:
    """La máquina del bus donde vive el hilo, si es otra; "" si vive aquí, no hay bus o no se sabe."""
    from telar import bus as mod_bus

    if not hilo.remoto or hilo.remoto == "?" or not mod_bus.hay_bus(ctx.config):
        return ""
    maquina = mod_bus.maquina_de(ctx.config, hilo.nombre) or hilo.remoto
    return "" if maquina == mod_bus.maquina(ctx.config) else maquina


def _adelantar(est, o, nombre: str, raiz) -> None:
    """Anota en lo que se lee del dueño (`ajenos.json`) el cambio que acaba de aceptar, si ese campo lo
    publica: lo que el nodo recoja después lo reemplaza entero. Un campo que no publica se lee de la
    copia de aquí, que la orden escribe igual."""
    publica = est.registro_ajeno().get(nombre, {})
    if o.verbo in ("archivar", "desarchivar") and "archivado" in publica:
        est.adelantar_ajeno(nombre, archivado=o.verbo == "archivar")
    elif o.verbo in ("publicar", "privar") and "publico" in publica:
        est.adelantar_ajeno(nombre, publico=o.verbo == "publicar")
    elif o.verbo in ("vincular", "desvincular") and "vinculo" in publica:
        relativa = _ruta_en_raiz(o.valor or ".", raiz)[0] if o.verbo == "vincular" else ""
        if relativa is not None:
            est.adelantar_ajeno(nombre, vinculo=relativa)


def _al_dueno(ctx, dueno: str, o, nombre: str) -> str:
    """Pide el verbo a la máquina dueña del hilo y muestra lo que dijo. "" si salió bien; si no, el problema."""
    from telar import bus as mod_bus

    argv = [o.verbo, *([o.valor] if o.valor else []), "--hilo", nombre, *(["--cerrar"] if o.cerrar else [])]
    r = mod_bus.pedir(ctx.config, dueno, "hilo", {"argv": argv}, espera=60)
    if not r.get("ok"):
        return f"«{nombre}» vive en {dueno}, y no respondió: {r.get('error', '')}"
    if r.get("salida", "").strip() and not o.json:
        print(_comun.tenue(f"  en {dueno}: " + r["salida"].strip().splitlines()[0]))
    if int(r.get("codigo", 1)) != 0:
        ultima = (r.get("error_salida", "").strip().splitlines() or ["falló"])[-1].removeprefix("telar: ")
        return f"en {dueno}: {ultima}"
    return ""


def _cerrar(ctx, tel: _comun.Telar, hilo) -> int:
    # un hilo remoto tiene además su ventana en la otra máquina, que sigue viva aunque la
    # ventana local ya no esté: se cierra igual, o el agente quedaría corriendo allá
    _matar_remoto(ctx, tel, hilo)
    if tel.mux is None or not tel.vivo(hilo):
        print(_comun.tenue("  no está vivo: no hay nada que cerrar"))
        return 0
    try:
        tel.mux.cerrar(hilo.id)
    except ErrorDeMux as e:
        return _comun.queja(f"no pude cerrarlo: {e}")
    print("  cerrado en el multiplexor")
    return 0


def _cerrar_vista(tel: _comun.Telar, hilo) -> int:
    """La ventana de aquí de un hilo que su dueño ya cerró en su máquina: solo se cierra, y se olvida dónde vivía."""
    if tel.mux is not None and tel.vivo(hilo):
        try:
            tel.mux.cerrar(hilo.id)
        except ErrorDeMux:
            pass  # si no se deja, la cierra el nodo cuando vea que allá ya no vive
    tel.estado.olvidar_remoto(hilo.nombre)
    return 0


def _sin_subir(ruta: Path) -> str:
    """Lo que el repositorio de esa carpeta tiene y la otra máquina no: sin commitear, sin subir.
    "" si nada, o si no es un repositorio git."""
    import subprocess

    def git(*args):
        r = subprocess.run(["git", "-C", str(ruta), *args], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else None

    raiz = git("rev-parse", "--show-toplevel")
    if not raiz:
        return ""
    # lo de otros repositorios no cuenta: un submódulo con cambios adentro (su puntero no
    # cambió) o un repo anidado sin rastrear (`?? empresa/`) se sincronizan por su cuenta
    lineas = (git("status", "--porcelain", "--ignore-submodules=dirty") or "").splitlines()
    sucios = len([l for l in lineas if l.strip()
                  and not (l.startswith("?? ") and l.rstrip().endswith("/") and (Path(raiz) / l[3:].strip() / ".git").exists())])
    adelante = git("rev-list", "--count", "@{u}..HEAD")
    partes = ([f"{sucios} archivo{'s' if sucios != 1 else ''} sin commitear"] if sucios else []) + (
        [f"{adelante} commit{'s' if adelante != '1' else ''} sin subir"] if adelante and adelante != "0" else [])
    return f"{raiz}: {', '.join(partes)}" if partes else ""


def _falta_alla(remoto, ruta: str) -> str:
    """La carpeta como se llamaría allá (`~/Code/x`), si NO existe allá; "" si existe o no se sabe."""
    import shlex
    import subprocess

    try:
        alla = "~/" + Path(ruta).expanduser().resolve().relative_to(Path.home().resolve()).as_posix()
    except (ValueError, OSError):
        alla = ruta
    prueba = f"test -d {alla if alla.startswith('~/') and ' ' not in alla else shlex.quote(alla)}"
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino, prueba],
                           capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return alla if r.returncode == 1 else ""


def _llevar(ctx, tel: _comun.Telar, hilo, valor: str, si: bool, sesion: str = "") -> int:
    """Pasar la conversación de un hilo local a otra máquina, y seguirla allá.

    La conversación viaja; los archivos no. Lo que el repositorio de aquí tenga sin commitear
    o sin subir, el agente de allá no lo va a ver aunque lo recuerde: se dice antes, y hay que
    confirmar. El agente de aquí se cierra antes de copiar: la misma conversación viva en dos
    máquinas se bifurca.
    """
    from telar import agente as mod_agente

    if hilo.remoto:
        return _comun.queja(f"«{hilo.nombre}» ya vive en otra máquina ({hilo.remoto})")
    from telar import mudanza

    remotos = ctx.config.remotos
    remoto = next((r for r in remotos if r.nombre == valor), None) if valor else (remotos[0] if len(remotos) == 1 else None)
    # una máquina del bus (otra tuya, como tu lugar en un servidor): la conversación va por el bus (telar.mudanza)
    del_bus = mudanza.maquinas_del_bus(ctx.config) if remoto is None else []
    if remoto is None and valor not in del_bus:
        nombres = ", ".join([*(r.nombre for r in remotos), *del_bus]) or "ninguna: ni en [remotos] ni en el bus"
        return _comun.queja(f"¿a qué máquina? telar hilo llevar <máquina> ({nombres})")
    # con --sesion, esa y no las anotadas: para cuando los ganchos no la dejaron escrita
    sesiones = (sesion,) if sesion else tuple(hilo.sesiones)
    if not ctx.config.agente.nombre or not sesiones:
        return _comun.queja(f"«{hilo.nombre}» no tiene una conversación anotada que llevar"
                            " (si sabes cuál es: --sesion <id>)")
    agente = mod_agente.obtener(ctx.config.agente.nombre, ctx.config)
    # la primera anotada que exista en disco, como al retomar: una anotada puede no tener
    # archivo (vacía, o de un agente que no era la conversación del hilo)
    sid, archivo = next(((s, a) for s in sesiones for a in [agente.archivo_de(s)] if a is not None), ("", None))
    if archivo is None and sesion:
        return _comun.queja(f"no encuentro en disco la conversación {sesion}")
    if archivo is None:
        # Claude escribe la conversación recién con el primer mensaje: un hilo sin mensajes no tiene qué llevar,
        # y allá se abre con una nueva (lo que le pasó a Pablo con un hilo «prueba» recién abierto)
        print(_comun.tenue("  su conversación está vacía (sin mensajes): allá se abre con una nueva"))

    # lo que la otra máquina no va a tener
    # la carpeta del agente, la del hilo y la raíz de trabajo: en la raíz está casi todo lo
    # que se hace, aunque el agente arranque en otra parte y el hilo no esté vinculado
    carpetas = {lanzar.carpeta(ctx.config, hilo.ruta), Path(ctx.config.raiz)} | ({hilo.ruta} if hilo.ruta else set())
    if remoto is not None:
        carpetas |= {Path(x).expanduser() for x in remoto.repos}  # los que viven en las dos máquinas
    avisos = sorted({a for c in carpetas if c for a in [_sin_subir(Path(c))] if a})
    if avisos:
        print("la conversación viaja, los archivos no. Aquí hay trabajo que allá no va a estar:")
        for a in avisos:
            print(f"  · {a}")
        print(_comun.tenue("  (sincroniza primero, o sigue sabiendo que el agente de allá no lo verá)"))
        if not si:
            if not sys.stdin.isatty():
                return _comun.queja("hay trabajo sin subir; --si para llevarla igual")
            if input("¿la llevo igual? [s/N] ").strip().lower() not in ("s", "si", "sí", "y", "yes"):
                print("no se movió nada")
                return 1

    relativa = tel.estado.vinculos().get(hilo.nombre, "")
    if remoto is None:
        return _llevar_por_el_bus(ctx, tel, hilo, valor, sid, archivo, relativa, si=si)
    from telar import mudanza

    # los pasos, para la página (telar.mudanza.progreso), como por el bus; aquí no hay revisión allá
    mudanza.progreso(ctx.config, hilo.nombre, "revisar", maquina=remoto.nombre,
                     bytes=Path(archivo).stat().st_size if archivo is not None else 0, error="", avisos=[])

    def falla(texto: str) -> int:
        mudanza.progreso(ctx.config, hilo.nombre, "falla", error=texto)
        return _comun.queja(texto)

    carpeta = mod_remoto.carpeta_remota(ctx.config, remoto, relativa)
    if relativa.startswith("/"):
        # vinculado fuera de la raíz: allá no hay traducción de esa carpeta. Si no existe en
        # la misma ruta del hogar, el agente de allá sigue la conversación sin sus archivos.
        faltante = _falta_alla(remoto, relativa)
        if faltante:
            print(f"su carpeta, {faltante}, no existe en {remoto.destino}: el agente de allá recordará "
                  "la conversación pero no tendrá esos archivos (clónalos allá primero)")
            if not si:
                if not sys.stdin.isatty():
                    return falla(f"{faltante} no existe en {remoto.destino}; --si para llevarla igual")
                if input("¿la llevo igual? [s/N] ").strip().lower() not in ("s", "si", "sí", "y", "yes"):
                    print("no se movió nada")
                    return 1
    # 1. cerrar aquí: desde ahora la conversación sigue solo allá
    mudanza.progreso(ctx.config, hilo.nombre, "cerrar")
    if tel.mux is not None and tel.vivo(hilo):
        try:
            tel.mux.cerrar(hilo.id)
        except ErrorDeMux as e:
            return falla(f"no pude cerrar el hilo aquí: {e}")
    mudanza.progreso(ctx.config, hilo.nombre, "copiar")
    # 2. llevar la conversación (si tiene: una vacía no se copia, y allá se abre una nueva)
    destino, problema = mod_remoto.copiar_conversacion(remoto, archivo, sid, carpeta) if archivo is not None else ("", "")
    if problema:
        return falla(f"no se llevó la conversación: {problema}. Aquí quedó cerrada; "
                     f"`telar hilo retomar` la reabre en esta máquina.")
    # 3. abrirla allá, retomándola
    mudanza.progreso(ctx.config, hilo.nombre, "abrir")
    try:
        mod_remoto.abrir(ctx, tel, hilo.nombre, remoto, relativa=relativa, conversacion=sid if archivo is not None else "")
    except (ErrorDeMux, ErrorDeAgente) as e:
        return falla(f"la conversación ya está en {remoto.destino} ({destino}), pero no pude abrir "
                     f"el hilo: {e}. `telar hilo retomar` lo intenta de nuevo.")
    mudanza.progreso(ctx.config, hilo.nombre, "listo", carpeta=str(carpeta))
    tel.estado.desarchivar(hilo.nombre)
    from telar import directorio as mod_directorio

    mod_directorio.publicar_callado(ctx, tel, remoto.nombre)
    if archivo is None:
        print(f"«{hilo.nombre}» sigue en {remoto.destino}, con una conversación nueva")
    else:
        print(f"«{hilo.nombre}» sigue en {remoto.destino}, retomando la conversación {sid[:8]}")
        print(_comun.tenue(f"  allá: {destino}; aquí queda la copia de como estaba al irse"))
    return 0


def _llevar_por_el_bus(ctx, tel: _comun.Telar, hilo, maquina: str, sid: str, archivo, relativa: str, *,
                       si: bool = False) -> int:
    """Lo de `_llevar` hacia una máquina del bus (telar.mudanza). Antes de tocar nada, se le pregunta a la de allá si
    puede recibirlo (`hilo-revisar`): lo grave no se lleva, y lo que llegaría a medias (su carpeta sin clonar) se
    pregunta. Después se cierra aquí (la misma conversación viva en dos máquinas se bifurca), viaja por el bus y allá
    se abre retomándola. Si allá no se abre, se vuelve a abrir aquí: el hilo no queda cerrado en ninguna parte. Cada
    paso queda en el progreso de la mudanza (telar.mudanza.progreso), que la página dibuja."""
    from telar import bus as mod_bus
    from telar import mudanza

    pesa = Path(archivo).stat().st_size if archivo is not None else 0
    mudanza.progreso(ctx.config, hilo.nombre, "revisar", maquina=maquina, bytes=pesa, error="", avisos=[])

    def falla(texto: str) -> int:
        mudanza.progreso(ctx.config, hilo.nombre, "falla", error=texto)
        return _comun.queja(texto)

    try:
        revision = mod_bus.pedir(ctx.config, maquina, mudanza.VERBO_REVISAR,
                                 {"hilo": hilo.nombre, "sesion": sid if archivo is not None else "", "relativa": relativa},
                                 espera=15)
    except mod_bus.ErrorDeBus:
        revision = {}  # un telar de antes allá no sabe revisar: se sigue como antes
    if revision.get("graves"):
        return falla(f"en {maquina} no se puede recibir: " + "; ".join(revision["graves"]) + ". No se movió nada.")
    if revision.get("avisos"):
        mudanza.progreso(ctx.config, hilo.nombre, "revisar", avisos=revision["avisos"])
        print(f"en {maquina}, el hilo llegaría a medias:")
        for a in revision["avisos"]:
            print(f"  · {a}")
        if not si:
            if not sys.stdin.isatty():
                return falla(f"en {maquina}, " + "; ".join(revision["avisos"]) + " (--si para llevarla igual)")
            if input("¿la llevo igual? [s/N] ").strip().lower() not in ("s", "si", "sí", "y", "yes"):
                print("no se movió nada")
                mudanza.progreso(ctx.config, hilo.nombre, "falla", error="no se movió nada")
                return 1

    mudanza.progreso(ctx.config, hilo.nombre, "cerrar")
    estaba_vivo = tel.mux is not None and tel.vivo(hilo)
    if estaba_vivo:
        try:
            tel.mux.cerrar(hilo.id)
        except ErrorDeMux as e:
            return falla(f"no pude cerrar el hilo aquí: {e}")
    mudanza.progreso(ctx.config, hilo.nombre, "copiar")
    try:
        r = mudanza.enviar(ctx, hilo.nombre, maquina, sid if archivo is not None else "",
                           Path(archivo) if archivo is not None else None, relativa,
                           al_abrir=lambda: mudanza.progreso(ctx.config, hilo.nombre, "abrir"))
    except mudanza.ErrorDeMudanza as e:
        # allá no se abrió: aquí se vuelve a abrir, retomando la misma conversación, como si no se hubiera ido
        vuelta = ""
        if estaba_vivo:
            nuevo = _comun.tejer(ctx)
            de_nuevo = next((h for h in nuevo.hilos if h.nombre == hilo.nombre), None)
            if de_nuevo is not None and _retomar(ctx, nuevo, de_nuevo) == 0:
                vuelta = " Se volvió a abrir aquí, con su conversación."
        return falla(f"{e}.{vuelta or ' Aquí quedó cerrada; `telar hilo retomar` la reabre en esta máquina.'}")
    mudanza.progreso(ctx.config, hilo.nombre, "listo", carpeta=r.get("carpeta", ""), aviso=r.get("aviso", ""))
    tel.estado.archivar(hilo.nombre)
    print(f"«{hilo.nombre}» sigue en {maquina}, " + (f"retomando la conversación {sid[:8]}" if archivo is not None
                                                       else "con una conversación nueva"))
    if r.get("aviso"):
        print(_comun.tenue(f"  {r['aviso']}"))
    print(_comun.tenue(f"  allá: {r.get('carpeta', '?')}; aquí queda archivado, con la copia de como estaba al irse"))
    return 0


def _matar_remoto(ctx, tel: _comun.Telar, hilo) -> None:
    anotado = tel.estado.remotos().get(hilo.nombre)
    remoto = _remoto_de(ctx, anotado["remoto"]) if anotado else None
    if remoto is None or not anotado.get("sesion"):
        return
    problema = mod_remoto.matar(remoto, anotado["sesion"])
    if problema:
        print(_comun.tenue(f"  su ventana en {remoto.destino} no se pudo cerrar: {problema}"))
    else:
        print(_comun.tenue(f"  cerrada su ventana en {remoto.destino}"))


def _remoto_de(ctx, nombre: str):
    return next((r for r in ctx.config.remotos if r.nombre == nombre), None)


def _sesiones(hilo) -> str:
    if not hilo.sesiones:
        return ""
    return f"; conversación anotada: {hilo.sesiones[0]}"


def _leer(ctx, o) -> int:
    """Lo último de un hilo, sin moverle nada: ni foco, ni atención, ni estado (telar.servicios.historias)."""
    from telar import historia
    from telar.servicios import ErrorDeServicio
    from telar.servicios import historias

    referencia = o.hilo or o.valor
    if not referencia and not o.maquina:
        tel = _comun.tejer(ctx, con_ficha=False)
        if _comun.hilo_actual(tel) is None:
            return _comun.sin_hilo("hilo", tel)
    try:
        datos = historias.leer(ctx, referencia, ultimos=o.ultimos, maquina=o.maquina).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(datos)
    print(historia.como_texto(datos))
    return 0


def caidos(tel: _comun.Telar, horas: float, ahora=None) -> list:
    """Los hilos que el nodo vio vivos en las últimas `horas` y ya no tienen ventana ni sesión: no
    archivados, de esta máquina (un remoto lo reabre la suya) y con una conversación que retomar."""
    from datetime import datetime, timedelta

    est = tel.estado
    limite = (ahora or datetime.now()) - timedelta(hours=horas)
    vistos, remotos = est.vivos_vistos(), est.remotos()
    return [h for h in tel.hilos
            if vistos.get(h.nombre) and vistos[h.nombre] >= limite and not h.archivado and h.sesiones
            and h.nombre not in remotos and not tel.vivo(h)]


def _caidos(ctx, o) -> int:
    tel = _comun.tejer(ctx, con_ficha=False)
    lista = caidos(tel, o.horas)
    if o.json and o.seco:
        return _comun.escribir_json({"caidos": [h.nombre for h in lista]})
    if not lista:
        print(_comun.tenue(f"ningún hilo que estuviera vivo en las últimas {o.horas:g} h está caído"))
        return 0
    if o.seco:
        print("reabriría: " + ", ".join(h.nombre for h in lista))
        return 0
    fallas = 0
    for h in lista:
        # cada uno con el telar al día: retomar abre ventanas y cambia lo que está vivo
        fallas += _retomar(ctx, _comun.tejer(ctx, con_ficha=False), h) != 0
    print(f"reabiertos {len(lista) - fallas} de {len(lista)}")
    return 1 if fallas else 0


def _retomar(ctx, tel: _comun.Telar, hilo) -> int:
    """Sacarlo del archivo y reabrirlo tal como estaba: su carpeta, su agente, su conversación.

    Es la otra mitad de archivar con --cerrar. El tab se cerró y la conversación quedó en
    disco con el id que telar le dio al abrirla; retomar la reabre con `--resume` en vez
    de pedirle a nadie que busque el id y lo escriba. Si el hilo sigue vivo, solo se va a él.
    """
    est = tel.estado
    # el de otra máquina lo desarchiva su dueño (telar.estado, «hilos ajenos»), y aquí la copia, que es
    # lo que vale si el dueño no publica su archivo (un telar de antes allá)
    dueno = _dueno(ctx, hilo) if est.es_ajeno(hilo.nombre) else ""
    if dueno and hilo.archivado:
        o = SimpleNamespace(verbo="desarchivar", valor="", cerrar=False, json=True)
        problema = _al_dueno(ctx, dueno, o, hilo.nombre)
        if problema:
            print(_comun.tenue(f"  sigue archivado allá: {problema}"))
        else:
            _adelantar(est, o, hilo.nombre, ctx.config.raiz)
    est.desarchivar(hilo.nombre)
    if tel.mux is None or not tel.viva:
        return _comun.queja(tel.aviso or "la sesión no está viva: primero telar tejer")
    try:
        if hilo.nombre in tel.vivos:
            tel.mux.ir(hilo.id)
            print(f"«{hilo.nombre}» ya estaba abierto")
            return 0
        relativa = est.vinculos().get(hilo.nombre, "")
        anotado = est.remotos().get(hilo.nombre)
        remoto = _remoto_de(ctx, anotado["remoto"]) if anotado else None
        if remoto is not None:
            # un hilo remoto se reabre por su transporte: si la sesión de allá sigue viva,
            # `-A` se engancha a ella; si no, se crea retomando su conversación, la que
            # allá tenga archivo: la anotada aquí puede no ser la que quedó
            conversacion, problema = mod_remoto.conversacion_alla(remoto, hilo.nombre, list(hilo.sesiones))
            if conversacion is None:
                print(_comun.tenue(f"  no pude preguntar allá qué conversación retomar ({problema}): uso la anotada aquí"))
                conversacion = hilo.sesiones[0] if hilo.sesiones else ""
            elif conversacion and conversacion != (hilo.sesiones[0] if hilo.sesiones else ""):
                # la de un hilo ajeno la publica su dueño cuando su agente la abre; la de aquí es el
                # respaldo mientras no la publique
                est.anotar_sesion(hilo.nombre, conversacion, revivir=False)
            elif not conversacion and hilo.sesiones:
                print(_comun.tenue("  allá no hay archivo de ninguna de sus conversaciones: se abre una nueva"))
            mod_remoto.abrir(ctx, tel, hilo.nombre, remoto, relativa=relativa,
                             sesion=anotado.get("sesion", ""), conversacion=conversacion)
            print(f"retomado «{hilo.nombre}» en {remoto.destino}"
                  + (f" · conversación {conversacion[:8]}" if conversacion else ""))
            return 0
        carpeta = Path(ctx.config.raiz) / relativa if relativa else None
        if carpeta is not None and not carpeta.is_dir():
            carpeta = None
        try:
            lanz = lanzar.para_hilo(ctx.config, hilo.nombre, carpeta)
        except ErrorDeAgente as e:
            print(_comun.tenue(f"  sin agente: {e}"))
            lanz = None
        if lanz is None:
            tel.mux.crear_tab(hilo.nombre, ruta=carpeta, foco=True)
        else:
            tel.mux.crear_tab(hilo.nombre, ruta=lanz.carpeta, comando=lanz.comando, foco=True)
            lanzar.anotar(ctx.config, hilo.nombre, lanz, tel.mux)
        nuevo = next((h for h in tel.mux.hilos() if h.nombre == hilo.nombre), None)
        if nuevo is not None:
            tel.mux.ir(nuevo.id)
    except (ErrorDeMux, ErrorDeAgente) as e:
        return _comun.queja(f"no pude retomar «{hilo.nombre}»: {e}")
    if lanz is not None and lanz.retoma:
        print(f"retomado «{hilo.nombre}» · conversación {lanz.retoma}")
    elif lanz is not None and lanz.vacia:
        print(f"retomado «{hilo.nombre}» · su conversación estaba vacía (sin mensajes): se abre de nuevo, con el mismo id")
    elif lanz is not None:
        print(f"retomado «{hilo.nombre}» · no había conversación guardada: una nueva")
    else:
        print(f"retomado «{hilo.nombre}»")
    return 0


def _mudar(tel: _comun.Telar, hilo, destino: str, ctx) -> int:
    """Lleva el panel donde corre esto a otro hilo, con su conversación.

    Es para cuando una conversación empieza en un lado y resulta ser de otro proyecto:
    en vez de cerrarla y abrir otra, se muda. El panel conserva lo que corre adentro —el
    agente no se reinicia— y su conversación deja de figurar en el hilo viejo, porque una
    conversación vive en un hilo y solo en uno.
    """
    if not destino:
        return _comun.queja("telar hilo mudar «<hilo destino>»")
    if tel.mux is None or not tel.viva:
        return _comun.queja(tel.aviso or "la sesión no está viva")
    panel = panel_del_entorno(ctx.config.multiplexor)
    if not panel:
        return _comun.queja(
            "no sé en qué panel corro: el multiplexor no exportó su id (o exporta $TELAR_PANEL)"
        )
    otro, problema = _comun.resolver(tel, destino)
    if otro is None:
        return _comun.queja(problema)
    if otro.nombre == hilo.nombre:
        print(_comun.tenue(f"  ya estoy en «{hilo.nombre}»"))
        return 0
    if otro.nombre not in tel.vivos:
        return _comun.queja(f"«{otro.nombre}» no tiene tab abierto; `telar hilo retomar` lo abre")
    try:
        tel.mux.mover_pane(panel, tab=otro.id)
    except ErrorDeMux as e:
        return _comun.queja(f"no pude mudarme: {e}")
    conversacion = tel.estado.paneles().get(panel, "")
    if not conversacion:
        # sin el mapa panel → conversación (lo llenan telar al abrir el hilo y los ganchos),
        # solo se puede saber cuál es la mía si el hilo tenía una sola
        sueltas = tel.estado.sesiones().get(hilo.nombre, ())
        conversacion = sueltas[0] if len(sueltas) == 1 else ""
    if conversacion:
        tel.estado.anotar_sesion(otro.nombre, conversacion, panel=panel)
    print(f"«{hilo.nombre}» → «{otro.nombre}»" + (f" · conversación {conversacion}" if conversacion else ""))
    return 0
