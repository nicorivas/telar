"""El catálogo de módulos y su ciclo (telar.catalogo, `telar modulos catalogo|instalar|activar|nuevo|revisar|publicar`),
con un repositorio git de verdad y un catálogo en una carpeta."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import catalogo, config as mod_config, modulos as mod_modulos

MANIFIESTO = '''descripcion = "Saluda, para probar."

[ordenes.hola]
comando = ["python3", "bin/hola.py"]
consulta = true

[permisos]
leer = []
escribir = []
red = false
ordenes = []
'''

CATALOGO = '''version = 1

[modulos.saludo]
descripcion = "Saluda, para probar."
fuente = "https://example.com/telar-saludo"
version = "v0.1.0"
etiquetas = ["prueba"]
telar = ">=0.1"
'''


def _git(carpeta, *args):
    subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@a", "GIT_COMMITTER_NAME": "a",
                        "GIT_COMMITTER_EMAIL": "a@a"})


class ElFormato(Prueba):
    def test_lee_las_entradas_y_deja_fuera_las_malas_con_su_motivo(self):
        texto = CATALOGO + '''
[modulos.Malo]
descripcion = "x"
fuente = "https://example.com/x"
version = "v1"

[modulos.sinfuente]
descripcion = "x"
version = "v1"

[modulos.rama]
descripcion = "x"
fuente = "file:///tmp/x"
version = "main"
'''
        entradas, problemas = catalogo.leer_texto(texto, catalogo="oficial", confianza="oficial")
        self.assertEqual([e.nombre for e in entradas], ["saludo"])
        self.assertEqual((entradas[0].version, entradas[0].etiquetas, entradas[0].confianza), ("v0.1.0", ("prueba",), "oficial"))
        self.assertEqual(len(problemas), 3)
        with self.assertRaises(catalogo.ErrorDeCatalogo):
            catalogo.leer_texto("version = 2\n")
        with self.assertRaises(catalogo.ErrorDeCatalogo):
            catalogo.leer_texto("no es toml =")

    def test_la_version_minima_de_telar(self):
        e = catalogo.leer_texto(CATALOGO)[0][0]
        self.assertTrue(catalogo.le_sirve(e, "0.5.1"))
        e2 = catalogo.Entrada("x", "x", "https://x", "v1", telar=">=9.1")
        self.assertFalse(catalogo.le_sirve(e2, "0.5.1"))

    def test_la_entrada_como_va_en_el_catalogo_se_vuelve_a_leer(self):
        e = {"nombre": "saludo", "descripcion": "Saluda.", "fuente": "https://example.com/s", "version": "v0.2.0",
             "autor": "ana", "etiquetas": ["a"], "telar": ">=0.6", "permisos": {"leer": [], "red": ["x.org"], "otros": {}}}
        leidas, problemas = catalogo.leer_texto("version = 1\n" + catalogo.entrada_toml(e))
        self.assertEqual((problemas, leidas[0].permisos), ([], {"red": ["x.org"]}))


class DondeSeLeen(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        (raiz / "equipo" / ".telar").mkdir(parents=True)
        (raiz / "equipo" / ".telar" / "catalogo.toml").write_text(CATALOGO.replace("saludo", "del-equipo"))
        self.config = SimpleNamespace(raiz=raiz, estado=raiz / ".estado", catalogos_oficial=True, catalogos_fuentes=(),
                                      repos=(mod_config.Repo("equipo", raiz / "equipo"),))

    def test_el_oficial_con_cache_y_los_del_equipo(self):
        bajadas = []

        def bajar(url):
            bajadas.append(url)
            return CATALOGO

        c = catalogo.cargar(self.config, bajar=bajar, ahora=1000)
        self.assertEqual({(e.nombre, e.confianza) for e in c["entradas"]}, {("saludo", "oficial"), ("del-equipo", "equipo")})
        catalogo.cargar(self.config, bajar=bajar, ahora=1500)  # dentro de la hora: de la caché
        self.assertEqual(len(bajadas), 1)
        catalogo.cargar(self.config, bajar=bajar, ahora=1500, forzar=True)
        self.assertEqual(len(bajadas), 2)

        def sin_red(url):
            raise OSError("sin red")

        c = catalogo.cargar(self.config, bajar=sin_red, forzar=True, ahora=9999)
        self.assertIn("saludo", [e.nombre for e in c["entradas"]])  # lo de antes
        self.assertTrue(any("sin red" in p for p in c["problemas"]))

    def test_sin_el_oficial_y_uno_mas_sin_revisar(self):
        otro = Path(self.tmp.name) / "otro.toml"
        otro.write_text(CATALOGO.replace("saludo", "suelto"))
        cfg = SimpleNamespace(**{**vars(self.config), "catalogos_oficial": False, "catalogos_fuentes": (str(otro),)})
        c = catalogo.cargar(cfg, bajar=lambda u: self.fail("no debería bajar"))
        self.assertEqual({(e.nombre, e.confianza) for e in c["entradas"]}, {("del-equipo", "equipo"), ("suelto", "sin revisar")})


class ElCiclo(Prueba):
    """Un módulo de verdad: un repo git con dos etiquetas, en un catálogo que es una carpeta."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.repo = d / "telar-saludo"
        (self.repo / "bin").mkdir(parents=True)
        (self.repo / "modulo.toml").write_text(MANIFIESTO)
        (self.repo / "bin" / "hola.py").write_text('import json; print(json.dumps({"hola": 1}))\n')
        (self.repo / "README.md").write_text("# saludo\n")
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "uno")
        _git(self.repo, "tag", "v0.1.0")
        (self.repo / "modulo.toml").write_text(MANIFIESTO.replace("Saluda, para probar.", "Saluda mejor."))
        _git(self.repo, "commit", "-q", "-am", "dos")
        _git(self.repo, "tag", "v0.2.0")
        _git(self.repo, "remote", "add", "origin", "https://github.com/ana/telar-saludo.git")
        entorno = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(d / "datos"), "XDG_CONFIG_HOME": str(d / "conf")})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.instalados = d / "conf" / "telar" / "modulos.toml"

    def test_instalar_en_una_etiqueta_actualizar_a_otra_apagar_y_encender(self):
        m, anotar = mod_modulos.preparar(str(self.repo), nombre="saludo", ref="v0.1.0")
        self.assertEqual(m.descripcion, "Saluda, para probar.")
        anotar["catalogo"] = "oficial"
        carpeta = mod_modulos.confirmar_instalacion(self.instalados, m, anotar)
        d = mod_modulos.leer_instalados(self.instalados)["saludo"]
        self.assertEqual((d["ref"], d["catalogo"]), ("v0.1.0", "oficial"))
        linea = mod_modulos.actualizar(self.instalados, "saludo", ref="v0.2.0")
        self.assertIn("→", linea)
        self.assertEqual(mod_modulos.leer(  "saludo", carpeta).descripcion, "Saluda mejor.")
        self.assertEqual(mod_modulos.leer_instalados(self.instalados)["saludo"]["ref"], "v0.2.0")
        # apagado: sigue anotado, pero la configuración no lo carga
        self.assertIn("apagado", mod_modulos.activar(self.instalados, "saludo", False))
        datos = mod_config._con_instalados({}, self.instalados.parent / "config.toml")
        self.assertNotIn("saludo", datos.get("modulos", {}))
        self.assertIn("activo", mod_modulos.activar(self.instalados, "saludo", True))
        datos = mod_config._con_instalados({}, self.instalados.parent / "config.toml")
        self.assertIn("saludo", datos["modulos"])

    def test_un_commit_que_no_existe(self):
        with self.assertRaises(mod_modulos.ErrorDeModulo):
            mod_modulos.preparar(str(self.repo), nombre="saludo", ref="v9.9.9")

    def test_revisar_y_publicar_en_seco(self):
        from telar.ordenes import modulos_publicar as pub

        self.assertEqual([g for g, _ in pub.revisar_carpeta(self.repo)], [])
        e = pub.entrada(self.repo, "v0.2.0", ["prueba"])
        self.assertEqual((e["nombre"], e["fuente"], e["version"]), ("saludo", "https://github.com/ana/telar-saludo", "v0.2.0"))
        self.assertEqual(e["permisos"], {"leer": [], "escribir": [], "red": False, "ordenes": []})
        salida = io.StringIO()
        ctx = SimpleNamespace(config=SimpleNamespace(repos=()))
        with redirect_stdout(salida):
            self.assertEqual(pub.main("publicar", [str(self.repo), "--version", "v0.2.0", "--seco", "--json"], ctx), 0)
        dicho = json.loads(salida.getvalue())
        self.assertEqual(dicho["catalogo"], catalogo.REPO_OFICIAL)
        self.assertEqual(dicho["plan"], [f"abrir un PR a {catalogo.REPO_OFICIAL} con la entrada de saludo"])  # ya etiquetada

    def test_revisar_lo_que_falta(self):
        from telar.ordenes import modulos_publicar as pub

        (self.repo / "modulo.toml").write_text('descripcion = "x"\n[ordenes.y]\ncomando = ["no-existe-este"]\n')
        fallas = [q for g, q in pub.revisar_carpeta(self.repo) if g == "falla"]
        self.assertTrue(any("[permisos]" in q for q in fallas))
        self.assertTrue(any("no-existe-este" in q for q in fallas))

    def test_nuevo_arma_uno_que_revisar_solo_le_pide_descripcion_y_origen(self):
        from telar.ordenes import modulos_publicar as pub

        carpeta = Path(self.tmp.name) / "telar-nuevo"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(pub.main("nuevo", ["nuevo", "--carpeta", str(carpeta)], SimpleNamespace(config=None)), 0)
        self.assertTrue((carpeta / "modulo.toml").is_file())
        fallas = [q for g, q in pub.revisar_carpeta(carpeta) if g == "falla"]
        self.assertEqual(len(fallas), 2, fallas)  # la descripción del ejemplo, y el repo sin origen
        with redirect_stderr(io.StringIO()):
            self.assertNotEqual(pub.main("nuevo", ["hilo"], SimpleNamespace(config=None)), 0)  # una orden de telar


class LaPagina(Prueba):
    def test_desde_la_pagina_no_se_instala_uno_sin_revisar(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import modulos as servicio

        suelto = catalogo.Entrada("suelto", "x", "https://x", "v1", catalogo="otro", confianza="sin revisar")
        with mock.patch.object(catalogo, "buscar", return_value=suelto):
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.hacer(SimpleNamespace(config=None), "instalar", "suelto")
        self.assertEqual(e.exception.codigo, 403)
        with self.assertRaises(ErrorDeServicio):
            servicio.hacer(SimpleNamespace(config=None), "borrar-todo", "x")


class LasSkills(Prueba):
    def test_telar_pone_hilos_y_modulos(self):
        from telar.agente import skill

        with tempfile.TemporaryDirectory() as d:
            for nombre in skill.SKILLS:
                ruta, estado = skill.instalar(Path(d), nombre=nombre)
                self.assertEqual(estado, "nueva")
                self.assertIn(f"name: {nombre}", ruta.read_text())
            self.assertIn("telar modulos publicar", skill.ruta(Path(d), "modulos").read_text())
            self.assertEqual(skill.desinstalar(Path(d), nombre="modulos")[1], "quitada")
