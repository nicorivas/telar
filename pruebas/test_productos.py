"""Los productos y sus ideas (telar.productos) y el formato de una idea (telar.tipos.registro)."""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar.tipos import registro
from telar.tipos.registro import REGISTRO

IDEA = """---
titulo: Versión corta del taller
estado: idea   # idea · evaluando · priorizada
valor: alto
origen: "retro: octubre"
etiquetas: [a, b]
---
Lo que se propone.

## Historia
- 2026-10-29 10:00 [creada]
"""


class ElRegistro(Prueba):
    def test_leer_y_escribir_sin_cambios_da_los_mismos_bytes(self):
        r = REGISTRO.leer(IDEA, "I01")
        self.assertEqual(r.campos, {"titulo": "Versión corta del taller", "estado": "idea", "valor": "alto",
                                    "origen": "retro: octubre", "etiquetas": "[a, b]"})
        self.assertEqual((r.cuerpo, r.historia), ("Lo que se propone.", ["2026-10-29 10:00 [creada]"]))
        self.assertEqual(REGISTRO.escribir(IDEA, r, r), IDEA)

    def test_un_cambio_toca_solo_su_linea_y_suma_a_la_historia(self):
        r = REGISTRO.leer(IDEA, "I01")
        nuevo = REGISTRO.escribir(IDEA, r, registro.cambiar(r, {"estado": "priorizada", "esfuerzo": "bajo"}))
        antes, despues = IDEA.splitlines(), nuevo.splitlines()
        self.assertEqual(despues[2], "estado: priorizada")
        self.assertIn("esfuerzo: bajo", despues[:9])
        self.assertEqual([x for x in antes if x not in despues], ["estado: idea   # idea · evaluando · priorizada"])
        self.assertRegex(despues[-1], r"^- \d{4}-\d\d-\d\d \d\d:\d\d \[cambio\] estado: idea → priorizada, esfuerzo: — → bajo$")
        self.assertEqual(REGISTRO.leer(nuevo).campos["origen"], "retro: octubre")

    def test_uno_nuevo_se_relee_igual(self):
        r = registro.nuevo({"titulo": "Algo: con dos puntos", "estado": "idea", "vacio": ""}, "Por qué.")
        r = r.model_copy(update={"id": "I02"})
        self.assertEqual(REGISTRO.leer(REGISTRO.nuevo(r), "I02"), r)


