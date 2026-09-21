"""`telar ficha` — lo que el documento de un hilo dice de sí mismo.

Un hilo vale por su carpeta, y la carpeta ya se explica en su documento. La ficha
no inventa nada: lee ese documento como lo declara el perfil y lo pone en una
pantalla, junto con lo que telar sabe del hilo (atención, tiempo, conversaciones) y
las acciones que el repositorio ofrece sobre él.

Sin argumento, el hilo actual (`$TELAR_HILO`, y si no, el del foco).
"""

from __future__ import annotations

import shutil

from telar.ordenes import _comun

AYUDA = "Lo que el documento de un hilo dice de sí mismo."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("ficha", AYUDA)
    p.add_argument("hilo", nargs="?", default="", help="id o nombre del hilo (por defecto, este)")
    p.add_argument("--json", action="store_true", help="los datos, en una línea (docs/contratos.md)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx)
    if o.hilo:
        hilo, problema = _comun.resolver(tel, o.hilo)
        if hilo is None:
            return _comun.queja(problema)
    else:
        hilo = _comun.hilo_actual(tel)
        if hilo is None:
            return _comun.queja(
                "no sé en qué hilo estoy. Dime cuál: telar ficha <hilo>"
                + (f"\n{tel.aviso}" if tel.aviso else "")
            )

    acciones = [
        {
            "nombre": a.nombre,
            "descripcion": a.descripcion,
            "tecla": a.tecla,
            "donde": a.donde,
            "confirmar": a.confirmar,
        }
        for a in ctx.perfil.acciones
    ]

    if o.json:
        return _comun.escribir_json(
            {
                "hilo": _comun.json_hilo(hilo, tel),
                "seguro": _comun.seguro(tel),
                "acciones": acciones,
                "perfil": ctx.perfil.nombre,
            }
        )

    ancho = shutil.get_terminal_size((100, 24)).columns
    ficha = hilo.ficha
    titulo = (ficha.titulo if ficha else "") or hilo.nombre
    print(_comun.fuerte(titulo) + "  " + _comun.tenue(_comun.ruta_relativa(hilo.ruta, tel.raiz)))

    detalles = []
    if hilo.arquetipo:
        detalles.append(hilo.arquetipo)
    if not tel.vivo(hilo):
        detalles.append("no vivo")
    if hilo.archivado:
        detalles.append("archivado")
    if hilo.prioridad:
        detalles.append(f"prioridad {int(hilo.prioridad)}")
    if hilo.atencion.value != "ninguna":
        detalles.append(f"atención: {hilo.atencion.value}")
    if hilo.tiempo:
        detalles.append(f"hoy {_comun.duracion(hilo.tiempo)}")
    if hilo.sesiones:
        detalles.append(f"{len(hilo.sesiones)} conversación(es)")
    if detalles:
        print(_comun.tenue("  " + " · ".join(detalles)))
    if not _comun.seguro(tel) and not o.hilo:
        print(_comun.tenue(f"  (el hilo salió del foco, no de ${_comun.VARIABLE_HILO})"))

    if ficha is None or ficha.documento is None:
        print()
        print("  sin documento: el hilo no está vinculado a ninguna unidad del perfil.")
        print(_comun.tenue("  telar hilo vincular <carpeta>"))
        return 0

    if ficha.nota:
        print(_comun.tenue(f"  {ficha.nota}"))

    print()
    print(_comun.fuerte("ESTADO"))
    print(f"  {ficha.estado[:ancho - 4]}" if ficha.estado else _comun.tenue("  —"))

    if ficha.pendientes:
        print()
        print(_comun.fuerte("PENDIENTES"))
        for i, pendiente in enumerate(ficha.pendientes, 1):
            casilla = "▣" if pendiente.en_curso else ("✓" if pendiente.hecho else "☐")
            ref = f"{hilo.nombre}:{i}"
            print(f"  {casilla} {_comun.tenue(ref):<18} {pendiente.texto[:ancho - 24]}")

    for nombre, valor in ficha.secciones.items():
        print()
        print(_comun.fuerte(nombre.upper()))
        for linea in _dibujar(valor, ancho):
            print(linea)

    if ctx.perfil.acciones:
        print()
        print(_comun.fuerte("ACCIONES") + _comun.tenue("  (telar accion <nombre>)"))
        for a in ctx.perfil.acciones:
            tecla = f"[{a.tecla}] " if a.tecla else "    "
            print(f"  {tecla}{a.nombre:<12} {_comun.tenue(a.descripcion[:ancho - 20])}")
    return 0


def _dibujar(valor, ancho: int) -> list[str]:
    if isinstance(valor, dict):
        return [f"  {k}: {_recortar(str(v), ancho - len(k) - 6)}" for k, v in valor.items()]
    if isinstance(valor, (tuple, list)):
        return [_vinieta(v, ancho) for v in valor]
    texto = str(valor)
    return [f"  {_recortar(l, ancho - 4)}" for l in texto.splitlines()[:8] if l.strip()]


#: De dónde sale el texto de un elemento de sección, en orden: una espera y un enlace
#: lo traen en `texto`, un hito en `que` (docs/contratos.md).
_CAMPOS_TEXTO = ("texto", "que")

#: Y qué se le cuelga detrás: la fecha que lo vence, o el destino al que apunta.
_CAMPOS_COLA = ("cuando", "destino")

#: Mínimo que se le deja al texto por angosta que venga la terminal. Sin este piso,
#: un recorte negativo cortaría por el final en vez de por el principio.
_MINIMO = 8


def _recortar(texto: str, tope: int) -> str:
    return _comun.recortar(texto, tope, minimo=_MINIMO)


def _vinieta(valor, ancho: int) -> str:
    """Un elemento de una sección tipo lista, en una línea.

    Las secciones `esperando`, `hitos` y `enlaces` no llegan como cadenas: son los
    diccionarios del contrato, y ese es todo el vocabulario que esta función conoce.
    Lo que no reconozca se imprime tal cual, que es mejor que esconderlo.
    """
    texto, cola = "", ""
    if isinstance(valor, dict):
        texto = next((str(valor[c]) for c in _CAMPOS_TEXTO if valor.get(c)), "")
        cola = next((str(valor[c]) for c in _CAMPOS_COLA if valor.get(c)), "")
    if not texto:
        return f"  · {_recortar(str(valor), ancho - 6)}"
    if not cola:
        return f"  · {_recortar(texto, ancho - 6)}"
    # La cola es corta y dice lo más caro de la línea (cuándo vence, adónde va): se
    # recorta el texto, nunca ella.
    return f"  · {_recortar(texto, ancho - 9 - len(cola))} — {cola}"
