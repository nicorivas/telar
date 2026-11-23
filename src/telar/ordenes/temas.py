"""`telar temas` — dónde vive cada tema: en la raíz (todas las máquinas) o solo en esta; y pasarlos a la raíz.

    telar temas                   cada tema con colores propios o propio, y dónde vive cada cosa
    telar temas migrar --ver      qué pasaría de la configuración de esta máquina a la raíz
    telar temas migrar            pasarlo (con respaldo de la configuración), commitearlo y subirlo
    telar temas migrar --local    pasarlo y commitearlo, sin subir
    telar temas subir             commitear y subir el archivo de la raíz ahora (⚙ temas lo hace solo, al rato)

Los temas de la raíz van en `<raiz>/.telar/temas.toml`, y se leen con la configuración: de fábrica < la raíz < los
`[temas.<tema>]` de la configuración de la máquina, que pisan color por color, solo ahí (telar.temas). Migrar pasa lo
de la máquina a la raíz sin cambiar lo que se ve: lo que la raíz ya dice igual sale de la máquina, y lo que la raíz dice
distinto se queda en la máquina (se lista: nada se pierde). Antes, la configuración se copia al lado
(`config.toml.antes-de-temas-en-raiz-<fecha>`), y si la raíz de esta máquina está atrasada respecto de arriba, no migra:
hay que traerlo antes. Se commitea solo ese archivo, nunca otro.

Sale con 0 si quedó hecho (y subido, si se pidió), con 1 si quedó local (un choque, sin red) y con 2 si no se pudo.
"""

from __future__ import annotations

import sys
from pathlib import Path

from telar import config as mod_config
from telar import temas
from telar.ordenes import _comun

AYUDA = "Dónde vive cada tema (en la raíz, para todas las máquinas, o solo en esta), y pasarlos a la raíz."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("temas", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", default="", choices=["", "migrar", "subir"], help="migrar · subir")
    p.add_argument("--ver", action="store_true", help="con migrar: solo decir qué haría")
    p.add_argument("--local", action="store_true", help="commitear sin subir")
    p.add_argument("--json", action="store_true", help="lo que hay o lo que pasó, como JSON")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    cfg = ctx.config
    if o.verbo == "migrar":
        return _migrar(ctx, o)
    if o.verbo == "subir":
        if cfg.temas_archivo is None:
            return _comun.queja("la configuración no dice `raiz`: no hay archivo de la raíz")
        res = temas.subir(cfg.temas_archivo, estado=Path(cfg.estado), empujar=not o.local)
        return _decir_git(res, o.json, cfg.temas_archivo, empujar=not o.local)

    d = temas.para_la_configuracion(cfg)
    if o.json:
        return _comun.escribir_json(d)
    n = temas.nombre_raiz(d["raiz"])
    print(_comun.fuerte(f"raíz: {d['raiz'] or 'no hay (la configuración no dice raiz)'}"))
    print(_comun.tenue(f"esta máquina: {d['maquina']}"))
    if d["error_raiz"]:
        print(_comun.rojo(f"  ✗ {d['error_raiz']}"))
    hay = False
    for t in d["temas"]:
        if not t["vive"]:
            continue
        hay = True
        dice = {"raiz": f"en {n}, todas las máquinas", "maquina": "solo en esta máquina",
                "mixto": f"en {n}, y esta máquina pisa algunos"}[t["vive"]]
        base = f" (parte de {t['base']})" if t["base"] else ""
        print(f"  {t['clave']}{base}: {dice}")
        if t["en_raiz"]:
            print(_comun.tenue(f"      en {n}: {', '.join(t['en_raiz'])}"))
        if t["en_maquina"]:
            print(_comun.tenue(f"      solo aquí: {', '.join(t['en_maquina'])}"))
    if not hay:
        print(_comun.tenue("  todos de fábrica"))
    return 0


def _migrar(ctx, o) -> int:
    cfg = ctx.config
    if cfg.temas_archivo is None:
        return _comun.queja("la configuración no dice `raiz`: no hay raíz adonde llevar los temas")
    if not o.ver:
        atraso = temas.atrasado(cfg.temas_archivo)
        if atraso:
            return _comun.queja(atraso)
    try:
        plan = temas.migrar(cfg, ver=o.ver)
    except mod_config.ErrorDeConfig as e:
        return _comun.queja(str(e))
    res = None
    if plan["escrito"]:
        res = temas.subir(cfg.temas_archivo, estado=Path(cfg.estado), empujar=not o.local,
                          mensaje="temas: los de la configuración de esta máquina, a la raíz (telar temas migrar)")
        plan["git"] = res.json() if res is not None else None
    if o.json:
        _comun.escribir_json(plan)
    else:
        verbo = "pasarían" if o.ver else "pasaron"
        n = temas.nombre_raiz(plan["raiz"])
        if not (plan["pasan"] or plan["iguales"] or plan["quedan"]):
            print("la configuración de esta máquina no tiene [temas.*]: nada que migrar")
        for x in plan["pasan"]:
            print(f"  → {x['tema']}.{x['clave']} = {x['valor']}  ({verbo} a {n})")
        for x in plan["iguales"]:
            print(_comun.tenue(f"  = {x['tema']}.{x['clave']} = {x['valor']}  ({n} ya lo dice: sale de la máquina)"))
        for x in plan["quedan"]:
            print(_comun.amarillo(f"  · {x['tema']}.{x['clave']} = {x['aqui']}  queda en esta máquina ({n} dice "
                                  f"{x['raiz'] or 'otra base'})"))
        if plan["respaldo"]:
            print(_comun.tenue(f"respaldo: {plan['respaldo']}"))
        if o.ver:
            print(_comun.tenue(f"nada escrito · raíz: {plan['raiz']}"))
    if res is None:
        return 0
    return _decir_git(res, o.json, cfg.temas_archivo, empujar=not o.local, callado=o.json)


def _decir_git(res, como_json: bool, archivo_raiz: Path, *, empujar: bool, callado: bool = False) -> int:
    """0 si quedó commiteado (y subido, si se pidió), 1 si quedó local (un choque, sin red), 2 si no se pudo."""
    if res is None:
        if not callado:
            print(f"{archivo_raiz} no está en un repositorio git: queda sin commitear")
        return 0
    bien = res.subido if empujar else res.estado in ("commiteado", "nada")
    codigo = 0 if bien else 2 if res.estado == "fallo" and not res.commit else 1
    if como_json and not callado:
        _comun.escribir_json(res.json())
    elif not como_json:
        dice = {"subido": f"{res.commit or 'al día'} en {res.rama}, subido",
                "commiteado": f"{res.commit} en {res.rama}, sin subir" + (f": {res.detalle}" if res.detalle else ""),
                "nada": "nada que commitear: ya estaba"}.get(res.estado, res.detalle)
        print(dice, file=sys.stdout if codigo == 0 else sys.stderr)
    return codigo
