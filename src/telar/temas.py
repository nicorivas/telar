"""Los colores principales de un tema, cambiados en esta máquina, y los temas propios (`[temas.<tema>]`,
docs/configuracion.md).

    [temas.brasa]
    azul = "#7dae9a"          # el acento: los enlaces, la fila activa, lo que trabaja
    bg = "#1c1510"            # el fondo

    [temas.noche-azul]        # uno propio: parte de brasa, y cambia lo que dice
    base = "brasa"
    bg = "#141820"

    from telar import temas
    temas.para_la_pagina(config)          # {"brasa": {"azul": "#7dae9a", …}, "noche-azul": {"base": "brasa", …}}
    temas.ajustar(ruta, "brasa", {"azul": "#7dae9a", "violeta": None})   # None vuelve al de fábrica
    temas.crear(ruta, "noche-azul", "brasa")   # uno propio, con lo de brasa
    temas.borrar(ruta, "brasa")           # todo de fábrica; de uno propio, el tema entero

Los temas de fábrica son los de la página (telar.modos.TEMAS); sus colores, en pagina/media/css/tokens.css y
temas.css. Un color es uno de sus primitivos, por el mismo nombre (`--azul` es `azul`): los fondos y las líneas
(`FONDOS`: el fondo, las barras, las líneas, la selección) y las tintas de letra (`TINTAS`: el texto, lo tenue y las
siete con significado). Cambiarlo lo cambia en todo lo que lo usa (el acento, los enlaces, la terminal), solo con ese
tema puesto; lo que sale de ellos (el hover, la fila activa, la superficie) se deriva solo. Lo que no se dice queda de
fábrica.

Un tema propio tiene un nombre que no es de fábrica y un `base`, el de fábrica del que parte: es ese tema entero (sus
colores y sus tokens de temas.css) con lo que diga encima, y su «de fábrica» es el de su base. Se elige donde se elige
un tema (`[modos.<m>] tema`, `[mundos.<n>] tema`); mientras uno lo use, no se borra.

Un color que se lee mal (bajo 4,5:1) no se niega: la página lo avisa (pagina/src/componentes/temas.ts, `avisos`), y
⚙ temas es donde se elige.

**En la raíz, para todas las máquinas.** `[temas]` va también en `<raiz>/.telar/temas.toml` (ARCHIVO), con la misma forma, y
se lee con la configuración: de fábrica < ese archivo < `[temas.<tema>]` de la configuración de la máquina, que pisa
color por color, solo ahí (`juntar`; de dónde sale cada cosa, `donde`). ⚙ temas escribe ahí (`cambiar`, `nuevo`,
`quitar`): un color que se cambia pasa a la raíz y sale de la configuración de la máquina, si estaba, para que se vea; uno
que vuelve al de fábrica sale de los dos. Lo escrito se commitea solo, ese archivo y nada más, y se sube (`subir_luego`,
`subir`): las otras máquinas lo leen cuando integren lo de arriba (su próximo `telar commit`, o /sincronizar). Sin `raiz` en la
configuración no hay raíz: todo queda en la de la máquina, como antes. `migrar` pasa los `[temas.*]` de la configuración
de una máquina a la raíz, con respaldo, sin cambiar lo que se ve (`telar temas migrar`).

    temas.cambiar(config, "brasa", {"azul": "#7dae9a"})   # a la raíz
    temas.migrar(config, ver=True)                        # qué pasaría
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

__all__ = ["TINTAS", "FONDOS", "COLORES", "NOMBRE", "ARCHIVO", "EnUso", "normalizar", "validar", "propios", "que_hay",
           "en", "faltan", "para_la_pagina", "para_la_configuracion", "usos", "crear", "ajustar", "borrar",
           "archivo_de", "nombre_raiz", "leer_raiz", "juntar", "donde", "cambiar", "nuevo", "quitar", "migrar", "subir", "subir_luego"]

#: las tintas de letra de un tema que se pueden cambiar, por el nombre de su primitivo y en el orden en que se ven en
#: ⚙ temas (la que más se ve primero): el texto, lo tenue, los títulos, el acento, lo de un agente, el éxito, lo remoto,
#: el magenta y el peligro. Las mismas de EDITABLES en pagina/src/componentes/temas.ts
TINTAS = ("fg", "dim", "amarillo", "azul", "violeta", "verde", "cian", "magenta", "rojo")
#: los fondos y las líneas, lo mínimo que cambia la cara de un tema: el fondo (la página, la terminal), las barras
#: (las de arriba, las ventanas, el menú), las líneas (las que parten filas y secciones) y la selección (lo elegido en
#: un menú o una lista). Los mismos de FONDOS en pagina/src/componentes/temas.ts
FONDOS = ("bg", "bg-barra", "linea", "sel")
#: todo lo que un tema puede cambiar, en el orden de ⚙ temas
COLORES = FONDOS + TINTAS
#: el nombre de un tema propio: minúsculas, números y guiones, hasta 24 (va sin comillas en `[temas.<nombre>]`)
NOMBRE = re.compile(r"[a-z][a-z0-9-]{0,23}")

_COLOR = re.compile(r"#(?:[0-9a-f]{3}|[0-9a-f]{6})")

#: los temas de la raíz, relativo a ella: valen en todas las máquinas que comparten esa raíz por git
ARCHIVO = Path(".telar") / "temas.toml"
#: la cabeza de ese archivo, cuando ⚙ temas lo crea
CABEZA = """# Los temas de telar que valen en todas las máquinas de esta raíz: los colores cambiados de un tema y los temas
# propios (docs/configuracion.md, «[temas]»). Los escribe ⚙ temas, que lo commitea y lo sube solo.
# Lo que diga [temas.<tema>] en la configuración de una máquina pisa esto, color por color, solo en esa máquina.
"""


class EnUso(Exception):
    """Un tema propio que un modo o un mundo tiene puesto: no se borra (se le cambia antes)."""


def normalizar(donde: str, valor) -> str:
    """Un color como se guarda: `#rrggbb`, en minúsculas (`#abc` es `#aabbcc`). ErrorDeConfig si no es uno."""
    from telar.config import ErrorDeConfig

    texto = valor.strip().lower() if isinstance(valor, str) else ""
    if not _COLOR.fullmatch(texto):
        raise ErrorDeConfig(f"{donde}: un color como #rrggbb; llegó {valor!r}")
    return texto if len(texto) == 7 else "#" + "".join(c * 2 for c in texto[1:])


def _nombre_valido(nombre: str) -> str:
    """Por qué un nombre no sirve para un tema propio ("" si sirve)."""
    from telar.modos import TEMAS

    if nombre in TEMAS:
        return f"«{nombre}» es un tema de fábrica: uno propio se llama de otra forma"
    if not NOMBRE.fullmatch(nombre):
        return (f"«{nombre}»: un tema propio se llama en minúsculas, con letras, números y guiones (hasta 24, "
                "empezando por una letra)")
    return ""


def validar(tabla: dict) -> dict[str, dict[str, str]]:
    """`[temas]` leído: tema → {color: #rrggbb} (y `base`, de uno propio). ErrorDeConfig si un tema, un color o una base
    no sirven."""
    from telar.config import ErrorDeConfig
    from telar.modos import TEMAS

    salida: dict[str, dict[str, str]] = {}
    for tema, cuerpo in tabla.items():
        if not isinstance(cuerpo, dict):
            raise ErrorDeConfig(f"temas.{tema}: se esperaba una tabla [temas.{tema}]")
        propio = tema not in TEMAS
        if propio:
            if not NOMBRE.fullmatch(tema):
                raise ErrorDeConfig(f"temas.{tema}: {_nombre_valido(tema)}; los de fábrica: {', '.join(TEMAS)}")
            base = cuerpo.get("base")
            if base not in TEMAS:
                raise ErrorDeConfig(f"temas.{tema}.base: un tema propio dice de cuál de fábrica parte, uno de "
                                    f"{', '.join(TEMAS)}; llegó {base!r}")
        elif "base" in cuerpo:
            raise ErrorDeConfig(f"temas.{tema}.base: solo un tema propio parte de otro, y «{tema}» es de fábrica")
        sobra = sorted(set(cuerpo) - set(COLORES) - {"base"})
        if sobra:
            raise ErrorDeConfig(f"temas.{tema}.{sobra[0]}: no existe (base, {', '.join(COLORES)})")
        colores = {c: normalizar(f"temas.{tema}.{c}", cuerpo[c]) for c in COLORES if c in cuerpo}
        salida[tema] = {"base": cuerpo["base"], **colores} if propio else colores
    return salida


def propios(config) -> dict[str, str]:
    """Los temas propios de la configuración, en su orden: nombre → el de fábrica del que parte."""
    from telar.modos import TEMAS

    return {t: v["base"] for t, v in (getattr(config, "temas", {}) or {}).items() if t not in TEMAS and v.get("base")}


def que_hay(config) -> tuple[str, ...]:
    """Los temas que se pueden elegir: los de fábrica, en su orden, y los propios."""
    from telar.modos import TEMAS

    return (*TEMAS, *propios(config))


def en(destino) -> tuple[str, ...]:
    """Los temas que se pueden elegir según ese archivo, sin leer la configuración entera (para revisar lo que se va a
    escribir): los de fábrica y los propios bien declarados, los de la raíz (si ese archivo dice `raiz`) y los suyos."""
    from telar.modos import TEMAS

    destino = _destino(destino)
    leidos = juntar(_de_raiz_para(destino), _leidos(destino))
    return (*TEMAS, *(t for t, v in leidos.items()
                      if t not in TEMAS and isinstance(v, dict) and NOMBRE.fullmatch(t) and v.get("base") in TEMAS))


def faltan(destino) -> tuple[str, ...]:
    """Los temas propios que nombran los modos y los mundos de ese archivo y no hay (ni en él ni en la raíz)."""
    import tomllib

    from telar import config as mod_config

    destino = _destino(destino)
    if not destino.exists():
        return ()
    hay = en(destino)
    nombrados = mod_config._temas_nombrados(tomllib.loads(destino.read_text(encoding="utf-8")))
    return tuple(t for t in dict.fromkeys(nombrados) if t not in hay and NOMBRE.fullmatch(t))


# ── la raíz: <raiz>/.telar/temas.toml ────────────────────────────────────────────────────────────────────────────


def archivo_de(datos: dict, origen=None, *, nombre: Path = ARCHIVO) -> Path | None:
    """El archivo de los temas de la raíz según esa configuración ya parseada: `<raiz>/.telar/temas.toml`, con la raíz de
    `TELAR_RAIZ` o de `raiz`. None si no dice raíz (todo queda en la máquina) o si `origen` es ese mismo
    archivo (se está revisando lo que se le va a escribir). `nombre`, otro archivo relativo a la raíz (el de los
    horarios de los mundos, telar.mundos_raiz)."""
    import os

    valor = os.environ.get("TELAR_RAIZ") or datos.get("raiz")
    if not isinstance(valor, str) or not valor.strip():
        return None
    archivo = Path(valor).expanduser().absolute() / nombre
    if origen is not None:
        try:
            if Path(origen).expanduser().resolve() == archivo.resolve():
                return None
        except OSError:
            pass
    return archivo


def nombre_raiz(archivo) -> str:
    """Cómo decir la raíz en palabras: el nombre de su carpeta, sacado de uno de sus archivos (`<raiz>/.telar/temas.toml`
    → el nombre de `<raiz>`), para que cada persona vea la suya; «la raíz» si no hay archivo."""
    if not archivo:
        return "la raíz"
    carpeta = Path(archivo).parent
    if carpeta.name == ".telar":
        carpeta = carpeta.parent
    return carpeta.name or "la raíz"


def leer_raiz(archivo: Path | None) -> tuple[dict, str]:
    """Los temas de la raíz, revisados como `[temas]` (`validar`), y "" ; o {} y por qué no se pudo leer (un TOML roto, un
    choque de git a medio resolver, un color que no sirve): telar sigue sin ellos, y doctor lo dice."""
    import tomllib

    from telar.config import ErrorDeConfig

    if archivo is None or not archivo.exists():
        return {}, ""
    try:
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        return {}, f"{archivo}: no se lee ({e})"
    sobra = sorted(set(datos) - {"temas"})
    if sobra:
        return {}, f"{archivo}: solo lleva tablas [temas.<tema>]; sobra «{sobra[0]}»"
    tabla = datos.get("temas", {})
    if not isinstance(tabla, dict):
        return {}, f"{archivo}: se esperaban tablas [temas.<tema>]"
    try:
        return validar(tabla), ""
    except ErrorDeConfig as e:
        return {}, f"{archivo}: {e}"


def juntar(de_raiz: dict, de_aqui: dict) -> dict:
    """Los temas de la raíz con los de la máquina encima, color por color (y la `base`): primero los de la raíz, en su orden, y
    después los que solo están en la máquina. Lo que no es una tabla pasa tal cual (para que `validar` lo diga)."""
    salida: dict = {}
    for tema in (*de_raiz, *(t for t in de_aqui if t not in de_raiz)):
        a, b = de_raiz.get(tema), de_aqui.get(tema)
        if tema not in de_aqui:
            salida[tema] = dict(a) if isinstance(a, dict) else a
        elif isinstance(a, dict) and isinstance(b, dict):
            salida[tema] = {**a, **b}
        else:
            salida[tema] = b
    return salida


def donde(de_raiz: dict, de_aqui: dict) -> dict[str, dict[str, tuple[str, ...]]]:
    """De dónde sale cada cosa de un tema: tema → {"raiz": sus claves en la raíz, "maquina": las de la máquina} (los colores
    y `base`; en las dos, gana la de la máquina)."""
    salida = {}
    for tema in (*de_raiz, *(t for t in de_aqui if t not in de_raiz)):
        a, b = de_raiz.get(tema), de_aqui.get(tema)
        salida[tema] = {"raiz": tuple(a) if isinstance(a, dict) else (), "maquina": tuple(b) if isinstance(b, dict) else ()}
    return salida


def _datos(destino: Path) -> dict:
    import tomllib

    try:
        return tomllib.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _de_raiz_para(destino: Path) -> dict:
    """Los temas de la raíz de la configuración `destino` (de su `raiz`); {} si no dice raíz o no se leen."""
    return leer_raiz(archivo_de(_datos(destino), destino))[0]


def para_la_pagina(config) -> dict[str, dict[str, str]]:
    """Los colores propios de cada tema, como los dice `telar config --json`: solo los temas que cambian algo (los
    propios siempre, con su `base`)."""
    return {t: dict(v) for t, v in (getattr(config, "temas", {}) or {}).items() if v}


def para_la_configuracion(config) -> dict:
    """Lo que muestra ⚙ temas (`GET /temas`): cada tema que se puede elegir (los de fábrica en su orden y después los
    propios), con sus colores propios (`propios`, vacío si es el de fábrica), su `base` ("" si es de fábrica) y si es
    de fábrica; y los colores que se pueden cambiar (`fondos` y `tintas`, en el orden en que se ven)."""
    from telar.modos import TEMAS

    leidos = getattr(config, "temas", {}) or {}
    bases = propios(config)
    de_donde = getattr(config, "temas_donde", {}) or {}
    archivo_raiz = getattr(config, "temas_archivo", None)

    def uno(t: str) -> dict:
        colores = {k: v for k, v in leidos.get(t, {}).items() if k != "base"}
        d = de_donde.get(t, {})
        aqui = [k for k in COLORES if k in d.get("maquina", ())]
        en_raiz = [k for k in COLORES if k in d.get("raiz", ()) and k not in aqui]
        hay_raiz, hay_aqui = bool(d.get("raiz")), bool(d.get("maquina"))
        vive = "mixto" if hay_raiz and hay_aqui and aqui else "raiz" if hay_raiz else "maquina" if hay_aqui else ""
        return {"clave": t, "propios": colores, "base": bases.get(t, ""), "de_fabrica": t in TEMAS,
                "vive": vive, "en_raiz": en_raiz, "en_maquina": aqui}

    return {"temas": [uno(t) for t in que_hay(config)], "tintas": list(TINTAS), "fondos": list(FONDOS),
            "raiz": str(archivo_raiz or ""), "maquina": str(_destino(getattr(config, "origen", None))),
            "error_raiz": getattr(config, "temas_error", "") or ""}


def _destino(ruta) -> Path:
    from telar import config as mod_config

    return Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()


def _leidos(destino: Path) -> dict:
    import tomllib

    if not destino.exists():
        return {}
    tabla = tomllib.loads(destino.read_text(encoding="utf-8")).get("temas", {})
    return tabla if isinstance(tabla, dict) else {}


def usos(ruta, tema: str) -> list[str]:
    """Quién tiene puesto ese tema en el archivo: «el mundo «personal»», «el modo «lectura»»."""
    import tomllib

    destino = _destino(ruta)
    if not destino.exists():
        return []
    datos = tomllib.loads(destino.read_text(encoding="utf-8"))
    salida = []
    for clave, de in (("mundos", "el mundo"), ("modos", "el modo")):
        tabla = datos.get(clave, {})
        for nombre, cuerpo in (tabla.items() if isinstance(tabla, dict) else ()):
            if isinstance(cuerpo, dict) and cuerpo.get("tema") == tema:
                salida.append(f"{de} «{nombre}» ([{clave}.{nombre}] tema)")
    return salida


def crear(ruta, nombre: str, base: str) -> dict:
    """Agrega `[temas.<nombre>]`, un tema propio que parte de `base`: con `base = "<tema de fábrica>"` y, si parte de
    otro propio, con su base y sus colores (una copia). Devuelve lo escrito. FileExistsError si ya hay uno así;
    ErrorDeConfig si el nombre no sirve (uno de fábrica, otra forma) o la base no existe."""
    from telar import config as mod_config
    from telar.modos import TEMAS

    nombre = str(nombre or "").strip()
    problema = _nombre_valido(nombre)
    if problema:
        raise mod_config.ErrorDeConfig(f"temas.{nombre}: {problema}")
    destino = _destino(ruta)
    leidos = juntar(_de_raiz_para(destino), _leidos(destino))
    if isinstance(leidos.get(nombre), dict):
        raise FileExistsError(nombre)
    colores: dict = {}
    if base not in TEMAS:
        de = leidos.get(base) if base else None
        if not isinstance(de, dict) or de.get("base") not in TEMAS:
            raise mod_config.ErrorDeConfig(f"temas.{nombre}.base: el tema del que parte, uno de "
                                           f"{', '.join(en(destino))}; llegó {base!r}")
        colores = {c: normalizar(f"temas.{base}.{c}", de[c]) for c in COLORES if c in de}
        base = de["base"]
    mod_config.escribir_clave(f"temas.{nombre}", "base", base, destino)
    for c, v in colores.items():
        mod_config.escribir_clave(f"temas.{nombre}", c, v, destino)
    return {"base": base, **colores}


def ajustar(ruta, tema: str, valores: dict) -> dict:
    """Cambia esos colores de `[temas.<tema>]`, línea por línea (lo demás del archivo queda como estaba); None o vacío
    vuelve al de fábrica (al de su base, si es propio: quita la línea) y, si la tabla de uno de fábrica queda vacía, se
    quita. La base de uno propio no se cambia aquí. Antes de escribir se revisa todo: si algo no sirve, nada se escribe.
    Devuelve lo escrito (None: lo quitado). KeyError si el tema no existe; ErrorDeConfig si un color no sirve."""
    from telar import config as mod_config
    from telar.modos import TEMAS

    destino = _destino(ruta)
    if tema not in en(destino):
        raise KeyError(tema)
    limpio = _limpiar(tema, valores)
    for t in COLORES:
        if t in limpio:
            mod_config.escribir_clave(f"temas.{tema}", t, limpio[t], destino)
    quedo = _leidos(destino).get(tema)
    if tema in TEMAS and isinstance(quedo, dict) and not quedo:
        borrar(destino, tema)
    return limpio


def _limpiar(tema: str, valores: dict) -> dict:
    """Los colores pedidos como se escriben (`#rrggbb`; None, de fábrica). ErrorDeConfig si uno no existe o no sirve."""
    from telar import config as mod_config

    sobra = sorted(set(valores) - set(COLORES))
    if sobra:
        raise mod_config.ErrorDeConfig(f"temas.{tema}.{sobra[0]}: no existe ({', '.join(COLORES)})")
    return {t: None if v is None or (isinstance(v, str) and not v.strip()) else normalizar(f"temas.{tema}.{t}", v)
            for t, v in valores.items()}


def borrar(ruta, tema: str, *, revisar_usos: bool = True) -> bool:
    """Quita `[temas.<tema>]`: uno de fábrica vuelve a ser el de fábrica; uno propio deja de existir. True si estaba.
    EnUso si es uno propio que un modo o un mundo tiene puesto (se le cambia antes); sin `revisar_usos`, se quita igual
    (el tema sigue en el otro archivo)."""
    import os
    import tomllib

    from telar import config as mod_config
    from telar.modos import TEMAS
    from telar.unirse import quitar_tabla

    destino = _destino(ruta)
    if not isinstance(_leidos(destino).get(tema), dict):
        return False
    if tema not in TEMAS and revisar_usos:
        quien = usos(destino, tema)
        if quien:
            raise EnUso(f"«{tema}» lo tiene puesto {', '.join(quien)}: cámbiale el tema antes de borrarlo")
    texto = destino.read_text(encoding="utf-8")
    nuevo = quitar_tabla(texto, f"temas.{tema}")
    if nuevo == texto:
        return False
    mod_config.revisar_antes_de_escribir(texto, nuevo, destino)  # que se siga leyendo
    temporal = destino.with_name(destino.name + ".nuevo")
    temporal.write_text(nuevo, encoding="utf-8")
    os.chmod(temporal, destino.stat().st_mode & 0o777)
    os.replace(temporal, destino)
    return True


# ── lo que escribe ⚙ temas: a la raíz (y fuera de la máquina lo que lo taparía) ──────────────────────────────────────


def _maquina(config) -> Path:
    return _destino(getattr(config, "origen", None))


def _archivo_raiz(config) -> Path | None:
    """El archivo de la raíz donde escribir, o None si no hay (sin `raiz`: todo en la máquina). ErrorDeConfig si está pero no
    se lee: no se escribe encima de un archivo roto (un choque de git a medio resolver)."""
    from telar.config import ErrorDeConfig

    archivo_raiz = getattr(config, "temas_archivo", None)
    if archivo_raiz is not None and getattr(config, "temas_error", ""):
        raise ErrorDeConfig(f"no escribí nada: {config.temas_error}")
    return archivo_raiz


def _preparar(archivo_raiz: Path) -> None:
    """Que el archivo de la raíz exista, con su cabeza que dice qué es."""
    if not archivo_raiz.exists():
        archivo_raiz.parent.mkdir(parents=True, exist_ok=True)
        archivo_raiz.write_text(CABEZA, encoding="utf-8")


def _sacar_de_la_maquina(maquina: Path, archivo_raiz: Path, tema: str, claves) -> None:
    """Saca de `[temas.<tema>]` de la máquina esas claves (lo que taparía lo de la raíz) y, si la tabla queda vacía, o solo
    con la misma `base` que ya dice la raíz, la tabla."""
    from telar import config as mod_config

    aqui = _leidos(maquina).get(tema)
    if not isinstance(aqui, dict):
        return
    for k in claves:
        if k in aqui:
            mod_config.escribir_clave(f"temas.{tema}", k, None, maquina)
    quedo = _leidos(maquina).get(tema)
    alla = _leidos(archivo_raiz).get(tema)
    if isinstance(quedo, dict) and (not quedo or (set(quedo) == {"base"} and isinstance(alla, dict)
                                                  and alla.get("base") == quedo["base"])):
        borrar(maquina, tema, revisar_usos=False)


def cambiar(config, tema: str, valores: dict) -> dict:
    """Lo que hace ⚙ temas con unos colores: los escribe en la raíz (si es uno propio que no está allá, con su `base`) y los
    saca de la configuración de la máquina, si estaban, para que se vean; None vuelve al de fábrica en los dos. Sin raíz,
    en la de la máquina (`ajustar`). Devuelve lo escrito. KeyError si el tema no existe; ErrorDeConfig si un color no
    sirve (y nada se escribe)."""
    from telar import config as mod_config
    from telar.modos import TEMAS

    archivo_raiz, maquina = _archivo_raiz(config), _maquina(config)
    if archivo_raiz is None:
        return ajustar(maquina, tema, valores)
    if tema not in que_hay(config):
        raise KeyError(tema)
    limpio = _limpiar(tema, valores)
    pone = any(v is not None for v in limpio.values())
    propio = tema not in TEMAS
    if pone:
        _preparar(archivo_raiz)
        if propio and not isinstance(_leidos(archivo_raiz).get(tema), dict):
            mod_config.escribir_clave(f"temas.{tema}", "base", config.temas[tema]["base"], archivo_raiz)
    if pone or isinstance(_leidos(archivo_raiz).get(tema), dict):
        ajustar(archivo_raiz, tema, limpio)
    _sacar_de_la_maquina(maquina, archivo_raiz, tema, limpio)
    return limpio


def nuevo(config, nombre: str, base: str) -> dict:
    """Un tema propio nuevo, en la raíz (`crear`, con lo que dice la configuración entera: la base puede ser uno propio de la
    máquina). Sin raíz, en la de la máquina. FileExistsError si ya hay uno así; ErrorDeConfig si el nombre o la base no
    sirven."""
    from telar import config as mod_config
    from telar.modos import TEMAS

    archivo_raiz = _archivo_raiz(config)
    if archivo_raiz is None:
        return crear(_maquina(config), nombre, base)
    nombre = str(nombre or "").strip()
    problema = _nombre_valido(nombre)
    if problema:
        raise mod_config.ErrorDeConfig(f"temas.{nombre}: {problema}")
    leidos = getattr(config, "temas", {}) or {}
    if nombre in leidos:
        raise FileExistsError(nombre)
    colores: dict = {}
    if base not in TEMAS:
        de = leidos.get(base) if base else None
        if not isinstance(de, dict) or de.get("base") not in TEMAS:
            raise mod_config.ErrorDeConfig(f"temas.{nombre}.base: el tema del que parte, uno de "
                                           f"{', '.join(que_hay(config))}; llegó {base!r}")
        colores = {c: de[c] for c in COLORES if c in de}
        base = de["base"]
    _preparar(archivo_raiz)
    mod_config.escribir_clave(f"temas.{nombre}", "base", base, archivo_raiz)
    for c, v in colores.items():
        mod_config.escribir_clave(f"temas.{nombre}", c, v, archivo_raiz)
    return {"base": base, **colores}


def quitar(config, tema: str) -> bool:
    """«todo de fábrica» de uno de fábrica, o «borrar tema» de uno propio: la tabla fuera de la máquina y de la raíz. True si
    estaba en alguna. EnUso si es uno propio que un modo o un mundo de esta máquina tiene puesto (los de la otra no se
    ven desde aquí: si uno lo nombraba, allá queda anotado y la página pone el del modo; doctor lo dice)."""
    from telar.modos import TEMAS

    archivo_raiz, maquina = _archivo_raiz(config), _maquina(config)
    if archivo_raiz is None:
        return borrar(maquina, tema)
    en_raiz = isinstance(_leidos(archivo_raiz).get(tema), dict)
    aqui = isinstance(_leidos(maquina).get(tema), dict)
    if not (en_raiz or aqui):
        return False
    if tema not in TEMAS:
        quien = usos(maquina, tema)
        if quien:
            raise EnUso(f"«{tema}» lo tiene puesto {', '.join(quien)}: cámbiale el tema antes de borrarlo")
    # la máquina primero: mientras, el tema sigue en la raíz y lo que ella diga se sigue leyendo
    if aqui:
        borrar(maquina, tema, revisar_usos=False)
    if en_raiz:
        borrar(archivo_raiz, tema, revisar_usos=False)
    return True


# ── la migración: los [temas.*] de la configuración de una máquina, a la raíz ────────────────────────────────────────


def migrar(config, *, ver: bool = False, ahora=None) -> dict:
    """Pasa los `[temas.*]` de la configuración de esta máquina a la raíz sin cambiar lo que se ve. Cada color (y la `base`
    de uno propio): si la raíz no lo dice, pasa; si la raíz dice lo mismo, sale de la máquina; si dice otro, se queda en la
    máquina, que lo sigue pisando (`quedan`, con lo que dice la raíz: nada se pierde). Uno propio que en la raíz parte de otra
    base se queda entero en la máquina. Antes de escribir, un respaldo de la configuración al lado
    (`config.toml.antes-de-temas-en-raiz-AAAAMMDD-HHMMSS`); después, si la configuración no queda viendo los mismos
    temas, lo devuelve todo como estaba y es un error. Con `ver`, solo dice qué haría. ErrorDeConfig si no hay raíz (sin
    `raiz`) o no se lee."""
    import datetime as dt
    import shutil

    from telar import config as mod_config
    from telar.modos import TEMAS

    archivo_raiz = _archivo_raiz(config)
    if archivo_raiz is None:
        raise mod_config.ErrorDeConfig("la configuración no dice `raiz`: no hay raíz adonde llevar los temas")
    maquina = _maquina(config)
    aqui = _leidos(maquina)
    alla = _leidos(archivo_raiz)
    pasan: list[dict] = []
    iguales: list[dict] = []
    quedan: list[dict] = []

    def valor(tema, k, v):
        return v if k == "base" else normalizar(f"temas.{tema}.{k}", v)

    for tema, cuerpo in aqui.items():
        if not isinstance(cuerpo, dict):
            continue
        de_alla = alla.get(tema) if isinstance(alla.get(tema), dict) else {}
        propio = tema not in TEMAS
        if propio and de_alla and cuerpo.get("base") and cuerpo.get("base") != de_alla.get("base"):
            quedan += [{"tema": tema, "clave": k, "aqui": v, "raiz": de_alla.get(k, "")} for k, v in cuerpo.items()]
            continue
        orden = (["base"] if "base" in cuerpo else []) + [k for k in cuerpo if k != "base"]
        for k in orden:
            v = valor(tema, k, cuerpo[k])
            if k not in de_alla:
                pasan.append({"tema": tema, "clave": k, "valor": v})
            elif valor(tema, k, de_alla[k]) == v:
                iguales.append({"tema": tema, "clave": k, "valor": v})
            else:
                quedan.append({"tema": tema, "clave": k, "aqui": v, "raiz": valor(tema, k, de_alla[k])})
    plan = {"raiz": str(archivo_raiz), "maquina": str(maquina), "pasan": pasan, "iguales": iguales, "quedan": quedan,
            "respaldo": "", "escrito": False}
    if ver or not (pasan or iguales):
        return plan

    antes = mod_config.cargar(maquina).temas
    marca = (ahora or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
    respaldo = maquina.with_name(f"{maquina.name}.antes-de-temas-en-raiz-{marca}")
    shutil.copy2(maquina, respaldo)
    plan["respaldo"] = str(respaldo)
    texto_raiz = archivo_raiz.read_text(encoding="utf-8") if archivo_raiz.exists() else None
    try:
        _preparar(archivo_raiz)
        for p in pasan:
            mod_config.escribir_clave(f"temas.{p['tema']}", p["clave"], p["valor"], archivo_raiz)
        por_tema: dict[str, list[str]] = {}
        for p in (*pasan, *iguales):
            por_tema.setdefault(p["tema"], []).append(p["clave"])
        for tema, claves in por_tema.items():
            _sacar_de_la_maquina(maquina, archivo_raiz, tema, claves)
        despues = mod_config.cargar(maquina).temas
        if despues != antes:
            raise mod_config.ErrorDeConfig(f"la configuración no quedó viendo los mismos temas ({antes} → {despues})")
    except Exception:
        shutil.copy2(respaldo, maquina)
        if texto_raiz is None:
            archivo_raiz.unlink(missing_ok=True)
        else:
            archivo_raiz.write_text(texto_raiz, encoding="utf-8")
        raise
    plan["escrito"] = True
    return plan


# ── que llegue a las otras máquinas: commitear ese archivo, solo ese, y subirlo ──────────────────────────────────

#: cuánto se espera después de la última escritura de ⚙ temas para commitear: varios clics seguidos en la paleta son un
#: solo commit
ESPERA = 20.0
#: el mensaje del commit
MENSAJE = "temas: lo cambiado en ⚙ temas ({maquina})"

#: el commit que espera, por archivo de la raíz (un threading.Timer), y su candado
_pendientes: dict = {}
_candado = threading.Lock()
#: si ya está anotado commitear lo pendiente al salir
_al_salir = False


def subir(archivo_raiz: Path, *, estado: Path | None = None, empujar: bool = True, mensaje: str = ""):
    """Commitea `archivo_raiz` (solo ese archivo: nunca otro, aunque el árbol tenga cambios ajenos) y, con `empujar`, lo sube como
    `telar commit` (trae lo de arriba y rebasa encima; si choca, el commit queda local y lo dice). Devuelve el
    telar.git.Resultado, o None si el archivo no está en un repositorio git. Con `estado`, queda en su commits.log."""
    import socket

    from telar import git

    repo = git.repositorio(archivo_raiz)
    if repo is None:
        return None
    mensaje = mensaje or MENSAJE.format(maquina=socket.gethostname().split(".")[0])
    res = git.commitear([archivo_raiz], mensaje, repo=repo)
    if empujar and res.estado in ("commiteado", "nada"):
        res = git.subir(res)
    if estado is not None:
        git.anotar(Path(estado), res, mensaje)
    return res


def subir_luego(config, *, espera: float = ESPERA, archivo: Path | None = None, mensaje: str = "") -> None:
    """Después de una escritura de ⚙ temas: `subir` el archivo de la raíz en `espera` segundos, en otro hilo (lo que vuelve a
    escribirse antes, lo corre). Si el proceso termina antes, se commitea al salir, sin subir (lo sube el próximo `telar
    commit` de esa máquina). `archivo` y `mensaje`, otro archivo de la raíz y su mensaje (el de los horarios de los mundos,
    telar.mundos_raiz); sin ellos, el de los temas."""
    import atexit

    archivo_raiz = archivo if archivo is not None else getattr(config, "temas_archivo", None)
    if archivo_raiz is None:
        return
    estado = getattr(config, "estado", None)
    with _candado:
        viejo = _pendientes.pop(archivo_raiz, None)
        if viejo is not None:
            viejo.cancel()

        def correr():
            with _candado:
                if _pendientes.get(archivo_raiz) is not reloj:
                    return
                _pendientes.pop(archivo_raiz, None)
            try:
                subir(archivo_raiz, estado=estado, mensaje=mensaje)
            except Exception:  # noqa: BLE001 - un commit que falla no tumba la API: queda en commits.log o sin commitear
                pass

        reloj = threading.Timer(espera, correr)
        reloj.daemon = True
        reloj.mensaje = mensaje
        _pendientes[archivo_raiz] = reloj
        reloj.start()
    global _al_salir
    if not _al_salir:
        atexit.register(_commitear_lo_pendiente)
        _al_salir = True


def _commitear_lo_pendiente() -> None:
    with _candado:
        pendientes = list(_pendientes.items())
        _pendientes.clear()
    for archivo_raiz, reloj in pendientes:
        reloj.cancel()
        try:
            subir(archivo_raiz, empujar=False, mensaje=getattr(reloj, "mensaje", ""))
        except Exception:  # noqa: BLE001
            pass


def atrasado(archivo_raiz: Path) -> str:
    """Si el archivo de la raíz de esta máquina no es el último: trae lo de arriba (`git fetch`) y compara su versión de
    arriba con la de aquí. Lo que dice por qué no está al día ("" si lo está, o si no hay git, rama de arriba o red: lo
    que no se puede saber no detiene). Antes de migrar: escribir sobre uno viejo choca al subir."""
    import subprocess

    from telar import git

    repo = git.repositorio(archivo_raiz)
    if repo is None:
        return ""

    def g(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60)

    if g("rev-parse", "--abbrev-ref", "@{u}").returncode != 0:
        return ""
    try:
        if g("fetch", "-q").returncode != 0:
            return ""
    except subprocess.TimeoutExpired:
        return ""
    rel = archivo_raiz.resolve().relative_to(repo.resolve()).as_posix() if archivo_raiz.exists() else \
        (archivo_raiz.parent.resolve() / archivo_raiz.name).relative_to(repo.resolve()).as_posix()
    arriba = g("rev-parse", "-q", "--verify", f"@{{u}}:{rel}").stdout.strip()
    if not arriba:
        return ""
    aqui = g("hash-object", str(archivo_raiz)).stdout.strip() if archivo_raiz.exists() else ""
    if aqui == arriba:
        return ""
    en_head = g("rev-parse", "-q", "--verify", f"HEAD:{rel}").stdout.strip()
    if en_head != arriba and g("merge-base", "--is-ancestor", "@{u}", "HEAD").returncode != 0:
        return (f"{rel} cambió arriba y esta máquina no lo tiene: trae lo de arriba antes (git -C {repo} pull, o "
                "/sincronizar) y vuelve a migrar")
    return ""
