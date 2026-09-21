"""Leer un documento como lo declara el perfil: los seis tipos, y lo que falta."""

from __future__ import annotations

import unittest
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import lectura
from telar.perfil import PERFIL_MINIMO, Arquetipo, Seccion
from telar.perfil import cargar as cargar_perfil

FARO = EJEMPLO / "proyectos" / "faro" / "README.md"


class ElEjemplo(Prueba):
    def setUp(self):
        super().setUp()
        self.perfil = cargar_perfil(EJEMPLO)
        self.arquetipo = self.perfil.arquetipo("proyecto")

    def test_el_titulo_sale_del_encabezado(self):
        ficha = lectura.leer(FARO, self.arquetipo)
        self.assertEqual(ficha.titulo, "Faro")

    def test_el_estado_es_el_primer_parrafo_y_para_ahi(self):
        ficha = lectura.leer(FARO, self.arquetipo)
        self.assertTrue(ficha.estado.startswith("La lámpara nueva llegó"))
        self.assertNotIn("Segundo párrafo", ficha.estado)

    def test_las_casillas_traen_su_marca(self):
        ficha = lectura.leer(FARO, self.arquetipo)
        self.assertEqual(len(ficha.pendientes), 4)
        self.assertTrue(ficha.pendientes[0].hecho)
        self.assertTrue(ficha.pendientes[1].en_curso)
        self.assertFalse(ficha.pendientes[2].hecho or ficha.pendientes[2].en_curso)

    def test_las_secciones_que_telar_no_conoce_quedan_en_secciones(self):
        ficha = lectura.leer(FARO, self.arquetipo)
        self.assertIn("esperando", ficha.secciones)
        self.assertEqual(len(ficha.secciones["esperando"]), 2)
        self.assertEqual(ficha.secciones["ficha"]["Entrega"], "2026-06-30")

    def test_una_seccion_requerida_que_falta_se_dice(self):
        arboleda = EJEMPLO / "proyectos" / "arboleda" / "README.md"
        ficha = lectura.leer(arboleda, self.arquetipo)
        self.assertIn("estado", ficha.nota)
        self.assertFalse(ficha.vacia)  # el resto se leyó igual

    def test_un_documento_que_no_existe_lo_dice_y_no_revienta(self):
        ficha = lectura.leer(EJEMPLO / "no" / "existe.md", self.arquetipo)
        self.assertTrue(ficha.vacia)
        self.assertIn("no existe", ficha.nota)


class SinPerfil(Prueba):
    """La convención mínima: sin encabezados declarados, lo primero que calce."""

    def test_titulo_estado_y_casillas_por_convencion(self):
        arquetipo = PERFIL_MINIMO.arquetipo("proyecto")
        texto = (
            "# Molino\n\nHay que rearmarlo antes del invierno.\n\n"
            "## Lo que sea\n\n- [ ] Conseguir madera\n- [x] Medir el eje\n"
        )
        ficha = lectura.parsear(texto, arquetipo)
        self.assertEqual(ficha.titulo, "Molino")
        self.assertEqual(ficha.estado, "Hay que rearmarlo antes del invierno.")
        self.assertEqual([p.texto for p in ficha.pendientes], ["Conseguir madera", "Medir el eje"])

    def test_el_front_matter_no_se_toma_por_el_primer_parrafo(self):
        arquetipo = PERFIL_MINIMO.arquetipo("proyecto")
        texto = "---\nactualizado: 2026-09-01\n---\n\n# Faro\n\nEl estado de verdad.\n"
        ficha = lectura.parsear(texto, arquetipo)
        self.assertEqual(ficha.estado, "El estado de verdad.")


class Tipos(Prueba):
    """Cada tipo devuelve lo suyo, y el encabezado ancla dónde mirar."""

    TEXTO = (
        "# Título\n\nPreámbulo.\n\n"
        "## Estado\n\nVa bien.\n\n### Detalle\n\nSubsección que pertenece al estado.\n\n"
        "## Tabla\n\n| Campo | Valor |\n|---|---|\n| Cliente | La costa |\n| Vence | mañana |\n\n"
        "## Cosas\n\n- una\n- otra\n- tercera\n"
    )

    def arquetipo(self, *secciones: Seccion) -> Arquetipo:
        return Arquetipo(nombre="x", ruta="*/", secciones=secciones)

    def test_texto_se_lleva_las_subsecciones(self):
        a = self.arquetipo(Seccion(nombre="estado", tipo="texto", encabezado=r"^##\s+Estado"))
        ficha = lectura.parsear(self.TEXTO, a)
        self.assertIn("Subsección", ficha.estado)

    def test_parrafo_para_en_el_primer_corte(self):
        a = self.arquetipo(Seccion(nombre="estado", tipo="parrafo", encabezado=r"^##\s+Estado"))
        self.assertEqual(lectura.parsear(self.TEXTO, a).estado, "Va bien.")

    def test_tabla_da_clave_valor_sin_la_cabecera(self):
        a = self.arquetipo(Seccion(nombre="t", tipo="tabla", encabezado=r"^##\s+Tabla"))
        self.assertEqual(
            lectura.parsear(self.TEXTO, a).secciones["t"],
            {"Cliente": "La costa", "Vence": "mañana"},
        )

    def test_lista_respeta_el_maximo(self):
        a = self.arquetipo(Seccion(nombre="c", tipo="lista", encabezado=r"^##\s+Cosas", maximo=2))
        self.assertEqual(lectura.parsear(self.TEXTO, a).secciones["c"], ("una", "otra"))

    def test_linea_toma_el_grupo_del_encabezado(self):
        a = self.arquetipo(Seccion(nombre="titulo", tipo="linea", encabezado=r"^#\s+(.+)$"))
        self.assertEqual(lectura.parsear(self.TEXTO, a).titulo, "Título")

    def test_una_seccion_que_no_esta_no_inventa_nada(self):
        a = self.arquetipo(Seccion(nombre="otra", tipo="parrafo", encabezado=r"^##\s+Otra"))
        self.assertNotIn("otra", lectura.parsear(self.TEXTO, a).secciones)

    def test_casillas_solo_cuenta_las_que_tienen_casilla(self):
        a = self.arquetipo(Seccion(nombre="pendientes", tipo="casillas", encabezado=r"^##\s+Cosas"))
        self.assertEqual(lectura.parsear(self.TEXTO, a).pendientes, ())


class Ubicar(Prueba):
    """De una ruta a su arquetipo: la clave es la unidad, no el documento."""

    def setUp(self):
        super().setUp()
        self.perfil = cargar_perfil(EJEMPLO)

    def test_el_indice_lista_carpetas_y_archivos(self):
        mapa = lectura.indice(self.perfil, EJEMPLO)
        self.assertIn("proyectos/faro", mapa)
        self.assertIn("notas/madera.md", mapa)
        self.assertEqual(mapa["proyectos/faro"][1].name, "README.md")

    def test_ubicar_acepta_relativa_y_absoluta(self):
        for ruta in ("proyectos/faro", str(EJEMPLO / "proyectos" / "faro"), EJEMPLO / "proyectos" / "faro"):
            arquetipo, documento = lectura.ubicar(self.perfil, EJEMPLO, ruta)
            self.assertIsNotNone(arquetipo, ruta)
            self.assertTrue(Path(documento).is_file())

    def test_una_carpeta_que_el_perfil_no_declara_no_se_adivina(self):
        self.assertEqual(lectura.ubicar(self.perfil, EJEMPLO, "notas"), (None, None))


if __name__ == "__main__":
    unittest.main()
