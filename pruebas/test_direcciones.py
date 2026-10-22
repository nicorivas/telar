"""La dirección de cada objeto en las salidas JSON que lo nombran (telar.objetos, docs/contratos.md): los hilos de
`telar hilos` y `telar ficha`, las unidades de `telar proyectos`, las tareas del tipo en `telar pendientes`, la
ficha de una tarea y lo que da `telar tipo tarea`. Se agrega `direccion` y nada más cambia; la que sale es la
misma que `telar objeto` lee y devuelve."""

from __future__ import annotations

import datetime as _dt
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)
from test_ordenes import Orden

from telar import objetos
from telar.modelo import Item

TAREA = """---
titulo: Llamar a Ana por el faro
estado: activa
prioridad: 1
proyecto: proyectos/faro
---
Que confirme la fecha.
"""


class EnLasOrdenesDelEjemplo(Orden):
    """Contra el workspace de ejemplo: los hilos, su ficha, las unidades y los pendientes de los documentos."""

    def test_cada_hilo_trae_su_direccion(self):
        self.vincular_faro()
        hilo = next(h for h in self.json_de("hilos", "--json")["hilos"] if h["nombre"] == "faro")
        self.assertEqual(hilo["direccion"], "hilo:faro")
        # sin ficha también: la dirección no sale del documento
        hilo = self.json_de("hilos", "--json", "--sin-ficha")["hilos"][0]
        self.assertEqual(hilo["direccion"], "hilo:faro")

    def test_la_ficha_de_un_hilo_trae_su_direccion(self):
        self.vincular_faro()
        self.assertEqual(self.json_de("ficha", "faro", "--json")["hilo"]["direccion"], "hilo:faro")

    def test_cada_unidad_trae_la_direccion_que_abre_telar_objeto(self):
        unidades = self.json_de("proyectos", "--json")["proyectos"]
        self.assertTrue(unidades)
        for u in unidades:
            self.assertEqual(u["direccion"], f"proyecto:{u['ruta'].strip('/')}")
            self.assertEqual(objetos.leer(u["direccion"]), ("proyecto", u["ruta"].strip("/"), ""))
        faro = next(u for u in unidades if u["ruta"] == "proyectos/faro")
        self.assertEqual(faro["direccion"], "proyecto:proyectos/faro")

    def test_un_pendiente_de_un_documento_no_tiene_direccion(self):
        self.vincular_faro()
        filas = self.json_de("pendientes", "--json", "--repo")["pendientes"]
        self.assertTrue(filas)
        self.assertTrue(all(f["direccion"] == "" for f in filas))


class LaDireccionNoEsUnCampoDelObjeto(Prueba):
    """`telar objeto` arma sus campos con lo que dan las salidas: la dirección va en `direccion`, no repetida."""

    def test_un_proyecto(self):
        from telar.servicios import proyectos

        lista = proyectos.Proyectos(raiz="/x", proyectos=[{"ruta": "proyectos/faro", "direccion": "proyecto:proyectos/faro",
                                                           "nombre": "Faro", "arquetipo": "proyecto", "hilo": ""}])
        with mock.patch.object(proyectos, "lista", return_value=lista):
            o = objetos.ver(SimpleNamespace(config=SimpleNamespace(modulos=())), "proyecto:proyectos/faro")
        self.assertEqual(o.direccion, "proyecto:proyectos/faro")
        self.assertNotIn("direccion", o.campos)

    def test_una_tarea(self):
        from telar.servicios import tipos as servicio

        t = servicio.TareaConVersion(id="T84", titulo="Llamar a Ana", version="abc")
        with mock.patch.object(servicio, "obtener", return_value=t):
            o = objetos.ver(SimpleNamespace(config=SimpleNamespace(modulos=())), "tarea:T84")
        self.assertEqual(o.direccion, "tarea:T84")
        self.assertNotIn("direccion", o.campos)


