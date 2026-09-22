"""La configuración del usuario: `~/.config/telar/config.toml`.

telar no guarda nada en el repositorio de trabajo salvo lo que el usuario ponga
ahí a propósito. Todo lo que es de esta máquina —qué multiplexor, qué sesión, qué
carpeta se está trabajando, qué proveedores se encienden— vive en un TOML, y todo
tiene un valor por defecto razonable: sin archivo, telar arranca igual.

Orden de precedencia, de más fuerte a más débil:

  1. las variables de entorno (`TELAR_*`), que son para una corrida suelta;
  2. el archivo de configuración;
  3. los valores por defecto de este módulo.

El esquema está documentado en `docs/configuracion.md`, y esa página manda: si
aquí se agrega una clave, allá se escribe.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

__all__ = [
    "Intervalos",
    "Proveedor",
    "Config",
    "ruta_config",
    "cargar",
    "ErrorDeConfig",
]

#: Multiplexores que telar sabe nombrar. Lo que cada uno puede hacer, en `telar.mux`.
MULTIPLEXORES = ("tmux", "zellij")


class ErrorDeConfig(Exception):
    """El archivo de configuración existe pero no se puede usar."""


@dataclass(frozen=True, slots=True)
class Intervalos:
    """Cada cuánto se vuelve a mirar algo, en segundos.

    `foco_maximo` no es un refresco: es el tope que se le pone a un intervalo sin
    cambio de foco al contar tiempo. Nadie avisa "me fui del computador", así que
    una hora de silencio cuenta como una hora y no como la noche entera.
    """

    refresco: float = 1.0
    ficha: float = 60.0
    proveedores: float = 300.0
    foco_maximo: float = 3600.0


@dataclass(frozen=True, slots=True)
class Proveedor:
    """Un proveedor encendido, con lo que él mismo necesite saber.

    telar no interpreta `opciones`: se las pasa tal cual al proveedor al
    construirlo. Ningún proveedor sale de red si no está declarado aquí.
    """

    nombre: str
    activo: bool = True
    opciones: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Agente:
    """Qué agente se abre en cada hilo, y en qué carpeta arranca.

    `nombre` vacío es no abrir ninguno: el hilo queda con una shell. `carpeta` es
    "hilo" (la carpeta de la unidad), "raiz" (la del repositorio) o una ruta. La ruta
    existe porque hay agentes cuya memoria cuelga de dónde arrancan: abrirlos en otra
    carpeta es abrir a otro, que no recuerda nada.
    """

    nombre: str = ""
    carpeta: str = "hilo"


@dataclass(frozen=True, slots=True)
class Config:
    """La configuración resuelta. Inmutable; para variarla, `dataclasses.replace`."""

    #: "tmux" o "zellij".
    multiplexor: str = "tmux"
    #: nombre de la sesión del multiplexor que telar teje.
    sesion: str = "telar"
    #: raíz del repositorio de trabajo: de ahí sale el perfil y ahí viven los hilos.
    raiz: Path = field(default_factory=Path.cwd)
    #: dónde escribir el estado (vínculos, prioridades, semáforo, foco). Nunca en `raiz`.
    #: Las fichas no se guardan: se leen del documento cada vez (ver docs/estado.md).
    estado: Path = field(default_factory=lambda: _estado_por_defecto())
    #: el `telar-perfil.yaml`; por defecto, el de la raíz.
    perfil: Path | None = None
    #: proveedores encendidos, por nombre.
    proveedores: dict[str, Proveedor] = field(default_factory=dict)
    #: quién arma la ficha de un documento. Tabla aparte de `proveedores`, que son los
    #: que traen ítems del día: comparten la palabra «proveedor» y nada más.
    ficha: Proveedor = field(default_factory=lambda: Proveedor(nombre="documento"))
    intervalos: Intervalos = field(default_factory=Intervalos)
    #: el agente que se abre en cada hilo; sin nombre, ninguno.
    agente: Agente = field(default_factory=Agente)
    #: de qué archivo salió esta configuración; None si son puros valores por defecto.
    origen: Path | None = None

    @property
    def ruta_perfil(self) -> Path:
        """El perfil declarado, o el que se espera en la raíz del repositorio."""
        return self.perfil or (self.raiz / "telar-perfil.yaml")

    def proveedores_activos(self) -> tuple[Proveedor, ...]:
        return tuple(p for p in self.proveedores.values() if p.activo)


def _hogar_config() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "telar"


def _estado_por_defecto() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    return (Path(base) if base else Path.home() / ".local" / "state") / "telar"


def ruta_config() -> Path:
    """Dónde se busca el archivo de configuración.

    `$TELAR_CONFIG` la pisa entera (útil en pruebas y en corridas de un solo uso).
    """
    env = os.environ.get("TELAR_CONFIG")
    if env:
        return Path(env).expanduser()
    return _hogar_config() / "config.toml"


def _ruta(valor: object, contexto: str) -> Path:
    """Una ruta de la configuración, siempre absoluta.

    El contrato promete que `ruta` sirve para `cd`, y una raíz relativa («.», «ejemplo»)
    dependía del directorio desde donde se corriera la orden: la misma sesión daba
    respuestas distintas según dónde estuviera la shell.
    """
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorDeConfig(f"{contexto}: se esperaba una ruta, llegó {valor!r}")
    return Path(valor).expanduser().absolute()


def _numero(valor: object, contexto: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorDeConfig(f"{contexto}: se esperaba un número, llegó {valor!r}")
    if valor <= 0:
        raise ErrorDeConfig(f"{contexto}: se esperaba un número positivo, llegó {valor!r}")
    return float(valor)


def _tabla(valor: object, contexto: str) -> dict:
    if not isinstance(valor, dict):
        raise ErrorDeConfig(f"{contexto}: se esperaba una tabla, llegó {valor!r}")
    return valor


def desde_dict(datos: dict, *, origen: Path | None = None) -> Config:
    """Arma una `Config` desde el TOML ya parseado, validando lo que llegó."""
    base = Config()
    cambios: dict[str, object] = {"origen": origen}

    if "multiplexor" in datos:
        mux = datos["multiplexor"]
        if mux not in MULTIPLEXORES:
            conocidos = ", ".join(MULTIPLEXORES)
            raise ErrorDeConfig(f"multiplexor: {mux!r} no es uno de: {conocidos}")
        cambios["multiplexor"] = mux

    if "sesion" in datos:
        sesion = datos["sesion"]
        if not isinstance(sesion, str) or not sesion.strip():
            raise ErrorDeConfig(f"sesion: se esperaba un nombre, llegó {sesion!r}")
        cambios["sesion"] = sesion

    if "raiz" in datos:
        cambios["raiz"] = _ruta(datos["raiz"], "raiz")
    if "estado" in datos:
        cambios["estado"] = _ruta(datos["estado"], "estado")
    if "perfil" in datos:
        cambios["perfil"] = _ruta(datos["perfil"], "perfil")

    if "intervalos" in datos:
        tabla = _tabla(datos["intervalos"], "intervalos")
        campos = {f: getattr(base.intervalos, f) for f in Intervalos.__slots__}
        for clave, valor in tabla.items():
            if clave not in campos:
                raise ErrorDeConfig(f"intervalos.{clave}: no existe")
            campos[clave] = _numero(valor, f"intervalos.{clave}")
        cambios["intervalos"] = Intervalos(**campos)

    if "ficha" in datos:
        tabla = _tabla(datos["ficha"], "ficha")
        nombre = tabla.get("proveedor", "documento")
        if not isinstance(nombre, str) or not nombre.strip():
            raise ErrorDeConfig(f"ficha.proveedor: se esperaba un nombre, llegó {nombre!r}")
        opciones = {k: v for k, v in tabla.items() if k != "proveedor"}
        cambios["ficha"] = Proveedor(nombre=nombre, activo=True, opciones=opciones)

    if "proveedores" in datos:
        tabla = _tabla(datos["proveedores"], "proveedores")
        proveedores: dict[str, Proveedor] = {}
        for nombre, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"proveedores.{nombre}")
            activo = cuerpo.get("activo", True)
            if not isinstance(activo, bool):
                raise ErrorDeConfig(f"proveedores.{nombre}.activo: se esperaba true o false")
            opciones = {k: v for k, v in cuerpo.items() if k != "activo"}
            proveedores[nombre] = Proveedor(nombre=nombre, activo=activo, opciones=opciones)
        cambios["proveedores"] = proveedores

    if "agente" in datos:
        tabla = _tabla(datos["agente"], "agente")
        sobra = set(tabla) - {"nombre", "carpeta"}
        if sobra:
            raise ErrorDeConfig(f"agente.{sorted(sobra)[0]}: no existe")
        nombre = tabla.get("nombre", "")
        carpeta = tabla.get("carpeta", "hilo")
        if not isinstance(nombre, str):
            raise ErrorDeConfig(f"agente.nombre: se esperaba un nombre, llegó {nombre!r}")
        if not isinstance(carpeta, str) or not carpeta.strip():
            raise ErrorDeConfig(
                f"agente.carpeta: se esperaba \"hilo\", \"raiz\" o una ruta, llegó {carpeta!r}"
            )
        cambios["agente"] = Agente(nombre=nombre.strip(), carpeta=carpeta.strip())

    desconocidas = set(datos) - {
        "multiplexor", "sesion", "raiz", "estado", "perfil", "intervalos", "proveedores",
        "ficha", "agente",
    }
    if desconocidas:
        sobra = ", ".join(sorted(desconocidas))
        raise ErrorDeConfig(f"claves que telar no conoce: {sobra}")

    return replace(base, **cambios)  # type: ignore[arg-type]


def _entorno(cfg: Config) -> Config:
    """Las variables `TELAR_*` pisan lo que diga el archivo."""
    cambios: dict[str, object] = {}
    if v := os.environ.get("TELAR_MULTIPLEXOR"):
        if v not in MULTIPLEXORES:
            raise ErrorDeConfig(f"TELAR_MULTIPLEXOR: {v!r} no es uno de: {', '.join(MULTIPLEXORES)}")
        cambios["multiplexor"] = v
    if v := os.environ.get("TELAR_SESION"):
        cambios["sesion"] = v
    if v := os.environ.get("TELAR_RAIZ"):
        cambios["raiz"] = Path(v).expanduser().absolute()
    if v := os.environ.get("TELAR_ESTADO"):
        cambios["estado"] = Path(v).expanduser()
    if v := os.environ.get("TELAR_PERFIL"):
        cambios["perfil"] = Path(v).expanduser()
    return replace(cfg, **cambios) if cambios else cfg  # type: ignore[arg-type]


def cargar(ruta: Path | None = None) -> Config:
    """Lee la configuración. Sin archivo, devuelve los valores por defecto.

    `ruta` explícita manda sobre `$TELAR_CONFIG`; si esa ruta no existe, es un
    error, porque alguien la pidió a propósito.
    """
    explicita = ruta is not None
    destino = Path(ruta).expanduser() if ruta is not None else ruta_config()

    if not destino.exists():
        if explicita:
            raise ErrorDeConfig(f"no existe el archivo de configuración: {destino}")
        return _entorno(Config())

    try:
        with destino.open("rb") as f:
            datos = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ErrorDeConfig(f"{destino}: TOML mal formado: {e}") from e
    except OSError as e:
        raise ErrorDeConfig(f"{destino}: no se pudo leer: {e}") from e

    return _entorno(desde_dict(datos, origen=destino))
