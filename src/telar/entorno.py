"""Lo que un proceso que telar arranca no hereda de quien se lo pidió.

Quien le pide a telar que abra algo (un hilo, un hijo, un agente, un periódico, una vista) suele ser un agente: un
Claude Code que corre `telar hilo hijo` desde su Bash. Claude Code marca el entorno de lo que lanza con su sesión
(`CLAUDECODE`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_CHILD_SESSION`, el socket de sus mensajes…). Un Claude Code que
arranca con esas marcas se cree hijo de esa sesión: apaga su transcript («Transcript saving is off — inherited
CLAUDE_CODE_CHILD_SESSION marker», y telar ya no puede leer el hilo), y queda colgado del socket y la sesión de otro.
El camino más largo es tmux: un servidor de tmux que se levanta desde la Bash de un Claude Code guarda ese entorno
como global y se lo da a cada panel que abre después, para siempre.

Lo mismo con otro multiplexor (`ZELLIJ_*`) y con el hilo de telar de quien lo pidió (`TELAR_HILO`): el proceso cree
estar en un lugar donde no está.

Las de configuración que la persona pone a propósito (`CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`,
`CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`…) pasan: solo se quita lo que identifica a una sesión.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

#: Variables que dicen «estás dentro de otro multiplexor». Heredadas en un panel de tmux, mienten.
AJENAS = ("ZELLIJ", "ZELLIJ_PANE_ID", "ZELLIJ_SESSION_NAME", "ZELLIJ_TAB_NAME")

#: Las marcas de la sesión de Claude Code que lanzó el proceso. Salen de lo que el mismo Claude Code (2.1.327) pone en
#: el entorno de lo que lanza y de lo que borra cuando abre una sesión independiente (las de fondo).
DE_SESION = (
    "CLAUDECODE",                           # «corres dentro de Claude Code»
    "CLAUDE_CODE_CHILD_SESSION",            # «eres hijo de otra sesión»: apaga el transcript
    "CLAUDE_CODE_SESSION_ID",               # la sesión que lo lanzó
    "CLAUDE_CODE_LAUNCHED_BY_SESSION_IDS",  # y las de antes
    "CLAUDE_CODE_CHILD_NOTES_DIR",
    "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_MESSAGING_SOCKET",         # el socket de mensajes de esa sesión, y su llave
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_ENTRYPOINT",               # cómo se abrió esa sesión (cli, sdk…)
    "CLAUDE_CODE_EXECPATH",                 # el binario de esa sesión, de su versión
    "CLAUDE_CODE_INVOKED_SKILLS",
    "CLAUDE_CODE_BRIDGE_SESSION_ID",
    "CLAUDE_CODE_HOST_WORKTREE",
    "CLAUDE_CODE_HOST_WORKTREE_FENCE",
    "CLAUDE_CODE_PLUGIN_DIRS",              # telar lo pone en settings.json (agente/claude_code.py, `_poner_mod`)
    "CLAUDE_PID",
    "CLAUDE_EFFORT",                        # el esfuerzo de esa sesión
    "AI_AGENT",
    "TRACEPARENT",                          # la traza de esa sesión, si tiene la telemetría prendida
)

#: Y cualquier otro identificador de sesión que traiga una versión nueva: `CLAUDE_…SESSION_ID(S)` o `…SESSION_UUID`.
ID_DE_SESION = re.compile(r"CLAUDE_\w*SESSION_(?:IDS?|UUID)")

#: El hilo de telar de quien lo pidió. Cada agente recibe el suyo al arrancar (`telar.agente.lanzar.envolver`); heredado,
#: un panel suelto o el comando de un periódico se cree ese otro hilo: firma sus mensajes con su nombre, y `telar ir`
#: desde ahí no mueve el foco (lo toma por un agente).
DEL_HILO = ("TELAR_HILO",)

#: Lo que Claude Code pone en el entorno de sus comandos con un valor fijo: con ese valor es suyo (y el `git commit` de
#: la persona en ese panel abortaba sin abrir el editor); con otro, es de la persona y pasa.
PUESTAS = {"GIT_EDITOR": "true"}

#: Lo que se borra con `unset` en una línea de shell (`telar.agente.lanzar.envolver`).
QUITAR = AJENAS + DE_SESION


def heredable(nombre: str, valor: str | None = None) -> bool:
    """¿Puede pasar esta variable a un proceso que telar arranca? No, si es de otro multiplexor, de una sesión de
    Claude Code o el hilo de quien lo pidió. `valor`: el de la variable, para las que son de Claude Code solo con un
    valor (`PUESTAS`)."""
    if nombre in AJENAS or nombre in DE_SESION or nombre in DEL_HILO or ID_DE_SESION.fullmatch(nombre):
        return False
    return not (nombre in PUESTAS and valor == PUESTAS[nombre])


def sin_marcas(entorno: Mapping[str, str]) -> dict[str, str]:
    """El entorno sin lo que no es heredable."""
    return {k: v for k, v in entorno.items() if heredable(k, v)}


def linea_unset() -> str:
    """Lo que borra esas variables en una shell, antes de arrancar algo: el último resguardo, por si llegaron igual
    (un servidor de tmux con el entorno sucio)."""
    puestas = "; ".join(f'[ "${{{k}-}}" = {v} ] && unset {k}' for k, v in PUESTAS.items())
    return f"unset {' '.join(QUITAR)}; {puestas}"
