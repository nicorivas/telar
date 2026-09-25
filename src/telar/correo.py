"""El correo entre agentes de una máquina remota: direcciones, pendientes y conversaciones.

En un servidor compartido, cada persona es un usuario y sus agentes se escriben por correo
local (ver docs/propuestas/correo-y-celular.md). telar no entrega nada: eso lo hace el
servidor. telar **lee**, por ssh, la Maildir del usuario, el registro de su cartero y, si
el servidor lo publica, el archivo común de todos los correos entre agentes; y con eso
dice qué dirección tiene cada hilo, cuántos correos le esperan y qué conversaciones hubo.

Un correo es **pendiente** si está en la Maildir y el cartero no lo entregó a ninguna
sesión: llegó con el hilo cerrado (SIN SESIÓN) o quedó RETENIDO. Para saber cuál es cuál,
el cartero anota en cada línea el `Message-Id`; sin eso, telar no puede distinguirlos y no
cuenta pendientes (lo dice, no adivina).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import unicodedata
from dataclasses import dataclass, field

from telar.config import Remoto

ESPERA = 20

#: El guion que corre allá. Imprime un JSON con los encabezados de cada correo (no los
#: cuerpos, salvo que se pidan) y las líneas del registro del cartero. Solo lee.
GUION = r'''
import email, email.policy, glob, json, os, re, sys, pwd
casillas = sys.argv[1:] or ["~/Maildir"]
con_cuerpo = os.environ.get("TELAR_CUERPO") == "1"
salida = {"correos": [], "log": [], "usuario": pwd.getpwuid(os.getuid()).pw_name}
vistos = set()
for n, casilla in enumerate(casillas):
    base = os.path.expanduser(casilla)
    propia = n == 0  # la primera es la Maildir del usuario; las otras, copias (la casilla común)
    for sub in ("new", "cur"):
        for ruta in glob.glob(os.path.join(base, sub, "*")):
            try:
                with open(ruta, "rb") as f:
                    m = email.message_from_binary_file(f, policy=email.policy.default)
            except Exception:
                continue
            mid = str(m.get("Message-Id", "")).strip()
            if mid and mid in vistos:
                continue
            vistos.add(mid)
            rec = " ".join(str(h) for h in m.get_all("Received", []))
            uid = re.search(r"from userid (\d+)", rec)
            try:
                de = pwd.getpwuid(int(uid.group(1))).pw_name if uid else ""
            except KeyError:
                de = ""
            # en la propia, X-Original-To dice a qué dirección llegó (con su +extensión); en una
            # copia de archivo esa cabecera es la del archivo, y el destinatario real está en To/Cc
            destino = str(m.get("X-Original-To", "") or m.get("To", "")) if propia else \
                ", ".join(str(x) for x in (m.get("To"), m.get("Cc")) if x)
            c = {"archivo": ruta, "nuevo": sub == "new", "id": mid, "de": de, "propia": propia,
                 "from": str(m.get("From", "")), "para": destino,
                 "asunto": str(m.get("Subject", "")), "fecha": str(m.get("Date", "")),
                 # los ids van entre <>; GNU mail antepone texto («Your message of…») al de In-Reply-To
                 "responde": " ".join(re.findall(r"<[^<>\s]+>", str(m.get("In-Reply-To", "")))),
                 "referencias": re.findall(r"<[^<>\s]+>", str(m.get("References", "")))}
            if con_cuerpo:
                p = m.get_body(preferencelist=("plain",))
                c["cuerpo"] = (p.get_content() if p else "")[:20000]
            salida["correos"].append(c)
try:
    with open(os.path.expanduser("~/.cartero.log"), encoding="utf-8", errors="replace") as f:
        salida["log"] = f.read().splitlines()[-2000:]
except FileNotFoundError:
    pass
print(json.dumps(salida))
'''


@dataclass(frozen=True, slots=True)
class Correo:
    archivo: str
    id: str
    de: str          # el usuario que lo mandó, según el uid que anotó Postfix (verificado)
    para: str        # la dirección a la que llegó (usuario+extension@servidor)
    asunto: str
    fecha: str
    responde: str = ""
    referencias: tuple[str, ...] = ()
    nuevo: bool = False
    estado: str = ""  # entregado · retenido · sin sesión · "" (no se sabe)
    #: llegó a la casilla del propio usuario (no es una copia de la casilla común)
    propia: bool = True
    cuerpo: str = ""


@dataclass(frozen=True, slots=True)
class Buzon:
    usuario: str
    correos: tuple[Correo, ...] = ()
    #: False si el registro del cartero no anota el Message-Id: los pendientes no se saben
    sabe_pendientes: bool = False
    error: str = ""
    lineas: tuple[str, ...] = field(default=())


# ── la dirección de un hilo ──────────────────────────────────────────────────────────

def extension(nombre: str) -> str:
    """El nombre de un hilo como extensión de dirección: «T42 Faro Norte» → `t42-faro-norte`.

    Minúsculas, sin acentos, y todo lo que no sea letra o número se vuelve un guion. Un
    nombre que no deja nada (solo símbolos) no tiene dirección propia: "".
    """
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plano).strip("-")


def direccion(remoto: Remoto, nombre: str) -> str:
    """`usuario+extension@servidor` para un hilo de esa máquina; "" si no se puede armar."""
    usuario, _, servidor = remoto.destino.rpartition("@")
    if not usuario:
        return ""  # un alias de ~/.ssh/config no dice el usuario ni el nombre del servidor
    ext = extension(nombre)
    return f"{usuario}+{ext}@{servidor}" if ext else f"{usuario}@{servidor}"


def extension_de(direccion_: str) -> str:
    """La extensión de una dirección: `usuario+pizza@servidor` → `pizza`; sin extensión, ""."""
    local = direccion_.strip().strip("<>").split("@", 1)[0]
    return local.split("+", 1)[1] if "+" in local else ""


# ── leer ─────────────────────────────────────────────────────────────────────────────

_ID = re.compile(r"\bid=(<[^>\s]+>)")


def desde_cuando(lineas: list[str]) -> str:
    """La hora de la primera línea del registro que anota ids (`2026-09-24T13:17:02`), o "".

    Lo anterior a eso se registró sin id: de esos correos no se sabe si se entregaron.
    """
    for linea in lineas:
        if _ID.search(linea):
            return linea[:19]
    return ""


def estados(lineas: list[str]) -> tuple[dict[str, str], bool]:
    """Message-Id → estado, según el registro del cartero; y si el registro anota ids."""
    salida: dict[str, str] = {}
    sabe = False
    for linea in lineas:
        m = _ID.search(linea)
        if not m:
            continue
        sabe = True
        cuerpo = linea[20:] if len(linea) > 20 else linea
        estado = ("entregado" if cuerpo.startswith("ENTREGADO") else "retenido" if cuerpo.startswith("RETENIDO")
                  else "sin sesión" if cuerpo.startswith("SIN SESI") else "")
        if estado:
            salida[m.group(1)] = estado
    return salida, sabe


def desde_json(datos: dict) -> Buzon:
    lineas = [str(x) for x in datos.get("log", [])]
    por_id, sabe = estados(lineas)
    desde = desde_cuando(lineas)
    correos = []
    for c in datos.get("correos", []):
        mid = str(c.get("id", ""))
        propia = bool(c.get("propia", True))
        estado = por_id.get(mid, "")
        # solo se juzga lo que llegó a la casilla propia: de un correo a otro usuario, su
        # registro no se puede leer, y no aparecer en el propio no dice nada
        if propia and sabe and not estado and _posterior(str(c.get("fecha", "")), desde):
            estado = "sin sesión"  # llegó después de que el cartero anota ids, y no lo entregó
        correos.append(Correo(
            archivo=str(c.get("archivo", "")), id=mid, de=str(c.get("de", "")), para=str(c.get("para", "")),
            asunto=str(c.get("asunto", "")), fecha=str(c.get("fecha", "")), responde=str(c.get("responde", "")),
            referencias=tuple(c.get("referencias") or ()), nuevo=bool(c.get("nuevo")), estado=estado, propia=propia,
            cuerpo=str(c.get("cuerpo", ""))))
    return Buzon(usuario=str(datos.get("usuario", "")), correos=tuple(correos), sabe_pendientes=sabe,
                 lineas=tuple(lineas))


def _posterior(fecha: str, desde: str) -> bool:
    """¿El correo llegó cuando el registro ya anotaba ids? Se compara en la hora de pared del
    servidor, que es la que usan los dos. Una fecha que no se entiende no cuenta como pendiente."""
    from datetime import datetime
    from email.utils import parsedate_to_datetime

    if not desde:
        return False
    try:
        cuando = parsedate_to_datetime(fecha).replace(tzinfo=None)
        return cuando >= datetime.fromisoformat(desde)
    except (TypeError, ValueError):
        return False


def leer(remoto: Remoto, *, con_cuerpo: bool = False, archivo: str = "") -> Buzon:
    """El buzón del usuario en esa máquina, por ssh. Nunca lanza: un error queda en `error`."""
    casillas = ["~/Maildir"] + ([archivo] if archivo else [])
    remoto_cmd = ("TELAR_CUERPO=1 " if con_cuerpo else "") + shlex.join(["python3", "-c", GUION, *casillas])
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino, remoto_cmd]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return Buzon(usuario="", error=f"{remoto.destino} no responde: {e}")
    if r.returncode != 0:
        return Buzon(usuario="", error=(r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:])
    try:
        return desde_json(json.loads(r.stdout))
    except ValueError:
        return Buzon(usuario="", error="el servidor no devolvió JSON")


def leer_local(*, con_cuerpo: bool = False, archivo: str = "") -> Buzon:
    """Lo mismo que `leer`, en esta máquina: para `telar movil`, que corre en el servidor."""
    import os
    import sys

    casillas = ["~/Maildir"] + ([archivo] if archivo else [])
    entorno = {**os.environ, **({"TELAR_CUERPO": "1"} if con_cuerpo else {})}
    try:
        r = subprocess.run([sys.executable, "-c", GUION, *casillas], capture_output=True, text=True,
                           timeout=ESPERA, env=entorno)
    except (OSError, subprocess.TimeoutExpired) as e:
        return Buzon(usuario="", error=str(e))
    try:
        return desde_json(json.loads(r.stdout))
    except ValueError:
        return Buzon(usuario="", error=(r.stderr.strip() or "no se pudo leer la Maildir")[-300:])


# ── contar y agrupar ─────────────────────────────────────────────────────────────────

def pendientes(buzon: Buzon) -> list[Correo]:
    """Los que llegaron y no alcanzaron a ningún agente. Vacío si el cartero no anota ids."""
    if not buzon.sabe_pendientes:
        return []
    return [c for c in buzon.correos if c.estado in ("sin sesión", "retenido")]


def _usuario_de(direccion_: str) -> str:
    return direccion_.strip().strip("<>").split("@", 1)[0].split("+", 1)[0]


def por_hilo(correos: list[Correo], nombres: list[str], usuario: str = "") -> dict[str, list[Correo]]:
    """Reparte correos entre hilos por la extensión de la dirección a la que llegaron.

    Con `usuario`, solo los dirigidos a esa persona: en la casilla común, `ana+pizza@` no es
    para el hilo «Pizza» de otro.
    """
    ext_a_hilo = {extension(n): n for n in nombres if extension(n)}
    salida: dict[str, list[Correo]] = {}
    for c in correos:
        destinos = [d for d in re.split(r",\s*", c.para) if d.strip()] or [c.para]
        if usuario and not any(_usuario_de(d) == usuario for d in destinos):
            continue
        hilo = next((ext_a_hilo[extension_de(d)] for d in destinos if extension_de(d) in ext_a_hilo), None)
        if hilo:
            salida.setdefault(hilo, []).append(c)
    return salida


def conversaciones(correos: list[Correo]) -> list[list[Correo]]:
    """Agrupa en hilos de correo por Message-Id / In-Reply-To / References.

    Si falta un eslabón (un mensaje intermedio que no está), los que lo citan igual quedan
    juntos porque comparten la raíz de `References`. Sin ningún encabezado de respuesta,
    se agrupa por el asunto sin «Re:». Las conversaciones van con la más reciente arriba.
    """
    from email.utils import parsedate_to_datetime

    padre: dict[str, str] = {}

    def raiz(x: str) -> str:
        while padre.get(x, x) != x:
            x = padre[x]
        return x

    def unir(a: str, b: str) -> None:
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            padre[rb] = ra

    def clave(c: Correo) -> str:
        return c.id or _por_asunto(c.asunto)

    for c in correos:
        k = clave(c)
        padre.setdefault(k, k)
        respondidos = [*c.referencias, *c.responde.split()]
        for otro in respondidos:
            padre.setdefault(otro, otro)
            unir(otro, k)
        # sin cabeceras de respuesta (`mail -s "Re: …"` no las pone), el asunto sin «Re:» es
        # lo único que lo ata a su conversación
        if c.id and not respondidos:
            asunto = _por_asunto(c.asunto)
            padre.setdefault(asunto, asunto)
            unir(asunto, k)

    grupos: dict[str, list[Correo]] = {}
    for c in correos:
        grupos.setdefault(raiz(clave(c)), []).append(c)

    def cuando(c: Correo) -> float:
        try:
            return parsedate_to_datetime(c.fecha).timestamp()
        except (TypeError, ValueError):
            return 0.0

    salida = [sorted(g, key=cuando) for g in grupos.values()]
    salida.sort(key=lambda g: cuando(g[-1]), reverse=True)
    return salida


def _por_asunto(asunto: str) -> str:
    """La clave de un correo sin encabezados de respuesta: su asunto sin «Re:», en minúsculas."""
    return "asunto:" + re.sub(r"^((re|fw|fwd)\s*:\s*)+", "", asunto.strip(), flags=re.I).lower()


def json_correo(c: Correo) -> dict:
    return {"id": c.id, "de": c.de, "para": c.para, "asunto": c.asunto, "fecha": c.fecha,
            "estado": c.estado, "nuevo": c.nuevo, **({"cuerpo": c.cuerpo} if c.cuerpo else {})}
