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
import re
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
MULTIPLEXORES = ("tmux",)


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

#: y al pinchar una que ya empezó: procesar lo que se dijo. Supone la skill `/minuta`.
MINUTA_POR_DEFECTO = "/minuta {titulo} ({fecha} {hora}) · proyecto: {proyecto}"

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
    #: lo mismo para una reunión que ya empezó (la minuta, no la preparación).
    minuta: str = MINUTA_POR_DEFECTO
    #: lo que se le dice al abrir un proyecto desde la lista. Marcadores: {nombre} (el de
    #: pantalla), {ruta} (relativa a la raíz), {carpeta} y {documento} (absolutas).
    proyecto: str = PROYECTO_POR_DEFECTO
    #: al llevar un pendiente a un hilo con su agente ya corriendo: se escribe y no se
    #: envía. Marcadores: {texto} {ref} {id} {direccion}; con {id} y un pendiente sin id, o
    #: {direccion} y uno sin dirección, rige {texto}.
    pendiente: str = PENDIENTE_POR_DEFECTO
    #: al llevarlo a un hilo que hay que abrir: es el primer mensaje del agente, y ese sí
    #: se envía (no hay a quién escribirle hasta que arranca). Mismos marcadores.
    pendiente_nuevo: str = PENDIENTE_POR_DEFECTO
    #: si el agente recibe al empezar unas líneas sobre su hilo y cómo hablar con los otros
    #: (el gancho SessionStart de `telar agente contexto`).
    contexto: bool = True
    #: cuántas sesiones propias (hilos que no son tabs: periódicos, encargos, el celular) pueden
    #: estar vivas a la vez en esta máquina; 0 es sin tope. Al abrir otra se cierran las ociosas.
    max_vivos: int = 0
    #: la sordina (telar/sordina/): en Claude Code, una línea gris por archivo editado y por comando, sin
    #: diffs ni salida. La pone `telar agente instalar`; con false, no.
    sordina: bool = True


#: teclas que el dashboard ya usa (pagina/src/vistas/dashboard/panel.ts, teclasDePestanas): n (ahora), v (tareas),
#: p (proyectos), r (recargar), o (periódicos), d (el plan), a (la agenda), c (el correo), / (buscar). Un
#: atajo con una de ellas no es un error: la pestaña le gana y el atajo queda con un clic. `telar doctor`
#: lo avisa. Las de las pestañas de bloques y proveedores se suman en cada configuración.
TECLAS_RESERVADAS = frozenset("nvprodac/")


@dataclass(frozen=True, slots=True)
class ReglaAgenda:
    """Qué se le dice al agente al pinchar un evento de cierto tipo (`[agenda.<clave>]`).

    `si` es una expresión regular que se busca en el título, sin distinguir mayúsculas.
    `antes` rige mientras el evento no empieza; `despues`, desde que empezó. Una vacía cae
    a la de `[agente]` (`reunion` o `minuta`). La primera regla que calza gana.
    """

    clave: str
    si: str
    antes: str = ""
    despues: str = ""


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
    #: dónde se muestra: «hoy» (arriba del día, los generales), la clave de un bloque del
    #: dashboard (en su título: «correo» → el de procesar el correo) o «seccion:<clave>» (en
    #: la pestaña de esa sección). La tecla funciona desde cualquier pestaña.
    en: str = "hoy"
    #: si no es "", el mensaje se le encarga a ese agente residente (su carpeta) en vez de abrir
    #: un hilo nuevo: la tecla lleva a su hilo de siempre (ver telar.encargos).
    agente: str = ""


@dataclass(frozen=True, slots=True)
class Bloque:
    """Una sección del dashboard que llena un comando (`[bloques.<clave>]`): los correos de hoy,
    la retro del día. El comando imprime el mismo JSON que una página de sección
    (docs/contratos.md); telar lo pide con el ritmo de la red. Cada bloque es su propia pestaña,
    salvo que `en` lo ponga dentro de otra («plan»)."""

    clave: str
    nombre: str
    comando: tuple[str, ...]
    #: el color de la sección: azul, amarillo, verde, rojo, magenta, cian, violeta
    color: str = "cian"
    #: "" es una pestaña propia; «plan», arriba de la pestaña del plan (y solo si trae algo)
    en: str = ""
    #: la tecla de su pestaña en el dashboard, si tiene una
    tecla: str = ""


@dataclass(frozen=True, slots=True)
class App:
    """Algo que se abre en el panel y no es un hilo: un juego, un vivero, un atlas.

    Viene de una de tres fuentes, y solo una: `pagina`, un comando que imprime el JSON de una
    página (el contrato de `telar seccion`); `archivo`, un HTML autocontenido que llena el panel;
    o `url`, una página servida que se muestra en un marco. `telar app <clave> --json` las vuelve
    las tres una página, así el panel dibuja una sola cosa (ver docs/configuracion.md, `[apps]`).
    """

    clave: str
    nombre: str
    descripcion: str = ""
    pagina: tuple[str, ...] = ()
    archivo: str = ""
    url: str = ""
    #: con `archivo`: el .json donde el HTML guarda lo suyo (`window.lienzo.guardar`)
    memoria: str = ""

    @property
    def fuente(self) -> str:
        return "pagina" if self.pagina else "archivo" if self.archivo else "url"


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


@dataclass(frozen=True, slots=True)
class Bus:
    """El bus entre máquinas (`[bus]`, ver telar.bus). Sin `url`, no hay bus: todo es local."""

    #: `nats://host:4222`, casi siempre la IP de la red privada de la máquina que no se apaga.
    url: str = ""
    #: el archivo con el token de esta persona en el bus (nunca el token mismo en la configuración).
    token: str = ""
    #: quién es esta persona en el bus; vacío es el usuario del sistema.
    persona: str = ""
    #: hilos que otra máquina no puede leer (`telar hilo leer --maquina`), por nombre o carpeta, con `*`
    no_leer: tuple[str, ...] = ()
    #: dónde caen los archivos que otra máquina manda (`telar archivo`); vacío, `[enlace] entrada` o ~/telar-entrada
    entrada: str = ""
    #: cómo se llama esta máquina en el bus; vacío es su nombre de red, corto.
    maquina: str = ""


@dataclass(frozen=True, slots=True)
class Resultado:
    """Lo que una skill deja por día y se quiere ver en el dashboard (`[resultados.<clave>]`, ver
    telar.resultados): un `AAAA-MM-DD.json` (o `.md`) por día en una carpeta."""

    clave: str
    #: la carpeta en la máquina donde vive. Con `en`, es la de respaldo si esa máquina no responde.
    carpeta: str = ""
    #: la máquina del bus donde se escribe (la que corre la skill); "" es esta.
    en: str = ""
    #: cómo se llama en el dashboard; por defecto, la clave.
    nombre: str = ""
    #: el comando que atiende un comentario sobre un día (lista de palabras; el texto le llega por la
    #: entrada estándar). Se declara en la máquina donde vive el resultado; vacío, no recibe comentarios.
    comentar: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Tipo:
    """Dónde viven los objetos de un tipo y con qué formato (`[tipos.<clave>]`, telar.tipos): una
    carpeta con un archivo por objeto. Con `en`, viven en otra máquina del bus."""

    clave: str
    carpeta: str = ""
    formato: str = "archivo"
    en: str = ""


