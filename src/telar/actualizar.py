"""Versiones nuevas de telar: saber si hay una y, con un clic en la página, instalarla y reiniciar.

    ver(config, forzar)       qué versión corre, cuál es la última en PyPI y si esta instalación se actualiza sola
    empezar(config, version)  instalarla en un proceso aparte, y reiniciar el servicio
    progreso(config)          en qué va eso

La última versión se le pregunta a PyPI a lo más cada `CADA` segundos (se guarda en `<estado>/version-pypi.json`);
`forzar` pregunta ya. Solo se actualiza sola una instalación de `uv tool install` (la de quien instala desde
PyPI): una desde el repositorio (`pip install -e`, la de quien desarrolla telar) se actualiza con `git pull`, y
la página no ofrece nada.

Actualizar corre aparte porque el servicio no se puede reiniciar a sí mismo desde adentro: instala esa versión
exacta (`uv tool install --force --refresh 'telar[serve,bus]==X'`), corre `telar instalar --si` con la nueva (que
reinicia el servicio porque corre otra versión que la instalada) y anota cómo le fue en
`<estado>/actualizar.json`, con lo que dijo en `<estado>/actualizar.log`. En Linux se lanza fuera del grupo del
servicio (`systemd-run --user`): reiniciarlo no lo corta a medio camino.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from telar import __version__

PYPI = "https://pypi.org/pypi/telar/json"
#: cada cuánto se le pregunta a PyPI por la última versión, si nadie fuerza (segundos)
CADA = 3600
#: una versión como las de telar (sin letras: nada de prerelease)
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
#: los extras con que se reinstala
EXTRAS = "serve,bus"


class ErrorDeActualizar(Exception):
    """Lo que no se puede: el mensaje es para la persona."""


def _tupla(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


def como_instalado() -> str:
    """«uv»: un `uv tool install` (se actualiza solo); «repo»: instalado desde el repositorio, editable (con git
    pull); «otro»: pip u otra cosa (a mano)."""
    try:
        from importlib.metadata import distribution

        directo = json.loads(distribution("telar").read_text("direct_url.json") or "{}")
        if (directo.get("dir_info") or {}).get("editable"):
            return "repo"
    except Exception:  # noqa: BLE001 - sin metadatos: se mira el camino
        pass
    partes = Path(sys.prefix).parts
    if "uv" in partes and "tools" in partes:
        return "uv"
    return "otro"


def _cache(config) -> Path:
    return Path(config.estado) / "version-pypi.json"


def ultima(config, *, forzar: bool = False, ahora: float | None = None, leer=None) -> dict:
    """{version, consultado} de la última en PyPI, de la caché si es reciente. `error` si no se pudo preguntar."""
    ahora = ahora if ahora is not None else time.time()
    ruta = _cache(config)
    try:
        guardada = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardada = {}
    if not forzar and guardada.get("version") and ahora - float(guardada.get("consultado", 0)) < CADA:
        return guardada
    try:
        datos = (leer or _leer_pypi)()
        version = str(datos["info"]["version"])
        if not VERSION.match(version):
            raise ValueError(f"PyPI dice «{version}»")
    except Exception as e:  # noqa: BLE001 - sin red o PyPI raro: queda lo que había, con el motivo
        return {**guardada, "error": f"no pude preguntarle a PyPI: {type(e).__name__}: {e}"[:200]}
    nueva = {"version": version, "consultado": ahora}
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(nueva), encoding="utf-8")
    except OSError:
        pass
    return nueva


def _leer_pypi() -> dict:
    pedido = urllib.request.Request(PYPI, headers={"Accept": "application/json", "Cache-Control": "no-cache",
                                                   "User-Agent": f"telar/{__version__}"})
    with urllib.request.urlopen(pedido, timeout=8) as r:  # noqa: S310 - una dirección fija, https
        return json.loads(r.read())


def ver(config, *, forzar: bool = False, leer=None) -> dict:
    """Lo que la página necesita: `corre`, `ultima`, `hay_nueva`, `como` (uv, repo, otro), `puede` (si el clic la
    instala), `consultado` y, si lo hay, `error`; y `progreso`, si hay una actualización en curso."""
    u = ultima(config, forzar=forzar, leer=leer)
    como = como_instalado()
    hay = bool(u.get("version")) and _tupla(u["version"]) > _tupla(__version__)
    salida = {"corre": __version__, "ultima": u.get("version", ""), "hay_nueva": hay, "como": como,
              "puede": hay and como == "uv" and bool(_uv()), "consultado": u.get("consultado"),
              "notas": f"https://github.com/nicorivas/telar/releases/tag/v{u['version']}" if u.get("version") else ""}
    if u.get("error"):
        salida["error"] = u["error"]
    if como == "repo" and hay:
        salida["a_mano"] = "instalado desde el repositorio: git pull y reiniciar el servicio"
    elif como == "otro" and hay:
        salida["a_mano"] = f"pip install --upgrade 'telar[{EXTRAS}]' y reiniciar el servicio"
    p = progreso(config)
    if p:
        salida["progreso"] = p
    return salida


def _uv() -> str:
    """El uv de esta máquina: el del PATH, o donde suele quedar (el servicio corre con un PATH corto)."""
    for c in (shutil.which("uv"), Path.home() / ".local" / "bin" / "uv", Path.home() / ".cargo" / "bin" / "uv",
              Path("/opt/homebrew/bin/uv"), Path("/usr/local/bin/uv")):
        if c and Path(c).exists():
            return str(c)
    return ""


def _estado_actualizar(config) -> Path:
    return Path(config.estado) / "actualizar.json"


def progreso(config) -> dict:
    """{version, estado: corriendo|listo|fallo, desde, hasta, error, log} de la última actualización; {} si nunca."""
    try:
        p = json.loads(_estado_actualizar(config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if p.get("estado") == "corriendo" and p.get("version") == __version__:
        # el servicio ya corre la nueva: el proceso de afuera pudo morir al reiniciarlo sin anotar «listo»
        p["estado"] = "listo"
    try:
        log = (Path(config.estado) / "actualizar.log").read_text(encoding="utf-8", errors="replace")
        p["log"] = "\n".join(log.strip().splitlines()[-12:])
    except OSError:
        pass
    return p


#: el proceso de afuera: instala, corre `telar instalar --si` con la nueva y anota cómo le fue
GUION = r'''
set -u
estado="$1"; version="$2"; uv="$3"; log="$4"
desde=$(date +%s)
anotar() { printf '{"version": "%s", "estado": "%s", "desde": %s, "hasta": %s, "error": "%s"}\n' \
  "$version" "$1" "$desde" "$(date +%s)" "$2" > "$estado.tmp" && mv "$estado.tmp" "$estado"; }
echo "== $(date) telar $version"
sleep 1
if ! "$uv" tool install --force --refresh "telar[serve,bus]==$version"; then
  anotar fallo "uv no pudo instalar la $version (ver el registro)"; exit 1
fi
bin=$("$uv" tool dir --bin 2>/dev/null)/telar
[ -x "$bin" ] || bin=$(command -v telar)
echo "== telar instalar --si ($bin)"
if ! "$bin" instalar --si; then
  anotar fallo "telar instalar no terminó bien (ver el registro)"; exit 1
fi
anotar listo ""
'''


def empezar(config, version: str) -> dict:
    """Lanza la actualización a `version` (que tiene que ser la última que se conoce, y más nueva que la que
    corre). Devuelve el progreso recién anotado."""
    if not VERSION.match(version or ""):
        raise ErrorDeActualizar(f"«{version}» no es una versión")
    if como_instalado() != "uv":
        raise ErrorDeActualizar("esta instalación no se actualiza desde la página: "
                                + ("es del repositorio (git pull)" if como_instalado() == "repo" else "no es de uv tool"))
    u = ultima(config)
    if version != u.get("version") or _tupla(version) <= _tupla(__version__):
        raise ErrorDeActualizar(f"la {version} no es la última nueva (corre la {__version__}, la última es "
                                f"{u.get('version') or '?'})")
    p = progreso(config)
    if p.get("estado") == "corriendo" and time.time() - float(p.get("desde", 0)) < 600:
        raise ErrorDeActualizar(f"ya se está instalando la {p.get('version')}")
    uv = _uv()
    if not uv:
        raise ErrorDeActualizar("no encuentro uv en esta máquina")
    estado, log = _estado_actualizar(config), Path(config.estado) / "actualizar.log"
    estado.parent.mkdir(parents=True, exist_ok=True)
    ahora = int(time.time())
    estado.write_text(json.dumps({"version": version, "estado": "corriendo", "desde": ahora}), encoding="utf-8")
    orden = ["/bin/sh", "-c", GUION, "telar-actualizar", str(estado), version, uv, str(log)]
    if sys.platform != "darwin" and shutil.which("systemd-run"):
        # fuera del grupo de telar-serve: reiniciar el servicio mataría a quien lo reinicia
        orden = ["systemd-run", "--user", "--collect", "--quiet", f"--unit=telar-actualizar-{ahora}",
                 "-p", f"StandardOutput=append:{log}", "-p", f"StandardError=append:{log}", *orden]
        subprocess.run(orden, check=True, timeout=20, env={**os.environ})
    else:
        with log.open("a", encoding="utf-8") as salida:
            subprocess.Popen(orden, stdin=subprocess.DEVNULL, stdout=salida, stderr=salida,
                             start_new_session=True, env={**os.environ, "PATH": _path()})
    return progreso(config)


def _path() -> str:
    from telar import instalacion

    return instalacion.ruta_path()
