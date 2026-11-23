"""Las pasadas de un resultado (telar.pasadas): agregar una (validada, atómica, sin repetir id), importar un .jsonl
(idempotente), lo visto (solo avanza) y lo sin ver, aquí y por el bus; la orden y la API."""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import HAY_FASTAPI, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar import config as mod_config
from telar import pasadas


def una(id_="2026-11-18T13:00", **cambios) -> dict:
    """Una pasada de pulso que cumple el esquema."""
    p = {
        "id": id_, "termino": id_[:11] + "13:12", "modo": "dia", "resumen": "3 tareas nuevas, 2 te esperan",
        "fuentes": [{"fuente": "correo-trabajo", "llegaron": 12, "archivados": 7, "error": ""},
                    {"fuente": "whatsapp", "llegaron": 3, "archivados": 0, "error": "no respondió"}],
        "tareas": {"nuevas": [{"id": "tarea:T580", "linea": "Arcilla: retrospectiva", "por": "correo de Carla", "fuente": "correo-trabajo"}],
                   "avanzadas": [{"id": "tarea:T540", "linea": "nota de Carla", "por": "minuta del 17-nov", "enlace": "archivo:minuta.md"}],
                   "cerradas": [{"id": "tarea:T512", "como": "hecha", "linea": "el correo salió", "por": "respuesta de Ana"}]},
        "te_esperan": [{"id": "tarea:T540", "pide": "decidir", "linea": "Molino: ¿se conecta?", "peso": 3, "vence": "2026-11-20"}],
        "borradores": [{"para": "Inés Vega", "asunto": "Informe", "enlace": "gmail:r-1", "tarea": "tarea:T470", "por": "correo de Inés"}],
    }
    p.update(cambios)
    return p


class ConCarpeta(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.carpeta = Path(self.tmp.name) / "pulso"

    def config(self, esquema="pulso", **extra):
        return mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                 resultados=(mod_config.Resultado(clave="pulso", carpeta=str(self.carpeta), pasadas=esquema, **extra),),
                                 **({"bus": extra.pop("bus")} if "bus" in extra else {}))

    def dia(self, dia="2026-11-18") -> list:
        return json.loads((self.carpeta / f"{dia}.json").read_text())["pasadas"]


class Validar(Prueba):
    def test_una_pasada_bien_hecha_no_tiene_errores_y_lo_extra_pasa(self):
        self.assertEqual(pasadas.validar("pulso", una()), [])
        self.assertEqual(pasadas.validar("pulso", una(pedida=True, seco=True, seco_detalle={"x": 1})), [])
        # una fuente puede decir algo sin haber fallado
        p = una()
        p["fuentes"][0]["nota"] = "ventana desde 12:41"
        self.assertEqual(pasadas.validar("pulso", p), [])
        # y sin `error`, no falló (así las escribe Secretaría desde las 15:00)
        del p["fuentes"][0]["error"]
        self.assertEqual(pasadas.validar("pulso", p), [])
        p["fuentes"][0]["error"] = None
        self.assertEqual(pasadas.validar("pulso", p), ["fuentes[0].error: se esperaba un texto, llegó null"])
        # el id con segundos, para dos que empezaron en el mismo minuto; un id de tarea que todavía no es dirección
        p = una("2026-11-18T13:00:30")
        p["tareas"]["nuevas"][0]["id"] = "HABRIA tarea nueva"
        self.assertEqual(pasadas.validar("pulso", p), [])

    def test_lo_que_el_esquema_nombra_se_revisa_estricto_y_dice_donde(self):
        p = una(modo="tarde", pedida="sí")
        del p["resumen"]
        p["fuentes"][0]["llegaron"] = True
        p["tareas"]["cerradas"][0]["como"] = "lista"
        p["te_esperan"][0].update(peso=4, vence="20-nov", pide="mirar")
        p["borradores"][0]["para"] = "  "
        del p["tareas"]["avanzadas"]
        errores = pasadas.validar("pulso", p)
        for esperado in ("modo: dia | noche; llegó 'tarde'", "pedida: true o false; llegó un texto", "resumen: falta",
                         "fuentes[0].llegaron: se esperaba un número entero, llegó true",
                         "tareas.avanzadas: falta (una lista, aunque esté vacía)",
                         "tareas.cerradas[0].como: hecha | caduca | descartada; llegó 'lista'",
                         "te_esperan[0].peso: de 1 a 3; llegó 4", "te_esperan[0].vence: AAAA-MM-DD o vacío; llegó '20-nov'",
                         "te_esperan[0].pide: decidir | aprobar | cerrar | hacer; llegó 'mirar'", "borradores[0].para: está vacío"):
            self.assertIn(esperado, errores)
        self.assertEqual(len(errores), 10, errores)

    def test_las_vencidas_sin_propuesta_son_opcionales_y_van_por_su_direccion(self):
        self.assertEqual(pasadas.validar("pulso", una(vencidas_sin_propuesta=["tarea:T405", "tarea:T566"])), [])
        self.assertEqual(pasadas.validar("pulso", una(vencidas_sin_propuesta=[])), [])
        # el código solo (como venía en la pasada de las 15:00), vacío o lo que no es texto: no
        errores = pasadas.validar("pulso", una(vencidas_sin_propuesta=["T405", "", "tarea:T1 y más", 405]))
        self.assertEqual(errores, ["vencidas_sin_propuesta[0]: una dirección (tarea:T405); llegó 'T405'",
                                   "vencidas_sin_propuesta[1]: una dirección (tarea:T405); llegó ''",
                                   "vencidas_sin_propuesta[2]: una dirección (tarea:T405); llegó 'tarea:T1 y más'",
                                   "vencidas_sin_propuesta[3]: una dirección (tarea:T405); llegó un número"])
        self.assertEqual(pasadas.validar("pulso", una(vencidas_sin_propuesta="tarea:T405")),
                         ["vencidas_sin_propuesta: se esperaba una lista, llegó un texto"])

    def test_cada_cambio_dice_por_que_y_lo_que_te_espera_es_opcional(self):
        p = una()
        del p["tareas"]["nuevas"][0]["por"]
        p["tareas"]["avanzadas"][0]["por"] = " "
        p["borradores"][0]["fuente"] = 3
        p["tareas"]["cerradas"][0]["enlace"] = ["x"]
        self.assertEqual(pasadas.validar("pulso", p), ["tareas.nuevas[0].por: falta", "tareas.avanzadas[0].por: está vacío",
                                                      "tareas.cerradas[0].enlace: se esperaba un texto, llegó una lista",
                                                      "borradores[0].fuente: se esperaba un texto, llegó un número"])
        sin = una()
        del sin["te_esperan"]
        self.assertEqual(pasadas.validar("pulso", sin), [], "te_esperan se acepta y no hace falta")
        self.assertEqual(pasadas.validar("pulso", una(te_esperan=[{"id": "x"}]))[0], "te_esperan[0].pide: falta", "si viene, se revisa")

    def test_lo_que_cambio_son_las_tareas_y_los_borradores(self):
        self.assertTrue(pasadas.hay_cambios(una()))
        quieta = una(tareas={"nuevas": [], "avanzadas": [], "cerradas": []}, borradores=[])
        self.assertFalse(pasadas.hay_cambios(quieta), "lo que te espera y las fuentes no son cambios")
        self.assertEqual(pasadas.clasificar(quieta, ("trabajo",), {})["mundos_cambios"], [])
        self.assertEqual(pasadas.clasificar(una(), ("trabajo",), {})["mundos_cambios"], [""])

    def test_el_id_es_la_hora_en_que_empezo(self):
        for malo in ("2026-11-18", "13:00", "2026-11-18T25:00", "2026-02-30T10:00", "2026-11-18T13:00-03:00", ""):
            self.assertTrue(any(e.startswith("id:") for e in pasadas.validar("pulso", una(malo))), malo)
        self.assertEqual(pasadas.dia_de("2026-11-18T23:30"), "2026-11-18")
        self.assertIn("termino: la hora en que terminó, AAAA-MM-DDTHH:MM; llegó 'luego'", pasadas.validar("pulso", una(termino="luego")))

    def test_libre_solo_pide_su_id_y_lo_que_no_es_un_objeto_no_es_una_pasada(self):
        self.assertEqual(pasadas.validar("libre", {"id": "2026-11-18T13:00", "lo-que-sea": [1]}), [])
        self.assertEqual(pasadas.validar("libre", {"id": "ayer"})[0][:3], "id:")
        self.assertEqual(pasadas.validar("pulso", [una()]), ["una pasada es un objeto JSON; llegó una lista"])
        self.assertIn("pesa", pasadas.validar("pulso", una(resumen="x" * (pasadas.MAX_PASADA + 1)))[0])


