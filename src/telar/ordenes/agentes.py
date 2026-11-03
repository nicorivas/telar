"""`telar agentes` — los agentes residentes y lo que declara cada uno en su `agente.toml`.

    telar agentes              uno por línea: nombre, carpeta, modelo, para qué es
    telar agentes faro         uno entero: lo que declara, lo que todavía no se usa y lo que no se pudo leer
    telar agentes --json       el contrato (docs/contratos.md)
    telar agentes nuevo "Faro" [--para "…"] [--icono ☼]   uno nuevo: su carpeta, y [agentes] carpeta si faltaba
    telar agentes eliminar faro [--si]   sacarlo: archiva sus hilos (con su conversación) y su carpeta pasa a
                                         <agentes>/_eliminados/ (no se borra nada)
    telar agentes eliminados             los que se pueden traer de vuelta
    telar agentes restaurar faro         traerlo de vuelta: su carpeta y lo que esta máquina tenía de él

Un residente es una carpeta de `[agentes] carpeta` con su `CLAUDE.md`; su definición, si la tiene, es un
`agente.toml` al lado (telar.agentes, docs/propuestas/agente-como-definicion.md). Sin él vale lo de
siempre: el nombre del README, el modelo de la configuración, residente. `telar agente` (sin la s) es otra
cosa: el motor que corre en un hilo, sus ganchos y sus conversaciones.
"""

from __future__ import annotations

from telar import agentes as mod_agentes
from telar.ordenes import _comun

AYUDA = "Los agentes residentes y lo que declara cada uno en su agente.toml."


def main(argv: list[str], ctx) -> int:
    if argv and argv[0] == "nuevo":
        return _nuevo(argv[1:], ctx)
    if argv and argv[0] in ("eliminar", "restaurar", "eliminados"):
        return _eliminar(argv[0], argv[1:], ctx)
    p = _comun.analizador("agentes", AYUDA)
    p.epilog = __doc__
    p.add_argument("agente", nargs="?", default="", help="uno solo: su carpeta o su nombre")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    from telar import estado as mod_estado

    try:
        vinculos = mod_estado.abrir(ctx.config).vinculos()
    except Exception:  # noqa: BLE001 - sin estado salen igual, solo sin los hilos vinculados
        vinculos = {}
    todos = mod_agentes.descubrir(ctx.config, vinculos)
    if o.agente:
        uno = next((a for a in todos if o.agente in (a.clave, a.nombre)), None)
        if uno is None:
            hay = ", ".join(a.clave for a in todos) or "ninguno: [agentes] carpeta en la configuración"
            return _comun.queja(f"no hay un agente «{o.agente}» (hay: {hay})")
        if o.json:
            return _comun.escribir_json(mod_agentes.como_json(uno))
        _uno(uno)
        return 0
    if o.json:
        return _comun.escribir_json({"agentes": [mod_agentes.como_json(a) for a in todos]})
    if not todos:
        print(_comun.tenue("no hay agentes residentes: telar agentes nuevo \"Nombre\" arma uno"))
        return 0
    ancho = max(len(a.nombre) for a in todos)
    for a in todos:
        marcas = [a.modelo] if a.modelo else []
        if not a.residente:
            marcas.append("no residente")
        if a.problemas:
            marcas.append(_comun.plural(len(a.problemas), "problema"))
        print(f"{a.nombre:<{ancho}}  " + _comun.tenue(f"{a.clave}/" + (f"  {' · '.join(marcas)}" if marcas else "")))
        if a.para:
            print(f"    {a.para}")
    return 0


def _uno(a) -> None:
    print(_comun.fuerte(a.nombre) + _comun.tenue(f"  agente:{a.clave}  {a.carpeta}"))
    print(f"  definición   {a.definicion or _comun.tenue('sin agente.toml: lo de siempre')}")
    if a.nombre != a.nombre_de_antes:
        print(f"  nombre       {a.nombre} " + _comun.tenue(f"(sin agente.toml sería «{a.nombre_de_antes}»)"))
    print(f"  para         {a.para or _comun.tenue('—')}")
    print(f"  modelo       {a.modelo or _comun.tenue('el de la configuración')}")
    print(f"  residente    {'sí' if a.residente else 'no: lo que le llega espera en su casilla'}")
    print(f"  hilos        {', '.join(a.hilos)}")
    if a.en:
        print(f"  vive en      {a.en}")
    if a.argumentos:
        print(f"  argumentos   {' '.join(a.argumentos)} " + _comun.tenue("([agentes.<carpeta>] de esta máquina)"))
    for clave, valor in a.sin_uso.items():
        print(f"  {clave:<12} {valor} " + _comun.tenue("(declarado, sin uso todavía)"))
    for problema in a.problemas:
        print(f"  ! {problema}")


