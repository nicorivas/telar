"""`telar equipo`: qué se comparte, las sugerencias y su resolución."""

import datetime
import json
import stat
import tempfile
import unittest
from types import SimpleNamespace as N
from unittest import mock
from pathlib import Path

import comun  # noqa: F401 (src/ en el camino)

from telar import equipo as mod

TAREA = """---
titulo: {titulo}
estado: {estado}
prioridad: {pri}
etiquetas: {tags}
{extra}---
CUERPO PRIVADO que no debe salir
"""


def montar(tmp: Path, tareas: dict[str, dict]) -> mod.Equipo:
    carpeta = tmp / "tareas"
    carpeta.mkdir()
    for ident, d in tareas.items():
        (carpeta / f"{ident}.md").write_text(TAREA.format(**{"estado": "activa", "pri": 2, "tags": "equipo", "extra": "", **d}), encoding="utf-8")
    todo = tmp / "todo"
    todo.write_text("#!/bin/sh\necho \"$@\" >> " + str(tmp / "todo.log") + "\n", encoding="utf-8")
    todo.chmod(todo.stat().st_mode | stat.S_IXUSR)
    return mod.Equipo(tareas=carpeta, todo=todo, personas={"marcelo": "secreto"}, bandeja=tmp / "est" / "sug.jsonl", semantica="")


class Visibles(unittest.TestCase):
    def test_solo_lo_marcado_y_sin_cuerpo(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {"T1": {"titulo": "pública"}, "T2": {"titulo": "privada", "tags": "personal"},
                                  "T3": {"titulo": "caduca", "estado": "caduca"}})
            vis = mod.tareas_visibles(eq)
            self.assertEqual([t["id"] for t in vis], ["T1"])
            self.assertNotIn("CUERPO", json.dumps(vis))

    def test_hecha_reciente_si_vieja_no(self):
        with tempfile.TemporaryDirectory() as d:
            hoy = datetime.date(2026, 10, 14)
            eq = montar(Path(d), {"T1": {"titulo": "a", "estado": "hecha", "extra": "cerrada: 2026-10-10\n"},
                                  "T2": {"titulo": "b", "estado": "hecha", "extra": "cerrada: 2026-08-01\n"}})
            self.assertEqual([t["id"] for t in mod.tareas_visibles(eq, hoy)], ["T1"])


