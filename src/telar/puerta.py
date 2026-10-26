"""La puerta: una sola dirección para todas las personas de un servidor, como un servidor web normal.

En un servidor con alojados (telar.alojamiento) cada persona tiene su usuario de Linux y su propio `telar serve`:
sus hilos y sus agentes corren con sus permisos, y los de una no leen los de otra. Antes, cada uno publicaba su
página en un puerto propio de la red, con su llave; ahora todos entran por la misma dirección (la de Tailscale del
servidor, `https://<máquina>.<red>.ts.net`) y la puerta sabe quién es cada uno y le pasa el pedido a su telar:

    navegador ── https ──▶ tailscale serve ── /run/telar/puerta/puerta.sock ──▶ la puerta
                                                                                  │ quién es: `tailscale whois`
                                                                                  ▼
                                                     /run/telar/<usuario>/web.sock ──▶ el `telar serve` de esa persona

Quién es: Tailscale lo sabe. `tailscale serve` le agrega a cada pedido la dirección de la máquina que lo hace
(`X-Forwarded-For`, la última de la lista: las de antes las pudo escribir el navegador) y `tailscale whois` dice de
qué cuenta es; eso funciona también con quien entra desde otra red a la que se compartió el servidor. La cuenta se
busca en la tabla de la puerta (`/etc/telar/puerta.toml`, la de quien administra, y `/etc/telar/alojados.d/*.json`,
la que escribe el ayudante de root al alojar a alguien). Quien no está, no entra.

De qué se fía y por qué:

- Del `X-Forwarded-For` solo porque al socket de la puerta llega nada más que root (tailscaled): su carpeta es de la
  puerta y nadie más la cruza. Un proceso del servidor que llegue por la red de Tailscale (de la misma máquina) viene
  desde una IP del servidor mismo, que `whois` daría como la de quien administra: esa no se acepta nunca.
- El telar de cada persona confía en lo que le llega por su socket de la puerta (`telar serve --web-socket`): no pide
  la llave de su página. Lo que lo cuida es la carpeta del socket, `/run/telar/<usuario>/` (2750, de esa persona y
  del grupo telar-puerta): solo ella y la puerta la cruzan.
- Escribir desde otra página no: un pedido que cambia algo tiene que venir con `Origin` igual a la dirección pedida,
  como en la página de siempre. A un socket, `tailscale serve` le manda `Host: localhost` y la dirección de verdad
  en `X-Forwarded-Host` (que pisa, como el `X-Forwarded-For`): la puerta la usa, y se la pasa a cada telar como su
  `Host`, para que su propia comprobación de origen (y la de la terminal) vea lo mismo que el navegador.

Cómo se instala: `servidor/telar-puerta-instalar` (root), y `tailscale serve --bg --https=443
unix:/run/telar/puerta/puerta.sock`. Necesita el extra «serve».
"""


import ipaddress
import json
import re
import subprocess
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG = Path("/etc/telar/puerta.toml")
#: donde `servidor/telar-puerta-instalar` deja el telar de la puerta (un venv propio): se actualiza a mano, con root
INSTALADA = Path("/opt/telar-puerta")
ALOJADOS = Path("/etc/telar/alojados.d")
#: la carpeta de los sockets: `<SOCKETS>/<usuario>/web.sock` el de cada persona, `<SOCKETS>/puerta/puerta.sock` la puerta
SOCKETS = Path("/run/telar")
#: cuánto se recuerda lo que dijo `tailscale whois` de una dirección
MEMORIA_WHOIS = 60.0

REDES_TAILSCALE = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))
USUARIO = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
#: lo que no pasa de un lado al otro: lo que es de cada conexión (RFC 9110 §7.6.1) y la cookie de la página (cada
#: telar de detrás usa la misma, con su valor: en una sola dirección se pisarían, y detrás de la puerta no hace falta)
SALTO = frozenset({"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
                   "transfer-encoding", "upgrade", "content-length"})


class ErrorDePuerta(Exception):
    def __init__(self, mensaje: str, codigo: int = 403) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def socket_de(usuario: str, base: Path = SOCKETS) -> Path:
    return base / usuario / "web.sock"


@dataclass
class Tabla:
    """Cuenta de Tailscale → usuario del servidor, y la dirección pública de la puerta."""

    personas: dict[str, str] = field(default_factory=dict)
    url: str = ""
    problemas: list[str] = field(default_factory=list)


