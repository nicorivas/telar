"""Las ventanas que un módulo pide abrir en la página cuando ocurre algo (`[ventanas]` de su modulo.toml): la de un chat
de foco de WhatsApp cuando le llega un mensaje, para responder o aplazar sin ir a su pestaña.

    from telar.servicios import ventanas
    ventanas.listar(ctx, "trabajo")                     # las que esperan con ese mundo puesto ("" ambos), y el silencio
    ventanas.accion(ctx, "whatsapp", "foco", {...})     # lo que corre un botón: una consulta del módulo que la pidió
    ventanas.silenciar(ctx, True)                       # no molestar, en esta máquina

El módulo dice qué ventanas quiere abrir **ahora**: una consulta suya (`[ventanas] consulta`) que recibe el mundo puesto
en la página (`{"mundo": …}`, "" con ambos) y da `{"ventanas": […]}`, cada una con lo que muestra (un título, sus
líneas, una caja para responder) y sus botones, que corren otras consultas suyas (`[ventanas] acciones`): nada más que
eso puede pedir la página por este camino. El estado (qué espera, qué se respondió o se aplazó) es del módulo, no de una
pestaña: lo que se hace en una página cierra la ventana en las demás, aquí y en otras máquinas, cuando vuelven a
preguntar. La forma, entera, en docs/modulos.md («Sus ventanas»).

**Los mundos.** Lo de otro mundo no llega a la página: el módulo no lo da (no sabe más que el mundo que se le dice) y,
por si acaso, aquí se descarta lo que diga ser de otro. Lo sin mundo ("") sale en todos, como lo sin clasificar en el
resto de telar.

**El silencio.** «No molestar», a mano, vale en esta máquina (`<estado>/ventanas/silencio.json`) hasta que se apague:
mientras, la página no abre nada y pide solo cuántas esperan (`solo_cuantas`), sin su contenido. El de las reuniones
lo pone la página sola, con su calendario. Lo que llegó en silencio sale al terminar: sigue esperando en el módulo.

Cada cambio (un botón, el silencio) toca `<estado>/ventanas/`: la página lo sabe por `/eventos` («ventanas») y las
otras pestañas de esta máquina vuelven a preguntar al tiro. Lo leído se guarda unos segundos (VIGENCIA): varias
pestañas abiertas no corren la consulta del módulo cada una.
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoTarde
from pathlib import Path

from telar.servicios import ErrorDeServicio

#: cuánto vale lo leído de los módulos: varias pestañas preguntando a la vez leen lo mismo
VIGENCIA = 3.0
#: cuánto se espera a un módulo (el de otra máquina va por el bus)
ESPERA = 20
#: lo que cabe en una ventana: más se recorta (lo escribe un módulo, y lo que dicen sus líneas es de otras personas)
TOPES = {"titulo": 200, "ayuda": 300, "de": 120, "texto": 4000, "marca": 80, "boton": 40, "lineas": 80, "acciones": 12,
         "borradores": 5}
#: dónde va un botón: en el pie (con su tecla) o en la cabecera, junto al título (lo que lleva a otra parte)
LUGARES = ("pie", "cabecera")
#: los íconos que una ventana puede pedir junto a su título
ICONOS = ("persona", "grupo", "aviso", "")
#: el ícono de un botón (`icono`): un nombre de los de la página (pagina/src/web/iconos.ts: «enviar», «aplazar»,
#: «externo»); la página dice la palabra si no lo conoce
ICONO_BOTON = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}")

_cache: dict[tuple[str, bool], tuple[float, dict]] = {}
_candado = threading.Lock()


def carpeta(ctx) -> Path:
    return Path(ctx.config.estado) / "ventanas"


def _tocar(ctx) -> None:
    """Que la página sepa que algo cambió (`/eventos` mira esta carpeta) y que lo guardado ya no vale."""
    with _candado:
        _cache.clear()
    d = carpeta(ctx)
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / "cambio").write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def de_ventanas(ctx) -> list:
    """Los módulos que piden ventanas."""
    return [m for m in getattr(ctx.config, "modulos", ()) if getattr(m, "ventanas", None)]


# ── el silencio ─────────────────────────────────────────────────────────────────────

def silencio(ctx) -> dict:
    """«No molestar» puesto a mano en esta máquina: `{"a_mano": bool, "desde": iso}`."""
    try:
        d = json.loads((carpeta(ctx) / "silencio.json").read_text(encoding="utf-8"))
        desde = float(d.get("desde") or 0)
    except (OSError, ValueError, TypeError, AttributeError):
        desde = 0
    if not desde:
        return {"a_mano": False, "desde": ""}
    import datetime as dt

    return {"a_mano": True, "desde": dt.datetime.fromtimestamp(desde).astimezone().isoformat(timespec="seconds")}


def silenciar(ctx, si: bool) -> dict:
    ruta = carpeta(ctx) / "silencio.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if si:
        if not silencio(ctx)["a_mano"]:
            tmp = ruta.with_suffix(".tmp")
            tmp.write_text(json.dumps({"desde": time.time()}), encoding="utf-8")
            tmp.replace(ruta)
    else:
        ruta.unlink(missing_ok=True)
    _tocar(ctx)
    return silencio(ctx)


# ── lo que piden los módulos ────────────────────────────────────────────────────────

def _texto(v, tope: int) -> str:
    t = v if isinstance(v, str) else "" if v is None else str(v)
    return t if len(t) <= tope else t[: tope - 1] + "…"


def _llamada(m, d, campo: str) -> dict | None:
    """Una consulta que corre un botón (`{verbo, params}`): solo las que el módulo declaró en `[ventanas]`."""
    if not isinstance(d, dict):
        return None
    verbo = d.get("verbo")
    if not isinstance(verbo, str) or verbo not in (m.ventanas["consulta"], *m.ventanas["acciones"]):
        raise ValueError(f"{campo}: «{verbo}» no es de sus [ventanas] acciones")
    params = d.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError(f"{campo}: los parámetros van en un objeto")
    return {"verbo": verbo, "params": params}


def _ventana(m, v) -> dict:
    """Una ventana como la pidió el módulo, revisada: lo que no se entiende se dice (y la ventana no sale)."""
    if not isinstance(v, dict) or not isinstance(v.get("id"), str) or not v["id"].strip():
        raise ValueError("una ventana sin id")
    lineas = []
    for x in (v.get("lineas") or [])[-TOPES["lineas"]:]:
        if isinstance(x, dict):
            lineas.append({"de": _texto(x.get("de"), TOPES["de"]), "ts": _texto(x.get("ts"), 40),
                           "texto": _texto(x.get("texto"), TOPES["texto"]), "marca": _texto(x.get("marca"), TOPES["marca"]),
                           "nueva": x.get("nueva") is True, "mia": x.get("mia") is True})
    responder = None
    r = v.get("responder")
    if isinstance(r, dict):
        responder = {**_llamada(m, r, "responder"), "campo": _texto(r.get("campo") or "texto", 40),
                     "placeholder": _texto(r.get("placeholder"), TOPES["titulo"]),
                     "largo": max(1, min(int(r.get("largo") or 4000), 20000)),
                     "despues": _llamada(m, r.get("despues"), "responder.despues")}
    # lo que alguien dejó para responder y espera que la persona lo apruebe (el borrador de un agente): aprobarlo, con lo
    # editado, o descartarlo, cada uno una consulta del módulo
    borradores = []
    for i, x in enumerate((v.get("borradores") or [])[: TOPES["borradores"]]):
        if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not x["id"].strip():
            raise ValueError(f"borradores[{i}]: sin id")
        ap = x.get("aprobar")
        aprobar = {**_llamada(m, ap, f"borradores[{i}].aprobar"), "campo": _texto(ap.get("campo") or "texto", 40),
                   "despues": _llamada(m, ap.get("despues"), f"borradores[{i}].aprobar.despues")} if isinstance(ap, dict) else None
        borradores.append({"id": x["id"].strip(), "de": _texto(x.get("de"), TOPES["de"]), "texto": _texto(x.get("texto"), TOPES["texto"]),
                           "motivo": _texto(x.get("motivo"), TOPES["ayuda"]), "sale": _texto(x.get("sale"), 20),
                           "editable": x.get("editable") is True, "aprobar": aprobar,
                           "descartar": _llamada(m, x.get("descartar"), f"borradores[{i}].descartar")})
    acciones = []
    for i, a in enumerate((v.get("acciones") or [])[: TOPES["acciones"]]):
        if not isinstance(a, dict) or not _texto(a.get("texto"), TOPES["boton"]).strip():
            raise ValueError(f"acciones[{i}]: sin texto")
        b = {"texto": _texto(a["texto"], TOPES["boton"]), "tecla": _texto(a.get("tecla"), 4),
             "en": a.get("en") if a.get("en") in LUGARES else "pie", "despues": _llamada(m, a.get("despues"), f"acciones[{i}].despues")}
        # el ícono que va en lugar de la palabra (que pasa a su nombre) y lo poco que va a su lado: lo raro se descarta
        if isinstance(a.get("icono"), str) and ICONO_BOTON.fullmatch(a["icono"]):
            b["icono"] = a["icono"]
            if _texto(a.get("corto"), 12).strip():
                b["corto"] = _texto(a["corto"], 12).strip()
        if isinstance(a.get("abrir"), str) and a["abrir"].strip():
            b.update(abrir=a["abrir"].strip(), item=_texto(a.get("item"), 300))
        elif isinstance(a.get("instruccion"), dict):
            b["instruccion"] = _llamada(m, a["instruccion"], f"acciones[{i}].instruccion")
        else:
            b.update(_llamada(m, a, f"acciones[{i}]") or {})
            if "verbo" not in b:
                raise ValueError(f"acciones[{i}]: ni verbo, ni abrir, ni instruccion")
        acciones.append(b)
    escape, nuevos = v.get("escape"), v.get("nuevos")
    return {"modulo": m.nombre, "id": v["id"].strip(), "version": _texto(v.get("version"), 200),
            "mundo": _texto(v.get("mundo"), 60), "titulo": _texto(v.get("titulo"), TOPES["titulo"]),
            "ayuda": _texto(v.get("ayuda"), TOPES["ayuda"]), "icono": v.get("icono") if v.get("icono") in ICONOS else "",
            "nuevos": nuevos if isinstance(nuevos, int) and not isinstance(nuevos, bool) and nuevos > 0 else 0,
            "desde": _texto(v.get("desde"), 40), "lineas": lineas, "borradores": borradores, "responder": responder, "acciones": acciones,
            "escape": escape if isinstance(escape, int) and not isinstance(escape, bool) and 0 <= escape < len(acciones) else None}


def _de_un_modulo(ctx, m, mundo: str, solo_cuantas: bool) -> dict:
    from telar.servicios import modulos as servicio_modulos

    params = {"mundo": mundo, **({"solo_cuantas": True} if solo_cuantas else {})}
    r = servicio_modulos.consultar(ctx, m.nombre, m.ventanas["consulta"], params)
    salida: dict = {"ventanas": [], "fallas": [], "cuantas": 0}
    for v in [] if solo_cuantas else (r.get("ventanas") or []):
        try:
            x = _ventana(m, v)
        except (ValueError, TypeError) as e:
            salida["fallas"].append({"modulo": m.nombre, "error": f"una ventana que no sirve: {e}"})
            continue
        # lo de otro mundo no llega a la página, aunque el módulo lo mande
        if mundo and x["mundo"] not in ("", mundo):
            continue
        salida["ventanas"].append(x)
    c = r.get("cuantas")
    salida["cuantas"] = c if isinstance(c, int) and not isinstance(c, bool) and c >= 0 else len(salida["ventanas"])
    return salida


def listar(ctx, mundo: str = "", solo_cuantas: bool = False) -> dict:
    """Las ventanas que esperan con ese mundo puesto, de todos los módulos que las piden, y el silencio de esta
    máquina. Un módulo que falla no tumba a los demás: va en `fallas`."""
    mundo = mundo.strip()
    # con «no molestar» a mano, ninguna página recibe su contenido: solo cuántas
    solo_cuantas = solo_cuantas or silencio(ctx)["a_mano"]
    clave = (mundo, solo_cuantas)
    with _candado:
        guardado = _cache.get(clave)
        if guardado and time.monotonic() - guardado[0] < VIGENCIA:
            return {**guardado[1], "silencio": silencio(ctx)}
    modulos = de_ventanas(ctx)
    ventanas, fallas, cuantas = [], [], 0
    if modulos:
        # sin `with`: al salir esperaría al que tarda, y ESPERA es lo más que se le espera a uno
        hilos = ThreadPoolExecutor(max_workers=min(4, len(modulos)))
        try:
            futuros = {m.nombre: hilos.submit(_de_un_modulo, ctx, m, mundo, solo_cuantas) for m in modulos}
            for nombre, f in futuros.items():
                try:
                    r = f.result(timeout=ESPERA)
                except ErrorDeServicio as e:
                    fallas.append({"modulo": nombre, "error": str(e)})
                    continue
                except FuturoTarde:
                    fallas.append({"modulo": nombre, "error": f"no contestó en {ESPERA} s"})
                    continue
                except Exception as e:  # noqa: BLE001 - un módulo que se cae no tumba a los demás
                    fallas.append({"modulo": nombre, "error": f"{type(e).__name__}: {e}"})
                    continue
                ventanas += r["ventanas"]
                fallas += r["fallas"]
                cuantas += r["cuantas"]
        finally:
            hilos.shutdown(wait=False, cancel_futures=True)
    # la que espera hace más, primero
    ventanas.sort(key=lambda v: v.get("desde") or "")
    hecho = {"ventanas": ventanas, "cuantas": cuantas, "fallas": fallas, "modulos": [m.nombre for m in modulos]}
    with _candado:
        _cache[clave] = (time.monotonic(), hecho)
    return {**hecho, "silencio": silencio(ctx)}


def accion(ctx, modulo: str, verbo: str, params: dict) -> dict:
    """Lo que corre un botón de una ventana (o su caja de responder): una consulta del módulo que la pidió, de las que
    declaró en `[ventanas]`. Lo devuelve tal cual."""
    from telar.servicios import modulos as servicio_modulos

    m = next((x for x in de_ventanas(ctx) if x.nombre == modulo), None)
    if m is None:
        raise ErrorDeServicio(f"el módulo «{modulo}» no pide ventanas", 404)
    if verbo not in (m.ventanas["consulta"], *m.ventanas["acciones"]):
        raise ErrorDeServicio(f"«{verbo}» no es de las [ventanas] acciones de «{modulo}»", 403)
    if not isinstance(params, dict):
        raise ErrorDeServicio("los parámetros van en un objeto", 422)
    try:
        return servicio_modulos.consultar(ctx, modulo, verbo, params)
    finally:
        _tocar(ctx)
