"""`telar web` — telar en el navegador del celular: el día y los hilos, tocables.

    telar web                    escucha en la IP de Tailscale (o en localhost si no hay), puerto 8765
    telar web --host IP --puerto N
    telar web --sin-recarga      no recarga la página cuando cambian sus archivos

Una capa fina sobre lo que telar ya sabe: cada pantalla lee un `--json` documentado
(docs/contratos.md), así que la lógica no se duplica. Los hilos de otras máquinas (el laptop) salen
de las fotos que ellas empujan con `telar espejo publicar` (ver `telar.espejo`). Solo lee: no hay ninguna ruta que
escriba ni que corra órdenes con lo que llega de la red. Escucha en una sola interfaz; una
dirección abierta a todas (`0.0.0.0`) hay que pedirla con `--abierto`.

Los archivos de la página viven en `telar/web/`. Con la recarga puesta (lo normal), editar uno
de ellos recarga la página abierta en el celular en un par de segundos: ese es el punto.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from telar import espejo
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


def version_de_la_pagina() -> str:
    """Una huella de los archivos de la página: cambia cuando se edita uno."""
    h = hashlib.sha1()
    for f in sorted(CARPETA.glob("*")):
        if f.is_file():
            h.update(f.name.encode() + str(f.stat().st_mtime_ns).encode())
    return h.hexdigest()[:12]


def manejador(recarga: bool, config=None):
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

        def log_message(self, *a):  # una línea por petición ahogaría la terminal
            pass

    return Manejador


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("web", AYUDA)
    p.epilog = __doc__
    p.add_argument("--host", default="", help="la IP donde escuchar (por defecto, la de Tailscale)")
    p.add_argument("--puerto", type=int, default=PUERTO)
    p.add_argument("--abierto", action="store_true", help="permitir escuchar en todas las interfaces (0.0.0.0)")
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
    servidor = ThreadingHTTPServer((host, o.puerto), manejador(not o.sin_recarga, ctx.config))
    print(f"telar web en http://{host}:{o.puerto}  ·  {'con' if not o.sin_recarga else 'sin'} recarga automática")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0
