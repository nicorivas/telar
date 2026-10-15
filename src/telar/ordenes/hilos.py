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

    tel = _comun.tejer(ctx, con_ficha=not o.sin_ficha, todos=not o.vivos)
    hilos = mod_estado.ordenar(tel.hilos, o.orden)
    vivos, sin_ventana, archivados = mod_estado.repartir(hilos, tel.vivos)

    otras, maquinas, aviso_red = _red(ctx) if o.red else ([], [], "")
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
                **({"otras_maquinas": otras, "maquinas": maquinas, "aviso_red": aviso_red} if o.red else {}),
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
    if o.red:
        _imprimir_red(otras, maquinas, aviso_red, tel)
    return 0


def _red(ctx) -> tuple[list[dict], list[dict], str]:
    """Los hilos de las otras máquinas, como los registra el bus: (hilos, máquinas, aviso).

    El bus tiene un registro de todos los hilos de la persona, de cualquier máquina; cada nodo
    publica los suyos. `telar hilos` a secas lee solo el multiplexor de aquí, por eso no veía los del
    laptop. Un hilo del registro lleva `vivo` según lo último que publicó su máquina: si esa máquina
    se apagó, no pudo decirlo, y `maquinas` trae si su espejo sigue en línea.
    """
    from telar import bus as mod_bus
    from telar import espejo as mod_espejo

    if not ctx.config.bus.url:
        return [], [], "no hay bus ([bus] en la configuración): solo se ven los hilos de esta máquina"
    try:
        registro = mod_bus.estados(ctx.config)
    except mod_bus.ErrorDeBus as e:
        return [], [], f"{e}; se muestran solo los hilos de esta máquina"
    yo = mod_bus.maquina(ctx.config)
    otras = [
        {"nombre": d.get("nombre") or n, "maquina": d.get("maquina", ""), "vivo": bool(d.get("vivo")),
         "atencion": d.get("atencion", "ninguna"), "atencion_desde": d.get("desde", ""),
         "residente": d.get("residente", ""), "actualizado": d.get("actualizado", "")}
        for n, d in sorted(registro.items(), key=lambda x: (x[1].get("maquina", ""), x[0].lower()))
        if d.get("maquina") and d.get("maquina") != yo
    ]
    try:
        maquinas = [{"nombre": e.get("nombre"), "en_linea": bool(e.get("en_linea")), "edad": e.get("edad")}
                    for e in mod_espejo.leer_todos(ctx.config)]
    except Exception:  # noqa: BLE001 - sin espejos, solo falta saber si la máquina sigue encendida
        maquinas = []
    return otras, maquinas, ""


def _imprimir_red(otras: list[dict], maquinas: list[dict], aviso: str, tel) -> None:
    if aviso:
        print(_comun.tenue(f"({aviso})"))
    apagadas = {m["nombre"] for m in maquinas if not m["en_linea"]}
    for maquina in dict.fromkeys(h["maquina"] for h in otras):
        suyos = [h for h in otras if h["maquina"] == maquina]
        vivos = [h for h in suyos if h["vivo"]]
        nota = " · apagada o sin señal: lo último que dijo" if maquina in apagadas else ""
        print(_comun.fuerte(f"{maquina} · {len(vivos)} hilos") + (_comun.tenue(nota) if nota else ""))
        for h in vivos:
            print(f"  {h['nombre']}  " + _comun.tenue(h["atencion"] if h["atencion"] != "ninguna" else ""))
        if len(suyos) > len(vivos):
            print(_comun.tenue(f"  y {len(suyos) - len(vivos)} cerrados o archivados"))


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

