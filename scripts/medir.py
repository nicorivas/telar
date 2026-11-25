#!/usr/bin/env python3
"""Comprobar la página de telar en un navegador de verdad: medir y fotografiar sus pantallas, rápido y sin colgarse.

    python3 scripts/medir.py todas -s .pantalla-barra -s .franja          el rectángulo de cada una, en todas
    python3 scripts/medir.py calendario proyectos -s .pantalla-barra -e height,padding-top
    python3 scripts/medir.py modo:foco hilo:Faro/conv --captura           y una captura PNG de cada pantalla
    python3 scripts/medir.py todas -s .franja --telefono --json           en un teléfono, en JSON
    python3 scripts/medir.py --lista                                       las pantallas que la página tiene hoy

Levanta la página con `scripts/dev.py` en un puerto libre propio (el código de esta copia, con los datos de verdad),
entra con la llave sin imprimirla, abre una sola sesión de agent-browser con nombre propio y recorre las pantallas
pedidas, en orden: el estado pasa de una a la otra (un modo puesto sigue puesto). En cada una espera lo justo (a que
la pantalla esté y la página se calme: nada cambia en el DOM y no hay pedidos en vuelo), y devuelve lo pedido. Al
terminar, pase lo que pase (un error, ⌃C, un tope), cierra el navegador y apaga la página; y lo que dejó una corrida
que murió sin poder limpiar (un `kill -9`), lo limpia la siguiente.

Las pantallas, por su nombre (sin tildes ni mayúsculas que importen):

    tactica estrategia foco todo     un modo (o modo:<clave>): el clic en la banda de modos
    calendario, te esperan…          una pestaña del dashboard por su nombre, su clave o su acción (o pestana:<x>);
                                     si el modo puesto no la muestra, pone «todo» primero
    pestanas                         todas las pestañas que tiene el dashboard (en el modo todo)
    config, config:<sección>         la configuración (el ⚙), en una sección (pestanas, modos, mundos…)
    hilo:<nombre>[/term|lectura|conv]  un hilo; sin vista, la conversación: la terminal se engancha a la ventana
                                     de tmux del hilo y le cambia el tamaño, así que solo si se pide
    arch:<ruta>                      un archivo en el visor (la ventana encima de lo que se mira)
    obj:<dirección>                  un objeto (tarea:T84, proyecto:…)
    dashboard                        volver al dashboard
    todas                            los modos, cada pestaña, config, un archivo (el README) y, si corre en un
                                     hilo (TELAR_HILO), su conversación; foco al final

En el dashboard nunca se teclea: las letras son atajos que encargan trabajo de verdad. Esto solo hace clics y JS.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEV = RAIZ / "scripts" / "dev.py"

#: los modos de fábrica (componentes/modos-mundos.ts, MODOS): la prueba revisa que sean los mismos
MODOS = ("tactica", "estrategia", "foco", "todo")
#: las pestañas de fábrica del dashboard, por su clave (vistas/dashboard/panel.ts, `todasLasPestanas`); las de los
#: bloques, los módulos y los proveedores se leen de la página
PESTANAS_DE_FABRICA = ("todo", "tactica", "ahora", "esperas", "revisar", "proyectos", "calendario")
#: las vistas de un hilo (web/vistas-hilo.ts, VISTAS)
VISTAS_HILO = ("term", "lectura", "conv")
#: la cookie de la llave (telar.api_web.COOKIE)
COOKIE = "telar_panel"
ESCRITORIO = (1440, 900)
TELEFONO = "iPhone 14"
#: cuánto tiempo sin cambios en el DOM ni pedidos en vuelo cuenta como «calma», y cuánto se espera la calma después de
#: que la pantalla está (una terminal o un reloj no se calman nunca: se mide igual, y lo dice)
CALMA_MS = 150
CALMA_TOPE_MS = 2500
PUERTOS = range(18800, 19000)


class Falla(Exception):
    """Algo de la corrida entera (la página no levantó, el navegador no contesta, el tope total): se limpia y se sale."""


class FallaPantalla(Exception):
    """Una pantalla que no se pudo mostrar: se dice y se sigue con la siguiente."""


# ── las pantallas ─────────────────────────────────────────────────────────────

def normal(texto: str) -> str:
    """Sin tildes, en minúsculas y sin espacios de sobra: «Táctica» es «tactica»."""
    t = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Pantalla:
    tipo: str  # modo, pestana, pestanas, config, hilo, arch, obj, dashboard
    valor: str = ""
    sub: str = ""  # la sección de config, la vista de un hilo

    @property
    def nombre(self) -> str:
        if self.tipo in ("dashboard", "pestanas") or (self.tipo == "config" and not self.sub):
            return self.tipo
        if self.tipo == "config":
            return f"config:{self.sub}"
        return f"{self.tipo}:{self.valor}" + (f"/{self.sub}" if self.sub else "")


def resolver(nombres: list[str], hilo_propio: str = "", raiz: Path = RAIZ) -> list[Pantalla]:
    """Los nombres de la línea de órdenes, en pantallas. Lo que no se reconoce es una pestaña: si la página no la
    tiene, lo dice al llegar ahí (las de los módulos y los proveedores solo las sabe la página)."""
    out: list[Pantalla] = []
    for crudo in nombres:
        n = crudo.strip()
        if not n:
            continue
        tipo, _, resto = n.partition(":")
        t = normal(tipo)
        if not _ or t not in ("modo", "pestana", "config", "hilo", "arch", "archivo", "obj"):
            t, resto = "", n
        if t == "" and normal(n) == "todas":
            out += todas(hilo_propio, raiz)
        elif t == "" and normal(n) in ("pestanas", "pestañas"):
            out += [Pantalla("modo", "todo"), Pantalla("pestanas")]
        elif t == "" and normal(n) == "dashboard":
            out.append(Pantalla("dashboard"))
        elif t == "modo" or (t == "" and normal(n) in MODOS):
            m = normal(resto)
            if m not in MODOS:
                raise ValueError(f"«{crudo}»: no es un modo (hay {', '.join(MODOS)})")
            out.append(Pantalla("modo", m))
        elif t == "config" or (t == "" and normal(n) == "config"):
            out.append(Pantalla("config", sub=normal(resto) if t else ""))
        elif t == "hilo":
            hilo, _, vista = resto.partition("/")
            vista = normal(vista) or "conv"
            if not hilo.strip():
                raise ValueError(f"«{crudo}»: falta el nombre del hilo (hilo:Faro)")
            if vista not in VISTAS_HILO:
                raise ValueError(f"«{crudo}»: la vista de un hilo es una de {', '.join(VISTAS_HILO)}")
            out.append(Pantalla("hilo", hilo.strip(), vista))
        elif t in ("arch", "archivo"):
            if not resto.strip():
                raise ValueError(f"«{crudo}»: falta la ruta (arch:README.md)")
            out.append(Pantalla("arch", str(Path(resto.strip()).expanduser().resolve())))
        elif t == "obj":
            if ":" not in resto:
                raise ValueError(f"«{crudo}»: una dirección es tipo:id (obj:tarea:T84)")
            out.append(Pantalla("obj", resto.strip()))
        else:
            out.append(Pantalla("pestana", resto.strip()))
    return out


def todas(hilo_propio: str = "", raiz: Path = RAIZ) -> list[Pantalla]:
    """Todas: los modos, cada pestaña (en el modo todo, que las muestra todas), config, un archivo, el hilo propio y
    foco al final (foco muestra lo último que se miró)."""
    out = [Pantalla("modo", "tactica"), Pantalla("modo", "estrategia"), Pantalla("modo", "todo"), Pantalla("pestanas"),
           Pantalla("config"), Pantalla("arch", str(raiz / "README.md"))]
    if hilo_propio:
        out.append(Pantalla("hilo", hilo_propio, "conv"))
    return out + [Pantalla("modo", "foco")]


# ── las opciones ──────────────────────────────────────────────────────────────

def ventana(texto: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d{3,5})\s*[x×]\s*(\d{3,5})\s*", texto)
    if not m:
        raise argparse.ArgumentTypeError(f"«{texto}»: un tamaño es ANCHOxALTO (1440x900)")
    return int(m[1]), int(m[2])


def segundos(texto: str) -> float:
    try:
        v = float(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"«{texto}»: en segundos (10, 2.5)") from None
    if v <= 0:
        raise argparse.ArgumentTypeError("tiene que ser más que 0")
    return v


def analizador() -> argparse.ArgumentParser:
    a = argparse.ArgumentParser(prog="medir", description=__doc__.splitlines()[0], epilog=__doc__.split("\n", 2)[2],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("pantallas", nargs="*", help="las pantallas, en orden (todas, tactica, calendario, hilo:Faro…)")
    a.add_argument("-s", "--selector", action="append", default=[], metavar="CSS",
                   help="medir esto (getBoundingClientRect); se repite")
    a.add_argument("-e", "--estilo", action="append", default=[], metavar="PROPS",
                   help="y sus estilos calculados: height,padding-top,--pantalla-barra-alto (una variable sola, con =: -e=--x); se repite")
    a.add_argument("--todos", action="store_true", help="todos los elementos que calzan (hasta 20), no solo el primero")
    a.add_argument("--captura", nargs="?", const="", default=None, metavar="CARPETA",
                   help="una captura PNG de cada pantalla (sin carpeta, una nueva en el temporal)")
    a.add_argument("--js", metavar="JS", help="correr esto en cada pantalla antes de medir (una promesa se espera "
                   "dejando su resultado en window, nunca colgada); su resultado sale en la salida")
    a.add_argument("--esperar", metavar="CSS", help="en cada pantalla, esperar además a que esto aparezca")
    tam = a.add_mutually_exclusive_group()
    tam.add_argument("--telefono", action="store_true", help=f"como un teléfono ({TELEFONO}: angosto y táctil)")
    tam.add_argument("--ventana", type=ventana, default=ESCRITORIO, metavar="ANCHOxALTO",
                     help=f"el tamaño de la ventana (de fábrica {ESCRITORIO[0]}x{ESCRITORIO[1]}, un laptop)")
    a.add_argument("--paso", type=segundos, default=10.0, metavar="S", help="tope de cada paso, en segundos (10)")
    a.add_argument("--total", type=segundos, default=90.0, metavar="S", help="tope de la corrida entera (90)")
    a.add_argument("--json", action="store_true", help="la salida en JSON")
    a.add_argument("--lista", action="store_true", help="las pantallas que tiene la página (los modos, las pestañas, "
                   "las secciones de config, las vistas de un hilo) y salir")
    a.add_argument("--url", help="medir una página que ya corre (http://ip:puerto), sin levantar otra")
    a.add_argument("--puerto", type=int, help="el puerto de la página que se levanta (de fábrica, uno libre entre "
                   f"{PUERTOS.start} y {PUERTOS.stop - 1})")
    return a


def analizar(argv: list[str]) -> argparse.Namespace:
    a = analizador()
    o = a.parse_args(argv)
    o.estilos = [p.strip() for e in o.estilo for p in e.split(",") if p.strip()]
    if not o.pantallas and not o.lista:
        a.error("¿qué pantallas? (todas, tactica, calendario, hilo:Faro…; --lista dice cuáles hay)")
    if not o.lista and not (o.selector or o.captura is not None or o.js):
        a.error("¿qué medir? -s <css> (y -e <estilos>), --captura o --js")
    try:
        o.recorrido = resolver(o.pantallas, os.environ.get("TELAR_HILO", ""))
    except ValueError as e:
        a.error(str(e))
    return o


# ── los procesos: la página y el navegador, y limpiarlos siempre ──────────────

def carpeta_estado() -> Path:
    return Path(tempfile.gettempdir()) / f"telar-medir-{os.getuid()}"


def vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def descendientes(pid: int) -> list[int]:
    """Los procesos que salen de este (hijos, nietos…), para apagarlos aunque su padre ya no esté."""
    out: list[int] = []
    pendientes = [pid]
    while pendientes:
        p = pendientes.pop()
        try:
            r = subprocess.run(["pgrep", "-P", str(p)], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        hijos = [int(x) for x in r.stdout.split() if x.strip().isdigit()]
        out += hijos
        pendientes += hijos
    return out


def matar(pids: list[int], espera: float = 5.0) -> None:
    """SIGTERM a cada uno (a su grupo si lo encabeza), y SIGKILL a los que sigan vivos después de `espera`."""
    for sen in (signal.SIGTERM, signal.SIGKILL):
        for p in pids:
            try:
                if os.getpgid(p) == p:
                    os.killpg(p, sen)
                else:
                    os.kill(p, sen)
            except (ProcessLookupError, PermissionError):
                pass
        hasta = time.monotonic() + espera
        while time.monotonic() < hasta and any(vivo(p) for p in pids):
            time.sleep(0.05)
        if not any(vivo(p) for p in pids):
            return


def dir_sesiones() -> Path:
    return Path(os.environ.get("AGENT_BROWSER_SOCKET_DIR") or Path.home() / ".agent-browser")


def cerrar_navegador(ab: str, sesion: str) -> None:
    """Cierra la sesión de agent-browser; si no contesta, mata su daemon y su navegador."""
    archivo = dir_sesiones() / f"{sesion}.pid"
    try:
        pid = int(archivo.read_text().strip())
    except (OSError, ValueError):
        pid = 0
    resto = [pid, *descendientes(pid)] if pid else []
    try:
        subprocess.run([ab, "--session", sesion, "close"], capture_output=True, timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    vivos = [p for p in resto if vivo(p)]
    if vivos:
        matar(vivos, 3)
    for sufijo in (".pid", ".sock"):
        try:
            if pid and not vivo(pid):
                (dir_sesiones() / f"{sesion}{sufijo}").unlink(missing_ok=True)
        except OSError:
            pass


def limpiar_restos(ab: str, carpeta: Path | None = None) -> list[str]:
    """Lo que dejó una corrida que murió sin limpiar (su página, su navegador): su archivo de estado lo dice."""
    carpeta = carpeta or carpeta_estado()
    limpiados = []
    for f in sorted(carpeta.glob("*.json")) if carpeta.is_dir() else []:
        try:
            e = json.loads(f.read_text())
            dueno = int(e.get("pid", 0))
        except (OSError, ValueError, TypeError):
            continue
        if dueno and vivo(dueno):
            continue
        if e.get("sesion"):
            cerrar_navegador(ab, e["sesion"])
        restos = [p for p in e.get("procesos", []) if isinstance(p, int) and vivo(p)]
        if restos:
            matar(restos, 3)
        f.unlink(missing_ok=True)
        limpiados.append(f.name)
    return limpiados


def puerto_libre(prefiere: int | None = None) -> int:
    def libre(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", p))
                return True
            except OSError:
                return False

    if prefiere:
        if not libre(prefiere):
            raise Falla(f"el puerto {prefiere} está ocupado")
        return prefiere
    inicio = PUERTOS.start + os.getpid() % len(PUERTOS)
    for i in range(len(PUERTOS)):
        p = PUERTOS.start + (inicio - PUERTOS.start + i) % len(PUERTOS)
        if libre(p):
            return p
    raise Falla(f"no hay un puerto libre entre {PUERTOS.start} y {PUERTOS.stop - 1}")


def llave() -> str:
    base = os.environ.get("XDG_CONFIG_HOME")
    ruta = (Path(base) if base else Path.home() / ".config") / "telar" / "panel.llave"
    try:
        return ruta.read_text(encoding="utf-8").strip()
    except OSError:
        raise Falla(f"no encuentro la llave de la página ({ruta}): ¿telar serve --web corrió alguna vez?") from None


class Pagina:
    """`scripts/dev.py` en su puerto: la página de esta copia, que se apaga con `apagar`."""

    def __init__(self, orden: list[str]):
        self.orden = orden
        self.proc: subprocess.Popen | None = None
        self.lineas: list[str] = []
        self.url = ""
        self.compilada = False
        self._cambio = threading.Condition()

    def arrancar(self) -> None:
        self.proc = subprocess.Popen(self.orden, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, text=True, start_new_session=True)
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self) -> None:
        assert self.proc and self.proc.stdout
        for linea in self.proc.stdout:
            with self._cambio:
                self.lineas.append(linea.rstrip("\n"))
                if (m := re.search(r"la página en (http://\S+)", linea)):
                    self.url = m[1]
                if "app.js y componentes.js" in linea and "error" not in linea:
                    self.compilada = True
                self._cambio.notify_all()
        with self._cambio:
            self._cambio.notify_all()

    def esperar(self, hasta: float) -> str:
        """Hasta que esbuild compiló y el servidor dijo su dirección, y la dirección contesta."""
        with self._cambio:
            while not (self.url and self.compilada):
                if self.proc and self.proc.poll() is not None:
                    raise Falla("la página no levantó:\n  " + "\n  ".join(self.lineas[-8:]))
                if time.monotonic() > hasta:
                    raise Falla("la página no levantó a tiempo:\n  " + "\n  ".join(self.lineas[-8:]))
                self._cambio.wait(0.2)
        while True:
            try:
                with urllib.request.urlopen(f"{self.url}/manifest.webmanifest", timeout=2) as r:
                    if r.status == 200:
                        return self.url
            except OSError:
                pass
            if self.proc and self.proc.poll() is not None:
                raise Falla("la página se cayó al arrancar:\n  " + "\n  ".join(self.lineas[-8:]))
            if time.monotonic() > hasta:
                raise Falla(f"{self.url} no contesta")
            time.sleep(0.1)

    def procesos(self) -> list[int]:
        return [self.proc.pid, *descendientes(self.proc.pid)] if self.proc else []

    def apagar(self) -> None:
        if not self.proc:
            return
        restos = self.procesos()
        if self.proc.poll() is None:
            try:
                os.kill(self.proc.pid, signal.SIGTERM)
                self.proc.wait(8)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
        vivos = [p for p in restos if vivo(p)]
        if vivos:
            matar(vivos, 3)
        try:
            self.proc.wait(1)
        except subprocess.TimeoutExpired:
            pass


class Navegador:
    """Una sesión de agent-browser con nombre propio. Cada orden con su tope; ninguna eval devuelve una promesa."""

    def __init__(self, ab: str, sesion: str, paso: float, hasta: float):
        self.ab, self.sesion, self.paso, self.hasta = ab, sesion, paso, hasta
        self.entorno = {**os.environ, "AGENT_BROWSER_DEFAULT_TIMEOUT": str(int(paso * 1000))}

    def orden(self, *args: str, entrada: str | None = None, tope: float | None = None) -> object:
        queda = self.hasta - time.monotonic()
        if queda <= 0:
            raise Falla("se acabó el tiempo total (--total)")
        tope = min(tope or self.paso + 3, queda)
        try:
            r = subprocess.run([self.ab, "--session", self.sesion, "--json", *args], input=entrada,
                               capture_output=True, text=True, timeout=tope, env=self.entorno,
                               stdin=None if entrada is not None else subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            if time.monotonic() >= self.hasta:
                raise Falla("se acabó el tiempo total (--total)") from None
            raise Falla(f"el navegador no contestó en {tope:.0f} s ({args[0]}): lo cierro") from None
        except FileNotFoundError:
            raise Falla(f"no encuentro {self.ab}: npm i -g agent-browser") from None
        try:
            datos = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        except ValueError:
            datos = {}
        if not datos.get("success"):
            error = datos.get("error") or (r.stderr or r.stdout).strip() or f"salió con {r.returncode}"
            raise FallaPantalla(str(error))
        return (datos.get("data") or {}).get("result", datos.get("data"))

    def js(self, codigo: str) -> object:
        return self.orden("eval", "--stdin", entrada=codigo)

    def esperar(self, condicion: str) -> None:
        self.orden("wait", "--fn", condicion)


# ── lo que corre en la página ─────────────────────────────────────────────────

#: lo que lleva la página para saber si está calmada: cuándo cambió el DOM por última vez y cuántos fetch van en
#: vuelo. Se pone solo desde cualquier condición (si la página se recargó, vuelve a ponerse)
PONER = """(() => { if (window.__medir) return window.__medir;
  const m = window.__medir = { mut: performance.now(), vuelo: 0, t0: performance.now(), listoEn: 0 };
  new MutationObserver(() => { m.mut = performance.now(); }).observe(document.documentElement,
      { subtree: true, childList: true, attributes: true, characterData: true });
  const f = window.fetch;
  window.fetch = function (...a) { m.vuelo++; const p = f.apply(this, a); p.then(() => { m.vuelo--; }, () => { m.vuelo--; }); return p; };
  return m; })()"""

AYUDAS = """
const norm = s => String(s ?? '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().trim();
const filas = () => [...document.querySelectorAll('[data-accion="dash"]')].map(a => {
  let id = []; try { id = JSON.parse(a.dataset.id || '[]'); } catch {}
  return { a, accion: id[0] || '', valor: id[1] || '', nombre: (a.title || a.textContent || '').split(' · ')[0].trim() }; });
const ALIAS = { revisar: 'foco', esperas: 'esperas' };
const fila = q => { const n = norm(q), alias = ALIAS[n];
  return filas().find(f => [f.nombre, f.accion, f.valor, `${f.accion}:${f.valor}`].some(x => norm(x) === n) || (alias && f.accion === alias && !f.valor)); };
const seccion = p => [...document.querySelectorAll('#vistas > [data-p]')].find(x => x.dataset.p === p);
const aLaVista = p => { const s = seccion(p); return !!s && !s.hidden; };
const modoBoton = m => document.querySelector(`#modos-fila [data-accion="modos-modo"][data-id="${m}"]`);
const hiloALaVista = h => [...document.querySelectorAll('#vistas > [data-p]')].some(x => !x.hidden && x.dataset.p.endsWith(':' + h));
const visorListo = () => !!document.querySelector('dialog.ventana-documento[open] .v-documento[data-listo]');
"""


def _js(cuerpo: str) -> str:
    """Una función síncrona que nunca lanza: lo que devuelve o {error}."""
    return f"(() => {{ {AYUDAS}\ntry {{ {cuerpo} }} catch (e) {{ return {{ error: String(e && e.message || e) }}; }} }})()"


def condicion(listo: str, esperar: str = "", calma: int = CALMA_MS, tope: int = CALMA_TOPE_MS) -> str:
    """Lo que `wait --fn` espera: que la pantalla esté (`listo`) y que la página se calme, o que pase `tope` desde que
    estuvo (una terminal no se calma nunca)."""
    extra = f" && !!document.querySelector({json.dumps(esperar)})" if esperar else ""
    return (f"(() => {{ const m = {PONER}; {AYUDAS}\nlet ok = false; try {{ ok = !!({listo}){extra}; }} catch (e) {{ ok = false; }}"
            f" if (!ok) {{ m.listoEn = 0; return false; }} const t = performance.now(); if (!m.listoEn) m.listoEn = t;"
            f" return (m.vuelo === 0 && t - m.mut > {calma}) || t - m.listoEn > {tope}; }})()")


def accion(codigo: str) -> str:
    """Hacer algo en la página (un clic, `mostrar`): síncrono, y marca desde cuándo se espera."""
    return _js(f"const m = {PONER}; m.t0 = performance.now(); m.listoEn = 0; m.mut = performance.now(); m.espera = null;\n{codigo}\nreturn {{ ok: true }};")


DASH_A_LA_VISTA = "aLaVista('dashboard')"


def pasos(p: Pantalla, telefono: bool, ventana: tuple[int, int]) -> list[tuple]:
    """Cómo se llega a una pantalla: una lista de ('js', acción, listo) y ('ab', *orden) (cambiar la ventana)."""
    j = json.dumps
    if p.tipo == "modo":
        listo = f"document.body.dataset.modo === {j(p.valor)} && modoBoton({j(p.valor)})?.classList.contains('si')"
        if p.valor != "foco":
            listo += f" && {DASH_A_LA_VISTA}"
        return [("js", f"const b = modoBoton({j(p.valor)}); if (!b) return {{ error: 'no está el botón del modo {p.valor}: el mundo puesto no lo tiene, o no existe' }}; b.click();",
                 listo)]
    if p.tipo == "pestana":
        n = j(p.valor)
        return [
            # si el modo puesto no la muestra, el modo todo (que las muestra todas)
            ("js", f"if (!fila({n}) && document.body.dataset.modo !== 'todo') modoBoton('todo')?.click();",
             f"!!fila({n}) || document.body.dataset.modo === 'todo'"),
            ("js", f"const f = fila({n}); if (!f) return {{ error: 'no hay una pestaña «' + {n} + '»: hay ' + filas().map(x => x.nombre).join(', ') }}; f.a.click();",
             f"fila({n})?.a.classList.contains('activa') && {DASH_A_LA_VISTA}"),
        ]
    if p.tipo == "config":
        out = [("js", "window.telar.mostrar('config');", f"!!document.querySelector('#dia .config') && {DASH_A_LA_VISTA}")]
        if p.sub:
            s = j(p.sub)
            out.append(("js", f"const a = [...document.querySelectorAll('.config-op')].find(x => norm(x.dataset.valor) === {s} || norm(x.textContent) === {s});"
                              f" if (!a) return {{ error: 'no hay una sección «' + {s} + '» en config: hay ' + [...document.querySelectorAll('.config-op')].map(x => x.dataset.valor).join(', ') }}; a.click();",
                        f"!![...document.querySelectorAll('.config-op.activa')].find(x => norm(x.dataset.valor) === {s} || norm(x.textContent) === {s})"))
        return out
    if p.tipo == "hilo":
        h, v = j(p.valor), p.sub
        ver = f"aLaVista({j(f'{v}:{p.valor}')})"
        clic = f"document.querySelector('#acciones [data-accion=\"vista\"][data-valor=\"{v}\"]')?.click();"
        if v != "term" and not telefono:
            # en un laptop, mostrar un hilo monta su terminal, que se engancha a la ventana de tmux y le cambia el
            # tamaño: angosta, la página abre su conversación; ahí se elige la vista (lectura y vuelta, para que la
            # recuerde) y se vuelve al ancho
            return [("ab", "set", "viewport", "390", str(ventana[1])),
                    ("js", "", "document.body.classList.contains('angosto')"),
                    ("js", f"window.telar.mostrar({h});", f"hiloALaVista({h})"),
                    ("js", "document.querySelector('#acciones [data-accion=\"vista\"][data-valor=\"lectura\"]')?.click();"
                           + (clic if v == "conv" else ""), ver),
                    ("ab", "set", "viewport", str(ventana[0]), str(ventana[1])),
                    ("js", "", f"!document.body.classList.contains('angosto') && {ver}")]
        return [("js", f"window.telar.mostrar({h});", f"hiloALaVista({h})"),
                ("js", clic, ver)]
    if p.tipo in ("arch", "obj"):
        d = j(f"{p.tipo}:{p.valor}")
        # un archivo se abre en el visor, una ventana encima de lo que se mira (web/carpeta.ts); un objeto puede abrirse en
        # su vista, en el dashboard (una tarea, una pestaña), en un hilo o en el visor: se espera la calma
        return [("js", f"window.telar.mostrar({d});", "visorListo()" if p.tipo == "arch" else "true")]
    if p.tipo == "dashboard":
        # (y cierra el visor, si quedó abierto)
        return [("js", "window.telar.mostrar('dashboard');", DASH_A_LA_VISTA)]
    raise ValueError(p.tipo)


LISTAR_PESTANAS = _js("return filas().map(f => ({ nombre: f.nombre, accion: f.accion, valor: f.valor }));")
LISTAR_CONFIG = _js("return [...document.querySelectorAll('.config-op')].map(x => ({ clave: x.dataset.valor, nombre: x.textContent.trim() }));")


def medir_js(selectores: list[str], estilos: list[str], todos: bool) -> str:
    return _js(f"""
const out = {{}};
for (const s of {json.dumps(selectores)}) {{
  let els; try {{ els = [...document.querySelectorAll(s)]; }} catch (e) {{ out[s] = {{ error: 'selector inválido' }}; continue; }}
  const r1 = x => Math.round(x * 10) / 10;
  const uno = el => {{
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el), est = {{}};
    for (const p of {json.dumps(estilos)}) est[p] = cs.getPropertyValue(p).trim();
    return {{ x: r1(r.x), y: r1(r.y), w: r1(r.width), h: r1(r.height),
      visible: el.checkVisibility ? el.checkVisibility({{ visibilityProperty: true }}) : r.width > 0 && r.height > 0, estilos: est }}; }};
  // los que se ven primero, en el orden del documento: el de una pantalla escondida (el dashboard detrás de un hilo) no es el que se busca
  const todos = els.map(uno), vistos = todos.filter(x => x.visible);
  out[s] = {{ cuantos: els.length, visibles: vistos.length, elementos: [...vistos, ...todos.filter(x => !x.visible)].slice(0, {20 if todos else 1}) }};
}}
const activa = filas().find(f => f.a.classList.contains('activa'));
const vista = [...document.querySelectorAll('#vistas > [data-p]')].find(x => !x.hidden)?.dataset.p || '';
const m = window.__medir || {{}}, t = performance.now();
const espera = m.espera || {{ listo_ms: m.listoEn && m.t0 ? Math.round(m.listoEn - m.t0) : null, calma: m.vuelo === 0 && t - m.mut > {CALMA_MS}, en_vuelo: m.vuelo ?? null }};
return {{ donde: {{ modo: document.body.dataset.modo || '', vista, pestana: vista === 'dashboard' ? (document.querySelector('#dia .config') ? 'config' : activa?.nombre || '') : '',
  ventana: [innerWidth, innerHeight] }}, medidas: out,
  espera }};""")


def js_usuario(codigo: str) -> str:
    """El --js de la persona, sin que nunca quede una eval colgada: si da una promesa, su resultado queda en window y
    se lee después."""
    return _js(f"""
