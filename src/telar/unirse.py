"""Unirse a un equipo: una persona nueva corre un comando y quien administra el bus aprueba.

Un equipo se declara en el repositorio que comparte, en `.telar/equipo.yaml`:

    nombre: brinca
    administra: ana               # quién aprueba a las personas nuevas (su nombre en el bus)
    bus: nats://servidor:4222      # el bus del equipo
    puerta: http://servidor:8780   # opcional: dónde se pide entrar; por defecto, la página de la máquina del bus
    modulos:                       # opcional: los módulos que usa el equipo
      grafo: https://github.com/alguien/telar-grafo
    requiere: [tmux, claude, tailscale]
    agente:                        # opcional: el [agente] de quien se une, si no tiene uno
      nombre: claude-code
      carpeta: raiz                # Claude se abre en la raíz del repositorio (su CLAUDE.md, sus skills)

`telar instalar --unirse`, desde el clon del repositorio, lee eso y:

1. revisa que estén los programas que el equipo pide;
2. genera el secreto de la persona **en su máquina** (`~/.config/telar/bus.token`) y manda a la puerta solo su
   hash (bcrypt): el secreto no viaja;
3. deja en su configuración el bus, el repositorio (`[repos.<equipo>]`), los módulos del equipo y, si no tenía,
   su `[agente]`.

La **puerta** es `POST /unirse` en la página de la máquina del bus. Es lo único que telar recibe sin la llave de
la página, y por eso pide tres cosas: que venga de la red de Tailscale (la página solo escucha ahí, y además se
mira la dirección), que Tailscale diga quién es (`tailscale whois`: no se puede hacer pasar por otro), y no más
de unos pocos pedidos por hora desde una misma dirección. Un pedido no da acceso: queda pendiente hasta que
quien administra lo aprueba (`telar bus pedidos`, `telar bus aprobar <id>`), y recién ahí su hash entra a las
cuentas del bus (telar.cuentas) y el bus se recarga. Mientras tanto, el nodo de la persona intenta conectarse
y espera.
"""

from __future__ import annotations

import ipaddress
import json
import re
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

#: el manifiesto del equipo, en la carpeta de telar del repositorio
NOMBRE_EQUIPO = ".telar/equipo.yaml"
#: cuántos pedidos acepta la puerta desde una misma dirección por hora
TOPE_POR_HORA = 5
#: la red de Tailscale (100.64.0.0/10) y la de IPv6 de Tailscale: de fuera de ahí, la puerta no atiende
REDES_TAILSCALE = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))


class ErrorDeUnirse(Exception):
    """Lo que no se pudo; el mensaje es para la persona."""


class YaTieneCuenta(ErrorDeUnirse):
    """Esa persona ya está en el bus: la puerta contesta 409, y quien ya tenía la clave es otra máquina suya."""


@dataclass(frozen=True)
class Equipo:
    nombre: str
    bus: str
    administra: str = ""
    puerta: str = ""
    modulos: dict = field(default_factory=dict)
    requiere: tuple = ()
    #: el [agente] que se le propone a quien se une: {nombre, carpeta}
    agente: dict = field(default_factory=dict)
    #: la carpeta del repositorio que lo declara
    repo: Path | None = None

    @property
    def url_puerta(self) -> str:
        """Dónde se pide entrar: la que dice el manifiesto, o la página (puerto 8780) de la máquina del bus."""
        if self.puerta:
            return self.puerta.rstrip("/")
        return f"http://{urlparse(self.bus).hostname}:8780"


