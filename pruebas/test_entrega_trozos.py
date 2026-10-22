import os, sys, tempfile, unittest, base64, uuid
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from telar import entrega


class Trozos(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = SimpleNamespace(bus=SimpleNamespace(entrada=self.d), puerta=SimpleNamespace(entrada=""))

    def enviar(self, datos, ident=None, saltar=()):
        t = entrega.MAX_ARCHIVO
        partes = [datos[i:i + t] for i in range(0, len(datos), t)]
        ident = ident or uuid.uuid4().hex
        r = {}
        for n, x in enumerate(partes):
            if n in saltar:
                continue
            r = entrega.recibir_archivo(self.cfg, {"nombre": "g.bin", "id": ident, "parte": n, "total": len(partes),
                                                   "datos": base64.b64encode(x).decode()})
        return r

    def test_junta_trozos(self):
        datos = os.urandom(entrega.MAX_ARCHIVO * 2 + 1000)
        r = self.enviar(datos)
        self.assertTrue(r["ok"])
        self.assertEqual(Path(r["ruta"]).read_bytes(), datos)

    def test_trozo_perdido(self):
        r = self.enviar(os.urandom(entrega.MAX_ARCHIVO * 3), saltar=(1,))
        self.assertFalse(r["ok"])

    def test_chico_sigue_igual(self):
        r = entrega.recibir_archivo(self.cfg, {"nombre": "a.png", "datos": base64.b64encode(b"hola").decode()})
        self.assertTrue(r["ok"])

    def test_id_malo(self):
        r = entrega.recibir_archivo(self.cfg, {"nombre": "a", "id": "../x", "parte": 0, "total": 2,
                                               "datos": base64.b64encode(b"x").decode()})
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
