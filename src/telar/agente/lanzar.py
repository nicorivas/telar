"""Abrir el agente de un hilo: qué comando, en qué carpeta, y qué queda cuando termina.

Un hilo es un tab, una carpeta y lo que esa carpeta dice de sí misma; pero lo que lo
vuelve un lugar de trabajo es el agente que corre adentro. Por eso `tejer` no abre una
shell vacía: abre el agente, retomando la conversación que el hilo ya tenía si hay una.

Tres decisiones, cada una contra una falla concreta:

  · **Retomar solo lo que existe.** Una conversación anotada cuyo archivo ya no está
    haría fallar `--resume`; entonces se abre una nueva, no se pide lo imposible.
  · **El tab sobrevive al agente.** En tmux, un panel cuyo comando termina se cierra, y
    con él el tab si era el único: salir del agente con /exit borraría el hilo entero.
    Por eso el agente corre dentro de un `sh -c` que, al terminar, deja una shell.
  · **Ningún rastro de otro multiplexor.** Si tmux se levantó desde dentro de Zellij,
    sus paneles heredan `ZELLIJ_*`, y los ganchos de Zellij anotarían al agente en un
    panel ajeno. Se borran antes de arrancarlo.
  · **`TELAR_HILO` va exportada.** Los ganchos del agente la leen para saber a qué hilo
    pertenece la conversación, sin tener que adivinarlo por el foco, que miente.

Todo lo que entra a la línea de shell pasa por `shlex.quote`: un nombre de hilo es un
texto ajeno y no se interpola crudo.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from telar import agente as mod_agente
from telar.agente import ErrorDeAgente

#: variables de otro multiplexor que un panel no debe heredar; ver `telar.mux.tmux.AJENAS`.
AJENAS = ("ZELLIJ", "ZELLIJ_PANE_ID", "ZELLIJ_SESSION_NAME", "ZELLIJ_TAB_NAME")

#: los procesos que, si son lo único que corre en un panel, significan «aquí no hay nadie».
SHELLS = frozenset({"sh", "bash", "zsh", "fish", "dash", "ksh", "tcsh", "csh", "nu", "-zsh", "-bash"})


@dataclass(frozen=True, slots=True)
class Lanzamiento:
    """Lo necesario para abrir el agente de un hilo."""

    comando: list[str]
    carpeta: Path | None
    retoma: str = ""  # el id de la conversación que retoma, o vacío si es nueva
    nueva: str = ""   # el id que se le dio a la conversación nueva, para anotarlo al abrirla


def carpeta(config, carpeta_hilo: Path | None) -> Path | None:
    """Dónde arranca el agente, según `[agente] carpeta`."""
    donde = config.agente.carpeta
    if donde == "hilo":
        return carpeta_hilo or Path(config.raiz)
    if donde == "raiz":
        return Path(config.raiz)
    return Path(donde).expanduser()


def para_hilo(config, hilo: str, carpeta_hilo: Path | None) -> Lanzamiento | None:
    """El lanzamiento del agente configurado para ese hilo, o None si no hay agente."""
    nombre = config.agente.nombre
    if not nombre:
        return None
    agente = mod_agente.obtener(nombre, config)
    palabras: list[str] | None = None
    retoma = ""
    for conversacion in agente.conversaciones(hilo):
        archivo = agente.archivo_de(conversacion)
        if archivo is None or not Path(archivo).exists():
            continue
        try:
            palabras = agente.retomar(conversacion)
        except ErrorDeAgente:
            continue
        retoma = conversacion.id
        break
    nueva = ""
    if palabras is None:
        palabras, nueva = agente.nuevo_con_id()
    return Lanzamiento(comando=envolver(palabras, hilo), carpeta=carpeta(config, carpeta_hilo),
                       retoma=retoma, nueva=nueva)


def anotar(config, hilo: str, lanz: Lanzamiento | None) -> None:
    """Guarda junto al hilo el id de la conversación que se acaba de abrir en él.

    Se llama después de abrir el tab, no antes: anotar una conversación en un hilo que el
    multiplexor no llegó a crear dejaría un id apuntando a nada.
    """
    if lanz is None or not lanz.nueva or not config.agente.nombre:
        return
    agente = mod_agente.obtener(config.agente.nombre, config)
    agente.anotar(hilo, mod_agente.Conversacion(id=lanz.nueva, hilo=hilo))


def envolver(palabras: list[str], hilo: str) -> list[str]:
    """El agente dentro de un `sh -c` que exporta el hilo y deja una shell al salir."""
    linea = (
        f"unset {' '.join(AJENAS)}; "
        f"export TELAR_HILO={shlex.quote(hilo)}; "
        f"{shlex.join(palabras)}; "
        'exec "${SHELL:-/bin/sh}" -l'
    )
    return ["sh", "-c", linea]


def panel_ocioso(panes, *, tiene_hijos=None) -> str | None:
    """El único panel de un tab, si es una shell que no está corriendo nada. Si no, None.

    Es la condición para poner un agente sin preguntar: reemplazar una shell vacía no
    le quita nada a nadie. Si el tab tiene más de un panel, o algo corriendo, se deja
    como está: puede ser trabajo a medias de la persona.

    «Algo corriendo» se decide por los procesos hijos, no por el nombre que informa el
    multiplexor. Con Claude Code adentro, tmux dice `bash`, porque Claude lanza procesos
    auxiliares que le tapan el nombre: fiarse de eso fue a un paso de matar nueve
    conversaciones para abrir nueve encima. Si el multiplexor no da el pid, no se sabe,
    y lo que no se sabe no se reemplaza.
    """
    tiene_hijos = tiene_hijos or _tiene_hijos
    vivos = [p for p in panes if not getattr(p, "flotante", False) and not getattr(p, "terminado", False)]
    if len(vivos) != 1:
        return None
    panel = vivos[0]
    if Path((panel.comando or "").strip()).name not in SHELLS:
        return None
    pid = getattr(panel, "pid", None)
    if pid is None or tiene_hijos(pid):
        return None
    return panel.id


def _tiene_hijos(pid: int) -> bool:
    """¿Ese proceso tiene hijos? Ante la duda, sí: es la respuesta que no rompe nada."""
    import subprocess

    try:
        hecho = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return True
    return hecho.returncode != 1  # 0: tiene; 1: no tiene; otra cosa: no se supo
