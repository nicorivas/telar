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
    max_abiertos = 2                   # si ya hay tantos abiertos sin cerrar, esta vez no abre
    argumentos = ["--permission-mode", "acceptEdits"]   # para el agente, después del prompt
    carpeta = "~/trabajo"              # dónde corre (por defecto, el hogar)
    activo = false                     # pausado: no corre, pero no se olvida

    [avanzar]
    cuando = "0 9-19/2 * * 1-5"
    mensaje = "/avanzar"
    agente = "gestion"                 # se le encarga al agente residente (telar.encargos) en vez de
                                       # abrir un hilo nuevo cada vez: una sola sesión que dura

`telar periodicos aplicar` escribe en el crontab de la máquina un bloque entre marcas con una
línea por proceso activo, y no toca nada fuera de él. Cada línea llama a `telar periodicos correr
<nombre>`, que anota inicio, fin y resultado en `<estado>/periodicos/<nombre>.json` y la salida en
`<nombre>.log`: de ahí sale lo que muestra el dashboard (la última corrida, si salió bien, el log).
Cambiar el archivo desde telar guarda la versión anterior en `periodicos.toml.anterior`.

Los hilos que abre un proceso con `mensaje` son sesiones tmux `telar-…` con `@telar_hilo`, la misma
convención de los hilos remotos: otra máquina los trae a su lista (`telar remotos traer`).
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
CLAVES = ("cuando", "comando", "mensaje", "agente", "hilo", "max_abiertos", "argumentos", "carpeta", "descripcion", "activo")


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
    max_abiertos: int = 1
    argumentos: tuple[str, ...] = ()
    carpeta: str = ""
    descripcion: str = ""
    activo: bool = True

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
        if self.max_abiertos < 1:
            raise ErrorDePeriodicos(f"«{self.nombre}»: max_abiertos va desde 1")
        if "\n" in self.comando or "\n" in self.cuando:
            raise ErrorDePeriodicos(f"«{self.nombre}»: el comando y el horario van en una línea")


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
                        hilo=str(cuerpo.get("hilo", "")),
                        max_abiertos=int(cuerpo.get("max_abiertos", 1)),
                        argumentos=tuple(str(x) for x in cuerpo.get("argumentos", ())),
                        carpeta=str(cuerpo.get("carpeta", "")), descripcion=str(cuerpo.get("descripcion", "")),
                        activo=bool(cuerpo.get("activo", True)))
        except (TypeError, ValueError) as e:
            raise ErrorDePeriodicos(f"{destino}: [{nombre}]: {e}") from e
        p.validar()
        procesos.append(p)
    zona_info(zona)
    return Archivo(zona=zona, procesos=procesos)


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
    if "argumentos" in campos:
        campos["argumentos"] = tuple(campos["argumentos"])
    # cambiar de comando a mensaje (o al revés) deja el otro vacío
    if campos.get("comando"):
        campos.setdefault("mensaje", "")
        campos.setdefault("agente", "")
    if campos.get("mensaje"):
        campos.setdefault("comando", "")
    nuevo = replace(p, **campos)
    nuevo.validar()
    a.procesos[a.procesos.index(p)] = nuevo
    return nuevo


# ── el crontab ─────────────────────────────────────────────────────────────────

def bloque(a: Archivo, telar: str) -> list[str]:
    """Las líneas del bloque de telar en el crontab. Los pausados quedan comentados, a la vista."""
    lineas = [MARCA_INICIO]
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


def crontab_actual() -> str:
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
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
    r = subprocess.run(["crontab", "-"], input=nuevo, capture_output=True, text=True)
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


def _entorno() -> dict:
    """cron corre con un PATH mínimo y sin idioma: sin UTF-8, tmux cambia los glifos por «_»."""
    entorno = dict(os.environ)
    extra = [os.path.expanduser("~/.local/bin"), "/usr/local/bin", "/opt/homebrew/bin"]
    entorno["PATH"] = os.pathsep.join([*[d for d in extra if os.path.isdir(d)], entorno.get("PATH", "/usr/bin:/bin")])
    entorno.setdefault("LANG", "C.UTF-8")
    return entorno