@dataclass(frozen=True, slots=True)
class Notas:
    """Las notas que las skills y la persona le dejan a los eventos del día (`[notas]`, telar.notas)."""

    #: dónde se guardan, un `AAAA-MM-DD.json` por día; "" es `<estado>/notas`.
    carpeta: str = ""
    #: la máquina del bus que las guarda; "" es esta.
    en: str = ""


@dataclass(frozen=True, slots=True)
class AgenteExtra:
    """Lo que un agente residente agrega a lo que telar descubre (`[agentes.<carpeta>]`)."""

    clave: str
    #: hilos suyos además del que lleva su nombre: nombre exacto, o prefijo si termina en `*`.
    hilos: tuple[str, ...] = ()
    #: un comando que imprime una página propia; sus bloques van arriba del home que arma telar.
    home: tuple[str, ...] = ()
    #: para el agente al abrir su sesión, después del prompt (permisos, herramientas).
    argumentos: tuple[str, ...] = ()
    #: dónde vive este agente, si no es donde dice `[agentes] en`: «aqui», un [remotos] o un
    #: [enlaces] (la puerta: así el servidor le encarga a un agente que vive en el laptop).
    en: str = ""


#: con qué se llega a una máquina remota. mosh sobrevive a que el laptop se duerma.
TRANSPORTES = ("mosh", "ssh")


@dataclass(frozen=True, slots=True)
class Repo:
    """Un repositorio de trabajo (`[repos.<nombre>]`): su carpeta y, si no está en ella, su perfil.

    Los hilos trabajan en carpetas de uno u otro; cada repo trae su perfil (qué es una unidad de trabajo
    ahí), y telar los junta (telar.perfil.cargar_todos). Puede estar dentro de otro, como un repo del equipo
    dentro del repo de vida: entonces sus carpetas las describe su propio perfil."""

    nombre: str
    #: la carpeta del repositorio, absoluta (con `~` expandida)
    ruta: Path
    #: el archivo de su perfil, si no es `.telar/perfil.yaml` en su carpeta
    perfil: str = ""


@dataclass(frozen=True, slots=True)
class Remoto:
    """Una máquina donde pueden vivir hilos (`[remotos.<nombre>]`).

    El agente de un hilo remoto corre allá, en una ventana de la sesión del telar de allá; el hilo
    local es solo la ventana desde donde se lo mira. Ver docs/propuestas/un-dueno-por-hilo.md.
    """

    nombre: str
    #: lo que va después de mosh/ssh: `usuario@servidor`, o un alias de ~/.ssh/config.
    destino: str
    transporte: str = "mosh"
    #: la carpeta del repositorio EN la otra máquina; ahí se traducen los vínculos.
    raiz: str = "~"
    #: la casilla (Maildir) común con todos los correos entre agentes, si el servidor la
    #: publica; sin ella, las conversaciones son solo las de la Maildir propia.
    #: de cuando el panel leía la casilla común por ssh (se retiró): se acepta y no se usa
    correo_archivo: str = ""
    #: la carpeta común donde cada persona publica sus hilos de esa máquina (`telar
    #: directorio`); sin ella, no se publica ni se lee nada.
    directorio: str = ""
    #: los repositorios que viven en las dos máquinas (`~/repo/empresa`): antes de llevar un
    #: hilo allá se revisa que no tengan trabajo sin subir, además de la raíz.
    repos: tuple[str, ...] = ()
    #: la sesión del telar EN la otra máquina, donde nacen sus hilos; "" es la misma que aquí.
    sesion: str = ""


@dataclass(frozen=True, slots=True)
class Puerta:
    """Lo que queda de `[enlace]`, de cuando había una puerta por ssh entre las máquinas (se retiró: lo hace
    el bus): `entrada` y `no_leer` todavía valen, y `[bus] entrada` y `[bus] no_leer` los reemplazan."""

    entrada: str = "~/telar-entrada"
    no_leer: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Config:
    """La configuración resuelta. Inmutable; para variarla, `dataclasses.replace`."""

    #: "tmux", el único (zellij se dejó de soportar en la 0.3).
    multiplexor: str = "tmux"
    #: nombre de la sesión del multiplexor que telar teje.
    sesion: str = "telar"
    #: raíz del repositorio de trabajo: de ahí sale el perfil y ahí viven los hilos.
    raiz: Path = field(default_factory=Path.cwd)
    #: dónde viven los agentes residentes (`[agentes] carpeta`), relativa a la raíz; "" es que no hay.
    agentes_carpeta: str = ""
    #: lo que un agente agrega a lo que telar descubre (`[agentes.<carpeta>] hilos/home/argumentos`).
    agentes_extra: tuple[AgenteExtra, ...] = ()
    #: una conversación de agente que pesa más que esto (MB) no se retoma: se empieza otra. 0: siempre.
    agentes_rotar_mb: int = 0
    #: en qué máquina de [remotos] viven los agentes (`[agentes] en`): encargar se hace allá. "" es esta.
    agentes_en: str = ""
    #: el agente que recibe los pendientes sin proyecto (`[agentes] sin_proyecto`); "" abre un hilo nuevo.
    agentes_sin_proyecto: str = ""
    #: cómo se abre aquí el hilo de un agente: «sesion» (una sesión tmux propia, como en un servidor) o
    #: «tab» (un hilo más de la lista, como en el laptop).
    agentes_abrir: str = "sesion"
    #: el bus entre máquinas (`[bus]`); sin url, telar trabaja solo con esta máquina.
    bus: Bus = field(default_factory=Bus)
    #: en qué máquina de [remotos] viven los procesos periódicos (`[periodicos] en`); "" es esta.
    periodicos_en: str = ""
    #: lo que dejan las skills por día, para verlo en el dashboard (`[resultados.<clave>]`).
    resultados: tuple[Resultado, ...] = ()
    #: dónde viven los objetos de cada tipo (`[tipos.<clave>]`): las tareas, por ejemplo.
    tipos: tuple[Tipo, ...] = ()
    #: las notas de los eventos del día (`[notas]`).
    notas: Notas = field(default_factory=Notas)
    #: dónde escribir el estado (vínculos, prioridades, semáforo, foco). Nunca en `raiz`.
    #: Las fichas no se guardan: se leen del documento cada vez (ver docs/estado.md).
    estado: Path = field(default_factory=lambda: _estado_por_defecto())
    #: el perfil (`.telar/perfil.yaml`); por defecto, el de la raíz.
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
    #: lo que corre o manda algo solo (`[disparadores.x]`, telar.disparadores), en el orden del archivo: por un
    #: reloj, una tecla o un cambio. Los de tecla ya están sumados a `atajos`; los de reloj los suma
    #: `telar.periodicos` a lo de periodicos.toml, y los de cambio los despacha el nodo.
    disparadores: tuple = ()
    #: secciones del día llenadas por un comando (`[bloques.<clave>]`), en el orden del archivo.
    bloques: tuple[Bloque, ...] = ()
    #: qué abre cada tipo de evento de la agenda (`[agenda.<clave>]`), en el orden del archivo.
    agenda: tuple[ReglaAgenda, ...] = ()
    #: grupos propios en la lista de hilos (`[secciones.x]`), en el orden del archivo.
    secciones: tuple[Seccion, ...] = ()
    #: lo que se abre en el panel y no es un hilo (`[apps.x]`), en el orden del archivo.
    apps: tuple[App, ...] = ()
    #: las claves de `[vistas.x]`, en el orden del archivo. Cada una ya está traducida a su bloque, app,
    #: sección o resultado (ver `_con_vistas`); esto solo dice cuáles se declararon en la forma nueva.
    vistas: tuple[str, ...] = ()
    #: lo declarado a mano en las tablas que `[vistas]` reemplaza, como (tabla, clave): `telar doctor` sugiere
    #: la forma nueva. Lo que aporta un módulo no está aquí.
    vistas_de_antes: tuple[tuple[str, str], ...] = ()
    #: los módulos instalados (`[modulos.x]`, ver telar.modulos); lo que aportan ya está sumado a
    #: los bloques, las apps y los resultados.
    modulos: tuple = ()
    #: los módulos declarados que no se pudieron leer, como (nombre, por qué). Solo se llena al cargar con
    #: `tolerar_modulos=True`, que es lo que hace `telar doctor` para poder decirlo; las demás órdenes no
    #: arrancan con un módulo así (ErrorDeConfig), y aquí queda vacío.
    modulos_rotos: tuple[tuple[str, str], ...] = ()
    #: las pestañas del dashboard: en qué orden van (`orden`) y cuáles no se muestran (`ocultas`).
    #: Las que no se nombran van después, en su orden de siempre.
    dashboard_orden: tuple[str, ...] = ()
    dashboard_ocultas: tuple[str, ...] = ()
    #: máquinas donde pueden vivir hilos. Sin ninguna, no hay hilos remotos.
    remotos: tuple[Remoto, ...] = ()
    #: los repositorios de trabajo, cada uno con su perfil (`[repos.<nombre>]`). Sin ninguno, solo `raiz`.
    repos: tuple[Repo, ...] = ()
    #: lo que queda de `[enlace]` (la puerta se retiró): `entrada` y `no_leer`
    puerta: Puerta = field(default_factory=Puerta)
    #: de qué archivo salió esta configuración; None si son puros valores por defecto.
    origen: Path | None = None

    @property
    def ruta_perfil(self) -> Path:
        """El perfil declarado, o el que se espera en la raíz del repositorio."""
        from telar.perfil import NOMBRE_ARCHIVO

        return self.perfil or (self.raiz / NOMBRE_ARCHIVO)

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


