"""`telar mensaje` — un mensaje para un hilo o un agente, en la máquina que sea, por el bus.

    telar mensaje Gestión "¿quedó la nota en T185?"
    telar mensaje gestion -              el texto por la entrada estándar (sin tope de largo práctico)
    telar mensaje Faro "…" --tipo encargo
    telar mensaje Faro - --tipo persona --de "el panel"   lo escribe la persona, desde otra parte
    telar mensaje Faro "…" --modo aviso      para que lo sepa: espera en su casilla y no lo despierta
    telar mensaje Faro "…" --modo encargo [--plazo 2026-10-24]
                                         un Encargo (`encargo:e-…`) que Faro acepta y cierra con un resultado
    telar mensaje Faro --modo consulta   en qué anda, sin entrar a su conversación (su ficha y lo último)
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

El modo (`--modo`, docs/propuestas/mensajes-con-modos.md) dice qué espera quien manda: `pedido` (lo de
siempre: despierta), `aviso` (no despierta), `encargo` (despierta y crea un Encargo, telar.encargo, en la
máquina del destinatario) o `consulta` (no manda nada: lee el estado del hilo).
"""

from __future__ import annotations

import json
import os
import re
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
    # persona: lo escribe la persona desde otra parte (el panel en el celular): le llega como suyo, no de un colega
    p.add_argument("--tipo", choices=("mensaje", "encargo", "persona"), default="mensaje")
    p.add_argument("--modo", choices=MODOS, default="pedido",
                   help="aviso (no despierta), pedido (lo de siempre), encargo (un Encargo con resultado) o consulta")
    p.add_argument("--plazo", default="", metavar="FECHA", help="con --modo encargo: para cuándo (2026-10-24)")
    p.add_argument("--de", default="", help="quién lo manda (por defecto, este hilo o esta máquina)")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.registro or o.retenidos:
        from telar.servicios import ErrorDeServicio
        from telar.servicios import mensajes as servicio

        try:
            r = servicio.registro(ctx, o.registro, retenidos=bool(o.retenidos))
        except ErrorDeServicio as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r.model_dump(mode="json"))
        lista = r.mensajes
        for m in lista:
            marca = "⏸ " if m.get("estado") == "retenido" else ""
            print(f"{str(m.get('creado', ''))[:16].replace('T', ' ')}  {marca}{m.get('de', '')} → {m.get('para', '')}"
                  + _comun.tenue(f"  {m.get('tipo', '')}{' · salto ' + str(m['saltos']) if m.get('saltos') else ''}"
                                 f"{' · ' + m['motivo'] if m.get('motivo') else ''} · {m.get('id', '')}"))
            print("    " + " ".join(str(m.get("texto", "")).split())[:160])
        return 0
    if o.soltar:
        from telar.servicios import ErrorDeServicio
        from telar.servicios import mensajes as servicio

        try:
            r = servicio.soltar(ctx, o.soltar).model_dump(mode="json")
        except ErrorDeServicio as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r)
        print(f"«{r['para']}»: soltado, en su casilla · id {r['id']}")
        return 0
    if not o.para:
        return _comun.queja("¿para quién? telar mensaje <hilo> \"texto\"")
    if o.modo == "consulta":
        return _consulta(ctx, o)
    texto = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
    if not texto.strip():
        return _comun.queja("¿qué le digo? telar mensaje <hilo> \"texto\" (o «-» para la entrada)")
    from telar.servicios import ErrorDeServicio
    from telar.servicios import mensajes as servicio

    try:
        r = servicio.enviar(ctx, o.para, texto, tipo=o.tipo, de=o.de, modo=o.modo, plazo=o.plazo).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    if r.get("estado") == "retenido":
        print(f"«{r['para']}»: RETENIDO, no se entregó ({r['motivo']}). Cuéntale a tu persona qué querías decir "
              f"y a quién; ella lo suelta con: telar mensaje --soltar {r['id']}", file=sys.stderr)
        return 3
    como = {"aviso": " (un aviso: no lo despierta)"}.get(o.modo, "")
    print(f"«{r['para']}»: en su casilla{como}" + (" (ya estaba: no se duplicó)" if r.get("duplicado") else "")
          + f" · id {r['id']}")
    if r.get("encargo"):
        print(f"  {r['direccion']}: en qué va, con telar objeto {r['direccion']}")
    return 0


