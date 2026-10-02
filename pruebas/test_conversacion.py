"""La conversación de un hilo, por páginas: lo que se sirve y lo que no."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import conversacion as m
from telar.ordenes import web

SID = "aaaaaaaa-1111-2222-3333-444444444444"
OTRA = "bbbbbbbb-1111-2222-3333-444444444444"


def mensajes(n, quien="agente"):
    return [{"quien": quien if i % 2 else "usuario", "hora": f"2026-09-30T10:{i % 60:02d}:00Z", "texto": f"mensaje {i}"} for i in range(n)]


class ConAgente(Prueba):
    """Un agente de mentira que lee de un diccionario y cuenta cuántas veces se lee."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.config = mod_config.Config(raiz=self.base, estado=self.base / "estado")
        self.archivos = {}
        self.lecturas = 0
        self.contenido = {SID: mensajes(150)}

        def archivo_de(sid):
            return self.archivos.get(sid)

        def leer(sid):
            self.lecturas += 1
            return self.contenido.get(sid)

        self.agente = SimpleNamespace(archivo_de=archivo_de, mensajes=leer)
        parche = mock.patch.object(m, "_agente", return_value=self.agente)
        parche.start()
        self.addCleanup(parche.stop)
        m._cache.clear()
        self.addCleanup(m._cache.clear)
        self.poner(SID)

    def poner(self, sid):
        ruta = self.base / f"{sid}.jsonl"
        ruta.write_text("x")
        self.archivos[sid] = ruta
        return ruta


class Paginas(ConAgente):
    def test_al_abrir_van_los_ultimos(self):
        p = m.pagina(self.config, [SID])
        self.assertEqual((p["desde"], p["hasta"], p["total"]), (90, 150, 150))
        self.assertEqual(p["mensajes"][0]["texto"], "mensaje 90")
        self.assertEqual(p["mensajes"][-1]["texto"], "mensaje 149")

    def test_los_anteriores_empiezan_donde_termina_lo_que_ya_se_tiene(self):
        p = m.pagina(self.config, [SID], antes=90)
        self.assertEqual((p["desde"], p["hasta"]), (30, 90))
        p = m.pagina(self.config, [SID], antes=30, n=100)  # no pasa de la primera
        self.assertEqual((p["desde"], p["hasta"]), (0, 30))
        self.assertEqual(m.pagina(self.config, [SID], antes=0)["mensajes"], [])

    def test_lo_que_llego_despues_para_seguir_en_vivo(self):
        self.assertEqual(m.pagina(self.config, [SID], despues=150)["mensajes"], [])
        self.contenido[SID] = mensajes(153)
        self.archivos[SID].write_text("xx")  # el archivo creció
        p = m.pagina(self.config, [SID], despues=150)
        self.assertEqual([x["texto"] for x in p["mensajes"]], ["mensaje 150", "mensaje 151", "mensaje 152"])
        self.assertEqual((p["desde"], p["hasta"], p["total"]), (150, 153, 153))

    def test_los_indices_absurdos_no_rompen(self):
        for k in dict(despues=10**9), dict(despues=-5), dict(antes=10**9), dict(antes=-1):
            p = m.pagina(self.config, [SID], **k)
            self.assertLessEqual(p["hasta"], p["total"])
            self.assertGreaterEqual(p["desde"], 0)
        self.assertLessEqual(len(m.pagina(self.config, [SID], n=10**6)["mensajes"]), m.MAXIMO)

    def test_un_mensaje_enorme_se_recorta_y_se_dice(self):
        self.contenido[SID] = [{"quien": "agente", "hora": "", "texto": "x" * (m.MAX_TEXTO + 123)}]
        [msg] = m.pagina(self.config, [SID])["mensajes"]
        self.assertEqual(len(msg["texto"]), m.MAX_TEXTO)
        self.assertEqual(msg["recortado"], 123)


class Permisos(ConAgente):
    def test_solo_se_abre_una_conversacion_del_hilo(self):
        self.contenido[OTRA] = mensajes(3)
        self.poner(OTRA)
        with self.assertRaises(m.ErrorDeConversacion):
            m.pagina(self.config, [SID], sesion=OTRA)  # existe en disco, pero no es de este hilo
        self.assertEqual(m.pagina(self.config, [SID, OTRA], sesion=OTRA)["sesion"], OTRA)

    def test_un_hilo_sin_conversaciones(self):
        with self.assertRaises(m.ErrorDeConversacion):
            m.pagina(self.config, [])

    def test_un_id_raro_nunca_llega_al_disco(self):
        for malo in ("../../etc/passwd", "a" * 100, "x y", "", "*"):
            with self.assertRaises(m.ErrorDeConversacion, msg=malo):
                m.leer(self.config, malo)
        self.assertEqual(self.lecturas, 0)

    def test_una_conversacion_que_no_esta_en_disco_se_dice(self):
        self.archivos.clear()
        with self.assertRaises(m.ErrorDeConversacion) as e:
            m.pagina(self.config, [SID])
        self.assertIn("no está en disco", str(e.exception))


