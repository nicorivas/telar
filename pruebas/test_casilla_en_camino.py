"""Un mensaje de la casilla se da por entregado solo cuando la conversación muestra que entró.

El 14-nov, con la máquina cargada, Claude Code mató a los ganchos de la casilla a los 5 s: uno alcanzó a marcar el
mensaje como entregado antes de morir, Claude Code descartó su salida, y el mensaje se perdió. Aquí el gancho lo deja
en camino, y la corrida siguiente lo busca en la conversación: si no está, vuelve. Puede llegar dos veces (marcado
«otra vez», con el mismo id), nunca cero. Y los ganchos tienen que ser livianos: lo que importan, medido.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from comun import RAIZ, Prueba  # noqa: E402  (pone src/ en el camino)

from telar import casilla as m

UPS = "UserPromptSubmit"


def _un_pid_muerto() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class ConCasilla(Prueba):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = SimpleNamespace(estado=Path(self.tmp.name) / "estado")
        self.conversacion = Path(self.tmp.name) / "conversacion.jsonl"
        # una conversación con historia: lo de antes no cuenta, se busca en lo que se escriba después
        self.conversacion.write_text('{"type":"user","message":{"role":"user","content":"hola"}}\n' * 50)
        self.d = m.carpeta(self.config, "Faro")

    def entrar(self, salida: str) -> None:
        """Lo que hace Claude Code cuando acepta la salida del gancho: la deja en la conversación."""
        datos = json.loads(salida)
        texto = datos.get("reason") or datos["hookSpecificOutput"]["additionalContext"]
        fila = {"type": "attachment", "attachment": {"type": "hook_additional_context", "content": [texto]}}
        with self.conversacion.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    def envejecer(self, mid: str, segundos: float, pid: int | None = None) -> None:
        """Que el gancho que lo tomó lo haya tomado hace `segundos` (y, si se dice, que fuera otro proceso)."""
        f = self.d / m.CAMINO / f"{mid}.json"
        datos = json.loads(f.read_text())
        datos["entrega"]["hora"] -= segundos
        if pid is not None:
            datos["entrega"]["pid"] = pid
        f.write_text(json.dumps(datos))

    def estado_de(self, mid: str) -> str:
        for donde, ruta in (("pendiente", self.d / f"{mid}.json"), ("aviso", self.d / m.AVISOS / f"{mid}.json"),
                            ("camino", self.d / m.CAMINO / f"{mid}.json"),
                            ("entregado", self.d / "entregados" / f"{mid}.json")):
            if ruta.exists():
                return donde
        return "ninguno"


class EnCamino(ConCasilla):
    def test_imprimirlo_no_es_entregarlo(self):
        m.dejar(self.config, "Faro", {"id": "a1", "de": "Secretaría", "texto": "hola"})
        salida = m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion))
        self.assertIn("id a1]", salida)
        self.assertEqual(self.estado_de("a1"), "camino")
        # en camino no está pendiente: ni el aviso ni otro gancho lo vuelven a entregar mientras tanto
        self.assertEqual(m.pendientes(self.config, "Faro"), [])
        self.assertEqual(m.para_gancho(self.config, "Faro", "Stop", conversacion=str(self.conversacion)), "")
        # y llegar otra vez por el bus no lo duplica
        self.assertFalse(m.dejar(self.config, "Faro", {"id": "a1", "texto": "hola"}))

    def test_cuando_la_conversacion_lo_muestra_queda_entregado(self):
        m.dejar(self.config, "Faro", {"id": "a1", "de": "Secretaría", "texto": "hola"})
        self.entrar(m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion)))
        self.assertEqual(m.revisar(self.config, "Faro")["entraron"], ["a1"])
        self.assertEqual(self.estado_de("a1"), "entregado")

    def test_un_gancho_que_muere_despues_de_marcar_no_pierde_el_mensaje(self):
        """Lo del 14-nov, con un gancho de verdad: un proceso aparte toma el mensaje, imprime, y lo matan antes de
        que termine (Claude Code descarta lo que imprimió). La corrida siguiente lo vuelve a entregar."""
        m.dejar(self.config, "Faro", {"id": "a1", "de": "Secretaría", "texto": "el encargo de la mañana"})
        codigo = (
            "import sys, time; from pathlib import Path; from types import SimpleNamespace\n"
            "from telar import casilla\n"
            f"c = SimpleNamespace(estado=Path({str(self.config.estado)!r}))\n"
            f"print(casilla.para_gancho(c, 'Faro', 'UserPromptSubmit', '↯ mensaje nuevo', conversacion={str(self.conversacion)!r}), flush=True)\n"
            "time.sleep(60)\n")
        gancho = subprocess.Popen([sys.executable, "-c", codigo], stdout=subprocess.PIPE, text=True,
                                  env={**os.environ, "PYTHONPATH": str(RAIZ / "src")})
        try:
            impreso = gancho.stdout.readline()
            self.assertIn("el encargo de la mañana", impreso)
            self.assertEqual(self.estado_de("a1"), "camino")
            # mientras el gancho vive, lo suyo no se toca: todavía puede terminar bien
            self.assertEqual(m.revisar(self.config, "Faro", ahora=time.time() + m.GRACIA + 1)["volvieron"], [])
        finally:
            gancho.send_signal(signal.SIGKILL)
            gancho.wait()
            gancho.stdout.close()
        # lo mataron: nada de lo que imprimió entró a la conversación. Antes de la gracia, espera
        self.assertEqual(m.revisar(self.config, "Faro")["volvieron"], [])
        self.assertEqual(self.estado_de("a1"), "camino")
        self.envejecer("a1", m.GRACIA + 1)
        # el gancho siguiente (el Stop de ese turno) lo trae de vuelta y lo entrega, marcado «otra vez»
        salida = m.para_gancho(self.config, "Faro", "Stop", conversacion=str(self.conversacion))
        self.assertIn("el encargo de la mañana", salida)
        self.assertIn("id a1, otra vez]", salida)
        self.assertIn("no lo repitas", salida)
        self.entrar(salida)
        self.assertEqual(m.para_gancho(self.config, "Faro", UPS, "sigue", conversacion=str(self.conversacion)), "")
        self.assertEqual(self.estado_de("a1"), "entregado")

    def test_la_orden_del_gancho_deja_en_camino_y_la_siguiente_lo_recupera(self):
        """`telar agente casilla claude-code`, como lo corre Claude Code, en un proceso aparte: su salida se descarta
        (un gancho cancelado) y la corrida siguiente de la orden lo vuelve a entregar."""
        cfg = Path(self.tmp.name) / "config.toml"
        cfg.write_text(f'raiz = "{self.tmp.name}"\nestado = "{self.config.estado}"\n', encoding="utf-8")
        m.dejar(self.config, "Faro", {"id": "a1", "de": "Secretaría", "texto": "¿revisas la rama?"})
        entorno = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "TELAR_CONFIG": str(cfg), "TELAR_HILO": "Faro",
                   "CLAUDE_CODE_ENTRYPOINT": "cli"}

        def gancho(evento: str, prompt: str = "") -> str:
            carga = {"hook_event_name": evento, "prompt": prompt, "session_id": "s1",
                     "transcript_path": str(self.conversacion)}
            r = subprocess.run([sys.executable, "-m", "telar", "agente", "casilla", "claude-code"],
                               input=json.dumps(carga), capture_output=True, text=True, env=entorno, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.strip()

        self.assertIn("¿revisas la rama?", gancho(UPS, m.AVISO))  # …y Claude Code lo mató: no entra
        self.assertEqual(self.estado_de("a1"), "camino")
        self.envejecer("a1", m.GRACIA + 1)
        salida = gancho("Stop")
        self.assertEqual(json.loads(salida)["decision"], "block")
        self.assertIn("id a1, otra vez]", salida)
        self.entrar(salida)
        self.assertEqual(gancho(UPS, "hola"), "")
        self.assertEqual(self.estado_de("a1"), "entregado")

    def test_lo_que_tomo_un_gancho_que_no_alcanzo_a_anotarse_vuelve_pasado_el_tope(self):
        m.dejar(self.config, "Faro", {"id": "a1", "texto": "x"})
        (self.d / m.CAMINO).mkdir(parents=True)
        os.rename(self.d / "a1.json", self.d / m.CAMINO / "a1.json")  # tomado, sin su entrega anotada
        self.assertEqual(m.revisar(self.config, "Faro", ahora=time.time() + m.GRACIA + 1)["volvieron"], [])
        self.assertEqual(m.revisar(self.config, "Faro", ahora=time.time() + m.SIN_DUENO + 1)["volvieron"], ["a1"])
        self.assertEqual(self.estado_de("a1"), "pendiente")

    def test_un_pid_vivo_no_lo_retiene_para_siempre(self):
        m.dejar(self.config, "Faro", {"id": "a1", "texto": "x"})
        m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion))
        # el pid anotado es el de esta prueba, que sigue viva (como uno reciclado): pasado el tope, igual vuelve
        self.assertEqual(m.revisar(self.config, "Faro", ahora=time.time() + m.GRACIA + 1)["volvieron"], [])
        self.assertEqual(m.revisar(self.config, "Faro", ahora=time.time() + m.SIN_DUENO + 1)["volvieron"], ["a1"])

    def test_un_aviso_vuelve_a_esperar_entre_los_avisos(self):
        m.dejar(self.config, "Faro", {"id": "a1", "texto": "para que sepas", "modo": "aviso"})
        m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion))
        self.envejecer("a1", m.GRACIA + 1, pid=_un_pid_muerto())
        m.revisar(self.config, "Faro")
        self.assertEqual(self.estado_de("a1"), "aviso")

    def test_se_rinde_a_los_max_intentos_y_lo_anota(self):
        m.dejar(self.config, "Faro", {"id": "a1", "texto": "x"})
        muerto = _un_pid_muerto()
        for _ in range(m.MAX_INTENTOS):
            self.assertTrue(m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion)))
            self.envejecer("a1", m.GRACIA + 1, pid=muerto)
            m.revisar(self.config, "Faro")
        self.assertEqual(self.estado_de("a1"), "entregado")
        self.assertTrue(json.loads((self.d / "entregados" / "a1.json").read_text())["sin_confirmar"])

    def test_un_encargo_cerrado_no_vuelve(self):
        from telar import encargo

        m.dejar(self.config, "Faro", {"id": "a1", "de": "Secretaría", "texto": "haz x", "modo": "encargo",
                                      "encargo": "e-1a2b3c4d"})
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["estado"], "pedido")
        m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion))
        # en camino todavía no corre: corre cuando se ve que entró
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["estado"], "pedido")
        ruta = encargo._ruta(self.config, "objetos", "e-1a2b3c4d")
        e = json.loads(ruta.read_text())
        e["estado"] = "hecho"  # lo cerró igual (le llegó por otro lado)
        ruta.write_text(json.dumps(e))
        self.envejecer("a1", m.GRACIA + 1, pid=_un_pid_muerto())
        self.assertEqual(m.revisar(self.config, "Faro")["sin_confirmar"], ["a1"])
        self.assertEqual(self.estado_de("a1"), "entregado")

    def test_un_encargo_que_entra_queda_corriendo(self):
        from telar import encargo

        m.dejar(self.config, "Faro", {"id": "a1", "de": "Secretaría", "texto": "haz x", "modo": "encargo",
                                      "encargo": "e-1a2b3c4d"})
        self.entrar(m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion)))
        m.revisar(self.config, "Faro")
        self.assertEqual(encargo.leer(self.config, "e-1a2b3c4d")["estado"], "corriendo")

    def test_lo_de_tu_persona_tambien_lleva_su_id(self):
        m.dejar(self.config, "Faro", {"id": "p1", "tipo": "persona", "de": "la web", "texto": "¿y eso?",
                                      "creado": "2026-11-14T15:46:04"})
        salida = m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion))
        self.assertIn("[tu persona te escribe desde la web, 2026-11-14 15:46, id p1]", salida)
        self.entrar(salida)
        self.assertEqual(m.revisar(self.config, "Faro")["entraron"], ["p1"])

    def test_sin_conversacion_se_entrega_al_imprimir(self):
        """Un gancho sin `transcript_path` (otro agente, una prueba) no tiene dónde mirar: lo de siempre."""
        m.dejar(self.config, "Faro", {"id": "a1", "texto": "x"})
        m.para_gancho(self.config, "Faro", "Stop")
        self.assertEqual(self.estado_de("a1"), "entregado")

    def test_mudar_lleva_tambien_lo_que_estaba_en_camino(self):
        m.dejar(self.config, "Viejo", {"id": "a1", "texto": "x"})
        m.para_gancho(self.config, "Viejo", UPS, m.AVISO, conversacion=str(self.conversacion))
        self.assertEqual(m.mudar(self.config, "Viejo", "Faro"), 1)
        self.assertEqual(self.estado_de("a1"), "pendiente")
        self.assertEqual(m.en_camino(self.config, "Viejo"), [])


class LaCola(ConCasilla):
    def test_busca_desde_donde_iba_no_en_lo_de_antes(self):
        with self.conversacion.open("a") as f:
            f.write('{"x": "[mensaje de Secretaría, 2026-11-14 15:46, id a1]"}\n')
        desde = self.conversacion.stat().st_size
        self.assertTrue(m.visto(str(self.conversacion), 0, "a1"))
        self.assertFalse(m.visto(str(self.conversacion), desde, "a1"))
        with self.conversacion.open("a") as f:
            f.write('{"x": "[mensaje de Secretaría, 2026-11-14 15:46, id a1, otra vez]"}\n')
        self.assertTrue(m.visto(str(self.conversacion), desde, "a1"))

    def test_otro_id_que_empieza_igual_no_cuenta(self):
        with self.conversacion.open("a") as f:
            f.write('{"x": "[mensaje de Secretaría, 2026-11-14 15:46, id a12]"}\n')
        self.assertFalse(m.visto(str(self.conversacion), 0, "a1"))

    def test_una_cabecera_partida_entre_dos_trozos_se_encuentra(self):
        viejo = m.TROZO
        m.TROZO = 64
        self.addCleanup(setattr, m, "TROZO", viejo)
        texto = "x" * 50 + "[mensaje de Secretaría, 2026-11-14 15:46, id a1]"
        self.conversacion.write_text(texto)
        self.assertTrue(m.visto(str(self.conversacion), 0, "a1"))

    def test_sin_conversacion_no_lo_ve(self):
        self.assertFalse(m.visto(str(Path(self.tmp.name) / "no-existe.jsonl"), 0, "a1"))


class Leer(ConCasilla):
    def test_muestra_lo_que_espera_y_lo_da_por_entregado(self):
        m.dejar(self.config, "Faro", {"id": "a1", "de": "Secretaría", "texto": "uno"})
        m.para_gancho(self.config, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion))  # en camino
        m.dejar(self.config, "Faro", {"id": "a2", "de": "Base", "texto": "dos"})
        texto = m.leer(self.config, "Faro")
        self.assertIn("uno", texto)
        self.assertIn("dos", texto)
        self.assertEqual((self.estado_de("a1"), self.estado_de("a2")), ("entregado", "entregado"))
        self.assertEqual(m.leer(self.config, "Faro"), "")

    def test_la_orden_lo_muestra(self):
        import io
        from contextlib import redirect_stdout

        from telar import config as mod_config
        from telar.cli import Contexto
        from telar.ordenes import agente as orden

        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=self.config.estado)
        m.dejar(cfg, "Faro", {"id": "a1", "de": "Secretaría", "texto": "lo que no llegó"})
        os.environ["TELAR_HILO"] = "Faro"
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(orden.main(["casilla", "--leer"], Contexto(config=cfg)), 0)
        self.assertIn("lo que no llegó", salida.getvalue())
        salida = io.StringIO()
        with redirect_stdout(salida):
            orden.main(["casilla", "--leer"], Contexto(config=cfg))
        self.assertIn("No hay mensajes", salida.getvalue())


class ElMod(ConCasilla):
    def test_la_pregunta_del_mod_devuelve_lo_perdido_y_da_el_aviso(self):
        import io
        from contextlib import redirect_stdout

        from telar import config as mod_config
        from telar.cli import Contexto
        from telar.ordenes import agente as orden

        cfg = mod_config.Config(raiz=Path(self.tmp.name), estado=self.config.estado)
        m.dejar(cfg, "Faro", {"id": "a1", "de": "Secretaría", "texto": "hola"})
        m.para_gancho(cfg, "Faro", UPS, m.AVISO, conversacion=str(self.conversacion))

        def preguntar() -> dict:
            salida = io.StringIO()
            with redirect_stdout(salida):
                orden.main(["mod", "--hilo", "Faro"], Contexto(config=cfg))
            return json.loads(salida.getvalue())

        self.assertEqual(preguntar()["aviso"], "")  # en camino: todavía puede entrar
        self.envejecer("a1", m.GRACIA + 1, pid=_un_pid_muerto())
        self.assertTrue(preguntar()["aviso"].startswith(m.AVISO))


class LoQueImportan(Prueba):
    """Los ganchos corren en cada turno de cada hilo, y el mod pregunta cada 2 s: con la máquina cargada, lo que
    importan es lo que tardan (el 14-nov, 1 s solo en importar, por pydantic). Ninguno carga lo pesado."""

    PESADOS = ("pydantic", "asyncio", "telar.objetos", "telar.servicios", "telar.bus", "difflib", "tempfile")

    def test_los_ganchos_no_importan_lo_pesado(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.toml"
            cfg.write_text(f'raiz = "{tmp}"\nestado = "{tmp}/estado"\n[bus]\nurl = "nats://127.0.0.1:1"\n',
                           encoding="utf-8")
            conversacion = Path(tmp) / "c.jsonl"
            conversacion.write_text("{}\n")
            from telar import casilla

            c = SimpleNamespace(estado=Path(tmp) / "estado")
            entorno = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "TELAR_CONFIG": str(cfg), "TELAR_HILO": "Faro",
                       "CLAUDE_CODE_ENTRYPOINT": "cli"}
            casos = [
                (["agente", "casilla", "claude-code"], {"hook_event_name": UPS, "prompt": casilla.AVISO}),
                (["agente", "casilla", "claude-code"], {"hook_event_name": "Stop"}),
                (["agente", "mod", "--sesion", "s1"], None),
                (["agente", "evento", "claude-code"], {"hook_event_name": "PostToolUse", "tool_name": "Bash"}),
                # el nombre de antes, que corren los ganchos ya instalados hasta que se reinstalan
                (["agente", "aviso", "claude-code"], {"hook_event_name": "PostToolUse", "tool_name": "Bash"}),
                (["agente", "contexto", "claude-code"], {"hook_event_name": "SessionStart", "source": "startup"}),
            ]
            for argv, carga in casos:
                casilla.dejar(c, "Faro", {"id": casilla.nuevo_id(), "de": "Secretaría", "texto": "hola"})
                entrada = json.dumps({**carga, "session_id": "s1", "transcript_path": str(conversacion)}) if carga else ""
                r = subprocess.run([sys.executable, "-X", "importtime", "-m", "telar", *argv], input=entrada,
                                   capture_output=True, text=True, env=entorno, timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr[-500:])
                importados = {linea.split("|")[-1].strip() for linea in r.stderr.splitlines() if "|" in linea}
                with self.subTest(orden=" ".join(argv)):
                    self.assertEqual(sorted(importados & set(self.PESADOS)), [])
                    # que corrió de verdad: la orden misma no sale (la carga importlib.import_module), lo suyo sí
                    self.assertIn("telar.ordenes._comun", importados)
