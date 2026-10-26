"""Leer y escribir archivos de esta máquina desde la página (el dashboard en el navegador), con límites.

En VS Code el dashboard lee el disco directo (el README de un proyecto, la
preparación de una reunión, la página y la memoria de un lienzo). En el navegador no hay disco: lo pide aquí.

- **Leer**: un archivo bajo la raíz del repositorio (`[telar] raiz`) o de uno de `[repos]`, uno que la configuración declara
  para una app (`[apps.*] archivo` y `memoria`), o el lienzo de una página que esta misma API entregó (el
  programa de una app con `pagina` puede dejarlo donde quiera, p. ej. en `~/.local/state`). Nada de `..`
  que escape, hasta 2 MB.
- **Buscar**: los `.md` de una carpeta de la raíz, hasta tres niveles (sin ocultos, `node_modules` ni
  `assets`), con su fecha: para encontrar la preparación o la minuta más reciente de una reunión.
- **Escribir**: solo la memoria de un lienzo, un `.json` válido bajo la raíz, declarado como `memoria` de
  una app o nombrado por una página entregada, hasta 4 MB, de una vez (temporal y rename).

- **En otra máquina**: `leer_en` con `maquina` se lo pide al nodo de esa máquina por el bus, que lo lee con
  sus propios límites (su raíz, sus repos, sus apps): el visor de la página abre `servidor:docs/x.md` sin
  copiarlo antes.
- **Dejar en la entrada**: lo que se arrastra a la terminal de un hilo (web/terminal.ts) y el hilo no puede
  leer donde está. Va a la carpeta de entrada de la máquina del hilo: aquí, la de `[bus] entrada` (por
  defecto `~/telar-entrada`); en otra, su entrada. Son los bytes que sube la página (`desde_bytes`), o un
  archivo de esta máquina nombrado por su ruta (`desde_ruta`), que a un hilo de otra máquina se le lleva por
  el bus (`telar archivo`, hasta 25 MB: llega a cualquier máquina de la persona) o, si no hay bus o es más
  grande, por ssh (`imagen.subir`, con el `destino` de `[remotos]`). Del nombre
  queda solo el último tramo, sin separadores ni caracteres de control; si ya hay uno igual, `-2`, `-3`…:
  nunca se pisa nada. Hasta 200 MB.

Lo usan `GET /archivos`, `GET /archivos/md`, `PUT /archivos` y `POST /archivos/entrada` de la API; detrás de la
llave de la página (y las escrituras, del mismo origen).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio

TOPE_LEER = 2 * 1024 * 1024
TOPE_ESCRIBIR = 4_000_000
TOPE_ENTRADA = 200 * 1024 * 1024
#: el nombre más largo que se deja en la entrada, en bytes (los sistemas de archivos aceptan 255)
LARGO_NOMBRE = 200
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


    maquina: str = ""  # dónde se leyó, si fue en otra máquina


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


def _bajo_repos(ctx, p: Path) -> bool:
    """Bajo la raíz o bajo la carpeta de uno de `[repos]`: lo que se puede leer (escribir, solo bajo la raíz)."""
    if _bajo_raiz(ctx, p):
        return True
    from telar.perfil import carpeta_de_repo

    for r in getattr(ctx.config, "repos", ()) or ():
        try:
            p.relative_to(carpeta_de_repo(ctx.config, r))
            return True
        except ValueError:
            continue
    return False


def leer(ctx, ruta: str) -> Archivo:
    p = _resolver(ctx, ruta)
    if not (_bajo_repos(ctx, p) or p in _de_apps(ctx, "archivo") | _de_apps(ctx, "memoria")):
        raise ErrorDeServicio(f"{ruta}: fuera de la raíz y de las apps declaradas", 403)
    if not p.is_file():
        raise ErrorDeServicio(f"no hay {ruta}", 404)
    with open(p, "rb") as f:
        datos = f.read(TOPE_LEER + 1)
    return Archivo(ruta=str(p), texto=datos[:TOPE_LEER].decode("utf-8", "replace"), mtime=p.stat().st_mtime,
                   recortado=len(datos) > TOPE_LEER)


def leer_en(ctx, ruta: str, maquina: str = "") -> Archivo:
    """`leer`, en esta máquina o en `maquina` (por el bus, a su nodo). Una ruta `máquina:ruta` también vale."""
    from telar import bus as mod_bus

    if not maquina and (m := re.match(r"([A-Za-z0-9][\w-]*):(?!//)(.+)", ruta)):
        maquina, ruta = m.group(1), m.group(2)
    if not maquina or not mod_bus.hay_bus(ctx.config) or maquina == mod_bus.maquina(ctx.config):
        return leer(ctx, ruta)
    r = mod_bus.pedir(ctx.config, maquina, "archivo-leer", {"ruta": ruta}, espera=20)
    if not r.get("ok"):
        raise ErrorDeServicio(r.get("error") or f"{maquina} no pudo leer {ruta}", int(r.get("codigo") or 502))
    return Archivo(**{**r["archivo"], "maquina": maquina})


def leer_para_otra(ctx, pedido: dict) -> dict:
    """Lo que responde el nodo a `archivo-leer`: el archivo, o el error con su código."""
    try:
        return {"ok": True, "archivo": leer(ctx, str(pedido.get("ruta", ""))).model_dump()}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}


def para_bajar(ctx, ruta: str) -> Path:
    """Un archivo para bajarlo entero (lo que la página no muestra: un binario, uno grande): los mismos límites
    que `leer` (la raíz, lo que declaran las apps, los lienzos entregados), sin tope de tamaño."""
    p = _resolver(ctx, ruta)
    if not (_bajo_repos(ctx, p) or p in _de_apps(ctx, "archivo") | _de_apps(ctx, "memoria")):
        raise ErrorDeServicio(f"{ruta}: fuera de la raíz y de las apps declaradas", 403)
    if not p.is_file():
        raise ErrorDeServicio(f"no hay {ruta}", 404)
    return p


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


# ── dejar en la entrada: lo que se arrastra a un hilo, en ~/telar-entrada/ de su máquina ─────────────────────


class Entrada(BaseModel):
    """Dónde quedó lo que se dejó en la entrada: su ruta en la máquina del hilo ('' es esta)."""

    ruta: str
    maquina: str = ""
    bytes: int


def nombre_seguro(nombre: str) -> str:
    """El nombre de un archivo para dejarlo en la entrada: solo su último tramo (sin `/` ni `\\`), sin
    caracteres de control y no más largo que LARGO_NOMBRE bytes (se corta el nombre, no la extensión). Uno
    vacío, `.` o `..` no sirve."""
    n = (nombre or "").replace("\\", "/").rsplit("/", 1)[-1]
    n = "".join(c for c in n if c.isprintable()).strip()
    if n in ("", ".", ".."):
        raise ErrorDeServicio(f"«{nombre}» no sirve como nombre de archivo", 422)
    if len(n.encode("utf-8")) > LARGO_NOMBRE:
        p = Path(n)
        sufijo = p.suffix if len(p.suffix.encode("utf-8")) < 20 else ""
        tronco = (p.stem if sufijo else n).encode("utf-8")[: LARGO_NOMBRE - len(sufijo.encode("utf-8"))]
        n = tronco.decode("utf-8", "ignore") + sufijo
    return n


def _dejar(tmp: Path, carpeta: Path, nombre: str) -> Path:
    """Pone `tmp` en `carpeta` como `nombre`, o con su sufijo (-2, -3…) si ya hay uno: el mismo criterio que
    `imagen.subir` allá. Con un enlace duro, que falla si el nombre está tomado: elegir y escribir es una sola
    operación, y dos a la vez no se pisan."""
    from telar.ordenes.imagen import con_sufijo

    for n in range(1, 1000):
        destino = carpeta / (nombre if n == 1 else con_sufijo(nombre, n))
        try:
            os.link(tmp, destino)
        except FileExistsError:
            continue
        os.unlink(tmp)
        return destino
    raise ErrorDeServicio(f"no hay un nombre libre para {nombre} en {carpeta}", 409)


def _remoto(ctx, maquina: str):
    """La máquina del hilo: None si es esta; si es otra, `(su [remotos] o None, si hay bus)`: por el bus se le
    llega a cualquier máquina de la persona (`telar archivo`), por ssh solo a una de `[remotos]`."""
    from telar import bus as mod_bus

    if not maquina or maquina == mod_bus.maquina(ctx.config):
        return None
    r = next((r for r in getattr(ctx.config, "remotos", ()) or () if r.nombre == maquina), None)
    hay_bus = mod_bus.hay_bus(ctx.config)
    if r is None and not hay_bus:
        raise ErrorDeServicio(f"{maquina}: sin bus y sin [remotos] para ella, no sé cómo llevarle el archivo", 404)
    return (maquina, r, hay_bus, ctx.config)


def _espera(bytes_: int) -> float:
    """Cuánto puede tardar la copia por ssh: un minuto, y más si es grande (a 512 KB/s, una red lenta)."""
    return max(60.0, bytes_ / (512 * 1024))


def _a_otra(destino, origen: Path, nombre: str, bytes_: int) -> Entrada:
    """A la entrada de la otra máquina: por el bus si lo hay y cabe (`telar archivo`, hasta 25 MB), si no por ssh
    a su `[remotos]` (`imagen.subir`)."""
    from telar import entrega

    maquina, remoto, hay_bus, config = destino
    if hay_bus and bytes_ <= entrega.MAX_TOTAL:
        try:
            r = entrega.archivo(config, origen, a=maquina, nombre=nombre)
            return Entrada(ruta=str(r.get("ruta", "")), maquina=maquina, bytes=int(r.get("bytes", bytes_)))
        except entrega.ErrorDeEntrega as e:
            if remoto is None:
                raise ErrorDeServicio(f"no se copió a {maquina} por el bus: {e}", 502) from e
    if remoto is None:
        raise ErrorDeServicio(f"{nombre} pasa de {entrega.MAX_TOTAL // (1024 * 1024)} MB, lo más que lleva el bus, y "
                              f"{maquina} no está en [remotos] para copiarlo por ssh", 413)
    from telar.ordenes import imagen

    ruta, problema = imagen.subir(remoto, origen, nombre, espera=_espera(bytes_))
    if problema:
        raise ErrorDeServicio(f"no se copió a {maquina}: {problema}", 502)
    return Entrada(ruta=ruta, maquina=maquina, bytes=bytes_)


def desde_bytes(ctx, maquina: str, nombre: str, datos: BinaryIO) -> Entrada:
    """Lo que sube la página (un archivo soltado sin su ruta), en la entrada de la máquina del hilo. En esta, se
    escribe de una vez (un temporal, que después toma su nombre); en otra, se junta en un temporal y se copia
    por ssh."""
    from telar.entrega import carpeta_de_entrada

    nombre = nombre_seguro(nombre)
    remoto = _remoto(ctx, maquina)
    # aquí, la entrada de esta máquina (`[bus] entrada`, por defecto ~/telar-entrada); el temporal, a su lado,
    # para que el enlace del final no cruce de disco
    carpeta = carpeta_de_entrada(ctx.config) if remoto is None else Path(tempfile.gettempdir())
    carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".telar-entrada-", suffix=".tmp", dir=carpeta)
    try:
        total = 0
        with os.fdopen(fd, "wb") as f:
            while trozo := datos.read(1024 * 1024):
                total += len(trozo)
                if total > TOPE_ENTRADA:
                    raise ErrorDeServicio(f"{nombre} pasa de {TOPE_ENTRADA // (1024 * 1024)} MB", 413)
                f.write(trozo)
        if remoto is not None:
            return _a_otra(remoto, Path(tmp), nombre, total)
        return Entrada(ruta=str(_dejar(Path(tmp), carpeta, nombre)), bytes=total)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def desde_ruta(ctx, maquina: str, ruta: str) -> Entrada:
    """Un archivo de esta máquina, nombrado por su ruta (el arrastre la trajo), copiado a la entrada de la
    máquina del hilo. Para un hilo de esta máquina no hace falta: la página escribe la ruta tal cual."""
    if not ruta or "\x00" in ruta:
        raise ErrorDeServicio("¿qué archivo?", 422)
    p = Path(ruta).expanduser()
    if not p.is_absolute():
        raise ErrorDeServicio(f"{ruta}: hace falta la ruta entera", 422)
    p = p.resolve()
    if not p.is_file():
        raise ErrorDeServicio(f"{ruta}: no es un archivo de esta máquina", 404)
    if not os.access(p, os.R_OK):
        raise ErrorDeServicio(f"{ruta}: no se puede leer", 403)
    bytes_ = p.stat().st_size
    if bytes_ > TOPE_ENTRADA:
        raise ErrorDeServicio(f"{p.name} pasa de {TOPE_ENTRADA // (1024 * 1024)} MB", 413)
    remoto = _remoto(ctx, maquina)
    if remoto is None:
        # el hilo es de aquí: ya lo puede leer donde está (la página no lo pide, pero si alguien lo pide, se dice)
        return Entrada(ruta=str(p), bytes=bytes_)
    # con el nombre que se arrastró (si era un enlace simbólico, el suyo y no el de su destino)
    return _a_otra(remoto, p, nombre_seguro(Path(ruta).name), bytes_)
