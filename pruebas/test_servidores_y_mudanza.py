"""Servidores agregados a mano en «máquinas» (telar.servidores) y llevar un hilo a otra máquina por el bus
(telar.mudanza)."""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import mudanza, servidores

FICHA = {"telar": "0.7.3", "servidor": "telar", "bus": "nats://100.64.0.10:4222", "administra": "ana",
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
        self.assertEqual(servidores.normalizar("100.64.0.10"), "http://100.64.0.10:8780")
        self.assertEqual(servidores.normalizar(" telar "), "http://telar:8780")
        self.assertEqual(servidores.normalizar("https://telar.x.ts.net/maquinas"), "https://telar.x.ts.net")
        self.assertEqual(servidores.normalizar("http://telar:9000"), "http://telar:9000")
        for malo in ("", "ftp://x", "a b", "http://"):
            with self.assertRaises(servidores.ErrorDeServidores, msg=malo):
                servidores.normalizar(malo)

    def test_agregar_le_pregunta_quien_es_y_lo_anota(self):
        p = self.pedir({"/unirse/servidor": (200, FICHA)})
        s = servidores.agregar(None, "100.64.0.10", pedir=p)
        self.assertEqual(p.visto, ["http://100.64.0.10:8780/unirse/servidor"])
        self.assertEqual((s["nombre"], s["administra"], s["aloja"]), ("telar", "ana", True))
        eq = servidores.equipo_de(s["url"])
        self.assertEqual((eq.bus, eq.administra, eq.url_puerta), (FICHA["bus"], "ana", s["url"]))

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
        servidores.anotar_pedido(url, pedido="abc", persona="bruno", estado="pendiente")
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
            servidores.entrar(otro, url, "bruno")
        with self.assertRaises(servidores.ErrorDeServidores):
            servidores.entrar(otro, url, "Bruno Soto")  # un nombre que no sirve en el bus


class LaMudanzaAlLlegar(_ConCarpeta):
    """`hilo-llegar`: la conversación ya está donde Claude la busca (telar.replica); aquí se toma el hilo con la época
    que se le cedió (telar.dueno) y se abre. Si allá se echaron atrás, ni se toma ni se abre."""

    SID = "0f3c2a9e-1111-2222-3333-444455556666"
    CLAVE = "ana.faro"

    def setUp(self):
        super().setUp()
        from comun import KvDeMentira

        self.raiz = self.dir / "trabajo"
        (self.raiz / "repo").mkdir(parents=True)
        self.casa = self.dir / "casa"
        self.conversacion = b'{"type":"user"}\n' * 50
        self.ctx = SimpleNamespace(config=SimpleNamespace(agente=SimpleNamespace(nombre="claude-code"), raiz=str(self.raiz),
                                                          estado=str(self.dir / "estado"),
                                                          bus=SimpleNamespace(maquina="aqui", url="nats://x", persona="ana")))
        self.estado = mock.Mock()
        self.estado.remotos.return_value = {}
        self.mux = mock.Mock()
        self.tel = SimpleNamespace(mux=self.mux, viva=True, vivos=set(), estado=self.estado, aviso="")
        # allá lo cedieron a esta máquina, con la época 4
        self.kv = KvDeMentira({self.CLAVE: {"nombre": "Faro", "dueno": "laptop", "maquina": "laptop", "epoca": 4,
                                            "cede": "aqui", "mudanza": {"a": "aqui", "de": "laptop", "paso": "abrir"}}})

    def dejar_conversacion(self, carpeta: str = "repo") -> Path:
        from telar import rutas

        with mock.patch.object(Path, "home", return_value=self.casa):
            final = rutas.proyecto(self.raiz / carpeta if carpeta else self.raiz) / f"{self.SID}.jsonl"
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(self.conversacion)
        return final

    def almacen(self):
        """`dueno.con_almacen`, contra el almacén de mentira."""
        from telar import dueno

        return mock.patch.object(dueno, "con_almacen", side_effect=lambda config, hacer: asyncio.run(hacer(self.kv)))

    def llegar(self, **p):
        from telar.agente import lanzar
        from telar.ordenes import _comun

        pedido = {"hilo": "Faro", "sesion": self.SID, "relativa": "repo", "replica": True,
                  "dueno": {"clave": self.CLAVE, "de": "laptop", "epoca": 4}, **p}
        lanz = SimpleNamespace(carpeta=self.raiz / "repo", comando=["claude", "--resume", self.SID], retoma=self.SID)
        with mock.patch.object(_comun, "tejer", return_value=self.tel), \
                mock.patch.object(lanzar, "carpeta", side_effect=lambda c, h: h or Path(c.raiz)), \
                mock.patch.object(lanzar, "para_hilo", return_value=lanz), mock.patch.object(lanzar, "anotar"), \
                mock.patch.object(Path, "home", return_value=self.casa), self.almacen():
            return mudanza.llegar(self.ctx, pedido)

    def test_lo_toma_y_lo_abre_retomandola(self):
        final = self.dejar_conversacion()
        r = self.llegar()
        self.assertTrue(r["ok"], r)
        self.assertEqual(Path(r["conversacion"]), final)
        self.assertEqual(final.read_bytes(), self.conversacion, "la deja como la dejó la copia")
        self.estado.vincular.assert_called_once_with("Faro", "repo")
        self.estado.anotar_sesion.assert_called_once_with("Faro", self.SID)
        self.mux.crear_tab.assert_called_once()
        v = self.kv.valor(self.CLAVE)
        self.assertEqual((v["dueno"], v["maquina"], v["epoca"]), ("aqui", "aqui", 5))
        self.assertNotIn("cede", v)
        self.assertNotIn("mudanza", v, "abierto: el traspaso terminó")

    def test_si_alla_se_echo_atras_ni_lo_toma_ni_lo_abre(self):
        self.dejar_conversacion()
        self.kv = type(self.kv)({self.CLAVE: {"nombre": "Faro", "dueno": "laptop", "epoca": 5}})
        r = self.llegar()
        self.assertFalse(r["ok"])
        self.assertIn("ya no vale", r["error"])
        self.mux.crear_tab.assert_not_called()
        self.assertEqual(self.kv.valor(self.CLAVE)["dueno"], "laptop")

    def test_si_lo_tomo_y_no_pudo_abrirlo_es_de_aqui_igual(self):
        # lo abre el nodo después (abrir_tomado): allá ya no se echa atrás
        self.dejar_conversacion()
        self.mux.crear_tab.side_effect = RuntimeError("sin tmux")
        r = self.llegar()
        self.assertFalse(r["ok"])
        self.assertTrue(r["tomado"])
        v = self.kv.valor(self.CLAVE)
        self.assertEqual((v["dueno"], v["mudanza"]["paso"]), ("aqui", "abrir"))

    def test_de_a_pedazos_o_nada(self):
        from telar import replica

        archivo = self.dir / "c.jsonl"
        archivo.write_bytes(b'{"type":"user"}\n')
        hecho = {"bytes": 16, "conversacion_bytes": 16, "mandados": 0, "red": 0, "archivos": 1, "conversacion": "/x",
                 "carpeta": "/c", "aparte": [], "aviso": "", "saltados": []}
        with mock.patch.object(replica, "mandar", return_value=hecho) as pedazos:
            r = mudanza.mandar(self.ctx, "laptop", self.SID, archivo, "repo")
        self.assertEqual(pedazos.call_args.args[4], {"relativa": "repo"}, "allá la deja donde arranca el hilo")
        self.assertTrue(r["replica"])
        with mock.patch.object(replica, "mandar", side_effect=replica.ErrorDeReplica("se cortó")):
            with self.assertRaisesRegex(mudanza.ErrorDeMudanza, "no llegó a laptop: se cortó"):
                mudanza.mandar(self.ctx, "laptop", self.SID, archivo)
        # un telar de antes allá no sabe recibirla así ni tomar el hilo: no se lleva (antes, entera por la entrada)
        with mock.patch.object(replica, "mandar", side_effect=replica.SinReplica("no atiende")):
            with self.assertRaisesRegex(mudanza.ErrorDeMudanza, "no atiende la copia: su nodo no está, o corre un telar de antes"):
                mudanza.mandar(self.ctx, "laptop", self.SID, archivo)

    def test_sin_su_carpeta_se_abre_en_la_raiz_y_lo_dice(self):
        self.dejar_conversacion(carpeta="")
        r = self.llegar(relativa="otro-repo")
        self.assertTrue(r["ok"], r)
        self.assertIn("no existe aquí", r["aviso"])
        self.estado.vincular.assert_not_called()

    def test_un_hilo_sin_mensajes_se_abre_con_una_nueva(self):
        r = self.llegar(sesion="", replica=False)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["conversacion"], "")
        self.estado.anotar_sesion.assert_not_called()
        self.mux.crear_tab.assert_called_once()

    def test_con_su_registro_su_casilla_y_su_repositorio_al_dia(self):
        # el repositorio, antes de abrirlo (que el agente vea lo que allá se subió); su casilla, ya abierto
        from telar import casilla, sin_subir

        self.dejar_conversacion()
        orden = []
        self.mux.crear_tab.side_effect = lambda *a, **k: orden.append("abrir")
        registro = {"padre": "Taller", "etiquetas": ["cliente"], "prioridad": 1, "esfuerzo": "high", "publico": False,
                    "borradores": [{"id": "b1", "texto": "lo siguiente", "al_terminar": "enviar"}]}
        with mock.patch.object(sin_subir, "al_dia", side_effect=lambda ctx, repos: orden.append(("al día", repos))
                               or ["proyecto: llegaron 3 commits de arriba"]):
            r = self.llegar(registro=registro, casilla=[{"id": "m1", "de": "Telar", "texto": "hola"}],
                            repos=[{"relativa": "repo", "commit": "abc"}])
        self.assertTrue(r["ok"], r)
        self.assertEqual(orden, [("al día", [{"relativa": "repo", "commit": "abc"}]), "abrir"])
        self.estado.colgar.assert_called_once_with("Faro", "Taller")
        self.estado.etiquetar.assert_called_once_with("Faro", ["cliente"])
        self.estado.prioridad.assert_called_once_with("Faro", 1)
        self.estado.anotar_esfuerzo.assert_called_once_with("Faro", "high")
        self.estado.poner_borradores.assert_called_once_with("Faro", registro["borradores"])
        self.assertIn("llegaron 3 commits", r["aviso"])
        self.assertEqual(r["casilla"], 1)
        self.assertEqual([m["texto"] for m in casilla.pendientes(self.ctx.config, "Faro")], ["hola"])

    def test_si_no_abre_su_casilla_no_queda_aqui(self):
        # allá sigue esperando a que se abra aquí: su nodo la entrega cuando abra, no dos veces
        from telar import casilla

        self.dejar_conversacion()
        self.mux.crear_tab.side_effect = RuntimeError("sin tmux")
        r = self.llegar(casilla=[{"id": "m1", "de": "Telar", "texto": "hola"}])
        self.assertFalse(r["ok"])
        self.assertEqual(casilla.pendientes(self.ctx.config, "Faro"), [])

    def test_lo_que_no_se_acepta(self):
        self.dejar_conversacion()
        for cambio, palabra in (({"sesion": "../../x"}, "falta"), ({"dueno": None}, "telar de allá es de antes"),
                                ({"replica": False}, "de antes"), ({"relativa": "otro"}, "no está donde la dejó")):
            with self.subTest(cambio):
                self.assertIn(palabra, self.llegar(**cambio)["error"])
        self.tel.vivos.add("Faro")
        self.assertIn("ya hay un hilo", self.llegar()["error"])
        self.mux.crear_tab.assert_not_called()


