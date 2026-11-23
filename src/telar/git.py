"""Escribir en git sin pisar a nadie: commitear solo unas rutas y subirlas.

Varios escriben en un mismo árbol de trabajo (hilos, agentes, periódicos, una CLI de tareas), cada uno
con cosas a medio hacer. Lo que aquí se hace parte de eso:

- **Commitear solo las rutas que se dan.** `git add -- rutas` primero, porque `commit -- rutas`
  deja fuera los archivos nuevos; después `commit -- rutas`, que commitea solo esas aunque el índice
  tenga otras cosas. Nunca `git add -A` sin rutas, y las rutas marcadas `skip-worktree` no se tocan:
  un `add` sobre ellas las borra del repositorio si no existen en el disco (pasa en un sistema de
  archivos que no acepta sus nombres).
- **Integrar sin pisar lo ajeno.** Si lo que llega del remoto toca un archivo sin commitear de aquí
  (de otro), no se integra y se dice. Si no lo toca, se rebasa: lo sin commitear se aparta antes a un
  stash con una marca propia y se devuelve después, y no puede chocar, porque nada de lo apartado
  cambió allá. Si el rebase choca con lo propio, se aborta y el commit queda local.
- **Lo apartado vuelve, o se dice.** No con `rebase --autostash`: si no puede devolver lo que guardó,
  git lo deja en la lista de stash, lo avisa por stderr y sale con 0, y un `telar commit` lo daba por
  subido con los cambios de otros fuera del árbol. Le basta que otro proceso tenga tomado el
  `index.lock` en ese instante (cualquier `git status` de otro hilo lo toma). Aquí se devuelve con
  `stash apply`, reintentando mientras ninguno de esos archivos tenga cambios nuevos; si alguien
  escribió uno mientras tanto, o no hay caso, no se sube: el resultado es `apartado` y dice qué stash,
  qué archivos y cómo devolverlos.
- **Reintentar las carreras.** Un push que falla porque otro subió en el mismo segundo («is at … but
  expected …», «fetch first») se reintenta con espera, trayendo e integrando antes de cada intento.
- **De a uno por repositorio** (un candado en el directorio común de git, que comparten los worktrees),
  y **un registro único**: `<estado>/commits.log`, una línea JSON por intento. El candado es un `flock`
  sobre `telar-subir.lock`: el archivo queda siempre (borrarlo dejaría a dos con candados distintos), y
  el candado se suelta solo cuando el proceso lo cierra o termina.
"""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

__all__ = ["Resultado", "commitear", "subir", "repositorio", "anotar"]

#: lo que dice git cuando el push perdió una carrera (otro subió antes): se reintenta
CARRERA = ("fetch first", "non-fast-forward", "but expected", "stale info", "cannot lock ref",
           "failed to update ref", "rejected")
ESPERAS = (1.0, 3.0, 8.0)
#: entre los intentos de devolver lo apartado: lo que tarda otro en soltar el `index.lock`
ESPERAS_DEVOLVER = (0.2, 0.5, 1.0, 2.0)


