"""A qué proyecto pertenece una reunión: lo que se deduce, y lo que la persona ya decidió una vez.

Una reunión del calendario no dice de qué proyecto es. Se deduce con tres señales, cada una
pesada por lo poco común que es (una palabra que está en cinco proyectos dice menos que una que
está en uno):

- las palabras del título que están en el nombre de la carpeta del proyecto;
- el dominio del correo de los asistentes («@cliente.cl») en el nombre de la carpeta;
- los asistentes (su correo o su nombre completo) que aparecen en el README del proyecto.

Un dominio o una persona que aparece en muchos proyectos es la propia empresa: no decide nada y se
descarta. Cuando la persona elige un proyecto para una serie de reuniones, se recuerda por el título
de la serie (`<estado>/reuniones.json`, en la máquina de `[notas] en`): la próxima vez va directo,
sin preguntar.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

#: desde cuántos proyectos un dominio o una persona es de la casa y no dice nada
COMUN = 3
#: lo que alcanza para decidir sin preguntar: el primero suma al menos esto…
SEGURO = 2.0
#: …y le saca esta ventaja al segundo
VENTAJA = 2.0
#: palabras que no distinguen una reunión de otra
VACIAS = {"reunion", "reuniones", "weekly", "semanal", "daily", "comite", "sesion", "coordinacion", "interna",
          "interno", "seguimiento", "avance", "con", "para", "del", "las", "los", "una", "the", "and", "meeting",
          "sync", "call", "brief", "kick", "off", "kickoff", "revision", "entrevista"}
#: lo que queda de una fecha en un título («7-oct», «14 de octubre»): no distingue una serie de otra
MESES = {"ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "sept", "oct", "nov", "dic", "enero", "febrero",
         "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre", "de"}
#: dominios de correo que no son de ninguna organización
GENERICOS = {"gmail", "hotmail", "outlook", "yahoo", "icloud", "live", "google", "googlemail", "proton", "protonmail"}


def _plano(texto: str) -> str:
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()


def palabras(texto: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", _plano(texto)) if len(w) >= 3 and w not in VACIAS}


def serie(titulo: str) -> str:
    """El título sin fechas ni números: «Weekly KO Andina 7-oct» y la del 14 son la misma serie."""
    t = re.sub(r"\d+", " ", _plano(titulo))
    return " ".join(w for w in re.split(r"[^a-z]+", t) if w and w not in MESES)


def _archivo(config) -> Path:
    return Path(config.estado) / "reuniones.json"


def recordado_local(config, titulo: str) -> str:
    """Lo que la persona eligió antes para esta serie: la ruta de un proyecto, «gestion», o ""."""
    try:
        return str(json.loads(_archivo(config).read_text(encoding="utf-8")).get(serie(titulo), ""))
    except (OSError, ValueError, AttributeError):
        return ""


def recordado(config, titulo: str) -> str:
    """Lo mismo, leído en la máquina que guarda las notas (`[notas] en`): la elección hecha en el
    dashboard del laptop vale también para lo que corre en el servidor (el correo, las minutas)."""
    from telar import bus as mod_bus
    from telar import notas

    en = notas._remota(config)
    if en:
        r = mod_bus.pedir(config, en, "serie", {"titulo": titulo}, espera=10)
        if r.get("ok"):
            return str(r.get("destino", ""))
    return recordado_local(config, titulo)


def recordar(config, titulo: str, destino: str) -> None:
    from telar import bus as mod_bus
    from telar import notas

    en = notas._remota(config)
    if en and mod_bus.pedir(config, en, "serie-recordar", {"titulo": titulo, "destino": destino}, espera=10).get("ok"):
        return
    recordar_local(config, titulo, destino)


def recordar_local(config, titulo: str, destino: str) -> None:
    f = _archivo(config)
    try:
        datos = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    datos[serie(titulo)] = destino
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def _asistente(texto: str) -> tuple[str, str]:
    """(nombre, correo) de «Nombre <correo>» o de un correo solo."""
    m = re.match(r"\s*(.*?)\s*<([^>]+)>\s*$", texto)
    if m:
        return m.group(1), m.group(2).strip().lower()
    return ("", texto.strip().lower()) if "@" in texto else (texto.strip(), "")


def _dominio(correo: str) -> str:
    """«ana@mail.cliente.cl» → «cliente»: la parte del dominio que nombra a la organización."""
    partes = correo.rsplit("@", 1)[-1].split(".")
    if len(partes) >= 3 and len(partes[-1]) == 2 and partes[-2] in {"com", "co", "gob", "org", "net", "edu"}:
        return partes[-3]
    return partes[-2] if len(partes) >= 2 else ""


def _readme(raiz: Path, unidad: str) -> str:
    for nombre in ("README.md", "readme.md"):
        f = raiz / unidad / nombre
        try:
            return _plano(f.read_text(encoding="utf-8", errors="ignore")[:80_000])
        except OSError:
            continue
    return ""


def candidatos(raiz: Path, unidades: list[str], titulo: str, asistentes: list[str], *, limite: int = 6) -> list[dict]:
    """Los proyectos de los que podría ser la reunión, del más probable al menos, con el porqué."""
    de_cada = {u: palabras(Path(u).name.replace("-", " ").replace("_", " ")) for u in unidades}
    frecuencia: dict[str, int] = {}
    for ps in de_cada.values():
        for p in ps:
            frecuencia[p] = frecuencia.get(p, 0) + 1
    puntos: dict[str, float] = {}
    motivos: dict[str, list[str]] = {}

    def sumar(u: str, valor: float, motivo: str) -> None:
        puntos[u] = puntos.get(u, 0.0) + valor
        if motivo not in motivos.setdefault(u, []):
            motivos[u].append(motivo)

    for w in palabras(titulo):
        for u, ps in de_cada.items():
            if w in ps:
                sumar(u, 1 / frecuencia[w], f"«{w}» en el título")

    personas = [_asistente(a) for a in asistentes]
    dominios = {_dominio(c) for _, c in personas if c} - GENERICOS - {""}
    for d in dominios:
        en = [u for u, ps in de_cada.items() if any(d == p or (len(p) >= 4 and p in d) or (len(d) >= 4 and d in p) for p in ps)]
        if 0 < len(en) <= COMUN:
            for u in en:
                sumar(u, 1.5 / len(en), f"asistentes de @{d}")

    if personas:
        textos = {u: _readme(raiz, u) for u in unidades}
        # un dominio que aparece en muchos READMEs es el de la propia empresa (o el de la persona): sus
        # asistentes están en todas las reuniones y no dicen de qué proyecto es ninguna
        casa = {c.rsplit("@", 1)[-1] for _, c in personas if c
                and sum(1 for t in textos.values() if "@" + c.rsplit("@", 1)[-1] in t) > COMUN}
        for nombre, correo in personas:
            if correo and correo.rsplit("@", 1)[-1] in casa:
                continue
            claves = [c for c in (correo, _plano(nombre) if len(nombre.split()) >= 2 else "") if c]
            for clave in claves:
                en = [u for u, t in textos.items() if t and clave in t]
                if 0 < len(en) <= COMUN:
                    for u in en:
                        sumar(u, 2.0 / len(en), f"{nombre or correo} aparece en su README")
                    break

    orden = sorted(puntos, key=lambda u: (-puntos[u], u))[:limite]
    return [{"ruta": u, "nombre": Path(u).name, "puntaje": round(puntos[u], 2), "motivos": motivos[u]} for u in orden]


def decidir(cands: list[dict]) -> str:
    """La ruta del proyecto si la deducción es clara; "" si hay que preguntar."""
    if not cands or cands[0]["puntaje"] < SEGURO:
        return ""
    if len(cands) > 1 and cands[0]["puntaje"] < VENTAJA * cands[1]["puntaje"]:
        return ""
    return cands[0]["ruta"]
