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

    def test_nuevo_id_no_repite_uno_del_documento(self):
        # `nuevo_id` sobre lo que ya hay: dos líneas iguales a las que se les pone id quedan con ids distintos.
        # Por `telar pendiente`, el camino de punta a punta está en
        # LoQueEncontraronLosRevisoresEnLasOrdenes.test_dos_casillas_iguales_sin_id_son_dos_y_cada_una_recibe_su_id
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
        # los espacios del final se quedan al final (dos son un salto en markdown): el id va antes
        self.assertEqual(despues_l[3], f"- [x] Revisar el **NDA** 🧾 @deadline(2026-10-30) <!-- id: {ident} -->   \r".encode())

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


class SobreElEjemplo(Orden):
    """Una copia del ejemplo, para escribir en sus documentos."""

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


class EnLasOrdenes(SobreElEjemplo):
    """`telar pendiente`, `telar pendientes` y `telar objeto pendiente:…` sobre una copia del ejemplo."""

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
        # la lista la trae con su dirección, y su referencia pasa a ser la del id (no la de su lugar)
        fila2 = next(f for f in self.json_de("pendientes", "--repo", "--json", "--hechos")["pendientes"]
                     if f["texto"] == fila["texto"])
        lugar = fila["ref"].rsplit(":", 1)[0]
        self.assertEqual((fila2["direccion"], fila2["ref"], fila2["hecho"]), (r["direccion"], f"{lugar}:{ident}", True))
        # y la referencia de lugar de antes la sigue encontrando (alguien que la guardó, la página abierta)
        r2 = self.json_de("pendiente", fila["ref"], "--linea", "--json")
        self.assertEqual((r2["linea"], r2["direccion"]), (r["linea"], r["direccion"]))
        self.assertEqual(self.doc.read_text().count("<!-- id:"), 1)

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


