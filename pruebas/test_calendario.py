"""El proveedor de agenda: leer un .ics y contestar qué hay hoy.

El lector de iCalendar es la pieza que más fácil miente: el formato pliega líneas,
mezcla husos horarios y repite eventos con reglas. Casi todas estas pruebas son
calendarios chicos escritos a mano, y cada una pregunta por un día concreto.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import proveedores
from telar.config import Proveedor as CfgProveedor
from telar.proveedores import ErrorDeProveedor
from telar.proveedores import calendario as C

UTC = timezone.utc


def cfg(**opciones) -> CfgProveedor:
    return CfgProveedor(nombre="calendario", opciones=opciones)


def ics(*veventos: str) -> str:
    cuerpo = "\n".join(veventos)
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//pruebas//telar//ES\n{cuerpo}\nEND:VCALENDAR\n"


def vevento(**campos: str) -> str:
    lineas = ["BEGIN:VEVENT"] + [f"{k.replace('_', '-')}:{v}" for k, v in campos.items()] + ["END:VEVENT"]
    return "\n".join(lineas)


def leer(texto: str, dia: date, **kw):
    return C.eventos_del_dia(C.leer_ics(texto, local=UTC), dia, local=UTC, **kw)


# ── el formato ──────────────────────────────────────────────────────────────────

class Formato(Prueba):
    def test_una_linea_plegada_se_vuelve_a_juntar(self):
        crudo = "SUMMARY:Comité de\n  la mañana\nUID:1"
        self.assertEqual(C.desplegar(crudo), ["SUMMARY:Comité de la mañana", "UID:1"])

    def test_el_primer_dos_puntos_separa_salvo_entre_comillas(self):
        nombre, params, valor = C._propiedad('DTSTART;TZID="America/Santiago":20260618T100000')
        self.assertEqual(nombre, "DTSTART")
        self.assertEqual(params["TZID"], "America/Santiago")
        self.assertEqual(valor, "20260618T100000")

    def test_el_valor_puede_traer_dos_puntos(self):
        self.assertEqual(C._propiedad("URL:https://x.org/a")[2], "https://x.org/a")

    def test_las_comas_y_los_saltos_vienen_escapados(self):
        evs = leer(ics(vevento(UID="1", SUMMARY=r"Uno\, dos\nTres", DTSTART="20260618T100000Z")), date(2026, 6, 18))
        self.assertEqual(evs[0].titulo, "Uno, dos\nTres")

    def test_una_duracion_iso_se_entiende(self):
        self.assertEqual(C._duracion("PT1H30M"), timedelta(hours=1, minutes=30))
        self.assertEqual(C._duracion("P2D"), timedelta(days=2))


# ── qué hay hoy ─────────────────────────────────────────────────────────────────

class Dia(Prueba):
    def test_un_evento_suelto_sale_con_sus_cuatro_datos(self):
        texto = ics(vevento(
            UID="a1", SUMMARY="Comité", DTSTART="20260618T140000Z", DTEND="20260618T150000Z",
            URL="https://reunion.example/abc", LOCATION="sala 2",
        ))
        e = leer(texto, date(2026, 6, 18))[0]
        self.assertEqual(e.titulo, "Comité")
        self.assertEqual(e.inicio, datetime(2026, 6, 18, 14, tzinfo=UTC))
        self.assertEqual(e.fin, datetime(2026, 6, 18, 15, tzinfo=UTC))
        self.assertEqual(e.enlace, "https://reunion.example/abc")
        self.assertEqual(e.lugar, "sala 2")

    def test_el_de_ayer_no_es_el_de_hoy(self):
        texto = ics(vevento(UID="a1", SUMMARY="Comité", DTSTART="20260617T140000Z", DTEND="20260617T150000Z"))
        self.assertEqual(leer(texto, date(2026, 6, 18)), [])

    def test_los_eventos_salen_ordenados_por_hora(self):
        texto = ics(
            vevento(UID="b", SUMMARY="Tarde", DTSTART="20260618T160000Z"),
            vevento(UID="a", SUMMARY="Mañana", DTSTART="20260618T090000Z"),
        )
        self.assertEqual([e.titulo for e in leer(texto, date(2026, 6, 18))], ["Mañana", "Tarde"])

    def test_un_evento_de_dia_completo_empieza_a_medianoche_y_lo_dice(self):
        texto = ics("BEGIN:VEVENT\nUID:a1\nSUMMARY:Feriado\nDTSTART;VALUE=DATE:20260618\nEND:VEVENT")
        e = leer(texto, date(2026, 6, 18))[0]
        self.assertTrue(e.todo_el_dia)
        self.assertEqual(e.inicio.hour, 0)
        self.assertEqual(e.duracion, timedelta(days=1))

    def test_un_evento_que_cruza_la_medianoche_es_de_los_dos_dias(self):
        texto = ics(vevento(UID="a1", SUMMARY="Guardia", DTSTART="20260617T230000Z", DTEND="20260618T010000Z"))
        self.assertEqual([e.titulo for e in leer(texto, date(2026, 6, 17))], ["Guardia"])
        self.assertEqual([e.titulo for e in leer(texto, date(2026, 6, 18))], ["Guardia"])

    def test_la_duracion_reemplaza_al_fin(self):
        texto = ics(vevento(UID="a1", SUMMARY="Taller", DTSTART="20260618T100000Z", DURATION="PT2H"))
        self.assertEqual(leer(texto, date(2026, 6, 18))[0].fin, datetime(2026, 6, 18, 12, tzinfo=UTC))

    def test_un_evento_cancelado_no_ocupa_el_dia(self):
        texto = ics(vevento(UID="a1", SUMMARY="Anulada", DTSTART="20260618T100000Z", STATUS="CANCELLED"))
        self.assertEqual(leer(texto, date(2026, 6, 18)), [])

    def test_lo_que_hay_dentro_del_evento_no_se_confunde_con_el_evento(self):
        """Una alarma trae su propio DTSTART (relativo): si se leyera, movería la hora."""
        texto = ics(
            "BEGIN:VEVENT\nUID:a1\nSUMMARY:Comité\nDTSTART:20260618T100000Z\n"
            "BEGIN:VALARM\nTRIGGER:-PT15M\nACTION:DISPLAY\nSUMMARY:Aviso\nEND:VALARM\nEND:VEVENT"
        )
        e = leer(texto, date(2026, 6, 18))[0]
        self.assertEqual((e.titulo, e.inicio.hour), ("Comité", 10))

    def test_un_evento_roto_no_se_lleva_a_los_demas(self):
        texto = ics(
            vevento(UID="malo", SUMMARY="Ilegible", DTSTART="mañana por la tarde"),
            vevento(UID="bueno", SUMMARY="Comité", DTSTART="20260618T100000Z"),
        )
        self.assertEqual([e.titulo for e in leer(texto, date(2026, 6, 18))], ["Comité"])

    def test_un_huso_horario_se_respeta(self):
        texto = ics("BEGIN:VEVENT\nUID:a1\nSUMMARY:Comité\n"
                    "DTSTART;TZID=America/Santiago:20260618T090000\nEND:VEVENT")
        e = leer(texto, date(2026, 6, 18))[0]
        self.assertEqual(e.inicio.astimezone(UTC).hour, 13)  # Santiago en junio: UTC-4


# ── repeticiones ────────────────────────────────────────────────────────────────

class Repeticiones(Prueba):
    def semanal(self, **extra):
        regla = ";".join(f"{k}={v}" for k, v in {"FREQ": "WEEKLY", **extra}.items())
        return ics(vevento(
            UID="a1", SUMMARY="Semanal", DTSTART="20260601T100000Z", DTEND="20260601T110000Z", RRULE=regla,
        ))

    def test_una_semanal_cae_el_mismo_dia_de_la_semana(self):
        texto = self.semanal()
        self.assertEqual(len(leer(texto, date(2026, 6, 15))), 1)  # lunes
        self.assertEqual(leer(texto, date(2026, 6, 16)), [])      # martes

    def test_el_intervalo_se_cuenta(self):
        texto = self.semanal(INTERVAL="2")
        self.assertEqual(len(leer(texto, date(2026, 6, 15))), 1)
        self.assertEqual(leer(texto, date(2026, 6, 8)), [])

    def test_byday_agrega_los_dias_de_la_semana(self):
        texto = self.semanal(BYDAY="MO,WE")
        self.assertEqual(len(leer(texto, date(2026, 6, 17))), 1)  # miércoles
        self.assertEqual(leer(texto, date(2026, 6, 18)), [])      # jueves

    def test_until_termina_la_serie(self):
        texto = self.semanal(UNTIL="20260610T235959Z")
        self.assertEqual(len(leer(texto, date(2026, 6, 8))), 1)
        self.assertEqual(leer(texto, date(2026, 6, 15)), [])

    def test_count_termina_la_serie(self):
        texto = self.semanal(COUNT="2")
        self.assertEqual(len(leer(texto, date(2026, 6, 8))), 1)
        self.assertEqual(leer(texto, date(2026, 6, 15)), [])

    def test_exdate_saca_una_fecha_de_la_serie(self):
        texto = ics(vevento(
            UID="a1", SUMMARY="Semanal", DTSTART="20260601T100000Z", RRULE="FREQ=WEEKLY",
            EXDATE="20260615T100000Z",
        ))
        self.assertEqual(leer(texto, date(2026, 6, 15)), [])
        self.assertEqual(len(leer(texto, date(2026, 6, 22))), 1)

    def test_una_diaria_cae_todos_los_dias(self):
        texto = ics(vevento(UID="a1", SUMMARY="Diaria", DTSTART="20260601T100000Z", RRULE="FREQ=DAILY"))
        self.assertEqual(len(leer(texto, date(2026, 6, 18))), 1)

    def test_una_mensual_cae_el_mismo_dia_del_mes(self):
        texto = ics(vevento(UID="a1", SUMMARY="Mensual", DTSTART="20260118T100000Z", RRULE="FREQ=MONTHLY"))
        self.assertEqual(len(leer(texto, date(2026, 6, 18))), 1)
        self.assertEqual(leer(texto, date(2026, 6, 17)), [])

    def test_una_mensual_del_31_se_salta_los_meses_cortos(self):
        texto = ics(vevento(UID="a1", SUMMARY="Mensual", DTSTART="20260131T100000Z", RRULE="FREQ=MONTHLY"))
        self.assertEqual(len(leer(texto, date(2026, 3, 31))), 1)
        self.assertEqual(leer(texto, date(2026, 3, 1)), [])

    def test_una_anual_cae_el_mismo_dia_del_ano(self):
        texto = ics(vevento(UID="a1", SUMMARY="Anual", DTSTART="20200618T100000Z", RRULE="FREQ=YEARLY"))
        self.assertEqual(len(leer(texto, date(2026, 6, 18))), 1)

    def test_nada_ocurre_antes_de_que_la_serie_empiece(self):
        texto = ics(vevento(UID="a1", SUMMARY="Semanal", DTSTART="20260601T100000Z", RRULE="FREQ=WEEKLY"))
        self.assertEqual(leer(texto, date(2026, 5, 25)), [])

    def test_una_regla_ilegible_deja_el_evento_como_uno_suelto(self):
        texto = ics(vevento(UID="a1", SUMMARY="Rara", DTSTART="20260601T100000Z", RRULE="FREQ=SIEMPRE"))
        self.assertEqual(len(leer(texto, date(2026, 6, 1))), 1)
        self.assertEqual(leer(texto, date(2026, 6, 8)), [])


# ── las implementaciones ────────────────────────────────────────────────────────

class FuenteICS(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "agenda.ics"
        self.ruta.write_text(
            ics(vevento(UID="a1", SUMMARY="Comité", DTSTART="20260618T140000Z", DTEND="20260618T150000Z")),
            encoding="utf-8",
        )

    def test_lee_el_archivo_de_la_maquina(self):
        fuente = C.construir(cfg(tipo="ics", archivo=str(self.ruta)))
        self.assertEqual([e.titulo for e in fuente.eventos(date(2026, 6, 18))], ["Comité"])

    def test_con_archivo_el_alcance_dice_que_no_sale_de_la_maquina(self):
        fuente = C.construir(cfg(tipo="ics", archivo=str(self.ruta)))
        self.assertIn("no sale de la máquina", fuente.alcance)

    def test_con_url_el_alcance_dice_que_descarga(self):
        fuente = C.construir(cfg(tipo="ics", url="https://ejemplo.org/basic.ics"))
        self.assertIn("descarga", fuente.alcance)
        self.assertIn("https://ejemplo.org/basic.ics", fuente.alcance)

    def test_hay_que_elegir_entre_archivo_y_url(self):
        with self.assertRaises(ErrorDeProveedor):
            C.construir(cfg(tipo="ics"))
        with self.assertRaises(ErrorDeProveedor):
            C.construir(cfg(tipo="ics", archivo=str(self.ruta), url="https://ejemplo.org/x.ics"))

    def test_una_url_que_no_es_http_se_rechaza(self):
        with self.assertRaises(ErrorDeProveedor) as e:
            C.construir(cfg(tipo="ics", url="file:///etc/passwd"))
        self.assertIn("archivo", str(e.exception))

    def test_un_archivo_que_no_existe_se_dice(self):
        fuente = C.construir(cfg(tipo="ics", archivo=str(self.ruta.parent / "no-existe.ics")))
        with self.assertRaises(ErrorDeProveedor):
            fuente.eventos(date(2026, 6, 18))

    def test_cumple_el_protocolo_y_devuelve_items(self):
        fuente = C.construir(cfg(tipo="ics", archivo=str(self.ruta)))
        self.assertIsInstance(fuente, proveedores.Fuente)
        i = fuente.consultar(date(2026, 6, 18))[0]
        self.assertEqual((i.proveedor, i.titulo), ("calendario", "Comité"))
        self.assertIsNotNone(i.cuando)


def programa(cuerpo: str) -> list[str]:
    return [sys.executable, "-c", cuerpo]


class FuenteComando(Prueba):
    def test_lee_la_lista_que_imprime_el_programa(self):
        salida = json.dumps([
            {"id": "a1", "titulo": "Comité", "inicio": "2026-06-18T10:00:00+00:00",
             "fin": "2026-06-18T11:00:00+00:00", "enlace": "https://x", "lugar": "sala 2"},
        ])
        fuente = C.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        e = fuente.eventos(date(2026, 6, 18))[0]
        self.assertEqual((e.id, e.titulo, e.enlace, e.lugar), ("a1", "Comité", "https://x", "sala 2"))
        self.assertEqual(e.inicio, datetime(2026, 6, 18, 10, tzinfo=UTC))

    def test_tambien_acepta_un_objeto_con_la_clave_eventos(self):
        salida = json.dumps({"eventos": [{"titulo": "Uno", "inicio": "2026-06-18T10:00:00Z"}]})
        fuente = C.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        self.assertEqual([e.titulo for e in fuente.eventos(date(2026, 6, 18))], ["Uno"])

    def test_el_programa_recibe_el_dia_por_palabra_y_por_entorno(self):
        cuerpo = (
            "import os, sys, json; "
            "print(json.dumps([{'titulo': sys.argv[1] + ' ' + os.environ['TELAR_DIA'], "
            "'inicio': '2026-06-18T10:00:00Z'}]))"
        )
        fuente = C.construir(cfg(tipo="comando", comando=[*programa(cuerpo), "{dia}"]))
        self.assertEqual(fuente.eventos(date(2026, 6, 18))[0].titulo, "2026-06-18 2026-06-18")

    def test_una_hora_sin_zona_se_entiende_como_la_de_esta_maquina(self):
        salida = json.dumps([{"titulo": "Uno", "inicio": "2026-06-18T10:00:00"}])
        fuente = C.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        self.assertIsNotNone(fuente.eventos(date(2026, 6, 18))[0].inicio.tzinfo)

    def test_una_linea_de_shell_no_es_un_comando(self):
        with self.assertRaises(ErrorDeProveedor):
            C.construir(cfg(tipo="comando", comando="mi-agenda --json"))

    def test_un_evento_sin_titulo_se_dice(self):
        salida = json.dumps([{"inicio": "2026-06-18T10:00:00Z"}])
        fuente = C.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        with self.assertRaises(ErrorDeProveedor) as e:
            fuente.eventos(date(2026, 6, 18))
        self.assertIn("titulo", str(e.exception))

    def test_una_hora_ilegible_se_dice(self):
        salida = json.dumps([{"titulo": "Uno", "inicio": "mañana temprano"}])
        fuente = C.construir(cfg(tipo="comando", comando=programa(f"print({salida!r})")))
        with self.assertRaises(ErrorDeProveedor):
            fuente.eventos(date(2026, 6, 18))

    def test_un_programa_que_falla_trae_su_queja(self):
        cuerpo = "import sys; print('sin agenda', file=sys.stderr); sys.exit(2)"
        fuente = C.construir(cfg(tipo="comando", comando=programa(cuerpo)))
        with self.assertRaises(ErrorDeProveedor) as e:
            fuente.eventos(date(2026, 6, 18))
        self.assertIn("sin agenda", str(e.exception))


class Eleccion(Prueba):
    def test_ninguno_no_toca_nada(self):
        fuente = C.construir(cfg(tipo="ninguno"))
        self.assertEqual(fuente.eventos(date(2026, 6, 18)), [])
        self.assertEqual(fuente.consultar(date(2026, 6, 18)), [])
        self.assertEqual(fuente.alcance, "no toca nada")

    def test_sin_tipo_se_dice_cuales_hay(self):
        with self.assertRaises(ErrorDeProveedor) as e:
            C.construir(cfg())
        self.assertIn("ics", str(e.exception))

    def test_un_tipo_inventado_se_dice(self):
        with self.assertRaises(ErrorDeProveedor):
            C.construir(cfg(tipo="palomas"))

    def test_importar_el_modulo_lo_deja_en_el_registro(self):
        self.assertIn(C.NOMBRE, proveedores.REGISTRO)
        self.assertIsInstance(proveedores.obtener(cfg(tipo="ninguno")), proveedores.Fuente)

    def test_registrar_dos_veces_no_se_queja(self):
        C.registrar()
        C.registrar()


if __name__ == "__main__":
    unittest.main()
