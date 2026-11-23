"""Los hijos con rama propia: un hilo abre un hijo que trabaja en su worktree, en su rama, y después fusiona lo suyo.

Para tener varios agentes en funcionalidades distintas del mismo código sin que se pisen: cada funcionalidad la hace
un hijo en su carpeta y su rama, y el padre (el gestor) reparte, revisa y fusiona. Lo usa `telar hilo hijo --rama`,
`telar hilo fusionar` y `telar hilo descartar` (ordenes/hilo.py); el método, la skill `/ramas` (agente/skill.py).

    from telar import ramas
    lugar = ramas.crear(Path("~/trabajo/proyectos/faro"), "Calendario")   # el worktree, desde la rama del padre
    ramas.pendientes(lugar)                                            # commits suyos que la base no tiene
    ramas.fusionar(lugar)                                              # en la carpeta donde está la base
    ramas.borrar(lugar)                                                # el worktree y la rama

- **Dónde**: `~/worktrees/<repo>-<rama>` (`CARPETA`), desde la rama en que está la carpeta del padre. El hijo
  trabaja en la misma subcarpeta que el padre (un proyecto dentro de un repositorio grande), pero en su copia.
- **Fusionar** prueba antes, sin tocar nada (`git merge-tree`): si choca, dice en qué archivos y la carpeta del padre
  queda como estaba. Si no, `git merge --no-ff` en la carpeta donde está la base (un commit de fusión por
  funcionalidad: se deshace entera con `git revert -m 1`). No sube: subir es del gestor, con las reglas de su repo.
- Lo que git no versiona (`node_modules`, un entorno de Python) no está en un worktree nuevo. Cada `node_modules`
  que la carpeta del padre tiene junto a un `package.json` versionado se enlaza en el worktree al crearlo
  (`enlazar_dependencias`): el hijo nace listo para compilar y probar.
- **Lo compilado** (un archivo que sale de un comando, que `.gitattributes` marca con `merge=telar-compilado`) no
  se resuelve a mano. Si la rama lo toca, o toca sus fuentes (`fuentes` de cada comando: una rama que cambió el CSS
  y no el compilado lo dejaría viejo en la base), `fusionar` hace la fusión en un árbol aparte, toma cualquiera de las
  dos versiones, lo vuelve a generar con lo que dice `.telar/compilados.yaml` y commitea la fusión con lo generado;
  la carpeta del padre solo avanza al final. Si choca algo más, se niega como siempre. En los worktrees de los hijos,
  un `git merge` de la base tampoco se detiene en ellos: el driver queda en una de las versiones (`preparar_driver`).
  `desfasados` es la red de `telar desplegar`: vuelve a generar lo de un commit aparte y dice qué salió distinto.
- **El CHANGELOG por fragmentos** (si el repositorio lo declara en `.telar/changelog.yaml`, telar.changelog): el hijo
  escribe su entrada en un archivo propio (`changelog.d/<rama>.md`), que no choca con nada, y `fusionar` la mueve a
  [Unreleased] y borra el fragmento, en el mismo commit de la fusión (en el árbol aparte, como lo compilado). Un
  fragmento mal formado se niega antes de tocar nada.

Se aplazó otra forma el 21-oct-2026 (un worktree para cada hilo: vivían semanas y su rama se alejaba de la
principal). Esta es para hijos de una funcionalidad, de horas o pocos días, que se fusionan y se borran.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from telar.git import _git

#: dónde van los worktrees de los hijos
CARPETA = Path("~/worktrees")

#: el driver de fusión de lo compilado: lo que `.gitattributes` pone en `merge=` a un archivo que sale de un comando
COMPILADO = "telar-compilado"
#: cómo se vuelve a generar lo compilado, en la raíz del repositorio
COMPILADOS = Path(".telar") / "compilados.yaml"
#: el archivo de configuración de git que define el driver, al lado del `config` del repositorio (lo incluye solo para
#: sus worktrees: `preparar_driver`)
DRIVER = "telar-compilados.gitconfig"
#: cuánto se espera a que un comando vuelva a generar lo compilado (segundos)
PLAZO_COMPILAR = 600


class ErrorDeRama(Exception):
    """Lo que no se pudo hacer con la rama de un hijo. El mensaje es para la persona; `archivos`, los que chocan o
    están sucios, si vienen al caso."""

    def __init__(self, mensaje: str, archivos: list[str] | None = None) -> None:
        super().__init__(mensaje)
        self.archivos = list(archivos or [])


def nombre_de_rama(hilo: str) -> str:
    """«Calendario nuevo» → `calendario-nuevo`: minúsculas, sin acentos, letras, números y guiones."""
    from telar.casilla import extension

    return extension(hilo) or "hijo"


def _salida(r) -> str:
    return (r.stderr or r.stdout or "").strip()[-400:]


def _lineas(texto: str) -> list[str]:
    return [l for l in texto.splitlines() if l.strip()]


def _repo(carpeta: Path) -> tuple[Path, Path]:
    """(la raíz de la copia de trabajo donde está `carpeta`, la carpeta del repositorio principal)."""
    r = _git(carpeta, "rev-parse", "--show-toplevel")
    if r.returncode != 0 or not r.stdout.strip():
        raise ErrorDeRama(f"{carpeta} no está en un repositorio git: un hijo con rama necesita uno")
    raiz = Path(r.stdout.strip())
    c = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    comun = Path(c.stdout.strip()) if c.returncode == 0 and c.stdout.strip() else raiz / ".git"
    return raiz, (comun.parent if comun.name == ".git" else comun)


def copias(repo: Path) -> dict[str, Path]:
    """rama → la carpeta donde está sacada (la principal y cada worktree), de `git worktree list`."""
    r = _git(repo, "worktree", "list", "--porcelain")
    salida, ruta = {}, None
    for linea in r.stdout.splitlines() if r.returncode == 0 else ():
        if linea.startswith("worktree "):
            ruta = Path(linea[len("worktree "):])
        elif linea.startswith("branch refs/heads/") and ruta is not None:
            salida[linea[len("branch refs/heads/"):]] = ruta
    return salida


def sucios(ruta: Path, *, solo_aqui: bool = False) -> list[str]:
    """Lo que hay sin commitear en esa copia (cambios y archivos nuevos; lo ignorado no cuenta), con su ruta desde la
    raíz del repositorio. Con `solo_aqui`, solo lo de esa carpeta para abajo."""
    r = _git(ruta, "status", "--porcelain", "--untracked-files=all", *(["--", "."] if solo_aqui else []))
    return [l[3:] for l in r.stdout.splitlines() if len(l) > 3] if r.returncode == 0 else []


def crear(carpeta_padre: Path | str, hijo: str, rama: str = "", *, carpeta: Path | str | None = None) -> dict:
    """El worktree del hijo: una rama nueva desde la que tiene sacada la carpeta del padre, en
    `<CARPETA>/<repo>-<rama>`, con los `node_modules` de la carpeta del padre enlazados. Devuelve su lugar, lo que se
    anota en el estado (`Estado.anotar_rama`): {ruta (el worktree), carpeta (donde trabaja el hijo: la misma subcarpeta
    que el padre), rama, base, repo, desde, creado, enlazados (los `node_modules` enlazados)}. ErrorDeRama si la carpeta no está en un repositorio, no está en una rama, o la rama o la carpeta ya existen."""
    padre = Path(carpeta_padre).expanduser().resolve()
    raiz, repo = _repo(padre)
    base = _git(raiz, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not base or base == "HEAD":
        raise ErrorDeRama(f"{raiz} no está en una rama (HEAD suelto): no sé de cuál sacar la del hijo")
    rama = (rama or nombre_de_rama(hijo)).strip()
    if _git(raiz, "check-ref-format", "--branch", rama).returncode != 0:
        raise ErrorDeRama(f"«{rama}» no sirve como nombre de rama")
    if _git(raiz, "rev-parse", "--verify", "--quiet", f"refs/heads/{rama}").returncode == 0:
        raise ErrorDeRama(f"ya existe la rama {rama}: dale otro nombre con --rama")
    donde = Path(carpeta).expanduser() if carpeta else CARPETA.expanduser()
    ruta = donde / f"{repo.name.lower()}-{rama.replace('/', '-')}"
    if ruta.exists():
        raise ErrorDeRama(f"ya existe {ruta}: dale otro nombre con --rama")
    donde.mkdir(parents=True, exist_ok=True)
    r = _git(raiz, "worktree", "add", "-q", "-b", rama, str(ruta), base)
    if r.returncode != 0:
        raise ErrorDeRama(f"git worktree add: {_salida(r)}")
    # que un `git merge` de la base en el worktree no se detenga en lo compilado (si el repositorio lo declara)
    preparar_driver(ruta)
    # y que nazca listo para compilar y probar: los node_modules de la carpeta del padre, enlazados
    enlazados = enlazar_dependencias(raiz, ruta)
    relativa = padre.relative_to(raiz.resolve()).as_posix() if padre != raiz.resolve() else ""
    return {"ruta": str(ruta), "carpeta": str(ruta / relativa) if relativa else str(ruta), "rama": rama, "base": base,
            "repo": str(repo), "desde": str(raiz), "creado": datetime.now().isoformat(timespec="seconds"),
            "enlazados": enlazados}


def _repo_de(lugar: dict) -> Path:
    """Una copia del repositorio que exista, para correr git: la principal, la del padre o la del hijo."""
    for clave in ("repo", "desde", "ruta"):
        p = Path(lugar.get(clave) or "")
        if str(p) not in ("", ".") and p.is_dir():
            return p
    raise ErrorDeRama(f"no encuentro el repositorio de la rama {lugar.get('rama', '')}: ¿se borró?")


def pendientes(lugar: dict) -> int:
    """Cuántos commits tiene la rama del hijo que su base no tiene (lo que falta fusionar); -1 si no se sabe."""
    try:
        repo = _repo_de(lugar)
    except ErrorDeRama:
        return -1
    r = _git(repo, "rev-list", "--count", f"{lugar['base']}..{lugar['rama']}")
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else -1


def chocaria(repo: Path, base: str, rama: str) -> list[str]:
    """Los archivos que chocarían al fusionar `rama` en `base`, probándolo sin tocar ninguna carpeta
    (`git merge-tree --write-tree`); [] si fusiona limpio."""
    r = _git(repo, "merge-tree", "--write-tree", "--name-only", "--no-messages", base, rama)
    if r.returncode == 0:
        return []
    if r.returncode == 1:
        # la primera línea es el árbol que resultaría; las siguientes, los archivos con choque
        return sorted(set(_lineas(r.stdout)[1:])) or ["(sin nombre)"]
    raise ErrorDeRama(f"git merge-tree: {_salida(r)}")


def compilados(carpeta: Path, archivos) -> list[str]:
    """De `archivos` (rutas desde la raíz del repositorio), los que su `.gitattributes` marca como compilados
    (`merge=telar-compilado`), según la copia de trabajo `carpeta` (su raíz)."""
    archivos = [a for a in archivos if a]
    if not archivos:
        return []
    try:
        r = subprocess.run(["git", "-C", str(carpeta), "check-attr", "--stdin", "-z", "merge"], input="\0".join(archivos) + "\0",
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    partes = r.stdout.split("\0") if r.returncode == 0 else []
    # de a tres: la ruta, el atributo y su valor
    return sorted({partes[i] for i in range(0, len(partes) - 2, 3) if partes[i + 2] == COMPILADO})


def comandos(raiz: Path) -> list[dict]:
    """Cómo se vuelve a generar lo compilado, de `.telar/compilados.yaml` en la raíz `raiz`: [{carpeta, comando,
    fuentes}], en orden (la carpeta, desde la raíz del repositorio; `fuentes`, los globs de lo que lee, [] si no las
    dice). [] si no está. ErrorDeRama si está y no se entiende.

        comandos:
          - carpeta: pagina
            comando: npm run navegador
            fuentes: [pagina/src/, pagina/media/]
    """
    ruta = Path(raiz) / COMPILADOS
    if not ruta.is_file():
        return []
    import yaml

    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ErrorDeRama(f"{COMPILADOS}: no lo entiendo ({e})") from None
    lista = datos.get("comandos") if isinstance(datos, dict) else None
    if not isinstance(lista, list) or not lista:
        raise ErrorDeRama(f"{COMPILADOS}: falta `comandos`, una lista de {{carpeta, comando}}")
    salida = []
    for c in lista:
        comando = str(c.get("comando") or "").strip() if isinstance(c, dict) else ""
        if not comando:
            raise ErrorDeRama(f"{COMPILADOS}: cada uno de `comandos` lleva su `comando`")
        carpeta = str(c.get("carpeta") or ".").strip() or "."
        if Path(carpeta).is_absolute() or ".." in Path(carpeta).parts:
            raise ErrorDeRama(f"{COMPILADOS}: la carpeta «{carpeta}» tiene que estar dentro del repositorio")
        fuentes = c.get("fuentes")
        if isinstance(fuentes, str):
            fuentes = [fuentes]
        if fuentes is None:
            fuentes = []
        if not isinstance(fuentes, list) or not all(isinstance(f, str) and f.strip() for f in fuentes):
            raise ErrorDeRama(f"{COMPILADOS}: `fuentes` es una lista de rutas (globs desde la raíz; `x/`, todo lo de "
                              f"adentro)")
        salida.append({"carpeta": carpeta, "comando": comando, "fuentes": [f.strip() for f in fuentes]})
    return salida


def calza(globs, archivos) -> bool:
    """Si alguno de `archivos` (rutas desde la raíz) calza con `globs`: `*` cruza carpetas y `x/` es todo lo de
    adentro (como `si_cambia` de `.telar/despliegue.yaml`)."""
    import fnmatch

    return any((g.endswith("/") and a.startswith(g)) or fnmatch.fnmatchcase(a, g) for g in globs for a in archivos)


def a_regenerar(lista: list[dict], cambia, tocados) -> list[dict]:
    """De los comandos de `.telar/compilados.yaml` (`comandos`), los que hay que correr si cambian los archivos
    `cambia` y de ellos `tocados` son compilados: todos si se toca lo compilado (no se sabe de qué comando sale cada
    uno); si no, los que tienen alguna de sus `fuentes` en `cambia`. `cambia` None es «todo cambió»."""
    if cambia is None or tocados:
        return list(lista)
    cambia = sorted(cambia)
    return [c for c in lista if c.get("fuentes") and calza(c["fuentes"], cambia)]


def enlazar_dependencias(desde: Path, hacia: Path) -> list[str]:
    """En la copia `hacia` (la raíz de un worktree), un enlace a cada `node_modules` que tiene la copia `desde` junto a
    un `package.json` versionado: lo que git no versiona no llega a un worktree nuevo, y sin eso no se compila ni se
    prueba. Solo donde `hacia` no tiene uno. Si git no ignora el enlace (un `node_modules/` con barra no ignora un
    enlace), se ignora en `info/exclude` del repositorio: si no, quedaría como un cambio sin commitear. Devuelve lo
    enlazado, desde la raíz de `hacia`."""
    desde, hacia = Path(desde), Path(hacia)
    r = _git(hacia, "ls-files", "-z", "--", "*package.json")
    hechos = []
    for rel in r.stdout.split("\0") if r.returncode == 0 else []:
        carpeta = Path(rel).parent
        if Path(rel).name != "package.json" or "node_modules" in carpeta.parts:
            continue
        origen, enlace = desde / carpeta / "node_modules", hacia / carpeta / "node_modules"
        if not origen.is_dir() or enlace.exists() or enlace.is_symlink() or not enlace.parent.is_dir():
            continue
        try:
            enlace.symlink_to(origen.resolve(), target_is_directory=True)
        except OSError:
            continue
        relativa = (carpeta / "node_modules").as_posix()
        if _git(hacia, "check-ignore", "-q", relativa).returncode != 0:
            _ignorar(hacia, relativa)
        hechos.append(relativa)
    return hechos


def _ignorar(copia: Path, relativa: str) -> None:
    """Agrega `/<relativa>` a `info/exclude` del repositorio (común a sus worktrees), si no está."""
    c = _git(copia, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if c.returncode != 0 or not c.stdout.strip():
        return
    exclude = Path(c.stdout.strip()) / "info" / "exclude"
    linea = f"/{relativa}"
    try:
        actual = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
        if linea not in actual.splitlines():
            exclude.parent.mkdir(parents=True, exist_ok=True)
            exclude.write_text(actual + ("" if not actual or actual.endswith("\n") else "\n")
                               + f"# un enlace de telar (telar.ramas): lo de la carpeta principal, en los worktrees\n{linea}\n",
                               encoding="utf-8")
    except OSError:
        pass


#: lo que define el driver de lo compilado, en el archivo que incluyen solo los worktrees (`preparar_driver`)
TEXTO_DRIVER = (f"# telar (telar.ramas): en los worktrees de los hijos, un compilado que choca al fusionar queda en la\n"
                f"# versión de la rama donde se fusiona, y se vuelve a generar después (`telar hilo fusionar` lo hace solo)\n"
                f'[merge "{COMPILADO}"]\n\tname = compilado: queda una versión y se vuelve a generar\n\tdriver = true\n')


def preparar_driver(repo: Path) -> bool:
    """Que en los worktrees de este repositorio (los de los hijos) un `git merge` de la base no se detenga en lo
    compilado: el driver `telar-compilado` deja la versión de la rama donde se fusiona, y lo compilado se vuelve a
    generar después (`fusionar` lo hace solo). Se define en un archivo aparte (`DRIVER`, al lado del `config` del
    repositorio) que el `config` incluye solo en sus worktrees (`includeIf "gitdir:<.git>/worktrees/"`): en la carpeta
    principal un `git merge` o un `git pull` sigue chocando en lo compilado, como siempre, y no queda un compilado viejo
    sin que nadie lo vea. Solo si el repositorio dice cómo volver a generarlo (`.telar/compilados.yaml`). Devuelve si
    quedó puesto."""
    raiz = _git(repo, "rev-parse", "--show-toplevel").stdout.strip()
    if not raiz or not (Path(raiz) / COMPILADOS).is_file():
        return False
    c = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if c.returncode != 0 or not c.stdout.strip():
        return False
    comun = Path(c.stdout.strip())
    try:
        archivo = comun / DRIVER
        if not archivo.is_file() or archivo.read_text(encoding="utf-8") != TEXTO_DRIVER:
            archivo.write_text(TEXTO_DRIVER, encoding="utf-8")
    except OSError:
        return False
    # la ruta real y la dicha, si difieren (un /tmp que es un enlace): git compara la de su carpeta con cualquiera
    for ruta in dict.fromkeys((comun.resolve(), comun)):
        clave = f"includeIf.gitdir:{ruta.as_posix().rstrip('/')}/worktrees/.path"
        if _git(repo, "config", "--file", str(comun / "config"), "--get", clave).stdout.strip() != DRIVER:
            if _git(repo, "config", "--file", str(comun / "config"), clave, DRIVER).returncode != 0:
                return False
    return True


def _arbol_fusionado(repo: Path, base: str, rama: str) -> str:
    """El árbol que dejaría fusionar `rama` en `base`, sin tocar ninguna carpeta (`git merge-tree --write-tree`); si
    choca, con las marcas del choque en lo que choca."""
    r = _git(repo, "merge-tree", "--write-tree", "--no-messages", base, rama)
    if r.returncode in (0, 1) and r.stdout.strip():
        return _lineas(r.stdout)[0]
    raise ErrorDeRama(f"git merge-tree: {_salida(r)}")


def fragmentos(repo: Path, arbol: str) -> tuple[dict | None, list[dict]]:
    """El CHANGELOG por fragmentos en el árbol `arbol` (lo que quedaría al fusionar): (su declaración, de
    `.telar/changelog.yaml`, o None si el repositorio no lo declara; los fragmentos que hay, ya leídos, en orden:
    [{ruta, entradas: {sección: [líneas]}}]). ErrorDeRama si la declaración o un fragmento están mal, con cada
    problema en `archivos`."""
    from telar import changelog

    def leer(ruta: str) -> str | None:
        r = _git(repo, "cat-file", "-p", f"{arbol}:{ruta}")
        return r.stdout if r.returncode == 0 else None

    try:
        decl = changelog.declaracion(leer(changelog.DECLARACION.as_posix()))
    except changelog.ErrorDeChangelog as e:
        raise ErrorDeRama(str(e)) from None
    if decl is None:
        return None, []
    if _git(repo, "cat-file", "-e", f"{arbol}:{decl['archivo']}").returncode != 0:
        raise ErrorDeRama(f"{changelog.DECLARACION} dice que el CHANGELOG es {decl['archivo']}, y no está")
    r = _git(repo, "ls-tree", "-z", "--name-only", arbol, "--", decl["carpeta"] + "/")
    rutas = sorted(p for p in r.stdout.split("\0") if p and changelog.es_fragmento(p, decl))
    salida, errores = [], []
    for ruta in rutas:
        try:
            salida.append({"ruta": ruta, "entradas": changelog.leer_fragmento(leer(ruta) or "", ruta, decl)})
        except changelog.ErrorDeChangelog as e:
            errores += e.errores
    if errores:
        raise ErrorDeRama(f"el fragmento del CHANGELOG está mal formado, y no fusioné: nada cambió. Que el hijo lo "
                          f"arregle en su worktree y lo commitee (cómo es un fragmento: {decl['carpeta']}/README.md o "
                          f"docs/perfil.md de telar, «El CHANGELOG por fragmentos»)", errores)
    return decl, salida


def fusionar(lugar: dict, *, mensaje: str = "", con_cambios: bool = False) -> dict:
    """Fusiona la rama del hijo en su base, en la carpeta donde está sacada la base. Antes comprueba, y si algo
    falla no toca nada: que el hijo no tenga cambios sin commitear (salvo `con_cambios`: sigue trabajando, y se
    fusiona lo commiteado), que la base esté sacada en alguna carpeta, que lo sucio de esa carpeta no sea algo que la
    fusión cambia, y que no choque más que en lo compilado.

    Si la rama toca lo compilado (`compilados`) o sus fuentes (`a_regenerar`) y el repositorio dice cómo volver a
    generarlo (`comandos`), la fusión se hace en un árbol aparte: lo compilado queda en una de sus versiones, se
    vuelve a generar y la fusión se commitea con lo generado; la carpeta del padre solo avanza al final, hasta ese
    commit. Así un choque que es solo de lo compilado no le vuelve al hijo, y lo que llega a la base está compilado de
    lo fusionado.

    Si el repositorio junta el CHANGELOG por fragmentos (`fragmentos`), lo mismo: en el árbol aparte, cada fragmento
    pasa a [Unreleased] y se borra, y eso va en el commit de la fusión. Un fragmento mal formado se niega antes.

    {commits, destino, base, rama, commit (el de la fusión; "" si no había nada), regenerados (lo compilado que se
    volvió a generar), changelog (None si el repositorio no lo junta por fragmentos; si no, {archivo, carpeta,
    fragmentos: los que se juntaron, [] si la rama no traía, secciones: las que recibieron entradas})}."""
    repo, base, rama = _repo_de(lugar), lugar["base"], lugar["rama"]
    if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{rama}").returncode != 0:
        raise ErrorDeRama(f"la rama {rama} ya no existe")
    hijo = Path(lugar.get("ruta") or "")
    if not con_cambios and hijo.is_dir():
        sucio = sucios(hijo)
        if sucio:
            raise ErrorDeRama(f"el hijo tiene cambios sin commitear en {hijo}: que los commitee (o descártalos)", sucio)
    n = pendientes(lugar)
    destino = copias(repo).get(base)
    if n == 0:
        return {"commits": 0, "destino": str(destino or ""), "base": base, "rama": rama, "commit": "",
                "regenerados": [], "changelog": None}
    if destino is None:
        raise ErrorDeRama(f"la rama {base} no está sacada en ninguna carpeta: no tengo dónde fusionar")
    cambia = set(_lineas(_git(repo, "diff", "--name-only", f"{base}...{rama}").stdout))
    tocados = set(compilados(destino, sorted(cambia)))
    chocan = chocaria(repo, base, rama)
    reales = [f for f in chocan if f not in tocados]
    if reales:
        solos = " (lo compilado que también choca se resuelve solo al fusionar)" if len(reales) < len(chocan) else ""
        raise ErrorDeRama(f"la rama {rama} choca con {base}: nada cambió en {destino}. Que se resuelva en el worktree "
                          f"del hijo ({hijo}): `git merge {base}` ahí, resolver y commitear; después se vuelve a fusionar"
                          + solos, reales)
    # lo compilado se vuelve a generar si la rama lo toca o toca sus fuentes (`fuentes` de cada comando): si cambió
    # solo la fuente, lo compilado de la rama quedó viejo, y llegaría así a la base
    regenerar = a_regenerar(comandos(destino), cambia, tocados)
    if chocan and not regenerar:
        raise ErrorDeRama(f"la rama {rama} choca con {base} solo en lo compilado, pero el repositorio no dice cómo volver "
                          f"a generarlo ({COMPILADOS}): nada cambió en {destino}. Que el hijo haga `git merge {base}`, "
                          f"tome cualquiera de las dos versiones y lo vuelva a generar", chocan)
    # después de los choques: un fragmento que choca se leería con las marcas del choque
    decl, juntar = fragmentos(repo, _arbol_fusionado(repo, base, rama))
    if juntar:
        cambia |= {decl["archivo"], *(f["ruta"] for f in juntar)}
    pisaria = sorted(cambia & set(sucios(destino)))
    if pisaria:
        raise ErrorDeRama(f"en {destino} hay cambios sin commitear en archivos que la fusión cambia: commitéalos antes",
                          pisaria)
    cl = None if decl is None else {
        "archivo": decl["archivo"], "carpeta": decl["carpeta"], "fragmentos": [f["ruta"] for f in juntar],
        "secciones": [s for s in decl["secciones"] if any(s in f["entradas"] for f in juntar)]}
    if regenerar or juntar:
        commit, regenerados = _fusionar_aparte(repo, Path(destino), base, rama, mensaje, regenerar, decl, juntar)
        return {"commits": n, "destino": str(destino), "base": base, "rama": rama, "commit": commit,
                "regenerados": regenerados, "changelog": cl}
    r = _git(destino, "merge", "--no-ff", "--no-edit", *(["-m", mensaje] if mensaje else []), rama, timeout=180)
    if r.returncode != 0:
        if _git(destino, "rev-parse", "--verify", "--quiet", "MERGE_HEAD").returncode == 0:
            _git(destino, "merge", "--abort")
        raise ErrorDeRama(f"git merge en {destino}: {_salida(r)}")
    commit = _git(destino, "rev-parse", "--short", "HEAD").stdout.strip()
    return {"commits": n, "destino": str(destino), "base": base, "rama": rama, "commit": commit, "regenerados": [],
            "changelog": cl}


def _fusionar_aparte(repo: Path, destino: Path, base: str, rama: str, mensaje: str, regenerar: list[dict],
                     decl: dict | None = None, juntar: list[dict] = ()) -> tuple[str, list[str]]:
    """La fusión con lo compilado vuelto a generar y los fragmentos del CHANGELOG juntados, en un worktree temporal
    desde la punta de la base: fusiona sin commitear (lo compilado que choca queda en la versión de la base), corre
    cada comando de `regenerar`, agrega lo compilado que cambió, pasa cada fragmento de `juntar` al CHANGELOG que
    dice `decl` y lo borra, y commitea; después la base avanza en `destino` hasta ese commit (`--ff-only`: si se movió
    entretanto, no se toca nada). El árbol temporal se borra siempre. (commit corto, lo regenerado)."""
    # aquí y no arriba: el contexto de cada sesión (telar.ordenes.agente) importa este módulo, y un gancho no carga
    # lo que no usa
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="telar-fusion-"))
    arbol = tmp / "arbol"
    try:
        punta = _git(destino, "rev-parse", "HEAD").stdout.strip()
        r = _git(repo, "worktree", "add", "-q", "--detach", str(arbol), punta)
        if r.returncode != 0:
            raise ErrorDeRama(f"git worktree add (el árbol aparte para fusionar): {_salida(r)}")
        enlazar_dependencias(destino, arbol)
        mensaje = mensaje or f"Merge branch '{rama}'" + ("" if base in ("main", "master") else f" into {base}")
        r = _git(arbol, "-c", f"merge.{COMPILADO}.driver=true", "merge", "--no-ff", "--no-commit", "-m", mensaje, rama,
                 timeout=180)
        if r.returncode != 0:
            raise ErrorDeRama(f"la fusión en el árbol aparte no salió limpia: nada cambió en {destino} ({_salida(r)})",
                              _lineas(_git(arbol, "diff", "--name-only", "--diff-filter=U").stdout))
        regenerados = _regenerar(arbol, regenerar, f"Nada cambió en {destino}")
        if regenerados:
            _git(arbol, "add", "--", *regenerados)
        if juntar:
            from telar import changelog

            ruta = arbol / decl["archivo"]
            ruta.write_text(changelog.juntar(ruta.read_text(encoding="utf-8"), [f["entradas"] for f in juntar], decl),
                            encoding="utf-8")
            r = _git(arbol, "rm", "-q", "-f", "--", *(f["ruta"] for f in juntar))
            if r.returncode != 0:
                raise ErrorDeRama(f"git rm de los fragmentos del CHANGELOG: {_salida(r)}. Nada cambió en {destino}")
            _git(arbol, "add", "--", decl["archivo"])
        r = _git(arbol, "commit", "-q", "--no-edit", "--no-verify", timeout=120)
        if r.returncode != 0:
            raise ErrorDeRama(f"git commit en el árbol aparte: {_salida(r)}")
        commit = _git(arbol, "rev-parse", "HEAD").stdout.strip()
        r = _git(destino, "merge", "--ff-only", "-q", commit, timeout=180)
        if r.returncode != 0:
            raise ErrorDeRama(f"{base} no pudo avanzar en {destino} hasta la fusión (¿se movió mientras?): nada cambió. "
                              f"{_salida(r)}")
        return _git(destino, "rev-parse", "--short", "HEAD").stdout.strip(), regenerados
    finally:
        if arbol.exists():
            _git(repo, "worktree", "remove", "--force", str(arbol))
        shutil.rmtree(tmp, ignore_errors=True)
        _git(repo, "worktree", "prune")


def _regenerar(arbol: Path, regenerar: list[dict], nada: str) -> list[str]:
    """Corre cada comando de `regenerar` en la copia `arbol` y devuelve lo compilado que quedó distinto de lo que
    tiene su índice. ErrorDeRama (con `nada`, lo que no se tocó) si uno no corre o falla."""
    import shlex

    for c in regenerar:
        try:
            p = subprocess.run(shlex.split(c["comando"]), cwd=arbol / c["carpeta"], capture_output=True, text=True,
                               timeout=PLAZO_COMPILAR)
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            raise ErrorDeRama(f"no pude volver a generar lo compilado («{c['comando']}» en {c['carpeta']}): {e}. "
                              f"{nada}") from None
        if p.returncode != 0:
            raise ErrorDeRama(f"«{c['comando']}» falló al volver a generar lo compilado (en {c['carpeta']}): "
                              f"{nada[:1].lower() + nada[1:]}. {_salida(p)}")
    return compilados(arbol, _lineas(_git(arbol, "diff", "--name-only").stdout))


def desfasados(repo: Path, commit: str = "HEAD", cambia=None) -> list[str] | None:
    """Lo compilado del `commit` que no corresponde a sus fuentes: lo vuelve a generar en un worktree temporal de ese
    commit (con los `node_modules` de `repo` enlazados) y devuelve lo que salió distinto ([] si está al día). Solo
    los comandos que tocan `cambia` (lo que cambió desde lo que ya se sabe bueno; None, todos: `a_regenerar`).
    None si el repositorio no dice cómo generarlo o nada de `cambia` es fuente ni compilado. ErrorDeRama si un
    comando falla. Lo usa `telar desplegar` como red: lo compilado viaja tal cual está commiteado."""
    import shutil
    import tempfile

    repo = Path(repo)
    lista = comandos(repo)
    if not lista:
        return None
    regenerar = a_regenerar(lista, cambia, None if cambia is None else compilados(repo, sorted(cambia)))
    if not regenerar:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="telar-compilados-"))
    arbol = tmp / "arbol"
    try:
        r = _git(repo, "worktree", "add", "-q", "--detach", str(arbol), commit)
        if r.returncode != 0:
            raise ErrorDeRama(f"git worktree add (el árbol aparte para comprobar lo compilado): {_salida(r)}")
        enlazar_dependencias(repo, arbol)
        return _regenerar(arbol, regenerar, "No toqué nada")
    finally:
        if arbol.exists():
            _git(repo, "worktree", "remove", "--force", str(arbol))
        shutil.rmtree(tmp, ignore_errors=True)
        _git(repo, "worktree", "prune")


def comprobar_borrar(lugar: dict) -> None:
    """ErrorDeRama si borrar el worktree perdería algo: cambios sin commitear o commits sin fusionar en su base."""
    rama, ruta = lugar["rama"], Path(lugar.get("ruta") or "")
    if ruta.is_dir():
        sucio = sucios(ruta)
        if sucio:
            raise ErrorDeRama(f"hay cambios sin commitear en {ruta}: --forzar los pierde", sucio)
    n = pendientes(lugar)
    if n > 0:
        raise ErrorDeRama(f"la rama {rama} tiene {n} commit(s) sin fusionar en {lugar['base']}: telar hilo fusionar, "
                          f"o --forzar los pierde")


def borrar(lugar: dict, *, forzar: bool = False) -> str:
    """Borra el worktree del hijo y su rama. Sin `forzar`, se niega si perdería algo (`comprobar_borrar`) y no borra
    nada. Devuelve qué hizo."""
    repo, rama, ruta = _repo_de(lugar), lugar["rama"], Path(lugar.get("ruta") or "")
    if not forzar:
        comprobar_borrar(lugar)
    if ruta.is_dir():
        r = _git(repo, "worktree", "remove", *(["--force"] if forzar else []), str(ruta))
        if r.returncode != 0:
            raise ErrorDeRama(f"git worktree remove: {_salida(r)}")
    _git(repo, "worktree", "prune")
    if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{rama}").returncode == 0:
        # -D: que no quede nada sin fusionar ya se comprobó (o se pidió perderlo); -d miraría la rama sacada aquí
        b = _git(repo, "branch", "-D", rama)
        if b.returncode != 0:
            raise ErrorDeRama(f"git branch -D {rama}: {_salida(b)}")
    return f"borrados el worktree {ruta} y la rama {rama}"
