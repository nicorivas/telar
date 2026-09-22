"""Abrir el agente de un hilo: la configuración, el comando y cuándo se reemplaza una shell."""

from __future__ import annotations

import shlex
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar.agente import lanzar
from telar.config import Agente, Config, ErrorDeConfig


class LaConfiguracion(Prueba):
    def test_sin_seccion_no_hay_agente(self):
        self.assertEqual(mod_config.desde_dict({}).agente, Agente(nombre="", carpeta="hilo"))

    def test_se_lee_nombre_y_carpeta(self):
        cfg = mod_config.desde_dict({"agente": {"nombre": "claude-code", "carpeta": "~/Vida"}})
        self.assertEqual(cfg.agente, Agente(nombre="claude-code", carpeta="~/Vida"))

    def test_una_clave_inventada_es_un_error(self):
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"agente": {"nombre": "claude-code", "modelo": "x"}})


class LaCarpeta(Prueba):
    def _cfg(self, carpeta):
        return replace(Config(raiz=Path("/repo")), agente=Agente(nombre="x", carpeta=carpeta))

    def test_hilo_es_la_carpeta_de_la_unidad(self):
        self.assertEqual(lanzar.carpeta(self._cfg("hilo"), Path("/repo/p/faro")), Path("/repo/p/faro"))

    def test_hilo_sin_carpeta_cae_en_la_raiz(self):
        self.assertEqual(lanzar.carpeta(self._cfg("hilo"), None), Path("/repo"))

    def test_raiz(self):
        self.assertEqual(lanzar.carpeta(self._cfg("raiz"), Path("/repo/p/faro")), Path("/repo"))

    def test_una_ruta_manda_sobre_el_hilo(self):
        self.assertEqual(lanzar.carpeta(self._cfg("/vida"), Path("/repo/p/faro")), Path("/vida"))


class ElEnvoltorio(Prueba):
    def test_el_nombre_del_hilo_no_se_interpola_crudo(self):
        comando = lanzar.envolver(["claude"], "faro'; rm -rf ~; echo '")
        self.assertEqual(comando[:2], ["sh", "-c"])
        self.assertIn(shlex.quote("faro'; rm -rf ~; echo '"), comando[2])

    def test_exporta_el_hilo_y_deja_una_shell_al_terminar(self):
        # Se corre de verdad: el "agente" es `true`, y en vez de la shell final se mira la variable.
        comando = lanzar.envolver(["true"], "el faro")
        linea = comando[2].replace('exec "${SHELL:-/bin/sh}" -l', 'printf %s "$TELAR_HILO"')
        salida = subprocess.run(["sh", "-c", linea], capture_output=True, text=True, timeout=5)
        self.assertEqual(salida.stdout, "el faro")
        self.assertIn('exec "${SHELL:-/bin/sh}" -l', comando[2])


class NadaDeOtroMultiplexor(Prueba):
    def test_el_agente_no_hereda_las_variables_de_zellij(self):
        # El caso real: tmux levantado desde un panel de Zellij le pasaba ZELLIJ_PANE_ID
        # a cada agente, y los ganchos de flow lo anotaban en un panel que no era suyo.
        import os
        comando = lanzar.envolver(["true"], "faro")
        linea = comando[2].replace('exec "${SHELL:-/bin/sh}" -l', 'printf %s "${ZELLIJ_PANE_ID:-limpio}"')
        entorno = {**os.environ, "ZELLIJ_PANE_ID": "123", "ZELLIJ_SESSION_NAME": "flow"}
        salida = subprocess.run(["sh", "-c", linea], capture_output=True, text=True, timeout=5, env=entorno)
        self.assertEqual(salida.stdout, "limpio")

    def test_tmux_se_levanta_sin_ellas(self):
        import os
        from telar.mux import tmux
        antes = dict(os.environ)
        os.environ["ZELLIJ_PANE_ID"] = "123"
        try:
            self.assertNotIn("ZELLIJ_PANE_ID", tmux.entorno_limpio())
        finally:
            os.environ.clear()
            os.environ.update(antes)


