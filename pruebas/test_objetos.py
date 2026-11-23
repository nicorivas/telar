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
        self.assertEqual(str(objetos.leer(" proyecto:proyectos/faro ")), "proyecto:proyectos/faro")
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

    def test_un_mensaje_a_un_hilo_de_otra_maquina_mira_que_alla_exista(self):
        from telar import bus, espejo
        from telar.ordenes import mensaje

        fotos = [{"nombre": "servidor", "hilos": [{"nombre": "Faro"}]}]
        ctx = SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="nats://x")))
        with mock.patch.object(bus, "hay_bus", return_value=True), mock.patch.object(bus, "maquina", return_value="laptop"), \
                mock.patch.object(espejo, "leer_todos", return_value=fotos):
            self.assertEqual(mensaje._por_nombre(ctx, "hilo:Faro@servidor"), "Faro")
            self.assertEqual(mensaje._por_nombre(ctx, "hilo:Faro"), "Faro")  # sin máquina: el nombre, como siempre
            with self.assertRaises(mensaje.NoHayHilo):
                mensaje._por_nombre(ctx, "hilo:Telar@servidor")
            with self.assertRaises(mensaje.NoHayHilo):
                mensaje._por_nombre(ctx, "hilo:Faro@otra")
        # y por el servicio, un 404 (no una falla del bus)
        from telar.servicios import mensajes

        with mock.patch.object(mensaje, "_por_direccion", side_effect=mensaje.NoHayHilo("servidor no tiene un hilo «X»")):
            with self.assertRaises(ErrorDeServicio) as e:
                mensajes.enviar(ctx, "hilo:X@servidor", "hola")
        self.assertEqual(e.exception.codigo, 404)

    def test_un_tipo_que_no_hay(self):
        with self.assertRaises(ErrorDeServicio) as e:
            objetos.ver(self.ctx, "correo:abc")
        self.assertEqual(e.exception.codigo, 404)
        self.assertIn("tarea", str(e.exception))

    def test_listar_los_de_un_tipo_de_fabrica(self):
        from telar import agentes as mod_agentes
        from telar.servicios import tipos as servicio

        tareas = servicio.Tareas(tareas=[servicio.TareaConVersion(id="T9", titulo="Llamar a Ana", estado="activa", version="abc"),
                                         servicio.TareaConVersion(id="T10", titulo="Escribir", estado="activa", version="def")],
                                 fallas={"T11.md": "no se lee"})
        with mock.patch.object(servicio, "lista", return_value=tareas):
            r = objetos.listar(self.ctx, "tarea")
        self.assertEqual([(o.direccion, o.titulo, o.version) for o in r.objetos],
                         [("tarea:T9", "Llamar a Ana", "abc"), ("tarea:T10", "Escribir", "def")])
        self.assertIn("completar", [a.nombre for a in r.objetos[0].acciones])
        self.assertEqual(r.fallas, ["T11.md: no se lee"])
        agente = SimpleNamespace(clave="faro", nombre="Faro", residente=True, para="cuida el faro")
        with mock.patch.object(mod_agentes, "descubrir", return_value=[agente]), \
                mock.patch.object(mod_agentes, "como_json", return_value={"clave": "faro", "nombre": "Faro", "direccion": "agente:faro",
                                                                          "para": "cuida el faro", "modelo": "opus"}):
            r = objetos.listar(self.ctx, "agente:")
            self.assertEqual(r.objetos[0], objetos.ver(self.ctx, "agente:faro"))
        self.assertEqual((r.objetos[0].direccion, r.objetos[0].campos), ("agente:faro", {"modelo": "opus"}))
        # los que no saben listar lo dicen, y un tipo que no hay, también
        for tipo, codigo in (("archivo", 404), ("permiso", 404), ("correo", 404), ("Tarea", 422), ("tarea:T9", 422)):
            with self.assertRaises(ErrorDeServicio) as e:
                objetos.listar(self.ctx, tipo)
            self.assertEqual(e.exception.codigo, codigo, tipo)
        self.assertEqual([objetos.es_tipo(x) for x in ("tarea", "tarea:", " hilo ", "tarea:T9", "Tarea", "", "a b")],
                         ["tarea", "tarea", "hilo", "", "", "", ""])


