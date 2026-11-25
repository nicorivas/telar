"""Los comentarios de un archivo: lo que la persona marca sobre el texto para que un agente lo lea y trabaje en ello.

El documento **nunca se toca**. Los comentarios de `informe.md` viven al lado, en `.informe.md.marginalia.json`: texto
plano, versionable, legible sin telar. El formato (docs/contratos.md, «Los comentarios de un archivo») es el de la
extensión de editor que lo inventó, tal cual: lo que se comenta desde la página lo lee su CLI, y lo que ella escribe se
ve en la página.

    {"version": 1, "archivo": "informe.md", "hilos": [
      {"id": "h1", "estado": "abierto",
       "ancla": {"cita": "…", "antes": "…", "despues": "…", "inicio": 40, "fin": 65},
       "creado": "2026-11-23T09:00:00-03:00",
       "comentarios": [{"id": "c1", "autor": "…", "cuerpo": "…", "fecha": "…"}]}]}

Un **hilo** es un comentario sobre un tramo y sus respuestas; está `abierto` o `resuelto`, y resolverlo quiere decir
«está hecho». El **ancla** es la cita, no la línea (telar.anclaje): el texto comentado y 48 caracteres de contexto a
cada lado, y las posiciones de cuando se ancló como pista (en unidades UTF-16, como las cuenta JavaScript). Al leerlo,
cada hilo se vuelve a ubicar en el texto de hoy y se dice cómo (`metodo`, `confianza`), o que está **sin ancla**.

Lo que no se conoce del archivo (un campo que agregue otra versión) se conserva al reescribirlo. Cuando un archivo se
queda sin hilos, el de al lado se borra en vez de quedar como cascarón. Se escribe de una vez (temporal y rename), y
dos que escriben a la vez (la página y el agente) se turnan.

Lo usan la API (telar.servicios.comentarios, que agrega los límites de lo que la página puede leer, la otra máquina y
el commit) y `telar comentarios` (telar.ordenes.comentarios).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from telar import anclaje

__all__ = ["SUFIJO", "ErrorDeComentarios", "lateral", "documento_de", "leer", "escribir", "ubicar", "buscar", "comentar",
           "responder", "resolver", "reabrir", "editar", "borrar", "ahora"]

SUFIJO = ".marginalia.json"
VERSION = 1
#: lo que no se recorre al buscar los comentarios de una carpeta
IGNORADOS = frozenset({"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".next", "out",
                       "_archive", "_dormant", ".vercel"})
#: cuántas entradas mira, como mucho, la búsqueda en una carpeta
TOPE_BUSCAR = 20000

_candado = threading.Lock()


class ErrorDeComentarios(Exception):
    """Lo que no se puede hacer, con su código HTTP (404: no hay ese hilo; 409: el texto cambió; 422: el pedido no sirve)."""

    def __init__(self, mensaje: str, codigo: int = 422):
        super().__init__(mensaje)
        self.codigo = codigo


# ── el archivo de al lado ──────────────────────────────────────────────────────────────────────────────────────────


def lateral(ruta: Path) -> Path:
    """`dir/informe.md` → `dir/.informe.md.marginalia.json`."""
    ruta = Path(ruta)
    return ruta.parent / f".{ruta.name}{SUFIJO}"


def documento_de(lado: Path) -> Path | None:
    """`dir/.informe.md.marginalia.json` → `dir/informe.md`, o None si no es uno de esos."""
    lado = Path(lado)
    if not lado.name.startswith(".") or not lado.name.endswith(SUFIJO) or len(lado.name) <= len(SUFIJO) + 1:
        return None
    return lado.parent / lado.name[1:-len(SUFIJO)]


def _vacio(ruta: Path) -> dict:
    return {"version": VERSION, "archivo": Path(ruta).name, "hilos": []}


def leer(ruta: Path) -> dict:
    """Los comentarios de `ruta` (el documento): el contenido del archivo de al lado, o uno vacío si no hay. Uno que
    no se puede leer o no tiene la forma levanta (409): no se pisa lo que no se entiende."""
    lado = lateral(ruta)
    try:
        crudo = json.loads(lado.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _vacio(ruta)
    except (OSError, ValueError) as e:
        raise ErrorDeComentarios(f"{lado.name} no se pudo leer: {e}", 409) from e
    if not isinstance(crudo, dict) or not isinstance(crudo.get("hilos"), list):
        raise ErrorDeComentarios(f"{lado.name} no tiene la forma esperada (le falta la lista «hilos»)", 409)
    crudo.setdefault("version", VERSION)
    crudo.setdefault("archivo", Path(ruta).name)
    return crudo


def escribir(ruta: Path, datos: dict) -> Path:
    """Escribe los comentarios de `ruta` de una vez; sin hilos, borra el de al lado. Devuelve su ruta."""
    lado = lateral(ruta)
    if not datos.get("hilos"):
        with contextlib.suppress(FileNotFoundError):
            lado.unlink()
        return lado
    # como JSON.stringify(…, null, 2) + "\n": dos espacios, sin escapar lo que no es ASCII
    texto = json.dumps(datos, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=f".{lado.name}.", suffix=".tmp", dir=lado.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
        # los permisos de un archivo cualquiera (mkstemp lo deja solo para su dueño), o los que ya tenía
        try:
            modo = lado.stat().st_mode & 0o777
        except FileNotFoundError:
            modo = 0o644
        os.chmod(tmp, modo)
        os.replace(tmp, lado)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return lado


@contextlib.contextmanager
def _turno(ruta: Path):
    """Uno a la vez sobre los comentarios de `ruta`: en este proceso (un candado) y entre procesos (la página y el
    agente: un candado de archivo, en la carpeta temporal, para no dejar nada al lado del documento)."""
    import fcntl

    llave = hashlib.sha1(str(Path(ruta).resolve()).encode()).hexdigest()[:16]
    candado = Path(tempfile.gettempdir()) / f"telar-comentarios-{llave}.lock"
    with _candado, open(candado, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def ahora() -> str:
    """La fecha de ahora, ISO 8601 con el desfase de aquí y sin fracciones de segundo."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _siguiente(prefijo: str, usados) -> str:
    """Ids cortos y legibles: h1, h2… c1, c2…, uno más que el mayor."""
    mayor = 0
    for u in usados:
        if m := re.fullmatch(rf"{prefijo}(\d+)", str(u)):
            mayor = max(mayor, int(m.group(1)))
    return f"{prefijo}{mayor + 1}"


