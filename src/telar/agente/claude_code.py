"""El adaptador de Claude Code: sus ganchos, sus conversaciones, su instalador.

Claude Code avisa lo que le pasa por *hooks*: programas que corre en momentos fijos y
a los que les manda un JSON por la entrada estándar. Este módulo traduce esos momentos
a los seis eventos de `telar.agente.base` y sabe escribir los ganchos en la
configuración del usuario.

    momento de Claude Code   evento de telar   qué queda
    ──────────────────────────────────────────────────────────────────────────────
    SessionStart             abre              este hilo tiene esta conversación
    UserPromptSubmit         empieza           atención: trabajando
    Notification             espera            atención: espera
    PostToolUse              sigue             desmiente un «espera» anterior
    SubagentStop             sigue             lo mismo: sigue vivo
    Stop                     termina           atención: terminó
    SessionEnd               cierra            atención: ninguna

Los seis se enganchan al **mismo** comando —`telar agente aviso claude-code`— y cuál
fue viene en el JSON (`hook_event_name`). Una sola línea que mantener, y un solo lugar
donde equivocarse.

Dos detalles de Claude Code que se pagan si no se saben:

  * la carpeta de configuración es `~/.claude`, salvo que `$CLAUDE_CONFIG_DIR` diga
    otra; ahí están `settings.json` y las conversaciones;
  * las conversaciones se guardan en `projects/<carpeta con la ruta aplanada>/<id>.jsonl`.
    Cómo se aplana la ruta es cosa de Claude Code y cambia sin avisar, así que aquí
    **no se reconstruye**: se busca el archivo por su nombre, que es el id.
"""

from __future__ import annotations

import json
import os
import shlex
import tempfile
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from telar.agente import Conversacion, ErrorDeAgente, registrar
from telar.agente.base import MARCA_AVISO, AgenteBase, Aviso, Evento, Gancho, Instalacion, comando_aviso

__all__ = [
    "ClaudeCode",
    "NOMBRE",
    "EVENTOS",
    "GANCHOS",
    "MARCA",
    "construir",
    "carpeta_config",
    "ruta_ajustes",
]

#: Cómo se nombra este agente en la configuración y en `telar agente`.
NOMBRE = "claude-code"

#: El ejecutable; `TELAR_CLAUDE` lo pisa, para una máquina donde se llame de otra forma.
VARIABLE_BINARIO = "TELAR_CLAUDE"

#: Lo que delata a Claude Code en el proceso de un panel.
COMANDOS = ("claude", "claude-code")

#: Momento de Claude Code → evento de telar.
EVENTOS: dict[str, Evento] = {
    "SessionStart": Evento.ABRE,
    "UserPromptSubmit": Evento.EMPIEZA,
    "Notification": Evento.ESPERA,
    "PostToolUse": Evento.SIGUE,
    "SubagentStop": Evento.SIGUE,
    "Stop": Evento.TERMINA,
    "SessionEnd": Evento.CIERRA,
}

#: Los ganchos que instala telar. `PostToolUse` se dispara a cada rato: tope corto.
GANCHOS: tuple[Gancho, ...] = (
    Gancho(Evento.ABRE, "SessionStart"),
    Gancho(Evento.EMPIEZA, "UserPromptSubmit"),
    Gancho(Evento.ESPERA, "Notification"),
    Gancho(Evento.SIGUE, "PostToolUse", filtro="*", espera=3),
    Gancho(Evento.TERMINA, "Stop"),
    Gancho(Evento.CIERRA, "SessionEnd"),
)

#: Con esto se reconocen los ganchos de telar dentro de un `settings.json` ajeno.
MARCA = f"agente aviso {NOMBRE}"

#: El nombre del primer respaldo que se deja antes de tocar la configuración del usuario.
SUFIJO_RESPALDO = ".telar.bak"

#: Si ese nombre ya está ocupado, el respaldo lleva fecha y el anterior queda intacto.
FORMATO_RESPALDO = ".telar.{marca}.bak"

