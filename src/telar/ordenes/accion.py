"""`telar accion` — correr una acción que declaró el repositorio.

telar no adivina comandos. Corre los que el perfil declare, tal como los declaró:
una lista de palabras, sin shell en medio salvo que el propio perfil la pida. Los
marcadores `{ruta}`, `{hilo}` y `{documento}` se reemplazan palabra por palabra,
así que un espacio en una ruta no parte nada.

    telar accion                 qué ofrece este repositorio
    telar accion revisar         correrla sobre este hilo
    telar accion limpiar --si    sin preguntar, cuando la acción pide confirmación
    telar accion revisar --seco  mostrar qué correría, sin correrlo
"""

from __future__ import annotations

import subprocess
import sys

from telar.ordenes import _comun

AYUDA = "Correr una acción declarada por el perfil."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("accion", AYUDA)
    p.epilog = __doc__
    p.add_argument("nombre", nargs="?", default="", help="cuál correr (sin nada, las lista)")
    p.add_argument("--hilo", default="", help="sobre cuál (por defecto, este)")
    p.add_argument("--si", action="store_true", help="no preguntar, aunque la acción lo pida")
    p.add_argument("--seco", action="store_true", help="decir qué correría, sin correrlo")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    if not o.nombre:
        return _listar(ctx)

    accion = ctx.perfil.accion(o.nombre)
    if accion is None:
        conocidas = ", ".join(a.nombre for a in ctx.perfil.acciones) or "ninguna"
        return _comun.queja(
            f"el perfil no declara una acción «{o.nombre}». Declara: {conocidas}"
        )

    tel = _comun.tejer(ctx)
    hilo = None
    if accion.donde == "hilo":
        if o.hilo:
            hilo, problema = _comun.resolver(tel, o.hilo)
            if hilo is None:
                return _comun.queja(problema)
        else:
            hilo = _comun.hilo_actual(tel)
        if hilo is None:
            return _comun.sin_hilo("accion", tel)
        if hilo.ruta is None:
            return _comun.queja(
                f"«{hilo.nombre}» no está vinculado, y «{accion.nombre}» corre en la carpeta del hilo"
            )

    documento = hilo.ficha.documento if (hilo and hilo.ficha and hilo.ficha.documento) else None
    reemplazos = {
        "{ruta}": str(hilo.ruta) if hilo and hilo.ruta else str(ctx.config.raiz),
        "{hilo}": hilo.nombre if hilo else "",
        "{documento}": str(documento) if documento else "",
    }
    comando = [_reemplazar(palabra, reemplazos) for palabra in accion.comando]
    donde = hilo.ruta if (accion.donde == "hilo" and hilo and hilo.ruta) else ctx.config.raiz

    if o.seco:
        print(" ".join(comando))
        print(_comun.tenue(f"  en {donde}"))
        return 0

    if accion.confirmar and not o.si:
        if not sys.stdin.isatty():
            return _comun.queja(
                f"«{accion.nombre}» pide confirmación y nadie puede darla aquí; pasa --si"
            )
        print(" ".join(comando))
        if input(f"correr «{accion.nombre}» en {donde}? [s/N] ").strip().lower() not in ("s", "si", "sí"):
            print("no se corrió")
            return 1

    try:
        return subprocess.run(comando, cwd=str(donde)).returncode
    except FileNotFoundError:
        return _comun.queja(f"no existe el programa «{comando[0]}» que declara la acción")
    except OSError as e:
        return _comun.queja(f"no pude correr «{accion.nombre}»: {e}")


def _reemplazar(palabra: str, reemplazos: dict[str, str]) -> str:
    for marcador, valor in reemplazos.items():
        palabra = palabra.replace(marcador, valor)
    return palabra


def _listar(ctx) -> int:
    if not ctx.perfil.acciones:
        print(_comun.tenue("este repositorio no declara acciones (docs/perfil.md)."))
        return 0
    print(_comun.fuerte(f"acciones de «{ctx.perfil.nombre or 'el repositorio'}»"))
    for a in ctx.perfil.acciones:
        tecla = f"[{a.tecla}] " if a.tecla else "    "
        marcas = " · ".join(filter(None, [a.donde, "confirma" if a.confirmar else ""]))
        print(f"  {tecla}{a.nombre:<14} {a.descripcion}")
        print(_comun.tenue(f"      {' '.join(a.comando)}   ({marcas})"))
    return 0
