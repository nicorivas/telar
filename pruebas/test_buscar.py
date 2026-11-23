"""Buscar sobre todo junto (`telar buscar`, `GET /buscar`, telar.servicios.buscar): todas las palabras, sin tildes; por
fuente, lo del título primero y lo que ya pasó al final; una fuente que falla no tumba a las demás; el mundo filtra solo
si se pide."""

from __future__ import annotations

import io
import json
import threading
import time
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar.servicios import ErrorDeServicio, Pagina
from telar.servicios import buscar as servicio

H = servicio.Hallado


def config(texto: str = "") -> cfg.Config:
    import tomllib

    return cfg.desde_dict({"raiz": "/casa", **tomllib.loads(texto)})


MUNDOS = """
[mundos.trabajo]
rutas = ["empresa/"]
[mundos.personal]
rutas = ["casa/"]
[tipos.tarea]
carpeta = "tareas"
"""


class Buscar(Prueba):
    def setUp(self):
        super().setUp()
        servicio.olvidar()
        self.addCleanup(servicio.olvidar)
        self.ctx = SimpleNamespace(config=config(MUNDOS))
        self.tareas = [
            (H(fuente="tareas", direccion="tarea:T1", titulo="Armar la vitrina", cuando="2026-11-10", mundo="trabajo"), "vitrina"),
            (H(fuente="tareas", direccion="tarea:T2", titulo="Pedir el vidrio", cuando="2026-11-12", mundo="trabajo"), "proyecto vitrina"),
            (H(fuente="tareas", direccion="tarea:T3", titulo="Fotografiar la Vitrína", cuando="2026-11-15", pasada=True, mundo="trabajo"), ""),
            (H(fuente="tareas", direccion="tarea:T4", titulo="Vender la vitrina vieja", cuando="2026-11-01", mundo="personal"), ""),
            (H(fuente="tareas", direccion="tarea:T5", titulo="Otra cosa", mundo=""), ""),
        ]
        self.parches = [mock.patch.object(servicio, "_esperas", return_value=[]),
                        mock.patch.object(servicio, "_tareas", return_value=self.tareas),
                        mock.patch.object(servicio, "_casillas", return_value=[]),
                        mock.patch.object(servicio, "_hilos", side_effect=RuntimeError("tmux no responde")),
                        mock.patch.object(servicio, "_proyectos", return_value=[])]
        for p in self.parches:
            p.start()
            self.addCleanup(p.stop)

    def fuente(self, r, clave):
        return next(f for f in r.fuentes if f.clave == clave)

    def test_por_fuente_lo_del_titulo_primero_y_lo_pasado_al_final(self):
        r = servicio.buscar(self.ctx, "VITRINA")
        t = self.fuente(r, "tareas")
        self.assertEqual(t.total, 4)
        self.assertEqual([h.direccion for h in t.hallados], ["tarea:T1", "tarea:T4", "tarea:T3", "tarea:T2"],
                         "en el título y vigentes (lo más nuevo antes), en el título y pasada, y solo en lo demás")
        self.assertEqual(r.mundos, ["trabajo", "personal"])
        self.assertEqual([f.clave for f in r.fuentes], ["esperas", "tareas", "casillas", "hilos", "proyectos"])

    def test_todas_las_palabras(self):
        r = servicio.buscar(self.ctx, "vitrina vieja")
        self.assertEqual([h.direccion for h in self.fuente(r, "tareas").hallados], ["tarea:T4"])
        self.assertEqual(self.fuente(servicio.buscar(self.ctx, "vidrio vitrina"), "tareas").total, 1, "una en el título, otra en lo demás")

    def test_una_fuente_que_falla_lo_dice_y_las_demas_siguen(self):
        r = servicio.buscar(self.ctx, "vitrina")
        self.assertIn("tmux no responde", self.fuente(r, "hilos").falla)
        self.assertEqual(self.fuente(r, "tareas").total, 4)

    def test_el_mundo_filtra_solo_si_se_pide(self):
        r = servicio.buscar(self.ctx, "vitrina", mundos=("personal",))
        self.assertEqual([h.direccion for h in self.fuente(r, "tareas").hallados], ["tarea:T4"])
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.buscar(self.ctx, "vitrina", mundos=("casa",))
        self.assertEqual(e.exception.codigo, 404)

    def test_las_fuentes_y_el_limite(self):
        r = servicio.buscar(self.ctx, "vitrina", fuentes=("tareas",), limite=2)
        self.assertEqual([f.clave for f in r.fuentes], ["tareas"])
        self.assertEqual((r.fuentes[0].total, len(r.fuentes[0].hallados)), (4, 2))
        with self.assertRaises(ErrorDeServicio) as e:
            servicio.buscar(self.ctx, "vitrina", fuentes=("nada",))
        self.assertEqual(e.exception.codigo, 404)
        # con `si_hay` (⌘K pide tres de una vez), la que aquí no hay se deja fuera y las demás vienen
        r = servicio.buscar(self.ctx, "vitrina", fuentes=("tareas", "objeto:doc"), limite=2, si_hay=True)
        self.assertEqual([f.clave for f in r.fuentes], ["tareas"])
        self.assertEqual(servicio.buscar(self.ctx, "vitrina", fuentes=("nada",), si_hay=True).fuentes, [])
        for q in ("", " x ", "   "):
            with self.subTest(q=q), self.assertRaises(ErrorDeServicio) as e:
                servicio.buscar(self.ctx, q)
            self.assertEqual(e.exception.codigo, 422)

    def test_primero_lo_del_mundo_puesto_antes_del_tope(self):
        # dos mundos desparejos, como los documentos de un repositorio grande de trabajo contra unos pocos personales: sin
        # `primero`, el tope se llena con lo de trabajo y lo personal, que también calza, no llega
        muchas = [(H(fuente="tareas", direccion=f"tarea:W{i}", titulo=f"Vitrina {i}", cuando=f"2026-11-{10 + i}", mundo="trabajo"), "")
                  for i in range(6)]
        pocas = [(H(fuente="tareas", direccion="tarea:P1", titulo="Otra cosa", cuando="2026-10-01", mundo="personal"), "vitrina"),
                 (H(fuente="tareas", direccion="tarea:S1", titulo="Suelta", cuando="2026-09-01", mundo=""), "vitrina")]
        with mock.patch.object(servicio, "_tareas", return_value=muchas + pocas):
            servicio.olvidar()
            sin = self.fuente(servicio.buscar(self.ctx, "vitrina", fuentes=("tareas",), limite=3), "tareas")
            con = servicio.buscar(self.ctx, "vitrina", fuentes=("tareas",), limite=3, primero="personal")
        self.assertEqual((sin.total, [h.mundo for h in sin.hallados]), (8, ["trabajo"] * 3))
        self.assertEqual(con.primero, "personal")
        t = self.fuente(con, "tareas")
        self.assertEqual(t.total, 8, "no esconde ni agrega: cuenta lo mismo")
        self.assertEqual([h.direccion for h in t.hallados], ["tarea:P1", "tarea:S1", "tarea:W5"],
                         "lo personal y lo sin clasificar primero; después, lo de los otros, en su orden de siempre")
        # un mundo que no se declara no ordena (la página puede traer uno de antes): no es un error
        with mock.patch.object(servicio, "_tareas", return_value=muchas + pocas):
            otro = servicio.buscar(self.ctx, "vitrina", fuentes=("tareas",), limite=3, primero="casa")
        self.assertEqual((otro.primero, [h.mundo for h in self.fuente(otro, "tareas").hallados]), ("", ["trabajo"] * 3))

    def test_sin_tipos_tarea_las_tareas_no_son_una_fuente(self):
        r = servicio.buscar(SimpleNamespace(config=config()), "vitrina")
        self.assertNotIn("tareas", [f.clave for f in r.fuentes])
        self.assertEqual(r.mundos, [])



