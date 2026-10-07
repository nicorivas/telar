"""Encargos a un agente residente: escribirle a su hilo de siempre en vez de abrir uno nuevo.

Un encargo es un prompt para un agente (`telar encargar gestion "/avanzar"`, o un proceso periódico
con `agente = "gestion"`). Su hilo es una sesión propia de esta máquina (`telar-…` con
`@telar_hilo` = el nombre del agente):

    vivo y libre        se le escribe el encargo, como si se tecleara
    vivo y trabajando   el encargo espera en una cola; cuando el agente termina su turno, el gancho
                        `telar agente aviso` le entrega el siguiente
    sin sesión          se abre retomando su última conversación con el encargo como primer mensaje;
                        si esa conversación pesa más de `[agentes] rotar_mb`, se empieza una nueva

Abrir una sesión respeta `[agente] max_vivos`: si ya hay tantas sesiones propias vivas, se cierran
antes las que llevan más rato ociosas y sin nadie mirando (`liberar`). Su conversación queda en disco
y se retoma cuando haga falta: cerrar una sesión ociosa es liberar memoria, no perder nada.

La cola vive en `<estado>/encargos/<agente>.jsonl`; lo que pasó, en `<estado>/encargos.log`.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from telar.modelo import Atencion


class ErrorDeEncargo(Exception):
    """Un encargo que no se pudo hacer. El mensaje es para la persona."""


def _carpeta(config) -> Path:
    return Path(config.estado) / "encargos"


def _cola(config, hilo: str) -> Path:
    return _carpeta(config) / (re.sub(r"[^\w-]+", "_", hilo, flags=re.UNICODE).strip("_") + ".jsonl")


def _anotar(config, texto: str) -> None:
    try:
        ruta = Path(config.estado) / "encargos.log"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texto}\n")
    except OSError:
        pass


def pendientes(config, hilo: str) -> list[dict]:
    try:
        lineas = _cola(config, hilo).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    salida = []
    for l in lineas:
        try:
            salida.append(json.loads(l))
        except ValueError:
            continue
    return salida


def _encolar(config, hilo: str, texto: str) -> int:
    ruta = _cola(config, hilo)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps({"hilo": hilo, "texto": texto, "desde": datetime.now().isoformat(timespec="seconds")},
                           ensure_ascii=False) + "\n")
    return len(pendientes(config, hilo))


def _sacar(config, hilo: str) -> dict | None:
    lista = pendientes(config, hilo)
    if not lista:
        return None
    primero, resto = lista[0], lista[1:]
    ruta = _cola(config, hilo)
    if resto:
        tmp = ruta.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in resto), encoding="utf-8")
        os.replace(tmp, ruta)
    else:
        ruta.unlink(missing_ok=True)
    return primero


#: desde qué largo un encargo no se teclea: se deja en un archivo y se escribe una línea que lo apunta
LARGO_TECLEADO = 600


def _una_linea(texto: str, config=None, hilo: str = "") -> str:
    """Lo que se teclea en una sesión: un salto de línea sería un ↩ que manda el encargo a medias, y un
    texto largo pegado de una vez puede perder el comienzo. Ese va entero a un archivo."""
    plano = " ".join(texto.split())
    if config is None or len(plano) <= LARGO_TECLEADO:
        return plano
    carpeta = _carpeta(config) / "textos"
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = re.sub(r"[^\w-]+", "_", hilo, flags=re.UNICODE).strip("_") or "encargo"
    ruta = carpeta / f"{nombre}-{datetime.now():%Y%m%d-%H%M%S}.md"
    ruta.write_text(texto.strip() + "\n", encoding="utf-8")
    return f"[encargo de {len(plano)} caracteres: léelo entero en {ruta}]"


# ── el tope de sesiones vivas ─────────────────────────────────────────────────

def liberar(config, nuevas: int = 1, *, cuidar: tuple[str, ...] = ()) -> list[str]:
    """Cierra sesiones propias ociosas hasta que quepan `nuevas` bajo `[agente] max_vivos`.

    Ociosa es sin nadie mirando y sin el agente trabajando. Primero las de paso, después los
    residentes (los de `cuidar`), y de cada grupo la que lleva más rato quieta. Devuelve los hilos
    cerrados."""
    tope = getattr(config.agente, "max_vivos", 0)
    if not tope:
        return []
    from telar import estado as mod_estado
    from telar import movil

    # las ventanas de la sesión del telar cuentan solo donde nadie la mira directo (un servidor)
    vivos = movil.hilos(config.sesion if movil.sin_mirar(config.sesion) else "")
    sobran = len(vivos) + nuevas - tope
    if sobran <= 0:
        return []
    est = mod_estado.abrir(config)
    atenciones = est.atenciones()
    candidatos = []
    for h in vivos:
        atencion, desde = atenciones.get(h.nombre, (Atencion.NINGUNA, None))
        if h.clientes or atencion == Atencion.TRABAJANDO:
            continue
        candidatos.append((h.nombre in cuidar, desde.isoformat() if desde else "", h))
    candidatos.sort(key=lambda x: (x[0], x[1]))
    cerrados = []
    for _, _, h in candidatos[:sobran]:
        try:
            movil._tmux("kill-window" if h.ventana else "kill-session", "-t", h.objetivo)
        except Exception as e:  # noqa: BLE001 - una que no se deja cerrar no tumba al resto
            _anotar(config, f"no pude cerrar «{h.nombre}» ({h.direccion}): {e}")
            continue
        est.anotar_atencion(h.nombre, Atencion.NINGUNA)
        cerrados.append(h.nombre)
        _anotar(config, f"cerré «{h.nombre}» ({h.direccion}) por el tope de {tope} hilos vivos")
    return cerrados


# ── dónde vive su hilo ─────────────────────────────────────────────────────────

def _donde(ctx, hilo: str):
    """Cómo escribirle al hilo vivo de un agente: una función (texto) → None, o None si no está vivo.

    Primero un hilo de la lista (un tab, como en el laptop); si no, una sesión propia (servidor)."""
    from telar import movil
    from telar.ordenes import _comun

    try:
        tel = _comun.tejer(ctx, con_ficha=False)
        h = tel.por_nombre(hilo)
        if h is not None and tel.mux is not None and tel.vivo(h):
            return lambda texto: tel.mux.escribir(h.id, texto, enviar=True)
    except Exception:  # noqa: BLE001 - sin multiplexor se busca la sesión propia
        pass
    sesion = movil.propios().get(hilo)
    if sesion:
        return lambda texto: movil.escribir(sesion, texto, enviar=True)
    return None


# ── encargar y repartir ───────────────────────────────────────────────────────

def encargar(ctx, agente, texto: str) -> dict:
    """Le hace llegar `texto` al hilo de `agente` (un `telar.agentes.Agente`), en esta máquina."""
    from telar import estado as mod_estado

    texto = texto.strip()
    if not texto:
        raise ErrorDeEncargo("un encargo sin texto")
    hilo = agente.nombre
    est = mod_estado.abrir(ctx.config)
    escribir = _donde(ctx, hilo)
    if escribir is not None:
        if est.atencion(hilo) == Atencion.TRABAJANDO or pendientes(ctx.config, hilo):
            n = _encolar(ctx.config, hilo, texto)
            _anotar(ctx.config, f"«{hilo}» trabajando: en cola ({n}) · {texto[:80]}")
            return {"hilo": hilo, "estado": "en cola", "en_cola": n}
        escribir(_una_linea(texto, ctx.config, hilo))
        est.anotar_atencion(hilo, Atencion.TRABAJANDO)
        _anotar(ctx.config, f"«{hilo}» libre: entregado · {texto[:80]}")
        return {"hilo": hilo, "estado": "entregado"}
    return _abrir(ctx, agente, texto)


def _abrir(ctx, agente, texto: str) -> dict:
    from telar import agente as mod_agente
    from telar import estado as mod_estado
    from telar import movil
    from telar.agente import ErrorDeAgente, lanzar

    if not ctx.config.agente.nombre:
        raise ErrorDeEncargo("encargar necesita un agente: [agente] nombre en config.toml")
    hilo = agente.nombre
    try:
        ag = mod_agente.obtener(ctx.config.agente.nombre, ctx.config)
    except ErrorDeAgente as e:
        raise ErrorDeEncargo(str(e)) from e
    est = mod_estado.abrir(ctx.config)
    rotar = getattr(ctx.config, "agentes_rotar_mb", 0) * 1024 * 1024
    retoma, nueva = "", ""
    for sid in est.sesiones().get(hilo, ()):
        archivo = ag.archivo_de(sid)
        if archivo is None or not Path(archivo).exists():
            continue
        if rotar and Path(archivo).stat().st_size > rotar:
            _anotar(ctx.config, f"«{hilo}»: su conversación {sid[:8]} pasó de {rotar // (1024 * 1024)} MB; empiezo otra")
            break
        retoma = sid
        break
    if retoma:
        palabras = [*ag.retomar(mod_agente.Conversacion(id=retoma, hilo=hilo)), texto]
    else:
        palabras, nueva = ag.nuevo_con_id(texto)
    palabras = [*palabras, *agente.argumentos]  # después del prompt: hay banderas que se tragan lo que sigue
    if getattr(ctx.config, "agentes_abrir", "sesion") == "tab":
        # un hilo más de la lista (el laptop): se ve y se entra como a cualquiera
        from telar.mux import ErrorDeMux
        from telar.ordenes import _comun

        tel = _comun.tejer(ctx, con_ficha=False)
        if tel.mux is None or not tel.viva:
            raise ErrorDeEncargo(tel.aviso or "la sesión no está viva: primero telar tejer")
        try:
            tel.mux.crear_tab(hilo, ruta=agente.carpeta.resolve(), comando=lanzar.envolver(palabras, hilo), foco=False)
        except ErrorDeMux as e:
            raise ErrorDeEncargo(f"no pude abrir el hilo de {hilo}: {e}") from e
        if nueva:
            lanzar.anotar(ctx.config, hilo, lanzar.Lanzamiento(comando=[], carpeta=agente.carpeta, nueva=nueva), tel.mux)
        tel.estado.vincular(hilo, _comun.ruta_relativa(agente.carpeta, tel.raiz))
        tel.estado.desarchivar(hilo)
        est.anotar_atencion(hilo, Atencion.TRABAJANDO)
        _anotar(ctx.config, f"«{hilo}» sin hilo: abierto en la lista ({'retoma ' + retoma[:8] if retoma else 'conversación nueva'}) · {texto[:80]}")
        return {"hilo": hilo, "estado": "abierto", "retoma": retoma, "cerrados": []}
    cerrados = liberar(ctx.config, 1, cuidar=(hilo,))
    try:
        h = movil.crear(hilo, str(agente.carpeta.resolve()), lanzar.envolver(palabras, hilo), ctx.config.sesion)
    except (RuntimeError, OSError) as e:
        raise ErrorDeEncargo(f"no pude abrir el hilo de {hilo}: {e}") from e
    if nueva:
        lanzar.anotar(ctx.config, hilo, lanzar.Lanzamiento(comando=[], carpeta=agente.carpeta, nueva=nueva))
    est.anotar_atencion(hilo, Atencion.TRABAJANDO)
    _anotar(ctx.config, f"«{hilo}» sin sesión: abierto ({'retoma ' + retoma[:8] if retoma else 'conversación nueva'})"
                        f"{' · cerré ' + ', '.join(cerrados) if cerrados else ''} · {texto[:80]}")
    return {"hilo": hilo, "estado": "abierto", "sesion": h.direccion, "retoma": retoma, "cerrados": cerrados}


def repartir(ctx, hilo: str) -> bool:
    """Si `hilo` tiene encargos en cola, le entrega el siguiente. Lo llama el gancho cuando el agente
    termina un turno; tiene que ser rápido y no fallar nunca."""
    if not hilo or not _cola(ctx.config, hilo).exists():
        return False
    from telar import estado as mod_estado

    escribir = _donde(ctx, hilo)
    if escribir is None:
        return False
    siguiente = _sacar(ctx.config, hilo)
    if siguiente is None:
        return False
    escribir(_una_linea(siguiente["texto"], ctx.config, hilo))
    mod_estado.abrir(ctx.config).anotar_atencion(hilo, Atencion.TRABAJANDO)
    _anotar(ctx.config, f"«{hilo}» terminó: le entregué el siguiente de la cola · {siguiente['texto'][:80]}")
    return True
