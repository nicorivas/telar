"""`telar objeto` — cualquier objeto por su dirección: verlo y aplicarle una acción (telar.objetos).

    telar objeto tarea:T366                        lo que es: título, estado, campos, enlaces y acciones
    telar objeto hilo:Telar --json
    telar objeto tarea:T366 completar --params '{"nota": "listo"}' [--version V]
    telar objeto hilo:Faro mensaje --params '{"texto": "¿quedó?"}'
    telar objeto --tipos                           los tipos que hay, los de fábrica y los de los módulos
    telar objeto --buscar "revisa tarea:T366 y hilo:Faro"   las direcciones que hay en un texto

Una dirección es `tipo:id`, y `@máquina` cuando importa: `tarea:T366`, `hilo:Telar`,
`proyecto:proyectos/faro`, `archivo:telar:docs/x.md`. Con `--json`, la salida es el objeto (o lo que
hizo la acción); si no se pudo, `{"error": …, "codigo": …}` (404: no existe; 409: cambió; 422: el pedido no
sirve).
"""

from __future__ import annotations

import json

from telar.ordenes import _comun
from telar.servicios import ErrorDeServicio

AYUDA = "Cualquier objeto por su dirección (tarea:T366, hilo:Telar…): verlo y aplicarle una acción."


def main(argv: list[str], ctx) -> int:
    from telar import objetos

    p = _comun.analizador("objeto", AYUDA)
    p.epilog = __doc__
    p.add_argument("direccion", nargs="?", default="", help="tipo:id, como tarea:T366")
    p.add_argument("accion", nargs="?", default="", help="una de sus acciones (sin ella, verlo)")
    p.add_argument("--params", default="{}", help="los parámetros de la acción, en JSON")
    p.add_argument("--version", default="", help="la versión que se leyó: si cambió, no se hace")
    p.add_argument("--tipos", action="store_true", help="los tipos que hay")
    p.add_argument("--buscar", default=None, metavar="TEXTO", help="las direcciones que aparecen en un texto")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        if o.tipos:
            lista = [{"tipo": n, "descripcion": t.descripcion, "modulo": getattr(t, "modulo", "")}
                     for n, t in sorted(objetos.tipos(ctx).items())]
            if o.json:
                return _comun.escribir_json({"tipos": lista})
            for t in lista:
                print(f"{t['tipo']:<12}{t['descripcion']}" + (_comun.tenue(f"  (módulo {t['modulo']})") if t["modulo"] else ""))
            return 0
        if o.buscar is not None:
            halladas = [str(d) for d in objetos.buscar(ctx, o.buscar)]
            if o.json:
                return _comun.escribir_json({"direcciones": halladas})
            print("\n".join(halladas))
            return 0
        if not o.direccion:
            raise ErrorDeServicio("¿qué objeto? telar objeto tipo:id (telar objeto --tipos dice cuáles hay)", 422)
        if o.accion:
            try:
                params = json.loads(o.params)
            except ValueError as e:
                raise ErrorDeServicio(f"--params: no es JSON ({e})", 422) from e
            if not isinstance(params, dict):
                raise ErrorDeServicio("--params: se esperaba un objeto JSON", 422)
            r = objetos.hacer(ctx, o.direccion, o.accion, params, o.version)
        else:
            r = objetos.ver(ctx, o.direccion)
    except ErrorDeServicio as e:
        if o.json:
            _comun.escribir_json({"error": str(e), "codigo": e.codigo, **e.datos})
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    if o.accion:
        print(f"{r.direccion}: {r.accion} hecho")
        objeto = r.objeto
        if objeto is None:
            if r.resultado:
                print(_comun.tenue(json.dumps(r.resultado, ensure_ascii=False)[:500]))
            return 0
    else:
        objeto = r
    _imprimir(objeto)
    return 0


def _imprimir(x) -> None:
    print(f"{x.direccion}" + (f"  {x.estado}" if x.estado else "") + (f"  · en {x.maquina}" if x.maquina else ""))
    if x.titulo and x.titulo != x.id:
        print(f"  {x.titulo}")
    if x.resumen:
        print(_comun.tenue(f"  {x.resumen[:300]}"))
    for k, v in x.campos.items():
        print(_comun.tenue(f"  {k}: {v if not isinstance(v, (list, dict)) else json.dumps(v, ensure_ascii=False)}"))
    if x.enlaces:
        print("  enlaces: " + " · ".join(x.enlaces))
    if x.acciones:
        print("  acciones: " + ", ".join(a.nombre for a in x.acciones))
