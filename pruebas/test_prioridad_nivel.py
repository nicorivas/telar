"""La prioridad de una tarea llega a su fila con sus cuatro niveles (P0…P3): la página la muestra y la cambia."""

from __future__ import annotations

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.proveedores.tareas import Prioridad, Tarea


class NivelEnLaFila(Prueba):
    def test_el_nivel_declarado_pasa_tal_cual(self):
        for n in range(4):
            t = Tarea(id="T1", texto="x", prioridad=Prioridad.ALTA if n < 2 else Prioridad.MEDIA, nivel=n)
            self.assertEqual(t.item().datos["nivel"], n)

    def test_sin_nivel_sale_de_la_prioridad(self):
        self.assertEqual(Tarea(id="T1", texto="x", prioridad=Prioridad.ALTA).item().datos["nivel"], 1)
        self.assertEqual(Tarea(id="T1", texto="x", prioridad=Prioridad.BAJA).item().datos["nivel"], 3)
        self.assertIsNone(Tarea(id="T1", texto="x").item().datos["nivel"])
