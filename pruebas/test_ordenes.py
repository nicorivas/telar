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
from types import SimpleNamespace

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import cli
from telar.ordenes import tejer


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
            set(datos), {"sesion", "maquina", "viva", "raiz", "multiplexor", "aviso", "orden", "clientes", "hilos"}
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
    def test_vincular_algo_que_no_existe_se_rechaza(self):
        codigo, _, error = self.correr("hilo", "vincular", "/no/existe/esto", "--hilo", "x")
        self.assertEqual(codigo, 2)
        self.assertIn("no existe", error)

    def test_fuera_de_la_raiz_se_vincula_y_la_ficha_es_su_readme(self):
        afuera = Path(self.tmp.name) / "otro-repo"
        afuera.mkdir()
        (afuera / "README.md").write_text("# Otro repo\n\nalgo\n", encoding="utf-8")
        codigo, _, error = self.correr("hilo", "vincular", str(afuera), "--hilo", "otro")
        self.assertEqual(codigo, 0, error)
        hilo = next(h for h in self.json_de("hilos", "--json")["hilos"] if h["nombre"] == "otro")
        self.assertEqual(hilo["ruta"], str(afuera.resolve()))
        self.assertEqual(hilo["ficha"]["titulo"], "Otro repo")
        self.assertTrue(hilo["ficha"]["documento"].endswith("README.md"))

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

    def test_padre_cuelga_suelta_y_no_hace_circulos(self):
        self.vincular_faro()
        self.correr("vincular", "proyectos/faro", "--hilo", "faro-movil")
        codigo, salida, error = self.correr("hilo", "padre", "faro", "--hilo", "faro-movil")
        self.assertEqual(codigo, 0, error)
        hilos = {h["nombre"]: h for h in self.json_de("hilos", "--json")["hilos"]}
        self.assertEqual(hilos["faro-movil"]["padre"], "faro")
        codigo, _, error = self.correr("hilo", "padre", "faro-movil", "--hilo", "faro")
        self.assertNotEqual(codigo, 0)
        self.assertIn("círculo", error)
        self.correr("hilo", "padre", "ninguno", "--hilo", "faro-movil")
        self.assertEqual({h["nombre"]: h for h in self.json_de("hilos", "--json")["hilos"]}["faro-movil"]["padre"], "")

    def test_archivar_con_hijos(self):
        self.vincular_faro()
        self.correr("vincular", "proyectos/faro", "--hilo", "faro-movil")
        self.correr("hilo", "padre", "faro", "--hilo", "faro-movil")
        codigo, _, error = self.correr("hilo", "archivar", "--con-hijos", "--hilo", "faro")
        self.assertEqual(codigo, 0, error)
        hilos = {h["nombre"]: h for h in self.json_de("hilos", "--json")["hilos"]}
        self.assertTrue(hilos["faro"]["archivado"] and hilos["faro-movil"]["archivado"])

    def test_las_etiquetas_se_ponen_se_ven_y_se_quitan(self):
        self.vincular_faro()
        codigo, salida, _ = self.correr("hilo", "etiquetas", "Trabajo, cliente", "--hilo", "faro")
        self.assertEqual(codigo, 0)
        self.assertIn("trabajo, cliente", salida)
        self.assertEqual(self.json_de("hilos", "--json")["hilos"][0]["etiquetas"], ["trabajo", "cliente"])
        codigo, _, error = self.correr("hilo", "etiquetas", "¡no!", "--hilo", "faro")
        self.assertNotEqual(codigo, 0)
        self.assertIn("no sirve de etiqueta", error)
        self.correr("hilo", "etiquetas", "ninguna", "--hilo", "faro")
        self.assertEqual(self.json_de("hilos", "--json")["hilos"][0]["etiquetas"], [])

    def test_cerrar_lo_saca_de_la_lista(self):
        # cerrar es descartar: lo que se quiere guardar se archiva
        self.vincular_faro()
        self.correr("hilo", "prioridad", "1", "--hilo", "faro")
        codigo, salida, _ = self.correr("hilo", "cerrar", "--hilo", "faro")
        self.assertEqual(codigo, 0)
        self.assertIn("olvidado", salida)
        self.assertEqual(self.json_de("hilos", "--json")["hilos"], [])

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

    def test_olvidar_con_el_nombre_suelto_olvida_ese_y_no_el_actual(self):
        self.vincular_faro()
        codigo, _, error = self.correr("hilo", "olvidar", "faro")
        self.assertEqual(codigo, 0, error)
        self.assertEqual(self.json_de("hilos", "--json")["hilos"], [])

    def test_un_verbo_sin_valor_con_nombre_y_hilo_se_niega(self):
        self.vincular_faro()
        codigo, _, error = self.correr("hilo", "olvidar", "otro", "--hilo", "faro")
        self.assertEqual(codigo, 2)
        self.assertIn("sobra", error)
        self.assertEqual(len(self.json_de("hilos", "--json")["hilos"]), 1)


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
    def test_otro_dia_pide_la_agenda_de_esa_fecha(self):
        from unittest import mock

        from telar import config as mod_config
        from telar.ordenes import pendientes as orden_pendientes

        cal = mock.Mock()
        cal.nombre = "calendario"
        with mock.patch.object(mod_config.Config, "proveedores_activos", return_value=[cal]), \
                mock.patch.object(orden_pendientes, "de_proveedores", return_value=([], [])) as consulta:
            datos = self.json_de("hoy", "--json", "--dia", "2026-02-03")
        self.assertEqual((datos["fecha"], datos["dia"], datos["agenda"]), ("2026-02-03", "martes", []))
        self.assertEqual(consulta.call_args[0][2].isoformat(), "2026-02-03")

    def test_un_dia_mal_escrito_se_dice(self):
        codigo, _, error = self.correr("hoy", "--json", "--dia", "mañana")
        self.assertEqual(codigo, 2)
        self.assertIn("no es un día", error)

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


class ElOrdenEnQueSeAbren(Prueba):
    """`tejer` abre ocho de las que haya: cuáles ocho lo decide el perfil, no el abecedario."""

    @staticmethod
    def _perfil(*nombres):
        return SimpleNamespace(arquetipos=[SimpleNamespace(nombre=n) for n in nombres])

    @staticmethod
    def _unidades(pares):
        return {ruta: (SimpleNamespace(nombre=arq), Path(ruta) / "README.md") for ruta, arq in pares}

    def test_manda_el_orden_en_que_el_perfil_declara_los_arquetipos(self):
        # El caso real: por ruta, «conocimiento/» gana siempre y no se abre un proyecto vivo.
        unidades = self._unidades([
            ("conocimiento/benchmarks", "area"),
            ("conocimiento/ia", "area"),
            ("operacion/proyectos/astillero", "proyecto"),
            ("operacion/proyectos/canteras", "proyecto"),
        ])
        self.assertEqual(
            tejer._primeras(self._perfil("proyecto", "area"), unidades),
            ["operacion/proyectos/astillero", "operacion/proyectos/canteras",
             "conocimiento/benchmarks", "conocimiento/ia"],
        )

    def test_dentro_de_un_arquetipo_sigue_mandando_la_ruta(self):
        unidades = self._unidades([("b", "uno"), ("a", "uno"), ("c", "uno")])
        self.assertEqual(tejer._primeras(self._perfil("uno"), unidades), ["a", "b", "c"])

    def test_un_arquetipo_que_el_perfil_no_declara_va_al_final(self):
        unidades = self._unidades([("z", "forastero"), ("a", "uno")])
        self.assertEqual(tejer._primeras(self._perfil("uno"), unidades), ["a", "z"])

    def test_nunca_abre_mas_que_el_tope(self):
        unidades = self._unidades([(f"p{i:02d}", "uno") for i in range(30)])
        self.assertEqual(len(tejer._primeras(self._perfil("uno"), unidades)), tejer.TOPE)


