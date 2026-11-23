"""Lo que carga el contexto de una conversación de Claude Code, leído de su `.jsonl` (telar.agente.carga).

Claude Code guarda en la conversación, además de los mensajes, lo que le agrega al contexto sin que nadie lo pida: un
registro `attachment` por cosa, con lo que el modelo vio (`rendered`). Los que se miran aquí (y cambian entre
versiones de Claude Code: un tipo que no se conoce va a «Claude Code», con su nombre):

    instructions             los CLAUDE.md y el índice de la memoria que cargó al empezar (`files`)
    nested_memory            el CLAUDE.md de una subcarpeta, que se carga al leer algo ahí
    dynamic_skill            las skills de una subcarpeta
    hook_success             lo que imprimió un hook de inicio (SessionStart)
    hook_additional_context  lo que agrega un hook en cada mensaje (UserPromptSubmit) o herramienta (PostToolUse)
    hook_blocking_error      lo que un hook Stop le devuelve al terminar
    skill_listing            la lista de skills
    mcp_instructions_delta   las instrucciones de cada servidor MCP
    deferred_tools_delta     los nombres de las herramientas que se cargan a pedido (por servidor MCP)
    agent_listing_delta      los tipos de subagente
    session_context          el estado de git y los datos de la sesión
    invoked_skills           las skills usadas, que se vuelven a adjuntar al compactar
    file, compact_file_reference, edited_text_file   archivos que se vuelven a adjuntar (o que cambiaron afuera)
    queued_command           un mensaje que llegó mientras trabajaba: de otra sesión (`origin.kind` peer) o no

Y en los mensajes: los `tool_use` de Read, Grep y Glob, y los de Bash que solo leen archivos (`cat`, `head`, `tail`,
`sed -n`, `nl`, con filtros detrás de un `|`), cada uno con el tamaño de su resultado; la skill que se carga (el
mensaje `isMeta` que empieza con «Base directory for this skill:»); los mensajes de otros hilos que entrega la casilla
de telar (por un hook); el uso de tokens de cada pedido (`message.usage`); y los registros `system` que marcan una
compactación (`compact_boundary`). Lo de un subagente (`isSidechain`) no es de este contexto.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path

from telar.agente.carga import Carga

#: los registros que no dicen nada del contexto: se saltan sin leerlos (los pedidos enteros que Claude Code guarda
#: para depurar pesan más que todo lo demás)
SIN_LEER = (b'{"type":"api-request', b'{"type":"file-history', b'{"type":"last-prompt"', b'{"type":"ai-title"',
            b'{"type":"mode"', b'{"type":"atis-latch"', b'{"type":"permission-mode"', b'{"type":"session-owner"',
            b'{"type":"queue-operation"', b'{"type":"pr-link"', b'{"type":"frame-link"', b'{"type":"tools-used"',
            b'{"type":"bridge-session"', b'{"type":"history-suppression"', b'{"type":"cost-state"')

#: lo que lee archivos en un Bash, y lo que solo filtra lo que le llega por un `|`
LEEN = ("cat", "head", "tail", "sed", "nl", "less", "more", "bat")
FILTRAN = ("head", "tail", "grep", "rg", "sed", "wc", "sort", "uniq", "cut", "awk", "tr", "nl", "column", "fold", "less")

#: una imagen, en tokens, si no se sabe su tamaño (la que Claude Code achica al máximo que manda)
IMAGEN = 1600

#: los avisos de Claude Code que no son ni archivos ni hooks: su nombre para mostrarlos
AVISOS = {"date": "la fecha", "environment": "el entorno", "model": "el modelo", "auto_mode": "el modo automático",
          "total_tokens_reminder": "el aviso de tokens", "silent_turn_reminder": "el aviso de turno silencioso",
          "command_permissions": "los permisos de un comando", "task_status": "el estado de una tarea",
          "credential_org": "la organización", "remote_session_change": "la sesión remota",
          "read_truncation_notice": "un archivo leído a medias", "skill_mention": "una skill mencionada",
          "thinking_drop": "el razonamiento que se soltó"}

#: lo que es cada parte de la conversación, para mostrarla
ESCRIBIO = "lo que escribió la persona"
RESPONDIO = "lo que respondió el agente"
PIDIO = "las llamadas a herramientas"
OTROS = "avisos y lo demás"

_BASE_SKILL = re.compile(r"Base directory for this skill:\s*(\S+)")


def _texto(contenido) -> tuple[int, int]:
    """(caracteres, tokens de imágenes) de un contenido de mensaje o de resultado de herramienta."""
    if isinstance(contenido, str):
        return len(contenido), 0
    chars = fijos = 0
    if isinstance(contenido, list):
        for x in contenido:
            if not isinstance(x, dict):
                continue
            if x.get("type") == "text":
                chars += len(str(x.get("text", "")))
            elif x.get("type") == "image":
                fijos += IMAGEN
            elif x.get("type") == "tool_reference":
                chars += len(str(x.get("tool_name", "")))
            else:
                chars += len(json.dumps(x, ensure_ascii=False)) if x.get("type") != "thinking" else 0
    return chars, fijos


def _imagen(resultado) -> int:
    """Los tokens de una imagen leída, por sus medidas si Claude Code las anotó (ancho × alto / 750)."""
    try:
        dim = resultado["file"]["dimensions"]
        return max(1, round(int(dim["displayWidth"]) * int(dim["displayHeight"]) / 750))
    except (KeyError, TypeError, ValueError):
        return IMAGEN


def _renderizado(d: dict) -> int:
    """Lo que el modelo vio de un adjunto: `rendered`, si está; si no, nada (no entró como texto)."""
    r = d.get("rendered")
    if isinstance(r, list):
        return sum(len(str(x.get("content", ""))) for x in r if isinstance(x, dict))
    if isinstance(r, str):
        return len(r)
    return 0


def _servidor(nombre: str) -> str:
    """Un servidor MCP por su nombre, como lo nombran sus instrucciones («claude.ai Google Drive») o sus herramientas
    (`mcp__claude_ai_Google_Drive__…`): los dos van a la misma cosa."""
    return re.sub(r"[^a-z0-9]+", "_", nombre.casefold()).strip("_")


def _abrible(ruta: str) -> str:
    """La ruta para abrir un archivo: no la de un patrón (`docs/*.md`), que no es un archivo."""
    return "" if any(c in ruta for c in "*?[") else ruta


def _corto(comando: str) -> str:
    """Un comando de hook para mostrarlo: sin la ruta de su ejecutable ni comillas, y no muy largo."""
    partes = comando.strip().split()
    if partes and "/" in partes[0] and not partes[0].startswith("$"):
        partes[0] = os.path.basename(partes[0])
    texto = " ".join(partes).replace('"', "")
    texto = re.sub(r"\$\{CLAUDE_PLUGIN_ROOT\}/", "…/", texto)
    return texto if len(texto) <= 70 else texto[:69] + "…"


def lee_bash(comando: str, carpeta: str = "") -> list[str] | None:
    """Los archivos que lee un comando de Bash, si es solo leer: `cat a b`, `sed -n 1,80p x`, `head -50 x`,
    `cd d && cat x`, `cat x | grep y`, `cat x 2>/dev/null`. None si hace cualquier otra cosa: lo que no se sabe sin
    adivinar, no se cuenta como leído. Las rutas relativas, desde `carpeta` (o la del `cd`)."""
    try:
        lexer = shlex.shlex(comando, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        palabras = list(lexer)
    except ValueError:
        return None
    # lo que solo apaga o junta los errores no cambia lo que se lee: «2>/dev/null», «2>&1»
    limpias: list[str] = []
    i = 0
    while i < len(palabras):
        if palabras[i] == "2" and palabras[i + 1:i + 3] in ([">", "/dev/null"], [">&", "1"]):
            i += 3
            continue
        limpias.append(palabras[i])
        i += 1
    # en tramos (los que separan && y ;) y, dentro de cada uno, los segmentos de un |
    tramos: list[list[list[str]]] = []
    tramo: list[list[str]] = [[]]
    for p in limpias + [";"]:
        if p in ("&&", ";"):
            tramos.append(tramo)
            tramo = [[]]
        elif p == "|":
            tramo.append([])
        elif set(p) <= set("();<>|&"):
            return None  # una redirección, un subshell, algo en segundo plano: ya no es solo leer
        else:
            tramo[-1].append(p)
    archivos: list[str] = []
    donde = carpeta
    for t in tramos:
        if not any(t):
            continue
        if any(not seg for seg in t):
            return None
        primero = t[0]
        if primero[0] == "cd" and len(t) == 1 and len(primero) <= 2:
            if len(primero) == 2:
                destino = os.path.expanduser(primero[1])
                donde = destino if destino.startswith("/") else os.path.join(donde, destino)
            continue
        leidos = _lee(primero)
        if not leidos or any(not _filtra(seg) for seg in t[1:]):
            return None
        for a in leidos:
            a = os.path.expanduser(a)
            archivos.append(a if a.startswith("/") or not donde else os.path.normpath(os.path.join(donde, a)))
    return archivos or None


def _lee(seg: list[str]) -> list[str] | None:
    """Los archivos de un `cat`, `head`, `tail`, `sed -n` o `nl` sueltos; None si es otra cosa."""
    orden, args = os.path.basename(seg[0]), seg[1:]
    if orden not in LEEN:
        return None
    if orden == "sed":
        # solo `sed -n <guion> archivo…`: el que imprime lo que se le pide y no cambia nada
        if "-n" not in args or any(a.startswith(("-i", "-e", "-f", "--")) for a in args):
            return None
        resto = [a for a in args if a != "-n"]
        return [a for a in resto[1:] if not a.startswith("-")] or None
    archivos, saltar = [], False
    for a in args:
        if saltar:
            saltar = False
        elif orden in ("head", "tail") and a in ("-n", "-c"):
            saltar = True
        elif not a.startswith("-") and not (orden in ("head", "tail") and a.startswith("+")):
            archivos.append(a)
    return archivos or None


def _filtra(seg: list[str]) -> bool:
    """Si lo que va detrás de un `|` solo filtra lo que le llega, sin leer un archivo propio (`grep x otro.txt` no)."""
    orden = os.path.basename(seg[0])
    if orden not in FILTRAN:
        return False
    sueltos = [a for a in seg[1:] if not a.startswith("-")]
    if orden in ("grep", "rg", "sed", "awk"):
        return len(sueltos) <= 1  # el patrón o el guion
    if orden in ("head", "tail"):
        return all(a.isdigit() or a.startswith("+") for a in sueltos)
    if orden in ("tr", "cut"):
        return True  # sus argumentos son conjuntos y campos, no archivos
    return not sueltos


class LectorClaude:
    """Lee los registros de una conversación, uno por uno y en orden, y anota en su `Carga`. Puede seguir leyendo
    cuando la conversación crece: lo que espera (una herramienta sin resultado todavía) queda pendiente."""

    def __init__(self) -> None:
        self.carga = Carga()
        #: id de tool_use → lo que se anota cuando llegue su resultado
        self.pendientes: dict[str, tuple] = {}
        #: los mensajes del modelo ya contados (un mensaje viene en varios registros, con el mismo uso)
        self.ultimo_mensaje = ""
        #: los «Stop hook feedback» ya contados: el adjunto que los repite no se cuenta dos veces
        self.stop_vistos: set[str] = set()
        self.empezo = False

    def saltar(self, linea: bytes) -> bool:
        return linea.startswith(SIN_LEER)

    def resumen(self) -> dict:
        return self.carga.resumen()

    # ── un registro ──

    def registro(self, d: dict) -> None:
        if not isinstance(d, dict) or d.get("isSidechain"):
            return
        tipo, hora = d.get("type"), str(d.get("timestamp") or "")
        self.carga.hora(hora)
        if tipo == "attachment":
            self._adjunto(d, hora)
        elif tipo == "system":
            if d.get("subtype") == "compact_boundary":
                m = d.get("compactMetadata") or {}
                self.carga.compactar(hora, como=str(m.get("trigger") or ""), antes=int(m.get("preTokens") or 0),
                                     despues=int(m.get("postTokens") or 0))
                self.pendientes.clear()
        elif tipo == "assistant":
            self._asistente(d, hora)
        elif tipo == "user":
            self._usuario(d, hora)

    def _asistente(self, d: dict, hora: str) -> None:
        m = d.get("message") or {}
        if not isinstance(m, dict):
            return
        u = m.get("usage") or {}
        if isinstance(u, dict) and m.get("id") != self.ultimo_mensaje:
            entrada = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            if entrada:
                self.ultimo_mensaje = m.get("id") or ""
                self.carga.uso(entrada, hora, str(m.get("model") or ""))
        for x in m.get("content") or []:
            if not isinstance(x, dict):
                continue
            if x.get("type") == "text":
                self.carga.dijo(len(str(x.get("text", ""))), RESPONDIO, hora)
            elif x.get("type") == "tool_use":
                entrada = x.get("input") if isinstance(x.get("input"), dict) else {}
                nombre = str(x.get("name", ""))
                self.carga.dijo(len(json.dumps(entrada, ensure_ascii=False)), PIDIO, hora)
                if x.get("id"):
                    lo = self._que_lee(nombre, entrada, str(d.get("cwd") or ""))
                    self.pendientes[str(x["id"])] = lo if lo is not None else ("", [], nombre)

    def _que_lee(self, nombre: str, e: dict, carpeta: str):
        """Lo que se anotará cuando llegue el resultado: (clase, [(nombre, ruta)], vía); None si no lee."""
        if nombre == "Read" and e.get("file_path"):
            ruta = str(e["file_path"])
            return ("archivo", [(ruta, _abrible(ruta))], "Read")
        if nombre in ("Grep", "Glob") and e.get("pattern"):
            donde = str(e.get("path") or "")
            texto = f"{nombre.lower()} «{e['pattern']}»" + (f" en {donde}" if donde else "")
            return ("busqueda", [(texto, "")], nombre)
        if nombre == "Bash" and e.get("command"):
            archivos = lee_bash(str(e["command"]), carpeta)
            if archivos:
                return ("archivo", [(a, _abrible(a)) for a in archivos], "Bash")
        if nombre == "Skill" and e.get("skill"):
            return ("skill-pedida", [(str(e["skill"]).lstrip("/"), "")], "Skill")
        return None

    def _usuario(self, d: dict, hora: str) -> None:
        m = d.get("message") or {}
        contenido = m.get("content") if isinstance(m, dict) else None
        if d.get("isCompactSummary"):
            chars, _ = _texto(contenido)
            self.carga.agregar("conversacion", "resumen", "el resumen de la compactación", chars, hora)
            return
        if isinstance(contenido, str) or (d.get("isMeta") and isinstance(contenido, list)):
            texto = contenido if isinstance(contenido, str) else " ".join(
                str(x.get("text", "")) for x in contenido if isinstance(x, dict) and x.get("type") == "text")
            self._texto_de_usuario(d, texto, hora, contenido)
            return
        if not isinstance(contenido, list):
            return
        for x in contenido:
            if not isinstance(x, dict):
                continue
            if x.get("type") == "tool_result":
                chars, fijos = _texto(x.get("content"))
                lo = self.pendientes.pop(str(x.get("tool_use_id", "")), None) or ("", [], "")
                clase, cosas, via = lo
                if not cosas or x.get("is_error") or clase == "skill-pedida":
                    self.carga.dijo(chars + fijos * 3, f"lo que devolvió {via}" if via else "lo que devolvieron las herramientas", hora)
                    continue
                if fijos and clase == "archivo":
                    clase, fijos = "imagen", _imagen(d.get("toolUseResult"))
                grupo = "leido"
                for nombre, ruta in cosas:
                    self.carga.agregar(grupo, clase, nombre, chars // len(cosas), hora, ruta=ruta,
                                       fijos=fijos // len(cosas), via=via)
            elif x.get("type") == "text":
                self.carga.dijo(len(str(x.get("text", ""))), OTROS, hora)

    def _texto_de_usuario(self, d: dict, texto: str, hora: str, contenido) -> None:
        from telar import casilla

        chars, _ = _texto(contenido)
        if not self.empezo and not d.get("isMeta"):
            self.empezo = True
            if "<command-name>/clear</command-name>" in texto:
                self.carga.empezo("clear", hora)
        base = _BASE_SKILL.search(texto[:400]) if d.get("isMeta") else None
        if base:
            dir_skill = base.group(1)
            nombre = os.path.basename(dir_skill.rstrip("/"))
            self.carga.agregar("leido", "skill", nombre, chars, hora, ruta=str(Path(dir_skill) / "SKILL.md"),
                               via="Skill" if d.get("sourceToolUseID") else "/" + nombre, clave=f"skill:{nombre}")
            return
        if d.get("isMeta") and texto.startswith("Stop hook feedback"):
            self.stop_vistos.add(str(d.get("uuid") or ""))
            self._de_hook(texto, chars, hora, "Stop")
            return
        if d.get("isMeta") and texto.startswith("Another Claude session"):
            self.carga.agregar("hilos", "sesion", "otra sesión de Claude Code", chars, hora)
            return
        de = casilla.de_entrega(texto)
        if de == "hilos":
            self.carga.agregar("hilos", "mensaje", "la casilla de telar", chars, hora)
            return
        self.carga.dijo(chars, OTROS if d.get("isMeta") else ESCRIBIO, hora)

    def _de_hook(self, texto: str, chars: int, hora: str, nombre: str) -> None:
        """Lo que agregó un hook a mitad de la conversación: de otros hilos si es la casilla de telar; de la persona,
        a la conversación; lo demás se repite."""
        from telar import casilla

        de = casilla.de_entrega(texto)
        if de == "hilos":
            self.carga.agregar("hilos", "mensaje", "la casilla de telar", chars, hora)
        elif de == "persona":
            self.carga.dijo(chars, ESCRIBIO, hora)
        else:
            self.carga.agregar("repetido", "hook", nombre, chars, hora)

    def _adjunto(self, d: dict, hora: str) -> None:
        a = d.get("attachment") or {}
        if not isinstance(a, dict):
            return
        t = str(a.get("type") or "")
        n = _renderizado(d)
        agregar = self.carga.agregar
        if t == "instructions":
            archivos = [f for f in a.get("files") or [] if isinstance(f, dict)]
            largos = [len(str(f.get("content", ""))) for f in archivos]
            suma = sum(largos) or 1
            for f, largo in zip(archivos, largos):
                tipo = str(f.get("type") or "")
                ruta = str(f.get("path") or "")
                clase = "memoria" if tipo == "AutoMem" else "claude_md"
                agregar("inicio", clase, ruta or tipo, round(n * largo / suma) if n else largo, hora, ruta=ruta)
        elif t == "nested_memory":
            ruta = str(a.get("path") or "")
            agregar("carpetas", "claude_md", ruta or str(a.get("displayPath") or ""), n, hora, ruta=ruta)
        elif t == "dynamic_skill":
            nombre = str(a.get("displayPath") or a.get("skillDir") or "")
            agregar("carpetas", "skills", f"las skills de {nombre}", n, hora, ruta=str(a.get("skillDir") or ""),
                    clave=f"skills:{nombre}")
        elif t == "skill_listing":
            agregar("inicio", "skills", "la lista de skills", n, hora, clave="lista-skills")
        elif t == "mcp_instructions_delta":
            nombres = [str(x) for x in a.get("addedNames") or []]
            bloques = [len(str(x)) for x in a.get("addedBlocks") or []]
            if nombres and len(bloques) == len(nombres):
                suma = sum(bloques) or 1
                for nombre, largo in zip(nombres, bloques):
                    clave = f"mcp:{_servidor(nombre)}"
                    agregar("inicio", "mcp", f"el MCP {nombre}", round(n * largo / suma), hora, clave=clave, via="sus instrucciones")
                    self.carga.renombrar("inicio", "mcp", clave, f"el MCP {nombre}")
            elif n:
                agregar("inicio", "mcp", "instrucciones de los MCP", n, hora, clave="mcp:", via="sus instrucciones")
        elif t == "deferred_tools_delta":
            self._herramientas(a, n, hora)
        elif t == "agent_listing_delta":
            agregar("inicio", "agentes", "los tipos de subagente", n, hora, clave="agentes")
        elif t == "session_context":
            claves = sorted((a.get("context") or {}).keys()) if isinstance(a.get("context"), dict) else []
            nombre = "el estado de git" if "gitStatus" in claves else "los datos de la sesión"
            agregar("inicio", "git", nombre, n, hora, clave="sesion")
        elif t == "hook_success":
            nombre = str(a.get("hookName") or "")
            if n and nombre.startswith("SessionStart"):
                if not self.empezo and ":" in nombre:
                    fuente = nombre.split(":", 1)[1]
                    self.carga.empezo({"clear": "clear", "resume": "retomada"}.get(fuente, "inicio"), hora)
                agregar("inicio", "hook", _corto(str(a.get("command") or nombre)), n, hora, clave=f"hook:{a.get('command') or nombre}")
            elif n:
                agregar("repetido", "hook", _corto(str(a.get("command") or nombre)), n, hora, clave=f"hook:{a.get('command') or nombre}")
        elif t == "hook_additional_context":
            nombre = str(a.get("hookName") or a.get("hookEvent") or "hook")
            contenido = a.get("content")
            texto = "\n".join(str(x) for x in contenido) if isinstance(contenido, list) else str(contenido or "")
            if str(a.get("hookEvent") or "").startswith("SessionStart"):
                agregar("inicio", "hook", nombre, n or len(texto), hora, clave=f"hook:{nombre}")
            else:
                self._de_hook(texto, n or len(texto), hora, nombre)
        elif t == "hook_blocking_error":
            if str(d.get("parentUuid") or "") in self.stop_vistos:
                return  # el mismo que el «Stop hook feedback» de recién
            e = a.get("blockingError")
            texto = str(e.get("blockingError", "")) if isinstance(e, dict) else str(e or "")
            self._de_hook(texto, n or len(texto), hora, str(a.get("hookName") or "hook"))
        elif t == "invoked_skills":
            skills = [s for s in a.get("skills") or [] if isinstance(s, dict)]
            largos = [len(str(s.get("content", ""))) for s in skills]
            suma = sum(largos) or 1
            for s, largo in zip(skills, largos):
                nombre = str(s.get("name") or "")
                agregar("leido", "skill", nombre, round(n * largo / suma) if n else largo, hora,
                        ruta=str(s.get("path") or ""), via="al compactar", clave=f"skill:{nombre}")
        elif t in ("file", "compact_file_reference", "edited_text_file"):
            ruta = str(a.get("filename") or a.get("displayPath") or "")
            via = {"file": "adjunto", "compact_file_reference": "al compactar", "edited_text_file": "cambió afuera"}[t]
            agregar("leido", "archivo", ruta, n, hora, ruta=ruta, via=via)
        elif t == "queued_command":
            origen = (a.get("origin") or {}).get("kind") if isinstance(a.get("origin"), dict) else ""
            if origen == "peer":
                agregar("hilos", "sesion", "otra sesión de Claude Code", n, hora)
            elif a.get("commandMode") == "prompt":
                self.carga.dijo(n, ESCRIBIO, hora)
            else:
                self.carga.dijo(n, "los avisos de tareas de fondo", hora)
        elif n:
            agregar("claude", "aviso", AVISOS.get(t, t), n, hora, clave=f"aviso:{t}")

    def _herramientas(self, a: dict, n: int, hora: str) -> None:
        """Los nombres de las herramientas que se cargan a pedido, por servidor MCP (`mcp__<servidor>__…`)."""
        nombres = [str(x) for x in a.get("addedNames") or []]
        lineas = [len(str(x)) for x in a.get("addedLines") or []]
        if not nombres or not n:
            if n:
                self.carga.agregar("claude", "herramientas", "los nombres de sus herramientas a pedido", n, hora, clave="herr:")
            return
        if len(lineas) != len(nombres):
            lineas = [len(x) for x in nombres]
        por: dict[str, int] = {}
        for nombre, largo in zip(nombres, lineas):
            servidor = nombre.split("__")[1] if nombre.startswith("mcp__") and nombre.count("__") >= 2 else ""
            por[servidor] = por.get(servidor, 0) + largo
        suma = sum(por.values()) or 1
        for servidor, largo in por.items():
            parte = round(n * largo / suma)
            if servidor:
                # con las instrucciones del mismo servidor, en una sola cosa: lo que ese MCP le cuesta a todo hilo
                self.carga.agregar("inicio", "mcp", f"el MCP {servidor}", parte, hora, clave=f"mcp:{_servidor(servidor)}",
                                   via="los nombres de sus herramientas")
            else:
                self.carga.agregar("claude", "herramientas", "los nombres de sus herramientas a pedido", parte, hora, clave="herr:")
