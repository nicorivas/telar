"""El tipo tarea y sus dos lentes: el archivo propio y la casilla de un documento.

Cada lente promete leer con tolerancia y escribir al mínimo: lo que no cambió queda byte por byte. Estas
pruebas usan ejemplos inventados; la verificación contra archivos reales (cientos de tareas y miles de
casillas, leídas y cambiadas) está en docs/propuestas/tipos.md.
"""

from __future__ import annotations

import difflib

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar.tipos import ErrorDeFormato
from telar.tipos.tarea import ARCHIVO, CASILLA, Cambio, FormatoArchivo

TAREA = """---
titulo: Watts: volver con Ignacia por el contrato
estado: activa
prioridad: 1
vence: 2026-10-30
area: trabajo
etiquetas: watts, contratos
creada: 2026-10-01
avance: pregunta 2026-10-15
---
Volver con Ignacia: el contrato quedó en la cláusula 7.

## Historia
- 2026-10-01 [creada] a mano
- 2026-10-15 22:43 [avance] pregunta: ¿le escribo yo?
"""


def lineas_tocadas(a: str, b: str) -> list[str]:
    return [l for l in difflib.ndiff(a.split("\n"), b.split("\n")) if l[:1] in "+-"]


class ArchivoPropio(Prueba):
    def test_lee_lo_que_no_es_yaml_y_su_historia(self):
        t = ARCHIVO.leer(TAREA, "T84")
        self.assertEqual(t.titulo, "Watts: volver con Ignacia por el contrato")  # un «:» sin comillas
        self.assertEqual((t.estado, t.prioridad, t.vence, t.etiquetas), ("activa", 1, "2026-10-30", ["watts", "contratos"]))
        self.assertEqual(t.contexto, "Volver con Ignacia: el contrato quedó en la cláusula 7.")
        self.assertEqual([(c.fecha, c.hora, c.tipo) for c in t.historia], [("2026-10-01", "", "creada"), ("2026-10-15", "22:43", "avance")])

    def test_sin_cambios_los_mismos_bytes(self):
        t = ARCHIVO.leer(TAREA, "T84")
        self.assertEqual(ARCHIVO.escribir(TAREA, t, t.model_copy()), TAREA)

    def test_completar_toca_solo_sus_lineas_y_cada_una_en_su_lugar(self):
        t = ARCHIVO.leer(TAREA, "T84")
        hecha = t.model_copy(update=dict(estado="hecha", cerrada="2026-10-19", avance="", dueno="marcelo",
                                         historia=t.historia + [Cambio(fecha="2026-10-19", hora="10:00", tipo="cierre", texto="hecha")]))
        salida = ARCHIVO.escribir(TAREA, t, hecha)
        self.assertEqual(ARCHIVO.leer(salida, "T84").model_dump(), hecha.model_dump())
        self.assertEqual(lineas_tocadas(TAREA, salida), [
            "- estado: activa", "+ estado: hecha", "+ dueño: marcelo", "- avance: pregunta 2026-10-15",
            "+ cerrada: 2026-10-19", "+ - 2026-10-19 10:00 [cierre] hecha"])
        # cada clave nueva va en su lugar del orden del formato: dueño después de vence, cerrada después de creada
        claves = [l.split(":")[0] for l in salida.split("---")[1].strip().split("\n")]
        self.assertEqual(claves, ["titulo", "estado", "prioridad", "vence", "dueño", "area", "etiquetas", "creada", "cerrada"])

    def test_una_clave_repetida_vale_la_ultima_y_se_cambia_esa(self):
        texto = TAREA.replace("prioridad: 1\n", "prioridad: 1\nprioridad: 3\n")
        t = ARCHIVO.leer(texto, "T84")
        self.assertEqual((t.prioridad, t.duplicadas), (3, ["prioridad"]))
        salida = ARCHIVO.escribir(texto, t, t.model_copy(update={"prioridad": 0}))
        self.assertIn("prioridad: 1\nprioridad: 0\n", salida)

    def test_lo_que_no_reconoce_se_conserva(self):
        texto = TAREA.replace("area: trabajo\n", "area: trabajo\n# una nota a mano\n")
        t = ARCHIVO.leer(texto, "T84")
        salida = ARCHIVO.escribir(texto, t, t.model_copy(update={"vence": "2026-11-15"}))
        self.assertIn("# una nota a mano", salida)
        self.assertEqual(len(lineas_tocadas(texto, salida)), 2)

    def test_las_conexiones_van_antes_de_la_historia_y_el_contexto_se_reemplaza(self):
        t = ARCHIVO.leer(TAREA, "T84")
        salida = ARCHIVO.escribir(TAREA, t, t.model_copy(update={"conexiones": ["- [[contrato-watts]]"], "contexto": "Ya le escribí."}))
        self.assertLess(salida.index("## Conexiones"), salida.index("## Historia"))
        self.assertEqual(ARCHIVO.leer(salida, "T84").contexto, "Ya le escribí.")

    def test_a_quien_se_espera_vale_solo_mientras_espera(self):
        t = ARCHIVO.leer(TAREA, "T84")
        espera = ARCHIVO.escribir(TAREA, t, t.model_copy(update={"estado": "espera", "espera": "ignacia"}))
        self.assertIn("espera: ignacia", espera)
        t2 = ARCHIVO.leer(espera, "T84")
        de_vuelta = ARCHIVO.escribir(espera, t2, t2.model_copy(update={"estado": "activa"}))
        self.assertNotIn("espera: ignacia", de_vuelta)

    def test_lo_que_no_guarda_es_un_error_y_no_una_perdida(self):
        t = ARCHIVO.leer(TAREA, "T84")
        with self.assertRaises(ErrorDeFormato):
            ARCHIVO.escribir(TAREA, t, t.model_copy(update={"en_curso": True}))

    def test_las_claves_se_configuran(self):
        ingles = FormatoArchivo({**{c: c for c in ("titulo", "proyecto", "area", "etiquetas", "origen", "trabajo", "creada", "avance", "espera", "prioridad")},
                                 "estado": "status", "vence": "due", "dueno": "owner", "cerrada": "closed"})
        texto = "---\ntitulo: Pay the bill\nstatus: activa\ndue: 2026-10-30\n---\n"
        t = ingles.leer(texto, "T1")
        self.assertEqual((t.estado, t.vence), ("activa", "2026-10-30"))
        self.assertIn("status: hecha\ndue: 2026-10-30\nclosed: 2026-10-19\n", ingles.escribir(texto, t, t.model_copy(update={"estado": "hecha", "cerrada": "2026-10-19"})))


