"""La ficha de una tarea de un proveedor, y correr una de sus acciones.

    from telar.servicios import tareas
    pagina = tareas.ficha(ctx, "T203")                       # la página, con sus `acciones`
    hecho = tareas.accion(ctx, "T203", rol="hecha")          # la acción por su rol
    hecho = tareas.accion(ctx, "T203", n=2, texto="sigue viva")

Lo usan `telar tarea` (telar.ordenes.tarea) y `/tareas/{id}` (telar.api). Las reglas (que el comando
lo da siempre el proveedor, nunca quien pide; `mensaje`, `al_hilo`) están en telar.ordenes.tarea.
"""

from __future__ import annotations

import json
import subprocess

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio, Pagina

__all__ = ["AccionHecha", "ficha", "accion", "detalle_de"]


class AccionHecha(BaseModel):
    """Lo que hizo una acción. `tipo` hilo o abrir los hace quien dibuja: aquí solo se dice cuál."""

    tipo: str
    hecho: str = ""
    salida: str = ""
    hilo: str = ""
    enlace: str = ""


def detalle_de(ctx, proveedor: str) -> tuple[tuple[str, ...], str]:
    """El comando de ficha de ese proveedor, o por qué no hay."""
    p = next((x for x in ctx.config.proveedores_activos() if x.nombre == proveedor), None)
    if p is None:
        return (), f"no hay proveedor activo «{proveedor}»"
    detalle = p.opciones.get("detalle")
    if not isinstance(detalle, list) or not detalle or not all(isinstance(x, str) for x in detalle):
        return (), f"el proveedor «{proveedor}» no declara `detalle`"
    return tuple(detalle), ""


def _alla(ctx, proveedor: str) -> str:
    """La máquina donde viven las tareas de ese proveedor (`en`), o "" si es esta."""
    from telar import alla

    p = next((x for x in ctx.config.proveedores_activos() if x.nombre == proveedor), None)
    return alla.donde(ctx.config, p) if p is not None else ""


def _pedir_alla(ctx, en: str, argv: list[str]) -> dict:
    """Corre `telar tarea …` en la máquina donde viven las tareas y devuelve su JSON: aquí hay una copia, y
    una acción corrida aquí la cambiaría a ella y no a las tareas (ver telar.alla)."""
    from telar import alla
    from telar import bus as mod_bus

    r = mod_bus.pedir(ctx.config, en, "tarea", {"argv": [*argv, "--json"]}, espera=alla.ESPERA * 2 + 10)
    if not r.get("ok"):
        raise ErrorDeServicio(f"las tareas viven en {en} y no respondió: {r.get('error', '')}", 502)
    if int(r.get("codigo", 1)) != 0:
        linea = (r.get("error_salida", "").strip().splitlines() or [f"{en} no pudo"])[-1]
        raise ErrorDeServicio(linea.removeprefix("telar: "), 400)
    try:
        return json.loads(r.get("salida", ""))
    except ValueError as e:
        raise ErrorDeServicio(f"{en} no devolvió JSON", 502) from e


def ficha(ctx, id: str, proveedor: str = "tareas") -> Pagina:
    """La ficha de la tarea: la página que imprime el `detalle` del proveedor, con sus acciones."""
    from telar.ordenes.seccion import correr

    en = _alla(ctx, proveedor)
    if en:
        return Pagina(**_pedir_alla(ctx, en, [id, "--proveedor", proveedor]))
    detalle, problema = detalle_de(ctx, proveedor)
    if problema:
        raise ErrorDeServicio(problema, 404)
    pagina, problema = correr([w.replace("{id}", id) for w in detalle], f"la ficha de {id}")
    if problema:
        raise ErrorDeServicio(problema, 502)
    return Pagina(**pagina)


