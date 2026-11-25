"""La copia de una conversación a otra máquina por el bus, de a pedazos: solo lo que allá falta
(docs/propuestas/mudanza-de-hilos.md, B1).

Una conversación de Claude Code (`<proyecto>/<sid>.jsonl`) es un archivo al que solo se le agregan líneas al final, y
junto a ella vive su carpeta (`<proyecto>/<sid>/`: `tool-results/`, `subagents/`, `workflows/`), de archivos que
tampoco se reescriben. Por eso lo que le falta a la copia de allá es siempre la cola de cada archivo, y cuando un hilo
vuelve a una máquina donde ya vivió, allá ya está casi todo.

    mandar(config, maquina, sid, archivo, destino)    de este lado: pregunta qué hay allá, manda lo que falta,
                                                        verifica y lo deja en su lugar allá
    estado(ctx, p)           allá (verbo `replica-estado`, solo lee): de cada archivo, lo que hay a medias de una
                             llegada anterior y lo que hay en su lugar, con la huella de dónde podría cortarse
    escribir(config, meta, datos)    allá (`replica-escribir`): un pedazo, al final de su copia a medias
    cerrar(ctx, p)           allá (`replica-cerrar`): verifica largo y sha256 de cada archivo y los deja donde Claude
                             los busca

Lo que llega se junta en `<estado>/llegadas/<sid>/` y recién verificado pasa a su lugar, así que un corte a mitad no
toca lo que había. Cada pedazo dice desde qué byte va, y allá se agrega solo si su copia a medias llega justo ahí:
repetir uno no duplica nada, y el siguiente intento sigue desde lo que ya se juntó. Si la copia de allá no es un
comienzo de la de aquí (se siguió allá por su lado), se manda entera y la de allá queda aparte, con su fecha.

Los pedazos viajan por una sola conexión al bus, como bytes crudos (una línea JSON con lo que identifica al pedazo, y
después sus bytes), comprimidos con zlib solo si eso los achica, y varios en camino a la vez. No hay tope de tamaño: la
conversación se lee del disco de a pedazos.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import zlib
from collections import deque
from datetime import datetime
from pathlib import Path

from telar import rutas

VERBO_ESTADO = "replica-estado"
VERBO_ESCRIBIR = "replica-escribir"
VERBO_CERRAR = "replica-cerrar"

#: los bytes antes de un corte cuya huella (sha256) dice si dos copias coinciden hasta ahí
HUELLA = 64 * 1024
#: lo que lleva un pedazo, sin comprimir: cabe en un mensaje del bus (1 MB) con su línea de cabecera
TROZO = 896 * 1024
#: los pedazos en camino a la vez: esconden lo que tarda cada ida y vuelta por la red
EN_CAMINO = 6
#: cuánto se espera la respuesta a un pedazo, y a la verificación del final (que lee todo lo que llegó)
ESPERA = 60.0
ESPERA_CERRAR = 300.0
#: los intentos de una copia: después de un corte, el siguiente sigue desde lo que allá ya juntó
INTENTOS = 3
PAUSAS = (2.0, 5.0)
#: de cuántos archivos se pregunta el estado en un pedido
LOTE = 400
#: cuántos lugares de corte ofrece una copia (su largo, y hacia atrás las líneas que no son mensajes)
CORTES = 20
#: una llegada a medias más vieja que esto se borra (segundos)
VIEJA = 3 * 24 * 3600

SID = re.compile(r"^[0-9A-Za-z-]{8,64}$")
#: cada parte de una ruta dentro de la carpeta `<sid>/`
NOMBRE = re.compile(r"^[0-9A-Za-z._-]{1,120}$")


class ErrorDeReplica(Exception):
    """La copia no se completó. El mensaje es para la persona."""


class SinReplica(ErrorDeReplica):
    """La otra máquina no sabe recibir de a pedazos (un telar de antes): se copia como antes."""


# ── lo común ──

def ruta_valida(sid: str, ruta: str) -> bool:
    """Si `ruta` es un archivo de la conversación `sid`, relativo a su carpeta de proyecto: `<sid>.jsonl` o algo dentro
    de `<sid>/`, sin salirse de ahí."""
    if not SID.match(sid or ""):
        return False
    if ruta == f"{sid}.jsonl":
        return True
    partes = ruta.split("/")
    return (2 <= len(partes) <= 6 and partes[0] == sid
            and all(NOMBRE.match(x) and x not in (".", "..") for x in partes[1:]))


def sha(ruta: Path, desde: int = 0, hasta: int | None = None) -> str:
    """El sha256 de los bytes [desde, hasta) del archivo (hasta el final si no se dice), leído de a pedazos."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        f.seek(desde)
        falta = None if hasta is None else max(0, hasta - desde)
        while falta is None or falta > 0:
            b = f.read(1 << 20 if falta is None else min(1 << 20, falta))
            if not b:
                break
            h.update(b)
            if falta is not None:
                falta -= len(b)
    return h.hexdigest()


