"""El estado: que sobreviva, que no mienta y que dos escritores no se pisen.

Lo que de verdad importa aquí no es que un JSON se lea. Es el recorte del intervalo
sin cambio de foco, que una conversación no quede en dos hilos, que renombrar no
deje la mitad de las llaves atrás, y que borrar la carpeta no rompa nada.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config, estado as e
from telar.modelo import Atencion, Hilo, Marca, Prioridad

HORA = 3600.0


class ConCarpeta(Prueba):
    """Cada prueba, su carpeta de estado. Nada queda en el disco de nadie."""

    def setUp(self) -> None:
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.est = e.Estado(Path(self.tmp.name) / "estado")


class SinCarpeta(ConCarpeta):
    def test_leer_sin_carpeta_no_es_un_error(self):
        self.assertFalse(self.est.existe)
        self.assertEqual(self.est.vinculos(), {})
        self.assertEqual(self.est.archivados(), set())
        self.assertEqual(self.est.marcas(), [])
        self.assertIs(self.est.orden(), e.Orden.MUX)

    def test_la_carpeta_se_crea_al_escribir_y_no_antes(self):
        self.assertFalse(self.est.existe)
        self.est.vincular("faro", "proyectos/faro")
        self.assertTrue(self.est.existe)

    def test_un_json_roto_se_dice_con_su_nombre(self):
        self.est.preparar()
        self.est.ruta("vinculos").write_text("{ esto no es json")
        with self.assertRaises(e.ErrorDeEstado) as caso:
            self.est.vinculos()
        self.assertIn("vinculos.json", str(caso.exception))

    def test_el_estado_sale_de_la_configuracion(self):
        cfg = config.Config(estado=Path(self.tmp.name) / "otro")
        self.assertEqual(e.abrir(cfg).carpeta, Path(self.tmp.name) / "otro")


class Vinculos(ConCarpeta):
    def test_vincular_y_desvincular(self):
        self.est.vincular("faro", "proyectos/faro/")
        self.assertEqual(self.est.vinculo("faro"), "proyectos/faro")
        self.est.desvincular("faro")
        self.assertEqual(self.est.vinculo("faro"), "")

    def test_las_llaves_con_guion_bajo_son_notas_al_pie(self):
        self.est.preparar()
        self.est.ruta("vinculos").write_text(
            json.dumps({"_": "esto lo escribió una persona", "faro": "proyectos/faro"})
        )
        self.assertEqual(self.est.vinculos(), {"faro": "proyectos/faro"})


class Prioridades(ConCarpeta):
    def test_poner_y_quitar(self):
        self.est.prioridad("faro", Prioridad.ALTA)
        self.assertEqual(self.est.prioridades(), {"faro": Prioridad.ALTA})
        self.est.prioridad("faro", None)
        self.assertEqual(self.est.prioridades(), {})

    def test_una_prioridad_que_no_existe_se_ignora_al_leer(self):
        self.est.preparar()
        self.est.ruta("prioridades").write_text(json.dumps({"faro": 9, "molino": 2}))
        self.assertEqual(self.est.prioridades(), {"molino": Prioridad.MEDIA})


class Archivados(ConCarpeta):
    def test_archivar_es_idempotente(self):
        self.est.archivar("faro")
        self.est.archivar("faro")
        self.assertEqual(self.est.archivados(), {"faro"})
        self.est.desarchivar("faro")
        self.assertEqual(self.est.archivados(), set())


class Atenciones(ConCarpeta):
    def test_anotar_y_borrar_el_semaforo(self):
        self.est.anotar_atencion("faro", Atencion.ESPERA)
        self.assertIs(self.est.atencion("faro"), Atencion.ESPERA)
        self.est.anotar_atencion("faro", Atencion.NINGUNA)
        self.assertIs(self.est.atencion("faro"), Atencion.NINGUNA)
        self.assertEqual(self.est.atenciones(), {})

    def test_se_guarda_cuando_fue(self):
        self.est.anotar_atencion("faro", Atencion.TRABAJANDO, datetime(2026, 9, 18, 10, 0))
        _, cuando = self.est.atenciones()["faro"]
        self.assertEqual(cuando, datetime(2026, 9, 18, 10, 0))


class Sesiones(ConCarpeta):
    def test_una_conversacion_vive_en_un_solo_hilo(self):
        self.est.anotar_sesion("faro", "aaa")
        self.est.anotar_sesion("molino", "aaa")
        self.assertEqual(self.est.sesiones(), {"molino": ("aaa",)})
        self.assertEqual(self.est.hilo_de("aaa"), "molino")

    def test_varias_conversaciones_en_un_hilo_la_principal_primero(self):
        self.est.anotar_sesion("faro", "vieja")
        self.est.anotar_sesion("faro", "nueva")
        self.assertEqual(self.est.sesiones()["faro"], ("nueva", "vieja"))

    def test_un_panel_corre_una_conversacion_la_anterior_sale_del_hilo(self):
        # /clear en el mismo panel: la de antes ya no está abierta en ninguna parte
        self.est.anotar_sesion("faro", "aaa", panel="7")
        self.est.anotar_sesion("faro", "bbb", panel="7")
        self.assertEqual(self.est.sesiones()["faro"], ("bbb",))
        self.assertEqual(self.est.paneles(), {"7": "bbb"})

    def test_la_anterior_se_queda_si_sigue_viva_en_otro_panel(self):
        # el mapa de paneles puede traer la misma conversación dos veces (se retomó
        # al lado sin que nadie lo anotara). Si sigue abierta en otro, no se la saca.
        self.est.anotar_sesion("faro", "aaa", panel="7")
        self.est.ruta("paneles").write_text(json.dumps({"7": "aaa", "9": "aaa"}))
        self.est.anotar_sesion("faro", "bbb", panel="7")
        self.assertIn("aaa", self.est.sesiones()["faro"])
        self.assertEqual(self.est.paneles(), {"9": "aaa", "7": "bbb"})

    def test_revivir_el_agente_desarchiva_el_hilo(self):
        self.est.archivar("faro")
        self.est.anotar_sesion("faro", "aaa")
        self.assertEqual(self.est.archivados(), set())

    def test_sin_revivir_el_hilo_sigue_archivado(self):
        self.est.archivar("faro")
        self.est.anotar_sesion("faro", "aaa", revivir=False)
        self.assertEqual(self.est.archivados(), {"faro"})

    def test_olvidar_una_sesion_la_saca_de_todos_lados(self):
        self.est.anotar_sesion("faro", "aaa", panel="7")
        self.est.olvidar_sesion("aaa")
        self.assertEqual(self.est.sesiones(), {})
        self.assertEqual(self.est.paneles(), {})

    def test_se_lee_el_formato_viejo_de_una_sola_cadena(self):
        self.est.preparar()
        self.est.ruta("sesiones").write_text(json.dumps({"faro": "aaa"}))
        self.assertEqual(self.est.sesiones()["faro"], ("aaa",))


class Foco(ConCarpeta):
    def test_marcar_el_mismo_hilo_dos_veces_no_escribe(self):
        self.assertTrue(self.est.marcar("faro"))
        self.assertFalse(self.est.marcar("faro"))
        self.assertEqual(len(self.est.marcas()), 1)

    def test_el_registro_salta_las_lineas_rotas(self):
        self.est.preparar()
        self.est.ruta(e.FOCO).write_text(
            "2026-09-18T10:00:00\tfaro\nbasura sin tabulador\nno-es-fecha\tmolino\n"
        )
        self.assertEqual([m.hilo for m in self.est.marcas()], ["faro"])

    def test_un_intervalo_sin_cambio_de_foco_se_recorta(self):
        # tres horas en el mismo hilo sin tocar nada cuentan una, no tres
        marcas = [Marca(cuando=datetime(2026, 9, 18, 9, 0), hilo="faro")]
        ahora = datetime(2026, 9, 18, 12, 0)
        tiempos = e.tiempo_por_hilo(marcas, HORA, ahora=ahora)
        self.assertEqual(tiempos["faro"], HORA)

    def test_el_tiempo_se_reparte_entre_marcas(self):
        marcas = [
            Marca(cuando=datetime(2026, 9, 18, 9, 0), hilo="faro"),
            Marca(cuando=datetime(2026, 9, 18, 9, 30), hilo="molino"),
        ]
        ahora = datetime(2026, 9, 18, 10, 0)
        tiempos = e.tiempo_por_hilo(marcas, HORA, ahora=ahora)
        self.assertEqual(tiempos, {"faro": 1800.0, "molino": 1800.0})

    def test_un_tope_que_no_es_positivo_se_queja(self):
        with self.assertRaises(ValueError):
            list(e.intervalos_de([], 0))

    def test_el_intervalo_cuenta_en_el_dia_en_que_empezo(self):
        marcas = [
            Marca(cuando=datetime(2026, 9, 17, 23, 50), hilo="faro"),
            Marca(cuando=datetime(2026, 9, 18, 9, 0), hilo="molino"),
        ]
        ahora = datetime(2026, 9, 18, 9, 30)
        por_dia = e.tiempo_por_dia(marcas, HORA, ahora=ahora)
        self.assertEqual(sorted(por_dia), [date(2026, 9, 17), date(2026, 9, 18)])
        self.assertEqual(list(por_dia[date(2026, 9, 17)]), ["faro"])

    def test_se_puede_pedir_solo_un_dia(self):
        self.est.marcar("faro", datetime(2026, 9, 17, 10, 0))
        self.est.marcar("molino", datetime(2026, 9, 18, 10, 0))
        ayer = self.est.tiempos(date(2026, 9, 17), date(2026, 9, 17), HORA)[0]
        self.assertEqual(list(ayer), ["faro"])

    def test_el_ultimo_foco_por_hilo(self):
        marcas = [
            Marca(cuando=datetime(2026, 9, 18, 9, 0), hilo="faro"),
            Marca(cuando=datetime(2026, 9, 18, 11, 0), hilo="faro"),
        ]
        self.assertEqual(e.ultimo_foco(marcas)["faro"], datetime(2026, 9, 18, 11, 0))

    def test_dos_hilos_del_mismo_proyecto_suman_uno(self):
        tiempos = {"faro": 600.0, "faro informe": 300.0, "suelto": 60.0}
        vinculos = {"faro": "proyectos/faro", "faro informe": "proyectos/faro"}
        self.assertEqual(
            e.agrupar(tiempos, vinculos), {"proyectos/faro": 900.0, "suelto": 60.0}
        )


class ElOrden(ConCarpeta):
    def test_por_defecto_manda_el_multiplexor(self):
        self.assertIs(self.est.orden(), e.Orden.MUX)

    def test_se_guarda_y_se_relee(self):
        self.est.ordenar_por("alfa")
        self.assertIs(self.est.orden(), e.Orden.ALFA)
        self.assertEqual((self.est.carpeta / e.ORDEN).read_text().strip(), "alfa")

    def test_una_palabra_que_no_se_entiende_no_rompe_la_lista(self):
        self.est.preparar()
        (self.est.carpeta / e.ORDEN).write_text("por-color\n")
        self.assertIs(self.est.orden(), e.Orden.MUX)

    def test_un_criterio_inventado_se_rechaza_al_escribir(self):
        with self.assertRaises(ValueError):
            self.est.ordenar_por("por-color")


class Ordenar(Prueba):
    def hilos(self):
        return [
            Hilo(id="1", nombre="molino", prioridad=Prioridad.BAJA),
            Hilo(id="2", nombre="Faro", prioridad=Prioridad.ALTA,
                 visto=datetime(2026, 9, 18, 9, 0)),
            Hilo(id="3", nombre="arboleda", visto=datetime(2026, 9, 18, 12, 0)),
        ]

    def test_el_orden_del_multiplexor_no_toca_nada(self):
        self.assertEqual(
            [h.nombre for h in e.ordenar(self.hilos(), e.Orden.MUX)],
            ["molino", "Faro", "arboleda"],
        )

    def test_alfabetico_no_distingue_mayusculas(self):
        self.assertEqual(
            [h.nombre for h in e.ordenar(self.hilos(), "alfa")],
            ["arboleda", "Faro", "molino"],
        )

    def test_por_prioridad_lo_que_no_tiene_va_al_final(self):
        self.assertEqual(
            [h.nombre for h in e.ordenar(self.hilos(), "prioridad")],
            ["Faro", "molino", "arboleda"],
        )

    def test_por_reciente_lo_que_nunca_tuvo_foco_va_al_final(self):
        self.assertEqual(
            [h.nombre for h in e.ordenar(self.hilos(), "reciente")],
            ["arboleda", "Faro", "molino"],
        )

    def test_los_archivados_se_separan_sin_reordenar(self):
        hilos = [Hilo(id="1", nombre="a"), Hilo(id="2", nombre="b", archivado=True)]
        vivos, guardados = e.partir(hilos)
        self.assertEqual([h.nombre for h in vivos], ["a"])
        self.assertEqual([h.nombre for h in guardados], ["b"])


class Repartir(Prueba):
    """Lo que el multiplexor muestra, lo que telar solo recuerda, y el cajón."""

    def hilos(self):
        return [
            Hilo(id="@1", nombre="faro"),
            Hilo(id="arboleda", nombre="arboleda"),
            Hilo(id="@2", nombre="molino", archivado=True),
        ]

    def test_lo_que_el_multiplexor_no_muestra_no_cuenta_como_abierto(self):
        # «arboleda» es lo que queda cuando el tab se renombra desde el multiplexor:
        # telar lo recuerda, pero ya no hay ninguna ventana detrás
        abiertos, sin_ventana, archivados = e.repartir(self.hilos(), {"faro", "molino"})
        self.assertEqual([h.nombre for h in abiertos], ["faro"])
        self.assertEqual([h.nombre for h in sin_ventana], ["arboleda"])
        self.assertEqual([h.nombre for h in archivados], ["molino"])

    def test_sin_multiplexor_ninguno_esta_abierto(self):
        abiertos, sin_ventana, _ = e.repartir(self.hilos(), frozenset())
        self.assertEqual(abiertos, ())
        self.assertEqual([h.nombre for h in sin_ventana], ["faro", "arboleda"])


class Vestir(ConCarpeta):
    def test_el_vinculo_del_estado_gana_sobre_el_cwd_del_panel(self):
        crudos = [Hilo(id="1", nombre="faro", ruta=Path("/donde/quedo/una/shell"))]
        vestidos = e.vestir(
            crudos, raiz=Path("/taller"), vinculos={"faro": "proyectos/faro"}
        )
        self.assertEqual(vestidos[0].ruta, Path("/taller/proyectos/faro"))

    def test_sin_vinculo_se_respeta_lo_que_dijo_el_multiplexor(self):
        crudos = [Hilo(id="1", nombre="faro", ruta=Path("/otra/parte"))]
        self.assertEqual(e.vestir(crudos, raiz=Path("/taller"))[0].ruta, Path("/otra/parte"))

    def test_un_vinculo_absoluto_no_se_pega_a_la_raiz(self):
        vestidos = e.vestir(
            [Hilo(id="1", nombre="faro")], raiz=Path("/taller"), vinculos={"faro": "/afuera/faro"}
        )
        self.assertEqual(vestidos[0].ruta, Path("/afuera/faro"))

    def test_el_estado_le_pone_al_hilo_todo_lo_que_sabe(self):
        vestido = e.vestir(
            [Hilo(id="1", nombre="faro")],
            prioridades={"faro": Prioridad.ALTA},
            archivados=["faro"],
            atenciones={"faro": Atencion.ESPERA},
            sesiones={"faro": ["aaa"]},
            tiempos={"faro": 1800.0},
            vistos={"faro": datetime(2026, 9, 18, 9, 0)},
        )[0]
        self.assertIs(vestido.prioridad, Prioridad.ALTA)
        self.assertTrue(vestido.archivado)
        self.assertIs(vestido.atencion, Atencion.ESPERA)
        self.assertEqual(vestido.sesiones, ("aaa",))
        self.assertEqual(vestido.tiempo, 1800.0)

    def test_la_foto_sirve_tal_cual_para_vestir(self):
        self.est.vincular("faro", "proyectos/faro")
        self.est.prioridad("faro", Prioridad.MEDIA)
        self.est.anotar_atencion("faro", Atencion.ESPERA)
        vestido = e.vestir(
            [Hilo(id="1", nombre="faro")], raiz=Path("/taller"), **self.est.foto(tope=HORA)
        )[0]
        self.assertEqual(vestido.ruta, Path("/taller/proyectos/faro"))
        self.assertIs(vestido.prioridad, Prioridad.MEDIA)
        self.assertIs(vestido.atencion, Atencion.ESPERA)


class Renombrar(ConCarpeta):
    def poblar(self, hilo="faro"):
        self.est.vincular(hilo, "proyectos/faro")
        self.est.prioridad(hilo, Prioridad.ALTA)
        self.est.anotar_atencion(hilo, Atencion.ESPERA)
        self.est.anotar_sesion(hilo, "aaa", revivir=False)
        self.est.archivar(hilo)

    def test_se_mueven_todas_las_llaves_a_la_vez(self):
        self.poblar()
        self.est.renombrar("faro", "el faro")
        self.assertEqual(self.est.vinculo("el faro"), "proyectos/faro")
        self.assertEqual(self.est.prioridades(), {"el faro": Prioridad.ALTA})
        self.assertIs(self.est.atencion("el faro"), Atencion.ESPERA)
        self.assertEqual(self.est.sesiones(), {"el faro": ("aaa",)})
        self.assertEqual(self.est.archivados(), {"el faro"})

    def test_el_registro_de_foco_no_se_reescribe(self):
        self.est.marcar("faro", datetime(2026, 9, 18, 9, 0))
        self.est.renombrar("faro", "el faro")
        self.assertEqual([m.hilo for m in self.est.marcas()], ["faro"])

    def test_fusionar_suma_las_conversaciones_y_no_pisa_el_vinculo(self):
        self.poblar()
        self.est.vincular("molino", "proyectos/molino")
        self.est.anotar_sesion("molino", "bbb", revivir=False)
        self.est.renombrar("faro", "molino", fusionar=True)
        self.assertEqual(self.est.vinculo("molino"), "proyectos/molino")
        self.assertEqual(set(self.est.sesiones()["molino"]), {"aaa", "bbb"})

    def test_un_nombre_vacio_se_rechaza(self):
        with self.assertRaises(e.ErrorDeEstado):
            self.est.renombrar("faro", "")

    def test_olvidar_borra_todo_menos_la_historia(self):
        self.poblar()
        self.est.marcar("faro", datetime(2026, 9, 18, 9, 0))
        self.est.olvidar("faro")
        self.assertEqual(self.est.vinculos(), {})
        self.assertEqual(self.est.prioridades(), {})
        self.assertEqual(self.est.sesiones(), {})
        self.assertEqual(self.est.archivados(), set())
        self.assertEqual(len(self.est.marcas()), 1)


class Escrituras(ConCarpeta):
    def test_se_escribe_entero_y_de_una_vez(self):
        # nada de temporales sueltos: quien lea, lee un JSON completo o el anterior
        self.est.vincular("faro", "proyectos/faro")
        sobrantes = [p.name for p in self.est.carpeta.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(sobrantes, [])

    def test_dos_escritores_no_se_pisan(self):
        # el caso real: dos sesiones escribiendo el mismo archivo a la vez
        hijo = os.fork()
        if hijo == 0:  # pragma: no cover - corre en el proceso hijo
            try:
                otro = e.Estado(self.est.carpeta)
                for i in range(50):
                    otro.prioridad(f"hilo-{i}", Prioridad.BAJA)
            finally:
                os._exit(0)
        for i in range(50):
            self.est.vincular(f"hilo-{i}", f"proyectos/p{i}")
        os.waitpid(hijo, 0)
        self.assertEqual(len(self.est.vinculos()), 50)
        self.assertEqual(len(self.est.prioridades()), 50)

    def test_el_candado_de_la_carpeta_anida_con_el_de_un_archivo(self):
        with self.est.bajo_candado():
            self.est.vincular("faro", "proyectos/faro")
        self.assertEqual(self.est.vinculo("faro"), "proyectos/faro")


if __name__ == "__main__":
    unittest.main()