#: Cuántos respaldos del mismo segundo se toleran antes de darse por vencido.
TOPE_RESPALDOS = 100


def carpeta_config() -> Path:
    """Dónde guarda Claude Code lo suyo en esta máquina."""
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(base).expanduser() if base else Path.home() / ".claude"


def ruta_ajustes() -> Path:
    """El `settings.json` del usuario, que es donde viven los ganchos."""
    return carpeta_config() / "settings.json"


class ClaudeCode(AgenteBase):
    """Claude Code, visto desde telar."""

    nombre = NOMBRE
    comandos = COMANDOS

    # ── conversaciones ──────────────────────────────────────────────────────────

    def archivo_de(self, conversacion: Conversacion | str) -> Path | None:
        """El `.jsonl` de una conversación, si está en disco.

        Se busca por nombre y no se arma la ruta: la carpeta que Claude Code le da a
        cada proyecto sale de aplanar el `cwd`, y esa receta es suya, no nuestra.
        """
        sid = conversacion if isinstance(conversacion, str) else conversacion.id
        if not sid:
            return None
        proyectos = carpeta_config() / "projects"
        try:
            return next(proyectos.glob(f"*/{sid}.jsonl"), None)
        except OSError:
            return None

    def mensajes(self, conversacion: Conversacion | str) -> list[dict] | None:
        """Lee el `.jsonl`: lo que escribió la persona, lo que contestó el agente, y una
        línea por herramienta. El razonamiento no se guarda legible y se omite, igual que
        los mensajes que son solo resultados de herramientas."""
        archivo = self.archivo_de(conversacion)
        if archivo is None:
            return None
        salida: list[dict] = []
        try:
            lineas = archivo.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return None
        for linea in lineas:
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            if not isinstance(d, dict) or d.get("isMeta"):
                continue
            tipo, m = d.get("type"), d.get("message") or {}
            contenido = m.get("content") if isinstance(m, dict) else None
            hora = d.get("timestamp") or ""
            if tipo == "user" and isinstance(contenido, str):
                texto = _sin_marcas(contenido)
                if texto:
                    salida.append({"quien": "usuario", "hora": hora, "texto": texto})
            elif tipo == "assistant" and isinstance(contenido, list):
                for x in contenido:
                    if not isinstance(x, dict):
                        continue
                    if x.get("type") == "text" and str(x.get("text", "")).strip():
                        salida.append({"quien": "agente", "hora": hora, "texto": x["text"].strip()})
                    elif x.get("type") == "tool_use":
                        salida.append({"quien": "herramienta", "hora": hora,
                                       "texto": _herramienta(x.get("name", ""), x.get("input") or {})})
        return salida

    def retomar(self, conversacion: Conversacion) -> list[str]:
        """Volver a esa conversación. No la corre: la devuelve para que decida quien pueda."""
        if not conversacion.id:
            raise ErrorDeAgente("no hay conversación que retomar")
        return [self.binario, "--resume", conversacion.id]

    def nuevo(self, ruta: Path | None = None) -> list[str]:
        """Una conversación nueva. La carpeta la pone el panel donde se abra, no una bandera."""
        return [self.binario]

    def nuevo_con_id(self, mensaje: str = "", id: str = "") -> tuple[list[str], str]:
        """Claude Code acepta `--session-id`: el id lo elige telar, y queda guardado desde ya.

        Con `--resume` Claude conserva ese mismo id, así que archivar y retomar se puede
        repetir sin perder el hilo. Lo único que lo cambia es `/clear` dentro de Claude,
        que abre otra conversación: esa solo la conoce telar si están los ganchos.
        """
        import uuid

        # `id` es para abrir con el id que el hilo ya tenía: una conversación sin mensajes
        # no dejó archivo, y darle otro id le cambiaría la conversación al hilo por nada
        sid = id or str(uuid.uuid4())
        palabras = [self.binario, "--session-id", sid]
        return ([*palabras, mensaje] if mensaje else palabras), sid

    @property
    def binario(self) -> str:
        return os.environ.get(VARIABLE_BINARIO) or "claude"

    # ── lo que llega por el gancho ──────────────────────────────────────────────

    def leer_aviso(self, crudo: Mapping[str, object], *, evento: Evento | None = None) -> Aviso:
        """El JSON que manda un hook de Claude Code, traducido.

        Lo que no se entiende se dice en voz alta: un gancho que llegue con un momento
        desconocido significa que Claude Code cambió y que hay que mirar esta tabla.
        """
        nativo = str(crudo.get("hook_event_name") or "")
        elegido = evento or EVENTOS.get(nativo)
        if elegido is None:
            conocidos = ", ".join(sorted(EVENTOS))
            raise ErrorDeAgente(
                f"no sé qué hacer con «{nativo or 'un aviso sin hook_event_name'}»;"
                f" los que conozco: {conocidos}"
            )
        cwd = str(crudo.get("cwd") or "")
        return Aviso(
            evento=elegido,
            agente=self.nombre,
            sesion=str(crudo.get("session_id") or ""),
            ruta=Path(cwd) if cwd else None,
            cuando=datetime.now(),
            datos={"nativo": nativo, "transcripcion": str(crudo.get("transcript_path") or "")},
        )

    def comandos_instalados(self) -> tuple[str, ...]:
        datos = _leer_ajustes(self.ruta_ajustes())
        hooks = datos.get("hooks") if isinstance(datos, dict) else None
        if not isinstance(hooks, dict):
            return ()
        vistos: list[str] = []
        for grupos in hooks.values():
            for grupo in grupos if isinstance(grupos, list) else []:
                for gancho in (grupo or {}).get("hooks", []) if isinstance(grupo, dict) else []:
                    comando = gancho.get("command", "") if isinstance(gancho, dict) else ""
                    if MARCA_AVISO in comando and comando not in vistos:
                        vistos.append(comando)
        return tuple(vistos)

    def ganchos(self) -> tuple[Gancho, ...]:
        return GANCHOS

    # ── instalarse ──────────────────────────────────────────────────────────────

    def ruta_ajustes(self) -> Path:
        # la función de este módulo, no este método: un método no ve el ámbito de su clase
        return ruta_ajustes()

    def instalar(
        self,
        *,
        ruta: Path | None = None,
        ejecutable: Sequence[str] | None = None,
        seco: bool = False,
    ) -> Instalacion:
        """Escribe los ganchos de telar en el `settings.json` del usuario.

        Respeta lo que ya estaba: se mezcla con los ganchos ajenos y solo se reemplazan
        los de telar, que se reconocen por su comando. Antes de tocar nada deja un
        respaldo al lado —sin pisar el que hubiera de una vez anterior—, y escribe a un
        temporal que después renombra, para que nadie lea el archivo a medio escribir.
        """
        destino = Path(ruta).expanduser() if ruta else self.ruta_ajustes()
        datos = _leer_ajustes(destino)
        palabras = comando_aviso(self.nombre, ejecutable=ejecutable)
        nuevos, puestos, reemplazados = _mezclar(datos, self.ganchos(), shlex.join(palabras))
        texto = json.dumps(nuevos, ensure_ascii=False, indent=2) + "\n"
        antes = _texto_actual(destino)
        respaldo = None
        if not seco:
            respaldo = _escribir(destino, texto)
        return Instalacion(
            ruta=destino,
            ganchos=tuple(puestos),
            escrito=not seco,
            respaldo=respaldo,
            texto=texto,
            reemplazados=tuple(reemplazados),
            antes=antes,
            comando=tuple(palabras),
        )

    def desinstalar(self, *, ruta: Path | None = None, seco: bool = False) -> Instalacion:
        """Saca de la configuración los ganchos de telar, y nada más."""
        destino = Path(ruta).expanduser() if ruta else self.ruta_ajustes()
        datos = _leer_ajustes(destino)
        nuevos, sacados = _quitar(datos)
        texto = json.dumps(nuevos, ensure_ascii=False, indent=2) + "\n"
        antes = _texto_actual(destino)
        respaldo = None
        if not seco and sacados:
            respaldo = _escribir(destino, texto)
        return Instalacion(
            ruta=destino,
            ganchos=(),
            escrito=bool(sacados) and not seco,
            respaldo=respaldo,
            texto=texto,
            reemplazados=tuple(sacados),
            antes=antes,
        )


