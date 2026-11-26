"""Lo que un proceso que telar arranca no hereda de quien se lo pidió (`telar.entorno`).

El caso real (18-nov-2026): el servidor de tmux del laptop se había levantado desde la Bash de un Claude Code y tenía
en su entorno global las marcas de esa sesión (`CLAUDECODE`, `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, el
socket de sus mensajes…). Cada hilo que se abría después las heredaba, y su Claude Code se creía hijo de una sesión ya
muerta: «Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker», y telar no podía leer el hilo.

Las pruebas contra tmux de verdad corren en un servidor propio (`TMUX_TMPDIR` temporal, sin `TMUX`): no ven ni tocan el
de la persona.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba, matar_tmux, socket_tmux  # noqa: E402  (pone src/ en el camino)

from telar import entorno, movil
from telar import periodicos as mod_periodicos
from telar.agente import lanzar
from telar.config import Config
from telar.mux import ErrorDeMux, tmux

#: lo que una sesión de Claude Code le deja a lo que lanza (los valores, inventados)
MARCAS = {
    "CLAUDECODE": "1",
    "CLAUDE_CODE_CHILD_SESSION": "1",
    "CLAUDE_CODE_SESSION_ID": "d98c79ae-0000-4000-8000-000000000000",
    "CLAUDE_CODE_MESSAGING_SOCKET": "/tmp/cc-socks/1.sock",
    "CLAUDE_CODE_MESSAGING_TOKEN": "secreto",
    "CLAUDE_CODE_CHILD_NOTES_DIR": "/tmp/notas",
    "CLAUDE_CODE_SESSION_ATTENDED": "1",
    "CLAUDE_CODE_ENTRYPOINT": "cli",
    "CLAUDE_CODE_EXECPATH": "/x/claude/versions/2.1.327",
    "CLAUDE_CODE_PLUGIN_DIRS": "/x/telar/mod",
    "CLAUDE_PID": "18387",
    "CLAUDE_EFFORT": "xhigh",
    "AI_AGENT": "claude-code_2-1-327_agent",
    "ZELLIJ_PANE_ID": "3",
    "GIT_EDITOR": "true",
}

#: el hilo de quien pidió: cada agente recibe el suyo; heredado, un panel suelto se cree ese otro hilo
DEL_HILO = {"TELAR_HILO": "Entorno"}

#: lo que la persona pone a propósito: pasa
CONFIGURACION = {
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "CLAUDE_CONFIG_DIR": "/x/.claude",
    "ANTHROPIC_API_KEY": "sk-falsa",
}


def _nombres(texto: str) -> set[str]:
    """Los nombres de un volcado de `env` o de `show-environment`."""
    return {r.split("=", 1)[0] for r in texto.splitlines() if "=" in r}


class LoQueSeHereda(Prueba):
    def test_las_marcas_de_la_sesion_no(self):
        for nombre, valor in MARCAS.items():
            with self.subTest(nombre=nombre):
                self.assertFalse(entorno.heredable(nombre, valor))

    def test_otro_identificador_de_sesion_tampoco(self):
        # los que traiga una versión nueva de Claude Code, por la forma del nombre
        for nombre in ("CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_RUNNER_SESSION_UUID",
                       "CLAUDE_SESSION_ID"):
            with self.subTest(nombre=nombre):
                self.assertFalse(entorno.heredable(nombre, "x"))

    def test_la_configuracion_de_la_persona_si(self):
        for nombre, valor in {**CONFIGURACION, "PATH": "/usr/bin", "HOME": "/x", "TELAR_CONFIG": "/x/t.toml"}.items():
            with self.subTest(nombre=nombre):
                self.assertTrue(entorno.heredable(nombre, valor))

    def test_el_hilo_de_quien_pidio_tampoco(self):
        self.assertFalse(entorno.heredable("TELAR_HILO", "Entorno"))

    def test_el_editor_de_git_solo_si_es_el_de_claude_code(self):
        self.assertFalse(entorno.heredable("GIT_EDITOR", "true"))
        self.assertTrue(entorno.heredable("GIT_EDITOR", "nvim"))

    def test_sin_marcas_deja_lo_demas_tal_cual(self):
        self.assertEqual(entorno.sin_marcas({**MARCAS, **CONFIGURACION}), CONFIGURACION)


class ElEntornoConQueSeAbre(Prueba):
    """Lo que telar le pasa a tmux al abrir (y al levantar su servidor) y a la terminal de la página."""

    def test_entorno_limpio_y_para_abrir_van_sin_marcas(self):
        with mock.patch.dict(os.environ, {**MARCAS, **CONFIGURACION}), \
                mock.patch.object(tmux, "path_de_la_persona", return_value="/casa/bin"):
            limpio, para_abrir = tmux.entorno_limpio(), tmux.entorno_para_abrir()
        for env in (limpio, para_abrir):
            self.assertFalse(set(MARCAS) & set(env), sorted(set(MARCAS) & set(env)))
            for nombre, valor in CONFIGURACION.items():
                self.assertEqual(env[nombre], valor)
        self.assertTrue(para_abrir["PATH"].startswith("/casa/bin:"))

    def test_las_ordenes_de_movil_van_sin_marcas(self):
        # `movil.crear` (periódicos, encargos) levanta el servidor si no está: con este entorno
        hecho = SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.dict(os.environ, MARCAS), mock.patch("subprocess.run", return_value=hecho) as run:
            movil._tmux("new-session", "-d", "-s", "x")
        self.assertFalse(set(MARCAS) & set(run.call_args.kwargs["env"]))

    def test_un_periodico_corre_sin_marcas(self):
        # `telar periodicos ahora` desde la Bash de un Claude Code: el comando no hereda esa sesión
        with tempfile.TemporaryDirectory() as d:
            ctx = SimpleNamespace(config=Config(raiz=Path(d), estado=Path(d) / "estado"))
            with mock.patch.dict(os.environ, {**MARCAS, **DEL_HILO, **CONFIGURACION}):
                self.assertFalse((set(MARCAS) | set(DEL_HILO)) & set(mod_periodicos._entorno()))
                r = mod_periodicos.correr(ctx, mod_periodicos.Proceso(nombre="env", cuando="* * * * *", comando="env"))
            self.assertEqual(r["codigo"], 0)
            vistas = _nombres(mod_periodicos.log(ctx.config, "env", lineas=500))
        self.assertFalse((set(MARCAS) | set(DEL_HILO)) & vistas, sorted((set(MARCAS) | set(DEL_HILO)) & vistas))
        self.assertLessEqual(set(CONFIGURACION), vistas)


class ElAgente(Prueba):
    """La línea que arranca al agente las borra igual: el último resguardo, si el servidor de tmux vino sucio."""

    def _correr(self, entorno_de_afuera: dict) -> set[str]:
        comando = lanzar.envolver(["env"], "faro")
        linea = comando[2].replace('exec "${SHELL:-/bin/sh}" -l', "true")
        hecho = subprocess.run(["sh", "-c", linea], capture_output=True, text=True, timeout=5,
                               env={**os.environ, **entorno_de_afuera})
        return _nombres(hecho.stdout)

    def test_el_agente_no_ve_las_marcas_y_si_la_configuracion(self):
        vistas = self._correr({**MARCAS, **CONFIGURACION})
        self.assertFalse(set(MARCAS) & vistas, sorted(set(MARCAS) & vistas))
        self.assertLessEqual(set(CONFIGURACION) | {"TELAR_HILO"}, vistas)

    def test_un_editor_de_git_de_la_persona_queda(self):
        self.assertIn("GIT_EDITOR", self._correr({"GIT_EDITOR": "nvim"}))

    def _valor(self, nombre: str, entorno_de_afuera: dict) -> str | None:
        comando = lanzar.envolver(["env"], "faro")
        linea = comando[2].replace('exec "${SHELL:-/bin/sh}" -l', "true")
        afuera = {k: v for k, v in os.environ.items() if k != nombre}
        hecho = subprocess.run(["sh", "-c", linea], capture_output=True, text=True, timeout=5,
                               env={**afuera, **entorno_de_afuera})
        return next((l.split("=", 1)[1] for l in hecho.stdout.splitlines() if l.startswith(f"{nombre}=")), None)

    def test_el_agente_escribe_los_enlaces_con_la_direccion_a_la_vista(self):
        # sin esto, Claude Code esconde la dirección de un enlace en un OSC 8, que mosh bota (entorno.DEL_AGENTE)
        self.assertEqual(self._valor("FORCE_HYPERLINK", {}), "0")

    def test_si_la_persona_puso_los_hipervinculos_manda_la_suya(self):
        self.assertEqual(self._valor("FORCE_HYPERLINK", {"FORCE_HYPERLINK": "1"}), "1")


class _TmuxQueAnota(tmux.Tmux):
    """Un tmux de mentira con un entorno global enlatado: anota lo que se le pide."""

    def __init__(self, global_: str, *, viva: bool = True):
        super().__init__(Config(sesion="taller"))
        self.global_, self.viva_falsa, self.llamadas = global_, viva, []

    def disponible(self) -> bool:
        return True

    def _ok(self, *args: str) -> bool:
        self.llamadas.append(list(args))
        return self.viva_falsa

    def _tmux(self, *args: str, tolerante: bool = False, entorno=None, entrada=None) -> str:
        self.llamadas.append(list(args))
        return self.global_ if list(args[:2]) == ["show-environment", "-g"] else ""

    def borrados(self) -> list[list[str]]:
        return [ll for ll in self.llamadas if "set-environment" in ll]


class LimpiarElServidor(Prueba):
    GLOBAL = ("CLAUDECODE=1\nCLAUDE_CODE_SESSION_ID=abc\nCLAUDE_CODE_MAX_OUTPUT_TOKENS=64000\nGIT_EDITOR=true\n"
              "PATH=/usr/bin\n-ZELLIJ\nCLAUDE_CODE_REMOTE_SESSION_ID=x\n")

    def test_borra_las_marcas_en_una_sola_orden_y_deja_lo_demas(self):
        m = _TmuxQueAnota(self.GLOBAL)
        self.assertEqual(m.limpiar_entorno(),
                         ["CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "GIT_EDITOR", "CLAUDE_CODE_REMOTE_SESSION_ID"])
        self.assertEqual(m.borrados(), [[
            "set-environment", "-g", "-u", "CLAUDECODE", ";",
            "set-environment", "-g", "-u", "CLAUDE_CODE_SESSION_ID", ";",
            "set-environment", "-g", "-u", "GIT_EDITOR", ";",
            "set-environment", "-g", "-u", "CLAUDE_CODE_REMOTE_SESSION_ID",
        ]])

    def test_limpio_no_escribe_nada(self):
        m = _TmuxQueAnota("PATH=/usr/bin\nCLAUDE_CODE_MAX_OUTPUT_TOKENS=64000\n")
        self.assertEqual(m.limpiar_entorno(), [])
        self.assertEqual(m.borrados(), [])

    def test_tejer_limpia_aunque_la_sesion_ya_estuviera(self):
        m = _TmuxQueAnota(self.GLOBAL, viva=True)
        m.tejer()
        self.assertEqual([ll for ll in m.llamadas if ll[0] == "new-session"], [])
        self.assertEqual(len(m.borrados()), 1)

    def test_abrir_el_primer_tab_limpia_antes_de_levantar_la_sesion(self):
        m = _TmuxQueAnota(self.GLOBAL, viva=False)
        with self.assertRaises(ErrorDeMux):  # el tmux de mentira no contesta qué tab abrió: no importa aquí
            m.crear_tab("faro", comando=["sh"])
        ordenes = [ll[0] for ll in m.llamadas if ll[0] in ("show-environment", "set-environment", "new-session")]
        self.assertEqual(ordenes, ["show-environment", "set-environment", "new-session"])


@unittest.skipUnless(shutil.which("tmux"), "no hay tmux instalado en esta máquina")
class ContraUnTmuxDeVerdad(Prueba):
    """Un servidor de tmux propio por prueba: `TMUX_TMPDIR` en una carpeta nueva, y sin `TMUX` (que apuntaría al de la
    persona si las pruebas corren dentro de tmux)."""

    def setUp(self) -> None:
        super().setUp()
        self.carpeta = Path(tempfile.mkdtemp(prefix="telar-entorno-"))
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)
        previo = {k: os.environ.get(k) for k in ("TMUX_TMPDIR", "TMUX")}
        self.addCleanup(self._restaurar, previo)
        os.environ["TMUX_TMPDIR"] = str(self.carpeta)
        os.environ.pop("TMUX", None)
        self.socket = socket_tmux(self.carpeta)  # las llamadas directas lo nombran: nunca el servidor de la persona
        self.addCleanup(matar_tmux, self.carpeta)
        # `entorno_para_abrir` lee el PATH de la shell de login de la persona: aquí no hace falta
        parche = mock.patch.object(tmux, "path_de_la_persona", return_value="")
        parche.start()
        self.addCleanup(parche.stop)
        self.mux = tmux.Tmux(Config(sesion="telar-entorno", raiz=self.carpeta))

    @staticmethod
    def _restaurar(previo: dict) -> None:
        for clave, valor in previo.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor

    def _global(self) -> set[str]:
        hecho = subprocess.run(["tmux", "-S", self.socket, "show-environment", "-g"], capture_output=True, text=True,
                               timeout=10)
        return _nombres(hecho.stdout)

    def _lo_que_ve_un_tab(self, nombre: str) -> set[str]:
        """Abre un tab cuyo proceso escribe su entorno, y lo lee."""
        salida = self.carpeta / f"{nombre}.env"
        self.mux.crear_tab(nombre, ruta=self.carpeta, foco=False,
                           comando=["sh", "-c", f'env > "{salida}.tmp" && mv "{salida}.tmp" "{salida}"; sleep 30'])
        fin = time.monotonic() + 8
        while not salida.exists():
            if time.monotonic() > fin:
                self.fail(f"el tab {nombre} no escribió su entorno")
            time.sleep(0.05)
        return _nombres(salida.read_text())

    def test_un_servidor_levantado_desde_un_claude_code_queda_limpio_al_tejer(self):
        # el caso del laptop: alguien levantó el servidor desde la Bash de un Claude Code, con su entorno entero
        sucias = set(MARCAS) | set(DEL_HILO)
        subprocess.run(["tmux", "-S", self.socket, "-f", "/dev/null", "new-session", "-d", "-s", "ajena"], check=True,
                       timeout=10,
                       env={**os.environ, **MARCAS, **DEL_HILO, **CONFIGURACION})
        self.assertLessEqual(sucias, self._global())  # el servidor sí las tiene
        self.mux.tejer()
        self.assertFalse(sucias & self._global())
        self.assertLessEqual(set(CONFIGURACION), self._global())
        vistas = self._lo_que_ve_un_tab("hijo")  # un tab suelto, sin el agente: lo que le da el servidor
        self.assertFalse(sucias & vistas, sorted(sucias & vistas))
        self.assertLessEqual(set(CONFIGURACION), vistas)

    def test_el_servidor_que_levanta_telar_nace_sin_marcas(self):
        # quien teje es un Claude Code: el servidor que nace no se queda con su sesión
        with mock.patch.dict(os.environ, {**MARCAS, **CONFIGURACION}):
            self.mux._levantar()
            self.assertFalse(set(MARCAS) & self._global())
            vistas = self._lo_que_ve_un_tab("hilo")
        self.assertFalse(set(MARCAS) & vistas, sorted(set(MARCAS) & vistas))
        self.assertLessEqual(set(CONFIGURACION), vistas)

    def test_un_tab_que_abre_un_claude_code_no_las_hereda(self):
        # el servidor ya estaba, limpio; quien abre el tab tiene las marcas
        self.mux.tejer()
        with mock.patch.dict(os.environ, MARCAS):
            vistas = self._lo_que_ve_un_tab("encargo")
        self.assertFalse(set(MARCAS) & vistas, sorted(set(MARCAS) & vistas))


if __name__ == "__main__":
    unittest.main()