def leer_tabla(config: Path = CONFIG, alojados: Path = ALOJADOS) -> Tabla:
    """La tabla de la puerta: `[personas]` de su configuración (quien administra, y a mano) y la cuenta de cada
    alojado (`tailscale` en su archivo del registro). Una cuenta que aparece dos veces con usuarios distintos no
    entra: no se adivina."""
    t = Tabla()
    vistos: dict[str, set[str]] = {}

    def anotar(cuenta: object, usuario: object, de: str) -> None:
        if not isinstance(cuenta, str) or not isinstance(usuario, str) or not cuenta.strip():
            return
        if not USUARIO.fullmatch(usuario):
            t.problemas.append(f"{de}: «{usuario}» no es un nombre de usuario")
            return
        vistos.setdefault(cuenta.strip().lower(), set()).add(usuario)

    try:
        datos = tomllib.loads(config.read_text(encoding="utf-8"))
    except FileNotFoundError:
        datos = {}
        t.problemas.append(f"no hay {config}")
    except (OSError, tomllib.TOMLDecodeError) as e:
        datos = {}
        t.problemas.append(f"{config}: {e}")
    t.url = str(datos.get("url") or "").rstrip("/")
    for cuenta, usuario in (datos.get("personas") or {}).items():
        anotar(cuenta, usuario, str(config))
    try:
        archivos = sorted(alojados.glob("*.json"))
    except OSError:
        archivos = []
    for a in archivos:
        try:
            d = json.loads(a.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            t.problemas.append(f"{a}: {e}")
            continue
        if isinstance(d, dict):
            anotar(d.get("tailscale"), d.get("nombre"), str(a))
    for cuenta, usuarios in vistos.items():
        if len(usuarios) == 1:
            t.personas[cuenta] = next(iter(usuarios))
        else:
            t.problemas.append(f"la cuenta {cuenta} aparece con varios usuarios ({', '.join(sorted(usuarios))}): no entra")
    return t


def version_instalada(base: Path = INSTALADA) -> str:
    """La versión de telar instalada para la puerta ('' si no está): de los metadatos de su venv, sin correrla."""
    for meta in sorted(base.glob("lib/python*/site-packages/telar-*.dist-info/METADATA")):
        try:
            for linea in meta.read_text(encoding="utf-8").splitlines():
                if linea.startswith("Version:"):
                    return linea.split(":", 1)[1].strip()
                if not linea.strip():
                    break
        except OSError:
            continue
    return ""


def _tupla(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


def estado(usuario: str, *, config: Path = CONFIG, base: Path = INSTALADA) -> dict | None:
    """La puerta de esta máquina vista por `usuario`: None si no hay puerta. `administra`: si es la persona de la
    configuración de la puerta (quien la instaló: la puede actualizar); `atras`: si su versión es más vieja que la
    de este telar; `actualizar`: la orden para ponerla al día."""
    from telar import __version__

    if not config.exists():
        return None
    try:
        datos = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        datos = {}
    cuentas = [c for c, u in (datos.get("personas") or {}).items() if u == usuario]
    v = version_instalada(base)
    salida = {"version": v, "url": str(datos.get("url") or "").rstrip("/"), "administra": bool(cuentas),
              "atras": bool(v) and _tupla(v) < _tupla(__version__), "telar": __version__}
    if cuentas:
        salida["actualizar"] = (f"sudo sh servidor/telar-puerta-instalar --dueno {usuario} --cuenta {cuentas[0]} "
                                f"--version {__version__}")
    return salida


def cliente(cabeceras: dict[str, str]) -> str:
    """La dirección de la máquina que pide: la última de `X-Forwarded-For`, la que agregó `tailscale serve` (las de
    antes las pudo poner quien pide). '' si no hay."""
    xff = cabeceras.get("x-forwarded-for", "")
    ultima = xff.split(",")[-1].strip() if xff else ""
    try:
        return str(ipaddress.ip_address(ultima))
    except ValueError:
        return ""


def host(cabeceras: dict[str, str]) -> str:
    """La dirección a la que se pidió: `X-Forwarded-Host`, que pone `tailscale serve` (a un socket le manda `Host:
    localhost`, y pisa el `X-Forwarded-Host` que traiga el navegador), o el `Host` si no viene."""
    return cabeceras.get("x-forwarded-host") or cabeceras.get("host", "")


def whois(ip: str) -> dict:
    """Lo que dice Tailscale de una dirección de su red: {"cuenta": LoginName, "maquina": nombre}; {} si no sabe."""
    try:
        r = subprocess.run(["tailscale", "whois", "--json", ip], capture_output=True, text=True, timeout=10)
        d = json.loads(r.stdout) if r.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {}
    perfil, nodo = d.get("UserProfile") or {}, d.get("Node") or {}
    return {"cuenta": str(perfil.get("LoginName") or ""), "maquina": str(nodo.get("ComputedName") or nodo.get("Name") or "")}


def mis_direcciones() -> set[str]:
    """Las direcciones de Tailscale de esta máquina: un pedido que viene de ellas viene de un proceso del servidor."""
    try:
        r = subprocess.run(["tailscale", "ip"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    salida = set()
    for linea in r.stdout.split():
        try:
            salida.add(str(ipaddress.ip_address(linea.strip())))
        except ValueError:
            pass
    return salida


class Identificar:
    """De la dirección que pide al usuario del servidor, con lo que dijo `whois` en memoria un rato."""

    def __init__(self, tabla: Tabla, *, quien=whois, propias=mis_direcciones, reloj=time.monotonic) -> None:
        self.tabla, self._quien, self._reloj = tabla, quien, reloj
        self._buscar_propias = propias if callable(propias) else (lambda: set(propias))
        self._propias = self._buscar_propias()
        self._visto: dict[str, tuple[float, dict]] = {}

    def __call__(self, ip: str) -> tuple[str, str]:
        """(usuario, cuenta); ErrorDePuerta si no entra."""
        if not ip:
            raise ErrorDePuerta("la puerta no sabe desde dónde viene este pedido (falta X-Forwarded-For): "
                                "¿llegó por `tailscale serve`?", 400)
        if not any(ipaddress.ip_address(ip) in red for red in REDES_TAILSCALE):
            raise ErrorDePuerta("solo se entra desde la red de Tailscale")
        if not self._propias:
            # sin saber las direcciones del servidor no se distingue un proceso de aquí de quien administra
            self._propias = self._buscar_propias()
            if not self._propias:
                raise ErrorDePuerta("la puerta no sabe las direcciones de este servidor (`tailscale ip`)", 503)
        if ip in self._propias:
            raise ErrorDePuerta("desde el servidor mismo no se entra por la puerta")
        ahora = self._reloj()
        guardado = self._visto.get(ip)
        if guardado and ahora - guardado[0] < MEMORIA_WHOIS:
            datos = guardado[1]
        else:
            datos = self._quien(ip)
            if datos.get("cuenta"):
                self._visto[ip] = (ahora, datos)
        cuenta = (datos.get("cuenta") or "").strip().lower()
        if not cuenta:
            raise ErrorDePuerta("Tailscale no dice de quién es esta máquina", 403)
        usuario = self.tabla.personas.get(cuenta)
        if not usuario:
            raise ErrorDePuerta(f"la cuenta {cuenta} no tiene lugar en este servidor. Para pedirlo, desde tu "
                                f"máquina: `telar servidor pedir`")
        return usuario, cuenta


PAGINA_ERROR = """<!doctype html><meta charset="utf-8"><title>telar</title>
<style>body{{font:15px ui-monospace,monospace;background:#1e1e2e;color:#cdd6f4;padding:3em;max-width:60ch}}
code{{color:#89b4fa}}</style><p>telar · la puerta del servidor</p><p>{texto}</p>"""


def crear(tabla: Tabla | None = None, *, identificar: Identificar | None = None, sockets: Path = SOCKETS):
    """La app de la puerta (ASGI): cada pedido, HTTP o WebSocket, al telar de quien lo hace."""
    import asyncio
    import contextlib
    from html import escape
    from urllib.parse import urlsplit

    import httpx
    from fastapi import FastAPI, Request, WebSocket
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from starlette.background import BackgroundTask
    from websockets.asyncio.client import unix_connect
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    estado = {"tabla": tabla or leer_tabla(), "leida": time.monotonic()}
    ident = identificar or Identificar(estado["tabla"])
    clientes: dict[str, httpx.AsyncClient] = {}
    cerrando: set = set()  # los cierres de terminales en curso (una tarea sin referencia se la lleva el recolector)

    def tabla_al_dia() -> None:
        # la tabla cambia al alojar a alguien: se relee cada tanto, sin reiniciar la puerta
        if identificar is None and time.monotonic() - estado["leida"] > 30:
            estado["tabla"], estado["leida"] = leer_tabla(), time.monotonic()
            ident.tabla = estado["tabla"]

    async def de_quien(cabeceras: dict[str, str]) -> tuple[str, str]:
        tabla_al_dia()
        # `tailscale whois` es un proceso: fuera del bucle, para no detener a los demás mientras contesta
        return await asyncio.to_thread(ident, cliente(cabeceras))

    def cliente_de(usuario: str) -> httpx.AsyncClient:
        c = clientes.get(usuario)
        if c is None:
            c = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(socket_de(usuario, sockets))),
                                  timeout=httpx.Timeout(300, connect=5), follow_redirects=False)
            clientes[usuario] = c
        return c

    def error(texto: str, codigo: int, html: bool):
        if html:
            return HTMLResponse(PAGINA_ERROR.format(texto=escape(texto)), status_code=codigo)
        return JSONResponse({"detail": texto}, status_code=codigo)

    @contextlib.asynccontextmanager
    async def vida(_app):
        yield
        for c in clientes.values():
            await c.aclose()

    app = FastAPI(title="telar puerta", docs_url=None, redoc_url=None, openapi_url=None, lifespan=vida)

    @app.api_route("/{ruta:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def pasar(request: Request, ruta: str):
        cab = {k.lower(): v for k, v in request.headers.items()}
        html = "text/html" in cab.get("accept", "")
        try:
            usuario, cuenta = await de_quien(cab)
        except ErrorDePuerta as e:
            return error(str(e), e.codigo, html)
        origen, pedido_a = cab.get("origin", ""), host(cab)
        if request.method not in ("GET", "HEAD", "OPTIONS") and origen and urlsplit(origen).netloc != pedido_a:
            return error("desde otra página, no", 403, False)
        fuera = SALTO | {"cookie", "x-telar-persona", "host"}
        salen = [(k.decode("latin-1"), v.decode("latin-1")) for k, v in request.headers.raw
                 if k.decode("latin-1").lower() not in fuera]
        salen += [("host", pedido_a), ("x-telar-persona", usuario)]
        destino = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        c = cliente_de(usuario)
        pedido = c.build_request(request.method, f"http://telar{destino}", headers=salen, content=request.stream())
        try:
            r = await c.send(pedido, stream=True)
        except (httpx.ConnectError, FileNotFoundError, ConnectionRefusedError):
            return error(f"tu telar en el servidor no está corriendo ({usuario}): espera un poco y recarga; si "
                         f"sigue, avísale a quien administra el servidor", 502, html)
        except httpx.HTTPError as e:
            return error(f"tu telar no contestó: {type(e).__name__}", 504, html)
        vuelven = [(k, v) for k, v in r.headers.multi_items() if k.lower() not in SALTO]
        respuesta = StreamingResponse(r.aiter_raw(), status_code=r.status_code, background=BackgroundTask(r.aclose))
        respuesta.raw_headers = [(k.encode("latin-1"), v.encode("latin-1")) for k, v in vuelven]
        return respuesta

    @app.websocket("/{ruta:path}")
    async def pasar_ws(ws: WebSocket, ruta: str):
        cab = {k.lower(): v for k, v in ws.headers.items()}
        try:
            usuario, _ = await de_quien(cab)
        except ErrorDePuerta:
            await ws.close(code=1008)
            return
        pedido_a = host(cab) or "telar"
        destino = ws.url.path + (f"?{ws.url.query}" if ws.url.query else "")
        extra = {k: v for k, v in cab.items() if k in ("origin", "user-agent")}
        extra["x-telar-persona"] = usuario
        try:
            otro = await unix_connect(str(socket_de(usuario, sockets)), f"ws://{pedido_a}{destino}",
                                      additional_headers=extra, max_size=None, open_timeout=10,
                                      close_timeout=2)
        except (OSError, InvalidStatus, TimeoutError):
            await ws.close(code=1011)
            return
        await ws.accept()

        async def hacia_atras():
            while True:
                m = await ws.receive()
                if m["type"] == "websocket.disconnect":
                    return
                if m.get("bytes") is not None:
                    await otro.send(m["bytes"])
                elif m.get("text") is not None:
                    await otro.send(m["text"])

        async def hacia_adelante():
            async for m in otro:
                if isinstance(m, bytes):
                    await ws.send_bytes(m)
                else:
                    await ws.send_text(m)

        tareas = [asyncio.create_task(hacia_atras()), asyncio.create_task(hacia_adelante())]
        try:
            hecho, _ = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tareas:
                t.cancel()
            await asyncio.gather(*tareas, return_exceptions=True)
            # el saludo de cierre con su telar, aparte: quien pidió no lo espera
            cierre = asyncio.create_task(otro.close())
            cerrando.add(cierre)
            cierre.add_done_callback(cerrando.discard)
        # si cerró el de atrás (su telar), se le cierra al navegador; si cerró el navegador, ya está
        if tareas[1] in hecho:
            try:
                await ws.close()
            except (RuntimeError, ConnectionClosed):
                pass

    return app