def correr(ctx, p: Proceso, ahora: datetime | None = None) -> dict:
    """Corre un proceso una vez y anota cómo salió. Devuelve lo anotado."""
    ahora = ahora or datetime.now().astimezone()
    d = carpeta_estado(ctx.config)
    d.mkdir(parents=True, exist_ok=True)
    ruta_log = d / f"{p.nombre}.log"
    carpeta = Path(os.path.expanduser(p.carpeta)) if p.carpeta else Path.home()
    registro = {"inicio": ahora.isoformat(timespec="seconds"), "tipo": p.tipo}
    _anotar(ctx.config, p.nombre, {**registro, "corriendo": True})
    with open(ruta_log, "a", encoding="utf-8") as f:
        f.write(f"\n── {ahora:%Y-%m-%d %H:%M:%S} · {p.nombre} ──\n")
        f.flush()
        if p.tipo == "comando":
            try:
                r = subprocess.run(["bash", "-lc", p.comando], cwd=carpeta if carpeta.is_dir() else None,
                                   stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=_entorno())
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
    return registro


def _encargar(ctx, p: Proceso) -> tuple[int, str, str]:
    """El prompt, encargado al agente residente: su hilo de siempre, no uno nuevo."""
    os.environ.update({k: v for k, v in _entorno().items() if k in ("PATH", "LANG")})
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
            r = mod_bus.enviar(ctx.config, agente.nombre, p.mensaje, de=f"periódico {p.nombre}", tipo="encargo")
            return 0, f"encargado a «{agente.nombre}» por el bus · id {r['id']}", agente.nombre
        except mod_bus.ErrorDeBus as e:
            problema_bus = f"el bus no lo recibió ({e}); "
    try:
        r = encargos.encargar(ctx, agente, p.mensaje)
    except encargos.ErrorDeEncargo as e:
        return 1, f"no se pudo encargar a {agente.nombre}: {e}", ""
    dice = {"entregado": "le escribí", "en cola": f"quedó en cola ({r.get('en_cola')})", "abierto": "abrí su sesión"}
    return 0, f"{problema_bus}encargado a «{agente.nombre}»: {dice.get(r['estado'], r['estado'])}", agente.nombre


def _abrir_hilo(ctx, p: Proceso, carpeta: Path, ahora: datetime) -> tuple[int, str, str]:
    """Un hilo nuevo con el agente y el prompt, si no hay ya `max_abiertos` de este proceso."""
    os.environ.update({k: v for k, v in _entorno().items() if k in ("PATH", "LANG")})
    from telar import movil as mod_movil
    from telar.agente import ErrorDeAgente, lanzar
    from telar import agente as mod_agente

    abiertos = [h for h in mod_movil.hilos() if h.nombre.startswith(p.nombre_hilo + " ")]
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
        mod_movil.crear(nombre, str(carpeta), lanzar.envolver(palabras, nombre))
        lanzar.anotar(ctx.config, nombre, lanzar.Lanzamiento(comando=[], carpeta=carpeta, nueva=sid))
    except (ErrorDeAgente, RuntimeError, OSError) as e:
        return 1, f"no pude abrir el hilo: {e}", ""
    return 0, f"abrí «{nombre}»", nombre


def resumen(ctx, a: Archivo, ahora: datetime | None = None) -> list[dict]:
    """Lo que muestra `telar periodicos ver --json` y el dashboard, proceso por proceso."""
    salida = []
    for p in a.procesos:
        sig = proxima(p, a.zona, ahora)
        salida.append({"nombre": p.nombre, "cuando": Horario(p.cuando).texto, "tipo": p.tipo,
                       "comando": p.comando, "mensaje": p.mensaje, "agente": p.agente, "hilo": p.hilo,
                       "max_abiertos": p.max_abiertos,
                       "argumentos": list(p.argumentos), "carpeta": p.carpeta, "descripcion": p.descripcion,
                       "activo": p.activo, "proxima": sig.isoformat(timespec="minutes") if sig else "",
                       "ultima": ultima(ctx.config, p.nombre)})
    return salida