class LasTareasDeVerdad(Prueba):
    """La fuente «tareas» sin parchar `_tareas`: lee las filas que devuelve `tipos.lista` de verdad (TareaConVersion, donde
    `cerrada_ya` es una propiedad), de la carpeta de aquí o de la máquina donde viven (`telar tipo tarea lista --json`)."""

    ARCHIVOS = {
        "T1.md": "---\ntitulo: Armar la vitrina\nestado: activa\nproyecto: empresa/tienda\netiquetas: local\n"
                 "creada: 2026-11-10\n---\nCon el vidrio templado.\n",
        "T2.md": "---\ntitulo: Pedir el vidrio\nestado: activa\nproyecto: empresa/tienda\netiquetas: vitrina\n"
                 "creada: 2026-11-12\navance: cotizado\n---\n",
        "T3.md": "---\ntitulo: Fotografiar la vitrina\nestado: hecha\nproyecto: empresa/tienda\ncreada: 2026-11-14\n"
                 "cerrada: 2026-11-15\n---\n",
        "T4.md": "---\ntitulo: Otra cosa\nestado: activa\nproyecto: casa/cocina\n---\nNada que ver.\n",
    }

    def setUp(self):
        super().setUp()
        import shutil
        import tempfile
        from pathlib import Path

        servicio.olvidar()
        self.addCleanup(servicio.olvidar)
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        for nombre, texto in self.ARCHIVOS.items():
            (self.dir / nombre).write_text(texto, encoding="utf-8")
        self.ctx = SimpleNamespace(config=config(MUNDOS.replace('carpeta = "tareas"', f'carpeta = "{self.dir}"')))

    def comprobar(self, r):
        t = next(f for f in r.fuentes if f.clave == "tareas")
        self.assertEqual(t.falla, "")
        self.assertEqual([(h.direccion, h.pasada, h.mundo, h.donde) for h in t.hallados],
                         [("tarea:T1", False, "trabajo", "tienda"), ("tarea:T3", True, "trabajo", "tienda"),
                          ("tarea:T2", False, "trabajo", "tienda")],
                         "en el título y vigente, en el título y cerrada, y por su etiqueta")
        self.assertEqual(servicio.buscar(self.ctx, "templado", fuentes=("tareas",)).fuentes[0].total, 1, "por su contexto")
        self.assertEqual(servicio.buscar(self.ctx, "cotizado", fuentes=("tareas",)).fuentes[0].total, 1, "por su avance")

    def test_las_de_la_carpeta_de_aqui(self):
        self.comprobar(servicio.buscar(self.ctx, "vitrina", fuentes=("tareas",)))

    def test_las_que_trae_la_maquina_donde_viven(self):
        from telar.servicios import tipos

        aqui = tipos.lista(self.ctx, "tarea", todas=True)
        servicio.olvidar()
        # lo que responde allá `telar tipo tarea lista --todas --json`: el modelo hecho JSON, sin propiedades
        salida = json.loads(json.dumps(aqui.model_dump(mode="json")))
        self.assertNotIn("cerrada_ya", salida["tareas"][0])
        with mock.patch.object(tipos, "_alla", return_value="servidor"), \
                mock.patch.object(tipos, "_pedir_alla", return_value=salida) as pedir:
            self.comprobar(servicio.buscar(self.ctx, "vitrina", fuentes=("tareas",)))
        self.assertEqual(pedir.call_args.args[2], ["tarea", "lista", "--todas"])

