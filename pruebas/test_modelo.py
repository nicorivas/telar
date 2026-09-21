"""El modelo: que las piezas se armen solas y digan lo que prometen.

Son datos puros, así que hay poco que probar. Lo que sí importa: que no haya E/S
escondida (se arman sin tocar el disco) y que las propiedades derivadas no mientan.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import modelo as m
from telar.mux import Multiplexor
from telar.proveedores import Fuente
from telar.agente import Agente


class Piezas(Prueba):
    def test_un_hilo_se_arma_con_un_nombre_y_nada_mas(self):
        h = m.Hilo(id="3", nombre="faro")
        self.assertFalse(h.vinculado)
        self.assertFalse(h.activo)
        self.assertIs(h.atencion, m.Atencion.NINGUNA)
        self.assertIsNone(h.prioridad)

    def test_un_hilo_con_carpeta_esta_vinculado(self):
        self.assertTrue(m.Hilo(id="3", nombre="faro", ruta=Path("proyectos/faro")).vinculado)

    def test_una_ficha_sin_nada_se_sabe_vacia(self):
        self.assertTrue(m.Ficha().vacia)
        self.assertFalse(m.Ficha(estado="parado desde la tormenta").vacia)

    def test_el_semaforo_serializa_como_texto(self):
        self.assertEqual(json.dumps({"a": m.Atencion.ESPERA}), '{"a": "espera"}')

    def test_la_prioridad_es_un_numero_ordenable(self):
        self.assertLess(m.Prioridad.ALTA, m.Prioridad.BAJA)

    def test_un_pendiente_puede_venir_de_un_proveedor_o_del_texto(self):
        del_texto = m.Pendiente(texto="Ajustar el giro", en_curso=True)
        de_afuera = m.Pendiente(texto="Firmar el anexo", id="T84", origen="tareas")
        self.assertEqual(del_texto.id, "")
        self.assertEqual(de_afuera.origen, "tareas")

    def test_los_hilos_son_inmutables(self):
        h = m.Hilo(id="3", nombre="faro")
        with self.assertRaises(Exception):
            h.nombre = "otro"  # type: ignore[misc]


class Fronteras(Prueba):
    """Los tres protocolos existen y se pueden comprobar en tiempo de ejecución."""

    def test_los_protocolos_son_comprobables(self):
        for protocolo in (Multiplexor, Fuente, Agente):
            self.assertFalse(isinstance(object(), protocolo))


if __name__ == "__main__":
    unittest.main()
