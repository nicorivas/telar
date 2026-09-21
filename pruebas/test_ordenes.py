"""Las órdenes de la CLI, contra el workspace de ejemplo y sin multiplexor vivo.

Todo esto corre sin tmux ni zellij: un telar sin multiplexor sigue sabiendo lo que
guardó y lo que dicen los documentos, y eso es justo lo que hay que poder probar en
una máquina limpia. Lo que sí necesita un multiplexor (tejer, ir, llevar un
pendiente a un hilo) se prueba por su decisión, no por su efecto.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cli


class Orden(Prueba):
    """Cada prueba, su propio estado y su propia sesión: nada heredado, nada compartido."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["TELAR_ESTADO"] = str(Path(self.tmp.name) / "estado")
        os.environ["TELAR_RAIZ"] = str(EJEMPLO)
        # una sesión que no existe en ninguna parte: el multiplexor no debe tener nada que decir
        os.environ["TELAR_SESION"] = f"telar-pruebas-{uuid.uuid4().hex[:8]}"

    def correr(self, *argv: str) -> tuple[int, str, str]:
        salida, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = cli.main(list(argv))
        return codigo, salida.getvalue(), error.getvalue()

    def json_de(self, *argv: str) -> dict:
        codigo, salida, error = self.correr(*argv)
        self.assertEqual(codigo, 0, f"{argv} falló: {error}")
        return json.loads(salida)

    def vincular_faro(self) -> None:
        codigo, _, error = self.correr("vincular", "proyectos/faro", "--hilo", "faro")
        self.assertEqual(codigo, 0, error)

    def ancho(self, columnas: int) -> None:
        """Fija el ancho de la terminal: sin esto, cada máquina corta las líneas distinto."""
        previo = os.environ.get("COLUMNS")

        def devolver() -> None:
            if previo is None:
                os.environ.pop("COLUMNS", None)
            else:
                os.environ["COLUMNS"] = previo

        os.environ["COLUMNS"] = str(columnas)
        self.addCleanup(devolver)


class Hilos(Orden):
    def test_sin_hilos_lo_dice_y_sale_bien(self):
        codigo, salida, _ = self.correr("hilos")
        self.assertEqual(codigo, 0)
        self.assertIn("0 hilos", salida)

    def test_un_hilo_vinculado_aparece_con_su_ficha(self):
        self.vincular_faro()
        datos = self.json_de("hilos", "--json")
        hilo = next(h for h in datos["hilos"] if h["nombre"] == "faro")
        self.assertEqual(hilo["relativa"], "proyectos/faro")
        self.assertEqual(hilo["arquetipo"], "proyecto")
        self.assertEqual(hilo["ficha"]["titulo"], "Faro")
        self.assertFalse(hilo["vivo"])  # no hay sesión: se dice, no se miente

    def test_el_json_trae_las_claves_del_contrato(self):
        datos = self.json_de("hilos", "--json")
        self.assertEqual(
            set(datos), {"sesion", "viva", "raiz", "multiplexor", "aviso", "orden", "hilos"}
        )

    def test_sin_ficha_no_lee_documentos(self):
        self.vincular_faro()
        datos = self.json_de("hilos", "--json", "--sin-ficha")
        self.assertNotIn("ficha", datos["hilos"][0])

    def test_la_cabecera_no_cuenta_lo_que_no_tiene_ventana(self):
        # el hilo existe en el estado y en ningún multiplexor: contarlo entre los
        # abiertos anunciaría un tab que no está en la pantalla de nadie
        self.vincular_faro()
        codigo, salida, _ = self.correr("hilos")
        self.assertEqual(codigo, 0)
        self.assertIn("0 hilos", salida)
        self.assertIn("1 sin ventana", salida)


