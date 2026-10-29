#!/usr/bin/env python3
"""Rehace la letra de íconos de la página (media/css/iconos.css): los íconos que usa, recortados de Symbols Nerd Font Mono.

    uv run --with fonttools --with brotli python3 scripts/iconos.py [ruta/a/SymbolsNerdFontMono-Regular.ttf]

Busca en src/ y en media/css/ los códigos de la zona privada de Unicode (`\\u{ea70}` en TypeScript, `\\ea70` en CSS),
recorta la letra a solo esos y la escribe como `@font-face` en base64 (la página no pide archivos aparte). Correrlo
cada vez que se agrega o se quita un ícono (web/iconos.ts). La letra es de Nerd Fonts (MIT), con los íconos de
Codicons (CC BY 4.0).
"""

from __future__ import annotations

import base64
import io
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

AQUI = Path(__file__).resolve().parent.parent
LETRA = Path.home() / "Library" / "Fonts" / "SymbolsNerdFontMono-Regular.ttf"
SALIDA = AQUI / "media" / "css" / "iconos.css"


def usados() -> list[int]:
    codigos: set[int] = set()
    for p in [*(AQUI / "src").rglob("*.ts"), *(AQUI / "media" / "css").glob("*.css")]:
        if p == SALIDA:
            continue
        texto = p.read_text(encoding="utf-8")
        codigos |= {int(c, 16) for c in re.findall(r"\\u\{([0-9a-fA-F]{4,5})\}", texto)}
        codigos |= {int(c, 16) for c in re.findall(r"content:\s*['\"]\\([0-9a-fA-F]{4,5})['\"]", texto)}
    return sorted(c for c in codigos if 0xE000 <= c <= 0xF8FF or 0xF0000 <= c <= 0xFFFFD)


def main(argv: list[str]) -> int:
    letra = Path(argv[0]) if argv else LETRA
    codigos = usados()
    fuente = TTFont(letra)
    faltan = [hex(c) for c in codigos if c not in fuente.getBestCmap()]
    if faltan:
        print(f"no están en {letra.name}: {', '.join(faltan)}", file=sys.stderr)
        return 1
    opciones = subset.Options()
    opciones.flavor = "woff2"
    opciones.layout_features = []
    opciones.name_IDs = []
    recorte = subset.Subsetter(options=opciones)
    recorte.populate(unicodes=codigos)
    recorte.subset(fuente)
    fuente.flavor = "woff2"
    salida = io.BytesIO()
    fuente.save(salida)
    b64 = base64.b64encode(salida.getvalue()).decode()
    SALIDA.write_text(
        "/* La letra de íconos de la página (Codicons, de Nerd Fonts): la escribe scripts/iconos.py con solo los que se\n"
        "   usan (web/iconos.ts). No editar aquí. Un ícono va con la clase `.i`, o solo: la letra de la página la tiene\n"
        "   como respaldo, así que un código de íconos se ve en cualquier texto. */\n"
        f"@font-face {{ font-family: iconos; src: url(\"data:font/woff2;base64,{b64}\") format('woff2'); }}\n"
        ".i { font-family: iconos, monospace; font-style: normal; font-weight: normal; }\n", encoding="utf-8")
    print(f"{len(codigos)} íconos, {len(salida.getvalue())} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
