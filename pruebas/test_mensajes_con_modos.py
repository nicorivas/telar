"""Mensajes con modos y el Encargo (docs/propuestas/mensajes-con-modos.md): `telar mensaje --modo aviso|pedido|
encargo|consulta`, la casilla que deja esperar a un aviso sin despertar, y el Encargo como objeto
(`encargo:e-…`, telar.encargo), con sus acciones. Sin bus real: `telar.bus.enviar` es un falso que deja el
mensaje en la casilla de aquí, como lo haría el nodo."""

from __future__ import annotations

import io
import json
import os
import tempfile
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


class ConEstado(Prueba):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        self.config = mod_config.Config(raiz=self.raiz, estado=self.raiz / "estado",
                                        bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="laptop"))
        self.ctx = SimpleNamespace(config=self.config)


class ConBusFalso(ConEstado):
    """`telar.bus.enviar` deja el mensaje en la casilla de aquí (lo que haría el nodo al recogerlo) y lo anota."""

    def setUp(self):
        super().setUp()
        self.enviados: list[dict] = []
        self.llamadas: list[dict] = []

        def enviar(config, para, texto, *, de, tipo="mensaje", quien="", saltos=0, mid="", retener="", **kw):
            self.llamadas.append(kw)
            m = mod_bus.mensaje(texto, de=de, para=para, tipo=tipo, mid=mid, persona="ana", saltos=saltos, **kw)
            self.enviados.append(m)
            if retener:
                return {**m, "estado": "retenido", "motivo": retener}
            casilla.dejar(config, para, m)
            return {**m, "secuencia": len(self.enviados), "duplicado": False}

        p = mock.patch.object(mod_bus, "enviar", side_effect=enviar)
        p.start()
        self.addCleanup(p.stop)
        # sin multiplexor: el nombre del hilo es el que se escribe
        p = mock.patch.object(mensaje, "_por_nombre", side_effect=lambda ctx, para: para)
        p.start()
        self.addCleanup(p.stop)
        # los hilos viven en el servidor, según el bus
        p = mock.patch.object(mod_bus, "maquina_de", return_value="servidor")
        p.start()
        self.addCleanup(p.stop)


class ElMensaje(Prueba):
    def test_un_pedido_queda_como_siempre(self):
        m = mod_bus.mensaje("hola", de="Ana", para="Faro", mid="m1")
        self.assertNotIn("modo", m)
        self.assertEqual(set(m), {"id", "de", "para", "tipo", "texto", "persona", "saltos", "creado"})

    def test_otro_modo_va_en_el_mensaje_con_lo_suyo(self):
        m = mod_bus.mensaje("hola", de="Ana", para="Faro", modo="encargo",
                            extra={"encargo": "e-1a2b3c4d", "plazo": "", "texto": "no pisa", "responder_a": "Molino"})
        self.assertEqual((m["modo"], m["encargo"], m["responder_a"], m["texto"]), ("encargo", "e-1a2b3c4d", "Molino", "hola"))
        self.assertNotIn("plazo", m)  # lo vacío no viaja

    def test_sin_modo_o_con_uno_desconocido_es_un_pedido(self):
        self.assertEqual(casilla.modo_de({}), "pedido")
        self.assertEqual(casilla.modo_de({"modo": "grito"}), "pedido")
        self.assertTrue(casilla.despierta({"modo": "encargo"}))
        self.assertFalse(casilla.despierta({"modo": "aviso"}))