class LaFormaDeLaDireccion(Prueba):
    """Lo que un id no puede llevar tal cual va escapado, y `leer` y `buscar` devuelven el id como era."""

    def test_un_proyecto_va_sin_barras_en_los_bordes(self):
        self.assertEqual(objetos.direccion_de("proyecto", "/proyectos/faro/"), "proyecto:proyectos/faro")

    def test_un_nombre_con_arroba_no_se_lee_como_la_maquina(self):
        d = objetos.direccion_de("hilo", "Faro@casa")
        self.assertEqual(d, "hilo:Faro%40casa")
        self.assertEqual(objetos.leer(d), ("hilo", "Faro@casa", ""))
        # con la máquina de verdad, también
        self.assertEqual(objetos.leer(objetos.direccion_de("hilo", "Faro@casa", "servidor")),
                         ("hilo", "Faro@casa", "servidor"))
        # la de siempre sigue diciendo lo mismo
        self.assertEqual(objetos.leer("hilo:Faro@casa"), ("hilo", "Faro", "casa"))

    def test_un_nombre_con_espacios_se_encuentra_en_un_texto(self):
        d = objetos.direccion_de("hilo", "◌ a solas")
        self.assertEqual(d, "hilo:◌%20a%20solas")
        ctx = SimpleNamespace(config=SimpleNamespace(modulos=()))
        self.assertEqual(objetos.buscar(ctx, f"mira {d} y tarea:T84."), [("hilo", "◌ a solas", ""), ("tarea", "T84", "")])

    def test_el_escape_mismo_va_escapado(self):
        d = objetos.direccion_de("tarea", "100%")
        self.assertEqual(d, "tarea:100%25")
        self.assertEqual(objetos.leer(d).id, "100%")

    def test_los_ids_de_siempre_no_cambian(self):
        for tipo, id in (("tarea", "T84"), ("proyecto", "proyectos/faro"), ("archivo", "telar:docs/x.md"), ("hilo", "Faro")):
            self.assertEqual(objetos.direccion_de(tipo, id), f"{tipo}:{id}")

    def test_un_hilo_con_arroba_en_telar_hilos(self):
        from telar.modelo import Hilo
        from telar.ordenes import _comun

        h = Hilo(id="@1", nombre="Faro@casa", ruta=Path("/x"))
        j = _comun.json_hilo(h, _comun.Telar(hilos=[h], raiz=Path("/x")), con_ficha=False)
        self.assertEqual(objetos.leer(j["direccion"]).id, "Faro@casa")


class LosHilosDeOtrasMaquinas(Prueba):
    def test_traen_su_direccion(self):
        from telar import bus as mod_bus
        from telar import espejo as mod_espejo
        from telar.servicios import hilos

        ctx = SimpleNamespace(config=SimpleNamespace(bus=SimpleNamespace(url="nats://x")))
        registro = {"Faro": {"nombre": "Faro", "maquina": "servidor", "vivo": True}}
        with mock.patch.object(mod_bus, "estados", return_value=registro), \
                mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(mod_espejo, "leer_todos", return_value=[]):
            otras, _, aviso = hilos._red(ctx)
        self.assertEqual(aviso, "")
        self.assertEqual(hilos.OtroHilo(**otras[0]).direccion, "hilo:Faro")


class _ConTareas(Prueba):
    """Un proveedor del tipo `tarea` y otro cualquiera, y las tareas del tipo en una carpeta de aquí."""

    def setUp(self):
        super().setUp()
        from telar.config import Config, Proveedor, Tipo
        from telar.servicios import tareas, tipos

        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "T84.md").write_text(TAREA, encoding="utf-8")
        provs = {"tareas": Proveedor(nombre="tareas", opciones={"tipo": "tipo", "carpeta": str(self.dir)}),
                 "agenda": Proveedor(nombre="agenda", opciones={"tipo": "comando", "comando": ["true"]})}
        self.cfg = Config(raiz=self.dir, estado=self.dir / "e", proveedores=provs,
                          tipos=(Tipo(clave="tarea", carpeta=str(self.dir)),))
        self.ctx = SimpleNamespace(config=self.cfg)
        for mod, nombre in ((tareas, "_subir"), (tipos, "subir")):
            p = mock.patch.object(mod, nombre)
            p.start()
            self.addCleanup(p.stop)


