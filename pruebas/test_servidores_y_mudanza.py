"""Servidores agregados a mano en «máquinas» (telar.servidores) y llevar un hilo a otra máquina por el bus
(telar.mudanza)."""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import mudanza, servidores

FICHA = {"telar": "0.7.3", "servidor": "telar", "bus": "nats://100.66.75.117:4222", "administra": "nico",
         "aloja": True, "puerta": "https://telar.x.ts.net"}


class _ConCarpeta(Prueba):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        e = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.dir / "config")})
        e.start()
        self.addCleanup(e.stop)

    def tearDown(self):
        self._tmp.cleanup()
        super().tearDown()


class LosServidoresAgregados(_ConCarpeta):
    def pedir(self, respuestas):
        visto = []

        def p(url, timeout=8):
            visto.append(url)
            for fin, r in respuestas.items():
                if url.endswith(fin):
                    return r
            raise OSError("nadie")
        p.visto = visto
        return p

    def test_normalizar(self):
        self.assertEqual(servidores.normalizar("100.66.75.117"), "http://100.66.75.117:8780")
        self.assertEqual(servidores.normalizar(" telar "), "http://telar:8780")
        self.assertEqual(servidores.normalizar("https://telar.x.ts.net/maquinas"), "https://telar.x.ts.net")
        self.assertEqual(servidores.normalizar("http://telar:9000"), "http://telar:9000")
        for malo in ("", "ftp://x", "a b", "http://"):
            with self.assertRaises(servidores.ErrorDeServidores, msg=malo):
                servidores.normalizar(malo)

    def test_agregar_le_pregunta_quien_es_y_lo_anota(self):
        p = self.pedir({"/unirse/servidor": (200, FICHA)})
        s = servidores.agregar(None, "100.66.75.117", pedir=p)
        self.assertEqual(p.visto, ["http://100.66.75.117:8780/unirse/servidor"])
        self.assertEqual((s["nombre"], s["administra"], s["aloja"]), ("telar", "nico", True))
        eq = servidores.equipo_de(s["url"])
        self.assertEqual((eq.bus, eq.administra, eq.url_puerta), (FICHA["bus"], "nico", s["url"]))

    def test_lo_que_no_es_un_servidor_de_telar(self):
        for r, palabra in (((404, {"detail": "no"}), "no es la máquina del bus"), ((200, {"ok": True}), "no contestó como"),
                           ((403, {}), "no contestó como")):
            with self.assertRaisesRegex(servidores.ErrorDeServidores, palabra):
                servidores.agregar(None, "telar", pedir=self.pedir({"/unirse/servidor": r}))
        with self.assertRaisesRegex(servidores.ErrorDeServidores, "no contesta"):
            servidores.agregar(None, "telar", pedir=self.pedir({}))
        self.assertEqual(servidores.leer(), {})

    def test_en_que_va_cada_uno(self):
        p = self.pedir({"/unirse/servidor": (200, FICHA), "/unirse/abc": (200, {"estado": "pendiente"})})
        url = servidores.agregar(None, "telar", pedir=p)["url"]
        sin_bus = SimpleNamespace(bus=SimpleNamespace(url=""))
        self.assertEqual(servidores.lista(sin_bus, pedir=p)[0]["estado"], "sin-pedir")
        servidores.anotar_pedido(url, pedido="abc", persona="pablo", estado="pendiente")
        su_bus = SimpleNamespace(bus=SimpleNamespace(url=FICHA["bus"]))  # instalar ya escribió [bus]
        self.assertEqual(servidores.lista(su_bus, pedir=p, ahora=10**10)[0]["estado"], "pendiente")
        p2 = self.pedir({"/unirse/abc": (200, {"estado": "aprobado"})})
        self.assertEqual(servidores.lista(su_bus, pedir=p2, ahora=10**10 + servidores.CADA)[0]["estado"], "en-su-bus")
        otro = SimpleNamespace(bus=SimpleNamespace(url="nats://otro:4222"))
        self.assertEqual(servidores.lista(otro, pedir=p2, ahora=10**10)[0]["estado"], "otro-bus")

    def test_desde_otro_bus_no_se_pide_entrar(self):
        url = servidores.agregar(None, "telar", pedir=self.pedir({"/unirse/servidor": (200, FICHA)}))["url"]
        otro = SimpleNamespace(bus=SimpleNamespace(url="nats://otro:4222"), estado=str(self.dir))
        with self.assertRaisesRegex(servidores.ErrorDeServidores, "otro bus"):
            servidores.entrar(otro, url, "pablo")
        with self.assertRaises(servidores.ErrorDeServidores):
            servidores.entrar(otro, url, "Pablo Ferreiro")  # un nombre que no sirve en el bus


