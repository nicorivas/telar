"""Las fechas (telar.fechas, `telar fechas`): los cronogramas de los documentos y los proveedores `fechas`."""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from comun import EJEMPLO, HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import fechas
from telar.config import Proveedor
from telar.proveedores import ErrorDeProveedor
from telar.proveedores import fechas as prov

DOC = """# Faro

## Estado

Montada la lámpara.

## Cronograma

| Estado | Actividad | Responsable | Inicio | Fin | Depende de |
|---|---|---|---|---|---|
| ✅ | Montar la lámpara | Ana | 2026-10-01 | 2026-10-10 | |
| 🔄 | Ajustar el giro | Ana | 2026-10-11 | 2026-10-20 | Montar la lámpara |
| ⬜ | Inauguración | Beto | 2026-11-05 | | Ajustar el giro, Otra cosa |
| ⬜ | Pintar | | por definir | | |
| ⬜ | Revisar | | 6 a 10 de julio | | |
| completado | Medir en agosto | | 2026-08 | | |

## Bitácora

| Fecha | Qué pasó |
|---|---|
| 2026-09-01 | Llegó la lámpara |
"""


class LeerUnDocumento(Prueba):
    def leer(self, texto=DOC):
        return fechas.leer_documento(texto, archivo="proyectos/faro/README.md", proyecto="proyectos/faro")

    def test_lee_el_cronograma_por_el_nombre_de_cada_columna(self):
        leidas = self.leer()
        titulos = [f.titulo for f in leidas.fechas]
        self.assertEqual(titulos, ["Montar la lámpara", "Ajustar el giro", "Inauguración", "Medir en agosto"])
        montar, giro, inauguracion, agosto = leidas.fechas
        self.assertEqual((montar.inicio, montar.fin, montar.clase, montar.estado, montar.responsable),
                         (date(2026, 10, 1), date(2026, 10, 10), "actividad", "hecho", "Ana"))
        self.assertEqual(giro.estado, "en-curso")
        # un día solo, sin fin: un evento de ese día
        self.assertEqual((inauguracion.inicio, inauguracion.fin, inauguracion.clase), (date(2026, 11, 5),) * 2 + ("evento",))
        # un mes entero, del primero al último
        self.assertEqual((agosto.inicio, agosto.fin, agosto.estado), (date(2026, 8, 1), date(2026, 8, 31), "hecho"))

    def test_cada_fila_se_nombra_por_su_lugar_y_depende_de_otras_por_su_titulo(self):
        montar, giro, inauguracion, _ = self.leer().fechas
        self.assertEqual(montar.id, "proyectos/faro/README.md:11")
        self.assertEqual(montar.fuente, montar.id)
        self.assertEqual(giro.depende, (montar.id,))
        # «Otra cosa» no es una fila de la tabla: se pierde, no se inventa
        self.assertEqual(inauguracion.depende, (giro.id,))
        self.assertTrue(montar.version)
        self.assertEqual(montar.editable, ("inicio", "fin"))

    def test_lo_que_no_tiene_fecha_todavia_se_calla_y_lo_que_no_se_entiende_se_dice(self):
        saltadas = self.leer().saltadas
        self.assertEqual(saltadas, ["proyectos/faro/README.md:15: «6 a 10 de julio» no es una fecha que se entienda"])

    def test_solo_las_secciones_de_cronograma(self):
        # la bitácora tiene una columna «Fecha»: no es un plan
        self.assertNotIn("Llegó la lámpara", [f.titulo for f in self.leer().fechas])
        self.assertEqual(self.leer("# Sin\n\n| Fecha | Qué |\n|---|---|\n| 2026-01-01 | x |\n").fechas, [])

    def test_una_tabla_sin_columna_de_fecha_se_dice(self):
        leidas = self.leer("## Cronograma\n\n| Actividad | Quién |\n|---|---|\n| a | b |\n")
        self.assertEqual(leidas.fechas, [])
        self.assertIn("no tiene una columna de fecha", leidas.saltadas[0])

    def test_un_cronograma_en_un_nivel_mas_hondo_y_la_seccion_termina_en_el_siguiente_encabezado(self):
        texto = "## Plan\n\n### Cronograma\n\n| Hito | Fecha |\n|---|---|\n| Lanzamiento | 1-dic-2026 |\n\n### Otra\n\n| Hito | Fecha |\n|---|---|\n| No | 2026-01-01 |\n"
        leidas = self.leer(texto)
        self.assertEqual([(f.titulo, f.inicio) for f in leidas.fechas], [("Lanzamiento", date(2026, 12, 1))])