class LoQueEncontraronLosRevisores(Prueba):
    """Los casos borde de la escritura que no estaban cubiertos (revisión de 30761ed)."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.doc = Path(self.tmp.name) / "README.md"

    def test_un_separador_unicode_en_la_linea_no_la_esconde(self):
        # la lectura parte en U+2028 (splitlines) y ve «Medir el alcance»: la escritura tiene que encontrar esa
        self.doc.write_text("- [ ] Medir el alcance\u2028real\n- [ ] Otra\n", encoding="utf-8")
        lineas = self.doc.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lectura._casillas(lineas, 0, "pendientes")[0].texto, "Medir el alcance")
        n, ident = vinetas.escribir(self.doc, vinetas.hecha, texto="Medir el alcance")
        self.assertEqual(n, 1)
        # el id queda donde la lectura lo ve: en la parte que es la casilla, antes del separador
        self.assertEqual(self.doc.read_text(encoding="utf-8"),
                         f"- [x] Medir el alcance <!-- id: {ident} -->\u2028real\n- [ ] Otra\n")
        p = lectura._casillas(self.doc.read_text(encoding="utf-8").splitlines(), 0, "pendientes")[0]
        self.assertEqual((p.texto, p.id_casilla, p.hecho), ("Medir el alcance", ident, True))
        self.assertEqual(vinetas.linea(self.doc, "", id=ident), 1)

    def test_los_espacios_del_final_se_quedan(self):
        # dos espacios al final son un salto de línea en markdown: no son de telar
        self.doc.write_bytes(b"- [ ] Revisar   \r\n")
        _, ident = vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar")
        self.assertEqual(self.doc.read_bytes(), f"- [x] Revisar <!-- id: {ident} -->   \r\n".encode())
        vinetas.escribir(self.doc, lambda l: vinetas.con_responsable(l, "Ana"), id=ident, abierta=False)
        self.assertEqual(self.doc.read_bytes(), f"- [x] Revisar @owner(Ana) <!-- id: {ident} -->   \r\n".encode())

    def test_un_id_dentro_de_un_codigo_no_es_el_suyo(self):
        for linea in ("- [ ] documentar el `<!-- id: T84 -->` en la skill",
                      "- [ ] documentar `<!-- id: c-bbbbbb -->`"):
            p = lectura._casillas([linea], 0, "pendientes")[0]
            self.assertEqual(p.id_casilla, "", linea)
            self.assertEqual(vinetas.id_de(linea + "\n"), "", linea)
        # y al escribirla recibe uno propio, al final
        self.doc.write_text("- [ ] documentar el `<!-- id: T84 -->` en la skill\n")
        _, ident = vinetas.escribir(self.doc, vinetas.hecha, texto="documentar el `` en la skill")
        self.assertRegex(ident, vinetas.FORMA_ID)
        self.assertEqual(self.doc.read_text(), f"- [x] documentar el `<!-- id: T84 -->` en la skill <!-- id: {ident} -->\n")

    def test_un_id_que_no_cierra_la_linea_no_es_su_id(self):
        # telar lo pone al final; uno en medio es texto (un ejemplo, una nota)
        self.assertEqual(lectura._casillas(["- [ ] ver <!-- id: c-0a0a0a --> y seguir"], 0, "p")[0].id_casilla, "")
        self.assertEqual(lectura._casillas(["- [ ] ver <!-- id: c-0a0a0a -->  "], 0, "p")[0].id_casilla, "c-0a0a0a")

    def test_un_comentario_abierto_no_se_traga_el_id(self):
        # «<!-- nota» que cierra en la línea siguiente: un id agregado quedaría adentro del comentario
        self.assertEqual(vinetas.con_id("- [x] tarea <!-- nota\n", "c-0a0a0a"), "- [x] tarea <!-- nota\n")
        self.assertEqual(vinetas.con_id("- [x] tarea <!-- nota --> y más\n", "c-0a0a0a"),
                         "- [x] tarea <!-- nota --> y más <!-- id: c-0a0a0a -->\n")

    def test_un_archivo_de_solo_lectura_no_se_reemplaza(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("como root se escribe igual")
        self.doc.write_text("- [ ] Revisar el NDA\n")
        os.chmod(self.doc, 0o444)
        self.addCleanup(os.chmod, self.doc, 0o644)
        with self.assertRaises(OSError):
            vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar el NDA")
        self.assertEqual(self.doc.read_text(), "- [ ] Revisar el NDA\n")
        self.assertEqual(sorted(p.name for p in self.doc.parent.iterdir()), ["README.md"])

    def test_un_enlace_duro_sigue_siendo_el_mismo_archivo(self):
        self.doc.write_text("- [ ] Revisar el NDA\n")
        otro = self.doc.with_name("OTRO.md")
        os.link(self.doc, otro)
        _, ident = vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar el NDA")
        self.assertEqual(otro.read_text(), f"- [x] Revisar el NDA <!-- id: {ident} -->\n")
        self.assertTrue(os.path.samefile(self.doc, otro))

    def test_si_falla_el_renombre_no_queda_el_temporal(self):
        crudo = b"- [ ] Revisar el NDA\n"
        self.doc.write_bytes(crudo)
        with mock.patch.object(vinetas.os, "replace", side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                vinetas.escribir(self.doc, vinetas.hecha, texto="Revisar el NDA")
        self.assertEqual(self.doc.read_bytes(), crudo)
        self.assertEqual(sorted(p.name for p in self.doc.parent.iterdir()), ["README.md"])

    def test_dos_escrituras_a_la_vez_no_comparten_temporal_ni_se_pisan(self):
        import threading

        self.doc.write_text("".join(f"- [ ] Casilla {i}\n" for i in range(8)))
        errores = []

        def marcar(i):
            try:
                vinetas.escribir(self.doc, vinetas.hecha, texto=f"Casilla {i}")
            except Exception as e:  # noqa: BLE001
                errores.append(e)

        hilos = [threading.Thread(target=marcar, args=(i,)) for i in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        texto = self.doc.read_text()
        self.assertEqual(texto.count("- [x] "), 8, texto)
        self.assertEqual(len(set(ID.findall(texto))), 8)


class LoQueEncontraronLosRevisoresEnLasOrdenes(SobreElEjemplo):
    def poner_id(self, doc: Path, texto: str, ident: str) -> None:
        contenido = doc.read_text()
        self.assertIn(f"- [ ] {texto}\n", contenido)
        doc.write_text(contenido.replace(f"- [ ] {texto}\n", f"- [ ] {texto} <!-- id: {ident} -->\n", 1))

    def test_un_mismo_id_en_dos_documentos_no_se_adivina(self):
        arboleda = self.raiz / "proyectos" / "arboleda" / "README.md"
        self.poner_id(self.doc, "Medir el alcance real en una noche de niebla", "c-abcabc")
        self.poner_id(arboleda, "Encargar treinta álamos", "c-abcabc")
        antes = (self.doc.read_bytes(), arboleda.read_bytes())
        for argv in (("pendiente", "c-abcabc", "--hecho", "--json"), ("pendiente", "pendiente:c-abcabc", "--hecho", "--json"),
                     ("objeto", "pendiente:c-abcabc", "--json"), ("objeto", "pendiente:c-abcabc", "hecho", "--json")):
            codigo, salida, error = self.correr(*argv)
            self.assertNotEqual(codigo, 0, argv)
            self.assertIn("proyectos/arboleda", salida + error, argv)
            self.assertIn("proyectos/faro", salida + error, argv)
            self.assertEqual((self.doc.read_bytes(), arboleda.read_bytes()), antes, argv)
        self.assertEqual(json.loads(self.correr("objeto", "pendiente:c-abcabc", "--json")[1])["codigo"], 409)
        # por su lugar sí se llega a cada una, y la escritura cae en la de ese documento
        fila = self.fila("Medir el alcance real en una noche de niebla")
        r = self.json_de("pendiente", fila["ref"], "--hecho", "--json")
        self.assertEqual(r["relativa"], "proyectos/faro/README.md")
        self.assertIn("- [x] Medir el alcance real en una noche de niebla <!-- id: c-abcabc -->", self.doc.read_text())
        self.assertEqual(arboleda.read_bytes(), antes[1])

    def test_un_id_puesto_a_mano_no_le_gana_a_una_tarea(self):
        # `<!-- id: T84 -->` a mano en una casilla: `telar pendiente T84` sigue llegando a la tarea T84 del
        # proveedor, como antes de que las casillas tuvieran id; la casilla se nombra con `pendiente:T84`
        from types import SimpleNamespace

        from telar import config as mod_config
        from telar.ordenes import pendientes as orden_pendientes

        self.poner_id(self.doc, "Medir el alcance real en una noche de niebla", "T84")
        tarea = {"texto": "Revisar el NDA", "hecho": False, "en_curso": False, "id": "T84", "origen": "tareas",
                 "ref": "T84", "direccion": "tarea:T84", "hilo": "", "ruta": "", "proveedor": "tareas", "url": ""}

        def de_proveedores(ctx, tel, dia, *, solo=None):
            return ([dict(tarea)] if solo is None or "tareas" in solo else []), []

        proveedor = SimpleNamespace(nombre="tareas", opciones={}, activo=True)
        with mock.patch.object(orden_pendientes, "de_proveedores", de_proveedores), \
                mock.patch.object(mod_config.Config, "proveedores_activos", lambda self: (proveedor,)):
            codigo, salida, error = self.correr("pendiente", "T84", "--linea", "--json")
            self.assertNotEqual(codigo, 0)
            self.assertIn("es de tareas", salida + error)  # llegó a la tarea, no a la casilla
            r = self.json_de("pendiente", "pendiente:T84", "--linea", "--json")
            self.assertEqual((r["relativa"], r["direccion"]), ("proyectos/faro/README.md", "pendiente:T84"))
        # sin un proveedor que la tenga, el id solo todavía encuentra la casilla
        self.assertEqual(self.json_de("pendiente", "T84", "--linea", "--json")["direccion"], "pendiente:T84")

    def test_dos_casillas_iguales_sin_id_son_dos_y_cada_una_recibe_su_id(self):
        # sin id, una casilla se busca por su texto; dos iguales en el mismo documento son dos filas en `telar
        # pendientes`, cada una sabe cuál es de las dos (`repetida`), y escribirla toca esa y le da su propio id
        molino = self.raiz / "proyectos" / "molino" / "README.md"
        molino.write_text(molino.read_text().replace("- [ ] Rearmar las dos aspas", "- [ ] Conseguir madera seca"))

        def filas():
            return [f for f in self.json_de("pendientes", "--repo", "--hechos", "--json")["pendientes"]
                    if f["texto"] == "Conseguir madera seca"]

        dos = filas()
        self.assertEqual([f["repetida"] for f in dos], [{"cual": 1, "de": 2}, {"cual": 2, "de": 2}])
        self.assertEqual(len({f["ref"] for f in dos}), 2)
        # la segunda primero: le toca a la segunda línea, no a la primera que calza
        codigo, salida, error = self.correr("pendiente", dos[1]["ref"], "--responsable", "Ana", "--json")
        self.assertEqual(codigo, 0, salida + error)
        lineas = molino.read_text().splitlines()
        self.assertEqual(lineas[-2], "- [ ] Conseguir madera seca")
        segunda = ID.search(lineas[-1]).group(1)
        self.assertEqual(lineas[-1], f"- [ ] Conseguir madera seca @owner(Ana) <!-- id: {segunda} -->")
        self.assertEqual(json.loads(salida)["direccion"], f"pendiente:{segunda}")
        # la otra se sigue alcanzando por su fila, y recibe un id distinto
        otra = next(f for f in filas() if not f["direccion"])
        codigo, salida, error = self.correr("pendiente", otra["ref"], "--hecho", "--json")
        self.assertEqual(codigo, 0, salida + error)
        lineas = molino.read_text().splitlines()
        primera = ID.search(lineas[-2]).group(1)
        self.assertNotEqual(primera, segunda)
        self.assertEqual(lineas[-2], f"- [x] Conseguir madera seca <!-- id: {primera} -->")
        self.assertEqual(lineas[-1], f"- [ ] Conseguir madera seca @owner(Ana) <!-- id: {segunda} -->")
        # y desde ahí cada una tiene su dirección
        self.assertEqual(sorted(f["direccion"] for f in filas()), sorted([f"pendiente:{primera}", f"pendiente:{segunda}"]))

    def test_si_cambio_cuantas_dicen_lo_mismo_no_se_adivina(self):
        # la fila dijo «la 2 de 2»; si alguien agregó una tercera igual, la 2 ya puede ser otra: no se escribe
        molino = self.raiz / "proyectos" / "molino" / "README.md"
        molino.write_text(molino.read_text().replace("- [ ] Rearmar las dos aspas", "- [ ] Conseguir madera seca"))
        fila = [f for f in self.json_de("pendientes", "--repo", "--json")["pendientes"]
                if f["texto"] == "Conseguir madera seca"][1]
        molino.write_text(molino.read_text().replace("## Pendientes\n\n", "## Pendientes\n\n- [ ] Conseguir madera seca\n"))
        antes = molino.read_bytes()
        from telar.cli import Contexto
        from telar.config import cargar as cargar_config
        from telar.ordenes import pendiente
        from telar.servicios import ErrorDeServicio

        with self.assertRaises(ErrorDeServicio) as e:
            pendiente.en_su_documento(Contexto(config=cargar_config(None)), fila["ref"], hecho=True, fila=fila)
        self.assertEqual(e.exception.codigo, 409)
        self.assertIn("ahora hay 3", str(e.exception))
        self.assertEqual(molino.read_bytes(), antes)


class DosCasillasIguales(Prueba):
    """Dos casillas que dicen lo mismo, sin id: la lectura dice cuál es cada una, y la escritura toca esa."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.doc = Path(self.tmp.name) / "README.md"

    def test_la_lectura_dice_cual_es_de_cuantas(self):
        texto = "## Pendientes\n\n- [ ] Llamar\n- [x] Llamar @owner(Ana)\n- [ ] Otra\n\n### Más\n\n- [ ] Llamar\n"
        p = lectura._casillas(lectura._con_lugar(texto.splitlines()), 0, "pendientes")
        self.assertEqual([(x.texto, x.cual, x.de) for x in p],
                         [("Llamar", 1, 3), ("Llamar", 2, 3), ("Otra", 1, 1), ("Llamar", 3, 3)])
        # sin lugar (líneas sueltas), como antes
        self.assertEqual({(x.cual, x.de) for x in lectura._casillas(texto.splitlines(), 0, "p")}, {(0, 0)})

    def test_la_misma_linea_en_dos_secciones_va_una_vez_y_dos_iguales_van_dos(self):
        from telar.perfil import Arquetipo, Seccion
        from telar.proveedores.estado import Documento

        # «Pendientes» se queda con su subsección «Más», y la convención lee las casillas sueltas también
        texto = "# Faro\n\n## Pendientes\n\n- [ ] Llamar\n\n### Más\n\n- [ ] Llamar\n- [ ] Otra\n"
        arq = Arquetipo(nombre="p", ruta="*.md", secciones=(Seccion(nombre="pendientes", tipo="casillas", encabezado="Pendientes"),
                                               Seccion(nombre="mas", tipo="casillas", encabezado="Más")))
        doc = Documento.__new__(Documento)
        doc.marcas = {}
        ficha = lectura.parsear(texto, arq)
        valores = {"pendientes": ficha.pendientes, "mas": ficha.secciones["mas"]}
        salida = doc._pendientes(valores, ("pendientes", "mas"))
        self.assertEqual([(x.texto, x.cual) for x in salida], [("Llamar", 1), ("Llamar", 2), ("Otra", 1)])

    def test_escribir_la_segunda_de_dos(self):
        self.doc.write_text("- [ ] Llamar\n- [ ] Llamar\n")
        n, ident = vinetas.escribir(self.doc, vinetas.hecha, texto="Llamar", cual=2, de=2)
        self.assertEqual(n, 2)
        self.assertEqual(self.doc.read_text(), f"- [ ] Llamar\n- [x] Llamar <!-- id: {ident} -->\n")
        n, otro = vinetas.escribir(self.doc, vinetas.hecha, texto="Llamar", cual=1, de=2)
        self.assertEqual(n, 1)
        self.assertNotEqual(otro, ident)
        self.assertEqual(vinetas.linea(self.doc, "Llamar", cual=1, de=2), 1)
        # ya hecha, no se vuelve a marcar
        with self.assertRaises(vinetas.ErrorDeVineta):
            vinetas.escribir(self.doc, vinetas.hecha, texto="Llamar", cual=1, de=2)

    def test_si_cambio_cuantas_son_no_escribe(self):
        self.doc.write_text("- [ ] Llamar\n- [ ] Llamar\n- [ ] Llamar\n")
        antes = self.doc.read_bytes()
        for cual, de in ((2, 2), (4, 4), (0, 2)):
            with self.subTest(cual=cual, de=de), self.assertRaises(vinetas.ErrorDeVineta):
                vinetas.escribir(self.doc, vinetas.hecha, texto="Llamar", cual=cual, de=de)
        self.assertEqual(self.doc.read_bytes(), antes)