class LaMudanzaAlLlegar(_ConCarpeta):
    SID = "0f3c2a9e-1111-2222-3333-444455556666"

    def setUp(self):
        super().setUp()
        self.raiz = self.dir / "trabajo"
        (self.raiz / "repo").mkdir(parents=True)
        self.entrada = self.dir / "entrada"
        self.entrada.mkdir()
        self.casa = self.dir / "casa"
        self.conversacion = b'{"type":"user"}\n' * 50
        (self.entrada / f"{self.SID}.jsonl.gz").write_bytes(gzip.compress(self.conversacion))
        self.ctx = SimpleNamespace(config=SimpleNamespace(agente=SimpleNamespace(nombre="claude"), raiz=str(self.raiz)))
        self.estado = mock.Mock()
        self.mux = mock.Mock()
        self.tel = SimpleNamespace(mux=self.mux, viva=True, vivos=set(), estado=self.estado, aviso="")

    def llegar(self, **p):
        from telar import entrega
        from telar.agente import lanzar
        from telar.ordenes import _comun

        pedido = {"hilo": "Faro", "sesion": self.SID, "relativa": "repo", "archivo": f"/lo/que/sea/{self.SID}.jsonl.gz",
                  "bytes": len(self.conversacion), **p}
        lanz = SimpleNamespace(carpeta=self.raiz / "repo", comando=["claude", "--resume", self.SID], retoma=self.SID)
        with mock.patch.object(entrega, "carpeta_de_entrada", return_value=self.entrada), \
                mock.patch.object(_comun, "tejer", return_value=self.tel), \
                mock.patch.object(lanzar, "carpeta", side_effect=lambda c, h: h or Path(c.raiz)), \
                mock.patch.object(lanzar, "para_hilo", return_value=lanz), mock.patch.object(lanzar, "anotar"), \
                mock.patch.object(Path, "home", return_value=self.casa):
            return mudanza.llegar(self.ctx, pedido)

    def test_la_deja_donde_claude_la_busca_y_abre_el_hilo(self):
        r = self.llegar()
        self.assertTrue(r["ok"], r)
        ruta = Path(r["conversacion"])
        self.assertEqual(ruta.read_bytes(), self.conversacion)
        self.assertEqual(ruta.parent.parent, self.casa / ".claude" / "projects")
        self.assertTrue(ruta.parent.name.endswith("-trabajo-repo"))
        self.assertFalse((self.entrada / f"{self.SID}.jsonl.gz").exists())
        self.estado.vincular.assert_called_once_with("Faro", "repo")
        self.estado.anotar_sesion.assert_called_once_with("Faro", self.SID)
        self.mux.crear_tab.assert_called_once()

    def test_sin_su_carpeta_se_abre_en_la_raiz_y_lo_dice(self):
        r = self.llegar(relativa="otro-repo")
        self.assertTrue(r["ok"], r)
        self.assertIn("no existe aquí", r["aviso"])
        self.estado.vincular.assert_not_called()

    def test_un_hilo_sin_mensajes_se_abre_con_una_nueva(self):
        r = self.llegar(sesion="", archivo="", bytes=0)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["conversacion"], "")
        self.estado.anotar_sesion.assert_not_called()
        self.mux.crear_tab.assert_called_once()

    def test_lo_que_no_se_acepta(self):
        for cambio, palabra in (({"sesion": "../../x"}, "falta"), ({"archivo": "otra.txt"}, "carpeta de entrada"),
                                ({"bytes": 3}, "cortada")):
            with self.subTest(cambio):
                self.assertIn(palabra, self.llegar(**cambio)["error"])
        self.tel.vivos.add("Faro")
        self.assertIn("ya hay un hilo", self.llegar()["error"])