def huella(ruta: Path, hasta: int) -> str:
    """La huella de una copia en `hasta`: el sha256 de los HUELLA bytes de antes."""
    return sha(ruta, max(0, hasta - HUELLA), hasta)


def _es_mensaje(linea: bytes) -> bool:
    """Una línea de lo que dijeron la persona o el agente. Lo que no se entiende cuenta como mensaje (no se corta ahí);
    una línea vacía, no."""
    if not linea.strip():
        return False
    try:
        d = json.loads(linea)
    except ValueError:
        return True
    return not isinstance(d, dict) or d.get("type") in ("user", "assistant")


def cortes(ruta: Path) -> list[int]:
    """Dónde podría cortarse la copia de aquí para ser el comienzo de una más larga: su largo y, si es una conversación
    (`.jsonl`), cada fin de línea hacia atrás mientras lo de detrás no sea un mensaje (lo que Claude anota al cerrarse:
    su costo, el último prompt) y antes de una línea a medias. Quien manda elige el que calce con lo suyo."""
    largo = ruta.stat().st_size
    salida = [largo]
    if ruta.suffix != ".jsonl" or largo == 0:
        return salida
    desde = max(0, largo - 256 * 1024)
    with open(ruta, "rb") as f:
        f.seek(desde)
        partes = f.read().split(b"\n")
    pos = largo
    if partes[-1]:  # una línea a medias al final (se estaba escribiendo al cerrarse)
        pos -= len(partes[-1])
        salida.append(pos)
    for i in range(len(partes) - 2, -1, -1):
        if len(salida) >= CORTES or (i == 0 and desde > 0) or _es_mensaje(partes[i]):
            break
        pos -= len(partes[i]) + 1
        salida.append(pos)
    return list(dict.fromkeys(salida))


def continua(vieja: Path, nueva: Path) -> bool:
    """Si `nueva` sigue a `vieja`: `vieja`, cortada en alguno de sus `cortes`, es el comienzo de `nueva`. Así la de
    aquí se puede reemplazar sin perder nada (lo que Claude anotó al cerrarse no cuenta)."""
    largo = nueva.stat().st_size
    for c in cortes(vieja):
        if c <= largo and huella(vieja, c) == huella(nueva, c) and sha(vieja, 0, c) == sha(nueva, 0, c):
            return True
    return False


def archivos_de(sid: str, archivo: Path) -> tuple[list[tuple[str, Path, int]], list[str]]:
    """Los archivos de la conversación `sid`, cuyo `.jsonl` es `archivo`: (ruta relativa a su carpeta de proyecto, ruta
    aquí, largo ahora), la conversación primero y lo de su carpeta `<sid>/` después, en orden. Aparte, lo que no se
    manda (un enlace, un nombre que no se acepta allá)."""
    base = Path(archivo).parent
    salida = [(f"{sid}.jsonl", Path(archivo), Path(archivo).stat().st_size)]
    saltados: list[str] = []
    carpeta = base / sid
    if carpeta.is_dir() and not carpeta.is_symlink():
        for p in sorted(carpeta.rglob("*")):
            rel = p.relative_to(base).as_posix()
            if p.is_symlink():
                saltados.append(rel)
                continue
            if not p.is_file():
                continue
            if not ruta_valida(sid, rel):
                saltados.append(rel)
                continue
            salida.append((rel, p, p.stat().st_size))
    return salida, saltados


def mb(n: int) -> str:
    """Un tamaño para la persona: «1,2 MB», «340 KB»."""
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}".replace(".", ",") + " MB"
    return f"{max(1, round(n / 1e3)) if n else 0} KB"


# ── del lado que recibe ──

def carpeta_llegadas(config) -> Path:
    return Path(config.estado) / "llegadas"


