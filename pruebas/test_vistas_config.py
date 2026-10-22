"""`[vistas.<clave>]` en la configuración: se traduce al leerla a `[bloques]`, `[apps]`, `[secciones]` o
`[resultados]`, que se siguen leyendo, así que el resto de telar no cambia (docs/propuestas/vistas.md).

Lo central es que cada forma de antes y su vista den la misma configuración. Además: los errores nombran la
vista, un nombre en las dos formas es un error, el orden, los módulos y la revisión `vistas` de `telar doctor`.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cli
from telar.cli import Contexto
from telar.config import ErrorDeConfig, como_vista, desde_dict, vista_en_toml
from telar.ordenes import doctor

#: cada forma de antes, con su vista equivalente. Cubren lo que hacen hoy las cuatro tablas: una página que
#: imprime un comando (en una pestaña, en el plan, en la barra o como página de un grupo), un lienzo, una url,
#: un grupo de hilos sin página y un resultado por día.
PARES = {
    "pestaña con color y tecla": (
        '[bloques.correo]\nnombre = "el correo"\ncomando = ["mi-correo", "--json"]\ncolor = "rojo"\ntecla = "e"\n',
        '[vistas.correo]\naparece = "pestana"\nnombre = "el correo"\ncomando = ["mi-correo", "--json"]\n'
        'color = "rojo"\ntecla = "e"\n'),
    "pestaña mínima": (
        '[bloques.mareas]\ncomando = ["mareas"]\n',
        '[vistas.mareas]\naparece = "pestana"\ncomando = ["mareas"]\n'),
    "arriba del plan": (
        '[bloques.retro]\ncomando = ["mi-retro"]\nen = "plan"\n',
        '[vistas.retro]\naparece = "plan"\ncomando = ["mi-retro"]\n'),
    "app de un comando": (
        '[apps.juego]\ndescripcion = "un juego"\npagina = ["/ruta/juego/casa"]\n',
        '[vistas.juego]\naparece = "apps"\ndescripcion = "un juego"\ncomando = ["/ruta/juego/casa"]\n'),
    "app de un archivo": (
        '[apps.vivero]\nnombre = "Vivero"\narchivo = "/ruta/vivero.html"\nmemoria = "/ruta/vivero.json"\n',
        '[vistas.vivero]\nnombre = "Vivero"\narchivo = "/ruta/vivero.html"\nmemoria = "/ruta/vivero.json"\n'),
    "app de una url": (
        '[apps.atlas]\nurl = "http://servidor:8790"\n',
        '[vistas.atlas]\nurl = "http://servidor:8790"\n'),
    "grupo de hilos con página": (
        '[secciones.diario]\nnombre = "Diario"\nhilos = ["notas", "rato*"]\nhome = ["mi-diario", "--json"]\n',
        '[vistas.diario]\nnombre = "Diario"\nhilos = ["notas", "rato*"]\ncomando = ["mi-diario", "--json"]\n'),
    "grupo de hilos sin página": (
        '[secciones.faro]\nhilos = ["Faro*"]\n',
        '[vistas.faro]\naparece = "hilos"\nhilos = ["Faro*"]\n'),
    "resultado por día": (
        '[resultados.plan]\ncarpeta = "/ruta/planes"\nen = "servidor"\ncomentar = ["/ruta/comentario"]\n',
        '[vistas.plan]\ncarpeta = "/ruta/planes"\nen = "servidor"\ncomentar = ["/ruta/comentario"]\n'),
    "resultado que vive en otra máquina": (
        '[resultados.mareas]\nen = "servidor"\nnombre = "las mareas"\n',
        '[vistas.mareas]\naparece = "dia"\nen = "servidor"\nnombre = "las mareas"\n'),
}


def leer(texto: str):
    return desde_dict(tomllib.loads(texto))


def sin_marcas(cfg):
    """La configuración sin lo que solo dice de qué forma se declaró (eso es lo único que puede cambiar)."""
    return replace(cfg, vistas=(), vistas_de_antes=())


class CadaFormaYSuVista(Prueba):
    def test_dan_la_misma_configuracion(self):
        for caso, (antes, ahora) in PARES.items():
            with self.subTest(caso):
                self.assertEqual(sin_marcas(leer(antes)), sin_marcas(leer(ahora)))

    def test_todas_juntas_tambien(self):
        antes = "".join(a for a, _ in PARES.values() if "mareas" not in a)
        ahora = "".join(v for a, v in PARES.values() if "mareas" not in a)
        a, b = leer(antes), leer(ahora)
        self.assertEqual(sin_marcas(a), sin_marcas(b))
        self.assertEqual(len(b.bloques) + len(b.apps) + len(b.secciones) + len(b.resultados), len(b.vistas))

    def test_dice_de_que_forma_se_declaro(self):
        antes, ahora = PARES["pestaña con color y tecla"]
        self.assertEqual(leer(antes).vistas_de_antes, (("bloques", "correo"),))
        self.assertEqual(leer(antes).vistas, ())
        self.assertEqual(leer(ahora).vistas, ("correo",))
        self.assertEqual(leer(ahora).vistas_de_antes, ())

    def test_sin_nada_todo_como_antes(self):
        cfg = leer("")
        self.assertEqual((cfg.vistas, cfg.vistas_de_antes, cfg.bloques, cfg.apps), ((), (), (), ()))


class ElLugar(Prueba):
    def test_la_fuente_que_deja_un_solo_lugar_lo_dice(self):
        cfg = leer('[vistas.a]\nurl = "https://a.org"\n[vistas.b]\narchivo = "/b.html"\n'
                   '[vistas.c]\nhilos = ["c*"]\n[vistas.d]\ncarpeta = "/d"\n')
        self.assertEqual([x.clave for x in cfg.apps], ["a", "b"])
        self.assertEqual([x.clave for x in cfg.secciones], ["c"])
        self.assertEqual([x.clave for x in cfg.resultados], ["d"])

    def test_con_comando_hay_que_decirlo(self):
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a\.aparece: con comando, di dónde"):
            leer('[vistas.a]\ncomando = ["a"]\n')

    def test_un_lugar_que_no_existe(self):
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a\.aparece: pestana, plan, apps, hilos o dia"):
            leer('[vistas.a]\naparece = "barra"\ncomando = ["a"]\n')

    def test_claves_de_dos_lugares(self):
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a: sus claves son de lugares distintos"):
            leer('[vistas.a]\nurl = "https://a.org"\ncarpeta = "/a"\n')

    def test_una_clave_que_no_va_en_ese_lugar(self):
        with self.assertRaisesRegex(ErrorDeConfig, r'vistas\.a\.hilos: no va con aparece = "pestana"'):
            leer('[vistas.a]\naparece = "pestana"\ncomando = ["a"]\nhilos = ["a"]\n')

    def test_en_ya_no_es_el_lugar(self):
        # `en` es la máquina, como en las demás tablas: el plan se dice con aparece
        with self.assertRaisesRegex(ErrorDeConfig, r'vistas\.a\.en: no va con aparece = "pestana"'):
            leer('[vistas.a]\naparece = "pestana"\ncomando = ["a"]\nen = "plan"\n')

    def test_una_clave_que_no_existe(self):
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a\.zzz: no existe"):
            leer('[vistas.a]\nurl = "https://a.org"\nzzz = 1\n')

    def test_sin_fuente(self):
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a: falta qué muestra"):
            leer('[vistas.a]\nnombre = "a"\n')
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a: falta comando"):
            leer('[vistas.a]\naparece = "plan"\n')
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a: falta carpeta o en"):
            leer('[vistas.a]\naparece = "dia"\n')

    def test_una_app_con_dos_fuentes(self):
        with self.assertRaisesRegex(ErrorDeConfig, r"vistas\.a: se esperaba una sola de comando, archivo o url"):
            leer('[vistas.a]\naparece = "apps"\ncomando = ["a"]\nurl = "https://a.org"\n')


class LosErrores(Prueba):
    def test_nombran_la_vista_y_no_la_tabla_de_antes(self):
        casos = {
            '[vistas.a]\naparece = "pestana"\ncomando = ["a"]\ncolor = "gris"\n': r"^vistas\.a\.color: azul",
            '[vistas.a]\nurl = "ftp://a"\n': r"^vistas\.a\.url: se esperaba http",
            '[vistas.a]\naparece = "apps"\ncomando = "a"\n': r"^vistas\.a\.comando: se esperaba una lista",
            '[vistas.a]\nhilos = "a"\n': r"^vistas\.a\.hilos: se esperaba una lista",
            '[vistas.A]\ncarpeta = "/a"\n': r"^vistas\.A: la clave va en minúsculas",
            '[vistas.a]\narchivo = "/a.txt"\n': r"^vistas\.a\.archivo: se esperaba la ruta absoluta",
            "vistas = 3\n": r"^vistas: se esperaba una tabla",
        }
        for texto, patron in casos.items():
            with self.subTest(texto):
                with self.assertRaisesRegex(ErrorDeConfig, patron):
                    leer(texto)

    def test_aparece_que_no_es_un_texto(self):
        for valor in ('["apps"]', '{ a = 1 }', "3"):
            with self.subTest(valor):
                with self.assertRaisesRegex(ErrorDeConfig, r"^vistas\.x\.aparece: pestana, plan, apps, hilos o dia"):
                    leer(f'[vistas.x]\naparece = {valor}\nurl = "https://a.org"\n')

    def test_en_con_una_fuente_que_no_corre_en_otra_maquina(self):
        # sin aparece, `en` haría de la vista un resultado por día y el error culparía al comando
        for fuente in ('comando = ["a"]', 'url = "https://a.org"', 'archivo = "/a.html"'):
            with self.subTest(fuente):
                nombre = fuente.split(" ")[0]
                with self.assertRaisesRegex(ErrorDeConfig, rf"^vistas\.x\.en: no va con {nombre}"):
                    leer(f'[vistas.x]\n{fuente}\nen = "srv"\n')

    def test_el_comando_traducido_se_nombra_como_comando(self):
        for vista in ('[vistas.j]\naparece = "apps"\ncomando = [" "]\n', '[vistas.j]\nhilos = ["j"]\ncomando = [" "]\n'):
            with self.subTest(vista):
                with self.assertRaisesRegex(ErrorDeConfig, r"^vistas\.j\.comando: "):
                    leer(vista)

    def test_un_nombre_en_las_dos_formas(self):
        for tabla, cuerpo in (("bloques", 'comando = ["a"]'), ("apps", 'url = "https://a.org"'),
                              ("secciones", 'hilos = ["a"]'), ("resultados", 'carpeta = "/a"')):
            with self.subTest(tabla):
                with self.assertRaisesRegex(ErrorDeConfig, rf"vistas\.a: también está declarada como \[{tabla}\.a\]"):
                    leer(f'[{tabla}.a]\n{cuerpo}\n[vistas.a]\nurl = "https://b.org"\n')


class ElOrden(Prueba):
    def test_primero_las_de_antes_y_las_vistas_en_el_orden_del_archivo(self):
        cfg = leer('[vistas.z]\naparece = "pestana"\ncomando = ["z"]\n'
                   '[bloques.m]\ncomando = ["m"]\n'
                   '[vistas.a]\naparece = "pestana"\ncomando = ["a"]\n')
        self.assertEqual([b.clave for b in cfg.bloques], ["m", "z", "a"])
        self.assertEqual(cfg.vistas, ("z", "a"))


class LoQueSugiereDoctor(Prueba):
    def test_la_sugerencia_leida_de_vuelta_da_lo_mismo(self):
        for caso, (antes, _ahora) in PARES.items():
            with self.subTest(caso):
                cfg = leer(antes)
                tabla, clave = cfg.vistas_de_antes[0]
                cosa = getattr(cfg, tabla)[0]
                texto = vista_en_toml(clave, como_vista(tabla, cosa))
                self.assertTrue(texto.startswith(f"[vistas.{clave}]\n"))
                self.assertEqual(sin_marcas(leer(texto)), sin_marcas(cfg))

    def test_siempre_dice_el_lugar(self):
        cfg = leer(PARES["app de una url"][0])
        self.assertEqual(como_vista("apps", cfg.apps[0]), {"aparece": "apps", "url": "http://servidor:8790"})

    def test_la_revision_de_doctor(self):
        antes, _ = PARES["pestaña con color y tecla"]
        cfg = leer(antes + PARES["app de una url"][1])
        revisiones = doctor._vistas(Contexto(config=cfg))
        self.assertEqual(len(revisiones), 1)
        r = revisiones[0]
        self.assertEqual((r["nombre"], r["estado"]), ("vistas", doctor.AVISO))
        self.assertIn("[bloques.correo] es de la forma de antes", r["dice"])
        self.assertTrue(r["arreglo"].startswith("cámbiala por:\n[vistas.correo]\n"))
        # lo que sugiere es TOML que se copia tal cual y da la misma configuración
        texto = r["arreglo"].removeprefix("cámbiala por:\n")
        self.assertEqual(sin_marcas(leer(texto)).bloques, cfg.bloques)

    def test_doctor_escribe_la_vista_entera_y_con_comillas(self):
        # la sugerencia es TOML que se copia tal cual, también con una clave que lleva un punto o un espacio
        for antes in ('[bloques."mi correo"]\ncomando = ["a"]\ncolor = "rojo"\n', '[apps."a.b"]\nurl = "http://x"\n'):
            with self.subTest(antes):
                cfg = leer(antes)
                (r,) = doctor._vistas(Contexto(config=cfg))
                self.assertTrue(r["arreglo"].startswith("cámbiala por:\n"))
                texto = r["arreglo"].removeprefix("cámbiala por:\n")
                self.assertEqual(sin_marcas(leer(texto)), sin_marcas(cfg))

    def test_doctor_con_la_misma_clave_en_dos_tablas_de_antes(self):
        # una vista es una sola cosa: [bloques.x] y [apps.x] no caben en una [vistas.x], y sugerir dos daría un
        # TOML que no se lee. Se dice que se quedan como están, sin aviso que no tenga arreglo.
        cfg = leer('[bloques.x]\ncomando = ["a"]\n[apps.x]\nurl = "https://a.org"\n[bloques.y]\ncomando = ["y"]\n')
        revisiones = doctor._vistas(Contexto(config=cfg))
        avisos = [r for r in revisiones if r["estado"] == doctor.AVISO]
        self.assertEqual([r["dice"] for r in avisos], ["[bloques.y] es de la forma de antes: telar la sigue leyendo"])
        otros = [r for r in revisiones if r["estado"] != doctor.AVISO]
        self.assertEqual(len(otros), 1)
        self.assertEqual(otros[0]["estado"], doctor.OK)
        self.assertIn("[bloques.x] y [apps.x]", otros[0]["dice"])

    def test_la_sugerencia_de_un_resultado_con_nombre(self):
        cfg = leer('[resultados.x]\nen = "srv"\nnombre = "x"\n')
        texto = vista_en_toml("x", como_vista("resultados", cfg.resultados[0]))
        self.assertEqual(leer(texto).resultados, cfg.resultados)

    def test_la_sugerencia_no_queda_atada_a_la_carpeta_de_esta_maquina(self):
        cfg = leer('[apps.x]\narchivo = "~/a.html"\nmemoria = "~/a.json"\n')
        vista = como_vista("apps", cfg.apps[0])
        self.assertEqual((vista["archivo"], vista["memoria"]), ("~/a.html", "~/a.json"))
        self.assertEqual(leer(vista_en_toml("x", vista)).apps, cfg.apps)

    def test_un_comando_que_bloques_acepta_tambien_vale_como_vista(self):
        cfg = leer('[bloques.x]\ncomando = ["echo", " "]\n[secciones.y]\nhilos = ["y"]\nhome = []\n')
        for tabla, cosa in (("bloques", cfg.bloques[0]), ("secciones", cfg.secciones[0])):
            with self.subTest(tabla):
                self.assertEqual(getattr(leer(vista_en_toml(cosa.clave, como_vista(tabla, cosa))), tabla), (cosa,))
        self.assertEqual(leer('[vistas.y]\nhilos = ["y"]\ncomando = []\n').secciones, cfg.secciones)

    def test_doctor_sin_nada_de_antes(self):
        cfg = leer(PARES["app de una url"][1])
        self.assertEqual([(r["estado"], r["dice"]) for r in doctor._vistas(Contexto(config=cfg))],
                         [(doctor.OK, "1 vista en [vistas], ninguna de antes")])
        self.assertEqual(doctor._vistas(Contexto(config=leer(""))), [])

    def test_doctor_corre_la_revision(self):
        self.assertIn("revisiones += _vistas(ctx)", Path(doctor.__file__).read_text(encoding="utf-8"))


class ConModulos(Prueba):
    """Los módulos siguen igual: aportan a las tablas de antes, y no cuentan como «de antes» para doctor."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name) / "faro"
        self.carpeta.mkdir()
        (self.carpeta / "modulo.toml").write_text('[pestana]\ncomando = ["faro"]\n', encoding="utf-8")
        self.modulo = f'[modulos.faro]\ncarpeta = "{self.carpeta}"\n'

    def test_un_modulo_junto_a_las_vistas(self):
        cfg = leer(self.modulo + '[vistas.mareas]\naparece = "pestana"\ncomando = ["mareas"]\n')
        self.assertEqual([b.clave for b in cfg.bloques], ["mareas", "faro"])
        self.assertEqual(cfg.vistas_de_antes, ())
        self.assertEqual(doctor._vistas(Contexto(config=cfg))[0]["estado"], doctor.OK)

    def test_un_modulo_que_se_llama_como_una_vista(self):
        with self.assertRaisesRegex(ErrorDeConfig, r"modulos\.faro: ya hay una \[vistas\.faro\] declarada a mano"):
            leer(self.modulo + '[vistas.faro]\naparece = "pestana"\ncomando = ["otro"]\n')
        rotos: list = []
        cfg = desde_dict(tomllib.loads(self.modulo + '[vistas.faro]\naparece = "pestana"\ncomando = ["otro"]\n'),
                         rotos=rotos)
        self.assertEqual([b.comando for b in cfg.bloques], [("otro",)])
        self.assertIn("[vistas.faro]", cfg.modulos_rotos[0][1])


    def test_un_modulo_que_se_llama_como_una_vista_de_otro_lugar(self):
        # el módulo aporta una pestaña y la vista es una app o un grupo de hilos: igual son dos cosas llamadas faro
        for vista in ('url = "https://a.org"', 'hilos = ["Faro*"]'):
            with self.subTest(vista):
                with self.assertRaisesRegex(ErrorDeConfig, r"modulos\.faro: ya hay una \[vistas\.faro\]"):
                    leer(self.modulo + f'[vistas.faro]\n{vista}\n')


