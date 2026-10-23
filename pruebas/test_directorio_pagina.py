"""Los hilos de las otras personas para la página (telar.servicios.directorio): lo que se ve y escribirles."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar.servicios import ErrorDeServicio
from telar.servicios import directorio


class ElDirectorioEnLaPagina(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctx = SimpleNamespace(config=SimpleNamespace(
            estado=Path(self.tmp.name), bus=SimpleNamespace(url="nats://bus", persona="ana", maquina="laptop", token="")))
        self.ahora = datetime(2026, 10, 23, 10, 0).astimezone()
        reciente = (self.ahora - timedelta(minutes=2)).isoformat()
        viejo = (self.ahora - timedelta(hours=3)).isoformat()
        (Path(self.tmp.name) / "directorio-bus.json").write_text(json.dumps({
            "beto": {"mac": {"publicado": reciente, "visto": reciente, "hilos": [
                {"nombre": "Zeta", "ext": "zeta", "vivo": False, "carpeta": "", "resumen": ""},
                {"nombre": "Faro", "ext": "faro", "vivo": True, "carpeta": "proyectos/faro", "resumen": "el faro"}]}},
            "carla": {"pc": {"publicado": viejo, "visto": viejo, "hilos": []}},
            "ana": {"otra": {"hilos": [{"nombre": "mío"}]}},
        }))

    def test_por_persona_los_vivos_primero_y_sin_los_propios(self):
        d = directorio.ver(self.ctx, ahora=self.ahora)
        self.assertEqual(d.yo, "ana")
        self.assertEqual([p["persona"] for p in d.personas], ["beto", "carla"])
        beto = d.personas[0]["maquinas"][0]
        self.assertEqual([h["nombre"] for h in beto["hilos"]], ["Faro", "Zeta"])
        self.assertTrue(beto["al_dia"])
        self.assertFalse(d.personas[1]["maquinas"][0]["al_dia"])

    def test_escribir_va_por_el_correo_entre_personas(self):
        with mock.patch.object(mod_bus, "escribir_a", return_value={"ok": True, "id": "m1"}) as escribir:
            r = directorio.escribir(self.ctx, "beto", "faro", "hola")
        self.assertEqual((r.id, r.persona, r.hilo), ("m1", "beto", "faro"))
        self.assertEqual(escribir.call_args.args[1:4], ("beto", "faro", "hola"))
        for persona, hilo, texto in (("ana", "x", "hola"), ("beto", "", "hola"), ("Beto Grande", "x", "y")):
            with self.assertRaises(ErrorDeServicio):
                directorio.escribir(self.ctx, persona, hilo, texto)
