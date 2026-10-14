"""`telar equipo`: qué se comparte, las sugerencias y su resolución."""

import datetime
import json
import stat
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import comun  # noqa: F401 (src/ en el camino)

from telar import equipo as mod
from telar.ordenes import equipo as orden

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
    return mod.Equipo(tareas=carpeta, todo=todo, personas={"marcelo": "secreto"}, bandeja=tmp / "est" / "sug.jsonl")


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

    def test_rechazar_no_crea_nada(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            eq = montar(tmp, {})
            r = mod.pedir(eq, "marcelo", "Hacer la sesión 5 de GOA")[0]
            self.assertEqual(mod.resolver(eq, r["id"], "rechazar", "no esta semana")[0]["estado"], "rechazada")
            self.assertFalse((tmp / "todo.log").exists())


class Servidor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.eq = montar(Path(self.tmp.name), {"T1": {"titulo": "x"}})
        mod.avisar = lambda *a: None  # sin notificar de verdad
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), orden.manejador(self.eq))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def pedir(self, ruta, token="secreto", cuerpo=None):
        req = urllib.request.Request(self.url + ruta, data=json.dumps(cuerpo).encode() if cuerpo else None,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

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

    def test_pedido_mal_formado(self):
        self.assertEqual(self.pedir("/api/pedir", cuerpo={"contexto": "falta el título"})[0], 400)

    def test_no_hay_otras_rutas(self):
        self.assertEqual(self.pedir("/api/enviar", cuerpo={"x": 1})[0], 404)


if __name__ == "__main__":
    unittest.main()