class LaCasilla(ConEstado):
    def test_un_aviso_espera_aparte_y_no_despierta(self):
        self.assertTrue(casilla.dejar(self.config, "Faro", {"id": "a1", "de": "Molino", "texto": "ya está", "modo": "aviso"}))
        self.assertTrue((casilla.carpeta(self.config, "Faro") / casilla.AVISOS / "a1.json").exists())
        self.assertEqual([m["id"] for m in casilla.pendientes(self.config, "Faro")], ["a1"])
        self.assertEqual(casilla.despiertan(self.config, "Faro"), [])
        self.assertFalse(casilla.dejar(self.config, "Faro", {"id": "a1", "texto": "ya está", "modo": "aviso"}))
        # el gancho Stop no alarga el turno por un aviso solo
        self.assertEqual(casilla.para_gancho(self.config, "Faro", "Stop"), "")
        self.assertEqual(len(casilla.pendientes(self.config, "Faro")), 1)

    def test_el_aviso_entra_con_el_turno_siguiente(self):
        casilla.dejar(self.config, "Faro", {"id": "a1", "de": "Molino", "texto": "ya está", "modo": "aviso"})
        salida = json.loads(casilla.para_gancho(self.config, "Faro", "UserPromptSubmit", prompt="sigue"))
        texto = salida["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[aviso de Molino", texto)
        self.assertIn("no pide nada", texto)
        self.assertEqual(casilla.pendientes(self.config, "Faro"), [])
        self.assertTrue((casilla.carpeta(self.config, "Faro") / "entregados" / "a1.json").exists())
        self.assertFalse(casilla.dejar(self.config, "Faro", {"id": "a1", "texto": "otra vez", "modo": "aviso"}))

    def test_con_un_pedido_al_lado_stop_entrega_los_dos_en_orden(self):
        casilla.dejar(self.config, "Faro", {"id": "20261022100000-a", "de": "Molino", "texto": "primero", "modo": "aviso"})
        casilla.dejar(self.config, "Faro", {"id": "20261022100500-b", "de": "Molino", "texto": "segundo"})
        razon = json.loads(casilla.para_gancho(self.config, "Faro", "Stop"))["reason"]
        self.assertLess(razon.index("primero"), razon.index("segundo"))
        self.assertEqual(casilla.pendientes(self.config, "Faro"), [])

    def test_la_linea_que_despierta_habla_de_lo_que_despierta(self):
        casilla.dejar(self.config, "Faro", {"id": "1-a", "de": "Molino", "texto": "un aviso viejo", "modo": "aviso"})
        casilla.dejar(self.config, "Faro", {"id": "2-b", "de": "Molino", "texto": "esto sí", "modo": "encargo",
                                            "encargo": "e-00000001"})
        linea = casilla.aviso(self.config, "Faro")
        self.assertTrue(linea.startswith(casilla.AVISO))
        self.assertIn("encargo de Molino: esto sí", linea)

    def test_un_encargo_se_crea_al_llegar_una_sola_vez(self):
        m = {"id": "m1", "de": "Molino", "texto": "revisa tarea:T84", "modo": "encargo", "encargo": "e-1a2b3c4d",
             "responder_a": "Molino", "plazo": "2026-10-24"}
        self.assertTrue(casilla.dejar(self.config, "Faro", m))
        e = encargo.leer(self.config, "e-1a2b3c4d")
        self.assertEqual((e["estado"], e["para"], e["de"], e["responder_a"], e["plazo"], e["mensaje"]),
                         ("pedido", "Faro", "Molino", "Molino", "2026-10-24", "m1"))
        self.assertEqual(e["maquina"], "laptop")
        encargo.hacer(self.ctx, "e-1a2b3c4d", "aceptar")
        # el mismo mensaje otra vez (un reintento del bus) no lo crea de nuevo ni lo vuelve a «pedido»
        casilla.mudar(self.config, "Faro", "Lámpara")
        casilla.dejar(self.config, "Faro", {**m, "id": "m2"})
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["estado"], "aceptado")

    def test_el_encargo_llega_con_su_direccion_y_como_contestarlo(self):
        casilla.dejar(self.config, "Faro", {"id": "m1", "de": "Molino", "texto": "revisa", "modo": "encargo",
                                            "encargo": "e-1a2b3c4d", "plazo": "2026-10-24"})
        razon = json.loads(casilla.para_gancho(self.config, "Faro", "Stop"))["reason"]
        # con la máquina donde quedó: el hilo lo encuentra aunque se mude
        self.assertIn("[encargo `encargo:e-1a2b3c4d@laptop` de Molino", razon)
        self.assertIn("plazo 2026-10-24", razon)
        self.assertIn("telar objeto encargo:e-1a2b3c4d@laptop aceptar", razon)
        self.assertIn("cerrar --params", razon)

    def test_un_aviso_se_muda_con_su_agente(self):
        casilla.dejar(self.config, "Faro", {"id": "a1", "texto": "x", "modo": "aviso"})
        self.assertEqual(casilla.mudar(self.config, "Faro", "Lámpara"), 1)
        self.assertEqual(casilla.pendientes(self.config, "Faro"), [])
        self.assertTrue((casilla.carpeta(self.config, "Lámpara") / casilla.AVISOS / "a1.json").exists())

    def test_el_mod_no_manda_el_aviso_por_un_aviso(self):
        from telar.ordenes import agente

        casilla.dejar(self.config, "Faro", {"id": "a1", "texto": "x", "modo": "aviso"})
        o = SimpleNamespace(hilo="Faro", sesion="")
        salida = io.StringIO()
        with redirect_stdout(salida):
            agente._mod(o, self.ctx)
        self.assertEqual(json.loads(salida.getvalue())["aviso"], "")
        casilla.dejar(self.config, "Faro", {"id": "b1", "texto": "y"})
        salida = io.StringIO()
        with redirect_stdout(salida):
            agente._mod(o, self.ctx)
        self.assertTrue(json.loads(salida.getvalue())["aviso"].startswith(casilla.AVISO))