CALENDARIO = """---
actualizado: 2026-10-27
---

# Calendario

## Junio

| Fecha | Hora | Cliente | Programa | Ses. | Relator | Estado | Proyecto |
|---|---|---|---|---|---|---|---|
| jue 18-jun | 10:00–12:00 | Faro | Taller de luz | 1 | Ana | dictado | 70 |
| vie 19-jun | 10:00–12:00 | Molino | Aspas | | Beto | por confirmar | 140 |
| 3 al 5-jun | | Faro | Visita | | | dictado | 70 |

## Notas

| Fecha | Qué |
|---|---|
| 2026-06-01 | no es un plan |
"""

MAPA = {
    "secciones": "## Junio",
    "campos": {
        "clase": "sesion",
        "inicio": {"columna": "Fecha", "formato": "EEE d-MMM", "año": "frontmatter:actualizado"},
        "hora": {"columna": "Hora", "formato": "HH:mm", "rango": "–"},
        "titulo": "{Programa} · {Ses.}",
        "responsable": {"columna": "Relator"},
        "estado": {"columna": "Estado", "valores": {"dictado": "hecho", "por confirmar": "pendiente"}},
        "proyecto": {"columna": "Proyecto", "buscar": "codigo"},
    },
}


class ConUnMapa(Prueba):
    def leer(self, mapa=MAPA, texto=CALENDARIO):
        from telar import mapas

        lector = fechas.Lector(unidades={"p/faro", "p/molino"},
                               buscar=lambda clave, valor: {"70": "p/faro"}.get(valor, "") if clave == "codigo" else "")
        return fechas.leer_documento(texto, archivo="equipo/calendario.md", proyecto="", mapa=mapas.mapa_de("s", mapa),
                                     lector=lector, es_de_unidad=False)

    def test_traduce_las_columnas_el_formato_y_el_vocabulario(self):
        leidas = self.leer()
        taller, aspas = leidas.fechas
        self.assertEqual((taller.inicio, taller.hora, taller.titulo, taller.clase, taller.estado, taller.responsable,
                          taller.proyecto), (date(2026, 6, 18), "10:00", "Taller de luz · 1", "sesion", "hecho", "Ana", "p/faro"))
        # una plantilla con una columna vacía no deja el separador suelto
        self.assertEqual(aspas.titulo, "Aspas")
        self.assertEqual(aspas.estado, "pendiente")

    def test_lo_que_no_calza_con_el_patron_o_no_encuentra_su_proyecto_se_dice(self):
        saltadas = self.leer().saltadas
        self.assertTrue(any("leída sin proyecto: ninguna unidad dice codigo: 140" in s for s in saltadas), saltadas)
        self.assertTrue(any("«3 al 5-jun» no calza" in s for s in saltadas), saltadas)

    def test_un_rango_en_una_celda_y_el_año_del_mapa(self):
        mapa = {"secciones": "## Junio", "campos": {"inicio": {"columna": "Fecha", "formato": "d-MMM", "rango": " al ", "año": 2025}}}
        visita = [f for f in self.leer(mapa).fechas if f.inicio.year == 2025]
        self.assertEqual([(f.inicio, f.fin, f.clase) for f in visita], [(date(2025, 6, 3), date(2025, 6, 5), "actividad")])

    def test_sin_mapa_una_fila_de_un_documento_compartido_es_de_la_unidad_de_su_enlace(self):
        texto = "## Cronograma\n\n| Hito | Fecha | Dónde |\n|---|---|---|\n| Cierre | 2026-12-01 | [Faro](../p/faro/README.md) |\n"
        f = fechas.leer_documento(texto, archivo="equipo/plan.md", proyecto="", lector=fechas.Lector(unidades={"p/faro"}),
                                  es_de_unidad=False).fechas[0]
        self.assertEqual(f.proyecto, "p/faro")

    def test_un_mapa_mal_escrito_dice_donde(self):
        from telar import mapas

        for malo, dice in (({"campos": {"fecha": "x"}}, "campos.fecha"), ({"otra": 1}, "otra"),
                           ({"campos": {"inicio": {"formato": "!!"}}}, "formato"),
                           ({"campos": {"inicio": {"columna": "F", "año": "ayer"}}}, "año")):
            with self.assertRaisesRegex(mapas.ErrorDeMapa, dice):
                mapas.mapa_de("m", malo)