class HilosRed(unittest.TestCase):
    """`telar hilos --red`: los hilos de las otras máquinas, del registro del bus."""

    def ctx(self, url="nats://x:4222"):
        from types import SimpleNamespace as N
        return N(config=N(bus=N(url=url)))

    def test_deja_fuera_los_de_esta_maquina_y_pone_los_de_las_otras(self):
        from unittest import mock
        from telar import bus as mod_bus
        from telar.ordenes import hilos
        registro = {"Telar": {"nombre": "Telar", "maquina": "laptop", "vivo": True, "atencion": "espera"},
                    "Secretaría": {"nombre": "Secretaría", "maquina": "telar", "vivo": True},
                    "Romero": {"nombre": "Romero", "maquina": "laptop", "vivo": False}}
        with mock.patch.object(mod_bus, "estados", return_value=registro), \
                mock.patch.object(mod_bus, "maquina", return_value="telar"):
            otras, maquinas, aviso = hilos._red(self.ctx())
        self.assertEqual([h["nombre"] for h in otras], ["Romero", "Telar"])
        self.assertEqual({h["nombre"]: h["vivo"] for h in otras}, {"Romero": False, "Telar": True})
        self.assertEqual(aviso, "")

    def test_sin_bus_o_con_el_bus_caido_avisa_y_no_revienta(self):
        from unittest import mock
        from telar import bus as mod_bus
        from telar.ordenes import hilos
        self.assertIn("no hay bus", hilos._red(self.ctx(url=""))[2])
        with mock.patch.object(mod_bus, "estados", side_effect=mod_bus.ErrorDeBus("el bus no responde")):
            otras, _, aviso = hilos._red(self.ctx())
        self.assertEqual(otras, [])
        self.assertIn("no responde", aviso)


if __name__ == "__main__":
    unittest.main()


class Proyectos(Orden):
    def test_lista_todas_las_unidades_con_nombre_y_fecha(self):
        datos = self.json_de("proyectos", "--json")
        faro = next(p for p in datos["proyectos"] if p["ruta"] == "proyectos/faro")
        self.assertEqual(faro["nombre"], "Faro")
        self.assertEqual(faro["arquetipo"], "proyecto")
        self.assertTrue(faro["modificado"])
        self.assertEqual(faro["hilo"], "")
        self.assertFalse(faro["vivo"])
        self.assertTrue(faro["interno"])  # sin cliente: se muestra su nombre
        self.assertEqual(datos["areas"], [])  # el perfil del ejemplo no ordena áreas

    def test_dice_que_hilo_tiene_cada_una(self):
        self.vincular_faro()
        datos = self.json_de("proyectos", "--json")
        faro = next(p for p in datos["proyectos"] if p["ruta"] == "proyectos/faro")
        self.assertEqual(faro["hilo"], "faro")
        self.assertFalse(faro["vivo"])  # vinculado, pero sin tab

    def test_abrir_algo_que_el_perfil_no_declara_se_rechaza(self):
        codigo, _, error = self.correr("proyectos", "abrir", "no/existe")
        self.assertEqual(codigo, 2)

    def test_abrir_sin_ruta_pregunta_cual(self):
        codigo, _, error = self.correr("proyectos", "abrir")
        self.assertEqual(codigo, 2)
        self.assertIn("¿cuál?", error)

    def test_la_plantilla_llena_sus_marcadores_y_deja_los_ajenos(self):
        from telar.ordenes.proyectos import mensaje

        self.assertEqual(mensaje("/pm {ruta} {otro}", ruta="a/b"), "/pm a/b {otro}")

    def test_la_plantilla_de_proyecto_se_configura(self):
        from telar import config as mod_config
        from telar.config import PROYECTO_POR_DEFECTO, ErrorDeConfig

        self.assertEqual(mod_config.desde_dict({}).agente.proyecto, PROYECTO_POR_DEFECTO)
        self.assertEqual(mod_config.desde_dict({"agente": {"proyecto": "/pm {ruta}"}}).agente.proyecto, "/pm {ruta}")
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"agente": {"proyecto": "  "}})


class MensajeDePendiente(Orden):
    def test_con_id_usa_la_plantilla(self):
        from telar.ordenes.pendiente import mensaje

        self.assertEqual(mensaje("/tarea {id}", {"id": "T118", "texto": "algo", "ref": "T118"}), "/tarea T118")

    def test_sin_id_cae_al_texto(self):
        from telar.ordenes.pendiente import mensaje

        fila = {"id": "", "texto": "revisar el contrato", "ref": "faro:2"}
        self.assertEqual(mensaje("Veamos {id}", fila), "revisar el contrato")
        self.assertEqual(mensaje("{ref}: {texto}", fila), "faro:2: revisar el contrato")


class Atajos(Orden):
    def test_se_declaran_por_tecla(self):
        from telar import config as mod_config

        cfg = mod_config.desde_dict({"atajos": {"m": {"nombre": "⚑ correo", "mensaje": "/correo"}}})
        self.assertEqual([(a.tecla, a.nombre, a.mensaje) for a in cfg.atajos], [("m", "⚑ correo", "/correo")])

    def test_una_tecla_del_dashboard_se_acepta_y_doctor_avisa(self):
        """La pestaña le gana y el atajo queda con un clic: la configuración carga igual (la «n» de un atajo
        no puede dejar sin telar a quien la tenía), y doctor lo avisa."""
        from types import SimpleNamespace

        from telar import config as mod_config
        from telar.ordenes import doctor

        cfg = mod_config.desde_dict({"atajos": {"n": {"nombre": "⟳ sincronizar", "mensaje": "/sincronizar"},
                                                "m": {"nombre": "⚑ correo", "mensaje": "/correo"}}})
        self.assertEqual(sorted(a.tecla for a in cfg.atajos), ["m", "n"])
        avisos = doctor._atajos(SimpleNamespace(config=cfg))
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]["estado"], doctor.AVISO)
        self.assertIn("«n»", avisos[0]["dice"])

    def test_sin_mensaje_es_un_error(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"atajos": {"m": {"nombre": "x"}}})

    def test_en_dice_donde_se_muestra(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        cfg = mod_config.desde_dict({"atajos": {
            "m": {"nombre": "x", "mensaje": "y", "en": "correo"},
            "s": {"nombre": "x", "mensaje": "y", "en": "seccion:diario"},
            "n": {"nombre": "x", "mensaje": "y"}}})
        self.assertEqual({a.tecla: a.en for a in cfg.atajos}, {"m": "correo", "s": "seccion:diario", "n": "hoy"})
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"atajos": {"m": {"nombre": "x", "mensaje": "y", "en": ""}}})

    def test_un_atajo_que_no_existe_se_dice(self):
        codigo, _, error = self.correr("atajo", "m")
        self.assertEqual(codigo, 2)
        self.assertIn("no hay atajo", error)