class Agregar(ConCarpeta):
    def test_se_agrega_al_final_de_su_dia_tal_cual_con_lo_extra(self):
        cfg = self.config()
        r = pasadas.agregar_local(cfg, "pulso", [una(seco_detalle={"habria": 3})])
        self.assertEqual((r["ok"], r["agregadas"], r["en_el_dia"]), (True, ["2026-11-18T13:00"], {"2026-11-18": 1}))
        self.assertTrue(pasadas.agregar_local(cfg, "pulso", [una("2026-11-18T14:00")])["ok"])
        self.assertEqual([p["id"] for p in self.dia()], ["2026-11-18T13:00", "2026-11-18T14:00"])
        self.assertEqual(self.dia()[0], una(seco_detalle={"habria": 3}))
        # se lee como cualquier resultado: el día entero
        from telar import resultados

        self.assertEqual(len(resultados.local(cfg, "pulso", "2026-11-18")["contenido"]["pasadas"]), 2)
        self.assertEqual(resultados.local(cfg, "pulso", "ultimo")["dias"], ["2026-11-18"], "lo visto y el candado no son días")
        # solo para la persona
        self.assertEqual(os.stat(self.carpeta / "2026-11-18.json").st_mode & 0o777, 0o600)

    def test_el_dia_es_el_del_id_no_el_de_cuando_llega(self):
        cfg = self.config()
        pasadas.agregar_local(cfg, "pulso", [una("2026-11-18T23:30", modo="noche", termino="2026-11-19T00:20")])
        self.assertEqual(self.dia("2026-11-18")[0]["modo"], "noche")
        self.assertFalse((self.carpeta / "2026-11-19.json").exists())

    def test_un_id_repetido_es_un_error_y_no_se_reescribe_nada(self):
        cfg = self.config()
        pasadas.agregar_local(cfg, "pulso", [una()])
        antes = (self.carpeta / "2026-11-18.json").read_bytes()
        r = pasadas.agregar_local(cfg, "pulso", [una(resumen="otra cosa")])
        self.assertEqual((r["ok"], r["repetida"]), (False, "2026-11-18T13:00"))
        self.assertIn("ya está en el 2026-11-18; no se reescribe", r["error"])
        self.assertIn("(igual a esta: ya había llegado)", pasadas.agregar_local(cfg, "pulso", [una()])["error"])
        self.assertEqual((self.carpeta / "2026-11-18.json").read_bytes(), antes)

    def test_una_mala_no_escribe_nada_y_los_errores_dicen_cual(self):
        cfg = self.config()
        r = pasadas.agregar_local(cfg, "pulso", [una(), una("2026-11-18T14:00", modo="x")])
        self.assertFalse(r["ok"])
        self.assertEqual(r["errores"], ["pasada 2 (2026-11-18T14:00): modo: dia | noche; llegó 'x'"])
        self.assertFalse((self.carpeta / "2026-11-18.json").exists())
        self.assertFalse(pasadas.agregar_local(cfg, "pulso", [])["ok"])

    def test_es_atomico_si_falla_al_escribir_queda_el_dia_de_antes_y_sin_temporales(self):
        cfg = self.config()
        pasadas.agregar_local(cfg, "pulso", [una()])
        antes = (self.carpeta / "2026-11-18.json").read_bytes()
        with mock.patch.object(pasadas.os, "replace", side_effect=OSError(28, "No space left on device")):
            r = pasadas.agregar_local(cfg, "pulso", [una("2026-11-18T14:00")])
        self.assertFalse(r["ok"])
        self.assertEqual((self.carpeta / "2026-11-18.json").read_bytes(), antes)
        self.assertEqual(sorted(f.name for f in self.carpeta.iterdir()), [".pasadas.lock", "2026-11-18.json"])

    def test_un_dia_que_no_es_de_pasadas_no_se_pisa(self):
        cfg = self.config()
        self.carpeta.mkdir()
        (self.carpeta / "2026-11-18.json").write_text('{"plan": "otra cosa"}')
        r = pasadas.agregar_local(cfg, "pulso", [una()])
        self.assertEqual((r["ok"], r["error"]), (False, '2026-11-18.json no es un día de pasadas ({"pasadas": [...]}): no lo toco'))
        self.assertEqual((self.carpeta / "2026-11-18.json").read_text(), '{"plan": "otra cosa"}')

    def test_a_la_vez_no_se_pierde_ninguna(self):
        cfg = self.config()
        errores = []

        def agregar(h):
            for m in range(6):
                r = pasadas.agregar_local(cfg, "pulso", [una(f"2026-11-18T{h:02d}:{m:02d}")])
                if not r["ok"]:
                    errores.append(r["error"])

        hilos = [threading.Thread(target=agregar, args=(h,)) for h in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        self.assertEqual(len({p["id"] for p in self.dia()}), 48)

    def test_sin_pasadas_declaradas_o_sin_carpeta_se_dice(self):
        self.assertIn("no lleva pasadas", pasadas.agregar_local(self.config(esquema=""), "pulso", [una()])["error"])
        self.assertIn("no hay un resultado «otro»", pasadas.agregar_local(self.config(), "otro", [una()])["error"])
        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                resultados=(mod_config.Resultado(clave="pulso", en="servidor", pasadas="pulso"),))
        self.assertIn("no tiene carpeta en esta máquina", pasadas.agregar_local(cfg, "pulso", [una()])["error"])


