"""La terminal de un hilo que no se pudo abrir: el motivo que va en el cierre (telar.terminal.motivo)."""

from __future__ import annotations

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import terminal


class ElMotivoDelCierre(Prueba):
    def test_la_ultima_linea_sin_colores_ni_telar(self):
        salida = "\x1b[1mtelar: no hay un hilo «◌ a solas 10/28 10:00»\x1b[0m\r\n"
        self.assertEqual(terminal.motivo(salida), "no hay un hilo «◌ a solas 10/28 10:00»")

    def test_cabe_en_el_cierre_de_un_websocket(self):
        self.assertLessEqual(len(terminal.motivo("é" * 300).encode("utf-8")), 123)
        self.assertEqual(terminal.motivo("\r\n  \r\n"), "no se pudo abrir")
