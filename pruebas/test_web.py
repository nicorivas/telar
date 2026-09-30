"""`telar web`: lo que decide el servidor, sin red real ni el calendario."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import web


class Servidor(Prueba):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), web.manejador(True))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        web._cache.clear()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def pedir(self, ruta):
        try:
            with urllib.request.urlopen(self.base + ruta) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_la_raiz_es_la_pagina(self):
        codigo, cuerpo = self.pedir("/")
        self.assertEqual(codigo, 200)
        self.assertIn(b"<title>telar</title>", cuerpo)

    def test_no_sirve_archivos_fuera_de_su_carpeta(self):
        for ruta in ("/../ordenes/web.py", "/..%2fordenes/web.py", "/%2e%2e/cli.py"):
            self.assertEqual(self.pedir(ruta)[0], 404, ruta)

    def test_solo_lee(self):
        req = urllib.request.Request(self.base + "/api/hoy", method="POST", data=b"{}")
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 501)  # http.server no conoce POST: no hay ruta que escriba

    def test_los_datos_se_reusan_mientras_estan_vigentes(self):
        with mock.patch.object(web, "_correr", return_value=b'{"a": 1}') as correr:
            self.pedir("/api/hilos")
            self.pedir("/api/hilos")
        self.assertEqual(correr.call_count, 1)

    def test_fresco_salta_la_vigencia(self):
        with mock.patch.object(web, "_correr", return_value=b'{"a": 1}') as correr:
            self.pedir("/api/hilos")
            self.pedir("/api/hilos?fresco=1")
        self.assertEqual(correr.call_count, 2)

    def test_una_orden_que_falla_es_un_502_con_el_motivo(self):
        with mock.patch.object(web, "_correr", side_effect=RuntimeError("se cayó el calendario")):
            codigo, cuerpo = self.pedir("/api/hoy")
        self.assertEqual(codigo, 502)
        self.assertEqual(json.loads(cuerpo)["error"], "se cayó el calendario")

    def test_la_version_cambia_al_editar_un_archivo_de_la_pagina(self):
        antes = json.loads(self.pedir("/api/version")[1])["pagina"]
        archivo = web.CARPETA / "estilo.css"
        original = archivo.stat().st_mtime_ns
        try:
            import os
            os.utime(archivo, ns=(original + 10**9, original + 10**9))
            despues = json.loads(self.pedir("/api/version")[1])["pagina"]
        finally:
            os.utime(archivo, ns=(original, original))
        self.assertNotEqual(antes, despues)


class Escucha(Prueba):
    def test_todas_las_interfaces_hay_que_pedirlas(self):
        codigo = web.main(["--host", "0.0.0.0"], mock.Mock())
        self.assertNotEqual(codigo, 0)


class Espejos(Prueba):
    def test_las_fotos_de_otras_maquinas_salen_por_su_ruta(self):
        import tempfile
        from pathlib import Path

        from telar import config as mod_config
        from telar import espejo

        with tempfile.TemporaryDirectory() as tmp:
            config = mod_config.Config(raiz=Path(tmp), estado=Path(tmp) / "estado")
            espejo.guardar(config, "laptop", json.dumps({"version": 1, "hilos": [{"nombre": "Faro", "atencion": "espera"}]}))
            srv = ThreadingHTTPServer(("127.0.0.1", 0), web.manejador(True, config))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/espejos") as r:
                    cuerpo = json.loads(r.read())
            finally:
                srv.shutdown()
                srv.server_close()
        [laptop] = cuerpo["espejos"]
        self.assertEqual(laptop["nombre"], "laptop")
        self.assertTrue(laptop["en_linea"])
        self.assertEqual(laptop["hilos"][0]["nombre"], "Faro")
