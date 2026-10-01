"""`telar web` — telar en el navegador del celular: el día y los hilos, tocables.

    telar web                    escucha en la IP de Tailscale (o en localhost si no hay), puerto 8765
    telar web --host IP --puerto N
    telar web --sin-recarga      no recarga la página cuando cambian sus archivos
    telar web --escribir         permite escribirle a un hilo desde la página (por defecto, solo lee)

Una capa fina sobre lo que telar ya sabe: cada pantalla lee un `--json` documentado
(docs/contratos.md), así que la lógica no se duplica. Los hilos de otras máquinas (el laptop) salen
de las fotos que ellas empujan con `telar espejo publicar` (ver `telar.espejo`). Escucha en una sola
interfaz; una dirección abierta a todas (`0.0.0.0`) hay que pedirla con `--abierto`.

**Por defecto solo lee.** Con `--escribir` hay una sola ruta que escribe, `POST /api/enviar`: le
escribe un texto a un hilo vivo, de esta máquina o de otra por `telar enlace`. Es delicado —lo que se
escribe en un hilo lo ejecuta un agente—, así que se defiende: exige un encabezado propio
(`X-Telar`) que una página ajena no puede poner sin permiso, que `Host` y `Origin` sean los de este
servidor (contra páginas ajenas y contra DNS rebinding), tope de tamaño, un envío cada medio segundo, y
anota cada uno en `<estado>/web.log` (el texto no; solo su tamaño). Quien pueda alcanzar el puerto puede
escribirle a tus agentes: por eso escucha solo en Tailscale y la escritura es opt-in.

Los archivos de la página viven en `telar/web/`. Con la recarga puesta (lo normal), editar uno
de ellos recarga la página abierta en el celular en un par de segundos: ese es el punto.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shlex
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urllib.parse import parse_qs

from telar import conversacion, enlace, espejo
from telar.ordenes import _comun

AYUDA = "telar en el navegador del celular: el día y los hilos."
CARPETA = Path(__file__).resolve().parent.parent / "web"
PUERTO = 8765

#: cuánto se reusa la respuesta de cada orden (segundos). `hoy` consulta el calendario y tarda ~10 s:
#: lo rehace un hilo de fondo cada `RENUEVA` segundos, y quien pide recibe lo que haya, aunque el
#: refresco esté a medias; solo se espera si lo último tiene más de `VIGENCIA` (el hilo murió).
VIGENCIA = {"hoy": 300.0, "hilos": 4.0}
RENUEVA = 40.0
_cache: dict[str, tuple[float, bytes]] = {}
_candado = threading.Lock()


def ip_de_tailscale() -> str:
    """La IPv4 de esta máquina en Tailscale, o «» si no hay."""
    if not shutil.which("tailscale"):
        return ""
    r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True)
    return r.stdout.split()[0] if r.returncode == 0 and r.stdout.split() else ""


def _correr(orden: str, argumentos: list[str]) -> bytes:
    r = subprocess.run([sys.executable, "-m", "telar", orden, *argumentos, "--json"],
                       capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(detalle[-1] if detalle else f"telar {orden} salió con {r.returncode}")
    json.loads(r.stdout)  # que sea JSON antes de servirlo
    return r.stdout.encode()


def datos(orden: str, fresco: bool = False) -> bytes:
    """La salida `--json` de una orden, reusada mientras esté vigente."""
    with _candado:
        hora, cuerpo = _cache.get(orden, (0.0, b""))
        if cuerpo and not fresco and time.monotonic() - hora < VIGENCIA[orden]:
            return cuerpo
    cuerpo = _correr(orden, [])
    with _candado:
        _cache[orden] = (time.monotonic(), cuerpo)
    return cuerpo


def mantener_fresco(pausa: float = RENUEVA) -> None:
    """Rehace `hoy` en segundo plano, para que quien abra la página nunca espere al calendario."""
    while True:
        try:
            datos("hoy", fresco=True)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired):
            pass  # el próximo pedido lo intenta y le dice el motivo a quien lo mire
        time.sleep(pausa)


#: cuánto se acepta en una petición de escritura, y cada cuánto se permite una (segundos)
MAX_CUERPO = 64 * 1024
ENTRE_ENVIOS = 0.5
_ultimo_envio = [0.0]


def enlace_para(config, maquina: str):
    """A qué máquina de `[enlaces]` corresponde el nombre que trae el espejo. Con un solo enlace, ese;
    con varios, el que se llame igual. Ninguno → None (y se dice, no se adivina)."""
    por_nombre = next((e for e in config.enlaces if e.nombre == maquina), None)
    if por_nombre is not None:
        return por_nombre
    return config.enlaces[0] if len(config.enlaces) == 1 else None


def enviar(ctx, datos: object) -> tuple[int, dict]:
    """Le escribe un texto a un hilo: `(código http, respuesta)`. `maquina` vacío es esta máquina; con
    nombre, la del espejo, por `telar enlace`. La validación de fondo (hilo vivo, tamaños, saltos de
    línea) es la de la puerta (`telar.enlace.servir`): aquí solo se traduce y se protege."""
    if not isinstance(datos, dict):
        return 400, {"ok": False, "error": "se esperaba un objeto JSON"}
    maquina, hilo, texto, enter = datos.get("maquina", ""), datos.get("hilo"), datos.get("texto"), datos.get("enter", True)
    if not isinstance(maquina, str) or not isinstance(hilo, str) or not hilo or not isinstance(texto, str) or not isinstance(enter, bool):
        return 400, {"ok": False, "error": "faltan o no son válidos maquina, hilo, texto y enter"}
    with _candado:  # un envío cada medio segundo: un dedo torpe o un bucle no inundan a un agente
        ahora = time.monotonic()
        if ahora - _ultimo_envio[0] < ENTRE_ENVIOS:
            return 429, {"ok": False, "error": "muy rápido: un envío a la vez"}
        _ultimo_envio[0] = ahora
    args = [hilo, *(["enter"] if enter else [])]
    if not maquina:
        r = enlace.servir(ctx, shlex.join(["enviar", *args]), texto.encode())
    else:
        destino = enlace_para(ctx.config, maquina)
        if destino is None:
            return 404, {"ok": False, "error": f"no sé a qué enlace corresponde «{maquina[:40]}» (ver [enlaces])"}
        r = enlace.llamar(destino, "enviar", args, texto.encode())
    return (200 if r.get("ok") else 409), r


def anotar_envio(config, cliente: str, maquina: str, hilo: str, caracteres: int, resultado: str) -> None:
    """Una línea por envío: quién, a qué hilo, cuánto y cómo salió. El texto no se guarda."""
    try:
        ruta = Path(config.estado) / "web.log"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\t{cliente}\t{maquina or 'aquí'}\t{hilo[:80]}\t{caracteres}\t{resultado[:120]}\n")
    except OSError:
        pass


def mantener_espejos(config, pausa: float = 30.0) -> None:
    """Cada `pausa` segundos le pide su foto a cada máquina de `[enlaces]`, para que el espejo esté al día
    aunque su extensión no esté publicando. Un laptop apagado falla rápido y queda con su última foto."""
    while True:
        for e in config.enlaces:
            try:
                enlace.traer_foto(config, e)
            except Exception:  # noqa: BLE001 - un intento fallido no puede matar el hilo; el espejo ya se ve apagado
                pass
        time.sleep(pausa)


def _entero(q: dict, clave: str) -> int | None:
    valor = q.get(clave, [""])[0]
    if valor == "":
        return None
    if not valor.lstrip("-").isdigit():
        raise ValueError(f"«{clave}» tiene que ser un número")
    return int(valor)


def _conversacion(consulta: str, config) -> tuple[int, bytes, str]:
    """`GET /api/conversacion?hilo=…[&sesion=][&antes=][&despues=][&n=]` → (código, cuerpo, tipo).

    La conversación se pide por **hilo**, no por id: de ahí sale la lista de conversaciones permitidas
    (`hilos --json`), así que un id suelto nunca abre un archivo."""
    def responder(codigo: int, cuerpo: dict) -> tuple[int, bytes, str]:
        return codigo, json.dumps(cuerpo, ensure_ascii=False).encode(), "application/json; charset=utf-8"

    q = parse_qs(consulta)
    nombre = q.get("hilo", [""])[0]
    if not nombre or config is None:
        return responder(400, {"error": "falta el hilo"})
    try:
        antes, despues, n = _entero(q, "antes"), _entero(q, "despues"), _entero(q, "n")
    except ValueError as e:
        return responder(400, {"error": str(e)})
    hilos = json.loads(datos("hilos")).get("hilos", [])
    h = next((x for x in hilos if x.get("nombre") == nombre and not x.get("archivado")), None)
    if h is None:
        return responder(404, {"error": f"no hay un hilo «{nombre[:60]}»"})
    try:
        cuerpo = conversacion.pagina(config, h.get("sesiones") or [], sesion=q.get("sesion", [""])[0], antes=antes,
                                     despues=despues, n=n or conversacion.POR_PAGINA)
    except conversacion.ErrorDeConversacion as e:
        return responder(404, {"error": str(e)})
    cuerpo["hilo"] = {"nombre": h["nombre"], "atencion": h.get("atencion", ""), "vivo": bool(h.get("vivo"))}
    return responder(200, cuerpo)


def version_de_la_pagina() -> str:
    """Una huella de los archivos de la página: cambia cuando se edita uno."""
    h = hashlib.sha1()
    for f in sorted(CARPETA.glob("*")):
        if f.is_file():
            h.update(f.name.encode() + str(f.stat().st_mtime_ns).encode())
    return h.hexdigest()[:12]


def manejador(recarga: bool, config=None, ctx=None, escribir: bool = False, tambien: tuple[str, ...] = ()):
    config = config if config is not None else (ctx.config if ctx is not None else None)

    class Manejador(BaseHTTPRequestHandler):
        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            # las fuentes no cambian: se guardan un día; todo lo demás se pide siempre (se edita y se recarga)
            self.send_header("Cache-Control", "public, max-age=86400" if tipo.startswith("font/") else "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):  # noqa: N802 (nombre que pide http.server)
            ruta, _, consulta = self.path.partition("?")
            try:
                if ruta == "/api/version":
                    return self._enviar(200, json.dumps({"pagina": version_de_la_pagina() if recarga else ""}).encode(), "application/json")
                if ruta == "/api/conversacion":  # el historial de un hilo de esta máquina, por páginas (solo lee)
                    return self._enviar(*_conversacion(consulta, config))
                if ruta == "/api/yo":  # qué puede hacer esta página: la escritura es opt-in y necesita el enlace
                    cuerpo = {"escribir": escribir, "enlaces": [e.nombre for e in (config.enlaces if config else ())]}
                    return self._enviar(200, json.dumps(cuerpo).encode(), "application/json")
                if ruta == "/api/espejos":  # los hilos de otras máquinas (el laptop), de sus fotos; no cuesta nada leerlos
                    cuerpo = {"espejos": espejo.leer_todos(config) if config is not None else [], "vigente": espejo.VIGENTE}
                    return self._enviar(200, json.dumps(cuerpo, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                if ruta in ("/api/hoy", "/api/hilos"):
                    return self._enviar(200, datos(ruta[5:], fresco="fresco" in consulta), "application/json; charset=utf-8")
                nombre = "index.html" if ruta == "/" else ruta.lstrip("/")
                archivo = (CARPETA / nombre).resolve()
                if CARPETA not in archivo.parents or not archivo.is_file():
                    return self._enviar(404, b"no hay tal pagina", "text/plain; charset=utf-8")
                tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
                self._enviar(200, archivo.read_bytes(), f"{tipo}; charset=utf-8" if tipo.startswith("text/") or tipo.endswith("javascript") else tipo)
            except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
                self._enviar(502, json.dumps({"error": str(e)}).encode(), "application/json; charset=utf-8")

        def _permitido(self) -> str:
            """"" si la petición viene de esta página; si no, por qué se rechaza."""
            host, puerto = self.server.server_address[:2]
            validos = {f"{host}:{puerto}", f"localhost:{puerto}", f"127.0.0.1:{puerto}", *tambien}
            if self.headers.get("Host", "") not in validos:
                return "Host que no es de este servidor"
            origen = self.headers.get("Origin")
            if origen is not None and origen != f"http://{self.headers.get('Host')}":
                return "Origin que no es de esta página"
            if self.headers.get("X-Telar") != "1":
                return "falta el encabezado X-Telar"
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return "se esperaba application/json"
            return ""

        def do_POST(self):  # noqa: N802
            def responder(codigo, cuerpo):
                self._enviar(codigo, json.dumps(cuerpo, ensure_ascii=False).encode(), "application/json; charset=utf-8")

            if self.path.partition("?")[0] != "/api/enviar":
                return responder(404, {"ok": False, "error": "no hay tal ruta"})
            if not escribir or ctx is None:
                return responder(403, {"ok": False, "error": "esta página solo lee: arráncala con `telar web --escribir`"})
            rechazo = self._permitido()
            if rechazo:
                return responder(403, {"ok": False, "error": rechazo})
            try:
                largo = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                largo = -1
            if not 0 < largo <= MAX_CUERPO:
                return responder(413 if largo > MAX_CUERPO else 400, {"ok": False, "error": "el cuerpo falta o es demasiado grande"})
            try:
                datos = json.loads(self.rfile.read(largo))
            except ValueError:
                return responder(400, {"ok": False, "error": "el cuerpo no es JSON"})
            try:
                codigo, resultado = enviar(ctx, datos)
            except Exception as e:  # noqa: BLE001 - una falla interna se dice, no cuelga la conexión
                codigo, resultado = 500, {"ok": False, "error": f"falló por dentro: {type(e).__name__}"}
            if isinstance(datos, dict):
                anotar_envio(config, self.client_address[0], str(datos.get("maquina", "")), str(datos.get("hilo", "")),
                             len(str(datos.get("texto", ""))), "ok" if resultado.get("ok") else str(resultado.get("error", codigo)))
            responder(codigo, resultado)

        def log_message(self, *a):  # una línea por petición ahogaría la terminal
            pass

    return Manejador


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("web", AYUDA)
    p.epilog = __doc__
    p.add_argument("--host", default="", help="la IP donde escuchar (por defecto, la de Tailscale)")
    p.add_argument("--puerto", type=int, default=PUERTO)
    p.add_argument("--abierto", action="store_true", help="permitir escuchar en todas las interfaces (0.0.0.0)")
    p.add_argument("--escribir", action="store_true", help="permitir escribirle a un hilo desde la página (por defecto, solo lee)")
    p.add_argument("--tambien", action="append", default=[], metavar="HOST:PUERTO",
                   help="otro nombre con el que se llega a esta página (para `--escribir`); se puede repetir")
    p.add_argument("--sin-recarga", action="store_true", help="no recargar la página al cambiar sus archivos")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    host = o.host or ip_de_tailscale() or "127.0.0.1"
    if host in ("0.0.0.0", "::") and not o.abierto:
        return _comun.queja("escuchar en todas las interfaces expone telar a la red entera: pídelo con --abierto")
    if not CARPETA.is_dir():
        return _comun.queja(f"no encuentro los archivos de la página en {CARPETA}")
    threading.Thread(target=mantener_fresco, daemon=True).start()
    if ctx.config.enlaces:
        threading.Thread(target=mantener_espejos, args=(ctx.config,), daemon=True).start()
    servidor = ThreadingHTTPServer((host, o.puerto), manejador(not o.sin_recarga, ctx.config, ctx, o.escribir, tuple(o.tambien)))
    print(f"telar web en http://{host}:{o.puerto}  ·  {'con' if not o.sin_recarga else 'sin'} recarga automática  ·  "
          f"{'PUEDE ESCRIBIR en hilos' if o.escribir else 'solo lee'}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0
