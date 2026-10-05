"""Buscar un pendiente: el proveedor nombrado primero, y no preguntarles a todos si no hace falta."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import pendiente


class Buscar(Prueba):
    def correr(self, proveedor, filas_por=None):
        consultados = []
        filas_por = filas_por or {"tareas": [{"ref": "T7", "id": "T7"}], "calendario": [{"ref": "c1", "id": "c1"}]}

        def de_proveedores(ctx, tel, dia, solo=None):
            consultados.append(solo)
            return [f for n in (solo or filas_por) for f in filas_por.get(n, [])], []

        ctx = SimpleNamespace(config=SimpleNamespace(proveedores_activos=lambda: [SimpleNamespace(nombre="calendario"),
                                                                                   SimpleNamespace(nombre="tareas")]))
        with mock.patch.object(pendiente.orden_pendientes, "de_proveedores", side_effect=de_proveedores), \
                mock.patch.object(pendiente.orden_pendientes, "juntar", return_value=[]):
            fila = pendiente._buscar(ctx, SimpleNamespace(), "T7", proveedor=proveedor)
        return fila, consultados

    def test_con_proveedor_va_directo_y_no_pregunta_a_los_demas(self):
        fila, consultados = self.correr("tareas")
        self.assertEqual((fila["ref"], consultados), ("T7", [("tareas",)]))

    def test_sin_proveedor_pregunta_de_a_uno_y_para_al_encontrarlo(self):
        fila, consultados = self.correr("")
        self.assertEqual((fila["ref"], consultados), ("T7", [("calendario",), ("tareas",)]))