class LosProductos(Prueba):
    """Sobre el repositorio de ejemplo: sus proyectos son los productos."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name) / "ejemplo"
        shutil.copytree(EJEMPLO, self.raiz)
        os.environ["TELAR_RAIZ"] = str(self.raiz)
        (self.raiz / ".telar" / "productos.yaml").write_text(
            "productos:\n  arquetipo: proyecto\n  nombre: encargos\n  campos:\n    carpeta: '{ruta:-1}'\n"
            "    encargo: '{campo:Encargo}'\n")

    def correr(self, *argv):
        from telar import cli

        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = cli.main(["productos", *argv])
        return codigo, (json.loads(salida.getvalue()) if "--json" in argv and codigo == 0 else salida.getvalue())

    def test_la_lista_con_sus_campos(self):
        codigo, d = self.correr("--json")
        self.assertEqual(codigo, 0, d)
        faro = next(p for p in d["productos"] if p["ruta"] == "proyectos/faro")
        self.assertEqual(faro["campos"], {"carpeta": "faro", "encargo": "Municipalidad de la costa"})
        self.assertEqual((faro["ideas"], d["declaraciones"][0]["nombre"]), ([], "encargos"))

    def test_crear_mover_y_no_pisar(self):
        codigo, i = self.correr("crear", "proyectos/faro", "Lámpara LED", "--campo", "valor=alto", "--json")
        self.assertEqual(codigo, 0, i)
        self.assertEqual((i["id"], i["estado"], i["direccion"]), ("I01", "idea", "idea:proyectos/faro/I01"))
        self.assertTrue((self.raiz / "proyectos/faro/backlog/README.md").is_file())
        codigo, j = self.correr("cambiar", i["direccion"], "--campo", "estado=priorizada", "--version", i["version"], "--json")
        self.assertEqual((codigo, j["estado"]), (0, "priorizada"))
        self.assertIn("[cambio] estado: idea → priorizada", (self.raiz / "proyectos/faro/backlog/I01.md").read_text())
        # con la versión de antes, no: alguien la cambió desde que se leyó
        codigo, _ = self.correr("cambiar", i["direccion"], "--campo", "estado=lanzada", "--version", i["version"])
        self.assertNotEqual(codigo, 0)
        # lo que no es de sus estados o de sus niveles, tampoco
        self.assertNotEqual(self.correr("cambiar", i["direccion"], "--campo", "estado=quizas")[0], 0)
        self.assertNotEqual(self.correr("cambiar", i["direccion"], "--campo", "valor=altisimo")[0], 0)
        _, d = self.correr("--json")
        self.assertEqual([x["estado"] for p in d["productos"] for x in p["ideas"]], ["priorizada"])

    def test_lo_que_no_es_un_producto(self):
        self.assertNotEqual(self.correr("crear", "notas", "x")[0], 0)
        self.assertNotEqual(self.correr("cambiar", "idea:proyectos/faro/I09", "--campo", "estado=idea")[0], 0)

    def test_un_yaml_mal_escrito_se_dice(self):
        (self.raiz / ".telar" / "productos.yaml").write_text("productos: {}\n")
        codigo, d = self.correr("--json")
        self.assertEqual((codigo, d["productos"]), (0, []))
        self.assertIn("arquetipo", d["fallas"][0])


class DesdeUnLienzo(LosProductos):
    def test_un_modulo_crea_y_mueve_solo_con_permiso(self):
        from telar.cli import Contexto
        from telar.config import cargar as cargar_config
        from telar.servicios import ErrorDeServicio, lienzos

        modulo = Path(self.tmp.name) / "p"
        modulo.mkdir()
        (modulo / "modulo.toml").write_text('[pestana]\ncomando = ["x"]\n[permisos]\nordenes = ["idea"]\n')
        ruta = Path(self.tmp.name) / "config.toml"
        # su propio estado: las concesiones no van a las de quien corre las pruebas
        ruta.write_text(f'estado = "{Path(self.tmp.name) / "estado"}"\n[modulos.p]\ncarpeta = "{modulo}"\n')
        os.environ["TELAR_CONFIG"] = str(ruta)
        ctx = Contexto(config=cargar_config(None))
        nueva = {"producto": "proyectos/faro", "titulo": "Lámpara LED", "campos": {"valor": "medio"}}
        with self.assertRaises(ErrorDeServicio) as e:
            lienzos.pedir(ctx, "bloque:p", "idea", nueva)
        self.assertEqual(e.exception.codigo, 403)
        lienzos.conceder(ctx, "p", "idea", "concedido")
        i = lienzos.pedir(ctx, "bloque:p", "idea", nueva)["datos"]
        self.assertEqual((i["id"], i["campos"]["valor"]), ("I01", "medio"))
        j = lienzos.pedir(ctx, "bloque:p", "idea", {"direccion": i["direccion"], "version": i["version"],
                                                     "campos": {"estado": "en-curso"}})["datos"]
        self.assertEqual(j["estado"], "en-curso")
        with self.assertRaises(ErrorDeServicio) as e:   # con la versión de antes: alguien la cambió
            lienzos.pedir(ctx, "bloque:p", "idea", {"direccion": i["direccion"], "version": i["version"], "campos": {"estado": "lanzada"}})
        self.assertEqual(e.exception.codigo, 409)


class IdeasYTareas(LosProductos):
    """Una tarea que es una idea pasa al backlog; una idea abre tareas operativas."""

    def setUp(self):
        super().setUp()
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text(f'estado = "{Path(self.tmp.name) / "estado"}"\n[tipos.tarea]\ncarpeta = "{Path(self.tmp.name) / "tareas"}"\n')
        os.environ["TELAR_CONFIG"] = str(ruta)
        from telar.cli import Contexto
        from telar.config import cargar as cargar_config
        from telar.servicios import tipos as st

        self.ctx = Contexto(config=cargar_config(None))
        self.t = st.crear(self.ctx, {"titulo": "Sección de cambio en la página", "contexto": "Lo pidió un cliente."})

    def test_una_tarea_pasa_al_backlog_y_se_descarta(self):
        from telar import objetos, productos
        from telar.servicios import tipos as st

        acciones = {a.nombre: a for a in objetos.ver(self.ctx, f"tarea:{self.t.id}").acciones}
        self.assertIn("proyectos/faro", [x["valor"] for x in acciones["al_backlog"].opciones["producto"]])
        h = objetos.hacer(self.ctx, f"tarea:{self.t.id}", "al_backlog", {"producto": "proyectos/faro"})
        i = productos.ver(self.ctx, h.resultado["idea"])
        self.assertEqual((i["titulo"], i["campos"]["origen"]), ("Sección de cambio en la página", f"tarea:{self.t.id}"))
        self.assertTrue(i["cuerpo"].startswith("Lo pidió un cliente.\n\nVenía de la tarea "), i["cuerpo"])
        self.assertIn("[creada]", i["cuerpo"])
        self.assertEqual(st.obtener(self.ctx, self.t.id).estado, "descartada")
        # una ya cerrada no se lleva dos veces
        with self.assertRaises(productos.ErrorDeProductos):
            productos.desde_tarea(self.ctx, self.t.id, "proyectos/faro")

    def test_una_idea_abre_una_tarea_y_la_muestra(self):
        from telar import objetos, productos
        from telar.servicios import tipos as st

        i = productos.crear(self.ctx, "proyectos/molino", "Mantención anual")
        h = objetos.hacer(self.ctx, i["direccion"], "tarea", {"titulo": "Cotizar la mantención"})
        t = st.obtener(self.ctx, h.resultado["tarea"])
        self.assertEqual((t.proyecto, t.origen), ("proyectos/molino", i["direccion"]))
        molino = next(p for p in productos.listar(self.ctx)["productos"] if p["ruta"] == "proyectos/molino")
        self.assertEqual([x["id"] for x in molino["ideas"][0]["tareas"]], [t.id])
        self.assertIn(f"tarea {t.id}", productos.ver(self.ctx, i["direccion"])["ultima"])
        # moverla por su menú, eligiendo el estado
        o = objetos.ver(self.ctx, i["direccion"])
        self.assertIn("priorizada", [x["valor"] for x in next(a for a in o.acciones if a.nombre == "mover").opciones["estado"]])
        self.assertEqual(objetos.hacer(self.ctx, i["direccion"], "mover", {"estado": "priorizada"}).objeto.estado, "priorizada")
