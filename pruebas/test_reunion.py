"""`telar reunion`: el mensaje, el proyecto, el nombre del tab y la plantilla configurable."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar.config import REUNION_POR_DEFECTO, ErrorDeConfig, escribir_clave
from telar.ordenes import reunion

UNIDADES = [
    "operacion/proyectos/anasac-adopcion-ia",
    "operacion/proyectos/valgesta-adopcion-ia",
    "conocimiento/proyectos/anasac-diagnostico",
    "negocio/pipeline/walmart-c3",
]


class ElProyecto(Prueba):
    def test_la_palabra_del_titulo_encuentra_la_carpeta(self):
        self.assertEqual(reunion.proyecto_para("coordinación interna valgesta", UNIDADES),
                         "operacion/proyectos/valgesta-adopcion-ia")

    def test_entre_empates_gana_la_primera_del_perfil(self):
        self.assertEqual(reunion.proyecto_para("Coordinación interna ANASAC", UNIDADES),
                         "operacion/proyectos/anasac-adopcion-ia")

    def test_y_antes_la_que_tiene_hilo_vivo(self):
        self.assertEqual(
            reunion.proyecto_para("ANASAC", UNIDADES, {"anasac-diagnostico"}),
            "conocimiento/proyectos/anasac-diagnostico",
        )

    def test_las_palabras_de_siempre_no_encuentran_nada(self):
        self.assertEqual(reunion.proyecto_para("Coordinación interna semanal", UNIDADES), "")


class ElMensaje(Prueba):
    def test_el_de_fabrica_es_el_de_flow(self):
        self.assertEqual(
            reunion.mensaje(REUNION_POR_DEFECTO, titulo="Comité", hora="15:00",
                            proyecto="operacion/proyectos/x"),
            "/preparar-reunion Comité (hoy 15:00) · proyecto: operacion/proyectos/x",
        )

    def test_sin_proyecto_se_quita_la_cola(self):
        self.assertEqual(reunion.mensaje(REUNION_POR_DEFECTO, titulo="Comité", hora="15:00"),
                         "/preparar-reunion Comité (hoy 15:00)")

    def test_una_plantilla_propia_con_enlace(self):
        self.assertEqual(
            reunion.mensaje("Prepárame «{titulo}» ({enlace})", titulo="Comité", hora="9:00", enlace="https://m"),
            "Prepárame «Comité» (https://m)",
        )

    def test_un_marcador_desconocido_queda_tal_cual(self):
        self.assertEqual(reunion.mensaje("{titulo} {sala}", titulo="A", hora="1:00"), "A {sala}")


class ElNombreDelTab(Prueba):
    def test_se_queda_con_lo_que_distingue(self):
        self.assertEqual(reunion.nombre_del_tab("Coordinación interna ANASAC", "12:00"), "◷ 12:00 ANASAC")

    def test_si_no_queda_nada_usa_el_titulo(self):
        self.assertEqual(reunion.nombre_del_tab("Daily", "9:00"), "◷ 9:00 Daily")


class LaPlantillaConfigurable(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "config.toml"
        self.ruta.write_text('sesion = "x"\n\n[agente]\nnombre = "claude-code"\ncarpeta = "~/Vida"\n\n[intervalos]\nficha = 30\n')

    def test_por_defecto_la_de_flow(self):
        self.assertEqual(mod_config.cargar(self.ruta).agente.reunion, REUNION_POR_DEFECTO)

    def test_se_escribe_dentro_de_su_tabla_sin_tocar_lo_demas(self):
        escribir_clave("agente", "reunion", "/mi-skill {titulo}", self.ruta)
        cfg = mod_config.cargar(self.ruta)
        self.assertEqual(cfg.agente.reunion, "/mi-skill {titulo}")
        self.assertEqual(cfg.agente.carpeta, "~/Vida")
        self.assertEqual(cfg.intervalos.ficha, 30)

    def test_cambiarla_otra_vez_no_la_duplica(self):
        escribir_clave("agente", "reunion", "uno", self.ruta)
        escribir_clave("agente", "reunion", "dos", self.ruta)
        self.assertEqual(self.ruta.read_text().count("reunion ="), 1)
        self.assertEqual(mod_config.cargar(self.ruta).agente.reunion, "dos")

    def test_borrarla_vuelve_a_la_de_fabrica(self):
        escribir_clave("agente", "reunion", "uno", self.ruta)
        escribir_clave("agente", "reunion", None, self.ruta)
        self.assertEqual(mod_config.cargar(self.ruta).agente.reunion, REUNION_POR_DEFECTO)

    def test_sin_la_tabla_la_crea(self):
        self.ruta.write_text('sesion = "x"\n')
        escribir_clave("agente", "reunion", "uno", self.ruta)
        self.assertEqual(mod_config.cargar(self.ruta).agente.reunion, "uno")

    def test_una_plantilla_vacia_en_el_archivo_es_un_error(self):
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"agente": {"reunion": "  "}})


if __name__ == "__main__":
    unittest.main()
