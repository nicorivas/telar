"""`telar imagen`: subir una imagen a la máquina remota y dar su ruta."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest import mock

import comun  # noqa: F401 (src/ en el camino)

from telar.ordenes import imagen


class Subir(unittest.TestCase):
    def test_manda_por_ssh_con_bash_lc_y_devuelve_la_ruta(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.png"
            f.write_bytes(b"\x89PNG")
            with mock.patch("subprocess.run", return_value=N(returncode=0, stdout="/home/ana/telar-entrada/a.png\n", stderr="")) as run:
                ruta, problema = imagen.subir(N(destino="ana@servidor"), f, "a.png")
        self.assertEqual((ruta, problema), ("/home/ana/telar-entrada/a.png", ""))
        orden = run.call_args.args[0]
        self.assertEqual(orden[:2], ["ssh", "-o"])
        self.assertIn("bash -lc", orden[-1])
        self.assertIn("telar-entrada", orden[-1])

    def test_error_de_ssh(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.png"
            f.write_bytes(b"x")
            with mock.patch("subprocess.run", return_value=N(returncode=255, stdout="", stderr="Permission denied")):
                self.assertEqual(imagen.subir(N(destino="x"), f, "a.png"), ("", "Permission denied"))

    def test_no_pisa_lo_que_ya_estaba(self):
        # el guion de verdad, con bash en esta máquina en vez de ssh, y un HOME de prueba
        import os
        import subprocess

        real = subprocess.run

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "origen"
            f.write_bytes(b"x")

            def aqui(argv, **kw):
                return real(["bash", "-c", argv[-1]], env={**os.environ, "HOME": d}, **kw)

            with mock.patch("subprocess.run", side_effect=aqui):
                rutas = [imagen.subir(N(destino="x"), f, "mi informe.tar.gz")[0] for _ in range(3)]
            self.assertEqual([Path(r).name for r in rutas], ["mi informe.tar.gz", "mi informe.tar-2.gz", "mi informe.tar-3.gz"])
            self.assertEqual(Path(rutas[1]).read_bytes(), b"x")

    def test_con_sufijo(self):
        self.assertEqual(imagen.con_sufijo("a.png", 2), "a-2.png")
        self.assertEqual(imagen.con_sufijo("LEEME", 3), "LEEME-3")


class Main(unittest.TestCase):
    def ctx(self, *nombres):
        return N(config=N(remotos=[N(nombre=n, destino=f"ana@{n}") for n in nombres]))

    def test_rechaza_lo_que_no_es_imagen(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "notas.txt"
            t.write_text("x")
            self.assertEqual(imagen.main([str(t)], self.ctx("telar")), 2)

    def test_sin_o_con_varios_remotos(self):
        self.assertEqual(imagen.main([], self.ctx()), 2)
        self.assertEqual(imagen.main([], self.ctx("a", "b")), 2)

    def test_archivo_sube_y_copia_la_ruta(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "mi captura.PNG"
            f.write_bytes(b"x")
            with mock.patch.object(imagen, "subir", return_value=("/h/telar-entrada/x.png", "")) as sube, \
                 mock.patch.object(imagen, "al_portapapeles", return_value=True) as copia:
                self.assertEqual(imagen.main([str(f)], self.ctx("telar")), 0)
        self.assertTrue(sube.call_args.args[2].startswith("mi-captura-"))
        self.assertTrue(sube.call_args.args[2].endswith(".png"))
        copia.assert_called_once_with("/h/telar-entrada/x.png")

    def test_pegar_sin_imagen_sale_con_1_sin_tocar_tmux(self):
        with mock.patch.object(imagen, "del_portapapeles", return_value="no hay imagen"), \
             mock.patch("subprocess.run") as run:
            self.assertEqual(imagen.main(["--pegar", "%3"], self.ctx("telar")), 1)
        run.assert_not_called()

    def test_pegar_con_imagen_escribe_la_ruta_en_el_panel(self):
        with mock.patch.object(imagen, "del_portapapeles", side_effect=lambda d: d.write_bytes(b"x") and "" or ""), \
             mock.patch.object(imagen, "subir", return_value=("/h/telar-entrada/a.png", "")), \
             mock.patch("subprocess.run", return_value=N(returncode=0)) as run:
            self.assertEqual(imagen.main(["--pegar", "%3"], self.ctx("telar")), 0)
        self.assertEqual(run.call_args.args[0], ["tmux", "send-keys", "-t", "%3", "-l", "/h/telar-entrada/a.png"])


if __name__ == "__main__":
    unittest.main()
