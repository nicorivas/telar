"""`telar proyectos` — todas las unidades del perfil, tengan hilo o no, y abrir una.

    telar proyectos                        la lista: nombre, arquetipo, ruta, cuándo se tocó
    telar proyectos --json
    telar proyectos abrir operacion/faro   un hilo vinculado a esa unidad, con el agente
                                           ya cargándola; si ya tiene hilo abierto, va a él

La lista de hilos muestra lo que está abierto; esta muestra de dónde se puede abrir algo.
Es la pantalla «proyectos» del dashboard.

«Cuándo se tocó» es el archivo más reciente de la carpeta, sin contar las carpetas ocultas:
la fecha del documento solo dice cuándo se escribió el estado, y en una carpeta se trabaja
sobre todo en los archivos de al lado.

Al abrir, el agente recibe lo que diga `[agente] proyecto`. De fábrica le pide leer el
documento de la unidad; se puede cambiar por una skill (`/pm {ruta}`).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from telar import lectura
from telar.agente import ErrorDeAgente
from telar.agente import lanzar
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Todas las unidades del perfil, y abrir un hilo cargando una."

#: carpetas que no cuentan para «cuándo se tocó»: lo que se regenera solo no es trabajo.
IGNORADAS = frozenset({"node_modules", "__pycache__"})


def reciente(ruta: Path) -> float:
    """El mtime del archivo más reciente bajo `ruta` (o de `ruta`, si es un archivo). 0 si nada."""
    try:
        if ruta.is_file():
            return ruta.stat().st_mtime
    except OSError:
        return 0.0
    mayor = 0.0
    for carpeta, dirs, archivos in os.walk(ruta):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORADAS]
        for a in archivos:
            if a.startswith("."):
                continue
            try:
                mayor = max(mayor, os.stat(os.path.join(carpeta, a)).st_mtime)
            except OSError:
                pass
    return mayor


def mensaje(plantilla: str, **valores: str) -> str:
    """La plantilla de `[agente] proyecto`, llena. Un marcador desconocido queda tal cual."""
    return re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), plantilla).strip()


def listar(ctx, tel) -> list[dict]:
    raiz = Path(ctx.config.raiz)
    unidades = lectura.indice(ctx.perfil, raiz)
    vinculos = tel.estado.vinculos()
    hilo_de = {ruta: hilo for hilo, ruta in vinculos.items()}
    fuente = _comun.fuente_ficha(ctx.config)
    salida = []
    for relativa, (arquetipo, documento) in unidades.items():
        ficha = _comun.leer_ficha(documento, arquetipo, fuente)
        nombre = lectura.etiqueta(arquetipo.etiqueta, ficha) or Path(relativa).name
        mtime = reciente(raiz / relativa)
        hilo = hilo_de.get(relativa, "")
        salida.append({
            "ruta": relativa,
            "nombre": nombre,
            "arquetipo": arquetipo.nombre,
            "modificado": datetime.fromtimestamp(mtime, timezone.utc).isoformat() if mtime else None,
            "hilo": hilo,
            "vivo": bool(hilo) and hilo in tel.vivos,
        })
    salida.sort(key=lambda p: p["nombre"].casefold())
    return salida


def abrir(ctx, tel, relativa: str) -> dict:
    """Ir al hilo de esa unidad o abrirle uno. Devuelve {hilo, ruta, mensaje, hecho}."""
    raiz = Path(ctx.config.raiz)
    unidades = lectura.indice(ctx.perfil, raiz)
    relativa = relativa.strip().strip("/")
    if relativa not in unidades:
        raise ValueError(f"«{relativa}» no es ninguna unidad que declare el perfil")
    arquetipo, documento = unidades[relativa]
    est = tel.estado
    vinculos = est.vinculos()

    # ya tiene un hilo abierto: se va a él, no se abre otro Claude sobre lo mismo
    for hilo, ruta in vinculos.items():
        if ruta == relativa and hilo in tel.vivos:
            _ir(tel, hilo)
            return {"hilo": hilo, "ruta": relativa, "mensaje": "", "hecho": "ya estaba"}

    ficha = _comun.leer_ficha(documento, arquetipo, _comun.fuente_ficha(ctx.config))
    carpeta = raiz / relativa
    texto = mensaje(
        ctx.config.agente.proyecto,
        nombre=lectura.etiqueta(arquetipo.etiqueta, ficha) or Path(relativa).name,
        ruta=relativa,
        carpeta=str(carpeta),
        documento=str(documento),
    )
    # el nombre del hilo es el de la carpeta, como los que abre tejer. Si ese nombre ya lo
    # usa un tab vivo de otra cosa, se numera; uno muerto o archivado con esta misma
    # unidad se reutiliza, que es el mismo hilo volviendo.
    base = Path(relativa).name or relativa
    nombre, n = base, 1
    while nombre in tel.vivos or (nombre in vinculos and vinculos[nombre] != relativa):
        n += 1
        nombre = f"{base} {n}"
    est.desarchivar(nombre)

    carpeta_hilo = carpeta if carpeta.is_dir() else None
    lanz = None
    if ctx.config.agente.nombre:
        palabras, sid = _agente(ctx).nuevo_con_id(texto)
        lanz = lanzar.Lanzamiento(
            comando=lanzar.envolver(palabras, nombre),
            carpeta=lanzar.carpeta(ctx.config, carpeta_hilo),
            nueva=sid,
        )
    if lanz is None:
        tel.mux.crear_tab(nombre, ruta=carpeta_hilo, foco=True)
    else:
        tel.mux.crear_tab(nombre, ruta=lanz.carpeta, comando=lanz.comando, foco=True)
    est.vincular(nombre, relativa)
    lanzar.anotar(ctx.config, nombre, lanz)
    _ir(tel, nombre)
    return {"hilo": nombre, "ruta": relativa, "mensaje": texto if lanz else "", "hecho": "abierto"}


def _ir(tel, nombre: str) -> None:
    hilo = next((h for h in tel.mux.hilos() if h.nombre == nombre), None)
    if hilo is not None:
        tel.mux.ir(hilo.id)


def _agente(ctx):
    from telar import agente as mod_agente

    return mod_agente.obtener(ctx.config.agente.nombre, ctx.config)


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("proyectos", AYUDA)
    p.add_argument("verbo", nargs="?", choices=("abrir",), help="abrir: un hilo cargando esa unidad")
    p.add_argument("ruta", nargs="?", default="", help="con abrir: la unidad, relativa a la raíz")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "abrir" and not o.ruta:
        return _comun.queja("¿cuál? telar proyectos abrir <ruta relativa a la raíz>")

    tel = _comun.tejer(ctx, con_ficha=False)
    if o.verbo != "abrir":
        lista = listar(ctx, tel)
        if o.json:
            return _comun.escribir_json({"raiz": str(ctx.config.raiz), "proyectos": lista})
        ancho = min(max((len(x["nombre"]) for x in lista), default=0), 48)
        for x in lista:
            nombre = x["nombre"] if len(x["nombre"]) <= ancho else x["nombre"][: ancho - 1] + "…"
            fecha = (x["modificado"] or "")[:10]
            marca = "●" if x["vivo"] else "·" if x["hilo"] else " "
            print(f"{marca} {nombre:<{ancho}}  {fecha}  " + _comun.tenue(f"{x['arquetipo']} · {x['ruta']}"))
        print(_comun.tenue(f"{len(lista)} unidades · ● con hilo abierto · telar proyectos abrir <ruta>"))
        return 0

    if tel.mux is None or not tel.viva:
        return _comun.queja(tel.aviso or "la sesión no está viva: primero telar tejer")
    try:
        r = abrir(ctx, tel, o.ruta)
    except ValueError as e:
        return _comun.queja(str(e))
    except (ErrorDeMux, ErrorDeAgente) as e:
        return _comun.queja(f"no pude abrirlo: {e}")
    if o.json:
        return _comun.escribir_json(r)
    print(f"{r['hilo']} · {r['hecho']}")
    if r["mensaje"]:
        print(_comun.tenue(f"  {r['mensaje']}"))
    return 0
