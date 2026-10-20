"""La página de telar en el navegador (telar.api_web): la llave, la cookie, el origen y la API adentro."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from telar import api_web


def _app():
    interna = FastAPI()

    @interna.get("/salud")
    def salud():
        return {"ok": True}

    @interna.post("/algo")
    def algo():
        return {"hecho": True}

    return TestClient(api_web.crear(interna, clave="llave-de-prueba"), base_url="http://telar:8780")


class LaLlave(Prueba):
    def test_sin_llave_nada_y_con_llave_una_cookie(self):
        c = _app()
        self.assertEqual(c.get("/").status_code, 403)
        self.assertEqual(c.get("/api/salud").status_code, 403)
        r = c.get("/?k=llave-de-prueba", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (302, "/"))
        self.assertIn("HttpOnly", r.headers["set-cookie"])
        self.assertIn("telar_panel=llave-de-prueba", r.headers["set-cookie"])
        self.assertEqual(_app().get("/?k=otra", follow_redirects=False).status_code, 403)  # sin la cookie de recién

    def test_con_la_cookie_la_pagina_y_la_api(self):
        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        self.assertEqual(c.get("/").status_code, 200)
        self.assertEqual(c.get("/api/salud").json(), {"ok": True})
        self.assertEqual(c.get("/estatico/indice.html").status_code, 200)

    def test_lo_que_escribe_tiene_que_venir_de_aqui(self):
        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        self.assertEqual(c.post("/api/algo", headers={"Origin": "http://telar:8780"}).status_code, 200)
        self.assertEqual(c.post("/api/algo", headers={"Origin": "https://ajeno.example"}).status_code, 403)
        self.assertEqual(c.post("/api/algo").status_code, 200)  # sin Origin (curl): manda la llave


class LoQueSeGuarda(Prueba):
    """xterm se guarda en el navegador; lo demás de la página se revalida; los datos, nunca. Y va comprimido."""

    def test_cache_y_gzip(self):
        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        x = c.get("/estatico/xterm/xterm.js", headers={"accept-encoding": "gzip"})
        self.assertEqual((x.status_code, x.headers["cache-control"], x.headers.get("content-encoding")),
                         (200, "public, max-age=604800", "gzip"))
        self.assertEqual(c.get("/estatico/indice.html").headers["cache-control"], "no-cache")
        self.assertEqual(c.get("/api/salud").headers["cache-control"], "no-store")
        # revalidar: si no cambió, un 304 sin cuerpo
        etag = c.get("/estatico/indice.html").headers["etag"]
        self.assertEqual(c.get("/estatico/indice.html", headers={"if-none-match": etag}).status_code, 304)


class ElModoDesarrollo(Prueba):
    def test_dev_cambios_solo_con_dev(self):
        from fastapi import FastAPI

        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        self.assertEqual(c.get("/dev/cambios").status_code, 404)
        con = api_web.crear(FastAPI(), clave="llave-de-prueba", dev=True)
        self.assertIn("/dev/cambios", [getattr(r, "path", "") for r in con.routes])


class LasMaquinas(Prueba):
    """La página madre: tus máquinas, y entrar a otra con un boleto firmado con el token del bus."""

    def _app(self, aqui="telar"):
        from fastapi import FastAPI

        from telar import api_web as w

        # el nombre de la máquina se lee en cada pedido: el parche vale toda la prueba
        nombre = mock.patch("telar.bus.maquina", return_value=aqui)
        nombre.start()
        self.addCleanup(nombre.stop)
        with mock.patch.object(w, "_token_del_bus", return_value="token-del-bus"):
            return TestClient(w.crear(FastAPI(), clave=f"llave-de-{aqui}", config=SimpleNamespace()),
                              base_url="http://otra:8780")

    def test_un_boleto_entra_una_vez_y_no_vence_de_mas(self):
        import time
        from urllib.parse import urlsplit

        c = self._app("laptop")
        url = api_web.boleto("token-del-bus", "telar", "laptop", "http://otra:8780")
        ruta = url[len("http://otra:8780"):]
        r = c.get(ruta, follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (302, "/"))
        self.assertIn("telar_panel=llave-de-laptop", r.headers["set-cookie"])
        self.assertEqual(c.get(ruta, follow_redirects=False).status_code, 403, "se usa una vez")
        for malo in (api_web.boleto("token-del-bus", "telar", "otra-maquina", "http://otra:8780"),  # para otra
                     api_web.boleto("otro-token", "telar", "laptop", "http://otra:8780"),           # otro secreto
                     api_web.boleto("token-del-bus", "telar", "laptop", "http://otra:8780", ahora=time.time() - 120)):
            self.assertEqual(c.get(malo[len("http://otra:8780"):], follow_redirects=False).status_code, 403, malo)
        self.assertEqual(urlsplit(url).path, "/entrar")

    def test_la_lista_trae_las_que_sirven_su_pagina(self):
        fotos = [
            {"nombre": "telar", "en_linea": True, "edad": 2, "web": "http://100.1.1.1:8780", "hilos": []},
            {"nombre": "laptop", "en_linea": True, "edad": 5, "web": "http://100.2.2.2:8780", "telar": "0.1.13",
             "hilos": [{"nombre": "A", "vivo": True}, {"nombre": "B", "vivo": False}]},
            {"nombre": "vieja", "en_linea": False, "edad": 9000, "web": "http://100.3.3.3:8780", "hilos": []},
        ]
        c = self._app("telar")
        c.cookies.set(api_web.COOKIE, "llave-de-telar")
        with mock.patch("telar.espejo.leer_todos", return_value=fotos):
            d = c.get("/maquinas.json").json()
        nombres = [(m["nombre"], m["aqui"], bool(m["url"])) for m in d["maquinas"]]
        self.assertEqual(nombres, [("telar", True, True), ("laptop", False, True), ("vieja", False, False)])
        laptop = d["maquinas"][1]
        self.assertEqual(laptop["hilos"], 1)
        self.assertTrue(laptop["url"].startswith("http://100.2.2.2:8780/entrar?de=telar&"))
        self.assertEqual(c.get("/maquinas").status_code, 200)
        c.cookies.clear()
        self.assertEqual(c.get("/maquinas.json").status_code, 403, "la lista, solo con la llave")


class LaTerminal(Prueba):
    """`/pty`: la terminal de un hilo. Sin la llave o desde otra página, ni se abre; con las dos, va y vuelve.
    (El cliente de prueba manda `host: testserver` en los WebSocket: de ahí el origen.)"""

    def setUp(self):
        super().setUp()
        import asyncio
        import os
        import pty
        from unittest import mock

        from telar import terminal

        async def abrir(hilo, columnas, filas):
            # `cat` en vez de `telar mirar`: devuelve lo que se teclea, sin tmux
            principal, secundario = pty.openpty()
            proceso = await asyncio.create_subprocess_exec("cat", stdin=secundario, stdout=secundario,
                                                           stderr=secundario, start_new_session=True)
            os.close(secundario)
            os.set_blocking(principal, False)
            self.abiertos.append((hilo, columnas, filas))
            return proceso, principal

        self.abiertos = []
        p = mock.patch.object(terminal, "abrir", abrir)
        p.start()
        self.addCleanup(p.stop)

    def test_sin_llave_o_de_otra_pagina_no_se_abre(self):
        from starlette.websockets import WebSocketDisconnect

        c = _app()
        with self.assertRaises(WebSocketDisconnect):
            with c.websocket_connect("/pty?hilo=faro", headers={"origin": "http://testserver"}) as ws:
                ws.receive_text()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        for origen in ({"origin": "http://otro:9999"}, {}):
            with self.assertRaises(WebSocketDisconnect):
                with c.websocket_connect("/pty?hilo=faro", headers=origen) as ws:
                    ws.receive_text()
        self.assertEqual(self.abiertos, [])

    def test_otra_maquina_entra_con_el_token_del_bus(self):
        from fastapi import FastAPI
        from starlette.websockets import WebSocketDisconnect

        from telar import api_web as w

        with mock.patch.object(w, "_token_del_bus", return_value="token-del-bus"):
            c = TestClient(w.crear(FastAPI(), clave="llave-de-prueba", config=object()))
        with c.websocket_connect("/pty?hilo=faro", headers={"authorization": "Bearer token-del-bus"}) as ws:
            ws.send_json({"d": "hola\n"})
            visto = ""
            while "hola" not in visto:
                visto += ws.receive_text()
        with self.assertRaises(WebSocketDisconnect):
            with c.websocket_connect("/pty?hilo=faro", headers={"authorization": "Bearer otro"}) as ws:
                ws.receive_text()

    def test_un_hilo_de_otra_maquina_se_reenvia_a_su_pagina(self):
        from fastapi import FastAPI

        from telar import api_web as w
        from telar import terminal

        llamadas = []

        async def reenviar(ws, web, hilo, maquina, cols, rows, token):
            llamadas.append((web, hilo, maquina, token))
            await ws.close()

        config = SimpleNamespace()
        with mock.patch.object(w, "_token_del_bus", return_value="token-del-bus"):
            c = TestClient(w.crear(FastAPI(), clave="llave-de-prueba", config=config))
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        with mock.patch.object(terminal, "reenviar", reenviar), \
                mock.patch("telar.bus.maquina", return_value="telar"), \
                mock.patch("telar.espejo.web_de", return_value="http://100.1.2.3:8780"):
            with c.websocket_connect("/pty?hilo=Telar&maquina=laptop", headers={"origin": "http://testserver"}) as ws:
                with self.assertRaises(Exception):
                    ws.receive_text()
            # el de esta misma máquina no se reenvía
            with c.websocket_connect("/pty?hilo=faro&maquina=telar", headers={"origin": "http://testserver"}) as ws:
                ws.send_json({"d": "x\n"})
                ws.receive_text()
        self.assertEqual(llamadas, [("http://100.1.2.3:8780", "Telar", "laptop", "token-del-bus")])
        self.assertEqual([a[0] for a in self.abiertos], ["faro"])

    def test_lo_tecleado_llega_y_vuelve(self):
        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        with c.websocket_connect("/pty?hilo=faro&cols=900&rows=40", headers={"origin": "http://testserver"}) as ws:
            ws.send_json({"r": [120, 50]})
            ws.send_json({"d": "hola ñandú\n"})
            visto = ""
            while "hola ñandú" not in visto:
                visto += ws.receive_text()
        # el tamaño que pide la página se acota (hasta 400 columnas)
        self.assertEqual(self.abiertos, [("faro", 400, 40)])
