"""`telar espejo` — los hilos de otra máquina, vistos desde esta (ver `telar.espejo`).

    telar espejo publicar            (en el laptop) empuja una foto de sus hilos al servidor
    telar espejo publicar --cada 30  lo repite cada 30 s hasta Ctrl-C (para un terminal o launchd)
    telar espejo recibir --de laptop (en el servidor) guarda la foto que llega por la entrada estándar
    telar espejo ver                 qué fotos hay, de quién y cuánto hace que llegaron

`publicar` entra por ssh a una máquina de `[remotos]` (`--a`, o la única que haya) y corre allá
`telar espejo recibir`. El nombre con que el laptop se presenta sale de su hostname; `--nombre`
lo cambia. Solo viajan los hilos, con su semáforo y su carpeta: ninguna conversación.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from datetime import datetime

from telar import __version__
from telar import espejo as mod
from telar.ordenes import _comun

AYUDA = "Los hilos de otra máquina, vistos desde esta: publicar los propios, recibir, ver."
ESPERA = 25


def publicar_una_vez(ctx, remoto, nombre: str) -> str:
    """Empuja una foto ahora. "" si salió bien; si no, por qué no (sin levantar excepción)."""
    try:
        tel = _comun.tejer(ctx)
        crudo = json.dumps(mod.foto(tel, maquina=nombre, version_telar=__version__), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 - un perfil roto no debe tumbar un ciclo que se repite
        return f"no pude armar la foto: {e}"
    # ssh junta sus argumentos en una línea para la shell remota; el PATH no trae ~/.local/bin
    guion = f'PATH="$HOME/.local/bin:$PATH" telar espejo recibir --de {shlex.quote(nombre)}'
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino, guion],
                           input=crudo, capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{remoto.destino} no responde: {e}"
    return "" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip() or f"ssh salió con {r.returncode}")[-300:]


def _elegir_remoto(ctx, nombre: str):
    remotos = list(ctx.config.remotos)
    if nombre:
        return next((r for r in remotos if r.nombre == nombre), None), f"no hay una máquina «{nombre}» en [remotos]"
    if len(remotos) == 1:
        return remotos[0], ""
    if not remotos:
        return None, "no hay ninguna máquina en [remotos]: ¿a dónde publico?"
    return None, "hay varias máquinas en [remotos]; elige con --a (" + ", ".join(r.nombre for r in remotos) + ")"


def _edad(seg: float | None) -> str:
    if seg is None:
        return "—"
    if seg < 90:
        return f"{int(seg)} s"
    if seg < 5400:
        return f"{round(seg / 60)} min"
    return f"{round(seg / 3600)} h" if seg < 172800 else f"{round(seg / 86400)} d"


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("espejo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=("publicar", "recibir", "ver"))
    p.add_argument("--a", default="", metavar="REMOTO", help="publicar: la máquina de [remotos] (por defecto, la única)")
    p.add_argument("--nombre", default="", help="publicar: cómo se llama esta máquina allá (por defecto, su hostname)")
    p.add_argument("--cada", type=float, default=0, metavar="SEG", help="publicar: repetir cada tantos segundos")
    p.add_argument("--de", default="", metavar="NOMBRE", help="recibir: de qué máquina viene la foto")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    if o.verbo == "recibir":
        if not o.de:
            return _comun.queja("recibir necesita --de NOMBRE")
        try:
            limpia = mod.guardar(ctx.config, o.de, sys.stdin.read(mod.MAXIMO + 1))
        except mod.ErrorDeEspejo as e:
            return _comun.queja(str(e))
        return _comun.escribir_json({"ok": True, "maquina": o.de, "hilos": len(limpia["hilos"])}) if o.json else (
            print(f"{o.de}: {len(limpia['hilos'])} hilos") or 0)

    if o.verbo == "ver":
        fotos = mod.leer_todos(ctx.config)
        if o.json:
            return _comun.escribir_json({"espejos": fotos, "vigente": mod.VIGENTE})
        if not fotos:
            print(_comun.tenue("ninguna máquina ha publicado aquí todavía"))
        for f in fotos:
            estado = f.get("error") or f"{'en línea' if f['en_linea'] else 'apagado'} · hace {_edad(f['edad'])} · {len(f['hilos'])} hilos"
            print(f"{f['nombre']:<16} {estado}")
        return 0

    # publicar
    remoto, problema = _elegir_remoto(ctx, o.a)
    if remoto is None:
        return _comun.queja(problema)
    nombre = mod.nombre_valido(o.nombre) if o.nombre else mod.nombre_de_esta_maquina()
    if not nombre:
        return _comun.queja("ese nombre no sirve para una máquina (a-z, 0-9, - y _)")
    if o.cada <= 0:
        error = publicar_una_vez(ctx, remoto, nombre)
        if o.json:
            return _comun.escribir_json({"publicado": not error, "maquina": nombre, "remoto": remoto.nombre, "error": error})
        print(f"{nombre} → {remoto.nombre}: {error or 'publicado'}")
        return 1 if error else 0
    # en bucle: solo se habla cuando cambia el estado (bien → mal, mal → bien), no en cada vuelta
    previo = None
    try:
        while True:
            error = publicar_una_vez(ctx, remoto, nombre)
            if error != previo:
                print(f"{datetime.now():%H:%M:%S} {nombre} → {remoto.nombre}: {error or 'publicando'}", flush=True)
                previo = error
            time.sleep(max(o.cada, 5))
    except KeyboardInterrupt:
        print()
        return 0