class LosBloques(Prueba):
    def test_sus_filas_con_lo_que_las_abre_y_su_pagina_guardada(self):
        c = config('[bloques.correo]\nnombre = "correo"\ncomando = ["x"]\n')
        ctx = SimpleNamespace(config=c)
        pagina = Pagina(titulo="correo", bloques=[{"titulo": "hoy", "items": [
            {"titulo": "Re: el vidrio de la vitrina", "texto": "de la vidriería", "fecha": "2026-11-16T10:00", "mensaje": "/correo 1a2b"},
            {"titulo": "Boletín", "texto": "vitrinas que venden", "marca": "✓"},
            {"titulo": "", "texto": "sin título: no cuenta"}]}])
        servicio.olvidar()
        self.addCleanup(servicio.olvidar)
        vacias = {f: mock.patch.object(servicio, f, return_value=[]) for f in ("_esperas", "_casillas", "_hilos", "_proyectos")}
        for p in vacias.values():
            p.start()
            self.addCleanup(p.stop)
        from telar.servicios import bloques

        with mock.patch.object(bloques, "pagina", return_value=pagina) as correr:
            r = servicio.buscar(ctx, "vitrina")
            servicio.buscar(ctx, "boletin")
        self.assertEqual(correr.call_count, 1, "la segunda búsqueda usa la página guardada")
        f = next(x for x in r.fuentes if x.clave == "bloque:correo")
        self.assertEqual(f.nombre, "correo")
        self.assertEqual([(h.titulo, h.donde, h.pasada) for h in f.hallados],
                         [("Re: el vidrio de la vitrina", "de la vidriería", False), ("Boletín", "vitrinas que venden", True)])
        self.assertEqual(f.hallados[0].datos, {"bloque": "correo", "mensaje": "/correo 1a2b"})

    def test_la_pagina_que_abrio_su_pestana_sirve_sin_correr_el_comando(self):
        from telar.servicios import bloques

        c = config('[bloques.correo]\nnombre = "correo"\ncomando = ["x"]\n')
        ctx = SimpleNamespace(config=c)
        servicio.olvidar()
        self.addCleanup(servicio.olvidar)
        self.addCleanup(bloques._GUARDADAS.clear)
        for f in ("_esperas", "_casillas", "_hilos", "_proyectos"):
            p = mock.patch.object(servicio, f, return_value=[])
            p.start()
            self.addCleanup(p.stop)
        datos = {"titulo": "correo", "bloques": [{"titulo": "hoy", "items": [{"titulo": "La vitrina nueva"}]}]}
        with mock.patch("telar.ordenes.seccion.correr", return_value=(datos, "")):
            bloques.pagina(ctx, "correo")  # su pestaña
        with mock.patch.object(bloques, "pagina", side_effect=AssertionError("no debía correr el comando")):
            r = servicio.buscar(ctx, "vitrina")
        f = next(x for x in r.fuentes if x.clave == "bloque:correo")
        self.assertEqual(([h.titulo for h in f.hallados], f.falla, f.tarde), (["La vitrina nueva"], "", False))
        self.assertTrue(f.leida)


