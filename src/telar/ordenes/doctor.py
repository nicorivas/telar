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
import shlex
import shutil
from pathlib import Path

from telar import estado as mod_estado
from telar import lectura
from telar.config import ruta_config
from telar.mux import ErrorDeMux
from telar.mux import obtener as obtener_mux
from telar.ordenes import _comun
from telar.perfil import NOMBRE_ARCHIVO, carpeta_de_repo
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
    revisiones += _repos(ctx)
    revisiones += _modulos(ctx)
    revisiones += _estado(ctx)
    revisiones += _vinculos(ctx, abiertos)
    revisiones += _gemelos(ctx)
    revisiones += _version_mux(ctx)
    revisiones += _ganchos_vivos(ctx)
    revisiones += _ficha(ctx)
    revisiones += _proveedores(ctx)
    revisiones += _tareas_del_tipo(ctx)
    revisiones += _ganchos(ctx, abiertos)
    revisiones += _remotos(ctx)
    revisiones += _sesiones_propias(ctx)

    fallas = [r for r in revisiones if r["estado"] == FALLA]

    if o.json:
        _comun.escribir_json({"ok": not fallas, "revisiones": revisiones})
        return 1 if fallas else 0

    ancho = shutil.get_terminal_size((100, 24)).columns
    for r in revisiones:
        print(f"  {MARCA[r['estado']]} {r['nombre']:<14} {_comun.recortar(r['dice'], ancho - 20)}")
        if r["arreglo"] and r["estado"] != OK:
            print(_comun.tenue(f"      → {r['arreglo']}"))
    print()
    if fallas:
        print(_comun.fuerte(_comun.plural(len(fallas), "falla")))
    else:
        print(_comun.fuerte("sin fallas"))
    return 1 if fallas else 0


def _remotos(ctx) -> list[dict]:
    """Por cada máquina de `[remotos]`: que responda, y que tenga lo que un hilo necesita allá."""
    from telar import remoto as mod_remoto

    salida = []
    for r in ctx.config.remotos:
        for bien, dice in mod_remoto.revisar(r):
            salida.append(_r(f"remoto {r.nombre}", OK if bien else FALLA, dice))
    return salida


