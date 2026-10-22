"""`telar doctor` avisa de los repos de `[repos]` que se pisan o quedan fuera de la raíz, y de un módulo
declarado que no se puede leer (y carga igual para poder decirlo).

Nada de esto toca el multiplexor: las revisiones se piden una por una con un contexto armado a mano, y la
prueba de la orden entera reemplaza `doctor.main` por uno que solo guarda el contexto que le llegó.
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cli, lectura
from telar import config as mod_config
from telar.cli import Contexto
from telar.config import Config, ErrorDeConfig, Repo
from telar.ordenes import doctor

#: un perfil que reconoce cada carpeta con README bajo `ruta`
PERFIL = "version: 1\nnombre: {nombre}\narquetipos:\n  {arquetipo}:\n    ruta: \"{ruta}\"\n"


def _perfil(carpeta: Path, nombre: str, ruta: str = "*/", arquetipo: str = "proyecto") -> None:
    (carpeta / ".telar").mkdir(parents=True, exist_ok=True)
    (carpeta / ".telar" / "perfil.yaml").write_text(PERFIL.format(nombre=nombre, ruta=ruta, arquetipo=arquetipo),
                                               encoding="utf-8")


def _unidad(carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "README.md").write_text(f"# {carpeta.name}\n", encoding="utf-8")


class _ConRaiz(Prueba):
    """Una raíz con un repo del equipo adentro (`equipo/`), y adentro de ese otro más hondo (`equipo/faro/`)."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve() / "vida"
        self.equipo = self.raiz / "equipo"
        self.faro = self.equipo / "faro"
        for c in (self.raiz / "notas", self.faro / "mareas", self.equipo / "molino"):
            _unidad(c)

    def ctx(self, *repos: Repo) -> Contexto:
        return Contexto(config=Config(raiz=self.raiz, estado=Path(self.tmp.name) / "estado", repos=repos))

    def por_nombre(self, revisiones: list[dict], nombre: str) -> list[dict]:
        return [r for r in revisiones if r["nombre"] == nombre]