// cómo se llegó a la pantalla, antes de que el --js la cambie
const m = window.__medir, t = performance.now();
if (m) m.espera = {{ listo_ms: m.listoEn && m.t0 ? Math.round(m.listoEn - m.t0) : null, calma: m.vuelo === 0 && t - m.mut > {CALMA_MS}, en_vuelo: m.vuelo }};
const r = (0, eval)({json.dumps(codigo)});
if (r && typeof r.then === 'function') {{
  const j = window.__medirJs = {{ hecho: false }};
  r.then(v => {{ j.hecho = true; j.valor = v; }}, e => {{ j.hecho = true; j.error = String(e && e.message || e); }});
  return {{ promesa: true }};
}}
return {{ valor: r === undefined ? null : r }};""")


# ── la corrida ────────────────────────────────────────────────────────────────

@dataclass
class Resultado:
    pantalla: str
    ok: bool = True
    error: str = ""
    segundos: float = 0.0
    donde: dict = field(default_factory=dict)
    medidas: dict = field(default_factory=dict)
    #: cuánto tardó en estar (ms desde la acción) y si la página se calmó antes de medir
    espera: dict = field(default_factory=dict)
    js: object = None
    captura: str = ""


class Corrida:
    def __init__(self, o: argparse.Namespace, ab: str = "agent-browser", dev: list[str] | None = None,
                 estado: Path | None = None):
        self.o, self.ab = o, ab
        self.dev = dev or [sys.executable, str(DEV)]
        self.estado = estado or carpeta_estado()
        self.sesion = f"medir-{os.getpid()}"
        self.hasta = time.monotonic() + o.total
        self.pagina: Pagina | None = None
        self.nav = Navegador(ab, self.sesion, o.paso, self.hasta)
        self.url = ""
        self.resultados: list[Resultado] = []
        self.capturas = ""
        self.lista: dict = {}

    # el archivo de estado: si esta corrida muere sin limpiar, la siguiente sabe qué apagar
    def _anotar(self) -> None:
        self.estado.mkdir(parents=True, exist_ok=True)
        procesos = self.pagina.procesos() if self.pagina else []
        (self.estado / f"{os.getpid()}.json").write_text(json.dumps({"pid": os.getpid(), "sesion": self.sesion, "procesos": procesos}))

    def correr(self) -> None:
        limpiar_restos(self.ab, self.estado)
        self._anotar()
        try:
            if self.o.url:
                self.url = self.o.url.rstrip("/")
            else:
                puerto = puerto_libre(self.o.puerto)
                self.pagina = Pagina([*self.dev, "--puerto", str(puerto)])
                self.pagina.arrancar()
                self._anotar()
                self.url = self.pagina.esperar(min(self.hasta, time.monotonic() + 45))
                self._anotar()
            self._entrar()
            if self.o.lista:
                self._listar()
                return
            if self.o.captura is not None:
                self.capturas = self.o.captura or str(self.estado / "capturas" / time.strftime("%Y%m%d-%H%M%S"))
                Path(self.capturas).mkdir(parents=True, exist_ok=True)
            for p in self.o.recorrido:
                if p.tipo == "pestanas":
                    for f in self._pestanas():
                        self._pantalla(Pantalla("pestana", f))
                else:
                    self._pantalla(p)
        finally:
            self.limpiar()

    def limpiar(self) -> None:
        # ni ⌃C ni un kill a medias de la limpieza
        viejas = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        try:
            cerrar_navegador(self.ab, self.sesion)
            if self.pagina:
                self.pagina.apagar()
            (self.estado / f"{os.getpid()}.json").unlink(missing_ok=True)
        finally:
            for s, v in viejas.items():
                signal.signal(s, v)

    def _entrar(self) -> None:
        nav = self.nav
        if self.o.telefono:
            nav.orden("set", "device", TELEFONO)
        else:
            nav.orden("set", "viewport", str(self.o.ventana[0]), str(self.o.ventana[1]))
        # la llave, sin que aparezca en ninguna parte: en una página que no la pide, la cookie por la entrada estándar
        nav.orden("open", f"{self.url}/manifest.webmanifest")
        nav.js(f"document.cookie = {json.dumps(f'{COOKIE}={llave()}; path=/')}; 1")
        nav.orden("open", f"{self.url}/")
        try:
            # solo que esté: la calma la espera cada pantalla antes de medir. El botón de un modo cualquiera: un mundo
            # puede no tener táctica (`[mundos.<n>] modos`). Las filas del dashboard, o «sin hilos» en la barra: una
            # máquina sin su sesión de tmux (una configuración de prueba) no las tiene, y la página igual cargó
            nav.esperar(condicion("!!document.querySelector('#modos-fila [data-accion=\"modos-modo\"]')"
                                  " && (filas().length > 0 || !!document.querySelector('#barra .nota'))", tope=0))
        except FallaPantalla as e:
            try:
                texto = nav.js("document.body.innerText.slice(0, 200)")
            except FallaPantalla:
                texto = ""
            raise Falla(f"la página no cargó ({_corto(e)}){': ' + str(texto) if texto else ''}") from None

    def _pestanas(self) -> list[str]:
        r = self.nav.js(LISTAR_PESTANAS)
        if isinstance(r, dict):
            raise Falla(f"no pude leer las pestañas: {r.get('error')}")
        vistas = {"todo", "tactica"}  # las vistas de los modos: ya se vieron como modo (estrategia abre en proyectos)
        nombres = [f["nombre"] for f in r]
        # por su nombre, que es como se ve; si dos se llaman igual, por su acción
        return [f["nombre"] if nombres.count(f["nombre"]) == 1 else (f"{f['accion']}:{f['valor']}" if f["valor"] else f["accion"])
                for f in r if not (f["accion"] in vistas and not f["valor"])]

    def _listar(self) -> None:
        self._pantalla(Pantalla("modo", "todo"), medir=False)
        pestanas = self.nav.js(LISTAR_PESTANAS)
        self._pantalla(Pantalla("config"), medir=False)
        config = self.nav.js(LISTAR_CONFIG)
        self.lista = {"modos": list(MODOS), "pestanas": pestanas if isinstance(pestanas, list) else [],
                      "config": config if isinstance(config, list) else [], "vistas_hilo": list(VISTAS_HILO)}

    def _pantalla(self, p: Pantalla, medir: bool = True) -> None:
        r = Resultado(p.nombre)
        t0 = time.monotonic()
        try:
            lista = pasos(p, self.o.telefono, self.o.ventana)
            for i, paso in enumerate(lista):
                if paso[0] == "ab":
                    self.nav.orden(*paso[1:])
                    continue
                _, hacer, listo = paso
                # aunque no haga nada, marca desde cuándo se espera: la calma se cuenta desde aquí
                h = self.nav.js(accion(hacer))
                if isinstance(h, dict) and h.get("error"):
                    raise FallaPantalla(h["error"])
                try:
                    # la calma, solo en el último: los de antes solo tienen que estar
                    ultimo = i == len(lista) - 1
                    self.nav.esperar(condicion(listo, self.o.esperar or "") if ultimo else condicion(listo, tope=0))
                except FallaPantalla as e:
                    raise FallaPantalla(f"no llegó ({_corto(e)})") from None
            if medir and self.o.js:
                h = self.nav.js(js_usuario(self.o.js))
                if isinstance(h, dict) and h.get("error"):
                    raise FallaPantalla(f"--js: {h['error']}")
                if isinstance(h, dict) and h.get("promesa"):
                    self.nav.esperar(condicion("window.__medirJs && window.__medirJs.hecho"))
                    h = self.nav.js("(() => { const j = window.__medirJs; return j.error ? { error: j.error } : { valor: j.valor ?? null }; })()")
                else:
                    self.nav.esperar(condicion("true"))
                if isinstance(h, dict) and h.get("error"):
                    r.js = {"error": h["error"]}
                else:
                    r.js = h.get("valor") if isinstance(h, dict) else h
            if medir:
                m = self.nav.js(medir_js(self.o.selector, self.o.estilos, self.o.todos))
                if isinstance(m, dict) and m.get("error"):
                    raise FallaPantalla(m["error"])
                r.donde, r.medidas, r.espera = m.get("donde", {}), m.get("medidas", {}), m.get("espera", {})
                if self.capturas:
                    r.captura = str(Path(self.capturas) / f"{len(self.resultados) + 1:02d}-{_archivo(p.nombre)}.png")
                    self.nav.orden("screenshot", r.captura)
        except FallaPantalla as e:
            r.ok, r.error = False, _corto(e)
        r.segundos = round(time.monotonic() - t0, 2)
        if medir:
            self.resultados.append(r)
        elif not r.ok:
            raise Falla(f"{p.nombre}: {r.error}")


def _corto(e: Exception) -> str:
    t = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return t.replace("page.waitForFunction: ", "").replace("page.evaluate: ", "")[:300]


def _archivo(nombre: str) -> str:
    return re.sub(r"[^\w.-]+", "-", normal(nombre)).strip("-")[:60] or "pantalla"


# ── la salida ─────────────────────────────────────────────────────────────────

def texto(c: Corrida, total: float, error: str = "") -> str:
    o = c.o
    tam = TELEFONO if o.telefono else f"{o.ventana[0]}×{o.ventana[1]}"
    lineas = []
    if c.lista:
        lineas.append("modos:     " + " ".join(c.lista["modos"]))
        lineas.append("pestañas:  " + ", ".join(f"{f['nombre']} ({f['accion']}{':' + f['valor'] if f['valor'] else ''})" for f in c.lista["pestanas"]))
        lineas.append("config:    " + " ".join(s["clave"] for s in c.lista["config"]))
        lineas.append("un hilo:   hilo:<nombre>/" + "|".join(c.lista["vistas_hilo"]))
    ancho = max([len(s) for s in o.selector] + [8])
    for r in c.resultados:
        cab = f"{r.pantalla}  {r.segundos:.1f} s"
        if r.donde:
            d = r.donde
            cab += f"  · {d.get('modo', '')}" + (f" · {d['pestana']}" if d.get("pestana") else f" · {d['vista']}" if d.get("vista") != "dashboard" else "")
        if not r.ok:
            lineas.append(f"✗ {cab}: {r.error}")
            continue
        if r.espera and r.espera.get("calma") is False:
            cab += "  (sin calma: algo sigue cambiando)"

        lineas.append(cab)
        for s, m in r.medidas.items():
            if m.get("error"):
                lineas.append(f"  {s:<{ancho}}  {m['error']}")
                continue
            if not m["elementos"]:
                lineas.append(f"  {s:<{ancho}}  — no está")
            for i, el in enumerate(m["elementos"]):
                pref = s if i == 0 else f"  [{i}]"
                rect = f"{el['x']:g},{el['y']:g} {el['w']:g}×{el['h']:g}"
                extra = "" if el["visible"] else "  (oculto)"
                est = "  " + " ".join(f"{k}={v}" for k, v in el["estilos"].items()) if el["estilos"] else ""
                mas = f"  (1 de {m['cuantos']}, {m.get('visibles', 0)} a la vista)" if i == 0 and m["cuantos"] > 1 and not o.todos else ""
                lineas.append(f"  {pref:<{ancho}}  {rect}{est}{extra}{mas}")
        if r.js is not None:
            lineas.append(f"  js: {json.dumps(r.js, ensure_ascii=False)[:300]}")
        if r.captura:
            lineas.append(f"  captura: {r.captura}")
    if c.lista and not c.resultados and not error:
        return "\n".join(lineas)
    malas = sum(not r.ok for r in c.resultados)
    pie = f"{c.url or '(sin página)'} · {tam} · {len(c.resultados)} pantallas en {total:.1f} s"
    if malas:
        pie += f" · {malas} sin llegar"
    lineas.append(pie)
    if error:
        lineas.append(f"medir: {error}")
    return "\n".join(lineas)


def salida_json(c: Corrida, total: float, error: str = "") -> str:
    return json.dumps({"url": c.url, "ventana": TELEFONO if c.o.telefono else list(c.o.ventana), "segundos": round(total, 2),
                       "error": error, "capturas": c.capturas, **({"lista": c.lista} if c.lista else {}),
                       "pantallas": [r.__dict__ for r in c.resultados]}, ensure_ascii=False, indent=1)


def main(argv: list[str] | None = None, *, ab: str = "agent-browser", dev: list[str] | None = None,
         estado: Path | None = None) -> int:
    o = analizar(sys.argv[1:] if argv is None else argv)
    inicio = time.monotonic()

    def salir(*_):
        raise KeyboardInterrupt

    viejas = {s: signal.signal(s, salir) for s in (signal.SIGTERM, signal.SIGHUP)}
    c = Corrida(o, ab=ab, dev=dev, estado=estado)
    error = ""
    try:
        c.correr()
    except (Falla, FallaPantalla) as e:
        # lo de una pantalla se ataja en ella: esto es entrar, listar o el navegador que no contesta
        error = _corto(e) if isinstance(e, FallaPantalla) else str(e)
    except KeyboardInterrupt:
        error = "interrumpido"
    finally:
        for s, v in viejas.items():
            signal.signal(s, v)
    total = time.monotonic() - inicio
    print(salida_json(c, total, error) if o.json else texto(c, total, error), flush=True)
    if error:
        return 3
    return 1 if any(not r.ok for r in c.resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
