"""`telar modulos` — los módulos: cuáles hay, instalarlos desde un repositorio, actualizarlos, quitarlos.

    telar modulos                              la lista: nombre, carpeta, lo que trae y de dónde vino
    telar modulos --json
    telar modulos instalar <repo git o carpeta> [--nombre N] [--enlazar] [--si]
    telar modulos actualizar <nombre>          git pull y su [instalar] de nuevo
    telar modulos quitar <nombre> [--si]       lo desanota y borra la carpeta que bajó telar

Un módulo es una carpeta con un `modulo.toml` (ver telar.modulos y docs/configuracion.md, `[modulos]`). Instalar clona el
repositorio en `~/.local/share/telar/modulos/<nombre>`, muestra lo que trae (pestaña, órdenes,
periódicos…) y, con tu sí, corre su `[instalar]` y lo anota en `modulos.toml`, al lado de la
configuración. `--enlazar` usa la carpeta donde está, sin copiarla: para desarrollar un módulo. Se instala
en cada máquina que lo usa. Si trae periódicos, `telar periodicos aplicar` los pone en el crontab.

También se puede declarar uno a mano en la configuración, `[modulos.<nombre>] carpeta = "…"`.
"""

from __future__ import annotations

import sys

from telar.ordenes import _comun

AYUDA = "Los módulos (una carpeta con modulo.toml): la lista, e instalarlos desde un repositorio."
VERBOS = ("instalar", "actualizar", "quitar")


def main(argv: list[str], ctx) -> int:
    if argv and argv[0] in VERBOS:
        return _verbo(argv[0], argv[1:], ctx)
    p = _comun.analizador("modulos", AYUDA)
    p.epilog = __doc__
    p.add_argument("--json", action="store_true", help="la lista, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    from telar import modulos as mod_modulos

    modulos = ctx.config.modulos
    instalados = mod_modulos.leer_instalados(mod_modulos.ruta_instalados(ctx.config.origen))
    if o.json:
        return _comun.escribir_json({"modulos": [
            {"nombre": m.nombre, "carpeta": str(m.carpeta), "descripcion": m.descripcion, "aporta": m.aporta,
             "fuente": instalados.get(m.nombre, {}).get("fuente", ""), "version": instalados.get(m.nombre, {}).get("version", "")}
            for m in modulos]})
    if not modulos:
        print(_comun.tenue("no hay módulos: telar modulos instalar <repo>, o [modulos.<nombre>] carpeta = \"…\" a mano"))
    for m in modulos:
        d = instalados.get(m.nombre, {})
        de = f"  {d.get('fuente', '')} @ {d.get('version', '')}" if d else "  (a mano)"
        print(f"{m.nombre}  " + _comun.tenue(str(m.carpeta) + de))
        if m.descripcion:
            print(f"    {m.descripcion}")
        print(_comun.tenue("    aporta: " + (", ".join(m.aporta) or "nada")))
    return 0


def _si(pregunta: str, si: bool) -> bool:
    if si:
        return True
    if not sys.stdin.isatty():
        print(_comun.tenue("sin terminal para preguntar: repite con --si"))
        return False
    return input(f"{pregunta} [s/N] ").strip().lower() in ("s", "si", "sí", "y", "yes")


def _verbo(verbo: str, argv: list[str], ctx) -> int:
    from telar import modulos as mod_modulos

    p = _comun.analizador(f"modulos {verbo}", AYUDA)
    if verbo == "instalar":
        p.add_argument("fuente", help="un repositorio git (URL o carpeta) con un modulo.toml")
        p.add_argument("--nombre", default="", help="con otro nombre que el del manifiesto o el repositorio")
        p.add_argument("--enlazar", action="store_true", help="usar la carpeta donde está, sin copiarla")
    else:
        p.add_argument("nombre")
    if verbo != "actualizar":
        p.add_argument("--si", action="store_true", help="sin preguntar")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    ruta = mod_modulos.ruta_instalados(ctx.config.origen)
    try:
        if verbo == "instalar":
            m, anotar = mod_modulos.preparar(o.fuente, nombre=o.nombre, enlazar=o.enlazar)
            print(f"{m.nombre}" + (f" — {m.descripcion}" if m.descripcion else ""))
            print(_comun.tenue(f"    de {anotar['fuente']} @ {anotar.get('version') or '?'}"))
            print("    trae: " + (", ".join(m.aporta) or "nada"))
            if m.instalar:
                print("    al instalarse corre: " + " ".join(m.instalar))
            if not _si(f"¿instalar {m.nombre}?", o.si):
                if anotar.get("provisorio"):
                    import shutil

                    shutil.rmtree(anotar["provisorio"], ignore_errors=True)
                return 1
            carpeta = mod_modulos.confirmar_instalacion(ruta, m, anotar)
            print(f"instalado {m.nombre} en {carpeta}")
            if m.periodicos:
                print(_comun.tenue("    trae periódicos: telar periodicos aplicar, donde corren"))
            if m.ordenes:
                print(_comun.tenue(f"    sus órdenes: telar {m.nombre} <{'|'.join(m.ordenes)}>"))
            return 0
        if verbo == "actualizar":
            print(mod_modulos.actualizar(ruta, o.nombre))
            return 0
        if not _si(f"¿quitar {o.nombre}?", o.si):
            return 1
        print(mod_modulos.quitar(ruta, o.nombre))
        return 0
    except mod_modulos.ErrorDeModulo as e:
        print(f"telar: {e}", file=sys.stderr)
        return 1