class ElNodo(ConEstado):
    def _recoger(self, mensajes):
        import asyncio

        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.ctx, n.config, n.yo, n.renombrados = self.ctx, self.config, "laptop", {}
        n.anotado = []
        n.anotar = n.anotado.append

        async def _ack():
            pass

        class Sub:
            def __init__(self, datos):
                self.datos = datos

            async def fetch(self, cuantos, timeout):
                d, self.datos = self.datos, []
                return [SimpleNamespace(data=json.dumps(x).encode(), ack=_ack) for x in d]

        n.subs = {mod_bus.ficha("Faro"): Sub(mensajes)}
        avisados = []
        n.avisar = lambda nombre, info, encargo=False: avisados.append((nombre, encargo)) or "avisado"
        asyncio.run(n._recoger({"Faro": {}}))
        return avisados, n.anotado

    def test_un_aviso_no_despierta_ni_abre(self):
        avisados, anotado = self._recoger([{"id": "a1", "texto": "x", "modo": "aviso"}])
        self.assertEqual(avisados, [])
        self.assertTrue(any("1 aviso(s)" in x for x in anotado))
        self.assertEqual(len(casilla.pendientes(self.config, "Faro")), 1)

    def test_un_encargo_despierta_y_abre_aunque_no_sea_residente(self):
        avisados, _ = self._recoger([{"id": "m1", "texto": "x", "modo": "encargo", "encargo": "e-1a2b3c4d"},
                                     {"id": "m2", "texto": "y", "modo": "aviso"}])
        self.assertEqual(avisados, [("Faro", True)])
        self.assertIsNotNone(encargo.leer(self.config, "e-1a2b3c4d"))

    def test_un_pedido_como_siempre(self):
        avisados, _ = self._recoger([{"id": "m1", "texto": "x"}])
        self.assertEqual(avisados, [("Faro", False)])

    def test_el_pedido_encargo_del_nodo(self):
        casilla.dejar(self.config, "Faro", {"id": "m1", "texto": "x", "modo": "encargo", "encargo": "e-1a2b3c4d"})
        r = encargo.atender(self.ctx, {"id": "e-1a2b3c4d"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["encargo"]["estado"], "pedido")
        r = encargo.atender(self.ctx, {"id": "e-1a2b3c4d", "accion": "aceptar", "version": r["version"], "quien": "Ana"})
        self.assertEqual((r["ok"], r["encargo"]["estado"], r["encargo"]["historia"][-1]["quien"]), (True, "aceptado", "Ana"))
        self.assertEqual(encargo.atender(self.ctx, {"id": "e-ffffffff"})["codigo"], 404)
        self.assertEqual(encargo.atender(self.ctx, {"id": "e-1a2b3c4d", "accion": "aceptar"})["codigo"], 409)


class ElEncargo(ConEstado):
    def setUp(self):
        super().setUp()
        casilla.dejar(self.config, "Faro", {"id": "m1", "de": "Molino", "texto": "revisa tarea:T84", "modo": "encargo",
                                            "encargo": "e-1a2b3c4d", "responder_a": "Molino"})
        self.avisos = []
        p = mock.patch.object(mensaje, "enviar", side_effect=lambda ctx, para, texto, **kw: self.avisos.append(
            (para, texto, kw)) or {"id": "r1", "para": para})
        p.start()
        self.addCleanup(p.stop)

    def test_aceptar_y_cerrar_le_avisa_a_quien_lo_pidio(self):
        e = encargo.hacer(self.ctx, "e-1a2b3c4d", "aceptar", quien="Faro")
        self.assertEqual(e["estado"], "aceptado")
        self.assertEqual(self.avisos, [])  # aceptar no avisa
        e = encargo.hacer(self.ctx, "e-1a2b3c4d", "cerrar", {"resultado": "faltan dos casillas"}, quien="Faro")
        self.assertEqual((e["estado"], e["resultado"]), ("hecho", "faltan dos casillas"))
        self.assertEqual([h["estado"] for h in e["historia"]], ["pedido", "aceptado", "hecho", "hecho"])
        self.assertIn("avisado a «Molino»", e["historia"][-1]["nota"])
        para, texto, kw = self.avisos[0]
        self.assertEqual((para, kw.get("de")), ("Molino", "Faro"))
        self.assertIn("encargo:e-1a2b3c4d", texto)
        self.assertIn("faltan dos casillas", texto)
        self.assertNotIn("modo", kw)  # vuelve como un pedido: despierta
        with self.assertRaises(encargo.ErrorDeEncargo) as cm:
            encargo.hacer(self.ctx, "e-1a2b3c4d", "rechazar")
        self.assertEqual(cm.exception.codigo, 409)
        self.assertEqual(encargo.acciones_de(e), [])

    def test_rechazar_lo_deja_cancelado_con_su_motivo(self):
        e = encargo.hacer(self.ctx, "e-1a2b3c4d", "rechazar", {"motivo": "es de Molino"})
        self.assertEqual((e["estado"], e["rechazado"], e["resultado"]), ("cancelado", True, "es de Molino"))
        self.assertIn("rechazó", self.avisos[0][1])

    def test_cerrar_sin_resultado_o_con_un_estado_raro_no(self):
        for params in ({}, {"resultado": "  "}, {"resultado": "x", "estado": "a medias"}):
            with self.assertRaises(encargo.ErrorDeEncargo) as cm:
                encargo.hacer(self.ctx, "e-1a2b3c4d", "cerrar", params)
            self.assertEqual(cm.exception.codigo, 422)
        e = encargo.hacer(self.ctx, "e-1a2b3c4d", "cerrar", {"resultado": "no había red", "estado": "fallo"})
        self.assertEqual(e["estado"], "falló")

    def test_una_version_vieja_no_se_hace(self):
        vieja = encargo.version(encargo.leer(self.config, "e-1a2b3c4d"))
        encargo.hacer(self.ctx, "e-1a2b3c4d", "aceptar", version_leida=vieja)
        with self.assertRaises(encargo.ErrorDeEncargo) as cm:
            encargo.hacer(self.ctx, "e-1a2b3c4d", "cerrar", {"resultado": "x"}, version_leida=vieja)
        self.assertEqual(cm.exception.codigo, 409)

    def test_si_el_aviso_no_sale_la_accion_vale_igual(self):
        with mock.patch.object(mensaje, "enviar", side_effect=mod_bus.ErrorDeBus("no hay bus")):
            e = encargo.hacer(self.ctx, "e-1a2b3c4d", "cerrar", {"resultado": "listo"})
        self.assertEqual(e["estado"], "hecho")
        self.assertIn("no se le pudo avisar", e["historia"][-1]["nota"])
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["estado"], "hecho")

    def test_sin_responder_a_no_se_avisa_a_nadie(self):
        casilla.dejar(self.config, "Faro", {"id": "m9", "texto": "x", "modo": "encargo", "encargo": "e-00000009"})
        encargo.hacer(self.ctx, "e-00000009", "cerrar", {"resultado": "listo"})
        self.assertEqual(self.avisos, [])

    def test_vencido(self):
        e = {"plazo": "2026-10-24", "estado": "pedido"}
        self.assertFalse(encargo.vencido(e, datetime(2026, 10, 24, 23, 0)))
        self.assertTrue(encargo.vencido(e, datetime(2026, 10, 25, 0, 1)))
        self.assertFalse(encargo.vencido({**e, "estado": "hecho"}, datetime(2027, 1, 1)))
        self.assertTrue(encargo.vencido({"plazo": "2026-10-24T18:00", "estado": "aceptado"}, datetime(2026, 10, 24, 18, 1)))
        self.assertFalse(encargo.vencido({"estado": "pedido"}))
        with self.assertRaises(ValueError):
            encargo.plazo_valido("el jueves")

    def test_un_id_que_no_es_de_encargo(self):
        self.assertIsNone(encargo.leer(self.config, "../../x"))
        with self.assertRaises(encargo.ErrorDeEncargo) as cm:
            encargo.hacer(self.ctx, "../../x", "aceptar")
        self.assertEqual(cm.exception.codigo, 404)


