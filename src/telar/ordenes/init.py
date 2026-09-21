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
#
# El nombre de la sección ES el módulo que lo trae (telar.proveedores.<nombre>): hoy
# vienen `calendario` y `tareas`. Un nombre inventado hace fallar a `telar doctor`.
# [proveedores.calendario]
# activo = true
# ics = "https://ejemplo/calendario.ics"
"""

PLANTILLA_PERFIL = """\
# telar-perfil.yaml — lo que este repositorio declara de sí mismo.
#
# telar no sabe qué es un proyecto aquí: lo dice este archivo, viaja con el
# repositorio, y cualquier telar que lo abra teje lo mismo. Esquema: docs/perfil.md
#
# Lo de abajo sale de mirar {mirado}: cambia las rutas y los encabezados por los
# que de verdad usa este repositorio, que es para lo que existe el archivo.

version: 1
nombre: {nombre}

arquetipos:
{arquetipos}
# Lo que este repositorio ofrece hacer sobre un hilo. `comando` es una lista de
# palabras, nunca una línea de shell.
acciones: []
"""

PLANTILLA_ARQUETIPO = """
  {nombre}:
    descripcion: {descripcion}
    ruta: "{ruta}"
    documento: {documento}
    secciones:
      titulo:
        tipo: linea
        encabezado: '^#\\s+(.+)$'
      estado:
        tipo: parrafo
        encabezado: '{encabezado_estado}'
      pendientes:
        tipo: casillas
        encabezado: '{encabezado_pendientes}'
        maximo: 6
"""

#: Dónde suele guardar la gente sus unidades de trabajo. Se prueban contra el repositorio
#: y solo se escriben las que encuentran algo: un perfil que no calza con nada es peor que
#: no tener perfil, porque parece configurado.
CANDIDATOS = (
    ("proyecto", "*/", "Una carpeta de la raíz con un README que dice cómo va."),
    ("proyecto", "proyectos/*/", "Un proyecto, en proyectos/."),
    ("proyecto", "projects/*/", "Un proyecto, en projects/."),
    ("cliente", "clientes/*/", "Un cliente, en clientes/."),
    ("cliente", "clients/*/", "Un cliente, en clients/."),
)


def _encabezados(documentos) -> tuple[str, str]:
    """Con qué encabezado titula ESTE repositorio su estado y sus pendientes.

    Se miran los documentos encontrados y se elige el que más aparece; si no aparece
    ninguno, se deja el castellano, que es el del ejemplo, y el usuario lo cambia.
    """
    import re as _re

    def mas_usado(palabras, defecto):
        cuenta: dict[str, int] = {}
        for doc in documentos[:20]:
            try:
                texto = doc.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for linea in texto.splitlines():
                m = _re.match(r"^#{2,3}\s+(.+?)\s*$", linea)
                if m and m.group(1).split()[0].lower() in palabras:
                    clave = m.group(1).split()[0]
                    cuenta[clave] = cuenta.get(clave, 0) + 1
        if not cuenta:
            return defecto
        return max(cuenta.items(), key=lambda par: par[1])[0]

    estado = mas_usado({"estado", "status", "state"}, "Estado")
    pendientes = mas_usado({"pendientes", "tareas", "todo", "to-do", "próximos", "next"}, "Pendientes")
    return rf"^#{{2,3}}\s+{estado}", rf"^#{{2,3}}\s+{pendientes}"


def _arquetipos_del_repo(raiz: Path) -> tuple[str, str]:
    """Los arquetipos que calzan con lo que hay, y qué se miró para proponerlos."""
    from telar.perfil import Arquetipo

    bloques: list[str] = []
    mirados: list[str] = []
    vistos: set[str] = set()
    for nombre, ruta, descripcion in CANDIDATOS:
        arq = Arquetipo(nombre=nombre, ruta=ruta, documento="README.md")
        documentos = arq.documentos(raiz)
        if not documentos:
            continue
        clave = nombre if nombre not in vistos else f"{nombre}-{ruta.strip('*/').strip('/') or 'raiz'}"
        vistos.add(clave)
        estado, pendientes = _encabezados(documentos)
        bloques.append(
            PLANTILLA_ARQUETIPO.format(
                nombre=clave, descripcion=descripcion, ruta=ruta, documento="README.md",
                encabezado_estado=estado, encabezado_pendientes=pendientes,
            )
        )
        mirados.append(f"{len(documentos)} en {ruta}")
    if not bloques:
        estado, pendientes = "^#{2,3}\\s+Estado", "^#{2,3}\\s+Pendientes"
        bloques.append(
            PLANTILLA_ARQUETIPO.format(
                nombre="proyecto", descripcion="Una carpeta con un README que dice cómo va.",
                ruta="*/", documento="README.md",
                encabezado_estado=estado, encabezado_pendientes=pendientes,
            )
        )
        mirados.append("ningún README donde se suele mirar")
    return "".join(bloques), " · ".join(mirados)


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
            _arq, _mirado = _arquetipos_del_repo(Path(cfg.raiz))
            try:
                ruta_perfil.write_text(
                    PLANTILLA_PERFIL.format(
                        nombre=Path(cfg.raiz).name or "trabajo",
                        arquetipos=_arq,
                        mirado=_mirado,
                    ),
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
    # con los dos instalados gana tmux: es la implementación de referencia, la que
    # sabe mover paneles entre hilos y la única a la que se le puede apuntar un cliente
    for nombre in ("tmux", *MULTIPLEXORES):
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
    # por componente y no por prefijo de texto: /Users/nicolas empieza con /Users/nico
    try:
        return "~/" + ruta.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(ruta)
