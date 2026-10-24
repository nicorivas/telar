"""La gestión de personas del bus: quién tiene cuenta y con qué rol, quién pidió entrar, y decidirlo.

Todo vive en la máquina del bus (telar.cuentas, telar.unirse) y lo atiende su nodo; desde cualquier otra
máquina se pide por el bus, al servicio `admin.<dueño>`:

- desde otra máquina del dueño, dentro de su propia cuenta;
- desde la de un admin, por la importación que el servidor solo les da a las cuentas admin (telar.cuentas): una
  cuenta miembro no tiene por dónde pedirlo. El nodo igual revisa el rol de quien pide, que el servidor le dice
  (`Nats-Request-Info`).

Los roles:

    dueño     quien corre el bus (uno). No se le cambia el rol ni se le quita la cuenta.
    admin     aprueba y rechaza pedidos, quita cuentas y cambia roles, como el dueño, salvo lo del dueño.
    miembro   su cuenta y nada más: lo de siempre.

Las acciones (`atender`): `ver`, `aprobar` (un pedido, con el rol que entra: miembro si no se dice),
`rechazar`, `quitar` (una cuenta) y `rol` (cambiarlo). Las que cambian algo recargan el bus.

Lo usan `telar bus personas|pedidos|aprobar|rechazar|quitar|rol`, `GET /personas`, `POST /personas/<accion>` y
la sección «personas» de ⚙ en la página.
"""

from __future__ import annotations

import time

ACCIONES = ("ver", "aprobar", "rechazar", "quitar", "rol")
#: cuánto se espera la respuesta de la máquina del bus (aprobar recarga el servidor)
ESPERA = 30
#: cuántos días se siguen mostrando los pedidos ya decididos
DIAS_DECIDIDOS = 14


class ErrorDePersonas(Exception):
    """Lo pedido no se puede; el mensaje es para la persona. `codigo`, el HTTP que le corresponde."""

    def __init__(self, mensaje: str, codigo: int = 409) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


# ── en la máquina del bus ────────────────────────────────────────────────────────────

def _roles(dueno: str) -> dict[str, str]:
    """Los roles de las cuentas, con el dueño anotado (la primera vez se escribe: es quien corre el bus)."""
    from telar import cuentas

    base = cuentas.carpeta()
    roles = cuentas.leer_roles(base)
    if dueno and roles.get(dueno) != cuentas.DUENO:
        roles = {n: r for n, r in roles.items() if r != cuentas.DUENO}
        roles[dueno] = cuentas.DUENO
        cuentas.escribir_roles(base, roles)
    return roles


def rol_de(roles: dict[str, str], nombre: str) -> str:
    from telar import cuentas

    return roles.get(nombre, cuentas.MIEMBRO)


def ver(dueno: str, quien: str, *, ahora: float | None = None) -> dict:
    """Las cuentas con su rol (el dueño primero, después los admin, después el resto) y los pedidos: los pendientes
    y los decididos de los últimos días."""
    from telar import cuentas, unirse

    roles = _roles(dueno)
    orden = {cuentas.DUENO: 0, cuentas.ADMINISTRA: 1, cuentas.MIEMBRO: 2}
    personas = sorted(({"nombre": n, "rol": rol_de(roles, n)} for n in cuentas.leer(cuentas.carpeta())),
                      key=lambda p: (orden[p["rol"]], p["nombre"]))
    corte = (ahora if ahora is not None else time.time()) - DIAS_DECIDIDOS * 86400
    pedidos = []
    for pid, p in sorted(unirse.leer_pedidos().items(), key=lambda x: -x[1]["cuando"]):
        if p["estado"] != "pendiente" and p.get("decidido", p["cuando"]) < corte:
            continue
        pedidos.append({"id": pid, "persona": p["persona"], "estado": p["estado"], "cuando": p["cuando"],
                        "decidido": p.get("decidido"), "por": p.get("por", ""), "tailscale": p["tailscale"],
                        "desde": p["nodo"] or p["ip"], "maquina": p.get("maquina", ""), "equipo": p.get("equipo", "")})
    return {"dueno": dueno, "quien": quien, "rol": rol_de(roles, quien), "personas": personas, "pedidos": pedidos,
            "roles": list(cuentas.ROLES)}


