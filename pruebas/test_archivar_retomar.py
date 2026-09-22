"""Archivar y retomar un hilo, y de qué carpetas salen los hilos."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar.agente.claude_code import ClaudeCode
from telar.config import Config, ErrorDeConfig, Hilos, escribir_clave
from telar.ordenes import tejer
from telar.perfil import Arquetipo


class ElIdSeSabeAlAbrir(Prueba):
    def test_claude_nace_con_el_id_que_elige_telar(self):
        palabras, sid = ClaudeCode(Config()).nuevo_con_id()
        self.assertEqual(palabras[1:], ["--session-id", sid])
        self.assertEqual(len(sid), 36)

    def test_con_mensaje_el_mensaje_va_al_final(self):
        palabras, sid = ClaudeCode(Config()).nuevo_con_id("/preparar-reunion X")
        self.assertEqual(palabras[-1], "/preparar-reunion X")
        self.assertIn(sid, palabras)

    def test_dos_conversaciones_no_comparten_id(self):
        a = ClaudeCode(Config()).nuevo_con_id()[1]
        b = ClaudeCode(Config()).nuevo_con_id()[1]
        self.assertNotEqual(a, b)


class DeQueCarpetas(Prueba):
    UNIDADES = {u: (None, None) for u in [
        "operacion/proyectos/anasac", "operacion/proyectos/copec",
        "negocio/pipeline/aguas", "negocio/pipeline/roche", "conocimiento/ia",
    ]}

    def test_por_turnos_en_el_orden_en_que_se_nombran(self):
        self.assertEqual(
            tejer._de_directorios(self.UNIDADES, ("negocio/pipeline", "operacion/proyectos"), 10),
            ["negocio/pipeline/aguas", "operacion/proyectos/anasac",
             "negocio/pipeline/roche", "operacion/proyectos/copec"],
        )

    def test_la_segunda_carpeta_aparece_aunque_la_primera_llene_el_tope(self):
        muchas = {f"operacion/proyectos/p{i:02d}": (None, None) for i in range(36)}
        muchas["negocio/pipeline/aguas"] = (None, None)
        elegidas = tejer._de_directorios(muchas, ("operacion/proyectos", "negocio/pipeline"), 8)
        self.assertIn("negocio/pipeline/aguas", elegidas)
        self.assertEqual(len(elegidas), 8)

    def test_el_tope_corta(self):
        self.assertEqual(len(tejer._de_directorios(self.UNIDADES, ("operacion/proyectos", "negocio/pipeline"), 3)), 3)

    def test_un_directorio_no_calza_con_su_vecino_de_nombre_parecido(self):
        unidades = {"operacion/proyectos-viejos/x": (None, None), "operacion/proyectos/y": (None, None)}
        self.assertEqual(tejer._de_directorios(unidades, ("operacion/proyectos",), 10), ["operacion/proyectos/y"])


class LaConfiguracionDeHilos(Prueba):
    def test_por_defecto_lo_de_siempre(self):
        self.assertEqual(mod_config.desde_dict({}).hilos, Hilos(directorios=(), tope=8))

    def test_se_leen_directorios_y_tope(self):
        cfg = mod_config.desde_dict({"hilos": {"directorios": ["a/b/", "c"], "tope": 12}})
        self.assertEqual(cfg.hilos, Hilos(directorios=("a/b", "c"), tope=12))

    def test_una_carpeta_que_sale_de_la_raiz_es_un_error(self):
        for malo in (["../afuera"], ["/absoluta"]):
            with self.assertRaises(ErrorDeConfig):
                mod_config.desde_dict({"hilos": {"directorios": malo}})

    def test_se_escribe_como_lista(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.toml"
            ruta.write_text('sesion = "x"\n')
            escribir_clave("hilos", "directorios", ["negocio/pipeline", "operacion/proyectos"], ruta)
            escribir_clave("hilos", "tope", 5, ruta)
            self.assertEqual(mod_config.cargar(ruta).hilos,
                             Hilos(directorios=("negocio/pipeline", "operacion/proyectos"), tope=5))


class LoQueEmpiezaConGuion(Prueba):
    def test_una_carpeta_con_guion_bajo_no_es_unidad(self):
        # `_perdidos` en el pipeline de brinca: además telar reserva las claves con _ en su
        # estado, y un hilo así llamado perdía su conversación al archivarlo.
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            for c in ("faro", "_perdidos", ".oculta"):
                (raiz / "p" / c).mkdir(parents=True)
                (raiz / "p" / c / "README.md").write_text("# x\n")
            docs = Arquetipo(nombre="p", ruta="p/*/").documentos(raiz)
            self.assertEqual([d.parent.name for d in docs], ["faro"])


if __name__ == "__main__":
    unittest.main()
