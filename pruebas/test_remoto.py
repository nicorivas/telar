"""Hilos remotos: la configuración, el comando de la ventana, el reconocimiento y el estado.

Lo que habla con otra máquina (mosh, ssh) no se prueba aquí: se probó contra un servidor
de verdad. Aquí va lo que decide qué se le dice.
"""

from __future__ import annotations

import shlex
import tempfile
import unittest
from pathlib import Path

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import estado as mod_estado
from telar import remoto as r
from telar.config import Config, ErrorDeConfig, Remoto
from telar.mux import tmux as t
from telar.mux.base import Pane, Tab


CASA = Remoto(nombre="casa", destino="usuario@servidor", transporte="mosh", raiz="~/repo")


class Configuracion(Prueba):
    def test_se_declaran_por_nombre(self):
        cfg = mod_config.desde_dict({"remotos": {"casa": {"destino": "usuario@servidor", "raiz": "~/repo/"}}})
        self.assertEqual(cfg.remotos, (Remoto("casa", "usuario@servidor", "mosh", "~/repo"),))

    def test_sin_seccion_no_hay_remotos(self):
        self.assertEqual(mod_config.desde_dict({}).remotos, ())

    def test_lo_que_no_sirve_se_rechaza(self):
        for malo in ({"destino": ""}, {"destino": "-oProxyCommand=x"}, {"destino": "a@b", "transporte": "telnet"},
                     {"destino": "a@b", "puerto": 22}):
            with self.assertRaises(ErrorDeConfig, msg=malo):
                mod_config.desde_dict({"remotos": {"casa": malo}})


class Comando(Prueba):
    def test_mosh_lleva_el_tmux_de_alla_como_palabras(self):
        c = r.comando(CASA, "telar-1234abcd", "cd ~; exec bash -l")
        self.assertEqual(c, ["mosh", "usuario@servidor", "--", "tmux", "new-session", "-A", "-s",
                             "telar-1234abcd", "bash", "-lc", "cd ~; exec bash -l"])

    def test_ssh_lo_cita_entero_porque_junta_sus_argumentos(self):
        c = r.comando(Remoto("casa", "usuario@servidor", "ssh"), "telar-1", "echo 'a b'")
        self.assertEqual(c[:3], ["ssh", "-t", "usuario@servidor"])
        self.assertEqual(shlex.split(c[3])[-1], "echo 'a b'")

    def test_el_vinculo_se_traduce_a_la_raiz_de_alla(self):
        self.assertEqual(r.ruta_remota(CASA, "proyectos/faro"), "~/repo/proyectos/faro")
        self.assertEqual(r.ruta_remota(CASA, ""), "~/repo")
        self.assertEqual(r.ruta_remota(CASA, "/Users/alguien/otro"), "~/repo")  # absoluto: sin traducción
        self.assertEqual(r.ruta_remota(CASA, "../fuera"), "~/repo")

    def test_la_linea_deja_la_tilde_para_la_shell_de_alla(self):
        l = r.linea("~/repo/el faro", ["claude", "--session-id", "x"], "faro")
        self.assertIn("; cd ~/'repo/el faro' 2>/dev/null;", l)
        self.assertIn("export TELAR_HILO=faro", l)
        self.assertIn("claude --session-id x", l)
        self.assertTrue(l.endswith("exec bash -l"))

    def test_la_sesion_sirve_para_tmux(self):
        s = r.sesion_nueva()
        self.assertTrue(s.startswith("telar-"))
        self.assertNotIn(".", s)
        self.assertNotIn(":", s)


class Reconocer(Prueba):
    def _hilo(self, tab: Tab, comando: str):
        m = t.Tmux(Config(sesion="taller"))
        return m.hilo_de(tab, [Pane(id="%1", tab=tab.id, titulo="", comando=comando, ruta=None, foco=True)])

    def test_por_la_marca(self):
        self.assertEqual(self._hilo(Tab(id="@1", posicion=1, nombre="x", remoto="casa"), "mosh-client").remoto, "casa")

    def test_sin_marca_por_el_comando(self):
        for cliente in ("mosh-client", "ssh", "et"):
            self.assertEqual(self._hilo(Tab(id="@1", posicion=1, nombre="x"), cliente).remoto, "?")

    def test_una_shell_es_local(self):
        self.assertEqual(self._hilo(Tab(id="@1", posicion=1, nombre="x"), "zsh").remoto, "")


