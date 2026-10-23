"""Los hilos son privados por defecto y se pueden hacer públicos (telar.estado, `telar hilo publicar|privar`):
solo los públicos salen en el directorio que ven las otras personas."""

from __future__ import annotations

import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import entre_personas
from telar import estado as e


class LosPublicos(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.est = e.Estado(Path(self.tmp.name))

    def test_privado_por_defecto_publicar_y_privar(self):
        self.assertEqual(self.est.publicos(), set())
        self.est.publicar("Faro")
        self.est.publicar("Faro")  # dos veces, una
        self.assertEqual(self.est.publicos(), {"Faro"})
        self.est.privar("Faro")
        self.assertEqual(self.est.publicos(), set())

    def test_se_mueve_con_el_renombre_y_se_va_al_olvidarlo(self):
        self.est.publicar("Faro")
        self.est.renombrar("Faro", "Faro Norte")
        self.assertEqual(self.est.publicos(), {"Faro Norte"})
        self.est.olvidar("Faro Norte")
        self.assertEqual(self.est.publicos(), set())

    def test_lo_que_va_en_la_foto_y_en_el_directorio(self):
        self.est.publicar("Faro")
        foto = self.est.foto(tope=600)
        self.assertEqual(foto["publicos"], {"Faro"})
        hilos = e.vestir([e.Hilo(id="@1", nombre="Faro"), e.Hilo(id="@2", nombre="Diario")], **foto)
        self.assertEqual([(h.nombre, h.publico) for h in hilos], [("Faro", True), ("Diario", False)])
        d = entre_personas.directorio({"hilos": [{"nombre": h.nombre, "publico": h.publico} for h in hilos]}, "ana")
        self.assertEqual([x["nombre"] for x in d["hilos"]], ["Faro"])


class ElCorreoAUnPrivado(Prueba):
    """A un hilo privado no le llega correo de otra persona, y se le contesta como si no existiera."""

    def existe(self, valor):
        import asyncio
        import json
        from types import SimpleNamespace

        from telar.ordenes import nodo as mod_nodo

        class Kv:
            async def get(self, clave):
                if valor is None:
                    raise type("KeyNotFoundError", (Exception,), {})()
                return SimpleNamespace(value=json.dumps(valor).encode())

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.kv, n.persona = Kv(), "ana"
        return asyncio.run(n._hilo_existe("faro"))

    def test_publico_privado_y_sin_hilo(self):
        self.assertTrue(self.existe({"nombre": "Faro", "publico": True}))
        self.assertFalse(self.existe({"nombre": "Faro", "publico": False}))
        self.assertFalse(self.existe({"nombre": "Faro"}))  # de un telar de antes: privado
        self.assertFalse(self.existe(None))