class Traer(LaMudanzaAlLlegar):
    def test_el_dueno_corre_llevar_hacia_quien_pide(self):
        # aparte, en su propia sesión (esperar el turno y copiar tarda): contesta en segundos, y si sigue, `en_curso`
        from telar.servicios import llevar as servicio

        proc = mock.Mock(returncode=None)
        proc.poll.return_value = None
        with mock.patch("subprocess.Popen", return_value=proc) as popen, mock.patch.object(mudanza, "ESPERA_TRAER", 0.3):
            r = mudanza.traer_aqui(self.ctx, {"hilo": "Faro", "a": "macbook-de-ana", "si": True})
        self.assertEqual((r["ok"], r["codigo"], r["en_curso"]), (True, 0, True))
        self.assertEqual(popen.call_args.args[0][-6:], ["hilo", "llevar", "macbook-de-ana", "--hilo", "Faro", "--si"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"], "fuera del grupo del nodo: sobrevive su reinicio")
        # lo que pide confirmar falla al tiro, con su salida, para que quien pidió pregunte
        from telar.servicios import ErrorDeServicio

        with mock.patch.object(servicio, "llevar", side_effect=ErrorDeServicio(
                "hay trabajo sin subir; --si para llevarla igual", 409, {"salida": "  · repo: 2 archivos\ntelar: hay trabajo sin subir", "codigo": 1})):
            r = mudanza.traer_aqui(self.ctx, {"hilo": "Faro", "a": "laptop"})
        self.assertEqual((r["ok"], r["codigo"]), (True, 1))
        self.assertIn("· repo: 2 archivos", r["salida"])

    def test_sin_sesion_la_levanta_y_el_hilo_es_el_primero(self):
        from telar.ordenes import _comun

        self.dejar_conversacion()
        dormida = SimpleNamespace(mux=self.mux, viva=False, vivos=set(), estado=self.estado, aviso="")
        with mock.patch.object(_comun, "tejer", side_effect=[dormida, self.tel]):
            from telar.agente import lanzar

            lanz = SimpleNamespace(carpeta=self.raiz, comando=["claude"], retoma=self.SID)
            with mock.patch.object(lanzar, "carpeta", side_effect=lambda c, h: h or Path(c.raiz)), \
                    mock.patch.object(lanzar, "para_hilo", return_value=lanz), mock.patch.object(lanzar, "anotar"), \
                    mock.patch.object(Path, "home", return_value=self.casa), self.almacen():
                r = mudanza.llegar(self.ctx, {"hilo": "Faro", "sesion": self.SID, "relativa": "repo", "replica": True,
                                              "dueno": {"clave": self.CLAVE, "de": "laptop", "epoca": 4}})
        self.assertTrue(r["ok"], r)
        self.mux.tejer.assert_called_once()

    def test_no_acepta_una_maquina_rara(self):
        for a in ("", "a b", "x;reboot", "-rf"):
            self.assertFalse(mudanza.traer_aqui(self.ctx, {"hilo": "Faro", "a": a})["ok"], a)

    def test_al_llegar_cierra_la_ventana_que_solo_lo_miraba(self):
        self.dejar_conversacion()
        self.tel.vivos.add("Faro")
        self.estado.remotos.return_value = {"Faro": {"remoto": "telar", "sesion": "telar:3"}}
        self.mux.hilos.return_value = [SimpleNamespace(nombre="Faro", id="@7")]
        r = self.llegar()
        self.assertTrue(r["ok"], r)
        self.mux.cerrar.assert_called_once_with("@7")
        self.estado.olvidar_remoto.assert_called_once_with("Faro")

    def test_la_que_miraba_se_cierra_despues_de_abrir_la_nueva(self):
        # nunca un momento sin ventana: la página que la mira, y el nodo que la traería otra vez de allá, no lo ven irse
        self.dejar_conversacion()
        self.tel.vivos.add("Faro")
        self.estado.remotos.return_value = {"Faro": {"remoto": "telar", "sesion": "telar:3"}}
        self.mux.hilos.return_value = [SimpleNamespace(nombre="Faro", id="@7")]
        orden = []
        self.estado.olvidar_remoto.side_effect = lambda *a: orden.append("olvidar")
        self.mux.crear_tab.side_effect = lambda *a, **k: orden.append("abrir")
        self.mux.cerrar.side_effect = lambda *a: orden.append("cerrar la que miraba")
        self.assertTrue(self.llegar()["ok"])
        self.assertEqual(orden, ["olvidar", "abrir", "cerrar la que miraba"])

    def test_si_no_abre_la_que_miraba_sigue_mirando_alla(self):
        self.dejar_conversacion()
        self.tel.vivos.add("Faro")
        self.estado.remotos.return_value = {"Faro": {"remoto": "telar", "sesion": "telar:3"}}
        self.mux.hilos.return_value = [SimpleNamespace(nombre="Faro", id="@7")]
        self.mux.crear_tab.side_effect = RuntimeError("sin tmux")
        r = self.llegar()
        self.assertFalse(r["ok"])
        self.mux.cerrar.assert_not_called()
        self.estado.anotar_remoto.assert_called_once_with("Faro", "telar", "telar:3")


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
        self.assertEqual(self.revisar(), {"ok": True, "graves": [], "avisos": [], "repos": []})

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
    """Llevar un hilo a otra máquina por el bus, con un dueño por hilo (telar.dueno): se cede (el registro dice adónde
    va, y su agente se detiene), la conversación viaja, y allá lo toman con esa época. Si algo falla antes de que lo
    tomen, aquí se echa atrás y su agente despierta; si ya lo tomaron, vive allá. Nada se archiva aquí."""

    CLAVE = "ana.faro"
    turno = ""
    #: lo que tiene sin subir (telar.sin_subir.revisar) y lo que se eligió
    pendiente: dict = {"repos": []}
    si, subir = True, False
    sube = (True, "subido")
    #: si allá lo toma al abrirlo (lo que hace hilo-llegar)
    toma_alla = True
    #: lo que dice detener a su agente ("" si se detuvo)
    detiene = ""

    def llevar(self, revision, mandar=None, abrir=None, *, dentro=False, aparte_env=False):
        from comun import KvDeMentira

        from telar import bus as mod_bus
        from telar import dueno, sin_subir
        from telar.ordenes import _comun
        from telar.ordenes import hilo as orden

        self.ctx = SimpleNamespace(config=SimpleNamespace(
            estado=str(self.dir / "estado"), multiplexor="tmux", raiz=str(self.dir),
            bus=SimpleNamespace(url="nats://x", maquina="laptop", persona="ana", token="")))
        self.hilo = SimpleNamespace(nombre="Faro", id="@3")
        self.orden = []  # lo que se hizo, en orden
        self.mux = mock.Mock()
        self.tel = mock.Mock(mux=self.mux)
        self.tel.vivo.return_value = True
        self.tel.estado.archivar.side_effect = lambda *a: self.orden.append("archivar")
        for metodo, valor in (("ramas", {}), ("hijos", []), ("prioridades", {}), ("etiquetas", {}), ("esfuerzos", {}),
                              ("publicos", set()), ("padre", "")):
            getattr(self.tel.estado, metodo).return_value = valor
        self.archivo = self.dir / "c.jsonl"
        self.archivo.write_bytes(b"{}\n")
        self.kv = KvDeMentira({self.CLAVE: {"nombre": "Faro", "dueno": "laptop", "maquina": "laptop", "epoca": 2,
                                            "vivo": True}})
        self.en_registro = {}  # lo que decía el registro en cada paso

        def mandar_(*a, **k):
            self.orden.append("copiar")
            self.en_registro["copiar"] = dict(self.kv.valor(self.CLAVE))
            if isinstance(mandar, Exception):
                raise mandar
            return {"ruta": "", "replica": True, "bytes": 3, "conversacion_bytes": 3}

        def abrir_(*a, **k):
            self.orden.append("abrir")
            self.extra = k.get("extra")
            if self.toma_alla:
                d = self.extra["dueno"]
                asyncio.run(dueno.tomar(self.kv, d["clave"], yo="telar", de_=d["de"], epoca_=d["epoca"], valor={}))
            if isinstance(abrir, Exception):
                raise abrir
            return abrir or {"ok": True, "carpeta": "/x", "aviso": "", "casilla": 0}

        entorno = {orden.APARTE: "1"} if aparte_env else {}
        with mock.patch.object(mod_bus, "pedir", side_effect=revision if callable(revision) else lambda *a, **k: revision), \
                mock.patch.object(dueno, "con_almacen", side_effect=lambda config, hacer: asyncio.run(hacer(self.kv))), \
                mock.patch.object(dueno, "clave", return_value=self.CLAVE), \
                mock.patch.object(mudanza, "mandar", side_effect=mandar_), \
                mock.patch.object(mudanza, "abrir_alla", side_effect=abrir_), \
                mock.patch.object(mudanza, "detener", side_effect=lambda *a: self.orden.append("detener") or self.detiene), \
                mock.patch.object(mudanza, "reanudar", side_effect=lambda *a: self.orden.append("reanudar") or "despertó"), \
                mock.patch.object(mudanza, "soltar", side_effect=lambda *a: self.orden.append("soltar")), \
                mock.patch.object(mudanza, "esperar_turno", side_effect=lambda *a, **k: self.orden.append("esperar") or self.turno) as esperar, \
                mock.patch.object(orden, "_dentro_de", return_value=dentro), \
                mock.patch.object(orden, "_seguir_aparte", return_value=0) as aparte, \
                mock.patch.object(orden, "_avisar_al_hilo") as avisar, \
                mock.patch.dict(os.environ, entorno), \
                mock.patch.object(sin_subir, "revisar", side_effect=lambda *a, **k: self.pendiente), \
                mock.patch.object(sin_subir, "subir", side_effect=lambda *a, **k: (self.orden.append("subir"), self.sube)[1]), \
                mock.patch.object(_comun, "queja", side_effect=lambda t: (self.quejas.append(t), 1)[1]):
            self.quejas = []
            self.extra = None
            r = orden._llevar_por_el_bus(self.ctx, self.tel, self.hilo, "telar", "sid", self.archivo, "repo", si=self.si,
                                         aparte=dentro, subir=self.subir)
        self.aparte, self.esperar, self.avisar = aparte, esperar, avisar
        return r, json.loads(mudanza.ruta_progreso(self.ctx.config, "Faro").read_text())

    def registro(self) -> dict:
        return self.kv.valor(self.CLAVE)

    def test_lo_grave_no_mueve_nada(self):
        r, prog = self.llevar({"ok": True, "graves": ["sin claude"]})
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, [], "ni se cedió ni se copió")
        self.assertEqual(prog["paso"], "falla")
        self.assertIn("No se movió nada", prog["error"])
        self.assertNotIn("cede", self.registro())

    def test_se_cede_se_detiene_viaja_alla_lo_toman_y_aqui_se_cierra_sin_archivar(self):
        r, prog = self.llevar({})
        self.assertEqual(r, 0)
        self.assertEqual(self.orden, ["esperar", "detener", "copiar", "abrir", "soltar"])
        self.tel.estado.archivar.assert_not_called()
        # mientras viajaba, el registro decía que se iba, con su época
        viaje = self.en_registro["copiar"]
        self.assertEqual((viaje["dueno"], viaje["cede"], viaje["epoca"], viaje["mudanza"]["paso"]),
                         ("laptop", "telar", 2, "copiar"))
        self.assertEqual(self.extra["dueno"], {"clave": self.CLAVE, "de": "laptop", "epoca": 2})
        self.assertEqual((self.registro()["dueno"], self.registro()["epoca"]), ("telar", 3))
        self.assertEqual((prog["paso"], prog["carpeta"], prog["maquina"]), ("listo", "/x", "telar"))

    def test_si_la_copia_no_llega_se_echa_atras_y_despierta(self):
        r, prog = self.llevar({}, mandar=mudanza.ErrorDeMudanza("la conversación no llegó a telar: se cortó"))
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, ["esperar", "detener", "copiar", "reanudar"])
        self.assertEqual((self.registro()["dueno"], self.registro()["epoca"]), ("laptop", 3), "la época sube: ya no se toma")
        self.assertNotIn("cede", self.registro())
        self.assertEqual(prog["paso"], "falla")
        self.assertIn("Aquí sigue como estaba", prog["error"])
        self.assertIn("Aquí sigue como estaba", self.quejas[-1], "la CLI lo dice")

    def test_si_alla_no_lo_toma_se_echa_atras(self):
        self.toma_alla = False
        r, prog = self.llevar({}, abrir=mudanza.ErrorDeMudanza("telar recibió la conversación pero no tomó el hilo: x"))
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, ["esperar", "detener", "copiar", "abrir", "reanudar"])
        self.assertEqual(self.registro()["dueno"], "laptop")
        self.assertIn("no tomó el hilo", prog["error"])

    def test_si_alla_ya_lo_tomo_aunque_la_respuesta_falle_vive_alla(self):
        # nunca dos vivos: echarse atrás no puede (allá ya lo tomó), así que aquí no despierta y su ventana se cierra
        r, prog = self.llevar({}, abrir=mudanza.ErrorDeMudanza("telar no contestó"))
        self.assertEqual(r, 0)
        self.assertEqual(self.orden, ["esperar", "detener", "copiar", "abrir", "soltar"])
        self.assertEqual(self.registro()["dueno"], "telar")
        self.assertIn("ya lo había tomado", prog["aviso"])

    def test_si_no_se_puede_detener_a_su_agente_no_se_mueve(self):
        self.detiene = "su ventana tiene más de un panel: ciérralos antes de llevarlo"
        r, prog = self.llevar({})
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, ["esperar", "detener", "reanudar"])
        self.assertEqual(self.registro()["dueno"], "laptop")
        self.assertIn("más de un panel", prog["error"])

    def test_abrir_alla_sin_respuesta_lo_dice_el_registro(self):
        from telar import bus as mod_bus
        from telar import dueno

        ctx = SimpleNamespace(config=SimpleNamespace(estado=str(self.dir / "estado")))
        for dueno_ahora, llego in (("telar", True), ("laptop", False)):
            with self.subTest(dueno_ahora), \
                    mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "telar no respondió a tiempo"}), \
                    mock.patch.object(dueno, "registro", return_value={"dueno": dueno_ahora}):
                if llego:
                    r = mudanza.abrir_alla(ctx, "Faro", "telar", "sid", {"replica": True}, "repo")
                    self.assertTrue(r["ok"] and r["tomado"])
                    self.assertIn("lo tomó", r["aviso"])
                else:
                    with self.assertRaisesRegex(mudanza.ErrorDeMudanza, "no tomó el hilo"):
                        mudanza.abrir_alla(ctx, "Faro", "telar", "sid", {"replica": True}, "repo")
        # un «no» de allá (no lo tomó) no se confunde con la falta de respuesta: no se mira el registro
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "aquí ya hay un hilo «Faro» abierto"}), \
                mock.patch.object(dueno, "registro") as reg:
            with self.assertRaises(mudanza.ErrorDeMudanza):
                mudanza.abrir_alla(ctx, "Faro", "telar", "sid", {"replica": True}, "repo")
        reg.assert_not_called()

    def test_pedido_desde_su_ventana_sigue_aparte_sin_tocar_nada(self):
        # el agente del hilo corre `telar hilo llevar`: revisa y pregunta aquí, y lo demás sigue en un proceso aparte
        r, _ = self.llevar({}, dentro=True)
        self.assertEqual(r, 0)
        self.aparte.assert_called_once()
        self.assertEqual(self.orden, [], "nada se cedió ni se copió desde la ventana que se detiene")
        self.esperar.assert_not_called()

    def test_aparte_espera_su_turno_antes_de_copiar(self):
        r, _ = self.llevar({}, aparte_env=True)
        self.assertEqual(r, 0)
        self.esperar.assert_called_once()
        self.assertEqual(self.orden, ["esperar", "detener", "copiar", "abrir", "soltar"])

    def test_desde_la_pagina_traer_o_la_cli_tambien_espera_su_turno(self):
        # antes solo esperaba el agente que se llevaba a sí mismo: la página y «traer» copiaban con el turno a medias
        r, _ = self.llevar({})
        self.assertEqual(r, 0)
        self.esperar.assert_called_once()
        self.assertEqual(self.orden[0], "esperar")

    def test_si_no_termina_su_turno_no_se_mueve_nada(self):
        self.turno = "su agente sigue trabajando después de 10 min: no se movió nada"
        r, prog = self.llevar({})
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, ["esperar"])
        self.assertEqual(prog["paso"], "falla")
        self.assertIn("sigue trabajando", prog["error"])
        self.assertNotIn("cede", self.registro(), "ni siquiera se cedió")

    def test_aparte_si_falla_se_le_dice_al_hilo(self):
        self.toma_alla = False
        r, prog = self.llevar({}, abrir=mudanza.ErrorDeMudanza("telar no tomó el hilo"), aparte_env=True)
        self.assertEqual(r, 1)
        self.avisar.assert_called_once()
        self.assertIn("Aquí sigue como estaba", self.avisar.call_args.args[2])

    PENDIENTE = {"repos": [{"repo": "/r", "nombre": "proyecto", "relativa": "proyecto", "rama": "main",
                            "arriba": "origin/main", "commit": "a" * 40, "del_hilo": ["a.txt"], "n_del_hilo": 1,
                            "en_su_carpeta": ["gen.png"], "n_en_su_carpeta": 1, "commits": [], "n_commits": 0,
                            "puede_subir": True, "por_que_no": "", "pendiente": True}]}

    def test_con_algo_sin_subir_pregunta_antes_de_tocar_nada(self):
        # desde la página (sin terminal) y sin elegir: falla diciendo qué elegir, con el detalle en el progreso
        self.pendiente, self.si = self.PENDIENTE, False
        destino = [{"relativa": "proyecto", "existe": True, "tiene": False}]
        with mock.patch("sys.stdin.isatty", return_value=False):
            r, prog = self.llevar({"ok": True, "graves": [], "avisos": [], "repos": destino})
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, [], "ni esperó su turno ni cedió")
        self.assertIn("--subir", self.quejas[-1])
        self.assertIn("llevarla igual", self.quejas[-1], "lo que la página reconoce para preguntar")
        self.assertEqual((prog["paso"], prog["pendiente"], prog["destino"], prog["maquina"]),
                         ("revisar", self.PENDIENTE, destino, "telar"))

    def test_sin_nada_sin_subir_ni_se_pregunta(self):
        self.pendiente, self.si = {"repos": [{**self.PENDIENTE["repos"][0], "del_hilo": [], "n_del_hilo": 0,
                                               "en_su_carpeta": [], "n_en_su_carpeta": 0, "pendiente": False}]}, False
        r, _ = self.llevar({"ok": True, "graves": [], "avisos": []})
        self.assertEqual(r, 0)
        self.assertEqual(self.orden, ["esperar", "detener", "copiar", "abrir", "soltar"])

    def test_subir_y_llevar_sube_despues_de_su_turno_y_antes_de_ceder(self):
        self.pendiente, self.si, self.subir = self.PENDIENTE, False, True
        r, prog = self.llevar({"ok": True, "graves": [], "avisos": []})
        self.assertEqual(r, 0)
        self.assertEqual(self.orden, ["esperar", "subir", "detener", "copiar", "abrir", "soltar"])
        self.assertEqual(prog["subido"], "subido")
        # allá se abre con su repositorio al día, su registro y su casilla
        self.assertEqual(self.extra["repos"][0]["relativa"], "proyecto")
        self.assertEqual(set(self.extra["registro"]), {"padre", "etiquetas", "prioridad", "esfuerzo", "publico", "borradores"})
        self.assertEqual(self.extra["casilla"], [])

    def test_si_no_sube_no_se_mueve(self):
        self.pendiente, self.si, self.subir = self.PENDIENTE, False, True
        self.sube = (False, "proyecto: no subió (choque): lo que llega toca a.txt")
        r, prog = self.llevar({"ok": True, "graves": [], "avisos": []})
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, ["esperar", "subir"])
        self.assertEqual(prog["paso"], "falla")
        self.assertIn("no pude subir lo suyo", prog["error"])
        self.assertIn("No se movió nada", prog["error"])

    def test_llevar_igual_no_sube_nada(self):
        self.pendiente, self.si = self.PENDIENTE, True
        r, _ = self.llevar({"ok": True, "graves": [], "avisos": []})
        self.assertEqual(r, 0)
        self.assertNotIn("subir", self.orden)

    def test_lo_de_su_casilla_va_con_el_y_sale_de_aqui(self):
        from telar import bus as mod_bus
        from telar import casilla

        config = SimpleNamespace(estado=str(self.dir / "estado"))
        m = mod_bus.mensaje("revisa esto", de="Telar", para="Faro")
        casilla.dejar(config, "Faro", m)
        r, _ = self.llevar({"ok": True, "graves": [], "avisos": []})
        self.assertEqual(r, 0)
        self.assertEqual([x["id"] for x in self.extra["casilla"]], [m["id"]])
        self.assertEqual(casilla.pendientes(config, "Faro"), [], "allá lo entrega su nodo")


    def test_sus_borradores_salen_de_aqui_solo_si_alla_dice_que_llegaron(self):
        # los próximos prompts de la persona (telar.borradores): un telar de allá más viejo no los recibe ni lo dice, y
        # entonces se quedan aquí en vez de perderse
        r, _ = self.llevar({"ok": True, "graves": [], "avisos": []},
                           abrir={"ok": True, "carpeta": "/x", "aviso": "", "casilla": 0, "borradores": 2})
        self.assertEqual(r, 0)
        self.tel.estado.poner_borradores.assert_called_once_with("Faro", [])
        self.tel.estado.poner_borradores.reset_mock()
        r, _ = self.llevar({"ok": True, "graves": [], "avisos": []})
        self.assertEqual(r, 0)
        self.tel.estado.poner_borradores.assert_not_called()


