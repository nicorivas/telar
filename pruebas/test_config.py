"""La configuración: valores por defecto, archivo, entorno y quejas."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg


class SinArchivo(Prueba):
    def test_los_valores_por_defecto_alcanzan(self):
        c = cfg.cargar()
        self.assertEqual(c.multiplexor, "tmux")
        self.assertEqual(c.sesion, "telar")
        self.assertIsNone(c.origen)
        self.assertEqual(c.proveedores, {})
        self.assertEqual(c.intervalos.refresco, 1.0)

    def test_sin_proveedores_declarados_no_hay_ninguno_activo(self):
        self.assertEqual(cfg.cargar().proveedores_activos(), ())

    def test_el_perfil_por_defecto_es_el_de_la_raiz(self):
        c = cfg.cargar()
        self.assertEqual(c.ruta_perfil, c.raiz / "telar-perfil.yaml")

    def test_una_ruta_pedida_a_mano_que_no_existe_es_un_error(self):
        with self.assertRaises(cfg.ErrorDeConfig):
            cfg.cargar(Path("/no/existe/config.toml"))


class ConArchivo(Prueba):
    def escribir(self, texto: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name) / "config.toml"
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def test_lee_lo_que_dice_el_archivo(self):
        ruta = self.escribir(
            """
            multiplexor = "zellij"
            sesion = "taller"
            raiz = "~/trabajo"

            [intervalos]
            refresco = 2.5

            [proveedores.agenda]
            activo = true
            calendario = "trabajo"

            [proveedores.tareas]
            activo = false
            """
        )
        c = cfg.cargar(ruta)
        self.assertEqual(c.multiplexor, "zellij")
        self.assertEqual(c.sesion, "taller")
        self.assertEqual(c.raiz, Path.home() / "trabajo")
        self.assertEqual(c.intervalos.refresco, 2.5)
        self.assertEqual(c.intervalos.ficha, 60.0)  # lo no dicho queda por defecto
        self.assertEqual(c.origen, ruta)

    def test_solo_los_proveedores_activos_salen_activos(self):
        ruta = self.escribir(
            """
            [proveedores.agenda]
            activo = true
            [proveedores.tareas]
            activo = false
            """
        )
        activos = cfg.cargar(ruta).proveedores_activos()
        self.assertEqual([p.nombre for p in activos], ["agenda"])

    def test_las_opciones_del_proveedor_pasan_tal_cual(self):
        ruta = self.escribir('[proveedores.agenda]\ncalendario = "trabajo"\ndias = 7\n')
        agenda = cfg.cargar(ruta).proveedores["agenda"]
        self.assertTrue(agenda.activo)
        self.assertEqual(agenda.opciones, {"calendario": "trabajo", "dias": 7})

    def test_la_variable_de_entorno_pisa_el_archivo(self):
        ruta = self.escribir('sesion = "del-archivo"\n')
        os.environ["TELAR_SESION"] = "del-entorno"
        self.assertEqual(cfg.cargar(ruta).sesion, "del-entorno")

    def test_telar_config_dice_donde_buscar(self):
        ruta = self.escribir('sesion = "apuntada"\n')
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.assertEqual(cfg.ruta_config(), ruta)
        self.assertEqual(cfg.cargar().sesion, "apuntada")


class Quejas(Prueba):
    def malo(self, texto: str) -> str:
        with self.assertRaises(cfg.ErrorDeConfig) as caja:
            cfg.desde_dict(__import__("tomllib").loads(texto))
        return str(caja.exception)

    def test_un_multiplexor_desconocido_se_rechaza(self):
        self.assertIn("multiplexor", self.malo('multiplexor = "screen"'))

    def test_una_clave_que_no_existe_se_rechaza(self):
        self.assertIn("inventada", self.malo("inventada = 1"))

    def test_un_intervalo_dentro_de_intervalos_que_no_existe_se_rechaza(self):
        self.assertIn("intervalos.rapidez", self.malo("[intervalos]\nrapidez = 1"))

    def test_un_intervalo_negativo_se_rechaza(self):
        self.assertIn("positivo", self.malo("[intervalos]\nrefresco = -1"))

    def test_un_toml_mal_formado_se_dice_con_el_nombre_del_archivo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name) / "config.toml"
        ruta.write_text("esto = no es toml", encoding="utf-8")
        with self.assertRaises(cfg.ErrorDeConfig) as caja:
            cfg.cargar(ruta)
        self.assertIn("config.toml", str(caja.exception))


if __name__ == "__main__":
    unittest.main()
