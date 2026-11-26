"""Con pytest: la sesión aislada de lo vivo de quien la corre, la suite completa en paralelo y con turno.

- **Aislada.** pytest lee este archivo antes de juntar las pruebas, e importar `comun` basta: al importarse quita
  `TMUX`, `TMUX_PANE`, `TELAR_HILO` y las demás marcas, y deja el hogar, la configuración, el estado y el servidor de
  tmux en una carpeta temporal de la sesión (`comun.aislar_sesion`), y lo que telar lee de la máquina (`/etc/telar`,
  `/run/telar`), en una carpeta de ella que no existe (`comun.aislar_maquina`). Con `unittest`, lo mismo pasa cuando la primera
  prueba importa `comun`. Con pytest-xdist, cada proceso que corre pruebas lo lee también, y tiene su carpeta.
- **En paralelo.** La suite completa (`pytest pruebas`, o sin nada desde la raíz) corre en `PROCESOS` procesos con
  `--dist loadscope` si está pytest-xdist (el extra `pruebas`): cada archivo o clase entero en un proceso, que las de
  tmux de verdad (`test_mux_tmux_real`) necesitan su clase junta (repartidas de a una, fallaban). `-n` manda (`-n 0`,
  en uno). Un archivo suelto corre en uno: repartirlo cuesta más de lo que ahorra.
- **Con turno.** Como mucho `comun.TURNOS` suites completas a la vez en la máquina (`comun.turno`); la siguiente
  espera, y dice a quién.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

import pytest

import comun

#: Con cuántos procesos corre la suite completa, si está pytest-xdist. Medido el 18-nov-2026 en un MacBook Air M2:
#: 71 s en uno, 24,6 s con 4 y 19,3 s con `-n auto` (8 procesos, el doble de carga para la máquina que comparten los
#: hilos).
PROCESOS = 4

_turno: int | None = None


def suite_completa(config: pytest.Config) -> bool:
    """¿Se pidió la suite entera (la carpeta `pruebas` o la raíz), y no unos archivos o pruebas sueltos?"""
    desde = Path(config.invocation_params.dir)
    return any((desde / str(a).split("::")[0]).resolve() in (comun.RAIZ, comun.RAIZ / "pruebas") for a in config.args)


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config: pytest.Config) -> None:
    if hasattr(config, "workerinput") or not config.pluginmanager.hasplugin("xdist"):
        return
    if config.option.numprocesses is None and not config.getoption("usepdb", False) and suite_completa(config):
        config.option.numprocesses = PROCESOS
        config.option.tx = ["popen"] * PROCESOS  # lo de xdist, por si su gancho ya pasó
        if config.option.dist == "no":
            config.option.dist = "loadscope"


def pytest_report_header(config: pytest.Config) -> list[str]:
    if not suite_completa(config):
        return []
    if not config.pluginmanager.hasplugin("xdist"):
        return ["telar: sin pytest-xdist, la suite corre en un proceso (pip install -e '.[pruebas]' la reparte en "
                f"{PROCESOS})"]
    n = config.option.numprocesses
    return [f"telar: la suite, en {n} procesos (--dist {config.option.dist})" if n else "telar: la suite, en un proceso"]


def pytest_configure(config: pytest.Config) -> None:
    """El turno, en el proceso que reparte (no en cada uno de los de xdist) y antes de que arranquen."""
    global _turno
    if hasattr(config, "workerinput") or config.option.collectonly or not suite_completa(config):
        return
    capturas = config.pluginmanager.getplugin("capturemanager")

    def avisar(texto: str) -> None:
        with capturas.global_and_fixture_disabled() if capturas else contextlib.nullcontext():
            print(texto, file=sys.stderr, flush=True)

    _turno = comun.turno(avisar)


def pytest_unconfigure(config: pytest.Config) -> None:
    global _turno
    if _turno is not None:
        os.close(_turno)
        _turno = None
