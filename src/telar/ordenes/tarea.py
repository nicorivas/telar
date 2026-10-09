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

import subprocess

from telar.ordenes import _comun
from telar.ordenes.seccion import ESPERA, correr

AYUDA = "La ficha de una tarea de un proveedor, y correr una de sus acciones."


def detalle_de(ctx, proveedor: str) -> tuple[tuple[str, ...], str]:
    """El comando de ficha de ese proveedor, o por qué no hay."""
    p = next((x for x in ctx.config.proveedores_activos() if x.nombre == proveedor), None)
    if p is None:
        return (), f"no hay proveedor activo «{proveedor}»"
    detalle = p.opciones.get("detalle")
    if not isinstance(detalle, list) or not detalle or not all(isinstance(x, str) for x in detalle):
        return (), f"el proveedor «{proveedor}» no declara `detalle`"
    return tuple(detalle), ""


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("tarea", AYUDA)
    p.epilog = __doc__
    p.add_argument("id", help="la tarea, como la da el proveedor")
    p.add_argument("--proveedor", default="tareas", help="de qué proveedor (tareas si no se dice)")
    p.add_argument("--accion", type=int, default=None, metavar="N", help="correr la acción N (desde 0)")
    p.add_argument("--texto", default="", help="lo escrito, para una acción que lo pide")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    # las tareas de un proveedor que vive en otra máquina se leen y se cambian allá (ver telar.alla):
    # aquí hay una copia, y una acción corrida aquí la cambiaría a ella y no a las tareas
    from telar import alla

    config = getattr(ctx, "config", None)
    proveedor = next((x for x in config.proveedores_activos() if x.nombre == o.proveedor), None) if config else None
    en = alla.donde(config, proveedor) if proveedor is not None else ""
    if en:
        return alla.tarea_alla(config, en, argv)

    detalle, problema = detalle_de(ctx, o.proveedor)
    if problema:
        return _comun.queja(problema)
    pagina, problema = correr([w.replace("{id}", o.id) for w in detalle], f"la ficha de {o.id}")
    if problema:
        return _comun.queja(problema)

    if o.accion is None:
        if o.json:
            return _comun.escribir_json(pagina)
        print(_comun.fuerte(pagina.get("titulo", o.id)))
        for i, a in enumerate(pagina.get("acciones", [])):
            print(f"  {i}  {a['nombre']}")
        return 0

    acciones = pagina.get("acciones", [])
    if not 0 <= o.accion < len(acciones):
        return _comun.queja(f"{o.id} no tiene la acción {o.accion}")
    a = acciones[o.accion]
    tipo = a.get("tipo", "comando")
    if tipo != "comando":
        # llevar al hilo y abrir un enlace los hace quien dibuja: aquí solo se dice cuál
        resultado = {"tipo": tipo, "enlace": a.get("enlace", ""), "hecho": ""}
        return _comun.escribir_json(resultado) if o.json else (print(resultado) or 0)
    if a.get("pide") and not o.texto.strip() and any("{texto}" in w for w in [*a["comando"], a.get("mensaje", "")]):
        return _comun.queja(f"«{a['nombre']}» pide texto: --texto")
    palabras = [w.replace("{texto}", o.texto.strip()) for w in a["comando"]]
    fila = None
    if a.get("mensaje") and a.get("al_hilo"):
        # adónde va el mensaje se busca ANTES del comando: si el comando cierra la tarea («✓ hecha y
        # procesar ahora»), su proveedor ya no la lista y después no se la encontraría
        from telar.ordenes import pendiente

        fila = pendiente._buscar(ctx, _comun.tejer(ctx), o.id, proveedor=o.proveedor)
    try:
        r = subprocess.run(palabras, capture_output=True, text=True, timeout=ESPERA, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return _comun.queja(f"«{a['nombre']}» no corrió: {e}")
    if r.returncode != 0:
        return _comun.queja(f"«{a['nombre']}» salió con {r.returncode}: {r.stderr.strip()[-300:]}")
    salida = {"tipo": "comando", "hecho": a["nombre"], "salida": r.stdout.strip()[-500:], "hilo": ""}
    if a.get("mensaje") and a.get("al_hilo"):
        # al hilo donde se trabaja la tarea, no a uno nuevo: el de su proyecto (retomándolo si
        # duerme) o, sin proyecto, el agente de `[agentes] sin_proyecto` (ver `telar pendiente`)
        import io
        import json as mod_json
        from contextlib import redirect_stdout

        from telar.ordenes import pendiente

        texto = a["mensaje"].replace("{texto}", o.texto.strip())
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = pendiente.main([o.id, "--texto", texto, "--enviar", "--proveedor", o.proveedor, "--json"], ctx, fila=fila)
        if codigo != 0:
            return _comun.queja(f"«{a['nombre']}» se anotó, pero no pude llevarlo a su hilo")
        try:
            salida["hilo"] = mod_json.loads(buf.getvalue().strip().splitlines()[-1]).get("destino", "")
        except (ValueError, IndexError):
            salida["hilo"] = ""
    elif a.get("mensaje"):
        import datetime as dt

        from telar.ordenes.atajo import abrir

        nombre = " ".join(a.get("nombre_hilo", "").split())[:48] or f"{o.id} {dt.datetime.now():%m/%d %H:%M}"
        problema = abrir(ctx, nombre, a["mensaje"].replace("{texto}", o.texto.strip()))
        if problema:
            return _comun.queja(f"«{a['nombre']}» se hizo, pero no pude abrir el hilo: {problema}")
        salida["hilo"] = nombre
    if o.json:
        return _comun.escribir_json(salida)
    print(f"{a['nombre']}: hecho")
    return 0
