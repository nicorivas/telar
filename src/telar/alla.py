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

    cfg = next((p for p in config.proveedores_activos() if p.nombre == nombre), None)
    if cfg is None:
        return {"ok": False, "error": f"no hay proveedor activo «{nombre}» en esta máquina"}
    items, fallas = mod_prov.consultar([cfg], date.fromisoformat(dia) if dia else date.today())
    return {"ok": True, "items": [item_a_dict(i) for i in items], "fallas": fallas}


def consultar(config, proveedores: list, dia: date) -> tuple[list[Item], list[str]]:
    """Como `proveedores.consultar`, pero los que viven en otra máquina se le piden a ella."""
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


def tarea_aqui(argv: list[str]) -> dict:
    """Corre `telar tarea …` en esta máquina (lo que responde el nodo al pedido `tarea`)."""
    try:
        r = subprocess.run([sys.executable, "-m", "telar", "tarea", *argv], capture_output=True, text=True,
                           timeout=ESPERA * 2, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": f"telar tarea no corrió: {e}"}
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
