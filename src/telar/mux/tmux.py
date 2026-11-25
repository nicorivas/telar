"""tmux: la implementación de referencia de `telar.mux.base.MultiplexorBase`.

Todo lo que este módulo hace es correr `tmux` como cualquiera lo correría a mano y
leer lo que contesta. Tres decisiones explican casi todo el archivo:

**Se pregunta con formatos, no se leen tablas.** `list-windows`, `list-panes` y
`display-message` aceptan un `-F` con los campos que uno quiera y los devuelven en el
orden pedido. Parsear la salida bonita de tmux —columnas alineadas, `1: nombre* (2
panes)`— es frágil: cambia entre versiones, se rompe con un nombre largo y miente con
un nombre que traiga espacios. Acá cada consulta pide sus campos separados por un
byte que ningún nombre de ventana trae (`\\x1f`, el separador de unidades de ASCII),
y si vuelve un número de campos distinto del pedido, eso es un error, no un renglón
que se adivina.

**La llave de un tab es su `window_id` (`@3`), no su índice.** Los índices se
renumeran solos —basta cerrar el tab 2 para que el 3 pase a ser 2— y un identificador
que cambia solo es un identificador que en algún momento apunta al tab equivocado.
`@3` vive lo que vive la ventana. Para no pelear con nadie, `ir`, `cerrar` y compañía
también aceptan un índice (`"3"`) o un nombre exacto, y cada forma se traduce al
objetivo que tmux espera.

**Al cambiar de tab se le apunta a un cliente concreto.** `select-window` mueve la
ventana actual de la *sesión*, que es lo correcto cuando nadie está mirando; pero si
quien corre el comando está adentro de otra sesión, lo que hay que mover es su
terminal, y para eso está `switch-client -c <tty>`. Se hacen las dos cosas: la sesión
queda apuntando al tab y el cliente que preguntó, también.

Lo que tmux no tiene: paneles flotantes. Sus popups (`display-popup`) no son paneles,
no salen en `list-panes` y no se les puede hablar, así que `Pane.flotante` es siempre
falso acá. Y el título por defecto de un panel es el nombre de la máquina: sirve para
encontrar los paneles que telar mismo tituló, no para reconocer lo que corre adentro
—para eso está `Pane.comando`, que sale de `#{pane_current_command}`.
"""

from __future__ import annotations

import itertools
import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from telar import entorno as mod_entorno
from telar.config import Config
from telar.mux.base import (
    Direccion,
    ErrorDeMux,
    MultiplexorBase,
    NoExiste,
    Pane,
    SinPrograma,
    SinSesion,
    Tab,
    comprobar_direccion,
)

__all__ = ["Tmux", "construir"]

#: un nombre de buffer distinto para cada texto que se pega: dos pegados a la vez no se pisan
_BUFFERS = itertools.count(1)

PROGRAMA = "tmux"

#: Ninguna consulta a tmux debería demorar esto; si demora, es que el servidor se colgó
#: y más vale un error que una barra de estado congelada.
TIEMPO_LIMITE = 5.0

#: Lo más largo que tmux acepta en una orden, en bytes. El cliente le pasa la orden al servidor en mensajes de 16 KB, y
#: una más larga (un texto que se teclea, un primer mensaje con un contexto largo en la línea del comando) sale con
#: «command too long». Lo que pasa de esto va por otro lado: un texto, por la entrada de `load-buffer`; un comando, en
#: un guion (`_corta`). Con margen para el resto de la orden.
LARGO_ORDEN = 12_000

#: Separador de campos: el byte 0x1f de ASCII, que no aparece en un nombre de ventana
#: ni en una ruta. Con un tabulador o un espacio, un nombre con espacios rompe el parseo.
SEP = "\x1f"

#: Cómo escribe ese byte un tmux viejo. Hasta 3.4, tmux pasa lo que imprime por `vis()`
#: antes de devolverlo, y los caracteres de control salen en octal: el 0x1f se vuelve los
#: cuatro caracteres `\\037`. Un tmux nuevo devuelve el byte crudo. Los dos se leen igual
#: si, cuando no vino el byte, se deshace el disfraz.
SEP_EN_OCTAL = "\\037"

CAMPOS_TAB = (
    "#{window_id}",
    "#{window_index}",
    "#{window_name}",
    "#{window_active}",
    "#{window_panes}",
    # la marca de hilo remoto: una opción de ventana propia de telar, vacía si no está
    "#{@telar_remoto}",
)