class EsperarSuTurno(_ConCarpeta):
    """Antes de copiar la conversación de un agente que se lleva a sí mismo: que termine su turno."""

    def test_espera_a_que_deje_de_trabajar_y_de_escribir(self):
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        archivo = self.dir / "c.jsonl"
        archivo.write_bytes(b"x")
        atenciones = iter([Atencion.TRABAJANDO, Atencion.TRABAJANDO, Atencion.TERMINO, Atencion.TERMINO,
                           Atencion.TERMINO, Atencion.TERMINO])
        est = mock.Mock()
        est.atencion.side_effect = lambda h: next(atenciones, Atencion.TERMINO)
        reloj = [0.0]
        with mock.patch.object(mod_estado, "abrir", return_value=est), \
                mock.patch("time.monotonic", side_effect=lambda: reloj[0]), \
                mock.patch("time.sleep", side_effect=lambda s: reloj.__setitem__(0, reloj[0] + s)):
            self.assertEqual(mudanza.esperar_turno(SimpleNamespace(), "Faro", archivo, quieto=2, paso=1), "")
        self.assertGreaterEqual(reloj[0], 2)

    def test_si_ya_estaba_quieto_no_espera(self):
        # sin turno a medias y la conversación sin crecer desde hace rato: se copia al tiro, sin decir que espera
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        archivo = self.dir / "c.jsonl"
        archivo.write_bytes(b"x")
        os.utime(archivo, (1, 1))
        est = mock.Mock()
        est.atencion.return_value = Atencion.TERMINO
        avisos = []
        with mock.patch.object(mod_estado, "abrir", return_value=est), mock.patch("time.sleep") as dormir:
            self.assertEqual(mudanza.esperar_turno(SimpleNamespace(), "Faro", archivo, al_esperar=lambda: avisos.append(1)), "")
        dormir.assert_not_called()
        self.assertEqual(avisos, [])

    def test_si_espera_lo_dice_una_vez(self):
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        est = mock.Mock()
        est.atencion.side_effect = [Atencion.TRABAJANDO] * 3 + [Atencion.TERMINO] * 20
        reloj, avisos = [0.0], []
        with mock.patch.object(mod_estado, "abrir", return_value=est), \
                mock.patch("time.monotonic", side_effect=lambda: reloj[0]), \
                mock.patch("time.sleep", side_effect=lambda s: reloj.__setitem__(0, reloj[0] + s)):
            r = mudanza.esperar_turno(SimpleNamespace(), "Faro", None, quieto=2, paso=1, al_esperar=lambda: avisos.append(1))
        self.assertEqual((r, avisos), ("", [1]))

    def test_si_no_termina_no_se_lleva(self):
        from telar import estado as mod_estado
        from telar.modelo import Atencion

        est = mock.Mock()
        est.atencion.return_value = Atencion.TRABAJANDO
        reloj = [0.0]
        with mock.patch.object(mod_estado, "abrir", return_value=est), \
                mock.patch("time.monotonic", side_effect=lambda: reloj[0]), \
                mock.patch("time.sleep", side_effect=lambda s: reloj.__setitem__(0, reloj[0] + s)):
            r = mudanza.esperar_turno(SimpleNamespace(), "Faro", None, tope=60, paso=5)
        self.assertIn("no se movió nada", r)


