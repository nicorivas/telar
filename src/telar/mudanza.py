"""Llevar un hilo a otra máquina de la persona por el bus: su conversación viaja, y allá se retoma.

Es `telar hilo llevar <hilo> <máquina>` cuando la máquina no está en `[remotos]` (que van por ssh) sino en el bus:
otra máquina de la misma persona, como su lugar en un servidor (telar.alojamiento), que no tiene ssh para ella.

    enviar(ctx, hilo, maquina, sid, archivo, relativa)        de este lado: la manda y le pide retomarla
    llegar(ctx, pedido)                                       del otro (el nodo, verbo `hilo-llegar`): la deja donde
                                                              el agente la busca y abre el hilo retomándola
    traer_aqui(ctx, pedido)                                   el dueño del hilo, cuando otra máquina lo pide
                                                              (verbo `hilo-traer`, «traer a esta máquina»): lo
                                                              lleva a la que pide, con `telar hilo llevar`

La conversación va comprimida por el mismo camino que un archivo (telar.entrega.archivo: en trozos, hasta 25 MB
comprimida) y llega a la carpeta de entrada de allá; `hilo-llegar` la saca de ahí. Los archivos no viajan: si la
carpeta del hilo no existe allá (un repositorio sin clonar), el hilo se abre en la raíz y el agente recuerda la
conversación sin esos archivos.
"""

from __future__ import annotations

import gzip
import re
import tempfile
from datetime import datetime
from pathlib import Path

#: el verbo del nodo que recibe
VERBO = "hilo-llegar"
#: el que pregunta antes, sin mover nada, si allá se puede recibir (`revisar`)
VERBO_REVISAR = "hilo-revisar"
#: los pasos de una mudanza, en orden: lo que la página muestra mientras ocurre (`progreso`)
PASOS = ("revisar", "cerrar", "copiar", "abrir", "listo")


class ErrorDeMudanza(Exception):
    pass


def ruta_progreso(config, hilo: str) -> Path:
    from telar import casilla

    d = Path(config.estado) / "llevar"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{casilla.nombre_de_carpeta(hilo)}.json"


def progreso(config, hilo: str, paso: str, **datos) -> None:
    """Deja escrito en qué va la mudanza de `hilo` (`<estado>/llevar/<hilo>.json`): el paso (de `PASOS`, o «falla»),
    a qué máquina, cuánto pesa la conversación y lo que haya que decir. La página lo lee mientras ocurre (GET
    /hilo/llevar/progreso) para dibujar la transición. Un error al escribirlo no detiene la mudanza."""
    import json
    import time

    try:
        ruta = ruta_progreso(config, hilo)
        antes = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() and paso != "revisar" else {}
        antes.update(datos, paso=paso, hilo=hilo, hora=time.time())
        tmp = ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps(antes, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ruta)
    except (OSError, ValueError):
        pass


def revisar(ctx, p: dict) -> dict:
    """Del lado que recibiría, sin mover nada: lo que haría fallar la llegada de este hilo (`graves`: no se lleva) y lo
    que haría que llegue a medias (`avisos`: se pregunta). Lo que ya falló en un telar alojado: sin agente declarado,
    sin `claude` en el PATH del servicio, la carpeta del hilo sin clonar."""
    import shutil

    from telar.agente import claude_code
    from telar.ordenes import _comun

    hilo, sid = str(p.get("hilo") or "").strip(), str(p.get("sesion") or "")
    relativa = str(p.get("relativa") or "")
    graves, avisos = [], []
    if sid and ctx.config.agente.nombre != claude_code.NOMBRE:
        graves.append(f"aquí el agente de los hilos es «{ctx.config.agente.nombre or 'ninguno'}»: una conversación de"
                      f" Claude no se retoma ([agente] nombre = \"{claude_code.NOMBRE}\" en su configuración)")
    if sid and not shutil.which("claude"):
        graves.append("aquí el servicio de telar no encuentra `claude` en su PATH (falta ~/.local/bin en su servicio:"
                      " telar instalar lo arregla)")
    tel = _comun.tejer(ctx, con_ficha=False)
    if hilo in tel.vivos and tel.estado.remotos().get(hilo) is None:
        graves.append(f"aquí ya hay un hilo «{hilo}» abierto")
    if relativa and not relativa.startswith("/") and not (Path(ctx.config.raiz) / relativa).is_dir():
        avisos.append(f"su carpeta ({relativa}) no existe aquí: se abriría en la raíz, sin sus archivos"
                      " (¿falta clonar su repositorio?)")
    # la conversación ya escrita aquí no impide nada: es la copia de cuando el hilo se fue de esta máquina (traerlo de
    # vuelta), y al llegar se reemplaza por la de allá (`llegar`). Lo que sí impediría, un hilo vivo con ese nombre,
    # ya se revisó arriba
    return {"ok": True, "graves": graves, "avisos": avisos}


