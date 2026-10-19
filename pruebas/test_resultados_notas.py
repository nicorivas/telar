"""Lo que dejan las skills por día (`[resultados]`) y las notas de los eventos (`[notas]`)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import bus as mod_bus
from telar import config as mod_config
from telar import notas, resultados


class Resultados(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.planes = Path(self.tmp.name) / "planes"
        self.planes.mkdir()
        (self.planes / "2026-10-06.json").write_text(json.dumps({"dia": "2026-10-06", "foco": {"paso": "x"}}))
        (self.planes / "2026-10-05.md").write_text("# plan viejo")

    def config(self, **extra):
        return mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                 resultados=(mod_config.Resultado(clave="plan", carpeta=str(self.planes), **extra),))

    def test_se_lee_el_json_del_dia_con_los_dias_disponibles(self):
        r = resultados.local(self.config(), "plan", "2026-10-06")
        self.assertTrue(r["ok"])
        self.assertEqual((r["formato"], r["contenido"]["foco"]["paso"]), ("json", "x"))
        self.assertEqual(r["dias"], ["2026-10-06", "2026-10-05"])

    def test_un_md_viejo_se_entrega_como_texto_y_un_dia_sin_plan_vacio(self):
        self.assertEqual(resultados.local(self.config(), "plan", "2026-10-05")["formato"], "md")
        vacio = resultados.local(self.config(), "plan", "2026-10-01")
        self.assertTrue(vacio["ok"])
        self.assertIsNone(vacio["contenido"])

    def test_un_dia_mal_escrito_o_un_resultado_que_no_existe_se_dicen(self):
        self.assertFalse(resultados.local(self.config(), "plan", "../../etc")["ok"])
        self.assertFalse(resultados.local(self.config(), "otro")["ok"])

    def test_con_bus_se_pide_alla_y_si_no_responde_se_lee_aqui(self):
        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                bus=mod_config.Bus(url="nats://x:1", maquina="laptop"),
                                resultados=(mod_config.Resultado(clave="plan", carpeta=str(self.planes), en="servidor"),))
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "contenido": {"de": "allá"}}) as pedir:
            r = resultados.leer(cfg, "plan", "2026-10-06")
        self.assertEqual((r["desde"], r["contenido"]), ("servidor", {"de": "allá"}))
        self.assertEqual(pedir.call_args[0][1:3], ("servidor", "resultado"))
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "no respondió"}):
            r = resultados.leer(cfg, "plan", "2026-10-06")
        self.assertEqual((r["desde"], r["contenido"]["foco"]["paso"]), ("aquí", "x"))
        self.assertIn("no respondió", r["aviso"])

    def comentador(self, cuerpo='cat > "$TELAR_RESULTADO_CARPETA/comentario-$TELAR_RESULTADO_DIA.txt"; echo "✎ plan · abierto"'):
        guion = Path(self.tmp.name) / "comentar"
        guion.write_text("#!/bin/sh\n" + cuerpo + "\n")
        guion.chmod(0o755)
        return (str(guion),)

    def test_un_comentario_llega_por_la_entrada_al_comando_con_el_dia(self):
        r = resultados.comentar_local(self.config(comentar=self.comentador()), "plan", "2026-10-06", "  falta la reunión  ")
        self.assertEqual(r, {"ok": True, "abrio": "✎ plan"})
        self.assertEqual((self.planes / "comentario-2026-10-06.txt").read_text(), "falta la reunión")
        self.assertTrue(resultados.local(self.config(comentar=self.comentador()), "plan", "2026-10-06")["comentable"])
        self.assertFalse(resultados.local(self.config(), "plan", "2026-10-06")["comentable"])

    def test_un_comentario_que_no_sirve_no_corre_nada(self):
        cfg = self.config(comentar=self.comentador())
        for dia, texto in (("2026-10-01", "x"), ("../etc", "x"), ("2026-10-06", "   ")):
            self.assertFalse(resultados.comentar_local(cfg, "plan", dia, texto)["ok"])
        self.assertFalse(resultados.comentar_local(self.config(), "plan", "2026-10-06", "x")["ok"])  # sin comentar
        self.assertEqual(list(self.planes.glob("comentario-*")), [])

    def test_si_el_comando_falla_se_dice_su_ultima_linea(self):
        r = resultados.comentar_local(self.config(comentar=self.comentador('echo "no hay pasada" >&2; exit 3')), "plan", "2026-10-06", "x")
        self.assertEqual(r, {"ok": False, "error": "no hay pasada"})

    def test_con_bus_el_comentario_va_a_la_maquina_del_resultado(self):
        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                bus=mod_config.Bus(url="nats://x:1", maquina="laptop"),
                                resultados=(mod_config.Resultado(clave="plan", carpeta=str(self.planes), en="servidor"),))
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": True, "abrio": "✎ plan"}) as pedir:
            r = resultados.comentar(cfg, "plan", "2026-10-06", "hola")
        self.assertEqual(r["abrio"], "✎ plan")
        self.assertEqual(pedir.call_args[0][1:4], ("servidor", "resultado-comentar", {"clave": "plan", "dia": "2026-10-06", "texto": "hola"}))

    def test_la_configuracion_se_lee_y_se_valida(self):
        f = Path(self.tmp.name) / "config.toml"
        f.write_text('[resultados.plan]\ncarpeta = "~/planes"\nen = "telar"\nnombre = "Plan del día"\n\n[notas]\nen = "telar"\n')
        cfg = mod_config.cargar(f)
        self.assertEqual((cfg.resultados[0].clave, cfg.resultados[0].en, cfg.resultados[0].nombre), ("plan", "telar", "Plan del día"))
        self.assertEqual(cfg.notas.en, "telar")
        f.write_text('[resultados.plan]\nnombre = "x"\n')
        with self.assertRaises(mod_config.ErrorDeConfig):
            mod_config.cargar(f)


class Notas(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado")

    def test_una_nota_se_guarda_por_evento_y_se_lee(self):
        r = notas.agregar_local(self.cfg, "2026-10-07", "ev1", "Llevar el deck", de="planear", titulo="Comité", inicio="10:00")
        self.assertTrue(r["ok"])
        notas.agregar_local(self.cfg, "2026-10-07", "ev1", "Preguntar por el precio", de="Nico")
        e = notas.leer_local(self.cfg, "2026-10-07")["eventos"]["ev1"]
        self.assertEqual((e["titulo"], e["inicio"]), ("Comité", "10:00"))
        self.assertEqual([n["de"] for n in e["notas"]], ["planear", "Nico"])

    def test_sin_evento_o_sin_texto_no_se_guarda(self):
        self.assertFalse(notas.agregar_local(self.cfg, "2026-10-07", "", "x", de="a")["ok"])
        self.assertFalse(notas.agregar_local(self.cfg, "2026-10-07", "ev", " ", de="a")["ok"])
        self.assertFalse(notas.agregar_local(self.cfg, "hoy", "ev", "x", de="a")["ok"])

    def test_con_bus_escribir_alla_y_si_no_responde_no_se_escribe_aqui(self):
        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                bus=mod_config.Bus(url="nats://x:1", maquina="laptop"),
                                notas=mod_config.Notas(en="servidor"))
        with mock.patch.object(mod_bus, "pedir", return_value={"ok": False, "error": "no respondió"}):
            r = notas.agregar(cfg, "2026-10-07", "ev1", "x", de="a")
        self.assertFalse(r["ok"])
        self.assertEqual(notas.leer_local(cfg, "2026-10-07")["eventos"], {})
