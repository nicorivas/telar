"""`telar hilo` — actuar sobre un hilo: vincularlo, renombrarlo, priorizarlo, archivarlo.

Todo lo que se le hace a un hilo suelto vive aquí, con un verbo por operación:

    telar hilo vincular proyectos/faro     asociarlo a una carpeta del repositorio
    telar hilo desvincular                 soltar esa asociación
    telar hilo renombrar «Faro»            renombrarlo, y mover con él lo que telar sabía
    telar hilo adoptar [«faro»]            recoger el estado que quedó en otro nombre
    telar hilo prioridad 1|2|3|ninguna     prioridad manual, para ordenar
    telar hilo padre «Telar»|ninguno       colgarlo de otro hilo (el del proyecto, el que lo encarga): la barra lo
                                           anida debajo, hereda sus etiquetas, y el padre sabe de él
    telar hilo hijo «Mobile» [--carpeta R] [--texto "…"|-]   abrir un hilo hijo de este, con su agente y un
                                           encargo; sin --carpeta, la de este hilo
    telar hilo hijo «Mobile» --rama [NOMBRE] …   el hijo trabaja en su propia rama, en un worktree
                                           (~/worktrees/<repo>-<rama>) que sale de la rama de este hilo
    telar hilo hijo «Mobile» --esfuerzo low|medium|high|xhigh …   su agente arranca con ese esfuerzo (también
                                           al retomarlo); sin la opción, el de siempre
    telar hilo fusionar «Mobile» [--seguir] [--mensaje "…"]   fusionar la rama de ese hijo en la de este hilo
                                           (prueba antes, sin tocar nada) y cerrarlo, archivarlo y borrar su
                                           worktree; con --seguir, fusiona lo commiteado y lo deja trabajando
    telar hilo descartar «Mobile» [--forzar]   cerrar ese hijo y borrar su worktree y su rama sin fusionar
                                           (se niega si hay trabajo sin fusionar; --forzar lo pierde)
    telar hilo etiquetas "trabajo, cliente"|ninguna   sus etiquetas (todas: reemplazan a las de antes); los
                                           modos de la página filtran la lista por ellas
    telar hilo mudar «Arrayán»               llevarse este panel (y su conversación) a ese hilo
    telar hilo cerrar                      cerrar su tab (y lo que corra adentro) y
                                           olvidarlo: sale de la lista. Para guardarlo
                                           está `archivar`
    telar hilo archivar [--cerrar] [--con-hijos]   sacarlo de la lista sin perderlo (y a sus hijos)
    telar hilo desarchivar
    telar hilo publicar                    que las otras personas del bus lo vean en su directorio (por
                                           defecto, un hilo es privado: no sale)
    telar hilo privar                      volver a privado
    telar hilo retomar                     desarchivarlo y reabrirlo, con su agente retomando
                                           la conversación que tenía. Uno archivado aquí que el bus
                                           dice de otra máquina se retoma allá (si está apagada,
                                           dice si se puede seguir aquí)
    telar hilo seguir [--si]               seguir aquí uno cuya máquina está apagada, desde la copia de
                                           su conversación que quedó aquí (telar.seguir): sin --si, dice
                                           de cuándo es la copia y cuánto falta; con --si, lo toma y lo
                                           abre. Cuando aquella vuelva, cede sola
    telar hilo olvidar                     borrar lo que telar sabía de él
    telar hilo dormir [--seco]             cerrar su agente y dejar su ventana esperando, en su lugar de la lista
                                           (el nodo lo hace solo tras `[hilos] dormir_tras` sin actividad: telar.dormir);
                                           con --seco, por qué cada hilo de aquí se dormiría o no
    telar hilo despertar [--texto "…"] [--maquina M]   retomar su agente con ese primer mensaje: el de uno dormido,
                                           en su ventana (abrirlo, o que le llegue algo, también lo despierta); el de
                                           uno cerrado o archivado, con su conversación. El de otra máquina (--maquina,
                                           o la que dice el bus), por el bus a su nodo; si esa máquina está fuera de
                                           línea, queda en cola y se hace cuando vuelva (telar.alcance)
    telar hilo caidos [--horas N] [--seco] reabrir de una vez, con su conversación, los hilos que
                                           estaban vivos en esta máquina y ya no tienen ventana
                                           (tmux se cayó, la máquina se reinició). Los cuenta el
                                           nodo cada 30 s; --horas, qué tan reciente (6)
    telar hilo llevar [máquina] [--sesion ID]  pasar su conversación a otra máquina: una de [remotos]
                                           (por ssh) o una tuya del bus, como tu lugar en un
                                           servidor (por el bus, telar.mudanza). Sigue allá,
                                           retomada; aquí se cierra recién cuando allá lo abrió (si
                                           no llega, aquí sigue como estaba). Pedido por el agente
                                           del hilo, se va cuando termina su turno. Con --sesion, esa
                                           conversación aunque telar no la tenga anotada
    telar hilo ver                         lo mismo que `telar hilos` para uno solo
    telar hilo leer [«Faro»] [--ultimos N] [--maquina M]   lo último que pasó en ese hilo (de esa máquina, por el bus): lo que se le pidió y
                                           lo que respondió su agente (5 turnos si no se dice)
    telar hilo borradores [«Faro»] [--maquina M]   los próximos prompts que le guardaste, en orden (telar.borradores)
    telar hilo borradores --agregar "…"|-   uno más, al final (con «-», por la entrada)
    telar hilo borradores --mandar N|ID [--enviar] [--esperar]   escribirlo en su entrada sin ⏎ (con --enviar, y ⏎);
                                           sale de la lista. Si su agente trabaja, se niega; con --esperar, sale
                                           solo cuando termine su turno
    telar hilo borradores --borrar N|ID    sacarlo de la lista
    telar hilo contexto [«Faro»] [--maquina M]   lo que carga el contexto de su conversación: cuánto pesa, desde
                                           cuándo, y qué es (los CLAUDE.md, la memoria, los hooks, las skills, los
                                           MCP, lo que leyó, lo que se repite, lo de otros hilos), con sus tamaños

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

import os
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
    "relevo",
    "vincular",
    "desvincular",
    "renombrar",
    "adoptar",
    "prioridad",
    "etiquetas",
    "padre",
    "hijo",
    "fusionar",
    "descartar",
    "mudar",
    "cerrar",
    "archivar",
    "desarchivar",
    "publicar",
    "privar",
    "retomar",
    "olvidar",
    "dormir",
    "despertar",
    "llevar",
    "seguir",
    "leer",
    "contexto",
    "borradores",
    "caidos",
)


#: los verbos que cambian el registro de un hilo: sobre uno que vive en otra máquina, se le piden a su
#: dueño por el bus (docs/propuestas/un-dueno-por-hilo.md), que los aplica y los vuelve a publicar
AL_DUENO = ("vincular", "desvincular", "renombrar", "prioridad", "etiquetas", "padre", "archivar", "desarchivar", "publicar", "privar",
            "cerrar", "olvidar", "dormir", "despertar")

#: los verbos que no llevan valor: el nombre suelto que se les dé es el hilo sobre el que actúan
SIN_VALOR = ("ver", "desvincular", "cerrar", "archivar", "desarchivar", "publicar", "privar", "retomar", "olvidar",
             "fusionar", "descartar", "dormir", "despertar", "seguir")


#: los esfuerzos que se le pueden dar al agente de un hijo (`--esfuerzo`; Claude Code: `--effort`)
ESFUERZOS = ("low", "medium", "high", "xhigh")


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hilo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=VERBOS, help="qué hacerle")
    p.add_argument(
        "valor",
        nargs="?",
        default="",
        help="la carpeta, el nombre nuevo, el hilo que se adopta, la prioridad o las etiquetas; en los verbos sin valor, el hilo",
    )
    p.add_argument("--hilo", default="", help="sobre cuál actuar (por defecto, este)")
    p.add_argument("--cerrar", action="store_true", help="al archivar, cerrar además el hilo")
    p.add_argument("--si", action="store_true", help="con llevar: seguir aunque haya trabajo sin subir; con seguir: "
                                                     "tomarlo y abrirlo aquí (sin --si, solo dice lo que falta)")
    p.add_argument("--subir", action="store_true", help="con llevar: commitear lo suyo sin commitear (solo eso) y "
                                                        "subirlo antes de llevarlo")
    p.add_argument("--sesion", default="",
                   help="con llevar: el id de la conversación, si telar no la tiene anotada (salida de emergencia)")
    p.add_argument("--ultimos", type=int, default=0, metavar="N", help="con leer: cuántos turnos")
    p.add_argument("--maquina", default="", metavar="NOMBRE",
                   help="con leer, contexto y despertar: un hilo de otra máquina, por el bus")
    p.add_argument("--json", action="store_true", help="el hilo resultante, en una línea")
    p.add_argument("--horas", type=float, default=6, help="con caidos: vistos vivos en estas últimas horas")
    p.add_argument("--seco", action="store_true",
                   help="con caidos: solo decir cuáles reabriría; con dormir: por qué cada hilo de aquí se dormiría o no")
    p.add_argument("--aqui", action="store_true",
                   help="con despertar: lo que corre el ⏎ en la ventana de un hilo dormido (despierta aunque no esté anotado)")
    p.add_argument("--ruta", action="store_true", help="con relevo: solo decir dónde va el relevo de este hilo")
    p.add_argument("--con-hijos", action="store_true", help="con archivar: también sus hilos hijos")
    p.add_argument("--sin-avisar", action="store_true", help="con archivar: sin avisarle a su padre")
    p.add_argument("--carpeta", default="", help="con hijo: la carpeta del hijo (por defecto, la de este hilo)")
    p.add_argument("--texto", default="",
                   help="con hijo: lo que se le encarga al abrirlo (o «-»: por la entrada); con despertar y retomar: su "
                        "primer mensaje")
    p.add_argument("--rama", nargs="?", const="-", default="", metavar="NOMBRE",
                   help="con hijo: que trabaje en su propia rama y su worktree (sin nombre, el del hijo)")
    p.add_argument("--esfuerzo", choices=ESFUERZOS, default="",
                   help="con hijo: el esfuerzo con que arranca su agente (sin la opción, el de siempre)")
    p.add_argument("--seguir", action="store_true", help="con fusionar: fusionar lo commiteado y dejar al hijo trabajando")
    p.add_argument("--mensaje", default="", help="con fusionar: el mensaje del commit de fusión")
    p.add_argument("--forzar", action="store_true", help="con descartar: aunque pierda trabajo sin fusionar")
    p.add_argument("--agregar", default=None, metavar="TEXTO", help="con borradores: uno más, al final (o «-»: por la entrada)")
    p.add_argument("--mandar", default="", metavar="N|ID",
                   help="con borradores: escribirlo en la entrada de su hilo, sin ⏎ (sale de la lista)")
    p.add_argument("--enviar", action="store_true", help="con borradores --mandar: y apretar ⏎")
    p.add_argument("--esperar", action="store_true",
                   help="con borradores --mandar: si su agente está trabajando, que salga cuando termine su turno")
    p.add_argument("--borrar", default="", metavar="N|ID", help="con borradores: sacarlo de la lista")
    p.add_argument("--soltar", action="store_true",
                   help="con borradores: lo que corre el fin de un turno, aparte: el primero en espera, si el agente quedó quieto")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "leer":
        return _leer(ctx, o)
    if o.verbo == "contexto":
        return _contexto(ctx, o)
    if o.verbo == "borradores":
        return _borradores(ctx, o)
    if o.verbo == "caidos":
        return _caidos(ctx, o)
    if o.verbo == "despertar" and o.aqui:
        # el ⏎ en la ventana de un hilo dormido: lo despierta reemplazando ese panel (y con él, este proceso)
        from telar import dormir

        nombre = o.hilo or o.valor or os.environ.get("TELAR_HILO", "").strip()
        if not nombre:
            return _comun.queja("¿cuál? --hilo, o $TELAR_HILO")
        return dormir.despertar_aqui(ctx.config, nombre, o.texto)
    if o.verbo == "dormir" and o.seco:
        return _dormir_seco(ctx, o)
    if o.valor and o.verbo in SIN_VALOR:
        # `telar hilo olvidar X` actuaba sobre el hilo actual e ignoraba X: lo suelto es el hilo
        if o.hilo:
            return _comun.queja(f"«{o.verbo}» no lleva valor: «{o.valor}» sobra (el hilo ya es «{o.hilo}»)")
        o.hilo = o.valor
    if o.verbo == "seguir":
        # un hilo de otra máquina, que aquí puede no estar en la lista: por su nombre
        return _seguir(ctx, o)

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
    if o.verbo == "despertar":
        # donde viva, aunque aquí no se lo conozca: aquí, por el bus a su nodo, o a la cola de su máquina si está fuera
        # de línea (telar.alcance). No va por el pedido «hilo» de siempre: ese corre `despertar` allá, que antes solo
        # despertaba a los dormidos
        salida, despierto = _despertar(ctx, tel, hilo, o)
        if o.json:
            tel = _comun.tejer(ctx)
            actual = tel.por_nombre(hilo.nombre) or Hilo(id=hilo.id or hilo.nombre, nombre=hilo.nombre)
            return _comun.escribir_json({"hilo": _comun.json_hilo(actual, tel), "codigo": salida, "despertar": despierto})
        return salida
    if o.verbo == "renombrar" and o.valor.strip():
        # antes de pedírselo al dueño: un nombre que choca con el de otro hilo no se acepta en ninguna máquina
        problema = _choca(ctx, tel, o.valor.strip(), hilo.nombre)
        if problema:
            return _comun.queja(problema)
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
        salida = _renombrar(tel, hilo, o.valor, ctx.config)
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
        _queda_la_rama(est, hilo.nombre)
    elif o.verbo == "padre":
        valor = o.valor.strip()
        if not valor:
            return _comun.queja("¿de cuál? «telar hilo padre Telar», o «ninguno» para soltarlo")
        try:
            est.colgar(hilo.nombre, "" if valor in ("ninguno", "ninguna") else valor)
        except ValueError as e:
            return _comun.queja(str(e))
        print(f"«{hilo.nombre}» cuelga de «{valor}»" if valor not in ("ninguno", "ninguna") else f"«{hilo.nombre}» suelto")
    elif o.verbo == "hijo":
        return _hijo(ctx, tel, hilo, o)
    elif o.verbo == "fusionar":
        return _fusionar(ctx, tel, hilo, o)
    elif o.verbo == "descartar":
        return _descartar(ctx, tel, hilo, o)
    elif o.verbo == "archivar":
        # sus hijos primero (los que siguen en la lista), con lo mismo que se le pidió a él y sin avisarle a él
        if o.con_hijos:
            for hijo in est.hijos(hilo.nombre):
                if hijo not in est.archivados():
                    main(["archivar", "--con-hijos", "--sin-avisar", *(["--cerrar"] if o.cerrar else []), "--hilo", hijo], ctx)
        est.archivar(hilo.nombre)
        print(f"archivado «{hilo.nombre}»" + _sesiones(hilo))
        if not o.sin_avisar:
            _avisar_al_padre(ctx, est, hilo.nombre, "se archivó: terminó lo suyo, o lo dejó para después")
        if o.cerrar and dueno:
            salida = _cerrar_vista(tel, hilo)
        elif o.cerrar:
            salida = _cerrar(ctx, tel, hilo)
        else:
            print(_comun.tenue("  sigue abierto; --cerrar además lo cierra en el multiplexor"))
    elif o.verbo == "desarchivar":
        est.desarchivar(hilo.nombre)
        print(f"de vuelta en la lista «{hilo.nombre}»")
    elif o.verbo == "etiquetas":
        if not o.valor.strip():
            return _comun.queja("¿cuáles? «telar hilo etiquetas \"trabajo, cliente\"», o «ninguna» para quitarlas")
        try:
            puestas = est.etiquetar(hilo.nombre, o.valor)
        except ValueError as e:
            return _comun.queja(str(e))
        print(f"«{hilo.nombre}»: {', '.join(puestas)}" if puestas else f"«{hilo.nombre}» sin etiquetas")
    elif o.verbo == "publicar":
        est.publicar(hilo.nombre)
        print(f"«{hilo.nombre}» es público: las otras personas del bus lo ven en su directorio (su nombre, su carpeta "
              f"y una línea; nunca la conversación) y pueden escribirle")
    elif o.verbo == "privar":
        est.privar(hilo.nombre)
        print(f"«{hilo.nombre}» es privado: sale del directorio de las otras personas")
    elif o.verbo == "retomar":
        salida = _retomar(ctx, tel, hilo, o.texto)
    elif o.verbo == "dormir" and dueno:
        pass  # lo hizo su dueño, allá
    elif o.verbo == "dormir":
        salida = _dormir(ctx, tel, hilo)
    elif o.verbo == "llevar":
        salida = _llevar(ctx, tel, hilo, o.valor, o.si, o.sesion, subir=o.subir)
    elif o.verbo == "relevo":
        # /relevo: dónde va el relevo de este hilo; sin --ruta, además, que al terminar el turno se limpie la
        # conversación y la nueva lo lea (telar.rotacion: el nodo teclea /clear y después el aviso)
        from telar import rotacion

        ruta = rotacion.ruta_handoff(ctx.config, hilo.nombre, est.vinculos().get(hilo.nombre, ""))
        if o.ruta:
            print(ruta)
            return 0
        if not ruta.is_file():
            return _comun.queja(f"primero escribe el relevo en {ruta}: es lo que leerá la conversación siguiente")
        sesion = (est.sesiones().get(hilo.nombre) or ("",))[0]
        if not sesion:
            return _comun.queja(f"«{hilo.nombre}» no tiene una conversación anotada: telar no sabría cuándo empezó la nueva")
        rotacion.pedir_handoff(ctx.config, hilo.nombre, sesion, ruta, o.valor)
        print(f"listo: al terminar este turno, /clear; la conversación nueva leerá {ruta}"
              + (f" y seguirá con: {o.valor}" if o.valor else ""))
    elif o.verbo == "olvidar":
        est.olvidar(hilo.nombre)
        print(f"telar olvidó «{hilo.nombre}» (el registro de foco queda: es historia)")
        _queda_la_rama(est, hilo.nombre)

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


def _renombrar(tel: _comun.Telar, hilo, nuevo: str, config=None) -> int:
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
    if config is not None:
        _mudar_casilla(config, hilo.nombre, nuevo)
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


def _choca(ctx, tel: _comun.Telar, nombre: str, propio: str = "") -> str:
    """Por qué no se puede llamar así un hilo: su nombre choca con el de otro (vivo o archivado, de esta máquina o de
    otra según el bus) que solo difiere en mayúsculas, tildes o espacios, y sus casillas serían la misma
    (telar.casilla). Dice con cuál, y propone otro. "" si no choca. `propio`: el hilo que se renombra, que no choca
    consigo mismo (cambiarle solo las mayúsculas se puede)."""
    from telar import casilla

    conocidos = _comun.nombres_conocidos(ctx, tel)
    otros = [n for n in conocidos if not (propio and casilla.mismo_nombre(n, propio))]
    otro = casilla.choque(nombre, otros)
    if not otro:
        return ""
    conocido = conocidos.get(otro) or next((v for k, v in conocidos.items() if casilla.mismo_nombre(k, otro)), None)
    donde = conocido.donde if conocido is not None else ""
    return (f"«{nombre}» choca con «{otro}»{f' ({donde})' if donde else ''}: solo difieren en mayúsculas, tildes o "
            f"espacios, y los mensajes de uno le llegarían al otro. Ponle otro nombre, por ejemplo "
            f"«{casilla.otro_nombre(nombre, [*conocidos, propio])}»")


def _mudar_casilla(config, viejo: str, nuevo: str) -> None:
    """Lo que esperaba en la casilla del nombre viejo pasa a la del nuevo (sus ganchos ya leen la del nuevo: el
    alias del estado), y la ficha apartada del viejo, si tenía, se suelta."""
    from telar import casilla

    try:
        if pasados := casilla.mudar(config, viejo, nuevo):
            print(_comun.tenue(f"  {pasados} mensaje(s) que esperaban en su casilla pasan a la del nombre nuevo"))
        casilla.soltar_ficha(config, viejo)
    except OSError as e:
        print(_comun.tenue(f"  su casilla no se movió ({e}): lo que esperaba sigue en la del nombre viejo"))


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


def padre_de(est, hilo: str) -> str:
    """Del que cuelga un hilo: el que se le puso o, si no, el que lo abrió (salvo que se haya soltado)."""
    return est.padre(hilo)


#: cómo anota un periódico que abrió un hilo (telar.periodicos, `por=`): quien lo abrió, pero no un hilo
POR_PERIODICO = "periódico "


def padre_que_lee(est, hilo: str) -> str:
    """El padre de `hilo` al que se le puede avisar: el de `padre_de`, salvo que sea el periódico que lo abrió
    («periódico a-solas»). Ese no es un hilo y nadie lee su casilla: los avisos de cada turno quedaban ahí, huérfanos.
    Si el periódico declara un padre (`padre` en su definición), el hilo cuelga de ese y el aviso le llega."""
    padre = padre_de(est, hilo)
    return "" if padre.startswith(POR_PERIODICO) else padre


def _avisar_al_padre(ctx, est, hilo: str, que: str) -> None:
    """Un aviso (no lo despierta: lo lee en su próximo turno) al padre de `hilo`, si tiene y hay bus."""
    from telar import bus as mod_bus

    padre = padre_que_lee(est, hilo)
    if not padre or not mod_bus.hay_bus(ctx.config):
        return
    try:
        from telar.ordenes import mensaje

        mensaje.enviar(ctx, padre, f"«{hilo}», tu hilo hijo, {que}.", modo="aviso", de=hilo)
    except Exception:  # noqa: BLE001 - avisar es un extra: lo de este hilo ya está hecho
        pass


def _hijo(ctx, tel, padre, o) -> int:
    """Abrir un hilo hijo de `padre` (`telar hilo hijo «Mobile»`): un tab con su agente, en su carpeta (la del padre si
    no se dice), con el encargo como primer mensaje; cuelga del padre y hereda sus etiquetas."""
    from telar.agente import lanzar

    nombre = " ".join(o.valor.split())
    if not nombre:
        return _comun.queja("¿cómo se llama? telar hilo hijo «Mobile» --texto \"…\"")
    if any(h.nombre == nombre and tel.vivo(h) for h in tel.hilos):
        return _comun.queja(f"ya hay un hilo «{nombre}» abierto: colgarlo es `telar hilo padre {padre.nombre} --hilo {nombre}`")
    if problema := _choca(ctx, tel, nombre):
        return _comun.queja(problema)
    if tel.mux is None or not tel.viva:
        return _comun.queja(tel.aviso or "la sesión no está viva: primero telar tejer")
    est = tel.estado
    texto = sys.stdin.read() if o.texto == "-" else o.texto
    relativa = ""
    if o.carpeta:
        relativa, problema = _ruta_en_raiz(o.carpeta, ctx.config.raiz)
        if relativa is None:
            return _comun.queja(problema)
    else:
        relativa = est.vinculos().get(padre.nombre, "")
    carpeta = None
    if relativa:
        carpeta = Path(relativa) if Path(relativa).is_absolute() else Path(ctx.config.raiz) / relativa
        if not carpeta.is_dir():
            return _comun.queja(f"no existe la carpeta {carpeta}")
    lugar, sin_commitear = None, []
    if o.rama:
        # su propia rama: un worktree que sale de la rama de la carpeta del padre (telar.ramas)
        from telar import ramas as mod_ramas

        if carpeta is None:
            return _comun.queja("un hijo con rama necesita una carpeta en un repositorio: --carpeta, o vincula este hilo")
        sin_commitear = mod_ramas.sucios(carpeta, solo_aqui=True)
        try:
            lugar = mod_ramas.crear(carpeta, nombre, "" if o.rama == "-" else o.rama)
        except mod_ramas.ErrorDeRama as e:
            return _comun.queja(str(e))
        carpeta = Path(lugar["carpeta"])
        relativa, _ = _ruta_en_raiz(str(carpeta), ctx.config.raiz)
        relativa = relativa or str(carpeta)
        # antes de lanzar: el lanzamiento suma el worktree como carpeta de trabajo del agente
        est.anotar_rama(nombre, lugar)
    # también antes: el lanzamiento (y cada vez que se retome) lo lee de ahí. Sin --esfuerzo, el de siempre, aunque un
    # hilo de antes con su nombre tuviera otro
    esfuerzo = getattr(o, "esfuerzo", "") or ""
    est.anotar_esfuerzo(nombre, esfuerzo)
    encargo = texto.strip() and (f"Eres un hilo hijo de «{padre.nombre}», que te encarga esto. Cuando termines, o si "
                                 f"necesitas que decida algo, escríbele con `telar mensaje \"{padre.nombre}\" \"…\"`.\n\n"
                                 + (f"Trabajas en tu propia rama, {lugar['rama']}, en {carpeta}: tu contexto y la skill "
                                    f"/ramas dicen cómo.\n\n" if lugar else "")
                                 + texto.strip())
    lanz = lanzar.para_hilo(ctx.config, nombre, carpeta, encargo or "")
    try:
        if lanz is None:
            tel.mux.crear_tab(nombre, ruta=carpeta, foco=False)
        else:
            tel.mux.crear_tab(nombre, ruta=lanz.carpeta, comando=lanz.comando, foco=False)
    except ErrorDeMux as e:
        est.anotar_esfuerzo(nombre, "")
        if lugar:
            from telar import ramas as mod_ramas

            est.olvidar_rama(nombre)
            try:
                mod_ramas.borrar(lugar, forzar=True)
            except mod_ramas.ErrorDeRama:
                pass
        return _comun.queja(f"no pude abrir «{nombre}»: {e}")
    est.desarchivar(nombre)
    if relativa:
        est.vincular(nombre, relativa)
    est.colgar(nombre, padre.nombre)
    est.anotar_abierto_por(nombre, padre.nombre)
    if lanz is not None:
        lanzar.anotar(ctx.config, nombre, lanz, tel.mux)
    heredadas = est.etiquetas().get(padre.nombre, ())
    if heredadas and not est.etiquetas().get(nombre):
        est.etiquetar(nombre, list(heredadas))
    if o.json:
        return _comun.escribir_json({"hilo": nombre, "padre": padre.nombre, "carpeta": relativa,
                                     "agente": bool(lanz), "encargo": bool(encargo), "rama": lugar,
                                     "esfuerzo": esfuerzo})
    print(f"«{nombre}», hijo de «{padre.nombre}»" + (f" · {relativa}" if relativa else "")
          + (f" (rama {lugar['rama']}, desde {lugar['base']})" if lugar else "")
          + (f" · esfuerzo {esfuerzo}" if esfuerzo else "")
          + ("" if lanz else _comun.tenue("  (sin motor de agentes: quedó una shell)")))
    if lugar and lugar.get("enlazados"):
        print(_comun.tenue(f"  enlazado desde tu carpeta: {', '.join(lugar['enlazados'])}"))
    if sin_commitear:
        print(_comun.tenue(f"  ojo: {len(sin_commitear)} archivo(s) sin commitear en tu carpeta no llegaron a su worktree "
                           f"({', '.join(sin_commitear[:3])}{'…' if len(sin_commitear) > 3 else ''})"))
    return 0


def _queja_rama(e) -> int:
    """El error de una rama (telar.ramas), con los archivos que vienen al caso."""
    if e.archivos:
        print("  " + "\n  ".join(e.archivos[:20]) + (f"\n  … y {len(e.archivos) - 20} más" if len(e.archivos) > 20 else ""),
              file=sys.stderr)
    return _comun.queja(str(e))


def _queda_la_rama(est, hilo: str) -> None:
    lugar = est.ramas().get(hilo)
    if lugar:
        print(_comun.tenue(f"  su worktree ({lugar['ruta']}) y su rama {lugar['rama']} quedan: "
                           f"telar hilo fusionar «{hilo}» o telar hilo descartar «{hilo}»"))


def _fusionar(ctx, tel, hijo, o) -> int:
    """`telar hilo fusionar «Mobile»`: la rama de ese hijo, a la de su padre (telar.ramas.fusionar). Si sale bien y no
    sigue (`--seguir`), se cierra, se archiva y se borran su worktree y su rama."""
    from telar import ramas as mod_ramas

    est = tel.estado
    lugar = est.ramas().get(hijo.nombre)
    if not lugar:
        return _comun.queja(f"«{hijo.nombre}» no trabaja en una rama propia: no hay nada que fusionar")
    try:
        r = mod_ramas.fusionar(lugar, mensaje=o.mensaje, con_cambios=o.seguir)
    except mod_ramas.ErrorDeRama as e:
        return _queja_rama(e)
    salida = {"hilo": hijo.nombre, **r, "cerrado": False, "borrado": False}
    hecho = (f"fusionados {r['commits']} commit(s) de {r['rama']} en {r['base']} ({r['destino']}, {r['commit']})"
             if r["commits"] else f"nada que fusionar: {r['base']} ya tiene todo lo de {r['rama']}")
    if r.get("regenerados"):
        hecho += f"\n  lo compilado, vuelto a generar en la fusión: {', '.join(r['regenerados'])}"
    cl = r.get("changelog")
    if cl and cl["fragmentos"]:
        hecho += (f"\n  el CHANGELOG: {', '.join(cl['fragmentos'])} pasó a {cl['archivo']} ([Unreleased], "
                  f"{', '.join(cl['secciones'])}), en el commit de la fusión")
    elif cl and r["commits"]:
        hecho += (f"\n  sin entrada del CHANGELOG: la rama no trae fragmento en {cl['carpeta']}/ (si hace falta, "
                  f"escríbela tú en {cl['archivo']})")
    if o.seguir:
        if r["commits"]:
            _avisar(ctx, est, hijo.nombre, f"tu rama {r['rama']} se fusionó en {r['base']} hasta aquí ({r['commit']}); sigue en ella")
        return _comun.escribir_json(salida) if o.json else (print(hecho) or 0)
    if not o.json:
        print(hecho)
    if _cerrar(ctx, tel, hijo, aparte=o.json) != 0:
        return _comun.queja(f"fusionado, pero no pude cerrar «{hijo.nombre}»: su worktree queda ({lugar['ruta']})")
    est.archivar(hijo.nombre)
    salida["cerrado"] = True
    try:
        borrado = mod_ramas.borrar(lugar)
    except mod_ramas.ErrorDeRama as e:
        return _queja_rama(mod_ramas.ErrorDeRama(f"fusionado y archivado, pero no pude borrar su worktree: {e}", e.archivos))
    est.olvidar_rama(hijo.nombre)
    salida["borrado"] = True
    if o.json:
        return _comun.escribir_json(salida)
    print(f"archivado «{hijo.nombre}»; {borrado}")
    return 0


def _descartar(ctx, tel, hijo, o) -> int:
    """`telar hilo descartar «Mobile»`: cerrar ese hijo y borrar su worktree y su rama, sin fusionar."""
    from telar import ramas as mod_ramas

    est = tel.estado
    lugar = est.ramas().get(hijo.nombre)
    if not lugar:
        return _comun.queja(f"«{hijo.nombre}» no trabaja en una rama propia: no hay nada que descartar")
    if not o.forzar:
        # antes de cerrar nada: si se va a negar, que el hijo siga como estaba
        try:
            mod_ramas.comprobar_borrar(lugar)
        except mod_ramas.ErrorDeRama as e:
            return _queja_rama(e)
    if _cerrar(ctx, tel, hijo, aparte=o.json) != 0:
        return _comun.queja(f"no pude cerrar «{hijo.nombre}»: su worktree queda ({lugar['ruta']})")
    est.archivar(hijo.nombre)
    try:
        borrado = mod_ramas.borrar(lugar, forzar=o.forzar)
    except mod_ramas.ErrorDeRama as e:
        return _queja_rama(e)
    est.olvidar_rama(hijo.nombre)
    if o.json:
        return _comun.escribir_json({"hilo": hijo.nombre, "rama": lugar["rama"], "cerrado": True, "borrado": True})
    print(f"archivado «{hijo.nombre}»; {borrado}")
    return 0


def _avisar(ctx, est, hilo: str, que: str) -> None:
    """Un aviso (no lo despierta) a `hilo`, de parte de su padre, si hay bus; si falla, nada: es un extra."""
    from telar import bus as mod_bus

    if not mod_bus.hay_bus(ctx.config):
        return
    try:
        from telar.ordenes import mensaje

        mensaje.enviar(ctx, hilo, que, modo="aviso", de=padre_de(est, hilo) or "telar")
    except Exception:  # noqa: BLE001 - avisar es un extra: la fusión ya está hecha
        pass


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
    elif o.verbo == "padre" and "padre" in publica:
        est.adelantar_ajeno(nombre, padre="" if o.valor.strip() in ("ninguno", "ninguna") else o.valor.strip())
    elif o.verbo == "etiquetas" and "etiquetas" in publica:
        try:
            from telar.modelo import normalizar_etiquetas

            est.adelantar_ajeno(nombre, etiquetas=list(normalizar_etiquetas(o.valor)))
        except ValueError:
            pass
    elif o.verbo in ("publicar", "privar") and "publico" in publica:
        est.adelantar_ajeno(nombre, publico=o.verbo == "publicar")
    elif o.verbo in ("vincular", "desvincular") and "vinculo" in publica:
        relativa = _ruta_en_raiz(o.valor or ".", raiz)[0] if o.verbo == "vincular" else ""
        if relativa is not None:
            est.adelantar_ajeno(nombre, vinculo=relativa)


def _al_dueno(ctx, dueno: str, o, nombre: str) -> str:
    """Pide el verbo a la máquina dueña del hilo y muestra lo que dijo. "" si salió bien; si no, el problema."""
    from telar import bus as mod_bus

    argv = [o.verbo, *([o.valor] if o.valor else []), "--hilo", nombre, *(["--cerrar"] if o.cerrar else []),
            *(["--texto", o.texto] if o.verbo == "despertar" and getattr(o, "texto", "") else [])]
    r = mod_bus.pedir(ctx.config, dueno, "hilo", {"argv": argv}, espera=60)
    if not r.get("ok"):
        return f"«{nombre}» vive en {dueno}, y no respondió: {r.get('error', '')}"
    if r.get("salida", "").strip() and not o.json:
        print(_comun.tenue(f"  en {dueno}: " + r["salida"].strip().splitlines()[0]))
    if int(r.get("codigo", 1)) != 0:
        ultima = (r.get("error_salida", "").strip().splitlines() or ["falló"])[-1].removeprefix("telar: ")
        return f"en {dueno}: {ultima}"
    return ""


def _cerrar(ctx, tel: _comun.Telar, hilo, aparte: bool = False) -> int:
    """Cierra la ventana del hilo (y la de la otra máquina, si es remoto). Con `aparte` (lo pide una orden con
    --json) lo que va contando sale por stderr: en stdout va solo el JSON, que así se lee limpio."""
    # un hilo remoto tiene además su ventana en la otra máquina, que sigue viva aunque la
    # ventana local ya no esté: se cierra igual, o el agente quedaría corriendo allá
    _matar_remoto(ctx, tel, hilo, aparte=aparte)
    flujo = sys.stderr if aparte else sys.stdout
    if tel.mux is None or not tel.vivo(hilo):
        print(_comun.tenue("  no está vivo: no hay nada que cerrar"), file=flujo)
        return 0
    try:
        tel.mux.cerrar(hilo.id)
    except ErrorDeMux as e:
        return _comun.queja(f"no pude cerrarlo: {e}")
    print("  cerrado en el multiplexor", file=flujo)
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


#: la marca en el entorno de la mudanza que sigue aparte (`_seguir_aparte`): ya no corre en la ventana que cierra
APARTE = "TELAR_LLEVAR_APARTE"


def _dentro_de(ctx, tel: _comun.Telar, hilo) -> bool:
    """Si este proceso corre en la ventana del hilo: el agente del hilo pidió llevarse a sí mismo. Cerrar esa ventana
    al final de la mudanza lo terminaría a la mitad, así que la mudanza sigue aparte (`_seguir_aparte`)."""
    if os.environ.get(APARTE) or tel.mux is None or not tel.vivo(hilo):
        return False
    panel = panel_del_entorno(ctx.config.multiplexor)
    if panel:
        try:
            return any(str(getattr(p, "id", "")) == panel for p in tel.mux.panes(hilo.id))
        except Exception:  # noqa: BLE001 - sin poder preguntarle al multiplexor, lo que exportó al abrirlo
            pass
    return os.environ.get("TELAR_HILO", "").strip() == hilo.nombre


def _seguir_aparte(ctx, hilo, maquina: str, sesion: str, subir: bool = False) -> int:
    """La mudanza de un hilo pedida desde su propia ventana, en un proceso aparte (su propia sesión, fuera del árbol
    del agente): espera a que el agente termine su turno, la copia, la abre allá y recién entonces cierra la ventana.
    Lo que ya se decidió aquí (las preguntas, `--si`) no se vuelve a preguntar. Su salida, en
    `<estado>/llevar/<hilo>.log`; su avance, en el progreso de la mudanza; si falla, el hilo sigue aquí y su agente
    recibe un mensaje que dice por qué."""
    import subprocess

    from telar import mudanza

    registro = mudanza.ruta_progreso(ctx.config, hilo.nombre).with_suffix(".log")
    # lo decidido, tal cual: subir lo suyo antes, o llevarlo igual
    argv = [sys.executable, "-m", "telar", "hilo", "llevar", maquina, "--hilo", hilo.nombre,
            "--subir" if subir else "--si", *(["--sesion", sesion] if sesion else [])]
    try:
        with registro.open("w", encoding="utf-8") as salida:
            subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=salida, stderr=subprocess.STDOUT,
                             start_new_session=True, env={**os.environ, APARTE: "1"})
    except OSError as e:
        return _comun.queja(f"no pude seguir la mudanza aparte: {e}. No se movió nada")
    print(f"«{hilo.nombre}» se va a {maquina} apenas termine este turno: la mudanza sigue aparte, porque corre en la"
          " ventana que va a cerrar.")
    print(_comun.tenue("  termina el turno sin más herramientas: tu conversación se copia cuando terminas, allá se abre"
                       " retomándola y recién entonces se cierra esta ventana. Si algo falla, sigues aquí y te llega"
                       f" un mensaje con el porqué. Su avance: {registro}"))
    return 0


def _avisar_al_hilo(ctx, hilo: str, texto: str) -> None:
    """Lo que tiene que saber el agente de un hilo de su propia mudanza (que falló, y que sigue aquí): un mensaje en
    su casilla. Solo cuando la mudanza siguió aparte: si no, quien la pidió ya lo leyó en su salida."""
    if not os.environ.get(APARTE):
        return
    try:
        from telar import bus as mod_bus
        from telar import casilla

        casilla.dejar(ctx.config, hilo, mod_bus.mensaje(f"telar hilo llevar no te llevó: {texto}", de="telar", para=hilo))
    except Exception:  # noqa: BLE001 - el progreso y el registro lo dicen igual
        pass


def _llevar(ctx, tel: _comun.Telar, hilo, valor: str, si: bool, sesion: str = "", *, subir: bool = False) -> int:
    """Pasar la conversación de un hilo local a otra máquina, y seguirla allá.

    La conversación viaja; los archivos no. Lo que el hilo tiene sin subir en sus repositorios (telar.sin_subir: lo
    sin commitear que escribió su conversación, lo de su carpeta, los commits sin subir) se muestra antes, y se elige:
    `subir` lo commitea (solo lo suyo) y lo sube antes de copiar, `si` lo lleva igual. Allá, el repositorio se pone al
    día antes de abrir. Un hijo con rama no se muda. Aquí no se cierra ni se archiva nada hasta que allá confirma que
    lo abrió: si la copia no llega o allá no abre, aquí sigue como estaba. Cerrar la ventana de aquí es lo último (la
    misma conversación viva en dos máquinas se bifurca); si este proceso corre en esa ventana (el agente del hilo pidió
    llevarse a sí mismo), la mudanza sigue aparte (`_seguir_aparte`).
    """
    from telar import agente as mod_agente

    if hilo.remoto:
        return _comun.queja(f"«{hilo.nombre}» ya vive en otra máquina ({hilo.remoto})")
    from telar import mudanza

    remotos = ctx.config.remotos
    remoto = next((r for r in remotos if r.nombre == valor), None) if valor else (remotos[0] if len(remotos) == 1 else None)
    # una máquina del bus (otra tuya, como tu lugar en un servidor): la conversación va por el bus (telar.mudanza). Una
    # de [remotos] que también está en el bus, igual: por ssh ya no se mudan hilos si hay bus (sin él no hay dueño que
    # compartir, y queda el camino de antes)
    del_bus = mudanza.maquinas_del_bus(ctx.config)
    if remoto is not None and remoto.nombre in _conocidas_del_bus(ctx.config):
        valor, remoto = remoto.nombre, None
    if remoto is None and valor not in del_bus:
        fuera = _fuera_de_linea(ctx, valor) if valor else ""
        if fuera:
            return _comun.queja(f"{fuera}: no tiene dónde recibirlo. No se movió nada")
        nombres = ", ".join([*(r.nombre for r in remotos), *del_bus]) or "ninguna: ni en [remotos] ni en el bus"
        return _comun.queja(f"¿a qué máquina? telar hilo llevar <máquina> ({nombres})")
    # un hijo con rama no se muda: su rama y su worktree existen solo aquí, y allá se abriría en la carpeta principal
    lugar = tel.estado.ramas().get(hilo.nombre)
    if lugar:
        return _comun.queja(f"«{hilo.nombre}» es un hijo con rama: su rama ({lugar.get('rama') or '?'}) y su worktree "
                            f"({lugar.get('ruta') or lugar.get('carpeta') or '?'}) existen solo aquí, y allá trabajaría "
                            "en la carpeta principal. Fusiónalo o descártalo antes (telar hilo fusionar / descartar). "
                            "No se movió nada")
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
        # y allá se abre con una nueva (lo que pasó con un hilo «prueba» recién abierto)
        print(_comun.tenue("  su conversación está vacía (sin mensajes): allá se abre con una nueva"))

    relativa = tel.estado.vinculos().get(hilo.nombre, "")
    aparte = _dentro_de(ctx, tel, hilo)
    if remoto is None:
        return _llevar_por_el_bus(ctx, tel, hilo, valor, sid, archivo, relativa, si=si, aparte=aparte, sesion=sesion,
                                  subir=subir)

    # sin bus (la otra máquina no está en él): por ssh, como antes de que hubiera un dueño por hilo. Los pasos, para la
    # página (telar.mudanza.progreso), como por el bus
    mudanza.progreso(ctx.config, hilo.nombre, "revisar", maquina=remoto.nombre,
                     bytes=Path(archivo).stat().st_size if archivo is not None else 0, error="", avisos=[])

    def falla(texto: str) -> int:
        mudanza.progreso(ctx.config, hilo.nombre, "falla", error=texto)
        _avisar_al_hilo(ctx, hilo.nombre, texto)
        return _comun.queja(texto)

    carpeta = mod_remoto.carpeta_remota(ctx.config, remoto, relativa)
    pendiente, avisos = _lo_de_aqui(ctx, tel, hilo, relativa, archivo, sid)
    if relativa.startswith("/"):
        # vinculado fuera de la raíz: allá no hay traducción de esa carpeta. Si no existe en
        # la misma ruta del hogar, el agente de allá sigue la conversación sin sus archivos.
        faltante = _falta_alla(remoto, relativa)
        if faltante:
            avisos.append(f"su carpeta, {faltante}, no existe en {remoto.destino}: el agente de allá recordará la "
                          "conversación pero no tendrá esos archivos (clónalos allá primero)")
    codigo, subir = _antes_de_llevar(ctx, hilo, remoto.nombre, pendiente, avisos, [], si, subir)
    if codigo is not None:
        return codigo
    if aparte:
        return _seguir_aparte(ctx, hilo, remoto.nombre, sesion, subir)
    estaba_vivo = tel.mux is not None and tel.vivo(hilo)
    problema = _esperar_su_turno(ctx, hilo, archivo, estaba_vivo)
    if problema:
        return falla(problema)
    if subir:
        problema, pendiente = _subir_lo_suyo(ctx, tel, hilo, remoto.nombre, relativa, archivo, sid)
        if problema:
            return falla(problema)
    pesa = Path(archivo).stat().st_size if archivo is not None else 0
    # 1. llevar la conversación (si tiene: una vacía no se copia, y allá se abre una nueva). Aquí no se toca nada
    mudanza.progreso(ctx.config, hilo.nombre, "copiar", bytes=pesa)
    destino, problema = mod_remoto.copiar_conversacion(remoto, archivo, sid, carpeta) if archivo is not None else ("", "")
    if problema:
        return falla(f"no se llevó la conversación: {problema}. Aquí sigue como estaba.")
    # 2. abrirla allá, retomándola (con su ventana aquí, que la mira); aquí sigue abierta hasta que allá esté
    mudanza.progreso(ctx.config, hilo.nombre, "abrir")
    try:
        mod_remoto.abrir(ctx, tel, hilo.nombre, remoto, relativa=relativa, conversacion=sid if archivo is not None else "")
    except (ErrorDeMux, ErrorDeAgente) as e:
        return falla(f"la conversación ya está en {remoto.destino} ({destino}), pero no pude abrir el hilo allá: {e}."
                     " Aquí sigue como estaba.")
    # 3. allá ya está: lo de aquí se cierra, lo último (si este proceso vive en esa ventana, cerrarla lo termina)
    mudanza.progreso(ctx.config, hilo.nombre, "cerrar")
    tel.estado.desarchivar(hilo.nombre)
    _desarchivar_alla(ctx, remoto.nombre, hilo.nombre)
    from telar import directorio as mod_directorio

    mod_directorio.publicar_callado(ctx, tel, remoto.nombre)
    mudanza.progreso(ctx.config, hilo.nombre, "listo", carpeta=str(carpeta))
    if archivo is None:
        print(f"«{hilo.nombre}» sigue en {remoto.destino}, con una conversación nueva")
    else:
        print(f"«{hilo.nombre}» sigue en {remoto.destino}, retomando la conversación {sid[:8]}")
        print(_comun.tenue(f"  allá: {destino}; aquí queda la copia de como estaba al irse"), flush=True)
    return _cerrar_lo_de_aqui(ctx, tel, hilo, remoto.nombre, archivo, pesa, estaba_vivo)


def _conocidas_del_bus(config) -> set[str]:
    """Las máquinas que el bus conoce (las que publicaron su foto alguna vez, en línea o no): a una de [remotos] que está
    ahí se la lleva por el bus aunque haya ssh, y si no contesta, no se lleva (allá nadie lo tomaría)."""
    from telar import bus as mod_bus
    from telar import espejo

    if not mod_bus.hay_bus(config):
        return set()
    try:
        return {e["nombre"] for e in espejo.leer_todos(config) if e.get("nombre")}
    except Exception:  # noqa: BLE001
        return set()


def _carpeta_del_hilo(ctx, relativa: str) -> Path | None:
    """La carpeta de un hilo, de su vínculo (relativo a la raíz, o absoluto); None si no tiene."""
    if not relativa:
        return None
    return Path(relativa).expanduser() if relativa.startswith(("/", "~")) else Path(ctx.config.raiz).expanduser() / relativa


def _lo_de_aqui(ctx, tel: _comun.Telar, hilo, relativa: str, archivo, sid: str) -> tuple[dict, list[str]]:
    """Antes de llevarlo: lo que tiene sin subir en sus repositorios (telar.sin_subir) y lo que quedaría atrás (sus
    hijos con rama, que no se mudan: se lleva solo al padre)."""
    from telar import sin_subir

    pendiente = sin_subir.revisar(ctx.config, _carpeta_del_hilo(ctx, relativa), archivo, sid)
    ramas = tel.estado.ramas()
    hijos = [h for h in tel.estado.hijos(hilo.nombre) if h in ramas]
    avisos = ([f"sus hijos con rama ({', '.join(hijos)}) se quedan aquí, con su rama y su worktree: se lleva solo a "
               f"«{hilo.nombre}», y fusionarlos se hace desde aquí"] if hijos else [])
    return pendiente, avisos


def _repos_para(pendiente: dict) -> list[dict]:
    """Lo que la otra máquina necesita de cada repositorio del hilo para ver si va atrás: dónde está bajo la raíz y
    el último commit de aquí (el de ahora: después de subir es otro)."""
    from telar import git

    salida = []
    for r in pendiente.get("repos") or []:
        if not r.get("relativa"):
            continue
        commit = git._git(Path(r["repo"]), "rev-parse", "HEAD").stdout.strip() or r.get("commit", "")
        salida.append({"relativa": r["relativa"], "commit": commit, "nombre": r["nombre"]})
    return salida


def _revisar_alla(ctx, maquina: str, hilo, sid: str, relativa: str, pendiente: dict) -> dict:
    """Le pregunta a la otra máquina, sin mover nada (`hilo-revisar`), si puede recibirlo y si tiene el último commit
    de cada repositorio del hilo. {} si no contesta (un telar de antes: se sigue como antes)."""
    from telar import bus as mod_bus
    from telar import mudanza

    pedido = {"hilo": hilo.nombre, "sesion": sid, "relativa": relativa, "repos": _repos_para(pendiente)}
    r = mod_bus.pedir(ctx.config, maquina, mudanza.VERBO_REVISAR, pedido, espera=15)
    return r if r.get("ok") else {}


def _antes_de_llevar(ctx, hilo, maquina: str, pendiente: dict, avisos: list[str], destino: list, si: bool,
                     subir: bool) -> tuple[int | None, bool]:
    """Lo que hay que ver antes de llevarlo: lo sin subir (telar.sin_subir) y lo que llegaría a medias (`avisos`).
    Queda en el progreso de la mudanza (`pendiente`, `destino`, `avisos`) para que la página lo muestre entero. Si no
    hay nada, ni se pregunta. Si hay, `subir` o `si` ya lo deciden; si no, en una terminal se pregunta, y si no, falla
    diciendo qué elegir. (None si se sigue, o el código de salida; si se sube)."""
    from telar import mudanza, sin_subir

    mudanza.progreso(ctx.config, hilo.nombre, "revisar", avisos=avisos, pendiente=pendiente, destino=destino)
    lineas = sin_subir.lineas(pendiente, destino, maquina)
    if not sin_subir.hay_algo(pendiente) and not avisos:
        for x in lineas:  # allá va atrás: al llegar se pone al día, no hay nada que elegir
            print(_comun.tenue(f"  {x.removeprefix('· ')}"))
        return None, False
    puede = sin_subir.hay_algo(pendiente) and sin_subir.se_puede_subir(pendiente)
    if subir and not puede:
        print(_comun.tenue("  no hay nada suyo que se pueda subir: se lleva igual"))
        subir = False
    if si or subir or os.environ.get(APARTE):
        return None, subir
    print(f"antes de llevar «{hilo.nombre}» a {maquina}:")
    for x in [*lineas, *(f"· {a}" for a in avisos)]:
        print(f"  {x}")
    sys.stdout.flush()  # antes de la queja, que va por stderr: en el registro de la página, en su orden
    if not sys.stdin.isatty():
        if puede:
            return _comun.queja("hay trabajo sin subir: --subir para subir lo suyo y llevarla, --si para llevarla "
                                "igual"), False
        if sin_subir.hay_algo(pendiente):
            return _comun.queja("hay trabajo sin subir que no se puede subir desde aquí (no sé si es suyo, o su rama no "
                                "tiene una de arriba): --si para llevarla igual"), False
        return _comun.queja(f"en {maquina} llegaría a medias: --si para llevarla igual"), False
    pregunta = "¿[s]ubir lo suyo y llevarla, llevarla [i]gual o [n]o? " if puede else "¿llevarla [i]gual o [n]o? "
    r = input(pregunta).strip().lower()
    if puede and r in ("s", "si", "sí", "subir"):
        return None, True
    if r in ("i", "igual", "y", "yes") or (not puede and r in ("s", "si", "sí")):
        return None, False
    print("no se movió nada")
    return 1, False


def _subir_lo_suyo(ctx, tel: _comun.Telar, hilo, maquina: str, relativa: str, archivo, sid: str) -> tuple[str, dict]:
    """«Subir y llevar», después de su turno (lo que escribió al final también es suyo): commitea solo lo del hilo en
    cada repositorio y sube (telar.sin_subir.subir). ("", lo que hay ahora) si subió; si no, por qué, y no se lleva."""
    from telar import mudanza, sin_subir

    mudanza.progreso(ctx.config, hilo.nombre, "subir")
    pendiente, _ = _lo_de_aqui(ctx, tel, hilo, relativa, archivo, sid)
    ok, texto = sin_subir.subir(ctx.config, pendiente, hilo.nombre, maquina)
    if not ok:
        return f"no pude subir lo suyo: {texto}. No se movió nada", pendiente
    if texto:
        print(_comun.tenue(f"  subido: {texto}"), flush=True)
        mudanza.progreso(ctx.config, hilo.nombre, "subir", subido=texto)
    return "", pendiente


def _esperar_su_turno(ctx, hilo, archivo, vivo: bool) -> str:
    """Antes de copiar: que el agente del hilo termine su turno (telar.mudanza.esperar_turno), venga de donde venga la
    orden. Mientras espera, el progreso de la mudanza lo dice (`esperar`). Un hilo sin ventana no tiene agente que
    esperar. "" si se puede copiar; si no, por qué."""
    from telar import mudanza

    if not vivo:
        return ""

    def avisar() -> None:
        mudanza.progreso(ctx.config, hilo.nombre, "esperar")
        print(_comun.tenue(f"  esperando que «{hilo.nombre}» termine su turno…"), flush=True)

    return mudanza.esperar_turno(ctx.config, hilo.nombre, Path(archivo) if archivo is not None else None,
                                 al_esperar=avisar)


def _lo_copiado(r: dict) -> str:
    """Lo que viajó de una conversación copiada de a pedazos (telar.replica.mandar), en una línea."""
    from telar import replica

    total, mandados = int(r.get("bytes") or 0), int(r.get("mandados") or 0)
    if mandados >= total:
        return f"copiada entera: {replica.mb(total)}" + (f", {replica.mb(r['red'])} por la red" if r.get("red") else "")
    return (f"copiados {replica.mb(mandados)} de {replica.mb(total)}: lo demás ya estaba allá"
            + (f" ({r.get('archivos')} archivos con su carpeta)" if int(r.get("archivos") or 1) > 1 else ""))


def _desarchivar_alla(ctx, maquina: str, hilo: str) -> None:
    """Un hilo que vuelve por ssh a la máquina de donde se fue quedó archivado allá (al irse, por el bus): ahora vive
    allá, y su dueño es quien dice si está archivado (lo publica, y aquí se lee de eso). Se le pide desarchivarlo, si
    está en el bus; si no contesta, se dice y sigue."""
    from telar import bus as mod_bus

    if not mod_bus.hay_bus(ctx.config):
        return
    o = SimpleNamespace(verbo="desarchivar", valor="", cerrar=False, json=True)
    problema = _al_dueno(ctx, maquina, o, hilo)
    if problema:
        print(_comun.tenue(f"  allá puede seguir figurando archivado: {problema}"))


def _fuera_de_linea(ctx, maquina: str) -> str:
    """«laptop fuera de línea desde 14:02» si se sabe que esa máquina del bus no contesta; "" si contesta o no se
    sabe (telar.alcance)."""
    try:
        from telar import alcance

        a = alcance.de(ctx.config, maquina)
    except Exception:  # noqa: BLE001
        return ""
    return a.frase() if a.fuera else ""


def _cerrar_lo_de_aqui(ctx, tel: _comun.Telar, hilo, maquina: str, archivo, mandados: int, estaba_vivo: bool) -> int:
    """El último paso de una mudanza por ssh que ya llegó: cerrar la ventana de aquí (la que corría el agente; la que
    mira el hilo allá, si la hay, queda)."""
    from telar import mudanza

    if estaba_vivo and tel.mux is not None:
        try:
            tel.mux.cerrar(hilo.id)
        except ErrorDeMux as e:
            texto = (f"«{hilo.nombre}» ya está abierto en {maquina}, pero aquí no pude cerrarlo: {e}. Ciérralo aquí a"
                     " mano (telar hilo cerrar): la misma conversación viva en dos máquinas se bifurca")
            mudanza.progreso(ctx.config, hilo.nombre, "listo", aviso=texto)
            return _comun.queja(texto)
    return 0


def _llevar_por_el_bus(ctx, tel: _comun.Telar, hilo, maquina: str, sid: str, archivo, relativa: str, *,
                       si: bool = False, aparte: bool = False, sesion: str = "", subir: bool = False) -> int:
    """Lo de `_llevar` hacia una máquina del bus (telar.mudanza), con un dueño por hilo (telar.dueno).

    Antes de tocar nada, se le pregunta a la de allá si puede recibirlo y si tiene el último commit de sus
    repositorios (`hilo-revisar`): lo grave no se lleva, y lo que llegaría a medias o lo sin subir de aquí se pregunta
    (`_antes_de_llevar`). Después se espera su turno, se sube lo suyo si se eligió, y se **cede**: el registro del bus
    dice que se va a `maquina`, y su agente se detiene (su ventana espera, y no despierta mientras viaja). La
    conversación viaja (la final: ya nadie la escribe), y allá lo **toman** con la época que se cedió y lo abren, con
    sus repositorios al día, su registro y su casilla. Si algo falla antes de que lo tomen, aquí se echa atrás y su
    agente despierta: no se movió nada. Si ya lo tomaron, vive allá. Con la confirmación, su ventana de aquí se cierra;
    no se archiva: aquí se lo ve como de allá. Cada paso queda en el progreso de la mudanza (telar.mudanza.progreso),
    que la página dibuja, y en el registro del bus, que ve cualquier página. `aparte`: corre en la ventana que se
    detendría (el agente pidió llevarse a sí mismo): después de revisar, sigue en un proceso aparte (`_seguir_aparte`)."""
    from telar import bus as mod_bus
    from telar import casilla, dueno, mudanza

    pesa = Path(archivo).stat().st_size if archivo is not None else 0
    mudanza.progreso(ctx.config, hilo.nombre, "revisar", maquina=maquina, bytes=pesa, error="", avisos=[])

    def falla(texto: str) -> int:
        mudanza.progreso(ctx.config, hilo.nombre, "falla", error=texto)
        _avisar_al_hilo(ctx, hilo.nombre, texto)
        return _comun.queja(texto)

    pendiente, avisos = _lo_de_aqui(ctx, tel, hilo, relativa, archivo, sid)
    revision = _revisar_alla(ctx, maquina, hilo, sid if archivo is not None else "", relativa, pendiente)
    if revision.get("graves"):
        return falla(f"en {maquina} no se puede recibir: " + "; ".join(revision["graves"]) + ". No se movió nada.")
    avisos = [*(revision.get("avisos") or []), *avisos]
    codigo, subir = _antes_de_llevar(ctx, hilo, maquina, pendiente, avisos, revision.get("repos") or [], si, subir)
    if codigo is not None:
        return codigo
    if aparte:
        return _seguir_aparte(ctx, hilo, maquina, sesion, subir)
    estaba_vivo = tel.mux is not None and tel.vivo(hilo)
    problema = _esperar_su_turno(ctx, hilo, archivo, estaba_vivo)
    if problema:
        return falla(problema)
    if subir:
        problema, pendiente = _subir_lo_suyo(ctx, tel, hilo, maquina, relativa, archivo, sid)
        if problema:
            return falla(problema)

    # 1. cederlo: el registro dice que se va, y su agente se detiene. Desde aquí su conversación no cambia
    yo, clave = mod_bus.maquina(ctx.config), dueno.clave(ctx.config, hilo.nombre)
    try:
        epoca = dueno.con_almacen(ctx.config, lambda kv: dueno.ceder(kv, clave, hilo=hilo.nombre, yo=yo, a=maquina))
    except dueno.ErrorDeDueno as e:
        return falla(f"{e}. No se movió nada.")
    except Exception as e:  # noqa: BLE001 - sin el registro del bus no se cede
        return falla(f"no pude escribir en el registro del bus ({type(e).__name__}: {e}). No se movió nada.")

    def atras(texto: str) -> int:
        """Algo falló antes de que allá lo tomaran: aquí se echa atrás y su agente despierta. Si allá ya lo tomó,
        vive allá (lo abre su nodo si no alcanzó)."""
        try:
            sigue = dueno.con_almacen(ctx.config, lambda kv: dueno.abortar(kv, clave, yo=yo, epoca_=epoca))
        except Exception as e:  # noqa: BLE001 - sin el registro, el nodo se echa atrás cuando vea que nadie conduce
            return falla(f"{texto}. Y no pude echarme atrás en el registro del bus ({e}): su nodo lo hará")
        if not sigue:
            mudanza.soltar(ctx.config, tel, hilo.nombre)
            mudanza.progreso(ctx.config, hilo.nombre, "listo", aviso=f"{texto}; pero {maquina} ya lo había tomado: "
                             "vive allá (si no alcanzó a abrirlo, lo abre su nodo)")
            print(f"«{hilo.nombre}» vive en {maquina}: {texto}, pero allá ya lo había tomado")
            return 0
        despierto = mudanza.reanudar(ctx.config, hilo.nombre) if estaba_vivo else ""
        return falla(f"{texto}. Aquí sigue como estaba" + (f" ({despierto})" if despierto else "") + ".")

    if estaba_vivo:
        mudanza.progreso(ctx.config, hilo.nombre, "detener")
        problema = mudanza.detener(ctx.config, tel, hilo.nombre, maquina)
        if problema:
            return atras(problema)
    pesa = Path(archivo).stat().st_size if archivo is not None else 0

    # 2. la conversación, allá (solo lo que falta): aquí no se toca nada
    mudanza.progreso(ctx.config, hilo.nombre, "copiar", bytes=pesa)
    _paso_en_el_registro(ctx, clave, yo, "copiar")
    try:
        mandada = mudanza.mandar(ctx, maquina, sid, Path(archivo) if archivo is not None else None, relativa,
                                 hilo=hilo.nombre)
    except mudanza.ErrorDeMudanza as e:
        return atras(str(e))
    if mandada.get("replica"):
        print(_comun.tenue(f"  {_lo_copiado(mandada)}"), flush=True)
    # 3. que allá lo tome con esta época y lo abra retomándola, con sus repositorios al día, su registro y lo que esperaba
    # en su casilla
    mudanza.progreso(ctx.config, hilo.nombre, "abrir")
    _paso_en_el_registro(ctx, clave, yo, "abrir")
    mensajes, quedan = mudanza.casilla_de(ctx.config, hilo.nombre)
    extra = {"repos": _repos_para(pendiente), "registro": mudanza.registro_de(tel.estado, hilo.nombre),
             "casilla": mensajes, "dueno": {"clave": clave, "de": yo, "epoca": epoca}}
    try:
        r = mudanza.abrir_alla(ctx, hilo.nombre, maquina, sid if archivo is not None else "", mandada, relativa,
                               extra=extra)
    except mudanza.ErrorDeMudanza as e:
        return atras(str(e))
    # lo de su casilla ya está allá (si allá lo tomó sin contestar, lo de aquí se queda: no se pierde)
    if "casilla" in r:
        casilla.sacar(ctx.config, hilo.nombre, [m.get("id") for m in mensajes])
    # sus borradores también (telar.borradores): allá dijo que los tiene; un telar de allá más viejo no lo dice, y aquí se
    # quedan, para no perder lo que escribió la persona
    if "borradores" in r:
        tel.estado.poner_borradores(hilo.nombre, [])
    # 4. vive allá: su ventana de aquí, la que esperaba, se cierra. No se archiva: aquí se lo ve como de allá
    mudanza.progreso(ctx.config, hilo.nombre, "cerrar")
    mudanza.soltar(ctx.config, tel, hilo.nombre)
    aviso = "; ".join(x for x in (mandada.get("aviso", ""), r.get("aviso", ""),
                                  f"{quedan} mensajes de su casilla quedaron aquí: no cupieron" if quedan else "") if x)
    mudanza.progreso(ctx.config, hilo.nombre, "listo", carpeta=r.get("carpeta", ""), aviso=aviso)
    print(f"«{hilo.nombre}» sigue en {maquina}, " + (f"retomando la conversación {sid[:8]}" if archivo is not None
                                                       else "con una conversación nueva"))
    if aviso:
        print(_comun.tenue(f"  {aviso}"))
    print(_comun.tenue(f"  allá: {r.get('carpeta') or '?'}; aquí queda su copia, y el hilo se ve como de {maquina}"),
          flush=True)
    return 0


def _paso_en_el_registro(ctx, clave: str, yo: str, paso: str) -> None:
    """En qué va el traspaso, en el registro del bus (lo ve cualquier página). Si no se pudo, no detiene nada."""
    from telar import dueno

    try:
        dueno.con_almacen(ctx.config, lambda kv: dueno.paso(kv, clave, yo=yo, paso_=paso))
    except Exception:  # noqa: BLE001
        pass


def _matar_remoto(ctx, tel: _comun.Telar, hilo, aparte: bool = False) -> None:
    anotado = tel.estado.remotos().get(hilo.nombre)
    remoto = _remoto_de(ctx, anotado["remoto"]) if anotado else None
    if remoto is None or not anotado.get("sesion"):
        return
    problema = mod_remoto.matar(remoto, anotado["sesion"])
    flujo = sys.stderr if aparte else sys.stdout
    if problema:
        print(_comun.tenue(f"  su ventana en {remoto.destino} no se pudo cerrar: {problema}"), file=flujo)
    else:
        print(_comun.tenue(f"  cerrada su ventana en {remoto.destino}"), file=flujo)


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


def _borradores(ctx, o) -> int:
    """Los borradores de un hilo: verlos, agregar uno, mandarlo o borrarlo (telar.servicios.borradores)."""
    from telar import borradores as mod
    from telar.servicios import ErrorDeServicio
    from telar.servicios import borradores

    nombre = o.hilo or o.valor or os.environ.get(_comun.VARIABLE_HILO, "").strip()
    if not nombre:
        return _comun.queja("¿de qué hilo? «telar hilo borradores Faro», --hilo, o desde adentro de uno")
    if o.soltar:
        # lo lanza el fin de un turno (telar.borradores.al_terminar), sin nadie mirando: callado y siempre 0
        try:
            mod.soltar(ctx.config, _comun.tejer(ctx, con_ficha=False), nombre)
        except Exception:  # noqa: BLE001 - el nodo lo intenta de nuevo en su vuelta
            pass
        return 0
    try:
        if o.agregar is not None:
            texto = sys.stdin.read() if o.agregar == "-" else o.agregar
            b = borradores.guardar(ctx, nombre, texto.rstrip("\n"), maquina=o.maquina)
            if o.json:
                return _comun.escribir_json(b.model_dump(mode="json"))
            print(f"«{nombre}»: guardado ({b.id})")
            return 0
        if o.mandar or o.borrar:
            id = _id_de_borrador(borradores.de_hilo(ctx, nombre, maquina=o.maquina), o.mandar or o.borrar)
            if o.borrar:
                b = borradores.borrar(ctx, nombre, id, maquina=o.maquina)
                if o.json:
                    return _comun.escribir_json(b.model_dump(mode="json"))
                print(f"«{nombre}»: borrado ({b.id})")
                return 0
            r = borradores.mandar(ctx, nombre, id, enviar=o.enviar, esperar=o.esperar, maquina=o.maquina)
            if o.json:
                return _comun.escribir_json(r.model_dump(mode="json"))
            print(f"«{nombre}»: " + {"escrito": "quedó escrito en su entrada, sin ⏎", "enviado": "enviado",
                                     "en espera": "sale cuando su agente termine el turno"}.get(r.como, r.como))
            return 0
        datos = borradores.de_hilo(ctx, nombre, maquina=o.maquina)
    except ErrorDeServicio as e:
        if o.json:
            _comun.escribir_json({"error": str(e), "codigo": e.codigo, **e.datos})
            return 1
        return _comun.queja(str(e) + ("; con --esperar, sale cuando termine" if e.datos.get("ocupado") else ""))
    if o.json:
        return _comun.escribir_json(datos.model_dump(mode="json"))
    print(como_texto_borradores(datos.model_dump(mode="json")))
    return 0


def _id_de_borrador(datos, ref: str) -> str:
    """El id de un borrador por su id o por su número en la lista (desde 1)."""
    from telar.servicios import ErrorDeServicio

    lista = datos.borradores
    if any(b.id == ref for b in lista):
        return ref
    if ref.isdigit() and 1 <= int(ref) <= len(lista):
        return lista[int(ref) - 1].id
    raise ErrorDeServicio(f"«{datos.hilo}» no tiene el borrador «{ref}»: tiene {len(lista)}", 404)


def como_texto_borradores(d: dict) -> str:
    """`telar hilo borradores`, para leerlo en la terminal: uno por línea, con su número, su id y su primera línea."""
    lista = d.get("borradores") or []
    ocupado = {"trabajando": " · su agente está trabajando", "espera": " · su agente te está preguntando algo"}.get(
        d.get("ocupado") or "", "")
    if not lista:
        return f"«{d.get('hilo', '')}»: sin borradores{ocupado}"
    lineas = [f"«{d.get('hilo', '')}»: {len(lista)} borrador{'es' if len(lista) != 1 else ''}{ocupado}"]
    for i, b in enumerate(lista, 1):
        texto = " ".join(str(b.get("texto") or "").split())
        espera = {"escribir": "  (sale al terminar su turno)", "enviar": "  (sale al terminar su turno, con ⏎)"}.get(
            b.get("al_terminar") or "", "")
        lineas.append(f"  {i}  {b.get('id', '')}  {texto[:90] + ('…' if len(texto) > 90 else '') or _comun.tenue('(vacío)')}{espera}")
    return "\n".join(lineas)


def _contexto(ctx, o) -> int:
    """Lo que carga el contexto de un hilo, sin moverle nada (telar.servicios.carga)."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import carga

    referencia = o.hilo or o.valor
    try:
        r = carga.de_hilo(ctx, referencia, maquina=o.maquina)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    datos = r.model_dump(mode="json")
    if o.json:
        return _comun.escribir_json(datos)
    print(como_texto_carga(datos))
    return 0


