"""Las ventanas de los hilos de esta máquina, y mirarlas desde afuera sin mover lo que ven los demás.

Lo usan `mirar`, la web, los periódicos, los encargos y las otras máquinas (el nombre viene de la
primera que lo usó, la vista del celular que hoy hace la web). Los hilos de esta máquina son
las ventanas de la sesión del telar, cada una marcada con un id propio (`@telar_id`): el `@338`
de tmux se reusa cuando su servidor se reinicia, la marca no.

Mirar una ventana desde afuera (el celular, otra máquina) es engancharse a una **sesión agrupada**
con la del telar, fija en esa ventana: comparte las ventanas pero elige la suya, así que dos que
miran hilos distintos no se mueven uno al otro. Un gancho la suelta si su ventana deja de ser la
actual (la ventana murió), y `destroy-unattached` la borra cuando nadie la mira.

El problema que resuelve: el tmux de aquí va sin barra y sin prefijo, para ser invisible
cuando se lo mira desde el tmux del laptop. Si el celular se engancha a esa sesión, Claude
ocupa toda la pantalla y no hay cómo volver. Por eso el celular no se engancha a la sesión
del hilo sino a una **sesión agrupada** con ella (`movil-1a2b3c4d`): comparte las ventanas
—el mismo Claude— pero tiene opciones propias. Esa sesión tiene barra arriba, mouse, y su
**propia tabla de teclas**: Alt+q, F12 o tocar «◀ telar» vuelven al menú, y el laptop,
enganchado a la sesión original, no ve nada de eso. Alt+q existe porque el toque no siempre
llega: por mosh, Termux no le pasa el mouse a tmux (probado el 28-sep-2026), y F12 no está en
el teclado del celular salvo que se configure. Al volver, la agrupada se mata; la del hilo sigue.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

#: la tabla de teclas de las sesiones del celular: lo que se ata aquí no toca al laptop.
PREFIJO = "movil-"
#: las sesiones que solo miran una ventana desde otra máquina: no son hilos
PREFIJO_VER = "ver-"
#: la marca de una ventana-hilo (opción de ventana): sobrevive a que tmux reuse su `@N`
OPCION_ID = "@telar_id"
SEP = "\x1f"


@dataclass(frozen=True, slots=True)
class HiloMovil:
    sesion: str
    nombre: str
    clientes: int = 0
    ventanas: int = 1
    #: la ventana de la sesión del telar («@338») y su marca
    ventana: str = ""
    marca: str = ""

    @property
    def objetivo(self) -> str:
        """A qué apuntar `send-keys` o `kill-*`: la ventana."""
        return self.ventana

    @property
    def direccion(self) -> str:
        """Cómo la nombra otra máquina: «@338/1a2b3c4d», la ventana y su marca."""
        return f"{self.ventana}/{self.marca}"


def partir_direccion(direccion: str) -> tuple[str, str]:
    """«@338/1a2b3c4d» → ("@338", "1a2b3c4d"); lo que no es una dirección → ("", "")."""
    if direccion.startswith("@") and "/" in direccion:
        ventana, _, marca = direccion.partition("/")
        return ventana, marca
    return "", ""


def marca_nueva() -> str:
    import uuid

    return uuid.uuid4().hex[:8]


def _tmux(*args: str, tolerante: bool = False) -> str:
    r = subprocess.run(["tmux", *args], capture_output=True, text=True)
    if r.returncode != 0 and not tolerante:
        raise RuntimeError(r.stderr.strip() or f"tmux {args[0]} salió con {r.returncode}")
    return r.stdout


def _partes(renglon: str, n: int) -> list[str]:
    # algunos tmux devuelven el separador como texto octal (ver telar.mux.tmux.SEP_EN_OCTAL)
    partes = (renglon if SEP in renglon else renglon.replace("\\037", SEP)).split(SEP)
    return partes if len(partes) == n else []


def ventanas(principal: str) -> list[HiloMovil]:
    """Las ventanas de la sesión del telar como hilos, con cuántas sesiones enganchadas las miran.

    La que no tiene marca la recibe aquí: así toda ventana que se lista tiene una dirección estable."""
    if not principal:
        return []
    salida = _tmux("list-windows", "-t", f"={principal}", "-F",
                   SEP.join(["#{window_id}", "#{window_name}", f"#{{{OPCION_ID}}}"]), tolerante=True)
    # quién mira cada ventana: una sesión con alguien enganchado cuya ventana actual es esa
    vistas: dict[str, int] = {}
    for r in _tmux("list-windows", "-a", "-F", SEP.join(["#{window_id}", "#{window_active}", "#{session_attached}"]),
                   tolerante=True).splitlines():
        p = _partes(r, 3)
        if p and p[1] == "1" and p[2].isdigit() and int(p[2]) > 0:
            vistas[p[0]] = vistas.get(p[0], 0) + 1
    lista = []
    for r in salida.splitlines():
        p = _partes(r, 3)
        if not p or not p[0].startswith("@"):
            continue
        ventana, nombre, marca = p
        if not marca:
            marca = marca_nueva()
            _tmux("set-option", "-w", "-t", ventana, OPCION_ID, marca, tolerante=True)
        lista.append(HiloMovil(sesion=principal, nombre=nombre, clientes=vistas.get(ventana, 0),
                               ventana=ventana, marca=marca))
    return lista


def sin_mirar(principal: str) -> bool:
    """¿Nadie está enganchado directo a la sesión del telar? Es lo de un servidor: ahí sus ventanas
    son hilos que se miran desde afuera, y se pueden cerrar por el tope sin quitarle nada a nadie.
    En el laptop la sesión del telar ES lo que la persona mira: sus tabs no se tocan."""
    salida = _tmux("display-message", "-p", "-t", f"={principal}:", "#{session_attached}", tolerante=True).strip()
    return salida == "0"


def hilos(principal: str = "") -> list[HiloMovil]:
    """Los hilos de esta máquina: las ventanas de la sesión del telar (`principal`), por nombre. Las
    sesiones del celular (`movil-…`) y las que solo miran una ventana (`ver-…`) no son hilos."""
    return sorted(ventanas(principal), key=lambda h: h.nombre.casefold())


def ordenes_ventana(principal: str, nombre: str, carpeta: str, palabras: list[str] | None,
                    *, viva: bool) -> list[str]:
    """El comando tmux que abre un hilo como ventana de la sesión del telar, sin moverle el foco a
    nadie (`-d`); si la sesión no existe, nace con esa ventana. Puro: se prueba sin tmux."""
    from telar import remoto as mod_remoto

    linea = mod_remoto.linea(carpeta, palabras, nombre)
    donde = ["-c", carpeta] if carpeta else []  # sin carpeta: la línea hace el `cd` (allá, `~` lo expande bash)
    if viva:
        return ["new-window", "-d", "-P", "-F", "#{window_id}", "-t", f"={principal}:", "-n", nombre,
                *donde, "bash", "-lc", linea]
    return ["new-session", "-d", "-P", "-F", "#{window_id}", "-s", principal, "-n", nombre,
            *donde, "bash", "-lc", linea]


def crear(nombre: str, carpeta: str, palabras: list[str] | None, principal: str) -> HiloMovil:
    """Abre un hilo nuevo en esta máquina: una ventana de la sesión del telar (`principal`), que otra
    máquina mira con una sesión agrupada. Si la sesión no existe, nace con esa ventana."""
    viva = subprocess.run(["tmux", "has-session", "-t", f"={principal}"], capture_output=True).returncode == 0
    ventana = _tmux(*ordenes_ventana(principal, nombre, carpeta, palabras, viva=viva)).strip()
    marca = marca_nueva()
    _tmux("set-option", "-w", "-t", ventana, OPCION_ID, marca)
    return HiloMovil(sesion=principal, nombre=nombre, ventana=ventana, marca=marca)


def ordenes_ver(grupo: str, vista: str, ventana: str) -> list[list[str]]:
    """Los comandos tmux que arman una sesión que mira una sola ventana: agrupada con `grupo` (la
    del telar), fija en `ventana`, y que suelta a quien mira si su ventana deja de ser la actual
    (murió, o algo la cambió): mirar otro hilo sin saberlo es peor que no mirar. Puros.

    `destroy-unattached` no va aquí: puesto antes de que alguien se enganche, tmux la borra en el
    acto. Va en el mismo `attach-session` (ver `enganchar`)."""
    t = f"={vista}:"
    return [
        ["new-session", "-d", "-t", f"={grupo}", "-s", vista],
        ["select-window", "-t", f"{t}{ventana}"],
        ["set-hook", "-t", t, "session-window-changed",
         f"if-shell -F '#{{!=:#{{window_id}},{ventana}}}' 'detach-client -s ={vista}'"],
    ]


def enganchar(vista: str, sin_tamano: bool = False) -> list[str]:
    """El attach a una sesión de `ordenes_ver`, que además la borra cuando nadie la mire. Con
    `sin_tamano`, quien mira no cambia el tamaño de la ventana (`ignore-size`): la ajusta quien
    trabaja en ella, no una vista de paso."""
    return ["attach-session", *(["-f", "ignore-size"] if sin_tamano else []), "-t", f"={vista}",
            ";", "set-option", "-t", f"={vista}:", "destroy-unattached", "on"]
