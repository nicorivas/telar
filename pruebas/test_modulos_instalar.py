"""Los módulos como plugins (telar.modulos): sus órdenes, sus consultas, e instalarlos desde un repositorio git."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import modulos

MANIFIESTO = """nombre = "eco"
descripcion = "repite lo que le dicen"

[ordenes.decir]
descripcion = "lo escribe"
comando = ["bin/eco"]
consulta = true

[ordenes.solo]
comando = ["bin/eco"]

[instalar]
comando = ["bin/eco", "--instalar"]
"""

# lee JSON de la entrada (consulta) o argumentos (orden), y dice lo que sabe de telar
ECO = """#!/usr/bin/env python3
import json, os, sys
if "--instalar" in sys.argv:
    open("instalado", "w").write("si")
    sys.exit(0)
if os.environ.get("TELAR_CONSULTA"):
    p = json.load(sys.stdin)
    if p.get("fallar"):
        print("se cayó a propósito", file=sys.stderr); sys.exit(3)
    if p.get("rechazar"):  # como lo dice un módulo: {"error", "codigo"} y sale con 1
        print(json.dumps({"error": "cambió desde que la leíste", "codigo": p["rechazar"]})); sys.exit(1)
    print(json.dumps({"dijo": p.get("texto", ""), "raiz": os.environ["TELAR_RAIZ"],
                      "repos": json.loads(os.environ["TELAR_REPOS"]), "persona": os.environ.get("TELAR_PERSONA")}))
else:
    print("eco:", " ".join(sys.argv[1:]))
