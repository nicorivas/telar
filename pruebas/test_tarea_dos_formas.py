"""Cómo cambia el modelo de tarea: el lector entiende la forma vieja y la nueva, sin un campo `version`.

Ningún archivo de tarea dice en qué versión está. Cuando el modelo cambie, el lector aceptará las dos formas
y las dos tienen que dar la misma tarea; lo que el formato no conoce se conserva tal cual. Estas pruebas
fijan las formas que el lector ya acepta a la vez (los campos que se omiten, la historia con o sin hora, los
dialectos y sinónimos de la casilla) y que una clave desconocida no se pierde.
"""

from __future__ import annotations

import difflib
import os
import shutil
import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.tipos import tarea as T
from telar.tipos.carpeta import Carpeta
from telar.tipos.tarea import ARCHIVO, CASILLA


def reloj():
    import datetime as dt
    return dt.datetime(2026, 10, 22, 9, 30)


def tocadas(a: str, b: str) -> list[str]:
    return [l for l in difflib.ndiff(a.split("\n"), b.split("\n")) if l[:1] in "+-"]


def modelo(t: T.Tarea) -> dict:
    return t.model_dump(exclude={"duplicadas"})


class ElArchivoDeAntesYElDeAhora(Prueba):
    def test_un_campo_que_no_se_dice_vale_lo_mismo_que_su_valor_por_defecto(self):
        # la forma de antes de que existieran estado, prioridad y área, y la que los escribe
        corto = "---\ntitulo: Pagar la luz\n---\n"
        largo = "---\ntitulo: Pagar la luz\nestado: activa\nprioridad: 2\narea: personal\n---\n"
        self.assertEqual(modelo(ARCHIVO.leer(corto, "T84")), modelo(ARCHIVO.leer(largo, "T84")))

    def test_la_historia_con_hora_o_sin_ella(self):
        sin = "---\ntitulo: Pagar la luz\n---\n\n## Historia\n- 2026-10-01 [creada] a mano\n"
        con = sin.replace("2026-10-01 [creada]", "2026-10-01 08:15 [creada]")
        a, b = ARCHIVO.leer(sin, "T84").historia[0], ARCHIVO.leer(con, "T84").historia[0]
        self.assertEqual((a.fecha, a.tipo, a.texto), (b.fecha, b.tipo, b.texto))
        self.assertEqual((a.hora, b.hora), ("", "08:15"))

    def test_cada_forma_se_escribe_en_la_suya(self):
        # un campo nuevo no obliga a reescribir los que el archivo omitía
        corto = "---\ntitulo: Pagar la luz\n---\n"
        t = ARCHIVO.leer(corto, "T84")
        salida = ARCHIVO.escribir(corto, t, t.model_copy(update={"vence": "2026-10-30"}))
        self.assertEqual(salida, "---\ntitulo: Pagar la luz\nvence: 2026-10-30\n---\n")


class LosDialectosDeLaCasilla(Prueba):
    def test_los_dos_dialectos_dan_la_misma_tarea(self):
        a = CASILLA.leer("- [ ] Pagar la luz vence:2026-10-30 !alta espera:@Ana #casa")
        b = CASILLA.leer("- [ ] Pagar la luz @deadline(2026-10-30) @prioridad(P1) @espera(Ana) #casa")
        c = CASILLA.leer("- [ ] Pagar la luz @vence(2026-10-30) @priority(1) @espera(Ana) #casa")
        self.assertEqual(modelo(a), modelo(b))
        self.assertEqual(modelo(b), modelo(c))
        self.assertEqual((a.estado, a.prioridad, a.vence, a.espera), ("espera", 1, "2026-10-30", "Ana"))

    def test_los_sinonimos_de_quien_la_hace(self):
        formas = ["- [ ] @Ana: Pagar la luz", "- [ ] Pagar la luz @owner(Ana)", "- [ ] Pagar la luz @dueño(Ana)",
                  "- [ ] Pagar la luz @responsable(Ana)", "- [ ] Pagar la luz → @para(Ana)"]
        leidas = [modelo(CASILLA.leer(f)) for f in formas]
        for f, l in zip(formas, leidas):
            with self.subTest(f):
                self.assertEqual(l, leidas[0])
        self.assertEqual((leidas[0]["titulo"], leidas[0]["dueno"]), ("Pagar la luz", "Ana"))

    def test_sin_cambios_cada_forma_queda_igual_y_un_cambio_va_en_su_dialecto(self):
        for linea in ("- [ ] Pagar la luz vence:2026-10-30 !alta", "- [ ] Pagar la luz @vence(2026-10-30) @priority(1)"):
            with self.subTest(linea):
                t = CASILLA.leer(linea)
                self.assertEqual(CASILLA.escribir(linea, t, t.model_copy()), linea)
        linea = "- [ ] Pagar la luz @vence(2026-10-30) @priority(1)"
        t = CASILLA.leer(linea)
        self.assertEqual(CASILLA.escribir(linea, t, t.model_copy(update={"vence": "2026-11-05"})),
                         "- [ ] Pagar la luz @vence(2026-11-05) @priority(1)")

    def test_un_sinonimo_de_quien_la_hace_se_reescribe_con_su_nombre(self):
        for antes, despues in (("- [ ] Pagar la luz @dueño(Ana)", "- [ ] Pagar la luz @dueño(Bea)"),
                               ("- [ ] Pagar la luz → @para(Ana)", "- [ ] Pagar la luz → @para(Bea)"),
                               ("- [ ] Pagar la luz @responsable(Ana)", "- [ ] Pagar la luz @responsable(Bea)"),
                               ("- [ ] @Ana: Pagar la luz", "- [ ] @Bea: Pagar la luz")):
            with self.subTest(antes):
                t = CASILLA.leer(antes)
                self.assertEqual(CASILLA.escribir(antes, t, t.model_copy(update={"dueno": "Bea"})), despues)


