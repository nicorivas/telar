"""`telar agentes` — los agentes residentes y lo que declara cada uno en su `agente.toml`.

    telar agentes              uno por línea: nombre, carpeta, modelo, para qué es
    telar agentes faro         uno entero: lo que declara, lo que todavía no se usa y lo que no se pudo leer
    telar agentes --json       el contrato (docs/contratos.md)

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
        print(_comun.tenue("no hay agentes residentes: [agentes] carpeta = \"agentes\" y una carpeta con su CLAUDE.md"))
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
