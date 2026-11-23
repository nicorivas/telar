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
encargo (un pedido con estado y resultado, telar.encargo), permiso (lo que un hilo espera de la persona, solo
lectura), idea (de un producto) y mensaje (uno entre hilos, del registro del bus, solo lectura).
Un módulo agrega los suyos en su `modulo.toml`:

    [objetos.correo]
    ver = "correo-ver"            # una orden suya con consulta = true: recibe {"id": …}, da el objeto
    acciones = ["archivar"]       # otras consultas: reciben {"id": …, más los parámetros}
    esperando = "correo-esperan"  # opcional: recibe {}, da los suyos que esperan a la persona (abajo)
    listar = "correos"            # opcional: recibe {"tipo": "correo"}, da todos los suyos (abajo)
    plural = "correos"            # opcional: cómo se llaman juntos en una lista (su fuente en telar buscar)

y su `ver` devuelve un objeto JSON con los campos de `Objeto` que tenga (titulo, estado, resumen, campos,
enlaces, acciones); telar pone la dirección, el tipo y el id.

**Los de un tipo.** Un tipo que sabe listar los suyos lo hace con `Tipo.listar` (`telar objeto <tipo> --listar`,
`GET /objetos/<tipo>`): de fábrica, tarea (las abiertas), hilo (los de esta máquina), proyecto y agente; los demás
dicen que no listan (404) y se abren de a uno, por su dirección. Un módulo lo declara con `listar = "<orden>"`: una
consulta que recibe `{"tipo": …}` (así una orden sirve a varios tipos) y da `{"objetos": [{id, titulo, estado,
resumen, campos, enlaces, acciones, version}], "fallas"?: [texto]}`, cada uno como lo da su `ver`. Cada tipo de un
módulo que lista es además una fuente de `telar buscar` (telar.servicios.buscar, `objeto:<tipo>`), con su `plural` de
nombre.

**Lo que espera a la persona.** Cada tipo sabe además decir cuáles de los suyos esperan una decisión de la persona
(`Tipo.esperando`, una `Espera` por objeto): el permiso o la pregunta de un hilo, el `avance` de una tarea, un
mensaje retenido. `telar esperas` (telar.servicios.esperas) los junta en una sola lista. Un módulo lo declara con
`esperando = "<orden>"` en su `[objetos.X]`: una consulta que recibe `{}` y da `{"esperas": [{id, clase, desde,
titulo, resumen, enlaces, campos}]}` (docs/propuestas/lo-que-espera-a-la-persona.md).

