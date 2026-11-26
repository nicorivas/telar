"""Un `telar serve` vivo y sordo (26-nov-2026): desplegado en el laptop, la página contestó, y a los 8 s ya no escuchaba
en su puerto, con el proceso vivo y sin una línea en el registro. El nodo del bus se cayó al preparar el bus (un corte
justo después de conectar: `ConnectionResetError`, y los pedidos de JetStream sin respuesta); al caerse uno, `telar serve`
apaga los demás, y el servidor de la página, que ya había dejado de escuchar, esperaba para siempre a que la página
cerrara sus eventos (`/eventos`), que no se cierran nunca. Lo que no tiene que volver: que un pedazo caído deje el
proceso vivo, que se caiga sin decirlo, y que el nodo se caiga por un corte del bus al arrancar."""

from __future__ import annotations

import asyncio
import contextlib
import http.client
import io
import socket
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.ordenes import serve

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    from telar import api_web
except ImportError:  # sin el extra «serve»
    uvicorn = None


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _escucha(puerto: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


class _NodoQueSeCae:
    def __init__(self, error: BaseException | None):
        self.error = error

    async def correr(self):
        await asyncio.sleep(0.6)
        if self.error is not None:
            raise self.error


def _sin_guardia():
    """La guardia de `_correr` sale del proceso a los PLAZO_SALIR s de una caída: en una prueba, se la cancela."""
    if serve.guardia is not None:
        serve.guardia.cancel()
        serve.guardia = None


class UnPedazoQueSeCae(Prueba):
    """Con un servidor de verdad (uvicorn) que sirve los eventos de la página, y una página conectada a ellos."""

    def setUp(self):
        super().setUp()
        if uvicorn is None:
            self.skipTest("sin el extra «serve»")
        estado = Path(tempfile.mkdtemp())
        app = FastAPI()

        @app.get("/eventos")
        def eventos():
            return StreamingResponse(api_web._eventos(SimpleNamespace(estado=str(estado))), media_type="text/event-stream")

        self.puerto = _puerto_libre()
        self.config = uvicorn.Config(app, host="127.0.0.1", port=self.puerto, log_level="warning")
        self.eventos_terminaron = threading.Event()

    def _pagina_conectada(self):
        """Una página con sus eventos abiertos, como la que había conectada el 26-nov."""
        def leer():
            for _ in range(50):
                if _escucha(self.puerto):
                    break
                time.sleep(0.05)
            c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=30)
            c.request("GET", "/eventos")
            r = c.getresponse()
            with contextlib.suppress(OSError, http.client.HTTPException):
                while r.readline():
                    pass
            self.eventos_terminaron.set()

        threading.Thread(target=leer, daemon=True).start()

    def correr(self, nodo):
        self._pagina_conectada()
        err = io.StringIO()
        salidas = []
        inicio = time.monotonic()
        self.addCleanup(_sin_guardia)
        with mock.patch("sys.stderr", err), mock.patch.object(serve, "_salir", salidas.append):
            codigo = serve._correr(uvicorn, self.config, [], nodo)
        self.assertIsNotNone(serve.guardia)
        _sin_guardia()
        return codigo, err.getvalue(), time.monotonic() - inicio, salidas

    def test_el_nodo_que_se_cae_hace_salir_al_proceso_y_lo_dice(self):
        codigo, err, duro, salidas = self.correr(_NodoQueSeCae(TimeoutError("nats: timeout")))
        self.assertEqual(codigo, 1)
        self.assertIn("telar serve: el nodo del bus se cayó: TimeoutError: nats: timeout", err)
        self.assertIn("Traceback", err)
        self.assertIn("apago lo demás y salgo", err)
        self.assertFalse(_escucha(self.puerto))
        # los eventos de la página terminan solos: el servidor no tuvo que esperar su plazo ni cortarlos
        self.assertTrue(self.eventos_terminaron.wait(2))
        self.assertLess(duro, serve.PLAZO_APAGAR)
        self.assertNotIn("Exception in ASGI application", err)
        self.assertEqual(salidas, [])

    def test_uno_que_termina_sin_que_se_lo_pidan_tambien_es_una_caida(self):
        codigo, err, _, _ = self.correr(_NodoQueSeCae(None))
        self.assertEqual(codigo, 1)
        self.assertIn("el nodo del bus terminó sin que nadie se lo pidiera", err)

    def test_sin_eventos_que_terminen_solos_el_plazo_los_corta(self):
        """Una conexión que no termina nunca (un evento que no mira `APAGANDO`): el servidor espera su plazo y sale."""
        app = FastAPI()

        @app.get("/eventos")
        def eventos():
            async def para_siempre():
                while True:
                    yield ": latido\n\n"
                    await asyncio.sleep(0.2)
            return StreamingResponse(para_siempre(), media_type="text/event-stream")

        self.config = uvicorn.Config(app, host="127.0.0.1", port=self.puerto, log_level="critical")
        with mock.patch.object(serve, "PLAZO_APAGAR", 0.5):
            self.config.timeout_graceful_shutdown = None
            codigo, err, duro, salidas = self.correr(_NodoQueSeCae(TimeoutError("x")))
        self.assertEqual(codigo, 1)
        self.assertLess(duro, 5)
        self.assertFalse(_escucha(self.puerto))
        self.assertEqual(salidas, [])


