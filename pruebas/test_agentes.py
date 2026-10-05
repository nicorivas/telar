"""Agentes residentes: descubrirlos, sus hilos, su home y dónde arrancan."""

from __future__ import annotations

import tempfile
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import agentes as m
from telar import config as mod_config
from telar.agente import lanzar
from telar.ordenes.seccion import validar


class ConCasa(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        r = self.raiz = Path(self.tmp.name)
        for nombre, readme in (("faro", "# Faro\n"), ("cronista", "# cronista/\n"), ("_plantilla", "# <nombre>\n")):
            d = r / "agentes" / nombre
            (d / "memoria").mkdir(parents=True)
            (d / "CLAUDE.md").write_text(f"# {nombre}\n\nEres {nombre}, el que cuida el faro.\nSegunda línea.\n\n## Más\n")
            (d / "README.md").write_text(readme)
        (r / "agentes" / "suelta").mkdir()  # sin CLAUDE.md: no es agente
        (r / "agentes" / "faro" / "proyecto").mkdir()
        (r / "agentes" / "faro" / "bitacora.md").write_text(
            "# Bitácora\n\nIntro.\n\n## 2026-10-01 09:00 — Primera\nCuerpo uno.\n\n## 2026-10-02 — Segunda\n"
            "- 2026-10-03 10:15 — una línea por encargo\n")
        (r / "agentes" / "faro" / "memoria" / "MEMORY.md").write_text(
            "# Memoria\n\n- [La lámpara](lampara.md) — se cambia los lunes\n- [Afuera](https://ejemplo.org) — un enlace\n")
        self.config = mod_config.Config(raiz=r, agentes_carpeta="agentes",
                                        agentes_extra=(mod_config.AgenteExtra(clave="faro", hilos=("◌ guardia*",)),))


class Descubrir(ConCasa):
    def test_las_carpetas_con_claude_md_menos_las_que_empiezan_con_guion_bajo(self):
        nombres = [(a.clave, a.nombre) for a in m.descubrir(self.config)]
        self.assertEqual(nombres, [("cronista", "Cronista"), ("faro", "Faro")])

    def test_sus_hilos_el_suyo_los_declarados_y_los_vinculados_a_su_casa_no_a_una_subcarpeta(self):
        faro = next(a for a in m.descubrir(self.config, {"Guardia": "agentes/faro", "Obra": "agentes/faro/proyecto"})
                    if a.clave == "faro")
        self.assertEqual(faro.hilos, ("Faro", "◌ guardia*", "Guardia"))

    def test_arranca_en_su_casa_y_un_proyecto_suyo_donde_diga_la_config(self):
        cfg = mod_config.Config(raiz=self.raiz, agentes_carpeta="agentes",
                                agente=mod_config.Agente(nombre="claude-code", carpeta="raiz"))
        self.assertEqual(lanzar.carpeta(cfg, self.raiz / "agentes" / "faro"), (self.raiz / "agentes" / "faro").resolve())
        self.assertEqual(lanzar.carpeta(cfg, self.raiz / "agentes" / "faro" / "proyecto"), self.raiz)


class ElHome(ConCasa):
    def test_bitacora_en_los_dos_formatos_la_mas_nueva_primero(self):
        e = m.bitacora(self.raiz / "agentes" / "faro")
        self.assertEqual([(x["titulo"], x["fecha"]) for x in e],
                         [("una línea por encargo", "2026-10-03T10:15"), ("Segunda", "2026-10-02"), ("Primera", "2026-10-01T09:00")])
        self.assertEqual(e[2]["texto"], "Cuerpo uno.")

    def test_memoria_con_sus_archivos(self):
        r = m.memoria(self.raiz / "agentes" / "faro")
        self.assertEqual(r[0]["titulo"], "La lámpara")
        self.assertTrue(r[0]["enlace"].endswith("agentes/faro/memoria/lampara.md"))
        self.assertEqual(r[1]["enlace"], "https://ejemplo.org")

    def test_la_pagina_cumple_el_contrato_y_dice_quien_es(self):
        faro = next(a for a in m.descubrir(self.config) if a.clave == "faro")
        p = m.pagina(faro)
        self.assertEqual(validar(p), "")
        self.assertEqual(p["bloques"][0]["texto"], "Eres faro, el que cuida el faro. Segunda línea.")
        self.assertEqual([b.get("titulo", "") for b in p["bloques"]][1:], ["bitácora · 3", "memoria · 2", "archivos"])
