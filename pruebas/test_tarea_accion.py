"""`telar tarea --accion`: lo escrito llega al comando y, si la acción abre un hilo, a su primer prompt."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import tarea

ACCION = {"nombre": "escribirle", "pide": "qué le dices", "comando": ["todo", "nota", "T7", "a Claude: {texto}"],
          "mensaje": "/tarea T7 {texto}", "nombre_hilo": "T7 ↩"}


class LoEscritoLlegaAlHilo(Prueba):
    def correr(self, accion, *argv):
        corrido, abierto = [], []
        with mock.patch.object(tarea, "detalle_de", return_value=(("x",), "")), \
                mock.patch.object(tarea, "correr", return_value=({"titulo": "T7", "acciones": [accion]}, "")), \
                mock.patch("subprocess.run", side_effect=lambda w, **k: corrido.append(w) or SimpleNamespace(returncode=0, stdout="", stderr="")), \
                mock.patch("telar.ordenes.atajo.abrir", side_effect=lambda ctx, n, m: abierto.append((n, m)) or ""), \
                redirect_stdout(io.StringIO()):
            codigo = tarea.main(["T7", "--accion", "0", *argv], SimpleNamespace())
        return codigo, corrido, abierto

    def test_el_texto_va_al_comando_y_al_mensaje(self):
        codigo, corrido, abierto = self.correr(ACCION, "--texto", "sí, pero con Ana")
        self.assertEqual(codigo, 0)
        self.assertEqual(corrido, [["todo", "nota", "T7", "a Claude: sí, pero con Ana"]])
        self.assertEqual(abierto, [("T7 ↩", "/tarea T7 sí, pero con Ana")])

    def test_sin_texto_no_corre_nada(self):
        accion = {**ACCION, "comando": ["todo", "ver", "T7"]}  # el {texto} solo en el mensaje
        codigo, corrido, abierto = self.correr(accion)
        self.assertNotEqual(codigo, 0)
        self.assertEqual((corrido, abierto), ([], []))
