"""Un proveedor que vive en otra máquina: se lo consulta allá, y sus fichas y acciones corren allá.

    [proveedores.tareas]
    tipo = "comando"
    comando = ["…/telar-tareas"]
    en = "servidor"        # la máquina donde viven las tareas; "" (o esta misma) es aquí

Las tareas de un proveedor son archivos de una máquina. Leer la copia de otra (sincronizada por git)
mostraba lo de hace horas, y marcar una hecha desde ahí cambiaba la copia, no las tareas. Con `en`,
esta máquina le pide al nodo de allá, por el bus, lo que el proveedor da (`proveedor`) y que corra allá
la ficha o la acción de una tarea (`tarea`). Si allá no responde, se lee lo de aquí y se dice; una
acción, en cambio, no se corre aquí: cambiaría la copia equivocada.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import date, datetime

from telar.modelo import Item

#: cuánto se espera a la otra máquina: el proveedor puede tardar (el calendario baja entero)
ESPERA = 60


def donde(config, proveedor) -> str:
    """La máquina donde vive un proveedor, si es otra y hay bus; "" si es aquí."""
    from telar import bus as mod_bus

    en = str((getattr(proveedor, "opciones", {}) or {}).get("en") or "").strip()
    if not en or not mod_bus.hay_bus(config) or en == mod_bus.maquina(config):
        return ""
    return en


def item_a_dict(i: Item) -> dict:
    return {"proveedor": i.proveedor, "id": i.id, "titulo": i.titulo,
            "cuando": i.cuando.isoformat() if i.cuando else None, "hilo": i.hilo, "url": i.url,
            "clase": i.clase, "datos": i.datos}


def item_de_dict(d: dict) -> Item:
    cuando = d.get("cuando")
    return Item(proveedor=str(d.get("proveedor", "")), id=str(d.get("id", "")), titulo=str(d.get("titulo", "")),
                cuando=datetime.fromisoformat(cuando) if cuando else None, hilo=str(d.get("hilo", "")),
                url=str(d.get("url", "")), clase=str(d.get("clase", "")), datos=dict(d.get("datos") or {}))


def consultar_aqui(config, nombre: str, dia: str) -> dict:
    """Lo que da un proveedor de esta máquina (lo que responde el nodo al pedido `proveedor`)."""
    from telar import proveedores as mod_prov
    from telar.ordenes import _comun

    _comun.asegurar_proveedores(config)  # los proveedores se registran al importarse: sin esto, «ninguno»
    cfg = next((p for p in config.proveedores_activos() if p.nombre == nombre), None)
    if cfg is None:
        return {"ok": False, "error": f"no hay proveedor activo «{nombre}» en esta máquina"}
    items, fallas = mod_prov.consultar([cfg], date.fromisoformat(dia) if dia else date.today())
    return {"ok": True, "items": [item_a_dict(i) for i in items], "fallas": fallas}


# ── lo consultado, por un rato (en `telar serve`) ──
#
# El día (`GET /hoy`) pregunta a los proveedores (el calendario, las tareas, que pueden vivir en otra máquina): segundos
# de espera cada vez. En el servicio lo piden a la vez la página, el teléfono y su propio refresco: con MEMORIA, lo
# consultado sirve unos segundos a todos, y quien llega mientras otro consulta lo mismo espera esa consulta en vez de
# hacer otra. Cualquier pedido a la API que cambia algo lo olvida (`olvidar`, telar.api): marcar una tarea hecha y
# volver a pedir el día trae la lista nueva. Lo que cambie por otro lado (un agente que cierra una tarea con la CLI) se
# ve a lo más MEMORIA segundos después. Una consulta con fallas no se guarda: la próxima vuelve a preguntar. Fuera del
# servicio (la CLI) MEMORIA es 0 y se consulta siempre.

#: cuántos segundos sirve lo consultado (0: nada se guarda). `telar serve` lo pone en MEMORIA_SERVE
MEMORIA = 0.0
MEMORIA_SERVE = 30.0
_guardado: dict[tuple, tuple[float, list[Item], list[str]]] = {}
_candados: dict[tuple, threading.Lock] = {}
_candado = threading.Lock()
#: cuántas veces se olvidó: una consulta que empezó antes de un olvido no se guarda (puede traer lo de antes)
_olvidos = 0


def olvidar() -> None:
    """Lo consultado ya no sirve (algo cambió): la próxima vez se pregunta de nuevo."""
    global _olvidos
    with _candado:
        _olvidos += 1
        _guardado.clear()


def _clave(proveedores: list, dia: date) -> tuple:
    return (dia.isoformat(), tuple((p.nombre, repr(sorted((getattr(p, "opciones", {}) or {}).items()))) for p in proveedores))


def consultar(config, proveedores: list, dia: date) -> tuple[list[Item], list[str]]:
    """Como `proveedores.consultar`, pero los que viven en otra máquina se le piden a ella. Con MEMORIA, lo de hace menos
    de MEMORIA segundos, si no se olvidó desde entonces."""
    if MEMORIA <= 0:
        return _consultar(config, proveedores, dia)
    clave = _clave(proveedores, dia)
    with _candado:
        uno = _candados.setdefault(clave, threading.Lock())
    with uno:
        with _candado:
            hay = _guardado.get(clave)
            desde = _olvidos
        if hay is not None and time.monotonic() - hay[0] < MEMORIA:
            return list(hay[1]), list(hay[2])
        items, fallas = _consultar(config, proveedores, dia)
        with _candado:
            if not fallas and desde == _olvidos:
                _guardado[clave] = (time.monotonic(), list(items), list(fallas))
        return items, fallas


def _consultar(config, proveedores: list, dia: date) -> tuple[list[Item], list[str]]:
    from telar import bus as mod_bus
    from telar import proveedores as mod_prov

    aqui = [p for p in proveedores if not donde(config, p)]
    items, fallas = mod_prov.consultar(aqui, dia)
    for p in proveedores:
        en = donde(config, p)
        if not en or not p.activo:
            continue
        r = mod_bus.pedir(config, en, "proveedor", {"nombre": p.nombre, "dia": dia.isoformat()}, espera=ESPERA)
        if r.get("ok"):
            items.extend(item_de_dict(d) for d in r.get("items", []))
            fallas.extend(r.get("fallas", []))
            continue
        # allá no responde: lo de aquí, que puede estar atrasado, y dicho
        mas, fallas_aqui = mod_prov.consultar([p], dia)
        items.extend(mas)
        fallas.extend(fallas_aqui)
        fallas.append(f"{p.nombre}: {en} no respondió ({r.get('error', '')[:80]}); se leyó la copia de aquí, que puede estar atrasada")
    return items, fallas


def tarea_aqui(argv: list[str], orden: str = "tarea") -> dict:
    """Corre `telar tarea …` (o `telar tipo …`, `telar periodicos …`) en esta máquina: lo que responde el
    nodo a los pedidos `tarea`, `tipo` y `periodicos`."""
    if orden not in ("tarea", "tipo", "periodicos", "equipo", "hilo"):
        return {"ok": False, "error": f"no se corre «{orden}» para otra máquina"}
    try:
        r = subprocess.run([sys.executable, "-m", "telar", orden, *argv], capture_output=True, text=True,
                           timeout=ESPERA * 2, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": f"telar {orden} no corrió: {e}"}
    return {"ok": True, "codigo": r.returncode, "salida": r.stdout, "error_salida": r.stderr}


def tarea_alla(config, en: str, argv: list[str]) -> int:
    """Pide a la máquina `en` que corra `telar tarea …` y deja aquí su salida tal cual."""
    from telar import bus as mod_bus

    r = mod_bus.pedir(config, en, "tarea", {"argv": argv}, espera=ESPERA * 2 + 10)
    if not r.get("ok"):
        print(f"telar: las tareas viven en {en} y no respondió: {r.get('error', '')}", file=sys.stderr)
        return 2
    sys.stdout.write(r.get("salida", ""))
    sys.stderr.write(r.get("error_salida", ""))
    return int(r.get("codigo", 1))
