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
        agentes.crear(self.config, self.ruta, "Secretaría")

    def test_eliminar_aparta_su_carpeta_y_su_config_y_restaurar_los_devuelve(self):
        self.assertEqual(sorted(a.clave for a in agentes.descubrir(self.config)), ["faro", "secretaria"])
        r = agentes.eliminar(self.config, self.ruta, "faro")
        self.assertTrue(r["config_guardada"])
        self.assertEqual([a.clave for a in agentes.descubrir(config.cargar(self.ruta))], ["secretaria"])
        self.assertNotIn("[agentes.faro]", self.ruta.read_text())
        self.assertIn("columnas = 100", self.ruta.read_text())   # lo demás no se toca
        self.assertTrue((Path(r["carpeta"]) / "CLAUDE.md").is_file())
        self.assertEqual([x["clave"] for x in agentes.eliminados(self.config)], ["faro"])

        agentes.restaurar(self.config, self.ruta, "faro")
        c = config.cargar(self.ruta)
        self.assertEqual(sorted(a.clave for a in agentes.descubrir(c)), ["faro", "secretaria"])
        self.assertIn('[agentes.faro]\nen = "servidor"', self.ruta.read_text())
        self.assertEqual(agentes.eliminados(c), [])

    def test_por_su_nombre_y_lo_que_no_existe(self):
        agentes.eliminar(self.config, self.ruta, "SECRETARIA")
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


class SoloAqui(Prueba):
    """Un agente con su carpeta aquí que vive en otra máquina, donde no está: abrirlo o eliminarlo lo dice así (y qué
    hacer), no con el «no hay un agente» de allá; la vista de agentes lo marca."""

    def setUp(self):
        super().setUp()
        from types import SimpleNamespace

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        raiz = Path(self.tmp.name)
        self.ruta = raiz / "config.toml"
        self.ruta.write_text(f'raiz = "{raiz}"\n\n[agentes]\ncarpeta = "agentes"\nen = "servidor"\n')
        agentes.crear(config.cargar(self.ruta), self.ruta, "Faro")
        self.ctx = SimpleNamespace(config=config.cargar(self.ruta))

    def _alla(self, respuesta):
        from unittest import mock

        return mock.patch("telar.bus.pedir", return_value=respuesta)

    def test_el_texto_dice_donde_esta_por_que_y_las_dos_salidas(self):
        from telar.servicios import agentes as servicio

        texto = servicio.solo_aqui(self.ctx, "faro", "servidor")
        self.assertIn("Faro está solo en esta máquina", texto)
        self.assertIn("los agentes viven en servidor ([agentes] en)", texto)
        self.assertIn('[agentes.faro] en = "aqui"', texto)
        self.assertEqual(servicio.solo_aqui(self.ctx, "nadie", "servidor"), "")

    def test_abrir_y_eliminar_lo_explican(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import agentes as servicio

        with self._alla({"ok": False, "error": "no hay un agente «faro»", "codigo": 404}), \
                self.assertRaises(ErrorDeServicio) as e:
            servicio.abrir(self.ctx, "faro", "servidor")
        self.assertEqual(e.exception.codigo, 409)
        self.assertIn("solo en esta máquina", str(e.exception))
        # sin decir la máquina: la de [agentes] en; y la respuesta de un telar de antes (409 con el texto) también
        with self._alla({"ok": False, "error": "no hay un agente «faro»", "codigo": 409}), \
                self.assertRaises(ErrorDeServicio) as e:
            servicio.eliminar(self.ctx, "faro")
        self.assertIn("solo en esta máquina", str(e.exception))
        self.assertTrue((Path(self.tmp.name) / "agentes" / "faro").is_dir())   # aquí no se tocó nada

    def test_otra_falla_de_alla_pasa_tal_cual(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import agentes as servicio

        with self._alla({"ok": False, "error": "servidor no respondió", "codigo": 504}), \
                self.assertRaises(ErrorDeServicio) as e:
            servicio.abrir(self.ctx, "faro", "servidor")
        self.assertEqual((e.exception.codigo, str(e.exception)), (504, "servidor no respondió"))

    def test_eliminar_aqui_lo_que_no_esta_es_404(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import agentes as servicio

        with self.assertRaises(ErrorDeServicio) as e:
            servicio.eliminar_aqui(self.ctx, "nadie")
        self.assertEqual(e.exception.codigo, 404)

    def test_la_vista_de_agentes_lo_marca(self):
        from unittest import mock

        from telar.servicios import agentes as servicio

        with mock.patch.object(servicio, "estado_local", side_effect=lambda ctx: []), \
                mock.patch("telar.bus.hay_bus", return_value=True):
            with self._alla({"ok": True, "agentes": []}):
                x = servicio.lista(self.ctx).model_dump()["agentes"][0]
            self.assertIn("solo en esta máquina", x["solo_aqui"])
            self.assertNotIn("sin_noticias", x)
            with self._alla({"ok": False, "error": "no respondió"}):
                x = servicio.lista(self.ctx).model_dump()["agentes"][0]
            self.assertTrue(x["sin_noticias"])
            self.assertNotIn("solo_aqui", x)