def _limpiar_viejas(config, ahora: float | None = None) -> None:
    ahora = time.time() if ahora is None else ahora
    try:
        for d in carpeta_llegadas(config).iterdir():
            if d.is_dir() and ahora - d.stat().st_mtime > VIEJA:
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def destino(ctx, p: dict) -> tuple[Path, str]:
    """Dónde arrancará aquí el agente del hilo, y por eso a qué carpeta de proyecto va su conversación: (inicio,
    aviso). `carpeta` la calculó quien manda (la mudanza por ssh: `~/vida`, o absoluta); si no, `relativa` es la
    carpeta del hilo bajo la raíz de aquí, como al llegar por el bus (telar.mudanza.inicio)."""
    carpeta = str(p.get("carpeta") or "")
    if carpeta:
        return Path(carpeta).expanduser().resolve(), ""
    from telar import mudanza

    inicio, _, aviso = mudanza.inicio(ctx, str(p.get("relativa") or ""))
    return inicio, aviso


def _base(nombre: str) -> Path | None:
    """La carpeta de proyecto `nombre` (un nombre suelto, como la dio `estado`), o None si no sirve."""
    if not nombre or "/" in nombre or nombre in (".", ".."):
        return None
    return rutas.proyectos() / nombre


def estado(ctx, p: dict) -> dict:
    """Lo que hay aquí de cada archivo de la conversación (`rutas`): `parte`, lo juntado de una llegada anterior que
    no terminó, [largo, huella]; `vivo`, la copia en su lugar, [[corte, huella], …] con su largo primero. `base`, la
    carpeta de proyecto donde está la copia de aquí (la de destino si está ahí). No escribe nada."""
    sid = str(p.get("sesion") or "")
    pedidas = p.get("rutas")
    if not SID.match(sid) or not isinstance(pedidas, list) or not all(isinstance(r, str) for r in pedidas):
        return {"ok": False, "error": "falta la conversación o sus archivos"}
    if any(not ruta_valida(sid, r) for r in pedidas):
        return {"ok": False, "error": "un archivo que no es de esa conversación"}
    inicio, _ = destino(ctx, p)
    _limpiar_viejas(ctx.config)
    viva = rutas.conversacion(sid, rutas.proyecto(inicio))
    base = viva.parent if viva is not None else None
    llegada = carpeta_llegadas(ctx.config) / sid
    archivos: dict[str, dict] = {}
    for r in pedidas:
        e: dict = {}
        parte = llegada / r
        if parte.is_file():
            n = parte.stat().st_size
            e["parte"] = [n, huella(parte, n)]
        if base is not None and (base / r).is_file():
            e["vivo"] = [[c, huella(base / r, c)] for c in cortes(base / r)]
        archivos[r] = e
    return {"ok": True, "base": base.name if base is not None else "", "archivos": archivos, "trozo": TROZO}


def _misma_cola(ruta: Path, desde: int, datos: bytes) -> bool:
    with open(ruta, "rb") as f:
        f.seek(desde)
        return f.read(len(datos)) == datos


