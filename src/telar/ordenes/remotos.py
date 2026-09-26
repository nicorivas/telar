"""`telar remotos` — las sesiones de hilo que hay en cada máquina de [remotos].

    telar remotos                 cuáles hay allá, y cuáles telar todavía no conoce
    telar remotos traer           abrir aquí una ventana para cada una que no conoce
    telar remotos traer --json

Un hilo remoto casi siempre nace aquí (`telar hilo llevar`, «nuevo hilo remoto»). Pero
también puede nacer allá: un reloj que abre una pasada de trabajo en el servidor, una
sesión empezada desde el celular. Si sigue la convención (una sesión tmux `telar-…` con su
nombre en `@telar_hilo`), `traer` la suma a la lista como cualquier hilo remoto, sin
quitarle el foco a nadie. La extensión de VS Code lo corre sola cada pocos minutos.
"""

from __future__ import annotations

from telar import remoto as mod_remoto
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Las sesiones de hilo de cada máquina remota, y traer las que nacieron allá."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("remotos", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", choices=("traer",), help="traer: abrir aquí las que no conoce")
    p.add_argument("--remoto", default="", help="solo esa máquina de [remotos]")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    remotos = [r for r in ctx.config.remotos if not o.remoto or r.nombre == o.remoto]
    if not remotos:
        return _comun.queja("no hay máquinas en [remotos]" if not o.remoto else f"no hay remoto «{o.remoto}»")

    tel = _comun.tejer(ctx, con_ficha=False)
    conocidas = {d["sesion"] for d in tel.estado.remotos().values() if d.get("sesion")}
    nombres = {h.nombre for h in tel.hilos} | set(tel.estado.remotos())
    datos, traidos = [], []
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
        datos.append({"remoto": r.nombre, "error": error,
                      "sesiones": [{"sesion": s, "hilo": h, "conocida": s in conocidas} for s, h in de_alla]})
    if traidos:
        from telar import directorio as mod_directorio

        for nombre in {t["remoto"] for t in traidos}:
            mod_directorio.publicar_callado(ctx, tel, nombre)

    if o.json:
        return _comun.escribir_json({"remotos": datos, "traidos": traidos})
    for d in datos:
        print(_comun.fuerte(d["remoto"]) + (f"  {_comun.tenue(d['error'])}" if d["error"] else ""))
        for s in d["sesiones"]:
            print(f"  {s['hilo']}  " + _comun.tenue(s["sesion"] + ("" if s["conocida"] else "  · nueva")))
    for t in traidos:
        print(f"traído: {t['hilo']} ({t['remoto']})")
    return 0
