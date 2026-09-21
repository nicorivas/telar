"""La salida en una terminal que no habla UTF-8.

Lo que se prueba no es la belleza del reemplazo sino que la orden siga viva: un
`PYTHONIOENCODING=ascii` heredado de un wrapper no puede matar a `telar doctor`
con una traza de Python. Y que el `--json`, en ese mismo caso, no se degrade:
escapado sí, transliterado no.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cli, salida


class Empobrecer(Prueba):
    def test_los_simbolos_con_que_telar_dibuja_tienen_reserva(self):
        for simbolo in "·✓✗☐▣●○«»—…→":
            reserva = salida.empobrecer(simbolo)
            self.assertTrue(reserva.isascii(), simbolo)
            self.assertNotEqual(reserva, "?", simbolo)

    def test_los_acentos_se_caen_y_la_palabra_se_lee(self):
        self.assertEqual(salida.empobrecer("configuración"), "configuracion")
        self.assertEqual(salida.empobrecer("señal"), "senal")

    def test_lo_que_no_tiene_reserva_ni_acento_no_se_pierde_en_silencio(self):
        self.assertEqual(salida.empobrecer("🧵"), "?")

    def test_alcanza_mira_la_codificacion_del_flujo(self):
        ascii_ = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        utf8 = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        self.assertFalse(salida.alcanza("«así»", ascii_))
        self.assertTrue(salida.alcanza("«así»", utf8))
        # en memoria no hay bytes todavía: alcanza para todo
        self.assertTrue(salida.alcanza("«así»", io.StringIO()))


class Terminal(Prueba):
    """Una salida de verdad —con bytes y con codificación— que no es UTF-8."""

    def flujo(self, codificacion: str) -> io.TextIOWrapper:
        crudo = io.BytesIO()
        texto = io.TextIOWrapper(crudo, encoding=codificacion, newline="")
        self.addCleanup(texto.detach)
        return texto

    def test_imprimir_los_simbolos_no_revienta(self):
        for codificacion in ("ascii", "latin-1", "cp1252"):
            with self.subTest(codificacion=codificacion):
                flujo = self.flujo(codificacion)
                salida.preparar(flujo)
                print("  · ✓ ✗ ☐ ▣ ● ○ «así» → …", file=flujo)
                flujo.flush()
                self.assertIn("+", flujo.buffer.getvalue().decode(codificacion))

    def test_sin_preparar_el_mismo_print_se_cae(self):
        # la prueba de que el arreglo es el que arregla, y no otra cosa
        flujo = self.flujo("ascii")
        with self.assertRaises(UnicodeEncodeError):
            print("·", file=flujo)
            flujo.flush()

    def test_preparar_no_se_queja_de_un_flujo_que_no_se_puede_reconfigurar(self):
        salida.preparar(io.StringIO())  # no lanza y no hace nada


class OrdenEnTerminalPobre(Prueba):
    """Las órdenes que dibujan, contra el workspace de ejemplo y sin multiplexor."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["TELAR_ESTADO"] = str(Path(self.tmp.name) / "estado")
        os.environ["TELAR_RAIZ"] = str(EJEMPLO)
        os.environ["TELAR_SESION"] = f"telar-pruebas-{uuid.uuid4().hex[:8]}"

    def correr(self, *argv: str, codificacion: str = "ascii") -> tuple[int, str]:
        crudo = io.BytesIO()
        flujo = io.TextIOWrapper(crudo, encoding=codificacion, newline="")
        with contextlib.redirect_stdout(flujo), contextlib.redirect_stderr(flujo):
            codigo = cli.main(list(argv))
            flujo.flush()
        return codigo, crudo.getvalue().decode(codificacion)

    def test_pendientes_dibuja_en_ascii(self):
        codigo, texto = self.correr("pendientes", "--repo")
        self.assertEqual(codigo, 0)
        self.assertTrue(texto.isascii())
        self.assertIn("pendientes", texto)

    def test_doctor_dibuja_en_ascii(self):
        codigo, texto = self.correr("doctor")
        self.assertTrue(texto.isascii())
        self.assertIn("fallas", texto)
        self.assertIn(codigo, (0, 1))

    def test_la_ayuda_tambien(self):
        codigo, texto = self.correr("--help")
        self.assertEqual(codigo, 0)
        self.assertTrue(texto.isascii())
        self.assertIn("Ordenes", texto)  # «Órdenes», sin la tilde

    def test_el_json_se_escapa_en_vez_de_transliterarse(self):
        codigo, texto = self.correr("pendientes", "--json", "--repo")
        self.assertEqual(codigo, 0)
        self.assertTrue(texto.isascii())
        datos = json.loads(texto)
        # el texto que llega al consumidor es el del documento, intacto
        textos = [p["texto"] for p in datos["pendientes"]]
        self.assertTrue(any(not t.isascii() for t in textos), textos)

    def test_en_utf8_el_json_va_con_sus_caracteres(self):
        _, texto = self.correr("pendientes", "--json", "--repo", codificacion="utf-8")
        self.assertNotIn("\\u", texto)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
