"""Lo que `telar desplegar` corre en cada máquina, la de aquí y las otras: mirar dónde vive un repositorio y cómo
está, reiniciar un servicio y comprobar la página de telar.

Se manda entero por la entrada estándar (`python3 - '<pedido en JSON>'`, por ssh en una máquina remota) y contesta una
línea de JSON. Solo con la biblioteca estándar y sin importar telar: corre con el python3 de la otra máquina, antes de
que su telar se ponga al día (y aunque esté roto). La orden y lo que se decide están en `telar.despliegue`.

    {"accion": "mirar", "candidatas": [...], "raices": [...], "servicios": [...], "buscar_en_config": true}
    {"accion": "reiniciar", "servicio": "telar-serve", "sistema": "systemd", "plazo": 20}
    {"accion": "comprobar", "pagina": "/pagina.json", "plazo": 30, "sigue": 15}
"""

from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time


def _correr(argv, cwd=None, timeout=60):
    try:
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)
    return r.returncode, r.stdout, r.stderr


def _git(carpeta, *args):
    codigo, salida, _ = _correr(["git", "-C", carpeta, *args])
    return salida.strip() if codigo == 0 else None


def _telar():
    """El telar de esta máquina, aunque ssh no traiga el PATH de una sesión (uv lo deja en ~/.local/bin)."""
    hay = shutil.which("telar")
    if hay:
        return hay
    local = os.path.expanduser("~/.local/bin/telar")
    return local if os.access(local, os.X_OK) else ""


def _de_la_config():
    """Dónde viven los repositorios según la configuración de telar de esta máquina: su raíz, sus `[repos]` y las
    carpetas de sus módulos. [] si no hay telar o no contesta."""
    telar = _telar()
    if not telar:
        return []
    codigo, salida, _ = _correr([telar, "config", "--json"], timeout=30)
    if codigo != 0:
        return []
    try:
        c = json.loads(salida)
    except ValueError:
        return []
    rutas = [c.get("raiz") or ""]
    rutas += [r.get("ruta") or "" for r in c.get("repos") or [] if isinstance(r, dict)]
    rutas += [m.get("carpeta") or "" for m in c.get("modulos") or [] if isinstance(m, dict)]
    return [r for r in rutas if r]


def sistema():
    """Con qué se cuidan los servicios aquí: launchd en macOS, systemd (de usuario) donde haya systemctl."""
    if sys.platform == "darwin":
        return "launchd"
    return "systemd" if shutil.which("systemctl") else ""


def _dominio():
    return f"gui/{os.getuid()}"


def instalado(nombre, sis):
    if not nombre:
        return False
    if sis == "systemd":
        return _correr(["systemctl", "--user", "cat", nombre])[0] == 0
    if sis == "launchd":
        return _correr(["launchctl", "print", f"{_dominio()}/{nombre}"])[0] == 0
    return False


def activo(nombre, sis):
    if sis == "systemd":
        codigo, salida, _ = _correr(["systemctl", "--user", "is-active", nombre])
        return codigo == 0 and salida.strip() == "active"
    codigo, salida, _ = _correr(["launchctl", "print", f"{_dominio()}/{nombre}"])
    return codigo == 0 and "state = running" in salida


def mirar(p):
    """Dónde vive aquí el repositorio de `raices` (sus primeros commits: el mismo repositorio, aunque esté en otra
    carpeta) y cómo está: su rama, su commit, lo sucio, lo que corre, y qué servicios de los declarados hay."""
    raices = set(p.get("raices") or [])
    vistas = []

    def buscar(candidatas):
        for c in candidatas:
            real = os.path.realpath(os.path.expanduser(c))
            if real in vistas:
                continue
            vistas.append(real)
            if not os.path.isdir(real):
                continue
            arriba = _git(real, "rev-parse", "--show-toplevel")
            if not arriba or os.path.realpath(arriba) != real:
                continue  # una carpeta de otro repositorio, no la raíz de uno
            if raices & set((_git(real, "rev-list", "--max-parents=0", "HEAD") or "").split()):
                return real
        return ""

    # lo que se deduce de aquí primero; lo que dice el telar de allá (más lento: arranca telar) si con eso no estaba
    ruta = buscar(p.get("candidatas") or [])
    if not ruta and p.get("buscar_en_config"):
        ruta = buscar(_de_la_config())
    sis = sistema()
    hay = []
    for s in p.get("servicios") or []:
        nombre = s.get(sis) or ""
        if instalado(nombre, sis):
            hay.append(nombre)
    r = {"ruta": ruta, "buscadas": vistas, "sistema": sis, "instalados": hay}
    if ruta:
        sucio = _git(ruta, "status", "--porcelain", "--untracked-files=no")
        r.update(rama=_git(ruta, "symbolic-ref", "--short", "-q", "HEAD") or "",
                 tiene=_git(ruta, "rev-parse", "HEAD") or "",
                 corre=_git(ruta, "rev-parse", "-q", "--verify", "refs/telar/desplegado^{commit}") or "",
                 sucio=[l for l in (sucio or "").splitlines() if l.strip()])
    return r


def _plazo(p, si_no):
    plazo = p.get("plazo")
    return float(si_no if plazo is None else plazo)


def _ventanas():
    """Cuántas ventanas de tmux hay (los hilos): reiniciar un servicio no puede llevarse ninguna."""
    codigo, salida, _ = _correr(["tmux", "list-windows", "-a", "-F", "#{window_id}"], timeout=10)
    return len(set(salida.split())) if codigo == 0 else 0


