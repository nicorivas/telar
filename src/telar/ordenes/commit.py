"""`telar commit` — commitear solo unas rutas y subirlas, sin pisar lo que otros dejaron a medias.

    telar commit -m "mensaje" -- ruta1 ruta2     commitea esas (las nuevas también) y las sube
    telar commit -m "…" --local -- rutas          solo commitea
    telar commit --subir                          sube lo ya commiteado del repositorio de aquí
    telar commit … --json                         lo que pasó, como contrato

El repositorio es el de la primera ruta (o el de aquí, con `--subir`). Commitea solo esas rutas
aunque el índice tenga otras cosas; nunca hace `git add -A` sin rutas, ni toca las marcadas
`skip-worktree`. Para subir, trae lo de arriba y rebasa encima, salvo que lo que llega toque un
archivo sin commitear de aquí: entonces no integra, lo dice y el commit queda local. Un push que
pierde la carrera con otro se reintenta con espera. Cada intento queda en `<estado>/commits.log`.

Sale con 0 si quedó commiteado (y subido, si se pidió), con 1 si quedó local por un choque o una
falla de red, y con 2 si no se pudo commitear.
"""

from __future__ import annotations

import sys
from pathlib import Path

from telar import git
from telar.ordenes import _comun

AYUDA = "Commitear solo unas rutas y subirlas, sin pisar lo que otros dejaron a medias."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("commit", AYUDA)
    p.epilog = __doc__
    p.add_argument("rutas", nargs="*", help="lo que se commitea (después de --)")
    p.add_argument("-m", "--mensaje", default="", help="el mensaje del commit")
    p.add_argument("--local", action="store_true", help="commitear sin subir")
    p.add_argument("--subir", action="store_true", help="solo subir lo ya commiteado")
    p.add_argument("--json", action="store_true", help="lo que pasó, como JSON")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.subir and o.rutas:
        return _comun.queja("--subir no lleva rutas: sube lo que ya está commiteado")
    if not o.subir:
        if not o.rutas:
            return _comun.queja("¿qué rutas? telar commit -m \"…\" -- ruta1 ruta2")
        if not o.mensaje.strip():
            return _comun.queja("falta el mensaje: -m \"…\"")
        res = git.commitear([Path(r) for r in o.rutas], o.mensaje)
        if res.estado == "fallo":
            git.anotar(Path(ctx.config.estado), res, o.mensaje)
            return _decir(res, o.json, 2)
    else:
        repo = git.repositorio(Path.cwd())
        if repo is None:
            return _comun.queja("aquí no hay un repositorio git")
        res = git.Resultado(repo=str(repo), estado="nada")
    if not o.local:
        res = git.subir(res)
    git.anotar(Path(ctx.config.estado), res, o.mensaje or "(subir)")
    # pedido subir: bien solo si quedó arriba; sin subir: bien si quedó commiteado (o no había nada)
    bien = res.subido if not o.local else res.estado in ("commiteado", "nada")
    return _decir(res, o.json, 0 if bien else 1)


def _decir(res: git.Resultado, como_json: bool, codigo: int) -> int:
    if como_json:
        _comun.escribir_json(res.json())
        return codigo
    lineas = {
        "subido": f"{res.commit or 'al día'} en {res.rama}, subido" + (f" ({res.intentos} intentos)" if res.intentos > 1 else ""),
        "commiteado": f"{res.commit} en {res.rama}, sin subir" + (f": {res.detalle}" if res.detalle else ""),
        "nada": res.detalle or "nada que commitear",
        "choque": f"{res.commit + ' queda local: ' if res.commit else 'no subí: '}{res.detalle}",
        "fallo": res.detalle,
    }
    print(lineas.get(res.estado, res.detalle), file=sys.stdout if codigo == 0 else sys.stderr)
    return codigo
