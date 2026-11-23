"""El CHANGELOG por fragmentos (telar.changelog): la declaración, cómo se lee un fragmento y cómo se junta en
[Unreleased]. Lo que hace `telar hilo fusionar` con ellos, en test_ramas.py («ElChangelog»)."""

from __future__ import annotations

import unittest

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import changelog

DECL = changelog.declaracion("archivo: CHANGELOG.md\ncarpeta: changelog.d\n")


class LaDeclaracion(Prueba):
    def test_sin_archivo_no_hay(self):
        self.assertIsNone(changelog.declaracion(None))

    def test_lo_que_se_omite_tiene_su_valor(self):
        self.assertEqual(DECL, {"archivo": "CHANGELOG.md", "carpeta": "changelog.d",
                                "secciones": list(changelog.SECCIONES), "ancho": None, "negrita": False})
        d = changelog.declaracion("archivo: docs/CHANGES.md\ncarpeta: cambios/\nsecciones: [Nuevo, Arreglado]\n"
                                  "ancho: 100\n")
        self.assertEqual((d["archivo"], d["carpeta"], d["secciones"], d["ancho"]),
                         ("docs/CHANGES.md", "cambios", ["Nuevo", "Arreglado"], 100))

    def test_lo_que_no_se_entiende(self):
        for texto in ("- una lista\n", "archivo: CHANGELOG.md\n", "carpeta: x\n", "archivo: ../afuera.md\ncarpeta: x\n",
                      "archivo: /abs.md\ncarpeta: x\n", "archivo: a.md\ncarpeta: x\nancho: mucho\n",
                      "archivo: a.md\ncarpeta: x\nsecciones: Added\n", "archivo: [a\n"):
            with self.subTest(texto=texto), self.assertRaises(changelog.ErrorDeChangelog):
                changelog.declaracion(texto)

    def test_que_es_un_fragmento(self):
        self.assertTrue(changelog.es_fragmento("changelog.d/calendario.md", DECL))
        for ruta in ("changelog.d/README.md", "changelog.d/notas.txt", "changelog.d/sub/x.md", "otra/x.md"):
            self.assertFalse(changelog.es_fragmento(ruta, DECL), ruta)


class ElFragmento(Prueba):
    def test_varias_secciones_y_entradas_sin_lineas_en_blanco(self):
        texto = ("\n### Fixed\n\n- **Uno.** a\n  b\n\n- **Dos.** c\n\n### Added\n- **Tres.**\n\n"
                 "### Fixed\n\n- **Cuatro.**\n")
        self.assertEqual(changelog.leer_fragmento(texto, "f.md", DECL),
                         {"Fixed": ["- **Uno.** a", "  b", "- **Dos.** c", "- **Cuatro.**"], "Added": ["- **Tres.**"]})

    def test_cada_problema_con_su_linea(self):
        with self.assertRaises(changelog.ErrorDeChangelog) as e:
            changelog.leer_fragmento("### Added\n\n  sangrada sin entrada\n## [1.0]\n- bien\n", "f.md", DECL)
        self.assertEqual([x.split(":")[1] for x in e.exception.errores], ["3", "4"])

    def test_una_seccion_mala_no_arrastra_sus_entradas(self):
        with self.assertRaises(changelog.ErrorDeChangelog) as e:
            changelog.leer_fragmento("### Otra\n\n- a\n- b\n", "f.md", DECL)
        self.assertEqual(len(e.exception.errores), 1)


CHANGELOG = "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n### Changed\n\n- viejo\n\n## [1.0.0]\n\n### Added\n\n- uno\n"


class Juntar(Prueba):
    def test_arriba_de_su_seccion_y_lo_demas_intacto(self):
        nuevo = changelog.juntar(CHANGELOG, [{"Changed": ["- a"]}, {"Changed": ["- b", "  b2"]}], DECL)
        self.assertEqual(nuevo, CHANGELOG.replace("### Changed\n\n- viejo", "### Changed\n\n- a\n- b\n  b2\n- viejo"))

    def test_las_secciones_que_faltan_en_su_orden(self):
        nuevo = changelog.juntar(CHANGELOG, [{"Security": ["- s"], "Added": ["- a"], "Fixed": ["- f"]}], DECL)
        self.assertIn("## [Unreleased]\n\n### Added\n\n- a\n\n### Changed\n\n- viejo\n\n### Fixed\n\n- f\n\n"
                      "### Security\n\n- s\n\n## [1.0.0]", nuevo)

    def test_sin_unreleased_ni_versiones(self):
        self.assertEqual(changelog.juntar("# Changelog\n\nIntro.\n\n", [{"Added": ["- a"]}], DECL),
                         "# Changelog\n\nIntro.\n\n## [Unreleased]\n\n### Added\n\n- a\n")

    def test_sin_nada_que_juntar_queda_igual(self):
        self.assertEqual(changelog.juntar(CHANGELOG, [], DECL), CHANGELOG)


if __name__ == "__main__":
    unittest.main()
