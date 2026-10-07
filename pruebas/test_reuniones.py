"""A qué proyecto pertenece una reunión (`telar.reuniones`) y quiénes asisten (el iCal)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import reuniones as m
from telar.proveedores import calendario


class Deducir(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.unidades = ["proyectos/faro-diagnostico", "proyectos/molino-academia", "proyectos/molino-taller",
                         "proyectos/puerto-gobernanza", "proyectos/casa-interna"]
        for u in self.unidades:
            (self.raiz / u).mkdir(parents=True)
            # todos los proyectos nombran a alguien de la casa; solo faro nombra a su contraparte
            extra = "Contraparte: Ana Pérez <ana@faro.cl>" if "faro" in u else ""
            (self.raiz / u / "README.md").write_text(f"# {u}\nEquipo: luis@miempresa.com\n{extra}\n")

    def test_el_titulo_raro_suma_mas_que_el_comun(self):
        c = m.candidatos(self.raiz, self.unidades, "Comité Molino", [])
        self.assertEqual({x["nombre"] for x in c}, {"molino-academia", "molino-taller"})
        self.assertEqual(m.decidir(c), "")  # dos iguales: se pregunta

    def test_un_asistente_nombrado_en_un_readme_decide(self):
        c = m.candidatos(self.raiz, self.unidades, "Seguimiento", ["Ana Pérez <ana@faro.cl>", "luis@miempresa.com"])
        self.assertEqual(c[0]["nombre"], "faro-diagnostico")
        self.assertEqual(m.decidir(c), "proyectos/faro-diagnostico")

    def test_los_de_la_casa_no_cuentan(self):
        c = m.candidatos(self.raiz, self.unidades, "Seguimiento", ["luis@miempresa.com"])
        self.assertEqual(c, [])

    def test_la_eleccion_se_recuerda_por_serie(self):
        cfg = SimpleNamespace(estado=self.raiz / "estado")
        m.recordar(cfg, "Weekly Faro 7-oct", "proyectos/faro-diagnostico")
        self.assertEqual(m.recordado(cfg, "Weekly Faro 14-oct"), "proyectos/faro-diagnostico")
        self.assertEqual(m.recordado(cfg, "Otra reunión"), "")


class AsistentesDelIcal(Prueba):
    def test_el_duenio_del_calendario_no_es_un_asistente(self):
        ics = ("BEGIN:VCALENDAR\nX-WR-CALNAME:yo@miempresa.com\nBEGIN:VEVENT\nUID:x1\nSUMMARY:Comité\n"
               "DTSTART:20261007T130000Z\nDTEND:20261007T133000Z\n"
               "ATTENDEE;CN=Yo Mismo:mailto:yo@miempresa.com\nATTENDEE;CN=Ana Pérez:mailto:ana@faro.cl\n"
               "END:VEVENT\nEND:VCALENDAR\n")
        self.assertEqual(calendario.leer_ics(ics)[0].asistentes, ["Ana Pérez <ana@faro.cl>"])
