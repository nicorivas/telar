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
pendiente hasta que quien administra el bus la aprueba (`telar bus aprobar`); mientras, tu telar espera.

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
    p.add_argument("--sin-servicio", action="store_true", help="no instalar el servicio")
    p.add_argument("--sin-agente", action="store_true", help="no instalar los ganchos del agente")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    ruta = ruta_config()
    try:
        pasos = _plan(ctx, o, ruta)
    except ErrorDeUso as e:
        return _comun.queja(str(e))
    for _, que in pasos:
        print(f"  → {que}")
    if not pasos:
        print("  todo estaba instalado")
    if o.seco:
        return 0
    if pasos and not o.si:
        if not sys.stdin.isatty():
            return _comun.queja("¿sigo? sin terminal no puedo preguntar: --si para hacerlo, --seco para solo mirar")
        if input("¿sigo? [s/N] ").strip().lower() not in ("s", "si", "sí", "y", "yes"):
            print("no hice nada")
            return 1
    for hacer, que in pasos:
        try:
            hacer()
        except (OSError, subprocess.CalledProcessError, ValueError) as e:
            return _comun.queja(f"{que}: {e}")

    from telar import config as mod_config
    from telar.ordenes import doctor

    # como la orden `telar doctor`: un módulo que no se lee se deja fuera, para que doctor lo diga
    ctx.config = mod_config.cargar(ruta if ruta.exists() else None, tolerar_modulos=True)
    print()
    return doctor.main([], ctx)


class ErrorDeUso(Exception):
    """Lo pedido no se puede hacer; el mensaje es para la persona."""


def _plan(ctx, o, ruta: Path) -> list[tuple]:
    """Los pasos que faltan: (función, qué hace)."""
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
        hay_bus = _unirse(ctx, o, ruta, pasos, hay_bus)

    if not o.sin_servicio:
        donde, texto = instalacion.servicio(nodo=hay_bus, equipo=_hay_equipo(ruta))
        if not donde.exists() or donde.read_text(encoding="utf-8") != texto:
            que = "instalar" if not donde.exists() else "actualizar"
            pasos.append((lambda: _servicio(donde, texto), f"{que} el servicio de telar serve ({donde})"))
    if not o.sin_agente and not _ganchos_puestos(ctx):
        from telar.ordenes import agente

        pasos.append((lambda: agente.main(["instalar", "--si"], ctx), "poner los ganchos, la skill y el mod de Claude Code"))
    return pasos


#: cómo instalar lo que un equipo suele pedir, para decirlo cuando falta
PISTAS = {"tmux": "brew install tmux (Mac) · apt install tmux (Linux)", "claude": "https://claude.com/download",
          "tailscale": "https://tailscale.com/download, y pídele a quien administra que te invite a su red",
          "uv": "https://docs.astral.sh/uv/", "npm": "https://nodejs.org", "git": "brew install git"}


def _unirse(ctx, o, ruta: Path, pasos: list, hay_bus: bool) -> bool:
    """Los pasos de `--unirse`: pedir entrar, el bus, el repositorio y los módulos del equipo."""
    import json

    from telar import unirse

    try:
        equipo = unirse.buscar(Path(o.unirse).expanduser() if o.unirse else None)
    except unirse.ErrorDeUnirse as e:
        raise ErrorDeUso(str(e)) from None
    if equipo is None:
        raise ErrorDeUso(f"aquí no hay un equipo: corre esto dentro del clon del repositorio del equipo (el que trae "
                         f"{unirse.NOMBRE_EQUIPO}), o dale su carpeta: --unirse ~/ruta/al/repo")
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
            quien = equipo.administra or "quien administra el bus"
            print(f"  pedido {r.get('id', '?')}: {r.get('estado', '?')}. Avísale a {quien} para que lo apruebe "
                  f"(telar bus aprobar {r.get('id', '?')}); tu telar se conecta solo cuando lo haga.")

        pasos.append((lambda: _sin_error(pedir), f"pedir entrar al bus de «{equipo.nombre}» como «{persona}» "
                                                 f"(el secreto se genera aquí, en {o.token}; viaja solo su hash)"))
        bloque = instalacion.bloque_bus(equipo.bus, o.token, persona)
        pasos.append((lambda: _agregar(ruta, bloque), f"unirse al bus {equipo.bus}"))
        hay_bus = True
    if not any(r.nombre == equipo.nombre for r in getattr(ctx.config, "repos", ()) or ()):
        bloque_repo = (f"\n# el repositorio del equipo {equipo.nombre} (lo escribió `telar instalar --unirse`)\n"
                       f"[repos.{equipo.nombre}]\nruta = {json.dumps(str(equipo.repo))}\n")
        pasos.append((lambda: _agregar(ruta, bloque_repo), f"agregar el repositorio {equipo.repo} como «{equipo.nombre}»"))
    instalados = {m.nombre for m in getattr(ctx.config, "modulos", ())}
    for nombre, fuente in equipo.modulos.items():
        if nombre not in instalados:
            pasos.append((lambda f=fuente: _modulo(ctx, f), f"instalar el módulo {nombre} del equipo ({fuente})"))
    return hay_bus


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
