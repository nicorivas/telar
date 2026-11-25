"""La página de telar en el navegador (telar.api_web): la llave, la cookie, el origen y la API adentro."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

if not HAY_FASTAPI:
    raise unittest.SkipTest("sin fastapi (el extra «serve»)")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from telar import api_web  # noqa: E402


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
        # lo demás de la dirección sigue: solo se va la llave
        r = _app().get("/?abrir=hilo:Gesti%C3%B3n&k=llave-de-prueba", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (302, "/?abrir=hilo%3AGesti%C3%B3n"))

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


class UnaPestanaComoApp(Prueba):
    """`/pestana/<nombre>/`: la página con solo esa pestaña, para instalarla aparte en el teléfono, con su manifiesto y el
    ícono de su módulo. El manifiesto y el ícono, sin llave: el navegador los pide sin la cookie."""

    def _con(self, modulos=()):
        return TestClient(api_web.crear(FastAPI(), clave="llave-de-prueba", config=SimpleNamespace(modulos=modulos)),
                          base_url="http://telar:8780")

    def test_la_pagina_con_su_manifiesto_y_con_llave(self):
        c = self._con()
        self.assertEqual(c.get("/pestana/chats/").status_code, 403)
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        r = c.get("/pestana/chats/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/pestana/chats/manifest.webmanifest"', r.text)
        self.assertNotIn('href="/manifest.webmanifest"', r.text)
        r = c.get("/pestana/chats", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (302, "/pestana/chats/"))

    def test_el_manifiesto_es_de_esa_pestana_y_su_icono_el_del_modulo(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            png = Path(d) / "icono.png"
            # un PNG de 256 x 256: basta la cabecera para saber su lado
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (256).to_bytes(4, "big") * 2 + b"\x08\x06\x00\x00\x00")
            m = SimpleNamespace(nombre="chat", pestana={"nombre": "chats"}, icono=png)
            c = self._con((m,))
            r = c.get("/pestana/chats/manifest.webmanifest")
            self.assertEqual(r.status_code, 200)
            d_ = r.json()
            self.assertEqual((d_["name"], d_["start_url"], d_["scope"], d_["id"]),
                             ("chats", "/pestana/chats/", "/pestana/chats/", "/pestana/chats/"))
            self.assertEqual({(i["src"], i["sizes"], i["purpose"]) for i in d_["icons"]},
                             {("/pestana/chats/icono.png", "256x256", "any"), ("/pestana/chats/icono.png", "256x256", "maskable")})
            self.assertEqual(c.get("/pestana/chats/icono.png").content, png.read_bytes())
            # por el nombre del módulo también, y la app se llama como se ve la pestaña: el módulo registro, cuya
            # pestaña es «decisiones», instalado de antes como /pestana/registro/, sigue en su dirección con el nombre nuevo
            self.assertEqual(c.get("/pestana/chat/icono.png").content, png.read_bytes())
            d_ = c.get("/pestana/chat/manifest.webmanifest").json()
            self.assertEqual((d_["name"], d_["short_name"], d_["id"]), ("chats", "chats", "/pestana/chat/"))
        # una pestaña sin módulo (o sin ícono): los de telar
        c = self._con()
        self.assertEqual(c.get("/pestana/plan/manifest.webmanifest").json()["icons"][0]["src"], "/icono-192.png")
        self.assertEqual(c.get("/pestana/plan/icono.png").status_code, 200)


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


class LaFirmaDeLaPagina(Prueba):
    """Una página abierta sabe con qué página arrancó (la firma escrita en indice.html) y la compara con la que sirve el
    proceso (`/pagina.json`): la de cuando arrancó, que un despliegue cambia al reiniciarlo."""

    def test_la_pagina_trae_la_firma_que_dice_pagina_json(self):
        c = _app()
        self.assertEqual(c.get("/pagina.json").status_code, 403)
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        r = c.get("/pagina.json")
        self.assertEqual(r.headers["cache-control"], "no-store")
        firma = r.json()["firma"]
        self.assertEqual(firma, api_web.firma_pagina())
        for ruta in ("/", "/compartir", "/pestana/chats/"):
            self.assertIn(f'<meta name="telar-pagina" content="{firma}">', c.get(ruta).text, ruta)

    def test_cambia_con_el_contenido_y_se_toma_al_arrancar(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            carpeta = Path(d)
            for n in api_web.PAGINA:
                (carpeta / n).write_text(f"{n} 1", encoding="utf-8")
            antes = api_web.firma_pagina(carpeta)
            (carpeta / "app.js").write_text("app.js 1", encoding="utf-8")  # igual, aunque cambie la hora
            self.assertEqual(api_web.firma_pagina(carpeta), antes)
            (carpeta / "app.js").write_text("app.js 2", encoding="utf-8")
            self.assertNotEqual(api_web.firma_pagina(carpeta), antes)
        # el proceso dice la de cuando arrancó, aunque los archivos cambien después (entre el pull y el reinicio)
        with mock.patch.object(api_web, "firma_pagina", return_value="primera"):
            c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        with mock.patch.object(api_web, "firma_pagina", return_value="otra"):
            self.assertEqual(c.get("/pagina.json").json(), {"firma": "primera"})
            self.assertIn('content="primera"', c.get("/").text)


class ElCatalogo(Prueba):
    def test_el_catalogo_de_componentes_con_la_llave(self):
        c = _app()
        self.assertEqual(c.get("/componentes").status_code, 403)
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        r = c.get("/componentes")
        self.assertEqual(r.status_code, 200)
        self.assertIn('/estatico/componentes.js', r.text)
        self.assertEqual(c.get("/estatico/componentes.js").status_code, 200)


class ElModoDesarrollo(Prueba):
    def test_dev_cambios_solo_con_dev(self):
        from fastapi import FastAPI

        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        self.assertEqual(c.get("/dev/cambios").status_code, 404)
        con = api_web.crear(FastAPI(), clave="llave-de-prueba", dev=True)
        self.assertIn("/dev/cambios", [getattr(r, "path", "") for r in con.routes])

    def test_la_pagina_pide_dev_cambios_solo_con_dev(self):
        # sin --dev, la página no escucha /dev/cambios (era un 404 en cada carga); con --dev, sí
        from fastapi import FastAPI

        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        self.assertIn('<meta name="telar-dev" content="">', c.get("/").text)
        con = TestClient(api_web.crear(FastAPI(), clave="llave-de-prueba", dev=True), base_url="http://telar:8780")
        con.cookies.set(api_web.COOKIE, "llave-de-prueba")
        self.assertIn('<meta name="telar-dev" content="si">', con.get("/").text)


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

    def _app_con_bus(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        config = SimpleNamespace(bus=SimpleNamespace(url="nats://100.1.1.1:4222", persona="bruno", administra="ana",
                                                     token="", maquina="laptop"))
        c = TestClient(api_web.crear(FastAPI(), clave="llave", config=config), base_url="http://otra:8780")
        c.cookies.set(api_web.COOKIE, "llave")
        c.headers["Origin"] = "http://otra:8780"
        return c

    def test_los_servidores_mainframe_salen_con_mi_lugar(self):
        from telar import alojamiento

        respuesta = {"dueno": "ana", "quien": "bruno", "administra": False, "servidor": "telar",
                     "alojamientos": [{"persona": "bruno", "estado": "pendiente"}]}
        with mock.patch.object(alojamiento, "pedir", return_value=respuesta) as pedir:
            d = self._app_con_bus().get("/alojamiento.json").json()
        pedir.assert_called_once()
        self.assertEqual(d["servidores"], [{"nombre": "telar", "dueno": "ana", "quien": "bruno", "administra": False,
                                            "alojamientos": [{"persona": "bruno", "estado": "pendiente"}]}])

    def test_sin_nadie_que_atienda_no_hay_servidores_y_no_es_un_error(self):
        from telar import alojamiento

        with mock.patch.object(alojamiento, "pedir", side_effect=alojamiento.ErrorDeAlojamiento("nadie atiende", 403)):
            r = self._app_con_bus().get("/alojamiento.json")
        self.assertEqual((r.status_code, r.json()["servidores"]), (200, []))

    def test_pedir_un_lugar_pone_el_secreto_aqui_y_no_viene_de_la_pagina(self):
        from telar import alojamiento

        c = self._app_con_bus()
        with mock.patch.object(alojamiento, "datos_de_pedir", return_value={"secreto": "S", "maquina": "laptop"}) as datos, \
                mock.patch.object(alojamiento, "pedir", return_value={"ok": True, "hecho": "anotado"}) as pedir:
            r = c.post("/alojamiento/pedir", json={"llave": "ssh-ed25519 AAA", "secreto": "robado", "accion": "quitar"})
        self.assertEqual(r.json()["hecho"], "anotado")
        datos.assert_called_once()
        self.assertEqual(datos.call_args.args[1], "ssh-ed25519 AAA")
        self.assertEqual(pedir.call_args.args[1], {"accion": "pedir", "persona": "", "secreto": "S", "maquina": "laptop"})

    def test_decidir_y_los_errores_con_su_codigo(self):
        from telar import alojamiento

        c = self._app_con_bus()
        with mock.patch.object(alojamiento, "pedir", side_effect=alojamiento.ErrorDeAlojamiento("no administras", 403)):
            r = c.post("/alojamiento/aprobar", json={"persona": "carla"})
        self.assertEqual((r.status_code, r.json()["detail"]), (403, "no administras"))
        self.assertEqual(c.post("/alojamiento/borrar", json={}).status_code, 404)
        c.headers["Origin"] = "http://ajena"
        self.assertEqual(c.post("/alojamiento/pedir", json={}).status_code, 403, "desde otra página, no")


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


class LosAvisos(Prueba):
    """`/eventos`: la página se entera al tiro de que cambió algo de telar («hilos») o llegó la foto de otra máquina
    («espejos»); lo que se reescribe solo cada tanto (los vivos, los candados) no avisa."""

    def setUp(self):
        super().setUp()
        import tempfile
        from pathlib import Path

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.estado = Path(self.tmp.name)
        (self.estado / "espejos").mkdir()

    def test_lo_quieto_no_cuenta_y_lo_demas_si(self):
        (self.estado / "vivos").write_text("{}")
        (self.estado / "atencion.json.lock").write_text("")
        (self.estado / "commits.log").write_text("x")
        (self.estado / ".candado").write_text("")
        self.assertEqual(api_web._firma_carpeta(self.estado), ())
        (self.estado / "atencion.json").write_text("{}")
        (self.estado / "foco.log").write_text("x")
        self.assertEqual([n for n, _ in api_web._firma_carpeta(self.estado)], ["atencion.json", "foco.log"])

    def test_avisa_hilos_y_espejos_cuando_cambian(self):
        import asyncio
        import os

        async def leer():
            g = api_web._eventos(SimpleNamespace(estado=self.estado))
            self.assertTrue((await g.__anext__()).startswith("retry:"))
            (self.estado / "atencion.json").write_text("{}")
            self.assertEqual(await g.__anext__(), "data: hilos\n\n")
            os.utime(self.estado / "vivos", None) if (self.estado / "vivos").exists() else None
            (self.estado / "espejos" / "otra.json").write_text("{}")
            self.assertEqual(await g.__anext__(), "data: espejos\n\n")
            # un botón de la ventana de un módulo, o el «no molestar» (telar.servicios.ventanas): solo «ventanas»
            (self.estado / "ventanas").mkdir()
            (self.estado / "ventanas" / "cambio").write_text("1")
            self.assertEqual(await g.__anext__(), "data: ventanas\n\n")
            await g.aclose()

        asyncio.run(asyncio.wait_for(leer(), 5))

    def test_sin_configuracion_no_hay_avisos(self):
        c = _app()
        c.get("/?k=llave-de-prueba")
        self.assertEqual(c.get("/eventos").status_code, 404)
