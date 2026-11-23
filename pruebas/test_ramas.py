"""Los hijos con rama propia (telar.ramas): su worktree, fusionar en la rama del padre y borrar, con repositorios git
de verdad; y lo que saben el padre y el hijo al arrancar."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import estado as mod_estado
from telar import ramas


def git(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout


def commitear(carpeta: Path, archivo: str, texto: str, mensaje: str = "") -> None:
    (carpeta / archivo).parent.mkdir(parents=True, exist_ok=True)
    (carpeta / archivo).write_text(texto)
    git(carpeta, "add", archivo)
    git(carpeta, "commit", "-q", "-m", mensaje or f"cambio en {archivo}")


class _ConRepo(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name).resolve()
        self.repo = self.dir / "Codigo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            git(self.repo, "config", k, v)
        commitear(self.repo, "proyectos/faro/README.md", "# faro\n")
        commitear(self.repo, "comun.txt", "uno\ndos\ntres\n")
        self.worktrees = self.dir / "worktrees"

    def crear(self, hijo="Calendario", rama="", carpeta=None) -> dict:
        return ramas.crear(carpeta or self.repo / "proyectos" / "faro", hijo, rama, carpeta=self.worktrees)


class ElWorktree(_ConRepo):
    def test_sale_de_la_rama_del_padre_en_la_misma_subcarpeta(self):
        lugar = self.crear("Calendario nuevo")
        self.assertEqual(lugar["rama"], "calendario-nuevo")
        self.assertEqual(lugar["base"], "main")
        self.assertEqual(Path(lugar["ruta"]), self.worktrees / "codigo-calendario-nuevo")
        self.assertEqual(Path(lugar["carpeta"]), self.worktrees / "codigo-calendario-nuevo" / "proyectos" / "faro")
        self.assertTrue((Path(lugar["carpeta"]) / "README.md").is_file())
        self.assertEqual(git(Path(lugar["ruta"]), "rev-parse", "--abbrev-ref", "HEAD").strip(), "calendario-nuevo")
        self.assertEqual(Path(lugar["repo"]), self.repo)
        self.assertEqual(ramas.pendientes(lugar), 0)

    def test_un_nombre_de_rama_dado(self):
        lugar = self.crear("Calendario", rama="faro/calendario")
        self.assertEqual(lugar["rama"], "faro/calendario")
        self.assertEqual(Path(lugar["ruta"]).name, "codigo-faro-calendario")

    def test_no_pisa_una_rama_que_ya_existe(self):
        git(self.repo, "branch", "calendario")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            self.crear("Calendario")
        self.assertIn("ya existe la rama", str(e.exception))

    def test_sin_rama_sacada_no_sabe_de_donde(self):
        git(self.repo, "checkout", "-q", "--detach")
        with self.assertRaises(ramas.ErrorDeRama):
            self.crear()

    def test_fuera_de_un_repositorio(self):
        suelta = self.dir / "suelta"
        suelta.mkdir()
        with self.assertRaises(ramas.ErrorDeRama):
            self.crear(carpeta=suelta)

    def test_un_hijo_de_un_hijo_sale_de_la_rama_del_hijo(self):
        hijo = self.crear("Calendario")
        nieto = ramas.crear(Path(hijo["carpeta"]), "Vista mes", carpeta=self.worktrees)
        self.assertEqual(nieto["base"], "calendario")
        self.assertEqual(Path(nieto["ruta"]).name, "codigo-vista-mes")


class Fusionar(_ConRepo):
    def test_fusiona_en_la_carpeta_de_la_base_con_un_commit_de_fusion(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "proyectos/faro/calendario.md", "mes\n")
        self.assertEqual(ramas.pendientes(lugar), 1)
        r = ramas.fusionar(lugar, mensaje="calendario del faro")
        self.assertEqual((r["commits"], Path(r["destino"]), r["base"]), (1, self.repo, "main"))
        self.assertTrue((self.repo / "proyectos" / "faro" / "calendario.md").is_file())
        padres = git(self.repo, "log", "-1", "--format=%P").split()
        self.assertEqual(len(padres), 2)  # --no-ff: la funcionalidad entera se deshace con revert -m 1
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s").strip(), "calendario del faro")
        self.assertEqual(ramas.pendientes(lugar), 0)

    def test_sin_nada_nuevo_no_fusiona(self):
        lugar = self.crear()
        antes = git(self.repo, "rev-parse", "HEAD")
        r = ramas.fusionar(lugar)
        self.assertEqual((r["commits"], r["commit"]), (0, ""))
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), antes)

    def test_con_cambios_sin_commitear_del_hijo_se_niega(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "a.txt", "a\n")
        (Path(lugar["ruta"]) / "b.txt").write_text("a medias\n")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.fusionar(lugar)
        self.assertEqual(e.exception.archivos, ["b.txt"])
        self.assertFalse((self.repo / "a.txt").exists())
        # si sigue trabajando, se fusiona lo commiteado
        self.assertEqual(ramas.fusionar(lugar, con_cambios=True)["commits"], 1)
        self.assertTrue((self.repo / "a.txt").exists())
        self.assertFalse((self.repo / "b.txt").exists())

    def test_si_choca_no_toca_la_carpeta_del_padre(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "comun.txt", "uno\nDOS del hijo\ntres\n")
        commitear(self.repo, "comun.txt", "uno\nDOS del padre\ntres\n")
        antes = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.fusionar(lugar)
        self.assertEqual(e.exception.archivos, ["comun.txt"])
        self.assertIn("git merge main", str(e.exception))
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), antes)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual((self.repo / "comun.txt").read_text(), "uno\nDOS del padre\ntres\n")

    def test_lo_sucio_del_padre_que_la_fusion_cambia_lo_detiene(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "comun.txt", "uno\ndos\ntres\ncuatro\n")
        (self.repo / "comun.txt").write_text("a medias del padre\n")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.fusionar(lugar)
        self.assertEqual(e.exception.archivos, ["comun.txt"])
        self.assertEqual((self.repo / "comun.txt").read_text(), "a medias del padre\n")

    def test_lo_sucio_del_padre_en_otro_archivo_queda_como_estaba(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "nuevo.txt", "del hijo\n")
        (self.repo / "proyectos" / "faro" / "README.md").write_text("# faro, a medias\n")
        self.assertEqual(ramas.fusionar(lugar)["commits"], 1)
        self.assertEqual((self.repo / "proyectos" / "faro" / "README.md").read_text(), "# faro, a medias\n")

    def test_la_base_sacada_en_otro_worktree(self):
        # el padre también trabaja en un worktree: se fusiona donde está sacada su rama
        hijo = self.crear("Calendario")
        nieto = ramas.crear(Path(hijo["carpeta"]), "Vista mes", carpeta=self.worktrees)
        commitear(Path(nieto["ruta"]), "mes.txt", "mes\n")
        r = ramas.fusionar(nieto)
        self.assertEqual(Path(r["destino"]), Path(hijo["ruta"]))
        self.assertTrue((Path(hijo["ruta"]) / "mes.txt").is_file())
        self.assertFalse((self.repo / "mes.txt").exists())


#: lo que hace de compilador en las pruebas de lo compilado: lee la fuente y escribe una sola línea (dos ramas que
#: cambian la fuente en lugares distintos chocan en lo compilado y no en la fuente), y necesita su node_modules
GENERAR = """import pathlib, sys
aqui = pathlib.Path(__file__).parent
if not (aqui / "node_modules" / "marca.txt").is_file():
    sys.exit("sin node_modules")
