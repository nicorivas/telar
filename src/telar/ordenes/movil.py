"""`telar movil` — telar en el celular: la lista de hilos de esta máquina, pensada para
una pantalla chica, y entrar a uno sin quedar encerrado.

    mosh usuario@servidor -- ~/.local/bin/telar movil

Corre en el servidor. Flechas o el número eligen, ⏎ o un toque entran, h el día (agenda, quién
te espera, pendientes), c el correo, r recarga, n abre un hilo nuevo, q sale. Dentro de un hilo: Alt+q, F12 o tocar «◀ telar» en la barra de arriba vuelven
aquí; tocar «✉ N» abre el correo encima. Ver `telar.movil` para cómo se consigue sin tocar
lo que ve el laptop, y docs/configuracion.md para la tecla F12 en Termux.

    telar movil --correo     solo el correo entre agentes, para leer (lo que abre «✉ N»)
    telar movil --hoy        el día una vez, sin interfaz (para probar)
    telar movil --lista      la lista una vez, sin interfaz (para probar)
"""

from __future__ import annotations

import curses
import json
import os
import shutil
import subprocess
import sys
import textwrap

from telar import correo as mod_correo
from telar import movil as mod_movil
from telar.ordenes import _comun

AYUDA = "telar en el celular: los hilos de esta máquina, y entrar a uno sin quedar encerrado."


def _pendientes(nombres: list[str]) -> dict[str, int]:
    buzon = mod_correo.leer_local()
    return {n: len(cs) for n, cs in mod_correo.por_hilo(mod_correo.pendientes(buzon), nombres).items()}


def _texto_correo() -> str:
    buzon = mod_correo.leer_local(con_cuerpo=True)
    if buzon.error:
        return f"no se pudo leer el correo: {buzon.error}"
    lineas = [f"correo de {buzon.usuario} · {len(buzon.correos)} mensajes", ""]
    for grupo in mod_correo.conversaciones(list(buzon.correos))[:30]:
        lineas.append(f"== {grupo[0].asunto or '(sin asunto)'}")
        for c in grupo:
            lineas.append(f"-- {c.de or '(sistema)'} · {c.fecha[:22]}{' · ' + c.estado if c.estado else ''}")
            lineas += [f"   {l}" for l in (c.cuerpo or "").strip().splitlines()[:40]]
        lineas.append("")
    return "\n".join(lineas)


def _mostrar(pantalla, texto: str) -> None:
    """Un texto largo, con flechas para desplazarse y cualquier otra tecla para salir."""
    lineas = texto.splitlines()
    arriba = 0
    while True:
        pantalla.erase()
        alto, ancho = pantalla.getmaxyx()
        for i, l in enumerate(lineas[arriba:arriba + alto - 1]):
            pantalla.addnstr(i, 0, l, ancho - 1)
        pantalla.addnstr(alto - 1, 0, "↑↓ desplaza · otra tecla vuelve", ancho - 1, curses.A_DIM)
        k = pantalla.getch()
        if k in (curses.KEY_DOWN, ord("j")):
            arriba = min(arriba + 1, max(len(lineas) - alto + 1, 0))
        elif k in (curses.KEY_UP, ord("k")):
            arriba = max(arriba - 1, 0)
        elif k == curses.KEY_NPAGE:
            arriba = min(arriba + alto - 1, max(len(lineas) - alto + 1, 0))
        elif k == curses.KEY_PPAGE:
            arriba = max(arriba - alto + 1, 0)
        elif k != curses.KEY_MOUSE:
            return


def _pedir(pantalla, pregunta: str) -> str:
    """Una línea de texto al pie de la pantalla. Esc o una línea vacía cancelan."""
    curses.curs_set(1)
    alto, ancho = pantalla.getmaxyx()
    texto = ""
    while True:
        pantalla.move(alto - 1, 0)
        pantalla.clrtoeol()
        pantalla.addnstr(alto - 1, 0, f"{pregunta}{texto}", ancho - 1)
        k = pantalla.get_wch()
        if k in ("\n", "\r", curses.KEY_ENTER):
            curses.curs_set(0)
            return texto.strip()
        if k in ("\x1b",):
            curses.curs_set(0)
            return ""
        if k in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            texto = texto[:-1]
        elif isinstance(k, str) and k.isprintable():
            texto += k