# ── leerlos ubicados en el texto de hoy ────────────────────────────────────────────────────────────────────────────


def ancla_de(texto: str, crudo: dict) -> anclaje.Ancla:
    """El ancla de un hilo como la entiende telar.anclaje: sus posiciones, de UTF-16 a puntos de código."""
    a = crudo if isinstance(crudo, dict) else {}
    return anclaje.Ancla(cita=str(a.get("cita") or ""), antes=str(a.get("antes") or ""), despues=str(a.get("despues") or ""),
                         inicio=anclaje.de_utf16(texto, int(a.get("inicio") or 0)), fin=anclaje.de_utf16(texto, int(a.get("fin") or 0)))


def _ancla_para_archivo(texto: str, a: anclaje.Ancla) -> dict:
    return {"cita": a.cita, "antes": a.antes, "despues": a.despues,
            "inicio": anclaje.a_utf16(texto, a.inicio), "fin": anclaje.a_utf16(texto, a.fin)}


def ubicado(texto: str, hilo: dict) -> dict:
    """Un hilo con dónde está hoy: `anclado`, `metodo` y `confianza` (None sin ancla), `linea` y `linea_fin` (desde 1),
    `inicio` y `fin` en el texto de hoy (en unidades UTF-16, como las usa la página) y `actual`, lo que dice hoy ese
    lugar si es otra cosa que la cita."""
    a = ancla_de(texto, hilo.get("ancla"))
    r = anclaje.resolver(texto, a)
    actual = texto[r.inicio:r.fin] if r and r.fin > r.inicio else None
    return {
        "id": str(hilo.get("id", "")), "estado": str(hilo.get("estado", "abierto")),
        "cita": a.cita, "antes": a.antes, "despues": a.despues, "creado": str(hilo.get("creado", "")),
        "anclado": r is not None, "metodo": r.metodo if r else None,
        "confianza": round(r.confianza, 3) if r else None,
        "linea": anclaje.linea_de(texto, r.inicio) if r else None,
        "linea_fin": anclaje.linea_de(texto, r.fin) if r else None,
        "inicio": anclaje.a_utf16(texto, r.inicio) if r else None,
        "fin": anclaje.a_utf16(texto, r.fin) if r else None,
        "actual": actual if actual is not None and _plano(actual) != _plano(a.cita) else None,
        "comentarios": [{"id": str(c.get("id", "")), "autor": str(c.get("autor", "")), "cuerpo": str(c.get("cuerpo", "")),
                         "fecha": str(c.get("fecha", ""))} for c in hilo.get("comentarios") or [] if isinstance(c, dict)],
    }


