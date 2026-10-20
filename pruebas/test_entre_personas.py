"""Entre personas por el bus (telar.entre_personas): el directorio y el correo que llega."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import entre_personas as ep


class ElDirectorio(Prueba):
    def test_publica_solo_nombre_palabra_carpeta_y_resumen(self):
        foto = {"maquina": "telar", "hilos": [
            {"nombre": "T42 Faro Norte", "vivo": True, "relativa": "proyectos/faro", "resumen": "va bien",
             "atencion": "espera", "tiempo": 99},
            {"nombre": "De otra máquina", "remoto": "laptop"},
        ]}
        d = ep.directorio(foto, "nico")
        self.assertEqual((d["persona"], d["maquina"]), ("nico", "telar"))
        self.assertEqual(d["hilos"], [{"nombre": "T42 Faro Norte", "ext": "t42-faro-norte", "vivo": True,
                                       "carpeta": "proyectos/faro", "resumen": "va bien"}])

    def test_guardar_y_leer_por_persona_y_maquina(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = SimpleNamespace(estado=tmp)
            ep.guardar(config, "marcelo", {"maquina": "telar", "hilos": [{"nombre": "Faro"}, "basura"]})
            ep.guardar(config, "marcelo", {"maquina": "laptop", "hilos": []})
            todos = ep.leer(config)
            self.assertEqual(sorted(todos["marcelo"]), ["laptop", "telar"])
            self.assertEqual(todos["marcelo"]["telar"]["hilos"], [{"nombre": "Faro"}])


class ElCorreoQueLlega(Prueba):
    def test_de_quien_lo_dice_el_bus_no_el_mensaje(self):
        pedido = {"para": "Faro Norte", "texto": " hola ", "de": "Gestión", "asunto": "una duda", "persona": "otro"}
        c = ep.correo(pedido, "marcelo")
        self.assertEqual((c["para"], c["de"], c["persona"]), ("faro-norte", "marcelo:Gestión", "marcelo"))
        self.assertEqual(c["texto"], "Asunto: una duda" + chr(10) * 2 + "hola")

    def test_lo_que_no_se_acepta(self):
        for pedido, cuenta in (({"para": "f", "texto": "x"}, ""), ({"para": "", "texto": "x"}, "m"),
                               ({"para": "f", "texto": "  "}, "m"), ({"para": "f", "texto": "x" * 60_001}, "m")):
            with self.subTest(pedido=str(pedido)[:40], cuenta=cuenta), self.assertRaises(ep.CorreoInvalido):
                ep.correo(pedido, cuenta)


if __name__ == "__main__":
    unittest.main()
