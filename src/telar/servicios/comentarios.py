"""Los comentarios de un archivo, para la página y para los agentes (telar.comentarios, docs/contratos.md «Los comentarios
de un archivo»): leerlos ubicados en el texto de hoy, y comentar, responder, resolver, reabrir, editar y borrar.

**Qué archivos.** Los que la página puede leer y recorrer (telar.servicios.archivos, `base_de`): bajo la raíz, un repo
de `[repos]` o la carpeta de un hilo de esta máquina; un archivo de texto, de hasta 2 MB. El comentario va al lado del
archivo (`.<nombre>.marginalia.json`): el documento no se toca.

**De otra máquina.** Con «máquina:» delante («servidor:docs/x.md»), lo hace el nodo de esa máquina, por el bus
(`comentarios`), con sus propios límites: el archivo de al lado queda allá, junto al documento. Un nodo con un telar de
antes no conoce el pedido, y se dice así.

**Que llegue adonde trabajan los agentes.** El archivo de al lado se commitea solo y se sube, como ⚙ temas
(telar.temas.subir_luego): **solo ese archivo**, nunca otro, aunque el árbol tenga cambios ajenos; desde la página
(y desde el nodo, por el bus), unos segundos después del último cambio, para que varios comentarios seguidos sean un
solo commit; desde `telar comentarios`, al tiro (el proceso termina enseguida). Si el archivo no está en un repositorio
git, o su rama no tiene una de arriba, queda donde está y nada falla: el commit es para que llegue, no una condición.

Lo usan `GET /comentarios` y `POST /comentarios` de la API, el pedido `comentarios` del nodo y `telar comentarios`.
"""

from __future__ import annotations

import re
import socket
import subprocess
from pathlib import Path

from pydantic import BaseModel

from telar import comentarios as mod
from telar.servicios import ErrorDeServicio

#: cuánto se espera después del último cambio para commitear (varios comentarios seguidos son un solo commit)
ESPERA = 15.0
#: el mensaje del commit
MENSAJE = "comentarios: {archivo} ({maquina})"
#: «máquina:» delante de una ruta, como la entiende telar.servicios.archivos
MAQUINA = re.compile(r"([A-Za-z0-9][\w-]*):(?!//)(.+)", re.S)
ACCIONES = ("comentar", "responder", "resolver", "reabrir", "editar", "borrar")


class Comentario(BaseModel):
    id: str
    autor: str = ""
    cuerpo: str = ""
    fecha: str = ""


class Hilo(BaseModel):
    """Un hilo, ubicado en el texto de hoy (telar.comentarios.ubicado)."""

    id: str
    estado: str = "abierto"
    cita: str = ""
    antes: str = ""
    despues: str = ""
    creado: str = ""
    #: si se encontró dónde está hoy; sin ancla, lo de abajo va en None
    anclado: bool = False
    #: cómo se encontró: exacto, contexto, normalizado, aproximado o vecindario
    metodo: str | None = None
    confianza: float | None = None
    linea: int | None = None
    linea_fin: int | None = None
    #: el tramo en el texto de hoy, en unidades UTF-16 (como lo cuenta la página)
    inicio: int | None = None
    fin: int | None = None
    #: lo que dice hoy ese lugar, si ya no es la cita
    actual: str | None = None
    comentarios: list[Comentario] = []


class Comentarios(BaseModel):
    """Los comentarios de un archivo."""

    #: el archivo como se pidió (con «máquina:» delante si es de otra)
    ruta: str
    #: el archivo entero en su máquina, y el de al lado que guarda los comentarios
    archivo: str = ""
    lateral: str = ""
    maquina: str = ""
    #: con qué nombre firma quien comenta desde la página (el `user.name` de git del repositorio del archivo)
    autor: str = ""
    hilos: list[Hilo] = []
    #: el hilo que se acaba de crear o cambiar, si fue eso
    hecho: str = ""


