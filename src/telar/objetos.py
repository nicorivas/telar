"""Direcciones y objetos (docs/propuestas/primitivas.md, «Las piezas»).

Un **objeto** es cualquier cosa con dirección, tipo y estado: una tarea, un hilo, un proyecto, un archivo, o lo
que traiga un módulo (un correo, un evento). Su **dirección** tiene una sola forma:

    tipo:id[@máquina]       tarea:T366 · hilo:Telar · proyecto:nico/proyectos/telar · archivo:telar:docs/x.md

`@máquina` va solo cuando importa (un hilo o un objeto de un módulo que vive en otra máquina); el `id` es
lo que el tipo entiende, y puede llevar `:` (un archivo es `máquina:ruta`). Con una forma, un mensaje puede
decir «revisa `tarea:T366`» y cualquiera sabe abrirlo: `telar objeto tarea:T366`, `GET /objetos/tarea:T366`.

Cada tipo sabe **ver** un objeto (lo que es, en campos) y le ofrece **acciones** con sus parámetros. Los de
fábrica son tarea (telar.tipos.tarea, sobre sus archivos), hilo, proyecto (las unidades del perfil) y archivo.
Un módulo agrega los suyos en su `modulo.toml`:

    [objetos.correo]
    ver = "correo-ver"            # una orden suya con consulta = true: recibe {"id": …}, da el objeto
    acciones = ["archivar"]       # otras consultas: reciben {"id": …, más los parámetros}

y su `ver` devuelve un objeto JSON con los campos de `Objeto` que tenga (titulo, estado, resumen, campos,
enlaces, acciones); telar pone la dirección, el tipo y el id.
"""

from __future__ import annotations

import inspect
import re
from typing import NamedTuple

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio

#: un tipo y su id, y quizás la máquina: lo que se reconoce en un texto como dirección
_DIRECCION = re.compile(r"(?<![\w/@.-])(?P<tipo>[a-z][a-z0-9-]*):(?P<id>[^\s`'\"<>()\[\]{},;]+?)(?:@(?P<maquina>[a-z0-9][\w-]*))?"
                        r"(?=$|[\s`'\"<>()\[\]{},;]|[.:!?](?:\s|$))")


class Direccion(NamedTuple):
    tipo: str
    id: str
    maquina: str = ""

    def __str__(self) -> str:
        return f"{self.tipo}:{self.id}" + (f"@{self.maquina}" if self.maquina else "")


class Accion(BaseModel):
    nombre: str
    descripcion: str = ""
    #: los parámetros que pide, por nombre (los opcionales con su valor por defecto)
    params: dict[str, str] = Field(default_factory=dict)


class Objeto(BaseModel):
    direccion: str
    tipo: str
    id: str
    titulo: str = ""
    estado: str = ""
    resumen: str = ""
    campos: dict = Field(default_factory=dict)
    #: las direcciones de otros objetos con que se relaciona (su proyecto, su hilo, su origen)
    enlaces: list[str] = Field(default_factory=list)
    acciones: list[Accion] = Field(default_factory=list)
    #: la versión que se leyó: una acción con ella no se hace si el objeto cambió
    version: str = ""
    maquina: str = ""


class Hecho(BaseModel):
    direccion: str
    accion: str
    objeto: Objeto | None = None
    resultado: dict = Field(default_factory=dict)


def leer(texto: str) -> Direccion:
    """La dirección de un texto entero (`tarea:T366`, `hilo:Telar@telar`). ErrorDeServicio 422 si no lo es."""
    t = texto.strip()
    m = re.fullmatch(r"(?P<tipo>[a-z][a-z0-9-]*):(?P<id>.+?)(?:@(?P<maquina>[a-z0-9][\w-]*))?", t)
    if not m or not m.group("id"):
        raise ErrorDeServicio(f"«{texto}» no es una dirección: se escribe tipo:id, como tarea:T366", 422)
    return Direccion(m.group("tipo"), m.group("id"), m.group("maquina") or "")


