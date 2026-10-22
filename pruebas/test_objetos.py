"""Direcciones y objetos (telar.objetos): leer una dirección, encontrarlas en un texto, y ver y actuar sobre los
objetos de cada tipo, los de fábrica y los de un módulo."""

from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import modulos, objetos
from telar.servicios import ErrorDeServicio


def ctx_con(raiz: Path, mods=()):
    return SimpleNamespace(config=SimpleNamespace(raiz=raiz, apps=(), modulos=tuple(mods), repos=()))


class LasDirecciones(Prueba):
    def test_leer(self):
        self.assertEqual(objetos.leer("tarea:T366"), ("tarea", "T366", ""))
        self.assertEqual(objetos.leer("hilo:Telar frontend@telar"), ("hilo", "Telar frontend", "telar"))
        self.assertEqual(objetos.leer("archivo:telar:docs/x.md"), ("archivo", "telar:docs/x.md", ""))
        self.assertEqual(str(objetos.leer(" proyecto:nico/proyectos/telar ")), "proyecto:nico/proyectos/telar")
        for malo in ("T366", "tarea:", "Tarea:T1", ":x"):
            with self.assertRaises(ErrorDeServicio):
                objetos.leer(malo)

    def test_encontrarlas_en_un_texto(self):
        ctx = ctx_con(Path("."))
        texto = ("revisa tarea:T366, y después hilo:Telar. Ver https://x.com/a:b, nota:algo (tipo que no hay) "
                 "o `archivo:telar:GRAFO.md`; otra vez tarea:T366 y tarea:T7@telar")
        self.assertEqual([str(d) for d in objetos.buscar(ctx, texto)],
                         ["tarea:T366", "hilo:Telar", "archivo:telar:GRAFO.md", "tarea:T7@telar"])


class LosTiposDeFabrica(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "nota.md").write_text("# Una nota\n\n> Lo que dice, en una línea.\n\nEl cuerpo.\n")
        self.ctx = ctx_con(self.raiz)

    def test_un_archivo(self):
        o = objetos.ver(self.ctx, "archivo:nota.md")
        self.assertEqual((o.titulo, o.resumen, o.tipo), ("Una nota", "Lo que dice, en una línea.", "archivo"))
        with self.assertRaises(ErrorDeServicio) as e:
            objetos.ver(self.ctx, "archivo:/etc/passwd")
        self.assertEqual(e.exception.codigo, 403)

    def test_una_tarea_y_su_accion(self):
        from telar.servicios import tipos as servicio

        t = servicio.TareaConVersion(id="T9", titulo="Llamar a Ana", estado="activa", proyecto="proyectos/faro",
                                     contexto="Por el contrato.", version="abc")
        with mock.patch.object(servicio, "obtener", return_value=t):
            o = objetos.ver(self.ctx, "tarea:T9")
        self.assertEqual((o.titulo, o.estado, o.version, o.resumen), ("Llamar a Ana", "activa", "abc", "Por el contrato."))
        self.assertEqual(o.enlaces, ["proyecto:proyectos/faro"])
        reagendar = next(a for a in o.acciones if a.nombre == "reagendar")
        self.assertIn("fecha", reagendar.params)
        # los valores por defecto, tal cual: la página los pone en el campo («hecha», no «'hecha'»)
        cerrar = next(a for a in o.acciones if a.nombre == "cerrar")
        self.assertEqual((cerrar.params["como"], cerrar.params["nota"]), ("hecha", ""))
        hecha = t.model_copy(update={"estado": "hecha", "version": "def"})
        with mock.patch.object(servicio, "aplicar", return_value=hecha) as aplicar:
            h = objetos.hacer(self.ctx, "tarea:T9", "completar", {"nota": "listo"}, "abc")
        self.assertEqual(aplicar.call_args.args[1:4], ("T9", "completar", {"nota": "listo"}))
        self.assertEqual(aplicar.call_args.kwargs["version"], "abc")
        self.assertEqual((h.objeto.estado, h.objeto.version), ("hecha", "def"))

    def test_a_un_hilo_se_le_escribe(self):
        from telar.servicios import mensajes

        enviado = mensajes.Enviado(id="m1")
        with mock.patch.object(mensajes, "enviar", return_value=enviado) as enviar:
            h = objetos.hacer(self.ctx, "hilo:Faro", "mensaje", {"texto": "¿quedó?"})
        self.assertEqual(enviar.call_args.args[1:3], ("Faro", "¿quedó?"))
        self.assertEqual(h.accion, "mensaje")
        with self.assertRaises(ErrorDeServicio):
            objetos.hacer(self.ctx, "hilo:Faro", "mensaje", {})
        with self.assertRaises(ErrorDeServicio):
            objetos.hacer(self.ctx, "hilo:Faro", "volar", {})

    def test_un_hilo_con_maquina_es_el_de_esa_maquina(self):
        # un «Faro» aquí y otro en el servidor: `hilo:Faro@servidor` abre el del servidor, no el local
        from telar import bus as mod_bus
        from telar import espejo
        from telar.ordenes import _comun

        aqui = SimpleNamespace(nombre="Faro", id="@1", remoto="")
        tel = SimpleNamespace(hilos=[aqui])
        fotos = [{"nombre": "laptop", "hilos": [{"nombre": "Faro", "relativa": "otra"}]},
                 {"nombre": "servidor", "hilos": [{"nombre": "Faro", "relativa": "proyectos/faro", "atencion": "trabajando"}]}]
        with mock.patch.object(mod_bus, "hay_bus", return_value=True), \
                mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(espejo, "leer_todos", return_value=fotos), \
                mock.patch.object(_comun, "tejer", return_value=tel), \
                mock.patch.object(_comun, "json_hilo", return_value={"nombre": "Faro", "relativa": "aqui"}):
            o = objetos.ver(self.ctx, "hilo:Faro@servidor")
            self.assertEqual((o.maquina, o.campos["relativa"], o.estado), ("servidor", "proyectos/faro", "trabajando"))
            self.assertEqual(objetos.ver(self.ctx, "hilo:Faro@laptop").campos["relativa"], "aqui")  # la de aquí
            self.assertEqual(objetos.ver(self.ctx, "hilo:Faro").campos["relativa"], "aqui")  # sin máquina, el local
            with self.assertRaises(ErrorDeServicio) as e:
                objetos.ver(self.ctx, "hilo:Faro@otra")
            self.assertEqual(e.exception.codigo, 404)

    def test_un_hilo_de_otra_maquina_lleva_su_maquina_en_la_direccion(self):
        from telar import bus, espejo

        fotos = [{"nombre": "servidor", "hilos": [{"nombre": "Faro", "atencion": "trabajando", "relativa": "proyectos/faro"}]}]
        with mock.patch.object(bus, "hay_bus", return_value=True), mock.patch.object(bus, "maquina", return_value="laptop"), \
                mock.patch.object(espejo, "leer_todos", return_value=fotos):
            o = objetos.ver(self.ctx, "hilo:Faro@servidor")
            self.assertEqual((o.direccion, o.maquina), ("hilo:Faro@servidor", "servidor"))
            with self.assertRaises(ErrorDeServicio) as e:  # allá no hay uno así: no se cae al de aquí
                objetos.ver(self.ctx, "hilo:Telar@servidor")
            self.assertEqual(e.exception.codigo, 404)

    def test_un_tipo_que_no_hay(self):
        with self.assertRaises(ErrorDeServicio) as e:
            objetos.ver(self.ctx, "correo:abc")
        self.assertEqual(e.exception.codigo, 404)
        self.assertIn("tarea", str(e.exception))


