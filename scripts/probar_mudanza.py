"""Probar la mudanza de un hilo entre dos máquinas de verdad, sin tocar ningún hilo de la persona.

En cada máquina se arma un telar aparte en una carpeta propia (`--carpeta`, corta: tmux pone ahí su socket): su
configuración, su estado, su tmux, su carpeta de Claude (`CLAUDE_CONFIG_DIR`) y un `claude` de mentira que se queda
quieto. Las dos usan el bus de la persona con su cuenta, pero con nombres de máquina propios (`e1-laptop`,
`e1-servidor`): nadie más atiende esos pedidos. El registro de los hilos y las fotos de las dos máquinas van a almacenes
aparte (`TELAR_BUS_HILOS`, `TELAR_BUS_ESPEJO`): nada de la prueba se mezcla con lo de la persona. En lugar del nodo
entero (que también recoge correo, publica su directorio y abre agentes), `atender` corre el nodo de verdad a medias:
sus vueltas, su vigía, su foto y los pedidos de la mudanza.
Corre el código de la carpeta de donde se llama (PYTHONPATH=src), así que prueba una rama sin desplegarla.

    python3 scripts/probar_mudanza.py preparar --carpeta /tmp/e1 --maquina e1-laptop --otra e1-servidor
    source /tmp/e1/entorno.sh                 # desde aquí, todo en el telar aparte
    $PY scripts/probar_mudanza.py atender &   # contesta lo de la mudanza mientras dure la prueba
    $PY scripts/probar_mudanza.py hilo juguete
    $PY scripts/probar_mudanza.py conversacion --sid <id> --mb 45 --carpeta-mb 8
    $PY -m telar hilo llevar e1-servidor --hilo juguete --sesion <id> --si
    $PY scripts/probar_mudanza.py medir juguete      # lo que viajó, del progreso de la mudanza
    $PY scripts/probar_mudanza.py sumas --sid <id>   # el sha256 de cada archivo, para comparar las dos máquinas
    $PY scripts/probar_mudanza.py trabajar juguete --sid <id> --segundos 15   # un turno a medias
    $PY scripts/probar_mudanza.py transporte --mb 100 --delta 1   # solo la copia (telar.replica), medida, a la otra
    $PY scripts/probar_mudanza.py escribio --sid <id> raiz/repo/a.txt   # que su conversación escribió ese archivo
    $PY scripts/probar_mudanza.py registro juguete --padre Papá --etiquetas e2,prueba --prioridad 1   # (sin más: verlo)
    $PY scripts/probar_mudanza.py mensaje juguete "revisa esto"     # uno que espera en su casilla local
    $PY scripts/probar_mudanza.py rama Hijo --padre juguete           # un hijo con rama (su worktree, de mentira)
    $PY scripts/probar_mudanza.py registro-bus juguete   # su dueño y su época, en el almacén de la prueba
    $PY scripts/probar_mudanza.py vivos                  # qué corre cada ventana: claude (vivo) o espera
    $PY scripts/probar_mudanza.py borrar-almacen         # al terminar: los almacenes de la prueba (registro y fotos)
    $PY scripts/probar_mudanza.py limpiar            # mata su tmux; la carpeta se borra a mano

Para «seguir aquí» con la dueña apagada (la etapa 4): se mata su `atender` (y se detiene a su agente con SIGSTOP, como
la tapa del laptop cerrada); a los dos minutos su foto deja de estar vigente en la otra, que entonces lo puede seguir
(`$PY -m telar hilo seguir juguete --si`). Al volver (SIGCONT y `atender` de nuevo), cede sola.

docs/propuestas/mudanza-de-hilos.md, etapas 1 a 4.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import hashlib
import json
import os
import random
import shlex
import subprocess
import sys
import time
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[1]


def preparar(o) -> None:
    d = Path(o.carpeta).resolve()
    for sub in ("home", "config/telar", "state/telar", "data", "cache", "tmux", "claude", "bin", "raiz"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    (d / "tmux").chmod(0o700)
    real = Path(os.path.expanduser("~/.config/telar/config.toml"))
    bus = {}
    if real.exists():
        import tomllib

        bus = tomllib.loads(real.read_text()).get("bus", {})
    token = os.path.expanduser(o.token or bus.get("token", "~/.config/telar/bus.token"))
    url = o.bus or bus.get("url", "")
    (d / "config/telar/config.toml").write_text(f'''# telar aparte para probar la mudanza (scripts/probar_mudanza.py): se borra al terminar
multiplexor = "tmux"
sesion = "e1"
raiz = "{d / 'raiz'}"
estado = "{d / 'state/telar'}"

[agente]
nombre = "claude-code"
carpeta = "raiz"

[hilos]
dormir_tras = 0

[bus]
url = "{url}"
token = "{token}"
persona = "{bus.get('persona') or os.environ.get('USER', '')}"
maquina = "{o.maquina}"
entrada = "{d / 'entrada'}"
''')
    falso = d / "bin/claude"
    falso.write_text('#!/bin/sh\n# claude de mentira (scripts/probar_mudanza.py): se queda quieto\n'
                     'if [ "$1" = "--version" ]; then echo "2.0.0 (Claude Code)"; exit 0; fi\nexec sleep 86400\n')
    falso.chmod(0o755)
    py = o.python or sys.executable
    (d / "entorno.sh").write_text(f'''# el telar aparte de la prueba de la mudanza
export HOME={d}/home XDG_CONFIG_HOME={d}/config XDG_STATE_HOME={d}/state XDG_DATA_HOME={d}/data XDG_CACHE_HOME={d}/cache
export TMUX_TMPDIR={d}/tmux CLAUDE_CONFIG_DIR={d}/claude TELAR_CONFIG={d}/config/telar/config.toml
export TELAR_CLAUDE={d}/bin/claude PATH={d}/bin:$PATH PYTHONPATH={RAIZ_REPO / 'src'}
export E1_CARPETA={d} E1_OTRA={o.otra} PY={py} TELAR_BUS_HILOS=TELAR_HILOS_PRUEBA TELAR_BUS_ESPEJO=TELAR_ESPEJO_PRUEBA
unset TMUX TMUX_PANE TELAR_HILO TELAR_PANEL TELAR_LLEVAR_APARTE
cd {RAIZ_REPO}
''')
    print(d / "entorno.sh")


def _config():
    from telar import config as mod_config

    return mod_config.cargar()


def atender(o) -> None:
    """El nodo de la máquina de la prueba, a medias: el de verdad (telar.ordenes.nodo.Nodo), con sus vueltas (publicar
    sus hilos en el registro del bus, condicionado; las mudanzas a medias), su vigía del registro y los pedidos de la
    mudanza, y su foto. Sin lo que tocaría lo de la persona: no recoge casillas, no publica su directorio, no avisa a
    padres, no atiende correo ni otros pedidos. El registro y las fotos van a almacenes aparte (`TELAR_BUS_HILOS`,
    `TELAR_BUS_ESPEJO`, los pone `preparar`). Con `E1_PARAR=tomado` (o `abierto`), el proceso se muere de un golpe justo después de tomar un hilo que
    llega (o de abrirlo), una vez: para ver qué pasa si el nodo de allá se cae en ese paso."""

    import telar
    from telar import bus as mod_bus
    from telar import mudanza
    from telar.ordenes import nodo as mod_nodo

    from telar.cli import Contexto

    config = _config()
    ctx = Contexto(config=config)  # el de las órdenes: la foto lee el perfil
    if mod_bus.ESTADO == "TELAR_HILOS" or mod_bus.ESPEJO == "TELAR_ESPEJO":
        sys.exit("sin TELAR_BUS_HILOS y TELAR_BUS_ESPEJO: la prueba escribiría en lo de la persona (source entorno.sh)")
    print(f"atiendo {mod_bus.maquina(config)} con el telar de {Path(telar.__file__).parent}, registro en {mod_bus.ESTADO}",
          flush=True)
    parar = os.environ.get("E1_PARAR", "")
    if parar:
        abrir = mudanza._abrir
        marca = Path(config.estado) / f"parado-{parar}"

        def _abrir(*a, **k):
            if parar == "tomado" and not marca.exists():
                marca.write_text("1")
                print(f"{time.strftime('%H:%M:%S')} tomado: me muero antes de abrirlo", flush=True)
                os.kill(os.getpid(), 9)
            r = abrir(*a, **k)
            if parar == "abierto" and not marca.exists():
                marca.write_text("1")
                print(f"{time.strftime('%H:%M:%S')} abierto: me muero antes de contestar", flush=True)
                os.kill(os.getpid(), 9)
            return r

        mudanza._abrir = _abrir

    class Js:
        """Las casillas no se recogen: nada de suscripciones durables en el stream de la persona."""

        async def pull_subscribe(self, *a, **k):
            return None

    async def nada(*a, **k):
        return None

    async def correr():
        nodo = mod_nodo.Nodo(ctx)
        nodo._recoger = nada
        nodo.avisar_padres = lambda locales: []
        # su foto la publica la vuelta de abajo, en el almacén de la prueba: la del nodo va además al directorio
        foto_de_verdad, nodo.foto = nodo.foto, lambda: None
        nc = await mod_bus.conectar(config)
        mod_bus.registrar_conexion(nc, asyncio.get_running_loop())
        js = nc.jetstream(timeout=10)
        almacenes = []
        for nombre in (mod_bus.ESTADO, mod_bus.ESPEJO):
            try:
                almacenes.append(await js.key_value(nombre))
            except Exception:  # noqa: BLE001 - la primera vez
                almacenes.append(await js.create_key_value(bucket=nombre, history=1))
        kv, nodo.espejo = almacenes
        nodo.kv, nodo.js, nodo.nc = kv, js, nc
        await nodo.sembrar(kv)
        # y `hilo` (los verbos que se le piden al dueño, y retomar): corren `telar hilo` en el telar aparte de la prueba
        for verbo, cb in (("hilo", nodo._hilo), ("hilo-revisar", nodo._hilo_revisar), ("hilo-llegar", nodo._hilo_llegar),
                          ("hilo-traer", nodo._hilo_traer), ("mudanza-progreso", nodo._mudanza_progreso),
                          ("replica-estado", nodo._replica_estado), ("replica-escribir", nodo._replica_escribir),
                          ("replica-cerrar", nodo._replica_cerrar)):
            await nodo._suscribir(nc, mod_bus.tema_rpc(config, nodo.yo, verbo), cb,
                                  en_fila=verbo not in mod_nodo.SOLO_LEEN)
        vigia = nodo.vigia = asyncio.create_task(nodo._vigilar(kv))
        vigia_espejo = asyncio.create_task(nodo._vigilar_espejo())
        try:
            while True:
                await nodo._vuelta(Js(), kv)
                if nodo.vueltas % mod_nodo.ESPEJO_CADA == 1:
                    f = await asyncio.to_thread(foto_de_verdad)
                    if f is not None:
                        await nodo.espejo.put(f"{nodo.persona}.{nodo.yo}", json.dumps(f, ensure_ascii=False).encode())
                await asyncio.sleep(mod_nodo.VUELTA)
        finally:
            vigia.cancel()
            vigia_espejo.cancel()
            await nc.close()

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(correr())


def registro_bus(o) -> None:
    """El registro de un hilo en el almacén de la prueba: su dueño, su época y el traspaso en curso."""
    from telar import dueno

    print(json.dumps(dueno.registro(_config(), o.nombre), ensure_ascii=False))


def vivos(o) -> None:
    """Las ventanas de la sesión de la prueba y qué corre cada una, por sus procesos: `claude` (el de mentira, `sleep
    86400`: su agente vivo), `espera` (el panel que espera: detenido para irse, o dormido) u otra cosa."""
    from telar import dormir

    config = _config()
    r = subprocess.run(["tmux", "list-panes", "-s", "-t", config.sesion, "-F", "#{window_name}\t#{pane_pid}"],
                       capture_output=True, text=True)
    tabla = dormir.procesos()

    def descendientes(pid):
        hijos = [p for p in tabla.values() if p.ppid == pid]
        return hijos + [d for h in hijos for d in descendientes(h.pid)]

    salida = {}
    for linea in r.stdout.splitlines():
        nombre, _, pid = linea.partition("\t")
        procs = [tabla[int(pid)]] if pid.isdigit() and int(pid) in tabla else []
        procs += descendientes(int(pid)) if pid.isdigit() else []
        args = [" ".join(p.args) for p in procs]
        salida[nombre] = ("claude" if any("sleep 86400" in a for a in args)
                          else "espera" if any(dormir.MARCA in a for a in args) else (procs[0].nombre if procs else "?"))
    print(json.dumps(salida, ensure_ascii=False))


def borrar_almacen(o) -> None:
    """Borra los almacenes de la prueba (`TELAR_BUS_HILOS`, `TELAR_BUS_ESPEJO`): nunca los de la persona."""
    from telar import bus as mod_bus

    if mod_bus.ESTADO == "TELAR_HILOS" or mod_bus.ESPEJO == "TELAR_ESPEJO":
        sys.exit("sin TELAR_BUS_HILOS y TELAR_BUS_ESPEJO: esos son los de la persona")

    async def borrar():
        nc = await mod_bus.conectar(_config())
        try:
            for nombre in (mod_bus.ESTADO, mod_bus.ESPEJO):
                with contextlib.suppress(Exception):
                    await nc.jetstream().delete_key_value(nombre)
                    print(f"borrado {nombre}")
        finally:
            await nc.close()

    asyncio.run(borrar())


def _proyecto():
    from telar import rutas

    config = _config()
    return rutas.proyecto(Path(config.raiz))


def hilo(o) -> None:
    """La sesión de tmux del telar aparte y una ventana `nombre` con el claude de mentira."""
    config = _config()
    vivo = subprocess.run(["tmux", "has-session", "-t", config.sesion], capture_output=True).returncode == 0
    if not vivo:
        subprocess.run([sys.executable, "-m", "telar", "tejer", "--vacia"], check=False, stdin=subprocess.DEVNULL)
    subprocess.run(["tmux", "new-window", "-d", "-t", f"{config.sesion}:", "-n", o.nombre,
                    os.environ.get("TELAR_CLAUDE", "sleep 86400")], check=True)
    print(subprocess.run(["tmux", "list-windows", "-t", config.sesion, "-F", "#{window_id} #{window_name}"],
                         capture_output=True, text=True).stdout.strip())


def _linea(rnd: random.Random, tipo: str | None = None, imagen: bool | None = None) -> bytes:
    palabras = "la conversación viaja los archivos no el agente lee escribe una herramienta resultado".split()
    if imagen if imagen is not None else rnd.random() < 0.15:
        d = {"type": "user", "message": {"content": [{"type": "image", "source": {
            "data": base64.b64encode(rnd.randbytes(rnd.randint(40_000, 120_000))).decode()}}]}}
    else:
        d = {"type": tipo or rnd.choice(["assistant", "user"]),
             "text": " ".join(rnd.choice(palabras) for _ in range(rnd.randint(50, 900)))}
    return (json.dumps(d, ensure_ascii=False) + "\n").encode()


def _crecer(ruta: Path, mb: float, semilla: int) -> int:
    rnd = random.Random(semilla)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(ruta, "ab") as f:
        while n < mb * 1e6:
            b = _linea(rnd)
            f.write(b)
            n += len(b)
    return n


def conversacion(o) -> None:
    """Una conversación falsa (líneas JSON, un 15% con una imagen que no comprime) y su carpeta `<sid>/`: resultados
    guardados y subagentes. Con `--agregar`, la hace crecer (lo que haría el agente en un rato), con un resultado y un
    subagente que crece. Con `--cierre`, lo que Claude anota al cerrarse; con `--diverge`, un mensaje que la otra no
    tiene."""
    proy = _proyecto()
    archivo = proy / f"{o.sid}.jsonl"
    semilla = int(time.time())
    if o.cierre:
        with open(archivo, "ab") as f:
            f.write(b'{"type":"last-prompt","lastPrompt":"x"}\n{"type":"cost-state","cost":1}\n')
    if o.diverge:
        with open(archivo, "ab") as f:
            f.write(b'{"type":"assistant","text":"esto se escribio solo en esta maquina"}\n')
    if o.mb:
        _crecer(archivo, o.mb, semilla)
    if o.carpeta_mb:
        carpeta = proy / o.sid
        rnd = random.Random(semilla)
        for i in range(12):
            (carpeta / "tool-results").mkdir(parents=True, exist_ok=True)
            (carpeta / "tool-results" / f"toolu_{semilla}_{i:02d}.txt").write_bytes(
                b"una salida larga de una herramienta\n" * rnd.randint(200, 3000))
        for i in range(3):
            _crecer(carpeta / "subagents" / f"agent-{i}.jsonl", o.carpeta_mb / 3, semilla + i)
    if o.agregar:
        _crecer(archivo, o.agregar, semilla)
        carpeta = proy / o.sid
        (carpeta / "tool-results").mkdir(parents=True, exist_ok=True)
        (carpeta / "tool-results" / f"toolu_nuevo_{semilla}.txt").write_bytes(b"lo nuevo\n" * 1000)
        subs = sorted((carpeta / "subagents").glob("*.jsonl"))
        if subs:
            _crecer(subs[0], 0.2, semilla + 99)
    _sumas(o.sid)


def _sumas(sid: str) -> dict:
    proy = _proyecto()
    salida = {}
    for p in sorted([proy / f"{sid}.jsonl", *(proy / sid).rglob("*")] if (proy / sid).is_dir() else [proy / f"{sid}.jsonl"]):
        if p.is_file():
            salida[p.relative_to(proy).as_posix()] = (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:16])
    total = sum(n for n, _ in salida.values())
    print(f"{proy}: {len(salida)} archivos, {total / 1e6:.2f} MB, la conversación "
          f"{salida.get(f'{sid}.jsonl', (0,))[0] / 1e6:.2f} MB")
    print("aparte:", [p.name for p in proy.glob(f"{sid}*.bak")])
    return salida


def sumas(o) -> None:
    s = _sumas(o.sid)
    if o.json:
        print(json.dumps(s))


def trabajar(o) -> None:
    """Un turno a medias: la atención del hilo en «trabajando» y la conversación creciendo una línea por segundo
    durante `segundos`; después, «terminó»."""
    from telar import estado as mod_estado
    from telar.modelo import Atencion

    config = _config()
    est = mod_estado.abrir(config)
    archivo = _proyecto() / f"{o.sid}.jsonl"
    rnd = random.Random(7)
    est.anotar_atencion(o.nombre, Atencion.TRABAJANDO)
    print(f"{time.strftime('%H:%M:%S')} trabajando", flush=True)
    fin = time.monotonic() + o.segundos
    while time.monotonic() < fin:
        with open(archivo, "ab") as f:
            f.write(_linea(rnd, "assistant", imagen=False))
        time.sleep(1)
    est.anotar_atencion(o.nombre, Atencion.TERMINO)
    print(f"{time.strftime('%H:%M:%S')} terminó su turno", flush=True)


def medir(o) -> None:
    from telar import mudanza

    p = mudanza.progreso_de(_config(), o.nombre)
    print(json.dumps(p, ensure_ascii=False))


def transporte(o) -> None:
    """Solo la copia, sin hilo: una conversación falsa de `--mb` con su carpeta a la otra máquina de la prueba
    (telar.replica.mandar), la primera vez entera y después con `--delta` MB más; cuánto tarda cada una."""
    import uuid

    from telar import replica

    config = _config()
    otra = os.environ["E1_OTRA"]
    sid = str(uuid.uuid4())
    archivo = Path(config.estado) / "medir" / f"{sid}.jsonl"
    _crecer(archivo, o.mb, 1)
    for i in range(3):
        _crecer(archivo.parent / sid / "subagents" / f"agent-{i}.jsonl", o.mb / 20, 10 + i)

    def una(nombre: str) -> None:
        t = time.monotonic()
        r = replica.mandar(config, otra, sid, archivo, {"carpeta": "~/medir"})
        s = time.monotonic() - t
        print(f"{nombre:8} {s:6.2f} s  {r['mandados'] / 1e6:7.1f} MB de {r['bytes'] / 1e6:.1f} MB, "
              f"{r['red'] / 1e6:.1f} MB por la red, {r['mandados'] / 1e6 / max(s, 0.01):.1f} MB/s", flush=True)

    una("entera")
    _crecer(archivo, o.delta, 2)
    una("delta")
    una("igual")


def escribio(o) -> None:
    """Que la conversación del hilo escribió esos archivos (una línea de Edit de Claude Code por cada uno): lo que
    telar.sin_subir reconoce como suyo."""
    archivo = _proyecto() / f"{o.sid}.jsonl"
    with open(archivo, "ab") as f:
        for r in o.rutas:
            ruta = str(Path(r).resolve())
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"toolu_{time.time_ns()}", "name": "Edit",
                 "input": {"file_path": ruta, "old_string": "a", "new_string": "b"}}]}}).encode() + b"\n")
    print(f"{archivo.name}: escribió {', '.join(o.rutas)}")


def registro(o) -> None:
    """El registro del hilo (padre, etiquetas, prioridad, esfuerzo, público): ponerlo, y verlo."""
    from telar import estado as mod_estado
    from telar import mudanza

    est = mod_estado.abrir(_config())
    if o.padre is not None or o.etiquetas is not None or o.prioridad is not None:
        mudanza.aplicar_registro(est, o.nombre, {
            **({"padre": o.padre} if o.padre is not None else {}),
            **({"etiquetas": [x for x in o.etiquetas.split(",") if x]} if o.etiquetas is not None else {}),
            **({"prioridad": o.prioridad} if o.prioridad is not None else {})})
    print(json.dumps(mudanza.registro_de(est, o.nombre), ensure_ascii=False))


def mensaje(o) -> None:
    """Un mensaje que espera en la casilla local del hilo (como los que deja el nodo); sin texto, los que esperan."""
    from telar import bus as mod_bus
    from telar import casilla

    config = _config()
    if o.texto:
        casilla.dejar(config, o.nombre, mod_bus.mensaje(o.texto, de="prueba", para=o.nombre))
    print(json.dumps([m.get("texto") for m in casilla.pendientes(config, o.nombre)], ensure_ascii=False))


def rama(o) -> None:
    """Un hijo con rama de mentira: su ventana, anotado con su worktree y colgado de su padre."""
    from telar import estado as mod_estado

    config = _config()
    subprocess.run(["tmux", "new-window", "-d", "-t", f"{config.sesion}:", "-n", o.nombre, "sleep 86400"], check=True)
    est = mod_estado.abrir(config)
    est.anotar_rama(o.nombre, {"ruta": str(Path.home() / "worktrees" / f"juguete-{o.nombre.lower()}"),
                               "rama": o.nombre.lower(), "base": "main"})
    if o.padre:
        est.colgar(o.nombre, o.padre)
    print(json.dumps(est.ramas().get(o.nombre), ensure_ascii=False))


def limpiar(o) -> None:
    config = _config()
    subprocess.run(["tmux", "kill-session", "-t", config.sesion], capture_output=True)
    d = os.environ.get("TMUX_TMPDIR", "")
    if d:
        for sock in Path(d).glob("tmux-*/default"):
            subprocess.run(["tmux", "-S", str(sock), "kill-server"], capture_output=True)
    print("tmux de la prueba, cerrado; la carpeta:", os.environ.get("E1_CARPETA", "?"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="orden", required=True)
    a = s.add_parser("preparar")
    a.add_argument("--carpeta", required=True)
    a.add_argument("--maquina", required=True)
    a.add_argument("--otra", required=True)
    a.add_argument("--bus", default="")
    a.add_argument("--token", default="")
    a.add_argument("--python", default="")
    s.add_parser("atender")
    a = s.add_parser("hilo")
    a.add_argument("nombre")
    a = s.add_parser("conversacion")
    a.add_argument("--sid", required=True)
    a.add_argument("--mb", type=float, default=0)
    a.add_argument("--carpeta-mb", type=float, default=0)
    a.add_argument("--agregar", type=float, default=0)
    a.add_argument("--cierre", action="store_true")
    a.add_argument("--diverge", action="store_true")
    a = s.add_parser("sumas")
    a.add_argument("--sid", required=True)
    a.add_argument("--json", action="store_true")
    a = s.add_parser("trabajar")
    a.add_argument("nombre")
    a.add_argument("--sid", required=True)
    a.add_argument("--segundos", type=float, default=15)
    a = s.add_parser("medir")
    a.add_argument("nombre")
    a = s.add_parser("transporte")
    a.add_argument("--mb", type=float, default=100)
    a.add_argument("--delta", type=float, default=1)
    a = s.add_parser("registro-bus")
    a.add_argument("nombre")
    s.add_parser("vivos")
    s.add_parser("borrar-almacen")
    a = s.add_parser("escribio")
    a.add_argument("--sid", required=True)
    a.add_argument("rutas", nargs="+")
    a = s.add_parser("registro")
    a.add_argument("nombre")
    a.add_argument("--padre")
    a.add_argument("--etiquetas")
    a.add_argument("--prioridad", type=int)
    a = s.add_parser("mensaje")
    a.add_argument("nombre")
    a.add_argument("texto", nargs="?", default="")
    a = s.add_parser("rama")
    a.add_argument("nombre")
    a.add_argument("--padre", default="")
    s.add_parser("limpiar")
    o = p.parse_args()
    {"preparar": preparar, "atender": atender, "hilo": hilo, "conversacion": conversacion, "sumas": sumas,
     "trabajar": trabajar, "medir": medir, "transporte": transporte, "escribio": escribio, "registro": registro,
     "mensaje": mensaje, "rama": rama, "registro-bus": registro_bus, "vivos": vivos, "borrar-almacen": borrar_almacen,
     "limpiar": limpiar}[o.orden](o)


if __name__ == "__main__":
    main()
