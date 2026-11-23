"""`telar hilos` dice en qué máquina vive cada hilo, de aquí o de las otras.

El caso que lo trajo: desde el servidor, un agente buscó un hilo del laptop en `telar hilos --json`
(con y sin `--red`), miró `hilos` y su `remoto`, vacío en todos, y concluyó que el hilo no existía.
Estaba en `otras_maquinas`, que `hilos` no mezcla. Ahora cada hilo de las dos listas dice su
`maquina` con la misma clave, la lista dice de qué máquina es, y el texto avisa que sin `--red` falta
el resto.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar import cli
from telar import espejo as mod_espejo
from telar.servicios import hilos as servicio

#: lo que el bus tiene registrado: un hilo del laptop, y uno de aquí que el bus también conoce
REGISTRO = {
    "Telar": {"nombre": "Telar", "maquina": "laptop", "vivo": True, "atencion": "termino"},
    "Faro": {"nombre": "Faro", "maquina": "servidor", "vivo": False},
}


class HilosConMaquina(Prueba):
    """Este telar es «servidor», con bus; el laptop tiene «Telar»."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        os.environ["TELAR_ESTADO"] = str(base / "estado")
        os.environ["TELAR_RAIZ"] = str(EJEMPLO)
        os.environ["TELAR_SESION"] = f"telar-pruebas-{uuid.uuid4().hex[:8]}"
        self.config = base / "config.toml"
        self.escribir_config('[bus]\nurl = "nats://127.0.0.1:1"\nmaquina = "servidor"\n')
        previo = os.environ.get("COLUMNS")
        os.environ["COLUMNS"] = "120"
        self.addCleanup(lambda: os.environ.pop("COLUMNS", None) if previo is None
                        else os.environ.__setitem__("COLUMNS", previo))
        codigo, _, error = self.correr("hilo", "vincular", "proyectos/faro", "--hilo", "Faro")
        self.assertEqual(codigo, 0, error)

    def escribir_config(self, texto: str) -> None:
        self.config.write_text(texto, encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(self.config)

    def correr(self, *argv: str) -> tuple[int, str, str]:
        salida, error = io.StringIO(), io.StringIO()
        # el bus, de mentira: ni la lista sin `--red` ni la prueba tienen que salir a la red
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error), \
                mock.patch.object(mod_bus, "estados", return_value=REGISTRO) as estados, \
                mock.patch.object(mod_espejo, "leer_todos", return_value=[{"nombre": "laptop", "en_linea": True}]):
            codigo = cli.main(list(argv))
        self.estados = estados
        return codigo, salida.getvalue(), error.getvalue()

    def json_de(self, *argv: str) -> dict:
        codigo, salida, error = self.correr(*argv)
        self.assertEqual(codigo, 0, error)
        return json.loads(salida)

    def test_cada_hilo_de_aqui_dice_esta_maquina(self):
        datos = self.json_de("hilos", "--json")
        self.assertEqual(datos["maquina"], "servidor")
        self.assertEqual({h["nombre"]: h["maquina"] for h in datos["hilos"]}, {"Faro": "servidor"})
        self.assertEqual(datos["hilos"][0]["remoto"], "")  # `remoto` no cambia: vacío es «aquí»

    def test_sin_red_no_le_pregunta_al_bus_ni_trae_las_otras(self):
        datos = self.json_de("hilos", "--json")
        self.estados.assert_not_called()
        self.assertNotIn("otras_maquinas", datos)

    def test_con_red_un_hilo_del_laptop_se_encuentra_con_su_maquina(self):
        """El caso del reporte: desde el servidor, «Telar» del laptop sale, y con su máquina."""
        datos = self.json_de("hilos", "--json", "--red")
        donde = {h["nombre"]: h["maquina"] for h in datos["hilos"] + datos["otras_maquinas"]}
        self.assertEqual(donde, {"Faro": "servidor", "Telar": "laptop"})
        # `hilos` sigue siendo solo esta máquina: el del laptop va aparte
        self.assertEqual([h["nombre"] for h in datos["hilos"]], ["Faro"])
        self.assertEqual(datos["otras_maquinas"][0]["direccion"], "hilo:Telar@laptop")
        self.assertEqual(datos["aviso_red"], "")

    def test_la_ventana_de_un_hilo_de_otra_maquina_dice_la_de_alla(self):
        self.assertEqual(servicio._con_maquina({"remoto": "laptop"}, "servidor"), {"remoto": "laptop", "maquina": "laptop"})
        self.assertEqual(servicio._con_maquina({"remoto": ""}, "servidor"), {"remoto": "", "maquina": "servidor"})
        # un ssh que telar no armó: se sabe que es de otra, no de cuál
        self.assertEqual(servicio._con_maquina({"remoto": "?"}, "servidor")["maquina"], "?")

    def test_el_texto_dice_de_que_maquina_es_la_lista_y_que_faltan_las_otras(self):
        codigo, salida, error = self.correr("hilos")
        self.assertEqual(codigo, 0, error)
        self.assertIn("en servidor", salida.splitlines()[0])
        self.assertIn("--red", salida.splitlines()[-1])

    def test_con_red_el_texto_muestra_las_otras_y_no_repite_el_aviso(self):
        codigo, salida, error = self.correr("hilos", "--red")
        self.assertEqual(codigo, 0, error)
        self.assertIn("laptop · 1 hilos", salida)
        self.assertIn("Telar", salida)
        self.assertNotIn("`telar hilos --red`", salida)

    def test_sin_bus_no_avisa_de_otras_maquinas(self):
        self.escribir_config("")
        codigo, salida, error = self.correr("hilos")
        self.assertEqual(codigo, 0, error)
        self.assertNotIn("--red", salida)
        # y la máquina igual se nombra: la de aquí, como la llamaría el bus
        self.assertEqual(self.json_de("hilos", "--json")["maquina"], mod_bus.maquina(_config()))

    def test_la_ayuda_dice_que_sin_red_es_solo_esta_maquina(self):
        codigo, salida, _ = self.correr("hilos", "--help")
        self.assertEqual(codigo, 0)
        self.assertIn("esta máquina", salida)
        self.assertIn("otras_maquinas", salida)


def _config():
    from telar.config import cargar

    return cargar()
