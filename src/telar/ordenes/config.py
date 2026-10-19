"""`telar config` — la configuración resuelta, y de dónde salió cada cosa.

No hay modo «adivina»: si telar se está portando raro, esto dice exactamente con
qué valores está trabajando, qué archivo los trajo y qué variable de entorno los
pisó. El esquema completo está en `docs/configuracion.md`.
"""

from __future__ import annotations

import os

from telar.config import (
    MULTIPLEXORES,
    PROYECTO_POR_DEFECTO,
    REUNION_POR_DEFECTO,
    ErrorDeConfig,
    escribir_calendario,
    escribir_clave,
    ruta_config,
)
from telar.ordenes import _comun
from telar.proveedores.calendario import tapar  # noqa: F401 - quien lo importaba de aquí
from telar.servicios import config as servicio
from telar.servicios.config import (  # noqa: F401 - antes vivían aquí
    _agentes, _alcance, _calendario, _cuenta_gws, _general, _nombres, _persona, _sin_secretos,
)

AYUDA = "Mostrar la configuración resuelta y de dónde salió."

#: Variable de entorno → clave que pisa. Igual que en docs/configuracion.md.
ENTORNO = {
    "TELAR_CONFIG": "el archivo",
    "TELAR_MULTIPLEXOR": "multiplexor",
    "TELAR_SESION": "sesion",
    "TELAR_RAIZ": "raiz",
    "TELAR_ESTADO": "estado",
    "TELAR_PERFIL": "perfil",
}


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("config", AYUDA)
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    p.add_argument("--ruta", action="store_true", help="solo dónde se busca el archivo")
    p.add_argument("--calendario", metavar="URL_O_ARCHIVO", default="",
                   help="conectar la agenda: gws, una dirección iCal privada (https://, webcal://), un .ics, o ninguno")
    p.add_argument("--reunion", metavar="TEXTO", default=None,
                   help="qué decirle al agente al preparar una reunión ({titulo} {hora} {fecha} {enlace} {proyecto}); "
                        "vacío vuelve al de fábrica")
    p.add_argument("--proyecto", metavar="TEXTO", default=None,
                   help="qué decirle al agente al abrir un proyecto ({nombre} {ruta} {carpeta} {documento}); "
                        "vacío vuelve al de fábrica")
    p.add_argument("--directorios", metavar="CARPETAS", default=None,
                   help="de qué carpetas salen los hilos, separadas por coma, relativas a la raíz; "
                        "vacío vuelve a las unidades del perfil")
    p.add_argument("--tope", type=int, default=None, help="cuántos hilos abre tejer de una vez")
    p.add_argument("--pestanas", metavar="ORDEN", default=None,
                   help="las pestañas del dashboard, en orden y separadas por coma; las que llevan «-» delante "
                        "no se muestran (ej. «ahora,revisar,-plan»); vacío vuelve a todas en su orden de siempre")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    if o.pestanas is not None:
        nombres = [x.strip() for x in o.pestanas.split(",") if x.strip()]
        orden = [x.lstrip("-") for x in nombres]
        ocultas = [x[1:] for x in nombres if x.startswith("-")]
        try:
            escribir_clave("dashboard", "orden", orden or None, ctx.config.origen)
            destino = escribir_clave("dashboard", "ocultas", ocultas or None, ctx.config.origen)
        except ErrorDeConfig as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json({"dashboard": {"orden": orden, "ocultas": ocultas}, "archivo": str(destino)})
        print(f"pestañas: {', '.join(nombres) or 'todas, en su orden'} · {destino}")
        return 0

    if o.directorios is not None or o.tope is not None:
        try:
            if o.directorios is not None:
                dirs = [d.strip().strip("/") for d in o.directorios.split(",") if d.strip()]
                faltan = [d for d in dirs if not (ctx.config.raiz / d).is_dir()]
                if faltan:
                    return _comun.queja(f"no existe en {ctx.config.raiz}: {', '.join(faltan)}")
                destino = escribir_clave("hilos", "directorios", dirs or None, ctx.config.origen)
            if o.tope is not None:
                destino = escribir_clave("hilos", "tope", o.tope, ctx.config.origen)
        except ErrorDeConfig as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json({"hilos": "ok", "archivo": str(destino)})
        print(f"hilos · {destino}")
        return 0

    if o.reunion is not None:
        valor = o.reunion.strip() or None  # vacío: se borra la clave y rige el de fábrica
        try:
            destino = escribir_clave("agente", "reunion", valor, ctx.config.origen)
        except ErrorDeConfig as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json({"reunion": valor or REUNION_POR_DEFECTO, "archivo": str(destino)})
        print(f"reunión: {valor or REUNION_POR_DEFECTO} · {destino}")
        return 0

    if o.proyecto is not None:
        valor = o.proyecto.strip() or None
        try:
            destino = escribir_clave("agente", "proyecto", valor, ctx.config.origen)
        except ErrorDeConfig as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json({"proyecto": valor or PROYECTO_POR_DEFECTO, "archivo": str(destino)})
        print(f"proyecto: {valor or PROYECTO_POR_DEFECTO} · {destino}")
        return 0

    if o.calendario:
        try:
            destino = escribir_calendario(o.calendario, ctx.config.origen)
        except ErrorDeConfig as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json({"calendario": "conectado", "archivo": str(destino)})
        print(f"calendario: {o.calendario if o.calendario.strip().lower() in ('gws', 'ninguno') else 'ics'} · {destino}")
        return 0

    cfg = ctx.config
    if o.ruta:
        print(cfg.origen or ruta_config())
        return 0

    cuerpo = servicio.resuelta(ctx).model_dump(mode="json", exclude_unset=True)
    pisadas = cuerpo.get("entorno") or {}
    if o.json:
        return _comun.escribir_json(cuerpo)

    if cfg.origen:
        print(_comun.fuerte(str(cfg.origen)))
    else:
        print(_comun.fuerte("sin archivo: todo por defecto"))
        print(_comun.tenue(f"  se buscaría en {ruta_config()} · `telar init` lo escribe"))
    for clave in ("multiplexor", "sesion", "raiz", "estado", "ruta_perfil"):
        print(f"  {clave:<13} {cuerpo[clave]}")
    intervalos = " · ".join(f"{k} {v:g}s" for k, v in cuerpo["intervalos"].items())
    print(f"  {'intervalos':<13} {intervalos}")
    if cfg.proveedores:
        for nombre, pr in cfg.proveedores.items():
            marca = "activo" if pr.activo else "apagado"
            opciones = ", ".join(f"{k}={v}" for k, v in _sin_secretos(pr.opciones).items())
            print(f"  {'proveedor':<13} {nombre} ({marca}) {_comun.tenue(opciones)}")
    else:
        print(f"  {'proveedores':<13} " + _comun.tenue("ninguno: telar no sale a la red"))
    if pisadas:
        print()
        print(_comun.tenue("pisado por el entorno: " + ", ".join(f"{k}={v}" for k, v in pisadas.items())))
    return 0


