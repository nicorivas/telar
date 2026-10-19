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