#: la opción de ventana donde telar anota que un hilo vive en otra máquina.
OPCION_REMOTO = "@telar_remoto"
FORMATO_TAB = SEP.join(CAMPOS_TAB)

CAMPOS_PANE = (
    "#{pane_id}",
    "#{window_id}",
    "#{pane_title}",
    "#{pane_current_command}",
    "#{pane_current_path}",
    "#{pane_active}",
    "#{pane_dead}",
    "#{pane_pid}",
)
FORMATO_PANE = SEP.join(CAMPOS_PANE)

#: dirección → banderas de `split-window` / `move-pane`. `-h` parte a lo ancho, `-v` a
#: lo alto, y `-b` pone el panel nuevo antes del que se partió en vez de después.
BANDERAS = {
    "derecha": ("-h",),
    "izquierda": ("-h", "-b"),
    "abajo": ("-v",),
    "arriba": ("-v", "-b"),
}


def entorno_limpio() -> dict[str, str]:
    """El entorno de este proceso sin lo que un panel no hereda: las variables de otro multiplexor y las marcas de la
    sesión de Claude Code que pidió abrirlo (`telar.entorno`)."""
    return mod_entorno.sin_marcas(os.environ)


#: las órdenes de tmux que arrancan un proceso. El panel nuevo recibe el entorno global del servidor de tmux (el de quien
#: lo levantó, que por eso se limpia al tejer: `Tmux.limpiar_entorno`), salvo el PATH, que tmux toma de quien corre la
#: orden: esas van con el de la persona (`entorno_para_abrir`). Y la que levanta el servidor le da su entorno entero.
ABREN = ("new-session", "new-window", "split-window")

#: Los ganchos con que tmux le cuenta a telar que la persona cambió de tab (`Tmux.ganchos`): la ventana de la sesión
#: cambió, o un cliente llegó a ella. Son de la sesión del telar, no globales: las vistas (`ver-…`, agrupadas con ella)
#: y las sesiones de prueba no los tienen.
GANCHOS_FOCO = ("session-window-changed", "client-session-changed", "client-attached")

#: Una ruta que se puede poner entre comillas simples en la orden de un gancho sin citarla de nuevo.
RUTA_CITABLE = re.compile(r"[A-Za-z0-9_./~+-]+")


def ejecutable_telar() -> str:
    """La ruta del `telar` que corre esto (el de su mismo entorno), o el del PATH; "" si no hay."""
    import sys

    junto = Path(sys.executable).with_name("telar")
    if junto.is_file() and os.access(junto, os.X_OK):
        return str(junto)
    return shutil.which("telar") or ""

_path_de_la_persona: str | None = None


def path_de_la_persona() -> str:
    """El PATH que tiene la persona en su terminal: el de una shell de login interactiva, leído una vez.

    Quien abre un hilo puede ser un servicio (`telar serve`, el nodo) o un `ssh host 'orden'`, con un PATH
    mínimo; el hilo lo hereda, y el agente sale sin lo que la persona instaló (Node, Homebrew, el mismo
    agente: diez tabs con «claude: not found»). "" si no se pudo leer."""
    global _path_de_la_persona
    if _path_de_la_persona is None:
        _path_de_la_persona = ""
        shell = os.environ.get("SHELL") or "/bin/sh"
        base = {k: os.environ[k] for k in ("HOME", "USER", "LOGNAME", "LANG") if k in os.environ}
        try:
            r = subprocess.run([shell, "-lic", 'printf "\n__TELAR_PATH__%s__\n" "$PATH"'], capture_output=True,
                               text=True, timeout=10, stdin=subprocess.DEVNULL,
                               env={**base, "SHELL": shell, "TERM": "dumb"})
            m = re.search(r"__TELAR_PATH__(.*?)__\n", r.stdout)
            if m:
                _path_de_la_persona = m.group(1)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return _path_de_la_persona


def entorno_para_abrir() -> dict[str, str]:
    """El entorno limpio, con el PATH de la persona delante del de este proceso (sin repetir)."""
    env = entorno_limpio()
    partes = [*path_de_la_persona().split(":"), *env.get("PATH", "").split(":")]
    env["PATH"] = ":".join(dict.fromkeys(p for p in partes if p))
    return env


