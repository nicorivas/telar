"""El bus contra un nats-server de verdad: corre solo si `TELAR_NATS_SERVER` dice dónde está el binario.

    TELAR_NATS_SERVER=/ruta/nats-server python3 -m pytest pruebas/test_bus.py
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as m
from telar import config as mod_config

BINARIO = os.environ.get("TELAR_NATS_SERVER", "")


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(BINARIO and Path(BINARIO).exists(), "sin TELAR_NATS_SERVER: el bus se prueba contra uno de verdad")
class ContraUnServidor(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        puerto = _puerto_libre()
        token = Path(self.tmp.name) / "token"
        token.write_text("secreto")
        self.proc = subprocess.Popen([BINARIO, "-a", "127.0.0.1", "-p", str(puerto), "--js", "--store_dir",
                                      str(Path(self.tmp.name) / "datos"), "--auth", "secreto"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.proc.kill)
        time.sleep(0.5)
        self.config = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                        bus=mod_config.Bus(url=f"nats://127.0.0.1:{puerto}", token=str(token),
                                                           persona="ana", maquina="servidor"))

    def test_lo_publicado_espera_y_llega_en_orden_sin_duplicar(self):
        a = m.enviar(self.config, "Faro", "uno: canción", de="Gestión")
        m.enviar(self.config, "Faro", "dos", de="Gestión")
        self.assertFalse(a["duplicado"])

        async def recoger():
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            sub = await js.pull_subscribe(m.tema_casilla(self.config, "Faro"), durable="c-ana-faro", stream=m.STREAM)
            msgs = await sub.fetch(10, timeout=2)
            textos = [json.loads(x.data)["texto"] for x in msgs]
            for x in msgs:
                await x.ack()
            await nc.close()
            return textos

        self.assertEqual(asyncio.run(recoger()), ["uno: canción", "dos"])

    def test_el_estado_se_lee_por_hilo(self):
        async def publicar():
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            await m.asegurar(js)
            kv = await js.key_value(m.ESTADO)
            await kv.put(m.clave_estado(self.config, "Gestión"), json.dumps({"nombre": "Gestión", "atencion": "espera"}).encode())
            await nc.close()

        asyncio.run(publicar())
        self.assertEqual(m.estados(self.config)["Gestión"]["atencion"], "espera")

    def test_una_cadena_larga_se_retiene_y_la_persona_la_suelta(self):
        from unittest import mock

        from telar import casilla
        from telar.ordenes import mensaje

        ctx = SimpleNamespace(config=self.config)
        casilla.anotar_cadena(self.config, "Faro", casilla.TOPE_SALTOS)  # Faro ya está al final de una cadena
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Faro"}):
            r = mensaje.enviar(ctx, "Gestión", "¿seguimos?")
        self.assertEqual(r["estado"], "retenido")
        self.assertEqual(r["saltos"], casilla.TOPE_SALTOS + 1)
        retenidos = mensaje.retenidos(m.registro(self.config))
        self.assertEqual([x["id"] for x in retenidos], [r["id"]])
        mensaje.soltar(ctx, r["id"])
        self.assertEqual(mensaje.retenidos(m.registro(self.config)), [])

        async def recoger():
            nc = await m.conectar(self.config)
            js = nc.jetstream()
            sub = await js.pull_subscribe(m.tema_casilla(self.config, "Gestión"), durable="c-ana-gestion", stream=m.STREAM)
            msgs = await sub.fetch(5, timeout=2)
            await nc.close()
            return [json.loads(x.data) for x in msgs]

        llegados = asyncio.run(recoger())
        self.assertEqual([(x["texto"], x["saltos"], x["persona"]) for x in llegados], [("¿seguimos?", 0, "ana")])

    def test_un_hilo_suma_un_salto_a_su_cadena(self):
        from unittest import mock

        from telar import casilla
        from telar.ordenes import mensaje

        casilla.anotar_cadena(self.config, "Faro", 2)
        with mock.patch.dict(os.environ, {"TELAR_HILO": "Faro"}):
            r = mensaje.enviar(SimpleNamespace(config=self.config), "Gestión", "hola")
        self.assertEqual((r["saltos"], r.get("estado")), (3, None))
        self.assertEqual(m.registro(self.config)[-1]["estado"], "enviado")

    def test_sin_servidor_el_error_se_entiende(self):
        cfg = mod_config.Config(bus=mod_config.Bus(url="nats://127.0.0.1:1"))
        with self.assertRaises(m.ErrorDeBus):
            m.enviar(cfg, "Faro", "x", de="y")
