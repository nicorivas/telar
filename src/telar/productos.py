"""Los productos y sus ideas (docs/propuestas/productos.md): lo que se vende, su backlog y su tablero.

    from telar import productos
    p = productos.listar(ctx)                         # {"declaraciones", "productos", "fallas"}
    productos.crear(ctx, "servicios/ia/sprint", "Versión de 3 semanas", {"valor": "alto"})
    productos.cambiar(ctx, "idea:servicios/ia/sprint/I01", {"estado": "priorizada"}, version="…")

Nada de esto sabe de un equipo: cada repositorio declara en `.telar/productos.yaml` qué unidades de su perfil son
productos (un arquetipo), qué se muestra de cada una y cómo son sus ideas. Una idea es un archivo markdown con
frontmatter en la carpeta de su producto (`<producto>/backlog/I01.md`, el formato telar.tipos.registro), escrito
con versión y candado (telar.tipos.carpeta). Lo usan `telar productos`, `GET /productos` y el lienzo de un módulo.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

ARCHIVO = Path(".telar") / "productos.yaml"
ESTADOS = ["idea", "evaluando", "priorizada", "en-curso", "lanzada", "descartada"]
NIVELES = ["alto", "medio", "bajo"]
LEEME = """# Backlog

Las ideas y mejoras de este producto, una por archivo (`I01.md`, `I02.md`…). Cada una dice en su frontmatter su
estado, su valor y su esfuerzo, y abajo su historia. Las muestra y las mueve la pestaña de productos de telar
(`telar productos`); también se pueden editar a mano.
"""


class ErrorDeProductos(Exception):
    def __init__(self, mensaje: str, codigo: int = 422) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


class Ideas(BaseModel):
    carpeta: str = "backlog"
    estados: list[str] = Field(default_factory=lambda: list(ESTADOS))
    backlog: list[str] = Field(default_factory=lambda: ["idea", "evaluando"])
    tablero: list[str] = Field(default_factory=lambda: ["priorizada", "en-curso", "lanzada"])
    campos: list[str] = Field(default_factory=lambda: ["valor", "esfuerzo", "origen", "responsable"])
    #: los valores posibles de un campo (los demás son texto libre)
    opciones: dict[str, list[str]] = Field(default_factory=lambda: {"valor": list(NIVELES), "esfuerzo": list(NIVELES)})
    #: el `area` de las tareas que nacen de una idea (la de las tareas de quien usa telar: "" es la de fábrica)
    area_tareas: str = ""


class Declaracion(BaseModel):
    """Un `.telar/productos.yaml`: el repositorio (su carpeta relativa a la raíz), qué es un producto y sus ideas."""

    repo: str = ""
    arquetipo: str
    nombre: str = "productos"
    campos: dict[str, str] = Field(default_factory=dict)
    ideas: Ideas = Field(default_factory=Ideas)


def _lugares(config) -> list[tuple[str, Path]]:
    from telar.perfil import carpeta_de_repo

    raiz = Path(config.raiz).expanduser().resolve()
    lugares = [("", raiz)]
    for repo in getattr(config, "repos", ()) or ():
        try:
            carpeta = carpeta_de_repo(config, repo)
            relativa = carpeta.relative_to(raiz).as_posix()
        except (ValueError, OSError):
            continue
        if relativa not in ("", "."):
            lugares.append((relativa, carpeta))
    return lugares


def declaraciones(config) -> tuple[list[Declaracion], list[str]]:
    """Los `.telar/productos.yaml` de la raíz y de los repositorios de `[repos]`. (las declaraciones, las fallas)."""
    salida, fallas = [], []
    for relativa, carpeta in _lugares(config):
        archivo = carpeta / ARCHIVO
        if not archivo.is_file():
            continue
        nombre = f"{relativa}/{ARCHIVO}" if relativa else str(ARCHIVO)
        try:
            datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
            if not isinstance(datos, dict) or not isinstance(datos.get("productos"), dict):
                raise ValueError("se esperaba «productos:» con su «arquetipo»")
            p = datos["productos"]
            if not p.get("arquetipo"):
                raise ValueError("falta productos.arquetipo")
            salida.append(Declaracion(repo=relativa, arquetipo=str(p["arquetipo"]), nombre=str(p.get("nombre") or "productos"),
                                      campos={str(k): str(v) for k, v in (p.get("campos") or {}).items()},
                                      ideas=Ideas(**(datos.get("ideas") or {}))))
        except (OSError, ValueError, TypeError, yaml.YAMLError) as e:
            fallas.append(f"{nombre}: {e}")
    return salida, fallas


def _frontmatter(documento: Path) -> dict[str, str]:
    try:
        texto = documento.read_text(encoding="utf-8")[:4000]
    except OSError:
        return {}
    from telar.tipos.registro import REGISTRO

    try:
        return REGISTRO.leer(texto).campos
    except ValueError:
        return {}


def _campo(selector: str, *, ficha, documento: Path, partes: list[str]) -> str:
    """Un campo de un producto por su selector: `{titulo}`, `{campo:X}` (su tabla), `{frontmatter:x}`, `{ruta:N}`
    (la parte N de su carpeta, contada desde el repositorio; -1 es la última). Un texto sin llaves va tal cual."""
    from telar import lectura

    def uno(m: re.Match[str]) -> str:
        clave = m.group(1).strip()
        if clave.startswith("frontmatter:"):
            return _frontmatter(documento).get(clave.split(":", 1)[1].strip(), "")
        if clave.startswith("ruta:"):
            try:
                return partes[int(clave.split(":", 1)[1])]
            except (ValueError, IndexError):
                return ""
        return lectura.etiqueta("{" + clave + "}", ficha)

    return re.sub(r"\{([^{}]+)\}", uno, selector).strip()


def _carpeta(config, producto: str, d: Declaracion):
    from telar.tipos.carpeta import Carpeta
    from telar.tipos.registro import REGISTRO

    return Carpeta(Path(config.raiz).expanduser() / producto / d.ideas.carpeta, REGISTRO)


def _idea(producto: str, d: Declaracion, r, version: str) -> dict:
    return {"id": r.id, "direccion": f"idea:{producto}/{r.id}", "producto": producto, "version": version,
            "titulo": r.campos.get("titulo", "") or r.id, "estado": r.campos.get("estado", "") or d.ideas.estados[0],
            "campos": r.campos, "cuerpo": r.cuerpo, "ultima": r.historia[-1] if r.historia else "",
            "archivo": f"{producto}/{d.ideas.carpeta}/{r.id}.md", "tareas": []}


def _productos(ctx) -> tuple[list[tuple[Declaracion, str, object, Path]], list[Declaracion], list[str]]:
    """(cada producto con su declaración, ruta, arquetipo y documento; las declaraciones; las fallas)."""
    from telar import lectura

    decl, fallas = declaraciones(ctx.config)
    unidades = lectura.indice(ctx.perfil, Path(ctx.config.raiz))
    salida = []
    for d in decl:
        prefijo = f"{d.repo}/" if d.repo else ""
        for ruta, (arquetipo, documento) in unidades.items():
            if arquetipo.nombre == d.arquetipo and ruta.startswith(prefijo):
                salida.append((d, ruta, arquetipo, documento))
    return salida, decl, fallas


def listar(ctx) -> dict:
    """Los productos de todas las declaraciones, cada uno con sus campos y sus ideas."""
    from telar import lectura
    from telar.ordenes import _comun
    from telar.tipos.carpeta import NoExiste

    encontrados, decl, fallas = _productos(ctx)
    fuente = _comun.fuente_ficha(ctx.config)
    productos = []
    for d, ruta, arquetipo, documento in encontrados:
        ficha = _comun.leer_ficha(documento, arquetipo, fuente)
        partes = ruta[len(d.repo) + 1:].split("/") if d.repo else ruta.split("/")
        ideas = []
        carpeta = _carpeta(ctx.config, ruta, d)
        for id in carpeta.ids():
            try:
                r, version = carpeta.leer(id)
                ideas.append(_idea(ruta, d, r, version))
            except (NoExiste, ValueError) as e:
                fallas.append(f"{ruta}/{d.ideas.carpeta}/{id}.md: {e}")
        productos.append({
            "ruta": ruta, "direccion": f"proyecto:{ruta}", "repo": d.repo,
            "titulo": lectura.etiqueta(arquetipo.etiqueta, ficha) or Path(ruta).name,
            "campos": {k: _campo(v, ficha=ficha, documento=documento, partes=partes) for k, v in d.campos.items()},
            "ideas": ideas,
        })
    productos.sort(key=lambda p: p["titulo"].casefold())
    _con_tareas(ctx, productos, fallas)
    return {"declaraciones": [x.model_dump() for x in decl], "productos": productos, "fallas": fallas}


def _con_tareas(ctx, productos: list[dict], fallas: list[str]) -> None:
    """Las tareas abiertas que nacieron de cada idea (las de `origen: idea:…`), en su idea. Sin tareas
    (`[tipos.tarea]` no declarado, o su máquina no contesta), las ideas van sin ellas."""
    ideas = {i["direccion"]: i for p in productos for i in p["ideas"]}
    if not ideas or not any(t.clave == "tarea" for t in getattr(ctx.config, "tipos", ())):
        return
    from telar.servicios import ErrorDeServicio
    from telar.servicios import tipos as st

    try:
        tareas = st.lista(ctx, "tarea").tareas
    except (ErrorDeServicio, OSError) as e:
        fallas.append(f"las tareas de las ideas: {e}")
        return
    for t in tareas:
        if t.origen in ideas:
            ideas[t.origen]["tareas"].append({"id": t.id, "titulo": t.titulo, "estado": t.estado, "direccion": f"tarea:{t.id}"})


def opciones(ctx) -> list[dict[str, str]]:
    """Los productos para elegir uno (llevar una tarea a su backlog): [{"valor": ruta, "nombre": título}]."""
    from telar import lectura
    from telar.ordenes import _comun

    encontrados, _, _ = _productos(ctx)
    fuente = _comun.fuente_ficha(ctx.config)
    salida = [{"valor": ruta, "nombre": lectura.etiqueta(a.etiqueta, _comun.leer_ficha(doc, a, fuente)) or Path(ruta).name}
              for _, ruta, a, doc in encontrados]
    return sorted(salida, key=lambda x: x["nombre"].casefold())


def _declaracion_de(ctx, producto: str) -> Declaracion:
    producto = producto.strip().strip("/")
    for d, ruta, _, _ in _productos(ctx)[0]:
        if ruta == producto:
            return d
    raise ErrorDeProductos(f"«{producto}» no es un producto (ningún .telar/productos.yaml lo declara)", 404)


def _validar(d: Declaracion, campos: dict[str, str]) -> None:
    if "estado" in campos and campos["estado"] not in d.ideas.estados:
        raise ErrorDeProductos(f"estado «{campos['estado']}»: puede ser {', '.join(d.ideas.estados)}")
    for k, v in campos.items():
        permitidos = d.ideas.opciones.get(k)
        if permitidos and v and v not in permitidos:
            raise ErrorDeProductos(f"{k} «{v}»: puede ser {', '.join(permitidos)}")
        if "\n" in str(v):
            raise ErrorDeProductos(f"{k}: un campo es una sola línea")


def partir(direccion: str) -> tuple[str, str]:
    """`idea:<producto>/<id>` → (producto, id)."""
    resto = direccion.removeprefix("idea:").strip().strip("/")
    if "/" not in resto:
        raise ErrorDeProductos(f"«{direccion}» no es la dirección de una idea (idea:<producto>/<id>)", 404)
    producto, id = resto.rsplit("/", 1)
    return producto, id


def ver(ctx, direccion: str) -> dict:
    from telar.tipos.carpeta import NoExiste

    producto, id = partir(direccion)
    d = _declaracion_de(ctx, producto)
    try:
        r, version = _carpeta(ctx.config, producto, d).leer(id)
    except NoExiste as e:
        raise ErrorDeProductos(str(e), 404) from e
    return _idea(producto, d, r, version)


def cambiar(ctx, direccion: str, campos: dict[str, str], *, version: str | None = None, nota: str = "") -> dict:
    """Cambia campos de una idea (su estado al moverla en el tablero), con su línea en la historia."""
    from telar.tipos import registro
    from telar.tipos.carpeta import ErrorDeVersion, NoExiste

    producto, id = partir(direccion)
    d = _declaracion_de(ctx, producto)
    campos = {str(k): str(v).strip() for k, v in campos.items()}
    if "titulo" in campos and not campos["titulo"]:
        raise ErrorDeProductos("una idea sin título no se distingue de las otras")
    _validar(d, campos)
    try:
        r, nueva = _carpeta(ctx.config, producto, d).aplicar(id, registro.cambiar, campos, nota, version=version or None)
    except NoExiste as e:
        raise ErrorDeProductos(str(e), 404) from e
    except ErrorDeVersion as e:
        raise ErrorDeProductos(str(e), 409) from e
    return _idea(producto, d, r, nueva)


def crear(ctx, producto: str, titulo: str, campos: dict[str, str] | None = None, cuerpo: str = "") -> dict:
    """Una idea nueva en el backlog de un producto: el primer estado, y la fecha de hoy."""
    from telar.tipos import registro

    producto = producto.strip().strip("/")
    d = _declaracion_de(ctx, producto)
    titulo = " ".join(titulo.split())
    if not titulo:
        raise ErrorDeProductos("una idea sin título no se distingue de las otras")
    otros = {str(k): str(v).strip() for k, v in (campos or {}).items() if k not in ("titulo", "creada")}
    otros.setdefault("estado", d.ideas.estados[0])
    _validar(d, otros)
    carpeta = _carpeta(ctx.config, producto, d)
    carpeta.ruta.mkdir(parents=True, exist_ok=True)
    leeme = carpeta.ruta / "README.md"
    if not leeme.exists():
        leeme.write_text(LEEME, encoding="utf-8")
    r, version = carpeta.crear(registro.nuevo({"titulo": titulo, **otros, "creada": date.today().isoformat()}, cuerpo),
                               prefijo="I")
    return _idea(producto, d, r, version)


def desde_tarea(ctx, tarea: str, producto: str, campos: dict[str, str] | None = None) -> dict:
    """Una tarea que en realidad es una idea de un producto: la idea nace con su título y su texto (y `origen:
    tarea:T84`), y la tarea se descarta diciendo adónde fue. Si la tarea no se puede cerrar (cambió, ya estaba
    cerrada), la idea no queda: o se hacen las dos cosas o ninguna."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import tipos as st

    try:
        t = st.obtener(ctx, tarea.removeprefix("tarea:"))
    except ErrorDeServicio as e:
        raise ErrorDeProductos(str(e), e.codigo) from e
    if t.estado in ("hecha", "caduca", "descartada"):
        raise ErrorDeProductos(f"{t.id} ya está cerrada ({t.estado}): no hay nada que llevar", 409)
    # lo que la tarea sabía va con la idea: su texto, quién la llevaba y su historia (la tarea queda, descartada)
    otros = {"origen": f"tarea:{t.id}", **({"responsable": t.dueno} if t.dueno else {}), **(campos or {})}
    historia = [f"- {c.fecha}{' ' + c.hora if c.hora else ''} [{c.tipo}] {c.texto}".rstrip() for c in t.historia]
    cuerpo = "\n\n".join(x for x in [t.contexto.strip(), f"Venía de la tarea {t.id}"
                                      + (f" (nació de {t.origen})" if t.origen else "") + ":\n" + "\n".join(historia)] if x)
    idea = crear(ctx, producto, t.titulo, otros, cuerpo)
    try:
        st.aplicar(ctx, t.id, "cerrar", {"como": "descartada", "nota": f"es una idea de producto: {idea['direccion']}"},
                   version=t.version)
    except ErrorDeServicio as e:
        _carpeta(ctx.config, idea["producto"], _declaracion_de(ctx, idea["producto"])).borrar(idea["id"])
        raise ErrorDeProductos(f"no se pudo cerrar {t.id} ({e}): la idea no quedó", e.codigo) from e
    return {**idea, "tarea": t.id}


def nueva_tarea(ctx, direccion: str, titulo: str = "", *, vence: str = "") -> dict:
    """Una tarea operativa que nace de una idea (`proyecto`: su producto; `origen`: la idea). La idea la anota en su
    historia y la muestra mientras siga abierta."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import tipos as st
    from telar.tipos import registro

    producto, id = partir(direccion)
    d = _declaracion_de(ctx, producto)
    i = ver(ctx, direccion)
    params = {"titulo": " ".join((titulo or i["titulo"]).split()), "proyecto": producto, "origen": i["direccion"],
              "desde": f"la idea {i['direccion']}", **({"area": d.ideas.area_tareas} if d.ideas.area_tareas else {}),
              **({"vence": vence} if vence else {})}
    try:
        t = st.crear(ctx, params)
    except ErrorDeServicio as e:
        raise ErrorDeProductos(str(e), e.codigo) from e
    _carpeta(ctx.config, producto, d).aplicar(id, registro.anotar, f"tarea {t.id}: {t.titulo}")
    return {**ver(ctx, direccion), "tarea": t.id, "tareas": [{"id": t.id, "titulo": t.titulo, "estado": t.estado,
                                                              "direccion": f"tarea:{t.id}"}]}
