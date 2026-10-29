"""La puerta de un servidor con alojados (telar.puerta): quién entra, a qué telar va cada pedido, y lo que cambia en
`telar serve`, `telar instalar`, el alojamiento y el ayudante de root cuando hay puerta."""

from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import instalacion, puerta

try:
    import httpx  # noqa: F401
    import uvicorn
    from fastapi import FastAPI, Request, WebSocket
    from fastapi.testclient import TestClient

    HAY_SERVE = True
except ImportError:  # sin el extra «serve» y las pruebas: lo de la app se salta
    HAY_SERVE = False

NICO, PABLO, SERVIDOR = "100.107.195.13", "100.80.165.37", "100.66.75.117"
CUENTAS = {NICO: "nicorivas@gmail.com", PABLO: "pablo.ferre@gmail.com", SERVIDOR: "nicorivas@gmail.com",
           "100.99.0.1": "sin-lugar@x.com"}


def tabla(**personas) -> puerta.Tabla:
    return puerta.Tabla(personas=personas or {"nicorivas@gmail.com": "nico", "pablo.ferre@gmail.com": "pablo"},
                        url="https://telar.ejemplo.ts.net", dueno="nico")


def identificar(t: puerta.Tabla | None = None, **kw) -> puerta.Identificar:
    preguntas: list[str] = []

    def quien(ip):
        preguntas.append(ip)
        return {"cuenta": CUENTAS.get(ip, ""), "maquina": "x"}

    i = puerta.Identificar(t or tabla(), quien=quien, propias={SERVIDOR}, **kw)
    i.preguntas = preguntas
    return i


class LaTabla(Prueba):
    def test_junta_la_configuracion_y_los_alojados(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "puerta.toml").write_text('url = "https://telar.x.ts.net/"\n[personas]\n"Nico@Gmail.com" = "nico"\n')
            (d / "alojados").mkdir()
            (d / "alojados" / "pablo.json").write_text(json.dumps({"nombre": "pablo", "tailscale": "pablo@x.com"}))
            (d / "alojados" / "viejo.json").write_text(json.dumps({"nombre": "viejo", "puerto": 8782}))  # sin cuenta
            t = puerta.leer_tabla(d / "puerta.toml", d / "alojados")
        self.assertEqual(t.url, "https://telar.x.ts.net")
        self.assertEqual(t.personas, {"nico@gmail.com": "nico", "pablo@x.com": "pablo"})
        self.assertEqual(t.problemas, [])

    def test_una_cuenta_con_dos_usuarios_no_entra(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "puerta.toml").write_text('[personas]\n"a@x.com" = "ana"\n')
            (d / "alojados").mkdir()
            (d / "alojados" / "b.json").write_text(json.dumps({"nombre": "beto", "tailscale": "a@x.com"}))
            t = puerta.leer_tabla(d / "puerta.toml", d / "alojados")
        self.assertEqual(t.personas, {})
        self.assertIn("varios usuarios", t.problemas[0])

    def test_un_usuario_raro_no_entra(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "puerta.toml").write_text('[personas]\n"a@x.com" = "../root"\n')
            t = puerta.leer_tabla(d / "puerta.toml", d / "nada")
        self.assertEqual(t.personas, {})


class QuienEs(Prueba):
    def test_la_ultima_direccion_es_la_que_vale(self):
        # la de antes la puede escribir el navegador; la última la agrega tailscale serve
        self.assertEqual(puerta.cliente({"x-forwarded-for": f"{NICO}, {PABLO}"}), PABLO)
        self.assertEqual(puerta.cliente({"x-forwarded-for": "basura"}), "")
        self.assertEqual(puerta.cliente({}), "")

    def test_cada_cuenta_a_su_usuario(self):
        i = identificar()
        self.assertEqual(i(NICO), ("nico", "nicorivas@gmail.com"))
        self.assertEqual(i(PABLO), ("pablo", "pablo.ferre@gmail.com"))

    def test_desde_el_servidor_mismo_no(self):
        # un proceso del servidor que llega por Tailscale viene desde la IP del servidor, que es de quien administra
        with self.assertRaises(puerta.ErrorDePuerta):
            identificar()(SERVIDOR)

    def test_sin_saber_las_direcciones_del_servidor_no_deja_entrar_a_nadie(self):
        i = puerta.Identificar(tabla(), quien=lambda ip: {"cuenta": CUENTAS[ip]}, propias=lambda: set())
        with self.assertRaises(puerta.ErrorDePuerta) as e:
            i(NICO)
        self.assertEqual(e.exception.codigo, 503)

    def test_fuera_de_tailscale_sin_direccion_o_sin_lugar_no(self):
        i = identificar()
        for ip in ("192.168.1.10", "", "100.99.0.1"):  # la última: de la red, pero de una cuenta sin lugar
            with self.assertRaises(puerta.ErrorDePuerta, msg=ip):
                i(ip)

    def test_whois_se_recuerda_un_rato(self):
        reloj = [0.0]
        i = identificar(reloj=lambda: reloj[0])
        i(NICO), i(NICO)
        self.assertEqual(i.preguntas, [NICO])
        reloj[0] = puerta.MEMORIA_WHOIS + 1
        i(NICO)
        self.assertEqual(i.preguntas, [NICO, NICO])


