"""`scripts/medir.py`, sin red ni navegador: sus opciones, los nombres de las pantallas, que lo que da por sabido de la
página siga siendo cierto (los modos, las pestañas de fábrica, las vistas de un hilo, los atributos que aprieta) y
que limpie siempre: con un agent-browser y un `dev.py` de mentira que fallan o se cuelgan, no queda ni la página, ni
el navegador, ni su archivo de estado; y lo que dejó una corrida muerta, lo limpia la siguiente.

El ensayo de verdad (la página y Chromium) no corre aquí: `python3 scripts/medir.py todas -s .pantalla-barra -s
.franja` (docs/desarrollar.md, «Comprobar en el navegador»).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import comun
from comun import RAIZ

_spec = importlib.util.spec_from_file_location("medir", RAIZ / "scripts" / "medir.py")
medir = importlib.util.module_from_spec(_spec)
sys.modules["medir"] = medir
_spec.loader.exec_module(medir)

PAGINA = RAIZ / "pagina" / "src"


def leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


class Opciones(comun.Prueba):
    def analizar(self, *argv: str):
        with contextlib.redirect_stderr(io.StringIO()):
            return medir.analizar(list(argv))

    def falla(self, *argv: str) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            medir.analizar(list(argv))
        return err.getvalue()

    def test_selectores_estilos_y_ventana(self):
        o = self.analizar("calendario", "-s", ".pantalla-barra", "-s", ".franja", "-e", "height, padding-top", "-e=--x")
        self.assertEqual(o.selector, [".pantalla-barra", ".franja"])
        self.assertEqual(o.estilos, ["height", "padding-top", "--x"])
        self.assertEqual(o.ventana, medir.ESCRITORIO)
        self.assertFalse(o.telefono)
        self.assertEqual((o.paso, o.total), (10.0, 90.0))
        self.assertEqual(self.analizar("proyectos", "--captura", "--ventana", "1024x700").ventana, (1024, 700))
        self.assertEqual(self.analizar("proyectos", "--captura").captura, "")
        self.assertEqual(self.analizar("proyectos", "--captura", "/tmp/x").captura, "/tmp/x")
        self.assertIsNone(self.analizar("proyectos", "--js", "1").captura)

    def test_lo_que_no_va(self):
        self.assertIn("qué pantallas", self.falla("-s", ".x"))
        self.assertIn("qué medir", self.falla("proyectos"))
        self.assertIn("ANCHOxALTO", self.falla("proyectos", "-s", "a", "--ventana", "grande"))
        self.assertIn("not allowed", self.falla("proyectos", "-s", "a", "--ventana", "800x600", "--telefono"))
        self.assertIn("más que 0", self.falla("proyectos", "-s", "a", "--paso", "0"))
        self.assertIn("no es un modo", self.falla("modo:calma", "-s", "a"))
        self.assertIn("la vista de un hilo", self.falla("hilo:Faro/mapa", "-s", "a"))
        self.assertIn("falta el nombre", self.falla("hilo:", "-s", "a"))
        self.assertIn("tipo:id", self.falla("obj:T84", "-s", "a"))

    def test_lista_no_pide_pantallas(self):
        o = self.analizar("--lista")
        self.assertTrue(o.lista)
        self.assertEqual(o.recorrido, [])


class Nombres(comun.Prueba):
    def nombres(self, *n: str, hilo: str = "") -> list[str]:
        return [p.nombre for p in medir.resolver(list(n), hilo)]

    def test_modos_sin_tildes_ni_mayusculas(self):
        self.assertEqual(self.nombres("Táctica", "ESTRATEGIA", "foco", "modo:todo"),
                         ["modo:tactica", "modo:estrategia", "modo:foco", "modo:todo"])

    def test_pestanas_config_hilos_y_archivos(self):
        self.assertEqual(self.nombres("calendario", "te esperan", "pestana:bloque:correo", "bloque:correo"),
                         ["pestana:calendario", "pestana:te esperan", "pestana:bloque:correo", "pestana:bloque:correo"])
        self.assertEqual(self.nombres("config", "config:Modos", "dashboard"), ["config", "config:modos", "dashboard"])
        # sin vista, la conversación: la terminal le cambia el tamaño a la ventana de tmux del hilo
        self.assertEqual(self.nombres("hilo:Faro", "hilo:Faro/term", "hilo:Faro/Lectura"),
                         ["hilo:Faro/conv", "hilo:Faro/term", "hilo:Faro/lectura"])
        self.assertEqual(self.nombres("obj:tarea:T84"), ["obj:tarea:T84"])
        [arch] = medir.resolver(["arch:README.md"])
        self.assertTrue(Path(arch.valor).is_absolute())

    def test_pestanas_ponen_todo_primero(self):
        self.assertEqual(self.nombres("pestanas"), ["modo:todo", "pestanas"])

    def test_todas(self):
        sin = self.nombres("todas")
        self.assertEqual(sin[:4], ["modo:tactica", "modo:estrategia", "modo:todo", "pestanas"])
        self.assertIn("config", sin)
        self.assertTrue(any(n.startswith("arch:") and n.endswith("README.md") for n in sin))
        self.assertFalse(any(n.startswith("hilo:") for n in sin))
        # foco al final: muestra lo último que se miró
        self.assertEqual(sin[-1], "modo:foco")
        con = self.nombres("todas", hilo="Faro")
        self.assertEqual(con[-2:], ["hilo:Faro/conv", "modo:foco"])

    def test_cada_pantalla_sabe_llegar(self):
        for p in medir.resolver(["todas", "calendario", "config:modos", "hilo:Faro/term", "hilo:Faro/lectura", "obj:tarea:T1",
                                 "dashboard"], "Faro"):
            if p.tipo == "pestanas":
                continue
            for telefono in (False, True):
                lista = medir.pasos(p, telefono, medir.ESCRITORIO)
                self.assertTrue(lista, p)
                for paso in lista:
                    self.assertIn(paso[0], ("js", "ab"))
        # en un laptop, la conversación de un hilo se abre angosta (sin montar la terminal) y se vuelve al ancho
        lista = medir.pasos(medir.Pantalla("hilo", "Faro", "conv"), False, (1440, 900))
        self.assertEqual(lista[0], ("ab", "set", "viewport", "390", "900"))
        self.assertEqual(lista[-2], ("ab", "set", "viewport", "1440", "900"))
        self.assertFalse(any(p[0] == "ab" for p in medir.pasos(medir.Pantalla("hilo", "Faro", "conv"), True, (1440, 900))))


class LoQueDeclaraLaPagina(comun.Prueba):
    """Lo que medir da por sabido de la página: si la página cambia, esto falla antes que el ensayo."""

    def test_los_modos(self):
        fuente = leer(PAGINA / "componentes" / "modos-mundos.ts")
        bloque = fuente[fuente.index("export const MODOS"):].split("];", 1)[0]
        self.assertEqual(tuple(re.findall(r"clave: '([^']+)'", bloque)), medir.MODOS)

    def test_las_pestanas_de_fabrica(self):
        fuente = leer(PAGINA / "vistas" / "dashboard" / "panel.ts")
        bloque = fuente[fuente.index("private todasLasPestanas"):].split("return todas;", 1)[0]
        claves = tuple(re.findall(r"^\s*\['([^']+)', '[^']*', '[^']*', '[^']*', '[^']*'\]", bloque, re.M))
        self.assertEqual(claves, medir.PESTANAS_DE_FABRICA)
        # «tareas» es la acción «foco» (medir la busca por su nombre, su clave o su acción)
        self.assertIn("['revisar', 'foco', '', 'tareas', 'v']", bloque)

    def test_las_vistas_de_un_hilo(self):
        fuente = leer(PAGINA / "web" / "vistas-hilo.ts")
        self.assertEqual(tuple(re.findall(r"\{ clave: '([^']+)', nombre:", fuente)), medir.VISTAS_HILO)

    def test_lo_que_aprieta_y_lee(self):
        app = leer(PAGINA / "navegador" / "app.ts")
        indice = leer(RAIZ / "src" / "telar" / "web" / "indice.html")
        self.assertIn('id="modos-fila"', indice)
        self.assertIn('id="vistas"', indice)
        self.assertIn('id="acciones"', indice)
        self.assertIn('data-accion="modos-modo" data-id="${esc(clave)}"', leer(PAGINA / "componentes" / "modos-mundos.ts"))
        self.assertIn("accion: 'dash', id: JSON.stringify([p.accion, p.valor])", leer(PAGINA / "vistas" / "hilos.ts"))
        self.assertIn("accion: 'vista', valor: v.clave", app)
        self.assertIn("window.telar = { ...(window.telar ?? {}), mostrar,", app)
        self.assertIn("if (que === 'config')", app)
        self.assertIn("s.dataset.p = clave;", app)
        self.assertIn('class="config-op', leer(PAGINA / "vistas" / "dashboard" / "config" / "configuracion.ts"))
        self.assertIn('<div class="config">', leer(PAGINA / "vistas" / "dashboard" / "config" / "configuracion.ts"))

    def test_la_llave_y_lo_que_dice_dev(self):
        self.assertIn(f'COOKIE = "{medir.COOKIE}"', leer(RAIZ / "src" / "telar" / "api_web.py"))
        self.assertIn("la página en http://{host}:{o.web_puerto}", leer(RAIZ / "src" / "telar" / "ordenes" / "serve.py"))
        self.assertIn("app.js y componentes.js ${r.errors.length ? `con ${r.errors.length} error(es)` : 'listo'}",
                      leer(RAIZ / "pagina" / "scripts" / "navegador.mjs"))
        self.assertIn('"--puerto"', leer(RAIZ / "scripts" / "dev.py"))


# ── limpiar siempre, con un navegador y una página de mentira ────────────────

AB_FALSO = textwrap.dedent('''\
    #!{python}
    """agent-browser de mentira: anota cada orden; FALSO_FALLA=<orden> falla en ella, FALSO_CUELGA=<orden> se cuelga."""
    import json, os, subprocess, sys, time
    from pathlib import Path
    args = sys.argv[1:]
    sesion = args[args.index("--session") + 1]
    orden = [a for a in args if not a.startswith("--") and a != sesion][0]
    entrada = sys.stdin.read() if "--stdin" in args else ""
    with open(os.environ["FALSO_LOG"], "a") as f:
        f.write(json.dumps({{"args": args, "stdin": entrada}}) + "\\n")
    # el daemon: un proceso que vive hasta que lo cierren (y que `close` no cierra, si FALSO_CLOSE_NO)
    pidfile = Path(os.environ["AGENT_BROWSER_SOCKET_DIR"]) / f"{{sesion}}.pid"
    if not pidfile.exists():
        d = subprocess.Popen(["sleep", "300"], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pidfile.write_text(str(d.pid))
    if orden == "close":
        if not os.environ.get("FALSO_CLOSE_NO"):
            os.kill(int(pidfile.read_text()), 15)
            pidfile.unlink()
        print(json.dumps({{"success": True, "data": {{}}}}))
        sys.exit(0)
    if orden == os.environ.get("FALSO_CUELGA"):
        time.sleep(300)
    if orden == os.environ.get("FALSO_FALLA"):
        print(json.dumps({{"success": False, "data": None, "error": "falla de mentira"}}))
        sys.exit(1)
    print(json.dumps({{"success": True, "data": {{"result": {{"ok": True}}}}}}))
''')

DEV_FALSO = textwrap.dedent('''\
    #!{python}
    """dev.py de mentira: sirve /manifest.webmanifest en su puerto, dice lo que dice dev.py y deja un nieto en su
    propia sesión (como esbuild y telar serve), que anota en FALSO_NIETO."""
    import http.server, os, subprocess, sys
    puerto = int(sys.argv[sys.argv.index("--puerto") + 1])
    nieto = subprocess.Popen(["sleep", "300"], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    open(os.environ["FALSO_NIETO"], "w").write(str(nieto.pid))
    print("20:00:00 app.js y componentes.js listo", flush=True)
    print(f"telar serve: la página en http://127.0.0.1:{{puerto}} (con la llave de ...)", flush=True)
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"{{}}")
        def log_message(self, *a): pass
    try:
        http.server.HTTPServer(("127.0.0.1", puerto), H).serve_forever()
    finally:
        nieto.kill()
''')

LLAVE = "llave-secreta-de-mentira-1234"


def huerfano() -> int:
    """Un proceso que no es hijo de las pruebas (como la página de una corrida muerta): al morir no queda zombi."""
    r = subprocess.run(["sh", "-c", "sleep 300 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True, check=True)
    return int(r.stdout.strip())


class Limpia(comun.Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="medir-"))
        self.ab = self.tmp / "agent-browser"
        self.ab.write_text(AB_FALSO.format(python=sys.executable))
        self.ab.chmod(0o755)
        self.dev = self.tmp / "dev.py"
        self.dev.write_text(DEV_FALSO.format(python=sys.executable))
        self.log = self.tmp / "ab.log"
        self.nieto = self.tmp / "nieto.pid"
        self.estado = self.tmp / "estado"
        (self.tmp / "sesiones").mkdir()
        (self.tmp / "config" / "telar").mkdir(parents=True)
        (self.tmp / "config" / "telar" / "panel.llave").write_text(LLAVE + "\n")
        self.antes = {k: os.environ.get(k) for k in ("FALSO_LOG", "FALSO_NIETO", "AGENT_BROWSER_SOCKET_DIR", "FALSO_FALLA",
                                                      "FALSO_CUELGA", "FALSO_CLOSE_NO", "XDG_CONFIG_HOME")}
        os.environ.update(FALSO_LOG=str(self.log), FALSO_NIETO=str(self.nieto),
                          AGENT_BROWSER_SOCKET_DIR=str(self.tmp / "sesiones"), XDG_CONFIG_HOME=str(self.tmp / "config"))
        self.addCleanup(self.volver)

    def volver(self):
        for k, v in self.antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        # por si una prueba falla a medias: nada vivo
        for f in [self.nieto, *(self.tmp / "sesiones").glob("*.pid")]:
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(f.read_text()), 9)
        subprocess.run(["rm", "-rf", str(self.tmp)], check=False)

    def correr(self, *argv: str) -> tuple[int, str, float]:
        salida = io.StringIO()
        t = time.monotonic()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            r = medir.main(list(argv), ab=str(self.ab), dev=[sys.executable, str(self.dev)], estado=self.estado)
        return r, salida.getvalue(), time.monotonic() - t

    def ordenes(self) -> list[dict]:
        return [json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []

    def nada_vivo(self):
        nieto = int(self.nieto.read_text())
        hasta = time.monotonic() + 3
        while medir.vivo(nieto) and time.monotonic() < hasta:
            time.sleep(0.05)
        self.assertFalse(medir.vivo(nieto), "quedó viva la página (un nieto de dev.py)")
        self.assertEqual(list((self.tmp / "sesiones").glob("*.pid")), [], "quedó vivo el navegador")
        self.assertEqual(list(self.estado.glob("*.json")), [], "quedó su archivo de estado")

    def test_falla_al_entrar_y_limpia(self):
        os.environ["FALSO_FALLA"] = "wait"
        r, salida, _ = self.correr("proyectos", "-s", ".x", "--paso", "2")
        self.assertEqual(r, 3)
        self.assertIn("falla de mentira", salida)
        ordenes = self.ordenes()
        self.assertEqual(ordenes[-1]["args"][-1], "close")
        sesion = {o["args"][o["args"].index("--session") + 1] for o in ordenes}
        self.assertEqual(sesion, {f"medir-{os.getpid()}"})
        self.nada_vivo()
        # la llave entró por la entrada estándar: ni en una orden ni en la salida
        self.assertTrue(any(LLAVE in o["stdin"] for o in ordenes))
        self.assertFalse(any(LLAVE in " ".join(o["args"]) for o in ordenes))
        self.assertNotIn(LLAVE, salida)

    def test_se_cuelga_y_el_tope_lo_corta(self):
        # un navegador que no contesta: el tope del paso lo corta, y `close` tampoco cierra: se mata el daemon
        os.environ.update(FALSO_CUELGA="eval", FALSO_CLOSE_NO="1")
        r, salida, dura = self.correr("proyectos", "-s", ".x", "--paso", "1", "--total", "20")
        self.assertEqual(r, 3)
        self.assertIn("no contestó", salida)
        self.assertLess(dura, 15)
        self.nada_vivo()

    def test_una_pantalla_que_no_llega_sigue_con_la_otra(self):
        # las órdenes de la pantalla contestan {ok: true}, sin medidas: llega, mide nada y sigue
        r, salida, _ = self.correr("proyectos", "calendario", "-s", ".x", "--json")
        datos = json.loads(salida)
        self.assertEqual([p["pantalla"] for p in datos["pantallas"]], ["pestana:proyectos", "pestana:calendario"])
        self.assertEqual(r, 0)
        self.nada_vivo()

    def test_limpia_lo_que_dejo_una_corrida_muerta(self):
        # una corrida que murió con kill -9: su página (un proceso) y su navegador siguen vivos
        resto, daemon = huerfano(), huerfano()
        self.addCleanup(lambda: [os.kill(p, 9) for p in (resto, daemon) if medir.vivo(p)])
        (self.tmp / "sesiones" / "medir-999999.pid").write_text(str(daemon))
        muerto = subprocess.Popen(["true"])
        muerto.wait()
        self.estado.mkdir()
        (self.estado / f"{muerto.pid}.json").write_text(json.dumps({"pid": muerto.pid, "sesion": "medir-999999",
                                                                    "procesos": [resto]}))
        # y la de otra corrida que sigue viva no se toca
        (self.estado / f"{os.getppid()}.json").write_text(json.dumps({"pid": os.getppid(), "sesion": "medir-vivo",
                                                                      "procesos": []}))
        os.environ["FALSO_CLOSE_NO"] = "1"
        limpiados = medir.limpiar_restos(str(self.ab), self.estado)
        self.assertEqual(limpiados, [f"{muerto.pid}.json"])
        self.assertFalse(medir.vivo(resto) or medir.vivo(daemon))
        self.assertTrue((self.estado / f"{os.getppid()}.json").exists())
        self.assertIn("close", [o["args"][-1] for o in self.ordenes() if "medir-999999" in o["args"]])


if __name__ == "__main__":
    import unittest

    unittest.main()
