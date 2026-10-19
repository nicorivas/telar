"""`telar resultado` — lo que una skill dejó un día, de la máquina donde vive (`[resultados]`).

    telar resultado                    los resultados declarados
    telar resultado plan               el plan de hoy
    telar resultado plan 2026-10-06    el de ese día
    telar resultado plan --json        para el dashboard: contenido, formato, días disponibles
    telar resultado plan 2026-10-06 --comentar < texto
                                       un comentario sobre ese día: lo atiende el `comentar` declarado,
                                       en la máquina donde vive (`en`); dice qué abrió

Con `en` y bus, se le pide a la máquina que corre la skill; si no responde, se lee la copia de aquí
y se dice (ver `telar.resultados`).
"""

from __future__ import annotations

import json
import sys

from telar import resultados as mod
from telar.ordenes import _comun

AYUDA = "Lo que una skill dejó un día (el plan, por ejemplo), leído de la máquina donde vive."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("resultado", AYUDA)
    p.epilog = __doc__
    p.add_argument("clave", nargs="?", default="", help="el resultado ([resultados.<clave>])")
    p.add_argument("dia", nargs="?", default="", help="AAAA-MM-DD; por defecto, hoy")
    p.add_argument("--json", action="store_true", help="en una línea")
    p.add_argument("--comentar", action="store_true", help="dejar un comentario sobre ese día (el texto, por la entrada estándar)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.comentar:
        if not o.clave:
            return _comun.queja("¿sobre qué resultado? telar resultado plan [día] --comentar < texto")
        from datetime import date

        r = mod.comentar(ctx.config, o.clave, o.dia or date.today().isoformat(), sys.stdin.read())
        if o.json:
            _comun.escribir_json(r)
            return 0 if r.get("ok") else 1
        if not r.get("ok"):
            return _comun.queja(r.get("error", "no salió"), 1)
        print(f"se abrió «{r.get('abrio', '')}»" if r.get("abrio") else "listo")
        return 0
    if not o.clave:
        lista = [{"clave": r.clave, "nombre": r.nombre or r.clave, "en": r.en, "carpeta": r.carpeta}
                 for r in ctx.config.resultados]
        if o.json:
            return _comun.escribir_json({"resultados": lista})
        if not lista:
            print(_comun.tenue("ninguno: [resultados.<clave>] en la configuración"))
        for r in lista:
            print(f"{r['clave']:<16} {r['nombre']:<20} " + _comun.tenue(f"{r['en'] or 'aquí'} · {r['carpeta']}"))
        return 0
    r = mod.leer(ctx.config, o.clave, o.dia)
    if o.json:
        return _comun.escribir_json(r)
    if not r.get("ok"):
        return _comun.queja(r.get("error", "no salió"))
    if r.get("aviso"):
        print(_comun.tenue(r["aviso"]))
    if r["contenido"] is None:
        print(_comun.tenue(f"no hay {r['nombre']} del {r['dia']}"))
    elif r["formato"] == "md":
        print(r["contenido"])
    else:
        print(json.dumps(r["contenido"], ensure_ascii=False, indent=1))
    return 0
