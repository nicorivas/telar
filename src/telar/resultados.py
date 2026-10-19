"""Lo que deja una skill por día, para verlo en el dashboard (`[resultados.<clave>]`).

Una skill que corre sola (el plan del día, la preparación de las reuniones) escribe un
`AAAA-MM-DD.json` (o `.md`) por día en una carpeta. telar no sabe qué hay adentro: lo entrega tal
cual y quien lo muestra decide cómo.

    [resultados.plan]
    carpeta = "~/notas/planes"
    en = "telar"           # la máquina que corre la skill; "" es esta
    comentar = ["~/bin/plan-comentario"]   # opcional, donde vive: atiende un comentario sobre un día

Con `en` y bus, se le pide a esa máquina (su nodo lee su propia carpeta): la sincronización entre
máquinas es frágil, y el resultado vive donde se escribió. Si esa máquina no responde, o no hay
bus, se lee la carpeta de aquí, y se dice.
"""

from __future__ import annotations

import json
import re
import os
import subprocess
from datetime import date
from pathlib import Path

DIA = re.compile(r"\d{4}-\d{2}-\d{2}")
#: cuántos días hacia atrás se listan para navegar
DIAS_LISTADOS = 60


def declarado(config, clave: str):
    return next((r for r in config.resultados if r.clave == clave), None)


def local(config, clave: str, dia: str = "") -> dict:
    """El resultado de un día leído de la carpeta de esta máquina. Siempre `{"ok": …}`."""
    r = declarado(config, clave)
    if r is None:
        return {"ok": False, "error": f"no hay un resultado «{clave}» en [resultados]"}
    if not r.carpeta:
        return {"ok": False, "error": f"«{clave}» no tiene carpeta en esta máquina"}
    carpeta = Path(r.carpeta).expanduser()
    dia = dia or date.today().isoformat()
    if not DIA.fullmatch(dia):
        return {"ok": False, "error": f"«{dia[:12]}» no es un día (AAAA-MM-DD)"}
    dias = sorted({f.stem for f in carpeta.glob("*") if DIA.fullmatch(f.stem) and f.suffix in (".json", ".md")},
                  reverse=True)[:DIAS_LISTADOS] if carpeta.is_dir() else []
    base = {"clave": clave, "nombre": r.nombre or clave, "dia": dia, "dias": dias, "comentable": bool(r.comentar)}
    for ext in (".json", ".md"):
        f = carpeta / f"{dia}{ext}"
        if not f.is_file():
            continue
        texto = f.read_text(encoding="utf-8")
        if ext == ".md":
            return {"ok": True, **base, "formato": "md", "contenido": texto}
        try:
            return {"ok": True, **base, "formato": "json", "contenido": json.loads(texto)}
        except ValueError as e:
            return {"ok": False, **base, "error": f"{f.name} no es JSON válido: {e}"}
    return {"ok": True, **base, "formato": "", "contenido": None}


def leer(config, clave: str, dia: str = "") -> dict:
    """El resultado de un día, de la máquina donde vive si se declaró `en`; si no responde, de aquí."""
    from telar import bus as mod_bus

    r = declarado(config, clave)
    if r is None:
        return {"ok": False, "error": f"no hay un resultado «{clave}» en [resultados]"}
    if r.en and mod_bus.hay_bus(config) and r.en != mod_bus.maquina(config):
        alla = mod_bus.pedir(config, r.en, "resultado", {"clave": clave, "dia": dia}, espera=15)
        if alla.get("ok"):
            return {**alla, "desde": r.en}
        aqui = local(config, clave, dia)
        return {**aqui, "desde": "aquí", "aviso": f"{r.en} no respondió ({alla.get('error', '')}); se leyó la copia de aquí"}
    return {**local(config, clave, dia), "desde": "aquí"}


#: el comentario más largo que se acepta
MAX_COMENTARIO = 4000


def comentar_local(config, clave: str, dia: str, texto: str) -> dict:
    """Un comentario sobre el resultado de un día, atendido aquí: corre el `comentar` declarado con el
    texto por la entrada estándar (nunca en la línea de comandos) y el día y la carpeta en el entorno
    (`TELAR_RESULTADO_DIA`, `TELAR_RESULTADO_CARPETA`). La primera línea que imprima es lo que abrió
    (un hilo, normalmente). Siempre `{"ok": …}`."""
    r = declarado(config, clave)
    if r is None:
        return {"ok": False, "error": f"no hay un resultado «{clave}» en [resultados]"}
    if not r.comentar:
        return {"ok": False, "error": f"«{clave}» no recibe comentarios en esta máquina ([resultados.{clave}] comentar)"}
    texto = (texto or "").strip()
    if not DIA.fullmatch(dia or ""):
        return {"ok": False, "error": f"«{(dia or '')[:12]}» no es un día (AAAA-MM-DD)"}
    if not texto:
        return {"ok": False, "error": "el comentario está vacío"}
    if len(texto) > MAX_COMENTARIO:
        return {"ok": False, "error": f"el comentario pasa de {MAX_COMENTARIO} caracteres"}
    carpeta = Path(r.carpeta).expanduser() if r.carpeta else Path()
    if r.carpeta and not any((carpeta / f"{dia}{ext}").is_file() for ext in (".json", ".md")):
        return {"ok": False, "error": f"no hay {r.nombre or clave} del {dia}"}
    comando = [os.path.expanduser(r.comentar[0]), *r.comentar[1:]]
    entorno = {**os.environ, "TELAR_RESULTADO_DIA": dia, "TELAR_RESULTADO_CARPETA": str(carpeta)}
    try:
        p = subprocess.run(comando, input=texto, capture_output=True, text=True, timeout=60, env=entorno)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": f"no pude correr {r.comentar[0]}: {type(e).__name__}"}
    if p.returncode != 0:
        cola = (p.stderr.strip().splitlines() or [f"salió con {p.returncode}"])[-1]
        return {"ok": False, "error": cola[:200]}
    primera = (p.stdout.strip().splitlines() or [""])[0]
    return {"ok": True, "abrio": primera.split(" · ")[0][:120]}


def comentar(config, clave: str, dia: str, texto: str) -> dict:
    """Un comentario sobre un día: lo atiende la máquina donde vive el resultado (`en`, por el bus)."""
    from telar import bus as mod_bus

    r = declarado(config, clave)
    if r is None:
        return {"ok": False, "error": f"no hay un resultado «{clave}» en [resultados]"}
    if r.en and mod_bus.hay_bus(config) and r.en != mod_bus.maquina(config):
        return mod_bus.pedir(config, r.en, "resultado-comentar", {"clave": clave, "dia": dia, "texto": texto}, espera=70)
    return comentar_local(config, clave, dia, texto)

