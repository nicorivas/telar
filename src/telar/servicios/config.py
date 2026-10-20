"""La configuración resuelta: con qué valores trabaja telar en esta máquina y de dónde salieron.

    from telar.servicios import config
    r = config.resuelta(ctx)

Lo usan `telar config --json` (telar.ordenes.config) y `GET /config` (telar.api). Lo que escribe la
configuración (`telar config --pestanas …`, `--calendario …`) sigue en la orden. La forma es la de
docs/contratos.md.
"""

from __future__ import annotations

import json
import os
import time as _reloj
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from telar.config import MULTIPLEXORES, PROYECTO_POR_DEFECTO, REUNION_POR_DEFECTO
from telar.proveedores.calendario import tapar

__all__ = ["ConfigResuelta", "resuelta", "ENTORNO"]

#: Variable de entorno → clave que pisa. Igual que en docs/configuracion.md.
ENTORNO = {
    "TELAR_CONFIG": "el archivo",
    "TELAR_MULTIPLEXOR": "multiplexor",
    "TELAR_SESION": "sesion",
    "TELAR_RAIZ": "raiz",
    "TELAR_ESTADO": "estado",
    "TELAR_PERFIL": "perfil",
}

#: cuánto vale la copia de la cuenta de gws (segundos)
VALE_CUENTA = 600


def _carpeta_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "telar"


class ConfigResuelta(BaseModel):
    """La configuración resuelta. Las partes con forma propia (proveedores, secciones, apps…) van como
    vienen: su detalle está en docs/contratos.md y en docs/configuracion.md."""

    model_config = ConfigDict(extra="allow")

    origen: str = ""
    multiplexor: str
    sesion: str
    raiz: str
    estado: str
    perfil: str = ""
    ruta_perfil: str = ""
    intervalos: dict[str, float] = Field(default_factory=dict)
    calendario: dict[str, Any] = Field(default_factory=dict)
    hilos: dict[str, Any] = Field(default_factory=dict)
    agente: dict[str, Any] = Field(default_factory=dict)
    remotos: list[dict[str, Any]] = Field(default_factory=list)
    bloques: list[dict[str, Any]] = Field(default_factory=list)
    pestanas: list[dict[str, Any]] = Field(default_factory=list)
    agenda: list[dict[str, Any]] = Field(default_factory=list)
    secciones: list[dict[str, Any]] = Field(default_factory=list)
    dashboard: dict[str, list[str]] = Field(default_factory=dict)
    modulos: list[dict[str, Any]] = Field(default_factory=list)
    apps: list[dict[str, Any]] = Field(default_factory=list)
    atajos: list[dict[str, Any]] = Field(default_factory=list)
    proveedores: dict[str, dict[str, Any]] = Field(default_factory=dict)
    entorno: dict[str, str] = Field(default_factory=dict)
    multiplexores: list[str] = Field(default_factory=list)
    agente_general: dict[str, str] = Field(default_factory=dict)
    persona: str = ""
    persona_nombres: list[str] = Field(default_factory=list)
    #: dónde vive la bandeja del equipo, vista desde aquí: «aqui», el nombre de otra máquina, o vacío
    equipo: str = ""