def escribir(config, meta: dict, datos: bytes) -> dict:
    """Un pedazo de un archivo (`ruta`) de la conversación (`sesion`), que va desde el byte `desde`: al final de lo
    juntado si llega justo ahí. El primero de un archivo (`nuevo`) empieza de nuevo, con los `desde` primeros bytes de
    la copia de aquí (`base`, la carpeta de proyecto que dio `estado`) si no empieza en 0. Repetido (ya está), no hace
    nada. Si no calza, dice cuánto hay ({ok: false, bytes}) y quien manda vuelve a preguntar."""
    sid, ruta = str(meta.get("sesion") or ""), str(meta.get("ruta") or "")
    try:
        desde = int(meta.get("desde") or 0)
    except (TypeError, ValueError):
        desde = -1
    if not ruta_valida(sid, ruta) or desde < 0:
        return {"ok": False, "error": "un pedazo sin conversación, archivo o lugar válidos"}
    if meta.get("z"):
        try:
            d = zlib.decompressobj()
            datos = d.decompress(datos, 2 * TROZO)
            if d.unconsumed_tail:
                return {"ok": False, "error": "un pedazo más grande de lo que se acepta"}
        except zlib.error as e:
            return {"ok": False, "error": f"un pedazo roto: {e}"}
    llegada = carpeta_llegadas(config) / sid
    parte = llegada / ruta
    try:
        parte.parent.mkdir(parents=True, exist_ok=True)
        os.utime(llegada)  # una llegada en curso no es vieja
        if not meta.get("nuevo") and desde > 0:
            n = parte.stat().st_size if parte.is_file() else 0
            if parte.is_file() and n == desde:
                with open(parte, "ab") as f:
                    f.write(datos)
                return {"ok": True, "bytes": n + len(datos)}
            if parte.is_file() and n == desde + len(datos) and _misma_cola(parte, desde, datos):
                return {"ok": True, "bytes": n, "repetido": True}
            return {"ok": False, "bytes": n, "error": f"{ruta}: aquí hay {n} bytes juntados, no {desde}"}
        tmp = parte.with_name(parte.name + ".tmp")
        falta = 0
        with open(tmp, "wb") as g:
            if desde > 0:
                base = _base(str(meta.get("base") or ""))
                viva = base / ruta if base is not None else None
                if viva is None or not viva.is_file() or viva.stat().st_size < desde:
                    g.close()
                    tmp.unlink(missing_ok=True)
                    return {"ok": False, "bytes": 0, "error": f"{ruta}: la copia de aquí ya no es la que se preguntó"}
                with open(viva, "rb") as f:
                    falta = desde
                    while falta > 0:
                        b = f.read(min(1 << 20, falta))
                        if not b:
                            break
                        g.write(b)
                        falta -= len(b)
            g.write(datos)
        if falta:
            tmp.unlink(missing_ok=True)
            return {"ok": False, "bytes": 0, "error": f"{ruta}: la copia de aquí se acortó"}
        tmp.replace(parte)
        return {"ok": True, "bytes": desde + len(datos)}
    except OSError as e:
        return {"ok": False, "error": f"{ruta}: {e}"}


def _aparte(ruta: Path, marca: str) -> Path:
    """Dónde queda una copia que no se reemplaza (se siguió aquí por su lado): `<sid>.antes-<fecha>.jsonl.bak`, al lado,
    con un nombre que nadie busca."""
    for n in range(100):
        extra = f"-{n}" if n else ""
        candidato = ruta.with_name(f"{ruta.stem}.antes-{marca}{extra}{ruta.suffix}.bak")
        if not candidato.exists():
            return candidato
    return ruta.with_name(f"{ruta.name}.antes-{marca}-{os.getpid()}.bak")