def _k(t: int) -> str:
    return f"{t / 1000:.1f} k".replace(".", ",") if t >= 1000 else str(t)


def como_texto_carga(d: dict) -> str:
    """El resumen de `telar hilo contexto`, para leerlo en la terminal: el total, desde cuándo, una línea por grupo y
    lo que más pesa de cada uno."""
    desde = d.get("desde") or {}
    cuando = str(desde.get("hora", ""))[:16].replace("T", " ")
    que = {"compactacion": "la compactación", "clear": "el /clear", "retomada": "que se retomó"}.get(desde.get("que", ""), "que empezó")
    total = d.get("total") or 0
    lineas = [f"{d.get('hilo', '')}: {'' if d.get('medido') else '≈ '}{_k(total)} tokens, desde {que} ({cuando} UTC)"
              + (f" · {d['compactaciones']} compactaciones" if d.get("compactaciones") else "")]
    if d.get("al_empezar"):
        lineas.append(f"  al empezar pesaba {_k(d['al_empezar'])}")
    casa, carpeta = d.get("casa") or "", d.get("carpeta") or ""

    def corta(ruta: str) -> str:
        if carpeta and ruta.startswith(carpeta.rstrip("/") + "/"):
            return ruta[len(carpeta.rstrip("/")) + 1:]
        if casa and ruta.startswith(casa.rstrip("/") + "/"):
            return "~/" + ruta[len(casa.rstrip("/")) + 1:]
        return ruta

    for g in d.get("grupos") or []:
        if not g.get("tokens"):
            continue
        pct = round(100 * g["tokens"] / total) if total else 0
        lineas.append(f"\n{g['nombre']:<22} {_k(g['tokens']):>8}  {pct:>3}%  ({g['cuantos']})")
        for it in [x for x in d.get("items") or [] if x.get("grupo") == g["clave"] and x.get("veces")][:8]:
            veces = f" ×{it['veces']}" if it.get("veces", 1) > 1 else ""
            lineas.append(f"  {corta(it.get('nombre', ''))[:70]:<70} {_k(it['tokens']):>8}{veces}")
    lineas.append(_comun.tenue(f"\n(cada cosa, estimada a {str(d.get('caracteres_por_token', '')).replace('.', ',')} caracteres por token;"
                               f" el total, {'medido por el modelo' if d.get('medido') else 'estimado también'})"))
    return "\n".join(lineas)


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


