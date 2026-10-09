import unittest
from types import SimpleNamespace as N
from unittest import mock

from telar.ordenes import web


class Teclas(unittest.TestCase):
    def setUp(self):
        web._ultima_tecla[0] = 0.0

    def test_solo_valen_las_teclas_de_la_lista(self):
        self.assertEqual(web.teclear_hilo(None, {"hilo": "Faro", "tecla": "rm -rf"})[0], 400)
        self.assertEqual(web.teclear_hilo(None, {"hilo": "Faro"})[0], 400)
        self.assertEqual(web.teclear_hilo(None, [])[0], 400)

    def test_un_hilo_que_no_esta_abierto_no_recibe_teclas(self):
        with mock.patch.object(web, "_objetivo_terminal", return_value=None):
            self.assertEqual(web.teclear_hilo(None, {"hilo": "Faro", "tecla": "enter"})[0], 404)

    def test_la_tecla_se_traduce_al_nombre_de_tmux(self):
        with mock.patch.object(web, "_objetivo_terminal", return_value="@20"), \
             mock.patch.object(web.subprocess, "run", return_value=N(returncode=0, stderr="")) as correr:
            self.assertEqual(web.teclear_hilo(None, {"hilo": "Faro", "tecla": "esc"}), (200, {"ok": True}))
        self.assertEqual(correr.call_args.args[0], ["tmux", "send-keys", "-t", "@20", "Escape"])


if __name__ == "__main__":
    unittest.main()