def accion(ctx, id: str, proveedor: str = "tareas", *, n: int | None = None, rol: str = "", texto: str = "") -> AccionHecha:
    """Corre una acción de la ficha, por su número (`n`) o por su `rol`. El comando sale de la ficha que
    vuelve a dar el proveedor, nunca de quien pide."""
    from telar.ordenes import _comun
    from telar.ordenes.seccion import ESPERA

    if n is None and not rol:
        raise ErrorDeServicio("¿cuál acción? un número o un rol")
    en = _alla(ctx, proveedor)
    if en:
        argv = [id, "--proveedor", proveedor, *(["--rol", rol] if rol else ["--accion", str(n)]),
                *(["--texto", texto] if texto else [])]
        return AccionHecha(**_pedir_alla(ctx, en, argv))
    pagina = ficha(ctx, id, proveedor).model_dump()
    acciones = pagina.get("acciones") or []
    if rol:
        # la acción por su rol: quien la pide (el ✓ de una lista) no tiene que leer la ficha antes
        n = next((i for i, a in enumerate(acciones) if a.get("rol") == rol), None)
        if n is None:
            raise ErrorDeServicio(f"{id} no tiene una acción «{rol}»: ábrela", 404)
    if not 0 <= n < len(acciones):
        raise ErrorDeServicio(f"{id} no tiene la acción {n}", 404)
    a = acciones[n]
    tipo = a.get("tipo", "comando")
    if tipo != "comando":
        return AccionHecha(tipo=tipo, enlace=a.get("enlace", ""))
    texto = texto.strip()
    if a.get("pide") and not texto and any("{texto}" in w for w in [*a["comando"], a.get("mensaje", "")]):
        raise ErrorDeServicio(f"«{a['nombre']}» pide texto")
    palabras = [w.replace("{texto}", texto) for w in a["comando"]]
    fila = None
    if a.get("mensaje") and a.get("al_hilo"):
        # adónde va el mensaje se busca ANTES del comando: si el comando cierra la tarea («✓ hecha y
        # procesar ahora»), su proveedor ya no la lista y después no se la encontraría
        from telar.ordenes import pendiente

        fila = pendiente._buscar(ctx, _comun.tejer(ctx), id, proveedor=proveedor)
    try:
        r = subprocess.run(palabras, capture_output=True, text=True, timeout=ESPERA, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ErrorDeServicio(f"«{a['nombre']}» no corrió: {e}", 502) from e
    if r.returncode != 0:
        raise ErrorDeServicio(f"«{a['nombre']}» salió con {r.returncode}: {r.stderr.strip()[-300:]}", 502)
    hecho = AccionHecha(tipo="comando", hecho=a["nombre"], salida=r.stdout.strip()[-500:])
    if a.get("mensaje") and a.get("al_hilo"):
        hecho.hilo = _al_hilo(ctx, id, proveedor, a["mensaje"].replace("{texto}", texto), fila, a["nombre"])
    elif a.get("mensaje"):
        import datetime as dt

        from telar.ordenes.atajo import abrir

        nombre = " ".join(a.get("nombre_hilo", "").split())[:48] or f"{id} {dt.datetime.now():%m/%d %H:%M}"
        problema = abrir(ctx, nombre, a["mensaje"].replace("{texto}", texto))
        if problema:
            raise ErrorDeServicio(f"«{a['nombre']}» se hizo, pero no pude abrir el hilo: {problema}", 502)
        hecho.hilo = nombre
    return hecho


def _al_hilo(ctx, id: str, proveedor: str, mensaje: str, fila, nombre: str) -> str:
    """Al hilo donde se trabaja la tarea, no a uno nuevo: el de su proyecto (retomándolo si duerme) o,
    sin proyecto, el agente de `[agentes] sin_proyecto` (ver `telar pendiente`)."""
    import io
    from contextlib import redirect_stdout

    from telar.ordenes import pendiente

    buf = io.StringIO()
    with redirect_stdout(buf):
        codigo = pendiente.main([id, "--texto", mensaje, "--enviar", "--proveedor", proveedor, "--json"], ctx, fila=fila)
    if codigo != 0:
        raise ErrorDeServicio(f"«{nombre}» se anotó, pero no pude llevarlo a su hilo", 502)
    try:
        return json.loads(buf.getvalue().strip().splitlines()[-1]).get("destino", "")
    except (ValueError, IndexError):
        return ""