class Secciones(Orden):
    def test_se_declaran_y_reclaman_hilos_por_nombre_o_prefijo(self):
        from telar import config as mod_config

        cfg = mod_config.desde_dict({"secciones": {"diario": {
            "nombre": "Diario", "hilos": ["notas", "◌ rato*"], "home": ["echo", "{}"]}}})
        s = cfg.secciones[0]
        self.assertEqual((s.clave, s.nombre, s.home), ("diario", "Diario", ("echo", "{}")))
        self.assertTrue(s.contiene("notas"))
        self.assertTrue(s.contiene("◌ rato 09/23 11:43"))
        self.assertFalse(s.contiene("notas viejas"))

    def test_una_clave_desconocida_es_un_error(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"secciones": {"x": {"hilo": ["a"]}}})

    def test_el_contrato_de_la_pagina(self):
        from telar.ordenes.seccion import validar

        self.assertEqual(validar({"titulo": "x", "bloques": [{"texto": "hola", "items": [{"titulo": "a"}]}]}), "")
        self.assertIn("bloques", validar({"titulo": "x", "bloques": "no"}))
        self.assertIn("items", validar({"titulo": "x", "bloques": [{"items": ["no"]}]}))

    def test_un_lienzo_es_un_html_que_existe(self):
        from telar.ordenes.seccion import validar

        html = Path(self.tmp.name) / "l.html"
        html.write_text("<canvas></canvas>", encoding="utf-8")
        bien = {"titulo": "x", "bloques": [{"lienzo": {"archivo": str(html), "alto": 200, "params": {"a": "b"}}}]}
        self.assertEqual(validar(bien), "")
        self.assertIn("no existe", validar({"titulo": "x", "bloques": [{"lienzo": {"archivo": "/no/hay.html"}}]}))
        self.assertIn(".html", validar({"titulo": "x", "bloques": [{"lienzo": {"archivo": str(Path(self.tmp.name))}}]}))
        self.assertIn("alto", validar({"titulo": "x", "bloques": [{"lienzo": {"archivo": str(html), "alto": 5}}]}))
        # la memoria es un .json absoluto, que puede no existir todavía (lo crea el panel al guardar)
        memoria = str(Path(self.tmp.name) / "nueva" / "m.json")
        self.assertEqual(validar({"titulo": "x", "bloques": [{"lienzo": {"archivo": str(html), "memoria": memoria}}]}), "")
        self.assertIn("memoria", validar({"titulo": "x", "bloques": [{"lienzo": {"archivo": str(html), "memoria": "m.json"}}]}))
        self.assertIn("memoria", validar({"titulo": "x", "bloques": [{"lienzo": {"archivo": str(html), "memoria": "/tmp/m.txt"}}]}))

    def test_la_orden_corre_el_home_y_devuelve_su_json(self):
        import sys

        ruta = Path(self.tmp.name) / "config.toml"
        codigo = 'import json; print(json.dumps({"titulo": "Diario", "bloques": []}))'
        ruta.write_text(
            f'[secciones.diario]\nnombre = "Diario"\nhome = [{json.dumps(sys.executable)}, "-c", {json.dumps(codigo)}]\n',
            encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)
        self.assertEqual(self.json_de("seccion", "diario", "--json")["titulo"], "Diario")


