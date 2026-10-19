"""`telar tipo` — los objetos de un tipo (las tareas): leerlos, crearlos y aplicarles sus acciones.

    telar tipo tarea lista [--todas] [--json]           las abiertas (con --todas, también las cerradas)
    telar tipo tarea ver T84 [--json]                   una, con su versión
    telar tipo tarea crear --params '{"titulo": "Llamar a Ana", "vence": "2026-10-30"}'
    telar tipo tarea completar T84 [--params '{"nota": "listo"}'] [--version V]
    telar tipo tarea reagendar T84 --params '{"fecha": "+7d"}'
    telar tipo tarea borrar T84 [--version V]

Las acciones son las del tipo (telar.tipos.tarea.ACCIONES: completar, cerrar, reabrir, algun_dia,
esperar, reagendar, asignar, anotar, proponer, responder, editar, secuela, conectar) y sus parámetros van
como JSON en `--params`. Con `--version` (la que dio `ver`), la acción solo se hace si el objeto no
cambió desde entonces.

Una sola máquina escribe los archivos (`[tipos.tarea] carpeta`); en las demás (`[tipos.tarea] en`), esta
orden se le pide a ella por el bus. Quien escribe commitea y sube el archivo. Con `--json`, la salida es
el objeto y su versión; si no se pudo, `{"error": …, "codigo": …}` (409: cambió o no se puede; 404: no
existe; 422: el pedido no sirve).
"""

from __future__ import annotations

import json

from telar.ordenes import _comun
from telar.servicios import ErrorDeServicio
from telar.servicios import tipos as servicio

AYUDA = "Los objetos de un tipo (las tareas): leerlos, crearlos y aplicarles sus acciones."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("tipo", AYUDA)
    p.epilog = __doc__
    p.add_argument("tipo", help="el tipo: tarea")
    p.add_argument("verbo", help="lista, ver, crear, borrar o una acción del tipo")
    p.add_argument("id", nargs="?", default="", help="el objeto (salvo en lista y crear)")
    p.add_argument("--params", default="{}", help="los parámetros, en JSON")
    p.add_argument("--version", default=None, help="la versión que se leyó: si cambió, no se hace")
    p.add_argument("--todas", action="store_true", help="en lista: también las cerradas")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        try:
            params = json.loads(o.params)
        except ValueError as e:
            raise ErrorDeServicio(f"--params: no es JSON ({e})", 422) from e
        if not isinstance(params, dict):
            raise ErrorDeServicio("--params: se esperaba un objeto JSON", 422)
        if o.verbo == "lista":
            r = servicio.lista(ctx, o.tipo, todas=o.todas)
        elif o.verbo == "crear":
            r = servicio.crear(ctx, params, clave=o.tipo)
        elif not o.id:
            raise ErrorDeServicio(f"«{o.verbo}» va con el identificador del objeto", 422)
        elif o.verbo == "ver":
            r = servicio.obtener(ctx, o.id, o.tipo)
        elif o.verbo == "borrar":
            r = servicio.borrar(ctx, o.id, version=o.version, clave=o.tipo)
        else:
            r = servicio.aplicar(ctx, o.id, o.verbo, params, version=o.version, clave=o.tipo)
    except ErrorDeServicio as e:
        if o.json:
            _comun.escribir_json({"error": str(e), "codigo": e.codigo, **e.datos})
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    if o.verbo == "lista":
        for t in r.tareas:
            print(f"{t.id}  {t.estado:<10} {t.titulo}")
        for id, motivo in r.fallas.items():
            print(f"{id}: no se pudo leer ({motivo})")
    elif o.verbo == "borrar":
        print(f"{r.id}: borrada")
    else:
        print(f"{r.id}  {r.estado}  {r.titulo}  (versión {r.version})")
    return 0