TAREA = """---
titulo: Pagar la luz
estado: activa
version: 2
costo: 3
Revisado-Por: Faro
vence: 2026-10-30
creada: 2026-10-01
---
El contexto.

## Historia
- 2026-10-01 [creada] a mano
"""


class UnaClaveQueNoConoce(Prueba):
    def test_no_entra_al_modelo_y_leer_y_escribir_sin_cambios_da_los_mismos_bytes(self):
        t = ARCHIVO.leer(TAREA, "T84")
        # `version`, `costo` y `Revisado-Por` no son claves de este formato: no dicen nada de la tarea
        self.assertEqual(modelo(t), modelo(ARCHIVO.leer(TAREA.replace("version: 2\ncosto: 3\nRevisado-Por: Faro\n", ""), "T84")))
        self.assertEqual((t.dueno, t.duplicadas), ("", []))
        self.assertEqual(ARCHIVO.escribir(TAREA, t, t.model_copy()), TAREA)

    def test_una_accion_toca_solo_sus_lineas_y_la_clave_queda_tal_cual(self):
        t = ARCHIVO.leer(TAREA, "T84")
        salida = ARCHIVO.escribir(TAREA, t, T.completar(t, reloj=reloj))
        self.assertEqual(tocadas(TAREA, salida), ["- estado: activa", "+ estado: hecha", "+ cerrada: 2026-10-22",
                                                  "+ - 2026-10-22 09:30 [cierre] hecha"])
        for linea in ("version: 2", "costo: 3", "Revisado-Por: Faro"):
            self.assertIn(f"\n{linea}\n", salida)

    def test_por_la_carpeta_tambien(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "T84.md").write_bytes(TAREA.encode("utf-8"))
        c = Carpeta(d, ARCHIVO)
        # una acción que no cambia nada no escribe: ni los bytes ni la fecha del archivo cambian
        os.utime(d / "T84.md", ns=(1_000_000_000, 1_000_000_000))
        c.aplicar("T84", T.asignar, "")
        self.assertEqual((d / "T84.md").read_bytes(), TAREA.encode("utf-8"))
        self.assertEqual((d / "T84.md").stat().st_mtime_ns, 1_000_000_000)
        c.aplicar("T84", T.asignar, "Ana", reloj=reloj)
        escrito = (d / "T84.md").read_text(encoding="utf-8")
        self.assertIn("version: 2\ncosto: 3\nRevisado-Por: Faro\n", escrito)
        self.assertEqual(c.leer("T84")[0].dueno, "Ana")