def resuelta(ctx) -> ConfigResuelta:
    """La configuración con la que trabaja telar aquí, y lo que se pisó por el entorno."""
    cfg = ctx.config
    pisadas = {v: os.environ[k] for k, v in ENTORNO.items() if os.environ.get(k)}
    return ConfigResuelta(**{
        "origen": str(cfg.origen) if cfg.origen else "",
        "multiplexor": cfg.multiplexor,
        "sesion": cfg.sesion,
        "raiz": str(cfg.raiz),
        "estado": str(cfg.estado),
        "perfil": str(cfg.perfil) if cfg.perfil else "",
        "ruta_perfil": str(cfg.ruta_perfil),
        "intervalos": {
            "refresco": cfg.intervalos.refresco,
            "ficha": cfg.intervalos.ficha,
            "proveedores": cfg.intervalos.proveedores,
            "foco_maximo": cfg.intervalos.foco_maximo,
        },
        "calendario": _calendario(cfg),
        "hilos": {"directorios": list(cfg.hilos.directorios), "tope": cfg.hilos.tope},
        "agente": {
            "nombre": cfg.agente.nombre,
            "carpeta": cfg.agente.carpeta,
            "reunion": cfg.agente.reunion,
            "reunion_por_defecto": REUNION_POR_DEFECTO,
            "minuta": cfg.agente.minuta,
            "proyecto": cfg.agente.proyecto,
            "proyecto_por_defecto": PROYECTO_POR_DEFECTO,
            "pendiente": cfg.agente.pendiente,
            "pendiente_nuevo": cfg.agente.pendiente_nuevo,
        },
        "remotos": [
            {"nombre": r.nombre, "destino": r.destino, "transporte": r.transporte, "raiz": r.raiz}
            for r in cfg.remotos
        ],
        "bloques": [{"clave": b.clave, "nombre": b.nombre, "color": b.color, "en": b.en, "tecla": b.tecla} for b in cfg.bloques],
        # las pestañas de proveedor (un feed) y su tecla, para el dashboard
        "pestanas": [{"nombre": str(p.opciones["pestana"]), "tecla": str(p.opciones.get("tecla") or "")}
                     for p in cfg.proveedores_activos() if p.opciones.get("pestana")],
        "agenda": [{"clave": r.clave, "si": r.si, "antes": r.antes, "despues": r.despues} for r in cfg.agenda],
        "secciones": [
            {"clave": s.clave, "nombre": s.nombre, "hilos": list(s.hilos), "home": bool(s.home)}
            for s in cfg.secciones
        ] + _agentes(cfg),
        "dashboard": {"orden": list(cfg.dashboard_orden), "ocultas": list(cfg.dashboard_ocultas)},
        "modulos": [{"nombre": m.nombre, "carpeta": str(m.carpeta), "descripcion": m.descripcion, "aporta": m.aporta}
                    for m in cfg.modulos],
        "apps": [{"clave": a.clave, "nombre": a.nombre, "descripcion": a.descripcion, "fuente": a.fuente,
                  **({"url": a.url} if a.url else {})} for a in cfg.apps],
        "atajos": [
            {"tecla": a.tecla, "nombre": a.nombre, "mensaje": a.mensaje, "descripcion": a.descripcion, "en": a.en}
            for a in cfg.atajos
        ],
        "proveedores": {
            nombre: {"activo": pr.activo, "alcance": _alcance(pr), "opciones": _sin_secretos(pr.opciones)}
            for nombre, pr in cfg.proveedores.items()
        },
        "entorno": pisadas,
        "multiplexores": list(MULTIPLEXORES),
        # el agente que recibe lo que no tiene proyecto (`[agentes] sin_proyecto`): a quién le escribe el
        # dashboard sobre una reunión
        "agente_general": _general(ctx),
        # quién es la persona de esta máquina (`[bus] persona`, o el usuario): una tarea sin dueño es suya
        "persona": _persona(cfg),
        # cómo más la nombran en un documento («Nicolás Rivas», de git): un pendiente a ese nombre es suyo
        "persona_nombres": _nombres(cfg),
        # la bandeja del equipo: la página en el navegador la lee de aquí (en VS Code, el ajuste equipoRemoto)
        "equipo": _equipo(cfg),
    })


def _equipo(cfg) -> str:
    """`[equipo]` de esta configuración: «aqui», la máquina de `[equipo] en`, o "" si no hay equipo."""
    import tomllib

    try:
        tabla = tomllib.loads(Path(cfg.origen).read_text(encoding="utf-8")).get("equipo") if cfg.origen else None
    except (OSError, ValueError):
        return ""
    if not isinstance(tabla, dict) or not tabla.get("tareas"):
        return ""
    return str(tabla.get("en") or "").strip() or "aqui"


