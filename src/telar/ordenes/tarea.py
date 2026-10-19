"""`telar tarea` — la ficha de una tarea de un proveedor, y sus acciones.

    telar tarea T203 --proveedor tareas --json          la ficha: una página con acciones
    telar tarea T203 --proveedor tareas --accion 0      corre la primera acción
    telar tarea T203 --proveedor tareas --accion 2 --texto "sigue viva"

Un clic en una tarea no tiene por qué abrir un agente: casi siempre basta leerla y decidir.
Si el proveedor declara `detalle` (`[proveedores.<n>] detalle = ["…", "--ver", "{id}"]`),
telar corre ese comando, que imprime la misma página que una sección (docs/contratos.md)
más una lista de `acciones`: correr un comando, llevar la tarea a su hilo o abrir un
enlace. La acción se elige por su número: el comando lo vuelve a dar el proveedor, nunca
quien pide, así que desde el dashboard solo se puede correr lo que el proveedor ofreció.
Un `{texto}` en el comando se reemplaza por lo que se escribió (`--texto`).

Una acción con `mensaje` abre además, después de su comando, un hilo nuevo con el agente y
ese primer prompt (`nombre_hilo` es su nombre): marcar hecha y procesar las secuelas de
inmediato, por ejemplo. Un `{texto}` en el mensaje también se reemplaza. Con `al_hilo: true`, el
mensaje no abre un hilo nuevo: va al hilo donde se trabaja la tarea, como `telar pendiente` (el de
su proyecto, retomándolo si duerme; sin proyecto, el agente de `[agentes] sin_proyecto`).
"""

from __future__ import annotations

from telar.ordenes import _comun
from telar.servicios import ErrorDeServicio
from telar.servicios import tareas as servicio
from telar.servicios.tareas import detalle_de  # noqa: F401 - quien lo importaba de aquí

AYUDA = "La ficha de una tarea de un proveedor, y correr una de sus acciones."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("tarea", AYUDA)
    p.epilog = __doc__
    p.add_argument("id", help="la tarea, como la da el proveedor")
    p.add_argument("--proveedor", default="tareas", help="de qué proveedor (tareas si no se dice)")
    p.add_argument("--accion", type=int, default=None, metavar="N", help="correr la acción N (desde 0)")
    p.add_argument("--rol", default="", metavar="ROL",
                   help="correr la acción con ese `rol` (hecha, fecha…), sin saber su número: un viaje en vez de dos")
    p.add_argument("--texto", default="", help="lo escrito, para una acción que lo pide")
    p.add_argument("--version", default=None, help="la versión que se leyó (la de la ficha): si la tarea cambió, no se hace")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        if o.accion is None and not o.rol:
            pagina = servicio.ficha(ctx, o.id, o.proveedor)
            if o.json:
                return _comun.escribir_json(pagina.model_dump(mode="json", exclude_unset=True))
            print(_comun.fuerte(getattr(pagina, "titulo", "") or o.id))
            for i, a in enumerate(getattr(pagina, "acciones", None) or []):
                print(f"  {i}  {a['nombre']}")
            return 0
        hecho = servicio.accion(ctx, o.id, o.proveedor, n=o.accion, rol=o.rol, texto=o.texto, version=o.version)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(hecho.model_dump(mode="json", exclude_defaults=False))
    print(f"{hecho.hecho}: hecho" if hecho.tipo == "comando" else hecho.model_dump())
    return 0
