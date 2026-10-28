"""Módulos: una carpeta con un `modulo.toml` que declara lo que aporta, y que se instala de una vez.

Una pestaña del dashboard, una app, procesos periódicos y un resultado diario suelen ser una sola
cosa (un gráfico que un periódico baja y una pestaña dibuja). Sin módulos, cada pieza se declara
por separado, en dos máquinas. Con un módulo, la carpeta lo dice todo y la configuración solo
nombra la carpeta:

    [modulos.nino34]
    carpeta = "~/proyectos/nino34"

El manifiesto (`<carpeta>/modulo.toml`):

    descripcion = "la temperatura del mar en Niño 3.4"

    [pestana]                      # una pestaña del dashboard: un bloque (`[bloques]`)
    nombre = "niño 3.4"
    comando = ["bin/nino34", "pagina"]
    dentro = "plan"                # opcional: una subpestaña de una fija (ahora, tareas, proyectos, plan, calendario)

    [app]                          # algo que se abre en el panel (`[apps]`): pagina, archivo o url
    archivo = "dist/app.html"

    [periodicos.bajar]             # corre donde viven los periódicos (`telar periodicos`)
    cuando = "30 7,15 * * *"
    comando = "bin/nino34 bajar"

    [resultado]                    # lo que el periódico deja por día (`[resultados]`)
    carpeta = "~/.local/state/nino34"

    [ordenes.medir]                # una orden propia: `telar nino34 medir …`
    descripcion = "la temperatura de hoy"
    comando = ["bin/nino34", "medir"]
    consulta = true                # también se le puede preguntar desde la página y otra máquina

    [instalar]                     # lo que corre al instalarlo y al actualizarlo, en su carpeta
    comando = ["python3", "-m", "venv", ".venv"]

    [contexto]                     # lo que el agente de cada hilo sabe del módulo al arrancar
    texto = "La temperatura del mar: `telar nino34 medir`."

    [requiere]                     # lo que tiene que haber en la máquina: se mira al instalarlo
    programas = ["uv"]

    [objetos.medicion]             # un tipo de objeto (telar.objetos): medicion:<id>, con sus consultas
    ver = "medir"                  # recibe {"id": …} y da el objeto
    acciones = []                  # otras consultas: reciben {"id": …, …parámetros}

    [permisos]                     # lo que pide fuera de su carpeta: se muestra antes de instalarlo
    leer = ["~/datos/oceano"]      # rutas que lee
    escribir = ["~/.local/state/nino34"]
    red = ["psl.noaa.gov"]         # los sitios a los que se conecta (true: cualquiera; false: ninguno)
    ordenes = ["mensaje"]          # las órdenes de telar que corre (`telar mensaje`)

Las rutas relativas son de la carpeta del módulo, y sus periódicos corren en ella. Todo lo que
aporta toma el nombre del módulo: la pestaña es el bloque `nino34`, el resultado `nino34`, y un
periódico `nino34-bajar` (o `nino34` si se llama como el módulo). El resultado se lee donde corren
los periódicos (`[periodicos] en`). telar los junta con lo declarado a mano al leer la
configuración; el resto de telar no distingue de dónde vino cada pieza.

**Órdenes.** Cada `[ordenes.<verbo>]` es `telar <modulo> <verbo> [args…]`: corre su `comando` con los
argumentos detrás, en la carpeta donde está quien la llama, con la entrada y la salida de la terminal.
Una con `consulta = true` también se pide sin terminal (`consultar`, la API `GET /modulos/<m>/<verbo>`,
el bus): recibe los parámetros como un objeto JSON por la entrada, corre en la carpeta del módulo y
devuelve un objeto JSON por la salida. Las dos reciben en el entorno lo que el módulo necesita saber de
telar: `TELAR_RAIZ`, `TELAR_REPOS` (los repos de `[repos]`, en JSON: nombre, ruta y perfil),
`TELAR_MAQUINA` y `TELAR_MODULO` (su carpeta). Un módulo es un programa aparte: si se cae, telar sigue.

**Permisos.** `[permisos]` dice lo que el módulo pide fuera de su carpeta: rutas que lee y que escribe, la
red y las órdenes de telar que corre. `telar modulos instalar` lo muestra antes de preguntar, y `actualizar`
dice si cambió. telar **todavía no lo hace cumplir**: un módulo corre con los permisos de quien lo instaló,
lo declare o no (docs/propuestas/permisos.md). Sin la tabla, el módulo «no dice qué pide», que no es lo
mismo que no pedir nada (`[permisos]` vacía).

**Instalados.** `telar modulo instalar <repo git o carpeta>` lo clona en `<datos>/modulos/<nombre>`
(`~/.local/share/telar`), corre su `[instalar]` y lo anota en `modulos.toml`, al lado de la
configuración: ese archivo es solo de `telar modulo` (la configuración sigue siendo de quien la escribe).
`--enlazar` usa la carpeta donde está, sin copiarla, para desarrollarlo. Desde un catálogo (telar.catalogo),
`telar modulos instalar <nombre>` lo baja en la versión que dice el catálogo (una etiqueta o un commit) y anota de
cuál vino; actualizarlo es ir a la versión que el catálogo diga después. `activo = false` lo deja instalado sin
cargarlo (`telar modulos desactivar`): no aporta nada hasta que se active de nuevo.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from telar.salida import visible

MANIFIESTO = "modulo.toml"
NOMBRE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_RAIZ = {"nombre", "descripcion", "pestana", "app", "periodicos", "resultado", "ordenes", "instalar", "contexto",
         "requiere", "objetos", "permisos", "fondo"}
#: lo que entiende `[permisos]`; una clave que no está aquí se muestra como no entendida, no se calla
PERMISOS = ("leer", "escribir", "red", "ordenes")
TOPE_CONTEXTO = 600  # caracteres: entra en cada sesión de cada hilo
ESPERA_CONSULTA = 30


class ErrorDeModulo(ValueError):
    """El manifiesto no está, o dice algo que telar no entiende."""


@dataclass(frozen=True, slots=True)
class Modulo:
    nombre: str
    carpeta: Path
    descripcion: str = ""
    pestana: dict = field(default_factory=dict)
    app: dict = field(default_factory=dict)
    #: nombre del proceso (ya con el del módulo) → su tabla
    periodicos: dict = field(default_factory=dict)
    resultado: dict = field(default_factory=dict)
    #: verbo → {comando, descripcion, consulta}
    ordenes: dict = field(default_factory=dict)
    #: lo que corre al instalarlo y al actualizarlo
    instalar: tuple = ()
    #: lo que el agente de cada hilo sabe del módulo al arrancar (`[contexto] texto`)
    contexto: str = ""
    #: los programas que tiene que haber en el PATH (`[requiere] programas`)
    requiere: tuple = ()
    #: los tipos de objeto que trae (`[objetos.<tipo>]`): tipo → {ver, acciones, descripcion}
    objetos: dict = field(default_factory=dict)
    #: lo que pide (`[permisos]`): leer, escribir y ordenes son tuplas, red es una tupla de sitios o un
    #: bool, y `otros` lo que esta versión no entiende. None si el manifiesto no lo dice. No se hace cumplir
    permisos: dict | None = None
    #: un fondo para la terminal de los hilos (`[fondo] archivo`): una página que se dibuja detrás de ella, aislada
    #: (`[terminal] fondo = "<módulo>"`). {archivo, nombre}; vacío si no trae
    fondo: dict = field(default_factory=dict)

    def faltan(self) -> list[str]:
        """Los programas de `[requiere]` que esta máquina no tiene."""
        import shutil

        return [p for p in self.requiere if not shutil.which(p)]

    @property
    def aporta(self) -> list[str]:
        """Lo que trae, en palabras: «pestaña», «app», «periódico nino34», «resultado», «orden medir»."""
        return ([*(["pestaña"] if self.pestana else []), *(["app"] if self.app else []),
                 *[f"periódico {n}" for n in self.periodicos], *(["resultado"] if self.resultado else []),
                 *[f"orden {v}" + (" (consulta)" if o.get("consulta") else "") for v, o in self.ordenes.items()],
                 *[f"objetos {t}:" for t in self.objetos],
                 *(["contexto del agente"] if self.contexto else []), *(["fondo de la terminal"] if self.fondo else [])])

    @property
    def pide(self) -> list[str]:
        """Lo que pide, en palabras, una cosa por elemento: «leer ~/datos», «red: psl.noaa.gov», «órdenes de
        telar: mensaje». Sin `[permisos]`, lo dice; con la tabla vacía, «nada fuera de su carpeta»."""
        return palabras_permisos(self.permisos)


def palabras_permisos(p: dict | None) -> list[str]:
    if p is None:
        return ["no dice qué pide (sin [permisos] en su modulo.toml)"]
    salida = [f"{verbo} {', '.join(p[clave])}" for clave, verbo in (("leer", "leer"), ("escribir", "escribir"))
              if p.get(clave)]
    red = p.get("red")
    if red is True:
        salida.append("red: cualquier sitio")
    elif red:
        salida.append("red: " + ", ".join(red))
    if p.get("ordenes"):
        salida.append("órdenes de telar: " + ", ".join(p["ordenes"]))
    salida += [f"«{k}» (esta versión de telar no lo entiende: {v!r})" for k, v in p.get("otros", {}).items()]
    # lo escribe el módulo y se lee antes de dar el sí: un carácter de control no borra ni tapa la línea
    return [visible(x) for x in salida] or ["nada fuera de su carpeta"]


def _permisos(nombre: str, datos) -> dict | None:
    """`[permisos]` validado. Una clave que esta versión no conoce no rompe el módulo (uno escrito para un telar
    más nuevo se sigue instalando), pero queda en `otros` y se muestra: lo que pide no se calla."""
    if datos is None:
        return None

    def lista(clave: str) -> tuple:
        # ordenadas y sin repetir: las mismas rutas en otro orden piden lo mismo (y `actualizar` no lo cuenta
        # como un cambio)
        v = datos.get(clave, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            raise ErrorDeModulo(f"{nombre}: [permisos] {clave}: se esperaba una lista de textos")
        return tuple(sorted({x.strip() for x in v}))

    red = datos.get("red", False)
    if isinstance(red, bool):
        pass
    elif isinstance(red, list) and all(isinstance(x, str) and x.strip() for x in red):
        red = tuple(sorted({x.strip() for x in red})) or False  # ningún sitio es lo mismo que `false`
    else:
        raise ErrorDeModulo(f"{nombre}: [permisos] red: true, false o una lista de sitios")
    # «telar mensaje» y «mensaje» son lo mismo: la orden, sin el programa. «telar» solo no es ninguna orden
    ordenes = []
    for x in lista("ordenes"):
        palabras = x.split()
        palabras = palabras[1:] if palabras[0] == "telar" else palabras
        if not palabras:
            raise ErrorDeModulo(f"{nombre}: [permisos] ordenes: «{x}» no es una orden de telar (como «mensaje»)")
        ordenes.append(" ".join(palabras))
    return {"leer": lista("leer"), "escribir": lista("escribir"), "red": red,
            "ordenes": tuple(sorted(set(ordenes))), "otros": {k: v for k, v in datos.items() if k not in PERMISOS}}


def permisos_json(p: dict | None) -> dict | None:
    """`[permisos]` como va en `telar modulos --json`: listas, y `red` como lista o bool."""
    if p is None:
        return None
    salida = {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items() if k != "otros"}
    # lo que no se entiende va tal cual, salvo lo que JSON no sabe escribir (una fecha de TOML), como texto
    salida["otros"] = json.loads(json.dumps(p.get("otros", {}), ensure_ascii=False, default=str))
    return salida


def _ruta(carpeta: Path, valor: str) -> str:
    """Una ruta del manifiesto: relativa a la carpeta del módulo, o absoluta, o con ~."""
    p = Path(valor).expanduser()
    return str(p if p.is_absolute() else carpeta / p)


def _comando(carpeta: Path, comando: list[str]) -> list[str]:
    """El primer elemento de un comando, si es un archivo del módulo, va con su ruta absoluta."""
    primero = comando[0]
    if not Path(primero).is_absolute() and (carpeta / primero).exists():
        primero = str(carpeta / primero)
    return [primero, *comando[1:]]


def leer(nombre: str, carpeta: Path) -> Modulo:
    """El módulo de esa carpeta, con sus rutas ya resueltas."""
    if not NOMBRE.fullmatch(nombre):
        raise ErrorDeModulo(f"«{nombre}»: el nombre de un módulo va en minúsculas, sin espacios")
    carpeta = carpeta.expanduser().resolve()
    archivo = carpeta / MANIFIESTO
    try:
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErrorDeModulo(f"{nombre}: no hay {archivo}") from None
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ErrorDeModulo(f"{nombre}: {archivo}: {e}") from None
    sobra = set(datos) - _RAIZ
    if sobra:
        raise ErrorDeModulo(f"{nombre}: {MANIFIESTO} no conoce «{sorted(sobra)[0]}»")
    for clave in ("pestana", "app", "periodicos", "resultado", "ordenes", "instalar", "contexto", "requiere", "objetos",
                  "permisos", "fondo"):
        if not isinstance(datos.get(clave, {}), dict):
            raise ErrorDeModulo(f"{nombre}: [{clave}] tiene que ser una tabla")

    pestana = dict(datos.get("pestana", {}))
    if pestana:
        if not isinstance(pestana.get("comando"), list) or not pestana["comando"]:
            raise ErrorDeModulo(f"{nombre}: [pestana] comando: se esperaba una lista de palabras")
        pestana["comando"] = _comando(carpeta, pestana["comando"])
        pestana.setdefault("nombre", nombre)

    app = dict(datos.get("app", {}))
    if app:
        if isinstance(app.get("pagina"), list) and app["pagina"]:
            app["pagina"] = _comando(carpeta, app["pagina"])
        for campo in ("archivo", "memoria"):
            if isinstance(app.get(campo), str) and app[campo]:
                app[campo] = _ruta(carpeta, app[campo])
        app.setdefault("nombre", nombre)

    periodicos = {}
    for sub, cuerpo in datos.get("periodicos", {}).items():
        if not isinstance(cuerpo, dict):
            raise ErrorDeModulo(f"{nombre}: [periodicos.{sub}] tiene que ser una tabla")
        periodicos[nombre if sub == nombre else f"{nombre}-{sub}"] = dict(cuerpo)

    resultado = dict(datos.get("resultado", {}))
    if resultado and isinstance(resultado.get("carpeta"), str):
        resultado["carpeta"] = _ruta(carpeta, resultado["carpeta"]) if not resultado["carpeta"].startswith("~") else resultado["carpeta"]

    ordenes = {}
    for verbo, cuerpo in datos.get("ordenes", {}).items():
        if not NOMBRE.fullmatch(verbo):
            raise ErrorDeModulo(f"{nombre}: [ordenes.{verbo}]: el verbo va en minúsculas, sin espacios")
        if not isinstance(cuerpo, dict) or not isinstance(cuerpo.get("comando"), list) or not cuerpo["comando"] \
                or not all(isinstance(w, str) for w in cuerpo["comando"]):
            raise ErrorDeModulo(f"{nombre}: [ordenes.{verbo}] comando: se esperaba una lista de palabras")
        sobra = set(cuerpo) - {"comando", "descripcion", "consulta"}
        if sobra:
            raise ErrorDeModulo(f"{nombre}: [ordenes.{verbo}] no conoce «{sorted(sobra)[0]}»")
        ordenes[verbo] = {"comando": _comando(carpeta, cuerpo["comando"]),
                          "descripcion": str(cuerpo.get("descripcion", "")).strip(),
                          "consulta": cuerpo.get("consulta") is True}

    instalar = datos.get("instalar", {})
    if instalar and (not isinstance(instalar.get("comando"), list) or not instalar["comando"]):
        raise ErrorDeModulo(f"{nombre}: [instalar] comando: se esperaba una lista de palabras")

    contexto = datos.get("contexto", {}).get("texto", "")
    if not isinstance(contexto, str):
        raise ErrorDeModulo(f"{nombre}: [contexto] texto: se esperaba un texto")
    contexto = " ".join(contexto.split())
    if len(contexto) > TOPE_CONTEXTO:
        raise ErrorDeModulo(f"{nombre}: [contexto] texto: hasta {TOPE_CONTEXTO} caracteres (entra en cada sesión)")

    requiere = datos.get("requiere", {}).get("programas", [])
    if not isinstance(requiere, list) or not all(isinstance(x, str) and x.strip() for x in requiere):
        raise ErrorDeModulo(f"{nombre}: [requiere] programas: se esperaba una lista de nombres de programa")

    objetos = {}
    for tipo, cuerpo in datos.get("objetos", {}).items():
        if not NOMBRE.fullmatch(tipo) or not isinstance(cuerpo, dict):
            raise ErrorDeModulo(f"{nombre}: [objetos.{tipo}]: el tipo va en minúsculas, y es una tabla")
        acciones = cuerpo.get("acciones", [])
        if not isinstance(acciones, list) or not all(isinstance(a, str) for a in acciones):
            raise ErrorDeModulo(f"{nombre}: [objetos.{tipo}] acciones: una lista de órdenes del módulo")
        for verbo in [cuerpo.get("ver"), *acciones]:
            if not isinstance(verbo, str) or verbo not in ordenes or not ordenes[verbo]["consulta"]:
                raise ErrorDeModulo(f"{nombre}: [objetos.{tipo}]: «{verbo}» tiene que ser una de sus [ordenes] con consulta = true")
        objetos[tipo] = {"ver": cuerpo["ver"], "acciones": tuple(acciones), "descripcion": str(cuerpo.get("descripcion", ""))}

    descripcion = datos.get("descripcion", "")
    if not isinstance(descripcion, str):
        raise ErrorDeModulo(f"{nombre}: descripcion: se esperaba un texto")
    fondo = dict(datos.get("fondo", {}))
    if fondo:
        sobra = set(fondo) - {"archivo", "nombre"}
        if sobra:
            raise ErrorDeModulo(f"{nombre}: [fondo] no conoce «{sorted(sobra)[0]}»")
        if not isinstance(fondo.get("archivo"), str) or not fondo["archivo"].endswith((".html", ".htm")):
            raise ErrorDeModulo(f"{nombre}: [fondo] archivo: una página .html de su carpeta")
        fondo = {"archivo": str(_ruta(carpeta, fondo["archivo"])), "nombre": str(fondo.get("nombre") or nombre)}

    return Modulo(nombre=nombre, carpeta=carpeta, descripcion=descripcion.strip(), pestana=pestana, app=app, fondo=fondo,
                  periodicos=periodicos, resultado=resultado, ordenes=ordenes,
                  instalar=tuple(_comando(carpeta, instalar["comando"])) if instalar else (), contexto=contexto,
                  requiere=tuple(x.strip() for x in requiere), objetos=objetos,
                  permisos=_permisos(nombre, datos.get("permisos")))


# ── correr sus órdenes ─────────────────────────────────────────────────────────────

def entorno(config, m: Modulo) -> dict:
    """Lo que un módulo sabe de telar, en su entorno."""
    from telar import bus as mod_bus

    from telar.perfil import ruta_de_repo

    # la ruta absoluta (una relativa, desde la raíz): el módulo no sabe desde dónde se escribió
    repos = [{"nombre": r.nombre, "ruta": str(ruta_de_repo(config, r)), "perfil": str(r.perfil or "")}
             for r in getattr(config, "repos", ()) or ()]
    maquina = mod_bus.maquina(config) if getattr(config, "bus", None) is not None else ""
    return {**os.environ, "TELAR_RAIZ": str(Path(config.raiz).expanduser()), "TELAR_REPOS": json.dumps(repos),
            "TELAR_MAQUINA": maquina, "TELAR_MODULO": str(m.carpeta)}


def buscar(config, nombre: str) -> Modulo | None:
    return next((m for m in getattr(config, "modulos", ()) if m.nombre == nombre), None)


def correr_orden(config, m: Modulo, argv: list[str]) -> int:
    """`telar <modulo> <verbo> …` en la terminal. Sin verbo, la lista de sus órdenes."""
    if not argv or argv[0] in ("-h", "--help"):
        print(f"telar {m.nombre} <orden>" + (f" — {m.descripcion}" if m.descripcion else ""))
        for verbo, o in m.ordenes.items():
            print(f"  {verbo:<12}{o['descripcion']}")
        return 0 if argv else 1
    o = m.ordenes.get(argv[0])
    if o is None:
        raise ErrorDeModulo(f"{m.nombre} no tiene la orden «{argv[0]}»: tiene {', '.join(m.ordenes) or 'ninguna'}")
    try:
        return subprocess.run([*o["comando"], *argv[1:]], env=entorno(config, m)).returncode
    except OSError as e:
        raise ErrorDeModulo(f"{m.nombre} {argv[0]}: {e}") from None


def consultar(config, nombre: str, verbo: str, params: dict) -> dict:
    """Una orden `consulta` de un módulo de aquí: los parámetros por la entrada, un objeto JSON de vuelta."""
    m = buscar(config, nombre)
    if m is None:
        raise ErrorDeModulo(f"aquí no está instalado el módulo «{nombre}»")
    o = m.ordenes.get(verbo)
    if o is None or not o["consulta"]:
        raise ErrorDeModulo(f"{nombre} no tiene la consulta «{verbo}»")
    try:
        r = subprocess.run(o["comando"], input=json.dumps(params, ensure_ascii=False), capture_output=True, text=True,
                           cwd=m.carpeta, env={**entorno(config, m), "TELAR_CONSULTA": "1"}, timeout=ESPERA_CONSULTA)
    except subprocess.TimeoutExpired:
        raise ErrorDeModulo(f"{nombre} {verbo}: no respondió en {ESPERA_CONSULTA} s") from None
    except OSError as e:
        raise ErrorDeModulo(f"{nombre} {verbo}: {e}") from None
    if r.returncode != 0:
        raise ErrorDeModulo(f"{nombre} {verbo}: " + ((r.stderr or r.stdout).strip().splitlines() or ["falló"])[-1][:300])
    try:
        salida = json.loads(r.stdout)
    except ValueError:
        raise ErrorDeModulo(f"{nombre} {verbo}: no devolvió JSON") from None
    if not isinstance(salida, dict):
        raise ErrorDeModulo(f"{nombre} {verbo}: se esperaba un objeto JSON")
    return salida


# ── instalados ─────────────────────────────────────────────────────────────────────

INSTALADOS = "modulos.toml"


def _datos() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "telar" / "modulos"


def ruta_instalados(origen_config: Path | None) -> Path:
    """`modulos.toml`, al lado de la configuración."""
    from telar.config import ruta_config

    return Path(origen_config or ruta_config()).parent / INSTALADOS


def leer_instalados(ruta: Path) -> dict:
    """nombre → {carpeta, fuente, version, enlazado}. {} si no hay archivo."""
    try:
        datos = tomllib.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ErrorDeModulo(f"{ruta}: {e}") from None
    return {k: v for k, v in datos.items() if isinstance(v, dict)}


def sin_credenciales(fuente: str) -> str:
    """La fuente sin la parte `usuario:clave@` de una URL: se ve de dónde viene, no con qué se entra.

    `telar modulo instalar https://ana:token@host/…` deja esa URL en `modulos.toml` (y `git remote
    get-url origin` la devuelve igual). Una carpeta o una dirección `git@host:…` quedan como están."""
    from urllib.parse import urlsplit, urlunsplit

    try:
        partes = urlsplit(fuente)
    except ValueError:
        return fuente
    if not partes.scheme or "@" not in partes.netloc:
        return fuente
    return urlunsplit(partes._replace(netloc=partes.netloc.rsplit("@", 1)[1]))


def procedencia(anotado: dict | None) -> dict:
    """De dónde vino un módulo, de lo que anotó `telar modulo` en `modulos.toml` (`anotado`, su tabla, o
    None si se declaró a mano): `instalado`, `fuente` (sin credenciales), `version` y `enlazado`.

    El archivo no se edita a mano, pero si alguien lo hace no se le cree cualquier cosa: `enlazado` es
    verdadero solo si dice `true` (el texto "false" no lo es)."""
    d = anotado if isinstance(anotado, dict) else {}
    version = d.get("version")
    return {"instalado": bool(d), "fuente": sin_credenciales(str(d.get("fuente") or "")),
            "version": version if isinstance(version, str) else "", "enlazado": d.get("enlazado") is True}


def linea_procedencia(p: dict) -> str:
    """Lo de `procedencia` para leer: «fuente @ version», «fuente» si no hay versión anotada (uno enlazado
    fuera de git), o «(a mano)»."""
    if not p["instalado"]:
        return "(a mano)"
    return " @ ".join(x for x in (p["fuente"], p["version"]) if x) or "(sin fuente anotada)"


def _escribir_instalados(ruta: Path, instalados: dict) -> None:
    lineas = ["# Los módulos que instaló `telar modulo`. Lo escribe esa orden: no lo edites a mano.", ""]
    for nombre, d in sorted(instalados.items()):
        lineas.append(f"[{nombre}]")
        for k in ("carpeta", "fuente", "version", "ref", "catalogo", "instalado"):
            if d.get(k):
                lineas.append(f"{k} = {json.dumps(str(d[k]), ensure_ascii=False)}")
        if d.get("enlazado"):
            lineas.append("enlazado = true")
        if d.get("activo") is False:
            lineas.append("activo = false")
        if isinstance(d.get("pide"), list):
            # lo que pedía cuando se instaló (o se actualizó por última vez), en palabras: contra eso compara
            # `actualizar`. Una lista de JSON de textos es TOML válido
            lineas.append(f"pide = {json.dumps([str(x) for x in d['pide']], ensure_ascii=False)}")
        lineas.append("")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text("\n".join(lineas), encoding="utf-8")
    tmp.replace(ruta)


def _git(carpeta: Path | None, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *(["-C", str(carpeta)] if carpeta else []), *args], capture_output=True, text=True)


def _nombre_de_fuente(fuente: str) -> str:
    base = re.sub(r"\.git$", "", fuente.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]).lower()
    return re.sub(r"[^a-z0-9_-]", "-", base.removeprefix("telar-")) or "modulo"


def _bajar_ref(origen: str, destino: Path, ref: str) -> None:
    """Un clon en `ref` (una etiqueta o una rama: --branch; un commit: el clon entero y checkout)."""
    r = _git(None, "clone", "-q", "--depth", "1", "--branch", ref, origen, str(destino))
    if r.returncode == 0:
        return
    import shutil

    shutil.rmtree(destino, ignore_errors=True)
    r = _git(None, "clone", "-q", origen, str(destino))
    if r.returncode != 0:
        raise ErrorDeModulo(f"git clone {origen}: {(r.stderr or r.stdout).strip()[-300:]}")
    c = _git(destino, "checkout", "-q", ref)
    if c.returncode != 0:
        shutil.rmtree(destino, ignore_errors=True)
        raise ErrorDeModulo(f"{origen} no tiene «{ref}» (ni etiqueta, ni rama, ni commit)")


def preparar(fuente: str, *, nombre: str = "", enlazar: bool = False, ref: str = "") -> tuple[Modulo, dict]:
    """Baja (o ubica, con `enlazar`) el módulo y lee su manifiesto, sin anotarlo todavía: lo que se va a
    instalar, para mostrarlo antes. Devuelve el módulo y lo que se anotaría. `ref`: en esa etiqueta o commit
    (la de un catálogo), no en la rama de siempre."""
    from datetime import date

    local = Path(fuente).expanduser()
    if enlazar:
        if not (local / MANIFIESTO).is_file():
            raise ErrorDeModulo(f"--enlazar: {local} no tiene {MANIFIESTO}")
        carpeta = local.resolve()
        nombre = nombre or _manifiesto_nombre(carpeta) or _nombre_de_fuente(str(carpeta))
        version = _git(carpeta, "rev-parse", "--short", "HEAD").stdout.strip()
        return leer(nombre, carpeta), {"carpeta": str(carpeta), "fuente": _fuente_de(carpeta), "version": version,
                                       "instalado": date.today().isoformat(), "enlazado": True}
    origen = str(local.resolve()) if local.is_dir() else fuente
    provisorio = _datos() / f".bajando-{os.getpid()}"
    if provisorio.exists():
        import shutil

        shutil.rmtree(provisorio)
    provisorio.parent.mkdir(parents=True, exist_ok=True)
    if ref:
        _bajar_ref(origen, provisorio, ref)
    else:
        r = _git(None, "clone", "-q", "--depth", "1", origen, str(provisorio))
        if r.returncode != 0:
            raise ErrorDeModulo(f"git clone {origen}: {(r.stderr or r.stdout).strip()[-300:]}")
    nombre = nombre or _manifiesto_nombre(provisorio) or _nombre_de_fuente(origen)
    try:
        m = leer(nombre, provisorio)
    except ErrorDeModulo:
        import shutil

        shutil.rmtree(provisorio, ignore_errors=True)
        raise
    version = _git(provisorio, "rev-parse", "--short", "HEAD").stdout.strip()
    return m, {"carpeta": str(_datos() / nombre), "fuente": origen, "version": version, "ref": ref,
               "instalado": date.today().isoformat(), "provisorio": str(provisorio)}


def _manifiesto_nombre(carpeta: Path) -> str:
    try:
        v = tomllib.loads((carpeta / MANIFIESTO).read_text(encoding="utf-8")).get("nombre", "")
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    return v if isinstance(v, str) and NOMBRE.fullmatch(v) else ""


def _correr_instalar(m: Modulo, carpeta: Path) -> None:
    if not m.instalar:
        return
    comando = [str(carpeta / Path(w).relative_to(m.carpeta)) if Path(w).is_absolute() and Path(w).is_relative_to(m.carpeta)
               else w for w in m.instalar]
    r = subprocess.run(comando, cwd=carpeta, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise ErrorDeModulo(f"{m.nombre}: [instalar] falló: " + ((r.stderr or r.stdout).strip().splitlines() or [""])[-1][:300])


def confirmar_instalacion(ruta: Path, m: Modulo, anotar: dict) -> Path:
    """Deja el módulo en su carpeta, corre su `[instalar]` y lo anota en `modulos.toml`."""
    import shutil

    instalados = leer_instalados(ruta)
    if m.nombre in instalados:
        shutil.rmtree(anotar.get("provisorio", ""), ignore_errors=True) if anotar.get("provisorio") else None
        raise ErrorDeModulo(f"ya está instalado «{m.nombre}»: telar modulo actualizar {m.nombre}, o quitar")
    if m.faltan():
        if anotar.get("provisorio"):
            shutil.rmtree(anotar["provisorio"], ignore_errors=True)
        raise ErrorDeModulo(f"{m.nombre} necesita {', '.join(m.faltan())}, y esta máquina no lo tiene en el PATH")
    carpeta = Path(anotar["carpeta"])
    if anotar.get("provisorio"):
        if carpeta.exists():
            shutil.rmtree(anotar["provisorio"], ignore_errors=True)
            raise ErrorDeModulo(f"ya hay una carpeta {carpeta}: bórrala o elige otro --nombre")
        Path(anotar.pop("provisorio")).rename(carpeta)
    try:
        _correr_instalar(m, carpeta)
    except ErrorDeModulo:
        if not anotar.get("enlazado"):
            shutil.rmtree(carpeta, ignore_errors=True)
        raise
    instalados[m.nombre] = {**anotar, "pide": m.pide}  # lo que se mostró antes del sí
    _escribir_instalados(ruta, instalados)
    return carpeta


def _fuente_de(carpeta: Path) -> str:
    """El repositorio remoto de la carpeta si el módulo es ese repositorio entero; si no, la carpeta."""
    raiz_git = _git(carpeta, "rev-parse", "--show-toplevel").stdout.strip()
    if raiz_git and Path(raiz_git).resolve() == carpeta:
        remoto = _git(carpeta, "remote", "get-url", "origin").stdout.strip()
        if remoto:
            return remoto
    return str(carpeta)


def adoptar(ruta: Path, config_ruta: Path, nombre: str) -> str:
    """Un módulo declarado a mano (`[modulos.<nombre>]` en la configuración) pasa a `modulos.toml`, enlazado
    a la carpeta donde está: desde ahí se actualiza y se quita como los demás. Su bloque sale de la
    configuración, que queda respaldada al lado (`config.toml.antes-adoptar-<nombre>`)."""
    from datetime import date

    texto = config_ruta.read_text(encoding="utf-8")
    datos = tomllib.loads(texto).get("modulos", {}).get(nombre)
    if not isinstance(datos, dict) or not isinstance(datos.get("carpeta"), str):
        raise ErrorDeModulo(f"«{nombre}» no está declarado a mano en {config_ruta}")
    carpeta = Path(datos["carpeta"]).expanduser().resolve()
    m = leer(nombre, carpeta)
    instalados = leer_instalados(ruta)
    if nombre in instalados:
        raise ErrorDeModulo(f"«{nombre}» ya está en {ruta}")
    instalados[nombre] = {"carpeta": str(carpeta), "fuente": _fuente_de(carpeta), "enlazado": True,
                          "version": _git(carpeta, "rev-parse", "--short", "HEAD").stdout.strip(),
                          "instalado": date.today().isoformat(), "pide": m.pide}
    # el bloque, de su cabecera hasta la siguiente tabla (con los comentarios que lo preceden pegados)
    lineas = texto.split("\n")
    i = next(k for k, l in enumerate(lineas) if l.strip() == f"[modulos.{nombre}]")
    j = next((k for k in range(i + 1, len(lineas)) if lineas[k].lstrip().startswith("[")), len(lineas))
    while j > i + 1 and (not lineas[j - 1].strip() or lineas[j - 1].lstrip().startswith("#")):
        j -= 1  # los comentarios y blancos del final son de la tabla siguiente
    respaldo = config_ruta.with_name(f"{config_ruta.name}.antes-adoptar-{nombre}")
    respaldo.write_text(texto, encoding="utf-8")
    nuevo = "\n".join(lineas[:i] + lineas[j:]).replace("\n\n\n\n", "\n\n")
    _escribir_instalados(ruta, instalados)
    tmp = config_ruta.with_suffix(".tmp")
    tmp.write_text(nuevo, encoding="utf-8")
    tmp.replace(config_ruta)
    return f"{m.nombre}: adoptado, enlazado a {carpeta} (la configuración de antes, en {respaldo.name})"


def activar(ruta: Path, nombre: str, si: bool) -> str:
    """Lo enciende o lo apaga sin desinstalarlo: apagado, la configuración no lo carga (no aporta nada)."""
    instalados = leer_instalados(ruta)
    d = instalados.get(nombre)
    if d is None:
        raise ErrorDeModulo(f"«{nombre}» no lo instaló telar modulo (uno declarado a mano se apaga quitándolo de la "
                            "configuración)")
    if (d.get("activo") is not False) == si:
        return f"{nombre}: ya estaba {'activo' if si else 'apagado'}"
    instalados[nombre] = {**{k: v for k, v in d.items() if k != "activo"}, **({} if si else {"activo": False})}
    _escribir_instalados(ruta, instalados)
    return f"{nombre}: {'activo' if si else 'apagado (sigue instalado: telar modulos activar ' + nombre + ')'}"


def actualizar(ruta: Path, nombre: str, *, ref: str = "") -> str:
    """git pull y su [instalar] de nuevo; uno de un catálogo (con `ref`), a la versión que diga ahora (`ref`)."""
    instalados = leer_instalados(ruta)
    d = instalados.get(nombre)
    if d is None:
        raise ErrorDeModulo(f"«{nombre}» no lo instaló telar modulo")
    carpeta = Path(d["carpeta"])
    antes = d.get("version", "")
    # lo que pedía: lo anotado al instalarlo (o en la última actualización), que es lo que se vio. Uno anotado
    # por un telar de antes no lo tiene: vale el manifiesto de antes del pull (en uno enlazado no hay pull, y
    # entonces no hay con qué comparar hasta la próxima vez)
    pedia = d.get("pide")
    if not (isinstance(pedia, list) and all(isinstance(x, str) for x in pedia)):
        try:
            pedia = leer(nombre, carpeta).pide
        except ErrorDeModulo:
            pedia = None  # el de antes no se leía: no hay con qué comparar
    if not d.get("enlazado") and (ref or d.get("ref")):
        # de un catálogo: a esa etiqueta o commit, no a la punta de la rama
        objetivo = ref or d["ref"]
        f = _git(carpeta, "fetch", "-q", "--tags", "origin")
        if f.returncode != 0:
            raise ErrorDeModulo(f"git fetch en {carpeta}: {(f.stderr or f.stdout).strip()[-300:]}")
        c = _git(carpeta, "checkout", "-q", objetivo)
        if c.returncode != 0:
            _git(carpeta, "fetch", "-q", "--unshallow")
            c = _git(carpeta, "checkout", "-q", objetivo)
            if c.returncode != 0:
                raise ErrorDeModulo(f"{nombre}: no encuentro «{objetivo}» en su repositorio")
        d = {**d, "ref": objetivo}
    elif not d.get("enlazado"):
        r = _git(carpeta, "pull", "-q", "--ff-only")
        if r.returncode != 0:
            raise ErrorDeModulo(f"git pull en {carpeta}: {(r.stderr or r.stdout).strip()[-300:]}")
    ahora = _git(carpeta, "rev-parse", "--short", "HEAD").stdout.strip()
    m = leer(nombre, carpeta)
    _correr_instalar(m, carpeta)
    instalados[nombre] = {**d, "version": ahora, "pide": m.pide}
    _escribir_instalados(ruta, instalados)
    linea = f"{nombre}: {antes} → {ahora}" if antes != ahora else f"{nombre}: ya estaba al día ({ahora})"
    if pedia is not None and pedia != m.pide:
        # no se pregunta (actualizar nunca preguntó), pero se dice: lo que pide ahora no es lo que se vio. Sale
        # después de su [instalar], que ya corrió con la versión nueva
        linea += "\n    lo que pide cambió: " + "; ".join(m.pide) + "\n    (antes: " + "; ".join(pedia) + ")"
    return linea


def quitar(ruta: Path, nombre: str) -> str:
    import shutil

    instalados = leer_instalados(ruta)
    d = instalados.pop(nombre, None)
    if d is None:
        raise ErrorDeModulo(f"«{nombre}» no lo instaló telar modulo")
    _escribir_instalados(ruta, instalados)
    carpeta = Path(d["carpeta"])
    if not d.get("enlazado") and carpeta.is_relative_to(_datos()) and carpeta.exists():
        shutil.rmtree(carpeta)
        return f"quitado {nombre} (y su carpeta {carpeta})"
    return f"quitado {nombre} (su carpeta {carpeta} queda: no la bajó telar)"