class Cache(ConAgente):
    def test_no_se_relee_mientras_el_archivo_no_cambie(self):
        for _ in range(5):
            m.pagina(self.config, [SID])
        self.assertEqual(self.lecturas, 1)

    def test_si_el_archivo_cambia_se_relee(self):
        m.pagina(self.config, [SID])
        self.archivos[SID].write_text("mas contenido")
        m.pagina(self.config, [SID])
        self.assertEqual(self.lecturas, 2)


class LaRuta(ConAgente):
    """`GET /api/conversacion`: se pide por hilo, y de ahí salen las conversaciones permitidas."""

    HILOS = {"hilos": [
        {"nombre": "Faro", "atencion": "espera", "vivo": True, "archivado": False, "sesiones": [SID]},
        {"nombre": "Viejo", "atencion": "ninguna", "vivo": False, "archivado": True, "sesiones": [OTRA]},
        {"nombre": "Vacio", "atencion": "ninguna", "vivo": False, "archivado": False, "sesiones": []},
    ]}

    def pedir(self, consulta):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), web.manejador(True, self.config))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        try:
            with mock.patch.object(web, "datos", return_value=json.dumps(self.HILOS).encode()):
                with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/conversacion?{consulta}") as r:
                    return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_devuelve_la_pagina_con_el_estado_del_hilo(self):
        codigo, cuerpo = self.pedir("hilo=Faro")
        self.assertEqual(codigo, 200)
        self.assertEqual(cuerpo["hilo"], {"nombre": "Faro", "atencion": "espera", "vivo": True})
        self.assertEqual(cuerpo["hasta"], 150)
        self.assertEqual(len(cuerpo["mensajes"]), 60)

    def test_los_parametros_llegan(self):
        _, cuerpo = self.pedir("hilo=Faro&antes=90&n=10")
        self.assertEqual((cuerpo["desde"], cuerpo["hasta"]), (80, 90))
        _, cuerpo = self.pedir("hilo=Faro&despues=148")
        self.assertEqual([x["texto"] for x in cuerpo["mensajes"]], ["mensaje 148", "mensaje 149"])

    def test_lo_que_no_es_de_un_hilo_conocido_se_rechaza(self):
        self.contenido[OTRA] = mensajes(2)
        self.poner(OTRA)
        for consulta, codigo in (("", 400), ("hilo=Nadie", 404), ("hilo=Viejo", 404), ("hilo=Vacio", 404),
                                 (f"hilo=Faro&sesion={OTRA}", 404), ("hilo=Faro&antes=abc", 400),
                                 (f"sesion={SID}", 400)):
            self.assertEqual(self.pedir(consulta)[0], codigo, consulta)


class UnSoloLector(ConAgente):
    """La web y la CLI/la puerta (`telar.historia`) leen la misma conversación por el mismo camino."""

    def test_sin_pedir_ninguna_es_la_primera_que_tiene_archivo(self):
        self.contenido[OTRA] = mensajes(4)
        self.poner(OTRA)
        del self.archivos[SID]  # la primera de las del hilo vivió en otra máquina
        p = m.pagina(self.config, [SID, OTRA])
        self.assertEqual((p["sesion"], p["total"]), (OTRA, 4))

    def test_historia_y_la_web_eligen_la_misma(self):
        from telar import historia

        self.contenido[OTRA] = mensajes(4)
        self.poner(OTRA)
        del self.archivos[SID]
        hilo = SimpleNamespace(nombre="Faro", id="@1", sesiones=(SID, OTRA))
        d = historia.leer(SimpleNamespace(config=self.config), SimpleNamespace(mux=None), hilo)
        self.assertEqual(d["conversacion"], m.pagina(self.config, [SID, OTRA])["sesion"])

    def test_pedir_una_concreta_sigue_exigiendo_que_sea_del_hilo(self):
        self.contenido[OTRA] = mensajes(2)
        self.poner(OTRA)
        with self.assertRaises(m.ErrorDeConversacion):
            m.mensajes_del_hilo(self.config, [SID], OTRA)

    def test_lo_que_entrega_la_puerta_se_aplana_a_la_forma_de_la_web(self):
        turnos = [[{"quien": "usuario", "hora": "h", "texto": "a"}, {"quien": "agente", "hora": "h", "texto": "b"}],
                  [{"quien": "usuario", "hora": "h", "texto": "c"}]]
        self.assertEqual([x["texto"] for x in m.aplanar({"fuente": "conversacion", "turnos": turnos})], ["a", "b", "c"])
        [panel] = m.aplanar({"fuente": "panel", "texto": "$ ls\nfoo"})
        self.assertEqual((panel["quien"], panel["texto"]), ("panel", "$ ls\nfoo"))
        self.assertEqual(m.aplanar({}), [])


