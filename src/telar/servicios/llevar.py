"""Llevar un hilo a otra máquina (`telar hilo llevar`) desde la API, sin tenerla ocupada minutos.

Llevar copia la conversación por ssh y abre el hilo allá: con una conversación grande tarda minutos. Lo que
puede fallar rápido —a qué máquina, si hay trabajo sin subir que pide confirmar— falla en los primeros
segundos. Así que se corre aparte, en su propio proceso: si termina dentro de ESPERA, se devuelve lo que
dijo (y, si falló, su queja); si no, se responde que sigue en curso y el proceso continúa solo, con su
salida en `<estado>/llevar/<hilo>.log`.

No usa el puente de `telar.servicios.en_proceso`: ese corre de a uno, y llevar lo tendría tomado minutos.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio

#: cuánto se espera a que termine antes de responder que sigue en curso
ESPERA = 20.0


class Llevado(BaseModel):
    """Lo que pasó: `en_curso` si sigue copiando (la salida queda en `registro`)."""

    codigo: int = 0
    salida: str = ""
    error: str = ""
    en_curso: bool = False
    registro: str = ""


def _registro(config, hilo: str) -> Path:
    from telar import casilla

    d = Path(config.estado) / "llevar"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{casilla.nombre_de_carpeta(hilo)}.log"


def llevar(ctx, hilo: str, maquina: str = "", si: bool = False, espera: float = ESPERA) -> Llevado:
    if not hilo.strip():
        raise ErrorDeServicio("¿qué hilo?", 422)
    argv = [sys.executable, "-m", "telar", "hilo", "llevar", *([maquina] if maquina else []), "--hilo", hilo,
            *(["--si"] if si else [])]
    registro = _registro(ctx.config, hilo)
    with registro.open("w", encoding="utf-8") as salida:
        # sin terminal: lo que pediría confirmar sale con su queja («--si para llevarla igual»)
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=salida, stderr=subprocess.STDOUT,
                                start_new_session=True)
    limite = time.monotonic() + espera
    while proc.poll() is None and time.monotonic() < limite:
        time.sleep(0.2)
    texto = registro.read_text(encoding="utf-8", errors="replace")
    if proc.returncode is None:
        return Llevado(en_curso=True, salida=texto, registro=str(registro))
    if proc.returncode != 0:
        # la queja es la línea «telar: …»; lo que venga después es contexto (y la última línea a secas engaña)
        lineas = texto.strip().splitlines()
        queja = next((l for l in reversed(lineas) if l.startswith("telar: ")), lineas[-1] if lineas else "no se llevó")
        linea = queja.removeprefix("telar: ")
        raise ErrorDeServicio(linea, 409, {"salida": texto, "codigo": proc.returncode})
    return Llevado(codigo=0, salida=texto, registro=str(registro))