class Casilla(Prueba):
    def test_lee_los_dos_dialectos(self):
        a = CASILLA.leer("- [ ] @Ana Pérez: revisar el NDA @deadline(2026-10-30) @prioridad(P1) #legal <!-- id: T84 -->")
        self.assertEqual((a.id, a.titulo, a.dueno, a.vence, a.prioridad, a.etiquetas), ("T84", "revisar el NDA", "Ana Pérez", "2026-10-30", 1, ["legal"]))
        b = CASILLA.leer("- [>] Ajustar el giro  vence:2026-06-30  !alta  espera:@electricista")
        self.assertEqual((b.en_curso, b.vence, b.prioridad, b.espera, b.estado), (True, "2026-06-30", 1, "electricista", "espera"))
        self.assertEqual(CASILLA.leer("  - [~] Algo viejo").estado, "caduca")

    def test_una_plantilla_no_es_una_fecha(self):
        self.assertEqual(CASILLA.leer("- [ ] [Descripción] @prioridad(P1) @vence(YYYY-MM-DD)").vence, "")

    def test_completar_cambia_la_marca_y_agrega_la_fecha_antes_del_id(self):
        linea = "- [ ] Revisar el NDA @owner(Ana) <!-- id: T84 -->"
        t = CASILLA.leer(linea)
        salida = CASILLA.escribir(linea, t, t.model_copy(update={"estado": "hecha", "cerrada": "2026-10-19"}))
        self.assertEqual(salida, "- [x] Revisar el NDA @owner(Ana) @hecha(2026-10-19) <!-- id: T84 -->")

    def test_un_campo_se_reescribe_en_su_dialecto_y_su_lugar(self):
        linea = "- [ ] @Ana Pérez: revisar  vence:2026-06-30  !alta"
        t = CASILLA.leer(linea)
        salida = CASILLA.escribir(linea, t, t.model_copy(update={"dueno": "Marcelo", "vence": "2026-07-15", "prioridad": 3}))
        self.assertEqual(salida, "- [ ] @Marcelo: revisar  vence:2026-07-15  !baja")

    def test_quitar_un_campo_quita_su_marca(self):
        linea = "- [ ] Revisar el NDA @owner(Ana) @deadline(2026-10-30)"
        t = CASILLA.leer(linea)
        self.assertEqual(CASILLA.escribir(linea, t, t.model_copy(update={"dueno": ""})), "- [ ] Revisar el NDA @deadline(2026-10-30)")

    def test_lo_que_una_casilla_no_guarda_es_un_error(self):
        linea = "- [ ] Revisar el NDA"
        t = CASILLA.leer(linea)
        for cambio in ({"contexto": "un cuerpo largo"}, {"titulo": "otro texto"}, {"origen": "gmail:1a"}):
            with self.assertRaises(ErrorDeFormato):
                CASILLA.escribir(linea, t, t.model_copy(update=cambio))
        # la historia no se guarda, y eso está declarado: no es un error
        self.assertEqual(CASILLA.escribir(linea, t, t.model_copy(update={"historia": [Cambio(texto="x")]})), linea)


# ── las acciones y la carpeta ───────────────────────────────────────────────────

import datetime as _dt
import shutil
import tempfile
from pathlib import Path

from telar.tipos import tarea as T
from telar.tipos.carpeta import Carpeta, ErrorDeVersion, NoExiste

AHORA = _dt.datetime(2026, 10, 19, 10, 30)
reloj = lambda: AHORA  # noqa: E731