def atender(dueno: str, quien: str, pedido: dict) -> dict:
    """Una acción de gestión, pedida por `quien` (su nombre en el bus), en la máquina del bus de `dueno`.
    Devuelve lo que hay después (`ver`), con `hecho` (qué se hizo, en una línea) y `falta` si el bus no se pudo
    recargar."""
    from telar import cuentas, unirse

    accion = str(pedido.get("accion") or "ver")
    if accion not in ACCIONES:
        raise ErrorDePersonas(f"«{accion}» no es una acción: {', '.join(ACCIONES)}", 422)
    if not unirse.administra_aqui():
        raise ErrorDePersonas("esta máquina no tiene las cuentas del bus", 404)
    roles = _roles(dueno)
    if quien != dueno and roles.get(quien) != cuentas.ADMINISTRA:
        raise ErrorDePersonas(f"«{quien or 'nadie'}» no administra el bus: eso lo hace {dueno} o un admin", 403)
    if accion == "ver":
        return ver(dueno, quien)
    try:
        hecho = _hacer(accion, pedido, dueno, quien, roles)
    except (unirse.ErrorDeUnirse, cuentas.ErrorDeCuentas) as e:
        raise ErrorDePersonas(str(e)) from None
    falta = unirse.recargar_bus() if hecho.pop("recargar", False) else ""
    return {**ver(dueno, quien), "hecho": hecho["texto"], "falta": falta}


def _hacer(accion: str, pedido: dict, dueno: str, quien: str, roles: dict[str, str]) -> dict:
    from telar import cuentas, unirse

    base = cuentas.carpeta()
    if accion in ("aprobar", "rechazar"):
        pid = str(pedido.get("pedido") or "")
        if not pid:
            raise ErrorDePersonas("¿cuál pedido? falta su id", 422)
        rol = str(pedido.get("rol") or cuentas.MIEMBRO)
        if rol not in (cuentas.ADMINISTRA, cuentas.MIEMBRO):
            raise ErrorDePersonas(f"se entra como {cuentas.ADMINISTRA} o {cuentas.MIEMBRO}, no como «{rol}»", 422)
        p = unirse.decidir(pid, accion == "aprobar", por=quien)
        if accion == "rechazar":
            return {"texto": f"{p['persona']}: pedido rechazado"}
        if rol == cuentas.ADMINISTRA:
            cuentas.escribir_roles(base, {**cuentas.leer_roles(base), p["persona"]: cuentas.ADMINISTRA})
            cuentas.escribir(base, cuentas.leer(base))
        return {"texto": f"{p['persona']}: cuenta nueva en el bus, como {rol}", "recargar": True}
    nombre = cuentas.validar(str(pedido.get("nombre") or ""))
    personas = cuentas.leer(base)
    if nombre not in personas:
        raise ErrorDePersonas(f"«{nombre}» no tiene cuenta en el bus", 404)
    if nombre == dueno:
        raise ErrorDePersonas(f"{dueno} es el dueño del bus: su cuenta y su rol no se tocan desde aquí")
    if accion == "quitar":
        if nombre == quien:
            raise ErrorDePersonas("tu propia cuenta no te la quitas tú: pídeselo a otro admin o al dueño")
        del personas[nombre]
        cuentas.escribir(base, personas)
        return {"texto": f"{nombre}: sin cuenta en el bus", "recargar": True}
    rol = str(pedido.get("rol") or "")
    if rol not in (cuentas.ADMINISTRA, cuentas.MIEMBRO):
        raise ErrorDePersonas(f"el rol es {cuentas.ADMINISTRA} o {cuentas.MIEMBRO}, no «{rol}»", 422)
    if rol_de(roles, nombre) == rol:
        return {"texto": f"{nombre} ya es {rol}"}
    nuevos = {n: r for n, r in roles.items() if n != nombre}
    if rol == cuentas.ADMINISTRA:
        nuevos[nombre] = cuentas.ADMINISTRA
    cuentas.escribir_roles(base, nuevos)
    cuentas.escribir(base, personas)
    return {"texto": f"{nombre}: ahora {rol}", "recargar": True}


