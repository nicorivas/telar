"""Las cuentas del bus (telar.cuentas): una por persona, en la configuración de nats-server."""

from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cuentas

HASH = "$2b$11$" + "a" * 53


class LasCuentas(Prueba):
    def test_nombres(self):
        self.assertEqual(cuentas.validar("marcelo"), "marcelo")
        for malo in ("", "Nico", "1nico", "ni co", "ni.co", "a" * 33, "$G"):
            with self.subTest(malo=malo), self.assertRaises(cuentas.ErrorDeCuentas):
                cuentas.validar(malo)

    def test_configuracion_una_cuenta_por_persona(self):
        conf = cuentas.configuracion({"nico": HASH, "marcelo": HASH})
        self.assertLess(conf.index("marcelo: {"), conf.index("nico: {"))
        self.assertEqual(conf.count("jetstream: enabled"), 2)
        self.assertIn(f'users: [ {{ user: "nico", password: "{HASH}" }} ]', conf)

    def test_escribir_y_leer(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "bus"
            conf = cuentas.escribir(base, {"nico": HASH, "pablo": HASH})
            self.assertEqual(cuentas.leer(base), {"nico": HASH, "pablo": HASH})
            self.assertEqual(stat.S_IMODE(conf.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(base.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((base / "personas" / "nico.hash").stat().st_mode), 0o600)
            cuentas.escribir(base, {"nico": HASH})  # quitar a una persona borra su hash
            self.assertEqual(cuentas.leer(base), {"nico": HASH})
            self.assertNotIn("pablo", conf.read_text())

    def test_leer_rechaza_lo_que_no_es_un_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "personas").mkdir()
            (Path(tmp) / "personas" / "nico.hash").write_text("secreto-en-claro\n")
            with self.assertRaises(cuentas.ErrorDeCuentas):
                cuentas.leer(Path(tmp))

    def test_hashear(self):
        try:
            import bcrypt
        except ImportError:
            self.skipTest("sin bcrypt (el extra «bus»)")
        h = cuentas.hashear("s" * 48)
        self.assertRegex(h, cuentas.BCRYPT)
        self.assertTrue(bcrypt.checkpw(b"s" * 48, h.encode()))


if __name__ == "__main__":
    unittest.main()