class DePuntaAPunta(Prueba):
    """Con un archivo de configuración de verdad: lo que ven las órdenes es lo mismo con una forma y con la otra."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["TELAR_ESTADO"] = str(Path(self.tmp.name) / "estado")
        os.environ["TELAR_RAIZ"] = str(EJEMPLO)

    def correr(self, texto: str, *argv: str) -> tuple[int, str]:
        archivo = Path(self.tmp.name) / "config.toml"
        archivo.write_text(texto, encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(archivo)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = cli.main(list(argv))
        return codigo, salida.getvalue()

    def test_config_json_igual(self):
        antes = "".join(a for a, _ in PARES.values() if "mareas" not in a)
        ahora = "".join(v for a, v in PARES.values() if "mareas" not in a)
        codigo_a, a = self.correr(antes, "config", "--json")
        codigo_b, b = self.correr(ahora, "config", "--json")
        self.assertEqual((codigo_a, codigo_b), (0, 0))
        self.assertEqual(json.loads(a), json.loads(b))

    def test_la_lista_de_apps(self):
        _, a = self.correr(PARES["app de un archivo"][0] + PARES["app de una url"][0], "app")
        _, b = self.correr(PARES["app de un archivo"][1] + PARES["app de una url"][1], "app")
        self.assertEqual(a, b)
        self.assertIn("atlas", b)

    def test_un_error_no_deja_arrancar_y_lo_dice(self):
        archivo = Path(self.tmp.name) / "config.toml"
        archivo.write_text('[vistas.a]\ncomando = ["a"]\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(archivo)
        error = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(error):
            codigo = cli.main(["config", "--json"])
        self.assertEqual(codigo, 2)
        self.assertIn("vistas.a.aparece", error.getvalue())


if __name__ == "__main__":
    unittest.main()
