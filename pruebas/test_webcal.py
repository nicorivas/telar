import unittest
from unittest import mock

from telar import webcal

EVENTO = {"id": "ev1", "texto": "Comité", "cuando": "2026-10-08T10:00", "fin": "2026-10-08T11:00:00-03:00", "todo_el_dia": False,
          "url": "", "asistentes": [], "lugar": ""}


class Escribir(unittest.TestCase):
    def _con_agenda(self):
        return mock.patch.object(webcal, "dia", return_value=(200, {"agenda": [EVENTO], "plan": None}))

    def test_el_dia_y_el_id_se_validan_antes_de_tocar_nada(self):
        self.assertEqual(webcal.nota(None, None, {"dia": "ayer", "id": "ev1", "texto": "x"})[0], 400)
        self.assertEqual(webcal.nota(None, None, {"dia": "2026-10-08", "id": "", "texto": "x"})[0], 400)
        self.assertEqual(webcal.nota(None, None, [])[0], 400)

    def test_un_evento_que_no_esta_en_la_agenda_no_se_acepta(self):
        with self._con_agenda():
            self.assertEqual(webcal.nota(None, None, {"dia": "2026-10-08", "id": "otro", "texto": "x"})[0], 404)

    def test_la_nota_lleva_titulo_y_hora_de_la_agenda_y_no_de_la_pagina(self):
        webcal._ultimo[0] = 0.0
        with self._con_agenda(), mock.patch.object(webcal, "_json", return_value={"ok": True}) as j:
            codigo, r = webcal.nota(None, None, {"dia": "2026-10-08", "id": "ev1", "texto": "hola", "titulo": "falso"})
        self.assertEqual((codigo, r["ok"]), (200, True))
        args = j.call_args.args[0]
        self.assertEqual(args[args.index("--titulo") + 1], "Comité")
        self.assertEqual(args[args.index("--inicio") + 1], "10:00")

    def test_una_carpeta_que_no_es_proyecto_no_abre_reunion(self):
        with self._con_agenda():
            codigo, _ = webcal.reunion(None, None, {"dia": "2026-10-08", "id": "ev1", "proyecto": "../../etc"}, {"a/b"})
        self.assertEqual(codigo, 404)


if __name__ == "__main__":
    unittest.main()
