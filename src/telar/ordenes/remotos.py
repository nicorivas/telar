"""`telar remotos` — las sesiones de hilo que hay en cada máquina de [remotos].

    telar remotos                 cuáles hay allá, y cuáles telar todavía no conoce
    telar remotos traer           abrir aquí una ventana para cada una que no conoce
    telar remotos traer --json
    telar remotos atencion        copiar aquí el semáforo de los hilos remotos (trabajando, espera…)

Un hilo remoto casi siempre nace aquí (`telar hilo llevar`, «nuevo hilo remoto»). Pero
también puede nacer allá: un reloj que abre una pasada de trabajo en el servidor, una
sesión empezada desde el celular. Si sigue la convención (una sesión tmux `telar-…` con su
nombre en `@telar_hilo`), `traer` la suma a la lista como cualquier hilo remoto, sin
quitarle el foco a nadie. La extensión de VS Code lo corre sola cada pocos minutos.

`traer` también cierra aquí las ventanas **fantasma**: las de un hilo remoto cuya sesión ya no existe
allá (la cerró el tope de `[agente] max_vivos`, o alguien desde el celular). La ventana mostraría una
pantalla congelada; el hilo conserva su conversación y vuelve con `telar hilo retomar` (▶). Solo se
hace con la lista de sesiones de allá en la mano: si la otra máquina no responde, no se toca nada.
"""

from __future__ import annotations

from telar import remoto as mod_remoto
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Las sesiones de hilo de cada máquina remota, y traer las que nacieron allá."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("remotos", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", choices=("traer", "atencion"),
                   help="traer: abrir aquí las que no conoce; atencion: traer su semáforo")
    p.add_argument("--remoto", default="", help="solo esa máquina de [remotos]")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    p.add_argument("--sondeo", action="store_true",
                   help="traer: lo pide un sondeo periódico; con bus no hace nada (lo hace `telar nodo` al instante)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    from telar import bus as mod_bus

    if o.sondeo and o.verbo == "traer" and mod_bus.hay_bus(ctx.config):
        if o.json:
            return _comun.escribir_json({"remotos": [], "traidos": [], "cerrados": [], "por": "bus"})
        return 0
    remotos = [r for r in ctx.config.remotos if not o.remoto or r.nombre == o.remoto]
    if not remotos:
        return _comun.queja("no hay máquinas en [remotos]" if not o.remoto else f"no hay remoto «{o.remoto}»")

    if o.verbo == "atencion":
        return _atencion(ctx, remotos, o.json)

    tel = _comun.tejer(ctx, con_ficha=False)
    conocidas = {d["sesion"] for d in tel.estado.remotos().values() if d.get("sesion")}
    # un hilo dormido de aquí con el mismo nombre que una sesión de allá es el mismo hilo que se mudó
    # (`telar hilo llevar`, un agente que pasó al servidor): se adopta su nombre en vez de crear «· 2»
    dormidos = {h.nombre for h in tel.hilos if not tel.vivo(h) and h.nombre not in tel.estado.remotos()}
    nombres = ({h.nombre for h in tel.hilos} | set(tel.estado.remotos())) - dormidos
    datos, traidos, cerrados = [], [], []
    for r in remotos:
        de_alla, error = mod_remoto.sesiones(r)
        faltan = mod_remoto.nuevas(conocidas, de_alla, nombres)
        nombres |= {aqui for _, _, aqui in faltan}
        if o.verbo == "traer" and faltan:
            if tel.mux is None or not tel.viva:
                return _comun.queja(tel.aviso or "la sesión no está viva: primero telar tejer")
            for sesion, _, aqui in faltan:
                try:
                    mod_remoto.traer(tel, r, sesion, aqui)
                    traidos.append({"remoto": r.nombre, "sesion": sesion, "hilo": aqui})
                except ErrorDeMux as e:
                    error = error or f"no pude abrir «{aqui}»: {e}"
        if o.verbo == "traer" and not error and tel.mux is not None:
            alla = {s for s, _ in de_alla}
            for h in tel.hilos:
                anotado = tel.estado.remotos().get(h.nombre) or {}
                if anotado.get("remoto") != r.nombre or not anotado.get("sesion") or anotado["sesion"] in alla:
                    continue
                if not tel.vivo(h):
                    continue
                try:
                    tel.mux.cerrar(h.id)
                    cerrados.append({"remoto": r.nombre, "sesion": anotado["sesion"], "hilo": h.nombre})
                except ErrorDeMux as e:
                    error = error or f"no pude cerrar la ventana fantasma de «{h.nombre}»: {e}"
        datos.append({"remoto": r.nombre, "error": error,
                      "sesiones": [{"sesion": s, "hilo": h, "conocida": s in conocidas} for s, h in de_alla]})
    if traidos:
        from telar import directorio as mod_directorio

        for nombre in {t["remoto"] for t in traidos}:
            mod_directorio.publicar_callado(ctx, tel, nombre)

    if o.json:
        return _comun.escribir_json({"remotos": datos, "traidos": traidos, "cerrados": cerrados})
    for d in datos:
        print(_comun.fuerte(d["remoto"]) + (f"  {_comun.tenue(d['error'])}" if d["error"] else ""))
        for s in d["sesiones"]:
            print(f"  {s['hilo']}  " + _comun.tenue(s["sesion"] + ("" if s["conocida"] else "  · nueva")))
    for t in traidos:
        print(f"traído: {t['hilo']} ({t['remoto']})")
    for c in cerrados:
        print(f"cerrada la ventana de {c['hilo']}: su sesión ya no existe en {c['remoto']} (▶ la retoma)")
    return 0


def _atencion(ctx, remotos, como_json: bool) -> int:
    """Copia aquí el semáforo de los hilos remotos: sus ganchos corren allá y aquí nadie se entera.

    Solo toca los hilos que viven en esa máquina; lo que allá no está anotado queda en «ninguna»."""
    from datetime import datetime

    from telar import estado as mod_estado
    from telar.modelo import Atencion

    from telar import bus as mod_bus

    if mod_bus.hay_bus(ctx.config):
        # con bus, el nodo de esta máquina ya anota la atención de los remotos apenas cambia
        return _comun.escribir_json({"cambios": [], "errores": [], "bus": True, "por": "bus"}) if como_json else 0
    est = mod_estado.abrir(ctx.config)
    actuales = est.atenciones()
    cambios, errores = [], []
    for r in remotos:
        alla, error = mod_remoto.atenciones(r)
        if alla is None:
            errores.append(error)
            continue
        for hilo, anotado in est.remotos().items():
            if anotado.get("remoto") != r.nombre:
                continue
            cuerpo = alla.get(hilo) or {}
            try:
                nueva = Atencion(cuerpo.get("atencion", "ninguna"))
            except ValueError:
                nueva = Atencion.NINGUNA
            try:
                desde = datetime.fromisoformat(cuerpo["desde"]) if cuerpo.get("desde") else None
            except ValueError:
                desde = None
            vieja, vieja_desde = actuales.get(hilo, (Atencion.NINGUNA, None))
            if nueva != vieja or (desde and desde != vieja_desde):
                est.anotar_atencion(hilo, nueva, desde)
                cambios.append({"hilo": hilo, "atencion": nueva.value})
    if como_json:
        return _comun.escribir_json({"cambios": cambios, "errores": errores})
    for c in cambios:
        print(f"{c['hilo']}: {c['atencion']}")
    for e in errores:
        print(_comun.tenue(e))
    return 0
