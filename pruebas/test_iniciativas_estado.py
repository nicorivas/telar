"""El estado de las iniciativas (telar.iniciativas, `[iniciativas]` de la configuración, `telar proyectos estado` y
`POST /proyectos/estado`): el vocabulario y sus sinónimos, las de fuente externa (su ficha dice `estado_fuente:`) que no
se cambian aquí, y escribirlo en la ficha tocando solo `estado:` y `estado_desde:` de su frontmatter."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as cfg
from telar import iniciativas
from telar.iniciativas import ErrorDeEstado, con_estado

HOY = "2026-11-18"


def cambiadas(antes: str, despues: str) -> list[tuple[str, str]]:
    """Las líneas que cambiaron (con su final), en pares; las agregadas van con "" a la izquierda."""
    import difflib

    a, b = antes.splitlines(keepends=True), despues.splitlines(keepends=True)
    salida = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        izq, der = a[i1:i2], b[j1:j2]
        for k in range(max(len(izq), len(der))):
            salida.append((izq[k] if k < len(izq) else "", der[k] if k < len(der) else ""))
    return salida


class EscribirElFrontmatter(Prueba):
    """`con_estado`: solo esas dos líneas, y el resto del archivo byte a byte."""

    def test_con_estado_previo_cambia_su_linea_y_suma_desde_tras_ella(self):
        ficha = ('---\ntitulo: Club de lectura\nestado: "activo"\ndueno: "Ana"\n---\n\n# Club de lectura\n\n'
                 '| Campo | Valor |\n|---|---|\n| Estado | Activo |\n')
        nuevo, antes = con_estado(ficha, "en pausa", HOY)
        self.assertEqual(antes, "activo")
        self.assertEqual(cambiadas(ficha, nuevo), [('estado: "activo"\n', 'estado: "en pausa"\n'), ("", f"estado_desde: {HOY}\n")],
                         "las comillas de antes se quedan; la tabla del documento no se toca")
        self.assertTrue(nuevo.endswith("| Estado | Activo |\n"))

    def test_sin_estado_previo_van_las_dos_al_final_del_frontmatter(self):
        ficha = "---\ntitulo: Boletín\nactualizado: 2026-10-14\n---\n# Boletín\n"
        nuevo, antes = con_estado(ficha, "en curso", HOY)
        self.assertEqual(antes, "")
        self.assertEqual(nuevo, f"---\ntitulo: Boletín\nactualizado: 2026-10-14\nestado: en curso\nestado_desde: {HOY}\n---\n# Boletín\n")

    def test_con_los_dos_previos_cambian_en_su_lugar(self):
        ficha = "---\nestado_desde: 2026-01-02\ntitulo: X\nestado: idea\n---\ncuerpo\n"
        nuevo, antes = con_estado(ficha, "diseño", HOY)
        self.assertEqual(antes, "idea")
        self.assertEqual(nuevo, f"---\nestado_desde: {HOY}\ntitulo: X\nestado: diseño\n---\ncuerpo\n")

    def test_solo_desde_previo_estado_va_justo_antes(self):
        nuevo, _ = con_estado("---\na: 1\nestado_desde: '2026-01-02'\nb: 2\n---\n", "terminada", HOY)
        self.assertEqual(nuevo, f"---\na: 1\nestado: terminada\nestado_desde: '{HOY}'\nb: 2\n---\n")

    def test_los_comentarios_se_quedan(self):
        ficha = ("---\n# la ficha de la iniciativa\ntitulo: Encuentros   # el nombre corto\n"
                 "estado: activa    # lo dijo la reunión del lunes\n#estado: vieja\n  # sangrado\n---\n# Encuentros\n")
        nuevo, antes = con_estado(ficha, "en pausa", HOY)
        self.assertEqual(antes, "activa")
        self.assertEqual(cambiadas(ficha, nuevo), [
            ("estado: activa    # lo dijo la reunión del lunes\n", "estado: en pausa    # lo dijo la reunión del lunes\n"),
            ("", f"estado_desde: {HOY}\n")])
        # un comentario sin valor, también
        nuevo, antes = con_estado("---\nestado:   # falta\n---\n", "idea", HOY)
        self.assertEqual((nuevo, antes), (f"---\nestado:   idea # falta\nestado_desde: {HOY}\n---\n", ""))

    def test_las_comillas_y_lo_que_las_necesita(self):
        self.assertEqual(con_estado("---\nestado: 'idea'\n---\n", "it's", HOY)[0], f"---\nestado: 'it''s'\nestado_desde: {HOY}\n---\n")
        # sin comillas antes, y un valor que en YAML no sería texto: con comillas dobles
        self.assertEqual(con_estado("---\nestado: idea\n---\n", "no", HOY)[0], f'---\nestado: "no"\nestado_desde: {HOY}\n---\n')
        self.assertEqual(con_estado("---\nestado: idea\n---\n", "fase: 2", HOY)[0], f'---\nestado: "fase: 2"\nestado_desde: {HOY}\n---\n')
        # un # dentro de las comillas no es un comentario
        self.assertEqual(con_estado('---\nestado: "en #1" # ojo\n---\n', "idea", HOY),
                         (f'---\nestado: "idea" # ojo\nestado_desde: {HOY}\n---\n', "en #1"))

    def test_la_nota_y_la_fuente_no_se_tocan(self):
        ficha = ('---\ntitulo: Ofertas\nestado: "idea"\nestado_desde: 2026-11-01\nestado_nota: "falta la reunión con el área"\n'
                 'estado_fuente: sheet\nprograma: "plan"\n---\n# Ofertas\n')
        nuevo, antes = con_estado(ficha, "diseño", HOY)
        self.assertEqual(antes, "idea")
        self.assertEqual(cambiadas(ficha, nuevo), [('estado: "idea"\n', 'estado: "diseño"\n'), ("estado_desde: 2026-11-01\n", f"estado_desde: {HOY}\n")])

    def test_estado_desde_no_es_estado(self):
        """`estado_desde:` no se confunde con `estado:`, ni una clave con sangría (de un mapa) con una de primer nivel."""
        ficha = "---\nestado_desde: 2026-01-01\nmeta:\n  estado: otro\n---\n"
        nuevo, antes = con_estado(ficha, "idea", HOY)
        self.assertEqual(antes, "")
        self.assertEqual(nuevo, f"---\nestado: idea\nestado_desde: {HOY}\nmeta:\n  estado: otro\n---\n")

    def test_finales_de_linea_y_bom(self):
        ficha = "﻿---\r\ntitulo: X\r\nestado: idea\r\n---\r\ncuerpo\r\n"
        nuevo, _ = con_estado(ficha, "en curso", HOY)
        self.assertEqual(nuevo, f"﻿---\r\ntitulo: X\r\nestado: en curso\r\nestado_desde: {HOY}\r\n---\r\ncuerpo\r\n")

    def test_sin_frontmatter_se_le_pone_uno_arriba(self):
        nuevo, antes = con_estado("# Inventario\n\nTexto.\n", "idea", HOY)
        self.assertEqual((nuevo, antes), (f"---\nestado: idea\nestado_desde: {HOY}\n---\n# Inventario\n\nTexto.\n", ""))

    def test_lo_que_no_es_de_una_linea_no_se_toca(self):
        for ficha in ("---\nestado: |\n  activo\n---\n", "---\nestado:\n  - activo\n---\n", "---\nestado: [a, b]\n---\n",
                      "---\nestado: activo\n"):
            with self.subTest(ficha=ficha), self.assertRaises(ErrorDeEstado):
                con_estado(ficha, "idea", HOY)

    def test_escribir_en_el_archivo_y_no_si_es_de_solo_lectura(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "README.md"
            f.write_bytes(b"---\nestado: idea\n---\n# X\n")
            self.assertEqual(iniciativas.escribir_estado(f, "en curso", HOY), "idea")
            self.assertEqual(f.read_text(), f"---\nestado: en curso\nestado_desde: {HOY}\n---\n# X\n")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["README.md"], "sin temporales que queden")
            f.chmod(0o444)
            try:
                with self.assertRaises(PermissionError):
                    iniciativas.escribir_estado(f, "en pausa", HOY)
                self.assertIn("estado: en curso", f.read_text())
            finally:
                f.chmod(0o644)


class ElVocabulario(Prueba):
    def ini(self, **extra) -> cfg.Iniciativas:
        tabla = {"estados": ["idea", "diseño", "en curso", "en pausa", "terminada", "descartada"],
                 "sinonimos": {"activo": "en curso", "activa": "en curso"}, **extra}
        return cfg._iniciativas(tabla)

    def test_canonico_sinonimos_y_fuera(self):
        ini = self.ini()
        self.assertEqual(iniciativas.canonico(ini, "En Curso"), ("en curso", True))
        self.assertEqual(iniciativas.canonico(ini, "Diseno"), ("diseño", True), "sin tildes también")
        self.assertEqual(iniciativas.canonico(ini, "Activo"), ("en curso", True), "un sinónimo vale como el suyo")
        self.assertEqual(iniciativas.canonico(ini, "piloto"), ("piloto", False), "fuera del vocabulario: tal cual")
        self.assertEqual(iniciativas.canonico(ini, ""), ("", True))
        self.assertEqual(iniciativas.canonico(cfg.Iniciativas(), "piloto"), ("piloto", True), "sin vocabulario, nada está fuera")
        self.assertEqual(iniciativas.del_vocabulario(ini, "activa"), "en curso")
        self.assertIsNone(iniciativas.del_vocabulario(ini, "piloto"))

    def test_la_fuente_la_dice_la_ficha_y_la_configuracion_la_nombra(self):
        ini = self.ini(fuentes={"sheet": "Planilla"})
        self.assertEqual(iniciativas.fuente(ini, {"estado_fuente": "Sheet"}), "Planilla")
        self.assertEqual(iniciativas.fuente(ini, {"estado_fuente": "pmo"}), "pmo", "una que no nombra: tal cual")
        self.assertEqual(iniciativas.fuente(ini, {"programa": "plan"}), "", "sin estado_fuente: se cambia aquí")
        self.assertEqual(iniciativas.para_la_pagina(ini)["fuentes"], {"sheet": "Planilla"})

    def test_lo_que_la_configuracion_no_acepta(self):
        malos = [
            {"estados": ["idea", "Idea"]},                                  # dos veces
            {"estados": ["idea"], "sinonimos": {"idea": "idea"}},           # un sinónimo que ya es estado
            {"estados": ["idea"], "sinonimos": {"nueva": "otra"}},          # a un estado que no está
            {"estados": ["idea"], "clases": {"idea": "rara"}},              # una clase que no existe
            {"estados": ["idea"], "clases": {"otra": "idea"}},              # de un estado que no está
            {"sinonimos": {"activo": "en curso"}},                          # sinónimos sin vocabulario
            {"fuentes": ["sheet"]},                                         # una tabla, no una lista
            {"fuentes": {"sheet": ""}},                                     # sin nombre
            {"fuentes": {"sheet": "Sheet", "Sheet": "Planilla"}},           # dos veces
            {"estados": ["idea"], "colores": {}},                           # una clave que no existe
        ]
        for tabla in malos:
            with self.subTest(tabla=tabla), self.assertRaises(cfg.ErrorDeConfig):
                cfg._iniciativas(tabla)
        self.assertEqual(self.ini(clases={"Diseño": "preparacion"}).clases, (("diseño", "preparacion"),))


PERFIL = """version: 1
nombre: casa
arquetipos:
  iniciativa:
    descripcion: El trabajo propio, sin cliente.
    ruta: "iniciativas/*/"
    documento: README.md
    secciones:
      titulo:
        tipo: linea
        encabezado: '^#\\s+(.+)$'
  proyecto:
    descripcion: Un encargo.
    ruta: "proyectos/*/"
    documento: README.md
    secciones:
      titulo:
        tipo: linea
        encabezado: '^#\\s+(.+)$'
