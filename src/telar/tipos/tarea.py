"""El tipo tarea: su modelo y sus dos formatos, el archivo propio y la casilla de un documento.

    from telar.tipos.tarea import ARCHIVO, CASILLA
    t = ARCHIVO.leer(texto, id="T84")
    nuevo = ARCHIVO.escribir(texto, t, t.model_copy(update={"estado": "hecha", "cerrada": "2026-10-19"}))
    c = CASILLA.leer("- [ ] Revisar el NDA @owner(Ana) @deadline(2026-10-30)")

**El archivo propio** es una tarea por archivo (`T84.md`): arriba, entre dos `---`, una línea
`clave: valor` por campo (no es YAML: un título puede llevar «:» sin comillas), en un orden fijo; después
el texto libre (el contexto) y dos secciones, `## Conexiones` y `## Historia`. Cada línea de la historia es
`- AAAA-MM-DD [HH:MM] [tipo] texto`. Las claves y su orden son configurables (`FormatoArchivo(claves=…)`): un
repositorio en inglés puede decir `status` y `due` donde este dice `estado` y `vence`.

Leer es tolerante: una clave repetida vale la última, una línea que no es `clave: valor` se conserva, una
línea de historia que no calza es una nota. Escribir es mínimo: un campo que cambia reescribe su línea, uno
nuevo se agrega en su lugar del orden, uno que se vacía se quita; lo demás queda byte por byte.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from telar.tipos import ErrorDeFormato

__all__ = ["Tarea", "Cambio", "FormatoArchivo", "FormatoCasilla", "ARCHIVO", "CASILLA", "ESTADOS", "TERMINALES",
           "ACCIONES", "ErrorDeAccion", "nueva", "PREFIJO"]

ESTADOS = ("activa", "espera", "algun-dia", "hecha", "caduca", "descartada")
TERMINALES = ("hecha", "caduca", "descartada")


class Cambio(BaseModel):
    """Una línea de la historia: lo que le pasó a la tarea, cuándo y de qué clase."""

    fecha: str = ""
    hora: str = ""
    tipo: str = "nota"
    texto: str = ""


class Tarea(BaseModel):
    """Una tarea. Los valores por defecto son los de un archivo que no dice el campo."""

    id: str = ""
    titulo: str = ""
    estado: str = "activa"
    #: en curso: una casilla `[>]` (el archivo propio no lo guarda)
    en_curso: bool = False
    prioridad: int = 2
    vence: str = ""
    espera: str = ""
    dueno: str = ""
    proyecto: str = ""
    area: str = "personal"
    etiquetas: list[str] = Field(default_factory=list)
    origen: str = ""
    trabajo: str = ""
    creada: str = ""
    cerrada: str = ""
    avance: str = ""
    contexto: str = ""
    conexiones: list[str] = Field(default_factory=list)
    historia: list[Cambio] = Field(default_factory=list)
    #: claves repetidas en el archivo (vale la última): se avisan, no se corrigen solas
    duplicadas: list[str] = Field(default_factory=list)

    @property
    def cerrada_ya(self) -> bool:
        return self.estado in TERMINALES


#: campo del modelo → su clave en el archivo, en el orden en que se escriben
CLAVES = {
    "titulo": "titulo", "estado": "estado", "prioridad": "prioridad", "vence": "vence", "espera": "espera",
    "dueno": "dueño", "proyecto": "proyecto", "area": "area", "etiquetas": "etiquetas", "origen": "origen",
    "trabajo": "trabajo", "creada": "creada", "cerrada": "cerrada", "avance": "avance",
}

CLAVE_RE = re.compile(r"^([a-zñ_]+):[ \t]?(.*)$")
HIST_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))? \[([\w-]+)\] ?(.*)$")
SECCIONES = ("Conexiones", "Historia")


def _limpio(v: object) -> str:
    """Un valor de una línea: sin saltos ni espacios de sobra."""
    return " ".join(str(v if v is not None else "").split())


class _Lectura:
    """El texto partido en piezas con posición: dónde está cada clave y cada sección."""

    def __init__(self, texto: str, claves: dict[str, str]) -> None:
        self.lineas = texto.split("\n")
        self.claves = claves
        self.fm: tuple[int, int] | None = None          # (línea de apertura, línea de cierre)
        self.donde: dict[str, list[int]] = {}           # clave del archivo → líneas donde aparece
        self.valores: dict[str, str] = {}
        if self.lineas and self.lineas[0].strip() == "---":
            for i, l in enumerate(self.lineas[1:], 1):
                if l.strip() == "---":
                    self.fm = (0, i)
                    break
                m = CLAVE_RE.match(l)
                if m:
                    self.donde.setdefault(m.group(1), []).append(i)
                    self.valores[m.group(1)] = m.group(2).strip()
        self.cuerpo_desde = self.fm[1] + 1 if self.fm else 0
        # las secciones: (nombre, línea del título); el contexto va hasta la primera
        self.secciones: list[tuple[str, int]] = []
        for i in range(self.cuerpo_desde, len(self.lineas)):
            m = re.match(r"^## (Conexiones|Historia)\s*$", self.lineas[i])
            if m:
                self.secciones.append((m.group(1), i))

    def fin_de(self, k: int) -> int:
        """La línea (excluida) donde termina la sección número k."""
        return self.secciones[k + 1][1] if k + 1 < len(self.secciones) else len(self.lineas)

    def seccion(self, nombre: str) -> tuple[int, int] | None:
        """(primera línea del contenido, fin) de la ÚLTIMA sección con ese nombre; None si no está."""
        k = next((j for j in range(len(self.secciones) - 1, -1, -1) if self.secciones[j][0] == nombre), None)
        return None if k is None else (self.secciones[k][1] + 1, self.fin_de(k))


class FormatoArchivo:
    """Una tarea por archivo: líneas `clave: valor` entre `---`, el contexto y las secciones."""

    def __init__(self, claves: dict[str, str] | None = None) -> None:
        self.claves = dict(claves or CLAVES)

    # ── leer ──
    def leer(self, texto: str, id: str = "") -> Tarea:
        L = _Lectura(texto, self.claves)
        v = {campo: L.valores.get(clave, "") for campo, clave in self.claves.items()}
        duplicadas = [k for k, ls in L.donde.items() if len({L.lineas[i].split(":", 1)[1].strip() for i in ls}) > 1]
        pri = v["prioridad"] or "2"
        cuerpo = L.lineas[L.cuerpo_desde:]
        primera = L.secciones[0][1] - L.cuerpo_desde if L.secciones else len(cuerpo)
        conexiones: list[str] = []
        historia: list[Cambio] = []
        for k, (nombre, _) in enumerate(L.secciones):
            for l in L.lineas[L.secciones[k][1] + 1:L.fin_de(k)]:
                if not l.strip():
                    continue
                if nombre == "Conexiones":
                    conexiones.append(l.rstrip())
                else:
                    m = HIST_RE.match(l.strip())
                    historia.append(Cambio(fecha=m.group(1), hora=m.group(2) or "", tipo=m.group(3), texto=m.group(4))
                                    if m else Cambio(tipo="nota", texto=l.strip().lstrip("- ")))
        return Tarea(
            id=id, titulo=v["titulo"], estado=v["estado"] or "activa",
            prioridad=int(pri) if pri.isdigit() and int(pri) in (0, 1, 2, 3) else 2,
            vence=v["vence"], espera=v["espera"], dueno=v["dueno"], proyecto=v["proyecto"], area=v["area"] or "personal",
            etiquetas=[x.strip() for x in v["etiquetas"].split(",") if x.strip()], origen=v["origen"],
            trabajo=v["trabajo"], creada=v["creada"], cerrada=v["cerrada"], avance=v["avance"],
            contexto="\n".join(cuerpo[:primera]).strip(), conexiones=conexiones, historia=historia,
            duplicadas=duplicadas,
        )

    # ── escribir ──
    def _valor(self, t: Tarea, campo: str) -> str:
        if campo == "etiquetas":
            return ", ".join(t.etiquetas)
        if campo == "prioridad":
            return str(t.prioridad)
        if campo == "espera":
            # a quién se espera se guarda solo mientras la tarea espera
            return _limpio(t.espera).lstrip("@") if t.estado == "espera" else ""
        if campo == "cerrada":
            return _limpio(t.cerrada) if t.estado in TERMINALES else ""
        return _limpio(getattr(t, campo))

    #: lo que este formato no guarda: cambiarlo es un error, no una pérdida
    NO_GUARDA = ("en_curso",)

    def escribir(self, texto: str, antes: Tarea, despues: Tarea) -> str:
        """El texto con los cambios de `antes` a `despues`, tocando solo lo que cambió."""
        if despues == antes:
            return texto
        for campo in self.NO_GUARDA:
            if getattr(despues, campo) != getattr(antes, campo):
                raise ErrorDeFormato(f"una tarea en su archivo no guarda «{campo}»")
        L = _Lectura(texto, self.claves)
        lineas = list(L.lineas)
        orden = list(self.claves)

        # 1) las secciones del cuerpo, de abajo hacia arriba: así las posiciones de arriba no se mueven
        if despues.historia != antes.historia:
            lineas = self._historia(lineas, L, antes.historia, despues.historia)
        if despues.conexiones != antes.conexiones:
            lineas = self._seccion(lineas, _Lectura("\n".join(lineas), self.claves), "Conexiones", despues.conexiones)
        if despues.contexto != antes.contexto:
            lineas = self._contexto(lineas, _Lectura("\n".join(lineas), self.claves), despues.contexto)

        # 2) las claves de arriba
        cambiados = [c for c in orden if self._valor(despues, c) != self._valor(antes, c)]
        if cambiados:
            if L.fm is None:
                lineas = ["---", "---", *lineas]
            for campo in cambiados:
                L2 = _Lectura("\n".join(lineas), self.claves)
                clave, nuevo = self.claves[campo], self._valor(despues, campo)
                if "\n" in nuevo:
                    raise ErrorDeFormato(f"{campo}: un valor de una sola línea")
                donde = L2.donde.get(clave, [])
                if donde and nuevo:
                    # la última es la que vale; las repetidas de antes quedan como estaban
                    lineas[donde[-1]] = f"{clave}: {nuevo}"
                elif donde:
                    for i in reversed(donde):
                        del lineas[i]
                elif nuevo:
                    # en su lugar del orden: después de la última clave que va antes que ella
                    previas = [self.claves[c] for c in orden[:orden.index(campo)]]
                    tras = max((L2.donde[c][-1] for c in previas if c in L2.donde), default=L2.fm[0])
                    lineas.insert(tras + 1, f"{clave}: {nuevo}")
        return "\n".join(lineas)

    def nuevo(self, t: Tarea) -> str:
        """El archivo de una tarea que todavía no existe: las claves con valor, en su orden, el contexto y
        las secciones. Es la forma que tienen las que escribía la CLI de tareas."""
        for campo in self.NO_GUARDA:
            if getattr(t, campo) != getattr(Tarea(), campo):
                raise ErrorDeFormato(f"una tarea en su archivo no guarda «{campo}»")
        claves = []
        for campo, clave in self.claves.items():
            valor = self._valor(t, campo)
            if "\n" in valor:
                raise ErrorDeFormato(f"{campo}: un valor de una sola línea")
            if valor:
                claves.append(f"{clave}: {valor}")
        out = ["---", *claves, "---"]
        if t.contexto.strip():
            out += [t.contexto.strip(), ""]
        if t.conexiones:
            out += ["## Conexiones", *t.conexiones, ""]
        if t.historia:
            out += ["## Historia", *(self._linea_historia(c) for c in t.historia)]
        return "\n".join(out).rstrip() + "\n"

    def _historia(self, lineas: list[str], L: _Lectura, antes: list[Cambio], despues: list[Cambio]) -> list[str]:
        rango = L.seccion("Historia")
        if rango is not None and despues[:len(antes)] == antes:
            # lo común: se agregan líneas al final, después de la última que no está en blanco
            ini, fin = rango
            ultima = max((i for i in range(ini, fin) if lineas[i].strip()), default=ini - 1)
            return lineas[:ultima + 1] + [self._linea_historia(c) for c in despues[len(antes):]] + lineas[ultima + 1:]
        return self._seccion(lineas, L, "Historia", [self._linea_historia(c) for c in despues])

    @staticmethod
    def _linea_historia(c: Cambio) -> str:
        return f"- {c.fecha}{' ' + c.hora if c.hora else ''} [{c.tipo}] {_limpio(c.texto)}".rstrip()

    def _seccion(self, lineas: list[str], L: _Lectura, nombre: str, contenido: list[str]) -> list[str]:
        """Reescribe una sección entera (o la agrega al final, o la quita si queda vacía)."""
        rango = L.seccion(nombre)
        if rango is None:
            if not contenido:
                return lineas
            final = len(lineas) - (1 if lineas and lineas[-1] == "" else 0)
            # Conexiones va antes de Historia, si Historia ya está
            hist = L.seccion("Historia")
            if nombre == "Conexiones" and hist is not None:
                titulo = hist[0] - 1
                return lineas[:titulo] + [f"## {nombre}", *contenido, ""] + lineas[titulo:]
            separador = [""] if final and lineas[final - 1].strip() else []
            return lineas[:final] + separador + [f"## {nombre}", *contenido] + lineas[final:]
        ini, fin = rango
        # conserva las líneas en blanco del final de la sección (la separación con la siguiente)
        cola = fin
        while cola > ini and not lineas[cola - 1].strip():
            cola -= 1
        if not contenido:
            return lineas[:ini - 1] + lineas[fin:]
        return lineas[:ini] + list(contenido) + lineas[cola:]

    def _contexto(self, lineas: list[str], L: _Lectura, contexto: str) -> list[str]:
        ini = L.cuerpo_desde
        fin = L.secciones[0][1] if L.secciones else len(lineas)
        nuevo = contexto.strip().split("\n") if contexto.strip() else []
        cola = [""] if L.secciones else ([""] if fin == len(lineas) and lineas and lineas[-1] == "" else [])
        return lineas[:ini] + nuevo + (cola if nuevo or L.secciones else []) + lineas[fin:]


# ── la casilla de un documento ──────────────────────────────────────────────────

#: una casilla de lista: la sangría y la viñeta, la marca, y lo demás
_CASILLA = re.compile(r"^(?P<cabeza>\s*[-*+]\s+\[)(?P<marca>.)(?P<cierre>\]\s+)(?P<resto>.*)$")
#: marca → estado (y si está en curso); cualquier otra marca es «hecha»
_MARCAS = {" ": ("activa", False), ">": ("activa", True), "x": ("hecha", False), "X": ("hecha", False),
           "~": ("caduca", False), "-": ("descartada", False)}
_ESCRIBE_MARCA = {"activa": " ", "espera": " ", "algun-dia": " ", "hecha": "x", "caduca": "~", "descartada": "-"}
_ID = re.compile(r"<!--\s*id:\s*([^\s<>]+?)\s*-->", re.I)
#: las marcas `@clave(valor)`, como las escriben los documentos (telar.lectura)
_ARROBA = re.compile(r"\s*(?:->|→)?\s*@(owner|due[nñ]o|responsable|para|deadline|vence|prioridad|priority|hecha|espera)\(([^)]*)\)", re.I)
#: quién, al comienzo: «@Ana Pérez: revisar el NDA»
_QUIEN = re.compile(r"^@([A-ZÁÉÍÓÚÑ][\w.'-]*(?:\s+[A-ZÁÉÍÓÚÑ][\w.'-]*){0,3})\s*:\s+")
#: el otro dialecto, el del proveedor `markdown`: `vence:AAAA-MM-DD`, `espera:@quien`, `!alta`, `#etiqueta`
_VENCE = re.compile(r"(?<![\w-])vence:(\d{4}-\d{2}-\d{2})(?![\w-])")
_ESPERA = re.compile(r"(?<![\w-])espera:(@?[^\s·]+)")
_NIVEL = re.compile(r"(?<![\w-])!(alta|media|baja)(?![\w-])", re.I)
_ETIQUETA = re.compile(r"(?<![\w&#])#([A-Za-zÀ-ɏ][\wÀ-ɏ-]*)")
_PRIO_TXT = {"alta": 1, "media": 2, "baja": 3}
#: campo → la clave con que se escribe, en el dialecto `@clave(valor)`
_ESCRIBE = {"dueno": "owner", "vence": "deadline", "prioridad": "prioridad", "cerrada": "hecha", "espera": "espera"}
_CLAVE_DE = {"owner": "dueno", "dueño": "dueno", "dueno": "dueno", "responsable": "dueno", "para": "dueno",
             "deadline": "vence", "vence": "vence", "prioridad": "prioridad", "priority": "prioridad",
             "hecha": "cerrada", "espera": "espera"}


class FormatoCasilla:
    """Una tarea como casilla de un documento, en una línea:

        - [ ] Revisar el NDA @owner(Ana) @deadline(2026-10-30) @prioridad(P1) <!-- id: T84 -->

    Lee los dos dialectos que usan los documentos: `@clave(valor)` (`@owner`, `@deadline`,
    `@prioridad`, `@hecha`, `@espera`; y «@Nombre:» al comienzo) y el del proveedor `markdown`
    (`vence:`, `espera:`, `!alta`, `#etiqueta`). Escribe al mínimo: un campo que ya está se reescribe en
    su dialecto y en su lugar; uno nuevo se agrega como `@clave(valor)`, antes del identificador.

    Una casilla no guarda un cuerpo largo, ni conexiones, ni de dónde salió: cambiar eso es un error.
    Tampoco guarda la historia, y eso está declarado: la historia de un documento es su git.
    """

    NO_GUARDA = ("contexto", "conexiones", "origen", "trabajo", "proyecto", "area", "creada", "avance")
    IGNORA = ("historia",)

    def leer(self, linea: str, id: str = "") -> Tarea:
        m = _CASILLA.match(linea)
        if not m:
            raise ErrorDeFormato("no es una casilla")
        estado, en_curso = _MARCAS.get(m.group("marca"), ("hecha", False))
        resto = m.group("resto")
        campos: dict[str, str] = {}
        if (i := _ID.search(resto)):
            id = id or i.group(1)
            resto = resto[:i.start()] + resto[i.end():]
        for clave, valor in _ARROBA.findall(resto):
            campo, valor = _CLAVE_DE[clave.lower()], valor.strip()
            # una fecha que no es fecha (una plantilla: «@vence(YYYY-MM-DD)») no es una fecha
            if campo in ("vence", "cerrada") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
                continue
            campos.setdefault(campo, valor)
        resto = _ARROBA.sub("", resto)
        if (q := _QUIEN.match(resto.strip())):
            campos.setdefault("dueno", q.group(1))
            resto = resto.strip()[q.end():]
        if (v := _VENCE.search(resto)):
            campos.setdefault("vence", v.group(1))
            resto = resto[:v.start()] + resto[v.end():]
        if (e := _ESPERA.search(resto)):
            campos.setdefault("espera", e.group(1).lstrip("@"))
            resto = resto[:e.start()] + resto[e.end():]
        prioridad = 2
        if (n := _NIVEL.search(resto)):
            prioridad = _PRIO_TXT[n.group(1).lower()]
            resto = resto[:n.start()] + resto[n.end():]
        if "prioridad" in campos and (p := re.fullmatch(r"[Pp]?([0-3])", campos["prioridad"])):
            prioridad = int(p.group(1))
        etiquetas = [x.lower() for x in _ETIQUETA.findall(resto)]
        resto = _ETIQUETA.sub(" ", resto)
        if campos.get("espera") and estado == "activa":
            estado = "espera"
        return Tarea(id=id, titulo=_limpio(resto).strip(" ·-—|").strip(), estado=estado, en_curso=en_curso,
                     prioridad=prioridad, vence=campos.get("vence", ""), espera=campos.get("espera", ""),
                     dueno=campos.get("dueno", ""), cerrada=campos.get("cerrada", ""), etiquetas=etiquetas)

    def escribir(self, linea: str, antes: Tarea, despues: Tarea) -> str:
        for campo in self.NO_GUARDA:
            if getattr(despues, campo) != getattr(antes, campo):
                raise ErrorDeFormato(f"una casilla no guarda «{campo}»: va en el archivo de la tarea")
        if despues.titulo != antes.titulo:
            raise ErrorDeFormato("el texto de una casilla se cambia en su documento")
        m = _CASILLA.match(linea)
        if not m:
            raise ErrorDeFormato("no es una casilla")
        if (despues.estado, despues.en_curso) != (antes.estado, antes.en_curso):
            marca = ">" if despues.en_curso and despues.estado in ("activa", "espera") else _ESCRIBE_MARCA.get(despues.estado, " ")
            if m.group("marca") != marca:
                linea = linea[:m.start("marca")] + marca + linea[m.end("marca"):]
        for campo in ("dueno", "vence", "prioridad", "cerrada", "espera"):
            nuevo, viejo = self._valor(despues, campo), self._valor(antes, campo)
            if nuevo != viejo:
                linea = self._poner(linea, campo, nuevo)
        if despues.etiquetas != antes.etiquetas:
            for e in antes.etiquetas:
                if e not in despues.etiquetas:
                    linea = re.sub(rf"\s*(?<![\w&#])#{re.escape(e)}(?![\wÀ-ɏ-])", "", linea, count=1, flags=re.I)
            for e in despues.etiquetas:
                if e not in antes.etiquetas:
                    linea = self._insertar(linea, f"#{e}")
        return linea

    @staticmethod
    def _valor(t: Tarea, campo: str) -> str:
        if campo == "prioridad":
            return "" if t.prioridad == 2 else f"P{t.prioridad}"
        if campo == "espera":
            # a quién se espera vale solo mientras la tarea espera (como en el archivo propio)
            return _limpio(t.espera).lstrip("@") if t.estado == "espera" else ""
        return _limpio(getattr(t, campo))

    def _poner(self, linea: str, campo: str, valor: str) -> str:
        """El campo con su valor nuevo, en el dialecto y el lugar donde ya estaba; si no estaba, al final."""
        for x in _ARROBA.finditer(linea):
            if _CLAVE_DE[x.group(1).lower()] == campo:
                if not valor:
                    return linea[:x.start()] + linea[x.end():]
                ini, fin = x.span(2)
                return linea[:ini] + valor + linea[fin:]
        otros = {"vence": _VENCE, "espera": _ESPERA}
        if campo in otros and (x := otros[campo].search(linea)):
            if not valor:
                return (linea[:x.start()] + linea[x.end():]).replace("  ", " ")
            return linea[:x.start(1)] + (valor if campo == "vence" else "@" + valor.lstrip("@")) + linea[x.end(1):]
        if campo == "prioridad" and (x := _NIVEL.search(linea)):
            # el dialecto `!alta` no tiene P0: se pasa a `@prioridad(…)`
            txt = {1: "alta", 2: "media", 3: "baja"}.get(int(valor[1:]) if valor else 2, "")
            if txt and valor:
                return linea[:x.start(1)] + txt + linea[x.end(1):]
            linea = (linea[:x.start()] + linea[x.end():]).replace("  ", " ")
            return self._insertar(linea, f"@prioridad({valor})") if valor else linea
        if campo == "dueno":
            m = _CASILLA.match(linea)
            if m and (q := _QUIEN.match(m.group("resto"))):
                ini = m.start("resto")
                if not valor:
                    return linea[:ini] + linea[ini + q.end():]
                return linea[:ini + q.start(1)] + valor + linea[ini + q.end(1):]
        return self._insertar(linea, f"@{_ESCRIBE[campo]}({valor})") if valor else linea

    @staticmethod
    def _insertar(linea: str, ficha: str) -> str:
        """Una ficha nueva antes del identificador (`<!-- id: … -->`), o al final."""
        if (i := _ID.search(linea)):
            antes = linea[:i.start()].rstrip()
            return f"{antes} {ficha} {linea[i.start():]}"
        cuerpo = linea.rstrip()
        return f"{cuerpo} {ficha}" + linea[len(cuerpo):]


ARCHIVO = FormatoArchivo()
CASILLA = FormatoCasilla()


# ── las acciones ───────────────────────────────────────────────────────────────
#
# Funciones sobre el modelo, sin texto: reciben una tarea y devuelven otra (la de entrada no cambia).
# Cada una deja su línea en la historia. Son las mismas transiciones que la CLI de tareas, con dos
# diferencias a propósito: cerrar lo cerrado o reabrir lo abierto es un error (un doble clic dejaría la
# historia repetida), y asignar o editar también dejan su línea.

import datetime as _dt

AVANCES = ("preparado", "cerrar", "pregunta", "choca")
_ETIQUETA_CIERRE = {"hecha": "hecha", "caduca": "caducó", "descartada": "descartada"}


class ErrorDeAccion(ValueError):
    """La acción no se puede hacer sobre la tarea como está (la precondición no se cumple)."""


def _ahora(reloj=None) -> _dt.datetime:
    return reloj() if reloj else _dt.datetime.now()


def _con(t: Tarea, tipo: str, texto: str, nota: str = "", *, hora: bool = True, reloj=None, **cambios) -> Tarea:
    """La tarea con esos cambios y una línea más en la historia."""
    ahora = _ahora(reloj)
    linea = Cambio(fecha=ahora.date().isoformat(), hora=ahora.strftime("%H:%M") if hora else "", tipo=tipo,
                   texto=_limpio(texto + (f": {nota}" if nota else "")))
    return t.model_copy(update={**cambios, "historia": [*t.historia, linea]})


def cerrar(t: Tarea, como: str = "hecha", nota: str = "", *, reloj=None) -> Tarea:
    """Cerrarla: `hecha`, `caduca` o `descartada`. La propuesta pendiente y la espera se van."""
    if como not in TERMINALES:
        raise ErrorDeAccion(f"cerrar es {', '.join(TERMINALES)}")
    if t.estado in TERMINALES:
        raise ErrorDeAccion(f"{t.id} ya está cerrada ({t.estado})")
    return _con(t, "cierre", _ETIQUETA_CIERRE[como], nota, reloj=reloj, estado=como, en_curso=False,
                cerrada=_ahora(reloj).date().isoformat(), espera="", avance="")


def completar(t: Tarea, nota: str = "", *, reloj=None) -> Tarea:
    return cerrar(t, "hecha", nota, reloj=reloj)


def reabrir(t: Tarea, nota: str = "", *, reloj=None) -> Tarea:
    """Volver a abrirla: vuelve a estar activa, sin fecha de cierre."""
    if t.estado not in TERMINALES and t.estado != "algun-dia":
        raise ErrorDeAccion(f"{t.id} no está cerrada")
    return _con(t, "mover", "reabierta", nota, reloj=reloj, estado="activa", cerrada="", avance="")


def algun_dia(t: Tarea, nota: str = "", *, reloj=None) -> Tarea:
    if t.estado in TERMINALES:
        raise ErrorDeAccion(f"{t.id} está cerrada: reábrela primero")
    # a quién se esperaba deja de valer: ya no espera a nadie (el archivo solo lo guarda mientras espera)
    return _con(t, "mover", "a algún día", nota, reloj=reloj, estado="algun-dia", espera="", avance="")


def esperar(t: Tarea, quien: str, nota: str = "", *, reloj=None) -> Tarea:
    """Que le toque a otra persona (`quien`); con `quien` vacío, vuelve a ser de la dueña."""
    if t.estado in TERMINALES:
        raise ErrorDeAccion(f"{t.id} está cerrada")
    quien = _limpio(quien).lstrip("@")
    if not quien:
        return _con(t, "espera", "vuelve a ser tuya", nota, reloj=reloj, estado="activa", espera="", avance="")
    return _con(t, "espera", f"espera a {quien}", nota, reloj=reloj, estado="espera", espera=quien, avance="")


def reagendar(t: Tarea, fecha: str, nota: str = "", *, reloj=None) -> Tarea:
    """Otra fecha: `AAAA-MM-DD`, o `+Nd` (N días desde la fecha que tenía si no pasó, o desde hoy); vacía
    (o `none`), ninguna."""
    if t.estado in TERMINALES:
        raise ErrorDeAccion(f"{t.id} está cerrada")
    hoy = _ahora(reloj).date()
    if fecha.strip().lower() in ("", "none"):
        # sin fecha: deja de vencer
        if not t.vence:
            return t
        return _con(t, "mover", f"{t.vence} → sin fecha", nota, reloj=reloj, vence="", avance="")
    if (m := re.fullmatch(r"\+(\d+)d", fecha.strip())):
        base = _dt.date.fromisoformat(t.vence) if t.vence and t.vence >= hoy.isoformat() else hoy
        nueva = (base + _dt.timedelta(days=int(m.group(1)))).isoformat()
    else:
        try:
            nueva = _dt.date.fromisoformat(fecha.strip()).isoformat()
        except ValueError as e:
            raise ErrorDeAccion(f"fecha inválida: {fecha} (AAAA-MM-DD o +Nd)") from e
    texto = f"{t.vence} → {nueva}" if t.vence else f"fecha {nueva}"
    return _con(t, "mover", texto, nota, reloj=reloj, vence=nueva, avance="",
                estado="activa" if t.estado == "algun-dia" else t.estado)


def asignar(t: Tarea, persona: str, *, reloj=None) -> Tarea:
    """Quién la hace; vacío, nadie en particular (es de la dueña del repositorio)."""
    persona = _limpio(persona)
    if persona == t.dueno:
        return t
    return _con(t, "edita", f"dueño {persona}" if persona else "sin dueño", reloj=reloj, dueno=persona)


def anotar(t: Tarea, texto: str, *, reloj=None) -> Tarea:
    if not _limpio(texto):
        raise ErrorDeAccion("la nota está vacía")
    return _con(t, "nota", texto, reloj=reloj)


def proponer(t: Tarea, estado: str, texto: str, como: str = "", *, reloj=None) -> Tarea:
    """Lo que un agente dejó preparado para decidir (`avance`): preparado, cerrar (con `como`),
    pregunta o choca."""
    if estado not in AVANCES:
        raise ErrorDeAccion(f"avance: {' | '.join(AVANCES)}")
    if estado == "cerrar" and como not in TERMINALES:
        raise ErrorDeAccion("cerrar pide cómo: hecha, caduca o descartada")
    marca = f"cerrar:{como}" if estado == "cerrar" else estado
    return _con(t, "avance", f"{marca}: {texto}", reloj=reloj, avance=f"{marca} {_ahora(reloj).date().isoformat()}")


def responder(t: Tarea, texto: str, *, reloj=None) -> Tarea:
    """La respuesta de la persona a una propuesta: queda en la historia y la propuesta deja de estar pendiente."""
    return _con(t, "respuesta", texto, reloj=reloj, avance="")


def editar(t: Tarea, *, reloj=None, **campos) -> Tarea:
    """Cambiar campos sueltos (título, prioridad, área, proyecto, etiquetas…), con su línea en la historia."""
    permitidos = {"titulo", "prioridad", "area", "proyecto", "origen", "trabajo", "etiquetas", "contexto"}
    raros = set(campos) - permitidos
    if raros:
        raise ErrorDeAccion(f"editar no cambia {', '.join(sorted(raros))}: para eso hay una acción")
    if isinstance(campos.get("prioridad"), str):
        # escrita: «P1» o «1» (lo que manda la ficha)
        m = re.fullmatch(r"\s*[Pp]?([0-3])\s*", campos["prioridad"])
        if not m:
            raise ErrorDeAccion(f"prioridad «{campos['prioridad']}»: va de P0 (la más alta) a P3")
        campos["prioridad"] = int(m.group(1))
    cambios = {k: v for k, v in campos.items() if getattr(t, k) != v}
    if not cambios:
        return t
    return _con(t, "edita", ", ".join(sorted(cambios)), reloj=reloj, **cambios)


def secuela(t: Tarea, texto: str, *, reloj=None) -> Tarea:
    """Lo que se hizo con lo que el cierre dejó por hacer (avisar, archivar, la tarea que sigue)."""
    if not _limpio(texto):
        raise ErrorDeAccion("la secuela está vacía")
    return _con(t, "secuela", texto, reloj=reloj)


def conectar(t: Tarea, tipo: str, destino: str, porque: str, *, reloj=None) -> Tarea:
    """Una arista del grafo en `## Conexiones`: «- `tipo` destino · por qué». `destino` es el enlace ya
    escrito (`[T228](T228.md)`). La conexión es su propio registro: no deja línea en la historia."""
    if not re.fullmatch(r"[\w-]+", tipo or ""):
        raise ErrorDeAccion("el tipo de una conexión es una palabra")
    if not _limpio(destino) or not _limpio(porque):
        raise ErrorDeAccion("una conexión lleva destino y por qué")
    linea = f"- `{tipo}` {_limpio(destino)} · {_limpio(porque)}"
    return t.model_copy(update={"conexiones": [*t.conexiones, linea]})


#: con qué letra empiezan los identificadores que se les dan a las tareas nuevas (T1, T2… T344)
PREFIJO = "T"


def nueva(titulo: str, *, contexto: str = "", estado: str = "activa", prioridad: int = 2, vence: str = "",
          dueno: str = "", proyecto: str = "", area: str = "personal", etiquetas: list[str] | tuple = (),
          origen: str = "", trabajo: str = "", desde: str = "", reloj=None) -> Tarea:
    """Una tarea que todavía no existe, sin identificador: se lo da quien la escribe (Carpeta.crear).
    `desde` dice de dónde salió (email, minuta…), y queda en la historia; sin él, «a mano»."""
    titulo = _limpio(titulo)
    if not titulo:
        raise ErrorDeAccion("una tarea lleva título")
    if estado not in ("activa", "algun-dia"):
        raise ErrorDeAccion("una tarea nueva está activa o es de algún día")
    if prioridad not in (0, 1, 2, 3):
        raise ErrorDeAccion("la prioridad va de 0 a 3")
    if vence:
        try:
            vence = _dt.date.fromisoformat(vence.strip()).isoformat()
        except ValueError as e:
            raise ErrorDeAccion(f"fecha inválida: {vence} (AAAA-MM-DD)") from e
    hoy = _ahora(reloj).date().isoformat()
    origen_txt = f"desde {_limpio(desde)}" if _limpio(desde) and _limpio(desde) != "manual" else "a mano"
    return Tarea(titulo=titulo, contexto=contexto.strip(), estado=estado, prioridad=prioridad, vence=vence,
                 dueno=_limpio(dueno), proyecto=_limpio(proyecto), area=_limpio(area) or "personal",
                 etiquetas=[_limpio(e) for e in etiquetas if _limpio(e)], origen=_limpio(origen),
                 trabajo=_limpio(trabajo), creada=hoy, historia=[Cambio(fecha=hoy, tipo="creada", texto=origen_txt)])


ACCIONES = {"completar": completar, "cerrar": cerrar, "reabrir": reabrir, "algun_dia": algun_dia,
            "esperar": esperar, "reagendar": reagendar, "asignar": asignar, "anotar": anotar,
            "proponer": proponer, "responder": responder, "editar": editar, "secuela": secuela,
            "conectar": conectar}
