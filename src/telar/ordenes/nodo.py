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
from telar.ordenes import _comun

AYUDA = "Esta máquina en el bus: recibe lo suyo, avisa a sus hilos y publica su estado."

#: cada cuánto se miran los hilos de aquí, las casillas y el estado
VUELTA = 2.0


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
        return _comun.queja("no hay bus: [bus] url en la configuración (docs/propuestas/bus.md)")
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
    def __init__(self, ctx):
        self.ctx = ctx
        self.config = ctx.config
        self.yo = mod_bus.maquina(self.config)
        self.persona = mod_bus.persona(self.config)
        self.subs: dict[str, object] = {}
        self.publicado: dict[str, str] = {}

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

        def ficha_de(nombre: str, vivo: bool, residente: str = "") -> dict:
            atencion, desde = atenciones.get(nombre, (None, None))
            return {"nombre": nombre, "maquina": self.yo, "vivo": vivo, "residente": residente,
                    "atencion": atencion.value if atencion else "ninguna",
                    "desde": desde.isoformat(timespec="seconds") if desde else "",
                    "conversacion": (sesiones.get(nombre) or ("",))[0]}

        for h in tel.hilos:
            if h.nombre in remotos:
                continue  # su ventana está aquí, pero vive en otra máquina: lo publica esa
            if tel.vivo(h) or tel.propio(h):
                salida[h.nombre] = ficha_de(h.nombre, True)
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
            if est.atencion(nombre) == Atencion.TRABAJANDO:
                return "trabajando: se lo entrega Stop"
            escribir(casilla.AVISO)
            est.anotar_atencion(nombre, Atencion.TRABAJANDO)
            return "avisado"
        if info.get("residente"):
            agente = next((a for a in mod_agentes.descubrir(self.config) if a.clave == info["residente"]), None)
            if agente is not None:
                encargos._abrir(self.ctx, agente, casilla.AVISO)
                return "abierto"
        return "en su casilla, hasta que se abra"

    # ── el bucle ─────────────────────────────────────────────────────────────────

    async def correr(self, *, una_vez: bool = False) -> None:
        nc = await mod_bus.conectar(self.config, para_siempre=not una_vez)
        js = nc.jetstream()
        await mod_bus.asegurar(js)
        kv = await js.key_value(mod_bus.ESTADO)
        self.anotar(f"en el bus como {self.persona}@{self.yo} ({self.config.bus.url})")
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "ping"), cb=self._ping)
        await nc.subscribe(mod_bus.tema_rpc(self.config, self.yo, "leer"), cb=self._leer)
        vigia = None if una_vez else asyncio.create_task(self._vigilar(kv))
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
            if vigia:
                vigia.cancel()
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
        # estado: solo lo que cambió
        from datetime import datetime

        for nombre, info in locales.items():
            valor = json.dumps(info, ensure_ascii=False, sort_keys=True)
            clave = mod_bus.clave_estado(self.config, nombre)
            if self.publicado.get(clave) != valor:
                await kv.put(clave, json.dumps({**info, "actualizado": datetime.now().astimezone().isoformat(timespec="seconds")},
                                               ensure_ascii=False).encode())
                self.publicado[clave] = valor

    async def _vigilar(self, kv) -> None:
        """La atención de los hilos que viven en otra máquina, anotada aquí apenas cambia."""
        from datetime import datetime

        from telar import estado as mod_estado
        from telar.modelo import Atencion

        vigia = await kv.watch(f"{self.persona}.>")
        async for e in vigia:
            if e is None or not e.value:
                continue
            try:
                d = json.loads(e.value)
            except ValueError:
                continue
            if d.get("maquina") == self.yo:
                continue

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

    # ── pedidos con respuesta ────────────────────────────────────────────────────

    async def _ping(self, m) -> None:
        from telar import __version__

        await m.respond(json.dumps({"ok": True, "maquina": self.yo, "telar": __version__}).encode())

    async def _leer(self, m) -> None:
        from telar import historia

        def leer():
            pedido = json.loads(m.data or b"{}")
            tel = _comun.tejer(self.ctx, con_ficha=False)
            hilo = tel.por_nombre(str(pedido.get("hilo", "")))
            if hilo is None:
                return {"ok": False, "error": f"aquí no hay un hilo «{pedido.get('hilo', '')}»"}
            return {"ok": True, "historia": historia.leer(self.ctx, tel, hilo, int(pedido.get("ultimos") or 5))}

        try:
            r = await asyncio.to_thread(leer)
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        await m.respond(json.dumps(r, ensure_ascii=False).encode())


# para `python -m telar.ordenes.nodo` en una prueba
if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:], None))