class LaRutaRemota(ConAgente):
    """`GET /api/conversacion?maquina=…`: la conversación de un hilo del laptop, por la puerta."""

    def setUp(self):
        super().setUp()
        from telar.config import Enlace
        from telar import espejo

        self.config = mod_config.Config(raiz=self.base, estado=self.base / "estado",
                                        enlaces=(Enlace(nombre="laptop", destino="nico@mac"),))
        espejo.guardar(self.config, "macbook", json.dumps({"version": 1, "hilos": [
            {"nombre": "Lumbre", "atencion": "espera", "vivo": True}]}))
        web._remotas.clear()
        self.addCleanup(web._remotas.clear)

    HISTORIA = {"ok": True, "verbo": "leer", "historia": {
        "hilo": "Lumbre", "fuente": "conversacion", "conversacion": "abc", "total_turnos": 7, "recortado": False,
        "turnos": [[{"quien": "usuario", "hora": "2026-10-01T10:00:00Z", "texto": "hola"},
                    {"quien": "herramienta", "hora": "2026-10-01T10:00:01Z", "texto": "Bash · ls"},
                    {"quien": "agente", "hora": "2026-10-01T10:00:02Z", "texto": "listo"}]]}}

    def pedir(self, consulta, respuesta=None):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), web.manejador(True, self.config))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        try:
            with mock.patch.object(web.enlace, "llamar", return_value=respuesta or self.HISTORIA) as llamar:
                with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/conversacion?{consulta}") as r:
                    return r.status, json.loads(r.read()), llamar
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read()), None

    def test_la_forma_es_la_de_un_hilo_de_aqui(self):
        codigo, cuerpo, llamar = self.pedir("maquina=macbook&hilo=Lumbre")
        self.assertEqual(codigo, 200)
        self.assertEqual([x["texto"] for x in cuerpo["mensajes"]], ["hola", "Bash · ls", "listo"])
        self.assertEqual((cuerpo["desde"], cuerpo["hasta"], cuerpo["total"]), (0, 3, 3))
        self.assertEqual(cuerpo["hilo"], {"nombre": "Lumbre", "atencion": "espera", "vivo": True, "en_linea": True})
        self.assertEqual((cuerpo["turnos"], cuerpo["total_turnos"], cuerpo["remota"]), (1, 7, "macbook"))
        self.assertEqual(llamar.call_args.args[1:3], ("leer", ["Lumbre", "10"]))

    def test_los_turnos_pedidos_se_acotan(self):
        _, _, llamar = self.pedir("maquina=macbook&hilo=Lumbre&turnos=500")
        self.assertEqual(llamar.call_args.args[2], ["Lumbre", "50"])

    def test_lo_que_la_otra_maquina_no_entrega_llega_con_su_motivo(self):
        for motivo in ("esta puerta no hace «leer»", "no hay un hilo que se pueda leer con el nombre «Lumbre»",
                       "macbook no responde: timed out"):
            web._remotas.clear()
            codigo, cuerpo, _ = self.pedir("maquina=macbook&hilo=Lumbre", {"ok": False, "error": motivo})
            self.assertEqual((codigo, cuerpo["error"]), (409, motivo))

    def test_el_panel_llega_como_un_solo_mensaje(self):
        r = {"ok": True, "historia": {"hilo": "K", "fuente": "panel", "texto": "$ ls\\nfoo", "recortado": False}}
        _, cuerpo, _ = self.pedir("maquina=macbook&hilo=Lumbre", r)
        self.assertEqual((cuerpo["fuente"], cuerpo["mensajes"][0]["quien"]), ("panel", "panel"))

    def test_una_maquina_sin_enlace_o_un_numero_malo(self):
        from telar.config import Enlace

        self.config = mod_config.Config(raiz=self.base, estado=self.base / "estado", enlaces=(Enlace("a", "x@a"), Enlace("b", "x@b")))
        self.assertEqual(self.pedir("maquina=otra&hilo=Lumbre")[0], 404)
        self.assertEqual(self.pedir("maquina=a&hilo=Lumbre&turnos=abc")[0], 400)

    def test_no_se_guarda_nada_de_lo_conversado_en_el_servidor(self):
        self.pedir("maquina=macbook&hilo=Lumbre")
        guardado = [p for p in self.base.rglob("*") if p.is_file() and "hola" in p.read_text(errors="ignore")]
        self.assertEqual([p for p in guardado if "estado" in str(p)], [])