class LlevarPorSsh(_ConCarpeta):
    """A una máquina de [remotos]: lo mismo, aquí no se cierra nada hasta que allá está abierto."""

    del_bus: list = []
    ramas: dict = {}
    pendiente: dict = {"repos": []}

    def llevar(self, copiar=("~/.claude/x.jsonl", ""), abrir=None):
        from telar import agente as mod_agente
        from telar import directorio as mod_directorio
        from telar import remoto as mod_remoto
        from telar.ordenes import _comun
        from telar.ordenes import hilo as orden

        archivo = self.dir / "c.jsonl"
        archivo.write_bytes(b"{}\n")
        remoto = SimpleNamespace(nombre="telar", destino="ana@telar", repos=[])
        self.ctx = SimpleNamespace(config=SimpleNamespace(
            estado=str(self.dir / "estado"), raiz=str(self.dir), remotos=[remoto], multiplexor="tmux",
            agente=SimpleNamespace(nombre="claude-code")))
        hilo = SimpleNamespace(nombre="Faro", id="@3", remoto="", sesiones=("sid",), ruta=None)
        self.orden = []
        self.mux = mock.Mock()
        self.mux.cerrar.side_effect = lambda *a: self.orden.append("cerrar")
        tel = mock.Mock(mux=self.mux)
        tel.vivo.return_value = True
        tel.estado.vinculos.return_value = {}
        for metodo, valor in (("ramas", self.ramas), ("hijos", []), ("prioridades", {}), ("etiquetas", {}),
                              ("esfuerzos", {}), ("publicos", set()), ("padre", "")):
            getattr(tel.estado, metodo).return_value = valor
        from telar import sin_subir

        def copiar_(*a):
            self.orden.append("copiar")
            return copiar

        def abrir_(*a, **k):
            self.orden.append("abrir")
            if abrir:
                raise abrir

        agente = mock.Mock()
        agente.archivo_de.return_value = archivo
        from telar.agente import lanzar

        with mock.patch.object(mod_agente, "obtener", return_value=agente), \
                mock.patch.object(lanzar, "carpeta", return_value=self.dir), \
                mock.patch.object(sin_subir, "revisar", return_value=self.pendiente), \
                mock.patch.object(orden, "_dentro_de", return_value=False), \
                mock.patch.object(mod_remoto, "carpeta_remota", return_value="~/repo"), \
                mock.patch.object(mod_remoto, "copiar_conversacion", side_effect=copiar_), \
                mock.patch.object(mod_remoto, "abrir", side_effect=abrir_), \
                mock.patch.object(mod_directorio, "publicar_callado"), \
                mock.patch.object(orden, "_desarchivar_alla", side_effect=lambda *a: self.orden.append("desarchivar allá")), \
                mock.patch.object(mudanza, "esperar_turno", side_effect=lambda *a, **k: self.orden.append("esperar") or ""), \
                mock.patch.object(mudanza, "maquinas_del_bus", return_value=self.del_bus), \
                mock.patch.object(_comun, "queja", side_effect=lambda t: (self.quejas.append(t), 1)[1]):
            self.quejas = []
            r = orden._llevar(self.ctx, tel, hilo, "telar", si=True)
        return r, json.loads(mudanza.ruta_progreso(self.ctx.config, "Faro").read_text())

    def test_al_llegar_cierra_aqui_lo_ultimo(self):
        r, prog = self.llevar()
        self.assertEqual(r, 0)
        # de vuelta a donde quedó archivado al irse: allá deja de estarlo. Antes de copiar, su turno, siempre
        self.assertEqual(self.orden, ["esperar", "copiar", "abrir", "desarchivar allá", "cerrar"])
        self.assertEqual(prog["paso"], "listo")

    def test_si_la_copia_falla_aqui_sigue_como_estaba(self):
        r, prog = self.llevar(copiar=("", "ana@telar no responde"))
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, ["esperar", "copiar"])
        self.assertIn("Aquí sigue como estaba", prog["error"])

    def test_si_alla_no_abre_aqui_sigue_como_estaba(self):
        from telar.mux import ErrorDeMux

        r, prog = self.llevar(abrir=ErrorDeMux("sin sesión allá"))
        self.assertEqual(r, 1)
        self.assertEqual(self.orden, ["esperar", "copiar", "abrir"])
        self.assertIn("Aquí sigue como estaba", prog["error"])

    def test_si_esta_en_el_bus_va_por_el_bus(self):
        # por ssh ya no se mudan hilos si la otra máquina está en el bus: allí hay un dueño que compartir
        from telar.ordenes import hilo as orden

        self.del_bus = ["telar"]
        from telar import mudanza as m

        with mock.patch.object(orden, "_conocidas_del_bus", return_value={"telar"}), \
                mock.patch.object(orden, "_llevar_por_el_bus", side_effect=lambda ctx, *a, **k: m.progreso(
                ctx.config, "Faro", "revisar", maquina="telar") or 0) as bus:
            r, _ = self.llevar()
        self.assertEqual(r, 0)
        self.assertEqual(bus.call_args.args[3], "telar")
        self.assertEqual(self.orden, [], "ni ssh ni tmux allá")