fuente = (aqui.parent / "fuente.txt").read_text().split()
(aqui.parent / "salida").mkdir(exist_ok=True)
(aqui.parent / "salida" / "app.js").write_text("compilado:" + ",".join(fuente) + chr(10))
"""


def compilado(raiz: Path) -> str:
    return "compilado:" + ",".join((raiz / "fuente.txt").read_text().split()) + "\n"


def compilar(raiz: Path) -> None:
    """Lo que haría el hijo con `npm run navegador`: lo compilado al día con la fuente de su copia."""
    (raiz / "salida").mkdir(exist_ok=True)
    (raiz / "salida" / "app.js").write_text(compilado(raiz))


class LoCompilado(_ConRepo):
    """`fusionar` con lo compilado (`merge=telar-compilado` y `.telar/compilados.yaml`): un choque que es solo de lo
    compilado se resuelve volviéndolo a generar en un árbol aparte; uno de verdad se niega como siempre."""

    def setUp(self):
        super().setUp()
        (self.repo / ".gitattributes").write_text("salida/app.js merge=telar-compilado\n")
        (self.repo / ".telar").mkdir()
        (self.repo / ".telar" / "compilados.yaml").write_text(
            f"comandos:\n  - carpeta: web\n    comando: {sys.executable} generar.py\n")
        (self.repo / "web").mkdir()
        (self.repo / "web" / "package.json").write_text("{}\n")
        (self.repo / "web" / "generar.py").write_text(GENERAR)
        (self.repo / "web" / ".gitignore").write_text("node_modules\n")
        (self.repo / "web" / "node_modules").mkdir()
        (self.repo / "web" / "node_modules" / "marca.txt").write_text("las dependencias\n")
        (self.repo / "fuente.txt").write_text("uno\ndos\ntres\ncuatro\n")
        compilar(self.repo)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "con lo compilado")

    def cambiar(self, raiz: Path, linea: int, texto: str, compilar_=True) -> None:
        lineas = (raiz / "fuente.txt").read_text().splitlines()
        lineas[linea] = texto
        (raiz / "fuente.txt").write_text("\n".join(lineas) + "\n")
        if compilar_:
            compilar(raiz)
        git(raiz, "commit", "-q", "-am", f"fuente: {texto}")

    def chocan_en_lo_compilado(self) -> dict:
        lugar = self.crear()
        self.cambiar(Path(lugar["ruta"]), 0, "UNO-del-hijo")
        self.cambiar(self.repo, 3, "CUATRO-del-padre")
        self.assertEqual(ramas.chocaria(self.repo, "main", "calendario"), ["salida/app.js"])
        return lugar

    def test_un_choque_solo_de_lo_compilado_se_vuelve_a_generar(self):
        lugar = self.chocan_en_lo_compilado()
        r = ramas.fusionar(lugar, mensaje="calendario")
        self.assertEqual((r["commits"], r["regenerados"]), (1, ["salida/app.js"]))
        # lo compilado es el de la fuente fusionada, no el de ninguna de las dos ramas
        self.assertEqual((self.repo / "fuente.txt").read_text(), "UNO-del-hijo\ndos\ntres\nCUATRO-del-padre\n")
        self.assertEqual((self.repo / "salida" / "app.js").read_text(), "compilado:UNO-del-hijo,dos,tres,CUATRO-del-padre\n")
        # un commit de fusión, con el mensaje, y la carpeta del padre limpia
        self.assertEqual(len(git(self.repo, "log", "-1", "--format=%P").split()), 2)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s").strip(), "calendario")
        self.assertEqual(git(self.repo, "rev-parse", "--short", "HEAD").strip(), r["commit"])
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(ramas.pendientes(lugar), 0)
        # el árbol aparte no queda: solo la carpeta del padre y el worktree del hijo
        self.assertEqual(len(ramas.copias(self.repo)), 2)

    def test_sin_mensaje_el_de_git(self):
        lugar = self.chocan_en_lo_compilado()
        ramas.fusionar(lugar)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s").strip(), "Merge branch 'calendario'")

    def test_un_choque_de_verdad_se_niega_como_siempre(self):
        lugar = self.chocan_en_lo_compilado()
        commitear(Path(lugar["ruta"]), "comun.txt", "uno\nDOS del hijo\ntres\n")
        commitear(self.repo, "comun.txt", "uno\nDOS del padre\ntres\n")
        antes = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.fusionar(lugar)
        self.assertEqual(e.exception.archivos, ["comun.txt"])
        self.assertIn("git merge main", str(e.exception))
        self.assertIn("lo compilado que también choca se resuelve solo", str(e.exception))
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), antes)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_sin_compilados_yaml_un_choque_de_lo_compilado_se_niega(self):
        git(self.repo, "rm", "-q", ".telar/compilados.yaml")
        git(self.repo, "commit", "-q", "-m", "sin compilados.yaml")
        lugar = self.chocan_en_lo_compilado()
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.fusionar(lugar)
        self.assertEqual(e.exception.archivos, ["salida/app.js"])
        self.assertIn(".telar/compilados.yaml", str(e.exception))

    def test_si_el_comando_falla_nada_cambia(self):
        lugar = self.chocan_en_lo_compilado()
        (self.repo / "web" / "node_modules" / "marca.txt").unlink()   # el compilador no encuentra sus dependencias
        antes = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.fusionar(lugar)
        self.assertIn("falló al volver a generar", str(e.exception))
        self.assertIn("sin node_modules", str(e.exception))
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), antes)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(len(ramas.copias(self.repo)), 2)

    def test_lo_compilado_viejo_de_la_rama_se_vuelve_a_generar(self):
        # el hijo trae main con `git merge`: el driver se queda con su compilado (viejo), y fusionar lo arregla
        lugar = self.crear()
        hijo = Path(lugar["ruta"])
        self.cambiar(hijo, 0, "UNO-del-hijo")
        self.cambiar(self.repo, 3, "CUATRO-del-padre")
        git(hijo, "merge", "-q", "--no-edit", "main")
        self.assertEqual((hijo / "salida" / "app.js").read_text(), "compilado:UNO-del-hijo,dos,tres,cuatro\n")
        self.assertEqual(ramas.chocaria(self.repo, "main", "calendario"), [])
        r = ramas.fusionar(lugar)
        self.assertEqual(r["regenerados"], ["salida/app.js"])
        self.assertEqual((self.repo / "salida" / "app.js").read_text(), "compilado:UNO-del-hijo,dos,tres,CUATRO-del-padre\n")

    def test_una_rama_que_no_toca_lo_compilado_se_fusiona_como_siempre(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "notas.md", "nada compilado\n")
        r = ramas.fusionar(lugar)
        self.assertEqual((r["commits"], r["regenerados"]), (1, []))

    def test_el_driver_vale_en_los_worktrees_y_no_en_la_carpeta_principal(self):
        lugar = self.crear()
        hijo = Path(lugar["ruta"])
        self.assertEqual(git(hijo, "config", "merge.telar-compilado.driver").strip(), "true")
        r = subprocess.run(["git", "-C", str(self.repo), "config", "merge.telar-compilado.driver"], capture_output=True)
        self.assertNotEqual(r.returncode, 0)
        # en la carpeta principal, un choque de lo compilado sigue siendo un choque
        self.cambiar(hijo, 0, "UNO-del-hijo")
        self.cambiar(self.repo, 3, "CUATRO-del-padre")
        r = subprocess.run(["git", "-C", str(self.repo), "merge", "--no-edit", "calendario"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("salida/app.js", git(self.repo, "diff", "--name-only", "--diff-filter=U"))
        git(self.repo, "merge", "--abort")
        # preparar el driver es idempotente: el config no junta líneas
        self.assertTrue(ramas.preparar_driver(self.repo))
        config = Path(git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()) / "config"
        self.assertEqual(config.read_text().count("telar-compilados.gitconfig"), 1)

    def test_sin_compilados_yaml_no_se_toca_el_config(self):
        git(self.repo, "rm", "-q", ".telar/compilados.yaml")
        git(self.repo, "commit", "-q", "-m", "sin compilados.yaml")
        self.assertFalse(ramas.preparar_driver(self.repo))
        lugar = self.crear()
        r = subprocess.run(["git", "-C", lugar["ruta"], "config", "merge.telar-compilado.driver"], capture_output=True)
        self.assertNotEqual(r.returncode, 0)

    def con_fuentes(self) -> None:
        """Que `.telar/compilados.yaml` diga de qué sale lo compilado: de fuente.txt."""
        (self.repo / ".telar" / "compilados.yaml").write_text(
            f"comandos:\n  - carpeta: web\n    comando: {sys.executable} generar.py\n    fuentes: [fuente.txt, web/]\n")
        git(self.repo, "commit", "-q", "-am", "de qué sale lo compilado")

    def test_una_rama_que_solo_toca_la_fuente_se_vuelve_a_generar_en_la_fusion(self):
        # lo de tirador-ficha: cambió pagina/media/css/marco.css, no src/telar/web/marco.css, y llegó el viejo a main
        self.con_fuentes()
        lugar = self.crear()
        self.cambiar(Path(lugar["ruta"]), 0, "UNO-del-hijo", compilar_=False)
        r = ramas.fusionar(lugar, mensaje="calendario")
        self.assertEqual((r["commits"], r["regenerados"]), (1, ["salida/app.js"]))
        self.assertEqual((self.repo / "salida" / "app.js").read_text(), "compilado:UNO-del-hijo,dos,tres,cuatro\n")
        # en el commit de la fusión, no suelto en la carpeta del padre
        self.assertIn("salida/app.js", git(self.repo, "show", "--format=", "--name-only", "-m", "--first-parent", "HEAD"))
        self.assertEqual(len(git(self.repo, "log", "-1", "--format=%P").split()), 2)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(len(ramas.copias(self.repo)), 2)

    def test_la_fuente_con_lo_compilado_al_dia_no_agrega_nada(self):
        self.con_fuentes()
        lugar = self.crear()
        self.cambiar(Path(lugar["ruta"]), 0, "UNO-del-hijo")
        r = ramas.fusionar(lugar)
        self.assertEqual(r["regenerados"], [])
        self.assertEqual((self.repo / "salida" / "app.js").read_text(), "compilado:UNO-del-hijo,dos,tres,cuatro\n")

    def test_una_rama_que_no_toca_ni_lo_compilado_ni_sus_fuentes_no_compila(self):
        self.con_fuentes()
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "notas.md", "nada compilado\n")
        with mock.patch.object(ramas, "_regenerar", wraps=ramas._regenerar) as regenerar, \
                mock.patch.object(ramas, "_fusionar_aparte", wraps=ramas._fusionar_aparte) as aparte:
            r = ramas.fusionar(lugar)
        self.assertEqual((r["commits"], r["regenerados"]), (1, []))
        regenerar.assert_not_called()
        aparte.assert_not_called()

    def test_sin_fuentes_declaradas_la_fuente_sola_no_compila(self):
        # lo de antes: sin `fuentes`, solo cuenta tocar lo compilado
        lugar = self.crear()
        self.cambiar(Path(lugar["ruta"]), 0, "UNO-del-hijo", compilar_=False)
        with mock.patch.object(ramas, "_regenerar", wraps=ramas._regenerar) as regenerar:
            r = ramas.fusionar(lugar)
        self.assertEqual(r["regenerados"], [])
        regenerar.assert_not_called()

    def test_las_fuentes_de_cada_comando(self):
        self.con_fuentes()
        self.assertEqual(ramas.comandos(self.repo)[0]["fuentes"], ["fuente.txt", "web/"])
        lista = ramas.comandos(self.repo)
        self.assertEqual(ramas.a_regenerar(lista, {"web/generar.py"}, []), lista)
        self.assertEqual(ramas.a_regenerar(lista, {"notas.md"}, []), [])
        self.assertEqual(ramas.a_regenerar(lista, {"notas.md"}, ["salida/app.js"]), lista)
        self.assertEqual(ramas.a_regenerar(lista, None, []), lista)

    def test_lo_compilado_desfasado_de_un_commit(self):
        # la red de `telar desplegar`: vuelve a generar en un árbol aparte y compara
        self.con_fuentes()
        self.assertEqual(ramas.desfasados(self.repo), [])
        self.cambiar(self.repo, 0, "UNO-sin-compilar", compilar_=False)
        self.assertEqual(ramas.desfasados(self.repo), ["salida/app.js"])
        self.assertEqual(ramas.desfasados(self.repo, cambia={"fuente.txt"}), ["salida/app.js"])
        # si lo que cambió no es fuente ni compilado, no mira
        self.assertIsNone(ramas.desfasados(self.repo, cambia={"notas.md"}))
        # la carpeta queda como estaba, y el árbol aparte no queda
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(len(ramas.copias(self.repo)), 1)

    def test_un_compilados_yaml_que_no_se_entiende(self):
        for texto in ("comandos: npm run x\n", "comandos:\n  - carpeta: web\n", "comandos:\n  - comando: x\n    carpeta: ../afuera\n",
                      "comandos:\n  - comando: x\n    fuentes: {a: 1}\n"):
            (self.repo / ".telar" / "compilados.yaml").write_text(texto)
            with self.assertRaises(ramas.ErrorDeRama):
                ramas.comandos(self.repo)


#: el CHANGELOG de las pruebas del CHANGELOG por fragmentos
CHANGELOG = """# Changelog