class LaListaNoDependeDelOrden(Prueba):
    """Una casilla sin id que dice lo mismo que una con id no aparece, venga antes o después."""

    def test_el_duplicado_sin_id_se_esconde_en_los_dos_ordenes(self):
        from telar.modelo import Pendiente
        from telar.proveedores.estado import Documento

        con = Pendiente(texto="Llamar", origen="p", id_casilla="c-0a0a0a")
        sin = Pendiente(texto="Llamar", origen="p")
        otra = Pendiente(texto="Otra", origen="p")
        doc = Documento.__new__(Documento)
        doc.marcas = None
        for orden in ([con, sin, otra], [sin, con, otra]):
            with mock.patch.object(Documento, "_pendiente", lambda self, item, origen: item):
                salida = doc._pendientes({"p": orden}, ("p",))
            self.assertEqual([(p.texto, p.id_casilla) for p in salida], [("Llamar", "c-0a0a0a"), ("Otra", "")], orden)
        # dos con ids distintos son dos, aunque digan lo mismo
        dos = Pendiente(texto="Llamar", origen="p", id_casilla="c-0b0b0b")
        with mock.patch.object(Documento, "_pendiente", lambda self, item, origen: item):
            self.assertEqual(len(doc._pendientes({"p": [con, dos, sin]}, ("p",))), 2)


class ElMensajeNoCambia(Prueba):
    def test_una_casilla_con_id_llena_la_direccion(self):
        from telar.ordenes.pendiente import mensaje

        casilla = {"id": "", "texto": "revisar el contrato", "ref": "faro:c-1a2b3c", "direccion": "pendiente:c-1a2b3c",
                   "proveedor": ""}
        self.assertEqual(mensaje("Veamos {direccion}", casilla), "Veamos pendiente:c-1a2b3c")
        self.assertEqual(mensaje("{texto} ({ref})", casilla), "revisar el contrato (faro:c-1a2b3c)")
        sin_id = {**casilla, "direccion": "", "ref": "faro:2"}
        self.assertEqual(mensaje("Veamos {direccion}", sin_id), "revisar el contrato")  # sin id, cae al texto


if __name__ == "__main__":
    unittest.main()
