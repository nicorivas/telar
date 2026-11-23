"""`telar hilos` — los hilos de la sesión, con lo que telar sabe de cada uno.

Los de esta máquina: los de las otras, con `--red` (el registro del bus), en su propia lista
(`otras_maquinas`). Sin `--red` no se le pregunta nada al bus, y un hilo del laptop no aparece en
la lista del servidor: por eso cada hilo dice su `maquina`, y el texto dice de cuál es la lista.

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

AYUDA = "Los hilos de esta máquina, con su estado; con --red, también los de las demás."

#: lo que antes vivía aquí: quien lo importaba lo sigue encontrando
_red, _clientes = servicio._red, servicio._clientes


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("hilos", AYUDA)
    p.add_argument("--json", action="store_true", help="los datos, en una línea (docs/contratos.md)")
    p.add_argument("--vivos", action="store_true", help="solo los que el multiplexor muestra ahora")
    p.add_argument("--red", action="store_true",
                   help="además, los hilos de las otras máquinas, del registro del bus (en el JSON, `otras_maquinas`); "
                        "sin --red, solo los de esta")
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
    _imprimir(r, o.red, hay_bus=bool(getattr(getattr(ctx.config, "bus", None), "url", "")))
    return 0


def _imprimir(r: servicio.Hilos, red: bool, *, hay_bus: bool = False) -> None:
    ancho = shutil.get_terminal_size((100, 24)).columns
    # abiertos, sin ventana y archivados, sin reordenar (telar.estado.repartir, sobre el modelo)
    vivos = [h for h in r.hilos if not h.archivado and h.vivo]
    sin_ventana = [h for h in r.hilos if not h.archivado and not h.vivo]
    archivados = [h for h in r.hilos if h.archivado]
    if r.aviso:
        print(_comun.tenue(f"({r.aviso})"))
    cabecera = f"sesión «{r.sesion}»" + (f" en {r.maquina}" if r.maquina else "") + f" · {len(vivos)} hilos"
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

    # la columna del repo, solo si la lista abarca más de uno: con uno solo (o sin [repos]) no dice nada.
    # «ninguno» no cuenta como un repo más: un hilo fuera de todos junto a los de uno solo no la abre
    repos = len({h.repo for h in r.hilos if h.ruta and h.repo}) > 1
    for hilo in vivos:
        print(_linea(hilo, ancho, repos))
    if sin_ventana:
        print(_comun.tenue(f"sin ventana ({len(sin_ventana)})"))
        for hilo in sin_ventana:
            print(_linea(hilo, ancho, repos))
        if r.viva:
            # el caso que muerde: renombrar un tab desde el multiplexor deja aquí el nombre viejo, con
            # su vínculo y su prioridad, y el tab vivo sin nada
            print(_comun.tenue("  el multiplexor no los muestra;"
                               " `telar hilo adoptar <nombre>` le devuelve ese estado a un tab renombrado"))
    if archivados:
        print(_comun.tenue(f"archivados ({len(archivados)})"))
        for hilo in archivados:
            print(_linea(hilo, ancho, repos))
    if red:
        _imprimir_red(r)
    elif hay_bus:
        # sin esto, quien busca un hilo del laptop desde el servidor concluye que no existe
        print(_comun.tenue("solo los de esta máquina: `telar hilos --red` suma los de las otras"))


def _imprimir_red(r: servicio.Hilos) -> None:
    if r.aviso_red:
        print(_comun.tenue(f"({r.aviso_red})"))
    otras, maquinas = r.otras_maquinas or [], r.maquinas or []
    apagadas = {m.nombre for m in maquinas if not m.en_linea}
    por_nombre = {m.nombre: m for m in maquinas}
    from telar import alcance

    for maquina in dict.fromkeys([*(h.maquina for h in otras), *(m.nombre for m in maquinas if m.cola or m.hechos)]):
        suyos = [h for h in otras if h.maquina == maquina]
        vivos = [h for h in suyos if h.vivo]
        m = por_nombre.get(maquina)
        if suyos and not suyos[0].alcanzable:
            # fuera de línea (telar.alcance): lo que se sabe de sus hilos es de antes de irse
            desde = alcance.desde_texto(_epoca(suyos[0].fuera_de_linea_desde))
            print(_comun.fuerte(f"{maquina} · fuera de línea desde {desde}")
                  + _comun.tenue(f" · {len(vivos)} hilos abiertos cuando se fue: inalcanzables hasta que vuelva"))
            for h in vivos:
                antes = "dormía" if h.dormido else {"trabajando": "trabajaba", "espera": "te esperaba",
                                                    "termino": "había terminado"}.get(h.atencion, "")
                print(f"  · {h.nombre}  " + _comun.tenue("inalcanzable" + (f" (cuando se fue, {antes})" if antes else "")))
        else:
            nota = " · apagada o sin señal: lo último que dijo" if maquina in apagadas else ""
            print(_comun.fuerte(f"{maquina} · {len(vivos)} hilos") + (_comun.tenue(nota) if nota else ""))
            for h in vivos:
                estado = "dormido" if h.dormido else h.atencion if h.atencion != "ninguna" else ""
                print(f"  {DORMIDO if h.dormido else ' '} {h.nombre}  " + _comun.tenue(estado))
        if len(suyos) > len(vivos):
            print(_comun.tenue(f"  y {len(suyos) - len(vivos)} cerrados o archivados"))
        for p in (m.cola if m else []):
            print(_comun.tenue(f"  en cola desde {alcance.desde_texto(p.get('cuando'))}: despertar «{p.get('hilo')}»"
                               + (" con un texto" if p.get("texto") else "") + " (se hace cuando vuelva)"))
        for x in (m.hechos[:3] if m else []):
            print(_comun.tenue(f"  de la cola, {alcance.desde_texto(x.get('hecho_en'))}: "
                               + ("" if x.get("ok") else "falló: ") + str(x.get("resultado", ""))))


def _epoca(iso: str) -> float | None:
    from datetime import datetime

    try:
        return datetime.fromisoformat(iso).timestamp() if iso else None
    except ValueError:
        return None


#: un hilo dormido (telar.dormir): un aro, como en la página (falta: detenido), tenue
DORMIDO = "◌"


def _linea(hilo: servicio.Hilo, ancho: int, repos: bool = False) -> str:
    """Una fila: atención, id, nombre, carpeta, tiempo de hoy y la línea de estado. Con `repos`, entre
    el tiempo y el estado va el repo de su carpeta, tenue como el estado («—» si no es de ninguno)."""
    marca = _comun.SIMBOLO.get(_comun.Atencion(hilo.atencion), " ") if hilo.vivo else "·"
    if hilo.vivo and hilo.dormido and marca == " ":
        # dormido (telar.dormir): un aro, tenue; lo que terminó sin que se viera se sigue diciendo
        marca = _comun.tenue(DORMIDO)
    prioridad = str(hilo.prioridad) if hilo.prioridad else " "
    carpeta = hilo.relativa or "—"
    tiempo = _comun.duracion(hilo.tiempo)
    izquierda = f"{marca} {prioridad} {hilo.id:>3}  {hilo.nombre[:18]:<18}  {carpeta[:26]:<26} {tiempo:>5}  "
    estado = (hilo.ficha.estado or hilo.ficha.nota) if hilo.ficha else ""
    if hilo.vivo and hilo.dormido:
        estado = "dormido" + (f" · {estado}" if estado else "")
    if repos:
        repo = (hilo.repo or ("—" if hilo.ruta else ""))[:12]
        izquierda_repo = f"{repo:<12}  "
    else:
        izquierda_repo = ""
    resto = max(ancho - len(izquierda) - len(izquierda_repo) - 1, 12)
    return izquierda + _comun.tenue(izquierda_repo + estado[:resto])