class _Servidor:
    """Una app en un socket, con uvicorn de verdad, en otro hilo."""

    def __init__(self, app, sock: Path) -> None:
        self.server = uvicorn.Server(uvicorn.Config(app, uds=str(sock), log_level="critical"))
        self.hilo = threading.Thread(target=self.server.run, daemon=True)
        self.hilo.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)

    def parar(self) -> None:
        self.server.should_exit = True
        self.hilo.join(5)


def _detras(sock: Path, quien: str) -> _Servidor:
    """Un telar falso detrás de la puerta, en su socket: contesta con lo que le llegó."""
    app = FastAPI()

    @app.api_route("/{ruta:path}", methods=["GET", "POST"])
    async def eco(request: Request, ruta: str):
        cuerpo = await request.body()
        return {"quien": quien, "ruta": "/" + ruta, "query": request.url.query, "largo": len(cuerpo),
                "cabeceras": {k.lower(): v for k, v in request.headers.items()}}

    @app.websocket("/pty")
    async def pty(ws: WebSocket):
        from starlette.websockets import WebSocketDisconnect

        await ws.accept()
        try:
            while True:
                m = await ws.receive_text()
                auth = ws.headers.get("authorization", "")
                await ws.send_text(f"{quien}:{m}:{ws.headers.get('origin', '')}" + (f"|{auth}" if auth else ""))
        except WebSocketDisconnect:
            pass

    return _Servidor(app, sock)


