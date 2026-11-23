"""Lo que carga el contexto de una conversación (telar.agente.carga, carga_claude y telar.conversacion.carga), con una
conversación de Claude Code inventada: qué va a cada grupo, cuánto pesa, qué resumió una compactación, y que el archivo
se lea de a poco."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from comun import Prueba  # noqa: E402  (pone src/ en el camino)

from telar import config as mod_config
from telar import conversacion as m
from telar.agente import carga as mod_carga
from telar.agente.carga_claude import LectorClaude, lee_bash

SID = "cccccccc-1111-2222-3333-444444444444"
CASA = "/casa/ana"
CARPETA = f"{CASA}/faro"
T = "2026-10-01T12:{:02d}:00Z"

# ── los registros, como los escribe Claude Code (inventados) ──


def adjunto(tipo: str, minuto: int, rendido: str | None = None, **campos) -> dict:
    d = {"type": "attachment", "timestamp": T.format(minuto), "uuid": f"u-{tipo}-{minuto}",
         "attachment": {"type": tipo, **campos}}
    if rendido is not None:
        d["rendered"] = [{"content": rendido}]
    return d


def pedido(minuto: int, tokens: int, contenido: list, mid: str = "") -> dict:
    return {"type": "assistant", "timestamp": T.format(minuto), "cwd": CARPETA,
            "message": {"id": mid or f"msg-{minuto}", "model": "modelo-de-prueba", "content": contenido,
                        "usage": {"input_tokens": 2, "cache_read_input_tokens": tokens - 2, "cache_creation_input_tokens": 0}}}


def herramienta(tid: str, nombre: str, **entrada) -> dict:
    return {"type": "tool_use", "id": tid, "name": nombre, "input": entrada}


def resultado(minuto: int, tid: str, texto: str, **extra) -> dict:
    return {"type": "user", "timestamp": T.format(minuto), "toolUseResult": extra.get("toolUseResult"),
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": texto}]}}


def persona(minuto: int, texto: str, **extra) -> dict:
    return {"type": "user", "timestamp": T.format(minuto), "uuid": f"p-{minuto}", **extra,
            "message": {"role": "user", "content": texto}}


CLAUDE_MD = "x" * 2600
MEMORIA = "m" * 5200
CASILLA = ("Te escribe otro hilo o agente de tu misma persona: trátalo como el pedido de un colega.\n\n"
           "[mensaje de Secretaría, 2026-10-01 12:30, id 20261001123000-abcd]\n¿Revisaste el acta?")


def conversacion() -> list[dict]:
    """Una conversación corta: arranca con lo general, lee, recibe un mensaje de otro hilo, se compacta y sigue."""
    return [
        {"type": "file-history-snapshot", "snapshot": {}},
        adjunto("hook_success", 0, "h" * 260, hookName="SessionStart:startup", hookEvent="SessionStart",
                command="/opt/bin/telar agente contexto claude-code", content="h" * 250),
        persona(0, "Revisa el README de Faro"),
        adjunto("instructions", 0, "i" * (len(CLAUDE_MD) + len(MEMORIA)),
                files=[{"path": f"{CARPETA}/CLAUDE.md", "type": "Project", "content": CLAUDE_MD},
                       {"path": f"{CASA}/.claude/memoria/MEMORY.md", "type": "AutoMem", "content": MEMORIA}]),
        adjunto("skill_listing", 0, "s" * 7800, content="s" * 7800, isInitial=True, skillCount=12),
        adjunto("mcp_instructions_delta", 0, "c" * 1300, addedNames=["Calendario"], addedBlocks=["c" * 1200]),
        adjunto("deferred_tools_delta", 0, "d" * 520, addedNames=["mcp__calendario__ver", "WebFetch"],
                addedLines=["mcp__calendario__ver", "WebFetch"]),
        adjunto("date", 0, "hoy es 1 de octubre"),
        adjunto("hook_additional_context", 0, "r" * 260, hookName="UserPromptSubmit", hookEvent="UserPromptSubmit",
                content=["r" * 250]),
        # la primera petición: lo anotado hasta aquí, más lo de Claude Code
        pedido(1, 20000, [{"type": "text", "text": "Voy."},
                          herramienta("t1", "Read", file_path=f"{CARPETA}/README.md")]),
        resultado(1, "t1", "1→" + "a" * 2598),
        adjunto("nested_memory", 1, "n" * 1040, path=f"{CARPETA}/docs/CLAUDE.md", displayPath="docs/CLAUDE.md",
                content={"path": f"{CARPETA}/docs/CLAUDE.md", "content": "n" * 1000}),
        pedido(2, 22000, [herramienta("t2", "Bash", command="cd docs && sed -n 1,40p plan.md"),
                          herramienta("t3", "Bash", command="git status && cat README.md"),
                          herramienta("t4", "Grep", pattern="acta", path=CARPETA)]),
        resultado(2, "t2", "b" * 1300),
        resultado(2, "t3", "g" * 520),
        resultado(2, "t4", "README.md:3"),
        persona(3, "otra cosa"),
        adjunto("hook_additional_context", 3, "r" * 260, hookName="UserPromptSubmit", hookEvent="UserPromptSubmit",
                content=["r" * 250]),
        adjunto("hook_additional_context", 3, CASILLA, hookName="UserPromptSubmit", hookEvent="UserPromptSubmit",
                content=[CASILLA]),
        pedido(4, 24000, [herramienta("t5", "Skill", skill="revisar")]),
        resultado(4, "t5", "Launching skill: revisar"),
        persona(4, f"Base directory for this skill: {CASA}/.claude/skills/revisar\n\n" + "k" * 1000,
                isMeta=True, sourceToolUseID="t5"),
        # el mismo mensaje de otro hilo, entregado al terminar: el aviso y su adjunto son uno
        persona(5, "Stop hook feedback:\n" + CASILLA, isMeta=True),
        {**adjunto("hook_blocking_error", 5, "Stop hook feedback:\n" + CASILLA, hookName="Stop",
                   blockingError={"blockingError": CASILLA, "command": "telar agente casilla claude-code"}), "parentUuid": "p-5"},
        pedido(5, 26000, [{"type": "text", "text": "Listo."}], mid="msg-5"),
        # lo de un subagente no es de este contexto
        {"type": "assistant", "isSidechain": True, "message": {"id": "sub", "usage": {"input_tokens": 999999}}},
    ]


def compactada() -> list[dict]:
    """Lo que sigue a `conversacion()` después de una compactación automática."""
    return [
        {"type": "system", "subtype": "compact_boundary", "timestamp": T.format(10),
         "compactMetadata": {"trigger": "auto", "preTokens": 26000, "postTokens": 9000}},
        {"type": "user", "timestamp": T.format(10), "isCompactSummary": True,
         "message": {"role": "user", "content": "Resumen: " + "z" * 2591}},
        adjunto("file", 10, "a" * 2600, filename=f"{CARPETA}/README.md", displayPath="README.md"),
        adjunto("instructions", 10, "i" * len(MEMORIA), reason="compaction",
                files=[{"path": f"{CASA}/.claude/memoria/MEMORY.md", "type": "AutoMem", "content": MEMORIA}]),
        persona(11, "sigamos"),
        pedido(11, 15000, [{"type": "text", "text": "Sigo."}]),
    ]


def leer(registros: list[dict]) -> dict:
    lector = LectorClaude()
    for r in registros:
        lector.registro(json.loads(json.dumps(r)))
    return lector.resumen()


def de(r: dict, grupo: str) -> dict:
    return {x["nombre"]: x for x in r["items"] if x["grupo"] == grupo}


def grupo(r: dict, clave: str) -> dict:
    return next(g for g in r["grupos"] if g["clave"] == clave)


class QueVaACadaGrupo(Prueba):
    def setUp(self):
        super().setUp()
        self.r = leer(conversacion())

    def test_lo_general_al_empezar(self):
        inicio = de(self.r, "inicio")
        self.assertEqual(inicio[f"{CARPETA}/CLAUDE.md"]["clase"], "claude_md")
        self.assertEqual(inicio[f"{CARPETA}/CLAUDE.md"]["caracteres"], len(CLAUDE_MD))
        self.assertEqual(inicio[f"{CASA}/.claude/memoria/MEMORY.md"]["clase"], "memoria")
        self.assertEqual(inicio["la lista de skills"]["caracteres"], 7800)
        self.assertEqual(inicio["telar agente contexto claude-code"]["clase"], "hook")
        # las instrucciones de un MCP y los nombres de sus herramientas, en una sola cosa
        self.assertEqual(inicio["el MCP Calendario"]["clase"], "mcp")
        self.assertEqual(sorted(inicio["el MCP Calendario"]["vias"]), ["los nombres de sus herramientas", "sus instrucciones"])
        # las herramientas a pedido que no son de un MCP son de Claude Code, como sus avisos
        claude = de(self.r, "claude")
        self.assertIn("los nombres de sus herramientas a pedido", claude)
        self.assertIn("la fecha", claude)

    def test_al_entrar_a_una_carpeta(self):
        self.assertEqual(de(self.r, "carpetas")[f"{CARPETA}/docs/CLAUDE.md"]["caracteres"], 1040)

    def test_lo_que_leyo_con_el_tamano_de_lo_que_le_llego(self):
        leido = de(self.r, "leido")
        self.assertEqual(leido[f"{CARPETA}/README.md"]["caracteres"], 2600)
        self.assertEqual(leido[f"{CARPETA}/README.md"]["vias"], ["Read"])
        self.assertEqual(leido[f"{CARPETA}/docs/plan.md"]["vias"], ["Bash"])
        self.assertEqual(leido[f"{CARPETA}/docs/plan.md"]["ruta"], f"{CARPETA}/docs/plan.md")
        self.assertEqual(leido[f"grep «acta» en {CARPETA}"]["clase"], "busqueda")
        self.assertEqual(leido["revisar"]["clase"], "skill")
        self.assertTrue(leido["revisar"]["ruta"].endswith("revisar/SKILL.md"))
        # un Bash que hace más que leer no se cuenta como leído: va a la conversación
        self.assertNotIn(f"{CARPETA}/README.md", [x for x in leido if leido[x].get("vias") == ["Bash"]])
        self.assertIn("lo que devolvió Bash", de(self.r, "conversacion"))

    def test_lo_que_se_repite_veces_por_tamano(self):
        r = de(self.r, "repetido")["UserPromptSubmit"]
        self.assertEqual((r["veces"], r["caracteres"]), (2, 520))

    def test_lo_de_otros_hilos_una_vez_por_entrega(self):
        hilos = de(self.r, "hilos")["la casilla de telar"]
        # por el hook de cada mensaje y por el Stop (su aviso y su adjunto cuentan una vez)
        self.assertEqual(hilos["veces"], 2)

    def test_el_total_es_el_medido_y_lo_de_claude_code_se_deduce(self):
        self.assertTrue(self.r["medido"])
        self.assertEqual(self.r["total"], 26000)
        self.assertEqual(self.r["al_empezar"], 20000)
        sistema = next(x for x in self.r["items"] if x["clase"] == "sistema")
        self.assertTrue(sistema["deducido"])
        self.assertGreater(sistema["tokens"], 10000)
        # los grupos suman el total: lo que no se anotó cae en la conversación
        self.assertEqual(sum(g["tokens"] for g in self.r["grupos"]), 26000)
        self.assertEqual(self.r["desde"]["que"], "inicio")
        self.assertEqual(self.r["modelo"], "modelo-de-prueba")

    def test_nunca_el_contenido(self):
        texto = json.dumps(self.r)
        for secreto in ("Revisa el README", "¿Revisaste el acta?", "Voy.", CLAUDE_MD[:50]):
            self.assertNotIn(secreto, texto)


class Compactacion(Prueba):
    def test_lo_de_antes_queda_resumido_y_aparte(self):
        r = leer(conversacion() + compactada())
        self.assertEqual(r["desde"], {"que": "compactacion", "hora": T.format(10), "como": "auto", "antes": 26000, "despues": 9000})
        self.assertEqual(r["compactaciones"], 1)
        self.assertEqual((r["total"], r["al_empezar"]), (15000, 15000))
        leido = de(r, "leido")
        readme = leido[f"{CARPETA}/README.md"]
        # vuelto a adjuntar al compactar: sigue en el contexto, y se sabe que antes entró por Read
        self.assertEqual(readme["veces"], 1)
        self.assertEqual(readme["antes"]["veces"], 1)
        self.assertIn("adjunto", readme["vias"])
        # lo que no volvió ya no está: solo en `antes`
        plan = leido[f"{CARPETA}/docs/plan.md"]
        self.assertEqual(plan["veces"], 0)
        self.assertEqual(plan["antes"]["veces"], 1)
        self.assertEqual(grupo(r, "repetido")["tokens"], 0)
        self.assertIn("el resumen de la compactación", de(r, "conversacion"))


class Comienzos(Prueba):
    def test_despues_de_un_clear(self):
        r = leer([adjunto("hook_success", 0, "h", hookName="SessionStart:clear", hookEvent="SessionStart", command="x"),
                  persona(0, "<command-name>/clear</command-name>")])
        self.assertEqual(r["desde"]["que"], "clear")

    def test_sin_uso_de_tokens_todo_es_estimado(self):
        r = leer([persona(0, "hola " * 100), adjunto("skill_listing", 0, "s" * 2600)])
        self.assertFalse(r["medido"])
        self.assertIsNone(r["al_empezar"])
        self.assertEqual(r["total"], sum(g["tokens"] for g in r["grupos"]))
        self.assertEqual(grupo(r, "inicio")["tokens"], round(2600 / mod_carga.CARACTERES_POR_TOKEN))


class LeerBash(Prueba):
    def test_lo_que_solo_lee(self):
        casos = {
            "cat a.md": ["/w/a.md"],
            "cd /x && cat a b": ["/x/a", "/x/b"],
            "sed -n 1,80p f.py": ["/w/f.py"],
            "head -50 /r/f": ["/r/f"],
            "tail -n +10 f": ["/w/f"],
            "cat f | grep x | head -5": ["/w/f"],
            "cat f 2>/dev/null": ["/w/f"],
            "nl -ba f | sed -n 1,5p": ["/w/f"],
        }
        for comando, esperado in casos.items():
            self.assertEqual(lee_bash(comando, "/w"), esperado, comando)

    def test_lo_que_hace_otra_cosa_no_se_adivina(self):
        for comando in ("cat f > g", "grep x f", "cat f | grep x otro", "sed -i s/a/b/ f", "ls", "cat <<EOF",
                        "cat f; rm f", "cat f && echo hola", "wc -l f", "cat 'sin cerrar"):
            self.assertIsNone(lee_bash(comando, "/w"), comando)


class DeAPoco(Prueba):
    """`telar.conversacion.carga`: lee el archivo, lo guarda, y cuando crece sigue desde donde quedó."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.config = mod_config.Config(raiz=self.base, estado=self.base / "estado")
        self.archivo = self.base / f"{SID}.jsonl"
        self.lectores: list[LectorClaude] = []

        def nuevo():
            self.lectores.append(LectorClaude())
            return self.lectores[-1]

        agente = SimpleNamespace(nombre="claude-code", archivo_de=lambda sid: self.archivo if sid == SID else None, carga=nuevo)
        parche = mock.patch.object(m, "_agente", return_value=agente)
        parche.start()
        self.addCleanup(parche.stop)
        m._cache_carga.clear()
        self.addCleanup(m._cache_carga.clear)

    def escribir(self, registros, modo="w", cola=""):
        with open(self.archivo, modo, encoding="utf-8") as f:
            f.write("".join(json.dumps(r) + "\n" for r in registros) + cola)

    def test_sigue_desde_donde_quedo(self):
        registros = conversacion()
        self.escribir(registros[:12])
        sid, r1 = m.carga(self.config, [SID])
        self.assertEqual(sid, SID)
        # una línea a medio escribir no se lee todavía
        mitad = json.dumps(registros[12])
        self.escribir([], "a", cola=mitad[:20])
        m.carga(self.config, [SID])
        self.escribir([], "a", cola=mitad[20:] + "\n")
        self.escribir(registros[13:], "a")
        _, r2 = m.carga(self.config, [SID])
        self.assertEqual(len(self.lectores), 1)  # el mismo lector, con lo nuevo
        self.assertEqual(r2, leer(registros))
        self.assertNotEqual(r1["total"], r2["total"])

    def test_si_el_archivo_se_achica_se_lee_de_nuevo(self):
        self.escribir(conversacion())
        m.carga(self.config, [SID])
        self.escribir(conversacion()[:5])
        m.carga(self.config, [SID])
        self.assertEqual(len(self.lectores), 2)

    def test_un_agente_que_no_sabe(self):
        self.escribir(conversacion())
        agente = SimpleNamespace(nombre="otro", archivo_de=lambda sid: self.archivo, carga=lambda: None)
        with mock.patch.object(m, "_agente", return_value=agente):
            with self.assertRaises(m.ErrorDeConversacion) as e:
                m.carga(self.config, [SID])
        self.assertIn("no dice qué carga", str(e.exception))

    def test_sin_conversacion(self):
        with self.assertRaises(m.ErrorDeConversacion):
            m.carga(self.config, [])
        with self.assertRaises(m.ErrorDeConversacion):
            m.carga(self.config, ["dddddddd-1111-2222-3333-444444444444"])