class Importar(ConCarpeta):
    def jsonl(self, *lineas) -> str:
        return "\n".join(x if isinstance(x, str) else json.dumps(x) for x in lineas) + "\n"

    def test_se_importa_una_vez_aunque_se_corra_dos(self):
        cfg = self.config()
        lista, nombres, rotas = pasadas.leer_jsonl(self.jsonl(una(), "", una("2026-11-18T14:00"), una("2026-11-19T08:00")))
        self.assertEqual((nombres, rotas), (["línea 1", "línea 3", "línea 4"], []))
        r = pasadas.agregar_local(cfg, "pulso", lista, saltar_repetidas=True, nombres=nombres)
        self.assertEqual((r["agregadas"], r["ya_estaban"], r["en_el_dia"]),
                         (["2026-11-18T13:00", "2026-11-18T14:00", "2026-11-19T08:00"], [], {"2026-11-18": 2, "2026-11-19": 1}))
        otra = pasadas.agregar_local(cfg, "pulso", lista, saltar_repetidas=True, nombres=nombres)
        self.assertEqual((otra["ok"], otra["agregadas"], len(otra["ya_estaban"]), otra["distintas"]), (True, [], 3, []))
        self.assertEqual(len(self.dia()), 2)

    def test_una_que_ya_estaba_distinta_se_dice_y_no_se_reescribe(self):
        cfg = self.config()
        pasadas.agregar_local(cfg, "pulso", [una()])
        r = pasadas.agregar_local(cfg, "pulso", [una(resumen="otra"), una("2026-11-18T14:00")], saltar_repetidas=True)
        self.assertEqual((r["agregadas"], r["ya_estaban"], r["distintas"]), (["2026-11-18T14:00"], ["2026-11-18T13:00"], ["2026-11-18T13:00"]))
        self.assertEqual(self.dia()[0]["resumen"], una()["resumen"])

    def test_una_linea_mala_o_un_id_repetido_en_el_archivo_y_no_entra_ninguna(self):
        cfg = self.config()
        lista, nombres, rotas = pasadas.leer_jsonl(self.jsonl(una(), "{roto"))
        self.assertEqual(len(rotas), 1)
        self.assertTrue(rotas[0].startswith("línea 2: no es JSON"))
        lista, nombres, _ = pasadas.leer_jsonl(self.jsonl(una(), una("2026-11-18T14:00", modo="x"), una()))
        r = pasadas.agregar_local(cfg, "pulso", lista, saltar_repetidas=True, nombres=nombres)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errores"], ["línea 2 (2026-11-18T14:00): modo: dia | noche; llegó 'x'",
                                        "línea 3 (2026-11-18T13:00): el id 2026-11-18T13:00 se repite (también en la línea 1)"])
        self.assertFalse(self.carpeta.exists() and any(self.carpeta.glob("*.json")))