class _ServidorSordo:
    """Un servidor que no se deja apagar: ni should_exit ni cancelarlo lo detienen, hasta que el proceso «sale»."""

    salio = False

    def __init__(self, config):
        self.config, self.should_exit, self.force_exit = config, False, False
        self._captured_signals = []

    async def serve(self):
        while not _ServidorSordo.salio:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.sleep(0.05)


class LaGuardia(Prueba):
    def test_si_no_alcanza_a_apagarse_sale_igual(self):
        _ServidorSordo.salio = False
        salidas = []

        def salir(codigo):
            salidas.append(codigo)
            _ServidorSordo.salio = True

        falso = SimpleNamespace(Server=_ServidorSordo)
        self.addCleanup(_sin_guardia)
        err = io.StringIO()
        with mock.patch.object(serve, "PLAZO_APAGAR", 0.1), mock.patch.object(serve, "PLAZO_SALIR", 0.4), \
                mock.patch.object(serve, "_salir", salir), mock.patch("sys.stderr", err):
            codigo = serve._correr(falso, SimpleNamespace(uds="/tmp/x.sock", timeout_graceful_shutdown=None), [],
                                   _NodoQueSeCae(RuntimeError("roto")))
        self.assertEqual(salidas, [1])
        self.assertEqual(codigo, 1)
        self.assertIn("no alcanzó a apagarse en 0.4 s: sale igual", err.getvalue())


class _ServidorConSenal:
    """Uno al que le llegó la señal de apagarse (lo que hace launchd o systemd al reiniciar): no es una caída."""

    def __init__(self, config):
        self.config, self.should_exit, self.force_exit = config, False, False
        self._captured_signals = []

    async def serve(self):
        await asyncio.sleep(0.1)
        self._captured_signals.append(15)


class ApagarPorUnaSenal(Prueba):
    def test_no_es_una_caida(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            codigo = serve._correr(SimpleNamespace(Server=_ServidorConSenal),
                                   SimpleNamespace(uds="/tmp/x.sock", timeout_graceful_shutdown=None), [])
        self.assertEqual(codigo, 0)
        self.assertEqual(err.getvalue(), "")


class ElNodoAlPrepararElBus(Prueba):
    """El corte del bus justo después de conectar: los pedidos de JetStream no vuelven. El nodo del servicio lo intenta
    de nuevo; el de una vez (`telar nodo --una-vez`) falla."""

    def setUp(self):
        super().setUp()
        from telar import bus as mod_bus
        from telar.ordenes import nodo as mod_nodo

        self.bus = mod_bus
        self.nodo = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        self.lineas = []
        self.nodo.anotar = self.lineas.append
        js = mock.Mock()
        js.key_value = mock.AsyncMock(side_effect=lambda nombre: f"kv:{nombre}")
        self.nc = mock.Mock(jetstream=mock.Mock(return_value=js), close=mock.AsyncMock())
        self.fallas = [ConnectionResetError(54, "Connection reset by peer"), TimeoutError("nats: timeout")]

        async def asegurar(_js):
            if self.fallas:
                raise self.fallas.pop(0)

        for parche in (mock.patch.object(mod_bus, "asegurar", asegurar),
                       mock.patch.object(mod_bus, "ESPERAS_PRIMERA", (0,))):
            parche.start()
            self.addCleanup(parche.stop)

    def test_el_del_servicio_lo_intenta_de_nuevo(self):
        js, kv, espejo = asyncio.run(self.nodo._preparar(self.nc))
        self.assertEqual((kv, espejo), (f"kv:{self.bus.ESTADO}", f"kv:{self.bus.ESPEJO}"))
        self.assertEqual(self.fallas, [])
        self.assertTrue(any("preparar el bus" in linea and "ConnectionResetError" in linea for linea in self.lineas))

    def test_el_de_una_vez_falla(self):
        with self.assertRaises(ConnectionResetError):
            asyncio.run(self.nodo._preparar(self.nc, una_vez=True))

    def test_si_falla_cierra_la_conexion(self):
        self.nodo.config = mock.Mock()
        with mock.patch.object(self.bus, "conectar", mock.AsyncMock(return_value=self.nc)), \
                mock.patch.object(self.bus, "registrar_conexion") as registrar, self.assertRaises(ConnectionResetError):
            asyncio.run(self.nodo.correr(una_vez=True))
        self.nc.close.assert_awaited_once()
        self.assertEqual(registrar.call_args_list[-1], mock.call(None, None))


class ElProcesoAparte(Prueba):
    def test_al_apagar_se_termina_aunque_este_calculando(self):
        """Si no, Python, al salir, espera a que termine lo que calcula: un servicio que no sale."""
        from telar import aparte

        proceso = mock.Mock()
        pool = mock.Mock(_processes={1: proceso})
        with mock.patch.object(aparte, "_pool", pool):
            aparte.apagar()
            self.assertIsNone(aparte._pool)
        pool.shutdown.assert_called_once_with(wait=False, cancel_futures=True)
        proceso.terminate.assert_called_once()

    def test_sale_solo_cuando_el_servicio_ya_no_esta(self):
        """Un servicio que se apaga por una señal, o muere de golpe, no alcanza a terminarlo: que no quede huérfano."""
        from telar import aparte

        salio = threading.Event()
        with mock.patch.object(aparte.os, "_exit", lambda codigo: salio.set()):
            aparte._seguir_al_servicio(aparte.os.getppid(), cada=0.05)
            self.assertFalse(salio.wait(0.3))
            aparte._seguir_al_servicio(-1, cada=0.05)  # uno que ya no es su padre
            self.assertTrue(salio.wait(2))
