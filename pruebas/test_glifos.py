"""Los estilos de los glifos (telar.glifos): el catálogo, los de fábrica, `[glifos.<estilo>]`, y guardarlos o quitarlos."""

from __future__ import annotations

import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config, glifos, modos


class LosEstilos(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "config.toml"
        self.ruta.write_text("")

    def test_base_es_lo_elegido_y_cada_parametro_tiene_su_valor_de_fabrica(self):
        base = glifos.todos(config.desde_dict({}))["base"]
        self.assertEqual((base["paleta"], base["celda"], base["transicion"], base["corte"]), ("fluo", 8, "absorber", .35))
        self.assertEqual((base["gesto_cuartos"], base["gesto_punto"], base["hilo_paleta"], base["espera"]), ("rueda", "salto", "mocha", "cadena"))
        self.assertEqual(set(base), {p["clave"] for p in glifos.catalogo()})

    def test_lo_que_no_sirve(self):
        for malo in ({"celda": 3}, {"paleta": "sepia"}, {"gesto_cruz": "baile"}, {"inventado": 1}, {"ritmo": "rápido"}):
            with self.assertRaises(config.ErrorDeConfig):
                glifos.validar("x", malo)
        self.assertEqual(glifos.validar("x", {"celda": "12", "grano": "0,2"}), {"celda": 12, "grano": .2})

    def test_guardar_escribe_lo_distinto_de_fabrica_y_un_estilo_toma_de_base_lo_que_no_dice(self):
        glifos.guardar(self.ruta, "base", {**glifos.BASE, "celda": 12})
        glifos.guardar(self.ruta, "tenue", {"intensidad": .3})
        c = config.cargar(self.ruta)
        t = glifos.todos(c)
        self.assertEqual((t["base"]["celda"], t["tenue"]["celda"], t["tenue"]["intensidad"]), (12, 12, .3))
        self.assertNotIn("paleta", self.ruta.read_text())
        self.assertTrue(glifos.borrar(self.ruta, "tenue"))
        self.assertEqual(list(glifos.todos(config.cargar(self.ruta))), ["base"])

    def test_un_modo_elige_su_estilo(self):
        self.assertEqual(modos.validar("riso", {"estilo": "tenue"})["valores"], {"estilo": "tenue"})
        with self.assertRaises(config.ErrorDeConfig):
            modos.validar("riso", {"estilo": "Con Espacios"})
