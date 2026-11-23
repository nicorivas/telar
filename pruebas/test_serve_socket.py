"""`telar serve --socket <ruta>`: una ruta que no cabe en un socket Unix se dice en una línea, sin arrancar; a una
carpeta que ya estaba (/tmp) no se le cambian los permisos, y a una que crea, sí (solo para su dueño); y no borra un
archivo que no es un socket."""

import contextlib
import io
import os
import socket
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from comun import HAY_FASTAPI  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import serve  # noqa: E402


@unittest.skipUnless(HAY_FASTAPI, "sin el extra «serve»")
class ServeSocket(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="ts-"))
        self.addCleanup(self._limpiar)

    def _limpiar(self) -> None:
        os.chmod(self.dir, 0o700)
        for p in sorted(self.dir.rglob("*"), reverse=True):
            p.rmdir() if p.is_dir() and not p.is_symlink() else p.unlink()
        self.dir.rmdir()

    def _servir(self, *argv: str):
        corridas = []
        err, out = io.StringIO(), io.StringIO()
        with mock.patch.object(serve, "_correr", lambda uv, principal, otros, nodo=None: corridas.append(principal)), \
                mock.patch("telar.salida.recortar_registro"), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            codigo = serve.main(list(argv), mock.Mock())
        return codigo, corridas, err.getvalue()

    def test_ruta_demasiado_larga_una_linea_sin_arrancar(self):
        sock = self.dir / ("x" * 120) / "telar.sock"
        codigo, corridas, err = self._servir("--socket", str(sock))
        self.assertNotEqual(codigo, 0)
        self.assertEqual(corridas, [], "no arranca")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("demasiado larga", err)
        self.assertIn("usa una más corta", err)
        self.assertNotIn("Traceback", err)
        self.assertFalse(sock.parent.exists(), "no crea la carpeta")

    def test_la_ruta_mas_larga_que_cabe_se_puede_abrir(self):
        # lo que `_demasiado_largo` deja pasar, el sistema lo abre; uno más, no
        base = str(self.dir) + "/"
        cabe = Path(base + "x" * (serve._largo_maximo() - len(base)))
        self.assertEqual(serve._demasiado_largo(cabe), "")
        s = socket.socket(socket.AF_UNIX)
        try:
            s.bind(str(cabe))
        finally:
            s.close()
        self.assertTrue(cabe.is_socket())
        no_cabe = Path(str(cabe) + "y")
        self.assertIn("demasiado larga", serve._demasiado_largo(no_cabe))
        with self.assertRaises(OSError), socket.socket(socket.AF_UNIX) as s2:
            s2.bind(str(no_cabe))

    def test_web_socket_demasiado_largo(self):
        codigo, corridas, err = self._servir("--puerto", "8771", "--web-socket", str(self.dir / ("y" * 120) / "web.sock"))
        self.assertNotEqual(codigo, 0)
        self.assertEqual(corridas, [])
        self.assertIn("--web-socket", err)
        self.assertIn("demasiado larga", err)

    def test_carpeta_que_ya_estaba_no_se_le_cambian_los_permisos(self):
        # como /tmp: ya estaba y otros entran. Arranca, sin tocarla, y avisa
        os.chmod(self.dir, 0o755)
        sock = self.dir / "telar.sock"
        codigo, corridas, err = self._servir("--socket", str(sock))
        self.assertEqual(codigo, 0)
        self.assertEqual([c.uds for c in corridas], [str(sock)])
        self.assertEqual(stat.S_IMODE(self.dir.stat().st_mode), 0o755)
        self.assertIn("otros usuarios", err)

    def test_carpeta_propia_cerrada_no_avisa(self):
        os.chmod(self.dir, 0o700)
        codigo, corridas, err = self._servir("--socket", str(self.dir / "telar.sock"))
        self.assertEqual(codigo, 0)
        self.assertEqual(len(corridas), 1)
        self.assertEqual(err, "")

    def test_carpeta_que_crea_queda_solo_para_su_dueno(self):
        sock = self.dir / "nueva" / "telar.sock"
        codigo, corridas, err = self._servir("--socket", str(sock))
        self.assertEqual(codigo, 0)
        self.assertEqual(len(corridas), 1)
        self.assertEqual(stat.S_IMODE(sock.parent.stat().st_mode), 0o700)
        self.assertEqual(err, "")

    def test_socket_que_quedo_se_reemplaza(self):
        sock = self.dir / "telar.sock"
        with socket.socket(socket.AF_UNIX) as s:
            s.bind(str(sock))
        codigo, corridas, _ = self._servir("--socket", str(sock))
        self.assertEqual(codigo, 0)
        self.assertEqual(len(corridas), 1)
        self.assertFalse(sock.exists(), "el que quedó de una vuelta anterior se borra (uvicorn abre el suyo)")

    def test_archivo_que_no_es_socket_no_se_borra(self):
        nota = self.dir / "notas.txt"
        nota.write_text("lo mío")
        codigo, corridas, err = self._servir("--socket", str(nota))
        self.assertNotEqual(codigo, 0)
        self.assertEqual(corridas, [])
        self.assertEqual(nota.read_text(), "lo mío")
        self.assertIn("no es un socket", err)


if __name__ == "__main__":
    unittest.main()
