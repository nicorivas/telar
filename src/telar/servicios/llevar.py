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
    return d / f"{casilla.ficha(config, hilo)}.log"


def llevar(ctx, hilo: str, maquina: str = "", si: bool = False, espera: float = ESPERA, subir: bool = False) -> Llevado:
    """`si`: llevarlo aunque haya algo sin subir; `subir`: subir antes lo suyo (telar.sin_subir). Sin ninguno, si hay
    algo, falla con 409 y el detalle queda en el progreso de la mudanza (`pendiente`), para mostrarlo."""
    if not hilo.strip():
        raise ErrorDeServicio("¿qué hilo?", 422)
    argv = [sys.executable, "-m", "telar", "hilo", "llevar", *([maquina] if maquina else []), "--hilo", hilo,
            *(["--si"] if si else []), *(["--subir"] if subir else [])]
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


#: cuánto se espera a la dueña al pedirle traer un hilo: ella lo corre aparte y contesta en unos 20 s (ESPERA), lo
#: que tarde en fallar lo que pide confirmar
ESPERA_TRAER = 90.0


def traer(ctx, hilo: str, maquina: str, si: bool = False, *, a: str = "", subir: bool = False) -> Llevado:
    """«Traer a esta máquina» un hilo que vive en `maquina`, otra de la persona: se le pide por el bus que lo lleve
    aquí (telar.mudanza.traer_aqui). Con `a`, que lo lleve a esa otra máquina (ni esta ni la suya). Allá corre aparte:
    si termina pronto se devuelve lo que dijo (y, si falló, su queja); si no, `en_curso`, y su progreso se lee de allá
    (`progreso`, GET /mudanza?maquina=)."""
    from telar import bus as mod_bus

    if not hilo.strip() or not maquina.strip():
        raise ErrorDeServicio("¿qué hilo, y de qué máquina?", 422)
    if not mod_bus.hay_bus(ctx.config):
        raise ErrorDeServicio("sin bus no se trae un hilo de otra máquina", 409)
    aqui = mod_bus.maquina(ctx.config)
    if a and a == maquina:
        raise ErrorDeServicio(f"«{hilo}» ya vive en {maquina}", 422)
    r = mod_bus.pedir(ctx.config, maquina, "hilo-traer", {"hilo": hilo, "a": a or aqui, "si": si,
                                                         **({"subir": True} if subir else {})}, espera=ESPERA_TRAER)
    if not r.get("ok"):
        raise ErrorDeServicio(f"{maquina}: {r.get('error', 'no respondió')}", 502)
    texto = str(r.get("salida") or "")
    if int(r.get("codigo") or 0) != 0:
        lineas = texto.strip().splitlines()
        queja = next((l for l in reversed(lineas) if l.startswith("telar: ")), lineas[-1] if lineas else "no se trajo")
        raise ErrorDeServicio(queja.removeprefix("telar: "), 409, {"salida": texto, "codigo": r.get("codigo")})
    return Llevado(codigo=0, salida=texto, en_curso=bool(r.get("en_curso")))


def progreso(ctx, hilo: str, maquina: str = "") -> dict:
    """En qué va la mudanza de `hilo` (telar.mudanza.progreso): la que corre aquí o, con `maquina` (otra de la
    persona), la que corre allá, pedida por el bus: así quien pidió traer un hilo ve sus pasos. {} si no hay ninguna o
    allá no contesta."""
    from telar import bus as mod_bus
    from telar import mudanza

    if not maquina or not mod_bus.hay_bus(ctx.config) or maquina == mod_bus.maquina(ctx.config):
        return mudanza.progreso_de(ctx.config, hilo)
    r = mod_bus.pedir(ctx.config, maquina, mudanza.VERBO_PROGRESO, {"hilo": hilo}, espera=8)
    d = r.get("progreso") if r.get("ok") else None
    return d if isinstance(d, dict) else {}
