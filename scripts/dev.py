#!/usr/bin/env python3
"""Desarrollar la página de telar viendo los cambios al tiro, sin desplegar.

    python3 scripts/dev.py                   en http://<ip de tailscale>:18780, con tu llave de siempre
    python3 scripts/dev.py --puerto 18790

Corre dos cosas hasta ⌃C:

- `npm run navegador:watch` (en pagina/): esbuild rehace src/telar/web/app.js y marco.css con cada cambio
  en el TypeScript o el CSS, en menos de un segundo;
- un `telar serve --web --dev` aparte, en su propio puerto y su propio socket (el `serve` de siempre, con el
  bus y el nodo, no se toca), que se reinicia cuando cambia un .py de src/telar.

La página (con --dev) se recarga sola cuando cambian sus archivos y cuando el servidor vuelve de reiniciarse.
Usa la configuración y los datos de verdad: lo que se aprieta ahí, pasa. Solo cambia el código.

Necesita telar instalado en modo editable (`uv tool install --editable .`): así `telar` corre el código del
repositorio. Para llevarlo al servidor cuando esté listo: servidor/desplegar.sh.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "src" / "telar"


def firma() -> dict[Path, int]:
    """La fecha de cada .py de src/telar: si cambia una, el servidor se reinicia."""
    return {p: p.stat().st_mtime_ns for p in FUENTE.rglob("*.py") if "__pycache__" not in p.parts}


def arrancar(puerto: int, socket: Path) -> subprocess.Popen:
    telar = shutil.which("telar") or "telar"
    return subprocess.Popen([telar, "serve", "--socket", str(socket), "--web", "--web-puerto", str(puerto), "--dev"],
                            start_new_session=True)


def parar(p: subprocess.Popen | None) -> None:
    if p is None or p.poll() is not None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--puerto", type=int, default=18780, help="el de la página de desarrollo (el de siempre es 8780)")
    o = a.parse_args()
    if not shutil.which("npm"):
        print("dev: falta npm (Node), para empaquetar la página", file=sys.stderr)
        return 1
    # en una carpeta propia: `telar serve` la deja solo para su dueño
    socket = Path(tempfile.gettempdir()) / f"telar-dev-{os.getuid()}" / "telar.sock"

    # ⌃C, cerrar la terminal o un kill: igual se apagan los dos (corren en su propio grupo, no se enteran solos)
    def salir(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, salir)
    signal.signal(signal.SIGHUP, salir)
    esbuild = subprocess.Popen(["npm", "run", "-s", "navegador:watch"], cwd=RAIZ / "pagina", start_new_session=True)
    servidor = arrancar(o.puerto, socket)
    antes = firma()
    try:
        while True:
            time.sleep(0.5)
            if esbuild.poll() is not None:
                print("dev: esbuild terminó; salgo", file=sys.stderr)
                return 1
            ahora = firma()
            if ahora != antes:
                cambiados = sorted(str(p.relative_to(RAIZ)) for p in ahora.keys() | antes.keys() if ahora.get(p) != antes.get(p))
                antes = ahora
                print(f"{time.strftime('%H:%M:%S')} cambió {', '.join(cambiados[:3])}{'…' if len(cambiados) > 3 else ''}: reinicio el servidor", flush=True)
                parar(servidor)
                servidor = arrancar(o.puerto, socket)
            elif servidor.poll() is not None:
                # se cayó solo (un error al importar, típicamente): se reintenta con el próximo cambio
                time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        parar(servidor)
        parar(esbuild)


if __name__ == "__main__":
    sys.exit(main())