class UnHilo(Orden):
    def test_vincular_fuera_de_la_raiz_se_rechaza(self):
        codigo, _, error = self.correr("hilo", "vincular", "/", "--hilo", "x")
        self.assertEqual(codigo, 2)
        self.assertIn("fuera de la raíz", error)

    def test_vincular_a_algo_que_el_perfil_no_declara_avisa_pero_vincula(self):
        codigo, salida, _ = self.correr("hilo", "vincular", "notas", "--hilo", "n")
        self.assertEqual(codigo, 0)
        self.assertIn("no declara esa ruta", salida)

    def test_prioridad_y_archivo_quedan_guardados(self):
        self.vincular_faro()
        self.correr("hilo", "prioridad", "1", "--hilo", "faro")
        self.correr("hilo", "archivar", "--hilo", "faro")
        hilo = self.json_de("hilos", "--json")["hilos"][0]
        self.assertEqual(hilo["prioridad"], 1)
        self.assertTrue(hilo["archivado"])

    def test_prioridad_inventada_se_rechaza(self):
        codigo, _, error = self.correr("hilo", "prioridad", "9", "--hilo", "faro")
        self.assertEqual(codigo, 2)
        self.assertIn("1 (alta)", error)

    def test_renombrar_se_lleva_el_vinculo(self):
        self.vincular_faro()
        codigo, salida, _ = self.correr("hilo", "renombrar", "Faro norte", "--hilo", "faro")
        self.assertEqual(codigo, 0)
        hilos = self.json_de("hilos", "--json")["hilos"]
        self.assertEqual([h["nombre"] for h in hilos], ["Faro norte"])
        self.assertEqual(hilos[0]["relativa"], "proyectos/faro")

    def test_renombrar_a_un_nombre_ocupado_se_rechaza(self):
        self.vincular_faro()
        self.correr("vincular", "proyectos/molino", "--hilo", "molino")
        codigo, _, error = self.correr("hilo", "renombrar", "molino", "--hilo", "faro")
        self.assertEqual(codigo, 2)
        self.assertIn("ya hay un hilo", error)

    def test_renombrar_a_un_nombre_sin_ventana_manda_a_adoptar(self):
        # es el caso de verdad: el nombre lo ocupa el estado que quedó colgado cuando
        # el tab se renombró desde el multiplexor, y ahí renombrar no es la salida
        self.vincular_faro()
        self.correr("vincular", "proyectos/molino", "--hilo", "molino")
        codigo, _, error = self.correr("hilo", "renombrar", "molino", "--hilo", "faro")
        self.assertEqual(codigo, 2)
        self.assertIn("adoptar", error)

    def test_adoptar_recoge_el_estado_que_quedo_colgado_de_otro_nombre(self):
        self.vincular_faro()
        self.correr("hilo", "prioridad", "1", "--hilo", "faro")
        self.correr("atencion", "set", "espera", "--hilo", "faro")
        codigo, salida, error = self.correr("hilo", "adoptar", "faro", "--hilo", "faro-nuevo")
        self.assertEqual(codigo, 0, error)
        self.assertIn("adoptó", salida)
        hilos = self.json_de("hilos", "--json")["hilos"]
        self.assertEqual([h["nombre"] for h in hilos], ["faro-nuevo"])
        self.assertEqual(hilos[0]["relativa"], "proyectos/faro")
        self.assertEqual(hilos[0]["prioridad"], 1)
        self.assertEqual(hilos[0]["atencion"], "espera")

    def test_adoptar_no_pisa_lo_que_el_hilo_ya_tenia(self):
        self.vincular_faro()
        self.correr("hilo", "prioridad", "3", "--hilo", "faro")
        self.correr("vincular", "proyectos/molino", "--hilo", "molino")
        codigo, _, error = self.correr("hilo", "adoptar", "faro", "--hilo", "molino")
        self.assertEqual(codigo, 0, error)
        hilo = self.json_de("hilos", "--json")["hilos"][0]
        self.assertEqual(hilo["nombre"], "molino")
        self.assertEqual(hilo["relativa"], "proyectos/molino")  # lo suyo manda
        self.assertEqual(hilo["prioridad"], 3)  # lo que le faltaba, lo hereda

    def test_adoptar_un_nombre_que_nadie_conoce_se_rechaza(self):
        codigo, _, error = self.correr("hilo", "adoptar", "inventado", "--hilo", "faro")
        self.assertEqual(codigo, 2)
        self.assertIn("no hay ningún hilo", error)

    def test_adoptar_sin_nombre_y_sin_candidato_lo_dice(self):
        codigo, _, error = self.correr("hilo", "adoptar", "--hilo", "faro")
        self.assertEqual(codigo, 2)
        self.assertIn("sin ventana", error)

    def test_olvidar_borra_lo_que_telar_sabia(self):
        self.vincular_faro()
        self.correr("hilo", "olvidar", "--hilo", "faro")
        self.assertEqual(self.json_de("hilos", "--json")["hilos"], [])