def cerrar(ctx, p: dict) -> dict:
    """Verifica cada archivo de la conversación (`archivos`: {ruta: [largo, sha256]}) con lo juntado o con la copia de
    aquí, y si todos calzan, los deja donde Claude los busca: la carpeta de proyecto del agente que arranca en el
    destino (`carpeta` o `relativa`, como en `destino`). Una copia de aquí que lo que llega no continúa queda aparte,
    con su fecha. Si alguno no calza, no mueve nada y dice cuáles ({ok: false, problemas: {ruta: incompleto | distinto
    | falta}}): lo distinto se borra, para mandarlo de nuevo entero."""
    sid = str(p.get("sesion") or "")
    pedidos = p.get("archivos")
    if not SID.match(sid) or not isinstance(pedidos, dict) or f"{sid}.jsonl" not in pedidos:
        return {"ok": False, "error": "falta la conversación o sus archivos"}
    inicio, _ = destino(ctx, p)  # lo que avisa del destino (su carpeta sin clonar) lo dice quien abre el hilo
    final = rutas.proyecto(inicio)
    base = _base(str(p.get("base") or ""))
    llegada = carpeta_llegadas(ctx.config) / sid
    aviso = ""
    problemas: dict[str, str] = {}
    origen: dict[str, Path | None] = {}
    for ruta, valor in pedidos.items():
        try:
            n, suyo = int(valor[0]), str(valor[1])
        except (TypeError, ValueError, IndexError, KeyError):
            n, suyo = -1, ""
        if not ruta_valida(sid, ruta) or n < 0:
            return {"ok": False, "error": f"un archivo que no es de esa conversación: {ruta}"}
        parte = llegada / ruta
        m = parte.stat().st_size if parte.is_file() else -1
        if m == n and sha(parte) == suyo:
            origen[ruta] = parte
            continue
        viva = base / ruta if base is not None else None
        if viva is not None and viva.is_file() and viva.stat().st_size == n and sha(viva) == suyo:
            # la copia de aquí ya es esa: lo juntado de otra vez, si había, sobra
            parte.unlink(missing_ok=True)
            origen[ruta] = None if base == final else viva
            continue
        if 0 <= m < n:
            problemas[ruta] = "incompleto"
        elif m >= 0:
            problemas[ruta] = "distinto"
            parte.unlink(missing_ok=True)
        else:
            problemas[ruta] = "falta"
    if problemas:
        return {"ok": False, "problemas": problemas,
                "error": f"no calzan {len(problemas)} archivo{'s' if len(problemas) != 1 else ''}: "
                         + ", ".join(f"{r} ({m})" for r, m in list(problemas.items())[:5])}
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    apartes: list[str] = []
    try:
        final.mkdir(parents=True, exist_ok=True)
        for ruta, de in origen.items():
            if de is None:
                continue  # ya está, igual, en su lugar
            a = final / ruta
            if a.is_file() and not continua(a, de):
                b = _aparte(a, marca)
                a.replace(b)
                apartes.append(b.relative_to(final).as_posix())
            a.parent.mkdir(parents=True, exist_ok=True)
            if de.is_relative_to(llegada):
                de.replace(a)
            else:
                tmp = a.with_name(a.name + ".tmp")
                shutil.copyfile(de, tmp)
                tmp.replace(a)
            a.chmod(0o600)
        # la copia de aquí estaba en otra carpeta de proyecto (el hilo arrancaba en otra parte): que no quede otra con
        # el mismo id, que Claude o telar podrían encontrar primero. Si la nueva la sigue, sobra; si no, aparte
        if base is not None and base != final and (base / f"{sid}.jsonl").is_file():
            vieja = base / f"{sid}.jsonl"
            if continua(vieja, final / f"{sid}.jsonl"):
                vieja.unlink()
            else:
                b = _aparte(vieja, marca)
                vieja.replace(b)
                apartes.append(str(b))
    except OSError as e:
        return {"ok": False, "error": f"no pude dejarla en su lugar: {e}"}
    shutil.rmtree(llegada, ignore_errors=True)
    if apartes:
        aviso = (aviso + "; " if aviso else "") + (
            "la copia de aquí se había seguido por su lado: quedó en " + ", ".join(apartes[:3])
            + (f" y {len(apartes) - 3} más" if len(apartes) > 3 else ""))
    return {"ok": True, "conversacion": str(final / f"{sid}.jsonl"), "carpeta": str(inicio), "aparte": apartes,
            "aviso": aviso}


def recibir(m_data: bytes) -> tuple[dict, bytes]:
    """Un pedazo como llega por el bus: su línea JSON de cabecera y sus bytes."""
    cabeza, _, datos = bytes(m_data).partition(b"\n")
    meta = json.loads(cabeza or b"{}")
    if not isinstance(meta, dict):
        raise ValueError("la cabecera no es un objeto")
    return meta, datos


# ── del lado que manda ──

def _pedazo(meta: dict, datos: bytes) -> tuple[bytes, int]:
    """Cómo viaja un pedazo (`recibir` lo deshace): (cuerpo, bytes por la red)."""
    if len(datos) > 4096:
        comprimido = zlib.compress(datos, 6)
        if len(comprimido) < len(datos) * 0.9:
            meta, datos = {**meta, "z": 1}, comprimido
    cuerpo = json.dumps(meta, ensure_ascii=True).encode() + b"\n" + datos
    return cuerpo, len(cuerpo)


def _desde(ruta_aqui: Path, largo: int, e: dict, de_cero: bool) -> tuple[int, str, bool]:
    """Desde qué byte se manda un archivo, según lo que hay allá (`e`, de `estado`): (desde, de dónde sigue allá
    —«parte», «vivo» o «»—, si no hay que mandar nada)."""
    if de_cero:
        return 0, "", False
    parte = e.get("parte")
    if parte and int(parte[0]) <= largo and parte[1] == huella(ruta_aqui, int(parte[0])):
        return int(parte[0]), "parte", int(parte[0]) == largo
    vivo = e.get("vivo") or []
    for c, h in vivo:
        c = int(c)
        if c <= largo and h == huella(ruta_aqui, c):
            # igual entera: nada que mandar; cortada (lo que anotó Claude al cerrarse allá): un pedazo vacío la corta
            return c, "vivo", c == largo and c == int(vivo[0][0])
    return 0, "", False


