"""`telar modulos catalogo|nuevo|revisar|publicar` — encontrar módulos, y escribir, revisar y publicar uno.

    telar modulos catalogo [--buscar X] [--forzar] [--json]
    telar modulos nuevo <nombre> [--carpeta C]
    telar modulos revisar [carpeta] [--json]
    telar modulos revisar --catalogo .telar/catalogo.toml [--resolver]
    telar modulos publicar [carpeta] --version v0.2.0 [--catalogo oficial|<repo>] [--etiquetas a,b] [--seco]

`catalogo` lista lo que hay en los catálogos que se leen (telar.catalogo): el oficial, el de cada repo de
`[repos]` y los de `[catalogos] fuentes`, cada uno con lo que pide y si ya está instalado.

`nuevo` arma la carpeta de un módulo: su `modulo.toml` con una orden de ejemplo y `[permisos]` vacío (que se
llena con lo que pida de verdad), un README y un repositorio git. Se prueba con `telar modulos instalar --enlazar
<carpeta>`.

`revisar` dice lo que le falta para publicarlo: que el manifiesto se lea, que traiga `[permisos]` y descripción,
que su nombre no choque con una orden de telar, que sus comandos existan, que tenga README y un repositorio con
origen. Con `--catalogo`, revisa un `catalogo.toml` (`--resolver`: baja cada módulo en su versión y compara lo que
pide; es lo que corre la revisión de un PR al catálogo oficial).

`publicar` etiqueta la versión (si no lo está) y la sube, arma su entrada y abre un PR al catálogo con `gh`: el
oficial (`nicorivas/telar-modulos`) o el de un repo de `[repos]` (el de tu equipo). Si ya estaba, la entrada se
reemplaza: el PR muestra qué cambió, también en lo que pide. `--seco` solo dice qué haría.

El criterio para escribirlo (qué pedir, cómo nombrar, cuándo subir la versión) está en la skill /modulos.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from telar.ordenes import _comun
from telar.salida import visible

AYUDA = "Encontrar módulos en los catálogos, y escribir, revisar y publicar uno."


def main(verbo: str, argv: list[str], ctx) -> int:
    p = _comun.analizador(f"modulos {verbo}", AYUDA)
    p.epilog = __doc__
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    if verbo == "catalogo":
        p.add_argument("--buscar", default="", help="por nombre, descripción, etiqueta o autor")
        p.add_argument("--forzar", action="store_true", help="bajar los catálogos ahora, sin esperar la hora")
    elif verbo == "nuevo":
        p.add_argument("nombre")
        p.add_argument("--carpeta", default="", help="dónde (por defecto, ./telar-<nombre>)")
    elif verbo == "revisar":
        p.add_argument("carpeta", nargs="?", default=".")
        p.add_argument("--catalogo", default="", metavar="ARCHIVO", help="revisar un catalogo.toml en vez de un módulo")
        p.add_argument("--resolver", action="store_true", help="con --catalogo: bajar cada módulo y compararlo")
    else:
        p.add_argument("carpeta", nargs="?", default=".")
        p.add_argument("--version", required=True, help="la etiqueta de esta versión: v0.2.0")
        p.add_argument("--catalogo", default="oficial", help="oficial, o el nombre de un repo de [repos]")
        p.add_argument("--etiquetas", default="", help="palabras para encontrarlo, separadas por comas")
        p.add_argument("--seco", action="store_true", help="solo decir qué haría")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    try:
        return {"catalogo": _catalogo, "nuevo": _nuevo, "revisar": _revisar, "publicar": _publicar}[verbo](ctx, o)
    except ErrorDePublicar as e:
        return _comun.queja(str(e))


class ErrorDePublicar(Exception):
    pass


# ── catalogo ─────────────────────────────────────────────────────────────────

def _catalogo(ctx, o) -> int:
    from telar.servicios import modulos as servicio

    c = servicio.catalogo(ctx, forzar=o.forzar, buscar=o.buscar)
    if o.json:
        return _comun.escribir_json(c.model_dump(mode="json"))
    marca = {"oficial": _comun.verde("revisado"), "equipo": "del equipo", "sin revisar": _comun.amarillo("sin revisar")}
    for x in c.disponibles:
        estado = "instalado" if x["instalado"] else ("" if x["le_sirve"] else _comun.amarillo(f"pide telar {x['telar']}"))
        print(f"{_comun.fuerte(x['nombre'])}  {marca.get(x['confianza'], x['confianza'])}"
              + _comun.tenue(f"  {x['version']} · {x['catalogo']}") + (f"  {estado}" if estado else ""))
        print(f"    {visible(x['descripcion'])}")
        if x["etiquetas"]:
            print(_comun.tenue("    " + ", ".join(x["etiquetas"])))
    if not c.disponibles:
        print(_comun.tenue("nada" + (f" con «{o.buscar}»" if o.buscar else " en los catálogos")))
    for p in c.problemas:
        print(_comun.tenue(f"  ! {p}"))
    return 0


# ── nuevo ────────────────────────────────────────────────────────────────────

MANIFIESTO_NUEVO = '''descripcion = "{descripcion}"

# una orden: `telar {nombre} hola` en la terminal; con consulta = true, también desde la página y otra máquina
[ordenes.hola]
descripcion = "un saludo, para probar que el módulo anda"
comando = ["python3", "bin/hola.py"]
consulta = true

# lo que el agente de cada hilo sabe de este módulo al arrancar (una o dos líneas)
[contexto]
texto = "El módulo {nombre}: `telar {nombre} hola`."

# lo que pide fuera de su carpeta. Llénalo con lo que use de verdad: se muestra antes de instalarlo, y un
# catálogo no acepta un módulo sin esta tabla
[permisos]
leer = []          # rutas que lee
escribir = []      # rutas que escribe
red = false        # los sitios a los que se conecta (una lista), o false
ordenes = []       # las órdenes de telar que corre ("mensaje", "tipo tarea"…)
'''

HOLA = '''#!/usr/bin/env python3
"""La orden de ejemplo: en una consulta recibe un objeto JSON por la entrada y devuelve otro por la salida."""
import json
import sys

pedido = json.loads(sys.stdin.read() or "{}") if not sys.stdin.isatty() else {}
print(json.dumps({"hola": pedido.get("nombre", "mundo")}, ensure_ascii=False))
'''

README_NUEVO = '''# {nombre}

{descripcion}

Un módulo de [telar](https://github.com/nicorivas/telar).

## Instalar

```sh
telar modulos instalar {nombre}                      # desde el catálogo, si está
telar modulos instalar <la URL de este repositorio>  # suelto
```

## Qué trae

- `telar {nombre} hola`: un saludo (cámbialo por lo que haga el módulo).

## Qué pide

Lo que dice `[permisos]` en `modulo.toml`: nada fuera de su carpeta, todavía.
'''


def _nuevo(ctx, o) -> int:
    from telar import modulos as mod_modulos

    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", o.nombre):
        raise ErrorDePublicar(f"«{o.nombre}»: minúsculas, números, - y _, empezando por una letra")
    if o.nombre in _ordenes_de_telar():
        raise ErrorDePublicar(f"«{o.nombre}» es una orden de telar: `telar {o.nombre}` no llegaría al módulo")
    carpeta = Path(o.carpeta or f"telar-{o.nombre}").expanduser()
    if carpeta.exists() and any(carpeta.iterdir()):
        raise ErrorDePublicar(f"{carpeta} ya existe y no está vacía")
    (carpeta / "bin").mkdir(parents=True, exist_ok=True)
    descripcion = f"Lo que hace {o.nombre}, en una frase."
    (carpeta / mod_modulos.MANIFIESTO).write_text(MANIFIESTO_NUEVO.format(nombre=o.nombre, descripcion=descripcion),
                                                 encoding="utf-8")
    hola = carpeta / "bin" / "hola.py"
    hola.write_text(HOLA, encoding="utf-8")
    hola.chmod(0o755)
    (carpeta / "README.md").write_text(README_NUEVO.format(nombre=o.nombre, descripcion=descripcion), encoding="utf-8")
    (carpeta / ".gitignore").write_text(".venv/\n__pycache__/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(carpeta)], check=False)
    if o.json:
        return _comun.escribir_json({"carpeta": str(carpeta.resolve()), "nombre": o.nombre})
    print(f"módulo {o.nombre} en {carpeta}")
    print(_comun.tenue(f"    pruébalo: telar modulos instalar --enlazar {carpeta} · telar {o.nombre} hola"))
    print(_comun.tenue(f"    antes de publicarlo: telar modulos revisar {carpeta}"))
    return 0


def _ordenes_de_telar() -> set[str]:
    from telar import cli

    return set(getattr(cli, "ORDENES", {}) or {})


# ── revisar ──────────────────────────────────────────────────────────────────

def revisar_carpeta(carpeta: Path) -> list[tuple[str, str]]:
    """(gravedad, qué) de lo que le falta a un módulo para publicarlo: «falla» lo impide, «aviso» conviene."""
    from telar import modulos as mod_modulos

    carpeta = Path(carpeta).expanduser().resolve()
    salida: list[tuple[str, str]] = []
    try:
        nombre = mod_modulos._manifiesto_nombre(carpeta) or mod_modulos._nombre_de_fuente(str(carpeta))
        m = mod_modulos.leer(nombre, carpeta)
    except mod_modulos.ErrorDeModulo as e:
        return [("falla", f"su {mod_modulos.MANIFIESTO} no se lee: {e}")]
    if m.permisos is None:
        salida.append(("falla", "no trae [permisos]: un catálogo no lo acepta (aunque no pida nada: la tabla vacía)"))
    if not m.descripcion.strip() or m.descripcion.startswith("Lo que hace "):
        salida.append(("falla", "falta la descripción (la del ejemplo no vale): una frase de lo que hace"))
    if m.nombre in _ordenes_de_telar():
        salida.append(("falla", f"«{m.nombre}» es una orden de telar: `telar {m.nombre}` no llegaría al módulo"))
    for verbo, orden in m.ordenes.items():
        comando = orden.get("comando") if isinstance(orden, dict) else None
        primero = (comando or [""])[0] if isinstance(comando, list) else ""
        if primero and not (Path(primero).exists() or shutil.which(primero)):
            salida.append(("falla", f"orden {verbo}: «{primero}» no existe ni está en el PATH"))
    if not (carpeta / "README.md").is_file():
        salida.append(("aviso", "sin README.md: quien lo encuentre en el catálogo no sabe qué hace"))
    if subprocess.run(["git", "-C", str(carpeta), "rev-parse"], capture_output=True).returncode != 0:
        salida.append(("falla", "no es un repositorio git: un catálogo lo instala desde su repositorio"))
    else:
        origen = mod_modulos._git(carpeta, "remote", "get-url", "origin").stdout.strip()
        if not origen:
            salida.append(("falla", "su repositorio no tiene origen (git remote add origin …): de ahí lo baja quien lo instala"))
        if mod_modulos._git(carpeta, "status", "--porcelain").stdout.strip():
            salida.append(("aviso", "hay cambios sin commitear: no entran a la versión que se publique"))
    return salida


def _revisar(ctx, o) -> int:
    if o.catalogo:
        from telar import catalogo

        problemas = catalogo.revisar_archivo(Path(o.catalogo), resolver=o.resolver)
        if o.json:
            return _comun.escribir_json({"catalogo": o.catalogo, "problemas": problemas})
        for x in problemas:
            print(f"  {_comun.rojo('✗')} {x}")
        print(_comun.verde("  ✓ el catálogo está bien") if not problemas else "")
        return 1 if problemas else 0
    hallado = revisar_carpeta(Path(o.carpeta))
    if o.json:
        return _comun.escribir_json({"carpeta": str(Path(o.carpeta).resolve()),
                                     "problemas": [{"gravedad": g, "que": q} for g, q in hallado]})
    for g, q in hallado:
        print(f"  {_comun.rojo('✗') if g == 'falla' else _comun.amarillo('!')} {q}")
    if not any(g == "falla" for g, _ in hallado):
        print(_comun.verde("  ✓ listo para publicar") + _comun.tenue(": telar modulos publicar --version vX.Y.Z"))
    return 1 if any(g == "falla" for g, _ in hallado) else 0


# ── publicar ─────────────────────────────────────────────────────────────────

def _slug(url: str) -> str:
    """dueño/repo de una URL de GitHub (https o git@)."""
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    if not m:
        raise ErrorDePublicar(f"no sé abrir un PR en {url}: publicar sabe de repositorios de GitHub")
    return m.group(1)


def entrada(carpeta: Path, version: str, etiquetas: list[str]) -> dict:
    """La entrada del catálogo de un módulo, de su manifiesto y su repositorio."""
    from telar import __version__
    from telar import modulos as mod_modulos

    carpeta = Path(carpeta).expanduser().resolve()
    nombre = mod_modulos._manifiesto_nombre(carpeta) or mod_modulos._nombre_de_fuente(str(carpeta))
    m = mod_modulos.leer(nombre, carpeta)
    origen = mod_modulos.sin_credenciales(mod_modulos._git(carpeta, "remote", "get-url", "origin").stdout.strip())
    if origen.startswith("git@github.com:"):
        origen = "https://github.com/" + origen.split(":", 1)[1]
    autor = subprocess.run(["git", "-C", str(carpeta), "config", "user.name"], capture_output=True, text=True).stdout.strip()
    permisos = {k: v for k, v in (mod_modulos.permisos_json(m.permisos) or {}).items() if k != "otros"}
    # la versión entera con que se publica: un módulo puede usar algo que llegó en un parche (telar fechas, en 0.8.1)
    menor = __version__
    return {"nombre": m.nombre, "descripcion": m.descripcion, "fuente": re.sub(r"\.git$", "", origen), "version": version,
            "autor": autor, "etiquetas": etiquetas, "telar": f">={menor}", "permisos": permisos}


def _publicar(ctx, o) -> int:
    from telar import catalogo, unirse
    from telar import modulos as mod_modulos

    carpeta = Path(o.carpeta).expanduser().resolve()
    fallas = [q for g, q in revisar_carpeta(carpeta) if g == "falla"]
    if fallas:
        raise ErrorDePublicar("antes de publicarlo: " + "; ".join(fallas) + " (telar modulos revisar)")
    if not catalogo.REF.fullmatch(o.version):
        raise ErrorDePublicar(f"--version «{o.version}»: una etiqueta, como v0.2.0")
    e = entrada(carpeta, o.version, [x.strip() for x in o.etiquetas.split(",") if x.strip()])
    bloque = catalogo.entrada_toml(e)
    destino = _repo_del_catalogo(ctx, o.catalogo)
    etiquetada = bool(mod_modulos._git(carpeta, "rev-parse", "-q", "--verify", f"refs/tags/{o.version}").stdout.strip())
    plan = [*([] if etiquetada else [f"etiquetar {o.version} en {carpeta.name} y subir la etiqueta"]),
            f"abrir un PR a {destino} con la entrada de {e['nombre']}"]
    if o.seco:
        if o.json:
            return _comun.escribir_json({"entrada": e, "toml": bloque, "plan": plan, "catalogo": destino})
        for x in plan:
            print(f"  → {x}")
        print(_comun.tenue("\n" + bloque))
        return 0
    if not etiquetada:
        for orden in (["tag", "-a", o.version, "-m", f"{e['nombre']} {o.version}"], ["push", "-q", "origin", o.version]):
            r = mod_modulos._git(carpeta, *orden)
            if r.returncode != 0:
                raise ErrorDePublicar(f"git {' '.join(orden[:2])}: {(r.stderr or r.stdout).strip()[-200:]}")
    url = _pr(destino, e, bloque, unirse.quitar_tabla)
    if o.json:
        return _comun.escribir_json({"entrada": e, "pr": url, "catalogo": destino})
    print(f"publicado: {url}")
    print(_comun.tenue("    cuando lo mergeen, sale en el catálogo de todos (telar modulos catalogo --forzar)"))
    return 0


def _repo_del_catalogo(ctx, catalogo_pedido: str) -> str:
    """dueño/repo de GitHub donde vive el catálogo: el oficial, o el de un repo de [repos] (su origen)."""
    from telar import catalogo
    from telar import modulos as mod_modulos
    from telar import perfil as mod_perfil

    if catalogo_pedido == "oficial":
        return catalogo.REPO_OFICIAL
    repo = next((r for r in getattr(ctx.config, "repos", ()) or () if r.nombre == catalogo_pedido), None)
    if repo is None:
        raise ErrorDePublicar(f"--catalogo: oficial, o el nombre de un repo de [repos] (no hay «{catalogo_pedido}»)")
    origen = mod_modulos._git(mod_perfil.carpeta_de_repo(ctx.config, repo), "remote", "get-url", "origin").stdout.strip()
    return _slug(mod_modulos.sin_credenciales(origen))


def _pr(slug: str, e: dict, bloque: str, quitar_tabla) -> str:
    """En un clon aparte del repositorio del catálogo: una rama con la entrada puesta (reemplaza la de antes), su
    commit, y el PR. Devuelve su URL."""
    from telar import catalogo

    if not shutil.which("gh"):
        raise ErrorDePublicar("publicar abre el PR con gh (GitHub CLI): instálalo y entra con gh auth login")
    with tempfile.TemporaryDirectory() as tmp:
        clon = Path(tmp) / "catalogo"
        r = subprocess.run(["gh", "repo", "clone", slug, str(clon), "--", "-q", "--depth", "1"], capture_output=True, text=True)
        if r.returncode != 0:
            raise ErrorDePublicar(f"gh repo clone {slug}: {(r.stderr or r.stdout).strip()[-200:]}")
        archivo = clon / catalogo.NOMBRE_ARCHIVO
        antes = archivo.read_text(encoding="utf-8") if archivo.is_file() else f"version = {catalogo.FORMATO}\n"
        viejo = re.search(rf"(?ms)^\[modulos\.{re.escape(e['nombre'])}\].*?(?=^\[modulos\.(?!{re.escape(e['nombre'])}\.)|\Z)", antes)
        sin = quitar_tabla(antes, f"modulos.{e['nombre']}").rstrip() + "\n"
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(sin + "\n" + bloque, encoding="utf-8")
        rama = f"modulo-{e['nombre']}-{e['version']}".replace("/", "-")
        titulo = f"{e['nombre']} {e['version']}" + (" (nueva versión)" if viejo else " (nuevo)")
        cuerpo = (f"{e['descripcion']}\n\nFuente: {e['fuente']} @ {e['version']}\n\n**Lo que pide**:\n```json\n"
                  f"{json.dumps(e['permisos'], ensure_ascii=False, indent=1)}\n```\n"
                  + (f"\n**Antes**:\n```toml\n{viejo.group(0).strip()}\n```\n" if viejo else "")
                  + "\nAbierto con `telar modulos publicar`.")
        for orden in (["checkout", "-q", "-b", rama], ["add", catalogo.NOMBRE_ARCHIVO],
                      ["commit", "-q", "-m", f"catálogo: {titulo}"], ["push", "-q", "-u", "origin", rama]):
            r = subprocess.run(["git", "-C", str(clon), *orden], capture_output=True, text=True)
            if r.returncode != 0:
                raise ErrorDePublicar(f"git {orden[0]}: {(r.stderr or r.stdout).strip()[-200:]}")
        r = subprocess.run(["gh", "pr", "create", "--repo", slug, "--head", rama, "--title", titulo, "--body", cuerpo],
                           capture_output=True, text=True, cwd=clon, env={**os.environ})
        if r.returncode != 0:
            raise ErrorDePublicar(f"gh pr create: {(r.stderr or r.stdout).strip()[-200:]}")
        return r.stdout.strip().splitlines()[-1]