# ── desde cualquier máquina ──────────────────────────────────────────────────────────

def dueno_del_bus(config) -> str:
    """A quién se le piden las acciones: `[bus] administra`, o esta misma persona."""
    from telar import bus as mod_bus

    return getattr(config.bus, "administra", "") or mod_bus.persona(config)


def pedir(config, pedido: dict) -> dict:
    """Una acción de gestión: aquí mismo si esta es la máquina del bus; si no, a su nodo, por el bus."""
    from telar import bus as mod_bus
    from telar import cuentas, unirse

    yo = mod_bus.persona(config)
    if unirse.administra_aqui():
        return atender(yo, yo, pedido)
    if not mod_bus.hay_bus(config):
        raise ErrorDePersonas("no hay bus: la gestión de personas vive en la máquina del bus", 404)
    return por_el_bus(config, cuentas.ADMIN.format(dueno_del_bus(config)), pedido,
                      sin_respuesta="no administras el bus, o su máquina no está atendiendo (¿sin su nodo, o con un "
                                    "telar más viejo?)")


def por_el_bus(config, tema: str, pedido: dict, *, plazo: float = ESPERA, sin_respuesta: str = "") -> dict:
    """Un pedido con respuesta a un servicio del bus (`tema`), con el JSON que contesta su nodo: `ok: false` es un
    ErrorDePersonas con su código. Por la conexión del nodo si esta máquina tiene una viva; si no, por una propia."""
    import asyncio
    import json

    from telar import bus as mod_bus

    cuerpo = json.dumps(pedido, ensure_ascii=False).encode()

    async def _por(nc):
        r = await nc.request(tema, cuerpo, timeout=plazo)
        return json.loads(r.data)

    async def _pedir():
        nc = await mod_bus.conectar(config)
        try:
            return await _por(nc)
        finally:
            await nc.close()

    try:
        viva = mod_bus._conexion_viva()
        if viva is not None:
            nc, bucle = viva
            r = asyncio.run_coroutine_threadsafe(asyncio.wait_for(_por(nc), plazo + 5), bucle).result(plazo + 10)
        else:
            r = asyncio.run(asyncio.wait_for(_pedir(), plazo + 5))
    except mod_bus.ErrorDeBus as e:
        raise ErrorDePersonas(str(e), 502) from None
    except Exception as e:  # noqa: BLE001 - nadie atiende, o no a tiempo
        if "NoResponders" in type(e).__name__:
            raise ErrorDePersonas(sin_respuesta or "nadie atiende ese servicio del bus", 403) from None
        raise ErrorDePersonas(f"la máquina del bus no respondió: {type(e).__name__}", 502) from None
    if not isinstance(r, dict):
        raise ErrorDePersonas("la máquina del bus no devolvió JSON", 502)
    if not r.get("ok", True):
        raise ErrorDePersonas(str(r.get("error") or "no se pudo"), int(r.get("codigo") or 409))
    return r


def atender_pedido_del_bus(persona: str, datos: bytes, cabeceras: dict | None) -> dict:
    """Lo que hace el nodo de la máquina del bus con un pedido a `admin.<persona>`: quien pide es la cuenta que
    dice el servidor (`Nats-Request-Info`, al cruzar de cuenta), o la misma persona si no cruzó."""
    import json

    try:
        info = json.loads((cabeceras or {}).get("Nats-Request-Info", "{}"))
        quien = str(info.get("acc") or "") or persona
        pedido = json.loads(datos or b"{}")
        if not isinstance(pedido, dict):
            raise ValueError("no es un objeto")
        return {"ok": True, **atender(persona, quien, pedido)}
    except ErrorDePersonas as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}
    except ValueError as e:
        return {"ok": False, "error": f"el pedido no es JSON: {e}", "codigo": 422}
    except Exception as e:  # noqa: BLE001 - quien pide se entera; el nodo sigue
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300], "codigo": 500}
