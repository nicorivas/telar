"""Lo que pasa por el bus cuando hay `[bus] url`: el correo entre hilos de una misma persona, lo que
se escribe desde la web a un hilo de otra máquina, el espejo y el contexto de los hilos. El bus
mismo se reemplaza por un registro: aquí se prueba el desvío, no NATS (eso es test_bus.py)."""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar import config as mod_config


class PorElBus(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                        bus=mod_config.Bus(url="nats://127.0.0.1:1", persona="ana", maquina="laptop"))
        self.ctx = SimpleNamespace(config=self.config)
        self.enviados: list[dict] = []

        def enviar(config, para, texto, *, de, tipo="mensaje", quien="", saltos=0, mid="", retener=""):
            m = {"id": mid or f"m{len(self.enviados)}", "para": para, "texto": texto, "de": de, "tipo": tipo,
                 "saltos": saltos, **({"estado": "retenido", "motivo": retener} if retener else {})}
            self.enviados.append(m)
            return m

        p = mock.patch.object(mod_bus, "enviar", side_effect=enviar)
        p.start()
        self.addCleanup(p.stop)

    def test_el_correo_a_un_hilo_propio_va_por_el_bus(self):
        from telar.ordenes import correo

        via, error = correo.enviar(self.ctx, "ana+faro@servidor", "hola", "cuerpo con tildes: canción")
        self.assertEqual(error, "")
        self.assertIn("bus", via)
        self.assertEqual(self.enviados[0]["para"], "faro")
        self.assertTrue(self.enviados[0]["texto"].startswith("Asunto: hola\n\n"))

    def test_el_correo_a_otra_persona_no_va_por_el_bus(self):
        from telar.ordenes import correo

        with mock.patch("subprocess.run") as run, mock.patch("telar.ordenes.agente._cartero_aqui", return_value=True):
            run.return_value = SimpleNamespace(returncode=0, stderr="")
            correo.enviar(self.ctx, "berta+faro@servidor", "hola", "cuerpo")
        self.assertEqual(self.enviados, [])
        self.assertEqual(run.call_args[0][0][0], "mail")

    def test_la_web_le_escribe_a_un_hilo_de_otra_maquina_como_la_persona(self):
        from telar.ordenes import web

        web._ultimo_envio[0] = 0.0
        codigo, r = web.enviar(self.ctx, {"maquina": "servidor", "hilo": "Faro", "texto": "hola", "enter": True})
        self.assertEqual(codigo, 200)
        self.assertEqual(r["por"], "bus")
        self.assertEqual((self.enviados[0]["tipo"], self.enviados[0]["para"]), ("persona", "Faro"))

    def test_con_bus_el_espejo_no_se_empuja_por_ssh(self):
        from telar.ordenes import espejo

        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = espejo.main(["publicar", "--json"], self.ctx)
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida.getvalue())["por"], "bus")

    def test_la_lectura_remota_de_la_web_es_un_pedido_al_nodo(self):
        from telar.ordenes import web

        web._remotas.clear()
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "servidor no respondió"}) as pedir:
            codigo, cuerpo, _ = web._conversacion("hilo=Faro&maquina=servidor&turnos=3", self.config)
        self.assertEqual(codigo, 409)
        self.assertIn("no respondió", json.loads(cuerpo)["error"])
        self.assertEqual(pedir.call_args[0][1:3], ("servidor", "leer"))
        self.assertEqual(pedir.call_args[0][3], {"hilo": "Faro", "ultimos": 3})

    def test_con_bus_el_sondeo_de_remotos_no_hace_ssh(self):
        from telar.ordenes import remotos

        import dataclasses

        ctx = SimpleNamespace(config=dataclasses.replace(
            self.config, remotos=(mod_config.Remoto(nombre="servidor", destino="ana@servidor"),)))
        salida = io.StringIO()
        with mock.patch("subprocess.run") as run, redirect_stdout(salida):
            codigo = remotos.main(["traer", "--sondeo", "--json"], ctx)
        self.assertEqual(codigo, 0)
        run.assert_not_called()
        self.assertEqual(json.loads(salida.getvalue())["por"], "bus")

    def test_una_tarea_va_al_hilo_cuya_carpeta_contiene_su_enlace(self):
        from telar.ordenes.pendiente import _por_enlace

        candidatos = [("brinca", "brinca", True), ("PA", "brinca/proyectos/pa", False), ("PA2", "brinca/proyectos/pa-otro", True)]
        self.assertEqual(_por_enlace(candidatos, "brinca/proyectos/pa/reuniones/x.md"), "PA")
        self.assertIsNone(_por_enlace(candidatos, "brinca/notas.md"))  # un área no decide
        self.assertIsNone(_por_enlace(candidatos, "https://brinca/proyectos/pa/x"))

    def test_sin_hilo_aqui_la_tarea_va_al_de_otra_maquina(self):
        from telar import espejo
        from telar.ordenes.pendiente import _destino_remoto

        fotos = [{"nombre": "laptop", "en_linea": True, "edad": 5, "hilos": [
            {"nombre": "Parque", "relativa": "brinca/proyectos/pa", "vivo": True, "remoto": ""},
            {"nombre": "Gestión", "relativa": "agentes/gestion", "vivo": True, "remoto": "servidor"}]}]
        with mock.patch.object(espejo, "leer_todos", return_value=fotos):
            self.assertEqual(_destino_remoto(self.ctx, {"url": "brinca/proyectos/pa/x.md"}), ("Parque", "laptop"))
            self.assertIsNone(_destino_remoto(self.ctx, {"url": "agentes/gestion/bitacora.md"}))