class ElObjeto(ConEstado):
    def setUp(self):
        super().setUp()
        casilla.dejar(self.config, "Faro", {"id": "m1", "de": "Molino", "texto": "revisa tarea:T84 y hilo:Molino",
                                            "modo": "encargo", "encargo": "e-1a2b3c4d", "plazo": "2020-01-01"})

    def test_es_un_tipo_de_fabrica_y_se_encuentra_en_un_texto(self):
        self.assertIn("encargo", objetos.tipos(self.ctx))
        self.assertEqual([str(d) for d in objetos.buscar(self.ctx, "mira encargo:e-1a2b3c4d.")], ["encargo:e-1a2b3c4d"])

    def test_ver_y_sus_acciones(self):
        o = objetos.ver(self.ctx, "encargo:e-1a2b3c4d")
        self.assertEqual((o.direccion, o.tipo, o.estado, o.maquina), ("encargo:e-1a2b3c4d", "encargo", "pedido", "laptop"))
        self.assertEqual([a.nombre for a in o.acciones], ["aceptar", "rechazar", "cerrar", "cancelar"])
        self.assertEqual(next(a for a in o.acciones if a.nombre == "cerrar").params, {"resultado": "", "estado": "'hecho'"})
        self.assertTrue(o.campos["vencido"])
        self.assertEqual((o.campos["de"], o.campos["para"]), ("Molino", "Faro"))
        self.assertIn("hilo:Faro", o.enlaces)
        self.assertIn("tarea:T84", o.enlaces)
        self.assertTrue(o.version)

    def test_hacer_por_su_direccion(self):
        o = objetos.ver(self.ctx, "encargo:e-1a2b3c4d")
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Faro"}):
            h = objetos.hacer(self.ctx, "encargo:e-1a2b3c4d", "aceptar", version=o.version)
        self.assertEqual(h.objeto.estado, "aceptado")
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["historia"][-1]["quien"], "Faro")
        with self.assertRaises(ErrorDeServicio) as cm:
            objetos.hacer(self.ctx, "encargo:e-1a2b3c4d", "aceptar")
        self.assertEqual(cm.exception.codigo, 409)
        with self.assertRaises(ErrorDeServicio) as cm:
            objetos.hacer(self.ctx, "encargo:e-1a2b3c4d", "volar")
        self.assertEqual(cm.exception.codigo, 404)

    def test_uno_que_no_hay(self):
        with self.assertRaises(ErrorDeServicio) as cm:
            objetos.ver(self.ctx, "encargo:e-ffffffff")
        self.assertEqual(cm.exception.codigo, 404)
        with self.assertRaises(ErrorDeServicio) as cm:
            objetos.ver(self.ctx, "encargo:T84")
        self.assertEqual(cm.exception.codigo, 404)

    def test_de_otra_maquina_se_le_pide_a_esa(self):
        """Quien lo mandó tiene la nota; el encargo está en la máquina del destinatario."""
        allá = encargo.atender(self.ctx, {"id": "e-1a2b3c4d"})
        aqui = mod_config.Config(raiz=self.raiz, estado=self.raiz / "otro",
                                 bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="servidor"))
        ctx = SimpleNamespace(config=aqui)
        encargo.anotar_enviado(aqui, "e-1a2b3c4d", para="Faro", texto="revisa")
        pedidos = []

        def pedir(config, maquina, verbo, datos, espera=30):
            pedidos.append((maquina, verbo, datos))
            return encargo.atender(self.ctx, datos) if maquina == "laptop" else {"ok": False, "error": "no"}

        with mock.patch.object(mod_bus, "pedir", side_effect=pedir), \
                mock.patch.object(mod_bus, "maquina_de", return_value="laptop"):
            o = objetos.ver(ctx, "encargo:e-1a2b3c4d")
            self.assertEqual((o.estado, o.maquina, o.version), ("pedido", "laptop", allá["version"]))
            h = objetos.hacer(ctx, "encargo:e-1a2b3c4d", "aceptar", version=o.version)
        self.assertEqual(h.objeto.estado, "aceptado")
        self.assertEqual([(p[0], p[1], p[2].get("accion", "")) for p in pedidos],
                         [("laptop", "encargo", ""), ("laptop", "encargo", "aceptar")])
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["estado"], "aceptado")
        self.assertIsNone(encargo.leer(aqui, "e-1a2b3c4d"))  # allá vive; aquí, solo la nota

    def test_mientras_no_llega_se_ve_en_camino(self):
        aqui = mod_config.Config(raiz=self.raiz, estado=self.raiz / "otro",
                                 bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="servidor"))
        ctx = SimpleNamespace(config=aqui)
        encargo.anotar_enviado(aqui, "e-0000000a", para="Faro", texto="revisa", plazo="2026-10-24")
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "codigo": 404, "error": "no está"}), \
                mock.patch.object(mod_bus, "maquina_de", return_value="laptop"):
            o = objetos.ver(ctx, "encargo:e-0000000a")
            self.assertEqual((o.estado, o.campos.get("en_camino"), o.acciones, o.campos["plazo"]),
                             ("pedido", True, [], "2026-10-24"))
            with self.assertRaises(ErrorDeServicio) as cm:
                objetos.hacer(ctx, "encargo:e-0000000a", "aceptar")
            self.assertEqual(cm.exception.codigo, 404)
        # sin bus, la nota sola
        sin_bus = mod_config.Config(raiz=self.raiz, estado=self.raiz / "otro")
        o = objetos.ver(SimpleNamespace(config=sin_bus), "encargo:e-0000000a")
        self.assertTrue(o.campos["en_camino"])

    def test_una_maquina_de_antes_no_atiende_encargo(self):
        aqui = mod_config.Config(raiz=self.raiz, estado=self.raiz / "otro",
                                 bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="servidor"))
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "sin_servicio": True,
                                                               "error": "laptop no atiende «encargo»"}):
            with self.assertRaises(ErrorDeServicio) as cm:
                objetos.ver(SimpleNamespace(config=aqui), "encargo:e-1a2b3c4d@laptop")
        self.assertEqual(cm.exception.codigo, 502)
        self.assertIn("no atiende", str(cm.exception))


