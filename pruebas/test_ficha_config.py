"""La sección [ficha] existe, elige el proveedor y no apaga nada si viene rota."""
import unittest

from pruebas import comun  # noqa: F401  (pone src/ en el path)

from telar import config as mod_config
from telar.ordenes import _comun
from telar.proveedores import estado as prov_estado


class Seccion(unittest.TestCase):
    def test_por_defecto_es_documento(self):
        cfg = mod_config.Config()
        self.assertEqual(cfg.ficha.nombre, "documento")
        self.assertIsInstance(_comun.fuente_ficha(cfg), prov_estado.Documento)

    def test_declara_el_proveedor_comando(self):
        cfg = mod_config.desde_dict(
            {"ficha": {"proveedor": "comando", "comando": ["cat", "{documento}"], "tiempo": 5}}
        )
        self.assertEqual(cfg.ficha.nombre, "comando")
        self.assertIsInstance(_comun.fuente_ficha(cfg), prov_estado.Comando)

    def test_opciones_del_documento_llegan(self):
        cfg = mod_config.desde_dict({"ficha": {"cascada": {"resumen": ["estado"]}, "maximo": 3}})
        fuente = _comun.fuente_ficha(cfg)
        self.assertIsInstance(fuente, prov_estado.Documento)
        self.assertEqual(fuente.maximo, 3)

    def test_proveedor_desconocido_no_apaga_la_ficha(self):
        cfg = mod_config.desde_dict({"ficha": {"proveedor": "inventado"}})
        self.assertIsInstance(_comun.fuente_ficha(cfg), prov_estado.Documento)


if __name__ == "__main__":
    unittest.main()
