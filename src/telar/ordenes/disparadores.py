"""`telar disparadores` — lo que corre o manda algo solo: por un reloj, una tecla o un cambio.

    telar disparadores                  la lista: cuándo, qué y la última corrida
    telar disparadores --json           el contrato (docs/contratos.md)
    telar disparadores correr <nombre>  correr ya uno de reloj o de cambio, y esperar (para probarlo)

Se declaran en la configuración, `[disparadores.<nombre>]`, con una de `cuando` (un horario cron), `tecla` (una
del dashboard) o `al = "cambio:<tema>"` (cuando alguna máquina anuncia `telar cambio <tema>`), y un `comando` o
un `mensaje` (telar.disparadores, docs/configuracion.md). Los de reloj corren desde el crontab, como los de
`telar periodicos` (donde también se ven); los de tecla son atajos (`telar atajo`); los de cambio los corre el
nodo de la máquina donde corren los periódicos.
"""

from __future__ import annotations

from telar import disparadores as mod
from telar.ordenes import _comun

AYUDA = "Lo que corre o manda algo solo: por un reloj, una tecla o un cambio."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("disparadores", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", default="ver", choices=("ver", "correr"))
    p.add_argument("nombre", nargs="?", default="", help="con correr: cuál")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    todos = tuple(getattr(ctx.config, "disparadores", ()))

    if o.verbo == "correr":
        d = next((x for x in todos if x.nombre == o.nombre), None) if o.nombre else None
        if d is None:
            hay = ", ".join(x.nombre for x in todos) or "ninguno: [disparadores.<nombre>] en la configuración"
            return _comun.queja(f"no hay un disparador «{o.nombre}» (hay: {hay})")
        if d.tipo == "tecla":
            return _comun.queja(f"«{d.nombre}» es la tecla «{d.tecla}»: telar atajo {d.tecla}")
        r = mod.correr(ctx, d)
        if o.json:
            return _comun.escribir_json({"nombre": d.nombre, **r})
        print(f"{d.nombre}: {r['resultado']}")
        return 0 if r["codigo"] == 0 else 1

    datos = lista(ctx, todos)
    if o.json:
        return _comun.escribir_json(datos)
    if not todos:
        print(_comun.tenue("no hay disparadores: se declaran en la configuración, [disparadores.<nombre>]"))
        return 0
    for d in datos["disparadores"]:
        marca = "⏸" if not d["activo"] else ("✗" if d["ultima"].get("codigo") not in (None, 0) else "●")
        cuando = {"reloj": d["cuando"], "tecla": f"tecla {d['tecla']}", "cambio": d["al"]}[d["tipo"]]
        que = d["mensaje"] and (f"✦ {d['mensaje']}" + (f" → {d['agente']}" if d["agente"] else "")) or d["comando"]
        print(f"{marca} {d['nombre']:<20} {cuando:<18} {que}")
        detalle = []
        if d["proxima"]:
            detalle.append(f"próxima {d['proxima'][5:16].replace('T', ' ')}")
        if d["ultima"].get("inicio"):
            detalle.append(f"última {d['ultima']['inicio'][5:16].replace('T', ' ')} · {d['ultima'].get('resultado', 'corriendo')}")
        if detalle:
            print(_comun.tenue("    " + " · ".join(detalle)))
    if not datos["corren_aqui"] and any(d["tipo"] != "tecla" for d in datos["disparadores"]):
        print(_comun.tenue(f"los de reloj y de cambio corren donde corren los periódicos ({ctx.config.periodicos_en}),"
                           " con la configuración de allá"))
    return 0


def lista(ctx, todos) -> dict:
    """Lo que imprime `telar disparadores --json`."""
    from telar import bus as mod_bus
    from telar import periodicos

    try:
        zona = periodicos.leer(periodicos.ruta(ctx.config.origen)).zona
    except periodicos.ErrorDePeriodicos:
        zona = ""
    salida = []
    for d in todos:
        proxima = ""
        if d.tipo == "reloj":
            try:
                sig = periodicos.proxima(d.proceso(), zona)
                proxima = sig.isoformat(timespec="minutes") if sig else ""
            except periodicos.ErrorDePeriodicos:
                proxima = ""
        salida.append({"nombre": d.nombre, "tipo": d.tipo, "cuando": d.cuando, "tecla": d.tecla, "al": d.al,
                       "tema": d.tema, "comando": d.comando, "mensaje": d.mensaje, "agente": d.agente, "hilo": d.hilo,
                       "max_abiertos": d.max_abiertos, "argumentos": list(d.argumentos), "carpeta": d.carpeta,
                       "descripcion": d.descripcion, "aparece": d.aparece, "activo": d.activo, "proxima": proxima,
                       "ultima": periodicos.ultima(ctx.config, d.nombre) if d.tipo != "tecla" else {}})
    return {"maquina": mod_bus.maquina(ctx.config), "corren_aqui": mod.corren_aqui(ctx.config),
            "disparadores": salida}
