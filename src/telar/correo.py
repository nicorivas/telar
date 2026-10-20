"""Las direcciones del correo entre agentes: `usuario+hilo@servidor`.

En un servidor compartido, cada persona es un usuario y sus agentes se escribían por correo local, que
entrega el `cartero` del servidor (servidor/cartero). Entre los hilos de una misma persona, eso ya lo hace
el bus; queda el correo **entre personas** (`telar correo enviar`) y el directorio, hasta que el bus tenga
credenciales por persona (docs/propuestas/telar-para-otros.md). Lo que leía la Maildir por ssh
(pendientes, conversaciones, leídos) se retiró con el panel que lo mostraba.
"""

from __future__ import annotations

from telar.casilla import extension  # noqa: F401 - vive en casilla: la usan el bus y las casillas
from telar.config import Remoto


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
