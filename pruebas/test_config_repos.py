"""`telar config --json` (y `GET /config`) muestra los repositorios de `[repos]` y de dónde vino cada módulo."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cli

try:
    from fastapi.testclient import TestClient

    from telar import api
except ImportError:  # sin el extra «serve»
    api = None

MANIFIESTO = 'descripcion = "el mar"\n'


class ConfigConReposYModulos(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        os.environ["TELAR_ESTADO"] = str(base / "estado")
        os.environ["TELAR_RAIZ"] = str(EJEMPLO)
        self.equipo = base / "equipo"
        self.equipo.mkdir()
        # un módulo a mano y otro instalado (lo que anota `telar modulo` en modulos.toml, al lado)
        self.a_mano = self._modulo("faro")
        self.instalado = self._modulo("molino")
        self.config = base / "config.toml"
        self.config.write_text(
            f'[repos.vida]\nruta = "{EJEMPLO}"\n'
            f'[repos.equipo]\nruta = "{self.equipo}"\nperfil = "perfiles/equipo.yaml"\n'
            f'[modulos.faro]\ncarpeta = "{self.a_mano}"\n', encoding="utf-8")
        (base / "modulos.toml").write_text(
            f'[molino]\ncarpeta = "{self.instalado}"\nfuente = "https://ejemplo.org/molino.git"\n'
            f'version = "a1b2c3d"\ninstalado = "2026-10-20"\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(self.config)

    def _modulo(self, nombre: str) -> Path:
        carpeta = Path(self.tmp.name) / "modulos" / nombre
        carpeta.mkdir(parents=True)
        (carpeta / "modulo.toml").write_text(MANIFIESTO, encoding="utf-8")
        return carpeta

    def correr(self, *argv: str) -> tuple[int, str, str]:
        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = cli.main(list(argv))
        return codigo, salida.getvalue(), error.getvalue()

    def json_config(self) -> dict:
        codigo, salida, error = self.correr("config", "--json")
        self.assertEqual(codigo, 0, error)
        return json.loads(salida)

    def test_los_repos_con_nombre_ruta_y_perfil(self):
        self.assertEqual(self.json_config()["repos"], [
            {"nombre": "vida", "ruta": str(EJEMPLO), "perfil": ""},
            {"nombre": "equipo", "ruta": str(self.equipo), "perfil": "perfiles/equipo.yaml"},
        ])

    def test_la_ruta_del_repo_sale_con_la_casa_expandida(self):
        self.config.write_text('[repos.casa]\nruta = "~/en-casa"\n', encoding="utf-8")
        ruta = self.json_config()["repos"][0]["ruta"]
        self.assertFalse(ruta.startswith("~"))
        self.assertEqual(ruta, str(Path("~/en-casa").expanduser()))

    def test_una_ruta_relativa_sale_tal_cual(self):
        """Como en `TELAR_REPOS`: el contrato no promete resolverla."""
        self.config.write_text('[repos.rel]\nruta = "equipo"\n', encoding="utf-8")
        self.assertEqual(self.json_config()["repos"], [{"nombre": "rel", "ruta": "equipo", "perfil": ""}])

    def test_sin_repos_la_lista_viene_vacia(self):
        self.config.write_text("", encoding="utf-8")
        (Path(self.tmp.name) / "modulos.toml").unlink()
        d = self.json_config()
        self.assertEqual((d["repos"], d["modulos"]), ([], []))

    def test_cada_modulo_dice_de_donde_vino(self):
        modulos = {m["nombre"]: m for m in self.json_config()["modulos"]}
        self.assertEqual(set(modulos), {"faro", "molino"})
        molino = modulos["molino"]
        self.assertEqual((molino["instalado"], molino["fuente"], molino["version"], molino["enlazado"]),
                         (True, "https://ejemplo.org/molino.git", "a1b2c3d", False))
        faro = modulos["faro"]
        self.assertEqual((faro["instalado"], faro["fuente"], faro["version"], faro["enlazado"]), (False, "", "", False))

    def test_los_campos_de_antes_siguen(self):
        """Solo se agregan campos: los que ya traía cada módulo, iguales."""
        m = next(m for m in self.json_config()["modulos"] if m["nombre"] == "faro")
        self.assertEqual(m["carpeta"], str(self.a_mano.resolve()))
        self.assertEqual((m["descripcion"], m["aporta"]), ("el mar", []))
        for clave in ("origen", "multiplexor", "raiz", "estado", "proveedores", "entorno"):
            self.assertIn(clave, self.json_config())

    def test_uno_enlazado(self):
        (Path(self.tmp.name) / "modulos.toml").write_text(
            f'[molino]\ncarpeta = "{self.instalado}"\nfuente = "{self.instalado}"\nenlazado = true\n', encoding="utf-8")
        molino = next(m for m in self.json_config()["modulos"] if m["nombre"] == "molino")
        self.assertEqual((molino["instalado"], molino["enlazado"], molino["fuente"]), (True, True, str(self.instalado)))

    def test_la_fuente_sale_sin_credenciales(self):
        (Path(self.tmp.name) / "modulos.toml").write_text(
            f'[molino]\ncarpeta = "{self.instalado}"\nfuente = "https://ana:secreto@ejemplo.org/molino.git"\n'
            f'version = "a1b2c3d"\n', encoding="utf-8")
        molino = next(m for m in self.json_config()["modulos"] if m["nombre"] == "molino")
        self.assertEqual(molino["fuente"], "https://ejemplo.org/molino.git")
        codigo, salida, error = self.correr("config")
        self.assertEqual(codigo, 0, error)
        self.assertNotIn("secreto", salida)
        self.assertIn("https://ejemplo.org/molino.git @ a1b2c3d", salida)

    def test_enlazado_solo_si_dice_true(self):
        """El texto "false" escrito a mano no es verdadero; una versión que no es texto no se inventa."""
        (Path(self.tmp.name) / "modulos.toml").write_text(
            f'[molino]\ncarpeta = "{self.instalado}"\nfuente = "{self.instalado}"\nenlazado = "false"\nversion = 7\n',
            encoding="utf-8")
        molino = next(m for m in self.json_config()["modulos"] if m["nombre"] == "molino")
        self.assertEqual((molino["enlazado"], molino["version"]), (False, ""))

    def test_sin_version_no_queda_la_arroba_colgando(self):
        (Path(self.tmp.name) / "modulos.toml").write_text(
            f'[molino]\ncarpeta = "{self.instalado}"\nfuente = "/otra/molino"\nenlazado = true\n', encoding="utf-8")
        for argv in (("config",), ("modulos",)):
            codigo, salida, error = self.correr(*argv)
            self.assertEqual(codigo, 0, error)
            linea = next(x for x in salida.splitlines() if "molino" in x)
            self.assertIn("/otra/molino", linea)
            self.assertNotIn("@", linea)

    def test_la_salida_para_leer_los_nombra(self):
        codigo, salida, error = self.correr("config")
        self.assertEqual(codigo, 0, error)
        self.assertIn("perfiles/equipo.yaml", salida)
        self.assertIn("https://ejemplo.org/molino.git @ a1b2c3d", salida)
        self.assertIn("(a mano)", salida)

    @unittest.skipIf(api is None, "sin fastapi")
    def test_la_api_entrega_lo_mismo(self):
        from telar.config import cargar
        from telar.cli import Contexto

        api.app.dependency_overrides[api.contexto] = lambda: Contexto(config=cargar(self.config))
        self.addCleanup(api.app.dependency_overrides.clear)
        d = TestClient(api.app).get("/config").json()
        # contra lo esperado, no contra la CLI: las dos salen de la misma función
        self.assertEqual([r["nombre"] for r in d["repos"]], ["vida", "equipo"])
        self.assertEqual(d["repos"][1], {"nombre": "equipo", "ruta": str(self.equipo), "perfil": "perfiles/equipo.yaml"})
        molino = next(m for m in d["modulos"] if m["nombre"] == "molino")
        self.assertEqual((molino["instalado"], molino["fuente"], molino["version"], molino["enlazado"]),
                         (True, "https://ejemplo.org/molino.git", "a1b2c3d", False))
        self.assertEqual(d["modulos"], self.json_config()["modulos"])


if __name__ == "__main__":
    unittest.main()