def reiniciar(p):
    nombre, sis, plazo = p["servicio"], p["sistema"], _plazo(p, 20)
    antes = _ventanas()
    if sis == "systemd":
        codigo, salida, error = _correr(["systemctl", "--user", "restart", nombre], timeout=120)
    elif sis == "launchd":
        codigo, salida, error = _correr(["launchctl", "kickstart", "-k", f"{_dominio()}/{nombre}"], timeout=120)
    else:
        return {"ok": False, "detalle": "no sé reiniciar servicios aquí (ni systemd ni launchd)"}
    if codigo != 0:
        return {"ok": False, "detalle": (error or salida or f"salió con {codigo}").strip()[-400:]}
    limite = time.monotonic() + plazo
    while not activo(nombre, sis):
        if time.monotonic() > limite:
            return {"ok": False, "detalle": f"no quedó corriendo en {plazo:g} s"}
        time.sleep(0.5)
    despues = _ventanas()
    # que tmux siga vivo con sus hilos: si se llevó todas sus ventanas, el reinicio mató a tmux. Una menos puede ser un
    # hilo que se cerró en esos segundos, y se dice sin detenerse
    if antes and not despues:
        return {"ok": False, "detalle": f"había {antes} ventanas de tmux y no queda ninguna: el reinicio se llevó tmux"}
    if despues < antes:
        return {"ok": True, "detalle": f"había {antes} ventanas de tmux y quedan {despues}"}
    return {"ok": True, "detalle": ""}


class _Unix(http.client.HTTPConnection):
    def __init__(self, ruta, timeout=5):
        super().__init__("telar", timeout=timeout)
        self._ruta = ruta

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._ruta)


def _base(variable, *resto):
    base = os.environ.get(variable)
    return os.path.join(base if base else os.path.expanduser(resto[0]), *resto[1:])


def _salud():
    """Lo que dice el `telar serve` de aquí por su socket (la API, sin llave)."""
    c = _Unix(_base("XDG_STATE_HOME", "~/.local/state", "telar", "serve", "telar.sock"))
    try:
        c.request("GET", "/salud")
        r = c.getresponse()
        cuerpo = r.read()
    finally:
        c.close()
    if r.status != 200:
        raise OSError(f"/salud contestó {r.status}")
    return json.loads(cuerpo)


def _pagina(ruta):
    """GET de `ruta` en la página de telar de esta máquina, con su llave. (estado HTTP, cuerpo, problema)."""
    try:
        web = (_salud().get("web") or "").rstrip("/")
    except (OSError, ValueError) as e:
        return 0, b"", f"el telar serve de aquí no contesta por su socket ({e})"
    if not web:
        return 0, b"", "el telar serve de aquí no dice dónde está su página (sin --web, o es anterior a `telar desplegar`)"
    try:
        with open(_base("XDG_CONFIG_HOME", "~/.config", "telar", "panel.llave"), encoding="utf-8") as f:
            llave = f.read().strip()
    except OSError:
        return 0, b"", "no hay llave de la página aquí (~/.config/telar/panel.llave)"
    from urllib.parse import urlsplit

    u = urlsplit(web)
    c = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=5)
    try:
        c.request("GET", ruta, headers={"Cookie": f"telar_panel={llave}"})
        r = c.getresponse()
        return r.status, r.read(), ""
    except OSError as e:
        return 0, b"", f"{web} no contesta ({e})"
    finally:
        c.close()


def comprobar(p):
    """Que la página de telar de aquí conteste `pagina` con 200, hasta `plazo` segundos (el servicio puede estar
    arrancando), y con `sigue`, que a esos segundos de contestar conteste de nuevo: uno que arranca y se cae a los pocos
    segundos pasaba la primera. Devuelve lo que contestó, si es JSON, para comparar entre máquinas. La llave nunca sale
    de aquí."""
    ruta, plazo = p["pagina"], _plazo(p, 30)
    sigue = float(p.get("sigue") or 0)
    limite = time.monotonic() + plazo
    while True:
        estado, cuerpo, problema = _pagina(ruta)
        if estado == 200:
            try:
                valor = json.loads(cuerpo)
            except ValueError:
                valor = None
            if sigue > 0:
                time.sleep(sigue)
                estado, _, problema = _pagina(ruta)
                if estado != 200:
                    problema = problema or f"{ruta} contestó {estado}"
                    return {"ok": False, "valor": None,
                            "detalle": f"contestó, pero a los {sigue:g} s ya no: {problema}"}
            return {"ok": True, "valor": valor, "detalle": ""}
        if not problema:
            problema = f"{ruta} contestó {estado}" + (" (no aceptó la llave de aquí)" if estado == 403 else "")
        if time.monotonic() > limite:
            return {"ok": False, "valor": None, "detalle": problema}
        time.sleep(1)


ACCIONES = {"mirar": mirar, "reiniciar": reiniciar, "comprobar": comprobar}


def main(argv):
    try:
        pedido = json.loads(argv[1])
        respuesta = ACCIONES[pedido["accion"]](pedido)
    except Exception as e:  # noqa: BLE001 - lo que sea, en una línea que telar entienda
        respuesta = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    # en una línea propia: lo que un perfil de shell imprima antes no la ensucia
    sys.stdout.write("\n" + json.dumps(respuesta) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
