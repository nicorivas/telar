"""Concesiones: lo que la persona le dejó hacer a un módulo, para no preguntárselo de nuevo (docs/propuestas/permisos.md).

Un módulo declara en su `modulo.toml` lo que pide (`[permisos] ordenes`); lo que la persona le concede queda aquí,
en `<estado>/concesiones.json`, por módulo y por orden:

    {"gantt": {"fecha": {"decision": "concedido", "desde": "2026-10-28T13:05:00"}}}

La primera puerta que lo usa es la de un lienzo: la página de un módulo, aislada y sin red, le pide a telar que corra
una orden por ella (`window.lienzo.pedir`, `POST /lienzo/pedir`). telar la corre solo si el módulo la declaró y la
persona la concedió; si no, responde qué hay que preguntar, y la página le pregunta a la persona. Lo concedido se
revoca con `telar modulos permisos <módulo> --quitar <orden>` (o borrando su entrada aquí).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

__all__ = ["DECISIONES", "leer", "decidir", "decision", "quitar"]

DECISIONES = ("concedido", "negado")


def _archivo(config) -> Path:
    return Path(config.estado) / "concesiones.json"


def leer(config) -> dict[str, dict[str, dict]]:
    try:
        datos = json.loads(_archivo(config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _escribir(config, datos: dict) -> None:
    archivo = _archivo(config)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    temporal = archivo.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(archivo)


def decision(config, modulo: str, orden: str) -> str:
    """«concedido», «negado» o "" (nunca se preguntó)."""
    return str(leer(config).get(modulo, {}).get(orden, {}).get("decision", ""))


def decidir(config, modulo: str, orden: str, decision_: str) -> None:
    if decision_ not in DECISIONES:
        raise ValueError(f"la decisión es una de {', '.join(DECISIONES)}")
    datos = leer(config)
    datos.setdefault(modulo, {})[orden] = {"decision": decision_, "desde": datetime.now().isoformat(timespec="seconds")}
    _escribir(config, datos)


def quitar(config, modulo: str, orden: str = "") -> bool:
    """Olvida lo decidido (una orden, o todas las del módulo): la próxima vez se pregunta. True si había algo."""
    datos = leer(config)
    if modulo not in datos or (orden and orden not in datos[modulo]):
        return False
    if orden:
        del datos[modulo][orden]
        if not datos[modulo]:
            del datos[modulo]
    else:
        del datos[modulo]
    _escribir(config, datos)
    return True