@dataclass(slots=True)
class Resultado:
    """Lo que pasó, para quien llamó y para el registro."""

    repo: str = ""
    rama: str = ""
    rutas: list[str] = field(default_factory=list)
    commit: str = ""          # el hash nuevo, o vacío si no había nada que commitear
    subido: bool = False
    intentos: int = 0
    estado: str = ""          # commiteado | subido | nada | choque | apartado | fallo
    detalle: str = ""
    stash: str = ""           # con `apartado`: el stash donde quedó lo sin commitear de otros
    apartados: list[str] = field(default_factory=list)  # y sus archivos

    def json(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Apartado:
    """Lo sin commitear que se sacó del árbol para rebasar: el stash, sus archivos y, si no volvió, por qué."""

    oid: str
    archivos: list[str]
    error: str = ""
    pisados: list[str] = field(default_factory=list)  # los que alguien escribió mientras estaban afuera


def _git(repo: Path, *args: str, timeout: float = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(e.cmd, 124, "", f"git no respondió en {timeout:.0f} s")


def _error(r: subprocess.CompletedProcess, largo: int = 200) -> str:
    """Lo que dijo git al fallar, desde el principio (ahí dice qué pasó: el `index.lock` tomado, el conflicto), en
    una línea."""
    texto = " ".join(l.strip() for l in (r.stderr or r.stdout).splitlines() if l.strip() and l.strip() != "hint:")
    texto = texto or f"git salió con {r.returncode}"
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def repositorio(ruta: Path) -> Path | None:
    """La raíz del repositorio (o del worktree) donde está `ruta`."""
    try:
        carpeta = ruta if ruta.is_dir() else ruta.parent
        while not carpeta.exists() and carpeta != carpeta.parent:
            carpeta = carpeta.parent
    except OSError:  # un nombre imposible (demasiado largo): no es una ruta de ningún repositorio
        return None
    r = _git(carpeta, "rev-parse", "--show-toplevel")
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def _comun(repo: Path) -> Path:
    r = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(r.stdout.strip()) if r.returncode == 0 else repo / ".git"


def _ocultas(repo: Path) -> set[str]:
    """Las rutas marcadas skip-worktree (`git ls-files -v` las da con «S»)."""
    r = _git(repo, "ls-files", "-v")
    return {l[2:] for l in r.stdout.splitlines() if l[:1] == "S"} if r.returncode == 0 else set()


def _sucios(repo: Path) -> set[str]:
    r = _git(repo, "status", "--porcelain", "-z", "--untracked-files=all")
    sucios, partes = set(), r.stdout.split("\0")
    i = 0
    while i < len(partes):
        linea = partes[i]
        if len(linea) > 3:
            sucios.add(linea[3:])
            if linea[0] in "RC":  # un renombre trae la ruta vieja en la parte siguiente
                i += 1
                if i < len(partes) and partes[i]:
                    sucios.add(partes[i])
        i += 1
    return sucios


def _resuelta(ruta: Path) -> Path:
    """Resuelve la parte que existe de una ruta y le pega el resto."""
    resto: list[str] = []
    while not ruta.exists() and ruta != ruta.parent:
        resto.insert(0, ruta.name)
        ruta = ruta.parent
    return ruta.resolve().joinpath(*resto)


def _relativas(repo: Path, rutas: list[Path]) -> list[str]:
    salida = []
    for r in rutas:
        absoluta = r if r.is_absolute() else Path.cwd() / r
        # una ruta borrada no se puede resolver: se resuelve su carpeta (en macOS /var es /private/var)
        real = absoluta.resolve() if absoluta.exists() else _resuelta(absoluta)
        try:
            salida.append(os.path.relpath(real, repo.resolve()))
        except ValueError:
            salida.append(str(r))
    return salida


@contextmanager
def _de_a_uno(repo: Path):
    """El candado del repositorio: commitear y subir, de a uno. Dos cambios seguidos (dos acciones sobre
    tareas, cada una con su `telar commit` en segundo plano) chocaban en el `index.lock` de git, y uno
    quedaba sin commitear; y un commit en medio de un rebase lo rompe."""
    with open(_comun(repo) / "telar-subir.lock", "w") as candado:
        fcntl.flock(candado, fcntl.LOCK_EX)
        yield


def commitear(rutas: list[Path], mensaje: str, *, repo: Path | None = None) -> Resultado:
    """Commitea solo `rutas` (las nuevas incluidas, las borradas como borradas)."""
    repo = repo or repositorio(rutas[0])
    if repo is not None:
        with _de_a_uno(repo):
            return _commitear(rutas, mensaje, repo)
    return _commitear(rutas, mensaje, repo)


def _commitear(rutas: list[Path], mensaje: str, repo: Path | None) -> Resultado:
    res = Resultado(repo=str(repo or ""))
    if repo is None:
        res.estado, res.detalle = "fallo", f"{rutas[0]} no está en un repositorio git"
        return res
    rel = _relativas(repo, rutas)
    fuera = [r for r in rel if r.startswith("..")]
    if fuera:
        res.estado, res.detalle = "fallo", f"fuera del repositorio {repo}: {', '.join(fuera)}"
        return res
    ocultas = _ocultas(repo)
    res.rutas = rel
    excluir = [f":(exclude,literal){o}" for o in ocultas]
    # lo ya borrado del índice (`git rm`) no existe ni en el disco ni en el índice: `add` no lo
    # encuentra y falla, pero el commit sí lo lleva (está en HEAD)
    en_indice = set(_git(repo, "ls-files", "--", *rel).stdout.splitlines())
    para_add = [r for r in rel if (repo / r).exists() or (repo / r).is_symlink()
                or r in en_indice or any(i.startswith(r.rstrip("/") + "/") for i in en_indice)]
    r = _git(repo, "add", "-A", "--", *para_add, *excluir) if para_add else subprocess.CompletedProcess([], 0, "", "")
    if r.returncode != 0:
        res.estado, res.detalle = "fallo", (r.stderr or r.stdout).strip()[-300:]
        return res
    # ¿cambió algo de lo pedido? (`diff --cached` limitado a esas rutas)
    if _git(repo, "diff", "--cached", "--quiet", "--", *rel).returncode == 0:
        res.estado, res.detalle = "nada", "no hay cambios en esas rutas"
        return res
    r = _git(repo, "commit", "-q", "--no-verify", "-m", mensaje, "--", *rel, *excluir)
    if r.returncode != 0:
        res.estado, res.detalle = "fallo", (r.stderr or r.stdout).strip()[-300:]
        return res
    res.commit = _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    res.rama = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    res.estado = "commiteado"
    return res


def _stashes(repo: Path) -> list[tuple[str, str, str]]:
    """La lista de stash, de la más nueva a la más vieja: (`stash@{n}`, hash, asunto)."""
    r = _git(repo, "stash", "list", "--format=%gd%x09%H%x09%gs")
    return [tuple(l.split("\t", 2)) for l in r.stdout.splitlines() if l.count("\t") >= 2]  # type: ignore[misc]


def _apartar(repo: Path) -> tuple[Apartado | None, str]:
    """Saca del árbol lo sin commitear (lo rastreado: lo nuevo sin rastrear no estorba al rebase) a un stash
    con una marca propia, para saber cuál es aunque otro guarde uno en el mismo momento. (None, "") si no
    había nada; (None, por qué) si no se pudo."""
    marca = f"telar commit {os.getpid()}.{time.time_ns()}: lo sin commitear, apartado mientras se integra"
    antes = _git(repo, "rev-parse", "-q", "--verify", "refs/stash").stdout.strip()
    r = _git(repo, "stash", "push", "-q", "-m", marca)
    if r.returncode != 0:
        return None, "no pude apartar lo sin commitear para integrar: " + _error(r)
    oid = next((h for _, h, asunto in _stashes(repo) if asunto.endswith(marca)), "")
    if not oid:
        if _git(repo, "rev-parse", "-q", "--verify", "refs/stash").stdout.strip() == antes:
            return None, ""  # no había nada rastreado sin commitear
        return None, "apartar lo sin commitear dejó un stash que no reconozco; no integro (mira `git stash list`)"
    archivos = _git(repo, "diff", "--name-only", "-z", f"{oid}^1", oid).stdout.split("\0")
    return Apartado(oid=oid, archivos=[a for a in archivos if a]), ""


def _esperar(segundos: float) -> None:
    """La espera entre intentos de devolver y de abortar (las pruebas la cambian sin tocar `time.sleep`, que es de
    todo el proceso)."""
    time.sleep(segundos)


def _devolver(repo: Path, ap: Apartado, esperas: tuple[float, ...] | None = None) -> bool:
    """Devuelve lo apartado al árbol y bota su stash. Reintenta mientras ninguno de sus archivos tenga cambios
    nuevos: lo que falla entonces es el `index.lock` tomado por otro, que dura un instante. Si alguien escribió
    uno mientras estaba afuera, no hay caso: queda en `ap.pisados`. False si no volvió (`ap.error` dice por qué)."""
    esperas = ESPERAS_DEVOLVER if esperas is None else esperas
    for i in range(len(esperas) + 1):
        r = _git(repo, "stash", "apply", "-q", ap.oid)
        if r.returncode == 0:
            ap.error = ""
            ref = next((g for g, h, _ in _stashes(repo) if h == ap.oid), "")
            if ref:
                _git(repo, "stash", "drop", "-q", ref)
            return True
        ap.error = _error(r)
        ap.pisados = sorted(set(ap.archivos) & _sucios(repo))
        if ap.pisados or i == len(esperas):
            return False
        _esperar(esperas[i])
    return False


def _en_rebase(repo: Path) -> bool:
    for carpeta in ("rebase-merge", "rebase-apply"):
        r = _git(repo, "rev-parse", "--path-format=absolute", "--git-path", carpeta)
        if r.returncode == 0 and r.stdout.strip() and Path(r.stdout.strip()).exists():
            return True
    return False


def _abortar(repo: Path, esperas: tuple[float, ...] | None = None) -> str:
    """Deshace el rebase que no pasó. Reintenta si no se pudo (otro con el `index.lock`): un rebase a medias deja
    el HEAD suelto y nada más se puede subir. "" si quedó como antes; si no, por qué."""
    esperas = ESPERAS_DEVOLVER if esperas is None else esperas
    error = ""
    for i in range(len(esperas) + 1):
        r = _git(repo, "rebase", "--abort")
        if not _en_rebase(repo):
            return ""
        error = _error(r)
        if i < len(esperas):
            _esperar(esperas[i])
    return error


def _como_devolver(repo: Path, ap: Apartado) -> str:
    """Qué quedó afuera, dónde y cómo devolverlo, para quien lea el resultado."""
    ref = next((g for g, h, _ in _stashes(repo) if h == ap.oid), "") or ap.oid
    h = ap.oid[:10]
    nombres = ", ".join(ap.archivos[:8]) + (f" y {len(ap.archivos) - 8} más" if len(ap.archivos) > 8 else "")
    texto = (f"lo sin commitear de otros ({nombres}) quedó fuera del árbol, en {ref} ({h}), y no pude devolverlo"
             f" ({ap.error}). ")
    if ap.pisados:
        resto = [a for a in ap.archivos if a not in ap.pisados]
        texto += (f"Mientras estaba afuera alguien escribió {', '.join(ap.pisados)}: lo apartado de esos se ve con "
                  f"`git diff {h}^1 {h} -- <archivo>` y hay que juntarlo a mano"
                  + (f"; el resto vuelve con `git restore --source={h} -- {' '.join(resto)}`" if resto else "")
                  + f". Con todo de vuelta, `git stash drop {ref}`")
    else:
        texto += f"Devuélvelo con `git stash apply {h}` y, de vuelta, `git stash drop {ref}`"
    return texto + "; después, `telar commit --subir`."


def _integrar(repo: Path, arriba: str) -> tuple[bool, str, Apartado | None]:
    """Trae `arriba` y rebasa encima, sin tocar lo ajeno. (True, "", None) si quedó al día; el Apartado, si lo
    sin commitear de otros no pudo volver al árbol."""
    remoto, _, rama = arriba.partition("/")
    f = _git(repo, "fetch", "-q", remoto, rama, timeout=30)
    if f.returncode != 0:
        return False, f"fetch: {(f.stderr or f.stdout).strip()[-200:]}", None
    atras = _git(repo, "rev-list", "--count", f"HEAD..{arriba}").stdout.strip()
    if atras in ("", "0"):
        return True, "", None
    llegan = set(_git(repo, "diff", "--name-only", f"HEAD...{arriba}").stdout.split("\n")) - {""}
    choques = llegan & _sucios(repo)
    if choques:
        return False, "lo que llega toca archivos sin commitear de aquí: " + ", ".join(sorted(choques))[:300], None
    apartado, motivo = _apartar(repo)
    if motivo:
        return False, motivo, None
    rb = _git(repo, "rebase", "-q", "--no-autostash", arriba, timeout=120)
    if rb.returncode != 0:
        motivo = "el rebase no pasó; lo dejé como estaba: " + _error(rb)
        error = _abortar(repo)
        if error:  # devolver ahora sería perderlo: el `rebase --abort` de después hace un reset --hard
            motivo = f"el rebase quedó a medias y no pude abortarlo ({error}): primero, `git rebase --abort`"
            if apartado is not None:
                apartado.error = "el rebase quedó a medias"
            return False, motivo, apartado
    if apartado is not None and not _devolver(repo, apartado):
        return False, motivo, apartado
    return not motivo, motivo, None


def subir(res: Resultado, *, esperas: tuple[float, ...] = ESPERAS) -> Resultado:
    """Sube la rama actual a la suya de arriba, integrando y reintentando las carreras."""
    repo = Path(res.repo)
    arriba = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").stdout.strip()
    res.rama = res.rama or _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if res.rama == "HEAD":
        res.estado, res.detalle = "fallo", "no hay rama (HEAD suelto): no subo"
        return res
    if not arriba:
        res.estado, res.detalle = res.estado or "commiteado", "la rama no tiene una de arriba: queda local"
        return res
    remoto, _, rama_arriba = arriba.partition("/")
    with _de_a_uno(repo):
        for i in range(len(esperas) + 1):
            res.intentos = i + 1
            ok, motivo, apartado = _integrar(repo, arriba)
            if apartado is not None:  # lo de otros quedó afuera: no se sube, y se dice dónde quedó
                if res.commit and not motivo:  # se rebasó: el hash es otro
                    res.commit = _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
                res.estado, res.stash, res.apartados = "apartado", apartado.oid, apartado.archivos
                res.detalle = (motivo + "; " if motivo else "") + _como_devolver(repo, apartado)
                return res
            if not ok:
                res.estado, res.detalle = "choque", motivo
                return res
            if _git(repo, "rev-list", "--count", f"{arriba}..HEAD").stdout.strip() in ("", "0"):
                res.subido, res.estado = True, "subido"
                return res
            p = _git(repo, "push", "-q", remoto, f"HEAD:{rama_arriba}", timeout=60)
            if p.returncode == 0:
                res.subido, res.estado, res.detalle = True, "subido", ""
                if res.commit:  # el rebase le cambia el hash: el que vale es el que quedó arriba
                    res.commit = _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
                return res
            error = (p.stderr or p.stdout).strip()
            if not any(c in error for c in CARRERA):
                res.estado, res.detalle = "fallo", f"push: {error[-300:]}"
                return res
            res.detalle = f"push perdió una carrera: {error[-200:]}"
            if i < len(esperas):
                time.sleep(esperas[i])
    res.estado = "fallo"
    res.detalle = f"no pude subir en {res.intentos} intentos ({res.detalle})"
    return res


def anotar(estado: Path, res: Resultado, mensaje: str) -> None:
    """Una línea en `<estado>/commits.log`; si no se puede escribir, no es motivo para fallar."""
    try:
        estado.mkdir(parents=True, exist_ok=True)
        linea = {"fecha": datetime.now().isoformat(timespec="seconds"), "mensaje": mensaje.splitlines()[0][:120],
                 **res.json()}
        with open(estado / "commits.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except OSError:
        pass