def leer(ruta: Path) -> Equipo:
    """El manifiesto de un equipo. ErrorDeUnirse si no se puede leer o le falta algo."""
    from telar import cuentas

    try:
        import yaml

        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError) as e:
        raise ErrorDeUnirse(f"{ruta}: {e}") from None
    except Exception as e:  # noqa: BLE001 - un YAML mal escrito
        raise ErrorDeUnirse(f"{ruta}: YAML mal formado: {e}") from None
    if not isinstance(datos, dict):
        raise ErrorDeUnirse(f"{ruta}: se esperaba un mapa (clave: valor)")
    sobra = set(datos) - {"nombre", "administra", "bus", "puerta", "modulos", "requiere", "agente"}
    if sobra:
        raise ErrorDeUnirse(f"{ruta}: no conozco «{sorted(sobra)[0]}»")
    nombre, bus = str(datos.get("nombre") or ""), str(datos.get("bus") or "")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", nombre):
        raise ErrorDeUnirse(f"{ruta}: `nombre` es el nombre del equipo, en minúsculas (como «brinca»)")
    if not re.fullmatch(r"nats://[^\s/:]+:\d+", bus):
        raise ErrorDeUnirse(f"{ruta}: `bus` va como nats://servidor:4222")
    administra = str(datos.get("administra") or "")
    if administra:
        try:
            cuentas.validar(administra)
        except cuentas.ErrorDeCuentas as e:
            raise ErrorDeUnirse(f"{ruta}: administra: {e}") from None
    puerta = str(datos.get("puerta") or "")
    if puerta and not re.fullmatch(r"https?://[^\s/]+(:\d+)?/?", puerta):
        raise ErrorDeUnirse(f"{ruta}: `puerta` va como http://servidor:8780")
    modulos = datos.get("modulos") or {}
    if not isinstance(modulos, dict) or not all(isinstance(v, str) and v for v in modulos.values()):
        raise ErrorDeUnirse(f"{ruta}: `modulos` es un mapa nombre: repositorio")
    requiere = datos.get("requiere") or []
    if not isinstance(requiere, list) or not all(isinstance(x, str) and x for x in requiere):
        raise ErrorDeUnirse(f"{ruta}: `requiere` es una lista de programas")
    agente = datos.get("agente") or {}
    if not isinstance(agente, dict) or set(agente) - {"nombre", "carpeta"} \
            or not all(isinstance(v, str) and v for v in agente.values()):
        raise ErrorDeUnirse(f"{ruta}: `agente` lleva nombre (como claude-code) y carpeta (hilo, raiz o una ruta)")
    return Equipo(nombre=nombre, bus=bus, administra=administra, puerta=puerta, modulos=dict(modulos),
                  requiere=tuple(requiere), agente=dict(agente), repo=ruta.parent.parent)


