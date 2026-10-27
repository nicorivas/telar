"""Servidores agregados a mano: los que una persona suma en «máquinas» (o `telar servidor agregar`) dando su
dirección, antes de estar en su bus.

    agregar(config, direccion)   preguntarle quién es (`GET /unirse/servidor`) y anotarlo
    lista(config)                los anotados, con en qué va cada uno: sin pedir, pendiente, aprobado, en su bus…
    quitar(direccion)            olvidarlo (no cambia nada en el servidor)
    equipo_de(servidor)          el equipo (telar.unirse.Equipo) con que `telar instalar --servidor` pide entrar

La dirección puede ser una IP o un nombre de Tailscale (`100.66.75.117`, `telar`: su página directa, puerto 8780) o
una dirección entera (`https://telar.<red>.ts.net`: su puerta, telar.puerta). Pedir entrar es lo mismo que `telar
instalar --unirse` con el `equipo.yaml` de un repositorio, pero el equipo sale de lo que el servidor dice de sí: su
nombre, su bus y quién lo administra. Después, como siempre, quien administra lo aprueba (⚙ personas) y el nodo se
conecta solo; ya en su bus, el lugar en el servidor se pide en «máquinas».

Se guardan en `~/.config/telar/servidores.json` (solo de esta máquina): {url: {nombre, bus, administra, aloja,
version, agregado, pedido, persona, estado, visto}}.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

#: el puerto de la página directa de un servidor, si la dirección no dice otro
PUERTO = 8780
#: cada cuánto se le pregunta al servidor en qué va un pedido pendiente (segundos)
CADA = 30
NOMBRE_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


class ErrorDeServidores(Exception):
    def __init__(self, mensaje: str, codigo: int = 422) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def _archivo() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "telar" / "servidores.json"


def leer() -> dict[str, dict]:
    try:
        d = json.loads(_archivo().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar(datos: dict[str, dict]) -> None:
    ruta = _archivo()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


def normalizar(direccion: str) -> str:
    """La dirección base de un servidor: `http://host:8780` para una IP o un nombre suelto, o la dirección entera
    (sin ruta) si trae su esquema. ErrorDeServidores si no parece una dirección."""
    d = (direccion or "").strip()
    if not d:
        raise ErrorDeServidores("¿qué dirección? una IP de Tailscale, el nombre de la máquina o su https://…")
    if "://" not in d:
        d = f"http://{d.rstrip('/')}"
    try:
        p = urlsplit(d)
        puerto = p.port
    except ValueError:
        raise ErrorDeServidores(f"«{direccion}» no es una dirección") from None
    host = p.hostname or ""
    if p.scheme not in ("http", "https") or not NOMBRE_HOST.match(host) and not _es_ip(host):
        raise ErrorDeServidores(f"«{direccion}» no es una dirección")
    if p.scheme == "http" and puerto is None:
        puerto = PUERTO
    return f"{p.scheme}://{host}{f':{puerto}' if puerto else ''}"


def _es_ip(host: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _pedir_json(url: str, timeout: float = 8) -> tuple[int, dict]:
    pedido = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:  # noqa: S310 - la dirección la dio la persona
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def sondear(url: str, *, pedir=_pedir_json) -> dict:
    """Lo que el servidor dice de sí (`/unirse/servidor`). ErrorDeServidores, en palabras, si no contesta o no es la
    máquina del bus de un telar."""
    try:
        codigo, d = pedir(f"{url}/unirse/servidor")
    except (urllib.error.URLError, OSError, ValueError) as e:
        motivo = getattr(e, "reason", e)
        raise ErrorDeServidores(f"{url} no contesta ({motivo}): ¿está en tu red de Tailscale, y te deja llegar a su "
                                f"puerto?", 502) from None
    if codigo == 404:
        raise ErrorDeServidores(f"{url} contesta, pero no es la máquina del bus de un telar (o es un telar anterior "
                                f"a la 0.7.3)", 404)
    if codigo != 200 or not d.get("telar") or not str(d.get("bus") or "").startswith("nats://"):
        raise ErrorDeServidores(f"{url} no contestó como un servidor de telar ({codigo})", 502)
    return d


def agregar(config, direccion: str, *, pedir=_pedir_json, ahora: float | None = None) -> dict:
    """Preguntarle al servidor quién es y anotarlo. Devuelve lo anotado."""
    url = normalizar(direccion)
    d = sondear(url, pedir=pedir)
    datos = leer()
    previo = datos.get(url, {})
    datos[url] = {**previo, "nombre": str(d.get("servidor") or urlsplit(url).hostname), "bus": str(d["bus"]),
                  "administra": str(d.get("administra") or ""), "aloja": bool(d.get("aloja")),
                  "puerta": str(d.get("puerta") or ""), "version": str(d.get("telar") or ""),
                  "agregado": previo.get("agregado") or int(ahora if ahora is not None else time.time())}
    _guardar(datos)
    return {"url": url, **datos[url]}


def quitar(direccion: str) -> bool:
    url = normalizar(direccion)
    datos = leer()
    if url not in datos:
        return False
    del datos[url]
    _guardar(datos)
    return True


def anotar_pedido(url: str, *, pedido: str, persona: str, estado: str) -> None:
    """Lo que contestó el servidor al pedir entrar (`telar instalar --servidor`)."""
    datos = leer()
    if url in datos:
        datos[url].update(pedido=pedido, persona=persona, estado=estado, visto=int(time.time()))
        _guardar(datos)


def equipo_de(url: str):
    """El equipo con que se pide entrar a un servidor anotado: su nombre, su bus, quién lo administra y su puerta."""
    from telar import unirse

    s = leer().get(url)
    if not s:
        raise ErrorDeServidores(f"{url} no está agregado: telar servidor agregar {url}", 404)
    return unirse.Equipo(nombre=s.get("nombre") or "servidor", bus=s["bus"], administra=s.get("administra", ""),
                         puerta=url)


def lista(config, *, pedir=_pedir_json, ahora: float | None = None) -> list[dict]:
    """Los anotados, cada uno con `estado`, en palabras de máquina:

        en-su-bus     esta máquina ya está en su bus (el lugar se pide en «máquinas», como siempre)
        otro-bus      esta máquina está en otro bus: un telar se conecta a uno solo
        pendiente     pidió entrar y espera que quien administra lo apruebe
        rechazado     no lo aprobaron (se puede pedir de nuevo)
        sin-pedir     agregado, sin pedir entrar todavía
        pidiendo      se está pidiendo (telar instalar --servidor, aparte)
        falló         el pedido no llegó a hacerse (lo que pasó, en `<estado>/servidor-entrar.log`)

    Un pedido pendiente se le pregunta al servidor a lo más cada CADA segundos."""
    ahora = ahora if ahora is not None else time.time()
    mi_bus = str(getattr(getattr(config, "bus", None), "url", "") or "") if config is not None else ""
    datos, cambio = leer(), False
    salida = []
    for url, s in sorted(datos.items(), key=lambda x: x[1].get("agregado", 0)):
        estado = s.get("estado") or "sin-pedir"
        if s.get("pedido") and estado == "pendiente" and ahora - float(s.get("visto") or 0) >= CADA:
            try:
                codigo, d = pedir(f"{url}/unirse/{s['pedido']}", timeout=5)
                if codigo == 200 and d.get("estado"):
                    estado = {"aprobado": "aprobado", "rechazado": "rechazado"}.get(d["estado"], "pendiente")
                    s.update(estado=estado, visto=int(ahora))
                    cambio = True
            except (urllib.error.URLError, OSError, ValueError):
                pass
        if estado == "pidiendo" and ahora - float(s.get("desde") or ahora) > 180:
            estado = "falló"  # telar instalar no llegó a anotar el pedido: lo que dijo, en servidor-entrar.log
        if mi_bus and mi_bus == s.get("bus"):
            # pidió y espera, o lo rechazaron: eso se dice; si no, ya está en su bus (aprobado, o entró de otra forma)
            estado = estado if estado in ("pendiente", "rechazado", "pidiendo") else "en-su-bus"
        elif mi_bus and estado != "pidiendo":
            estado = "otro-bus"
        salida.append({"url": url, **s, "estado": estado})
    if cambio:
        _guardar(datos)
    return salida


def entrar(config, url: str, persona: str) -> dict:
    """Pedir entrar al bus de un servidor anotado, desde la página: corre `telar instalar --servidor URL --persona P
    --si` en un proceso aparte (reescribe el servicio y lo reinicia: el de la página no puede hacerlo desde adentro).
    Lo que diga queda en `<estado>/servidor-entrar.log`; el pedido, en el servidor anotado."""
    import shutil
    import subprocess
    import sys

    from telar import cuentas
    from telar.actualizar import _path

    if url not in leer():
        raise ErrorDeServidores(f"{url} no está agregado", 404)
    try:
        cuentas.validar(persona)
    except cuentas.ErrorDeCuentas as e:
        raise ErrorDeServidores(f"{e}: tu nombre en el bus va en minúsculas, sin espacios") from None
    mi_bus = str(getattr(getattr(config, "bus", None), "url", "") or "")
    if mi_bus and mi_bus != leer()[url].get("bus"):
        raise ErrorDeServidores(f"esta máquina ya está en otro bus ({mi_bus}): un telar se conecta a uno solo", 409)
    telar = shutil.which("telar") or str(Path(sys.executable).parent / "telar")
    log = Path(config.estado) / "servidor-entrar.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    datos = leer()
    datos[url].update(estado="pidiendo", persona=persona, desde=int(time.time()), pedido="")
    _guardar(datos)
    orden = [telar, "instalar", "--servidor", url, "--persona", persona, "--si"]
    if sys.platform != "darwin" and shutil.which("systemd-run"):
        # fuera del grupo de telar-serve: reiniciarlo mataría a quien lo reinicia
        subprocess.run(["systemd-run", "--user", "--collect", "--quiet", f"--unit=telar-entrar-{int(time.time())}",
                        "-p", f"StandardOutput=append:{log}", "-p", f"StandardError=append:{log}", *orden],
                       check=True, timeout=20, env={**os.environ})
    else:
        with log.open("a", encoding="utf-8") as salida:
            subprocess.Popen(orden, stdin=subprocess.DEVNULL, stdout=salida, stderr=salida, start_new_session=True,
                             env={**os.environ, "PATH": _path()})
    return {"url": url, **leer()[url]}
