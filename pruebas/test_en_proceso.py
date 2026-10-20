"""El puente: una orden que todavía imprime, corrida en el proceso de la API con su salida capturada."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar.servicios import ErrorDeServicio
from telar.servicios import en_proceso


class ElPuente(Prueba):
    def test_captura_la_salida_y_la_queja_y_el_codigo(self):
        sin_mux = SimpleNamespace(mux=None, aviso="no hay multiplexor con el que hablar")
        with mock.patch("telar.ordenes._comun.tejer", return_value=sin_mux):
            c = en_proceso.correr(SimpleNamespace(config=SimpleNamespace()), "tejer", [])
        self.assertNotEqual(c.codigo, 0)
        self.assertIn("no hay multiplexor", c.error)
        with self.assertRaises(ErrorDeServicio) as e:
            en_proceso.o_falla(c, "telar tejer")
        self.assertEqual((str(e.exception), e.exception.codigo), ("no hay multiplexor con el que hablar", 409))

    def test_un_argumento_que_no_calza_no_tumba_el_proceso(self):
        c = en_proceso.correr(SimpleNamespace(config=SimpleNamespace()), "hilo", ["volar"])
        self.assertEqual(c.codigo, 2)

    def test_solo_las_ordenes_de_la_lista(self):
        with self.assertRaises(ErrorDeServicio):
            en_proceso.correr(SimpleNamespace(), "encargar", ["x"])

    @unittest.skipIf(not HAY_FASTAPI, "sin fastapi (el extra «serve»)")
    def test_la_ruta_no_deja_pedir_llevar(self):
        from fastapi.testclient import TestClient

        from telar import api
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            r = TestClient(api.app).post("/hilo/llevar", json={"hilo": "faro", "valor": "telar"})
        self.assertEqual(r.status_code, 422)


class LosPeriodicos(Prueba):
    """Por el bus a la máquina donde viven, o aquí por el puente; `correr` no se pide por la API."""

    def _ctx(self, en=""):
        return SimpleNamespace(config=SimpleNamespace(periodicos_en=en, bus=SimpleNamespace(url="nats://x", maquina="laptop")))

    def test_alla_por_el_bus_sin_su_en(self):
        from telar import bus as mod_bus
        from telar.servicios import periodicos
        r = {"ok": True, "codigo": 0, "salida": '{"procesos": []}\n', "error_salida": ""}
        with mock.patch.object(mod_bus, "pedir", return_value=r) as pedir:
            self.assertEqual(periodicos.orden(self._ctx("telar"), ["ver"]).model_dump(), {"procesos": []})
        self.assertEqual(pedir.call_args[0][1:3], ("telar", "periodicos"))
        self.assertEqual(pedir.call_args[0][3]["argv"], ["ver", "--json", "--en", "aqui"])
        with mock.patch.object(mod_bus, "pedir", return_value={**r, "codigo": 2, "salida": "", "error_salida": "telar: no hay «x»\n"}):
            with self.assertRaises(ErrorDeServicio) as e:
                periodicos.orden(self._ctx("telar"), ["log", "x"])
        self.assertEqual((str(e.exception), e.exception.codigo), ("no hay «x»", 409))

    def test_aqui_por_el_puente_y_correr_no(self):
        from telar.servicios import periodicos
        corrida = en_proceso.Corrida(codigo=0, salida='{"ok": true, "hecho": "x: pausado"}\n')
        with mock.patch.object(en_proceso, "correr", return_value=corrida) as correr:
            self.assertEqual(periodicos.orden(self._ctx(), ["pausar", "x"]).model_dump()["hecho"], "x: pausado")
        self.assertEqual(correr.call_args[0][1:], ("periodicos", ["pausar", "x", "--json", "--en", "aqui"]))
        with self.assertRaises(ErrorDeServicio):
            periodicos.orden(self._ctx(), ["correr", "x"])