class DentroDeSuVentana(_ConCarpeta):
    """Si `telar hilo llevar` corre en la ventana del hilo que lleva (su agente pidió llevarse a sí mismo)."""

    def dentro(self, entorno, panes=("%1",)):
        from telar.ordenes import hilo as orden

        ctx = SimpleNamespace(config=SimpleNamespace(multiplexor="tmux"))
        mux = mock.Mock()
        mux.panes.return_value = [SimpleNamespace(id=p, tab="@3") for p in panes]
        tel = mock.Mock(mux=mux)
        tel.vivo.return_value = True
        with mock.patch.dict(os.environ, entorno, clear=False):
            for k in ("TMUX_PANE", "TELAR_PANEL", "TELAR_HILO", orden.APARTE):
                if k not in entorno:
                    os.environ.pop(k, None)
            return orden._dentro_de(ctx, tel, SimpleNamespace(nombre="Faro", id="@3"))

    def test_su_panel_esta_en_la_ventana_del_hilo(self):
        self.assertTrue(self.dentro({"TMUX_PANE": "%1"}))
        self.assertFalse(self.dentro({"TMUX_PANE": "%9"}), "otro panel: otra ventana")
        self.assertFalse(self.dentro({}), "fuera de tmux (la página, el nodo, otra terminal)")
        self.assertFalse(self.dentro({"TMUX_PANE": "%1", "TELAR_LLEVAR_APARTE": "1"}), "el proceso aparte ya no lo está")

    def test_el_proceso_aparte_queda_fuera_del_arbol_del_agente(self):
        from telar.ordenes import hilo as orden

        ctx = SimpleNamespace(config=SimpleNamespace(estado=str(self.dir / "estado")))
        with mock.patch("subprocess.Popen") as popen:
            r = orden._seguir_aparte(ctx, SimpleNamespace(nombre="Faro"), "laptop", "")
        self.assertEqual(r, 0)
        k = popen.call_args.kwargs
        self.assertTrue(k["start_new_session"])
        self.assertEqual(k["env"][orden.APARTE], "1")
        self.assertEqual(popen.call_args.args[0][3:], ["hilo", "llevar", "laptop", "--hilo", "Faro", "--si"])


