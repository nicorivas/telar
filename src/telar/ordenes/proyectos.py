"""`telar proyectos` — todas las unidades del perfil, tengan hilo o no, y abrir una.

    telar proyectos                        la lista: nombre, arquetipo, ruta, cuándo se tocó
    telar proyectos --json
    telar proyectos abrir operacion/faro   un hilo vinculado a esa unidad, con el agente
                                           ya cargándola; si ya tiene hilo abierto, va a él
    telar proyectos estado operacion/club "en pausa"
                                           el estado de una iniciativa, en su ficha: uno del
                                           vocabulario de [iniciativas] (telar.iniciativas)

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

from telar import lectura, objetos
from telar.agente import lanzar
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


#: una línea `clave: valor` del frontmatter (la misma regla que telar.tipos.registro)
_CAMPO_FM = re.compile(r"^([A-Za-z_][\w-]*)[ \t]*:[ \t]?(.*)$")
#: el valor más largo que se lleva de un campo: lo que pasa de eso es un texto, no un dato para mostrar en una fila
LARGO_FM = 300


def frontmatter_de(documento: Path) -> dict[str, str]:
    """Los campos sueltos del frontmatter del documento, `clave: valor`, como texto, en su orden: sin comillas ni el
    comentario del final, y sin los vacíos ni los que pasan de LARGO_FM. Una lista o un mapa (lo que sigue en las
    líneas de abajo) no entra. {} si no tiene frontmatter. Solo se lee el comienzo: el frontmatter va arriba, y un
    documento largo no tiene por qué leerse entero aquí."""
    try:
        with open(documento, encoding="utf-8", errors="ignore") as f:
            cabeza = f.read(4096)
    except OSError:
        return {}
    m = re.match(r"\ufeff?---\r?\n(.*?)\r?\n---", cabeza, re.S)
    if not m:
        return {}
    campos: dict[str, str] = {}
    for linea in m.group(1).splitlines():
        c = _CAMPO_FM.match(linea)
        if not c or c.group(1) in campos:
            continue
        v = c.group(2).strip()
        entre = re.match(r"^([\"'])(.*?)\1\s*(?:#.*)?$", v)
        v = entre.group(2).strip() if entre else re.sub(r"\s+#.*$", "", v)
        if v and len(v) <= LARGO_FM and not v.startswith(("[", "{", "|", ">")):
            campos[c.group(1)] = v
    return campos


def area_de(documento: Path) -> str:
    """El `area:` del frontmatter del documento («area: Norte»), o "" si no la declara."""
    return frontmatter_de(documento).get("area", "")


def vigente(estado: str) -> str:
    """El Estado sin lo tachado: «~~Activo, sin empezar~~ **16-oct: activo**» → «**16-oct: activo**». Lo tachado
    es lo que ya no vale; quien lo tachó dejó al lado lo que sí."""
    return re.sub(r"\s+", " ", re.sub(r"~~.*?~~", "", estado)).strip()


def corto(estado: str, largo: int = 24) -> str:
    """«En pausa por el cliente desde el 9-sep. Ver Notas» → «En pausa por el cliente…»: lo de antes
    del primer punto, coma, dos puntos, paréntesis o punto medio («Activo · PMO: pista» → «Activo»), y no más de
    `largo` letras. Sin lo tachado y sin la fecha de adelante de una nota («16-oct: activo, en la semana 2» →
    «Activo»)."""
    texto = vigente(estado).replace("**", "")
    texto = re.sub(r"^\d{1,2}-[a-zé]{3,4}\.?(-\d{2,4})?\s*:\s*", "", texto, flags=re.I)
    texto = re.split(r"[.,;:(·]|\s[—–-]\s", texto, maxsplit=1)[0].strip()
    texto = texto[:1].upper() + texto[1:]
    return texto if len(texto) <= largo else texto[: largo - 1].rstrip() + "…"


def listar(ctx, tel) -> list[dict]:
    raiz = Path(ctx.config.raiz)
    unidades = lectura.indice(ctx.perfil, raiz)
    vinculos = tel.estado.vinculos()
    hilo_de = {ruta: hilo for hilo, ruta in vinculos.items()}
    fuente = _comun.fuente_ficha(ctx.config)
    internos = {x.casefold() for x in ctx.perfil.internos}
    salida = []
    for relativa, (arquetipo, documento) in unidades.items():
        ficha = _comun.leer_ficha(documento, arquetipo, fuente)
        nombre = lectura.etiqueta(arquetipo.etiqueta, ficha) or Path(relativa).name
        campos = (getattr(ficha, "secciones", {}) or {}).get("campos") or {}
        estado = str(campos.get("Estado") or campos.get("Etapa") or "").strip()
        mtime = reciente(raiz / relativa)
        hilo = hilo_de.get(relativa, "")
        cliente = lectura.etiqueta("{campo:Cliente}", ficha) if "{campo:Cliente}" in (arquetipo.etiqueta or "") else ""
        fm = frontmatter_de(documento)
        salida.append({
            "ruta": relativa,
            # su dirección de objeto (telar.objetos): `telar objeto proyecto:<ruta>`
            "direccion": objetos.direccion_de("proyecto", relativa),
            "nombre": nombre,
            # el cliente, si el nombre lo lleva adelante («Cliente · título»): el dashboard lo destaca
            "cliente": cliente,
            # sin cliente, o con uno que es la casa misma (`internos` del perfil): el dashboard muestra el nombre
            "interno": not cliente or cliente.casefold() in internos,
            # el Estado (o la Etapa, en un deal) de su tabla de campos: corto, y entero aparte
            "estado": corto(estado),
            "estado_completo": vigente(estado),
            # el área que declara el frontmatter del documento («area: PIA»); "" si no la tiene
            "area": fm.get("area", ""),
            # los campos sueltos de su frontmatter, como texto (`{frontmatter:<clave>}`): con qué se agrupan y se
            # describen las iniciativas en el dashboard (`agrupar_iniciativas` de un modo)
            "frontmatter": fm,
            "arquetipo": arquetipo.nombre,
            "modificado": datetime.fromtimestamp(mtime, timezone.utc).isoformat() if mtime else None,
            "hilo": hilo,
            "vivo": bool(hilo) and hilo in tel.vivos,
        })
    salida.sort(key=lambda p: p["nombre"].casefold())
    return salida


def abrir(ctx, tel, relativa: str, *, texto: str = "", nuevo: bool = False) -> dict:
    """Ir al hilo de esa unidad o abrirle uno. Devuelve {hilo, ruta, mensaje, hecho}. Con `texto`, un hilo nuevo
    arranca con eso en vez del mensaje de `[agente] proyecto` (telar actuar: lo que se le pide sobre la unidad); a
    uno que ya estaba no se le escribe aquí. Con `nuevo`, uno nuevo aunque ya tenga el suyo abierto (se numera)."""
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
        if ruta == relativa and hilo in tel.vivos and not nuevo:
            _ir(tel, hilo)
            return {"hilo": hilo, "ruta": relativa, "mensaje": "", "hecho": "ya estaba"}

    ficha = _comun.leer_ficha(documento, arquetipo, _comun.fuente_ficha(ctx.config))
    carpeta = raiz / relativa
    texto = texto or mensaje(
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


def _estado(ctx, o) -> int:
    """`telar proyectos estado <ruta> <estado>`: sin estado, dice el vocabulario."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import proyectos as servicio

    if not o.ruta or not o.estado:
        estados = ctx.config.iniciativas.estados
        return _comun.queja("telar proyectos estado <ruta> <estado>"
                            + (f"; el estado, uno de: {', '.join(estados)}" if estados else "; no hay [iniciativas] estados"))
    try:
        r = servicio.cambiar_estado(ctx, o.ruta, o.estado).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    if r["cambio"]:
        print(f"{r['archivo']} · estado: {r['antes'] or '—'} → {r['estado']} (desde {r['estado_desde']}; sin commitear)")
    else:
        print(f"{r['archivo']} · ya estaba en «{r['estado']}» ({r['antes']}): no lo toqué")
    return 0


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("proyectos", AYUDA)
    p.add_argument("verbo", nargs="?", choices=("abrir", "estado"),
                   help="abrir: un hilo cargando esa unidad; estado: cambiar el de una iniciativa")
    p.add_argument("ruta", nargs="?", default="", help="con abrir o estado: la unidad, relativa a la raíz")
    p.add_argument("estado", nargs="?", default="", help="con estado: uno del vocabulario de [iniciativas]")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "abrir" and not o.ruta:
        return _comun.queja("¿cuál? telar proyectos abrir <ruta relativa a la raíz>")
    if o.verbo == "estado":
        return _estado(ctx, o)

    if o.verbo != "abrir":
        from telar.servicios import proyectos as servicio

        r = servicio.lista(ctx)
        if o.json:
            return _comun.escribir_json(r.model_dump(mode="json"))
        lista = [x.model_dump() for x in r.proyectos]
        ancho = min(max((len(x["nombre"]) for x in lista), default=0), 48)
        for x in lista:
            nombre = x["nombre"] if len(x["nombre"]) <= ancho else x["nombre"][: ancho - 1] + "…"
            fecha = (x["modificado"] or "")[:10]
            marca = "●" if x["vivo"] else "·" if x["hilo"] else " "
            print(f"{marca} {nombre:<{ancho}}  {fecha}  " + _comun.tenue(f"{x['arquetipo']} · {x['ruta']}"))
        print(_comun.tenue(f"{len(lista)} unidades · ● con hilo abierto · telar proyectos abrir <ruta>"))
        return 0

    from telar.servicios import ErrorDeServicio
    from telar.servicios import atajos as servicio_atajos

    try:
        r = servicio_atajos.abrir_unidad(ctx, o.ruta).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    print(f"{r['hilo']} · {r['hecho']}")
    if r["mensaje"]:
        print(_comun.tenue(f"  {r['mensaje']}"))
    return 0
