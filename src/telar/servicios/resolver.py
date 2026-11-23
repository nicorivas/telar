"""Dónde está un archivo que nombró el agente de un hilo, cuando la ruta sola no basta para encontrarlo.

Un agente escribe a menudo «En `personal/referencia/artículos/x/`:» y abajo «`original.md` — el texto íntegro»: el
nombre suelto es de la carpeta nombrada antes, no de la raíz ni de la carpeta del hilo. La página (un clic en una
ruta de la terminal, la conversación o la lectura de un hilo, web/rutas-agente.ts) manda la ruta como se escribió, la
carpeta del hilo y las carpetas que se nombraron antes en el mismo mensaje (la más cercana primero), y aquí se busca,
en este orden:

1. **Contra lo que dice el mensaje.** Un nombre suelto (sin `/`), primero bajo las carpetas nombradas (la más
   cercana que lo tenga), después en la carpeta del hilo y en la raíz: así el `README.md` de debajo de una carpeta
   nombrada no se confunde con el de la raíz. Una ruta con carpetas, al revés: primero tal cual (desde la carpeta
   del hilo, desde la raíz) y después bajo las nombradas. Una carpeta nombrada puede ser relativa a la del hilo o a
   la raíz, o entera.
2. **Por nombre.** Si no aparece, se busca en la raíz (y en la carpeta del hilo, si está fuera de ella) un archivo
   con ese nombre (con esas últimas carpetas, si la ruta las trae): uno se abre; varios vuelven como candidatos, los
   más cercanos a lo que dice el mensaje primero (bajo una carpeta nombrada, bajo la del hilo, con más carpetas en
   común), para que el visor los ofrezca en vez de decir «no existe».

Las tildes no estorban: un nombre escrito con `í` compuesta (NFC) encuentra el del disco aunque esté descompuesto
(NFD, como los guarda a veces macOS), y al revés. Solo lo legible cuenta (`archivos.legible`: la raíz, `[repos]`, las
carpetas de los hilos): la búsqueda no sale de ahí ni sigue enlaces simbólicos. Las rutas vuelven como las pide el
visor: relativas a la raíz, o enteras (con `~`) si están fuera.

En otra máquina lo hace su nodo (`archivo-leer` con `resolver`, por el bus), con su raíz y sus límites. Un nodo de
antes no lo conoce: vuelve sin nada, y la página prueba como antes.

Lo usa `GET /archivos/resolver` de la API.
"""

from __future__ import annotations

import os
import time
import unicodedata
from pathlib import Path

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio

#: cuántas carpetas nombradas se miran, cuántos candidatos vuelven y cuánto puede durar la búsqueda por nombre
TOPE_CONTEXTO = 24
TOPE_CANDIDATOS = 30
TOPE_SEGUNDOS = 4.0
#: las carpetas donde no se busca por nombre (además de las ocultas)
NO_BUSCAR = {"node_modules", "__pycache__", "venv", "site-packages", "dist", "build", "target"}


class Resolucion(BaseModel):
    #: la ruta que se abre, si es una sola; vacía si no se encontró o si hay varias
    ruta: str = ""
    #: las que se llaman así, si hay más de una: la más cercana a lo que dice el mensaje primero
    candidatos: list[str] = []
    #: si había más candidatos que los que vuelven, o la búsqueda se cortó por tiempo
    mas: bool = False
    #: la máquina donde se buscó, si fue en otra
    maquina: str = ""


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _variantes(p: Path) -> list[Path]:
    """La ruta, y sus formas NFC y NFD si son otras: en Linux, «artículos» compuesto y descompuesto son dos nombres."""
    s = str(p)
    return list(dict.fromkeys(Path(x) for x in (s, unicodedata.normalize("NFC", s), unicodedata.normalize("NFD", s))))


def _archivo(ctx, p: Path) -> Path | None:
    """`p` (o una de sus variantes de tildes), resuelta, si es un archivo que la página puede leer."""
    from telar.servicios import archivos

    for v in _variantes(p):
        try:
            r = v.resolve()
        except (OSError, RuntimeError):
            continue
        if r.is_file() and archivos.legible(ctx, r):
            return r
    return None


def _como(ctx, p: Path) -> str:
    """Cómo se dice `p` para el visor: relativa a la raíz, o entera (con `~` si está en la carpeta personal)."""
    from telar.servicios import archivos, documentos

    raiz = archivos._raiz(ctx)
    return os.path.relpath(p, raiz) if archivos._dentro(p, raiz) else documentos._nombrar(p)