VER = """#!/usr/bin/env python3
import json, sys
p = json.load(sys.stdin)
if sys.argv[1] == "ver":
    print(json.dumps({"titulo": "el correo " + p["id"], "estado": "sin leer", "campos": {"de": "ana"}}))
elif sys.argv[1] == "lista":
    if p.get("tipo") != "correo":
        print("no sé de " + str(p.get("tipo")), file=sys.stderr); sys.exit(2)
    print(json.dumps({"objetos": [
        {"id": "1a2b", "titulo": "el correo 1a2b", "estado": "sin leer", "campos": {"de": "ana"}, "direccion": "otra:x"},
        {"id": "3c4d", "titulo": "el correo 3c4d", "acciones": []},
        {"titulo": "uno sin id"},
        {"id": "5e6f", "campos": "no es un objeto"},
        "ni siquiera un objeto"], "fallas": ["un correo que no se leyó"]}))
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
[ordenes.lista]
comando = ["bin/c", "lista"]
consulta = true
[ordenes.suelta]
comando = ["bin/c", "lista"]
[objetos.correo]
ver = "ver"
acciones = ["archivar"]
listar = "lista"
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

    def test_lista_los_suyos_con_su_consulta(self):
        m = modulos.leer("correo", self.carpeta)
        self.assertEqual(m.objetos["correo"]["listar"], "lista")
        ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))
        self.assertTrue(objetos.tipos(ctx)["correo"].lista)
        for como in ("correo", "correo:", " correo "):
            r = objetos.listar(ctx, como)
            self.assertEqual(r.tipo, "correo")
            # telar pone la dirección y el tipo (la que traiga el módulo no vale); sin acciones, las del tipo
            self.assertEqual([(o.direccion, o.tipo, o.id, o.titulo) for o in r.objetos],
                             [("correo:1a2b", "correo", "1a2b", "el correo 1a2b"), ("correo:3c4d", "correo", "3c4d", "el correo 3c4d")])
            self.assertEqual(([a.nombre for a in r.objetos[0].acciones], r.objetos[1].acciones), (["archivar"], []))
            self.assertEqual(r.objetos[0].campos, {"de": "ana"})
            # lo que no se pudo leer se dice: lo del módulo, lo que no trae id y lo que no tiene la forma de un objeto
            self.assertEqual(r.fallas[0], "un correo que no se leyó")
            self.assertEqual(len(r.fallas), 4)
            self.assertIn("correo:5e6f", r.fallas[2])

    def test_su_plural(self):
        # cómo se llaman juntos en una lista (su fuente en telar buscar); sin él, el tipo
        m = modulos.leer("correo", self.carpeta)
        ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))
        self.assertNotIn("plural", m.objetos["correo"])
        self.assertEqual(objetos.tipos(ctx)["correo"].plural, "correo")
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO.replace('descripcion = "un correo"', 'descripcion = "un correo"\nplural = " los  correos "'))
        m = modulos.leer("correo", self.carpeta)
        self.assertEqual(m.objetos["correo"]["plural"], "los correos")
        ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))
        self.assertEqual(objetos.tipos(ctx)["correo"].plural, "los correos")
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO.replace('descripcion = "un correo"', 'descripcion = "un correo"\nplural = 2'))
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.leer("correo", self.carpeta)

    def test_sin_listar_dice_que_no_lista(self):
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO.replace('listar = "lista"\n', ""))
        m = modulos.leer("correo", self.carpeta)
        self.assertNotIn("listar", m.objetos["correo"])
        ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))
        self.assertFalse(objetos.tipos(ctx)["correo"].lista)
        with self.assertRaises(ErrorDeServicio) as e:
            objetos.listar(ctx, "correo")
        self.assertEqual(e.exception.codigo, 404)
        self.assertIn("no lista", str(e.exception))
        # y ver sigue igual
        self.assertEqual(objetos.ver(ctx, "correo:1a2b").titulo, "el correo 1a2b")

    def test_una_respuesta_sin_la_forma_es_una_falla_del_modulo(self):
        (self.carpeta / "bin" / "c").write_text("#!/bin/sh\necho '{\"correos\": []}'\n")
        m = modulos.leer("correo", self.carpeta)
        ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))
        with self.assertRaises(ErrorDeServicio) as e:
            objetos.listar(ctx, "correo")
        self.assertEqual(e.exception.codigo, 502)

    def test_un_tipo_debe_apuntar_a_sus_consultas(self):
        (self.carpeta / "modulo.toml").write_text(MANIFIESTO.replace('ver = "ver"', 'ver = "nada"'))
        with self.assertRaises(modulos.ErrorDeModulo):
            modulos.leer("correo", self.carpeta)
        # listar, también: una consulta suya (no una orden sin consulta, ni una que no está)
        for malo in ("suelta", "nada"):
            (self.carpeta / "modulo.toml").write_text(MANIFIESTO.replace('listar = "lista"', f'listar = "{malo}"'))
            with self.assertRaises(modulos.ErrorDeModulo):
                modulos.leer("correo", self.carpeta)

    def test_la_orden_lista_los_de_un_tipo(self):
        import io
        import json
        from contextlib import redirect_stdout

        from telar.ordenes import objeto

        m = modulos.leer("correo", self.carpeta)
        ctx = SimpleNamespace(config=SimpleNamespace(raiz=Path(self.tmp.name), modulos=(m,), repos=(), bus=None, origen=None))
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(objeto.main(["correo", "--listar", "--json"], ctx), 0)
        d = json.loads(salida.getvalue())
        self.assertEqual([o["direccion"] for o in d["objetos"]], ["correo:1a2b", "correo:3c4d"])
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(objeto.main(["--listar", "correo:"], ctx), 0)
        self.assertIn("correo:1a2b  sin leer  el correo 1a2b", salida.getvalue())
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(objeto.main(["--tipos", "--json"], ctx), 0)
        tipos = {t["tipo"]: t for t in json.loads(salida.getvalue())["tipos"]}
        self.assertEqual((tipos["correo"]["listar"], tipos["tarea"]["listar"], tipos["archivo"]["listar"]), (True, True, False))
        # un tipo sin --listar no es un objeto: lo dice, y cómo listarlo
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertNotEqual(objeto.main(["correo"], ctx), 0)
        self.assertIn("--listar", err.getvalue())

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

    def test_la_coleccion_de_un_tipo(self):
        from telar.servicios import tipos as servicio

        with tempfile.TemporaryDirectory() as tmp:
            api.app.dependency_overrides[api.contexto] = lambda: ctx_con(Path(tmp))
            self.addCleanup(api.app.dependency_overrides.clear)
            c = TestClient(api.app)
            tareas = servicio.Tareas(tareas=[servicio.TareaConVersion(id="T9", titulo="Llamar a Ana", estado="activa", version="abc")])
            with mock.patch.object(servicio, "lista", return_value=tareas):
                for ruta in ("/objetos/tarea", "/objetos/tarea:"):
                    r = c.get(ruta)
                    self.assertEqual(r.status_code, 200, ruta)
                    self.assertEqual((r.json()["tipo"], [o["direccion"] for o in r.json()["objetos"]], r.json()["fallas"]),
                                     ("tarea", ["tarea:T9"], []))
            self.assertEqual(c.get("/objetos/archivo").status_code, 404)   # no lista los suyos
            self.assertEqual(c.get("/objetos/correo").status_code, 404)    # no hay ese tipo
            tipos = {t["tipo"]: t["listar"] for t in c.get("/objetos/tipos").json()["tipos"]}
            self.assertEqual((tipos["tarea"], tipos["archivo"]), (True, False))


if __name__ == "__main__":
    unittest.main()