def buscar(ctx, texto: str) -> list[Direccion]:
    """Las direcciones de tipos conocidos que aparecen en un texto, en orden y sin repetir."""
    conocidos = set(tipos(ctx))
    vistas, salida = set(), []
    for m in _DIRECCION.finditer(texto):
        d = Direccion(m.group("tipo"), m.group("id"), m.group("maquina") or "")
        if d.tipo in conocidos and str(d) not in vistas:
            vistas.add(str(d))
            salida.append(d)
    return salida


# ── los tipos ───────────────────────────────────────────────────────────────────────

class Tipo:
    nombre = ""
    descripcion = ""

    def ver(self, ctx, d: Direccion) -> Objeto:
        raise NotImplementedError

    def hacer(self, ctx, d: Direccion, accion: str, params: dict, version: str = "") -> Hecho:
        raise ErrorDeServicio(f"«{d.tipo}» no tiene acciones", 404)


def _params_de(fn) -> dict[str, str]:
    """Los parámetros de una acción del tipo tarea, sin el objeto ni el reloj: nombre → "" o su defecto."""
    salida = {}
    for i, (nombre, p) in enumerate(inspect.signature(fn).parameters.items()):
        if i == 0 or nombre == "reloj" or p.kind in (p.VAR_KEYWORD, p.VAR_POSITIONAL):
            continue
        # el valor por defecto tal cual (sin las comillas de repr): la página lo pone en el campo
        salida[nombre] = "" if p.default in (p.empty, None) else str(p.default)
    return salida


class Tarea(Tipo):
    nombre = "tarea"
    descripcion = "una tarea (telar tipo tarea): sus campos, su historia y sus acciones"

    def _objeto(self, t) -> Objeto:
        from telar.tipos import tarea as tipo

        campos = {k: v for k, v in t.model_dump(mode="json").items()
                  if k not in ("id", "titulo", "estado", "historia", "version", "duplicadas", "contexto")
                  and v not in ("", [], None, False)}
        enlaces = [f"proyecto:{t.proyecto}"] if t.proyecto else []
        acciones = [Accion(nombre=n, descripcion=(fn.__doc__ or "").strip().split("\n")[0], params=_params_de(fn))
                    for n, fn in tipo.ACCIONES.items()]
        return Objeto(direccion=f"tarea:{t.id}", tipo="tarea", id=t.id, titulo=t.titulo, estado=t.estado,
                      resumen=" ".join(t.contexto.split())[:400], campos=campos, enlaces=enlaces,
                      acciones=acciones, version=getattr(t, "version", ""))

    def ver(self, ctx, d):
        from telar.servicios import tipos as servicio

        return self._objeto(servicio.obtener(ctx, d.id, "tarea"))

    def hacer(self, ctx, d, accion, params, version=""):
        from telar.servicios import tipos as servicio

        t = servicio.aplicar(ctx, d.id, accion, params, version=version or None, clave="tarea")
        return Hecho(direccion=str(d), accion=accion, objeto=self._objeto(t))