def _dormir(ctx, tel: _comun.Telar, hilo) -> int:
    """`telar hilo dormir`: dormirlo ya, aunque no lleve `dormir_tras` quieto ni importe que se lo mire (lo pide la
    persona); lo demás que lo protege (trabajando, te espera, texto sin enviar, algo en segundo plano) vale igual."""
    from telar import dormir

    if not tel.vivo(hilo):
        return _comun.queja(f"«{hilo.nombre}» no tiene ventana aquí: no hay agente que dormir")
    try:
        print(dormir.dormir_uno(ctx.config, tel, hilo.nombre, forzar=True))
    except RuntimeError as e:
        return _comun.queja(str(e))
    return 0


def _despertar(ctx, tel: _comun.Telar, hilo, o) -> tuple[int, dict]:
    """`telar hilo despertar`: donde viva (telar.alcance.despertar). La máquina: la de `--maquina`, la de su ventana de
    aquí si solo lo mira, o la que dice el bus si aquí no se lo conoce. Devuelve (código, lo que pasó)."""
    from telar import alcance
    from telar import bus as mod_bus

    maquina = o.maquina or _dueno(ctx, hilo)
    if not maquina and mod_bus.hay_bus(ctx.config) and not any(h.nombre == hilo.nombre for h in tel.hilos):
        # un nombre que aquí no está (no tiene ventana ni registro): el de otra máquina, si el bus lo conoce
        alla = mod_bus.maquina_de(ctx.config, hilo.nombre)
        maquina = "" if alla == mod_bus.maquina(ctx.config) else alla
    try:
        r = alcance.despertar(ctx, hilo.nombre, maquina, o.texto, por="telar hilo despertar",
                              por_hilo=os.environ.get("TELAR_HILO", "").strip())
    except RuntimeError as e:
        return _comun.queja(str(e)), {}
    if not o.json:
        print(r.get("hecho") or f"«{hilo.nombre}» no estaba dormido")
        if r.get("en_cola"):
            print(_comun.tenue("  `telar hilos --red` dice lo que espera en cola; al hacerse queda anotado"
                               + (" y te llega un aviso" if os.environ.get("TELAR_HILO") else "")))
        if r.get("aviso"):
            print(_comun.tenue(f"  ({r['aviso']})"))
    return 0, r


