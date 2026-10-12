import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest import mock

from telar.ordenes import web


class DejarLectura(unittest.TestCase):
    def setUp(self):
        web._ultimo_envio[0] = 0.0
        self.raiz = Path(tempfile.mkdtemp())
        (self.raiz / "kichoro" / "bin").mkdir(parents=True)
        (self.raiz / "kichoro" / "bin" / "lecturas").write_text("#!/bin/sh\n")
        self.ctx = N(config=N(raiz=str(self.raiz)))

    def test_solo_se_aceptan_direcciones_http(self):
        for url in ("javascript:alert(1)", "file:///etc/passwd", "https://a b"):
            self.assertEqual(web.dejar_lectura(self.ctx, {"url": url, "nota": ""})[0], 400)
        self.assertEqual(web.dejar_lectura(self.ctx, {"url": "", "nota": ""})[0], 400)

    def test_la_direccion_va_como_argumento_y_no_por_shell(self):
        with mock.patch.object(web.subprocess, "run", return_value=N(returncode=0, stdout="", stderr="")) as correr:
            self.assertEqual(web.dejar_lectura(self.ctx, {"url": "https://x.cl/a?b=1&c=2", "nota": "; rm -rf /"}), (200, {"ok": True}))
        args = correr.call_args.args[0]
        self.assertEqual(args[1:], ["dejar", "https://x.cl/a?b=1&c=2", "--nota", "; rm -rf /", "--de", "nico"])
        self.assertIsInstance(args, list)

    def test_sin_el_feed_en_esta_maquina_se_dice(self):
        self.assertEqual(web.dejar_lectura(N(config=N(raiz=str(self.raiz / "otra"))), {"url": "https://x.cl", "nota": ""})[0], 404)


if __name__ == "__main__":
    unittest.main()
