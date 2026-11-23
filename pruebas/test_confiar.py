"""La pregunta de Claude Code de confiar en una carpeta (telar.confiar): reconocerla en un panel, y que el nodo marque al
hilo detenido en ella como que espera a la persona, sin contestarla. Con un panel falso y con uno de tmux de verdad, en
un servidor propio (`tmux -S`)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import confiar
from telar import config as mod_config
from telar import estado as mod_estado
from telar.modelo import Atencion

#: la pregunta de `--add-dir`, como la dibuja Claude Code 2.1.327 en un panel de 80 columnas
ADD_DIR = """\
╭──────────────────────────────────────────────────────────────────────────────╮
│                                                                              │
│ Adding a new directory:                                                      │
│ /casa/worktrees/codigo-ritmo                                                 │
│                                                                              │
│ This session hasn't worked here before. Is this a directory you created or   │
│ one you trust?                                                               │
│                                                                              │
│ Claude Code'll be able to read, edit, and execute files here.                │
│                                                                              │
│ Security guide                                                               │
│                                                                              │
│ ❯ 1. Yes, add it                                                             │
│   2. No, leave it out                                                        │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
   Enter to confirm · Esc to cancel
"""

#: la de la carpeta donde arranca, sin recuadro
CARPETA = """\
 Accessing workspace:

 /casa/proyectos/faro

 Quick safety check: Is this a project you created or one you trust? (Like your own code, a well-known open
 source project, or work from your team). If not, take a moment to review what's in this folder first.

 ❯ 1. Yes, I trust this folder
   2. No, exit

 Enter to confirm · Esc to cancel
"""

#: una conversación que habla de la pregunta, con la caja de escribir abajo: no es la pregunta
CONVERSACION = """\
⏺ La pregunta dice «Adding a new directory» y la opción es «Yes, add it». Telar la detecta y no la contesta:

  1. Yes, add it es lo que elige Ana.
  2. telar marca el hilo como que espera.

╭──────────────────────────────────────────────────────────────────────────────╮
│ >                                                                            │
╰──────────────────────────────────────────────────────────────────────────────╯
  ? for shortcuts
