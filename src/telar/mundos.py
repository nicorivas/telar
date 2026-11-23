"""A qué parte de la vida pertenece cada cosa: los mundos (`[mundos]`, docs/configuracion.md).

    [mundos.trabajo]
    areas = ["equipo", "cliente"]        # el campo `area` de una tarea
    rutas = ["empresa/", "clientes/"]    # prefijos de la carpeta de un documento, un proyecto o un hilo

    from telar import mundos
    mundos.de_tarea(config, area="cliente", proyecto="")       # "trabajo"
    mundos.de_ruta(config, "casa/jardin")                      # el de `casa/`, o ""
    c = mundos.Clasificador(ctx)                               # lo que necesita mirar los hilos
    c.de_direccion("hilo:Faro")

Un mundo se deriva de lo declarado, nunca del título:

- una tarea, de su `area`; si su área no es de ningún mundo, de la carpeta de su `proyecto`;
- una casilla de un documento o un proyecto, de la carpeta de su documento;
- lo que está en la carpeta de un agente residente que declara su mundo en su agente.toml, de ese mundo, antes que de
  cualquier ruta;
- un agente residente, del que declara su agente.toml (`mundo = "personal"`), si esta máquina declara ese mundo; si
  no, de las etiquetas de su hilo o de su carpeta;
- un hilo (y su permiso o su pregunta en vivo), del mundo que declara su agente, si es de uno que lo declara; si no,
  de sus etiquetas, si un mundo declara una (`etiquetas`); si no, de la
  carpeta de su proyecto; si no calza (un worktree fuera de la raíz, un agente sin proyecto), de la carpeta de su agente
  residente y, si tampoco, del hilo del que cuelga;
- un mensaje retenido, del hilo al que iba;
- lo demás, de su enlace principal (`proyecto:`, `hilo:`, `archivo:`), y si nada calza, ninguno: "" (sin
  clasificar).

Una ruta calza con un prefijo si empieza con él: `empresa/` es esa carpeta y lo que tiene dentro; sin la barra
final también calza con lo que empieza igual (`clientes/acme-` con `clientes/acme-faro/`). Se comparan absolutas:
un prefijo relativo es desde la raíz, y uno con `~` o `/` es una carpeta de esta máquina (los worktrees de
`~/worktrees/`). Si calzan varias, gana la más larga, de cualquier mundo.

Sin `[mundos]` nada dice mundo: todo da "".

Cada mundo tiene además su color (`colores`: el que declara, o el que le toca por orden), su horario (telar.horario),
que la página usa para ponerse sola en el mundo que rige, su tema (los colores de la página mientras rige; vacío, los
del modo) y sus modos (los de la banda de modos que tiene; vacío, todos); `[mundos] fuera` es el de fuera de todo horario. `para_la_pagina` los entrega como los dice `telar config
--json`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from telar.config import SIN_CLASIFICAR
from telar.servicios import ErrorDeServicio

__all__ = ["SIN_CLASIFICAR", "declarados", "de_area", "de_ruta", "agente_de_ruta", "de_tarea", "de_fila", "de_etiquetas",
           "de_agente",
           "declarado_de_agente",
           "pedidos", "calza", "colores", "para_la_pagina", "Clasificador", "ruta_que_calza", "por_que_agente",
           "para_la_configuracion", "ajustar", "crear", "borrar", "poner_fuera", "CAMPOS"]

#: las tintas que toman, por orden, los mundos que no declaran la suya: no son las de un estado ni las de una acción
COLORES = ("cian", "magenta", "verde", "azul", "violeta", "amarillo", "rojo")


def declarados(config) -> tuple[str, ...]:
    """Los nombres de los mundos, en el orden de la configuración; () si no hay `[mundos]`."""
    return tuple(m.nombre for m in getattr(config, "mundos", ()) or ())


def de_area(config, area: str) -> str:
    """El mundo de un `area` de tarea; "" si no es de ninguno."""
    area = (area or "").strip()
    if not area:
        return ""
    return next((m.nombre for m in getattr(config, "mundos", ()) or () if area in m.areas), "")


def _absoluta(config, ruta: str) -> str:
    """Una ruta como texto absoluto y normalizado (sin `..` ni `/` repetidas): relativa, desde la raíz."""
    r = os.path.expanduser(str(ruta).strip())
    if not os.path.isabs(r):
        r = os.path.join(str(getattr(config, "raiz", "") or "."), r)
    return os.path.normpath(r)


def _prefijos(config) -> list[tuple[str, str, str]]:
    """(prefijo absoluto, mundo, la ruta como se declaró) de todas las rutas declaradas, el más largo primero. Una que
    termina en `/` la conserva: es la carpeta, no lo que empieza igual."""
    salida = []
    for m in getattr(config, "mundos", ()) or ():
        for r in m.rutas:
            p = _absoluta(config, r)
            salida.append((p.rstrip("/") + "/" if r.endswith("/") else p, m.nombre, r))
    return sorted(salida, key=lambda x: -len(x[0]))


#: lo leído del agente.toml de cada agente (su ruta → (su mtime, el mundo que declara)): `de_ruta` corre por cada tarea
#: y cada documento, y releerlos cada vez sería un TOML por agente por cosa; un stat basta para saber si cambió
_DECLARADOS: dict[str, tuple[float, str]] = {}


def _carpetas_de_agentes(config) -> list[tuple[str, str, str]]:
    """(carpeta absoluta con «/», mundo, cómo se dice) de los agentes residentes cuyo agente.toml declara un mundo de
    esta configuración (`mundo = "personal"`): todo lo de su carpeta (su memoria, sus registros, su hilo) es de ese
    mundo. [] sin `[agentes] carpeta` o sin `[mundos]`."""
    from telar import agentes

    base = agentes.base(config) if getattr(config, "mundos", ()) else None
    if base is None:
        return []
    nombres = set(declarados(config))
    salida = []
    try:
        carpetas = [d for d in base.iterdir() if not d.name.startswith(("_", "."))]
    except OSError:
        return []
    for d in carpetas:
        archivo = d / agentes.DEFINICION
        try:
            mtime = archivo.stat().st_mtime
        except OSError:
            continue
        leido = _DECLARADOS.get(str(archivo))
        if leido is None or leido[0] != mtime:
            leido = (mtime, str(agentes.leer_definicion(d)[0].get("mundo", "")))
            _DECLARADOS[str(archivo)] = leido
        if leido[1] in nombres:
            salida.append((os.path.normpath(str(d)) + "/", leido[1], f"{_mostrar(config, d)} ({agentes.DEFINICION})"))
    return salida


def ruta_que_calza(config, ruta: str) -> tuple[str, str]:
    """(mundo, la ruta declarada que lo dice) de una carpeta o un documento: la más larga que calza; ("", "") si
    ninguna. Es lo que `de_ruta` deriva, con su porqué. Lo que está en la carpeta de un agente que declara su mundo
    (`_carpetas_de_agentes`) es de ese mundo, antes que de cualquier ruta: lo privado de un agente no se le escapa a una
    ruta más larga de otro mundo."""
    ruta = str(ruta or "").strip()
    if not ruta or not getattr(config, "mundos", ()):
        return "", ""
    cosa = _absoluta(config, ruta).rstrip("/") + "/"
    suya = next(((m, r) for p, m, r in _carpetas_de_agentes(config) if cosa.startswith(p)), None)
    if suya is not None:
        return suya
    return next(((m, r) for p, m, r in _prefijos(config) if cosa.startswith(p)), ("", ""))


def agente_de_ruta(config, ruta: str) -> str:
    """La clave del agente residente en cuya carpeta vive una carpeta o un documento, si su agente.toml declara su
    mundo (`_carpetas_de_agentes`); "" si no. Lo de un agente así es suyo, no solo de su mundo: la página no lo nombra
    fuera de ese mundo ni en el modo todo, donde lo demás de otro mundo va al final (docs/configuracion.md)."""
    ruta = str(ruta or "").strip()
    if not ruta or not getattr(config, "mundos", ()):
        return ""
    cosa = _absoluta(config, ruta).rstrip("/") + "/"
    return next((os.path.basename(p.rstrip("/")) for p, _, _ in _carpetas_de_agentes(config) if cosa.startswith(p)), "")


def de_ruta(config, ruta: str) -> str:
    """El mundo de una carpeta o un documento (relativa a la raíz, o absoluta); "" si ninguna ruta declarada calza.
    La raíz misma (`.`, "") no es de ningún mundo, salvo que se declare entera."""
    return ruta_que_calza(config, ruta)[0]


def de_etiquetas(config, etiquetas) -> str:
    """El mundo de un hilo por sus etiquetas: el del primer mundo que declara alguna de ellas; "" si ninguno."""
    suyas = {str(e).strip() for e in etiquetas or () if str(e).strip()}
    if not suyas:
        return ""
    return next((m.nombre for m in getattr(config, "mundos", ()) or () if suyas & set(m.etiquetas)), "")


#: los agentes de las fotos de las otras máquinas (telar.espejo), por la carpeta de fotos y la hora de cada una: se
#: leen de nuevo solo cuando llega una foto
_FOTOS: dict[str, tuple[tuple, list[tuple[str, dict]]]] = {}


def agentes_de_otras(config) -> list[tuple[str, dict]]:
    """(máquina, {clave, nombre, mundo}) de cada agente residente que traen las fotos de las otras máquinas, estén o
    no en línea (un agente sigue existiendo aunque su máquina duerma); `mundo`, el que declara su agente.toml allá. []
    si no hay fotos o no se pudieron leer."""
    from telar import espejo

    try:
        carpeta = espejo.carpeta(config)
        rutas = sorted(carpeta.glob("*.json"))
        firma = tuple((r.name, r.stat().st_mtime_ns) for r in rutas)
    except OSError:
        return []
    guardado = _FOTOS.get(str(carpeta))
    if guardado and guardado[0] == firma:
        return guardado[1]
    salida: list[tuple[str, dict]] = []
    try:
        for foto in espejo.leer_todos(config):
            for a in foto.get("agentes") or []:
                if isinstance(a, dict) and a.get("clave"):
                    salida.append((str(foto.get("nombre") or ""), a))
    except Exception:  # noqa: BLE001 - sin fotos legibles, ninguno
        salida = []
    _FOTOS[str(carpeta)] = (firma, salida)
    return salida


def declarado_de_agente(config, clave: str) -> str:
    """El mundo que un agente residente declara en su agente.toml (`mundo = "personal"`), si esta máquina declara un
    mundo con ese nombre; "" si no declara ninguno, si no es de aquí o no hay carpeta de agentes. Lo declarado es del
    agente, no de la máquina: viaja con su carpeta y vale igual en todas las que tengan ese mundo. Si aquí no lo
    declara (o su carpeta todavía no llega: una raíz atrasada), vale lo que declara en otra máquina, por su foto
    (`agentes_de_otras`): un agente privado no queda sin clasificar, a la vista en todos los mundos, por el atraso."""
    from telar import agentes

    clave = str(clave or "").strip()
    if not clave or not getattr(config, "mundos", ()) or "/" in clave or clave.startswith("."):
        return ""
    base = agentes.base(config)
    if base is not None:
        carpeta = os.path.normpath(str(base / clave)) + "/"
        aqui = next((m for p, m, _ in _carpetas_de_agentes(config) if p == carpeta), "")
        if aqui:
            return aqui
    nombres = set(declarados(config))
    return next((str(a.get("mundo")) for _, a in agentes_de_otras(config)
                 if a.get("clave") == clave and a.get("mundo") in nombres), "")


def de_agente(config, clave: str) -> str:
    """El mundo de un agente residente: el que declara su agente.toml (`declarado_de_agente`) y, si no, el de su
    carpeta (`[agentes] carpeta`/<clave>, desde la raíz de aquí, como la de un hilo de otra máquina); "" si no calza o
    no hay carpeta de agentes."""
    from telar import agentes

    clave = str(clave or "").strip()
    base = agentes.base(config) if clave and getattr(config, "mundos", ()) else None
    if base is None:
        return ""
    return declarado_de_agente(config, clave) or de_ruta(config, str(base / clave))


def colores(config) -> dict[str, str]:
    """El color de cada mundo: el que declara, o el primero de COLORES que no haya tomado otro (en su orden)."""
    mundos = getattr(config, "mundos", ()) or ()
    usados = {m.color for m in mundos if m.color}
    libres = [c for c in COLORES if c not in usados]
    salida = {}
    for m in mundos:
        salida[m.nombre] = m.color or (libres.pop(0) if libres else COLORES[0])
    return salida


def para_la_pagina(config) -> list[dict]:
    """Los mundos como los dice `telar config --json`: nombre, áreas, rutas, etiquetas, su color ya resuelto, su
    horario (cada tramo con su texto y lo que quiere decir: los días, de 0 domingo a 6 sábado, y los minutos), su tema
    ("" si no declara uno: el del modo), sus modos (las claves, en su orden: el primero es al que entra la página; [] si
    no los declara: todos) y su arte (la clave del dibujo de su tarjeta en la ventana de mundos; "" el que le toca)."""
    color = colores(config)
    return [{"nombre": m.nombre, "areas": list(m.areas), "rutas": list(m.rutas), "etiquetas": list(m.etiquetas),
             "color": color[m.nombre], "horario": [t.json() for t in m.horario], "tema": m.tema,
             "modos": list(m.modos), "arte": m.arte}
            for m in getattr(config, "mundos", ()) or ()]


# ── ⚙ mundos: verlos y cambiarlos desde la página (`GET`, `PUT`, `PATCH` y `DELETE /mundos`) ──

#: lo que dice un mundo, en el orden en que lo muestra ⚙ mundos
CAMPOS = ("horario", "color", "tema", "arte", "modos", "etiquetas", "areas", "rutas")


def por_que_agente(config, clave: str, etiquetas=()) -> dict:
    """El mundo de un agente residente y qué lo pone ahí, como se deriva el de su hilo: el que declara su agente.toml
    (`por` «agente.toml», `valor` `mundo = "…"`), que le gana a todo; si no, una etiqueta de su hilo que un mundo declara
    (`por` «etiqueta», `valor` cuál) y, si no, la ruta declarada que calza con su carpeta (`por` «ruta», `valor` la ruta
    como se declaró). Sin nada, `mundo` y `por` vacíos: sin clasificar, se ve en todos."""
    from telar import agentes

    declarado = declarado_de_agente(config, clave)
    if declarado:
        return {"mundo": declarado, "por": "agente.toml", "valor": f'mundo = "{declarado}"'}
    mundo = de_etiquetas(config, etiquetas)
    if mundo:
        suyas = next(m.etiquetas for m in config.mundos if m.nombre == mundo)
        return {"mundo": mundo, "por": "etiqueta", "valor": next(str(e).strip() for e in etiquetas if str(e).strip() in suyas)}
    base = agentes.base(config) if clave else None
    mundo, ruta = ruta_que_calza(config, str(base / clave)) if base is not None else ("", "")
    return {"mundo": mundo, "por": "ruta" if mundo else "", "valor": ruta}


def _mostrar(config, carpeta: Path) -> str:
    """Una carpeta como la lee la persona: desde la raíz si está dentro, o con `~`."""
    try:
        return f"{Path(carpeta).relative_to(Path(config.raiz))}/"
    except ValueError:
        texto, casa = str(carpeta), str(Path.home())
        return f"{'~' + texto[len(casa):] if texto.startswith(casa + os.sep) else texto}/"


def para_la_configuracion(config, etiquetas: dict | None = None) -> dict:
    """Lo que muestra ⚙ mundos (`GET /mundos`): cada mundo como lo da `para_la_pagina`, con el color que declara
    (`color_propio`; "" si toma uno por orden) y de dónde sale su horario (`horario_vive`: "raiz", todas las máquinas;
    "maquina", solo esta; "" sin horario); `fuera` y de dónde sale (`fuera_vive`); el archivo de la raíz (`raiz`, "" sin
    raíz), por qué no se lee (`error_raiz`) y lo suyo que esta máquina no aplica (`sobran_raiz`); dónde se pisan los
    horarios (`choques`, telar.horario.choques); las tintas que puede llevar uno (`tintas`) y los temas
    (`temas`); los modos que puede tener uno (`modos`: los de fábrica y los de `[modos]`, cada uno con su clave y su
    nombre); y cada agente residente con su carpeta, su mundo y por qué (`por_que_agente`), y qué pasa con él con otro
    mundo puesto (`fuera_de_su_mundo`, de su agente.toml: al-final, esconder o ver). `etiquetas` (hilo → las
    suyas), las de los hilos de los agentes; sin ellas, las del estado de esta máquina."""
    from telar import agentes as mod_agentes
    from telar import temas as mod_temas
    from telar.config import TINTAS_MUNDO

    propios = {m.nombre: m.color for m in getattr(config, "mundos", ()) or ()}
    salida_agentes = []
    if propios:
        if etiquetas is None:
            from telar import estado as mod_estado

            try:
                etiquetas = mod_estado.abrir(config).etiquetas()
            except Exception:  # noqa: BLE001 - sin el estado, cada agente por su carpeta
                etiquetas = {}
        for a in mod_agentes.descubrir(config):
            salida_agentes.append({"clave": a.clave, "nombre": a.nombre, "carpeta": _mostrar(config, a.carpeta),
                                   **por_que_agente(config, a.clave, etiquetas.get(a.nombre, ())),
                                   "fuera_de_su_mundo": a.fuera_de_su_mundo})
    from telar import modos as mod_modos

    from telar import mundos_raiz

    donde = getattr(config, "mundos_donde", {}) or {}
    archivo_raiz = getattr(config, "mundos_archivo", None)
    return {"mundos": [{**m, "color_propio": propios[m["nombre"]],
                        "horario_vive": (donde.get("horario") or {}).get(m["nombre"], "")}
                       for m in para_la_pagina(config)],
            "fuera": getattr(config, "mundos_fuera", "") or "", "fuera_vive": donde.get("fuera", ""),
            "raiz": str(archivo_raiz or ""), "error_raiz": getattr(config, "mundos_error", "") or "",
            "sobran_raiz": list(getattr(config, "mundos_sobran", ()) or ()),
            "choques": mundos_raiz.choques_de(config),
            "tintas": list(TINTAS_MUNDO),
            "temas": list(mod_temas.que_hay(config)),
            "modos": [{"clave": m["clave"], "nombre": m["nombre"]} for m in mod_modos.todos(config)],
            "agentes": salida_agentes}


def _destino(ruta) -> Path:
    from telar import config as mod_config

    return Path(ruta).expanduser() if ruta is not None else mod_config.ruta_config()


def _leidos(destino: Path) -> dict:
    """`[mundos]` de ese archivo, tal cual: sus mundos (tablas) y `fuera`."""
    import tomllib

    if not destino.exists():
        return {}
    tabla = tomllib.loads(destino.read_text(encoding="utf-8")).get("mundos", {})
    return tabla if isinstance(tabla, dict) else {}


def _modos_leidos(destino: Path) -> dict:
    """`[modos]` de ese archivo, tal cual (para saber qué modos propios hay)."""
    import tomllib

    if not destino.exists():
        return {}
    tabla = tomllib.loads(destino.read_text(encoding="utf-8")).get("modos", {})
    return tabla if isinstance(tabla, dict) else {}


#: un nombre que va sin comillas en la cabecera de su tabla (`[mundos.trabajo]`); los demás, entre comillas
_SIN_COMILLAS = re.compile(r"[A-Za-z0-9_-]+")


def _tabla_de(nombre: str) -> str:
    return f"mundos.{nombre}" if _SIN_COMILLAS.fullmatch(nombre) else f'mundos."{nombre}"'


def _escribir(destino: Path, texto: str) -> None:
    """Escribe el archivo entero si se sigue leyendo (como `config.escribir_clave`); si no, ErrorDeConfig y nada."""
    from telar import config as mod_config

    antes = destino.read_text(encoding="utf-8") if destino.exists() else ""
    mod_config.revisar_antes_de_escribir(antes, texto, destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".nuevo")
    temporal.write_text(texto, encoding="utf-8")
    if destino.exists():
        os.chmod(temporal, destino.stat().st_mode & 0o777)
    os.replace(temporal, destino)


def _valor(nombre: str, campo: str, v):
    """Un campo de `[mundos.<nombre>]` como se escribe: las listas, sus textos sin espacios a los lados ni repetidos
    (en un texto, separados por coma); el horario, un texto si es un tramo y una lista si son varios (en un texto,
    separados por «;», porque un tramo lleva comas: «lun,mié 9-13»); el color, el tema y el arte, un texto; los modos, una lista
    con sus nombres de antes pasados a los de ahora (`estandar` es `tactica`). Vacío: None, que quita la línea (sin
    modos, el mundo los tiene todos)."""
    from telar.config import ErrorDeConfig

    if v is None:
        return None
    if campo in ("color", "tema", "arte"):
        if not isinstance(v, str):
            raise ErrorDeConfig(f"mundos.{nombre}.{campo}: se esperaba un texto, llegó {v!r}")
        return v.strip() or None
    if isinstance(v, str):
        v = v.split(";" if campo == "horario" else ",")
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ErrorDeConfig(f"mundos.{nombre}.{campo}: se esperaba una lista de textos, llegó {v!r}")
    lista = list(dict.fromkeys(x.strip() for x in v if x.strip()))
    if campo == "modos":
        from telar.modos import ALIAS

        lista = list(dict.fromkeys(ALIAS.get(x, x) for x in lista))
    if not lista:
        return None
    return lista[0] if campo == "horario" and len(lista) == 1 else lista


def ajustar(ruta, nombre: str, valores: dict) -> dict:
    """Cambia solo esos campos de `[mundos.<nombre>]` (CAMPOS), línea por línea: lo demás del archivo, comentarios
    incluidos, queda como estaba. Vacío (o None) quita la línea: sin horario, el mundo se pone solo a mano; sin color,
    toma el que le toca por orden; sin tema, la página lleva el del modo; sin modos, los tiene todos. Antes de escribir se lee `[mundos]` entero como quedaría, con las reglas de siempre
    (un área, una ruta o una etiqueta en dos mundos es un error, y dice de cuál ya es; un modo que no existe, también, y
    dice cuáles hay). Devuelve lo escrito (None: lo
    quitado). KeyError si no hay ese mundo; ErrorDeConfig si algo no sirve."""
    from telar import config as mod_config
    from telar import temas as mod_temas

    destino = _destino(ruta)
    leidos = _leidos(destino)
    if not isinstance(leidos.get(nombre), dict):
        raise KeyError(nombre)
    sobra = set(valores) - set(CAMPOS)
    if sobra:
        raise mod_config.ErrorDeConfig(f"mundos.{nombre}.{sorted(sobra)[0]}: no existe ({', '.join(CAMPOS)})")
    limpio = {k: _valor(nombre, k, v) for k, v in valores.items()}
    # lo que ya es de otro, dicho desde este (config.py lo diría desde el último de los dos, que puede ser el otro)
    for campo in ("areas", "rutas", "etiquetas"):
        def clave(x: str) -> str:
            return x.rstrip("/") + "/" if campo == "rutas" else x
        for v in limpio.get(campo) or ():
            otro = next((k for k, m in leidos.items() if k != nombre and isinstance(m, dict)
                         and any(isinstance(x, str) and clave(x.strip()) == clave(v) for x in m.get(campo) or ())), "")
            if otro:
                raise mod_config.ErrorDeConfig(f"mundos.{nombre}.{campo}: «{v}» ya es de «{otro}»")
    quedaria = {k: v for k, v in leidos[nombre].items() if k not in limpio}
    quedaria.update({k: v for k, v in limpio.items() if v is not None})
    # que se siga leyendo y, si no, por qué (un tema, de fábrica o de los propios de este archivo)
    # (los que ya nombraba y no hay, uno propio que se borró en otra máquina, no impiden cambiar otra cosa)
    nuevos, _ = mod_config._mundos({**leidos, nombre: quedaria}, temas=(*mod_temas.en(destino), *mod_temas.faltan(destino)))
    if "modos" in limpio:
        mod_config._modos_de_mundos([m for m in nuevos if m.nombre == nombre], _modos_leidos(destino))
    for k, v in limpio.items():
        mod_config.escribir_clave(_tabla_de(nombre), k, v, destino)
    return limpio


def crear(ruta, nombre: str) -> str:
    """Agrega `[mundos.<nombre>]`, vacía, después del último mundo (al final del archivo, si no hay ninguno): un mundo
    que todavía no tiene nada suyo, para irle poniendo lo que es suyo. Devuelve el nombre. FileExistsError si ya hay
    uno así; ErrorDeConfig si el nombre no sirve."""
    from telar import config as mod_config

    destino = _destino(ruta)
    nombre = str(nombre or "").strip()
    leidos = _leidos(destino)
    if isinstance(leidos.get(nombre), dict):
        raise FileExistsError(nombre)
    if nombre in leidos or not re.fullmatch(r"[^\s,:/.\"'\[\]#=]+", nombre):
        raise mod_config.ErrorDeConfig(f"mundos.{nombre}: un mundo se llama con una palabra, sin espacios ni signos "
                                       "(«,», «:», «/», «.»…), y no «fuera»")
    mod_config._mundos({**leidos, nombre: {}})  # el nombre, con las reglas de siempre (no «sin-clasificar»)
    renglones = destino.read_text(encoding="utf-8").splitlines() if destino.exists() else []
    cabeza = re.compile(r"^\s*\[\s*mundos\s*\.")
    ultimo = max((i for i, r in enumerate(renglones) if cabeza.match(r)), default=-1)
    if ultimo < 0:
        donde = len(renglones)
    else:
        donde = next((n for n in range(ultimo + 1, len(renglones)) if renglones[n].strip().startswith("[")), len(renglones))
        if donde < len(renglones):
            # el comentario pegado a la tabla que sigue es de ella
            while donde > ultimo + 1 and renglones[donde - 1].lstrip().startswith("#"):
                donde -= 1
    while donde > 0 and not renglones[donde - 1].strip():
        donde -= 1
    renglones[donde:donde] = [*([""] if donde else []), f"[{_tabla_de(nombre)}]"]
    while renglones and not renglones[-1].strip():
        renglones.pop()
    _escribir(destino, "\n".join(renglones) + "\n")
    return nombre


def borrar(ruta, nombre: str) -> bool:
    """Quita `[mundos.<nombre>]` y, si rige fuera de todo horario, `[mundos] fuera` (vuelve a ser ambos): lo que era
    suyo queda sin clasificar. True si estaba."""
    from telar import config as mod_config
    from telar.unirse import quitar_tabla

    destino = _destino(ruta)
    leidos = _leidos(destino)
    if not isinstance(leidos.get(nombre), dict):
        return False
    texto = destino.read_text(encoding="utf-8")
    nuevo = quitar_tabla(texto, f"mundos.{nombre}")
    if nuevo == texto:
        return False
    if leidos.get("fuera") == nombre:
        mod_config.escribir_clave("mundos", "fuera", None, destino)
        nuevo = quitar_tabla(destino.read_text(encoding="utf-8"), f"mundos.{nombre}")
    _escribir(destino, nuevo)
    return True


def poner_fuera(ruta, valor: str) -> str:
    """`[mundos] fuera`: el mundo que rige fuera de todo horario; vacío, ambos (se quita la línea). Devuelve lo
    escrito. ErrorDeConfig si no es uno de los declarados."""
    from telar import config as mod_config

    destino = _destino(ruta)
    valor = str(valor or "").strip()
    nombres = [k for k, v in _leidos(destino).items() if isinstance(v, dict)]
    if valor and valor not in nombres:
        raise mod_config.ErrorDeConfig(f"mundos.fuera: el nombre de uno de los mundos declarados "
                                       f"({', '.join(nombres) or 'no hay'}); llegó {valor!r}")
    mod_config.escribir_clave("mundos", "fuera", valor or None, destino)
    return valor


def de_tarea(config, area: str, proyecto: str) -> str:
    """El mundo de una tarea: el de su `area` y, si su área no es de ninguno, el de la carpeta de su `proyecto`."""
    return de_area(config, area) or de_ruta(config, proyecto)


def de_fila(config, fila: dict) -> str:
    """El mundo de una fila de `telar pendientes` o `telar hoy`. Una tarea de un proveedor, por su `area` y su
    `proyecto`; una casilla de un documento, por la carpeta de su documento (`ruta`). La `ruta` de una tarea no
    cuenta: es la del hilo al que se la llevaría, y ese sale de su título."""
    de_proveedor = bool(fila.get("proveedor"))
    m = de_tarea(config, str(fila.get("area") or "") if de_proveedor else "", str(fila.get("proyecto") or ""))
    return m or ("" if de_proveedor else de_ruta(config, str(fila.get("ruta") or "")))


def pedidos(config, mundos) -> set[str]:
    """Los mundos de un filtro (`--mundo`, `?mundo=`), validados: un nombre declarado, o `sin-clasificar` (que
    queda como ""). Uno que no existe, ErrorDeServicio 404; vacío, set() (no filtra)."""
    pedidos = [str(m).strip() for m in mundos or () if str(m).strip()]
    if not pedidos:
        return set()
    hay = declarados(config)
    if not hay:
        raise ErrorDeServicio("esta configuración no declara mundos ([mundos]): no hay por cuál filtrar", 404)
    raros = [m for m in pedidos if m not in hay and m != SIN_CLASIFICAR]
    if raros:
        raise ErrorDeServicio(f"no hay un mundo «{raros[0]}»: {', '.join((*hay, SIN_CLASIFICAR))}", 404)
    return {"" if m == SIN_CLASIFICAR else m for m in pedidos}


def calza(mundo: str, filtro: set[str]) -> bool:
    """Si una cosa de ese mundo pasa el filtro (vacío: todas)."""
    return not filtro or (mundo or "") in filtro


class Clasificador:
    """El mundo de lo que necesita mirar los hilos: un hilo (por su carpeta, su agente o el hilo del que cuelga) y lo
    que se nombra por una dirección. Lee los hilos una vez, la primera que hace falta: los de esta máquina
    (`_comun.tejer`) y los de las otras, de su última foto (telar.espejo), esté o no en línea."""

    def __init__(self, ctx, hilos: dict[tuple[str, str], dict] | None = None):
        """`hilos`, si ya se tienen ({(nombre, máquina): hilo}, máquina "" la de aquí): no se vuelven a leer."""
        self.ctx = ctx
        self.config = ctx.config
        self._hilos: dict[tuple[str, str], dict] | None = hilos
        self._cache: dict[tuple[str, str], str] = {}

    # ── los hilos ──
    def preparar(self) -> None:
        """Lee los hilos (lo hace sola la primera vez que hace falta; quien quiera, la adelanta en otro hilo)."""
        if self._hilos is not None:
            return
        hilos: dict[tuple[str, str], dict] = {}
        try:
            from telar.ordenes import _comun

            tel = _comun.tejer(self.ctx, con_ficha=False)
            for h in tel.hilos:
                if not h.remoto:
                    j = _comun.json_hilo(h, tel, con_ficha=False)
                    hilos[(h.nombre, "")] = {k: j.get(k) for k in ("nombre", "relativa", "ruta", "agente", "padre", "etiquetas")}
        except Exception:  # noqa: BLE001 - sin hilos legibles, lo que depende de ellos queda sin clasificar
            pass
        try:
            from telar import espejo

            for foto in espejo.leer_todos(self.config):
                for j in foto.get("hilos") or []:
                    if isinstance(j, dict) and j.get("nombre") and not j.get("remoto"):
                        hilos.setdefault((str(j["nombre"]), str(foto.get("nombre") or "")), j)
        except Exception:  # noqa: BLE001
            pass
        self._hilos = hilos

    def _hilo(self, nombre: str, maquina: str = "") -> dict | None:
        self.preparar()
        assert self._hilos is not None
        if maquina:
            return self._hilos.get((nombre, maquina)) or self._hilos.get((nombre, ""))
        # sin máquina: el de aquí, y si no, el de otra
        return self._hilos.get((nombre, "")) or next((j for (n, _), j in self._hilos.items() if n == nombre), None)

    def de_hilo(self, nombre: str, maquina: str = "", _vistos: frozenset = frozenset()) -> str:
        """El mundo de un hilo: el de sus etiquetas, si un mundo las declara; si no, el de la carpeta de su proyecto;
        si no calza, el de la carpeta de su agente residente; si tampoco, el del hilo del que cuelga. "" si nada calza
        o no se lo encuentra."""
        if not declarados(self.config) or not nombre:
            return ""
        clave = (nombre, maquina)
        if clave in self._cache:
            return self._cache[clave]
        j = self._hilo(nombre, maquina)
        mundo = ""
        if j is not None:
            # la relativa es desde la raíz de la máquina donde vive el hilo: se lee desde la de aquí (la misma casa).
            # Un hilo en la raíz misma no está en ningún proyecto: su agente o su padre dicen más que la raíz entera
            relativa = str(j.get("relativa") or "").strip()
            # el mundo que declara su agente (agente.toml) le gana a todo: lo privado de un agente no se le escapa a
            # una etiqueta puesta a mano ni a una carpeta de otro mundo
            mundo = declarado_de_agente(self.config, str(j.get("agente") or ""))
            mundo = mundo or de_etiquetas(self.config, j.get("etiquetas"))
            mundo = mundo or (de_ruta(self.config, relativa) if relativa not in ("", ".") else "")
            mundo = mundo or self._de_agente(j)
            padre = str(j.get("padre") or "")
            if not mundo and padre and padre not in _vistos:
                mundo = self.de_hilo(padre, maquina, _vistos | {nombre})
            if not mundo and relativa == ".":
                mundo = de_ruta(self.config, ".")
        self._cache[clave] = mundo
        return mundo

    def _de_agente(self, j: dict) -> str:
        return de_agente(self.config, str(j.get("agente") or ""))

    # ── una dirección ──
    def de_direccion(self, direccion: str) -> str:
        """El mundo de lo que nombra una dirección: un hilo o un permiso (su hilo), un proyecto (su carpeta), un
        archivo (su ruta). "" en lo demás."""
        from telar import objetos

        try:
            d = objetos.leer(direccion)
        except ErrorDeServicio:
            return ""
        if d.tipo in ("hilo", "permiso"):
            return self.de_hilo(d.id, d.maquina)
        if d.tipo == "proyecto":
            return de_ruta(self.config, d.id)
        if d.tipo == "archivo":
            # archivo:<máquina>:<ruta>
            _, _, ruta = d.id.partition(":")
            return de_ruta(self.config, ruta or d.id)
        return ""

    def agente_de_hilo(self, nombre: str, maquina: str = "", _vistos: frozenset = frozenset()) -> str:
        """El agente residente del que es un hilo: el suyo (su carpeta) y, si no tiene, el del hilo del que cuelga (un
        hijo de un agente que trabaja en otra carpeta). "" si de ninguno o no se lo encuentra."""
        j = self._hilo(nombre, maquina) if nombre else None
        if j is None:
            return ""
        padre = str(j.get("padre") or "")
        return str(j.get("agente") or "") or (self.agente_de_hilo(padre, maquina, _vistos | {nombre})
                                              if padre and padre not in _vistos else "")

    def agente_de_direccion(self, direccion: str) -> str:
        """El agente residente del que es lo que nombra una dirección: un hilo o un permiso, el de su hilo
        (`agente_de_hilo`); un agente (`agente:<clave>`), él; un proyecto o un archivo, el de la carpeta donde vive si
        declara su mundo (`agente_de_ruta`). "" en lo demás."""
        from telar import objetos

        try:
            d = objetos.leer(direccion)
        except ErrorDeServicio:
            return ""
        if d.tipo in ("hilo", "permiso"):
            return self.agente_de_hilo(d.id, d.maquina)
        if d.tipo == "agente":
            return d.id
        if d.tipo == "proyecto":
            return agente_de_ruta(self.config, d.id)
        if d.tipo == "archivo":
            _, _, ruta = d.id.partition(":")
            return agente_de_ruta(self.config, ruta or d.id)
        return ""

    def agente_de_espera(self, e) -> str:
        """El agente residente del que es una espera: el del primero de sus enlaces que sea de uno (el hilo de un
        permiso, el hilo al que iba un mensaje, el agente que pregunta, la carpeta de su proyecto). "" si de ninguno."""
        return next((a for a in (self.agente_de_direccion(x) for x in e.enlaces or ()) if a), "")

    def de_espera(self, e) -> str:
        """El mundo de una espera que no lo dijo su tipo: el de su enlace principal (el hilo de un permiso, el hilo
        al que iba un mensaje, el proyecto de lo que traiga un módulo)."""
        return self.de_direccion(e.enlaces[0]) if e.enlaces else ""
