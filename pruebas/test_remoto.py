"""Hilos remotos: la configuración, el comando de la ventana, el reconocimiento y el estado.

Lo que habla con otra máquina (mosh, ssh) no se prueba aquí: se probó contra un servidor
de verdad. Aquí va lo que decide qué se le dice.
"""

from __future__ import annotations

import shlex
import tempfile
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
        self.assertTrue(l.startswith("cd ~/'repo/el faro'"))
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
