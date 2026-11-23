"""La carpeta de un hilo y uno de sus archivos (su documento, si no se pide otro), para leerlos en la página:
lo que en VS Code son la ficha y la vista de carpeta. Solo lee.

Nada fuera de la carpeta del hilo (tampoco por un enlace simbólico que apunte afuera), nada oculto ni
`node_modules`, y hasta 1 MB por archivo. Un `.md` va como markdown (la página lo convierte); el resto,
como texto; un binario no se muestra.

Sin hilo, un archivo o una carpeta de lo que la página puede leer (telar.servicios.archivos, `base_de`): la raíz del
repositorio (`[telar] raiz`), lo que el dashboard abre (un README, la carpeta de un proyecto); uno de `[repos]`; o la
carpeta de un hilo de esta máquina, aunque esté fuera de la raíz (el worktree de un hijo con rama, un repo aparte),
lo que abre un clic en una ruta que escribió su agente. Se recorre sin salir de la carpeta que lo contiene. Las rutas
vuelven como se pueden volver a pedir: las de la raíz, relativas a ella; las de otra carpeta, enteras (con `~` si
están en la carpeta personal). Un archivo suelto que declara una app se muestra solo, sin carpeta. Lo que no se
muestra (un binario, uno grande) trae `descarga`, su ruta, para bajarlo (`GET /archivos/bajar`).

Con «máquina:» delante («servidor:docs/x.md»), el de otra máquina: su nodo lo arma con sus propios límites
(`archivo-leer` con `documento`, por el bus) y sus rutas vuelven con la máquina delante, para seguir recorriendo
allá. Un nodo de antes contesta solo el archivo, y se muestra solo.

Lo usa `GET /hilos/documento` de la API (las vistas `doc:<hilo>` y `arch:<ruta>` de la página).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from pydantic import BaseModel

TOPE = 1 << 20


class Entrada(BaseModel):
    nombre: str
    ruta: str


class Documento(BaseModel):
    hilo: str
    titulo: str
    error: str = ""
    carpeta: str = "."
    archivo: str = ""
    #: la carpeta de arriba, relativa a la del hilo; None si ya es la del hilo
    subir: str | None = None
    archivos: list[Entrada] = []
    markdown: str = ""
    texto: str = ""
    #: la ruta del archivo elegido cuando no se muestra (binario o grande): para bajarlo
    descarga: str = ""
    #: lo que hay que saber de lo que se muestra (que se cortó)
    aviso: str = ""
    #: la máquina donde está, si no es esta
    maquina: str = ""


#: «máquina:» delante de una ruta, como la entiende `archivos.leer_en`
MAQUINA = re.compile(r"([A-Za-z0-9][\w-]*):(?!//)(.+)", re.S)


def _dentro(p: Path, base: Path) -> bool:
    return p == base or base in p.parents


def documento(ctx, hilo: str = "", archivo: str = "") -> Documento:
    if not hilo:
        if m := MAQUINA.match(archivo):
            return _en_otra(ctx, m.group(1), m.group(2))
        return de_aqui(ctx, archivo)
    from telar.servicios import ErrorDeServicio
    from telar.servicios import fichas

    try:
        h = fichas.ficha(ctx, hilo).hilo
    except ErrorDeServicio as e:
        return Documento(hilo=hilo, titulo=hilo, error=str(e))
    ficha = h.get("ficha") or {}
    titulo = ficha.get("titulo") or hilo
    ruta = h.get("ruta") or ""
    if not h.get("vinculado") or not ruta or not os.path.isdir(ruta):
        return Documento(hilo=hilo, titulo=titulo, error=f"«{hilo}» no tiene una carpeta en esta máquina")
    base = Path(ruta).resolve()
    if archivo:
        elegido = (base / archivo).resolve()
    elif ficha.get("documento"):
        elegido = Path(ficha["documento"]).resolve()
    else:
        elegido = None
    return _leer(hilo, titulo, base, elegido)


def de_aqui(ctx, archivo: str) -> Documento:
    """Un archivo o una carpeta de esta máquina que la página puede leer (`archivo`: absoluto, con `~` o relativo a
    la raíz), con los de al lado, sin salir de la carpeta que lo contiene."""
    from telar.servicios import archivos

    raiz = Path(ctx.config.raiz).expanduser().resolve()
    p = Path(archivo).expanduser() if archivo else raiz
    # resolve() sigue los enlaces: uno que apunta afuera queda afuera
    elegido = (p if p.is_absolute() else raiz / p).resolve()
    base = archivos.base_de(ctx, elegido)
    if base is None:
        if archivos.legible(ctx, elegido) and elegido.is_file():
            # uno suelto que declara una app: solo él
            doc = Documento(hilo="", titulo=elegido.name, archivos=[])
            _contenido(doc, elegido, _nombrar(elegido))
            return doc
        return Documento(hilo="", titulo=archivo, error="ese archivo está fuera de la raíz del repositorio y de las "
                                                       "carpetas de los hilos")
    nombre = (lambda x: os.path.relpath(x, raiz)) if base == raiz else _nombrar
    titulo = os.path.relpath(elegido, base) if elegido != base else base.name
    return _leer("", titulo if base == raiz or elegido == base else f"{base.name}/{titulo}", base, elegido, nombre)


def _nombrar(p: Path) -> str:
    """Una ruta fuera de la raíz, como se vuelve a pedir: entera, con `~` si está en la carpeta personal."""
    casa = Path.home().resolve()
    return "~/" + os.path.relpath(p, casa) if casa in p.parents else str(p)


def _en_otra(ctx, maquina: str, ruta: str) -> Documento:
    """El documento de otra máquina: lo arma su nodo (`archivo-leer` con `documento`), y sus rutas vuelven con la
    máquina delante. Sin bus, o si es esta, aquí."""
    from telar import bus as mod_bus

    if not mod_bus.hay_bus(ctx.config) or maquina == mod_bus.maquina(ctx.config):
        return de_aqui(ctx, ruta)
    en = f"{maquina}:"
    titulo = f"{ruta.rstrip('/').rsplit('/', 1)[-1] or ruta} · en {maquina}"
    r = mod_bus.pedir(ctx.config, maquina, "archivo-leer", {"ruta": ruta, "documento": True}, espera=20)
    if not r.get("ok"):
        return Documento(hilo="", titulo=titulo, error=r.get("error") or f"{maquina} no pudo leer {ruta}", maquina=maquina)
    if isinstance(r.get("documento"), dict):
        d = Documento.model_validate(r["documento"])
        con = lambda x: en + x if x and not x.startswith(en) else x  # noqa: E731
        return d.model_copy(update={
            "titulo": f"{d.titulo} · en {maquina}", "maquina": maquina, "hilo": "",
            "archivo": con(d.archivo), "subir": con(d.subir) if d.subir is not None else None,
            "archivos": [Entrada(nombre=a.nombre, ruta=con(a.ruta)) for a in d.archivos],
            # bajar es de esta máquina (`GET /archivos/bajar`): uno de allá no se baja desde aquí
            "descarga": ""})
    # un nodo de antes: solo el archivo
    a = r.get("archivo") or {}
    ruta_alla = str(a.get("ruta") or ruta)
    texto = str(a.get("texto") or "")
    es_md = ruta_alla.lower().endswith((".md", ".markdown"))
    return Documento(hilo="", titulo=f"{ruta_alla.rsplit('/', 1)[-1]} · en {maquina}", archivos=[], carpeta="",
                     archivo=en + ruta_alla, markdown=texto if es_md else "", texto="" if es_md else texto,
                     aviso="el archivo es más largo: se muestra hasta donde alcanza" if a.get("recortado") else "",
                     maquina=maquina)


def _leer(hilo: str, titulo: str, base: Path, elegido: Path | None, nombre=None) -> Documento:
    """La carpeta y el archivo elegido, sin salir de `base`. `nombre`: cómo se dice cada ruta (por defecto,
    relativa a `base`)."""
    nombre = nombre or (lambda x: os.path.relpath(x, base))
    # resolve() ya siguió los enlaces: si apunta afuera, se nota aquí
    if elegido is not None and not _dentro(elegido, base):
        return Documento(hilo=hilo, titulo=titulo, error="ese archivo no es de la carpeta del hilo" if hilo
                         else "ese archivo está fuera de la raíz del repositorio")
    es_carpeta = elegido is not None and elegido.is_dir()
    carpeta = elegido if es_carpeta else elegido.parent if elegido is not None else base
    try:
        entradas = [e for e in os.scandir(carpeta) if not e.name.startswith(".") and e.name != "node_modules"]
    except OSError:
        entradas = []
    entradas.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
    archivos = [Entrada(nombre=e.name + ("/" if e.is_dir() else ""), ruta=nombre(Path(e.path))) for e in entradas]
    doc = Documento(hilo=hilo, titulo=titulo, carpeta=nombre(carpeta), archivos=archivos,
                    subir=(nombre(carpeta.parent) if carpeta != base else None))
    if elegido is None or es_carpeta:
        return doc
    _contenido(doc, elegido, nombre(elegido))
    return doc


def _contenido(doc: Documento, elegido: Path, como: str) -> None:
    """Pone en `doc` el archivo elegido (`como`: su ruta, como se dice): su texto o su markdown, o, si no se
    muestra, por qué y `descarga`."""
    doc.archivo = como
    try:
        tamano = elegido.stat().st_size
    except OSError:
        doc.texto = "no existe"
        return
    if tamano > TOPE:
        doc.texto = f"pesa {round(tamano / 1024)} KB: no se muestra aquí"
        doc.descarga = str(elegido)
        return
    crudo = elegido.read_bytes()
    if b"\0" in crudo:
        doc.texto = "es un archivo binario: no se muestra aquí"
        doc.descarga = str(elegido)
    elif elegido.suffix.lower() == ".md":
        doc.markdown = crudo.decode("utf-8", "replace")
    else:
        doc.texto = crudo.decode("utf-8", "replace")