class LoVisto(ConCarpeta):
    def setUp(self):
        super().setUp()
        self.cfg = self.config()
        pasadas.agregar_local(self.cfg, "pulso", [una("2026-11-17T22:00"), una("2026-11-17T23:30", modo="noche"),
                                                  una("2026-11-18T07:00"), una("2026-11-18T08:00", seco=True)])

    def test_sin_nada_visto_son_las_del_ultimo_dia_la_mas_nueva_arriba(self):
        r = pasadas.sin_ver_local(self.cfg, "pulso")
        self.assertEqual((r["ok"], r["visto"], r["total"], r["esquema"]), (True, {}, 2, "pulso"))
        self.assertEqual([p["id"] for p in r["pasadas"]], ["2026-11-18T08:00", "2026-11-18T07:00"])
        self.assertTrue(r["pasadas"][0]["seco"])

    def test_vista_una_quedan_las_de_despues_aunque_sean_de_otro_dia(self):
        v = pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-17T22:00")
        self.assertEqual((v["ok"], v["movio"], v["visto"]["id"], v["visto"]["dia"]), (True, True, "2026-11-17T22:00", "2026-11-17"))
        r = pasadas.sin_ver_local(self.cfg, "pulso")
        self.assertEqual([p["id"] for p in r["pasadas"]], ["2026-11-18T08:00", "2026-11-18T07:00", "2026-11-17T23:30"])
        self.assertEqual(r["visto"]["id"], "2026-11-17T22:00")
        self.assertEqual(pasadas.sin_ver_local(self.cfg, "pulso", tope=1)["total"], 3)
        self.assertEqual(len(pasadas.sin_ver_local(self.cfg, "pulso", tope=1)["pasadas"]), 1)

    def test_solo_avanza_y_tiene_que_existir(self):
        pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T07:00")
        atras = pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-17T23:30")
        self.assertEqual((atras["ok"], atras["movio"], atras["visto"]["id"]), (True, False, "2026-11-18T07:00"))
        self.assertEqual(pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T09:00")["error"], "no hay una pasada 2026-11-18T09:00 en el 2026-11-18")
        self.assertIn("no es el id de una pasada", pasadas.marcar_visto_local(self.cfg, "pulso", "ayer")["error"])
        self.assertEqual(pasadas.visto_local(self.cfg, "pulso")["id"], "2026-11-18T07:00")

    def test_sin_id_hasta_la_mas_nueva_y_despues_nada_sin_ver(self):
        v = pasadas.marcar_visto_local(self.cfg, "pulso")
        self.assertEqual(v["visto"]["id"], "2026-11-18T08:00")
        r = pasadas.sin_ver_local(self.cfg, "pulso")
        self.assertEqual((r["total"], r["pasadas"]), (0, []))
        # llega otra: esa sola
        pasadas.agregar_local(self.cfg, "pulso", [una("2026-11-18T09:00")])
        self.assertEqual([p["id"] for p in pasadas.sin_ver_local(self.cfg, "pulso")["pasadas"]], ["2026-11-18T09:00"])

    def test_lo_visto_vive_en_la_carpeta_solo_para_la_persona(self):
        pasadas.marcar_visto_local(self.cfg, "pulso", "ultimo")
        f = self.carpeta / pasadas.VISTO
        self.assertEqual(json.loads(f.read_text())["id"], "2026-11-18T08:00")
        self.assertEqual(os.stat(f).st_mode & 0o777, 0o600)


class PorElBus(ConCarpeta):
    def config_alla(self):
        return mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                 bus=mod_config.Bus(url="nats://x:1", maquina="laptop"),
                                 resultados=(mod_config.Resultado(clave="pulso", carpeta=str(self.carpeta), en="servidor", pasadas="pulso"),))

    def test_desde_otra_maquina_todo_se_pide_alla(self):
        cfg = self.config_alla()
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "agregadas": ["2026-11-18T13:00"]}) as pedir:
            r = pasadas.agregar(cfg, "pulso", [una()])
            self.assertEqual((r["desde"], r["agregadas"]), ("servidor", ["2026-11-18T13:00"]))
            self.assertEqual(pedir.call_args[0][1:4], ("servidor", "resultado-agregar",
                                                        {"clave": "pulso", "pasadas": [una()], "saltar_repetidas": False, "nombres": None}))
            pasadas.marcar_visto(cfg, "pulso", "2026-11-18T13:00")
            self.assertEqual(pedir.call_args[0][1:4], ("servidor", "resultado-visto", {"clave": "pulso", "id": "2026-11-18T13:00"}))
            pasadas.marcar_visto(cfg, "pulso", "2026-11-18T13:00", "trabajo")
            self.assertEqual(pedir.call_args[0][3], {"clave": "pulso", "id": "2026-11-18T13:00", "mundo": "trabajo"})
            pasadas.sin_ver(cfg, "pulso")
            self.assertEqual(pedir.call_args[0][1:4], ("servidor", "resultado-sin-ver", {"clave": "pulso"}))
        self.assertFalse(self.carpeta.exists(), "aquí no se escribió nada")

    def test_si_alla_no_responde_se_dice_y_aqui_no_se_escribe(self):
        cfg = self.config_alla()
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "servidor no respondió en 15 s"}):
            for r in (pasadas.agregar(cfg, "pulso", [una()]), pasadas.marcar_visto(cfg, "pulso"), pasadas.sin_ver(cfg, "pulso")):
                self.assertEqual((r["ok"], r["desde"], r["error"]), (False, "servidor", "servidor no respondió en 15 s"))
        self.assertFalse(self.carpeta.exists())

    def test_en_la_maquina_donde_vive_es_aqui(self):
        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                bus=mod_config.Bus(url="nats://x:1", maquina="servidor"),
                                resultados=(mod_config.Resultado(clave="pulso", carpeta=str(self.carpeta), en="servidor", pasadas="pulso"),))
        with mock.patch.object(mod_bus, "pedir") as pedir:
            self.assertEqual(pasadas.agregar(cfg, "pulso", [una()])["desde"], "aquí")
        pedir.assert_not_called()
        self.assertEqual(len(self.dia()), 1)

    def test_el_nodo_atiende_los_tres_pedidos_con_lo_de_aqui(self):
        import asyncio

        from telar.ordenes import nodo as mod_nodo

        cfg = self.config()
        n = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        n.config = cfg
        n.ctx = SimpleNamespace(config=cfg)
        respuestas = []

        class M:
            def __init__(self, datos):
                self.data = json.dumps(datos).encode()

            async def respond(self, cuerpo):
                respuestas.append(mod_bus.desempacar(cuerpo))

        asyncio.run(n._resultado_agregar(M({"clave": "pulso", "pasadas": [una()], "saltar_repetidas": True})))
        asyncio.run(n._resultado_visto(M({"clave": "pulso", "id": ""})))
        asyncio.run(n._resultado_sin_ver(M({"clave": "pulso"})))
        self.assertEqual([r["ok"] for r in respuestas], [True, True, True])
        self.assertEqual((respuestas[0]["agregadas"], respuestas[1]["visto"]["id"], respuestas[2]["total"]),
                         (["2026-11-18T13:00"], "2026-11-18T13:00", 0))


class ConMundos(ConCarpeta):
    """Una casa con dos mundos y sus tareas en una carpeta: T1 de un cliente (trabajo), T2 de la casa (personal), T3 de
    un área que no es de ninguno (sin clasificar)."""

    def setUp(self):
        super().setUp()
        self.tareas = Path(self.tmp.name) / "tareas"
        self.tareas.mkdir()
        for id_, campos in (("T1", "area: cliente"), ("T2", "area: personal\nproyecto: casa/jardin"), ("T3", "area: otra"),
                            ("T4", "estado: hecha\ncerrada: 2026-11-17\narea: cliente")):
            (self.tareas / f"{id_}.md").write_text(f"---\ntitulo: {id_}\n{campos}\n---\n", encoding="utf-8")
        self.cfg = self.config()

    def config(self, esquema="pulso", **extra):
        return mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                 resultados=(mod_config.Resultado(clave="pulso", carpeta=str(self.carpeta), pasadas=esquema, **extra),),
                                 mundos=(mod_config.Mundo(nombre="trabajo", areas=("cliente",), rutas=("empresa/",)),
                                         mod_config.Mundo(nombre="personal", areas=("personal",), rutas=("casa/",))),
                                 tipos=(mod_config.Tipo(clave="tarea", carpeta=str(self.tareas)),))


def mezclada(id_="2026-11-18T13:00", **cambios) -> dict:
    """Una pasada como las de antes (ningún mundo dicho), con lo de los dos mundos: T1 es de trabajo, T2 personal."""
    p = una(id_, resumen="Carla confirmó el jueves; Luis pidió la bici")
    p["tareas"] = {"nuevas": [{"id": "tarea:T1", "linea": "Arcilla: retrospectiva", "por": "correo de Carla"},
                              {"id": "HABRIA tarea nueva", "linea": "algo", "por": "WhatsApp de Ana"}],
                   "avanzadas": [{"id": "tarea:T2", "linea": "el jardín", "por": "correo del vivero"}],
                   "cerradas": [{"id": "tarea:T4", "como": "hecha", "linea": "salió", "por": "respuesta de Ana"}]}
    p["te_esperan"] = [{"id": "tarea:T2", "pide": "decidir", "linea": "¿poda?", "peso": 2, "vence": ""}]
    p["borradores"] = [{"para": "Ana", "asunto": "x", "enlace": "", "tarea": "tarea:T1", "por": "correo de Ana"}]
    p["vencidas_sin_propuesta"] = ["tarea:T2", "tarea:T3"]
    p.update(cambios)
    return p


