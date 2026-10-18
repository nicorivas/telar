"""Escribir en git sin pisar a nadie: commitear solo unas rutas y subirlas.

Varios escriben en un mismo árbol de trabajo (hilos, agentes, periódicos, una CLI de tareas), cada uno
con cosas a medio hacer. Lo que aquí se hace parte de eso:

- **Commitear solo las rutas que se dan.** `git add -- rutas` primero, porque `commit -- rutas`
  deja fuera los archivos nuevos; después `commit -- rutas`, que commitea solo esas aunque el índice
  tenga otras cosas. Nunca `git add -A` sin rutas, y las rutas marcadas `skip-worktree` no se tocan:
  un `add` sobre ellas las borra del repositorio si no existen en el disco (pasa en un sistema de
  archivos que no acepta sus nombres).
- **Integrar sin pisar lo ajeno.** Si lo que llega del remoto toca un archivo sin commitear de aquí
  (de otro), no se integra y se dice. Si no lo toca, se rebasa: el autostash entonces no puede chocar,
  porque nada de lo guardado cambió allá. Si el rebase choca con lo propio, se aborta y el commit
  queda local.
- **Reintentar las carreras.** Un push que falla porque otro subió en el mismo segundo («is at … but
  expected …», «fetch first») se reintenta con espera, trayendo e integrando antes de cada intento.
- **De a uno por repositorio** (un candado en el directorio común de git, que comparten los worktrees),
  y **un registro único**: `<estado>/commits.log`, una línea JSON por intento.
"""

from __future__ import annotations

import fcntl
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


@dataclass(slots=True)
class Resultado:
    """Lo que pasó, para quien llamó y para el registro."""

    repo: str = ""
    rama: str = ""
    rutas: list[str] = field(default_factory=list)
    commit: str = ""          # el hash nuevo, o vacío si no había nada que commitear
    subido: bool = False
    intentos: int = 0
    estado: str = ""          # commiteado | subido | nada | choque | fallo
    detalle: str = ""

    def json(self) -> dict:
        return asdict(self)


def _git(repo: Path, *args: str, timeout: float = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(e.cmd, 124, "", f"git no respondió en {timeout:.0f} s")


def repositorio(ruta: Path) -> Path | None:
    """La raíz del repositorio (o del worktree) donde está `ruta`."""
    carpeta = ruta if ruta.is_dir() else ruta.parent
    while not carpeta.exists() and carpeta != carpeta.parent:
        carpeta = carpeta.parent
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


def commitear(rutas: list[Path], mensaje: str, *, repo: Path | None = None) -> Resultado:
    """Commitea solo `rutas` (las nuevas incluidas, las borradas como borradas)."""
    repo = repo or repositorio(rutas[0])
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
    r = _git(repo, "add", "-A", "--", *rel, *excluir)
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


def _integrar(repo: Path, arriba: str) -> tuple[bool, str]:
    """Trae `arriba` y rebasa encima, sin tocar lo ajeno. (True, "") si quedó al día."""
    remoto, _, rama = arriba.partition("/")
    f = _git(repo, "fetch", "-q", remoto, rama, timeout=30)
    if f.returncode != 0:
        return False, f"fetch: {(f.stderr or f.stdout).strip()[-200:]}"
    atras = _git(repo, "rev-list", "--count", f"HEAD..{arriba}").stdout.strip()
    if atras in ("", "0"):
        return True, ""
    llegan = set(_git(repo, "diff", "--name-only", f"HEAD...{arriba}").stdout.split("\n")) - {""}
    choques = llegan & _sucios(repo)
    if choques:
        return False, "lo que llega toca archivos sin commitear de aquí: " + ", ".join(sorted(choques))[:300]
    rb = _git(repo, "rebase", "-q", "--autostash", arriba, timeout=120)
    if rb.returncode != 0:
        _git(repo, "rebase", "--abort")
        return False, "el rebase chocó con lo propio; lo dejé como estaba: " + (rb.stderr or rb.stdout).strip()[-200:]
    return True, ""


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
    with open(_comun(repo) / "telar-subir.lock", "w") as candado:
        fcntl.flock(candado, fcntl.LOCK_EX)
        for i in range(len(esperas) + 1):
            res.intentos = i + 1
            ok, motivo = _integrar(repo, arriba)
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
