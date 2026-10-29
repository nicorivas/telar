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
        self.ctx = SimpleNamespace(config=SimpleNamespace(agente=SimpleNamespace(nombre="claude-code"), raiz=str(self.raiz)))
        self.estado = mock.Mock()
        self.estado.remotos.return_value = {}
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

    def test_de_vuelta_reemplaza_la_copia_de_cuando_se_fue(self):
        # el hilo se fue de aquí y vuelve: aquí quedó su conversación de entonces, y la que llega la continúa
        import re as _re
        carpeta = self.casa / ".claude" / "projects" / _re.sub(r"[^A-Za-z0-9]", "-", str((self.raiz / "repo").resolve()))
        carpeta.mkdir(parents=True)
        (carpeta / f"{self.SID}.jsonl").write_bytes(self.conversacion[:160])
        r = self.llegar()
        self.assertTrue(r["ok"], r)
        self.assertEqual((carpeta / f"{self.SID}.jsonl").read_bytes(), self.conversacion)
        self.assertEqual(list(carpeta.glob("*.bak")), [])

    def test_si_aqui_se_siguio_por_su_lado_queda_aparte(self):
        import re as _re
        carpeta = self.casa / ".claude" / "projects" / _re.sub(r"[^A-Za-z0-9]", "-", str((self.raiz / "repo").resolve()))
        carpeta.mkdir(parents=True)
        (carpeta / f"{self.SID}.jsonl").write_bytes(b'{"type":"otra"}\n')
        r = self.llegar()
        self.assertTrue(r["ok"], r)
        self.assertEqual((carpeta / f"{self.SID}.jsonl").read_bytes(), self.conversacion)
        aparte = list(carpeta.glob("*.bak"))
        self.assertEqual(len(aparte), 1)
        self.assertEqual(aparte[0].read_bytes(), b'{"type":"otra"}\n')
        self.assertIn("por su lado", r["aviso"])

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


class Traer(LaMudanzaAlLlegar):
    def test_el_dueno_corre_llevar_hacia_quien_pide(self):
        from types import SimpleNamespace as NS

        with mock.patch("subprocess.run", return_value=NS(returncode=0, stdout="«Faro» sigue en laptop", stderr="")) as run:
            r = mudanza.traer_aqui(self.ctx, {"hilo": "Faro", "a": "nicolss-macbook-air", "si": True})
        self.assertEqual((r["ok"], r["codigo"]), (True, 0))
        argv = run.call_args.args[0]
        self.assertEqual(argv[-6:], ["hilo", "llevar", "nicolss-macbook-air", "--hilo", "Faro", "--si"])

    def test_sin_sesion_la_levanta_y_el_hilo_es_el_primero(self):
        from telar.ordenes import _comun

        dormida = SimpleNamespace(mux=self.mux, viva=False, vivos=set(), estado=self.estado, aviso="")
        with mock.patch.object(_comun, "tejer", side_effect=[dormida, self.tel]):
            from telar import entrega
            from telar.agente import lanzar

            lanz = SimpleNamespace(carpeta=self.raiz, comando=["claude"], retoma=self.SID)
            with mock.patch.object(entrega, "carpeta_de_entrada", return_value=self.entrada), \
                    mock.patch.object(lanzar, "carpeta", side_effect=lambda c, h: h or Path(c.raiz)), \
                    mock.patch.object(lanzar, "para_hilo", return_value=lanz), mock.patch.object(lanzar, "anotar"), \
                    mock.patch.object(Path, "home", return_value=self.casa):
                r = mudanza.llegar(self.ctx, {"hilo": "Faro", "sesion": self.SID, "relativa": "repo",
                                              "archivo": f"{self.SID}.jsonl.gz", "bytes": len(self.conversacion)})
        self.assertTrue(r["ok"], r)
        self.mux.tejer.assert_called_once()

    def test_no_acepta_una_maquina_rara(self):
        for a in ("", "a b", "x;reboot", "-rf"):
            self.assertFalse(mudanza.traer_aqui(self.ctx, {"hilo": "Faro", "a": a})["ok"], a)

    def test_al_llegar_cierra_la_ventana_que_solo_lo_miraba(self):
        self.tel.vivos.add("Faro")
        self.estado.remotos.return_value = {"Faro": {"remoto": "telar", "sesion": "telar:3"}}
        self.mux.hilos.return_value = [SimpleNamespace(nombre="Faro", id="@7")]
        r = self.llegar()
        self.assertTrue(r["ok"], r)
        self.mux.cerrar.assert_called_once_with("@7")
        self.estado.olvidar_remoto.assert_called_once_with("Faro")


