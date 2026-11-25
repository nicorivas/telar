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
from telar.perfil import ruta_de_repo
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
    #: cómo se ve la terminal de un hilo (`[terminal]`): columnas, posicion, fondo
    terminal: dict[str, Any] = Field(default_factory=dict)
    hilos: dict[str, Any] = Field(default_factory=dict)
    agente: dict[str, Any] = Field(default_factory=dict)
    remotos: list[dict[str, Any]] = Field(default_factory=list)
    #: el bus de esta persona (`[bus]`): url, persona y máquina; vacío si no hay (todo en una máquina)
    bus: dict[str, str] = Field(default_factory=dict)
    bloques: list[dict[str, Any]] = Field(default_factory=list)
    pestanas: list[dict[str, Any]] = Field(default_factory=list)
    agenda: list[dict[str, Any]] = Field(default_factory=list)
    secciones: list[dict[str, Any]] = Field(default_factory=list)
    dashboard: dict[str, list[str]] = Field(default_factory=dict)
    #: los repositorios de trabajo de `[repos]`: nombre, ruta y perfil, como en `TELAR_REPOS`
    repos: list[dict[str, str]] = Field(default_factory=list)
    modulos: list[dict[str, Any]] = Field(default_factory=list)
    apps: list[dict[str, Any]] = Field(default_factory=list)
    #: lo que dejan las skills por día (`[vistas.x]` con carpeta o en): clave, nombre, en y `pasadas` (el esquema, si
    #: cada día es una lista de pasadas: la página muestra las que no se han visto)
    resultados: list[dict[str, str]] = Field(default_factory=list)
    atajos: list[dict[str, Any]] = Field(default_factory=list)
    proveedores: dict[str, dict[str, Any]] = Field(default_factory=dict)
    entorno: dict[str, str] = Field(default_factory=dict)
    multiplexores: list[str] = Field(default_factory=list)
    agente_general: dict[str, str] = Field(default_factory=dict)
    persona: str = ""
    persona_nombres: list[str] = Field(default_factory=list)
    #: dónde vive la bandeja del equipo, vista desde aquí: «aqui», el nombre de otra máquina, o vacío
    equipo: str = ""
    #: lo que la ventana «instrucción» necesita de aquí: a quién va de entrada lo que manda la pestaña de un módulo
    #: (`[instruccion] destino`, como se declaró, y `a`, el nombre que lo elige en la ventana: el de un agente aunque se
    #: haya declarado por su carpeta; sin declarar, no están) y `procesar`, la línea que le llega al agente con un
    #: contexto libre y nada pedido
    instruccion: dict[str, str] = Field(default_factory=dict)
    #: las partes de la vida (`[mundos]`), en su orden: [{nombre, areas, rutas, etiquetas, color, horario, tema, modos}]
    #: (telar.mundos, `para_la_pagina`; `modos` vacío: todos); vacío si no se declaran
    mundos: list[dict[str, Any]] = Field(default_factory=list)
    #: el mundo que rige fuera de todo horario (`[mundos] fuera`); "" es ambos
    mundos_fuera: str = ""
    #: los colores propios de cada tema en esta máquina (`[temas.<tema>]`, telar.temas): tema → {tinta: "#rrggbb"}; solo
    #: los temas que cambian algo
    temas: dict[str, dict[str, str]] = Field(default_factory=dict)


