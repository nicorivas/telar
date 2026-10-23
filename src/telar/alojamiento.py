"""El servidor como mainframe: una persona del bus pide un lugar en él y sus hilos viven ahí.

Un servidor de telar tiene dos oficios. El de siempre es ser una máquina más de quien lo corre (y alojar el bus).
El otro es **alojar a otras personas**: cada una que ya tiene cuenta en el bus puede pedir un lugar, y cuando
quien administra lo aprueba, el servidor le arma una cuenta propia (un usuario Linux con tope de recursos, su
telar, su Claude Code y su propio nodo, con su cuenta del bus). Desde ahí el servidor es una máquina más *de esa
persona*: sus hilos nacen y viven aquí, y los ve y los abre desde su laptop por el bus, como los de cualquier
otra máquina suya. Lo de una no lo ve otra: el aislamiento lo hace el sistema (usuarios, permisos, systemd) y el
bus (una cuenta por persona).

El pedido va por el bus, al servicio `alojar.<dueño>` (telar.cuentas): lo exporta la cuenta del dueño a todas, y
el servidor NATS dice de qué cuenta viene (`Nats-Request-Info`), así que nadie pide a nombre de otro. Lo atiende
el nodo de la máquina del bus. Las acciones:

    pedir        (cualquiera del bus) un lugar para mí; lleva mi secreto del bus, y opcional mi llave ssh
    estado       (cualquiera) cómo va el mío
    ver          (dueño y admin) todos los alojamientos
    aprobar      (dueño y admin) crearle el lugar
    rechazar     (dueño y admin)
    quitar       (dueño y admin) cerrarle el lugar (su carpeta se conserva)

El nodo corre sin privilegios (y con `NoNewPrivileges`), así que no hay sudo: lo que necesita root lo hace
`servidor/telar-alojar`, un servicio systemd de root que vigila una carpeta de pedidos (`/var/spool/telar-alojar`,
de quien corre el bus). El nodo deja ahí un archivo y espera el resultado. Ese ayudante no importa nada de telar
ni de la carpeta de nadie, y valida cada campo por su cuenta: lo peor que le puede llegar es un nombre de usuario
nuevo con tope de recursos.

**El secreto viaja una vez.** El telar de la persona usa el mismo secreto del bus en todas sus máquinas (con él
se abren las terminales de una máquina a otra y se firman los boletos), así que el servidor lo necesita para el
nodo que le arma. Viaja en el pedido, dentro del bus (que va por Tailscale); el nodo comprueba que es el de la
cuenta (contra su hash) antes de aceptarlo, lo guarda en un archivo privado hasta que se aprueba, y lo borra al
dejarlo en el `bus.token` del usuario nuevo. Quien administra el servidor es root en él, así que de por sí podría
leerlo: lo que importa es que no queda en ningún otro lado.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Callable

#: dónde deja el nodo los pedidos para el ayudante de root, y dónde éste deja los resultados
SPOOL = Path("/var/spool/telar-alojar")
#: el primer puerto de página para los alojados (el 8780 es el de la máquina de quien administra)
PRIMER_PUERTO = 8781
ULTIMO_PUERTO = 8899
#: topes por defecto de cada alojado (el servidor es de 8 GB)
MEMORIA, CPU = "2500M", "100%"
#: cuánto se espera al ayudante antes de dar el alojamiento por caído
ESPERA_AYUDANTE = 30 * 60
#: usuarios del sistema que ninguna persona puede tomar, aunque tenga cuenta en el bus
RESERVADOS = frozenset({
    "root", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp", "proxy", "www-data",
    "backup", "list", "irc", "gnats", "nobody", "systemd-network", "systemd-resolve", "sshd", "ubuntu", "admin",
    "agentes", "archivo", "postfix", "tailscale", "telar", "operator", "adm", "wheel", "sudo", "staff", "users"})
NOMBRE = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
LLAVE = re.compile(r"^ssh-(ed25519|rsa) [A-Za-z0-9+/=]+( [^\n]*)?$")
ACCIONES = ("pedir", "estado", "ver", "aprobar", "rechazar", "quitar")
#: las que son de quien administra
DE_ADMIN = frozenset({"ver", "aprobar", "rechazar", "quitar"})


class ErrorDeAlojamiento(Exception):
    """Lo pedido no se puede; el mensaje es para la persona. `codigo`, el HTTP que le corresponde."""

    def __init__(self, mensaje: str, codigo: int = 409) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


# ── el archivo de alojamientos (en la máquina del bus) ────────────────────────────────

def _archivo() -> Path:
    from telar import cuentas

    return cuentas.carpeta() / "alojamientos.json"


def leer() -> dict[str, dict]:
    try:
        return json.loads(_archivo().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise ErrorDeAlojamiento(f"{_archivo()}: no se puede leer: {e}", 500) from None


_candado = threading.Lock()


def _guardar(datos: dict[str, dict]) -> None:
    from telar import cuentas

    cuentas._escribir_privado(_archivo(), json.dumps(datos, ensure_ascii=False, indent=1) + "\n")


def _cambiar(persona: str, **campos) -> dict:
    """Pone `campos` en el alojamiento de `persona` (los `None` lo quitan) y lo devuelve."""
    with _candado:
        datos = leer()
        a = datos.setdefault(persona, {})
        for k, v in campos.items():
            if v is None:
                a.pop(k, None)
            else:
                a[k] = v
        _guardar(datos)
        return dict(a)


def publico(a: dict, persona: str) -> dict:
    """Lo que se puede mostrar de un alojamiento: nunca el secreto."""
    return {"persona": persona, **{k: v for k, v in a.items() if k != "secreto"}}


def puerto_libre(datos: dict[str, dict]) -> int:
    usados = {a.get("puerto") for a in datos.values() if a.get("estado") in ("preparando", "activo", "falló")}
    for p in range(PRIMER_PUERTO, ULTIMO_PUERTO + 1):
        if p not in usados:
            return p
    raise ErrorDeAlojamiento("el servidor no tiene más puertos de página para alojados", 507)


# ── el ayudante de root, por la carpeta de pedidos ────────────────────────────────────

def ayudante(pedido: dict, *, spool: Path = SPOOL, espera: float = ESPERA_AYUDANTE,
             dormir: Callable[[float], None] = time.sleep, ahora: Callable[[], float] = time.time) -> dict:
    """Le deja un pedido al ayudante de root y espera su resultado: {ok, error?, …}. Si el ayudante no está
    instalado (la carpeta no existe), lo dice con cómo instalarlo."""
    pendientes, resultados = spool / "pendientes", spool / "resultados"
    if not pendientes.is_dir() or not resultados.is_dir():
        return {"ok": False, "error": f"el ayudante de root no está instalado ({spool}): servidor/README.md, "
                                      f"«Alojar a otras personas»"}
    ident = secrets.token_hex(8)
    from telar import cuentas

    cuentas._escribir_privado(pendientes / f"{ident}.json", json.dumps({**pedido, "id": ident}))
    resultado = resultados / f"{ident}.json"
    limite = ahora() + espera
    while ahora() < limite:
        if resultado.exists():
            try:
                r = json.loads(resultado.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                dormir(0.5)  # a medio escribir
                continue
            resultado.unlink(missing_ok=True)
            return r if isinstance(r, dict) else {"ok": False, "error": "el ayudante contestó algo raro"}
        dormir(1)
    (pendientes / f"{ident}.json").unlink(missing_ok=True)
    return {"ok": False, "error": f"el ayudante de root no contestó en {int(espera // 60)} min: "
                                  f"`systemctl status telar-alojar` en el servidor"}


# ── lo que se hace en la máquina del bus ──────────────────────────────────────────────

def validar_nombre(persona: str) -> str:
    if not NOMBRE.match(persona) or persona in RESERVADOS:
        raise ErrorDeAlojamiento(f"«{persona}» no sirve como usuario del servidor (minúsculas, cifras, - y _; sin "
                                 f"nombres del sistema)", 422)
    return persona


def pedir_aqui(persona: str, datos: dict, dueno: str, *, ahora: float | None = None) -> dict:
    """Anota que `persona` (una cuenta del bus, ya verificada por el servidor NATS) pide un lugar."""
    from telar import cuentas

    if persona == dueno:
        raise ErrorDeAlojamiento(f"{dueno} corre este servidor: ya es de la casa", 409)
    cuenta = cuentas.leer(cuentas.carpeta()).get(persona)
    if cuenta is None:
        raise ErrorDeAlojamiento(f"«{persona}» no tiene cuenta en el bus", 403)
    validar_nombre(persona)
    secreto = str(datos.get("secreto") or "")
    if not cuentas.verificar(secreto, cuenta):
        raise ErrorDeAlojamiento("el secreto que mandaste no es el de tu cuenta del bus", 403)
    llave = str(datos.get("llave") or "").strip()
    if llave and not LLAVE.match(llave):
        raise ErrorDeAlojamiento("la llave debe ser una llave pública ssh en una línea (ssh-ed25519 AAAA… comentario)", 422)
    actual = leer().get(persona, {})
    if actual.get("estado") in ("activo", "preparando"):
        raise ErrorDeAlojamiento(f"ya tienes un lugar en el servidor ({actual['estado']})", 409)
    _cambiar(persona, estado="pendiente", cuando=int(ahora if ahora is not None else time.time()),
             maquina=str(datos.get("maquina") or "")[:64], llave=llave or None, secreto=secreto,
             error=None, decidido=None, por=None)
    return {"hecho": f"{persona}: pedido anotado; queda pendiente hasta que {dueno} o un admin lo apruebe"}


def _admin(quien: str, dueno: str) -> None:
    from telar import cuentas, personas

    roles = personas._roles(dueno)
    if quien != dueno and roles.get(quien) != cuentas.ADMINISTRA:
        raise ErrorDeAlojamiento(f"«{quien or 'nadie'}» no administra este servidor: eso lo hace {dueno} o un admin", 403)


def ver(quien: str, dueno: str, *, ahora: float | None = None) -> dict:
    """Todos los alojamientos para quien administra; el propio, para cualquiera."""
    from telar import personas

    datos = leer()
    _caducar(datos, ahora)
    es_admin = quien == dueno or personas._roles(dueno).get(quien) == "admin"
    mios = {p: a for p, a in datos.items() if es_admin or p == quien}
    return {"dueno": dueno, "quien": quien, "administra": es_admin,
            "alojamientos": [publico(a, p) for p, a in sorted(mios.items(), key=lambda x: -x[1].get("cuando", 0))]}


def _caducar(datos: dict, ahora: float | None) -> None:
    """Un alojamiento «preparando» que nadie terminó (el nodo se cayó a medias) se da por fallido."""
    ahora = ahora if ahora is not None else time.time()
    for p, a in datos.items():
        if a.get("estado") == "preparando" and ahora - a.get("empezo", ahora) > ESPERA_AYUDANTE + 120 \
                and p not in _EN_CURSO:
            a.update(estado="falló", error="se interrumpió mientras se preparaba (el nodo se reinició): aprobar de nuevo")


_EN_CURSO: set[str] = set()


def atender(dueno: str, quien: str, pedido: dict, config=None, *, sincrono: bool = False,
            ayuda: Callable[[dict], dict] | None = None) -> dict:
    """Una acción de alojamiento, pedida por `quien` (su nombre en el bus), en la máquina del bus de `dueno`.
    `config`: la de este nodo (de ahí sale la dirección del bus que verá el nodo nuevo). `sincrono`: esperar a
    que el ayudante termine (las pruebas); `ayuda`: cómo hablarle (las pruebas)."""
    from telar import unirse

    accion = str(pedido.get("accion") or "estado")
    if accion not in ACCIONES:
        raise ErrorDeAlojamiento(f"«{accion}» no es una acción: {', '.join(ACCIONES)}", 422)
    if not unirse.administra_aqui():
        raise ErrorDeAlojamiento("esta máquina no es el servidor del bus", 404)
    if not quien:
        raise ErrorDeAlojamiento("no sé quién pide", 403)
    if accion in DE_ADMIN:
        _admin(quien, dueno)
    if accion == "pedir":
        hecho = pedir_aqui(quien, pedido, dueno)
        return {**ver(quien, dueno), **hecho}
    if accion in ("estado", "ver"):
        return ver(quien, dueno)
    persona = validar_nombre(str(pedido.get("persona") or pedido.get("nombre") or ""))
    a = leer().get(persona)
    if a is None:
        raise ErrorDeAlojamiento(f"«{persona}» no pidió un lugar: telar servidor pedidos", 404)
    if accion == "rechazar":
        if a["estado"] not in ("pendiente", "falló"):
            raise ErrorDeAlojamiento(f"el pedido de {persona} está {a['estado']}: no se rechaza")
        _cambiar(persona, estado="rechazado", decidido=int(time.time()), por=quien, secreto=None)
        return {**ver(quien, dueno), "hecho": f"{persona}: pedido rechazado"}
    ayuda = ayuda or ayudante
    if accion == "aprobar":
        if a["estado"] not in ("pendiente", "falló"):
            raise ErrorDeAlojamiento(f"el pedido de {persona} está {a['estado']}: no se aprueba")
        if not a.get("secreto"):
            raise ErrorDeAlojamiento(f"el pedido de {persona} ya no trae su secreto: que lo vuelva a pedir", 410)
        bus = getattr(getattr(config, "bus", None), "url", "") or ""
        if not re.match(r"^nats://[^\s/]+:\d+$", bus):
            raise ErrorDeAlojamiento("este nodo no sabe su dirección del bus ([bus] url): sin ella el alojado no se conecta", 500)
        puerto = a.get("puerto") or puerto_libre(leer())
        _cambiar(persona, estado="preparando", empezo=int(time.time()), decidido=int(time.time()), por=quien,
                 puerto=puerto, error=None)
        pedido_root = {"accion": "crear", "nombre": persona, "llave": a.get("llave") or "", "secreto": a["secreto"],
                       "puerto": puerto, "bus": bus, "memoria": MEMORIA, "cpu": CPU}
        _EN_CURSO.add(persona)
        if sincrono:
            _terminar(persona, pedido_root, ayuda)
        else:
            threading.Thread(target=_terminar, args=(persona, pedido_root, ayuda), daemon=True,
                             name=f"alojar-{persona}").start()
        return {**ver(quien, dueno), "hecho": f"{persona}: preparando su lugar en el servidor (tarda unos minutos)"}
    # quitar
    if a["estado"] not in ("activo", "falló", "preparando"):
        raise ErrorDeAlojamiento(f"{persona} no tiene un lugar que quitar ({a['estado']})")
    r = ayuda({"accion": "quitar", "nombre": persona})
    if not r.get("ok"):
        raise ErrorDeAlojamiento(f"no se pudo cerrar el lugar de {persona}: {r.get('error', '?')}", 502)
    _cambiar(persona, estado="quitado", decidido=int(time.time()), por=quien, secreto=None, error=None)
    return {**ver(quien, dueno), "hecho": f"{persona}: lugar cerrado (su carpeta se conserva)"}


def _terminar(persona: str, pedido_root: dict, ayuda: Callable[[dict], dict]) -> None:
    """Lo que pasa después de aprobar: el ayudante crea el lugar y el alojamiento queda activo, o fallido."""
    try:
        r = ayuda(pedido_root)
    except Exception as e:  # noqa: BLE001 - el hilo no puede morir callado
        r = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        _EN_CURSO.discard(persona)
    if r.get("ok"):
        _cambiar(persona, estado="activo", usuario=persona, secreto=None, error=None, listo=int(time.time()))
    else:
        _cambiar(persona, estado="falló", error=str(r.get("error") or "falló sin decir por qué")[:500])


def atender_pedido_del_bus(persona: str, datos: bytes, cabeceras: dict | None, config=None) -> dict:
    """Lo que hace el nodo de la máquina del bus con un pedido a `alojar.<persona>`: quien pide es la cuenta que dice
    el servidor (`Nats-Request-Info`, al cruzar de cuenta), o la misma persona si no cruzó."""
    try:
        info = json.loads((cabeceras or {}).get("Nats-Request-Info", "{}"))
        quien = str(info.get("acc") or "") or persona
        pedido = json.loads(datos or b"{}")
        if not isinstance(pedido, dict):
            raise ValueError("no es un objeto")
        return {"ok": True, **atender(persona, quien, pedido, config)}
    except ErrorDeAlojamiento as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}
    except ValueError as e:
        return {"ok": False, "error": f"el pedido no es JSON: {e}", "codigo": 422}
    except Exception as e:  # noqa: BLE001 - quien pide se entera; el nodo sigue
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300], "codigo": 500}


# ── desde cualquier máquina ──────────────────────────────────────────────────────────

def pedir(config, pedido: dict) -> dict:
    """Una acción de alojamiento: aquí mismo si esta es la máquina del bus; si no, al nodo que la tiene, por el bus."""
    from telar import bus as mod_bus
    from telar import cuentas, personas, unirse

    yo = mod_bus.persona(config)
    if unirse.administra_aqui():
        return atender(yo, yo, pedido, config)
    if not mod_bus.hay_bus(config):
        raise ErrorDeAlojamiento("no hay bus: el alojamiento se pide por él", 404)
    try:
        return personas.por_el_bus(
            config, cuentas.ALOJAR.format(personas.dueno_del_bus(config)), pedido, plazo=30,
            sin_respuesta="nadie atiende alojamientos en el bus: ¿el servidor tiene un telar más viejo, o "
                          "`[bus] administra` no es quien corre el bus?")
    except personas.ErrorDePersonas as e:
        raise ErrorDeAlojamiento(str(e), e.codigo) from None
