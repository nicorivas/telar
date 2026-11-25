"""Lo que toda prueba necesita antes de importar telar.

Tres cosas: que `src/` esté en el camino aunque nadie haya instalado el paquete
(para poder correr las pruebas en un clon recién bajado), que las variables
`TELAR_*` del que corre las pruebas no se cuelen adentro — una configuración
heredada del entorno es la forma más silenciosa de que una prueba mienta —, y que
ninguna prueba alcance lo vivo de quien las corre (`aislar_sesion`, abajo).
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLO = RAIZ / "ejemplo"

if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))


# ── La red de seguridad de la sesión ──────────────────────────────────────────────────────────────────────────────
#
# Cada hilo corre las pruebas desde su panel, con el entorno de su sesión: `TMUX` y `TMUX_PANE` (el servidor de tmux
# de la persona y el panel del hilo), `TELAR_HILO` (el hilo), y la configuración y el estado de telar de la persona
# en su lugar de siempre. Una prueba que se olvide de aislarse los alcanza: un `tmux kill-server` sin `-S` sigue a
# `TMUX` antes que a `TMUX_TMPDIR` y mató el tmux de la persona con todos sus hilos; un pytest de una copia vieja,
# corrido con `TELAR_HILO` de un hijo, le cerró la ventana y telar lo archivó (18-nov-2026). Por eso, antes de que se
# importe una sola prueba, el proceso de las pruebas pierde esas marcas y todo lo que telar lee del entorno apunta a
# una carpeta temporal de la sesión, que se borra al salir. Corre al importar este módulo: desde `conftest.py` con
# pytest, y desde la primera prueba que lo importe con `unittest`. Cada prueba sigue aislándose sola (un `TMUX_TMPDIR`
# propio, `Prueba`); esto es lo que queda debajo para la que no lo haga.

#: Las que apuntan a lo vivo de quien corre las pruebas y se quitan, además de las `TELAR_*`, de otro multiplexor
#: (`ZELLIJ_*`) y de la sesión de Claude Code que las lanzó (`telar.entorno`): su servidor de tmux y su panel, la
#: configuración de su Claude Code, y dónde guarda su historia y su configuración la shell que abre un panel de prueba.
VIVAS = ("TMUX", "TMUX_PANE", "CLAUDE_CONFIG_DIR", "HISTFILE", "ZDOTDIR", "GIT_CONFIG_GLOBAL")

#: Las `TELAR_*` que no son de la persona sino de las pruebas: dicen cuáles corren (y se leen al importar). Pasan.
DE_LAS_PRUEBAS = ("TELAR_NATS_SERVER",)

#: Dónde telar busca la configuración, el estado, los módulos instalados y lo cacheado de la persona si nadie dice otra
#: cosa (`~/.config/telar`, `~/.local/state/telar`, `~/.local/share/telar`, `~/.cache/telar`): en la sesión, carpetas
#: temporales suyas. Y el hogar entero (`HOME`): lo que va a `~` sin pasar por estas (la historia de la shell de un
#: panel de prueba, `~/.claude`) tampoco llega al de la persona.
XDG = {"XDG_CONFIG_HOME": "config", "XDG_STATE_HOME": "estado", "XDG_DATA_HOME": "datos", "XDG_CACHE_HOME": "cache"}

#: La carpeta temporal de esta sesión de pruebas (la pone `aislar_sesion`). Con pytest-xdist, cada proceso que corre
#: pruebas tiene la suya dentro de la del que los reparte (`gw0`, `gw1`…): su estado, su hogar y su tmux, aparte.
SESION: Path | None = None
PREFIJO = "telar-pruebas-"

#: Dónde queda dicha esa carpeta, para lo que viene después en el mismo proceso (este archivo importado con otro nombre,
#: `pruebas.comun`) o en uno que una prueba lance: la misma sesión, no otra. No empieza con `TELAR_`: `Prueba` las saca.
MARCA = "PRUEBAS_TELAR_SESION"

#: El hilo de telar desde el que se corrieron las pruebas, antes de sacarlo del entorno: solo para decir quién tiene
#: un turno (`turno`).
HILO_DE_AFUERA = ""


def _sesion_heredada() -> Path | None:
    """La sesión que dejó dicha quien lanzó este proceso, si es una de estas (y no una ruta cualquiera)."""
    valor = os.environ.get(MARCA, "")
    p = Path(valor)
    if valor and p.is_dir() and (p.name.startswith(PREFIJO) or p.parent.name.startswith(PREFIJO)):
        return p.resolve()
    return None


def aislar_sesion() -> Path:
    """Saca del entorno de este proceso lo que apunta a lo vivo de quien corre las pruebas, y deja el hogar, la
    configuración, el estado y el servidor de tmux en una carpeta temporal de la sesión. Devuelve esa carpeta. La crea
    la primera vez y, al salir, mata los servidores de tmux que alguna prueba haya levantado ahí (con `-S`: los suyos y
    ningún otro) y la borra; lo que viene después (otro nombre del módulo, un proceso hijo) usa la misma, y cada
    proceso de pytest-xdist, una suya adentro."""
    global SESION, HILO_DE_AFUERA
    if SESION is not None:
        return SESION
    heredada = _sesion_heredada()
    trabajador = os.environ.get("PYTEST_XDIST_WORKER", "")
    HILO_DE_AFUERA = os.environ.get("TELAR_HILO", "")
    gitconfig = _identidad_git() if heredada is None else ""  # antes de tocar nada: se lee donde la persona la tenga
    for clave in [*VIVAS, *(k for k in os.environ if k.startswith("TELAR_") and k not in DE_LAS_PRUEBAS)]:
        os.environ.pop(clave, None)
    if heredada is None:
        SESION = Path(tempfile.mkdtemp(prefix=PREFIJO)).resolve()
        atexit.register(_cerrar_sesion, SESION)
    elif trabajador and heredada.name.startswith(PREFIJO):
        SESION = heredada / trabajador  # el que reparte la borra al terminar, con su tmux
        SESION.mkdir(exist_ok=True)
        if (heredada / "casa" / ".gitconfig").is_file():
            gitconfig = (heredada / "casa" / ".gitconfig").read_text(encoding="utf-8")
    else:
        SESION = heredada
    for variable, carpeta in XDG.items():
        (SESION / carpeta).mkdir(exist_ok=True)
        os.environ[variable] = str(SESION / carpeta)
    (SESION / "tmux").mkdir(mode=0o700, exist_ok=True)
    os.environ["TMUX_TMPDIR"] = str(SESION / "tmux")
    casa = SESION / "casa"
    casa.mkdir(exist_ok=True)
    if gitconfig:
        (casa / ".gitconfig").write_text(gitconfig, encoding="utf-8")
    os.environ["HOME"] = str(casa)
    os.environ[MARCA] = str(SESION)
    # Las de la sesión de Claude Code y de otro multiplexor, con la lista de telar (que es la que se mantiene al día).
    # Se importa después de lo de arriba: nada de telar alcanza a leer el entorno de la persona.
    from telar import entorno
    for clave in [k for k in os.environ if k in entorno.QUITAR or entorno.ID_DE_SESION.fullmatch(k)]:
        del os.environ[clave]
    return SESION


def _identidad_git() -> str:
    """El nombre y el correo de git de quien corre las pruebas, como `.gitconfig` para el hogar de la sesión: las que
    commitean en un repositorio temporal sin decir quién siguen pudiendo, y un `git config --global` de una prueba
    escribe ahí, no en el de la persona. Lo demás de su configuración de git no pasa."""
    lineas = []
    for clave in ("user.name", "user.email"):
        try:
            r = subprocess.run(["git", "config", "--global", "--get", clave], capture_output=True, text=True)
        except OSError:  # sin git
            return ""
        if r.returncode == 0 and r.stdout.strip():
            lineas.append(f"\t{clave.split('.')[1]} = {r.stdout.strip()}")
    return "[user]\n" + "\n".join(lineas) + "\n" if lineas else ""


def _cerrar_sesion(carpeta: Path) -> None:
    for tmux in [carpeta / "tmux", *carpeta.glob("*/tmux")]:  # el suyo y el de cada proceso de pytest-xdist
        matar_tmux(tmux)
    shutil.rmtree(carpeta, ignore_errors=True)


# ── El turno de la suite completa ─────────────────────────────────────────────────────────────────────────────────
#
# Varios hilos corren la suite a la vez (un padre y sus hijos, cada uno en su worktree) y, con la máquina cargada, 70 s
# se vuelven varios minutos y las pruebas con relojes fallan. Como mucho `TURNOS` suites completas a la vez en la
# máquina: la siguiente espera, y dice que espera y a quién (`conftest.py` lo pide con pytest; un archivo suelto no).

TURNOS = 2
#: En /tmp y no en el hogar: de todas las cuentas de la máquina (en el servidor, las de cada persona alojada).
CARPETA_TURNOS = Path("/tmp")


def turno(avisar=None, *, ranuras: int = TURNOS, carpeta: Path = CARPETA_TURNOS, cada: float = 1.0) -> int | None:
    """Espera un turno para correr la suite completa: uno de los `ranuras` archivos `telar-pruebas.turno.N` de
    `carpeta`, tomado con `flock`. Devuelve el descriptor que lo tiene: el turno se suelta al cerrarlo o cuando el
    proceso termina, aunque muera. Si tiene que esperar, `avisar(texto)` dice a quién, y otra vez cuando le toca. None
    si no hay dónde tomar turnos (y entonces no espera)."""
    import fcntl
    import time

    fds = []
    for n in range(ranuras):
        ruta = Path(carpeta) / f"telar-pruebas.turno.{n}"
        try:  # sin seguir enlaces: en /tmp, un enlace puesto ahí haría escribir en otro archivo
            fd = os.open(ruta, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o666)
            try:
                os.fchmod(fd, 0o666)  # que otra cuenta de la máquina pueda escribir quién lo tiene (si es mío)
            except OSError:
                pass
        except PermissionError:
            try:
                fd = os.open(ruta, os.O_RDONLY | os.O_NOFOLLOW)  # de otra cuenta: para flock basta leerlo
            except OSError:
                continue
        except OSError:
            continue
        fds.append(fd)
    if not fds:
        return None
    desde, avisado = time.monotonic(), False
    try:
        while True:
            for fd in fds:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                for otro in fds:
                    if otro != fd:
                        os.close(otro)
                _anotar_turno(fd)
                if avisado and avisar:
                    avisar(f"pruebas: me tocó, tras {round(time.monotonic() - desde)} s")
                return fd
            if not avisado and avisar:
                quienes = "; ".join(q for q in map(_quien_tiene, fds) if q) or "no dicen quiénes"
                avisar(f"pruebas: ya corren {len(fds)} suites completas en esta máquina ({quienes}); "
                       f"espero turno (como mucho {len(fds)} a la vez)…")
                avisado = True
            time.sleep(cada)
    except BaseException:
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                pass
        raise


def _anotar_turno(fd: int) -> None:
    hilo = f"hilo {HILO_DE_AFUERA}, " if HILO_DE_AFUERA else ""
    texto = f"pid {os.getpid()}, {hilo}en {os.getcwd()}"
    try:
        os.ftruncate(fd, 0)
        os.pwrite(fd, texto.encode(), 0)
    except OSError:  # de otra cuenta, abierto solo para leer: el turno vale igual
        pass


def _quien_tiene(fd: int) -> str:
    try:
        return os.pread(fd, 400, 0).decode("utf-8", "replace").strip()
    except OSError:
        return ""


aislar_sesion()


try:
    import fastapi  # noqa: F401
    HAY_FASTAPI = True
except ImportError:  # sin el extra «serve»: las pruebas de la API y de la página se saltan
    HAY_FASTAPI = False


class Prueba(unittest.TestCase):
    """Caso base: el entorno queda limpio de `TELAR_*` mientras dure la prueba."""

    def setUp(self) -> None:
        super().setUp()
        entorno = {k: v for k, v in os.environ.items() if k.startswith("TELAR_")}
        for clave in entorno:
            del os.environ[clave]
        # Un HOME de verdad haría que `cargar()` leyera la config del que corre las
        # pruebas. Se apunta a una ruta que no existe y listo.
        hogar = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(RAIZ / "pruebas" / "no-existe")
        # Se vuelve con `addCleanup`, no en `tearDown`: corre aunque la prueba se salte o falle en su `setUp` (sin eso,
        # `XDG_CONFIG_HOME` quedaba en `no-existe` para las que venían después), y en orden si `setUp` corre dos veces.
        self.addCleanup(self._volver, entorno, hogar)

    @staticmethod
    def _volver(entorno: dict[str, str], hogar: str | None) -> None:
        for clave in [k for k in os.environ if k.startswith("TELAR_")]:
            del os.environ[clave]
        os.environ.update(entorno)
        if hogar is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = hogar


def socket_tmux(carpeta) -> str:
    """El socket del servidor de tmux de una prueba cuyo `TMUX_TMPDIR` es `carpeta`. Deja hecha su carpeta, como la
    haría tmux (solo de quien corre: si no, tmux no la usa), para levantar el servidor con `-S`."""
    donde = Path(carpeta) / f"tmux-{os.getuid()}"
    donde.mkdir(mode=0o700, exist_ok=True)
    return str(donde / "default")


def matar_tmux(carpeta) -> None:
    """Mata el servidor de tmux de la prueba (el de `carpeta`, su `TMUX_TMPDIR`) y solo ese: con el socket explícito
    (`-S`), no por el entorno. Un `tmux kill-server` a secas sigue a `TMUX` antes que a `TMUX_TMPDIR`, y con `TMUX`
    puesto (las pruebas corridas desde un hilo) mata el servidor de la persona con todos sus hilos (18-nov-2026)."""
    subprocess.run(["tmux", "-S", socket_tmux(carpeta), "kill-server"], capture_output=True)


class KvDeMentira:
    """El almacén del estado del bus, en memoria, con revisiones: lo que lee y escribe condicionado telar.dueno
    (`get`, `create`, `update`, `put`, `delete`). Cada escritura queda en `puestos`."""

    class KeyNotFoundError(Exception):
        pass

    class KeyWrongLastSequenceError(Exception):
        pass

    def __init__(self, entradas: dict | None = None):
        import json as _json

        self._json = _json
        self.n = 0
        self.actual: dict = {}
        self.puestos: list = []
        for k, d in (entradas or {}).items():
            self.n += 1
            self.actual[k] = (self.n, d)

    async def get(self, k):
        from types import SimpleNamespace

        if k not in self.actual:
            raise self.KeyNotFoundError(k)
        rev, d = self.actual[k]
        return SimpleNamespace(key=k, value=self._json.dumps(d, ensure_ascii=False).encode(), revision=rev)

    async def create(self, k, v):
        if k in self.actual:
            raise self.KeyWrongLastSequenceError(k)
        return self._poner(k, v)

    async def update(self, k, v, last):
        if self.actual.get(k, (0, None))[0] != last:
            raise self.KeyWrongLastSequenceError(k)
        return self._poner(k, v)

    async def put(self, k, v):
        return self._poner(k, v)

    async def delete(self, k):
        self.actual.pop(k, None)

    def _poner(self, k, v) -> int:
        self.n += 1
        d = self._json.loads(v)
        self.actual[k] = (self.n, d)
        self.puestos.append((k, d))
        return self.n

    def valor(self, k) -> dict | None:
        return self.actual.get(k, (0, None))[1]