def resolver(ctx, ruta: str, carpeta: str = "", contexto: list[str] | tuple[str, ...] = ()) -> Resolucion:
    """Dónde está `ruta` (como la escribió el agente), con la carpeta de su hilo (`carpeta`: entera, o relativa a la
    raíz) y las carpetas nombradas antes en su mensaje (`contexto`, la más cercana primero). Ver el docstring del
    módulo."""
    from telar.servicios import archivos

    ruta = (ruta or "").strip()
    if not ruta or "\x00" in ruta or any("\x00" in c for c in (carpeta, *contexto)):
        raise ErrorDeServicio("¿qué archivo?", 422)
    raiz = archivos._raiz(ctx)

    def entera(c: str) -> Path:
        p = Path(c).expanduser()
        return p if p.is_absolute() else raiz / p

    pedida = Path(ruta).expanduser()
    hilo = entera(carpeta) if carpeta else None
    if pedida.is_absolute():
        if (r := _archivo(ctx, pedida)) is not None:
            return Resolucion(ruta=_como(ctx, r))
        bases: list[Path] = []
        nombradas: list[Path] = []
    else:
        nombradas = []
        for c in [c for c in contexto if c.strip()][:TOPE_CONTEXTO]:
            p = Path(c.strip()).expanduser()
            nombradas += [p] if p.is_absolute() else [*([hilo / p] if hilo else []), raiz / p]
        tal_cual = [*([hilo] if hilo else []), raiz]
        bases = [*nombradas, *tal_cual] if len(pedida.parts) == 1 else [*tal_cual, *nombradas]
    for b in bases:
        if (r := _archivo(ctx, b / pedida)) is not None:
            return Resolucion(ruta=_como(ctx, r))

    # 2. por nombre, en la raíz y en la carpeta del hilo si está fuera de ella
    # de una entera (quizás de otra máquina, o de antes de una mudanza), solo el nombre y su carpeta
    cola = [_nfc(x) for x in pedida.parts if x not in ("/", "~", ".", "..")][-2 if pedida.is_absolute() else 0:]
    if not cola:
        return Resolucion()
    donde = [raiz]
    if hilo is not None:
        try:
            h = hilo.resolve()
        except OSError:
            h = None
        if h is not None and h.is_dir() and not archivos._dentro(h, raiz) and (b := archivos.base_de(ctx, h)) is not None:
            donde.append(b)
    hallados, cortada = _por_nombre(ctx, cola, donde)
    if not hallados:
        return Resolucion(mas=cortada)
    cerca = [*[_resuelta(n) for n in nombradas], *([_resuelta(hilo)] if hilo else [])]
    hallados.sort(key=lambda p: _cercania(p, [c for c in cerca if c is not None], hilo and _resuelta(hilo)))
    nombres = [_como(ctx, p) for p in hallados]
    if len(nombres) == 1:
        return Resolucion(ruta=nombres[0], candidatos=nombres, mas=cortada)
    return Resolucion(candidatos=nombres[:TOPE_CANDIDATOS], mas=cortada or len(nombres) > TOPE_CANDIDATOS)


def _resuelta(p: Path | None) -> Path | None:
    if p is None:
        return None
    try:
        return p.resolve()
    except OSError:
        return None


def _por_nombre(ctx, cola: list[str], donde: list[Path]) -> tuple[list[Path], bool]:
    """Los archivos legibles bajo `donde` cuya ruta termina en `cola` (sus últimos tramos, en NFC), sin entrar en lo
    oculto ni en `NO_BUSCAR` ni seguir enlaces. True de segundo si se cortó por tiempo."""
    from telar.servicios import archivos

    nombre, carpetas = cola[-1], cola[:-1]
    hasta = time.monotonic() + TOPE_SEGUNDOS
    hallados: list[Path] = []
    vistos: set[Path] = set()
    for base in donde:
        for d, subs, nombres in os.walk(base):
            if time.monotonic() > hasta:
                return hallados, True
            subs[:] = [s for s in subs if not s.startswith(".") and s not in NO_BUSCAR]
            for n in nombres:
                if _nfc(n) != nombre:
                    continue
                p = Path(d) / n
                if carpetas and [_nfc(x) for x in p.parent.parts[-len(carpetas):]] != carpetas:
                    continue
                r = _resuelta(p)
                if r is not None and r not in vistos and r.is_file() and archivos.legible(ctx, r):
                    vistos.add(r)
                    hallados.append(r)
    return hallados, False


def _cercania(p: Path, cerca: list[Path], hilo: Path | None) -> tuple:
    """Para ordenar los candidatos: bajo la carpeta nombrada más cercana (o la del hilo) primero; después, los que
    tienen más carpetas en común con ellas; después, los más cortos."""
    from telar.servicios import archivos

    debajo = next((i for i, c in enumerate(cerca) if archivos._dentro(p, c)), len(cerca))
    comun = max((len(os.path.commonpath([p, c]).split(os.sep)) for c in cerca), default=0) if cerca else 0
    return (debajo, -comun, len(p.parts), str(p))


def resolver_en(ctx, ruta: str, carpeta: str = "", contexto: list[str] | tuple[str, ...] = (),
                maquina: str = "") -> Resolucion:
    """`resolver`, aquí o en `maquina` (por el bus, a su nodo: `archivo-leer` con `resolver`). Un nodo de antes no
    lo conoce y vuelve sin nada."""
    from telar import bus as mod_bus

    if not maquina or not mod_bus.hay_bus(ctx.config) or maquina == mod_bus.maquina(ctx.config):
        return resolver(ctx, ruta, carpeta, contexto)
    # sin `ruta` de primer nivel: un nodo de antes contesta «¿qué archivo?» y no lee nada
    r = mod_bus.pedir(ctx.config, maquina, "archivo-leer",
                      {"resolver": {"ruta": ruta, "carpeta": carpeta, "contexto": list(contexto)}}, espera=20)
    if r.get("ok") and isinstance(r.get("resolucion"), dict):
        return Resolucion.model_validate({**r["resolucion"], "maquina": maquina})
    if r.get("ok") is False and r.get("codigo") not in (None, 422):
        raise ErrorDeServicio(r.get("error") or f"{maquina} no pudo buscar {ruta}", int(r.get("codigo") or 502))
    return Resolucion(maquina=maquina)


def para_otra(ctx, pedido: dict) -> dict:
    """Lo que responde el nodo a `archivo-leer` con `resolver`."""
    try:
        return {"ok": True, "resolucion": resolver(ctx, str(pedido.get("ruta", "")), str(pedido.get("carpeta", "")),
                                                   [str(c) for c in pedido.get("contexto") or []]).model_dump()}
    except ErrorDeServicio as e:
        return {"ok": False, "error": str(e), "codigo": e.codigo}
