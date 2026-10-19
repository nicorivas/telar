"""Lo que una máquina le entrega a otra por el bus: un aviso en pantalla y un archivo en su entrada."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import entrega


def _config(carpeta, **bus):
    return SimpleNamespace(bus=SimpleNamespace(entrada=str(carpeta), url="nats://x", maquina="telar", **bus),
                           puerta=SimpleNamespace(entrada=""))


class ElArchivo(Prueba):
    def test_nunca_escapa_ni_pisa(self):
        with tempfile.TemporaryDirectory() as d:
            c = _config(d)
            uno = entrega.guardar_archivo(c, "../../etc/passwd", b"x")
            dos = entrega.guardar_archivo(c, "../../etc/passwd", b"y")
            self.assertEqual((uno.parent, uno.name, dos.name), (Path(d), "passwd", "passwd-1"))
            self.assertEqual(entrega.nombre_de_archivo(".oculto"), "oculto")
            with self.assertRaises(entrega.ErrorDeEntrega):
                entrega.guardar_archivo(c, "grande.bin", b"0" * (entrega.MAX_ARCHIVO + 1))

    def test_lo_que_llega_por_el_bus(self):
        with tempfile.TemporaryDirectory() as d:
            c = _config(d)
            r = entrega.recibir_archivo(c, {"nombre": "nota.md", "datos": base64.b64encode(b"hola").decode()})
            self.assertTrue(r["ok"])
            self.assertEqual(Path(r["ruta"]).read_bytes(), b"hola")
            self.assertFalse(entrega.recibir_archivo(c, {"nombre": "x", "datos": "no es base64!"})["ok"])

    def test_mandar_uno_por_el_bus(self):
        from telar import bus as mod_bus
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "foto.png"
            f.write_bytes(b"png")
            with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "ruta": "/allá/foto.png"}) as pedir:
                self.assertEqual(entrega.archivo(_config(d), f, a="laptop"), {"ruta": "/allá/foto.png", "bytes": 3})
            self.assertEqual(pedir.call_args[0][1:3], ("laptop", "archivo"))
            self.assertEqual(base64.b64decode(pedir.call_args[0][3]["datos"]), b"png")


class ElAviso(Prueba):
    def test_a_las_otras_en_linea(self):
        from telar import bus as mod_bus
        from telar import espejo
        fotos = [{"nombre": "laptop", "en_linea": True}, {"nombre": "telar", "en_linea": True}, {"nombre": "vieja", "en_linea": False}]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(espejo, "leer_todos", return_value=fotos), \
                mock.patch.object(mod_bus, "pedir", return_value={"ok": True}) as pedir:
            self.assertEqual(entrega.aviso(_config(d), "terminó", titulo="telar"), {"laptop": ""})
        self.assertEqual(pedir.call_args[0][1:4], ("laptop", "aviso", {"titulo": "telar", "texto": "terminó"}))

    def test_un_aviso_vacio_no_se_muestra(self):
        self.assertFalse(entrega.recibir_aviso({"titulo": "x", "texto": "  "})["ok"])
