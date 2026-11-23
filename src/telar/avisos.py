"""Los avisos que vienen de un archivo: un programa (un agente, un chequeo que corre solo) deja en un JSON cómo está
algo, y la franja de avisos de la página lo dice mientras no esté bien.

    {"nivel": "ok|aviso|mal", "linea": "el disco está al 92%", "fecha": "2026-11-18T15:30:00",
     "informe": "/ruta/al/informe.md", "sugerencias": 3, "problemas": ["disco", "swap"]}

Se declaran en la configuración, una tabla por fuente, con el archivo y, si vive en otra máquina del bus, cuál:

    [avisos.equipo]
    archivo = "~/.local/state/chequeo/aviso.json"
    en = "laptop"             # opcional: sin ella, esta máquina

`de_todas` los lee (los de aquí del disco; los de otra máquina, a su nodo por el bus, `avisos-archivo`) y devuelve
solo lo que hay que decir: `aviso` o `mal`, de la última hora. Un archivo que no está, que no se entiende, que dice
`ok` o que es viejo (`VIEJO`: el programa dejó de correr) no dice nada. La página los pone en la franja
(`pagina/src/web/avisos-archivos.ts`), y un clic abre el informe en el visor de documentos (por eso `informes` dice
qué informes puede leer la página: los `.md` que nombran los archivos declarados aquí).

Una máquina solo entrega los archivos que su propia configuración declara como suyos: pedir uno que no declara es
pedir nada.

**Lo visto.** La persona da un aviso por visto (abrió su informe, o su ✓ en la franja: `marcar_visto`) y deja de salir
mientras sea «el mismo aviso»: con `problemas` (ids estables de lo que está mal), mientras los de ahora sean los vistos
o menos y el nivel no suba; sin `problemas`, mientras el nivel no suba. Sale de nuevo con un problema nuevo, con un
`aviso` que pasa a `mal`, o si el archivo dijo `ok` entre medio (eso olvida lo visto: lo mira quien lee el archivo, y el
nodo cada 30 s, `olvidar_los_ok`). Lo visto se guarda en la máquina donde vive el archivo (`<estado>/avisos-vistos.json`,
por la ruta del archivo), así vale igual en el laptop y en el teléfono; el de otra máquina se marca allá por el bus
(`avisos-visto`), como lo visto de las pasadas (telar.pasadas). `GET /avisos` dice de cada uno si está `visto`.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

#: lo que puede decir `nivel`; `ok` no se avisa
NIVELES = ("ok", "aviso", "mal")
#: pasado esto (segundos) desde su `fecha`, el archivo ya no dice nada: el programa que lo escribe dejó de correr
VIEJO = 3600
#: cuánto se espera a otra máquina (segundos)
ESPERA = 10
#: lo más largo que se lee de un archivo de aviso: es una línea, no un informe
TOPE = 64 * 1024
#: lo visto de cada archivo, en el estado de la máquina donde vive: {ruta: {nivel, problemas, cuando}}
VISTOS = "avisos-vistos.json"
#: cuántos problemas se leen de un archivo, y lo más largo de cada id
PROBLEMAS = 100
LARGO_PROBLEMA = 200


def _maquina(config) -> str:
    from telar import bus as mod_bus

    return mod_bus.maquina(config) if mod_bus.hay_bus(config) else ""


def _de_aqui(config, fuente) -> bool:
    return not fuente.en or fuente.en == _maquina(config)


def _momento(valor, ruta: Path) -> float | None:
    """La `fecha` del archivo (ISO, con zona o sin ella, como hora local), o si no dice, cuándo se escribió."""
    if isinstance(valor, str) and valor.strip():
        try:
            return datetime.fromisoformat(valor.strip().replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    try:
        return ruta.stat().st_mtime
    except OSError:
        return None


def _datos(ruta: Path | str) -> dict | None:
    """El JSON de un archivo de aviso, tal cual (None si no está o no es un objeto)."""
    try:
        with open(Path(ruta).expanduser(), "rb") as f:
            datos = json.loads(f.read(TOPE).decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def _problemas(valor) -> list[str] | None:
    """Los ids de `problemas`, sin repetir y en orden; None si el archivo no trae la lista (o no es una lista)."""
    if not isinstance(valor, list):
        return None
    salida: list[str] = []
    for x in valor:
        if isinstance(x, (str, int)) and not isinstance(x, bool):
            x = str(x).strip()[:LARGO_PROBLEMA]
            if x and x not in salida:
                salida.append(x)
    return salida[:PROBLEMAS]


def leer_archivo(ruta: Path | str, ahora: float | None = None) -> dict | None:
    """Lo que dice un archivo de aviso, si hay que decirlo: {nivel, linea, fecha, informe, sugerencias, problemas}. None
    si no está, no se entiende, dice `ok` o es de hace más de `VIEJO`. `problemas`, None si no trae la lista."""
    ruta = Path(ruta).expanduser()
    datos = _datos(ruta)
    if datos is None or datos.get("nivel") not in NIVELES or datos["nivel"] == "ok":
        return None
    cuando = _momento(datos.get("fecha"), ruta)
    if cuando is None or (ahora if ahora is not None else time.time()) - cuando > VIEJO:
        return None
    linea = " ".join(str(datos.get("linea") or "").split())[:300]
    if not linea:
        return None
    informe = str(datos.get("informe") or "").strip()
    sugerencias = datos.get("sugerencias")
    return {"nivel": datos["nivel"], "linea": linea, "fecha": datetime.fromtimestamp(cuando).isoformat(timespec="seconds"),
            "informe": informe, "sugerencias": sugerencias if isinstance(sugerencias, int) and sugerencias >= 0 else None,
            "problemas": _problemas(datos.get("problemas"))}


# ── lo visto ──────────────────────────────────────────────────────────────────

def _llave(archivo: str) -> str:
    """Cómo se guarda lo visto de un archivo: su ruta, con ~ resuelto (la misma se declare como se declare)."""
    return str(Path(archivo).expanduser())


def _ruta_vistos(config) -> Path:
    return Path(config.estado) / VISTOS


def _leer_vistos(config) -> dict:
    try:
        datos = json.loads(_ruta_vistos(config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _cambiar_vistos(config, cambio) -> dict:
    """Leer lo visto, cambiarlo (`cambio` recibe el dict y lo cambia ahí) y escribirlo entero, con candado: el nodo y la
    API lo tocan a la vez. Devuelve cómo quedó."""
    from telar.estado import _candado
    from telar.pasadas import _escribir

    ruta = _ruta_vistos(config)
    with _candado(ruta.with_name(f".{VISTOS}.lock")):
        vistos = _leer_vistos(config)
        antes = json.dumps(vistos, sort_keys=True)
        cambio(vistos)
        if json.dumps(vistos, sort_keys=True) != antes:
            _escribir(ruta, vistos)
    return vistos


def es_el_mismo(visto: dict | None, aviso: dict) -> bool:
    """Si `aviso` es el mismo que se vio: el nivel no subió y, si trae `problemas`, son los vistos o menos (si lo visto
    no tenía la lista, no se sabe: no es el mismo)."""
    if not isinstance(visto, dict) or visto.get("nivel") not in NIVELES:
        return False
    if NIVELES.index(aviso.get("nivel", "mal")) > NIVELES.index(visto["nivel"]):
        return False
    actuales = aviso.get("problemas")
    if actuales is None:
        return True
    vistos = visto.get("problemas")
    return isinstance(vistos, list) and set(actuales) <= set(vistos)


def _locales_declarados(config):
    return [f for f in getattr(config, "avisos", ()) if _de_aqui(config, f)]


def _declarado_aqui(config, archivo: str):
    """La fuente de aquí que declara `archivo` (como se declaró o con ~ resuelto), o None."""
    return next((f for f in _locales_declarados(config) if archivo in (f.archivo, _llave(f.archivo))), None)


def olvidar_los_ok(config) -> list[str]:
    """Olvidar lo visto de los archivos de aquí que dicen `ok`: lo que vuelva a estar mal sale de nuevo. Lo corre el nodo
    cada 30 s (y `locales`, al leer). Devuelve las rutas olvidadas."""
    vistos = _leer_vistos(config)
    ok = [_llave(f.archivo) for f in _locales_declarados(config)
          if _llave(f.archivo) in vistos and (_datos(f.archivo) or {}).get("nivel") == "ok"]
    if ok:
        _cambiar_vistos(config, lambda v: [v.pop(k, None) for k in ok])
    return ok


def marcar_visto_local(config, archivo: str, nivel: str = "", problemas: list | None = None) -> dict:
    """Dar por visto el aviso de un archivo declarado aquí. Con `nivel` (y `problemas`), lo que la persona vio (lo que
    mostró la página: si el archivo cambió después, lo nuevo no queda visto); sin él, lo que dice el archivo ahora.
    Siempre `{"ok": …}`, con `visto`."""
    fuente = _declarado_aqui(config, str(archivo))
    if fuente is None:
        return {"ok": False, "error": f"«{str(archivo)[:80]}» no es un archivo de aviso de esta máquina"}
    if nivel:
        if nivel not in ("aviso", "mal"):
            return {"ok": False, "error": f"nivel «{str(nivel)[:20]}»: se da por visto un aviso o un mal"}
        visto = {"nivel": nivel, "problemas": _problemas(problemas)}
    else:
        d = leer_archivo(fuente.archivo)
        if d is None:
            return {"ok": False, "error": f"{fuente.clave} no dice nada ahora: no hay qué dar por visto"}
        visto = {"nivel": d["nivel"], "problemas": d["problemas"]}
    visto["cuando"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _cambiar_vistos(config, lambda v: v.update({_llave(fuente.archivo): visto}))
    return {"ok": True, "clave": fuente.clave, "visto": visto}


def visto_para_otra(config, pedido: dict) -> dict:
    """Lo que responde el nodo a `avisos-visto`: dar por visto un archivo que esta máquina declara."""
    problemas = pedido.get("problemas")
    return marcar_visto_local(config, str(pedido.get("archivo") or ""), str(pedido.get("nivel") or ""),
                              problemas if isinstance(problemas, list) else None)


def marcar_visto(config, clave: str, nivel: str = "", problemas: list | None = None) -> dict:
    """Dar por visto el aviso de la fuente `clave`, en la máquina donde vive su archivo (por el bus si es otra)."""
    from telar import bus as mod_bus

    fuente = next((f for f in getattr(config, "avisos", ()) if f.clave == clave), None)
    if fuente is None:
        return {"ok": False, "error": f"no hay un aviso «{clave[:40]}» en la configuración ([avisos.<clave>])"}
    if _de_aqui(config, fuente):
        return {**marcar_visto_local(config, fuente.archivo, nivel, problemas), "desde": "aquí"}
    if not mod_bus.hay_bus(config):
        return {"ok": False, "error": f"{clave} vive en {fuente.en} y no hay bus"}
    try:
        r = mod_bus.pedir(config, fuente.en, "avisos-visto",
                          {"archivo": fuente.archivo, "nivel": nivel, "problemas": problemas}, espera=ESPERA)
    except Exception as e:  # noqa: BLE001 - se dice, no se cae
        return {"ok": False, "error": str(e)}
    if not isinstance(r, dict) or not r.get("ok"):
        return {"ok": False, "error": str((r or {}).get("error") or f"{fuente.en} no contestó")}
    return {**r, "clave": clave, "desde": fuente.en}


def locales(config, archivos: list[str] | None = None) -> list[dict]:
    """Los avisos de las fuentes que viven aquí (sin `en`, o con esta máquina), cada uno con su `archivo` como se
    declaró y si está `visto`. Con `archivos`, solo esos (lo que pide otra máquina): uno que esta configuración no
    declara como suyo no se lee. Lo visto de un archivo que dice `ok` se olvida."""
    salida = []
    olvidar_los_ok(config)
    vistos = _leer_vistos(config)
    for f in _locales_declarados(config):
        if archivos is not None and f.archivo not in archivos and _llave(f.archivo) not in archivos:
            continue
        d = leer_archivo(f.archivo)
        if d:
            salida.append({"archivo": f.archivo, **d, "visto": es_el_mismo(vistos.get(_llave(f.archivo)), d)})
    return salida


def para_otra(config, pedido: dict) -> dict:
    """Lo que responde el nodo a `avisos-archivo`: los avisos de los archivos pedidos que esta máquina declara."""
    archivos = [str(a) for a in pedido.get("archivos") or [] if isinstance(a, str)]
    return {"ok": True, "avisos": locales(config, archivos)}


def de_todas(config) -> dict:
    """Los avisos que hay que decir, de todas las fuentes declaradas: {avisos: [{clave, maquina, nivel, linea, fecha,
    informe, sugerencias, problemas, visto}], fallas: {clave: motivo}} (una máquina que no contestó: lo suyo no se dice)."""
    from telar import bus as mod_bus

    avisos, fallas = [], {}
    fuentes = list(getattr(config, "avisos", ()))
    aqui = {a["archivo"]: a for a in locales(config)}
    otras: dict[str, list] = {}
    for f in fuentes:
        if _de_aqui(config, f):
            if f.archivo in aqui:
                avisos.append({"clave": f.clave, "maquina": "", **_sin_archivo(aqui[f.archivo])})
        else:
            otras.setdefault(f.en, []).append(f)
    for maquina, lista in otras.items():
        if not mod_bus.hay_bus(config):
            fallas.update({f.clave: f"vive en {maquina} y no hay bus" for f in lista})
            continue
        try:
            r = mod_bus.pedir(config, maquina, "avisos-archivo", {"archivos": [f.archivo for f in lista]}, espera=ESPERA)
        except Exception as e:  # noqa: BLE001 - una máquina que no contesta no tumba las demás
            r = {"ok": False, "error": str(e)}
        if not r.get("ok"):
            fallas.update({f.clave: str(r.get("error") or f"{maquina} no contestó") for f in lista})
            continue
        suyos = {a.get("archivo"): a for a in r.get("avisos") or [] if isinstance(a, dict)}
        for f in lista:
            if f.archivo in suyos:
                avisos.append({"clave": f.clave, "maquina": maquina, **_sin_archivo(suyos[f.archivo])})
    return {"avisos": avisos, "fallas": fallas}


def _sin_archivo(a: dict) -> dict:
    return {**{k: a.get(k) for k in ("nivel", "linea", "fecha", "informe", "sugerencias", "problemas")},
            "visto": bool(a.get("visto"))}


def informes(config) -> set[Path]:
    """Los informes que nombran los archivos de aviso declarados aquí (solo `.md`, y que existan): la página los
    puede abrir en su visor aunque estén fuera de la raíz, como un archivo que declara una app."""
    salida = set()
    for f in _locales_declarados(config):
        datos = _datos(f.archivo)
        informe = str(datos.get("informe") or "").strip() if datos else ""
        if informe.endswith(".md"):
            p = Path(informe).expanduser().resolve()
            if p.is_file():
                salida.add(p)
    return salida
