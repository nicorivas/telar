"""Que un agente sepa, al empezar, quién es y cómo hablar con los otros: el contexto de
inicio, su gancho y la skill /hilos."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from test_agente import ConEstado  # noqa: E402  (y con eso, src/ en el camino)

from telar.agente import skill as mod_skill
from telar.agente.claude_code import carpeta_config
from telar.ordenes import agente as orden_agente


class Contexto(ConEstado):
    def contexto(self, hilo="Faro", cartero=False, **agente):
        cfg = replace(self.config, agente=replace(self.config.agente, **agente))
        entorno = {k: v for k, v in os.environ.items() if k != "TELAR_HILO"}
        if hilo:
            entorno["TELAR_HILO"] = hilo
        with mock.patch.dict(os.environ, entorno, clear=True), \
                mock.patch.object(orden_agente, "_cartero_aqui", return_value=cartero):
            return orden_agente.contexto(SimpleNamespace(config=cfg))

    def test_lo_que_dice_un_modulo_entra_al_final(self):
        from telar.modulos import Modulo

        m = Modulo(nombre="grafo", carpeta=self.config.raiz, contexto="Explora con `telar grafo vecinos`.")
        self.config = replace(self.config, modulos=(m,))
        self.assertTrue(self.contexto().endswith("Explora con `telar grafo vecinos`."))

    def test_sin_hilo_no_dice_nada(self):
        self.assertEqual(self.contexto(hilo=""), "")

    def test_apagado_no_dice_nada(self):
        self.assertEqual(self.contexto(contexto=False), "")

    def test_un_hilo_local_sabe_que_no_tiene_casilla(self):
        self.est.vincular("Faro", "proyectos/faro")
        texto = self.contexto()
        self.assertIn("Eres el hilo «Faro» de telar (vinculado a proyectos/faro).", texto)
        self.assertIn("no tiene casilla", texto)
        self.assertIn("skill /hilos", texto)
        self.assertLessEqual(len(texto.splitlines()), 7)  # se carga en cada sesión: corto

    def test_sabe_nombrar_las_cosas_por_su_direccion(self):
        lineas = [l for l in self.contexto().splitlines() if "telar objeto <dirección>" in l]
        self.assertEqual(len(lineas), 1)  # una sola línea, corta
        linea = lineas[0]
        self.assertIn("`tipo:id`", linea)
        self.assertIn("`tarea:T84`", linea)
        self.assertIn("`hilo:Faro`", linea)
        self.assertIn("acciones", linea)
        self.assertIn("nombra las cosas por su dirección", linea)
        self.assertLessEqual(len(linea), 250)

    def test_la_linea_de_direcciones_va_con_y_sin_bus(self):
        from telar import bus as mod_bus

        for hay in (True, False):
            with self.subTest(bus=hay), mock.patch.object(mod_bus, "hay_bus", return_value=hay):
                self.assertIn("telar objeto <dirección>", self.contexto())

    def test_con_cartero_dice_su_direccion(self):
        texto = self.contexto(hilo="Faro Norte", cartero=True)
        self.assertRegex(texto, r"Tu correo: \S+\+faro-norte@\S+\.")
        # «dirección», en el contexto, es la de un objeto (`tipo:id`): el correo no se llama así
        self.assertNotIn("a esa dirección", texto)

    def test_el_proyecto_de_ejemplo_es_el_suyo(self):
        self.est.vincular("Faro", "proyectos/faro")
        self.assertIn("`proyecto:proyectos/faro`", self.contexto())
        self.assertIn("`proyecto:<carpeta relativa a la raíz>`", self.contexto(hilo="Brisa"))


class GanchoDeContexto(ConEstado):
    def setUp(self) -> None:
        super().setUp()
        self.ajustes = self.carpeta / "settings.json"

    def comandos(self, evento):
        datos = json.loads(self.ajustes.read_text(encoding="utf-8"))
        return [g["command"] for e in datos.get("hooks", {}).get(evento, []) for g in e["hooks"]]

    def test_instalar_pone_el_contexto_en_session_start_y_desinstalar_lo_saca(self):
        self.agente().instalar(ruta=self.ajustes)
        comandos = self.comandos("SessionStart")
        self.assertEqual(len(comandos), 2)
        self.assertTrue(any("agente contexto claude-code" in c for c in comandos))
        self.agente().instalar(ruta=self.ajustes)  # dos veces no lo duplica
        self.assertEqual(len(self.comandos("SessionStart")), 2)
        self.agente().desinstalar(ruta=self.ajustes)
        self.assertEqual(self.comandos("SessionStart"), [])

    def test_con_el_contexto_apagado_no_se_pone(self):
        self.config = replace(self.config, agente=replace(self.config.agente, contexto=False))
        self.agente().instalar(ruta=self.ajustes)
        self.assertFalse(any("contexto" in c for c in self.comandos("SessionStart")))


class SkillHilos(ConEstado):
    def test_se_instala_una_vez_y_se_quita(self):
        ruta, estado = mod_skill.instalar(carpeta_config())
        self.assertEqual(estado, "nueva")
        self.assertIn("name: hilos", ruta.read_text(encoding="utf-8"))
        self.assertEqual(mod_skill.instalar(carpeta_config())[1], "al día")
        self.assertEqual(mod_skill.desinstalar(carpeta_config())[1], "quitada")
        self.assertFalse(ruta.exists())

    def test_la_skill_explica_las_direcciones(self):
        texto = mod_skill.SKILL
        self.assertIn("## Nombrar las cosas: direcciones", texto)
        for trozo in ("`tipo:id`", "`tarea:T84`", "`hilo:Faro`", "`telar objeto <dirección> --json`",
                      "`telar objeto --tipos`", "`telar objeto --buscar", "nombra las cosas por su dirección",
                      "`hilo:Faro%40casa`"):
            self.assertIn(trozo, texto)
        # las llaves del ejemplo salen simples: la skill es un f-string
        self.assertIn("--params '{\"texto\": \"…\"}'", texto)

    def test_el_campo_direccion_de_directorio_es_un_correo(self):
        # `telar directorio` llama `direccion` al correo del hilo: la skill no puede decir que todo
        # campo `direccion` es un `tipo:id` sin nombrar la excepción
        texto = mod_skill.SKILL
        self.assertIn("correo (`usuario+hilo@servidor`, en el campo `direccion`)", texto)
        self.assertIn("salvo\n`telar directorio`: ahí `direccion` es el correo del hilo", texto)

    def test_la_skill_no_promete_un_mensaje_por_maquina(self):
        # la casilla es del nombre (bus.tema_casilla): `hilo:Faro@servidor mensaje` no elige máquina
        self.assertIn("Un `mensaje` va a la casilla del nombre, no de la máquina", mod_skill.SKILL)

    def test_el_documento_de_los_agentes_dice_lo_que_trae_el_contexto(self):
        from pathlib import Path

        doc = (Path(__file__).resolve().parents[1] / "docs" / "agentes.md").read_text(encoding="utf-8")
        self.assertNotIn("cinco líneas", doc)  # son más, y depende de la configuración y los módulos
        self.assertIn("`telar objeto` abre", doc)

    def test_una_skill_hilos_ajena_no_se_toca(self):
        ruta = mod_skill.ruta(carpeta_config())
        ruta.parent.mkdir(parents=True)
        ruta.write_text("mía", encoding="utf-8")
        self.assertEqual(mod_skill.instalar(carpeta_config())[1], "ajena")
        self.assertEqual(mod_skill.desinstalar(carpeta_config())[1], "ajena")
        self.assertEqual(ruta.read_text(encoding="utf-8"), "mía")


class NoInteractivos(ConEstado):
    def test_un_claude_p_dentro_de_un_hilo_no_se_anota_ni_recibe_contexto(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_ENTRYPOINT": "sdk-cli", "TELAR_HILO": "Faro"}):
            self.assertTrue(orden_agente._no_interactivo())
            self.assertEqual(orden_agente.contexto(SimpleNamespace(config=self.config)), "")
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_ENTRYPOINT": "cli"}):
            self.assertFalse(orden_agente._no_interactivo())