class Pedido(BaseModel):
    """Lo que se le hace a los comentarios de un archivo (`POST /comentarios`, `telar comentarios`, el pedido del nodo)."""

    ruta: str
    #: comentar, responder, resolver, reabrir, editar o borrar
    accion: str
    #: el hilo (todas menos comentar) y el comentario (editar; borrar uno, sin él se borra el hilo entero)
    hilo: str = ""
    comentario: str = ""
    #: lo que se escribe (comentar, responder, editar; resolver y reabrir lo agregan como respuesta si va)
    texto: str = ""
    #: comentar: el tramo del texto (en unidades UTF-16), lo que se vio ahí y su vecindario
    inicio: int = 0
    fin: int = 0
    cita: str | None = None
    antes: str = ""
    despues: str = ""
    #: quién firma; vacío, quien comenta desde la página (el `user.name` de git del repositorio del archivo)
    autor: str = ""


# ── qué archivo ────────────────────────────────────────────────────────────────────────────────────────────────────


def partir(ruta: str) -> tuple[str, str]:
    """(máquina, ruta) de «máquina:ruta»; ("", ruta) si no la dice."""
    if m := MAQUINA.fullmatch(ruta or ""):
        return m.group(1), m.group(2)
    return "", ruta or ""


def de_aqui(ctx, ruta: str, desde: Path | None = None) -> Path:
    """El archivo de esta máquina al que se le pueden poner comentarios: uno que la página recorre (la raíz, `[repos]`,
    la carpeta de un hilo), de texto y de hasta 2 MB. Con `desde` (lo que pide `telar comentarios`, un agente en su
    carpeta), una ruta relativa es desde ahí y vale cualquier archivo: los límites son de la página y del bus."""
    from telar.servicios import archivos

    if not ruta or "\x00" in ruta:
        raise ErrorDeServicio("¿qué archivo?", 422)
    if desde is not None:
        p = Path(ruta).expanduser()
        p = (p if p.is_absolute() else Path(desde) / p).resolve()
    else:
        p = archivos._resolver(ctx, ruta)
        if archivos.base_de(ctx, p) is None:
            raise ErrorDeServicio(f"{ruta}: fuera de la raíz, de los repos y de las carpetas de los hilos: ahí no se "
                                  "comenta", 403)
    if p.name.endswith(mod.SUFIJO) and (doc := mod.documento_de(p)) is not None:
        p = doc  # el de al lado de uno: el documento
    if not p.is_file():
        raise ErrorDeServicio(f"no hay {ruta}", 404)
    if p.stat().st_size > archivos.TOPE_LEER:
        raise ErrorDeServicio(f"{ruta} pesa más de 2 MB: no se comenta desde aquí", 413)
    return p


def carpeta_de_aqui(ctx, ruta: str, desde: Path | None = None) -> Path:
    """Una carpeta (o un archivo) de esta máquina donde buscar comentarios, con los mismos límites que `de_aqui`."""
    from telar.servicios import archivos

    if desde is not None:
        p = Path(ruta or ".").expanduser()
        p = (p if p.is_absolute() else Path(desde) / p).resolve()
    else:
        p = archivos._resolver(ctx, ruta) if ruta else Path(ctx.config.raiz).expanduser().resolve()
        if archivos.base_de(ctx, p) is None:
            raise ErrorDeServicio(f"{ruta}: fuera de la raíz, de los repos y de las carpetas de los hilos", 403)
    if not p.exists():
        raise ErrorDeServicio(f"no hay {ruta or p}", 404)
    return p


