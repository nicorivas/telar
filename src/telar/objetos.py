"""Direcciones y objetos (docs/propuestas/primitivas.md, «Las piezas»).

Un **objeto** es cualquier cosa con dirección, tipo y estado: una tarea, un hilo, un proyecto, un archivo, o lo
que traiga un módulo (un correo, un evento). Su **dirección** tiene una sola forma:

    tipo:id[@máquina]       tarea:T366 · hilo:Telar · proyecto:proyectos/faro · archivo:telar:docs/x.md
                            pendiente:c-1a2b3c · encargo:e-1a2b3c4d · permiso:Faro

`@máquina` va solo cuando importa (un hilo o un objeto de un módulo que vive en otra máquina); el `id` es
lo que el tipo entiende, y puede llevar `:` (un archivo es `máquina:ruta`). Lo que en un id rompería la
forma va escapado como en una URL (`%40` por `@`, `%20` por un espacio: `hilo:Faro%40casa`, `hilo:◌%20a%20solas`),
para que `@` no se lea como la máquina y un texto la encuentre entera. Con una forma, un mensaje puede
decir «revisa `tarea:T366`» y cualquiera sabe abrirlo: `telar objeto tarea:T366`, `GET /objetos/tarea:T366`.

Cada tipo sabe **ver** un objeto (lo que es, en campos) y le ofrece **acciones** con sus parámetros. Los de
fábrica son tarea (telar.tipos.tarea, sobre sus archivos), hilo, proyecto (las unidades del perfil), archivo,
pendiente (una casilla de un documento, telar.vinetas), agente (un residente, con lo que declara su agente.toml),
encargo (un pedido con estado y resultado, telar.encargo) y permiso (lo que un hilo espera de la persona, solo
lectura).
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
from urllib.parse import unquote

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio

#: un tipo y su id, y quizás la máquina: lo que se reconoce en un texto como dirección
_DIRECCION = re.compile(r"(?<![\w/@.-])(?P<tipo>[a-z][a-z0-9-]*):(?P<id>[^\s`'\"<>()\[\]{},;]+?)(?:@(?P<maquina>[a-z0-9][\w-]*))?"
                        r"(?=$|[\s`'\"<>()\[\]{},;]|[.:!?](?:\s|$))")


#: lo que un id no puede llevar tal cual: `@` (se leería como la máquina), `%` (el escape mismo), los
#: espacios y lo que corta una dirección dentro de un texto (`buscar`)
_ESCAPAR = re.compile(r"[%@\s`'\"<>()\[\]{},;]")


def _escapar(id: str) -> str:
    return _ESCAPAR.sub(lambda m: "".join(f"%{b:02X}" for b in m.group().encode()), id)


class Direccion(NamedTuple):
    #: el id va tal cual (`◌ a solas`); escapado, solo en el texto de la dirección
    tipo: str
    id: str
    maquina: str = ""

    def __str__(self) -> str:
        return f"{self.tipo}:{_escapar(self.id)}" + (f"@{self.maquina}" if self.maquina else "")


def direccion_de(tipo: str, id: str, maquina: str = "") -> str:
    """La dirección de un objeto, como la escriben sus tipos y la llevan las salidas JSON que lo nombran
    (`telar hilos`, `telar proyectos`, `telar pendientes`, `telar tipo tarea`): `hilo:Faro`, `tarea:T84`.
    Un proyecto va por su ruta sin barras en los bordes, que es como lo encuentra `ver`. Lo que el id no puede
    llevar tal cual va escapado (`hilo:Faro%40casa`); `leer` y `buscar` lo devuelven a como era."""
    if tipo == "proyecto":
        id = id.strip("/")
    return str(Direccion(tipo, id, maquina))


class Accion(BaseModel):
    nombre: str
    descripcion: str = ""
    #: los parámetros que pide, por nombre (los opcionales con su valor por defecto)
    params: dict[str, str] = Field(default_factory=dict)
    #: los valores posibles de un parámetro, para elegir en vez de escribir: [{"valor", "nombre"}]
    opciones: dict[str, list[dict[str, str]]] = Field(default_factory=dict)


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
    return Direccion(m.group("tipo"), unquote(m.group("id")), m.group("maquina") or "")


def buscar(ctx, texto: str) -> list[Direccion]:
    """Las direcciones de tipos conocidos que aparecen en un texto, en orden y sin repetir."""
    conocidos = set(tipos(ctx))
    vistas, salida = set(), []
    for m in _DIRECCION.finditer(texto):
        d = Direccion(m.group("tipo"), unquote(m.group("id")), m.group("maquina") or "")
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

    def _objeto(self, t, con_productos: list | None = None) -> Objeto:
        from telar.tipos import tarea as tipo

        campos = {k: v for k, v in t.model_dump(mode="json").items()
                  if k not in ("id", "direccion", "titulo", "estado", "historia", "version", "duplicadas", "contexto")
                  and v not in ("", [], None, False)}
        enlaces = [direccion_de("proyecto", t.proyecto)] if t.proyecto else []
        acciones = [Accion(nombre=n, descripcion=(fn.__doc__ or "").strip().split("\n")[0], params=_params_de(fn))
                    for n, fn in tipo.ACCIONES.items()]
        if con_productos and t.estado not in tipo.TERMINALES:
            # una tarea que en realidad es una idea de un producto (telar.productos)
            acciones.append(Accion(nombre="al_backlog", params={"producto": ""}, opciones={"producto": con_productos},
                                   descripcion="llevarla al backlog de un producto: nace una idea con su texto y la tarea se descarta"))
        return Objeto(direccion=direccion_de("tarea", t.id), tipo="tarea", id=t.id, titulo=t.titulo, estado=t.estado,
                      resumen=" ".join(t.contexto.split())[:400], campos=campos, enlaces=enlaces,
                      acciones=acciones, version=getattr(t, "version", ""))

    def ver(self, ctx, d):
        from telar.servicios import tipos as servicio

        return self._objeto(servicio.obtener(ctx, d.id, "tarea"), _hay_productos(ctx))

    def hacer(self, ctx, d, accion, params, version=""):
        from telar.servicios import tipos as servicio

        if accion == "al_backlog":
            from telar import productos

            try:
                i = productos.desde_tarea(ctx, d.id, str(params.get("producto") or ""))
            except productos.ErrorDeProductos as e:
                raise ErrorDeServicio(str(e), e.codigo) from e
            return Hecho(direccion=str(d), accion=accion, objeto=self._objeto(servicio.obtener(ctx, d.id, "tarea")),
                         resultado={"idea": i["direccion"], "texto": f"{d.id} es ahora {i['direccion']}"})
        t = servicio.aplicar(ctx, d.id, accion, params, version=version or None, clave="tarea")
        return Hecho(direccion=str(d), accion=accion, objeto=self._objeto(t, _hay_productos(ctx)))


def _hay_productos(ctx) -> list:
    """Los productos a los que se puede llevar una tarea ([{valor, nombre}]); [] si nadie declara productos."""
    try:
        from telar import productos

        return productos.opciones(ctx)
    except Exception:  # noqa: BLE001 - sin productos, la tarea va sin esa acción
        return []


class Idea(Tipo):
    nombre = "idea"
    descripcion = "una idea de un producto (telar productos): su estado, valor y esfuerzo, su texto y sus tareas"

    def _objeto(self, ctx, i: dict) -> Objeto:
        from telar import productos

        d = productos._declaracion_de(ctx, i["producto"])
        campos = {k: v for k, v in i["campos"].items() if k not in ("titulo", "estado") and v}
        enlaces = [direccion_de("proyecto", i["producto"])]
        if i["campos"].get("origen", "").startswith("tarea:"):
            enlaces.append(i["campos"]["origen"])
        otros = [e for e in d.ideas.estados if e != i["estado"]]
        acciones = [
            Accion(nombre="mover", descripcion=f"cambiarle el estado ({', '.join(otros)})", params={"estado": ""},
                   opciones={"estado": [{"valor": e, "nombre": e} for e in otros]}),
            Accion(nombre="tarea", descripcion="abrir una tarea operativa desde ella (su producto, y la idea de origen)",
                   params={"titulo": i["titulo"], "vence": ""}),
            Accion(nombre="anotar", descripcion="una línea en su historia", params={"texto": ""}),
        ]
        return Objeto(direccion=i["direccion"], tipo="idea", id=f"{i['producto']}/{i['id']}", titulo=i["titulo"],
                      estado=i["estado"], resumen=" ".join(i["cuerpo"].split())[:400], campos=campos, enlaces=enlaces,
                      acciones=acciones, version=i["version"])

    def ver(self, ctx, d):
        from telar import productos

        try:
            return self._objeto(ctx, productos.ver(ctx, str(d)))
        except productos.ErrorDeProductos as e:
            raise ErrorDeServicio(str(e), e.codigo) from e

    def hacer(self, ctx, d, accion, params, version=""):
        from telar import productos
        from telar.tipos import registro

        try:
            if accion == "mover":
                i = productos.cambiar(ctx, str(d), {"estado": str(params.get("estado") or "")}, version=version or None)
            elif accion == "tarea":
                i = productos.nueva_tarea(ctx, str(d), str(params.get("titulo") or ""), vence=str(params.get("vence") or ""))
            elif accion == "anotar":
                producto, id = productos.partir(str(d))
                decl = productos._declaracion_de(ctx, producto)
                productos._carpeta(ctx.config, producto, decl).aplicar(id, registro.anotar, str(params.get("texto") or ""),
                                                                       version=version or None)
                i = productos.ver(ctx, str(d))
            else:
                raise ErrorDeServicio(f"una idea no tiene la acción «{accion}»: mover, tarea, anotar", 404)
        except productos.ErrorDeProductos as e:
            raise ErrorDeServicio(str(e), e.codigo) from e
        return Hecho(direccion=str(d), accion=accion, objeto=self._objeto(ctx, i),
                     resultado={"tarea": i["tarea"]} if i.get("tarea") else {})


class Hilo(Tipo):
    nombre = "hilo"
    descripcion = "un hilo de telar: dónde trabaja, en qué anda; escribirle o leer lo último"

    def ver(self, ctx, d):
        return self._objeto(*self.buscar(ctx, d))

    def buscar(self, ctx, d: Direccion) -> tuple[dict, str]:
        """(su JSON, como `telar hilos --json`; la máquina donde vive, "" si es de aquí). 404 si no está."""
        from telar import bus as mod_bus
        from telar.ordenes import _comun

        # `hilo:Faro@servidor`: el de esa máquina, aunque aquí haya otro «Faro» (como `telar hilo leer --maquina`)
        if d.maquina and mod_bus.hay_bus(ctx.config) and d.maquina != mod_bus.maquina(ctx.config):
            remoto = _hilo_remoto(ctx, d.id, maquina=d.maquina)
            if remoto is None:
                raise ErrorDeServicio(f"no hay ningún hilo «{d.id}» en {d.maquina} (según lo último que publicó)", 404)
            return remoto
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
        return j, maquina

    def _objeto(self, j: dict, maquina: str) -> Objeto:
        campos = {k: j[k] for k in ("relativa", "arquetipo", "vivo", "actividad", "atencion_desde") if j.get(k) not in (None, "", False)}
        enlaces = [direccion_de("proyecto", j["relativa"])] if j.get("relativa") and j.get("relativa") not in (".", "") else []
        if j.get("atencion") == "espera":
            # lo que espera es un objeto aparte: se abre ahí (desde cuándo, qué pide)
            enlaces.append(direccion_de("permiso", j["nombre"], maquina))
        return Objeto(direccion=direccion_de("hilo", j["nombre"], maquina), tipo="hilo", id=j["nombre"], titulo=j["nombre"],
                      estado=str(j.get("atencion", "")), campos=campos, enlaces=enlaces, maquina=maquina,
                      acciones=[Accion(nombre="mensaje", descripcion="escribirle (llega a su casilla, viva donde viva); "
                                       "modo: aviso (no lo despierta), pedido o encargo (con plazo, si se quiere)",
                                       params={"texto": "", "modo": "'pedido'", "plazo": "''"}),
                                Accion(nombre="leer", descripcion="lo último que pasó en su conversación",
                                       params={"ultimos": "5"})])

    def hacer(self, ctx, d, accion, params, version=""):
        if accion == "mensaje":
            from telar.servicios import mensajes

            texto = str(params.get("texto", "")).strip()
            if not texto:
                raise ErrorDeServicio("mensaje: ¿qué le dices? params {\"texto\": …}", 422)
            # la dirección entera: con @máquina, se comprueba que esa máquina lo tenga (telar.ordenes.mensaje)
            r = mensajes.enviar(ctx, str(d) if d.maquina else d.id, texto, modo=str(params.get("modo") or "pedido"), plazo=str(params.get("plazo") or ""))
            return Hecho(direccion=str(d), accion=accion, resultado=r.model_dump(mode="json"))
        if accion == "leer":
            from telar.servicios import historias

            r = historias.leer(ctx, d.id, ultimos=int(params.get("ultimos") or 5), maquina=d.maquina)
            return Hecho(direccion=str(d), accion=accion, resultado=r.model_dump(mode="json"))
        raise ErrorDeServicio(f"un hilo no tiene la acción «{accion}»: mensaje o leer", 404)


def _hilo_remoto(ctx, nombre: str, maquina: str = ""):
    """(su JSON, su máquina) de un hilo que vive en otra máquina, según la foto de su espejo; None si no.

    Con `maquina`, solo en esa."""
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
        campos = {k: v for k, v in p.items() if k not in ("nombre", "ruta", "direccion", "hilo", "estado", "estado_completo")
                  and v not in ("", None, [], {})}
        enlaces = [direccion_de("hilo", p["hilo"])] if p.get("hilo") else []
        return Objeto(direccion=direccion_de("proyecto", ruta), tipo="proyecto", id=ruta, titulo=p.get("nombre") or ruta,
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
        return Objeto(direccion=direccion_de("archivo", d.id, d.maquina), tipo="archivo", id=d.id,
                      titulo=titulo, resumen=lede[:400], campos={"ruta": a.ruta, "mtime": a.mtime, "recortado": a.recortado},
                      maquina=a.maquina)


class Pendiente(Tipo):
    """Una casilla de un documento («- [ ] …», la sección `pendientes` del perfil). `pendiente:c-1a2b3c` es la
    que tiene ese id (telar.vinetas se lo pone la primera vez que la escribe) y no cambia con el documento;
    `pendiente:faro:2` la nombra por su lugar (`ref` de `telar pendientes`), que sirve para el minuto siguiente.
    Sus acciones son las de `telar pendiente --hecho/--responsable`, y no tocan nada fuera del documento."""

    nombre = "pendiente"
    descripcion = "una casilla de un documento («- [ ] …»): su texto, dónde está y quién la hace; marcarla hecha o cambiar quién"

    def _fila(self, ctx, d: Direccion):
        from telar.ordenes import _comun, pendiente, pendientes

        if d.maquina:
            from telar import bus as mod_bus

            if d.maquina != mod_bus.maquina(ctx.config):
                raise ErrorDeServicio(f"una casilla se abre en la máquina de su documento: aquí no es {d.maquina}", 404)
        tel = _comun.tejer(ctx)
        filas = pendientes.juntar(ctx, tel, repo=True, hechos=True)
        # por el id primero (dos documentos con el mismo id son un 409, no la primera que aparezca), y si no,
        # por su lugar
        fila = pendiente.por_direccion(filas, direccion_de("pendiente", d.id)) \
            or next((f for f in filas if f["ref"] == d.id), None)
        if fila is None:
            raise ErrorDeServicio(f"no hay ninguna casilla «{d.id}» en los documentos (`telar pendientes --repo --json` "
                                  "las lista con su ref y su dirección)", 404)
        return tel, fila

    @staticmethod
    def _version(fila: dict) -> str:
        import hashlib

        huella = "\0".join([fila["texto"], str(fila["hecho"]), str(fila["en_curso"]), fila.get("dueno", "")])
        return hashlib.sha1(huella.encode()).hexdigest()[:12]

    def _objeto(self, tel, fila: dict) -> Objeto:
        from telar import vinetas
        from telar.ordenes import _comun
        from telar.ordenes.pendiente import id_casilla, lugar_casilla

        ident = id_casilla(fila)
        unidad = tel.unidades.get(fila.get("ruta", ""))
        documento, linea = "", 0
        if unidad is not None:
            documento = _comun.ruta_relativa(unidad[1], tel.raiz)
            try:
                linea = vinetas.linea(unidad[1], fila["texto"], id=ident, **lugar_casilla(fila))
            except (vinetas.ErrorDeVineta, OSError):
                linea = 0  # el documento cambió, o un mismo id dos veces: no se adivina
        estado = "hecha" if fila["hecho"] else "en curso" if fila["en_curso"] else "abierta"
        campos = {k: v for k, v in (("texto", fila["texto"]), ("documento", documento), ("linea", linea),
                                     ("responsable", fila.get("dueno", "")), ("ref", fila["ref"]),
                                     ("vence", (fila.get("cuando") or "")[:10])) if v not in ("", 0)}
        enlaces = ([direccion_de("proyecto", fila["ruta"])] if fila.get("ruta") else []) \
            + ([direccion_de("hilo", fila["hilo"])] if fila.get("hilo") else [])
        acciones = [] if fila["hecho"] else [
            Accion(nombre="hecho", descripcion="marcarla hecha en su documento ([ ] → [x])"),
            Accion(nombre="responsable", descripcion="decir quién la hace (@owner); vacío o «none» lo quita",
                   params={"nombre": ""}),
        ]
        return Objeto(direccion=fila["direccion"] or direccion_de("pendiente", fila["ref"]), tipo="pendiente",
                      id=ident or fila["ref"], titulo=fila["texto"], estado=estado, campos=campos, enlaces=enlaces,
                      acciones=acciones, version=self._version(fila))

    def ver(self, ctx, d):
        tel, fila = self._fila(ctx, d)
        return self._objeto(tel, fila)

    def hacer(self, ctx, d, accion, params, version=""):
        from telar.ordenes import pendiente

        if accion not in ("hecho", "responsable"):
            raise ErrorDeServicio(f"una casilla no tiene la acción «{accion}»: hecho o responsable", 404)
        if accion == "responsable" and "nombre" not in params:
            raise ErrorDeServicio("responsable: ¿quién? params {\"nombre\": …} (vacío lo quita)", 422)
        tel, fila = self._fila(ctx, d)
        if version and version != self._version(fila):
            raise ErrorDeServicio(f"«{d}» cambió desde que se leyó: vuelve a mirarla", 409)
        if fila["hecho"]:
            raise ErrorDeServicio(f"«{d}» ya está hecha", 409)
        if accion == "hecho":
            datos, _ = pendiente.en_su_documento(ctx, fila["ref"], hecho=True, fila=fila)
        else:
            datos, _ = pendiente.en_su_documento(ctx, fila["ref"], responsable=str(params["nombre"] or ""), fila=fila)
        # después de escribirla tiene id: se la vuelve a leer por él (el lugar pudo cambiar de dueño)
        try:
            objeto = self.ver(ctx, leer(datos["direccion"]) if datos.get("direccion") else d)
        except ErrorDeServicio:
            objeto = None
        return Hecho(direccion=str(d), accion=accion, objeto=objeto, resultado=datos)


class Permiso(Tipo):
    """Lo que un hilo espera de la persona (su atención en «espera»): `permiso:<hilo>`, de solo lectura.

    Es la solicitud de permiso de primitivas.md («Permiso»), en su primer paso: dice qué hilo espera, desde
    cuándo y, si su agente lo dijo, qué pide (Estado.espera, que anota el gancho del agente). Todavía no se
    contesta desde aquí: se contesta en el hilo (`telar ir <hilo>`), y por eso no tiene acciones. Su id es el
    del hilo, porque un hilo espera una cosa a la vez; cuando haya una solicitud con su propio id y su
    decisión, `permiso:<hilo>` seguirá siendo «la que espera ahora» (docs/propuestas/permisos.md)."""

    nombre = "permiso"
    descripcion = "lo que un hilo espera de la persona (un permiso, una pregunta): desde cuándo y qué pide; solo lectura"

    def ver(self, ctx, d):
        from telar import estado as mod_estado

        j, maquina = Hilo().buscar(ctx, Direccion("hilo", d.id, d.maquina))
        nombre = j["nombre"]
        if j.get("atencion") != "espera":
            estado = {"trabajando": "está trabajando", "termino": "terminó su turno"}.get(str(j.get("atencion")), "no está esperando")
            raise ErrorDeServicio(f"«{nombre}» no espera nada de nadie: {estado} (telar objeto hilo:{_escapar(nombre)})", 404)
        desde, pide, clase = str(j.get("atencion_desde") or ""), "", ""
        if not maquina:
            # lo que pide lo anota el gancho de esta máquina; de un hilo de otra, se sabe que espera y desde cuándo
            e = mod_estado.abrir(ctx.config).espera(nombre) or {}
            pide, clase = e.get("pide", ""), e.get("clase", "")
        campos = {k: v for k, v in (("hilo", nombre), ("desde", desde), ("pide", pide), ("clase", clase),
                                     ("contestar", f"en el hilo: telar ir {nombre}")) if v}
        enlaces = [direccion_de("hilo", nombre, maquina)]
        if j.get("relativa") and j.get("relativa") not in (".", ""):
            enlaces.append(direccion_de("proyecto", j["relativa"]))
        titulo = pide or (f"«{nombre}» te espera" if clase != "pregunta" else f"«{nombre}» te pregunta algo")
        return Objeto(direccion=direccion_de("permiso", nombre, maquina), tipo="permiso", id=nombre, titulo=titulo,
                      estado="pendiente", resumen=pide, campos=campos, enlaces=enlaces, version=desde,
                      maquina=maquina)

    def hacer(self, ctx, d, accion, params, version=""):
        raise ErrorDeServicio(f"«{d}» todavía no se contesta desde aquí: en su hilo (telar ir {d.id})", 404)


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


class Agente(Tipo):
    """Un agente residente (telar.agentes): `agente:<carpeta>`, o su nombre. Lo que ve es lo que declara su
    agente.toml (o lo de siempre, sin él); su acción es encargarle algo, como `telar encargar`."""

    nombre = "agente"
    descripcion = "un agente residente: para qué es, su modelo, sus hilos; encargarle algo"

    def ver(self, ctx, d):
        from telar import agentes as mod_agentes

        a = next((x for x in mod_agentes.descubrir(ctx.config) if d.id in (x.clave, x.nombre)), None)
        if a is None:
            hay = ", ".join(x.clave for x in mod_agentes.descubrir(ctx.config)) or "ninguno"
            raise ErrorDeServicio(f"no hay un agente «{d.id}» (hay: {hay})", 404)
        j = mod_agentes.como_json(a)
        campos = {k: v for k, v in j.items() if k not in ("clave", "nombre", "direccion", "para")
                  and v not in ("", [], {}, None)}
        return Objeto(direccion=j["direccion"], tipo="agente", id=a.clave, titulo=a.nombre,
                      estado="residente" if a.residente else "no residente", resumen=a.para, campos=campos,
                      enlaces=[direccion_de("hilo", a.nombre)],
                      acciones=[Accion(nombre="encargar", descripcion="pedirle algo, en su hilo de siempre (telar encargar)",
                                       params={"texto": ""})])

    def hacer(self, ctx, d, accion, params, version=""):
        if accion != "encargar":
            raise ErrorDeServicio(f"un agente no tiene la acción «{accion}»: encargar", 404)
        from telar.servicios import encargos

        texto = str(params.get("texto", "")).strip()
        if not texto:
            raise ErrorDeServicio("encargar: ¿qué le encargas? params {\"texto\": …}", 422)
        r = encargos.encargar(ctx, self.ver(ctx, d).id, texto)
        return Hecho(direccion=str(d), accion=accion, resultado=r.model_dump(mode="json"))


class Encargo(Tipo):
    """Un encargo (telar.encargo): `encargo:e-1a2b3c4d`. Vive en la máquina de quien lo hace; desde otra se le pide
    a esa (el pedido `encargo` del nodo), que es la de su `@máquina`, la de la nota de quien lo mandó o la del hilo
    al que se mandó. Mientras no llega, quien lo mandó lo ve en camino, con lo que anotó al mandarlo."""

    nombre = "encargo"
    descripcion = "un encargo a un hilo (telar mensaje --modo encargo): quién lo pidió, en qué va y cómo terminó"

    def _objeto(self, ctx, e: dict, maquina: str = "", en_camino: bool = False) -> Objeto:
        from telar import encargo

        campos = {k: e[k] for k in ("de", "para", "responder_a", "plazo", "resultado", "rechazado", "creado",
                                     "actualizado", "historia", "mensaje") if e.get(k) not in (None, "", [], False)}
        if encargo.vencido(e):
            campos["vencido"] = True
        if en_camino and e.get("retenido"):
            # no salió: no va en camino hasta que la persona lo suelte (telar mensaje --soltar)
            campos["retenido"] = str(e["retenido"])
        elif en_camino:
            campos["en_camino"] = True
        enlaces = [direccion_de("hilo", x) for x in dict.fromkeys((e.get("para", ""), e.get("responder_a", ""))) if x]
        enlaces += [str(x) for x in buscar(ctx, str(e.get("texto", ""))) if x.tipo != "encargo"][:10]
        acciones = [] if en_camino else [
            Accion(nombre=n, descripcion=encargo.ACCIONES[n][0], params=dict(encargo.ACCIONES[n][1]))
            for n in encargo.acciones_de(e)]
        texto = " ".join(str(e.get("texto", "")).split())
        return Objeto(direccion=direccion_de("encargo", e["id"]), tipo="encargo", id=e["id"], titulo=texto[:80],
                      estado=str(e.get("estado", "pedido")), resumen=texto[:400], campos=campos, enlaces=enlaces,
                      acciones=acciones, version="" if en_camino else encargo.version(e),
                      maquina=maquina or str(e.get("maquina", "")))

    def _donde(self, ctx, d: Direccion) -> tuple[str, dict | None]:
        """(la máquina donde buscarlo, la nota de quien lo mandó) de uno que no está aquí."""
        from telar import bus as mod_bus
        from telar import encargo

        nota = encargo.enviado(ctx.config, d.id)
        maquina = d.maquina or (nota or {}).get("maquina", "")
        if not maquina and nota and nota.get("para") and mod_bus.hay_bus(ctx.config):
            maquina = mod_bus.maquina_de(ctx.config, nota["para"])
        return maquina, nota

    def _de_otra(self, ctx, d: Direccion, pedido: dict):
        """Lo que responde la máquina donde vive: (respuesta, máquina, nota), o levanta ErrorDeServicio. La
        respuesta es None si allá no está (todavía) y hay nota de quien lo mandó."""
        from telar import bus as mod_bus

        aqui = mod_bus.maquina(ctx.config) if mod_bus.hay_bus(ctx.config) else ""
        maquina, nota = self._donde(ctx, d)
        if not maquina or maquina == aqui or not mod_bus.hay_bus(ctx.config):
            if nota is not None:
                return None, maquina, nota
            raise ErrorDeServicio(f"no hay un encargo {d.id} aquí, ni se sabe de qué máquina es (encargo:{d.id}@máquina)", 404)
        r = mod_bus.pedir(ctx.config, maquina, "encargo", {"id": d.id, **pedido}, espera=20)
        if r.get("ok"):
            return r, maquina, nota
        if r.get("codigo") == 404 and nota is not None and not pedido.get("accion"):
            return None, maquina, nota  # todavía no lo recoge su nodo
        raise ErrorDeServicio(r.get("error") or f"{maquina} no respondió", int(r.get("codigo") or 502))

    def ver(self, ctx, d):
        from telar import encargo

        e = encargo.leer(ctx.config, d.id) if encargo.FORMA_ID.fullmatch(d.id) else None
        if e is None and not encargo.FORMA_ID.fullmatch(d.id):
            raise ErrorDeServicio(f"«{d.id}» no es el id de un encargo: e- y ocho cifras hex (encargo:e-1a2b3c4d)", 404)
        if e is not None:
            return self._objeto(ctx, e)
        r, maquina, nota = self._de_otra(ctx, d, {})
        if r is None:
            # en camino: lo que anotó quien lo mandó
            return self._objeto(ctx, {**nota, "estado": "pedido"}, maquina, en_camino=True)
        return self._objeto(ctx, r["encargo"], maquina)

    def hacer(self, ctx, d, accion, params, version=""):
        from telar import encargo
        from telar.ordenes.mensaje import remitente

        quien = remitente(ctx)
        if encargo.leer(ctx.config, d.id) is not None:
            try:
                e = encargo.hacer(ctx, d.id, accion, params, version_leida=version, quien=quien)
            except encargo.ErrorDeEncargo as ex:
                raise ErrorDeServicio(str(ex), ex.codigo) from ex
            return Hecho(direccion=str(d), accion=accion, objeto=self._objeto(ctx, e))
        if not encargo.FORMA_ID.fullmatch(d.id):
            raise ErrorDeServicio(f"«{d.id}» no es el id de un encargo: e- y ocho cifras hex (encargo:e-1a2b3c4d)", 404)
        r, maquina, _ = self._de_otra(ctx, d, {"accion": accion, "params": params, "version": version, "quien": quien})
        if r is None:
            raise ErrorDeServicio(f"encargo:{d.id} todavía no llega a su máquina: no se le puede {accion}", 409)
        return Hecho(direccion=str(d), accion=accion, objeto=self._objeto(ctx, r["encargo"], maquina))


DE_FABRICA = (Tarea(), Hilo(), Proyecto(), Archivo(), Pendiente(), Agente(), Encargo(), Permiso(), Idea())


def tipos(ctx) -> dict[str, Tipo]:
    """Los tipos que hay: los de fábrica y los de los módulos instalados (un módulo no pisa uno de fábrica;
    `telar doctor` avisa del que queda tapado, `doctor._tapados`)."""
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
