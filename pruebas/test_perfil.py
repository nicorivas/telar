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
        # tres formas, para que un repositorio sirva sin declarar nada: carpetas en la
        # raíz, carpetas un nivel adentro (proyectos/…) y el README de la raíz
        self.assertEqual(
            [a.nombre for a in perf.arquetipos], ["proyecto", "proyecto anidado", "repositorio"]
        )
        self.assertEqual([a.ruta for a in perf.arquetipos], ["*/", "*/*/", "README.md"])

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
            p.cargar(EJEMPLO, ruta=Path("/no/existe/.telar/perfil.yaml"))


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


class LaCarpetaTelar(Prueba):
    """El perfil vive en `.telar/perfil.yaml`; `.telar/local.yaml`, de cada persona, se lee encima."""

    PERFIL = """version: 1
nombre: equipo
arquetipos:
  proyecto:
    ruta: "proyectos/*/"
    etiqueta: proyecto
  deal:
    ruta: "deals/*/"
"""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / ".telar").mkdir()
        (self.raiz / ".telar" / "perfil.yaml").write_text(self.PERFIL, encoding="utf-8")

    def test_el_perfil_se_lee_de_la_carpeta(self):
        perfil = p.cargar(self.raiz)
        self.assertEqual(perfil.nombre, "equipo")
        self.assertEqual(perfil.origen, self.raiz / ".telar" / "perfil.yaml")

    def test_el_archivo_de_antes_ya_no_cuenta(self):
        (self.raiz / ".telar" / "perfil.yaml").unlink()
        (self.raiz / "telar-perfil.yaml").write_text(self.PERFIL, encoding="utf-8")
        self.assertIs(p.cargar(self.raiz), p.PERFIL_MINIMO)

    def test_lo_local_se_mezcla_encima(self):
        (self.raiz / ".telar" / "local.yaml").write_text(
            "nombre: el mío\narquetipos:\n  proyecto:\n    etiqueta: mío\n  deal: null\n", encoding="utf-8")
        perfil = p.cargar(self.raiz)
        self.assertEqual(perfil.nombre, "el mío")
        por_nombre = {a.nombre: a for a in perfil.arquetipos}
        self.assertEqual(set(por_nombre), {"proyecto"})  # el null quita el deal
        self.assertEqual(por_nombre["proyecto"].etiqueta, "mío")  # se mezcla: la ruta sigue siendo la del equipo
        self.assertEqual(por_nombre["proyecto"].ruta, "proyectos/*/")

    def test_un_perfil_pedido_a_mano_no_lee_lo_local(self):
        otro = self.raiz / "otro.yaml"
        otro.write_text(self.PERFIL, encoding="utf-8")
        (self.raiz / ".telar" / "local.yaml").write_text("nombre: el mío\n", encoding="utf-8")
        self.assertEqual(p.cargar(self.raiz, ruta=otro).nombre, "equipo")

    def test_un_local_que_no_es_un_mapa_es_un_error(self):
        (self.raiz / ".telar" / "local.yaml").write_text("- una lista\n", encoding="utf-8")
        with self.assertRaises(p.ErrorDePerfil):
            p.cargar(self.raiz)

    def test_mezclar(self):
        self.assertEqual(p.mezclar({"a": 1, "b": {"c": 2, "d": 3}, "e": [1]}, {"b": {"c": 9, "d": None}, "e": [2], "f": 4}),
                         {"a": 1, "b": {"c": 9}, "e": [2], "f": 4})


if __name__ == "__main__":
    unittest.main()