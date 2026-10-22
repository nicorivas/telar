"""Cómo cambia el modelo de tarea: el lector entiende la forma vieja y la nueva, sin un campo `version`.

Ningún archivo de tarea dice en qué versión está. Cuando el modelo cambie, el lector aceptará las dos formas
y las dos tienen que dar la misma tarea; lo que el formato no conoce se conserva tal cual. Estas pruebas
fijan las formas que el lector ya acepta a la vez (los campos que se omiten, la historia con o sin hora, los
dialectos y sinónimos de la casilla) y que una clave desconocida no se pierde.
"""

from __future__ import annotations

import difflib
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


TAREA = """---
titulo: Pagar la luz
estado: activa
version: 2
dueno: Ana
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
        # `version` y `dueno` (sin ñ) no son claves de este formato: no dicen nada de la tarea
        self.assertEqual(modelo(t), modelo(ARCHIVO.leer(TAREA.replace("version: 2\ndueno: Ana\nRevisado-Por: Faro\n", ""), "T84")))
        self.assertEqual((t.dueno, t.duplicadas), ("", []))
        self.assertEqual(ARCHIVO.escribir(TAREA, t, t.model_copy()), TAREA)

    def test_una_accion_toca_solo_sus_lineas_y_la_clave_queda_tal_cual(self):
        t = ARCHIVO.leer(TAREA, "T84")
        salida = ARCHIVO.escribir(TAREA, t, T.completar(t, reloj=reloj))
        self.assertEqual(tocadas(TAREA, salida), ["- estado: activa", "+ estado: hecha", "+ cerrada: 2026-10-22",
                                                  "+ - 2026-10-22 09:30 [cierre] hecha"])
        for linea in ("version: 2", "dueno: Ana", "Revisado-Por: Faro"):
            self.assertIn(f"\n{linea}\n", salida)

    def test_por_la_carpeta_tambien(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "T84.md").write_bytes(TAREA.encode("utf-8"))
        c = Carpeta(d, ARCHIVO)
        # una acción que no cambia nada no escribe: los bytes son los mismos
        c.aplicar("T84", T.asignar, "")
        self.assertEqual((d / "T84.md").read_bytes(), TAREA.encode("utf-8"))
        c.aplicar("T84", T.asignar, "Ana", reloj=reloj)
        escrito = (d / "T84.md").read_text(encoding="utf-8")
        self.assertIn("version: 2\ndueno: Ana\nRevisado-Por: Faro\n", escrito)
        self.assertEqual(c.leer("T84")[0].dueno, "Ana")