def _con_modulos(datos: dict, rotos: list | None = None) -> tuple[dict, tuple]:
    """Lo que aportan los módulos (`[modulos.x]`), sumado a lo declarado a mano, para que pase por
    la misma validación: la pestaña es un `[bloques.x]`, la app un `[apps.x]`, el resultado un
    `[resultados.x]` que vive donde corren los periódicos. Los periódicos no van aquí: los suma
    `telar.periodicos` al leer `periodicos.toml`. Un nombre que ya está declarado es un error.

    Un módulo que no se puede leer (su entrada en `[modulos]` está mal, su manifiesto no se lee, o lo que
    aporta no vale o choca con algo declarado a mano) es un error, salvo que llegue `rotos`: entonces se
    deja fuera y se anota ahí (nombre, por qué), para que `telar doctor` lo diga."""
    if "modulos" not in datos:
        return datos, ()
    datos = {k: (dict(v) if isinstance(v, dict) else v) for k, v in datos.items()}
    lista = []
    for nombre, cuerpo in _tabla(datos.pop("modulos"), "modulos").items():
        try:
            m, aportes = _un_modulo(nombre, cuerpo, datos)
        except ErrorDeConfig as e:
            if rotos is None:
                raise
            rotos.append((nombre, str(e)))
            continue
        if m is None:
            continue
        for tabla, aporte in aportes.items():
            datos.setdefault(tabla, {})[nombre] = aporte
        lista.append(m)
    return datos, tuple(lista)


#: la sección de `modulo.toml` que se vuelve cada tabla de la configuración, para nombrarla en un error
_SECCION_DEL_MODULO = {"bloques": "pestana", "apps": "app", "resultados": "resultado"}


def _un_modulo(nombre: str, cuerpo: object, datos: dict) -> tuple[object, dict]:
    """Un `[modulos.x]`: (el módulo, lo que aporta por tabla), o (None, {}) si está apagado. Lo que aporta
    se valida aquí, solo, para que un error nombre al módulo y la sección de su `modulo.toml` (y no un
    `[bloques.x]` que nadie escribió); lo que choca con otro módulo lo ve recién la validación de todo."""
    from telar import modulos as mod_modulos

    cuerpo = _tabla(cuerpo, f"modulos.{nombre}")
    sobra = set(cuerpo) - {"carpeta", "activo"}
    if sobra:
        raise ErrorDeConfig(f"modulos.{nombre}.{sorted(sobra)[0]}: no existe")
    if not isinstance(cuerpo.get("carpeta"), str) or not cuerpo["carpeta"].strip():
        raise ErrorDeConfig(f"modulos.{nombre}.carpeta: se esperaba la carpeta del módulo")
    if not isinstance(cuerpo.get("activo", True), bool):
        raise ErrorDeConfig(f"modulos.{nombre}.activo: true o false")
    if not cuerpo.get("activo", True):
        return None, {}
    try:
        m = mod_modulos.leer(nombre, Path(cuerpo["carpeta"]))
    except mod_modulos.ErrorDeModulo as e:
        raise ErrorDeConfig(f"modulos.{e}") from None
    en = datos.get("periodicos", {}).get("en", "") if isinstance(datos.get("periodicos"), dict) else ""
    aportes = {}
    vistas = datos.get("vistas") if isinstance(datos.get("vistas"), dict) else {}
    for tabla, aporte in (("bloques", m.pestana), ("apps", {"descripcion": m.descripcion, **m.app} if m.app else {}),
                          ("resultados", {"nombre": m.nombre, **m.resultado, **({"en": en} if en else {})} if m.resultado else {})):
        if not aporte:
            continue
        # una vista con su nombre choca aunque esté en otro lugar: serían dos cosas llamadas igual
        if nombre in vistas:
            raise ErrorDeConfig(f"modulos.{nombre}: ya hay una [vistas.{nombre}] declarada a mano")
        if isinstance(datos.get(tabla), dict) and nombre in datos[tabla]:
            raise ErrorDeConfig(f"modulos.{nombre}: ya hay un [{tabla}.{nombre}] declarado a mano")
        try:
            desde_dict({tabla: {nombre: aporte}})
        except ErrorDeConfig as e:
            raise ErrorDeConfig(f"modulos.{nombre}: la [{_SECCION_DEL_MODULO[tabla]}] de su modulo.toml no vale: {e}") from None
        aportes[tabla] = aporte
    return m, aportes