def _plano(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _texto(ruta: Path) -> str:
    try:
        return Path(ruta).read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ErrorDeComentarios(f"{Path(ruta).name} no existe", 404) from e
    except (OSError, UnicodeDecodeError) as e:
        raise ErrorDeComentarios(f"{Path(ruta).name} no se puede leer como texto: {e}", 422) from e


def ubicar(ruta: Path, *, todos: bool = True) -> list[dict]:
    """Los hilos de `ruta`, ubicados en su texto de hoy, en el orden del documento (los sin ancla al final). Sin
    `todos`, solo los abiertos."""
    datos = leer(ruta)
    if not datos["hilos"]:
        return []
    try:
        texto = _texto(ruta)
    except ErrorDeComentarios as e:
        if e.codigo == 404:
            raise ErrorDeComentarios(f"{Path(ruta).name} no existe, pero su archivo de comentarios sí", 404) from e
        raise
    hilos = [ubicado(texto, h) for h in datos["hilos"] if isinstance(h, dict)
             and (todos or h.get("estado", "abierto") == "abierto")]
    hilos.sort(key=lambda h: h["inicio"] if h["inicio"] is not None else float("inf"))
    return hilos


def buscar(raiz: Path, tope: int = TOPE_BUSCAR) -> list[Path]:
    """Los documentos con comentarios bajo `raiz` (una carpeta, o un archivo: él, si tiene), en orden."""
    raiz = Path(raiz)
    if raiz.is_file():
        return [raiz] if lateral(raiz).is_file() else []
    hallados: list[Path] = []
    pendientes, vistos = [raiz], 0
    while pendientes and vistos < tope:
        carpeta = pendientes.pop()
        try:
            entradas = list(os.scandir(carpeta))
        except OSError:
            continue
        for e in entradas:
            vistos += 1
            if e.is_dir(follow_symlinks=False):
                if e.name not in IGNORADOS:
                    pendientes.append(Path(e.path))
            elif e.name.startswith(".") and e.name.endswith(SUFIJO) and (doc := documento_de(Path(e.path))) is not None:
                hallados.append(doc)
    return sorted(hallados)


# ── cambiarlos ─────────────────────────────────────────────────────────────────────────────────────────────────────


def comentar(ruta: Path, inicio: int, fin: int, cuerpo: str, autor: str, *, cita: str | None = None,
             antes: str = "", despues: str = "") -> dict:
    """Un hilo nuevo sobre el tramo [`inicio`, `fin`) del texto de hoy (en unidades UTF-16, como lo cuenta quien
    selecciona en la página), con su primer comentario. Con `cita`, lo que se veía ahí al seleccionar: si el texto
    cambió desde entonces, se la busca (con `antes` y `despues`) y, si ya no está, 409. Devuelve el hilo ubicado."""
    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        raise ErrorDeComentarios("¿qué dice el comentario? Va vacío", 422)
    with _turno(ruta):
        texto = _texto(ruta)
        i, f = anclaje.de_utf16(texto, inicio), anclaje.de_utf16(texto, fin)
        if cita is not None and texto[i:f] != cita:
            r = anclaje.resolver(texto, anclaje.Ancla(cita=cita, antes=antes, despues=despues, inicio=i, fin=f))
            if r is None or r.metodo not in ("exacto", "contexto", "normalizado") or not cita:
                raise ErrorDeComentarios(f"{Path(ruta).name} cambió desde que se abrió y lo seleccionado ya no está: "
                                         "vuelve a abrirlo", 409)
            i, f = r.inicio, r.fin
        i, f = anclaje.recortar_blancos(texto, i, f)
        if f <= i:
            raise ErrorDeComentarios("no hay texto en lo seleccionado", 422)
        datos = leer(ruta)
        hilo = {"id": _siguiente("h", (h.get("id") for h in datos["hilos"] if isinstance(h, dict))), "estado": "abierto",
                "ancla": _ancla_para_archivo(texto, anclaje.derivar(texto, i, f)), "creado": ahora(),
                "comentarios": [{"id": "c1", "autor": autor, "cuerpo": cuerpo, "fecha": ahora()}]}
        datos["hilos"].append(hilo)
        escribir(ruta, datos)
        return ubicado(texto, hilo)


def _cambiar(ruta: Path, hilo_id: str, cambio) -> dict | None:
    """Lee, aplica `cambio(datos, hilo)` al hilo `hilo_id` y escribe, en su turno. Devuelve el hilo ubicado (None si
    se fue)."""
    with _turno(ruta):
        datos = leer(ruta)
        hilo = next((h for h in datos["hilos"] if isinstance(h, dict) and h.get("id") == hilo_id), None)
        if hilo is None:
            ids = ", ".join(str(h.get("id")) for h in datos["hilos"] if isinstance(h, dict)) or "ninguno"
            raise ErrorDeComentarios(f"{Path(ruta).name} no tiene un hilo {hilo_id} (tiene: {ids})", 404)
        cambio(datos, hilo)
        escribir(ruta, datos)
        if hilo not in datos["hilos"]:
            return None
        try:
            return ubicado(_texto(ruta), hilo)
        except ErrorDeComentarios:
            return ubicado("", hilo)


def _agregar(hilo: dict, cuerpo: str, autor: str) -> None:
    comentarios = hilo.setdefault("comentarios", [])
    comentarios.append({"id": _siguiente("c", (c.get("id") for c in comentarios if isinstance(c, dict))),
                        "autor": autor, "cuerpo": cuerpo, "fecha": ahora()})


def responder(ruta: Path, hilo_id: str, cuerpo: str, autor: str) -> dict:
    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        raise ErrorDeComentarios("¿qué dice la respuesta? Va vacía", 422)
    return _cambiar(ruta, hilo_id, lambda d, h: _agregar(h, cuerpo, autor))


def resolver(ruta: Path, hilo_id: str, cuerpo: str = "", autor: str = "") -> dict:
    """Marca el hilo resuelto («está hecho»), con una respuesta antes si la hay."""

    def hacer(d, h):
        if (cuerpo or "").strip():
            _agregar(h, cuerpo.strip(), autor)
        h["estado"] = "resuelto"

    return _cambiar(ruta, hilo_id, hacer)


def reabrir(ruta: Path, hilo_id: str, cuerpo: str = "", autor: str = "") -> dict:
    def hacer(d, h):
        if (cuerpo or "").strip():
            _agregar(h, cuerpo.strip(), autor)
        h["estado"] = "abierto"

    return _cambiar(ruta, hilo_id, hacer)


def editar(ruta: Path, hilo_id: str, comentario_id: str, cuerpo: str) -> dict:
    """Cambia lo que dice un comentario (su fecha queda la de cuando se escribió)."""
    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        raise ErrorDeComentarios("el comentario quedaría vacío: para quitarlo, bórralo", 422)

    def hacer(d, h):
        c = next((c for c in h.get("comentarios") or [] if isinstance(c, dict) and c.get("id") == comentario_id), None)
        if c is None:
            raise ErrorDeComentarios(f"el hilo {hilo_id} no tiene un comentario {comentario_id}", 404)
        c["cuerpo"] = cuerpo

    return _cambiar(ruta, hilo_id, hacer)


def borrar(ruta: Path, hilo_id: str, comentario_id: str = "") -> dict | None:
    """Borra un comentario del hilo o, sin `comentario_id` (o si era el único), el hilo entero. Devuelve el hilo como
    quedó, o None si se fue."""

    def hacer(d, h):
        if comentario_id:
            antes = h.get("comentarios") or []
            quedan = [c for c in antes if not (isinstance(c, dict) and c.get("id") == comentario_id)]
            if len(quedan) == len(antes):
                raise ErrorDeComentarios(f"el hilo {hilo_id} no tiene un comentario {comentario_id}", 404)
            h["comentarios"] = quedan
        if not comentario_id or not h.get("comentarios"):
            d["hilos"].remove(h)

    return _cambiar(ruta, hilo_id, hacer)
