"""`telar panel` — la barra de hilos, el dashboard y las terminales, en un navegador.

    telar panel                          en esta máquina: http://127.0.0.1:8770
    telar panel --puerto N --host IP
    telar panel --tailscale              en la IP de Tailscale de esta máquina (para el celular, otra máquina)
    telar panel --verificar              dice si está todo para correrlo, y no lo corre

Es el servidor de `vscode/src/web/servidor.ts` (Node): el mismo dashboard y la misma barra que en
VS Code, con las terminales de los hilos al lado. Se entra con una llave, que imprime al arrancar
(`?k=…` la primera vez; después queda en una cookie) y vive en `~/.config/telar/panel.llave`.

Necesita Node 20+ y el panel compilado, en la carpeta `vscode/` del repositorio de telar:

    cd vscode && npm ci && npm run compile

Con `--tailscale` espera hasta un par de minutos a que la interfaz tenga IP (al encender, tarda): sin
eso, caería a otra dirección sin avisar. Quien alcance el puerto y tenga la llave puede escribirle a
tus agentes: por eso escucha en una sola dirección, nunca en todas.

Para que arranque solo: `servidor/telar-panel.service` (systemd) y `servidor/telar-panel.plist` (launchd).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from telar.ordenes import _comun

AYUDA = "La barra de hilos, el dashboard y las terminales, en un navegador."
PUERTO = 8770


def carpeta() -> Path:
    """Dónde está el panel: `$TELAR_PANEL_DIR`, o `vscode/` junto al código de telar (un clon)."""
    if os.environ.get("TELAR_PANEL_DIR"):
        return Path(os.environ["TELAR_PANEL_DIR"]).expanduser()
    return Path(__file__).resolve().parents[3] / "vscode"


def faltas(base: Path) -> list[str]:
    """Lo que falta para correr el panel, cada cosa con cómo arreglarla."""
    if not base.is_dir():
        return [f"no está la carpeta del panel ({base}): telar panel corre desde un clon del repositorio,"
                " o con $TELAR_PANEL_DIR apuntando a su carpeta vscode/"]
    falta = []
    if not shutil.which("node"):
        falta.append("falta node (20 o más)")
    if not (base / "node_modules").is_dir():
        falta.append(f"faltan sus dependencias: cd {base} && npm ci")
    if not (base / "out" / "web" / "servidor.js").is_file():
        falta.append(f"falta compilarlo: cd {base} && npm run compile")
    return falta


def ip_tailscale(espera: float) -> str:
    """La IP de Tailscale de esta máquina, esperando hasta `espera` segundos a que exista."""
    fin = time.monotonic() + espera
    while True:
        try:
            r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=10)
            ip = r.stdout.split()[0] if r.returncode == 0 and r.stdout.split() else ""
        except (OSError, subprocess.TimeoutExpired):
            ip = ""
        if ip or time.monotonic() >= fin:
            return ip
        time.sleep(2)


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("panel", AYUDA)
    p.epilog = __doc__
    p.add_argument("--puerto", type=int, default=PUERTO, help=f"el puerto (por defecto, {PUERTO})")
    donde = p.add_mutually_exclusive_group()
    donde.add_argument("--host", default="", help="la dirección donde escucha (por defecto, 127.0.0.1)")
    donde.add_argument("--tailscale", action="store_true", help="escuchar en la IP de Tailscale de esta máquina")
    p.add_argument("--esperar", type=float, default=120.0, help="con --tailscale, cuánto esperar su IP (segundos)")
    p.add_argument("--verificar", action="store_true", help="decir si está todo para correrlo, sin correrlo")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    base = carpeta()
    falta = faltas(base)
    if o.host in ("0.0.0.0", "::"):
        return _comun.queja("el panel escucha en una sola dirección: la de esta máquina o la de Tailscale")
    host = o.host or "127.0.0.1"
    if o.tailscale:
        host = ip_tailscale(o.esperar)
        if not host:
            falta.append("tailscale no tiene IP (¿está conectado?)")
    if o.verificar:
        for f in falta:
            print(f"✗ {f}")
        if not falta:
            print(f"✓ listo: node {base / 'out/web/servidor.js'} --puerto {o.puerto} --host {host}")
        return 1 if falta else 0
    if falta:
        return _comun.queja("no puedo abrir el panel:\n  " + "\n  ".join(falta))
    os.chdir(base)
    # el proceso pasa a ser el de node: un servicio ve sus caídas y sus señales sin Python en medio
    os.execvp("node", ["node", "out/web/servidor.js", "--puerto", str(o.puerto), "--host", host])
    return 0  # no se llega