class DeVueltaSeReemplazaLaCopia(_ConCarpeta):
    """Un hilo que vuelve a la máquina de donde se fue: allá quedó la copia de cuando se fue (más lo que Claude anota al
    cerrarse). Por el bus (`llegar`) y por ssh (`remoto._DEJAR`), si la que llega la continúa, la reemplaza; si allá se
    siguió por su lado, la de allá queda aparte. Antes, por ssh: «ya hay una conversación con ese id allá»."""

    SID = "0f3c2a9e-1111-2222-3333-444455556666"
    MENSAJES = b'{"type":"user","n":1}\n{"type":"assistant","n":2}\n'
    CIERRE = b'{"type":"last-prompt"}\n{"type":"cost-state"}\n'

    def dejar(self, casa, datos):
        import subprocess
        import sys

        from telar import remoto

        return subprocess.run([sys.executable, "-c", remoto._DEJAR, str(casa / "trabajo"), self.SID, str(len(datos))],
                              input=gzip.compress(datos), capture_output=True, env={**os.environ, "HOME": str(casa)})

    def test_por_ssh_reemplaza_la_copia_de_cuando_se_fue(self):
        casa = self.dir / "casa"
        r = self.dejar(casa, self.MENSAJES)
        self.assertEqual(r.returncode, 0, r.stderr)
        ruta = Path(r.stdout.decode().strip())
        ruta.write_bytes(self.MENSAJES + self.CIERRE)  # Claude se cerró aquí al irse
        vuelve = self.MENSAJES + b'{"type":"user","n":3}\n'
        r = self.dejar(casa, vuelve)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ruta.read_bytes(), vuelve)
        self.assertEqual(list(ruta.parent.glob("*.bak")), [])

    def test_por_ssh_lo_seguido_alla_queda_aparte(self):
        casa = self.dir / "casa"
        ruta = Path(self.dejar(casa, self.MENSAJES).stdout.decode().strip())
        ruta.write_bytes(self.MENSAJES + b'{"type":"assistant","n":9}\n')
        r = self.dejar(casa, self.MENSAJES + b'{"type":"user","n":3}\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("quedó en", r.stderr.decode())
        (aparte,) = ruta.parent.glob("*.bak")
        self.assertIn(b'"n":9', aparte.read_bytes())

    def test_por_ssh_una_cortada_no(self):
        casa = self.dir / "casa"
        import subprocess
        import sys

        from telar import remoto

        r = subprocess.run([sys.executable, "-c", remoto._DEJAR, str(casa / "t"), self.SID, "999"],
                           input=gzip.compress(self.MENSAJES), capture_output=True, env={**os.environ, "HOME": str(casa)})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("cortada", r.stderr.decode())


class TraerDesdeLaQuePide(_ConCarpeta):
    """La máquina que pide traer un hilo: la dueña contesta en segundos que sigue (`en_curso`), y su progreso se lee
    de allá por el bus (`mudanza-progreso`), como si fuera el de aquí."""

    def ctx(self):
        return SimpleNamespace(config=SimpleNamespace(estado=str(self.dir / "estado"), bus=SimpleNamespace(url="nats://x")))

    def test_la_duena_contesta_que_sigue(self):
        from telar import bus as mod_bus
        from telar.servicios import llevar as servicio

        with mock.patch.object(mod_bus, "hay_bus", return_value=True), \
                mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "codigo": 0, "salida": "", "en_curso": True}) as pedir:
            r = servicio.traer(self.ctx(), "Faro", "telar")
        self.assertTrue(r.en_curso)
        self.assertEqual(pedir.call_args.args[1:3], ("telar", "hilo-traer"))
        self.assertEqual(pedir.call_args.args[3], {"hilo": "Faro", "a": "laptop", "si": False})
        self.assertLessEqual(pedir.call_args.kwargs["espera"], 120, "ya no espera diez minutos a la dueña")

    def test_su_progreso_se_lee_de_alla(self):
        from telar import bus as mod_bus
        from telar.servicios import llevar as servicio

        ctx = self.ctx()
        mudanza.progreso(ctx.config, "Faro", "revisar", maquina="aqui-mismo")
        alla = {"paso": "copiar", "maquina": "laptop", "por_mandar": 1200000, "mandados": 300000, "hora": 1}
        with mock.patch.object(mod_bus, "hay_bus", return_value=True), \
                mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "progreso": alla}) as pedir:
            self.assertEqual(servicio.progreso(ctx, "Faro", "telar"), alla)
            self.assertEqual(pedir.call_args.args[1:4], ("telar", "mudanza-progreso", {"hilo": "Faro"}))
            self.assertEqual(servicio.progreso(ctx, "Faro")["maquina"], "aqui-mismo", "sin máquina, la de aquí")
            self.assertEqual(servicio.progreso(ctx, "Faro", "laptop")["maquina"], "aqui-mismo", "esta máquina es aquí")
        with mock.patch.object(mod_bus, "hay_bus", return_value=True), \
                mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "no respondió"}):
            self.assertEqual(servicio.progreso(ctx, "Faro", "telar"), {})
        self.assertEqual(mudanza.progreso_de(ctx.config, "Otro"), {})


