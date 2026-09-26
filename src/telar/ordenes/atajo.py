"""`telar atajo` — una tecla del dashboard: un hilo nuevo con el agente haciendo algo recurrente.

    telar atajo           los atajos declarados
    telar atajo m         abre «⚑ correo 09/23 09:14» con el agente y su mensaje
    telar atajo m --json

Se declaran en la configuración, uno por tecla:

    [atajos.m]
    nombre = "⚑ correo"
    mensaje = "/correo"
    descripcion = "procesar el correo de hoy"

Cada vez es un hilo nuevo con la hora en el nombre: la revisión de la mañana y la de la
tarde son dos conversaciones, y la de la mañana puede seguir abierta. El agente arranca en
`[agente] carpeta` y el mensaje es su primer prompt.
"""

from __future__ import annotations

import datetime as dt

from telar.agente import ErrorDeAgente
from telar.agente import lanzar
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Una tecla del dashboard: un hilo con el agente haciendo algo recurrente."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("atajo", AYUDA)
    p.epilog = __doc__
    p.add_argument("tecla", nargs="?", default="", help="la del atajo; sin ella, la lista")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    atajos = {a.tecla: a for a in ctx.config.atajos}
    if not o.tecla:
        if o.json:
            return _comun.escribir_json({"atajos": [
                {"tecla": a.tecla, "nombre": a.nombre, "mensaje": a.mensaje, "descripcion": a.descripcion}
                for a in atajos.values()]})
        if not atajos:
            print(_comun.tenue("no hay atajos: se declaran en la configuración, [atajos.<tecla>]"))
        for a in atajos.values():
            print(f"{a.tecla}  {a.nombre}  " + _comun.tenue(a.descripcion or a.mensaje))
        return 0

    atajo = atajos.get(o.tecla)
    if atajo is None:
        return _comun.queja(f"no hay atajo en «{o.tecla}»: `telar atajo` lista los que hay")
    nombre = f"{atajo.nombre} {dt.datetime.now():%m/%d %H:%M}"
    problema = abrir(ctx, nombre, atajo.mensaje)
    if problema:
        return _comun.queja(problema)
    if o.json:
        return _comun.escribir_json({"hilo": nombre, "mensaje": atajo.mensaje})
    print(f"{nombre} · {atajo.mensaje}")
    return 0


def abrir(ctx, nombre: str, mensaje: str) -> str:
    """Un hilo nuevo `nombre` con el agente en `[agente] carpeta` y `mensaje` como primer
    prompt, al frente. "" si se abrió; si no, por qué. Lo usan los atajos y los ítems de un
    bloque del día."""
    if not ctx.config.agente.nombre:
        return "abrir un hilo con el agente pide uno: [agente] nombre = \"claude-code\""
    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None or not tel.viva:
        return tel.aviso or "la sesión no está viva: primero telar tejer"
    try:
        from telar import agente as mod_agente

        palabras, sid = mod_agente.obtener(ctx.config.agente.nombre, ctx.config).nuevo_con_id(mensaje)
        lanz = lanzar.Lanzamiento(
            comando=lanzar.envolver(palabras, nombre),
            carpeta=lanzar.carpeta(ctx.config, None),
            nueva=sid,
        )
        tel.mux.crear_tab(nombre, ruta=lanz.carpeta, comando=lanz.comando, foco=True)
        lanzar.anotar(ctx.config, nombre, lanz)
        hilo = next((h for h in tel.mux.hilos() if h.nombre == nombre), None)
        if hilo is not None:
            tel.mux.ir(hilo.id)
    except (ErrorDeMux, ErrorDeAgente) as e:
        return f"no pude abrir «{nombre}»: {e}"
    return ""
