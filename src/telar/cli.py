"""La CLI de telar: solo el despachador.

Aquí no vive ninguna orden. Este archivo resuelve las banderas globales, arma el
contexto (configuración y perfil) y le pasa el resto a la orden, que vive en su
propio módulo `telar.ordenes.<nombre>`. Cada orden expone:

    def main(argv: list[str], ctx: Contexto) -> int

`argv` son los argumentos que quedaron después del nombre de la orden; el entero
que devuelve es el código de salida. Una orden que no existe todavía se dice en
voz alta y sale con 2: es un esqueleto, no un misterio.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

from telar import __version__, salida
from telar.config import Config, ErrorDeConfig
from telar.config import cargar as cargar_config
from telar.perfil import ErrorDePerfil, Perfil
from telar.perfil import cargar_todos as cargar_perfiles

__all__ = ["Contexto", "ORDENES", "main"]

#: Las órdenes que telar va a tener, con su línea de ayuda. El módulo de cada una
#: es `telar.ordenes.<nombre>`; mientras no exista, el despachador lo dice.
ORDENES: dict[str, str] = {
    "init": "Escribir la configuración y preparar el estado.",
    "doctor": "Revisar multiplexor, sesión, perfil, proveedores y ganchos.",
    "tejer": "Levantar la sesión, o reengancharla si ya está viva.",
    "hilos": "Los hilos de la sesión, con su estado.",
    "hilo": "Vincular, renombrar, priorizar, archivar: actuar sobre un hilo.",
    "ficha": "Lo que el documento de un hilo dice de sí mismo.",
    "ir": "Poner el foco en un hilo.",
    "vincular": "Asociar un hilo a una carpeta del repositorio.",
    "fecha": "Cambiar una fecha (su inicio, su fin) donde vive: la celda de su documento, su tarea, su programa.",
    "fechas": "Lo que tiene día (actividades, hitos, sesiones), venga de donde venga.",
    "pendientes": "Lo que está por hacer, junto y con su hilo al lado.",
    "pendiente": "Llevar un pendiente al hilo donde se trabaja.",
    "tarea": "La ficha de una tarea de un proveedor, y correr una de sus acciones.",
    "aviso": "Un aviso en la pantalla de otra máquina, por el bus.",
    "archivo": "Mandar un archivo a la carpeta de entrada de otra máquina, por el bus.",
    "tipo": "Los objetos de un tipo (las tareas): leerlos, crearlos y aplicarles sus acciones.",
    "cambio": "Avisar que algo cambió (las tareas), para que el dashboard lo relea ya.",
    "commit": "Commitear solo unas rutas y subirlas, sin pisar lo que otros dejaron a medias.",
    "hoy": "El día en una pantalla: agenda, quién te espera, qué falta.",
    "reunion": "Preparar una reunión: un hilo con el agente ya trabajando en ella.",
    "atajo": "Una tecla del dashboard: un hilo con el agente haciendo algo recurrente.",
    "bloque": "Lo que muestra un bloque del día: corre su comando y devuelve su página.",
    "mirar": "Engancharse a la ventana de un hilo en esta terminal, sin tocar lo que ven los demás.",
    "objeto": "Cualquier objeto por su dirección (tarea:T366, hilo:Telar…): verlo y aplicarle una acción.",
    "modulos": "Los módulos instalados (una carpeta con modulo.toml) y lo que aporta cada uno.",
    "app": "Las apps del panel (un juego, un vivero): la lista, o la página de una.",
    "seccion": "La página de una sección de la lista: corre su `home` y devuelve su JSON.",
    "directorio": "Los hilos remotos de cada persona de una máquina compartida: leerlos y publicar los propios.",
    "correo": "Escribirle a un hilo de otra persona (por el bus, si es propio).",
    "espejo": "Los hilos de otra máquina, vistos desde esta.",
    "equipo": "Que una persona de confianza vea tus tareas del equipo y te sugiera prioridades.",
    "persona": "Las personas de este servidor: darles de alta con un perfil, verlas, cerrarles el acceso.",
    "servidor": "Un lugar para ti en el servidor, que alberga hilos de varias personas.",
    "imagen": "Llevar una imagen del portapapeles (o un archivo) a la máquina donde corre el hilo.",
    "puerta": "La puerta de un servidor con alojados: una sola dirección, y cada persona a su telar.",
    "serve": "La API de telar: los mismos datos que la CLI, por HTTP, desde un proceso que se queda.",
    "periodicos": "Los procesos que corren solos cada cierto tiempo: verlos, crearlos, cambiarlos.",
    "disparadores": "Lo que corre o manda algo solo: por un reloj, una tecla o un cambio.",
    "encargar": "Pedirle algo a un agente residente, en su hilo de siempre.",
    "mensaje": "Un mensaje para un hilo o un agente, en la máquina que sea, por el bus.",
    "compartir": "Llevar algo de afuera (un enlace, un texto) a un hilo, a un agente o a un proveedor que lo recibe.",
    "nodo": "Esta máquina en el bus: recibe lo suyo, avisa a sus hilos y publica su estado.",
    "bus": "Las cuentas del bus: una por persona, que el servidor hace cumplir.",
    "instalar": "Dejar esta máquina andando de una vez: configuración, página, servicio y agente.",
    "resultado": "Lo que una skill dejó un día (el plan, por ejemplo), leído de la máquina donde vive.",
    "evento": "Las notas de los eventos del día: verlas y dejarle una a un evento.",
    "proyectos": "Todas las unidades del perfil, y abrir un hilo cargando una.",
    "atencion": "Qué dice el agente de cada hilo: trabajando, espera, terminó.",
    "agente": "El agente que corre en un hilo: sus ganchos, sus conversaciones.",
    "agentes": "Los agentes residentes y lo que declara cada uno en su agente.toml.",
    "tiempo": "Cuánto estuvo arriba cada hilo, medido por el foco.",
    "accion": "Correr una acción declarada por el perfil.",
    "config": "Mostrar la configuración resuelta y de dónde salió.",
    "perfil": "Mostrar el perfil del repositorio y qué documentos alcanza.",
}

AYUDA = f"""\
telar {__version__} — un telar para hilos de trabajo.

  telar [banderas] <orden> [argumentos]

