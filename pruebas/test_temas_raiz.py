"""Los temas en la raíz (`<raiz>/.telar/temas.toml`, telar.temas): valen en todas las máquinas. Se leen con la configuración
(de fábrica < la raíz < la configuración de la máquina, que pisa color por color), ⚙ temas escribe en la raíz y saca de la
máquina lo que lo taparía, lo escrito se commitea solo (ese archivo, nada más) y se sube, y `telar temas migrar` pasa los
`[temas.*]` de una máquina a la raíz con respaldo, sin cambiar lo que se ve. Un tema propio que se borró en la raíz desde la
otra máquina no tumba la configuración de esta: se tolera al cargar y doctor lo dice."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import temas

MAQUINA = """# la configuración de esta máquina
raiz = "{raiz}"
estado = "{estado}"

[temas.brasa]
azul = "#7dae9a"   # salvia, solo aquí
"""

EN_RAIZ = """# los de la raíz
[temas.brasa]
azul = "#111111"
violeta = "#cc99aa"

[temas.noche]
base = "rescoldo"
bg = "#101418"
"""


def sh(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout


class Base(Prueba):
    def setUp(self):
        super().setUp()
        self.raiz = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.raiz, ignore_errors=True)
        self.ruta = self.raiz / "config" / "config.toml"
        self.ruta.parent.mkdir()
        self.ruta.write_text(MAQUINA.format(raiz=self.raiz, estado=self.raiz / "estado"))
        self.archivo = self.raiz / ".telar" / "temas.toml"
        self.archivo.parent.mkdir()
        self.archivo.write_text(EN_RAIZ)

    def config(self) -> cfg.Config:
        return cfg.cargar(self.ruta)

    def de(self, archivo: Path) -> dict:
        return tomllib.loads(archivo.read_text()).get("temas", {}) if archivo.exists() else {}


class Leerlos(Base):
    def test_la_raiz_debajo_y_la_maquina_pisa_color_por_color(self):
        c = self.config()
        self.assertEqual(c.temas_archivo, self.archivo)
        self.assertEqual(c.temas["brasa"], {"azul": "#7dae9a", "violeta": "#cc99aa"}, "azul de la máquina, violeta de la raíz")
        self.assertEqual(c.temas["noche"], {"base": "rescoldo", "bg": "#101418"})
        self.assertEqual(c.temas_donde["brasa"], {"raiz": ("azul", "violeta"), "maquina": ("azul",)})
        d = {t["clave"]: t for t in temas.para_la_configuracion(c)["temas"]}
        self.assertEqual((d["brasa"]["vive"], d["brasa"]["en_raiz"], d["brasa"]["en_maquina"]), ("mixto", ["violeta"], ["azul"]))
        self.assertEqual((d["noche"]["vive"], d["noche"]["en_raiz"]), ("raiz", ["bg"]))
        self.assertEqual(d["telar"]["vive"], "")
        self.assertEqual(temas.para_la_configuracion(c)["raiz"], str(self.archivo))

    def test_la_maquina_pisa_uno_propio_de_la_raiz_sin_repetir_su_base(self):
        cfg.escribir_clave("temas.noche", "fg", "#eeeeee", self.ruta)
        self.assertEqual(self.config().temas["noche"], {"base": "rescoldo", "bg": "#101418", "fg": "#eeeeee"})

    def test_un_mundo_y_un_modo_nombran_uno_de_la_raiz(self):
        cfg.escribir_clave("mundos.personal", "tema", "noche", self.ruta)
        cfg.escribir_clave("modos.lectura", "tema", "noche", self.ruta)
        self.assertEqual(self.config().mundos[0].tema, "noche")
        self.assertIn("noche", temas.en(self.ruta))

    def test_sin_raiz_todo_en_la_maquina(self):
        c = cfg.desde_dict({"temas": {"brasa": {"azul": "#fff"}}})
        self.assertIsNone(c.temas_archivo)
        self.assertEqual(c.temas, {"brasa": {"azul": "#ffffff"}})

    def test_la_raiz_del_entorno_manda(self):
        otra = self.raiz / "otra"
        (otra / ".telar").mkdir(parents=True)
        (otra / ".telar" / "temas.toml").write_text('[temas.latte]\nazul = "#123456"\n')
        import os

        os.environ["TELAR_RAIZ"] = str(otra)
        self.addCleanup(os.environ.pop, "TELAR_RAIZ", None)
        self.assertEqual(self.config().temas["latte"], {"azul": "#123456"})

    def test_un_archivo_roto_no_tumba_nada_y_no_se_escribe_encima(self):
        self.archivo.write_text("[temas.brasa]\n<<<<<<< HEAD\nazul = 1\n")
        c = self.config()
        self.assertIn("no se lee", c.temas_error)
        self.assertEqual(c.temas, {"brasa": {"azul": "#7dae9a"}}, "queda lo de la máquina")
        antes = self.archivo.read_text()
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.cambiar(c, "brasa", {"violeta": "#abcdef"})
        self.assertEqual(self.archivo.read_text(), antes)
        self.archivo.write_text('[hilos]\ntope = 3\n')
        self.assertIn("solo lleva tablas [temas", self.config().temas_error)

    def test_uno_que_se_borro_en_la_otra_maquina_se_tolera(self):
        cfg.escribir_clave("mundos.personal", "tema", "noche", self.ruta)
        self.archivo.write_text('[temas.brasa]\nazul = "#111111"\n')   # la otra máquina borró «noche»
        c = self.config()
        self.assertEqual(c.temas_faltan, ("noche",))
        self.assertEqual(c.mundos[0].tema, "noche", "la página pone el del modo")
        # se puede seguir escribiendo otra cosa, pero no nombrar otro que no hay
        cfg.escribir_clave("mundos.personal", "color", "verde", self.ruta)
        with self.assertRaises(cfg.ErrorDeConfig):
            cfg.escribir_clave("mundos.trabajo", "tema", "otro-que-no-hay", self.ruta)
        # desde_dict, sin tolerar, lo sigue diciendo
        with self.assertRaises(cfg.ErrorDeConfig):
            cfg.desde_dict(tomllib.loads(self.ruta.read_text()), origen=self.ruta)


class Escribirlos(Base):
    def test_cambiar_escribe_en_la_raiz_y_saca_de_la_maquina_lo_que_lo_taparia(self):
        temas.cambiar(self.config(), "brasa", {"azul": "#88aa99", "amarillo": "#e5b96a"})
        self.assertEqual(self.de(self.archivo)["brasa"], {"azul": "#88aa99", "violeta": "#cc99aa", "amarillo": "#e5b96a"})
        self.assertNotIn("brasa", self.de(self.ruta), "la tabla de la máquina quedó vacía: se va")
        self.assertIn("# los de la raíz", self.archivo.read_text(), "lo demás de la raíz queda como estaba")
        self.assertEqual(self.config().temas["brasa"]["azul"], "#88aa99")

    def test_de_fabrica_sale_de_las_dos(self):
        temas.cambiar(self.config(), "brasa", {"azul": None})
        self.assertEqual(self.de(self.archivo)["brasa"], {"violeta": "#cc99aa"})
        self.assertNotIn("brasa", self.de(self.ruta))
        self.assertNotIn("azul", self.config().temas["brasa"])

    def test_uno_propio_solo_de_la_maquina_pasa_a_la_raiz_con_su_base(self):
        cfg.escribir_clave("temas.mio", "base", "latte", self.ruta)
        cfg.escribir_clave("temas.mio", "fg", "#222222", self.ruta)
        temas.cambiar(self.config(), "mio", {"bg": "#fafafa"})
        self.assertEqual(self.de(self.archivo)["mio"], {"base": "latte", "bg": "#fafafa"})
        self.assertEqual(self.de(self.ruta)["mio"], {"base": "latte", "fg": "#222222"}, "lo otro se queda aquí")
        self.assertEqual(self.config().temas["mio"], {"base": "latte", "bg": "#fafafa", "fg": "#222222"})
        temas.cambiar(self.config(), "mio", {"fg": "#333333"})
        self.assertNotIn("mio", self.de(self.ruta), "solo quedaba la misma base que dice la raíz")

    def test_un_color_que_no_sirve_no_escribe_nada(self):
        antes = (self.archivo.read_text(), self.ruta.read_text())
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.cambiar(self.config(), "brasa", {"azul": "salvia"})
        with self.assertRaises(KeyError):
            temas.cambiar(self.config(), "neon", {"azul": "#fff"})
        self.assertEqual((self.archivo.read_text(), self.ruta.read_text()), antes)

    def test_sin_archivo_de_la_raiz_lo_crea_con_su_cabeza(self):
        self.archivo.unlink()
        temas.cambiar(self.config(), "latte", {"azul": "#3366aa"})
        self.assertTrue(self.archivo.read_text().startswith("# Los temas de telar que valen en todas las máquinas"))
        self.assertEqual(self.de(self.archivo), {"latte": {"azul": "#3366aa"}})

    def test_nuevo_en_la_raiz_y_copia_de_uno_propio(self):
        self.assertEqual(temas.nuevo(self.config(), "dia", "latte"), {"base": "latte"})
        self.assertEqual(self.de(self.archivo)["dia"], {"base": "latte"})
        temas.nuevo(self.config(), "noche-2", "noche")
        self.assertEqual(self.de(self.archivo)["noche-2"], {"base": "rescoldo", "bg": "#101418"})
        with self.assertRaises(FileExistsError):
            temas.nuevo(self.config(), "noche", "latte")
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.nuevo(self.config(), "brasa", "latte")
        self.assertNotIn("dia", self.de(self.ruta), "nada en la máquina")

    def test_quitar_de_las_dos_y_lo_puesto_no(self):
        self.assertTrue(temas.quitar(self.config(), "brasa"))
        self.assertNotIn("brasa", self.de(self.archivo))
        self.assertNotIn("brasa", self.de(self.ruta))
        self.assertFalse(temas.quitar(self.config(), "brasa"))
        cfg.escribir_clave("mundos.personal", "tema", "noche", self.ruta)
        with self.assertRaises(temas.EnUso):
            temas.quitar(self.config(), "noche")
        self.assertIn("noche", self.de(self.archivo))
        cfg.escribir_clave("mundos.personal", "tema", None, self.ruta)
        cfg.escribir_clave("temas.noche", "fg", "#eeeeee", self.ruta)   # y la máquina lo pisaba
        self.assertTrue(temas.quitar(self.config(), "noche"))
        self.assertNotIn("noche", self.de(self.archivo))
        self.assertNotIn("noche", self.de(self.ruta))

    def test_sin_raiz_todo_en_la_maquina_como_antes(self):
        texto = self.ruta.read_text().replace(f'raiz = "{self.raiz}"\n', "")
        self.ruta.write_text(texto)
        c = self.config()
        self.assertIsNone(c.temas_archivo)
        temas.cambiar(c, "brasa", {"violeta": "#abcdef"})
        self.assertEqual(self.de(self.ruta)["brasa"], {"azul": "#7dae9a", "violeta": "#abcdef"})
        self.assertNotIn("abcdef", self.archivo.read_text())


class LaApi(Base):
    def setUp(self):
        super().setUp()
        if not HAY_FASTAPI:
            self.skipTest("sin el extra «serve»")
        from fastapi.testclient import TestClient

        from telar import api

        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg.cargar(self.ruta))
        self.addCleanup(api.app.dependency_overrides.clear)
        self.subidos = []
        viejo = temas.subir_luego
        temas.subir_luego = lambda config, **_: self.subidos.append(config.temas_archivo)
        self.addCleanup(setattr, temas, "subir_luego", viejo)
        self.c = TestClient(api.app)

    def test_patch_en_la_raiz_y_dice_donde_vive(self):
        r = self.c.patch("/temas/brasa", json={"valores": {"azul": "#88AA99"}})
        self.assertEqual(r.status_code, 200, r.text)
        brasa = next(t for t in r.json()["temas"] if t["clave"] == "brasa")
        self.assertEqual((brasa["vive"], brasa["en_raiz"], brasa["en_maquina"]), ("raiz", ["azul", "violeta"], []))
        self.assertEqual(self.de(self.archivo)["brasa"]["azul"], "#88aa99")
        self.assertEqual(r.json()["raiz"], str(self.archivo))
        self.assertEqual(self.subidos, [self.archivo], "lo escrito se sube")

    def test_put_y_delete_en_la_raiz(self):
        self.assertEqual(self.c.put("/temas/dia", json={"base": "latte"}).status_code, 200)
        self.assertIn("dia", self.de(self.archivo))
        self.assertEqual(self.c.delete("/temas/dia").status_code, 200)
        self.assertNotIn("dia", self.de(self.archivo))
        self.assertEqual(len(self.subidos), 2)

    def test_lo_que_no_se_escribe_no_se_sube(self):
        self.assertEqual(self.c.patch("/temas/brasa", json={"valores": {"azul": "salvia"}}).status_code, 422)
        self.assertEqual(self.subidos, [])


class Migrar(Base):
    def setUp(self):
        super().setUp()
        self.ruta.write_text(MAQUINA.format(raiz=self.raiz, estado=self.raiz / "estado")
                             + 'violeta = "#d19fb6"\n\n[temas.mio]\nbase = "latte"\nbg = "#FAFAFA"\n\n'
                             + '[temas.noche]\nbase = "brasa"\n\n[mundos.personal]\ntema = "mio"\n')
        self.archivo.write_text('[temas.brasa]\nazul = "#7dae9a"\nvioleta = "#cc99aa"\n\n'
                             '[temas.noche]\nbase = "rescoldo"\n')

    def test_ver_no_escribe(self):
        antes = (self.ruta.read_text(), self.archivo.read_text())
        plan = temas.migrar(self.config(), ver=True)
        self.assertEqual([(p["tema"], p["clave"]) for p in plan["pasan"]], [("mio", "base"), ("mio", "bg")])
        self.assertEqual([(p["tema"], p["clave"]) for p in plan["iguales"]], [("brasa", "azul")])
        self.assertEqual({(p["tema"], p["clave"]) for p in plan["quedan"]}, {("brasa", "violeta"), ("noche", "base")})
        self.assertFalse(plan["escrito"])
        self.assertEqual((self.ruta.read_text(), self.archivo.read_text()), antes)

    def test_pasa_lo_que_falta_y_deja_lo_distinto_sin_cambiar_lo_que_se_ve(self):
        original = self.ruta.read_text()
        antes = self.config().temas
        plan = temas.migrar(self.config())
        self.assertTrue(plan["escrito"])
        self.assertEqual(Path(plan["respaldo"]).read_text(), original, "el respaldo es la configuración de antes")
        self.assertTrue(plan["respaldo"].startswith(str(self.ruta) + ".antes-de-temas-en-raiz-"))
        self.assertEqual(self.config().temas, antes, "se ve lo mismo")
        self.assertEqual(self.de(self.archivo)["mio"], {"base": "latte", "bg": "#fafafa"})
        aqui = self.de(self.ruta)
        self.assertEqual(aqui["brasa"], {"violeta": "#d19fb6"}, "lo distinto se queda; lo igual sale")
        self.assertEqual(aqui["noche"], {"base": "brasa"}, "otra base: entero en la máquina")
        self.assertNotIn("mio", aqui)
        self.assertEqual(self.config().mundos[0].tema, "mio", "el mundo lo sigue teniendo, ahora de la raíz")
        # otra vez: ya no pasa nada
        plan = temas.migrar(self.config())
        self.assertEqual((plan["pasan"], plan["iguales"], plan["escrito"]), ([], [], False))

    def test_sin_raiz_no_hay_adonde(self):
        self.ruta.write_text('[temas.brasa]\nazul = "#7dae9a"\n')
        with self.assertRaises(cfg.ErrorDeConfig):
            temas.migrar(self.config())


@unittest.skipUnless(shutil.which("git"), "sin git")
class Git(Base):
    """Commitear solo el archivo de la raíz, subirlo, y que la otra máquina lo lea al traer lo de arriba."""

    def setUp(self):
        super().setUp()
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        origen = self.base / "origen.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origen)], check=True)
        self.a, self.b = self.base / "laptop", self.base / "servidor"
        for c in (self.a, self.b):
            subprocess.run(["git", "clone", "-q", str(origen), str(c)], check=True, capture_output=True)
            sh(c, "config", "user.email", "x@x"), sh(c, "config", "user.name", "x")
            sh(c, "checkout", "-q", "-b", "main")
        (self.a / "diario.md").write_text("hoy\n")
        sh(self.a, "add", "."), sh(self.a, "commit", "-qm", "inicio"), sh(self.a, "push", "-q", "-u", "origin", "main")
        sh(self.b, "pull", "-q", "origin", "main"), sh(self.b, "branch", "-q", "-u", "origin/main")
        # la configuración de cada máquina, fuera del repositorio, con la raíz en su copia
        self.cfg_a, self.cfg_b = self.base / "cfg-a.toml", self.base / "cfg-b.toml"
        self.cfg_a.write_text(f'raiz = "{self.a}"\nestado = "{self.base / "estado-a"}"\n')
        self.cfg_b.write_text(f'raiz = "{self.b}"\nestado = "{self.base / "estado-b"}"\n')

    def test_commitea_solo_ese_archivo_y_lo_sube(self):
        (self.a / "diario.md").write_text("a medias, de otro\n")
        (self.a / "suelto.md").write_text("de otro\n")
        temas.cambiar(cfg.cargar(self.cfg_a), "brasa", {"azul": "#88aa99"})
        res = temas.subir(cfg.cargar(self.cfg_a).temas_archivo, estado=self.base / "estado-a")
        self.assertEqual(res.estado, "subido", res.detalle)
        self.assertEqual(sh(self.a, "show", "--name-only", "--format=", "HEAD").split(), [".telar/temas.toml"])
        estado = sh(self.a, "status", "--porcelain")
        self.assertIn(" M diario.md", estado, "lo de otros queda como estaba")
        self.assertIn("?? suelto.md", estado)
        self.assertIn("temas.toml", (self.base / "estado-a" / "commits.log").read_text())
        # la otra máquina, al traer lo de arriba, lo lee
        self.assertEqual(cfg.cargar(self.cfg_b).temas, {})
        sh(self.b, "pull", "-q")
        self.assertEqual(cfg.cargar(self.cfg_b).temas, {"brasa": {"azul": "#88aa99"}})

    def test_subir_luego_junta_varios_cambios_en_un_commit(self):
        for color in ("#111111", "#222222", "#333333"):
            temas.cambiar(cfg.cargar(self.cfg_a), "brasa", {"azul": color})
            temas.subir_luego(cfg.cargar(self.cfg_a), espera=0.3)
        limite = time.time() + 20
        while time.time() < limite and "temas" not in sh(self.a, "log", "-1", "--format=%s"):
            time.sleep(0.1)
        time.sleep(0.5)
        self.assertEqual(sh(self.a, "log", "--format=%s").count("temas:"), 1)
        self.assertEqual(sh(self.a, "status", "--porcelain", "--", ".telar"), "")
        self.assertIn("#333333", sh(self.a, "show", "origin/main:.telar/temas.toml"))

    def test_fuera_de_git_no_hace_nada(self):
        self.assertIsNone(temas.subir(self.archivo))

    def test_atrasado_si_arriba_cambio(self):
        temas.cambiar(cfg.cargar(self.cfg_a), "brasa", {"azul": "#88aa99"})
        temas.subir(cfg.cargar(self.cfg_a).temas_archivo)
        archivo_b = self.b / ".telar" / "temas.toml"
        self.assertIn("cambió arriba", temas.atrasado(archivo_b))
        sh(self.b, "pull", "-q")
        self.assertEqual(temas.atrasado(archivo_b), "")
        self.assertEqual(temas.atrasado(self.a / ".telar" / "temas.toml"), "")

    def test_la_orden_migrar(self):
        import contextlib
        import io

        from telar.ordenes import temas as orden

        self.cfg_a.write_text(self.cfg_a.read_text() + '\n[temas.brasa]\nazul = "#7dae9a"\n')
        ctx = SimpleNamespace(config=cfg.cargar(self.cfg_a))
        with contextlib.redirect_stdout(io.StringIO()) as dicho:
            self.assertEqual(orden.main(["migrar", "--ver"], ctx), 0)
        self.assertIn("brasa.azul", dicho.getvalue())
        self.assertFalse((self.a / ".telar" / "temas.toml").exists(), "--ver no escribe")
        with contextlib.redirect_stdout(io.StringIO()) as dicho:
            self.assertEqual(orden.main(["migrar"], ctx), 0, dicho.getvalue())
        self.assertIn("subido", dicho.getvalue())
        self.assertIn('azul = "#7dae9a"', sh(self.a, "show", "origin/main:.telar/temas.toml"))
        self.assertNotIn("[temas.brasa]", self.cfg_a.read_text())
        self.assertEqual(len(list(self.base.glob("cfg-a.toml.antes-de-temas-en-raiz-*"))), 1)
        with contextlib.redirect_stdout(io.StringIO()) as dicho:
            self.assertEqual(orden.main([], SimpleNamespace(config=cfg.cargar(self.cfg_a))), 0)
        self.assertIn("en laptop, todas las máquinas", dicho.getvalue())


if __name__ == "__main__":
    unittest.main()
