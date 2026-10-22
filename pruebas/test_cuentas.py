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
        self.assertEqual(cuentas.validar("ramiro"), "ramiro")
        for malo in ("", "Ana", "1ana", "a na", "a.na", "a" * 33, "$G"):
            with self.subTest(malo=malo), self.assertRaises(cuentas.ErrorDeCuentas):
                cuentas.validar(malo)

    def test_configuracion_una_cuenta_por_persona(self):
        conf = cuentas.configuracion({"ana": HASH, "ramiro": HASH})
        self.assertLess(conf.index("ana: {"), conf.index("ramiro: {"))
        self.assertEqual(conf.count("jetstream: enabled"), 2)
        self.assertIn(f'users: [ {{ user: "ana", password: "{HASH}" }} ]', conf)

    def test_entre_cuentas_cruzan_solo_el_correo_y_el_directorio(self):
        conf = cuentas.configuracion({"ana": HASH, "ramiro": HASH, "pedro": HASH})
        self.assertIn('{ service: "correo.ana" }', conf)
        self.assertIn('{ stream: "directorio.ana" }', conf)
        # cada una importa los de las demás, el correo con share (quien recibe sabe de qué cuenta viene)
        self.assertIn('{ service: { account: "ramiro", subject: "correo.ramiro" }, share: true }', conf)
        self.assertEqual(conf.count("share: true"), 6)
        self.assertEqual(conf.count("exports: ["), 3)
        # una sola persona: nada que importar
        self.assertNotIn("imports", cuentas.configuracion({"ana": HASH}))

    def test_escribir_y_leer(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "bus"
            conf = cuentas.escribir(base, {"ana": HASH, "pedro": HASH})
            self.assertEqual(cuentas.leer(base), {"ana": HASH, "pedro": HASH})
            self.assertEqual(stat.S_IMODE(conf.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(base.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((base / "personas" / "ana.hash").stat().st_mode), 0o600)
            cuentas.escribir(base, {"ana": HASH})  # quitar a una persona borra su hash
            self.assertEqual(cuentas.leer(base), {"ana": HASH})
            self.assertNotIn("pedro", conf.read_text())

    def test_leer_rechaza_lo_que_no_es_un_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "personas").mkdir()
            (Path(tmp) / "personas" / "ana.hash").write_text("secreto-en-claro\n")
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