class QueSeRetoma(Prueba):
    def _agente(self, conversaciones, archivos):
        return SimpleNamespace(
            conversaciones=lambda hilo: [SimpleNamespace(id=c) for c in conversaciones],
            archivo_de=lambda c: archivos.get(c.id),
            retomar=lambda c: ["claude", "--resume", c.id],
            nuevo=lambda: ["claude"],
            nuevo_con_id=lambda mensaje="": (["claude", "--session-id", "id-nuevo"], "id-nuevo"),
        )

    def _correr(self, agente):
        cfg = replace(Config(raiz=Path("/repo")), agente=Agente(nombre="falso", carpeta="hilo"))
        original = lanzar.mod_agente.obtener
        lanzar.mod_agente.obtener = lambda nombre, config: agente
        try:
            return lanzar.para_hilo(cfg, "faro", Path("/repo/faro"))
        finally:
            lanzar.mod_agente.obtener = original

    def test_sin_agente_configurado_no_hay_lanzamiento(self):
        self.assertIsNone(lanzar.para_hilo(Config(), "faro", None))

    def test_retoma_la_conversacion_cuyo_archivo_existe(self):
        with tempfile.NamedTemporaryFile() as f:
            lanz = self._correr(self._agente(["vieja", "buena"], {"buena": Path(f.name)}))
        self.assertEqual(lanz.retoma, "buena")
        self.assertIn("--resume buena", lanz.comando[2])

    def test_si_ninguna_existe_abre_una_nueva(self):
        lanz = self._correr(self._agente(["perdida"], {"perdida": Path("/no/existe.jsonl")}))
        self.assertEqual(lanz.retoma, "")
        self.assertNotIn("--resume", lanz.comando[2])
        # la nueva nace con un id conocido, que quien la abre anota junto al hilo
        self.assertEqual(lanz.nueva, "id-nuevo")
        self.assertIn("--session-id id-nuevo", lanz.comando[2])


class CuandoSeReemplaza(Prueba):
    def _pane(self, id, comando, pid=100, **extra):
        return SimpleNamespace(id=id, comando=comando, pid=pid, flotante=False, terminado=False, **extra)

    def _ocioso(self, panes, hijos=False):
        return lanzar.panel_ocioso(panes, tiene_hijos=lambda pid: hijos)

    def test_una_shell_sin_hijos_se_reemplaza(self):
        self.assertEqual(self._ocioso([self._pane("%1", "zsh")]), "%1")

    def test_una_shell_con_hijos_no_se_toca(self):
        # El caso real: Claude Code corriendo, y tmux informándolo como `bash`.
        self.assertIsNone(self._ocioso([self._pane("%1", "bash")], hijos=True))

    def test_sin_pid_no_se_sabe_y_no_se_toca(self):
        self.assertIsNone(self._ocioso([self._pane("%1", "zsh", pid=None)]))

    def test_algo_corriendo_no_se_toca(self):
        self.assertIsNone(self._ocioso([self._pane("%1", "vim")]))

    def test_dos_paneles_no_se_tocan(self):
        self.assertIsNone(self._ocioso([self._pane("%1", "zsh"), self._pane("%2", "zsh", pid=101)]))

    def test_contra_procesos_de_verdad(self):
        # Una shell que duerme tiene un hijo; una que espera en `read` no tiene ninguno.
        import subprocess, time
        # «; true» obliga a sh a esperar a sleep como hijo en vez de reemplazarse por él
        con = subprocess.Popen(["sh", "-c", "sleep 30; true"])
        sin = subprocess.Popen(["sh", "-c", "read x"], stdin=subprocess.PIPE)
        try:
            time.sleep(0.3)
            self.assertTrue(lanzar._tiene_hijos(con.pid))
            self.assertFalse(lanzar._tiene_hijos(sin.pid))
        finally:
            con.kill(); sin.kill()


if __name__ == "__main__":
    unittest.main()
