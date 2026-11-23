"""Si otra máquina de la persona se alcanza ahora, y qué pasa con lo que se le pide cuando no.

Una máquina está **en línea** mientras su foto (telar.espejo) tenga menos de `espejo.VIGENTE` segundos. Pasado eso,
lo que se sabe de sus hilos es lo último que publicó antes de irse: no se dice que estén vivos ni dormidos, se dice
que son **inalcanzables** («laptop fuera de línea desde 14:02»). Eso se sabe solo si el nodo de aquí está al día con
el bus (`al_dia`): con el nodo de aquí caído, todas las fotos envejecen y la que se quedó sin noticias es esta.

Lo que se le pide a un hilo de una máquina fuera de línea:

- **un mensaje** ya espera solo: su casilla en el bus es durable, y el nodo de allá lo recoge al volver. Solo se dice.
- **despertarlo** (o retomarlo para que lea un mensaje, si no estaba abierto) necesita a su nodo: queda **en cola**
  aquí (`<estado>/cola/<máquina>.json`) y el nodo de aquí lo hace cuando la foto de esa máquina vuelve a llegar
  (`atender`). Lo hecho queda anotado un día, con su resultado (`hechos`), para que la página y `telar hilos --red`
  lo digan; si lo pidió un hilo, le llega un aviso.

    de(config, "laptop")                  Alcance: en línea, desde cuándo no, su versión de telar
    despertar(ctx, hilo, maquina, texto)  despertarlo donde viva: aquí, por el bus, o a la cola
    despertar_aqui(ctx, hilo, texto)      lo que hace su dueño (el verbo `hilo-despertar` del nodo)
    encolar / cola / hechos               la cola de una máquina
    atender(ctx)                          el nodo: lo de las máquinas que volvieron
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

#: el verbo del nodo del dueño
VERBO = "hilo-despertar"
#: cuánto vale la marca de que el nodo de aquí está al día con el bus (la deja cada 30 s mientras está conectado)
AL_DIA = 120.0
#: cuántas veces se intenta un pedido en cola que no tuvo respuesta (o que su nodo no atiende) antes de darlo por fallado
INTENTOS = 3
#: lo hecho se recuerda un día, y hasta tantos por máquina
HECHOS_DURAN = 24 * 3600
HECHOS_TOPE = 30
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def desde_texto(epoca: float | None, ahora: float | None = None) -> str:
    """Desde cuándo, corto: «14:02» hoy, «ayer 14:02», «el 20-nov 14:02»; «?» si no se sabe."""
    if not epoca:
        return "?"
    d = datetime.fromtimestamp(epoca)
    hoy = datetime.fromtimestamp(time.time() if ahora is None else ahora).date()
    if d.date() == hoy:
        return f"{d:%H:%M}"
    if d.date() == hoy - timedelta(days=1):
        return f"ayer {d:%H:%M}"
    return f"el {d.day}-{MESES[d.month - 1]} {d:%H:%M}"


@dataclass(frozen=True)
class Alcance:
    """Lo que se sabe de si una máquina contesta. `conocida`: hay foto suya y el nodo de aquí está al día, así que
    `en_linea` es un dato; sin eso se supone en línea y se le pregunta como siempre."""

    maquina: str
    aqui: bool = False
    conocida: bool = False
    en_linea: bool = True
    #: cuándo llegó su última foto (este reloj)
    recibido: float | None = None
    #: la versión de telar que dice su foto
    telar: str = ""

    @property
    def fuera(self) -> bool:
        """Se sabe que está fuera de línea."""
        return self.conocida and not self.en_linea

    def desde(self, ahora: float | None = None) -> str:
        return desde_texto(self.recibido, ahora)

    def frase(self, ahora: float | None = None) -> str:
        return f"{self.maquina} fuera de línea desde {self.desde(ahora)}"

    def desde_iso(self) -> str:
        return datetime.fromtimestamp(self.recibido).astimezone().isoformat(timespec="seconds") if self.recibido else ""


def _marca(config) -> Path:
    from telar import espejo

    return espejo.carpeta(config) / ".al-dia"


def marcar_al_dia(config) -> None:
    """El nodo, mientras está conectado al bus y recibiendo las fotos: sin esto, una foto vieja no dice nada."""
    try:
        ruta = _marca(config)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.touch()
    except (OSError, AttributeError, TypeError):
        pass


def al_dia(config, ahora: float | None = None) -> bool:
    """Si el nodo de aquí está conectado al bus: entonces la edad de una foto es la de la otra máquina."""
    try:
        return (time.time() if ahora is None else ahora) - _marca(config).stat().st_mtime < AL_DIA
    except (OSError, AttributeError, TypeError):
        return False


def de(config, maquina: str, ahora: float | None = None) -> Alcance:
    """Si `maquina` se alcanza ahora, según su foto."""
    from telar import bus as mod_bus
    from telar import espejo

    if not maquina or not mod_bus.hay_bus(config) or maquina == mod_bus.maquina(config):
        return Alcance(maquina=maquina, aqui=True, conocida=True)
    try:
        foto = next((f for f in espejo.leer_todos(config, ahora) if f.get("nombre") == maquina and not f.get("error")), None)
    except Exception:  # noqa: BLE001 - sin poder leer las fotos, no se sabe
        foto = None
    if foto is None:
        return Alcance(maquina=maquina)
    return Alcance(maquina=maquina, conocida=al_dia(config, ahora), en_linea=bool(foto.get("en_linea")),
                   recibido=foto.get("recibido"), telar=str(foto.get("telar") or ""))


def todas(config, ahora: float | None = None) -> dict[str, Alcance]:
    """El alcance de cada máquina que tiene foto aquí."""
    from telar import espejo

    try:
        nombres = [f["nombre"] for f in espejo.leer_todos(config, ahora) if not f.get("error")]
    except Exception:  # noqa: BLE001
        return {}
    return {n: de(config, n, ahora) for n in nombres}


# ── la cola ─────────────────────────────────────────────────────────────────

def carpeta(config) -> Path:
    return Path(config.estado) / "cola"


def _ruta(config, maquina: str) -> Path:
    from telar import espejo

    nombre = espejo.nombre_valido(maquina)
    if not nombre:
        raise ValueError(f"«{maquina}» no es un nombre de máquina")
    return carpeta(config) / f"{nombre}.json"


def _candado(config):
    from telar import estado as mod_estado

    return mod_estado._candado(carpeta(config) / ".cola.lock")


def _leer(ruta: Path) -> dict:
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pedidos": [], "hechos": []}
    if not isinstance(d, dict):
        return {"pedidos": [], "hechos": []}
    return {"pedidos": [p for p in d.get("pedidos") or [] if isinstance(p, dict)],
            "hechos": [h for h in d.get("hechos") or [] if isinstance(h, dict)]}


def _escribir(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(f".{ruta.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(ruta)


def encolar(config, maquina: str, hilo: str, *, texto: str = "", por: str = "", por_hilo: str = "",
            ahora: float | None = None) -> dict:
    """Deja en cola despertar a `hilo` cuando `maquina` vuelva. Uno solo por hilo: lo que se pide de nuevo se suma al que
    ya espera (su texto, a continuación). `por`: quién lo pidió, en palabras; `por_hilo`: el hilo al que se le avisa
    cuando se haga. Devuelve el pedido, con `nuevo`."""
    ahora = time.time() if ahora is None else ahora
    ruta = _ruta(config, maquina)
    with _candado(config):
        datos = _leer(ruta)
        previo = next((p for p in datos["pedidos"] if p.get("hilo") == hilo), None)
        if previo is not None:
            if texto.strip():
                previo["texto"] = "\n\n".join(t for t in (previo.get("texto", "").strip(), texto.strip()) if t)
            if por_hilo and not previo.get("por_hilo"):
                previo["por_hilo"] = por_hilo
            _escribir(ruta, datos)
            return {**previo, "nuevo": False}
        pedido = {"id": uuid.uuid4().hex[:8], "hilo": hilo, "texto": texto.strip(), "por": por, "por_hilo": por_hilo,
                  "cuando": ahora, "intentos": 0}
        datos["pedidos"].append(pedido)
        _escribir(ruta, datos)
    return {**pedido, "nuevo": True}


def cola(config, maquina: str = "") -> dict[str, list[dict]]:
    """Lo que espera, por máquina (o solo el de `maquina`)."""
    return {m: d["pedidos"] for m, d in _todo(config, maquina).items() if d["pedidos"]}


def hechos(config, maquina: str = "", ahora: float | None = None) -> dict[str, list[dict]]:
    """Lo que se hizo de la cola en el último día, por máquina, lo más nuevo primero."""
    ahora = time.time() if ahora is None else ahora
    salida = {}
    for m, d in _todo(config, maquina).items():
        recientes = [h for h in d["hechos"] if ahora - float(h.get("hecho_en") or 0) < HECHOS_DURAN]
        if recientes:
            salida[m] = sorted(recientes, key=lambda h: -float(h.get("hecho_en") or 0))
    return salida


def _todo(config, maquina: str = "") -> dict[str, dict]:
    """La cola de cada máquina (o la de `maquina`); {} si no hay, o sin carpeta de estado."""
    try:
        if maquina:
            return {maquina: _leer(_ruta(config, maquina))}
        return {r.stem: _leer(r) for r in sorted(carpeta(config).glob("*.json"))}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def _cerrar(config, maquina: str, pid: str, *, ok: bool, resultado: str, ahora: float) -> dict | None:
    """Saca el pedido `pid` de la cola y lo anota hecho (o fallado) con su resultado. El pedido, o None si ya no estaba."""
    ruta = _ruta(config, maquina)
    with _candado(config):
        datos = _leer(ruta)
        p = next((x for x in datos["pedidos"] if x.get("id") == pid), None)
        if p is None:
            return None
        datos["pedidos"] = [x for x in datos["pedidos"] if x.get("id") != pid]
        hecho = {**p, "ok": ok, "resultado": resultado, "hecho_en": ahora}
        datos["hechos"] = [hecho, *[h for h in datos["hechos"] if ahora - float(h.get("hecho_en") or 0) < HECHOS_DURAN]][:HECHOS_TOPE]
        _escribir(ruta, datos)
    return hecho


def _intento(config, maquina: str, pid: str, error: str, ahora: float) -> int:
    """Anota un intento sin respuesta; devuelve cuántos van."""
    ruta = _ruta(config, maquina)
    with _candado(config):
        datos = _leer(ruta)
        p = next((x for x in datos["pedidos"] if x.get("id") == pid), None)
        if p is None:
            return 0
        p["intentos"] = int(p.get("intentos") or 0) + 1
        p["ultimo_intento"], p["ultimo_error"] = ahora, error
        _escribir(ruta, datos)
        return p["intentos"]


# ── despertar ───────────────────────────────────────────────────────────────

def despertar_aqui(ctx, hilo: str, texto: str = "") -> dict:
    """Lo que hace la máquina dueña de `hilo` cuando otra se lo pide (verbo `hilo-despertar`), o cuando se pide aquí:
    uno dormido se despierta en su ventana; uno sin ventana (cerrado, archivado) se retoma con su conversación; uno
    despierto queda como está (y el foco de aquí, también). `texto`: su primer mensaje, al despertarlo o retomarlo.
    {ok, hecho, estaba} o {ok: False, error}."""
    from telar import dormir
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx, con_ficha=False)
    h = next((x for x in tel.hilos if x.nombre == hilo), None)
    if h is None:
        return {"ok": False, "error": f"aquí no hay un hilo «{hilo}»"}
    if h.remoto:
        return {"ok": False, "error": f"«{hilo}» no vive aquí: esta ventana solo lo mira"
                                     + (f" (vive en {h.remoto})" if h.remoto != "?" else "")}
    if tel.vivo(h):
        if dormir.dormido(ctx.config, h.nombre):
            try:
                hecho = dormir.despertar(ctx.config, h.nombre, mensaje=texto, mux=tel.mux)
            except RuntimeError as e:
                return {"ok": False, "error": str(e)}
            if hecho:
                return {"ok": True, "hecho": hecho, "estaba": "dormido"}
        else:
            return {"ok": True, "estaba": "despierto",
                    "hecho": f"«{hilo}» ya estaba despierto" + (": el texto no se le mandó (eso es telar mensaje)" if texto else "")}
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from telar.ordenes import hilo as orden_hilo

    estaba = "archivado" if h.archivado else "cerrado"
    salida, errores = io.StringIO(), io.StringIO()
    with redirect_stdout(salida), redirect_stderr(errores):
        codigo = orden_hilo.main(["retomar", "--hilo", hilo, *(["--texto", texto] if texto else [])], ctx)
    lineas = (errores.getvalue() if codigo else salida.getvalue()).strip().splitlines()
    if codigo != 0:
        return {"ok": False, "error": (lineas[-1] if lineas else "no se pudo retomar").removeprefix("telar: ")}
    return {"ok": True, "estaba": estaba, "hecho": (lineas[-1] if lineas else f"retomado «{hilo}»")}


def despertar(ctx, hilo: str, maquina: str = "", texto: str = "", *, por: str = "", por_hilo: str = "",
              ahora: float | None = None) -> dict:
    """Despertar `hilo` donde viva: aquí (`despertar_aqui`), en otra máquina por el bus, o, si esa máquina está fuera
    de línea, a su cola. {hecho, estaba, maquina, en_cola, desde, aviso}. RuntimeError si no se pudo, con el motivo."""
    from telar import bus as mod_bus

    if not maquina or not mod_bus.hay_bus(ctx.config) or maquina == mod_bus.maquina(ctx.config):
        r = despertar_aqui(ctx, hilo, texto)
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "no se pudo")
        return {"hecho": r.get("hecho", ""), "estaba": r.get("estaba", ""), "maquina": "", "en_cola": False}
    a = de(ctx.config, maquina, ahora)
    if a.fuera:
        return _a_la_cola(ctx, a, hilo, texto, por, por_hilo, ahora)
    r = mod_bus.pedir(ctx.config, maquina, VERBO, {"hilo": hilo, "texto": texto}, espera=60)
    if r.get("fuera_de_linea"):
        return _a_la_cola(ctx, de(ctx.config, maquina, ahora), hilo, texto, por, por_hilo, ahora)
    if not r.get("ok"):
        raise RuntimeError(f"«{hilo}» vive en {maquina} y no se pudo despertar: {r.get('error') or 'no respondió'}")
    if "hecho" not in r:
        # un nodo de antes contesta {ok} solo: retomó (o despertó) sin saber de texto
        aviso = f"{maquina} tiene un telar de antes" + (": el texto no le llegó (mándaselo con telar mensaje)" if texto else "")
        return {"hecho": f"«{hilo}» retomado en {maquina}", "estaba": "", "maquina": maquina, "en_cola": False,
                "aviso": aviso}
    return {"hecho": f"{r['hecho']} (en {maquina})" if r.get("hecho") else "", "estaba": r.get("estaba", ""),
            "maquina": maquina, "en_cola": False}


def _a_la_cola(ctx, a: Alcance, hilo: str, texto: str, por: str, por_hilo: str, ahora: float | None) -> dict:
    p = encolar(ctx.config, a.maquina, hilo, texto=texto, por=por, por_hilo=por_hilo, ahora=ahora)
    ya = "" if p["nuevo"] else " (ya estaba en cola: " + ("se le suma el texto" if texto else "queda uno") + ")"
    return {"hecho": f"{a.frase(ahora)}: «{hilo}» se despierta cuando vuelva{ya}", "estaba": "", "maquina": a.maquina,
            "en_cola": True, "desde": a.desde_iso(), "pedido": p["id"]}


def atender(ctx, *, anotar=None, ahora: float | None = None) -> list[str]:
    """El nodo, cada pocos segundos: lo que espera para las máquinas que volvieron (su foto llegó de nuevo), una vez
    por foto nueva. Lo que se hace sale de la cola con su resultado; lo que sigue sin respuesta se intenta en la foto
    siguiente, hasta `INTENTOS`. Devuelve lo que hizo, una línea por pedido."""
    from telar import bus as mod_bus

    dicho: list[str] = []
    for maquina, pedidos in cola(ctx.config).items():
        momento = time.time() if ahora is None else ahora
        a = de(ctx.config, maquina, momento)
        if not a.conocida or not a.en_linea:
            continue  # sigue fuera (o no se sabe: el nodo de aquí no está al día)
        for p in pedidos:
            if p.get("ultimo_intento") and a.recibido and float(p["ultimo_intento"]) >= a.recibido:
                continue  # ya se intentó con esta foto: la siguiente
            hilo, texto = str(p.get("hilo") or ""), str(p.get("texto") or "")
            r = mod_bus.pedir(ctx.config, maquina, VERBO, {"hilo": hilo, "texto": texto, "en_cola": True}, espera=60)
            momento = time.time() if ahora is None else ahora
            if r.get("ok"):
                resultado = r.get("hecho") or f"«{hilo}» retomado en {maquina}"
                if "hecho" not in r and texto:
                    resultado += f" ({maquina} tiene un telar de antes: el texto no le llegó)"
                cerrado = _cerrar(ctx.config, maquina, p["id"], ok=True, resultado=resultado, ahora=momento)
            elif r.get("fuera_de_linea"):
                continue  # se volvió a ir: se espera la próxima foto
            elif r.get("sin_servicio") or "no respondió" in str(r.get("error") or ""):
                if _intento(ctx.config, maquina, p["id"], str(r.get("error") or ""), momento) < INTENTOS:
                    continue
                cerrado = _cerrar(ctx.config, maquina, p["id"], ok=False, ahora=momento,
                                  resultado=f"no se pudo despertar a «{hilo}» en {maquina}: {r.get('error') or 'no respondió'}")
            else:
                cerrado = _cerrar(ctx.config, maquina, p["id"], ok=False, ahora=momento,
                                  resultado=f"no se pudo despertar a «{hilo}» en {maquina}: {r.get('error') or 'falló'}")
            if cerrado is None:
                continue
            linea = f"en cola para {maquina} desde {desde_texto(cerrado.get('cuando'), momento)}: {cerrado['resultado']}"
            dicho.append(linea)
            if anotar is not None:
                anotar(linea)
            if cerrado.get("por_hilo"):
                try:
                    mod_bus.enviar(ctx.config, cerrado["por_hilo"], linea, de="telar", modo="aviso")
                except Exception:  # noqa: BLE001 - el aviso es un extra: lo hecho queda anotado
                    pass
    return dicho