# un módulo de mentira con dos tipos que listan: documentos (cada uno es un archivo, con `ruta_abs`) y fichas (que viven
# en un archivo, `archivo:`); y uno que no lista
LISTAR = r"""#!/usr/bin/env python3
import json, os, sys
p = json.load(sys.stdin)
raiz = os.environ["TELAR_RAIZ"]
if sys.argv[1] == "lista" and p.get("tipo") == "doc":
    print(json.dumps({"objetos": [
        {"id": "empresa/taller/notas/vitrina.md", "titulo": "La vitrina", "estado": "3 conexiones",
         "resumen": "Cómo se arma el vidrio templado.",
         "campos": {"ruta": "notas/vitrina.md", "ruta_abs": raiz + "/empresa/taller/notas/vitrina.md", "conexiones": 3}},
        {"id": "casa/ideas/vidrio.md", "titulo": "Una idea", "estado": "1 conexión", "resumen": "Otra vitrina, en casa.",
         "campos": {"ruta": "ideas/vidrio.md", "ruta_abs": raiz + "/casa/ideas/vidrio.md"}},
        {"id": "suelto.md", "titulo": "Suelto", "estado": "1 conexión", "resumen": "una vitrina sin mundo",
         "campos": {"ruta": "suelto.md", "ruta_abs": "suelto.md"}}]}))
elif sys.argv[1] == "lista" and p.get("tipo") == "ficha":
    print(json.dumps({"objetos": [{"id": "F-1", "titulo": "Vender la vitrina", "estado": "tomada",
                                   "campos": {"archivo": "archivo:empresa/fichas/F-1.md"}}]}))
elif sys.argv[1] == "rota":
    print(json.dumps({"objetos": [], "fallas": ["taller: el lector falló"]}))
else:
    print(json.dumps({"id": p.get("id")}))
"""

MODULO = """descripcion = "de mentira"
[ordenes.ver]
comando = ["bin/m", "ver"]
consulta = true
[ordenes.lista]
comando = ["bin/m", "lista"]
consulta = true
[ordenes.rota]
comando = ["bin/m", "rota"]
consulta = true
[objetos.doc]
ver = "ver"
listar = "lista"
plural = "documentos"
[objetos.ficha]
ver = "ver"
listar = "lista"
[objetos.suelta]
ver = "ver"
"""