class ElMundoDeCadaCosa(ConMundos):
    def test_el_mundo_es_opcional_un_texto_y_resumenes_un_objeto_de_textos(self):
        p = una()
        p["fuentes"][0]["mundo"] = "trabajo"
        p["tareas"]["nuevas"][0]["mundo"] = ""
        p["te_esperan"][0]["mundo"] = "personal"
        p["borradores"][0]["mundo"] = "trabajo"
        self.assertEqual(pasadas.validar("pulso", {**p, "resumenes": {"trabajo": "dos de Arcilla", "personal": "el jardín"}}), [])
        p["tareas"]["cerradas"][0]["mundo"] = 3
        errores = pasadas.validar("pulso", {**p, "resumenes": {"trabajo": "", "personal": ["x"]}})
        self.assertEqual(errores, ["tareas.cerradas[0].mundo: se esperaba un texto, llegó un número",
                                   "resumenes.trabajo: está vacío", "resumenes.personal: se esperaba un texto, llegó una lista"])
        self.assertEqual(pasadas.validar("pulso", una(resumenes="trabajo")), ["resumenes: se esperaba un objeto, llegó un texto"])

    def test_un_mundo_que_no_existe_se_avisa_y_la_pasada_entra(self):
        p = una(resumenes={"casa": "algo"})
        p["te_esperan"][0]["mundo"] = "ocio"
        p["fuentes"][1]["mundo"] = "personal"
        r = pasadas.agregar_local(self.cfg, "pulso", [p])
        self.assertTrue(r["ok"])
        self.assertEqual(r["avisos"], ["te_esperan[0].mundo: «ocio» no es un mundo de aquí (trabajo, personal); queda sin clasificar",
                                       "resumenes.casa: «casa» no es un mundo de aquí (trabajo, personal); queda sin clasificar"])
        self.assertEqual(self.dia()[0], p, "se guarda tal cual")
        # sin mundos declarados no se avisa nada: ahí todo es sin clasificar
        self.assertEqual(pasadas.avisos("pulso", p, ()), [])
        self.assertNotIn("avisos", pasadas.agregar_local(self.cfg, "pulso", [una("2026-11-18T14:00")]))

    def test_una_tarea_con_direccion_es_del_mundo_de_la_tarea_y_ese_manda(self):
        p = mezclada()
        p["tareas"]["nuevas"][0]["mundo"] = "personal"  # el agente se equivocó: T1 es de trabajo
        p["tareas"]["nuevas"][1]["mundo"] = "personal"  # sin dirección: vale lo que dijo
        p["fuentes"][0]["mundo"] = "trabajo"
        p["fuentes"][1]["mundo"] = "ocio"               # uno que no existe: sin clasificar
        p["vencidas_sin_propuesta"].append("tarea:T99")
        de = pasadas.mundos_de_tareas(SimpleNamespace(config=self.cfg), pasadas.tareas_de(p))
        self.assertEqual(de, {"T1": "trabajo", "T2": "personal", "T3": "", "T4": "trabajo"}, "las cerradas también; T99 no está")
        v = pasadas.clasificar(p, ("trabajo", "personal"), de)
        t = v["tareas"]
        self.assertEqual([x["mundo"] for x in t["nuevas"] + t["avanzadas"] + t["cerradas"]], ["trabajo", "personal", "personal", "trabajo"])
        self.assertEqual([x["mundo"] for x in v["fuentes"]], ["trabajo", ""])
        self.assertEqual((v["te_esperan"][0]["mundo"], v["borradores"][0]["mundo"]), ("personal", "trabajo"), "el borrador, por su tarea")
        self.assertEqual(v["mundos_vencidas"], {"tarea:T2": "personal", "tarea:T3": "", "tarea:T99": ""})
        self.assertEqual(v["mundos"], ["trabajo", "personal", ""])
        self.assertEqual((p["fuentes"][1]["mundo"], p["tareas"]["nuevas"][0]["mundo"]), ("ocio", "personal"), "la de disco no cambia")
        self.assertNotIn("mundos", p)

    def test_una_tarea_que_no_se_clasifica_lleva_el_del_agente(self):
        p = una()
        p["tareas"]["nuevas"] = [{"id": "tarea:T3", "linea": "de un área de nadie", "mundo": "trabajo"},
                                 {"id": "tarea:T99", "linea": "no existe", "mundo": "personal"},
                                 {"id": "tarea:T3", "linea": "y sin decir"}]
        v = pasadas.clasificar(p, ("trabajo", "personal"), {"T3": ""})
        self.assertEqual([x["mundo"] for x in v["tareas"]["nuevas"]], ["trabajo", "personal", ""])

    def test_sin_cosas_la_pasada_misma_es_sin_clasificar(self):
        vacia = {"id": "2026-11-18T13:00", "resumen": "nada", "fuentes": [], "tareas": {}, "te_esperan": [], "borradores": []}
        self.assertEqual(pasadas.clasificar(vacia, ("trabajo",), {})["mundos"], [""])
        self.assertEqual(pasadas.clasificar(pasadas.clasificar(vacia, (), {}), (), {})["mundos"], [""])


