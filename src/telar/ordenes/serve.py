"""`telar serve` — la API de telar: los mismos datos que la CLI, por HTTP, desde un proceso que se queda.

    telar serve                     en el socket Unix de siempre (<estado>/serve/telar.sock), solo para su dueño
    telar serve --socket RUTA       en otro socket (hasta 103 bytes en macOS, 107 en Linux). Si su carpeta no
                                    existe, la crea solo para su dueño; a una que ya estaba (/tmp) no le cambia
                                    los permisos, y avisa si otros entran
    telar serve --puerto 8771       en TCP, solo en 127.0.0.1 (para probar; en una máquina compartida,
                                    cualquier usuario de ella alcanzaría el puerto)
    telar serve --equipo            además, la página del equipo ([equipo]) en la IP de Tailscale y su puerto;
                                    sin nadie en [equipo.personas], avisa y arranca sin ella
    telar serve --web               además, la página de telar (telar.api_web) en la IP de Tailscale, puerto
                                    8780 (--web-puerto), con la llave de la página (~/.config/telar/panel.llave);
                                    con --dev, la página se recarga sola al cambiar sus archivos (scripts/dev.py)
    telar serve --web-socket RUTA   además, la página en ese socket Unix, para la puerta de un servidor con alojados
                                    (telar.puerta): sin llave, porque la cuida la carpeta del socket
                                    (/run/telar/<usuario>/, de la persona y del grupo telar-puerta). Con
                                    --web-url, la dirección que el nodo publica como la de su página
    telar serve --nodo              además, el nodo del bus (lo que hace `telar nodo`), en el mismo proceso:
                                    una máquina, un proceso; y los pedidos al bus de la API van por su
                                    conexión, que queda abierta

La página del equipo es **otra app** (telar.api_equipo), en otro puerto: con la llave de una persona no se
alcanza ninguna ruta de esta API. Mismo proceso, nada compartido entre las dos salvo los archivos.

Lo que sirve y por qué está en telar.api. La documentación de cada ruta, en `/docs` (con --puerto) o
`curl --unix-socket <socket> http://telar/openapi.json`. Necesita el extra «serve»:
`pip install 'telar[serve]'`. Para que arranque solo: `telar instalar` (escribe el servicio de esta
máquina); a mano, `servidor/telar-serve.service` y `servidor/telar-serve.plist`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from telar.ordenes import _comun

AYUDA = "La API de telar: los mismos datos que la CLI, por HTTP, desde un proceso que se queda."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("serve", AYUDA)
    p.epilog = __doc__
    p.add_argument("--socket", default="", help="el socket Unix (por defecto, ~/.local/state/telar/serve/telar.sock)")
    p.add_argument("--puerto", type=int, default=0, help="en TCP, en 127.0.0.1, en vez del socket")
    p.add_argument("--equipo", action="store_true", help="además, la página del equipo ([equipo]), en Tailscale")
    p.add_argument("--nodo", action="store_true", help="además, el nodo del bus (`telar nodo`), en el mismo proceso")
    p.add_argument("--web", action="store_true", help="además, la página de telar en el navegador, en Tailscale")
    p.add_argument("--web-puerto", dest="web_puerto", type=int, default=8780, help="con --web: el puerto")
    p.add_argument("--web-socket", dest="web_socket", default="",
                   help="además, la página en este socket Unix, para la puerta del servidor (sin llave)")
    p.add_argument("--web-url", dest="web_url", default="",
                   help="la dirección de la página que publica el nodo (la de la puerta del servidor)")
    p.add_argument("--dev", action="store_true",
                   help="con --web: la página se recarga sola cuando cambian sus archivos (scripts/dev.py)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        import uvicorn

        from telar import api
    except ImportError as e:
        return _comun.queja(f"falta el extra «serve» ({e.name}): pip install 'telar[serve]'")
    # los sockets, antes de arrancar nada: uno que no cabe o que pisaría un archivo se dice en una línea
    sock = Path(o.socket).expanduser() if o.socket else api.socket_por_defecto()
    ws_sock = Path(o.web_socket).expanduser() if o.web_socket else None
    for ruta, quien in ((None if o.puerto else sock, "--socket" if o.socket else f"el socket de siempre ({sock})"),
                        (ws_sock, "--web-socket")):
        if ruta is None:
            continue
        if (largo := _demasiado_largo(ruta)):
            return _comun.queja(f"{quien}: {largo}")
        if (ruta.exists() or ruta.is_symlink()) and not ruta.is_socket():
            return _comun.queja(f"{quien}: {ruta} ya existe y no es un socket: no lo borro (usa otra ruta)")
    equipo = None
    if o.equipo:
        from telar import equipo as mod_equipo
        from telar import api_equipo
        from telar.ordenes.equipo import ip_de_tailscale

        # la página del equipo es un extra: si no se puede servir, se avisa y el resto arranca igual (sacar a
        # la última persona de [equipo.personas] no puede botar el servicio de la máquina)
        try:
            eq = mod_equipo.cargar()
        except ValueError as e:
            eq = None
            print(f"telar serve: sin la página del equipo: {e}", file=sys.stderr, flush=True)
        if eq is not None and not eq.personas:
            eq = None
            print("telar serve: sin la página del equipo: no hay nadie en [equipo.personas] "
                  "(`telar equipo token ramiro` da una llave)", file=sys.stderr, flush=True)
        if eq is not None:
            host = ip_de_tailscale() or "127.0.0.1"
            equipo = uvicorn.Config(api_equipo.crear(eq), host=host, port=eq.puerto, log_level="warning")
            print(f"telar serve: equipo en http://{host}:{eq.puerto} · {', '.join(sorted(eq.personas))}", flush=True)
    otros = [equipo] if equipo else []
    url_web = ""
    if o.web:
        from telar import api_web
        from telar.ordenes.equipo import ip_de_tailscale

        host = ip_de_tailscale() or "127.0.0.1"
        otros.append(uvicorn.Config(api_web.crear(api.app, dev=o.dev, config=ctx.config), host=host, port=o.web_puerto,
                                    log_level="warning"))
        url_web = f"http://{host}:{o.web_puerto}" if host != "127.0.0.1" else ""
        # dónde contesta la página de verdad, aunque sea 127.0.0.1 (que el nodo no publica): lo dice `/salud`
        api.app.state.web = f"http://{host}:{o.web_puerto}"
        print(f"telar serve: la página en http://{host}:{o.web_puerto} (con la llave de {api_web.ruta_llave()})", flush=True)
    if ws_sock is not None:
        from telar import api_web

        # su carpeta la crea root (2750, de la persona y del grupo de la puerta: `servidor/telar-puerta-instalar`): no
        # se le cambian los permisos aquí, porque son ellos los que dejan pasar solo a la puerta
        if not ws_sock.parent.is_dir():
            print(f"telar serve: sin la página para la puerta: no existe {ws_sock.parent} "
                  "(la crea root al instalar la puerta)", file=sys.stderr, flush=True)
        else:
            if ws_sock.exists():
                ws_sock.unlink()
            otros.append(uvicorn.Config(api_web.crear(api.app, config=ctx.config, puerta=True), uds=str(ws_sock),
                                        log_level="warning"))
            print(f"telar serve: la página para la puerta en {ws_sock}", flush=True)
    if o.web_url:
        url_web = o.web_url.rstrip("/")
    equipo = otros
    # el registro de este servicio, con tope al arrancar (bajo launchd es un archivo que nadie rota; el nodo,
    # si va, lo sigue recortando cada tanto)
    from telar import salida

    salida.recortar_registro()
    nodo = None
    if o.nodo:
        from telar import bus as mod_bus
        from telar.ordenes.nodo import Nodo

        if not mod_bus.hay_bus(ctx.config):
            return _comun.queja("--nodo: no hay bus ([bus] url en la configuración)")
        nodo = Nodo(ctx, web=url_web)
        print("telar serve: con el nodo del bus", flush=True)
    if o.puerto:
        principal = uvicorn.Config(api.app, host="127.0.0.1", port=o.puerto, log_level="warning")
        return _correr(uvicorn, principal, equipo, nodo) or 0
    # solo su dueño entra a la carpeta del socket: uvicorn le pone al socket mismo permisos para todos
    # (0666), así que lo que protege es la carpeta, no el archivo. Se la cierra si es de telar: la de siempre, o una
    # que crea ahora. A una que ya estaba (/tmp, la de otro) no se le cambian los permisos: se avisa si otros entran
    carpeta = sock.parent
    nueva = not carpeta.exists()
    carpeta.mkdir(parents=True, exist_ok=True)
    if nueva or not o.socket:
        os.chmod(carpeta, 0o700)
    elif carpeta.stat().st_mode & 0o077:
        print(f"telar serve: otros usuarios de esta máquina entran a {carpeta}, y pueden usar el socket: para que sea "
              "solo tuyo, ponlo en una carpeta que no exista (la crea, solo para ti)", file=sys.stderr, flush=True)
    if sock.is_socket():
        sock.unlink()  # uno que quedó de una vuelta anterior
    print(f"telar serve: {sock}", flush=True)
    # 1 si un pedazo se cayó (y lo dijo en el registro): el servicio lo levanta de nuevo
    return _correr(uvicorn, uvicorn.Config(api.app, uds=str(sock), log_level="warning"), equipo, nodo) or 0


def _largo_maximo() -> int:
    """Lo más larga que puede ser la ruta de un socket Unix, en bytes: lo que cabe en sun_path sin el byte que la
    cierra (103 en macOS y los BSD, 107 en Linux)."""
    return (104 if sys.platform == "darwin" or "bsd" in sys.platform else 108) - 1


def _demasiado_largo(sock: Path) -> str:
    """Qué pasa si la ruta de un socket es más larga de lo que admite un socket Unix, o '' si cabe. Sin esto, uvicorn
    se cae al abrirlo con un traceback."""
    maximo = _largo_maximo()
    largo = len(os.fsencode(str(sock)))
    if largo <= maximo:
        return ""
    return f"la ruta es demasiado larga ({largo} bytes; un socket Unix admite hasta {maximo}): usa una más corta"


#: cuánto espera un servidor, al apagarse, a que terminen las conexiones abiertas (segundos). Sin tope, uvicorn espera
#: para siempre: la página tiene siempre una abierta (los eventos, la terminal), y un servicio que se apagaba a medias
#: quedaba vivo y sordo (26-nov-2026)
PLAZO_APAGAR = 5.0

#: lo que sale del proceso si, caído un pedazo, no alcanzó a apagarse solo en este tiempo (segundos)
PLAZO_SALIR = 20.0

#: cómo sale el proceso cuando no alcanzó a apagarse (una prueba lo cambia)
_salir = os._exit

#: la guardia que lo hace salir, si un pedazo se cayó: sigue después de `_correr`, porque Python, al salir, todavía
#: espera a sus hilos (una prueba la cancela)
guardia: "threading.Timer | None" = None


def _nombre(config) -> str:
    """Cómo se llama en el registro el servidor de esa configuración de uvicorn."""
    if getattr(config, "uds", None):
        return f"el servidor en {config.uds}"
    return f"el servidor en {config.host}:{config.port}"


def _anotar(texto: str) -> None:
    from datetime import datetime

    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} telar serve: {texto}", file=sys.stderr, flush=True)


def _apagando(si: bool) -> None:
    """Que los avisos a la página (`/eventos`, telar.api_web) terminen solos: si no, el servidor espera a la página."""
    if (web := sys.modules.get("telar.api_web")) is not None:
        web.APAGANDO = si


def _correr(uvicorn, principal, equipo, nodo=None) -> int:
    """La API y, si se pidieron, la página del equipo y el nodo del bus: todo en el mismo bucle. Si uno se
    cae, se cae el proceso entero (y el servicio lo levanta): uno a medias no sirve. Lo que se cayó y por qué va al
    registro, y el proceso sale con 1; si no alcanza a apagarse en PLAZO_SALIR, sale igual. Devuelve 0 si se apagó porque
    se lo pidieron (una señal)."""
    import asyncio
    import threading
    import traceback

    # `equipo`: los servidores de más (la página del equipo, la página de telar), cada uno en su puerto
    extra = equipo if isinstance(equipo, list) else ([equipo] if equipo else [])
    configs = [principal, *extra]
    for c in configs:
        # sin tope, un servidor que se apaga espera para siempre a la página, que nunca cierra sus eventos
        if getattr(c, "timeout_graceful_shutdown", None) is None:
            c.timeout_graceful_shutdown = PLAZO_APAGAR
    servidores = [uvicorn.Server(c) for c in configs]
    caida: list[str] = []

    def salir_igual() -> None:
        _anotar(f"no alcanzó a apagarse en {PLAZO_SALIR:g} s: sale igual")
        _salir(1)

    async def mirar_apagado():
        # uno que se apaga (por una señal, a uno solo le llega) apaga los avisos a la página al tiro
        while not any(s.should_exit is True for s in servidores):
            await asyncio.sleep(0.2)
        _apagando(True)

    async def todos():
        mirador = asyncio.create_task(mirar_apagado())
        tareas = [asyncio.create_task(s.serve()) for s in servidores]
        nombres = [_nombre(c) for c in configs]
        if nodo is not None:
            tareas.append(asyncio.create_task(nodo.correr()))
            nombres.append("el nodo del bus")
        hecho, _ = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
        # lo que terminó sin que nadie lo pidiera (una señal) es una caída: se dice qué y por qué, antes de apagar el
        # resto, que puede no terminar nunca
        for t in hecho:
            i = tareas.index(t)
            pedido = i < len(servidores) and bool(getattr(servidores[i], "_captured_signals", None))
            if pedido:
                continue
            if t.cancelled():
                caida.append(f"{nombres[i]} se canceló")
            elif (e := t.exception()) is not None:
                caida.append(f"{nombres[i]} se cayó: {type(e).__name__}: {e}\n"
                             + "".join(traceback.format_exception(e)).rstrip())
            else:
                caida.append(f"{nombres[i]} terminó sin que nadie se lo pidiera")
        if caida:
            for linea in caida:
                _anotar(linea)
            _anotar("apago lo demás y salgo (el servicio me levanta de nuevo)")
            global guardia
            guardia = threading.Timer(PLAZO_SALIR, salir_igual)
            guardia.daemon = True
            guardia.start()
        _apagando(True)
        for s in servidores:
            s.should_exit = True
        if nodo is not None:
            tareas[-1].cancel()  # el nodo no mira should_exit: se le cancela
        _, quedan = await asyncio.wait(tareas, timeout=PLAZO_APAGAR + 2)
        for s in servidores:
            s.force_exit = True  # lo que sigue esperando conexiones, que no espere más
        for t in quedan:
            t.cancel()
        mirador.cancel()
        await asyncio.gather(*tareas, mirador, return_exceptions=True)

    # mientras corre el servicio (y solo entonces: no la CLI ni quien llame a esto en una prueba), lo que dan los
    # proveedores sirve unos segundos a todos los que lo piden (telar.alla, MEMORIA), y lo pesado que solo lee (los
    # proyectos, los pendientes de todo el repositorio) va a un proceso aparte (telar.aparte)
    from telar import alla, aparte

    antes = (alla.MEMORIA, aparte.ACTIVO)
    alla.MEMORIA, aparte.ACTIVO = alla.MEMORIA_SERVE, True
    _apagando(False)
    try:
        asyncio.run(todos())
    finally:
        aparte.apagar()
        alla.MEMORIA, aparte.ACTIVO = antes
        _apagando(False)
    return 1 if caida else 0