def _sesiones_propias(ctx) -> list[dict]:
    """Las sesiones tmux propias por hilo (`telar-…`, de las versiones de antes) que siguen vivas aquí, y
    los hilos remotos anotados con una dirección de ese tipo. telar ya no abre ninguna: todo hilo nuevo
    es una ventana de la sesión del telar. Las de antes se siguen leyendo mientras existan, y lo que las
    lee se podrá quitar cuando no quede ninguna (docs/propuestas/un-dueno-por-hilo.md). Sin tmux instalado
    no hay ninguna; si está y no se le pudo preguntar, no se sabe, y se dice: esta revisión es la que
    dice cuándo es seguro quitarlas."""
    from telar import movil

    try:
        vivas = sorted(movil.propios())
    except FileNotFoundError:
        vivas = []  # sin tmux en esta máquina: ninguna sesión, ni de antes
    except (OSError, RuntimeError) as e:
        return [_r("sesiones", AVISO, f"no pude revisar las sesiones de tmux: {e}",
                   "con tmux respondiendo, `telar doctor` de nuevo")]
    try:
        viejas = sorted(h for h, r in mod_estado.abrir(ctx.config).remotos().items()
                        if r.get("sesion") and not r["sesion"].startswith("@"))
    except mod_estado.ErrorDeEstado:
        viejas = []
    if not vivas and not viejas:
        return [_r("sesiones", OK, "ninguna sesión propia por hilo: todos son ventanas de la sesión del telar")]
    partes = []
    if vivas:
        partes.append(f"{_comun.plural(len(vivas), 'sesión propia', 'sesiones propias')} de antes, viva"
                      f"{'s' if len(vivas) > 1 else ''}: {', '.join(vivas[:5])}{' …' if len(vivas) > 5 else ''}")
    if viejas:
        partes.append(f"{_comun.plural(len(viejas), 'hilo remoto', 'hilos remotos')} con dirección de antes: "
                      f"{', '.join(viejas[:5])}{' …' if len(viejas) > 5 else ''}")
    return [_r("sesiones", AVISO, "; ".join(partes),
               "telar las sigue leyendo; para pasar uno a ventana, `telar hilo archivar --cerrar` y "
               "`telar hilo retomar`. Cuando no quede ninguna en ninguna máquina, telar puede dejar de leerlas")]


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
        cuantas = len(lectura.indice(perfil, raiz))
        if cuantas:
            return [
                _r(
                    "perfil",
                    OK,
                    f"sin {NOMBRE_ARCHIVO}: rige el de casa, y alcanza {_comun.plural(cuantas, 'unidad', 'unidades')}",
                    "telar init --perfil escribe uno a la medida de este repositorio",
                )
            ]
        return [
            _r(
                "perfil",
                AVISO,
                f"sin {NOMBRE_ARCHIVO}, y el de casa no alcanza ningún README bajo {raiz}",
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


def _repos(ctx) -> list[dict]:
    """Los repositorios de `[repos]`: que estén dentro de la raíz, y que sus perfiles no se pisen.

    Un repo fuera de la raíz no suma su perfil (telar.perfil.cargar_todos todavía no los junta): sus
    carpetas no son unidades, y sus hilos quedan sin ficha. Y si dos repos reconocen la misma carpeta,
    la describe uno solo, el más hondo: el otro la nombra en vano, y quizá con otro arquetipo. Las dos
    cosas son avisos: telar funciona igual, con lo que dice el perfil que gana.
    """
    repos = tuple(getattr(ctx.config, "repos", ()) or ())
    if not repos:
        return []
    raiz = Path(ctx.config.raiz).expanduser()
    salida = []
    fuera = []
    for repo in repos:
        if not carpeta_de_repo(ctx.config, repo).is_dir():
            salida.append(_r("repos", AVISO, f"«{repo.nombre}» ({repo.ruta}) no existe: no aporta nada",
                             "corrige su `ruta` en [repos], o sácalo"))
            continue
        if not Path(repo.ruta).expanduser().is_absolute():
            # telar la lee desde la raíz, pero un módulo la recibe tal cual en TELAR_REPOS y no sabe desde dónde
            salida.append(_r("repos", AVISO, f"«{repo.nombre}» tiene la ruta relativa «{repo.ruta}»: telar la lee "
                             f"desde la raíz, pero los módulos la reciben tal cual",
                             f"escríbela absoluta: ruta = \"{carpeta_de_repo(ctx.config, repo)}\""))
        try:
            carpeta_de_repo(ctx.config, repo).relative_to(raiz.resolve())
        except (ValueError, OSError):
            fuera.append(repo)
    for repo in fuera:
        salida.append(_r("repos", AVISO, f"«{repo.nombre}» ({repo.ruta}) queda fuera de la raíz {raiz}: su perfil no se suma",
                         "múdalo dentro de la raíz, o pon en `raiz` una carpeta que lo contenga"))
    salida += _pisadas(ctx, repos, raiz)
    if not salida:
        salida.append(_r("repos", OK, f"{_comun.plural(len(repos), 'repo')} dentro de la raíz, sin carpetas que se pisen"))
    return salida


def pisadas(perfil, raiz: Path, nombre_raiz: str = "") -> dict[str, list[str]]:
    """Las carpetas que reconocen arquetipos de dos o más repos: carpeta → repos, el que gana primero.

    Gana el primero que la reconoce en el perfil junto (telar.lectura.indice), y cargar_todos pone primero
    los más hondos: este orden es el de verdad, no uno calculado aparte. Los arquetipos de la raíz no son
    de ningún repo (`repo` vacío) y cuentan solo si la raíz está declarada en `[repos]` (`nombre_raiz`):
    que el perfil de la raíz también nombre las carpetas de un repo de adentro es lo previsto. Y si la
    raíz no tiene perfil, los suyos son los del perfil mínimo, que no escribió nadie: tampoco cuentan
    (cargar_todos descarta por lo mismo el mínimo de un repo).
    """
    if perfil.minimo:
        nombre_raiz = ""
    vistos: dict[str, list[str]] = {}
    for arquetipo in perfil.arquetipos:
        repo = arquetipo.repo or nombre_raiz
        if not repo:
            continue
        for documento in arquetipo.documentos(raiz):
            unidad = arquetipo.carpeta_de(documento) if arquetipo.por_carpeta else documento
            try:
                clave = unidad.relative_to(raiz).as_posix()
            except ValueError:  # pragma: no cover - el glob no sale de la raíz
                continue
            de_quien = vistos.setdefault(clave, [])
            if repo not in de_quien:
                de_quien.append(repo)
    return {clave: repos for clave, repos in sorted(vistos.items()) if len(repos) > 1}


def _pisadas(ctx, repos, raiz: Path) -> list[dict]:
    """El aviso de los perfiles que se pisan, uno por par de repos (el que gana, el que pierde)."""
    try:
        base = raiz.resolve()
        nombre_raiz = next((r.nombre for r in repos if carpeta_de_repo(ctx.config, r) == base), "")
        hondura = {r.nombre: len(carpeta_de_repo(ctx.config, r).parts) for r in repos}
    except OSError:  # pragma: no cover
        nombre_raiz, hondura = "", {}
    choques: dict[tuple[str, ...], list[str]] = {}
    for carpeta, de_quien in pisadas(ctx.perfil, raiz, nombre_raiz).items():
        choques.setdefault(tuple(de_quien), []).append(carpeta)
    salida = []
    for (gana, *pierden), carpetas in choques.items():
        muestra = ", ".join(carpetas[:3]) + (" …" if len(carpetas) > 3 else "")
        otros = ", ".join(f"«{x}»" for x in pierden)
        # a la misma hondura (dos repos en la misma carpeta) cargar_todos deja el orden de [repos]
        por_que = ("el primero de [repos], a la misma hondura" if any(hondura.get(x) == hondura.get(gana) for x in pierden)
                   else "el más hondo")
        salida.append(_r("perfiles", AVISO,
                         f"«{gana}» y {otros} reconocen {_comun.plural(len(carpetas), 'carpeta')} ({muestra}): gana «{gana}», {por_que}",
                         f"quita esas carpetas del perfil de {otros}, si no las quiere describir"))
    return salida


def _modulos(ctx) -> list[dict]:
    """Los módulos declarados (`[modulos]` y los de `telar modulos instalar`): que se puedan leer.

    Uno que no se lee no deja arrancar a las demás órdenes (la configuración es un error), así que es una
    falla. doctor carga igual, sin él (telar.cli.TOLERAN_MODULOS_ROTOS), para poder decirlo aquí.
    """
    from telar import modulos as mod_modulos

    rotos = tuple(getattr(ctx.config, "modulos_rotos", ()) or ())
    leidos = tuple(getattr(ctx.config, "modulos", ()) or ())
    salida = []
    for nombre, por_que in rotos:
        if nombre == mod_modulos.INSTALADOS:
            salida.append(_r("módulos", FALLA, f"no se puede leer {por_que}",
                             "arregla ese archivo (lo escribe telar modulos): hasta entonces las demás órdenes no arrancan"))
            continue
        por_que = por_que.removeprefix(f"modulos.{nombre}: ").removeprefix(f"{nombre}: ")
        salida.append(_r("módulos", FALLA, f"«{nombre}» no se puede leer: {por_que}",
                         "arregla su carpeta o su modulo.toml, o sácalo de [modulos] (o de modulos.toml, si lo instaló"
                         " telar modulos): hasta entonces las demás órdenes no arrancan"))
    if leidos and not rotos:
        salida.append(_r("módulos", OK, ", ".join(m.nombre for m in leidos)))
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


def gemelos(nombres: list[str]) -> list[str]:
    """Los nombres que llevan dos o más hilos vivos a la vez."""
    from collections import Counter

    return sorted(n for n, k in Counter(nombres).items() if k > 1)


def _gemelos(ctx) -> list[dict]:
    """Dos hilos vivos con el mismo nombre comparten todo lo que telar guarda por nombre:
    conversación, vínculo, prioridad. Lo de uno pisa lo del otro."""
    try:
        tel = _comun.tejer(ctx, con_ficha=False)
    except Exception:  # noqa: BLE001 - sin multiplexor no hay gemelos que buscar
        return []
    repetidos = gemelos([h.nombre for h in tel.hilos if tel.vivo(h)])
    if not repetidos:
        return [_r("nombres", OK, "ningún par de hilos vivos con el mismo nombre")]
    return [_r("nombres", AVISO, f"hilos vivos con el mismo nombre: {', '.join(repetidos)}",
               "renombra uno (telar hilo renombrar): el estado se guarda por nombre y se pisan")]


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
        salida = [_r("vínculos", OK, f"{_comun.plural(len(vinculos), 'hilo')} vinculados")]
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


def _partes(v: str) -> tuple[int, ...]:
    """«3.7c» → (3, 7). Lo que no sea número se ignora: las letras de tmux no ordenan."""
    import re as _re

    return tuple(int(p) for p in _re.findall(r"\d+", v)[:3])


def _version_mux(ctx) -> list[dict]:
    """La versión instalada contra la que el backend declara necesitar.

    telar habla por acciones que no existían en cualquier versión (`#{pane_current_command}`,
    `-t` con `=nombre:`). Cuando falta una, el error que sale es
    del programa y no dice que el problema es la edad.
    """
    try:
        mux = obtener_mux(ctx.config)
    except ErrorDeMux:
        return []
    minima = getattr(mux, "version_minima", "")
    try:
        instalada = mux.version()
    except ErrorDeMux:
        instalada = ""
    nombre = ctx.config.multiplexor
    if not instalada:
        return [_r("versión", AVISO, f"no pude preguntarle su versión a {nombre}")]
    if minima and _partes(instalada) < _partes(minima):
        return [
            _r("versión", AVISO, f"{nombre} {instalada}; telar se probó con {minima} o más",
               f"actualiza {nombre}: telar usa acciones que las versiones viejas no traen")
        ]
    return [_r("versión", OK, f"{nombre} {instalada}")]


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
    from telar.proveedores import clase

    sin_registrar = [p.nombre for p in declarados if clase(p) not in REGISTRO]
    if sin_registrar:
        return [
            _r(
                "proveedores",
                FALLA,
                f"declarados y no registrados: {', '.join(sin_registrar)}",
                "instala el paquete que los registra, o quítalos de la configuración",
            )
        ]
    activos = [p for p in declarados if p.activo]
    if not activos:
        return [*_atajos(ctx), _r("proveedores", OK, "ninguno activo")]
    # la tecla de una pestaña de proveedor no puede ser una del dashboard ni la de un atajo
    from telar.config import TECLAS_RESERVADAS

    de_atajos = {a.tecla for a in ctx.config.atajos}
    for p in activos:
        tecla = str(p.opciones.get("tecla") or "")
        if tecla and (len(tecla) != 1 or tecla in TECLAS_RESERVADAS or tecla in de_atajos):
            return [_r("proveedores", FALLA, f"{p.nombre}: la tecla «{tecla}» ya la usa el dashboard o un atajo",
                       "elige otra en [proveedores.%s] tecla" % p.nombre)]
    # el alcance es lo que cada proveedor promete tocar: se lee aquí, antes de confiar
    lineas = []
    for pr in activos:
        try:
            alcance = REGISTRO[pr.nombre](pr).alcance  # type: ignore[operator]
        except Exception:  # noqa: BLE001 - un proveedor roto se reporta, no revienta doctor
            alcance = "no supo decir qué toca"
        lineas.append(_r("proveedor", OK, f"{pr.nombre}: {alcance}"))
    return [*_atajos(ctx), *lineas]


def _tareas_del_tipo(ctx) -> list[dict]:
    """Que un proveedor con `tipo = "tipo"` lea la carpeta de `[tipos.tarea]`: sus filas de `telar pendientes`
    llevan `tarea:<id>`, y `telar objeto` abre esa dirección en la carpeta del tipo. Si son otras, la dirección
    abre otra tarea con el mismo id, o ninguna. Es un aviso: los pendientes se ven igual."""
    t = next((x for x in getattr(ctx.config, "tipos", ()) if x.clave == "tarea"), None)
    salida = []
    for p in ctx.config.proveedores_activos():
        if p.opciones.get("tipo") != "tipo" or not isinstance(p.opciones.get("carpeta"), str):
            continue
        if t is None:
            salida.append(_r("tareas", AVISO, f"{p.nombre} lee tareas del tipo y no hay [tipos.tarea]: "
                             "sus direcciones (tarea:<id>) no se abren con telar objeto",
                             "declara [tipos.tarea] carpeta, la misma del proveedor"))
            continue
        if not t.carpeta:
            continue  # viven en otra máquina (`en`): allá se abren, y esta no puede comparar carpetas
        suya, del_tipo = (Path(c).expanduser().resolve() for c in (p.opciones["carpeta"], t.carpeta))
        if suya != del_tipo:
            salida.append(_r("tareas", AVISO, f"{p.nombre} lee {suya} y [tipos.tarea] es {del_tipo}: "
                             "telar objeto tarea:<id> abriría otra tarea, o ninguna",
                             f"pon en [proveedores.{p.nombre}] carpeta la misma de [tipos.tarea]"))
    return salida


def _atajos(ctx) -> list[dict]:
    """Un atajo con una tecla del dashboard (o de una pestaña de bloque o proveedor) no se rompe: la pestaña
    le gana y el atajo queda con un clic. Pero probablemente no es lo que se quería: se avisa."""
    from telar.config import TECLAS_RESERVADAS

    ocupadas = set(TECLAS_RESERVADAS) | {str(p.opciones.get("tecla") or "") for p in ctx.config.proveedores.values()}
    ocupadas |= {b.tecla for b in getattr(ctx.config, "bloques", ()) if getattr(b, "tecla", "")}
    choques = sorted(a.tecla for a in ctx.config.atajos if a.tecla in ocupadas)
    if not choques:
        return []
    return [_r("atajos", AVISO, f"la tecla de {', '.join(f'«{t}»' for t in choques)} es de una pestaña: el atajo va con un clic",
               "cámbiale la tecla en [atajos], si lo quieres con tecla")]


def _ganchos_vivos(ctx) -> list[dict]:
    """El comando anotado en los ganchos del agente, ¿todavía existe?

    `instalar` escribe la ruta absoluta de telar, que es lo correcto —el PATH de un
    gancho no es el de tu shell—, pero un venv rehecho o un `pipx reinstall` la dejan
    apuntando a un ejecutable muerto. El agente se traga el error en silencio y la
    atención simplemente deja de moverse; sin esto, doctor manda a instalar lo que ya
    estaba instalado.
    """
    from telar.agente import INCLUIDOS, obtener as obtener_agente

    salida: list[dict] = []
    for nombre in INCLUIDOS:
        try:
            agente = obtener_agente(nombre, ctx.config)
            instalados = agente.comandos_instalados()
        except Exception:  # noqa: BLE001 - un agente ajeno no tiene por qué ser prolijo
            continue
        for comando in sorted({c for c in instalados if c}):
            programa = shlex.split(comando)[0] if comando else ""
            if programa and not (Path(programa).exists() or shutil.which(programa)):
                salida.append(
                    _r("ganchos", FALLA, f"{nombre}: apuntan a «{programa}», que ya no está",
                       "vuelve a instalarlos con `telar agente instalar` desde el telar que uses hoy")
                )
            elif programa:
                salida.append(_r("ganchos", OK, f"{nombre}: llaman a «{programa}»"))
    return salida


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
