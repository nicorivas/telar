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

from telar.horario import Tramo

__all__ = [
    "Intervalos",
    "Proveedor",
    "Config",
    "Mundo",
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


_DURACION = re.compile(r"(\d+(?:\.\d+)?)\s*(min|h|m|s)\s*")


def duracion(valor: object) -> float:
    """Una duración de la configuración, en segundos: «30m», «1h», «1h30m», «90s», o un número suelto (minutos). 0 (o
    «0») es nada. Lo que no se entiende levanta ValueError, con lo que llegó."""
    if isinstance(valor, bool):
        raise ValueError(f"se esperaba una duración como «30m», llegó {valor!r}")
    if isinstance(valor, (int, float)):
        if valor < 0:
            raise ValueError(f"una duración no es negativa, llegó {valor!r}")
        return float(valor) * 60
    texto = str(valor).strip().lower()
    if texto in ("", "0", "nunca", "no"):
        return 0.0
    if re.fullmatch(r"\d+(?:\.\d+)?", texto):
        return float(texto) * 60
    total, pos = 0.0, 0
    for m in _DURACION.finditer(texto):
        if m.start() != pos:
            break
        total += float(m.group(1)) * {"h": 3600, "m": 60, "min": 60, "s": 1}[m.group(2)]
        pos = m.end()
    if pos != len(texto) or pos == 0:
        raise ValueError(f"se esperaba una duración como «30m», «1h» o «90s» (0, nunca), llegó {valor!r}")
    return total


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
    #: segundos sin actividad tras los que el nodo duerme a un hilo: cierra su agente y deja su ventana, que lo retoma
    #: al abrirla o al llegarle algo (telar.dormir). 0 es nunca. Se escribe «30m», «1h», «90s» o minutos sueltos
    dormir_tras: float = 30 * 60.0


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
    #: cuántos hilos pueden estar vivos a la vez en esta máquina, si nadie mira su sesión del telar directo
    #: (un servidor); 0 es sin tope. Al abrir otro (un periódico, un encargo) se cierran los ociosos.
    max_vivos: int = 0
    #: la sordina (telar/sordina/): en Claude Code, una línea gris por archivo editado y por comando, sin
    #: diffs ni salida. La pone `telar agente instalar`; con false, no.
    sordina: bool = True


#: teclas que el dashboard ya usa (pagina/src/vistas/dashboard/panel.ts, teclasDePestanas): n (ahora), t (te esperan),
#: v (tareas), p (proyectos), r (recargar), o (periódicos), a (la agenda), c (el correo), / (buscar). Un
#: atajo con una de ellas no es un error: la pestaña le gana y el atajo queda con un clic. `telar doctor`
#: lo avisa. Las de las pestañas de bloques y proveedores se suman en cada configuración.
TECLAS_RESERVADAS = frozenset("ntvproac/")


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
    el Gantt. El comando imprime el mismo JSON que una página de sección (docs/contratos.md); telar lo
    pide con el ritmo de la red. Cada bloque es su propia pestaña, salvo que `dentro` lo haga una
    subpestaña de una de las fijas (el Gantt, dentro de «proyectos»). `en = "plan"` (arriba de la pestaña
    del plan) se retiró con esa pestaña, y lo mismo `en` o `dentro` = "estrategia": un bloque que lo dice se
    deja fuera (`Config.retirados`)."""

    clave: str
    nombre: str
    comando: tuple[str, ...]
    #: el color de la sección: azul, amarillo, verde, rojo, magenta, cian, violeta
    color: str = "cian"
    #: la tecla de su pestaña en el dashboard, si tiene una
    tecla: str = ""
    #: "" es una pestaña propia; una de `DENTRO_DE`, una subpestaña de esa: se ve al lado de su nombre, arriba
    dentro: str = ""


#: las pestañas fijas del dashboard que aceptan subpestañas (`[bloques.x] dentro`)
DENTRO_DE = ("ahora", "tareas", "proyectos", "calendario")

#: lo que un bloque decía para ir en la pestaña del plan, que se sacó del dashboard (18-nov-2026): `en = "plan"`,
#: `dentro = "plan"` o una `[vistas.x]` con `aparece = "plan"`. Un bloque así no rompe la configuración: se deja
#: fuera, y `telar doctor` lo dice (`Config.retirados`).
PESTANA_RETIRADA = "plan"
#: las pestañas fijas que se sacaron del dashboard, con cómo se nombran al avisar: el plan (18-nov-2026) y estrategia
#: (19-nov-2026; el modo estrategia sigue, y abre en proyectos). Lo que todavía las nombre (un bloque con `en` o
#: `dentro`, `[dashboard] orden` u `ocultas`, `filas` de un modo) no rompe nada: no cuenta, y `telar doctor` lo avisa.
PESTANAS_RETIRADAS = {"plan": "la pestaña del plan", "estrategia": "la pantalla estrategia"}


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
    #: quién administra el bus (su nombre en él): a esa persona van los pedidos de gestión de personas
    #: (telar.personas); vacío, esta misma persona
    administra: str = ""


@dataclass(frozen=True, slots=True)
class Resultado:
    """Lo que una skill deja por día y se quiere ver en el dashboard (`[resultados.<clave>]`, ver
    telar.resultados): un `AAAA-MM-DD.json` (o `.md`) por día en una carpeta, o `<prefijo>AAAA-MM-DD…` si declara
    uno (dos resultados en la misma carpeta: el plan del día y el resumen de la semana)."""

    clave: str
    #: la carpeta en la máquina donde vive. Con `en`, es la de respaldo si esa máquina no responde.
    carpeta: str = ""
    #: la máquina del bus donde se escribe (la que corre la skill); "" es esta.
    en: str = ""
    #: cómo se llama en el dashboard; por defecto, la clave.
    nombre: str = ""
    #: lo que va antes de la fecha en el nombre de cada archivo (`estrategia-` lee `estrategia-AAAA-MM-DD.md`);
    #: vacío, el archivo es solo la fecha
    prefijo: str = ""
    #: el comando que atiende un comentario sobre un día (lista de palabras; el texto le llega por la
    #: entrada estándar). Se declara en la máquina donde vive el resultado; vacío, no recibe comentarios.
    comentar: tuple[str, ...] = ()
    #: si cada día es una lista de pasadas (una skill que corre varias veces al día, telar.pasadas), el esquema de cada
    #: una: «pulso» o «libre»; vacío, el día es lo que la skill escriba, entero.
    pasadas: str = ""


@dataclass(frozen=True, slots=True)
class AvisoArchivo:
    """Un aviso que viene de un archivo (`[avisos.<clave>]`, telar.avisos): un programa deja en un JSON cómo está algo
    (`{"nivel": "ok|aviso|mal", "linea", "fecha", "informe", "sugerencias"}`) y la franja de avisos de la página lo
    dice cuando no está bien."""

    clave: str
    #: el JSON, en la máquina donde vive (con `~`, el de quien corre telar allá)
    archivo: str
    #: la máquina del bus donde vive el archivo; "" es esta
    en: str = ""


@dataclass(frozen=True, slots=True)
class Tipo:
    """Dónde viven los objetos de un tipo y con qué formato (`[tipos.<clave>]`, telar.tipos): una
    carpeta con un archivo por objeto. Con `en`, viven en otra máquina del bus."""

    clave: str
    carpeta: str = ""
    formato: str = "archivo"
    en: str = ""


#: dónde va la terminal dentro de su vista
POSICIONES_TERMINAL = ("izquierda", "centro", "derecha")
#: el ancho de la terminal: entre estas columnas, o 0 (todo lo que quepa)
COLUMNAS_TERMINAL = (40, 400)


@dataclass(frozen=True, slots=True)
class Terminal:
    """Cómo se ve la terminal de un hilo en la página (`[terminal]`).

    `columnas`: hasta cuántas columnas de ancho (0: todo lo que quepa); `posicion`: izquierda, centro o derecha;
    `fondo`: lo que va alrededor: «telar» (el de siempre, un telar tenue), «ninguno», un color («#1e1e2e»), una
    imagen («imagen:~/fondos/a.jpg» o «imagen:https://…») o el nombre de un módulo que trae un `[fondo]`."""

    columnas: int = 130
    posicion: str = "centro"
    fondo: str = "telar"


def validar_terminal(clave: str, valor: object) -> object:
    """Un valor de `[terminal]`, normalizado; ErrorDeConfig si no sirve."""
    if clave == "columnas":
        if isinstance(valor, str) and valor.strip().isdigit():
            valor = int(valor.strip())
        if isinstance(valor, str) and valor.strip().lower() in ("todo", "todas", "0"):
            valor = 0
        if not isinstance(valor, int) or isinstance(valor, bool) or (valor and not COLUMNAS_TERMINAL[0] <= valor <= COLUMNAS_TERMINAL[1]):
            raise ErrorDeConfig(f"terminal.columnas: un número de {COLUMNAS_TERMINAL[0]} a {COLUMNAS_TERMINAL[1]}, o 0 "
                                f"(todo el ancho); llegó {valor!r}")
        return valor
    if clave == "posicion":
        v = str(valor or "").strip().lower()
        if v not in POSICIONES_TERMINAL:
            raise ErrorDeConfig(f"terminal.posicion: {', '.join(POSICIONES_TERMINAL)}; llegó {valor!r}")
        return v
    if clave == "fondo":
        v = str(valor or "").strip()
        if not v or re.search(r"[\x00-\x1f]", v):
            raise ErrorDeConfig(f"terminal.fondo: telar, ninguno, un color #rrggbb, imagen:… o un módulo; llegó {valor!r}")
        if v.startswith("#") and not re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", v):
            raise ErrorDeConfig(f"terminal.fondo: un color va como #rgb o #rrggbb; llegó {v!r}")
        return v
    raise ErrorDeConfig(f"terminal.{clave}: no existe (columnas, posicion, fondo)")


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


#: el valor de un filtro por mundo que pide lo que no calza en ninguno (`telar esperas --mundo sin-clasificar`): un
#: mundo no puede llamarse así
SIN_CLASIFICAR = "sin-clasificar"
#: las tintas de la página que puede llevar un mundo (las de cada tema: pagina/media/css/tokens.css)
TINTAS_MUNDO = ("azul", "amarillo", "verde", "rojo", "magenta", "cian", "violeta")


@dataclass(frozen=True, slots=True)
class Mundo:
    """Una parte de la vida de la persona (`[mundos.<nombre>]`): trabajo, personal. Lo que espera a la persona y sus
    tareas dicen a cuál pertenecen, derivado de lo que se declara aquí (telar.mundos), nunca del título: el `area` de
    una tarea, o la carpeta de su proyecto, documento o hilo. El orden de las tablas es el orden en que se muestran."""

    nombre: str
    #: los valores del campo `area` de una tarea que son de este mundo
    areas: tuple[str, ...] = ()
    #: prefijos de la carpeta de un documento, un proyecto o un hilo: relativos a la raíz, o absolutos (con `~`)
    rutas: tuple[str, ...] = ()
    #: las etiquetas de un hilo (`telar hilo etiquetas`) que lo hacen de este mundo, aunque su carpeta diga otra cosa
    etiquetas: tuple[str, ...] = ()
    #: cuándo rige (telar.horario): la página lo pone sola en esas horas; vacío, solo a mano
    horario: tuple[Tramo, ...] = ()
    #: su tinta, una de las del tema (TINTAS_MUNDO); vacío, la que le toca por orden (telar.mundos.colores)
    color: str = ""
    #: los colores de la página mientras rige (uno de telar.modos.TEMAS, o uno propio de `[temas]`); vacío, los del modo
    #: puesto
    tema: str = ""
    #: los modos de la página que tiene (sus claves, telar.modos): la banda muestra solo esos mientras rige, y al entrar
    #: la página pasa al primero si el puesto no es uno de ellos; vacío, todos
    modos: tuple[str, ...] = ()
    #: el dibujo animado de su tarjeta en la ventana de mundos (la clave de un arte: uno de fábrica de la página, o un
    #: `<raiz>/.telar/arte/<clave>.txt`, telar.arte); vacío, el que le toca (el que se llama como el mundo, uno de
    #: fábrica que lo sugiere, o la órbita)
    arte: str = ""


@dataclass(frozen=True, slots=True)
class Iniciativas:
    """`[iniciativas]`: el vocabulario de estados de las iniciativas (las unidades que un modo llama así) y cómo se
    nombra cada fuente externa (telar.iniciativas). Sin `estados`, se muestra lo que diga cada ficha y no se cambia
    desde telar. De dónde sale el estado lo dice cada ficha (`estado_fuente`), no la configuración."""

    #: el vocabulario cerrado, en su orden (el de la página: el menú para cambiarlo, las cuentas)
    estados: tuple[str, ...] = ()
    #: (lo escrito, el estado del vocabulario al que vale): «activo» → «en curso»
    sinonimos: tuple[tuple[str, str], ...] = ()
    #: (estado, clase): cómo se dibuja uno cuya clase no se deduce de su nombre (telar.iniciativas.CLASES)
    clases: tuple[tuple[str, str], ...] = ()
    #: (lo que dice `estado_fuente` en una ficha, cómo se muestra): «sheet» → «Sheet»
    fuentes: tuple[tuple[str, str], ...] = ()


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
    #: a quién va, de entrada, lo que la pestaña de un módulo manda con la ventana «instrucción» sin decir a quién
    #: (`[instruccion] destino`): «agente:<nombre>» o «hilo:<nombre>»; "" la abre sin destino elegido.
    instruccion_destino: str = ""
    #: cómo se abre aquí el hilo de un agente: «sesion» (una sesión tmux propia, como en un servidor) o
    #: «tab» (un hilo más de la lista, como en el laptop).
    agentes_abrir: str = "sesion"
    #: el bus entre máquinas (`[bus]`); sin url, telar trabaja solo con esta máquina.
    bus: Bus = field(default_factory=Bus)
    #: en qué máquina de [remotos] viven los procesos periódicos (`[periodicos] en`); "" es esta.
    periodicos_en: str = ""
    #: `[catalogos]` (telar.catalogo): si se lee el oficial, y otros catálogos (URL o ruta), «sin revisar»
    catalogos_oficial: bool = True
    catalogos_fuentes: tuple[str, ...] = ()
    #: lo que dejan las skills por día, para verlo en el dashboard (`[resultados.<clave>]`).
    resultados: tuple[Resultado, ...] = ()
    #: los avisos que vienen de un archivo (`[avisos.<clave>]`, telar.avisos): la franja de la página los dice
    avisos: tuple[AvisoArchivo, ...] = ()
    #: dónde viven los objetos de cada tipo (`[tipos.<clave>]`): las tareas, por ejemplo.
    tipos: tuple[Tipo, ...] = ()
    #: las notas de los eventos del día (`[notas]`).
    notas: Notas = field(default_factory=Notas)
    #: cómo se ve la terminal de un hilo en la página (`[terminal]`).
    terminal: Terminal = field(default_factory=Terminal)
    #: los modos de la página definidos o cambiados aquí (`[modos.<n>]`, telar.modos): clave → {nombre, valores}
    modos: dict = field(default_factory=dict)
    #: los estilos de los glifos de la página (`[glifos.<n>]`, telar.glifos): estilo → sus valores
    glifos: dict = field(default_factory=dict)
    #: los colores propios de cada tema y los temas propios (`[temas.<tema>]`, telar.temas): tema → {tinta: #rrggbb} (y
    #: `base`, de uno propio). Juntos los de la raíz (`<raiz>/.telar/temas.toml`, valen en todas las máquinas) y los de esta
    #: configuración, que pisan color por color
    temas: dict = field(default_factory=dict)
    #: de dónde sale cada cosa de `temas`: tema → {"raiz": claves, "maquina": claves} (telar.temas.donde)
    temas_donde: dict = field(default_factory=dict)
    #: el archivo de los temas de la raíz, `<raiz>/.telar/temas.toml`; None si la configuración no dice `raiz`
    temas_archivo: Path | None = None
    #: por qué ese archivo no se pudo leer ("" si se leyó, o no está): se sigue sin él, y doctor lo dice
    temas_error: str = ""
    #: los temas que un modo o un mundo nombra y no hay (uno propio que se borró en otra máquina): al cargar se toleran
    #: (la página pone el del modo) y doctor lo dice; al escribir, no se deja nombrar uno nuevo que no hay
    temas_faltan: tuple[str, ...] = ()
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
    #: lo declarado para una pestaña que ya no está (la del plan, `PESTANA_RETIRADA`), como (dónde, qué decía): se
    #: deja fuera sin que la configuración falle, y `telar doctor` lo avisa.
    retirados: tuple[tuple[str, str], ...] = ()
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
    #: las partes de la vida (`[mundos]`), en el orden en que se declaran; vacío, nada dice mundo
    mundos: tuple[Mundo, ...] = ()
    #: el mundo que rige fuera de todo horario (`[mundos] fuera`); vacío, ambos (no filtra)
    mundos_fuera: str = ""
    #: el archivo de la raíz con el horario de cada mundo y `fuera` (`<raiz>/.telar/mundos.toml`, telar.mundos_raiz): vale en
    #: todas las máquinas; None sin `raiz` (todo queda en la de la máquina)
    mundos_archivo: Path | None = None
    #: por qué ese archivo no se lee ("" si se lee o no está): sus horarios no se aplican, y doctor lo dice
    mundos_error: str = ""
    #: de dónde sale el horario de cada mundo y `fuera`: {"horario": {mundo: "raiz" | "maquina"}, "fuera": "raiz" |
    #: "maquina" | ""}
    mundos_donde: dict = field(default_factory=dict)
    #: lo de la raíz que esta máquina no aplica (el horario de un mundo que no declara, un `fuera` que no es de los suyos)
    mundos_sobran: tuple[str, ...] = ()
    remotos: tuple[Remoto, ...] = ()
    #: los repositorios de trabajo, cada uno con su perfil (`[repos.<nombre>]`). Sin ninguno, solo `raiz`.
    repos: tuple[Repo, ...] = ()
    #: lo que queda de `[enlace]` (la puerta se retiró): `entrada` y `no_leer`
    puerta: Puerta = field(default_factory=Puerta)
    #: el vocabulario de estados de las iniciativas (`[iniciativas]`)
    iniciativas: Iniciativas = field(default_factory=Iniciativas)
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


def socket_serve() -> Path:
    """El socket donde escucha `telar serve` por defecto (su API, sin llave: la carpeta es solo de su dueño)."""
    base = os.environ.get("XDG_STATE_HOME")
    return (Path(base) if base else Path.home() / ".local" / "state") / "telar" / "serve" / "telar.sock"


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
_SECCION_DEL_MODULO = {"bloques": "pestana", "apps": "app", "resultados": "resultado", "proveedores": "fechas"}


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
                          ("resultados", {"nombre": m.nombre, **m.resultado, **({"en": en} if en else {})} if m.resultado else {}),
                          # su fuente de fechas es un proveedor `fechas` de tipo `comando`, que corre en su carpeta
                          ("proveedores", {"como": "fechas", "tipo": "comando", "donde": str(m.carpeta), **m.fechas}
                           if m.fechas else {})):
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
#: los lugares que se pueden pedir hoy: «plan» se sigue leyendo (se traduce a un bloque `en = "plan"`, que se deja
#: fuera y `telar doctor` avisa), pero la pestaña ya no está
LUGARES_VIGENTES = tuple(x for x in LUGARES_DE_VISTA if x != PESTANA_RETIRADA)

#: las claves que acepta una vista en cada lugar, además de `aparece` y `nombre`
_CLAVES_DE_VISTA = {
    "pestana": {"comando", "color", "tecla", "dentro"},
    "plan": {"comando", "color", "tecla"},
    "apps": {"comando", "archivo", "url", "memoria", "descripcion"},
    "hilos": {"hilos", "comando"},
    "dia": {"carpeta", "en", "comentar", "prefijo", "pasadas"},
}

#: las claves que dejan un solo lugar posible: con una de ellas, `aparece` se puede callar. `comando` no está
#: porque sirve en cuatro lugares (docs/propuestas/vistas.md, decisión 2), ni `color` y `tecla`, que sirven en dos.
_LUGAR_POR_FUENTE = {"archivo": "apps", "url": "apps", "memoria": "apps", "descripcion": "apps",
                     "hilos": "hilos", "carpeta": "dia", "en": "dia", "comentar": "dia", "prefijo": "dia",
                     "pasadas": "dia"}


def _lugar_de_vista(clave: str, cuerpo: dict) -> str:
    """Dónde aparece una vista: lo que dice `aparece`, o el único lugar que deja su fuente."""
    if "aparece" in cuerpo:
        aparece = cuerpo["aparece"]
        if not isinstance(aparece, str) or aparece not in LUGARES_DE_VISTA:
            raise ErrorDeConfig(f"vistas.{clave}.aparece: {', '.join(LUGARES_VIGENTES[:-1])} o {LUGARES_VIGENTES[-1]};"
                                f" llegó {aparece!r}")
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
        raise ErrorDeConfig(f"vistas.{clave}.aparece: con comando, di dónde aparece: pestana, apps o hilos")
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
        d["aparece"] = "pestana"
        d["comando"] = list(cosa.comando)
        if cosa.color != "cian":
            d["color"] = cosa.color
        if cosa.tecla:
            d["tecla"] = cosa.tecla
        if cosa.dentro:
            d["dentro"] = cosa.dentro
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
        for campo in ("carpeta", "en", "prefijo", "pasadas"):
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


def desde_dict(datos: dict, *, origen: Path | None = None, rotos: list | None = None,
               tolerar_temas: bool = False) -> Config:
    """Arma una `Config` desde el TOML ya parseado, validando lo que llegó. Con `rotos`, un módulo que no se
    puede leer se deja fuera y se anota en `modulos_rotos` en vez de ser un error (ver `cargar`). Con `tolerar_temas`, un
    modo o un mundo que nombra un tema propio que no hay no es un error: queda anotado en `temas_faltan` (así carga
    `cargar`; al escribir, no se tolera)."""
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
        sobra = set(tabla) - {"directorios", "tope", "dormir_tras"}
        if sobra:
            raise ErrorDeConfig(f"hilos.{sorted(sobra)[0]}: no existe")
        try:
            dormir_tras = duracion(tabla["dormir_tras"]) if "dormir_tras" in tabla else Hilos().dormir_tras
        except ValueError as e:
            raise ErrorDeConfig(f"hilos.dormir_tras: {e}") from e
        dirs = tabla.get("directorios", [])
        if not isinstance(dirs, list) or not all(isinstance(d, str) and d.strip() for d in dirs):
            raise ErrorDeConfig(f"hilos.directorios: se esperaba una lista de carpetas, llegó {dirs!r}")
        for d in dirs:
            if d.startswith("/") or ".." in Path(d).parts:
                raise ErrorDeConfig(f"hilos.directorios: «{d}» tiene que ser relativa a la raíz y no salir de ella")
        tope = tabla.get("tope", 8)
        if not isinstance(tope, int) or isinstance(tope, bool) or tope < 0:
            raise ErrorDeConfig(f"hilos.tope: se esperaba un número entero, llegó {tope!r}")
        cambios["hilos"] = Hilos(directorios=tuple(d.strip().strip("/") for d in dirs), tope=tope, dormir_tras=dormir_tras)

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
        bloques, retirados = [], []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"bloques.{clave}")
            sobra = set(cuerpo) - {"nombre", "comando", "color", "en", "tecla", "dentro"}
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
            if en not in ("", *PESTANAS_RETIRADAS):
                raise ErrorDeConfig(f"bloques.{clave}.en: ya no existe (iba arriba de la pestaña del plan, que se sacó);"
                                    f" llegó {en!r}")
            tecla = cuerpo.get("tecla", "")
            if not isinstance(tecla, str) or len(tecla) > 1:
                raise ErrorDeConfig(f"bloques.{clave}.tecla: se esperaba una letra, llegó {tecla!r}")
            dentro = cuerpo.get("dentro", "")
            if dentro not in ("", *PESTANAS_RETIRADAS, *DENTRO_DE):
                raise ErrorDeConfig(f"bloques.{clave}.dentro: {', '.join(DENTRO_DE[:-1])} o {DENTRO_DE[-1]}; llegó {dentro!r}")
            # lo que iba en una pestaña que se sacó (el plan, estrategia): fuera, sin romper nada (telar doctor lo dice)
            if en in PESTANAS_RETIRADAS or dentro in PESTANAS_RETIRADAS:
                que = f'en = "{en}"' if en else f'dentro = "{dentro}"'
                retirados.append((f"vistas.{clave}", 'aparece = "plan"' if en == PESTANA_RETIRADA else que) if clave in vistas
                                 else (f"bloques.{clave}", que))
                continue
            bloques.append(Bloque(clave=clave, nombre=nombre.strip(), comando=tuple(comando), color=color,
                                  tecla=tecla, dentro=dentro))
        cambios["bloques"] = tuple(bloques)
        cambios["retirados"] = tuple(retirados)

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
        sobra = set(cuerpo) - {"url", "token", "persona", "maquina", "administra", "no_leer", "entrada"}
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
        for clave in ("url", "token", "persona", "maquina", "administra"):
            v = cuerpo.get(clave, "")
            if not isinstance(v, str):
                raise ErrorDeConfig(f"bus.{clave}: se esperaba un texto, llegó {v!r}")
            valores[clave] = v.strip()
        if valores["url"] and not valores["url"].startswith(("nats://", "tls://")):
            raise ErrorDeConfig(f"bus.url: se esperaba nats://host:puerto, llegó {valores['url']!r}")
        cambios["bus"] = Bus(**valores)

    if "catalogos" in datos:
        cuerpo = _tabla(datos["catalogos"], "catalogos")
        sobra = set(cuerpo) - {"oficial", "fuentes"}
        if sobra:
            raise ErrorDeConfig(f"catalogos.{sorted(sobra)[0]}: no existe")
        oficial = cuerpo.get("oficial", True)
        if not isinstance(oficial, bool):
            raise ErrorDeConfig(f"catalogos.oficial: true o false, llegó {oficial!r}")
        fuentes_cat = cuerpo.get("fuentes", [])
        if not isinstance(fuentes_cat, list) or not all(isinstance(x, str) and x.strip() for x in fuentes_cat):
            raise ErrorDeConfig(f"catalogos.fuentes: una lista de URL o rutas a un catalogo.toml, llegó {fuentes_cat!r}")
        cambios["catalogos_oficial"] = oficial
        cambios["catalogos_fuentes"] = tuple(x.strip() for x in fuentes_cat)

    if "periodicos" in datos:
        cuerpo = _tabla(datos["periodicos"], "periodicos")
        sobra = set(cuerpo) - {"en"}
        if sobra:
            raise ErrorDeConfig(f"periodicos.{sorted(sobra)[0]}: no existe")
        en = cuerpo.get("en", "")
        if not isinstance(en, str):
            raise ErrorDeConfig(f"periodicos.en: se esperaba el nombre de un remoto, llegó {en!r}")
        cambios["periodicos_en"] = en.strip()

    if "instruccion" in datos:
        cuerpo = _tabla(datos["instruccion"], "instruccion")
        sobra = set(cuerpo) - {"destino"}
        if sobra:
            raise ErrorDeConfig(f"instruccion.{sorted(sobra)[0]}: no existe")
        destino = cuerpo.get("destino", "")
        if not isinstance(destino, str) or (destino.strip() and not re.fullmatch(r"(agente|hilo):\S.*", destino.strip())):
            raise ErrorDeConfig(f"instruccion.destino: «agente:<nombre>» o «hilo:<nombre>», llegó {destino!r}")
        cambios["instruccion_destino"] = destino.strip()

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
            sobra = set(cuerpo) - {"carpeta", "en", "nombre", "comentar", "prefijo", "pasadas"}
            if sobra:
                raise ErrorDeConfig(f"resultados.{clave}.{sorted(sobra)[0]}: no existe")
            valores: dict = {}
            comentar = cuerpo.get("comentar", [])
            if not isinstance(comentar, list) or not all(isinstance(x, str) and x.strip() for x in comentar):
                raise ErrorDeConfig(f"resultados.{clave}.comentar: se esperaba una lista de palabras, llegó {comentar!r}")
            valores["comentar"] = tuple(comentar)
            for campo in ("carpeta", "en", "nombre", "prefijo", "pasadas"):
                v = cuerpo.get(campo, "")
                if not isinstance(v, str):
                    raise ErrorDeConfig(f"resultados.{clave}.{campo}: se esperaba un texto, llegó {v!r}")
                valores[campo] = v.strip()
            if valores["pasadas"]:
                from telar.pasadas import ESQUEMAS

                if valores["pasadas"] not in ESQUEMAS:
                    raise ErrorDeConfig(f"resultados.{clave}.pasadas: {' o '.join(ESQUEMAS)}; llegó {valores['pasadas']!r}")
            if valores["prefijo"] and not re.fullmatch(r"[\w.-]+", valores["prefijo"]):
                raise ErrorDeConfig(f"resultados.{clave}.prefijo: letras, números, «-», «_» o «.», sin «/»; llegó {valores['prefijo']!r}")
            if not valores["carpeta"] and not valores["en"]:
                raise ErrorDeConfig(f"resultados.{clave}: falta carpeta o en")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", clave):
                raise ErrorDeConfig(f"resultados.{clave}: la clave va en minúsculas, sin espacios")
            lista.append(Resultado(clave=clave, **valores))
        cambios["resultados"] = tuple(lista)

    if "avisos" in datos:
        tabla = _tabla(datos["avisos"], "avisos")
        lista_avisos = []
        for clave, cuerpo in tabla.items():
            cuerpo = _tabla(cuerpo, f"avisos.{clave}")
            sobra = set(cuerpo) - {"archivo", "en"}
            if sobra:
                raise ErrorDeConfig(f"avisos.{clave}.{sorted(sobra)[0]}: no existe")
            valores = {}
            for campo in ("archivo", "en"):
                v = cuerpo.get(campo, "")
                if not isinstance(v, str):
                    raise ErrorDeConfig(f"avisos.{clave}.{campo}: se esperaba un texto, llegó {v!r}")
                valores[campo] = v.strip()
            if not valores["archivo"]:
                raise ErrorDeConfig(f"avisos.{clave}: falta archivo (el JSON que deja el programa)")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", clave):
                raise ErrorDeConfig(f"avisos.{clave}: la clave va en minúsculas, sin espacios")
            lista_avisos.append(AvisoArchivo(clave=clave, **valores))
        cambios["avisos"] = tuple(lista_avisos)

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

    if "terminal" in datos:
        cuerpo = _tabla(datos["terminal"], "terminal")
        cambios["terminal"] = Terminal(**{k: validar_terminal(k, v) for k, v in cuerpo.items()})
    if "modos" in datos:
        from telar import modos as mod_modos

        cambios["modos"] = {k: mod_modos.validar(k, v) for k, v in _tabla(datos["modos"], "modos").items()}
    if "glifos" in datos:
        from telar import glifos as mod_glifos

        cambios["glifos"] = {k: mod_glifos.validar(k, v) for k, v in _tabla(datos["glifos"], "glifos").items()}
    # los temas: los de la raíz (`<raiz>/.telar/temas.toml`) y, encima, los de este archivo
    from telar import temas as mod_temas

    archivo_temas = mod_temas.archivo_de(datos, origen)
    de_raiz, cambios["temas_error"] = mod_temas.leer_raiz(archivo_temas)
    cambios["temas_archivo"] = archivo_temas
    de_aqui = _tabla(datos["temas"], "temas") if "temas" in datos else {}
    if de_raiz or de_aqui:
        cambios["temas"] = mod_temas.validar(mod_temas.juntar(de_raiz, de_aqui))
        cambios["temas_donde"] = mod_temas.donde(de_raiz, de_aqui)
    # los temas que se pueden poner: los de fábrica y los propios de `[temas]`
    from telar.modos import TEMAS

    hay_temas = (*TEMAS, *(t for t in cambios.get("temas", base.temas) if t not in TEMAS))
    if tolerar_temas:
        faltan = tuple(t for t in dict.fromkeys(_temas_nombrados(datos))
                       if t not in hay_temas and mod_temas.NOMBRE.fullmatch(t))
        cambios["temas_faltan"] = faltan
        hay_temas = (*hay_temas, *faltan)

    # el horario de cada mundo y `fuera`: los de la raíz (`<raiz>/.telar/mundos.toml`) y, encima, los de este archivo
    from telar import mundos_raiz

    archivo_mundos = mundos_raiz.archivo_de(datos, origen)
    de_raiz_mundos, cambios["mundos_error"] = mundos_raiz.leer_raiz(archivo_mundos)
    cambios["mundos_archivo"] = archivo_mundos
    if "mundos" in datos:
        tabla_mundos, cambios["mundos_donde"], cambios["mundos_sobran"] = mundos_raiz.juntar(
            _tabla(datos["mundos"], "mundos"), de_raiz_mundos)
        cambios["mundos"], cambios["mundos_fuera"] = _mundos(tabla_mundos, temas=hay_temas)
        _modos_de_mundos(cambios["mundos"], cambios.get("modos", base.modos))
    if "modos" in datos or "temas" in cambios:
        _temas_de_modos(cambios.get("modos", base.modos), hay_temas)
    if "iniciativas" in datos:
        cambios["iniciativas"] = _iniciativas(_tabla(datos["iniciativas"], "iniciativas"))

    desconocidas = set(datos) - {
        "multiplexor", "sesion", "raiz", "estado", "perfil", "intervalos", "proveedores",
        "ficha", "agente", "hilos", "atajos", "secciones", "apps", "dashboard", "remotos", "bloques", "agenda",
        "enlaces", "enlace", "periodicos", "agentes", "bus", "resultados", "notas", "equipo",  # `equipo`: lo lee telar.equipo
        "tipos", "repos", "vistas",  # `vistas`: ya traducidas por _con_vistas
        "disparadores",  # leídos por _con_disparadores
        "terminal", "modos", "glifos", "temas", "instruccion", "mundos", "iniciativas", "avisos",
    }
    if desconocidas:
        sobra = ", ".join(sorted(desconocidas))
        raise ErrorDeConfig(f"claves que telar no conoce: {sobra}")

    return replace(base, **cambios)  # type: ignore[arg-type]


def _modos_de_mundos(mundos, propios: dict) -> None:
    """Que los `modos` de cada mundo existan: los de fábrica y los de `[modos]`. ErrorDeConfig con los que hay."""
    from telar import modos as mod_modos

    hay = [*mod_modos.DE_FABRICA, *(k for k in mod_modos.con_alias(propios or {}) if k not in mod_modos.DE_FABRICA)]
    for m in mundos:
        raro = next((x for x in m.modos if x not in hay), "")
        if raro:
            raise ErrorDeConfig(f"mundos.{m.nombre}.modos: «{raro}» no es un modo ({', '.join(hay)})")


def _modos_del_mundo(nombre: str, valor) -> tuple[str, ...]:
    """`[mundos.<nombre>] modos`: una lista de claves de modos, con al menos una (sin la línea, todos). Los nombres de
    antes pasan a los de ahora (`estandar` es `tactica`); sin repetir, en su orden: el primero es al que entra."""
    from telar import modos as mod_modos

    if not isinstance(valor, list) or not all(isinstance(x, str) and x.strip() for x in valor):
        raise ErrorDeConfig(f"mundos.{nombre}.modos: se esperaba una lista de modos (\"todo\", \"foco\"…), llegó {valor!r}")
    if not valor:
        raise ErrorDeConfig(f"mundos.{nombre}.modos: al menos uno; sin la línea, el mundo tiene todos")
    claves = []
    for x in valor:
        clave = mod_modos.ALIAS.get(x.strip(), x.strip())
        if not mod_modos.CLAVE.match(clave):
            raise ErrorDeConfig(f"mundos.{nombre}.modos: «{x}» no es la clave de un modo (minúsculas, números y guiones)")
        claves.append(clave)
    return tuple(dict.fromkeys(claves))


def _temas_nombrados(datos: dict) -> list[str]:
    """Los temas que nombran los modos y los mundos de ese TOML (`[modos.<m>] tema`, `[mundos.<n>] tema`), sin revisar."""
    salida = []
    for clave in ("modos", "mundos"):
        tabla = datos.get(clave)
        for cuerpo in (tabla.values() if isinstance(tabla, dict) else ()):
            tema = cuerpo.get("tema") if isinstance(cuerpo, dict) else None
            if isinstance(tema, str) and tema:
                salida.append(tema)
    return salida


def _temas_de_modos(modos: dict, temas: tuple[str, ...]) -> None:
    """El tema de cada modo, uno que se puede poner: de fábrica o propio (`[temas.<nombre>] base`). ErrorDeConfig si no."""
    for clave, modo in (modos or {}).items():
        tema = (modo.get("valores") or {}).get("tema") if isinstance(modo, dict) else None
        if tema and tema not in temas:
            raise ErrorDeConfig(f"modos.{clave}.tema: uno de {', '.join(temas)}; llegó {tema!r}")


def _mundos(tabla: dict, *, temas: tuple[str, ...] | None = None) -> tuple[tuple[Mundo, ...], str]:
    """`[mundos.<nombre>]` con `areas`, `rutas`, `etiquetas`, `horario`, `color`, `tema`, `modos` y `arte`, en su orden, y `[mundos] fuera`
    (el que rige fuera de todo horario). Un área, una ruta o una etiqueta en dos mundos es un error: no se sabría a cuál
    pertenece lo que la tiene (una ruta dentro de otra sí vale: gana la más larga). `temas`, los que puede llevar uno (de
    fábrica y propios); sin ellos, los de fábrica."""
    from telar import horario as mod_horario
    from telar.modos import TEMAS

    validos = temas or TEMAS

    mundos, de_area, de_ruta, de_etiqueta = [], {}, {}, {}
    ajustes = {k: v for k, v in tabla.items() if not isinstance(v, dict)}
    sobra = set(ajustes) - {"fuera"}
    if sobra:
        raise ErrorDeConfig(f"mundos.{sorted(sobra)[0]}: no existe (fuera, o una tabla [mundos.<nombre>])")
    for nombre, cuerpo in tabla.items():
        if nombre in ajustes:
            continue
        cuerpo = _tabla(cuerpo, f"mundos.{nombre}")
        if not re.fullmatch(r"[^\s,:/]+", nombre) or nombre == SIN_CLASIFICAR:
            raise ErrorDeConfig(f"mundos.{nombre}: un mundo se llama con una palabra, sin espacios, «,», «:» ni «/», "
                                f"y no «{SIN_CLASIFICAR}» (es lo que no calza en ninguno)")
        sobra = set(cuerpo) - {"areas", "rutas", "etiquetas", "horario", "color", "tema", "modos", "arte"}
        if sobra:
            raise ErrorDeConfig(f"mundos.{nombre}.{sorted(sobra)[0]}: no existe (areas, rutas, etiquetas, horario, color, "
                                "tema, modos o arte)")
        listas = {}
        for campo in ("areas", "rutas", "etiquetas"):
            valor = cuerpo.get(campo, [])
            if not isinstance(valor, list) or not all(isinstance(x, str) and x.strip() for x in valor):
                raise ErrorDeConfig(f"mundos.{nombre}.{campo}: se esperaba una lista de textos, llegó {valor!r}")
            listas[campo] = tuple(dict.fromkeys(x.strip() for x in valor))
        for area in listas["areas"]:
            if de_area.setdefault(area, nombre) != nombre:
                raise ErrorDeConfig(f"mundos.{nombre}.areas: «{area}» ya es de «{de_area[area]}»")
        for ruta in listas["rutas"]:
            if ".." in Path(ruta).parts:
                raise ErrorDeConfig(f"mundos.{nombre}.rutas: «{ruta}» no puede subir con «..»: relativa a la raíz, o absoluta")
            if de_ruta.setdefault(ruta.rstrip("/") + "/", nombre) != nombre:
                raise ErrorDeConfig(f"mundos.{nombre}.rutas: «{ruta}» ya es de «{de_ruta[ruta.rstrip('/') + '/']}»")
        for etiqueta in listas["etiquetas"]:
            if de_etiqueta.setdefault(etiqueta, nombre) != nombre:
                raise ErrorDeConfig(f"mundos.{nombre}.etiquetas: «{etiqueta}» ya es de «{de_etiqueta[etiqueta]}»")
        try:
            tramos = mod_horario.leer_horario(cuerpo.get("horario"))
        except ValueError as e:
            raise ErrorDeConfig(f"mundos.{nombre}.horario: {e}") from None
        color = cuerpo.get("color", "")
        if color and color not in TINTAS_MUNDO:
            raise ErrorDeConfig(f"mundos.{nombre}.color: una de {', '.join(TINTAS_MUNDO)}; llegó {color!r}")
        tema = cuerpo.get("tema", "")
        if tema and tema not in validos:
            raise ErrorDeConfig(f"mundos.{nombre}.tema: uno de {', '.join(validos)}; llegó {tema!r}")
        modos = _modos_del_mundo(nombre, cuerpo["modos"]) if "modos" in cuerpo else ()
        # el arte: solo su clave (que exista lo sabe la página, que tiene los de fábrica: uno que no hay lleva el que le toca)
        arte = cuerpo.get("arte", "")
        if not isinstance(arte, str) or (arte and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", arte)):
            raise ErrorDeConfig(f"mundos.{nombre}.arte: la clave de un arte (minúsculas, números y guiones: «telar», "
                                f"«cielo», o el nombre de un <raiz>/.telar/arte/<clave>.txt); llegó {arte!r}")
        mundos.append(Mundo(nombre=nombre, areas=listas["areas"], rutas=listas["rutas"], etiquetas=listas["etiquetas"],
                            horario=tramos, color=color, tema=tema, modos=modos, arte=arte))
    fuera = ajustes.get("fuera", "")
    if not isinstance(fuera, str) or (fuera and fuera not in [m.nombre for m in mundos]):
        raise ErrorDeConfig(f"mundos.fuera: el nombre de uno de los mundos declarados "
                            f"({', '.join(m.nombre for m in mundos) or 'no hay'}); llegó {fuera!r}")
    return tuple(mundos), fuera


def _iniciativas(tabla: dict) -> Iniciativas:
    """`[iniciativas]`: `estados` (el vocabulario, una lista), `sinonimos` (lo escrito → un estado), `clases` (un estado →
    su clase, telar.iniciativas.CLASES) y `fuentes` (lo que dice `estado_fuente` en una ficha → cómo se muestra). Dos
    estados que solo cambian en tildes o mayúsculas son el mismo, y es un error; un sinónimo que también es estado,
    también."""
    from telar import iniciativas as ini

    sobra = set(tabla) - {"estados", "sinonimos", "clases", "fuentes"}
    if sobra:
        raise ErrorDeConfig(f"iniciativas.{sorted(sobra)[0]}: no existe (estados, sinonimos, clases o fuentes)")

    def texto(v: object, donde: str, largo: int = 40) -> str:
        if not isinstance(v, str) or not v.strip() or "\n" in v or len(v.strip()) > largo:
            raise ErrorDeConfig(f"{donde}: se esperaba un texto de una línea, de hasta {largo} letras; llegó {v!r}")
        return " ".join(v.split())

    crudos = tabla.get("estados", [])
    if not isinstance(crudos, list):
        raise ErrorDeConfig(f"iniciativas.estados: se esperaba una lista de estados, llegó {crudos!r}")
    estados: list[str] = []
    for v in crudos:
        e = texto(v, "iniciativas.estados")
        if any(ini.normalizar(x) == ini.normalizar(e) for x in estados):
            raise ErrorDeConfig(f"iniciativas.estados: «{e}» está dos veces")
        estados.append(e)
    por_norma = {ini.normalizar(e): e for e in estados}

    def del_vocabulario(v: object, donde: str) -> str:
        e = por_norma.get(ini.normalizar(texto(v, donde)))
        if e is None:
            raise ErrorDeConfig(f"{donde}: «{v}» no es uno de iniciativas.estados ({', '.join(estados) or 'no hay'})")
        return e

    crudos_s = tabla.get("sinonimos", {})
    if not isinstance(crudos_s, dict):
        raise ErrorDeConfig(f"iniciativas.sinonimos: se esperaba una tabla, «lo escrito» = «estado»; llegó {crudos_s!r}")
    sinonimos: list[tuple[str, str]] = []
    for de, a in crudos_s.items():
        de = texto(de, "iniciativas.sinonimos")
        if ini.normalizar(de) in por_norma:
            raise ErrorDeConfig(f"iniciativas.sinonimos.{de}: ya es un estado; un sinónimo es lo que vale como otro")
        if any(ini.normalizar(x) == ini.normalizar(de) for x, _ in sinonimos):
            raise ErrorDeConfig(f"iniciativas.sinonimos: «{de}» está dos veces")
        sinonimos.append((de, del_vocabulario(a, f"iniciativas.sinonimos.{de}")))

    crudas_c = tabla.get("clases", {})
    if not isinstance(crudas_c, dict):
        raise ErrorDeConfig(f"iniciativas.clases: se esperaba una tabla, «estado» = «clase»; llegó {crudas_c!r}")
    clases: list[tuple[str, str]] = []
    for e, c in crudas_c.items():
        e = del_vocabulario(e, "iniciativas.clases")
        if c not in ini.CLASES:
            raise ErrorDeConfig(f"iniciativas.clases.{e}: una de {', '.join(ini.CLASES)}; llegó {c!r}")
        clases.append((e, c))

    crudas_f = tabla.get("fuentes", {})
    if not isinstance(crudas_f, dict):
        raise ErrorDeConfig(f"iniciativas.fuentes: se esperaba una tabla, «lo que dice estado_fuente» = «cómo se muestra»; "
                            f"llegó {crudas_f!r}")
    fuentes: list[tuple[str, str]] = []
    for de, nombre in crudas_f.items():
        de = texto(de, "iniciativas.fuentes")
        if any(ini.normalizar(x) == ini.normalizar(de) for x, _ in fuentes):
            raise ErrorDeConfig(f"iniciativas.fuentes: «{de}» está dos veces")
        fuentes.append((de, texto(nombre, f"iniciativas.fuentes.{de}")))
    if (sinonimos or clases) and not estados:
        raise ErrorDeConfig("iniciativas: sinonimos y clases son de los estados de iniciativas.estados, que no hay")
    return Iniciativas(estados=tuple(estados), sinonimos=tuple(sinonimos), clases=tuple(clases), fuentes=tuple(fuentes))


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
    return _entorno(desde_dict(datos, origen=destino, rotos=rotos, tolerar_temas=True))


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
        if d.get("activo") is False:
            continue  # apagado (telar modulos desactivar): instalado, pero no aporta nada
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


def escribir_clave(tabla: str, clave: str, valor: object, ruta: Path | None = None, *, revisar=None) -> Path:
    """Pone `clave = valor` en `[tabla]`, o la quita si `valor` es None.

    `valor` es un texto, un número o una lista de textos.

    Toca solo esa línea: el resto del archivo, comentarios incluidos, queda como estaba.
    Si la tabla no existe se agrega al final. Igual que con el calendario, antes de
    escribir se comprueba que el resultado se siga leyendo: como configuración o, con `revisar(antes, nuevo, destino)`,
    como lo diga quien escribe (un archivo de la raíz que no es una configuración, telar.mundos_raiz).
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

    (revisar or revisar_antes_de_escribir)(texto, nuevo, destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".nuevo")
    temporal.write_text(nuevo, encoding="utf-8")
    if destino.exists():
        os.chmod(temporal, destino.stat().st_mode & 0o777)
    os.replace(temporal, destino)
    return destino


def revisar_antes_de_escribir(antes: str, nuevo: str, destino: Path) -> None:
    """Que lo que se va a escribir en `destino` se siga leyendo. Un modo o un mundo que ya nombraba un tema que no hay (uno
    propio que se borró en la raíz desde otra máquina) no impide escribir otra cosa; nombrar uno nuevo que no hay, sí.
    ErrorDeConfig («no escribí nada: …») si no."""
    try:
        desde_dict(tomllib.loads(nuevo), origen=destino)
        return
    except (tomllib.TOMLDecodeError, ErrorDeConfig) as e:
        error = e
    try:
        ya_faltaban = set(desde_dict(tomllib.loads(antes), origen=destino, tolerar_temas=True).temas_faltan) if antes else set()
        faltan = set(desde_dict(tomllib.loads(nuevo), origen=destino, tolerar_temas=True).temas_faltan)
    except (tomllib.TOMLDecodeError, ErrorDeConfig):
        faltan, ya_faltaban = {""}, set()
    if faltan and faltan <= ya_faltaban:
        return
    raise ErrorDeConfig(f"no escribí nada: el resultado no se podría leer ({error})") from error


def _valor_toml(valor: object) -> str:
    """Un valor TOML en una línea: texto, número o lista de textos (JSON sirve para los tres)."""
    import json
    import math

    if isinstance(valor, float) and math.isfinite(valor):
        return repr(valor)
    if isinstance(valor, bool) or not isinstance(valor, (str, int, list, tuple)):
        raise ErrorDeConfig(f"no sé escribir {valor!r} en la configuración")
    return json.dumps(list(valor) if isinstance(valor, tuple) else valor, ensure_ascii=False)

