"""`telar nodo` — esta máquina en el bus: recibe lo suyo, avisa a sus hilos y publica su estado.

    telar nodo                 correr (lo que levantan launchd o systemd; no termina)
    telar nodo --una-vez       una vuelta y salir (para probar)
    telar nodo estado          el estado de todos los hilos de esta persona, como lo tiene el bus

Cada dos segundos:

1. **Qué hilos viven aquí**: los de la lista con ventana en esta máquina, las sesiones propias (las del
   celular, los periódicos, los agentes de un servidor) y los agentes residentes que viven aquí, aunque
   no estén abiertos.
2. **Sus mensajes**: recoge del bus lo de cada uno, lo deja en su casilla local (telar.casilla) y lo
   confirma. Después avisa: a un hilo inactivo se le teclea «↯ mensaje nuevo» (el gancho le entrega el
   contenido); a uno que trabaja, nada (el gancho Stop se lo entrega al terminar el turno); a un agente
   residente sin sesión, se le abre con ese aviso como primer mensaje.
3. **Su estado**: publica de cada uno la máquina, la atención, desde cuándo, su conversación, su vínculo
   y si está archivado, solo si cambió. Un hilo que falta dos vueltas seguidas se publica muerto, también
   el que murió con el nodo apagado: al arrancar, el nodo parte de lo que el bus da vivo en esta máquina.
   Y escucha el de los demás: lo que publica el dueño de un hilo que vive en otra máquina queda aquí en
   `ajenos.json` (telar.estado, «hilos ajenos»), de donde lo leen la lista y la página, y su atención se
   anota aquí al instante, sin sondeo. Su ventana aquí se trae, se cierra o se reabre según lo que publica;
   reabierta tres veces en cinco minutos sin que allá cambie nada, no se reabre más.

Y lo que oye de las demás: un `telar cambio <tema>` se anota aquí para que el dashboard relea, y si un
`[disparadores.x] al = "cambio:<tema>"` lo espera (en la máquina de los periódicos), se corre con freno
(telar.disparadores). Cada 30 s mira el estado deseado (telar.deseado): avisa, sin arreglar, del residente
que no tiene sesión.

También atiende pedidos con respuesta: `leer` (los últimos turnos de un hilo de aquí) y `ping`.
Necesita `[bus] url` en la configuración y el extra «bus» de telar (nats-py).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time

from telar import bus as mod_bus
from telar import estado as mod_estado
from telar.ordenes import _comun

AYUDA = "Esta máquina en el bus: recibe lo suyo, avisa a sus hilos y publica su estado."

#: cada cuánto se miran los hilos de aquí, las casillas y el estado
VUELTA = 2.0
#: cada cuántas vueltas se publica la foto del espejo (15 × 2 s = 30 s)
ESPEJO_CADA = 15
#: un «trabajando» sin cambios por más de esto se da por pegado y se avisa igual (segundos)
TRABAJANDO_VIEJO = 45 * 60
#: los pedidos con respuesta de un mismo verbo que se atienden a la vez, y cuántos de ese verbo pueden
#: esperar turno: pasado eso se contesta «ocupada» al tiro, en vez de dejar que el que pidió espere hasta
#: agotar su plazo. Cada verbo tiene los suyos: cuatro `telar hilo` lentos no atrasan un `leer`
PEDIDOS_A_LA_VEZ = 4
PEDIDOS_EN_ESPERA = 64
#: cuánto espera cada casilla en una vuelta lo que tenga (segundos). Se piden todas a la vez: la vuelta
#: tarda esto, no esto por hilo. Lo que no alcanza a llegar no se pierde: JetStream lo entrega de nuevo
CASILLA_ESPERA = 1.0
#: los pedidos que solo leen: varios del mismo verbo a la vez. Los demás escriben algo aquí (el registro de un
#: hilo, una tarea, una nota) y se atienden de a uno por verbo, en orden, como antes: dos que leen y reescriben
#: el mismo archivo a la vez podrían perder uno de los cambios
SOLO_LEEN = ("leer", "resultado", "resultado-sin-ver", "proveedor", "notas", "serie", "archivo-leer", "hilo-revisar", "codigos",
             "contexto", "avisos-archivo", "replica-estado", "mudanza-progreso")
#: lo que puede esperar en cada suscripción antes de que nats-py descarte (y avise «slow consumer»): el
#: de fábrica es medio millón de mensajes o 128 MB, que es memoria sin tope si una se queda pegada
PENDIENTES_MSGS = 2_000
PENDIENTES_BYTES = 32 * 1024 * 1024
#: cuánto espera el nodo cada pedido a JetStream (poner el estado, abrir una casilla). El de nats-py es 5 s,
#: corto para el laptop por un hotspot: cada vuelta que se pasaba quedaba en el registro como `nats: timeout`
ESPERA_JS = 10
#: lo que se guarda en `ajenos.json` de cada hilo de otra máquina: lo que se lee de él aquí (telar.estado,
#: «hilos ajenos»). Lo demás —su ventana, su atención, cuándo se publicó— lo usa el nodo de lo que tiene
#: en memoria, y guardarlo reescribiría el archivo con cada cambio de atención
CAMPOS_AJENOS = ("maquina", "conversacion", "vinculo", "archivado", "publico", "etiquetas", "padre", "ficha", "dueno", "borradores",
                 "cede", "mudanza")
#: la ventana aquí de un hilo de otra máquina que se reabrió REABRIR_TOPE veces en REABRIR_EN segundos y se
#: volvió a cerrar no se reabre más, hasta que cambie su dirección o el hilo publique otra cosa: allá no
#: contesta, aunque el bus lo siga dando por vivo (ver `Nodo.puede_reabrir`)
REABRIR_TOPE = 3
REABRIR_EN = 5 * 60


def registro_de(nombre: str, vinculos, archivados, publicos=(), etiquetas=None, padres=None) -> dict:
    """Lo que el dueño de un hilo publica de su registro: su vínculo (relativo a la raíz, "" si no
    tiene), si está archivado, si es público y sus etiquetas."""
    return {"vinculo": vinculos.get(nombre, ""), "archivado": nombre in archivados, "publico": nombre in publicos,
            "etiquetas": list((etiquetas or {}).get(nombre, ())), "padre": (padres or {}).get(nombre, "")}


def _en_hilo_suelto(funcion, *args, nombre: str = "") -> asyncio.Future:
    """`funcion(*args)` en un hilo daemon, como un futuro del loop: lo que `run_in_executor`, pero sin un hilo que
    Python espere al salir. Si el loop ya cerró cuando termina, el resultado se pierde: nadie lo esperaba."""
    import threading

    loop = asyncio.get_running_loop()
    futuro = loop.create_future()

    def fijar(resultado=None, error=None):
        if futuro.done():
            return
        if error is not None:
            futuro.set_exception(error)
        else:
            futuro.set_result(resultado)

    def correr():
        try:
            r, e = funcion(*args), None
        except Exception as x:  # noqa: BLE001 - vuelve al que espera, que decide
            r, e = None, x
        with contextlib.suppress(RuntimeError):  # el loop ya cerró
            loop.call_soon_threadsafe(fijar, r, e)

    threading.Thread(target=correr, name=nombre or None, daemon=True).start()
    return futuro


def _vive(pid) -> bool:
    """Si el proceso `pid` (de esta máquina) sigue corriendo."""
    try:
        os.kill(int(pid), 0)
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return True


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("nodo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", default="", choices=("", "estado"))
    p.add_argument("--una-vez", dest="una_vez", action="store_true", help="una vuelta y salir")
    p.add_argument("--json", action="store_true", help="con estado: en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if not mod_bus.hay_bus(ctx.config):
        return _comun.queja("no hay bus: [bus] url en la configuración (docs/arquitectura.md, «Entre máquinas: el bus»)")
    if o.verbo == "estado":
        try:
            datos = mod_bus.estados(ctx.config)
        except mod_bus.ErrorDeBus as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json({"hilos": datos})
        for nombre, d in sorted(datos.items()):
            print(f"{d.get('atencion', ''):<11}{nombre:<36}{d.get('maquina', '')}  " + _comun.tenue(str(d.get("actualizado", ""))[:16]))
        return 0
    try:
        asyncio.run(Nodo(ctx).correr(una_vez=o.una_vez))
    except mod_bus.ErrorDeBus as e:
        return _comun.queja(str(e))
    except KeyboardInterrupt:
        pass
    return 0


class Nodo:
    def __init__(self, ctx, web: str = ""):
        self.ctx = ctx
        #: la dirección de la página de esta máquina (`telar serve --web`), para la foto
        self.web = web
        self.config = ctx.config
        self.yo = mod_bus.maquina(self.config)
        self.persona = mod_bus.persona(self.config)
        self.subs: dict[str, object] = {}
        #: lo último que se publicó de cada hilo de aquí, por su clave del bus, sin `actualizado`. Al arrancar se
        #: siembra con lo que el bus dice vivo en esta máquina (`sembrar`): sin eso, un hilo que murió con el
        #: nodo apagado quedaría vivo en el bus para siempre
        self.publicado: dict[str, str] = {}
        #: si ya se sembró `publicado` con lo del bus (se reintenta cada 30 s si al arrancar no se pudo)
        self.sembrado = False
        #: los hilos que se sembraron y todavía no aparecen aquí: si se publican muertos, se dice por qué
        self.sembrados: set[str] = set()
        #: las claves sembradas que escribió un nodo de antes, sin dueño ni época (telar.dueno): se vuelven a escribir una
        #: vez aunque aquí nada cambie, para que el registro diga de quién son
        self.sin_dueno: set[str] = set()
        #: las reaperturas recientes de la ventana de cada hilo de otra máquina (ver `puede_reabrir`)
        self.reabiertas: dict[str, dict] = {}
        self.vueltas = 0
        #: cuántas vueltas seguidas falta un hilo que estaba vivo (se anuncia muerto a la segunda)
        self.ausentes: dict[str, int] = {}
        self.espejo = None
        #: el último estado de cada hilo de las otras máquinas, por su clave del bus (lo llena `_vigilar`)
        self.vistos: dict[str, dict] = {}
        #: lo último que se dejó en `ajenos.json`, para no reescribirlo si no cambió
        self.ajenos_escritos: dict | None = None
        #: si el vigía ya recibió lo que había en el bus al arrancar: antes, `vistos` está a medias
        self.ajenos_listos = False
        #: la tarea que vigila el bus: mientras viva, `ajenos.json` se refresca (ver `AJENOS_CADUCA`)
        self.vigia = None
        #: el registro de los hilos de aquí en la última vuelta: (vínculos, archivados, remotos)
        self.registro: tuple[dict, set, dict, set, dict, dict] = ({}, set(), {}, set(), {}, {})
        #: lo que el vigía recibió y falta atender (anotar la atención, la ventana): lo último de cada clave
        self.por_atender: dict[str, dict] = {}
        #: los pedidos con respuesta en curso o esperando turno, de todos los verbos (ver `_aparte`)
        self.atendiendo: set = set()
        #: el nombre de antes de cada agente de aquí que su agente.toml renombró → el de ahora: su casilla
        #: vieja se sigue recogiendo, hacia la nueva (lo llena `locales`)
        self.renombrados: dict[str, str] = {}

    def anotar(self, texto: str) -> None:
        from datetime import datetime

        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}", flush=True)

    # ── qué vive aquí (sincrónico: tmux, archivos) ──────────────────────────────

    def locales(self) -> dict[str, dict]:
        tel = _comun.tejer(self.ctx, con_ficha=False)
        est = tel.estado
        remotos = est.remotos()
        atenciones = est.atenciones()
        sesiones = est.sesiones()
        vinculos, archivados = est.vinculos(), est.archivados()
        from telar import agentes as mod_agentes
        from telar import casilla

        publicos = est.publicos() | mod_agentes.publicos(self.config, vinculos)
        # el padre de cada uno como lo ve aquí (el puesto, o el que lo abrió): las ventanas de otra máquina, igual
        etiquetas, padres = est.etiquetas(), est.padres_efectivos()
        self.registro = (vinculos, archivados, remotos, publicos, etiquetas, padres)
        try:
            # cuántos borradores le guardó la persona (telar.borradores): la fila de otra máquina lo dice, tenue
            cuantos = {h: len(v) for h, v in est.todos_los_borradores().items()}
        except Exception:  # noqa: BLE001 - sin poder leerlo, ninguno
            cuantos = {}
        salida: dict[str, dict] = {}

        from telar import movil

        try:
            # la dirección de cada ventana de la sesión del telar («@338/marca»): con ella otra máquina
            # la mira (telar.remoto.guion_ver). Listarlas también les pone marca a las que no tienen
            direcciones = {v.ventana: v.direccion for v in movil.ventanas(self.config.sesion)}
        except Exception:  # noqa: BLE001 - sin tmux no hay ventanas que mirar desde afuera
            direcciones = {}

        try:
            dormidos = est.dormidos()
        except Exception:  # noqa: BLE001 - sin poder leerlo, nadie duerme
            dormidos = {}

        def ficha_de(nombre: str, vivo: bool, residente: str = "", ventana: str = "") -> dict:
            atencion, desde = atenciones.get(nombre, (None, None))
            return {"nombre": nombre, "maquina": self.yo, "vivo": vivo, "residente": residente,
                    # si duerme (telar.dormir): su ventana sigue, sin agente; abrirlo o escribirle lo despierta
                    "dormido": vivo and nombre in dormidos,
                    "atencion": atencion.value if atencion else "ninguna",
                    "desde": desde.isoformat(timespec="seconds") if desde else "",
                    "conversacion": (sesiones.get(nombre) or ("",))[0],
                    # el registro del hilo, que las otras máquinas leen de aquí en vez de copiarlo
                    **registro_de(nombre, vinculos, archivados, publicos, etiquetas, padres),
                    # dónde mirarlo desde otra máquina: su ventana en la sesión del telar
                    "ventana": ventana,
                    # la palabra de su casilla y de su clave (telar.casilla.ficha): la apartada, si su nombre choca
                    "ficha": casilla.ficha(self.config, nombre),
                    "borradores": cuantos.get(nombre, 0)}

        agentes = self._agentes_de_aqui()
        # antes de publicar y suscribir con sus fichas: que dos hilos cuyos nombres solo difieren en mayúsculas,
        # tildes o espacios no compartan casilla
        de_aqui = [h for h in tel.hilos if h.nombre not in remotos and not getattr(h, "remoto", "")]
        self.separar([h.nombre for h in de_aqui] + [a.nombre for a in agentes],
                     leen=[h.nombre for h in de_aqui if tel.vivo(h)] + [a.nombre for a in agentes])
        for h in tel.hilos:
            if h.nombre in remotos:
                continue  # su ventana está aquí, pero vive en otra máquina: lo publica esa
            if tel.vivo(h):
                salida[h.nombre] = ficha_de(h.nombre, True, ventana=direcciones.get(h.id, ""))
        renombrados = {}
        for a in agentes:
            actual = salida.get(a.nombre) or ficha_de(a.nombre, False)
            # `residente = false` en su agente.toml: no se le abre la sesión sola cuando le llega algo (avisar)
            actual["residente"] = a.clave if a.residente else ""
            salida[a.nombre] = actual
            if a.nombre_de_antes not in (a.nombre, "") and \
                    mod_bus.ficha(a.nombre_de_antes, self.config) != mod_bus.ficha(a.nombre, self.config):
                renombrados[a.nombre_de_antes] = a.nombre
        # un hilo vivo con el nombre de antes (su ventana vieja) sigue teniendo su casilla: esa no se le quita
        self.renombrados = {viejo: nuevo for viejo, nuevo in renombrados.items() if viejo not in salida}
        return salida

    def separar(self, nombres, leen=()) -> list[str]:
        """Aparta la casilla de los hilos de aquí cuyo nombre choca con el de otro (telar.casilla.separar): con los
        de aquí, y con lo que el bus dice que tienen las otras máquinas (lo que vio el vigía, `vistos`). `leen`: los
        que el nodo suscribe (vivos y agentes), que se quedan con la forma normalizada antes que un archivado.
        Devuelve los que apartó."""
        from telar import casilla

        prefijo = f"{getattr(self, 'persona', '')}."
        # lo de las otras máquinas, como quedó la última vez (al arrancar, antes de que el vigía traiga lo del bus): un
        # nombre de allá cuenta como dueño de su forma normalizada. Si allá estaba apartado, apartar al de aquí no
        # estorba: igual queda cada uno con la suya
        ocupadas = {}
        try:
            for nombre, d in mod_estado.abrir(self.config).ajenos(viejos=True).items():
                # con la ficha que publicó su nodo (uno apartado allá no ocupa la forma normalizada); sin ella (un
                # telar de antes, que no aparta a nadie), la forma normalizada
                ocupadas.setdefault(str(d.get("ficha") or casilla.nombre_de_carpeta(nombre)), nombre)
        except Exception:  # noqa: BLE001 - sin el archivo, lo que diga el vigía
            pass
        # y lo que el vigía vio en el bus, que manda (una copia: el vigía lo cambia mientras esto corre en otro hilo)
        vistos = dict(getattr(self, "vistos", None) or {})
        ocupadas.update({k[len(prefijo):]: d["nombre"] for k, d in vistos.items()
                         if k.startswith(prefijo) and isinstance(d, dict) and isinstance(d.get("nombre"), str)})
        try:
            apartados = casilla.separar(self.config, nombres, ocupadas, leen)
        except OSError as e:
            self.anotar(f"apartar las casillas que chocan: {type(e).__name__}: {e}")
            return []
        for n in apartados:
            self.anotar(f"«{n}» chocaba con otro hilo de nombre casi igual: su casilla es ahora "
                        f"{casilla.ficha(self.config, n)}")
        return apartados

    def _agentes_de_aqui(self) -> list:
        from telar import agentes as mod_agentes

        return [a for a in mod_agentes.descubrir(self.config) if (a.en or self.config.agentes_en) in ("", "aqui")]

    def avisar(self, nombre: str, info: dict, encargo: bool = False) -> str:
        """Que el hilo se entere de lo que llegó a su casilla, sin teclear el contenido. Un residente sin
        sesión se abre con cualquier mensaje; uno con `residente = false`, solo si llegó un `encargo` (de
        `telar encargar` o de un periódico: es pedirlo explícito, como sin bus)."""
        from telar import agentes as mod_agentes
        from telar import casilla, encargos
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        est = mod_estado.abrir(self.config)
        # uno dormido (telar.dormir) se despierta en su ventana, con el aviso de primer mensaje: el gancho le entrega
        # lo de su casilla
        from telar import dormir

        if dormir.dormido(self.config, nombre):
            try:
                hecho = dormir.despertar(self.config, nombre, mensaje=casilla.aviso(self.config, nombre))
            except RuntimeError as e:
                self.anotar(str(e))
                return "en su casilla: no se pudo despertar"
            if hecho:
                est.anotar_atencion(nombre, Atencion.TRABAJANDO)
                self.anotar(hecho)
                return "despertado"
        escribir = encargos._donde(self.ctx, nombre)
        if escribir is not None:
            if est.atencion(nombre) == Atencion.TRABAJANDO and not self.atencion_vieja(est, nombre):
                return "trabajando: se lo entrega Stop"
            if casilla.mod_vivo(self.config, nombre):
                return "lo avisa su mod"
            escribir(casilla.aviso(self.config, nombre))
            est.anotar_atencion(nombre, Atencion.TRABAJANDO)
            return "avisado"
        if info.get("residente"):
            agente = next((a for a in mod_agentes.descubrir(self.config) if a.clave == info["residente"]), None)
            if agente is not None:
                encargos._abrir(self.ctx, agente, casilla.aviso(self.config, nombre))
                return "abierto"
        elif encargo:
            agente = next((a for a in self._agentes_de_aqui() if a.nombre == nombre and not a.residente), None)
            if agente is not None:
                encargos._abrir(self.ctx, agente, casilla.aviso(self.config, nombre))
                return "abierto (un encargo, aunque no es residente)"
        return "en su casilla, hasta que se abra"

    def rotar_relevos(self) -> None:
        """El paso de cada residente que está rotando su conversación (telar.rotacion): cuando quedó quieto tras
        escribir su relevo, el /clear en su ventana; cuando la conversación nueva ya está anotada, que lo lea."""
        from telar import encargos, rotacion
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        pendientes = rotacion.leer(self.config)
        if not pendientes:
            return
        est = mod_estado.abrir(self.config)
        for hilo in pendientes:
            escribir = encargos._donde(self.ctx, hilo)
            if escribir is None:
                # su ventana no está aquí (se cerró): solo se abandona cuando vence
                linea = rotacion.avanzar(self.config, hilo, quieto=False, sesion_actual="", escribir=lambda _t: None)
            else:
                quieto = est.atencion(hilo) != Atencion.TRABAJANDO or self.atencion_vieja(est, hilo)
                sesion = (est.sesiones().get(hilo) or ("",))[0]
                linea = rotacion.avanzar(self.config, hilo, quieto=quieto, sesion_actual=sesion, escribir=escribir)
                if linea and "conversación nueva" in linea:
                    est.anotar_atencion(hilo, Atencion.TRABAJANDO)
            if linea:
                self.anotar(linea)

    @staticmethod
    def atencion_vieja(est, nombre: str) -> bool:
        """Un «trabajando» que lleva más de TRABAJANDO_VIEJO sin cambiar es un estado que quedó pegado
        (un gancho que no corrió), no un turno real: esperar al Stop dejaría los mensajes sin entregar."""
        from datetime import datetime

        _, desde = est.atenciones().get(nombre, (None, None))
        if desde is None:
            return False
        ahora = datetime.now(desde.tzinfo) if desde.tzinfo else datetime.now()
        return (ahora - desde).total_seconds() > TRABAJANDO_VIEJO

    # ── el bucle ─────────────────────────────────────────────────────────────────

    async def _suscribir(self, nc, tema: str, cb, *, aparte: bool = True, en_fila: bool = False, **opciones):
        """Una suscripción del nodo, con tope de lo que puede esperar (PENDIENTES_*). `aparte`: un pedido con
        respuesta, que se atiende en su propia tarea (`_aparte`) para que uno lento no atrase a los demás;
        `en_fila`: los de este tema, de a uno y en orden."""
        if aparte:
            cb = self._aparte(cb, asyncio.Lock() if en_fila else None)
        return await nc.subscribe(tema, cb=cb, pending_msgs_limit=PENDIENTES_MSGS,
                                  pending_bytes_limit=PENDIENTES_BYTES, **opciones)

    def _aparte(self, cb, fila: asyncio.Lock | None = None):
        """El callback de una suscripción, en una tarea suya. nats-py llama los de una misma suscripción de a
        uno, dentro de su lectura: un `telar hilo` que tarda diez segundos dejaba a todo lo que llegaba a ese
        tema esperando en la cola de nats-py, y a los pedidos siguientes del mismo verbo esperando hasta pasarse
        de su plazo (`nats: timeout` del lado del que pedía). Así nats-py nunca espera: se atienden hasta
        PEDIDOS_A_LA_VEZ a la vez, con `fila` de a uno por tema (los que escriben), y con PEDIDOS_EN_ESPERA en
        curso o esperando se contesta que está ocupada.

        Los turnos y la cuenta de los que esperan son de esta suscripción, no del nodo: como antes, cuando
        cada una iba por su cuenta, los lentos de un verbo (un `resultado-comentar`, un `tarea` que corre un
        proceso) no dejan sin turno a los de otro (un `leer`, un correo)."""
        turnos, suyos = asyncio.Semaphore(PEDIDOS_A_LA_VEZ), set()

        async def atender(m) -> None:
            if len(suyos) >= PEDIDOS_EN_ESPERA:
                if getattr(m, "reply", ""):
                    await m.respond(json.dumps({"ok": False, "ocupada": True, "error": (
                        f"{self.yo} está ocupada: {len(suyos)} pedidos en curso; prueba en un rato")},
                        ensure_ascii=False).encode())
                return

            async def con_turno() -> None:
                async with fila or contextlib.nullcontext(), turnos:
                    try:
                        await cb(m)
                    except Exception as e:  # noqa: BLE001 - uno que falla no tumba a los demás
                        self.anotar(f"pedido en {getattr(m, 'subject', '?')}: {type(e).__name__}: {e}")

            t = asyncio.create_task(con_turno())
            for en in (suyos, self.atendiendo):
                en.add(t)
                t.add_done_callback(en.discard)

        return atender

    async def correr(self, *, una_vez: bool = False) -> None:
        nc = await mod_bus.conectar(self.config, para_siempre=not una_vez)
        # los pedidos al bus de este proceso (la API, en `telar serve --nodo`) van por esta conexión
        mod_bus.registrar_conexion(nc, asyncio.get_running_loop())
        js = nc.jetstream(timeout=ESPERA_JS)
        await mod_bus.asegurar(js)
        kv = await js.key_value(mod_bus.ESTADO)
        self.kv, self.js = kv, js
        self.espejo = await js.key_value(mod_bus.ESPEJO)
        self.anotar(f"en el bus como {self.persona}@{self.yo} ({self.config.bus.url})")
        self.nc = nc
        # lo que el bus dice vivo aquí, antes de la primera vuelta y del vigía: lo que murió con el nodo apagado
        await self.sembrar(kv)
        await self.suscribirse(nc)
        vigia = self.vigia = None if una_vez else asyncio.create_task(self._vigilar(kv))
        vigia_espejo = None if una_vez else asyncio.create_task(self._vigilar_espejo())
        try:
            await self._girar(js, kv, una_vez=una_vez)
        finally:
            for t in (vigia, vigia_espejo):
                if t:
                    t.cancel()
            mod_bus.registrar_conexion(None, None)
            await nc.close()

    async def sembrar(self, kv) -> bool:
        """`publicado` con lo que el bus dice vivo en esta máquina, como lo deja `_vuelta`: el valor guardado sin
        `actualizado`. Así un hilo que murió mientras el nodo no corría (la máquina se cayó, o `telar serve` se
        reinició justo cuando se cerró su ventana) lo publica muerto la lógica de siempre, a la segunda vuelta sin
        estar aquí. Solo lo que dice esta máquina: el que se mudó a otra es de aquella. Un hilo que ya se
        publicó en este arranque no se toca. Si el bus no contesta, se dice y se intenta en otra vuelta.
        Devuelve si se pudo leer."""
        from telar import dueno as mod_dueno

        try:
            en_el_bus = await asyncio.wait_for(self._lo_del_bus(kv), ESPERA_JS)
        except Exception as e:  # noqa: BLE001 - sin sembrar, el nodo funciona como antes
            self.anotar(f"no pude leer del bus qué hilos daba vivos aquí ({type(e).__name__}: {e}): lo intento de nuevo")
            return False
        for clave, d in en_el_bus.items():
            nombre = d.get("nombre")
            if d.get("maquina") != self.yo or not d.get("vivo") or not isinstance(nombre, str) or not nombre:
                continue
            if clave in self.publicado:
                continue
            # lo que la vuelta compara es lo que sabe del hilo, sin lo que agrega el registro (su dueño, su época, el
            # traspaso): telar.dueno lo pone al publicar
            valor = {k: v for k, v in d.items()
                     if k not in ("actualizado", "dueno", "epoca", *mod_dueno.PROTOCOLO, *mod_dueno.SEGUIDO)}
            self.publicado[clave] = json.dumps(valor, ensure_ascii=False, sort_keys=True)
            self.sembrados.add(nombre)
            if not d.get("dueno") or "epoca" not in d:
                self.__dict__.setdefault("sin_dueno", set()).add(clave)
        self.sembrado = True
        return True

    async def _lo_del_bus(self, kv) -> dict[str, dict]:
        """El último estado de cada hilo de esta persona en el bus, por su clave: lo que había al empezar a mirar."""
        vigia = await kv.watch(f"{self.persona}.>", ignore_deletes=True)
        salida: dict[str, dict] = {}
        try:
            async for e in vigia:
                if e is None:
                    break  # lo que había ya llegó entero
                try:
                    d = json.loads(e.value)
                except (TypeError, ValueError):
                    continue
                if isinstance(d, dict):
                    salida[e.key] = d
        finally:
            with contextlib.suppress(Exception):
                await vigia.stop()
        return salida

    async def _girar(self, js, kv, *, una_vez: bool = False) -> None:
        """Las vueltas del nodo, cada VUELTA segundos. Una que falla no tumba el nodo, y su falla va al
        registro en una línea, la misma una vez cada diez minutos (con el bus caído fallan todas: eran
        cientos de `vuelta con error: TimeoutError` por hora). El registro de este proceso se recorta cada
        ESPEJO_CADA vueltas aunque fallen: es justo cuando más crece."""
        fallas = mod_bus.Avisador(self.anotar, prefijo="vuelta con error")
        giros = 0
        while True:
            try:
                await self._vuelta(js, kv)
            except Exception as e:  # noqa: BLE001 - una vuelta que falla no tumba el nodo
                fallas.anotar(e)
            giros += 1
            if giros % ESPEJO_CADA == 0:
                # el registro de este proceso, con tope (bajo launchd es un archivo que nadie rota)
                try:
                    await asyncio.to_thread(self.recortar_registro)
                except Exception as e:  # noqa: BLE001 - nunca debería; si pasa, que no pare las vueltas
                    self.anotar(f"recortar el registro: {type(e).__name__}: {e}")
            if una_vez:
                break
            await asyncio.sleep(VUELTA)

    async def suscribirse(self, nc) -> None:
        """Lo que atiende el nodo. Los pedidos con respuesta, cada uno en su tarea (`_aparte`): los que solo
        leen, varios a la vez; los que escriben, de a uno por verbo. El ping no, para que conteste aunque el nodo
        esté ocupado. Los avisos sin respuesta (cambios, directorios), de a uno y en orden: son cortos, y uno
        viejo no debe pisar a uno nuevo."""
        rpc = lambda verbo: mod_bus.tema_rpc(self.config, self.yo, verbo)  # noqa: E731
        await self._suscribir(nc, rpc("ping"), self._ping, aparte=False)
        # entre personas (telar.entre_personas): el correo que le escriben a esta persona (lo atiende un
        # solo nodo suyo: cola «correo») y los directorios de las demás
        from telar import cuentas

        # en fila: escribe en la casilla, y dos correos seguidos al mismo hilo tienen que quedar en su orden
        await self._suscribir(nc, cuentas.CORREO.format(self.persona), self._correo, en_fila=True, queue="correo")
        await self._suscribir(nc, cuentas.DIRECTORIO.format("*"), self._directorio, aparte=False)
        await self._suscribir(nc, mod_bus.tema_cambio(self.config, "*"), self._cambio, aparte=False)
        # en la máquina del bus, la gestión de personas (telar.personas): la piden las otras máquinas de esta persona
        # y, por la importación que solo tienen ellas, las cuentas admin
        from telar import unirse

        if unirse.administra_aqui():
            await self._suscribir(nc, cuentas.ADMIN.format(self.persona), self._admin, en_fila=True)
            # y el alojamiento (telar.alojamiento): cualquier persona del bus pide un lugar en este servidor
            await self._suscribir(nc, cuentas.ALOJAR.format(self.persona), self._alojar, en_fila=True)
        for verbo, cb in (("leer", self._leer), ("responder", self._responder_pregunta), ("resultado", self._resultado),
                          ("resultado-comentar", self._resultado_comentar), ("resultado-agregar", self._resultado_agregar),
                          ("resultado-visto", self._resultado_visto), ("resultado-sin-ver", self._resultado_sin_ver),
                          ("proveedor", self._proveedor),
                          ("tarea", self._tarea), ("tipo", self._tipo), ("periodicos", self._periodicos),
                          ("hilo", self._hilo), ("equipo", self._equipo), ("aviso", self._aviso),
                          ("archivo", self._archivo), ("archivo-leer", self._archivo_leer), ("modulo", self._modulo),
                          ("notas", self._notas), ("nota", self._nota), ("serie", self._serie),
                          ("serie-recordar", self._serie_recordar), ("encargo", self._encargo),
                          ("agentes", self._agentes), ("hilo-llegar", self._hilo_llegar),
                          ("hilo-revisar", self._hilo_revisar), ("hilo-hijo", self._hilo_hijo), ("hilo-despertar", self._hilo_despertar),
                          ("hilo-traer", self._hilo_traer), ("mudanza-progreso", self._mudanza_progreso),
                          ("replica-estado", self._replica_estado), ("replica-escribir", self._replica_escribir),
                          ("replica-cerrar", self._replica_cerrar),
                          ("codigos", self._codigos), ("contexto", self._contexto),
                          ("avisos-archivo", self._avisos_archivo), ("avisos-visto", self._avisos_visto),
                          ("comentarios", self._comentarios), ("borradores", self._borradores)):
            await self._suscribir(nc, rpc(verbo), cb, en_fila=verbo not in SOLO_LEEN)

    def releer_config(self) -> bool:
        """Si la configuración cambió en el disco, la vuelve a leer (la máquina y la persona del bus no cambian con el
        nodo andando). Elegir el motor de los agentes (`[agente] nombre`) con el nodo ya corriendo hace que los
        residentes que están para siempre se abran ya, sin esperar su pausa. True si la releyó."""
        from dataclasses import replace
        from pathlib import Path

        from telar import config as mod_config

        ruta = getattr(self.config, "origen", None)
        if not ruta:
            return False  # sin archivo (todo por defecto): no hay qué releer
        try:
            marca = Path(ruta).stat().st_mtime
        except OSError:
            return False
        if getattr(self, "marca_config", None) is None:
            self.marca_config = marca
            return False
        if marca == self.marca_config:
            return False
        self.marca_config = marca
        try:
            nueva = mod_config.cargar(ruta)
        except Exception as e:  # noqa: BLE001 - una configuración a medio escribir: sigue la de antes
            self.anotar(f"la configuración cambió y no se pudo leer ({e}): sigo con la de antes")
            return False
        sin_motor = not self.config.agente.nombre
        self.config = nueva
        self.ctx = replace(self.ctx, config=nueva)
        if sin_motor and nueva.agente.nombre:
            self.abiertos_siempre = {}
            self.anotar(f"el motor de los agentes ahora es «{nueva.agente.nombre}»: los residentes se abren con él")
            # los que están para siempre y se abrieron sin motor tienen un tab con una shell: se abre el agente ahí
            from telar.servicios import agentes as servicio

            for a in self._agentes_de_aqui():
                if a.presencia == "siempre":
                    try:
                        servicio.abrir_aqui(self.ctx, a.clave)
                    except Exception as e:  # noqa: BLE001 - lo intenta de nuevo su vuelta de siempre
                        self.anotar(f"«{a.nombre}»: no pude abrirlo con el motor nuevo: {e}")
        return True

    async def _vuelta(self, js, kv) -> None:
        self.releer_config()
        # los disparadores de cambio que quedaron esperando su pausa salen cuando se cumple
        despacho = self._despacho()
        if despacho and despacho.pendientes:
            self._disparar(despacho.listos(asyncio.get_running_loop().time()))
        locales = await asyncio.to_thread(self.locales)
        # casillas: una suscripción durable por hilo que vive aquí, y la del nombre de antes de un agente
        # renombrado (lo que le mandó una máquina que todavía no tiene su agente.toml nuevo)
        renombrados = getattr(self, "renombrados", {})
        for nombre in [*locales, *renombrados]:
            f = mod_bus.ficha(nombre, self.config)
            if f not in self.subs:
                self.subs[f] = await js.pull_subscribe(mod_bus.tema_casilla(self.config, nombre, ficha_=f),
                                                       durable=f"c-{self.persona}-{f}", stream=mod_bus.STREAM)
        for f in [f for f in self.subs if f not in {mod_bus.ficha(n, self.config) for n in [*locales, *renombrados]}]:
            del self.subs[f]  # se fue a otra máquina: que lo recoja aquella
        await self._recoger(locales)
        # lo que el bus daba vivo aquí al arrancar, si entonces no se pudo leer
        if not getattr(self, "sembrado", True) and self.vueltas % ESPEJO_CADA == 0:
            await self.sembrar(kv)
        # estado: solo lo que cambió, y que dejó de estar vivo lo que ya no está aquí
        actuales = dict(locales)
        sembrados = getattr(self, "sembrados", set())
        await self._soltar_claves_movidas(kv, actuales)
        for clave, valor in list(self.publicado.items()):
            previo = json.loads(valor)
            if previo["nombre"] not in actuales and previo.get("vivo"):
                if clave in self.vistos:
                    # ya lo publica otra máquina (se mudó): no es de aquí, y publicarlo muerto le pisaría su estado
                    del self.publicado[clave]
                    self.ausentes.pop(previo["nombre"], None)
                    sembrados.discard(previo["nombre"])
                    continue
                # muerto solo si falta dos vueltas seguidas: una lectura de tmux que falla una vez
                # no tiene por qué anunciarle a la otra máquina que el hilo se fue
                self.ausentes[previo["nombre"]] = self.ausentes.get(previo["nombre"], 0) + 1
                if self.ausentes[previo["nombre"]] < 2:
                    actuales[previo["nombre"]] = previo
                    continue
                actuales[previo["nombre"]] = {**previo, "vivo": False, "atencion": "ninguna", "ventana": "", "dormido": False}
                if previo["nombre"] in sembrados:
                    sembrados.discard(previo["nombre"])
                    self.anotar(f"«{previo['nombre']}»: el bus lo daba vivo aquí desde antes de que arrancara el nodo "
                                f"y aquí no está: lo publico muerto")
            elif previo["nombre"] not in actuales:
                # ya publicado como muerto: si aquí se archivó o se vinculó después (lo pidió otra
                # máquina), se vuelve a publicar con lo nuevo. Salvo que ya lo publique otra máquina
                # (se mudó): pisarle su estado lo traería de vuelta
                vinculos, archivados, remotos, publicos, etiquetas, padres = self.registro
                if clave in self.vistos or previo["nombre"] in remotos:
                    continue
                nuevo = {**previo, **registro_de(previo["nombre"], vinculos, archivados, publicos, etiquetas, padres)}
                if nuevo != previo:
                    actuales[previo["nombre"]] = nuevo
        for nombre in locales:
            self.ausentes.pop(nombre, None)
            sembrados.discard(nombre)
        # cada 6 s, los residentes que rotan su conversación con relevo (telar.rotacion): el /clear y el aviso
        if self.vueltas % 3 == 0:
            try:
                await asyncio.to_thread(self.rotar_relevos)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"la rotación con relevo: {type(e).__name__}: {e}")
        # un hilo hijo que terminó un turno se lo cuenta a su padre (un aviso, que no lo despierta)
        try:
            await asyncio.to_thread(self.avisar_padres, locales)
        except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
            self.anotar(f"avisar a los padres: {type(e).__name__}: {e}")
        # cada 30 s, quiénes están vivos aquí: si tmux se cae, `telar hilo caidos` sabe qué reabrir
        if self.vueltas % 15 == 0:
            vivos = [n for n, i in locales.items() if i.get("vivo")]
            await asyncio.to_thread(lambda: mod_estado.abrir(self.config).anotar_vivos(vivos))
            # y el estado deseado: el residente sin sesión se avisa, no se abre (telar.deseado)
            try:
                await asyncio.to_thread(self.mirar_deseado, locales)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"el estado deseado: {type(e).__name__}: {e}")
            # y quién quedó detenido en la pregunta de confiar en una carpeta, que no avisa sola (telar.confiar)
            try:
                await asyncio.to_thread(self.mirar_confiar)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"la pregunta de confiar: {type(e).__name__}: {e}")
            # y los borradores en espera de un hilo que terminó sin que el evento los soltara (telar.borradores)
            try:
                await asyncio.to_thread(self.soltar_borradores, locales)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"soltar borradores: {type(e).__name__}: {e}")
            # y los hilos quietos se duermen: su agente se cierra y su ventana espera (telar.dormir)
            try:
                await asyncio.to_thread(self.mirar_dormir)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"dormir a los quietos: {type(e).__name__}: {e}")
            # y lo visto de los avisos de archivo que ya dicen ok se olvida: si vuelve a estar mal, sale (telar.avisos)
            try:
                from telar import avisos

                await asyncio.to_thread(avisos.olvidar_los_ok, self.config)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"lo visto de los avisos: {type(e).__name__}: {e}")
            # y lo de los hilos ajenos sigue valiendo mientras se vigila el bus: sin esto, caduca
            vigia = getattr(self, "vigia", None)
            if vigia is not None and not vigia.done() and getattr(self, "ajenos_listos", False):
                await asyncio.to_thread(lambda: mod_estado.abrir(self.config).refrescar_ajenos())
            # y que las fotos de las otras máquinas dicen algo: con el nodo de aquí conectado, la que envejece es la de
            # una máquina que se fue (telar.alcance); sin esta marca, se supone que contestan
            if getattr(getattr(self, "nc", None), "is_connected", False):
                from telar import alcance

                await asyncio.to_thread(alcance.marcar_al_dia, self.config)
        # cada 6 s, lo que espera en cola para una máquina que estaba fuera de línea y volvió (telar.alcance): aparte,
        # porque cada pedido puede esperar hasta su plazo, y la vuelta no debe esperarlo
        if self.vueltas % 3 == 0:
            tarea = getattr(self, "tarea_cola", None)
            if tarea is None or tarea.done():
                from telar import alcance

                if alcance.cola(self.config):
                    self.tarea_cola = asyncio.create_task(asyncio.to_thread(self.atender_cola))
        await self.publicar_estado(kv, actuales, aqui=locales)
        # un hilo abierto aquí que el bus dice de otra máquina, con su misma conversación: lo siguieron allá mientras
        # esta no estaba (telar.seguir). Cede sola, en la primera vuelta después de volver
        try:
            await self.ceder_seguidos(locales)
        except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
            self.anotar(f"ceder lo que se siguió en otra: {type(e).__name__}: {e}")
        # cada 30 s, los traspasos que quedaron a medias (telar.dueno): uno que esta máquina cedía y nadie conduce ya,
        # uno que tomó y no alcanzó a abrir, una ventana que esperaba a un hilo que ya es de otra. Y el aviso de lo que
        # se cedió al volver, al día
        if self.vueltas % ESPEJO_CADA == 0:
            try:
                await self.mudanzas_colgadas(kv)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"las mudanzas a medias: {type(e).__name__}: {e}")
            try:
                from telar import seguir

                await asyncio.to_thread(seguir.refrescar_aviso, self.config)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"el aviso de lo que se cedió al volver: {type(e).__name__}: {e}")
        # la foto del espejo, cada tanto: la que muestra el panel en la otra máquina. Y al tiro si cambió qué hilos
        # hay o cuáles están vivos (uno se cerró, se archivó, nació): la otra máquina lo ve en segundos, no en 30
        self.vueltas += 1
        firma = sorted((n, bool(i.get("vivo")), bool(i.get("dormido"))) for n, i in locales.items())
        # y lo que muestran las páginas de aquí: la máquina de un hilo que se empieza a mirar desde aquí no lo duerme
        # (telar.dormir, `mirando` en la foto)
        try:
            from telar import dormir

            firma = (firma, sorted((p["maquina"], p["hilo"]) for p in dormir.paginas(self.config)))
        except Exception:  # noqa: BLE001 - sin poder leerlas, la firma de los hilos
            pass
        if self.vueltas % ESPEJO_CADA == 1 or firma != getattr(self, "firma_foto", None):
            self.firma_foto = firma
            foto = await asyncio.to_thread(self.foto)
            if foto is not None:
                await self.espejo.put(f"{self.persona}.{self.yo}", json.dumps(foto, ensure_ascii=False).encode())
                # y el directorio, para las demás personas: solo nombres, carpetas y una línea
                from telar import cuentas, entre_personas

                await self.nc.publish(cuentas.DIRECTORIO.format(self.persona), json.dumps(
                    entre_personas.directorio(foto, self.persona, self.config), ensure_ascii=False).encode())
            # y las ventanas de los hilos de las otras máquinas, contra lo que dice el bus: un evento perdido,
            # o una ventana cerrada aquí sin cambio allá, se corrige aquí (un dueño por hilo, paso 2)
            try:
                await asyncio.to_thread(self.conciliar)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"conciliar las ventanas: {type(e).__name__}: {e}")

    async def _soltar_claves_movidas(self, kv, actuales: dict) -> list[str]:
        """Un hilo de aquí que se apartó (telar.casilla.separar) publicaba su estado con la forma normalizada de su
        nombre, que ahora es solo del otro: esa clave se suelta (se borra del estado, salvo que la publique otro
        hilo de aquí), para que quien busque al otro no lo encuentre a él. Lo mismo la clave apartada de uno que ya
        no lo está (se renombró): quien le escriba a un hilo nuevo con ese nombre no debe ir a parar a ella
        (telar.bus.ficha_para). Devuelve las claves que soltó."""
        from telar import casilla

        nuevas = {mod_bus.clave_estado(self.config, n) for n in actuales}
        sueltas = []
        for clave, valor in list(self.publicado.items()):
            try:
                nombre = json.loads(valor).get("nombre")
            except (ValueError, AttributeError):
                continue
            if not isinstance(nombre, str) or clave == mod_bus.clave_estado(self.config, nombre):
                continue
            if nombre not in actuales and not casilla.es_apartada(clave.partition(".")[2]):
                continue  # uno que se fue (se mudó, se cerró) con su clave de siempre: eso lo ve la vuelta
            del self.publicado[clave]
            sueltas.append(clave)
            if clave in nuevas:
                continue  # la publica el otro hilo de aquí en esta misma vuelta
            try:
                # solo si lo que está ahí sigue siendo suyo: el dueño de la forma, en otra máquina, también publicaba
                # ahí (se pisaban), y borrarle su estado lo dejaría fuera del bus hasta que cambie algo suyo
                actual = json.loads((await kv.get(clave)).value or b"{}")
                if isinstance(actual, dict) and actual.get("nombre") == nombre:
                    await kv.delete(clave)
            except Exception as e:  # noqa: BLE001 - ya no está, o no se pudo: lo pisa el otro al publicar
                if type(e).__name__ not in ("KeyNotFoundError", "KeyDeletedError"):
                    self.anotar(f"«{nombre}»: no pude soltar su clave de antes ({clave}): {type(e).__name__}: {e}")
        return sueltas

    def _registro(self, kv):
        """Lo que publica el nodo en el registro del bus, condicionado (telar.dueno.Registro)."""
        from telar import dueno

        r = getattr(self, "registro_bus", None)
        if r is None or r.kv is not kv:
            simple = getattr(getattr(self.config, "bus", None), "publicar", "condicionado") == "simple"
            r = self.registro_bus = dueno.Registro(kv, self.yo, simple=simple, anotar=self.anotar)
        return r

    async def publicar_estado(self, kv, actuales: dict, aqui=()) -> None:
        """Lo que cambió de cada hilo de aquí, en el registro del bus: solo si es de esta máquina (telar.dueno), con su
        época y lo de un traspaso en curso. El de un hilo que es de otra (se fue, o allá vive otro con su nombre) no se
        publica, y se vuelve a mirar cada 30 s: antes se pisaban, y un hilo que se fue podía volver a figurar aquí. Uno
        abierto aquí (`aqui`) que el bus tenía como lo dejó un nodo de antes, sin dueño ni época, se escribe una vez
        aunque no haya cambiado."""
        registro = self._registro(kv)
        ajenas = getattr(self, "ajenas_hasta", None)
        if ajenas is None:
            ajenas = self.ajenas_hasta = {}
        ahora = time.monotonic()
        sin_dueno = getattr(self, "sin_dueno", set())
        for nombre, info in actuales.items():
            valor = json.dumps(info, ensure_ascii=False, sort_keys=True)
            clave = mod_bus.clave_estado(self.config, nombre)
            de_antes = clave in sin_dueno and nombre in aqui
            if (self.publicado.get(clave) == valor and not de_antes) or ajenas.get(clave, 0) > ahora:
                continue
            if await registro.publicar(clave, info):
                self.publicado[clave] = valor
                ajenas.pop(clave, None)
                sin_dueno.discard(clave)
            else:
                self.publicado.pop(clave, None)
                ajenas[clave] = ahora + 30

    async def ceder_seguidos(self, locales: dict) -> list[str]:
        """Los hilos abiertos aquí que el registro del bus (lo que trajo el vigía) dice de otra máquina, con la misma
        conversación que tienen aquí: se siguieron allá mientras esta máquina no estaba (la etapa 4, telar.seguir), o
        quedaron abiertos aquí por otra razón. Dos agentes con una conversación no pueden seguir: el de aquí cede solo
        (decisión 3 del 24-nov), deja aparte lo que escribió después de la copia con que se siguió, y se avisa. No toca
        a los que están en un traspaso (los atiende `mudanzas_colgadas`) ni a uno que se llama igual con otra
        conversación (es otro hilo). Devuelve lo que hizo, una línea por hilo."""
        from telar import dueno, seguir
        from telar import estado as mod_estado

        hechos, est = [], None
        ya = self.__dict__.setdefault("cedidos_ya", set())
        for nombre, info in locales.items():
            conv = str(info.get("conversacion") or "")
            if not info.get("vivo") or not conv:
                continue
            clave = mod_bus.clave_estado(self.config, nombre)
            reg = self.vistos.get(clave)
            if not isinstance(reg, dict) or dueno.de(reg) in ("", self.yo) or reg.get("conversacion") != conv:
                continue
            if reg.get("cede") == self.yo or (reg.get("mudanza") or {}).get("a") == self.yo:
                continue  # viene hacia aquí: lo conduce la mudanza
            est = est or mod_estado.abrir(self.config)
            if (est.dormidos().get(nombre) or {}).get("cede"):
                continue  # se iba de aquí: lo atiende `mudanzas_colgadas`
            marca = (clave, dueno.epoca(reg))
            if marca in ya:
                continue
            ya.add(marca)
            hechos.append(await asyncio.to_thread(seguir.ceder_aqui, self.ctx, nombre, conv, reg))
        for h in hechos:
            self.anotar(h)
        return hechos

    async def mudanzas_colgadas(self, kv) -> list[str]:
        """Los traspasos que quedaron a medias (telar.dueno, telar.mudanza), con lo que dice el registro del bus:

        - uno que esta máquina cedía y cuyo proceso ya no corre (se cayó, la tapa del laptop): se echa atrás, y su agente
          despierta; si la otra ya lo había tomado, su ventana de aquí se cierra;
        - uno que esta máquina tomó y no alcanzó a abrir (el nodo se reinició, abrir falló): se abre;
        - la ventana que esperaba a un hilo que ya es de otra: se cierra.

        Devuelve lo que hizo, una línea por hilo."""
        from telar import dueno, mudanza
        from telar import estado as mod_estado

        hechos = []
        est = mod_estado.abrir(self.config)
        cedidos = {h: r for h, r in est.dormidos().items() if r.get("cede")}
        tel = None
        for nombre, d in list(cedidos.items()):
            rev, reg = await dueno.leer(kv, mod_bus.clave_estado(self.config, nombre))
            if dueno.de(reg) not in ("", self.yo):
                # ya es de otra: la ventana que esperaba se cierra
                tel = tel or await asyncio.to_thread(_comun.tejer, self.ctx, con_ficha=False)
                await asyncio.to_thread(mudanza.soltar, self.config, tel, nombre)
                hechos.append(f"«{nombre}» ya vive en {dueno.de(reg)}: cerré la ventana que esperaba aquí")
                continue
            m = (reg or {}).get("mudanza") or {}
            if reg and reg.get("cede") and not _vive(m.get("pid")) and time.time() - float(m.get("hora") or 0) > 60:
                sigue = await dueno.abortar(kv, mod_bus.clave_estado(self.config, nombre), yo=self.yo,
                                            epoca_=dueno.epoca(reg))
                if sigue:
                    texto = await asyncio.to_thread(mudanza.reanudar, self.config, nombre)
                    hechos.append(f"«{nombre}» se iba a {reg.get('cede')} y nadie lo llevaba ya: me eché atrás ({texto})")
            elif not (reg or {}).get("cede") and dueno.de(reg) in ("", self.yo):
                # cedido aquí sin traspaso en el registro (se echó atrás sin alcanzar a despertarlo)
                texto = await asyncio.to_thread(mudanza.reanudar, self.config, nombre)
                hechos.append(f"«{nombre}» esperaba un traspaso que ya no está: {texto}")
        for reg in list(getattr(self, "propios", {}).values()):
            m = reg.get("mudanza") or {}
            if dueno.de(reg) != self.yo or m.get("paso") != "abrir" or m.get("a") != self.yo \
                    or not isinstance(reg.get("nombre"), str):
                continue
            # lo está abriendo la llegada (en este proceso, hace poco): se la deja terminar
            if _vive(m.get("pid")) and time.time() - float(m.get("hora") or 0) < 120:
                continue
            ok, texto = await asyncio.to_thread(mudanza.abrir_tomado, self.ctx, reg["nombre"], reg)
            hechos.append(f"«{reg['nombre']}» lo tomó esta máquina y su traspaso no había terminado: "
                          + (texto if ok else f"no pude abrirlo ({texto})"))
        for h in hechos:
            self.anotar(h)
        return hechos

    def atender_cola(self) -> list[str]:
        """Lo que espera en cola para las máquinas que volvieron (telar.alcance.atender); una falla se dice y se
        intenta en otra vuelta."""
        from telar import alcance

        try:
            return alcance.atender(self.ctx, anotar=self.anotar)
        except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
            self.anotar(f"lo que espera en cola: {type(e).__name__}: {e}")
            return []

    def recortar_registro(self) -> bool:
        from telar import salida

        if salida.recortar_registro():
            self.anotar(f"el registro pasaba de {salida.MAX_REGISTRO // (1024 * 1024)} MB: quedó la última mitad")
            return True
        return False

    async def _recoger(self, locales: dict) -> None:
        """Lo que llegó a la casilla de cada hilo de aquí: se deja en su archivo y se le avisa. Las casillas
        se piden todas a la vez (antes, una tras otra: 0,3 s por hilo en cada vuelta, y con un hotspot lento
        no alcanzaba), y dejar cada mensaje, que escribe un archivo, va fuera del bucle."""
        from telar import casilla

        async def pedir(nombre):
            try:
                return await self.subs[mod_bus.ficha(nombre, self.config)].fetch(20, timeout=CASILLA_ESPERA)
            except Exception:  # noqa: BLE001 - sin mensajes, fetch termina por tiempo
                return []

        # de qué casilla del bus a cuál de aquí: la de cada hilo a la suya, y la del nombre de antes de un
        # agente renombrado a la de su nombre de ahora
        renombrados = {v: n for v, n in getattr(self, "renombrados", {}).items() if n in locales}
        for viejo, nuevo in renombrados.items():
            # lo que ya había bajado a la casilla de aquí con el nombre de antes, también
            if pasados := await asyncio.to_thread(casilla.mudar, self.config, viejo, nuevo):
                self.anotar(f"«{viejo}» ahora es «{nuevo}»: {pasados} mensaje(s) de su casilla vieja pasan a la nueva")
        caminos = [(n, n) for n in locales] + list(renombrados.items())
        nuevos: dict[str, int] = {}
        callados: dict[str, int] = {}
        encargos: set[str] = set()
        for (fuente, dueno), msgs in zip(caminos, await asyncio.gather(*(pedir(f) for f, _ in caminos))):
            for m in msgs:
                nombre = dueno
                try:
                    datos = json.loads(m.data)
                    # lo que llegó por la casilla compartida para un hilo vivo de aquí que se apartó (de un telar
                    # que todavía no sabe de fichas apartadas): a ese, no al dueño de la forma normalizada
                    nombre = casilla.destinatario(self.config, dueno, datos, locales) if isinstance(datos, dict) else dueno
                    if await asyncio.to_thread(casilla.dejar, self.config, nombre, datos):
                        if isinstance(datos, dict) and not casilla.despierta(datos):
                            # un aviso: queda en su casilla, sin despertarlo ni abrir su sesión
                            callados[nombre] = callados.get(nombre, 0) + 1
                        else:
                            nuevos[nombre] = nuevos.get(nombre, 0) + 1
                        # un encargo explícito (`telar encargar`, un periódico, `--modo encargo`) abre a un agente
                        # aunque no sea residente
                        if isinstance(datos, dict) and (datos.get("tipo") == "encargo" or casilla.modo_de(datos) == "encargo"):
                            encargos.add(nombre)
                except ValueError:
                    self.anotar(f"«{fuente}»: un mensaje que no es JSON, descartado")
                await m.ack()
        for nombre, cuantos in callados.items():
            self.anotar(f"«{nombre}»: {cuantos} aviso(s) en su casilla, sin despertarlo")
        for nombre, cuantos in nuevos.items():
            dicho = await asyncio.to_thread(self.avisar, nombre, locales.get(nombre, {}), nombre in encargos)
            self.anotar(f"«{nombre}»: {cuantos} mensaje(s) · {dicho}")

    async def _vigilar(self, kv) -> None:
        """La atención de los hilos que viven en otra máquina, anotada aquí apenas cambia.

        El vigía solo recibe: guarda lo último de cada hilo y se lo deja a `_atender_vistos`, que anota la
        atención y mira su ventana (tmux, archivos) en otra tarea. Antes lo hacía aquí mismo, evento por
        evento: con varios hilos cambiando de atención, el vigía se atrasaba, su cola se llenaba y nats-py
        dejaba de leer el consumidor del estado, que perdía sus latidos y se rehacía (`nats: timeout` en
        `recreate_consumer`). Una ráfaga de cambios de un mismo hilo se atiende una vez, con el último."""
        hay = asyncio.Event()
        self.por_atender, self.por_atender_fin = {}, False
        trabajador = asyncio.create_task(self._atender_vistos(hay))
        try:
            vigia = await kv.watch(f"{self.persona}.>")
            async for e in vigia:
                if e is None:
                    # lo que había en el bus ya llegó entero: recién ahora `ajenos.json` tiene a todos (antes,
                    # escribirlo con cada clave lo dejaría un rato con una parte, y el resto volvería a la copia)
                    self.ajenos_listos = True
                    await self._espejar()
                    continue
                if not e.value:
                    self.vistos.pop(e.key, None)  # borrado: ese hilo ya no está en ninguna parte
                    self.por_atender.pop(e.key, None)
                    await self._espejar()
                    continue
                try:
                    d = json.loads(e.value)
                except ValueError:
                    continue
                registro = getattr(self, "registro_bus", None)
                if registro is not None and registro.vistas.get(e.key, (None,))[0] != getattr(e, "revision", None):
                    registro.olvidar(e.key)  # alguien más lo escribió (el traspaso): se lee antes de publicar
                propios = getattr(self, "propios", None)
                if propios is None:
                    propios = self.propios = {}
                if (d.get("dueno") or d.get("maquina")) == self.yo:
                    propios[e.key] = d
                    self.vistos.pop(e.key, None)
                    self.por_atender.pop(e.key, None)
                    await self._espejar()
                    continue
                propios.pop(e.key, None)
                self.vistos[e.key] = d
                await self._espejar()
                self.por_atender.pop(e.key, None)  # al final de la fila: el orden es el de los cambios
                self.por_atender[e.key] = d
                hay.set()
            # el vigía terminó (en una prueba; en el bus no termina): lo que quedó se atiende antes de irse
            self.por_atender_fin = True
            hay.set()
            await trabajador
        finally:
            trabajador.cancel()

    async def _atender_vistos(self, hay: asyncio.Event) -> None:
        """Lo que dejó el vigía, de a un hilo, con lo último que publicó cada uno."""
        while True:
            await hay.wait()
            hay.clear()
            while self.por_atender:
                await self._atender_visto(self.por_atender.pop(next(iter(self.por_atender))))
            if getattr(self, "por_atender_fin", False):
                return

    async def _atender_visto(self, d: dict) -> None:
        """Lo de un hilo de otra máquina que cambió: su atención, anotada aquí, y su ventana."""
        from datetime import datetime

        from telar import estado as mod_estado
        from telar.modelo import Atencion

        def anotar_aqui():
            est = mod_estado.abrir(self.config)
            if d.get("nombre") not in est.remotos():
                return
            try:
                atencion = Atencion(d.get("atencion") or "ninguna")
                desde = datetime.fromisoformat(d["desde"]) if d.get("desde") else None
            except ValueError:
                return
            est.anotar_atencion(d["nombre"], atencion, desde)

        try:
            await asyncio.to_thread(anotar_aqui)
        except Exception as e:  # noqa: BLE001 - un estado que no se pudo escribir no tumba al vigía
            self.anotar(f"«{d.get('nombre')}»: la atención no se anotó: {type(e).__name__}: {e}")
        try:
            await asyncio.to_thread(self.ventana_de, d)
        except Exception as e:  # noqa: BLE001 - una ventana que no se pudo abrir o cerrar no tumba al vigía
            self.anotar(f"«{d.get('nombre')}»: {type(e).__name__}: {e}")

    async def _espejar(self) -> None:
        """`espejar_ajenos` desde el vigía, cuando ya llegó lo del arranque. Un archivo que no se pudo
        escribir no lo tumba: se anota, y el evento siguiente lo intenta de nuevo."""
        if not self.ajenos_listos:
            return
        try:
            await asyncio.to_thread(self.espejar_ajenos)
        except Exception as e:  # noqa: BLE001 - disco lleno, permisos: el vigía sigue
            self.anotar(f"ajenos.json: {type(e).__name__}: {e}")

    def espejar_ajenos(self) -> bool:
        """Deja en `ajenos.json` lo último que publicó cada hilo de las otras máquinas (lo que hay en
        `vistos`), entero: la lista y la página leen de ahí el vínculo, el archivo y la conversación de un
        hilo ajeno, sin copia que mantener. Devuelve si escribió."""
        ajenos = {}
        for d in self.vistos.values():
            nombre = d.get("nombre")
            if not isinstance(nombre, str) or not nombre or not d.get("maquina"):
                continue
            ajenos[nombre] = {k: d[k] for k in CAMPOS_AJENOS if k in d}
        if ajenos == self.ajenos_escritos:
            return False
        mod_estado.abrir(self.config).guardar_ajenos(ajenos)
        self.ajenos_escritos = ajenos
        return True

    def conciliar(self) -> list[str]:
        """Las ventanas de aquí de los hilos que viven en otras máquinas, contra su estado en el bus (lo que
        `_vigilar` va guardando en `vistos`): se trae la de uno vivo allá que aquí no está (salvo archivado),
        y se cierra la de uno que allá ya no vive. Devuelve los nombres que tocó."""
        if not self.vistos:
            return []
        tel = _comun.tejer(self.ctx, con_ficha=False)
        if tel.mux is None or not tel.viva:
            return []
        anotados, archivados = tel.estado.remotos(), tel.estado.archivados()
        tocados = []
        for d in list(self.vistos.values()):
            nombre = d.get("nombre", "")
            h = tel.por_nombre(nombre)
            viva = h is not None and tel.vivo(h)
            # archivado: lo que publica su dueño; si no lo publica (un telar de antes), lo de aquí
            archivado = d["archivado"] if isinstance(d.get("archivado"), bool) else nombre in archivados
            falta = bool(d.get("vivo")) and not viva and not archivado
            sobra = not d.get("vivo") and viva and (anotados.get(nombre) or {}).get("remoto") == d.get("maquina")
            if falta or sobra:
                self.ventana_de(d)
                tocados.append(nombre)
        return tocados

    def ventana_de(self, d: dict) -> None:
        """La ventana aquí de un hilo que vive en otra máquina de [remotos]: se trae si nació allá y aquí
        no está, y se cierra si su sesión allá ya no existe (lo que hacía `telar remotos traer`)."""
        from telar import remoto as mod_remoto

        remoto = next((r for r in self.config.remotos if r.nombre == d.get("maquina")), None)
        if remoto is None:
            return
        tel = _comun.tejer(self.ctx, con_ficha=False)
        if tel.mux is None or not tel.viva:
            return
        nombre, sesion = d.get("nombre", ""), d.get("ventana", "")
        anotados = tel.estado.remotos()
        if d.get("vivo"):
            for aqui in {nombre, *(n for n, x in anotados.items() if sesion and x.get("sesion") == sesion)}:
                self._revivir(tel, aqui, d, remoto.nombre)
        hilo = tel.por_nombre(nombre)
        if d.get("vivo") and sesion:
            conocidas = {x.get("sesion") for x in anotados.values() if x.get("sesion")}
            if sesion in conocidas:
                # ya la conocemos: si su ventana se cayó (el laptop durmió, se cortó la red) y el hilo no
                # se archivó a propósito, se vuelve a abrir con el mismo nombre
                aqui = next((n for n, x in anotados.items() if x.get("sesion") == sesion), "")
                if aqui and aqui != nombre and nombre not in anotados and tel.por_nombre(nombre) is None:
                    # se renombró allá: el nombre lo pone la máquina donde vive
                    previo = tel.por_nombre(aqui)
                    if previo is not None and tel.vivo(previo):
                        tel.mux.renombrar(previo.id, nombre)
                    tel.estado.renombrar(aqui, nombre)
                    self.anotar(f"«{aqui}» se llama «{nombre}» en {remoto.nombre}: lo renombré aquí")
                    if previo is not None and tel.vivo(previo):
                        return  # su ventana sigue abierta, ya con el nombre nuevo
                    aqui = nombre
                local = tel.por_nombre(aqui) if aqui else None
                if not aqui or (local is not None and tel.vivo(local)) or aqui in tel.estado.archivados():
                    return
                if not self.puede_reabrir(d, aqui):
                    return
                mod_remoto.traer(tel, remoto, sesion, aqui)
                self.anotar(f"«{aqui}»: su ventana se había cerrado y la sesión sigue en {remoto.nombre}: la reabrí")
                return
            previo = anotados.get(nombre) or {}
            if previo.get("remoto") == remoto.nombre and previo.get("sesion"):
                # el mismo hilo en otra dirección: se reabrió allá. Se sigue a la dirección nueva en vez de
                # traerlo otra vez como «· 2»
                if hilo is not None and tel.vivo(hilo):
                    tel.mux.cerrar(hilo.id)
                if nombre in tel.estado.archivados():
                    tel.estado.anotar_remoto(nombre, remoto.nombre, sesion)
                    return
                mod_remoto.traer(tel, remoto, sesion, nombre)
                self.anotar(f"«{nombre}» cambió de lugar en {remoto.nombre} ({previo['sesion']} → {sesion}): lo sigo")
                return
            # uno que su dueño archivó no nace: es el que se fue de allá (telar.mudanza: se archiva al llegar aquí, un
            # momento antes de cerrar su ventana) o uno que se guardó. Traerlo dejaba aquí una ventana «· 2» que miraba
            # lo que se estaba cerrando
            if d.get("archivado") is True:
                return
            dormidos = {h.nombre for h in tel.hilos if not tel.vivo(h) and h.nombre not in anotados}
            nombres = ({h.nombre for h in tel.hilos} | set(anotados)) - dormidos
            for ses, _, aqui in mod_remoto.nuevas(conocidas, [(sesion, nombre)], nombres):
                mod_remoto.traer(tel, remoto, ses, aqui)
                self.anotar(f"«{aqui}» nació en {remoto.nombre}: traje su ventana")
        elif not d.get("vivo") and hilo is not None and tel.vivo(hilo):
            anotado = anotados.get(nombre) or {}
            if anotado.get("remoto") == remoto.nombre:
                tel.mux.cerrar(hilo.id)
                self.anotar(f"«{nombre}»: su sesión en {remoto.nombre} terminó; cerré la ventana (▶ la retoma)")

    def puede_reabrir(self, d: dict, aqui: str = "", ahora: float | None = None) -> bool:
        """Si se puede reabrir otra vez la ventana de un hilo de otra máquina, y si sí, la cuenta. Con un estado
        viejo en el bus (el hilo murió allá sin que su nodo lo publicara) la ventana que se trae muere en segundos,
        porque allá ya no existe, y sin tope se reabriría en cada vuelta: la barra lo mostraría abierto y cerrado.
        Reabierta REABRIR_TOPE veces en REABRIR_EN segundos, no se reabre más, y se dice una vez. La cuenta vuelve
        a cero cuando cambia su dirección o cuando el hilo publica otra cosa (lo que llega del bus es distinto)."""
        ahora = time.monotonic() if ahora is None else ahora
        nombre, sesion = d.get("nombre", ""), d.get("ventana", "")
        huella = json.dumps(d, ensure_ascii=False, sort_keys=True, default=str)
        r = self.reabiertas.get(nombre)
        if r is None or r["sesion"] != sesion or r["huella"] != huella:
            r = self.reabiertas[nombre] = {"sesion": sesion, "huella": huella, "veces": [], "parada": False}
        if r["parada"]:
            return False
        r["veces"] = [t for t in r["veces"] if ahora - t < REABRIR_EN]
        if len(r["veces"]) >= REABRIR_TOPE:
            r["parada"] = True
            self.anotar(f"«{aqui or nombre}»: reabrí su ventana {len(r['veces'])} veces en {REABRIR_EN // 60} min "
                        f"y se vuelve a cerrar; allá no contesta: no la reabro más (hasta que publique algo nuevo)")
            return False
        r["veces"].append(ahora)
        return True

    def _revivir(self, tel, aqui: str, d: dict, donde: str) -> None:
        """Un hilo archivado aquí, cuyo agente vuelve a trabajar allá, se desarchiva: igual que aquí un
        agente que arranca desarchiva su hilo. Archivarlo fue una decisión, y se respeta mientras allá
        no pase nada nuevo: se compara cuándo se archivó con desde cuándo está su atención en ese estado.
        Sin fecha de archivo (se archivó antes de que se anotara) no se reabre, y se dice."""
        from datetime import datetime

        est = tel.estado
        if "archivado" in est.registro_ajeno().get(aqui, {}):
            # su dueño publica si está archivado (y lo desarchiva allá cuando su agente vuelve). Solo si lo
            # de aquí se lee de eso: uno que aquí se llama distinto («Faro · 2») sigue con su copia
            return
        if aqui not in est.archivados():
            return
        try:
            desde = datetime.fromisoformat(d["desde"]) if d.get("desde") else None
        except ValueError:
            desde = None
        cuando = est.archivado_en(aqui)
        if cuando is None or desde is None or desde.replace(tzinfo=None) <= cuando:
            self.anotar(f"«{aqui}» sigue archivado: en {donde} no hay actividad posterior a cuando se archivó"
                        + ("" if cuando else " (sin fecha de archivo)"))
            return
        est.desarchivar(aqui)
        self.anotar(f"«{aqui}» estaba archivado y en {donde} volvió a trabajar ({d['desde']}): lo desarchivé")

    def foto(self) -> dict | None:
        from telar import __version__, espejo

        try:
            tel = _comun.tejer(self.ctx)
            from telar import dormir

            # lo que se mira aquí, para que la máquina de cada hilo no lo duerma (telar.dormir)
            try:
                mirando = dormir.mirando_de_aqui(self.config, tel)
            except Exception as e:  # noqa: BLE001 - sin eso, la foto de siempre (allá cuentan como mirados)
                self.anotar(f"lo que se mira aquí: {type(e).__name__}: {e}")
                mirando = None
            return espejo.foto(tel, maquina=self.yo, version_telar=__version__, web=self.web, mirando=mirando,
                               vista=dormir.sufijo_vista(), agentes=espejo.agentes_de(self.config))
        except Exception as e:  # noqa: BLE001
            self.anotar(f"la foto del espejo no salió: {type(e).__name__}: {e}")
            return None

    async def _vigilar_espejo(self) -> None:
        """Las fotos de las otras máquinas, guardadas donde las lee el panel (telar.espejo).

        Como el vigía del estado, solo recibe: guardar cada foto (un archivo) lo hace otra tarea, con la
        última de cada máquina. Una cola de nats-py que se atrasa es la de `kv.watch`, que nats-py arma con
        sus límites de fábrica y que telar no puede cambiar: lo que la mantiene corta es vaciarla al tiro."""
        from telar import espejo

        por_guardar: dict[str, str] = {}
        hay, fin = asyncio.Event(), []

        async def guardar() -> None:
            while True:
                await hay.wait()
                hay.clear()
                while por_guardar:
                    de = next(iter(por_guardar))
                    valor = por_guardar.pop(de)
                    try:
                        await asyncio.to_thread(espejo.guardar, self.config, de, valor)
                    except Exception as x:  # noqa: BLE001 - una foto rota se ignora: el espejo queda con la anterior
                        self.anotar(f"la foto de {de} no se guardó: {x}")
                if fin:
                    return

        trabajador = asyncio.create_task(guardar())
        try:
            vigia = await self.espejo.watch(f"{self.persona}.>")
            async for e in vigia:
                if e is None or not e.value:
                    continue
                de = e.key.split(".", 1)[-1]
                if de == self.yo:
                    continue
                por_guardar.pop(de, None)  # al final de la fila: el orden es el de los cambios
                por_guardar[de] = e.value.decode()
                hay.set()
            # el vigía terminó (en una prueba; en el bus no termina): lo que quedó se guarda antes de irse
            fin.append(True)
            hay.set()
            await trabajador
        finally:
            trabajador.cancel()

    # ── pedidos con respuesta ────────────────────────────────────────────────────

    async def _correo(self, m) -> None:
        """Un correo de otra persona para un hilo de esta: a la casilla del hilo, como cualquier mensaje."""
        from telar import entre_personas

        try:
            info = json.loads((m.headers or {}).get("Nats-Request-Info", "{}"))
            c = entre_personas.correo(json.loads(m.data or b"{}"), str(info.get("acc") or ""))
            if c["persona"] == self.persona:
                raise entre_personas.CorreoInvalido("entre tus hilos se escribe con telar mensaje")
            if await self._hilo_existe(c["para"]) is False:
                raise entre_personas.CorreoInvalido(f"{self.persona} no tiene un hilo «{c['para']}»")
            msg = mod_bus.mensaje(c["texto"], de=c["de"], para=c["para"], tipo="correo", persona=c["persona"])
            # `para` ya es la palabra de su casilla (la del directorio): se usa tal cual
            await self.js.publish(mod_bus.tema_casilla(self.config, c["para"], ficha_=c["para"]),
                                  json.dumps(msg, ensure_ascii=False).encode(), headers={"Nats-Msg-Id": msg["id"]})
            # con id, como la de `telar mensaje` (telar.bus.enviar): si se repite, el bus la descarta
            await self.js.publish(f"registro.{self.persona}", json.dumps({**msg, "estado": "enviado"},
                                                                          ensure_ascii=False).encode(),
                                  headers={"Nats-Msg-Id": f"{msg['id']}.enviado"})
            self.anotar(f"correo de {c['persona']} para «{c['para']}» ({msg['id']})")
            respuesta = {"ok": True, "id": msg["id"]}
        except (entre_personas.CorreoInvalido, ValueError) as e:
            respuesta = {"ok": False, "error": str(e)}
        except Exception as e:  # noqa: BLE001 - quien escribe se entera; el nodo sigue
            respuesta = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        await m.respond(json.dumps(respuesta, ensure_ascii=False).encode())

    async def _admin(self, m) -> None:
        """Una acción de gestión de personas (telar.personas), de esta persona o de un admin."""
        from telar import personas

        r = await asyncio.to_thread(personas.atender_pedido_del_bus, self.persona, m.data, m.headers)
        if r.get("hecho"):
            self.anotar(f"personas: {r['hecho']} (lo pidió {r.get('quien') or self.persona})")
        await m.respond(json.dumps(r, ensure_ascii=False).encode())

    async def _alojar(self, m) -> None:
        """Una acción de alojamiento (telar.alojamiento): una persona del bus pide un lugar en este servidor, o
        quien lo administra decide."""
        from telar import alojamiento

        r = await asyncio.to_thread(alojamiento.atender_pedido_del_bus, self.persona, m.data, m.headers, self.config)
        if r.get("hecho"):
            self.anotar(f"alojamiento: {r['hecho']} (lo pidió {r.get('quien') or self.persona})")
        await m.respond(json.dumps(r, ensure_ascii=False).encode())

    async def _hilo_existe(self, ext: str) -> bool | None:
        """Si esta persona tiene un hilo **público** con esa palabra (en el estado del bus, de cualquier máquina
        suya): a uno privado no le llega correo de otra persona, y se contesta lo mismo que si no existiera, para
        que no se sepa que está. None si no se pudo saber: entonces se acepta, y espera en la casilla."""
        try:
            entrada = await self.kv.get(f"{self.persona}.{ext}")
        except Exception as e:  # noqa: BLE001
            return False if type(e).__name__ in ("KeyNotFoundError", "KeyDeletedError") else None
        try:
            return json.loads(entrada.value or b"{}").get("publico") is True
        except (ValueError, AttributeError):
            return False

    async def _directorio(self, m) -> None:
        """El directorio que publicó otra persona: se guarda, para `telar directorio` y para escribirle."""
        from telar import entre_personas

        persona = m.subject.split(".", 1)[-1]
        if persona == self.persona:
            return
        try:
            await asyncio.to_thread(entre_personas.guardar, self.config, persona, json.loads(m.data or b"{}"))
        except Exception as e:  # noqa: BLE001 - uno roto se ignora: queda el anterior
            self.anotar(f"el directorio de {persona} no se guardó: {e}")

    async def _ping(self, m) -> None:
        from telar import __version__

        await m.respond(json.dumps({"ok": True, "maquina": self.yo, "telar": __version__}).encode())

    async def _leer(self, m) -> None:
        from telar import historia

        def leer():
            pedido = json.loads(m.data or b"{}")
            tel = _comun.tejer(self.ctx, con_ficha=False)
            hilo = tel.por_nombre(str(pedido.get("hilo", "")))
            if hilo is None or historia.vetado(historia.no_leer(self.config), hilo.nombre,
                                               tel.estado.vinculos().get(hilo.nombre, "")):
                return {"ok": False, "error": f"aquí no hay un hilo «{pedido.get('hilo', '')}» que se pueda leer"}
            return {"ok": True, "historia": historia.leer(self.ctx, tel, hilo, int(pedido.get("ultimos") or 5))}

        try:
            r = await asyncio.to_thread(leer)
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        await m.respond(mod_bus.empacar(r, mod_bus.maximo_de(m)))


    async def _responder_pregunta(self, m) -> None:
        """Contestar la pregunta abierta de un hilo de aquí (telar.historia.responder), desde la página de otra máquina.
        Lo que no se puede leer desde otra (`[bus] no_leer`) tampoco se contesta."""
        from telar import historia

        def responder(pedido: dict) -> dict:
            tel = _comun.tejer(self.ctx, con_ficha=False)
            hilo = tel.por_nombre(str(pedido.get("hilo", "")))
            if hilo is None or historia.vetado(historia.no_leer(self.config), hilo.nombre,
                                               tel.estado.vinculos().get(hilo.nombre, "")):
                return {"ok": False, "codigo": 404, "error": f"aquí no hay un hilo «{pedido.get('hilo', '')}» que se pueda contestar"}
            try:
                return historia.responder(self.config, hilo.nombre, str(pedido.get("id", "")), pedido.get("respuestas") or {})
            except historia.ErrorDeRespuesta as e:
                return {"ok": False, "codigo": e.codigo, "error": str(e)}

        await self._responder(m, responder)

    async def _responder(self, m, hacer) -> None:
        try:
            pedido = json.loads(m.data or b"{}")
            r = await asyncio.to_thread(hacer, pedido)
        except Exception as e:  # noqa: BLE001 - un pedido roto se responde con su error
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        # la grande (todas las tareas, con su texto) va comprimida: sin eso no salía, y el otro esperaba hasta su plazo
        await m.respond(mod_bus.empacar(r, mod_bus.maximo_de(m)))

    async def _codigos(self, m) -> None:
        """Los códigos de un hilo de aquí (telar.servicios.codigos), para la página de otra máquina."""
        from telar.servicios import codigos

        await self._responder(m, lambda p: codigos.para_otra(self.ctx, p))

    async def _contexto(self, m) -> None:
        """Lo que carga el contexto de un hilo de aquí (telar.servicios.carga), para la página de otra máquina."""
        from telar.servicios import carga

        await self._responder(m, lambda p: carga.para_otra(self.ctx, p))

    async def _resultado(self, m) -> None:
        from telar import resultados

        await self._responder(m, lambda p: resultados.local(self.config, str(p.get("clave", "")), str(p.get("dia", ""))))

    async def _resultado_comentar(self, m) -> None:
        from telar import resultados

        await self._responder(m, lambda p: resultados.comentar_local(
            self.config, str(p.get("clave", "")), str(p.get("dia", "")), str(p.get("texto", ""))))

    async def _resultado_agregar(self, m) -> None:
        """Pasadas de un resultado que vive aquí (telar.pasadas), mandadas desde otra máquina: se agregan aquí."""
        from telar import pasadas

        await self._responder(m, lambda p: pasadas.agregar_local(
            self.config, str(p.get("clave", "")), p.get("pasadas"), saltar_repetidas=bool(p.get("saltar_repetidas")),
            nombres=p.get("nombres")))

    async def _resultado_visto(self, m) -> None:
        from telar import pasadas

        await self._responder(m, lambda p: pasadas.marcar_visto_local(self.config, str(p.get("clave", "")), str(p.get("id", "")),
                                                                     str(p.get("mundo", "") or "")))

    async def _resultado_sin_ver(self, m) -> None:
        from telar import pasadas

        # clasificadas aquí, con la configuración y las tareas de aquí
        await self._responder(m, lambda p: pasadas.sin_ver_local(self.config, str(p.get("clave", "")), ctx=self.ctx))

    async def _cambio(self, m) -> None:
        """Algo cambió en alguna máquina (`telar cambio`): se anota aquí para que el dashboard lo relea, y salen
        los disparadores que lo esperan (telar.disparadores)."""
        from telar.ordenes import cambio

        tema = m.subject.rsplit(".", 1)[-1]
        if tema and tema.replace("-", "").isalnum():
            await asyncio.to_thread(cambio.anotar, self.config, tema)
            despacho = self._despacho()
            if despacho:
                self._disparar(despacho.llego(tema, asyncio.get_running_loop().time()))

    # ── los disparadores de cambio y el estado deseado ──────────────────────────

    def _despacho(self):
        """El despacho de los disparadores de cambio de esta máquina, armado la primera vez (con lo que dice la
        configuración al arrancar: uno nuevo pide reiniciar el nodo)."""
        despacho = getattr(self, "despacho", None)
        if despacho is None:
            from telar import disparadores

            despacho = self.despacho = disparadores.Despacho(disparadores.de_cambio(self.config, getattr(self, "yo", "")))
        return despacho

    def _disparar(self, salen) -> None:
        """Corre cada disparador que salió, en su tarea, y anota lo que el freno tenga que decir."""
        despacho = self._despacho()
        for aviso in despacho.avisos:
            self.anotar(aviso)
        despacho.avisos.clear()
        if not hasattr(self, "disparos"):
            self.disparos = set()
        for d in salen:
            t = asyncio.create_task(self._correr_disparador(d))
            self.disparos.add(t)
            t.add_done_callback(self.disparos.discard)

    async def _correr_disparador(self, d) -> None:
        """Uno de cambio, corrido como un periódico (telar.periodicos.correr), en un hilo suyo: un comando largo no
        deja al nodo sin hilos para sus vueltas. El hilo es daemon, y no de un ThreadPoolExecutor: Python espera a
        los de un grupo al salir, y un `sleep 600` hacía esperar diez minutos al detener el nodo. Cuántos corren a
        la vez ya lo cuida el despacho (`disparadores.A_LA_VEZ`)."""
        from telar import disparadores

        try:
            r = await _en_hilo_suelto(disparadores.correr, self.ctx, d, nombre=f"disparador-{d.nombre}")
            self.anotar(f"disparador «{d.nombre}» ({d.al}): {r.get('resultado', '')}")
        except Exception as e:  # noqa: BLE001 - uno que falla no tumba el nodo
            self.anotar(f"disparador «{d.nombre}» ({d.al}): {type(e).__name__}: {e}")
        finally:
            self._despacho().termino(d.nombre)
            # lo que quedó pendiente mientras corría sale ahora, sin esperar la vuelta
            self._disparar(self._despacho().listos(asyncio.get_running_loop().time()))

    #: lo más seguido que un hijo le avisa a su padre que terminó un turno (segundos): uno que conversa con la persona
    #: termina muchos turnos seguidos, y al padre le basta saber que avanzó
    AVISO_PADRE_CADA = 10 * 60

    def avisar_padres(self, locales: dict, ahora: float | None = None) -> list[str]:
        """Los hilos de aquí que cuelgan de otro y acaban de terminar un turno (pasaron de trabajando a terminó o a te
        espera): le dejan a su padre un aviso con lo último que dijeron. Devuelve a quiénes avisó."""
        import time

        ahora = ahora if ahora is not None else time.time()
        antes = getattr(self, "atencion_antes", None)
        self.atencion_antes = {n: str(i.get("atencion") or "") for n, i in locales.items()}
        if antes is None:
            return []  # la primera vuelta solo mira: un nodo que arranca no avisa de turnos viejos
        if not hasattr(self, "avisados_padre"):
            self.avisados_padre: dict[str, float] = {}
        from telar.ordenes import hilo as orden_hilo
        from telar.ordenes import mensaje

        est = mod_estado.abrir(self.config)
        avisados = []
        for nombre, at in self.atencion_antes.items():
            if antes.get(nombre) != "trabajando" or at not in ("termino", "espera"):
                continue
            padre = orden_hilo.padre_de(est, nombre)
            if not padre or padre == nombre or ahora - self.avisados_padre.get(nombre, 0) < self.AVISO_PADRE_CADA:
                continue
            self.avisados_padre[nombre] = ahora
            dijo = self._lo_ultimo(est, nombre)
            que = "terminó un turno y te espera" if at == "espera" else "terminó un turno"
            texto = f"«{nombre}», tu hilo hijo, {que}." + (f" Lo último que dijo:\n\n{dijo}" if dijo else "") + \
                f"\n\n(Más: `telar hilo leer \"{nombre}\"`; escríbele con `telar mensaje \"{nombre}\" \"…\"`.)"
            try:
                mensaje.enviar(self.ctx, padre, texto, modo="aviso", de=nombre)
                avisados.append(nombre)
            except Exception as e:  # noqa: BLE001 - un aviso que no salió no frena la vuelta
                self.anotar(f"«{nombre}» no pudo avisarle a «{padre}»: {e}")
        return avisados

    def _lo_ultimo(self, est, hilo: str, tope: int = 600) -> str:
        """Lo último que dijo el agente de `hilo` en su conversación, recortado."""
        from telar import conversacion

        try:
            _, mensajes, _ = conversacion.mensajes_del_hilo(self.config, list(est.sesiones().get(hilo) or ()))
        except Exception:  # noqa: BLE001 - sin conversación que leer, el aviso va sin cita
            return ""
        texto = next((str(m.get("texto") or "") for m in reversed(mensajes) if m.get("quien") == "agente"), "").strip()
        return texto if len(texto) <= tope else texto[:tope].rstrip() + "…"

    def mirar_confiar(self) -> list[str]:
        """Los hilos de aquí detenidos en la pregunta de Claude Code de confiar en una carpeta (telar.confiar): quedan
        esperando a la persona, y lo que cambió va al registro. Nunca la contesta. Devuelve lo que cambió."""
        from telar import confiar

        cambios = confiar.mirar(self.config, _comun.tejer(self.ctx, con_ficha=False))
        for linea in cambios:
            self.anotar(linea)
        return cambios

    def mirar_dormir(self) -> list[str]:
        """Los hilos de aquí que llevan `[hilos] dormir_tras` quietos se duermen (telar.dormir); lo que pasó va al
        registro. Devuelve lo que cambió."""
        from telar import dormir

        cambios = dormir.mirar(self.config, _comun.tejer(self.ctx, con_ficha=False))
        for linea in cambios:
            self.anotar(linea)
        return cambios

    def mirar_deseado(self, locales: dict) -> None:
        """Los residentes de aquí sin sesión: una línea al registro cuando cambia, y `deseado.json` para doctor."""
        from telar import deseado

        if getattr(self, "residentes", None) is None:
            self.residentes = deseado.Residentes()
        sin_sesion = deseado.residentes_sin_sesion(locales)
        for linea in self.residentes.mirar(sin_sesion):
            self.anotar(linea)
        deseado.escribir(self.config, self.yo, sin_sesion, residentes=deseado.residentes(locales))
        # los que están para siempre (`residente = "siempre"`) se abren: al arrancar la máquina, o si se cerraron
        self.abrir_los_de_siempre(sin_sesion)

    #: cuánto se espera para volver a abrir a uno que está para siempre y se cerró (segundos): uno que se cae al
    #: abrirse no se reabre en bucle
    REABRIR_CADA = 10 * 60

    def abrir_los_de_siempre(self, sin_sesion, ahora: float | None = None) -> list[str]:
        """Abre, retomando callada su conversación, a los residentes de aquí con `residente = "siempre"` que no
        tienen sesión. A lo más uno cada REABRIR_CADA por agente. Devuelve los que abrió."""
        import time

        from telar import encargos

        ahora = ahora if ahora is not None else time.time()
        if not hasattr(self, "abiertos_siempre"):
            self.abiertos_siempre: dict[str, float] = {}
        abiertos = []
        for a in self._agentes_de_aqui():
            if a.presencia != "siempre" or a.nombre not in sin_sesion:
                continue
            if ahora - self.abiertos_siempre.get(a.clave, 0) < self.REABRIR_CADA:
                continue
            self.abiertos_siempre[a.clave] = ahora
            try:
                encargos._abrir(self.ctx, a, "")
                abiertos.append(a.nombre)
                self.anotar(f"«{a.nombre}» está para siempre y no tenía sesión: abierto")
            except Exception as e:  # noqa: BLE001 - la próxima vez se intenta de nuevo
                self.anotar(f"«{a.nombre}» está para siempre y no pude abrirlo: {e}")
        return abiertos

    async def _proveedor(self, m) -> None:
        """Lo que da un proveedor de esta máquina, para otra que lo declara `en` esta (telar.alla)."""
        from telar import alla

        await self._responder(m, lambda p: alla.consultar_aqui(self.config, str(p.get("nombre", "")), str(p.get("dia", ""))))

    async def _tarea(self, m) -> None:
        """`telar tarea …` corrido aquí, para otra máquina: la ficha o una acción de una tarea de aquí."""
        from telar import alla

        def correr(p):
            argv = p.get("argv")
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                return {"ok": False, "error": "argv: se esperaba una lista de textos"}
            return alla.tarea_aqui(argv)

        await self._responder(m, correr)

    async def _encargo(self, m) -> None:
        """Un encargo que vive aquí (telar.encargo), pedido desde otra máquina: `{id}` lo devuelve, y con `accion`
        se la aplica (aceptar, rechazar, cerrar). En fila: una acción lee y reescribe su archivo."""
        from telar import encargo

        await self._responder(m, lambda p: encargo.atender(self.ctx, p))

    async def _agentes(self, m) -> None:
        """Los agentes que viven aquí con su estado (telar.servicios.agentes), para la página de otra máquina; con
        `rotar`, rotar ya la conversación de uno; con `eliminar`, eliminarlo (sus hilos al archivo, su carpeta aparte)."""
        from telar.servicios import ErrorDeServicio
        from telar.servicios import agentes as servicio

        def hacer(p):
            try:
                if p.get("rotar"):
                    return servicio.rotar_aqui(self.ctx, str(p["rotar"]))
                if p.get("abrir"):
                    return servicio.abrir_aqui(self.ctx, str(p["abrir"]))
                if p.get("eliminar"):
                    return servicio.eliminar_aqui(self.ctx, str(p["eliminar"]))
                return {"ok": True, "agentes": servicio.estado_local(self.ctx)}
            except ErrorDeServicio as e:
                return {"ok": False, "error": str(e), "codigo": e.codigo}

        await self._responder(m, hacer)

    async def _tipo(self, m) -> None:
        """`telar tipo …` corrido aquí, para otra máquina: leer, crear o cambiar los objetos de un tipo que
        viven aquí (telar.servicios.tipos)."""
        from telar import alla

        def correr(p):
            argv = p.get("argv")
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                return {"ok": False, "error": "argv: se esperaba una lista de textos"}
            return alla.tarea_aqui(argv, "tipo")

        await self._responder(m, correr)

    async def _periodicos(self, m) -> None:
        """`telar periodicos …` corrido aquí, para otra máquina que declara `[periodicos] en` esta."""
        from telar import alla

        def correr(p):
            argv = p.get("argv")
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                return {"ok": False, "error": "argv: se esperaba una lista de textos"}
            return alla.tarea_aqui(argv, "periodicos")

        await self._responder(m, correr)

    async def _hilo(self, m) -> None:
        """`telar hilo <verbo>` sobre un hilo que vive aquí, pedido desde otra máquina: el dueño aplica el
        cambio y lo vuelve a publicar (docs/propuestas/un-dueno-por-hilo.md). Solo los verbos que cambian su
        registro, nunca llevar ni retomar."""
        from telar import alla
        from telar.ordenes.hilo import AL_DUENO

        def correr(p):
            argv = p.get("argv")
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                return {"ok": False, "error": "argv: se esperaba una lista de textos"}
            # y retomar: uno archivado en otra máquina que es de esta se retoma aquí (telar.seguir, «retomar» de allá)
            if not argv or argv[0] not in (*AL_DUENO, "retomar"):
                return {"ok": False, "error": f"hilo: solo {', '.join(AL_DUENO)} y retomar"}
            return alla.tarea_aqui(argv, "hilo")

        await self._responder(m, correr)

    async def _hilo_llegar(self, m) -> None:
        """Un hilo que otra máquina de esta persona trae aquí (`telar hilo llevar`, por el bus): su conversación ya
        llegó a la carpeta de entrada; se deja donde el agente la busca y el hilo se abre retomándola (telar.mudanza)."""
        from telar import mudanza

        await self._responder(m, lambda p: mudanza.llegar(self.ctx, p))

    async def _hilo_revisar(self, m) -> None:
        """Otra máquina de esta persona pregunta, antes de traer un hilo aquí, si se puede: qué fallaría y qué llegaría
        a medias (telar.mudanza.revisar). No mueve nada."""
        from telar import mudanza

        await self._responder(m, lambda p: mudanza.revisar(self.ctx, p))

    async def _hilo_hijo(self, m) -> None:
        """Otra máquina le lleva una tarea a un agente que vive aquí: un hilo hijo suyo para ella (telar.hijos)."""
        from telar import hijos
        from telar.servicios import ErrorDeServicio

        def abrir(p):
            try:
                return hijos.abrir_aqui(self.ctx, str(p.get("agente") or ""), str(p.get("hilo") or ""), str(p.get("ref") or ""),
                                        str(p.get("texto") or ""))
            except ErrorDeServicio as e:
                return {"ok": False, "error": str(e), "codigo": e.codigo}

        await self._responder(m, abrir)

    async def _hilo_despertar(self, m) -> None:
        """Otra máquina pide despertar a un hilo de aquí (telar.alcance): uno dormido, en su ventana; uno cerrado o
        archivado, retomado con su conversación (le llegó un mensaje, o lo pidió la persona desde allá); uno despierto
        queda como está. `texto`, su primer mensaje. Responde {ok, hecho, estaba}: un telar de antes respondía {ok}
        solo, y así lo reconoce quien pide."""
        from telar import alcance

        await self._responder(m, lambda p: alcance.despertar_aqui(self.ctx, str(p.get("hilo") or ""),
                                                                 str(p.get("texto") or "")))

    async def _hilo_traer(self, m) -> None:
        """Otra máquina de esta persona pide para sí un hilo que vive aquí («traer a esta máquina»): se le lleva con
        `telar hilo llevar` (telar.mudanza.traer_aqui)."""
        from telar import mudanza

        await self._responder(m, lambda p: mudanza.traer_aqui(self.ctx, p))

    async def _mudanza_progreso(self, m) -> None:
        """Otra máquina que pidió traer un hilo de aquí sigue su mudanza: en qué va (telar.mudanza.progreso_de)."""
        from telar import mudanza

        await self._responder(m, lambda p: {"ok": True, "progreso": mudanza.progreso_de(self.config,
                                                                                         str(p.get("hilo") or ""))})

    async def _replica_estado(self, m) -> None:
        """Otra máquina va a mandar una conversación aquí: qué hay de cada archivo suyo (telar.replica.estado)."""
        from telar import replica

        await self._responder(m, lambda p: replica.estado(self.ctx, p))

    async def _replica_escribir(self, m) -> None:
        """Un pedazo de una conversación que llega (telar.replica.escribir): bytes crudos detrás de una línea JSON, no
        un pedido JSON. De a uno y en orden (`en_fila`): cada uno va al final del anterior."""
        from telar import replica

        def escribir() -> dict:
            try:
                meta, datos = replica.recibir(m.data or b"")
            except ValueError as e:
                return {"ok": False, "error": f"un pedazo sin cabecera: {e}"}
            return replica.escribir(self.config, meta, datos)

        try:
            r = await asyncio.to_thread(escribir)
        except Exception as e:  # noqa: BLE001 - un pedazo que falla se responde con su error
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        await m.respond(mod_bus.empacar(r, mod_bus.maximo_de(m)))

    async def _replica_cerrar(self, m) -> None:
        """Una conversación que terminó de llegar: verificarla y dejarla donde Claude la busca (telar.replica.cerrar)."""
        from telar import replica

        await self._responder(m, lambda p: replica.cerrar(self.ctx, p))

    async def _equipo(self, m) -> None:
        """`telar equipo …` corrido aquí, para otra máquina: la bandeja del equipo vive donde están las tareas.
        Nunca `servir` ni `token`: solo leer la bandeja y decidirla."""
        from telar import alla

        def correr(p):
            argv = p.get("argv")
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                return {"ok": False, "error": "argv: se esperaba una lista de textos"}
            if not argv or argv[0] not in ("sugerencias", "aceptar", "rechazar", "existe", "revisando"):
                return {"ok": False, "error": "equipo: solo la bandeja y sus decisiones"}
            return alla.tarea_aqui(argv, "equipo")

        await self._responder(m, correr)

    async def _avisos_archivo(self, m) -> None:
        """Los avisos que vienen de un archivo de esta máquina (telar.avisos), para la página de otra: solo los que la
        configuración de aquí declara como suyos."""
        from telar import avisos

        await self._responder(m, lambda p: avisos.para_otra(self.config, p))

    async def _avisos_visto(self, m) -> None:
        """Dar por visto un aviso de un archivo de esta máquina, que pide la página de otra (telar.avisos): solo uno que
        la configuración de aquí declara."""
        from telar import avisos

        await self._responder(m, lambda p: avisos.visto_para_otra(self.config, p))

    async def _aviso(self, m) -> None:
        """Un aviso en la pantalla de esta máquina, que manda otra (telar.entrega)."""
        from telar import entrega

        await self._responder(m, entrega.recibir_aviso)

    async def _archivo(self, m) -> None:
        """Un archivo que manda otra máquina, a la carpeta de entrada de esta (telar.entrega)."""
        from telar import entrega

        await self._responder(m, lambda p: entrega.recibir_archivo(self.config, p))

    async def _archivo_leer(self, m) -> None:
        """Un archivo de aquí que pide leer otra máquina (el visor de su página), con los límites de aquí."""
        from telar.servicios import archivos

        await self._responder(m, lambda p: archivos.leer_para_otra(self.ctx, p))

    async def _borradores(self, m) -> None:
        """Los borradores de un hilo de aquí (telar.servicios.borradores), que pide la página de otra máquina: verlos,
        escribirlos, borrarlos o mandárselos a su hilo, que vive aquí."""
        from telar.servicios import borradores

        await self._responder(m, lambda p: borradores.para_otra(self.ctx, p))

    def soltar_borradores(self, locales: dict) -> list[str]:
        """Los hilos de aquí con un borrador en espera cuyo agente ya terminó (telar.borradores): el evento de fin de
        turno lo suelta al tiro; esto es el respaldo, por si un turno terminó sin evento. Devuelve a cuáles les escribió."""
        from telar import borradores

        hechos = []
        for nombre in borradores.pendientes(self.config):
            if nombre not in locales or str(locales[nombre].get("atencion") or "") in ("trabajando", "espera"):
                continue
            como = borradores.soltar(self.config, _comun.tejer(self.ctx, con_ficha=False), nombre, pausa=0)
            if como:
                hechos.append(nombre)
                self.anotar(f"«{nombre}»: terminó su turno y le dejé su borrador en espera ({como})")
        return hechos

    async def _comentarios(self, m) -> None:
        """Los comentarios de un archivo de aquí (telar.servicios.comentarios), que pide la página de otra máquina o un
        agente de allá: leerlos o cambiarlos, con los límites de aquí. El archivo de al lado se commitea al rato, aquí."""
        from telar.servicios import comentarios

        await self._responder(m, lambda p: comentarios.para_otra(self.ctx, p))

    async def _modulo(self, m) -> None:
        """Una consulta a un módulo instalado aquí, que pide otra máquina (telar.servicios.modulos)."""
        from telar.servicios import modulos

        await self._responder(m, lambda p: modulos.para_otra(self.ctx, p))

    async def _notas(self, m) -> None:
        from telar import notas

        await self._responder(m, lambda p: notas.leer_local(self.config, str(p.get("dia", ""))))

    async def _nota(self, m) -> None:
        from telar import notas

        await self._responder(m, lambda p: notas.agregar_local(
            self.config, str(p.get("dia", "")), str(p.get("evento", "")), str(p.get("texto", "")),
            de=str(p.get("de", "")), titulo=str(p.get("titulo", "")), inicio=str(p.get("inicio", ""))))


    async def _serie(self, m) -> None:
        from telar import reuniones

        await self._responder(m, lambda p: {"ok": True, "destino": reuniones.recordado_local(self.config, str(p.get("titulo", "")))})

    async def _serie_recordar(self, m) -> None:
        from telar import reuniones

        def hacer(p):
            reuniones.recordar_local(self.config, str(p.get("titulo", "")), str(p.get("destino", "")))
            return {"ok": True}

        await self._responder(m, hacer)


# para `python -m telar.ordenes.nodo` en una prueba
if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:], None))
