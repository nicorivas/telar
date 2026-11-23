"""El horario de los mundos en la raíz (`<raiz>/.telar/mundos.toml`, telar.mundos_raiz): vale en todas las máquinas. Se lee
con la configuración (sin horario < la raíz < la configuración de la máquina, que pisa mundo por mundo); ⚙ mundos escribe el
horario y `fuera` en la raíz y saca de la máquina lo que lo taparía, sin escribir un horario que no se entiende o que se pisa
con el de otro mundo (422 con el porqué); lo escrito se commitea solo (ese archivo, nada más) y se sube; y `telar mundos
migrar` pasa los horarios de una máquina a la raíz con respaldo, sin cambiar lo que rige. Y la cuenta de los choques
(telar.horario.choques), la misma que dibuja la vista previa de la semana en la página."""

from __future__ import annotations

import contextlib
import io
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
from telar import horario, mundos, mundos_raiz

MAQUINA = """# la configuración de esta máquina
raiz = "{raiz}"
estado = "{estado}"

[mundos]
fuera = "personal"

[mundos.trabajo]
rutas = ["empresa/"]
horario = "lun-vie 9:00-19:00"   # el de siempre

[mundos.personal]
rutas = ["casa/"]
color = "verde"
"""


def sh(carpeta: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(carpeta), *args], check=True, capture_output=True, text=True).stdout


def forma(m) -> list:
    return [(t.dias, t.desde, t.hasta) for t in m.horario]


class Choques(unittest.TestCase):
    def tramos(self, *textos):
        return tuple(horario.leer_tramo(t) for t in textos)

    def test_dos_que_se_pisan_dicen_donde_por_dia(self):
        c = horario.choques({"trabajo": self.tramos("lun-vie 9-19"), "estudio": self.tramos("lun,mié 18-20")})
        self.assertEqual(c, [{"mundos": ["trabajo", "estudio"], "dia": 1, "desde": 1080, "hasta": 1140},
                             {"mundos": ["trabajo", "estudio"], "dia": 3, "desde": 1080, "hasta": 1140}])
        self.assertEqual(horario.decir_choque(c[0]), "«trabajo» y «estudio» se pisan el lunes de 18:00 a 19:00")

    def test_los_que_se_tocan_no_se_pisan_ni_los_de_un_mismo_mundo(self):
        self.assertEqual(horario.choques({"trabajo": self.tramos("lun-vie 9-13", "lun-vie 12-19"),
                                          "noche": self.tramos("lun-vie 19-23")}), [])

    def test_la_medianoche_del_sabado_sigue_el_domingo(self):
        c = horario.choques({"fiesta": self.tramos("sáb 22:00-2:00"), "domingo": self.tramos("dom")})
        self.assertEqual(c, [{"mundos": ["fiesta", "domingo"], "dia": 0, "desde": 0, "hasta": 120}])
        self.assertEqual(horario.hora(1440), "24:00")


class Base(Prueba):
    def setUp(self):
        super().setUp()
        self.raiz = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.raiz, ignore_errors=True)
        self.ruta = self.raiz / "config" / "config.toml"
        self.ruta.parent.mkdir()
        self.ruta.write_text(MAQUINA.format(raiz=self.raiz, estado=self.raiz / "estado"))
        self.archivo = self.raiz / ".telar" / "mundos.toml"

    def config(self) -> cfg.Config:
        return cfg.cargar(self.ruta)

    def de(self, archivo: Path) -> dict:
        return tomllib.loads(archivo.read_text()).get("mundos", {}) if archivo.exists() else {}