def maquinas_del_bus(config) -> list[str]:
    """Las otras máquinas de la persona que se ven en el bus (sus fotos), las que estén en línea."""
    from telar import espejo

    try:
        return [e["nombre"] for e in espejo.leer_todos(config) if e.get("en_linea") and not e.get("error")]
    except Exception:  # noqa: BLE001
        return []


def enviar(ctx, hilo: str, maquina: str, sid: str, archivo: Path | None, relativa: str, al_abrir=None) -> dict:
    """Manda la conversación `sid` (su `.jsonl`) a `maquina` y le pide abrir ahí el hilo retomándola. Devuelve lo
    que contestó allá: {ok, carpeta, aviso}. ErrorDeMudanza si no se pudo."""
    from telar import bus as mod_bus
    from telar import entrega

    r, datos = {}, b""
    if archivo is not None:
        datos = Path(archivo).read_bytes()
        with tempfile.TemporaryDirectory() as d:
            gz = Path(d) / f"{sid}.jsonl.gz"
            gz.write_bytes(gzip.compress(datos, 6))
            try:
                r = entrega.archivo(ctx.config, gz, a=maquina, nombre=gz.name)
            except entrega.ErrorDeEntrega as e:
                raise ErrorDeMudanza(f"la conversación no llegó a {maquina}: {e}") from None
    # sin conversación (un hilo sin mensajes todavía): allá se abre con una nueva
    if al_abrir is not None:
        al_abrir()  # la conversación ya está allá: lo que sigue es abrir el hilo
    r = mod_bus.pedir(ctx.config, maquina, VERBO, {"hilo": hilo, "sesion": sid if archivo is not None else "",
                                                   "relativa": relativa, "archivo": r.get("ruta", ""),
                                                   "bytes": len(datos)}, espera=60)
    if not r.get("ok"):
        raise ErrorDeMudanza(f"{maquina} recibió la conversación pero no abrió el hilo: {r.get('error', 'no respondió')}")
    return r


