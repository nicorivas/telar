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

    def test_el_panel_le_escribe_a_un_hilo_de_otra_maquina_como_la_persona(self):
        from telar.ordenes import mensaje

        mensaje.enviar(self.ctx, "Faro", "hola", tipo="persona", de="el panel")
        self.assertEqual((self.enviados[0]["tipo"], self.enviados[0]["para"]), ("persona", "Faro"))

    def test_con_bus_el_espejo_no_se_empuja_por_ssh(self):
        from telar.ordenes import espejo

        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = espejo.main(["publicar", "--json"], self.ctx)
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida.getvalue())["por"], "bus")

    def test_leer_un_hilo_de_otra_maquina_es_un_pedido_al_nodo(self):
        from telar.ordenes import hilo

        salida, error = io.StringIO(), io.StringIO()
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "servidor no respondió"}) as pedir, \
                redirect_stdout(salida), mock.patch("sys.stderr", error):
            codigo = hilo.main(["leer", "Faro", "--maquina", "servidor", "--ultimos", "3", "--json"], self.ctx)
        self.assertNotEqual(codigo, 0)
        self.assertIn("no respondió", error.getvalue())
        self.assertEqual(pedir.call_args[0][1:3], ("servidor", "leer"))
        self.assertEqual(pedir.call_args[0][3], {"hilo": "Faro", "ultimos": 3})
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "historia": {"hilo": "Faro", "turnos": []}}), redirect_stdout(salida := io.StringIO()):
            self.assertEqual(hilo.main(["leer", "Faro", "--maquina", "servidor", "--json"], self.ctx), 0)
        self.assertEqual(json.loads(salida.getvalue())["maquina"], "servidor")

    def test_una_tarea_va_al_hilo_cuya_carpeta_contiene_su_enlace(self):
        from telar.ordenes.pendiente import _por_enlace

        candidatos = [("trabajo", "trabajo", True), ("PA", "trabajo/proyectos/pa", False), ("PA2", "trabajo/proyectos/pa-otro", True)]
        self.assertEqual(_por_enlace(candidatos, "trabajo/proyectos/pa/reuniones/x.md"), "PA")
        self.assertIsNone(_por_enlace(candidatos, "trabajo/notas.md"))  # un área no decide
        self.assertIsNone(_por_enlace(candidatos, "https://trabajo/proyectos/pa/x"))

    def test_sin_hilo_aqui_la_tarea_va_al_de_otra_maquina(self):
        from telar import espejo
        from telar.ordenes.pendiente import _destino_remoto

        fotos = [{"nombre": "laptop", "en_linea": True, "edad": 5, "hilos": [
            {"nombre": "Faro", "relativa": "trabajo/proyectos/pa", "vivo": True, "remoto": ""},
            {"nombre": "Gestión", "relativa": "agentes/gestion", "vivo": True, "remoto": "servidor"}]}]
        with mock.patch.object(espejo, "leer_todos", return_value=fotos):
            self.assertEqual(_destino_remoto(self.ctx, {"url": "trabajo/proyectos/pa/x.md"}), ("Faro", "laptop"))
            self.assertIsNone(_destino_remoto(self.ctx, {"url": "agentes/gestion/bitacora.md"}))

    def test_un_trabajando_viejo_se_da_por_pegado(self):
        from datetime import datetime, timedelta

        from telar.modelo import Atencion
        from telar.ordenes.nodo import TRABAJANDO_VIEJO, Nodo

        def est(hace):
            return SimpleNamespace(atenciones=lambda: {"Faro": (Atencion.TRABAJANDO, datetime.now() - timedelta(seconds=hace))})

        self.assertTrue(Nodo.atencion_vieja(est(TRABAJANDO_VIEJO + 60), "Faro"))
        self.assertFalse(Nodo.atencion_vieja(est(60), "Faro"))
        self.assertFalse(Nodo.atencion_vieja(SimpleNamespace(atenciones=lambda: {}), "Faro"))
