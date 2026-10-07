import json
import unittest
from types import SimpleNamespace as N
from unittest import mock

from telar.ordenes import web

HILOS = {"hilos": [{"nombre": "Faro", "vivo": True, "propio": False}, {"nombre": "Gestión", "vivo": False, "propio": True},
                   {"nombre": "Dormido", "vivo": False, "propio": False}]}


class CerrarUnHilo(unittest.TestCase):
    def setUp(self):
        web._ultimo_nuevo[0] = 0.0
        self.ctx = N(config=N())
        patch = mock.patch.object(web, "datos", return_value=json.dumps(HILOS).encode())
        patch.start()
        self.addCleanup(patch.stop)
        agentes = mock.patch("telar.agentes.descubrir", return_value=[N(clave="gestion", nombre="Gestión")])
        agentes.start()
        self.addCleanup(agentes.stop)

    def test_lo_que_no_existe_o_ya_esta_cerrado_se_dice(self):
        self.assertEqual(web.cerrar_hilo(self.ctx, {})[0], 400)
        self.assertEqual(web.cerrar_hilo(self.ctx, {"hilo": "Nadie"})[0], 404)
        self.assertEqual(web.cerrar_hilo(self.ctx, {"hilo": "Dormido"})[0], 409)

    def test_un_agente_residente_no_se_cierra_desde_la_pagina(self):
        with mock.patch.object(web.subprocess, "run") as correr:
            self.assertEqual(web.cerrar_hilo(self.ctx, {"hilo": "Gestión"})[0], 403)
        correr.assert_not_called()

    def test_un_hilo_abierto_se_archiva_y_se_cierra(self):
        with mock.patch.object(web.subprocess, "run", return_value=N(returncode=0, stdout="", stderr="")) as correr:
            self.assertEqual(web.cerrar_hilo(self.ctx, {"hilo": "Faro"}), (200, {"ok": True, "hilo": "Faro"}))
        self.assertEqual(correr.call_args.args[0][-4:], ["--hilo", "Faro", "archivar", "--cerrar"][-4:])


if __name__ == "__main__":
    unittest.main()
