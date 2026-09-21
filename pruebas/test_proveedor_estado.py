"""El proveedor de estado: el contrato, la cascada y el programa externo.

Casi todo corre contra el taller de `ejemplo/`, que está escrito a propósito con un
proyecto completo (`faro`), uno mínimo (`molino`) y uno al que le falta una sección
que su perfil declaró (`arboleda`). Lo que no cabe ahí —marcas de otro repositorio,
cascadas a medida, un programa que imprime el contrato— se arma en un temporal.

Parsear el markdown es de `telar.lectura` y se prueba allá. Aquí se prueba el paso
siguiente: qué significa cada sección para el estado de un hilo.
"""

from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from comun import EJEMPLO, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import perfil as p
from telar.config import Proveedor as ConfigProveedor
from telar.modelo import Pendiente
from telar.proveedores import ErrorDeProveedor
from telar.proveedores import estado as e


def documento(nombre: str) -> Path:
    return EJEMPLO / "proyectos" / nombre / "README.md"


class Contrato(Prueba):
    """La forma de salida: siete campos, y la vuelta entera por JSON."""

    def setUp(self):
        super().setUp()
        self.proyecto = p.cargar(EJEMPLO).arquetipo("proyecto")

    def test_los_siete_campos_son_el_contrato(self):
        self.assertEqual(
            e.CONTRATO,
            ("titulo", "resumen", "campos", "pendientes", "esperando", "hitos", "enlaces"),
        )

    def test_un_estado_sin_contenido_se_sabe_vacio(self):
        self.assertTrue(e.Estado().vacio)
        self.assertTrue(e.Estado(nota="no existe el documento").vacio)  # la nota no es contenido
        self.assertFalse(e.Estado(resumen="parado desde la tormenta").vacio)

    def test_el_dict_lleva_el_contrato_y_la_procedencia(self):
        crudo = e.leer(documento("faro"), self.proyecto).a_dict()
        for clave in (*e.CONTRATO, "documento", "leido", "nota", "faltan"):
            self.assertIn(clave, crudo)
        json.dumps(crudo)  # tiene que ser serializable tal cual

    def test_ida_y_vuelta_por_json(self):
        antes = e.leer(documento("faro"), self.proyecto)
        despues = e.Estado.desde_dict(json.loads(json.dumps(antes.a_dict())))
        self.assertEqual(antes, despues)

    def test_lo_que_no_es_del_contrato_se_ignora(self):
        self.assertEqual(e.Estado.desde_dict({"titulo": "Faro", "invento": {"a": 1}}).titulo, "Faro")

    def test_una_forma_mala_se_queja_en_vez_de_adivinar(self):
        for datos in (
            [],
            {"campos": ["Encargo"]},
            {"pendientes": {"texto": "x"}},
            {"titulo": 3},
            {"hitos": [{"que": "Entrega", "cuando": "el martes"}]},
        ):
            with self.assertRaises(ErrorDeProveedor):
                e.Estado.desde_dict(datos)

    def test_la_ficha_habla_el_vocabulario_del_modelo(self):
        ficha = e.leer(documento("faro"), self.proyecto).a_ficha()
        self.assertEqual(ficha.titulo, "Faro")
        self.assertTrue(ficha.estado.startswith("La lámpara nueva"))
        self.assertEqual(ficha.pendientes[0].texto, "Desmontar la lámpara vieja")
        self.assertIn("campos", ficha.secciones)
        self.assertIn("esperando", ficha.secciones)
        self.assertFalse(ficha.vacia)
        json.dumps(ficha.secciones)  # `secciones` viaja en JSON, no en estas clases


