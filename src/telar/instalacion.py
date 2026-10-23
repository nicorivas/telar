"""Lo que `telar instalar` escribe fuera de telar: el servicio de `telar serve` y un `[bus]` en la configuración.

Puro salvo `escribir_si_cambia`: arma el texto del servicio (systemd de usuario en Linux, launchd en macOS)
para esta máquina, con la ruta real de telar y un PATH que alcance a tmux y al agente. Las plantillas de
`servidor/` son el mismo texto, para quien lo instale a mano.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ETIQUETA = "com.telar.serve"
#: lo que tiene que ver un servicio para que telar, tmux y el agente corran (un servicio no hereda tu PATH)
PROGRAMAS = ("telar", "tmux", "claude", "git", "node", "tailscale")
BASICOS = ("/usr/local/bin", "/usr/bin", "/bin")


def ejecutable() -> str:
    """Con qué se llama a telar: el que está en el PATH, o el que corre ahora."""
    return shutil.which("telar") or str(Path(sys.argv[0]).resolve())


def ruta_path(buscar=shutil.which) -> str:
    """Las carpetas de los programas que telar necesita, en orden, sin repetir, más las de siempre."""
    carpetas: list[str] = []
    for prog in PROGRAMAS:
        r = buscar(prog)
        if r:
            carpetas.append(str(Path(r).parent))
    if sys.platform == "darwin":
        carpetas.append("/opt/homebrew/bin")
    carpetas += BASICOS
    return ":".join(dict.fromkeys(carpetas))


def argumentos(*, web: bool = True, nodo: bool = False, equipo: bool = False, web_puerto: int = 0) -> list[str]:
    a = ["serve"]
    if equipo:
        a.append("--equipo")
    if nodo:
        a.append("--nodo")
    if web:
        a.append("--web")
        if web_puerto:
            a += ["--web-puerto", str(web_puerto)]
    return a


def unidad_systemd(telar: str, args: list[str], path: str, *, esperar_tailscale: bool) -> str:
    espera = ""
    if esperar_tailscale:
        # la página escucha en la IP de Tailscale, que tarda unos segundos en existir al encender
        espera = ("ExecStartPre=/bin/sh -c 'for i in $(seq 1 60); do tailscale ip -4 >/dev/null 2>&1 && exit 0; "
                  "sleep 2; done; echo \"tailscale no tiene IP todavía\" >&2; exit 1'\n")
    return f"""\
# La escribió `telar instalar`; se puede volver a correr sin romper nada.
# Ver cómo va:  systemctl --user status telar-serve   ·   journalctl --user -u telar-serve -f

[Unit]
Description=telar serve: la API, la página y el nodo del bus de esta máquina
Documentation=https://github.com/nicorivas/telar
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=PATH={path}
Environment=PYTHONUNBUFFERED=1
{espera}ExecStart={telar} {" ".join(args)}
# al pararlo, solo el proceso principal: los hilos que abrió (el servidor tmux, si lo levantó él) viven en su grupo
KillMode=process
Restart=always
RestartSec=5
NoNewPrivileges=yes

[Install]
WantedBy=default.target
"""


def plist_launchd(telar: str, args: list[str], path: str, log: str) -> str:
    programa = "".join(f"<string>{escape(a)}</string>" for a in [telar, *args])
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!-- La escribió `telar instalar`; se puede volver a correr sin romper nada. Ver cómo va: tail -f {escape(log)} -->
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{ETIQUETA}</string>
  <key>ProgramArguments</key>
  <array>{programa}</array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>{escape(path)}</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
    <key>LANG</key><string>en_US.UTF-8</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{escape(log)}</string>
  <key>StandardErrorPath</key><string>{escape(log)}</string>
</dict>
</plist>
"""


def ruta_servicio() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{ETIQUETA}.plist"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "systemd" / "user" / "telar-serve.service"


def servicio(*, nodo: bool, equipo: bool, telar: str = "", path: str = "", web_puerto: int = 0) -> tuple[Path, str]:
    """(dónde, qué) del servicio de esta máquina. `web_puerto`: el de la página, si no es el de siempre (en un
    servidor que aloja a varias personas, cada una tiene el suyo)."""
    telar = telar or ejecutable()
    path = path or ruta_path()
    args = argumentos(nodo=nodo, equipo=equipo, web_puerto=web_puerto)
    if sys.platform == "darwin":
        log = str(Path.home() / "Library" / "Logs" / "telar-serve.log")
        return ruta_servicio(), plist_launchd(telar, args, path, log)
    return ruta_servicio(), unidad_systemd(telar, args, path, esperar_tailscale=bool(shutil.which("tailscale")))


def bloque_bus(url: str, token: str, persona: str = "", administra: str = "") -> str:
    lineas = ["", "# el bus entre tus máquinas (lo escribió `telar instalar --bus`)", "[bus]", f'url = "{url}"',
              f'token = "{token}"']
    if persona:
        lineas.append(f'persona = "{persona}"')
    if administra and administra != persona:
        lineas.append(f'administra = "{administra}"')
    return "\n".join(lineas) + "\n"


def escribir_si_cambia(ruta: Path, texto: str) -> bool:
    """Escribe si no existe o si cambió. True si escribió."""
    if ruta.exists() and ruta.read_text(encoding="utf-8") == texto:
        return False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, ruta)
    return True
