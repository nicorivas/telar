"""⚙ mundos (telar.mundos, `GET`/`PUT`/`PATCH`/`DELETE /mundos`): ver los mundos con lo suyo y de qué mundo es cada agente
y por qué, y cambiarlos en el archivo línea por línea, con la misma validación que al leer la configuración: un área,
una ruta o una etiqueta en dos mundos no se escribe, y se dice de cuál ya es."""

from __future__ import annotations

import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import mundos

ARCHIVO = """# mi configuración
raiz = "{raiz}"
estado = "{estado}"

[agentes]
carpeta = "agentes"

[mundos]
fuera = "personal"

# lo de la oficina
[mundos.trabajo]
rutas = ["empresa/", "agentes/oficina/"]
etiquetas = ["trabajo"]
horario = "lun-vie 9:00-19:00"   # el de siempre

[mundos.personal]
rutas = ["casa/"]
areas = ["personal"]
color = "verde"

# los hilos
[hilos]
directorios = ["empresa"]
"""


class Base(Prueba):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        raiz = Path(self._tmp.name)
        for agente in ("oficina", "huerta", "suelto"):
            (raiz / "agentes" / agente).mkdir(parents=True)
            (raiz / "agentes" / agente / "CLAUDE.md").write_text(f"# {agente}\n")
        self.ruta = raiz / "config.toml"
        self.ruta.write_text(ARCHIVO.format(raiz=raiz, estado=raiz / "estado"))

    def leer(self) -> dict:
        return tomllib.loads(self.ruta.read_text())["mundos"]

    def config(self) -> cfg.Config:
        return cfg.cargar(self.ruta)


class LoQueSeVe(Base):
    def test_cada_mundo_con_lo_suyo_y_el_color_que_declara(self):
        d = mundos.para_la_configuracion(self.config(), etiquetas={})
        self.assertEqual([m["nombre"] for m in d["mundos"]], ["trabajo", "personal"])
        trabajo, personal = d["mundos"]
        self.assertEqual((trabajo["color"], trabajo["color_propio"]), ("cian", ""), "por orden: no lo declara")
        self.assertEqual((personal["color"], personal["color_propio"]), ("verde", "verde"))
        self.assertEqual(trabajo["horario"][0]["texto"], "lun-vie 9:00-19:00")
        self.assertEqual(d["fuera"], "personal")
        self.assertIn("violeta", d["tintas"])
        self.assertEqual((trabajo["tema"], personal["tema"]), ("", ""), "sin tema: el del modo")
        self.assertIn("brasa", d["temas"])

    def test_cada_agente_con_su_mundo_y_por_que(self):
        """Por su carpeta (la ruta declarada que calza, como se escribió) o por una etiqueta de su hilo, que le gana; sin
        nada, sin clasificar."""
        d = mundos.para_la_configuracion(self.config(), etiquetas={"Huerta": ("trabajo", "jardin")})
        por = {a["clave"]: (a["mundo"], a["por"], a["valor"]) for a in d["agentes"]}
        self.assertEqual(por, {"oficina": ("trabajo", "ruta", "agentes/oficina/"),
                               "huerta": ("trabajo", "etiqueta", "trabajo"),
                               "suelto": ("", "", "")})
        self.assertEqual(next(a for a in d["agentes"] if a["clave"] == "oficina")["carpeta"], "agentes/oficina/")

    def test_la_ruta_que_lo_dice_es_la_mas_larga(self):
        c = self.config()
        self.assertEqual(mundos.ruta_que_calza(c, "agentes/oficina/notas"), ("trabajo", "agentes/oficina/"))
        self.assertEqual(mundos.ruta_que_calza(c, "casa"), ("personal", "casa/"))
        self.assertEqual(mundos.ruta_que_calza(c, "otra/cosa"), ("", ""))
        self.assertEqual(mundos.de_ruta(c, "empresa/x"), "trabajo")

    def test_sin_mundos_ni_agentes(self):
        self.ruta.write_text(f'raiz = "{self._tmp.name}"\n[agentes]\ncarpeta = "agentes"\n')
        d = mundos.para_la_configuracion(self.config(), etiquetas={})
        self.assertEqual((d["mundos"], d["fuera"], d["agentes"]), ([], "", []))


