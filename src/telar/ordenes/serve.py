"""`telar serve` — la API de telar: los mismos datos que la CLI, por HTTP, desde un proceso que se queda.

    telar serve                     en el socket Unix de siempre (<estado>/serve/telar.sock), solo para su dueño
    telar serve --socket RUTA       en otro socket
    telar serve --puerto 8771       en TCP, solo en 127.0.0.1 (para probar; en una máquina compartida,
                                    cualquier usuario de ella alcanzaría el puerto)
    telar serve --equipo            además, la página del equipo ([equipo]) en la IP de Tailscale y su puerto
    telar serve --web               además, la página de telar (telar.api_web) en la IP de Tailscale, puerto
                                    8780 (--web-puerto), con la llave de la página (~/.config/telar/panel.llave);
                                    con --dev, la página se recarga sola al cambiar sus archivos (scripts/dev.py)
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
    equipo = None
    if o.equipo:
        from telar import equipo as mod_equipo
        from telar import api_equipo
        from telar.ordenes.equipo import ip_de_tailscale

        try:
            eq = mod_equipo.cargar()
        except ValueError as e:
            return _comun.queja(f"--equipo: {e}")
        if not eq.personas:
            return _comun.queja("--equipo: no hay nadie en [equipo.personas] (`telar equipo token marcelo` da una llave)")
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
        print(f"telar serve: la página en http://{host}:{o.web_puerto} (con la llave de {api_web.ruta_llave()})", flush=True)
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
    sock = Path(o.socket).expanduser() if o.socket else api.socket_por_defecto()
    # solo su dueño entra a la carpeta del socket: uvicorn le pone al socket mismo permisos para todos
    # (0666), así que lo que protege es la carpeta, no el archivo
    sock.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(sock.parent, 0o700)
    if sock.exists():
        sock.unlink()  # uno que quedó de una vuelta anterior
    print(f"telar serve: {sock}", flush=True)
    _correr(uvicorn, uvicorn.Config(api.app, uds=str(sock), log_level="warning"), equipo, nodo)
    return 0


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