class LosObjetosDeUnModulo(Prueba):
    """Cada tipo de objeto de un módulo que sabe listar es una fuente (`objeto:<tipo>`): por su título, su id y su
    resumen; dónde vive, su `campos.ruta`; su mundo, el de su ruta absoluta (o el de su `archivo:`); y lo que lo abre."""

    def setUp(self):
        super().setUp()
        import shutil
        import stat
        import tempfile
        from pathlib import Path

        servicio.olvidar()
        self.addCleanup(servicio.olvidar)
        self.raiz = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.raiz, ignore_errors=True)
        carpeta = self.raiz / "modulo"
        (carpeta / "bin").mkdir(parents=True)
        (carpeta / "modulo.toml").write_text(MODULO)
        m = carpeta / "bin" / "m"
        m.write_text(LISTAR)
        m.chmod(m.stat().st_mode | stat.S_IEXEC)
        self.carpeta = carpeta
        self.ctx = SimpleNamespace(config=self.config())
        for f in ("_esperas", "_casillas", "_hilos", "_proyectos"):
            p = mock.patch.object(servicio, f, return_value=[])
            p.start()
            self.addCleanup(p.stop)

    def config(self, manifiesto: str = MODULO):
        import tomllib

        (self.carpeta / "modulo.toml").write_text(manifiesto)
        return cfg.desde_dict({"raiz": str(self.raiz), **tomllib.loads(MUNDOS),
                               "modulos": {"mentira": {"carpeta": str(self.carpeta)}}})

    def fuente(self, r, clave):
        return next(f for f in r.fuentes if f.clave == clave)

    def test_una_fuente_por_tipo_que_lista_con_su_plural(self):
        r = servicio.buscar(self.ctx, "vitrina")
        claves = [(f.clave, f.nombre) for f in r.fuentes]
        self.assertEqual(claves[-2:], [("objeto:doc", "documentos"), ("objeto:ficha", "ficha")],
                         "después de lo propio; sin plural, el tipo; el que no lista no es una fuente")
        self.assertNotIn("objeto:suelta", [c for c, _ in claves])

    def test_cada_objeto_con_su_mundo_por_la_ruta_absoluta(self):
        r = servicio.buscar(self.ctx, "vitrina", fuentes=("objeto:doc",))
        docs = self.fuente(r, "objeto:doc")
        self.assertEqual((docs.falla, docs.total), ("", 3))
        h = {x.id: x for x in docs.hallados}
        vitrina = h["empresa/taller/notas/vitrina.md"]
        self.assertEqual((vitrina.direccion, vitrina.titulo, vitrina.donde, vitrina.estado, vitrina.mundo),
                         ("doc:empresa/taller/notas/vitrina.md", "La vitrina", "notas/vitrina.md", "3 conexiones", "trabajo"),
                         "el mundo, por la ruta absoluta: la relativa es de su repositorio anidado, no de la raíz")
        self.assertEqual(vitrina.datos, {"ruta_abs": str(self.raiz / "empresa/taller/notas/vitrina.md")}, "lo que lo abre en el visor")
        self.assertEqual(h["casa/ideas/vidrio.md"].mundo, "personal")
        self.assertEqual((h["suelto.md"].mundo, h["suelto.md"].datos), ("", {}), "una ruta que no es absoluta no dice nada")
        self.assertEqual([x.id for x in docs.hallados][0], "empresa/taller/notas/vitrina.md", "lo del título primero")

    def test_el_resumen_y_el_id_se_buscan_pero_no_son_el_titulo(self):
        docs = self.fuente(servicio.buscar(self.ctx, "templado", fuentes=("objeto:doc",)), "objeto:doc")
        self.assertEqual([x.titulo for x in docs.hallados], ["La vitrina"], "por su resumen")
        self.assertEqual(self.fuente(servicio.buscar(self.ctx, "taller notas", fuentes=("objeto:doc",)), "objeto:doc").total, 1, "por su ruta")
        r = servicio.buscar(self.ctx, "vitrina", fuentes=("objeto:doc",), mundos=("personal",))
        self.assertEqual([x.titulo for x in self.fuente(r, "objeto:doc").hallados], ["Una idea"], "en su resumen, y de su mundo")

    def test_el_que_vive_en_un_archivo_tiene_el_mundo_del_archivo(self):
        fichas = self.fuente(servicio.buscar(self.ctx, "vitrina", fuentes=("objeto:ficha",)), "objeto:ficha")
        [f] = fichas.hallados
        self.assertEqual((f.direccion, f.mundo, f.estado, f.datos), ("ficha:F-1", "trabajo", "tomada", {}),
                         "su mundo, el de su archivo; se abre por su dirección")

    def test_si_no_trae_ninguno_y_dice_por_que_es_una_falla(self):
        c = self.config(MODULO.replace('listar = "lista"\nplural', 'listar = "rota"\nplural'))
        r = servicio.buscar(SimpleNamespace(config=c), "vitrina", fuentes=("objeto:doc",))
        self.assertIn("el lector falló", self.fuente(r, "objeto:doc").falla)

    def test_se_lee_con_la_vigencia_de_un_bloque_y_preparar_la_empieza(self):
        lecturas = []
        real = servicio._objetos

        def contar(ctx, tipo):
            lecturas.append(tipo)
            return real(ctx, tipo)

        with mock.patch.object(servicio, "_objetos", side_effect=contar), mock.patch.object(servicio, "VIGENCIA", 0):
            self.assertIn("objeto:doc", servicio.preparar(self.ctx))
            servicio.buscar(self.ctx, "vitrina", fuentes=("objeto:doc",), tope=10)
            servicio.buscar(self.ctx, "vidrio", fuentes=("objeto:doc",), tope=10)
        self.assertEqual(lecturas.count("doc"), 1, "corre una consulta del módulo: vale lo que un bloque, no se relee al tiro")

    def test_la_que_tarda_sale_tarde_y_la_siguiente_la_trae(self):
        soltar = threading.Event()
        self.addCleanup(soltar.set)
        real = servicio._objetos

        def lenta(ctx, tipo):
            soltar.wait(10)
            return real(ctx, tipo)

        with mock.patch.object(servicio, "_objetos", side_effect=lenta):
            inicio = time.monotonic()
            r = servicio.buscar(self.ctx, "vitrina", fuentes=("objeto:doc", "tareas"), tope=0.3)
            self.assertLess(time.monotonic() - inicio, 2, "no espera al grafo grande más que el tope")
            docs = self.fuente(r, "objeto:doc")
            self.assertEqual((docs.tarde, docs.total), (True, 0))
            soltar.set()
            while servicio.leyendo():
                time.sleep(0.02)
            self.assertEqual(self.fuente(servicio.buscar(self.ctx, "vitrina", fuentes=("objeto:doc",)), "objeto:doc").total, 3)


