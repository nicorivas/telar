"""El proveedor de tareas: qué urge, a qué hilo va, y de dónde salen.

Las dos mitades se prueban por separado a propósito. El núcleo (`urgencia`,
`hilo_de_tarea`) no toca disco ni procesos: se prueba con `Tarea` y `Hilo`
inventados, que es exactamente para lo que existe `telar.modelo`. Las tres
implementaciones sí tocan el mundo, y cada una se prueba contra un mundo chico
armado en un directorio temporal.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import proveedores
from telar.config import Proveedor as CfgProveedor
from telar.modelo import Hilo, Prioridad
from telar.proveedores import ErrorDeProveedor
from telar.proveedores import tareas as T

HOY = date(2026, 6, 15)


def tarea(**kw) -> T.Tarea:
    base = {"id": "T1", "texto": "algo"}
    return T.Tarea(**(base | kw))


def cfg(**opciones) -> CfgProveedor:
    return CfgProveedor(nombre="tareas", opciones=opciones)


# ── el núcleo: qué urge ─────────────────────────────────────────────────────────

class Urgencia(Prueba):
    def test_lo_vencido_cuenta_como_hoy_y_no_como_deuda(self):
        vencida = tarea(vence=date(2026, 1, 1), prioridad=Prioridad.ALTA)
        hoy_mismo = tarea(vence=HOY, prioridad=Prioridad.ALTA)
        self.assertEqual(T.urgencia(vencida, HOY)[0], T.urgencia(hoy_mismo, HOY)[0])

    def test_una_tarea_sin_fecha_cuenta_como_si_venciera_hoy(self):
        self.assertEqual(T.urgencia(tarea(prioridad=Prioridad.ALTA), HOY)[0], 0)

    def test_cada_nivel_de_prioridad_suma_dos_dias(self):
        pesos = [T.urgencia(tarea(prioridad=p), HOY)[0] for p in (Prioridad.ALTA, Prioridad.MEDIA, Prioridad.BAJA)]
        self.assertEqual(pesos, [0, 2, 4])

    def test_sin_prioridad_pesa_mas_que_la_mas_baja(self):
        self.assertGreater(T.urgencia(tarea(), HOY)[0], T.urgencia(tarea(prioridad=Prioridad.BAJA), HOY)[0])

    def test_el_plazo_le_puede_ganar_a_la_prioridad(self):
        """El caso que justifica la fórmula: ordenar por prioridad primero escondía
        lo que vencía mañana, y una alta sin fecha no entraba nunca."""
        manana = tarea(id="T1", texto="media que vence mañana", prioridad=Prioridad.MEDIA, vence=date(2026, 6, 16))
        vencida = tarea(id="T2", texto="baja vencida", prioridad=Prioridad.BAJA, vence=date(2026, 6, 1))
        lejana = tarea(id="T3", texto="alta en cuatro días", prioridad=Prioridad.ALTA, vence=date(2026, 6, 19))
        orden = sorted([vencida, lejana, manana], key=lambda t: T.urgencia(t, HOY))
        self.assertEqual([t.id for t in orden], ["T1", "T2", "T3"])

    def test_los_empates_se_rompen_por_fecha_y_despues_por_numero_de_id(self):
        a = tarea(id="T9", prioridad=Prioridad.MEDIA)
        b = tarea(id="T84", prioridad=Prioridad.MEDIA)
        self.assertEqual([t.id for t in sorted([b, a], key=lambda t: T.urgencia(t, HOY))], ["T9", "T84"])


class Urgentes(Prueba):
    def setUp(self):
        super().setUp()
        self.lote = [
            tarea(id="T1", vence=date(2026, 6, 1)),                              # vencida
            tarea(id="T2", vence=date(2026, 6, 18)),                             # dentro de 7 días
            tarea(id="T3", vence=date(2026, 12, 1)),                             # lejana
            tarea(id="T4", prioridad=Prioridad.ALTA),                            # alta sin fecha
            tarea(id="T5", prioridad=Prioridad.BAJA),                            # baja sin fecha
            tarea(id="T6", vence=date(2026, 6, 1), espera="@quien"),             # espera a otro
            tarea(id="T7", vence=date(2026, 6, 1), hecha=True),                  # cerrada
        ]

    def test_entran_las_vencidas_las_de_la_semana_y_la_alta_sin_fecha(self):
        self.assertEqual({t.id for t in T.urgentes(self.lote, HOY)}, {"T1", "T2", "T4"})

    def test_lo_que_espera_a_otro_no_depende_de_ti_y_no_entra(self):
        self.assertNotIn("T6", [t.id for t in T.urgentes(self.lote, HOY)])

    def test_salen_ordenadas_por_urgencia(self):
        self.assertEqual([t.id for t in T.urgentes(self.lote, HOY)], ["T4", "T1", "T2"])

    def test_la_ventana_se_puede_abrir(self):
        self.assertIn("T3", [t.id for t in T.urgentes(self.lote, HOY, dias=365)])


# ── el núcleo: a qué hilo va ────────────────────────────────────────────────────

class Etiquetas(Prueba):
    def test_la_etiqueta_que_es_el_hilo_calza_entero(self):
        self.assertEqual(T.etiqueta_calza("faro", "faro", "proyectos/faro"), 2)
        self.assertEqual(T.etiqueta_calza("#faro", "El Faro", "proyectos/faro"), 2)

    def test_los_guiones_no_cuentan_al_comparar(self):
        self.assertEqual(T.etiqueta_calza("faronorte", "el norte", "proyectos/faro-norte"), 2)

    def test_la_etiqueta_que_empieza_la_carpeta_calza_a_medias(self):
        self.assertEqual(T.etiqueta_calza("molino", "Molino de viento", "proyectos/molino-de-viento"), 1)

    def test_una_palabra_propia_del_nombre_calza_a_medias(self):
        self.assertEqual(T.etiqueta_calza("molino", "Proyecto MOLINO", "encargos/e-4454"), 1)

    def test_la_etiqueta_mas_especifica_que_el_hilo_no_calza(self):
        self.assertEqual(T.etiqueta_calza("faro-norte", "faro", "proyectos/faro"), 0)

    def test_calzar_el_final_no_es_calzar(self):
        self.assertEqual(T.etiqueta_calza("faro", "puerto", "proyectos/puerto-faro"), 0)

    def test_una_palabra_generica_no_calza_a_medias_con_nadie(self):
        self.assertEqual(T.etiqueta_calza("proyecto", "El taller", "carpetas/proyecto-faro"), 0)

    def test_una_palabra_generica_que_es_el_hilo_entero_sigue_calzando(self):
        """Si alguien llamó a su hilo «proyecto», la etiqueta `#proyecto` lo nombra
        a él y a nadie más: lo genérico solo bloquea el calce a medias."""
        self.assertEqual(T.etiqueta_calza("proyecto", "proyecto", "carpetas/proyecto"), 2)

    def test_cada_repositorio_trae_sus_propias_genericas(self):
        self.assertEqual(T.etiqueta_calza("faro", "El taller", "proyectos/faro-norte"), 1)
        self.assertEqual(
            T.etiqueta_calza("faro", "El taller", "proyectos/faro-norte", genericas={"faro"}), 0
        )


class Enrutado(Prueba):
    def setUp(self):
        super().setUp()
        self.raiz = Path("/trabajo")
        self.faro = Hilo(id="1", nombre="faro", ruta=self.raiz / "proyectos/faro")
        self.molino = Hilo(id="2", nombre="molino", ruta=self.raiz / "proyectos/molino")
        self.hilos = [self.faro, self.molino]

    def enrutar(self, t, hilos=None, **kw):
        return T.hilo_de_tarea(t, hilos if hilos is not None else self.hilos, raiz=self.raiz, **kw)

    def test_el_hilo_que_ya_es_de_la_tarea_gana_a_todo(self):
        propio = Hilo(id="9", nombre="⚑ T84 medir el alcance")
        elegido = self.enrutar(tarea(id="T84", etiquetas=("faro",)), [*self.hilos, propio])
        self.assertIs(elegido, propio)

    def test_un_id_no_calza_con_otro_que_lo_contiene(self):
        propio = Hilo(id="9", nombre="⚑ T840 otra cosa")
        self.assertIsNone(self.enrutar(tarea(id="T84"), [propio]))

    def test_la_ruta_del_origen_manda_a_su_hilo(self):
        t = tarea(texto="medir", origen="proyectos/faro/README.md")
        self.assertIs(self.enrutar(t), self.faro)

    def test_gana_la_ruta_mas_especifica(self):
        contenedor = Hilo(id="3", nombre="proyectos", ruta=self.raiz / "proyectos")
        t = tarea(origen="proyectos/faro/README.md")
        self.assertIs(self.enrutar(t, [contenedor, self.faro]), self.faro)

    def test_una_carpeta_contenedora_se_puede_dejar_fuera_de_la_competencia(self):
        contenedor = Hilo(id="3", nombre="proyectos", ruta=self.raiz / "proyectos")
        t = tarea(texto="algo sin ruta", etiquetas=("proyectos",))
        self.assertIsNone(self.enrutar(t, [contenedor], profundidad_minima=1))

    def test_sin_ruta_dicha_decide_la_etiqueta(self):
        self.assertIs(self.enrutar(tarea(etiquetas=("molino",))), self.molino)

    def test_el_hilo_con_agente_gana_el_empate(self):
        con_agente = Hilo(id="3", nombre="faro", ruta=self.raiz / "otros/faro", sesiones=("a1",))
        elegido = T.hilo_de_tarea(tarea(etiquetas=("faro",)), [self.faro, con_agente], raiz=self.raiz)
        self.assertIs(elegido, con_agente)

    def test_entre_dos_sin_agente_gana_el_de_foco_mas_reciente(self):
        viejo = Hilo(id="3", nombre="faro", ruta=self.raiz / "a/faro", visto=datetime(2026, 1, 1))
        nuevo = Hilo(id="4", nombre="faro", ruta=self.raiz / "b/faro", visto=datetime(2026, 6, 1))
        self.assertIs(T.hilo_de_tarea(tarea(etiquetas=("faro",)), [viejo, nuevo], raiz=self.raiz), nuevo)

    def test_un_hilo_archivado_no_compite_salvo_que_se_pida(self):
        guardado = Hilo(id="3", nombre="faro", ruta=self.raiz / "proyectos/faro", archivado=True)
        t = tarea(etiquetas=("faro",))
        self.assertIsNone(T.hilo_de_tarea(t, [guardado], raiz=self.raiz))
        self.assertIs(T.hilo_de_tarea(t, [guardado], raiz=self.raiz, incluir_archivados=True), guardado)

    def test_un_hilo_sin_carpeta_no_es_destino(self):
        self.assertIsNone(self.enrutar(tarea(etiquetas=("suelto",)), [Hilo(id="5", nombre="suelto")]))

    def test_si_nada_calza_no_se_inventa_un_destino(self):
        self.assertIsNone(self.enrutar(tarea(texto="comprar café", etiquetas=("casa",))))


# ── markdown ────────────────────────────────────────────────────────────────────

DOCUMENTO = """\
# Faro