class LaRevisionAntesDeLlevar(LaMudanzaAlLlegar):
    """`hilo-revisar`: del lado que recibiría, lo que haría fallar la llegada (no se lleva) y lo que la dejaría a
    medias (se pregunta), sin mover nada."""

    def revisar(self, **p):
        from telar.ordenes import _comun

        pedido = {"hilo": "Faro", "sesion": self.SID, "relativa": "repo", **p}
        with mock.patch.object(_comun, "tejer", return_value=self.tel), \
                mock.patch("shutil.which", return_value="/usr/bin/claude"), \
                mock.patch.object(Path, "home", return_value=self.casa):
            return mudanza.revisar(self.ctx, pedido)

    def test_todo_en_orden(self):
        self.assertEqual(self.revisar(), {"ok": True, "graves": [], "avisos": []})

    def test_lo_grave(self):
        self.ctx.config.agente.nombre = ""
        self.assertIn("ninguno", self.revisar()["graves"][0])
        self.ctx.config.agente.nombre = "claude-code"
        self.tel.vivos.add("Faro")
        self.assertIn("ya hay un hilo", self.revisar()["graves"][0])
        self.tel.vivos.clear()
        # la conversación ya escrita aquí no es grave: es la copia de cuando se fue, y el hilo vuelve
        (self.casa / ".claude" / "projects" / "x").mkdir(parents=True)
        (self.casa / ".claude" / "projects" / "x" / f"{self.SID}.jsonl").write_text("{}")
        self.assertEqual(self.revisar()["graves"], [])

    def test_su_carpeta_sin_clonar_es_un_aviso(self):
        r = self.revisar(relativa="otro/repo")
        self.assertEqual(r["graves"], [])
        self.assertIn("clonar", r["avisos"][0])


class ElProgresoDeLaMudanza(_ConCarpeta):
    def test_cada_paso_se_suma_y_revisar_empieza_de_nuevo(self):
        config = SimpleNamespace(estado=str(self.dir / "estado"))
        mudanza.progreso(config, "Faro/uno", "revisar", maquina="telar", bytes=10)
        mudanza.progreso(config, "Faro/uno", "copiar")
        d = json.loads(mudanza.ruta_progreso(config, "Faro/uno").read_text())
        self.assertEqual((d["paso"], d["maquina"], d["bytes"], d["hilo"]), ("copiar", "telar", 10, "Faro/uno"))
        mudanza.progreso(config, "Faro/uno", "revisar", maquina="otra")
        self.assertNotIn("bytes", json.loads(mudanza.ruta_progreso(config, "Faro/uno").read_text()))


class LlevarPorElBus(_ConCarpeta):
    """Llevar un hilo a otra máquina: lo grave allá no mueve nada, y si allá no se abre, se vuelve a abrir aquí."""

    def llevar(self, revision, enviar):
        from telar import bus as mod_bus
        from telar.ordenes import _comun
        from telar.ordenes import hilo as orden

        self.ctx = SimpleNamespace(config=SimpleNamespace(estado=str(self.dir / "estado")))
        self.hilo = SimpleNamespace(nombre="Faro", id="@3")
        self.mux = mock.Mock()
        self.tel = mock.Mock(mux=self.mux)
        self.tel.vivo.return_value = True
        nuevo = SimpleNamespace(hilos=[SimpleNamespace(nombre="Faro")])
        archivo = self.dir / "c.jsonl"
        archivo.write_text("{}")
        with mock.patch.object(mod_bus, "pedir", side_effect=revision if callable(revision) else lambda *a, **k: revision), \
                mock.patch.object(mudanza, "enviar", side_effect=enviar), \
                mock.patch.object(_comun, "tejer", return_value=nuevo), \
                mock.patch.object(orden, "_retomar", return_value=0) as retomar, \
                mock.patch.object(_comun, "queja", side_effect=lambda t: (self.quejas.append(t), 1)[1]):
            self.quejas = []
            r = orden._llevar_por_el_bus(self.ctx, self.tel, self.hilo, "telar", "sid", archivo, "repo", si=True)
        self.retomar = retomar
        return r, json.loads(mudanza.ruta_progreso(self.ctx.config, "Faro").read_text())

    def test_lo_grave_no_mueve_nada(self):
        r, prog = self.llevar({"graves": ["sin claude"]}, enviar=AssertionError("no debía enviarse"))
        self.assertEqual(r, 1)
        self.mux.cerrar.assert_not_called()
        self.assertEqual(prog["paso"], "falla")
        self.assertIn("No se movió nada", prog["error"])

    def test_si_alla_no_se_abre_vuelve_aqui(self):
        r, prog = self.llevar({}, enviar=mudanza.ErrorDeMudanza("telar no abrió el hilo"))
        self.assertEqual(r, 1)
        self.mux.cerrar.assert_called_once_with("@3")
        self.retomar.assert_called_once()
        self.tel.estado.archivar.assert_not_called()
        self.assertIn("Se volvió a abrir aquí", prog["error"])

    def test_al_llegar_queda_archivado_aqui(self):
        r, prog = self.llevar({}, enviar=lambda *a, al_abrir=None, **k: (al_abrir(), {"carpeta": "/x"})[1])
        self.assertEqual(r, 0)
        self.tel.estado.archivar.assert_called_once_with("Faro")
        self.assertEqual((prog["paso"], prog["carpeta"], prog["maquina"]), ("listo", "/x", "telar"))