class Texto(Prueba):
    def test_la_orden_en_la_terminal(self):
        from telar.ordenes.hilo import como_texto_carga

        r = leer(conversacion())
        texto = como_texto_carga({**r, "hilo": "Faro", "carpeta": CARPETA, "casa": CASA})
        self.assertIn("Faro: 26,0 k tokens", texto)
        self.assertIn("al empezar", texto)
        self.assertIn("README.md", texto)
        self.assertIn("~/.claude/memoria/MEMORY.md", texto)


class ElServicio(Prueba):
    """`telar.servicios.carga`: el hilo, su conversación, el veto de otra máquina, y por el bus."""

    def correr(self, sesiones=(SID,), de_otra=False, no_leer=(), maquina=""):
        from telar.servicios import carga as servicio

        hilo = SimpleNamespace(nombre="Faro", vinculo=CARPETA, sesiones=sesiones)
        tel = SimpleNamespace(estado=SimpleNamespace(vinculos=lambda: {"Faro": "faro"}))
        config = SimpleNamespace(agente=SimpleNamespace(nombre="claude-code"), bus=SimpleNamespace(no_leer=no_leer),
                                 puerta=SimpleNamespace(no_leer=()))
        ctx = SimpleNamespace(config=config)
        with mock.patch("telar.ordenes._comun.tejer", return_value=tel), \
                mock.patch("telar.ordenes._comun.resolver", return_value=(hilo, "")), \
                mock.patch("telar.conversacion.carga", return_value=(SID, leer(conversacion()))), \
                mock.patch("telar.bus.hay_bus", return_value=bool(maquina)), \
                mock.patch("telar.bus.maquina", return_value="laptop"), \
                mock.patch("telar.bus.pedir", side_effect=lambda c, a, verbo, datos, espera: servicio.para_otra(ctx, datos)):
            return servicio.de_hilo(ctx, "Faro", de_otra=de_otra, maquina=maquina)

    def test_lo_del_hilo_con_su_carpeta(self):
        r = self.correr()
        self.assertEqual((r.hilo, r.conversacion, r.agente, r.carpeta), ("Faro", SID, "claude-code", CARPETA))
        self.assertEqual(r.total, 26000)
        self.assertTrue(r.items)

    def test_sin_conversacion_lo_dice(self):
        from telar.servicios import ErrorDeServicio

        with self.assertRaises(ErrorDeServicio) as e:
            self.correr(sesiones=())
        self.assertIn("no se sabe qué cargó", str(e.exception))

    def test_de_otra_maquina_por_el_bus_y_su_veto(self):
        from telar.servicios import ErrorDeServicio

        r = self.correr(maquina="servidor")
        self.assertEqual((r.maquina, r.total), ("servidor", 26000))
        with self.assertRaises(ErrorDeServicio) as e:
            self.correr(maquina="servidor", no_leer=("faro",))
        self.assertEqual(e.exception.codigo, 403)