def _descamuflar(salida: str) -> str:
    """Devuelve el separador a ser un byte cuando el tmux de turno lo disfrazó de octal.

    Se toca solo si el byte de verdad no vino en toda la salida: si vino, este tmux no
    disfraza nada y un nombre de ventana que traiga los caracteres `\\037` es un nombre,
    no un separador.
    """
    if SEP in salida or SEP_EN_OCTAL not in salida:
        return salida
    return salida.replace(SEP_EN_OCTAL, SEP)


def _entero(valor: str, campo: str) -> int:
    try:
        return int(valor)
    except ValueError as e:
        raise ErrorDeMux(f"tmux devolvió {valor!r} donde iba {campo}, que es un número") from e


def _linea(comando: Sequence[str] | None) -> str:
    """Vuelve una lista de palabras un solo argumento para tmux, sin perder los bordes.

    tmux recibe el programa a correr como **un** argumento y se lo pasa a un shell. Para
    que eso no sea una inyección, las palabras se citan una por una: lo que entró como
    tres palabras sale como tres palabras, aunque traigan espacios, comillas o un `;`.
    """
    if comando is None:
        return ""
    if isinstance(comando, str):
        raise ErrorDeMux(
            "el comando es una lista de palabras, no una línea de shell; "
            'si hace falta un shell, se pide explícito: ["sh", "-c", "…"]'
        )
    palabras = [str(p) for p in comando]
    if not palabras:
        return ""
    return shlex.join(palabras)


def _corta(linea: str) -> str:
    """La línea de un comando, que tmux acepte: tal cual si cabe en una orden (`LARGO_ORDEN`); si no, la misma línea en
    un guion de shell que se borra al empezar a correr, y la orden es correrlo (`sh <guion>`). Así un agente puede
    arrancar con un primer mensaje largo (un contexto de muchas líneas) sin que tmux lo rechace."""
    if len(linea.encode()) <= LARGO_ORDEN:
        return linea
    import tempfile

    primera = shlex.split(linea)[0] if linea.strip() else ""
    # `exec` deja al comando en el lugar del guion (el panel corre lo mismo que con la línea corta); con una
    # asignación delante (`X=1 programa`), exec la tomaría por el programa
    correr = linea if "=" in primera else f"exec {linea}"
    fd, ruta = tempfile.mkstemp(prefix="telar-orden-", suffix=".sh")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f'rm -f -- "$0"\n{correr}\n')
    return shlex.join(["sh", ruta])


def _banderas(direccion: Direccion) -> tuple[str, ...]:
    return BANDERAS[comprobar_direccion(direccion)]


def _tamano(tamano: int | None) -> list[str]:
    if tamano is None:
        return []
    if not isinstance(tamano, int) or isinstance(tamano, bool) or not 1 <= tamano <= 100:
        raise ErrorDeMux(f"el tamaño es un porcentaje entre 1 y 100, llegó {tamano!r}")
    return ["-l", f"{tamano}%"]


def _carpeta(ruta: Path | None) -> list[str]:
    """`-c` solo si la carpeta existe: tmux se niega a abrir en una que no está."""
    if ruta is None:
        return []
    destino = Path(ruta).expanduser()
    if not destino.is_dir():
        raise NoExiste(f"no existe la carpeta {destino}")
    return ["-c", str(destino)]


