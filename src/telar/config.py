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
class Hilos:
    """De qué carpetas salen los hilos que abre `tejer`, y cuántos.

    `directorios` vacío es lo de siempre: las unidades del perfil, en el orden en que el
    perfil declara sus arquetipos. Con directorios, solo las unidades que viven dentro de
    alguno, repartidas por turnos en el orden en que se nombran: una de cada carpeta por
    vuelta. `tope` es cuántas abre `tejer` de una vez; las demás se abren a mano.
    """

    directorios: tuple[str, ...] = ()
    tope: int = 8


#: lo que flow le decía a Claude al pinchar una reunión, y el punto de partida de telar.
REUNION_POR_DEFECTO = "/preparar-reunion {titulo} (hoy {hora}) · proyecto: {proyecto}"

#: lo que se le dice al agente al abrir un proyecto desde la lista del dashboard. No supone
#: ninguna skill: cualquier agente sabe leer un archivo.
PROYECTO_POR_DEFECTO = "Carga el proyecto {nombre}: lee {documento} y dime en qué está y qué sigue."

#: lo que se le escribe (sin enviar) al agente de un hilo que ya está abierto al llevarle un
#: pendiente, y lo primero que recibe un agente recién abierto para trabajarlo.
PENDIENTE_POR_DEFECTO = "{texto}"


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
    #: lo que se le dice al agente al pinchar una reunión de la agenda. Marcadores:
    #: {titulo} {hora} {fecha} {enlace} {proyecto}; si no hay proyecto, la cola
    #: «· proyecto: …» se quita. La de fábrica es la de flow, y supone una skill
    #: `/preparar-reunion` instalada en el agente.
    reunion: str = REUNION_POR_DEFECTO
    #: lo que se le dice al abrir un proyecto desde la lista. Marcadores: {nombre} (el de
    #: pantalla), {ruta} (relativa a la raíz), {carpeta} y {documento} (absolutas).
    proyecto: str = PROYECTO_POR_DEFECTO
    #: al llevar un pendiente a un hilo con su agente ya corriendo: se escribe y no se
    #: envía. Marcadores: {texto} {ref} {id}; con {id} y un pendiente sin id, rige {texto}.
    pendiente: str = PENDIENTE_POR_DEFECTO
    #: al llevarlo a un hilo que hay que abrir: es el primer mensaje del agente, y ese sí
    #: se envía (no hay a quién escribirle hasta que arranca). Mismos marcadores.
    pendiente_nuevo: str = PENDIENTE_POR_DEFECTO
    #: si el agente recibe al empezar unas líneas sobre su hilo y cómo hablar con los otros
    #: (el gancho SessionStart de `telar agente contexto`).
    contexto: bool = True


#: teclas que el dashboard ya usa: un atajo no las puede tomar. Las letras de los pendientes
#: (a b d e f g h i), los números de la agenda, r (recargar), p (proyectos), t (tareas), / (buscar).
TECLAS_RESERVADAS = frozenset("abdefghi123456789rpt/")


@dataclass(frozen=True, slots=True)
class Atajo:
    """Una tecla del dashboard que abre un hilo con el agente haciendo algo recurrente.

    En flow eran `m` (el correo con `/correo`), `w` (WhatsApp), `c` (capacity): tareas que no
    son de ningún proyecto y se hacen varias veces al día. Cada vez es un hilo nuevo, con la
    hora en el nombre, porque la revisión de las 9 y la de las 15 son dos conversaciones.
    """

    tecla: str
    nombre: str
    mensaje: str
    descripcion: str = ""