class LoVistoPorMundo(ConMundos):
    """13:00 trae de los dos (y fuentes sin clasificar), 14:00 solo personal, 15:00 solo trabajo."""

    def setUp(self):
        super().setUp()
        solo = lambda id_, tarea, mundo: una(id_, fuentes=[{"fuente": "correo", "llegaron": 1, "archivados": 0, "mundo": mundo}],
                                             tareas={"nuevas": [{"id": tarea, "linea": "x", "por": "un correo"}], "avanzadas": [], "cerradas": []},
                                             te_esperan=[], borradores=[])
        pasadas.agregar_local(self.cfg, "pulso", [mezclada(), solo("2026-11-18T14:00", "tarea:T2", "personal"),
                                                  solo("2026-11-18T15:00", "tarea:T1", "trabajo")])

    def sin_ver(self):
        r = pasadas.sin_ver_local(self.cfg, "pulso")
        self.assertTrue(r["ok"], r)
        return r, {p["id"][11:]: p["sin_ver_en"] for p in r["pasadas"]}

    def test_cada_una_dice_en_que_mundos_tiene_algo_sin_ver(self):
        r, en = self.sin_ver()
        self.assertEqual(en, {"15:00": ["trabajo"], "14:00": ["personal"], "13:00": ["trabajo", "personal", ""]})
        self.assertEqual((r["total"], r["con_cambios"], r["por_mundo"], r["visto"], r["vistos"]), (3, 3, {"trabajo": 2, "personal": 2}, {}, {}))
        self.assertEqual(r["pasadas"][2]["tareas"]["nuevas"][0]["mundo"], "trabajo", "cada cosa con su mundo resuelto")

    def test_vistas_con_trabajo_lo_personal_sigue_sin_ver(self):
        v = pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T15:00", "trabajo")
        self.assertEqual((v["ok"], v["movio"], v["mundo"], v["visto"]), (True, True, "trabajo", {}))
        self.assertEqual({k: x["id"] for k, x in v["vistos"].items()}, {"trabajo": "2026-11-18T15:00", "": "2026-11-18T15:00"},
                         "lo sin clasificar queda visto en cuanto se ve")
        r, en = self.sin_ver()
        self.assertEqual(en, {"14:00": ["personal"], "13:00": ["personal"]})
        self.assertEqual((r["total"], r["por_mundo"]), (2, {"trabajo": 0, "personal": 2}))
        # solo avanza, por mundo
        self.assertFalse(pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T13:00", "trabajo")["movio"])
        # con personal, lo suyo; y no queda nada
        self.assertTrue(pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T14:00", "personal")["movio"])
        self.assertEqual(self.sin_ver()[0]["total"], 0)

    def test_con_ambos_se_marca_todo_y_lo_de_cada_mundo_que_quedo_atras_se_olvida(self):
        pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T13:00", "personal")
        r, en = self.sin_ver()
        self.assertEqual(en, {"15:00": ["trabajo"], "14:00": ["personal"], "13:00": ["trabajo"]})
        v = pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T14:00")
        self.assertEqual((v["movio"], v["visto"]["id"], v["vistos"]), (True, "2026-11-18T14:00", {}))
        self.assertEqual(self.sin_ver()[1], {"15:00": ["trabajo"]})
        self.assertNotIn("mundos", json.loads((self.carpeta / pasadas.VISTO).read_text()))
        # la que llega después sin cambios es sin clasificar: se ve con cualquiera, y no cuenta
        pasadas.agregar_local(self.cfg, "pulso", [una("2026-11-18T16:00", tareas={"nuevas": [], "avanzadas": [], "cerradas": []},
                                                      te_esperan=[], borradores=[])])
        self.assertEqual(self.sin_ver()[1], {"16:00": [""], "15:00": ["trabajo"]})
        self.assertEqual((self.sin_ver()[0]["total"], self.sin_ver()[0]["con_cambios"], self.sin_ver()[0]["por_mundo"]),
                         (2, 1, {"trabajo": 1, "personal": 0}))
        # y lo sin clasificar con cambios sí cuenta, en los dos
        pasadas.agregar_local(self.cfg, "pulso", [una("2026-11-18T17:00", te_esperan=[], borradores=[])])
        self.assertEqual(self.sin_ver()[0]["por_mundo"], {"trabajo": 2, "personal": 1})

    def test_un_mundo_que_no_existe_no_se_marca(self):
        self.assertEqual(pasadas.marcar_visto_local(self.cfg, "pulso", "", "ocio")["error"], "no hay un mundo «ocio» (trabajo, personal)")
        sin = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado", resultados=self.cfg.resultados)
        self.assertIn("no declara mundos", pasadas.marcar_visto_local(sin, "pulso", "", "trabajo")["error"])
        self.assertFalse((self.carpeta / pasadas.VISTO).exists())

    def test_lo_visto_de_antes_sin_mundos_vale_para_todos(self):
        (self.carpeta / pasadas.VISTO).write_text(json.dumps({"id": "2026-11-18T14:00", "dia": "2026-11-18", "cuando": "x"}))
        self.assertEqual(self.sin_ver()[1], {"15:00": ["trabajo"]})
        pasadas.marcar_visto_local(self.cfg, "pulso", "", "trabajo")
        self.assertEqual(json.loads((self.carpeta / pasadas.VISTO).read_text())["id"], "2026-11-18T14:00", "lo de ambos queda")
        self.assertEqual(self.sin_ver()[0]["total"], 0)

    def test_sin_nada_visto_en_un_mundo_son_las_del_ultimo_dia(self):
        pasadas.agregar_local(self.cfg, "pulso", [mezclada("2026-11-17T22:00")])
        pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-17T22:00", "trabajo")
        r, en = self.sin_ver()
        self.assertNotIn("22:00", en, "personal, que nunca se marcó, mira solo el último día")
        pasadas.marcar_visto_local(self.cfg, "pulso", "2026-11-18T13:00", "personal")
        pasadas.agregar_local(self.cfg, "pulso", [mezclada("2026-11-19T08:00")])
        self.assertEqual(self.sin_ver()[1], {"08:00": ["trabajo", "personal", ""], "15:00": ["trabajo"], "14:00": ["personal"],
                                             "13:00": ["trabajo"]})


class LasDeAntes(ConMundos):
    """Las pasadas de antes no dicen mundo: las tareas con dirección van por su tarea; lo demás, sin clasificar. Y su
    resumen puede nombrar lo de cualquier mundo."""

    def vista(self, p):
        return pasadas.clasificar(p, ("trabajo", "personal"), pasadas.mundos_de_tareas(SimpleNamespace(config=self.cfg), pasadas.tareas_de(p)))

    def test_se_clasifican_por_su_tarea_y_lo_demas_queda_sin_clasificar(self):
        v = self.vista(mezclada())
        self.assertEqual([x["mundo"] for x in v["tareas"]["nuevas"]], ["trabajo", ""], "«HABRIA tarea nueva» no es una tarea")
        self.assertEqual({x["mundo"] for x in v["fuentes"]}, {""})

    def test_con_un_mundo_puesto_el_resumen_solo_si_no_trae_nada_de_otro(self):
        v = self.vista(mezclada())
        self.assertEqual(pasadas.para_mundo(v, "trabajo")["resumen"], "", "nombra lo personal: solo las cuentas")
        self.assertEqual(pasadas.para_mundo(v, "")["resumen"], "Carla confirmó el jueves; Luis pidió la bici", "con ambos, entero")
        solo_trabajo = mezclada(te_esperan=[], vencidas_sin_propuesta=["tarea:T3"])
        solo_trabajo["tareas"]["avanzadas"] = []
        w = self.vista(solo_trabajo)
        self.assertEqual(w["mundos"], ["trabajo", ""])
        self.assertEqual(pasadas.para_mundo(w, "trabajo")["resumen"], solo_trabajo["resumen"])
        self.assertEqual(pasadas.para_mundo(w, "personal")["resumen"], "")

    def test_una_guardada_sin_por_ni_mundos_se_lee(self):
        # las de antes de la causa: no se revalidan
        vieja = mezclada()
        for g in ("nuevas", "avanzadas", "cerradas"):
            for t in vieja["tareas"][g]:
                del t["por"]
        del vieja["borradores"][0]["por"]
        self.carpeta.mkdir()
        (self.carpeta / "2026-11-18.json").write_text(json.dumps({"pasadas": [vieja]}))
        r = pasadas.sin_ver_local(self.cfg, "pulso")
        self.assertEqual((r["ok"], r["total"], r["pasadas"][0]["sin_ver_en"]), (True, 1, ["trabajo", "personal", ""]))

    def test_lo_que_se_ve_con_un_mundo(self):
        v = pasadas.para_mundo(self.vista(mezclada()), "trabajo")
        self.assertEqual([x["id"] for x in v["tareas"]["nuevas"] + v["tareas"]["avanzadas"] + v["tareas"]["cerradas"]],
                         ["tarea:T1", "HABRIA tarea nueva", "tarea:T4"])
        self.assertEqual((v["te_esperan"], len(v["borradores"]), len(v["fuentes"])), ([], 1, 2))
        self.assertEqual(v["vencidas_sin_propuesta"], ["tarea:T3"], "la de T2 es personal")

    def test_lo_que_ya_se_vio_con_otro_mundo_no_vuelve(self):
        v = {**self.vista(mezclada(resumenes={"trabajo": "Carla", "personal": "las plantas"})), "sin_ver_en": ["personal"]}
        p = pasadas.para_mundo(v, "personal")
        self.assertEqual([x["id"] for x in p["tareas"]["nuevas"] + p["tareas"]["avanzadas"]], ["tarea:T2"],
                         "lo sin clasificar (HABRIA) ya se vio con trabajo")
        a = pasadas.para_mundo(v, "")
        self.assertEqual(([x["id"] for x in a["tareas"]["nuevas"] + a["tareas"]["avanzadas"] + a["tareas"]["cerradas"]], a["borradores"]),
                         (["tarea:T2"], []))
        self.assertEqual((a["resumen"], a["resumenes"]), ("", {"personal": "las plantas"}), "el neutro contaba también lo ya visto")

    def test_con_resumenes_van_los_de_los_mundos_que_se_ven(self):
        v = self.vista(mezclada(resumen="2 nuevas, 1 te espera", resumenes={"trabajo": "Carla confirmó", "personal": "Luis y la bici"}))
        t = pasadas.para_mundo(v, "trabajo")
        # el neutro cuenta la pasada entera: con un mundo, las cuentas son las de lo que se ve (la línea de la página)
        self.assertEqual((t["resumen"], t["resumenes"]), ("", {"trabajo": "Carla confirmó"}))
        a = pasadas.para_mundo(v, "")
        self.assertEqual((a["resumen"], a["resumenes"]), ("2 nuevas, 1 te espera", {"trabajo": "Carla confirmó", "personal": "Luis y la bici"}))


class LaOrden(ConCarpeta):
    def correr(self, *argv, entrada="") -> tuple[int, str, str]:
        from telar.ordenes import resultado as orden

        salida, errores = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(entrada)), redirect_stdout(salida), redirect_stderr(errores):
            codigo = orden.main(list(argv), SimpleNamespace(config=self.config()))
        return codigo, salida.getvalue(), errores.getvalue()

    def test_agregar_por_la_entrada_y_un_repetido_sale_con_error(self):
        codigo, salida, _ = self.correr("pulso", "--agregar", entrada=json.dumps(una()))
        self.assertEqual((codigo, salida), (0, "agregada 2026-11-18T13:00 · 1 el 2026-11-18\n"))
        codigo, salida, _ = self.correr("pulso", "--agregar", "--json", entrada=json.dumps(una()))
        self.assertEqual((codigo, json.loads(salida)["repetida"]), (1, "2026-11-18T13:00"))
        codigo, _, errores = self.correr("pulso", "--agregar", entrada="no es json")
        self.assertEqual(codigo, 2)
        self.assertIn("la entrada no es JSON", errores)

    def test_importar_ver_y_marcar(self):
        archivo = Path(self.tmp.name) / "2026-11-18.jsonl"
        archivo.write_text("\n".join(json.dumps(p) for p in (una(), una("2026-11-18T14:00", seco=True))) + "\n")
        self.assertEqual(self.correr("pulso", "--agregar", "--desde", str(archivo))[1], "2 agregadas\n")
        self.assertEqual(self.correr("pulso", "--agregar", "--desde", str(archivo))[1], "0 agregadas · 2 ya estaban\n")
        codigo, salida, _ = self.correr("pulso", "--sin-ver")
        self.assertEqual(codigo, 0)
        lineas = salida.splitlines()
        self.assertEqual(lineas[0], "pulso · nada visto todavía · 2 sin ver, 2 con cambios")
        self.assertEqual(lineas[1], "2026-11-18T14:00  1 nueva · 1 avanzada · 1 cerrada · 1 borrador · falló whatsapp  seco")
        self.assertEqual(self.correr("pulso", "--visto", "2026-11-18T13:00")[1], "visto hasta 2026-11-18T13:00\n")
        self.assertEqual(json.loads(self.correr("pulso", "--sin-ver", "--json")[1])["total"], 1)
        self.assertEqual(self.correr("pulso", "--visto")[1], "visto hasta 2026-11-18T14:00\n")
        self.assertEqual(self.correr("pulso", "--visto", "2026-11-18T13:00")[1], "ya estaba visto hasta 2026-11-18T14:00\n")

    def test_lo_que_no_se_combina_se_dice(self):
        self.assertEqual(self.correr("pulso", "--desde", "x.jsonl")[0], 2)
        self.assertEqual(self.correr("pulso", "--sin-ver", "--visto")[0], 2)
        self.assertEqual(self.correr("pulso", "2026-11-18", "--agregar")[0], 2)
        self.assertEqual(self.correr("--agregar")[0], 2)


class LaOrdenConMundos(ConMundos):
    def correr(self, *argv, entrada="") -> tuple[int, str, str]:
        from telar.ordenes import resultado as orden

        salida, errores = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(entrada)), redirect_stdout(salida), redirect_stderr(errores):
            codigo = orden.main(list(argv), SimpleNamespace(config=self.cfg))
        return codigo, salida.getvalue(), errores.getvalue()

    def test_agregar_avisa_el_mundo_que_no_existe(self):
        p = una()
        p["fuentes"][0]["mundo"] = "ocio"
        codigo, salida, errores = self.correr("pulso", "--agregar", entrada=json.dumps(p))
        self.assertEqual((codigo, salida), (0, "agregada 2026-11-18T13:00 · 1 el 2026-11-18\n"))
        self.assertIn("fuentes[0].mundo: «ocio» no es un mundo de aquí", errores)

    def test_ver_y_marcar_con_un_mundo(self):
        self.correr("pulso", "--agregar", entrada=json.dumps(mezclada()))
        self.correr("pulso", "--agregar", entrada=json.dumps(una("2026-11-18T14:00", tareas={"nuevas": [{"id": "tarea:T2", "linea": "x", "por": "y"}],
                                                                                           "avanzadas": [], "cerradas": []},
                                                                 te_esperan=[], borradores=[], fuentes=[], resumen="lo de la casa")))
        lineas = self.correr("pulso", "--sin-ver")[1].splitlines()
        self.assertEqual(lineas[0], "pulso · nada visto todavía · 2 sin ver, 2 con cambios (trabajo 1, personal 2)")
        self.assertEqual(lineas[1], "2026-11-18T14:00  1 nueva  sin ver en personal")
        self.assertIn("sin ver en trabajo, personal, sin clasificar", lineas[3])
        # con trabajo: solo lo que se ve, y el resumen de la de antes que nombra lo personal, no
        lineas = self.correr("pulso", "--sin-ver", "--mundo", "trabajo")[1].splitlines()
        self.assertEqual(lineas, ["pulso · trabajo · nada visto todavía · 1 sin ver, 1 con cambios",
                                  "2026-11-18T13:00  2 nuevas · 1 cerrada · 1 borrador · falló whatsapp"])
        self.assertEqual(self.correr("pulso", "--visto", "--mundo", "trabajo")[1], "visto hasta 2026-11-18T14:00 en trabajo\n")
        self.assertEqual(json.loads(self.correr("pulso", "--sin-ver", "--mundo", "trabajo", "--json")[1])["total"], 0)
        self.assertEqual(json.loads(self.correr("pulso", "--sin-ver", "--mundo", "personal", "--json")[1])["total"], 2)
        codigo, _, errores = self.correr("pulso", "--sin-ver", "--mundo", "ocio")
        self.assertEqual(codigo, 2)
        self.assertIn("no hay un mundo «ocio» (trabajo, personal)", errores)
        self.assertEqual(self.correr("pulso", "--agregar", "--mundo", "trabajo")[0], 2)


