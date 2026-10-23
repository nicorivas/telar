"""Rotar con relevo: la conversación de un agente residente que pesa demasiado empieza de nuevo sin perder el hilo.

Un residente vive meses. Su conversación crece con cada encargo hasta que retomarla sale caro y lento; cortarla
en frío le hace olvidar en qué iba. Rotar con relevo es lo que haría una persona al cambiar de turno: antes de
irse, deja escrito en qué está; quien llega lo lee primero.

Cuando el agente termina un turno (el gancho `Stop`, con su casilla vacía) y su conversación pasa de
`[agentes] rotar_mb`, telar le pide su **relevo**: que escriba en `<estado>/relevos/<agente>.md` en qué estaba, qué
queda y qué tiene que saber la conversación siguiente, y que termine. Al terminar ese turno, el nodo de la máquina
le teclea `/clear` en su ventana (Claude Code abre otra conversación, que sus ganchos anotan como la del hilo) y,
cuando la nueva ya está anotada, le teclea que lea su relevo. Las fases quedan en `<estado>/rotaciones.json`:

    relevo    se le pidió el relevo a la conversación `sesion`
    limpiar   ya lo escribió: falta el /clear
    retomar   se tecleó el /clear: falta decirle a la nueva que lea su relevo

Una fase que no avanza en `PLAZO` segundos (el agente siguió en otra cosa, la ventana se cerró) se abandona.

En frío —un encargo que abre al agente sin sesión, `telar tejer`, `retomar`— una conversación demasiado pesada no
se retoma: se empieza otra, y su primer mensaje dice dónde está el último relevo (`con_relevo`).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

FASES = ("relevo", "limpiar", "retomar")
#: lo más que se espera a que una fase avance (segundos)
PLAZO = 30 * 60


def _ruta(config) -> Path:
    return Path(config.estado) / "rotaciones.json"


def ruta_relevo(config, clave: str) -> Path:
    """Dónde deja su relevo el agente `clave` (su carpeta): en el estado de esta máquina, no en el repositorio."""
    return Path(config.estado) / "relevos" / f"{clave}.md"


def leer(config) -> dict[str, dict]:
    try:
        d = json.loads(_ruta(config).read_text(encoding="utf-8"))
        return {h: r for h, r in d.items() if isinstance(r, dict) and r.get("fase") in FASES}
    except (OSError, ValueError, AttributeError):
        return {}


def _escribir(config, datos: dict) -> None:
    ruta = _ruta(config)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, ruta)


def _poner(config, hilo: str, **campos) -> None:
    d = leer(config)
    d[hilo] = {**d.get(hilo, {}), **campos, "cuando": time.time()}
    _escribir(config, d)


def _quitar(config, hilo: str) -> None:
    d = leer(config)
    if d.pop(hilo, None) is not None:
        _escribir(config, d)


def tope(config) -> int:
    """El peso desde el que se rota, en bytes; 0 si no se rota."""
    return int(getattr(config, "agentes_rotar_mb", 0) or 0) * 1024 * 1024


def pesada(config, archivo) -> int:
    """Cuánto pesa la conversación de ese archivo si pasa del tope (en bytes); 0 si no pasa o no se rota."""
    t = tope(config)
    if not t or not archivo:
        return 0
    try:
        peso = Path(archivo).stat().st_size
    except OSError:
        return 0
    return peso if peso > t else 0


def pedido_de_relevo(config, clave: str, peso: int) -> str:
    mb = lambda b: f"{b / (1024 * 1024):.0f} MB"  # noqa: E731
    return (f"[telar] Tu conversación pesa {mb(peso)} (el tope es {mb(tope(config))}): telar la va a rotar al "
            f"terminar este turno, y la siguiente empieza sin lo que llevas en la cabeza. Antes, escribe tu relevo en "
            f"{ruta_relevo(config, clave)} (reemplaza el anterior): en qué estabas, qué queda pendiente y para "
            f"quién, qué decidiste y por qué, y dónde está lo que la próxima conversación tiene que leer. Corto y en "
            f"prosa: lo lee alguien que no estuvo aquí. Lo que ya está en tu bitácora o tu memoria, no lo repitas; "
            f"anótalo ahí si falta. Cuando lo hayas escrito, termina el turno sin hacer nada más.")


def aviso_de_relevo(config, clave: str) -> str:
    return (f"[telar] Esta es una conversación nueva: la anterior pesaba demasiado y telar la rotó. Antes de "
            f"seguir, lee tu relevo, {ruta_relevo(config, clave)}: ahí está en qué ibas. Después, sigue con lo que "
            f"diga, o espera el próximo encargo.")


def con_relevo(config, clave: str, texto: str) -> str:
    """El primer mensaje de una conversación nueva de un agente (rotada en frío): con su último relevo, si hay."""
    relevo = ruta_relevo(config, clave)
    if not relevo.is_file():
        return texto
    return (f"[telar] Conversación nueva: la anterior pesaba demasiado. Tu último relevo está en {relevo}: léelo "
            f"antes de seguir.\n\n{texto}")


def al_terminar(config, hilo: str, sesion: str, transcripcion: str = "", *, archivo_de=None) -> str:
    """Lo que hace el gancho `Stop` de un agente con la casilla vacía. Devuelve el JSON que le pide su relevo (no lo
    deja parar), o "" si no hay nada que hacer (o si ya lo escribió: entonces queda para el /clear del nodo)."""
    from telar import agentes as mod_agentes

    if not hilo:
        return ""
    r = leer(config).get(hilo)
    # una que ya va (también una que pidió la persona, sin tope) sigue aunque no haya tope
    if r is None and not tope(config):
        return ""
    agente = mod_agentes.del_hilo(config, hilo)
    if agente is None:
        return ""
    if r is not None:
        vencida = time.time() - float(r.get("cuando", 0)) > PLAZO
        if r["fase"] == "relevo" and r.get("sesion") == sesion and not vencida:
            # el turno en que escribió su relevo: el nodo hace el resto cuando quede quieto
            _poner(config, hilo, fase="limpiar")
            return ""
        if not vencida:
            return ""  # limpiar o retomar: ya va en camino
        _quitar(config, hilo)
    archivo = transcripcion or (archivo_de(sesion) if archivo_de and sesion else "")
    peso = pesada(config, archivo)
    if not peso:
        return ""
    _poner(config, hilo, fase="relevo", sesion=sesion, agente=agente.clave, peso=peso)
    return json.dumps({"decision": "block", "reason": pedido_de_relevo(config, agente.clave, peso)}, ensure_ascii=False)


def avanzar(config, hilo: str, *, quieto: bool, sesion_actual: str, escribir) -> str:
    """El paso del nodo para un hilo en rotación: teclear `/clear` cuando quedó quieto tras escribir su relevo, y
    después decirle a la conversación nueva que lo lea. `escribir(texto)` teclea en su ventana. Devuelve lo que
    hizo, en una línea para el registro, o ""."""
    r = leer(config).get(hilo)
    if r is None:
        return ""
    if time.time() - float(r.get("cuando", 0)) > PLAZO:
        _quitar(config, hilo)
        return f"«{hilo}»: la rotación quedó en «{r['fase']}» más de {PLAZO // 60} min; la dejo"
    if not quieto:
        return ""
    if r["fase"] == "limpiar":
        escribir("/clear")
        _poner(config, hilo, fase="retomar")
        return f"«{hilo}»: escribió su relevo; /clear para empezar otra conversación"
    if r["fase"] == "retomar" and sesion_actual and sesion_actual != r.get("sesion"):
        escribir(aviso_de_relevo(config, r.get("agente") or hilo))
        _quitar(config, hilo)
        return f"«{hilo}»: conversación nueva ({sesion_actual[:8]}), con su relevo"
    return ""


def forzar(config, hilo: str, clave: str, sesion: str) -> str:
    """Rotar ya, aunque no pase del tope (lo pide la persona desde la página): el pedido de relevo, como mensaje
    para su casilla, y la fase anotada; al terminar ese turno sigue como cualquier rotación. Devuelve el texto."""
    _poner(config, hilo, fase="relevo", sesion=sesion, agente=clave, peso=0)
    return (f"[telar] Tu persona pidió rotar tu conversación ahora: la siguiente empieza sin lo que llevas en la "
            f"cabeza. Antes, escribe tu relevo en {ruta_relevo(config, clave)} (reemplaza el anterior): en qué estabas, "
            f"qué queda pendiente y para quién, qué decidiste y por qué. Corto y en prosa. Cuando lo hayas escrito, "
            f"termina el turno sin hacer nada más.")
