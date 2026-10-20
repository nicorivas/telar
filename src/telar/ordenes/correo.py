"""`telar correo enviar` — escribirle a un hilo de otra persona.

    echo "cuerpo" | telar correo enviar usuario+hilo@servidor -s "asunto" [--responde "<id>"]

A un hilo propio (de esta persona, en cualquier máquina) va por el bus, como `telar mensaje`. A otra
persona, por el correo del servidor, que lo entrega su `cartero`: el bus todavía no cruza personas
(docs/propuestas/telar-para-otros.md). Leer la Maildir por ssh se retiró.
"""

from __future__ import annotations

import shlex

from telar.ordenes import _comun

AYUDA = "Escribirle a un hilo de otra persona (por el bus, si es propio)."


_DIRECCION = r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+"


def enviar(ctx, direccion: str, asunto: str, cuerpo: str, *, responde: str = "", remoto: str = "") -> tuple[str, str]:
    """Manda un correo entre agentes. Devuelve (por dónde salió, error o "").

    Desde una máquina con cartero, con `mail`; desde otra, por ssh a la máquina de la
    dirección (su remitente queda verificado como el usuario de ssh). Lo que va en las
    cabeceras no puede traer saltos de línea: con uno se inyectan cabeceras nuevas.
    """
    import re
    import subprocess

    from telar.ordenes.agente import _cartero_aqui

    if not re.fullmatch(_DIRECCION, direccion):
        return "", f"«{direccion}» no es una dirección usuario[+hilo]@servidor"
    if not asunto.strip() or any(c in asunto for c in "\r\n"):
        return "", "el asunto va en una sola línea, y no vacío"
    if responde and not re.fullmatch(r"<[^<>\s]+>", responde.strip()):
        return "", f"«{responde}» no es un Message-Id (<algo@servidor>)"
    from telar import bus as mod_bus

    usuario, _, ext = direccion.rsplit("@", 1)[0].partition("+")
    if ext and mod_bus.hay_bus(ctx.config) and usuario == mod_bus.persona(ctx.config):
        # entre hilos de una misma persona, el correo es un mensaje del bus: sin Postfix ni cartero
        from telar.ordenes import mensaje

        try:
            m = mensaje.enviar(ctx, ext, f"Asunto: {asunto.strip()}\n\n{cuerpo.strip()}")
        except mod_bus.ErrorDeBus as e:
            return "", str(e)
        if m.get("estado") == "retenido":
            return "", f"retenido, no se entregó ({m['motivo']}); tu persona lo suelta con: telar mensaje --soltar {m['id']}"
        return f"el bus (id {m['id']})", ""
    # sin charset declarado, quien lo lee asume us-ascii y cada tilde llega como «��»
    orden = ["mail", "-s", asunto.strip(), "-a", "MIME-Version: 1.0",
             "-a", "Content-Type: text/plain; charset=UTF-8", "-a", "Content-Transfer-Encoding: 8bit"]
    if responde:
        orden += ["-a", f"In-Reply-To: {responde.strip()}", "-a", f"References: {responde.strip()}"]
    orden.append(direccion)
    servidor = direccion.rsplit("@", 1)[1].split(".")[0]
    elegido = next((r for r in ctx.config.remotos if r.nombre == remoto), None) if remoto else next(
        (r for r in ctx.config.remotos if r.destino.rpartition("@")[2].split(".")[0] == servidor), None)
    if remoto and elegido is None:
        return "", f"no hay remoto «{remoto}»"
    if elegido is None and not _cartero_aqui():
        return "", f"no sé cómo llegar a {servidor}: ninguna máquina de [remotos] se llama así"
    comando = orden if elegido is None else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                                              elegido.destino, shlex.join(orden)]
    try:
        r = subprocess.run(comando, input=cuerpo, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", str(e)
    via = "aquí" if elegido is None else elegido.destino
    return via, "" if r.returncode == 0 else (r.stderr.strip() or f"mail salió con {r.returncode}")[-300:]


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("correo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=("enviar",), help="enviar: escribirle a un hilo de otra persona")
    p.add_argument("direccion", nargs="?", default="", help="usuario+hilo@servidor")
    p.add_argument("-s", "--asunto", default="", help="el asunto")
    p.add_argument("--responde", default="", help="el Message-Id al que se responde")
    p.add_argument("--remoto", default="", help="por esa máquina de [remotos]")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    import sys

    if not o.direccion:
        return _comun.queja("¿a quién? telar correo enviar usuario+hilo@servidor -s \"asunto\" (el cuerpo por stdin)")
    cuerpo = "" if sys.stdin.isatty() else sys.stdin.read()
    via, problema = enviar(ctx, o.direccion, o.asunto, cuerpo, responde=o.responde, remoto=o.remoto)
    if problema:
        return _comun.queja(f"no se envió: {problema}")
    if o.json:
        return _comun.escribir_json({"enviado": True, "a": o.direccion, "via": via})
    print(f"enviado a {o.direccion} (por {via})")
    return 0