# ── las vistas (`[vistas.<clave>]`) ─────────────────────────────────────────────────

#: las tablas que `[vistas]` reemplaza (docs/propuestas/vistas.md). Se siguen leyendo; `telar doctor` sugiere
#: la forma nueva.
TABLAS_DE_ANTES = ("bloques", "apps", "secciones", "resultados")

#: dónde puede aparecer una vista (`aparece`) y a qué tabla de antes se traduce
LUGARES_DE_VISTA = {"pestana": "bloques", "plan": "bloques", "apps": "apps", "hilos": "secciones",
                    "dia": "resultados"}

#: las claves que acepta una vista en cada lugar, además de `aparece` y `nombre`
_CLAVES_DE_VISTA = {
    "pestana": {"comando", "color", "tecla"},
    "plan": {"comando", "color", "tecla"},
    "apps": {"comando", "archivo", "url", "memoria", "descripcion"},
    "hilos": {"hilos", "comando"},
    "dia": {"carpeta", "en", "comentar"},
}

#: las claves que dejan un solo lugar posible: con una de ellas, `aparece` se puede callar. `comando` no está
#: porque sirve en cuatro lugares (docs/propuestas/vistas.md, decisión 2), ni `color` y `tecla`, que sirven en dos.
_LUGAR_POR_FUENTE = {"archivo": "apps", "url": "apps", "memoria": "apps", "descripcion": "apps",
                     "hilos": "hilos", "carpeta": "dia", "en": "dia", "comentar": "dia"}


def _lugar_de_vista(clave: str, cuerpo: dict) -> str:
    """Dónde aparece una vista: lo que dice `aparece`, o el único lugar que deja su fuente."""
    if "aparece" in cuerpo:
        aparece = cuerpo["aparece"]
        if not isinstance(aparece, str) or aparece not in LUGARES_DE_VISTA:
            raise ErrorDeConfig(f"vistas.{clave}.aparece: pestana, plan, apps, hilos o dia; llegó {aparece!r}")
        return aparece
    # sin `aparece`, `en` la haría un resultado por día y el error culparía a la fuente (decisión 8)
    fuente = next((f for f in ("comando", "archivo", "url") if f in cuerpo), None)
    if "en" in cuerpo and fuente:
        raise ErrorDeConfig(f"vistas.{clave}.en: no va con {fuente}: en es la máquina donde vive la fuente, y un"
                            f" {fuente} todavía no puede vivir en otra")
    lugares = sorted({_LUGAR_POR_FUENTE[k] for k in cuerpo if k in _LUGAR_POR_FUENTE})
    if len(lugares) == 1:
        return lugares[0]
    if len(lugares) > 1:
        raise ErrorDeConfig(f"vistas.{clave}: sus claves son de lugares distintos ({' y '.join(lugares)}): "
                            "di cuál con aparece")
    if "comando" in cuerpo:
        raise ErrorDeConfig(f"vistas.{clave}.aparece: con comando, di dónde aparece: pestana, plan, apps o hilos")
    raise ErrorDeConfig(f"vistas.{clave}: falta qué muestra (comando, archivo, url, hilos o carpeta)")


def _traducir_vista(clave: str, cuerpo: object) -> tuple[str, dict]:
    """Una `[vistas.x]` como la entrada de la tabla de antes que la reemplaza: (tabla, cuerpo). Solo se copian
    las claves que vinieron, así los valores por defecto son los de esa tabla. La validación de cada valor es
    la de la tabla de antes (en `desde_dict`); aquí, lo que es propio de la vista."""
    cuerpo = _tabla(cuerpo, f"vistas.{clave}")
    lugar = _lugar_de_vista(clave, cuerpo)
    validas = _CLAVES_DE_VISTA[lugar] | {"aparece", "nombre"}
    sobra = sorted(set(cuerpo) - validas)
    if sobra:
        todas = set().union(*_CLAVES_DE_VISTA.values()) | {"aparece", "nombre"}
        if sobra[0] in todas:
            raise ErrorDeConfig(f"vistas.{clave}.{sobra[0]}: no va con aparece = \"{lugar}\"")
        raise ErrorDeConfig(f"vistas.{clave}.{sobra[0]}: no existe")
    # lo que vale en `comando` lo dice la tabla de antes (`comando`, `pagina` o `home`), así una forma y la otra
    # aceptan lo mismo; su error se renombra en `_con_vistas`
    if "comando" not in cuerpo and lugar in ("pestana", "plan"):
        raise ErrorDeConfig(f"vistas.{clave}: falta comando, el que imprime la página")
    if lugar == "apps":
        fuentes = [f for f in ("comando", "archivo", "url") if cuerpo.get(f)]
        if len(fuentes) != 1:
            raise ErrorDeConfig(f"vistas.{clave}: se esperaba una sola de comando, archivo o url"
                                + (f", llegaron {' y '.join(fuentes)}" if fuentes else ""))
    copia = {k: v for k, v in cuerpo.items() if k != "aparece"}
    if lugar == "plan":
        copia["en"] = "plan"
    elif lugar == "apps" and "comando" in copia:
        copia["pagina"] = copia.pop("comando")
    elif lugar == "hilos" and "comando" in copia:
        copia["home"] = copia.pop("comando")
    return LUGARES_DE_VISTA[lugar], copia


def _con_vistas(datos: dict) -> tuple[dict, tuple[str, ...]]:
    """Las `[vistas.x]`, traducidas a las tablas de antes (`[bloques]`, `[apps]`, `[secciones]`,
    `[resultados]`) para que el resto de telar no cambie: (los datos con ellas sumadas, sus claves). En cada
    tabla van después de lo declarado ahí a mano, en el orden del archivo. Un nombre que está en las dos
    formas es un error. `datos["vistas"]` se deja: así un módulo que choca con una vista lo dice
    (`_un_modulo`)."""
    if "vistas" not in datos:
        return datos, ()
    tabla = _tabla(datos["vistas"], "vistas")
    datos = {k: (dict(v) if isinstance(v, dict) else v) for k, v in datos.items()}
    for clave, cuerpo in tabla.items():
        for antes in TABLAS_DE_ANTES:
            if isinstance(datos.get(antes), dict) and clave in datos[antes]:
                raise ErrorDeConfig(f"vistas.{clave}: también está declarada como [{antes}.{clave}]: deja una sola"
                                    f" (la forma nueva es [vistas.{clave}])")
    for clave, cuerpo in tabla.items():
        destino, traducida = _traducir_vista(clave, cuerpo)
        try:
            desde_dict({destino: {clave: traducida}})
        except ErrorDeConfig as e:
            dice = str(e)
            for antes in ("pagina", "home"):  # las claves que la traducción renombró
                dice = dice.replace(f"{destino}.{clave}.{antes}:", f"{destino}.{clave}.comando:", 1)
            raise ErrorDeConfig(dice.replace(f"{destino}.{clave}", f"vistas.{clave}", 1)) from None
        if not isinstance(datos.get(destino), dict):
            datos[destino] = {}
        datos[destino][clave] = traducida
    return datos, tuple(tabla)


