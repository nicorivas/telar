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
        self.assertLessEqual(len(texto.splitlines()), 6)  # se carga en cada sesión: corto

    def test_con_cartero_dice_su_direccion(self):
        texto = self.contexto(hilo="Faro Norte", cartero=True)
        self.assertRegex(texto, r"Tu correo: \S+\+faro-norte@\S+\.")


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

    def test_una_skill_hilos_ajena_no_se_toca(self):
        ruta = mod_skill.ruta(carpeta_config())
        ruta.parent.mkdir(parents=True)
        ruta.write_text("mía", encoding="utf-8")
        self.assertEqual(mod_skill.instalar(carpeta_config())[1], "ajena")
        self.assertEqual(mod_skill.desinstalar(carpeta_config())[1], "ajena")
        self.assertEqual(ruta.read_text(encoding="utf-8"), "mía")