class Taller(Prueba):
    """Los tres proyectos del ejemplo, leídos con el perfil del ejemplo."""

    def setUp(self):
        super().setUp()
        self.perfil = p.cargar(EJEMPLO)
        self.proyecto = self.perfil.arquetipo("proyecto")

    def test_el_titulo_sale_del_encabezado(self):
        self.assertEqual(e.leer(documento("faro"), self.proyecto).titulo, "Faro")

    def test_el_resumen_es_el_primer_parrafo_y_para(self):
        resumen = e.leer(documento("faro"), self.proyecto).resumen
        self.assertTrue(resumen.startswith("La lámpara nueva llegó"))
        self.assertTrue(resumen.endswith("El resto del encargo está cerrado."))
        self.assertNotIn("Segundo párrafo", resumen)

    def test_los_campos_salen_de_la_tabla_declarada_sin_su_encabezado(self):
        campos = e.leer(documento("faro"), self.proyecto).campos
        self.assertEqual(campos["Encargo"], "Municipalidad de la costa")
        self.assertEqual(campos["Entrega"], "2026-06-30")
        self.assertNotIn("Campo", campos)  # la fila de encabezado no es un campo
        self.assertEqual(len(campos), 3)

    def test_las_casillas_traen_su_marca(self):
        pendientes = e.leer(documento("faro"), self.proyecto).pendientes
        self.assertEqual(
            [(x.texto[:9], x.hecho, x.en_curso) for x in pendientes],
            [
                ("Desmontar", True, False),
                ("Ajustar l", False, True),
                ("Medir el ", False, False),
                ("Entregar ", False, False),
            ],
        )
        self.assertEqual(pendientes[0].origen, "pendientes")

    def test_esperando_es_su_propia_seccion_y_no_pendientes(self):
        estado = e.leer(documento("faro"), self.proyecto)
        self.assertEqual(len(estado.esperando), 2)
        self.assertTrue(estado.esperando[0].texto.startswith("El electricista"))
        self.assertNotIn(estado.esperando[0].texto, [x.texto for x in estado.pendientes])

    def test_los_hitos_salen_de_los_campos_con_fecha_y_van_en_orden(self):
        hitos = e.leer(documento("faro"), self.proyecto).hitos
        self.assertEqual(
            [(h.que, h.cuando) for h in hitos],
            [("Empezó", date(2026, 3, 2)), ("Entrega", date(2026, 6, 30))],
        )
        self.assertTrue(all(h.origen == "campos" for h in hitos))

    def test_un_proyecto_con_lo_justo_no_inventa_nada(self):
        estado = e.leer(documento("molino"), self.proyecto)
        self.assertEqual(estado.titulo, "Molino")
        self.assertTrue(estado.resumen.startswith("Parado desde la tormenta"))
        self.assertEqual(estado.campos, {})
        self.assertEqual(estado.esperando, ())
        self.assertEqual(estado.hitos, ())
        self.assertEqual(len(estado.pendientes), 2)
        self.assertEqual(estado.nota, "")

    def test_una_seccion_requerida_que_falta_se_dice(self):
        estado = e.leer(documento("arboleda"), self.proyecto)
        self.assertEqual(estado.faltan, ("estado",))
        self.assertIn("estado", estado.nota)
        self.assertEqual(estado.resumen, "")
        self.assertEqual(len(estado.pendientes), 2)  # lo demás se lee igual

    def test_el_arquetipo_por_archivo_tambien_se_lee(self):
        estado = e.leer(EJEMPLO / "notas" / "madera.md", self.perfil.arquetipo("nota"))
        self.assertEqual(estado.titulo, "De dónde sale la madera seca")
        self.assertTrue(estado.resumen.startswith("El aserradero del río"))

    def test_sin_arquetipo_rige_la_convencion_minima(self):
        estado = e.leer(EJEMPLO / "README.md")
        self.assertEqual(estado.titulo, "El taller")
        self.assertTrue(estado.resumen.startswith("Un repositorio de trabajo inventado"))

    def test_un_documento_que_no_esta_no_es_una_falla(self):
        estado = e.leer(EJEMPLO / "proyectos" / "no-existe" / "README.md", self.proyecto)
        self.assertTrue(estado.vacio)
        self.assertIn("no se pudo leer", estado.nota)
        self.assertEqual(estado.documento, EJEMPLO / "proyectos" / "no-existe" / "README.md")