class Hilo(Tipo):
    nombre = "hilo"
    descripcion = "un hilo de telar: dónde trabaja, en qué anda; escribirle o leer lo último"

    def ver(self, ctx, d):
        from telar import bus as mod_bus
        from telar.ordenes import _comun

        if d.maquina and mod_bus.hay_bus(ctx.config) and d.maquina != mod_bus.maquina(ctx.config):
            # el de esa máquina, según su foto; si allá no hay uno con ese nombre, no es el de aquí
            remoto = _hilo_remoto(ctx, d.id, d.maquina)
            if remoto is None:
                raise ErrorDeServicio(f"{d.maquina} no tiene un hilo «{d.id}»", 404)
            return self._objeto(*remoto)
        tel = _comun.tejer(ctx)
        h = next((x for x in tel.hilos if x.nombre == d.id or x.id == d.id), None)
        # una ventana de aquí de un hilo que vive en otra máquina: lo que vale es lo que publica esa máquina
        if h is None or h.remoto:
            remoto = _hilo_remoto(ctx, h.nombre if h is not None else d.id)
            if remoto is None and h is not None:
                remoto = _comun.json_hilo(h, tel), h.remoto if h.remoto != "?" else ""
            if remoto is None:
                raise ErrorDeServicio(f"no hay ningún hilo «{d.id}», ni aquí ni en otra máquina del bus", 404)
            j, maquina = remoto
        else:
            j, maquina = _comun.json_hilo(h, tel), (h.remoto if h.remoto and h.remoto != "?" else "")
        return self._objeto(j, maquina)

    def _objeto(self, j: dict, maquina: str) -> Objeto:
        campos = {k: j[k] for k in ("relativa", "arquetipo", "vivo", "actividad", "atencion_desde") if j.get(k) not in (None, "", False)}
        enlaces = [f"proyecto:{j['relativa']}"] if j.get("relativa") and j.get("relativa") not in (".", "") else []
        return Objeto(direccion=f"hilo:{j['nombre']}" + (f"@{maquina}" if maquina else ""), tipo="hilo", id=j["nombre"], titulo=j["nombre"],
                      estado=str(j.get("atencion", "")), campos=campos, enlaces=enlaces, maquina=maquina,
                      acciones=[Accion(nombre="mensaje", descripcion="escribirle (llega a su casilla, viva donde viva)",
                                       params={"texto": ""}),
                                Accion(nombre="leer", descripcion="lo último que pasó en su conversación",
                                       params={"ultimos": "5"})])

    def hacer(self, ctx, d, accion, params, version=""):
        if accion == "mensaje":
            from telar.servicios import mensajes

            texto = str(params.get("texto", "")).strip()
            if not texto:
                raise ErrorDeServicio("mensaje: ¿qué le dices? params {\"texto\": …}", 422)
            r = mensajes.enviar(ctx, d.id, texto)
            return Hecho(direccion=str(d), accion=accion, resultado=r.model_dump(mode="json"))
        if accion == "leer":
            from telar.servicios import historias

            r = historias.leer(ctx, d.id, ultimos=int(params.get("ultimos") or 5), maquina=d.maquina)
            return Hecho(direccion=str(d), accion=accion, resultado=r.model_dump(mode="json"))
        raise ErrorDeServicio(f"un hilo no tiene la acción «{accion}»: mensaje o leer", 404)


def _hilo_remoto(ctx, nombre: str, maquina: str = ""):
    """(su JSON, su máquina) de un hilo que vive en otra máquina (en `maquina`, si se dice), según la foto de su
    espejo; None si no."""
    from telar import bus as mod_bus
    from telar import espejo

    if not mod_bus.hay_bus(ctx.config):
        return None
    for foto in espejo.leer_todos(ctx.config):
        if maquina and foto.get("nombre") != maquina:
            continue
        for h in foto.get("hilos", []):
            if h.get("nombre") == nombre and not h.get("remoto"):
                return h, foto["nombre"]
    return None


class Proyecto(Tipo):
    nombre = "proyecto"
    descripcion = "una unidad del perfil (un proyecto, un área, un cliente): su ficha y su hilo"

    def ver(self, ctx, d):
        from telar.servicios import proyectos

        lista = [x.model_dump() for x in proyectos.lista(ctx).proyectos]
        ruta = d.id.strip("/")
        p = next((x for x in lista if (x.get("ruta") or "").strip("/") == ruta), None) \
            or next((x for x in lista if x.get("nombre") == d.id), None)
        if p is None:
            raise ErrorDeServicio(f"el perfil no tiene una unidad «{d.id}» (telar proyectos)", 404)
        ruta = (p.get("ruta") or ruta).strip("/")
        campos = {k: v for k, v in p.items() if k not in ("nombre", "ruta", "hilo", "estado", "estado_completo")
                  and v not in ("", None, [], {})}
        enlaces = [f"hilo:{p['hilo']}"] if p.get("hilo") else []
        return Objeto(direccion=f"proyecto:{ruta}", tipo="proyecto", id=ruta, titulo=p.get("nombre") or ruta,
                      estado=str(p.get("estado") or ""), resumen=str(p.get("estado_completo") or ""), campos=campos,
                      enlaces=enlaces)


