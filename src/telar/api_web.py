"""La página de telar en el navegador, servida por `telar serve --web`: la que reemplaza al panel en Node.

Es una app aparte de la API del socket (telar.api), que monta adentro bajo `/api`, y escucha en la IP de
Tailscale. Como el panel: se entra con la llave de `~/.config/telar/panel.llave` (`?k=…` la primera vez;
después queda en una cookie HttpOnly, la misma del panel, así que entrar a uno entra a los dos), y lo que
escribe (POST, PUT, DELETE) tiene que venir de una página de aquí: un sitio ajeno no puede fingir el
`Origin`. Sin `Origin` (curl, la CLI) manda la llave.

    GET  /                  la página (se arma pantalla por pantalla: docs/propuestas/dashboard-fuera-de-vscode.md)
    GET  /estatico/…        sus archivos (src/telar/web; xterm.js en estatico/xterm)
    WS   /pty?hilo=…        la terminal de un hilo de esta máquina (telar.terminal), con la llave y desde aquí
    *    /api/…             la API de esta máquina (la misma de `telar serve`), detrás de la llave
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

#: la misma cookie que el panel en Node: las cookies no distinguen puertos, y así una llave sirve a los dos
COOKIE = "telar_panel"
CARPETA = Path(__file__).parent / "web"
#: lo que se sirve sin llave: no dice nada de nadie (el navegador lo pide sin la cookie)
LIBRES = ("/manifest.webmanifest", "/icono.svg", "/favicon.ico")


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


def crear(api_app, clave: str | None = None) -> FastAPI:
    clave = clave or llave()
    app = FastAPI(title="telar web", docs_url=None, redoc_url=None, openapi_url=None)

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
        r.headers.setdefault("Cache-Control", "no-store")
        r.headers.setdefault("X-Content-Type-Options", "nosniff")
        return r

    @app.get("/")
    def pagina():
        return FileResponse(CARPETA / "indice.html", media_type="text/html; charset=utf-8")

    if (CARPETA / "manifest.webmanifest").exists():
        @app.get("/manifest.webmanifest")
        def manifiesto():
            return FileResponse(CARPETA / "manifest.webmanifest", media_type="application/manifest+json")

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

    app.mount("/estatico", StaticFiles(directory=CARPETA), name="estatico")
    app.mount("/api", api_app)
    return app
