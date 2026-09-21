"""`telar tiempo` — cuánto estuvo arriba cada hilo, medido por el foco.

Cada cambio de foco se anota como una línea (`ISO<TAB>hilo`) y abre un intervalo
que cierra la siguiente. De ahí sale el tiempo por hilo y por día:

    telar tiempo                       hoy
    telar tiempo --semana              la semana en curso, abierta por día
    telar tiempo --desde 2026-09-01 --hasta 2026-09-07
    telar tiempo --por-carpeta         sumando los hilos que miran la misma carpeta
    telar tiempo marcar                anotar que el foco está aquí ahora

`marcar` es el gancho: lo llama el multiplexor o la barra cada vez que cambia el
tab, y no anota nada si el foco no cambió. Sin ese gancho, telar solo ve los
cambios que pasaron por `telar ir`, y el total miente por abajo.

Un intervalo sin cambio de foco se recorta a `intervalos.foco_maximo` (una hora,
por defecto): nadie avisa cuando se va del computador, y sin recorte una noche
entera queda anotada como trabajo.
"""

from __future__ import annotations

import datetime as dt

from telar import estado as mod_estado
from telar.ordenes import _comun

AYUDA = "Cuánto estuvo arriba cada hilo, medido por el foco."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("tiempo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", choices=("ver", "marcar"), default="ver")
    p.add_argument("hilo", nargs="?", default="", help="con marcar: cuál (por defecto, este)")
    p.add_argument("--semana", action="store_true", help="la semana en curso")
    p.add_argument("--desde", default="", metavar="AAAA-MM-DD")
    p.add_argument("--hasta", default="", metavar="AAAA-MM-DD")
    p.add_argument("--tope", type=float, default=0.0, metavar="MIN", help="recorte, en minutos")
    p.add_argument("--por-carpeta", action="store_true", help="sumar los hilos de la misma carpeta")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    est = mod_estado.abrir(ctx.config)
    if o.verbo == "marcar":
        return _marcar(ctx, est, o)

    try:
        desde, hasta = _rango(o)
    except ValueError as e:
        return _comun.queja(str(e))

    tope = o.tope * 60 if o.tope else ctx.config.intervalos.foco_maximo
    if tope <= 0:
        return _comun.queja("el tope tiene que ser positivo")

    try:
        lineas = est.ruta(mod_estado.FOCO).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lineas = []
    marcas = mod_estado.marcas_desde(lineas)
    por_hilo = mod_estado.tiempo_por_hilo(marcas, tope, desde=desde, hasta=hasta)
    por_dia = mod_estado.tiempo_por_dia(marcas, tope, desde=desde, hasta=hasta)
    if o.por_carpeta:
        por_hilo = mod_estado.agrupar(por_hilo, est.vinculos())

    if o.json:
        return _comun.escribir_json(
            {
                "desde": desde.isoformat(),
                "hasta": hasta.isoformat(),
                "tope": tope,
                "unidad": "segundos",
                "agrupado": "carpeta" if o.por_carpeta else "hilo",
                "total": round(sum(por_hilo.values()), 1),
                "hilos": {k: round(v, 1) for k, v in por_hilo.items()},
                "dias": {
                    d.isoformat(): {k: round(v, 1) for k, v in valores.items()}
                    for d, valores in por_dia.items()
                },
            }
        )

    if not por_hilo:
        print(_comun.tenue(f"sin registro entre {desde} y {hasta}."))
        print(_comun.tenue("  el foco lo anota `telar tiempo marcar`, desde el multiplexor."))
        return 0

    total = sum(por_hilo.values())
    cuando = "hoy" if desde == hasta == dt.date.today() else f"{desde} → {hasta}"
    print(
        _comun.fuerte(f"{cuando}  ·  {_comun.duracion(total) or '< 1 min'}")
        + _comun.tenue(f"  ·  tope {int(tope // 60)} min por intervalo")
    )
    vinculos = est.vinculos()
    for nombre, segundos in por_hilo.items():
        detalle = "" if o.por_carpeta else vinculos.get(nombre, "")
        reloj = _comun.duracion(segundos) or "—"
        print(f"  {reloj:>6}  {nombre[:22]:<22} {_comun.tenue(detalle)}")
    if len(por_dia) > 1:
        print()
        for dia, valores in por_dia.items():
            arriba = sorted(valores.items(), key=lambda kv: -kv[1])[:4]
            resumen = ", ".join(f"{h} {_comun.duracion(s)}" for h, s in arriba)
            total_dia = _comun.duracion(sum(valores.values()))
            print(f"  {dia} {dia.strftime('%a')}  {total_dia:>6}  {_comun.tenue(resumen)}")
    return 0


def _marcar(ctx, est, o) -> int:
    tel = _comun.tejer(ctx, con_ficha=False) if not o.hilo else None
    if o.hilo:
        nombre = o.hilo
    else:
        actual = _comun.hilo_actual(tel)
        if actual is None:
            return _comun.queja(
                f"no sé qué hilo tiene el foco: exporta ${_comun.VARIABLE_HILO}"
                " o pásalo: telar tiempo marcar <hilo>"
            )
        nombre = actual.nombre
    cambio = est.marcar(nombre)
    if o.json:
        return _comun.escribir_json({"hilo": nombre, "anotado": cambio})
    print(f"«{nombre}»" + ("" if cambio else _comun.tenue("  (ya lo tenía: nada que anotar)")))
    return 0


def _rango(o) -> tuple[dt.date, dt.date]:
    hoy = dt.date.today()
    if o.semana:
        lunes = hoy - dt.timedelta(days=hoy.weekday())
        return lunes, lunes + dt.timedelta(days=6)
    try:
        desde = dt.date.fromisoformat(o.desde) if o.desde else hoy
        hasta = dt.date.fromisoformat(o.hasta) if o.hasta else (desde if o.desde else hoy)
    except ValueError as e:
        raise ValueError(f"fecha que no entiendo ({e}); usa AAAA-MM-DD") from e
    if hasta < desde:
        raise ValueError(f"--hasta ({hasta}) es anterior a --desde ({desde})")
    return desde, hasta