## [Unreleased]

### Added

- **Something older.** Already there.

### Fixed

- **An old fix.** Already there.

## [0.1.0] — 2026-11-01

### Added

- **The first version.**
"""


def fragmento(seccion: str, titulo: str, resto: str = "More words.") -> str:
    return f"### {seccion}\n\n- **{titulo}** {resto}\n  A second line, indented.\n"


class ElChangelog(_ConRepo):
    """`fusionar` con el CHANGELOG por fragmentos (`.telar/changelog.yaml`, telar.changelog): el fragmento de la rama
    pasa a [Unreleased] y se borra en el commit de la fusión; uno mal formado se niega sin tocar nada."""

    def setUp(self):
        super().setUp()
        (self.repo / ".telar").mkdir()
        (self.repo / ".telar" / "changelog.yaml").write_text("archivo: CHANGELOG.md\ncarpeta: changelog.d\nancho: 120\n"
                                                             "negrita: true\n")
        (self.repo / "CHANGELOG.md").write_text(CHANGELOG)
        (self.repo / "changelog.d").mkdir()
        (self.repo / "changelog.d" / "README.md").write_text("# changelog.d\n\nNo es un fragmento.\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "changelog por fragmentos")

    def rama(self, hijo: str, texto: str | None, archivo: str = "") -> dict:
        lugar = self.crear(hijo)
        ruta = Path(lugar["ruta"])
        commitear(ruta, f"{lugar['rama']}.txt", "lo suyo\n")
        if texto is not None:
            commitear(ruta, f"changelog.d/{archivo or lugar['rama']}.md", texto)
        return lugar

    def unreleased(self) -> str:
        texto = (self.repo / "CHANGELOG.md").read_text()
        return texto[texto.index("## [Unreleased]"):texto.index("## [0.1.0]")]

    def test_un_fragmento_pasa_a_su_seccion_en_el_commit_de_la_fusion(self):
        lugar = self.rama("Calendario", fragmento("Added", "A calendar."))
        r = ramas.fusionar(lugar, mensaje="calendario")
        self.assertEqual(r["changelog"], {"archivo": "CHANGELOG.md", "carpeta": "changelog.d",
                                          "fragmentos": ["changelog.d/calendario.md"], "secciones": ["Added"]})
        self.assertIn("### Added\n\n- **A calendar.** More words.\n  A second line, indented.\n- **Something older.**",
                      self.unreleased())
        self.assertFalse((self.repo / "changelog.d" / "calendario.md").exists())
        self.assertTrue((self.repo / "changelog.d" / "README.md").is_file())
        self.assertTrue((self.repo / "calendario.txt").is_file())
        # un solo commit de fusión, con el CHANGELOG y el fragmento borrado adentro; la carpeta queda limpia
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s%n%P").split("\n")[0], "calendario")
        self.assertEqual(len(git(self.repo, "log", "-1", "--format=%P").split()), 2)
        cambios = git(self.repo, "diff", "--name-status", "HEAD^1", "HEAD")
        self.assertIn("M\tCHANGELOG.md", cambios)
        self.assertNotIn("changelog.d", cambios)  # entró y salió en la misma fusión
        self.assertEqual(ramas.sucios(self.repo), [])

    def test_dos_ramas_seguidas_a_la_misma_seccion_no_chocan(self):
        uno = self.rama("Calendario", fragmento("Fixed", "First fix."))
        dos = self.rama("Mapa", fragmento("Fixed", "Second fix.") + "\n" + fragmento("Removed", "Something gone."))
        ramas.fusionar(uno)
        r = ramas.fusionar(dos)
        self.assertEqual(r["changelog"]["secciones"], ["Removed", "Fixed"])
        texto = self.unreleased()
        # lo más nuevo, arriba; Removed se crea entre Added y Fixed
        self.assertLess(texto.index("Second fix."), texto.index("First fix."))
        self.assertLess(texto.index("First fix."), texto.index("An old fix."))
        self.assertLess(texto.index("### Added"), texto.index("### Removed"))
        self.assertLess(texto.index("Something gone."), texto.index("### Fixed"))
        self.assertEqual(sorted(p.name for p in (self.repo / "changelog.d").iterdir()), ["README.md"])

    def test_sin_fragmento_fusiona_y_lo_dice(self):
        lugar = self.rama("Calendario", None)
        r = ramas.fusionar(lugar)
        self.assertEqual(r["changelog"]["fragmentos"], [])
        self.assertEqual((self.repo / "CHANGELOG.md").read_text(), CHANGELOG)
        self.assertTrue((self.repo / "calendario.txt").is_file())

    def test_un_fragmento_mal_formado_se_niega_sin_tocar_nada(self):
        malos = {
            "### Novedades\n\n- **Algo.** x\n": "no es una sección",
            "Algo suelto.\n\n### Added\n\n- **Algo.** x\n": "antes de la primera sección",
            "### Added\n\n- Sin negrita.\n": "negrita",
            "### Added\n\n- **Larga.** " + "x" * 120 + "\n": "el máximo es 120",
            "### Added\n\nUna línea sin guion.\n": "empieza con «- »",
            "### Added\n": "no tiene entradas",
            "": "está vacío",
        }
        for i, (texto, dice) in enumerate(malos.items()):
            with self.subTest(dice=dice):
                lugar = self.rama(f"Rama {i}", texto)
                antes = git(self.repo, "rev-parse", "HEAD")
                with self.assertRaises(ramas.ErrorDeRama) as e:
                    ramas.fusionar(lugar)
                self.assertIn("mal formado", str(e.exception))
                self.assertTrue(any(dice in a and f"changelog.d/rama-{i}.md" in a for a in e.exception.archivos),
                                e.exception.archivos)
                self.assertEqual(git(self.repo, "rev-parse", "HEAD"), antes)
                self.assertEqual((self.repo / "CHANGELOG.md").read_text(), CHANGELOG)
                self.assertFalse((self.repo / f"rama-{i}.txt").exists())

    def test_la_seccion_y_unreleased_que_faltan_se_crean(self):
        (self.repo / "CHANGELOG.md").write_text(CHANGELOG[CHANGELOG.index("## [0.1.0]"):].join(["# Changelog\n\n", ""]))
        git(self.repo, "commit", "-q", "-am", "sin unreleased")
        ramas.fusionar(self.rama("Calendario", fragmento("Security", "Safer.")))
        texto = (self.repo / "CHANGELOG.md").read_text()
        self.assertTrue(texto.startswith("# Changelog\n\n## [Unreleased]\n\n### Security\n\n- **Safer.** More words.\n"
                                         "  A second line, indented.\n\n## [0.1.0]"), texto)

    def test_con_el_changelog_sucio_en_la_carpeta_del_padre_se_niega(self):
        lugar = self.rama("Calendario", fragmento("Added", "A calendar."))
        (self.repo / "CHANGELOG.md").write_text(CHANGELOG + "\nalgo a medias\n")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.fusionar(lugar)
        self.assertEqual(e.exception.archivos, ["CHANGELOG.md"])
        self.assertTrue((self.repo / "CHANGELOG.md").read_text().endswith("algo a medias\n"))

    def test_con_lo_compilado_va_todo_en_la_misma_fusion(self):
        # el fragmento y lo compilado, juntos en el árbol aparte
        (self.repo / ".gitattributes").write_text("salida.txt merge=telar-compilado\n")
        (self.repo / ".telar" / "compilados.yaml").write_text(
            f"comandos:\n  - carpeta: .\n    comando: {sys.executable} -c \"open('salida.txt','w').write(open('comun.txt').read().upper())\"\n")
        (self.repo / "salida.txt").write_text("UNO\nDOS\nTRES\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "compilado")
        lugar = self.crear()
        hijo = Path(lugar["ruta"])
        (hijo / "comun.txt").write_text("uno del hijo\ndos\ntres\n")
        (hijo / "salida.txt").write_text("UNO DEL HIJO\nDOS\nTRES\n")
        git(hijo, "commit", "-q", "-am", "fuente")
        commitear(hijo, "changelog.d/calendario.md", fragmento("Changed", "Louder."))
        (self.repo / "comun.txt").write_text("uno\ndos\ntres del padre\n")
        (self.repo / "salida.txt").write_text("UNO\nDOS\nTRES DEL PADRE\n")
        git(self.repo, "commit", "-q", "-am", "fuente del padre")
        r = ramas.fusionar(lugar)
        self.assertEqual((r["regenerados"], r["changelog"]["secciones"]), (["salida.txt"], ["Changed"]))
        self.assertEqual((self.repo / "salida.txt").read_text(), "UNO DEL HIJO\nDOS\nTRES DEL PADRE\n")
        self.assertIn("### Changed\n\n- **Louder.**", self.unreleased())
        self.assertEqual(ramas.sucios(self.repo), [])


class SinElChangelogDeclarado(_ConRepo):
    """Un repositorio que no declara `.telar/changelog.yaml`: fusionar hace lo de siempre, y un archivo en
    `changelog.d/` es un archivo más."""

    def test_fusiona_como_siempre(self):
        commitear(self.repo, "CHANGELOG.md", CHANGELOG)
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "changelog.d/calendario.md", "cualquier cosa\n")
        r = ramas.fusionar(lugar)
        self.assertIsNone(r["changelog"])
        self.assertEqual((self.repo / "CHANGELOG.md").read_text(), CHANGELOG)
        self.assertEqual((self.repo / "changelog.d" / "calendario.md").read_text(), "cualquier cosa\n")
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s").strip(), "Merge branch 'calendario'")


class NaceListo(_ConRepo):
    """El worktree de un hijo nace con los `node_modules` de la carpeta del padre enlazados (`enlazar_dependencias`):
    junto a cada `package.json` versionado, sin que git lo vea como un cambio."""

    def setUp(self):
        super().setUp()
        for carpeta, ignora in (("pagina", "node_modules\n"), ("otra", "node_modules/\n"), ("sin", "node_modules\n")):
            (self.repo / carpeta).mkdir()
            (self.repo / carpeta / "package.json").write_text("{}\n")
            (self.repo / carpeta / ".gitignore").write_text(ignora)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "paquetes")
        # «sin» no tiene node_modules en la carpeta del padre: no hay nada que enlazar
        for carpeta in ("pagina", "otra"):
            (self.repo / carpeta / "node_modules" / "esbuild").mkdir(parents=True)

    def test_enlaza_los_node_modules_del_padre(self):
        lugar = self.crear()
        ruta = Path(lugar["ruta"])
        self.assertEqual(lugar["enlazados"], ["otra/node_modules", "pagina/node_modules"])
        for carpeta in ("pagina", "otra"):
            enlace = ruta / carpeta / "node_modules"
            self.assertTrue(enlace.is_symlink())
            self.assertEqual(enlace.resolve(), (self.repo / carpeta / "node_modules").resolve())
            self.assertTrue((enlace / "esbuild").is_dir())
        self.assertFalse((ruta / "sin" / "node_modules").exists())
        # git no lo ve: ni con «node_modules» (sin barra) ni con «node_modules/», que se ignora en info/exclude
        self.assertEqual(ramas.sucios(ruta), [])
        self.assertIn("/otra/node_modules", (self.repo / ".git" / "info" / "exclude").read_text())
        # y por eso se fusiona y se borra como cualquier otro
        commitear(ruta, "pagina/x.ts", "x\n")
        ramas.fusionar(lugar)
        ramas.borrar(lugar)
        self.assertTrue((self.repo / "pagina" / "node_modules" / "esbuild").is_dir(), "borrar el enlace no toca lo del padre")

    def test_un_nieto_enlaza_lo_de_verdad(self):
        hijo = self.crear("Calendario")
        nieto = ramas.crear(Path(hijo["carpeta"]), "Vista mes", carpeta=self.worktrees)
        enlace = Path(nieto["ruta"]) / "pagina" / "node_modules"
        self.assertTrue(enlace.is_symlink())
        self.assertEqual(Path(os.readlink(enlace)), (self.repo / "pagina" / "node_modules").resolve())

    def test_sin_node_modules_en_el_padre_nada(self):
        for carpeta in ("pagina", "otra"):
            shutil.rmtree(self.repo / carpeta / "node_modules")
        lugar = self.crear()
        self.assertEqual(lugar["enlazados"], [])
        self.assertEqual(ramas.sucios(Path(lugar["ruta"])), [])


class Borrar(_ConRepo):
    def test_se_niega_si_hay_commits_sin_fusionar(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "a.txt", "a\n")
        with self.assertRaises(ramas.ErrorDeRama):
            ramas.borrar(lugar)
        self.assertTrue(Path(lugar["ruta"]).is_dir())

    def test_se_niega_si_hay_cambios_sin_commitear(self):
        lugar = self.crear()
        (Path(lugar["ruta"]) / "a.txt").write_text("a\n")
        with self.assertRaises(ramas.ErrorDeRama) as e:
            ramas.comprobar_borrar(lugar)
        self.assertEqual(e.exception.archivos, ["a.txt"])

    def test_despues_de_fusionar_borra_worktree_y_rama(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "a.txt", "a\n")
        ramas.fusionar(lugar)
        ramas.borrar(lugar)
        self.assertFalse(Path(lugar["ruta"]).exists())
        self.assertEqual(git(self.repo, "branch", "--list", "calendario"), "")
        self.assertTrue((self.repo / "a.txt").is_file())

    def test_forzar_pierde_lo_que_haya(self):
        lugar = self.crear()
        commitear(Path(lugar["ruta"]), "a.txt", "a\n")
        (Path(lugar["ruta"]) / "b.txt").write_text("b\n")
        ramas.borrar(lugar, forzar=True)
        self.assertFalse(Path(lugar["ruta"]).exists())
        self.assertEqual(git(self.repo, "branch", "--list", "calendario"), "")

    def test_un_worktree_que_ya_no_esta(self):
        lugar = self.crear()
        git(self.repo, "worktree", "remove", lugar["ruta"])
        ramas.borrar(lugar)
        self.assertEqual(git(self.repo, "branch", "--list", "calendario"), "")


class _ConHilos(_ConRepo):
    """La orden `telar hilo hijo --rama`, `fusionar` y `descartar`, con un multiplexor falso y el estado de verdad."""

    def setUp(self):
        super().setUp()
        self.config = mod_config.Config(raiz=self.dir, estado=self.dir / "estado",
                                        agente=mod_config.Agente(nombre="claude-code"))
        self.ctx = SimpleNamespace(config=self.config)
        self.est = mod_estado.abrir(self.config)
        self.est.vincular("Faro", "Codigo/proyectos/faro")
        self.mux = mock.Mock()
        self.vivos: set[str] = set()
        self.tel = SimpleNamespace(mux=self.mux, viva=True, hilos=[], estado=self.est, aviso="",
                                   vivo=lambda h: h.nombre in self.vivos)
        self.mux.crear_tab.side_effect = lambda nombre, **_: self.vivos.add(nombre)
        self.mux.cerrar.side_effect = lambda id_: self.vivos.discard(id_)
        p = mock.patch.object(ramas, "CARPETA", self.worktrees)
        p.start()
        self.addCleanup(p.stop)

    def opciones(self, **kw):
        base = dict(valor="", texto="", carpeta="", rama="", json=False, seguir=False, mensaje="", forzar=False)
        return SimpleNamespace(**{**base, **kw})

    def hijo(self, nombre="Calendario", **kw):
        from telar.agente import lanzar
        from telar.ordenes import hilo as orden

        padre = SimpleNamespace(nombre="Faro", id="Faro")
        lanz = SimpleNamespace(carpeta=self.dir, comando=["claude"])
        with mock.patch.object(lanzar, "para_hilo", return_value=lanz) as para, mock.patch.object(lanzar, "anotar"):
            codigo = orden._hijo(self.ctx, self.tel, padre, self.opciones(valor=nombre, texto="haz el calendario",
                                                                           rama="-", **kw))
        self.para_hilo = para
        return codigo

    def orden(self, verbo, nombre="Calendario", **kw):
        from telar.ordenes import hilo as orden

        h = SimpleNamespace(nombre=nombre, id=nombre, remoto="")
        fn = orden._fusionar if verbo == "fusionar" else orden._descartar
        with mock.patch.object(orden, "_matar_remoto"):
            return fn(self.ctx, self.tel, h, self.opciones(**kw))


class LaOrden(_ConHilos):
    def test_hijo_con_rama_abre_en_su_worktree_y_lo_anota(self):
        self.assertEqual(self.hijo(), 0)
        lugar = self.est.ramas()["Calendario"]
        self.assertEqual((lugar["rama"], lugar["base"]), ("calendario", "main"))
        # el worktree de la prueba está dentro de la raíz: el vínculo es relativo (el de ~/worktrees, absoluto)
        self.assertEqual(self.est.vinculos()["Calendario"], "worktrees/codigo-calendario/proyectos/faro")
        self.assertEqual(self.est.padres()["Calendario"], "Faro")
        # el agente se lanza con la carpeta del worktree, y el encargo dice que trabaja en su rama
        carpeta, encargo = self.para_hilo.call_args.args[2], self.para_hilo.call_args.args[3]
        self.assertEqual(carpeta, Path(lugar["carpeta"]))
        self.assertIn("tu propia rama, calendario", encargo)

    def test_si_no_se_abre_el_tab_no_queda_el_worktree(self):
        from telar.mux import ErrorDeMux

        self.mux.crear_tab.side_effect = ErrorDeMux("no")
        self.assertNotEqual(self.hijo(), 0)
        self.assertEqual(self.est.ramas(), {})
        self.assertFalse((self.worktrees / "codigo-calendario").exists())
        self.assertEqual(git(self.repo, "branch", "--list", "calendario"), "")

    def test_fusionar_cierra_archiva_y_borra(self):
        self.hijo()
        lugar = self.est.ramas()["Calendario"]
        commitear(Path(lugar["ruta"]), "proyectos/faro/calendario.md", "mes\n")
        self.assertEqual(self.orden("fusionar"), 0)
        self.assertTrue((self.repo / "proyectos" / "faro" / "calendario.md").is_file())
        self.assertNotIn("Calendario", self.vivos)
        self.assertIn("Calendario", self.est.archivados())
        self.assertEqual(self.est.ramas(), {})
        self.assertFalse(Path(lugar["ruta"]).exists())

    def test_fusionar_y_seguir_deja_al_hijo(self):
        self.hijo()
        lugar = self.est.ramas()["Calendario"]
        commitear(Path(lugar["ruta"]), "a.txt", "a\n")
        self.assertEqual(self.orden("fusionar", seguir=True), 0)
        self.assertTrue((self.repo / "a.txt").is_file())
        self.assertIn("Calendario", self.vivos)
        self.assertIn("Calendario", self.est.ramas())

    def test_si_choca_el_hijo_sigue_vivo(self):
        self.hijo()
        lugar = self.est.ramas()["Calendario"]
        commitear(Path(lugar["ruta"]), "comun.txt", "del hijo\n")
        commitear(self.repo, "comun.txt", "del padre\n")
        self.assertNotEqual(self.orden("fusionar"), 0)
        self.assertIn("Calendario", self.vivos)
        self.assertTrue(Path(lugar["ruta"]).is_dir())

    def test_descartar_se_niega_antes_de_cerrar_nada(self):
        self.hijo()
        lugar = self.est.ramas()["Calendario"]
        commitear(Path(lugar["ruta"]), "a.txt", "a\n")
        self.assertNotEqual(self.orden("descartar"), 0)
        self.assertIn("Calendario", self.vivos)
        self.assertEqual(self.orden("descartar", forzar=True), 0)
        self.assertNotIn("Calendario", self.vivos)
        self.assertFalse(Path(lugar["ruta"]).exists())
        self.assertFalse((self.repo / "a.txt").exists())

    def test_fusionar_dice_si_traia_entrada_del_changelog(self):
        commitear(self.repo, ".telar/changelog.yaml", "archivo: CHANGELOG.md\ncarpeta: changelog.d\n")
        commitear(self.repo, "CHANGELOG.md", CHANGELOG)
        for nombre, texto in (("Calendario", fragmento("Added", "A calendar.")), ("Mapa", None)):
            self.hijo(nombre)
            lugar = self.est.ramas()[nombre]
            commitear(Path(lugar["ruta"]), "proyectos/faro/" + lugar["rama"] + ".md", "x\n")
            if texto:
                commitear(Path(lugar["ruta"]), f"changelog.d/{lugar['rama']}.md", texto)
            salida, aparte = io.StringIO(), io.StringIO()
            with mock.patch("sys.stdout", salida), mock.patch("sys.stderr", aparte):
                self.assertEqual(self.orden("fusionar", nombre=nombre, json=True), 0)
            # con --json, stdout es solo el JSON: lo que cuenta al cerrar al hijo va por stderr
            datos = json.loads(salida.getvalue())
            self.assertIn("cerrado en el multiplexor", aparte.getvalue())
            self.assertEqual(datos["changelog"]["fragmentos"], [f"changelog.d/{lugar['rama']}.md"] if texto else [])
        texto = io.StringIO()
        self.hijo("Notas")
        commitear(Path(self.est.ramas()["Notas"]["ruta"]), "proyectos/faro/notas.md", "x\n")
        with mock.patch("sys.stdout", texto):
            self.assertEqual(self.orden("fusionar", nombre="Notas"), 0)
        self.assertIn("sin entrada del CHANGELOG", texto.getvalue())

    def test_descartar_con_json_deja_stdout_limpio(self):
        self.hijo()
        salida, aparte = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", salida), mock.patch("sys.stderr", aparte):
            self.assertEqual(self.orden("descartar", json=True), 0)
        self.assertTrue(json.loads(salida.getvalue())["borrado"])
        self.assertIn("cerrado en el multiplexor", aparte.getvalue())

    def test_un_hilo_sin_rama_no_se_fusiona(self):
        self.assertNotEqual(self.orden("fusionar", nombre="Faro"), 0)


class LoQueSaben(_ConHilos):
    def contexto(self, hilo: str) -> str:
        from telar.ordenes import agente

        return "\n".join(agente._familia(mod_estado.abrir(self.config), hilo))

    def test_el_hijo_sabe_su_rama_y_que_no_fusiona(self):
        self.hijo()
        texto = self.contexto("Calendario")
        self.assertIn("tu propia rama, calendario (salió de main)", texto)
        self.assertIn("No fusiones", texto)
        self.assertIn("/ramas", texto)

    def test_el_hijo_sabe_donde_va_su_entrada_del_changelog(self):
        self.hijo()
        self.assertNotIn("fragmentos", self.contexto("Calendario"))
        ruta = Path(self.est.ramas()["Calendario"]["ruta"])
        (ruta / ".telar").mkdir()
        (ruta / ".telar" / "changelog.yaml").write_text("archivo: CHANGELOG.md\ncarpeta: changelog.d\n")
        texto = self.contexto("Calendario")
        self.assertIn("CHANGELOG por fragmentos: tu entrada va en changelog.d/calendario.md", texto)

    def test_el_padre_sabe_que_fusiona_y_cuanto_le_falta(self):
        self.hijo()
        commitear(Path(self.est.ramas()["Calendario"]["ruta"]), "a.txt", "a\n")
        texto = self.contexto("Faro")
        self.assertIn("rama calendario, 1 commit(s) sin fusionar", texto)
        self.assertIn("los fusionas tú", texto)

    def test_sin_hijos_con_rama_no_se_dice(self):
        self.est.colgar("Notas", "Faro")
        self.assertNotIn("fusionas", self.contexto("Faro"))

    def test_renombrar_lleva_la_rama(self):
        self.hijo()
        self.est.renombrar("Calendario", "Calendario mensual")
        self.assertIn("Calendario mensual", self.est.ramas())
        self.est.olvidar("Calendario mensual")
        self.assertIn("Calendario mensual", self.est.ramas())  # olvidar no pierde trabajo sin fusionar


class ElLanzamiento(Prueba):
    def test_claude_code_suma_el_worktree_al_final(self):
        from telar.agente.claude_code import ClaudeCode

        self.assertEqual(ClaudeCode.con_carpetas(None, ["/w/codigo-x"]), ["--add-dir", "/w/codigo-x"])
        self.assertEqual(ClaudeCode.con_carpetas(None, [""]), [])

    def test_para_hilo_lo_pone_despues_del_mensaje(self):
        from telar.agente import lanzar

        with tempfile.TemporaryDirectory() as d:
            config = mod_config.Config(raiz=Path(d), estado=Path(d) / "estado", agente=mod_config.Agente(nombre="claude-code"))
            (Path(d) / "wt").mkdir()
            mod_estado.abrir(config).anotar_rama("Calendario", {"rama": "calendario", "ruta": str(Path(d) / "wt")})
            falso = SimpleNamespace(conversaciones=lambda h: [], nuevo_con_id=lambda m, id="": (["claude", m], "sid"),
                                    con_carpetas=lambda cs: ["--add-dir", *cs] if any(cs) else [])
            with mock.patch("telar.agente.obtener", return_value=falso):
                lanz = lanzar.para_hilo(config, "Calendario", Path(d) / "wt", "hola")
                otro = lanzar.para_hilo(config, "Faro", None, "hola")
        self.assertTrue(lanz.comando[-1].endswith(f"claude hola --add-dir {Path(d) / 'wt'}") or
                        f"hola --add-dir {Path(d) / 'wt'}" in " ".join(lanz.comando))
        self.assertNotIn("--add-dir", " ".join(otro.comando))


class ElEsfuerzo(_ConHilos):
    """`telar hilo hijo --esfuerzo`: su agente arranca con ese esfuerzo, y lo conserva al retomarlo; sin la opción, el de
    siempre."""

    def test_claude_code_lo_pide_con_effort(self):
        from telar.agente.claude_code import ClaudeCode

        self.assertEqual(ClaudeCode.con_esfuerzo(None, "low"), ["--effort", "low"])
        self.assertEqual(ClaudeCode.con_esfuerzo(None, ""), [])

    def test_hijo_con_esfuerzo_lo_anota_antes_de_lanzar(self):
        visto = {}

        def para_hilo(config, nombre, carpeta, mensaje=""):
            visto["esfuerzo"] = mod_estado.abrir(config).esfuerzos().get(nombre)
            return SimpleNamespace(carpeta=self.dir, comando=["claude"])

        from telar.agente import lanzar
        from telar.ordenes import hilo as orden

        padre = SimpleNamespace(nombre="Faro", id="Faro")
        with mock.patch.object(lanzar, "para_hilo", side_effect=para_hilo), mock.patch.object(lanzar, "anotar"), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as salida:
            codigo = orden._hijo(self.ctx, self.tel, padre, self.opciones(valor="Calendario", texto="haz", rama="-",
                                                                          esfuerzo="low", json=True))
        self.assertEqual(codigo, 0)
        self.assertEqual(visto["esfuerzo"], "low")
        self.assertEqual(json.loads(salida.getvalue())["esfuerzo"], "low")
        self.assertEqual(self.est.esfuerzos(), {"Calendario": "low"})

    def test_sin_la_opcion_el_de_siempre_aunque_hubiera_otro(self):
        self.est.anotar_esfuerzo("Calendario", "xhigh")   # un hilo de antes con el mismo nombre
        self.assertEqual(self.hijo(), 0)
        self.assertEqual(self.est.esfuerzos(), {})

    def test_si_no_se_abre_el_tab_no_queda(self):
        from telar.mux import ErrorDeMux

        self.mux.crear_tab.side_effect = ErrorDeMux("no")
        self.assertNotEqual(self.hijo(esfuerzo="medium"), 0)
        self.assertEqual(self.est.esfuerzos(), {})

    def test_un_esfuerzo_que_no_existe_no_se_acepta(self):
        from telar.ordenes import hilo as orden

        with mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertNotEqual(orden.main(["hijo", "Calendario", "--esfuerzo", "muchisimo"], self.ctx), 0)
        self.assertEqual(orden.ESFUERZOS, ("low", "medium", "high", "xhigh"))

    def test_renombrar_lo_lleva_y_olvidar_lo_borra(self):
        self.est.anotar_esfuerzo("Calendario", "medium")
        self.est.renombrar("Calendario", "Calendario mensual")
        self.assertEqual(self.est.esfuerzos(), {"Calendario mensual": "medium"})
        self.est.olvidar("Calendario mensual")
        self.assertEqual(self.est.esfuerzos(), {})

    def test_el_lanzamiento_lo_usa_al_abrir_y_al_retomar_antes_del_worktree(self):
        from telar.agente import lanzar

        wt = self.dir / "wt"
        wt.mkdir()
        self.est.anotar_rama("Calendario", {"rama": "calendario", "ruta": str(wt)})
        self.est.anotar_esfuerzo("Calendario", "medium")
        conversacion = SimpleNamespace(id="sid-1")
        archivo = self.dir / "sid-1.jsonl"
        archivo.write_text("{}\n")
        falso = SimpleNamespace(conversaciones=lambda h: [], nuevo_con_id=lambda m, id="": (["claude", m], "sid"),
                                retomar=lambda c: ["claude", "--resume", c.id], archivo_de=lambda c: archivo,
                                con_esfuerzo=lambda e: ["--effort", e] if e else [],
                                con_carpetas=lambda cs: ["--add-dir", *cs] if any(cs) else [])
        with mock.patch("telar.agente.obtener", return_value=falso):
            nuevo = " ".join(lanzar.para_hilo(self.config, "Calendario", wt, "hola").comando)
            falso.conversaciones = lambda h: [conversacion]
            retomado = " ".join(lanzar.para_hilo(self.config, "Calendario", wt, "sigue").comando)
            otro = " ".join(lanzar.para_hilo(self.config, "Faro", None, "hola").comando)
        self.assertIn(f"claude hola --effort medium --add-dir {wt}", nuevo)
        self.assertIn(f"claude --resume sid-1 sigue --effort medium --add-dir {wt}", retomado)
        self.assertNotIn("--effort", otro)


@unittest.skipUnless(HAY_FASTAPI, "sin el extra serve")
class ElEsfuerzoPorLaApi(Prueba):
    def test_post_hilo_hijo_lo_pasa(self):
        from telar import api
        from telar.servicios import en_proceso

        corrida = en_proceso.Corrida(codigo=0, salida="", error="")
        with mock.patch.object(en_proceso, "correr", return_value=corrida) as correr:
            api.post_hilo("hijo", api.PedidoHilo(hilo="Faro", valor="Calendario", texto="haz", esfuerzo="low"),
                          SimpleNamespace(config=None))
        argv = correr.call_args.args[2]
        self.assertEqual(argv[argv.index("--esfuerzo") + 1], "low")
        with mock.patch.object(en_proceso, "correr", return_value=corrida) as correr:
            api.post_hilo("hijo", api.PedidoHilo(hilo="Faro", valor="Calendario", texto="haz"), SimpleNamespace(config=None))
        self.assertNotIn("--esfuerzo", correr.call_args.args[2])
