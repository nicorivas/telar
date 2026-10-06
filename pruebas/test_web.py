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
        self.assertEqual(e.exception.code, 404)  # solo /api/enviar acepta POST, y solo con --escribir

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


class Escritura(Prueba):
    """`POST /api/enviar`: la única ruta que escribe. Apagada por defecto y defendida de páginas ajenas."""

    def setUp(self):
        super().setUp()
        import tempfile
        from pathlib import Path

        from telar import config as mod_config
        from telar.cli import Contexto
        from telar.config import Enlace

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                        enlaces=(Enlace(nombre="laptop", destino="nico@mac"),))
        self.ctx = Contexto(config=self.config)
        web._ultimo_envio[0] = 0.0
        self.addCleanup(lambda: web._ultimo_envio.__setitem__(0, 0.0))

    def servir(self, escribir=True, **kw):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), web.manejador(True, self.config, self.ctx, escribir, **kw))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return srv.server_address[1]

    def post(self, puerto, cuerpo=None, *, ruta="/api/enviar", cabeceras=None, crudo=None):
        import http.client

        c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
        datos = crudo if crudo is not None else json.dumps(cuerpo if cuerpo is not None else
                                                            {"maquina": "", "hilo": "Faro", "texto": "hola"}).encode()
        h = {"Content-Type": "application/json", "X-Telar": "1", **(cabeceras or {})}
        c.request("POST", ruta, datos, h)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"{}")

    def test_por_defecto_la_pagina_solo_lee(self):
        puerto = self.servir(escribir=False)
        with mock.patch.object(web.enlace, "servir") as servir:
            codigo, cuerpo = self.post(puerto)
        self.assertEqual(codigo, 403)
        servir.assert_not_called()

    def test_yo_dice_si_se_puede_escribir(self):
        for escribir in (False, True):
            puerto = self.servir(escribir=escribir)
            with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/yo") as r:
                cuerpo = json.loads(r.read())
            # sin --plan, la pestaña del plan no está ni se puede comentar
            self.assertEqual(cuerpo, {"escribir": escribir, "plan": False, "plan_comentar": False, "nuevo": False, "enlaces": ["laptop"]})

    def test_una_pagina_ajena_no_puede_escribir(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "servir") as servir:
            casos = [
                {"X-Telar": "0"},                              # sin el encabezado propio (un formulario ajeno no puede ponerlo)
                {"Origin": "http://malo.example"},              # una página de otro origen
                {"Host": "malo.example"},                       # DNS rebinding: el navegador cree hablar con otro nombre
                {"Content-Type": "text/plain"},                 # un formulario HTML solo manda text/plain
            ]
            for cab in casos:
                codigo, _ = self.post(puerto, cabeceras=cab)
                self.assertEqual(codigo, 403, cab)
            servir.assert_not_called()

    def test_el_origen_propio_y_los_nombres_permitidos_pasan(self):
        puerto = self.servir(tambien=("telar:8765",))
        with mock.patch.object(web.enlace, "servir", return_value={"ok": True}):
            self.assertEqual(self.post(puerto, cabeceras={"Origin": f"http://127.0.0.1:{puerto}"})[0], 200)
            web._ultimo_envio[0] = 0.0
            self.assertEqual(self.post(puerto, cabeceras={"Host": "telar:8765", "Origin": "http://telar:8765"})[0], 200)

    def test_un_envio_local_va_a_la_puerta_con_el_texto_por_la_entrada(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "servir", return_value={"ok": True, "hilo": "Faro"}) as servir:
            codigo, cuerpo = self.post(puerto, {"maquina": "", "hilo": "Faro", "texto": "hola\nmundo", "enter": True})
        self.assertEqual(codigo, 200)
        pedido, entrada = servir.call_args.args[1], servir.call_args.args[2]
        self.assertEqual(pedido, "enviar Faro enter")
        self.assertEqual(entrada, "hola\nmundo".encode())

    def test_un_nombre_con_comillas_o_espacios_no_se_cuela_en_el_pedido(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "servir", return_value={"ok": True}) as servir:
            self.post(puerto, {"maquina": "", "hilo": "a b'; ls #", "texto": "x", "enter": False})
        import shlex
        self.assertEqual(shlex.split(servir.call_args.args[1]), ["enviar", "a b'; ls #"])

    def test_un_envio_al_laptop_va_por_el_enlace(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "llamar", return_value={"ok": True, "hilo": "Lumbre"}) as llamar:
            codigo, _ = self.post(puerto, {"maquina": "macbook-de-ana", "hilo": "Lumbre", "texto": "hola", "enter": True})
        self.assertEqual(codigo, 200)
        self.assertEqual(llamar.call_args.args[0].nombre, "laptop")  # un solo enlace: es ese
        self.assertEqual(llamar.call_args.args[1:3], ("enviar", ["Lumbre", "enter"]))
        self.assertEqual(llamar.call_args.args[3], b"hola")

    def test_con_varios_enlaces_hay_que_llamarse_igual(self):
        from telar.config import Enlace

        config = self.config.__class__(raiz=self.config.raiz, estado=self.config.estado,
                                       enlaces=(Enlace("a", "x@a"), Enlace("b", "x@b")))
        self.assertEqual(web.enlace_para(config, "b").nombre, "b")
        self.assertIsNone(web.enlace_para(config, "otro"))
        self.assertIsNone(web.enlace_para(self.config.__class__(raiz=self.config.raiz, estado=self.config.estado), "x"))

    def test_lo_que_la_puerta_rechaza_llega_como_409_con_el_motivo(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "servir", return_value={"ok": False, "error": "no hay un hilo vivo que se llame «Faro»"}):
            codigo, cuerpo = self.post(puerto)
        self.assertEqual(codigo, 409)
        self.assertIn("hilo vivo", cuerpo["error"])

    def test_cuerpos_malos(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "servir") as servir:
            self.assertEqual(self.post(puerto, crudo=b"no es json")[0], 400)
            for malo in ([], {"hilo": "Faro"}, {"maquina": "", "hilo": "", "texto": "x"}, {"maquina": 3, "hilo": "F", "texto": "x"},
                         {"maquina": "", "hilo": "F", "texto": "x", "enter": "si"}):
                self.assertEqual(self.post(puerto, malo)[0], 400, malo)
                web._ultimo_envio[0] = 0.0
            self.assertEqual(self.post(puerto, crudo=b"x" * (web.MAX_CUERPO + 1))[0], 413)
            servir.assert_not_called()

    def test_un_envio_cada_medio_segundo(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "servir", return_value={"ok": True}) as servir:
            self.assertEqual(self.post(puerto)[0], 200)
            self.assertEqual(self.post(puerto)[0], 429)
        self.assertEqual(servir.call_count, 1)

    def test_queda_anotado_quien_a_que_hilo_y_cuanto_pero_no_el_texto(self):
        puerto = self.servir()
        with mock.patch.object(web.enlace, "servir", return_value={"ok": True}):
            self.post(puerto, {"maquina": "", "hilo": "Faro", "texto": "una contraseña que no debe quedar", "enter": True})
        lineas = (self.config.estado / "web.log").read_text().splitlines()
        self.assertEqual(len(lineas), 1)
        self.assertNotIn("contraseña", lineas[0])
        campos = lineas[0].split("\t")
        self.assertEqual(campos[2:5], ["aquí", "Faro", "33"])
        self.assertEqual(campos[5], "ok")
