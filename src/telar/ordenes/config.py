"""`telar config` — la configuración resuelta, y de dónde salió cada cosa.

No hay modo «adivina»: si telar se está portando raro, esto dice exactamente con
qué valores está trabajando, qué archivo los trajo y qué variable de entorno los
pisó. El esquema completo está en `docs/configuracion.md`.
"""

from __future__ import annotations

import os

from telar.config import MULTIPLEXORES, ruta_config
from telar.ordenes import _comun

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
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    cfg = ctx.config
    if o.ruta:
        print(cfg.origen or ruta_config())
        return 0

    pisadas = {v: os.environ[k] for k, v in ENTORNO.items() if os.environ.get(k)}
    cuerpo = {
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
        "proveedores": {
            nombre: {"activo": pr.activo, "opciones": pr.opciones}
            for nombre, pr in cfg.proveedores.items()
        },
        "entorno": pisadas,
        "multiplexores": list(MULTIPLEXORES),
    }
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
            opciones = ", ".join(f"{k}={v}" for k, v in pr.opciones.items())
            print(f"  {'proveedor':<13} {nombre} ({marca}) {_comun.tenue(opciones)}")
    else:
        print(f"  {'proveedores':<13} " + _comun.tenue("ninguno: telar no sale a la red"))
    if pisadas:
        print()
        print(_comun.tenue("pisado por el entorno: " + ", ".join(f"{k}={v}" for k, v in pisadas.items())))
    return 0