class LasTareasDelTipo(_ConTareas):
    """Solo las tareas del tipo tienen dirección; las de otro proveedor, no."""

    def test_en_los_pendientes(self):
        from telar import alla
        from telar.ordenes import _comun
        from telar.ordenes import pendientes as orden

        items = [Item(proveedor="tareas", id="T84", titulo="Llamar a Ana", clase="tarea"),
                 Item(proveedor="agenda", id="ev1", titulo="Reunión con Faro", clase="evento")]
        with mock.patch.object(alla, "consultar", return_value=(items, [])):
            filas, _ = orden.de_proveedores(self.ctx, _comun.Telar(hilos=[], raiz=self.dir), _dt.date(2026, 10, 21))
        self.assertEqual({f["id"]: f["direccion"] for f in filas}, {"T84": "tarea:T84", "ev1": ""})

    def test_en_la_ficha(self):
        from telar.servicios import tareas

        self.assertEqual(tareas.ficha(self.ctx, "T84").model_dump()["direccion"], "tarea:T84")

    def test_la_pone_el_proveedor_del_tipo(self):
        # el servicio la completa si falta: aquí se fija que el proveedor ya la trae
        from telar.proveedores import tareas as mod_prov

        pagina, _ = mod_prov.DeTipo(self.cfg.proveedores["tareas"]).ficha("T84")
        self.assertEqual(pagina["direccion"], "tarea:T84")

    def test_en_la_ficha_que_la_trae_vacia(self):
        # un `detalle` que imprime "direccion": "" (o null) no tumba la ficha: se pisa
        from telar.servicios import Pagina, tareas

        for vacia in ("", None):
            with mock.patch.object(tareas, "_ficha", return_value=Pagina(titulo="T84", direccion=vacia)):
                self.assertEqual(tareas.ficha(self.ctx, "T84").model_dump()["direccion"], "tarea:T84")

    def test_en_la_ficha_que_da_otra_maquina_de_antes(self):
        # una máquina de antes de las direcciones da la ficha sin ella: se le pone aquí
        from telar.servicios import tareas

        with mock.patch.object(tareas, "_alla", return_value="servidor"), \
                mock.patch.object(tareas, "_pedir_alla", return_value={"titulo": "T84 · Llamar a Ana", "bloques": []}):
            self.assertEqual(tareas.ficha(self.ctx, "T84").model_dump()["direccion"], "tarea:T84")

    def test_la_ficha_de_otro_proveedor_no_la_inventa(self):
        from telar.servicios import Pagina, tareas

        with mock.patch.object(tareas, "_ficha", return_value=Pagina(titulo="ev1")):
            self.assertNotIn("direccion", tareas.ficha(self.ctx, "ev1", "agenda").model_dump())

    def correr_tipo(self, *argv) -> dict:
        from telar.ordenes import tipo

        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            codigo = tipo.main([*argv, "--json"], self.ctx)
        self.assertEqual(codigo, 0, out.getvalue())
        return json.loads(out.getvalue())

    def test_en_telar_tipo_tarea(self):
        self.assertEqual(self.correr_tipo("tarea", "ver", "T84")["direccion"], "tarea:T84")
        self.assertEqual([t["direccion"] for t in self.correr_tipo("tarea", "lista")["tareas"]], ["tarea:T84"])
        nueva = self.correr_tipo("tarea", "crear", "--params", '{"titulo": "Pedir el plano"}')
        self.assertEqual(nueva["direccion"], f"tarea:{nueva['id']}")
        self.assertEqual(self.correr_tipo("tarea", "anotar", "T84", "--params", '{"texto": "le escribí"}')["direccion"],
                         "tarea:T84")
        self.assertEqual(self.correr_tipo("tarea", "borrar", nueva["id"]),
                         {"id": nueva["id"], "direccion": f"tarea:{nueva['id']}", "borrada": True})
        # el archivo no la guarda: es de la salida, no de la tarea
        self.assertNotIn("direccion", (self.dir / "T84.md").read_text())

    def test_en_telar_tipo_tarea_de_una_maquina_de_antes(self):
        from telar import bus as mod_bus
        from telar.config import Bus, Config, Tipo

        cfg = Config(raiz=self.dir, estado=self.dir / "e", bus=Bus(url="nats://x", maquina="laptop"),
                     tipos=(Tipo(clave="tarea", en="servidor"),))
        self.ctx = SimpleNamespace(config=cfg)
        vieja = {"id": "T90", "titulo": "Pedir el plano", "version": "a" * 16}
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "codigo": 0, "salida": json.dumps(vieja)}):
            self.assertEqual(self.correr_tipo("tarea", "ver", "T90")["direccion"], "tarea:T90")
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "codigo": 0,
                                                               "salida": '{"id": "T90", "borrada": true}'}):
            self.assertEqual(self.correr_tipo("tarea", "borrar", "T90")["direccion"], "tarea:T90")


