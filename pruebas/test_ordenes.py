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
            set(datos), {"sesion", "viva", "raiz", "multiplexor", "aviso", "orden", "clientes", "hilos"}
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

    def test_una_tecla_del_dashboard_se_rechaza(self):
        from telar import config as mod_config
        from telar.config import ErrorDeConfig

        for tecla in ("r", "p", "/"):
            with self.assertRaises(ErrorDeConfig):
                mod_config.desde_dict({"atajos": {tecla: {"nombre": "x", "mensaje": "y"}}})

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


class Bloques(Orden):
    def test_se_declaran_con_comando_y_color(self):
        from telar import config as mod_config

        cfg = mod_config.desde_dict({"bloques": {"correo": {"nombre": "correo", "comando": ["x", "--json"], "color": "rojo"}}})
        self.assertEqual([(b.clave, b.nombre, b.comando, b.color) for b in cfg.bloques],
                         [("correo", "correo", ("x", "--json"), "rojo")])
        self.assertEqual(mod_config.desde_dict({"bloques": {"c": {"nombre": "c", "comando": ["x"]}}}).bloques[0].color, "cian")

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
