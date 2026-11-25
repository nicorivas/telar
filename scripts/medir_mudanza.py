"""Medir cuánto tarda en viajar una conversación grande entre dos máquinas de la persona, por cada camino posible.

No toca ningún hilo ni ninguna conversación: genera un archivo de prueba con la forma de una (líneas JSON, un 15% con
una imagen en base64, que es lo que no se comprime) y lo manda a la otra máquina, que lo deja en su carpeta de entrada;
al final lo borra allá. Para comparar caminos en la propuesta docs/propuestas/mudanza-de-hilos.md.

    python3 scripts/medir_mudanza.py --a servidor --ssh ana@servidor [--mb 25] [--delta 1]

Caminos:
  bus-hoy       telar.entrega.archivo: trozos de 700 KB en base64, una conexión al bus por trozo (lo de hoy)
  bus-viva      los mismos trozos por UNA conexión al bus (lo que haría el nodo, que ya tiene la suya)
  ssh           el .gz entero por ssh (lo que hace hoy la mudanza por [remotos])
  ssh-delta     solo lo que creció (--delta MB), comprimido, agregado al final allá
Corre con el Python de telar (el de `uv tool`), desde la raíz del repositorio: PYTHONPATH=src.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import gzip
import json
import os
import random
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


def conversacion_falsa(ruta: Path, tam: int, semilla: int = 1) -> None:
    rnd = random.Random(semilla)
    palabras = "la conversación viaja los archivos no el agente lee escribe una herramienta resultado".split()
    with open(ruta, "w") as f:
        n = 0
        while n < tam:
            if rnd.random() < 0.15:
                d = {"type": "user", "message": {"content": [{"type": "image", "source": {
                    "data": base64.b64encode(rnd.randbytes(rnd.randint(40_000, 120_000))).decode()}}]}}
            else:
                d = {"type": rnd.choice(["assistant", "user"]), "text": " ".join(rnd.choice(palabras) for _ in range(rnd.randint(50, 900)))}
            linea = json.dumps(d, ensure_ascii=False) + "\n"
            f.write(linea)
            n += len(linea.encode())


def reloj(nombre: str, hacer) -> float:
    t = time.monotonic()
    r = hacer()
    s = time.monotonic() - t
    print(f"{nombre:12} {s:7.2f} s   {r}")
    return s


def bus_viva(config, a: str, gz: Path) -> str:
    """Los trozos de entrega.archivo por una sola conexión, uno detrás de otro."""
    from telar import bus as mod_bus
    from telar import entrega

    datos = gz.read_bytes()
    trozos = [datos[i:i + entrega.MAX_ARCHIVO] for i in range(0, len(datos), entrega.MAX_ARCHIVO)]
    carga = {"nombre": "medir-viva-" + gz.name, "id": uuid.uuid4().hex, "total": len(trozos), "bytes": len(datos)}
    tema = mod_bus.tema_rpc(config, a, "archivo")

    async def correr():
        nc = await mod_bus.conectar(config)
        try:
            r = {}
            for n, t in enumerate(trozos):
                cuerpo = json.dumps({**carga, "parte": n, "datos": base64.b64encode(t).decode("ascii")}).encode()
                r = mod_bus.desempacar((await nc.request(tema, cuerpo, timeout=30)).data)
                if not r.get("ok"):
                    return f"falló en el trozo {n}: {r}"
            return f"{len(trozos)} trozos → {r.get('ruta')}"
        finally:
            await nc.close()

    return asyncio.run(correr())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True, help="la otra máquina, como se llama en el bus")
    p.add_argument("--ssh", default="", help="usuario@máquina para los caminos por ssh (sin esto, se saltan)")
    p.add_argument("--mb", type=float, default=25)
    p.add_argument("--delta", type=float, default=1)
    o = p.parse_args()

    from telar import config as mod_config
    from telar import entrega

    config = mod_config.cargar()
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "medir-conversacion.jsonl"
        conversacion_falsa(base, int(o.mb * 1e6))
        gz = Path(d) / "medir-conversacion.jsonl.gz"
        gz.write_bytes(gzip.compress(base.read_bytes(), 6))
        print(f"prueba: {base.stat().st_size / 1e6:.1f} MB, {gz.stat().st_size / 1e6:.1f} MB comprimida")
        dejados = []
        if gz.stat().st_size <= entrega.MAX_TOTAL:
            reloj("bus-hoy", lambda: dejados.append(entrega.archivo(config, gz, a=o.a)["ruta"]) or dejados[-1])
        else:
            print("bus-hoy      no cabe: pasa del tope de entrega.archivo")
        reloj("bus-viva", lambda: bus_viva(config, o.a, gz))
        dejados.append(f"~/telar-entrada/medir-viva-{gz.name}")
        if o.ssh:
            destino = "/tmp/medir-mudanza.jsonl"
            reloj("ssh", lambda: subprocess.run(["ssh", "-o", "BatchMode=yes", o.ssh, f"gunzip > {destino}"],
                                                 stdin=open(gz, "rb"), check=True) and "ok")
            conversacion_falsa(Path(d) / "delta.jsonl", int(o.delta * 1e6), semilla=2)
            delta = gzip.compress((Path(d) / "delta.jsonl").read_bytes(), 6)
            reloj("ssh-delta", lambda: subprocess.run(["ssh", "-o", "BatchMode=yes", o.ssh, f"gunzip >> {destino}"],
                                                       input=delta, check=True) and f"{len(delta) / 1e6:.1f} MB comprimidos")
            subprocess.run(["ssh", o.ssh, f"rm -f {destino} " + " ".join(x for x in dejados if x)], check=False)
        else:
            print("(sin --ssh: lo que quedó en la entrada de allá hay que borrarlo a mano:", ", ".join(dejados), ")")


if __name__ == "__main__":
    main()