class Archivo(Tipo):
    nombre = "archivo"
    descripcion = "un archivo de una máquina (máquina:ruta, o solo la ruta): su título y su texto"

    def ver(self, ctx, d):
        from telar.servicios import archivos

        a = archivos.leer_en(ctx, d.id, d.maquina)
        titulo = next((l[2:].strip() for l in a.texto.splitlines() if l.startswith("# ")), a.ruta.rsplit("/", 1)[-1])
        lede = next((l.lstrip("> ").strip() for l in a.texto.splitlines() if l.startswith(">")), "")
        return Objeto(direccion=f"archivo:{d.id}" + (f"@{d.maquina}" if d.maquina else ""), tipo="archivo", id=d.id,
                      titulo=titulo, resumen=lede[:400], campos={"ruta": a.ruta, "mtime": a.mtime, "recortado": a.recortado},
                      maquina=a.maquina)


class DeModulo(Tipo):
    """Un tipo que trae un módulo: `ver` y sus acciones son consultas suyas (telar.servicios.modulos)."""

    def __init__(self, modulo: str, nombre: str, ver: str, acciones: tuple, descripcion: str):
        self.modulo, self.nombre, self._ver, self._acciones, self.descripcion = modulo, nombre, ver, acciones, descripcion

    def _consultar(self, ctx, verbo, params, maquina):
        from telar.servicios import modulos

        return modulos.consultar(ctx, self.modulo, verbo, params, maquina)

    def ver(self, ctx, d):
        r = self._consultar(ctx, self._ver, {"id": d.id}, d.maquina)
        datos = {k: v for k, v in r.items() if k in Objeto.model_fields and k not in ("direccion", "tipo", "id")}
        datos.setdefault("acciones", [{"nombre": a} for a in self._acciones])
        return Objeto(direccion=str(d), tipo=self.nombre, id=d.id, maquina=d.maquina, **datos)

    def hacer(self, ctx, d, accion, params, version=""):
        if accion not in self._acciones:
            raise ErrorDeServicio(f"«{self.nombre}» no tiene la acción «{accion}»: {', '.join(self._acciones) or 'ninguna'}", 404)
        r = self._consultar(ctx, accion, {"id": d.id, **params, **({"version": version} if version else {})}, d.maquina)
        return Hecho(direccion=str(d), accion=accion, resultado=r)


DE_FABRICA = (Tarea(), Hilo(), Proyecto(), Archivo())


def tipos(ctx) -> dict[str, Tipo]:
    """Los tipos que hay: los de fábrica y los de los módulos instalados (un módulo no pisa uno de fábrica)."""
    salida = {t.nombre: t for t in DE_FABRICA}
    for m in getattr(ctx.config, "modulos", ()):
        for nombre, o in getattr(m, "objetos", {}).items():
            if nombre not in salida:
                salida[nombre] = DeModulo(m.nombre, nombre, o["ver"], tuple(o.get("acciones", ())), o.get("descripcion", ""))
    return salida


def _tipo(ctx, d: Direccion) -> Tipo:
    t = tipos(ctx).get(d.tipo)
    if t is None:
        raise ErrorDeServicio(f"no hay un tipo «{d.tipo}»: {', '.join(sorted(tipos(ctx)))}", 404)
    return t


def ver(ctx, direccion: str) -> Objeto:
    d = leer(direccion)
    return _tipo(ctx, d).ver(ctx, d)


def hacer(ctx, direccion: str, accion: str, params: dict | None = None, version: str = "") -> Hecho:
    d = leer(direccion)
    return _tipo(ctx, d).hacer(ctx, d, accion, params or {}, version)