class Cascada(Prueba):
    """De dónde sale cada campo, y cómo el repositorio lo cambia sin tocar código."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def escribir(self, texto: str, nombre: str = "README.md") -> Path:
        ruta = self.raiz / nombre
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def arquetipo(self, *secciones: p.Seccion, ruta: str = "*/") -> p.Arquetipo:
        return p.Arquetipo(nombre="proyecto", ruta=ruta, secciones=secciones)

    def test_la_cascada_por_defecto_sale_de_lo_que_el_perfil_declaro(self):
        cascada = e.cascada_por_defecto(p.cargar(EJEMPLO).arquetipo("proyecto"))
        self.assertEqual(cascada["resumen"], ("estado",))
        self.assertEqual(cascada["campos"], ("ficha",))
        self.assertEqual(cascada["esperando"], ("esperando",))
        # `esperando` ya tiene dueño: no vuelve a entrar como respaldo de pendientes.
        self.assertEqual(cascada["pendientes"], ("pendientes",))

    def test_una_lista_sin_dueno_sirve_de_respaldo_de_pendientes(self):
        arquetipo = self.arquetipo(
            p.Seccion(nombre="pendientes", tipo="casillas", encabezado=r"^##\s+Pendientes"),
            p.Seccion(nombre="proximos", tipo="lista", encabezado=r"^##\s+Próximos"),
        )
        self.assertEqual(e.cascada_por_defecto(arquetipo)["pendientes"], ("pendientes", "proximos"))
        estado = e.leer(self.escribir("# X\n\n## Próximos\n\n- Cambiar la correa\n"), arquetipo)
        self.assertEqual([x.texto for x in estado.pendientes], ["Cambiar la correa"])
        self.assertEqual(estado.pendientes[0].origen, "proximos")

    def test_el_resumen_cae_a_una_fila_de_la_tabla_cuando_no_hay_seccion(self):
        arquetipo = self.arquetipo(
            p.Seccion(nombre="estado", tipo="parrafo", encabezado=r"^##\s+Estado"),
            p.Seccion(nombre="ficha", tipo="tabla", encabezado=r"^##\s+Ficha"),
        )
        ruta = self.escribir("# X\n\n## Ficha\n\n| Campo | Valor |\n|---|---|\n| Etapa | Montaje |\n")
        self.assertEqual(e.leer(ruta, arquetipo).resumen, "")
        guiado = e.leer(ruta, arquetipo, cascada={"resumen": ["estado", "campo:Etapa"]})
        self.assertEqual(guiado.resumen, "Etapa: Montaje")

    def test_el_resumen_cae_a_la_siguiente_seccion_de_prosa(self):
        """Sin `## Estado`, sirve cualquier otra sección de prosa que el perfil declare."""
        arquetipo = self.arquetipo(
            p.Seccion(nombre="estado", tipo="parrafo", encabezado=r"^##\s+Estado"),
            p.Seccion(nombre="situacion", tipo="parrafo", encabezado=r"^##\s+Situación"),
        )
        self.assertEqual(e.cascada_por_defecto(arquetipo)["resumen"], ("estado", "situacion"))
        ruta = self.escribir("# X\n\n## Situación\n\nMontada la lámpara, falta el giro.\n")
        self.assertEqual(e.leer(ruta, arquetipo).resumen, "Montada la lámpara, falta el giro.")

    def test_el_encabezado_de_una_seccion_manda_sobre_el_orden(self):
        """Declarada `## Estado`, gana aunque otra sección de prosa venga antes."""
        arquetipo = self.arquetipo(
            p.Seccion(nombre="estado", tipo="parrafo", encabezado=r"^##\s+Estado"),
            p.Seccion(nombre="situacion", tipo="parrafo", encabezado=r"^##\s+Situación"),
        )
        ruta = self.escribir(
            "# X\n\n## Situación\n\nLo de siempre.\n\n## Estado\n\nMontada la lámpara.\n"
        )
        self.assertEqual(e.leer(ruta, arquetipo).resumen, "Montada la lámpara.")

    def test_las_marcas_del_repositorio_se_suman_a_la_casilla(self):
        arquetipo = self.arquetipo(p.Seccion(nombre="pendientes", tipo="casillas"))
        ruta = self.escribir("# X\n\n- [ ] ⏳ Ajustar el giro\n- [ ] ✅ Firmar\n- [x] Medir\n")
        estado = e.leer(ruta, arquetipo, marcas={"hecho": ["✅"], "en_curso": ["⏳"]})
        self.assertEqual(
            [(x.texto, x.hecho, x.en_curso) for x in estado.pendientes],
            [("Ajustar el giro", False, True), ("Firmar", True, False), ("Medir", True, False)],
        )

    def test_sin_declararlas_el_emoji_es_texto_y_nada_mas(self):
        arquetipo = self.arquetipo(p.Seccion(nombre="pendientes", tipo="casillas"))
        pendiente = e.leer(self.escribir("# X\n\n- [ ] ✅ Firmar\n"), arquetipo).pendientes[0]
        self.assertEqual(pendiente.texto, "✅ Firmar")
        self.assertFalse(pendiente.hecho)

    def test_una_marca_ascii_no_se_come_el_principio_de_una_palabra(self):
        arquetipo = self.arquetipo(p.Seccion(nombre="pendientes", tipo="casillas"))
        ruta = self.escribir("# X\n\n- [ ] xilófonos para la fiesta\n")
        pendiente = e.leer(ruta, arquetipo, marcas={"hecho": ["x", "✅"]}).pendientes[0]
        self.assertEqual(pendiente.texto, "xilófonos para la fiesta")
        self.assertFalse(pendiente.hecho)

    def test_una_espera_cumplida_ya_no_es_una_espera(self):
        arquetipo = self.arquetipo(
            p.Seccion(nombre="esperando", tipo="lista", encabezado=r"^##\s+Esperando")
        )
        ruta = self.escribir("# X\n\n## Esperando\n\n- ✅ Llegó la madera\n- El permiso municipal\n")
        estado = e.leer(ruta, arquetipo, marcas={"hecho": ["✅"]})
        self.assertEqual([x.texto for x in estado.esperando], ["El permiso municipal"])

    def test_la_fecha_de_una_espera_se_lee_del_texto(self):
        arquetipo = self.arquetipo(
            p.Seccion(nombre="esperando", tipo="lista", encabezado=r"^##\s+Esperando")
        )
        ruta = self.escribir("# X\n\n## Esperando\n\n- El informe, prometido para el 2026-06-30\n")
        self.assertEqual(e.leer(ruta, arquetipo).esperando[0].cuando, date(2026, 6, 30))

    def test_el_maximo_recorta_cada_campo(self):
        arquetipo = self.arquetipo(p.Seccion(nombre="pendientes", tipo="casillas", maximo=3))
        ruta = self.escribir("# X\n\n- [ ] a\n- [ ] b\n- [ ] c\n- [ ] d\n")
        self.assertEqual(len(e.leer(ruta, arquetipo).pendientes), 3)  # el de la sección
        self.assertEqual(len(e.leer(ruta, arquetipo, maximo=1).pendientes), 1)  # el del proveedor

    def test_los_enlaces_salen_del_documento_y_no_se_repiten(self):
        ruta = self.escribir(
            "# X\n\nVer [el informe](informes/2026-06.pdf), otra vez "
            "[el informe](informes/2026-06.pdf) y [la norma](https://ejemplo.invalid/norma).\n"
        )
        enlaces = e.leer(ruta).enlaces
        self.assertEqual(
            [x.destino for x in enlaces],
            ["informes/2026-06.pdf", "https://ejemplo.invalid/norma"],
        )
        self.assertEqual(enlaces[0].texto, "el informe")

    def test_el_front_matter_llena_los_campos_que_la_tabla_no_trae(self):
        ruta = self.escribir("---\nactualizado: 2026-06-01\ncliente: La costa\n---\n\nUn párrafo.\n")
        estado = e.leer(ruta)
        self.assertEqual(estado.campos, {"actualizado": "2026-06-01", "cliente": "La costa"})
        self.assertEqual(estado.resumen, "Un párrafo.")  # el front matter no es el primer párrafo
        self.assertEqual(estado.hitos[0].que, "actualizado")

    def test_sin_titulo_en_el_documento_sirve_el_nombre_del_archivo(self):
        arquetipo = self.arquetipo(
            p.Seccion(nombre="titulo", tipo="linea", encabezado=r"^#\s+(.+)$"), ruta="*.md"
        )
        ruta = self.escribir("Solo un párrafo, sin encabezado.\n", nombre="molino.md")
        self.assertEqual(e.leer(ruta, arquetipo).titulo, "molino")

    def test_un_texto_se_puede_leer_sin_pasar_por_el_disco(self):
        estado = e.Documento().desde_texto("# Faro\n\nMontada la lámpara.\n")
        self.assertEqual(estado.titulo, "Faro")
        self.assertEqual(estado.resumen, "Montada la lámpara.")
        self.assertIsNone(estado.documento)

    def test_una_cascada_que_no_cuadra_se_rechaza(self):
        for mala in ({"inventado": ["estado"]}, {"resumen": "estado"}, {"resumen": [3]}, "estado"):
            with self.assertRaises(ErrorDeProveedor):
                e.Documento(cascada=mala)

    def test_los_enlaces_no_se_gobiernan_por_cascada(self):
        with self.assertRaises(ErrorDeProveedor) as caja:
            e.Documento(cascada={"enlaces": ["esperando"]})
        self.assertIn("documento entero", str(caja.exception))

    def test_las_otras_opciones_tambien_se_validan(self):
        for malas in ({"hecho": "x"}, {"inventada": ["x"]}, "✅"):
            with self.assertRaises(ErrorDeProveedor):
                e.Documento(marcas=malas)
        for tope in (-1, "tres", True):
            with self.assertRaises(ErrorDeProveedor):
                e.Documento(maximo=tope)


class Fechas(Prueba):
    def test_las_formas_que_entiende(self):
        self.assertEqual(e.fecha_en("entrega el 2026-06-30, sin falta"), date(2026, 6, 30))
        self.assertEqual(e.fecha_en("vence 30-06-2026"), date(2026, 6, 30))
        self.assertEqual(e.fecha_en("para el 5-ene-2027"), date(2027, 1, 5))

    def test_sin_ano_se_supone_el_en_curso(self):
        self.assertEqual(e.fecha_en("para el 5-ene", hoy=date(2026, 12, 1)), date(2026, 1, 5))

    def test_una_fecha_despues_de_un_numero_suelto_se_encuentra_igual(self):
        self.assertEqual(e.fecha_en("30 álamos antes del 5-ene-2027"), date(2027, 1, 5))

    def test_lo_que_no_es_una_fecha_no_lo_es(self):
        for texto in ("Encargar treinta álamos", "sin fecha todavía", "2026-13-40", ""):
            self.assertIsNone(e.fecha_en(texto), texto)

    def test_el_idioma_de_los_meses_se_puede_cambiar(self):
        self.assertIsNone(e.fecha_en("5-sty-2027"))
        self.assertEqual(e.fecha_en("5-sty-2027", meses={"sty": 1}), date(2027, 1, 5))


class ProveedorComando(Prueba):
    """El programa externo que imprime el contrato."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.documento = self.raiz / "README.md"
        self.documento.write_text("# Faro\n", encoding="utf-8")

    def programa(self, cuerpo: str) -> Path:
        ruta = self.raiz / "estado.py"
        ruta.write_text("#!/usr/bin/env python3\n" + cuerpo, encoding="utf-8")
        ruta.chmod(ruta.stat().st_mode | stat.S_IXUSR)
        return ruta

    def correr(self, cuerpo: str, *argumentos: str) -> e.Estado:
        fuente = e.Comando([sys.executable, str(self.programa(cuerpo)), *argumentos])
        return fuente.leer(self.documento)

    def test_lo_que_imprime_el_programa_es_el_estado(self):
        estado = self.correr(
            "import json\n"
            "print(json.dumps({'titulo': 'Faro', 'resumen': 'falta el giro',\n"
            "  'pendientes': [{'texto': 'Ajustar', 'en_curso': True}],\n"
            "  'hitos': [{'que': 'Entrega', 'cuando': '2026-06-30'}]}))\n"
        )
        self.assertEqual(estado.titulo, "Faro")
        self.assertEqual(estado.pendientes, (Pendiente(texto="Ajustar", en_curso=True),))
        self.assertEqual(estado.hitos[0].cuando, date(2026, 6, 30))
        self.assertEqual(estado.documento, self.documento)

    def test_los_marcadores_llegan_al_programa(self):
        estado = self.correr(
            "import json, sys\nprint(json.dumps({'titulo': sys.argv[1], 'resumen': sys.argv[2]}))\n",
            "{hilo}",
            "{documento}",
        )
        self.assertEqual(estado.titulo, self.raiz.name)
        self.assertEqual(estado.resumen, str(self.documento))

    def test_un_programa_que_falla_es_un_error_con_su_queja(self):
        with self.assertRaises(ErrorDeProveedor) as caja:
            self.correr("import sys\nprint('no pude leer la base', file=sys.stderr)\nsys.exit(3)\n")
        self.assertIn("no pude leer la base", str(caja.exception))

    def test_un_programa_que_no_imprime_el_contrato_es_un_error(self):
        with self.assertRaises(ErrorDeProveedor):
            self.correr("print('todo bien por acá')\n")

    def test_un_programa_que_no_existe_es_un_error(self):
        with self.assertRaises(ErrorDeProveedor):
            e.Comando([str(self.raiz / "no-existe")]).leer(self.documento)

    def test_un_programa_colgado_no_cuelga_el_telar(self):
        prog = self.programa("import time\ntime.sleep(5)\n")
        with self.assertRaises(ErrorDeProveedor):
            e.Comando([sys.executable, str(prog)], tiempo=0.5).leer(self.documento)

    def test_una_linea_de_shell_se_rechaza(self):
        with self.assertRaises(ErrorDeProveedor) as caja:
            e.Comando("rm -rf /")
        self.assertIn("lista de palabras", str(caja.exception))
        for malo in ([], [1, 2], None, {"programa": "ls"}):
            with self.assertRaises(ErrorDeProveedor):
                e.Comando(malo)
        for tiempo in (0, -1, "diez", True):
            with self.assertRaises(ErrorDeProveedor):
                e.Comando(["ls"], tiempo=tiempo)

    def test_se_construye_desde_la_configuracion(self):
        fuente = e.Comando.desde_config(
            ConfigProveedor(nombre="externo", opciones={"comando": ["echo", "{}"], "tiempo": 2})
        )
        self.assertEqual(fuente.comando, ("echo", "{}"))
        self.assertEqual(fuente.tiempo, 2.0)

    def test_sin_comando_declarado_no_hay_proveedor(self):
        with self.assertRaises(ErrorDeProveedor):
            e.Comando.desde_config(ConfigProveedor(nombre="externo", opciones={}))
        with self.assertRaises(ErrorDeProveedor):
            e.Comando.desde_config(
                ConfigProveedor(nombre="externo", opciones={"comando": ["ls"], "inventada": 1})
            )


