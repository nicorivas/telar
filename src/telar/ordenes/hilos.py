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
from telar.ordenes import _comun
from telar.servicios import hilos as servicio

AYUDA = "Los hilos de la sesión, con su estado."

#: lo que antes vivía aquí: quien lo importaba lo sigue encontrando
_red, _clientes = servicio._red, servicio._clientes


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hilos", AYUDA)
    p.add_argument("--json", action="store_true", help="los datos, en una línea (docs/contratos.md)")
    p.add_argument("--vivos", action="store_true", help="solo los que el multiplexor muestra ahora")
    p.add_argument("--red", action="store_true",
                   help="además, los hilos de las otras máquinas (el registro del bus): todos, en todos los computadores")
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

    r = servicio.hilos(ctx, vivos=o.vivos, red=o.red, con_ficha=not o.sin_ficha, orden=o.orden)
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json", exclude_unset=True))
    _imprimir(r, o.red)
    return 0


def _imprimir(r: servicio.Hilos, red: bool) -> None:
    ancho = shutil.get_terminal_size((100, 24)).columns
    # abiertos, sin ventana y archivados, sin reordenar (telar.estado.repartir, sobre el modelo)
    vivos = [h for h in r.hilos if not h.archivado and h.vivo]
    sin_ventana = [h for h in r.hilos if not h.archivado and not h.vivo]
    archivados = [h for h in r.hilos if h.archivado]
    if r.aviso:
        print(_comun.tenue(f"({r.aviso})"))
    cabecera = f"sesión «{r.sesion}» · {len(vivos)} hilos"
    if sin_ventana:
        cabecera += f" · {len(sin_ventana)} sin ventana"
    if archivados:
        cabecera += f" · {len(archivados)} archivados"
    if not r.viva:
        cabecera += " · la sesión no está viva (telar tejer)"
    print(_comun.fuerte(cabecera))
    if not r.hilos:
        print(_comun.tenue("  ninguno todavía. `telar tejer` levanta la sesión."))
        return

    for hilo in vivos:
        print(_linea(hilo, ancho))
    if sin_ventana:
        print(_comun.tenue(f"sin ventana ({len(sin_ventana)})"))
        for hilo in sin_ventana:
            print(_linea(hilo, ancho))
        if r.viva:
            # el caso que muerde: renombrar un tab desde el multiplexor deja aquí el nombre viejo, con
            # su vínculo y su prioridad, y el tab vivo sin nada
            print(_comun.tenue("  el multiplexor no los muestra;"
                               " `telar hilo adoptar <nombre>` le devuelve ese estado a un tab renombrado"))
    if archivados:
        print(_comun.tenue(f"archivados ({len(archivados)})"))
        for hilo in archivados:
            print(_linea(hilo, ancho))
    if red:
        _imprimir_red(r)


def _imprimir_red(r: servicio.Hilos) -> None:
    if r.aviso_red:
        print(_comun.tenue(f"({r.aviso_red})"))
    otras, maquinas = r.otras_maquinas or [], r.maquinas or []
    apagadas = {m.nombre for m in maquinas if not m.en_linea}
    for maquina in dict.fromkeys(h.maquina for h in otras):
        suyos = [h for h in otras if h.maquina == maquina]
        vivos = [h for h in suyos if h.vivo]
        nota = " · apagada o sin señal: lo último que dijo" if maquina in apagadas else ""
        print(_comun.fuerte(f"{maquina} · {len(vivos)} hilos") + (_comun.tenue(nota) if nota else ""))
        for h in vivos:
            print(f"  {h.nombre}  " + _comun.tenue(h.atencion if h.atencion != "ninguna" else ""))
        if len(suyos) > len(vivos):
            print(_comun.tenue(f"  y {len(suyos) - len(vivos)} cerrados o archivados"))


def _linea(hilo: servicio.Hilo, ancho: int) -> str:
    """Una fila: atención, id, nombre, carpeta, tiempo de hoy y la línea de estado."""
    marca = _comun.SIMBOLO.get(_comun.Atencion(hilo.atencion), " ") if hilo.vivo else "·"
    prioridad = str(hilo.prioridad) if hilo.prioridad else " "
    carpeta = hilo.relativa or "—"
    tiempo = _comun.duracion(hilo.tiempo)
    izquierda = f"{marca} {prioridad} {hilo.id:>3}  {hilo.nombre[:18]:<18}  {carpeta[:26]:<26} {tiempo:>5}  "
    estado = (hilo.ficha.estado or hilo.ficha.nota) if hilo.ficha else ""
    resto = max(ancho - len(izquierda) - 1, 12)
    return izquierda + _comun.tenue(estado[:resto])
