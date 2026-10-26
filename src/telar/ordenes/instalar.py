"""`telar instalar` — dejar esta máquina andando de una vez: configuración, página, servicio, agente.

    telar instalar                          lo que falte, mostrando antes qué va a hacer y preguntando
    telar instalar --si                     sin preguntar
    telar instalar --seco                   solo decir qué haría
    telar instalar --bus URL --token RUTA   además, unirse al bus de tus máquinas ([bus] en la configuración)
    telar instalar --unirse [CARPETA]       unirse al equipo del repositorio donde estás (su .telar/equipo.yaml)
    telar instalar --sin-servicio           sin el servicio (telar serve se corre a mano)
    telar instalar --sin-agente             sin los ganchos ni la skill de Claude Code

En orden, y cada paso solo si falta:

1. **La configuración** (`telar init`), si no hay archivo.
2. **La llave de la página** (`~/.config/telar/panel.llave`), para entrar la primera vez con `?k=…`.
3. **El bus**, con `--bus`: un `[bus]` en la configuración. El secreto (`--token`) es un archivo que ya
   tiene que estar: lo da `telar bus persona` en la máquina del bus.
4. **El servicio de `telar serve`**: systemd de usuario en Linux, launchd en macOS, con la página
   (`--web`), el nodo si hay bus (`--nodo`) y la página del equipo si hay `[equipo]` con personas. Si ya
   estaba igual, no se toca; si cambió, se reescribe y se reinicia.
5. **El agente** (`telar agente instalar`): los ganchos, la skill `/hilos` y el mod de Claude Code.
6. **Revisar** con `telar doctor` (que avisa, entre otras cosas, si tmux es anterior a la 3.5).

Con `--unirse`, desde el clon del repositorio del equipo (el que trae `.telar/equipo.yaml`, telar.unirse): revisa
que estén los programas que el equipo pide, genera tu secreto aquí y le pide entrar a la puerta del bus (viaja
solo su hash), y deja en la configuración el bus, el repositorio y los módulos del equipo. La cuenta queda
pendiente hasta que quien administra el bus la aprueba (⚙ personas en su página, o `telar bus aprobar`);
mientras, tu telar espera. Fuera del repositorio, busca su clon donde suelen estar (`~/Code`, `~/Documents`…,
telar.unirse.CARPETAS_DE_CLONES): si hay uno, se une a ese; si no, avisa e instala lo demás.

Muestra antes los pasos numerados y, mientras corre, cada uno con su resultado (✓ o ✗), lo que tardó y lo que
dijo; al final, `telar doctor` y lo que queda por hacer.

Se puede correr de nuevo cuando se quiera: lo que ya está, queda.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from telar import instalacion
from telar.config import ruta_config
from telar.ordenes import _comun

AYUDA = "Dejar esta máquina andando de una vez: configuración, página, servicio y agente."

def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("instalar", AYUDA)
    p.epilog = __doc__
    p.add_argument("--si", action="store_true", help="sin preguntar")
    p.add_argument("--seco", action="store_true", help="solo decir qué haría")
    p.add_argument("--bus", default="", help="nats://host:4222, el bus de tus máquinas")
    p.add_argument("--token", default="~/.config/telar/bus.token", help="con --bus: el archivo con tu secreto")
    p.add_argument("--persona", default="", help="con --bus: tu nombre en el bus, si no es tu usuario")
    p.add_argument("--unirse", nargs="?", const="", default=None, metavar="CARPETA",
                   help="unirse al equipo del repositorio de aquí (o de CARPETA): su .telar/equipo.yaml")
    p.add_argument("--web-puerto", dest="web_puerto", type=int, default=0, metavar="N",
                   help="el puerto de la página de esta máquina, si no es el 8780 (un servidor que aloja a varias personas)")
    p.add_argument("--sin-servicio", action="store_true", help="no instalar el servicio")
    p.add_argument("--sin-agente", action="store_true", help="no instalar los ganchos del agente")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    ruta = ruta_config()
    avisos: list[str] = []
    AL_FINAL.clear()
    print()
    print(f"  {_comun.fuerte('telar')} {_comun.tenue('·')} instalar en {_comun.fuerte(_maquina())}")
    print()
    try:
        pasos = _plan(ctx, o, ruta, avisos)
    except ErrorDeUso as e:
        print(f"  {_comun.rojo('✗')} {e}")
        print()
        return 2
    for a in avisos:
        print(f"  {_comun.amarillo('!')} {a}")
    if avisos:
        print()
    if not pasos:
        print(f"  {_comun.verde('✓')} todo estaba instalado")
    else:
        print(f"  {'Voy a hacer esto:' if not o.seco else 'Haría esto:'}")
        for n, (_, que) in enumerate(pasos, 1):
            print(f"    {_comun.tenue(str(n).rjust(len(str(len(pasos)))))}  {que}")
        print()
    if o.seco:
        return 0
    if pasos and not o.si:
        if not sys.stdin.isatty():
            return _comun.queja("¿sigo? sin terminal no puedo preguntar: --si para hacerlo, --seco para solo mirar")
        if input("  ¿sigo? [S/n] ").strip().lower() not in ("", "s", "si", "sí", "y", "yes"):
            print("  no hice nada")
            return 1
        print()
    for n, (hacer, que) in enumerate(pasos, 1):
        if not _paso(hacer, que, n, len(pasos)):
            print()
            print(f"  {_comun.rojo('Se detuvo en el paso')} {n}. Lo que ya quedó hecho no se repite: arregla eso y "
                  f"vuelve a correr {_comun.fuerte('telar instalar' + (' --unirse' if o.unirse is not None else ''))}.")
            return 2

    from telar import config as mod_config
    from telar.ordenes import doctor

    # como la orden `telar doctor`: un módulo que no se lee se deja fuera, para que doctor lo diga
    ctx.config = mod_config.cargar(ruta if ruta.exists() else None, tolerar_modulos=True)
    print()
    print(f"  {_comun.tenue('Revisando cómo quedó (telar doctor)…')}")
    print()
    codigo = doctor.main([], ctx)
    for x in AL_FINAL:
        print()
        print(f"  {_comun.amarillo('→')} {x}")
    _decir_pagina(o)
    print()
    return codigo


def direccion_pagina(puerto: int = 0) -> tuple[str, str]:
    """(la dirección de la página de esta máquina, la misma con la llave para entrar la primera vez). Donde la sirve
    `telar serve --web`: la IP de Tailscale, o 127.0.0.1 sin ella, en el puerto de siempre."""
    from telar import api_web
    from telar.ordenes.equipo import ip_de_tailscale

    base = f"http://{ip_de_tailscale() or '127.0.0.1'}:{puerto or PUERTO_PAGINA}"
    try:
        llave = api_web.ruta_llave().read_text(encoding="utf-8").strip()
    except OSError:
        llave = ""
    return base, f"{base}/?k={llave}" if llave else base


#: el puerto de la página (`telar serve --web`, su --web-puerto por defecto)
PUERTO_PAGINA = 8780


def _decir_pagina(o) -> None:
    """Al final, dónde está la página: con la llave, que el navegador guarda en una cookie la primera vez."""
    base, con_llave = direccion_pagina(getattr(o, "web_puerto", 0))
    print()
    print(f"  {_comun.verde('→')} {_comun.fuerte('Tu página:')} {con_llave}")
    detalle = (f"la primera vez entra con la llave; después basta {base}, desde esta máquina o desde tu celular "
               f"con Tailscale")
    if o.sin_servicio:
        detalle += ". Sin el servicio, antes corre: telar serve --web"
    print(f"    {_comun.tenue(detalle)}")


#: lo que la persona tiene que hacer después, dicho al final (después de doctor), donde se ve
AL_FINAL: list[str] = []


#: los cuadros del indicador mientras corre un paso
GIRO = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
#: cuántas líneas de lo que dijo un paso se muestran cuando sale bien (todas si falla)
LINEAS_DE_PASO = 6


def _maquina() -> str:
    import socket

    return socket.gethostname().split(".")[0] or "esta máquina"


def _paso(hacer, que: str, n: int, total: int) -> bool:
    """Corre un paso mostrando que está corriendo (un indicador que gira, si hay terminal) y cómo terminó: ✓ o ✗,
    lo que tardó y, abajo y tenue, lo que dijo. True si salió bien."""
    import contextlib
    import io
    import threading

    cuenta = _comun.tenue(f"{n}/{total}")
    real = sys.stdout
    vivo = real.isatty()
    dicho = io.StringIO()
    error: list[BaseException] = []

    def correr() -> None:
        try:
            with contextlib.redirect_stdout(dicho), contextlib.redirect_stderr(dicho):
                hacer()
        except (OSError, subprocess.CalledProcessError, ValueError) as e:
            error.append(e)
        except SystemExit as e:  # una orden que se sale: es su código
            if e.code not in (0, None):
                error.append(ValueError(f"salió con {e.code}"))

    inicio = time.monotonic()
    hilo = threading.Thread(target=correr, daemon=True)
    hilo.start()
    if not vivo:
        print(f"  → {n}/{total}  {que}", file=real, flush=True)
    k = 0
    while hilo.is_alive():
        if vivo:
            real.write(f"\r\x1b[K  {_comun.amarillo(GIRO[k % len(GIRO)])} {cuenta}  {que}")
            real.flush()
            k += 1
        hilo.join(0.08)
    segundos = time.monotonic() - inicio
    tiempo = _comun.tenue(f"  {segundos:.1f} s".replace(".", ",")) if segundos >= 1 else ""
    marca = _comun.rojo("✗") if error else _comun.verde("✓")
    if vivo:
        real.write("\r\x1b[K")
    print(f"  {marca} {cuenta}  {que}{tiempo}", file=real)
    lineas = [x.rstrip() for x in dicho.getvalue().splitlines() if x.strip()]
    if error:
        lineas.append(str(error[0]))
    elif len(lineas) > LINEAS_DE_PASO:
        lineas = [*lineas[:LINEAS_DE_PASO - 1], f"… y {len(lineas) - LINEAS_DE_PASO + 1} líneas más"]
    for x in lineas:
        print(("        " + (_comun.rojo(x) if error and x == lineas[-1] else _comun.tenue(x.strip()))), file=real)
    real.flush()
    return not error


class ErrorDeUso(Exception):
    """Lo pedido no se puede hacer; el mensaje es para la persona."""


def _plan(ctx, o, ruta: Path, avisos: list[str] | None = None) -> list[tuple]:
    """Los pasos que faltan: (función, qué hace). Lo que conviene saber pero no detiene nada va a `avisos`."""
    avisos = avisos if avisos is not None else []
    from telar import api_web

    pasos: list[tuple] = []
    if not ruta.exists():
        from telar.ordenes import init

        pasos.append((lambda: init.main([], ctx), f"escribir la configuración ({_comun.ruta_relativa(ruta, Path.home())})"))
    if not api_web.ruta_llave().exists():
        pasos.append((api_web.llave, f"crear la llave de la página ({api_web.ruta_llave()})"))

    hay_bus = bool(ctx.config.bus.url)
    if o.bus:
        if not re.match(r"^nats://[^\s/]+:\d+$", o.bus):
            raise ErrorDeUso(f"--bus: se esperaba nats://host:puerto, llegó {o.bus!r}")
        if hay_bus and ctx.config.bus.url != o.bus:
            raise ErrorDeUso(f"ya hay un [bus] con otra dirección ({ctx.config.bus.url}): cámbiala a mano en {ruta}")
        if not hay_bus:
            if not Path(o.token).expanduser().exists():
                raise ErrorDeUso(
                    f"no está tu secreto del bus en {o.token}: lo da `telar bus persona` en la máquina del bus")
            bloque = instalacion.bloque_bus(o.bus, o.token, o.persona)
            pasos.append((lambda: _agregar(ruta, bloque), f"unirse al bus {o.bus}"))
            hay_bus = True

    if o.unirse is not None:
        hay_bus = _unirse(ctx, o, ruta, pasos, hay_bus, avisos)

    if not o.sin_servicio:
        donde, texto = instalacion.servicio(nodo=hay_bus, equipo=_hay_equipo(ruta), web_puerto=o.web_puerto)
        if not donde.exists() or donde.read_text(encoding="utf-8") != texto:
            que = "instalar" if not donde.exists() else "actualizar"
            pasos.append((lambda: _servicio(donde, texto), f"{que} el servicio de telar serve ({donde})"))
        else:
            from telar import __version__

            corre = version_corriendo()
            if corre and corre != __version__:
                # se actualizó telar (uv tool install --force) y el servicio sigue con el código de antes
                pasos.append((lambda: _servicio(donde, texto),
                              f"reiniciar el servicio de telar serve: corre la {corre} y está instalada la {__version__}"))
    if not o.sin_agente and not _ganchos_puestos(ctx):
        from telar.ordenes import agente

        pasos.append((lambda: agente.main(["instalar", "--si"], ctx), "poner los ganchos, la skill y el mod de Claude Code"))
    return pasos


#: cómo instalar lo que un equipo suele pedir, para decirlo cuando falta
PISTAS = {"tmux": "brew install tmux (Mac) · apt install tmux (Linux)", "claude": "https://claude.com/download",
          "tailscale": "https://tailscale.com/download, y pídele a quien administra que te invite a su red",
          "uv": "https://docs.astral.sh/uv/", "npm": "https://nodejs.org", "git": "brew install git"}


def _unirse(ctx, o, ruta: Path, pasos: list, hay_bus: bool, avisos: list[str]) -> bool:
    """Los pasos de `--unirse`: pedir entrar, el bus, el repositorio y los módulos del equipo. Sin el repositorio
    del equipo (ni aquí ni donde suelen estar los clones), se avisa y se instala lo demás."""
    import json

    from telar import unirse

    try:
        equipo = unirse.buscar(Path(o.unirse).expanduser() if o.unirse else None)
        if equipo is None and o.unirse:
            raise ErrorDeUso(f"en {o.unirse} no hay un equipo (falta {unirse.NOMBRE_EQUIPO}): dale la carpeta del clon "
                             f"del repositorio del equipo")
        if equipo is None:
            cerca = unirse.buscar_cerca()
            if len(cerca) == 1:
                equipo = cerca[0]
                avisos.append(f"aquí no hay un equipo, pero encontré el repositorio de «{equipo.nombre}» en "
                              f"{_comun.ruta_relativa(equipo.repo, Path.home())}: me uno a ese")
            elif cerca:
                avisos.append("aquí no hay un equipo y encontré varios: "
                              + ", ".join(f"«{e.nombre}» en {_comun.ruta_relativa(e.repo, Path.home())}" for e in cerca)
                              + ". Instalo lo demás; para unirte a uno, corre esto dentro de su carpeta (o "
                              "--unirse ~/ruta/al/repo)")
                return hay_bus
            else:
                avisos.append(f"no encontré el repositorio del equipo (el que trae {unirse.NOMBRE_EQUIPO}): instalo lo "
                              "demás, sin unirte. Clónalo y corre esto dentro de su carpeta (o --unirse ~/ruta/al/repo)")
                return hay_bus
    except unirse.ErrorDeUnirse as e:
        raise ErrorDeUso(str(e)) from None
    faltan = unirse.faltan(equipo)
    if faltan:
        raise ErrorDeUso("falta instalar " + "; ".join(f"{x} ({PISTAS.get(x, 'instálalo')})" for x in faltan)
                         + ", y vuelve a correr esto")
    persona = o.persona or getattr(ctx.config.bus, "persona", "") or unirse.persona_por_defecto()
    from telar import cuentas

    try:
        cuentas.validar(persona)
    except cuentas.ErrorDeCuentas as e:
        raise ErrorDeUso(f"{e}: elige tu nombre en el bus con --persona") from None
    if hay_bus and ctx.config.bus.url != equipo.bus:
        raise ErrorDeUso(f"ya estás en otro bus ({ctx.config.bus.url}); el de {equipo.nombre} es {equipo.bus}")
    if not hay_bus:
        token = Path(o.token).expanduser()
        maquina = unirse.nombre_de_maquina()

        def pedir() -> None:
            r = unirse.pedir(equipo, persona, maquina, token)
            if r.get("estado") == "ya tiene cuenta":
                print(f"«{persona}» ya está en el bus y aquí está su clave: esta máquina entra con esa cuenta.")
                return
            quien = equipo.administra or "quien administra el bus"
            print(f"pedido {r.get('id', '?')}: {r.get('estado', '?')}")
            AL_FINAL.append(f"Tu pedido para entrar al bus de «{equipo.nombre}» quedó {r.get('estado', '?')} "
                            f"({r.get('id', '?')}). Avísale a {quien} para que lo apruebe: en su página, ⚙ personas. "
                            f"Tu telar se conecta solo cuando lo haga; no tienes que volver a correr nada.")

        pasos.append((lambda: _sin_error(pedir), f"pedir entrar al bus de «{equipo.nombre}» como «{persona}» "
                                                 f"(el secreto se genera aquí, en {o.token}; viaja solo su hash)"))
        bloque = instalacion.bloque_bus(equipo.bus, o.token, persona, equipo.administra)
        pasos.append((lambda: _agregar(ruta, bloque), f"unirse al bus {equipo.bus}"))
        hay_bus = True
    for viejo in unirse.remotos_viejos(equipo, getattr(ctx.config, "remotos", ()) or (), persona):
        pasos.append((lambda n=viejo.nombre: _quitar_remoto(ruta, n),
                      f"quitar [remotos.{viejo.nombre}] ({viejo.destino}): es del sistema de antes, por ssh a la máquina "
                      f"del bus; ahora lo de allá llega por el bus (respaldo en {ruta.name}.antes-unirse)"))
    if not any(r.nombre == equipo.nombre for r in getattr(ctx.config, "repos", ()) or ()):
        bloque_repo = (f"\n# el repositorio del equipo {equipo.nombre} (lo escribió `telar instalar --unirse`)\n"
                       f"[repos.{equipo.nombre}]\nruta = {json.dumps(str(equipo.repo))}\n")
        pasos.append((lambda: _agregar(ruta, bloque_repo), f"agregar el repositorio {equipo.repo} como «{equipo.nombre}»"))
    tiene_agente = ruta.exists() and re.search(r"^\[agente\]", ruta.read_text(encoding="utf-8"), re.M)
    if equipo.agente and not tiene_agente:
        lineas = [f"{k} = {json.dumps(v)}" for k, v in equipo.agente.items()]
        bloque_agente = (f"\n# el agente de cada hilo, como lo usa el equipo {equipo.nombre} (lo escribió `telar instalar "
                         f"--unirse`)\n[agente]\n" + "\n".join(lineas) + "\n")
        pasos.append((lambda: _agregar(ruta, bloque_agente),
                      "el agente de cada hilo: " + ", ".join(f"{k} {v}" for k, v in equipo.agente.items())))
    instalados = {m.nombre for m in getattr(ctx.config, "modulos", ())}
    for nombre, fuente in equipo.modulos.items():
        if nombre not in instalados:
            pasos.append((lambda f=fuente: _modulo(ctx, f), f"instalar el módulo {nombre} del equipo ({fuente})"))
    return hay_bus


def _quitar_remoto(ruta: Path, nombre: str) -> None:
    import shutil as _sh

    from telar import unirse

    respaldo = ruta.with_name(ruta.name + ".antes-unirse")
    if not respaldo.exists():
        _sh.copy2(ruta, respaldo)
    texto = ruta.read_text(encoding="utf-8")
    nuevo = unirse.quitar_tabla(texto, f"remotos.{nombre}")
    if nuevo == texto:
        raise ValueError(f"no encontré [remotos.{nombre}] en {ruta}: quítalo a mano")
    ruta.write_text(nuevo, encoding="utf-8")
    from telar import config as mod_config

    try:
        mod_config.cargar(ruta, tolerar_modulos=True)
    except Exception as e:  # noqa: BLE001 - otra parte la nombra: se deja como estaba
        ruta.write_text(texto, encoding="utf-8")
        raise ValueError(f"sin [remotos.{nombre}] la configuración no se lee ({e}); la dejé como estaba: "
                         f"quítalo a mano junto con lo que lo nombra") from None
    print(f"quité [remotos.{nombre}]; lo de antes quedó en {respaldo}")


def version_corriendo() -> str:
    """La versión del `telar serve` que está corriendo (su `/salud`, por el socket de siempre); "" si no contesta."""
    import http.client
    import json
    import socket

    from telar import api

    class _PorSocket(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect(str(api.socket_por_defecto()))

    try:
        c = _PorSocket("telar", timeout=3)
        c.request("GET", "/salud")
        r = c.getresponse()
        return str(json.loads(r.read() or b"{}").get("version") or "") if r.status == 200 else ""
    except (OSError, ValueError, http.client.HTTPException):
        return ""


def _sin_error(hacer) -> None:
    """Un paso que puede fallar con ErrorDeUnirse: como ValueError, que `main` dice y detiene."""
    from telar import unirse

    from telar import cuentas

    try:
        hacer()
    except (unirse.ErrorDeUnirse, cuentas.ErrorDeCuentas) as e:
        raise ValueError(str(e)) from None


def _modulo(ctx, fuente: str) -> None:
    from telar.ordenes import modulos

    if modulos.main(["instalar", fuente, "--si"], ctx) != 0:
        raise ValueError(f"no se pudo instalar {fuente}")


def _agregar(ruta: Path, bloque: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(bloque)


def _hay_equipo(ruta: Path) -> bool:
    from telar import equipo as mod_equipo

    try:
        return bool(mod_equipo.cargar(ruta).personas)
    except (ValueError, OSError):
        return False


def _ganchos_puestos(ctx) -> bool:
    """Si la configuración del agente ya tiene todo lo que `telar agente instalar` escribiría (los ganchos,
    la skill, el mod): se compara lo que escribiría con lo que hay."""
    from telar.agente import INCLUIDOS, obtener as obtener_agente

    try:
        for n in INCLUIDOS:
            hecho = obtener_agente(n, ctx.config).instalar(seco=True)
            if hecho.texto != hecho.antes:
                return False
        # y las skills (/hilos, /modulos): una nueva de esta versión de telar, o una que cambió, se pone
        from telar.agente import skill as mod_skill
        from telar.agente.claude_code import carpeta_config

        if "claude-code" in INCLUIDOS and any(
                mod_skill.instalar(carpeta_config(), seco=True, nombre=n)[1] in ("nueva", "actualizada") for n in mod_skill.SKILLS):
            return False
        return True
    except Exception:  # noqa: BLE001 - si no se puede saber, se instala (instalar respeta lo que hay)
        return False


def _servicio(donde: Path, texto: str) -> None:
    habia = donde.exists()
    instalacion.escribir_si_cambia(donde, texto)
    if sys.platform == "darwin":
        dominio = f"gui/{_uid()}"
        cargado = subprocess.run(["launchctl", "print", f"{dominio}/{instalacion.ETIQUETA}"],
                                 capture_output=True).returncode == 0
        if cargado:
            subprocess.run(["launchctl", "bootout", f"{dominio}/{instalacion.ETIQUETA}"], capture_output=True)
        # bootout vuelve antes de que launchd suelte el servicio (está terminando el proceso): mientras tanto,
        # bootstrap falla con «Input/output error». Se espera a que se vaya y se reintenta.
        for _ in range(40):
            r = subprocess.run(["launchctl", "bootstrap", dominio, str(donde)], capture_output=True, text=True)
            if r.returncode == 0:
                return
            time.sleep(0.5)
        raise OSError(f"launchctl bootstrap: {r.stderr.strip() or r.returncode}; a mano: launchctl bootstrap {dominio} {donde}")
    if not shutil.which("systemctl"):
        print(f"    no hay systemctl: el servicio quedó en {donde}, pero hay que arrancarlo a mano")
        return
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "telar-serve"], check=True, capture_output=True)
    if habia:
        subprocess.run(["systemctl", "--user", "restart", "telar-serve"], check=True)
    # sin «linger», systemd de usuario se apaga al cerrar la sesión, y telar serve con él
    linger = subprocess.run(["loginctl", "show-user", "--property=Linger", "--value"], capture_output=True, text=True)
    if linger.stdout.strip() == "no":
        print("    ojo: para que siga corriendo sin una sesión abierta: loginctl enable-linger \"$USER\"")


def _uid() -> int:
    import os

    return os.getuid()
