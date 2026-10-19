"""El programa del agente, cuando quien lanza no lo tiene en el PATH (un `ssh host 'orden'`)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.agente import lanzar


class ElProgramaDelAgente(Prueba):
    def test_en_el_path_va_tal_cual_y_si_no_con_su_ruta(self):
        with tempfile.TemporaryDirectory() as casa:
            bin_ = Path(casa) / ".local" / "bin"
            bin_.mkdir(parents=True)
            (bin_ / "agente-x").write_text("#!/bin/sh\n")
            os.chmod(bin_ / "agente-x", 0o755)
            with mock.patch.dict(os.environ, {"HOME": casa, "PATH": "/usr/bin:/bin"}):
                self.assertEqual(lanzar._programa("agente-x"), str(bin_ / "agente-x"))
                self.assertIn(str(bin_ / "agente-x"), lanzar.envolver(["agente-x", "--resume", "1"], "h")[2])
                self.assertEqual(lanzar._programa("no-existe-en-ningun-lado"), "no-existe-en-ningun-lado")
                self.assertEqual(lanzar._programa("sh"), "sh")
            with mock.patch.dict(os.environ, {"HOME": casa, "PATH": f"{bin_}:/usr/bin:/bin"}):
                self.assertEqual(lanzar._programa("agente-x"), "agente-x")


class ElEntornoDeQuienAbre(Prueba):
    """Un panel nuevo hereda el entorno de quien corre la orden de tmux: un servicio o un `ssh` con un PATH
    mínimo dejaba al agente sin lo que la persona instaló. Esas órdenes van con el PATH de su shell."""

    def setUp(self):
        super().setUp()
        from telar.mux import tmux
        self.tmux = tmux
        tmux._path_de_la_persona = None
        self.addCleanup(setattr, tmux, "_path_de_la_persona", None)

    def test_el_path_de_la_shell_de_login_va_delante_sin_repetir(self):
        with tempfile.TemporaryDirectory() as d:
            shell = Path(d) / "shell"
            shell.write_text('#!/bin/sh\necho "bienvenida que imprime el .zshrc"\n'
                             'printf "\\n__TELAR_PATH__/casa/nvm/bin:/opt/homebrew/bin:/usr/bin__\\n"\n')
            os.chmod(shell, 0o755)
            with mock.patch.dict(os.environ, {"SHELL": str(shell), "PATH": "/usr/bin:/bin", "ZELLIJ": "0"}):
                env = self.tmux.entorno_para_abrir()
        self.assertEqual(env["PATH"], "/casa/nvm/bin:/opt/homebrew/bin:/usr/bin:/bin")
        self.assertNotIn("ZELLIJ", env)

    def test_si_la_shell_no_responde_queda_el_path_de_aqui(self):
        with mock.patch.dict(os.environ, {"SHELL": "/no/existe", "PATH": "/usr/bin:/bin"}):
            self.assertEqual(self.tmux.entorno_para_abrir()["PATH"], "/usr/bin:/bin")
