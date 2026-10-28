"""`telar modulos` — los módulos: cuáles hay, instalarlos desde un repositorio, actualizarlos, quitarlos.

    telar modulos                              la lista: nombre, carpeta, lo que trae y de dónde vino
    telar modulos --json
    telar modulos catalogo [--buscar X] [--forzar] [--json]   los que hay en los catálogos (telar.catalogo)
    telar modulos instalar <nombre>            uno del catálogo, en la versión que dice el catálogo
    telar modulos instalar <repo git o carpeta> [--nombre N] [--enlazar] [--si]   uno suelto (sin revisar)
    telar modulos actualizar <nombre>          a la versión nueva del catálogo, o git pull; y su [instalar]
    telar modulos activar|desactivar <nombre>  encenderlo o apagarlo sin desinstalarlo
    telar modulos quitar <nombre> [--si]       lo desanota y borra la carpeta que bajó telar
    telar modulos adoptar <nombre>             uno declarado a mano en la configuración pasa a los instalados
    telar modulos nuevo <nombre> [--carpeta C] arma la carpeta de un módulo nuevo, para escribirlo
    telar modulos revisar [carpeta]            lo que le falta para publicarlo (y `--catalogo F`: revisar un catálogo)
    telar modulos publicar [carpeta] --version vX.Y [--catalogo oficial|<repo>] [--seco]   al catálogo, con un PR
    telar modulos permisos [nombre] [--quitar [orden]]   lo que su página pidió y se le concedió o negó; olvidarlo

Escribir, probar, publicar y mantener un módulo, con su criterio: la skill /modulos (`telar agente instalar`).

Un módulo es una carpeta con un `modulo.toml` (ver telar.modulos y docs/configuracion.md, `[modulos]`). Instalar clona el
repositorio en `~/.local/share/telar/modulos/<nombre>`, muestra lo que trae (pestaña, órdenes,
periódicos…) y, con tu sí, corre su `[instalar]` y lo anota en `modulos.toml`, al lado de la
configuración. Antes de preguntar dice también lo que el módulo pide fuera de su carpeta (`[permisos]`: rutas,
red, órdenes de telar); telar todavía no lo hace cumplir, y lo dice. `--enlazar` usa la carpeta donde está, sin copiarla: para desarrollar un módulo. Se instala
en cada máquina que lo usa. Si trae periódicos y esta es la máquina donde corren (`[periodicos] en`),
instalar, actualizar, adoptar y quitar dejan el crontab al día solos; si corren en otra, lo dice.

También se puede declarar uno a mano en la configuración, `[modulos.<nombre>] carpeta = "…"`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from telar.ordenes import _comun
from telar.salida import visible

AYUDA = "Los módulos (una carpeta con modulo.toml): la lista, e instalarlos desde un repositorio."
VERBOS = ("instalar", "actualizar", "quitar", "adoptar", "activar", "desactivar", "catalogo", "nuevo", "revisar",
          "publicar", "permisos")


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
        from telar.servicios import modulos as servicio

        return _comun.escribir_json(servicio.instalados(ctx).model_dump(mode="json"))
    apagados = [n for n, d in instalados.items() if d.get("activo") is False]
    if not modulos:
        print(_comun.tenue("no hay módulos: telar modulos instalar <repo>, o [modulos.<nombre>] carpeta = \"…\" a mano"))
    for m in modulos:
        de = mod_modulos.linea_procedencia(mod_modulos.procedencia(instalados.get(m.nombre)))
        print(f"{m.nombre}  " + _comun.tenue(f"{m.carpeta}  {de}"))
        if m.descripcion:
            print(f"    {visible(m.descripcion)}")
        print(_comun.tenue("    aporta: " + (", ".join(m.aporta) or "nada")))
        print(_comun.tenue("    pide: " + "; ".join(m.pide)))
    for n in apagados:
        print(f"{n}  " + _comun.tenue(f"apagado · {instalados[n].get('carpeta', '')} · telar modulos activar {n}"))
    return 0


def _periodicos(ctx, hay: bool) -> None:
    """Si el módulo trae (o traía) periódicos: en la máquina donde corren, el crontab al día con la
    configuración de ahora; en otra, el aviso de que allá también hay que instalarlo."""
    if not hay:
        return
    from telar import bus as mod_bus
    from telar import config as mod_config
    from telar import periodicos as mod_periodicos

    en = ctx.config.periodicos_en
    if en and en not in ("aqui", mod_bus.maquina(ctx.config)):
        print(_comun.tenue(f"    sus periódicos corren en {en}: instálalo (o actualízalo, o quítalo) allá también"))
        return
    try:
        config = mod_config.cargar(ctx.config.origen) if ctx.config.origen else mod_config.cargar()
        archivo = mod_periodicos.completo(mod_periodicos.leer(mod_periodicos.ruta(ctx.config.origen)), config)
        from telar.ordenes.periodicos import _telar

        mod_periodicos.aplicar(archivo, _telar())
        print(_comun.tenue("    crontab al día con sus periódicos"))
    except (mod_config.ErrorDeConfig, mod_periodicos.ErrorDePeriodicos) as e:
        print(f"telar: el crontab no quedó al día ({e}): telar periodicos aplicar", file=sys.stderr)


def _si(pregunta: str, si: bool) -> bool:
    if si:
        return True
    if not sys.stdin.isatty():
        print(_comun.tenue("sin terminal para preguntar: repite con --si"))
        return False
    return input(f"{pregunta} [s/N] ").strip().lower() in ("s", "si", "sí", "y", "yes")


def _verbo(verbo: str, argv: list[str], ctx) -> int:
    from telar import modulos as mod_modulos

    if verbo in ("catalogo", "nuevo", "revisar", "publicar"):
        from telar.ordenes import modulos_publicar

        return modulos_publicar.main(verbo, argv, ctx)
    if verbo == "permisos":
        return _permisos(argv, ctx)
    p = _comun.analizador(f"modulos {verbo}", AYUDA)
    if verbo == "instalar":
        p.add_argument("fuente", help="su nombre en un catálogo, o un repositorio git (URL o carpeta) con un modulo.toml")
        p.add_argument("--nombre", default="", help="con otro nombre que el del manifiesto o el repositorio")
        p.add_argument("--enlazar", action="store_true", help="usar la carpeta donde está, sin copiarla")
    else:
        p.add_argument("nombre")
    if verbo in ("instalar", "quitar"):
        p.add_argument("--si", action="store_true", help="sin preguntar")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    ruta = mod_modulos.ruta_instalados(ctx.config.origen)
    try:
        if verbo in ("activar", "desactivar"):
            tenia = bool(getattr(mod_modulos.buscar(ctx.config, o.nombre), "periodicos", None))
            print(mod_modulos.activar(ruta, o.nombre, verbo == "activar"))
            if verbo == "activar":
                # con la configuración de ahora, ya cargado: sus periódicos, si trae
                from telar import config as mod_config

                ctx.config = mod_config.cargar(ctx.config.origen) if ctx.config.origen else mod_config.cargar()
                tenia = bool(getattr(mod_modulos.buscar(ctx.config, o.nombre), "periodicos", None))
            _periodicos(ctx, tenia)
            return 0
        if verbo == "instalar":
            del_catalogo = None
            if mod_modulos.NOMBRE.fullmatch(o.fuente) and not o.enlazar and not Path(o.fuente).expanduser().exists():
                from telar import __version__, catalogo

                del_catalogo = catalogo.buscar(ctx.config, o.fuente)
                if del_catalogo is None:
                    print(f"telar: «{o.fuente}» no está en ningún catálogo (telar modulos catalogo): dale la URL de su "
                          "repositorio para instalarlo suelto", file=sys.stderr)
                    return 1
                if not catalogo.le_sirve(del_catalogo, __version__):
                    print(f"telar: {o.fuente} pide telar {del_catalogo.telar} y este es el {__version__}: actualiza telar",
                          file=sys.stderr)
                    return 1
            if del_catalogo is not None:
                m, anotar = mod_modulos.preparar(del_catalogo.fuente, nombre=o.nombre or del_catalogo.nombre,
                                                 ref=del_catalogo.version)
                anotar["catalogo"] = del_catalogo.catalogo
            else:
                m, anotar = mod_modulos.preparar(o.fuente, nombre=o.nombre, enlazar=o.enlazar)
            # lo escribe el módulo y se lee antes del sí: sus caracteres de control a la vista (telar.salida.visible)
            print(f"{m.nombre}" + (f" — {visible(m.descripcion)}" if m.descripcion else ""))
            print(_comun.tenue(f"    de {anotar['fuente']} @ {anotar.get('ref') or anotar.get('version') or '?'}"))
            confianza = {"oficial": "del catálogo de telar: revisado", "equipo": "del catálogo de tu equipo"}
            print(("    " + confianza[del_catalogo.confianza]) if del_catalogo is not None and del_catalogo.confianza in confianza
                  else _comun.amarillo("    sin revisar: no viene de un catálogo revisado; lee lo que corre y lo que pide"))
            print("    trae: " + (", ".join(m.aporta) or "nada"))
            if m.instalar:
                print("    al instalarse corre: " + visible(" ".join(m.instalar)))
            print("    pide: " + "; ".join(m.pide))
            print(_comun.tenue("    (telar todavía no lo hace cumplir: corre con tus permisos, lo declare o no)"))
            if not _si(f"¿instalar {m.nombre}?", o.si):
                if anotar.get("provisorio"):
                    import shutil

                    shutil.rmtree(anotar["provisorio"], ignore_errors=True)
                return 1
            carpeta = mod_modulos.confirmar_instalacion(ruta, m, anotar)
            print(f"instalado {m.nombre} en {carpeta}")
            if m.ordenes:
                print(_comun.tenue(f"    sus órdenes: telar {m.nombre} <{'|'.join(m.ordenes)}>"))
            _periodicos(ctx, bool(m.periodicos))
            return 0
        tenia = bool(getattr(mod_modulos.buscar(ctx.config, o.nombre), "periodicos", None))
        if verbo == "actualizar":
            anotado = mod_modulos.leer_instalados(ruta).get(o.nombre, {})
            ref = ""
            if anotado.get("catalogo"):
                from telar import catalogo

                e = catalogo.buscar(ctx.config, o.nombre, forzar=True)
                ref = e.version if e is not None else ""
            print(mod_modulos.actualizar(ruta, o.nombre, ref=ref))
        elif verbo == "adoptar":
            from telar.config import ruta_config

            print(mod_modulos.adoptar(ruta, Path(ctx.config.origen or ruta_config()), o.nombre))
        else:
            if not _si(f"¿quitar {o.nombre}?", o.si):
                return 1
            print(mod_modulos.quitar(ruta, o.nombre))
        _periodicos(ctx, tenia)
        return 0
    except mod_modulos.ErrorDeModulo as e:
        print(f"telar: {e}", file=sys.stderr)
        return 1


def _permisos(argv: list[str], ctx) -> int:
    """`telar modulos permisos [módulo] [--quitar orden]`: lo que la persona le concedió o negó a cada módulo cuando su
    página lo pidió (telar.concesiones), y olvidarlo para que se vuelva a preguntar."""
    from telar import concesiones

    p = _comun.analizador("modulos permisos", "Lo concedido o negado a cada módulo, y olvidarlo.")
    p.add_argument("nombre", nargs="?", default="")
    p.add_argument("--quitar", nargs="?", const="*", default="", help="olvidar una orden (o todas): se vuelve a preguntar")
    p.add_argument("--json", action="store_true")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.quitar:
        if not o.nombre:
            return _comun.queja("¿de qué módulo? telar modulos permisos <módulo> --quitar [orden]")
        hubo = concesiones.quitar(ctx.config, o.nombre, "" if o.quitar == "*" else o.quitar)
        print(f"{o.nombre}: olvidado; la próxima vez se pregunta" if hubo else f"{o.nombre}: no había nada que olvidar")
        return 0
    datos = concesiones.leer(ctx.config)
    if o.nombre:
        datos = {o.nombre: datos.get(o.nombre, {})}
    if o.json:
        return _comun.escribir_json(datos)
    if not any(datos.values()):
        print(_comun.tenue("ningún módulo ha pedido nada todavía"))
    for modulo, ordenes in datos.items():
        for orden, d in ordenes.items():
            print(f"{modulo}  {orden}  {d.get('decision', '')}  " + _comun.tenue(str(d.get("desde", ""))))
    return 0