class Leerlos(Base):
    def test_sin_archivo_de_la_raiz_rige_lo_de_la_maquina(self):
        c = self.config()
        self.assertEqual(c.mundos_archivo, self.archivo)
        self.assertEqual(forma(c.mundos[0]), [((1, 2, 3, 4, 5), 540, 1140)])
        self.assertEqual(c.mundos_donde, {"horario": {"trabajo": "maquina"}, "fuera": "maquina"})

    def test_la_raiz_debajo_y_la_maquina_pisa_mundo_por_mundo(self):
        self.archivo.parent.mkdir()
        self.archivo.write_text('[mundos]\nfuera = "trabajo"\n\n[mundos.trabajo]\nhorario = "lun-jue 8-17"\n\n'
                             '[mundos.personal]\nhorario = ["sáb-dom"]\n')
        c = self.config()
        trabajo, personal = c.mundos
        self.assertEqual(forma(trabajo), [((1, 2, 3, 4, 5), 540, 1140)], "trabajo: el de la máquina")
        self.assertEqual(forma(personal), [((0, 6), 0, 1440)], "personal: el de la raíz")
        self.assertEqual(c.mundos_fuera, "personal", "fuera: el de la máquina")
        self.assertEqual(c.mundos_donde, {"horario": {"trabajo": "maquina", "personal": "raiz"}, "fuera": "maquina"})
        # sin lo de la máquina, rige la raíz
        cfg.escribir_clave("mundos.trabajo", "horario", None, self.ruta)
        cfg.escribir_clave("mundos", "fuera", None, self.ruta)
        c = self.config()
        self.assertEqual(forma(c.mundos[0]), [((1, 2, 3, 4), 480, 1020)])
        self.assertEqual((c.mundos_fuera, c.mundos_donde["fuera"]), ("trabajo", "raiz"))
        d = mundos.para_la_configuracion(c, etiquetas={})
        self.assertEqual([m["horario_vive"] for m in d["mundos"]], ["raiz", "raiz"])
        self.assertEqual((d["fuera_vive"], d["raiz"]), ("raiz", str(self.archivo)))

    def test_un_horario_vacio_en_la_maquina_tapa_el_de_la_raiz(self):
        self.archivo.parent.mkdir()
        self.archivo.write_text('[mundos.personal]\nhorario = "sáb-dom"\n')
        cfg.escribir_clave("mundos.personal", "horario", [], self.ruta)
        self.assertEqual(self.config().mundos[1].horario, ())

    def test_lo_de_la_raiz_que_esta_maquina_no_declara_no_se_aplica(self):
        self.archivo.parent.mkdir()
        self.archivo.write_text('[mundos]\nfuera = "estudio"\n\n[mundos.estudio]\nhorario = "sáb 9-13"\n')
        cfg.escribir_clave("mundos", "fuera", None, self.ruta)
        c = self.config()
        self.assertEqual([m.nombre for m in c.mundos], ["trabajo", "personal"], "no se inventa un mundo")
        self.assertEqual(c.mundos_fuera, "")
        self.assertEqual(len(c.mundos_sobran), 2)
        self.assertIn("estudio", c.mundos_sobran[0])

    def test_un_archivo_roto_no_tumba_nada_y_no_se_escribe_encima(self):
        self.archivo.parent.mkdir()
        for roto, dice in (('[mundos.trabajo]\n<<<<<<< HEAD\nhorario = "lun"\n', "no se lee"),
                           ('[mundos.trabajo]\nhorario = "lunes a viernes"\n', "mundos.trabajo.horario"),
                           ('[mundos.trabajo]\nrutas = ["x/"]\n', "solo su horario"),
                           ('[hilos]\ntope = 3\n', "sobra «hilos»")):
            self.archivo.write_text(roto)
            c = self.config()
            self.assertIn(dice, c.mundos_error)
            self.assertEqual(forma(c.mundos[0]), [((1, 2, 3, 4, 5), 540, 1140)], "queda lo de la máquina")
            with self.assertRaises(cfg.ErrorDeConfig):
                mundos_raiz.cambiar(c, "trabajo", {"horario": "lun-vie 9-18"})
            self.assertEqual(self.archivo.read_text(), roto)

    def test_sin_raiz_todo_en_la_maquina(self):
        c = cfg.desde_dict({"mundos": {"trabajo": {"horario": "lun-vie 9-19"}}})
        self.assertIsNone(c.mundos_archivo)
        self.assertEqual(forma(c.mundos[0]), [((1, 2, 3, 4, 5), 540, 1140)])


