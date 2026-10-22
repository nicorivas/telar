"""El estado deseado: lo declarado contra lo que hay, visto por el nodo (docs/propuestas/disparadores.md).

Primer paso: solo los residentes, y solo avisar. Un agente de `[agentes] carpeta` que vive aquí y es residente
(su `agente.toml` no dice `residente = false`) debería tener sesión. Hoy no tenerla no es una falla: se le abre
cuando le llega algo, y `[agente] max_vivos` cierra a los ociosos. Así que el nodo no la abre: anota en su
registro una línea cuando uno deja de tener sesión (o no la tiene al arrancar) y otra cuando vuelve, y deja lo
que vio en `<estado>/deseado.json`, que lee `telar doctor`:

    {"actualizado": "2026-10-22T10:00:00-03:00", "maquina": "servidor", "residentes": ["Faro", "Molino"],
     "residentes_sin_sesion": ["Faro"]}

`residentes` (los que viven aquí, con sesión o sin ella) separa «ninguno sin sesión» de «ninguno aquí»; un
archivo de antes no lo trae.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

#: más viejo que esto, el nodo no está corriendo: lo de `deseado.json` ya no dice cómo están las cosas
CADUCA = timedelta(minutes=10)


def ruta(config) -> Path:
    return Path(config.estado) / "deseado.json"


def residentes(locales: dict) -> list[str]:
    """Los residentes de lo que el nodo ve aquí (`Nodo.locales`), con sesión o sin ella, en orden."""
    return sorted(n for n, info in locales.items() if info.get("residente"))


def residentes_sin_sesion(locales: dict) -> list[str]:
    """Los residentes de lo que el nodo ve aquí (`Nodo.locales`) que no tienen sesión viva, en orden."""
    return sorted(n for n, info in locales.items() if info.get("residente") and not info.get("vivo"))


class Residentes:
    """Lo que el nodo anota de los residentes sin sesión: una línea cuando cambia, nunca una por vuelta."""

    def __init__(self):
        #: los que estaban sin sesión la última vez que se miró; None, que todavía no se mira
        self.antes: set[str] | None = None

    def mirar(self, sin_sesion) -> list[str]:
        ahora = set(sin_sesion)
        antes = self.antes if self.antes is not None else set()
        lineas = []
        for nombre in sorted(ahora - antes):
            lineas.append(f"«{nombre}» es residente y no tiene sesión: se le abre cuando le llegue algo")
        for nombre in sorted(antes - ahora):
            lineas.append(f"«{nombre}» tiene sesión de nuevo")
        self.antes = ahora
        return lineas


def escribir(config, maquina: str, sin_sesion, cuando: datetime | None = None, residentes=None) -> None:
    """`residentes`: los que viven aquí; None, que no se sabe (no se escribe la clave)."""
    destino = ruta(config)
    destino.parent.mkdir(parents=True, exist_ok=True)
    datos = {"actualizado": (cuando or datetime.now().astimezone()).isoformat(timespec="seconds"), "maquina": maquina}
    if residentes is not None:
        datos["residentes"] = list(residentes)
    datos["residentes_sin_sesion"] = list(sin_sesion)
    # un .tmp por proceso: dos nodos en la misma máquina (`telar serve --nodo` y `telar nodo`) no se pisan el
    # archivo a medio escribir; el último os.replace gana, y los dos escriben lo mismo
    tmp = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, destino)


def leer(config, ahora: datetime | None = None) -> dict | None:
    """Lo último que dejó el nodo, o None si no hay nada, no se lee o está viejo (el nodo no corre)."""
    try:
        datos = json.loads(ruta(config).read_text(encoding="utf-8"))
        cuando = datetime.fromisoformat(str(datos["actualizado"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    ahora = ahora or datetime.now().astimezone()
    if cuando.tzinfo is None:
        cuando = cuando.astimezone()
    if ahora - cuando > CADUCA or not isinstance(datos.get("residentes_sin_sesion"), list):
        return None
    return datos