@dataclass(frozen=True, slots=True)
class Seccion:
    """Un grupo propio en la lista de hilos, con su página opcional.

    `hilos` dice cuáles le pertenecen: un nombre exacto, o un prefijo si termina en `*`.
    Esos hilos salen de la lista general y van bajo la cabecera de la sección. `home` es
    un comando que imprime el JSON de su página (ver docs/contratos.md): telar lo corre
    cuando se abre y lo dibuja, sin saber de qué trata.
    """

    clave: str
    nombre: str
    hilos: tuple[str, ...] = ()
    home: tuple[str, ...] = ()

    def contiene(self, hilo: str) -> bool:
        return any(hilo.startswith(p[:-1]) if p.endswith("*") else hilo == p for p in self.hilos)


#: con qué se llega a una máquina remota. mosh sobrevive a que el laptop se duerma.
TRANSPORTES = ("mosh", "ssh")


@dataclass(frozen=True, slots=True)
class Remoto:
    """Una máquina donde pueden vivir hilos (`[remotos.<nombre>]`).

    El agente de un hilo remoto corre allá, en una sesión tmux propia; el hilo local es
    solo la ventana desde donde se lo mira. Ver docs/propuestas/hilos-remotos.md.
    """

    nombre: str
    #: lo que va después de mosh/ssh: `usuario@servidor`, o un alias de ~/.ssh/config.
    destino: str
    transporte: str = "mosh"
    #: la carpeta del repositorio EN la otra máquina; ahí se traducen los vínculos.
    raiz: str = "~"
    #: la casilla (Maildir) común con todos los correos entre agentes, si el servidor la
    #: publica; sin ella, las conversaciones son solo las de la Maildir propia.
    correo_archivo: str = ""
    #: la carpeta común donde cada persona publica sus hilos de esa máquina (`telar
    #: directorio`); sin ella, no se publica ni se lee nada.
    directorio: str = ""
    #: los repositorios que viven en las dos máquinas (`~/repo/empresa`): antes de llevar un
    #: hilo allá se revisa que no tengan trabajo sin subir, además de la raíz.
    repos: tuple[str, ...] = ()


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
    #: de qué carpetas salen los hilos, y cuántos se abren al tejer.
    hilos: Hilos = field(default_factory=Hilos)
    #: las teclas del dashboard que abren un hilo con el agente haciendo algo (`[atajos.m]`).
    atajos: tuple[Atajo, ...] = ()
    #: grupos propios en la lista de hilos (`[secciones.x]`), en el orden del archivo.
    secciones: tuple[Seccion, ...] = ()
    #: máquinas donde pueden vivir hilos. Sin ninguna, no hay hilos remotos.
    remotos: tuple[Remoto, ...] = ()
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
        sobra = set(tabla) - {"nombre", "carpeta", "reunion", "proyecto", "pendiente", "pendiente_nuevo", "contexto"}
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
        reunion = tabla.get("reunion", REUNION_POR_DEFECTO)
        if not isinstance(reunion, str) or not reunion.strip():
            raise ErrorDeConfig(f"agente.reunion: se esperaba un texto, llegó {reunion!r}")
        proyecto = tabla.get("proyecto", PROYECTO_POR_DEFECTO)
        if not isinstance(proyecto, str) or not proyecto.strip():
            raise ErrorDeConfig(f"agente.proyecto: se esperaba un texto, llegó {proyecto!r}")
        textos = {}
        for clave in ("pendiente", "pendiente_nuevo"):
            valor = tabla.get(clave, PENDIENTE_POR_DEFECTO)
            if not isinstance(valor, str) or not valor.strip():
                raise ErrorDeConfig(f"agente.{clave}: se esperaba un texto, llegó {valor!r}")
            textos[clave] = valor.strip()
        contexto = tabla.get("contexto", True)
        if not isinstance(contexto, bool):
            raise ErrorDeConfig(f"agente.contexto: se esperaba true o false, llegó {contexto!r}")
        cambios["agente"] = Agente(nombre=nombre.strip(), carpeta=carpeta.strip(),
                                   reunion=reunion.strip(), proyecto=proyecto.strip(), contexto=contexto, **textos)

    if "hilos" in datos:
        tabla = _tabla(datos["hilos"], "hilos")
        sobra = set(tabla) - {"directorios", "tope"}
        if sobra:
            raise ErrorDeConfig(f"hilos.{sorted(sobra)[0]}: no existe")
        dirs = tabla.get("directorios", [])
        if not isinstance(dirs, list) or not all(isinstance(d, str) and d.strip() for d in dirs):
            raise ErrorDeConfig(f"hilos.directorios: se esperaba una lista de carpetas, llegó {dirs!r}")
        for d in dirs:
            if d.startswith("/") or ".." in Path(d).parts:
                raise ErrorDeConfig(f"hilos.directorios: «{d}» tiene que ser relativa a la raíz y no salir de ella")
        tope = tabla.get("tope", 8)
        if not isinstance(tope, int) or isinstance(tope, bool) or tope < 0:
            raise ErrorDeConfig(f"hilos.tope: se esperaba un número entero, llegó {tope!r}")
        cambios["hilos"] = Hilos(directorios=tuple(d.strip().strip("/") for d in dirs), tope=tope)

    if "atajos" in datos:
        tabla = _tabla(datos["atajos"], "atajos")
        atajos = []
        for tecla, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"atajos.{tecla}")
            if len(tecla) != 1:
                raise ErrorDeConfig(f"atajos.{tecla}: la tecla es un solo carácter")
            if tecla in TECLAS_RESERVADAS:
                raise ErrorDeConfig(f"atajos.{tecla}: esa tecla ya la usa el dashboard")
            sobra = set(cuerpo) - {"nombre", "mensaje", "descripcion"}
            if sobra:
                raise ErrorDeConfig(f"atajos.{tecla}.{sorted(sobra)[0]}: no existe")
            campos = {}
            for clave in ("nombre", "mensaje", "descripcion"):
                valor = cuerpo.get(clave, "")
                if not isinstance(valor, str) or (clave != "descripcion" and not valor.strip()):
                    raise ErrorDeConfig(f"atajos.{tecla}.{clave}: se esperaba un texto, llegó {valor!r}")
                campos[clave] = valor.strip()
            atajos.append(Atajo(tecla=tecla, **campos))
        cambios["atajos"] = tuple(atajos)

    if "secciones" in datos:
        tabla = _tabla(datos["secciones"], "secciones")
        secciones = []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"secciones.{clave}")
            sobra = set(cuerpo) - {"nombre", "hilos", "home"}
            if sobra:
                raise ErrorDeConfig(f"secciones.{clave}.{sorted(sobra)[0]}: no existe")
            nombre = cuerpo.get("nombre", clave)
            if not isinstance(nombre, str) or not nombre.strip():
                raise ErrorDeConfig(f"secciones.{clave}.nombre: se esperaba un texto, llegó {nombre!r}")
            for campo in ("hilos", "home"):
                valor = cuerpo.get(campo, [])
                if not isinstance(valor, list) or not all(isinstance(x, str) and x.strip() for x in valor):
                    raise ErrorDeConfig(f"secciones.{clave}.{campo}: se esperaba una lista de textos, llegó {valor!r}")
            secciones.append(Seccion(clave=clave, nombre=nombre.strip(),
                                     hilos=tuple(x.strip() for x in cuerpo.get("hilos", [])),
                                     home=tuple(cuerpo.get("home", []))))
        cambios["secciones"] = tuple(secciones)

    if "remotos" in datos:
        tabla = _tabla(datos["remotos"], "remotos")
        remotos = []
        for nombre, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"remotos.{nombre}")
            sobra = set(cuerpo) - {"destino", "transporte", "raiz", "correo_archivo", "directorio", "repos"}
            if sobra:
                raise ErrorDeConfig(f"remotos.{nombre}.{sorted(sobra)[0]}: no existe")
            destino = cuerpo.get("destino", "")
            if not isinstance(destino, str) or not destino.strip() or destino.strip().startswith("-"):
                raise ErrorDeConfig(f"remotos.{nombre}.destino: se esperaba usuario@servidor o un alias, llegó {destino!r}")
            transporte = cuerpo.get("transporte", "mosh")
            if transporte not in TRANSPORTES:
                raise ErrorDeConfig(f"remotos.{nombre}.transporte: {' o '.join(TRANSPORTES)}, llegó {transporte!r}")
            raiz = cuerpo.get("raiz", "~")
            if not isinstance(raiz, str) or not raiz.strip():
                raise ErrorDeConfig(f"remotos.{nombre}.raiz: se esperaba una carpeta, llegó {raiz!r}")
            archivo = cuerpo.get("correo_archivo", "")
            directorio = cuerpo.get("directorio", "")
            for clave, valor in (("correo_archivo", archivo), ("directorio", directorio)):
                if not isinstance(valor, str):
                    raise ErrorDeConfig(f"remotos.{nombre}.{clave}: se esperaba una ruta, llegó {valor!r}")
            repos = cuerpo.get("repos", [])
            if not isinstance(repos, list) or not all(isinstance(x, str) and x.strip() for x in repos):
                raise ErrorDeConfig(f"remotos.{nombre}.repos: se esperaba una lista de carpetas, llegó {repos!r}")
            remotos.append(Remoto(nombre=nombre, destino=destino.strip(), transporte=transporte, repos=tuple(x.strip() for x in repos),
                                  raiz=raiz.strip().rstrip("/") or "/", correo_archivo=archivo.strip(),
                                  directorio=directorio.strip().rstrip("/")))
        cambios["remotos"] = tuple(remotos)

    desconocidas = set(datos) - {
        "multiplexor", "sesion", "raiz", "estado", "perfil", "intervalos", "proveedores",
        "ficha", "agente", "hilos", "atajos", "secciones", "remotos",
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


# ── escribir el calendario ─────────────────────────────────────────────────────────

_CABEZA_CALENDARIO = "[proveedores.calendario]"


def fuente_calendario(valor: str) -> tuple[str, str]:
    """(`url` o `archivo`, valor normalizado). `webcal://` es https con otro nombre.

    `gws` y `ninguno` no son fuentes iCal sino tipos, y los resuelve `escribir_calendario`.
    """
    valor = valor.strip()
    if not valor:
        raise ErrorDeConfig("falta la dirección del calendario")
    if valor.lower().startswith("webcal://"):
        valor = "https://" + valor[len("webcal://"):]
    if valor.lower().startswith(("https://", "http://")):
        return "url", valor
    ruta = Path(valor).expanduser()
    if not ruta.is_file():
        raise ErrorDeConfig(
            f"«{valor}» no es una dirección https ni un archivo .ics que exista"
        )
    return "archivo", str(ruta)


def escribir_calendario(valor: str, ruta: Path | None = None) -> Path:
    """Deja `[proveedores.calendario]` apuntando a esa fuente, y nada más.

    `valor` es una dirección iCal (https, webcal) o un archivo .ics; o bien `gws`, para
    leerlo con la CLI de Google Workspace; o `ninguno`, para desconectarlo.

    Se reemplaza la tabla si ya había una (la de verdad, no la que está comentada en el
    ejemplo) y el resto del archivo queda como estaba, comentarios incluidos. Antes de
    escribir se comprueba que el resultado se siga leyendo: un archivo que telar no
    entiende es peor que un calendario sin conectar.

    El archivo queda legible solo por su dueño: una dirección iCal privada es un
    secreto, porque cualquiera que la tenga ve la agenda.
    """
    eleccion = valor.strip().lower()
    if eleccion in ("gws", "ninguno"):
        lineas = [f'tipo = "{eleccion}"']
    else:
        clave, fuente = fuente_calendario(valor)
        lineas = ['tipo = "ics"', f"{clave} = {_cadena_toml(fuente)}"]
    destino = Path(ruta).expanduser() if ruta is not None else ruta_config()
    texto = destino.read_text(encoding="utf-8") if destino.exists() else ""

    renglones = texto.splitlines()
    salida: list[str] = []
    dentro = False
    for r in renglones:
        limpio = r.strip()
        if limpio == _CABEZA_CALENDARIO:
            dentro = True
            continue
        if dentro and limpio.startswith("["):
            dentro = False
        if not dentro:
            salida.append(r)
    while salida and not salida[-1].strip():
        salida.pop()

    bloque = [
        "",
        "# La agenda del día (lo escribió `telar config --calendario`): ics, gws o ninguno.",
        _CABEZA_CALENDARIO,
        *lineas,
    ]
    nuevo = "\n".join(salida + bloque) + "\n"

    try:
        desde_dict(tomllib.loads(nuevo), origen=destino)
    except (tomllib.TOMLDecodeError, ErrorDeConfig) as e:
        raise ErrorDeConfig(f"no escribí nada: el resultado no se podría leer ({e})") from e

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".nuevo")
    temporal.write_text(nuevo, encoding="utf-8")
    os.chmod(temporal, 0o600)
    os.replace(temporal, destino)
    return destino


