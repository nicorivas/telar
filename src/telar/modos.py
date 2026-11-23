"""Los modos de la página: un nombre con valores para un catálogo fijo de ajustes (docs/propuestas/modos.md y
orden-por-modos.md).

    CATALOGO                  cada ajuste: su grupo, su nombre y sus valores
    DE_FABRICA                «tactica», «estrategia», «foco» y «todo»: las cuatro actitudes
    validar(clave, valores)   los valores de un modo, normalizados; ErrorDeConfig si alguno no sirve
    todos(config)             cada modo con sus valores completos (lo que no dice, de su base y de «tactica»), lo que
                              dice su tabla (`propios`), a qué vuelve cada uno sin ella (`heredados`) y de qué modo
                              sale lo que no es de su fábrica (`origenes`)
    pestanas_que_hay(config)  las claves de las pestañas del dashboard con esta configuración (las que `filas` nombra)
    revisar_filas             `filas` desde la página: solo pestañas que hay (o que el modo ya nombraba)
    guardar / borrar          escribir o quitar `[modos.<clave>]` en la configuración
    ajustar                   cambiar solo algunos ajustes de un modo, sin tocar los demás (la grilla de agentes)

Los cuatro de fábrica son las actitudes de la página: táctica (decidir y hacer; la de partida), estrategia (mirar con
calma: abre en proyectos, con el tablero y las decisiones —módulos tablero y registro— al lado), foco (solo la terminal) y todo (ver y buscar todo). Cada uno dice sus ajustes: qué filas de DASHBOARD se ven
(`filas`), la barra, la terminal, los avisos. Un modo propio se arma sobre uno de ellos (`base`, táctica si no lo dice)
y cambia lo que quiera. Lo que un modo no dice lo toma de su base, y la base de todo es «tactica», que toma la terminal
de `[terminal]`; salvo `agentes`, que no se hereda: cada modo dice qué agentes residentes se ven en él, y sin decirlo,
todos. «estandar», el de antes, es un alias de «tactica»: `[modos.estandar]` se lee como `[modos.tactica]`.
Cuál está puesto lo sabe el navegador (pagina/src/web/modos.ts), no esta máquina.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CLAVE = re.compile(r"^[a-z][a-z0-9-]{0,23}$")


@dataclass(frozen=True)
class Ajuste:
    clave: str
    grupo: str
    nombre: str
    #: los valores posibles; vacío para los de la terminal, que valida `config.validar_terminal`
    opciones: tuple[str, ...] = ()
    ayuda: str = ""


#: los temas de la página (sus colores: pagina/media/css/tokens.css y temas.css; los mismos de
#: pagina/src/componentes/temas.ts); /componentes los muestra lado a lado. Los tres últimos son cálidos, para la noche
#: (poca luz azul): un mundo los puede llevar (`[mundos.<n>] tema`)
TEMAS = ("telar", "latte", "riso", "papel", "brasa", "rescoldo", "ambar")
#: las densidades: cuánto aire lleva cada fila (pagina/media/css/densidades.css; los mismos de
#: pagina/src/componentes/densidades.ts), más «auto»: amplia en una pantalla táctil, compacta con mouse
DENSIDADES = ("auto", "compacta", "comoda", "amplia")

CATALOGO: tuple[Ajuste, ...] = (
    Ajuste("tema", "aspecto", "tema", TEMAS, "los colores de la página; /componentes los muestra lado a lado"),
    Ajuste("densidad", "aspecto", "densidad", DENSIDADES,
           "cuánto aire lleva cada fila: amplia es para el dedo; auto, amplia en una pantalla táctil y compacta con mouse"),
    Ajuste("barra", "disposición", "barra de hilos", ("abierta", "plegada", "oculta")),
    Ajuste("lado", "disposición", "ficha de un agente", ("abierto", "plegado", "oculto"), "a la derecha de un hilo de agente"),
    Ajuste("cabecera", "disposición", "cabecera", ("visible", "oculta"), "oculta, un ◧ arriba a la derecha vuelve"),
    Ajuste("acciones", "disposición", "barra del hilo", ("visible", "oculta"), "sus vistas y su carpeta"),
    Ajuste("escribir", "disposición", "caja para escribir", ("visible", "oculta"), "la de abajo de la terminal"),
    Ajuste("pantalla_completa", "disposición", "pantalla completa", ("no", "si")),
    Ajuste("columnas", "terminal", "ancho", (), "columnas de 40 a 400, o 0: todo"),
    Ajuste("posicion", "terminal", "posición", ("izquierda", "centro", "derecha")),
    Ajuste("fondo", "terminal", "fondo", (), "telar, ninguno, #rrggbb, imagen:… o un módulo"),
    Ajuste("etiquetas", "hilos", "solo con las etiquetas", (),
           "los hilos con alguna de estas etiquetas (trabajo, personal…); vacío: todos"),
    Ajuste("sin_etiqueta", "hilos", "los sin etiqueta", ("se-ven", "no-se-ven"), "con un filtro de etiquetas puesto"),
    Ajuste("agentes", "hilos", "agentes que se ven", (),
           "los agentes residentes que salen en AGENTES, por su carpeta, separados por coma; vacío: todos; «-»: ninguno. "
           "No se hereda: cada modo dice los suyos"),
    Ajuste("proyectos", "proyectos", "qué son proyectos", (),
           "los tipos de unidad (arquetipos del perfil: proyecto, proyecto propio…) que lista la pantalla de proyectos; "
           "vacío: todas las unidades"),
    Ajuste("negocios", "proyectos", "qué son negocios", (),
           "los tipos de unidad que son negocios por cerrar: la pantalla de proyectos dice cuántos hay en propuesta y en "
           "negociación; vacío: no los cuenta"),
    Ajuste("iniciativas", "proyectos", "qué son iniciativas", (),
           "los tipos de unidad que son iniciativas internas (el trabajo propio, sin cliente): la pantalla de proyectos "
           "las pone en su sección, aparte de los proyectos; vacío: no hay sección"),
    Ajuste("agrupar_iniciativas", "proyectos", "iniciativas por", (),
           "el campo del frontmatter con que se agrupan las iniciativas, {frontmatter:<clave>} (el programa al que "
           "pertenecen); vacío: sin agrupar"),
    Ajuste("area", "proyectos", "área de entrada", (),
           "el área (o las áreas, separadas por coma) con que abría filtrada la tabla de proyectos e iniciativas de la "
           "pantalla estrategia, que se sacó (19-nov-2026): hoy ninguna pantalla lo usa. Se lee igual, para no romper "
           "la configuración"),
    Ajuste("glifos", "glifos", "glifos de risografía", ("no", "si"), "el interruptor de todo: «no» deja la página como siempre"),
    Ajuste("estilo", "glifos", "estilo de los glifos", (), "cuál de [glifos.<estilo>]: sus tintas, su vida, sus gestos (⚙ glifos)"),
    Ajuste("iconos", "glifos", "íconos de los hilos", ("simbolos", "glifos"), "en la barra: los símbolos de siempre, o el glifo de cada hilo con su estado"),
    Ajuste("campo", "glifos", "campo de glifos", (),
           "dónde, por pantalla: «ahora=banda, calendario=fondo 0.15, *=nada» (banda arriba, fondo detrás o nada; la intensidad, de 0.05 a 1)"),
    Ajuste("filas", "disposición", "filas de DASHBOARD", (),
           "las pestañas que se ven en DASHBOARD, por su clave (tactica, calendario, proyectos, bloque:correo…), separadas "
           "por coma; * todas"),
    Ajuste("mundo", "mundo", "mundo al ponerse", (), "el de [mundos] que pone este modo al ponerse (a mano); vacío, no lo toca"),
    Ajuste("avisos", "avisos", "avisos", ("todos", "urgentes", "ninguno"),
           "los de abajo a la derecha, que responden a lo que se aprieta; urgentes: solo los de algo que falló o pide atención"),
    Ajuste("aviso_version", "avisos", "aviso de versión nueva", ("visible", "oculto"),
           "la versión y la página nuevas, en la franja de avisos de arriba de la barra"),
)
POR_CLAVE = {a.clave: a for a in CATALOGO}
TERMINAL = ("columnas", "posicion", "fondo")

#: los modos de fábrica, las cuatro actitudes, en su orden (el de las teclas ⌥⇧1–4 y la cabecera). «tactica» dice todo
#: (la terminal, de `[terminal]`: ver `todos`); los demás, lo que cambian
DE_FABRICA: dict[str, dict] = {
    "tactica": {"nombre": "táctica", "valores": {
        "barra": "abierta", "lado": "abierto", "cabecera": "visible", "acciones": "visible", "escribir": "oculta",
        "pantalla_completa": "no", "etiquetas": "", "sin_etiqueta": "se-ven", "agentes": "", "proyectos": "", "negocios": "", "iniciativas": "", "agrupar_iniciativas": "", "area": "",
        "glifos": "no", "estilo": "base", "iconos": "simbolos", "campo": "",
        "filas": "tactica, calendario", "mundo": "", "avisos": "todos",
        "aviso_version": "visible", "tema": "telar", "densidad": "auto"}},
    "estrategia": {"nombre": "estrategia", "valores": {"filas": "proyectos, bloque:tablero, bloque:registro", "avisos": "urgentes"}},
    "foco": {"nombre": "foco", "valores": {
        "barra": "oculta", "lado": "oculto", "cabecera": "oculta", "acciones": "oculta", "escribir": "oculta",
        "pantalla_completa": "no", "columnas": 110, "posicion": "centro", "fondo": "ninguno", "avisos": "urgentes",
        "aviso_version": "oculto"}},
    "todo": {"nombre": "todo", "valores": {"filas": "*"}},
}
#: los nombres de antes que siguen valiendo: `[modos.estandar]` es `[modos.tactica]`
ALIAS = {"estandar": "tactica"}


def validar(clave: str, cuerpo: dict) -> dict:
    """`[modos.<clave>]`: {nombre, valores}, con cada valor normalizado. ErrorDeConfig si algo no sirve."""
    from telar.config import ErrorDeConfig, validar_terminal

    if not CLAVE.match(clave):
        raise ErrorDeConfig(f"modos.{clave}: el nombre va en minúsculas, con letras, números y guiones")
    if not isinstance(cuerpo, dict):
        raise ErrorDeConfig(f"modos.{clave}: tiene que ser una tabla")
    nombre = cuerpo.get("nombre", "")
    if not isinstance(nombre, str) or len(nombre) > 40:
        raise ErrorDeConfig(f"modos.{clave}.nombre: un texto corto")
    base = cuerpo.get("base", "")
    if base and (base not in DE_FABRICA or clave in DE_FABRICA or clave in ALIAS):
        raise ErrorDeConfig(f"modos.{clave}.base: uno de {', '.join(DE_FABRICA)}, y solo en un modo propio; llegó {base!r}")
    valores = {}
    for k, v in cuerpo.items():
        if k in ("nombre", "base"):
            continue
        a = POR_CLAVE.get(k)
        if a is None:
            raise ErrorDeConfig(f"modos.{clave}.{k}: no es un ajuste ({', '.join(POR_CLAVE)})")
        if k == "etiquetas":
            from telar.modelo import normalizar_etiquetas

            try:
                valores[k] = ",".join(normalizar_etiquetas(v))
            except ValueError as e:
                raise ErrorDeConfig(f"modos.{clave}.etiquetas: {e}") from None
        elif k == "agentes":
            valores[k] = _agentes(clave, v)
        elif k in ("proyectos", "negocios", "iniciativas"):
            valores[k] = _tipos(clave, k, v)
        elif k == "agrupar_iniciativas":
            valores[k] = _selector(clave, k, v)
        elif k == "area":
            valores[k] = _areas(clave, v)
        elif k == "estilo":
            v = str(v).strip() or "base"
            if not CLAVE.match(v):
                raise ErrorDeConfig(f"modos.{clave}.estilo: el nombre de un estilo de [glifos], en minúsculas; llegó {v!r}")
            valores[k] = v
        elif k == "campo":
            valores[k] = _campo(clave, v)
        elif k == "filas":
            valores[k] = _filas(clave, v)
        elif k == "mundo":
            v = str(v or "").strip()
            if v and not re.fullmatch(r"[^\s,:/]+", v):
                raise ErrorDeConfig(f"modos.{clave}.mundo: el nombre de un mundo de [mundos]; llegó {v!r}")
            valores[k] = v
        elif k == "tema":
            # uno de fábrica o el nombre de uno propio: si existe (`[temas.<nombre>] base`) lo revisa la configuración
            # entera (config._temas_de_modos), que sabe cuáles hay
            from telar.temas import NOMBRE

            v = str(v or "").strip().lower()
            if v not in TEMAS and not NOMBRE.fullmatch(v):
                raise ErrorDeConfig(f"modos.{clave}.tema: {' · '.join(TEMAS)} o uno propio de [temas]; llegó {v!r}")
            valores[k] = v
        elif k in TERMINAL:
            try:
                valores[k] = validar_terminal(k, v)
            except ErrorDeConfig as e:
                raise ErrorDeConfig(f"modos.{clave}: {e}") from None
        else:
            if isinstance(v, bool) and a.opciones == ("no", "si"):
                v = "si" if v else "no"
            v = str(v).strip().lower().replace("sí", "si")
            if v not in a.opciones:
                raise ErrorDeConfig(f"modos.{clave}.{k}: {' · '.join(a.opciones)}; llegó {v!r}")
            valores[k] = v
    return {"nombre": nombre.strip(), **({"base": base} if base else {}), "valores": valores}


def _filas(clave: str, v) -> str:
    """`filas`: las claves de las pestañas, separadas por coma (o una lista); `*`, todas. Normalizado."""
    from telar.config import ErrorDeConfig

    crudo = ",".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
    salida: list[str] = []
    for parte in (x.strip() for x in crudo.split(",")):
        if not parte:
            continue
        if parte != "*" and not re.fullmatch(r"[\w:.-]+", parte):
            raise ErrorDeConfig(f"modos.{clave}.filas: claves de pestañas (tactica, calendario, bloque:correo…) o *; llegó {parte!r}")
        if parte not in salida:
            salida.append(parte)
    return "*" if "*" in salida else ", ".join(salida)


#: `agentes` de un modo que no muestra ninguno (vacío es todos)
NINGUNO = "-"


def _agentes(clave: str, v) -> str:
    """`agentes`: las carpetas de los agentes que se ven, separadas por coma (o una lista); su dirección
    (`agente:<carpeta>`) también vale. Vacío o `*`, todos; `-`, ninguno. Normalizado: sin repetir, en su orden."""
    from telar.agentes import PREFIJO
    from telar.config import ErrorDeConfig

    crudo = ",".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
    salida: list[str] = []
    for parte in (x.strip() for x in crudo.split(",")):
        if parte.startswith(PREFIJO):
            parte = parte[len(PREFIJO):].strip()
        if not parte:
            continue
        if parte not in ("*", NINGUNO) and not re.fullmatch(r"[^\s,:/]+", parte):
            raise ErrorDeConfig(f"modos.{clave}.agentes: las carpetas de los agentes, separadas por coma, * o -; llegó {parte!r}")
        if parte not in salida:
            salida.append(parte)
    if "*" in salida:
        return ""
    if NINGUNO in salida:
        if len(salida) > 1:
            raise ErrorDeConfig(f"modos.{clave}.agentes: «-» (ninguno) va solo; llegó {crudo.strip()!r}")
        return NINGUNO
    return ", ".join(salida)


def _tipos(clave: str, k: str, v) -> str:
    """`proyectos`, `negocios`, `iniciativas`: nombres de arquetipos separados por coma (llevan espacios: «proyecto cerrado»).
    Normalizado: sin espacios de más, sin repetir, en minúsculas."""
    from telar.config import ErrorDeConfig

    crudo = ",".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
    salida: list[str] = []
    for parte in crudo.split(","):
        nombre = " ".join(parte.split()).lower()
        if not nombre:
            continue
        if len(nombre) > 40 or not re.match(r"^[\w][\w .-]*$", nombre):
            raise ErrorDeConfig(f"modos.{clave}.{k}: nombres de arquetipos separados por coma; llegó {parte.strip()!r}")
        if nombre not in salida:
            salida.append(nombre)
    return ",".join(salida)


def _areas(clave: str, v) -> str:
    """`area`: los nombres de las áreas (el `area:` del frontmatter de una unidad), separados por coma (o una lista); llevan
    espacios y mayúsculas, como las escribe cada ficha. Normalizado: sin espacios de más, sin repetir (sin mirar
    mayúsculas ni tildes), en su orden; vacío, ninguna (todas)."""
    from telar.config import ErrorDeConfig
    from telar.iniciativas import normalizar

    crudo = ",".join(str(x) for x in v) if isinstance(v, list) else str(v or "")
    salida: list[str] = []
    vistas: set[str] = set()
    for parte in crudo.split(","):
        nombre = " ".join(parte.split())
        if not nombre:
            continue
        if len(nombre) > 40 or not re.match(r"^[\w][\w .&/-]*$", nombre):
            raise ErrorDeConfig(f"modos.{clave}.area: nombres de áreas separados por coma; llegó {parte.strip()!r}")
        if normalizar(nombre) not in vistas:
            vistas.add(normalizar(nombre))
            salida.append(nombre)
    return ", ".join(salida)


#: `{frontmatter:<clave>}`: un campo del frontmatter de una unidad, como en productos.yaml (docs/perfil.md)
SELECTOR = re.compile(r"^(?:\{?\s*frontmatter\s*:\s*)?([A-Za-z_][\w-]*)(?:\s*\})?$")


def _selector(clave: str, k: str, v) -> str:
    """`agrupar_iniciativas`: un campo del frontmatter, `{frontmatter:<clave>}` (sin las llaves también vale; y solo la
    clave). Normalizado con las llaves; vacío, sin agrupar."""
    from telar.config import ErrorDeConfig

    crudo = str(v or "").strip()
    if not crudo:
        return ""
    m = SELECTOR.match(crudo)
    if not m or crudo.startswith("{") != crudo.endswith("}"):
        raise ErrorDeConfig(f"modos.{clave}.{k}: un campo del frontmatter, {{frontmatter:<clave>}}; llegó {crudo!r}")
    return "{frontmatter:" + m.group(1) + "}"


CAMPO = re.compile(r"^([^=\s]+)\s*=\s*(banda|fondo|nada)(?:\s+(\d*\.?\d+))?$")


def _campo(clave: str, v) -> str:
    """`campo`: «pantalla=lugar [intensidad]», separadas por coma (`*`, las que no se nombran). Normalizado."""
    from telar.config import ErrorDeConfig

    partes = []
    for crudo in str(v or "").split(","):
        crudo = crudo.strip()
        if not crudo:
            continue
        m = CAMPO.match(crudo)
        if not m:
            raise ErrorDeConfig(f"modos.{clave}.campo: «{crudo}» no es «pantalla=banda|fondo|nada [intensidad]»")
        pantalla, lugar, intensidad = m.groups()
        if intensidad is not None and not 0.05 <= float(intensidad) <= 1:
            raise ErrorDeConfig(f"modos.{clave}.campo: la intensidad va de 0.05 a 1; llegó {intensidad}")
        partes.append(f"{pantalla}={lugar}" + (f" {intensidad}" if intensidad is not None else ""))
    return ", ".join(partes)


def con_alias(propios: dict) -> dict:
    """Los modos de la configuración con los nombres de antes pasados a los de ahora (`estandar` → `tactica`): si están
    los dos, lo del nuevo gana."""
    salida = dict(propios)
    for viejo, nuevo in ALIAS.items():
        if viejo not in salida:
            continue
        antes = salida.pop(viejo)
        ahora = salida.get(nuevo, {})
        salida[nuevo] = {"nombre": ahora.get("nombre") or antes.get("nombre", ""),
                         "valores": {**antes.get("valores", {}), **ahora.get("valores", {})}}
    return salida


def todos(config) -> list[dict]:
    """Cada modo, con todos sus valores: los de fábrica y los de la configuración (`[modos.<n>]`, que pisan a uno de
    fábrica con su mismo nombre). Lo que no dice, de su base (la suya, de fábrica, o la que declara uno propio:
    táctica si no la dice) y de «tactica»; la terminal de «tactica», de `[terminal]`. Cada uno dice su `base`."""
    t = config.terminal
    propios = con_alias(getattr(config, "modos", {}) or {})
    tactica = {**DE_FABRICA["tactica"]["valores"], "columnas": t.columnas, "posicion": t.posicion, "fondo": t.fondo,
               **propios.get("tactica", {}).get("valores", {})}
    resueltos = {"tactica": tactica}
    for k in DE_FABRICA:
        if k != "tactica":
            resueltos[k] = {**tactica, **DE_FABRICA[k]["valores"], **propios.get(k, {}).get("valores", {})}
    salida = []
    for k in [*DE_FABRICA, *(x for x in propios if x not in DE_FABRICA)]:
        fabrica = DE_FABRICA.get(k, {})
        propio = propios.get(k, {})
        base = k if k in DE_FABRICA else propio.get("base") or "tactica"
        valores = resueltos[k] if k in DE_FABRICA else {**resueltos[base], **propio.get("valores", {})}
        # los agentes no se heredan: los de este modo, o todos
        valores = {**valores, "agentes": propio.get("valores", {}).get("agentes", "")}
        # lo que el modo dice en su tabla, y lo que diría cada uno de esos ajustes sin su línea (lo de fábrica o de su
        # base): ⚙ modos muestra qué es propio y a qué vuelve al quitarlo
        sin_lo_suyo = _heredado(k, base, t, propios)
        dice = list(propio.get("valores", {}))
        salida.append({"clave": k, "nombre": propio.get("nombre") or fabrica.get("nombre") or k, "base": base, "valores": valores,
                       "de_fabrica": k in DE_FABRICA, "cambiado": k in propios, "propios": dice,
                       "heredados": {a: sin_lo_suyo.get(a, "") for a in dice},
                       "origenes": _origenes(k, base, propios)})
    return salida


def _origenes(clave: str, base: str, propios: dict) -> dict:
    """De dónde sale cada ajuste del modo `clave` sin su propia línea, si no es de su fábrica: la clave del modo que lo
    dice (`tactica`, o su base). Lo que no está, de fábrica (o, en uno propio, de su base de fábrica)."""
    def dice(k: str) -> set:
        return set(DE_FABRICA.get(k, {}).get("valores", {})) | set(propios.get(k, {}).get("valores", {}))

    if clave == "tactica":
        return {}
    if clave in DE_FABRICA:
        return {a: "tactica" for a in POR_CLAVE if a != "agentes" and a not in DE_FABRICA[clave]["valores"]}
    if base == "tactica":
        return {a: "tactica" for a in POR_CLAVE if a != "agentes"}
    return {a: base if a in dice(base) else "tactica" for a in POR_CLAVE if a != "agentes"}


def _heredado(clave: str, base: str, t, propios: dict) -> dict:
    """Los valores que tendría el modo `clave` sin su tabla: uno de fábrica, los de fábrica (sobre «tactica» como la
    deja la configuración, salvo «tactica» misma, que toma solo los de fábrica y `[terminal]`); uno propio, los de su
    base, como los deja la configuración. `agentes` sin decirlo es todos."""
    tactica_fabrica = {**DE_FABRICA["tactica"]["valores"], "columnas": t.columnas, "posicion": t.posicion, "fondo": t.fondo}
    tactica = {**tactica_fabrica, **propios.get("tactica", {}).get("valores", {})}
    if clave == "tactica":
        sin = tactica_fabrica
    elif clave in DE_FABRICA:
        sin = {**tactica, **DE_FABRICA[clave]["valores"]}
    else:
        sin = tactica if base == "tactica" else {**tactica, **DE_FABRICA[base]["valores"], **propios.get(base, {}).get("valores", {})}
    return {**sin, "agentes": ""}


#: las pestañas fijas del dashboard, en su orden de siempre (pagina/src/vistas/dashboard/panel.ts, todasLasPestanas):
#: entre «revisar» y «proyectos» van las de los bloques y las de los proveedores
PESTANAS_FIJAS = ("todo", "tactica", "ahora", "esperas", "revisar", "proyectos", "calendario")
#: otros nombres con que `filas` nombra una pestaña (pagina/src/vistas/dashboard/orden-pestanas.ts, ALIAS_FILA)
ALIAS_PESTANA = {"tareas": "revisar"}


def pestanas_que_hay(config) -> list[str]:
    """Las claves de las pestañas que el dashboard puede mostrar con esta configuración, en su orden de siempre: las fijas,
    `bloque:<clave>` por cada bloque que no va dentro de otro (los de los módulos) y `pestana:<nombre>` por cada
    proveedor activo que declara su pestaña."""
    bloques = [f"bloque:{b.clave}" for b in getattr(config, "bloques", ()) if not getattr(b, "dentro", "")]
    try:
        proveedores = [f"pestana:{p.opciones['pestana']}" for p in config.proveedores_activos() if p.opciones.get("pestana")]
    except AttributeError:
        proveedores = []
    i = PESTANAS_FIJAS.index("proyectos")
    return list(dict.fromkeys([*PESTANAS_FIJAS[:i], *bloques, *proveedores, *PESTANAS_FIJAS[i:]]))


def revisar_filas(config, clave: str, valor) -> str:
    """`filas` para escribir en el modo `clave` desde la página (⚙ modos): normalizado, con al menos una pestaña, y cada
    una de las que hay hoy (`pestanas_que_hay`) o de las que el modo ya nombraba (la de un módulo que se desinstaló se
    conserva hasta que vuelva). Una pestaña que se sacó del dashboard (`PESTANAS_RETIRADAS`: estrategia, el plan) no se
    conserva: se quita. ErrorDeConfig si no; KeyError si no hay un modo `clave`."""
    from telar.config import ErrorDeConfig, PESTANAS_RETIRADAS

    clave = ALIAS.get(clave, clave)
    v = _filas(clave, valor)
    if v != "*":
        v = ", ".join(x for x in v.split(", ") if x and x not in PESTANAS_RETIRADAS)
    if not v:
        raise ErrorDeConfig(f"modos.{clave}.filas: un modo ve al menos una pestaña (o * todas); para volver a lo heredado, null")
    actual = next((m for m in todos(config) if m["clave"] == clave), None)
    if actual is None:
        raise KeyError(clave)
    if v == "*":
        return v
    nombradas = {x.strip() for x in str(actual["valores"].get("filas", "")).split(",")}
    hay = pestanas_que_hay(config)
    for parte in v.split(", "):
        if parte not in hay and parte not in ALIAS_PESTANA and parte not in nombradas:
            raise ErrorDeConfig(f"modos.{clave}.filas: «{parte}» no es una pestaña del dashboard; las que hay: {', '.join(hay)}")
    return v


def catalogo(config=None) -> list[dict]:
    """Los ajustes de un modo, con sus valores posibles; los del tema, con los propios de esa configuración (`[temas]`)."""
    from telar import temas as mod_temas

    def opciones(a: Ajuste) -> list[str]:
        return list(mod_temas.que_hay(config)) if a.clave == "tema" and config is not None else list(a.opciones)

    return [{"clave": a.clave, "grupo": a.grupo, "nombre": a.nombre, "opciones": opciones(a), "ayuda": a.ayuda}
            for a in CATALOGO]


def guardar(ruta: Path | None, clave: str, valores: dict, nombre: str = "", *, base: str = "") -> dict:
    """Escribe `[modos.<clave>]` con esos valores (los reemplaza enteros: lo que no venga, se quita de la tabla). De
    uno propio, `base`: sobre cuál de los cuatro se arma. Por su nombre de antes (`estandar`), el de ahora."""
    from telar import config as mod_config

    clave = ALIAS.get(clave, clave)
    limpio = validar(clave, {**({"nombre": nombre} if nombre else {}), **({"base": base} if base else {}), **valores})
    destino = Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()
    _quitar(destino, clave)
    # el nombre de antes se va con lo de ahora: lo que decía, ya viene en `valores` (la página manda el modo entero)
    for viejo, nuevo in ALIAS.items():
        if nuevo == clave:
            _quitar(destino, viejo)
    if limpio["nombre"]:
        mod_config.escribir_clave(f"modos.{clave}", "nombre", limpio["nombre"], destino)
    if limpio.get("base"):
        mod_config.escribir_clave(f"modos.{clave}", "base", limpio["base"], destino)
    for k, v in limpio["valores"].items():
        mod_config.escribir_clave(f"modos.{clave}", k, v, destino)
    return limpio


def ajustar(ruta: Path | None, clave: str, valores: dict) -> dict:
    """Cambia solo esos ajustes de `[modos.<clave>]`, línea por línea: lo demás de la tabla y del archivo queda como
    estaba, y lo que el modo hereda sigue heredándose (`guardar` reemplaza la tabla entera). Un valor None quita su
    línea, y `agentes` vacío (todos, lo de fábrica) también; uno de fábrica que se queda sin nada vuelve a ser el de
    fábrica. Devuelve los valores escritos, normalizados. KeyError si es uno propio que no está; ErrorDeConfig si un
    valor no sirve."""
    from telar import config as mod_config

    clave = ALIAS.get(clave, clave)
    destino = Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()
    if clave not in DE_FABRICA and clave not in _propios(destino):
        raise KeyError(clave)
    limpio = validar(clave, {k: v for k, v in valores.items() if v is not None})["valores"]
    for k in valores:
        v = limpio.get(k)
        quitar = v is None or (k == "agentes" and v == "")
        mod_config.escribir_clave(f"modos.{clave}", k, None if quitar else v, destino)
        if quitar:
            # lo que decía con su nombre de antes (`[modos.estandar]`) se iría a leer en su lugar
            for viejo, nuevo in ALIAS.items():
                if nuevo == clave:
                    mod_config.escribir_clave(f"modos.{viejo}", k, None, destino)
    if clave in DE_FABRICA:
        quedo = _propios(destino).get(clave)
        if quedo is not None and not quedo.get("nombre") and not quedo.get("valores"):
            borrar(destino, clave)
    return limpio


def _propios(destino: Path) -> dict:
    """Los `[modos]` de ese archivo, validados y con los nombres de antes pasados a los de ahora."""
    import tomllib

    if not destino.exists():
        return {}
    tabla = tomllib.loads(destino.read_text(encoding="utf-8")).get("modos", {})
    return con_alias({k: validar(k, v) for k, v in tabla.items()}) if isinstance(tabla, dict) else {}


def borrar(ruta: Path | None, clave: str) -> bool:
    """Quita `[modos.<clave>]`: uno propio desaparece, uno de fábrica vuelve a ser el de fábrica. True si estaba."""
    from telar import config as mod_config

    destino = Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()
    quitado = _quitar(destino, clave)
    for viejo, nuevo in ALIAS.items():
        if nuevo == clave:
            quitado = _quitar(destino, viejo) or quitado
    return quitado


def _quitar(destino: Path, clave: str) -> bool:
    from telar import config as mod_config
    from telar.unirse import quitar_tabla

    if not CLAVE.match(clave) or not destino.exists():
        return False
    texto = destino.read_text(encoding="utf-8")
    nuevo = quitar_tabla(texto, f"modos.{clave}")
    if nuevo == texto:
        return False
    mod_config.revisar_antes_de_escribir(texto, nuevo, destino)  # que se siga leyendo
    tmp = destino.with_name(destino.name + ".nuevo")
    tmp.write_text(nuevo, encoding="utf-8")
    tmp.replace(destino)
    return True
