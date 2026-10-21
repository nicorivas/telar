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
3. **Su estado**: publica de cada uno la máquina, la atención, desde cuándo y su conversación, solo si
   cambió. Y escucha el de los demás: la atención de un hilo que vive en otra máquina se anota aquí al
   instante, sin sondeo.

También atiende pedidos con respuesta: `leer` (los últimos turnos de un hilo de aquí) y `ping`.
Necesita `[bus] url` en la configuración y el extra «bus» de telar (nats-py).
"""

from __future__ import annotations

import asyncio
import json
import sys

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
        self.publicado: dict[str, str] = {}
        self.vueltas = 0
        #: cuántas vueltas seguidas falta un hilo que estaba vivo (se anuncia muerto a la segunda)
        self.ausentes: dict[str, int] = {}
        self.espejo = None
        #: el último estado de cada hilo de las otras máquinas, por su clave del bus (lo llena `_vigilar`)
        self.vistos: dict[str, dict] = {}

    def anotar(self, texto: str) -> None:
        from datetime import datetime

        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}", flush=True)

    # ── qué vive aquí (sincrónico: tmux, archivos) ──────────────────────────────

    def locales(self) -> dict[str, dict]:
        from telar import agentes as mod_agentes

        tel = _comun.tejer(self.ctx, con_ficha=False)
        est = tel.estado
        remotos = est.remotos()
        atenciones = est.atenciones()
        sesiones = est.sesiones()
        salida: dict[str, dict] = {}

        from telar import movil

        try:
            propias = movil.propios()
        except Exception:  # noqa: BLE001 - sin tmux no hay sesiones propias
            propias = {}
        try:
            # la dirección de cada ventana de la sesión del telar («@338/marca»): con ella otra máquina
            # la mira (telar.remoto.guion_ver). Listarlas también les pone marca a las que no tienen
            direcciones = {v.ventana: v.direccion for v in movil.ventanas(self.config.sesion)}
        except Exception:  # noqa: BLE001 - sin tmux no hay ventanas que mirar desde afuera
            direcciones = {}

        def ficha_de(nombre: str, vivo: bool, residente: str = "", ventana: str = "") -> dict:
            atencion, desde = atenciones.get(nombre, (None, None))
            return {"nombre": nombre, "maquina": self.yo, "vivo": vivo, "residente": residente,
                    "atencion": atencion.value if atencion else "ninguna",
                    "desde": desde.isoformat(timespec="seconds") if desde else "",
                    "conversacion": (sesiones.get(nombre) or ("",))[0],
                    # dónde mirarlo desde otra máquina: su ventana en la sesión del telar, o la sesión
                    # tmux propia de antes (remotos)
                    "ventana": ventana,
                    "sesion_tmux": propias.get(nombre, "")}

        for h in tel.hilos:
            if h.nombre in remotos:
                continue  # su ventana está aquí, pero vive en otra máquina: lo publica esa
            if tel.vivo(h) or tel.propio(h):
                salida[h.nombre] = ficha_de(h.nombre, True, ventana=direcciones.get(h.id, "") if tel.vivo(h) else "")
        # una sesión propia que telar todavía no registró (la abrió un periódico, el celular, otra
        # máquina) también vive aquí: sin esto, la otra máquina no se entera de que nació
        for nombre in propias:
            if nombre not in salida and nombre not in remotos:
                salida[nombre] = ficha_de(nombre, True)
        for a in mod_agentes.descubrir(self.config):
            if (a.en or self.config.agentes_en) not in ("", "aqui"):
                continue
            actual = salida.get(a.nombre) or ficha_de(a.nombre, False)
            actual["residente"] = a.clave
            salida[a.nombre] = actual
        return salida

    def avisar(self, nombre: str, info: dict) -> str:
        """Que el hilo se entere de lo que llegó a su casilla, sin teclear el contenido."""
        from telar import agentes as mod_agentes
        from telar import casilla, encargos
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        est = mod_estado.abrir(self.config)
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
        return "en su casilla, hasta que se abra"

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

    async def correr(self, *, una_vez: bool = False) -> None:
        nc = await mod_bus.conectar(self.config, para_siempre=not una_vez)
        # los pedidos al bus de este proceso (la API, en `telar serve --nodo`) van por esta conexión
        mod_bus.registrar_conexion(nc, asyncio.get_running_loop())
        js = nc.jetstream()
        await mod_bus.asegurar(js)
        kv = await js.key_value(mod_bus.ESTADO)
        self.kv, self.js = kv, js
        self.espejo = await js.key_value(mod_bus.ESPEJO)
        self.anotar(f"en el bus como {self.persona}@{self.yo} ({self.config.bus.url})")
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "ping"), cb=self._ping)
        # entre personas (telar.entre_personas): el correo que le escriben a esta persona (lo atiende un
        # solo nodo suyo: cola «correo») y los directorios de las demás
        from telar import cuentas

        self.nc = nc
        await nc.subscribe(cuentas.CORREO.format(self.persona), queue="correo", cb=self._correo)
        await nc.subscribe(cuentas.DIRECTORIO.format("*"), cb=self._directorio)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "leer"), cb=self._leer)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "resultado"), cb=self._resultado)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "resultado-comentar"), cb=self._resultado_comentar)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "proveedor"), cb=self._proveedor)
        await nc.subscribe(mod_bus.tema_cambio(self.config, "*"), cb=self._cambio)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "tarea"), cb=self._tarea)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "tipo"), cb=self._tipo)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "periodicos"), cb=self._periodicos)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "hilo"), cb=self._hilo)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "equipo"), cb=self._equipo)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "aviso"), cb=self._aviso)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "archivo"), cb=self._archivo)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "archivo-leer"), cb=self._archivo_leer)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "notas"), cb=self._notas)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "nota"), cb=self._nota)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "serie"), cb=self._serie)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "serie-recordar"), cb=self._serie_recordar)
        vigia = None if una_vez else asyncio.create_task(self._vigilar(kv))
        vigia_espejo = None if una_vez else asyncio.create_task(self._vigilar_espejo())
        try:
            while True:
                try:
                    await self._vuelta(js, kv)
                except Exception as e:  # noqa: BLE001 - una vuelta que falla no tumba el nodo
                    self.anotar(f"vuelta con error: {type(e).__name__}: {e}")
                if una_vez:
                    break
                await asyncio.sleep(VUELTA)
        finally:
            for t in (vigia, vigia_espejo):
                if t:
                    t.cancel()
            mod_bus.registrar_conexion(None, None)
            await nc.close()

    async def _vuelta(self, js, kv) -> None:
        from telar import casilla

        locales = await asyncio.to_thread(self.locales)
        # casillas: una suscripción durable por hilo que vive aquí
        for nombre in locales:
            f = mod_bus.ficha(nombre)
            if f not in self.subs:
                self.subs[f] = await js.pull_subscribe(mod_bus.tema_casilla(self.config, nombre),
                                                       durable=f"c-{self.persona}-{f}", stream=mod_bus.STREAM)
        for f in [f for f in self.subs if f not in {mod_bus.ficha(n) for n in locales}]:
            del self.subs[f]  # se fue a otra máquina: que lo recoja aquella
        for nombre, info in locales.items():
            sub = self.subs[mod_bus.ficha(nombre)]
            try:
                msgs = await sub.fetch(20, timeout=0.3)
            except Exception:  # noqa: BLE001 - sin mensajes, fetch termina por tiempo
                continue
            nuevos = 0
            for m in msgs:
                try:
                    datos = json.loads(m.data)
                    if casilla.dejar(self.config, nombre, datos):
                        nuevos += 1
                except ValueError:
                    self.anotar(f"«{nombre}»: un mensaje que no es JSON, descartado")
                await m.ack()
            if nuevos:
                dicho = await asyncio.to_thread(self.avisar, nombre, info)
                self.anotar(f"«{nombre}»: {nuevos} mensaje(s) · {dicho}")
        # estado: solo lo que cambió, y que dejó de estar vivo lo que ya no está aquí
        from datetime import datetime

        actuales = dict(locales)
        for clave, valor in list(self.publicado.items()):
            previo = json.loads(valor)
            if previo["nombre"] not in actuales and previo.get("vivo"):
                # muerto solo si falta dos vueltas seguidas: una lectura de tmux que falla una vez
                # no tiene por qué anunciarle a la otra máquina que el hilo se fue
                self.ausentes[previo["nombre"]] = self.ausentes.get(previo["nombre"], 0) + 1
                if self.ausentes[previo["nombre"]] < 2:
                    actuales[previo["nombre"]] = previo
                    continue
                actuales[previo["nombre"]] = {**previo, "vivo": False, "atencion": "ninguna", "sesion_tmux": "", "ventana": ""}
        for nombre in locales:
            self.ausentes.pop(nombre, None)
        # cada 30 s, quiénes están vivos aquí: si tmux se cae, `telar hilo caidos` sabe qué reabrir
        if self.vueltas % 15 == 0:
            vivos = [n for n, i in locales.items() if i.get("vivo")]
            await asyncio.to_thread(lambda: mod_estado.abrir(self.config).anotar_vivos(vivos))
        for nombre, info in actuales.items():
            valor = json.dumps(info, ensure_ascii=False, sort_keys=True)
            clave = mod_bus.clave_estado(self.config, nombre)
            if self.publicado.get(clave) != valor:
                await kv.put(clave, json.dumps({**info, "actualizado": datetime.now().astimezone().isoformat(timespec="seconds")},
                                               ensure_ascii=False).encode())
                self.publicado[clave] = valor
        # la foto del espejo, cada tanto: la que muestra el panel en la otra máquina
        self.vueltas += 1
        if self.vueltas % ESPEJO_CADA == 1:
            foto = await asyncio.to_thread(self.foto)
            if foto is not None:
                await self.espejo.put(f"{self.persona}.{self.yo}", json.dumps(foto, ensure_ascii=False).encode())
                # y el directorio, para las demás personas: solo nombres, carpetas y una línea
                from telar import cuentas, entre_personas

                await self.nc.publish(cuentas.DIRECTORIO.format(self.persona), json.dumps(
                    entre_personas.directorio(foto, self.persona), ensure_ascii=False).encode())
            # y las ventanas de los hilos de las otras máquinas, contra lo que dice el bus: un evento perdido,
            # o una ventana cerrada aquí sin cambio allá, se corrige aquí (un dueño por hilo, paso 2)
            try:
                await asyncio.to_thread(self.conciliar)
            except Exception as e:  # noqa: BLE001 - la vuelta siguiente lo intenta de nuevo
                self.anotar(f"conciliar las ventanas: {type(e).__name__}: {e}")

    async def _vigilar(self, kv) -> None:
        """La atención de los hilos que viven en otra máquina, anotada aquí apenas cambia."""
        from datetime import datetime

        from telar import estado as mod_estado
        from telar.modelo import Atencion

        vigia = await kv.watch(f"{self.persona}.>")
        async for e in vigia:
            if e is None:
                continue
            if not e.value:
                self.vistos.pop(e.key, None)  # borrado: ese hilo ya no está en ninguna parte
                continue
            try:
                d = json.loads(e.value)
            except ValueError:
                continue
            if d.get("maquina") == self.yo:
                self.vistos.pop(e.key, None)
                continue
            self.vistos[e.key] = d

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

            await asyncio.to_thread(anotar_aqui)
            try:
                await asyncio.to_thread(self.ventana_de, d)
            except Exception as e:  # noqa: BLE001 - una ventana que no se pudo abrir o cerrar no tumba al vigía
                self.anotar(f"«{d.get('nombre')}»: {type(e).__name__}: {e}")

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
            falta = bool(d.get("vivo")) and not viva and nombre not in archivados
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
        nombre, sesion = d.get("nombre", ""), d.get("ventana") or d.get("sesion_tmux", "")
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
                mod_remoto.traer(tel, remoto, sesion, aqui)
                self.anotar(f"«{aqui}»: su ventana se había cerrado y la sesión sigue en {remoto.nombre}: la reabrí")
                return
            previo = anotados.get(nombre) or {}
            if previo.get("remoto") == remoto.nombre and previo.get("sesion"):
                # el mismo hilo en otra dirección: pasó de sesión propia a ventana, o se reabrió allá. Se
                # sigue a la dirección nueva en vez de traerlo otra vez como «· 2»
                if hilo is not None and tel.vivo(hilo):
                    tel.mux.cerrar(hilo.id)
                if nombre in tel.estado.archivados():
                    tel.estado.anotar_remoto(nombre, remoto.nombre, sesion)
                    return
                mod_remoto.traer(tel, remoto, sesion, nombre)
                self.anotar(f"«{nombre}» cambió de lugar en {remoto.nombre} ({previo['sesion']} → {sesion}): lo sigo")
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

    def _revivir(self, tel, aqui: str, d: dict, donde: str) -> None:
        """Un hilo archivado aquí, cuyo agente vuelve a trabajar allá, se desarchiva: igual que aquí un
        agente que arranca desarchiva su hilo. Archivarlo fue una decisión, y se respeta mientras allá
        no pase nada nuevo: se compara cuándo se archivó con desde cuándo está su atención en ese estado.
        Sin fecha de archivo (se archivó antes de que se anotara) no se reabre, y se dice."""
        from datetime import datetime

        est = tel.estado
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
            return espejo.foto(tel, maquina=self.yo, version_telar=__version__, web=self.web)
        except Exception as e:  # noqa: BLE001
            self.anotar(f"la foto del espejo no salió: {type(e).__name__}: {e}")
            return None

    async def _vigilar_espejo(self) -> None:
        """Las fotos de las otras máquinas, guardadas donde las lee el panel (telar.espejo)."""
        from telar import espejo

        vigia = await self.espejo.watch(f"{self.persona}.>")
        async for e in vigia:
            if e is None or not e.value:
                continue
            de = e.key.split(".", 1)[-1]
            if de == self.yo:
                continue
            try:
                await asyncio.to_thread(espejo.guardar, self.config, de, e.value.decode())
            except Exception as x:  # noqa: BLE001 - una foto rota se ignora: el espejo queda con la anterior
                self.anotar(f"la foto de {de} no se guardó: {x}")

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
            await self.js.publish(mod_bus.tema_casilla(self.config, c["para"]),
                                  json.dumps(msg, ensure_ascii=False).encode(), headers={"Nats-Msg-Id": msg["id"]})
            await self.js.publish(f"registro.{self.persona}", json.dumps({**msg, "estado": "enviado"},
                                                                          ensure_ascii=False).encode())
            self.anotar(f"correo de {c['persona']} para «{c['para']}» ({msg['id']})")
            respuesta = {"ok": True, "id": msg["id"]}
        except (entre_personas.CorreoInvalido, ValueError) as e:
            respuesta = {"ok": False, "error": str(e)}
        except Exception as e:  # noqa: BLE001 - quien escribe se entera; el nodo sigue
            respuesta = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        await m.respond(json.dumps(respuesta, ensure_ascii=False).encode())

    async def _hilo_existe(self, ext: str) -> bool | None:
        """Si esta persona tiene un hilo con esa palabra (en el estado del bus, de cualquier máquina suya).
        None si no se pudo saber: entonces se acepta, y espera en la casilla."""
        try:
            await self.kv.get(f"{self.persona}.{ext}")
            return True
        except Exception as e:  # noqa: BLE001
            return False if type(e).__name__ in ("KeyNotFoundError", "KeyDeletedError") else None

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
        await m.respond(json.dumps(r, ensure_ascii=False).encode())


    async def _responder(self, m, hacer) -> None:
        try:
            pedido = json.loads(m.data or b"{}")
            r = await asyncio.to_thread(hacer, pedido)
        except Exception as e:  # noqa: BLE001 - un pedido roto se responde con su error
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        await m.respond(json.dumps(r, ensure_ascii=False).encode())

    async def _resultado(self, m) -> None:
        from telar import resultados

        await self._responder(m, lambda p: resultados.local(self.config, str(p.get("clave", "")), str(p.get("dia", ""))))

    async def _resultado_comentar(self, m) -> None:
        from telar import resultados

        await self._responder(m, lambda p: resultados.comentar_local(
            self.config, str(p.get("clave", "")), str(p.get("dia", "")), str(p.get("texto", ""))))

    async def _cambio(self, m) -> None:
        """Algo cambió en alguna máquina (`telar cambio`): se anota aquí para que el dashboard lo relea."""
        from telar.ordenes import cambio

        tema = m.subject.rsplit(".", 1)[-1]
        if tema and tema.replace("-", "").isalnum():
            await asyncio.to_thread(cambio.anotar, self.config, tema)

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
            if not argv or argv[0] not in AL_DUENO:
                return {"ok": False, "error": f"hilo: solo {', '.join(AL_DUENO)}"}
            return alla.tarea_aqui(argv, "hilo")

        await self._responder(m, correr)

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