class Cambiarlos(Base):
    def test_ajustar_escribe_solo_esas_lineas(self):
        antes = self.ruta.read_text()
        mundos.ajustar(self.ruta, "trabajo", {"horario": "lun-vie 9-13; lun-vie 14-18", "color": "azul"})
        despues = self.ruta.read_text()
        self.assertEqual(self.leer()["trabajo"]["horario"], ["lun-vie 9-13", "lun-vie 14-18"])
        self.assertEqual(self.leer()["trabajo"]["color"], "azul")
        self.assertEqual(self.leer()["personal"], tomllib.loads(antes)["mundos"]["personal"])
        for linea in ("# mi configuración", "# lo de la oficina", "# los hilos", 'directorios = ["empresa"]'):
            self.assertIn(linea, despues)
        self.assertEqual(len(despues.splitlines()), len(antes.splitlines()) + 1, "una línea cambia y otra se suma")

    def test_el_tema_de_un_mundo(self):
        """Un tema de la página (telar.modos.TEMAS) se escribe en su línea; vacío la quita (vuelve el del modo)."""
        mundos.ajustar(self.ruta, "personal", {"tema": " brasa "})
        self.assertEqual(self.leer()["personal"]["tema"], "brasa")
        self.assertEqual(self.config().mundos[1].tema, "brasa")
        self.assertEqual(mundos.para_la_pagina(self.config())[1]["tema"], "brasa")
        mundos.ajustar(self.ruta, "personal", {"tema": ""})
        self.assertNotIn("tema", self.leer()["personal"])
        self.assertEqual(self.config().mundos[1].tema, "")

    def test_los_modos_de_un_mundo(self):
        """Los modos que tiene un mundo, en su orden (el primero es al que entra la página), con los nombres de antes
        pasados a los de ahora; uno propio de `[modos]` también vale. Vacío quita la línea: los tiene todos."""
        mundos.ajustar(self.ruta, "personal", {"modos": [" todo ", "foco", "todo"]})
        self.assertEqual(self.leer()["personal"]["modos"], ["todo", "foco"])
        self.assertEqual(self.config().mundos[1].modos, ("todo", "foco"))
        self.assertEqual(self.config().mundos[0].modos, (), "sin la línea: todos")
        self.assertEqual(mundos.para_la_pagina(self.config())[1]["modos"], ["todo", "foco"])
        mundos.ajustar(self.ruta, "trabajo", {"modos": "estandar, estrategia"})
        self.assertEqual(self.leer()["trabajo"]["modos"], ["tactica", "estrategia"])
        with self.ruta.open("a") as f:
            f.write('\n[modos.lectura]\nbase = "foco"\n')
        mundos.ajustar(self.ruta, "personal", {"modos": ["lectura", "todo"]})
        self.assertEqual(self.config().mundos[1].modos, ("lectura", "todo"))
        d = mundos.para_la_configuracion(self.config(), etiquetas={})
        self.assertEqual([m["clave"] for m in d["modos"]], ["tactica", "estrategia", "foco", "todo", "lectura"])
        mundos.ajustar(self.ruta, "personal", {"modos": []})
        self.assertNotIn("modos", self.leer()["personal"])
        self.assertEqual(self.config().mundos[1].modos, ())

    def test_un_modo_que_no_existe_no_se_escribe(self):
        antes = self.ruta.read_text()
        with self.assertRaises(cfg.ErrorDeConfig) as e:
            mundos.ajustar(self.ruta, "personal", {"modos": ["todo", "lectura"]})
        self.assertIn("mundos.personal.modos: «lectura» no es un modo (tactica, estrategia, foco, todo)", str(e.exception))
        with self.assertRaises(cfg.ErrorDeConfig) as e:
            mundos.ajustar(self.ruta, "personal", {"modos": ["Todo"]})
        self.assertIn("no es la clave de un modo", str(e.exception))
        self.assertEqual(self.ruta.read_text(), antes)

    def test_los_modos_al_leer_la_configuracion(self):
        """En el archivo: al menos uno (sin la línea, todos) y que existan; borrar un modo propio que un mundo tiene se
        niega y dice por qué."""
        texto = self.ruta.read_text()
        for linea, dice in (("modos = []", "al menos uno"), ('modos = ["todo", "nada"]', "«nada» no es un modo"),
                            ('modos = "todo"', "lista de modos")):
            with self.subTest(linea=linea):
                self.ruta.write_text(texto.replace('color = "verde"', f'color = "verde"\n{linea}'))
                with self.assertRaises(cfg.ErrorDeConfig) as e:
                    self.config()
                self.assertIn(dice, str(e.exception))
        self.ruta.write_text(texto.replace('color = "verde"', 'color = "verde"\nmodos = ["lectura"]') + '\n[modos.lectura]\nnombre = "lectura"\n')
        self.assertEqual(self.config().mundos[1].modos, ("lectura",))
        from telar import modos as mod_modos

        with self.assertRaises(cfg.ErrorDeConfig) as e:
            mod_modos.borrar(self.ruta, "lectura")
        self.assertIn("mundos.personal.modos: «lectura» no es un modo", str(e.exception))
        self.assertEqual(self.config().mundos[1].modos, ("lectura",), "no se borró")

    def test_vacio_quita_la_linea(self):
        mundos.ajustar(self.ruta, "trabajo", {"horario": "", "etiquetas": []})
        self.assertNotIn("horario", self.leer()["trabajo"])
        self.assertNotIn("etiquetas", self.leer()["trabajo"])
        self.assertEqual(self.config().mundos[0].horario, (), "sin horario: solo a mano")

    def test_las_listas_se_limpian(self):
        mundos.ajustar(self.ruta, "personal", {"areas": " personal , casa,personal,", "rutas": ["casa/", " jardin/ "]})
        self.assertEqual(self.leer()["personal"]["areas"], ["personal", "casa"])
        self.assertEqual(self.leer()["personal"]["rutas"], ["casa/", "jardin/"])

    def test_lo_de_otro_mundo_no_se_escribe_y_dice_de_cual_es(self):
        antes = self.ruta.read_text()
        choques = {"rutas": (["casa/", "empresa"], "«empresa» ya es de «trabajo»"),
                   "etiquetas": (["trabajo"], "«trabajo» ya es de «trabajo»"),
                   "areas": (["personal"], None)}
        for campo, (valor, dice) in choques.items():
            with self.subTest(campo=campo):
                if dice is None:
                    mundos.ajustar(self.ruta, "personal", {campo: valor})  # lo suyo, sí
                    continue
                with self.assertRaises(cfg.ErrorDeConfig) as e:
                    mundos.ajustar(self.ruta, "personal", {campo: valor})
                self.assertIn(f"mundos.personal.{campo}", str(e.exception))
                self.assertIn(dice, str(e.exception))
        # desde el primero de los dos, también se dice desde él
        with self.assertRaises(cfg.ErrorDeConfig) as e:
            mundos.ajustar(self.ruta, "trabajo", {"rutas": ["empresa/", "casa"]})
        self.assertIn("mundos.trabajo.rutas: «casa» ya es de «personal»", str(e.exception))
        self.assertEqual(self.ruta.read_text(), antes)

    def test_lo_que_no_sirve(self):
        antes = self.ruta.read_text()
        malos = [("trabajo", "color", "naranjo", "mundos.trabajo.color"),
                 ("trabajo", "tema", "noche", "mundos.trabajo.tema"),
                 ("trabajo", "tema", ["brasa"], "se esperaba un texto"),
                 ("trabajo", "horario", "lunes a viernes", "mundos.trabajo.horario"),
                 ("trabajo", "rutas", ["../afuera/"], "no puede subir"),
                 ("trabajo", "lugares", ["x"], "no existe"),
                 ("trabajo", "areas", 3, "lista de textos")]
        for nombre, campo, valor, dice in malos:
            with self.subTest(campo=campo), self.assertRaises(cfg.ErrorDeConfig) as e:
                mundos.ajustar(self.ruta, nombre, {campo: valor})
            self.assertIn(dice, str(e.exception))
        with self.assertRaises(KeyError):
            mundos.ajustar(self.ruta, "casa", {"color": "azul"})
        self.assertEqual(self.ruta.read_text(), antes)

    def test_fuera(self):
        mundos.poner_fuera(self.ruta, "trabajo")
        self.assertEqual(self.leer()["fuera"], "trabajo")
        mundos.poner_fuera(self.ruta, "")
        self.assertNotIn("fuera", self.leer())
        with self.assertRaises(cfg.ErrorDeConfig) as e:
            mundos.poner_fuera(self.ruta, "casa")
        self.assertIn("trabajo, personal", str(e.exception))

    def test_crear_uno_va_despues_del_ultimo(self):
        mundos.crear(self.ruta, "estudio")
        texto = self.ruta.read_text()
        self.assertEqual(list(self.leer()), ["fuera", "trabajo", "personal", "estudio"])
        self.assertLess(texto.index("[mundos.estudio]"), texto.index("# los hilos"), "antes del comentario de la tabla que sigue")
        self.assertEqual(self.config().mundos[2].nombre, "estudio")
        mundos.ajustar(self.ruta, "estudio", {"etiquetas": ["estudio"]})
        self.assertEqual(self.config().mundos[2].etiquetas, ("estudio",))
        with self.assertRaises(FileExistsError):
            mundos.crear(self.ruta, "estudio")
        for malo in ("sin-clasificar", "mi mundo", "a.b", "fuera", "", 'x"y'):
            with self.subTest(malo=malo), self.assertRaises(cfg.ErrorDeConfig):
                mundos.crear(self.ruta, malo)

    def test_crear_el_primero(self):
        self.ruta.write_text(f'raiz = "{self._tmp.name}"\n\n')
        mundos.crear(self.ruta, "trabajo")
        self.assertEqual(self.ruta.read_text(), f'raiz = "{self._tmp.name}"\n\n[mundos.trabajo]\n')
        self.assertEqual([m.nombre for m in self.config().mundos], ["trabajo"])

    def test_borrar_uno_tambien_quita_fuera_si_era_el(self):
        self.assertTrue(mundos.borrar(self.ruta, "personal"))
        self.assertEqual(list(self.leer()), ["trabajo"])
        self.assertEqual(self.config().mundos_fuera, "")
        self.assertIn("# los hilos", self.ruta.read_text())
        self.assertFalse(mundos.borrar(self.ruta, "personal"))
        self.assertTrue(mundos.borrar(self.ruta, "trabajo"))
        self.assertEqual(self.config().mundos, ())