class LosHijosConRama(_ConCarpeta):
    """Un hijo con rama no se muda: su rama y su worktree existen solo en su máquina. Su padre sí, solo."""

    def tel(self, ramas, hijos=()):
        tel = mock.Mock()
        tel.estado.ramas.return_value = ramas
        tel.estado.hijos.return_value = list(hijos)
        return tel

    def test_un_hijo_con_rama_no_se_lleva(self):
        from telar.ordenes import _comun
        from telar.ordenes import hilo as orden

        ctx = SimpleNamespace(config=SimpleNamespace(remotos=[], estado=str(self.dir / "estado")))
        tel = self.tel({"Calendario": {"rama": "calendario", "ruta": "/home/ana/worktrees/faro-calendario"}})
        quejas = []
        with mock.patch.object(mudanza, "maquinas_del_bus", return_value=["servidor"]), \
                mock.patch.object(_comun, "queja", side_effect=lambda t: (quejas.append(t), 1)[1]):
            r = orden._llevar(ctx, tel, SimpleNamespace(nombre="Calendario", remoto="", sesiones=("sid",)), "servidor", True)
        self.assertEqual(r, 1)
        self.assertIn("hijo con rama", quejas[0])
        self.assertIn("worktrees/faro-calendario", quejas[0])
        self.assertIn("No se movió nada", quejas[0])

    def test_su_padre_se_lleva_solo_y_se_dice(self):
        from telar import sin_subir
        from telar.ordenes import hilo as orden

        ctx = SimpleNamespace(config=SimpleNamespace(raiz=str(self.dir)))
        tel = self.tel({"Calendario": {"rama": "calendario"}}, hijos=["Calendario", "Notas"])
        with mock.patch.object(sin_subir, "revisar", return_value={"repos": []}):
            _, avisos = orden._lo_de_aqui(ctx, tel, SimpleNamespace(nombre="Faro"), "", None, "")
        (aviso,) = avisos
        self.assertIn("(Calendario) se quedan aquí", aviso)
        self.assertNotIn("Notas", aviso)

    def test_el_proceso_aparte_lleva_lo_decidido(self):
        from telar.ordenes import hilo as orden

        ctx = SimpleNamespace(config=SimpleNamespace(estado=str(self.dir / "estado")))
        for subir, bandera in ((True, "--subir"), (False, "--si")):
            with mock.patch("subprocess.Popen") as popen:
                orden._seguir_aparte(ctx, SimpleNamespace(nombre="Faro"), "laptop", "", subir)
            argv = popen.call_args.args[0]
            self.assertIn(bandera, argv)
            self.assertNotIn("--si" if subir else "--subir", argv)

    def test_la_pagina_pide_subir(self):
        from telar.servicios import llevar as servicio

        ctx = SimpleNamespace(config=SimpleNamespace(estado=str(self.dir / "estado")))
        proc = mock.Mock(returncode=0)
        proc.poll.return_value = 0
        with mock.patch("subprocess.Popen", return_value=proc) as popen:
            servicio.llevar(ctx, "Faro", "servidor", subir=True)
        self.assertEqual(popen.call_args.args[0][-3:], ["--hilo", "Faro", "--subir"])
