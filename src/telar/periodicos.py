"""Procesos periódicos: lo que corre solo cada cierto tiempo, definido en un lugar y visible.

Viven en `periodicos.toml`, al lado de `config.toml`, en la máquina que los corre (un servidor
que no se apaga). Cada proceso es una tabla con su nombre:

    zona = "America/Santiago"          # la hora en que se leen los horarios

    [resumen-diario]
    cuando = "30 8 * * 1-5"            # cron: minuto hora día-del-mes mes día-de-la-semana
    comando = "~/bin/resumen --corto"  # una línea de shell (bash -lc), o…
    descripcion = "el resumen de la mañana"

    [revisar-correo]
    cuando = "0 9-19/2 * * *"
    mensaje = "/correo"                # …un prompt: abre un hilo con el agente, que se puede mirar
    hilo = "✉ correo"                  # el nombre del hilo (se le agrega la fecha y la hora)
    padre = "Secretaría"               # cuelga de ese hilo en la barra (el de un agente), y le avisa al terminar
    max_abiertos = 2                   # si ya hay tantos abiertos sin cerrar, esta vez no abre
    argumentos = ["--permission-mode", "acceptEdits"]   # para el agente, después del prompt
    carpeta = "~/trabajo"              # dónde corre (por defecto, el hogar)
    activo = false                     # pausado: no corre, pero no se olvida

    [avanzar]
    cuando = "0 9-19/2 * * 1-5"
    mensaje = "/avanzar"
    agente = "secretaria"              # se le encarga al agente residente (telar.encargos) en vez de
                                       # abrir un hilo nuevo cada vez: una sola sesión que dura
    despues = ["revisar-correo"]       # usa lo que deja otro: se dibuja junto a él (no lo espera)

`telar periodicos aplicar` escribe en el crontab de la máquina un bloque entre marcas con una
línea por proceso activo, y no toca nada fuera de él. Cada línea llama a `telar periodicos correr
<nombre>`, que anota inicio, fin y resultado en `<estado>/periodicos/<nombre>.json` y la salida en
`<nombre>.log`, y cada corrida terminada en `<nombre>.historial.jsonl`: de ahí sale lo que muestra el
dashboard (la última corrida, si salió bien, el log, y el calendario de lo que corrió y lo que viene:
`corridas`). Cambiar el archivo desde telar guarda la versión anterior en `periodicos.toml.anterior`.

Las dependencias son de dos clases, y el calendario dibuja las dos. Una se declara: `despues` nombra los
procesos cuyo resultado usa este (el plan de la noche lee la retrospectiva de la tarde); es solo para
verla, cron no espera a nadie. La otra se deduce: dos procesos que van al mismo agente comparten su
casilla, y el que llega mientras el agente trabaja espera su turno (`destino`; el de un comando que
encarga, `telar encargar <agente>`, se lee en el comando o en su script).

Los hilos que abre un proceso con `mensaje` son ventanas de la sesión del telar, como cualquier hilo:
otra máquina los trae a su lista (su nodo, al verlos en el bus).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

#: las marcas del bloque que telar maneja en el crontab; lo de afuera no se toca
MARCA_INICIO = "# >>> telar periodicos — no editar a mano: `telar periodicos`"
MARCA_FIN = "# <<< telar periodicos"
#: el nombre de un proceso va en el crontab y en nombres de archivo: letras, números, - y _
NOMBRE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
#: el log de cada proceso no crece sin fin: al pasar de esto se queda con la mitad más nueva
MAX_LOG = 512 * 1024
CLAVES = ("cuando", "comando", "mensaje", "agente", "hilo", "padre", "max_abiertos", "argumentos", "carpeta", "descripcion",
          "activo", "despues")
#: cuántas corridas guarda el historial de cada proceso; al pasar, se queda con las más nuevas
MAX_HISTORIAL = 1000


class ErrorDePeriodicos(Exception):
    """Un proceso mal definido o algo que no se pudo hacer. El mensaje es para la persona."""


@dataclass(frozen=True)
class Proceso:
    nombre: str
    cuando: str
    comando: str = ""
    mensaje: str = ""
    agente: str = ""
    hilo: str = ""
    #: el hilo del que cuelga cada hilo que abre (el de un agente: «Cuaderno»), como uno abierto con `telar hilo hijo`
    padre: str = ""
    max_abiertos: int = 1
    argumentos: tuple[str, ...] = ()
    carpeta: str = ""
    descripcion: str = ""
    activo: bool = True
    #: los procesos cuyo resultado usa este: se dibujan juntos en el calendario (cron no espera a nadie)
    despues: tuple[str, ...] = ()
    #: el módulo que lo declara (`telar.modulos`); "" si vive en periodicos.toml. Los de un módulo
    #: no se escriben en periodicos.toml ni se cambian desde aquí: se cambian en su modulo.toml.
    modulo: str = ""
    #: si lo declara un `[disparadores.x]` de la configuración (telar.disparadores): tampoco se escribe en
    #: periodicos.toml ni se cambia desde aquí, sino en la configuración.
    disparador: bool = False

    @property
    def tipo(self) -> str:
        return "mensaje" if self.mensaje else "comando"

    @property
    def nombre_hilo(self) -> str:
        return self.hilo or self.nombre

    def validar(self) -> None:
        if not NOMBRE.match(self.nombre):
            raise ErrorDePeriodicos(f"«{self.nombre}»: el nombre va en minúsculas, con letras, números, - y _")
        Horario(self.cuando)  # levanta si no se entiende
        if bool(self.comando.strip()) == bool(self.mensaje.strip()):
            raise ErrorDePeriodicos(f"«{self.nombre}»: lleva `comando` o `mensaje`, uno de los dos")
        if self.agente and not self.mensaje.strip():
            raise ErrorDePeriodicos(f"«{self.nombre}»: `agente` va con `mensaje` (lo que se le encarga)")
        if self.padre and (self.agente or not self.mensaje.strip()):
            raise ErrorDePeriodicos(f"«{self.nombre}»: `padre` es de los que abren un hilo nuevo (con `mensaje` y sin `agente`)")
        if "\n" in self.padre:
            raise ErrorDePeriodicos(f"«{self.nombre}»: `padre` es el nombre de un hilo, en una línea")
        if self.max_abiertos < 1:
            raise ErrorDePeriodicos(f"«{self.nombre}»: max_abiertos va desde 1")
        if "\n" in self.comando or "\n" in self.cuando:
            raise ErrorDePeriodicos(f"«{self.nombre}»: el comando y el horario van en una línea")
        for otro in self.despues:
            if otro == self.nombre:
                raise ErrorDePeriodicos(f"«{self.nombre}»: no va después de sí mismo")
            if not NOMBRE.match(otro):
                raise ErrorDePeriodicos(f"«{self.nombre}»: `despues` nombra procesos («{otro}» no es un nombre)")


@dataclass
class Archivo:
    zona: str = ""
    procesos: list[Proceso] = field(default_factory=list)

    def por_nombre(self, nombre: str) -> Proceso | None:
        return next((p for p in self.procesos if p.nombre == nombre), None)


# ── el horario ─────────────────────────────────────────────────────────────────

_RANGOS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
_NOMBRES_CAMPO = ("minuto", "hora", "día del mes", "mes", "día de la semana")
_ATAJOS = {"@hourly": "0 * * * *", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
           "@weekly": "0 0 * * 0", "@monthly": "0 0 1 * *", "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *"}


class Horario:
    """Una expresión cron de cinco campos, entendida: qué minutos, horas, días… valen."""

    def __init__(self, texto: str):
        texto = " ".join((texto or "").split())
        texto = _ATAJOS.get(texto, texto)
        campos = texto.split(" ")
        if len(campos) != 5:
            raise ErrorDePeriodicos(f"«{texto}» no es un horario cron: van cinco campos (minuto hora día mes día-semana)")
        self.texto = texto
        self.valores = [self._campo(c, *_RANGOS[i], _NOMBRES_CAMPO[i]) for i, c in enumerate(campos)]
        self.valores[4] = {0 if d == 7 else d for d in self.valores[4]}
        # cron: si día del mes y día de la semana están ambos restringidos, vale cualquiera de los dos
        self.dom_libre, self.dow_libre = campos[2] == "*", campos[4] == "*"

    @staticmethod
    def _campo(texto: str, bajo: int, alto: int, nombre: str) -> set[int]:
        salida: set[int] = set()
        for parte in texto.split(","):
            m = re.fullmatch(r"(\*|\d+(?:-\d+)?)(?:/(\d+))?", parte)
            if not m:
                raise ErrorDePeriodicos(f"no entiendo «{parte}» en el campo {nombre}")
            rango, paso = m.group(1), int(m.group(2) or 1)
            if rango == "*":
                a, b = bajo, alto
            elif "-" in rango:
                a, b = (int(x) for x in rango.split("-"))
            else:
                a = b = int(rango)
                if m.group(2):
                    b = alto  # «5/15»: desde 5, cada 15
            if not (bajo <= a <= alto and bajo <= b <= alto and a <= b) or paso < 1:
                raise ErrorDePeriodicos(f"«{parte}» está fuera de rango en el campo {nombre} ({bajo}-{alto})")
            salida.update(range(a, b + 1, paso))
        return salida

    def _dia_vale(self, d: datetime) -> bool:
        dom = d.day in self.valores[2]
        dow = (d.isoweekday() % 7) in self.valores[4]
        if self.dom_libre and self.dow_libre:
            return True
        if self.dom_libre:
            return dow
        if self.dow_libre:
            return dom
        return dom or dow

    def proxima(self, desde: datetime) -> datetime | None:
        """La primera vez después de `desde` (sin segundos), en la misma zona que `desde`."""
        inicio = desde.replace(second=0, microsecond=0) + timedelta(minutes=1)
        minutos, horas, meses = sorted(self.valores[0]), sorted(self.valores[1]), self.valores[3]
        dia = inicio.replace(hour=0, minute=0)
        for _ in range(366 * 5):
            if dia.month in meses and self._dia_vale(dia):
                for h in horas:
                    for m in minutos:
                        t = dia.replace(hour=h, minute=m)
                        if t >= inicio:
                            return t
            dia = (dia + timedelta(days=1)).replace(hour=0, minute=0)
        return None


def zona_info(zona: str):
    """La zona horaria del archivo, o la de la máquina si no dice."""
    if not zona:
        return datetime.now().astimezone().tzinfo
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(zona)
    except Exception as e:  # noqa: BLE001 - ZoneInfoNotFoundError y los de clave inválida
        raise ErrorDePeriodicos(f"no conozco la zona «{zona}»") from e


def proxima(p: Proceso, zona: str, ahora: datetime | None = None) -> datetime | None:
    if not p.activo:
        return None
    tz = zona_info(zona)
    ahora = (ahora or datetime.now(tz)).astimezone(tz)
    return Horario(p.cuando).proxima(ahora)


# ── el archivo ─────────────────────────────────────────────────────────────────

def ruta(config_ruta: Path | None = None) -> Path:
    """`periodicos.toml` al lado del config.toml que se está usando."""
    from telar import config as mod_config

    return Path(config_ruta or mod_config.ruta_config()).expanduser().parent / "periodicos.toml"


def _lista(valor) -> tuple[str, ...]:
    """Una lista de nombres del TOML; uno solo, entre comillas, también vale."""
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, (list, tuple)):
        raise ValueError("`despues` es una lista de nombres")
    return tuple(str(x) for x in valor)


def leer(destino: Path) -> Archivo:
    if not destino.exists():
        return Archivo()
    try:
        datos = tomllib.loads(destino.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ErrorDePeriodicos(f"{destino}: {e}") from e
    zona = datos.pop("zona", "")
    if not isinstance(zona, str):
        raise ErrorDePeriodicos(f"{destino}: `zona` va entre comillas")
    procesos = []
    for nombre, cuerpo in datos.items():
        if not isinstance(cuerpo, dict):
            raise ErrorDePeriodicos(f"{destino}: «{nombre}» tiene que ser una tabla [{nombre}]")
        sobra = set(cuerpo) - set(CLAVES)
        if sobra:
            raise ErrorDePeriodicos(f"{destino}: [{nombre}] no conoce «{sorted(sobra)[0]}»")
        try:
            p = Proceso(nombre=nombre, cuando=str(cuerpo.get("cuando", "")), comando=str(cuerpo.get("comando", "")),
                        mensaje=str(cuerpo.get("mensaje", "")), agente=str(cuerpo.get("agente", "")),
                        hilo=str(cuerpo.get("hilo", "")), padre=str(cuerpo.get("padre", "")),
                        max_abiertos=int(cuerpo.get("max_abiertos", 1)),
                        argumentos=tuple(str(x) for x in cuerpo.get("argumentos", ())),
                        carpeta=str(cuerpo.get("carpeta", "")), descripcion=str(cuerpo.get("descripcion", "")),
                        activo=bool(cuerpo.get("activo", True)), despues=_lista(cuerpo.get("despues", ())))
        except (TypeError, ValueError) as e:
            raise ErrorDePeriodicos(f"{destino}: [{nombre}]: {e}") from e
        p.validar()
        procesos.append(p)
    zona_info(zona)
    return Archivo(zona=zona, procesos=procesos)


def con_modulos(a: Archivo, config) -> Archivo:
    """El archivo con los procesos de los módulos instalados (`[modulos]`) al final. Corren en la
    carpeta del módulo, así que su comando puede ser una ruta relativa a ella."""
    for m in getattr(config, "modulos", ()):
        for nombre, cuerpo in m.periodicos.items():
            if a.por_nombre(nombre):
                raise ErrorDePeriodicos(f"el módulo {m.nombre} trae «{nombre}», que ya está en periodicos.toml: bórralo de ahí")
            sobra = set(cuerpo) - set(CLAVES)
            if sobra:
                raise ErrorDePeriodicos(f"módulo {m.nombre}: [periodicos.{nombre}] no conoce «{sorted(sobra)[0]}»")
            try:
                p = Proceso(nombre=nombre, cuando=str(cuerpo.get("cuando", "")), comando=str(cuerpo.get("comando", "")),
                            mensaje=str(cuerpo.get("mensaje", "")), agente=str(cuerpo.get("agente", "")),
                            hilo=str(cuerpo.get("hilo", "")), padre=str(cuerpo.get("padre", "")),
                            max_abiertos=int(cuerpo.get("max_abiertos", 1)),
                            argumentos=tuple(str(x) for x in cuerpo.get("argumentos", ())),
                            carpeta=str(cuerpo.get("carpeta") or m.carpeta),
                            descripcion=str(cuerpo.get("descripcion", "") or m.descripcion),
                            activo=bool(cuerpo.get("activo", True)), despues=_lista(cuerpo.get("despues", ())),
                            modulo=m.nombre)
            except (TypeError, ValueError) as e:
                raise ErrorDePeriodicos(f"módulo {m.nombre}: [periodicos.{nombre}]: {e}") from e
            p.validar()
            a.procesos.append(p)
    return a


def con_disparadores(a: Archivo, config) -> Archivo:
    """El archivo con los `[disparadores]` de reloj de la configuración al final (telar.disparadores). Solo en la
    máquina donde corren los periódicos: en otra, su configuración no es la que lee el crontab. Uno de reloj o de
    cambio que se llama como un proceso de periodicos.toml o de un módulo queda fuera, él solo: los dos anotarían
    su última corrida en `<estado>/periodicos/<nombre>.json`. Antes era un error, y tumbaba todos los periódicos
    de la máquina (cada línea del crontab pasa por aquí); ahora lo dice `telar doctor` (`choques`)."""
    from telar import disparadores as mod_disparadores

    for d in getattr(config, "disparadores", ()):
        if d.tipo == "tecla" or a.por_nombre(d.nombre) is not None:
            continue
        if d.tipo == "reloj" and mod_disparadores.corren_aqui(config):
            a.procesos.append(d.proceso())
    return a


def choques(a: Archivo, config) -> list[tuple[str, str]]:
    """Los `[disparadores]` de reloj o de cambio que se llaman como un proceso de `a` (periodicos.toml y los
    módulos, sin los disparadores): (nombre, dónde está el otro). No corren hasta que se cambie uno de los dos."""
    salida = []
    for d in getattr(config, "disparadores", ()):
        previo = a.por_nombre(d.nombre) if d.tipo != "tecla" else None
        if previo is not None and not previo.disparador:
            salida.append((d.nombre, f"el módulo {previo.modulo}" if previo.modulo else "periodicos.toml"))
    return salida


def choques_aqui(config) -> list[tuple[str, str]]:
    """`choques` con el periodicos.toml de esta configuración y sus módulos. Si no se pueden leer, ninguno: eso ya
    lo dice `telar periodicos`."""
    if not getattr(config, "disparadores", ()):
        return []
    try:
        return choques(con_modulos(leer(ruta(getattr(config, "origen", None))), config), config)
    except ErrorDePeriodicos:
        return []


def completo(a: Archivo, config) -> Archivo:
    """Lo que corre en esta máquina: periodicos.toml, los módulos y los `[disparadores]` de reloj."""
    return con_disparadores(con_modulos(a, config), config)


def _toml(valor) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, (list, tuple)):
        return "[" + ", ".join(_toml(v) for v in valor) + "]"
    return json.dumps(str(valor), ensure_ascii=False)  # una cadena JSON es una cadena TOML básica válida


def texto(a: Archivo) -> str:
    lineas = ["# Los procesos periódicos de esta máquina. Lo escribe `telar periodicos`; se puede",
              "# editar a mano, y después `telar periodicos aplicar`.", ""]
    if a.zona:
        lineas += [f"zona = {_toml(a.zona)}", ""]
    for p in a.procesos:
        if p.modulo or p.disparador:
            continue   # lo declara su módulo, o la configuración
        lineas.append(f"[{p.nombre}]")
        por_defecto = Proceso(nombre=p.nombre, cuando="")
        for clave in CLAVES:
            v = getattr(p, clave)
            if clave == "cuando" or v != getattr(por_defecto, clave):
                lineas.append(f"{clave} = {_toml(v)}")
        lineas.append("")
    return "\n".join(lineas)


def escribir(destino: Path, a: Archivo) -> None:
    for p in a.procesos:
        p.validar()
    zona_info(a.zona)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        shutil.copy2(destino, destino.with_name(destino.name + ".anterior"))
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text(texto(a), encoding="utf-8")
    os.replace(tmp, destino)


def cambiar(a: Archivo, nombre: str, **campos) -> Proceso:
    p = a.por_nombre(nombre)
    if p is None:
        raise ErrorDePeriodicos(f"no hay un proceso «{nombre}»")
    for clave in ("argumentos", "despues"):
        if clave in campos:
            campos[clave] = tuple(campos[clave])
    # cambiar de comando a mensaje (o al revés) deja el otro vacío
    if campos.get("comando"):
        campos.setdefault("mensaje", "")
        campos.setdefault("agente", "")
        campos.setdefault("padre", "")
    if campos.get("agente"):
        campos.setdefault("padre", "")
    if campos.get("mensaje"):
        campos.setdefault("comando", "")
    nuevo = replace(p, **campos)
    nuevo.validar()
    a.procesos[a.procesos.index(p)] = nuevo
    return nuevo


# ── el crontab ─────────────────────────────────────────────────────────────────

def bloque(a: Archivo, telar: str) -> list[str]:
    """Las líneas del bloque de telar en el crontab. Los pausados quedan comentados, a la vista."""
    # cada corrida guarda su salida en su log (`telar periodicos log`): por correo era una copia más, que
    # además llenaba la casilla. Como CRON_TZ, vale para las líneas de abajo: el bloque va al final
    lineas = [MARCA_INICIO, 'MAILTO=""']
    if a.zona:
        lineas.append(f"CRON_TZ={a.zona}")
    for p in a.procesos:
        linea = f"{Horario(p.cuando).texto} {shlex.quote(telar)} periodicos correr {p.nombre} --en aqui"
        lineas.append(linea if p.activo else f"# (pausado) {linea}")
    lineas.append(MARCA_FIN)
    return lineas


def con_bloque(actual: str, nuevo: list[str]) -> str:
    """El crontab con el bloque de telar reemplazado (o agregado al final). Lo de afuera queda igual.

    Va al final porque `CRON_TZ` vale para las líneas que vienen después: así no le cambia la zona
    a las que la persona escribió."""
    lineas = actual.splitlines()
    if MARCA_INICIO in lineas and MARCA_FIN in lineas:
        i, j = lineas.index(MARCA_INICIO), lineas.index(MARCA_FIN)
        lineas = lineas[:i] + lineas[j + 1:]
    while lineas and not lineas[-1].strip():
        lineas.pop()
    return "\n".join([*lineas, *([""] if lineas else []), *nuevo]) + "\n"


def sin_privilegios_nuevos() -> bool:
    """Si este proceso corre con `no_new_privs` (Linux): el nodo de telar, que su servicio systemd lanza con
    `NoNewPrivileges=yes`, y todo lo que él lanza (las órdenes que le piden por el bus y la página)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            return any(linea.split() == ["NoNewPrivs:", "1"] for linea in f)
    except OSError:
        return False


