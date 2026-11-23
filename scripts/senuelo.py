#!/usr/bin/env python3
"""Correr las pruebas con todo apuntando a un señuelo, y ver que el señuelo quede intacto.

    python3 scripts/senuelo.py                         la suite entera, con pytest
    python3 scripts/senuelo.py --unittest              con `unittest discover`, como el CI
    python3 scripts/senuelo.py pruebas/test_vistas.py  solo esas (lo que sigue va a pytest)

Es la prueba de la red de seguridad de las pruebas (`pruebas/comun.py`, `aislar_sesion`): que ninguna, ni una nueva
que se olvide de aislarse, alcance lo vivo de quien las corre. Se arma lo que tendría un hilo de verdad, pero de
mentira: dos servidores de tmux con sus ventanas, uno al que apunta `TMUX` (con `TMUX_PANE` en la ventana del hilo y
`TELAR_HILO=Señuelo`) y otro, el de siempre de `TMUX_TMPDIR`; y la configuración, el estado, los módulos, la caché y
el hogar de telar en carpetas con algo adentro (`XDG_*`, `TELAR_CONFIG`, `TELAR_ESTADO`, `HOME`). Se corren las
pruebas con ese entorno y, al final, cada servidor tiene que seguir vivo (el mismo proceso) con las mismas sesiones,
ventanas y paneles, y cada carpeta con los mismos archivos y el mismo contenido. Si algo cambió, lo dice y sale con 1.

Nunca toca el tmux de quien lo corre: los dos señuelos se nombran con su socket (`-S`), y las pruebas corren sin el
`TMUX` de afuera. Tarda lo que la suite (minuto y medio en un MacBook Air M2).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HILO = "Señuelo"
FORMATO = "#{session_name} #{window_id} #{window_index} #{window_name} #{pane_id} #{pane_pid} #{pane_dead}"


#: Lo que corre en cada panel de un señuelo: algo quieto, que no lee la configuración de nadie ni escribe nada.
QUIETO = "sleep 864000"


def tmux(socket: Path, *args: str) -> str:
    """Un comando a un señuelo: siempre con su socket, y sin el `TMUX` de quien corre esto."""
    sin = {k: v for k, v in os.environ.items() if not k.startswith("TMUX")}
    return subprocess.run(["tmux", "-S", str(socket), *args], capture_output=True, text=True, check=True,
                          env=sin).stdout


def levantar(socket: Path, sesion: str, ventanas: list[str]) -> None:
    tmux(socket, "new-session", "-d", "-s", sesion, "-n", ventanas[0], "-x", "120", "-y", "30", QUIETO)
    for nombre in ventanas[1:]:
        tmux(socket, "new-window", "-d", "-t", sesion, "-n", nombre, QUIETO)


def foto_tmux(socket: Path) -> dict:
    """Lo que no puede cambiar de un señuelo: su proceso, sus sesiones, ventanas y paneles, y su entorno global."""
    try:
        return {"pid": tmux(socket, "display-message", "-p", "#{pid}").strip(),
                "paneles": sorted(tmux(socket, "list-panes", "-a", "-F", FORMATO).splitlines()),
                "entorno": sorted(tmux(socket, "show-environment", "-g").splitlines())}
    except subprocess.CalledProcessError as e:
        return {"muerto": (e.stderr or "").strip()}


def foto_carpeta(carpeta: Path) -> dict:
    return {str(p.relative_to(carpeta)): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "carpeta"
            for p in sorted(carpeta.rglob("*"))}


def sembrar(base: Path) -> dict[str, Path]:
    """Las carpetas de mentira de la persona, con lo que tendrían."""
    c = {nombre: base / nombre for nombre in ("config", "estado", "datos", "cache", "casa", "claude")}
    for carpeta in c.values():
        carpeta.mkdir(parents=True)
    (c["config"] / "telar").mkdir()
    (c["config"] / "telar" / "config.toml").write_text('sesion = "senuelo"\nraiz = "~/senuelo"\n', encoding="utf-8")
    (c["estado"] / "telar").mkdir()
    (c["estado"] / "telar" / "commits.log").write_text('{"mensaje": "del señuelo"}\n', encoding="utf-8")
    (c["estado"] / "telar" / "concesiones.json").write_text('{"gantt": {"fecha": {"decision": "concedido"}}}\n',
                                                              encoding="utf-8")
    (c["datos"] / "telar").mkdir()
    (c["cache"] / "telar").mkdir()
    (c["cache"] / "telar" / "gws-cuenta.json").write_text('{"conectado": true}\n', encoding="utf-8")
    (c["casa"] / ".bash_history").write_text("echo del señuelo\n", encoding="utf-8")
    (c["casa"] / ".gitconfig").write_text("[user]\n\tname = Señuelo\n\temail = senuelo@example.com\n",
                                          encoding="utf-8")
    (c["claude"] / "settings.json").write_text("{}\n", encoding="utf-8")
    return c


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--unittest", action="store_true", help="correr con `unittest discover -s pruebas`, como el CI")
    p.add_argument("pytest", nargs=argparse.REMAINDER, help="lo que va a pytest (por defecto, pruebas)")
    a = p.parse_args()
    if not shutil.which("tmux"):
        print("senuelo: sin tmux no hay señuelo", file=sys.stderr)
        return 2

    base = Path(tempfile.mkdtemp(prefix="senuelo-")).resolve()
    sock_a = base / "a.sock"                                    # al que apunta TMUX
    tmpdir_b = base / "b"                                       # el de siempre de TMUX_TMPDIR
    (tmpdir_b / f"tmux-{os.getuid()}").mkdir(parents=True, mode=0o700)
    sock_b = tmpdir_b / f"tmux-{os.getuid()}" / "default"
    try:
        levantar(sock_a, "telar", ["uno", HILO, "tres"])
        levantar(sock_b, "otra", ["uno", HILO])
        pid_a = tmux(sock_a, "display-message", "-p", "#{pid}").strip()
        panel = tmux(sock_a, "display-message", "-p", "-t", f"telar:{HILO}", "#{pane_id}").strip()
        carpetas = sembrar(base)
        entorno = {k: v for k, v in os.environ.items()
                   if not k.startswith(("TMUX", "TELAR_")) or k == "TELAR_NATS_SERVER"}
        entorno.update(
            TMUX=f"{sock_a},{pid_a},0", TMUX_PANE=panel, TMUX_TMPDIR=str(tmpdir_b), TELAR_HILO=HILO,
            XDG_CONFIG_HOME=str(carpetas["config"]), XDG_STATE_HOME=str(carpetas["estado"]),
            XDG_DATA_HOME=str(carpetas["datos"]), XDG_CACHE_HOME=str(carpetas["cache"]), HOME=str(carpetas["casa"]),
            TELAR_CONFIG=str(carpetas["config"] / "telar" / "config.toml"),
            TELAR_ESTADO=str(carpetas["estado"] / "telar"), CLAUDE_CONFIG_DIR=str(carpetas["claude"]),
            PYTHONPATH=os.pathsep.join(filter(None, [str(RAIZ / "src"), os.environ.get("PYTHONPATH", "")])),
        )
        antes = {"tmux TMUX": foto_tmux(sock_a), "tmux TMUX_TMPDIR": foto_tmux(sock_b),
                 **{f"carpeta {n}": foto_carpeta(c) for n, c in carpetas.items()}}

        orden = ([sys.executable, "-m", "unittest", "discover", "-s", "pruebas"] if a.unittest else
                 [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *(a.pytest or ["pruebas"])])
        print(f"senuelo: TMUX → {sock_a} (panel {panel}, hilo {HILO}), TMUX_TMPDIR → {tmpdir_b}", flush=True)
        corrida = subprocess.run(orden, cwd=RAIZ, env=entorno)

        despues = {"tmux TMUX": foto_tmux(sock_a), "tmux TMUX_TMPDIR": foto_tmux(sock_b),
                   **{f"carpeta {n}": foto_carpeta(c) for n, c in carpetas.items()}}
        cambios = [que for que in antes if antes[que] != despues[que]]
        for que in cambios:
            print(f"senuelo: cambió {que}", file=sys.stderr)
            a_, d_ = antes[que], despues[que]
            for clave in sorted(set(a_) | set(d_)):
                if a_.get(clave) != d_.get(clave):
                    print(f"  {clave}: {a_.get(clave)!r} → {d_.get(clave)!r}", file=sys.stderr)
        if not cambios:
            print("senuelo: los dos servidores de tmux y las carpetas de la persona quedaron intactos")
        if corrida.returncode:
            print(f"senuelo: las pruebas fallaron ({corrida.returncode})", file=sys.stderr)
        return 1 if cambios or corrida.returncode else 0
    finally:
        for socket in (sock_a, sock_b):
            subprocess.run(["tmux", "-S", str(socket), "kill-server"], capture_output=True)
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
