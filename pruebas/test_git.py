"""`telar commit`: solo las rutas dadas, sin pisar lo ajeno, y las carreras de push se reintentan.

Con repositorios de verdad en una carpeta temporal: un remoto pelado y dos copias que escriben a la vez,
como el laptop y el servidor sobre un mismo repositorio.
"""

from __future__ import annotations

import contextlib
import fcntl
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import git
from telar.ordenes import commit as orden_commit


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

    def test_lo_ya_borrado_con_git_rm_tambien_entra(self):
        sh(self.a, "rm", "-q", "uno.md")
        (self.a / "nuevo.md").write_text("n\n")
        res = self.commit(self.a, ["uno.md", "nuevo.md"], subir=False)
        self.assertEqual(res.estado, "commiteado")
        self.assertEqual(sorted(sh(self.a, "show", "--name-only", "--format=", "HEAD").split()), ["nuevo.md", "uno.md"])

    def test_un_nombre_imposible_no_es_un_traceback(self):
        self.assertEqual(git.commitear([Path("x" * 2000)], "m").estado, "fallo")

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
        (self.a / "otro.md").write_text("a medias, de otro hilo\n")
        res = self.commit(self.a, ["uno.md"])
        self.assertEqual(res.estado, "choque")
        self.assertFalse((self.a / ".git" / "rebase-merge").exists())
        self.assertEqual((self.a / "uno.md").read_text(), "de a\n")
        self.assertEqual((self.a / "otro.md").read_text(), "a medias, de otro hilo\n")  # lo apartado volvió
        self.assertEqual(sh(self.a, "stash", "list"), "")

    # ── lo sin commitear de otros, que se aparta mientras se rebasa ──
    #
    # El hook post-rewrite lo corre git al terminar el rebase, justo antes de que lo apartado vuelva al árbol: ahí
    # se hace lo que otro hilo podría hacer en ese instante.

    def _otro_subio_y_aqui_hay_cosas_a_medias(self, gancho: str):
        (self.b / "de-b.md").write_text("b\n")
        self.commit(self.b, ["de-b.md"])
        (self.a / "otro.md").write_text("a medias, de otro hilo\n")
        (self.a / "uno.md").write_text("uno, a medias\n")
        (self.a / "de-a.md").write_text("a\n")
        h = self.a / ".git" / "hooks" / "post-rewrite"
        h.write_text("#!/bin/sh\n" + gancho + "\n")
        h.chmod(0o755)

    def _candado_libre(self, carpeta: Path) -> bool:
        with open(carpeta / ".git" / "telar-subir.lock", "a") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            fcntl.flock(f, fcntl.LOCK_UN)
            return True

    def test_si_otro_tiene_tomado_el_indice_al_devolver_se_reintenta(self):
        # Lo que pasó: un `git status` de otro hilo tenía el index.lock cuando el `rebase --autostash` quiso
        # devolver lo guardado; git lo dejó en la lista de stash, salió con 0, y `telar commit` dijo «subido» con
        # los cambios de otros fuera del árbol
        self._otro_subio_y_aqui_hay_cosas_a_medias("touch .git/index.lock")
        esperas = []

        def esperar(s):  # el otro suelta el índice mientras se espera
            esperas.append(s)
            (self.a / ".git" / "index.lock").unlink(missing_ok=True)

        with mock.patch.object(git, "_esperar", side_effect=esperar):
            res = self.commit(self.a, ["de-a.md"])
        self.assertEqual((self.a / "otro.md").read_text(), "a medias, de otro hilo\n")
        self.assertEqual((self.a / "uno.md").read_text(), "uno, a medias\n")
        self.assertEqual(sh(self.a, "stash", "list"), "")
        self.assertEqual((res.estado, len(esperas)), ("subido", 1))
        self.assertEqual(sh(self.a, "status", "--porcelain").split("\n")[:2], [" M otro.md", " M uno.md"])

    def test_si_no_puede_devolverlo_no_sube_y_dice_como(self):
        self._otro_subio_y_aqui_hay_cosas_a_medias("touch .git/index.lock")  # y no lo suelta
        with mock.patch.object(git, "ESPERAS_DEVOLVER", (0, 0)):
            res = self.commit(self.a, ["de-a.md"])
        self.assertEqual((res.estado, res.subido), ("apartado", False))
        self.assertEqual(res.apartados, ["otro.md", "uno.md"])
        self.assertEqual(sh(self.a, "stash", "list", "--format=%H").split(), [res.stash])
        self.assertNotEqual(sh(self.a, "rev-parse", "HEAD"), sh(self.a, "rev-parse", "origin/main"))  # no subió
        self.assertEqual(res.commit, sh(self.a, "rev-parse", "--short", "HEAD").strip())  # el rebasado
        self.assertIn("stash@{0}", res.detalle)
        self.assertTrue(self._candado_libre(self.a))
        # lo que dice que haga, devuelve todo
        (self.a / ".git" / "index.lock").unlink()
        self.assertIn(f"git stash apply {res.stash[:10]}", res.detalle)
        sh(self.a, "stash", "apply", "-q", res.stash[:10])
        self.assertEqual((self.a / "otro.md").read_text(), "a medias, de otro hilo\n")
        self.assertEqual((self.a / "uno.md").read_text(), "uno, a medias\n")

    def test_si_alguien_escribio_lo_apartado_mientras_no_reintenta_y_nada_se_pierde(self):
        self._otro_subio_y_aqui_hay_cosas_a_medias('echo "de otro hilo, mientras" > otro.md')
        with mock.patch.object(git, "_esperar") as esperar:
            res = self.commit(self.a, ["de-a.md"])
        esperar.assert_not_called()  # esperar no lo arregla
        self.assertEqual((res.estado, res.subido), ("apartado", False))
        self.assertEqual((self.a / "otro.md").read_text(), "de otro hilo, mientras\n")  # lo nuevo no se pisa
        self.assertEqual(sh(self.a, "show", f"{res.stash}:otro.md"), "a medias, de otro hilo\n")  # lo de antes, ahí
        self.assertIn("alguien escribió otro.md", res.detalle)
        # el resto vuelve como dice
        h = res.stash[:10]
        self.assertIn(f"git restore --source={h} -- uno.md", res.detalle)
        sh(self.a, "restore", f"--source={h}", "--", "uno.md")
        self.assertEqual((self.a / "uno.md").read_text(), "uno, a medias\n")
        self.assertTrue(self._candado_libre(self.a))

    def test_si_el_rebase_queda_a_medias_lo_apartado_no_vuelve_hasta_abortarlo(self):
        # devolverlo con el rebase a medias sería perderlo: el `rebase --abort` de después hace un reset --hard
        (self.b / "uno.md").write_text("de b\n")
        self.commit(self.b, ["uno.md"])
        (self.a / "uno.md").write_text("de a\n")
        (self.a / "otro.md").write_text("a medias, de otro hilo\n")
        real = git._git

        def falso(repo, *args, **k):  # otro tiene el índice todo el rato: el abort no pasa
            if args[:2] == ("rebase", "--abort"):
                return subprocess.CompletedProcess(args, 128, "", "fatal: Unable to create '.git/index.lock'")
            return real(repo, *args, **k)

        with mock.patch.object(git, "_git", side_effect=falso), mock.patch.object(git, "ESPERAS_DEVOLVER", (0, 0)):
            res = self.commit(self.a, ["uno.md"])
        self.assertEqual((res.estado, res.apartados), ("apartado", ["otro.md"]))
        self.assertTrue(git._en_rebase(self.a))
        self.assertIn("primero, `git rebase --abort`", res.detalle)
        self.assertNotIn("otro.md", sh(self.a, "status", "--porcelain"))  # sigue afuera, no se devolvió a medias
        sh(self.a, "rebase", "--abort")
        sh(self.a, "stash", "apply", "-q", res.stash[:10])
        self.assertEqual((self.a / "otro.md").read_text(), "a medias, de otro hilo\n")
        self.assertEqual((self.a / "uno.md").read_text(), "de a\n")

    def test_la_orden_sale_con_3_y_no_dice_subido(self):
        self._otro_subio_y_aqui_hay_cosas_a_medias('echo "de otro hilo, mientras" > otro.md')
        ctx = SimpleNamespace(config=SimpleNamespace(estado=str(self.base / "estado")))
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = orden_commit.main(["-m", "m", "--", str(self.a / "de-a.md")], ctx)
        self.assertEqual(codigo, 3)
        self.assertEqual(salida.getvalue(), "")
        self.assertIn("queda local, sin subir", errores.getvalue())
        self.assertIn("stash@{0}", errores.getvalue())
        self.assertNotIn("subido", errores.getvalue())
        self.assertIn('"estado": "apartado"', (self.base / "estado" / "commits.log").read_text())

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


    # ── la orden, desde una subcarpeta: las rutas son relativas a donde se está, como en git ──

    def _subcarpeta(self) -> Path:
        sub = self.a / "docs" / "sub"
        sub.mkdir(parents=True)
        (sub / "viejo.md").write_text("viejo\n")
        sh(self.a, "add", "."), sh(self.a, "commit", "-qm", "sub"), sh(self.a, "push", "-q")
        return sub

    def orden(self, argv: list[str], en: Path) -> tuple[int, str, str]:
        ctx = SimpleNamespace(config=SimpleNamespace(estado=str(self.base / "estado")))
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.chdir(en), contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = orden_commit.main(argv, ctx)
        return codigo, salida.getvalue(), errores.getvalue()

    def head(self) -> str:
        return sh(self.a, "rev-parse", "HEAD").strip()

    def arriba(self) -> str:
        return sh(self.a, "rev-parse", "origin/main").strip()

    def test_desde_una_subcarpeta_las_rutas_relativas_a_ella_se_commitean(self):
        sub = self._subcarpeta()
        for local in (False, True):
            for caso in ("nuevo", "modificado"):
                with self.subTest(local=local, caso=caso):
                    nombre = f"{caso}-{local}.md" if caso == "nuevo" else "viejo.md"
                    with open(sub / nombre, "a") as f:
                        f.write(f"{caso} {local}\n")
                    codigo, salida, errores = self.orden(
                        ["-m", "m", *(["--local"] if local else []), "--", nombre], en=sub)
                    self.assertEqual((codigo, errores), (0, ""))
                    self.assertEqual(sh(self.a, "show", "--name-only", "--format=", "HEAD").split(), [f"docs/sub/{nombre}"])
                    self.assertIn("sin subir" if local else "subido", salida)
                    self.assertEqual(self.head() == self.arriba(), not local)
                    sh(self.a, "push", "-q")

    def test_desde_una_subcarpeta_las_rutas_relativas_a_la_raiz_no_commitean_ni_dicen_subido(self):
        # lo que pasó: un agente en una subcarpeta dio las rutas desde la raíz; telar no commiteó nada y dijo «subido»
        sub = self._subcarpeta()
        for local in (False, True):
            for caso in ("nuevo", "modificado"):
                with self.subTest(local=local, caso=caso):
                    nombre = "nuevo.md" if caso == "nuevo" else "viejo.md"
                    with open(sub / nombre, "a") as f:
                        f.write(f"{caso} {local}\n")
                    antes = self.head()
                    codigo, salida, errores = self.orden(
                        ["-m", "m", *(["--local"] if local else []), "--", f"docs/sub/{nombre}"], en=sub)
                    self.assertEqual((codigo, salida), (2, ""))
                    self.assertNotIn("subido", errores)
                    self.assertIn("no commiteé nada", errores)
                    self.assertIn(f"docs/sub/{nombre} → {nombre}", errores)  # cómo se escribe desde aquí
                    self.assertEqual(self.head(), antes)
                    self.assertIn(nombre, sh(self.a, "status", "--porcelain"))
        self.assertIn('"estado": "fallo"', (self.base / "estado" / "commits.log").read_text())

    def test_una_ruta_que_no_existe_entre_otras_no_commitea_ninguna(self):
        sub = self._subcarpeta()
        (sub / "viejo.md").write_text("cambio\n")
        antes = self.head()
        codigo, _, errores = self.orden(["-m", "m", "--", "viejo.md", "docs/sub/viejo.md"], en=sub)
        self.assertEqual(codigo, 2)
        self.assertIn("docs/sub/viejo.md → viejo.md", errores)
        self.assertEqual(self.head(), antes)

    def test_el_json_de_una_ruta_que_no_existe(self):
        sub = self._subcarpeta()
        codigo, salida, _ = self.orden(["-m", "m", "--json", "--", "docs/sub/viejo.md"], en=sub)
        res = json.loads(salida)
        self.assertEqual(codigo, 2)
        self.assertEqual((res["estado"], res["subido"], res["commit"], res["subidos"]), ("fallo", False, "", 0))

    def test_nada_que_commitear_en_esas_rutas_sale_con_4_y_no_dice_subido(self):
        sub = self._subcarpeta()
        for local in (False, True):
            with self.subTest(local=local):
                codigo, salida, errores = self.orden(["-m", "m", *(["--local"] if local else []), "--", "viejo.md"],
                                                     en=sub)
                self.assertEqual((codigo, salida), (4, ""))
                self.assertIn("no commiteé nada", errores)
                self.assertNotIn("subí", errores)
                self.assertNotIn("subido", errores)

    def test_nada_que_commitear_pero_habia_commits_pendientes_dice_que_subio_esos(self):
        sub = self._subcarpeta()
        (self.a / "uno.md").write_text("pendiente\n")
        sh(self.a, "commit", "-qam", "pendiente")
        codigo, salida, errores = self.orden(["-m", "m", "--", "viejo.md"], en=sub)
        self.assertEqual((codigo, salida), (4, ""))
        self.assertIn("no commiteé nada; subí 1 commit que ya estaba pendiente en main", errores)
        self.assertEqual(self.head(), self.arriba())
        # y en JSON: estado «nada», sin commit, pero la rama quedó arriba con un commit de antes
        (self.a / "uno.md").write_text("otro pendiente\n")
        sh(self.a, "commit", "-qam", "otro pendiente")
        codigo, salida, _ = self.orden(["-m", "m", "--json", "--", "viejo.md"], en=sub)
        res = json.loads(salida)
        self.assertEqual(codigo, 4)
        self.assertEqual((res["estado"], res["commit"], res["subido"], res["subidos"]), ("nada", "", True, 1))

    def test_el_json_de_un_commit_subido_cuenta_los_pendientes(self):
        sub = self._subcarpeta()
        (self.a / "uno.md").write_text("pendiente\n")
        sh(self.a, "commit", "-qam", "pendiente")
        (sub / "viejo.md").write_text("cambio\n")
        codigo, salida, _ = self.orden(["-m", "m", "--json", "--", "viejo.md"], en=sub)
        res = json.loads(salida)
        self.assertEqual(codigo, 0)
        self.assertEqual((res["estado"], res["subido"], res["subidos"]), ("subido", True, 2))
        self.assertEqual(res["rutas"], ["docs/sub/viejo.md"])

    def test_subir_sin_nada_pendiente_dice_que_estaba_al_dia(self):
        codigo, salida, _ = self.orden(["--subir"], en=self.a)
        self.assertEqual(codigo, 0)
        self.assertIn("ya estaba al día arriba", salida)
        (self.a / "uno.md").write_text("pendiente\n")
        sh(self.a, "commit", "-qam", "pendiente")
        codigo, salida, _ = self.orden(["--subir"], en=self.a)
        self.assertEqual((codigo, salida.strip()), (0, "subí 1 commit a main"))

    def test_una_ruta_que_no_existe_no_es_nada_que_commitear(self):
        res = git.commitear([self.a / "no-esta.md"], "m")
        self.assertEqual(res.estado, "fallo")
        self.assertIn("no-esta.md", res.detalle)

if __name__ == "__main__":
    unittest.main()