class LaConfiguracion(Prueba):
    def test_pasadas_va_en_la_vista_y_en_la_tabla_de_antes(self):
        cfg = mod_config.desde_dict({"vistas": {"pulso": {"carpeta": "~/s/pulso", "en": "telar", "pasadas": "pulso"}}})
        self.assertEqual((cfg.resultados[0].clave, cfg.resultados[0].pasadas, cfg.resultados[0].en), ("pulso", "pulso", "telar"))
        self.assertEqual(mod_config.desde_dict({"resultados": {"x": {"en": "telar", "pasadas": "libre"}}}).resultados[0].pasadas, "libre")
        # sin `aparece`: pasadas solo puede ser un resultado por día
        self.assertEqual(mod_config.desde_dict({"vistas": {"y": {"en": "telar", "pasadas": "libre"}}}).resultados[0].pasadas, "libre")
        with self.assertRaisesRegex(mod_config.ErrorDeConfig, r"vistas\.pulso\.pasadas: pulso o libre; llegó 'otro'"):
            mod_config.desde_dict({"vistas": {"pulso": {"carpeta": "/a", "pasadas": "otro"}}})
        # doctor lo devuelve en la forma nueva, y leída da lo mismo
        vista = mod_config.como_vista("resultados", cfg.resultados[0])
        self.assertEqual(vista["pasadas"], "pulso")

    @unittest.skipUnless(HAY_FASTAPI, "sin fastapi")
    def test_la_pagina_sabe_que_resultados_llevan_pasadas(self):
        from telar.servicios import config as sc

        cfg = mod_config.desde_dict({"vistas": {"pulso": {"en": "telar", "pasadas": "pulso"}, "plan": {"carpeta": "/p"}}})
        r = sc.resuelta(SimpleNamespace(config=cfg))
        self.assertEqual(r.resultados, [{"clave": "pulso", "nombre": "pulso", "en": "telar", "pasadas": "pulso"},
                                        {"clave": "plan", "nombre": "plan", "en": "", "pasadas": ""}])


