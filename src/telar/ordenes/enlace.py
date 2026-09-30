"""`telar enlace` — la puerta entre dos máquinas: pedirle cosas al laptop desde el servidor.

    Desde el servidor (quien llama):
      telar enlace ping                         ¿está el laptop? quién es y qué verbos hace
      telar enlace hilos                        la foto de sus hilos, ahora
      telar enlace archivo foto.png             manda un archivo a su carpeta de entrada
      telar enlace enviar "Faro" "hola" --enter escribe en un hilo suyo (y lo manda)
      telar enlace notificar "terminó" --titulo telar
      telar enlace instalar                     crea la llave y dice cómo autorizarla en el laptop

    En el laptop (quien recibe):
      telar enlace autorizar "ssh-ed25519 AAAA…"   ata esa llave al único comando `telar enlace servir`
      telar enlace revocar                         quita toda llave atada a la puerta
      telar enlace servir                          lo que sshd ejecuta; no se corre a mano

La seguridad no está en este programa sino en `authorized_keys`: la llave del servidor solo puede
ejecutar `telar enlace servir`, sin shell ni túneles (`restrict`), y `servir` solo cumple cinco
verbos con topes. Ver `telar.enlace` y docs/configuracion.md, `[enlaces]` y `[enlace]`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from telar import enlace as mod
from telar.config import VERBOS_ENLACE
from telar.ordenes import _comun

AYUDA = "La puerta entre dos máquinas: pedirle cosas al laptop desde el servidor."

LLAMADAS = ("ping", "hilos", "archivo", "enviar", "notificar")
LOCALES = ("instalar", "autorizar", "revocar", "servir")


def _elegir(ctx, nombre: str):
    enlaces = list(ctx.config.enlaces)
    if nombre:
        return next((e for e in enlaces if e.nombre == nombre), None), f"no hay un enlace «{nombre}» en [enlaces]"
    if len(enlaces) == 1:
        return enlaces[0], ""
    if not enlaces:
        return None, "no hay ningún enlace: agrega [enlaces.laptop] a la configuración (`telar enlace instalar` dice cómo)"
    return None, "hay varios enlaces; elige con --a (" + ", ".join(e.nombre for e in enlaces) + ")"


def _servir(ctx) -> int:
    """Lo que sshd ejecuta. La petición viene en SSH_ORIGINAL_COMMAND y el contenido, por la entrada."""
    os.environ["PATH"] = mod.completar_path()  # sshd trae un PATH sin tmux
    pedido = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    tope = mod.LIMITE.get(mod.verbo_de(pedido), 0)
    entrada = sys.stdin.buffer.read(tope + 1) if tope else b""
    respuesta = mod.servir(ctx, pedido, entrada)
    print(json.dumps(respuesta, ensure_ascii=False))
    return 0 if respuesta.get("ok") else 1


def _instalar(ctx, o) -> int:
    llave = Path(o.llave).expanduser()
    creada = False
    if not llave.exists():
        if not shutil.which("ssh-keygen"):
            return _comun.queja("no encuentro ssh-keygen")
        llave.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        r = subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "telar-enlace", "-f", str(llave)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return _comun.queja(f"ssh-keygen falló: {(r.stderr or r.stdout).strip()[-200:]}")
        creada = True
    publica = Path(str(llave) + ".pub").read_text(encoding="utf-8").strip()
    destino = o.destino or "usuario@nombre-del-laptop"
    if o.json:
        return _comun.escribir_json({"llave": str(llave), "creada": creada, "publica": publica})
    print(f"{'Creé' if creada else 'Ya existía'} la llave {llave}\n")
    print("1. En el laptop (con Sesión remota activada: Ajustes → General → Compartir), corre:\n")
    print(f'     telar enlace autorizar "{publica}"\n')
    print("2. En la configuración de esta máquina (~/.config/telar/config.toml):\n")
    print(f'     [enlaces.laptop]\n     destino = "{destino}"\n     llave = "{o.llave}"\n')
    print("3. Prueba:  telar enlace ping")
    return 0


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("enlace", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=(*LLAMADAS, *LOCALES))
    p.add_argument("args", nargs="*", help="lo que lleve el verbo (un archivo, un hilo y un texto, la llave…)")
    p.add_argument("--a", default="", metavar="ENLACE", help="a qué máquina de [enlaces] llamar (por defecto, la única)")
    p.add_argument("--enter", action="store_true", help="enviar: además de escribir, mandarlo (↩)")
    p.add_argument("--titulo", default="telar", help="notificar: el título del aviso")
    p.add_argument("--llave", default="~/.ssh/telar_enlace", help="instalar: dónde va la llave")
    p.add_argument("--destino", default="", help="instalar: el destino del laptop, para completar el ejemplo")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    if o.verbo == "servir":
        return _servir(ctx)
    if o.verbo == "instalar":
        return _instalar(ctx, o)
    if o.verbo == "autorizar":
        if len(o.args) != 1:
            return _comun.queja('autorizar lleva la llave pública entre comillas: telar enlace autorizar "ssh-ed25519 AAAA…"')
        telar = shutil.which("telar") or ""
        if not telar:
            return _comun.queja("no encuentro `telar` en el PATH: sshd necesita su ruta absoluta")
        try:
            hecho = mod.autorizar(o.args[0], telar, Path.home() / ".ssh" / "authorized_keys")
        except mod.ErrorDePuerta as e:
            return _comun.queja(str(e))
        print(f"llave {hecho} en ~/.ssh/authorized_keys, atada a: {telar} {mod.MARCA}")
        print("Falta que la Sesión remota esté activada (Ajustes → General → Compartir). Para quitarla: telar enlace revocar")
        return 0
    if o.verbo == "revocar":
        n = mod.revocar(Path.home() / ".ssh" / "authorized_keys")
        print(f"{n} llave(s) quitada(s)" if n else "no había ninguna llave atada a la puerta")
        return 0

    # llamar
    enlace, problema = _elegir(ctx, o.a)
    if enlace is None:
        return _comun.queja(problema)
    args: list[str] = []
    entrada: bytes | None = None
    if o.verbo == "archivo":
        if len(o.args) != 1:
            return _comun.queja("archivo lleva la ruta de lo que quieres mandar")
        ruta = Path(o.args[0]).expanduser()
        if not ruta.is_file():
            return _comun.queja(f"{ruta} no es un archivo")
        if ruta.stat().st_size > mod.MAX_ARCHIVO:
            return _comun.queja(f"pesa más de {mod.MAX_ARCHIVO // (1024 * 1024)} MB")
        args, entrada = [ruta.name], ruta.read_bytes()
    elif o.verbo == "enviar":
        if len(o.args) < 2:
            return _comun.queja('enviar lleva el hilo y el texto: telar enlace enviar "Faro" "hola" --enter (o «-» para leerlo de la entrada)')
        texto = sys.stdin.read() if o.args[1:] == ["-"] else " ".join(o.args[1:])
        args, entrada = [o.args[0], *(["enter"] if o.enter else [])], texto.encode("utf-8")
    elif o.verbo == "notificar":
        if not o.args:
            return _comun.queja('notificar lleva el texto: telar enlace notificar "terminó" --titulo telar')
        args, entrada = [o.titulo], " ".join(o.args).encode("utf-8")
    elif o.args:
        return _comun.queja(f"«{o.verbo}» no lleva argumentos")
    r = mod.llamar(enlace, o.verbo, args, entrada)
    if o.json:
        _comun.escribir_json(r)
    elif not r.get("ok"):
        print(f"{enlace.nombre}: {r.get('error', 'no salió')}", file=sys.stderr)
    elif o.verbo == "hilos":
        for h in r["foto"]["hilos"]:
            print(f"{h.get('atencion', ''):<11}{h['nombre']}")
    elif o.verbo == "ping":
        print(f"{r['maquina']} responde · telar {r['telar']} · {r['hora']} · verbos: {', '.join(r['verbos'])}")
    else:
        print(f"{enlace.nombre}: " + ", ".join(f"{k} {v}" for k, v in r.items() if k not in ("ok", "verbo")))
    return 0 if r.get("ok") else 1
