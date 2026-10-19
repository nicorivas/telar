"""Leer y escribir archivos de esta máquina desde la página (el dashboard en el navegador), con límites.

En VS Code y en el panel en Node el dashboard lee el disco directo (el README de un proyecto, la
preparación de una reunión, la página y la memoria de un lienzo). En el navegador no hay disco: lo pide aquí.

- **Leer**: un archivo bajo la raíz del repositorio (`[telar] raiz`), uno que la configuración declara
  para una app (`[apps.*] archivo` y `memoria`), o el lienzo de una página que esta misma API entregó (el
  programa de una app con `pagina` puede dejarlo donde quiera, p. ej. en `~/.local/state`). Nada de `..`
  que escape, hasta 2 MB.
- **Buscar**: los `.md` de una carpeta de la raíz, hasta tres niveles (sin ocultos, `node_modules` ni
  `assets`), con su fecha: para encontrar la preparación o la minuta más reciente de una reunión.
- **Escribir**: solo la memoria de un lienzo, un `.json` válido bajo la raíz, declarado como `memoria` de
  una app o nombrado por una página entregada, hasta 4 MB, de una vez (temporal y rename).

Lo usan `GET /archivos`, `GET /archivos/md` y `PUT /archivos` de la API; detrás de la llave de la página.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio

TOPE_LEER = 2 * 1024 * 1024
TOPE_ESCRIBIR = 4_000_000
NO_ENTRAR = {"node_modules", "assets"}

#: los lienzos (página y memoria) que nombraron las páginas que entregó esta API: se pueden leer, y su
#: memoria escribir, aunque estén fuera de la raíz. Lo que telar mismo entregó, nada que pida la página.
_de_paginas: dict[str, set[Path]] = {"archivo": set(), "memoria": set()}


def anotar_lienzos(pagina):
    """Recuerda los lienzos de una página que la API va a entregar; la devuelve tal cual."""
    for b in getattr(pagina, "bloques", None) or []:
        lienzo = b.get("lienzo") if isinstance(b, dict) else None
        if not isinstance(lienzo, dict):
            continue
        for campo in ("archivo", "memoria"):
            v = lienzo.get(campo)
            if isinstance(v, str) and v:
                _de_paginas[campo].add(Path(v).expanduser().resolve())
    return pagina


class Archivo(BaseModel):
    ruta: str
    texto: str
    mtime: float
    recortado: bool = False


class Hallado(BaseModel):
    ruta: str
    mtime: float


class Hallados(BaseModel):
    archivos: list[Hallado]


class Escrito(BaseModel):
    ruta: str
    bytes: int


def _raiz(ctx) -> Path:
    return Path(ctx.config.raiz).expanduser().resolve()


def _de_apps(ctx, campo: str) -> set[Path]:
    salida = set()
    for a in getattr(ctx.config, "apps", ()):
        v = getattr(a, campo, "")
        if v:
            salida.add(Path(v).expanduser().resolve())
    return salida | _de_paginas[campo]


def _resolver(ctx, ruta: str) -> Path:
    if not ruta or "\x00" in ruta:
        raise ErrorDeServicio("¿qué archivo?", 422)
    p = Path(ruta).expanduser()
    if not p.is_absolute():
        p = _raiz(ctx) / p
    return p.resolve()


def _bajo_raiz(ctx, p: Path) -> bool:
    try:
        p.relative_to(_raiz(ctx))
        return True
    except ValueError:
        return False


def leer(ctx, ruta: str) -> Archivo:
    p = _resolver(ctx, ruta)
    if not (_bajo_raiz(ctx, p) or p in _de_apps(ctx, "archivo") | _de_apps(ctx, "memoria")):
        raise ErrorDeServicio(f"{ruta}: fuera de la raíz y de las apps declaradas", 403)
    if not p.is_file():
        raise ErrorDeServicio(f"no hay {ruta}", 404)
    with open(p, "rb") as f:
        datos = f.read(TOPE_LEER + 1)
    return Archivo(ruta=str(p), texto=datos[:TOPE_LEER].decode("utf-8", "replace"), mtime=p.stat().st_mtime,
                   recortado=len(datos) > TOPE_LEER)


def buscar_md(ctx, carpeta: str, hondo: int = 3) -> Hallados:
    base = _resolver(ctx, carpeta)
    if not _bajo_raiz(ctx, base):
        raise ErrorDeServicio(f"{carpeta}: fuera de la raíz", 403)
    hallados: list[Hallado] = []

    def recorrer(d: Path, nivel: int) -> None:
        try:
            entradas = list(os.scandir(d))
        except OSError:
            return
        for e in entradas:
            if e.name.startswith(".") or e.name in NO_ENTRAR:
                continue
            if e.is_dir(follow_symlinks=False) and nivel < hondo:
                recorrer(Path(e.path), nivel + 1)
            elif e.is_file() and e.name.endswith(".md"):
                try:
                    hallados.append(Hallado(ruta=e.path, mtime=e.stat().st_mtime))
                except OSError:
                    pass

    recorrer(base, 0)
    return Hallados(archivos=hallados)


def escribir(ctx, ruta: str, texto: str) -> Escrito:
    p = _resolver(ctx, ruta)
    if p.suffix != ".json" or not (_bajo_raiz(ctx, p) or p in _de_apps(ctx, "memoria")):
        raise ErrorDeServicio(f"{ruta}: solo se escribe la memoria de un lienzo (un .json de la raíz o de una app)", 403)
    if len(texto) > TOPE_ESCRIBIR:
        raise ErrorDeServicio("pasa de 4 MB", 413)
    try:
        json.loads(texto)
    except ValueError as e:
        raise ErrorDeServicio("no es JSON", 422) from e
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, p)
    return Escrito(ruta=str(p), bytes=len(texto.encode("utf-8")))
