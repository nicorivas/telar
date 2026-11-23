"""Los hilos hijos de un agente (telar.hijos): su nombre, y que una tarea sin proyecto abra uno."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import hijos


class ElNombre(Prueba):
    def test_agente_ref_y_titulo_corto(self):
        self.assertEqual(hijos.nombre("Secretaría", "T454", "Hacer el informe Faro"), "Secretaría › T454 Hacer el informe Faro")
        largo = hijos.nombre("Secretaría", "T454", "T454: Hacer el informe Faro trimestral con las notas de Carla")
        self.assertTrue(largo.startswith("Secretaría › T454 Hacer el informe Faro") and largo.endswith("…"), largo)
        self.assertLessEqual(len(largo), len("Secretaría › T454 ") + 29)
        self.assertEqual(hijos.nombre("Secretaría", "T1", ""), "Secretaría › T1")
        self.assertTrue(hijos.de("Secretaría", "Secretaría › T1"))
        self.assertFalse(hijos.de("Secretaría", "Secretaría"))


class SinProyecto(Prueba):
    def test_una_tarea_sin_proyecto_abre_un_hijo_del_agente(self):
        from telar.ordenes import pendiente

        general = SimpleNamespace(nombre="Secretaría", clave="secretaria")
        tel = SimpleNamespace(mux=object(), hilos=[], vivo=lambda h: False)
        ctx = SimpleNamespace(config=SimpleNamespace(agente=SimpleNamespace(pendiente="Veamos {ref}", pendiente_nuevo="/tarea {ref}")))
        fila = {"ref": "T454", "texto": "Hacer el informe Faro", "proveedor": "tareas"}
        with mock.patch.object(pendiente._comun, "tejer", return_value=tel), \
                mock.patch.object(pendiente, "_destino", return_value=None), \
                mock.patch.object(pendiente, "_destino_remoto", return_value=None), \
                mock.patch.object(pendiente, "_agente_general", return_value=general), \
                mock.patch.object(pendiente, "_con_direccion", side_effect=lambda c, f: f), \
                mock.patch.object(hijos, "abrir", return_value={"hilo": "Secretaría › T454 Hacer el informe Faro", "nuevo": True, "maquina": "telar"}) as abrir:
            datos, linea = pendiente.llevar(ctx, "T454", texto="/tarea T454", enviar=True, fila=fila)
        abrir.assert_called_once_with(ctx, general, "T454", "Hacer el informe Faro", "/tarea T454")
        self.assertEqual((datos["destino"], datos["maquina"], datos["hijo_de"]), ("Secretaría › T454 Hacer el informe Faro", "telar", "Secretaría"))
        self.assertIn("hijo de Secretaría", linea)
