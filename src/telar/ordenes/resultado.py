"""`telar resultado` — lo que una skill dejó un día, de la máquina donde vive (`[resultados]`).

    telar resultado                    los resultados declarados
    telar resultado plan               el plan de hoy
    telar resultado plan 2026-10-06    el de ese día
    telar resultado plan --json        para el dashboard: contenido, formato, días disponibles
    telar resultado plan 2026-10-06 --comentar < texto
                                       un comentario sobre ese día: lo atiende el `comentar` declarado,
                                       en la máquina donde vive (`en`); dice qué abrió

Un resultado con pasadas (`pasadas = "pulso"` en su vista: una skill que corre varias veces al día; ver
telar.pasadas) es una lista por día, que se va llenando:

    telar resultado pulso --agregar < pasada.json
                                       agrega UNA pasada (JSON) a su día, validada contra su esquema;
                                       un id que ya está es un error
    telar resultado pulso --agregar --desde archivo.jsonl
                                       importa las de un archivo (una por línea): todas se validan antes;
                                       las que ya están, por id, se saltan (se puede repetir)
    telar resultado pulso --sin-ver    las que la persona no ha visto, la más nueva arriba, y hasta cuál vio
    telar resultado pulso --visto [id] marcar vistas hasta esa (sin id: hasta la más nueva). Solo avanza
    … --mundo trabajo                  con --sin-ver, lo que se ve con ese mundo puesto (lo suyo y lo sin
                                       clasificar); con --visto, marca vistas solo esas (sin --mundo, todo)

Con `en` y bus, se le pide a la máquina que corre la skill; si no responde, se lee la copia de aquí
y se dice (ver `telar.resultados`). Las pasadas no tienen copia: si esa máquina no responde, se dice y
no se hace nada aquí.
"""

from __future__ import annotations

import json
import sys

from telar import resultados as mod
from telar.ordenes import _comun
from telar.servicios import resultados as servicio