def buscar(desde: Path | None = None) -> Equipo | None:
    """El equipo del repositorio donde se está (la raíz git de `desde`, o de la carpeta actual); None si no
    declara uno."""
    desde = Path(desde or Path.cwd())
    r = subprocess.run(["git", "-C", str(desde), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    raiz = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else desde
    manifiesto = raiz / NOMBRE_EQUIPO
    return leer(manifiesto) if manifiesto.is_file() else None


def faltan(equipo: Equipo) -> list[str]:
    import shutil

    return [p for p in equipo.requiere if not shutil.which(p)]


# ── quien pide entrar ─────────────────────────────────────────────────────────────────

def pedir(equipo: Equipo, persona: str, maquina: str, ruta_secreto: Path) -> dict:
    """Genera el secreto (si no lo hay) y deja el pedido en la puerta del equipo. Devuelve lo que contestó:
    {id, estado}. ErrorDeUnirse si la puerta no contesta o no lo acepta."""
    import urllib.error
    import urllib.request

    from telar import cuentas

    cuentas.validar(persona)
    ya_estaba = ruta_secreto.exists()
    if ya_estaba:
        secreto = ruta_secreto.read_text(encoding="utf-8").strip()
    else:
        secreto = cuentas.secreto_nuevo()
        cuentas.guardar_secreto(ruta_secreto, secreto)
    cuerpo = json.dumps({"persona": persona, "maquina": maquina, "hash": cuentas.hashear(secreto),
                         "equipo": equipo.nombre}).encode()
    pedido = urllib.request.Request(f"{equipo.url_puerta}/unirse", data=cuerpo, method="POST",
                                    headers={"Content-Type": "application/json"})
    try:
        return _tocar(pedido, equipo, ya_estaba)
    except ErrorDeUnirse:
        if not ya_estaba:
            # la clave recién hecha no sirvió para nada: que no quede, o la próxima vez parecería de antes
            ruta_secreto.unlink(missing_ok=True)
        raise


def _tocar(pedido, equipo: Equipo, ya_estaba: bool) -> dict:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(pedido, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            detalle = json.loads(e.read() or b"{}").get("detail", "")
        except ValueError:
            detalle = ""
        if e.code == 409 and ya_estaba:
            # otra máquina de una persona que ya está en el bus, con su clave copiada: entra con esa cuenta (si la
            # clave no es la suya, el bus no la deja conectarse; la puerta no da nada)
            return {"id": "", "estado": "ya tiene cuenta"}
        raise ErrorDeUnirse(f"la puerta del equipo no lo aceptó ({e.code}): {detalle or e.reason}") from None
    except (urllib.error.URLError, OSError) as e:
        raise ErrorDeUnirse(f"no llego a la puerta del equipo ({equipo.url_puerta}): {e}. ¿Estás en su red de "
                            f"Tailscale? Pídele a quien administra que te invite.") from None


# ── la máquina del bus: los pedidos ──────────────────────────────────────────────────

def _archivo_pedidos() -> Path:
    from telar import cuentas

    return cuentas.carpeta() / "pedidos.json"


def administra_aqui() -> bool:
    """Si esta máquina tiene las cuentas del bus (su `servidor.conf`): solo ahí atiende la puerta."""
    from telar import cuentas

    return (cuentas.carpeta() / "servidor.conf").is_file()


def leer_pedidos() -> dict:
    try:
        return json.loads(_archivo_pedidos().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise ErrorDeUnirse(f"{_archivo_pedidos()}: no se puede leer: {e}") from None


def _guardar_pedidos(pedidos: dict) -> None:
    from telar import cuentas

    cuentas._escribir_privado(_archivo_pedidos(), json.dumps(pedidos, ensure_ascii=False, indent=1))


def de_tailscale(ip: str) -> bool:
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(direccion in red for red in REDES_TAILSCALE)


def quien_es(ip: str) -> dict:
    """Quién es esa dirección según Tailscale: {cuenta, maquina}. ErrorDeUnirse si no lo sabe."""
    try:
        r = subprocess.run(["tailscale", "whois", "--json", ip], capture_output=True, text=True, timeout=10)
        datos = json.loads(r.stdout)
        return {"cuenta": datos["UserProfile"]["LoginName"],
                "maquina": datos["Node"].get("ComputedName") or datos["Node"].get("Name", "")}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise ErrorDeUnirse(f"Tailscale no sabe quién es {ip}") from None


def recibir(datos: dict, ip: str, quien: dict, *, ahora: float | None = None) -> dict:
    """Anota un pedido de entrada que llegó a la puerta. Devuelve {id, estado}. Uno igual que ya estaba
    pendiente (misma persona, misma cuenta de Tailscale) se reemplaza: es la misma persona que lo intenta de
    nuevo, con su secreto de ahora."""
    from telar import cuentas

    persona = cuentas.validar(str(datos.get("persona") or ""))
    h = str(datos.get("hash") or "")
    if not cuentas.BCRYPT.match(h):
        raise ErrorDeUnirse("el pedido no trae un hash de su secreto")
    pedidos = leer_pedidos()
    if persona in cuentas.leer(cuentas.carpeta()):
        raise YaTieneCuenta(f"«{persona}» ya tiene cuenta en el bus: si es otra persona, elige otro nombre; si es "
                            f"otra máquina tuya, copia aquí tu clave (~/.config/telar/bus.token) y vuelve a correrlo")
    for pid, p in list(pedidos.items()):
        if p["estado"] == "pendiente" and p["persona"] == persona:
            if p["tailscale"] != quien["cuenta"]:
                raise ErrorDeUnirse(f"ya hay un pedido pendiente de «{persona}» desde otra cuenta: elige otro nombre")
            del pedidos[pid]
    pid = secrets.token_hex(4)
    pedidos[pid] = {"persona": persona, "maquina": str(datos.get("maquina") or "")[:64], "hash": h,
                    "equipo": str(datos.get("equipo") or "")[:64], "tailscale": quien["cuenta"],
                    "nodo": quien["maquina"], "ip": ip, "cuando": int(ahora if ahora is not None else time.time()),
                    "estado": "pendiente"}
    _guardar_pedidos(pedidos)
    return {"id": pid, "estado": "pendiente"}


def estado(pid: str, ip: str) -> dict:
    """En qué va un pedido, solo para la dirección que lo hizo."""
    p = leer_pedidos().get(pid)
    if p is None or p.get("ip") != ip:
        raise ErrorDeUnirse("no hay un pedido así desde esta máquina")
    return {"id": pid, "estado": p["estado"], "persona": p["persona"]}


def decidir(pid: str, aprobar: bool) -> dict:
    """Aprueba (su hash entra a las cuentas del bus) o rechaza un pedido pendiente. Devuelve el pedido."""
    from telar import cuentas

    pedidos = leer_pedidos()
    p = pedidos.get(pid)
    if p is None:
        raise ErrorDeUnirse(f"no hay un pedido «{pid}»: telar bus pedidos")
    if p["estado"] != "pendiente":
        raise ErrorDeUnirse(f"el pedido «{pid}» ya está {p['estado']}")
    if aprobar:
        personas = cuentas.leer(cuentas.carpeta())
        if p["persona"] in personas:
            raise ErrorDeUnirse(f"«{p['persona']}» ya tiene cuenta en el bus")
        personas[p["persona"]] = p["hash"]
        cuentas.escribir(cuentas.carpeta(), personas)
    p["estado"] = "aprobado" if aprobar else "rechazado"
    p["decidido"] = int(time.time())
    _guardar_pedidos(pedidos)
    return {"id": pid, **p}


def recargar_bus() -> str:
    """Que el servidor del bus lea las cuentas de nuevo. "" si se pudo; si no, qué correr a mano."""
    orden = ["systemctl", "--user", "reload", "telar-bus"]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return " ".join(orden)
    return "" if r.returncode == 0 else " ".join(orden)


class Tope:
    """Cuántos pedidos llegaron de cada dirección en la última hora (en memoria: lo lleva telar serve)."""

    def __init__(self, tope: int = TOPE_POR_HORA) -> None:
        self.tope, self.vistos = tope, {}

    def pasa(self, ip: str, ahora: float | None = None) -> bool:
        ahora = time.time() if ahora is None else ahora
        recientes = [t for t in self.vistos.get(ip, []) if ahora - t < 3600]
        if len(recientes) >= self.tope:
            self.vistos[ip] = recientes
            return False
        self.vistos[ip] = [*recientes, ahora]
        return True


def nombre_de_maquina() -> str:
    import socket

    return re.sub(r"[^a-z0-9-]", "-", socket.gethostname().split(".")[0].lower()) or "maquina"


def persona_por_defecto() -> str:
    import getpass

    return re.sub(r"[^a-z0-9_-]", "", getpass.getuser().lower()) or "persona"


__all__ = ["Equipo", "ErrorDeUnirse", "leer", "buscar", "pedir", "recibir", "decidir", "estado", "leer_pedidos",
           "administra_aqui", "de_tailscale", "quien_es", "recargar_bus", "Tope", "NOMBRE_EQUIPO"]