class LosSinonimosDelArchivo(Prueba):
    """En el archivo propio, `dueno` (sin ñ, como se escribe en un teclado sin ella) dice lo mismo que `dueño`."""

    def test_dueno_sin_ene_es_el_duenio(self):
        a = ARCHIVO.leer("---\ntitulo: Pagar la luz\ndueno: Ana\n---\n", "T84")
        b = ARCHIVO.leer("---\ntitulo: Pagar la luz\ndueño: Ana\n---\n", "T84")
        self.assertEqual(modelo(a), modelo(b))
        self.assertEqual(a.dueno, "Ana")

    def test_se_reescribe_en_el_nombre_que_ya_tenia_la_linea(self):
        texto = "---\ntitulo: Pagar la luz\ndueno: Ana\n---\n"
        t = ARCHIVO.leer(texto, "T84")
        salida = ARCHIVO.escribir(texto, t, T.asignar(t, "Bea", reloj=reloj))
        self.assertTrue(salida.startswith("---\ntitulo: Pagar la luz\ndueno: Bea\n---\n"), salida)
        self.assertNotIn("dueño", salida.split("---")[1])
        # vaciarlo quita la línea, con el nombre que tenga
        salida = ARCHIVO.escribir(texto, t, T.asignar(t, "", reloj=reloj))
        self.assertTrue(salida.startswith("---\ntitulo: Pagar la luz\n---\n"), salida)

    def test_las_dos_a_la_vez_son_una_clave_repetida(self):
        t = ARCHIVO.leer("---\ntitulo: X\ndueño: Ana\ndueno: Bea\n---\n", "T84")
        self.assertEqual((t.dueno, t.duplicadas), ("Bea", ["dueño"]))

    def test_duenio_con_la_tilde_aparte(self):
        # «dueño» escrito con la n y la tilde combinante (NFD), como lo dejan algunos editores
        nfd = "---\ntitulo: Pagar la luz\nduen\u0303o: Ana\n---\n"
        self.assertEqual(ARCHIVO.leer(nfd, "T84").dueno, "Ana")

    def test_una_clave_desconocida_repetida_no_se_avisa(self):
        # el formato no la lee: que valga la última no significa nada, y no hay nada que avisar
        t = ARCHIVO.leer("---\ntitulo: X\nversion: 1\nversion: 2\nRevisado-Por: A\nRevisado-Por: B\n---\n", "T84")
        self.assertEqual(t.duplicadas, [])


class LoQueDejaOtraHerramienta(Prueba):
    """Una tarea escrita por otro editor: con BOM al comienzo o con finales de línea CRLF."""

    def carpeta(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d, Carpeta(d, ARCHIVO)

    def test_con_bom_se_lee_y_se_escribe_sin_romperse(self):
        d, c = self.carpeta()
        (d / "T85.md").write_bytes("\ufeff---\ntitulo: Pagar\nestado: hecha\ndueño: Ana\n---\nctx\n".encode("utf-8"))
        t, _ = c.leer("T85")
        self.assertEqual((t.titulo, t.estado, t.dueno, t.contexto), ("Pagar", "hecha", "Ana", "ctx"))
        c.aplicar("T85", T.asignar, "Bea", reloj=reloj)
        escrito = (d / "T85.md").read_bytes().decode("utf-8")
        self.assertTrue(escrito.startswith("\ufeff---\ntitulo: Pagar\nestado: hecha\ndueño: Bea\n---\nctx\n"), escrito)
        self.assertEqual(escrito.count("---"), 2)

    def test_crlf_por_la_carpeta_queda_crlf(self):
        d, c = self.carpeta()
        original = b"---\r\ntitulo: Pagar\r\nversion: 2\r\n---\r\nctx\r\nde dos lineas\r\n"
        (d / "T84.md").write_bytes(original)
        t, _ = c.leer("T84")
        self.assertEqual(t.contexto, "ctx\nde dos lineas")
        c.aplicar("T84", T.asignar, "Ana", reloj=reloj)
        escrito = (d / "T84.md").read_bytes()
        self.assertEqual(escrito.count(b"\n"), escrito.count(b"\r\n"), escrito)
        self.assertTrue(escrito.startswith(b"---\r\ntitulo: Pagar\r\ndue\xc3\xb1o: Ana\r\nversion: 2\r\n---\r\nctx\r\n"), escrito)
        self.assertEqual(c.leer("T84")[0].dueno, "Ana")

    def test_crlf_por_el_formato_no_queda_mixto(self):
        texto = "---\r\ntitulo: Pagar\r\n---\r\nctx\r\n"
        t = ARCHIVO.leer(texto, "T84")
        salida = ARCHIVO.escribir(texto, t, T.completar(t, reloj=reloj))
        self.assertEqual(salida.count("\n"), salida.count("\r\n"), salida)
        self.assertEqual(ARCHIVO.escribir(texto, t, t.model_copy()), texto)
