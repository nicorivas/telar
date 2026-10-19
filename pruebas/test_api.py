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


@unittest.skipIf(api is None, "sin fastapi")
class HilosYConfig(Prueba):
    """`/hilos` y `/config`: lo mismo que la CLI, con los parámetros validados."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(api, "_refrescar", mock.AsyncMock())
        p.start()
        self.addCleanup(p.stop)

    def test_hilos_pasa_sus_parametros_y_rechaza_un_orden_que_no_existe(self):
        from telar.servicios import hilos as sh

        vacio = sh.Hilos(sesion="s", viva=True, raiz="/r", multiplexor="tmux", orden="mux", hilos=[])
        with mock.patch.object(api.servicio_hilos, "hilos", return_value=vacio) as h:
            r = TestClient(api.app).get("/hilos", params={"ficha": "false", "red": "true"})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(h.call_args.kwargs, {"vivos": False, "red": True, "con_ficha": False, "orden": ""})
            self.assertEqual(TestClient(api.app).get("/hilos", params={"orden": "al-azar"}).status_code, 422)

    def test_la_cli_y_la_api_dicen_lo_mismo_de_los_hilos(self):
        from telar.ordenes import hilos as orden
        from telar.servicios import hilos as sh

        uno = sh.Hilos(sesion="s", viva=True, raiz="/r", multiplexor="tmux", orden="mux",
                       hilos=[sh.Hilo(id="@1", nombre="Faro", vivo=True, relativa="faro", extra_de_alguien=1)])
        with mock.patch.object(sh, "hilos", return_value=uno):
            salida = io.StringIO()
            with redirect_stdout(salida):
                orden.main(["--json"], SimpleNamespace())
            self.assertEqual(json.loads(salida.getvalue()), TestClient(api.app).get("/hilos").json())

    def test_config_es_la_de_la_cli(self):
        from telar.ordenes import config as orden
        from telar.servicios import config as sc

        r = sc.ConfigResuelta(multiplexor="tmux", sesion="s", raiz="/r", estado="/e", persona="nico")
        with mock.patch.object(sc, "resuelta", return_value=r):
            salida = io.StringIO()
            with redirect_stdout(salida):
                orden.main(["--json"], SimpleNamespace(config=SimpleNamespace(origen=None)))
            self.assertEqual(json.loads(salida.getvalue()), TestClient(api.app).get("/config").json())


class CuentaDeGws(Prueba):
    """La cuenta de gws se pregunta una vez y vale 10 minutos: la pregunta puede tardar."""

    def test_la_segunda_vez_no_se_pregunta(self):
        from telar.servicios import config as sc

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}), \
                mock.patch.object(sc, "_preguntar_gws", return_value=("yo@ejemplo.org", True)) as preguntar:
            self.assertEqual(sc._cuenta_gws("gws"), ("yo@ejemplo.org", True))
            self.assertEqual(sc._cuenta_gws("gws"), ("yo@ejemplo.org", True))
            self.assertEqual(preguntar.call_count, 1)
            self.assertEqual(sc._cuenta_gws("otro-gws"), ("yo@ejemplo.org", True))  # otro programa: se pregunta
            self.assertEqual(preguntar.call_count, 2)


@unittest.skipIf(api is None, "sin fastapi")
class TareasBloquesResultados(Prueba):
    """Las rutas de tareas, bloques y resultados: cáscaras de sus servicios, y los errores con su código."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(api, "_refrescar", mock.AsyncMock())
        p.start()
        self.addCleanup(p.stop)
        self.c = TestClient(api.app)

    def test_un_error_del_servicio_es_su_codigo_con_el_mensaje_de_la_cli(self):
        from telar.servicios import ErrorDeServicio

        with mock.patch.object(api.servicio_tareas, "ficha", side_effect=ErrorDeServicio("no hay proveedor activo «x»", 404)):
            r = self.c.get("/tareas/T7", params={"proveedor": "x"})
        self.assertEqual((r.status_code, r.json()), (404, {"detail": "no hay proveedor activo «x»"}))

    def test_un_id_con_lo_que_sea_llega_entero(self):
        from telar.servicios import Pagina

        with mock.patch.object(api.servicio_tareas, "ficha", return_value=Pagina(titulo="x")) as ficha:
            self.c.get("/tareas/2026-10-05 lectura·rara", params={"proveedor": "lecturas"})
        self.assertEqual(ficha.call_args[0][1:], ("2026-10-05 lectura·rara", "lecturas"))

    def test_una_accion_llega_con_su_rol_o_su_numero_y_su_texto(self):
        from telar.servicios import tareas as st

        hecha = st.AccionHecha(tipo="comando", hecho="✓ hecha")
        with mock.patch.object(api.servicio_tareas, "accion", return_value=hecha) as accion:
            r = self.c.post("/tareas/T7/accion", json={"rol": "hecha"})
            self.c.post("/tareas/T7/accion", json={"n": 2, "texto": "sigue viva", "proveedor": "tareas"})
        self.assertEqual(r.json()["hecho"], "✓ hecha")
        self.assertEqual(accion.call_args_list[0].kwargs, {"n": None, "rol": "hecha", "texto": ""})
        self.assertEqual(accion.call_args_list[1].kwargs, {"n": 2, "rol": "", "texto": "sigue viva"})

    def test_la_cli_y_la_api_dan_la_misma_pagina_de_un_bloque(self):
        from telar.ordenes import bloque as orden
        from telar.servicios import Pagina
        from telar.servicios import bloques as sb

        pagina = Pagina(titulo="correo", bloques=[{"titulo": "hoy", "items": [{"texto": "hola", "id": "1a"}]}], extra=True)
        with mock.patch.object(sb, "pagina", return_value=pagina):
            salida = io.StringIO()
            with redirect_stdout(salida):
                orden.main(["correo", "--json"], SimpleNamespace(config=SimpleNamespace(bloques=())))
            self.assertEqual(json.loads(salida.getvalue()), self.c.get("/bloques/correo").json())

    def test_un_comentario_va_al_servicio_con_su_dia(self):
        from telar.servicios import resultados as sr

        with mock.patch.object(api.servicio_resultados, "comentar", return_value=sr.Comentario(ok=True, abrio="✎ plan")) as comentar:
            r = self.c.post("/resultados/plan/comentario", json={"dia": "2026-10-19", "texto": "falta algo"})
        self.assertEqual(r.json(), {"ok": True, "abrio": "✎ plan"})
        self.assertEqual(comentar.call_args[0][1:], ("plan", "2026-10-19", "falta algo"))


