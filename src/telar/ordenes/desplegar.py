"""`telar desplegar` — dejar corriendo lo que está en main en todas las máquinas donde vive el repositorio.

    telar desplegar                  el repositorio de aquí: lleva main a cada máquina, reinicia y comprueba
    telar desplegar --repo RUTA      otro repositorio
    telar desplegar --ver            qué haría en cada máquina, sin tocar nada
    telar desplegar --maquina NOMBRE solo en esa (se repite; las de [remotos] y esta, por su nombre)
    telar desplegar --todo           como si todo hubiera cambiado: corre todos los pasos aunque la máquina ya
                                     corra ese commit
    telar desplegar --json           lo que pasó, como contrato (docs/contratos.md)

Lo que se hace en cada máquina lo declara el repositorio en `.telar/despliegue.yaml` (docs/perfil.md, «El
despliegue»): qué preparar, qué servicios reiniciar, qué hacer después y qué comprobar. Las máquinas son esta y las
de `[remotos]`; dónde vive allá el repositorio y si usa systemd o launchd se averigua allá (docs/configuracion.md,
«`telar desplegar`»).

Se niega, sin tocar nada, si no se está en main, si hay cambios sin commitear en lo versionado (aquí o allá) o si
otra máquina tiene commits que aquí no están. Nunca fuerza un push. Si un paso falla se detiene ahí, y dice cuál y en
qué quedó cada máquina. Sale con 0 si todo quedó corriendo y comprobado, con 1 si algo falló y con 2 si se negó.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from telar import despliegue
from telar.ordenes import _comun

AYUDA = "Dejar corriendo lo que está en main en todas las máquinas donde vive el repositorio."

#: cómo se ve cada estado de un paso
MARCA = {"hecho": "✓", "fallo": "✗", "saltado": "·", "haria": "→", "pendiente": "○"}
FASE = {"codigo": "código", "preparar": "preparar", "reiniciar": "reiniciar", "despues": "después",
        "anotar": "anotar", "comprobar": "comprobar"}


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("desplegar", AYUDA)
    p.epilog = __doc__
    p.add_argument("--repo", default="", help="el repositorio (por defecto, el de la carpeta de aquí)")
    p.add_argument("--ver", action="store_true", help="qué haría, sin tocar nada")
    p.add_argument("--maquina", action="append", default=[], help="solo en esta máquina (se repite)")
    p.add_argument("--todo", action="store_true", help="todos los pasos, aunque la máquina ya corra ese commit")
    p.add_argument("--json", action="store_true", help="lo que pasó, como JSON")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    carpeta = Path(o.repo).expanduser() if o.repo else Path.cwd()
    try:
        d = despliegue.preparar(ctx.config, carpeta, solo=tuple(o.maquina), todo=o.todo)
    except despliegue.ErrorDeDespliegue as e:
        if o.json:
            _comun.escribir_json({"ok": False, "negado": str(e)})
            return 2
        return _comun.queja(f"desplegar: {e}")
    d.ver = o.ver
    if not o.json and not d.negado and not d.ver:
        print(_cabeza(d), flush=True)
    despliegue.desplegar(d, avisar=None if o.json else _avisar)
    if o.json:
        _comun.escribir_json(d.json())
    else:
        _informe(d)
    if d.negado:
        return 2
    return 0 if d.ok else 1


def _corto(sha: str) -> str:
    return sha[:7] if sha and sha != "?" else (sha or "nada anotado")


def _ruta(m: despliegue.Maquina) -> str:
    if not m.aqui:
        return f"{m.destino}:{m.ruta}"
    casa = str(Path.home())
    return "aquí, " + ("~" + m.ruta[len(casa):] if m.ruta.startswith(casa + os.sep) else m.ruta)


def _cabeza(d: despliegue.Despliegue) -> str:
    return _comun.fuerte(f"telar desplegar · {d.repo.name} en {d.rama}, a {d.commit[:7]}")


def _avisar(m: despliegue.Maquina, p: despliegue.Hecho) -> None:
    """Mientras corre, en la terminal: un paso que puede tardar (compilar, reinstalar) no deja la pantalla quieta."""
    if sys.stderr.isatty():
        print(_comun.tenue(f"  {MARCA.get(p.estado, ' ')} {m.nombre} · {FASE[p.fase]} {p.que}"), file=sys.stderr,
              flush=True)


def _linea(p: despliegue.Hecho) -> str:
    marca = MARCA.get(p.estado, " ")
    if p.estado == "fallo":
        marca = _comun.rojo(marca)
    elif p.estado == "hecho":
        marca = _comun.verde(marca)
    texto = f"  {marca} {FASE[p.fase]:<10} {p.que}"
    if p.detalle:
        detalle = p.detalle if p.estado == "fallo" else _comun.tenue(p.detalle)
        texto += " · " + detalle.replace("\n", "\n      ")
    return texto


def _aviso_compilados(d: despliegue.Despliegue) -> str:
    """Si lo compilado del commit no corresponde a sus fuentes (o no se pudo saber), el aviso; "" si está bien."""
    c = d.compilados
    if not c:
        return ""
    if c.get("error"):
        return _comun.rojo("!") + f" no pude comprobar que lo compilado corresponda a sus fuentes: {c['error']}"
    if c.get("desfasados"):
        return (_comun.rojo("!") + f" lo compilado de {d.commit[:7]} no corresponde a sus fuentes: "
                f"{', '.join(c['desfasados'])}. Se despliega tal cual está commiteado: vuelve a generarlo "
                f"(.telar/compilados.yaml dice cómo), commitea y despliega de nuevo")
    return ""


def _informe(d: despliegue.Despliegue) -> None:
    if d.negado:
        print(f"telar desplegar: no despliego (no toqué nada): {d.negado}" if "\n" not in d.negado else
              f"telar desplegar: no despliego (no toqué nada):\n  {d.negado.replace(chr(10), chr(10) + '  ')}",
              file=sys.stderr)
        return
    if d.ver:
        print(_cabeza(d) + _comun.tenue(" · lo que haría (--ver: no toco nada)"))
    aviso = _aviso_compilados(d)
    if aviso:
        print(aviso)
    for m in d.maquinas:
        print()
        if not m.ruta:
            buscadas = ", ".join(m.buscadas) or "—"
            print(f"{_comun.fuerte(m.nombre)} · no vive allá " + _comun.tenue(f"(busqué en {buscadas})"))
            continue
        cuenta = "nunca se desplegó con telar desplegar: hace todo" if not m.corre else f"corre {m.corre[:7]}"
        print(f"{_comun.fuerte(m.nombre)} · {_ruta(m)} · {m.sistema or 'sin systemd ni launchd'} · {cuenta}")
        for p in m.pasos:
            print(_linea(p))
    if d.iguales:
        print()
    for i in d.iguales:
        valores = set(map(str, i["valores"].values()))
        if i["ok"]:
            print(f"{_comun.verde('✓')} {i['que']}: {i['campo']} igual en {len(i['valores'])} "
                  f"{'máquina' if len(i['valores']) == 1 else 'máquinas'}" + _comun.tenue(f" ({next(iter(valores), '')})"))
        else:
            dichos = ", ".join(f"{k} {v}" for k, v in i["valores"].items())
            print(f"{_comun.rojo('✗')} {i['que']}: {i['campo']} distinta entre máquinas ({dichos})")
    print()
    if d.ver:
        return
    if d.fallo is None and d.ok:
        corren = [m.nombre for m in d.maquinas if m.ruta]
        print(_comun.verde("listo") + f": {', '.join(corren)} {'corre' if len(corren) == 1 else 'corren'} "
              f"{d.commit[:7]}")
        return
    # todo por la salida estándar, en orden: quien lo lee por un tubo (un agente) lo ve como se escribió
    if d.fallo is not None:
        f = d.fallo
        print(_comun.rojo("✗") + f" falló en {f['maquina']}, al {FASE[f['fase']]} {f['que']}: {f['detalle']}")
    print("quedó así:")
    for m in d.maquinas:
        if not m.ruta:
            continue
        tiene, corre = despliegue.quedo(d, m)
        estado = despliegue.estado_de(d, m)
        nota = {
            "listo": "al día", "al-dia": "al día", "sin-tocar": "sin tocar",
            "codigo-nuevo": "tiene el código nuevo, sigue corriendo el de antes",
            "a-medias": "algo se reinició, o falló al reiniciar: puede que no corra nada",
            "no-comprueba": "corre lo nuevo, pero algo de lo que se comprueba no contesta",
        }.get(estado, estado)
        print(f"  {m.nombre}: {nota} · tiene {_corto(tiene)}, corre {_corto(corre)}")
