"""El Encargo como objeto: un pedido durable a un hilo, con estado y resultado (docs/propuestas/mensajes-con-modos.md).

Lo crea un mensaje con `--modo encargo` (`telar mensaje Faro "…" --modo encargo`) al llegar a la casilla de su
destinatario (telar.casilla.dejar), y vive en la máquina de quien lo hace:

    <estado>/encargos/objetos/<id>.json     el encargo, en la máquina del destinatario
    <estado>/encargos/enviados/<id>.json    la nota de quien lo mandó: para quién y en qué máquina

Su dirección es `encargo:<id>` (`e-1a2b3c4d`, que elige quien lo manda para poder nombrarlo antes de que
llegue). Su estado va

    pedido → aceptado → corriendo → hecho | falló | cancelado

`aceptar`, `rechazar` (lo deja cancelado, con el motivo como resultado), `cerrar` (hecho o falló, con el
resultado) y `cancelar` (lo pide quien lo mandó: si no le había llegado, sale de su casilla; si ya corría, se le
dice que pare) son sus acciones; rechazar o cerrar le avisa a quien lo pidió, si fue un hilo. Queda `corriendo`
cuando su casilla se lo entrega al hilo (el gancho), y si el hilo termina el turno sin cerrarlo, el gancho `Stop`
le recuerda cerrarlo, una vez (`sin_cerrar`). `telar encargar` también hace un encargo así (telar.encargos).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

ESTADOS = ("pedido", "aceptado", "corriendo", "hecho", "falló", "cancelado")
CERRADOS = ("hecho", "falló", "cancelado")
#: e- y ocho cifras hex: no se confunde con un id de tarea (T84) ni con el de una casilla (c-1a2b3c)
FORMA_ID = re.compile(r"e-[0-9a-f]{8}")


class ErrorDeEncargo(Exception):
    """Una acción que no se pudo hacer, con el código que le toca (404, 409, 422). El mensaje es para quien la pidió."""

    def __init__(self, texto: str, codigo: int = 422):
        super().__init__(texto)
        self.codigo = codigo


def nuevo_id() -> str:
    return "e-" + uuid.uuid4().hex[:8]


def plazo_valido(texto: str) -> str:
    """El plazo como se guarda: una fecha (`2026-10-24`) o fecha y hora ISO, tal cual. "" si no hay. ValueError
    si no se entiende. La forma ISO básica (`20261024`, que Python también lee) se guarda en la extendida: así
    una fecha sola se reconoce como fecha y vence al final del día, como `2026-10-24`."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    if _solo_fecha(texto):
        return date.fromisoformat(texto).isoformat()
    try:
        cuando = datetime.fromisoformat(texto)
    except ValueError:
        raise ValueError(f"el plazo «{texto}» no es una fecha: 2026-10-24, o 2026-10-24T18:00") from None
    return texto if re.match(r"\d{4}-\d{2}-\d{2}[T ]", texto) else cuando.isoformat()


def _solo_fecha(texto: str) -> bool:
    """Si el plazo es una fecha sin hora, en la forma que sea (`2026-10-24`, `20261024`)."""
    try:
        date.fromisoformat(texto)
    except ValueError:
        return False
    return True


def vencido(e: dict, ahora: datetime | None = None) -> bool:
    """Si su plazo pasó y no está cerrado. Una fecha sola vence al terminar ese día."""
    texto = str(e.get("plazo") or "")
    if not texto or e.get("estado") in CERRADOS:
        return False
    try:
        plazo = datetime.fromisoformat(texto)
    except ValueError:
        return False
    ahora = ahora or datetime.now().astimezone()
    if _solo_fecha(texto):  # solo la fecha: vale hasta el final del día
        return ahora.date() > plazo.date()

    def local(t: datetime) -> datetime:
        # con zona o sin ella, en la hora de esta máquina: así se comparan siempre
        return t.astimezone().replace(tzinfo=None) if t.tzinfo else t

    return local(ahora) > local(plazo)


def _carpeta(config, cual: str) -> Path:
    return Path(config.estado) / "encargos" / cual