def _alcance(pr) -> str:
    """Qué promete tocar ese proveedor. Se lee antes de encenderlo, que es para lo que está."""
    try:
        from telar.proveedores import REGISTRO

        return REGISTRO[pr.nombre](pr).alcance
    except Exception:  # noqa: BLE001 - un proveedor ajeno no tiene por qué ser prolijo
        return ""


def _sin_secretos(opciones: dict) -> dict:
    return {k: (tapar(v) if k == "url" and isinstance(v, str) else v) for k, v in opciones.items()}


def _calendario(cfg) -> dict:
    """Qué fuente tiene la agenda, para la pantalla de configuración del dashboard."""
    import shutil

    pr = cfg.proveedores.get("calendario")
    opciones = pr.opciones if pr else {}
    tipo = str(opciones.get("tipo") or "") if pr and pr.activo else ""
    url = opciones.get("url") if isinstance(opciones.get("url"), str) else ""
    programa = str(opciones.get("programa") or "gws")
    instalado = bool(shutil.which(programa))
    cuenta, conectado = _cuenta_gws(programa) if instalado else ("", False)
    return {
        "tipo": tipo or "ninguno",
        "fuente": tapar(url) if url else str(opciones.get("archivo") or ""),
        # la pública solo sirve si el calendario está publicado para todo internet
        "publica": "/public/" in url,
        "gws": instalado,
        "gws_cuenta": cuenta,
        "gws_conectado": conectado,
    }


def _cuenta_gws(programa: str) -> tuple[str, bool]:
    """Con qué cuenta está conectado `gws`, y si la sesión sirve, con una copia que vale 10 minutos: la
    pregunta puede tardar (hasta 10 s), y el dashboard lee la configuración a cada rato."""
    copia = _carpeta_cache() / "gws-cuenta.json"
    try:
        if _reloj.time() - copia.stat().st_mtime < VALE_CUENTA:
            d = json.loads(copia.read_text(encoding="utf-8"))
            if d.get("programa") == programa:
                return str(d.get("cuenta", "")), bool(d.get("conectado"))
    except (OSError, ValueError):
        pass
    cuenta, conectado = _preguntar_gws(programa)
    try:
        copia.parent.mkdir(parents=True, exist_ok=True)
        copia.write_text(json.dumps({"programa": programa, "cuenta": cuenta, "conectado": conectado}), encoding="utf-8")
    except OSError:
        pass
    return cuenta, conectado


def _preguntar_gws(programa: str) -> tuple[str, bool]:
    """Con qué cuenta está conectado `gws`, y si la sesión sirve.

    De `gws auth status` se toman dos datos y ninguno más: esa salida también trae rutas
    de credenciales e identificadores del cliente OAuth, que no tienen por qué viajar.
    """
    import json
    import subprocess

    try:
        r = subprocess.run([programa, "auth", "status"], capture_output=True, text=True,
                           timeout=10, stdin=subprocess.DEVNULL)
        datos = json.loads(r.stdout[r.stdout.index("{"):])
    except (OSError, subprocess.SubprocessError, ValueError):
        return "", False
    cuenta = datos.get("user") if isinstance(datos.get("user"), str) else ""
    return cuenta, bool(datos.get("token_valid") or datos.get("has_refresh_token"))


def _agentes(cfg) -> list[dict]:
    """Los agentes residentes, como secciones del grupo «agentes»: su home lo arma telar."""
    from telar import agentes as mod_agentes
    from telar import estado as mod_estado

    try:
        vinculos = mod_estado.abrir(cfg).vinculos()
    except Exception:  # noqa: BLE001 - sin estado, los agentes salen igual, solo con sus nombres
        vinculos = {}
    return [{"clave": a.seccion, "nombre": a.nombre, "hilos": list(a.hilos), "home": True, "grupo": "agentes"}
            for a in mod_agentes.descubrir(cfg, vinculos)]


def _nombres(cfg) -> list[str]:
    import subprocess

    nombres = [n for n in [_persona(cfg)] if n]
    try:
        git = subprocess.run(["git", "config", "--get", "user.name"], capture_output=True, text=True, timeout=5,
                             cwd=str(cfg.raiz)).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        git = ""
    if git and git not in nombres:
        nombres.append(git)
    return nombres


