"""`telar doctor` — qué está en su sitio, qué no, y qué hacer con lo que no.

Una revisión por cosa que puede fallar, y cada falla con su arreglo escrito al
lado. Nada de esto cambia nada: doctor mira y dice.

Sale con 0 si no hay fallas y con 1 si hay alguna, para que se pueda encadenar.
Un aviso no es una falla: telar funciona sin perfil, sin proveedores y sin
ganchos, solo hace menos.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
from pathlib import Path

from telar import estado as mod_estado
from telar import lectura
from telar.config import ruta_config
from telar.mux import ErrorDeMux
from telar.mux import obtener as obtener_mux
from telar.ordenes import _comun
from telar.perfil import NOMBRE_ARCHIVO
from telar.proveedores import REGISTRO

AYUDA = "Revisar multiplexor, sesión, perfil, proveedores y ganchos."

OK, AVISO, FALLA = "ok", "aviso", "falla"
MARCA = {OK: "✓", AVISO: "·", FALLA: "✗"}


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("doctor", AYUDA)
    p.add_argument("--json", action="store_true", help="las revisiones, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    abiertos = _abiertos(ctx)
    revisiones: list[dict] = []
    revisiones += _configuracion(ctx)
    revisiones += _raiz(ctx)
    revisiones += _multiplexor(ctx)
    revisiones += _perfil(ctx)
    revisiones += _estado(ctx)
    revisiones += _vinculos(ctx, abiertos)
    revisiones += _ficha(ctx)
    revisiones += _proveedores(ctx)
    revisiones += _ganchos(ctx, abiertos)

    fallas = [r for r in revisiones if r["estado"] == FALLA]

    if o.json:
        _comun.escribir_json({"ok": not fallas, "revisiones": revisiones})
        return 1 if fallas else 0

    ancho = shutil.get_terminal_size((100, 24)).columns
    for r in revisiones:
        print(f"  {MARCA[r['estado']]} {r['nombre']:<14} {r['dice'][:ancho - 20]}")
        if r["arreglo"] and r["estado"] != OK:
            print(_comun.tenue(f"      → {r['arreglo']}"))
    print()
    if fallas:
        print(_comun.fuerte(f"{len(fallas)} falla(s)"))
    else:
        print(_comun.fuerte("sin fallas"))
    return 1 if fallas else 0


def _r(nombre: str, estado: str, dice: str, arreglo: str = "") -> dict:
    return {"nombre": nombre, "estado": estado, "dice": dice, "arreglo": arreglo}


def _abiertos(ctx) -> frozenset[str] | None:
    """Los nombres de hilo que el multiplexor muestra ahora, o None si no se le pudo preguntar.

    `None` no es «ninguno»: es «no se sabe». Con la sesión caída, todo el estado
    quedaría acusado de colgar de tabs que no existen, y sería falso: existen, están
    esperando un `telar tejer`.
    """
    try:
        mux = obtener_mux(ctx.config)
        disponible = getattr(mux, "disponible", None)
        if disponible is not None and not disponible():
            return None
        if not mux.viva():
            return None
        return frozenset(h.nombre for h in mux.hilos())
    except ErrorDeMux:
        return None


def _sin_ventana(ctx, llaves, abiertos: frozenset[str] | None) -> list[str]:
    """De esas llaves del estado, las que no son ningún tab ni están archivadas.

    Archivar es una decisión y no tener ventana es su consecuencia normal; lo que
    queda después de descontarlas es lo que de verdad quedó huérfano.
    """
    if abiertos is None:
        return []
    est = mod_estado.abrir(ctx.config)
    try:
        archivados = est.archivados()
    except mod_estado.ErrorDeEstado:
        archivados = set()
    return sorted(set(llaves) - abiertos - archivados)


def _configuracion(ctx) -> list[dict]:
    cfg = ctx.config
    if cfg.origen:
        return [_r("config", OK, f"{cfg.origen}")]
    return [
        _r(
            "config",
            AVISO,
            f"sin archivo; todo por defecto (se buscaría en {ruta_config()})",
            "telar init",
        )
    ]


def _raiz(ctx) -> list[dict]:
    raiz = Path(ctx.config.raiz)
    if not raiz.exists():
        return [_r("raíz", FALLA, f"{raiz} no existe", "corrige `raiz` en la configuración")]
    if not raiz.is_dir():
        return [_r("raíz", FALLA, f"{raiz} no es una carpeta", "corrige `raiz`")]
    return [_r("raíz", OK, str(raiz))]


def _multiplexor(ctx) -> list[dict]:
    nombre = ctx.config.multiplexor
    try:
        mux = obtener_mux(ctx.config)
    except ErrorDeMux as e:
        return [
            _r("multiplexor", FALLA, str(e), "usa otro en `multiplexor`, o escribe su soporte"),
            _r("sesión", FALLA, "no se pudo preguntar", ""),
        ]

    salida = []
    disponible = getattr(mux, "disponible", None)
    if disponible is not None and not disponible():
        salida.append(
            _r("multiplexor", FALLA, f"no encontré «{nombre}» en el PATH", f"instala {nombre}")
        )
        salida.append(_r("sesión", FALLA, "sin programa no hay sesión", ""))
        return salida
    salida.append(_r("multiplexor", OK, nombre))

    try:
        viva = mux.viva()
    except ErrorDeMux as e:
        return salida + [_r("sesión", FALLA, str(e), "")]
    if not viva:
        return salida + [
            _r("sesión", AVISO, f"«{ctx.config.sesion}» no está viva", "telar tejer")
        ]
    try:
        cuantos = len(mux.hilos())
    except ErrorDeMux as e:
        return salida + [_r("sesión", FALLA, f"viva, pero no pude listarla: {e}", "")]
    return salida + [_r("sesión", OK, f"«{ctx.config.sesion}» viva, {cuantos} hilos")]


def _perfil(ctx) -> list[dict]:
    perfil = ctx.perfil
    raiz = ctx.config.raiz
    if perfil.minimo:
        return [
            _r(
                "perfil",
                AVISO,
                f"no hay {NOMBRE_ARCHIVO} en {raiz}: rige la convención mínima",
                "telar init --perfil, o escríbelo a mano (docs/perfil.md)",
            )
        ]

    unidades = lectura.indice(perfil, raiz)
    salida = [_r("perfil", OK, f"«{perfil.nombre}», {len(unidades)} unidades")]
    if not unidades:
        salida[0] = _r(
            "perfil",
            FALLA,
            f"«{perfil.nombre}» no alcanza ningún documento bajo {raiz}",
            "revisa `ruta` y `documento` de cada arquetipo (telar perfil --documentos)",
        )
        return salida

    faltantes: list[str] = []
    for relativa, (arquetipo, documento) in unidades.items():
        ficha = lectura.leer(documento, arquetipo)
        if ficha.nota.startswith("falta"):
            faltantes.append(f"{relativa} ({ficha.nota.removeprefix('falta la sección requerida: ')})")
    if faltantes:
        muestra = ", ".join(faltantes[:3]) + (" …" if len(faltantes) > 3 else "")
        salida.append(
            _r(
                "documentos",
                AVISO,
                f"{len(faltantes)} sin una sección requerida: {muestra}",
                "escribe la sección, o quítale `requerida: true` en el perfil",
            )
        )
    else:
        salida.append(_r("documentos", OK, "todos traen sus secciones requeridas"))
    return salida


def _estado(ctx) -> list[dict]:
    est = mod_estado.abrir(ctx.config)
    salida = []
    try:
        dentro = est.carpeta.resolve().is_relative_to(Path(ctx.config.raiz).resolve())
    except OSError:  # pragma: no cover
        dentro = False
    if dentro:
        salida.append(
            _r(
                "estado",
                FALLA,
                f"{est.carpeta} está dentro de la raíz",
                "sácalo del repositorio: es caché, y el repositorio no se ensucia con caché",
            )
        )
        return salida
    try:
        est.preparar()
        prueba = est.carpeta / ".doctor"
        prueba.write_text("", encoding="utf-8")
        prueba.unlink()
    except (OSError, mod_estado.ErrorDeEstado) as e:
        return [_r("estado", FALLA, f"no puedo escribir en {est.carpeta}: {e}", "revisa permisos")]
    return [_r("estado", OK, str(est.carpeta))]


def _vinculos(ctx, abiertos: frozenset[str] | None = None) -> list[dict]:
    est = mod_estado.abrir(ctx.config)
    try:
        vinculos = est.vinculos()
    except mod_estado.ErrorDeEstado as e:
        return [_r("vínculos", FALLA, str(e), "borra el archivo: es derivado")]
    if not vinculos:
        return [
            _r("vínculos", AVISO, "ningún hilo vinculado todavía", "telar vincular <carpeta>")
        ]
    unidades = lectura.indice(ctx.perfil, ctx.config.raiz)
    rotos = [h for h, r in vinculos.items() if not (Path(ctx.config.raiz) / r).exists()]
    ajenos = [h for h, r in vinculos.items() if r not in unidades and h not in rotos]
    huerfanos = _sin_ventana(ctx, vinculos, abiertos)
    # el conteo dice cuántos vínculos tienen tab: un vínculo colgado de un nombre que
    # ya no existe no es un hilo vinculado, y contarlo como tal esconde justo la falla
    con_tab = len(vinculos) - len(huerfanos)

    if rotos:
        salida = [
            _r(
                "vínculos",
                FALLA,
                f"{len(rotos)} apuntan a carpetas que no existen: {', '.join(rotos[:4])}",
                "telar hilo vincular <carpeta> --hilo <hilo>, o telar hilo olvidar",
            )
        ]
    elif ajenos:
        salida = [
            _r(
                "vínculos",
                AVISO,
                f"{len(ajenos)} apuntan a carpetas que el perfil no declara: {', '.join(ajenos[:4])}",
                "no tendrán ficha; agrégalas a un arquetipo o vincúlalos a otra carpeta",
            )
        ]
    elif huerfanos:
        salida = [_r("vínculos", OK, f"{con_tab} con tab abierto, de {len(vinculos)} vinculados")]
    else:
        salida = [_r("vínculos", OK, f"{len(vinculos)} hilos vinculados")]
    return salida + _huerfanos(huerfanos, "vínculo", "vínculos")


def _huerfanos(nombres: list[str], singular: str, plural: str) -> list[dict]:
    """El aviso de lo que quedó colgado de un nombre que ya no es ningún tab.

    Pasa sin que nadie haga nada raro: renombrar un tab desde el multiplexor
    (`prefix + ,`) es la forma natural de renombrar una ventana, y el estado se
    guarda por nombre. También pasa, y es inocuo, cuando se anota un hilo antes de
    abrirlo.
    """
    if not nombres:
        return []
    que = singular if len(nombres) == 1 else plural
    return [
        _r(
            "sin ventana",
            AVISO,
            f"{len(nombres)} {que}: {', '.join(nombres[:4])}",
            "si renombraste el tab, `telar hilo adoptar <nombre>` desde él recupera su"
            " estado; si ya no sirve, `telar hilo olvidar --hilo <nombre>`",
        )
    ]


def _ficha(ctx) -> list[dict]:
    """Quién arma la ficha: `[ficha]`, que es tabla aparte de `[proveedores.*]`."""
    from telar.proveedores import estado as prov_estado

    cfg = ctx.config.ficha
    if cfg.nombre not in prov_estado.REGISTRO:
        conocidos = ", ".join(sorted(prov_estado.REGISTRO))
        return [
            _r("ficha", FALLA, f"proveedor desconocido: {cfg.nombre}",
               f"en [ficha], `proveedor` tiene que ser uno de: {conocidos}")
        ]
    try:
        prov_estado.obtener(cfg)
    except Exception as e:  # noqa: BLE001 - el proveedor se queja como quiera
        return [_r("ficha", FALLA, f"{cfg.nombre}: {e}", "revisa la sección [ficha] de la configuración")]
    return [_r("ficha", OK, f"la arma el proveedor {cfg.nombre}")]


def _proveedores(ctx) -> list[dict]:
    _comun.asegurar_proveedores(ctx.config)
    declarados = list(ctx.config.proveedores.values())
    if not declarados:
        return [
            _r(
                "proveedores",
                AVISO,
                "ninguno: telar no sale de la máquina",
                "declara uno en [proveedores.<nombre>] si quieres agenda o tareas externas",
            )
        ]
    sin_registrar = [p.nombre for p in declarados if p.nombre not in REGISTRO]
    if sin_registrar:
        return [
            _r(
                "proveedores",
                FALLA,
                f"declarados y no registrados: {', '.join(sin_registrar)}",
                "instala el paquete que los registra, o quítalos de la configuración",
            )
        ]
    activos = [p.nombre for p in declarados if p.activo]
    return [_r("proveedores", OK, f"{len(activos)} activos: {', '.join(activos) or '—'}")]


def _ganchos(ctx, abiertos: frozenset[str] | None = None) -> list[dict]:
    """Los ganchos son lo que telar NO puede hacer solo: que alguien le cuente.

    Dos, y los dos los llama quien corre los hilos: `telar tiempo marcar` cuando
    cambia el foco, y `telar atencion set` desde el agente. Se comprueban por sus
    huellas, porque no hay registro de instalación que valga: si hay marcas de hoy,
    el gancho del foco está puesto.
    """
    est = mod_estado.abrir(ctx.config)
    salida = []

    try:
        lineas = est.ruta(mod_estado.FOCO).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lineas = []
    marcas = mod_estado.marcas_desde(lineas)
    arreglo_foco = (
        "haz que el multiplexor llame a `telar tiempo marcar` al cambiar de tab,"
        f" con ${_comun.VARIABLE_HILO} exportado"
    )
    if not marcas:
        salida.append(_r("gancho foco", AVISO, "nunca se anotó un cambio de foco", arreglo_foco))
    else:
        ultima = marcas[-1].cuando
        dias = (dt.datetime.now() - ultima).days
        if dias >= 2:
            salida.append(
                _r("gancho foco", AVISO, f"la última marca es de hace {dias} días", arreglo_foco)
            )
        else:
            salida.append(_r("gancho foco", OK, f"última marca: {ultima:%Y-%m-%d %H:%M}"))

    atenciones = est.atenciones()
    colgadas = _sin_ventana(ctx, atenciones, abiertos)
    # una atención anotada en un nombre sin tab no la dijo ningún agente vivo: es la
    # que se quedó atrás cuando el tab se renombró, y el tab de verdad perdió su símbolo
    vivas = [h for h in atenciones if h not in colgadas]
    if vivas:
        salida.append(_r("gancho agente", OK, f"{len(vivas)} hilos con atención anotada"))
    else:
        salida.append(
            _r(
                "gancho agente",
                AVISO,
                "ningún agente ha dicho en qué anda",
                "que el agente llame a `telar atencion set trabajando|espera|termino`",
            )
        )
    salida += _huerfanos(colgadas, "atención", "atenciones")

    if os.environ.get(_comun.VARIABLE_HILO):
        salida.append(_r("hilo actual", OK, f"${_comun.VARIABLE_HILO}={os.environ[_comun.VARIABLE_HILO]}"))
    else:
        salida.append(
            _r(
                "hilo actual",
                AVISO,
                f"sin ${_comun.VARIABLE_HILO}: telar tiene que adivinarlo por el foco",
                "expórtala al abrir cada hilo; el foco lo mueve la persona y miente",
            )
        )
    return salida