def _dormir_seco(ctx, o) -> int:
    """Por qué cada hilo de aquí se dormiría ahora o no (las reglas de telar.dormir, la primera que no se cumple)."""
    from telar import dormir

    tel = _comun.tejer(ctx, con_ficha=False)
    tras = ctx.config.hilos.dormir_tras
    filas = []
    for ob in dormir.observar(ctx.config, tel, completo=True):
        motivo = dormir.por_que_no(ob, tras)
        filas.append({"hilo": ob.nombre, "dormiria": not motivo, "motivo": motivo,
                      "pid": ob.agente.pid if ob.agente else None})
    if o.json:
        return _comun.escribir_json({"dormir_tras": tras, "hilos": filas})
    print(_comun.tenue(f"dormir_tras = {tras / 60:g} min" if tras else "dormir_tras = 0: nunca"))
    for f in filas:
        print(f"{'◌' if f['dormiria'] else '·'} {f['hilo']}: {'se dormiría' if f['dormiria'] else f['motivo']}")
    return 0


def _seguir(ctx, o) -> int:
    """`telar hilo seguir`: seguir aquí un hilo cuya máquina está apagada, desde la copia de aquí (telar.seguir). Sin
    --si, dice de cuándo es la copia y cuánto falta, y no toca nada."""
    from telar import seguir

    nombre = o.hilo or os.environ.get("TELAR_HILO", "").strip()
    if not nombre:
        return _comun.queja("¿cuál? telar hilo seguir «Faro»")
    if not o.si:
        r = seguir.revisar(ctx, nombre)
        if o.json:
            return _comun.escribir_json(r)
        if not r["puede"]:
            return _comun.queja(r["por_que_no"])
        print(r["aviso"])
        print(_comun.tenue(f"  para seguirlo aquí: telar hilo seguir «{nombre}» --si"))
        return 0
    r = seguir.seguir(ctx, nombre)
    if o.json:
        _comun.escribir_json(r)
        return 0 if r.get("ok") else 1
    if not r.get("ok"):
        return _comun.queja(str(r.get("error")))
    print(r["hecho"])
    return 0