def _cadena_toml(valor: str) -> str:
    """Una cadena TOML básica. Las secuencias de escape de JSON son válidas en TOML."""
    import json

    return json.dumps(valor, ensure_ascii=False)


def escribir_clave(tabla: str, clave: str, valor: object, ruta: Path | None = None) -> Path:
    """Pone `clave = valor` en `[tabla]`, o la quita si `valor` es None.

    `valor` es un texto, un número o una lista de textos.

    Toca solo esa línea: el resto del archivo, comentarios incluidos, queda como estaba.
    Si la tabla no existe se agrega al final. Igual que con el calendario, antes de
    escribir se comprueba que el resultado se siga leyendo.
    """
    destino = Path(ruta).expanduser() if ruta is not None else ruta_config()
    texto = destino.read_text(encoding="utf-8") if destino.exists() else ""
    renglones = texto.splitlines()
    cabeza = f"[{tabla}]"
    nueva = f"{clave} = {_valor_toml(valor)}" if valor is not None else None

    try:
        i = next(n for n, r in enumerate(renglones) if r.strip() == cabeza)
    except StopIteration:
        i = -1
    if i < 0:
        if nueva is not None:
            while renglones and not renglones[-1].strip():
                renglones.pop()
            renglones += ["", cabeza, nueva]
    else:
        fin = next((n for n in range(i + 1, len(renglones)) if renglones[n].strip().startswith("[")),
                   len(renglones))
        donde = next((n for n in range(i + 1, fin)
                      if renglones[n].split("=", 1)[0].strip() == clave and not renglones[n].lstrip().startswith("#")),
                     -1)
        if donde >= 0:
            if nueva is None:
                del renglones[donde]
            else:
                renglones[donde] = nueva
        elif nueva is not None:
            ultimo = max((n for n in range(i, fin) if renglones[n].strip()), default=i)
            renglones.insert(ultimo + 1, nueva)
    nuevo = "\n".join(renglones) + "\n"

    try:
        desde_dict(tomllib.loads(nuevo), origen=destino)
    except (tomllib.TOMLDecodeError, ErrorDeConfig) as e:
        raise ErrorDeConfig(f"no escribí nada: el resultado no se podría leer ({e})") from e
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".nuevo")
    temporal.write_text(nuevo, encoding="utf-8")
    if destino.exists():
        os.chmod(temporal, destino.stat().st_mode & 0o777)
    os.replace(temporal, destino)
    return destino


def _valor_toml(valor: object) -> str:
    """Un valor TOML en una línea: texto, entero o lista de textos (JSON sirve para los tres)."""
    import json

    if isinstance(valor, bool) or not isinstance(valor, (str, int, list, tuple)):
        raise ErrorDeConfig(f"no sé escribir {valor!r} en la configuración")
    return json.dumps(list(valor) if isinstance(valor, tuple) else valor, ensure_ascii=False)

