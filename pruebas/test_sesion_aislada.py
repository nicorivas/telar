"""La red de seguridad de la suite: dentro de las pruebas no queda nada que apunte a lo vivo de quien las corre.

Cada hilo corre las pruebas desde su panel, con `TMUX`, `TMUX_PANE` y `TELAR_HILO` de verdad, y con la configuración y
el estado de telar de la persona donde siempre. `comun.aislar_sesion` los saca del proceso antes de que se importe
una sola prueba (`conftest.py` con pytest; la primera que importa `comun` con `unittest`). Estas pruebas no se aíslan
solas (son `unittest.TestCase`, no `Prueba`) para ver lo que ve una prueba que se olvidó de aislarse.

Que la suite entera no toque un servidor de tmux ajeno ni un estado ajeno, con todo apuntando a ellos al empezar, lo
prueba `scripts/senuelo.py` (corre la suite contra un señuelo y mira que quede igual). Aquí también el turno de la suite
completa (`comun.turno`) y lo que `conftest.py` entiende por suite completa.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

import comun
from comun import RAIZ

from telar import config as mod_config
from telar import modulos
from telar.proveedores import calendario
from telar.servicios import config as servicios_config

#: El hogar de verdad de quien corre las pruebas, de su cuenta y no de `HOME` (que la sesión cambió).
HOGAR_REAL = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()


def dentro(ruta, carpeta) -> bool:
    return Path(ruta).resolve().is_relative_to(Path(carpeta).resolve())


class SesionAislada(unittest.TestCase):
    def test_sin_marcas_de_lo_vivo(self):
        """Ni el servidor de tmux ni el panel ni el hilo de quien las corre; ninguna `TELAR_*` suya."""
        for clave in ("TMUX", "TMUX_PANE", "TELAR_HILO", "TELAR_CONFIG", "TELAR_ESTADO", "CLAUDE_CONFIG_DIR",
                      "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "ZELLIJ"):
            self.assertNotIn(clave, os.environ)
        sobran = [k for k in os.environ if k.startswith("TELAR_") and k not in comun.DE_LAS_PRUEBAS]
        self.assertEqual(sobran, [])

    def test_lo_que_lanza_una_prueba_tampoco_las_ve(self):
        r = subprocess.run([sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
                           capture_output=True, text=True, check=True)
        hijo = json.loads(r.stdout)
        self.assertNotIn("TMUX", hijo)
        self.assertNotIn("TELAR_HILO", hijo)
        self.assertTrue(dentro(hijo["HOME"], comun.SESION))
        self.assertTrue(dentro(hijo["TMUX_TMPDIR"], comun.SESION))

    def test_estado_y_configuracion_en_la_sesion(self):
        """Lo que telar lee y escribe de la persona cuando nadie dice otra cosa cae en la carpeta temporal de la sesión,
        nunca en `~/.config/telar`, `~/.local/state/telar`, `~/.local/share/telar` ni `~/.cache/telar` de verdad."""
        self.assertIsNotNone(comun.SESION)
        self.assertFalse(dentro(comun.SESION, HOGAR_REAL))
        rutas = {
            "HOME": Path.home(),
            "TMUX_TMPDIR": os.environ["TMUX_TMPDIR"],
            "la configuración": mod_config.ruta_config(),
            "el estado": mod_config._estado_por_defecto(),
            "el estado de la configuración cargada": mod_config.cargar().estado,
            "el socket de serve": mod_config.socket_serve(),
            "los módulos instalados": modulos._datos(),
            "la caché de los servicios": servicios_config._carpeta_cache(),
            "la caché del calendario": calendario._carpeta_cache(),
            **{v: os.environ[v] for v in comun.XDG},
        }
        for que, ruta in rutas.items():
            with self.subTest(que):
                self.assertTrue(dentro(ruta, comun.SESION), f"{que}: {ruta}")
                self.assertFalse(dentro(ruta, HOGAR_REAL), f"{que}: {ruta}")

    @unittest.skipUnless(shutil.which("tmux"), "sin tmux")
    def test_tmux_sin_S_va_al_servidor_de_la_sesion(self):
        """Una prueba que llama a `tmux` a secas, sin `-S` ni `TMUX_TMPDIR` propio, cae en el servidor de la sesión."""
        nombre = f"aislada-{uuid.uuid4().hex[:6]}"
        subprocess.run(["tmux", "new-session", "-d", "-s", nombre, "-x", "80", "-y", "24"], check=True,
                       capture_output=True)
        socket = subprocess.run(["tmux", "display-message", "-p", "-t", nombre, "#{socket_path}"],
                                capture_output=True, text=True, check=True).stdout.strip()
        # se cierra lo suyo, con el socket explícito: nunca un `tmux` a secas para matar algo
        self.addCleanup(subprocess.run, ["tmux", "-S", socket, "kill-session", "-t", nombre], capture_output=True)
        self.assertTrue(dentro(socket, Path(os.environ["TMUX_TMPDIR"])), socket)
        self.assertTrue(dentro(socket, comun.SESION), socket)

    def test_cada_prueba_importa_comun(self):
        """Con `unittest`, la red se tiende cuando una prueba importa `comun`: que lo haga cada una (o lo traiga de otra
        prueba que lo importa), para que correr un archivo solo también quede aislado."""
        importa = re.compile(r"^\s*(import comun\b|from comun import|from pruebas import comun\b|from test_\w+ import)", re.M)
        sin = [p.name for p in sorted((RAIZ / "pruebas").glob("test_*.py")) if not importa.search(p.read_text("utf-8"))]
        self.assertEqual(sin, [])

    def test_una_prueba_que_se_salta_en_su_setUp_no_deja_el_entorno_cambiado(self):
        """`Prueba` vuelve el entorno aunque la prueba se salte en su `setUp` (antes dejaba `XDG_CONFIG_HOME` apuntando
        a `pruebas/no-existe` para todas las que venían después)."""
        antes = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "TELAR_NATS_SERVER")}

        class SeSalta(comun.Prueba):
            def setUp(self):
                super().setUp()
                self.skipTest("adrede")

            def test_nada(self):
                pass

        resultado = unittest.TestResult()
        SeSalta("test_nada").run(resultado)
        self.assertEqual(len(resultado.skipped), 1)
        self.assertEqual({k: os.environ.get(k) for k in antes}, antes)

    def test_cada_proceso_de_xdist_tiene_su_carpeta_dentro_de_la_sesion(self):
        """Un proceso de pytest-xdist (`PYTEST_XDIST_WORKER`) que hereda la sesión del que reparte se arma la suya
        adentro: su estado, su hogar y su tmux, aparte de los de los otros procesos."""
        raiz = comun.SESION if comun.SESION.name.startswith(comun.PREFIJO) else comun.SESION.parent
        trabajador = f"gw-prueba-{uuid.uuid4().hex[:6]}"
        self.addCleanup(shutil.rmtree, raiz / trabajador, True)
        programa = ("import json, os, sys; sys.path.insert(0, sys.argv[1]); import comun; "
                    "print(json.dumps({'sesion': str(comun.SESION), **{k: os.environ.get(k) for k in "
                    "('HOME', 'TMUX_TMPDIR', 'XDG_STATE_HOME', 'TMUX', 'TELAR_HILO')}}))")
        entorno = {**os.environ, comun.MARCA: str(raiz), "PYTEST_XDIST_WORKER": trabajador,
                   "TMUX": "/tmp/no/va,1,0", "TELAR_HILO": "Otro"}
        r = subprocess.run([sys.executable, "-c", programa, str(RAIZ / "pruebas")], env=entorno, capture_output=True,
                           text=True, check=True)
        visto = json.loads(r.stdout)
        self.assertEqual(Path(visto["sesion"]), raiz / trabajador)
        for clave in ("HOME", "TMUX_TMPDIR", "XDG_STATE_HOME"):
            self.assertTrue(dentro(visto[clave], raiz / trabajador), f"{clave}: {visto[clave]}")
        self.assertIsNone(visto["TMUX"])
        self.assertIsNone(visto["TELAR_HILO"])


class Turno(unittest.TestCase):
    """Como mucho dos suites completas a la vez: la tercera espera, dice a quién, y entra cuando una termina."""

    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.carpeta, True)

    def test_la_tercera_espera_y_entra_cuando_se_suelta_una(self):
        primera = comun.turno(carpeta=self.carpeta)
        segunda = comun.turno(carpeta=self.carpeta)
        self.assertIsNotNone(primera)
        self.assertIsNotNone(segunda)
        dicho, tercera = [], []
        hilo = threading.Thread(target=lambda: tercera.append(comun.turno(dicho.append, carpeta=self.carpeta,
                                                                          cada=0.02)))
        hilo.start()
        time.sleep(0.2)
        self.assertEqual(tercera, [], "con dos adentro, la tercera espera")
        self.assertEqual(len(dicho), 1)
        self.assertIn("ya corren 2 suites completas", dicho[0])
        self.assertIn(f"pid {os.getpid()}", dicho[0], "y dice quiénes las tienen")
        os.close(primera)
        hilo.join(5)
        self.assertFalse(hilo.is_alive())
        self.assertIsNotNone(tercera[0])
        self.assertIn("me tocó", dicho[-1])
        os.close(segunda)
        os.close(tercera[0])

    def test_sin_donde_tomar_turnos_no_espera(self):
        self.assertIsNone(comun.turno(carpeta=self.carpeta / "no-existe"))


@unittest.skipUnless(importlib.util.find_spec("pytest"), "sin pytest")
class SuiteCompleta(unittest.TestCase):
    """Lo que `conftest.py` reparte en procesos y pone en turno: la carpeta `pruebas` o la raíz, no unos archivos."""

    def test_que_es_la_suite_completa(self):
        import conftest

        def es(*args, desde=RAIZ):
            return conftest.suite_completa(SimpleNamespace(invocation_params=SimpleNamespace(dir=desde), args=args))

        self.assertTrue(es("pruebas"))
        self.assertTrue(es(str(RAIZ)))
        self.assertTrue(es(".", desde=RAIZ / "pruebas"))
        self.assertFalse(es("pruebas/test_cli.py"))
        self.assertFalse(es("pruebas/test_cli.py::Cli::test_ayuda"))
        self.assertFalse(es("test_cli.py", desde=RAIZ / "pruebas"))


if __name__ == "__main__":
    unittest.main()
