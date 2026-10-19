"""`telar serve` — la API de telar: los mismos datos que la CLI, por HTTP, desde un proceso que se queda.

    telar serve                     en el socket Unix de siempre (<estado>/serve/telar.sock), solo para su dueño
    telar serve --socket RUTA       en otro socket
    telar serve --puerto 8771       en TCP, solo en 127.0.0.1 (para probar; en una máquina compartida,
                                    cualquier usuario de ella alcanzaría el puerto)

Lo que sirve y por qué está en telar.api. La documentación de cada ruta, en `/docs` (con --puerto) o
`curl --unix-socket <socket> http://telar/openapi.json`. Necesita el extra «serve»:
`pip install 'telar[serve]'`. Para que arranque solo: `servidor/telar-serve.service` y
`servidor/telar-serve.plist`.
"""

from __future__ import annotations

import os
from pathlib import Path

from telar.ordenes import _comun

AYUDA = "La API de telar: los mismos datos que la CLI, por HTTP, desde un proceso que se queda."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("serve", AYUDA)
    p.epilog = __doc__
    p.add_argument("--socket", default="", help="el socket Unix (por defecto, <estado>/serve.sock)")
    p.add_argument("--puerto", type=int, default=0, help="en TCP, en 127.0.0.1, en vez del socket")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        import uvicorn

        from telar import api
    except ImportError as e:
        return _comun.queja(f"falta el extra «serve» ({e.name}): pip install 'telar[serve]'")
    if o.puerto:
        uvicorn.run(api.app, host="127.0.0.1", port=o.puerto, log_level="warning")
        return 0
    sock = Path(o.socket).expanduser() if o.socket else api.socket_por_defecto()
    # solo su dueño entra a la carpeta del socket: uvicorn le pone al socket mismo permisos para todos
    # (0666), así que lo que protege es la carpeta, no el archivo
    sock.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(sock.parent, 0o700)
    if sock.exists():
        sock.unlink()  # uno que quedó de una vuelta anterior
    print(f"telar serve: {sock}", flush=True)
    uvicorn.run(api.app, uds=str(sock), log_level="warning")
    return 0