# ── el settings.json, tratado como ajeno ────────────────────────────────────────


def _leer_ajustes(ruta: Path) -> dict:
    """La configuración del agente. Sin archivo, un diccionario vacío.

    Un JSON roto **no** se pisa: es la configuración de otro programa y borrarla por
    no entenderla sería el peor final posible de una orden que se llama «instalar».
    """
    if not ruta.exists():
        return {}
    try:
        crudo = ruta.read_text(encoding="utf-8")
    except OSError as e:
        raise ErrorDeAgente(f"{ruta}: no se pudo leer: {e}") from e
    if not crudo.strip():
        return {}
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError as e:
        raise ErrorDeAgente(
            f"{ruta}: no es JSON válido ({e}). No lo toco: arréglalo y vuelve a intentar."
        ) from e
    if not isinstance(datos, dict):
        raise ErrorDeAgente(f"{ruta}: se esperaba un objeto JSON, hay {type(datos).__name__}")
    return datos


def _texto_actual(ruta: Path) -> str:
    """El archivo tal como está hoy, para poder mostrar qué cambiaría. Nunca revienta.

    Es para mirar, no para decidir: quien necesite entender el contenido pasa por
    `_leer_ajustes`, que sí se planta ante un JSON que no entiende.
    """
    try:
        return ruta.read_text(encoding="utf-8")
    except OSError:
        return ""