async def _una_vez(pedir, maximo: int, sid: str, archivos, destino_: dict, de_cero: set, cuenta: dict,
                   al_avanzar) -> dict:
    """Un intento: preguntar, mandar lo que falta y cerrar. `cuenta` suma lo mandado entre intentos."""
    from telar import bus as mod_bus

    async def pedir_json(verbo: str, datos: dict, espera: float) -> dict:
        r = mod_bus.desempacar(await pedir(verbo, json.dumps(datos, ensure_ascii=False).encode(), espera))
        return r if isinstance(r, dict) else {"ok": False, "error": "una respuesta que no se entiende"}

    # lo que hay allá, de a lotes; los sha256 de aquí, mientras tanto
    shas = asyncio.ensure_future(asyncio.to_thread(lambda: {r: sha(p, 0, n) for r, p, n in archivos}))
    try:
        hay: dict[str, dict] = {}
        base, trozo = "", TROZO
        for i in range(0, len(archivos), LOTE):
            r = await pedir_json(VERBO_ESTADO, {"sesion": sid, "rutas": [a[0] for a in archivos[i:i + LOTE]],
                                                **destino_}, ESPERA)
            if not r.get("ok"):
                raise ErrorDeReplica(str(r.get("error") or "no contestó"))
            hay.update(r.get("archivos") or {})
            base = str(r.get("base") or "")
            trozo = int(r.get("trozo") or TROZO)
        trozo = max(16 * 1024, min(trozo, TROZO, maximo - 16 * 1024))
        plan = []
        for ruta, p, n in archivos:
            d, sigue, nada = _desde(p, n, hay.get(ruta) or {}, ruta in de_cero)
            if not nada:
                plan.append((ruta, p, d, n, sigue))
        cuenta["por_mandar"] = sum(n - d for _, _, d, n, _ in plan)
        cuenta["mandados_ahora"] = 0
        if al_avanzar:
            al_avanzar(cuenta)

        en_camino: deque = deque()

        async def uno(cuerpo: bytes, crudos: int) -> int:
            r = mod_bus.desempacar(await pedir(VERBO_ESCRIBIR, cuerpo, ESPERA))
            if not isinstance(r, dict) or not r.get("ok"):
                raise ErrorDeReplica(str((r or {}).get("error") or "un pedazo no llegó"))
            return crudos

        async def esperar_uno() -> None:
            crudos = await en_camino.popleft()
            cuenta["mandados_ahora"] += crudos
            cuenta["mandados"] = cuenta.get("mandados", 0) + crudos
            if al_avanzar:
                al_avanzar(cuenta)

        try:
            for ruta, p, d, n, sigue in plan:
                meta = {"sesion": sid, "ruta": ruta, **({"base": base} if sigue == "vivo" else {})}
                # el primero de un archivo que no sigue lo juntado allá empieza de nuevo (lo juntado, si había, no sirve)
                nuevo = sigue != "parte"
                with open(p, "rb") as f:
                    f.seek(d)
                    pos, primero = d, True
                    while pos < n or primero:
                        datos = f.read(min(trozo, n - pos))
                        # comprimir, aparte: mientras, los pedazos en camino siguen su ida y vuelta
                        cuerpo, red = await asyncio.to_thread(
                            _pedazo, {**meta, "desde": pos, **({"nuevo": 1} if nuevo else {})}, datos)
                        nuevo = False
                        cuenta["red"] = cuenta.get("red", 0) + red
                        en_camino.append(asyncio.ensure_future(uno(cuerpo, len(datos))))
                        while len(en_camino) >= EN_CAMINO:
                            await esperar_uno()
                        pos += len(datos)
                        primero = False
                        if not datos:
                            break
            while en_camino:
                await esperar_uno()
        finally:
            for t in en_camino:
                t.cancel()
            if en_camino:
                await asyncio.gather(*en_camino, return_exceptions=True)
        sumas = await shas
        r = await pedir_json(VERBO_CERRAR, {"sesion": sid, "base": base, **destino_,
                                             "archivos": {ruta: [n, sumas[ruta]] for ruta, _, n in archivos}},
                             ESPERA_CERRAR)
        return r
    finally:
        if not shas.done():
            shas.cancel()