"""


class EnPantalla(unittest.TestCase):
    def test_la_de_add_dir(self):
        self.assertEqual(confiar.en_pantalla(ADD_DIR), {"carpeta": "/casa/worktrees/codigo-ritmo", "que": "--add-dir"})

    def test_la_de_la_carpeta_donde_arranca(self):
        self.assertEqual(confiar.en_pantalla(CARPETA), {"carpeta": "/casa/proyectos/faro", "que": "la carpeta donde arranca"})

    def test_con_conversacion_arriba_que_se_corrio(self):
        arriba = "\n".join(f"⏺ línea {i} de lo que pasó antes" for i in range(200))
        self.assertIsNotNone(confiar.en_pantalla(arriba + "\n" + ADD_DIR))

    def test_una_conversacion_que_la_cita_no_es_la_pregunta(self):
        self.assertIsNone(confiar.en_pantalla(CONVERSACION))

    def test_la_pregunta_que_se_corrio_hacia_arriba_ya_no_esta(self):
        # contestada: Claude Code siguió, y lo que queda de ella está muy arriba (en lo que se lee del panel)
        abajo = "\n".join(f"⏺ trabajando, paso {i}" for i in range(confiar.FINAL + 5))
        self.assertIsNone(confiar.en_pantalla(ADD_DIR + abajo + "\n" + CONVERSACION))

    def test_nada(self):
        self.assertIsNone(confiar.en_pantalla(""))
        self.assertIsNone(confiar.en_pantalla(None))
        self.assertIsNone(confiar.en_pantalla("$ ls\nREADME.md\n$ "))

    def test_sin_ruta_legible(self):
        texto = ADD_DIR.replace("/casa/worktrees/codigo-ritmo", "(una ruta que no se lee)")
        self.assertEqual(confiar.en_pantalla(texto)["carpeta"], "")
        self.assertIn("una carpeta", confiar.pide(confiar.en_pantalla(texto)))


class Mirar(Prueba):
    """`confiar.mirar` con un multiplexor falso: un panel por hilo, que muestra lo que diga `pantallas`."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = mod_config.Config(raiz=Path(tmp.name), estado=Path(tmp.name) / "estado")
        self.est = mod_estado.abrir(self.config)
        self.pantallas = {"%1": ADD_DIR, "%2": CONVERSACION, "%3": ADD_DIR, "%4": ADD_DIR}
        hilos = [SimpleNamespace(id="@1", nombre="Ritmo", remoto=""), SimpleNamespace(id="@2", nombre="Telar", remoto=""),
                 SimpleNamespace(id="@3", nombre="Allá", remoto="servidor"), SimpleNamespace(id="@4", nombre="Cerrado", remoto="")]
        self.leidos: list[str] = []

        def capturar(panel, lineas=300):
            self.leidos.append(panel)
            return self.pantallas[panel]

        mux = SimpleNamespace(panes=lambda tab=None: [SimpleNamespace(id=f"%{i}", tab=f"@{i}") for i in range(1, 5)],
                              capturar_pane=capturar)
        self.tel = SimpleNamespace(mux=mux, estado=self.est, hilos=hilos, vivo=lambda h: h.nombre != "Cerrado")

    def test_el_detenido_queda_esperando_a_la_persona_con_lo_que_pide(self):
        cambios = confiar.mirar(self.config, self.tel)
        self.assertEqual(len(cambios), 1)
        self.assertIn("«Ritmo»", cambios[0])
        self.assertEqual(self.est.atencion("Ritmo"), Atencion.ESPERA)
        espera = self.est.espera("Ritmo")
        self.assertEqual(espera["clase"], confiar.CLASE)
        self.assertIn("/casa/worktrees/codigo-ritmo (--add-dir)", espera["pide"])
        self.assertIn("telar no lo contesta", espera["pide"])
        # los demás, no: el que habla de ella, el de otra máquina (su panel es de allá) y el cerrado
        self.assertEqual(self.est.atencion("Telar"), Atencion.NINGUNA)
        self.assertEqual(self.leidos, ["%1", "%2"])

    def test_una_segunda_vuelta_no_lo_vuelve_a_anotar(self):
        confiar.mirar(self.config, self.tel)
        self.assertEqual(confiar.mirar(self.config, self.tel), [])

    def test_contestada_deja_de_esperar(self):
        confiar.mirar(self.config, self.tel)
        self.pantallas["%1"] = CONVERSACION
        cambios = confiar.mirar(self.config, self.tel)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(self.est.atencion("Ritmo"), Atencion.NINGUNA)

    def test_si_los_ganchos_ya_dijeron_otra_cosa_no_la_toca(self):
        confiar.mirar(self.config, self.tel)
        self.est.anotar_atencion("Ritmo", Atencion.TRABAJANDO)   # contestó, y Claude Code arrancó
        self.pantallas["%1"] = CONVERSACION
        self.assertEqual(confiar.mirar(self.config, self.tel), [])
        self.assertEqual(self.est.atencion("Ritmo"), Atencion.TRABAJANDO)

    def test_otra_espera_no_es_suya(self):
        self.est.anotar_atencion("Telar", Atencion.ESPERA)
        self.est.anotar_espera("Telar", "Claude needs your permission to use Bash", "permiso")
        confiar.mirar(self.config, self.tel)
        self.assertEqual(self.est.espera("Telar")["clase"], "permiso")

    def test_nunca_la_contesta(self):
        escrito = []
        self.tel.mux.escribir_pane = lambda *a, **k: escrito.append(a)
        self.tel.mux.escribir = lambda *a, **k: escrito.append(a)
        confiar.mirar(self.config, self.tel)
        self.assertEqual(escrito, [])

    def test_el_hilo_lo_dice_en_su_json(self):
        from telar.ordenes import _comun

        confiar.mirar(self.config, self.tel)
        h = SimpleNamespace(nombre="Ritmo", atencion=Atencion.ESPERA)
        self.assertEqual(_comun._espera(self.tel, h)["clase"], confiar.CLASE)
        self.assertIsNone(_comun._espera(self.tel, SimpleNamespace(nombre="Telar", atencion=Atencion.NINGUNA)))

    def test_sin_multiplexor_nada(self):
        self.assertEqual(confiar.mirar(self.config, SimpleNamespace(mux=None, estado=self.est, hilos=[])), [])


@unittest.skipUnless(shutil.which("tmux"), "sin tmux instalado")
class EnUnPanelDeVerdad(Prueba):
    """La pregunta escrita en un panel de tmux de verdad, de 80 columnas, leída con capture-pane: en un servidor propio
    (`tmux -S <socket>`), nunca el de la persona."""

    def setUp(self):
        super().setUp()
        self.carpeta = Path(tempfile.mkdtemp(prefix="telar-confiar-"))
        self.addCleanup(shutil.rmtree, self.carpeta, True)
        self.socket = str(self.carpeta / "s")
        (self.carpeta / "pregunta.txt").write_text(ADD_DIR)
        self.tmux("new-session", "-d", "-x", "80", "-y", "30", "-s", "confiar",
                  f"cat {self.carpeta / 'pregunta.txt'}; sleep 30")
        self.addCleanup(lambda: subprocess.run(["tmux", "-S", self.socket, "kill-server"], capture_output=True))

    def tmux(self, *args: str) -> str:
        entorno = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        return subprocess.run(["tmux", "-S", self.socket, *args], capture_output=True, text=True, env=entorno,
                              check=True).stdout

    def test_se_reconoce_lo_que_capture_pane_devuelve(self):
        texto = ""
        for _ in range(50):
            texto = self.tmux("capture-pane", "-p", "-J", "-S", "-1", "-t", "confiar")
            if "Yes, add it" in texto:
                break
            time.sleep(0.05)
        self.assertEqual(confiar.en_pantalla(texto), {"carpeta": "/casa/worktrees/codigo-ritmo", "que": "--add-dir"})
