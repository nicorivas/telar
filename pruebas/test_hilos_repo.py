"""`telar hilos` dice el repo de cada hilo: el de `[repos]` donde vive su carpeta (telar.perfil.repo_de)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import EJEMPLO, HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cli
from telar.ordenes import hilos as orden
from telar.servicios import hilos as servicio


class HilosConRepo(Prueba):
    """El ejemplo como repo «vida» y una de sus carpetas como repo «taller», adentro: gana el más hondo."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        os.environ["TELAR_ESTADO"] = str(base / "estado")
        os.environ["TELAR_RAIZ"] = str(EJEMPLO)
        os.environ["TELAR_SESION"] = f"telar-pruebas-{uuid.uuid4().hex[:8]}"
        self.config = base / "config.toml"
        self.escribir_config(
            f'[repos.vida]\nruta = "{EJEMPLO}"\n'
            f'[repos.taller]\nruta = "{EJEMPLO / "proyectos" / "molino"}"\n')
        self.afuera = base / "afuera"
        self.afuera.mkdir()
        (self.afuera / "README.md").write_text("# Afuera\n", encoding="utf-8")
        previo = os.environ.get("COLUMNS")
        os.environ["COLUMNS"] = "120"
        self.addCleanup(lambda: os.environ.pop("COLUMNS", None) if previo is None
                        else os.environ.__setitem__("COLUMNS", previo))

    def escribir_config(self, texto: str) -> None:
        self.config.write_text(texto, encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(self.config)

    def correr(self, *argv: str) -> tuple[int, str, str]:
        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = cli.main(list(argv))
        return codigo, salida.getvalue(), error.getvalue()

    def vincular(self, ruta: str, hilo: str) -> None:
        codigo, _, error = self.correr("hilo", "vincular", ruta, "--hilo", hilo)
        self.assertEqual(codigo, 0, error)

    def repos(self) -> dict[str, str]:
        codigo, salida, error = self.correr("hilos", "--json")
        self.assertEqual(codigo, 0, error)
        return {h["nombre"]: h["repo"] for h in json.loads(salida)["hilos"]}

    def test_cada_hilo_trae_el_repo_de_su_carpeta(self):
        self.vincular("proyectos/faro", "Faro")
        self.vincular("proyectos/molino", "Molino")
        self.vincular(str(self.afuera), "Afuera")
        self.assertEqual(self.repos(), {"Faro": "vida", "Molino": "taller", "Afuera": ""})

    def test_sin_repos_declarados_el_repo_va_vacio(self):
        self.escribir_config("")
        self.vincular("proyectos/faro", "Faro")
        self.assertEqual(self.repos(), {"Faro": ""})

    def test_con_sin_ficha_tambien_viene(self):
        self.vincular("proyectos/molino", "Molino")
        codigo, salida, error = self.correr("hilos", "--json", "--sin-ficha")
        self.assertEqual(codigo, 0, error)
        self.assertEqual(json.loads(salida)["hilos"][0]["repo"], "taller")

    def test_un_hilo_sin_carpeta_no_es_de_ningun_repo(self):
        """Aunque la raíz misma esté en `[repos]`: sin carpeta no hay de dónde decirlo."""
        from telar.config import cargar
        cuerpo = servicio._con_repo({}, SimpleNamespace(ruta=None), cargar())
        self.assertEqual(cuerpo, {"repo": ""})

    def test_los_demas_campos_del_hilo_no_cambian(self):
        self.vincular("proyectos/faro", "Faro")
        codigo, salida, _ = self.correr("hilos", "--json")
        hilo = json.loads(salida)["hilos"][0]
        self.assertEqual(hilo["relativa"], "proyectos/faro")
        self.assertEqual(hilo["direccion"], "hilo:Faro")
        self.assertIn("ficha", hilo)

    def test_el_texto_nombra_el_repo_si_hay_mas_de_uno(self):
        self.vincular("proyectos/faro", "Faro")
        self.vincular("proyectos/molino", "Molino")
        codigo, salida, error = self.correr("hilos")
        self.assertEqual(codigo, 0, error)
        faro = next(l for l in salida.splitlines() if "Faro" in l)
        molino = next(l for l in salida.splitlines() if "Molino" in l)
        self.assertIn("vida", faro)
        self.assertIn("taller", molino)

    def test_con_un_solo_repo_el_texto_no_lo_repite(self):
        self.vincular("proyectos/faro", "Faro")
        self.vincular("proyectos/arboleda", "Arboleda")
        codigo, salida, error = self.correr("hilos")
        self.assertEqual(codigo, 0, error)
        self.assertNotIn("vida", salida)

    def test_la_linea_sin_repos_es_la_de_siempre(self):
        hilo = servicio.Hilo(id="@1", nombre="Faro", vivo=True, relativa="proyectos/faro",
                             ruta="/r/proyectos/faro", repo="vida")
        self.assertEqual(orden._linea(hilo, 100), orden._linea(hilo, 100, False))
        self.assertNotIn("vida", orden._linea(hilo, 100))
        self.assertIn("vida", orden._linea(hilo, 100, True))
        # uno sin repo pero con carpeta se marca con «—», para que la columna no se corra
        suelto = hilo.model_copy(update={"repo": ""})
        self.assertIn("—", orden._linea(suelto, 100, True).split("proyectos/faro", 1)[1])


@unittest.skipUnless(HAY_FASTAPI, "sin el extra «serve»")
class LaApiTraeElRepo(Prueba):
    def test_get_hilos_trae_el_repo(self):
        from fastapi.testclient import TestClient

        from telar import api

        uno = servicio.Hilos(sesion="s", viva=True, raiz="/r", multiplexor="tmux", orden="mux",
                             hilos=[servicio.Hilo(id="@1", nombre="Faro", ruta="/r/faro", repo="vida")])
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()), \
                mock.patch.object(servicio, "hilos", return_value=uno):
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                orden.main(["--json"], SimpleNamespace())
            cli_json = json.loads(salida.getvalue())
            api_json = TestClient(api.app).get("/hilos").json()
        self.assertEqual(api_json["hilos"][0]["repo"], "vida")
        self.assertEqual(cli_json, api_json)


if __name__ == "__main__":
    unittest.main()