class Ficha(Orden):
    def test_la_ficha_de_un_hilo_trae_el_documento_leido(self):
        self.vincular_faro()
        datos = self.json_de("ficha", "faro", "--json")
        ficha = datos["hilo"]["ficha"]
        self.assertEqual(ficha["titulo"], "Faro")
        self.assertEqual(len(ficha["pendientes"]), 4)
        self.assertEqual(datos["acciones"][0]["nombre"], "revisar")

    def test_en_texto_las_secciones_de_lista_se_leen(self):
        """Esperando e hitos llegan como diccionarios del contrato, no como cadenas."""
        self.vincular_faro()
        self.ancho(100)
        codigo, salida, error = self.correr("ficha", "faro")
        self.assertEqual(codigo, 0, error)
        self.assertNotIn("{'", salida)  # ningún dict de Python impreso crudo
        self.assertIn("· El electricista confirma si el motor viejo sirve de repuesto", salida)
        self.assertIn("· Entrega — 2026-06-30", salida)  # el hito, con su fecha colgada
        self.assertIn("Encargo: Municipalidad de la costa", salida)  # la tabla, intacta

    def test_en_texto_una_terminal_angosta_recorta_por_el_final(self):
        """Un ancho ridículo acorta la línea; jamás la da vuelta ni se come la fecha."""
        self.vincular_faro()
        self.ancho(10)
        codigo, salida, error = self.correr("ficha", "faro")
        self.assertEqual(codigo, 0, error)
        self.assertIn("· Entrega — 2026-06-30", salida)
        # y lo que corta lo dice: «…» al final, no un corte mudo
        self.assertIn("· El elec…", salida)

    def test_un_hilo_que_no_existe_se_dice(self):
        codigo, _, error = self.correr("ficha", "inventado")
        self.assertEqual(codigo, 2)
        self.assertIn("inventado", error)

    def test_sin_hilo_y_sin_multiplexor_se_dice_en_vez_de_adivinar(self):
        codigo, _, error = self.correr("ficha")
        self.assertEqual(codigo, 2)
        self.assertIn("no sé en qué hilo estoy", error)

    def test_con_la_variable_del_hilo_no_hay_que_adivinar(self):
        self.vincular_faro()
        os.environ["TELAR_HILO"] = "faro"
        datos = self.json_de("ficha", "--json")
        self.assertEqual(datos["hilo"]["nombre"], "faro")
        self.assertTrue(datos["seguro"])


class Pendientes(Orden):
    def test_los_pendientes_del_hilo_traen_su_referencia(self):
        self.vincular_faro()
        datos = self.json_de("pendientes", "--json")
        refs = [p["ref"] for p in datos["pendientes"]]
        self.assertIn("faro:2", refs)
        # los hechos no se muestran salvo que se pidan
        self.assertNotIn("faro:1", refs)

    def test_repo_alcanza_las_unidades_sin_hilo(self):
        datos = self.json_de("pendientes", "--json", "--repo")
        rutas = {p["ruta"] for p in datos["pendientes"]}
        self.assertIn("proyectos/molino", rutas)
        self.assertTrue(all(p["hilo"] == "" for p in datos["pendientes"]))

    def test_donde_iria_un_pendiente_se_puede_preguntar_sin_hacer_nada(self):
        self.vincular_faro()
        codigo, salida, _ = self.correr("pendiente", "faro:2", "--donde")
        self.assertEqual(codigo, 0)
        self.assertIn("faro", salida)

    def test_una_referencia_que_no_existe_se_dice(self):
        codigo, _, error = self.correr("pendiente", "faro:99")
        self.assertEqual(codigo, 2)
        self.assertIn("no encuentro", error)


class Hoy(Orden):
    def test_local_no_consulta_nada_y_lo_declara(self):
        datos = self.json_de("hoy", "--json", "--local")
        self.assertTrue(datos["local"])
        self.assertIsNone(datos["agenda"])
        self.assertEqual(datos["proveedores"]["declarados"], [])

    def test_quien_te_espera_sale_de_la_atencion_anotada(self):
        self.vincular_faro()
        self.correr("atencion", "set", "espera", "--hilo", "faro")
        datos = self.json_de("hoy", "--json", "--local")
        self.assertEqual([h["nombre"] for h in datos["atencion"]], ["faro"])


class Atencion(Orden):
    def test_set_y_get_se_entienden(self):
        self.correr("atencion", "set", "trabajando", "--hilo", "faro")
        datos = self.json_de("atencion", "get", "--hilo", "faro", "--json")
        self.assertEqual(datos["atencion"], "trabajando")
        self.assertTrue(datos["desde"])

    def test_ninguna_borra_la_anotacion(self):
        self.correr("atencion", "set", "espera", "--hilo", "faro")
        self.correr("atencion", "set", "ninguna", "--hilo", "faro")
        self.assertEqual(self.json_de("atencion", "--json")["hilos"], {})

    def test_una_atencion_inventada_se_rechaza(self):
        codigo, _, error = self.correr("atencion", "set", "cansado", "--hilo", "faro")
        self.assertEqual(codigo, 2)
        self.assertIn("no es una atención", error)