def _ruta(config, cual: str, eid: str) -> Path:
    if not FORMA_ID.fullmatch(eid or ""):
        raise ErrorDeEncargo(f"«{eid}» no es el id de un encargo: se escribe e- y ocho cifras hex (e-1a2b3c4d)", 404)
    return _carpeta(config, cual) / f"{eid}.json"


def _escribir(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(f".{ruta.name}.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, ruta)


def _leer(ruta: Path) -> dict | None:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


@contextmanager
def _candado(ruta: Path):
    """De a uno sobre un encargo: la CLI (o la API) y el nodo pueden hacerle una acción a la vez, y la segunda
    leería lo de antes de la primera y la pisaría (dos `cerrar` pasarían los dos y se avisaría dos veces)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta.with_name(f".{ruta.name}.lock"), "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def _nombre_de_hoy(config, hilo: str) -> str:
    """El nombre que tiene hoy el hilo que lo hace, si se renombró después de recibirlo."""
    if not hilo:
        return hilo
    try:
        from telar import estado as mod_estado

        return mod_estado.abrir(config).nombre_actual(hilo)
    except Exception:  # noqa: BLE001 - sin estado legible, el nombre con que llegó
        return hilo


def _ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ── en la máquina del destinatario ──────────────────────────────────────────────

def recibir(config, mensaje: dict, maquina: str = "") -> bool:
    """Crea el encargo que trae un mensaje `modo = "encargo"` recién dejado en una casilla. False si ya existía
    (el mismo mensaje dos veces, o un id que ya está: el que llega segundo no pisa al primero) o si el mensaje no
    trae un id de encargo válido."""
    eid = str(mensaje.get("encargo") or "")
    if not FORMA_ID.fullmatch(eid):
        return False
    ruta = _ruta(config, "objetos", eid)
    if ruta.exists():
        return False
    ahora = _ahora()
    _escribir(ruta, {
        "id": eid, "estado": "pedido", "texto": str(mensaje.get("texto", "")),
        "de": str(mensaje.get("de", "")), "para": str(mensaje.get("hilo") or mensaje.get("para") or ""),
        "responder_a": str(mensaje.get("responder_a", "")), "persona": str(mensaje.get("persona", "")),
        "mensaje": str(mensaje.get("id", "")), "plazo": str(mensaje.get("plazo", "")),
        "resultado": "", "maquina": maquina, "creado": str(mensaje.get("creado") or ahora), "actualizado": ahora,
        "historia": [{"hora": ahora, "estado": "pedido", "quien": str(mensaje.get("de", ""))}],
    })
    return True


def mudar(config, eid: str, nuevo: str) -> bool:
    """Lo hace otro nombre (su agente se renombró y la casilla se mudó, telar.casilla.mudar): el aviso al
    cerrarlo y sus enlaces lo nombran como se llama ahora. False si no está aquí."""
    try:
        ruta = _ruta(config, "objetos", eid)
    except ErrorDeEncargo:
        return False
    with _candado(ruta):
        e = _leer(ruta)
        if e is None or e.get("para") == nuevo:
            return False
        e["para"] = nuevo
        _escribir(ruta, e)
    return True


def leer(config, eid: str) -> dict | None:
    """El encargo de esta máquina; None si no está aquí."""
    try:
        return _leer(_ruta(config, "objetos", eid))
    except ErrorDeEncargo:
        return None


def lista(config) -> list[dict]:
    """Los encargos de esta máquina, del más viejo al más nuevo."""
    d = _carpeta(config, "objetos")
    salida = [e for f in (sorted(d.glob("e-*.json")) if d.is_dir() else []) if (e := _leer(f))]
    return sorted(salida, key=lambda e: str(e.get("creado", "")))


def version(e: dict) -> str:
    """Lo que cambia con cada acción: una acción con una versión vieja no se hace (409)."""
    huella = "\0".join([str(e.get("estado", "")), str(len(e.get("historia") or ())), str(e.get("actualizado", ""))])
    return hashlib.sha1(huella.encode()).hexdigest()[:12]


#: las acciones y sus parámetros, por nombre ("" obligatorio; si no, su valor por defecto)
ACCIONES = {
    "aceptar": ("tomarlo: queda aceptado", {}),
    "cancelar": ("ya no hace falta (lo pide quien lo mandó): si no le llegó, sale de su casilla; si corría, se le "
                 "dice que pare", {"motivo": "''"}),
    "rechazar": ("no hacerlo, y decir por qué: queda cancelado y se le avisa a quien lo pidió", {"motivo": ""}),
    "cerrar": ("terminarlo con su resultado (hecho, o falló): se le avisa a quien lo pidió",
               {"resultado": "", "estado": "'hecho'"}),
}


def acciones_de(e: dict) -> list[str]:
    """Las acciones que tiene en su estado: ninguna, si ya se cerró."""
    if e.get("estado") in CERRADOS:
        return []
    return ["aceptar", "rechazar", "cerrar", "cancelar"] if e.get("estado") == "pedido" else ["rechazar", "cerrar", "cancelar"]


def hacer(ctx, eid: str, accion: str, params: dict | None = None, *, version_leida: str = "", quien: str = "") -> dict:
    """Aplica una acción a un encargo de esta máquina y lo devuelve como quedó. ErrorDeEncargo si no se puede:
    404 (no está, o no tiene esa acción), 409 (cambió desde que se leyó, o su estado no la permite), 422 (faltan
    parámetros). Rechazar o cerrar le avisa a `responder_a`; si el aviso no sale, queda en su historia y la
    acción vale igual."""
    params = params or {}
    if accion not in ACCIONES:
        raise ErrorDeEncargo(f"un encargo no tiene la acción «{accion}»: {', '.join(ACCIONES)}", 404)
    ruta = _ruta(ctx.config, "objetos", eid)
    # leer, comprobar y escribir, bajo candado: dos acciones a la vez no pasan las dos
    with _candado(ruta):
        e = _leer(ruta)
        if e is None:
            raise ErrorDeEncargo(f"no hay un encargo {eid} en esta máquina", 404)
        if version_leida and version_leida != version(e):
            raise ErrorDeEncargo(f"encargo:{eid} cambió desde que se leyó: vuelve a mirarlo", 409)
        if accion not in acciones_de(e):
            raise ErrorDeEncargo(f"encargo:{eid} está {e.get('estado')}: no se puede {accion}", 409)
        nota = ""
        antes = e.get("estado")
        if accion == "aceptar":
            nuevo = "aceptado"
        elif accion == "cancelar":
            nuevo = "cancelado"
            nota = str(params.get("motivo") or "").strip() or "ya no hace falta"
            e["cancelado_por"], e["resultado"] = quien, nota
        elif accion == "rechazar":
            nota = str(params.get("motivo") or "").strip()
            if not nota:
                raise ErrorDeEncargo("rechazar: ¿por qué no? params {\"motivo\": …}", 422)
            nuevo = "cancelado"
            e["rechazado"], e["resultado"] = True, nota
        else:
            resultado = str(params.get("resultado") or "").strip()
            if not resultado:
                raise ErrorDeEncargo("cerrar: ¿cómo terminó? params {\"resultado\": …}", 422)
            # en NFC: un «falló» escrito en macOS puede llegar descompuesto (la o y el acento aparte)
            nuevo = unicodedata.normalize("NFC", str(params.get("estado") or "hecho").strip())
            if nuevo not in ("hecho", "falló", "fallo"):
                raise ErrorDeEncargo(f"cerrar: el estado es hecho o falló, no «{nuevo}»", 422)
            nuevo = "falló" if nuevo == "fallo" else nuevo
            e["resultado"] = nota = resultado
        # si el hilo que lo hace se renombró, el aviso y los enlaces lo nombran como se llama ahora
        e["para"] = _nombre_de_hoy(ctx.config, str(e.get("para") or ""))
        ahora = _ahora()
        e["estado"], e["actualizado"] = nuevo, ahora
        paso = {"hora": ahora, "estado": nuevo, "quien": quien}
        if nota:
            paso["nota"] = nota
        e.setdefault("historia", []).append(paso)
        _escribir(ruta, e)
    if accion == "cancelar":
        avisado = _cancelado(ctx.config, e, antes)
        if avisado:
            with _candado(ruta):
                e = _leer(ruta) or e
                e.setdefault("historia", []).append({"hora": _ahora(), "estado": "cancelado", "quien": "telar", "nota": avisado})
                _escribir(ruta, e)
        return e
    if accion != "aceptar" and e.get("responder_a"):
        # el aviso, fuera del candado (el bus puede tardar); lo que pasó se agrega sobre lo que haya entonces
        avisado = _avisar(ctx, e)
        with _candado(ruta):
            e = _leer(ruta) or e
            e.setdefault("historia", []).append({"hora": _ahora(), "estado": nuevo, "quien": "telar", "nota": avisado})
            _escribir(ruta, e)
    return e


def _cancelado(config, e: dict, antes: str) -> str:
    """Lo que hace cancelar en la casilla de quien lo hace: si no le había llegado, el mensaje sale de ahí; si ya
    corría, se le deja un pedido de que pare. Lo que pasó, en una frase."""
    from telar import casilla

    hilo, mid = str(e.get("para") or ""), str(e.get("mensaje") or "")
    if antes in ("pedido", "aceptado") and hilo and mid:
        ruta = casilla._archivo(config, hilo, mid)
        if ruta is not None:
            try:
                ruta.unlink()
                return "no le había llegado: salió de su casilla"
            except OSError:
                pass
    if antes in ("aceptado", "corriendo", "pedido") and hilo:
        from telar import bus as mod_bus

        texto = (f"[telar] `encargo:{e['id']}` se canceló ({e.get('resultado') or 'ya no hace falta'}): deja lo que "
                 f"estés haciendo por él. Lo que pidió: {' '.join(str(e.get('texto', '')).split())[:160]}")
        casilla.dejar(config, hilo, mod_bus.mensaje(texto, de="telar", para=hilo))
        return "ya le había llegado: se le dijo que pare"
    return ""


def empezar(config, eid: str, quien: str = "") -> bool:
    """Lo deja `corriendo`: su casilla se lo acaba de entregar al hilo. False si no está aquí o ya no estaba por
    empezar (aceptado, o pedido)."""
    try:
        ruta = _ruta(config, "objetos", eid)
    except ErrorDeEncargo:
        return False
    with _candado(ruta):
        e = _leer(ruta)
        if e is None or e.get("estado") not in ("pedido", "aceptado"):
            return False
        ahora = _ahora()
        e["estado"], e["actualizado"] = "corriendo", ahora
        e.setdefault("historia", []).append({"hora": ahora, "estado": "corriendo", "quien": quien or str(e.get("para") or "")})
        _escribir(ruta, e)
    return True


def sin_cerrar(config, hilo: str) -> list[dict]:
    """Los encargos de `hilo` que corren y no se le recordó cerrar: el gancho `Stop` se lo recuerda una vez
    (`recordar`)."""
    return [e for e in lista(config) if e.get("estado") == "corriendo" and e.get("para") == hilo and not e.get("recordado")]


def recordar(config, eid: str) -> None:
    try:
        ruta = _ruta(config, "objetos", eid)
    except ErrorDeEncargo:
        return
    with _candado(ruta):
        e = _leer(ruta)
        if e is not None:
            e["recordado"] = True
            _escribir(ruta, e)


def recordatorio(encargos: list[dict]) -> str:
    """Lo que el gancho `Stop` le dice al hilo que termina un turno con encargos sin cerrar."""
    lineas = [f"- `encargo:{e['id']}`: {' '.join(str(e.get('texto', '')).split())[:120]}" for e in encargos]
    ejemplo = encargos[0]["id"]
    return ("[telar] Terminas el turno con encargos sin cerrar:\n" + "\n".join(lineas) + "\n"
            f"Si ya están, ciérralos con su resultado (lo recibe quien los pidió): `telar objeto encargo:{ejemplo} cerrar "
            "--params '{\"resultado\": \"…\"}'` (o con \"estado\": \"falló\"). Si siguen en curso, dilo en una línea y "
            "termina: no se vuelve a recordar.")


def de_hilo(config, hilo: str = "", *, abiertos: bool = False) -> list[dict]:
    """Los encargos de esta máquina para `hilo` (o todos), del más nuevo al más viejo; `abiertos`, solo los que no se
    cerraron."""
    return [e for e in reversed(lista(config)) if (not hilo or e.get("para") == hilo)
            and (not abiertos or e.get("estado") not in CERRADOS)]


def texto_del_aviso(e: dict) -> str:
    """Lo que le llega a quien lo pidió cuando se rechaza o se cierra."""
    que = "rechazó" if e.get("rechazado") else {"hecho": "terminó", "falló": "no pudo hacer"}.get(e["estado"], "cerró")
    pedido = " ".join(str(e.get("texto", "")).split())[:160]
    return (f"«{e.get('para') or 'el destinatario'}» {que} `encargo:{e['id']}` ({e['estado']}).\n"
            f"Lo que pediste: {pedido}\n"
            f"{'Motivo' if e.get('rechazado') else 'Resultado'}: {e.get('resultado') or '(sin decir)'}")


def _avisar(ctx, e: dict) -> str:
    """Le manda el resultado a quien lo pidió, como un pedido (despierta) y con los frenos de siempre. Lo que pasó,
    en una frase para la historia."""
    from telar.ordenes import mensaje

    try:
        r = mensaje.enviar(ctx, e["responder_a"], texto_del_aviso(e), de=e.get("para") or "")
    except Exception as ex:  # noqa: BLE001 - la acción ya quedó: que el aviso falle se anota, no la deshace
        return f"no se le pudo avisar a «{e['responder_a']}»: {ex}"
    if r.get("estado") == "retenido":
        return f"el aviso a «{e['responder_a']}» quedó retenido ({r.get('motivo', '')}) · id {r.get('id', '')}"
    return f"avisado a «{e['responder_a']}» · id {r.get('id', '')}"


def atender(ctx, pedido: dict) -> dict:
    """El pedido `encargo` del nodo, desde otra máquina: `{id}` lo devuelve; `{id, accion, params, version,
    quien}` le aplica la acción. Siempre `{ok, …}`: `encargo` y su `version`, o `error` y `codigo`."""
    if "lista" in pedido:
        # los de un hilo de aquí, para la página de otra máquina (su vista de agentes)
        return {"ok": True, "encargos": de_hilo(ctx.config, str(pedido.get("lista") or ""),
                                                abiertos=bool(pedido.get("abiertos")))[:50]}
    eid = str(pedido.get("id") or "")
    accion = str(pedido.get("accion") or "")
    try:
        if accion:
            params = pedido.get("params") if isinstance(pedido.get("params"), dict) else {}
            e = hacer(ctx, eid, accion, params, version_leida=str(pedido.get("version") or ""),
                      quien=str(pedido.get("quien") or ""))
        else:
            e = leer(ctx.config, eid)
            if e is None:
                raise ErrorDeEncargo(f"no hay un encargo {eid} en esta máquina", 404)
    except ErrorDeEncargo as ex:
        return {"ok": False, "error": str(ex), "codigo": ex.codigo}
    return {"ok": True, "encargo": e, "version": version(e)}


# ── en la máquina de quien lo mandó ─────────────────────────────────────────────

def anotar_enviado(config, eid: str, *, para: str, maquina: str = "", texto: str = "", plazo: str = "",
                   de: str = "", retenido: str = "") -> None:
    """La nota de quien lo mandó: con ella `telar objeto encargo:<id>` sabe dónde buscarlo, y lo muestra en camino
    mientras el nodo de allá no lo recoge. `maquina`: donde vivía su hilo al mandarlo (si se muda después, o su
    estado se borra del bus, el encargo sigue en esa). `retenido`: el motivo, si el mensaje no salió; en camino
    no va hasta que la persona lo suelte."""
    datos = {"id": eid, "para": para, "maquina": maquina, "texto": texto, "plazo": plazo, "de": de, "creado": _ahora()}
    if retenido:
        datos["retenido"] = retenido
    _escribir(_ruta(config, "enviados", eid), datos)


def soltado(config, eid: str) -> None:
    """El mensaje retenido de un encargo salió: su nota, si está aquí, deja de decir retenido."""
    nota = enviado(config, eid)
    if nota is not None and nota.pop("retenido", None) is not None:
        _escribir(_ruta(config, "enviados", eid), nota)


def enviado(config, eid: str) -> dict | None:
    try:
        return _leer(_ruta(config, "enviados", eid))
    except ErrorDeEncargo:
        return None
