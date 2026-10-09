"""Un proveedor que vive en otra máquina (`en`): se le pide allá, y sus acciones corren allá."""

from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import alla, bus as mod_bus, config as mod_config
from telar.modelo import Item


class EnOtraMaquina(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prov = mod_config.Proveedor(nombre="tareas", opciones={"tipo": "comando", "comando": ["x"], "en": "servidor"})
        self.cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "e",
                                     bus=mod_config.Bus(url="nats://x:1", maquina="laptop"),
                                     proveedores={"tareas": self.prov})

    def test_donde_vive(self):
        self.assertEqual(alla.donde(self.cfg, self.prov), "servidor")
        aqui = mod_config.Config(raiz=self.cfg.raiz, estado=self.cfg.estado, bus=mod_config.Bus(url="nats://x:1", maquina="servidor"))
        self.assertEqual(alla.donde(aqui, self.prov), "")                       # es esta misma
        self.assertEqual(alla.donde(mod_config.Config(raiz=self.cfg.raiz, estado=self.cfg.estado), self.prov), "")  # sin bus

    def test_un_item_va_y_vuelve(self):
        i = Item(proveedor="tareas", id="T7", titulo="x", cuando=datetime(2026, 10, 9, 0, 0), clase="tarea",
                 datos={"dueno": "Ana", "destacada": True})
        self.assertEqual(alla.item_de_dict(alla.item_a_dict(i)), i)

    def test_se_le_pide_alla_y_si_no_responde_se_lee_aqui_y_se_dice(self):
        respuesta = {"ok": True, "items": [alla.item_a_dict(Item(proveedor="tareas", id="T9", titulo="de allá"))], "fallas": []}
        with mock.patch.object(mod_bus, "pedir", return_value=respuesta) as pedir, \
                mock.patch("telar.proveedores.consultar", return_value=([], [])):
            items, fallas = alla.consultar(self.cfg, [self.prov], date(2026, 10, 9))
        self.assertEqual([i.id for i in items], ["T9"])
        self.assertEqual(pedir.call_args[0][1:3], ("servidor", "proveedor"))
        aqui = [Item(proveedor="tareas", id="T1", titulo="copia")]
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "no respondió"}), \
                mock.patch("telar.proveedores.consultar", side_effect=lambda ps, d: (aqui if ps else [], [])):
            items, fallas = alla.consultar(self.cfg, [self.prov], date(2026, 10, 9))
        self.assertEqual([i.id for i in items], ["T1"])
        self.assertTrue(any("atrasada" in f for f in fallas))

    def test_una_accion_corre_alla_y_si_no_responde_no_se_corre_aqui(self):
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "codigo": 0, "salida": '{"hecho": "✓"}\n', "error_salida": ""}) as pedir, \
                redirect_stdout(io.StringIO()) as salida:
            codigo = alla.tarea_alla(self.cfg, "servidor", ["T7", "--accion", "3", "--json"])
        self.assertEqual((codigo, salida.getvalue()), (0, '{"hecho": "✓"}\n'))
        self.assertEqual(pedir.call_args[0][3], {"argv": ["T7", "--accion", "3", "--json"]})
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "no respondió"}), \
                mock.patch("subprocess.run") as correr, redirect_stderr(io.StringIO()):
            self.assertNotEqual(alla.tarea_alla(self.cfg, "servidor", ["T7", "--accion", "3"]), 0)
        correr.assert_not_called()

    def test_telar_tarea_se_reenvia_si_el_proveedor_vive_alla(self):
        from telar.ordenes import tarea

        with mock.patch.object(alla, "tarea_alla", return_value=0) as reenvio:
            tarea.main(["T7", "--accion", "1"], SimpleNamespace(config=self.cfg))
        self.assertEqual(reenvio.call_args[0][1:], ("servidor", ["T7", "--accion", "1"]))
