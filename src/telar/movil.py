"""telar en el celular: los hilos de esta máquina, y entrar a uno sin quedar encerrado.

Corre **en el servidor** (`mosh usuario@servidor -- telar movil`). Los hilos de esta máquina son
las ventanas de la sesión del telar, cada una marcada con un id propio (`@telar_id`): el `@338`
de tmux se reusa cuando su servidor se reinicia, la marca no. Las sesiones propias de antes
(`telar-1a2b3c4d`, con su nombre en `@telar_hilo`) se siguen viendo mientras queden.

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
TABLA = "telar-movil"
PREFIJO = "movil-"
#: las sesiones que solo miran una ventana desde otra máquina: no son hilos
PREFIJO_VER = "ver-"
OPCION_HILO = "@telar_hilo"
#: la marca de una ventana-hilo (opción de ventana): sobrevive a que tmux reuse su `@N`
OPCION_ID = "@telar_id"
SEP = "\x1f"


@dataclass(frozen=True, slots=True)
class HiloMovil:
    sesion: str
    nombre: str
    clientes: int = 0
    ventanas: int = 1
    #: «@338» si el hilo es una ventana de la sesión del telar; "" si es una sesión propia
    ventana: str = ""
    marca: str = ""

    @property
    def objetivo(self) -> str:
        """A qué apuntar `send-keys` o `kill-*`: la ventana, o la sesión exacta."""
        return self.ventana or f"={self.sesion}:"

    @property
    def direccion(self) -> str:
        """Cómo la nombra otra máquina: «@338/1a2b3c4d» (ventana y marca) o el nombre de la sesión."""
        return f"{self.ventana}/{self.marca}" if self.ventana else self.sesion


def partir_direccion(direccion: str) -> tuple[str, str]:
    """«@338/1a2b3c4d» → ("@338", "1a2b3c4d"); una sesión → ("", "")."""
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
    """Los hilos de esta máquina: las ventanas de la sesión del telar (`principal`) y las sesiones
    propias de antes (las que tienen `@telar_hilo` o se llaman `telar-…`). Las del celular
    (`movil-…`) y las que solo miran una ventana (`ver-…`) no cuentan."""
    sep = SEP
    salida = _tmux("list-sessions", "-F", sep.join(
        ["#{session_name}", f"#{{{OPCION_HILO}}}", "#{session_attached}", "#{session_windows}"]), tolerante=True)
    lista = []
    for renglon in salida.splitlines():
        # algunos tmux devuelven el separador como texto octal (ver telar.mux.tmux.SEP_EN_OCTAL)
        partes = (renglon if sep in renglon else renglon.replace("\\037", sep)).split(sep)
        if len(partes) != 4:
            continue
        sesion, nombre, clientes, n_ventanas = partes
        if (sesion.startswith((PREFIJO, PREFIJO_VER)) or sesion == principal
                or not (nombre or sesion.startswith("telar-"))):
            continue
        lista.append(HiloMovil(sesion=sesion, nombre=nombre or sesion,
                               clientes=int(clientes) if clientes.isdigit() else 0,
                               ventanas=int(n_ventanas) if n_ventanas.isdigit() else 1))
    lista += ventanas(principal)
    lista.sort(key=lambda h: h.nombre.casefold())
    return lista


def hilo_de_panel(panel: str) -> str:
    """El hilo de un panel tmux que vive en una sesión propia (su `@telar_hilo`). Vacío si no.

    Las ventanas de la sesión del telar no llevan la marca, así que un panel de ahí da vacío y
    quien pregunta sigue con el multiplexor."""
    if not panel.startswith("%"):
        return ""
    try:
        return _tmux("display-message", "-p", "-t", panel, f"#{{{OPCION_HILO}}}", tolerante=True).strip()
    except OSError:
        return ""


def propios() -> dict[str, str]:
    """nombre del hilo → sesión tmux, de los hilos que viven en una sesión propia de esta máquina.

    Son los que abre el celular (`telar movil`) y los periódicos: no son ventanas de la sesión
    del telar, así que el multiplexor no los ve, pero están vivos y se les puede escribir. Si dos
    sesiones se llaman igual, gana la que tiene a alguien mirando.
    """
    salida: dict[str, HiloMovil] = {}
    for h in hilos():
        if h.nombre not in salida or h.clientes > salida[h.nombre].clientes:
            salida[h.nombre] = h
    return {nombre: h.sesion for nombre, h in salida.items()}


def escribir(sesion: str, texto: str, enviar: bool = False) -> None:
    """Le escribe a un hilo de esta máquina: su sesión propia o su ventana («@338»).

    `-l` manda el texto tal cual (la palabra «Enter» adentro no se vuelve un ↩). `=sesion:` es el
    nombre exacto: sin el `=`, tmux aceptaría un prefijo y podría escribirle a otro hilo.
    """
    objetivo = sesion if sesion.startswith("@") else f"={sesion}:"
    if texto:
        _tmux("send-keys", "-t", objetivo, "-l", "--", texto)
    if enviar:
        _tmux("send-keys", "-t", objetivo, "Enter")


def ordenes_nuevo(sesion: str, nombre: str, carpeta: str, palabras: list[str] | None) -> list[str]:
    """El comando tmux que abre un hilo nuevo en esta máquina, igual que los que abre el laptop
    en ella (`telar ir --remoto`): la sesión se anota su nombre, va a su carpeta y corre el
    agente, con una shell al final para que no muera si el agente termina. Puro: se prueba sin tmux."""
    from telar import remoto as mod_remoto

    return ["new-session", "-d", "-s", sesion, "-c", carpeta,
            "bash", "-lc", mod_remoto.linea(carpeta, palabras, nombre)]


def ordenes_ventana(principal: str, nombre: str, carpeta: str, palabras: list[str] | None,
                    *, viva: bool) -> list[str]:
    """El comando tmux que abre un hilo como ventana de la sesión del telar, sin moverle el foco a
    nadie (`-d`); si la sesión no existe, nace con esa ventana. Puro: se prueba sin tmux."""
    from telar import remoto as mod_remoto

    linea = mod_remoto.linea(carpeta, palabras, nombre, marcar=False)
    donde = ["-c", carpeta] if carpeta else []  # sin carpeta: la línea hace el `cd` (allá, `~` lo expande bash)
    if viva:
        return ["new-window", "-d", "-P", "-F", "#{window_id}", "-t", f"={principal}:", "-n", nombre,
                *donde, "bash", "-lc", linea]
    return ["new-session", "-d", "-P", "-F", "#{window_id}", "-s", principal, "-n", nombre,
            *donde, "bash", "-lc", linea]


def crear(nombre: str, carpeta: str, palabras: list[str] | None, principal: str = "") -> HiloMovil:
    """Abre un hilo nuevo en esta máquina: una ventana de la sesión del telar (`principal`), que
    otra máquina mira con una sesión agrupada; sin `principal`, una sesión propia como antes."""
    from telar import remoto as mod_remoto

    if principal:
        viva = subprocess.run(["tmux", "has-session", "-t", f"={principal}"], capture_output=True).returncode == 0
        ventana = _tmux(*ordenes_ventana(principal, nombre, carpeta, palabras, viva=viva)).strip()
        marca = marca_nueva()
        _tmux("set-option", "-w", "-t", ventana, OPCION_ID, marca)
        return HiloMovil(sesion=principal, nombre=nombre, ventana=ventana, marca=marca)
    sesion = mod_remoto.sesion_nueva()
    _tmux(*ordenes_nuevo(sesion, nombre, carpeta, palabras))
    return HiloMovil(sesion=sesion, nombre=nombre)


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


def enganchar(vista: str) -> list[str]:
    """El attach a una sesión de `ordenes_ver`, que además la borra cuando nadie la mire."""
    return ["attach-session", "-t", f"={vista}", ";", "set-option", "-t", f"={vista}:", "destroy-unattached", "on"]


def barra(nombre: str, correos: int = 0) -> str:
    """La línea de arriba en el celular: «◀ telar · ✉ 2 · Pizza», con rangos tocables."""
    correo = f" · #[range=user|correo]✉ {correos}#[norange]" if correos else ""
    nombre_seguro = nombre.replace("#", "##")  # un # en el nombre no es un formato de tmux
    return f"#[range=user|volver]#[reverse] ◀ telar (Alt+q) #[noreverse]#[norange]{correo} · {nombre_seguro}"


def ordenes_grupo(sesion: str, grupo: str, nombre: str, correos: int = 0, correo_cmd: str = "",
                  ventana: str = "") -> list[list[str]]:
    """Los comandos tmux que arman la sesión agrupada del celular. Puros: se prueban sin tmux.

    Con `ventana`, el hilo es una ventana de la sesión del telar: la agrupada se fija en ella."""
    t = f"={grupo}:"  # set-option apunta a un panel: sin los dos puntos, tmux no resuelve la sesión
    ordenes = ordenes_ver(sesion, grupo, ventana) if ventana else [["new-session", "-d", "-t", f"={sesion}", "-s", grupo]]
    ordenes += [
        ["set-option", "-t", t, "status", "on"],
        ["set-option", "-t", t, "status-position", "top"],
        # la barra por defecto de tmux es verde chillón; un gris azulado que no compita con el texto
        ["set-option", "-t", t, "status-style", "bg=#3b4252,fg=#d8dee9"],
        ["set-option", "-t", t, "status-left-length", "80"],
        ["set-option", "-t", t, "status-left", barra(nombre, correos)],
        ["set-option", "-t", t, "status-right", ""],
        ["set-option", "-t", t, "window-status-format", ""],
        ["set-option", "-t", t, "window-status-current-format", ""],
        ["set-option", "-t", t, "mouse", "on"],
        ["set-option", "-t", t, "key-table", TABLA],
        # la tabla es global al servidor tmux, pero solo la usan las sesiones que la eligen
        ["bind-key", "-T", TABLA, "F12", "detach-client"],
        # Alt+q: la vuelta que sí tiene el teclado del celular (Termux la trae en su fila extra)
        ["bind-key", "-T", TABLA, "M-q", "detach-client"],
        # tocar la barra: «◀ telar» vuelve al menú; «✉ N» abre el correo encima, sin salir
        ["bind-key", "-T", TABLA, "MouseDown1Status",
         "if-shell", "-F", "#{==:#{mouse_status_range},volver}", "detach-client",
         *([f"if-shell -F '#{{==:#{{mouse_status_range}},correo}}' "
            f"\"display-popup -E -w 100% -h 100% '{correo_cmd}'\""] if correo_cmd else [])],
        # la rueda del mouse sigue desplazando lo que hay en pantalla
        ["bind-key", "-T", TABLA, "WheelUpPane", "if-shell", "-F", "#{mouse_any_flag}",
         "send-keys -M", "copy-mode -e; send-keys -M"],
        # sin mouse (Termux por mosh), deslizar el dedo manda flechas al Claude y recorre su
        # historial de mensajes. PgUp (fila extra de Termux) o Alt+u entran al historial de tmux;
        # ahí las flechas y el deslizar sí mueven la pantalla, y bajar hasta el final sale solo.
        ["bind-key", "-T", TABLA, "PageUp", "copy-mode", "-eu"],
        ["bind-key", "-T", TABLA, "M-u", "copy-mode", "-eu"],
    ]
    return ordenes


def entrar(h: HiloMovil, correos: int = 0, correo_cmd: str = "") -> None:
    """Engancha el celular al hilo por una sesión agrupada; vuelve cuando se sale de ella."""
    grupo = f"{PREFIJO}{h.ventana.lstrip('@') if h.ventana else h.sesion.removeprefix('telar-')}"
    _tmux("kill-session", "-t", f"={grupo}", tolerante=True)  # una que quedó de otra vez
    try:
        for orden in ordenes_grupo(h.sesion, grupo, h.nombre, correos, correo_cmd, ventana=h.ventana):
            _tmux(*orden)
        subprocess.run(["tmux", "attach-session", "-t", f"={grupo}"])
    finally:
        _tmux("kill-session", "-t", f"={grupo}", tolerante=True)