class Escribirlos(Base):
    def test_el_horario_va_a_la_raiz_y_sale_de_la_maquina(self):
        mundos_raiz.cambiar(self.config(), "trabajo", {"horario": ["lun-vie 9:00-13:00", "lun-vie 14:00-18:30"]})
        self.assertEqual(self.de(self.archivo)["trabajo"], {"horario": ["lun-vie 9:00-13:00", "lun-vie 14:00-18:30"]})
        self.assertTrue(self.archivo.read_text().startswith("# Cuándo rige cada mundo"), "con su cabeza")
        aqui = self.de(self.ruta)
        self.assertNotIn("horario", aqui["trabajo"], "lo que lo taparía sale de la máquina")
        self.assertEqual(aqui["trabajo"]["rutas"], ["empresa/"], "lo demás queda")
        self.assertIn("# la configuración de esta máquina", self.ruta.read_text(), "los comentarios quedan")
        c = self.config()
        self.assertEqual(forma(c.mundos[0]), [((1, 2, 3, 4, 5), 540, 780), ((1, 2, 3, 4, 5), 840, 1110)])
        self.assertEqual(c.mundos_donde["horario"], {"trabajo": "raiz"})

    def test_lo_demas_va_a_la_maquina_y_vacio_sale_de_los_dos(self):
        mundos_raiz.cambiar(self.config(), "personal", {"horario": "sáb-dom", "color": "azul"})
        self.assertEqual(self.de(self.archivo)["personal"], {"horario": "sáb-dom"})
        self.assertEqual(self.de(self.ruta)["personal"]["color"], "azul")
        self.assertNotIn("color =", self.archivo.read_text())
        mundos_raiz.cambiar(self.config(), "personal", {"horario": None})
        self.assertNotIn("personal", self.de(self.archivo), "la tabla vacía se va")
        self.assertEqual(self.config().mundos[1].horario, ())

    def test_un_horario_que_se_pisa_no_se_escribe_y_dice_donde(self):
        antes = self.ruta.read_text()
        with self.assertRaises(cfg.ErrorDeConfig) as e:
            mundos_raiz.cambiar(self.config(), "personal", {"horario": "vie 18:00-23:00", "color": "azul"})
        self.assertIn("«personal» y «trabajo» se pisan el viernes de 18:00 a 19:00", str(e.exception))
        self.assertEqual(self.ruta.read_text(), antes, "ni el color: nada")
        self.assertFalse(self.archivo.exists())
        # el mismo mundo puede cambiar el suyo encima de lo que tenía
        mundos_raiz.cambiar(self.config(), "trabajo", {"horario": "lun-vie 10-20"})

    def test_un_horario_que_no_se_entiende_no_se_escribe(self):
        for malo in ("lunes a viernes", "lun 9-9", "lun 25-26", ["lun 9-12", "mar 7"]):
            with self.assertRaises(cfg.ErrorDeConfig, msg=malo):
                mundos_raiz.cambiar(self.config(), "trabajo", {"horario": malo})
        self.assertFalse(self.archivo.exists())

    def test_un_mundo_que_no_hay(self):
        with self.assertRaises(KeyError):
            mundos_raiz.cambiar(self.config(), "estudio", {"horario": "sáb 9-13"})

    def test_fuera_a_la_raiz_y_ambos_sale_de_los_dos(self):
        mundos_raiz.cambiar_fuera(self.config(), "trabajo")
        self.assertEqual(self.de(self.archivo)["fuera"], "trabajo")
        self.assertNotIn("fuera", self.de(self.ruta))
        self.assertEqual(self.config().mundos_fuera, "trabajo")
        with self.assertRaises(cfg.ErrorDeConfig):
            mundos_raiz.cambiar_fuera(self.config(), "estudio")
        mundos_raiz.cambiar_fuera(self.config(), "")
        self.assertNotIn("fuera", self.de(self.archivo))
        self.assertEqual(self.config().mundos_fuera, "")

    def test_sin_raiz_todo_en_la_maquina_como_antes(self):
        self.ruta.write_text(self.ruta.read_text().replace(f'raiz = "{self.raiz}"\n', ""))
        mundos_raiz.cambiar(self.config(), "trabajo", {"horario": "lun-vie 8-17"})
        mundos_raiz.cambiar_fuera(self.config(), "trabajo")
        self.assertEqual(self.de(self.ruta)["trabajo"]["horario"], "lun-vie 8-17")
        self.assertEqual(self.de(self.ruta)["fuera"], "trabajo")
        self.assertFalse(self.archivo.exists())
        with self.assertRaises(cfg.ErrorDeConfig):   # el choque se revisa igual
            mundos_raiz.cambiar(self.config(), "personal", {"horario": "lun 16-20"})


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
        viejo = mundos_raiz.subir_luego
        mundos_raiz.subir_luego = lambda config, **_: self.subidos.append(config.mundos_archivo)
        self.addCleanup(setattr, mundos_raiz, "subir_luego", viejo)
        self.c = TestClient(api.app)

    def test_patch_del_horario_a_la_raiz_y_dice_donde_vive(self):
        r = self.c.patch("/mundos/trabajo", json={"valores": {"horario": ["lun-vie 9:00-18:00"]}})
        self.assertEqual(r.status_code, 200, r.text)
        trabajo = r.json()["mundos"][0]
        self.assertEqual((trabajo["horario"][0]["texto"], trabajo["horario_vive"]), ("lun-vie 9:00-18:00", "raiz"))
        self.assertEqual((r.json()["raiz"], r.json()["choques"]), (str(self.archivo), []))
        self.assertEqual(self.subidos, [self.archivo], "lo escrito en la raíz se sube")

    def test_un_choque_es_422_con_el_porque_y_no_se_sube(self):
        r = self.c.patch("/mundos/personal", json={"valores": {"horario": "sáb-dom; lun 18:30-20"}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("se pisan el lunes de 18:30 a 19:00", r.text)
        self.assertEqual(self.c.patch("/mundos/trabajo", json={"valores": {"horario": "lunes"}}).status_code, 200)
        self.assertEqual(self.c.patch("/mundos/trabajo", json={"valores": {"horario": "lun 9-25"}}).status_code, 422)
        self.assertEqual(self.c.patch("/mundos/trabajo", json={"horario": "lun 9-12"}).status_code, 422, "otra forma")
        self.assertEqual(self.subidos, [self.archivo])

    def test_lo_que_no_es_horario_no_va_a_la_raiz_ni_se_sube(self):
        self.assertEqual(self.c.patch("/mundos/trabajo", json={"valores": {"color": "azul"}}).status_code, 200)
        self.assertFalse(self.archivo.exists())
        self.assertEqual(self.subidos, [])

    def test_fuera_a_la_raiz(self):
        r = self.c.patch("/mundos", json={"fuera": "trabajo"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["fuera"], r.json()["fuera_vive"]), ("trabajo", "raiz"))
        self.assertEqual(self.subidos, [self.archivo])


class Migrar(Base):
    def setUp(self):
        super().setUp()
        self.ruta.write_text(self.ruta.read_text() + '\n[mundos.estudio]\nrutas = ["libros/"]\nhorario = "sáb 9-13"\n')
        self.archivo.parent.mkdir()
        self.archivo.write_text('[mundos.trabajo]\nhorario = "lunes-viernes 9-19"\n\n[mundos.estudio]\nhorario = "sáb 10-13"\n')

    def test_ver_no_escribe(self):
        antes = (self.ruta.read_text(), self.archivo.read_text())
        plan = mundos_raiz.migrar(self.config(), ver=True)
        self.assertEqual([(p["mundo"], p["clave"]) for p in plan["pasan"]], [("", "fuera")])
        self.assertEqual([(p["mundo"], p["clave"]) for p in plan["iguales"]], [("trabajo", "horario")],
                         "los mismos días y horas, aunque escritos de otra forma")
        self.assertEqual([(p["mundo"], p["aqui"], p["raiz"]) for p in plan["quedan"]], [("estudio", "sáb 9-13", "sáb 10-13")])
        self.assertFalse(plan["escrito"])
        self.assertEqual((self.ruta.read_text(), self.archivo.read_text()), antes)

    def test_pasa_lo_que_falta_con_respaldo_sin_cambiar_lo_que_rige(self):
        original = self.ruta.read_text()
        c = self.config()
        antes = ([forma(m) for m in c.mundos], c.mundos_fuera)
        plan = mundos_raiz.migrar(c)
        self.assertTrue(plan["escrito"])
        self.assertEqual(Path(plan["respaldo"]).read_text(), original, "el respaldo es la configuración de antes")
        self.assertTrue(plan["respaldo"].startswith(str(self.ruta) + ".antes-de-mundos-en-raiz-"))
        c = self.config()
        self.assertEqual(([forma(m) for m in c.mundos], c.mundos_fuera), antes, "rige lo mismo")
        self.assertEqual(self.de(self.archivo)["fuera"], "personal")
        aqui = self.de(self.ruta)
        self.assertNotIn("horario", aqui["trabajo"])
        self.assertNotIn("fuera", aqui)
        self.assertEqual(aqui["estudio"]["horario"], "sáb 9-13", "lo distinto se queda en la máquina")
        self.assertEqual(c.mundos_donde, {"horario": {"trabajo": "raiz", "estudio": "maquina"}, "fuera": "raiz"})
        plan = mundos_raiz.migrar(self.config())
        self.assertEqual((plan["pasan"], plan["iguales"], plan["escrito"]), ([], [], False), "otra vez: nada")

    def test_si_no_rige_igual_lo_devuelve_todo(self):
        original, de_raiz = self.ruta.read_text(), self.archivo.read_text()
        real = mundos_raiz._lo_que_rige
        cuenta = iter(range(10))
        mundos_raiz._lo_que_rige = lambda config: next(cuenta)   # «antes» y «después» nunca iguales
        self.addCleanup(setattr, mundos_raiz, "_lo_que_rige", real)
        with self.assertRaises(cfg.ErrorDeConfig):
            mundos_raiz.migrar(self.config())
        self.assertEqual((self.ruta.read_text(), self.archivo.read_text()), (original, de_raiz))

    def test_sin_raiz_no_hay_adonde(self):
        self.ruta.write_text('[mundos.trabajo]\nhorario = "lun-vie 9-19"\n')
        with self.assertRaises(cfg.ErrorDeConfig):
            mundos_raiz.migrar(self.config())


@unittest.skipUnless(shutil.which("git"), "sin git")
class Git(Base):
    """Commitear solo el archivo de la raíz, subirlo, y que la otra máquina rija igual al traer lo de arriba."""

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
        mundos_de = '\n[mundos.trabajo]\nrutas = ["empresa/"]\n\n[mundos.personal]\nrutas = ["casa/"]\n'
        self.cfg_a, self.cfg_b = self.base / "cfg-a.toml", self.base / "cfg-b.toml"
        self.cfg_a.write_text(f'raiz = "{self.a}"\nestado = "{self.base / "estado-a"}"\n{mundos_de}')
        self.cfg_b.write_text(f'raiz = "{self.b}"\nestado = "{self.base / "estado-b"}"\n{mundos_de}')

    def test_lo_cambiado_en_una_rige_en_la_otra(self):
        (self.a / "suelto.md").write_text("de otro\n")
        mundos_raiz.cambiar(cfg.cargar(self.cfg_a), "trabajo", {"horario": "lun-vie 9-19"})
        mundos_raiz.cambiar_fuera(cfg.cargar(self.cfg_a), "personal")
        res = mundos_raiz.subir(cfg.cargar(self.cfg_a).mundos_archivo, estado=self.base / "estado-a")
        self.assertEqual(res.estado, "subido", res.detalle)
        self.assertEqual(sh(self.a, "show", "--name-only", "--format=", "HEAD").split(), [".telar/mundos.toml"])
        self.assertIn("?? suelto.md", sh(self.a, "status", "--porcelain"), "lo de otros queda como estaba")
        self.assertIn("mundos:", sh(self.a, "log", "-1", "--format=%s"))
        self.assertEqual(cfg.cargar(self.cfg_b).mundos[0].horario, ())
        sh(self.b, "pull", "-q")
        b = cfg.cargar(self.cfg_b)
        self.assertEqual((forma(b.mundos[0]), b.mundos_fuera), ([((1, 2, 3, 4, 5), 540, 1140)], "personal"))

    def test_subir_luego_junta_varios_cambios_en_un_commit(self):
        for h in ("lun-vie 9-17", "lun-vie 9-18", "lun-vie 9-19"):
            mundos_raiz.cambiar(cfg.cargar(self.cfg_a), "trabajo", {"horario": h})
            mundos_raiz.subir_luego(cfg.cargar(self.cfg_a), espera=0.3)
        limite = time.time() + 20
        while time.time() < limite and "mundos" not in sh(self.a, "log", "-1", "--format=%s"):
            time.sleep(0.1)
        time.sleep(0.5)
        self.assertEqual(sh(self.a, "log", "--format=%s").count("mundos:"), 1)
        self.assertIn("9-19", sh(self.a, "show", "origin/main:.telar/mundos.toml"))

    def test_la_orden_migrar_y_la_lista(self):
        from telar.ordenes import mundos as orden

        self.cfg_a.write_text(self.cfg_a.read_text().replace('rutas = ["empresa/"]\n', 'rutas = ["empresa/"]\nhorario = "lun-vie 9-19"\n'))
        ctx = SimpleNamespace(config=cfg.cargar(self.cfg_a))
        with contextlib.redirect_stdout(io.StringIO()) as dicho:
            self.assertEqual(orden.main(["migrar", "--ver"], ctx), 0)
        self.assertIn("trabajo.horario", dicho.getvalue())
        self.assertFalse((self.a / ".telar" / "mundos.toml").exists(), "--ver no escribe")
        with contextlib.redirect_stdout(io.StringIO()) as dicho:
            self.assertEqual(orden.main(["migrar"], ctx), 0, dicho.getvalue())
        self.assertIn("subido", dicho.getvalue())
        self.assertIn('horario = "lun-vie 9-19"', sh(self.a, "show", "origin/main:.telar/mundos.toml"))
        self.assertNotIn("horario", self.cfg_a.read_text())
        self.assertEqual(len(list(self.base.glob("cfg-a.toml.antes-de-mundos-en-raiz-*"))), 1)
        with contextlib.redirect_stdout(io.StringIO()) as dicho:
            self.assertEqual(orden.main([], SimpleNamespace(config=cfg.cargar(self.cfg_a))), 0)
        self.assertIn("en laptop, todas las máquinas", dicho.getvalue())

    def test_atrasado_no_migra(self):
        mundos_raiz.cambiar(cfg.cargar(self.cfg_a), "trabajo", {"horario": "lun-vie 9-19"})
        mundos_raiz.subir(cfg.cargar(self.cfg_a).mundos_archivo)
        self.assertIn("cambió arriba", mundos_raiz.atrasado(self.b / ".telar" / "mundos.toml"))


class Doctor(Base):
    def test_avisa_lo_solo_de_aqui_los_choques_y_lo_que_sobra(self):
        from telar.ordenes import doctor

        self.ruta.write_text(self.ruta.read_text() + '\n[mundos.estudio]\nhorario = "lun 18-20"\n')
        self.archivo.parent.mkdir()
        self.archivo.write_text('[mundos.huerta]\nhorario = "dom"\n')
        dichos = [r.get("detalle", "") or str(r) for r in doctor._horarios(SimpleNamespace(config=self.config()))]
        texto = "\n".join(map(str, dichos))
        self.assertIn("se pisan el lunes de 18:00 a 19:00", texto)
        self.assertIn("huerta", texto)
        self.assertIn("solo en esta máquina", texto)


if __name__ == "__main__":
    unittest.main()
