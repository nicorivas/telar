"""Lo que escribe `telar instalar` (telar.instalacion): el servicio de telar serve y el [bus]."""

from __future__ import annotations

import plistlib
import tempfile
import tomllib
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import instalacion


class LoQueEscribe(Prueba):
    def test_argumentos(self):
        self.assertEqual(instalacion.argumentos(), ["serve", "--web"])
        self.assertEqual(instalacion.argumentos(nodo=True, equipo=True), ["serve", "--equipo", "--nodo", "--web"])

    def test_path_sin_repetir_y_con_lo_basico(self):
        donde = {"telar": "/h/.local/bin/telar", "tmux": "/usr/bin/tmux", "claude": "/h/.local/bin/claude"}
        path = instalacion.ruta_path(donde.get).split(":")
        self.assertEqual(path[0], "/h/.local/bin")
        self.assertEqual((path.count("/h/.local/bin"), path.count("/usr/bin")), (1, 1))
        self.assertLessEqual({"/usr/local/bin", "/usr/bin", "/bin"}, set(path))

    def test_unidad_systemd(self):
        u = instalacion.unidad_systemd("/h/.local/bin/telar", ["serve", "--nodo", "--web"], "/h/.local/bin:/bin",
                                       esperar_tailscale=True)
        self.assertIn("ExecStart=/h/.local/bin/telar serve --nodo --web\n", u)
        self.assertIn("Environment=PATH=/h/.local/bin:/bin\n", u)
        self.assertIn("KillMode=process", u)
        self.assertIn("ExecStartPre=", u)
        sin = instalacion.unidad_systemd("/t", ["serve", "--web"], "/bin", esperar_tailscale=False)
        self.assertNotIn("ExecStartPre", sin)

    def test_plist_es_valido(self):
        texto = instalacion.plist_launchd("/Users/a b/telar", ["serve", "--web"], "/x:/bin", "/Users/a/l.log")
        d = plistlib.loads(texto.encode())
        self.assertEqual(d["Label"], instalacion.ETIQUETA)
        self.assertEqual(d["ProgramArguments"], ["/Users/a b/telar", "serve", "--web"])
        self.assertEqual(d["EnvironmentVariables"]["PATH"], "/x:/bin")
        self.assertIs(d["KeepAlive"], True)
        self.assertEqual(d["StandardOutPath"], "/Users/a/l.log")

    def test_bloque_bus_es_toml(self):
        base = 'raiz = "~/x"\n'
        datos = tomllib.loads(base + instalacion.bloque_bus("nats://100.1.2.3:4222", "~/.config/telar/bus.token", "ana"))
        self.assertEqual(datos["bus"], {"url": "nats://100.1.2.3:4222", "token": "~/.config/telar/bus.token", "persona": "ana"})
        self.assertNotIn("persona", tomllib.loads(instalacion.bloque_bus("nats://h:4222", "t"))["bus"])

    def test_escribir_si_cambia(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a" / "s.service"
            self.assertTrue(instalacion.escribir_si_cambia(f, "x\n"))
            self.assertFalse(instalacion.escribir_si_cambia(f, "x\n"))
            self.assertTrue(instalacion.escribir_si_cambia(f, "y\n"))
            self.assertEqual(f.read_text(), "y\n")


if __name__ == "__main__":
    unittest.main()
