"""`telar mundos` — cuándo rige cada mundo y dónde vive su horario: en la raíz (todas las máquinas) o solo en esta; y pasarlo a
la raíz.

    telar mundos                   el horario de cada mundo y `fuera`, de dónde sale cada uno, y si dos se pisan
    telar mundos migrar --ver      qué pasaría de la configuración de esta máquina a la raíz
    telar mundos migrar            pasarlo (con respaldo de la configuración), commitearlo y subirlo
    telar mundos migrar --local    pasarlo y commitearlo, sin subir
    telar mundos subir             commitear y subir el archivo de la raíz ahora (⚙ mundos lo hace solo, al rato)

El horario de cada mundo y `fuera` van en `<raiz>/.telar/mundos.toml`, y se leen con la configuración: sin horario <
la raíz < lo que diga la configuración de la máquina, que pisa mundo por mundo, solo ahí (telar.mundos_raiz). Lo demás de
un mundo (rutas, áreas, etiquetas, color, tema, modos) sigue en la configuración de cada máquina. Migrar pasa lo de la
máquina a la raíz sin cambiar lo que rige: lo que la raíz ya dice igual sale de la máquina, y lo que la raíz dice distinto se queda
en la máquina (se lista: nada se pierde). Antes, la configuración se copia al lado
(`config.toml.antes-de-mundos-en-raiz-<fecha>`), y si la raíz de esta máquina está atrasada respecto de arriba, no migra:
hay que traerlo antes. Se commitea solo ese archivo, nunca otro.

Sale con 0 si quedó hecho (y subido, si se pidió), con 1 si quedó local (un choque, sin red) y con 2 si no se pudo.
"""

from __future__ import annotations

from pathlib import Path

from telar import config as mod_config
from telar import horario as mod_horario
from telar import mundos_raiz, temas
from telar.ordenes import _comun
from telar.ordenes.temas import _decir_git

AYUDA = "Cuándo rige cada mundo y dónde vive su horario (en la raíz, para todas las máquinas, o solo en esta), y pasarlo a la raíz."

def _donde(vive: str, n: str) -> str:
    return {"raiz": f"en {n}, todas las máquinas", "maquina": "solo en esta máquina"}[vive]


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("mundos", AYUDA)
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
        if cfg.mundos_archivo is None:
            return _comun.queja("la configuración no dice `raiz`: no hay archivo de la raíz")
        res = mundos_raiz.subir(cfg.mundos_archivo, estado=Path(cfg.estado), empujar=not o.local)
        return _decir_git(res, o.json, cfg.mundos_archivo, empujar=not o.local)

    donde = cfg.mundos_donde or {}
    choques = mundos_raiz.choques_de(cfg)
    if o.json:
        return _comun.escribir_json({
            "raiz": str(cfg.mundos_archivo or ""), "error_raiz": cfg.mundos_error, "sobran_raiz": list(cfg.mundos_sobran),
            "mundos": [{"nombre": m.nombre, "horario": [t.texto for t in m.horario],
                        "vive": (donde.get("horario") or {}).get(m.nombre, "")} for m in cfg.mundos],
            "fuera": cfg.mundos_fuera, "fuera_vive": donde.get("fuera", ""), "choques": choques})
    n = temas.nombre_raiz(cfg.mundos_archivo)
    print(_comun.fuerte(f"raíz: {cfg.mundos_archivo or 'no hay (la configuración no dice raiz)'}"))
    if cfg.mundos_error:
        print(_comun.rojo(f"  ✗ {cfg.mundos_error}"))
    if not cfg.mundos:
        print(_comun.tenue("  esta máquina no declara [mundos]"))
    for m in cfg.mundos:
        vive = (donde.get("horario") or {}).get(m.nombre, "")
        texto = ", ".join(t.texto for t in m.horario) or "sin horario: solo a mano"
        print(f"  {m.nombre}: {texto}" + (_comun.tenue(f"  ({_donde(vive, n)})") if vive else ""))
    if cfg.mundos:
        fuera = cfg.mundos_fuera or "ambos"
        vive = donde.get("fuera", "")
        print(f"  fuera de todo horario: {fuera}" + (_comun.tenue(f"  ({_donde(vive, n)})") if vive else ""))
    for c in choques:
        print(_comun.amarillo(f"  · {mod_horario.decir_choque(c)}: a esa hora rige el de fuera"))
    for s in cfg.mundos_sobran:
        print(_comun.amarillo(f"  · en {n} y no aquí: {s}"))
    return 0


def _migrar(ctx, o) -> int:
    cfg = ctx.config
    if cfg.mundos_archivo is None:
        return _comun.queja("la configuración no dice `raiz`: no hay raíz adonde llevar los horarios")
    if not o.ver:
        atraso = mundos_raiz.atrasado(cfg.mundos_archivo)
        if atraso:
            return _comun.queja(atraso)
    try:
        plan = mundos_raiz.migrar(cfg, ver=o.ver)
    except mod_config.ErrorDeConfig as e:
        return _comun.queja(str(e))
    res = None
    if plan["escrito"]:
        res = mundos_raiz.subir(cfg.mundos_archivo, estado=Path(cfg.estado), empujar=not o.local,
                                mensaje="mundos: el horario de la configuración de esta máquina, a la raíz (telar mundos migrar)")
        plan["git"] = res.json() if res is not None else None
    if o.json:
        _comun.escribir_json(plan)
    else:
        verbo = "pasaría" if o.ver else "pasó"
        n = temas.nombre_raiz(plan["raiz"])

        def nombre(x):
            return "fuera" if x["clave"] == "fuera" else f"{x['mundo']}.horario"

        if not (plan["pasan"] or plan["iguales"] or plan["quedan"]):
            print("la configuración de esta máquina no dice ningún horario ni `fuera`: nada que migrar")
        for x in plan["pasan"]:
            print(f"  → {nombre(x)} = {x['valor']}  ({verbo} a {n})")
        for x in plan["iguales"]:
            print(_comun.tenue(f"  = {nombre(x)} = {x['valor']}  ({n} ya lo dice: sale de la máquina)"))
        for x in plan["quedan"]:
            print(_comun.amarillo(f"  · {nombre(x)} = {x['aqui']}  queda en esta máquina ({n} dice {x['raiz']})"))
        if plan["respaldo"]:
            print(_comun.tenue(f"respaldo: {plan['respaldo']}"))
        if o.ver:
            print(_comun.tenue(f"nada escrito · raíz: {plan['raiz']}"))
    if res is None:
        return 0
    return _decir_git(res, o.json, cfg.mundos_archivo, empujar=not o.local, callado=o.json)
