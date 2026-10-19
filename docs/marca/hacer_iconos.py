#!/usr/bin/env python3
"""Genera el logo de la app de telar (los iconos del panel web, instalable como app) a partir de una grilla de cuadrados.

El logo es una «t» con un cursor al lado. Todo cae en una grilla invisible de celdas cuadradas: el
trazo mide 2 celdas, el cursor 3×6, y entre la «t» y el cursor hay 1 celda. El cursor arranca justo
debajo del brazo de la «t» y los dos se apoyan en la misma línea base. Las medidas no se tocan a mano:
se cambia `FORMAS` y se vuelve a correr.

    python3 docs/marca/hacer_iconos.py          escribe los PNG de vscode/media/app/ y el SVG

Cada tamaño elige una celda de píxeles enteros, para que ningún borde quede a medias. El ícono
«maskable» (el que Android recorta en círculo) usa una celda menor, para que el logo quepa en el
80 % central.
"""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parents[2] / "vscode" / "media" / "app"

FONDO = (46, 52, 64)       # #2e3440
AZUL = (136, 192, 208)     # #88c0d0
VERDE = (163, 190, 140)    # #a3be8c

#: el logo en celdas, sobre un cuadro de 10×10: (columna, fila, ancho, alto, color)
LADO = 10
FORMAS = [
    (2, 0, 2, 10, AZUL),    # el tronco de la «t»
    (0, 2, 6, 2, AZUL),     # su brazo
    (4, 8, 2, 2, AZUL),     # su pie
    (7, 4, 3, 6, VERDE),    # el cursor
]


def hex_(c):
    return "#%02x%02x%02x" % c


def dibujar(tam: int, celda: int) -> Image.Image:
    """Un ícono de `tam` píxeles con el logo centrado, a `celda` píxeles por celda."""
    im = Image.new("RGB", (tam, tam), FONDO)
    d = ImageDraw.Draw(im)
    x0 = y0 = (tam - LADO * celda) // 2
    for c, f, an, al, color in FORMAS:
        d.rectangle([x0 + c * celda, y0 + f * celda, x0 + (c + an) * celda - 1, y0 + (f + al) * celda - 1], fill=color)
    return im


def svg() -> str:
    """El mismo logo como SVG, en una grilla de 16×16 (el logo ocupa el centro, de 3 a 13)."""
    r = "\n".join(f'  <rect x="{c + 3}" y="{f + 3}" width="{an}" height="{al}" fill="{hex_(col)}"/>' for c, f, an, al, col in FORMAS)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">\n'
            f'  <rect width="16" height="16" fill="{hex_(FONDO)}"/>\n{r}\n</svg>\n')


if __name__ == "__main__":
    # tamaño → celda. 180 (apple-touch-icon) cabe en 11 px por celda con 35 px de margen.
    dibujar(512, 32).save(DESTINO / "icono-512.png")
    dibujar(192, 12).save(DESTINO / "icono-192.png")
    dibujar(180, 11).save(DESTINO / "apple-touch-icon.png")
    # el recortable: celda menor, que el círculo de Android no le coma las esquinas
    dibujar(512, 24).save(DESTINO / "icono-maskable-512.png")
    dibujar(192, 9).save(DESTINO / "icono-maskable-192.png")
    (DESTINO / "icono.svg").write_text(svg(), encoding="utf-8")
    print("listo:", ", ".join(sorted(p.name for p in DESTINO.glob("icon*")) + ["apple-touch-icon.png"]))
