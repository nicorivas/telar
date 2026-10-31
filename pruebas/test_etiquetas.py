"""Las etiquetas de un hilo (telar.estado, `telar hilo etiquetas`) y los modos que filtran por ellas (telar.modos)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config, modos
from telar import estado as e
from telar.modelo import normalizar_etiquetas


class LasEtiquetas(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.est = e.Estado(Path(self.tmp.name))

    def test_se_escriben_en_minusculas_sin_repetir_y_ninguna_las_quita(self):
        self.assertEqual(normalizar_etiquetas("Trabajo, #cliente trabajo"), ("trabajo", "cliente"))
        self.assertEqual(normalizar_etiquetas(["Personal"]), ("personal",))
        self.assertEqual(normalizar_etiquetas("ninguna"), ())
        self.assertEqual(normalizar_etiquetas(""), ())
        with self.assertRaises(ValueError):
            normalizar_etiquetas("trabajo, ¡esto!")

    def test_ponerlas_reemplaza_y_vacio_las_quita(self):
        self.assertEqual(self.est.etiquetas(), {})
        self.est.etiquetar("Faro", "trabajo, cliente")
        self.est.etiquetar("Diario", "personal")
        self.assertEqual(self.est.etiquetas(), {"Faro": ("trabajo", "cliente"), "Diario": ("personal",)})
        self.est.etiquetar("Faro", "trabajo")
        self.assertEqual(self.est.etiquetas()["Faro"], ("trabajo",))
        self.est.etiquetar("Faro", "ninguna")
        self.assertNotIn("Faro", self.est.etiquetas())

    def test_se_mueven_con_el_renombre_y_se_van_al_olvidarlo(self):
        self.est.etiquetar("Faro", "trabajo")
        self.est.renombrar("Faro", "Faro Norte")
        self.assertEqual(self.est.etiquetas(), {"Faro Norte": ("trabajo",)})
        self.est.olvidar("Faro Norte")
        self.assertEqual(self.est.etiquetas(), {})

    def test_van_en_la_foto_y_visten_al_hilo(self):
        self.est.etiquetar("Faro", "trabajo")
        foto = self.est.foto(tope=600)
        hilos = e.vestir([e.Hilo(id="@1", nombre="Faro"), e.Hilo(id="@2", nombre="Diario")], **foto)
        self.assertEqual([(h.nombre, h.etiquetas) for h in hilos], [("Faro", ("trabajo",)), ("Diario", ())])


class LosModosQueFiltran(Prueba):
    def test_un_modo_guarda_sus_etiquetas_y_que_hacer_con_los_sin_etiqueta(self):
        v = modos.validar("trabajo", {"nombre": "trabajo", "etiquetas": "Trabajo, brinca", "sin_etiqueta": "no-se-ven"})
        self.assertEqual(v["valores"], {"etiquetas": "trabajo,brinca", "sin_etiqueta": "no-se-ven"})
        with self.assertRaises(config.ErrorDeConfig):
            modos.validar("trabajo", {"etiquetas": "¡no!"})
        with self.assertRaises(config.ErrorDeConfig):
            modos.validar("trabajo", {"sin_etiqueta": "a veces"})

    def test_estandar_no_filtra_y_los_demas_lo_heredan(self):
        c = config.desde_dict({"modos": {"trabajo": {"etiquetas": "trabajo"}}})
        m = {x["clave"]: x["valores"] for x in modos.todos(c)}
        self.assertEqual((m["estandar"]["etiquetas"], m["estandar"]["sin_etiqueta"]), ("", "se-ven"))
        self.assertEqual(m["foco"]["etiquetas"], "")
        self.assertEqual((m["trabajo"]["etiquetas"], m["trabajo"]["sin_etiqueta"]), ("trabajo", "se-ven"))
