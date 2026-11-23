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
        _correr(uvicorn, uvicorn.Config(api.app, host="127.0.0.1", port=o.puerto, log_level="warning"), equipo, nodo)
        return 0
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
    _correr(uvicorn, uvicorn.Config(api.app, uds=str(sock), log_level="warning"), equipo, nodo)
    return 0


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


def _correr(uvicorn, principal, equipo, nodo=None) -> None:
    """La API y, si se pidieron, la página del equipo y el nodo del bus: todo en el mismo bucle. Si uno se
    cae, se cae el proceso entero (y el servicio lo levanta): uno a medias no sirve."""
    import asyncio

    # `equipo`: los servidores de más (la página del equipo, la página de telar), cada uno en su puerto
    extra = equipo if isinstance(equipo, list) else ([equipo] if equipo else [])
    servidores = [uvicorn.Server(principal), *(uvicorn.Server(c) for c in extra)]

    async def todos():
        tareas = [asyncio.create_task(s.serve()) for s in servidores]
        if nodo is not None:
            tareas.append(asyncio.create_task(nodo.correr()))
        hecho, _ = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
        for s in servidores:
            s.should_exit = True
        if nodo is not None:
            tareas[-1].cancel()  # el nodo no mira should_exit: se le cancela
        await asyncio.gather(*tareas, return_exceptions=True)
        for t in hecho:
            if not t.cancelled():
                t.result()

    asyncio.run(todos())