def _consulta(ctx, o) -> int:
    """`--modo consulta`: la ficha del hilo y lo último de su conversación, sin mandarle nada."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import mensajes as servicio

    if o.texto:
        return _comun.queja("una consulta no lleva texto: no se le manda nada, se lee su estado (sin --modo consulta, "
                            "se le escribe)")
    try:
        r = servicio.consultar(ctx, o.para).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    obj = r["objeto"]
    campos = obj.get("campos") or {}
    donde = " · ".join(x for x in (campos.get("relativa", ""), obj.get("maquina", "")) if x)
    print(f"«{obj['titulo']}»: {obj.get('estado') or 'sin atención'}" + _comun.tenue(f"  {donde}" if donde else ""))
    turnos = (r.get("ultimos") or {}).get("turnos") or []
    for turno in turnos:
        for paso in turno:
            print(f"  {paso.get('quien', '')}: " + " ".join(str(paso.get("texto", "")).split())[:200])
    if r.get("problema"):
        print(_comun.tenue(f"  (su conversación: {r['problema']})"))
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


_ID_DE_HILO = re.compile(r"^@?\d+$")


def _por_nombre(ctx, para: str) -> str:
    """El nombre del hilo si `para` es un id (`@144`, como lo muestran `telar hilos` y el dashboard).

    La casilla se llama como el hilo, no como su id: un `@144` tal cual iba a una casilla «144» que
    nadie lee, y el mensaje salía como entregado. Un id que no es de un hilo de esta máquina se
    rechaza: el hilo de otra máquina se nombra, no se numera."""
    if para.strip().startswith("hilo:"):
        return _por_direccion(ctx, para.strip())
    if not _ID_DE_HILO.match(para.strip()):
        return para
    ref = "@" + para.strip().lstrip("@")
    tel = _comun.tejer(ctx, con_ficha=False)
    hilo = next((h for h in tel.hilos if h.id == ref), None)
    if hilo is None:
        raise mod_bus.ErrorDeBus(f"no hay ningún hilo con id {ref} en esta máquina: escribe su nombre")
    return hilo.nombre


class NoHayHilo(mod_bus.ErrorDeBus):
    """La máquina de `hilo:X@máquina` no tiene un hilo X: un 404, no una falla del bus."""


def _por_direccion(ctx, para: str) -> str:
    """El nombre del hilo de una dirección (`hilo:Faro`, `hilo:Faro@servidor`). Con `@máquina`, esa máquina
    tiene que tener un hilo así (aquí, o según la foto que publicó en el bus): la casilla es del nombre, y un
    mensaje para un hilo que allá no existe quedaría en una casilla que nadie lee, dado por entregado."""
    from telar import objetos
    from telar.servicios import ErrorDeServicio

    try:
        d = objetos.leer(para)
    except ErrorDeServicio as e:
        raise mod_bus.ErrorDeBus(str(e)) from None
    if not d.maquina or not mod_bus.hay_bus(ctx.config):
        return d.id
    if d.maquina == mod_bus.maquina(ctx.config):
        tel = _comun.tejer(ctx, con_ficha=False)
        if not any(h.nombre == d.id and not h.remoto for h in tel.hilos):
            raise NoHayHilo(f"{d.maquina} (esta máquina) no tiene un hilo «{d.id}»")
    elif objetos._hilo_remoto(ctx, d.id, d.maquina) is None:
        raise NoHayHilo(f"{d.maquina} no tiene un hilo «{d.id}» (según lo último que publicó en el bus)")
    return d.id


#: los modos de `--modo`: los que viajan (telar.casilla.MODOS) y la consulta, que no viaja
MODOS = ("aviso", "pedido", "encargo", "consulta")


def enviar(ctx, para: str, texto: str, *, tipo: str = "mensaje", de: str = "", modo: str = "pedido",
           plazo: str = "") -> dict:
    """Publica para `para` (un agente por su carpeta o nombre, o un hilo por su nombre).

    Si lo manda un hilo (`TELAR_HILO`), lleva un salto más que la cadena en la que está ese hilo, y se
    retiene (queda en el registro, sin entregar) si pasa el tope o si el hilo ya mandó demasiados
    esta hora. Lo que manda la persona desde un terminal no tiene freno.

    `modo` (telar.casilla): un `encargo` lleva el id de su Encargo (que se crea al llegar), su `plazo` y el
    hilo que lo pidió (`responder_a`, al que se le avisa al cerrarlo); aquí queda la nota de a quién se mandó
    (telar.encargo), y lo devuelto trae `encargo` y su `direccion`. ValueError si el modo o el plazo no sirven."""
    from telar import agentes as mod_agentes
    from telar import casilla
    from telar import encargo as mod_encargo

    if modo not in casilla.MODOS:
        raise ValueError(f"el modo «{modo}» no se manda: {', '.join(casilla.MODOS)} (la consulta no viaja)")
    if plazo and modo != "encargo":
        raise ValueError("el plazo es de un encargo: --modo encargo --plazo …")
    plazo = mod_encargo.plazo_valido(plazo)
    para = _por_nombre(ctx, para)
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
    # el modo y lo suyo, solo cuando no es un pedido: así un pedido se publica exactamente como siempre
    con_modo = {}
    eid = ""
    if modo == "encargo":
        eid = mod_encargo.nuevo_id()
        con_modo = {"modo": modo, "extra": {"encargo": eid, "plazo": plazo, "responder_a": hilo}}
    elif modo != "pedido":
        con_modo = {"modo": modo}
    r = mod_bus.enviar(ctx.config, nombre, texto.strip(), de=remitente(ctx, de), tipo=tipo, saltos=saltos, retener=retener,
                       **con_modo)
    if hilo and not retener:
        _anotar_envio(ctx.config, hilo)
    if eid:
        # la máquina donde vive el hilo ahora, que es donde se creará el encargo: si el hilo se muda después o su
        # estado se borra del bus, la nota sigue sabiendo dónde buscarlo
        donde = mod_bus.maquina_de(ctx.config, nombre) if mod_bus.hay_bus(ctx.config) else ""
        try:
            mod_encargo.anotar_enviado(ctx.config, eid, para=nombre, maquina=donde, texto=texto.strip(), plazo=plazo,
                                       de=remitente(ctx, de),
                                       retenido=str(r.get("motivo") or "retenido") if r.get("estado") == "retenido" else "")
        except OSError:
            pass  # sin la nota, se lo busca en la máquina donde vive su hilo
        r = {**r, "encargo": eid, "direccion": f"encargo:{eid}"}
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
    # con su modo y lo suyo (el id de su encargo, su plazo): el encargo se crea cuando llega
    con_modo = {}
    if m.get("modo") and m["modo"] != "pedido":
        con_modo = {"modo": m["modo"], "extra": {k: m[k] for k in ("encargo", "plazo", "responder_a") if m.get(k)}}
    r = mod_bus.enviar(ctx.config, m["para"], m["texto"], de=m["de"], tipo=m.get("tipo") or "mensaje", mid=m["id"],
                       **con_modo)
    if m.get("encargo"):
        from telar import encargo as mod_encargo

        try:
            mod_encargo.soltado(ctx.config, str(m["encargo"]))
        except (OSError, mod_encargo.ErrorDeEncargo):
            pass  # la nota es de la máquina de quien lo mandó: si no está aquí, allá seguirá diciendo retenido
    return r


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
