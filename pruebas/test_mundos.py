"""Los mundos (`[mundos]`, telar.mundos): cómo se declaran, cómo se deriva el de cada cosa (de lo declarado, nunca del
título) y cómo los dicen y los filtran `telar esperas`, `telar tipo tarea lista` y `telar pendientes`."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import mundos, objetos
from telar.servicios import ErrorDeServicio

RAIZ = Path("/casa")


def config(texto: str = "") -> cfg.Config:
    """Una configuración leída de un TOML, con la raíz en /casa."""
    import tomllib

    return cfg.desde_dict({"raiz": str(RAIZ), **tomllib.loads(texto)})


DOS = """
[mundos.trabajo]
areas = ["equipo", "cliente"]
rutas = ["empresa/", "clientes/acme-", "~/worktrees/empresa-"]

[mundos.personal]
areas = ["personal"]
rutas = ["casa/", "empresa/lo-mio/"]
"""


class LaDeclaracion(Prueba):
    def test_en_su_orden_con_sus_areas_y_rutas(self):
        c = config(DOS)
        self.assertEqual([m.nombre for m in c.mundos], ["trabajo", "personal"])
        self.assertEqual(c.mundos[0].areas, ("equipo", "cliente"))
        self.assertEqual(c.mundos[1].rutas, ("casa/", "empresa/lo-mio/"))
        self.assertEqual(mundos.declarados(c), ("trabajo", "personal"))

    def test_sin_mundos_no_hay_ninguno(self):
        self.assertEqual(config().mundos, ())
        self.assertEqual(mundos.declarados(config()), ())
        # una configuración vieja (o de prueba) sin el atributo, tampoco
        self.assertEqual(mundos.declarados(SimpleNamespace()), ())

    def test_lo_que_no_se_entiende_es_un_error(self):
        malos = {
            '[mundos.trabajo]\nlugares = ["x"]': "no existe",
            '[mundos.trabajo]\nareas = "equipo"': "lista de textos",
            '[mundos.trabajo]\nareas = ["equipo"]\n[mundos.personal]\nareas = ["equipo"]': "ya es de «trabajo»",
            '[mundos.trabajo]\nrutas = ["empresa/"]\n[mundos.personal]\nrutas = ["empresa"]': "ya es de «trabajo»",
            '[mundos.trabajo]\nrutas = ["../afuera/"]': "no puede subir",
            '[mundos.sin-clasificar]\nareas = ["x"]': "sin-clasificar",
            '[mundos."mi trabajo"]\nareas = ["x"]': "una palabra",
            'mundos = "trabajo"': "",
        }
        for texto, dice in malos.items():
            with self.subTest(texto=texto), self.assertRaises(cfg.ErrorDeConfig) as e:
                config(texto)
            self.assertIn(dice, str(e.exception))

    def test_la_configuracion_resuelta_los_dice(self):
        from telar.servicios import config as servicio

        r = servicio.resuelta(SimpleNamespace(config=config(DOS)))
        self.assertEqual(r.mundos[0], {"nombre": "trabajo", "areas": ["equipo", "cliente"],
                                       "rutas": ["empresa/", "clientes/acme-", "~/worktrees/empresa-"],
                                       "etiquetas": [], "color": "cian", "horario": [], "tema": "", "modos": [],
                                       "arte": ""})
        self.assertEqual(r.mundos_fuera, "")


CON_HORARIO = """
[mundos]
fuera = "personal"

[mundos.trabajo]
rutas = ["empresa/"]
etiquetas = ["trabajo", "oficina"]
horario = ["lun-vie 9:00-13:00", "lun-vie 14:00-19:00"]

