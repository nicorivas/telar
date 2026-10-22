"""El tipo tarea y sus dos lentes: el archivo propio y la casilla de un documento.

Cada lente promete leer con tolerancia y escribir al mínimo: lo que no cambió queda byte por byte. Estas
pruebas usan ejemplos inventados; la verificación contra archivos reales (cientos de tareas y miles de
casillas, leídas y cambiadas) está en docs/arquitectura.md, «Los tipos».
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
import os
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


class ElProveedorTipo(Prueba):
    """`[proveedores.tareas] tipo = "tipo"`: las tareas de una carpeta, con la forma de siempre de un proveedor."""

    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T1.md").write_text(TAREA, encoding="utf-8")
        (self.dir / "T2.md").write_text("---\ntitulo: Esperando\nestado: espera\nprioridad: 0\nespera: ana\n---\n", encoding="utf-8")
        (self.dir / "T3.md").write_text("---\ntitulo: Hecha\nestado: hecha\ncerrada: 2026-10-01\n---\n", encoding="utf-8")
        (self.dir / "T4.md").write_text("---\ntitulo: Algún día\nestado: algun-dia\n---\n", encoding="utf-8")
        from telar.config import Proveedor
        from telar.proveedores import tareas as P
        self.P = P
        self.prov = P.DeTipo(Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": str(self.dir)}))

    def test_entran_las_abiertas_con_su_prioridad_y_a_quien_esperan(self):
        items = {i.id: i for i in self.prov.consultar(_dt.date(2026, 10, 19))}
        self.assertEqual(sorted(items), ["T1", "T2"])
        self.assertEqual(items["T1"].titulo, "Watts: volver con Ignacia por el contrato")
        self.assertEqual(items["T1"].datos["etiquetas"], ["watts", "contratos"])
        self.assertEqual((items["T2"].datos["espera"], items["T2"].datos["destacada"]), ("@ana", True))

    def test_un_cambio_en_el_archivo_se_ve_en_la_siguiente_consulta(self):
        self.prov.consultar(_dt.date(2026, 10, 19))
        (self.dir / "T1.md").write_text(TAREA.replace("estado: activa", "estado: hecha\ncerrada: 2026-10-19"), encoding="utf-8")
        os.utime(self.dir / "T1.md", (1, 1))  # otra fecha, aunque el reloj no haya avanzado
        self.assertEqual([i.id for i in self.prov.consultar(_dt.date(2026, 10, 19))], ["T2"])

    def test_sin_carpeta_se_dice(self):
        from telar.config import Proveedor
        with self.assertRaises(self.P.ErrorDeProveedor):
            self.P.DeTipo(Proveedor(nombre="tareas", opciones={"tipo": "tipo"}))


class LaFichaYSusAcciones(Prueba):
    """La ficha que arma el proveedor del tipo, y sus botones corridos por el servicio: la acción del tipo
    sobre el archivo, con su versión, y el commit de ese archivo."""

    def setUp(self):
        super().setUp()
        from types import SimpleNamespace
        from unittest import mock

        from telar.config import Config, Proveedor
        from telar.servicios import tareas as servicio
        self.servicio, self.mock = servicio, mock
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T84.md").write_text(TAREA, encoding="utf-8")
        prov = Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": str(self.dir), "agente": "Ada",
                                                    "equipo": ["Marcelo"]})
        self.ctx = SimpleNamespace(config=Config(raiz=self.dir, estado=self.dir / "e", proveedores={"tareas": prov}))
        sube = mock.patch.object(servicio, "_subir")
        self.subir = sube.start()
        self.addCleanup(sube.stop)

    def test_la_ficha_trae_la_propuesta_la_version_y_los_botones_del_tipo(self):
        p = self.servicio.ficha(self.ctx, "T84").model_dump()
        self.assertEqual(p["titulo"], "T84 · Watts: volver con Ignacia por el contrato")
        self.assertTrue(p["bloques"][0]["titulo"].startswith("Ada · pregunta"))
        self.assertEqual(len(p["version"]), 16)
        roles = {a.get("rol"): a for a in p["acciones"] if a.get("rol")}
        self.assertEqual(roles["hecha"]["accion"], "completar")
        self.assertIn("Marcelo", roles["dueno"]["opciones"])

    def test_en_la_lista_un_clic_abre_su_ficha(self):
        # sin `detalle`: la ficha la arma el tipo, y la lista lo dice (si no, el clic la manda al hilo)
        from telar.ordenes import _comun
        from telar.ordenes import pendientes as orden
        filas, _ = orden.de_proveedores(self.ctx, _comun.Telar(hilos=[], raiz=self.dir), _dt.date(2026, 10, 19))
        self.assertEqual([(f["id"], f["ficha"]) for f in filas], [("T84", True)])

    def test_el_check_completa_por_el_tipo_y_pide_el_commit(self):
        h = self.servicio.accion(self.ctx, "T84", rol="hecha")
        self.assertEqual(h.hecho, "✓ hecha")
        self.assertIn("estado: hecha", (self.dir / "T84.md").read_text())
        self.assertEqual(self.subir.call_args[0][1], "tareas: T84 completar")

    def test_lo_escrito_llena_el_parametro(self):
        acciones = self.servicio.ficha(self.ctx, "T84").model_dump()["acciones"]
        n = next(i for i, a in enumerate(acciones) if a["nombre"] == "nota")
        self.servicio.accion(self.ctx, "T84", n=n, texto="le escribí el lunes")
        self.assertIn("[nota] le escribí el lunes", (self.dir / "T84.md").read_text())

    def test_con_una_version_vieja_no_se_hace(self):
        from telar.servicios import ErrorDeServicio
        with self.assertRaises(ErrorDeServicio) as e:
            self.servicio.accion(self.ctx, "T84", rol="hecha", version="0000000000000000")
        self.assertEqual(e.exception.codigo, 409)
        self.assertIn("estado: activa", (self.dir / "T84.md").read_text())
        self.subir.assert_not_called()

    def test_escribirle_a_otro_hilo(self):
        from telar.config import Config, Proveedor
        from telar.ordenes import pendiente
        from telar.servicios import ErrorDeServicio

        prov = Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": str(self.dir), "agente": "Ada",
                                                    "mensaje_escribir": "/tarea {id} {texto}"})
        self.ctx = type(self.ctx)(config=Config(raiz=self.dir, estado=self.dir / "e", proveedores={"tareas": prov}))
        acciones = self.servicio.ficha(self.ctx, "T84").model_dump()["acciones"]
        n = next(i for i, a in enumerate(acciones) if a.get("al_hilo") and "anotar" == a.get("accion"))
        antes = (self.dir / "T84.md").read_text()
        no_hay = ErrorDeServicio("no hay ningún hilo ni agente que se llame «Nadie»", 404)
        from telar.ordenes import _comun

        tejer = self.mock.patch.object(_comun, "tejer")
        tejer.start()
        self.addCleanup(tejer.stop)
        with self.mock.patch.object(pendiente, "destino_elegido", side_effect=no_hay):
            with self.assertRaises(ErrorDeServicio) as e:
                self.servicio.accion(self.ctx, "T84", n=n, texto="mira esto", hilo="Nadie")
        self.assertEqual(e.exception.codigo, 404)
        self.assertEqual((self.dir / "T84.md").read_text(), antes)  # antes de correr nada
        with self.mock.patch.object(pendiente, "destino_elegido", return_value=(None, None, object())), \
                self.mock.patch.object(pendiente, "_buscar", return_value={"ref": "T84", "id": "T84"}), \
                self.mock.patch.object(pendiente, "llevar", return_value=({"destino": "Faro"}, "")) as llevar:
            h = self.servicio.accion(self.ctx, "T84", n=n, texto="mira esto", hilo="Faro")
        self.assertEqual(h.hilo, "Faro")
        self.assertEqual(llevar.call_args.kwargs["a"], "Faro")
        self.assertEqual(llevar.call_args.kwargs["texto"], "/tarea T84 mira esto")

    def test_none_deja_sin_dueno(self):
        self.servicio.accion(self.ctx, "T84", rol="dueno", texto="Marcelo")
        self.assertIn("dueño: Marcelo", (self.dir / "T84.md").read_text())
        self.servicio.accion(self.ctx, "T84", rol="dueno", texto="none")
        self.assertNotIn("dueño:", (self.dir / "T84.md").read_text())


    def test_esperar_y_prioridad_tienen_rol(self):
        self.servicio.accion(self.ctx, "T84", rol="espera", texto="Marcelo")
        self.assertIn("espera: Marcelo", (self.dir / "T84.md").read_text())
        self.servicio.accion(self.ctx, "T84", rol="espera", texto="none")
        self.assertIn("estado: activa", (self.dir / "T84.md").read_text())
        roles = {a.get("rol"): a for a in self.servicio.ficha(self.ctx, "T84").model_dump()["acciones"] if a.get("rol")}
        self.assertEqual(roles["prioridad"]["opciones"], ["P0", "P1", "P2", "P3"])
        self.assertIn("Marcelo", roles["espera"]["opciones"])
        self.servicio.accion(self.ctx, "T84", rol="prioridad", texto="P1")
        self.assertIn("prioridad: 1", (self.dir / "T84.md").read_text())
        from telar.servicios import ErrorDeServicio
        with self.assertRaises(ErrorDeServicio):
            self.servicio.accion(self.ctx, "T84", rol="prioridad", texto="urgente")

    def test_el_tope_no_cuenta_las_que_tienen_rol(self):
        from telar.proveedores.tareas import _recortar
        acciones = [{"nombre": f"a{i}"} for i in range(12)] + [{"nombre": f"r{i}", "rol": f"r{i}"} for i in range(6)]
        self.assertEqual(len(_recortar(acciones, 12)), 18)
        self.assertEqual([a["nombre"] for a in _recortar(acciones + [{"nombre": "sobra"}], 12)][-1], "r5")
        self.assertNotIn("sobra", [a["nombre"] for a in _recortar(acciones + [{"nombre": "sobra"}], 12)])


class CrearYLasAccionesQueFaltaban(Prueba):
    """Crear una tarea (el número lo elige quien escribe), borrarla, y las acciones que la CLI de tareas
    tenía y el tipo no: la secuela de un cierre, una conexión del grafo, quitar la fecha."""

    def setUp(self):
        super().setUp()
        from datetime import datetime

        from telar.tipos import tarea as tipo
        from telar.tipos.carpeta import Carpeta
        self.tipo = tipo
        self.reloj = lambda: datetime(2026, 10, 19, 9, 30)
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T84.md").write_text(TAREA, encoding="utf-8")
        (self.dir / "T9.md").write_text("---\ntitulo: x\n---\n", encoding="utf-8")
        self.carpeta = Carpeta(self.dir, ARCHIVO)

    def test_crear_da_el_numero_que_sigue_y_escribe_la_forma_de_siempre(self):
        t, v = self.carpeta.crear(self.tipo.nueva("Llamar a Ana: el NDA", prioridad=1, etiquetas=["nda"],
                                                  desde="email", reloj=self.reloj))
        self.assertEqual(t.id, "T85")
        self.assertEqual((self.dir / "T85.md").read_text(), "---\ntitulo: Llamar a Ana: el NDA\nestado: activa\n"
                         "prioridad: 1\narea: personal\netiquetas: nda\ncreada: 2026-10-19\n---\n"
                         "## Historia\n- 2026-10-19 [creada] desde email\n")
        self.assertEqual(self.carpeta.leer("T85"), (t, v))
        self.assertEqual(self.carpeta.crear(self.tipo.nueva("Otra"))[0].id, "T86")

    def test_lo_que_una_tarea_nueva_no_puede_ser(self):
        for kw in ({"titulo": " "}, {"titulo": "x", "estado": "hecha"}, {"titulo": "x", "prioridad": 7},
                   {"titulo": "x", "vence": "mañana"}):
            with self.assertRaises(self.tipo.ErrorDeAccion):
                self.tipo.nueva(**kw)

    def test_borrar_con_version(self):
        from telar.tipos.carpeta import ErrorDeVersion, NoExiste
        _, v = self.carpeta.leer("T9")
        with self.assertRaises(ErrorDeVersion):
            self.carpeta.borrar("T9", version="0" * 16)
        self.carpeta.borrar("T9", version=v)
        with self.assertRaises(NoExiste):
            self.carpeta.leer("T9")

    def test_secuela_conexion_y_sin_fecha(self):
        t, _ = self.carpeta.aplicar("T84", self.tipo.secuela, "avisé a Marcelo", reloj=self.reloj)
        self.assertEqual(t.historia[-1].tipo, "secuela")
        t, _ = self.carpeta.aplicar("T84", self.tipo.conectar, "bloquea", "[T9](T9.md)", "sin el contrato no hay pago")
        self.assertEqual(t.conexiones, ["- `bloquea` [T9](T9.md) · sin el contrato no hay pago"])
        self.assertIn("## Conexiones\n- `bloquea` [T9](T9.md) · sin el contrato no hay pago\n\n## Historia",
                      (self.dir / "T84.md").read_text())
        t, _ = self.carpeta.aplicar("T84", self.tipo.reagendar, "none", reloj=self.reloj)
        self.assertEqual((t.vence, t.historia[-1].texto), ("", "2026-10-30 → sin fecha"))
        self.assertNotIn("vence:", (self.dir / "T84.md").read_text())
        with self.assertRaises(self.tipo.ErrorDeAccion):
            self.tipo.conectar(t, "dos palabras", "[T9](T9.md)", "x")


class LaOrdenTipo(Prueba):
    """`telar tipo tarea …`: aquí si las tareas viven aquí; si viven en otra máquina, se le pide a ella, y
    sus errores llegan con su código."""

    def setUp(self):
        super().setUp()
        from types import SimpleNamespace
        from unittest import mock

        from telar.config import Config, Tipo
        from telar.servicios import tipos as servicio
        self.mock, self.ns = mock, SimpleNamespace
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T84.md").write_text(TAREA, encoding="utf-8")
        self.cfg = Config(raiz=self.dir, estado=self.dir / "e", tipos=(Tipo(clave="tarea", carpeta=str(self.dir)),))
        sube = mock.patch.object(servicio, "subir")
        self.subir = sube.start()
        self.addCleanup(sube.stop)

    def correr(self, *argv, cfg=None):
        import io
        from contextlib import redirect_stderr, redirect_stdout

        from telar.ordenes import tipo
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            codigo = tipo.main(list(argv), self.ns(config=cfg or self.cfg))
        return codigo, out.getvalue()

    def test_aqui(self):
        import json
        codigo, out = self.correr("tarea", "crear", "--params", '{"titulo": "Llamar a Ana"}', "--json")
        self.assertEqual((codigo, json.loads(out)["id"]), (0, "T85"))
        codigo, out = self.correr("tarea", "anotar", "T85", "--params", '{"texto": "le escribí"}', "--json")
        self.assertEqual(json.loads(out)["historia"][-1]["texto"], "le escribí")
        codigo, out = self.correr("tarea", "completar", "T85", "--version", "0" * 16, "--json")
        self.assertEqual((codigo != 0, json.loads(out)["codigo"]), (True, 409))
        self.assertIn("version", json.loads(out))
        codigo, out = self.correr("tarea", "lista", "--json")
        self.assertEqual([t["id"] for t in json.loads(out)["tareas"]], ["T84", "T85"])

    def test_alla(self):
        import json

        from telar import bus as mod_bus
        from telar.config import Bus, Config, Tipo
        cfg = Config(raiz=self.dir, estado=self.dir / "e", bus=Bus(url="nats://x", maquina="laptop"),
                     tipos=(Tipo(clave="tarea", en="servidor"),))
        nueva = {"id": "T90", "titulo": "Llamar a Ana", "version": "a" * 16}
        with self.mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "codigo": 0, "salida": json.dumps(nueva)}) as pedir:
            codigo, out = self.correr("tarea", "crear", "--params", '{"titulo": "Llamar a Ana"}', "--json", cfg=cfg)
        self.assertEqual((codigo, json.loads(out)["id"]), (0, "T90"))
        self.assertEqual(pedir.call_args[0][1:3], ("servidor", "tipo"))
        self.assertEqual(pedir.call_args[0][3]["argv"], ["tarea", "crear", "--params", '{"titulo": "Llamar a Ana"}', "--json"])
        error = {"ok": True, "codigo": 2, "salida": '{"error": "T84 cambió", "codigo": 409, "version": "b"}', "error_salida": ""}
        with self.mock.patch.object(mod_bus, "pedir", return_value=error):
            codigo, out = self.correr("tarea", "completar", "T84", "--version", "a", "--json", cfg=cfg)
        self.assertEqual(json.loads(out), {"error": "T84 cambió", "codigo": 409, "version": "b"})
        # y si allá no responde, no se escribe la copia de aquí
        with self.mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "nadie"}):
            codigo, out = self.correr("tarea", "completar", "T84", "--json", cfg=cfg)
        self.assertEqual(json.loads(out)["codigo"], 502)
        self.assertIn("estado: activa", (self.dir / "T84.md").read_text())
