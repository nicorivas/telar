"""Seguir aquí un hilo cuya máquina está apagada, desde la copia de aquí (docs/propuestas/mudanza-de-hilos.md, la
etapa 4).

Sin réplica continua (decisión 1 del 24-nov-2026), con la máquina dueña de un hilo apagada no hay una copia al día de su
conversación en ninguna parte: solo la que quedó en cada máquina la última vez que el hilo vivió en ella. «Seguir aquí»
retoma esa copia, diciendo antes lo que falta:

- **Solo donde hay copia y solo con la dueña apagada.** La copia es el `.jsonl` de la conversación que dice su registro
  (`rutas.conversacion`). Apagada es que su foto ya no está vigente (telar.alcance, con el nodo de aquí al día) y que su
  nodo no contesta; con ella en línea, lo que corresponde es «traer aquí», que lo trae entero.
- **Con aviso de lo que falta.** La foto de cada máquina lleva el largo de la conversación de cada hilo suyo y cuándo
  creció, sin nada de lo que dice (telar.espejo, `conv_bytes` y `conv_crecio`). El aviso dice de cuándo es la copia de
  aquí y cuánto pesaba la de allá la última vez que se la vio: el agente no va a recordar lo de después.
- **Lo toma con la época que leyó** (telar.dueno.seguir: `tomado_de`, `hasta` = el largo de la copia de aquí) y lo abre
  retomándola (telar.mudanza.abrir_tomado). Si la dueña volvió y escribió entre medio, no lo toma.

Cuando la dueña vuelve, **cede sola** (decisión 3): su nodo ve que el registro de un hilo abierto allí, con su misma
conversación, es de otra máquina (`Nodo.ceder_seguidos`). Cierra a su agente, deja aparte su copia si creció después
de la con que se siguió (`<sid>.de-<máquina>-<fecha>.jsonl.bak`: se puede leer, no seguir) y lo avisa en la franja de la
página (un aviso de archivo, telar.avisos, con un informe de lo que pasó). Su ventana pasa a mirar la de la otra como
cualquier hilo de allá.

    revisar(ctx, hilo) -> dict        si se puede seguir aquí, y el aviso de lo que falta
    seguir(ctx, hilo) -> dict         tomarlo y abrirlo
    ceder_aqui(ctx, hilo, sid, reg)   lo que hace la que vuelve
    refrescar_aviso(config)           el aviso de lo que se cedió al volver, para la franja
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

#: cuánto se espera a que conteste el nodo de la dueña antes de darla por apagada (además de su foto vieja)
ESPERA = 4
#: cuánto se avisa en la franja lo que se cedió al volver (segundos)
AVISO_DURA = 7 * 24 * 3600
#: cuánto se espera, después de cerrar al agente que cede, a que su conversación deje de crecer
CALMA = 2.0
CALMA_TOPE = 12.0


def _iso(t: float | None) -> str:
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds") if t else ""


def _mb(n: int | None) -> str:
    return "?" if n is None else f"{n / 1e6:.1f} MB".replace(".", ",")


def _cuando(iso: str) -> str:
    """«el 23-nov a las 07:14», corto, de una fecha ISO; "" si no se entiende."""
    from telar import alcance

    try:
        return alcance.desde_texto(datetime.fromisoformat(iso).timestamp())
    except (TypeError, ValueError):
        return ""


def copia_aqui(sid: str) -> dict | None:
    """La copia de esa conversación en esta máquina: {ruta, bytes, fecha, crecio}; None si no hay."""
    from telar import rutas

    ruta = rutas.conversacion(sid) if sid else None
    try:
        st = ruta.stat() if ruta is not None else None
    except OSError:
        st = None
    if st is None:
        return None
    return {"ruta": str(ruta), "bytes": int(st.st_size), "fecha": _iso(st.st_mtime), "crecio": st.st_mtime}


def visto_alla(config, maquina: str, hilo: str) -> dict:
    """Lo que dijo de ese hilo la última foto de `maquina`: {visto (cuándo llegó la foto), en_linea, bytes, crecio,
    en_la_foto}. {} si no hay foto suya."""
    from telar import espejo

    try:
        foto = next((f for f in espejo.leer_todos(config) if f.get("nombre") == maquina and not f.get("error")), None)
    except Exception:  # noqa: BLE001 - sin poder leer las fotos, no se sabe
        foto = None
    if foto is None:
        return {}
    h = next((x for x in foto.get("hilos") or [] if isinstance(x, dict) and x.get("nombre") == hilo), None)
    bytes_ = (h or {}).get("conv_bytes")
    return {"visto": _iso(foto.get("recibido")), "en_linea": bool(foto.get("en_linea")), "en_la_foto": h is not None,
            "bytes": bytes_ if isinstance(bytes_, int) else None, "crecio": str((h or {}).get("conv_crecio") or "")}


def aviso(hilo: str, maquina: str, aqui: dict, alla: dict, desde: str) -> str:
    """Lo que se le dice a la persona antes de seguirlo aquí: de cuándo es la copia de aquí y cuánto falta."""
    partes = [f"Aquí está como quedó {_cuando(aqui['fecha']) or aqui['fecha']} ({_mb(aqui['bytes'])})."]
    if alla.get("bytes") is not None:
        visto = f"la última vez que se lo vio ({_cuando(alla.get('visto', '')) or desde})"
        crecio = f", y creció por última vez {_cuando(alla['crecio'])}" if alla.get("crecio") else ""
        if alla["bytes"] <= aqui["bytes"]:
            partes.append(f"En {maquina}, {visto}, pesaba {_mb(alla['bytes'])}{crecio}: no debería faltar nada.")
        else:
            partes.append(f"En {maquina}, {visto}, pesaba {_mb(alla['bytes'])}{crecio}: faltan unos "
                          f"{_mb(alla['bytes'] - aqui['bytes'])}, y el agente no va a recordar lo de después.")
    else:
        partes.append(f"De {maquina} no se sabe cuánto pesaba (su última foto no lo dice): el agente no va a recordar lo "
                      f"que hizo allá después de esa fecha.")
    partes.append(f"Cuando {maquina} vuelva, cede sola: lo que haya escrito allá después queda aparte, y se avisa.")
    return " ".join(partes)


def revisar(ctx, hilo: str, *, preguntar: bool = True) -> dict:
    """Si `hilo` se puede seguir aquí, solo leyendo: {ok, hilo, puede, por_que_no, aviso, dueno, epoca, conversacion,
    aqui: {bytes, fecha} | None, alla: {visto, en_linea, bytes, crecio, en_la_foto} | None}. Con `preguntar`, además le
    pregunta al nodo de la dueña (unos segundos): si contesta, está en línea aunque su foto se haya atrasado."""
    from telar import alcance, dueno
    from telar import bus as mod_bus

    config = ctx.config
    r: dict = {"ok": True, "hilo": hilo, "puede": False, "por_que_no": "", "aviso": "", "dueno": "", "epoca": 0,
               "conversacion": "", "aqui": None, "alla": None}

    def no(texto: str) -> dict:
        r["por_que_no"] = texto
        return r

    if not mod_bus.hay_bus(config):
        return no("sin bus no hay un dueño que compartir: «seguir aquí» es entre máquinas del bus")
    yo = mod_bus.maquina(config)
    reg = dueno.registro(config, hilo)
    if not reg:
        return no(f"el bus no sabe de «{hilo}»")
    m = dueno.de(reg)
    r.update(dueno=m, epoca=dueno.epoca(reg), conversacion=str(reg.get("conversacion") or ""))
    if m == yo:
        return no(f"«{hilo}» ya es de aquí: retomarlo lo abre")
    if reg.get("cede") or reg.get("mudanza"):
        return no(f"«{hilo}» está en medio de un traspaso: espera a que termine")
    if not r["conversacion"]:
        return no(f"el registro de «{hilo}» no dice cuál es su conversación: no se sabe qué copia retomar")
    aqui = copia_aqui(r["conversacion"])
    alla = visto_alla(config, m, hilo)
    r["aqui"] = {k: aqui[k] for k in ("bytes", "fecha")} if aqui else None
    r["alla"] = alla or None
    a = alcance.de(config, m)
    if not a.fuera:
        if not a.conocida:
            return no(f"no se sabe si {m} está apagada (su foto no llega aquí, o el nodo de aquí no está al día): "
                      f"«seguir aquí» es solo con ella apagada")
        return no(f"{m} está en línea: «traer aquí» lo trae entero")
    if aqui is None:
        return no(f"{a.frase()}, y aquí no hay copia de su conversación: vuelve cuando vuelva {m}")
    if preguntar and mod_bus.pedir(config, m, "mudanza-progreso", {"hilo": hilo}, espera=ESPERA).get("ok"):
        return no(f"{m} contesta, aunque su foto se atrasó: «traer aquí» lo trae entero")
    r["puede"] = True
    r["aviso"] = aviso(hilo, m, aqui, alla, a.desde())
    return r


def _al_lugar(ctx, sid: str, relativa: str) -> Path | None:
    """La copia, donde la busca el agente que arranca aquí en la carpeta del hilo: si está en otra carpeta de proyecto,
    se copia (con su carpeta `<sid>/`), sin mover la de origen. La ruta, o None si no hay copia."""
    from telar import mudanza, rutas

    inicio, _, _ = mudanza.inicio(ctx, relativa)
    destino = rutas.proyecto(inicio) / f"{sid}.jsonl"
    if destino.is_file():
        return destino
    origen = rutas.conversacion(sid)
    if origen is None:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    carpeta = origen.parent / sid
    if carpeta.is_dir():
        shutil.copytree(carpeta, destino.parent / sid, dirs_exist_ok=True)
    return destino


def seguir(ctx, hilo: str) -> dict:
    """Seguir `hilo` aquí desde la copia de aquí, con su dueña apagada: lo revisa de nuevo, lo toma con la época que leyó
    (telar.dueno.seguir) y lo abre. {ok, hilo, de, epoca, hasta, hecho, aviso} o {ok: false, error} (con `tomado` si es
    de aquí pero no se abrió: lo abre el nodo)."""
    from telar import bus as mod_bus
    from telar import dueno, mudanza

    config = ctx.config
    r = revisar(ctx, hilo)
    if not r["puede"]:
        return {**r, "ok": False, "error": r["por_que_no"]}
    sid, m, e = r["conversacion"], r["dueno"], r["epoca"]
    reg = dueno.registro(config, hilo)
    copia = _al_lugar(ctx, sid, str(reg.get("vinculo") or ""))
    if copia is None:
        return {**r, "ok": False, "error": "la copia de aquí ya no está"}
    hasta = copia.stat().st_size
    yo = mod_bus.maquina(config)
    clave = dueno.clave(config, hilo)
    tomado = dueno.con_almacen(config, lambda kv: dueno.seguir(kv, clave, yo=yo, de_=m, epoca_=e, hasta=hasta))
    if not tomado:
        return {**r, "ok": False, "error": f"no lo tomé: el registro cambió (¿volvió {m}, o otra lo tomó antes?). "
                                            f"Aquí no se abrió nada"}
    abierto, texto = mudanza.abrir_tomado(ctx, hilo, dueno.registro(config, hilo))
    if not abierto:
        return {**r, "ok": False, "tomado": True,
                "error": f"«{hilo}» ya es de aquí, pero no se abrió: {texto} (el nodo lo intenta de nuevo)"}
    return {**r, "ok": True, "de": m, "epoca": e + 1, "hasta": hasta,
            "hecho": f"«{hilo}» sigue aquí desde la copia de {_cuando(r['aqui']['fecha']) or r['aqui']['fecha']} "
                     f"({_mb(hasta)}); cuando {m} vuelva, cede sola"}


# ── la que vuelve ──────────────────────────────────────────────────────────────

def _cesiones(config) -> Path:
    return Path(config.estado) / "seguidos.json"


def _leer_cesiones(config) -> list[dict]:
    try:
        d = json.loads(_cesiones(config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []


def _escribir(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(f".{ruta.name}.{os.getpid()}")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, ruta)


def _calmar(ruta: Path) -> None:
    """Espera a que la conversación deje de crecer (el agente que se cerró escribe lo suyo al salir), hasta un tope."""
    fin, antes, quieto = time.monotonic() + CALMA_TOPE, -1, time.monotonic()
    while time.monotonic() < fin:
        try:
            ahora = ruta.stat().st_size
        except OSError:
            return
        if ahora != antes:
            antes, quieto = ahora, time.monotonic()
        elif time.monotonic() - quieto >= CALMA:
            return
        time.sleep(0.25)


def ceder_aqui(ctx, hilo: str, sid: str, reg: dict) -> str:
    """Lo que hace la máquina que vuelve con un hilo suyo que otra siguió mientras estaba apagada (o que quedó abierto
    aquí y el registro dice de otra, con su misma conversación): cierra a su agente, deja aparte su copia si creció
    después de la con que se siguió, lo anota para el aviso de la franja y dice qué hizo, en una línea."""
    from telar import bus as mod_bus
    from telar import dueno, rutas
    from telar.ordenes import _comun

    config = ctx.config
    yo = mod_bus.maquina(config)
    otra = dueno.de(reg)
    tel = _comun.tejer(ctx, con_ficha=False)
    est = tel.estado
    cerrada = ""
    if tel.mux is not None and hilo not in est.remotos():
        ids = [h.id for h in tel.mux.hilos() if h.nombre == hilo]
        if len(ids) == 1:
            try:
                tel.mux.cerrar(ids[0])
                cerrada = ids[0]
            except Exception:  # noqa: BLE001 - si no se cierra, se dice
                pass
    est.olvidar_dormido(hilo)
    ruta = rutas.conversacion(sid)
    hasta = reg.get("hasta")
    aparte = ""
    if ruta is not None:
        _calmar(ruta)
    if ruta is not None and reg.get("tomado_de") == yo and isinstance(hasta, int):
        try:
            largo = ruta.stat().st_size
        except OSError:
            largo = hasta
        if largo != hasta:
            destino = ruta.with_name(f"{sid}.de-{yo}-{datetime.now():%Y-%m-%d-%H%M}.jsonl.bak")
            os.replace(ruta, destino)
            aparte = str(destino)
    seguido = reg.get("seguido")
    cesion = {"id": uuid.uuid4().hex[:12], "hilo": hilo, "a": otra, "cuando": time.time(), "aparte": aparte,
              "tomado_de": str(reg.get("tomado_de") or ""), "hasta": hasta if isinstance(hasta, int) else None,
              "seguido": float(seguido) if isinstance(seguido, (int, float)) else None, "ventana_cerrada": bool(cerrada)}
    cesiones = [c for c in _leer_cesiones(config) if time.time() - float(c.get("cuando") or 0) < AVISO_DURA]
    _escribir(_cesiones(config), json.dumps([*cesiones, cesion], ensure_ascii=False, indent=1))
    refrescar_aviso(config)
    que = "cerré su agente" if cerrada else "no encontré una sola ventana suya que cerrar"
    if aparte:
        que += f"; lo que escribió aquí después de la copia con que se siguió quedó aparte en {aparte}"
    return f"«{hilo}» siguió en {otra} mientras esta máquina no estaba: {que}"


def aviso_archivo(config) -> Path:
    """El archivo de aviso de lo que se cedió al volver (telar.avisos lo lee sin que se declare)."""
    return Path(config.estado) / "avisos" / "seguidos.json"


def refrescar_aviso(config) -> None:
    """El aviso para la franja de la página, con lo que se cedió al volver en la última semana: una línea, un informe y
    un id por cesión (dado por visto, no sale hasta que haya otra). Lo refresca el nodo cada 30 s; sin nada, `ok`."""
    cesiones = [c for c in _leer_cesiones(config) if time.time() - float(c.get("cuando") or 0) < AVISO_DURA]
    ruta = aviso_archivo(config)
    if not cesiones:
        if ruta.exists():
            _escribir(ruta, json.dumps({"nivel": "ok", "linea": "", "fecha": _iso(time.time())}))
        return
    ultima = cesiones[-1]
    linea = (f"«{ultima['hilo']}» siguió en {ultima['a']} mientras esta máquina no estaba"
             + (": lo de aquí quedó aparte" if ultima.get("aparte") else "")
             + (f" (y {len(cesiones) - 1} más)" if len(cesiones) > 1 else ""))
    informe = ruta.with_name("seguidos.md")
    lineas = ["# Hilos que siguieron en otra máquina mientras esta no estaba", "",
              "Cada uno se siguió en otra máquina desde la copia que tenía allá, y al volver esta cedió sola: cerró a su "
              "agente y, si había escrito algo después de esa copia, lo dejó aparte. Lo de aparte se puede leer, no "
              "seguir.", ""]
    for c in reversed(cesiones):
        lineas.append(f"- **{c['hilo']}**: sigue en {c['a']} desde {_cuando(_iso(c.get('seguido'))) or '?'}; esta "
                      f"cedió {_cuando(_iso(c.get('cuando')))}.")
        if c.get("aparte"):
            lineas.append(f"  Lo de aquí, aparte: `{c['aparte']}`.")
        elif c.get("tomado_de"):
            lineas.append("  Aquí no había nada después de la copia con que se siguió.")
    _escribir(informe, "\n".join(lineas) + "\n")
    _escribir(ruta, json.dumps({"nivel": "aviso", "linea": linea, "fecha": _iso(time.time()), "informe": str(informe),
                                "problemas": [c["id"] for c in cesiones]}, ensure_ascii=False))
