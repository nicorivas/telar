"""Las cuentas del bus: una por persona, y el servidor NATS las hace cumplir.

Cada persona tiene su cuenta en el servidor del bus, con un usuario (su nombre en el bus, `[bus] persona`) y
una clave (el secreto de `[bus] token`, el mismo en todas sus máquinas). Una cuenta de NATS es un espacio
aparte: sus temas, sus streams y sus almacenes no los ve ninguna otra. Así, lo de una persona (sus
casillas, el estado de sus hilos, la foto de sus máquinas, los pedidos a sus nodos) no lo alcanza otra
aunque esté en el mismo bus, y no por convención de nombres sino porque el servidor no se lo deja.

El servidor guarda de cada clave solo su hash (bcrypt), en un archivo por persona:

    ~/.config/telar/bus/personas/<persona>.hash     lo escribe `telar bus persona`
    ~/.config/telar/bus/servidor.conf               la configuración de nats-server, armada de esos hashes

Este módulo es puro salvo `escribir`: arma el texto de la configuración y valida los nombres.
"""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

#: un nombre de persona en el bus: va en los temas y es el nombre de su cuenta
NOMBRE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
#: un hash de bcrypt, como lo acepta nats-server
BCRYPT = re.compile(r"^\$2[abxy]\$\d{2}\$[./A-Za-z0-9]{53}$")


class ErrorDeCuentas(Exception):
    """Un nombre o un archivo que no sirve. El mensaje es para la persona."""


def carpeta() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "telar" / "bus"


def validar(nombre: str) -> str:
    if not NOMBRE.match(nombre):
        raise ErrorDeCuentas(f"«{nombre}» no sirve como persona del bus: minúsculas, números, - y _, empezando por una letra")
    return nombre


def secreto_nuevo() -> str:
    return secrets.token_hex(24)


def hashear(secreto: str) -> str:
    try:
        import bcrypt
    except ImportError as e:
        raise ErrorDeCuentas("falta bcrypt: instala telar con el extra «bus»") from e
    # costo 11: lo que usa `nats server passwd`; se paga una vez por conexión
    return bcrypt.hashpw(secreto.encode(), bcrypt.gensalt(rounds=11)).decode()


def leer(base: Path) -> dict[str, str]:
    """{persona: hash} de la carpeta de personas; un archivo que no es un hash es un error."""
    personas: dict[str, str] = {}
    for f in sorted((base / "personas").glob("*.hash")):
        nombre, valor = f.stem, f.read_text(encoding="utf-8").strip()
        if not NOMBRE.match(nombre) or not BCRYPT.match(valor):
            raise ErrorDeCuentas(f"{f}: no es el hash de una persona del bus")
        personas[nombre] = valor
    return personas


#: lo único que cruza entre cuentas: el correo a una persona (un servicio: pedido y respuesta) y su
#: directorio (un tema: la lista de sus hilos, que publica su nodo)
CORREO = "correo.{}"
DIRECTORIO = "directorio.{}"


def configuracion(personas: dict[str, str]) -> str:
    """La configuración de nats-server: una cuenta por persona, con JetStream y un solo usuario.

    Entre cuentas cruza solo lo que se exporta: `correo.<persona>` (un servicio: otra persona le deja un
    mensaje a un hilo suyo y su nodo responde si lo guardó) y `directorio.<persona>` (sus hilos, para que
    otra persona sepa a quién escribirle). Cada cuenta importa los de todas las demás, y el correo con
    `share`: quien recibe ve de qué cuenta vino, y nadie escribe a nombre de otro.
    La dirección, el puerto y la carpeta de datos van en la línea de órdenes (telar-bus.service)."""
    lineas = [
        "# La escribe `telar bus persona`; no se edita a mano.",
        "# Una cuenta por persona: lo de una (temas, streams, almacenes) no lo ve otra, salvo lo que exporta.",
        "accounts {",
    ]
    for nombre, h in sorted(personas.items()):
        otras = [o for o in sorted(personas) if o != nombre]
        lineas += [
            f"  {nombre}: {{",
            "    jetstream: enabled",
            f'    users: [ {{ user: "{nombre}", password: "{h}" }} ]',
            "    exports: [",
            f'      {{ service: "{CORREO.format(nombre)}" }}',
            f'      {{ stream: "{DIRECTORIO.format(nombre)}" }}',
            "    ]",
        ]
        if otras:
            lineas.append("    imports: [")
            for o in otras:
                lineas += [
                    f'      {{ service: {{ account: "{o}", subject: "{CORREO.format(o)}" }}, share: true }}',
                    f'      {{ stream: {{ account: "{o}", subject: "{DIRECTORIO.format(o)}" }} }}',
                ]
            lineas.append("    ]")
        lineas.append("  }")
    lineas.append("}")
    return "\n".join(lineas) + "\n"


def _escribir_privado(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, ruta)


def escribir(base: Path, personas: dict[str, str]) -> Path:
    """Escribe el hash de cada persona y la configuración del servidor. Devuelve la ruta de la configuración."""
    (base / "personas").mkdir(parents=True, exist_ok=True, mode=0o700)
    base.chmod(0o700)
    for f in (base / "personas").glob("*.hash"):
        if f.stem not in personas:
            f.unlink()
    for nombre, h in personas.items():
        _escribir_privado(base / "personas" / f"{nombre}.hash", h + "\n")
    conf = base / "servidor.conf"
    _escribir_privado(conf, configuracion(personas))
    return conf


def guardar_secreto(ruta: Path, secreto: str) -> None:
    _escribir_privado(ruta, secreto + "\n")
