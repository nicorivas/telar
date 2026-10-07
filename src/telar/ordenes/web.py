"""`telar web` — telar en el navegador del celular: el día y los hilos, tocables.

    telar web                    escucha en la IP de Tailscale (o en localhost si no hay), puerto 8765
    telar web --host IP --puerto N
    telar web --sin-recarga      no recarga la página cuando cambian sus archivos
    telar web --escribir         permite escribirle a un hilo desde la página (por defecto, solo lee)
    telar web --escribir --nuevo [--nuevo-args PALABRAS]   la página abre hilos nuevos (nombre obligatorio) y lanza los atajos del dashboard (`[atajos.<tecla>]`, p. ej. ⚑ correo)
    telar web --plan CARPETA --plan-comando CMD   (con --escribir) la pestaña «plan» recibe comentarios que abren una sesión
    telar web --plan CARPETA     muestra una pestaña «plan» con los archivos AAAA-MM-DD.json de esa carpeta

Una capa fina sobre lo que telar ya sabe: cada pantalla lee un `--json` documentado
(docs/contratos.md), así que la lógica no se duplica. Los hilos de otras máquinas (el laptop) salen
de las fotos que ellas empujan con `telar espejo publicar` (ver `telar.espejo`). Escucha en una sola
interfaz; una dirección abierta a todas (`0.0.0.0`) hay que pedirla con `--abierto`.

**Por defecto solo lee.** Con `--escribir` hay una sola ruta que escribe, `POST /api/enviar`: le
escribe un texto a un hilo vivo, de esta máquina o de otra por `telar enlace`. Es delicado —lo que se
escribe en un hilo lo ejecuta un agente—, así que se defiende: exige un encabezado propio
(`X-Telar`) que una página ajena no puede poner sin permiso, que `Host` y `Origin` sean los de este
servidor (contra páginas ajenas y contra DNS rebinding), tope de tamaño, un envío cada medio segundo, y
anota cada uno en `<estado>/web.log` (el texto no; solo su tamaño). Quien pueda alcanzar el puerto puede
escribirle a tus agentes: por eso escucha solo en Tailscale y la escritura es opt-in.

Los archivos de la página viven en `telar/web/`. Con la recarga puesta (lo normal), editar uno
de ellos recarga la página abierta en el celular en un par de segundos: ese es el punto.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urllib.parse import parse_qs

from telar import bus as mod_bus
from telar import conversacion, enlace, espejo
from telar.ordenes import _comun

AYUDA = "telar en el navegador del celular: el día y los hilos."
CARPETA = Path(__file__).resolve().parent.parent / "web"
PUERTO = 8765

#: cuánto se reusa la respuesta de cada orden (segundos). `hoy` consulta el calendario y tarda ~10 s:
#: lo rehace un hilo de fondo cada `RENUEVA` segundos, y quien pide recibe lo que haya, aunque el
#: refresco esté a medias; solo se espera si lo último tiene más de `VIGENCIA` (el hilo murió).
VIGENCIA = {"hoy": 300.0, "hilos": 4.0, "proyectos": 120.0}
RENUEVA = 40.0
_cache: dict[str, tuple[float, bytes]] = {}
_candado = threading.Lock()


def ip_de_tailscale() -> str:
    """La IPv4 de esta máquina en Tailscale, o «» si no hay."""
    if not shutil.which("tailscale"):
        return ""
    r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True)
    return r.stdout.split()[0] if r.returncode == 0 and r.stdout.split() else ""


def _correr(orden: str, argumentos: list[str]) -> bytes:
    r = subprocess.run([sys.executable, "-m", "telar", orden, *argumentos, "--json"],
                       capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(detalle[-1] if detalle else f"telar {orden} salió con {r.returncode}")
    json.loads(r.stdout)  # que sea JSON antes de servirlo
    return r.stdout.encode()


def datos(orden: str, fresco: bool = False) -> bytes:
    """La salida `--json` de una orden, reusada mientras esté vigente."""
    with _candado:
        hora, cuerpo = _cache.get(orden, (0.0, b""))
        if cuerpo and not fresco and time.monotonic() - hora < VIGENCIA[orden]:
            return cuerpo
    cuerpo = _correr(orden, [])
    with _candado:
        _cache[orden] = (time.monotonic(), cuerpo)
    return cuerpo


def mantener_fresco(pausa: float = RENUEVA) -> None:
    """Rehace `hoy` en segundo plano, para que quien abra la página nunca espere al calendario."""
    while True:
        try:
            datos("hoy", fresco=True)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired):
            pass  # el próximo pedido lo intenta y le dice el motivo a quien lo mire
        time.sleep(pausa)


#: cuánto se acepta en una petición de escritura, y cada cuánto se permite una (segundos)
MAX_CUERPO = 64 * 1024
ENTRE_ENVIOS = 0.5
_ultimo_envio = [0.0]


def enlace_para(config, maquina: str):
    """A qué máquina de `[enlaces]` corresponde el nombre que trae el espejo. Con un solo enlace, ese;
    con varios, el que se llame igual. Ninguno → None (y se dice, no se adivina)."""
    por_nombre = next((e for e in config.enlaces if e.nombre == maquina), None)
    if por_nombre is not None:
        return por_nombre
    return config.enlaces[0] if len(config.enlaces) == 1 else None


def enviar(ctx, datos: object) -> tuple[int, dict]:
    """Le escribe un texto a un hilo: `(código http, respuesta)`. `maquina` vacío es esta máquina; con
    nombre, la del espejo, por `telar enlace`. La validación de fondo (hilo vivo, tamaños, saltos de
    línea) es la de la puerta (`telar.enlace.servir`): aquí solo se traduce y se protege."""
    if not isinstance(datos, dict):
        return 400, {"ok": False, "error": "se esperaba un objeto JSON"}
    maquina, hilo, texto, enter = datos.get("maquina", ""), datos.get("hilo"), datos.get("texto"), datos.get("enter", True)
    if not isinstance(maquina, str) or not isinstance(hilo, str) or not hilo or not isinstance(texto, str) or not isinstance(enter, bool):
        return 400, {"ok": False, "error": "faltan o no son válidos maquina, hilo, texto y enter"}
    with _candado:  # un envío cada medio segundo: un dedo torpe o un bucle no inundan a un agente
        ahora = time.monotonic()
        if ahora - _ultimo_envio[0] < ENTRE_ENVIOS:
            return 429, {"ok": False, "error": "muy rápido: un envío a la vez"}
        _ultimo_envio[0] = ahora
    if maquina and mod_bus.hay_bus(ctx.config):
        # a un hilo de otra máquina, por el bus: lo escribe la persona desde la web
        try:
            m = mod_bus.enviar(ctx.config, hilo, texto, de="la web", tipo="persona")
        except mod_bus.ErrorDeBus as e:
            return 409, {"ok": False, "error": str(e)}
        return 200, {"ok": True, "por": "bus", "id": m["id"]}
    args = [hilo, *(["enter"] if enter else [])]
    if not maquina:
        r = enlace.servir(ctx, shlex.join(["enviar", *args]), texto.encode())
    else:
        destino = enlace_para(ctx.config, maquina)
        if destino is None:
            return 404, {"ok": False, "error": f"no sé a qué enlace corresponde «{maquina[:40]}» (ver [enlaces])"}
        r = enlace.llamar(destino, "enviar", args, texto.encode())
    return (200 if r.get("ok") else 409), r


MAX_COMENTARIO = 4000
ENTRE_COMENTARIOS = 5.0
_ultimo_comentario = [0.0]


def comentar_plan(plan: Path, comando: str, datos: object) -> tuple[int, dict]:
    """Un comentario sobre el plan de un día abre una sesión de agente que lo atiende: `(código http, respuesta)`.

    telar no sabe qué hace esa sesión: corre `comando` (el que se declaró con `--plan-comando`) con el comentario en la
    **entrada estándar** —nunca en la línea de comandos— y el día y la carpeta en el entorno. La primera línea que imprima
    es el nombre del hilo que abrió. Un comentario a la vez, cada cinco segundos."""
    if not isinstance(datos, dict) or not isinstance(datos.get("dia"), str) or not isinstance(datos.get("texto"), str):
        return 400, {"ok": False, "error": "faltan o no son válidos dia y texto"}
    dia, texto = datos["dia"], datos["texto"].strip()
    if not _DIA.fullmatch(dia) or not any((plan / f"{dia}{ext}").is_file() for ext in (".json", ".md")):
        return 404, {"ok": False, "error": f"no hay un plan del {dia[:10]}"}
    if not texto:
        return 400, {"ok": False, "error": "el comentario está vacío"}
    if len(texto) > MAX_COMENTARIO:
        return 413, {"ok": False, "error": f"el comentario pasa de {MAX_COMENTARIO} caracteres"}
    with _candado:
        ahora = time.monotonic()
        if ahora - _ultimo_comentario[0] < ENTRE_COMENTARIOS:
            return 429, {"ok": False, "error": "muy rápido: un comentario cada cinco segundos"}
        _ultimo_comentario[0] = ahora
    entorno = {**os.environ, "TELAR_PLAN_DIA": dia, "TELAR_PLAN_CARPETA": str(plan)}
    try:
        r = subprocess.run(shlex.split(comando), input=texto.encode(), capture_output=True, timeout=30, env=entorno)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 502, {"ok": False, "error": f"no se pudo abrir la sesión: {type(e).__name__}"}
    if r.returncode != 0:
        cola = (r.stderr.decode("utf-8", "replace").strip().splitlines() or [f"salió con {r.returncode}"])[-1]
        return 502, {"ok": False, "error": f"no se pudo abrir la sesión: {cola[:200]}"}
    primera = (r.stdout.decode("utf-8", "replace").strip().splitlines() or [""])[0]
    return 200, {"ok": True, "hilo": primera.split(" · ")[0][:120], "caracteres": len(texto)}


MAX_NOMBRE = 60
ENTRE_NUEVOS = 5.0
_ultimo_nuevo = [0.0]


def nuevo_hilo(ctx, datos: object, extra: tuple[str, ...]) -> tuple[int, dict]:
    """Abre un hilo nuevo en esta máquina, con el agente configurado: `(código http, respuesta)`.

    Es la misma apertura que `telar movil`, con dos diferencias: `extra` son palabras que se le agregan al agente
    (`--nuevo-args`, p. ej. el modo de permisos) y puede llevar un primer mensaje. El nombre es obligatorio y no puede
    repetir el de ningún hilo, vivo o no, porque la conversación se anota por nombre. La carpeta solo puede ser una
    unidad de `telar proyectos` (o ninguna: la del agente), nunca una ruta que mande la página."""
    from telar import agente as mod_agente
    from telar import movil as mod_movil
    from telar.agente import lanzar
    from telar.ordenes import _comun

    if not isinstance(datos, dict) or not all(isinstance(datos.get(k, ""), str) for k in ("nombre", "carpeta", "mensaje")):
        return 400, {"ok": False, "error": "faltan o no son válidos nombre, carpeta y mensaje"}
    nombre = " ".join(datos.get("nombre", "").split())
    ruta, mensaje = datos.get("carpeta", "").strip(), datos.get("mensaje", "").strip()
    if not nombre:
        return 400, {"ok": False, "error": "el hilo necesita un nombre"}
    if len(nombre) > MAX_NOMBRE or not nombre.isprintable():
        return 400, {"ok": False, "error": f"el nombre pasa de {MAX_NOMBRE} caracteres o trae caracteres raros"}
    if len(mensaje) > MAX_COMENTARIO:
        return 413, {"ok": False, "error": f"el mensaje pasa de {MAX_COMENTARIO} caracteres"}
    config = ctx.config
    if not config.agente.nombre:
        return 409, {"ok": False, "error": "no hay agente configurado ([agente] nombre)"}
    if ruta:
        rutas = {p["ruta"] for p in json.loads(datos_proyectos())["proyectos"]}
        if ruta not in rutas:
            return 404, {"ok": False, "error": "esa carpeta no es una unidad de `telar proyectos`"}
    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.por_nombre(nombre) is not None or nombre in tel.propios:
        return 409, {"ok": False, "error": f"ya hay un hilo llamado «{nombre}»: elige otro nombre"}
    with _candado:
        ahora = time.monotonic()
        if ahora - _ultimo_nuevo[0] < ENTRE_NUEVOS:
            return 429, {"ok": False, "error": "muy rápido: un hilo nuevo cada cinco segundos"}
        _ultimo_nuevo[0] = ahora
    agente = mod_agente.obtener(config.agente.nombre, config)
    palabras, sid = agente.nuevo_con_id("")
    palabras = [*palabras, *extra]
    if mensaje:  # un mensaje que empiece con «-» se leería como una opción del agente
        palabras.append(f" {mensaje}" if mensaje.startswith("-") else mensaje)
    base = lanzar.carpeta(config, None)
    carpeta = (Path(config.raiz) / ruta) if ruta else Path(str(base or config.raiz)).expanduser()
    lanz = lanzar.Lanzamiento(comando=lanzar.envolver(palabras, nombre), carpeta=carpeta, nueva=sid)
    try:
        mod_movil.crear(nombre, str(carpeta), lanz.comando)
    except RuntimeError as e:
        return 502, {"ok": False, "error": f"no pude abrir «{nombre}»: {str(e)[:160]}"}
    lanzar.anotar(config, nombre, lanz)
    return 200, {"ok": True, "hilo": nombre, "carpeta": ruta or str(carpeta)}


def lanzar_atajo(ctx, datos: object, extra: tuple[str, ...]) -> tuple[int, dict]:
    """Lo mismo que la tecla de un atajo del dashboard (`telar atajo`), desde la página: `(código http, respuesta)`.

    Solo se acepta la **tecla** de un atajo declarado en la configuración: el mensaje sale de ahí, nunca de la página.
    Un atajo normal abre un hilo nuevo con la hora en el nombre (como `nuevo_hilo`); uno de agente residente le
    encarga el mensaje a su hilo de siempre."""
    import io
    from contextlib import redirect_stdout

    if not isinstance(datos, dict) or not isinstance(datos.get("tecla"), str):
        return 400, {"ok": False, "error": "falta la tecla del atajo"}
    atajo = next((a for a in ctx.config.atajos if a.tecla == datos["tecla"]), None)
    if atajo is None:
        return 404, {"ok": False, "error": f"no hay atajo en «{datos['tecla'][:20]}»"}
    if not atajo.agente:
        nombre = f"{atajo.nombre} {time.strftime('%m/%d %H:%M')}"
        codigo, r = nuevo_hilo(ctx, {"nombre": nombre, "carpeta": "", "mensaje": atajo.mensaje}, extra)
        return codigo, ({**r, "atajo": atajo.nombre} if r.get("ok") else r)
    from telar import agentes as mod_agentes
    from telar.ordenes import encargar

    agente = next((a for a in mod_agentes.descubrir(ctx.config) if atajo.agente in (a.clave, a.nombre)), None)
    if agente is None:
        return 404, {"ok": False, "error": f"el atajo le encarga a «{atajo.agente}», que no está en [agentes]"}
    with _candado:
        ahora = time.monotonic()
        if ahora - _ultimo_nuevo[0] < ENTRE_NUEVOS:
            return 429, {"ok": False, "error": "muy rápido: un atajo cada cinco segundos"}
        _ultimo_nuevo[0] = ahora
    salida = io.StringIO()
    with redirect_stdout(salida):
        codigo = encargar.main([agente.clave, atajo.mensaje, "--json"], ctx)
    if codigo != 0:
        return 502, {"ok": False, "error": f"«{agente.nombre}» no recibió el encargo"}
    try:
        estado = json.loads(salida.getvalue().strip().splitlines()[-1]).get("estado", "")
    except (ValueError, IndexError):
        estado = ""
    return 200, {"ok": True, "hilo": agente.nombre, "atajo": atajo.nombre, "encargo": estado}


def datos_proyectos() -> bytes:
    return datos("proyectos")


def anotar_envio(config, cliente: str, maquina: str, hilo: str, caracteres: int, resultado: str) -> None:
    """Una línea por envío: quién, a qué hilo, cuánto y cómo salió. El texto no se guarda."""
    try:
        ruta = Path(config.estado) / "web.log"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}\t{cliente}\t{maquina or 'aquí'}\t{hilo[:80]}\t{caracteres}\t{resultado[:120]}\n")
    except OSError:
        pass


def mantener_espejos(config, pausa: float = 30.0) -> None:
    """Cada `pausa` segundos le pide su foto a cada máquina de `[enlaces]`, para que el espejo esté al día
    aunque su extensión no esté publicando. Un laptop apagado falla rápido y queda con su última foto."""
    if mod_bus.hay_bus(config):
        return  # con bus, cada nodo publica su foto y el de aquí la guarda (telar nodo)
    while True:
        for e in config.enlaces:
            try:
                enlace.traer_foto(config, e)
            except Exception:  # noqa: BLE001 - un intento fallido no puede matar el hilo; el espejo ya se ve apagado
                pass
        time.sleep(pausa)


def _entero(q: dict, clave: str) -> int | None:
    valor = q.get(clave, [""])[0]
    if valor == "":
        return None
    if not valor.lstrip("-").isdigit():
        raise ValueError(f"«{clave}» tiene que ser un número")
    return int(valor)


def _conversacion(consulta: str, config) -> tuple[int, bytes, str]:
    """`GET /api/conversacion?hilo=…[&sesion=][&antes=][&despues=][&n=]` → (código, cuerpo, tipo).

    La conversación se pide por **hilo**, no por id: de ahí sale la lista de conversaciones permitidas
    (`hilos --json`), así que un id suelto nunca abre un archivo."""
    def responder(codigo: int, cuerpo: dict) -> tuple[int, bytes, str]:
        return codigo, json.dumps(cuerpo, ensure_ascii=False).encode(), "application/json; charset=utf-8"

    q = parse_qs(consulta)
    nombre = q.get("hilo", [""])[0]
    if not nombre or config is None:
        return responder(400, {"error": "falta el hilo"})
    if q.get("maquina", [""])[0]:
        return _conversacion_remota(q, nombre, config, responder)
    try:
        antes, despues, n = _entero(q, "antes"), _entero(q, "despues"), _entero(q, "n")
    except ValueError as e:
        return responder(400, {"error": str(e)})
    hilos = json.loads(datos("hilos")).get("hilos", [])
    h = next((x for x in hilos if x.get("nombre") == nombre and not x.get("archivado")), None)
    if h is None:
        return responder(404, {"error": f"no hay un hilo «{nombre[:60]}»"})
    try:
        cuerpo = conversacion.pagina(config, h.get("sesiones") or [], sesion=q.get("sesion", [""])[0], antes=antes,
                                     despues=despues, n=n or conversacion.POR_PAGINA)
    except conversacion.ErrorDeConversacion as e:
        return responder(404, {"error": str(e)})
    cuerpo["hilo"] = {"nombre": h["nombre"], "atencion": h.get("atencion", ""), "vivo": bool(h.get("vivo")),
                       "propio": bool(h.get("propio"))}
    return responder(200, cuerpo)


#: lo que devolvió la otra máquina hace un momento, para que dos pantallas abiertas no la llamen dos veces
_remotas: dict[tuple, tuple[float, tuple[int, dict]]] = {}
TURNOS_POR_DEFECTO = 10


def _conversacion_remota(q: dict, nombre: str, config, responder) -> tuple[int, bytes, str]:
    """La conversación de un hilo de **otra máquina**, por la puerta (`telar enlace`, verbo `leer`).

    El laptop entrega los últimos N turnos (hasta 50), no mensajes numerados: no hay «anteriores» ni «lo que llegó
    después» sino «pide más turnos» y «vuelve a pedir». La respuesta tiene la misma forma que la de un hilo de
    aquí, así que la pantalla es una sola. Lo que el laptop no entrega (verbo apagado, hilo vetado en `no_leer`,
    máquina apagada) llega como 409 con su motivo. Nada se guarda en este servidor."""
    maquina = q["maquina"][0]
    try:
        turnos = _entero(q, "turnos") or TURNOS_POR_DEFECTO
    except ValueError as e:
        return responder(400, {"error": str(e)})
    turnos = max(1, min(turnos, 50))
    destino = None if mod_bus.hay_bus(config) else enlace_para(config, maquina)
    if destino is None and not mod_bus.hay_bus(config):
        return responder(404, {"error": f"no sé a qué enlace corresponde «{maquina[:40]}» (ver [enlaces])"})
    clave = (maquina, nombre, turnos)
    with _candado:
        hora, previo = _remotas.get(clave, (0.0, None))
        if previo is not None and time.monotonic() - hora < 3.0:
            return responder(*previo)
    if destino is None:  # con bus: un pedido al nodo de esa máquina
        r = mod_bus.pedir(config, maquina, "leer", {"hilo": nombre, "ultimos": turnos}, espera=30)
    else:
        r = enlace.llamar(destino, "leer", [nombre, str(turnos)], espera=30)
    if not r.get("ok"):
        resultado = (409, {"error": str(r.get("error", "la otra máquina no respondió"))})
    else:
        h = r.get("historia") or {}
        mensajes = [conversacion.recortado(m) for m in conversacion.aplanar(h)]
        foto = next((e for e in espejo.leer_todos(config) if e["nombre"] == maquina), {})
        info = next((x for x in foto.get("hilos", []) if x.get("nombre") == nombre), {})
        resultado = (200, {
            "remota": maquina, "fuente": h.get("fuente", "conversacion"), "sesion": h.get("conversacion", ""), "sesiones": [],
            "turnos": len(h.get("turnos", [])), "turnos_pedidos": turnos, "total_turnos": h.get("total_turnos"),
            "recortado": bool(h.get("recortado")), "total": len(mensajes), "desde": 0, "hasta": len(mensajes),
            "mensajes": mensajes,
            "hilo": {"nombre": nombre, "atencion": info.get("atencion", ""), "vivo": bool(info.get("vivo")),
                     "en_linea": bool(foto.get("en_linea"))}})
    with _candado:
        _remotas[clave] = (time.monotonic(), resultado)
        if len(_remotas) > 16:
            _remotas.pop(next(iter(_remotas)))
    return responder(*resultado)


_DIA = re.compile(r"\d{4}-\d{2}-\d{2}")
MAX_PLAN = 400_000


def leer_plan(carpeta: Path, consulta: str) -> tuple[int, dict]:
    """El plan de un día: `(código http, cuerpo)`. Los planes son `AAAA-MM-DD.json` en `carpeta` (o `.md`, los de antes);
    sin `dia`, el de hoy, o el próximo que haya, o el último. Solo se lee, y el nombre se valida antes de tocar el disco."""
    por_dia: dict[str, Path] = {}
    for f in sorted(carpeta.glob("*")):  # el .json manda sobre un .md del mismo día
        if f.suffix in (".json", ".md") and _DIA.fullmatch(f.stem) and (f.stem not in por_dia or f.suffix == ".json"):
            por_dia[f.stem] = f
    dias = sorted(por_dia, reverse=True)
    hoy = datetime.date.today().isoformat()
    pedido = parse_qs(consulta).get("dia", [""])[0]
    if pedido:
        if not _DIA.fullmatch(pedido) or pedido not in por_dia:
            return 404, {"error": f"no hay un plan del {pedido[:10]}"}
        dia = pedido
    elif dias:
        dia = hoy if hoy in por_dia else next((d for d in reversed(dias) if d > hoy), dias[0])
    else:
        return 200, {"dia": "", "dias": [], "hoy": hoy}
    archivo = por_dia[dia]
    texto = archivo.read_text(encoding="utf-8", errors="replace")[:MAX_PLAN]
    cuerpo = {"dia": dia, "dias": dias, "hoy": hoy}
    if archivo.suffix == ".json":
        try:
            cuerpo["plan"] = json.loads(texto)
        except ValueError as e:
            return 502, {"error": f"el plan del {dia} no es JSON válido: {e}"}
    else:
        if texto.startswith("---\n"):  # el front-matter es para las máquinas
            fin = texto.find("\n---", 4)
            texto = texto[fin + 4:].lstrip("\n") if fin > 0 else texto
        cuerpo["texto"] = texto
    return 200, cuerpo


def version_de_la_pagina() -> str:
    """Una huella de los archivos de la página: cambia cuando se edita uno."""
    h = hashlib.sha1()
    for f in sorted(CARPETA.glob("*")):
        if f.is_file():
            h.update(f.name.encode() + str(f.stat().st_mtime_ns).encode())
    return h.hexdigest()[:12]


def manejador(recarga: bool, config=None, ctx=None, escribir: bool = False, tambien: tuple[str, ...] = (), plan: Path | None = None,
              plan_comando: str = "", nuevo: bool = False, nuevo_args: tuple[str, ...] = ()):
    config = config if config is not None else (ctx.config if ctx is not None else None)

    class Manejador(BaseHTTPRequestHandler):
        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            # las fuentes no cambian: se guardan un día; todo lo demás se pide siempre (se edita y se recarga)
            self.send_header("Cache-Control", "public, max-age=86400" if tipo.startswith("font/") else "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):  # noqa: N802 (nombre que pide http.server)
            ruta, _, consulta = self.path.partition("?")
            try:
                if ruta == "/api/version":
                    return self._enviar(200, json.dumps({"pagina": version_de_la_pagina() if recarga else ""}).encode(), "application/json")
                if ruta == "/api/conversacion":  # el historial de un hilo de esta máquina, por páginas (solo lee)
                    return self._enviar(*_conversacion(consulta, config))
                if ruta == "/api/yo":  # qué puede hacer esta página: la escritura es opt-in y necesita el enlace
                    cuerpo = {"escribir": escribir, "plan": plan is not None, "plan_comentar": bool(plan is not None and plan_comando and escribir),
                              "nuevo": bool(nuevo and escribir),
                              "atajos": [{"tecla": a.tecla, "nombre": a.nombre, "descripcion": a.descripcion or a.mensaje}
                                         for a in (config.atajos if config and nuevo and escribir else ())],
                              "enlaces": [e.nombre for e in (config.enlaces if config else ())]}
                    return self._enviar(200, json.dumps(cuerpo).encode(), "application/json")
                if ruta == "/api/plan":  # los planes del día (solo si se arrancó con --plan)
                    if plan is None:
                        return self._enviar(404, json.dumps({"error": "esta página no tiene planes: `telar web --plan CARPETA`"}).encode(), "application/json")
                    codigo, cuerpo = leer_plan(plan, consulta)
                    return self._enviar(codigo, json.dumps(cuerpo, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                if ruta == "/api/espejos":  # los hilos de otras máquinas (el laptop), de sus fotos; no cuesta nada leerlos
                    cuerpo = {"espejos": espejo.leer_todos(config) if config is not None else [], "vigente": espejo.VIGENTE}
                    return self._enviar(200, json.dumps(cuerpo, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                if ruta in ("/api/hoy", "/api/hilos", "/api/proyectos"):
                    return self._enviar(200, datos(ruta[5:], fresco="fresco" in consulta), "application/json; charset=utf-8")
                nombre = "index.html" if ruta == "/" else ruta.lstrip("/")
                archivo = (CARPETA / nombre).resolve()
                if CARPETA not in archivo.parents or not archivo.is_file():
                    return self._enviar(404, b"no hay tal pagina", "text/plain; charset=utf-8")
                tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
                self._enviar(200, archivo.read_bytes(), f"{tipo}; charset=utf-8" if tipo.startswith("text/") or tipo.endswith("javascript") else tipo)
            except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
                self._enviar(502, json.dumps({"error": str(e)}).encode(), "application/json; charset=utf-8")

        def _permitido(self) -> str:
            """"" si la petición viene de esta página; si no, por qué se rechaza."""
            host, puerto = self.server.server_address[:2]
            validos = {f"{host}:{puerto}", f"localhost:{puerto}", f"127.0.0.1:{puerto}", *tambien}
            if self.headers.get("Host", "") not in validos:
                return "Host que no es de este servidor"
            origen = self.headers.get("Origin")
            # con `tailscale serve` la página llega por https, y su Origin también: solo se acepta
            # para un nombre que se declaró con --tambien, no para cualquier Host
            propio = self.headers.get("Host", "")
            validos_origen = {f"http://{propio}", *([f"https://{propio}"] if propio in tambien else [])}
            if origen is not None and origen not in validos_origen:
                return "Origin que no es de esta página"
            if self.headers.get("X-Telar") != "1":
                return "falta el encabezado X-Telar"
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return "se esperaba application/json"
            return ""

        def do_POST(self):  # noqa: N802
            def responder(codigo, cuerpo):
                self._enviar(codigo, json.dumps(cuerpo, ensure_ascii=False).encode(), "application/json; charset=utf-8")

            ruta = self.path.partition("?")[0]
            if ruta not in ("/api/enviar", "/api/plan/comentar", "/api/hilo/nuevo", "/api/atajo"):
                return responder(404, {"ok": False, "error": "no hay tal ruta"})
            if ruta == "/api/plan/comentar" and not (plan is not None and plan_comando):
                return responder(404, {"ok": False, "error": "esta página no recibe comentarios del plan: `telar web --plan CARPETA --plan-comando CMD`"})
            if ruta in ("/api/hilo/nuevo", "/api/atajo") and not nuevo:
                return responder(404, {"ok": False, "error": "esta página no abre hilos: `telar web --escribir --nuevo`"})
            if not escribir or ctx is None:
                return responder(403, {"ok": False, "error": "esta página solo lee: arráncala con `telar web --escribir`"})
            rechazo = self._permitido()
            if rechazo:
                return responder(403, {"ok": False, "error": rechazo})
            try:
                largo = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                largo = -1
            if not 0 < largo <= MAX_CUERPO:
                return responder(413 if largo > MAX_CUERPO else 400, {"ok": False, "error": "el cuerpo falta o es demasiado grande"})
            try:
                datos = json.loads(self.rfile.read(largo))
            except ValueError:
                return responder(400, {"ok": False, "error": "el cuerpo no es JSON"})
            if ruta == "/api/hilo/nuevo":
                try:
                    codigo, resultado = nuevo_hilo(ctx, datos, nuevo_args)
                except Exception as e:  # noqa: BLE001
                    codigo, resultado = 500, {"ok": False, "error": f"falló por dentro: {type(e).__name__}"}
                if isinstance(datos, dict):
                    anotar_envio(config, self.client_address[0], "nuevo", str(datos.get("nombre", ""))[:60], len(str(datos.get("mensaje", ""))),
                                 "ok" if resultado.get("ok") else str(resultado.get("error", codigo)))
                return responder(codigo, resultado)
            if ruta == "/api/atajo":
                try:
                    codigo, resultado = lanzar_atajo(ctx, datos, nuevo_args)
                except Exception as e:  # noqa: BLE001
                    codigo, resultado = 500, {"ok": False, "error": f"falló por dentro: {type(e).__name__}"}
                if isinstance(datos, dict):
                    anotar_envio(config, self.client_address[0], "atajo", str(datos.get("tecla", ""))[:20], 0,
                                 "ok" if resultado.get("ok") else str(resultado.get("error", codigo)))
                return responder(codigo, resultado)
            if ruta == "/api/plan/comentar":
                try:
                    codigo, resultado = comentar_plan(plan, plan_comando, datos)
                except Exception as e:  # noqa: BLE001
                    codigo, resultado = 500, {"ok": False, "error": f"falló por dentro: {type(e).__name__}"}
                if isinstance(datos, dict):
                    anotar_envio(config, self.client_address[0], "plan", str(datos.get("dia", "")), len(str(datos.get("texto", ""))),
                                 "ok" if resultado.get("ok") else str(resultado.get("error", codigo)))
                return responder(codigo, resultado)
            try:
                codigo, resultado = enviar(ctx, datos)
            except Exception as e:  # noqa: BLE001 - una falla interna se dice, no cuelga la conexión
                codigo, resultado = 500, {"ok": False, "error": f"falló por dentro: {type(e).__name__}"}
            if isinstance(datos, dict):
                anotar_envio(config, self.client_address[0], str(datos.get("maquina", "")), str(datos.get("hilo", "")),
                             len(str(datos.get("texto", ""))), "ok" if resultado.get("ok") else str(resultado.get("error", codigo)))
            responder(codigo, resultado)

        def log_message(self, *a):  # una línea por petición ahogaría la terminal
            pass

    return Manejador


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("web", AYUDA)
    p.epilog = __doc__
    p.add_argument("--host", default="", help="la IP donde escuchar (por defecto, la de Tailscale)")
    p.add_argument("--puerto", type=int, default=PUERTO)
    p.add_argument("--abierto", action="store_true", help="permitir escuchar en todas las interfaces (0.0.0.0)")
    p.add_argument("--escribir", action="store_true", help="permitir escribirle a un hilo desde la página (por defecto, solo lee)")
    p.add_argument("--plan", default="", metavar="CARPETA", help="una pestaña «plan» con los AAAA-MM-DD.json de esa carpeta (solo lee)")
    p.add_argument("--plan-comando", default="", metavar="CMD",
                   help="con --plan y --escribir: el programa que atiende un comentario del plan (lo recibe por la entrada estándar)")
    p.add_argument("--nuevo", action="store_true", help="con --escribir: la página puede abrir hilos nuevos con el agente configurado")
    p.add_argument("--nuevo-args", default="", metavar="PALABRAS",
                   help="palabras que se le agregan al agente de un hilo abierto desde la página (p. ej. «--permission-mode auto»)")
    p.add_argument("--tambien", action="append", default=[], metavar="HOST:PUERTO",
                   help="otro nombre con el que se llega a esta página (para `--escribir`); se puede repetir")
    p.add_argument("--sin-recarga", action="store_true", help="no recargar la página al cambiar sus archivos")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    host = o.host or ip_de_tailscale() or "127.0.0.1"
    if host in ("0.0.0.0", "::") and not o.abierto:
        return _comun.queja("escuchar en todas las interfaces expone telar a la red entera: pídelo con --abierto")
    if not CARPETA.is_dir():
        return _comun.queja(f"no encuentro los archivos de la página en {CARPETA}")
    threading.Thread(target=mantener_fresco, daemon=True).start()
    if ctx.config.enlaces:
        threading.Thread(target=mantener_espejos, args=(ctx.config,), daemon=True).start()
    servidor = ThreadingHTTPServer((host, o.puerto), manejador(not o.sin_recarga, ctx.config, ctx, o.escribir, tuple(o.tambien),
                                                                plan=Path(o.plan).expanduser().resolve() if o.plan else None,
                                                                plan_comando=o.plan_comando, nuevo=o.nuevo, nuevo_args=tuple(shlex.split(o.nuevo_args))))
    print(f"telar web en http://{host}:{o.puerto}  ·  {'con' if not o.sin_recarga else 'sin'} recarga automática  ·  "
          f"{'PUEDE ESCRIBIR en hilos' if o.escribir else 'solo lee'}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    return 0
