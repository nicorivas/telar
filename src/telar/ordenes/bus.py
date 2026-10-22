"""`telar bus` — las cuentas del bus: una por persona, que el servidor NATS hace cumplir, y quién las administra.

    telar bus personas                        quiénes tienen cuenta, con su rol (dueño, admin, miembro)
    telar bus pedidos [--todos]               quiénes pidieron entrar (`telar instalar --unirse`, telar.unirse)
    telar bus aprobar ID [--rol admin]        darle la cuenta que pidió: su hash entra y el bus se recarga
    telar bus rechazar ID                     no dársela
    telar bus quitar NOMBRE                   cerrarle la cuenta
    telar bus rol NOMBRE admin|miembro        cambiarle el rol
    telar bus persona NOMBRE                  darle una cuenta (o una clave nueva) a mano, con un secreto de aquí
    telar bus persona NOMBRE --secreto RUTA   con el secreto de ese archivo (el tuyo: tu `[bus] token`)

Todas menos `persona` se corren desde cualquier máquina: en la del bus se hacen ahí mismo, y desde otra se le
piden a su nodo (telar.personas). Las puede pedir el dueño del bus (quien lo corre) y los admin; un miembro
no tiene por dónde. Desde la máquina de un admin, `[bus] administra` dice quién es el dueño (lo escribe
`telar instalar --unirse`). Lo mismo se hace en la página, en ⚙ personas.

Cada persona tiene una cuenta propia: lo suyo (casillas, estado de sus hilos, la foto de sus máquinas, los
pedidos a sus nodos) no lo ve nadie más, porque el servidor no lo deja. Su usuario es su nombre en el bus
(`[bus] persona`, o su usuario del sistema) y su clave es el secreto de `[bus] token`, el mismo en todas sus
máquinas: con él también entra una máquina suya a la terminal o la página de otra (`/pty?maquina=`, los
boletos de `/maquinas`), y no la de otra persona.

`persona` se corre en la máquina del bus. Sin `--secreto`, para ti se usa tu `[bus] token`; para otra persona
se genera uno nuevo en `~/.config/telar/bus/secretos/NOMBRE.token`, que hay que pasarle (a su
`~/.config/telar/bus.token`) y después borrar de aquí. El servidor guarda solo su hash. Después:

    systemctl --user reload telar-bus

(las demás recargan el bus solas). Lo de siempre para alguien nuevo es `telar instalar --unirse`, que no
mueve ningún secreto.
"""

from __future__ import annotations

import time
from pathlib import Path

from telar import cuentas
from telar.ordenes import _comun

AYUDA = "Las cuentas del bus: una por persona, que el servidor hace cumplir, y quién las administra."

#: los verbos que van por telar.personas (desde cualquier máquina)
GESTION = ("personas", "pedidos", "aprobar", "rechazar", "quitar", "rol")


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("bus", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=["persona", *GESTION])
    p.add_argument("nombre", nargs="?", default="")
    p.add_argument("rol_nuevo", nargs="?", default="", metavar="ROL")
    p.add_argument("--todos", action="store_true", help="en pedidos: también los ya decididos")
    p.add_argument("--rol", default="", help="en aprobar: admin o miembro (miembro si no se dice)")
    p.add_argument("--secreto", default="", help="en persona: el archivo con el secreto de esa persona")
    p.add_argument("--json", action="store_true", help="lo que hay, en JSON (telar.personas)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo in GESTION:
        return _gestion(ctx, o)
    base = cuentas.carpeta()
    try:
        if not o.nombre:
            return _comun.queja("¿quién? telar bus persona NOMBRE")
        return _persona(ctx, base, cuentas.leer(base), cuentas.validar(o.nombre), o.secreto)
    except cuentas.ErrorDeCuentas as e:
        return _comun.queja(str(e))


def _gestion(ctx, o) -> int:
    """Lo que va por telar.personas: mirar y decidir, aquí o en la máquina del bus."""
    import json

    from telar import personas

    pedido: dict = {"accion": "ver"}
    if o.verbo in ("aprobar", "rechazar"):
        if not o.nombre:
            return _comun.queja(f"¿cuál? telar bus {o.verbo} ID (telar bus pedidos los lista)")
        pedido = {"accion": o.verbo, "pedido": o.nombre, "rol": o.rol}
    elif o.verbo == "quitar":
        if not o.nombre:
            return _comun.queja("¿a quién? telar bus quitar NOMBRE")
        pedido = {"accion": "quitar", "nombre": o.nombre}
    elif o.verbo == "rol":
        if not o.nombre or not o.rol_nuevo:
            return _comun.queja("telar bus rol NOMBRE admin|miembro")
        pedido = {"accion": "rol", "nombre": o.nombre, "rol": o.rol_nuevo}
    try:
        r = personas.pedir(ctx.config, pedido)
    except (personas.ErrorDePersonas, cuentas.ErrorDeCuentas) as e:
        return _comun.queja(str(e))
    if o.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0
    if r.get("hecho"):
        print(f"{r['hecho']}.")
        if r.get("falta"):
            print(_comun.tenue(f"falta recargar el bus en su máquina: {r['falta']}"))
        elif o.verbo == "aprobar":
            print(_comun.tenue("el bus ya la conoce: su telar se conecta solo"))
        return 0
    if o.verbo == "personas":
        for x in r["personas"]:
            print(f"{x['nombre']:<16} {x['rol']}")
        if not r["personas"]:
            print(_comun.tenue("nadie tiene cuenta en el bus todavía"))
        return 0
    vistos = [x for x in sorted(r["pedidos"], key=lambda x: x["cuando"]) if o.todos or x["estado"] == "pendiente"]
    for x in vistos:
        cuando = time.strftime("%d-%m %H:%M", time.localtime(x["cuando"]))
        por = f" por {x['por']}" if x.get("por") else ""
        print(f"{x['id']}  {x['persona']:<12} {x['estado'] + por:<20} {cuando}  "
              + _comun.tenue(f"{x['tailscale']} · {x['desde']} · {x['equipo'] or 'sin equipo'}"))
    if not vistos:
        print(_comun.tenue("nadie pidió entrar" if not r["pedidos"] else "nada pendiente (--todos: también los decididos)"))
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
