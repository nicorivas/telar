"""El perfil: la convención mínima, el del ejemplo, y qué se rechaza."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import perfil as p


class Minimo(Prueba):
    def test_sin_archivo_rige_la_convencion_minima(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        perf = p.cargar(Path(tmp.name))
        self.assertTrue(perf.minimo)
        self.assertEqual([a.nombre for a in perf.arquetipos], ["proyecto"])

    def test_la_convencion_minima_es_primer_encabezado_parrafo_y_casillas(self):
        arq = p.PERFIL_MINIMO.arquetipo("proyecto")
        assert arq is not None
        self.assertEqual(arq.seccion("titulo").tipo, "linea")
        self.assertEqual(arq.seccion("estado").tipo, "parrafo")
        self.assertEqual(arq.seccion("pendientes").tipo, "casillas")
        # Sin anclar: se busca lo PRIMERO del documento que calce.
        self.assertIsNone(arq.seccion("estado").encabezado)
        self.assertIsNone(arq.seccion("pendientes").encabezado)

    def test_un_perfil_pedido_a_mano_que_no_existe_es_un_error(self):
        with self.assertRaises(p.ErrorDePerfil):
            p.cargar(EJEMPLO, ruta=Path("/no/existe/telar-perfil.yaml"))


class Ejemplo(Prueba):
    def setUp(self):
        super().setUp()
        self.perfil = p.cargar(EJEMPLO)

    def test_el_ejemplo_trae_su_propio_perfil(self):
        self.assertFalse(self.perfil.minimo)
        self.assertEqual(self.perfil.nombre, "taller")
        self.assertEqual(self.perfil.version, p.VERSION)

    def test_declara_proyectos_y_notas(self):
        self.assertEqual(sorted(a.nombre for a in self.perfil.arquetipos), ["nota", "proyecto"])

    def test_un_arquetipo_por_carpeta_y_otro_por_archivo(self):
        self.assertTrue(self.perfil.arquetipo("proyecto").por_carpeta)
        self.assertFalse(self.perfil.arquetipo("nota").por_carpeta)

    def test_los_documentos_del_ejemplo_existen(self):
        docs = self.perfil.documentos(EJEMPLO)
        self.assertEqual(
            sorted(d.parent.name for d in docs["proyecto"]),
            ["arboleda", "faro", "molino"],
        )
        self.assertEqual([d.name for d in docs["nota"]], ["madera.md"])
        for lista in docs.values():
            for doc in lista:
                self.assertTrue(doc.is_file(), doc)

    def test_las_secciones_se_declaran_con_su_tipo(self):
        proyecto = self.perfil.arquetipo("proyecto")
        self.assertEqual(proyecto.seccion("pendientes").tipo, "casillas")
        self.assertEqual(proyecto.seccion("pendientes").maximo, 6)
        self.assertTrue(proyecto.seccion("estado").requerida)
        self.assertEqual(proyecto.seccion("ficha").tipo, "tabla")

    def test_el_encabezado_se_compila_como_regex(self):
        titulo = self.perfil.arquetipo("proyecto").seccion("titulo")
        casa = titulo.patron.match("# Faro")
        self.assertIsNotNone(casa)
        self.assertEqual(casa.group(1), "Faro")

    def test_las_acciones_son_listas_de_palabras(self):
        revisar = self.perfil.accion("revisar")
        self.assertIsInstance(revisar.comando, tuple)
        self.assertEqual(revisar.donde, "hilo")
        self.assertEqual(self.perfil.accion("contar").donde, "raiz")
        self.assertTrue(self.perfil.accion("limpiar").confirmar)


class Quejas(Prueba):
    def malo(self, datos: dict) -> str:
        with self.assertRaises(p.ErrorDePerfil) as caja:
            p.desde_dict(datos)
        return str(caja.exception)

    def base(self, **arq) -> dict:
        cuerpo = {"ruta": "proyectos/*/"}
        cuerpo.update(arq)
        return {"version": 1, "arquetipos": {"proyecto": cuerpo}}

    def test_un_perfil_sin_arquetipos_no_declara_nada(self):
        self.assertIn("arquetipos", self.malo({"version": 1, "arquetipos": {}}))

    def test_una_version_que_no_es_la_nuestra_se_rechaza(self):
        self.assertIn("version", self.malo({"version": 99, "arquetipos": {"x": {"ruta": "*/"}}}))

    def test_una_ruta_que_sale_de_la_raiz_se_rechaza(self):
        self.assertIn("no salir de ella", self.malo(self.base(ruta="../afuera/*/")))

    def test_una_ruta_absoluta_se_rechaza(self):
        self.assertIn("relativa", self.malo(self.base(ruta="/etc/*/")))

    def test_un_tipo_de_seccion_desconocido_se_rechaza(self):
        datos = self.base(secciones={"estado": {"tipo": "adivinanza"}})
        self.assertIn("tipo", self.malo(datos))

    def test_una_regex_invalida_se_rechaza(self):
        datos = self.base(secciones={"estado": {"tipo": "linea", "encabezado": "^## ("}})
        self.assertIn("regular", self.malo(datos))

    def test_un_comando_en_una_sola_cadena_se_rechaza(self):
        datos = self.base()
        datos["acciones"] = [{"nombre": "x", "comando": "rm -rf /"}]
        self.assertIn("lista de palabras", self.malo(datos))

    def test_un_donde_desconocido_se_rechaza(self):
        datos = self.base()
        datos["acciones"] = [{"nombre": "x", "comando": ["ls"], "donde": "afuera"}]
        self.assertIn("donde", self.malo(datos))

    def test_una_clave_que_telar_no_conoce_se_rechaza(self):
        self.assertIn("inventada", self.malo(self.base(inventada=1)))


if __name__ == "__main__":
    unittest.main()