def _corrida(config, maquina: str, hacer):
    """`hacer(pedir, maximo)` con una conexión al bus: la del nodo de este proceso si la hay, o una propia que se cierra
    al terminar. `pedir(verbo, cuerpo, espera)` devuelve los bytes de la respuesta; si nadie atiende ese verbo allá,
    SinReplica."""
    from telar import bus as mod_bus

    async def con(nc):
        async def pedir(verbo: str, cuerpo: bytes, espera: float) -> bytes:
            try:
                r = await nc.request(mod_bus.tema_rpc(config, maquina, verbo), cuerpo, timeout=espera)
            except Exception as e:  # noqa: BLE001
                if "NoResponders" in type(e).__name__:
                    raise SinReplica(f"{maquina} no atiende «{verbo}» (¿un telar de antes, o sin su nodo?)") from e
                raise
            return r.data

        maximo = getattr(nc, "max_payload", None)
        return await hacer(pedir, maximo if isinstance(maximo, int) and maximo > 0 else 1 << 20)

    async def propia():
        nc = await mod_bus.conectar(config)
        try:
            return await con(nc)
        finally:
            try:
                await nc.close()
            except Exception:  # noqa: BLE001
                pass

    viva = mod_bus._conexion_viva()
    if viva is not None:
        nc, bucle = viva
        return asyncio.run_coroutine_threadsafe(con(nc), bucle).result()
    return asyncio.run(propia())


def mandar(config, maquina: str, sid: str, archivo: Path, destino_: dict, *, al_avanzar=None,
           intentos: int = INTENTOS, pausas=PAUSAS, corrida=None) -> dict:
    """La conversación `sid` (su `.jsonl`, `archivo`, y su carpeta `<sid>/`) a la máquina `maquina`, dejándola donde
    Claude la busca allá (`destino_`: {"relativa": …} por el bus, {"carpeta": …} por ssh). Manda solo lo que allá
    falta; si se corta, lo intenta otra vez desde lo que allá ya juntó. `al_avanzar(cuenta)` se llama con lo que va:
    {por_mandar, mandados_ahora, red}. Devuelve {bytes, mandados, red, archivos, conversacion, carpeta, aparte,
    aviso, saltados}. SinReplica si allá no saben recibirla así; ErrorDeReplica si no se completó (lo que llegó queda
    allá, y el próximo intento sigue desde ahí)."""
    from telar import bus as mod_bus

    archivos, saltados = archivos_de(sid, archivo)
    total = sum(n for _, _, n in archivos)
    corrida = corrida or (lambda hacer: _corrida(config, maquina, hacer))
    cuenta: dict = {"total": total, "archivos": len(archivos)}
    de_cero: set[str] = set()
    ultimo = ""
    for intento in range(max(1, intentos)):
        try:
            r = corrida(lambda pedir, maximo: _una_vez(pedir, maximo, sid, archivos, destino_, de_cero, cuenta,
                                                       al_avanzar))
        except SinReplica:
            raise
        except (ErrorDeReplica, mod_bus.ErrorDeBus) as e:
            ultimo = str(e)
            r = None
        except Exception as e:  # noqa: BLE001 - un corte de la red, un plazo: otra vez, desde lo que llegó
            ultimo = f"{type(e).__name__}: {e}".strip(": ")[:200] or "se cortó"
            r = None
        if r is not None and r.get("ok"):
            return {"bytes": total, "conversacion_bytes": archivos[0][2], "mandados": cuenta.get("mandados", 0),
                    "red": cuenta.get("red", 0),
                    "archivos": len(archivos), "conversacion": r.get("conversacion", ""),
                    "carpeta": r.get("carpeta", ""), "aparte": r.get("aparte") or [], "aviso": r.get("aviso", ""),
                    "saltados": saltados}
        if r is not None:
            ultimo = str(r.get("error") or "no se pudo cerrar")
            # lo que no calzó entero (una huella que coincidía por azar): de nuevo, desde el comienzo
            de_cero |= {ruta for ruta, m in (r.get("problemas") or {}).items() if m == "distinto"}
        if intento + 1 < intentos:
            time.sleep(pausas[min(intento, len(pausas) - 1)] if pausas else 0)
    raise ErrorDeReplica(f"la copia a {maquina} se cortó ({ultimo}); van {mb(cuenta.get('mandados', 0))} de "
                         f"{mb(cuenta.get('por_mandar', total))}, que quedan allá: el próximo intento sigue desde ahí")