VER = """#!/usr/bin/env python3
import json, sys
p = json.load(sys.stdin)
if sys.argv[1] == "ver":
    print(json.dumps({"titulo": "el correo " + p["id"], "estado": "sin leer", "campos": {"de": "ana"}}))
else:
    print(json.dumps({"archivado": p["id"], "carpeta": p.get("carpeta", "")}))
"""

MANIFIESTO = """nombre = "correo"
[ordenes.ver]
comando = ["bin/c", "ver"]
consulta = true
[ordenes.archivar]
comando = ["bin/c", "archivar"]
consulta = true
[objetos.correo]
ver = "ver"
acciones = ["archivar"]
descripcion = "un correo"
"""


class UnTipoDeModulo(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name) / "correo"
        (self.carpeta / "bin").mkdir(parents=True)
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO)
        c = self.carpeta / "bin" / "c"
        c.write_text(VER)
        c.chmod(c.stat().st_mode | stat.S_IEXEC)

    def test_se_ve_y_actua_por_sus_consultas(self):
        m = modulos.leer("correo", self.carpeta)
        self.assertIn("objetos correo:", m.aporta)
        ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))
        self.assertIn("correo", objetos.tipos(ctx))
        o = objetos.ver(ctx, "correo:1a2b")
        self.assertEqual((o.direccion, o.titulo, o.estado, o.campos), ("correo:1a2b", "el correo 1a2b", "sin leer", {"de": "ana"}))
        self.assertEqual([a.nombre for a in o.acciones], ["archivar"])
        h = objetos.hacer(ctx, "correo:1a2b", "archivar", {"carpeta": "hecho"})
        self.assertEqual(h.resultado, {"archivado": "1a2b", "carpeta": "hecho"})
        with self.assertRaises(ErrorDeServicio):
            objetos.hacer(ctx, "correo:1a2b", "borrar", {})

    def test_un_tipo_debe_apuntar_a_sus_consultas(self):
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO.replace('ver = "ver"', 'ver = "nada"'))
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.leer("correo", self.carpeta)

    def test_un_modulo_no_pisa_un_tipo_de_fabrica(self):
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO.replace("[objetos.correo]", "[objetos.tarea]"))
        m = modulos.leer("correo", self.carpeta)
        ctx = SimpleNamespace(config=SimpleNamespace(modulos=(m,)))
        self.assertIsInstance(objetos.tipos(ctx)["tarea"], objetos.Tarea)


try:
    from fastapi.testclient import TestClient

    from telar import api
except ImportError:  # sin el extra «serve»
    api = None


@unittest.skipIf(api is None, "sin fastapi")
class LaApi(Prueba):
    def test_un_objeto_y_los_tipos(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "nota.md").write_text("# Hola\n")
            api.app.dependency_overrides[api.contexto] = lambda: ctx_con(Path(tmp))
            self.addCleanup(api.app.dependency_overrides.clear)
            c = TestClient(api.app)
            r = c.get("/objetos/archivo:nota.md")
            self.assertEqual((r.status_code, r.json()["titulo"]), (200, "Hola"))
            self.assertIn("hilo", [t["tipo"] for t in c.get("/objetos/tipos").json()["tipos"]])
            self.assertEqual(c.get("/objetos/correo:x").status_code, 404)
            self.assertEqual(c.post("/objetos/archivo:nota.md/acciones/borrar", json={}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
