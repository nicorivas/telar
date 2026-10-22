"""`telar serve --equipo` sin nadie con llave: avisa y arranca sin la página del equipo, no se cae."""

import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from telar import equipo as mod_equipo
from telar.ordenes import serve


class ServeSinEquipo(unittest.TestCase):
    def _servir(self, cargar):
        corridas = []
        err = io.StringIO()
        with mock.patch.object(mod_equipo, "cargar", cargar), \
                mock.patch.object(serve, "_correr", lambda uv, principal, otros, nodo=None: corridas.append(otros)), \
                mock.patch("telar.salida.recortar_registro"), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            codigo = serve.main(["--equipo", "--puerto", "8771"], mock.Mock())
        return codigo, corridas, err.getvalue()

    def test_sin_personas_arranca_sin_la_pagina(self):
        codigo, corridas, err = self._servir(lambda *a, **k: mod_equipo.Equipo(Path("."), None, personas={}))
        self.assertEqual(codigo, 0)
        self.assertEqual(corridas, [[]])
        self.assertIn("no hay nadie en [equipo.personas]", err)

    def test_equipo_mal_escrito_arranca_igual(self):
        def roto(*a, **k):
            raise ValueError("[equipo.personas] debe ser una tabla")

        codigo, corridas, err = self._servir(roto)
        self.assertEqual(codigo, 0)
        self.assertEqual(corridas, [[]])
        self.assertIn("debe ser una tabla", err)

    def test_con_personas_sirve_la_pagina(self):
        eq = mod_equipo.Equipo(Path("."), None, personas={"ramiro": "x" * 20})
        with mock.patch("telar.ordenes.equipo.ip_de_tailscale", return_value=""), \
                mock.patch("telar.api_equipo.crear", return_value=object()):
            codigo, corridas, _ = self._servir(lambda *a, **k: eq)
        self.assertEqual(codigo, 0)
        self.assertEqual(len(corridas[0]), 1)


if __name__ == "__main__":
    unittest.main()