[mundos.personal]
rutas = ["casa/"]
color = "cian"
horario = "sáb-dom"
tema = "brasa"
modos = ["todo", "foco"]
"""


class ElHorarioYLoDemas(Prueba):
    """`horario`, `fuera`, `color`, `tema` y `etiquetas`: lo que la página necesita para ponerse sola en un mundo, con
    sus colores."""

    def test_se_leen(self):
        c = config(CON_HORARIO)
        trabajo, personal = c.mundos
        self.assertEqual(c.mundos_fuera, "personal")
        self.assertEqual(trabajo.etiquetas, ("trabajo", "oficina"))
        self.assertEqual([(t.dias, t.desde, t.hasta) for t in trabajo.horario], [((1, 2, 3, 4, 5), 540, 780), ((1, 2, 3, 4, 5), 840, 1140)])
        self.assertEqual([(t.dias, t.desde, t.hasta) for t in personal.horario], [((0, 6), 0, 1440)])
        self.assertEqual(personal.color, "cian")
        self.assertEqual((trabajo.tema, personal.tema), ("", "brasa"), "sin tema: el del modo")

    def test_los_tramos(self):
        from telar.horario import leer_tramo

        def tramo(texto):
            t = leer_tramo(texto)
            return (t.dias, t.desde, t.hasta)
        self.assertEqual(tramo("lun,miércoles,vie 8:30-12"), ((1, 3, 5), 510, 720))
        self.assertEqual(tramo("20:00-23:00"), ((0, 1, 2, 3, 4, 5, 6), 1200, 1380))
        self.assertEqual(tramo("todos"), ((0, 1, 2, 3, 4, 5, 6), 0, 1440))
        self.assertEqual(tramo("vie-lun 22-2"), ((0, 1, 5, 6), 1320, 120))  # da la vuelta a la semana y a la medianoche
        self.assertEqual(tramo("Sábado"), ((6,), 0, 1440))
        for malo in ("", "lunes a viernes", "lun 25:00-26:00", "lun 9-9", "xyz 9-10", "lu 9-10", "9:00", "lun- 9-10"):
            with self.subTest(malo=malo), self.assertRaises(ValueError):
                leer_tramo(malo)

    def test_el_color_por_orden_salta_los_que_ya_se_eligieron(self):
        c = config(CON_HORARIO)
        self.assertEqual(mundos.colores(c), {"trabajo": "magenta", "personal": "cian"})
        self.assertEqual(mundos.colores(config(DOS)), {"trabajo": "cian", "personal": "magenta"})

    def test_lo_que_no_se_entiende_es_un_error(self):
        malos = {
            '[mundos.trabajo]\nhorario = "lunes a viernes"': "mundos.trabajo.horario",
            '[mundos.trabajo]\nhorario = 9': "un texto o una lista",
            '[mundos.trabajo]\ncolor = "naranjo"': "mundos.trabajo.color",
            '[mundos.trabajo]\ntema = "noche"': "mundos.trabajo.tema: uno de telar, latte",
            '[mundos.trabajo]\ntema = 3': "mundos.trabajo.tema",
            '[mundos.trabajo]\netiquetas = "x"': "lista de textos",
            '[mundos.trabajo]\netiquetas = ["x"]\n[mundos.personal]\netiquetas = ["x"]': "ya es de «trabajo»",
            '[mundos]\nfuera = "casa"\n[mundos.trabajo]\nareas = ["x"]': "mundos.fuera",
            '[mundos]\nfuera = 3\n[mundos.trabajo]\nareas = ["x"]': "mundos.fuera",
            '[mundos]\ndesde = "x"': "mundos.desde: no existe",
        }
        for texto, dice in malos.items():
            with self.subTest(texto=texto), self.assertRaises(cfg.ErrorDeConfig) as e:
                config(texto)
            self.assertIn(dice, str(e.exception))

    def test_la_configuracion_resuelta_los_dice(self):
        from telar.servicios import config as servicio

        r = servicio.resuelta(SimpleNamespace(config=config(CON_HORARIO)))
        self.assertEqual(r.mundos_fuera, "personal")
        self.assertEqual(r.mundos[0]["etiquetas"], ["trabajo", "oficina"])
        self.assertEqual(r.mundos[0]["color"], "magenta")
        self.assertEqual(r.mundos[0]["horario"][0], {"texto": "lun-vie 9:00-13:00", "dias": [1, 2, 3, 4, 5], "desde": 540, "hasta": 780})
        self.assertEqual(r.mundos[1]["horario"], [{"texto": "sáb-dom", "dias": [0, 6], "desde": 0, "hasta": 1440}])
        self.assertEqual([m["tema"] for m in r.mundos], ["", "brasa"])
        self.assertEqual([m["modos"] for m in r.mundos], [[], ["todo", "foco"]], "sin declarar, todos: []")


class DeLoDeclarado(Prueba):
    def setUp(self):
        super().setUp()
        self.c = config(DOS)

    def test_un_area(self):
        self.assertEqual(mundos.de_area(self.c, "cliente"), "trabajo")
        self.assertEqual(mundos.de_area(self.c, "personal"), "personal")
        self.assertEqual(mundos.de_area(self.c, "otra"), "")
        self.assertEqual(mundos.de_area(self.c, ""), "")

    def test_una_carpeta_con_barra_es_ella_y_lo_que_tiene_dentro(self):
        self.assertEqual(mundos.de_ruta(self.c, "empresa"), "trabajo")
        self.assertEqual(mundos.de_ruta(self.c, "empresa/proyectos/faro"), "trabajo")
        self.assertEqual(mundos.de_ruta(self.c, "empresa/proyectos/faro/README.md"), "trabajo")
        self.assertEqual(mundos.de_ruta(self.c, "empresas/otra"), "")  # empieza igual, pero es otra carpeta

    def test_sin_barra_calza_lo_que_empieza_igual(self):
        self.assertEqual(mundos.de_ruta(self.c, "clientes/acme-faro"), "trabajo")
        self.assertEqual(mundos.de_ruta(self.c, "clientes/otra"), "")

    def test_gana_la_mas_larga_de_cualquier_mundo(self):
        self.assertEqual(mundos.de_ruta(self.c, "empresa/lo-mio/notas"), "personal")
        self.assertEqual(mundos.de_ruta(self.c, "empresa/lo-tuyo"), "trabajo")

    def test_absolutas_y_desde_la_raiz(self):
        self.assertEqual(mundos.de_ruta(self.c, "/casa/casa/jardin"), "personal")
        self.assertEqual(mundos.de_ruta(self.c, "/casa/empresa/../casa/jardin"), "personal")
        self.assertEqual(mundos.de_ruta(self.c, str(Path("~/worktrees/empresa-faro").expanduser())), "trabajo")
        self.assertEqual(mundos.de_ruta(self.c, "../worktrees/x"), "")

    def test_la_raiz_misma_no_es_de_nadie_salvo_que_se_declare(self):
        self.assertEqual(mundos.de_ruta(self.c, "."), "")
        self.assertEqual(mundos.de_ruta(self.c, ""), "")
        todo = config('[mundos.personal]\nrutas = ["./"]\n[mundos.trabajo]\nrutas = ["empresa/"]')
        self.assertEqual(mundos.de_ruta(todo, "."), "personal")
        self.assertEqual(mundos.de_ruta(todo, "notas/x"), "personal")
        self.assertEqual(mundos.de_ruta(todo, "empresa/x"), "trabajo")

    def test_una_tarea_por_su_area_y_si_no_por_su_proyecto(self):
        self.assertEqual(mundos.de_tarea(self.c, "personal", "empresa/faro"), "personal")  # el área manda
        self.assertEqual(mundos.de_tarea(self.c, "otra", "empresa/faro"), "trabajo")
        self.assertEqual(mundos.de_tarea(self.c, "otra", ""), "")
        self.assertEqual(mundos.de_tarea(config(), "personal", "empresa/faro"), "")  # sin [mundos], nada

    def test_una_fila_de_un_proveedor_o_de_un_documento(self):
        # la ruta de una tarea es la del hilo al que se la llevaría (sale de su título): no cuenta
        tarea = {"proveedor": "tareas", "area": "otra", "proyecto": "", "ruta": "empresa/faro"}
        self.assertEqual(mundos.de_fila(self.c, tarea), "")
        self.assertEqual(mundos.de_fila(self.c, {**tarea, "area": "cliente"}), "trabajo")
        self.assertEqual(mundos.de_fila(self.c, {**tarea, "proyecto": "casa/jardin"}), "personal")
        casilla = {"proveedor": "", "ruta": "casa/jardin", "area": ""}
        self.assertEqual(mundos.de_fila(self.c, casilla), "personal")

    def test_el_filtro(self):
        self.assertEqual(mundos.pedidos(self.c, ()), set())
        self.assertEqual(mundos.pedidos(self.c, ("trabajo", "sin-clasificar")), {"trabajo", ""})
        with self.assertRaises(ErrorDeServicio) as e:
            mundos.pedidos(self.c, ("ocio",))
        self.assertEqual(e.exception.codigo, 404)
        self.assertIn("trabajo, personal, sin-clasificar", str(e.exception))
        with self.assertRaises(ErrorDeServicio) as e:
            mundos.pedidos(config(), ("trabajo",))
        self.assertIn("no declara mundos", str(e.exception))
        self.assertTrue(mundos.calza("", set()))
        self.assertTrue(mundos.calza("", {""}))
        self.assertFalse(mundos.calza("personal", {"trabajo"}))


class LosHilos(Prueba):
    """El de un hilo: su carpeta; si no calza, la de su agente residente; si tampoco, el hilo del que cuelga."""

    def setUp(self):
        super().setUp()
        self.c = config(DOS.replace('"empresa/lo-mio/"]', '"empresa/lo-mio/", "agentes/dinero/"]')
                        + '\n[agentes]\ncarpeta = "agentes"\n')
        self.k = mundos.Clasificador(SimpleNamespace(config=self.c))
        self.k._hilos = {
            ("Faro", ""): {"nombre": "Faro", "relativa": "empresa/faro"},
            ("Rama", ""): {"nombre": "Rama", "relativa": "../worktrees/faro-rama", "padre": "Faro"},
            ("Nieta", ""): {"nombre": "Nieta", "relativa": "", "padre": "Rama"},
            ("Dinero", "servidor"): {"nombre": "Dinero", "relativa": ".", "agente": "dinero"},
            ("Suelto", ""): {"nombre": "Suelto", "relativa": ".", "padre": "Otro"},
            ("A", ""): {"nombre": "A", "relativa": "", "padre": "B"},
            ("B", ""): {"nombre": "B", "relativa": "", "padre": "A"},
            ("Jardin", "servidor"): {"nombre": "Jardin", "relativa": "casa/jardin"},
        }

    def test_por_su_carpeta(self):
        self.assertEqual(self.k.de_hilo("Faro"), "trabajo")
        self.assertEqual(self.k.de_hilo("Jardin"), "personal")  # de otra máquina: su relativa, leída desde aquí
        self.assertEqual(self.k.de_hilo("Jardin", "servidor"), "personal")

    def test_un_worktree_fuera_de_la_raiz_por_el_hilo_del_que_cuelga(self):
        self.assertEqual(self.k.de_hilo("Rama"), "trabajo")
        self.assertEqual(self.k.de_hilo("Nieta"), "trabajo")

    def test_un_agente_sin_proyecto_por_su_carpeta(self):
        self.assertEqual(self.k.de_hilo("Dinero", "servidor"), "personal")

    def test_lo_que_no_calza_queda_sin_clasificar_aunque_se_cuelguen_en_circulo(self):
        self.assertEqual(self.k.de_hilo("Suelto"), "")
        self.assertEqual(self.k.de_hilo("A"), "")
        self.assertEqual(self.k.de_hilo("Nadie"), "")

    def test_por_una_direccion(self):
        self.assertEqual(self.k.de_direccion("hilo:Faro"), "trabajo")
        self.assertEqual(self.k.de_direccion("permiso:Dinero@servidor"), "personal")
        self.assertEqual(self.k.de_direccion("proyecto:casa/jardin"), "personal")
        self.assertEqual(self.k.de_direccion("archivo:laptop:empresa/faro/README.md"), "trabajo")
        self.assertEqual(self.k.de_direccion("tarea:T84"), "")
        self.assertEqual(self.k.de_direccion("no es una dirección"), "")

    def test_sus_etiquetas_le_ganan_a_su_carpeta(self):
        c = config(CON_HORARIO)
        k = mundos.Clasificador(SimpleNamespace(config=c), hilos={
            ("Faro", ""): {"nombre": "Faro", "relativa": "casa/faro", "etiquetas": ["oficina"]},
            ("Hijo", ""): {"nombre": "Hijo", "relativa": "../worktrees/x", "padre": "Faro"},
            ("Huerto", ""): {"nombre": "Huerto", "relativa": "casa/huerto", "etiquetas": ["verde"]},
        })
        self.assertEqual(k.de_hilo("Faro"), "trabajo", "la etiqueta es de trabajo, aunque viva en casa/")
        self.assertEqual(k.de_hilo("Hijo"), "trabajo", "un hijo sin carpeta propia, el de su padre")
        self.assertEqual(k.de_hilo("Huerto"), "personal", "una etiqueta que no es de nadie no cuenta")
        self.assertEqual(mundos.de_etiquetas(c, ["oficina", "otra"]), "trabajo")
        self.assertEqual(mundos.de_etiquetas(c, []), "")

    def test_sin_mundos_ni_se_leen_los_hilos(self):
        k = mundos.Clasificador(SimpleNamespace(config=config()))
        with mock.patch.object(k, "preparar") as preparar:
            self.assertEqual(k.de_hilo("Faro"), "")
        preparar.assert_not_called()


class ElQueDeclaraSuAgente(Prueba):
    """`mundo = "personal"` en el agente.toml de un agente: le gana a la ruta de su carpeta y a las etiquetas de su hilo,
    para él, su hilo y los hilos que cuelgan de él. Uno que esta máquina no declara no cuenta: va por lo de siempre."""

    def setUp(self):
        super().setUp()
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        # todo agentes/ es del trabajo, y la etiqueta «oficina» también: lo que declara el agente le gana a las dos
        texto = CON_HORARIO.replace('rutas = ["empresa/"]', 'rutas = ["empresa/", "agentes/"]') + '\n[agentes]\ncarpeta = "agentes"\n'
        for clave, toml in (("cocina", 'mundo = "personal"\nresidente = "a-pedido"\n'), ("faro", ""),
                            ("lejos", 'mundo = "marte"\n')):
            d = self.raiz / "agentes" / clave
            d.mkdir(parents=True)
            (d / "CLAUDE.md").write_text(f"# {clave}\n")
            if toml:
                (d / "agente.toml").write_text(toml)
        import tomllib

        self.c = cfg.desde_dict({"raiz": str(self.raiz), **tomllib.loads(texto)})

    def test_su_mundo_le_gana_a_su_carpeta(self):
        self.assertEqual(mundos.declarado_de_agente(self.c, "cocina"), "personal")
        self.assertEqual(mundos.de_agente(self.c, "cocina"), "personal")
        self.assertEqual(mundos.de_agente(self.c, "faro"), "trabajo", "sin declararlo, por su carpeta")
        self.assertEqual(mundos.declarado_de_agente(self.c, "lejos"), "", "un mundo que aquí no existe no cuenta")
        self.assertEqual(mundos.de_agente(self.c, "lejos"), "trabajo")
        self.assertEqual(mundos.declarado_de_agente(self.c, "../cocina"), "", "una clave que sale de la carpeta, no")
        self.assertEqual(mundos.declarado_de_agente(config(CON_HORARIO), "cocina"), "", "sin [agentes] carpeta, ninguno")

    def test_todo_lo_de_su_carpeta_es_de_su_mundo(self):
        self.assertEqual(mundos.de_ruta(self.c, "agentes/cocina/registro/2026-11-22.md"), "personal")
        self.assertEqual(mundos.ruta_que_calza(self.c, "agentes/cocina"), ("personal", "agentes/cocina/ (agente.toml)"))
        self.assertEqual(mundos.de_ruta(self.c, str(self.raiz / "agentes" / "cocina" / "memoria")), "personal", "absoluta, igual")
        self.assertEqual(mundos.de_ruta(self.c, "agentes/cocinas/x.md"), "trabajo", "otra carpeta que empieza igual, no")
        self.assertEqual(mundos.de_ruta(self.c, "agentes/faro/x.md"), "trabajo")
        # cambia lo que declara: se lee de nuevo (por su fecha), sin reiniciar nada
        archivo = self.raiz / "agentes" / "cocina" / "agente.toml"
        archivo.write_text('mundo = "trabajo"\n')
        import os
        os.utime(archivo, (archivo.stat().st_atime, archivo.stat().st_mtime + 5))
        self.assertEqual(mundos.de_ruta(self.c, "agentes/cocina/registro/x.md"), "trabajo")
        archivo.unlink()
        self.assertEqual(mundos.declarado_de_agente(self.c, "cocina"), "", "sin su agente.toml, ninguno")

    def test_y_a_la_etiqueta_de_su_hilo_y_lo_dice(self):
        self.assertEqual(mundos.por_que_agente(self.c, "cocina", ["oficina"]),
                         {"mundo": "personal", "por": "agente.toml", "valor": 'mundo = "personal"'})
        self.assertEqual(mundos.por_que_agente(self.c, "faro", ["oficina"])["por"], "etiqueta")
        ver = mundos.para_la_configuracion(self.c, etiquetas={})
        self.assertEqual({a["clave"]: (a["mundo"], a["por"]) for a in ver["agentes"]},
                         {"cocina": ("personal", "agente.toml"), "faro": ("trabajo", "ruta"), "lejos": ("trabajo", "ruta")})

    def test_su_hilo_y_los_que_cuelgan_de_el(self):
        k = mundos.Clasificador(SimpleNamespace(config=self.c), hilos={
            ("Cocina", ""): {"nombre": "Cocina", "relativa": "agentes/cocina", "agente": "cocina", "etiquetas": ["oficina"]},
            ("Cocina › T1", ""): {"nombre": "Cocina › T1", "relativa": "", "padre": "Cocina"},
            ("Faro", ""): {"nombre": "Faro", "relativa": "agentes/faro", "agente": "faro"},
        })
        self.assertEqual(k.de_hilo("Cocina"), "personal", "ni su etiqueta ni su carpeta de trabajo lo sacan")
        self.assertEqual(k.de_hilo("Cocina › T1"), "personal", "su hijo, por él")
        self.assertEqual(k.de_hilo("Faro"), "trabajo")

    def test_lo_suyo_dice_de_que_agente_es(self):
        """La página no nombra lo de un agente de otro mundo que el puesto, ni en el modo todo (el 23-nov, ⌘K, la vista
        de agentes y la instrucción nombraban a un agente del mundo personal en el trabajo): para eso, cada cosa dice de qué agente es."""
        self.assertEqual(mundos.agente_de_ruta(self.c, "agentes/cocina/registro/2026-11-22.md"), "cocina")
        self.assertEqual(mundos.agente_de_ruta(self.c, str(self.raiz / "agentes" / "cocina")), "cocina", "su carpeta misma, absoluta")
        self.assertEqual(mundos.agente_de_ruta(self.c, "agentes/faro/x.md"), "", "uno que no declara su mundo: su carpeta va por la ruta")
        self.assertEqual(mundos.agente_de_ruta(self.c, "agentes/cocinas/x.md"), "")
        self.assertEqual(mundos.agente_de_ruta(self.c, ""), "")
        self.assertEqual(mundos.agente_de_ruta(config(CON_HORARIO), "agentes/cocina/x.md"), "", "sin [agentes] carpeta, ninguno")
        k = mundos.Clasificador(SimpleNamespace(config=self.c), hilos={
            ("Cocina", ""): {"nombre": "Cocina", "relativa": "agentes/cocina", "agente": "cocina"},
            ("Cocina › T1", ""): {"nombre": "Cocina › T1", "relativa": "", "padre": "Cocina"},
            ("Nieto", ""): {"nombre": "Nieto", "relativa": "", "padre": "Cocina › T1"},
            ("Faro", ""): {"nombre": "Faro", "relativa": "empresa/faro"},
        })
        self.assertEqual([k.agente_de_hilo(n) for n in ("Cocina", "Cocina › T1", "Nieto", "Faro", "Nadie")],
                         ["cocina", "cocina", "cocina", "", ""], "su hilo y los que cuelgan de él")
        por = {e.direccion: k.agente_de_espera(e) for e in (
            espera("permiso:Cocina › T1", enlaces=["hilo:Cocina › T1"]),
            espera("pregunta:casa/x", clase="decide", enlaces=["agente:cocina", "archivo:agentes/cocina/preguntas/x.md"]),
            espera("tarea:T9", clase="avance:pregunta", enlaces=["proyecto:agentes/cocina/recetas"]),
            espera("mensaje:m1", clase="retenido", enlaces=["hilo:Faro", "hilo:Cocina"]),
            espera("permiso:Faro", enlaces=["hilo:Faro"]))}
        self.assertEqual(por, {"permiso:Cocina › T1": "cocina", "pregunta:casa/x": "cocina", "tarea:T9": "cocina",
                               "mensaje:m1": "cocina", "permiso:Faro": ""})

    def test_la_busqueda_dice_de_que_agente_es(self):
        from telar.servicios import buscar

        ctx = SimpleNamespace(config=self.c)
        hilos = SimpleNamespace(hilos=[
            SimpleNamespace(nombre="Cocina", agente="cocina", padre="", relativa="agentes/cocina", archivado=False, vivo=True,
                            atencion="ninguna", actividad="", direccion="hilo:Cocina", arquetipo="", repo="", mundo="personal"),
            SimpleNamespace(nombre="Cocina › T1", agente="", padre="Cocina", relativa="", archivado=False, vivo=True,
                            atencion="ninguna", actividad="", direccion="", arquetipo="", repo="", mundo="personal"),
            SimpleNamespace(nombre="Faro", agente="", padre="", relativa="empresa/faro", archivado=False, vivo=True,
                            atencion="ninguna", actividad="", direccion="", arquetipo="", repo="", mundo="trabajo")])
        with mock.patch("telar.servicios.hilos.hilos", return_value=hilos):
            r = buscar._hilos(ctx)
        self.assertEqual({h.titulo: h.agente for h, _ in r}, {"Cocina": "cocina", "Cocina › T1": "cocina", "Faro": ""})

    def test_su_seccion_lo_trae_para_la_pagina(self):
        from telar.servicios import config as servicio

        secciones = {s["clave"]: s for s in servicio._agentes(self.c)}
        self.assertEqual((secciones["agente:cocina"]["mundo"], secciones["agente:cocina"]["presencia"]), ("personal", "a-pedido"))
        self.assertEqual(secciones["agente:faro"]["mundo"], "trabajo")
        sin = {s["clave"]: s for s in servicio._agentes(cfg.desde_dict({"raiz": str(self.raiz), "agentes": {"carpeta": "agentes"}}))}
        self.assertNotIn("mundo", sin["agente:cocina"], "sin [mundos], no viene")


def espera(direccion: str, desde: str = "2026-11-17T09:00:00", clase: str = "permiso", enlaces=(), mundo="") -> objetos.Espera:
    return objetos.Espera(direccion=direccion, tipo=direccion.split(":")[0], clase=clase, desde=desde,
                          enlaces=list(enlaces), mundo=mundo)


class LasEsperas(Prueba):
    """`telar esperas` con mundos: cada una dice el suyo, se filtran y la respuesta trae los declarados."""

    def setUp(self):
        super().setUp()
        self.ctx = SimpleNamespace(config=config(DOS))
        self.por_tipo = {
            "permiso": [espera("permiso:Faro", enlaces=["hilo:Faro"])],
            "tarea": [espera("tarea:T1", clase="avance:pregunta", mundo="personal"),
                      espera("tarea:T2", clase="avance:pregunta", mundo="viejo")],
            "mensaje": [espera("mensaje:m1", clase="retenido", enlaces=["hilo:Jardin", "hilo:Faro"]),
                        espera("mensaje:m2", clase="retenido", enlaces=["hilo:Nadie"])],
        }

    def esperas(self, ctx=None, **kw):
        from telar.servicios import esperas as servicio

        ctx = ctx or self.ctx
        parches = [mock.patch.object(type(objetos.tipos(ctx)[n]), "esperando", return_value=list(v))
                   for n, v in self.por_tipo.items()]
        hilos = {("Faro", ""): {"nombre": "Faro", "relativa": "empresa/faro"},
                 ("Jardin", ""): {"nombre": "Jardin", "relativa": "casa/jardin"}}
        parches.append(mock.patch.object(mundos.Clasificador, "preparar",
                                         lambda self: setattr(self, "_hilos", self._hilos if self._hilos is not None else hilos)))
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        return servicio.esperas(ctx, **kw)

    def test_cada_una_dice_su_mundo(self):
        r = self.esperas()
        self.assertEqual(r.mundos, ["trabajo", "personal"])
        por = {e.direccion: e.mundo for e in r.esperas}
        self.assertEqual(por, {"permiso:Faro": "trabajo", "tarea:T1": "personal", "tarea:T2": "",
                               "mensaje:m1": "personal",  # del hilo al que iba, no del que lo mandó
                               "mensaje:m2": ""})

    def test_se_filtran(self):
        self.assertEqual([e.direccion for e in self.esperas(mundos=("trabajo",)).esperas], ["permiso:Faro"])
        self.assertEqual(sorted(e.direccion for e in self.esperas(mundos=("sin-clasificar",)).esperas),
                         ["mensaje:m2", "tarea:T2"])
        with self.assertRaises(ErrorDeServicio):
            self.esperas(mundos=("ocio",))

    def test_sin_mundos_ninguna_dice_mundo(self):
        r = self.esperas(SimpleNamespace(config=config()))
        self.assertEqual(r.mundos, [])
        self.assertEqual({e.mundo for e in r.esperas}, {""})

    def test_la_orden_las_muestra_en_tandas(self):
        from telar.ordenes import esperas as orden

        r = self.esperas()
        tandas = orden.tandas(r.esperas, r.mundos)
        self.assertEqual([(m, len(s)) for m, s in tandas], [("trabajo", 1), ("personal", 2), ("", 2)])
        self.assertEqual([(m, len(s)) for m, s in orden.tandas(r.esperas, [])], [(None, 5)])
        # una tanda vacía no se dice
        self.assertEqual([m for m, _ in orden.tandas([e for e in r.esperas if e.mundo == "personal"], r.mundos)],
                         ["personal"])

    def test_la_tarea_lo_sabe_por_su_area(self):
        from telar.servicios import tipos as st

        ctx = SimpleNamespace(config=SimpleNamespace(mundos=config(DOS).mundos, raiz=RAIZ,
                                                     tipos=(SimpleNamespace(clave="tarea", en="", carpeta="x"),)))
        tareas = [st.TareaConVersion(id="T1", titulo="a", avance="pregunta 2026-11-10", area="cliente", version="v"),
                  st.TareaConVersion(id="T2", titulo="b", avance="pregunta 2026-11-10", area="otra",
                                     proyecto="casa/jardin", version="v")]
        with mock.patch.object(st, "lista", return_value=st.Tareas(tareas=tareas)):
            r = objetos.Tarea().esperando(ctx)
        self.assertEqual({e.direccion: e.mundo for e in r}, {"tarea:T1": "trabajo", "tarea:T2": "personal"})


class LasTareas(Prueba):
    """`telar tipo tarea lista --mundo`: cada tarea dice su mundo, según la configuración de aquí."""

    def setUp(self):
        super().setUp()
        from telar.tipos import tarea as tipo

        c = config(DOS)
        self.ctx = SimpleNamespace(config=SimpleNamespace(mundos=c.mundos, raiz=RAIZ, bus=c.bus,
                                                          tipos=(cfg.Tipo(clave="tarea", carpeta="/x"),)))
        self.tareas = [(tipo.Tarea(id="T1", titulo="a", area="cliente"), "v1"),
                       (tipo.Tarea(id="T2", titulo="b", area="personal", proyecto="empresa/faro"), "v2"),
                       (tipo.Tarea(id="T3", titulo="c", area="otra"), "v3")]

    def lista(self, **kw):
        from telar.servicios import tipos as st

        indice = SimpleNamespace(consultar=lambda f: [t for t in self.tareas if f(t[0])], fallas={})
        with mock.patch.object(st, "indice", return_value=indice):
            return st.lista(self.ctx, **kw)

    def test_cada_una_con_su_mundo(self):
        r = self.lista()
        self.assertEqual({t.id: t.mundo for t in r.tareas}, {"T1": "trabajo", "T2": "personal", "T3": ""})
        self.assertEqual(r.model_dump(mode="json")["tareas"][0]["mundo"], "trabajo")

    def test_se_filtran(self):
        self.assertEqual([t.id for t in self.lista(mundos=("personal",)).tareas], ["T2"])
        self.assertEqual([t.id for t in self.lista(mundos=("trabajo", "sin-clasificar")).tareas], ["T1", "T3"])

    def test_la_de_otra_maquina_se_reclasifica_aqui(self):
        from telar import bus as mod_bus
        from telar.servicios import tipos as st

        self.ctx.config.tipos = (cfg.Tipo(clave="tarea", en="servidor"),)
        alla = {"tareas": [{"id": "T1", "titulo": "a", "area": "cliente", "version": "v", "mundo": "de-alla"}], "fallas": {}}
        with mock.patch.object(mod_bus, "hay_bus", return_value=True), mock.patch.object(mod_bus, "maquina", return_value="laptop"), \
                mock.patch.object(st, "_pedir_alla", return_value=alla) as pedir:
            r = st.lista(self.ctx, mundos=("trabajo",))
        self.assertEqual([(t.id, t.mundo) for t in r.tareas], [("T1", "trabajo")])
        self.assertNotIn("--mundo", pedir.call_args.args[2])  # allá no se filtra: sus mundos son los suyos

    def test_el_objeto_tarea_lo_dice_en_sus_campos(self):
        from telar.servicios import tipos as st

        t = st._con_mundo(self.ctx, st.TareaConVersion(id="T1", titulo="a", area="cliente", version="v"))
        self.assertEqual(objetos.Tarea()._objeto(t).campos["mundo"], "trabajo")


class LasFilas(Prueba):
    def test_cada_fila_con_su_mundo_antes_de_inventarle_un_area(self):
        from telar.ordenes.pendientes import con_area, con_mundo

        filas = [{"proveedor": "tareas", "area": "", "proyecto": "", "ruta": "empresa/faro"},
                 {"proveedor": "", "area": "", "ruta": "casa/jardin"}]
        con_area(con_mundo(config(DOS), filas))
        self.assertEqual([f["mundo"] for f in filas], ["", "personal"])
        self.assertEqual(filas[0]["area"], "empresa")  # el área de antes sigue igual


class LosEventos(Prueba):
    def test_un_proveedor_declara_el_area_de_sus_items_y_el_dia_dice_su_mundo(self):
        from datetime import date, datetime

        from telar import alla
        from telar.modelo import Item
        from telar.ordenes import _comun
        from telar.ordenes.pendientes import de_proveedores
        from telar.servicios import hoy as servicio_hoy

        c = config(DOS + '\n[proveedores.cal]\narea = "equipo"\n[proveedores.otro]\n')
        items = [Item(proveedor="cal", id="e1", titulo="Comité", cuando=datetime(2026, 11, 17, 15), clase="evento"),
                 Item(proveedor="cal", id="e2", titulo="Cumpleaños", cuando=datetime(2026, 11, 17, 20), clase="evento",
                      datos={"area": "personal"}),
                 Item(proveedor="otro", id="e3", titulo="Algo", cuando=datetime(2026, 11, 17, 18), clase="evento")]
        tel = SimpleNamespace(hilos=[], raiz=RAIZ)
        ctx = SimpleNamespace(config=c)
        with mock.patch.object(alla, "consultar", return_value=(items, [])), \
                mock.patch.object(_comun, "asegurar_proveedores"), mock.patch.object(_comun, "enrutar", return_value=None):
            filas, _ = de_proveedores(ctx, tel, date(2026, 11, 17))
            self.assertEqual([f["area"] for f in filas], ["equipo", "personal", ""], "la del ítem le gana a la del proveedor")
            with mock.patch.object(_comun, "tejer", return_value=SimpleNamespace(hilos=[], raiz=RAIZ)), \
                    mock.patch("telar.ordenes.pendientes.juntar", return_value=[]):
                h = servicio_hoy.hoy(ctx, dia=date(2026, 11, 17))
        self.assertEqual([(e.texto, e.mundo) for e in h.agenda], [("Comité", "trabajo"), ("Algo", ""), ("Cumpleaños", "personal")])


class LaOrden(Prueba):
    def test_telar_esperas_mundo(self):
        from telar.ordenes import esperas as orden
        from telar.servicios import esperas as servicio

        ctx = SimpleNamespace(config=config(DOS))
        r = servicio.Esperas(esperas=[espera("tarea:T1", clase="avance:pregunta", mundo="trabajo"),
                                      espera("mensaje:m1", clase="retenido")], mundos=["trabajo", "personal"])
        with mock.patch.object(servicio, "esperas", return_value=r) as pedir:
            salida = io.StringIO()
            with redirect_stdout(salida):
                self.assertEqual(orden.main(["--mundo", "trabajo", "--mundo", "sin-clasificar"], ctx), 0)
        self.assertEqual(pedir.call_args.kwargs["mundos"], ("trabajo", "sin-clasificar"))
        texto = salida.getvalue()
        self.assertLess(texto.index("trabajo"), texto.index("sin clasificar"))
        with mock.patch.object(servicio, "esperas", return_value=r), redirect_stdout(io.StringIO()) as s:
            orden.main(["--json"], ctx)
        self.assertEqual(json.loads(s.getvalue())["mundos"], ["trabajo", "personal"])


class LaListaDeHilosYLasFotos(Prueba):
    """`telar hilos` y `telar espejo ver`: con `[mundos]`, cada hilo dice el suyo; sin, ni se dice."""

    def test_cada_hilo_con_su_mundo(self):
        from telar.servicios import hilos as servicio

        ctx = SimpleNamespace(config=config(CON_HORARIO))
        hs = [{"nombre": "Faro", "relativa": "empresa/faro"}, {"nombre": "Rama", "relativa": "../w", "padre": "Faro"},
              {"nombre": "Suelto", "relativa": "notas"}, {"nombre": "Etiquetado", "relativa": "casa/x", "etiquetas": ["trabajo"]}]
        servicio._con_mundo(hs, ctx)
        self.assertEqual([h["mundo"] for h in hs], ["trabajo", "trabajo", "", "trabajo"])
        sin = [{"nombre": "Faro", "relativa": "empresa/faro"}]
        servicio._con_mundo(sin, SimpleNamespace(config=config()))
        self.assertNotIn("mundo", sin[0])

    def test_cada_proyecto_con_su_mundo(self):
        from telar.ordenes import _comun
        from telar.servicios import proyectos as servicio

        unidades = [{"ruta": "empresa/faro"}, {"ruta": "casa/huerto"}, {"ruta": "notas/x.md"}]
        with mock.patch.object(_comun, "tejer"), mock.patch("telar.ordenes.proyectos.listar", side_effect=lambda *_: [dict(u) for u in unidades]), \
                mock.patch.object(servicio, "plazos", return_value=({}, [])):
            r = servicio.lista(SimpleNamespace(config=config(CON_HORARIO), perfil=SimpleNamespace(areas=[])))
            sin = servicio.lista(SimpleNamespace(config=config(), perfil=SimpleNamespace(areas=[])))
        self.assertEqual([p.model_dump().get("mundo") for p in r.proyectos], ["trabajo", "personal", ""])
        self.assertNotIn("mundo", sin.proyectos[0].model_dump())

    def test_cada_agente_con_su_mundo(self):
        """`GET /agentes`: cada uno con el de su carpeta, viva aquí o en otra máquina (Estrategia cuenta sus encargos)."""
        from telar.servicios import agentes as servicio

        def ag(clave: str, maquina: str = "") -> dict:
            return {"agente": {"clave": clave, "nombre": clave.title()}, "maquina": maquina, "aqui": not maquina,
                    "encargos": []}

        agentes = [ag("dinero"), ag("faro", "servidor"), ag("suelto")]
        texto = CON_HORARIO.replace('rutas = ["casa/"]', 'rutas = ["casa/", "agentes/dinero/"]') \
            .replace('rutas = ["empresa/"]', 'rutas = ["empresa/", "agentes/faro/"]') + '\n[agentes]\ncarpeta = "agentes"\n'
        with mock.patch.object(servicio, "estado_local", side_effect=lambda ctx: [dict(a) for a in agentes]), \
                mock.patch("telar.agentes.descubrir", return_value=[]):
            r = servicio.lista(SimpleNamespace(config=config(texto))).model_dump()["agentes"]
            sin = servicio.lista(SimpleNamespace(config=config('[agentes]\ncarpeta = "agentes"\n'))).model_dump()["agentes"]
        self.assertEqual({x["agente"]["clave"]: x["mundo"] for x in r}, {"dinero": "personal", "faro": "trabajo", "suelto": ""})
        self.assertNotIn("mundo", sin[0])
        self.assertEqual(mundos.de_agente(config(texto), "faro"), "trabajo")
        self.assertEqual(mundos.de_agente(config(CON_HORARIO), "faro"), "", "sin [agentes] carpeta, ninguno")

    def test_las_fotos_de_las_otras_maquinas(self):
        from telar import espejo
        from telar.servicios import espejos as servicio

        fotos = [{"nombre": "servidor", "hilos": [{"nombre": "Riego", "relativa": "casa/riego"},
                                                  {"nombre": "Hijo", "relativa": "", "padre": "Riego"}]}]
        with mock.patch.object(espejo, "leer_todos", return_value=fotos):
            r = servicio.ver(SimpleNamespace(config=config(CON_HORARIO)))
            sin = servicio.ver(SimpleNamespace(config=config()))
        hilos = r.model_dump()["espejos"][0]["hilos"]
        self.assertEqual([h["mundo"] for h in hilos], ["personal", "personal"])
        self.assertNotIn("mundo", sin.model_dump()["espejos"][0]["hilos"][0])
        self.assertNotIn("mundo", fotos[0]["hilos"][0], "lo leído no se toca")

    def test_los_archivados_de_las_otras_maquinas_tambien_traen_su_mundo(self):
        """El ARCHIVO de la página lista también los de las otras máquinas, con el filtro de mundo de siempre."""
        from telar import espejo
        from telar.servicios import espejos as servicio

        fotos = [{"nombre": "laptop", "hilos": [{"nombre": "Riego", "relativa": "casa/riego"}],
                  "archivados": [{"nombre": "Viejo", "relativa": "empresa/x"}, {"nombre": "Hijo viejo", "padre": "Riego"}]}]
        with mock.patch.object(espejo, "leer_todos", return_value=fotos):
            r = servicio.ver(SimpleNamespace(config=config(CON_HORARIO))).model_dump()["espejos"][0]
        self.assertEqual([a["mundo"] for a in r["archivados"]], ["trabajo", "personal"], "por su carpeta, o por su padre")
        self.assertNotIn("mundo", fotos[0]["archivados"][0], "lo leído no se toca")


@unittest.skipUnless(HAY_FASTAPI, "sin el extra «serve»")
class LaApi(Prueba):
    def test_get_esperas_mundo(self):
        from fastapi.testclient import TestClient

        from telar import api
        from telar.servicios import esperas as servicio

        r = servicio.Esperas(esperas=[espera("tarea:T1", mundo="trabajo")], mundos=["trabajo"])
        with mock.patch.object(servicio, "esperas", return_value=r) as pedir, mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            respuesta = TestClient(api.app).get("/esperas?mundo=trabajo&mundo=sin-clasificar")
        self.assertEqual(respuesta.status_code, 200, respuesta.text)
        self.assertEqual(pedir.call_args.kwargs["mundos"], ("trabajo", "sin-clasificar"))
        self.assertEqual(respuesta.json()["esperas"][0]["mundo"], "trabajo")


class UnAgenteDeOtraMaquina(Prueba):
    """El caso del 23-nov-2026: un agente creó a Cocina en el servidor (`mundo = "personal"` en su agente.toml) y la
    raíz del laptop iba 140 commits atrás, sin su carpeta. El laptop no lo listaba, y su hilo (que vive en el servidor)
    quedaba sin clasificar: a la vista en el trabajo. Ahora la foto del servidor trae sus agentes con su mundo: el laptop
    lo lista, con su máquina, y lo clasifica aunque su carpeta no haya llegado."""

    def setUp(self):
        super().setUp()
        import tempfile

        from telar import espejo

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name)
        # aquí solo está Secretaría; agentes/ es del trabajo (como «agentes/taller/» en una casa real)
        d = self.raiz / "agentes" / "secretaria"
        d.mkdir(parents=True)
        (d / "CLAUDE.md").write_text("# Secretaría\n")
        import tomllib

        texto = CON_HORARIO.replace('rutas = ["empresa/"]', 'rutas = ["empresa/", "agentes/"]') + '\n[agentes]\ncarpeta = "agentes"\n'
        self.c = cfg.desde_dict({"raiz": str(self.raiz), "estado": str(self.raiz / "estado"), **tomllib.loads(texto)})
        espejo.guardar(self.c, "telar", json.dumps({
            "version": espejo.VERSION, "maquina": "telar", "hilos": [
                {"nombre": "Cocina", "vivo": True, "relativa": "agentes/cocina", "agente": "cocina"}],
            "agentes": [{"clave": "cocina", "nombre": "Cocina", "mundo": "personal"},
                        {"clave": "secretaria", "nombre": "Secretaría", "mundo": ""},
                        {"clave": "marciano", "nombre": "Marciano", "mundo": "marte"}]}))

    def test_su_mundo_viene_de_la_foto_de_su_maquina(self):
        self.assertEqual(mundos.declarado_de_agente(self.c, "cocina"), "personal")
        self.assertEqual(mundos.de_agente(self.c, "cocina"), "personal", "le gana a la ruta de agentes/, del trabajo")
        self.assertEqual(mundos.declarado_de_agente(self.c, "marciano"), "", "un mundo que aquí no existe no cuenta")
        self.assertEqual(mundos.declarado_de_agente(self.c, "secretaria"), "")

    def test_su_hilo_alla_es_de_su_mundo(self):
        k = mundos.Clasificador(SimpleNamespace(config=self.c))
        with mock.patch("telar.ordenes._comun.tejer", side_effect=RuntimeError("sin tmux")):
            # antes: su carpeta no estaba aquí, y la ruta «agentes/cocina» lo dejaba en el trabajo
            self.assertEqual(k.de_hilo("Cocina", "telar"), "personal")

    def test_sale_en_la_lista_con_su_maquina_y_sin_repetir_los_de_aqui(self):
        from telar.servicios import config as servicio

        secciones = {s["clave"]: s for s in servicio._agentes(self.c)}
        self.assertEqual(set(secciones), {"agente:secretaria", "agente:cocina", "agente:marciano"})
        cocina = secciones["agente:cocina"]
        self.assertEqual((cocina["nombre"], cocina["maquina"], cocina["mundo"], cocina["home"], cocina["hilos"]),
                         ("Cocina", "telar", "personal", False, ["Cocina"]))
        self.assertNotIn("maquina", secciones["agente:secretaria"], "el de aquí, el de aquí")
        self.assertEqual(secciones["agente:marciano"]["mundo"], "", "de un mundo que aquí no hay: sin clasificar")

    def test_doctor_dice_que_falta_y_como_traerlo(self):
        from telar.ordenes import doctor

        with mock.patch.object(doctor, "atrasado", return_value=(Path("/casa/raiz"), 140)):
            r = doctor._agentes_de_otras(SimpleNamespace(config=self.c))
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["estado"], doctor.AVISO)
        self.assertIn("raiz atrasado 140 commits", r[0]["dice"])
        self.assertIn("cocina, marciano (de telar)", r[0]["dice"])
        self.assertIn("git -C /casa/raiz pull", r[0]["arreglo"])
        with mock.patch.object(doctor, "atrasado", return_value=None):
            self.assertNotIn("atrasado", doctor._agentes_de_otras(SimpleNamespace(config=self.c))[0]["dice"])


if __name__ == "__main__":
    unittest.main()