def _retomar_alla(ctx, est, hilo, maquina: str, mensaje: str = "") -> int:
    """Retomar un hilo archivado aquí que es de `maquina` (su conversación vive allá): allá, por su nodo, que lo
    desarchiva y lo abre; aquí sale del archivo (es de allá, y se ve en su foto). Con `maquina` apagada no se abre la
    copia de aquí: se dice si se puede seguir aquí (telar.seguir) o que vuelve cuando vuelva."""
    from telar import alcance, seguir
    from telar import bus as mod_bus

    a = alcance.de(ctx.config, maquina)
    if a.fuera:
        r = seguir.revisar(ctx, hilo.nombre, preguntar=False)
        if r.get("aqui"):
            return _comun.queja(f"«{hilo.nombre}» es de {a.frase()}: «telar hilo seguir «{hilo.nombre}»» dice de cuándo "
                                f"es la copia de aquí y cuánto falta, y con --si lo sigue aquí")
        return _comun.queja(f"«{hilo.nombre}» es de {a.frase()}, y aquí no hay copia de su conversación: vuelve cuando "
                            f"vuelva {maquina}")
    argv = ["retomar", "--hilo", hilo.nombre, *(["--texto", mensaje] if mensaje else [])]
    r = mod_bus.pedir(ctx.config, maquina, "hilo", {"argv": argv}, espera=60)
    if not r.get("ok"):
        return _comun.queja(f"«{hilo.nombre}» vive en {maquina}, y no respondió: {r.get('error', '')}")
    if int(r.get("codigo", 1)) != 0:
        ultima = (r.get("error_salida", "").strip().splitlines() or ["falló"])[-1].removeprefix("telar: ")
        return _comun.queja(f"en {maquina}: {ultima}")
    est.desarchivar(hilo.nombre)
    print(f"retomado «{hilo.nombre}» en {maquina}, donde vive su conversación")
    return 0


