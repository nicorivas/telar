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

    def test_no_hay_otras_rutas(self):
        self.assertEqual(self.pedir("/api/enviar", cuerpo={"x": 1})[0], 404)


if __name__ == "__main__":
    unittest.main()
