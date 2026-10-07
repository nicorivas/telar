"""Las notas de los eventos del día (`[notas]`): lo que una skill o la persona deja sobre una reunión.

Una skill que planifica o prepara reuniones deja una nota en el evento (`telar evento nota`); el
dashboard la muestra al hacer clic en él. Un archivo por día:

    <carpeta>/AAAA-MM-DD.json   {"eventos": {"<id del evento>": {"titulo", "inicio", "notas": [
                                    {"de", "texto", "creado"}]}}}

El evento se nombra por su id en el calendario. El título y la hora van al lado para que la nota
se pueda mostrar aunque el id cambie (un evento movido, otro calendario).

Con `en` y bus, se leen y se escriben en esa máquina; si no responde, leer cae a la copia de aquí y
escribir falla y lo dice: una nota escrita en la máquina equivocada no la vería nadie.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

from telar.resultados import DIA

#: lo más largo que se guarda de una nota
MAX_NOTA = 4000


def carpeta(config) -> Path:
    c = config.notas.carpeta
    return Path(c).expanduser() if c else Path(config.estado) / "notas"


def _archivo(config, dia: str) -> Path:
    return carpeta(config) / f"{dia}.json"


def _cargar(config, dia: str) -> dict:
    try:
        datos = json.loads(_archivo(config, dia).read_text(encoding="utf-8"))
        return datos if isinstance(datos.get("eventos"), dict) else {"eventos": {}}
    except (OSError, ValueError, AttributeError):
        return {"eventos": {}}


def leer_local(config, dia: str = "") -> dict:
    dia = dia or date.today().isoformat()
    if not DIA.fullmatch(dia):
        return {"ok": False, "error": f"«{dia[:12]}» no es un día (AAAA-MM-DD)"}
    return {"ok": True, "dia": dia, **_cargar(config, dia)}


def agregar_local(config, dia: str, evento: str, texto: str, *, de: str, titulo: str = "", inicio: str = "") -> dict:
    dia = dia or date.today().isoformat()
    if not DIA.fullmatch(dia):
        return {"ok": False, "error": f"«{dia[:12]}» no es un día (AAAA-MM-DD)"}
    evento, texto = evento.strip(), texto.strip()
    if not evento or not texto:
        return {"ok": False, "error": "la nota necesita el evento y el texto"}
    datos = _cargar(config, dia)
    e = datos["eventos"].setdefault(evento, {"titulo": "", "inicio": "", "notas": []})
    if titulo:
        e["titulo"] = titulo.strip()
    if inicio:
        e["inicio"] = inicio.strip()
    nota = {"de": de.strip() or "alguien", "texto": texto[:MAX_NOTA],
            "creado": datetime.now().astimezone().isoformat(timespec="seconds")}
    e["notas"].append(nota)
    f = _archivo(config, dia)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    return {"ok": True, "dia": dia, "evento": evento, "nota": nota}


def _remota(config) -> str:
    from telar import bus as mod_bus

    en = config.notas.en
    if en and mod_bus.hay_bus(config) and en != mod_bus.maquina(config):
        return en
    return ""


def leer(config, dia: str = "") -> dict:
    from telar import bus as mod_bus

    en = _remota(config)
    if en:
        r = mod_bus.pedir(config, en, "notas", {"dia": dia}, espera=15)
        if r.get("ok"):
            return {**r, "desde": en}
        return {**leer_local(config, dia), "desde": "aquí", "aviso": f"{en} no respondió ({r.get('error', '')}); son las notas de aquí"}
    return {**leer_local(config, dia), "desde": "aquí"}


def agregar(config, dia: str, evento: str, texto: str, *, de: str, titulo: str = "", inicio: str = "") -> dict:
    from telar import bus as mod_bus

    en = _remota(config)
    if en:
        r = mod_bus.pedir(config, en, "nota", {"dia": dia, "evento": evento, "texto": texto, "de": de,
                                                "titulo": titulo, "inicio": inicio}, espera=15)
        return {**r, "en": en} if r.get("ok") else {"ok": False, "error": f"la nota no llegó a {en}: {r.get('error', '')}"}
    return agregar_local(config, dia, evento, texto, de=de, titulo=titulo, inicio=inicio)
