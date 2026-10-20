"""La página de telar en el navegador, servida por `telar serve --web` (antes, el panel en Node).

Es una app aparte de la API del socket (telar.api), que monta adentro bajo `/api`, y escucha en la IP de
Tailscale. Como el panel: se entra con la llave de `~/.config/telar/panel.llave` (`?k=…` la primera vez;
después queda en una cookie HttpOnly, la misma del panel, así que entrar a uno entra a los dos), y lo que
escribe (POST, PUT, DELETE) tiene que venir de una página de aquí: un sitio ajeno no puede fingir el
`Origin`. Sin `Origin` (curl, la CLI) manda la llave.

    GET  /                  la página (se arma pantalla por pantalla: docs/propuestas/dashboard-fuera-de-vscode.md)
    GET  /compartir         la misma página, abierta en «compartir» (lo que el teléfono le comparte a la app)
    GET  /manifest.webmanifest, /sw.js, /icono-….png   lo que deja instalarla como app (sin llave: web/app)
    GET  /estatico/…        sus archivos (src/telar/web; xterm.js en estatico/xterm)
    WS   /pty?hilo=…        la terminal de un hilo de esta máquina (telar.terminal), con la llave y desde aquí
    GET  /dev/cambios       solo con `--dev`: avisa (server-sent events) cuando cambian los archivos de la página
    *    /api/…             la API de esta máquina (la misma de `telar serve`), detrás de la llave
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

#: la cookie de la llave: el mismo nombre que usaba el panel en Node, para que una app ya instalada siga entrando
COOKIE = "telar_panel"
CARPETA = Path(__file__).parent / "web"
#: lo que deja instalar la página como app (y recibir lo que comparte el teléfono): el manifiesto, los
#: íconos y un service worker. Se sirven sin llave: no dicen nada de nadie, y el navegador los pide sin
#: la cookie
APP = {
    "/manifest.webmanifest": "application/manifest+json", "/sw.js": "text/javascript",
    "/apple-touch-icon.png": "image/png", "/icono-192.png": "image/png", "/icono-512.png": "image/png",
    "/icono-maskable-192.png": "image/png", "/icono-maskable-512.png": "image/png",
}
LIBRES = tuple(APP)


def ruta_llave() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "telar" / "panel.llave"


def llave() -> str:
    """La llave del panel; si no hay, se crea (solo su dueño la lee)."""
    p = ruta_llave()
    try:
        texto = p.read_text(encoding="utf-8").strip()
        if texto:
            return texto
    except OSError:
        pass
    p.parent.mkdir(parents=True, exist_ok=True)
    nueva = secrets.token_urlsafe(24)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(nueva + "\n")
    return nueva


def _mismo_origen(request: Request) -> bool:
    origen = request.headers.get("origin")
    if not origen:
        return True  # curl, la CLI: manda la llave
    return urlsplit(origen).netloc == request.headers.get("host", "")


def _cache(ruta: str) -> str:
    """Qué puede guardar el navegador. Entre el laptop y el servidor hay ~220 ms de ida y vuelta y poco ancho:
    xterm.js (medio mega) se bajaba de nuevo en cada hilo que se abría. Lo copiado de afuera (xterm) no
    cambia entre versiones de telar: se guarda. Lo demás de la página se guarda pero se revalida (un 304
    si no cambió); los datos, nunca."""
    if ruta.startswith("/estatico/xterm/"):
        return "public, max-age=604800"
    if ruta.startswith("/estatico/"):
        return "no-cache"
    return "no-store"


#: lo que, al cambiar, recarga la página en modo desarrollo (lo rehace `npm run navegador:watch`)
VIGILADOS = ("app.js", "marco.css", "indice.html")


async def _cambios():
    """Un evento cada vez que cambia un archivo de la página; un latido cada 15 s para que nadie corte."""
    import asyncio

    def firma():
        return tuple((CARPETA / n).stat().st_mtime_ns if (CARPETA / n).exists() else 0 for n in VIGILADOS)

    antes, quieto = firma(), 0.0
    yield ": hola\n\n"
    while True:
        await asyncio.sleep(0.3)
        quieto += 0.3
        ahora = firma()
        if ahora != antes:
            antes, quieto = ahora, 0.0
            yield "data: cambio\n\n"
        elif quieto >= 15:
            quieto = 0.0
            yield ": latido\n\n"


def crear(api_app, clave: str | None = None, dev: bool = False) -> FastAPI:
    clave = clave or llave()
    app = FastAPI(title="telar web", docs_url=None, redoc_url=None, openapi_url=None)
    # comprimido: el JS de la página y de xterm baja a un cuarto, y el JSON de la API también
    from starlette.middleware.gzip import GZipMiddleware

    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def con_llave(request: Request, siguiente):
        ruta = request.url.path
        if ruta in LIBRES:
            return await siguiente(request)
        dada = request.query_params.get("k", "")
        if dada and secrets.compare_digest(dada, clave):
            # la llave en la dirección se cambia por una cookie, y la dirección queda limpia
            r = RedirectResponse(ruta if ruta != "/" else "/", status_code=302)
            r.set_cookie(COOKIE, clave, httponly=True, samesite="lax", max_age=31536000, path="/")
            return r
        if not secrets.compare_digest(request.cookies.get(COOKIE, ""), clave):
            return PlainTextResponse(
                "telar: falta la llave. Ábrela una vez con ?k=<llave> al final de la dirección: es la de "
                "~/.config/telar/panel.llave en esta máquina (la misma del panel). Después queda en una cookie.",
                status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS") and not _mismo_origen(request):
            return JSONResponse({"detail": "desde otra página, no"}, status_code=403)
        r = await siguiente(request)
        r.headers.setdefault("Cache-Control", _cache(ruta))
        r.headers.setdefault("X-Content-Type-Options", "nosniff")
        return r

    @app.get("/")
    @app.get("/compartir")
    def pagina():
        # /compartir es la misma página: app.js mira la dirección y abre «compartir» con lo que llegó
        return FileResponse(CARPETA / "indice.html", media_type="text/html; charset=utf-8")

    def _de_la_app(ruta: str, tipo: str):
        return lambda: FileResponse(CARPETA / "app" / ruta.lstrip("/"), media_type=tipo)

    for ruta, tipo in APP.items():
        app.add_api_route(ruta, _de_la_app(ruta, tipo), methods=["GET"], include_in_schema=False)

    @app.websocket("/pty")
    async def terminal(ws: WebSocket, hilo: str = "", cols: int = 100, rows: int = 30):
        # el middleware de arriba no ve los WebSocket: la llave y el origen se miran aquí. Un WebSocket
        # escribe en un hilo, así que el `Origin` es obligatorio (un navegador siempre lo manda)
        origen = ws.headers.get("origin", "")
        if (not secrets.compare_digest(ws.cookies.get(COOKIE, ""), clave) or not origen
                or urlsplit(origen).netloc != ws.headers.get("host", "") or not hilo):
            await ws.close(code=1008)
            return
        from telar import terminal as mod_terminal

        await ws.accept()
        await mod_terminal.puente(ws, hilo, cols, rows)

    if dev:
        @app.get("/dev/cambios")
        def cambios():
            return StreamingResponse(_cambios(), media_type="text/event-stream")

    app.mount("/estatico", StaticFiles(directory=CARPETA), name="estatico")
    app.mount("/api", api_app)
    return app