def _datos_hoy() -> dict:
    """`telar hoy --json`, el contrato documentado: la pantalla no depende de cómo se calcula el día."""
    r = subprocess.run([sys.executable, "-m", "telar", "hoy", "--json"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "telar hoy falló")
    return json.loads(r.stdout)


_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre")
_SIMBOLO = {"espera": "○", "termino": "✓", "trabajando": "●"}


def filas_hoy(datos: dict, ancho: int, vivos: set[str]) -> list[tuple[str, int, str | None]]:
    """El día como renglones de pantalla: (texto, atributo, hilo al que entra un toque o None).
    Pura: se prueba sin curses. El texto largo se parte en varios renglones, no se corta."""
    filas: list[tuple[str, int, str | None]] = []
    ancho = max(ancho - 1, 20)

    def partir(prefijo: str, texto: str, attr: int = 0, hilo: str | None = None) -> None:
        lineas = textwrap.wrap(texto, max(ancho - len(prefijo), 10)) or [""]
        for i, l in enumerate(lineas):
            filas.append(((prefijo if i == 0 else " " * len(prefijo)) + l, attr, hilo))

    def titulo(t: str) -> None:
        if filas:
            filas.append(("", 0, None))
        filas.append((t, curses.A_BOLD, None))

    fecha = (datos.get("fecha") or "").split("-")
    if len(fecha) == 3:
        d = _DIAS[__import__("datetime").date.fromisoformat(datos["fecha"]).weekday()]
        partir("", f"{d} {int(fecha[2])} de {_MESES[int(fecha[1]) - 1]} · semana {datos.get('semana', '')}", curses.A_BOLD)

    titulo("AGENDA")
    agenda = datos.get("agenda")
    if agenda is None:
        filas.append(("  sin agenda declarada", curses.A_DIM, None))
    elif not agenda:
        filas.append(("  nada con hora", curses.A_DIM, None))
    for e in agenda or []:
        partir(f"  {(e.get('cuando') or '')[11:16]:>5} ", e.get("texto", ""))

    titulo("TE ESPERAN")
    llaman = datos.get("atencion") or []
    if not llaman:
        filas.append(("  nadie", curses.A_DIM, None))
    for h in llaman:
        nombre = h.get("nombre", "")
        entra = nombre if nombre in vivos else None
        partir(f"  {_SIMBOLO.get(h.get('atencion'), ' ')} ", f"{nombre}  {h.get('atencion', '')}", 0, entra)

    titulo("PENDIENTES")
    pend = datos.get("pendientes") or []
    if not pend:
        filas.append(("  nada pendiente", curses.A_DIM, None))
    for f in pend[:12]:
        partir(f"  {'▣' if f.get('en_curso') else '☐'} ", f.get("texto", ""))  # la ref es una ruta larga; el texto ya trae su clave
    if len(pend) > 12:
        filas.append((f"  … y {len(pend) - 12} más", curses.A_DIM, None))

    total = (datos.get("tiempo") or {}).get("total")
    if total:
        titulo("HOY")
        minutos = int(total // 60)  # `telar hoy --json` da segundos
        partir("  ", f"{minutos // 60} h {minutos % 60:02d} min con los hilos abiertos")
    for falla in (datos.get("proveedores") or {}).get("fallas", []):
        partir("", f"(proveedor caído · {falla})", curses.A_DIM)
    return filas


def _hoy(pantalla) -> tuple[str, object]:
    """El día en una pantalla: agenda, quién te espera, pendientes. Un toque (o ⏎) sobre un hilo que espera
    entra a él. Devuelve como `_menu`: ("entrar", (hilo, correos)) o ("volver", None)."""
    curses.curs_set(0)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    pantalla.erase()
    pantalla.addnstr(0, 0, "cargando el día…", 30, curses.A_DIM)
    pantalla.refresh()
    hilos = {h.nombre: h for h in mod_movil.hilos()}
    error = ""
    try:
        datos = _datos_hoy()
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
        datos, error = {}, str(e)
    arriba = 0
    sel = 0  # índice, dentro de las filas que entran, de la elegida
    while True:
        alto, ancho = pantalla.getmaxyx()
        filas = filas_hoy(datos, ancho, set(hilos))
        entran = [i for i, f in enumerate(filas) if f[2]]
        sel = min(sel, max(len(entran) - 1, 0))
        actual = entran[sel] if entran else -1
        cuerpo = alto - 1
        if actual >= 0:  # que la elegida se vea
            arriba = min(max(arriba, actual - cuerpo + 1), actual)
        arriba = max(0, min(arriba, max(len(filas) - cuerpo, 0)))
        pantalla.erase()
        if error:
            pantalla.addnstr(0, 0, f"no pude leer el día: {error}", ancho - 1)
        for y, i in enumerate(range(arriba, min(arriba + cuerpo, len(filas)))):
            texto, attr, _ = filas[i]
            pantalla.addnstr(y, 0, texto.ljust(ancho - 1) if i == actual else texto, ancho - 1,
                             curses.A_REVERSE if i == actual else attr)
        pantalla.addnstr(alto - 1, 0, "⏎ entra · ↑↓ · r recarga · q vuelve", ancho - 1, curses.A_DIM)
        k = pantalla.getch()
        if k in (ord("q"), ord("h"), 27):
            return "volver", None
        if k == ord("r"):
            return "hoy", None
        if k in (curses.KEY_DOWN, ord("j")):
            if entran and sel < len(entran) - 1:
                sel += 1
            else:
                arriba += 1
        elif k in (curses.KEY_UP, ord("k")):
            if entran and sel > 0 and entran[sel - 1] >= arriba:
                sel -= 1
            elif arriba > 0:
                arriba -= 1
            elif sel > 0:
                sel -= 1
        elif k == curses.KEY_NPAGE:
            arriba += cuerpo - 1
        elif k == curses.KEY_PPAGE:
            arriba -= cuerpo - 1
        elif k in (10, 13, curses.KEY_ENTER) and actual >= 0:
            return "entrar", (hilos[filas[actual][2]], 0)
        elif k == curses.KEY_MOUSE:
            try:
                _, _, y, _, estado = curses.getmouse()
            except curses.error:
                continue
            i = arriba + y
            if 0 <= i < len(filas) and filas[i][2] and estado & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_RELEASED):
                return "entrar", (hilos[filas[i][2]], 0)


def _menu(pantalla) -> tuple[str, object]:
    """Dibuja la lista hasta que se elige algo: ("entrar", hilo), ("nuevo", nombre), ("correo", None) o ("salir", None)."""
    curses.curs_set(0)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    elegido = 0
    hilos = mod_movil.hilos()
    pend = _pendientes([h.nombre for h in hilos])
    while True:
        pantalla.erase()
        alto, ancho = pantalla.getmaxyx()
        total = sum(pend.values())
        pantalla.addnstr(0, 0, f"telar{f'  ✉ {total}' if total else ''}", ancho - 1, curses.A_BOLD)
        if not hilos:
            pantalla.addnstr(2, 0, "no hay hilos en esta máquina", ancho - 1, curses.A_DIM)
        for i, h in enumerate(hilos[: alto - 3]):
            marca = "●" if h.clientes else "·"
            correo = f" ✉{pend[h.nombre]}" if pend.get(h.nombre) else ""
            linea = f"{i + 1:>2} {marca} {h.nombre}{correo}"
            pantalla.addnstr(2 + i, 0, linea.ljust(ancho - 1), ancho - 1,
                             curses.A_REVERSE if i == elegido else curses.A_NORMAL)
        pantalla.addnstr(alto - 1, 0, "⏎ entra · h día · n nuevo · c correo · q sale", ancho - 1, curses.A_DIM)
        k = pantalla.getch()
        if k in (ord("q"), 27):
            return "salir", None
        if k == ord("c"):
            return "correo", None
        if k == ord("h"):
            return "hoy", None
        if k == ord("n"):
            nombre = _pedir(pantalla, "nombre del hilo nuevo: ")
            if nombre and nombre in {h.nombre for h in hilos}:
                pantalla.addnstr(alto - 1, 0, f"ya hay un hilo «{nombre}»".ljust(ancho - 1), ancho - 1)
                pantalla.getch()
            elif nombre:
                return "nuevo", nombre
            continue
        if k == ord("r"):
            hilos = mod_movil.hilos()
            pend = _pendientes([h.nombre for h in hilos])
            elegido = min(elegido, max(len(hilos) - 1, 0))
        elif k in (curses.KEY_DOWN, ord("j")) and hilos:
            elegido = (elegido + 1) % len(hilos)
        elif k in (curses.KEY_UP, ord("k")) and hilos:
            elegido = (elegido - 1) % len(hilos)
        elif k in (10, 13, curses.KEY_ENTER) and hilos:
            return "entrar", (hilos[elegido], pend.get(hilos[elegido].nombre, 0))
        elif ord("1") <= k <= ord("9") and k - ord("1") < len(hilos):
            h = hilos[k - ord("1")]
            return "entrar", (h, pend.get(h.nombre, 0))
        elif k == curses.KEY_MOUSE:
            try:
                _, _, y, _, estado = curses.getmouse()
            except curses.error:
                continue
            i = y - 2
            if 0 <= i < len(hilos) and estado & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED | curses.BUTTON1_RELEASED):
                return "entrar", (hilos[i], pend.get(hilos[i].nombre, 0))