def _nuevo(argv: list[str], ctx) -> int:
    from telar.config import ruta_config

    p = _comun.analizador("agentes nuevo", "Un agente residente nuevo: su carpeta y [agentes] carpeta si faltaba.")
    p.add_argument("nombre")
    p.add_argument("--para", default="", help="para qué encargarle algo, en una o dos frases")
    p.add_argument("--icono", default="", help="uno o dos caracteres para la lista")
    p.add_argument("--json", action="store_true")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        r = mod_agentes.crear(ctx.config, ctx.config.origen or ruta_config(), o.nombre, para=o.para,
                              icono=o.icono)
    except (ValueError, OSError) as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    print(f"agente {r['nombre']} en {r['carpeta']}")
    if r["configurado"]:
        print(_comun.tenue(f"    [agentes] carpeta quedó en la configuración"))
    print(_comun.tenue(f"    escribe en su CLAUDE.md qué hace; encárgale algo: telar encargar {r['clave']} \"…\""))
    return 0


def _eliminar(verbo: str, argv: list[str], ctx) -> int:
    """Eliminar a un agente (sus hilos al archivo, su carpeta a `_eliminados`), listar los eliminados o traer uno."""
    import io
    import sys
    from contextlib import redirect_stdout

    from telar.config import ruta_config
    from telar.ordenes import hilo as orden_hilo

    p = _comun.analizador(f"agentes {verbo}", "Eliminar a un agente, ver los eliminados o traer uno de vuelta.")
    if verbo != "eliminados":
        p.add_argument("agente", help="su carpeta o su nombre")
    p.add_argument("--si", action="store_true", help="sin preguntar")
    p.add_argument("--json", action="store_true")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    ruta = ctx.config.origen or ruta_config()
    if verbo == "eliminados":
        lista = mod_agentes.eliminados(ctx.config)
        if o.json:
            return _comun.escribir_json({"eliminados": lista})
        for x in lista:
            print(f"{x['nombre']}  " + _comun.tenue(x["carpeta"]))
        if not lista:
            print(_comun.tenue("ninguno"))
        return 0
    if verbo == "restaurar":
        try:
            r = mod_agentes.restaurar(ctx.config, ruta, o.agente)
        except (ValueError, OSError) as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r)
        print(f"de vuelta: {r['nombre']} en {r['carpeta']}")
        print(_comun.tenue("    sus hilos siguen en el archivo: retómalos desde ahí"))
        return 0

    a = mod_agentes.buscar(ctx.config, o.agente)
    if a is None:
        return _comun.queja(f"no hay un agente «{o.agente}»")
    if not o.si and not o.json:
        if not sys.stdin.isatty():
            return _comun.queja(f"eliminar a {a.nombre} archiva sus hilos y aparta su carpeta: confírmalo con --si")
        respuesta = input(f"¿Eliminar a {a.nombre}? Sus hilos van al archivo y su carpeta a {mod_agentes.ELIMINADOS}/ [s/N] ")
        if respuesta.strip().lower() not in ("s", "si", "sí", "y", "yes"):
            print("no se tocó nada")
            return 1
    # sus hilos (el suyo, los que declara y sus hijos «Agente › …»), al archivo con su conversación: se cierran donde
    # vivan (en otra máquina, por el bus) y se pueden retomar
    from telar import hijos

    tel = _comun.tejer(ctx, con_ficha=False)
    suyos = [h for h in tel.hilos if not h.archivado
             and (h.nombre in a.hilos or h.nombre.startswith(f"{a.nombre}{hijos.SEPARADOR}"))]
    archivados, problemas = [], []
    for h in suyos:
        salida = io.StringIO()
        with redirect_stdout(salida):
            c = orden_hilo.main(["archivar", "--cerrar", "--hilo", h.nombre], ctx)
        (archivados if c == 0 else problemas).append(h.nombre)
    try:
        r = mod_agentes.eliminar(ctx.config, ruta, a.clave)
    except (ValueError, OSError) as e:
        return _comun.queja(str(e))
    r = {**r, "archivados": archivados, "sin_archivar": problemas}
    if o.json:
        return _comun.escribir_json(r)
    print(f"eliminado: {r['nombre']}; su carpeta quedó en {r['carpeta']}")
    if archivados:
        print(_comun.tenue(f"    al archivo: {', '.join(archivados)}"))
    if problemas:
        print(_comun.tenue(f"    no se pudieron archivar: {', '.join(problemas)}"))
    if r["config_guardada"]:
        print(_comun.tenue("    su [agentes." + r["clave"] + "] de esta configuración quedó guardado con él"))
    print(_comun.tenue(f"    para traerlo de vuelta: telar agentes restaurar {r['carpeta'].rsplit('/', 1)[-1]}"))
    return 0