def _retomar(ctx, tel: _comun.Telar, hilo, mensaje: str = "") -> int:
    """Sacarlo del archivo y reabrirlo tal como estaba: su carpeta, su agente, su conversación.

    Es la otra mitad de archivar con --cerrar. El tab se cerró y la conversación quedó en
    disco con el id que telar le dio al abrirla; retomar la reabre con `--resume` en vez
    de pedirle a nadie que busque el id y lo escriba. Si el hilo sigue vivo, solo se va a él.
    """
    est = tel.estado
    # uno archivado aquí que el bus dice de otra máquina (con su conversación): se retoma allá, no la copia de aquí
    de_otra = getattr(tel, "de_otra", {}).get(hilo.nombre, "")
    if de_otra and hilo.nombre not in tel.vivos:
        return _retomar_alla(ctx, est, hilo, de_otra, mensaje)
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
            # uno que duerme (telar.dormir) se despierta en su ventana, aquí o donde viva
            try:
                from telar import dormir

                despierto = dormir.despertar_hilo(ctx, tel, hilo)
            except RuntimeError as e:
                return _comun.queja(str(e))
            tel.mux.ir(hilo.id)
            print(despierto or f"«{hilo.nombre}» ya estaba abierto")
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
            lanz = lanzar.para_hilo(ctx.config, hilo.nombre, carpeta, mensaje)
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
