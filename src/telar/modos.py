"""Los modos de la página: un nombre con valores para un catálogo fijo de ajustes (docs/propuestas/modos.md).

    CATALOGO                  cada ajuste: su grupo, su nombre y sus valores
    DE_FABRICA                «estandar» y «foco»
    validar(clave, valores)   los valores de un modo, normalizados; ErrorDeConfig si alguno no sirve
    todos(config)             cada modo con sus valores completos (lo que no dice, de «estandar»)
    guardar / borrar          escribir o quitar `[modos.<clave>]` en la configuración

Un modo dice valores para algunos ajustes; lo que no dice lo toma de «estandar», y «estandar» toma la terminal de
`[terminal]`. Cuál está puesto lo sabe el navegador (pagina/src/web/modos.ts), no esta máquina.
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


CATALOGO: tuple[Ajuste, ...] = (
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
    Ajuste("avisos", "avisos", "avisos", ("todos", "urgentes", "ninguno"), "urgentes: solo los de algo que falló o pide atención"),
    Ajuste("aviso_version", "avisos", "aviso de versión nueva", ("visible", "oculto")),
)
POR_CLAVE = {a.clave: a for a in CATALOGO}
TERMINAL = ("columnas", "posicion", "fondo")

#: los modos de fábrica: «estandar» dice todo (la terminal, de `[terminal]`: ver `todos`); «foco», solo la terminal
DE_FABRICA: dict[str, dict] = {
    "estandar": {"nombre": "estándar", "valores": {
        "barra": "abierta", "lado": "abierto", "cabecera": "visible", "acciones": "visible", "escribir": "oculta",
        "pantalla_completa": "no", "etiquetas": "", "sin_etiqueta": "se-ven", "avisos": "todos",
        "aviso_version": "visible"}},
    "foco": {"nombre": "foco", "valores": {
        "barra": "oculta", "lado": "oculto", "cabecera": "oculta", "acciones": "oculta", "escribir": "oculta",
        "pantalla_completa": "no", "columnas": 110, "posicion": "centro", "fondo": "ninguno", "avisos": "urgentes",
        "aviso_version": "oculto"}},
}


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
    valores = {}
    for k, v in cuerpo.items():
        if k == "nombre":
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
    return {"nombre": nombre.strip(), "valores": valores}


def todos(config) -> list[dict]:
    """Cada modo, con todos sus valores: los de fábrica y los de la configuración (`[modos.<n>]`, que pisan a uno de
    fábrica con su mismo nombre). Lo que un modo no dice, de «estandar»; la terminal de «estandar», de `[terminal]`."""
    t = config.terminal
    base_estandar = {**DE_FABRICA["estandar"]["valores"], "columnas": t.columnas, "posicion": t.posicion, "fondo": t.fondo}
    propios = getattr(config, "modos", {}) or {}
    claves = list(DE_FABRICA) + [k for k in propios if k not in DE_FABRICA]
    estandar = {**base_estandar, **propios.get("estandar", {}).get("valores", {})}
    salida = []
    for k in claves:
        fabrica = DE_FABRICA.get(k, {})
        propio = propios.get(k, {})
        valores = {**estandar, **fabrica.get("valores", {}), **propio.get("valores", {})} if k != "estandar" else estandar
        salida.append({"clave": k, "nombre": propio.get("nombre") or fabrica.get("nombre") or k, "valores": valores,
                       "de_fabrica": k in DE_FABRICA, "cambiado": k in propios})
    return salida


def catalogo() -> list[dict]:
    return [{"clave": a.clave, "grupo": a.grupo, "nombre": a.nombre, "opciones": list(a.opciones), "ayuda": a.ayuda}
            for a in CATALOGO]


def guardar(ruta: Path | None, clave: str, valores: dict, nombre: str = "") -> dict:
    """Escribe `[modos.<clave>]` con esos valores (los reemplaza enteros: lo que no venga, se quita de la tabla)."""
    from telar import config as mod_config

    limpio = validar(clave, {**({"nombre": nombre} if nombre else {}), **valores})
    destino = Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()
    _quitar(destino, clave)
    if limpio["nombre"]:
        mod_config.escribir_clave(f"modos.{clave}", "nombre", limpio["nombre"], destino)
    for k, v in limpio["valores"].items():
        mod_config.escribir_clave(f"modos.{clave}", k, v, destino)
    return limpio


def borrar(ruta: Path | None, clave: str) -> bool:
    """Quita `[modos.<clave>]`: uno propio desaparece, uno de fábrica vuelve a ser el de fábrica. True si estaba."""
    from telar import config as mod_config

    destino = Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()
    return _quitar(destino, clave)


def _quitar(destino: Path, clave: str) -> bool:
    import tomllib

    from telar import config as mod_config
    from telar.unirse import quitar_tabla

    if not CLAVE.match(clave) or not destino.exists():
        return False
    texto = destino.read_text(encoding="utf-8")
    nuevo = quitar_tabla(texto, f"modos.{clave}")
    if nuevo == texto:
        return False
    mod_config.desde_dict(tomllib.loads(nuevo), origen=destino)  # que se siga leyendo
    tmp = destino.with_name(destino.name + ".nuevo")
    tmp.write_text(nuevo, encoding="utf-8")
    tmp.replace(destino)
    return True