class Acciones(Prueba):
    def setUp(self):
        super().setUp()
        self.t = ARCHIVO.leer(TAREA, "T84")

    def test_completar_cierra_saca_de_en_curso_y_deja_su_linea(self):
        h = T.completar(self.t.model_copy(update={"en_curso": True, "estado": "espera", "espera": "ana"}), reloj=reloj)
        self.assertEqual((h.estado, h.en_curso, h.cerrada, h.espera, h.avance), ("hecha", False, "2026-10-19", "", ""))
        self.assertEqual(h.historia[-1], T.Cambio(fecha="2026-10-19", hora="10:30", tipo="cierre", texto="hecha"))

    def test_cerrar_lo_cerrado_o_reabrir_lo_abierto_es_un_error(self):
        h = T.completar(self.t, reloj=reloj)
        with self.assertRaises(T.ErrorDeAccion):
            T.completar(h, reloj=reloj)  # un doble clic no repite la historia
        with self.assertRaises(T.ErrorDeAccion):
            T.reabrir(self.t, reloj=reloj)
        self.assertEqual(T.reabrir(h, reloj=reloj).estado, "activa")

    def test_reagendar_en_dias_cuenta_desde_la_fecha_si_no_paso(self):
        self.assertEqual(T.reagendar(self.t, "+7d", reloj=reloj).vence, "2026-11-06")  # vencía el 30
        pasada = self.t.model_copy(update={"vence": "2026-10-01"})
        self.assertEqual(T.reagendar(pasada, "+7d", reloj=reloj).vence, "2026-10-26")  # desde hoy
        with self.assertRaises(T.ErrorDeAccion):
            T.reagendar(self.t, "el lunes", reloj=reloj)

    def test_esperar_y_volver(self):
        e = T.esperar(self.t, "@ignacia", reloj=reloj)
        self.assertEqual((e.estado, e.espera, e.historia[-1].texto), ("espera", "ignacia", "espera a ignacia"))
        v = T.esperar(e, "", reloj=reloj)
        self.assertEqual((v.estado, v.espera), ("activa", ""))
        self.assertEqual(T.algun_dia(e, reloj=reloj).espera, "")  # a algún día: ya no espera a nadie

    def test_proponer_y_responder(self):
        p = T.proponer(self.t, "cerrar", "ya se hizo", "hecha", reloj=reloj)
        self.assertEqual(p.avance, "cerrar:hecha 2026-10-19")
        self.assertEqual(T.responder(p, "de acuerdo", reloj=reloj).avance, "")
        with self.assertRaises(T.ErrorDeAccion):
            T.proponer(self.t, "cerrar", "x", reloj=reloj)  # cerrar pide cómo

    def test_editar_solo_lo_que_no_tiene_accion_propia(self):
        self.assertEqual(T.editar(self.t, prioridad=0, reloj=reloj).historia[-1].texto, "prioridad")
        with self.assertRaises(T.ErrorDeAccion):
            T.editar(self.t, estado="hecha", reloj=reloj)
        self.assertIs(T.editar(self.t, prioridad=1, reloj=reloj), self.t)  # sin cambios, la misma

    def test_las_acciones_no_cambian_la_tarea_que_reciben(self):
        antes = self.t.model_dump()
        T.completar(self.t, reloj=reloj)
        self.assertEqual(self.t.model_dump(), antes)


class LaCarpeta(Prueba):
    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T84.md").write_text(TAREA, encoding="utf-8")
        self.c = Carpeta(self.dir, ARCHIVO)

    def test_aplicar_escribe_al_minimo_y_devuelve_la_version_nueva(self):
        t, v = self.c.leer("T84")
        h, v2 = self.c.aplicar("T84", T.completar, version=v, reloj=reloj)
        self.assertNotEqual(v, v2)
        self.assertEqual(self.c.leer("T84"), (h, v2))
        self.assertEqual(len(lineas_tocadas(TAREA, (self.dir / "T84.md").read_text())), 5)

    def test_con_una_version_vieja_no_se_pisa_el_cambio_de_otro(self):
        _, v = self.c.leer("T84")
        (self.dir / "T84.md").write_text(TAREA.replace("prioridad: 1", "prioridad: 0"), encoding="utf-8")  # alguien lo editó
        with self.assertRaises(ErrorDeVersion):
            self.c.aplicar("T84", T.completar, version=v, reloj=reloj)
        self.assertIn("estado: activa", (self.dir / "T84.md").read_text())

    def test_un_id_no_es_una_ruta(self):
        for malo in ("../T84", "T84/..", "", "/etc/passwd"):
            with self.assertRaises(NoExiste):
                self.c.leer(malo)

    def test_una_accion_que_no_se_puede_no_escribe_nada(self):
        self.c.aplicar("T84", T.completar, reloj=reloj)
        antes = (self.dir / "T84.md").read_text()
        with self.assertRaises(T.ErrorDeAccion):
            self.c.aplicar("T84", T.completar, reloj=reloj)
        self.assertEqual((self.dir / "T84.md").read_text(), antes)