class LaOrden(ConBusFalso):
    def test_pedido_sin_modo_se_manda_como_siempre(self):
        r = mensaje.enviar(self.ctx, "Faro", "hola")
        self.assertEqual(self.llamadas, [{}])
        self.assertNotIn("modo", r)
        self.assertNotIn("encargo", r)

    def test_aviso(self):
        mensaje.enviar(self.ctx, "Faro", "ya está", modo="aviso")
        self.assertEqual(self.llamadas, [{"modo": "aviso"}])
        self.assertEqual(casilla.despiertan(self.config, "Faro"), [])
        self.assertEqual(len(casilla.pendientes(self.config, "Faro")), 1)

    def test_encargo_de_punta_a_punta(self):
        """Molino le encarga a Faro; Faro lo acepta y lo cierra; a Molino le llega el resultado."""
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Molino"}):
            r = mensaje.enviar(self.ctx, "Faro", "revisa tarea:T84", modo="encargo", plazo="2026-10-24")
        eid = r["encargo"]
        self.assertTrue(encargo.FORMA_ID.fullmatch(eid))
        self.assertEqual(r["direccion"], f"encargo:{eid}")
        self.assertEqual(self.llamadas[0]["extra"], {"encargo": eid, "plazo": "2026-10-24", "responder_a": "Molino"})
        self.assertEqual(encargo.enviado(self.config, eid)["para"], "Faro")
        # a Faro le llega con la dirección
        razon = json.loads(casilla.para_gancho(self.config, "Faro", "Stop"))["reason"]
        self.assertIn(f"encargo:{eid}", razon)
        # entregado: ya corre (lo tiene Faro), y ya no se acepta
        self.assertEqual(encargo.leer(self.config, eid)["estado"], "corriendo")
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Faro"}):
            h = objetos.hacer(self.ctx, f"encargo:{eid}", "cerrar", {"resultado": "faltan dos casillas"})
        self.assertEqual(h.objeto.estado, "hecho")
        # y a Molino, el resultado, como un pedido que despierta
        llegado = casilla.despiertan(self.config, "Molino")
        self.assertEqual(len(llegado), 1)
        self.assertEqual(llegado[0]["de"], "Faro")
        self.assertIn("faltan dos casillas", llegado[0]["texto"])
        self.assertNotIn("modo", llegado[0])

    def test_lo_que_no_sirve(self):
        for kw in ({"modo": "consulta"}, {"modo": "grito"}, {"plazo": "2026-10-24"},
                   {"modo": "encargo", "plazo": "el jueves"}):
            with self.assertRaises(ValueError, msg=kw):
                mensaje.enviar(self.ctx, "Faro", "x", **kw)
        self.assertEqual(self.enviados, [])

    def test_soltar_un_retenido_conserva_su_modo(self):
        retenido = {"id": "m1", "para": "Faro", "texto": "x", "de": "Molino", "tipo": "mensaje", "estado": "retenido",
                    "modo": "encargo", "encargo": "e-1a2b3c4d", "responder_a": "Molino"}
        with mock.patch.object(mod_bus, "registro", return_value=[retenido]):
            mensaje.soltar(self.ctx, "m1")
        self.assertEqual(self.llamadas[-1], {"modo": "encargo", "extra": {"encargo": "e-1a2b3c4d", "responder_a": "Molino"}})
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["responder_a"], "Molino")

    def _cli(self, *argv):
        from telar import cli

        salida, error = io.StringIO(), io.StringIO()
        with mock.patch.object(cli, "cargar_config", return_value=self.config), redirect_stdout(salida), \
                redirect_stderr(error):
            codigo = cli.main(list(argv))
        return codigo, salida.getvalue(), error.getvalue()

    def test_la_cli(self):
        codigo, salida, _ = self._cli("mensaje", "Faro", "revisa", "--modo", "encargo", "--plazo", "2026-10-24", "--json")
        self.assertEqual(codigo, 0)
        r = json.loads(salida)
        self.assertEqual((r["modo"], r["plazo"], r["direccion"]), ("encargo", "2026-10-24", f"encargo:{r['encargo']}"))
        codigo, salida, _ = self._cli("mensaje", "Faro", "ya está", "--modo", "aviso")
        self.assertEqual(codigo, 0)
        self.assertIn("no lo despierta", salida)
        codigo, _, error = self._cli("mensaje", "Faro", "x", "--plazo", "2026-10-24")
        self.assertNotEqual(codigo, 0)
        self.assertIn("plazo", error)
        codigo, _, error = self._cli("mensaje", "Faro", "¿cómo vas?", "--modo", "consulta")
        self.assertNotEqual(codigo, 0)
        self.assertIn("no lleva texto", error)

    def test_la_consulta_no_manda_nada(self):
        from telar.servicios import historias
        from telar.servicios import mensajes as servicio

        hilo = objetos.Objeto(direccion="hilo:Faro", tipo="hilo", id="Faro", titulo="Faro", estado="trabajando",
                              campos={"relativa": "proyectos/faro"}, maquina="servidor")
        leidos = []

        def leer(ctx, nombre, ultimos=0, maquina=""):
            leidos.append((nombre, ultimos, maquina))
            return historias.Historia(hilo=nombre, turnos=[[{"quien": "agente", "texto": "revisando T84"}]])

        with mock.patch.object(objetos, "ver", return_value=hilo) as ver, \
                mock.patch.object(historias, "leer", side_effect=leer):
            r = servicio.consultar(self.ctx, "Faro")
            codigo, salida, _ = self._cli("mensaje", "Faro", "--modo", "consulta")
        self.assertEqual(ver.call_args.args[1], "hilo:Faro")
        self.assertEqual(leidos[0], ("Faro", servicio.TURNOS_CONSULTA, "servidor"))
        self.assertEqual((r.modo, r.para, r.objeto["estado"]), ("consulta", "Faro", "trabajando"))
        self.assertEqual(codigo, 0)
        self.assertIn("«Faro»: trabajando", salida)
        self.assertIn("revisando T84", salida)
        self.assertEqual(self.enviados, [])
        self.assertEqual(casilla.pendientes(self.config, "Faro"), [])

    def test_la_consulta_sin_conversacion_dice_por_que(self):
        from telar.servicios import historias
        from telar.servicios import mensajes as servicio

        hilo = objetos.Objeto(direccion="hilo:Faro", tipo="hilo", id="Faro", titulo="Faro")
        with mock.patch.object(objetos, "ver", return_value=hilo), \
                mock.patch.object(historias, "leer", side_effect=ErrorDeServicio("no tiene conversación", 502)):
            r = servicio.consultar(self.ctx, "Faro")
        self.assertEqual((r.ultimos, r.problema), (None, "no tiene conversación"))

    def test_el_hilo_como_objeto_manda_con_modo(self):
        with mock.patch.object(objetos, "_tipo", return_value=objetos.Hilo()):
            h = objetos.hacer(self.ctx, "hilo:Faro", "mensaje", {"texto": "ya está", "modo": "aviso"})
        self.assertEqual(h.resultado["modo"], "aviso")
        self.assertEqual(casilla.despiertan(self.config, "Faro"), [])


