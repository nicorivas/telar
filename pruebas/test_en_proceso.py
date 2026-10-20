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
    def test_llevar_no_pasa_por_el_puente(self):
        """`hilo llevar` tarda minutos: tiene su ruta (telar.servicios.llevar), que lo corre aparte."""
        from telar import api

        self.assertNotIn("llevar", api.VERBOS_HILO)
        rutas = {r.path for r in api.app.routes}
        self.assertIn("/hilo/llevar", rutas)
        # antes que /hilo/{verbo}, que si no la tomaría
        orden = [r.path for r in api.app.routes]
        self.assertLess(orden.index("/hilo/llevar"), orden.index("/hilo/{verbo}"))


class Llevar(Prueba):
    """`telar.servicios.llevar`: aparte, y si no termina pronto, sigue solo."""

    def setUp(self):
        super().setUp()
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctx = SimpleNamespace(config=SimpleNamespace(estado=self.tmp.name))

    def proceso(self, codigo, texto=""):
        """Un proceso de mentira: escribe `texto` en su registro y termina con `codigo` (None: sigue)."""
        def popen(argv, stdout=None, **_):
            stdout.write(texto)
            stdout.flush()
            self.argv = argv
            return SimpleNamespace(poll=lambda: codigo, returncode=codigo)
        return mock.patch("telar.servicios.llevar.subprocess.Popen", side_effect=popen)

    def test_lo_que_termina_pronto_se_devuelve(self):
        from telar.servicios import llevar

        with self.proceso(0, "«faro» sigue en telar\n"):
            r = llevar.llevar(self.ctx, "faro", "telar", si=True)
        self.assertEqual((r.codigo, r.en_curso), (0, False))
        self.assertEqual(self.argv[-5:], ["llevar", "telar", "--hilo", "faro", "--si"])

    def test_una_queja_es_un_409_con_su_linea(self):
        from telar.servicios import llevar

        with self.proceso(2, "· proyectos/faro: 3 sin subir\ntelar: hay trabajo sin subir; --si para llevarla igual\n"):
            with self.assertRaises(ErrorDeServicio) as e:
                llevar.llevar(self.ctx, "faro", "telar")
        self.assertEqual(e.exception.codigo, 409)
        self.assertEqual(str(e.exception), "hay trabajo sin subir; --si para llevarla igual")

    def test_la_queja_es_la_linea_de_telar_aunque_no_sea_la_ultima(self):
        from telar.servicios import llevar

        with self.proceso(2, "telar: no hay ningún hilo que se llame «x»\n(«x» no estaba en la lista)\n"):
            with self.assertRaises(ErrorDeServicio) as e:
                llevar.llevar(self.ctx, "x", "telar")
        self.assertEqual(str(e.exception), "no hay ningún hilo que se llame «x»")

    def test_lo_que_tarda_sigue_solo(self):
        from telar.servicios import llevar

        with self.proceso(None, "copiando…\n"):
            r = llevar.llevar(self.ctx, "faro", "telar", espera=0.01)
        self.assertTrue(r.en_curso)
        self.assertTrue(r.registro.endswith("faro.log"))


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


@unittest.skipIf(not HAY_FASTAPI, "sin fastapi (el extra «serve»)")
class LaReunion(Prueba):
    """`POST /reunion`: `telar reunion … --json` por el puente, y su JSON tal cual."""

    def test_arma_la_orden_y_devuelve_su_json(self):
        from fastapi.testclient import TestClient

        from telar import api
        salida = '{"hilo": "◷ 12:00 Comité", "proyecto": "comite", "mensaje": "…", "hecho": "abierto"}\n'
        corrida = en_proceso.Corrida(codigo=0, salida=salida)
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()), \
                mock.patch.object(api.en_proceso, "correr", return_value=corrida) as correr:
            r = TestClient(api.app).post("/reunion", json={"titulo": "Comité", "hora": "12:00",
                                                           "asistentes": ["Ana <a@x.cl>"], "preguntar": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["hecho"], "abierto")
        _, orden, argv = correr.call_args.args
        self.assertEqual(orden, "reunion")
        self.assertEqual(argv, ["Comité", "12:00", "--asistentes", "Ana <a@x.cl>", "--preguntar", "--json"])