def _persona(cfg) -> str:
    from telar import bus as mod_bus

    try:
        return mod_bus.persona(cfg)
    except Exception:  # noqa: BLE001 - sin usuario conocido, el dashboard dice «tú»
        return ""


def _general(ctx) -> dict:
    from telar.ordenes import pendiente

    try:
        a = pendiente._agente_general(ctx)
    except Exception:  # noqa: BLE001 - sin agentes, nada
        a = None
    return {"clave": a.clave, "nombre": a.nombre} if a is not None else {}



class Pestanas(BaseModel):
    dashboard: dict
    archivo: str


def pestanas(ctx, valor: str) -> Pestanas:
    """El orden de las pestañas del dashboard y cuáles se esconden («hoy,plan,-correo»), escrito en la
    configuración (`telar config --pestanas`)."""
    from telar.config import ErrorDeConfig, escribir_clave
    from telar.servicios import ErrorDeServicio

    nombres = [x.strip() for x in valor.split(",") if x.strip()]
    orden = [x.lstrip("-") for x in nombres]
    ocultas = [x[1:] for x in nombres if x.startswith("-")]
    try:
        escribir_clave("dashboard", "orden", orden or None, ctx.config.origen)
        destino = escribir_clave("dashboard", "ocultas", ocultas or None, ctx.config.origen)
    except ErrorDeConfig as e:
        raise ErrorDeServicio(str(e), 422) from e
    return Pestanas(dashboard={"orden": orden, "ocultas": ocultas}, archivo=str(destino))


class Escrito(BaseModel):
    """Lo que quedó escrito en la configuración, y en qué archivo (el contrato de `telar config --json`)."""

    model_config = ConfigDict(extra="allow")

    archivo: str


def _escribir(ctx, seccion: str, clave: str, valor):
    from telar.config import ErrorDeConfig, escribir_clave
    from telar.servicios import ErrorDeServicio

    try:
        return escribir_clave(seccion, clave, valor, ctx.config.origen)
    except ErrorDeConfig as e:
        raise ErrorDeServicio(str(e), 422) from e


def directorios(ctx, carpetas: str) -> Escrito:
    """De qué carpetas salen los hilos («a,b»); vacío, las del perfil."""
    from telar.servicios import ErrorDeServicio

    dirs = [d.strip().strip("/") for d in carpetas.split(",") if d.strip()]
    faltan = [d for d in dirs if not (ctx.config.raiz / d).is_dir()]
    if faltan:
        raise ErrorDeServicio(f"no existe en {ctx.config.raiz}: {', '.join(faltan)}", 422)
    return Escrito(hilos="ok", archivo=str(_escribir(ctx, "hilos", "directorios", dirs or None)))


def tope(ctx, n: int) -> Escrito:
    return Escrito(hilos="ok", archivo=str(_escribir(ctx, "hilos", "tope", n)))


def plantilla(ctx, cual: str, texto: str) -> Escrito:
    """Qué decirle al agente al preparar una reunión (`reunion`) o al abrir un proyecto (`proyecto`); vacío,
    el de fábrica."""
    from telar.config import PROYECTO_POR_DEFECTO, REUNION_POR_DEFECTO

    valor = texto.strip() or None
    destino = _escribir(ctx, "agente", cual, valor)
    defecto = REUNION_POR_DEFECTO if cual == "reunion" else PROYECTO_POR_DEFECTO
    return Escrito(**{cual: valor or defecto, "archivo": str(destino)})


def calendario(ctx, valor: str) -> Escrito:
    """De dónde sale la agenda: `gws`, `ninguno` o la dirección de un calendario iCal."""
    from telar.config import ErrorDeConfig, escribir_calendario
    from telar.servicios import ErrorDeServicio

    try:
        destino = escribir_calendario(valor, ctx.config.origen)
    except ErrorDeConfig as e:
        raise ErrorDeServicio(str(e), 422) from e
    return Escrito(calendario="conectado", archivo=str(destino))