Banderas globales:
  -c, --config RUTA   archivo de configuración (por defecto, $TELAR_CONFIG o
                      ~/.config/telar/config.toml)
  -r, --raiz RUTA     raíz del repositorio de trabajo (pisa la de la configuración)
  -V, --version       la versión y nada más
  -h, --help          esto

Órdenes:
{chr(10).join(f"  {n:<12}{d}" for n, d in ORDENES.items())}

Cada orden explica lo suyo con --help, y lo que imprime con --json es un contrato:
está escrito en docs/contratos.md.

telar no decide qué es un proyecto: eso lo declara el repositorio de trabajo en su
.telar/perfil.yaml. Ver docs/perfil.md.
"""


@dataclass(slots=True)
class Contexto:
    """Lo que toda orden recibe. El perfil se lee la primera vez que se pide."""

    config: Config
    _perfil: Perfil | None = None

    @property
    def perfil(self) -> Perfil:
        if self._perfil is None:
            self._perfil = cargar_perfiles(self.config)
        return self._perfil

    @property
    def raiz(self) -> Path:
        return self.config.raiz


#: las órdenes que arrancan aunque un módulo declarado no se pueda leer (lo dejan fuera y lo anotan en
#: `Config.modulos_rotos`); las demás se niegan, como siempre.
TOLERAN_MODULOS_ROTOS = frozenset({"doctor"})


def _error(mensaje: str) -> int:
    print(f"telar: {mensaje}", file=sys.stderr)
    return 2


def _banderas(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    """Separa las banderas globales del resto. La primera palabra suelta es la orden.

    Se hace a mano y no con argparse porque las banderas de cada orden son de cada
    orden: aquí no se conocen y no hay que tocarlas.
    """
    opciones: dict[str, str] = {}
    resto: list[str] = []
    i = 0
    con_valor = {"-c": "config", "--config": "config", "-r": "raiz", "--raiz": "raiz"}
    solas = {"-h": "ayuda", "--help": "ayuda", "-V": "version", "--version": "version"}

    while i < len(argv):
        arg = argv[i]
        if arg in con_valor:
            if i + 1 >= len(argv):
                raise ValueError(f"{arg} necesita un valor")
            opciones[con_valor[arg]] = argv[i + 1]
            i += 2
            continue
        if arg in solas:
            opciones[solas[arg]] = "sí"
            i += 1
            continue
        if arg.startswith("-") and arg != "-":
            raise ValueError(f"bandera desconocida: {arg}")
        # la primera palabra suelta es la orden; de ahí en adelante, es de ella
        resto = argv[i:]
        break

    return opciones, resto


def main(argv: list[str] | None = None) -> int:
    """El punto de entrada de la consola. Devuelve el código de salida."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # Antes de imprimir nada, ni siquiera la ayuda: todo lo que telar dice trae
    # acentos, comillas «así» y símbolos, y una salida que no sea UTF-8 mataría la
    # orden con una traza. Ver `telar.salida`.
    salida.preparar()

    try:
        opciones, resto = _banderas(argv)
    except ValueError as e:
        return _error(f"{e}\nPrueba: telar --help")

    if "version" in opciones:
        print(f"telar {__version__}")
        return 0

    if "ayuda" in opciones or not resto:
        print(AYUDA, end="")
        return 0 if "ayuda" in opciones else 1

    orden, argumentos = resto[0], resto[1:]
    if orden not in ORDENES:
        # la de un módulo instalado: `telar <modulo> <verbo> …` (telar.modulos)
        externo = _de_un_modulo(orden, argumentos, opciones)
        if externo is not None:
            return externo
        parecidas = [n for n in ORDENES if n.startswith(orden[:2])]
        pista = f" ¿Quisiste decir {' o '.join(parecidas)}?" if parecidas else ""
        return _error(f"no conozco la orden '{orden}'.{pista}\nPrueba: telar --help")

    try:
        # doctor carga aunque un módulo no se lea: es la orden que tiene que decirlo
        config = cargar_config(Path(opciones["config"]) if "config" in opciones else None,
                               tolerar_modulos=orden in TOLERAN_MODULOS_ROTOS)
        if "raiz" in opciones:
            from dataclasses import replace

            # absoluta siempre: el contrato promete rutas que sirven para `cd`
            config = replace(config, raiz=Path(opciones["raiz"]).expanduser().absolute())
    except ErrorDeConfig as e:
        return _error(str(e))

    ruta_modulo = f"telar.ordenes.{orden}"
    try:
        modulo = importlib.import_module(ruta_modulo)
    except ModuleNotFoundError as e:
        # Solo si falta la orden misma. Si a la orden le falta OTRA cosa, que se vea.
        if e.name not in (ruta_modulo, "telar.ordenes"):
            raise
        return _error(f"la orden '{orden}' está declarada pero todavía no implementada")

    try:
        return int(modulo.main(argumentos, Contexto(config=config)))
    except (ErrorDeConfig, ErrorDePerfil) as e:
        return _error(str(e))
    except KeyboardInterrupt:  # pragma: no cover - depende de la terminal
        return 130


def _de_un_modulo(orden: str, argumentos: list[str], opciones: dict) -> int | None:
    """Corre la orden de un módulo que se llama `orden`; None si no hay un módulo así."""
    from telar import modulos as mod_modulos

    try:
        config = cargar_config(Path(opciones["config"]) if "config" in opciones else None)
    except ErrorDeConfig:
        return None
    m = mod_modulos.buscar(config, orden)
    if m is None or not m.ordenes:
        return None
    try:
        return mod_modulos.correr_orden(config, m, argumentos)
    except mod_modulos.ErrorDeModulo as e:
        return _error(str(e))
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
