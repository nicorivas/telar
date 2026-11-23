"""Descartar un mensaje retenido (`telar mensaje --descartar <id>`, `POST /mensajes/{id}/descartar`): sale de los
retenidos sin entregarse, queda en el registro como descartado (quién y cuándo) y a quien lo mandó le llega un aviso
que no lo despierta. Sin bus real: el registro es una lista que crece con lo que se anota, y `telar.bus.enviar` deja
el mensaje en la casilla de aquí, como lo haría el nodo."""

from __future__ import annotations

import asyncio
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar import casilla
from telar import config as mod_config
from telar import encargo
from telar import objetos
from telar.ordenes import mensaje
from telar.servicios import ErrorDeServicio
from telar.servicios import mensajes as servicio


def retenido(mid="m1", de="Molino", para="Faro", texto="¿seguimos con la vitrina?", **mas):
    return {"id": mid, "de": de, "para": para, "tipo": "mensaje", "texto": texto, "persona": "ana", "saltos": 7,
            "creado": "2026-11-18T10:00:00-03:00", "estado": "retenido", "motivo": "cadena de 7 mensajes", **mas}


class ConRegistro(Prueba):
    """Un registro de mentira: `registro` y `registro_al_dia` lo leen, `anotar` le suma la copia, y `enviar` deja el
    mensaje en la casilla de aquí (y su copia, en el registro)."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        self.config = mod_config.Config(raiz=self.raiz, estado=self.raiz / "estado",
                                        bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="laptop"))
        self.ctx = SimpleNamespace(config=self.config)
        self.lista: list[dict] = [retenido(), retenido("m2", de="Viento", texto="otro")]
        self.enviados: list[dict] = []

        def enviar(config, para, texto, *, de, tipo="mensaje", quien="", saltos=0, mid="", retener="", modo="pedido",
                   extra=None):
            m = mod_bus.mensaje(texto, de=de, para=para, tipo=tipo, mid=mid, persona="ana", saltos=saltos, modo=modo,
                                extra=extra)
            self.enviados.append(m)
            casilla.dejar(config, para, m)
            self.lista.append({**m, "estado": "enviado"})
            return {**m, "secuencia": len(self.lista), "duplicado": False}

        for nombre, falso in (("registro", lambda config, n=100: list(self.lista)[-n:]),
                              ("registro_al_dia", lambda config, n=100: list(self.lista)[-n:]),
                              ("anotar", lambda config, copia: self.lista.append(dict(copia))),
                              ("enviar", enviar)):
            p = mock.patch.object(mod_bus, nombre, side_effect=falso)
            p.start()
            self.addCleanup(p.stop)


class Descartar(ConRegistro):
    def test_descartar_uno_lo_deja_anotado_y_no_lo_entrega(self):
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Telar"}):
            r = mensaje.descartar(self.ctx, "m1")
        copia = self.lista[2]
        self.assertEqual((copia["id"], copia["estado"], copia["para"], copia["de"]), ("m1", "descartado", "Faro", "Molino"))
        # quién y cuándo: el hilo que lo corrió (o lo que diga quien llama), y la hora
        self.assertEqual(copia["descartado_por"], "Telar")
        self.assertLess(abs((datetime.now().astimezone() - datetime.fromisoformat(copia["descartado"])).total_seconds()), 60)
        self.assertEqual(copia["motivo"], "cadena de 7 mensajes")  # por qué se había retenido: sigue para rastrearlo
        self.assertEqual((r["estado"], r["id"]), ("descartado", "m1"))
        # a Faro no le llegó nada: solo el aviso a Molino salió
        self.assertEqual(casilla.pendientes(self.config, "Faro"), [])
        self.assertEqual([m["para"] for m in self.enviados], ["Molino"])
        # quien lo descarta se puede decir (la página: la persona en su máquina)
        mensaje.descartar(self.ctx, "m2", quien="ana@laptop")
        (copia,) = [m for m in self.lista if m["id"] == "m2" and m["estado"] == "descartado"]
        self.assertEqual(copia["descartado_por"], "ana@laptop")

    def test_al_que_lo_mando_le_llega_un_aviso_que_no_lo_despierta(self):
        r = mensaje.descartar(self.ctx, "m1")
        (aviso,) = casilla.pendientes(self.config, "Molino")
        self.assertEqual(r["aviso"], aviso["id"])
        self.assertEqual((aviso["modo"], aviso["de"], aviso["tipo"], aviso["saltos"]), ("aviso", "telar", "mensaje", 0))
        self.assertEqual(casilla.despiertan(self.config, "Molino"), [], "un aviso no lo despierta")
        self.assertTrue(aviso["texto"].startswith("tu mensaje a «Faro» (m1) no se entregó: Ana lo descartó."), aviso["texto"])
        self.assertIn("Decía: ¿seguimos con la vitrina?", aviso["texto"])
        # no alarga el turno en que está (solo avisos: esperan al próximo); entra con el próximo, como aviso de telar, y
        # no corta su cadena: el freno sigue donde estaba
        casilla.anotar_cadena(self.config, "Molino", casilla.TOPE_SALTOS)
        self.assertEqual(casilla.para_gancho(self.config, "Molino", "Stop"), "")
        d = json.loads(casilla.para_gancho(self.config, "Molino", "UserPromptSubmit"))
        self.assertIn("[aviso de telar", d["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(casilla.cadena(self.config, "Molino"), casilla.TOPE_SALTOS)

    def test_un_texto_largo_va_cortado_en_el_aviso(self):
        self.lista.append(retenido("m3", texto="palabra " * 100))
        mensaje.descartar(self.ctx, "m3")
        (aviso,) = casilla.pendientes(self.config, "Molino")
        self.assertTrue(aviso["texto"].endswith("…"))
        self.assertLess(len(aviso["texto"].split("Decía: ", 1)[1]), 201)

    def test_ya_no_esta_en_esperas_ni_entre_los_retenidos(self):
        self.assertEqual([e.direccion for e in objetos.Mensaje().esperando(self.ctx)], ["mensaje:m1", "mensaje:m2"])
        mensaje.descartar(self.ctx, "m1")
        self.assertEqual([e.direccion for e in objetos.Mensaje().esperando(self.ctx)], ["mensaje:m2"])
        self.assertEqual([m["id"] for m in servicio.registro(self.ctx, retenidos=True).mensajes], ["m2"])
        # el objeto sigue: descartado, con quién y cuándo, y el motivo por el que se retuvo
        o = objetos.ver(self.ctx, "mensaje:m1")
        self.assertEqual(o.estado, "descartado")
        self.assertIn("descartado_por", o.campos)
        self.assertEqual(o.campos["motivo"], "cadena de 7 mensajes")
        self.assertNotIn("soltar", o.campos)
        # mientras está retenido, dice cómo soltarlo y cómo descartarlo
        o = objetos.ver(self.ctx, "mensaje:m2")
        self.assertEqual((o.campos["soltar"], o.campos["descartar"]),
                         ("telar mensaje --soltar m2", "telar mensaje --descartar m2"))

    def test_uno_que_no_existe_o_ya_se_resolvio_da_error(self):
        for mid in ("nadie", "m1"):
            if mid == "m1":
                mensaje.soltar(self.ctx, "m1")
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.descartar(self.ctx, mid)
            self.assertEqual(e.exception.codigo, 404, mid)
            self.assertIn("¿ya se soltó o se descartó?", str(e.exception))
        # descartado una vez, no se descarta ni se suelta otra
        servicio.descartar(self.ctx, "m2")
        avisos = len(self.enviados)
        for hacer in (servicio.descartar, servicio.soltar):
            with self.assertRaises(ErrorDeServicio) as e:
                hacer(self.ctx, "m2")
            self.assertEqual(e.exception.codigo, 404)
        self.assertEqual(len(self.enviados), avisos, "no sale un segundo aviso ni el mensaje")

    def test_si_el_bus_no_anota_no_se_avisa_y_es_502(self):
        with mock.patch.object(mod_bus, "anotar", side_effect=mod_bus.ErrorDeBus("el bus no responde")):
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.descartar(self.ctx, "m1")
        self.assertEqual(e.exception.codigo, 502)
        self.assertEqual(self.enviados, [])
        self.assertEqual([m["id"] for m in mensaje.retenidos(self.lista)], ["m1", "m2"])

    def test_si_el_aviso_no_sale_queda_descartado_igual(self):
        with mock.patch.object(mod_bus, "enviar", side_effect=mod_bus.ErrorDeBus("sin red")):
            r = mensaje.descartar(self.ctx, "m1")
        self.assertEqual(r["sin_aviso"], "sin red")
        self.assertNotIn("aviso", r)
        self.assertEqual([m["id"] for m in mensaje.retenidos(self.lista)], ["m2"])

    def test_un_encargo_retenido_queda_cancelado_en_la_nota(self):
        eid = "e-1a2b3c4d"
        encargo.anotar_enviado(self.config, eid, para="Faro", maquina="laptop", texto="revisa", de="Molino",
                               retenido="cadena de 7 mensajes")
        self.lista.append(retenido("m3", modo="encargo", encargo=eid, responder_a="Molino"))
        mensaje.descartar(self.ctx, "m3", quien="ana@laptop")
        nota = encargo.enviado(self.config, eid)
        self.assertNotIn("retenido", nota)
        self.assertEqual(nota["descartado_por"], "ana@laptop")
        o = objetos.ver(self.ctx, f"encargo:{eid}")
        self.assertEqual(o.estado, "cancelado")
        self.assertEqual(o.campos["descartado_por"], "ana@laptop")
        self.assertNotIn("en_camino", o.campos)
        self.assertNotIn("retenido", o.campos)


class LaOrden(ConRegistro):
    def _cli(self, *argv):
        from telar import cli

        salida, error = io.StringIO(), io.StringIO()
        with mock.patch.object(cli, "cargar_config", return_value=self.config), redirect_stdout(salida), \
                redirect_stderr(error):
            codigo = cli.main(list(argv))
        return codigo, salida.getvalue(), error.getvalue()

    def test_descartar_por_la_cli(self):
        codigo, salida, _ = self._cli("mensaje", "--descartar", "m1")
        self.assertEqual(codigo, 0)
        self.assertIn("«Faro»: descartado, no se entregó · id m1", salida)
        self.assertIn("a «Molino» le llegó un aviso (no lo despierta)", salida)
        codigo, salida, _ = self._cli("mensaje", "--descartar", "m2", "--json")
        self.assertEqual(codigo, 0)
        r = json.loads(salida)
        self.assertEqual((r["id"], r["estado"], r["de"]), ("m2", "descartado", "Viento"))
        self.assertTrue(r["aviso"])
        codigo, _, error = self._cli("mensaje", "--descartar", "m1")
        self.assertNotEqual(codigo, 0)
        self.assertIn("no hay un mensaje retenido con id m1", error)
        # el registro marca el descartado
        codigo, salida, _ = self._cli("mensaje", "--registro", "10")
        self.assertIn("✕ Molino → Faro", salida)

    def test_la_ayuda_lo_ofrece(self):
        codigo, salida, error = self._cli("mensaje", "--help")
        self.assertEqual(codigo, 0)
        self.assertIn("--descartar ID", salida + error)
        self.assertIn("telar mensaje --descartar <id>", salida + error)


class ElBus(Prueba):
    """`telar.bus.anotar`: la copia va al registro de la persona, sin pasar por ninguna casilla, con un id por estado."""

    def test_la_copia_va_al_registro_con_su_id(self):
        publicados = []

        class Js:
            async def publish(self, tema, datos, headers=None, timeout=None):
                publicados.append((tema, json.loads(datos), headers))

        class Nc:
            def jetstream(self):
                return Js()

            async def close(self):
                pass

        async def conectar(config):
            return Nc()

        config = mod_config.Config(raiz=Path(tempfile.gettempdir()),
                                   bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="laptop"))
        with mock.patch.object(mod_bus, "conectar", side_effect=conectar), \
                mock.patch.object(mod_bus, "asegurar", mock.AsyncMock()):
            mod_bus.anotar(config, {**retenido(), "estado": "descartado"})
        ((tema, copia, headers),) = publicados
        self.assertEqual(tema, "registro.ana")
        self.assertEqual(copia["estado"], "descartado")
        self.assertEqual(headers, {"Nats-Msg-Id": "m1.descartado"})

    def test_sin_bus_no_se_anota(self):
        config = mod_config.Config(raiz=Path(tempfile.gettempdir()))
        with self.assertRaises(mod_bus.ErrorDeBus):
            mod_bus.anotar(config, {**retenido(), "estado": "descartado"})


@unittest.skipUnless(HAY_FASTAPI, "sin fastapi")
class LaApi(ConRegistro):
    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient

        from telar import api

        p = mock.patch.object(api, "_refrescar", mock.AsyncMock())
        p.start()
        self.addCleanup(p.stop)
        api.app.dependency_overrides[api.contexto] = lambda: self.ctx
        self.addCleanup(api.app.dependency_overrides.clear)
        self.c = TestClient(api.app)

    def test_post_descartar(self):
        r = self.c.post("/mensajes/m1/descartar")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["estado"], r.json()["descartado_por"]), ("descartado", "ana@laptop"))
        self.assertTrue(r.json()["aviso"])
        self.assertEqual(self.c.post("/mensajes/m1/descartar").status_code, 404)
        self.assertEqual(self.c.post("/mensajes/nadie/descartar").status_code, 404)
        with mock.patch.object(mod_bus, "anotar", side_effect=mod_bus.ErrorDeBus("el bus no responde")):
            self.assertEqual(self.c.post("/mensajes/m2/descartar").status_code, 502)
        self.assertIn("/mensajes/{mid}/descartar", self.c.get("/openapi.json").json()["paths"])


if __name__ == "__main__":
    unittest.main()
