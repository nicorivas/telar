"""`telar actuar` (telar.servicios.actuar): el prompt sobre una entidad, y lo que se rechaza antes de mandar nada."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar.servicios import ErrorDeServicio
from telar.servicios.actuar import actuar, prompt_de


class ElPrompt(Prueba):
    def test_una_linea_con_la_skill_lo_pedido_y_el_contexto(self):
        o = {"titulo": "Faro", "direccion": "proyecto:proyectos/faro", "tipo": "proyecto", "id": "proyectos/faro",
             "estado": "en curso"}
        p = prompt_de(o, skill="pm", nota="revisa\nel plan")
        self.assertEqual(p, "/pm revisa el plan [contexto: Faro · proyecto:proyectos/faro · carpeta proyectos/faro · "
                            "estado en curso; más con `telar objeto proyecto:proyectos/faro`]")
        self.assertNotIn("\n", p)
        # sin skill, solo lo pedido; una skill escrita con su / no la duplica
        self.assertTrue(prompt_de(o, nota="hola").startswith("hola [contexto: Faro"))
        self.assertTrue(prompt_de(o, skill="/pm").startswith("/pm [contexto:"))


class LoQueSeRechaza(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name) / "ejemplo"
        shutil.copytree(EJEMPLO, raiz)
        os.environ["TELAR_RAIZ"] = str(raiz)
        from telar.cli import Contexto
        from telar.config import cargar

        self.ctx = Contexto(config=cargar(None))

    def test_sin_skill_ni_nota_no_hay_que_pedir(self):
        with self.assertRaises(ErrorDeServicio) as e:
            actuar(self.ctx, "proyecto:proyectos/faro", a="Faro")
        self.assertEqual(e.exception.codigo, 422)

    def test_una_entidad_sin_hilo_propio_necesita_a_quien(self):
        with self.assertRaises(ErrorDeServicio) as e:
            actuar(self.ctx, "archivo:proyectos/faro/README.md", nota="léelo")
        self.assertEqual(e.exception.codigo, 422)
        self.assertIn("a quién", str(e.exception))

    def test_un_destino_que_no_existe_es_un_404(self):
        with self.assertRaises(ErrorDeServicio) as e:
            actuar(self.ctx, "proyecto:proyectos/faro", nota="hola", a="nadie-se-llama-asi")
        self.assertEqual(e.exception.codigo, 404)


class AUnAgente(Prueba):
    def test_se_le_encarga_por_su_nombre(self):
        from types import SimpleNamespace
        from unittest import mock

        from telar.servicios import actuar as mod

        agente = SimpleNamespace(nombre="Gestión", clave="gestion")
        tel = SimpleNamespace(mux=None, viva=True, aviso="")
        objeto = SimpleNamespace(model_dump=lambda: {"titulo": "Faro", "direccion": "proyecto:p/faro", "tipo": "proyecto",
                                                     "id": "p/faro", "estado": ""})
        with mock.patch("telar.objetos.ver", return_value=objeto), \
                mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
                mock.patch("telar.ordenes.pendiente.destino_elegido", return_value=(None, None, agente)), \
                mock.patch("telar.servicios.encargos.encargar") as encargar:
            r = mod.actuar(SimpleNamespace(), "proyecto:p/faro", a="Gestión", nota="revisa")
        self.assertEqual(encargar.call_args.args[1], "Gestión")
        self.assertEqual((r.destino, r.como), ("Gestión", "encargado"))


if __name__ == "__main__":
    unittest.main()