class ElTope(Prueba):
    """Una fuente lenta no atrasa a las demás: la búsqueda no espera más que el tope, la lenta lo dice y sigue leyéndose
    aparte, y la búsqueda siguiente la trae. Lo leído se guarda: buscar seguido no relee ni apila lecturas."""

    def setUp(self):
        super().setUp()
        servicio.olvidar()
        self.addCleanup(servicio.olvidar)
        self.ctx = SimpleNamespace(config=config(MUNDOS))
        self.soltar = threading.Event()
        self.addCleanup(self.soltar.set)  # que ninguna lectura quede colgada después de la prueba
        self.lecturas = 0

        def lenta(_ctx):
            self.lecturas += 1
            self.soltar.wait(10)
            return [(H(fuente="hilos", direccion="hilo:Vitrina", titulo="Vitrina"), "")]

        self.parches = [mock.patch.object(servicio, "_esperas", return_value=[]),
                        mock.patch.object(servicio, "_tareas", return_value=[
                            (H(fuente="tareas", direccion="tarea:T1", titulo="Armar la vitrina"), "")]),
                        mock.patch.object(servicio, "_casillas", return_value=[]),
                        mock.patch.object(servicio, "_hilos", side_effect=lenta),
                        mock.patch.object(servicio, "_proyectos", return_value=[])]
        for p in self.parches:
            p.start()
            self.addCleanup(p.stop)

    def fuente(self, r, clave):
        return next(f for f in r.fuentes if f.clave == clave)

    def buscar(self, **kw):
        inicio = time.monotonic()
        r = servicio.buscar(self.ctx, "vitrina", **kw)
        return r, time.monotonic() - inicio

    def test_una_fuente_lenta_no_atrasa_a_las_demas(self):
        r, tardo = self.buscar(tope=0.3)
        self.assertLess(tardo, 2, "no se espera a la lenta más que el tope")
        hilos = self.fuente(r, "hilos")
        self.assertTrue(hilos.tarde)
        self.assertEqual((hilos.total, hilos.leida), (0, ""))
        self.assertIn("tardó más de 0,3 s", hilos.falla)
        tareas = self.fuente(r, "tareas")
        self.assertEqual((tareas.total, tareas.tarde, tareas.falla), (1, False, ""))
        self.assertTrue(tareas.leida, "dice cuándo se leyó")
        # sigue leyéndose aparte: la búsqueda siguiente la trae, sin leerla de nuevo
        self.soltar.set()
        r, _ = self.buscar(tope=5)
        hilos = self.fuente(r, "hilos")
        self.assertEqual((hilos.total, hilos.tarde, hilos.falla), (1, False, ""))
        self.assertEqual(self.lecturas, 1)

    def test_buscar_seguido_no_apila_lecturas(self):
        for _ in range(3):
            r, _ = self.buscar(tope=0.05)
            self.assertTrue(self.fuente(r, "hilos").tarde)
        self.assertEqual(self.lecturas, 1, "una lectura por fuente a la vez")
        self.soltar.set()
        self.buscar(tope=5)
        self.buscar(tope=5)
        self.assertEqual(self.lecturas, 1, "dentro de su vigencia no se relee")

    def test_la_lectura_que_ya_se_paso_del_tope_no_atrasa_a_la_siguiente(self):
        self.buscar(tope=0.2)  # la lenta empieza, y se pasa
        r, tardo = self.buscar(tope=0.2)
        self.assertLess(tardo, 0.15, "su tope corre desde que empezó, no de nuevo con cada búsqueda")
        self.assertTrue(self.fuente(r, "hilos").tarde)
        self.assertEqual(self.lecturas, 1)

    def test_la_lenta_con_algo_guardado_sale_al_tiro_con_lo_de_antes(self):
        self.soltar.set()
        with mock.patch.object(servicio, "_hilos", side_effect=lambda c: time.sleep(0.3) or [
                (H(fuente="hilos", direccion="hilo:Vitrina", titulo="Vitrina"), "")]):
            self.buscar(tope=5)
        # vencida, se relee; la lectura nueva no termina, y como la última tardó más que el tope, no se la espera
        self.soltar.clear()
        with mock.patch.object(servicio, "VIGENCIA", 0):
            r, tardo = self.buscar(tope=0.2)
        self.assertLess(tardo, 0.15, "lo de antes, al tiro")
        hilos = self.fuente(r, "hilos")
        self.assertEqual((hilos.total, hilos.tarde, hilos.falla), (1, True, ""))
        self.assertTrue(hilos.leida)
        self.assertEqual(self.lecturas, 1, "la relectura empezó")

    def test_si_la_relectura_falla_sale_lo_de_antes_con_su_falla(self):
        self.soltar.set()
        self.buscar(tope=5)
        with mock.patch.object(servicio, "VIGENCIA", 0), \
                mock.patch.object(servicio, "_hilos", side_effect=RuntimeError("tmux no responde")):
            r, _ = self.buscar(tope=5)
        hilos = self.fuente(r, "hilos")
        self.assertEqual((hilos.total, hilos.tarde), (1, False))
        self.assertIn("tmux no responde", hilos.falla)
        self.assertTrue(hilos.leida)

    def test_preparar_empieza_a_leer_sin_esperar(self):
        inicio = time.monotonic()
        leyendo = servicio.preparar(self.ctx)
        self.assertLess(time.monotonic() - inicio, 0.5)
        self.assertIn("hilos", leyendo)
        self.assertEqual(self.lecturas, 1)
        self.soltar.set()
        r, _ = self.buscar(tope=5)
        self.assertEqual(self.fuente(r, "hilos").total, 1)
        self.assertEqual(self.lecturas, 1, "la búsqueda usa lo que empezó preparar")
        self.assertEqual(servicio.preparar(self.ctx), [], "dentro de la vigencia, nada que leer")

    def test_releer(self):
        self.soltar.set()
        self.buscar(tope=5)
        self.buscar(tope=5, releer=True)
        self.assertEqual(self.lecturas, 2)


