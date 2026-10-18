"""`telar commit`: solo las rutas dadas, sin pisar lo ajeno, y las carreras de push se reintentan.

Con repositorios de verdad en una carpeta temporal: un remoto pelado y dos copias que escriben a la vez,
como el laptop y el servidor sobre un mismo repositorio.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import git


def sh(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout


@unittest.skipUnless(shutil.which("git"), "sin git")
class Commit(Prueba):
    def setUp(self):
        super().setUp()
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        origen = self.base / "origen.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origen)], check=True)
        self.a, self.b = self.base / "a", self.base / "b"
        for c in (self.a, self.b):
            subprocess.run(["git", "clone", "-q", str(origen), str(c)], check=True, capture_output=True)
            sh(c, "config", "user.email", "x@x"), sh(c, "config", "user.name", "x")
            sh(c, "checkout", "-q", "-b", "main")
        (self.a / "uno.md").write_text("uno\n")
        (self.a / "otro.md").write_text("otro\n")
        sh(self.a, "add", "."), sh(self.a, "commit", "-qm", "inicio"), sh(self.a, "push", "-q", "-u", "origin", "main")
        sh(self.b, "pull", "-q", "origin", "main"), sh(self.b, "branch", "-q", "-u", "origin/main")

    def commit(self, carpeta: Path, rutas: list[str], mensaje="m", subir=True):
        res = git.commitear([carpeta / r for r in rutas], mensaje)
        return git.subir(res, esperas=(0, 0)) if subir and res.estado != "fallo" else res

    def test_commitea_solo_lo_dado_y_los_nuevos_entran(self):
        (self.a / "nuevo.md").write_text("nuevo\n")
        (self.a / "otro.md").write_text("a medias, de otro\n")
        (self.a / "suelto.md").write_text("de otro\n")
        res = self.commit(self.a, ["nuevo.md"])
        self.assertEqual(res.estado, "subido")
        self.assertEqual(sh(self.a, "show", "--name-only", "--format=", "HEAD").split(), ["nuevo.md"])
        self.assertIn(" M otro.md", sh(self.a, "status", "--porcelain"))
        self.assertIn("?? suelto.md", sh(self.a, "status", "--porcelain"))

    def test_un_borrado_se_commitea_como_borrado(self):
        (self.a / "uno.md").unlink()
        res = self.commit(self.a, ["uno.md"], subir=False)
        self.assertEqual(res.estado, "commiteado")
        self.assertNotIn("uno.md", sh(self.a, "ls-files"))

    def test_no_toca_lo_marcado_skip_worktree(self):
        sh(self.a, "update-index", "--skip-worktree", "otro.md")
        (self.a / "otro.md").unlink()  # como en un disco que no acepta su nombre
        (self.a / "nuevo.md").write_text("n\n")
        self.commit(self.a, ["."], subir=False)
        self.assertIn("otro.md", sh(self.a, "ls-files"))

    def test_nada_que_commitear(self):
        self.assertEqual(self.commit(self.a, ["uno.md"], subir=False).estado, "nada")

    def test_si_otro_subio_antes_integra_y_sube(self):
        (self.b / "de-b.md").write_text("b\n")
        self.assertEqual(self.commit(self.b, ["de-b.md"]).estado, "subido")
        (self.a / "otro.md").write_text("a medias\n")  # sucio de aquí, que lo de b no toca
        (self.a / "de-a.md").write_text("a\n")
        res = self.commit(self.a, ["de-a.md"])
        self.assertEqual(res.estado, "subido")
        self.assertEqual(res.commit, sh(self.a, "rev-parse", "--short", "HEAD").strip())  # el de después del rebase
        self.assertTrue((self.a / "de-b.md").exists())
        self.assertEqual((self.a / "otro.md").read_text(), "a medias\n")
        self.assertEqual(sh(self.a, "stash", "list"), "")

    def test_si_lo_que_llega_toca_algo_sucio_de_aqui_no_integra(self):
        (self.b / "otro.md").write_text("de b\n")
        self.commit(self.b, ["otro.md"])
        (self.a / "otro.md").write_text("a medias, de otro hilo\n")
        (self.a / "de-a.md").write_text("a\n")
        res = self.commit(self.a, ["de-a.md"])
        self.assertEqual(res.estado, "choque")
        self.assertIn("otro.md", res.detalle)
        self.assertEqual((self.a / "otro.md").read_text(), "a medias, de otro hilo\n")
        self.assertEqual(sh(self.a, "log", "-1", "--format=%s").strip(), "m")  # el commit quedó, local
        self.assertEqual(sh(self.a, "stash", "list"), "")

    def test_si_el_rebase_choca_con_lo_propio_se_aborta(self):
        (self.b / "uno.md").write_text("de b\n")
        self.commit(self.b, ["uno.md"])
        (self.a / "uno.md").write_text("de a\n")
        res = self.commit(self.a, ["uno.md"])
        self.assertEqual(res.estado, "choque")
        self.assertFalse((self.a / ".git" / "rebase-merge").exists())
        self.assertEqual((self.a / "uno.md").read_text(), "de a\n")

    def test_una_carrera_de_push_se_reintenta(self):
        (self.a / "de-a.md").write_text("a\n")
        res = git.commitear([self.a / "de-a.md"], "m")
        real, veces = git._git, []

        def falso(repo, *args, **k):
            if args[:1] == ("push",) and not veces:
                veces.append(1)
                return subprocess.CompletedProcess(args, 1, "", "! [remote rejected] main (is at c01494b but expected 4142874)")
            return real(repo, *args, **k)

        with mock.patch.object(git, "_git", side_effect=falso):
            res = git.subir(res, esperas=(0, 0))
        self.assertEqual((res.estado, res.intentos), ("subido", 2))

    def test_un_push_que_falla_por_otra_cosa_no_se_reintenta(self):
        (self.a / "de-a.md").write_text("a\n")
        res = git.commitear([self.a / "de-a.md"], "m")
        real = git._git
        with mock.patch.object(git, "_git", side_effect=lambda repo, *a, **k: subprocess.CompletedProcess(
                a, 128, "", "Permission denied (publickey)") if a[:1] == ("push",) else real(repo, *a, **k)):
            res = git.subir(res, esperas=(0, 0))
        self.assertEqual((res.estado, res.intentos), ("fallo", 1))

    def test_fuera_del_repositorio_no_commitea(self):
        afuera = self.base / "afuera.md"
        afuera.write_text("x")
        self.assertEqual(git.commitear([afuera], "m", repo=self.a).estado, "fallo")


if __name__ == "__main__":
    unittest.main()