AYUDA = "Lo que una skill dejó un día (el plan, por ejemplo), leído de la máquina donde vive."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("resultado", AYUDA)
    p.epilog = __doc__
    p.add_argument("clave", nargs="?", default="", help="el resultado ([resultados.<clave>])")
    p.add_argument("dia", nargs="?", default="", help="AAAA-MM-DD, o «ultimo» (el más reciente que hay); por defecto, hoy")
    p.add_argument("--json", action="store_true", help="en una línea")
    p.add_argument("--comentar", action="store_true", help="dejar un comentario sobre ese día (el texto, por la entrada estándar)")
    p.add_argument("--agregar", action="store_true", help="agregar una pasada (JSON, por la entrada estándar) a su día")
    p.add_argument("--desde", metavar="ARCHIVO", default="", help="con --agregar: importar las de un .jsonl (una por línea; las que ya están se saltan)")
    p.add_argument("--sin-ver", action="store_true", help="las pasadas que la persona no ha visto, y hasta cuál vio")
    p.add_argument("--visto", nargs="?", const="ultimo", default=None, metavar="ID",
                   help="marcar vistas las pasadas hasta ID (sin él, hasta la más nueva)")
    p.add_argument("--mundo", default="", metavar="MUNDO",
                   help="con --sin-ver o --visto: lo de ese mundo de [mundos] y lo sin clasificar (sin él, ambos)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.agregar or o.desde or o.sin_ver or o.visto is not None:
        if not o.clave:
            return _comun.queja("¿de qué resultado? telar resultado pulso --agregar < pasada.json")
        if o.dia:
            return _comun.queja("las pasadas no llevan día: el de cada una es el de su id")
        if o.desde and not o.agregar:
            return _comun.queja("--desde va con --agregar: telar resultado pulso --agregar --desde archivo.jsonl")
        if sum((o.agregar, o.sin_ver, o.visto is not None)) > 1:
            return _comun.queja("una cosa a la vez: --agregar, --sin-ver o --visto")
        if o.mundo and o.agregar:
            return _comun.queja("--mundo va con --sin-ver o --visto: el de cada cosa lo dice la pasada")
        if o.agregar:
            return _agregar(ctx, o)
        if o.sin_ver:
            return _sin_ver(ctx, o)
        return _visto(ctx, o)
    if o.mundo:
        return _comun.queja("--mundo va con --sin-ver o --visto")
    if o.comentar:
        if not o.clave:
            return _comun.queja("¿sobre qué resultado? telar resultado plan [día] --comentar < texto")
        from datetime import date

        c = servicio.comentar(ctx, o.clave, o.dia or date.today().isoformat(), sys.stdin.read())
        if o.json:
            _comun.escribir_json(c.model_dump(mode="json", exclude_unset=True))
            return 0 if c.ok else 1
        if not c.ok:
            return _comun.queja(c.error or "no salió", 1)
        print(f"se abrió «{c.abrio}»" if c.abrio else "listo")
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
    r = servicio.leer(ctx, o.clave, o.dia).model_dump(mode="json", exclude_unset=True)
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


# ── las pasadas (telar.pasadas) ──────────────────────────────────────────────

def _agregar(ctx, o) -> int:
    from pathlib import Path

    from telar import pasadas

    if o.desde:
        try:
            texto = Path(o.desde).expanduser().read_text(encoding="utf-8")
        except OSError as e:
            return _comun.queja(f"no pude leer {o.desde}: {e.strerror or e}")
        lista, nombres, rotas = pasadas.leer_jsonl(texto)
        if rotas:
            if o.json:
                _comun.escribir_json({"ok": False, "error": rotas[0], "errores": rotas})
                return 1
            for r in rotas:
                print(r, file=sys.stderr)
            return _comun.queja(f"{o.desde}: {len(rotas)} {'línea' if len(rotas) == 1 else 'líneas'} sin JSON; no importé nada")
        if not lista:
            return _comun.queja(f"{o.desde} no trae ninguna pasada")
        a = servicio.agregar(ctx, o.clave, lista, saltar_repetidas=True, nombres=nombres)
    else:
        try:
            pasada = json.loads(sys.stdin.read())
        except ValueError as e:
            return _comun.queja(f"la entrada no es JSON: {e}")
        a = servicio.agregar(ctx, o.clave, [pasada])
    if o.json:
        _comun.escribir_json(a.model_dump(mode="json", exclude_unset=True))
        return 0 if a.ok else 1
    if not a.ok:
        if len(a.errores) > 1:
            for e in a.errores:
                print(e, file=sys.stderr)
            return _comun.queja(f"{len(a.errores)} problemas: no entró ninguna", 1)
        return _comun.queja(a.error or "no salió", 1)
    donde = "" if a.desde in ("", "aquí") else f" en {a.desde}"
    for aviso in a.avisos:
        print(_comun.tenue(aviso), file=sys.stderr)
    if not o.desde:
        dia = next(iter(a.en_el_dia), "")
        print(f"agregada {a.agregadas[0]}{donde} · {a.en_el_dia.get(dia, 0)} el {dia}")
        return 0
    partes = [f"{len(a.agregadas)} {'agregada' if len(a.agregadas) == 1 else 'agregadas'}"]
    if a.ya_estaban:
        partes.append(f"{len(a.ya_estaban)} ya {'estaba' if len(a.ya_estaban) == 1 else 'estaban'}")
    print(" · ".join(partes) + donde)
    if a.distintas:
        print(_comun.tenue(f"con otro contenido aquí, no se reescribieron: {', '.join(a.distintas)}"))
    return 0


def _resumen(p: dict) -> str:
    """Una pasada en una línea: lo que cambió, como la de la página («3 nuevas · 2 avanzadas · 1 borrador»); sin cambios,
    lo que llegó de cada fuente. Lo que falló, al final."""
    t = p.get("tareas") if isinstance(p.get("tareas"), dict) else {}
    partes = []
    for n, una, varias in ((len(t.get("nuevas") or []), "nueva", "nuevas"), (len(t.get("avanzadas") or []), "avanzada", "avanzadas"),
                           (len(t.get("cerradas") or []), "cerrada", "cerradas"), (len(p.get("borradores") or []), "borrador", "borradores")):
        if n:
            partes.append(f"{n} {una if n == 1 else varias}")
    fuentes = [f for f in p.get("fuentes") or [] if isinstance(f, dict)]
    if not partes:
        partes = ["sin cambios"] + [f"{f.get('fuente', '')} {f.get('llegaron', 0)}" for f in fuentes if f.get("fuente")]
    fallas = [f.get("fuente", "") for f in fuentes if f.get("error")]
    if fallas:
        partes.append(f"falló {', '.join(fallas)}")
    return " · ".join(partes)


def _sin_ver(ctx, o) -> int:
    from telar import pasadas

    r = servicio.sin_ver(ctx, o.clave)
    if r.ok and o.mundo:
        # lo que se ve con ese mundo puesto: las que tienen algo sin ver de él o sin clasificar, con solo lo que se ve
        if o.mundo not in r.por_mundo:
            return _comun.queja(f"no hay un mundo «{o.mundo}»" + (f" ({', '.join(r.por_mundo)})" if r.por_mundo else
                                                                  ": esta configuración no declara [mundos]"))
        visibles = [pasadas.para_mundo(p, o.mundo) for p in r.pasadas if {o.mundo, ""} & set(p.get("sin_ver_en") or [""])]
        r = r.model_copy(update={"pasadas": visibles, "total": len(visibles), "con_cambios": r.por_mundo[o.mundo],
                                 "visto": max(r.visto, r.vistos.get(o.mundo, {}), key=lambda v: v.get("id", ""))})
    if o.json:
        _comun.escribir_json(r.model_dump(mode="json", exclude_unset=True))
        return 0 if r.ok else 1
    if not r.ok:
        return _comun.queja(r.error or "no salió")
    visto = r.visto.get("id", "")
    por_mundo = "" if o.mundo or not r.por_mundo else f" ({', '.join(f'{k} {n}' for k, n in r.por_mundo.items())})"
    print(_comun.tenue(f"{r.nombre}{' · ' + o.mundo if o.mundo else ''} · {'visto hasta ' + visto if visto else 'nada visto todavía'} · "
                       f"{r.total} sin ver, {r.con_cambios} con cambios{por_mundo}" + (f" · de {r.desde}" if r.desde not in ("", "aquí") else "")))
    for p in r.pasadas:
        marcas = " ".join(x for x in ("seco" if p.get("seco") else "", "pedida" if p.get("pedida") else "",
                                      "noche" if p.get("modo") == "noche" else "") if x)
        # en qué mundos tiene algo sin ver, si hay mundos y no se pidió uno
        en = [k or "sin clasificar" for k in p.get("sin_ver_en") or []] if r.por_mundo and not o.mundo else []
        cola = "  ".join(x for x in (marcas, f"sin ver en {', '.join(en)}" if en else "") if x)
        print(f"{p.get('id', '')}  {_resumen(p) if r.esquema == 'pulso' else ''}" + (_comun.tenue(f"  {cola}") if cola else ""))
        for t in [p.get("resumen") or ""] + [f"{k}: {v}" for k, v in (p.get("resumenes") or {}).items()]:
            if t:
                print(_comun.tenue(f"  {t}"))
    if r.total > len(r.pasadas):
        print(_comun.tenue(f"y {r.total - len(r.pasadas)} más"))
    return 0


def _visto(ctx, o) -> int:
    v = servicio.marcar_visto(ctx, o.clave, o.visto, o.mundo)
    if o.json:
        _comun.escribir_json(v.model_dump(mode="json", exclude_unset=True))
        return 0 if v.ok else 1
    if not v.ok:
        return _comun.queja(v.error or "no salió")
    hasta = max(v.visto.get("id", ""), v.vistos.get(o.mundo, {}).get("id", "")) if o.mundo else v.visto.get("id", "")
    en = f" en {o.mundo}" if o.mundo else ""
    if v.dice:
        print(v.dice)
    elif v.movio:
        print(f"visto hasta {hasta}{en}")
    else:
        print(f"ya estaba visto hasta {hasta}{en}")
    return 0
