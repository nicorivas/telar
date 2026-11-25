"""Lo que un hilo tiene en sus repositorios y la otra máquina no, al llevarlo (docs/propuestas/mudanza-de-hilos.md,
etapa 2).

La conversación viaja (telar.replica); los archivos no. Antes de llevar un hilo se mira el repositorio de su carpeta
(el de la raíz, si no tiene) y los repositorios donde su conversación escribió, y de cada uno:

    del hilo        archivos sin commitear que su conversación escribió (Edit, Write, MultiEdit, NotebookEdit, también
                    sus subagentes): son suyos, y «subir y llevar» commitea solo esos y los sube
    en su carpeta   otros archivos sin commitear dentro de su carpeta: pueden ser de otro hilo o de un programa, así que
                    se muestran y no se suben
    sin subir       los commits de la rama que su rama de arriba no tiene: «subir y llevar» los sube
    allá            si la otra máquina tiene el último commit de aquí: si no, al llegar se trae de arriba

El resto del repositorio (lo que otros hilos tienen a medias en la raíz) no se mira: no es de este hilo y no lo
detiene. Si no se puede saber qué es suyo (nada lo dice su conversación), no se ofrece subir: se muestra y se puede
llevar igual.

    revisar(config, carpeta, archivo, sid)   de este lado, sin tocar nada: {repos: [...]}
    hay_algo(p)                              si hay que preguntar antes de llevarlo
    subir(config, p, hilo, maquina)          commitea lo del hilo de cada repositorio y sube (telar.git)
    en_destino(ctx, repos)                   del otro lado (`hilo-revisar`): si tiene el último commit de aquí
    al_dia(ctx, repos)                       del otro lado (`hilo-llegar`): trae lo que falta antes
                                             de abrir el hilo, o dice por qué no
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from telar import git, rutas

#: las herramientas de Claude Code que escriben un archivo, y dónde dicen cuál
ESCRIBEN = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
_MARCAS = tuple(f'"{n}"'.encode() for n in ESCRIBEN)
#: cuántos archivos o commits de cada lista se mandan para mostrar (la cuenta va entera)
TOPE = 40


def escritos(archivo: Path, sid: str = "") -> set[Path]:
    """Los archivos que escribió la conversación `archivo` (y sus subagentes, en `<sid>/subagents/`), como rutas de
    esta máquina (telar.rutas.de_aqui: la conversación pudo seguir en otra)."""
    conversaciones = [Path(archivo)]
    if sid:
        conversaciones += sorted((Path(archivo).parent / sid / "subagents").glob("*.jsonl"))
    salida: set[str] = set()
    for c in conversaciones:
        try:
            f = open(c, "rb")
        except OSError:
            continue
        with f:
            for linea in f:
                if b'"tool_use"' not in linea or not any(m in linea for m in _MARCAS):
                    continue
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                contenido = ((d.get("message") or {}) if isinstance(d, dict) else {}).get("content")
                for x in contenido if isinstance(contenido, list) else []:
                    if isinstance(x, dict) and x.get("type") == "tool_use" and x.get("name") in ESCRIBEN:
                        ruta = (x.get("input") or {}).get(ESCRIBEN[x["name"]])
                        if isinstance(ruta, str) and ruta.startswith("/"):
                            salida.add(ruta)
    return {rutas.de_aqui(r) for r in salida}


def _real(p: Path) -> Path:
    """La ruta real de `p`, aunque ya no exista (un archivo borrado): la de su carpeta, con su nombre."""
    try:
        return p.resolve() if p.exists() else _real(p.parent) / p.name if p.parent != p else p
    except OSError:
        return p


def _sucios(repo: Path) -> set[str]:
    """Lo sin commitear del repositorio, sin los repositorios de adentro (un `clientes/` sin rastrear se sincroniza por
    su cuenta)."""
    return {s for s in git._sucios(repo) if not (s.endswith("/") and (repo / s / ".git").exists())}


def _lineas(repo: Path, *args: str) -> list[str]:
    r = git._git(repo, *args)
    return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def _nombre(repo: Path, raiz: Path) -> str:
    """Cómo se le dice a la persona: relativo a la raíz, o al hogar, o absoluto."""
    for base, prefijo in ((raiz, ""), (Path.home().resolve(), "~/")):
        try:
            rel = repo.relative_to(base).as_posix()
            return prefijo + rel if rel != "." else (prefijo.rstrip("/") or base.name)
        except ValueError:
            continue
    return str(repo)


def revisar(config, carpeta: Path | None, archivo: Path | None, sid: str = "") -> dict:
    """Lo que el hilo tiene en sus repositorios y la otra máquina no tendría, sin tocar nada: {repos: [{repo, nombre,
    relativa, rama, arriba, commit, del_hilo, en_su_carpeta, commits, n_commits, puede_subir, por_que_no,
    pendiente}]}. El primero es el de su carpeta (o el de la raíz), aunque no tenga nada: la otra máquina mira si
    tiene su último commit. `relativa`, el repositorio bajo la raíz ("" si está fuera de ella: allá no se sabe dónde)."""
    raiz = Path(config.raiz).expanduser().resolve()
    carpeta = Path(carpeta).expanduser().resolve() if carpeta else None
    principal = git.repositorio(carpeta or raiz)
    principal = principal.resolve() if principal is not None else None
    suyos: dict[Path, set[str]] = {}
    repo_de: dict[Path, Path | None] = {}
    for p in escritos(archivo, sid) if archivo is not None else ():
        real = _real(p)
        d = real.parent
        if d not in repo_de:
            r = git.repositorio(d)
            repo_de[d] = r.resolve() if r is not None else None
        if repo_de[d] is not None:
            suyos.setdefault(repo_de[d], set()).add(os.path.relpath(real, repo_de[d]))
    repos = []
    for repo in dict.fromkeys([*([principal] if principal else []), *sorted(suyos)]):
        sucios = _sucios(repo)
        del_hilo = sorted(sucios & suyos.get(repo, set()))
        en_carpeta: list[str] = []
        if repo == principal and carpeta is not None and carpeta != raiz:
            rel = os.path.relpath(carpeta, repo)
            en_carpeta = sorted(s for s in sucios - set(del_hilo)
                                if rel == "." or s == rel or s.startswith(rel.rstrip("/") + "/"))
        rama = (_lineas(repo, "symbolic-ref", "--short", "-q", "HEAD") or [""])[0]  # "" con un HEAD suelto
        arriba = (_lineas(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or [""])[0]
        commit = (_lineas(repo, "rev-parse", "HEAD") or [""])[0]
        commits = _lineas(repo, "log", "--format=%h %s", f"{arriba}..HEAD") if arriba else []
        por_que_no = ("está en un HEAD suelto, sin rama" if not rama
                      else f"la rama {rama} no tiene una de arriba" if not arriba else "")
        try:
            relativa = repo.relative_to(raiz).as_posix()
        except ValueError:
            relativa = ""
        entrada = {"repo": str(repo), "nombre": _nombre(repo, raiz), "relativa": relativa, "rama": rama,
                   "arriba": arriba, "commit": commit, "del_hilo": del_hilo[:TOPE], "n_del_hilo": len(del_hilo),
                   "en_su_carpeta": en_carpeta[:TOPE], "n_en_su_carpeta": len(en_carpeta),
                   "commits": commits[:TOPE], "n_commits": len(commits),
                   "puede_subir": not por_que_no and bool(del_hilo or commits), "por_que_no": por_que_no}
        entrada["pendiente"] = bool(del_hilo or en_carpeta or commits)
        if repo == principal or entrada["pendiente"]:
            repos.append(entrada)
    return {"repos": repos}


def hay_algo(p: dict) -> bool:
    """Si hay algo sin subir que mostrar antes de llevarlo."""
    return any(r.get("pendiente") for r in p.get("repos") or [])


def se_puede_subir(p: dict) -> bool:
    """Si «subir y llevar» tiene algo que hacer: lo del hilo sin commitear o commits sin subir, en un repositorio
    con rama de arriba."""
    return any(r.get("puede_subir") for r in p.get("repos") or [])


def lineas(p: dict, destino: list | None = None, maquina: str = "") -> list[str]:
    """Lo que hay sin subir, para la terminal: una línea por cosa, con «·» delante (la página las reconoce)."""
    salida = []
    alla = {d.get("relativa"): d for d in destino or []}
    for r in p.get("repos") or []:
        n = r.get("nombre", "")
        del_hilo, en_carpeta = r.get("n_del_hilo", 0), r.get("n_en_su_carpeta", 0)
        if del_hilo:
            salida.append(f"· {n}: {del_hilo} archivo{'s' if del_hilo != 1 else ''} de este hilo sin commitear "
                          f"({', '.join(r['del_hilo'][:5])}{'…' if del_hilo > 5 else ''})")
        if en_carpeta:
            salida.append(f"· {n}: {en_carpeta}{' más' if del_hilo else ''} sin commitear en su carpeta, que no sé si "
                          f"son suyos ({', '.join(r['en_su_carpeta'][:5])}{'…' if en_carpeta > 5 else ''}): no los subo")
        if r.get("n_commits"):
            salida.append(f"· {n}: {r['n_commits']} commit{'s' if r['n_commits'] != 1 else ''} sin subir")
        if r.get("pendiente") and r.get("por_que_no"):
            salida.append(f"· {n}: no se puede subir: {r['por_que_no']}")
        d = alla.get(r.get("relativa"))
        if d and d.get("existe") and not d.get("tiene"):
            salida.append(f"· {n}: {maquina or 'allá'} va atrás (no tiene {str(r.get('commit'))[:7]}): al llegar se "
                          "trae de arriba")
    return salida


def subir(config, p: dict, hilo: str, maquina: str) -> tuple[bool, str]:
    """«Subir y llevar»: en cada repositorio, commitea solo lo del hilo (nunca lo demás) y sube la rama. (True, qué
    se subió) o (False, por qué no): si algo no sube, no se lleva, y lo commiteado queda aquí."""
    hechos, problemas = [], []
    for r in p.get("repos") or []:
        if not r.get("puede_subir"):
            continue
        repo = Path(r["repo"])
        if r["n_del_hilo"] > len(r["del_hilo"]):  # la lista se cortó para mostrarla: se vuelve a mirar entera
            r = {**r, "del_hilo": sorted(_sucios(repo) & set(r["del_hilo"]))}
        if r["del_hilo"]:
            mensaje = (f"{hilo}: lo suyo sin commitear, antes de llevarlo a {maquina}\n\n"
                       + "\n".join(f"- {a}" for a in r["del_hilo"]))
            res = git.commitear([repo / a for a in r["del_hilo"]], mensaje, repo=repo)
            git.anotar(Path(config.estado), res, mensaje)
            if res.estado == "fallo":
                problemas.append(f"{r['nombre']}: no pude commitear: {res.detalle}")
                continue
        else:
            res = git.Resultado(repo=str(repo), estado="nada")
        res = git.subir(res)
        git.anotar(Path(config.estado), res, f"{hilo}: subir antes de llevarlo a {maquina}")
        if res.estado != "subido":
            problemas.append(f"{r['nombre']}: no subió ({res.estado}): {res.detalle}"
                             + (f"; el commit {res.commit} quedó aquí" if res.commit else ""))
            continue
        n = len(r["del_hilo"])
        hechos.append(f"{r['nombre']}: " + (f"{n} archivo{'s' if n != 1 else ''} commiteado{'s' if n != 1 else ''}"
                                            f" ({res.commit}) y " if res.commit else "") + "subido")
    if problemas:
        return False, "; ".join(problemas)
    return True, "; ".join(hechos)


# ── del otro lado ──

def _de_aqui(ctx, relativa: str) -> Path | None:
    """El repositorio que allá es `relativa` bajo la raíz («.», la raíz misma), aquí; None si no hay uno."""
    if not relativa or relativa.startswith("/") or ".." in Path(relativa).parts:
        return None
    raiz = Path(ctx.config.raiz).expanduser()
    lugar = raiz / relativa if relativa != "." else raiz
    if not lugar.is_dir():
        return None
    repo = git.repositorio(lugar)
    return repo.resolve() if repo is not None and repo.resolve() == lugar.resolve() else None


def _tiene(repo: Path, commit: str) -> bool:
    """Si la rama de aquí ya contiene ese commit."""
    return bool(commit) and git._git(repo, "merge-base", "--is-ancestor", commit, "HEAD").returncode == 0


def en_destino(ctx, repos: list) -> list[dict]:
    """Del lado que recibiría (`hilo-revisar`), sin tocar nada: de cada repositorio del hilo (`relativa`, `commit`),
    si está aquí y si ya tiene ese commit."""
    salida = []
    for r in repos if isinstance(repos, list) else []:
        relativa = str(r.get("relativa") or "") if isinstance(r, dict) else ""
        if not relativa:  # fuera de la raíz de allá: aquí no se sabe dónde está
            continue
        commit = str(r.get("commit") or "")
        repo = _de_aqui(ctx, relativa)
        salida.append({"relativa": relativa, "existe": repo is not None,
                       "tiene": repo is not None and _tiene(repo, commit)})
    return salida


def al_dia(ctx, repos: list) -> list[str]:
    """Del lado que recibe, antes de abrir el hilo: cada repositorio suyo que no tiene el último commit de allá se pone
    al día con su rama de arriba (telar.git.al_dia: sin tocar lo sin commitear de otros). Lo que no se pudo, o lo
    que sigue faltando (commits que allá no subieron), dicho en una línea cada uno."""
    avisos = []
    for r in repos if isinstance(repos, list) else []:
        if not isinstance(r, dict):
            continue
        relativa, commit = str(r.get("relativa") or ""), str(r.get("commit") or "")
        nombre = str(r.get("nombre") or relativa)
        repo = _de_aqui(ctx, relativa)
        if repo is None or not commit or _tiene(repo, commit):
            continue
        res = git.al_dia(repo)
        if res.estado in ("choque", "apartado", "sin-arriba", "fallo"):
            avisos.append(f"{nombre} sigue atrás aquí: {res.detalle}")
        elif not _tiene(repo, commit):
            avisos.append(f"{nombre}: " + (f"llegaron {res.intentos} commits, pero " if res.intentos else "")
                          + f"falta lo que allá no se subió ({commit[:7]})")
        else:
            avisos.append(f"{nombre}: llegaron {res.intentos} commit{'s' if res.intentos != 1 else ''} de arriba")
    return avisos
