"""`telar bus` — las cuentas del bus: una por persona, que el servidor NATS hace cumplir.

    telar bus persona NOMBRE                  darle una cuenta (o una clave nueva) a una persona
    telar bus persona NOMBRE --secreto RUTA   con el secreto de ese archivo (el tuyo: tu `[bus] token`)
    telar bus personas                        quiénes tienen cuenta
    telar bus quitar NOMBRE                   cerrarle la cuenta
    telar bus pedidos [--todos]               quiénes pidieron entrar (`telar instalar --unirse`, telar.unirse)
    telar bus aprobar ID                      darle la cuenta que pidió: su hash entra y el bus se recarga
    telar bus rechazar ID                     no dársela

Se corre en la máquina del bus, como la persona que lo administra. Cada persona tiene una cuenta propia:
lo suyo (casillas, estado de sus hilos, la foto de sus máquinas, los pedidos a sus nodos) no lo ve nadie
más, porque el servidor no lo deja. Su usuario es su nombre en el bus (`[bus] persona`, o su usuario del
sistema) y su clave es el secreto de `[bus] token`, el mismo en todas sus máquinas: con él también entra
una máquina suya a la terminal o la página de otra (`/pty?maquina=`, los boletos de `/maquinas`), y no
la de otra persona.

Sin `--secreto`, para ti se usa tu `[bus] token`; para otra persona se genera uno nuevo en
`~/.config/telar/bus/secretos/NOMBRE.token`, que hay que pasarle (a su `~/.config/telar/bus.token`) y
después borrar de aquí. El servidor guarda solo su hash. Después de cada cambio:

    systemctl --user reload telar-bus
"""

from __future__ import annotations

from pathlib import Path

from telar import cuentas
from telar.ordenes import _comun

AYUDA = "Las cuentas del bus: una por persona, que el servidor hace cumplir."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("bus", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=["persona", "personas", "quitar", "pedidos", "aprobar", "rechazar"])
    p.add_argument("--todos", action="store_true", help="en pedidos: también los ya decididos")
    p.add_argument("nombre", nargs="?", default="")
    p.add_argument("--secreto", default="", help="el archivo con el secreto de esa persona")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    base = cuentas.carpeta()
    if o.verbo in ("pedidos", "aprobar", "rechazar"):
        return _pedidos(o)
    try:
        personas = cuentas.leer(base)
        if o.verbo == "personas":
            for n in personas:
                print(n)
            if not personas:
                print(_comun.tenue("nadie tiene cuenta en el bus todavía: telar bus persona NOMBRE"))
            return 0
        if not o.nombre:
            return _comun.queja(f"¿quién? telar bus {o.verbo} NOMBRE")
        nombre = cuentas.validar(o.nombre)
        if o.verbo == "quitar":
            if nombre not in personas:
                return _comun.queja(f"{nombre} no tiene cuenta en el bus")
            del personas[nombre]
            conf = cuentas.escribir(base, personas)
            print(f"{nombre}: sin cuenta en el bus ({conf}).")
            print(_comun.tenue("falta: systemctl --user reload telar-bus"))
            return 0
        return _persona(ctx, base, personas, nombre, o.secreto)
    except cuentas.ErrorDeCuentas as e:
        return _comun.queja(str(e))


def _pedidos(o) -> int:
    """Los pedidos de entrada que llegaron a la puerta de esta máquina (telar.unirse), y decidirlos."""
    import time

    from telar import unirse

    try:
        if o.verbo == "pedidos":
            pedidos = unirse.leer_pedidos()
            vistos = [(pid, p) for pid, p in sorted(pedidos.items(), key=lambda x: x[1]["cuando"])
                      if o.todos or p["estado"] == "pendiente"]
            for pid, p in vistos:
                cuando = time.strftime("%d-%m %H:%M", time.localtime(p["cuando"]))
                print(f"{pid}  {p['persona']:<12} {p['estado']:<10} {cuando}  "
                      + _comun.tenue(f"{p['tailscale']} · {p['nodo'] or p['ip']} · {p['equipo'] or 'sin equipo'}"))
            if not vistos:
                print(_comun.tenue("nadie pidió entrar" if not pedidos else "nada pendiente (--todos: también los decididos)"))
            return 0
        if not o.nombre:
            return _comun.queja(f"¿cuál? telar bus {o.verbo} ID (telar bus pedidos los lista)")
        p = unirse.decidir(o.nombre, o.verbo == "aprobar")
    except (unirse.ErrorDeUnirse, cuentas.ErrorDeCuentas) as e:
        return _comun.queja(str(e))
    if o.verbo == "rechazar":
        print(f"{p['persona']}: pedido rechazado.")
        return 0
    falta = unirse.recargar_bus()
    print(f"{p['persona']}: cuenta nueva en el bus ({p['tailscale']}, desde {p['nodo'] or p['ip']}).")
    if falta:
        print(_comun.tenue(f"falta recargar el bus: {falta}"))
    else:
        print(_comun.tenue("el bus ya la conoce: su telar se conecta solo"))
    return 0


def _persona(ctx, base: Path, personas: dict[str, str], nombre: str, secreto_ruta: str) -> int:
    from telar import bus as mod_bus

    nuevo = ""
    if not secreto_ruta and nombre == mod_bus.persona(ctx.config) and ctx.config.bus.token:
        secreto_ruta = ctx.config.bus.token
    if secreto_ruta:
        ruta = Path(secreto_ruta).expanduser()
        try:
            secreto = ruta.read_text(encoding="utf-8").strip()
        except OSError as e:
            return _comun.queja(f"no puedo leer el secreto ({ruta}): {e}")
        if len(secreto) < 24:
            return _comun.queja(f"el secreto de {ruta} es muy corto: al menos 24 caracteres")
    else:
        secreto = cuentas.secreto_nuevo()
        nuevo = str(base / "secretos" / f"{nombre}.token")
        cuentas.guardar_secreto(Path(nuevo), secreto)
    habia = nombre in personas
    personas[nombre] = cuentas.hashear(secreto)
    conf = cuentas.escribir(base, personas)
    print(f"{nombre}: {'clave nueva' if habia else 'cuenta nueva'} en el bus ({conf}).")
    if nuevo:
        print(f"su secreto quedó en {nuevo}: pásaselo a su ~/.config/telar/bus.token y bórralo de aquí.")
    print(_comun.tenue("falta: systemctl --user reload telar-bus"))
    return 0
