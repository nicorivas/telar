"""`telar mensaje` — un mensaje para un hilo o un agente, en la máquina que sea, por el bus.

    telar mensaje Gestión "¿quedó la nota en T185?"
    telar mensaje gestion -              el texto por la entrada estándar (sin tope de largo práctico)
    telar mensaje Faro "…" --tipo encargo
    telar mensaje --registro [N]         los últimos mensajes entre hilos, de todas las máquinas
    telar mensaje --retenidos            los que se retuvieron (cadena larga, demasiados por hora)
    telar mensaje --soltar <id>          mandar uno retenido (lo decide la persona)

El mensaje espera en la casilla del hilo hasta que la máquina donde vive lo recoja (`telar nodo`) y
entra a la conversación por sus ganchos, entero, sin teclearlo. Un agente se nombra por su carpeta o
su nombre; cualquier otro nombre es un hilo, viva donde viva. Necesita `[bus] url`.

Entre hilos de una misma persona los mensajes corren sin pedirle permiso, con dos frenos en su lugar:
cada mensaje lleva cuántos saltos lleva su cadena sin que la persona hablara (`telar.casilla`), y
pasado el tope se retiene; y un hilo no manda más de cierto número por hora. Lo retenido queda en el
registro hasta que la persona lo suelte.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from telar import bus as mod_bus
from telar.ordenes import _comun

AYUDA = "Un mensaje para un hilo o un agente, en la máquina que sea, por el bus."

#: cuántos mensajes manda un hilo por hora antes de que se retengan
TOPE_HORA = 30


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("mensaje", AYUDA)
    p.epilog = __doc__
    p.add_argument("para", nargs="?", default="", help="el hilo (su nombre) o el agente (su carpeta o su nombre)")
    p.add_argument("texto", nargs="*", help="el mensaje (o «-» para leerlo de la entrada)")
    p.add_argument("--registro", nargs="?", type=int, const=40, default=0, metavar="N", help="los últimos N mensajes")
    p.add_argument("--retenidos", action="store_true", help="los retenidos que nadie ha soltado")
    p.add_argument("--soltar", default="", metavar="ID", help="mandar uno retenido")
    p.add_argument("--tipo", choices=("mensaje", "encargo"), default="mensaje")
    p.add_argument("--de", default="", help="quién lo manda (por defecto, este hilo o esta máquina)")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.registro or o.retenidos:
        try:
            lista = mod_bus.registro(ctx.config, max(o.registro, 200 if o.retenidos else 0))
        except mod_bus.ErrorDeBus as e:
            return _comun.queja(str(e))
        if o.retenidos:
            lista = retenidos(lista)
        if o.json:
            return _comun.escribir_json({"mensajes": lista})
        for m in lista:
            marca = "⏸ " if m.get("estado") == "retenido" else ""
            print(f"{str(m.get('creado', ''))[:16].replace('T', ' ')}  {marca}{m.get('de', '')} → {m.get('para', '')}"
                  + _comun.tenue(f"  {m.get('tipo', '')}{' · salto ' + str(m['saltos']) if m.get('saltos') else ''}"
                                 f"{' · ' + m['motivo'] if m.get('motivo') else ''} · {m.get('id', '')}"))
            print("    " + " ".join(str(m.get("texto", "")).split())[:160])
        return 0
    if o.soltar:
        try:
            r = soltar(ctx, o.soltar)
        except mod_bus.ErrorDeBus as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r)
        print(f"«{r['para']}»: soltado, en su casilla · id {r['id']}")
        return 0
    if not o.para:
        return _comun.queja("¿para quién? telar mensaje <hilo> \"texto\"")
    texto = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
    if not texto.strip():
        return _comun.queja("¿qué le digo? telar mensaje <hilo> \"texto\" (o «-» para la entrada)")
    try:
        r = enviar(ctx, o.para, texto, tipo=o.tipo, de=o.de)
    except mod_bus.ErrorDeBus as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    if r.get("estado") == "retenido":
        print(f"«{r['para']}»: RETENIDO, no se entregó ({r['motivo']}). Cuéntale a tu persona qué querías decir "
              f"y a quién; ella lo suelta con: telar mensaje --soltar {r['id']}", file=sys.stderr)
        return 3
    print(f"«{r['para']}»: en su casilla" + (" (ya estaba: no se duplicó)" if r.get("duplicado") else "") + f" · id {r['id']}")
    return 0


def _hilo_propio(ctx) -> str:
    """El hilo de quien escribe (`$TELAR_HILO`), con su nombre de hoy si se renombró mientras corría."""
    hilo = os.environ.get("TELAR_HILO", "").strip()
    if not hilo:
        return ""
    from telar import estado as mod_estado

    try:
        return mod_estado.abrir(ctx.config).nombre_actual(hilo)
    except Exception:  # noqa: BLE001 - sin estado legible, el nombre que se heredó
        return hilo


def remitente(ctx, de: str = "") -> str:
    return de or _hilo_propio(ctx) or f"{mod_bus.persona(ctx.config)}@{mod_bus.maquina(ctx.config)}"


def enviar(ctx, para: str, texto: str, *, tipo: str = "mensaje", de: str = "") -> dict:
    """Publica para `para` (un agente por su carpeta o nombre, o un hilo por su nombre).

    Si lo manda un hilo (`TELAR_HILO`), lleva un salto más que la cadena en la que está ese hilo, y se
    retiene (queda en el registro, sin entregar) si pasa el tope o si el hilo ya mandó demasiados
    esta hora. Lo que manda la persona desde un terminal no tiene freno."""
    from telar import agentes as mod_agentes
    from telar import casilla

    agente = next((a for a in mod_agentes.descubrir(ctx.config) if para in (a.clave, a.nombre)), None)
    nombre = agente.nombre if agente is not None else para
    hilo = _hilo_propio(ctx)
    saltos, retener = 0, ""
    if hilo:
        saltos = casilla.cadena(ctx.config, hilo) + 1
        if saltos > casilla.TOPE_SALTOS:
            retener = f"cadena de {saltos} mensajes entre hilos sin que hablara la persona (tope {casilla.TOPE_SALTOS})"
        elif _enviados_esta_hora(ctx.config, hilo) >= TOPE_HORA:
            retener = f"«{hilo}» ya mandó {TOPE_HORA} mensajes esta hora"
    r = mod_bus.enviar(ctx.config, nombre, texto.strip(), de=remitente(ctx, de), tipo=tipo, saltos=saltos, retener=retener)
    if hilo and not retener:
        _anotar_envio(ctx.config, hilo)
    return r


def retenidos(lista: list[dict]) -> list[dict]:
    """De un registro, los retenidos que todavía nadie soltó."""
    soltados = {m["id"] for m in lista if m.get("estado") == "enviado"}
    return [m for m in lista if m.get("estado") == "retenido" and m["id"] not in soltados]


def soltar(ctx, mid: str) -> dict:
    """Manda un mensaje retenido, con su mismo id y la cadena en cero: lo decidió la persona."""
    m = next((x for x in retenidos(mod_bus.registro(ctx.config, 500)) if x["id"] == mid), None)
    if m is None:
        raise mod_bus.ErrorDeBus(f"no hay un mensaje retenido con id {mid} (¿ya se soltó?)")
    return mod_bus.enviar(ctx.config, m["para"], m["texto"], de=m["de"], tipo=m.get("tipo") or "mensaje", mid=m["id"])


def _envios(config) -> Path:
    return Path(config.estado) / "casillas" / "enviados.log"


def _enviados_esta_hora(config, hilo: str) -> int:
    hace = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    try:
        lineas = _envios(config).read_text(encoding="utf-8").splitlines()[-500:]
    except OSError:
        return 0
    n = 0
    for linea in lineas:
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        n += d.get("hilo") == hilo and str(d.get("hora", "")) >= hace
    return n


def _anotar_envio(config, hilo: str) -> None:
    try:
        _envios(config).parent.mkdir(parents=True, exist_ok=True)
        with open(_envios(config), "a", encoding="utf-8") as f:
            f.write(json.dumps({"hilo": hilo, "hora": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
    except OSError:
        pass