def resuelta(ctx) -> ConfigResuelta:
    """La configuración con la que trabaja telar aquí, y lo que se pisó por el entorno."""
    from telar import mundos as mod_mundos
    from telar import temas as mod_temas

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
        "terminal": {"columnas": cfg.terminal.columnas, "posicion": cfg.terminal.posicion, "fondo": cfg.terminal.fondo},
        "hilos": {"directorios": list(cfg.hilos.directorios), "tope": cfg.hilos.tope, "dormir_tras": cfg.hilos.dormir_tras},
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
        "bus": _bus(cfg),
        "bloques": [{"clave": b.clave, "nombre": b.nombre, "color": b.color, "tecla": b.tecla, "dentro": b.dentro} for b in cfg.bloques],
        # las pestañas de proveedor (un feed), su tecla y cómo se ve su ficha (`vista`: "lectura", o la de una tarea)
        "pestanas": [{"nombre": str(p.opciones["pestana"]), "tecla": str(p.opciones.get("tecla") or ""),
                      "vista": str(p.opciones.get("vista") or "")}
                     for p in cfg.proveedores_activos() if p.opciones.get("pestana")],
        "agenda": [{"clave": r.clave, "si": r.si, "antes": r.antes, "despues": r.despues} for r in cfg.agenda],
        "secciones": [
            {"clave": s.clave, "nombre": s.nombre, "hilos": list(s.hilos), "home": bool(s.home)}
            for s in cfg.secciones
        ] + _agentes(cfg),
        "dashboard": {"orden": list(cfg.dashboard_orden), "ocultas": list(cfg.dashboard_ocultas)},
        "mundos": mod_mundos.para_la_pagina(cfg),
        "mundos_fuera": getattr(cfg, "mundos_fuera", ""),
        "temas": mod_temas.para_la_pagina(cfg),
        # la ruta absoluta, como la lee telar (una relativa, desde la raíz): la misma que reciben los módulos
        "repos": [{"nombre": r.nombre, "ruta": str(ruta_de_repo(cfg, r)), "perfil": str(r.perfil or "")}
                  for r in cfg.repos],
        "modulos": _modulos(cfg),
        "apps": [{"clave": a.clave, "nombre": a.nombre, "descripcion": a.descripcion, "fuente": a.fuente,
                  **({"url": a.url} if a.url else {})} for a in cfg.apps],
        "resultados": [{"clave": r.clave, "nombre": r.nombre or r.clave, "en": r.en, "pasadas": r.pasadas} for r in cfg.resultados],
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
        # cómo más la nombran en un documento («Ana Pérez», de git): un pendiente a ese nombre es suyo
        "persona_nombres": _nombres(cfg),
        # la bandeja del equipo: la página en el navegador la lee de aquí (en VS Code, el ajuste equipoRemoto)
        "equipo": _equipo(cfg),
        "instruccion": _instruccion(cfg),
    })


def _modulos(cfg) -> list[dict]:
    """Los módulos, con lo que anotó `telar modulo` de los instalados: de dónde vienen (`fuente`), en qué
    versión y si están enlazados a una carpeta (`telar.modulos.procedencia`). Uno declarado a mano trae
    `instalado` falso y lo demás vacío."""
    from telar import modulos as mod_modulos

    try:
        instalados = mod_modulos.leer_instalados(mod_modulos.ruta_instalados(cfg.origen)) if cfg.origen else {}
    except mod_modulos.ErrorDeModulo:
        # cargar la configuración ya lo habría dicho; esto pasa si modulos.toml se rompe después, con
        # `telar serve` andando: aquí solo falta el detalle
        instalados = {}
    # la fuente sale sin credenciales: esto también lo entrega `GET /config`, más allá de esta máquina
    # `buscables`: sus tipos de objeto que también se buscan en ⌘K (`[objetos.<tipo>] buscador`), con su plural
    return [{"nombre": m.nombre, "carpeta": str(m.carpeta), "descripcion": m.descripcion, "aporta": m.aporta,
             "configurar": bool(m.configurar), **mod_modulos.procedencia(instalados.get(m.nombre)),
             "buscables": [{"tipo": t, "plural": o.get("plural") or t} for t, o in m.objetos.items() if o.get("buscador")]}
            for m in cfg.modulos]


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
    """Los agentes residentes, como secciones del grupo «agentes»: su home lo arma telar, y su `presencia` (siempre,
    a-pedido o no: si escribirle lo abre cuando está cerrado). Con `[mundos]`, cada uno con
    su `mundo` (telar.mundos.por_que_agente: lo que declara su agente.toml, la etiqueta de su hilo o su carpeta; ""
    sin clasificar), para que la página no muestre ni un momento a uno de otro mundo mientras lee lo demás, y qué pasa
    con él con otro mundo puesto (`fuera_de_su_mundo`: al-final, esconder o ver, de su agente.toml)."""
    from telar import agentes as mod_agentes
    from telar import estado as mod_estado
    from telar import mundos

    etiquetas: dict = {}
    try:
        est = mod_estado.abrir(cfg)
        vinculos = est.vinculos()
        etiquetas = est.etiquetas() if mundos.declarados(cfg) else {}
    except Exception:  # noqa: BLE001 - sin estado, los agentes salen igual, solo con sus nombres
        vinculos = {}
    con_mundo = bool(mundos.declarados(cfg))
    aqui = [{"clave": a.seccion, "nombre": a.nombre, "hilos": list(a.hilos), "home": True, "grupo": "agentes",
             "presencia": a.presencia,
             **({"mundo": mundos.por_que_agente(cfg, a.clave, etiquetas.get(a.nombre, ()))["mundo"],
                 "fuera_de_su_mundo": a.fuera_de_su_mundo} if con_mundo else {})}
            for a in mod_agentes.descubrir(cfg, vinculos)]
    return aqui + _agentes_de_otras(cfg, aqui)