**Lo que la persona contestó y espera al agente.** Del otro lado: una tarea que la persona contestó (su última
`[respuesta]`, también una instrucción o un prompt) y por la que el agente todavía no pasa (`Tarea.contestadas`,
una `Contestada` por tarea; la regla, `contestada`). `telar esperas` las trae aparte, en `contestadas`.
"""

from __future__ import annotations

import inspect
import re
from urllib.parse import unquote

from pydantic import BaseModel, Field

# la forma de una dirección vive aparte, sin pydantic, para quien solo la escribe (el contexto de un gancho)
from telar.direcciones import _DIRECCION, _ESCAPAR, Direccion, _escapar, direccion_de  # noqa: F401
from telar.servicios import ErrorDeServicio


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


class Objetos(BaseModel):
    """Los objetos de un tipo (`telar objeto <tipo> --listar`, `GET /objetos/<tipo>`), cada uno como lo da `ver`."""

    tipo: str
    objetos: list[Objeto] = Field(default_factory=list)
    #: lo que no se pudo leer (un archivo roto, un objeto sin la forma): se dice, no se calla
    fallas: list[str] = Field(default_factory=list)


class Hecho(BaseModel):
    direccion: str
    accion: str
    objeto: Objeto | None = None
    resultado: dict = Field(default_factory=dict)


class Espera(BaseModel):
    """Un objeto que espera una decisión de la persona, como lo da `Tipo.esperando` (docs/contratos.md, «telar
    esperas --json»). Es lo justo para mostrarlo en una lista: el objeto entero se abre por su dirección."""

    direccion: str
    tipo: str
    #: de qué clase de espera es: `permiso`, `pregunta`, `avance:<marca>` (`avance:pregunta`, `avance:cerrar`…),
    #: `retenido`, o la que diga el tipo de un módulo
    clase: str
    #: desde cuándo espera: fecha y hora de esta máquina (`2026-11-17T09:30:00`), o solo la fecha si no se sabe la hora
    desde: str = ""
    titulo: str = ""
    resumen: str = ""
    #: dónde se ve o se contesta: su hilo, su proyecto (el primero es el principal)
    enlaces: list[str] = Field(default_factory=list)
    maquina: str = ""
    #: lo propio de cada clase: las preguntas con sus opciones, el motivo de un retenido, la prioridad de una tarea
    campos: dict = Field(default_factory=dict)
    #: a qué parte de la vida pertenece, de las que declara `[mundos]` (telar.mundos); "" si no calza en ninguna o no
    #: se declaran. La pone su tipo si la sabe (una tarea, por su área) y si no, quien las junta
    mundo: str = ""
    #: el agente residente del que es (su clave), si es de uno: el de su hilo, el que pregunta o el de la carpeta donde
    #: vive, si declara su mundo (telar.mundos, `Clasificador.agente_de_espera`). Con `[mundos]`, la pone quien las junta;
    #: la página no nombra lo de un agente de otro mundo que el puesto, ni en el modo todo
    agente: str = ""


#: el largo del resumen de una espera: lo que cabe en una o dos líneas de una lista
TOPE_RESUMEN = 300


#: la nota con que el agente cierra el ciclo de una respuesta: «apliqué: …» (con o sin tilde, en cualquier caja)
_APLIQUE = re.compile(r"^\s*apliqu[eé]\s*:\s*", re.IGNORECASE)


def aplicado(historia) -> str:
    """Lo que hizo el agente con la última respuesta de la persona: el texto de la última nota «apliqué: …» que vino
    después de la última línea [respuesta] de la historia (sin la marca). Vacío si nunca respondió o si el agente
    todavía no dice qué hizo."""
    import unicodedata

    ultima = max((i for i, c in enumerate(historia) if c.tipo == "respuesta"), default=None)
    if ultima is None:
        return ""
    for c in reversed(historia[ultima + 1:]):
        texto = unicodedata.normalize("NFC", c.texto or "")
        if c.tipo == "nota" and _APLIQUE.match(texto):
            return _APLIQUE.sub("", texto, count=1).strip()
    return ""


class Contestada(BaseModel):
    """Una tarea que la persona contestó y que espera al agente (docs/contratos.md, «telar esperas --json»): lo justo para
    una fila. La tarea entera se abre por su dirección."""

    direccion: str
    titulo: str = ""
    #: cuándo contestó (su última `[respuesta]`): fecha y hora de esta máquina, como `Espera.desde`
    cuando: str = ""
    #: lo que contestó: las `[respuesta]` desde la última marca del agente, en orden y juntas con « · » (sin los avisos
    #: de «revisar ya»), en una línea y con tope
    respuesta: str = ""
    #: cuándo se le avisó al agente que la atendiera ya: el último «prompt: …» de esas respuestas («hazte cargo ya» en
    #: «Contestar», «revisar ya» en Táctica); "" si no se le avisó
    encargada: str = ""
    enlaces: list[str] = Field(default_factory=list)
    mundo: str = ""


#: lo que deja el agente en la historia de una tarea al pasar por ella: después de una respuesta, cualquiera de estas
#: dice que ya la vio (la nota «apliqué: …» cierra el ciclo). Lo demás (`edita`, `mover`, `espera`) puede ser de
#: cualquiera: no cuenta para ninguno de los dos lados
MARCAS_DEL_AGENTE = frozenset({"avance", "nota", "cierre", "secuela"})

#: el aviso al agente para que la atienda ya, al inicio de una respuesta (`prompt:`, componentes/contestar.ts)
_PROMPT = re.compile(r"^\s*prompt\s*:", re.IGNORECASE)
#: el de «revisar ya» (Táctica, componentes/tactica.ts `lineaRevisarYa`): no es algo que la persona contestó
_REVISAR_YA = re.compile(r"^\s*prompt\s*:\s*revisar ya\b", re.IGNORECASE)
#: el largo de lo contestado en una fila
TOPE_RESPUESTA = 200


def _momento_de(c) -> str:
    return momento(f"{c.fecha}T{c.hora}:00" if c.hora else c.fecha)


def contestada(t) -> Contestada | None:
    """La tarea como espera al agente, si la persona la contestó y el agente todavía no pasa por ella: abierta (ni
    cerrada ni en algún día), sin un `avance` pendiente (esa espera a la persona) y con alguna `[respuesta]` después
    de la última marca del agente (MARCAS_DEL_AGENTE). Si no, None."""
    import unicodedata

    from telar.tipos.tarea import TERMINALES

    if t.avance or t.estado in TERMINALES or t.estado == "algun-dia":
        return None
    ultima = max((i for i, c in enumerate(t.historia) if c.tipo in MARCAS_DEL_AGENTE), default=-1)
    suyas = [c for c in t.historia[ultima + 1:] if c.tipo == "respuesta"]
    if not suyas:
        return None
    texto = [unicodedata.normalize("NFC", c.texto or "") for c in suyas]
    avisos = [c for c, x in zip(suyas, texto) if _PROMPT.match(x)]
    # «revisar ya» no es algo que contestó: ni lo que dijo ni cuándo (así, encargarla no la mueve)
    dijo = [(c, x) for c, x in zip(suyas, texto) if not _REVISAR_YA.match(x)]
    return Contestada(direccion=direccion_de("tarea", t.id), titulo=t.titulo, cuando=_momento_de((dijo or [(suyas[-1], "")])[-1][0]),
                      respuesta=_corto(" · ".join(x for _, x in dijo), TOPE_RESPUESTA), encargada=_momento_de(avisos[-1]) if avisos else "",
                      enlaces=[direccion_de("proyecto", t.proyecto)] if t.proyecto else [], mundo=getattr(t, "mundo", "") or "")


def _corto(texto: str, tope: int = TOPE_RESUMEN) -> str:
    """Un texto en una línea y con tope (con «…» si se cortó)."""
    t = " ".join(str(texto or "").split())
    return t if len(t) <= tope else t[:tope - 1].rstrip() + "…"


def momento(texto) -> str:
    """Una fecha o fecha y hora ISO como la lleva una espera: la hora de esta máquina, sin zona y en segundos
    (`2026-11-17T09:30:00`); una fecha sola queda sola (`2026-11-17`). Lo que no se lee, "" ."""
    from datetime import date, datetime

    t = str(texto or "").strip()
    if not t:
        return ""
    try:
        if len(t) == 10:
            return date.fromisoformat(t).isoformat()
        d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if d.tzinfo is not None:
        d = d.astimezone().replace(tzinfo=None)
    return d.replace(microsecond=0).isoformat()


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

    def esperando(self, ctx) -> list[Espera]:
        """Los objetos de este tipo que esperan una decisión de la persona; [] si el tipo no tiene de esos. Si no se
        pueden leer, levanta (ErrorDeServicio): quien junta las de todos los tipos lo anota y sigue con los demás."""
        return []

    @property
    def lista(self) -> bool:
        """Si sabe listar los suyos (`listar`)."""
        return type(self).listar is not Tipo.listar

    def listar(self, ctx) -> Objetos:
        """Todos los suyos, cada uno como lo da `ver`. El que no sabe, lo dice (404): los suyos se abren de a uno."""
        raise ErrorDeServicio(f"«{self.nombre}» no lista los suyos: se abren de a uno, por su dirección "
                              f"({self.nombre}:<id>)", 404)


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
        if t.estado not in tipo.TERMINALES:
            acciones.append(Accion(nombre="unir", params={"con": ""},
                                   descripcion="es la misma que otra: se le une (su texto pasa a esa, y esta se descarta)"))
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
        # lo que la bandeja leyó de otra máquina ya no es: la próxima lectura va a buscarlo (quien contestó relee al tiro)
        Tarea._reciente = {}
        return Hecho(direccion=str(d), accion=accion, objeto=self._objeto(t, _hay_productos(ctx)))

    def listar(self, ctx):
        """Las abiertas (`telar tipo tarea lista`); las que no se leyeron, en `fallas`."""
        from telar.servicios import tipos as servicio

        r = servicio.lista(ctx, "tarea")
        productos = _hay_productos(ctx)
        return Objetos(tipo=self.nombre, objetos=[self._objeto(t, productos) for t in r.tareas],
                       fallas=[f"{k}: {v}" for k, v in r.fallas.items()])

    def esperando(self, ctx):
        """Las tareas abiertas con un `avance` sin contestar: lo que un agente dejó para que la persona decida
        (`proponer`: preparado, cerrar, pregunta o choca). Solo se leen: nada de aquí toca el `avance`."""
        from telar import mundos
        from telar.servicios import tipos as servicio

        declarado = next((t for t in getattr(ctx.config, "tipos", ()) if getattr(t, "clave", "") == "tarea"), None)
        if declarado is None:
            return []  # esta máquina no tiene tareas ([tipos.tarea]): no es una falla
        r = self._lista_reciente(ctx, declarado)
        salida = []
        for t in r.tareas:
            if not t.avance:
                continue
            marca, _, fecha = t.avance.partition(" ")
            clase, _, como = marca.partition(":")
            # el texto de la propuesta es la última línea [avance] de su historia: «pregunta: ¿la cierro?»
            linea = next((c for c in reversed(t.historia) if c.tipo == "avance"), None)
            texto = (linea.texto if linea else "").strip()
            if texto.startswith(f"{marca}:"):
                texto = texto[len(marca) + 1:].strip()
            desde = fecha.strip() or (linea.fecha if linea else "")
            if linea and linea.hora and linea.fecha == desde:
                desde = f"{desde}T{linea.hora}:00"
            # `texto`, la propuesta entera (el resumen se corta), y `version`: para contestarla desde la bandeja;
            # `aplique`, lo que hizo el agente con la respuesta anterior (su nota «apliqué: …»), si la dejó
            campos = {k: v for k, v in (("avance", t.avance), ("como", como), ("prioridad", t.prioridad), ("vence", t.vence),
                                         ("dueno", t.dueno), ("texto", texto), ("version", getattr(t, "version", "")),
                                         ("aplique", aplicado(t.historia)))
                      if v not in ("", None)}
            salida.append(Espera(direccion=direccion_de("tarea", t.id), tipo="tarea", clase=f"avance:{clase}",
                                 desde=momento(desde), titulo=t.titulo, resumen=_corto(texto), campos=campos,
                                 enlaces=[direccion_de("proyecto", t.proyecto)] if t.proyecto else [],
                                 mundo=mundos.de_tarea(ctx.config, t.area, t.proyecto)))
        if r.fallas:
            # un archivo que no se leyó puede ser una tarea que espera: se dice, no se calla
            raise Incompletas(salida, f"{len(r.fallas)} archivos de tareas no se leyeron: "
                                   + "; ".join(f"{k}: {v}" for k, v in list(r.fallas.items())[:3]))
        return salida

    def contestadas(self, ctx) -> list[Contestada]:
        """Las tareas que la persona contestó y por las que el agente todavía no pasa (`contestada`), de la que se
        contestó hace más tiempo a la más nueva. Sale de la misma lectura que `esperando` (de otra máquina, la de hace
        poco: `_lista_reciente`). Lo que no se leyó ya lo dice `esperando`."""
        from telar import mundos

        declarado = next((t for t in getattr(ctx.config, "tipos", ()) if getattr(t, "clave", "") == "tarea"), None)
        if declarado is None:
            return []
        salida = []
        for t in self._lista_reciente(ctx, declarado).tareas:
            c = contestada(t)
            if c is not None:
                c.mundo = mundos.de_tarea(ctx.config, t.area, t.proyecto)
                salida.append(c)
        return sorted(salida, key=lambda c: (c.cuando, c.direccion))


    #: las tareas de otra máquina, leídas hace menos de esto (segundos), no se vuelven a pedir para la bandeja: allá
    #: cada pedido corre `telar tipo tarea lista` entero (unos 2,5 s desde el laptop), y el número de la barra pregunta
    #: seguido. Las de aquí salen del índice en memoria, siempre al día
    RECIENTE = 30.0
    _reciente: dict = {}

    def _lista_reciente(self, ctx, declarado):
        import time

        from telar.servicios import tipos as servicio

        if not servicio._alla(ctx, declarado):
            return servicio.lista(ctx, "tarea")
        clave = (declarado.en, id(ctx.config))
        hora, r = self._reciente.get(clave, (0.0, None))
        if r is None or time.monotonic() - hora > self.RECIENTE:
            r = servicio.lista(ctx, "tarea")
            Tarea._reciente = {clave: (time.monotonic(), r)}
        return r


class Incompletas(ErrorDeServicio):
    """Una fuente que leyó algo pero no todo: lo que leyó va en `esperas`, y por qué falta el resto, en `fallas`."""

    def __init__(self, esperas: list, mensaje: str):
        super().__init__(mensaje, 502)
        self.esperas = esperas


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

    def listar(self, ctx):
        """Los de esta máquina, como `telar hilos` (con las ventanas de los de otra, que llevan su `@máquina`)."""
        from telar.ordenes import _comun

        tel = _comun.tejer(ctx)
        return Objetos(tipo=self.nombre, objetos=[
            self._objeto(_comun.json_hilo(h, tel), h.remoto if h.remoto and h.remoto != "?" else "") for h in tel.hilos])

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

    @staticmethod
    def _lista(ctx) -> list[dict]:
        from telar.servicios import proyectos

        return [x.model_dump() for x in proyectos.lista(ctx).proyectos]

    def ver(self, ctx, d):
        lista = self._lista(ctx)
        ruta = d.id.strip("/")
        p = next((x for x in lista if (x.get("ruta") or "").strip("/") == ruta), None) \
            or next((x for x in lista if x.get("nombre") == d.id), None)
        if p is None:
            raise ErrorDeServicio(f"el perfil no tiene una unidad «{d.id}» (telar proyectos)", 404)
        return self._objeto(p, ruta)

    def listar(self, ctx):
        """Las unidades del perfil, como `telar proyectos`."""
        return Objetos(tipo=self.nombre, objetos=[self._objeto(p, p.get("nombre") or "") for p in self._lista(ctx)])

    @staticmethod
    def _objeto(p: dict, ruta: str) -> Objeto:
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
        from telar.lectura import sin_escapes
        from telar.servicios import archivos

        a = archivos.leer_en(ctx, d.id, d.maquina)
        titulo = next((sin_escapes(l[2:].strip()) for l in a.texto.splitlines() if l.startswith("# ")), a.ruta.rsplit("/", 1)[-1])
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
        j, maquina = Hilo().buscar(ctx, Direccion("hilo", d.id, d.maquina))
        nombre = j["nombre"]
        if j.get("atencion") != "espera":
            estado = {"trabajando": "está trabajando", "termino": "terminó su turno"}.get(str(j.get("atencion")), "no está esperando")
            raise ErrorDeServicio(f"«{nombre}» no espera nada de nadie: {estado} (telar objeto hilo:{_escapar(nombre)})", 404)
        desde = str(j.get("atencion_desde") or "")
        # lo que pide lo anota el gancho de esta máquina; de un hilo de otra, se sabe que espera y desde cuándo
        pide, clase, preguntas, pid = _lo_que_pide(ctx.config, nombre) if not maquina else ("", "", [], "")
        campos = {k: v for k, v in (("hilo", nombre), ("desde", desde), ("pide", pide), ("clase", clase),
                                     ("preguntas", preguntas), ("pregunta", pid),
                                     ("contestar", f"en el hilo: telar ir {nombre}")) if v}
        return Objeto(direccion=direccion_de("permiso", nombre, maquina), tipo="permiso", id=nombre,
                      titulo=_titulo_espera(nombre, pide, clase, preguntas), estado="pendiente",
                      resumen=_opciones(preguntas) if preguntas else pide, campos=campos,
                      enlaces=_enlaces_hilo(j, maquina), version=desde, maquina=maquina)

    def hacer(self, ctx, d, accion, params, version=""):
        raise ErrorDeServicio(f"«{d}» todavía no se contesta desde aquí: en su hilo (telar ir {d.id})", 404)

    def esperando(self, ctx):
        """Los hilos vivos cuyo agente espera a la persona: los de aquí, con lo que pide y la pregunta en vivo si la
        hay; los de las otras máquinas en línea, con lo que publicó cada una (que espera y desde cuándo)."""
        from telar import bus as mod_bus
        from telar import espejo
        from telar.ordenes import _comun

        salida = []
        tel = _comun.tejer(ctx, con_ficha=False)
        for h in tel.hilos:
            # una ventana de aquí de un hilo de otra máquina: lo cuenta la foto de esa máquina, abajo
            if h.remoto or h.atencion.value != "espera" or not tel.vivo(h):
                continue
            salida.append(self._espera(_comun.json_hilo(h, tel, con_ficha=False), "", *_lo_que_pide(ctx.config, h.nombre)))
        if not mod_bus.hay_bus(ctx.config):
            return salida
        yo = mod_bus.maquina(ctx.config)
        for foto in espejo.leer_todos(ctx.config):
            # de una máquina que dejó de publicar no se sabe si sigue esperando: no se muestra un fantasma
            if not foto.get("en_linea") or foto.get("nombre") == yo:
                continue
            for j in foto.get("hilos") or []:
                if isinstance(j, dict) and not j.get("remoto") and j.get("atencion") == "espera" and j.get("vivo"):
                    salida.append(self._espera(j, foto["nombre"], "", "", [], ""))
        return salida

    def _espera(self, j: dict, maquina: str, pide: str, clase: str, preguntas: list, pid: str = "") -> Espera:
        nombre = j["nombre"]
        # `pregunta`: el id de la pregunta en vivo, para contestarla desde la bandeja (POST /hilos/responder)
        campos = {k: v for k, v in (("hilo", nombre), ("pide", pide), ("preguntas", preguntas), ("pregunta", pid)) if v}
        return Espera(direccion=direccion_de("permiso", nombre, maquina), tipo="permiso",
                      clase="pregunta" if clase == "pregunta" else "permiso", desde=momento(j.get("atencion_desde")),
                      titulo=_titulo_espera(nombre, pide, clase, preguntas),
                      resumen=_corto(_opciones(preguntas) if preguntas else pide), enlaces=_enlaces_hilo(j, maquina),
                      maquina=maquina, campos=campos)


def _lo_que_pide(config, hilo: str) -> tuple[str, str, list, str]:
    """(lo que pide, su clase, las preguntas en vivo, el id de esa pregunta) de un hilo de esta máquina que espera: lo
    que anotó el gancho (Estado.espera) y, si su agente le preguntó con opciones y el diálogo sigue abierto
    (mod/pregunta.json, telar.historia), esas preguntas, como las lee `telar hilo leer`, y la clase es `pregunta`."""
    from telar import estado as mod_estado
    from telar import historia

    e = mod_estado.abrir(config).espera(hilo) or {}
    pide, clase = str(e.get("pide") or ""), str(e.get("clase") or "")
    abierta = historia.pregunta_abierta(config, hilo)
    preguntas, pid = [], ""
    if abierta:
        from telar.agente.claude_code import _pregunta

        preguntas = _pregunta(str(abierta.get("id", "")), abierta.get("preguntas"), None, "pendiente")["preguntas"]
        if preguntas:
            clase, pid = "pregunta", str(abierta.get("id", ""))
    return pide, clase, preguntas, pid


def _titulo_espera(nombre: str, pide: str, clase: str, preguntas: list) -> str:
    if preguntas and preguntas[0].get("pregunta"):
        return preguntas[0]["pregunta"]
    return pide or (f"«{nombre}» te espera" if clase != "pregunta" else f"«{nombre}» te pregunta algo")


def _opciones(preguntas: list) -> str:
    """Las opciones de la primera pregunta, en una línea («Oscura · Clara»), y cuántas preguntas más hay."""
    if not preguntas:
        return ""
    texto = " · ".join(o.get("etiqueta", "") for o in preguntas[0].get("opciones") or [] if o.get("etiqueta"))
    if len(preguntas) > 1:
        texto += f" (y {len(preguntas) - 1} pregunta{'s' if len(preguntas) > 2 else ''} más)"
    return texto.strip()


def _enlaces_hilo(j: dict, maquina: str) -> list[str]:
    enlaces = [direccion_de("hilo", j["nombre"], maquina)]
    if j.get("relativa") and j.get("relativa") not in (".", ""):
        enlaces.append(direccion_de("proyecto", j["relativa"]))
    return enlaces


class Mensaje(Tipo):
    """Un mensaje entre hilos, del registro del bus (telar.bus.registro): `mensaje:<id>`, de solo lectura. Lo que
    espera a la persona son los retenidos (el freno de cadenas, `telar mensaje --retenidos`): salen cuando ella los
    suelta (`telar mensaje --soltar <id>`) o dejan de esperar cuando los descarta (`--descartar <id>`), que todavía no se
    hace desde aquí."""

    nombre = "mensaje"
    descripcion = "un mensaje entre hilos (telar mensaje): de quién, para quién, su texto y si salió o quedó retenido; solo lectura"

    #: cuántos mensajes del registro se miran: los mismos que mira `telar mensaje --soltar` (y `--retenidos`)
    REGISTRO = 500

    def _registro(self, ctx) -> list[dict]:
        from telar import bus as mod_bus

        if not mod_bus.hay_bus(ctx.config):
            raise ErrorDeServicio("no hay bus ([bus] en la configuración): sin bus no hay mensajes entre hilos", 404)
        try:
            # por partes: `telar serve` pregunta seguido (el número de la barra), y del bus pide solo lo nuevo
            return mod_bus.registro_al_dia(ctx.config, self.REGISTRO)
        except mod_bus.ErrorDeBus as e:
            raise ErrorDeServicio(str(e), 502) from e

    def ver(self, ctx, d):
        from telar.ordenes.mensaje import retenidos

        lista = self._registro(ctx)
        m = next((x for x in reversed(lista) if x.get("id") == d.id), None)
        if m is None:
            raise ErrorDeServicio(f"no hay un mensaje {d.id} entre los últimos {self.REGISTRO} del registro", 404)
        retenido = any(x.get("id") == d.id for x in retenidos(lista))
        campos = {k: m[k] for k in ("de", "para", "modo", "creado", "saltos", "motivo", "encargo", "plazo",
                                    "descartado", "descartado_por") if m.get(k) not in (None, "")}
        if retenido:
            campos["soltar"] = f"telar mensaje --soltar {d.id}"
            campos["descartar"] = f"telar mensaje --descartar {d.id}"
        elif m.get("estado") != "descartado":
            campos.pop("motivo", None)  # se soltó: el motivo era el de la retención
        return Objeto(direccion=direccion_de("mensaje", d.id), tipo="mensaje", id=d.id, titulo=self._titulo(m),
                      estado="retenido" if retenido else str(m.get("estado") or "enviado"),
                      resumen=_corto(m.get("texto", ""), 400), campos=campos, enlaces=self._enlaces(m))

    def esperando(self, ctx):
        from telar import bus as mod_bus
        from telar.ordenes.mensaje import retenidos

        if not mod_bus.hay_bus(ctx.config):
            return []
        return [Espera(direccion=direccion_de("mensaje", m["id"]), tipo="mensaje", clase="retenido",
                       desde=momento(m.get("creado")), titulo=self._titulo(m), resumen=_corto(m.get("texto", "")),
                       enlaces=self._enlaces(m),
                       campos={k: m[k] for k in ("de", "para", "motivo", "modo", "encargo", "texto") if m.get(k)})
                for m in retenidos(self._registro(ctx)) if m.get("id")]

    @staticmethod
    def _titulo(m: dict) -> str:
        return f"«{m.get('de') or '?'}» → «{m.get('para') or '?'}»"

    @staticmethod
    def _enlaces(m: dict) -> list[str]:
        # a quién iba primero: es donde llega si se suelta
        enlaces = [direccion_de("hilo", x) for x in dict.fromkeys((m.get("para", ""), m.get("de", ""))) if x]
        if m.get("encargo"):
            enlaces.append(direccion_de("encargo", str(m["encargo"])))
        return enlaces


class DeModulo(Tipo):
    """Un tipo que trae un módulo: `ver` y sus acciones son consultas suyas (telar.servicios.modulos)."""

    def __init__(self, modulo: str, nombre: str, ver: str, acciones: tuple, descripcion: str, esperando: str = "",
                 listar: str = "", plural: str = ""):
        self.modulo, self.nombre, self._ver, self._acciones, self.descripcion = modulo, nombre, ver, acciones, descripcion
        self._esperando, self._listar = esperando, listar
        #: cómo se llaman los suyos juntos, en una lista (`plural` en su [objetos.X]); sin él, el tipo
        self.plural = plural or nombre

    @property
    def lista(self) -> bool:
        return bool(self._listar)

    def _consultar(self, ctx, verbo, params, maquina):
        from telar.servicios import modulos

        return modulos.consultar(ctx, self.modulo, verbo, params, maquina)

    def ver(self, ctx, d):
        r = self._consultar(ctx, self._ver, {"id": d.id}, d.maquina)
        datos = {k: v for k, v in r.items() if k in Objeto.model_fields and k not in ("direccion", "tipo", "id")}
        datos.setdefault("acciones", [{"nombre": a} for a in self._acciones])
        return Objeto(direccion=str(d), tipo=self.nombre, id=d.id, maquina=d.maquina, **datos)

    def listar(self, ctx):
        """Su consulta `listar` ([objetos.X] listar = "<orden>"): recibe {"tipo": …} y da {"objetos": [{id, titulo,
        estado, resumen, campos, enlaces, acciones, version}], "fallas"?: […]}, cada uno como lo da su `ver`. telar pone
        la dirección y el tipo, y sin `acciones`, las del tipo. Lo que no tiene id, o no tiene la forma de un objeto, va
        a `fallas`; si la respuesta no tiene esa forma, es una falla del módulo (502)."""
        from pydantic import ValidationError

        if not self._listar:
            return super().listar(ctx)
        r = self._consultar(ctx, self._listar, {"tipo": self.nombre}, "")
        lista = r.get("objetos")
        if not isinstance(lista, list):
            raise ErrorDeServicio(f"{self.modulo} {self._listar}: se esperaba {{\"objetos\": […]}}", 502)
        fallas = [str(f) for f in r["fallas"] if isinstance(f, str)] if isinstance(r.get("fallas"), list) else []
        salida = []
        for i, o in enumerate(lista):
            ident = str(o.get("id") or "").strip() if isinstance(o, dict) else ""
            if not ident:
                fallas.append(f"{self.modulo} {self._listar}: el {i + 1}.º no trae id")
                continue
            datos = {k: v for k, v in o.items() if k in Objeto.model_fields and k not in ("direccion", "tipo", "id", "maquina")}
            datos.setdefault("acciones", [{"nombre": a} for a in self._acciones])
            try:
                salida.append(Objeto(direccion=direccion_de(self.nombre, ident), tipo=self.nombre, id=ident, **datos))
            except ValidationError as e:
                fallas.append(f"{direccion_de(self.nombre, ident)}: no tiene la forma de un objeto "
                              f"({e.errors()[0].get('loc', ('?',))[0]})")
        return Objetos(tipo=self.nombre, objetos=salida, fallas=fallas)

    def hacer(self, ctx, d, accion, params, version=""):
        if accion not in self._acciones:
            raise ErrorDeServicio(f"«{self.nombre}» no tiene la acción «{accion}»: {', '.join(self._acciones) or 'ninguna'}", 404)
        r = self._consultar(ctx, accion, {"id": d.id, **params, **({"version": version} if version else {})}, d.maquina)
        return Hecho(direccion=str(d), accion=accion, resultado=r)

    def esperando(self, ctx):
        """Su consulta `esperando` ([objetos.X] esperando = "<orden>"): recibe {} y da {"esperas": [{id, clase,
        desde, titulo, resumen, enlaces, campos}]}. telar pone la dirección y el tipo; sin `clase`, la del tipo. Lo
        que no tiene id se deja fuera; si la respuesta no tiene esa forma, es una falla del módulo."""
        if not self._esperando:
            return []
        r = self._consultar(ctx, self._esperando, {}, "")
        lista = r.get("esperas")
        if not isinstance(lista, list):
            raise ErrorDeServicio(f"{self.modulo} {self._esperando}: se esperaba {{\"esperas\": […]}}", 502)
        salida = []
        for e in lista:
            if not isinstance(e, dict) or not str(e.get("id") or "").strip():
                continue
            enlaces = [str(x) for x in e.get("enlaces") or [] if isinstance(x, str)] \
                if isinstance(e.get("enlaces"), list) else []
            salida.append(Espera(direccion=direccion_de(self.nombre, str(e["id"]).strip()), tipo=self.nombre,
                                 clase=_corto(e.get("clase") or self.nombre, 40), desde=momento(e.get("desde")),
                                 titulo=_corto(e.get("titulo") or "", 200), resumen=_corto(e.get("resumen") or ""),
                                 enlaces=enlaces[:10], campos=e["campos"] if isinstance(e.get("campos"), dict) else {}))
        return salida


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
        return self._objeto(a)

    def listar(self, ctx):
        """Los agentes residentes, como `telar agentes`."""
        from telar import agentes as mod_agentes

        return Objetos(tipo=self.nombre, objetos=[self._objeto(a) for a in mod_agentes.descubrir(ctx.config)])

    @staticmethod
    def _objeto(a) -> Objeto:
        from telar import agentes as mod_agentes

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
        if en_camino and e.get("descartado"):
            # la persona descartó el mensaje retenido (telar mensaje --descartar): no sale nunca
            campos.update({k: str(e[k]) for k in ("descartado", "descartado_por") if e.get(k)})
        elif en_camino and e.get("retenido"):
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
            # en camino: lo que anotó quien lo mandó; si se descartó antes de salir, ya no va a llegar
            estado = "cancelado" if nota.get("descartado") else "pedido"
            return self._objeto(ctx, {**nota, "estado": estado}, maquina, en_camino=True)
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


DE_FABRICA = (Tarea(), Hilo(), Proyecto(), Archivo(), Pendiente(), Agente(), Encargo(), Permiso(), Idea(), Mensaje())


def tipos(ctx) -> dict[str, Tipo]:
    """Los tipos que hay: los de fábrica y los de los módulos instalados (un módulo no pisa uno de fábrica;
    `telar doctor` avisa del que queda tapado, `doctor._tapados`)."""
    salida = {t.nombre: t for t in DE_FABRICA}
    for m in getattr(ctx.config, "modulos", ()):
        for nombre, o in getattr(m, "objetos", {}).items():
            if nombre not in salida:
                salida[nombre] = DeModulo(m.nombre, nombre, o["ver"], tuple(o.get("acciones", ())), o.get("descripcion", ""),
                                          o.get("esperando", ""), o.get("listar", ""), o.get("plural", ""))
    return salida


def _tipo(ctx, d: Direccion) -> Tipo:
    t = tipos(ctx).get(d.tipo)
    if t is None:
        raise ErrorDeServicio(f"no hay un tipo «{d.tipo}»: {', '.join(sorted(tipos(ctx)))}", 404)
    return t


def ver(ctx, direccion: str) -> Objeto:
    d = leer(direccion)
    return _tipo(ctx, d).ver(ctx, d)


#: un tipo solo, sin id (`decision`, o `decision:`): la colección de los suyos
_SOLO_TIPO = re.compile(r"(?P<tipo>[a-z0-9][a-z0-9_-]*):?")


def es_tipo(texto: str) -> str:
    """El tipo si `texto` es un tipo solo (`decision` o `decision:`), sin id; "" si no (es una dirección, o nada)."""
    m = _SOLO_TIPO.fullmatch(texto.strip())
    return m.group("tipo") if m else ""


def listar(ctx, tipo: str) -> Objetos:
    """Los objetos de un tipo (`decision`, o `decision:`). 404 si no hay ese tipo o si no lista los suyos."""
    nombre = es_tipo(tipo)
    if not nombre:
        raise ErrorDeServicio(f"«{tipo}» no es un tipo: se escribe solo, como tarea (telar objeto --tipos dice cuáles hay)", 422)
    t = tipos(ctx).get(nombre)
    if t is None:
        raise ErrorDeServicio(f"no hay un tipo «{nombre}»: {', '.join(sorted(tipos(ctx)))}", 404)
    return t.listar(ctx)


def hacer(ctx, direccion: str, accion: str, params: dict | None = None, version: str = "") -> Hecho:
    d = leer(direccion)
    return _tipo(ctx, d).hacer(ctx, d, accion, params or {}, version)
