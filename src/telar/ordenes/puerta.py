"""`telar puerta` — la puerta de un servidor con alojados (telar.puerta): una sola dirección para todas las
personas, y cada pedido al telar de quien lo hace.

    telar puerta servir [--socket RUTA]   atender (lo corre su servicio, `telar-puerta.service`, como telar-puerta)
    telar puerta tabla [--json]           quién entra y a qué usuario va, y lo que no se pudo leer
    telar puerta quien <ip>               qué haría la puerta con un pedido desde esa dirección de Tailscale

Se instala con `servidor/telar-puerta-instalar` (root); después, `tailscale serve --bg --https=443
unix:/run/telar/puerta/puerta.sock` la pone en la dirección del servidor.
"""

from __future__ import annotations

import os
from pathlib import Path

from telar.ordenes import _comun

AYUDA = "La puerta de un servidor con alojados: una sola dirección, y cada persona a su telar."


def main(argv: list[str], ctx) -> int:
    from telar import puerta as mod

    p = _comun.analizador("puerta", AYUDA)
    p.epilog = __doc__
    p.add_argument("accion", choices=["servir", "tabla", "quien"])
    p.add_argument("ip", nargs="?", default="")
    p.add_argument("--socket", default=str(mod.SOCKETS / "puerta" / "puerta.sock"))
    p.add_argument("--json", action="store_true")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    tabla = mod.leer_tabla()
    if o.accion == "tabla":
        if o.json:
            return _comun.escribir_json({"url": tabla.url, "personas": tabla.personas, "problemas": tabla.problemas})
        print(f"la puerta: {tabla.url or '(sin url en ' + str(mod.CONFIG) + ')'}")
        for cuenta, usuario in sorted(tabla.personas.items()):
            sock = mod.socket_de(usuario)
            print(f"  {cuenta:40} → {usuario:16} {'' if sock.exists() else _comun.tenue('(su telar no está escuchando)')}")
        for x in tabla.problemas:
            print(_comun.tenue(f"  ! {x}"))
        return 0
    if o.accion == "quien":
        if not o.ip:
            return _comun.queja("¿qué dirección? telar puerta quien 100.x.y.z")
        try:
            usuario, cuenta = mod.Identificar(tabla)(o.ip)
        except mod.ErrorDePuerta as e:
            print(f"no entra: {e}")
            return 1
        print(f"{o.ip}: {cuenta} → {usuario} ({mod.socket_de(usuario)})")
        return 0
    try:
        import uvicorn
    except ImportError as e:
        return _comun.queja(f"falta el extra «serve» ({e.name}): pip install 'telar[serve]'")
    sock = Path(o.socket)
    sock.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(sock.parent, 0o700)  # solo la puerta (y root: tailscaled) llegan a su socket
    if sock.exists():
        sock.unlink()
    for x in tabla.problemas:
        print(f"telar puerta: {x}", flush=True)
    print(f"telar puerta: {sock} · {len(tabla.personas)} cuenta(s) · {tabla.url}", flush=True)
    uvicorn.run(mod.crear(tabla), uds=str(sock), log_level="warning", proxy_headers=False)
    return 0