def _con_disparadores(datos: dict) -> tuple[dict, tuple]:
    """Los `[disparadores.x]`, leídos (telar.disparadores), y los de tecla traducidos a `[atajos.<tecla>]` para que
    el resto de telar no cambie: (los datos con ellos sumados, todos los disparadores). Van después de los atajos
    declarados a mano. Una tecla en las dos formas es un error; los errores nombran el disparador."""
    if "disparadores" not in datos:
        return datos, ()
    from telar import disparadores as mod_disparadores

    lista = mod_disparadores.leer(datos["disparadores"])
    teclas = [d for d in lista if d.tipo == "tecla" and d.activo]
    if not teclas:
        return datos, lista
    datos = dict(datos)
    atajos = dict(_tabla(datos.get("atajos", {}), "atajos"))
    for d in teclas:
        if d.tecla in atajos:
            raise ErrorDeConfig(f"disparadores.{d.nombre}.tecla: «{d.tecla}» también está en [atajos.{d.tecla}]: deja"
                                f" una sola (la forma nueva es [disparadores.{d.nombre}])")
        cuerpo = d.atajo()
        try:
            desde_dict({"atajos": {d.tecla: cuerpo}})
        except ErrorDeConfig as e:
            dice = str(e)
            for antes, ahora in (("en", "aparece"), ("nombre", "hilo")):  # las claves que la traducción renombró
                dice = dice.replace(f"atajos.{d.tecla}.{antes}:", f"atajos.{d.tecla}.{ahora}:", 1)
            raise ErrorDeConfig(dice.replace(f"atajos.{d.tecla}", f"disparadores.{d.nombre}", 1)) from None
        atajos[d.tecla] = cuerpo
    datos["atajos"] = atajos
    return datos, lista


def como_vista(tabla: str, cosa) -> dict:
    """La `[vistas.x]` que reemplaza a un bloque, una app, una sección o un resultado ya leídos: lo que
    `telar doctor` sugiere. Solo trae lo que no es el valor por defecto; leída de vuelta, da lo mismo."""
    d: dict = {}
    if tabla == "bloques":
        d["aparece"] = "plan" if cosa.en == "plan" else "pestana"
        d["comando"] = list(cosa.comando)
        if cosa.color != "cian":
            d["color"] = cosa.color
        if cosa.tecla:
            d["tecla"] = cosa.tecla
    elif tabla == "apps":
        d["aparece"] = "apps"
        if cosa.pagina:
            d["comando"] = list(cosa.pagina)
        for campo in ("archivo", "url", "memoria", "descripcion"):
            if getattr(cosa, campo):
                d[campo] = getattr(cosa, campo)
        for campo in ("archivo", "memoria"):  # al leerla se expandió `~`: se devuelve, así no queda atada a esta máquina
            if campo in d:
                d[campo] = _con_tilde(d[campo])
    elif tabla == "secciones":
        d["aparece"] = "hilos"
        d["hilos"] = list(cosa.hilos)
        if cosa.home:
            d["comando"] = list(cosa.home)
    elif tabla == "resultados":
        d["aparece"] = "dia"
        for campo in ("carpeta", "en"):
            if getattr(cosa, campo):
                d[campo] = getattr(cosa, campo)
        if cosa.comentar:
            d["comentar"] = list(cosa.comentar)
    else:
        raise ValueError(f"[{tabla}] no es una de las tablas que reemplaza [vistas]")
    # un resultado no cae a su clave cuando no tiene nombre (queda ""), así que ahí el nombre se dice siempre
    if cosa.nombre and (cosa.nombre != cosa.clave or tabla == "resultados"):
        d = {"nombre": cosa.nombre, **d}
    return d


def _con_tilde(ruta: str) -> str:
    """Una ruta bajo la carpeta del usuario, escrita con `~`."""
    casa = str(Path.home())
    if ruta == casa or ruta.startswith(casa.rstrip("/") + "/"):
        return "~" + ruta[len(casa.rstrip("/")):]
    return ruta


def vista_en_toml(clave: str, vista: dict) -> str:
    """Una `[vistas.x]` escrita en TOML, para copiarla a la configuración."""
    return "\n".join([f"[vistas.{clave_toml(clave)}]", *(f"{k} = {_valor_toml(v)}" for k, v in vista.items())])


def clave_toml(clave: str) -> str:
    """Una clave como va en la cabeza de una tabla TOML: tal cual si es simple, entre comillas si no."""
    return clave if re.fullmatch(r"[A-Za-z0-9_-]+", clave) else _cadena_toml(clave)