class Escribir(Prueba):
    """Cambiar una fecha en su documento: solo sus celdas, con su forma, y su id la primera vez."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "p").mkdir()
        self.doc = self.raiz / "p" / "README.md"
        self.doc.write_text("# Faro\n\n## Cronograma\n\n| Actividad | Inicio | Fin | Estado |\n|---|---|---|---|\n"
                            "| Montar | 2026-10-01 | 2026-10-10 | ✅ |\n| Inaugurar | 05/11/2026 |  | ⬜ |\n"
                            "| Pintar | 2026-08 | | |\n")

    def leer(self):
        return fechas.leer_documento(self.doc.read_text(), archivo="p/README.md", proyecto="p").fechas

    def test_mover_corre_el_fin_lo_mismo_y_le_pone_su_id(self):
        montar = self.leer()[0]
        self.assertEqual(montar.editable, ("inicio", "fin"))
        f = fechas.escribir_en_documento(self.raiz, montar.id, inicio=date(2026, 10, 3), version=montar.version)
        self.assertEqual((f.inicio, f.fin), (date(2026, 10, 3), date(2026, 10, 12)))
        self.assertRegex(f.id, r"^p/README.md#f-[0-9a-f]{6}$")
        fila = self.doc.read_text().splitlines()[6]
        self.assertRegex(fila, r"^\| Montar \| 2026-10-03 \| 2026-10-12 \| ✅ <!-- id: f-[0-9a-f]{6} --> \|$")
        # por su id se la encuentra aunque el documento cambie arriba
        self.doc.write_text("intro\n" + self.doc.read_text())
        f = fechas.escribir_en_documento(self.raiz, f.id, fin=date(2026, 10, 20))
        self.assertEqual((f.inicio, f.fin), (date(2026, 10, 3), date(2026, 10, 20)))

    def test_cada_celda_con_su_forma_y_un_dia_sigue_siendo_un_dia(self):
        inaugurar = self.leer()[1]
        f = fechas.escribir_en_documento(self.raiz, inaugurar.id, inicio=date(2026, 11, 6))
        self.assertEqual((f.inicio, f.fin), (date(2026, 11, 6), date(2026, 11, 6)))
        self.assertIn("| Inaugurar | 06/11/2026 |  |", self.doc.read_text())

    def test_lo_que_cambio_o_no_se_sabe_escribir_no_toca_nada(self):
        antes = self.doc.read_text()
        montar, _, pintar = self.leer()
        with self.assertRaises(fechas.ErrorDeFecha) as e:
            fechas.escribir_en_documento(self.raiz, montar.id, inicio=date(2026, 10, 3), version="otra")
        self.assertEqual(e.exception.codigo, 409)
        # un mes entero no tiene una forma que telar sepa escribir
        self.assertEqual(pintar.editable, ())
        with self.assertRaises(fechas.ErrorDeFecha) as e:
            fechas.escribir_en_documento(self.raiz, pintar.id, inicio=date(2026, 9, 1))
        self.assertEqual(e.exception.codigo, 422)
        with self.assertRaises(fechas.ErrorDeFecha) as e:
            fechas.escribir_en_documento(self.raiz, "p/README.md:99", inicio=date(2026, 9, 1))
        self.assertEqual(self.doc.read_text(), antes)

    def test_solo_la_fecha_de_la_celda_y_lo_demas_queda(self):
        self.doc.write_text("## Cronograma\n\n| Actividad | Inicio | Fin |\n|---|---|---|\n"
                            "| Taller | 2026-08-12 10:00 | |\n| Visita | lunes 5-oct (por confirmar) | |\n"
                            "| Doble | 30-jun a 3-jul | |\n")
        taller, visita, doble = self.leer()
        fechas.escribir_en_documento(self.raiz, taller.id, inicio=date(2026, 8, 14))
        fechas.escribir_en_documento(self.raiz, visita.id, inicio=date(2026, 11, 17))
        texto = self.doc.read_text()
        self.assertIn("| Taller | 2026-08-14 10:00 |", texto)
        self.assertIn("| Visita | martes 17-nov (por confirmar) |", texto)
        # dos fechas en una celda: no se sabe cuál mover, y se dice
        self.assertEqual(doble.editable, ())
        self.assertIn("sin perder lo que dice", doble.bloqueo)

    def test_un_mes_entero_dice_por_que_no_se_mueve(self):
        pintar = self.leer()[2]
        self.assertEqual(pintar.editable, ())
        self.assertIn("mes entero", pintar.bloqueo)

    def test_con_el_patron_de_su_mapa(self):
        from telar import mapas

        self.doc.write_text("## Junio\n\n| Fecha | Qué |\n|---|---|\n| jue 18-jun | Taller |\n")
        m = mapas.Mapas(por_nombre={"s": mapas.mapa_de("s", {"secciones": "## Junio", "campos": {
            "inicio": {"columna": "Fecha", "formato": "EEE d-MMM", "año": 2026}}})}, documentos=[("p/README.md", "s")])
        f = fechas.escribir_en_documento(self.raiz, "p/README.md:5", inicio=date(2026, 11, 17), mapas=m)
        self.assertEqual(f.inicio, date(2026, 11, 17))
        self.assertIn("| mar 17-nov | Taller <!-- id:", self.doc.read_text())


class LoQueImprimeUnPrograma(Prueba):
    def test_una_lista_un_objeto_o_una_por_linea(self):
        una = {"titulo": "Cierre", "inicio": "2026-12-01", "fuente": "proyectos/faro/x.md:3"}
        for salida in (json.dumps([una]), json.dumps({"fechas": [una]}), json.dumps(una) + "\n"):
            leidas = prov.leer_salida(salida, "gestion", {"proyectos/faro"})
            self.assertEqual([(f.titulo, f.clase, f.proyecto) for f in leidas.fechas], [("Cierre", "evento", "proyectos/faro")])

    def test_la_que_no_se_entiende_se_dice_y_las_demas_llegan(self):
        salida = json.dumps([{"titulo": "Bien", "inicio": "2026-12-01", "fin": "2026-12-09", "estado": "✅"},
                             {"titulo": "Mal", "inicio": "mañana"}, {"inicio": "2026-01-01"},
                             {"titulo": "Clase rara", "inicio": "2026-01-01", "clase": "fiesta"}])
        leidas = prov.leer_salida(salida, "gestion", set())
        self.assertEqual([(f.titulo, f.clase, f.estado) for f in leidas.fechas], [("Bien", "actividad", "hecho")])
        self.assertEqual(len(leidas.saltadas), 3)
        with self.assertRaises(ErrorDeProveedor):
            prov.leer_salida("esto no es json", "gestion", set())

    def test_un_comando_que_falla_es_un_error_del_proveedor(self):
        cfg = Proveedor(nombre="gestion", activo=True, opciones={"como": "fechas", "tipo": "comando", "comando": ["false"]})
        with self.assertRaises(ErrorDeProveedor):
            prov.construir(cfg).leer(Path("."), {})

    def test_las_rutas_de_markdown_son_relativas_a_la_raiz(self):
        for rutas in ([], ["/etc/x.md"], ["../afuera.md"]):
            with self.assertRaises(ErrorDeProveedor, msg=rutas):
                prov.construir(Proveedor(nombre="f", activo=True, opciones={"tipo": "markdown", "rutas": rutas}))
        # no son pendientes del día
        self.assertEqual(prov.construir(Proveedor(nombre="f", activo=True,
                                                  opciones={"tipo": "markdown", "rutas": ["x.md"]})).consultar(date.today()), [])


class Filtrar(Prueba):
    def test_por_proyecto_y_por_intervalo(self):
        a = fechas.Fecha(id="a", titulo="a", inicio=date(2026, 1, 1), fin=date(2026, 1, 31), proyecto="p/faro")
        b = fechas.Fecha(id="b", titulo="b", inicio=date(2026, 3, 1), fin=date(2026, 3, 1), proyecto="p/faro/sub")
        c = fechas.Fecha(id="c", titulo="c", inicio=date(2026, 2, 1), fin=date(2026, 2, 1), proyecto="p/faros")
        self.assertEqual([f.id for f in fechas.filtrar([b, c, a], proyecto="p/faro")], ["a", "b"])
        self.assertEqual([f.id for f in fechas.filtrar([b, c, a], desde=date(2026, 1, 15), hasta=date(2026, 2, 15))], ["a", "c"])
        self.assertEqual(fechas.unidad_de("p/faro/sub/x.md", {"p", "p/faro", "p/faros"}), "p/faro")


class LaOrden(Prueba):
    """`telar fechas` sobre el repositorio de ejemplo, con un cronograma y un calendario compartido."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name) / "ejemplo"
        shutil.copytree(EJEMPLO, self.raiz)
        os.environ["TELAR_RAIZ"] = str(self.raiz)
        faro = self.raiz / "proyectos" / "faro" / "README.md"
        faro.write_text(faro.read_text() + "\n## Cronograma\n\n| Actividad | Inicio | Fin |\n|---|---|---|\n| Giro | 2026-10-11 | 2026-10-20 |\n")
        (self.raiz / "equipo" / "calendario.md").write_text(
            "# Calendario\n\n## Cronograma\n\n| Sesión | Fecha |\n|---|---|\n| Taller | 2026-11-03 |\n")

    def correr(self, *argv, config=""):
        from telar import cli

        if config:
            ruta = Path(self.tmp.name) / "config.toml"
            ruta.write_text(config)
            os.environ["TELAR_CONFIG"] = str(ruta)
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = cli.main(["fechas", *argv])
        self.assertEqual(codigo, 0, salida.getvalue())
        return json.loads(salida.getvalue()) if "--json" in argv else salida.getvalue()

    def test_las_de_los_documentos_de_las_unidades_sin_declarar_nada(self):
        d = self.correr("--json")
        self.assertEqual([(f["titulo"], f["proyecto"]) for f in d["fechas"]], [("Giro", "proyectos/faro")])
        self.assertEqual(d["fallas"], [])

    def test_un_proveedor_markdown_suma_otros_documentos(self):
        d = self.correr("--json", config='[proveedores.fechas]\ntipo = "markdown"\nrutas = ["equipo/*.md"]\n')
        self.assertEqual([f["titulo"] for f in d["fechas"]], ["Giro", "Taller"])

    def test_un_proveedor_caido_se_dice_y_lo_demas_llega(self):
        d = self.correr("--json", config='[proveedores.gestion]\ncomo = "fechas"\ntipo = "comando"\ncomando = ["false"]\n')
        self.assertEqual([f["titulo"] for f in d["fechas"]], ["Giro"])
        self.assertTrue(d["fallas"][0].startswith("gestion: "))

    def test_un_mapa_del_repositorio_lee_un_calendario_compartido(self):
        (self.raiz / ".telar" / "fechas.yaml").write_text(
            "version: 1\nmapas:\n  sesiones:\n    secciones: '## Junio'\n    campos:\n      clase: sesion\n"
            "      inicio: { columna: Fecha, formato: 'EEE d-MMM', año: 2026 }\n"
            "documentos:\n  - { ruta: equipo/agenda.md, mapa: sesiones }\n")
        (self.raiz / "equipo" / "agenda.md").write_text(
            "## Junio\n\n| Fecha | Qué | Proyecto |\n|---|---|---|\n| jue 18-jun | Taller | [Faro](../proyectos/faro/README.md) |\n")
        d = self.correr("--json")
        taller = next(f for f in d["fechas"] if f["titulo"] == "Taller")
        self.assertEqual((taller["inicio"], taller["clase"], taller["proyecto"]), ("2026-06-18", "sesion", "proyectos/faro"))
        p = self.correr("probar", "equipo/agenda.md", "--json")
        self.assertEqual((p["mapa"], len(p["fechas"])), ("sesiones", 1))

    def test_un_fechas_yaml_roto_es_una_falla_y_lo_demas_llega(self):
        (self.raiz / ".telar" / "fechas.yaml").write_text("mapas:\n  m:\n    campos:\n      fecha: x\n")
        d = self.correr("--json")
        self.assertEqual([f["titulo"] for f in d["fechas"]], ["Giro"])
        self.assertIn(".telar/fechas.yaml", d["fallas"][0])

    def test_un_modulo_trae_su_fuente_de_fechas_y_corre_en_su_carpeta(self):
        modulo = Path(self.tmp.name) / "hitos"
        (modulo / "bin").mkdir(parents=True)
        (modulo / "modulo.toml").write_text('descripcion = "hitos"\n[fechas]\ncomando = ["bin/fechas"]\n')
        guion = modulo / "bin" / "fechas"
        guion.write_text('#!/bin/sh\necho \'{"titulo": "Hito de \'"$(basename "$PWD")"\'", "inicio": "2026-12-01", '
                         '"clase": "hito", "proyecto": "proyectos/molino"}\'\n')
        guion.chmod(0o755)
        d = self.correr("--json", config=f'[modulos.hitos]\ncarpeta = "{modulo}"\n')
        hito = next(f for f in d["fechas"] if f["clase"] == "hito")
        self.assertEqual((hito["titulo"], hito["proyecto"]), ("Hito de hitos", "proyectos/molino"))

    def test_telar_fecha_escribe_y_un_lienzo_pide_permiso(self):
        from telar import cli, concesiones
        from telar.config import cargar as cargar_config
        from telar.servicios import ErrorDeServicio, lienzos

        giro = next(f for f in self.correr("--json")["fechas"] if f["titulo"] == "Giro")
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(cli.main(["fecha", giro["id"], "--inicio", "2026-10-13", "--json"]), 0)
        quedo = json.loads(salida.getvalue())
        self.assertEqual((quedo["inicio"], quedo["fin"]), ("2026-10-13", "2026-10-22"))
        # un lienzo de un módulo: solo lo declarado y concedido
        modulo = Path(self.tmp.name) / "g"
        modulo.mkdir()
        (modulo / "modulo.toml").write_text('[pestana]\ncomando = ["x"]\n[permisos]\nordenes = ["fecha"]\n')
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text(f'[modulos.g]\ncarpeta = "{modulo}"\n')
        os.environ["TELAR_CONFIG"] = str(ruta)
        from telar.cli import Contexto

        ctx = Contexto(config=cargar_config(None))
        pedido = {"id": quedo["id"], "inicio": "2026-10-14"}
        with self.assertRaises(ErrorDeServicio) as e:
            lienzos.pedir(ctx, "bloque:g", "fecha", pedido)
        self.assertEqual((e.exception.codigo, e.exception.datos["permiso"]["modulo"]), (403, "g"))
        with self.assertRaises(ErrorDeServicio):
            lienzos.pedir(ctx, "bloque:otro", "fecha", pedido)   # no es de un módulo
        lienzos.conceder(ctx, "g", "fecha", "concedido")
        self.assertEqual(lienzos.pedir(ctx, "bloque:g", "fecha", pedido)["datos"]["inicio"], "2026-10-14")
        lienzos.conceder(ctx, "g", "fecha", "olvidar")
        self.assertEqual(concesiones.decision(ctx.config, "g", "fecha"), "")

    def test_por_proyecto_y_en_texto(self):
        self.assertEqual(self.correr("--json", "--proyecto", "proyectos/molino")["fechas"], [])
        self.assertIn("Giro", self.correr())


@unittest.skipUnless(HAY_FASTAPI, "sin fastapi")
class LaApi(Prueba):
    def test_get_fechas_es_lo_mismo_que_la_cli_y_pasa_sus_parametros(self):
        from types import SimpleNamespace
        from unittest import mock

        from fastapi.testclient import TestClient

        from telar import api
        from telar.ordenes import fechas as orden
        from telar.servicios import fechas as servicio

        valor = servicio.Fechas(fechas=[{"id": "a", "titulo": "Giro", "inicio": "2026-10-11", "extra": 1}], fallas=["x: no"])
        with mock.patch.object(api, "_refrescar", mock.AsyncMock()), \
                mock.patch.object(servicio, "lista", return_value=valor) as lista:
            salida = io.StringIO()
            with redirect_stdout(salida):
                orden.main(["--json"], SimpleNamespace(config=SimpleNamespace()))
            r = TestClient(api.app).get("/fechas", params={"proyecto": "p/faro", "desde": "2026-10-01"})
        self.assertEqual(json.loads(salida.getvalue()), r.json())
        self.assertEqual(lista.call_args.kwargs, {"proyecto": "p/faro", "desde": date(2026, 10, 1), "hasta": None})


if __name__ == "__main__":
    unittest.main()