def _abrir_nuevo(ctx, nombre: str):
    """Abre el hilo con el agente configurado, en la carpeta de `[agente] carpeta` o la raíz."""
    from pathlib import Path

    from telar.agente import ErrorDeAgente
    from telar.agente import lanzar

    try:
        lanz = lanzar.para_hilo(ctx.config, nombre, None)
    except ErrorDeAgente as e:
        print(f"sin agente: {e}")
        lanz = None
    carpeta = lanz.carpeta if lanz is not None and lanz.carpeta else Path(ctx.config.raiz)
    try:
        hilo = mod_movil.crear(nombre, str(Path(carpeta).expanduser()), lanz.comando if lanz else None)
    except RuntimeError as e:
        print(f"no pude abrir «{nombre}»: {e}")
        return None
    lanzar.anotar(ctx.config, nombre, lanz)
    return hilo


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("movil", AYUDA)
    p.epilog = __doc__
    p.add_argument("--correo", action="store_true", help="solo el correo entre agentes")
    p.add_argument("--lista", action="store_true", help="la lista una vez, sin interfaz")
    p.add_argument("--hoy", action="store_true", help="el día una vez, sin interfaz")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.lista:
        hilos = mod_movil.hilos()
        pend = _pendientes([h.nombre for h in hilos])
        for h in hilos:
            print(f"{'●' if h.clientes else '·'} {h.nombre}" + (f" ✉{pend[h.nombre]}" if pend.get(h.nombre) else "")
                  + _comun.tenue(f"  {h.sesion}"))
        return 0
    if o.hoy:
        vivos = {h.nombre for h in mod_movil.hilos()}
        for texto, _, hilo in filas_hoy(_datos_hoy(), shutil.get_terminal_size((60, 24)).columns, vivos):
            print(texto + (_comun.tenue("  ⏎") if hilo else ""))
        return 0
    if o.correo:
        curses.wrapper(lambda s: _mostrar(s, _texto_correo()))
        return 0
    if os.environ.get("TMUX"):
        return _comun.queja("telar movil se abre fuera de tmux: es lo que tmux muestra, no algo que corre adentro")
    # el comando que abre «✉ N» desde la barra: este mismo telar, sin depender del PATH
    import shlex
    correo_cmd = shlex.join([sys.executable, "-m", "telar", "movil", "--correo"])
    accion, dato = "menu", None
    while True:
        if accion in ("menu", "volver"):
            accion, dato = curses.wrapper(_menu)
        if accion == "hoy":  # el día devuelve otra vez una acción: entrar a un hilo, volver o recargar
            accion, dato = curses.wrapper(_hoy)
            continue
        if accion == "salir":
            return 0
        if accion == "correo":
            curses.wrapper(lambda s: _mostrar(s, _texto_correo()))
            accion = "menu"
            continue
        if accion == "nuevo":
            hilo = _abrir_nuevo(ctx, dato)
            if hilo is None:
                input("⏎ para volver")
                accion = "menu"
                continue
            dato = (hilo, 0)
        hilo, pendientes = dato
        try:
            mod_movil.entrar(hilo, pendientes, correo_cmd)
        except RuntimeError as e:
            print(f"no pude entrar a «{hilo.nombre}»: {e}")
            input("⏎ para volver")
        accion = "menu"
