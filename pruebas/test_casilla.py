"""La casilla local de un hilo: dejar sin duplicar, entregar por los ganchos, marcar entregado."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import casilla as m


class LaCasilla(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = SimpleNamespace(estado=Path(self.tmp.name))

    def test_un_mismo_id_no_se_duplica_ni_despues_de_entregado(self):
        self.assertTrue(m.dejar(self.config, "Faro", {"id": "a1", "texto": "hola"}))
        self.assertFalse(m.dejar(self.config, "Faro", {"id": "a1", "texto": "hola"}))
        m.para_gancho(self.config, "Faro", "Stop")
        self.assertFalse(m.dejar(self.config, "Faro", {"id": "a1", "texto": "hola"}))

    def test_stop_no_deja_parar_y_entrega_entero(self):
        largo = "comienzo " + "x" * 5000 + " final"
        m.dejar(self.config, "Faro", {"id": "a1", "de": "Gestión", "texto": largo, "tipo": "encargo"})
        salida = json.loads(m.para_gancho(self.config, "Faro", "Stop"))
        self.assertEqual(salida["decision"], "block")
        self.assertIn("[encargo de Gestión", salida["reason"])
        self.assertIn("comienzo", salida["reason"])
        self.assertIn(" final", salida["reason"])
        self.assertEqual(m.para_gancho(self.config, "Faro", "Stop"), "")  # ya entró

    def test_user_prompt_submit_lo_agrega_como_contexto(self):
        m.dejar(self.config, "Faro", {"id": "a1", "texto": "canción"})
        salida = json.loads(m.para_gancho(self.config, "Faro", "UserPromptSubmit"))
        self.assertEqual(salida["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("canción", salida["hookSpecificOutput"]["additionalContext"])

    def test_lo_que_no_cabe_queda_para_el_turno_siguiente(self):
        for i in range(3):
            m.dejar(self.config, "Faro", {"id": f"a{i}", "texto": "y" * (m.MAX_ENTREGA // 2)})
        m.para_gancho(self.config, "Faro", "Stop")
        self.assertEqual(len(m.pendientes(self.config, "Faro")), 2)

    def test_sin_pendientes_no_imprime_nada(self):
        self.assertEqual(m.para_gancho(self.config, "Nadie", "Stop"), "")