class Tiempo(Orden):
    def test_marcar_dos_veces_seguidas_anota_una(self):
        self.assertTrue(self.json_de("tiempo", "marcar", "faro", "--json")["anotado"])
        self.assertFalse(self.json_de("tiempo", "marcar", "faro", "--json")["anotado"])

    def test_el_json_trae_segundos_y_su_rango(self):
        self.correr("tiempo", "marcar", "faro")
        self.correr("tiempo", "marcar", "molino")
        datos = self.json_de("tiempo", "--json")
        self.assertEqual(datos["unidad"], "segundos")
        # el intervalo de «faro» lo cerró «molino» en el mismo segundo y no suma nada;
        # el último queda abierto contra ahora, y ese sí
        self.assertIn("molino", datos["hilos"])
        self.assertEqual(datos["desde"], datos["hasta"])

    def test_un_rango_al_reves_se_rechaza(self):
        codigo, _, error = self.correr("tiempo", "--desde", "2026-09-10", "--hasta", "2026-09-01")
        self.assertEqual(codigo, 2)
        self.assertIn("anterior", error)


class Entorno(Orden):
    def test_config_json_dice_de_donde_salio_cada_cosa(self):
        datos = self.json_de("config", "--json")
        self.assertEqual(datos["raiz"], str(EJEMPLO))
        self.assertIn("raiz", datos["entorno"])  # lo pisó TELAR_RAIZ

    def test_perfil_json_trae_los_arquetipos_y_sus_documentos(self):
        datos = self.json_de("perfil", "--json")
        self.assertEqual(datos["nombre"], "taller")
        proyecto = next(a for a in datos["arquetipos"] if a["nombre"] == "proyecto")
        self.assertEqual(len(proyecto["documentos"]), 3)
        self.assertTrue(proyecto["por_carpeta"])

    def test_doctor_revisa_y_no_toca_nada(self):
        datos = self.json_de("doctor", "--json")
        nombres = {r["nombre"] for r in datos["revisiones"]}
        self.assertLessEqual({"config", "raíz", "perfil", "estado", "proveedores"}, nombres)
        self.assertTrue(all(r["estado"] in ("ok", "aviso", "falla") for r in datos["revisiones"]))

    def test_doctor_sale_con_1_si_hay_una_falla(self):
        # un vínculo a una carpeta que ya no está es una falla, y doctor lo dice
        self.correr("hilo", "vincular", "proyectos/faro", "--hilo", "faro")
        estado = Path(os.environ["TELAR_ESTADO"]) / "vinculos.json"
        estado.write_text('{"faro": "proyectos/se-borro"}\n', encoding="utf-8")
        codigo, salida, _ = self.correr("doctor", "--json")
        self.assertEqual(codigo, 1)
        datos = json.loads(salida)
        self.assertFalse(datos["ok"])

    def test_init_escribe_la_configuracion_y_no_la_pisa_sin_permiso(self):
        destino = Path(self.tmp.name) / "config.toml"
        datos = self.json_de("init", "--en", str(destino), "--json")
        self.assertEqual(datos["escrito"]["config"], str(destino))
        self.assertIn("multiplexor", destino.read_text(encoding="utf-8"))
        de_nuevo = self.json_de("init", "--en", str(destino), "--json")
        self.assertNotIn("config", de_nuevo["escrito"])
        self.assertTrue(any("--forzar" in a for a in de_nuevo["avisos"]))

    def test_init_no_escribe_el_perfil_si_no_se_lo_piden(self):
        destino = Path(self.tmp.name) / "config.toml"
        datos = self.json_de("init", "--en", str(destino), "--json")
        self.assertNotIn("perfil", datos["escrito"])


class Acciones(Orden):
    def test_seco_dice_que_correria_sin_correrlo(self):
        self.vincular_faro()
        codigo, salida, _ = self.correr("accion", "revisar", "--hilo", "faro", "--seco")
        self.assertEqual(codigo, 0)
        self.assertIn("date", salida)
        self.assertFalse((EJEMPLO / "proyectos" / "faro" / "revision.txt").exists())

    def test_una_accion_que_el_perfil_no_declara_se_dice(self):
        codigo, _, error = self.correr("accion", "inventada")
        self.assertEqual(codigo, 2)
        self.assertIn("no declara", error)

    def test_sin_nombre_las_lista(self):
        codigo, salida, _ = self.correr("accion")
        self.assertEqual(codigo, 0)
        self.assertIn("revisar", salida)


class Uso(Orden):
    def test_una_bandera_que_la_orden_no_conoce_no_revienta(self):
        codigo, _, error = self.correr("hilos", "--inventada")
        self.assertEqual(codigo, 2)
        self.assertIn("--help", error)

    def test_la_ayuda_de_una_orden_sale_bien(self):
        codigo, salida, _ = self.correr("hilos", "--help")
        self.assertEqual(codigo, 0)
        self.assertIn("telar hilos", salida)


if __name__ == "__main__":
    unittest.main()