class ReposDeDoctor(_ConRaiz):
    def test_sin_repos_no_dice_nada(self):
        self.assertEqual(doctor._repos(self.ctx()), [])

    def test_dentro_y_sin_pisarse_esta_bien(self):
        _perfil(self.equipo, "equipo")
        revisiones = doctor._repos(self.ctx(Repo(nombre="equipo", ruta=self.equipo)))
        self.assertEqual([(r["nombre"], r["estado"]) for r in revisiones], [("repos", doctor.OK)])

    def test_una_ruta_relativa_se_lee_desde_la_raiz(self):
        """Desde otro directorio de trabajo, `equipo` sigue siendo el de la raíz: ni «no existe» ni «fuera», y sin
        aviso, porque todas las salidas la dan absoluta (telar config --json, TELAR_REPOS)."""
        _perfil(self.equipo, "equipo")
        previo = os.getcwd()
        self.addCleanup(os.chdir, previo)
        os.chdir(self.tmp.name)
        avisos = self.por_nombre(doctor._repos(self.ctx(Repo(nombre="equipo", ruta=Path("equipo")))), "repos")
        self.assertTrue(all(a["estado"] == doctor.OK for a in avisos), avisos)

    def test_un_repo_fuera_de_la_raiz_avisa(self):
        afuera = Path(self.tmp.name).resolve() / "afuera"
        afuera.mkdir()
        revisiones = doctor._repos(self.ctx(Repo(nombre="equipo", ruta=self.equipo), Repo(nombre="taller", ruta=afuera)))
        avisos = self.por_nombre(revisiones, "repos")
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]["estado"], doctor.AVISO)
        self.assertIn("«taller»", avisos[0]["dice"])
        self.assertIn(str(self.raiz), avisos[0]["dice"])
        self.assertTrue(avisos[0]["arreglo"])
        self.assertNotIn(doctor.FALLA, [r["estado"] for r in revisiones])

    def test_dos_repos_que_reconocen_la_misma_carpeta_avisan_y_gana_el_mas_hondo(self):
        # el del equipo reconoce `faro/mareas` (por `*/*/`), y el de faro también (por `*/`)
        _perfil(self.equipo, "equipo", ruta="*/*/", arquetipo="cliente")
        _perfil(self.faro, "faro")
        ctx = self.ctx(Repo(nombre="equipo", ruta=self.equipo), Repo(nombre="faro", ruta=self.faro))
        avisos = self.por_nombre(doctor._repos(ctx), "perfiles")
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]["estado"], doctor.AVISO)
        self.assertIn("equipo/faro/mareas", avisos[0]["dice"])
        self.assertIn("gana «faro»", avisos[0]["dice"])
        self.assertIn("«equipo»", avisos[0]["arreglo"])
        self.assertNotIn("repos", [r["nombre"] for r in doctor._repos(ctx) if r["estado"] != doctor.OK])

    def test_el_que_gana_es_el_que_de_verdad_describe_la_carpeta(self):
        """El orden de `pisadas` es el del índice que usa telar, no uno calculado aparte."""
        _perfil(self.equipo, "equipo", ruta="*/*/", arquetipo="cliente")
        _perfil(self.faro, "faro")
        ctx = self.ctx(Repo(nombre="equipo", ruta=self.equipo), Repo(nombre="faro", ruta=self.faro))
        choques = doctor.pisadas(ctx.perfil, self.raiz)
        self.assertEqual(choques, {"equipo/faro/mareas": ["faro", "equipo"]})
        arquetipo, _ = lectura.indice(ctx.perfil, self.raiz)["equipo/faro/mareas"]
        self.assertEqual(arquetipo.repo, "faro")

    def test_el_perfil_de_la_raiz_cuenta_solo_si_la_raiz_esta_en_repos(self):
        """Que el perfil de vida también nombre las carpetas del repo del equipo es lo previsto (cargar_todos)."""
        _perfil(self.raiz, "vida", ruta="**/")
        _perfil(self.equipo, "equipo")
        solo_equipo = self.ctx(Repo(nombre="equipo", ruta=self.equipo))
        self.assertEqual(self.por_nombre(doctor._repos(solo_equipo), "perfiles"), [])
        con_vida = self.ctx(Repo(nombre="vida", ruta=self.raiz), Repo(nombre="equipo", ruta=self.equipo))
        avisos = self.por_nombre(doctor._repos(con_vida), "perfiles")
        self.assertEqual(len(avisos), 1)
        self.assertIn("gana «equipo»", avisos[0]["dice"])
        self.assertIn("«vida»", avisos[0]["dice"])

    def test_la_raiz_en_repos_pero_sin_perfil_no_cuenta(self):
        """Sin perfil en la raíz rige el mínimo, que nadie escribió: no es un perfil «vida» que se pise."""
        _perfil(self.equipo, "equipo")
        ctx = self.ctx(Repo(nombre="vida", ruta=self.raiz), Repo(nombre="equipo", ruta=self.equipo))
        self.assertTrue(ctx.perfil.minimo)
        self.assertEqual(self.por_nombre(doctor._repos(ctx), "perfiles"), [])

    def test_dos_repos_en_la_misma_carpeta_gana_el_primero_declarado(self):
        _perfil(self.equipo, "equipo")
        ctx = self.ctx(Repo(nombre="uno", ruta=self.equipo), Repo(nombre="dos", ruta=self.equipo))
        avisos = self.por_nombre(doctor._repos(ctx), "perfiles")
        self.assertEqual(len(avisos), 1)
        self.assertIn("gana «uno», el primero de [repos]", avisos[0]["dice"])
        self.assertNotIn("el más hondo", avisos[0]["dice"])
        arquetipo, _ = lectura.indice(ctx.perfil, self.raiz)["equipo/molino"]
        self.assertEqual(arquetipo.repo, "uno")

    def test_un_repo_que_no_existe_avisa(self):
        revisiones = doctor._repos(self.ctx(Repo(nombre="taller", ruta=self.raiz / "no-esta")))
        self.assertEqual([(r["nombre"], r["estado"]) for r in revisiones], [("repos", doctor.AVISO)])
        self.assertIn("«taller»", revisiones[0]["dice"])
        self.assertIn("no existe", revisiones[0]["dice"])

    def test_arquetipos_del_mismo_repo_no_son_dos_repos(self):
        (self.equipo / ".telar").mkdir(parents=True, exist_ok=True)
        (self.equipo / ".telar" / "perfil.yaml").write_text(
            'version: 1\nnombre: equipo\narquetipos:\n  a:\n    ruta: "*/"\n  b:\n    ruta: "molino/"\n',
            encoding="utf-8")
        self.assertEqual(doctor.pisadas(self.ctx(Repo(nombre="equipo", ruta=self.equipo)).perfil, self.raiz), {})


