"""`telar init` — dejar la máquina lista: configuración, estado y, si se pide, perfil.

Escribe el archivo de configuración con lo que se pueda detectar (qué multiplexor
hay instalado, si se está corriendo dentro de uno, dónde está el repositorio de
trabajo) y crea la carpeta de estado. Nada más: telar arranca igual sin archivo, y
este es un atajo, no un requisito.

    telar init                      escribir la configuración por defecto
    telar init --multiplexor tmux   forzar uno
    telar init --perfil             además, un telar-perfil.yaml mínimo en la raíz
    telar init --forzar             sobrescribir lo que ya exista

El perfil es lo único que se escribe DENTRO del repositorio de trabajo, y por eso
hay que pedirlo: viaja con el repo, lo lee todo el que lo abra, y no es de esta
máquina.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from telar.config import MULTIPLEXORES, ruta_config
from telar.estado import abrir as abrir_estado
from telar.ordenes import _comun
from telar.perfil import NOMBRE_ARCHIVO

AYUDA = "Escribir la configuración, detectar el multiplexor y preparar el estado."

PLANTILLA_CONFIG = """\
# La configuración de telar en esta máquina. Esquema completo: docs/configuracion.md
# Todo tiene valor por defecto: lo que sobre, se puede borrar.

# Qué multiplexor de terminal hay debajo: "tmux" o "zellij".
multiplexor = "{multiplexor}"

# El nombre de la sesión que telar teje. Una sesión, un telar.
sesion = "{sesion}"

# La raíz del repositorio de trabajo: de ahí sale el perfil, y ahí viven los hilos.
raiz = "{raiz}"

# Dónde escribir el estado derivado. Nunca dentro de `raiz`: se puede borrar entero
# sin perder trabajo.
estado = "{estado}"

[intervalos]
refresco    = {refresco:g}
ficha       = {ficha:g}
proveedores = {proveedores:g}
foco_maximo = {foco_maximo:g}

# Ningún proveedor existe hasta que aparece aquí, y sin ninguno telar no sale de la
# máquina. Cada uno declara en su documentación qué toca del mundo.
# [proveedores.agenda]
# activo = true
"""

PLANTILLA_PERFIL = """\
# telar-perfil.yaml — lo que este repositorio declara de sí mismo.
#
# telar no sabe qué es un proyecto aquí: lo dice este archivo, viaja con el
# repositorio, y cualquier telar que lo abra teje lo mismo. Esquema: docs/perfil.md

version: 1
nombre: {nombre}

arquetipos:

  proyecto:
    descripcion: Una carpeta con un README que dice cómo va.
    ruta: "*/"
    documento: README.md
    secciones:
      titulo:
        tipo: linea
        encabezado: '^#\\s+(.+)$'
      estado:
        tipo: parrafo
        encabezado: '^##\\s+Estado'
      pendientes:
        tipo: casillas
        encabezado: '^##\\s+Pendientes'
        maximo: 6

# Lo que este repositorio ofrece hacer sobre un hilo. `comando` es una lista de
# palabras, nunca una línea de shell.
acciones: []
"""


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("init", AYUDA)
    p.epilog = __doc__
    p.add_argument("--multiplexor", choices=list(MULTIPLEXORES), default="")
    p.add_argument("--sesion", default="", help="nombre de la sesión (por defecto, telar)")
    p.add_argument("--en", default="", metavar="RUTA", help="dónde escribir la configuración")
    p.add_argument("--perfil", action="store_true", help="escribir también un perfil mínimo")
    p.add_argument("--forzar", action="store_true", help="sobrescribir lo que exista")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    cfg = ctx.config
    destino = Path(o.en).expanduser() if o.en else ruta_config()
    multiplexor = o.multiplexor or detectar_multiplexor() or cfg.multiplexor
    sesion = o.sesion or os.environ.get("TELAR_SESION") or cfg.sesion
    hecho: dict[str, str] = {}
    avisos: list[str] = []

    if destino.exists() and not o.forzar:
        avisos.append(f"ya había configuración en {destino}; --forzar la reescribe")
    else:
        texto = PLANTILLA_CONFIG.format(
            multiplexor=multiplexor,
            sesion=sesion,
            # absolutas a propósito: una raíz relativa depende de dónde se corrió telar
            raiz=_atajo(Path(cfg.raiz).resolve()),
            estado=_atajo(Path(cfg.estado).resolve()),
            refresco=cfg.intervalos.refresco,
            ficha=cfg.intervalos.ficha,
            proveedores=cfg.intervalos.proveedores,
            foco_maximo=cfg.intervalos.foco_maximo,
        )
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8")
        except OSError as e:
            return _comun.queja(f"no pude escribir {destino}: {e}")
        hecho["config"] = str(destino)

    est = abrir_estado(cfg)
    if _dentro(est.carpeta, cfg.raiz):
        avisos.append(
            f"el estado ({est.carpeta}) está dentro de la raíz; muévelo: es caché, no trabajo"
        )
    try:
        est.preparar()
        hecho["estado"] = str(est.carpeta)
    except OSError as e:
        return _comun.queja(f"no pude crear la carpeta de estado: {e}")

    ruta_perfil = Path(cfg.ruta_perfil)
    if o.perfil:
        if ruta_perfil.exists() and not o.forzar:
            avisos.append(f"ya había un perfil en {ruta_perfil}; --forzar lo reescribe")
        else:
            try:
                ruta_perfil.write_text(
                    PLANTILLA_PERFIL.format(nombre=Path(cfg.raiz).name or "trabajo"),
                    encoding="utf-8",
                )
            except OSError as e:
                return _comun.queja(f"no pude escribir {ruta_perfil}: {e}")
            hecho["perfil"] = str(ruta_perfil)
    elif not ruta_perfil.exists():
        avisos.append(
            f"no hay {NOMBRE_ARCHIVO} en {cfg.raiz}: rige la convención mínima."
            " `telar init --perfil` escribe uno para empezar"
        )

    if o.json:
        return _comun.escribir_json(
            {
                "escrito": hecho,
                "multiplexor": multiplexor,
                "sesion": sesion,
                "raiz": str(cfg.raiz),
                "avisos": avisos,
            }
        )

    for que, donde in hecho.items():
        print(f"{que:<8} {donde}")
    print(_comun.tenue(f"multiplexor: {multiplexor} · sesión: {sesion} · raíz: {cfg.raiz}"))
    for aviso in avisos:
        print(_comun.tenue(f"  · {aviso}"))
    print(_comun.tenue("Revisa con: telar doctor"))
    return 0


def detectar_multiplexor() -> str:
    """Qué multiplexor hay: primero el que nos está corriendo, después el que esté instalado."""
    if os.environ.get("ZELLIJ_SESSION_NAME") or os.environ.get("ZELLIJ"):
        return "zellij"
    if os.environ.get("TMUX"):
        return "tmux"
    for nombre in MULTIPLEXORES:
        if shutil.which(nombre):
            return nombre
    return ""


def _dentro(hijo: Path, padre: Path) -> bool:
    """¿`hijo` cuelga de `padre`? Sin resolver enlaces no se sabe, así que se resuelven."""
    try:
        return Path(hijo).resolve().is_relative_to(Path(padre).resolve())
    except OSError:  # pragma: no cover - rutas rotas
        return False


def _atajo(ruta: Path) -> str:
    """`~` en vez del hogar: una configuración que se puede leer y copiar."""
    texto = str(ruta)
    hogar = str(Path.home())
    return "~" + texto[len(hogar):] if texto.startswith(hogar) else texto