def _respaldar(ruta: Path, modo: int) -> Path:
    """Una copia de `ruta` al lado, que no pisa a ninguna anterior ni afloja sus permisos.

    El primer respaldo se llama `<nombre>.telar.bak`. Si ese nombre ya está ocupado —un
    segundo `instalar`, o el `desinstalar` que viene después—, el nuevo lleva la fecha.
    El retrato del archivo *antes* de telar es justo el que hace falta cuando algo sale
    mal, así que la orden que deshace telar no puede ser la que lo destruye.

    El archivo nace privado y recién después toma los permisos del original: una
    configuración que nadie más podía leer no queda legible ni mientras se copia.
    """
    nombre = ruta.name + SUFIJO_RESPALDO
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    for intento in range(TOPE_RESPALDOS + 1):
        destino = ruta.with_name(nombre)
        try:
            fd = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            cola = marca if intento == 0 else f"{marca}-{intento + 1}"
            nombre = ruta.name + FORMATO_RESPALDO.format(marca=cola)
            continue
        with os.fdopen(fd, "wb") as fh:
            fh.write(ruta.read_bytes())
        os.chmod(destino, modo)
        return destino
    raise ErrorDeAgente(
        f"{ruta}: ya hay demasiados respaldos al lado; saca los «{SUFIJO_RESPALDO}» viejos"
    )


