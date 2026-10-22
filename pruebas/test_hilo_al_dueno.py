"""Un dueño por hilo, paso 1: los cambios a un hilo de otra máquina se le piden a su dueño por el bus."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import hilo as orden

CTX = SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="nats://x:4222", maquina="laptop", persona="ana")))


class QuienEsElDueno(Prueba):
    def test_aqui_o_sin_bus_no_hay_dueno_ajeno(self):
        self.assertEqual(orden._dueno(CTX, SimpleNamespace(remoto="", nombre="Faro")), "")
        self.assertEqual(orden._dueno(CTX, SimpleNamespace(remoto="?", nombre="Faro")), "")
        sin_bus = SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="", maquina="", persona="")))
        self.assertEqual(orden._dueno(sin_bus, SimpleNamespace(remoto="telar", nombre="Faro")), "")

    def test_lo_dice_el_estado_del_bus_y_si_no_el_remoto(self):
        h = SimpleNamespace(remoto="telar", nombre="Faro")
        with mock.patch("telar.bus.maquina_de", return_value="servidor"):
            self.assertEqual(orden._dueno(CTX, h), "servidor")
        with mock.patch("telar.bus.maquina_de", return_value=""):
            self.assertEqual(orden._dueno(CTX, h), "telar")
        with mock.patch("telar.bus.maquina_de", return_value="laptop"):  # se mudó aquí
            self.assertEqual(orden._dueno(CTX, h), "")


class PedirleAlDueno(Prueba):
    def pedir(self, respuesta, **o):
        opciones = SimpleNamespace(verbo="archivar", valor="", cerrar=True, json=False, **o)
        with mock.patch("telar.bus.pedir", return_value=respuesta) as pedir, redirect_stdout(io.StringIO()):
            problema = orden._al_dueno(CTX, "telar", opciones, "Faro")
        return problema, pedir.call_args

    def test_arma_la_orden_y_si_sale_bien_no_hay_problema(self):
        problema, llamada = self.pedir({"ok": True, "codigo": 0, "salida": "archivado «Faro»\n"})
        self.assertEqual(problema, "")
        self.assertEqual(llamada.args[1:3], ("telar", "hilo"))
        self.assertEqual(llamada.args[3], {"argv": ["archivar", "--hilo", "Faro", "--cerrar"]})

    def test_si_no_responde_o_falla_lo_dice(self):
        self.assertIn("no respondió", self.pedir({"ok": False, "error": "nats: timeout"})[0])
        problema, _ = self.pedir({"ok": True, "codigo": 2, "error_salida": "telar: no hay ningún hilo «Faro»\n"})
        self.assertEqual(problema, "en telar: no hay ningún hilo «Faro»")

    def test_el_nodo_solo_acepta_esos_verbos(self):
        self.assertNotIn("llevar", orden.AL_DUENO)
        self.assertNotIn("retomar", orden.AL_DUENO)
        self.assertTrue(set(orden.AL_DUENO) <= set(orden.VERBOS))


if __name__ == "__main__":
    unittest.main()


class Conciliar(Prueba):
    """Paso 2: las ventanas de los hilos de otras máquinas, contra su estado en el bus, en cada vuelta."""

    def nodo(self, vistos, ventanas, archivados=(), anotados=None):
        from telar.ordenes.nodo import Nodo

        n = Nodo.__new__(Nodo)
        n.ctx, n.vistos, n.tocadas = None, vistos, []
        vivas = {nombre for nombre in ventanas}
        tel = SimpleNamespace(
            mux=object(), viva=True,
            por_nombre=lambda nombre: SimpleNamespace(nombre=nombre) if nombre in ventanas else None,
            vivo=lambda h: h.nombre in vivas,
            estado=SimpleNamespace(remotos=lambda: anotados or {}, archivados=lambda: set(archivados)))
        n.ventana_de = lambda d: n.tocadas.append(d["nombre"])
        return n, tel

    def test_trae_lo_que_falta_y_cierra_lo_que_sobra(self):
        vistos = {"ana.faro": {"nombre": "Faro", "vivo": True, "maquina": "telar"},
                  "ana.viejo": {"nombre": "Viejo", "vivo": False, "maquina": "telar"},
                  "ana.al-dia": {"nombre": "Al día", "vivo": True, "maquina": "telar"},
                  "ana.guardado": {"nombre": "Guardado", "vivo": True, "maquina": "telar"}}
        n, tel = self.nodo(vistos, ventanas={"Viejo", "Al día"}, archivados={"Guardado"},
                           anotados={"Viejo": {"remoto": "telar"}})
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel):
            tocados = n.conciliar()
        self.assertEqual(sorted(tocados), ["Faro", "Viejo"])

    def test_una_ventana_que_no_es_de_ese_remoto_no_se_cierra(self):
        vistos = {"ana.faro": {"nombre": "Faro", "vivo": False, "maquina": "telar"}}
        n, tel = self.nodo(vistos, ventanas={"Faro"}, anotados={})
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel):
            self.assertEqual(n.conciliar(), [])
