"""Los hilos hijos de un agente (telar.hijos): su nombre, y que una tarea sin proyecto abra uno."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import hijos


class ElNombre(Prueba):
    def test_agente_ref_y_titulo_corto(self):
        self.assertEqual(hijos.nombre("Gestión", "T454", "Hacer el test Hogan"), "Gestión › T454 Hacer el test Hogan")
        largo = hijos.nombre("Gestión", "T454", "T454: Hacer el test Hogan Assessments con las instrucciones de Carolina")
        self.assertTrue(largo.startswith("Gestión › T454 Hacer el test Hogan") and largo.endswith("…"), largo)
        self.assertLessEqual(len(largo), len("Gestión › T454 ") + 29)
        self.assertEqual(hijos.nombre("Gestión", "T1", ""), "Gestión › T1")
        self.assertTrue(hijos.de("Gestión", "Gestión › T1"))
        self.assertFalse(hijos.de("Gestión", "Gestión"))


class SinProyecto(Prueba):
    def test_una_tarea_sin_proyecto_abre_un_hijo_del_agente(self):
        from telar.ordenes import pendiente

        general = SimpleNamespace(nombre="Gestión", clave="gestion")
        tel = SimpleNamespace(mux=object(), hilos=[], vivo=lambda h: False)
        ctx = SimpleNamespace(config=SimpleNamespace(agente=SimpleNamespace(pendiente="Veamos {ref}", pendiente_nuevo="/tarea {ref}")))
        fila = {"ref": "T454", "texto": "Hacer el test Hogan", "proveedor": "tareas"}
        with mock.patch.object(pendiente._comun, "tejer", return_value=tel), \
                mock.patch.object(pendiente, "_destino", return_value=None), \
                mock.patch.object(pendiente, "_destino_remoto", return_value=None), \
                mock.patch.object(pendiente, "_agente_general", return_value=general), \
                mock.patch.object(pendiente, "_con_direccion", side_effect=lambda c, f: f), \
                mock.patch.object(hijos, "abrir", return_value={"hilo": "Gestión › T454 Hacer el test Hogan", "nuevo": True, "maquina": "telar"}) as abrir:
            datos, linea = pendiente.llevar(ctx, "T454", texto="/tarea T454", enviar=True, fila=fila)
        abrir.assert_called_once_with(ctx, general, "T454", "Hacer el test Hogan", "/tarea T454")
        self.assertEqual((datos["destino"], datos["maquina"], datos["hijo_de"]), ("Gestión › T454 Hacer el test Hogan", "telar", "Gestión"))
        self.assertIn("hijo de Gestión", linea)