class LoQueEncontroLaRevision(ConBusFalso):
    """Lo que encontraron los revisores en los modos y el Encargo."""

    def _encargo(self, eid="e-1a2b3c4d", para="Faro", **extra):
        casilla.dejar(self.config, para, {"id": "m1", "de": "Molino", "texto": "revisa", "modo": "encargo",
                                          "encargo": eid, "responder_a": "Molino", **extra})
        return eid

    def test_la_nota_de_quien_manda_guarda_la_maquina_del_hilo(self):
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Molino"}):
            r = mensaje.enviar(self.ctx, "Faro", "revisa", modo="encargo")
        self.assertEqual(encargo.enviado(self.config, r["encargo"])["maquina"], "servidor")
        # si Faro se muda (o su estado se borra del bus), se le sigue pidiendo al servidor
        aqui = mod_config.Config(raiz=self.raiz, estado=self.raiz / "estado",
                                 bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="laptop"))
        os.remove(Path(self.config.estado) / "encargos" / "objetos" / f"{r['encargo']}.json")
        pedidos = []
        with mock.patch.object(mod_bus, "maquina_de", return_value="laptop"), \
                mock.patch.object(mod_bus, "pedir", side_effect=lambda c, m, v, d, espera=30: pedidos.append(m) or
                                  {"ok": False, "codigo": 404, "error": "no está"}):
            objetos.ver(SimpleNamespace(config=aqui), r["direccion"])
        self.assertEqual(pedidos, ["servidor"])

    def test_retenido_no_se_ve_en_camino_y_al_soltarlo_si(self):
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Molino"}), \
                mock.patch.object(casilla, "cadena", return_value=casilla.TOPE_SALTOS):
            r = mensaje.enviar(self.ctx, "Faro", "revisa", modo="encargo")
        self.assertEqual(r["estado"], "retenido")
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "codigo": 404, "error": "no está"}):
            o = objetos.ver(self.ctx, r["direccion"])
        self.assertIn("tope", o.campos["retenido"])
        self.assertNotIn("en_camino", o.campos)
        retenido = {**self.enviados[-1], "estado": "retenido"}
        with mock.patch.object(mod_bus, "registro", return_value=[retenido]):
            mensaje.soltar(self.ctx, retenido["id"])
        self.assertNotIn("retenido", encargo.enviado(self.config, r["encargo"]))

    def test_rechazar_pide_el_motivo(self):
        eid = self._encargo()
        for params in ({}, {"motivo": "  "}):
            with self.assertRaises(encargo.ErrorDeEncargo) as cm:
                encargo.hacer(self.ctx, eid, "rechazar", params)
            self.assertEqual(cm.exception.codigo, 422)
        self.assertEqual(encargo.leer(self.config, eid)["estado"], "pedido")

    def test_cerrar_con_falló_descompuesto(self):
        import unicodedata

        eid = self._encargo()
        e = encargo.hacer(self.ctx, eid, "cerrar", {"resultado": "r", "estado": unicodedata.normalize("NFD", "falló")})
        self.assertEqual(e["estado"], "falló")

    def test_lo_que_pasa_mientras_se_avisa_no_se_pisa(self):
        eid = self._encargo()

        def avisar(ctx, para, texto, **kw):
            encargo.mudar(self.config, eid, "Lámpara")  # otra escritura, mientras el bus tarda
            return {"id": "r1", "para": para}

        with mock.patch.object(mensaje, "enviar", side_effect=avisar):
            encargo.hacer(self.ctx, eid, "cerrar", {"resultado": "listo"})
        e = encargo.leer(self.config, eid)
        self.assertEqual((e["para"], e["estado"], e["historia"][-1]["quien"]), ("Lámpara", "hecho", "telar"))

    def test_dos_cerrar_a_la_vez_pasa_uno(self):
        import threading
        import time

        eid = self._encargo()
        leer = encargo._leer

        def lento(ruta):
            datos = leer(ruta)
            time.sleep(0.2)  # los dos leen antes de que el otro escriba, sin candado
            return datos

        avisos, errores = [], []

        def cerrar():
            try:
                encargo.hacer(self.ctx, eid, "cerrar", {"resultado": "listo"})
            except encargo.ErrorDeEncargo as ex:
                errores.append(ex.codigo)

        with mock.patch.object(encargo, "_leer", side_effect=lento), \
                mock.patch.object(mensaje, "enviar", side_effect=lambda ctx, para, texto, **kw: avisos.append(para) or {"id": "r"}):
            hilos = [threading.Thread(target=cerrar) for _ in range(2)]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()
        self.assertEqual((errores, avisos), ([409], ["Molino"]))

    def test_el_plazo_en_forma_basica_vence_al_final_del_dia(self):
        self.assertEqual(encargo.plazo_valido("20261024"), "2026-10-24")
        self.assertEqual(encargo.plazo_valido("2026-10-24T18:00"), "2026-10-24T18:00")
        self.assertEqual(encargo.plazo_valido("20261024T1800"), "2026-10-24T18:00:00")
        # uno guardado así antes de este cambio, también
        self.assertFalse(encargo.vencido({"plazo": "20261024", "estado": "pedido"}, datetime(2026, 10, 24, 18, 0)))
        self.assertTrue(encargo.vencido({"plazo": "20261024", "estado": "pedido"}, datetime(2026, 10, 25, 0, 1)))

    def test_un_aviso_de_la_persona_dice_que_es_un_aviso(self):
        casilla.dejar(self.config, "Faro", {"id": "1", "tipo": "persona", "modo": "aviso", "de": "el panel",
                                            "texto": "hola"})
        self.assertEqual(casilla.para_gancho(self.config, "Faro", "Stop"), "")
        texto = json.loads(casilla.para_gancho(self.config, "Faro", "UserPromptSubmit", prompt="sigue"))[
            "hookSpecificOutput"]["additionalContext"]
        self.assertIn("[aviso: tu persona te escribe desde el panel", texto)
        self.assertIn("no pide nada", texto)

    def test_mudar_la_casilla_muda_quien_hace_el_encargo(self):
        eid = self._encargo(para="Viejo")
        encargo.hacer(self.ctx, eid, "aceptar")
        casilla.mudar(self.config, "Viejo", "Nuevo")
        e = encargo.leer(self.config, eid)
        self.assertEqual((e["para"], e["estado"]), ("Nuevo", "aceptado"))

    def test_un_hilo_renombrado_avisa_con_su_nombre_de_hoy(self):
        from telar import estado as mod_estado

        eid = self._encargo()
        mod_estado.abrir(self.config).renombrar("Faro", "Lámpara")
        avisos = []
        with mock.patch.object(mensaje, "enviar", side_effect=lambda ctx, para, texto, **kw: avisos.append((texto, kw)) or {"id": "r"}):
            e = encargo.hacer(self.ctx, eid, "cerrar", {"resultado": "listo"})
        self.assertEqual(e["para"], "Lámpara")
        self.assertEqual(avisos[0][1]["de"], "Lámpara")
        self.assertIn("«Lámpara» terminó", avisos[0][0])

    def test_el_mensaje_del_hilo_declara_el_plazo(self):
        o = objetos.Hilo()._objeto({"nombre": "Faro"}, "")
        self.assertEqual(next(a for a in o.acciones if a.nombre == "mensaje").params,
                         {"texto": "", "modo": "'pedido'", "plazo": "''"})

    def test_un_valueerror_ajeno_no_es_un_422(self):
        from telar.servicios import mensajes as servicio

        with self.assertRaises(ErrorDeServicio) as cm:
            servicio.enviar(self.ctx, "Faro", "x", plazo="mañana", modo="encargo")
        self.assertEqual(cm.exception.codigo, 422)
        with mock.patch.object(mensaje, "enviar", side_effect=ValueError("otra cosa")):
            with self.assertRaises(ValueError) as cm:
                servicio.enviar(self.ctx, "Faro", "x")
        self.assertNotIsInstance(cm.exception, ErrorDeServicio)

    def test_la_cifra_de_la_linea_cuenta_lo_que_pide(self):
        casilla.dejar(self.config, "Faro", {"id": "1-a", "de": "Molino", "texto": "para que sepas", "modo": "aviso"})
        casilla.dejar(self.config, "Faro", {"id": "2-b", "de": "Molino", "texto": "esto sí"})
        self.assertTrue(casilla.aviso(self.config, "Faro").endswith("mensaje de Molino: esto sí (1 aviso)"))
        casilla.dejar(self.config, "Faro", {"id": "3-c", "de": "Molino", "texto": "y esto"})
        self.assertTrue(casilla.aviso(self.config, "Faro").endswith("esto sí (+1, 1 aviso)"))


if HAY_FASTAPI:
    class LaApi(ConBusFalso):
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

        def test_post_con_modo_y_la_consulta(self):
            r = self.c.post("/mensajes", json={"para": "Faro", "texto": "revisa", "modo": "encargo", "plazo": "2026-10-24"})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertTrue(r.json()["direccion"].startswith("encargo:e-"))
            self.assertEqual(self.c.post("/mensajes", json={"para": "Faro", "texto": "x", "modo": "consulta"}).status_code, 422)
            self.assertEqual(self.c.post("/mensajes", json={"para": "Faro", "texto": "x", "plazo": "mañana"}).status_code, 422)
            hilo = objetos.Objeto(direccion="hilo:Faro", tipo="hilo", id="Faro", titulo="Faro", estado="espera")
            from telar.servicios import historias

            with mock.patch.object(objetos, "ver", return_value=hilo), \
                    mock.patch.object(historias, "leer", side_effect=ErrorDeServicio("sin conversación", 502)):
                r = self.c.get("/mensajes/consulta", params={"para": "Faro"})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()["objeto"]["estado"], "espera")
