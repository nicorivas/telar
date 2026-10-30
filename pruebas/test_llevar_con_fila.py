"""Llevar un pendiente con la fila que ya tiene quien pide: no se vuelve a buscar (foco, por el dashboard)."""

from __future__ import annotations

from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import pendiente
from telar.servicios import pendientes as servicio


class ConLaFila(Prueba):
    def correr(self, fila, **kw):
        with mock.patch.object(pendiente, "llevar", return_value=({"ref": "T84", "texto": "x", "destino": "Faro"}, "")) as llevar:
            servicio.llevar(object(), "T84", proveedor="tareas", fila=fila, **kw)
        return llevar.call_args.kwargs["fila"]

    def test_la_de_ese_pendiente_se_usa(self):
        fila = {"ref": "T84", "proveedor": "tareas", "texto": "Faro: la lámpara"}
        self.assertEqual(self.correr(fila), fila)

    def test_la_de_otro_no(self):
        self.assertIsNone(self.correr({"ref": "T85", "proveedor": "tareas"}))
        self.assertIsNone(self.correr({"ref": "T84", "proveedor": "calendario"}))
        self.assertIsNone(self.correr("no es una fila"))
