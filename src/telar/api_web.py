"""La página de telar en el navegador, servida por `telar serve --web` (antes, el panel en Node).

Es una app aparte de la API del socket (telar.api), que monta adentro bajo `/api`, y escucha en la IP de
Tailscale. Como el panel: se entra con la llave de `~/.config/telar/panel.llave` (`?k=…` la primera vez;
después queda en una cookie HttpOnly, la misma del panel, así que entrar a uno entra a los dos), y lo que
escribe (POST, PUT, DELETE) tiene que venir de una página de aquí: un sitio ajeno no puede fingir el
`Origin`. Sin `Origin` (curl, la CLI) manda la llave.

    GET  /                  la página (se arma pantalla por pantalla: docs/propuestas/dashboard-fuera-de-vscode.md)
    GET  /compartir         la misma página, abierta en «compartir» (lo que el teléfono le comparte a la app)
    GET  /maquinas          la página madre: tus máquinas, para elegir en cuál abrir la página
    GET  /maquinas.json     esta máquina y las del bus que sirven su página, cada una con su enlace para entrar
    GET  /entrar?…          entrar con un boleto de otra máquina (sin la llave de esta): ver `boleto`
    GET  /manifest.webmanifest, /sw.js, /icono-….png   lo que deja instalarla como app (sin llave: web/app)
    GET  /estatico/…        sus archivos (src/telar/web; xterm.js en estatico/xterm)
    WS   /pty?hilo=…        la terminal de un hilo de esta máquina (telar.terminal), con la llave y desde aquí;
                            &maquina=… la de un hilo de otra máquina: se reenvía al /pty de su página (la
                            dirección viene en su foto del bus), presentándose con el token del bus. Ese
                            token también abre el /pty de aquí: es lo que comparten las máquinas de una persona
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
LIBRES = (*APP, "/entrar")

#: cuánto vale un boleto para entrar a otra máquina (ver `boleto`)
BOLETO_SEGUNDOS = 60


def _firma(token: str, de: str, para: str, expira: int) -> str:
    import hashlib
    import hmac

    return hmac.new(token.encode(), f"entrar|{de}|{para}|{expira}".encode(), hashlib.sha256).hexdigest()


def boleto(token: str, de: str, para: str, web: str, ahora: float | None = None) -> str:
    """La dirección para entrar a la página de otra máquina sin su llave: cada máquina tiene la suya, pero todas
    comparten el token del bus. El boleto lo firma esta máquina con ese token, nombra a quién va y vence en
    BOLETO_SEGUNDOS; la otra lo comprueba (`/entrar`), lo acepta una sola vez y le da su cookie."""
    import time
    from urllib.parse import urlencode

    expira = int((ahora if ahora is not None else time.time()) + BOLETO_SEGUNDOS)
    return f"{web}/entrar?{urlencode({'de': de, 'e': expira, 'f': _firma(token, de, para, expira)})}"


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


def _token_del_bus(config) -> str:
    """El secreto que comparten las máquinas de una persona (`[bus] token`); "" sin bus."""
    if config is None:
        return ""
    try:
        from telar import bus as mod_bus

        return mod_bus._token(config) if mod_bus.hay_bus(config) else ""
    except Exception:  # noqa: BLE001 - sin token, solo entra el navegador
        return ""


def crear(api_app, clave: str | None = None, dev: bool = False, config=None) -> FastAPI:
    """La página. `config` (la de `telar serve`) da el token del bus y las fotos de las otras máquinas: sin
    ella, las terminales son solo de esta."""
    clave = clave or llave()
    token = _token_del_bus(config)
    def nombre_aqui() -> str:
        """El nombre de esta máquina (en el bus, o su hostname); "" sin configuración."""
        if config is None:
            return ""
        try:
            from telar import bus as mod_bus

            return mod_bus.maquina(config)
        except Exception:  # noqa: BLE001 - sin nombre, no hay boletos
            return ""

    usados: dict[str, int] = {}  # los boletos ya usados, hasta que vencen: cada uno sirve una vez
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

    @app.get("/entrar")
    def entrar(de: str = "", e: int = 0, f: str = ""):
        import hmac
        import time

        ahora, aqui = int(time.time()), nombre_aqui()
        for k in [k for k, v in usados.items() if v < ahora]:
            del usados[k]
        valido = (bool(token) and bool(aqui) and ahora <= e <= ahora + BOLETO_SEGUNDOS + 5 and f not in usados
                  and hmac.compare_digest(f, _firma(token, de, aqui, e)))
        if not valido:
            return PlainTextResponse("telar: ese enlace para entrar no vale (venció, ya se usó, o no es de una de tus "
                                     "máquinas). Vuelve a «máquinas» y elige de nuevo.", status_code=403)
        usados[f] = e
        r = RedirectResponse("/", status_code=302)
        r.set_cookie(COOKIE, clave, httponly=True, samesite="lax", max_age=31536000, path="/")
        return r

    @app.get("/maquinas")
    def maquinas():
        return FileResponse(CARPETA / "maquinas.html", media_type="text/html; charset=utf-8")

    @app.get("/maquinas.json")
    def maquinas_json():
        """Esta máquina y las otras de la persona que sirven su página (su foto del bus trae la dirección), con
        un boleto nuevo para entrar a cada una. Las fotos viejas salen como fuera de línea, sin enlace."""
        aqui = nombre_aqui()
        lista = [{"nombre": aqui or "esta", "aqui": True, "en_linea": True, "edad": 0, "url": "/"}]
        if config is not None:
            from telar import espejo

            for x in espejo.leer_todos(config):
                if x.get("nombre") == aqui or x.get("error"):
                    continue
                web = x.get("web") or ""
                lista.append({
                    "nombre": x["nombre"], "aqui": False, "en_linea": x["en_linea"], "edad": x["edad"],
                    "hilos": sum(1 for h in x.get("hilos", []) if h.get("vivo")), "version": x.get("telar", ""),
                    "url": boleto(token, aqui, x["nombre"], web) if web and token and x["en_linea"] else "",
                })
        return {"aqui": aqui, "maquinas": lista}

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
    async def terminal(ws: WebSocket, hilo: str = "", cols: int = 100, rows: int = 30, maquina: str = ""):
        # el middleware de arriba no ve los WebSocket: la llave y el origen se miran aquí. Un WebSocket
        # escribe en un hilo, así que el `Origin` es obligatorio (un navegador siempre lo manda). Otra
        # máquina de la persona (su página, reenviando) entra con el token del bus, que un navegador no
        # puede poner en un WebSocket
        origen = ws.headers.get("origin", "")
        navegador = (secrets.compare_digest(ws.cookies.get(COOKIE, ""), clave) and bool(origen)
                     and urlsplit(origen).netloc == ws.headers.get("host", ""))
        otra_maquina = bool(token) and secrets.compare_digest(ws.headers.get("authorization", ""), f"Bearer {token}")
        if not (navegador or otra_maquina) or not hilo:
            await ws.close(code=1008)
            return
        from telar import terminal as mod_terminal

        aqui = ""
        if maquina and config is not None:
            from telar import bus as mod_bus

            aqui = mod_bus.maquina(config)
        if maquina and maquina != aqui:
            # solo desde el navegador: una máquina no le reenvía a una tercera
            if not navegador:
                await ws.close(code=1008)
                return
            from telar import espejo

            await ws.accept()
            web = espejo.web_de(config, maquina) if config is not None else ""
            await mod_terminal.reenviar(ws, web, hilo, maquina, cols, rows, token)
            return
        await ws.accept()
        await mod_terminal.puente(ws, hilo, cols, rows)

    if dev:
        @app.get("/dev/cambios")
        def cambios():
            return StreamingResponse(_cambios(), media_type="text/event-stream")

    app.mount("/estatico", StaticFiles(directory=CARPETA), name="estatico")
    app.mount("/api", api_app)
    return app
