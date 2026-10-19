"""El puente: una orden que todavía imprime, corrida en el proceso de la API con su salida capturada."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

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

    def test_la_ruta_no_deja_pedir_llevar(self):
        from fastapi.testclient import TestClient

        from telar import api
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            r = TestClient(api.app).post("/hilo/llevar", json={"hilo": "faro", "valor": "telar"})
        self.assertEqual(r.status_code, 422)