def autor(ruta: Path, config=None) -> str:
    """Quién firma lo que se comenta desde la página: el `user.name` de git del repositorio del archivo (lo que firma
    sus commits), o la persona del bus, o el usuario del sistema."""
    try:
        r = subprocess.run(["git", "-C", str(Path(ruta).parent), "config", "user.name"], capture_output=True, text=True,
                           timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    import getpass

    try:
        from telar import bus as mod_bus

        return mod_bus.persona(config) if config is not None else getpass.getuser()
    except Exception:  # noqa: BLE001 - una configuración sin [bus]: el usuario del sistema
        return getpass.getuser()


def _vista(ctx, ruta_pedida: str, p: Path, hecho: str = "") -> Comentarios:
    try:
        hilos = mod.ubicar(p)
    except mod.ErrorDeComentarios as e:
        raise ErrorDeServicio(str(e), e.codigo) from e
    return Comentarios(ruta=ruta_pedida, archivo=str(p), lateral=str(mod.lateral(p)), autor=autor(p, ctx.config),
                       hilos=[Hilo.model_validate(h) for h in hilos], hecho=hecho)


# ── leer y cambiar, aquí ───────────────────────────────────────────────────────────────────────────────────────────


def ver(ctx, ruta: str, desde: Path | None = None) -> Comentarios:
    """Los comentarios de un archivo de esta máquina, ubicados en su texto de hoy."""
    return _vista(ctx, ruta, de_aqui(ctx, ruta, desde))


class Listado(BaseModel):
    """Los archivos con comentarios bajo una carpeta (o un archivo), cada uno con sus hilos."""

    ruta: str
    maquina: str = ""
    archivos: list[Comentarios] = []
    #: los archivos de al lado que no se pudieron leer, con por qué
    errores: list[str] = []


def listar(ctx, ruta: str, *, todos: bool = False, desde: Path | None = None) -> Listado:
    """Los hilos abiertos (con `todos`, también los resueltos) de los archivos bajo `ruta`: una carpeta, un repositorio
    o un archivo. Solo los archivos que tienen alguno."""
    raiz = carpeta_de_aqui(ctx, ruta, desde)
    salida = Listado(ruta=ruta)
    for p in mod.buscar(raiz):
        try:
            hilos = mod.ubicar(p, todos=todos)
        except mod.ErrorDeComentarios as e:
            salida.errores.append(f"{p}: {e}")
            continue
        if hilos:
            salida.archivos.append(Comentarios(ruta=str(p), archivo=str(p), lateral=str(mod.lateral(p)),
                                               hilos=[Hilo.model_validate(h) for h in hilos]))
    return salida


def hacer(ctx, pedido: Pedido, *, subir: str = "luego", desde: Path | None = None) -> Comentarios:
    """Hace el pedido sobre un archivo de esta máquina y devuelve cómo quedaron sus comentarios. `subir`: «luego»
    (commitear y subir el de al lado unos segundos después del último cambio), «ya» o «no»."""
    if pedido.accion not in ACCIONES:
        raise ErrorDeServicio(f"no sé «{pedido.accion}»: {', '.join(ACCIONES)}", 422)
    if pedido.accion != "comentar" and not pedido.hilo:
        raise ErrorDeServicio(f"{pedido.accion}: ¿qué hilo? (h1, h2…)", 422)
    p = de_aqui(ctx, pedido.ruta, desde)
    firma = pedido.autor.strip() or autor(p, ctx.config)
    try:
        if pedido.accion == "comentar":
            h = mod.comentar(p, pedido.inicio, pedido.fin, pedido.texto, firma, cita=pedido.cita, antes=pedido.antes,
                             despues=pedido.despues)
            hecho = h["id"]
        elif pedido.accion == "responder":
            mod.responder(p, pedido.hilo, pedido.texto, firma)
            hecho = pedido.hilo
        elif pedido.accion == "resolver":
            mod.resolver(p, pedido.hilo, pedido.texto, firma)
            hecho = pedido.hilo
        elif pedido.accion == "reabrir":
            mod.reabrir(p, pedido.hilo, pedido.texto, firma)
            hecho = pedido.hilo
        elif pedido.accion == "editar":
            if not pedido.comentario:
                raise ErrorDeServicio("editar: ¿qué comentario? (c1, c2…)", 422)
            mod.editar(p, pedido.hilo, pedido.comentario, pedido.texto)
            hecho = pedido.hilo
        else:
            mod.borrar(p, pedido.hilo, pedido.comentario)
            hecho = pedido.hilo
    except mod.ErrorDeComentarios as e:
        raise ErrorDeServicio(str(e), e.codigo) from e
    _que_llegue(ctx, p, subir)
    return _vista(ctx, pedido.ruta, p, hecho)


def _que_llegue(ctx, p: Path, subir: str) -> None:
    """Commitear y subir el archivo de al lado de `p`, solo ese (telar.temas.subir y subir_luego)."""
    if subir == "no":
        return
    from telar import temas

    from telar import bus as mod_bus

    lado = mod.lateral(p)
    try:
        maquina = mod_bus.maquina(ctx.config)
    except Exception:  # noqa: BLE001 - una configuración a medias: el nombre de red
        maquina = socket.gethostname().split(".")[0]
    mensaje = MENSAJE.format(archivo=p.name, maquina=maquina)
    try:
        if subir == "ya":
            temas.subir(lado, estado=getattr(ctx.config, "estado", None), mensaje=mensaje)
        else:
            temas.subir_luego(ctx.config, espera=ESPERA, archivo=lado, mensaje=mensaje)
    except Exception:  # noqa: BLE001 - el commit es para que llegue: si falla, el comentario igual quedó escrito
        pass


# ── en la máquina que sea ──────────────────────────────────────────────────────────────────────────────────────────


def _de_otra(ctx, maquina: str) -> bool:
    from telar import bus as mod_bus

    return bool(maquina) and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config)


