"""Hilos como ventanas de la sesión del telar, y mirarlos desde afuera por una sesión agrupada fija.

Una parte corre contra un tmux de verdad, pero en un servidor aparte (`TMUX_TMPDIR` temporal): nunca
toca la sesión de quien corre las pruebas. Lo que mira es lo que se rompía en la práctica: que la
vista quede fija en su ventana aunque la sesión del telar cambie, que suelte a quien mira cuando su
ventana muere, y que una marca que no coincide (un `@N` reusado) no se mire.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import estado as mod_estado
from telar import movil, remoto as mod_remoto
from telar.modelo import Hilo
from telar.ordenes import nodo as mod_nodo

HAY_TMUX = shutil.which("tmux") is not None and shutil.which("script") is not None


class Direcciones(unittest.TestCase):
    def test_una_ventana_se_nombra_con_su_marca_y_una_sesion_con_su_nombre(self):
        v = movil.HiloMovil(sesion="telar", nombre="faro", ventana="@12", marca="ab12cd34")
        self.assertEqual((v.direccion, v.objetivo), ("@12/ab12cd34", "@12"))
        s = movil.HiloMovil(sesion="telar-1a2b3c4d", nombre="faro")
        self.assertEqual((s.direccion, s.objetivo), ("telar-1a2b3c4d", "=telar-1a2b3c4d:"))
        self.assertEqual(movil.partir_direccion("@12/ab12cd34"), ("@12", "ab12cd34"))
        self.assertEqual(movil.partir_direccion("telar-1a2b3c4d"), ("", ""))

    def test_el_comando_local_mira_la_ventana_o_se_engancha_a_la_sesion_de_antes(self):
        r = mod_config.Remoto(nombre="srv", destino="yo@srv")
        ventana = mod_remoto.comando(r, "@12/ab12cd34", "", "faro")
        self.assertEqual(ventana[:5], ["mosh", "yo@srv", "--", "bash", "-lc"])
        self.assertIn("@12", ventana[-1])
        self.assertIn("ab12cd34", ventana[-1])
        antes = mod_remoto.comando(r, "telar-1a2b3c4d", "exec bash -l")
        self.assertEqual(antes[3:8], ["tmux", "new-session", "-A", "-s", "telar-1a2b3c4d"])
        por_ssh = mod_remoto.comando(mod_config.Remoto(nombre="srv", destino="yo@srv", transporte="ssh"), "@12/ab", "", "faro")
        self.assertEqual(por_ssh[:3], ["ssh", "-t", "yo@srv"])
        self.assertTrue(por_ssh[3].startswith("bash -lc "))

    def test_la_linea_de_una_ventana_no_le_pone_nombre_a_la_sesion_del_telar(self):
        self.assertNotIn("set-option", mod_remoto.linea("~/x", ["claude"], "faro", marcar=False))
        self.assertIn("set-option", mod_remoto.linea("~/x", ["claude"], "faro"))

    def test_el_celular_se_fija_en_la_ventana_del_hilo(self):
        ordenes = movil.ordenes_grupo("telar", "movil-12", "faro", ventana="@12")
        self.assertEqual(ordenes[0], ["new-session", "-d", "-t", "=telar", "-s", "movil-12"])
        self.assertEqual(ordenes[1], ["select-window", "-t", "=movil-12:@12"])
        self.assertEqual(ordenes[2][:4], ["set-hook", "-t", "=movil-12:", "session-window-changed"])

    def test_la_configuracion_del_remoto_lleva_su_sesion(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "config.toml"
            f.write_text('[remotos.srv]\ndestino = "yo@srv"\nsesion = "taller"\n')
            self.assertEqual(mod_config.cargar(f).remotos[0].sesion, "taller")
            f.write_text('[remotos.srv]\ndestino = "yo@srv"\nsesion = "a:b"\n')
            with self.assertRaises(mod_config.ErrorDeConfig):
                mod_config.cargar(f)


@unittest.skipUnless(HAY_TMUX, "sin tmux o sin script(1)")
class ContraTmuxAparte(unittest.TestCase):
    """Un servidor tmux propio de la prueba: `TMUX_TMPDIR` apunta a una carpeta temporal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        previo = {k: os.environ.get(k) for k in ("TMUX_TMPDIR", "TMUX", "TERM", "TELAR_HILO")}

        def devolver():
            subprocess.run(["tmux", "kill-server"], capture_output=True)
            for k, v in previo.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        os.environ["TMUX_TMPDIR"] = self.tmp.name
        os.environ.pop("TMUX", None)
        os.environ.pop("TELAR_HILO", None)  # si no, quien corre las pruebas desde un hilo es «un agente» y no mueve nada
        os.environ["TERM"] = "xterm-256color"
        self.addCleanup(devolver)
        subprocess.run(["tmux", "new-session", "-d", "-s", "telar", "-n", "uno", "sleep 300"], check=True)
        self.clientes: list[subprocess.Popen] = []
        self.addCleanup(lambda: [c.kill() for c in self.clientes])

    def tmux(self, *args: str) -> str:
        return subprocess.run(["tmux", *args], capture_output=True, text=True).stdout.strip()

    def mirar(self, guion: str) -> None:
        """Corre el guion de la ventana local con una tty de verdad, como lo haría mosh."""
        if platform.system() == "Darwin":
            orden = ["script", "-q", "/dev/null", "bash", "-c", guion]
        else:
            orden = ["script", "-qc", f"bash -c {__import__('shlex').quote(guion)}", "/dev/null"]
        self.clientes.append(subprocess.Popen(orden, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL))

    def esperar(self, condicion, segundos: float = 5.0) -> bool:
        fin = time.monotonic() + segundos
        while time.monotonic() < fin:
            if condicion():
                return True
            time.sleep(0.1)
        return False

    def test_un_hilo_nuevo_es_una_ventana_marcada_y_se_le_puede_escribir(self):
        h = movil.crear("faro", self.tmp.name, ["sleep", "300"], "telar")
        self.assertTrue(h.ventana.startswith("@") and h.marca)
        self.assertEqual(self.tmux("display", "-p", "-t", h.ventana, "#{@telar_id}"), h.marca)
        listadas = {v.nombre: v for v in movil.hilos("telar")}
        self.assertEqual(listadas["faro"].direccion, h.direccion)
        self.assertIn("uno", listadas)  # una ventana sin marca la recibe al listarse
        self.assertTrue(listadas["uno"].marca)
        # la sesión del telar no es un hilo ella misma, aunque alguna vez la hayan marcado
        self.tmux("set-option", "-t", "=telar", "@telar_hilo", "faro")
        self.assertEqual(sum(1 for v in movil.hilos("telar") if v.nombre == "faro"), 1)
        self.assertTrue(movil.sin_mirar("telar"))

    def test_la_vista_queda_fija_y_suelta_cuando_su_ventana_muere(self):
        h = movil.crear("faro", self.tmp.name, ["sleep", "300"], "telar")
        otra = movil.crear("otro", self.tmp.name, ["sleep", "300"], "telar")
        self.mirar(mod_remoto.guion_ver(h.direccion, "faro"))
        vista = mod_remoto.vista(h.direccion)
        self.assertTrue(self.esperar(lambda: self.tmux("list-clients", "-t", f"={vista}", "-F", "x") == "x"),
                        "la vista no se enganchó")
        self.assertEqual(self.tmux("display", "-p", "-t", f"={vista}:", "#{window_id}"), h.ventana)
        # la sesión del telar cambia de ventana (como lo hace telar) y abre otra: la vista no se mueve
        from telar.mux.tmux import Tmux

        self.tmux("new-window", "-t", "=telar:", "-n", "tres", "sleep 300")
        Tmux(mod_config.Config(multiplexor="tmux", sesion="telar")).ir_a_tab(otra.ventana)
        self.assertEqual(self.tmux("display", "-p", "-t", "=telar:", "#{window_id}"), otra.ventana)
        time.sleep(0.3)
        self.assertEqual(self.tmux("display", "-p", "-t", f"={vista}:", "#{window_id}"), h.ventana)
        # muere su ventana: quien miraba se suelta y la vista desaparece; el telar sigue
        self.tmux("kill-window", "-t", h.ventana)
        self.assertTrue(self.esperar(lambda: subprocess.run(["tmux", "has-session", "-t", f"={vista}"],
                                                            capture_output=True).returncode != 0),
                        "la vista siguió viva mostrando otro hilo")
        self.assertIn("otro", self.tmux("list-windows", "-t", "=telar", "-F", "#{window_name}"))

    def test_si_se_va_quien_mira_la_vista_desaparece_y_el_hilo_sigue(self):
        h = movil.crear("faro", self.tmp.name, ["sleep", "300"], "telar")
        self.mirar(mod_remoto.guion_ver(h.direccion, "faro"))
        vista = mod_remoto.vista(h.direccion)
        self.assertTrue(self.esperar(lambda: self.tmux("list-clients", "-t", f"={vista}", "-F", "x") == "x"))
        self.tmux("detach-client", "-s", f"={vista}")
        self.assertTrue(self.esperar(lambda: subprocess.run(["tmux", "has-session", "-t", f"={vista}"],
                                                            capture_output=True).returncode != 0))
        self.assertIn("faro", self.tmux("list-windows", "-t", "=telar", "-F", "#{window_name}"))

    def test_una_marca_que_no_coincide_no_se_mira(self):
        h = movil.crear("faro", self.tmp.name, ["sleep", "300"], "telar")
        r = subprocess.run(["bash", "-c", mod_remoto.guion_ver(f"{h.ventana}/otra0000", "faro")],
                           capture_output=True, text=True, timeout=15)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ya no está", r.stdout)
        self.assertNotIn(mod_remoto.vista(h.direccion), self.tmux("ls", "-F", "#{session_name}"))

    def test_quien_mira_por_una_vista_no_es_el_cliente_que_se_mueve(self):
        from telar.mux.tmux import Tmux

        h = movil.crear("faro", self.tmp.name, ["sleep", "300"], "telar")
        self.mirar(mod_remoto.guion_ver(h.direccion, "faro"))
        vista = mod_remoto.vista(h.direccion)
        self.assertTrue(self.esperar(lambda: self.tmux("list-clients", "-t", f"={vista}", "-F", "x") == "x"))
        mux = Tmux(mod_config.Config(multiplexor="tmux", sesion="telar"))
        tty = self.tmux("list-clients", "-t", f"={vista}", "-F", "#{client_tty}")
        # desde adentro de tmux, «el cliente actual» puede ser el de la vista: no se lo mueve
        with mock.patch.dict(os.environ, {"TMUX": "x"}), \
             mock.patch.object(mux, "_tmux", side_effect=lambda *a, **k: f"{tty}\x1f{vista}" if a[0] == "display-message" else ""):
            self.assertEqual(mux._cliente(), "")


