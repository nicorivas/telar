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

import os
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

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

PROGRAMA = "tmux"

#: Ninguna consulta a tmux debería demorar esto; si demora, es que el servidor se colgó
#: y más vale un error que una barra de estado congelada.
TIEMPO_LIMITE = 5.0

#: Separador de campos: el byte 0x1f de ASCII, que no aparece en un nombre de ventana
#: ni en una ruta. Con un tabulador o un espacio, un nombre con espacios rompe el parseo.
SEP = "\x1f"

CAMPOS_TAB = (
    "#{window_id}",
    "#{window_index}",
    "#{window_name}",
    "#{window_active}",
    "#{window_panes}",
)
FORMATO_TAB = SEP.join(CAMPOS_TAB)

CAMPOS_PANE = (
    "#{pane_id}",
    "#{window_id}",
    "#{pane_title}",
    "#{pane_current_command}",
    "#{pane_current_path}",
    "#{pane_active}",
    "#{pane_dead}",
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

    nombre = "tmux"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.sesion = config.sesion
        self.raiz = config.raiz

    # ── hablarle al programa ─────────────────────────────────────────────────────

    def _tmux(self, *args: str, tolerante: bool = False) -> str:
        """Corre `tmux <args>` y devuelve su salida. El error trae qué se pidió y qué dijo."""
        try:
            hecho = subprocess.run(
                [PROGRAMA, *args],
                capture_output=True,
                text=True,
                timeout=TIEMPO_LIMITE,
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
        return hecho.stdout

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
        """
        aguja = str(tab).strip()
        if not aguja:
            raise NoExiste("no se nombró ningún tab")
        if aguja.startswith("@"):
            return aguja
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
        if len(campos) != len(CAMPOS_TAB):
            raise ErrorDeMux(
                f"tmux devolvió {len(campos)} campos donde iban {len(CAMPOS_TAB)}: {renglon!r}"
            )
        ident, indice, nombre, activo, paneles = campos
        return Tab(
            id=ident,
            posicion=_entero(indice, "el índice del tab"),
            nombre=nombre,
            activo=activo == "1",
            paneles=_entero(paneles, "la cuenta de paneles"),
        )

    def _pane_desde(self, renglon: str) -> Pane:
        campos = renglon.split(SEP)
        if len(campos) != len(CAMPOS_PANE):
            raise ErrorDeMux(
                f"tmux devolvió {len(campos)} campos donde iban {len(CAMPOS_PANE)}: {renglon!r}"
            )
        ident, ventana, titulo, comando, ruta, activo, muerto = campos
        return Pane(
            id=ident,
            tab=ventana,
            titulo=titulo,
            comando=comando,
            ruta=Path(ruta) if ruta else None,
            foco=activo == "1",
            flotante=False,  # tmux no tiene paneles flotantes; sus popups no son paneles.
            terminado=muerto == "1",
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

    def tejer(self) -> None:
        if not self.disponible():
            raise SinPrograma("tmux no está instalado, o no está en el PATH")
        if self.viva():
            return
        self._tmux("new-session", "-d", "-s", self.sesion, *_carpeta(self.raiz))

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

    def ir_a_tab(self, tab: str) -> None:
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
            tty = self._tmux("display-message", "-p", "#{client_tty}", tolerante=True).strip()
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

    def crear_tab(
        self,
        nombre: str,
        *,
        ruta: Path | None = None,
        comando: Sequence[str] | None = None,
        foco: bool = True,
    ) -> Tab:
        linea = _linea(comando)
        carpeta = _carpeta(ruta)

        if not self.viva():
            # Tejer y después abrir el tab dejaría un shell huérfano en el índice 0: la
            # sesión nace directamente con el tab que se pidió.
            if not self.disponible():
                raise SinPrograma("tmux no está instalado, o no está en el PATH")
            args = ["new-session", "-d", "-s", self.sesion, "-P", "-F", FORMATO_TAB]
            if nombre:
                args += ["-n", nombre]
            args += carpeta or _carpeta(self.raiz)
        else:
            args = ["new-window", "-t", self._objetivo_sesion, "-P", "-F", FORMATO_TAB]
            if nombre:
                args += ["-n", nombre]
            args += carpeta
            if not foco:
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

    def escribir_pane(self, pane: str, texto: str, *, enviar: bool = False) -> None:
        objetivo = self._objetivo_pane(pane)
        if texto:
            if not enviar and ("\n" in texto or "\r" in texto):
                raise ErrorDeMux(
                    "escribir sin enviar no admite saltos de línea: el salto ES el ↩. "
                    "Con enviar=True el texto se manda entero."
                )
            # `-l` manda el texto tal cual, sin buscarle nombres de tecla: un texto con la
            # palabra «Enter» adentro no puede convertirse en un ↩.
            self._tmux("send-keys", "-t", objetivo, "-l", "--", texto)
        if enviar:
            self._tmux("send-keys", "-t", objetivo, "Enter")

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
        linea = _linea(comando)
        carpeta = _carpeta(ruta)

        if reemplaza:
            nuevo = self._objetivo_pane(reemplaza)
            # `respawn-pane -k` mata lo que corría y arranca lo nuevo en el mismo panel: la
            # pantalla no se mueve ni un carácter, que es todo el punto de reemplazar.
            args = ["respawn-pane", "-k", "-t", nuevo, *carpeta]
            if linea:
                args += ["--", linea]
            self._tmux(*args)
            if foco:
                self._tmux("select-pane", "-t", nuevo)
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