def _por_el_bus(ctx, maquina: str, datos: dict) -> Comentarios:
    from telar import bus as mod_bus

    r = mod_bus.pedir(ctx.config, maquina, "comentarios", datos, espera=20)
    if not r.get("ok"):
        error = r.get("error") or f"{maquina} no pudo con los comentarios"
        if r.get("sin_servicio") or r.get("viejo"):
            error = f"{maquina} tiene un telar de antes, que no sabe de comentarios: actualízalo allá para comentar ahí ({error})"
        raise ErrorDeServicio(error, int(r.get("codigo") or 502))
    c = Comentarios.model_validate(r["comentarios"])
    return c.model_copy(update={"ruta": f"{maquina}:{c.ruta}", "maquina": maquina})


def ver_en(ctx, ruta: str, desde: Path | None = None) -> Comentarios:
    """`ver`, aquí o en la máquina que diga «máquina:» delante."""
    maquina, sin = partir(ruta)
    if not _de_otra(ctx, maquina):
        return ver(ctx, sin if maquina else ruta, desde)
    return _por_el_bus(ctx, maquina, {"ruta": sin})


def hacer_en(ctx, pedido: Pedido, *, subir: str = "luego", desde: Path | None = None) -> Comentarios:
    """`hacer`, aquí o en la máquina que diga «máquina:» delante (allá se commitea al rato, siempre)."""
    maquina, sin = partir(pedido.ruta)
    if not _de_otra(ctx, maquina):
        return hacer(ctx, pedido.model_copy(update={"ruta": sin}) if maquina else pedido, subir=subir, desde=desde)
    return _por_el_bus(ctx, maquina, {"pedido": pedido.model_copy(update={"ruta": sin}).model_dump()})


def listar_en(ctx, ruta: str, *, todos: bool = False, desde: Path | None = None) -> Listado:
    """`listar`, aquí o en la máquina que diga «máquina:» delante (allá, desde su raíz y con sus límites)."""
    from telar import bus as mod_bus

    maquina, sin = partir(ruta)
    if not _de_otra(ctx, maquina):
        return listar(ctx, sin if maquina else ruta, todos=todos, desde=desde)
    r = mod_bus.pedir(ctx.config, maquina, "comentarios", {"listar": sin, "todos": todos}, espera=30)
    if not r.get("ok"):
        error = r.get("error") or f"{maquina} no pudo listar los comentarios"
        if r.get("sin_servicio") or r.get("viejo"):
            error = f"{maquina} tiene un telar de antes, que no sabe de comentarios ({error})"
        raise ErrorDeServicio(error, int(r.get("codigo") or 502))
    lst = Listado.model_validate(r["listado"])
    return lst.model_copy(update={"maquina": maquina, "ruta": ruta, "archivos": [
        c.model_copy(update={"ruta": f"{maquina}:{c.ruta}", "maquina": maquina}) for c in lst.archivos]})


def para_otra(ctx, datos: dict) -> dict:
    """Lo que responde el nodo al pedido `comentarios` de otra máquina: los comentarios (`ruta`, para leerlos; `pedido`,
    para cambiarlos), o el error con su código."""
    try:
        if "listar" in datos:
            return {"ok": True, "listado": listar(ctx, str(datos.get("listar") or ""), todos=bool(datos.get("todos"))).model_dump()}
        if isinstance(datos.get("pedido"), dict):
            c = hacer(ctx, Pedido.model_validate(datos["pedido"]), subir="luego")
        else:
            c = ver(ctx, str(datos.get("ruta", "")))
        return {"ok": True, "comentarios": c.model_dump()}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}
    except ValueError as e:  # un pedido que no tiene la forma
        return {"ok": False, "error": f"el pedido no sirve: {e}", "codigo": 422}