class LaOrden(Prueba):
    def test_telar_buscar(self):
        from telar.ordenes import buscar as orden

        ctx = SimpleNamespace(config=config(MUNDOS))
        r = servicio.Busqueda(q="vitrina", mundos=["trabajo"], fuentes=[
            servicio.Fuente(clave="tareas", nombre="tareas", total=3,
                            hallados=[H(fuente="tareas", direccion="tarea:T1", titulo="Armar la vitrina", donde="vitrina", mundo="trabajo")]),
            servicio.Fuente(clave="hilos", nombre="hilos", falla="tmux no responde")])
        with mock.patch.object(servicio, "buscar", return_value=r) as pedir, redirect_stdout(io.StringIO()) as s:
            self.assertEqual(orden.main(["vitrina", "vieja", "--fuente", "tareas", "--mundo", "trabajo", "--limite", "1"], ctx), 0)
        self.assertEqual(pedir.call_args.args[1], "vitrina vieja")
        self.assertEqual(pedir.call_args.kwargs, {"fuentes": ("tareas",), "mundos": ("trabajo",), "limite": 1, "tope": orden.TOPE_AQUI})
        with mock.patch.object(servicio, "buscar", return_value=r) as pedir, redirect_stdout(io.StringIO()):
            orden.main(["vitrina", "--primero", "personal"], ctx)
        self.assertEqual(pedir.call_args.kwargs["primero"], "personal")
        texto = s.getvalue()
        self.assertIn("tarea:T1", texto)
        self.assertIn("[trabajo]", texto)
        self.assertIn("y 2 más", texto)
        self.assertIn("hilos: no se pudo leer: tmux no responde", texto)
        with mock.patch.object(servicio, "buscar", return_value=r), redirect_stdout(io.StringIO()) as s:
            orden.main(["vitrina", "--json"], ctx)
        self.assertEqual(json.loads(s.getvalue())["fuentes"][0]["hallados"][0]["direccion"], "tarea:T1")