class Sugerencias(unittest.TestCase):
    def test_sugerir_y_duplicado(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {"T1": {"titulo": "x"}, "T2": {"titulo": "y", "pri": 0}, "T3": {"titulo": "z", "tags": "otra"}})
            r, p = mod.sugerir(eq, "marcelo", "T1", "bloquea al equipo")
            self.assertEqual(p, "")
            self.assertEqual(r["estado"], "pendiente")
            self.assertIsNone(mod.sugerir(eq, "marcelo", "T1", "otra vez por favor")[0])
            self.assertIn("más alta", mod.sugerir(eq, "marcelo", "T2", "motivo largo")[1])
            self.assertIn("no está entre", mod.sugerir(eq, "marcelo", "T3", "motivo largo")[1])
            self.assertIn("motivo", mod.sugerir(eq, "marcelo", "T1", "no")[1])

    def test_aceptar_sube_un_nivel_y_rechazar_no_toca(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            eq = montar(tmp, {"T1": {"titulo": "x"}, "T4": {"titulo": "w"}})
            a = mod.sugerir(eq, "marcelo", "T1", "bloquea al equipo")[0]
            b = mod.sugerir(eq, "marcelo", "T4", "no urge tanto")[0]
            r, _ = mod.resolver(eq, a["id"], "aceptar")
            self.assertEqual((r["estado"], r["prioridad_nueva"]), ("aceptada", 1))
            self.assertIn("edit T1 --pri 1", (tmp / "todo.log").read_text())
            r, _ = mod.resolver(eq, b["id"], "rechazar", "ahora no")
            self.assertEqual((r["estado"], r["nota"]), ("rechazada", "ahora no"))
            self.assertNotIn("T4 --pri", (tmp / "todo.log").read_text())
            self.assertIsNone(mod.resolver(eq, a["id"], "rechazar")[0])  # ya resuelta


class Pedidos(unittest.TestCase):
    def test_pedir_valida_y_anota(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {})
            hoy = datetime.datetime(2026, 10, 14, 9, 0)
            r, p = mod.pedir(eq, "marcelo", "Hacer la sesión 5 de GOA", "la pide el cliente", "2026-10-20", ahora=hoy)
            self.assertEqual((p, r["tipo"], r["estado"], r["vence"]), ("", "tarea", "pendiente", "2026-10-20"))
            self.assertIn("ya tienes", mod.pedir(eq, "marcelo", "hacer la SESIÓN 5 de goa", ahora=hoy)[1])
            self.assertIn("de 5 a", mod.pedir(eq, "marcelo", "no", ahora=hoy)[1])
            self.assertIn("AAAA-MM-DD", mod.pedir(eq, "marcelo", "otra cosa distinta", vence="mañana", ahora=hoy)[1])
            self.assertIn("ya pasó", mod.pedir(eq, "marcelo", "otra cosa distinta", vence="2026-10-01", ahora=hoy)[1])

    def test_tope_de_pendientes_por_persona(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {})
            for i in range(mod.MAX_PENDIENTES):
                self.assertTrue(mod.pedir(eq, "marcelo", f"pedido número {i} largo")[0])
            self.assertIn("esperando", mod.pedir(eq, "marcelo", "uno más que sobra")[1])
            self.assertTrue(mod.pedir(eq, "ana", "pedido de otra persona")[0])

    def test_aceptar_agrega_la_tarea_con_el_cli(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            eq = montar(tmp, {})
            (tmp / "todo").write_text("#!/bin/sh\necho \"$@\" >> " + str(tmp / "todo.log") + "\necho 'añadida: T412  hacer algo'\n")
            r = mod.pedir(eq, "marcelo", "Hacer la sesión 5 de GOA", "la pide el cliente", "2026-12-31")[0]
            hecho, _ = mod.resolver(eq, r["id"], "aceptar", "ok")
            self.assertEqual((hecho["estado"], hecho["tarea"]), ("aceptada", "T412"))
            log = (tmp / "todo.log").read_text()
            self.assertIn("add Hacer la sesión 5 de GOA", log)
            self.assertIn("--tag equipo", log)
            self.assertIn("--due 2026-12-31", log)
            self.assertIn("equipo:marcelo", log)

    def test_revisando_marca_sin_resolver(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {})
            r = mod.pedir(eq, "marcelo", "Hacer la sesión 5 de GOA")[0]
            marcada, _ = mod.marcar_revision(eq, r["id"], "gestion")
            self.assertEqual((marcada["estado"], marcada["revisando"]["quien"]), ("pendiente", "gestion"))
            self.assertEqual(mod.leer_bandeja(eq)[0]["revisando"]["quien"], "gestion")
            self.assertIsNone(mod.marcar_revision(eq, "noexiste")[0])

    def test_rechazar_no_crea_nada(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            eq = montar(tmp, {})
            r = mod.pedir(eq, "marcelo", "Hacer la sesión 5 de GOA")[0]
            self.assertEqual(mod.resolver(eq, r["id"], "rechazar", "no esta semana")[0]["estado"], "rechazada")
            self.assertFalse((tmp / "todo.log").exists())


class Existentes(unittest.TestCase):
    def test_parecido_distingue_numeros_y_palabras(self):
        self.assertTrue(mod.parecido("Hacer la sesión 5 de GOA", "GOA: preparar y dictar la sesión 5"))
        self.assertFalse(mod.parecido("Hacer la sesión 5 de GOA", "GOA sesión 6"))
        self.assertFalse(mod.parecido("pagar la cuenta de luz", "Cerrar las 2 cuentas Enel"))

    def test_duplicadas_marca_las_compartidas(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {"T1": {"titulo": "GOA: dictar la sesión 5", "tags": "equipo", "extra": "avance: preparado\n"},
                                  "T2": {"titulo": "Preparar la sesión 5 de GOA con el cliente", "tags": "privada"},
                                  "T3": {"titulo": "otra cosa sin relación alguna"}})
            ya = {t["id"]: t["compartida"] for t in mod.duplicadas(eq, "Hacer la sesión 5 de GOA")}
            self.assertEqual(ya, {"T1": True, "T2": False})

    def test_el_pedido_guarda_las_parecidas_solo_para_nico(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {"T2": {"titulo": "Preparar la sesión 5 de GOA con el cliente", "tags": "privada"}})
            r = mod.pedir(eq, "marcelo", "Hacer la sesión 5 de GOA")[0]
            self.assertEqual([t["id"] for t in r["similares"]], ["T2"])

    def test_existe_contesta_con_el_estado(self):
        with tempfile.TemporaryDirectory() as d:
            eq = montar(Path(d), {"T1": {"titulo": "GOA: dictar la sesión 5", "pri": 1, "extra": "vence: 2026-10-22\navance: preparado 2026-10-13\n"}})
            r = mod.pedir(eq, "marcelo", "Hacer la sesión 5 de GOA")[0]
            hecho, p = mod.resolver(eq, r["id"], "existe", "va para el jueves", "T1")
            self.assertEqual((p, hecho["estado"], hecho["tarea"]), ("", "ya existía", "T1"))
            self.assertIn("T1 «GOA: dictar la sesión 5» · en curso · P1 · vence 2026-10-22 · avance: preparado 2026-10-13", hecho["nota"])
            self.assertTrue(hecho["nota"].endswith("va para el jueves"))
            self.assertNotIn("CUERPO", hecho["nota"])
            self.assertIn("T123", mod.resolver(eq, mod.pedir(eq, "marcelo", "Otro pedido distinto")[0]["id"], "existe", "", "")[1])


class Semantica(unittest.TestCase):
    HOY = datetime.date(2026, 10, 14)

    def montar(self, tmp):
        eq = montar(tmp, {
            "T1": {"titulo": "Programa de otoño del cliente GOA", "tags": "equipo", "extra": "creada: 2026-10-10\n"},
            "T2": {"titulo": "Cierre de contrato con Anasac", "tags": "privada", "extra": "creada: 2026-10-12\n"},
            "T3": {"titulo": "Tarea vieja sin relación", "extra": "creada: 2026-08-01\n"},
        })
        # el cuerpo de T1 dice de qué trata de verdad; el de T3 no debería viajar (tiene 2 meses)
        (eq.tareas / "T1.md").write_text(TAREA.format(titulo="Programa de otoño del cliente GOA", estado="activa", pri=2, tags="equipo",
                                                      extra="creada: 2026-10-10\n").replace("CUERPO PRIVADO que no debe salir", "Dictar la quinta sesión del programa"), encoding="utf-8")
        return mod.Equipo(**{**eq.__dict__, "semantica": "haiku"})

    def test_recientes_trae_descripcion_solo_de_las_ultimas_dos_semanas(self):
        with tempfile.TemporaryDirectory() as d:
            eq = self.montar(Path(d))
            vistas = {t["id"]: t for t in mod.recientes(eq, self.HOY)}
            self.assertEqual(sorted(vistas), ["T1", "T2"])
            self.assertIn("quinta sesión", vistas["T1"]["descripcion"])

    def test_el_modelo_encuentra_lo_que_las_palabras_no(self):
        with tempfile.TemporaryDirectory() as d:
            eq = self.montar(Path(d))
            with mock.patch("subprocess.run", return_value=N(returncode=0, stdout='{"ids": ["T1", "T9"]}', stderr="")) as run:
                ya = mod.parecidas(eq, "Hacer la sesión 5 de GOA", "", self.HOY)
            self.assertEqual([(t["id"], t["via"], t["compartida"]) for t in ya], [("T1", "sentido", True)])  # T9 no era candidata
            orden = run.call_args.args[0]
            self.assertEqual(orden[0], "claude")
            prompt = orden[2]
            self.assertIn("quinta sesión", prompt)       # la descripción viaja
            self.assertNotIn("Tarea vieja", prompt)       # lo de hace 2 meses no
            self.assertEqual(orden[orden.index("--tools") + 1], "")  # el modelo no tiene herramientas

    def test_si_el_modelo_falla_quedan_las_palabras(self):
        with tempfile.TemporaryDirectory() as d:
            eq = self.montar(Path(d))
            for falla in (N(returncode=1, stdout="", stderr="x"), N(returncode=0, stdout="no es json", stderr="")):
                with mock.patch("subprocess.run", return_value=falla):
                    self.assertEqual(mod.parecidas(eq, "Programa de otoño GOA", "", self.HOY)[0]["via"], "palabras")
            with mock.patch("subprocess.run", side_effect=OSError):
                self.assertEqual(mod.parecidas(eq, "algo que no se parece a nada", "", self.HOY), [])

    def test_sin_modelo_configurado_no_se_llama(self):
        with tempfile.TemporaryDirectory() as d:
            eq = mod.Equipo(**{**self.montar(Path(d)).__dict__, "semantica": ""})
            with mock.patch("subprocess.run") as run:
                mod.parecidas(eq, "Hacer la sesión 5 de GOA", "", self.HOY)
            run.assert_not_called()


@unittest.skipIf(not comun.HAY_FASTAPI, "sin fastapi (el extra «serve»)")
class Servidor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.eq = montar(Path(self.tmp.name), {"T1": {"titulo": "x"}})
        mod.avisar = lambda *a: None  # sin notificar de verdad
        from fastapi.testclient import TestClient

        from telar import api_equipo
        self.c = TestClient(api_equipo.crear(self.eq))

    def tearDown(self):
        self.tmp.cleanup()

    def pedir(self, ruta, token="secreto", cuerpo=None):
        cab = {"Authorization": f"Bearer {token}"}
        r = self.c.post(ruta, json=cuerpo, headers=cab) if cuerpo is not None else self.c.get(ruta, headers=cab)
        return r.status_code, r.json()

    def test_sin_llave_no_ve_nada(self):
        self.assertEqual(self.pedir("/api/tareas", token="mala")[0], 401)
        self.assertEqual(self.pedir("/api/sugerir", token="", cuerpo={"tarea": "T1", "motivo": "motivo largo"})[0], 401)

    def test_ve_y_sugiere(self):
        c, d = self.pedir("/api/tareas")
        self.assertEqual((c, d["quien"], [t["id"] for t in d["tareas"]]), (200, "marcelo", ["T1"]))
        c, d = self.pedir("/api/sugerir", cuerpo={"tarea": "T1", "motivo": "bloquea al equipo"})
        self.assertTrue(d["ok"], d)
        self.assertEqual(self.pedir("/api/tareas")[1]["sugerencias"][0]["estado"], "pendiente")
        self.assertEqual(self.pedir("/api/sugerir", cuerpo={"tarea": "T1", "motivo": "bloquea al equipo"})[0], 429)

    def test_pide_una_tarea(self):
        c, d = self.pedir("/api/pedir", cuerpo={"titulo": "Hacer la sesión 5 de GOA", "contexto": "urge"})
        self.assertTrue(d["ok"], d)
        mias = self.pedir("/api/tareas")[1]["sugerencias"]
        self.assertEqual([(x["tipo"], x["titulo"], x["estado"]) for x in mias], [("tarea", "Hacer la sesión 5 de GOA", "pendiente")])
        self.assertEqual(self.pedir("/api/pedir", token="mala", cuerpo={"titulo": "xxxxxx"})[0], 401)

    def test_pedir_algo_que_ya_existe_contesta_su_estado(self):
        mod_t = self.eq.tareas / "T9.md"
        mod_t.write_text(TAREA.format(titulo="GOA: dictar la sesión 5", estado="activa", pri=1, tags="equipo", extra="avance: preparado\n"), encoding="utf-8")
        c, d = self.pedir("/api/pedir", cuerpo={"titulo": "Hacer la sesión 5 de GOA"})
        self.assertEqual(c, 409)
        self.assertIn("T9", d["existe"][0]["resumen"])
        self.assertNotIn("CUERPO", json.dumps(d))
        self.assertEqual(mod.leer_bandeja(self.eq), [])  # no molestó a Nico
        c, d = self.pedir("/api/pedir", cuerpo={"titulo": "Hacer la sesión 5 de GOA", "aunque_exista": True})
        self.assertTrue(d["ok"], d)

    def test_pedido_mal_formado(self):
        self.assertEqual(self.pedir("/api/pedir", cuerpo={"contexto": "falta el título"})[0], 400)

    def test_no_hay_otras_rutas(self):
        self.assertEqual(self.pedir("/api/enviar", cuerpo={"x": 1})[0], 404)
        # ni las de la API de su dueño: es otra app
        for ruta in ("/hoy", "/mensajes", "/tipos/tarea", "/docs", "/openapi.json"):
            self.assertEqual(self.pedir(ruta)[0], 404, ruta)

    def test_un_cuerpo_demasiado_grande_no_se_lee(self):
        self.assertEqual(self.pedir("/api/sugerir", cuerpo={"tarea": "T1", "motivo": "x" * 5000})[0], 400)

    def test_la_pagina(self):
        r = self.c.get("/")
        self.assertEqual((r.status_code, r.headers["x-content-type-options"]), (200, "nosniff"))
        self.assertIn("pedirle algo a Nico", r.text)


if __name__ == "__main__":
    unittest.main()


class LaBandejaDelDueno(unittest.TestCase):
    """La bandeja, del lado de su dueño (telar.servicios.equipo): aquí, o en la máquina donde vive por el bus."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.eq = montar(Path(self.tmp.name), {"T1": {"titulo": "x"}})
        self.ctx = N(config=N(bus=N(url="nats://x", maquina="laptop")))

    def tearDown(self):
        self.tmp.cleanup()

    def test_aqui_lee_y_marca_y_lo_que_no_hay_es_409(self):
        from telar.servicios import ErrorDeServicio
        from telar.servicios import equipo as servicio
        mod.sugerir(self.eq, "marcelo", "T1", "bloquea al equipo")
        with mock.patch.object(mod, "cargar", return_value=self.eq):
            b = servicio.bandeja(self.ctx)
            self.assertEqual([r["tarea"] for r in b.sugerencias], ["T1"])
            r = servicio.revisando(self.ctx, b.sugerencias[0]["id"], quien="gestion")
            self.assertEqual(r.sugerencia["revisando"]["quien"], "gestion")
            with self.assertRaises(ErrorDeServicio) as e:
                servicio.decidir(self.ctx, "no-hay", "rechazar")
            self.assertEqual(e.exception.codigo, 409)
            with self.assertRaises(ErrorDeServicio):
                servicio.decidir(self.ctx, "x", "volar")

    def test_en_otra_maquina_por_el_bus(self):
        from telar import bus as mod_bus
        from telar.servicios import equipo as servicio
        r = {"ok": True, "codigo": 0, "salida": '{"sugerencias": [{"id": "a1"}]}\n', "error_salida": ""}
        with mock.patch.object(mod_bus, "pedir", return_value=r) as pedir:
            self.assertEqual(servicio.bandeja(self.ctx, maquina="telar").sugerencias, [{"id": "a1"}])
        self.assertEqual(pedir.call_args[0][1:3], ("telar", "equipo"))
        self.assertEqual(pedir.call_args[0][3]["argv"], ["sugerencias", "--json"])
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "codigo": 0, "salida": '{"sugerencia": {"id": "a1"}}'}) as pedir:
            servicio.decidir(self.ctx, "a1", "aceptar", nota="dale", maquina="telar")
        self.assertEqual(pedir.call_args[0][3]["argv"], ["aceptar", "a1", "--nota", "dale", "--json"])
