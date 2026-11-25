"""Dormir un hilo inactivo: cerrar su agente y dejar su ventana, que lo retoma cuando se lo necesita.

Un Claude Code quieto ocupa lo mismo que uno que trabaja (unos 300 MB): once hilos abiertos son 3 GB, en un laptop de
16 y en un servidor de 7. La mayoría está quieta casi todo el día. Dormir es cerrar el agente de un hilo que lleva
`[hilos] dormir_tras` sin actividad (30 min de fábrica; 0 es nunca) y dejar en su ventana, en su mismo lugar de la
lista, un programa de una línea que espera. Su conversación queda en disco con el id de siempre, y despertarlo es
abrir el agente retomándola (`claude --resume`), con el mismo esfuerzo y las mismas carpetas (`lanzar.para_hilo`):
unos segundos.

**Quién lo duerme.** El nodo, cada 30 s (`mirar`), como mira la pregunta de confiar (telar.confiar). Duerme solo lo
que está seguro de que está quieto; ante la duda, despierto. No duerme un hilo:

- de otra máquina (lo duerme la suya), archivado, con más de un panel, o cuyo panel no corre su agente;
- residente para siempre (`residente = "siempre"` en su agent.toml: el nodo lo mantiene abierto);
- trabajando o que te espera (su atención, y lo que dice su pantalla: «esc to interrupt», una pregunta);
- a la vista (`a_la_vista`): una terminal enganchada a su ventana (tmux directo, el celular, `telar mirar`), lo que
  muestra una página abierta (la página lo dice cada 30 s, `POST /mirando`) o lo que se mira en otra máquina (su foto
  del espejo lo dice: `mirando`);
- con actividad reciente: su atención, su último prompt, su último foco (aquí o en otra máquina), lo último que se
  escribió en su conversación (y en las de sus subagentes) y cuándo arrancó su agente, todo más viejo que
  `dormir_tras`;
- con algo en segundo plano: un proceso hijo de su agente que sea una shell (una tarea de Bash, un Monitor) o
  `caffeinate` (Claude Code lo corre mientras trabaja), lo que su pie de pantalla cuenta («1 shell»), un
  ScheduleWakeup o un cron de la sesión (`/loop`) que su conversación dejó pendiente;
- con texto escrito y sin enviar en su caja (lo escrito se ve en su color; la sugerencia de Claude Code, tenue, no
  cuenta), o sin la caja de escribir a la vista (una pregunta, un diálogo, una pantalla que no se reconoce);
- con mensajes por entregar en su casilla, o rotando su conversación (telar.rotacion).

**Cómo duerme.** Se anota en `dormidos.json` (cuándo, su panel, su conversación y la atención que tenía, para que
la lista siga diciendo «terminó, sin ver») y su panel se reemplaza por el programa que espera (`programa`), como
`abrir_pane(reemplaza=…)`: un panel nuevo junto al viejo, y el viejo se cierra (no `respawn-pane`, que tumbó un
tmux 3.4). La ventana es la misma: mismo id, mismo lugar, el mismo nombre.

**Cómo despierta** (`despertar`): su panel se reemplaza por el agente retomando su conversación, con un primer
mensaje si lo hay. Lo despierta:

- abrirlo: un clic en la lista de la página, ⌘K, `telar mirar` (la terminal de la página, la de otra máquina, el
  celular), `telar ir`, `telar hilo retomar`, `telar hilo despertar`;
- lo que le llega: un mensaje del bus o un encargo (el nodo lo despierta con el «↯ mensaje nuevo» de primer mensaje,
  y el gancho le entrega lo de su casilla), lo que otro hilo le teclea (`escribir`);
- un ⏎ en su ventana: lo que se escribió antes llega como primer mensaje. Es también la red de lo que se teclee en
  ella sin pasar por telar: nunca llega a una shell.

    from telar import dormir
    dormir.mirar(config, tel)                    # el paso del nodo: lo que durmió, una línea por hilo
    dormir.por_que_no(observacion, tras, ahora)  # "" si se puede dormir; si no, por qué
    dormir.despertar(config, "Faro", mensaje="↯ mensaje nuevo")
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from telar.modelo import Atencion

#: lo que dice una página sobre lo que muestra vale esto (segundos): la página lo repite cada 30 s
FRESCO_PAGINA = 90
#: una máquina cuya foto no llega hace más de esto (segundos) está apagada o dormida: lo que miraba ya no se mira
APAGADA = 10 * 60
#: cuántas líneas del final de la pantalla se miran
FINAL = 60
#: lo que marca la línea del programa que espera en el panel de un hilo dormido: así se lo reconoce entre los procesos
MARCA = "despertar --aqui"
#: los procesos hijos del agente que dicen que algo corre: una tarea en segundo plano (siempre en una shell), un
#: Monitor, o Claude Code trabajando (`caffeinate`, en macOS)
SHELLS = frozenset({"sh", "bash", "zsh", "fish", "dash", "ksh", "tcsh", "csh", "nu", "-zsh", "-bash", "-sh"})
OCUPADOS = SHELLS | {"caffeinate"}
#: lo que el pie de pantalla de Claude Code cuenta cuando algo corre en segundo plano («1 shell», «2 tasks»): «← 2
#: agents» no, que está siempre
FONDO = re.compile(r"\b(\d+)\s+(?:background\s+)?(shells?|tasks?|monitors?|workflows?|bash(?:es)?|jobs?|processes)\b", re.I)
#: una línea de la caja de escribir: «─» de lado a lado
REGLA = re.compile(r"^\s*─{20,}\s*$")
#: el comienzo de la caja: el «❯» (o «>») y lo escrito
CAJA = re.compile(r"^\s*[❯>›]\s?")
#: una opción numerada («❯ 1. Yes»): es una pregunta, no la caja
OPCION = re.compile(r"^\s*[❯>›]\s*\d+[.)]\s")

_SGR = re.compile(r"\x1b\[([0-9;:]*)m")
_ESC = re.compile(r"\x1b(?:\[[0-9;:?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")


# ── la pantalla ───────────────────────────────────────────────────────────────

def _visible(linea: str) -> list[tuple[str, bool]]:
    """Los pedazos de texto de una línea capturada con `capture-pane -e`, cada uno con si va tenue (SGR 2)."""
    salida, tenue, pos = [], False, 0
    for m in re.finditer(r"\x1b\[[0-9;:]*m|" + _ESC.pattern, linea):
        if m.start() > pos:
            salida.append((linea[pos:m.start()], tenue))
        pos = m.end()
        sgr = _SGR.fullmatch(m.group(0))
        if sgr is None:
            continue
        codigos = [c for c in re.split(r"[;:]", sgr.group(1))] or ["0"]
        i = 0
        while i < len(codigos):
            c = codigos[i] or "0"
            if c in ("38", "48", "58") and i + 1 < len(codigos):
                i += 3 if codigos[i + 1] == "5" else 5 if codigos[i + 1] == "2" else 2
                continue
            if c == "0" or c == "22":
                tenue = False
            elif c == "2":
                tenue = True
            i += 1
    if pos < len(linea):
        salida.append((linea[pos:], tenue))
    return salida


def _plano(linea: str) -> str:
    return "".join(t for t, _ in _visible(linea))


def leer_pantalla(texto: str | None) -> dict:
    """Lo que la pantalla de un agente (Claude Code) dice de él, capturada con escapes (`capture-pane -e`):

        caja         si se ve la caja de escribir abajo (dos «─» con «❯» entre ellas, y nada más que el pie abajo)
        escrito      lo escrito en ella y sin enviar (lo tenue es la sugerencia de Claude Code, que no cuenta)
        trabajando   si dice «esc to interrupt» (en la caja, el pie o justo arriba)
        fondo        lo que el pie cuenta en segundo plano («1 shell»), "" si nada
        pregunta     si hay una opción numerada a la vista («❯ 1. Yes»): una pregunta o un diálogo

    Sin caja, lo demás no se sabe: quien decide lo toma como que no está quieto."""
    salida = {"caja": False, "escrito": "", "trabajando": False, "fondo": "", "pregunta": False}
    if not texto:
        return salida
    lineas = texto.splitlines()
    while lineas and not _plano(lineas[-1]).strip():
        lineas.pop()
    lineas = lineas[-FINAL:]
    planas = [_plano(x) for x in lineas]
    reglas = [i for i, x in enumerate(planas) if REGLA.match(x)]
    caja = None
    for j in reversed(range(len(reglas))):
        abre = reglas[j]
        if abre + 1 < len(planas) and CAJA.match(planas[abre + 1]) and not OPCION.match(planas[abre + 1]):
            cierra = next((r for r in reglas[j + 1:]), None)
            if cierra is not None and cierra > abre + 1:
                caja = (abre, cierra)
            break
    abajo = planas[caja[1] + 1:] if caja else []
    # la caja va abajo: después de ella solo el pie (el nombre, el modo, la línea de estado), no una conversación
    if caja is None or len([x for x in abajo if x.strip()]) > 6:
        salida["pregunta"] = any(OPCION.match(x) for x in planas[-20:])
        return salida
    abre, cierra = caja
    salida["caja"] = True
    escrito = []
    for k in range(abre + 1, cierra):
        letras = [(c, tenue) for t, tenue in _visible(lineas[k]) for c in t]
        if k == abre + 1:
            # sin el «❯ » del comienzo
            m = CAJA.match("".join(c for c, _ in letras))
            letras = letras[m.end():] if m else letras
        escrito.append("".join(c for c, tenue in letras if not tenue))
    salida["escrito"] = "\n".join(x.rstrip() for x in escrito).strip()
    cerca = planas[max(0, abre - 3):]
    salida["trabajando"] = any("esc to interrupt" in x.lower() for x in cerca)
    for x in abajo:
        m = FONDO.search(x)
        if m:
            salida["fondo"] = m.group(0)
            break
    salida["pregunta"] = any(OPCION.match(x) for x in planas[abre:])
    return salida


# ── los procesos ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Proceso:
    pid: int
    ppid: int
    #: cuándo arrancó (época)
    inicio: float
    #: su línea de comandos, partida en palabras (lo que da `ps -o args`, sin comillas: las palabras con espacios se
    #: parten igual)
    args: tuple[str, ...]

    @property
    def nombre(self) -> str:
        return Path(self.args[0]).name if self.args else ""


def _edad(etime: str) -> float:
    """`ps -o etime` («[[dd-]hh:]mm:ss») en segundos."""
    dias, _, resto = etime.strip().rpartition("-")
    partes = [int(x) for x in resto.split(":") if x.isdigit()]
    seg = 0
    for p in partes:
        seg = seg * 60 + p
    return seg + (int(dias) * 86400 if dias.isdigit() else 0)


def procesos() -> dict[int, Proceso]:
    """Los procesos de la máquina, por pid. Vacío si no se pudo preguntar."""
    try:
        # `errors="replace"`: ps corta los args largos por bytes, a veces a mitad de un carácter UTF-8
        r = subprocess.run(["ps", "-axo", "pid=,ppid=,etime=,args="], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return {}
    salida, ahora = {}, time.time()
    for renglon in r.stdout.splitlines():
        partes = renglon.split(None, 3)
        if len(partes) < 3 or not partes[0].isdigit() or not partes[1].isdigit():
            continue
        args = tuple(partes[3].split()) if len(partes) > 3 else ()
        salida[int(partes[0])] = Proceso(pid=int(partes[0]), ppid=int(partes[1]), inicio=ahora - _edad(partes[2]), args=args)
    return salida


def hijos(tabla: dict[int, Proceso], pid: int) -> list[Proceso]:
    return [p for p in tabla.values() if p.ppid == pid]


def _es(p: Proceso, programa: str) -> bool:
    """¿Ese proceso corre `programa` (por su nombre), directo o como guion de un intérprete (`/bin/sh …/claude`)?"""
    nombre = Path(programa).name
    return bool(p.args) and (p.nombre == nombre or (len(p.args) > 1 and Path(p.args[1]).name == nombre))


#: cuántas shells puede haber entre el panel y su agente: `sh -c` (`lanzar.envolver`), y el `bash -lc cd …` con que se
#: abre el hilo de un agente residente, que lo envuelve otra vez
HONDO_SHELLS = 3


def agente_del_panel(tabla: dict[int, Proceso], pid_panel: int | None, programa: str) -> Proceso | None:
    """El proceso del agente de un panel: el que corre `programa`, sea el del panel o uno que cuelga de él solo a través
    de shells (el agente corre dentro de un `sh -c` que deja una shell al salir, `lanzar.envolver`; el hilo de un agente
    residente, además dentro de un `bash -lc cd <su carpeta>; …`). Sin mirar más hondo que eso, ni dentro de otra cosa
    que una shell (un `mosh` no es el agente aunque algo suyo se llame igual). None si el panel no corre al agente."""
    if not pid_panel or pid_panel not in tabla:
        return None
    nivel = [tabla[pid_panel]]
    for hondo in range(HONDO_SHELLS + 1):
        hallado = next((p for p in nivel if _es(p, programa)), None)
        if hallado is not None:
            return hallado
        if hondo == HONDO_SHELLS:
            break
        nivel = [h for p in nivel if p.nombre in SHELLS for h in hijos(tabla, p.pid)]
        if not nivel:
            break
    return None


def es_dormido(tabla: dict[int, Proceso], pid_panel: int | None) -> bool:
    """¿Ese panel corre el programa que espera de un hilo dormido?"""
    p = tabla.get(pid_panel or -1)
    return p is not None and MARCA in " ".join(p.args)


# ── la conversación ───────────────────────────────────────────────────────────

def _ts(valor) -> float | None:
    if not isinstance(valor, str) or not valor:
        return None
    try:
        d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


#: archivo → (tamaño, mtime, lo que se sacó de él): leer una conversación de 20 MB cada 30 s no; cuando cambia, sí
_LEIDAS: dict[str, tuple[int, float, list]] = {}


def _llamadas(archivo: Path) -> list[tuple[float, str, dict]]:
    """Las llamadas a ScheduleWakeup, CronCreate y CronDelete de una conversación: (cuándo, cuál, su entrada)."""
    try:
        st = archivo.stat()
    except OSError:
        return []
    guardado = _LEIDAS.get(str(archivo))
    if guardado and guardado[0] == st.st_size and guardado[1] == st.st_mtime:
        return guardado[2]
    salida: list[tuple[float, str, dict]] = []
    try:
        datos = archivo.read_bytes()
    except OSError:
        return []
    if b'"ScheduleWakeup"' in datos or b'"CronCreate"' in datos:
        for linea in datos.splitlines():
            if b'"ScheduleWakeup"' not in linea and b'"CronCreate"' not in linea and b'"CronDelete"' not in linea:
                continue
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            cuando = _ts(d.get("timestamp"))
            contenido = (d.get("message") or {}).get("content") if isinstance(d.get("message"), dict) else None
            for x in contenido if isinstance(contenido, list) else []:
                if isinstance(x, dict) and x.get("type") == "tool_use" and x.get("name") in ("ScheduleWakeup", "CronCreate", "CronDelete"):
                    salida.append((cuando or 0.0, x["name"], x.get("input") if isinstance(x.get("input"), dict) else {}))
    _LEIDAS[str(archivo)] = (st.st_size, st.st_mtime, salida)
    return salida


def programado(archivo: Path | None, desde: float, ahora: float) -> str:
    """Lo que la conversación dejó programado para más tarde y sigue pendiente: un ScheduleWakeup (un `/loop` sin
    intervalo) que todavía no suena, o un cron de la sesión (CronCreate, `/loop 5m`) que no se borró. Solo cuenta lo
    que pidió el agente que corre ahora (desde `desde`, cuando arrancó): lo de antes de retomarla murió con el otro
    proceso, salvo un cron `durable`. "" si nada; si no, qué."""
    if archivo is None:
        return ""
    llamadas = _llamadas(archivo)
    despertar = None
    crones = 0
    for cuando, cual, entrada in llamadas:
        if cual == "ScheduleWakeup" and cuando >= desde:
            despertar = None if entrada.get("stop") else (cuando, entrada)
        elif cual == "CronCreate" and (cuando >= desde or entrada.get("durable")):
            crones += 1
        elif cual == "CronDelete" and crones:
            crones -= 1
    if crones:
        return "un cron de la sesión (CronCreate) sin borrar"
    if despertar is not None:
        cuando, entrada = despertar
        try:
            espera = min(3600.0, max(60.0, float(entrada.get("delaySeconds") or 0)))
        except (TypeError, ValueError):
            espera = 3600.0
        if cuando + espera > ahora - 120:
            return f"un ScheduleWakeup pendiente (suena a las {datetime.fromtimestamp(cuando + espera):%H:%M})"
    return ""


#: cuánto del final de una conversación se lee para encontrar su último momento (bytes)
COLA = 256 * 1024


def _ultimo_momento(archivo: Path) -> float | None:
    """El último momento que dice una conversación: el `timestamp` de su última línea que lo tenga. No la fecha del
    archivo: Claude Code lo toca cada tanto sin escribir nada nuevo (una conversación quieta desde la mañana amanecía
    «escrita hace 4 min»). Sin ninguna línea con hora en su final, la fecha del archivo."""
    try:
        with open(archivo, "rb") as f:
            f.seek(0, os.SEEK_END)
            largo = f.tell()
            f.seek(max(0, largo - COLA))
            cola = f.read()
        mtime = archivo.stat().st_mtime
    except OSError:
        return None
    for linea in reversed(cola.splitlines()):
        if b'"timestamp"' not in linea:
            continue
        try:
            d = json.loads(linea)
        except ValueError:
            continue  # la primera, cortada por la mitad
        cuando = _ts(d.get("timestamp")) if isinstance(d, dict) else None
        if cuando is not None:
            return cuando
    return mtime


def ultima_escritura(archivo: Path | None) -> float | None:
    """El último momento de la conversación o de la de uno de sus subagentes (`<id>/subagents/*.jsonl`)."""
    if archivo is None:
        return None
    ultima = _ultimo_momento(archivo)
    if ultima is None:
        return None
    sub = archivo.with_suffix("") / "subagents"
    try:
        for f in sub.glob("*.jsonl"):
            # solo los que se tocaron después: los de antes no pueden decir nada más nuevo
            if f.stat().st_mtime > ultima:
                ultima = max(ultima, _ultimo_momento(f) or 0.0)
    except OSError:
        pass
    return ultima


# ── qué se mira ───────────────────────────────────────────────────────────────

def anotar_mirando(config, pagina: str, hilo: str, maquina: str = "", cuando: float | None = None) -> None:
    """Lo que muestra una página abierta (`POST /mirando`, cada 30 s y al cambiar): `hilo` "" es nada (el dashboard,
    un archivo, la página oculta). `maquina`: la del hilo, si es de otra. Lo de más de 10 min se olvida."""
    from telar import estado as mod_estado

    pagina = str(pagina)[:64]
    if not pagina:
        return
    ahora = cuando if cuando is not None else time.time()

    def cambio(d: dict) -> None:
        for k in [k for k, v in d.items() if not isinstance(v, dict) or ahora - float(v.get("cuando") or 0) > APAGADA]:
            d.pop(k, None)
        d[pagina] = {"hilo": str(hilo)[:200], "maquina": str(maquina)[:64], "cuando": ahora}

    mod_estado.abrir(config)._actualizar("mirando", cambio, {})


def paginas(config, ahora: float | None = None) -> list[dict]:
    """Lo que dicen las páginas abiertas de esta máquina, las que dijeron algo hace menos de FRESCO_PAGINA."""
    from telar import estado as mod_estado

    ahora = ahora if ahora is not None else time.time()
    try:
        d = mod_estado.abrir(config)._leer("mirando", {})
    except Exception:  # noqa: BLE001 - sin poder leerlo, ninguna página dijo nada
        return []
    salida = []
    for v in d.values():
        try:
            if isinstance(v, dict) and ahora - float(v.get("cuando") or 0) <= FRESCO_PAGINA:
                salida.append({"hilo": str(v.get("hilo") or ""), "maquina": str(v.get("maquina") or "")})
        except (TypeError, ValueError):
            continue
    return salida


def clientes() -> list[tuple[str, str]]:
    """Las terminales enganchadas a tmux: (la sesión a la que se engancharon, la ventana que muestran)."""
    from telar import movil

    try:
        salida = movil._tmux("list-clients", "-F", movil.SEP.join(["#{client_session}", "#{window_id}"]), tolerante=True)
    except Exception:  # noqa: BLE001 - sin tmux, nadie mira
        return []
    lista = []
    for r in salida.splitlines():
        p = movil._partes(r, 2)
        if p:
            lista.append((p[0], p[1]))
    return lista


def sufijo_vista() -> str:
    """Cómo se llama esta máquina en las sesiones con que mira las ventanas de otra (`ver-<ventana>-<esto>`)."""
    from telar import remoto

    return remoto.sufijo_vista()


def _dueno(est, hilo) -> str:
    """La máquina del bus de un hilo cuya ventana de aquí mira otra (su `remoto`)."""
    try:
        return str((est.ajenos().get(hilo.nombre) or {}).get("maquina") or "") or hilo.remoto
    except Exception:  # noqa: BLE001
        return hilo.remoto


def _ver_desde_otra(sesion: str) -> str:
    """El sufijo de una sesión con que otra máquina mira una ventana de aquí (`ver-338-macbook`); "" si no es una."""
    m = re.fullmatch(r"ver-\d+-(.+)", sesion)
    return m.group(1) if m and not m.group(1).isdigit() and not sesion.startswith("ver-web-") else ""


def a_la_vista(config, tel, ahora: float | None = None, *, lista_clientes=None, fotos=None, lo_de_paginas=None) -> dict[str, str]:
    """hilo de aquí → por qué está a la vista. Lo que se mira no se duerme:

    - lo que muestra una página abierta de esta máquina (`paginas`), o una de otra (su foto: `mirando`);
    - una terminal enganchada a su ventana: tmux directo, el celular (`movil-…`), `telar mirar` en una terminal;
    - una terminal de una página (`ver-web-…`) solo si ninguna página ni ninguna máquina dice qué muestra (una página
      de antes): la página guarda abiertas las terminales que se miraron hace poco, y esas no se ven;
    - la de otra máquina que la mira (`ver-<n>-<máquina>`, la ventana de un hilo remoto allá) la decide su foto: si la
      tiene y está al día, lo que diga su `mirando`; si su foto no llega hace más de APAGADA, nadie mira desde allá;
      si no hay foto o no dice `mirando` (un telar de antes), se mira."""
    from telar import bus as mod_bus
    from telar import espejo as mod_espejo

    ahora = ahora if ahora is not None else time.time()
    yo = mod_bus.maquina(config)
    lo_de_paginas = paginas(config, ahora) if lo_de_paginas is None else lo_de_paginas
    try:
        fotos = mod_espejo.leer_todos(config, ahora) if fotos is None else fotos
    except Exception:  # noqa: BLE001
        fotos = []
    vistos: dict[str, str] = {}
    for p in lo_de_paginas:
        if p["hilo"] and (not p["maquina"] or p["maquina"] == yo):
            vistos.setdefault(p["hilo"], "abierto en la página")
    for f in fotos:
        if f.get("en_linea"):
            for m in f.get("mirando") or []:
                if isinstance(m, dict) and m.get("maquina") == yo and m.get("hilo"):
                    vistos.setdefault(str(m["hilo"]), f"a la vista en {f.get('nombre')}")
    informan = bool(lo_de_paginas) or any(f.get("en_linea") and "mirando" in f for f in fotos)
    por_ventana = {h.id: h.nombre for h in tel.hilos if tel.vivo(h)}
    for sesion, ventana in (clientes() if lista_clientes is None else lista_clientes):
        nombre = por_ventana.get(ventana)
        if not nombre:
            continue
        if sesion.startswith("ver-web-"):
            if not informan:
                vistos.setdefault(nombre, "su terminal en la página (ninguna página dice qué muestra)")
            continue
        sufijo = _ver_desde_otra(sesion)
        if sufijo:
            f = next((x for x in fotos if x.get("vista") == sufijo), None)
            if f is None:
                vistos.setdefault(nombre, f"lo mira {sufijo} (sin su foto)")
            elif (f.get("edad") or 0) > APAGADA:
                continue  # esa máquina está apagada: nadie mira desde allá
            elif not f.get("en_linea") or "mirando" not in f:
                vistos.setdefault(nombre, f"lo mira {f.get('nombre')} (sin noticias de qué muestra)")
            continue
        vistos.setdefault(nombre, f"una terminal enganchada ({sesion})")
    return vistos


def mirando_de_aqui(config, tel, ahora: float | None = None, *, lista_clientes=None, lo_de_paginas=None) -> list[dict]:
    """Lo que se mira en esta máquina, para la foto del espejo (`mirando`): [{maquina, hilo}], con la máquina dueña de
    cada hilo. Así la máquina de un hilo que se mira desde aquí (una página de aquí, o la ventana local de un hilo
    remoto) sabe que no lo tiene que dormir."""
    from telar import bus as mod_bus

    ahora = ahora if ahora is not None else time.time()
    yo = mod_bus.maquina(config)
    est = tel.estado
    pares: set[tuple[str, str]] = set()

    def de(hilo_nombre: str) -> str:
        h = tel.por_nombre(hilo_nombre)
        return _dueno(est, h) if h is not None and h.remoto and h.remoto != "?" else yo

    for p in (paginas(config, ahora) if lo_de_paginas is None else lo_de_paginas):
        if p["hilo"]:
            pares.add((p["maquina"] or de(p["hilo"]), p["hilo"]))
    por_ventana = {h.id: h for h in tel.hilos if tel.vivo(h)}
    for sesion, ventana in (clientes() if lista_clientes is None else lista_clientes):
        h = por_ventana.get(ventana)
        if h is None or sesion.startswith("ver-web-") or _ver_desde_otra(sesion):
            continue
        pares.add((de(h.nombre), h.nombre))
    return [{"maquina": m, "hilo": n} for m, n in sorted(pares) if m]


# ── observar y decidir ────────────────────────────────────────────────────────

@dataclass
class Observacion:
    """Lo que se sabe de un hilo para decidir si duerme. Lo que no se llegó a mirar queda en None."""

    nombre: str
    id: str = ""
    remoto: str = ""
    archivado: bool = False
    dormido: bool = False
    #: cuántos paneles vivos tiene su ventana
    paneles: int = 0
    panel: str = ""
    #: el proceso de su agente, si su panel lo corre
    agente: Proceso | None = None
    #: lo que corre como hijo de su agente (sus nombres)
    hijos: list[str] = field(default_factory=list)
    conversacion: str = ""
    archivo: Path | None = None
    siempre: bool = False
    atencion: Atencion = Atencion.NINGUNA
    atencion_desde: datetime | None = None
    actividad: datetime | None = None
    visto: datetime | None = None
    escrito_en: float | None = None
    vista: str = ""
    pantalla: dict | None = None
    programado: str | None = None
    por_entregar: int = 0
    rotando: bool = False


def _epoca(d: datetime | float | None) -> float | None:
    if d is None:
        return None
    if isinstance(d, (int, float)):
        return float(d)
    return d.timestamp() if d.tzinfo else time.mktime(d.timetuple())


def quieto_desde(o: Observacion, ahora: float) -> float | None:
    """La última señal de vida de un hilo (época): su atención, su último prompt, su último foco, lo último escrito en
    su conversación y cuándo arrancó su agente. None si no hay ninguna."""
    marcas = [_epoca(o.atencion_desde), _epoca(o.actividad), _epoca(o.visto), o.escrito_en,
              o.agente.inicio if o.agente is not None else None]
    marcas = [m for m in marcas if m is not None]
    return max(marcas) if marcas else None


def _minutos(segundos: float) -> str:
    return f"{segundos / 60:.0f} min" if segundos < 5400 else f"{segundos / 3600:.1f} h"


def por_que_no(o: Observacion, tras: float, ahora: float | None = None, *, forzar: bool = False) -> str:
    """Por qué ese hilo no se duerme ahora; "" si se puede. Las reglas, en orden: la primera que no se cumple lo dice.
    Ante la duda (algo que no se pudo mirar), no. Con `forzar` (lo pide la persona: `telar hilo dormir`), sin mirar
    `dormir_tras`, cuánto lleva quieto ni si está a la vista; lo demás, igual."""
    ahora = ahora if ahora is not None else time.time()
    if tras <= 0 and not forzar:
        return "dormir_tras es 0: nunca"
    if o.dormido:
        return "ya duerme"
    if o.remoto:
        return "vive en otra máquina (lo duerme la suya)"
    if o.archivado:
        return "archivado"
    if o.paneles != 1:
        return f"su ventana tiene {o.paneles} paneles" if o.paneles else "sin panel"
    if o.agente is None:
        return "su panel no corre su agente"
    if not o.conversacion:
        return "sin conversación anotada que retomar"
    if o.archivo is None:
        return "su conversación no está en disco"
    if o.siempre:
        return "residente para siempre (residente = \"siempre\")"
    if o.atencion == Atencion.TRABAJANDO:
        return "trabajando"
    if o.atencion == Atencion.ESPERA:
        return "te espera"
    if o.vista and not forzar:
        return f"a la vista: {o.vista}"
    desde = quieto_desde(o, ahora)
    if desde is None and not forzar:
        return "no se sabe desde cuándo está quieto"
    if desde is not None and ahora - desde < tras and not forzar:
        return f"activo hace {_minutos(max(0.0, ahora - desde))} (duerme tras {_minutos(tras)})"
    # `caffeinate` (Claude Code lo deja hasta 5 min después de trabajar) solo cuenta sin `forzar`: tras `dormir_tras`
    # quieto ya no debería estar, y si está, algo lo renueva
    ocupados = [h for h in o.hijos if h in SHELLS or (h in OCUPADOS and not forzar)]
    if ocupados:
        return f"algo corre en segundo plano ({', '.join(sorted(set(ocupados)))})"
    p = o.pantalla
    if p is None:
        return "su pantalla no se pudo leer"
    if p.get("trabajando"):
        return "trabajando (lo dice su pantalla)"
    if p.get("pregunta") or not p.get("caja"):
        return "una pregunta o algo que no es la caja de escribir en su pantalla"
    if p.get("escrito"):
        return "tiene texto escrito sin enviar"
    if p.get("fondo"):
        return f"en segundo plano: {p['fondo']}"
    if o.programado is None:
        return "su conversación no se pudo leer"
    if o.programado:
        return o.programado
    if o.por_entregar:
        return f"{o.por_entregar} mensaje(s) por entregar en su casilla"
    if o.rotando:
        return "rotando su conversación"
    return ""


def _agente(config):
    from telar import agente as mod_agente

    if not config.agente.nombre:
        return None
    try:
        return mod_agente.obtener(config.agente.nombre, config)
    except Exception:  # noqa: BLE001 - sin agente no hay a quién dormir
        return None


def _siempre(config, est) -> set[str]:
    from telar import agentes as mod_agentes

    try:
        return {h for a in mod_agentes.descubrir(config, est.vinculos()) if a.presencia == "siempre" for h in a.hilos}
    except Exception:  # noqa: BLE001 - sin poder leerlos, ninguno es para siempre
        return set()


def observar(config, tel, ahora: float | None = None, *, tabla: dict[int, Proceso] | None = None, solo: str = "",
             vistos: dict[str, str] | None = None, completo: bool = False) -> list[Observacion]:
    """Lo que se sabe de cada hilo vivo de esta máquina (o solo de `solo`). Lo caro (la pantalla, la conversación, la
    casilla) se mira solo de los que pasan lo barato, salvo con `completo`."""
    from telar import casilla, rotacion

    ahora = ahora if ahora is not None else time.time()
    mux, est = getattr(tel, "mux", None), getattr(tel, "estado", None)
    agente = _agente(config)
    if mux is None or est is None or agente is None:
        return []
    programa = getattr(agente, "binario", "") or config.agente.nombre
    tabla = procesos() if tabla is None else tabla
    try:
        panes = [p for p in mux.panes() if not getattr(p, "flotante", False) and not getattr(p, "terminado", False)]
    except Exception:  # noqa: BLE001 - sin paneles que mirar, nada
        return []
    por_tab: dict[str, list] = {}
    for p in panes:
        por_tab.setdefault(str(p.tab), []).append(p)
    dormidos, atenciones, actividades = est.dormidos(), est.atenciones(), est.actividades()
    sesiones, paneles = est.sesiones(), est.paneles()
    siempre = _siempre(config, est)
    vistos = a_la_vista(config, tel, ahora) if vistos is None else vistos
    rotan = set(rotacion.leer(config))
    tras = config.hilos.dormir_tras
    salida = []
    for h in tel.hilos:
        if solo and h.nombre != solo:
            continue
        if not tel.vivo(h):
            continue
        mios = por_tab.get(str(h.id), [])
        o = Observacion(nombre=h.nombre, id=h.id, remoto=h.remoto, archivado=h.archivado, dormido=h.nombre in dormidos,
                        paneles=len(mios), siempre=h.nombre in siempre, vista=vistos.get(h.nombre, ""))
        if len(mios) == 1:
            panel = mios[0]
            o.panel = str(panel.id)
            o.agente = agente_del_panel(tabla, getattr(panel, "pid", None), programa)
            o.conversacion = paneles.get(o.panel) or (sesiones.get(h.nombre) or ("",))[0]
        o.atencion, o.atencion_desde = atenciones.get(h.nombre, (Atencion.NINGUNA, None))
        o.actividad = actividades.get(h.nombre)
        o.visto = h.visto
        if o.agente is not None:
            o.hijos = [p.nombre for p in hijos(tabla, o.agente.pid)]
        if o.conversacion:
            try:
                o.archivo = agente.archivo_de(o.conversacion)
            except Exception:  # noqa: BLE001
                o.archivo = None
            o.escrito_en = ultima_escritura(o.archivo)
            # y la principal del hilo, si es otra (la que retoma al despertar): lo más nuevo de las dos
            principal = (sesiones.get(h.nombre) or ("",))[0]
            if principal and principal != o.conversacion and o.escrito_en is not None:
                try:
                    otra = ultima_escritura(agente.archivo_de(principal))
                except Exception:  # noqa: BLE001
                    otra = None
                o.escrito_en = max(o.escrito_en, otra or 0.0)
        if completo or por_que_no(o, tras, ahora) == "su pantalla no se pudo leer":
            if o.agente is not None:
                try:
                    o.pantalla = leer_pantalla(_capturar(mux, o.panel))
                except Exception:  # noqa: BLE001 - una pantalla que no se deja leer: no se duerme
                    o.pantalla = None
                o.programado = programado(o.archivo, o.agente.inicio, ahora) if o.archivo else None
            try:
                o.por_entregar = len(casilla.despiertan(config, h.nombre))
            except Exception:  # noqa: BLE001
                o.por_entregar = 0
            o.rotando = h.nombre in rotan
        salida.append(o)
    return salida


# ── dormir y despertar ────────────────────────────────────────────────────────

def candado(config):
    """Dormir y despertar, de a uno por máquina: el nodo que duerme y la página que despierta no se cruzan."""
    from telar import estado as mod_estado

    return mod_estado._candado(Path(config.estado) / "dormir.lock")


def dormido(config, hilo: str) -> bool:
    from telar import estado as mod_estado

    if config is None:
        return False
    try:
        return hilo in mod_estado.abrir(config).dormidos()
    except Exception:  # noqa: BLE001 - sin poder leerlo, despierto
        return False


def programa(hilo: str, *, desde: datetime | None = None, conversacion: str = "", tras: float = 0,
             pedido: bool = False, motivo: str = "") -> list[str]:
    """Lo que corre el panel de un hilo dormido: dice que duerme y espera un ⏎. Con él, `telar hilo despertar --aqui`
    pone al agente en su lugar (reemplaza este panel), con lo escrito antes de primer mensaje; si no puede, lo dice y se
    vuelve a esperar: el panel no se cierra (la ventana perdería su lugar). Ignora ⌃C, y lo que se teclee nunca llega a
    una shell."""
    from telar.agente.base import ejecutable_telar
    from telar.entorno import linea_unset

    hora = f"{(desde or datetime.now()):%H:%M}"
    porque = "lo pidieron" if pedido else f"llevaba {_minutos(tras)} sin actividad" if tras else "sin actividad"
    lineas = [
        f"◌ «{hilo}» duerme desde las {hora}: {porque} y su agente se cerró para liberar memoria.",
        f"  Su conversación sigue en disco{f' ({conversacion[:8]})' if conversacion else ''} y se retoma tal cual.",
        "",
        "  ⏎ lo despierta. Lo que escribas antes le llega como primer mensaje.",
    ] if not motivo else [
        # se está yendo a otra máquina (telar.mudanza.detener): no se despierta aquí mientras viaja
        f"◌ «{hilo}» {motivo} ({hora}).",
        f"  Su agente se detuvo para que su conversación{f' ({conversacion[:8]})' if conversacion else ''} viaje entera.",
        "",
        "  Si el traspaso falla, despierta aquí solo; si llega, esta ventana se cierra.",
    ]
    despertar = [*ejecutable_telar(), "hilo", "despertar", "--aqui", "--hilo", hilo, "--texto"]
    linea = (f"{linea_unset()}; export TELAR_HILO={shlex.quote(hilo)}; trap '' INT QUIT TSTP; "
             f"printf '%s\\n' {' '.join(shlex.quote(x) for x in lineas)}; "
             "while :; do while ! IFS= read -r l; do sleep 1; done; "
             f"{shlex.join(despertar)} \"$l\"; "
             "printf '%s\\n' '  no se pudo despertar: ⏎ para intentar de nuevo'; done")
    return ["sh", "-c", linea]


def _carpeta_hilo(config, est, hilo: str) -> Path | None:
    relativa = est.vinculos().get(hilo, "")
    if not relativa:
        return None
    carpeta = Path(config.raiz) / relativa
    return carpeta if carpeta.is_dir() else None


def _panel_de(mux, hilo: str, preferido: str = ""):
    """La ventana del hilo y su panel (el anotado, si sigue; si no, el único). (None, None) si no está."""
    ventana = next((h.id for h in mux.hilos() if h.nombre == hilo), None)
    if ventana is None:
        return None, None
    panes = [p for p in mux.panes(ventana) if not getattr(p, "flotante", False) and not getattr(p, "terminado", False)]
    panel = next((p for p in panes if str(p.id) == preferido), None) or (panes[0] if len(panes) == 1 else None)
    return ventana, panel


def dormir_uno(config, tel, hilo: str, *, forzar: bool = False, tabla=None, vistos=None, ahora: float | None = None) -> str:
    """Duerme a `hilo` si las reglas lo dejan (con `forzar`, lo pidió la persona: sin mirar cuánto lleva quieto ni si
    está a la vista). Lo vuelve a mirar todo bajo el candado, justo antes. Devuelve lo que pasó, en una línea; levanta
    RuntimeError si no se puede, con el motivo."""
    from telar import estado as mod_estado
    from telar.agente import lanzar

    ahora = ahora if ahora is not None else time.time()
    tras = config.hilos.dormir_tras
    with candado(config):
        obs = observar(config, tel, ahora, tabla=tabla, solo=hilo, vistos={} if forzar else vistos, completo=True)
        if not obs:
            raise RuntimeError(f"«{hilo}» no tiene ventana viva en esta máquina")
        o = obs[0]
        motivo = por_que_no(o, tras, ahora, forzar=forzar)
        if motivo:
            raise RuntimeError(f"«{hilo}» no se duerme: {motivo}")
        est = mod_estado.abrir(config)
        try:
            carpeta = lanzar.carpeta(config, _carpeta_hilo(config, est, hilo))
        except Exception:  # noqa: BLE001 - sin carpeta, donde esté
            carpeta = None
        cuando = datetime.now()
        registro = {"desde": cuando.isoformat(timespec="seconds"), "panel": o.panel, "ventana": o.id,
                    "conversacion": o.conversacion, "atencion": o.atencion.value,
                    "atencion_desde": o.atencion_desde.isoformat(timespec="seconds") if o.atencion_desde else ""}
        est.anotar_dormido(hilo, registro)
        try:
            nuevo = tel.mux.abrir_pane(programa(hilo, desde=cuando, conversacion=o.conversacion, tras=tras, pedido=forzar),
                                       reemplaza=o.panel, ruta=carpeta if carpeta and Path(carpeta).is_dir() else None,
                                       foco=False)
        except Exception as e:
            est.olvidar_dormido(hilo)
            raise RuntimeError(f"no pude dormir a «{hilo}»: {e}") from e
        est.anotar_dormido(hilo, {**registro, "panel": str(getattr(nuevo, "id", "") or "")})
    quieto = quieto_desde(o, ahora)
    hace = f" tras {_minutos(ahora - quieto)} quieto" if quieto and not forzar else ""
    return f"«{hilo}» se durmió{hace}: su agente se cerró y su ventana espera (conversación {o.conversacion[:8]})"


def despertar(config, hilo: str, *, mensaje: str = "", mux=None, cesion: bool = False) -> str:
    """Retoma el agente de un hilo dormido en su misma ventana, con `mensaje` de primer mensaje si lo hay. Devuelve lo
    que hizo, en una línea; "" si no dormía (o su ventana ya no está: entonces se olvida que dormía, y abrirlo es
    retomarlo como a cualquiera sin ventana). Levanta RuntimeError si dormía y no se pudo. Uno que se detuvo para irse
    a otra máquina (`cede` en su registro, telar.mudanza.detener) no despierta, salvo que la mudanza se eche atrás
    (`cesion`): si despertara aquí mientras viaja, seguiría en dos máquinas."""
    from telar import estado as mod_estado
    from telar.agente import ErrorDeAgente, lanzar

    est = mod_estado.abrir(config)
    with candado(config):
        registro = est.dormidos().get(hilo)
        if registro is None:
            return ""
        if registro.get("cede") and not cesion:
            raise RuntimeError(f"«{hilo}» se está yendo a {registro['cede']}: no despierta aquí mientras viaja")
        if mux is None:
            from telar.mux import obtener as obtener_mux

            mux = obtener_mux(config)
        try:
            ventana, panel = _panel_de(mux, hilo, str(registro.get("panel") or ""))
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"no pude ver la ventana de «{hilo}»: {e}") from e
        if ventana is None or panel is None:
            est.olvidar_dormido(hilo)
            return ""
        try:
            lanz = lanzar.para_hilo(config, hilo, _carpeta_hilo(config, est, hilo), mensaje)
        except ErrorDeAgente as e:
            raise RuntimeError(f"no pude despertar a «{hilo}»: {e}") from e
        if lanz is None:
            raise RuntimeError(f"no pude despertar a «{hilo}»: no hay agente configurado")
        est.olvidar_dormido(hilo)
        # antes de reemplazar el panel: si el que lo pide es el panel que espera (el ⏎), reemplazarlo cierra este proceso
        try:
            lanzar.anotar(config, hilo, lanz, mux)
        except Exception:  # noqa: BLE001 - anotarlo es un extra: su gancho la anota igual al arrancar
            pass
        try:
            mux.abrir_pane(lanz.comando, reemplaza=str(panel.id), ruta=lanz.carpeta, foco=False)
        except Exception as e:
            est.anotar_dormido(hilo, registro)
            raise RuntimeError(f"no pude despertar a «{hilo}»: {e}") from e
    que = f"conversación {lanz.retoma[:8]}" if lanz.retoma else "una conversación nueva"
    return f"«{hilo}» despertó ({que})" + (f", con: {mensaje[:60]}" if mensaje else "")


def dormido_alla(tel, hilo) -> str:
    """Si `hilo` es la ventana de aquí de uno que vive en otra máquina y allá duerme (lo publica su dueño), esa
    máquina; "" si no."""
    if not getattr(hilo, "remoto", "") or hilo.remoto == "?" or getattr(tel, "estado", None) is None:
        return ""
    try:
        ajeno = tel.estado.ajenos().get(hilo.nombre) or {}
    except Exception:  # noqa: BLE001
        return ""
    return str(ajeno.get("maquina") or "") if ajeno.get("dormido") else ""


def despertar_hilo(ctx, tel, hilo, *, mensaje: str = "") -> str:
    """Despertar un hilo donde viva: el de aquí, en su ventana (`despertar`); el de otra máquina que duerme allá, por
    el bus (su dueño lo retoma: `hilo-despertar`). "" si no dormía. RuntimeError si dormía y no se pudo."""
    if dormido(ctx.config, hilo.nombre):
        return despertar(ctx.config, hilo.nombre, mensaje=mensaje, mux=getattr(tel, "mux", None))
    maquina = dormido_alla(tel, hilo)
    if not maquina:
        return ""
    from telar import alcance
    from telar import bus as mod_bus

    if alcance.de(ctx.config, maquina).fuera:
        # que duerma allá es lo último que dijo antes de irse: no hay a quién pedírselo, y esperar el plazo del bus
        # dejaba colgado a quien solo quería ir a él (`telar hilo despertar` lo deja en cola)
        return ""
    if mensaje:
        r = mod_bus.pedir(ctx.config, maquina, "hilo", {"argv": ["despertar", "--hilo", hilo.nombre, "--texto", mensaje]},
                          espera=60)
    else:
        r = mod_bus.pedir(ctx.config, maquina, "hilo-despertar", {"hilo": hilo.nombre}, espera=60)
    if not r.get("ok") or int(r.get("codigo", 0) or 0) != 0:
        raise RuntimeError(f"«{hilo.nombre}» duerme en {maquina} y no se pudo despertar: {r.get('error') or 'falló'}")
    return f"«{hilo.nombre}» despertó en {maquina}"


def despertar_pedido(ctx, hilo: str, maquina: str = "", *, texto: str = "", cola: bool = False) -> dict:
    """Lo que pide la página (`POST /despertar`): el hilo `hilo` de esta máquina, o el de `maquina` si es otra.
    {hecho} ("" si no dormía); con `cola` (un botón: «despertar», «despertar al volver»), donde viva y como viva
    (telar.alcance.despertar: uno cerrado se retoma, y el de una máquina fuera de línea queda en cola, con `en_cola`).
    Sin `cola` (abrir uno que la lista dice dormido), solo si duerme, y nada para una máquina fuera de línea: mirarlo no
    deja nada en cola. RuntimeError si no se pudo."""
    from telar import alcance
    from telar import bus as mod_bus
    from telar.ordenes import _comun

    if cola:
        return alcance.despertar(ctx, hilo, maquina, texto, por="la página")
    if maquina and mod_bus.hay_bus(ctx.config) and maquina != mod_bus.maquina(ctx.config):
        if alcance.de(ctx.config, maquina).fuera:
            return {"hecho": ""}
        return alcance.despertar(ctx, hilo, maquina, texto, por="la página")
    tel = _comun.tejer(ctx, con_ficha=False)
    h = tel.por_nombre(hilo)
    if h is None or not tel.vivo(h):
        return {"hecho": ""}
    return {"hecho": despertar_hilo(ctx, tel, h, mensaje=texto)}


def despertar_aqui(config, hilo: str, texto: str = "") -> int:
    """Lo que hace el ⏎ en la ventana de un hilo dormido (`programa`): despertarlo, con lo escrito de primer mensaje.
    Reemplaza este mismo panel, así que si sale bien este proceso no sigue (su panel se cierra). Si no se puede, lo
    dice y devuelve 1: el panel vuelve a esperar."""
    from telar import estado as mod_estado

    est = mod_estado.abrir(config)
    hilo = est.nombre_actual(hilo)
    # el panel que espera es la prueba de que duerme, aunque lo anotado se haya perdido
    if hilo not in est.dormidos():
        est.anotar_dormido(hilo, {"desde": datetime.now().isoformat(timespec="seconds"),
                                  "panel": os.environ.get("TMUX_PANE", "")})
    print(f"  despertando a «{hilo}»…", flush=True)
    try:
        hecho = despertar(config, hilo, mensaje=texto.strip())
    except RuntimeError as e:
        print(f"  {e}", flush=True)
        return 1
    if not hecho:
        print(f"  «{hilo}» no tiene ventana aquí", flush=True)
        return 1
    return 0


def escribir(config, tel, hilo, texto: str, *, enviar: bool = False, espera: float = 45.0, pegar: bool = False) -> None:
    """Teclearle a la ventana de un hilo, que puede estar dormido. Dormido y con `enviar`, se le despierta con lo
    escrito de primer mensaje; sin `enviar` (dejarlo escrito para que la persona lo mande), se le despierta y se espera
    a que su caja de escribir aparezca (hasta `espera` segundos). Despierto, como siempre (`mux.escribir`). `pegar`: el
    texto tiene varias líneas y va sin ⏎, pegado entre corchetes (lo de allá es Claude Code, que lo entiende)."""
    if dormido(config, hilo.nombre):
        if enviar:
            if despertar(config, hilo.nombre, mensaje=texto, mux=tel.mux):
                return
        else:
            hecho = despertar(config, hilo.nombre, mux=tel.mux)
            if hecho:
                limite = time.time() + espera
                while time.time() < limite:
                    time.sleep(0.5)
                    try:
                        _, panel = _panel_de(tel.mux, hilo.nombre)
                        if panel is not None and leer_pantalla(_capturar(tel.mux, str(panel.id)))["caja"]:
                            break
                    except Exception:  # noqa: BLE001 - se sigue esperando
                        continue
    if pegar:
        tel.mux.escribir(hilo.id, texto, enviar=enviar, pegar=True)
    else:
        tel.mux.escribir(hilo.id, texto, enviar=enviar)


def _capturar(mux, panel: str) -> str | None:
    if hasattr(mux, "capturar_pane_con_escapes"):
        return mux.capturar_pane_con_escapes(panel)
    return mux.capturar_pane(panel, FINAL)


# ── el paso del nodo ──────────────────────────────────────────────────────────

def mirar(config, tel, ahora: float | None = None, *, tabla=None, vistos=None) -> list[str]:
    """El paso del nodo, cada 30 s: duerme a los hilos de aquí que llevan `dormir_tras` quietos y que ninguna regla
    protege (`por_que_no`), y ordena lo anotado de los que duermen (`ordenar`). Devuelve lo que pasó, una línea por
    hilo, para su registro. Con `dormir_tras` 0, solo lo segundo."""
    ahora = ahora if ahora is not None else time.time()
    cambios = ordenar(config, tel, tabla=tabla)
    tras = config.hilos.dormir_tras
    if tras <= 0 or getattr(tel, "mux", None) is None:
        return cambios
    for o in observar(config, tel, ahora, tabla=procesos() if tabla is None else tabla,
                      vistos=a_la_vista(config, tel, ahora) if vistos is None else vistos):
        if por_que_no(o, tras, ahora):
            continue
        try:
            # bajo el candado lo mira todo de nuevo: lo que se le pase, solo si se le pasó aquí (las pruebas)
            cambios.append(dormir_uno(config, tel, o.nombre, tabla=tabla, vistos=vistos, ahora=ahora))
        except RuntimeError as e:
            cambios.append(str(e))
    return cambios


def ordenar(config, tel, *, tabla=None) -> list[str]:
    """Lo anotado de los que duermen, contra lo que hay: el que ya no tiene ventana (tmux se cayó, se cerró) o cuyo
    panel ya no corre el programa que espera (lo despertó otro camino) se olvida; y el que perdió la atención que
    tenía al dormirse (el gancho de cierre de su agente la borra) la recupera: la lista sigue diciendo «terminó, sin
    ver» de uno que nadie ha mirado. Todo bajo el candado, con los paneles y los procesos leídos adentro: uno que se
    duerme o se despierta mientras tanto no se olvida a medias ni recupera una atención vieja."""
    est = getattr(tel, "estado", None)
    mux = getattr(tel, "mux", None)
    if est is None or mux is None or not est.dormidos():
        return []
    with candado(config):
        try:
            panes = [p for p in mux.panes() if not getattr(p, "flotante", False) and not getattr(p, "terminado", False)]
        except Exception:  # noqa: BLE001 - sin poder mirar, nada se toca
            return []
        por_tab: dict[str, list] = {}
        for p in panes:
            por_tab.setdefault(str(p.tab), []).append(p)
        return _ordenar(est, tel, por_tab, procesos() if tabla is None else tabla, est.dormidos())


def _ordenar(est, tel, por_tab: dict, tabla: dict, dormidos: dict) -> list[str]:
    from telar.modelo import Atencion as A

    cambios = []
    atenciones = est.atenciones()
    for nombre, registro in dormidos.items():
        h = tel.por_nombre(nombre)
        mios = por_tab.get(str(h.id), []) if h is not None and tel.vivo(h) else []
        if not mios:
            est.olvidar_dormido(nombre)
            cambios.append(f"«{nombre}» dormía y su ventana ya no está: ya no duerme")
            continue
        if tabla and not any(es_dormido(tabla, getattr(p, "pid", None)) for p in mios):
            est.olvidar_dormido(nombre)
            cambios.append(f"«{nombre}» ya no duerme: su panel corre otra cosa")
            continue
        try:
            tenia = A(registro.get("atencion") or "ninguna")
        except ValueError:
            continue
        ahora_at, ahora_desde = atenciones.get(nombre, (A.NINGUNA, None))
        if tenia != A.NINGUNA and ahora_at != tenia:
            desde = registro.get("atencion_desde") or ""
            try:
                cuando = datetime.fromisoformat(desde) if desde else None
            except ValueError:
                cuando = None
            est.anotar_atencion(nombre, tenia, cuando)
    return cambios


def json_dormido(registro: dict | None) -> dict | None:
    """Lo que dice `telar hilos --json` de uno que duerme: {desde, conversacion}; None si no duerme."""
    if not registro:
        return None
    return {"desde": str(registro.get("desde") or ""), "conversacion": str(registro.get("conversacion") or "")}