"""


def git(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout


class LosModulosComoPlugins(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / "telar-eco"
        (self.repo / "bin").mkdir(parents=True)
        (self.repo / "modulo.toml").write_text(MANIFIESTO)
        eco = self.repo / "bin" / "eco"
        eco.write_text(ECO)
        eco.chmod(eco.stat().st_mode | stat.S_IEXEC)
        git(self.repo, "init", "-q", "-b", "main")
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            git(self.repo, "config", k, v)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "eco")
        self.conf = base / "conf"
        self.conf.mkdir()
        (self.conf / "config.toml").write_text(f'raiz = "{base}"\nestado = "{base / "estado"}"\n')
        entorno = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(base / "datos")})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.instalados = self.conf / modulos.INSTALADOS

    def instalar(self, **kw):
        m, anotar = modulos.preparar(str(self.repo), **kw)
        return modulos.confirmar_instalacion(self.instalados, m, anotar)

    def config(self):
        return cfg.cargar(self.conf / "config.toml")

    def test_instalar_lo_clona_corre_su_instalar_y_lo_anota(self):
        carpeta = self.instalar()
        self.assertEqual(carpeta, Path(self.tmp.name) / "datos" / "telar" / "modulos" / "eco")
        self.assertEqual((carpeta / "instalado").read_text(), "si")
        anotado = modulos.leer_instalados(self.instalados)["eco"]
        self.assertEqual((anotado["fuente"], len(anotado["version"]) >= 7), (str(self.repo.resolve()), True))
        m = modulos.buscar(self.config(), "eco")
        self.assertEqual(m.carpeta, carpeta.resolve())
        self.assertIn("orden decir (consulta)", m.aporta)
        with self.assertRaises(modulos.ErrorDeModulo):  # dos veces, no
            self.instalar()

    def test_una_consulta_recibe_json_y_lo_que_sabe_de_telar(self):
        self.instalar()
        r = modulos.consultar(self.config(), "eco", "decir", {"texto": "hola"})
        self.assertEqual((r["dijo"], r["raiz"], r["repos"]), ("hola", str(Path(self.tmp.name)), []))
        with self.assertRaises(modulos.ErrorDeModulo) as e:
            modulos.consultar(self.config(), "eco", "decir", {"fallar": True})
        self.assertIn("se cayó a propósito", str(e.exception))
        with self.assertRaises(modulos.ErrorDeModulo):  # una orden sin consulta no se pregunta
            modulos.consultar(self.config(), "eco", "solo", {})

    def test_la_persona_es_la_del_bus_o_el_usuario(self):
        import getpass

        self.instalar()
        os.environ.pop("TELAR_PERSONA", None)  # (mock.patch.dict del setUp lo devuelve como estaba)
        self.assertEqual(modulos.consultar(self.config(), "eco", "decir", {})["persona"], getpass.getuser())
        (self.conf / "config.toml").write_text((self.conf / "config.toml").read_text() + '\n[bus]\npersona = "ana"\n')
        self.assertEqual(modulos.consultar(self.config(), "eco", "decir", {})["persona"], "ana")
        # la del entorno le gana (como TELAR_RAIZ a raiz): una prueba la fija así
        with mock.patch.dict(os.environ, {"TELAR_PERSONA": "berta"}):
            self.assertEqual(modulos.consultar(self.config(), "eco", "decir", {})["persona"], "berta")

    def test_lo_que_el_modulo_rechaza_llega_con_su_codigo(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import modulos as servicio

        self.instalar()
        with self.assertRaises(modulos.ErrorDeConsulta) as e:
            modulos.consultar(self.config(), "eco", "decir", {"rechazar": 409})
        self.assertEqual((e.exception.codigo, str(e.exception)), (409, "cambió desde que la leíste"))
        ctx = SimpleNamespace(config=self.config())
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.consultar(ctx, "eco", "decir", {"rechazar": 409})
        self.assertEqual((e.exception.codigo, str(e.exception)), (409, "cambió desde que la leíste"))
        # por el bus, a la otra máquina, con el mismo código
        r = servicio.para_otra(ctx, {"modulo": "eco", "verbo": "decir", "params": {"rechazar": 403}})
        self.assertEqual((r["ok"], r["codigo"]), (False, 403))
        # un código que no es 4xx es una falla del módulo, como una salida sin JSON
        for raro in (500, "409", True):
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.consultar(ctx, "eco", "decir", {"rechazar": raro})
            self.assertEqual(e.exception.codigo, 502, raro)
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.consultar(ctx, "eco", "decir", {"fallar": True})
        self.assertEqual(e.exception.codigo, 502)

    def test_su_periodico_corre_con_lo_que_sabe_de_telar(self):
        (self.repo / "modulo.toml").write_text(MANIFIESTO + '\n[periodicos.medir]\ncuando = "0 7 * * *"\n'
                                               'comando = "echo modulo=$TELAR_MODULO persona=$TELAR_PERSONA raiz=$TELAR_RAIZ"\n')
        git(self.repo, "commit", "-qam", "periodico")
        carpeta = self.instalar()
        from telar import periodicos as mod_periodicos

        config = self.config()
        p = mod_periodicos.con_modulos(mod_periodicos.Archivo(), config).por_nombre("eco-medir")
        r = mod_periodicos.correr(SimpleNamespace(config=config), p)
        self.assertEqual(r["codigo"], 0)
        log = mod_periodicos.log(config, "eco-medir")
        self.assertIn(f"modulo={carpeta.resolve()}", log)
        self.assertIn(f"raiz={Path(self.tmp.name)}", log)
        self.assertRegex(log, r"persona=\S+")

    def test_su_orden_se_llama_como_una_de_telar(self):
        self.instalar()
        from telar import cli

        salida = subprocess.run([os.sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); from telar import cli; "
                                 f"raise SystemExit(cli.main(['--config', {str(self.conf / 'config.toml')!r}, 'eco', 'solo', 'uno', 'dos']))"],
                                capture_output=True, text=True, env={**os.environ}, cwd=Path(__file__).parent.parent)
        self.assertEqual((salida.returncode, salida.stdout.strip()), (0, "eco: uno dos"), salida.stderr)
        self.assertNotEqual(cli.main(["--config", str(self.conf / "config.toml"), "noexiste"]), 0)

    def test_actualizar_trae_lo_nuevo_y_quitar_borra_lo_que_bajo(self):
        carpeta = self.instalar()
        (self.repo / "LEEME").write_text("nuevo")
        git(self.repo, "add", "LEEME")
        git(self.repo, "commit", "-q", "-m", "nuevo")
        self.assertIn("→", modulos.actualizar(self.instalados, "eco"))
        self.assertTrue((carpeta / "LEEME").exists())
        modulos.quitar(self.instalados, "eco")
        self.assertFalse(carpeta.exists())
        self.assertIsNone(modulos.buscar(self.config(), "eco"))

    def test_enlazado_usa_la_carpeta_y_no_la_borra(self):
        carpeta = self.instalar(enlazar=True)
        self.assertEqual(carpeta, self.repo.resolve())
        modulos.quitar(self.instalados, "eco")
        self.assertTrue(self.repo.exists())

    def test_el_contexto_del_agente_va_en_una_linea_y_con_tope(self):
        (self.repo / "modulo.toml").write_text(MANIFIESTO + '\n[contexto]\ntexto = """Hay un grafo:\n  úsalo."""\n')
        self.assertEqual(modulos.leer("eco", self.repo).contexto, "Hay un grafo: úsalo.")
        (self.repo / "modulo.toml").write_text(MANIFIESTO + f'\n[contexto]\ntexto = "{"x" * 700}"\n')
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.leer("eco", self.repo)

    def test_su_icono_es_un_png_de_su_carpeta(self):
        (self.repo / "modulo.toml").write_text('icono = "icono.png"\n' + MANIFIESTO)
        self.assertEqual(modulos.leer("eco", self.repo).icono, self.repo.resolve() / "icono.png")
        (self.repo / "modulo.toml").write_text('icono = "icono.svg"\n' + MANIFIESTO)
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.leer("eco", self.repo)
        (self.repo / "modulo.toml").write_text(MANIFIESTO)
        self.assertIsNone(modulos.leer("eco", self.repo).icono)

    def test_su_configuracion_es_un_comando_de_su_carpeta(self):
        (self.repo / "modulo.toml").write_text(MANIFIESTO + '\n[configurar]\ncomando = ["bin/eco", "configurar"]\n')
        m = modulos.leer("eco", self.repo)
        self.assertEqual(m.configurar["comando"][0], str(self.repo.resolve() / "bin" / "eco"))
        self.assertIn("configuración", m.aporta)
        (self.repo / "modulo.toml").write_text(MANIFIESTO + '\n[configurar]\ncomando = "bin/eco"\n')
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.leer("eco", self.repo)

    def test_adoptar_uno_declarado_a_mano(self):
        conf = self.conf / "config.toml"
        conf.write_text(conf.read_text() + f'\n# los módulos\n[modulos.eco]\ncarpeta = "{self.repo}"\n\n# lo que sigue\n[dashboard]\norden = ["ahora"]\n')
        self.assertIsNotNone(modulos.buscar(self.config(), "eco"))
        hecho = modulos.adoptar(self.instalados, conf, "eco")
        self.assertIn("adoptado", hecho)
        texto = conf.read_text()
        self.assertNotIn("[modulos.eco]", texto)
        self.assertIn("# lo que sigue\n[dashboard]", texto)
        self.assertTrue((self.conf / "config.toml.antes-adoptar-eco").exists())
        d = modulos.leer_instalados(self.instalados)["eco"]
        self.assertEqual((d["carpeta"], d["enlazado"]), (str(self.repo.resolve()), True))
        self.assertEqual(modulos.buscar(self.config(), "eco").carpeta, self.repo.resolve())  # sigue ahí
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.adoptar(self.instalados, conf, "eco")

    def test_lo_que_requiere_se_mira_antes_de_instalar(self):
        (self.repo / "modulo.toml").write_text(MANIFIESTO + '\n[requiere]\nprogramas = ["no-existe-este-programa"]\n')
        git(self.repo, "commit", "-qam", "requiere")
        with self.assertRaises(modulos.ErrorDeModulo) as e:
            self.instalar()
        self.assertIn("no-existe-este-programa", str(e.exception))
        self.assertNotIn("eco", modulos.leer_instalados(self.instalados))
        self.assertEqual(list((Path(self.tmp.name) / "datos" / "telar" / "modulos").iterdir()), [])

    def test_instalar_uno_con_periodicos_deja_el_crontab_al_dia(self):
        (self.repo / "modulo.toml").write_text(MANIFIESTO + '\n[periodicos.medir]\ncuando = "0 7 * * *"\ncomando = "bin/eco"\n')
        git(self.repo, "commit", "-qam", "periodico")
        from telar import periodicos as mod_periodicos
        from telar.ordenes import modulos as orden

        with mock.patch.object(mod_periodicos, "aplicar") as aplicar, mock.patch("sys.stdout"):
            codigo = orden.main(["instalar", str(self.repo), "--si"], SimpleNamespace(config=self.config()))
        self.assertEqual(codigo, 0)
        archivo = aplicar.call_args.args[0]
        self.assertIn("eco-medir", [x.nombre for x in archivo.procesos])
        with mock.patch.object(mod_periodicos, "aplicar") as aplicar, mock.patch("sys.stdout"):
            orden.main(["quitar", "eco", "--si"], SimpleNamespace(config=self.config()))
        self.assertNotIn("eco-medir", [x.nombre for x in aplicar.call_args.args[0].procesos])

    def test_un_manifiesto_roto_no_queda_a_medias(self):
        (self.repo / "modulo.toml").write_text('[ordenes.decir]\ncomando = "bin/eco"\n')
        git(self.repo, "commit", "-qam", "roto")
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.preparar(str(self.repo))
        self.assertEqual([p for p in (Path(self.tmp.name) / "datos" / "telar" / "modulos").iterdir()], [])

    def test_uno_instalado_despues_de_arrancar_se_encuentra(self):
        from telar.servicios import modulos as servicio

        ctx = SimpleNamespace(config=self.config())  # como telar serve: leída antes de instalarlo
        self.instalar()
        self.assertEqual(servicio.consultar(ctx, "eco", "decir", {"texto": "b"})["dijo"], "b")

    def test_la_api_y_el_bus(self):
        self.instalar()
        from telar.servicios import modulos as servicio

        ctx = SimpleNamespace(config=self.config())
        self.assertEqual(servicio.consultar(ctx, "eco", "decir", {"texto": "a"})["dijo"], "a")
        r = servicio.para_otra(ctx, {"modulo": "nada", "verbo": "x", "params": {}})
        self.assertEqual((r["ok"], r["codigo"]), (False, 404))
        from telar import bus

        with mock.patch.object(bus, "hay_bus", return_value=True), mock.patch.object(bus, "maquina", return_value="laptop"), \
                mock.patch.object(bus, "pedir", return_value={"ok": True, "respuesta": {"dijo": "lejos"}}) as pedir:
            self.assertEqual(servicio.consultar(ctx, "eco", "decir", {"texto": "x"}, "telar"), {"dijo": "lejos"})
            self.assertEqual(pedir.call_args.args[1:4], ("telar", "modulo", {"modulo": "eco", "verbo": "decir", "params": {"texto": "x"}}))



# imprime una página que dice lo que sabe de telar (su pestaña, su app y su configuración), o el detalle de un ítem
PAGINA = """#!/usr/bin/env python3
import json, os, sys
sabe = {k: os.environ.get(k, "") for k in ("TELAR_RAIZ", "TELAR_REPOS", "TELAR_MAQUINA", "TELAR_MODULO")}
if "--item" in sys.argv:
    print(json.dumps({"texto": json.dumps(sabe)}))