def _agentes_de_otras(cfg, aqui: list[dict]) -> list[dict]:
    """Los agentes que viven en otra máquina y cuya carpeta todavía no está en esta (una raíz atrasada: la foto de su
    máquina los trae, telar.espejo): salen igual, con su `maquina` y su mundo (el que declaran allá, si esta máquina
    declara ese mundo; sin `[mundos]`, no va), sin home (su casa no está aquí). Uno con el mismo nombre o la misma
    carpeta que uno de aquí no se repite."""
    from telar import agentes as mod_agentes
    from telar import mundos

    vistos = {s["clave"] for s in aqui} | {s["nombre"] for s in aqui}
    nombres = set(mundos.declarados(cfg))
    salida: list[dict] = []
    for maquina, a in mundos.agentes_de_otras(cfg):
        clave, nombre = mod_agentes.PREFIJO + str(a["clave"]), str(a.get("nombre") or a["clave"])
        if not maquina or clave in vistos or nombre in vistos:
            continue
        vistos |= {clave, nombre}
        mundo = str(a.get("mundo") or "")
        fuera = str(a.get("fuera_de_su_mundo") or mod_agentes.FUERAS[0])
        salida.append({"clave": clave, "nombre": nombre, "hilos": [nombre], "home": False, "grupo": "agentes",
                       "maquina": maquina, **({"mundo": mundo if mundo in nombres else "", "fuera_de_su_mundo": fuera}
                                              if nombres else {})})
    return salida


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


def _instruccion(cfg) -> dict:
    """`[instruccion] destino`, y el nombre que lo elige en la ventana: el de un agente (que se puede declarar por su
    carpeta o por su nombre) o el del hilo. Un agente que no está queda con lo declarado: la ventana dice que no lo
    encuentra. Y la línea que pide procesar un contexto libre (`telar.servicios.actuar.PROCESAR`), que la ventana
    muestra en lo que le llega."""
    from telar.servicios.actuar import PROCESAR

    destino = getattr(cfg, "instruccion_destino", "")
    if not destino:
        return {"procesar": PROCESAR}
    tipo, _, nombre = destino.partition(":")
    if tipo == "agente":
        from telar import agentes as mod_agentes

        try:
            a = next((x for x in mod_agentes.descubrir(cfg) if nombre in (x.clave, x.nombre)), None)
        except Exception:  # noqa: BLE001 - sin agentes, lo declarado
            a = None
        nombre = a.nombre if a is not None else nombre
    return {"destino": destino, "a": nombre, "procesar": PROCESAR}


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


def motor(ctx, valor: str) -> Escrito:
    """Con qué agente se abren los hilos (`[agente] nombre`): uno de los que telar conoce (claude-code), o «ninguno»
    (los hilos quedan con una shell). El nodo lo nota solo y abre a los residentes que esperaban."""
    from telar import agente as mod_agente
    from telar.servicios import ErrorDeServicio

    v = valor.strip()
    if v in ("", "ninguno"):
        destino = _escribir(ctx, "agente", "nombre", None)
        return Escrito(motor="ninguno", archivo=str(destino))
    if v not in set(mod_agente.INCLUIDOS) | set(mod_agente.REGISTRO):
        raise ErrorDeServicio(f"no conozco el motor «{v}»: {', '.join(sorted(mod_agente.INCLUIDOS))} o ninguno", 422)
    destino = _escribir(ctx, "agente", "nombre", v)
    return Escrito(motor=v, archivo=str(destino))


def calendario(ctx, valor: str) -> Escrito:
    """De dónde sale la agenda: `gws`, `ninguno` o la dirección de un calendario iCal."""
    from telar.config import ErrorDeConfig, escribir_calendario
    from telar.servicios import ErrorDeServicio

    try:
        destino = escribir_calendario(valor, ctx.config.origen)
    except ErrorDeConfig as e:
        raise ErrorDeServicio(str(e), 422) from e
    return Escrito(calendario="conectado", archivo=str(destino))


def _bus(cfg) -> dict[str, str]:
    from telar import bus as mod_bus

    if not mod_bus.hay_bus(cfg):
        return {}
    return {"url": cfg.bus.url, "persona": mod_bus.persona(cfg), "maquina": mod_bus.maquina(cfg)}
