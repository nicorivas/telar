"""Eliminar a un agente y traerlo de vuelta (telar.agentes.eliminar, restaurar): nada se borra."""

from __future__ import annotations

import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import agentes, config


class EliminarAgentes(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.ruta = raiz / "config.toml"
        self.ruta.write_text(f'raiz = "{raiz}"\n\n[agentes]\ncarpeta = "agentes"\n\n[agentes.faro]\nen = "servidor"\n\n[terminal]\ncolumnas = 100\n')
        self.config = config.cargar(self.ruta)
        agentes.crear(self.config, self.ruta, "Faro", para="cuidar la costa")
        agentes.crear(self.config, self.ruta, "Gestión")

    def test_eliminar_aparta_su_carpeta_y_su_config_y_restaurar_los_devuelve(self):
        self.assertEqual(sorted(a.clave for a in agentes.descubrir(self.config)), ["faro", "gestion"])
        r = agentes.eliminar(self.config, self.ruta, "faro")
        self.assertTrue(r["config_guardada"])
        self.assertEqual([a.clave for a in agentes.descubrir(config.cargar(self.ruta))], ["gestion"])
        self.assertNotIn("[agentes.faro]", self.ruta.read_text())
        self.assertIn("columnas = 100", self.ruta.read_text())   # lo demás no se toca
        self.assertTrue((Path(r["carpeta"]) / "CLAUDE.md").is_file())
        self.assertEqual([x["clave"] for x in agentes.eliminados(self.config)], ["faro"])

        agentes.restaurar(self.config, self.ruta, "faro")
        c = config.cargar(self.ruta)
        self.assertEqual(sorted(a.clave for a in agentes.descubrir(c)), ["faro", "gestion"])
        self.assertIn('[agentes.faro]\nen = "servidor"', self.ruta.read_text())
        self.assertEqual(agentes.eliminados(c), [])

    def test_por_su_nombre_y_lo_que_no_existe(self):
        agentes.eliminar(self.config, self.ruta, "GESTION")
        with self.assertRaises(ValueError):
            agentes.eliminar(self.config, self.ruta, "nadie")
        with self.assertRaises(ValueError):
            agentes.restaurar(self.config, self.ruta, "nadie")


class AbrirSinMotor(Prueba):
    """Abrir a un agente sin motor elegido lo dice (y cómo elegirlo); el nodo nota cuando se elige."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.ruta = raiz / "config.toml"
        self.ruta.write_text(f'raiz = "{raiz}"\n\n[agentes]\ncarpeta = "agentes"\n')
        self.config = config.cargar(self.ruta)
        agentes.crear(self.config, self.ruta, "Faro")

    def test_sin_motor_dice_como_elegirlo(self):
        from types import SimpleNamespace

        from telar.servicios import ErrorDeServicio
        from telar.servicios import agentes as servicio

        with self.assertRaises(ErrorDeServicio) as e:
            servicio.abrir_aqui(SimpleNamespace(config=config.cargar(self.ruta)), "faro")
        self.assertEqual(e.exception.codigo, 409)
        self.assertIn("motor", str(e.exception))

    def test_el_nodo_relee_la_configuracion_y_nota_el_motor(self):
        import os
        from types import SimpleNamespace
        from unittest import mock

        from telar.cli import Contexto
        from telar.ordenes import nodo as mod_nodo

        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.ctx = Contexto(config=config.cargar(self.ruta))
        n.config = n.ctx.config
        n.anotar = lambda *_: None
        self.assertFalse(n.releer_config())   # la primera vez solo mira
        self.ruta.write_text(self.ruta.read_text() + '\n[agente]\nnombre = "claude-code"\n')
        os.utime(self.ruta, (1e9, 1e9 + 5))
        with mock.patch.object(n, "_agentes_de_aqui", return_value=[]):
            self.assertTrue(n.releer_config())
        self.assertEqual(n.config.agente.nombre, "claude-code")
        self.assertEqual(n.ctx.config.agente.nombre, "claude-code")
        self.assertEqual(n.abiertos_siempre, {})
