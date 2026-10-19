"""La página de telar en el navegador (telar.api_web): la llave, la cookie, el origen y la API adentro."""

from __future__ import annotations

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
        self.assertEqual(c.get("/estatico/progreso.json").status_code, 200)

    def test_lo_que_escribe_tiene_que_venir_de_aqui(self):
        c = _app()
        c.cookies.set(api_web.COOKIE, "llave-de-prueba")
        self.assertEqual(c.post("/api/algo", headers={"Origin": "http://telar:8780"}).status_code, 200)
        self.assertEqual(c.post("/api/algo", headers={"Origin": "https://ajeno.example"}).status_code, 403)
        self.assertEqual(c.post("/api/algo").status_code, 200)  # sin Origin (curl): manda la llave
