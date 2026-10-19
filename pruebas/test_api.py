"""`telar serve` (telar.api): las rutas son cáscaras de telar.servicios, con el mismo contrato que la CLI."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

try:
    from fastapi.testclient import TestClient

    from telar import api
    from telar.servicios import hoy as servicio
except ImportError:  # sin el extra «serve»
    api = None


def un_dia(**extra):
    return servicio.Hoy(ahora="2026-10-19T09:00:00", dia="lunes", fecha="2026-10-19", semana=43, local=False,
                        agenda=[servicio.Fila(texto="Comité", cuando="2026-10-19T09:30:00", clase="evento", lugar="sala 3")],
                        atencion=[], pendientes=[servicio.Fila(texto="T84 · medir", ref="T84")],
                        tiempo=servicio.Tiempo(), proveedores=servicio.Proveedores(declarados=["calendario"]), **extra)


@unittest.skipIf(api is None, "sin fastapi")
class LaApi(Prueba):
    """Cada prueba apaga la tarea de fondo (`_refrescar`): pediría el día de verdad."""

    def test_hoy_devuelve_lo_que_da_el_servicio_con_sus_campos_propios(self):
        with mock.patch.object(api.servicio_hoy, "hoy", return_value=un_dia()) as hoy, mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            r = TestClient(api.app).get("/hoy", params={"dia": "2026-10-19", "local": "true"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["agenda"][0]["lugar"], "sala 3")      # lo que agrega el proveedor viaja
        self.assertNotIn("hecho", d["pendientes"][0])              # lo que el servicio no puso, no aparece
        self.assertEqual(hoy.call_args.kwargs, {"dia": __import__("datetime").date(2026, 10, 19), "local": True})

    def test_un_dia_mal_escrito_es_un_422_sin_llamar_al_servicio(self):
        with mock.patch.object(api.servicio_hoy, "hoy") as hoy, mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            r = TestClient(api.app).get("/hoy", params={"dia": "ayer"})
        self.assertEqual(r.status_code, 422)
        hoy.assert_not_called()

    def test_la_cli_y_la_api_dicen_lo_mismo(self):
        from telar.ordenes import hoy as orden

        with mock.patch.object(servicio, "hoy", return_value=un_dia()), mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            salida = io.StringIO()
            with redirect_stdout(salida):
                orden.main(["--json"], SimpleNamespace())
            de_la_api = TestClient(api.app).get("/hoy").json()
        self.assertEqual(json.loads(salida.getvalue()), de_la_api)

    def test_la_configuracion_se_relee_cuando_cambia(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.toml"
            ruta.write_text('sesion = "una"\n')
            with mock.patch.dict(os.environ, {"TELAR_CONFIG": str(ruta)}):
                ctx = api._Contexto()
                self.assertEqual(ctx().config.sesion, "una")
                ruta.write_text('sesion = "otra"\n')
                os.utime(ruta, (1, 1))  # otra marca de tiempo, aunque el reloj no haya avanzado
                self.assertEqual(ctx().config.sesion, "otra")
