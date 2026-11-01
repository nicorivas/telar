"""Los estilos de los glifos de risografía de la página: los parámetros del campo, de su vida, del gesto de cada pieza,
del glifo de cada hilo y de sus estados (pagina/src/web/glifos/).

    CATALOGO                  cada parámetro: su grupo, su nombre, su tipo (rango u opciones) y su valor de fábrica
    BASE                      el estilo de fábrica, «base»: lo elegido el 31-oct-2026 y, lo que no se tocó, del prototipo
    validar(estilo, valores)  los valores de un estilo, normalizados; ErrorDeConfig si alguno no sirve
    todos(config)             cada estilo con todos sus valores (lo que no dice, de «base»)
    guardar / borrar          escribir o quitar `[glifos.<estilo>]` en la configuración

Un modo (telar.modos) dice si hay glifos, dónde va el campo y qué estilo usa (`estilo`); el estilo dice cómo se ven.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CLAVE = re.compile(r"^[a-z][a-z0-9-]{0,23}$")

PIEZAS = ("anillo", "aro", "dobleAnillo", "disco", "puntos8", "puntos12", "puntos4", "cruz", "cruzGruesa", "equis",
          "asterisco", "romboPixel", "damero", "cruzPixel", "rombos4", "rombos8", "triangulo", "cuartos", "punto",
          "anilloChico", "romboChico")
NOMBRE_PIEZA = {"anillo": "anillo", "aro": "aro", "dobleAnillo": "doble anillo", "disco": "disco", "puntos8": "8 puntos",
                "puntos12": "12 puntos", "puntos4": "4 puntos", "cruz": "cruz", "cruzGruesa": "cruz gruesa", "equis": "equis",
                "asterisco": "asterisco", "romboPixel": "rombo de píxeles", "damero": "damero", "cruzPixel": "cruz de píxeles",
                "rombos4": "4 rombos", "rombos8": "8 rombos", "triangulo": "triángulo", "cuartos": "cuartos", "punto": "punto",
                "anilloChico": "anillo chico", "romboChico": "rombo chico"}
GESTOS = ("giro", "rueda", "brote", "latido", "salto", "quieta")
GESTO_BASE = {"anillo": "latido", "aro": "latido", "dobleAnillo": "brote", "disco": "latido", "puntos8": "brote",
              "puntos12": "brote", "puntos4": "brote", "cruz": "giro", "cruzGruesa": "giro", "equis": "giro",
              "asterisco": "brote", "romboPixel": "brote", "damero": "brote", "cruzPixel": "brote", "rombos4": "giro",
              "rombos8": "giro", "triangulo": "giro", "cuartos": "rueda", "punto": "salto", "anilloChico": "latido",
              "romboChico": "giro"}
PALETAS = ("mocha", "fluo", "apagado")
MEZCLAS = ("luz", "maximo", "suma", "opaca")


@dataclass(frozen=True)
class Parametro:
    clave: str
    grupo: str
    nombre: str
    base: object
    #: rango: (mínimo, máximo, paso); opciones: los valores
    minimo: float = 0
    maximo: float = 0
    paso: float = 0
    opciones: tuple[str, ...] = ()
    ayuda: str = ""


def _r(clave, grupo, nombre, base, minimo, maximo, paso, ayuda=""):
    return Parametro(clave, grupo, nombre, base, minimo, maximo, paso, (), ayuda)


def _o(clave, grupo, nombre, base, opciones, ayuda=""):
    return Parametro(clave, grupo, nombre, base, opciones=tuple(opciones), ayuda=ayuda)


CATALOGO: tuple[Parametro, ...] = (
    # el campo: las tintas
    _o("paleta", "campo · tinta", "paleta", "fluo", PALETAS),
    _r("tintas", "campo · tinta", "tintas", 7, 2, 7, 1),
    _o("mezcla", "campo · tinta", "mezcla", "maximo", MEZCLAS, "cómo se juntan las tintas: luz, máximo, suma u opaca"),
    _o("fondo", "campo · tinta", "fondo", "crust", ("base", "barra", "crust", "ninguno"), "detrás de la banda; de fondo, ninguno"),
    _r("intensidad", "campo · tinta", "intensidad", 1, .05, 1, .01),
    _r("desregistro", "campo · tinta", "desregistro", 0, 0, 6, .1, "px que se corre cada tinta"),
    _r("grano", "campo · tinta", "grano", .1, 0, .9, .01),
    _r("papel", "campo · tinta", "papel", .27, 0, 1, .01),
    # el campo: la forma
    _r("celda", "campo · forma", "celda chica", 8, 8, 40, 1, "px"),
    _r("niveles", "campo · forma", "escalas", 4, 0, 4, 1, "sobre la más chica"),
    _r("capas", "campo · forma", "piezas por glifo", 3, 1, 3, 1),
    _r("variedad", "campo · forma", "tintas por glifo", 0, 0, 1, .01),
    _r("huecos", "campo · forma", "huecos", 0, 0, .9, .01),
    _r("semilla", "campo · forma", "semilla", 11, 0, 996, 1),
    # el campo: cómo se mueve
    _r("onda", "campo · movimiento", "onda", 1, 0, 1, .01, "cuánto se desfasan las zonas"),
    _r("ruido", "campo · movimiento", "tamaño de zonas", .61, .15, 1.5, .01),
    _r("ciclo", "campo · movimiento", "ciclo", 18.5, 2, 30, .5, "segundos"),
    _o("transicion", "campo · movimiento", "cambio de escala", "absorber", ("absorber", "tamano", "directa"),
       "absorber: los hijos se recogen al centro y el padre brota; tamano: encogen en su lugar; directa: de golpe"),
    _r("corte", "campo · movimiento", "duración del cambio", .35, .05, 1, .01),
    # la vida: los gestos
    _r("actividad", "vida", "se mueven", .3, 0, 1, .01, "la fracción de glifos que hace su gesto en cada vuelta"),
    _r("periodo", "vida", "cada", 4, 1, 12, .5, "segundos"),
    _r("duracion", "vida", "el gesto dura", .9, .3, 2.5, .1, "segundos"),
    _r("saltos", "vida", "saltos de tinta", .2, 0, 1, .01),
    _r("rueda", "vida", "giro continuo", .25, 0, 1, .01, "vueltas por segundo"),
    # el gesto de cada pieza
    *(_o(f"gesto_{p}", "gestos", NOMBRE_PIEZA[p], GESTO_BASE[p], GESTOS) for p in PIEZAS),
    # el glifo de cada hilo
    _o("hilo_paleta", "hilo", "paleta", "mocha", PALETAS),
    _r("hilo_capas", "hilo", "piezas", 3, 1, 3, 1),
    _r("hilo_variedad", "hilo", "tintas por glifo", 1, 0, 1, .01),
    _o("hilo_mezcla", "hilo", "mezcla", "luz", MEZCLAS),
    _r("hilo_desregistro", "hilo", "desregistro", 0, 0, 10, .1, "% del tamaño"),
    _r("hilo_grano", "hilo", "grano", 0, 0, .6, .01),
    _r("hilo_tam", "hilo", "tamaño en la barra", 15, 12, 28, 1, "px"),
    _r("sello_tam", "hilo", "tamaño del sello", 48, 24, 120, 1, "px, en la ficha del hilo"),
    # sus estados
    _o("trabajando", "estados", "trabajando", "giro", ("giro", "armado"), "giro: gira de a 45°; armado: se arma pieza a pieza"),
    _o("espera", "estados", "te espera", "cadena", ("cadena", "parpadeo"), "cadena: un anillo de puntos que se llena"),
    _r("tenue", "estados", "visto (brillo)", .3, .1, .7, .01),
    _r("ritmo", "estados", "ritmo", 1.5, .5, 3, .1, "segundos"),
)
POR_CLAVE = {p.clave: p for p in CATALOGO}
BASE = {p.clave: p.base for p in CATALOGO}


def validar(estilo: str, cuerpo: dict) -> dict:
    """`[glifos.<estilo>]`: cada valor normalizado (un número, dentro de su rango; una opción, de las suyas)."""
    from telar.config import ErrorDeConfig

    if not CLAVE.match(estilo):
        raise ErrorDeConfig(f"glifos.{estilo}: el nombre va en minúsculas, con letras, números y guiones")
    if not isinstance(cuerpo, dict):
        raise ErrorDeConfig(f"glifos.{estilo}: tiene que ser una tabla")
    salida = {}
    for k, v in cuerpo.items():
        p = POR_CLAVE.get(k)
        if p is None:
            raise ErrorDeConfig(f"glifos.{estilo}.{k}: no es un parámetro de los glifos")
        if p.opciones:
            v = str(v).strip()
            if v not in p.opciones:
                raise ErrorDeConfig(f"glifos.{estilo}.{k}: {' · '.join(p.opciones)}; llegó {v!r}")
            salida[k] = v
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            try:
                v = float(str(v).replace(",", "."))
            except ValueError:
                raise ErrorDeConfig(f"glifos.{estilo}.{k}: se esperaba un número, llegó {v!r}") from None
        if not p.minimo <= v <= p.maximo:
            raise ErrorDeConfig(f"glifos.{estilo}.{k}: de {p.minimo:g} a {p.maximo:g}; llegó {v:g}")
        salida[k] = int(v) if p.paso >= 1 else round(float(v), 4)
    return salida


def todos(config) -> dict[str, dict]:
    """Cada estilo con todos sus valores: «base» (el de fábrica, cambiado si la configuración lo cambia) y los de
    `[glifos.<n>]`, que toman de «base» lo que no dicen."""
    propios = getattr(config, "glifos", {}) or {}
    base = {**BASE, **propios.get("base", {})}
    salida = {"base": base}
    for k, v in propios.items():
        if k != "base":
            salida[k] = {**base, **v}
    return salida


def catalogo() -> list[dict]:
    return [{"clave": p.clave, "grupo": p.grupo, "nombre": p.nombre, "base": p.base, "ayuda": p.ayuda,
             **({"opciones": list(p.opciones)} if p.opciones else {"minimo": p.minimo, "maximo": p.maximo, "paso": p.paso})}
            for p in CATALOGO]


def guardar(ruta: Path | None, estilo: str, valores: dict) -> dict:
    """Escribe `[glifos.<estilo>]` con los valores que difieren de los de fábrica (reemplaza la tabla entera): lo que
    no dice, lo toma de «base»."""
    from telar import config as mod_config

    limpio = {k: v for k, v in validar(estilo, valores).items() if v != BASE.get(k)}
    if estilo != "base" and not limpio:
        limpio = {"semilla": BASE["semilla"]}  # una tabla vacía no se escribe: que el estilo exista igual
    destino = Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()
    borrar(destino, estilo)
    for k, v in limpio.items():
        mod_config.escribir_clave(f"glifos.{estilo}", k, v, destino)
    return limpio


def borrar(ruta: Path | None, estilo: str) -> bool:
    """Quita `[glifos.<estilo>]`: uno propio desaparece; «base» vuelve a ser el de fábrica. True si estaba."""
    import tomllib

    from telar import config as mod_config
    from telar.unirse import quitar_tabla

    destino = Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()
    if not CLAVE.match(estilo) or not destino.exists():
        return False
    texto = destino.read_text(encoding="utf-8")
    nuevo = quitar_tabla(texto, f"glifos.{estilo}")
    if nuevo == texto:
        return False
    mod_config.desde_dict(tomllib.loads(nuevo), origen=destino)  # que se siga leyendo
    tmp = destino.with_name(destino.name + ".nuevo")
    tmp.write_text(nuevo, encoding="utf-8")
    tmp.replace(destino)
    return True
