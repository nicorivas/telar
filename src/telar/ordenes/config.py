"""`telar config` — la configuración resuelta, y de dónde salió cada cosa.

No hay modo «adivina»: si telar se está portando raro, esto dice exactamente con
qué valores está trabajando, qué archivo los trajo y qué variable de entorno los
pisó. El esquema completo está en `docs/configuracion.md`.
"""

from __future__ import annotations

import os

from telar.config import MULTIPLEXORES, ruta_config  # noqa: F401 - MULTIPLEXORES: quien lo importaba de aquí
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
        from telar.servicios import ErrorDeServicio

        try:
            r = servicio.pestanas(ctx, o.pestanas)
        except ErrorDeServicio as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r.model_dump(mode="json"))
        nombres = [x.strip() for x in o.pestanas.split(",") if x.strip()]
        print(f"pestañas: {', '.join(nombres) or 'todas, en su orden'} · {r.archivo}")
        return 0

    if o.directorios is not None or o.tope is not None or o.reunion is not None or o.proyecto is not None or o.calendario:
        from telar.servicios import ErrorDeServicio

        try:
            if o.directorios is not None or o.tope is not None:
                if o.directorios is not None:
                    r = servicio.directorios(ctx, o.directorios)
                if o.tope is not None:
                    r = servicio.tope(ctx, o.tope)
                linea = f"hilos · {r.archivo}"
            elif o.reunion is not None:
                r = servicio.plantilla(ctx, "reunion", o.reunion)
                linea = f"reunión: {r.reunion} · {r.archivo}"
            elif o.proyecto is not None:
                r = servicio.plantilla(ctx, "proyecto", o.proyecto)
                linea = f"proyecto: {r.proyecto} · {r.archivo}"
            else:
                r = servicio.calendario(ctx, o.calendario)
                tipo = o.calendario if o.calendario.strip().lower() in ("gws", "ninguno") else "ics"
                linea = f"calendario: {tipo} · {r.archivo}"
        except ErrorDeServicio as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r.model_dump(mode="json"))
        print(linea)
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
    for r in cuerpo.get("repos") or []:
        perfil = f" · perfil {r['perfil']}" if r["perfil"] else ""
        print(f"  {'repo':<13} {r['nombre']} {_comun.tenue(r['ruta'] + perfil)}")
    for m in cuerpo.get("modulos") or []:
        de = f"{m['fuente']} @ {m['version']}" if m["instalado"] else "(a mano)"
        print(f"  {'modulo':<13} {m['nombre']} {_comun.tenue(de)}")
    if pisadas:
        print()
        print(_comun.tenue("pisado por el entorno: " + ", ".join(f"{k}={v}" for k, v in pisadas.items())))
    return 0