class Registro(Prueba):
    def test_vienen_los_dos_de_fabrica(self):
        self.assertEqual(sorted(e.REGISTRO), ["comando", "documento"])

    def test_se_construyen_desde_la_configuracion(self):
        fuente = e.obtener(ConfigProveedor(nombre="documento", opciones={"maximo": 3}))
        self.assertIsInstance(fuente, e.Documento)
        self.assertEqual(fuente.maximo, 3)

    def test_una_opcion_que_no_existe_se_rechaza(self):
        with self.assertRaises(ErrorDeProveedor):
            e.obtener(ConfigProveedor(nombre="documento", opciones={"inventada": 1}))

    def test_un_proveedor_que_no_existe_lo_dice_con_los_que_si(self):
        with self.assertRaises(ErrorDeProveedor) as caja:
            e.obtener(ConfigProveedor(nombre="adivino"))
        self.assertIn("documento", str(caja.exception))

    def test_no_se_registra_dos_veces_el_mismo_nombre(self):
        with self.assertRaises(ValueError):
            e.registrar("documento", lambda cfg: None)

    def test_los_dos_cumplen_el_protocolo_y_declaran_su_alcance(self):
        for fuente in (e.Documento(), e.Comando(["true"])):
            self.assertIsInstance(fuente, e.FuenteDeEstado)
            self.assertTrue(fuente.nombre)
            self.assertTrue(fuente.alcance)
        self.assertNotIsInstance(object(), e.FuenteDeEstado)


if __name__ == "__main__":
    unittest.main()
