"""Unirse a un equipo (telar.unirse): el manifiesto, la puerta del bus con sus resguardos, y aprobar o rechazar."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cuentas, unirse

MANIFIESTO = """nombre: faro
administra: ana
bus: nats://servidor:4222
modulos:
  grafo: https://example.com/telar-grafo
requiere: [git]
"""

QUIEN = {"cuenta": "beto@example.com", "maquina": "laptop-de-beto"}
#: hashes con la forma de bcrypt (la puerta mira la forma; no hace falta bcrypt para probarla)
HASH_ANA = "$2b$11$" + "a" * 53
HASH_BETO = "$2b$11$" + "b" * 53


class ElManifiesto(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "faro"
        (self.repo / ".telar").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".telar" / "equipo.yaml").write_text(MANIFIESTO, encoding="utf-8")

    def test_se_lee_y_se_encuentra_desde_una_carpeta_del_repo(self):
        e = unirse.buscar(self.repo / "docs")
        self.assertEqual((e.nombre, e.administra, e.bus, e.url_puerta), ("faro", "ana", "nats://servidor:4222",
                                                                           "http://servidor:8780"))
        self.assertEqual(e.modulos, {"grafo": "https://example.com/telar-grafo"})
        self.assertEqual(e.repo.resolve(), self.repo.resolve())
        self.assertEqual(unirse.faltan(e), [])  # git sí está

    def test_sin_manifiesto_no_hay_equipo(self):
        (self.repo / ".telar" / "equipo.yaml").unlink()
        self.assertIsNone(unirse.buscar(self.repo))

    def test_un_manifiesto_que_no_sirve(self):
        for malo in ("nombre: Faro Grande\nbus: nats://s:4222\n", "nombre: faro\nbus: http://s\n",
                     "nombre: faro\nbus: nats://s:4222\notra: 1\n", "nombre: faro\nbus: nats://s:4222\nrequiere: tmux\n",
                     "- una\n- lista\n", "nombre: faro\nbus: nats://s:4222\npuerta: ftp://x\n"):
            (self.repo / ".telar" / "equipo.yaml").write_text(malo, encoding="utf-8")
            with self.assertRaises(unirse.ErrorDeUnirse, msg=malo):
                unirse.buscar(self.repo)

    def test_lo_que_falta(self):
        (self.repo / ".telar" / "equipo.yaml").write_text(MANIFIESTO.replace("[git]", "[git, no-existe-este]"))
        self.assertEqual(unirse.faltan(unirse.buscar(self.repo)), ["no-existe-este"])


class LaPuerta(Prueba):
    """La máquina del bus: los pedidos, con las cuentas en una carpeta temporal (XDG_CONFIG_HOME)."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        entorno = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp.name})
        entorno.start()
        self.addCleanup(entorno.stop)
        cuentas.escribir(cuentas.carpeta(), {"ana": HASH_ANA})
        self.hash = HASH_BETO

    def pedir(self, persona="beto", ip="100.70.1.2", quien=QUIEN):
        return unirse.recibir({"persona": persona, "maquina": "mac", "hash": self.hash, "equipo": "faro"}, ip, quien)

    def test_solo_atiende_la_maquina_del_bus(self):
        self.assertTrue(unirse.administra_aqui())
        (cuentas.carpeta() / "servidor.conf").unlink()
        self.assertFalse(unirse.administra_aqui())

    def test_solo_desde_tailscale(self):
        self.assertTrue(unirse.de_tailscale("100.70.1.2"))
        self.assertTrue(unirse.de_tailscale("fd7a:115c:a1e0::1"))
        for otra in ("192.168.1.5", "8.8.8.8", "127.0.0.1", "testclient", ""):
            self.assertFalse(unirse.de_tailscale(otra), otra)

    def test_un_pedido_queda_pendiente_y_no_da_acceso(self):
        r = self.pedir()
        self.assertEqual(r["estado"], "pendiente")
        self.assertNotIn("beto", cuentas.leer(cuentas.carpeta()))
        p = unirse.leer_pedidos()[r["id"]]
        self.assertEqual((p["persona"], p["tailscale"], p["nodo"], p["equipo"]), ("beto", "beto@example.com",
                                                                                  "laptop-de-beto", "faro"))
        self.assertEqual(unirse.estado(r["id"], "100.70.1.2")["estado"], "pendiente")
        with self.assertRaises(unirse.ErrorDeUnirse):  # otra máquina no puede preguntar por él
            unirse.estado(r["id"], "100.70.9.9")

    def test_aprobar_le_da_la_cuenta_y_rechazar_no(self):
        r = self.pedir()
        p = unirse.decidir(r["id"], aprobar=True)
        self.assertEqual(p["estado"], "aprobado")
        self.assertEqual(cuentas.leer(cuentas.carpeta())["beto"], self.hash)
        self.assertIn("beto", (cuentas.carpeta() / "servidor.conf").read_text())
        with self.assertRaises(unirse.ErrorDeUnirse):  # dos veces, no
            unirse.decidir(r["id"], aprobar=True)
        r2 = self.pedir(persona="carla", quien={"cuenta": "carla@example.com", "maquina": "pc"})
        unirse.decidir(r2["id"], aprobar=False)
        self.assertNotIn("carla", cuentas.leer(cuentas.carpeta()))
        self.assertEqual(unirse.leer_pedidos()[r2["id"]]["estado"], "rechazado")

    def test_nombres_que_ya_estan(self):
        with self.assertRaises(unirse.ErrorDeUnirse):  # ya tiene cuenta
            self.pedir(persona="ana")
        r1 = self.pedir()
        r2 = self.pedir()  # la misma persona lo intenta de nuevo: reemplaza al pendiente
        self.assertEqual(list(unirse.leer_pedidos()), [r2["id"]])
        self.assertNotEqual(r1["id"], r2["id"])
        with self.assertRaises(unirse.ErrorDeUnirse):  # otra cuenta de Tailscale con el mismo nombre: no
            self.pedir(quien={"cuenta": "otro@example.com", "maquina": "x"})

    def test_lo_que_trae_un_pedido(self):
        with self.assertRaises(cuentas.ErrorDeCuentas):
            self.pedir(persona="Beto Grande")
        with self.assertRaises(unirse.ErrorDeUnirse):
            unirse.recibir({"persona": "beto", "hash": "no es un hash"}, "100.70.1.2", QUIEN)

    def test_el_tope_por_hora(self):
        tope = unirse.Tope(tope=2)
        self.assertEqual([tope.pasa("100.70.1.2", ahora=t) for t in (0, 10, 20)], [True, True, False])
        self.assertTrue(tope.pasa("100.70.1.3", ahora=20))  # otra dirección, su propia cuenta
        self.assertTrue(tope.pasa("100.70.1.2", ahora=3700))  # pasada la hora

    def test_quien_es_sin_tailscale_no_sabe(self):
        with mock.patch.object(unirse.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(unirse.ErrorDeUnirse):
                unirse.quien_es("100.70.1.2")
        salida = json.dumps({"UserProfile": {"LoginName": "beto@example.com"}, "Node": {"ComputedName": "mac-beto"}})
        with mock.patch.object(unirse.subprocess, "run", return_value=SimpleNamespace(stdout=salida)):
            self.assertEqual(unirse.quien_es("100.70.1.2"), {"cuenta": "beto@example.com", "maquina": "mac-beto"})


try:
    from fastapi.testclient import TestClient

    from telar import api_web
except ImportError:  # sin el extra «serve»
    api_web = None


@unittest.skipIf(api_web is None, "sin fastapi")
class LaPuertaEnLaPagina(LaPuerta):
    def cliente(self, ip):
        from fastapi import FastAPI

        app = api_web.crear(FastAPI(), clave="llave-de-prueba")

        async def desde(scope, receive, send):  # la dirección de quien pide, como la vería telar serve
            await app({**scope, "client": (ip, 50000)} if scope["type"] in ("http", "websocket") else scope, receive, send)

        return TestClient(desde)

    def test_sin_llave_pero_con_sus_resguardos(self):
        cuerpo = {"persona": "beto", "maquina": "mac", "hash": self.hash, "equipo": "faro"}
        with mock.patch.object(unirse, "quien_es", return_value=QUIEN):
            r = self.cliente("100.70.1.2").post("/unirse", json=cuerpo)
            self.assertEqual(r.status_code, 200, r.text)
            pid = r.json()["id"]
            self.assertEqual(self.cliente("100.70.1.2").get(f"/unirse/{pid}").json()["estado"], "pendiente")
            self.assertEqual(self.cliente("192.168.1.5").post("/unirse", json=cuerpo).status_code, 403)  # fuera de la red
            self.assertEqual(self.cliente("100.70.1.2").post("/unirse", content=b"[1]").status_code, 422)
            self.assertEqual(self.cliente("100.70.1.2").get("/api/hilos").status_code, 403)  # lo demás sigue con llave
        with mock.patch.object(unirse, "quien_es", side_effect=unirse.ErrorDeUnirse("Tailscale no sabe")):
            self.assertEqual(self.cliente("100.70.1.4").post("/unirse", json=cuerpo).status_code, 422)
        (cuentas.carpeta() / "servidor.conf").unlink()
        self.assertEqual(self.cliente("100.70.1.2").post("/unirse", json=cuerpo).status_code, 404)

    def test_el_tope_de_la_pagina(self):
        cuerpo = {"persona": "beto", "maquina": "mac", "hash": self.hash, "equipo": "faro"}
        c = self.cliente("100.70.1.7")
        with mock.patch.object(unirse, "quien_es", return_value=QUIEN):
            codigos = [c.post("/unirse", json=cuerpo).status_code for _ in range(unirse.TOPE_POR_HORA + 1)]
        self.assertEqual(codigos[-1], 429)
        self.assertEqual(set(codigos[:-1]), {200})


class AlInstalar(Prueba):
    """`telar instalar --unirse`: el plan que arma desde el manifiesto."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "faro"
        (self.repo / ".telar").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".telar" / "equipo.yaml").write_text(MANIFIESTO, encoding="utf-8")
        self.conf = Path(self.tmp.name) / "config.toml"

    def plan(self, *argv, config=None):
        from telar.ordenes import instalar

        p = instalar._comun.analizador("instalar", "")
        o = SimpleNamespace(bus="", token=str(Path(self.tmp.name) / "bus.token"), persona="", sin_servicio=True,
                            sin_agente=True, unirse=str(self.repo), si=True, seco=False)
        for k, v in zip(argv[::2], argv[1::2]):
            setattr(o, k, v)
        config = config or SimpleNamespace(bus=SimpleNamespace(url="", persona=""), repos=(), modulos=())
        p  # noqa: B018
        return instalar._plan(SimpleNamespace(config=config), o, self.conf)

    def test_pide_entrar_y_deja_el_bus_el_repo_y_los_modulos(self):
        from telar import api_web

        with mock.patch.object(api_web, "ruta_llave", return_value=self.conf):  # que no proponga crear la llave
            self.conf.write_text("")
            pasos = [que for _, que in self.plan("persona", "beto")]
        self.assertTrue(any("pedir entrar al bus de «faro» como «beto»" in q for q in pasos), pasos)
        self.assertTrue(any("unirse al bus nats://servidor:4222" in q for q in pasos), pasos)
        self.assertTrue(any("como «faro»" in q for q in pasos), pasos)
        self.assertTrue(any("instalar el módulo grafo" in q for q in pasos), pasos)

    def test_lo_que_ya_esta_no_se_repite(self):
        from telar import api_web

        config = SimpleNamespace(bus=SimpleNamespace(url="nats://servidor:4222", persona="beto"),
                                 repos=(SimpleNamespace(nombre="faro"),), modulos=(SimpleNamespace(nombre="grafo"),))
        with mock.patch.object(api_web, "ruta_llave", return_value=self.conf):
            self.conf.write_text("")
            self.assertEqual(self.plan(config=config), [])

    def test_lo_que_no_se_puede(self):
        from telar.ordenes import instalar

        with self.assertRaises(instalar.ErrorDeUso):  # otro bus
            self.plan(config=SimpleNamespace(bus=SimpleNamespace(url="nats://otro:4222", persona=""), repos=(), modulos=()))
        with self.assertRaises(instalar.ErrorDeUso):  # un nombre que el bus no acepta
            self.plan("persona", "Beto Grande")
        (self.repo / ".telar" / "equipo.yaml").write_text(MANIFIESTO.replace("[git]", "[git, no-existe-este]"))
        with self.assertRaises(instalar.ErrorDeUso) as e:
            self.plan("persona", "beto")
        self.assertIn("no-existe-este", str(e.exception))
        (self.repo / ".telar" / "equipo.yaml").unlink()
        with self.assertRaises(instalar.ErrorDeUso):  # sin manifiesto
            self.plan("persona", "beto")


if __name__ == "__main__":
    unittest.main()