SID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def llegar(ctx, p: dict) -> dict:
    """Del lado que recibe: la conversación que dejó `entrega.archivo` en la carpeta de entrada, a donde el agente la
    busca al arrancar en la carpeta del hilo; el hilo, anotado con ella y abierto retomándola."""
    from telar import entrega
    from telar.agente import lanzar
    from telar.ordenes import _comun

    hilo, sid = str(p.get("hilo") or "").strip(), str(p.get("sesion") or "")
    relativa = str(p.get("relativa") or "")
    # sin `sesion`: un hilo sin mensajes todavía, que se abre aquí con una conversación nueva
    if not hilo or (sid and not SID.match(sid)):
        return {"ok": False, "error": "falta el hilo, o su conversación no es un id"}
    from telar.agente import claude_code

    if sid and ctx.config.agente.nombre != claude_code.NOMBRE:
        return {"ok": False, "error": f"aquí el agente es «{ctx.config.agente.nombre or 'ninguno'}»: solo se retoma una de Claude"}
    datos, gz = b"", None
    if sid:
        # solo lo que dejó el archivo de entrada: un nombre suelto, dentro de su carpeta
        entrada = entrega.carpeta_de_entrada(ctx.config)
        gz = (entrada / Path(str(p.get("archivo") or "")).name)
        if not gz.name.endswith(".jsonl.gz") or not gz.is_file():
            return {"ok": False, "error": "la conversación no está en la carpeta de entrada"}
        try:
            datos = gzip.decompress(gz.read_bytes())
        except (OSError, EOFError, gzip.BadGzipFile) as e:
            return {"ok": False, "error": f"la conversación llegó rota: {e}"}
        if len(datos) != int(p.get("bytes") or -1):
            return {"ok": False, "error": f"llegaron {len(datos)} de {p.get('bytes')} bytes: no la retomo cortada"}

    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None:
        return {"ok": False, "error": tel.aviso or "aquí no hay multiplexor"}
    if not tel.viva:
        # sin sesión (un lugar recién creado en un servidor, que nadie abrió todavía): se levanta vacía, como
        # `telar tejer --vacia`, y el hilo que llega es el primero
        try:
            tel.mux.tejer()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"aquí la sesión no está viva y no pude levantarla: {e}"}
        tel = _comun.tejer(ctx, con_ficha=False)
        if not tel.viva:
            return {"ok": False, "error": tel.aviso or "aquí la sesión no está viva"}
    remoto = tel.estado.remotos().get(hilo)
    if hilo in tel.vivos and remoto is None:
        return {"ok": False, "error": f"aquí ya hay un hilo «{hilo}» abierto"}
    if remoto is not None:
        # aquí había una ventana que solo miraba el hilo de allá: se cierra, y desde ahora vive aquí
        viejo = next((h for h in tel.mux.hilos() if h.nombre == hilo), None)
        if viejo is not None:
            try:
                tel.mux.cerrar(viejo.id)
            except Exception:  # noqa: BLE001 - si no se cierra, queda una ventana de más, nada se pierde
                pass
        tel.estado.olvidar_remoto(hilo)
    carpeta_hilo = Path(ctx.config.raiz) / relativa if relativa and not relativa.startswith("/") else (
        Path(relativa) if relativa else None)
    aviso = ""
    if carpeta_hilo is not None and not carpeta_hilo.is_dir():
        aviso = f"su carpeta ({relativa}) no existe aquí: se abre en la raíz, sin esos archivos"
        carpeta_hilo = None
    # donde arranca el agente, y ahí la busca Claude: ~/.claude/projects/<la carpeta, con - por lo que no es letra>
    inicio = (lanzar.carpeta(ctx.config, carpeta_hilo) or Path(ctx.config.raiz)).resolve()
    ruta = None
    if sid:
        destino = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(inicio))
        destino.mkdir(parents=True, exist_ok=True)
        ruta = destino / f"{sid}.jsonl"
        # ya hay una aquí: la copia de cuando el hilo se fue de esta máquina, y vuelve. Si la que llega la continúa
        # (empieza igual), es la misma, más larga: se reemplaza. Si no (se siguió aquí también), la de aquí queda
        # aparte, con su fecha, y se dice: nada se pierde
        if ruta.exists():
            antes = ruta.read_bytes()
            if not datos.startswith(antes):
                aparte = ruta.with_name(f"{sid}.antes-{datetime.now():%Y%m%d-%H%M%S}.jsonl.bak")
                ruta.replace(aparte)
                aviso = (aviso + "; " if aviso else "") + f"la conversación de aquí se había seguido por su lado: quedó en {aparte.name}"
        tmp = ruta.with_suffix(".tmp")
        tmp.write_bytes(datos)
        tmp.chmod(0o600)
        tmp.replace(ruta)
        gz.unlink(missing_ok=True)

    est = tel.estado
    if carpeta_hilo is not None:
        est.vincular(hilo, relativa)
    if sid:
        est.anotar_sesion(hilo, sid)
    est.desarchivar(hilo)
    try:
        lanz = lanzar.para_hilo(ctx.config, hilo, carpeta_hilo)
        if lanz is None:
            tel.mux.crear_tab(hilo, ruta=carpeta_hilo, foco=False)
        else:
            tel.mux.crear_tab(hilo, ruta=lanz.carpeta, comando=lanz.comando, foco=False)
            lanzar.anotar(ctx.config, hilo, lanz, tel.mux)
    except Exception as e:  # noqa: BLE001 - la conversación quedó: `telar hilo retomar` lo intenta de nuevo
        return {"ok": False, "error": f"no pude abrir el hilo: {e}" + (f" (la conversación quedó aquí: {ruta})" if ruta else "")}
    retoma = getattr(lanz, "retoma", "") if lanz is not None else ""
    if sid and lanz is not None and retoma != sid:
        aviso = (aviso + "; " if aviso else "") + "se abrió, pero no retomando esa conversación"
    return {"ok": True, "carpeta": str(inicio), "conversacion": str(ruta) if ruta else "", "aviso": aviso}


MAQUINA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def traer_aqui(ctx, p: dict, *, espera: float = 900) -> dict:
    """Lo que corre el dueño de un hilo cuando otra máquina de la persona lo pide para sí («traer a esta máquina»):
    `telar hilo llevar <la que pide> --hilo <hilo>`, que la manda por el bus como siempre. `si`: aunque haya trabajo
    sin subir (sin él, falla diciéndolo, y quien pide pregunta). Devuelve {ok, codigo, salida}."""
    import subprocess
    import sys

    hilo, a = str(p.get("hilo") or "").strip(), str(p.get("a") or "").strip()
    if not hilo or not MAQUINA.match(a):
        return {"ok": False, "error": "falta el hilo o a qué máquina"}
    argv = [sys.executable, "-m", "telar", "hilo", "llevar", a, "--hilo", hilo, *(["--si"] if p.get("si") else [])]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=espera, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": f"telar hilo llevar no terminó: {e}"}
    return {"ok": True, "codigo": r.returncode, "salida": (r.stdout or "") + (r.stderr or "")}