@unittest.skipUnless(HAY_FASTAPI, "sin fastapi")
class LaApi(ConCarpeta):
    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient

        from telar import api

        p = mock.patch.object(api, "_refrescar", mock.AsyncMock())
        p.start()
        self.addCleanup(p.stop)
        cfg = self.config()
        pasadas.agregar_local(cfg, "pulso", [una(), una("2026-11-18T14:00")])
        ctx = SimpleNamespace(config=cfg)
        api.app.dependency_overrides[api.contexto] = lambda: ctx
        self.addCleanup(api.app.dependency_overrides.clear)
        self.c = TestClient(api.app)

    def test_get_dice_lo_sin_ver_y_post_lo_marca(self):
        r = self.c.get("/resultados/pulso/visto").json()
        self.assertEqual((r["ok"], r["total"], [p["id"] for p in r["pasadas"]]), (True, 2, ["2026-11-18T14:00", "2026-11-18T13:00"]))
        self.assertEqual(r["pasadas"][0]["tareas"]["nuevas"][0]["id"], "tarea:T580", "la pasada entera")
        v = self.c.post("/resultados/pulso/visto", json={"id": "2026-11-18T13:00"}).json()
        self.assertEqual((v["ok"], v["movio"], v["visto"]["id"]), (True, True, "2026-11-18T13:00"))
        self.assertEqual(self.c.get("/resultados/pulso/visto").json()["total"], 1)
        # sin id: hasta la más nueva
        self.assertEqual(self.c.post("/resultados/pulso/visto", json={}).json()["visto"]["id"], "2026-11-18T14:00")
        self.assertEqual(self.c.get("/resultados/pulso/visto").json()["total"], 0)
        malo = self.c.post("/resultados/pulso/visto", json={"id": "2026-11-18T09:00"}).json()
        self.assertEqual((malo["ok"], malo["error"]), (False, "no hay una pasada 2026-11-18T09:00 en el 2026-11-18"))

    def test_la_orden_y_la_api_dicen_lo_mismo(self):
        from telar.ordenes import resultado as orden

        salida = io.StringIO()
        with redirect_stdout(salida):
            orden.main(["pulso", "--sin-ver", "--json"], SimpleNamespace(config=self.config()))
        self.assertEqual(json.loads(salida.getvalue()), self.c.get("/resultados/pulso/visto").json())

    def test_con_un_mundo(self):
        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado", resultados=self.config().resultados,
                                mundos=(mod_config.Mundo(nombre="trabajo"), mod_config.Mundo(nombre="personal")))
        from telar import api

        api.app.dependency_overrides[api.contexto] = lambda: SimpleNamespace(config=cfg)
        r = self.c.get("/resultados/pulso/visto").json()
        self.assertEqual((r["por_mundo"], r["pasadas"][0]["sin_ver_en"], r["pasadas"][0]["fuentes"][0]["mundo"]),
                         ({"trabajo": 2, "personal": 2}, [""], ""))
        v = self.c.post("/resultados/pulso/visto", json={"id": "2026-11-18T13:00", "mundo": "trabajo"}).json()
        self.assertEqual((v["ok"], v["mundo"], v["visto"], v["vistos"]["trabajo"]["id"]), (True, "trabajo", {}, "2026-11-18T13:00"))
        self.assertEqual(self.c.get("/resultados/pulso/visto").json()["total"], 1, "lo sin clasificar quedó visto")
        self.assertIn("no hay un mundo", self.c.post("/resultados/pulso/visto", json={"mundo": "ocio"}).json()["error"])

    def test_un_resultado_sin_pasadas_se_dice(self):
        r = self.c.get("/resultados/otro/visto").json()
        self.assertEqual((r["ok"], r["error"][:24]), (False, "no hay un resultado «otr"))


if __name__ == "__main__":
    unittest.main()