class ModulosDeDoctor(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.raiz = base / "raiz"
        self.raiz.mkdir()
        os.environ["TELAR_ESTADO"] = str(base / "estado")
        os.environ["TELAR_RAIZ"] = str(self.raiz)
        self.bueno = base / "modulos" / "faro"
        self.bueno.mkdir(parents=True)
        (self.bueno / "modulo.toml").write_text('descripcion = "el mar"\n', encoding="utf-8")
        self.config = base / "config.toml"
        self.config.write_text(
            f'[modulos.faro]\ncarpeta = "{self.bueno}"\n[modulos.molino]\ncarpeta = "{base / "no-esta"}"\n',
            encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(self.config)

    def correr(self, *argv: str) -> tuple[int, str, str]:
        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = cli.main(list(argv))
        return codigo, salida.getvalue(), error.getvalue()

    def test_las_demas_ordenes_siguen_negandose(self):
        with self.assertRaises(ErrorDeConfig):
            mod_config.cargar()
        codigo, _, error = self.correr("config", "--json")
        self.assertEqual(codigo, 2)
        self.assertIn("molino", error)

    def test_con_tolerancia_queda_fuera_y_anotado(self):
        cfg = mod_config.cargar(tolerar_modulos=True)
        self.assertEqual([m.nombre for m in cfg.modulos], ["faro"])
        self.assertEqual([n for n, _ in cfg.modulos_rotos], ["molino"])
        self.assertIn("modulo.toml", cfg.modulos_rotos[0][1])

    def test_doctor_carga_igual_y_lo_dice_como_falla(self):
        llego = {}

        def main(argv, ctx):
            llego["ctx"] = ctx
            return 0

        with mock.patch.object(doctor, "main", main):
            codigo, _, error = self.correr("doctor")
        self.assertEqual(codigo, 0, error)
        revisiones = doctor._modulos(llego["ctx"])
        self.assertEqual([(r["nombre"], r["estado"]) for r in revisiones], [("módulos", doctor.FALLA)])
        self.assertIn("«molino» no se puede leer", revisiones[0]["dice"])
        self.assertNotIn("molino: ", revisiones[0]["dice"])
        self.assertIn("no arrancan", revisiones[0]["arreglo"])

    def test_un_modulos_toml_roto_tambien(self):
        self.config.write_text(f'[modulos.faro]\ncarpeta = "{self.bueno}"\n', encoding="utf-8")
        (self.config.parent / "modulos.toml").write_text("[molino\n", encoding="utf-8")
        with self.assertRaises(ErrorDeConfig):
            mod_config.cargar()
        cfg = mod_config.cargar(tolerar_modulos=True)
        self.assertEqual([m.nombre for m in cfg.modulos], ["faro"])
        revisiones = doctor._modulos(Contexto(config=cfg))
        self.assertEqual([(r["nombre"], r["estado"]) for r in revisiones], [("módulos", doctor.FALLA)])
        self.assertIn("modulos.toml", revisiones[0]["dice"])

    def test_todos_legibles_esta_bien_y_sin_modulos_no_dice_nada(self):
        self.config.write_text(f'[modulos.faro]\ncarpeta = "{self.bueno}"\n', encoding="utf-8")
        cfg = mod_config.cargar()
        self.assertEqual(cfg.modulos_rotos, ())
        self.assertEqual([(r["nombre"], r["estado"], r["dice"]) for r in doctor._modulos(Contexto(config=cfg))],
                         [("módulos", doctor.OK, "faro")])
        self.assertEqual(doctor._modulos(Contexto(config=Config(raiz=self.raiz))), [])

    def tolera(self, nombre: str) -> str:
        """Carga con y sin tolerancia: sin, es un error; con, `nombre` queda fuera. Devuelve el por qué."""
        with self.assertRaises(ErrorDeConfig):
            mod_config.cargar()
        cfg = mod_config.cargar(tolerar_modulos=True)
        self.assertIn(nombre, [n for n, _ in cfg.modulos_rotos])
        self.assertNotIn(nombre, [m.nombre for m in cfg.modulos])
        return dict(cfg.modulos_rotos)[nombre]

    def test_una_entrada_sin_carpeta_tambien(self):
        self.config.write_text(f'[modulos.faro]\ncarpeta = "{self.bueno}"\n[modulos.molino]\nfuente = "x"\n',
                               encoding="utf-8")
        self.assertIn("molino.fuente", self.tolera("molino"))
        self.config.write_text(f'[modulos.faro]\ncarpeta = "{self.bueno}"\n[modulos.molino]\nactivo = true\n',
                               encoding="utf-8")
        self.assertIn("carpeta", self.tolera("molino"))
        self.assertEqual([m.nombre for m in mod_config.cargar(tolerar_modulos=True).modulos], ["faro"])

    def test_una_pestana_que_no_vale_nombra_al_modulo(self):
        (self.bueno / "modulo.toml").write_text('[pestana]\ncomando = ["echo"]\nzzz = 3\n', encoding="utf-8")
        self.config.write_text(f'[modulos.faro]\ncarpeta = "{self.bueno}"\n', encoding="utf-8")
        por_que = self.tolera("faro")
        self.assertIn("[pestana]", por_que)
        self.assertIn("zzz", por_que)
        cfg = mod_config.cargar(tolerar_modulos=True)
        self.assertEqual(cfg.bloques, ())
        revisiones = doctor._modulos(Contexto(config=cfg))
        self.assertEqual([(r["nombre"], r["estado"]) for r in revisiones], [("módulos", doctor.FALLA)])
        self.assertIn("«faro» no se puede leer: la [pestana]", revisiones[0]["dice"])

    def test_una_pestana_que_choca_con_un_bloque_a_mano(self):
        (self.bueno / "modulo.toml").write_text('[pestana]\ncomando = ["echo"]\n', encoding="utf-8")
        self.config.write_text(f'[bloques.faro]\ncomando = ["true"]\n[modulos.faro]\ncarpeta = "{self.bueno}"\n',
                               encoding="utf-8")
        self.assertIn("a mano", self.tolera("faro"))
        cfg = mod_config.cargar(tolerar_modulos=True)
        self.assertEqual([b.comando for b in cfg.bloques], [("true",)])

    def test_instalar_tambien_deja_que_doctor_lo_diga(self):
        """`telar instalar` termina con doctor: recarga la configuración tolerando, como la orden."""
        from telar.ordenes import instalar

        llego = {}

        def main(argv, ctx):
            llego["ctx"] = ctx
            return 0

        with mock.patch.object(instalar, "_plan", lambda *a: []), mock.patch.object(doctor, "main", main), \
                contextlib.redirect_stdout(io.StringIO()):
            codigo = instalar.main(["--si"], Contexto(config=Config(raiz=self.raiz)))
        self.assertEqual(codigo, 0)
        self.assertEqual([n for n, _ in llego["ctx"].config.modulos_rotos], ["molino"])

    def test_uno_apagado_no_se_lee_ni_se_avisa(self):
        self.config.write_text(f'[modulos.molino]\ncarpeta = "{self.raiz / "no-esta"}"\nactivo = false\n',
                               encoding="utf-8")
        cfg = mod_config.cargar(tolerar_modulos=True)
        self.assertEqual(cfg.modulos_rotos, ())
        self.assertEqual(doctor._modulos(Contexto(config=cfg)), [])


class LaCarpetaTelarEnDoctor(Prueba):
    def test_el_perfil_de_antes_y_lo_local_en_git(self):
        import subprocess

        from telar.ordenes import doctor

        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            subprocess.run(["git", "init", "-q", str(raiz)], check=True)
            (raiz / "telar-perfil.yaml").write_text("version: 1\n")
            ctx = SimpleNamespace(config=SimpleNamespace(raiz=raiz, repos=()))
            [r] = doctor._carpeta_telar(ctx)
            self.assertEqual(r["estado"], doctor.FALLA)
            self.assertIn("git mv telar-perfil.yaml .telar/perfil.yaml", r["arreglo"])
            # pedido a mano en la configuración ([telar] perfil, [repos] perfil): se lee a propósito, no es un olvido
            self.assertEqual(doctor._carpeta_telar(SimpleNamespace(config=SimpleNamespace(
                raiz=raiz, repos=(), perfil=raiz / "telar-perfil.yaml"))), [])
            (raiz / ".telar").mkdir()
            (raiz / "telar-perfil.yaml").rename(raiz / ".telar" / "perfil.yaml")
            (raiz / ".telar" / "local.yaml").write_text("nombre: mío\n")
            self.assertEqual(doctor._carpeta_telar(ctx), [])  # sin commitear, nada que decir
            subprocess.run(["git", "-C", str(raiz), "add", ".telar/local.yaml"], check=True)
            [r] = doctor._carpeta_telar(ctx)
            self.assertEqual(r["estado"], doctor.AVISO)
            self.assertIn("git rm --cached .telar/local.yaml", r["arreglo"])


if __name__ == "__main__":
    unittest.main()