def desde_dict(datos: dict, *, origen: Path | None = None, rotos: list | None = None) -> Config:
    """Arma una `Config` desde el TOML ya parseado, validando lo que llegó. Con `rotos`, un módulo que no se
    puede leer se deja fuera y se anota en `modulos_rotos` en vez de ser un error (ver `cargar`)."""
    base = Config()
    rotos = None if rotos is None else list(rotos)
    de_antes = tuple((t, k) for t in TABLAS_DE_ANTES if isinstance(datos.get(t), dict) for k in datos[t])
    datos, vistas = _con_vistas(datos)
    datos, modulos = _con_modulos(datos, rotos)
    datos, disparadores = _con_disparadores(datos)
    cambios: dict[str, object] = {"origen": origen, "modulos": modulos, "modulos_rotos": tuple(rotos or ()),
                                  "vistas": vistas, "vistas_de_antes": de_antes, "disparadores": disparadores}

    if "multiplexor" in datos:
        mux = datos["multiplexor"]
        if mux == "zellij":
            raise ErrorDeConfig("multiplexor: zellij se dejó de soportar en la 0.3 (lo central de telar es de tmux): "
                                "usa multiplexor = \"tmux\", o borra la línea")
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
        sobra = set(tabla) - {"nombre", "carpeta", "reunion", "minuta", "proyecto", "pendiente", "pendiente_nuevo", "contexto", "max_vivos", "sordina"}
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
        minuta = tabla.get("minuta", MINUTA_POR_DEFECTO)
        if not isinstance(minuta, str) or not minuta.strip():
            raise ErrorDeConfig(f"agente.minuta: se esperaba un texto, llegó {minuta!r}")
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
        sordina = tabla.get("sordina", True)
        if not isinstance(sordina, bool):
            raise ErrorDeConfig(f"agente.sordina: se esperaba true o false, llegó {sordina!r}")
        max_vivos = tabla.get("max_vivos", 0)
        if not isinstance(max_vivos, int) or isinstance(max_vivos, bool) or max_vivos < 0:
            raise ErrorDeConfig(f"agente.max_vivos: se esperaba un número desde 0, llegó {max_vivos!r}")
        cambios["agente"] = Agente(nombre=nombre.strip(), carpeta=carpeta.strip(), reunion=reunion.strip(),
                                   minuta=minuta.strip(), proyecto=proyecto.strip(), contexto=contexto,
                                   max_vivos=max_vivos, sordina=sordina, **textos)

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
            sobra = set(cuerpo) - {"nombre", "mensaje", "descripcion", "en", "agente"}
            if sobra:
                raise ErrorDeConfig(f"atajos.{tecla}.{sorted(sobra)[0]}: no existe")
            campos = {}
            en = cuerpo.get("en", "hoy")
            if not isinstance(en, str) or not en.strip():
                raise ErrorDeConfig(f"atajos.{tecla}.en: «hoy», la clave de un bloque o «seccion:<clave>», llegó {en!r}")
            campos["en"] = en.strip()
            for clave in ("nombre", "mensaje", "descripcion", "agente"):
                valor = cuerpo.get(clave, "")
                if not isinstance(valor, str) or (clave not in ("descripcion", "agente") and not valor.strip()):
                    raise ErrorDeConfig(f"atajos.{tecla}.{clave}: se esperaba un texto, llegó {valor!r}")
                campos[clave] = valor.strip()
            atajos.append(Atajo(tecla=tecla, **campos))
        cambios["atajos"] = tuple(atajos)

    if "bloques" in datos:
        tabla = _tabla(datos["bloques"], "bloques")
        bloques = []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"bloques.{clave}")
            sobra = set(cuerpo) - {"nombre", "comando", "color", "en", "tecla"}
            if sobra:
                raise ErrorDeConfig(f"bloques.{clave}.{sorted(sobra)[0]}: no existe")
            comando = cuerpo.get("comando", [])
            if not isinstance(comando, list) or not comando or not all(isinstance(x, str) and x for x in comando):
                raise ErrorDeConfig(f"bloques.{clave}.comando: se esperaba una lista de palabras, llegó {comando!r}")
            color = cuerpo.get("color", "cian")
            if color not in ("azul", "amarillo", "verde", "rojo", "magenta", "cian", "violeta"):
                raise ErrorDeConfig(f"bloques.{clave}.color: azul, amarillo, verde, rojo, magenta, cian o violeta")
            nombre = cuerpo.get("nombre", clave)
            if not isinstance(nombre, str) or not nombre.strip():
                raise ErrorDeConfig(f"bloques.{clave}.nombre: se esperaba un texto")
            en = cuerpo.get("en", "")
            if en not in ("", "plan"):
                raise ErrorDeConfig(f"bloques.{clave}.en: «plan», o nada para una pestaña propia; llegó {en!r}")
            tecla = cuerpo.get("tecla", "")
            if not isinstance(tecla, str) or len(tecla) > 1:
                raise ErrorDeConfig(f"bloques.{clave}.tecla: se esperaba una letra, llegó {tecla!r}")
            bloques.append(Bloque(clave=clave, nombre=nombre.strip(), comando=tuple(comando), color=color,
                                  en=en, tecla=tecla))
        cambios["bloques"] = tuple(bloques)

    if "agenda" in datos:
        tabla = _tabla(datos["agenda"], "agenda")
        reglas = []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"agenda.{clave}")
            sobra = set(cuerpo) - {"si", "antes", "despues"}
            if sobra:
                raise ErrorDeConfig(f"agenda.{clave}.{sorted(sobra)[0]}: no existe")
            si = cuerpo.get("si", "")
            if not isinstance(si, str) or not si.strip():
                raise ErrorDeConfig(f"agenda.{clave}.si: se esperaba una expresión para el título")
            try:
                re.compile(si)
            except re.error as e:
                raise ErrorDeConfig(f"agenda.{clave}.si: no es una expresión regular ({e})") from None
            textos = {}
            for campo in ("antes", "despues"):
                valor = cuerpo.get(campo, "")
                if not isinstance(valor, str):
                    raise ErrorDeConfig(f"agenda.{clave}.{campo}: se esperaba un texto")
                textos[campo] = valor.strip()
            if not any(textos.values()):
                raise ErrorDeConfig(f"agenda.{clave}: falta antes o despues")
            reglas.append(ReglaAgenda(clave=clave, si=si, **textos))
        cambios["agenda"] = tuple(reglas)

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

    if "apps" in datos:
        tabla = _tabla(datos["apps"], "apps")
        apps = []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"apps.{clave}")
            sobra = set(cuerpo) - {"nombre", "descripcion", "pagina", "archivo", "url", "memoria"}
            if sobra:
                raise ErrorDeConfig(f"apps.{clave}.{sorted(sobra)[0]}: no existe")
            textos = {}
            for campo in ("nombre", "descripcion", "archivo", "url", "memoria"):
                v = cuerpo.get(campo, "")
                if not isinstance(v, str):
                    raise ErrorDeConfig(f"apps.{clave}.{campo}: se esperaba un texto, llegó {v!r}")
                textos[campo] = v.strip()
            pagina = cuerpo.get("pagina", [])
            if not isinstance(pagina, list) or not all(isinstance(x, str) and x.strip() for x in pagina):
                raise ErrorDeConfig(f"apps.{clave}.pagina: se esperaba una lista de textos (el comando), llegó {pagina!r}")
            fuentes = [f for f in ("pagina", "archivo", "url") if (pagina if f == "pagina" else textos[f])]
            if len(fuentes) != 1:
                raise ErrorDeConfig(f"apps.{clave}: se esperaba una sola de pagina, archivo o url"
                                    + (f", llegaron {' y '.join(fuentes)}" if fuentes else ""))
            for campo, fin in (("archivo", ".html"), ("memoria", ".json")):
                if textos[campo]:
                    textos[campo] = str(Path(textos[campo]).expanduser())
                    if not textos[campo].endswith(fin) or not Path(textos[campo]).is_absolute():
                        raise ErrorDeConfig(f"apps.{clave}.{campo}: se esperaba la ruta absoluta de un {fin}")
            if textos["memoria"] and not textos["archivo"]:
                raise ErrorDeConfig(f"apps.{clave}.memoria: solo vale con archivo")
            if textos["url"] and not textos["url"].startswith(("http://", "https://")):
                raise ErrorDeConfig(f"apps.{clave}.url: se esperaba http:// o https://")
            apps.append(App(clave=clave, nombre=textos["nombre"] or clave, descripcion=textos["descripcion"],
                            pagina=tuple(pagina), archivo=textos["archivo"], url=textos["url"],
                            memoria=textos["memoria"]))
        cambios["apps"] = tuple(apps)

    if "repos" in datos:
        tabla = _tabla(datos["repos"], "repos")
        repos_ = []
        for nombre, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"repos.{nombre}")
            sobra = set(cuerpo) - {"ruta", "perfil"}
            if sobra:
                raise ErrorDeConfig(f"repos.{nombre}.{sorted(sobra)[0]}: no existe")
            ruta = cuerpo.get("ruta", "")
            if not isinstance(ruta, str) or not ruta.strip():
                raise ErrorDeConfig(f"repos.{nombre}.ruta: se esperaba la carpeta del repositorio, llegó {ruta!r}")
            perfil_ = cuerpo.get("perfil", "")
            if not isinstance(perfil_, str):
                raise ErrorDeConfig(f"repos.{nombre}.perfil: se esperaba la ruta de un perfil, llegó {perfil_!r}")
            repos_.append(Repo(nombre=nombre, ruta=Path(os.path.expanduser(ruta.strip())), perfil=perfil_.strip()))
        cambios["repos"] = tuple(repos_)

    if "remotos" in datos:
        tabla = _tabla(datos["remotos"], "remotos")
        remotos = []
        for nombre, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"remotos.{nombre}")
            sobra = set(cuerpo) - {"destino", "transporte", "raiz", "correo_archivo", "directorio", "repos", "sesion"}
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
            sesion = cuerpo.get("sesion", "")
            if not isinstance(sesion, str) or any(c in sesion for c in ".:"):
                raise ErrorDeConfig(f"remotos.{nombre}.sesion: se esperaba el nombre de una sesión tmux, llegó {sesion!r}")
            remotos.append(Remoto(nombre=nombre, destino=destino.strip(), transporte=transporte, repos=tuple(x.strip() for x in repos),
                                  raiz=raiz.strip().rstrip("/") or "/", correo_archivo=archivo.strip(),
                                  directorio=directorio.strip().rstrip("/"), sesion=sesion.strip()))
        cambios["remotos"] = tuple(remotos)

    # `[enlaces.*]`: las máquinas a las que esta llamaba por la puerta. La puerta se retiró (lo hace el bus):
    # se acepta y no se usa, para que una configuración de antes siga cargando
    if "enlaces" in datos:
        _tabla(datos["enlaces"], "enlaces")

    if "enlace" in datos:
        cuerpo = _tabla(datos["enlace"], "enlace")
        # `verbos` era de la puerta (se retiró): se acepta y no se usa
        sobra = set(cuerpo) - {"entrada", "verbos", "no_leer"}
        if sobra:
            raise ErrorDeConfig(f"enlace.{sorted(sobra)[0]}: no existe")
        entrada = cuerpo.get("entrada", Puerta().entrada)
        if not isinstance(entrada, str) or not entrada.strip():
            raise ErrorDeConfig(f"enlace.entrada: se esperaba una carpeta, llegó {entrada!r}")
        no_leer = cuerpo.get("no_leer", [])
        if not isinstance(no_leer, list) or not all(isinstance(v, str) for v in no_leer):
            raise ErrorDeConfig(f"enlace.no_leer: se esperaba una lista de patrones, llegó {no_leer!r}")
        cambios["puerta"] = Puerta(entrada=entrada.strip().rstrip("/") or "/",
                                   no_leer=tuple(v.strip() for v in no_leer if v.strip()))

    if "agentes" in datos:
        tabla = _tabla(datos["agentes"], "agentes")
        carpeta = tabla.get("carpeta", "")
        if not isinstance(carpeta, str):
            raise ErrorDeConfig(f"agentes.carpeta: se esperaba una carpeta, llegó {carpeta!r}")
        en = tabla.get("en", "")
        if not isinstance(en, str):
            raise ErrorDeConfig(f"agentes.en: se esperaba el nombre de un remoto, llegó {en!r}")
        cambios["agentes_en"] = en.strip()
        sin_proyecto = tabla.get("sin_proyecto", "")
        if not isinstance(sin_proyecto, str):
            raise ErrorDeConfig(f"agentes.sin_proyecto: se esperaba la carpeta de un agente, llegó {sin_proyecto!r}")
        cambios["agentes_sin_proyecto"] = sin_proyecto.strip()
        abrir = tabla.get("abrir", "sesion")
        if abrir not in ("sesion", "tab"):
            raise ErrorDeConfig(f"agentes.abrir: «sesion» o «tab», llegó {abrir!r}")
        cambios["agentes_abrir"] = abrir
        rotar = tabla.get("rotar_mb", 0)
        if not isinstance(rotar, int) or isinstance(rotar, bool) or rotar < 0:
            raise ErrorDeConfig(f"agentes.rotar_mb: se esperaba un número de MB desde 0, llegó {rotar!r}")
        extras = []
        for clave, cuerpo in tabla.items():
            if clave in ("carpeta", "rotar_mb", "en", "sin_proyecto", "abrir"):
                continue
            cuerpo = _tabla(cuerpo, f"agentes.{clave}")
            sobra = set(cuerpo) - {"hilos", "home", "argumentos", "en"}
            if sobra:
                raise ErrorDeConfig(f"agentes.{clave}.{sorted(sobra)[0]}: no existe")
            en_agente = cuerpo.get("en", "")
            if not isinstance(en_agente, str):
                raise ErrorDeConfig(f"agentes.{clave}.en: «aqui», un remoto o un enlace, llegó {en_agente!r}")
            for campo in ("hilos", "home", "argumentos"):
                valor = cuerpo.get(campo, [])
                if not isinstance(valor, list) or not all(isinstance(x, str) and x.strip() for x in valor):
                    raise ErrorDeConfig(f"agentes.{clave}.{campo}: se esperaba una lista de textos, llegó {valor!r}")
            extras.append(AgenteExtra(clave=clave, hilos=tuple(x.strip() for x in cuerpo.get("hilos", [])),
                                      home=tuple(cuerpo.get("home", [])), argumentos=tuple(cuerpo.get("argumentos", [])),
                                      en=en_agente.strip()))
        cambios["agentes_carpeta"] = carpeta.strip()
        cambios["agentes_extra"] = tuple(extras)
        cambios["agentes_rotar_mb"] = rotar

    if "bus" in datos:
        cuerpo = _tabla(datos["bus"], "bus")
        sobra = set(cuerpo) - {"url", "token", "persona", "maquina", "no_leer", "entrada"}
        if sobra:
            raise ErrorDeConfig(f"bus.{sorted(sobra)[0]}: no existe")
        valores = {}
        no_leer_bus = cuerpo.get("no_leer", [])
        if not isinstance(no_leer_bus, list) or not all(isinstance(v, str) for v in no_leer_bus):
            raise ErrorDeConfig(f"bus.no_leer: se esperaba una lista de patrones, llegó {no_leer_bus!r}")
        valores["no_leer"] = tuple(v.strip() for v in no_leer_bus if v.strip())
        entrada_bus = cuerpo.get("entrada", "")
        if not isinstance(entrada_bus, str):
            raise ErrorDeConfig(f"bus.entrada: se esperaba una carpeta, llegó {entrada_bus!r}")
        valores["entrada"] = entrada_bus.strip()
        for clave in ("url", "token", "persona", "maquina"):
            v = cuerpo.get(clave, "")
            if not isinstance(v, str):
                raise ErrorDeConfig(f"bus.{clave}: se esperaba un texto, llegó {v!r}")
            valores[clave] = v.strip()
        if valores["url"] and not valores["url"].startswith(("nats://", "tls://")):
            raise ErrorDeConfig(f"bus.url: se esperaba nats://host:puerto, llegó {valores['url']!r}")
        cambios["bus"] = Bus(**valores)

    if "periodicos" in datos:
        cuerpo = _tabla(datos["periodicos"], "periodicos")
        sobra = set(cuerpo) - {"en"}
        if sobra:
            raise ErrorDeConfig(f"periodicos.{sorted(sobra)[0]}: no existe")
        en = cuerpo.get("en", "")
        if not isinstance(en, str):
            raise ErrorDeConfig(f"periodicos.en: se esperaba el nombre de un remoto, llegó {en!r}")
        cambios["periodicos_en"] = en.strip()

    if "dashboard" in datos:
        cuerpo = _tabla(datos["dashboard"], "dashboard")
        sobra = set(cuerpo) - {"orden", "ocultas"}
        if sobra:
            raise ErrorDeConfig(f"dashboard.{sorted(sobra)[0]}: no existe")
        for campo in ("orden", "ocultas"):
            v = cuerpo.get(campo, [])
            if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
                raise ErrorDeConfig(f"dashboard.{campo}: se esperaba una lista de pestañas, llegó {v!r}")
            cambios[f"dashboard_{campo}"] = tuple(x.strip() for x in v)

    if "resultados" in datos:
        tabla = _tabla(datos["resultados"], "resultados")
        lista = []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"resultados.{clave}")
            sobra = set(cuerpo) - {"carpeta", "en", "nombre", "comentar"}
            if sobra:
                raise ErrorDeConfig(f"resultados.{clave}.{sorted(sobra)[0]}: no existe")
            valores: dict = {}
            comentar = cuerpo.get("comentar", [])
            if not isinstance(comentar, list) or not all(isinstance(x, str) and x.strip() for x in comentar):
                raise ErrorDeConfig(f"resultados.{clave}.comentar: se esperaba una lista de palabras, llegó {comentar!r}")
            valores["comentar"] = tuple(comentar)
            for campo in ("carpeta", "en", "nombre"):
                v = cuerpo.get(campo, "")
                if not isinstance(v, str):
                    raise ErrorDeConfig(f"resultados.{clave}.{campo}: se esperaba un texto, llegó {v!r}")
                valores[campo] = v.strip()
            if not valores["carpeta"] and not valores["en"]:
                raise ErrorDeConfig(f"resultados.{clave}: falta carpeta o en")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", clave):
                raise ErrorDeConfig(f"resultados.{clave}: la clave va en minúsculas, sin espacios")
            lista.append(Resultado(clave=clave, **valores))
        cambios["resultados"] = tuple(lista)

    if "tipos" in datos:
        tabla = _tabla(datos["tipos"], "tipos")
        lista_tipos = []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"tipos.{clave}")
            sobra = set(cuerpo) - {"carpeta", "formato", "en"}
            if sobra:
                raise ErrorDeConfig(f"tipos.{clave}.{sorted(sobra)[0]}: no existe")
            valores = {}
            for campo in ("carpeta", "formato", "en"):
                v = cuerpo.get(campo, "")
                if not isinstance(v, str):
                    raise ErrorDeConfig(f"tipos.{clave}.{campo}: se esperaba un texto, llegó {v!r}")
                valores[campo] = v.strip()
            valores["formato"] = valores["formato"] or "archivo"
            if clave != "tarea":
                raise ErrorDeConfig(f"tipos.{clave}: telar conoce el tipo «tarea»")
            if valores["formato"] != "archivo":
                raise ErrorDeConfig(f"tipos.{clave}.formato: por ahora, «archivo»")
            if not valores["carpeta"] and not valores["en"]:
                raise ErrorDeConfig(f"tipos.{clave}: falta carpeta o en")
            lista_tipos.append(Tipo(clave=clave, **valores))
        cambios["tipos"] = tuple(lista_tipos)

    if "notas" in datos:
        cuerpo = _tabla(datos["notas"], "notas")
        sobra = set(cuerpo) - {"carpeta", "en"}
        if sobra:
            raise ErrorDeConfig(f"notas.{sorted(sobra)[0]}: no existe")
        valores = {}
        for campo in ("carpeta", "en"):
            v = cuerpo.get(campo, "")
            if not isinstance(v, str):
                raise ErrorDeConfig(f"notas.{campo}: se esperaba un texto, llegó {v!r}")
            valores[campo] = v.strip()
        cambios["notas"] = Notas(**valores)

    desconocidas = set(datos) - {
        "multiplexor", "sesion", "raiz", "estado", "perfil", "intervalos", "proveedores",
        "ficha", "agente", "hilos", "atajos", "secciones", "apps", "dashboard", "remotos", "bloques", "agenda",
        "enlaces", "enlace", "periodicos", "agentes", "bus", "resultados", "notas", "equipo",  # `equipo`: lo lee telar.equipo
        "tipos", "repos", "vistas",  # `vistas`: ya traducidas por _con_vistas
        "disparadores",  # leídos por _con_disparadores
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


def cargar(ruta: Path | None = None, *, tolerar_modulos: bool = False) -> Config:
    """Lee la configuración. Sin archivo, devuelve los valores por defecto.

    `ruta` explícita manda sobre `$TELAR_CONFIG`; si esa ruta no existe, es un
    error, porque alguien la pidió a propósito.

    Un módulo declarado que no se puede leer (su carpeta o su `modulo.toml` no están, o el manifiesto
    está mal, o `modulos.toml` no se lee) es un error. Con `tolerar_modulos`, se deja fuera y queda
    anotado en `modulos_rotos`: así carga `telar doctor`, que tiene que poder decir qué está mal.
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

    rotos: list | None = [] if tolerar_modulos else None
    datos = _con_instalados(datos, destino, rotos)
    return _entorno(desde_dict(datos, origen=destino, rotos=rotos))


def _con_instalados(datos: dict, destino: Path, rotos: list | None = None) -> dict:
    """Los módulos que instaló `telar modulo` (`modulos.toml`, al lado), junto a los `[modulos]` a mano.
    Con `rotos`, un `modulos.toml` que no se lee se anota ahí (y quedan solo los de a mano)."""
    from telar import modulos as mod_modulos

    try:
        instalados = mod_modulos.leer_instalados(destino.parent / mod_modulos.INSTALADOS)
    except mod_modulos.ErrorDeModulo as e:
        if rotos is None:
            raise ErrorDeConfig(str(e)) from None
        rotos.append((mod_modulos.INSTALADOS, str(e)))
        instalados = {}
    if not instalados:
        return datos
    a_mano = datos.get("modulos", {}) if isinstance(datos.get("modulos"), dict) else {}
    juntos = dict(a_mano)
    for nombre, d in instalados.items():
        if nombre in a_mano:
            mensaje = f"modulos.{nombre}: está en la configuración y también instalado con telar modulo"
            if rotos is None:
                raise ErrorDeConfig(mensaje)
            rotos.append((nombre, mensaje))  # queda el de a mano
            continue
        juntos[nombre] = {"carpeta": str(d.get("carpeta", ""))}
    return {**datos, "modulos": juntos}


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