class SeguirAlDueno(Prueba):
    """`ventana_de`: lo que publica la máquina donde vive el hilo manda sobre lo que se sabía aquí."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = mod_config.Config(raiz=Path(self.tmp.name), estado=Path(self.tmp.name) / "estado",
                                        remotos=(mod_config.Remoto(nombre="srv", destino="yo@srv"),))
        self.est = mod_estado.abrir(self.config)
        self.mux = mock.Mock()
        self.vivos: set[str] = set()
        self.nodo = mod_nodo.Nodo.__new__(mod_nodo.Nodo)
        self.nodo.ctx, self.nodo.config, self.nodo.yo = SimpleNamespace(config=self.config), self.config, "laptop"
        self.anotado: list[str] = []
        self.nodo.anotar = self.anotado.append
        self.traidos: list[tuple[str, str]] = []

    def correr(self, d: dict) -> None:
        hilos = tuple(Hilo(id=f"@{n}", nombre=n) for n in sorted(self.vivos | set(self.est.remotos())))
        tel = SimpleNamespace(mux=self.mux, viva=True, estado=self.est, hilos=hilos,
                              por_nombre=lambda n: next((h for h in hilos if h.nombre == n), None),
                              vivo=lambda h: h.nombre in self.vivos)

        def traer(tel_, remoto, sesion, nombre, foco=False):
            self.traidos.append((sesion, nombre))
            self.est.anotar_remoto(nombre, remoto.nombre, sesion)

        with mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
             mock.patch("telar.remoto.traer", side_effect=traer):
            self.nodo.ventana_de(d)

    def test_un_hilo_que_nace_alla_se_trae_por_su_ventana(self):
        self.correr({"nombre": "faro", "maquina": "srv", "vivo": True, "ventana": "@5/aa"})
        self.assertEqual(self.traidos, [("@5/aa", "faro")])

    def test_el_mismo_hilo_en_otra_direccion_se_sigue_sin_duplicarlo(self):
        self.est.anotar_remoto("Gestión", "srv", "telar-5e6f7a8b")
        self.vivos.add("Gestión")
        self.correr({"nombre": "Gestión", "maquina": "srv", "vivo": True, "ventana": "@7/bb", "sesion_tmux": ""})
        self.assertEqual(self.traidos, [("@7/bb", "Gestión")])
        self.mux.cerrar.assert_called_once_with("@Gestión")
        self.assertEqual(self.est.remotos()["Gestión"]["sesion"], "@7/bb")

    def test_un_renombre_alla_se_sigue_aqui(self):
        self.est.anotar_remoto("telar-1a2b3c4d", "srv", "@9/cc")
        self.vivos.add("telar-1a2b3c4d")
        self.correr({"nombre": "T12 Revisión", "maquina": "srv", "vivo": True, "ventana": "@9/cc"})
        self.mux.renombrar.assert_called_once_with("@telar-1a2b3c4d", "T12 Revisión")
        self.assertIn("T12 Revisión", self.est.remotos())
        self.assertNotIn("telar-1a2b3c4d", self.est.remotos())
        self.assertEqual(self.traidos, [])