class Tmux(MultiplexorBase):
    """Una sesión de tmux, vista como un telar.

    No guarda estado: cada pregunta va al servidor de tmux, que es el que sabe. Eso
    cuesta un proceso por consulta y evita el error más caro de todos, que es dibujar
    una barra con lo que había hace un rato.
    """

    #: `-t` con `=nombre:` y `#{pane_current_command}` piden un tmux moderno, y la 3.4 tiene un segfault
    #: del servidor que se lleva todos los hilos: telar doctor avisa por debajo de la 3.5.
    version_minima = "3.5"

    nombre = "tmux"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.sesion = config.sesion
        self.raiz = config.raiz

    # ── hablarle al programa ─────────────────────────────────────────────────────

    def _tmux(self, *args: str, tolerante: bool = False, entorno: dict | None = None, entrada: str | None = None) -> str:
        """Corre `tmux <args>` y devuelve su salida. El error trae qué se pidió y qué dijo. `entrada`: lo que lee de su
        entrada estándar (`load-buffer -`), que no tiene el tope de largo de una orden."""
        if entorno is None and args and args[0] in ABREN:
            entorno = entorno_para_abrir()
        try:
            hecho = subprocess.run(
                [PROGRAMA, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # lo que capturan los paneles es de otros programas: un byte suelto no la tumba
                timeout=TIEMPO_LIMITE,
                env=entorno,
                input=entrada,
            )
        except FileNotFoundError as e:
            raise SinPrograma("tmux no está instalado, o no está en el PATH") from e
        except subprocess.TimeoutExpired as e:
            pedido = " ".join(args)
            raise ErrorDeMux(
                f"tmux no contestó en {TIEMPO_LIMITE:.0f} s al hacer «tmux {pedido}»"
            ) from e
        if hecho.returncode != 0:
            if tolerante:
                return ""
            raise self._queja(args, hecho.stderr)
        return _descamuflar(hecho.stdout)

    def _queja(self, args: Sequence[str], stderr: str) -> ErrorDeMux:
        """Traduce la queja de tmux al error que corresponde, sin perder lo que dijo."""
        renglones = [r for r in (stderr or "").splitlines() if r.strip()]
        detalle = renglones[-1].strip() if renglones else "sin detalle"
        pedido = " ".join(args)
        dijo = detalle.lower()
        if "no server running" in dijo or "error connecting" in dijo or "failed to connect" in dijo:
            return SinSesion(
                f"no hay un servidor de tmux corriendo: la sesión {self.sesion!r} todavía "
                "no está tejida (al hacer «tmux " + pedido + "»)"
            )
        if "session not found" in dijo or "can't find session" in dijo:
            return SinSesion(
                f"no existe la sesión {self.sesion!r} (al hacer «tmux {pedido}»)"
            )
        if "can't find" in dijo or "not found" in dijo or "no such" in dijo:
            return NoExiste(f"tmux no encontró lo que se le nombró: {detalle} (al hacer «tmux {pedido}»)")
        return ErrorDeMux(f"tmux falló: {detalle} (al hacer «tmux {pedido}»)")

    def _ok(self, *args: str) -> bool:
        """¿Salió bien? Para las preguntas de sí o no, que no deben levantar excepción."""
        try:
            hecho = subprocess.run(
                [PROGRAMA, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # lo que capturan los paneles es de otros programas: un byte suelto no la tumba
                timeout=TIEMPO_LIMITE,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return hecho.returncode == 0

    def _listar(self, *args: str) -> str:
        """Una consulta que, si la sesión todavía no existe, devuelve vacío en vez de quejarse."""
        try:
            return self._tmux(*args)
        except SinSesion:
            return ""

    # ── traducir lo que se nombra al objetivo que tmux espera ────────────────────

    def _objetivo_tab(self, tab: str) -> str:
        """`@3` como viene, `3` como índice de la sesión, cualquier otra cosa como nombre exacto.

        El `=` que va delante del nombre es de tmux: sin él, `trabajo` también calza con
        `trabajo-viejo`, y uno termina cerrando el tab de al lado.

        `@3` va con la sesión delante: una ventana que además miran sesiones agrupadas (otra máquina,
        el celular) está en varias sesiones, y `select-window -t @3` a secas puede elegir la de quien
        mira y moverle la pantalla.
        """
        aguja = str(tab).strip()
        if not aguja:
            raise NoExiste("no se nombró ningún tab")
        if aguja.startswith("@"):
            return f"={self.sesion}:{aguja}"
        if aguja.isdigit():
            return f"={self.sesion}:{aguja}"
        return f"={self.sesion}:={aguja}"

    def _objetivo_pane(self, pane: str) -> str:
        aguja = str(pane).strip()
        if not aguja:
            raise NoExiste("no se nombró ningún panel")
        return aguja

    @property
    def _objetivo_sesion(self) -> str:
        """La sesión entera. Los dos puntos no sobran: sin ellos tmux no resuelve la ventana."""
        return f"={self.sesion}:"

    # ── leer lo que contestó ─────────────────────────────────────────────────────

    def _tab(self, renglon: str) -> Tab:
        campos = renglon.split(SEP)
        # sin el último campo (la marca remota) también se entiende: es un agregado
        if len(campos) == len(CAMPOS_TAB) - 1:
            campos.append("")
        if len(campos) != len(CAMPOS_TAB):
            raise ErrorDeMux(
                f"tmux devolvió {len(campos)} campos donde iban {len(CAMPOS_TAB)}: {renglon!r}"
            )
        ident, indice, nombre, activo, paneles, remoto = campos
        return Tab(
            id=ident,
            posicion=_entero(indice, "el índice del tab"),
            nombre=nombre,
            activo=activo == "1",
            paneles=_entero(paneles, "la cuenta de paneles"),
            remoto=remoto.strip(),
        )

    def _pane_desde(self, renglon: str) -> Pane:
        campos = renglon.split(SEP)
        if len(campos) != len(CAMPOS_PANE):
            raise ErrorDeMux(
                f"tmux devolvió {len(campos)} campos donde iban {len(CAMPOS_PANE)}: {renglon!r}"
            )
        ident, ventana, titulo, comando, ruta, activo, muerto, pid = campos
        return Pane(
            id=ident,
            tab=ventana,
            titulo=titulo,
            comando=comando,
            ruta=Path(ruta) if ruta else None,
            foco=activo == "1",
            flotante=False,  # tmux no tiene paneles flotantes; sus popups no son paneles.
            terminado=muerto == "1",
            pid=int(pid) if pid.isdigit() else None,
        )

    def _pane(self, pane: str) -> Pane:
        """Vuelve a preguntar por un panel recién abierto o movido, para devolverlo completo."""
        salida = self._tmux("display-message", "-p", "-t", self._objetivo_pane(pane), FORMATO_PANE)
        renglon = salida.strip("\n")
        if not renglon:
            raise NoExiste(f"tmux abrió el panel {pane} pero después no supo describirlo")
        return self._pane_desde(renglon)

    # ── la sesión ────────────────────────────────────────────────────────────────

    def disponible(self) -> bool:
        return shutil.which(PROGRAMA) is not None

    def viva(self) -> bool:
        if not self.disponible():
            return False
        return self._ok("has-session", "-t", f"={self.sesion}")

    def version(self) -> str:
        # «tmux 3.7c» → «3.7c»; con -V no hace falta servidor ni sesión
        salida = self._tmux("-V", tolerante=True).strip()
        return salida.split(" ", 1)[1] if " " in salida else salida

    def huella(self) -> str:
        salida = self._tmux(
            "display-message", "-p", "-t", self._objetivo_sesion,
            "#{session_id}:#{session_created}", tolerante=True,
        ).strip()
        return salida

    def tejer(self) -> None:
        if not self.disponible():
            raise SinPrograma("tmux no está instalado, o no está en el PATH")
        if not self.viva():
            self._levantar()
        self.limpiar_entorno()
        self.ganchos()

    def _levantar(self) -> None:
        # Quien teje suele estar dentro de otra cosa (otro multiplexor, la Bash de un Claude Code), y el servidor de tmux
        # que nace aquí hereda su entorno entero y se lo pasa a cada panel. Se levanta limpio.
        self._tmux("new-session", "-d", "-s", self.sesion, *_carpeta(self.raiz),
                   entorno=entorno_limpio())

    def limpiar_entorno(self) -> list[str]:
        """Borra del entorno global del servidor de tmux lo que un panel no hereda (`telar.entorno`), y devuelve lo que
        borró. Es el entorno de quien levantó el servidor, que puede no haber sido telar: un `tmux` corrido desde la Bash
        de un Claude Code le dejaba a cada hilo que se abría después las marcas de esa sesión. Va cada vez que se teje,
        aunque el servidor y la sesión ya estuvieran: una lectura, y una orden más solo si hay algo que borrar."""
        sobran = []
        for renglon in self._tmux("show-environment", "-g", tolerante=True).splitlines():
            nombre, igual, valor = renglon.partition("=")
            if igual and not mod_entorno.heredable(nombre, valor):  # sin «=»: «-NOMBRE», ya marcada para quitar
                sobran.append(nombre)
        if sobran:
            orden: list[str] = []
            for nombre in sobran:
                orden += [";", "set-environment", "-g", "-u", nombre]
            self._tmux(*orden[1:], tolerante=True)  # todas en una llamada: «;» separa órdenes de tmux
        return sobran

    def ganchos(self) -> None:
        """Que tmux le cuente a telar cuando la persona cambia de tab: con alguien mirando la sesión (un cliente
        enganchado), `telar tiempo marcar` con el nombre del tab. Es lo que dice qué hilo se vio (lo que terminó deja
        de estar «sin ver») y cuánto tiempo se le dedicó. Sin esto, solo lo anotaban `telar ir` y la página. Se ponen
        cada vez que se teje (son idempotentes); si no se encuentra telar, o su ruta no se puede citar, no se ponen."""
        telar = ejecutable_telar()
        if not telar or not RUTA_CITABLE.fullmatch(telar):
            return
        orden = f"if-shell -F '#{{session_attached}}' \"run-shell -b '{telar} tiempo marcar -- #{{q:window_name}}'\""
        for gancho in GANCHOS_FOCO:
            self._tmux("set-hook", "-t", self._objetivo_sesion, gancho, orden, tolerante=True)

    # ── tabs ─────────────────────────────────────────────────────────────────────

    def tabs(self) -> list[Tab]:
        salida = self._listar("list-windows", "-t", f"={self.sesion}", "-F", FORMATO_TAB)
        return [self._tab(r) for r in salida.splitlines() if r.strip()]

    def tab_activo(self) -> Tab | None:
        salida = self._listar("display-message", "-p", "-t", self._objetivo_sesion, FORMATO_TAB)
        renglon = salida.strip("\n")
        if not renglon or renglon.strip(SEP) == "":
            return None
        return self._tab(renglon)

    @staticmethod
    def _llama_un_agente() -> bool:
        """Quien corre el comando es un agente (`$TELAR_HILO`), no una persona.

        El foco es de la persona: dentro de tmux, `switch-client` mueve al cliente que mira el panel
        del agente, que es la terminal de la persona en el hilo de ese agente. Un agente delegando un pendiente
        le cambiaba esa terminal por la del hilo nuevo, y el agente parecía muerto."""
        return bool(os.environ.get("TELAR_HILO", "").strip())

    def ir_a_tab(self, tab: str) -> None:
        if self._llama_un_agente():
            return
        objetivo = self._objetivo_tab(tab)
        self._tmux("select-window", "-t", objetivo)
        cliente = self._cliente()
        if cliente:
            # Tolerante a propósito: entre una llamada y otra el cliente pudo irse, y eso
            # no invalida el cambio de tab que la sesión ya hizo.
            self._tmux("switch-client", "-c", cliente, "-t", objetivo, tolerante=True)

    def _cliente(self) -> str:
        """El terminal al que hay que apuntar, o vacío si no hay nadie mirando.

        Si el comando salió de adentro de tmux, el cliente es el que preguntó —aunque
        esté en otra sesión, que es justo el caso en que `select-window` no alcanza—. Si
        salió de afuera, se busca alguno enganchado a la sesión del telar.
        """
        if os.environ.get("TMUX"):
            tty, _, sesion = self._tmux("display-message", "-p", f"#{{client_tty}}{SEP}#{{client_session}}",
                                        tolerante=True).strip().partition(SEP)
            # quien mira un solo hilo desde otra máquina o el celular (`ver-…`, `movil-…`) no se mueve:
            # su sesión está fija en esa ventana, y moverla es mostrarle otro hilo creyendo que es el suyo
            if sesion.startswith(("ver-", "movil-")):
                return ""
            if tty:
                return tty
        salida = self._tmux(
            "list-clients", "-F", f"#{{client_tty}}{SEP}#{{client_session}}", tolerante=True
        )
        for renglon in salida.splitlines():
            tty, _, sesion = renglon.partition(SEP)
            if tty and sesion == self.sesion:
                return tty
        return ""

    def clientes(self) -> list[int]:
        salida = self._tmux(
            "list-clients", "-t", f"={self.sesion}", "-F", "#{client_pid}", tolerante=True
        )
        return [int(r) for r in salida.split() if r.strip().isdigit()]

    def crear_tab(
        self,
        nombre: str,
        *,
        ruta: Path | None = None,
        comando: Sequence[str] | None = None,
        foco: bool = True,
    ) -> Tab:
        linea = _corta(_linea(comando))
        carpeta = _carpeta(ruta)

        if not self.viva():
            # Tejer y después abrir el tab dejaría un shell huérfano en el índice 0: la
            # sesión nace directamente con el tab que se pidió.
            if not self.disponible():
                raise SinPrograma("tmux no está instalado, o no está en el PATH")
            self.limpiar_entorno()  # si el servidor ya estaba, el tab nace con su entorno global
            args = ["new-session", "-d", "-s", self.sesion, "-P", "-F", FORMATO_TAB]
            if nombre:
                args += ["-n", nombre]
            args += carpeta or _carpeta(self.raiz)
        else:
            args = ["new-window", "-t", self._objetivo_sesion, "-P", "-F", FORMATO_TAB]
            if nombre:
                args += ["-n", nombre]
            args += carpeta
            if not foco or self._llama_un_agente():
                args.append("-d")

        if linea:
            args += ["--", linea]

        renglon = self._tmux(*args).strip("\n")
        if not renglon:
            raise ErrorDeMux("tmux abrió el tab pero no dijo cuál es")
        return self._tab(renglon)

    def renombrar_tab(self, tab: str, nombre: str) -> None:
        if not str(nombre).strip():
            raise ErrorDeMux("un tab sin nombre no se distingue de los otros")
        # `rename-window` apaga solo el renombrado automático de esa ventana: el nombre
        # puesto a mano no se lo lleva el primer comando que corra adentro.
        self._tmux("rename-window", "-t", self._objetivo_tab(tab), nombre)

    def marcar_remoto(self, tab: str, remoto: str) -> None:
        self._tmux("set-option", "-w", "-t", self._objetivo_tab(tab), OPCION_REMOTO, remoto)

    def cerrar_tab(self, tab: str) -> None:
        self._tmux("kill-window", "-t", self._objetivo_tab(tab))

    # ── paneles ──────────────────────────────────────────────────────────────────

    def panes(self, tab: str | None = None) -> list[Pane]:
        if tab is None:
            # Los dos puntos del objetivo no sobran: sin ellos tmux lee el nombre como el
            # de una *ventana* y, con el servidor vivo pero la sesión sin tejer, se queja
            # de «can't find window» —un `NoExiste`— donde el contrato pide una lista
            # vacía. Con `=sesion:` se queja de la sesión, que es lo que de verdad falta.
            args = ("list-panes", "-s", "-t", self._objetivo_sesion, "-F", FORMATO_PANE)
        else:
            args = ("list-panes", "-t", self._objetivo_tab(tab), "-F", FORMATO_PANE)
        salida = self._listar(*args)
        return [self._pane_desde(r) for r in salida.splitlines() if r.strip()]

    def enfocar_pane(self, pane: str) -> None:
        objetivo = self._objetivo_pane(pane)
        ventana = self._tmux("display-message", "-p", "-t", objetivo, "#{window_id}").strip()
        self._tmux("select-pane", "-t", objetivo)
        # Enfocar un panel de otro tab sin ir al tab deja el foco donde estaba: media
        # operación. Se completa.
        if ventana:
            self.ir_a_tab(ventana)

    def escribir_pane(self, pane: str, texto: str, *, enviar: bool = False, pegar: bool = False) -> None:
        objetivo = self._objetivo_pane(pane)
        if texto:
            if not enviar and not pegar and ("\n" in texto or "\r" in texto):
                raise ErrorDeMux(
                    "escribir sin enviar no admite saltos de línea: el salto ES el ↩. "
                    "Con enviar=True el texto se manda entero."
                )
            if pegar or "\n" in texto or "\r" in texto or len(texto.encode()) > LARGO_ORDEN:
                # varias líneas: pegadas de una vez (bracketed paste, -p), para que cada salto no sea un ↩
                # que manda la primera línea sola; el ↩ de enviar va después, una vez. El texto entra al
                # buffer por la entrada de tmux, no en la orden: así no tiene el tope de una orden (un
                # contexto largo, un chat entero)
                buffer = f"telar-{os.getpid()}-{next(_BUFFERS)}"
                self._tmux("load-buffer", "-b", buffer, "-", entrada=texto)
                self._tmux("paste-buffer", "-p", "-d", "-b", buffer, "-t", objetivo)
            else:
                # `-l` manda el texto tal cual, sin buscarle nombres de tecla: un texto con la
                # palabra «Enter» adentro no puede convertirse en un ↩.
                self._tmux("send-keys", "-t", objetivo, "-l", "--", texto)
        if enviar:
            self._tmux("send-keys", "-t", objetivo, "Enter")

    def capturar_pane(self, pane: str, lineas: int = 300) -> str | None:
        # -J junta las líneas que tmux partió por el ancho; -S desde cuántas atrás
        return self._tmux("capture-pane", "-p", "-J", "-S", f"-{max(1, int(lineas))}",
                          "-t", self._objetivo_pane(pane))

    def capturar_pane_con_escapes(self, pane: str, lineas: int = 60) -> str | None:
        """Lo de abajo de la pantalla, con sus colores y atributos (`-e`): lo tenue (la sugerencia de Claude Code en su
        caja) se distingue de lo escrito (telar.dormir)."""
        return self._tmux("capture-pane", "-p", "-e", "-J", "-S", f"-{max(1, int(lineas))}",
                          "-t", self._objetivo_pane(pane))

    def abrir_pane(
        self,
        comando: Sequence[str] | None = None,
        *,
        junto_a: str | None = None,
        reemplaza: str | None = None,
        direccion: Direccion = "derecha",
        tamano: int | None = None,
        ruta: Path | None = None,
        titulo: str = "",
        foco: bool = True,
    ) -> Pane:
        if junto_a and reemplaza:
            raise ErrorDeMux(
                "abrir_pane: o se abre junto_a un panel, o se reemplaza uno; las dos cosas no"
            )
        linea = _corta(_linea(comando))
        carpeta = _carpeta(ruta)

        if reemplaza:
            viejo = self._objetivo_pane(reemplaza)
            # se abre el nuevo junto al viejo y se cierra el viejo: el nuevo queda con todo su lugar.
            # No `respawn-pane -k`, que lo hacía en el mismo panel sin mover la pantalla: tmux 3.4 se
            # cae con él (un segfault que se lleva la sesión entera, visto dos veces en un servidor)
            args = ["split-window", "-t", viejo, "-P", "-F", "#{pane_id}", *carpeta]
            if not foco:
                args.append("-d")
            if linea:
                args += ["--", linea]
            nuevo = self._tmux(*args).strip()
            if not nuevo:
                raise ErrorDeMux("tmux abrió el panel pero no dijo cuál es")
            self._tmux("kill-pane", "-t", viejo)
        else:
            objetivo = self._objetivo_pane(junto_a) if junto_a else self._objetivo_sesion
            args = [
                "split-window",
                "-t",
                objetivo,
                "-P",
                "-F",
                "#{pane_id}",
                *_banderas(direccion),
                *_tamano(tamano),
                *carpeta,
            ]
            if not foco:
                args.append("-d")
            if linea:
                args += ["--", linea]
            nuevo = self._tmux(*args).strip()
            if not nuevo:
                raise ErrorDeMux("tmux abrió el panel pero no dijo cuál es")

        if titulo:
            self._tmux("select-pane", "-t", nuevo, "-T", titulo)
        return self._pane(nuevo)

    def cerrar_pane(self, pane: str) -> None:
        self._tmux("kill-pane", "-t", self._objetivo_pane(pane))

    def mover_pane(
        self,
        pane: str,
        *,
        tab: str | None = None,
        junto_a: str | None = None,
        direccion: Direccion = "derecha",
        tamano: int | None = None,
        nombre: str = "",
        foco: bool = True,
    ) -> Pane:
        origen = self._objetivo_pane(pane)

        if junto_a is None and tab is None:
            # A un tab propio. `break-pane` no reinicia nada: el proceso sigue corriendo,
            # con su historial y su salida, en una ventana nueva.
            args = ["break-pane", "-s", origen, "-P", "-F", "#{pane_id}"]
            if nombre:
                args += ["-n", nombre]
            if not foco:
                args.append("-d")
            movido = self._tmux(*args).strip()
            return self._pane(movido or origen)

        destino = self._objetivo_pane(junto_a) if junto_a else self._objetivo_tab(tab or "")
        args = [
            "move-pane",
            "-s",
            origen,
            "-t",
            destino,
            *_banderas(direccion),
            *_tamano(tamano),
        ]
        if not foco:
            args.append("-d")
        self._tmux(*args)
        # El panel se muda con su identidad puesta: el `%7` que entró es el `%7` que sale.
        return self._pane(origen)


def construir(config: Config) -> Tmux:
    """La fábrica que busca `telar.mux.obtener`."""
    return Tmux(config)
