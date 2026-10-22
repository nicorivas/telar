"""Un id estable para las casillas de un documento (telar.vinetas): la primera vez que telar escribe una casilla
le pone `<!-- id: c-1a2b3c -->` al final de la línea, y desde ahí se la encuentra por ese id aunque el documento
cambie. Su dirección es `pendiente:<id>` (telar.objetos), con las acciones de `telar pendiente`. Un id que ya
está no se toca, ninguna otra línea cambia (ni sus bytes: `\\r\\n`, unicode) y si no se puede escribir, nada cambia."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)
from test_ordenes import EJEMPLO, Orden

from telar import lectura, vinetas
from telar.ordenes import _comun

ID = re.compile(r"<!-- id: (c-[0-9a-f]{6}) -->")


class ElIdDeUnaCasilla(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.doc = Path(self.tmp.name) / "README.md"

    def poner(self, contenido: str | bytes) -> bytes:
        crudo = contenido.encode() if isinstance(contenido, str) else contenido
        self.doc.write_bytes(crudo)
        return crudo

    def test_la_forma_no_se_confunde_con_una_tarea(self):
        ident = vinetas.nuevo_id("")
        self.assertRegex(ident, r"^c-[0-9a-f]{6}$")
        self.assertTrue(vinetas.FORMA_ID.fullmatch(ident))
        self.assertIsNone(vinetas.FORMA_ID.fullmatch("T84"))

    def test_al_escribirla_recibe_un_id_una_sola_vez_y_estable(self):
        self.poner("# Faro\n\n- [ ] Revisar el NDA\n- [ ] Llamar a Ana\n")
        n, ident = vinetas.escribir(self.doc, lambda l: vinetas.con_responsable(l, "Ana"), texto="Revisar el NDA")
        self.assertEqual(n, 3)
        texto = self.doc.read_text()
        self.assertEqual(texto.count("<!-- id:"), 1)
        self.assertIn(f"- [ ] Revisar el NDA @owner(Ana) <!-- id: {ident} -->\n", texto)
        # se relee igual, y una segunda escritura lo encuentra por el id y no pone otro
        self.assertEqual(vinetas.linea(self.doc, "", id=ident), 3)
        n, otra = vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar el NDA", id=ident)
        self.assertEqual((n, otra), (3, ident))
        self.assertEqual(self.doc.read_text().count("<!-- id:"), 1)
        self.assertIn(f"- [x] Revisar el NDA @owner(Ana) <!-- id: {ident} -->\n", self.doc.read_text())

    def test_la_lectura_lo_reconoce_y_el_texto_no_cambia(self):
        self.poner("## Pendientes\n\n- [ ] Revisar el NDA @owner(Ana) <!-- id: c-0a1b2c -->\n- [ ] Otra\n")
        lineas = self.doc.read_text().splitlines()
        p = lectura._casillas(lineas, 0, "pendientes")
        self.assertEqual([(x.texto, x.dueno, x.id_casilla, x.id) for x in p],
                         [("Revisar el NDA", "Ana", "c-0a1b2c", ""), ("Otra", "", "", "")])

    def test_un_id_que_ya_esta_no_se_reescribe(self):
        # el de una tarea, o uno escrito a mano: se usa tal cual, y no se agrega otro
        self.poner("- [ ] Revisar el NDA <!-- id: T84 -->\n")
        n, ident = vinetas.escribir(self.doc, lambda l: vinetas.con_responsable(l, "Ana"), texto="Revisar el NDA")
        self.assertEqual(ident, "T84")
        self.assertEqual(self.doc.read_text(), "- [ ] Revisar el NDA @owner(Ana) <!-- id: T84 -->\n")
        vinetas.escribir(self.doc, lambda l: vinetas.con_responsable(l, "none"), id="T84")
        self.assertEqual(self.doc.read_text(), "- [ ] Revisar el NDA <!-- id: T84 -->\n")

    def test_dos_casillas_iguales_reciben_ids_distintos(self):
        lineas = ["- [ ] Llamar\n", "- [ ] Llamar\n"]
        for i in range(2):
            lineas[i] = vinetas.con_id(lineas[i], vinetas.nuevo_id("".join(lineas)))
        ids = [vinetas.id_de(x) for x in lineas]
        self.assertEqual(len(set(ids)), 2)
        # aunque el azar repita uno que ya está en el documento
        with mock.patch.object(vinetas.secrets, "token_hex", side_effect=["0a0a0a", "0a0a0a", "0b0b0b"]):
            self.assertEqual(vinetas.nuevo_id("- [ ] Llamar <!-- id: c-0a0a0a -->\n"), "c-0b0b0b")
        # y una vez que una tiene id, las dos se distinguen por él aunque digan lo mismo
        self.poner("- [ ] Llamar <!-- id: c-0a0a0a -->\n- [ ] Llamar <!-- id: c-0b0b0b -->\n")
        self.assertEqual(vinetas.escribir(self.doc, vinetas.hecha, texto="Llamar", id="c-0b0b0b"), (2, "c-0b0b0b"))
        self.assertEqual(self.doc.read_text(), "- [ ] Llamar <!-- id: c-0a0a0a -->\n- [x] Llamar <!-- id: c-0b0b0b -->\n")

    def test_por_el_id_sigue_sirviendo_despues_de_insertar_lineas_arriba(self):
        self.poner("# Faro\n\n- [ ] Revisar el NDA\n")
        _, ident = vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar el NDA", abierta=True)
        self.doc.write_text("# Faro\n\nUn párrafo nuevo.\n\n- [ ] Revisar el NDA\n\n" + self.doc.read_text().split("\n\n", 1)[1])
        self.assertEqual(vinetas.linea(self.doc, "", id=ident), 7)
        with self.assertRaises(vinetas.ErrorDeVineta):
            vinetas.linea(self.doc, "Revisar el NDA")  # por el texto, ahora hay dos

    def test_el_resto_del_archivo_queda_byte_a_byte(self):
        crudo = ("\ufeff# Ñandú 🦤\r\n\r\nUn párrafo con\u2028separador y \x0c salto de página.\r\n"
                 "- [ ] Revisar el **NDA** 🧾 @deadline(2026-10-30)   \r\n- [x] Hecha\r\nSin salto al final").encode("utf-8")
        self.poner(crudo)
        n, ident = vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar el NDA 🧾")
        self.assertEqual(n, 4)
        despues = self.doc.read_bytes()
        antes_l, despues_l = crudo.split(b"\n"), despues.split(b"\n")
        self.assertEqual(len(antes_l), len(despues_l))
        self.assertEqual([x for i, x in enumerate(antes_l) if i != 3], [x for i, x in enumerate(despues_l) if i != 3])
        self.assertEqual(despues_l[3], f"- [x] Revisar el **NDA** 🧾 @deadline(2026-10-30) <!-- id: {ident} -->\r".encode())

    def test_si_no_se_puede_escribir_todo_queda_como_estaba(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("como root se escribe igual")
        crudo = self.poner("- [ ] Revisar el NDA\n")
        carpeta = self.doc.parent
        os.chmod(carpeta, 0o555)
        self.addCleanup(os.chmod, carpeta, 0o755)
        with self.assertRaises(OSError):
            vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar el NDA")
        self.assertEqual(self.doc.read_bytes(), crudo)
        self.assertEqual(sorted(p.name for p in carpeta.iterdir()), ["README.md"])

    def test_dos_con_el_mismo_id_o_texto_cambiado_no_se_adivina(self):
        crudo = self.poner("- [ ] Llamar <!-- id: c-0a0a0a -->\n- [ ] Llamar a Ana <!-- id: c-0a0a0a -->\n")
        with self.assertRaises(vinetas.ErrorDeVineta):
            vinetas.escribir(self.doc, vinetas.hecha, id="c-0a0a0a")
        crudo = self.poner("- [ ] Llamar a Ana mañana <!-- id: c-0a0a0a -->\n")
        with self.assertRaises(vinetas.ErrorDeVineta):
            vinetas.escribir(self.doc, vinetas.hecha, texto="Llamar a Ana", id="c-0a0a0a")
        self.assertEqual(self.doc.read_bytes(), crudo)

    def test_cambiar_sigue_sin_poner_id(self):
        # `cambiar` es la forma de antes: por el texto, sin id
        self.poner("- [ ] Revisar el NDA\n")
        vinetas.cambiar(self.doc, "Revisar el NDA", vinetas.hecha)
        self.assertEqual(self.doc.read_text(), "- [x] Revisar el NDA\n")


class EnLasOrdenes(Orden):
    """`telar pendiente`, `telar pendientes` y `telar objeto pendiente:…` sobre una copia del ejemplo."""

    def setUp(self):
        super().setUp()
        self.raiz = Path(self.tmp.name) / "ejemplo"
        shutil.copytree(EJEMPLO, self.raiz)
        os.environ["TELAR_RAIZ"] = str(self.raiz)
        self.doc = self.raiz / "proyectos" / "faro" / "README.md"
        sin_mux = mock.patch.object(_comun, "_mux", return_value=(None, "sin multiplexor en las pruebas"))
        sin_mux.start()
        self.addCleanup(sin_mux.stop)

    def fila(self, texto: str) -> dict:
        return next(f for f in self.json_de("pendientes", "--repo", "--json")["pendientes"] if f["texto"] == texto)

    def test_marcarla_hecha_le_da_id_y_direccion(self):
        antes = self.doc.read_bytes()
        fila = self.fila("Medir el alcance real en una noche de niebla")
        self.assertEqual(fila["direccion"], "")  # todavía no la escribió nadie
        r = self.json_de("pendiente", fila["ref"], "--hecho", "--json")
        ident = ID.search(self.doc.read_text()).group(1)
        self.assertEqual(r["direccion"], f"pendiente:{ident}")
        self.assertEqual(self.doc.read_text().count("<!-- id:"), 1)
        cambiadas = [i for i, (a, b) in enumerate(zip(antes.split(b"\n"), self.doc.read_bytes().split(b"\n"))) if a != b]
        self.assertEqual(cambiadas, [r["linea"] - 1])
        # la lista la trae con su dirección, y la referencia de lugar sigue igual
        fila2 = next(f for f in self.json_de("pendientes", "--repo", "--json", "--hechos")["pendientes"]
                     if f["texto"] == fila["texto"])
        self.assertEqual((fila2["direccion"], fila2["ref"], fila2["hecho"]), (r["direccion"], fila["ref"], True))

    def test_la_direccion_sigue_sirviendo_despues_de_insertar_lineas_arriba(self):
        fila = self.fila("Entregar el informe a la municipalidad")
        r = self.json_de("pendiente", fila["ref"], "--responsable", "Ana", "--json")
        direccion = r["direccion"]
        # alguien agrega casillas arriba, una con el mismo texto: el lugar y el texto ya no sirven, el id sí
        texto = self.doc.read_text().replace("## Pendientes\n\n", "## Pendientes\n\n- [ ] Llamar al electricista\n"
                                             "- [ ] Entregar el informe a la municipalidad\n", 1)
        self.doc.write_text(texto)
        o = self.json_de("objeto", direccion, "--json")
        self.assertEqual((o["tipo"], o["estado"], o["campos"]["responsable"]), ("pendiente", "abierta", "Ana"))
        self.assertEqual(o["campos"]["linea"], r["linea"] + 2)
        self.assertEqual(o["campos"]["documento"], "proyectos/faro/README.md")
        self.assertIn("proyecto:proyectos/faro", o["enlaces"])
        self.assertEqual([a["nombre"] for a in o["acciones"]], ["hecho", "responsable"])
        h = self.json_de("objeto", direccion, "hecho", "--version", o["version"], "--json")
        self.assertEqual((h["objeto"]["estado"], h["objeto"]["acciones"]), ("hecha", []))
        lineas = self.doc.read_text().splitlines()
        self.assertEqual(lineas[o["campos"]["linea"] - 1],
                         f"- [x] Entregar el informe a la municipalidad @owner(Ana) <!-- id: {direccion[10:]} -->")
        self.assertIn("- [ ] Entregar el informe a la municipalidad", lineas)  # la otra, intacta
        # por el id solo, también
        self.assertEqual(self.json_de("pendiente", direccion[10:], "--linea", "--json")["linea"], o["campos"]["linea"])

    def test_por_su_lugar_y_con_una_version_vieja(self):
        fila = self.fila("Medir el alcance real en una noche de niebla")
        o = self.json_de("objeto", f"pendiente:{fila['ref']}", "--json")
        self.assertEqual((o["id"], o["titulo"]), (fila["ref"], fila["texto"]))
        antes = self.doc.read_bytes()
        codigo, salida, _ = self.correr("objeto", f"pendiente:{fila['ref']}", "hecho", "--version", "vieja", "--json")
        self.assertNotEqual(codigo, 0)
        self.assertEqual(json.loads(salida)["codigo"], 409)
        self.assertEqual(self.doc.read_bytes(), antes)
        codigo, salida, _ = self.correr("objeto", "pendiente:c-ffffff", "--json")
        self.assertEqual(json.loads(salida)["codigo"], 404)

    def test_es_un_tipo_de_fabrica(self):
        tipos = {t["tipo"] for t in self.json_de("objeto", "--tipos", "--json")["tipos"]}
        self.assertIn("pendiente", tipos)
        self.assertEqual(self.json_de("objeto", "--buscar", "revisa pendiente:c-1a2b3c, porfa", "--json")["direcciones"],
                         ["pendiente:c-1a2b3c"])


class ElMensajeNoCambia(Prueba):
    def test_una_casilla_con_id_sigue_cayendo_al_texto(self):
        from telar.ordenes.pendiente import mensaje

        casilla = {"id": "", "texto": "revisar el contrato", "ref": "faro:2", "direccion": "pendiente:c-1a2b3c",
                   "proveedor": ""}
        self.assertEqual(mensaje("Veamos {direccion}", casilla), "revisar el contrato")
        self.assertEqual(mensaje("{texto} ({ref})", casilla), "revisar el contrato (faro:2)")


if __name__ == "__main__":
    unittest.main()
