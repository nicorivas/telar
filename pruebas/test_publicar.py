"""scripts/publicar.sh y scripts/pre-push: a GitHub sube un solo commit por versión, con el árbol de main y de padre
origin/main, y su etiqueta. Se prueba con un repositorio de juguete y un remoto bare local (docs/publicar.md)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from comun import RAIZ, Prueba  # noqa: E402

PUBLICAR = RAIZ / "scripts" / "publicar.sh"
GANCHO = RAIZ / "scripts" / "pre-push"
IDENTIDAD = {"GIT_AUTHOR_NAME": "Prueba", "GIT_AUTHOR_EMAIL": "prueba@ejemplo.org",
             "GIT_COMMITTER_NAME": "Prueba", "GIT_COMMITTER_EMAIL": "prueba@ejemplo.org"}


def _entorno() -> dict[str, str]:
    # Sin los GIT_* de afuera (un gancho que corra las pruebas trae GIT_DIR, y apuntaría al repositorio de verdad).
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(IDENTIDAD, GIT_CONFIG_NOSYSTEM="1")
    return env


class Juguete(Prueba):
    """Un repositorio con 0.1.0 ya publicado en un remoto bare, y después trabajo privado y 0.2.0 commiteada."""

    def setUp(self) -> None:
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="telar-publicar-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.remoto = self.tmp / "remoto.git"
        self.repo = self.tmp / "trabajo"
        self.git("init", "--bare", "-q", "-b", "main", str(self.remoto), cwd=self.tmp)
        self.git("init", "-q", "-b", "main", str(self.repo), cwd=self.tmp)
        (self.repo / "scripts").mkdir()
        shutil.copy(PUBLICAR, self.repo / "scripts" / "publicar.sh")
        shutil.copy(GANCHO, self.repo / "scripts" / "pre-push")
        self.version("0.1.0", "## [0.1.0] — 2026-11-01\n\n- primera\n")
        self.git("remote", "add", "origin", str(self.remoto))
        self.git("push", "-q", "origin", "main")
        self.publicado = self.git("rev-parse", "main")
        # el trabajo de después, con nombres que no tienen que llegar allá
        (self.repo / "privado.txt").write_text("nada\n")
        self.git("add", "privado.txt")
        self.git("commit", "-q", "-m", "trabajo con un nombre privado")
        self.version("0.2.0", "## [0.2.0] — 2026-11-23\n\n- segunda\n\n## [0.1.0] — 2026-11-01\n\n- primera\n")

    def git(self, *args: str, cwd: Path | None = None) -> str:
        r = subprocess.run(["git", *args], cwd=cwd or self.repo, env=_entorno(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"git {' '.join(args)}: {r.stderr}")
        return r.stdout.strip()

    def version(self, numero: str, changelog: str) -> None:
        (self.repo / "src" / "telar").mkdir(parents=True, exist_ok=True)
        (self.repo / "src" / "telar" / "__init__.py").write_text(f'__version__ = "{numero}"\n')
        (self.repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## [Unreleased]\n\n{changelog}")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"versión {numero}")

    def publicar(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", "scripts/publicar.sh", *args], cwd=self.repo, env=_entorno(),
                              capture_output=True, text=True)

    def alla(self, ref: str = "main") -> str:
        return self.git("rev-parse", ref, cwd=self.remoto)

    def gancho(self) -> Path:
        return self.repo / ".git" / "hooks" / "pre-push"


@unittest.skipUnless(shutil.which("bash") and shutil.which("git") and PUBLICAR.is_file(),
                     "hace falta bash, git y scripts/ (el sdist no lo lleva)")
class Publicar(Juguete):
    def test_en_seco_no_toca_nada(self):
        r = self.publicar()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Publicar v0.2.0", r.stdout)
        self.assertIn("En seco", r.stdout)
        self.assertEqual(self.alla(), self.publicado)
        self.assertEqual(self.git("tag"), "")
        self.assertFalse(self.gancho().exists())

    def test_de_verdad_sube_un_solo_commit_y_la_etiqueta(self):
        main = self.git("rev-parse", "main")
        r = self.publicar("0.2.0", "--de-verdad")
        self.assertEqual(r.returncode, 0, r.stderr)
        snap = self.alla()
        self.assertEqual(self.git("rev-list", "--count", f"{self.publicado}..{snap}", cwd=self.remoto), "1")
        self.assertEqual(self.git("rev-parse", f"{snap}^", cwd=self.remoto), self.publicado)
        self.assertEqual(self.git("rev-parse", f"{snap}^{{tree}}", cwd=self.remoto),
                         self.git("rev-parse", "main^{tree}"))
        self.assertEqual(self.git("log", "-1", "--format=%s", snap, cwd=self.remoto), "telar 0.2.0")
        self.assertNotIn("privado", self.git("log", "--format=%s", "main", cwd=self.remoto))
        self.assertEqual(self.git("cat-file", "-t", "v0.2.0", cwd=self.remoto), "tag")  # anotada
        self.assertEqual(self.alla("v0.2.0^{commit}"), snap)
        self.assertEqual(self.git("rev-parse", "main"), main)  # main local no se mueve
        self.assertTrue(self.gancho().is_file())
        self.assertTrue(os.access(self.gancho(), os.X_OK))

    def assertNiega(self, *args: str, dice: str) -> None:
        r = self.publicar(*args)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(dice, r.stderr)
        self.assertEqual(self.alla(), self.publicado)

    def test_arbol_sucio(self):
        (self.repo / "CHANGELOG.md").write_text("cambiado\n")
        self.assertNiega("--de-verdad", dice="no está limpio")

    def test_version_distinta_de_la_pedida(self):
        self.assertNiega("0.3.0", "--de-verdad", dice="pediste 0.3.0")

    def test_changelog_sin_la_seccion(self):
        (self.repo / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n- segunda\n")
        self.git("commit", "-q", "-am", "sin sección")
        self.assertNiega("--de-verdad", dice="«## [0.2.0]»")

    def test_fuera_de_main(self):
        self.git("checkout", "-q", "-b", "otra")
        self.assertNiega("--de-verdad", dice="estás en otra")

    def test_la_etiqueta_ya_existe(self):
        self.git("tag", "v0.2.0")
        self.assertNiega("--de-verdad", dice="v0.2.0 ya existe aquí")

    def test_alla_hay_algo_que_main_no_tiene(self):
        otro = self.tmp / "otro"
        self.git("clone", "-q", str(self.remoto), str(otro), cwd=self.tmp)
        (otro / "ajeno.txt").write_text("x\n")
        self.git("add", "ajeno.txt", cwd=otro)
        self.git("commit", "-q", "-m", "ajeno", cwd=otro)
        self.git("push", "-q", "origin", "main", cwd=otro)
        r = self.publicar("--de-verdad")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no salió de main", r.stderr)

    def test_nada_que_publicar(self):
        self.assertEqual(self.publicar("--de-verdad").returncode, 0)
        self.git("tag", "-d", "v0.2.0")
        self.git("push", "-q", "origin", ":refs/tags/v0.2.0")
        r = self.publicar()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no hay nada que publicar", r.stderr)


@unittest.skipUnless(shutil.which("sh") and shutil.which("git") and GANCHO.is_file(),
                     "hace falta sh, git y scripts/ (el sdist no lo lleva)")
class ElGancho(Juguete):
    """scripts/pre-push, llamado como lo llama git, con una URL de GitHub (con otra no dice nada)."""

    CERO = "0" * 40

    def empujar(self, *lineas: str, url: str = "https://github.com/x/telar.git") -> subprocess.CompletedProcess:
        return subprocess.run(["sh", str(GANCHO), "origin", url], cwd=self.repo, env=_entorno(),
                              input="".join(f"{x}\n" for x in lineas), capture_output=True, text=True)

    def test_main_entera_no(self):
        main = self.git("rev-parse", "main")
        r = self.empujar(f"refs/heads/main {main} refs/heads/main {self.publicado}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("un solo commit", r.stderr)
        self.assertEqual(self.empujar(f"refs/heads/main {main} refs/heads/main {self.publicado}",
                                      url="/algun/remoto.git").returncode, 0)

    def test_un_commit_encima_si(self):
        snap = self.git("commit-tree", "main^{tree}", "-p", self.publicado, "-m", "telar 0.2.0")
        self.assertEqual(self.empujar(f"{snap} {snap} refs/heads/main {self.publicado}").returncode, 0)

    def test_etiquetas_solo_sobre_lo_que_ya_esta_alla(self):
        self.git("fetch", "-q", "origin")
        main = self.git("rev-parse", "main")
        self.assertEqual(self.empujar(f"refs/tags/v0.2.0 {main} refs/tags/v0.2.0 {self.CERO}").returncode, 1)
        self.assertEqual(self.empujar(f"refs/tags/v0.1.0 {self.publicado} refs/tags/v0.1.0 {self.CERO}").returncode,
                         0)

    def test_otras_ramas_y_borrar_no(self):
        main = self.git("rev-parse", "main")
        self.assertEqual(self.empujar(f"refs/heads/x {main} refs/heads/x {self.CERO}").returncode, 1)
        self.assertEqual(self.empujar(f"(delete) {self.CERO} refs/heads/main {self.publicado}").returncode, 1)


if __name__ == "__main__":
    unittest.main()