def _crontab(*args: str, entrada: str | None = None) -> subprocess.CompletedProcess:
    """`crontab` con esos argumentos. En Linux, `crontab` lee y escribe `/var/spool/cron/crontabs` gracias a su bit
    setgid, que `no_new_privs` anula: ahí falla con «crontabs/<usuario>/: fopen: Permission denied», y una orden que
    llegaba por el nodo cambiaba `periodicos.toml` y dejaba el crontab como estaba. Si es el caso y hay systemd de
    usuario, corre como una unidad pasajera suya (`systemd-run --user`), que no hereda la restricción: el mismo
    usuario, el mismo `crontab`, sin nada más de lo que tendría desde su terminal."""
    orden = ["crontab", *args]
    if sin_privilegios_nuevos() and shutil.which("systemd-run"):
        orden = ["systemd-run", "--user", "--pipe", "--wait", "--quiet", "--collect", *orden]
    return subprocess.run(orden, input=entrada, capture_output=True, text=True,
                          stdin=None if entrada is not None else subprocess.DEVNULL)


def crontab_actual() -> str:
    r = _crontab("-l")
    if r.returncode != 0:
        if "no crontab" in (r.stderr or "").lower():
            return ""
        raise ErrorDePeriodicos(f"crontab -l falló: {r.stderr.strip()[-200:]}")
    return r.stdout


