"""Lo que pesa el contexto de una conversación, y de qué está hecho.

Un agente carga cosas que nadie le pidió (los CLAUDE.md de cada nivel, el índice de la memoria, lo que agregan los
hooks, la lista de skills, las instrucciones de los MCP) y otras que buscó para su trabajo (los archivos que leyó, las
búsquedas, las skills que usó). Esto junta las dos, cada cosa con su tamaño, para ver de un vistazo cuánto pesa lo
general contra lo propio del hilo y decidir qué recortar en lo general.

    Carga             el acumulador: cada adaptador de agente le pasa lo que encuentra en su conversación
                      (`agregar`, `uso`, `compactar`) y al final `resumen()` da el JSON (docs/contratos.md,
                      «telar hilo contexto»)

Los grupos, en el orden en que se muestran (`GRUPOS`):

    claude         lo de Claude Code: sus instrucciones de sistema y sus herramientas (lo que pesa la primera
                   petición y no es nada de lo de abajo) y los avisos que agrega a cada rato
    inicio         lo que carga solo al empezar: los CLAUDE.md, la memoria, los hooks de inicio, la lista de
                   skills, las instrucciones de los MCP, el estado de git
    carpetas       lo que carga al entrar a una carpeta: el CLAUDE.md de una subcarpeta, sus skills
    leido          lo que leyó: archivos, búsquedas, comandos que leen archivos, skills que cargó
    repetido       lo que un hook agrega en cada mensaje (o en cada herramienta): veces × tamaño
    hilos          lo que le llegó de otros hilos y otras sesiones
    conversacion   lo demás: lo que se dijo y lo que corrió (el total medido menos todo lo de arriba)

Lo que una compactación resumió ya no está en el contexto: queda aparte (`antes`), para comparar.

El total sale del uso que el modelo informa en cada pedido (exacto); el tamaño de cada cosa, de sus caracteres
(estimado, `CARACTERES_POR_TOKEN`). Sin uso informado, el total también es una estimación, y `medido` lo dice. Nunca
se guarda el contenido de nada: solo rutas, nombres y tamaños.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: cuántos caracteres hacen un token, para estimar lo que no viene medido. Medido en conversaciones de Claude Code en
#: español (instrucciones, markdown, JSON y código): la primera petición de cada una contra sus caracteres
CARACTERES_POR_TOKEN = 2.6

#: (clave, nombre, para qué), en el orden en que se muestran
GRUPOS: tuple[tuple[str, str, str], ...] = (
    ("claude", "Claude Code", "sus instrucciones de sistema, sus herramientas y sus avisos"),
    ("inicio", "al empezar", "lo que todo hilo carga sin pedirlo: CLAUDE.md, memoria, hooks, skills, MCP"),
    ("carpetas", "al entrar a carpetas", "el CLAUDE.md y las skills de una subcarpeta, al leer algo ahí"),
    ("leido", "lo que leyó", "archivos, búsquedas, comandos que leen y skills que cargó"),
    ("repetido", "lo que se repite", "lo que un hook agrega en cada mensaje o en cada herramienta"),
    ("hilos", "de otros hilos", "mensajes de otros hilos y de otras sesiones"),
    ("conversacion", "la conversación", "lo demás: lo que se dijo y lo que corrió"),
)
CLAVES = tuple(g[0] for g in GRUPOS)

#: cuántas cosas de cada grupo se entregan, a lo más (las que más pesan)
MAX_POR_GRUPO = 200


def tokens(caracteres: int) -> int:
    return round(caracteres / CARACTERES_POR_TOKEN)


@dataclass
class Item:
    """Una cosa que entró al contexto, con todas las veces que entró."""

    grupo: str
    clase: str
    nombre: str
    ruta: str = ""
    #: en el contexto de ahora (desde la última compactación o el último /clear)
    veces: int = 0
    caracteres: int = 0
    #: lo que no se mide en caracteres (una imagen): sus tokens
    fijos: int = 0
    primera: str = ""
    ultima: str = ""
    #: lo que una compactación ya resumió
    antes_veces: int = 0
    antes_caracteres: int = 0
    antes_fijos: int = 0
    vias: list[str] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return tokens(self.caracteres) + self.fijos

    def como_json(self) -> dict:
        d = {"grupo": self.grupo, "clase": self.clase, "nombre": self.nombre, "veces": self.veces,
             "tokens": self.tokens, "caracteres": self.caracteres, "primera": self.primera, "ultima": self.ultima}
        if self.ruta:
            d["ruta"] = self.ruta
        if self.antes_veces:
            d["antes"] = {"veces": self.antes_veces, "tokens": tokens(self.antes_caracteres) + self.antes_fijos}
        if self.vias:
            d["vias"] = list(self.vias)
        return d


class Carga:
    """El acumulador. Un adaptador lo llena registro por registro, en orden, y puede seguir llenándolo cuando la
    conversación crece (lo que ya leyó no se relee: `telar.conversacion.carga`)."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str, str], Item] = {}
        #: desde cuándo es el contexto de ahora: {"que": inicio|clear|retomada|compactacion, "hora", …}
        self.desde: dict = {"que": "inicio", "hora": ""}
        self.compactaciones = 0
        #: el uso del último pedido (tokens que entraron) y su hora; el del primero de este tramo
        self.total: int | None = None
        self.hora_total = ""
        self.modelo = ""
        self.al_empezar: int | None = None
        #: los tokens de la primera petición del tramo que no son nada de lo anotado: Claude Code
        self.fijo_claude = 0

    # ── lo que llena el adaptador ──

    def agregar(self, grupo: str, clase: str, nombre: str, caracteres: int, hora: str = "", *, ruta: str = "",
                fijos: int = 0, via: str = "", clave: str = "") -> None:
        """Una vez que algo entró al contexto. `clave` distingue dos cosas con el mismo nombre (si no, la ruta o el
        nombre); `fijos`, lo que pesa en tokens sin ser texto (una imagen); `via`, por dónde llegó (Read, Bash, al
        compactar)."""
        if grupo not in CLAVES:
            grupo = "conversacion"
        k = (grupo, clase, clave or ruta or nombre)
        it = self.items.get(k)
        if it is None:
            it = self.items[k] = Item(grupo=grupo, clase=clase, nombre=nombre, ruta=ruta)
        it.veces += 1
        it.caracteres += max(0, int(caracteres))
        it.fijos += max(0, int(fijos))
        if hora:
            it.primera = it.primera or hora
            it.ultima = hora
        if via and via not in it.vias:
            it.vias.append(via)

    def renombrar(self, grupo: str, clase: str, clave: str, nombre: str) -> None:
        """Otro nombre para algo ya anotado (el que se supo después es mejor: el de un MCP en sus instrucciones)."""
        it = self.items.get((grupo, clase, clave))
        if it is not None:
            it.nombre = nombre

    def dijo(self, caracteres: int, que: str, hora: str = "") -> None:
        """Lo que se dijo o corrió (va a «la conversación»), por lo que es: `que` es su nombre («lo que escribió la
        persona», «lo que devolvió Bash»)."""
        self.agregar("conversacion", "dijo", que, caracteres, hora, clave=f"dijo:{que}")

    def uso(self, tokens_entrada: int, hora: str = "", modelo: str = "") -> None:
        """Lo que pesó un pedido al modelo (los tokens de entrada, con lo que venía del caché). El primero de cada
        tramo fija lo de Claude Code: lo que pesó y no es nada de lo anotado hasta ahí."""
        if tokens_entrada <= 0:
            return
        if self.al_empezar is None:
            self.al_empezar = tokens_entrada
            anotado = sum(it.tokens for it in self.items.values() if it.veces)
            self.fijo_claude = max(0, tokens_entrada - anotado)
        self.total, self.hora_total = tokens_entrada, hora or self.hora_total
        self.modelo = modelo or self.modelo

    def empezo(self, que: str, hora: str = "") -> None:
        """Cómo empezó esta conversación (`inicio`, `clear`, `retomada`): lo dice el adaptador si lo sabe."""
        if self.desde.get("que") != "compactacion":
            self.desde = {"que": que, "hora": hora or self.desde.get("hora", "")}

    def hora(self, hora: str) -> None:
        """La hora del primer registro: desde cuándo, si no se sabe otra cosa."""
        if hora and not self.desde.get("hora"):
            self.desde["hora"] = hora

    def compactar(self, hora: str = "", *, como: str = "", antes: int = 0, despues: int = 0) -> None:
        """Una compactación: todo lo de hasta aquí queda resumido, y lo que siga es el contexto de ahora."""
        for it in self.items.values():
            it.antes_veces += it.veces
            it.antes_caracteres += it.caracteres
            it.antes_fijos += it.fijos
            it.veces = it.caracteres = it.fijos = 0
        self.compactaciones += 1
        self.desde = {"que": "compactacion", "hora": hora}
        if como:
            self.desde["como"] = como
        if antes:
            self.desde["antes"] = antes
        if despues:
            self.desde["despues"] = despues
        self.al_empezar = None
        self.total = None
        self.fijo_claude = 0

    # ── lo que se entrega ──

    def resumen(self) -> dict:
        """El JSON de `telar hilo contexto` (sin el hilo ni la máquina, que pone quien llama)."""
        por_grupo: dict[str, list[Item]] = {g: [] for g in CLAVES}
        for it in self.items.values():
            por_grupo[it.grupo].append(it)
        suma = {g: sum(it.tokens for it in xs if it.veces) for g, xs in por_grupo.items()}
        cuantos = {g: sum(1 for it in xs if it.veces) for g, xs in por_grupo.items()}
        # lo que no está en el archivo como texto, deducido: lo de Claude Code al empezar (lo que pesó la primera
        # petición menos lo anotado hasta ahí) y, de lo medido ahora, lo que no es nada de lo anotado
        extra: dict[str, dict] = {}
        if self.fijo_claude:
            extra["claude"] = {"grupo": "claude", "clase": "sistema", "nombre": "sus instrucciones de sistema y sus herramientas",
                               "veces": 1, "tokens": self.fijo_claude, "deducido": True}
        medido = self.total is not None
        if medido:
            resto = self.total - sum(suma.values()) - self.fijo_claude
            if resto > 0:
                extra["conversacion"] = {"grupo": "conversacion", "clase": "resto", "veces": 1, "tokens": resto, "deducido": True,
                                         "nombre": "el razonamiento y lo que no se alcanza a estimar"}
        for g, x in extra.items():
            suma[g] += x["tokens"]
            cuantos[g] += 1
        total = self.total if medido else sum(suma.values())
        grupos = [{"clave": clave, "nombre": nombre, "para": para, "cuantos": cuantos[clave], "tokens": suma[clave]}
                  for clave, nombre, para in GRUPOS]
        items: list[dict] = []
        truncado = False
        for clave in CLAVES:
            xs = [x.como_json() for x in sorted(por_grupo[clave], key=lambda it: (-it.tokens, -(it.antes_caracteres + it.antes_fijos), it.nombre))]
            if clave in extra:
                xs.append(extra[clave])
                xs.sort(key=lambda x: -x["tokens"])
            truncado |= len(xs) > MAX_POR_GRUPO
            items.extend(xs[:MAX_POR_GRUPO])
        return {"desde": dict(self.desde), "compactaciones": self.compactaciones, "total": total, "medido": medido,
                "hora": self.hora_total, "modelo": self.modelo, "al_empezar": self.al_empezar,
                "caracteres_por_token": CARACTERES_POR_TOKEN, "grupos": grupos, "items": items, "truncado": truncado}