class Apps(Orden):
    def test_cada_app_tiene_una_sola_fuente(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        cfg = mod_config.desde_dict({"apps": {
            "babel": {"descripcion": "un juego", "pagina": ["x", "--json"]},
            "vivero": {"nombre": "Vivero", "archivo": "/a/vivero.html", "memoria": "/a/v.json"},
            "pixel": {"url": "http://telar:8790"}}})
        self.assertEqual([(a.clave, a.nombre, a.fuente) for a in cfg.apps],
                         [("babel", "babel", "pagina"), ("vivero", "Vivero", "archivo"), ("pixel", "pixel", "url")])
        for mal in ({}, {"pagina": ["x"], "url": "http://a"}, {"archivo": "rel.html"}, {"archivo": "/a.txt"},
                    {"url": "ftp://a"}, {"url": "http://a", "memoria": "/m.json"}, {"pagina": "x"},
                    {"url": "http://a", "otra": 1}):
            with self.assertRaises(ErrorDeConfig, msg=mal):
                mod_config.desde_dict({"apps": {"a": mal}})

    def test_las_tres_fuentes_dan_una_pagina_del_contrato(self):
        import sys

        from telar import config as mod_config
        from telar.ordenes.app import pagina
        from telar.ordenes.seccion import validar

        html = Path(self.tmp.name) / "v.html"
        html.write_text("<canvas></canvas>", encoding="utf-8")
        codigo = 'import json; print(json.dumps({"bloques": []}))'
        cfg = mod_config.desde_dict({"apps": {
            "juego": {"pagina": [sys.executable, "-c", codigo]},
            "vivero": {"archivo": str(html), "memoria": "/a/v.json"},
            "atlas": {"url": "http://telar:8790", "descripcion": "el mapa"}}})
        juego, vivero, atlas = (pagina(a)[0] for a in cfg.apps)
        self.assertEqual(juego["titulo"], "juego")   # sin título propio, el de la app
        self.assertEqual(vivero["bloques"][0]["lienzo"], {"archivo": str(html), "alto": "lleno", "memoria": "/a/v.json"})
        self.assertEqual(atlas["bloques"][0]["marco"]["url"], "http://telar:8790")
        self.assertEqual(atlas["acciones"][0]["enlace"], "http://telar:8790")
        for p in (juego, vivero, atlas):
            self.assertEqual(validar(p), "", p)
        falta = mod_config.desde_dict({"apps": {"x": {"archivo": "/no/hay.html"}}}).apps[0]
        self.assertIn("no existe", pagina(falta)[1])

    def test_el_marco_y_el_alto_lleno(self):
        from telar.ordenes.seccion import validar

        self.assertEqual(validar({"titulo": "x", "bloques": [{"marco": {"url": "https://a.b", "alto": "lleno"}}]}), "")
        self.assertIn("url", validar({"titulo": "x", "bloques": [{"marco": {"url": "file:///a"}}]}))
        self.assertIn("alto", validar({"titulo": "x", "bloques": [{"marco": {"url": "http://a", "alto": "todo"}}]}))

    def test_la_orden_lista_y_devuelve_la_pagina(self):
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text('[apps.atlas]\nurl = "http://telar:8790"\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)
        self.assertEqual(self.json_de("app", "--json")["apps"][0]["fuente"], "url")
        self.assertEqual(self.json_de("app", "atlas", "--json")["titulo"], "atlas")


class Modulos(Orden):
    def _modulo(self, nombre="nino34", extra=""):
        carpeta = Path(self.tmp.name) / nombre
        (carpeta / "bin").mkdir(parents=True, exist_ok=True)
        (carpeta / "bin" / "dibujar").write_text("#!/bin/sh\n", encoding="utf-8")
        (carpeta / "modulo.toml").write_text(
            'descripcion = "el mar"\n'
            '[pestana]\nnombre = "niño 3.4"\ncomando = ["bin/dibujar", "pagina"]\n'
            '[app]\narchivo = "app.html"\n'
            '[periodicos.bajar]\ncuando = "30 7 * * *"\ncomando = "bin/dibujar bajar"\n'
            '[resultado]\ncarpeta = "~/.local/state/nino34"\n' + extra, encoding="utf-8")
        return carpeta

    def test_lo_que_aporta_se_suma_a_la_configuracion(self):
        from telar import config as mod_config

        carpeta = self._modulo()
        cfg = mod_config.desde_dict({"periodicos": {"en": "servidor"},
                                     "modulos": {"nino34": {"carpeta": str(carpeta)}}})
        m = cfg.modulos[0]
        self.assertEqual(m.aporta, ["pestaña", "app", "periódico nino34-bajar", "resultado"])
        b = cfg.bloques[0]
        self.assertEqual((b.clave, b.nombre, b.comando), ("nino34", "niño 3.4", (str(carpeta.resolve() / "bin/dibujar"), "pagina")))
        self.assertEqual((cfg.apps[0].archivo, cfg.apps[0].descripcion), (str(carpeta.resolve() / "app.html"), "el mar"))
        r = cfg.resultados[0]
        self.assertEqual((r.clave, r.carpeta, r.en), ("nino34", "~/.local/state/nino34", "servidor"))

    def test_un_modulo_apagado_o_que_choca(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        carpeta = self._modulo()
        apagado = mod_config.desde_dict({"modulos": {"nino34": {"carpeta": str(carpeta), "activo": False}}})
        self.assertEqual((apagado.modulos, apagado.bloques), ((), ()))
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"bloques": {"nino34": {"comando": ["x"]}}, "modulos": {"nino34": {"carpeta": str(carpeta)}}})
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"modulos": {"x": {"carpeta": str(Path(self.tmp.name) / "no-hay")}}})
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"modulos": {"x": {"carpeta": str(self._modulo("x", "otra = 1\n"))}}})

    def test_sus_periodicos_corren_en_su_carpeta_y_no_se_escriben(self):
        from telar import config as mod_config
        from telar import periodicos as mod

        carpeta = self._modulo()
        cfg = mod_config.desde_dict({"modulos": {"nino34": {"carpeta": str(carpeta)}}})
        a = mod.con_modulos(mod.Archivo(procesos=[mod.Proceso(nombre="propio", cuando="0 8 * * *", comando="x")]), cfg)
        p = a.por_nombre("nino34-bajar")
        self.assertEqual((p.carpeta, p.modulo, p.descripcion), (str(carpeta.resolve()), "nino34", "el mar"))
        texto = mod.texto(a)
        self.assertIn("[propio]", texto)
        self.assertNotIn("nino34", texto)
        with self.assertRaises(mod.ErrorDePeriodicos):
            mod.con_modulos(mod.Archivo(procesos=[mod.Proceso(nombre="nino34-bajar", cuando="0 8 * * *", comando="x")]), cfg)

    def test_las_pestanas_del_dashboard(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        cfg = mod_config.desde_dict({"dashboard": {"orden": ["ahora", "revisar"], "ocultas": ["plan"]}})
        self.assertEqual((cfg.dashboard_orden, cfg.dashboard_ocultas), (("ahora", "revisar"), ("plan",)))
        with self.assertRaises(ErrorDeConfig):
            mod_config.desde_dict({"dashboard": {"orden": "ahora"}})

    def test_la_orden_y_escribir_las_pestanas(self):
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text(f'[modulos.nino34]\ncarpeta = "{self._modulo()}"\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)
        self.assertEqual(self.json_de("modulos", "--json")["modulos"][0]["nombre"], "nino34")
        self.json_de("config", "--pestanas", "ahora,revisar,-plan", "--json")
        d = self.json_de("config", "--json")["dashboard"]
        self.assertEqual(d, {"orden": ["ahora", "revisar", "plan"], "ocultas": ["plan"]})


class Bloques(Orden):
    def test_se_declaran_con_comando_y_color(self):
        from telar import config as mod_config

        cfg = mod_config.desde_dict({"bloques": {"correo": {"nombre": "correo", "comando": ["x", "--json"], "color": "rojo"}}})
        self.assertEqual([(b.clave, b.nombre, b.comando, b.color) for b in cfg.bloques],
                         [("correo", "correo", ("x", "--json"), "rojo")])
        self.assertEqual(mod_config.desde_dict({"bloques": {"c": {"nombre": "c", "comando": ["x"]}}}).bloques[0].color, "cian")

    def test_un_bloque_es_su_pestana(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        # lo que iba arriba de la pestaña del plan, que se sacó, se deja fuera (test_vistas_config, LaPestanaDelPlanSeSaco)
        cfg = mod_config.desde_dict({"bloques": {"c": {"comando": ["x"], "tecla": "e"}, "r": {"comando": ["y"], "en": "plan"}}})
        self.assertEqual([(x.clave, x.tecla) for x in cfg.bloques], [("c", "e")])
        self.assertEqual(cfg.retirados, (("bloques.r", 'en = "plan"'),))
        for mal in ({"comando": ["x"], "en": "hoy"}, {"comando": ["x"], "tecla": "ee"}):
            with self.assertRaises(ErrorDeConfig, msg=mal):
                mod_config.desde_dict({"bloques": {"c": mal}})

    def test_un_bloque_puede_ser_subpestana_de_una_fija(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        b = mod_config.desde_dict({"bloques": {"g": {"comando": ["x"], "dentro": "proyectos"}}}).bloques[0]
        self.assertEqual(b.dentro, "proyectos")
        self.assertEqual(mod_config.como_vista("bloques", b)["dentro"], "proyectos")
        for mal in ({"comando": ["x"], "dentro": "correo"}, {"comando": ["x"], "dentro": "proyectos", "en": "hoy"}):
            with self.assertRaises(ErrorDeConfig, msg=mal):
                mod_config.desde_dict({"bloques": {"c": mal}})

    def test_lo_mal_declarado_es_un_error(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        for mal in ({"nombre": "c", "comando": []}, {"nombre": "c", "comando": "x"},
                    {"nombre": "c", "comando": ["x"], "color": "fucsia"}, {"nombre": "", "comando": ["x"]},
                    {"nombre": "c", "comando": ["x"], "otra": 1}):
            with self.assertRaises(ErrorDeConfig, msg=mal):
                mod_config.desde_dict({"bloques": {"c": mal}})

    def _config(self, codigo: str) -> None:
        import sys

        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text(f'[bloques.correo]\nnombre = "correo"\n'
                        f'comando = [{json.dumps(sys.executable)}, "-c", {json.dumps(codigo)}]\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)

    def test_la_orden_corre_el_comando_y_devuelve_su_pagina(self):
        self._config('import json; print(json.dumps({"titulo": "correo", "bloques": [{"items": '
                     '[{"titulo": "hola", "marca": "●", "destacado": True}]}]}))')
        pagina = self.json_de("bloque", "correo", "--json")
        self.assertEqual(pagina["bloques"][0]["items"][0]["marca"], "●")

    def test_el_detalle_de_un_item_es_el_comando_con_item(self):
        self._config('import json, sys; i = sys.argv.index("--item"); print(json.dumps({"texto": "cuerpo de " + sys.argv[i + 1]}))')
        self.assertEqual(self.json_de("bloque", "correo", "--item", "1a0d9", "--json"), {"texto": "cuerpo de 1a0d9"})
        self._config('print("no sé")')
        codigo, _, error = self.correr("bloque", "correo", "--item", "1a0d9", "--json")
        self.assertEqual(codigo, 2)
        self.assertIn("1a0d9", error)

    def test_una_pagina_con_otra_forma_sale_con_2(self):
        self._config('print("[]")')
        codigo, _, error = self.correr("bloque", "correo", "--json")
        self.assertEqual(codigo, 2)
        self.assertIn("correo", error)

    def test_mensaje_y_nombre_de_un_item_son_textos(self):
        from telar.ordenes.seccion import validar

        bien = {"titulo": "x", "bloques": [{"items": [{"titulo": "a", "mensaje": "/correo 1a", "nombre": "✉ a"}]}]}
        self.assertEqual(validar(bien), "")
        self.assertIn("mensaje", validar({"titulo": "x", "bloques": [{"items": [{"titulo": "a", "mensaje": 3}]}]}))

    def test_abrir_un_item_sin_sesion_se_dice_y_no_corre_el_comando(self):
        self._config('import sys; sys.exit("no me debían correr")')
        codigo, _, error = self.correr("bloque", "correo", "--abrir", "/correo 1a", "--nombre", "✉ a")
        self.assertEqual(codigo, 2)
        self.assertNotIn("no me debían correr", error)

    def test_un_bloque_que_no_existe_se_dice(self):
        codigo, _, error = self.correr("bloque", "nada")
        self.assertEqual(codigo, 2)
        self.assertIn("no hay bloque", error)


class LeerConversacion(Orden):
    def test_lo_dicho_y_una_linea_por_herramienta(self):
        from telar.agente.claude_code import ClaudeCode

        base = Path(self.tmp.name) / "claude"
        (base / "projects" / "-x").mkdir(parents=True)
        lineas = [
            {"type": "user", "timestamp": "t1", "message": {"content": "<command-message>x</command-message>\n<command-name>/revisar</command-name>"}},
            {"type": "assistant", "timestamp": "t2", "message": {"content": [
                {"type": "thinking", "thinking": ""},
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la", "description": "listar"}},
                {"type": "text", "text": "Listo."}]}},
            {"type": "user", "timestamp": "t3", "message": {"content": [{"type": "tool_result", "content": "..."}]}},
        ]
        (base / "projects" / "-x" / "abc.jsonl").write_text("\n".join(json.dumps(l) for l in lineas), encoding="utf-8")
        os.environ["CLAUDE_CONFIG_DIR"] = str(base)
        self.addCleanup(os.environ.pop, "CLAUDE_CONFIG_DIR", None)
        from telar import config as mod_config

        mensajes = ClaudeCode(mod_config.desde_dict({})).mensajes("abc")
        self.assertEqual([(m["quien"], m["texto"]) for m in mensajes],
                         [("usuario", "/revisar"), ("herramienta", "Bash · listar"), ("agente", "Listo.")])


class NombreDelHiloDeUnPendiente(Orden):
    def test_el_codigo_y_el_tema(self):
        from telar.ordenes.pendiente import _con_nombre

        self.assertEqual(_con_nombre({"ref": "T118", "texto": "Faro 2026: coordinar con el equipo"}),
                         "T118 Faro 2026")

    def test_sin_dos_puntos_las_primeras_palabras(self):
        from telar.ordenes.pendiente import _con_nombre

        self.assertEqual(_con_nombre({"ref": "T21", "texto": "Revisar el borrador del informe con el equipo"}),
                         "T21 Revisar el borrador del…")

    def test_sin_texto_el_codigo(self):
        from telar.ordenes.pendiente import _con_nombre

        self.assertEqual(_con_nombre({"ref": "T9", "texto": ""}), "T9")


class FichaDeTarea(Orden):
    def _config(self, pagina: dict) -> None:
        import sys

        codigo = f"import json; print(json.dumps({pagina!r}))"
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text(
            '[proveedores.tareas]\ntipo = "comando"\ncomando = ["true"]\n'
            f'detalle = [{json.dumps(sys.executable)}, "-c", {json.dumps(codigo)}, "{{id}}"]\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)

    def test_las_acciones_se_validan(self):
        from telar.ordenes.seccion import validar

        bien = {"titulo": "T1", "bloques": [{"texto": "x", "destacado": True, "color": "cian"}],
                "acciones": [{"nombre": "hecha", "comando": ["true"], "principal": True},
                             {"nombre": "hilo", "tipo": "hilo"}, {"nombre": "ver", "tipo": "abrir", "enlace": "https://x"}]}
        self.assertEqual(validar(bien), "")
        self.assertIn("principal", validar({**bien, "acciones": [{"nombre": "a", "comando": ["x"], "principal": True}] * 2}))
        self.assertIn("comando", validar({**bien, "acciones": [{"nombre": "a"}]}))
        self.assertIn("enlace", validar({**bien, "acciones": [{"nombre": "a", "tipo": "abrir"}]}))
        self.assertIn("color", validar({"titulo": "x", "bloques": [{"color": "fucsia"}]}))

    def test_la_ficha_y_una_accion_que_pide_texto(self):
        salida = Path(self.tmp.name) / "salida.txt"
        import sys
        escribir = [sys.executable, "-c", f"import sys; open({str(salida)!r}, 'w').write(sys.argv[1])", "dijo: {texto}"]
        self._config({"titulo": "T1 · algo", "bloques": [], "acciones": [
            {"nombre": "responder", "pide": "qué", "comando": escribir}, {"nombre": "hilo", "tipo": "hilo"}]})
        self.assertEqual(self.json_de("tarea", "T1", "--json")["titulo"], "T1 · algo")
        codigo, _, error = self.correr("tarea", "T1", "--accion", "0")
        self.assertEqual(codigo, 2)
        self.assertIn("pide texto", error)
        self.assertEqual(self.json_de("tarea", "T1", "--accion", "0", "--texto", "sigue viva", "--json")["hecho"], "responder")
        self.assertEqual(salida.read_text(encoding="utf-8"), "dijo: sigue viva")
        self.assertEqual(self.json_de("tarea", "T1", "--accion", "1", "--json")["tipo"], "hilo")

    def test_sin_detalle_se_dice(self):
        codigo, _, error = self.correr("tarea", "T1")
        self.assertEqual(codigo, 2)


class VistaDeLectura(Orden):
    """Un proveedor con pestaña y `vista = "lectura"`: su ficha se dibuja para leer (pagina/src/vistas/dashboard/leer.ts).
    La página sabe cuál por `/config` (pestanas[].vista), doctor revisa el valor, y la ficha puede traer cuatro campos más."""

    def _config(self, cuerpo: str) -> None:
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text(f'[proveedores.lecturas]\ncomo = "tareas"\ntipo = "comando"\ncomando = ["true"]\n{cuerpo}', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)

    def test_config_dice_la_vista_de_cada_pestana(self):
        self._config('pestana = "leer"\ntecla = "l"\nvista = "lectura"\n')
        self.assertEqual(self.json_de("config", "--json")["pestanas"], [{"nombre": "leer", "tecla": "l", "vista": "lectura"}])
        self._config('pestana = "leer"\n')
        self.assertEqual(self.json_de("config", "--json")["pestanas"], [{"nombre": "leer", "tecla": "", "vista": ""}])

    def test_llega_todo_con_de_fecha_y_prioridad(self):
        """Un feed largo llega entero a `telar hoy` (telar no lo corta), cada fila con su prioridad (el nivel: alta P1,
        media P2, baja P3), quién la dejó y su fecha; también si vienen dentro de `campos`."""
        import sys

        filas = [{"id": f"2026-11-{1 + i % 28:02d}-pieza-{i}", "texto": f"pieza {i}",
                  **({"prioridad": ["alta", "media", "baja"][i % 3]} if i % 4 else {}),
                  **({"campos": {"de": "ana"}} if i % 5 == 0 else {"de": "correo"})} for i in range(40)]
        codigo_py = f"import json; print(json.dumps({filas!r}))"
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text('[proveedores.lecturas]\ncomo = "tareas"\ntipo = "comando"\n'
                        f'comando = [{json.dumps(sys.executable)}, "-c", {json.dumps(codigo_py)}]\npestana = "leer"\nvista = "lectura"\n',
                        encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)
        leer = [f for f in self.json_de("hoy", "--json")["pendientes"] if f.get("pestana") == "leer"]
        self.assertEqual(len(leer), 40)
        por_id = {f["id"]: f for f in leer}
        self.assertEqual({k: por_id["2026-11-01-pieza-0"][k] for k in ("de", "fecha", "prioridad")},
                         {"de": "ana", "fecha": "2026-11-01", "prioridad": None})
        self.assertEqual({k: por_id["2026-11-02-pieza-1"][k] for k in ("de", "fecha", "prioridad")},
                         {"de": "correo", "fecha": "2026-11-02", "prioridad": 2})

    def test_doctor_revisa_la_vista(self):
        from types import SimpleNamespace

        from telar import config as mod_config
        from telar.ordenes import doctor

        def revisar(opciones: dict) -> list[dict]:
            cfg = mod_config.desde_dict({"proveedores": {"lecturas": {"como": "tareas", "tipo": "comando", "comando": ["true"], **opciones}}})
            return [r for r in doctor._proveedores(SimpleNamespace(config=cfg)) if r["estado"] != doctor.OK]

        self.assertEqual(revisar({"pestana": "leer", "vista": "lectura"}), [])
        mal = revisar({"pestana": "leer", "vista": "revista"})
        self.assertEqual([r["estado"] for r in mal], [doctor.FALLA])
        self.assertIn("«revista»", mal[0]["dice"])
        sin_pestana = revisar({"vista": "lectura"})
        self.assertEqual([r["estado"] for r in sin_pestana], [doctor.AVISO])

    def test_las_conexiones_elegidas_van_al_comando(self):
        """`{conexiones}` en el comando de una acción: las elegidas, en JSON, solo de las que la ficha propone y con un
        tipo de su vocabulario; sin elegidas, `[]`."""
        import sys

        salida = Path(self.tmp.name) / "salida.txt"
        escribir = [sys.executable, "-c", f"import sys; open({str(salida)!r}, 'w').write(sys.argv[1])", "{conexiones}"]
        pagina = {"titulo": "una lectura",
                  "bloques": [{"texto": "Cae en `obra/c/` y conversa con `notas/a.md`.\n\n- y con\n  `notas/d.md`"},
                              {"titulo": "de dónde salió", "items": [{"titulo": "`notas/e.md`"}]},
                              {"texto": "notas/sin codigo.md, `una frase/con espacio`"}],
                  "conexiones": [{"nota": "notas/a.md", "titulo": "A", "tipo": "informa", "porque": "por a", "ancla": "", "elegida": None},
                                 {"nota": "notas/b.md", "titulo": "B", "tipo": "confirma", "porque": "por b", "ancla": "", "elegida": None}],
                  "tipos": [{"tipo": "informa"}, {"tipo": "confirma"}, {"tipo": "tensiona"}],
                  "acciones": [{"nombre": "guardar", "comando": escribir}]}
        codigo_py = f"import json; print(json.dumps({pagina!r}))"
        ruta = Path(self.tmp.name) / "config.toml"
        ruta.write_text('[proveedores.tareas]\ntipo = "comando"\ncomando = ["true"]\n'
                        f'detalle = [{json.dumps(sys.executable)}, "-c", {json.dumps(codigo_py)}, "{{id}}"]\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(ruta)
        self.addCleanup(os.environ.pop, "TELAR_CONFIG", None)
        # las notas, en la raíz: las que no están no se conectan
        raiz = Path(self.tmp.name) / "raiz"
        for nota in ("notas/a.md", "notas/b.md", "notas/d.md", "obra/c/README.md", "obra/c/otra.md"):
            (raiz / nota).parent.mkdir(parents=True, exist_ok=True)
            (raiz / nota).write_text("# x\n", encoding="utf-8")
        os.environ["TELAR_RAIZ"] = str(raiz)

        elegidas = json.dumps([{"nota": "notas/b.md", "tipo": "tensiona", "porque": "  otro   porqué "}, {"nota": "notas/a.md"}])
        self.assertEqual(self.json_de("tarea", "T1", "--accion", "0", "--conexiones", elegidas, "--json")["hecho"], "guardar")
        self.assertEqual(json.loads(salida.read_text(encoding="utf-8")),
                         [{"nota": "notas/b.md", "tipo": "tensiona", "porque": "otro porqué", "titulo": "B"},
                          {"nota": "notas/a.md", "tipo": "informa", "porque": "por a", "titulo": "A"}])
        self.json_de("tarea", "T1", "--accion", "0", "--json")
        self.assertEqual(json.loads(salida.read_text(encoding="utf-8")), [])
        # una nota que nombra el texto (no propuesta): con tipo del vocabulario y porqué; una carpeta, por su README
        nombradas = json.dumps([{"nota": "obra/c/README.md", "tipo": "informa", "porque": "por c", "titulo": "  La C "},
                                {"nota": "notas/d.md", "tipo": "confirma", "porque": "por d"}])
        self.json_de("tarea", "T1", "--accion", "0", "--conexiones", nombradas, "--json")
        self.assertEqual(json.loads(salida.read_text(encoding="utf-8")),
                         [{"nota": "obra/c/README.md", "tipo": "informa", "porque": "por c", "titulo": "La C"},
                          {"nota": "notas/d.md", "tipo": "confirma", "porque": "por d"}])
        # una nombrada que no está en el repositorio: el texto la nombra, pero no hay qué conectar
        (raiz / "notas/d.md").unlink()
        codigo, _, error = self.correr("tarea", "T1", "--accion", "0", "--conexiones",
                                       json.dumps([{"nota": "notas/d.md", "tipo": "confirma", "porque": "por d"}]))
        self.assertEqual(codigo, 2)
        self.assertIn("no está en el repositorio", error)
        for mal in ([{"nota": "notas/otra.md"}], [{"nota": "notas/a.md", "tipo": "contiene"}], "{no es json",
                    # una nombrada sin tipo, sin porqué, con un tipo de fuera, o la carpeta en vez de su documento
                    [{"nota": "notas/d.md", "porque": "x"}], [{"nota": "notas/d.md", "tipo": "informa", "porque": "  "}],
                    [{"nota": "notas/d.md", "tipo": "contiene", "porque": "x"}], [{"nota": "obra/c/", "tipo": "informa", "porque": "x"}],
                    # una ruta que el texto escribe con espacios, o fuera de un `código`, no es una nota que nombre
                    [{"nota": "notas/sin codigo.md", "tipo": "informa", "porque": "x"}]):
            codigo, _, error = self.correr("tarea", "T1", "--accion", "0", "--conexiones", mal if isinstance(mal, str) else json.dumps(mal))
            self.assertEqual(codigo, 2, error)

    def test_las_notas_que_nombra_una_ficha(self):
        """Las calcula igual que la página (leer.ts): las rutas escritas como código en el texto de los bloques, con al
        menos una barra y sin espacios, en el orden en que aparecen, y la `nota` de los temas."""
        from telar.servicios.tareas import documento_de, notas_nombradas

        pagina = {"bloques": [{"texto": "Es tu tema (`notas/métodos/filtro.md`) y cae en `obra/ia-empleo/`;"
                                        " no `hyp-sin-barra`, ni `dos palabras/x`, ni `https://x.y/z`.\n\n"
                                        "- un ítem que sigue\n  en `notas/d.md`\n\notra vez `obra/ia-empleo/`"},
                              {"titulo": "fuentes", "items": [{"titulo": "`notas/e.md`"}]},
                              {"texto": "`~/abs/x.md` y `/abs/y.md`, `.claude/`"}],
                  "temas": ["suelto", {"nombre": "la frontera", "nota": "notas/frontera.md"}, {"nombre": "repetido", "nota": "notas/d.md"}]}
        # las absolutas no: no son de ningún grafo
        self.assertEqual(notas_nombradas(pagina), ["notas/métodos/filtro.md", "obra/ia-empleo/", "notas/d.md",
                                                   ".claude/", "notas/frontera.md"])
        self.assertEqual(notas_nombradas({"bloques": [{"texto": None}], "temas": None}), [])
        self.assertEqual(documento_de("notas/d.md", Path(self.tmp.name)), "notas/d.md")

    def test_el_documento_de_una_carpeta(self):
        """Una carpeta nombrada se conecta por su documento: su README.md, si no su index.md, y si no el único .md que
        tenga; sin ninguno, o si no está, no tiene. La misma regla que la página (relaciones.ts, `documentoDeCarpeta`)."""
        from telar.servicios.tareas import documento_de

        raiz = Path(self.tmp.name)
        for archivo in ("con-readme/README.md", "con-readme/index.md", "con-index/index.md", "con-index/b.md",
                        "uno/draft.md", "uno/datos.csv", "uno/sub/README.md", "uno/.oculto.md", "dos/a.md", "dos/b.md",
                        "vacia/sub/x.md"):
            (raiz / archivo).parent.mkdir(parents=True, exist_ok=True)
            (raiz / archivo).write_text("# x\n", encoding="utf-8")
        self.assertEqual(documento_de("con-readme/", raiz), "con-readme/README.md")
        self.assertEqual(documento_de("con-index/", raiz), "con-index/index.md")
        self.assertEqual(documento_de("uno/", raiz), "uno/draft.md")
        self.assertIsNone(documento_de("dos/", raiz))
        self.assertIsNone(documento_de("vacia/", raiz))
        self.assertIsNone(documento_de("no-esta/", raiz))

    def test_los_campos_de_la_ficha_se_validan(self):
        from telar.ordenes.seccion import validar

        bien = {"titulo": "x", "bloques": [], "temas": ["uno", {"nombre": "dos", "nota": "notas/dos.md"}],
                "fuente": "Alguien, una revista", "fecha": "2026-11-14", "estado": "me interesa: porque sí"}
        self.assertEqual(validar(bien), "")
        self.assertIn("temas", validar({**bien, "temas": "uno"}))
        self.assertIn("temas", validar({**bien, "temas": [{"nota": "x.md"}]}))
        self.assertIn("estado", validar({**bien, "estado": {"dijo": "sí"}}))
        con = {**bien, "conexiones": [{"nota": "a.md", "tipo": "informa", "porque": "x", "ancla": "", "elegida": None}],
               "tipos": [{"tipo": "informa", "que": "…", "color": "azul"}], "procesando": "21:40"}
        self.assertEqual(validar(con), "")
        self.assertIn("conexiones", validar({**con, "conexiones": [{"nota": "a.md"}]}))
        self.assertIn("conexiones", validar({**con, "conexiones": [{"nota": "a.md", "tipo": "x", "elegida": "sí"}]}))
        self.assertIn("tipos", validar({**con, "tipos": [{"tipo": "x", "color": "fucsia"}]}))
        self.assertIn("procesando", validar({**con, "procesando": 3}))


class AccionConMensaje(Orden):
    def test_el_mensaje_se_valida(self):
        from telar.ordenes.seccion import validar

        a = {"nombre": "hecha y procesar", "comando": ["true"], "mensaje": "/seguir T1", "nombre_hilo": "▶ T1"}
        self.assertEqual(validar({"titulo": "x", "bloques": [], "acciones": [a]}), "")
        self.assertIn("mensaje", validar({"titulo": "x", "bloques": [], "acciones": [{**a, "mensaje": 3}]}))


class AreaDeLasFilas(Orden):
    def test_la_del_proveedor_o_la_primera_carpeta(self):
        from telar.ordenes.pendientes import con_area

        filas = con_area([{"area": "personal", "ruta": "trabajo/x"}, {"ruta": "trabajo/proyectos/faro"}, {"ruta": ""}])
        self.assertEqual([f["area"] for f in filas], ["personal", "trabajo", ""])

    def test_el_proveedor_comando_la_lee(self):
        from telar.proveedores.tareas import _tarea_de_json

        self.assertEqual(_tarea_de_json({"texto": "x", "area": "personal"}, "o", 0).area, "personal")


class ProveedorConClase(Orden):
    def test_como_elige_la_clase_y_el_nombre_queda_libre(self):
        from telar.config import Proveedor
        from telar.proveedores import clase

        self.assertEqual(clase(Proveedor(nombre="lecturas", activo=True, opciones={"como": "tareas"})), "tareas")
        self.assertEqual(clase(Proveedor(nombre="tareas", activo=True, opciones={})), "tareas")


class HilosGemelos(Orden):
    def test_doctor_encuentra_los_nombres_repetidos(self):
        from telar.ordenes.doctor import gemelos

        self.assertEqual(gemelos(["Faro", "T12 algo…", "Faro", "Mar"]), ["Faro"])
        self.assertEqual(gemelos(["Faro", "Mar"]), [])

    def test_llevar_sin_conversacion_sugiere_sesion(self):
        codigo, _, error = self.correr("hilo", "llevar", "--hilo", "faro")
        self.assertNotEqual(codigo, 0)


class ProyectoDeUnaTarea(Prueba):
    def test_solo_una_carpeta_del_repositorio_es_proyecto(self):
        from telar.ordenes.pendientes import _carpeta_de

        self.assertEqual(_carpeta_de("negocio/pipeline/faro/"), "negocio/pipeline/faro")
        self.assertEqual(_carpeta_de("proyectos/faro/README.md#pendientes"), "proyectos/faro/README.md")
        for otra in ("", "gmail:1a2b", "https://x.y/z", "/abs/faro", "~/faro", ".", "dos palabras"):
            self.assertEqual(_carpeta_de(otra), "", otra)


class EstadoCorto(Prueba):
    def test_el_estado_queda_en_lo_de_antes_de_la_explicacion(self):
        from telar.ordenes.proyectos import corto

        self.assertEqual(corto("Activo"), "Activo")
        self.assertEqual(corto("Cerrado (confirmado el 16-sep)"), "Cerrado")
        self.assertEqual(corto("**Prospecto**. Marco presentado"), "Prospecto")
        self.assertEqual(corto("En pausa por el cliente desde el 9-sep. Ver Notas"), "En pausa por el cliente…")
        # la fila que escribe un gestor de proyectos: el estado, y después de qué sale
        self.assertEqual(corto("Por partir · PMO: pista (Preparación)"), "Por partir")
        self.assertEqual(corto("Terminado · a mano desde 2026-10-29: entregado"), "Terminado")
        self.assertEqual(corto(""), "")
        # lo tachado ya no vale, y la fecha de adelante de una nota no es el estado
        self.assertEqual(corto("~~Activo, sin empezar. Kick-off el 1-oct~~ **16-oct: activo, en la semana 2** (la 1 partió el 5-oct)"), "Activo")
        self.assertEqual(corto("~~Prospecto~~ Negociación"), "Negociación")


class AreaDelFrontmatter(Prueba):
    def test_el_area_sale_del_frontmatter_y_no_del_cuerpo(self):
        import tempfile
        from pathlib import Path
        from telar.ordenes.proyectos import area_de

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "README.md"
            f.write_text('---\ntitulo: Faro\narea: "PIA"   # la unidad\n---\n\n# Faro\n')
            self.assertEqual(area_de(f), "PIA")
            f.write_text("---\ntitulo: Faro\n---\n\narea: EIC\n")
            self.assertEqual(area_de(f), "")
            f.write_text("# sin frontmatter\narea: GT\n")
            self.assertEqual(area_de(f), "")
            self.assertEqual(area_de(Path(d) / "no-existe.md"), "")


class UnaMudanzaEntreDosArquetipos(Orden):
    """Un repositorio que muda sus iniciativas de una carpeta a otra: mientras dura, unas siguen en la vieja (con el
    arquetipo de antes) y otras ya están en la nueva (con el suyo), y alguna está en las dos. `telar proyectos` y los
    mundos leen las dos sin romperse."""

    PERFIL = """version: 1
arquetipos:
  proyecto:
    ruta: "operacion/proyectos/*/"
    etiqueta: "{campo:Cliente} · {titulo}"
    secciones:
      titulo: { tipo: linea, encabezado: '^#\\s+(.+)$' }
      campos: { tipo: tabla, encabezado: '^##\\s+Ficha' }
  iniciativa:
    ruta: "operacion/iniciativas/*/"
    secciones:
      titulo: { tipo: linea, encabezado: '^#\\s+(.+)$' }
internos: [Taller]
"""

    def setUp(self):
        super().setUp()
        raiz = Path(self.tmp.name) / "taller"
        (raiz / ".telar").mkdir(parents=True)
        (raiz / ".telar" / "perfil.yaml").write_text(self.PERFIL, encoding="utf-8")

        def unidad(ruta: str, titulo: str, frontmatter: str = "", cliente: str = "") -> None:
            carpeta = raiz / ruta
            carpeta.mkdir(parents=True)
            ficha = f"\n## Ficha\n\n| Campo | Valor |\n|---|---|\n| Cliente | {cliente} |\n" if cliente else ""
            (carpeta / "README.md").write_text(f"---\n{frontmatter}---\n\n# {titulo}\n{ficha}", encoding="utf-8")

        unidad("operacion/proyectos/muelle", "Muelle nuevo", "area: Norte\n", cliente="Puerto Sur")
        # todavía en la carpeta vieja, con el cliente que es la casa misma
        unidad("operacion/proyectos/club-lectura", "Club de lectura", "area: Norte\n", cliente="Taller")
        # ya en la nueva: un programa (el conjunto, sin programa) y dos que dicen ser de él
        unidad("operacion/iniciativas/club-lectura", "Club de lectura", "estado: en curso\npeso: alto\n")
        unidad("operacion/iniciativas/canales", "Canales del club", "programa: club-lectura\ndueno: Ana\npeso: medio\n"
               'proxima_decision: "¿Abrimos el canal de novedades?"\nestado: piloto\n')
        unidad("operacion/iniciativas/boletin", "Boletín", "programa: club-lectura\n")
        # una suelta
        unidad("operacion/iniciativas/inventario", "Inventario anual", "dueno: Bruno\nestado: por partir\n")
        self.raiz = raiz
        configuracion = Path(self.tmp.name) / "config.toml"
        configuracion.write_text('[mundos.trabajo]\nrutas = ["operacion/"]\n', encoding="utf-8")
        os.environ["TELAR_CONFIG"] = str(configuracion)
        os.environ["TELAR_RAIZ"] = str(raiz)

    def test_lee_las_dos_carpetas_cada_una_con_su_arquetipo(self):
        datos = self.json_de("proyectos", "--json")
        por_ruta = {p["ruta"]: p for p in datos["proyectos"]}
        self.assertEqual(sorted(por_ruta), [
            "operacion/iniciativas/boletin", "operacion/iniciativas/canales", "operacion/iniciativas/club-lectura",
            "operacion/iniciativas/inventario", "operacion/proyectos/club-lectura", "operacion/proyectos/muelle"])
        self.assertEqual({r: p["arquetipo"] for r, p in por_ruta.items() if "/iniciativas/" in r},
                         dict.fromkeys([r for r in por_ruta if "/iniciativas/" in r], "iniciativa"))
        self.assertEqual(por_ruta["operacion/proyectos/club-lectura"]["arquetipo"], "proyecto")
        # la misma iniciativa en las dos carpetas: dos unidades, cada una con su dirección
        self.assertNotEqual(por_ruta["operacion/proyectos/club-lectura"]["direccion"],
                            por_ruta["operacion/iniciativas/club-lectura"]["direccion"])
        # y cada una de su mundo, por su carpeta
        self.assertEqual({p["mundo"] for p in datos["proyectos"]}, {"trabajo"})

    def test_cada_unidad_trae_su_frontmatter(self):
        por_ruta = {p["ruta"]: p for p in self.json_de("proyectos", "--json")["proyectos"]}
        canales = por_ruta["operacion/iniciativas/canales"]
        self.assertEqual(canales["frontmatter"], {"programa": "club-lectura", "dueno": "Ana", "peso": "medio",
                                                  "proxima_decision": "¿Abrimos el canal de novedades?", "estado": "piloto"})
        self.assertEqual(por_ruta["operacion/iniciativas/club-lectura"]["frontmatter"].get("programa"), None)
        self.assertEqual(por_ruta["operacion/proyectos/muelle"]["area"], "Norte")

    def test_una_unidad_sin_cliente_se_llama_por_su_titulo_y_es_de_la_casa(self):
        por_ruta = {p["ruta"]: p for p in self.json_de("proyectos", "--json")["proyectos"]}
        nueva = por_ruta["operacion/iniciativas/canales"]
        self.assertEqual((nueva["nombre"], nueva["cliente"], nueva["interno"]), ("Canales del club", "", True))
        # en la carpeta vieja lleva el cliente de la casa: también es interna (el dashboard le quita ese prefijo)
        vieja = por_ruta["operacion/proyectos/club-lectura"]
        self.assertEqual((vieja["nombre"], vieja["cliente"], vieja["interno"]), ("Taller · Club de lectura", "Taller", True))
        afuera = por_ruta["operacion/proyectos/muelle"]
        self.assertEqual((afuera["cliente"], afuera["interno"]), ("Puerto Sur", False))

    def test_un_hilo_vinculado_a_la_carpeta_vieja_sigue_y_la_nueva_se_vincula_aparte(self):
        self.correr("hilo", "vincular", "operacion/proyectos/club-lectura", "--hilo", "club-lectura")
        self.correr("hilo", "vincular", "operacion/iniciativas/club-lectura", "--hilo", "club-lectura-nuevo")
        por_ruta = {p["ruta"]: p for p in self.json_de("proyectos", "--json")["proyectos"]}
        self.assertEqual(por_ruta["operacion/proyectos/club-lectura"]["hilo"], "club-lectura")
        self.assertEqual(por_ruta["operacion/iniciativas/club-lectura"]["hilo"], "club-lectura-nuevo")
        # terminada la mudanza, la carpeta vieja ya no está: la lista sigue, sin ella
        import shutil
        shutil.rmtree(self.raiz / "operacion" / "proyectos" / "club-lectura")
        rutas = [p["ruta"] for p in self.json_de("proyectos", "--json")["proyectos"]]
        self.assertNotIn("operacion/proyectos/club-lectura", rutas)
        self.assertIn("operacion/iniciativas/club-lectura", rutas)