## Estado

La lámpara está montada.

## Pendientes

- [x] Desmontar la lámpara vieja
- [>] Ajustar la velocidad de giro  #faro
- [ ] Medir el alcance real  vence:2026-06-30  !alta  #faro  <!-- id: T84 -->
- [ ] Entregar el [informe](https://ejemplo.org/informe)  espera:@municipalidad  !baja

## Esperando

- [ ] Esta casilla es de otra sección
"""


class Markdown(Prueba):
    def leer(self, texto=DOCUMENTO, **kw):
        return T.leer_markdown(texto, "proyectos/faro/README.md", **kw)

    def test_solo_siguen_activas_la_casilla_vacia_y_la_de_en_curso(self):
        estados = {t.texto: (t.hecha, t.en_curso) for t in self.leer()}
        self.assertEqual(estados["Desmontar la lámpara vieja"], (True, False))
        self.assertEqual(estados["Ajustar la velocidad de giro"], (False, True))
        self.assertEqual(estados["Medir el alcance real"], (False, False))

    def test_el_id_del_comentario_html_es_el_id_de_la_tarea(self):
        medir = next(t for t in self.leer() if t.texto.startswith("Medir"))
        self.assertEqual(medir.id, "T84")

    def test_los_tokens_salen_del_texto_y_quedan_en_sus_campos(self):
        medir = next(t for t in self.leer() if t.texto.startswith("Medir"))
        self.assertEqual(medir.texto, "Medir el alcance real")
        self.assertEqual(medir.vence, date(2026, 6, 30))
        self.assertIs(medir.prioridad, Prioridad.ALTA)
        self.assertEqual(medir.etiquetas, ("faro",))

    def test_un_enlace_markdown_deja_su_etiqueta_en_el_texto(self):
        entregar = next(t for t in self.leer() if t.texto.startswith("Entregar"))
        self.assertEqual(entregar.texto, "Entregar el informe")
        self.assertEqual(entregar.enlace, "https://ejemplo.org/informe")
        self.assertEqual(entregar.espera, "@municipalidad")
        self.assertIs(entregar.prioridad, Prioridad.BAJA)

    def test_la_tarea_sin_id_recibe_uno_estable(self):
        una = self.leer()[1]
        otra = self.leer()[1]
        self.assertEqual(una.id, otra.id)
        self.assertTrue(una.id.startswith("auto-"))

    def test_el_id_derivado_depende_del_documento(self):
        aqui = T.leer_markdown("- [ ] Igual", "a/README.md")[0]
        alla = T.leer_markdown("- [ ] Igual", "b/README.md")[0]
        self.assertNotEqual(aqui.id, alla.id)

    def test_el_origen_es_la_ruta_del_documento(self):
        self.assertEqual(self.leer()[0].origen, "proyectos/faro/README.md")

    def test_sin_encabezado_se_leen_todas_las_casillas(self):
        self.assertEqual(len(self.leer()), 5)

    def test_con_encabezado_se_lee_solo_esa_seccion(self):
        import re

        textos = [t.texto for t in self.leer(encabezado=re.compile(r"^##\s+Pendientes"))]
        self.assertEqual(len(textos), 4)
        self.assertNotIn("Esta casilla es de otra sección", textos)

    def test_lo_que_no_se_reconoce_se_queda_en_el_texto(self):
        t = T.leer_markdown("- [ ] Llamar al taller (urgente, dijo él)")[0]
        self.assertEqual(t.texto, "Llamar al taller (urgente, dijo él)")
        self.assertEqual(t.etiquetas, ())


class FuenteMarkdown(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "proyectos" / "faro").mkdir(parents=True)
        (self.raiz / "proyectos" / "faro" / "README.md").write_text(DOCUMENTO, encoding="utf-8")

    def fuente(self, **opciones):
        return T.construir(cfg(tipo="markdown", raiz=str(self.raiz), **opciones))

    def test_lista_solo_las_activas(self):
        activas = self.fuente(rutas=["proyectos/*/README.md"]).activas(HOY)
        self.assertEqual(len(activas), 4)
        self.assertTrue(all(t.activa for t in activas))

    def test_el_alcance_dice_que_no_sale_de_la_maquina(self):
        self.assertIn("no sale de la máquina", self.fuente().alcance)

    def test_cumple_el_protocolo_y_devuelve_items(self):
        fuente = self.fuente(rutas=["proyectos/*/README.md"])
        self.assertIsInstance(fuente, proveedores.Fuente)
        items = fuente.consultar(HOY)
        self.assertEqual({i.proveedor for i in items}, {"tareas"})
        self.assertIn("Medir el alcance real", [i.titulo for i in items])

    def test_un_glob_que_sale_de_la_raiz_se_rechaza(self):
        for malo in ("/etc/*.md", "../*.md"):
            with self.assertRaises(ErrorDeProveedor):
                self.fuente(rutas=[malo])

    def test_una_carpeta_que_no_existe_se_dice(self):
        fuente = T.construir(cfg(tipo="markdown", raiz=str(self.raiz / "no-existe")))
        with self.assertRaises(ErrorDeProveedor):
            fuente.activas(HOY)

    def test_sin_rutas_declaradas_mira_los_readme_de_primer_nivel(self):
        (self.raiz / "molino").mkdir()
        (self.raiz / "molino" / "README.md").write_text("- [ ] Cambiar el aspa\n", encoding="utf-8")
        self.assertEqual([t.texto for t in self.fuente().activas(HOY)], ["Cambiar el aspa"])


# ── comando ─────────────────────────────────────────────────────────────────────

def programa(cuerpo: str) -> list[str]:
    """Un programa de una línea que hace de gestor de tareas externo."""
    return [sys.executable, "-c", cuerpo]


class FuenteComando(Prueba):
    def test_lee_la_lista_que_imprime_el_programa(self):
        salida = json.dumps([
            {"id": "T84", "texto": "Medir el alcance", "prioridad": "alta",
             "vence": "2026-06-30", "etiquetas": ["#faro"], "enlace": "https://x",
             "espera": "", "hecha": False},
            {"texto": "Ya está", "hecha": True},
        ])
        fuente = T.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        activas = fuente.activas(HOY)
        self.assertEqual(len(activas), 1)
        una = activas[0]
        self.assertEqual((una.id, una.texto, una.vence), ("T84", "Medir el alcance", date(2026, 6, 30)))
        self.assertIs(una.prioridad, Prioridad.ALTA)
        self.assertEqual(una.etiquetas, ("faro",))

    def test_tambien_acepta_un_objeto_con_la_clave_tareas(self):
        salida = json.dumps({"tareas": [{"texto": "Una"}]})
        fuente = T.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        self.assertEqual([t.texto for t in fuente.activas(HOY)], ["Una"])

    def test_el_programa_recibe_el_dia_por_palabra_y_por_entorno(self):
        cuerpo = (
            "import os, sys, json; "
            "print(json.dumps([{'texto': sys.argv[1] + ' ' + os.environ['TELAR_DIA']}]))"
        )
        fuente = T.construir(cfg(tipo="comando", comando=[*programa(cuerpo), "{dia}"]))
        self.assertEqual(fuente.activas(HOY)[0].texto, "2026-06-15 2026-06-15")

    def test_una_linea_de_shell_no_es_un_comando(self):
        with self.assertRaises(ErrorDeProveedor) as e:
            T.construir(cfg(tipo="comando", comando="mis-tareas --json"))
        self.assertIn("lista de palabras", str(e.exception))

    def test_un_programa_que_no_existe_se_dice(self):
        fuente = T.construir(cfg(tipo="comando", comando=["telar-no-existe-jamas"]))
        with self.assertRaises(ErrorDeProveedor):
            fuente.activas(HOY)

    def test_un_programa_que_falla_trae_su_queja(self):
        cuerpo = "import sys; print('se cayó el puente', file=sys.stderr); sys.exit(3)"
        fuente = T.construir(cfg(tipo="comando", comando=programa(cuerpo)))
        with self.assertRaises(ErrorDeProveedor) as e:
            fuente.activas(HOY)
        self.assertIn("se cayó el puente", str(e.exception))

    def test_lo_que_no_es_json_se_dice(self):
        fuente = T.construir(cfg(tipo="comando", comando=programa("print('hola')")))
        with self.assertRaises(ErrorDeProveedor) as e:
            fuente.activas(HOY)
        self.assertIn("JSON", str(e.exception))

    def test_una_tarea_sin_texto_se_dice(self):
        fuente = T.construir(cfg(tipo="comando", comando=programa("print('[{\"id\": \"T1\"}]')")))
        with self.assertRaises(ErrorDeProveedor) as e:
            fuente.activas(HOY)
        self.assertIn("texto", str(e.exception))

    def test_una_prioridad_inventada_se_dice(self):
        salida = json.dumps([{"texto": "Una", "prioridad": "urgentísima"}])
        fuente = T.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        with self.assertRaises(ErrorDeProveedor):
            fuente.activas(HOY)

    def test_no_espera_para_siempre(self):
        cuerpo = "import time; time.sleep(30)"
        fuente = T.construir(cfg(tipo="comando", comando=programa(cuerpo), tiempo_maximo=0.3))
        with self.assertRaises(ErrorDeProveedor) as e:
            fuente.activas(HOY)
        self.assertIn("no respondió", str(e.exception))


# ── ninguno, y cómo se elige ────────────────────────────────────────────────────

class Eleccion(Prueba):
    def test_ninguno_no_toca_nada(self):
        fuente = T.construir(cfg(tipo="ninguno"))
        self.assertEqual(fuente.activas(HOY), [])
        self.assertEqual(fuente.consultar(HOY), [])
        self.assertEqual(fuente.alcance, "no toca nada")

    def test_sin_tipo_se_dice_cuales_hay(self):
        with self.assertRaises(ErrorDeProveedor) as e:
            T.construir(cfg())
        self.assertIn("markdown", str(e.exception))

    def test_un_tipo_inventado_se_dice(self):
        with self.assertRaises(ErrorDeProveedor) as e:
            T.construir(cfg(tipo="telepatía"))
        self.assertIn("telepatía", str(e.exception))

    def test_importar_el_modulo_lo_deja_en_el_registro(self):
        self.assertIn(T.NOMBRE, proveedores.REGISTRO)
        self.assertIsInstance(proveedores.obtener(cfg(tipo="ninguno")), proveedores.Fuente)

    def test_registrar_dos_veces_no_se_queja(self):
        T.registrar()
        T.registrar()

    def test_una_fuente_caida_no_apaga_el_telar(self):
        rota = CfgProveedor(nombre="tareas", opciones={"tipo": "comando", "comando": ["telar-no-existe"]})
        items, fallas = proveedores.consultar([rota], HOY)
        self.assertEqual(items, [])
        self.assertEqual(len(fallas), 1)
        self.assertIn("tareas", fallas[0])


class Conversion(Prueba):
    def test_una_tarea_se_vuelve_item_sin_perder_lo_suyo(self):
        t = tarea(id="T84", texto="Medir", prioridad=Prioridad.ALTA, vence=date(2026, 6, 30),
                  etiquetas=("faro",), enlace="https://x", origen="proyectos/faro/README.md")
        i = t.item(hilo="3")
        self.assertEqual((i.proveedor, i.id, i.titulo, i.hilo, i.url), ("tareas", "T84", "Medir", "3", "https://x"))
        self.assertEqual(i.cuando.date(), date(2026, 6, 30))
        self.assertEqual(i.datos["prioridad"], 1)
        self.assertEqual(i.datos["etiquetas"], ["faro"])

    def test_una_tarea_se_vuelve_pendiente_de_una_ficha(self):
        p = tarea(id="T84", texto="Medir", en_curso=True, origen="README.md").pendiente()
        self.assertEqual((p.texto, p.id, p.en_curso, p.hecho), ("Medir", "T84", True, False))

    def test_una_tarea_que_espera_no_es_tuya_pero_sigue_activa(self):
        t = tarea(espera="@quien")
        self.assertTrue(t.activa)
        self.assertFalse(t.tuya)


if __name__ == "__main__":
    unittest.main()