else:
    print(json.dumps({"titulo": sys.argv[1], "bloques": [{"texto": json.dumps(sabe)}]}))
"""


class LasPaginasDeUnModulo(Prueba):
    """Su pestaña, su app y su configuración corren con el entorno de sus órdenes (TELAR_RAIZ, TELAR_REPOS…); una
    pestaña o una app declarada a mano, con el de telar."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.modulo = base / "telar-mira"
        (self.modulo / "bin").mkdir(parents=True)
        guion = self.modulo / "bin" / "pagina"
        guion.write_text(PAGINA)
        guion.chmod(guion.stat().st_mode | stat.S_IEXEC)
        (self.modulo / "modulo.toml").write_text(
            'nombre = "mira"\ndescripcion = "dice lo que sabe"\n'
            '[pestana]\nnombre = "mira"\ncomando = ["bin/pagina", "pestana"]\n'
            '[app]\npagina = ["bin/pagina", "app"]\n'
            '[configurar]\ncomando = ["bin/pagina", "configurar"]\n')
        (base / "repo").mkdir()
        self.ruta = base / "config.toml"
        self.ruta.write_text(f'raiz = "{base}"\nestado = "{base / "estado"}"\n'
                             f'[repos.equipo]\nruta = "{base / "repo"}"\n'
                             f'[modulos.mira]\ncarpeta = "{self.modulo}"\n'
                             f'[bloques.amano]\ncomando = ["{guion}", "a mano"]\n'
                             f'[apps.otra]\npagina = ["{guion}", "otra"]\n')
        from telar.cli import Contexto

        self.ctx = Contexto(config=cfg.cargar(self.ruta))

    def sabe(self, pagina) -> dict:
        return json.loads(pagina.bloques[0]["texto"])

    def test_su_pestana_su_app_y_su_configuracion_saben_de_telar(self):
        from telar.servicios import bloques, paginas
        from telar.servicios import modulos as servicio_modulos

        base = Path(self.tmp.name)
        for pagina in (bloques.pagina(self.ctx, "mira"), paginas.app(self.ctx, "mira"),
                       servicio_modulos.configuracion(self.ctx, "mira")):
            sabe = self.sabe(pagina)
            self.assertEqual(sabe["TELAR_RAIZ"], str(base), pagina.titulo)
            self.assertEqual(sabe["TELAR_MODULO"], str(self.modulo.resolve()), pagina.titulo)
            self.assertEqual([(r["nombre"], r["ruta"]) for r in json.loads(sabe["TELAR_REPOS"])],
                             [("equipo", str(base / "repo"))], pagina.titulo)
        self.assertEqual([p.titulo for p in (bloques.pagina(self.ctx, "mira"), paginas.app(self.ctx, "mira"))],
                         ["pestana", "app"])
        # el detalle de un ítem de su pestaña, también
        detalle = json.loads(bloques.item(self.ctx, "mira", "uno").texto)
        self.assertEqual(detalle["TELAR_MODULO"], str(self.modulo.resolve()))

    def test_lo_declarado_a_mano_corre_con_el_entorno_de_telar(self):
        from telar.servicios import bloques, paginas

        for pagina in (bloques.pagina(self.ctx, "amano"), paginas.app(self.ctx, "otra")):
            self.assertEqual(self.sabe(pagina), {"TELAR_RAIZ": "", "TELAR_REPOS": "", "TELAR_MAQUINA": "", "TELAR_MODULO": ""},
                             pagina.titulo)
        self.assertIsNone(modulos.entorno_de(self.ctx.config, "amano", "pestana"))
        self.assertIsNone(modulos.entorno_de(self.ctx.config, "mira", "fondo"))  # no trae fondo
        self.assertEqual(modulos.entorno_de(self.ctx.config, "mira", "app")["TELAR_MODULO"], str(self.modulo.resolve()))

if __name__ == "__main__":
    unittest.main()
