"""Llevar un hilo a otra máquina de la persona por el bus: su conversación viaja, y allá se retoma.

Es `telar hilo llevar <hilo> <máquina>` cuando la máquina no está en `[remotos]` (que van por ssh) sino en el bus:
otra máquina de la misma persona, como su lugar en un servidor (telar.alojamiento), que no tiene ssh para ella.

    enviar(ctx, hilo, maquina, sid, archivo, relativa)        de este lado: la manda y le pide retomarla
    llegar(ctx, pedido)                                       del otro (el nodo, verbo `hilo-llegar`): la deja donde
                                                              el agente la busca y abre el hilo retomándola

La conversación va comprimida por el mismo camino que un archivo (telar.entrega.archivo: en trozos, hasta 25 MB
comprimida) y llega a la carpeta de entrada de allá; `hilo-llegar` la saca de ahí. Los archivos no viajan: si la
carpeta del hilo no existe allá (un repositorio sin clonar), el hilo se abre en la raíz y el agente recuerda la
conversación sin esos archivos.
"""

from __future__ import annotations

import gzip
import re
import tempfile
from pathlib import Path

#: el verbo del nodo que recibe
VERBO = "hilo-llegar"


class ErrorDeMudanza(Exception):
    pass


def maquinas_del_bus(config) -> list[str]:
    """Las otras máquinas de la persona que se ven en el bus (sus fotos), las que estén en línea."""
    from telar import espejo

    try:
        return [e["nombre"] for e in espejo.leer_todos(config) if e.get("en_linea") and not e.get("error")]
    except Exception:  # noqa: BLE001
        return []


def enviar(ctx, hilo: str, maquina: str, sid: str, archivo: Path | None, relativa: str) -> dict:
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
    if sid and ctx.config.agente.nombre != "claude":
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
    if tel.mux is None or not tel.viva:
        return {"ok": False, "error": tel.aviso or "aquí la sesión no está viva"}
    if hilo in tel.vivos:
        return {"ok": False, "error": f"aquí ya hay un hilo «{hilo}» abierto"}
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
        if ruta.exists():
            return {"ok": False, "error": f"aquí ya hay una conversación con ese id ({ruta})"}
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