class Estado(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.est = mod_estado.abrir(Config(estado=Path(self.tmp.name)))

    def test_se_anota_se_renombra_y_se_olvida(self):
        self.est.anotar_remoto("faro", "casa", "telar-1")
        self.assertEqual(self.est.remotos(), {"faro": {"remoto": "casa", "sesion": "telar-1"}})
        self.est.renombrar("faro", "Faro norte")
        self.assertEqual(self.est.remotos(), {"Faro norte": {"remoto": "casa", "sesion": "telar-1"}})
        self.est.olvidar("Faro norte")
        self.assertEqual(self.est.remotos(), {})

    def test_vestir_toma_el_remoto_del_estado_si_no_hay_marca(self):
        from telar.modelo import Hilo

        (h,) = mod_estado.vestir([Hilo(id="faro", nombre="faro")], remotos={"faro": {"remoto": "casa", "sesion": "s"}})
        self.assertEqual(h.remoto, "casa")


class Llevar(Prueba):
    def test_alla_el_agente_arranca_donde_dice_agente_carpeta(self):
        from telar.config import Agente

        def carpeta(donde):
            return r.carpeta_remota(Config(agente=Agente(nombre="claude-code", carpeta=donde)), CASA, "proyectos/faro")

        self.assertEqual(carpeta("hilo"), "~/repo/proyectos/faro")
        self.assertEqual(carpeta("raiz"), "~/repo")
        self.assertEqual(carpeta("~/notas"), "~/notas")
        self.assertEqual(carpeta(str(Path.home() / "notas")), "~/notas")  # el hogar de aquí es el de allá

    def test_lo_que_no_esta_subido_se_dice(self):
        import subprocess

        from telar.ordenes.hilo import _sin_subir

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_sin_subir(Path(tmp)), "")  # no es un repositorio: nada que decir
            subprocess.run(["git", "init", "-q", tmp], check=True)
            (Path(tmp) / "a.txt").write_text("x", encoding="utf-8")
            self.assertIn("1 archivo sin commitear", _sin_subir(Path(tmp)))


class SesionesQueNacieronAlla(unittest.TestCase):
    def test_solo_las_nuevas_y_sin_pisar_nombres(self):
        from telar import remoto

        de_alla = [("telar-aaaa0001", "Faro"), ("telar-bbbb0002", "▶ pasada 09/26 07:00"),
                   ("telar-cccc0003", "Faro")]
        nuevas = remoto.nuevas({"telar-aaaa0001"}, de_alla, {"Faro"})
        self.assertEqual(nuevas, [("telar-bbbb0002", "▶ pasada 09/26 07:00", "▶ pasada 09/26 07:00"),
                                  ("telar-cccc0003", "Faro", "Faro · 2")])

    def test_lee_la_lista_de_tmux_con_el_separador_en_octal(self):
        from unittest import mock

        from telar import remoto
        from telar.config import Remoto

        salida = "telar-aaaa0001\\037Faro\nmovil-aaaa0001\\037Faro\ntelar-bbbb0002\\037\notra\\037x\n"
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout=salida, stderr="")):
            sesiones, error = remoto.sesiones(Remoto(nombre="s", destino="u@s"))
        self.assertEqual((sesiones, error), ([("telar-aaaa0001", "Faro")], ""))


class QueConversacionRetomarAlla(Prueba):
    """El id anotado aquí al abrir puede no tener archivo allá: un `/resume` dentro de
    Claude escribe en el archivo de otra conversación, y `--resume <id de aquí>` falla."""

    def _correr(self, hilo, candidatas, anotadas=None, archivos=()):
        import json
        import os
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            estado = Path(tmp) / "estado" / "telar"
            estado.mkdir(parents=True)
            if anotadas is not None:
                (estado / "sesiones.json").write_text(json.dumps(anotadas))
            for sid in archivos:
                carpeta = Path(tmp) / "claude" / "projects" / "-home-u-Vida"
                carpeta.mkdir(parents=True, exist_ok=True)
                (carpeta / f"{sid}.jsonl").write_text("{}\n")
            entorno = {**os.environ, "XDG_STATE_HOME": str(Path(tmp) / "estado"),
                       "CLAUDE_CONFIG_DIR": str(Path(tmp) / "claude")}
            r_ = subprocess.run([sys.executable, "-c", r._CONVERSACION, hilo, *candidatas],
                                capture_output=True, text=True, env=entorno, check=True)
            return r_.stdout.strip()

    def test_gana_la_que_anoto_el_telar_de_alla_si_tiene_archivo(self):
        self.assertEqual(self._correr("Faro", ["aqui"], {"Faro": ["alla"]}, archivos=["aqui", "alla"]), "alla")

    def test_la_de_aqui_sin_archivo_cede_a_la_de_alla(self):
        self.assertEqual(self._correr("Faro", ["aqui"], {"Faro": ["alla"]}, archivos=["alla"]), "alla")

    def test_sin_estado_alla_sirve_la_de_aqui_si_existe(self):
        self.assertEqual(self._correr("Faro", ["aqui"], None, archivos=["aqui"]), "aqui")

    def test_ninguna_con_archivo_es_vacio(self):
        self.assertEqual(self._correr("Faro", ["aqui"], {"Faro": ["alla"]}), "")

    def test_si_la_otra_maquina_no_responde_no_se_sabe(self):
        from unittest import mock

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=255, stdout="", stderr="sin ruta")):
            sid, error = r.conversacion_alla(Remoto(nombre="s", destino="u@s"), "Faro", ["aqui"])
        self.assertEqual((sid, error), (None, "sin ruta"))
