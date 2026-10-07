import unittest
from types import SimpleNamespace as N
from unittest import mock

from telar.ordenes import web


class LanzarUnAtajo(unittest.TestCase):
    def setUp(self):
        self.ctx = N(config=N(atajos=[N(tecla="m", nombre="⚑ correo", mensaje="/correo", descripcion="", agente="")]))

    def test_solo_vale_la_tecla_de_un_atajo_declarado(self):
        self.assertEqual(web.lanzar_atajo(self.ctx, {"tecla": "x"}, ())[0], 404)
        self.assertEqual(web.lanzar_atajo(self.ctx, {}, ())[0], 400)

    def test_el_mensaje_sale_de_la_configuracion_y_no_de_la_pagina(self):
        with mock.patch.object(web, "nuevo_hilo", return_value=(200, {"ok": True, "hilo": "h"})) as nuevo:
            codigo, r = web.lanzar_atajo(self.ctx, {"tecla": "m", "mensaje": "rm -rf"}, ())
        self.assertEqual(codigo, 200)
        self.assertEqual(nuevo.call_args.args[1]["mensaje"], "/correo")
        self.assertTrue(nuevo.call_args.args[1]["nombre"].startswith("⚑ correo "))


if __name__ == "__main__":
    unittest.main()
