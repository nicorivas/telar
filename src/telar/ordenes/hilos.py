"""`telar hilos` — los hilos de la sesión, con lo que telar sabe de cada uno.

Es la orden que contesta «qué tengo abierto»: el multiplexor pone los tabs, el
estado pone el vínculo, la prioridad, la atención y el tiempo, y el documento de
cada hilo pone su estado en una línea.

Los hilos que el multiplexor no muestra —archivados, de una sesión que todavía no
se levanta, o un nombre que quedó huérfano porque el tab se renombró desde el
multiplexor— aparecen igual, en su propia sección: un hilo archivado sigue siendo
trabajo, y esconderlo es perderlo.

Son tres grupos y no dos, y la diferencia se cuenta: arriba, lo que el multiplexor
muestra ahora; después, lo que telar recuerda sin ventana; al final, el cajón de los
archivados. La cabecera cuenta el primero, porque «4 hilos» con tres ventanas
abiertas es un número que miente.
"""

from __future__ import annotations

import shutil

from telar import estado as mod_estado
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Los hilos de la sesión, con su estado."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hilos", AYUDA)
    p.add_argument("--json", action="store_true", help="los datos, en una línea (docs/contratos.md)")
    p.add_argument("--vivos", action="store_true", help="solo los que el multiplexor muestra ahora")
    p.add_argument("--sin-ficha", action="store_true", help="no leer los documentos (más rápido)")
    p.add_argument(
        "--orden",
        choices=[o.value for o in mod_estado.Orden],
        default=mod_estado.Orden.MUX.value,
        help="cómo ordenarlos (por defecto, como los da el multiplexor)",
    )
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx, con_ficha=not o.sin_ficha, todos=not o.vivos)
    hilos = mod_estado.ordenar(tel.hilos, o.orden)
    vivos, sin_ventana, archivados = mod_estado.repartir(hilos, tel.vivos)

    if o.json:
        return _comun.escribir_json(
            {
                "sesion": tel.sesion,
                "viva": tel.viva,
                "raiz": str(tel.raiz),
                "multiplexor": ctx.config.multiplexor,
                "aviso": tel.aviso,
                "orden": o.orden,
                "clientes": _clientes(tel),
                "hilos": [_comun.json_hilo(h, tel, con_ficha=not o.sin_ficha) for h in hilos],
            }
        )

    ancho = shutil.get_terminal_size((100, 24)).columns
    if tel.aviso:
        print(_comun.tenue(f"({tel.aviso})"))
    cabecera = f"sesión «{tel.sesion}» · {len(vivos)} hilos"
    if sin_ventana:
        cabecera += f" · {len(sin_ventana)} sin ventana"
    if archivados:
        cabecera += f" · {len(archivados)} archivados"
    if not tel.viva:
        cabecera += " · la sesión no está viva (telar tejer)"
    print(_comun.fuerte(cabecera))
    if not hilos:
        print(_comun.tenue("  ninguno todavía. `telar tejer` levanta la sesión."))
        return 0

    for hilo in vivos:
        print(_linea(hilo, tel, ancho))
    if sin_ventana:
        print(_comun.tenue(f"sin ventana ({len(sin_ventana)})"))
        for hilo in sin_ventana:
            print(_linea(hilo, tel, ancho))
        if tel.viva:
            # el caso que muerde: renombrar un tab desde el multiplexor deja aquí el
            # nombre viejo, con su vínculo y su prioridad, y el tab vivo sin nada
            print(
                _comun.tenue(
                    "  el multiplexor no los muestra;"
                    " `telar hilo adoptar <nombre>` le devuelve ese estado a un tab renombrado"
                )
            )
    if archivados:
        print(_comun.tenue(f"archivados ({len(archivados)})"))
        for hilo in archivados:
            print(_linea(hilo, tel, ancho))
    return 0


def _linea(hilo, tel: _comun.Telar, ancho: int) -> str:
    """Una fila: atención, id, nombre, carpeta, tiempo de hoy y la línea de estado."""
    marca = _comun.SIMBOLO.get(hilo.atencion, " ")
    if not tel.vivo(hilo):
        marca = "·"
    prioridad = str(int(hilo.prioridad)) if hilo.prioridad else " "
    carpeta = _comun.ruta_relativa(hilo.ruta, tel.raiz) or "—"
    tiempo = _comun.duracion(hilo.tiempo)
    izquierda = f"{marca} {prioridad} {hilo.id:>3}  {hilo.nombre[:18]:<18}  {carpeta[:26]:<26} {tiempo:>5}  "
    estado = ""
    if hilo.ficha is not None:
        estado = hilo.ficha.estado or hilo.ficha.nota
    resto = max(ancho - len(izquierda) - 1, 12)
    return izquierda + _comun.tenue(estado[:resto])


def _clientes(tel) -> list[int]:
    """Los pids de las terminales que muestran la sesión; vacío si no se puede saber."""
    if tel.mux is None or not tel.viva:
        return []
    try:
        return tel.mux.clientes()
    except ErrorDeMux:
        return []

