"""Los artes de la raíz: los dibujos animados de las tarjetas de la ventana de mundos que no vienen de fábrica, uno por
archivo en `<raiz>/.telar/arte/<clave>.txt` (docs/arte.md). telar solo los lista y entrega su texto tal cual
(`GET /arte`); los lee la página (pagina/src/componentes/arte.ts, `leerArteTexto`), que tiene también los de fábrica. Un
mundo elige el suyo con `[mundos.<n>] arte = "<clave>"`.

    from telar import arte
    arte.de_la_raiz(config)     # {"carpeta": "…/.telar/arte", "artes": [{"nombre": "faro", "texto": "…"}], "errores": {}}

Viven en la raíz y no en la configuración de la máquina: viajan por git a todas las máquinas, como lo demás que se
comparte (`<raiz>/.telar/temas.toml`, `mundos.toml`). Lo que no sirve (un nombre que no es una clave, un archivo muy
grande o que no es UTF-8) queda fuera, con su porqué en `errores`; nunca rompe la lista.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["CARPETA", "TOPE", "CLAVE", "carpeta_de", "de_la_raiz"]

#: dónde viven, relativo a la raíz
CARPETA = Path(".telar") / "arte"
#: lo más que puede pesar uno (un arte de 30 × 9 letras con 200 cuadros cabe de sobra)
TOPE = 64 * 1024
#: el nombre de un archivo de arte, sin `.txt`: la clave con que lo elige un mundo
CLAVE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
#: cuántos se leen a lo más
CUANTOS = 64


def carpeta_de(config) -> Path | None:
    """`<raiz>/.telar/arte` de esa configuración; None si no tiene raíz."""
    raiz = getattr(config, "raiz", None)
    return Path(raiz).expanduser() / CARPETA if raiz else None


def de_la_raiz(config) -> dict:
    """Los artes de la raíz, en orden alfabético: cada uno con su nombre (el del archivo, sin `.txt`) y su texto. `carpeta`,
    dónde se buscan ("" sin raíz); `errores`, nombre → por qué no se entregó."""
    carpeta = carpeta_de(config)
    salida: dict = {"carpeta": str(carpeta or ""), "artes": [], "errores": {}}
    if carpeta is None or not carpeta.is_dir():
        return salida
    for archivo in sorted(carpeta.glob("*.txt"))[:CUANTOS]:
        nombre = archivo.stem
        if not CLAVE.fullmatch(nombre):
            salida["errores"][archivo.name] = "el nombre va en minúsculas, números y guiones (es la clave con que lo elige un mundo)"
            continue
        try:
            if archivo.stat().st_size > TOPE:
                salida["errores"][nombre] = f"pesa más de {TOPE // 1024} KB"
                continue
            texto = archivo.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            salida["errores"][nombre] = "no está en UTF-8"
            continue
        except OSError as e:
            salida["errores"][nombre] = f"no se pudo leer: {e.strerror or e}"
            continue
        salida["artes"].append({"nombre": nombre, "texto": texto})
    return salida