def aplicar(a: Archivo, telar: str) -> str:
    """Escribe el bloque en el crontab de esta máquina. Devuelve el crontab nuevo."""
    if not shutil.which("crontab"):
        raise ErrorDePeriodicos("esta máquina no tiene `crontab`")
    nuevo = con_bloque(crontab_actual(), bloque(a, telar))
    r = _crontab("-", entrada=nuevo)
    if r.returncode != 0:
        raise ErrorDePeriodicos(f"crontab no aceptó el bloque: {r.stderr.strip()[-300:]}")
    return nuevo


# ── correr ─────────────────────────────────────────────────────────────────────

def carpeta_estado(config) -> Path:
    return Path(config.estado) / "periodicos"


def ultima(config, nombre: str) -> dict:
    try:
        return json.loads((carpeta_estado(config) / f"{nombre}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def log(config, nombre: str, lineas: int = 80) -> str:
    try:
        texto_log = (carpeta_estado(config) / f"{nombre}.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(texto_log.splitlines()[-lineas:])


def _anotar(config, nombre: str, datos: dict) -> None:
    d = carpeta_estado(config)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{nombre}.json.tmp"
    tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, d / f"{nombre}.json")


def _recortar_log(ruta_log: Path) -> None:
    try:
        if ruta_log.stat().st_size > MAX_LOG:
            datos = ruta_log.read_bytes()[-MAX_LOG // 2:]
            ruta_log.write_bytes(datos[datos.find(b"\n") + 1:])
    except OSError:
        pass


def _entorno(config=None, modulo: str = "") -> dict:
    """cron corre con un PATH mínimo y sin idioma: sin UTF-8, tmux cambia los glifos por «_». El de un módulo
    (`modulo`, si está en `config`) lleva además lo que reciben sus órdenes (`telar.modulos.entorno`: la raíz, los
    repositorios, la máquina, su carpeta y la persona). Sin las marcas de quien lo disparó (`telar.entorno`): un
    `telar periodicos ahora` desde la Bash de un Claude Code le pasaría su sesión al comando, y un `claude -p` adentro se
    creería su hijo."""
    from telar import entorno as mod_entorno

    entorno = dict(os.environ)
    if modulo and config is not None:
        from telar import modulos as mod_modulos

        m = mod_modulos.buscar(config, modulo)
        if m is not None:
            entorno = mod_modulos.entorno(config, m)
    entorno = mod_entorno.sin_marcas(entorno)
    extra = [os.path.expanduser("~/.local/bin"), "/usr/local/bin", "/opt/homebrew/bin"]
    camino = entorno.get("PATH", "/usr/bin:/bin")
    # las que ya están no se repiten: el nodo corre los disparadores de cambio con esto, una y otra vez, en el
    # mismo proceso, y el PATH crecería en cada corrida
    ya = set(camino.split(os.pathsep))
    entorno["PATH"] = os.pathsep.join([*[d for d in extra if os.path.isdir(d) and d not in ya], camino])
    entorno.setdefault("LANG", "C.UTF-8")
    return entorno


def _preparar_entorno() -> list[str]:
    """El PATH y el LANG de `_entorno` en el entorno de este proceso, para lo que lanza tmux o el agente sin pasar
    `env`. Solo se escribe lo que cambia: en cron es una vez por proceso, pero el nodo corre los disparadores de
    cambio desde sus hilos, una y otra vez, y escribir `os.environ` mientras otro hilo lanza un subproceso es una
    carrera. Desde la segunda corrida ya no cambia nada, y no se escribe. Devuelve las claves que cambió."""
    quiere = _entorno()
    cambia = [k for k in ("PATH", "LANG") if os.environ.get(k) != quiere[k]]
    for k in cambia:
        os.environ[k] = quiere[k]
    return cambia


def correr(ctx, p: Proceso, ahora: datetime | None = None, manual: bool = False) -> dict:
    """Corre un proceso una vez y anota cómo salió. Devuelve lo anotado. `manual`: lo pidió alguien (`ahora`), no
    su horario; el calendario lo dibuja aparte."""
    ahora = ahora or datetime.now().astimezone()
    d = carpeta_estado(ctx.config)
    d.mkdir(parents=True, exist_ok=True)
    ruta_log = d / f"{p.nombre}.log"
    carpeta = Path(os.path.expanduser(p.carpeta)) if p.carpeta else Path.home()
    registro = {"inicio": ahora.isoformat(timespec="seconds"), "tipo": p.tipo, **({"manual": True} if manual else {})}
    _anotar(ctx.config, p.nombre, {**registro, "corriendo": True})
    with open(ruta_log, "a", encoding="utf-8") as f:
        f.write(f"\n── {ahora:%Y-%m-%d %H:%M:%S} · {p.nombre} ──\n")
        f.flush()
        if p.tipo == "comando":
            try:
                r = subprocess.run(["bash", "-lc", p.comando], cwd=carpeta if carpeta.is_dir() else None,
                                   stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   env=_entorno(ctx.config, p.modulo))
                codigo, resultado = r.returncode, ("ok" if r.returncode == 0 else f"salió con {r.returncode}")
            except OSError as e:
                codigo, resultado = 127, f"no corrió: {e}"
                f.write(resultado + "\n")
        elif p.agente:
            codigo, resultado, hilo = _encargar(ctx, p)
        else:
            codigo, resultado, hilo = _abrir_hilo(ctx, p, carpeta, ahora)
            f.write(resultado + "\n")
            if hilo:
                registro["hilo"] = hilo
    _recortar_log(ruta_log)
    fin = datetime.now().astimezone()
    registro.update({"fin": fin.isoformat(timespec="seconds"), "codigo": codigo, "resultado": resultado,
                     "segundos": round((fin - ahora).total_seconds(), 1)})
    _anotar(ctx.config, p.nombre, registro)
    _al_historial(ctx.config, p.nombre, registro)
    return registro


def _al_historial(config, nombre: str, registro: dict) -> None:
    """Una línea más en `<nombre>.historial.jsonl`: la corrida terminada. Al pasar de MAX_HISTORIAL, se queda con
    las más nuevas. Si no se puede escribir, la corrida igual quedó en su .json y su log."""
    ruta_h = carpeta_estado(config) / f"{nombre}.historial.jsonl"
    try:
        with open(ruta_h, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        if ruta_h.stat().st_size > MAX_HISTORIAL * 400:
            lineas = ruta_h.read_text(encoding="utf-8").splitlines()[-MAX_HISTORIAL:]
            tmp = ruta_h.with_name(ruta_h.name + ".tmp")
            tmp.write_text("\n".join(lineas) + "\n", encoding="utf-8")
            os.replace(tmp, ruta_h)
    except OSError:
        pass


def _encargar(ctx, p: Proceso) -> tuple[int, str, str]:
    """El prompt, encargado al agente residente: su hilo de siempre, no uno nuevo."""
    _preparar_entorno()
    from telar import agentes as mod_agentes
    from telar import encargos

    agente = next((a for a in mod_agentes.descubrir(ctx.config) if a.clave == p.agente), None)
    if agente is None:
        return 1, f"no hay un agente «{p.agente}» en [agentes] carpeta", ""
    from telar import bus as mod_bus

    problema_bus = ""
    if mod_bus.hay_bus(ctx.config):
        # por el bus: espera en su casilla y lo recoge el nodo de la máquina donde vive el agente, que
        # lo abre o lo avisa; el contenido entra por sus ganchos, sin teclearlo
        try:
            from telar import encargo as mod_encargo

            eid = mod_encargo.nuevo_id()
            r = mod_bus.enviar(ctx.config, agente.nombre, p.mensaje, de=f"periódico {p.nombre}", tipo="encargo",
                               modo="encargo", extra={"encargo": eid})
            mod_encargo.anotar_enviado(ctx.config, eid, para=agente.nombre, texto=p.mensaje, de=f"periódico {p.nombre}")
            return 0, f"encargado a «{agente.nombre}» por el bus · encargo:{eid}", agente.nombre
        except mod_bus.ErrorDeBus as e:
            problema_bus = f"el bus no lo recibió ({e}); "
    try:
        r = encargos.encargar(ctx, agente, p.mensaje, de=f"periódico {p.nombre}")
    except encargos.ErrorDeEncargo as e:
        return 1, f"no se pudo encargar a {agente.nombre}: {e}", ""
    dice = {"avisado": "le avisé", "en su casilla": "espera en su casilla (trabajaba)", "abierto": "abrí su sesión"}
    return 0, (f"{problema_bus}encargado a «{agente.nombre}»: {dice.get(r['estado'], r['estado'])} · "
               f"{r.get('direccion', '')}"), agente.nombre


#: un «trabajando» sin cambios por más de esto es un agente pegado, no uno que trabaja
TRABAJANDO_VIEJO = timedelta(hours=3)


def cerrar_viejos(config, abiertos, ahora: datetime) -> list[str]:
    """Cierra los hilos de este proceso que quedaron abiertos de otro día, sin nadie mirándolos y
    sin el agente trabajando. Devuelve sus nombres.

    Un hilo olvidado de anoche no puede impedir la pasada de hoy: el 6-oct un «▣ planear» del 5
    quedó abierto y no hubo plan del 7. Lo que alguien mira, o lo que un agente sigue haciendo, se
    respeta: ese sí cuenta para `max_abiertos`."""
    from telar import estado as mod_estado
    from telar import movil as mod_movil
    from telar.modelo import Atencion

    est = mod_estado.abrir(config)
    atenciones = est.atenciones()
    hoy = f"{ahora:%m/%d}"
    cerrados = []
    for h in abiertos:
        fecha = re.search(r"(\d{2}/\d{2}) \d{2}:\d{2}$", h.nombre)
        if not fecha or fecha.group(1) == hoy or h.clientes:
            continue
        atencion, desde = atenciones.get(h.nombre, (Atencion.NINGUNA, None))
        if atencion == Atencion.TRABAJANDO and desde is not None and ahora.timestamp() - desde.timestamp() < TRABAJANDO_VIEJO.total_seconds():
            continue
        try:
            mod_movil._tmux("kill-window", "-t", h.objetivo)
        except (RuntimeError, OSError):
            continue
        est.anotar_atencion(h.nombre, Atencion.NINGUNA)
        cerrados.append(h.nombre)
    return cerrados


def _abrir_hilo(ctx, p: Proceso, carpeta: Path, ahora: datetime) -> tuple[int, str, str]:
    """Un hilo nuevo con el agente y el prompt, si no hay ya `max_abiertos` de este proceso."""
    _preparar_entorno()
    from telar import movil as mod_movil
    from telar.agente import ErrorDeAgente, lanzar
    from telar import agente as mod_agente

    abiertos = [h for h in mod_movil.hilos(ctx.config.sesion) if h.nombre.startswith(p.nombre_hilo + " ")]
    viejos = cerrar_viejos(ctx.config, abiertos, ahora)
    abiertos = [h for h in abiertos if h.nombre not in viejos]
    if len(abiertos) >= p.max_abiertos:
        return 0, f"saltado: ya hay {len(abiertos)} «{p.nombre_hilo}» abiertos sin cerrar", ""
    if not ctx.config.agente.nombre:
        return 1, "un proceso con `mensaje` necesita un agente: [agente] nombre en config.toml", ""
    nombre = f"{p.nombre_hilo} {ahora:%m/%d %H:%M}"
    from telar import encargos

    encargos.liberar(ctx.config, 1)  # bajo `[agente] max_vivos`: antes de abrir, se cierran ociosas
    try:
        palabras, sid = mod_agente.obtener(ctx.config.agente.nombre, ctx.config).nuevo_con_id(p.mensaje)
        palabras = [*palabras, *p.argumentos]  # después del prompt: hay banderas que se tragan lo que sigue
        mod_movil.crear(nombre, str(carpeta), lanzar.envolver(palabras, nombre), ctx.config.sesion)
        lanzar.anotar(ctx.config, nombre, lanzar.Lanzamiento(comando=[], carpeta=carpeta, nueva=sid), por=f"periódico {p.nombre}")
    except (ErrorDeAgente, RuntimeError, OSError) as e:
        return 1, f"no pude abrir el hilo: {e}", ""
    cerre = f" (cerré {', '.join(f'«{v}»' for v in viejos)}: de otro día y quietos)" if viejos else ""
    return 0, f"abrí «{nombre}»{_colgar(ctx.config, nombre, p.padre)}{cerre}", nombre


def _colgar(config, hilo: str, padre: str) -> str:
    """El hilo recién abierto cuelga de `padre` y hereda sus etiquetas, como uno abierto con `telar hilo hijo`: en la
    barra va debajo, y el padre recibe el aviso de cada turno que termina. Lo que no se pudo, se dice (el hilo ya está
    abierto igual)."""
    if not padre:
        return ""
    from telar import estado as mod_estado

    try:
        est = mod_estado.abrir(config)
        est.colgar(hilo, padre)
        heredadas = est.etiquetas().get(padre, ())
        if heredadas and not est.etiquetas().get(hilo):
            est.etiquetar(hilo, list(heredadas))
    except (ValueError, OSError) as e:
        return f" (no pude colgarlo de «{padre}»: {e})"
    return f", hijo de «{padre}»"


def resumen(ctx, a: Archivo, ahora: datetime | None = None) -> list[dict]:
    """Lo que muestra `telar periodicos ver --json` y el dashboard, proceso por proceso."""
    nombres = {p.nombre for p in a.procesos}
    agentes = agentes_de(ctx.config)
    salida = []
    for p in a.procesos:
        sig = proxima(p, a.zona, ahora)
        salida.append({"nombre": p.nombre, "cuando": Horario(p.cuando).texto, "tipo": p.tipo,
                       "comando": p.comando, "mensaje": p.mensaje, "agente": p.agente, "hilo": p.hilo,
                       "padre": p.padre, "max_abiertos": p.max_abiertos,
                       "argumentos": list(p.argumentos), "carpeta": p.carpeta, "descripcion": p.descripcion,
                       "activo": p.activo, "modulo": p.modulo, "disparador": p.disparador, "proxima": sig.isoformat(timespec="minutes") if sig else "",
                       "despues": list(p.despues), "despues_falta": [x for x in p.despues if x not in nombres],
                       "destino": destino(p, agentes),
                       "ultima": ultima(ctx.config, p.nombre)})
    return salida


# ── a quién le llega: las dependencias que no se declaran ──────────────────────

#: `telar encargar <agente>` en un comando o en su script: el agente al que le llega, aunque el proceso sea un comando
_ENCARGA = re.compile(r"\btelar\s+encargar\s+(?:--?[\w-]+(?:=\S+)?\s+)*[\"']?([\w.-]+)")


def agentes_de(config) -> list[dict]:
    """Los agentes residentes de esta máquina, como los lista el formulario: a quién se le puede encargar."""
    from telar import agentes as mod_agentes

    try:
        return [{"clave": x.clave, "nombre": x.nombre, "carpeta": str(x.carpeta), "icono": x.icono}
                for x in mod_agentes.descubrir(config)]
    except Exception:  # noqa: BLE001 - sin agentes (o con su carpeta rota) la lista igual se muestra
        return []


def _encarga(p: Proceso) -> str:
    """El agente al que encarga un comando: en su texto, o en el script que corre (si es un archivo de texto chico)."""
    m = _ENCARGA.search(p.comando)
    if m:
        return m.group(1)
    try:
        primera = shlex.split(p.comando)[0] if p.comando.strip() else ""
    except ValueError:
        return ""
    if not primera or primera in ("if", "for", "while", "[", "test"):
        return ""
    ruta_s = Path(os.path.expanduser(primera))
    if not ruta_s.is_absolute():
        ruta_s = Path(os.path.expanduser(p.carpeta or "~")) / ruta_s
    try:
        if ruta_s.is_file() and ruta_s.stat().st_size < 64 * 1024:
            m = _ENCARGA.search(ruta_s.read_text(encoding="utf-8", errors="replace"))
            return m.group(1) if m else ""
    except OSError:
        pass
    return ""


def _sin_tildes(s: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def destino(p: Proceso, agentes: list[dict] | None = None) -> dict:
    """A quién le llega cada corrida: `agente` (su clave; `inferido` si sale de un comando que encarga), `hilo` (uno
    nuevo cada vez) o `comando` (corre solo, sin agente). Dos que van al mismo agente comparten su casilla."""
    if p.tipo == "mensaje":
        return {"tipo": "agente", "agente": p.agente, "inferido": False} if p.agente else \
            {"tipo": "hilo", "agente": "", "inferido": False}
    dice = _encarga(p)
    if not dice:
        return {"tipo": "comando", "agente": "", "inferido": False}
    # el comando puede nombrarlo por su clave o por su nombre («secretaria», «Secretaría»)
    clave = next((x["clave"] for x in agentes or () if _sin_tildes(dice) in (_sin_tildes(x["clave"]), _sin_tildes(x["nombre"]))), dice)
    return {"tipo": "agente", "agente": clave, "inferido": True}


# ── el calendario: lo que corrió y lo que viene ────────────────────────────────

#: una corrida se reconoce en su horario si empezó hasta tanto después (cron tarda unos segundos; una máquina
#: cargada, más) o un poco antes
_TOLERANCIA = (timedelta(minutes=1), timedelta(minutes=10))
_CABEZA_LOG = re.compile(r"^── (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) · (\S+) ──$")


def _del_historial(config, nombre: str) -> list[dict]:
    try:
        lineas = (carpeta_estado(config) / f"{nombre}.historial.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    salida = []
    for linea in lineas:
        try:
            r = json.loads(linea)
            r["_t"] = datetime.fromisoformat(r["inicio"])
        except (ValueError, KeyError, TypeError):
            continue
        salida.append(r)
    return salida


def _del_log(config, nombre: str) -> list[dict]:
    """Las corridas que solo dejó su log (las de antes del historial): cuándo empezaron y, si lo escribió (un hilo
    que abrió o se saltó), cómo salió."""
    try:
        lineas = (carpeta_estado(config) / f"{nombre}.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    salida = []
    for i, linea in enumerate(lineas):
        m = _CABEZA_LOG.match(linea)
        if not m or m.group(2) != nombre:
            continue
        try:
            t = datetime.fromisoformat(m.group(1)).astimezone()   # la hora de la máquina, que la escribió
        except ValueError:
            continue
        r: dict = {"_t": t, "inicio": t.isoformat(timespec="seconds")}
        sigue = lineas[i + 1].strip() if i + 1 < len(lineas) else ""
        if sigue.startswith("saltado"):
            r.update(codigo=0, resultado=sigue)
        elif sigue.startswith(("abrí ", "encargado ")):
            r.update(codigo=0, resultado=sigue)
        elif sigue.startswith(("no pude", "no se pudo", "no hay un agente", "un proceso con")):
            r.update(codigo=1, resultado=sigue)
        salida.append(r)
    return salida


def _estado(r: dict) -> str:
    if r.get("corriendo"):
        return "corriendo"
    if "codigo" not in r:
        return "corrio"
    if r["codigo"] != 0:
        return "fallo"
    return "saltado" if str(r.get("resultado", "")).startswith("saltado") else "bien"


def corridas(ctx, a: Archivo, desde, dias: int = 7, ahora: datetime | None = None) -> dict[str, list[dict]]:
    """Las corridas de cada proceso en `dias` días desde `desde` (una fecha, en la zona del archivo): las de su
    horario, con cómo salieron las que ya pasaron, y las que alguien pidió fuera de horario (`manual`).

    Cada una: `dia` y `min` (el minuto del día, en la zona: así la página no hace cuentas de zona), `en` (ISO) y
    `estado`: bien, fallo, saltado (ya había hilos abiertos), corrio (solo quedó su log: sin resultado), corriendo,
    falto (le tocaba y no hay rastro, aunque hay registro de antes), sin-registro (antes de todo registro), proxima
    o pausado (las que vienen)."""
    from datetime import time as hora

    tz = zona_info(a.zona)
    ahora = (ahora or datetime.now(tz)).astimezone(tz)
    inicio = datetime.combine(desde, hora(0), tz)
    fin = inicio + timedelta(days=max(1, min(dias, 31)))
    antes, despues = _TOLERANCIA
    salida: dict[str, list[dict]] = {}

    def una(t: datetime, estado: str, r: dict | None = None) -> dict:
        t = t.astimezone(tz)
        c = {"dia": t.date().isoformat(), "min": t.hour * 60 + t.minute, "en": t.isoformat(timespec="minutes"), "estado": estado}
        if r:
            for k in ("resultado", "hilo", "manual"):
                if r.get(k):
                    c[k] = r[k]
        return c

    for p in a.procesos:
        hist = _del_historial(ctx.config, p.nombre)
        desde_hist = min((r["_t"] for r in hist), default=None)
        regs = hist + [r for r in _del_log(ctx.config, p.nombre) if desde_hist is None or r["_t"] < desde_hist - antes]
        u = ultima(ctx.config, p.nombre)
        if u.get("corriendo") and u.get("inicio"):
            try:
                regs.append({**u, "_t": datetime.fromisoformat(u["inicio"])})
            except ValueError:
                pass
        primero = min((r["_t"] for r in regs), default=None)
        regs = [r for r in regs if inicio - despues <= r["_t"] < fin + antes]
        usados: set[int] = set()
        lista = []
        h = Horario(p.cuando)
        t = h.proxima(inicio - timedelta(minutes=1))
        while t is not None and t < fin and len(lista) < 3000:
            cerca = [i for i, r in enumerate(regs) if i not in usados and t - antes <= r["_t"] <= t + despues]
            if cerca:
                i = min(cerca, key=lambda k: abs((regs[k]["_t"] - t).total_seconds()))
                usados.add(i)
                lista.append(una(t, _estado(regs[i]), regs[i]))
            elif t > ahora - timedelta(minutes=2):
                lista.append(una(t, "proxima" if p.activo else "pausado"))
            elif p.activo and primero is not None and t >= primero:
                lista.append(una(t, "falto"))
            else:
                lista.append(una(t, "sin-registro"))
            t = h.proxima(t)
        # las de fuera de horario: alguien la corrió a mano, o el horario era otro
        for i, r in enumerate(regs):
            if i not in usados and inicio <= r["_t"] < fin:
                lista.append({**una(r["_t"], _estado(r), r), "manual": True})
        salida[p.nombre] = sorted(lista, key=lambda c: c["en"])
    return salida