"""

CONFIG = """raiz = "{raiz}"
estado = "{estado}"

[modos.tactica]
iniciativas = "iniciativa"
agrupar_iniciativas = "{{frontmatter:programa}}"

[iniciativas]
estados = ["idea", "diseño", "en curso", "en pausa", "terminada", "descartada"]
sinonimos = {{ activo = "en curso", activa = "en curso" }}

fuentes = {{ sheet = "Planilla" }}
"""

FICHAS = {
    "iniciativas/club": '---\ntitulo: Club de lectura\nestado: "activo"   # desde la reunión\ndueno: Ana\n---\n# Club de lectura\n',
    "iniciativas/canales": "---\nprograma: club\n---\n# Canales\n",
    "iniciativas/plan-anual": "---\nestado: activo\n---\n# Plan anual\n",
    "iniciativas/p01-encuesta": '---\nprograma: "plan-anual"\nestado: "idea"\nestado_desde: 2026-11-01\nestado_fuente: sheet\n---\n# Encuesta\n',
    "iniciativas/p02-base": '---\nprograma: "plan-anual"\nestado: "idea"\nestado_nota: "espera la reunión"\n---\n# Base\n',
    "proyectos/faro": "---\nestado: activo\n---\n# Faro\n",
}


class CambiarElEstado(Prueba):
    """El servicio (`telar proyectos estado`, `POST /proyectos/estado`) sobre un repositorio de prueba."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name) / "casa"
        (self.raiz / ".telar").mkdir(parents=True)
        (self.raiz / ".telar" / "perfil.yaml").write_text(PERFIL)
        for ruta, texto in FICHAS.items():
            (self.raiz / ruta).mkdir(parents=True)
            (self.raiz / ruta / "README.md").write_text(texto)
        self.config_ruta = Path(self._tmp.name) / "config.toml"
        self.config_ruta.write_text(CONFIG.format(raiz=self.raiz, estado=Path(self._tmp.name) / "estado"))
        os.environ["TELAR_CONFIG"] = str(self.config_ruta)

    def ctx(self):
        from telar.cli import Contexto

        return Contexto(config=cfg.cargar(self.config_ruta))

    def ficha(self, ruta: str) -> str:
        return (self.raiz / ruta / "README.md").read_text()

    def cambiar(self, ruta, estado):
        from telar.servicios import proyectos

        return proyectos.cambiar_estado(self.ctx(), ruta, estado, hoy=date(2026, 11, 18))

    def test_cambia_solo_esas_dos_lineas(self):
        r = self.cambiar("iniciativas/club", "En pausa")
        self.assertEqual((r.archivo, r.estado, r.antes, r.estado_desde, r.cambio),
                         ("iniciativas/club/README.md", "en pausa", "activo", HOY, True))
        self.assertEqual(cambiadas(FICHAS["iniciativas/club"], self.ficha("iniciativas/club")),
                         [('estado: "activo"   # desde la reunión\n', 'estado: "en pausa"   # desde la reunión\n'), ("", f"estado_desde: {HOY}\n")])

    def test_sin_estado_previo_y_un_sinonimo_pedido_escribe_el_suyo(self):
        r = self.cambiar("iniciativas/canales", "activa")
        self.assertEqual((r.estado, r.antes), ("en curso", ""))
        self.assertEqual(self.ficha("iniciativas/canales"), f"---\nprograma: club\nestado: en curso\nestado_desde: {HOY}\n---\n# Canales\n")

    def test_ya_estaba_contando_sus_sinonimos_no_se_escribe(self):
        r = self.cambiar("iniciativas/club", "en curso")
        self.assertEqual((r.cambio, r.antes, r.estado), (False, "activo", "en curso"))
        self.assertEqual(self.ficha("iniciativas/club"), FICHAS["iniciativas/club"], "el archivo no se reescribe solo")

    def test_una_de_fuente_externa_se_niega(self):
        from telar.servicios import ErrorDeServicio

        with self.assertRaises(ErrorDeServicio) as e:
            self.cambiar("iniciativas/p01-encuesta", "diseño")
        self.assertEqual(e.exception.codigo, 409)
        self.assertIn("Planilla", str(e.exception))
        self.assertEqual(self.ficha("iniciativas/p01-encuesta"), FICHAS["iniciativas/p01-encuesta"])
        # otra del mismo programa, sin estado_fuente: se cambia aquí, y su nota se queda
        self.assertTrue(self.cambiar("iniciativas/p02-base", "en pausa").cambio)
        self.assertEqual(self.ficha("iniciativas/p02-base"),
                         f'---\nprograma: "plan-anual"\nestado: "en pausa"\nestado_desde: {HOY}\nestado_nota: "espera la reunión"\n---\n# Base\n')

    def test_lo_que_no_se_puede(self):
        from telar.servicios import ErrorDeServicio

        for ruta, estado, codigo in [("iniciativas/club", "piloto", 422),       # fuera del vocabulario
                                     ("proyectos/faro", "en pausa", 422),       # no es una iniciativa
                                     ("iniciativas/no-esta", "idea", 404)]:
            with self.subTest(ruta=ruta, estado=estado), self.assertRaises(ErrorDeServicio) as e:
                self.cambiar(ruta, estado)
            self.assertEqual(e.exception.codigo, codigo)
        self.assertEqual(self.ficha("proyectos/faro"), FICHAS["proyectos/faro"])
        self.assertEqual(self.ficha("iniciativas/club"), FICHAS["iniciativas/club"])

    def test_sin_vocabulario_no_se_cambia(self):
        from telar.servicios import ErrorDeServicio

        texto = self.config_ruta.read_text()
        self.config_ruta.write_text(texto[: texto.index("[iniciativas]")])
        with self.assertRaises(ErrorDeServicio) as e:
            self.cambiar("iniciativas/club", "idea")
        self.assertEqual(e.exception.codigo, 422)

    def test_la_orden(self):
        from telar import cli

        salida, errores = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(errores):
            codigo = cli.main(["proyectos", "estado", "iniciativas/canales", "diseño", "--json"])
        self.assertEqual(codigo, 0, errores.getvalue())
        self.assertEqual(json.loads(salida.getvalue())["estado"], "diseño")
        with redirect_stdout(io.StringIO()), redirect_stderr(errores):
            self.assertNotEqual(cli.main(["proyectos", "estado", "iniciativas/p01-encuesta", "idea"]), 0)
        self.assertIn("Planilla", errores.getvalue())

    @unittest.skipUnless(HAY_FASTAPI, "sin fastapi")
    def test_la_api(self):
        from fastapi.testclient import TestClient

        from telar import api

        with mock.patch.object(api, "_refrescar", mock.AsyncMock()):
            cliente = TestClient(api.app)
            # la configuración de la prueba, y no la que tenga en caché el `serve` de otra prueba
            api.app.dependency_overrides[api.contexto] = self.ctx
            try:
                r = cliente.post("/proyectos/estado", json={"ruta": "iniciativas/club", "estado": "terminada"})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()["estado"], "terminada")
                r = cliente.post("/proyectos/estado", json={"ruta": "iniciativas/p01-encuesta", "estado": "diseño"})
                self.assertEqual(r.status_code, 409)
                self.assertIn("Planilla", r.json()["detail"])
                lista = cliente.get("/proyectos").json()
            finally:
                api.app.dependency_overrides.clear()
        self.assertEqual(lista["iniciativas"]["estados"][2], "en curso")
        self.assertEqual(lista["iniciativas"]["sinonimos"], {"activo": "en curso", "activa": "en curso"})
        self.assertEqual(lista["iniciativas"]["fuentes"], {"sheet": "Planilla"})


if __name__ == "__main__":
    unittest.main()