class LaPuertaPasaCadaPedido(Prueba):
    def setUp(self):
        super().setUp()
        if not HAY_SERVE:
            self.skipTest("sin el extra «serve»")
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.detras = []
        for usuario in ("nico", "pablo"):
            (base / usuario).mkdir()
            self.detras.append(_detras(puerta.socket_de(usuario, base), usuario))
        app = puerta.crear(tabla(), identificar=identificar(), sockets=base)
        self.base = base
        self.c = TestClient(app, base_url="https://telar.ejemplo.ts.net")

    def tearDown(self):
        for d in self.detras:
            d.parar()
        self._tmp.cleanup()
        super().tearDown()

    def get(self, ip, ruta="/api/eco?x=1", **kw):
        return self.c.get(ruta, headers={"x-forwarded-for": ip, **kw.pop("headers", {})}, **kw)

    def test_cada_persona_a_su_telar_por_la_misma_direccion(self):
        a, b = self.get(NICO).json(), self.get(PABLO).json()
        self.assertEqual((a["quien"], b["quien"]), ("nico", "pablo"))
        self.assertEqual((a["ruta"], a["query"]), ("/api/eco", "x=1"))
        self.assertEqual(a["cabeceras"]["host"], "telar.ejemplo.ts.net")  # el Host pasa tal cual
        self.assertEqual(b["cabeceras"]["x-telar-persona"], "pablo")

    def test_detras_de_tailscale_serve_el_host_es_el_de_x_forwarded_host(self):
        # a un socket, tailscale serve le manda Host: localhost y la dirección de verdad en X-Forwarded-Host
        h = {"x-forwarded-for": NICO, "host": "localhost", "x-forwarded-host": "telar.x.ts.net:8444"}
        self.assertEqual(self.c.get("/api/eco", headers=h).json()["cabeceras"]["host"], "telar.x.ts.net:8444")
        h["origin"] = "https://telar.x.ts.net:8444"
        self.assertEqual(self.c.post("/api/eco", content=b"x", headers=h).status_code, 200)
        h["origin"] = "https://localhost"
        self.assertEqual(self.c.post("/api/eco", content=b"x", headers=h).status_code, 403)

    def test_la_cookie_y_un_x_telar_persona_falso_no_pasan(self):
        r = self.get(PABLO, headers={"cookie": "telar_panel=de-nico", "x-telar-persona": "nico"}).json()
        self.assertNotIn("cookie", r["cabeceras"])
        self.assertEqual(r["cabeceras"]["x-telar-persona"], "pablo")

    def test_quien_no_tiene_lugar_ve_por_que(self):
        r = self.get("100.99.0.1", headers={"accept": "text/html"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("telar servidor pedir", r.text)
        self.assertEqual(self.get(SERVIDOR).status_code, 403)

    def test_quien_no_tiene_lugar_solo_llega_a_unirse_y_va_al_de_quien_administra(self):
        r = self.get("100.99.0.1", "/unirse/servidor")
        self.assertEqual(r.json()["quien"], "nico")
        self.assertEqual(self.get("100.99.0.1", "/unirses").status_code, 403)

    def test_escribir_desde_otra_pagina_no(self):
        h = {"x-forwarded-for": NICO, "origin": "https://malo.example"}
        self.assertEqual(self.c.post("/api/eco", content=b"x", headers=h).status_code, 403)
        h["origin"] = "https://telar.ejemplo.ts.net"
        r = self.c.post("/api/eco", content=b"hola", headers=h)
        self.assertEqual((r.status_code, r.json()["largo"]), (200, 4))

    def test_la_terminal_va_a_su_telar(self):
        # con uvicorn de verdad (el cliente de pruebas corta el cierre de un WebSocket antes de que la puerta termine)
        import asyncio

        from websockets.asyncio.client import unix_connect

        sock = self.base / "puerta.sock"
        app = puerta.crear(tabla(), identificar=identificar(), sockets=self.base)
        servidor = _Servidor(app, sock)
        self.addCleanup(servidor.parar)

        async def hablar():
            cab = {"x-forwarded-for": PABLO, "origin": "https://telar.ejemplo.ts.net",
                   "x-forwarded-host": "telar.ejemplo.ts.net"}
            async with unix_connect(str(sock), "ws://localhost/pty?hilo=x", additional_headers=cab) as ws:
                await ws.send("hola")
                return await asyncio.wait_for(ws.recv(), 5)

        self.assertEqual(asyncio.run(hablar()), "pablo:hola:https://telar.ejemplo.ts.net")

    def test_la_terminal_que_pide_otra_maquina_lleva_su_llave_del_bus(self):
        # la página del laptop de Pablo reenvía la terminal de un hilo que vive en el servidor: sin navegador (sin
        # origen), con la llave del bus; si la puerta se la quitaba, su telar la rechazaba (InvalidStatus)
        import asyncio

        from websockets.asyncio.client import unix_connect

        sock = self.base / "puerta.sock"
        servidor = _Servidor(puerta.crear(tabla(), identificar=identificar(), sockets=self.base), sock)
        self.addCleanup(servidor.parar)

        async def hablar():
            cab = {"x-forwarded-for": PABLO, "x-forwarded-host": "telar.ejemplo.ts.net", "authorization": "Bearer secreto"}
            async with unix_connect(str(sock), "ws://localhost/pty?hilo=x", additional_headers=cab) as ws:
                await ws.send("hola")
                return await asyncio.wait_for(ws.recv(), 5)

        self.assertEqual(asyncio.run(hablar()), "pablo:hola:|Bearer secreto")

    def test_una_terminal_de_quien_no_tiene_lugar_no_abre(self):
        import asyncio

        from websockets.asyncio.client import unix_connect
        from websockets.exceptions import ConnectionClosed, InvalidStatus

        sock = self.base / "puerta.sock"
        servidor = _Servidor(puerta.crear(tabla(), identificar=identificar(), sockets=self.base), sock)
        self.addCleanup(servidor.parar)

        async def hablar():
            async with unix_connect(str(sock), "ws://telar.ejemplo.ts.net/pty?hilo=x",
                                    additional_headers={"x-forwarded-for": "100.99.0.1"}) as ws:
                await ws.recv()

        with self.assertRaises((ConnectionClosed, InvalidStatus)):
            asyncio.run(hablar())

    def test_si_su_telar_no_corre_lo_dice(self):
        self.detras[1].parar()
        r = self.get(PABLO, headers={"accept": "text/html"})
        self.assertEqual(r.status_code, 502)
        self.assertIn("no está corriendo", r.text)


class LaPaginaDetrasDeLaPuerta(Prueba):
    def setUp(self):
        super().setUp()
        if not HAY_SERVE:
            self.skipTest("sin el extra «serve»")
        from telar import api_web

        interna = FastAPI()
        interna.get("/salud")(lambda: {"ok": True})
        self.puerta = TestClient(api_web.crear(interna, clave="llave", puerta=True), base_url="https://telar.x.ts.net")
        self.sola = TestClient(api_web.crear(interna, clave="llave"), base_url="https://telar.x.ts.net")

    def test_no_pide_la_llave(self):
        self.assertEqual(self.puerta.get("/api/salud").status_code, 200)
        self.assertEqual(self.sola.get("/api/salud").status_code, 403)

    def test_escribir_desde_otra_pagina_sigue_sin_poderse(self):
        r = self.puerta.post("/api/salud", headers={"origin": "https://malo.example"})
        self.assertEqual(r.status_code, 403)


class InstalarDetrasDeLaPuerta(Prueba):
    def test_sin_puerto_propio(self):
        a = instalacion.argumentos(nodo=True, web_socket="/run/telar/pablo/web.sock", web_url="https://telar.x.ts.net")
        self.assertEqual(a, ["serve", "--nodo", "--web-socket", "/run/telar/pablo/web.sock", "--web-url", "https://telar.x.ts.net"])

    def test_quien_administra_sigue_con_su_puerto_y_ademas_la_puerta(self):
        a = instalacion.argumentos(nodo=True, web_socket="/run/telar/nico/web.sock")
        self.assertEqual(a, ["serve", "--nodo", "--web", "--web-socket", "/run/telar/nico/web.sock"])


class AlojarConPuerta(Prueba):
    """El ayudante de root, en seco, con la puerta instalada."""

    def setUp(self):
        super().setUp()
        from test_alojamiento import _cargar_ayudante

        self.m = _cargar_ayudante()
        self._tmp = tempfile.TemporaryDirectory()
        conf = Path(self._tmp.name) / "puerta.toml"
        conf.write_text('url = "https://telar.x.ts.net"\n')
        self.m.PUERTA = conf
        self.crear = {"accion": "crear", "nombre": "pablo", "llave": "", "secreto": "s" * 48,
                      "bus": "nats://100.66.75.117:4222", "memoria": "2500M", "cpu": "100%",
                      "tailscale": "pablo.ferre@gmail.com"}

    def tearDown(self):
        self._tmp.cleanup()
        super().tearDown()

    def test_su_pagina_va_por_su_socket_y_entra_por_la_puerta(self):
        pasos = self.m.plan(self.m.validar(self.crear))
        instalar = next(p for p in pasos if "uv, Claude Code" in p.texto)
        self.assertIn("--web-socket /run/telar/pablo/web.sock --web-url 'https://telar.x.ts.net' --si", instalar.stdin)
        self.assertNotIn("--web-puerto", instalar.stdin)
        carpeta = next(p for p in pasos if p.archivo and "tmpfiles" in p.archivo[0])
        self.assertEqual(carpeta.archivo[1], "d /run/telar/pablo 2750 pablo telar-puerta -\n")
        # la carpeta existe antes de que arranque su telar
        self.assertLess(pasos.index(carpeta), pasos.index(instalar))
        registro = json.loads(next(p for p in pasos if p.archivo and p.archivo[0].endswith("/pablo.json")).archivo[1])
        self.assertEqual(registro["tailscale"], "pablo.ferre@gmail.com")
        self.assertNotIn("puerto", registro)

    def test_sin_su_cuenta_o_con_una_rara_no(self):
        for cuenta in (None, "", "a b@x.com", "x@y; reboot", "'$(id)'@x"):
            with self.assertRaises(self.m.Rechazo, msg=str(cuenta)):
                self.m.validar({**self.crear, "tailscale": cuenta})

    def test_quitar_borra_su_carpeta_de_la_puerta(self):
        pasos = self.m.plan(self.m.validar({"accion": "quitar", "nombre": "pablo"}))
        self.assertTrue(any(p.argv and "/run/telar/pablo" in p.argv for p in pasos))


class LaVersionDeLaPuerta(Prueba):
    """Si la puerta quedó atrás de telar: la página se lo avisa a quien la administra, y doctor también."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        self.conf = self.d / "puerta.toml"
        self.conf.write_text('url = "https://telar.x.ts.net"\n[personas]\n"nico@x.com" = "nico"\n')
        self.base = self.d / "opt"

    def tearDown(self):
        self._tmp.cleanup()
        super().tearDown()

    def instalar(self, version: str) -> None:
        meta = self.base / "lib" / "python3.12" / "site-packages" / f"telar-{version}.dist-info"
        meta.mkdir(parents=True)
        (meta / "METADATA").write_text(f"Metadata-Version: 2.1\nName: telar\nVersion: {version}\n\nlo demás\n")

    def test_lee_la_version_sin_correrla(self):
        self.assertEqual(puerta.version_instalada(self.base), "")
        self.instalar("0.7.0")
        self.assertEqual(puerta.version_instalada(self.base), "0.7.0")

    def test_atras_y_la_orden_solo_para_quien_administra(self):
        self.instalar("0.0.1")
        e = puerta.estado("nico", config=self.conf, base=self.base)
        self.assertTrue(e["administra"] and e["atras"])
        self.assertIn("--dueno nico --cuenta nico@x.com --version", e["actualizar"])
        otro = puerta.estado("pablo", config=self.conf, base=self.base)
        self.assertFalse(otro["administra"])
        self.assertNotIn("actualizar", otro)
        self.assertIsNone(puerta.estado("nico", config=self.d / "no-hay.toml", base=self.base))

    def test_al_dia_no_avisa(self):
        from telar import __version__

        self.instalar(__version__)
        self.assertFalse(puerta.estado("nico", config=self.conf, base=self.base)["atras"])


class DoctorEnElServidor(Prueba):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        (self.d / "registro").mkdir()
        (self.d / "run" / "nico").mkdir(parents=True)
        (self.d / "run" / "pablo").mkdir()
        self.conf = self.d / "puerta.toml"
        self.conf.write_text('url = "https://telar.x.ts.net"\n[personas]\n"nico@x.com" = "nico"\n')
        spool = self.d / "spool"
        for x in ("pendientes", "resultados"):
            (spool / x).mkdir(parents=True)
        spool.chmod(0o700)
        self.spool = spool
        (self.d / "telar-alojar").write_text("#!/bin/sh\n")

    def tearDown(self):
        self._tmp.cleanup()
        super().tearDown()

    def revisar(self, alojados=None, **kw):
        from telar import alojamiento, unirse
        from telar.ordenes import doctor

        with mock.patch.object(puerta, "CONFIG", self.conf), \
                mock.patch.object(puerta, "estado", lambda u: {"version": "0.7.1", "telar": "0.7.1", "atras": False,
                                                               "administra": u == "nico", "url": "https://telar.x.ts.net"}), \
                mock.patch.object(alojamiento, "leer", return_value=alojados or {}), \
                mock.patch.object(unirse, "administra_aqui", return_value=True):
            return doctor._servidor(None, spool=self.spool, ayudante=self.d / "telar-alojar", registro=self.d / "registro",
                                    sockets=self.d / "run", usuario="nico", activo=lambda u: True, **kw)

    def test_todo_en_su_sitio(self):
        (self.d / "run" / "nico" / "web.sock").write_text("")
        (self.d / "registro" / "pablo.json").write_text(json.dumps({"nombre": "pablo", "tailscale": "pablo@x.com"}))
        r = self.revisar({"pablo": {"estado": "activo"}})
        self.assertEqual([x["estado"] for x in r], ["ok", "ok", "ok"], r)

    def test_sin_mi_socket_y_un_alojado_sin_cuenta(self):
        (self.d / "registro" / "pablo.json").write_text(json.dumps({"nombre": "pablo", "puerto": 8781}))
        r = self.revisar({"pablo": {"estado": "activo"}})
        fallas = [x["dice"] for x in r if x["estado"] == "falla"]
        self.assertTrue(any("no escucha para la puerta" in x for x in fallas), r)
        self.assertTrue(any("cuenta de Tailscale" in x for x in fallas), r)

    def test_sin_el_ayudante_con_alojados_es_falla(self):
        (self.d / "telar-alojar").unlink()
        (self.d / "run" / "nico" / "web.sock").write_text("")
        r = self.revisar({})
        self.assertEqual(r[0]["estado"], "aviso")
        r = self.revisar({"pablo": {"estado": "activo"}})
        self.assertEqual(r[0]["estado"], "falla")
