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
    print(json.dumps({"dijo": p.get("texto", ""), "raiz": os.environ["TELAR_RAIZ"],
                      "repos": json.loads(os.environ["TELAR_REPOS"])}))
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


if __name__ == "__main__":
    unittest.main()
