"""Los modos de la página (telar.modos): su catálogo, los de fábrica, los de `[modos]`, y guardarlos o quitarlos."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config, modos

try:
    from fastapi.testclient import TestClient

    from telar import api

    HAY_SERVE = True
except ImportError:
    HAY_SERVE = False


class LosModos(Prueba):
    def test_un_propio_dice_su_icono_en_la_banda_y_sin_decirlo_es_el_de_su_base(self):
        c = config.desde_dict({"modos": {"entradas": {"nombre": "entradas", "icono": "bandeja", "filas": "pestana:leer"},
                                         "otro": {"base": "estrategia"}}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertEqual(m["entradas"]["valores"]["icono"], "bandeja")
        self.assertEqual(m["otro"]["valores"]["icono"], "", "sin decirlo: vacío, la página pone el de su base")
        with self.assertRaises(config.ErrorDeConfig):
            modos.validar("malo", {"icono": "no es un nombre"})

    def test_de_fabrica_las_cuatro_actitudes_y_tactica_toma_la_terminal_de_su_tabla(self):
        c = config.desde_dict({"terminal": {"columnas": 120, "fondo": "#112233"}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertEqual(list(m), ["tactica", "estrategia", "foco", "todo"])
        self.assertEqual([m[k]["base"] for k in m], ["tactica", "estrategia", "foco", "todo"], "cada uno es su base")
        self.assertEqual((m["tactica"]["valores"]["columnas"], m["tactica"]["valores"]["fondo"]), (120, "#112233"))
        self.assertEqual(m["tactica"]["valores"]["escribir"], "oculta")
        self.assertEqual([m[k]["valores"]["filas"] for k in m], ["tactica, calendario", "proyectos, bloque:tablero, bloque:registro",
                                                                 "tactica, calendario", "*"])
        self.assertEqual((m["estrategia"]["valores"]["avisos"], m["estrategia"]["valores"]["columnas"]), ("urgentes", 120),
                         "lo que estrategia no dice, de táctica")
        foco = m["foco"]["valores"]
        self.assertEqual((foco["barra"], foco["cabecera"], foco["escribir"], foco["posicion"], foco["fondo"]),
                         ("oculta", "oculta", "oculta", "centro", "ninguno"))
        self.assertFalse(m["foco"]["cambiado"])

    def test_los_de_la_configuracion_pisan_y_suman(self):
        c = config.desde_dict({"modos": {"foco": {"columnas": "todo"}, "lectura": {"nombre": "Lectura", "barra": "plegada"}}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertEqual(m["foco"]["valores"]["columnas"], 0)
        self.assertEqual(m["foco"]["valores"]["cabecera"], "oculta")  # lo demás de foco, de fábrica
        self.assertTrue(m["foco"]["cambiado"])
        self.assertEqual((m["lectura"]["nombre"], m["lectura"]["valores"]["barra"]), ("Lectura", "plegada"))
        self.assertEqual(m["lectura"]["valores"]["cabecera"], "visible")  # lo que no dice, de estándar

    def test_estandar_es_tactica(self):
        # la configuración de antes sigue valiendo: [modos.estandar] es [modos.tactica]; con los dos, gana el nuevo
        c = config.desde_dict({"modos": {"estandar": {"nombre": "mío", "barra": "plegada", "avisos": "urgentes"},
                                         "tactica": {"avisos": "ninguno"}}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertNotIn("estandar", m)
        self.assertEqual((m["tactica"]["nombre"], m["tactica"]["valores"]["barra"], m["tactica"]["valores"]["avisos"]),
                         ("mío", "plegada", "ninguno"))
        self.assertTrue(m["tactica"]["cambiado"])
        self.assertEqual(m["estrategia"]["valores"]["barra"], "plegada", "y los demás lo heredan")

    def test_uno_propio_sobre_su_base(self):
        c = config.desde_dict({"modos": {"revision": {"base": "estrategia", "barra": "plegada"},
                                         "oficina": {"etiquetas": "trabajo", "mundo": "trabajo"}}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertEqual(list(m)[-2:], ["revision", "oficina"])
        self.assertEqual((m["revision"]["base"], m["revision"]["valores"]["filas"], m["revision"]["valores"]["barra"]),
                         ("estrategia", "proyectos, bloque:tablero, bloque:registro", "plegada"))
        self.assertEqual((m["oficina"]["base"], m["oficina"]["valores"]["filas"], m["oficina"]["valores"]["mundo"]),
                         ("tactica", "tactica, calendario", "trabajo"))
        for malo in ({"tactica": {"base": "todo"}}, {"x": {"base": "estandar"}}, {"x": {"base": "otra"}}):
            with self.assertRaises(config.ErrorDeConfig, msg=str(malo)):
                config.desde_dict({"modos": malo})

    def test_las_filas_y_el_mundo(self):
        self.assertEqual(modos.validar("x", {"filas": " tactica,bloque:correo , tactica"})["valores"], {"filas": "tactica, bloque:correo"})
        self.assertEqual(modos.validar("x", {"filas": ["tactica", "*"]})["valores"], {"filas": "*"})
        self.assertEqual(modos.validar("x", {"mundo": " trabajo "})["valores"], {"mundo": "trabajo"})
        for malo in ({"filas": "una cosa"}, {"mundo": "mi trabajo"}):
            with self.assertRaises(config.ErrorDeConfig, msg=str(malo)):
                modos.validar("x", malo)

    def test_lo_que_no_sirve(self):
        for tabla in ({"X": {}}, {"a": {"barra": "rara"}}, {"a": {"inventado": 1}}, {"a": {"columnas": 5}},
                      {"a": {"fondo": "#1"}}, {"a": "no es tabla"}):
            with self.assertRaises(config.ErrorDeConfig, msg=str(tabla)):
                config.desde_dict({"modos": tabla})

    def test_que_son_proyectos_y_negocios_lo_dice_el_modo(self):
        # nombres de arquetipos separados por coma, con sus espacios; en minúsculas y sin repetir. Vacío: de fábrica,
        # proyectos son todas las unidades y negocios ninguna
        v = modos.validar("equipo", {"proyectos": " Proyecto,proyecto  cerrado , proyecto", "negocios": ["deal"]})["valores"]
        self.assertEqual(v, {"proyectos": "proyecto,proyecto cerrado", "negocios": "deal"})
        self.assertEqual(modos.validar("equipo", {"negocios": ""})["valores"], {"negocios": ""})
        with self.assertRaises(config.ErrorDeConfig):
            modos.validar("equipo", {"proyectos": "proyecto, <b>"})
        estandar = modos.todos(config.desde_dict({}))[0]["valores"]
        self.assertEqual((estandar["proyectos"], estandar["negocios"]), ("", ""))
        self.assertEqual(modos.POR_CLAVE["proyectos"].grupo, "proyectos")

    def test_que_son_iniciativas_y_con_que_se_agrupan_lo_dice_el_modo(self):
        # las iniciativas son arquetipos, como los proyectos; se agrupan por un campo del frontmatter, con el selector
        # de productos.yaml ({frontmatter:<clave>}); sin las llaves, o solo la clave, también vale
        v = modos.validar("equipo", {"iniciativas": "Iniciativa, iniciativa", "agrupar_iniciativas": "frontmatter:programa"})["valores"]
        self.assertEqual(v, {"iniciativas": "iniciativa", "agrupar_iniciativas": "{frontmatter:programa}"})
        for escrito in ("{frontmatter:programa}", " { frontmatter: programa } ", "programa"):
            self.assertEqual(modos.validar("equipo", {"agrupar_iniciativas": escrito})["valores"]["agrupar_iniciativas"],
                             "{frontmatter:programa}", escrito)
        self.assertEqual(modos.validar("equipo", {"agrupar_iniciativas": ""})["valores"], {"agrupar_iniciativas": ""})
        # varios, en orden de preferencia: la pantalla agrupa por el primero que alguna ficha tenga
        self.assertEqual(modos.validar("equipo", {"agrupar_iniciativas": "funcion, {frontmatter:programa}, funcion"})["valores"]
                         ["agrupar_iniciativas"], "{frontmatter:funcion}, {frontmatter:programa}")
        for malo in ("{campo:Cliente}", "{programa", "dos palabras", "frontmatter:", "funcion, {campo:Cliente}", "funcion,"):
            with self.assertRaises(config.ErrorDeConfig, msg=malo):
                modos.validar("equipo", {"agrupar_iniciativas": malo})
        # de fábrica, sin sección de iniciativas; un modo propio las toma de táctica
        todos = {m["clave"]: m["valores"] for m in modos.todos(config.desde_dict(
            {"modos": {"tactica": {"iniciativas": "iniciativa", "agrupar_iniciativas": "programa"}, "equipo": {}}}))}
        self.assertEqual((todos["estrategia"]["iniciativas"], todos["equipo"]["agrupar_iniciativas"]), ("iniciativa", "{frontmatter:programa}"))
        self.assertEqual(modos.todos(config.desde_dict({}))[0]["valores"]["iniciativas"], "")

    def test_el_area_de_entrada_de_estrategia_la_dice_el_modo(self):
        # `area`: el área (o las áreas) con que abre filtrada la tabla de proyectos e iniciativas; como la escribe cada
        # ficha (mayúsculas, espacios), sin repetir sin mirar mayúsculas ni tildes
        v = modos.validar("equipo", {"area": " Tienda ,tienda, Gestión de  socios, gestion de socios"})["valores"]
        self.assertEqual(v, {"area": "Tienda, Gestión de socios"})
        self.assertEqual(modos.validar("equipo", {"area": ["Tienda"]})["valores"], {"area": "Tienda"})
        self.assertEqual(modos.validar("equipo", {"area": ""})["valores"], {"area": ""})
        for malo in ("<b>", "x" * 41, "tienda, ,; drop"):
            with self.assertRaises(config.ErrorDeConfig, msg=malo):
                modos.validar("equipo", {"area": malo})
        # de fábrica, ninguna (todas); lo dicho en táctica lo heredan estrategia y los propios
        self.assertEqual(modos.todos(config.desde_dict({}))[0]["valores"]["area"], "")
        todos = {m["clave"]: m["valores"] for m in modos.todos(config.desde_dict({"modos": {"tactica": {"area": "Tienda"}, "equipo": {}}}))}
        self.assertEqual((todos["estrategia"]["area"], todos["equipo"]["area"]), ("Tienda", "Tienda"))
        self.assertEqual(modos.POR_CLAVE["area"].grupo, "proyectos")

    def test_el_tema_es_uno_de_los_de_la_pagina(self):
        self.assertEqual(modos.validar("noche", {"tema": "Riso"})["valores"], {"tema": "riso"})
        with self.assertRaises(config.ErrorDeConfig):
            modos.validar("noche", {"tema": "neón azul"})
        self.assertEqual(modos.todos(config.desde_dict({}))[0]["valores"]["tema"], "telar")
        # uno propio vale si [temas] lo declara: el nombre solo, no
        with self.assertRaises(config.ErrorDeConfig) as e:
            config.desde_dict({"modos": {"noche": {"tema": "neon"}}})
        self.assertIn("modos.noche.tema", str(e.exception))
        hecho = config.desde_dict({"modos": {"noche": {"tema": "neon"}}, "temas": {"neon": {"base": "riso"}}})
        self.assertEqual(hecho.modos["noche"]["valores"]["tema"], "neon")
        # y la lista del tema en el catálogo de ajustes, con los propios
        tema = next(a for a in modos.catalogo(hecho) if a["clave"] == "tema")
        self.assertEqual(tema["opciones"], [*modos.TEMAS, "neon"])

    def test_los_temas_son_los_mismos_que_dibuja_la_pagina(self):
        # cada tema tiene sus colores en marco.css (el de fábrica, en :root) y su nombre en componentes/temas.ts
        raiz = Path(__file__).resolve().parent.parent
        css = (raiz / "src" / "telar" / "web" / "marco.css").read_text(encoding="utf-8")
        ts = (raiz / "pagina" / "src" / "componentes" / "temas.ts").read_text(encoding="utf-8")
        for t in modos.TEMAS:
            self.assertIn(f'[data-tema="{t}"]', css, t)
            self.assertIn(f"clave: '{t}'", ts, t)
        import re

        self.assertEqual(set(re.findall(r"clave: '([a-z-]+)'", ts)), set(modos.TEMAS))

    def test_la_densidad_es_una_de_las_de_la_pagina(self):
        self.assertEqual(modos.validar("tactil", {"densidad": "Amplia"})["valores"], {"densidad": "amplia"})
        with self.assertRaises(config.ErrorDeConfig):
            modos.validar("tactil", {"densidad": "enorme"})
        # de fábrica, «auto»: amplia en una pantalla táctil, compacta con mouse
        self.assertEqual(modos.todos(config.desde_dict({}))[0]["valores"]["densidad"], "auto")
        self.assertEqual(modos.POR_CLAVE["densidad"].grupo, "aspecto")

    def test_las_densidades_son_las_mismas_que_dibuja_la_pagina(self):
        # cada una tiene sus medidas en marco.css (la de fábrica, en :root) y su nombre en componentes/densidades.ts;
        # «auto» no es una densidad: la elige la página según el puntero
        raiz = Path(__file__).resolve().parent.parent
        css = (raiz / "src" / "telar" / "web" / "marco.css").read_text(encoding="utf-8")
        ts = (raiz / "pagina" / "src" / "componentes" / "densidades.ts").read_text(encoding="utf-8")
        for d in modos.DENSIDADES:
            if d in ("auto", "compacta"):
                continue
            self.assertIn(f'[data-densidad="{d}"]', css, d)
        self.assertIn("[data-densidad] {", css)
        import re

        self.assertEqual(set(re.findall(r"clave: '([a-z-]+)'", ts)) | {"auto"}, set(modos.DENSIDADES))
        self.assertIn("AUTO = 'auto'", ts)

    def test_que_agentes_se_ven_lo_dice_cada_modo_y_no_se_hereda(self):
        # las carpetas de los agentes, separadas por coma; su dirección también vale. Vacío o *, todos; -, ninguno
        v = lambda x: modos.validar("x", {"agentes": x})["valores"]["agentes"]  # noqa: E731
        self.assertEqual(v(" vigia,agente:cartero , vigia"), "vigia, cartero")
        self.assertEqual(v(["vigia", "cartero"]), "vigia, cartero")
        self.assertEqual((v(""), v("*"), v("vigia, *")), ("", "", ""))
        self.assertEqual((v("-"), v(" - ")), ("-", "-"))
        for malo in ("vigia, -", "un agente", "a/b"):
            with self.assertRaises(config.ErrorDeConfig, msg=malo):
                v(malo)
        # sin decirlo, todos: un modo sin la clave se ve como antes de que existiera
        m = {x["clave"]: x for x in modos.todos(config.desde_dict({}))}
        self.assertEqual({k: m[k]["valores"]["agentes"] for k in m}, dict.fromkeys(m, ""))
        # cada modo dice los suyos: lo de táctica no pasa a estrategia, ni lo de estrategia a uno propio sobre ella
        c = config.desde_dict({"modos": {"tactica": {"agentes": "vigia"}, "estrategia": {"agentes": "-"},
                                         "casa": {"base": "estrategia"}, "oficina": {"agentes": "cartero"}}})
        m = {x["clave"]: x["valores"]["agentes"] for x in modos.todos(c)}
        self.assertEqual(m, {"tactica": "vigia", "estrategia": "-", "foco": "", "todo": "", "casa": "", "oficina": "cartero"})
        # con su nombre de antes también
        c = config.desde_dict({"modos": {"estandar": {"agentes": "vigia"}}})
        self.assertEqual(modos.todos(c)[0]["valores"]["agentes"], "vigia")

    def test_lo_que_dice_su_tabla_y_a_que_vuelve_sin_ella(self):
        # `propios`: lo que el modo dice en su tabla; `heredados`: lo que diría cada uno sin su línea
        c = config.desde_dict({"terminal": {"columnas": 120}, "modos": {
            "tactica": {"filas": "tactica"}, "estrategia": {"barra": "plegada"},
            "casa": {"base": "estrategia", "filas": "proyectos"}, "oficina": {"filas": "calendario"}}})
        m = {x["clave"]: x for x in modos.todos(c)}
        self.assertEqual((m["tactica"]["propios"], m["tactica"]["heredados"]), (["filas"], {"filas": "tactica, calendario"}),
                         "táctica sin su línea vuelve a la de fábrica")
        self.assertEqual((m["foco"]["propios"], m["foco"]["heredados"]), ([], {}))
        self.assertEqual(m["foco"]["valores"]["filas"], "tactica", "foco las hereda de táctica, como la deja la configuración")
        self.assertEqual(m["estrategia"]["heredados"], {"barra": "abierta"})
        self.assertEqual(m["casa"]["heredados"], {"filas": "proyectos, bloque:tablero, bloque:registro"},
                         "uno propio vuelve a las de su base")
        self.assertEqual(m["oficina"]["heredados"], {"filas": "tactica"}, "sobre táctica, como la deja la configuración")
        # de dónde sale, sin su línea, lo que no es de su fábrica: foco no dice sus pestañas, las toma de táctica
        self.assertEqual((m["tactica"]["origenes"], m["foco"]["origenes"].get("filas"), m["estrategia"]["origenes"].get("filas")),
                         ({}, "tactica", None))
        self.assertEqual((m["casa"]["origenes"]["filas"], m["casa"]["origenes"]["barra"], m["oficina"]["origenes"]["filas"]),
                         ("estrategia", "estrategia", "tactica"), "la barra plegada de estrategia es de la configuración")
        self.assertEqual(m["casa"]["origenes"]["tema"], "tactica")
        self.assertNotIn("agentes", m["casa"]["origenes"], "los agentes no se heredan")

    def test_las_pestanas_que_hay(self):
        c = config.desde_dict({})
        self.assertEqual(modos.pestanas_que_hay(c),
                         ["todo", "tactica", "ahora", "esperas", "revisar", "proyectos", "calendario"])
        bloques = (SimpleNamespace(clave="correo", dentro=""), SimpleNamespace(clave="gantt", dentro="proyectos"))
        proveedores = [SimpleNamespace(opciones={"pestana": "leer"}), SimpleNamespace(opciones={})]
        falsa = SimpleNamespace(bloques=bloques, proveedores_activos=lambda: proveedores, modos={}, terminal=c.terminal)
        hay = modos.pestanas_que_hay(falsa)
        self.assertEqual(hay[hay.index("revisar"):], ["revisar", "bloque:correo", "pestana:leer", "proyectos", "calendario"],
                         "los bloques sin «dentro» y las pestañas de los proveedores, entre tareas y proyectos")

    def test_revisar_las_filas_que_manda_la_pagina(self):
        c = config.desde_dict({"modos": {"casa": {"filas": "calendario, bloque:viejo"}}})
        r = lambda clave, v: modos.revisar_filas(c, clave, v)  # noqa: E731
        self.assertEqual(r("tactica", "calendario,tactica , calendario"), "calendario, tactica")
        self.assertEqual(r("tactica", "tareas, *"), "*")
        self.assertEqual(r("estandar", "tareas"), "tareas", "«tareas» es la de clave «revisar»")
        # la de un módulo que ya no está: la conserva el modo que la nombraba (estrategia, la del tablero), no otro
        self.assertEqual(r("estrategia", "bloque:tablero, proyectos"), "bloque:tablero, proyectos")
        # una pestaña que se sacó del dashboard (estrategia, el plan) no se conserva: se quita
        self.assertEqual(r("estrategia", "estrategia, bloque:tablero, plan"), "bloque:tablero")
        with self.assertRaises(config.ErrorDeConfig, msg="solo retiradas: ninguna"):
            r("estrategia", "estrategia")
        self.assertEqual(r("casa", "bloque:viejo, ahora"), "bloque:viejo, ahora")
        for clave, malo in (("tactica", "bloque:tablero"), ("tactica", "nada"), ("foco", "pestana:leer"), ("tactica", ""), ("tactica", " , ")):
            with self.assertRaises(config.ErrorDeConfig, msg=f"{clave} {malo}"):
                r(clave, malo)
        with self.assertRaises(KeyError):
            r("lectura", "ahora")

    def test_ajustar_cambia_solo_esas_lineas(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "config.toml"
            ruta.write_text(f'raiz = "{d}"\n[terminal]\ncolumnas = 120\n\n[modos.oficina]\nnombre = "oficina"\n'
                            '# a mano\netiquetas = "trabajo"\n')
            # en uno de fábrica sin tabla: la crea con esa línea sola, y lo demás lo sigue heredando
            self.assertEqual(modos.ajustar(ruta, "estrategia", {"agentes": "vigia,agente:cartero"}), {"agentes": "vigia, cartero"})
            c = config.cargar(ruta)
            self.assertEqual(c.modos["estrategia"]["valores"], {"agentes": "vigia, cartero"})
            m = {x["clave"]: x for x in modos.todos(c)}
            self.assertTrue(m["estrategia"]["cambiado"])
            self.assertEqual((m["estrategia"]["valores"]["columnas"], m["tactica"]["valores"]["agentes"]), (120, ""))
            # en uno propio: su nombre, sus etiquetas y el comentario quedan
            modos.ajustar(ruta, "oficina", {"agentes": "-"})
            texto = ruta.read_text()
            self.assertIn("# a mano", texto)
            self.assertEqual(config.cargar(ruta).modos["oficina"], {"nombre": "oficina", "valores": {"etiquetas": "trabajo", "agentes": "-"}})
            # todos otra vez: la línea se va; y uno de fábrica que se queda sin nada vuelve a ser el de fábrica
            modos.ajustar(ruta, "oficina", {"agentes": ""})
            self.assertEqual(config.cargar(ruta).modos["oficina"]["valores"], {"etiquetas": "trabajo"})
            modos.ajustar(ruta, "estrategia", {"agentes": "*"})
            self.assertNotIn("modos.estrategia", ruta.read_text())
            self.assertFalse(next(x for x in modos.todos(config.cargar(ruta)) if x["clave"] == "estrategia")["cambiado"])
            # «estandar» es «tactica»: escribe en la de ahora, y quitar la quita también de la de antes
            ruta.write_text(ruta.read_text() + '\n[modos.estandar]\nbarra = "plegada"\nagentes = "vigia"\n')
            modos.ajustar(ruta, "estandar", {"agentes": ""})
            c = config.cargar(ruta)
            self.assertEqual((c.modos["estandar"]["valores"], "tactica" in c.modos), ({"barra": "plegada"}, False))
            self.assertEqual(modos.todos(c)[0]["valores"]["agentes"], "")
            # un propio que no está no se crea; un valor que no sirve no se escribe
            with self.assertRaises(KeyError):
                modos.ajustar(ruta, "lectura", {"agentes": "vigia"})
            antes = ruta.read_text()
            with self.assertRaises(config.ErrorDeConfig):
                modos.ajustar(ruta, "foco", {"agentes": "vigia, -"})
            self.assertEqual(ruta.read_text(), antes)
            self.assertEqual(config.cargar(ruta).terminal.columnas, 120)

    def test_guardar_y_borrar_en_el_archivo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "config.toml"
            ruta.write_text(f'raiz = "{d}"\n# mi config\n[terminal]\ncolumnas = 120\n')
            modos.guardar(ruta, "lectura", {"barra": "plegada", "pantalla_completa": True}, "lectura")
            modos.guardar(ruta, "lectura", {"barra": "oculta"}, base="todo")  # reemplaza la tabla entera
            c = config.cargar(ruta)
            self.assertEqual(c.modos["lectura"]["valores"], {"barra": "oculta"})
            self.assertEqual(c.modos["lectura"]["base"], "todo")
            # guardar «estandar» (una página de antes) es guardar «tactica», y la tabla vieja se va
            ruta.write_text(ruta.read_text() + '[modos.estandar]\nbarra = "plegada"\n')
            modos.guardar(ruta, "estandar", {"barra": "oculta"})
            texto = ruta.read_text()
            self.assertNotIn("modos.estandar", texto)
            self.assertEqual(config.cargar(ruta).modos["tactica"]["valores"], {"barra": "oculta"})
            self.assertTrue(modos.borrar(ruta, "tactica"))
            self.assertIn("# mi config", ruta.read_text())
            self.assertTrue(modos.borrar(ruta, "lectura"))
            self.assertNotIn("modos.lectura", ruta.read_text())
            self.assertFalse(modos.borrar(ruta, "lectura"))
            self.assertEqual(config.cargar(ruta).terminal.columnas, 120)


class LaApi(Prueba):
    def setUp(self):
        super().setUp()
        if not HAY_SERVE:
            self.skipTest("sin el extra «serve»")
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self._tmp.name) / "config.toml"
        self.ruta.write_text(f'raiz = "{self._tmp.name}"\n')
        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=config.cargar(self.ruta))
        self.addCleanup(api.app.dependency_overrides.clear)

    def tearDown(self):
        self._tmp.cleanup()
        super().tearDown()

    def test_ver_guardar_y_borrar(self):
        c = TestClient(api.app)
        d = c.get("/modos").json()
        self.assertIn("barra", [a["clave"] for a in d["catalogo"]])
        self.assertEqual([m["clave"] for m in d["modos"]], ["tactica", "estrategia", "foco", "todo"])
        r = c.put("/modos/lectura", json={"valores": {"barra": "plegada", "fondo": "ninguno"}, "nombre": "lectura"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("lectura", [m["clave"] for m in r.json()["modos"]])
        self.assertEqual(c.put("/modos/lectura", json={"valores": {"barra": "rara"}}).status_code, 422)
        self.assertEqual(c.delete("/modos/lectura").status_code, 200)
        self.assertEqual(c.delete("/modos/lectura").status_code, 404)

    def test_ajustar_los_agentes_de_un_modo(self):
        c = TestClient(api.app)
        r = c.patch("/modos/foco", json={"valores": {"agentes": "vigia"}})
        self.assertEqual(r.status_code, 200)
        m = {x["clave"]: x for x in r.json()["modos"]}
        self.assertEqual((m["foco"]["valores"]["agentes"], m["foco"]["valores"]["barra"], m["tactica"]["valores"]["agentes"]),
                         ("vigia", "oculta", ""), "solo esa línea: lo demás de foco sigue siendo de fábrica")
        self.assertEqual(config.cargar(self.ruta).modos["foco"]["valores"], {"agentes": "vigia"})
        self.assertEqual(c.patch("/modos/foco", json={"valores": {"agentes": "-, vigia"}}).status_code, 422)
        self.assertEqual(c.patch("/modos/lectura", json={"valores": {"agentes": "vigia"}}).status_code, 404)
        r = c.patch("/modos/foco", json={"agentes": "otro"})
        self.assertEqual(r.status_code, 422, "suelto, fuera de «valores», no se ignora")
        self.assertIn("dentro de «valores»", r.text)
        self.assertEqual(config.cargar(self.ruta).modos["foco"]["valores"], {"agentes": "vigia"})
        r = c.patch("/modos/foco", json={"valores": {"agentes": ""}})
        self.assertFalse(next(x for x in r.json()["modos"] if x["clave"] == "foco")["cambiado"])

    def test_ajustar_las_pestanas_de_un_modo(self):
        c = TestClient(api.app)
        r = c.patch("/modos/foco", json={"valores": {"filas": "calendario, ahora"}})
        self.assertEqual(r.status_code, 200)
        m = {x["clave"]: x for x in r.json()["modos"]}
        self.assertEqual((m["foco"]["valores"]["filas"], m["foco"]["propios"], m["foco"]["heredados"]),
                         ("calendario, ahora", ["filas"], {"filas": "tactica, calendario"}))
        self.assertEqual(config.cargar(self.ruta).modos["foco"]["valores"], {"filas": "calendario, ahora"})
        # una pestaña que no hay no se escribe: 422 con las que hay
        r = c.patch("/modos/foco", json={"valores": {"filas": "calendario, bloque:nada"}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("bloque:nada", r.text)
        self.assertIn("las que hay", r.text)
        self.assertEqual(c.patch("/modos/foco", json={"valores": {"filas": ""}}).status_code, 422, "al menos una")
        self.assertEqual(c.patch("/modos/lectura", json={"valores": {"filas": "ahora"}}).status_code, 404)
        self.assertEqual(config.cargar(self.ruta).modos["foco"]["valores"], {"filas": "calendario, ahora"})
        # null quita la línea: foco vuelve a heredar las de táctica, y sin nada más, a ser el de fábrica
        r = c.patch("/modos/foco", json={"valores": {"filas": None}})
        foco = next(x for x in r.json()["modos"] if x["clave"] == "foco")
        self.assertEqual((foco["valores"]["filas"], foco["cambiado"]), ("tactica, calendario", False))
        self.assertNotIn("modos.foco", self.ruta.read_text())