class AlServe(Prueba):
    """`telar buscar` le pregunta al `telar serve` de esta máquina, por su socket, que tiene lo leído guardado; si no está
    o no contesta, busca en la orden misma."""

    def servir(self, estado: int, cuerpo: dict):
        import http.server
        import socketserver
        import tempfile
        from pathlib import Path

        carpeta = tempfile.mkdtemp(prefix="tb")
        ruta = Path(carpeta) / "s.sock"
        pedidos = []

        class Atiende(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                pedidos.append(self.path)
                datos = json.dumps(cuerpo).encode()
                self.send_response(estado)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

            def log_message(self, *a):
                pass

        class Servidor(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True

            def get_request(self):
                pedido, _ = super().get_request()
                return pedido, ("local", 0)

        s = Servidor(str(ruta), Atiende)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.server_close)
        self.addCleanup(s.shutdown)
        return ruta, pedidos

    def test_lo_que_contesta_el_serve(self):
        from telar.ordenes import buscar as orden

        r = servicio.Busqueda(q="vitrina", fuentes=[servicio.Fuente(clave="tareas", nombre="tareas", total=1, leida="2026-11-17T10:00:00",
                                                                    hallados=[H(fuente="tareas", direccion="tarea:T1", titulo="Armar la vitrina")])])
        ruta, pedidos = self.servir(200, r.model_dump(mode="json"))
        dicho = orden.del_serve("vitrina vieja", fuentes=("tareas",), mundos=("trabajo",), limite=3, tope=2, socket=ruta)
        self.assertEqual(dicho, r)
        orden.del_serve("vitrina", tope=2, socket=ruta, primero="personal")
        self.assertEqual(pedidos, ["/buscar?q=vitrina+vieja&fuente=tareas&mundo=trabajo&limite=3&tope=2",
                                   "/buscar?q=vitrina&limite=50&tope=2&primero=personal"])

    def test_lo_que_el_serve_dice_que_no_se_dice_igual(self):
        from telar.ordenes import buscar as orden

        ruta, _ = self.servir(422, {"detail": "¿qué busco? (dos letras o más)"})
        with self.assertRaises(ErrorDeServicio) as e:
            orden.del_serve("x", socket=ruta)
        self.assertEqual(e.exception.codigo, 422)
        ruta, _ = self.servir(500, {"detail": "se cayó"})
        self.assertIsNone(orden.del_serve("vitrina", socket=ruta), "lo demás: se busca aquí")

    def test_sin_serve_se_busca_aqui(self):
        from pathlib import Path

        from telar.ordenes import buscar as orden

        self.assertIsNone(orden.del_serve("vitrina", socket=Path("/no/existe.sock")))
        ctx = SimpleNamespace(config=config(MUNDOS))
        r = servicio.Busqueda(q="vitrina")
        with mock.patch.object(orden, "_el_serve_es_de_aqui", return_value=True), \
                mock.patch.object(orden, "del_serve", return_value=None) as al_serve, \
                mock.patch.object(servicio, "buscar", return_value=r) as aqui, redirect_stdout(io.StringIO()):
            orden.main(["vitrina", "--tope", "4"], ctx)
            orden.main(["vitrina"], ctx)
        self.assertEqual([c.kwargs["tope"] for c in al_serve.call_args_list], [4, servicio.TOPE])
        self.assertEqual([c.kwargs["tope"] for c in aqui.call_args_list], [4, orden.TOPE_AQUI],
                         "sin serve, todo se lee de cero: espera más")
        with mock.patch.object(orden, "_el_serve_es_de_aqui", return_value=True), \
                mock.patch.object(orden, "del_serve", return_value=r) as al_serve, \
                mock.patch.object(servicio, "buscar") as aqui, redirect_stdout(io.StringIO()):
            orden.main(["vitrina"], ctx)
            orden.main(["vitrina", "--aqui"], ctx)
        self.assertEqual((al_serve.call_count, aqui.call_count), (1, 1), "--aqui no le pregunta")

    def test_lo_que_sigue_leyendose_no_atrasa_la_salida(self):
        from telar import cli, salida

        r = servicio.Busqueda(q="vitrina")
        self.addCleanup(setattr, salida, "SIN_ESPERAR", False)
        with mock.patch.object(servicio, "buscar", return_value=r), mock.patch.object(servicio, "leyendo", return_value=True), \
                mock.patch.object(cli.os, "_exit") as salir, redirect_stdout(io.StringIO()):
            cli.main(["buscar", "vitrina", "--aqui"])
        salir.assert_called_once_with(0)
        salida.SIN_ESPERAR = False
        with mock.patch.object(servicio, "buscar", return_value=r), mock.patch.object(servicio, "leyendo", return_value=False), \
                mock.patch.object(cli.os, "_exit") as salir, redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["buscar", "vitrina", "--aqui"]), 0)
        salir.assert_not_called()

    def test_otra_configuracion_no_es_la_del_serve(self):
        from telar.ordenes import buscar as orden

        self.assertFalse(orden._el_serve_es_de_aqui(SimpleNamespace(config=config(MUNDOS))), "sin archivo de origen")


@unittest.skipUnless(HAY_FASTAPI, "sin el extra «serve»")
class LaApi(Prueba):
    def test_get_buscar(self):
        from fastapi.testclient import TestClient

        from telar import api

        r = servicio.Busqueda(q="vitrina", fuentes=[servicio.Fuente(clave="tareas", nombre="tareas")])
        with mock.patch.object(servicio, "buscar", return_value=r) as pedir, mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            respuesta = TestClient(api.app).get("/buscar?q=vitrina&fuente=tareas&fuente=bloque:correo&mundo=trabajo&limite=5"
                                                "&primero=personal&si_hay=true")
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        self.assertEqual(pedir.call_args.kwargs, {"fuentes": ("tareas", "bloque:correo"), "mundos": ("trabajo",), "limite": 5,
                                                  "tope": servicio.TOPE, "releer": False, "primero": "personal",
                                                  "si_hay": True})
        self.assertEqual(respuesta.json()["q"], "vitrina")

    def test_post_buscar_preparar(self):
        from fastapi.testclient import TestClient

        from telar import api

        with mock.patch.object(servicio, "preparar", return_value=["hilos"]), mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            respuesta = TestClient(api.app).post("/buscar/preparar")
        self.assertEqual((respuesta.status_code, respuesta.json()), (200, {"leyendo": ["hilos"]}))


if __name__ == "__main__":
    unittest.main()
