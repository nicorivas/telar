"""`telar config --calendario`: conectar la agenda sin editar el archivo a mano."""

from __future__ import annotations

import stat
import tempfile
import tomllib
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar.config import ErrorDeConfig, escribir_calendario, fuente_calendario

URL = "https://calendar.google.com/calendar/ical/x%40y/private-abc/basic.ics"

EJEMPLO = """# La configuración de telar.
multiplexor = "tmux"
sesion = "brinca"

# [proveedores.calendario]
# activo = true
# ics = "https://ejemplo/calendario.ics"

[agente]
nombre = "claude-code"
"""


class ConectarCalendario(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "config.toml"

    def _leer(self):
        return mod_config.cargar(self.ruta)

    def test_agrega_la_tabla_y_respeta_el_resto(self):
        self.ruta.write_text(EJEMPLO)
        escribir_calendario(URL, self.ruta)
        cfg = self._leer()
        cal = cfg.proveedores["calendario"]
        self.assertEqual(cal.opciones, {"tipo": "ics", "url": URL})
        self.assertEqual(cfg.agente.nombre, "claude-code")
        texto = self.ruta.read_text()
        self.assertIn("# [proveedores.calendario]", texto)  # el ejemplo comentado sigue ahí
        self.assertIn('sesion = "brinca"', texto)

    def test_conectar_otra_vez_reemplaza_en_vez_de_duplicar(self):
        self.ruta.write_text(EJEMPLO)
        escribir_calendario(URL, self.ruta)
        escribir_calendario("webcal://otra/basic.ics", self.ruta)
        texto = self.ruta.read_text()
        self.assertEqual(texto.count("\n[proveedores.calendario]"), 1)
        self.assertEqual(self._leer().proveedores["calendario"].opciones["url"], "https://otra/basic.ics")
        self.assertEqual(self._leer().agente.nombre, "claude-code")

    def test_una_tabla_que_sigue_despues_no_se_pierde(self):
        self.ruta.write_text('[proveedores.calendario]\ntipo = "ninguno"\n\n[agente]\nnombre = "x"\n')
        escribir_calendario(URL, self.ruta)
        cfg = self._leer()
        self.assertEqual(cfg.agente.nombre, "x")
        self.assertEqual(cfg.proveedores["calendario"].opciones["tipo"], "ics")

    def test_queda_legible_solo_por_su_duenno(self):
        self.ruta.write_text(EJEMPLO)
        escribir_calendario(URL, self.ruta)
        self.assertEqual(stat.S_IMODE(self.ruta.stat().st_mode), 0o600)

    def test_sin_archivo_lo_crea(self):
        escribir_calendario(URL, self.ruta)
        self.assertEqual(tomllib.loads(self.ruta.read_text())["proveedores"]["calendario"]["url"], URL)

    def test_un_archivo_ics_local(self):
        ics = Path(self.tmp.name) / "agenda.ics"
        ics.write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        escribir_calendario(str(ics), self.ruta)
        self.assertEqual(self._leer().proveedores["calendario"].opciones["archivo"], str(ics))

    def test_lo_que_no_es_url_ni_archivo_no_escribe_nada(self):
        self.ruta.write_text(EJEMPLO)
        with self.assertRaises(ErrorDeConfig):
            escribir_calendario("mi calendario", self.ruta)
        self.assertEqual(self.ruta.read_text(), EJEMPLO)

    def test_webcal_es_https(self):
        self.assertEqual(fuente_calendario("webcal://a/b.ics"), ("url", "https://a/b.ics"))


if __name__ == "__main__":
    unittest.main()