@unittest.skipIf(api is None, "sin fastapi")
class TiposTarea(Prueba):
    """`/tipos/tarea`: las tareas desde el índice, y las acciones con su versión."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(api, "_refrescar", mock.AsyncMock())
        p.start()
        self.addCleanup(p.stop)
        import shutil
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T1.md").write_text("---\ntitulo: Una\nestado: activa\narea: trabajo\n---\n", encoding="utf-8")
        (self.dir / "T2.md").write_text("---\ntitulo: Otra\nestado: hecha\ncerrada: 2026-10-01\n---\n", encoding="utf-8")
        from telar.config import Config, Tipo
        cfg = Config(raiz=self.dir, estado=self.dir / "estado", tipos=(Tipo(clave="tarea", carpeta=str(self.dir)),))
        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg)
        self.addCleanup(api.app.dependency_overrides.clear)
        api._indices.clear()
        self.c = TestClient(api.app)

    def test_lista_las_abiertas_con_su_version(self):
        r = self.c.get("/tipos/tarea").json()
        self.assertEqual([t["id"] for t in r["tareas"]], ["T1"])
        self.assertEqual(len(r["tareas"][0]["version"]), 16)
        self.assertEqual(len(self.c.get("/tipos/tarea", params={"abiertas": "false"}).json()["tareas"]), 2)

    def test_una_accion_con_la_version_leida_escribe_y_devuelve_la_nueva(self):
        v = self.c.get("/tipos/tarea/T1").json()["version"]
        r = self.c.post("/tipos/tarea/T1/completar", json={"version": v, "params": {"nota": "listo"}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["estado"], "hecha")
        self.assertNotEqual(r.json()["version"], v)
        self.assertIn("estado: hecha", (self.dir / "T1.md").read_text())

    def test_con_una_version_vieja_409_y_la_de_ahora(self):
        v = self.c.get("/tipos/tarea/T1").json()["version"]
        (self.dir / "T1.md").write_text("---\ntitulo: Una, editada a mano\nestado: activa\n---\n", encoding="utf-8")
        r = self.c.post("/tipos/tarea/T1/completar", json={"version": v})
        self.assertEqual(r.status_code, 409)
        self.assertNotEqual(r.json()["version"], v)
        self.assertIn("estado: activa", (self.dir / "T1.md").read_text())

    def test_lo_que_no_se_puede_y_lo_que_no_existe(self):
        self.assertEqual(self.c.post("/tipos/tarea/T2/completar", json={}).status_code, 409)   # ya cerrada
        self.assertEqual(self.c.post("/tipos/tarea/T9/completar", json={}).status_code, 404)
        self.assertEqual(self.c.post("/tipos/tarea/T1/volar", json={}).status_code, 422)
        self.assertEqual(self.c.post("/tipos/tarea/T1/reagendar", json={"params": {"cuando": "mañana"}}).status_code, 422)