def _escribir(ruta: Path, texto: str) -> Path | None:
    """Deja el texto en `ruta`, con respaldo al lado y sin estados intermedios."""
    respaldo: Path | None = None
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        modo = (ruta.stat().st_mode & 0o777) if ruta.exists() else None
        if modo is not None:
            respaldo = _respaldar(ruta, modo)
        fd, tmp = tempfile.mkstemp(dir=str(ruta.parent), prefix=ruta.name, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(texto)
        if modo is not None:
            # el temporal nace 0600: el archivo del usuario conserva los permisos que tenía
            os.chmod(tmp, modo)
        os.replace(tmp, ruta)
    except OSError as e:
        raise ErrorDeAgente(f"{ruta}: no se pudo escribir: {e}") from e
    return respaldo


def _nuestro(gancho: object) -> bool:
    """¿Este gancho lo puso telar? Se reconoce por el comando, que es nuestro."""
    if not isinstance(gancho, dict):
        return False
    comando = gancho.get("command")
    return isinstance(comando, str) and MARCA in comando


def _limpiar(entradas: list) -> tuple[list, int]:
    """La lista de un evento sin los ganchos de telar. Devuelve también cuántos salieron."""
    quedan: list = []
    fuera = 0
    for entrada in entradas:
        adentro = entrada.get("hooks") if isinstance(entrada, dict) else None
        if not isinstance(adentro, list) or not adentro:
            quedan.append(entrada)
            continue
        limpios = [g for g in adentro if not _nuestro(g)]
        fuera += len(adentro) - len(limpios)
        if limpios:
            quedan.append({**entrada, "hooks": limpios})
    return quedan, fuera


def _entrada(gancho: Gancho, comando: str) -> dict:
    cuerpo: dict = {"hooks": [{"type": "command", "command": comando, "timeout": gancho.espera}]}
    if gancho.filtro:
        cuerpo = {"matcher": gancho.filtro, **cuerpo}
    return cuerpo


def _mezclar(
    datos: dict, ganchos: Sequence[Gancho], comando: str
) -> tuple[dict, list[str], list[str]]:
    """La configuración con los ganchos de telar puestos. No muta lo que recibe."""
    nuevos = deepcopy(datos)
    hooks = nuevos.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ErrorDeAgente("«hooks» no es un objeto: no voy a reescribir algo que no entiendo")

    puestos: list[str] = []
    reemplazados: list[str] = []
    for gancho in ganchos:
        entradas = hooks.get(gancho.nativo, [])
        if not isinstance(entradas, list):
            raise ErrorDeAgente(
                f"hooks.{gancho.nativo} no es una lista: no voy a reescribir algo que no entiendo"
            )
        limpias, fuera = _limpiar(entradas)
        if fuera:
            reemplazados.append(gancho.nativo)
        hooks[gancho.nativo] = [*limpias, _entrada(gancho, comando)]
        puestos.append(gancho.nativo)
    return nuevos, puestos, reemplazados


def _quitar(datos: dict) -> tuple[dict, list[str]]:
    """La configuración sin los ganchos de telar. Lo que queda vacío se va con ellos."""
    nuevos = deepcopy(datos)
    hooks = nuevos.get("hooks")
    if not isinstance(hooks, dict):
        return nuevos, []
    sacados: list[str] = []
    for nativo, entradas in list(hooks.items()):
        if not isinstance(entradas, list):
            continue
        limpias, fuera = _limpiar(entradas)
        if not fuera:
            continue
        sacados.append(nativo)
        if limpias:
            hooks[nativo] = limpias
        else:
            hooks.pop(nativo)
    if not hooks:
        nuevos.pop("hooks", None)
    return nuevos, sacados


def construir(config) -> ClaudeCode:
    """La fábrica que pide el registro de `telar.agente`."""
    return ClaudeCode(config)


registrar(NOMBRE, construir)


def _sin_marcas(texto: str) -> str:
    """Lo que la persona escribió, sin el envoltorio con que Claude Code guarda una skill."""
    import re

    texto = re.sub(r"<command-message>.*?</command-message>\s*", "", texto, flags=re.S)
    texto = re.sub(r"<command-name>(.*?)</command-name>", r"\1", texto)
    texto = re.sub(r"</?command-args>", "", texto)
    if texto.lstrip().startswith(("<local-command", "<system-reminder", "Caveat:")):
        return ""
    return texto.strip()


def _herramienta(nombre: str, entrada: Mapping[str, object]) -> str:
    """Una herramienta en una línea: cuál, y lo que la distingue de otra llamada igual."""
    for clave in ("description", "command", "file_path", "pattern", "url", "query", "prompt"):
        valor = entrada.get(clave) if isinstance(entrada, Mapping) else None
        if isinstance(valor, str) and valor.strip():
            detalle = " ".join(valor.split())
            return f"{nombre} · {detalle[:160]}{'…' if len(detalle) > 160 else ''}"
    return nombre

