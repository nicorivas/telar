"""Lo que el agente le pregunta a la persona con opciones (AskUserQuestion): cómo se lee en la conversación, cuándo
espera respuesta, y cómo se le deja la respuesta al mod para que la entregue al diálogo."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import casilla
from telar import historia as h
from telar.agente.claude_code import mensajes_del_mod

PREGUNTAS = [
    {"question": "¿Qué paleta?", "header": "Colores", "multiSelect": False,
     "options": [{"label": "Oscura", "description": "fondo oscuro", "preview": "<p>x</p>"},
                 {"label": "Clara", "description": "fondo claro"}]},
    {"question": "¿Qué secciones?", "header": "Secciones", "multiSelect": True,
     "options": [{"label": "Novedades", "description": ""}, {"label": "Mapa", "description": "cómo llegar"}]},
]


class Casilla(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = SimpleNamespace(estado=Path(self.tmp.name), agente=SimpleNamespace(nombre="claude-code"))
        self.carpeta = casilla.carpeta(self.config, "Faro")
        (self.carpeta / "mod").mkdir(parents=True)
        (self.carpeta / casilla.MOD).write_text("1")

    def abrir(self, id="p1", estado="abierta"):
        (self.carpeta / "mod" / "pregunta.json").write_text(json.dumps({"id": id, "estado": estado, "preguntas": PREGUNTAS}))


class DelRegistro(Prueba):
    """El registro de Claude Code (.jsonl): la pregunta en su tool_use; lo respondido, en el resultado."""

    def leer(self, lineas):
        from telar import config as mod_config
        from telar.agente.claude_code import ClaudeCode

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        (base / "projects" / "-x").mkdir(parents=True)
        (base / "projects" / "-x" / "abc.jsonl").write_text("\n".join(json.dumps(x) for x in lineas), encoding="utf-8")
        os.environ["CLAUDE_CONFIG_DIR"] = str(base)
        self.addCleanup(os.environ.pop, "CLAUDE_CONFIG_DIR", None)
        return ClaudeCode(mod_config.desde_dict({})).mensajes("abc")

    def pregunta(self, id="p1"):
        return {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": id, "name": "AskUserQuestion", "input": {"questions": PREGUNTAS}}]}}

    def test_sin_resultado_espera_con_sus_opciones_y_sin_las_vistas_previas(self):
        (m,) = self.leer([self.pregunta()])
        self.assertEqual(m["texto"], "AskUserQuestion · ¿Qué paleta?")
        p = m["pregunta"]
        self.assertEqual((p["id"], p["estado"]), ("p1", "pendiente"))
        self.assertEqual(p["preguntas"][0], {"pregunta": "¿Qué paleta?", "encabezado": "Colores", "varias": False, "opciones": [
            {"etiqueta": "Oscura", "descripcion": "fondo oscuro"}, {"etiqueta": "Clara", "descripcion": "fondo claro"}]})
        self.assertTrue(p["preguntas"][1]["varias"])

    def test_contestada_trae_lo_respondido(self):
        respuestas = {"¿Qué paleta?": "Clara", "¿Qué secciones?": "Novedades, una vitrina"}
        (m,) = self.leer([self.pregunta(), {"type": "user", "toolUseResult": {"questions": PREGUNTAS, "answers": respuestas},
                                            "message": {"content": [{"type": "tool_result", "tool_use_id": "p1", "content": "ok"}]}}])
        self.assertEqual((m["pregunta"]["estado"], m["pregunta"]["respuestas"]), ("respondida", respuestas))

    def test_cerrada_con_escape_queda_sin_contestar(self):
        (m,) = self.leer([self.pregunta(), {"type": "user", "toolUseResult": "Error: no", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "p1", "is_error": True, "content": "The user doesn't want to proceed"}]}}])
        self.assertEqual(m["pregunta"]["estado"], "cancelada")
        self.assertNotIn("respuestas", m["pregunta"])


class DelMod(Prueba):
    """Lo que deja el mod en mod/conversacion.json: la pregunta ya resumida, con su estado."""

    def test_la_misma_forma_que_del_registro(self):
        mensajes = mensajes_del_mod({"mensajes": [{"role": "assistant", "text": "", "tools": [
            {"tool": "AskUserQuestion", "input": {}, "pregunta": {"id": "p1", "estado": "respondida", "questions": PREGUNTAS,
                                                                  "answers": {"¿Qué paleta?": "Oscura"}}},
            {"tool": "Bash", "input": {"command": "ls"}}]}]})
        self.assertEqual([x["texto"] for x in mensajes], ["AskUserQuestion · ¿Qué paleta?", "Bash · ls"])
        p = mensajes[0]["pregunta"]
        self.assertEqual((p["estado"], p["respuestas"], p["preguntas"][0]["opciones"][0]["etiqueta"]),
                         ("respondida", {"¿Qué paleta?": "Oscura"}, "Oscura"))
        self.assertNotIn("pregunta", mensajes[1])

    def test_un_estado_desconocido_cuenta_como_pendiente(self):
        (m,) = mensajes_del_mod({"mensajes": [{"role": "assistant", "text": "", "tools": [
            {"tool": "AskUserQuestion", "input": {}, "pregunta": {"id": "p1", "estado": "rara", "questions": PREGUNTAS}}]}]})
        self.assertEqual(m["pregunta"]["estado"], "pendiente")


def con_pregunta(id="p1", estado="pendiente"):
    return {"quien": "herramienta", "texto": "AskUserQuestion", "pregunta": {"id": id, "estado": estado, "preguntas": []}}


class CuandoEspera(Casilla):
    """historia: una pregunta espera solo si es lo último y su hilo vive; y es contestable si el mod la tiene abierta."""

    def preguntas(self, mensajes, vivo=True):
        tel = SimpleNamespace(mux=object(), vivo=lambda hilo: vivo)
        salida = h._con_preguntas(self.config, tel, SimpleNamespace(nombre="Faro"), mensajes)
        return [m["pregunta"] for m in salida if m.get("pregunta")]

    def test_la_ultima_espera_y_es_contestable_si_el_mod_la_tiene_abierta(self):
        self.abrir("p1")
        (p,) = self.preguntas([{"quien": "usuario", "texto": "a"}, con_pregunta("p1")])
        self.assertEqual((p["estado"], p["contestable"]), ("pendiente", True))

    def test_otra_abierta_o_el_mod_muerto_no_es_contestable(self):
        self.abrir("otra")
        self.assertFalse(self.preguntas([con_pregunta("p1")])[0]["contestable"])
        self.abrir("p1")
        (self.carpeta / casilla.MOD).unlink()
        self.assertFalse(self.preguntas([con_pregunta("p1")])[0]["contestable"])

    def test_si_alguien_hablo_despues_o_el_hilo_se_cerro_quedo_sin_contestar(self):
        self.abrir("p1")
        despues = self.preguntas([con_pregunta("p1"), {"quien": "herramienta", "texto": "Bash"}, {"quien": "agente", "texto": "sigo"}])
        self.assertEqual(despues[0]["estado"], "cancelada")
        self.assertEqual(self.preguntas([con_pregunta("p1")], vivo=False)[0]["estado"], "cancelada")

    def test_no_toca_lo_leido(self):
        original = [con_pregunta("p1")]
        self.preguntas(original, vivo=False)
        self.assertEqual(original[0]["pregunta"]["estado"], "pendiente")

    def test_como_texto_dice_lo_respondido(self):
        p = {"quien": "herramienta", "texto": "AskUserQuestion · ¿Qué paleta?", "hora": "",
             "pregunta": {"id": "p1", "estado": "respondida", "preguntas": [], "respuestas": {"¿Qué paleta?": "Clara"}}}
        t = h.como_texto({"hilo": "Faro", "fuente": "conversacion", "conversacion": "abc", "total_turnos": 1, "turnos": [[p]]})
        self.assertIn("  › AskUserQuestion · ¿Qué paleta?\n    → Clara", t)


class Responder(Casilla):
    """La respuesta va a mod/respuesta.json, y el mod la toma: mod/pregunta.json dice que se cerró y por dónde."""

    RESPUESTAS = {"¿Qué paleta?": "Clara", "¿Qué secciones?": "Novedades, Mapa"}

    def mod_que_la_toma(self, por="afuera"):
        """Como el mod: cuando aparece la respuesta de esta pregunta, cierra el diálogo."""
        def mirar():
            ruta = self.carpeta / "mod" / "respuesta.json"
            for _ in range(100):
                if ruta.exists():
                    d = json.loads(ruta.read_text())
                    (self.carpeta / "mod" / "pregunta.json").write_text(json.dumps({"id": d["id"], "estado": "cerrada", "por": por}))
                    return
                time.sleep(0.02)
        hilo = threading.Thread(target=mirar)
        hilo.start()
        self.addCleanup(hilo.join)

    def test_el_mod_la_toma(self):
        self.abrir("p1")
        self.mod_que_la_toma()
        r = h.responder(self.config, "Faro", "p1", self.RESPUESTAS, esperar=3)
        self.assertEqual(r, {"ok": True, "tomada": True, "por": "afuera"})
        self.assertFalse((self.carpeta / "mod" / "respuesta.json").exists())  # tomada, se limpia

    def test_lo_que_se_deja_es_lo_que_se_respondio_sin_espacios_de_mas(self):
        self.abrir("p1")
        r = h.responder(self.config, "Faro", "p1", {"¿Qué paleta?": " Clara ", "¿Qué secciones?": "Mapa"}, esperar=0)
        self.assertEqual(r["tomada"], False)  # nadie la tomó todavía: queda en camino
        d = json.loads((self.carpeta / "mod" / "respuesta.json").read_text())
        self.assertEqual((d["id"], d["respuestas"]), ("p1", {"¿Qué paleta?": "Clara", "¿Qué secciones?": "Mapa"}))

    def test_si_antes_la_contestaron_en_la_terminal_lo_dice(self):
        self.abrir("p1")
        self.mod_que_la_toma(por="terminal")
        self.assertEqual(h.responder(self.config, "Faro", "p1", self.RESPUESTAS, esperar=3)["por"], "terminal")

    def test_una_pregunta_que_ya_no_esta_abierta(self):
        for id, estado in (("p1", "cerrada"), ("otra", "abierta")):
            with self.subTest(id=id, estado=estado):
                self.abrir(id, estado)
                with self.assertRaises(h.ErrorDeRespuesta) as e:
                    h.responder(self.config, "Faro", "p1", self.RESPUESTAS, esperar=0)
                self.assertEqual(e.exception.codigo, 409)

    def test_con_el_mod_muerto_no_se_deja_nada(self):
        self.abrir("p1")
        (self.carpeta / casilla.MOD).unlink()
        with self.assertRaises(h.ErrorDeRespuesta):
            h.responder(self.config, "Faro", "p1", self.RESPUESTAS, esperar=0)
        self.assertFalse((self.carpeta / "mod" / "respuesta.json").exists())

    def test_una_respuesta_que_no_sirve(self):
        self.abrir("p1")
        for malas in ({"¿Qué paleta?": "Clara"}, {**self.RESPUESTAS, "¿Otra?": "x"}, {**self.RESPUESTAS, "¿Qué paleta?": "  "}):
            with self.subTest(malas=malas), self.assertRaises(h.ErrorDeRespuesta) as e:
                h.responder(self.config, "Faro", "p1", malas, esperar=0)
            self.assertEqual(e.exception.codigo, 422)
        self.assertFalse((self.carpeta / "mod" / "respuesta.json").exists())


class DeOtraMaquina(Prueba):
    """A un hilo de otra máquina se le contesta por el bus: su nodo deja la respuesta para su mod."""

    def setUp(self):
        super().setUp()
        from telar import config as mod_config

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                   bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="laptop"))
        self.ctx = SimpleNamespace(config=config)

    def test_es_un_pedido_al_nodo_y_su_error_llega_con_su_codigo(self):
        from unittest import mock

        from telar import bus as mod_bus
        from telar.servicios import ErrorDeServicio
        from telar.servicios import historias

        respuestas = {"¿Qué paleta?": "Clara"}
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "tomada": True, "por": "afuera"}) as pedir:
            r = historias.responder(self.ctx, "Faro", "p1", respuestas, maquina="servidor")
        self.assertEqual(pedir.call_args[0][1:4], ("servidor", "responder", {"hilo": "Faro", "id": "p1", "respuestas": respuestas}))
        self.assertTrue(r.tomada)
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "codigo": 409, "error": "ya no está abierta"}), \
                self.assertRaises(ErrorDeServicio) as e:
            historias.responder(self.ctx, "Faro", "p1", respuestas, maquina="servidor")
        self.assertEqual(e.exception.codigo, 409)

    def test_el_nodo_la_deja_para_su_mod_y_no_contesta_lo_que_no_se_lee(self):
        import asyncio
        from unittest import mock

        from telar.ordenes import nodo

        n = nodo.Nodo.__new__(nodo.Nodo)
        n.ctx, n.config = self.ctx, SimpleNamespace(bus=SimpleNamespace(no_leer=("diario",)), puerta=SimpleNamespace(no_leer=()))
        tel = SimpleNamespace(por_nombre=lambda x: SimpleNamespace(nombre=x) if x in ("Faro", "Diario") else None,
                              estado=SimpleNamespace(vinculos=lambda: {}))

        def pedir(datos):
            respondido = []
            m = SimpleNamespace(data=json.dumps(datos).encode(), respond=lambda b: _anotar(respondido, b))
            asyncio.run(n._responder_pregunta(m))
            return json.loads(respondido[0])

        async def _anotar(lista, b):
            lista.append(b)

        with mock.patch.object(nodo._comun, "tejer", return_value=tel), \
                mock.patch.object(h, "responder", return_value={"ok": True, "tomada": True, "por": "afuera"}) as responder:
            self.assertEqual(pedir({"hilo": "Faro", "id": "p1", "respuestas": {"a": "b"}})["tomada"], True)
            self.assertEqual(responder.call_args[0][1:], ("Faro", "p1", {"a": "b"}))
            self.assertEqual(pedir({"hilo": "Diario", "id": "p1", "respuestas": {}})["codigo"], 404)
            self.assertEqual(responder.call_count, 1)
        with mock.patch.object(nodo._comun, "tejer", return_value=tel), \
                mock.patch.object(h, "responder", side_effect=h.ErrorDeRespuesta("ya no está abierta")):
            self.assertEqual(pedir({"hilo": "Faro", "id": "p1", "respuestas": {}}), {"ok": False, "codigo": 409, "error": "ya no está abierta"})


try:
    from fastapi.testclient import TestClient

    from telar import api
except ImportError:  # sin el extra «serve»
    api = None


class LaRuta(Prueba):
    def test_post_responder_pasa_lo_pedido_y_su_error_con_su_codigo(self):
        import unittest
        from unittest import mock

        if api is None:
            raise unittest.SkipTest("sin fastapi")
        from telar.servicios import ErrorDeServicio
        from telar.servicios import historias

        cuerpo = {"hilo": "Faro", "id": "p1", "respuestas": {"¿Qué paleta?": "Clara"}, "maquina": "servidor"}
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()), \
                mock.patch.object(api.servicio_historias, "responder", return_value=historias.Respondido(ok=True, tomada=True, por="afuera")) as r:
            res = TestClient(api.app).post("/hilos/responder", json=cuerpo)
        self.assertEqual((res.status_code, res.json()), (200, {"ok": True, "tomada": True, "por": "afuera"}))
        self.assertEqual(r.call_args.args[1:], ("Faro", "p1", {"¿Qué paleta?": "Clara"}))
        self.assertEqual(r.call_args.kwargs, {"maquina": "servidor"})
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()), \
                mock.patch.object(api.servicio_historias, "responder", side_effect=ErrorDeServicio("ya no está abierta", 409)):
            res = TestClient(api.app).post("/hilos/responder", json=cuerpo)
        self.assertEqual(res.status_code, 409)
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            self.assertEqual(TestClient(api.app).post("/hilos/responder", json={"hilo": "Faro"}).status_code, 422)