class LaApi(Base):
    def setUp(self):
        super().setUp()
        if not HAY_FASTAPI:
            self.skipTest("sin el extra «serve»")
        from fastapi.testclient import TestClient

        from telar import api

        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg.cargar(self.ruta))
        self.addCleanup(api.app.dependency_overrides.clear)
        self.c = TestClient(api.app)

    def test_ver(self):
        d = self.c.get("/mundos").json()
        self.assertEqual([m["nombre"] for m in d["mundos"]], ["trabajo", "personal"])
        self.assertEqual({a["clave"]: a["mundo"] for a in d["agentes"]}, {"oficina": "trabajo", "huerta": "", "suelto": ""})

    def test_patch_escribe_solo_lo_que_se_le_da(self):
        r = self.c.patch("/mundos/trabajo", json={"valores": {"color": "violeta"}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["mundos"][0]["color"], "violeta", "devuelve lo que quedó escrito")
        self.assertEqual(self.leer()["trabajo"]["horario"], "lun-vie 9:00-19:00")
        r = self.c.patch("/mundos/personal", json={"valores": {"rutas": ["casa/", "empresa/"]}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("«empresa/» ya es de «trabajo»", r.json()["detail"])
        self.assertEqual(self.c.patch("/mundos/casa", json={"valores": {"color": "azul"}}).status_code, 404)
        self.assertEqual(self.c.patch("/mundos/trabajo", json={"valores": {"color": "naranjo"}}).status_code, 422)
        r = self.c.patch("/mundos/trabajo", json={"valores": {"color": None}})
        self.assertEqual(r.json()["mundos"][0]["color_propio"], "")
        r = self.c.patch("/mundos/personal", json={"valores": {"tema": "ambar"}})
        self.assertEqual((r.status_code, r.json()["mundos"][1]["tema"]), (200, "ambar"))
        self.assertEqual(self.c.patch("/mundos/personal", json={"valores": {"tema": "noche"}}).status_code, 422)
        r = self.c.patch("/mundos/personal", json={"valores": {"tema": None}})
        self.assertEqual(r.json()["mundos"][1]["tema"], "")
        r = self.c.patch("/mundos/personal", json={"valores": {"modos": ["todo", "foco"]}})
        self.assertEqual((r.status_code, r.json()["mundos"][1]["modos"]), (200, ["todo", "foco"]))
        self.assertEqual(r.json()["mundos"][0]["modos"], [], "sin declarar: todos")
        r = self.c.patch("/mundos/personal", json={"valores": {"modos": ["todo", "lectura"]}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("«lectura» no es un modo", r.json()["detail"])
        r = self.c.patch("/mundos/personal", json={"valores": {"modos": None}})
        self.assertEqual(r.json()["mundos"][1]["modos"], [])

    def test_patch_con_los_ajustes_sueltos_se_niega_y_dice_donde_van(self):
        # antes respondía ok sin cambiar nada: pydantic ignoraba lo que no era «valores»
        antes = self.leer()
        r = self.c.patch("/mundos/personal", json={"tema": "ambar"})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn("dentro de «valores»", r.text)
        self.assertIn("tema", r.text)
        self.assertEqual(self.leer(), antes)

    def test_fuera_crear_y_borrar(self):
        self.assertEqual(self.c.patch("/mundos", json={"fuera": "trabajo"}).json()["fuera"], "trabajo")
        self.assertEqual(self.c.patch("/mundos", json={"fuera": "casa"}).status_code, 422)
        r = self.c.put("/mundos/estudio")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([m["nombre"] for m in r.json()["mundos"]], ["trabajo", "personal", "estudio"])
        self.assertEqual(self.c.put("/mundos/estudio").status_code, 409)
        self.assertEqual(self.c.put("/mundos/sin-clasificar").status_code, 422)
        r = self.c.delete("/mundos/trabajo")
        self.assertEqual((r.status_code, r.json()["fuera"]), (200, ""))
        self.assertEqual(self.c.delete("/mundos/trabajo").status_code, 404)


class FueraDeSuMundo(Base):
    """Qué pasa con un agente fuera de su mundo (`fuera_de_su_mundo` en su agente.toml): al-final (el de fábrica),
    esconder o ver. Se pidió el 23-nov para un agente del mundo personal: «debería ser una configuración posible, no algo que se
    haga en código». Se lee, viaja en `GET /mundos`, en las secciones de `telar config` y en la foto de la máquina, y ⚙
    mundos lo escribe (`PUT /mundos/agentes/<clave>`): solo esa línea, y se sube solo ese archivo."""

    def setUp(self):
        super().setUp()
        from unittest import mock

        if not HAY_FASTAPI:
            self.skipTest("sin el extra «serve»")
        from fastapi.testclient import TestClient

        from telar import api

        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg.cargar(self.ruta))
        self.addCleanup(api.app.dependency_overrides.clear)
        self.c = TestClient(api.app)
        self.raiz = self.ruta.parent
        self.toml = self.raiz / "agentes" / "huerta" / "agente.toml"
        self.toml.write_text('# la huerta\nnombre = "Huerta"\nmundo = "personal"\n\n[politica]\npermite = ["Edit"]\n')
        self.subidas = []
        p = mock.patch("telar.temas.subir_luego", side_effect=lambda config, **kw: self.subidas.append(kw))
        p.start()
        self.addCleanup(p.stop)

    def test_se_lee_y_de_fabrica_es_al_final(self):
        from telar import agentes

        self.assertEqual(agentes.FUERAS[0], "al-final")
        de = {a.clave: a.fuera_de_su_mundo for a in agentes.descubrir(self.config())}
        self.assertEqual(de, {"oficina": "al-final", "huerta": "al-final", "suelto": "al-final"})
        self.toml.write_text(self.toml.read_text().replace('mundo = "personal"\n', 'mundo = "personal"\nfuera_de_su_mundo = "esconder"\n'))
        a = next(x for x in agentes.descubrir(self.config()) if x.clave == "huerta")
        self.assertEqual((a.fuera_de_su_mundo, a.problemas), ("esconder", ()))
        self.toml.write_text('fuera_de_su_mundo = "ocultar"\n')
        valido, problemas = agentes.leer_definicion(self.toml.parent)
        self.assertNotIn("fuera_de_su_mundo", valido)
        self.assertIn("al-final, esconder, ver", problemas[0])

    def test_poner_toca_solo_esa_linea(self):
        from telar import agentes

        antes = self.toml.read_text()
        agentes.poner_fuera(self.toml.parent, "esconder")
        self.assertEqual(self.toml.read_text(), antes.replace('mundo = "personal"\n', 'mundo = "personal"\nfuera_de_su_mundo = "esconder"\n'))
        agentes.poner_fuera(self.toml.parent, "ver")
        self.assertEqual(self.toml.read_text().count("fuera_de_su_mundo"), 1)
        self.assertIn('fuera_de_su_mundo = "ver"', self.toml.read_text())
        agentes.poner_fuera(self.toml.parent, "al-final")
        self.assertEqual(self.toml.read_text(), antes, "el de fábrica quita la línea")
        # sin `mundo =`: antes de la primera tabla; sin archivo, lo crea
        sin = self.raiz / "agentes" / "oficina"
        (sin / "agente.toml").write_text('nombre = "Oficina"\n\n[politica]\nniega = ["Bash"]\n')
        agentes.poner_fuera(sin, "ver")
        self.assertEqual(tomllib.loads((sin / "agente.toml").read_text())["fuera_de_su_mundo"], "ver")
        self.assertEqual(tomllib.loads((sin / "agente.toml").read_text())["politica"], {"niega": ["Bash"]})
        agentes.poner_fuera(self.raiz / "agentes" / "suelto", "esconder")
        self.assertEqual((self.raiz / "agentes" / "suelto" / "agente.toml").read_text(), 'fuera_de_su_mundo = "esconder"\n')
        with self.assertRaises(ValueError):
            agentes.poner_fuera(sin, "ocultar")

    def test_la_api_lo_escribe_y_lo_sube(self):
        r = self.c.put("/mundos/agentes/huerta", json={"fuera_de_su_mundo": "esconder"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual({a["clave"]: a["fuera_de_su_mundo"] for a in r.json()["agentes"]}["huerta"], "esconder",
                         "devuelve lo que quedó escrito")
        self.assertEqual(tomllib.loads(self.toml.read_text())["fuera_de_su_mundo"], "esconder")
        self.assertEqual(len(self.subidas), 1)
        self.assertEqual(self.subidas[0]["archivo"], self.toml, "solo ese archivo")
        self.assertIn("huerta fuera de su mundo, esconder", self.subidas[0]["mensaje"])
        self.assertEqual(self.c.put("/mundos/agentes/huerta", json={"fuera_de_su_mundo": "ocultar"}).status_code, 422)
        self.assertEqual(self.c.put("/mundos/agentes/nadie", json={"fuera_de_su_mundo": "ver"}).status_code, 404)

    def test_viaja_en_las_secciones_y_en_la_foto(self):
        from telar import espejo
        from telar import agentes
        from telar.servicios import config as servicio

        agentes.poner_fuera(self.toml.parent, "esconder")
        c = self.config()
        secciones = {s["clave"]: s for s in servicio._agentes(c)}
        self.assertEqual(secciones["agente:huerta"]["fuera_de_su_mundo"], "esconder")
        self.assertEqual(secciones["agente:oficina"]["fuera_de_su_mundo"], "al-final")
        foto = {a["clave"]: a for a in espejo.agentes_de(c)}
        self.assertEqual(foto["huerta"]["fuera_de_su_mundo"], "esconder")
        limpia = espejo.validar({"version": espejo.VERSION, "maquina": "otra", "hilos": [], "agentes": [
            {"clave": "cocina", "nombre": "Cocina", "mundo": "personal", "fuera_de_su_mundo": "esconder"},
            {"clave": "raro", "nombre": "Raro", "mundo": "", "fuera_de_su_mundo": "<script>"}]}, "otra")
        self.assertEqual([a.get("fuera_de_su_mundo") for a in limpia["agentes"]], ["esconder", None], "lo que no se entiende no viaja")