class DoctorAvisa(_ConTareas):
    """Las direcciones `tarea:<id>` de los pendientes se abren en la carpeta de [tipos.tarea]."""

    def avisos(self):
        from telar.ordenes import doctor

        return doctor._tareas_del_tipo(self.ctx)

    def test_la_misma_carpeta_no_avisa(self):
        self.assertEqual(self.avisos(), [])

    def test_otra_carpeta_avisa(self):
        from telar.config import Config, Tipo

        otra = self.dir / "otra"
        otra.mkdir()
        self.ctx = SimpleNamespace(config=Config(raiz=self.dir, estado=self.dir / "e", proveedores=self.cfg.proveedores,
                                                 tipos=(Tipo(clave="tarea", carpeta=str(otra)),)))
        avisos = self.avisos()
        self.assertEqual([a["nombre"] for a in avisos], ["tareas"])
        self.assertIn(str(otra), avisos[0]["dice"])

    def test_sin_tipos_tarea_avisa(self):
        from telar.config import Config

        self.ctx = SimpleNamespace(config=Config(raiz=self.dir, estado=self.dir / "e", proveedores=self.cfg.proveedores))
        self.assertEqual(len(self.avisos()), 1)

    def test_si_viven_en_otra_maquina_no_compara(self):
        from telar.config import Config, Tipo

        self.ctx = SimpleNamespace(config=Config(raiz=self.dir, estado=self.dir / "e", proveedores=self.cfg.proveedores,
                                                 tipos=(Tipo(clave="tarea", en="servidor"),)))
        self.assertEqual(self.avisos(), [])


try:
    from fastapi.testclient import TestClient

    from telar import api
except ImportError:  # sin el extra «serve»
    api = None


@unittest.skipIf(api is None, "sin fastapi")
class EnLaApi(_ConTareas):
    def setUp(self):
        super().setUp()
        api.app.dependency_overrides[api.contexto] = lambda: self.ctx
        self.addCleanup(api.app.dependency_overrides.clear)
        self.c = TestClient(api.app)

    def test_la_ficha_y_el_tipo(self):
        self.assertEqual(self.c.get("/tareas/T84").json()["direccion"], "tarea:T84")
        self.assertEqual(self.c.get("/tipos/tarea/T84").json()["direccion"], "tarea:T84")
        self.assertEqual([t["direccion"] for t in self.c.get("/tipos/tarea").json()["tareas"]], ["tarea:T84"])


if __name__ == "__main__":
    unittest.main()
