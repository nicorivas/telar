"""Desplegar: dejar corriendo lo que está en la rama principal de un repositorio en cada máquina donde vive.

`telar desplegar` (ordenes/desplegar.py) lo usa así:

    d = despliegue.preparar(config, Path.cwd())     # mira todas las máquinas, sin tocar nada
    d.negado                                         # por qué no se puede ("" si se puede)
    despliegue.desplegar(d)                          # lleva el código, reinicia y comprueba

Lo que es de cada **repositorio** (qué se prepara, qué servicios corren su código, qué se comprueba) lo declara él, en
`.telar/despliegue.yaml` (`leer_declaracion`; docs/perfil.md, «El despliegue»). Lo que es de cada **máquina** sale de
la configuración de quien despliega y de la máquina misma: las otras son las de `[remotos]`; dónde vive allá el
repositorio, de su `raiz` (la misma carpeta relativa), de su `repos` y de lo que dice el telar de allá (su raíz, sus
`[repos]`, las carpetas de sus módulos), y es el mismo repositorio si comparte sus primeros commits; systemd o launchd,
de lo que hay allá. En cada máquina corre `telar.despliegue_alla`, por ssh en las otras.

El orden, en cada máquina (las otras primero, esta al final), y se detiene en el primer paso que falla:

1. **código**: aquí ya está; a otra se le manda el commit (`git push` a una referencia propia, nunca forzado) y
   avanza su rama con `git merge --ff-only`.
2. **preparar**: los comandos que el repositorio pide antes de reiniciar (compilar, reinstalar).
3. **reiniciar**: sus servicios, los que estén instalados en esa máquina.
4. **después**: lo que va con el código nuevo ya corriendo (`telar agente instalar`).
5. **anotar**: `refs/telar/desplegado` queda en el commit que corre. Así se sabe qué cambió desde el último despliegue
   de esa máquina (`si_cambia`), y una máquina al día no se reinicia de nuevo.
6. **comprobar**: lo que el repositorio declara (la página de telar con la llave de cada máquina, un comando), y que
   lo que debe ser igual en todas lo sea.

Se niega antes de tocar nada si no se está en la rama, si lo versionado está sucio aquí o allá, o si otra máquina
tiene commits que aquí no están.

Reemplaza a `servidor/desplegar.sh`, que desplegaba lo que ya estaba en el remoto de git (`git pull` en el servidor)
y reiniciaba a mano lo de telar: ahora avisa y llama a `telar desplegar`.
"""

from __future__ import annotations

import fnmatch
import json
import os
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

#: lo que cada repositorio declara
DECLARACION = Path(".telar") / "despliegue.yaml"
#: el commit que corre en esta máquina, en su copia del repositorio
DESPLEGADO = "refs/telar/desplegado"
#: adonde llega el commit a la otra máquina antes de avanzar su rama (una por despliegue: nunca se pisa otra)
LLEGA = "refs/telar/llega"
SSH = ("ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8")
#: cuánto puede tardar un paso declarado (compilar, reinstalar)
PLAZO_PASO = 900
AYUDANTE = Path(__file__).with_name("despliegue_alla.py")


class ErrorDeDespliegue(Exception):
    """Lo que no deja desplegar. El mensaje es para la persona."""


# ── lo que declara el repositorio ─────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Paso:
    comando: str
    #: solo si cambió alguno de estos archivos (glob desde la raíz; `*` cruza carpetas, `x/` es todo lo de adentro)
    si_cambia: tuple[str, ...] = ()
    #: solo en las máquinas donde está instalado ese servicio (uno de `servicios`, por cualquiera de sus nombres)
    si_corre: str = ""


@dataclass(frozen=True, slots=True)
class Servicio:
    systemd: str = ""
    launchd: str = ""
    si_cambia: tuple[str, ...] = ()

    def nombre(self, sistema: str) -> str:
        return {"systemd": self.systemd, "launchd": self.launchd}.get(sistema, "")

    @property
    def nombres(self) -> tuple[str, ...]:
        return tuple(n for n in (self.systemd, self.launchd) if n)


@dataclass(frozen=True, slots=True)
class Comprobacion:
    #: una ruta de la página de telar de cada máquina (`/pagina.json`, `/api/salud`), pedida con su llave
    pagina: str = ""
    #: o un comando, en la carpeta del repositorio
    comando: str = ""
    #: con `pagina`: el campo de su JSON que tiene que ser el mismo en todas las máquinas
    igual: str = ""
    #: cuánto esperar a que conteste (segundos): el servicio puede estar arrancando
    plazo: float = 30
    #: con `pagina`: a cuántos segundos de contestar se pide de nuevo, una vez, y tiene que seguir contestando (0: no se
    #: pide de nuevo). Un servicio que arranca y se cae a los pocos segundos pasaba la primera (26-nov-2026)
    sigue: float = 0

    @property
    def que(self) -> str:
        return self.pagina or self.comando


@dataclass(frozen=True, slots=True)
class Declaracion:
    rama: str = "main"
    preparar: tuple[Paso, ...] = ()
    servicios: tuple[Servicio, ...] = ()
    despues: tuple[Paso, ...] = ()
    comprobar: tuple[Comprobacion, ...] = ()


def _globs(valor, donde: str) -> tuple[str, ...]:
    if valor is None:
        return ()
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list) or not all(isinstance(v, str) and v.strip() for v in valor):
        raise ErrorDeDespliegue(f"{DECLARACION}: {donde}: `si_cambia` es una lista de rutas (globs)")
    return tuple(v.strip() for v in valor)


def _lista(datos: dict, clave: str) -> list:
    valor = datos.get(clave)
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise ErrorDeDespliegue(f"{DECLARACION}: `{clave}` es una lista")
    return valor


def _pasos(datos: dict, clave: str) -> tuple[Paso, ...]:
    pasos = []
    for i, c in enumerate(_lista(datos, clave), 1):
        if isinstance(c, str):
            c = {"comando": c}
        comando = str(c.get("comando") or "").strip() if isinstance(c, dict) else ""
        if not comando:
            raise ErrorDeDespliegue(f"{DECLARACION}: {clave} {i}: falta su `comando`")
        pasos.append(Paso(comando, _globs(c.get("si_cambia"), f"{clave} {i}"), str(c.get("si_corre") or "").strip()))
    return tuple(pasos)


def interpretar(datos) -> Declaracion:
    """La declaración, de lo leído del YAML. ErrorDeDespliegue con lo que no se entiende."""
    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise ErrorDeDespliegue(f"{DECLARACION}: se esperaba un mapa (rama, preparar, servicios, despues, comprobar)")
    conocidas = {"rama", "preparar", "servicios", "despues", "comprobar"}
    if (otras := sorted(set(datos) - conocidas)):
        raise ErrorDeDespliegue(f"{DECLARACION}: no conozco {', '.join(otras)} (sí: {', '.join(sorted(conocidas))})")
    servicios = []
    for i, s in enumerate(_lista(datos, "servicios"), 1):
        if not isinstance(s, dict) or not (s.get("systemd") or s.get("launchd")):
            raise ErrorDeDespliegue(f"{DECLARACION}: servicio {i}: dile su nombre en `systemd`, en `launchd` o en los dos")
        servicios.append(Servicio(str(s.get("systemd") or "").strip(), str(s.get("launchd") or "").strip(),
                                  _globs(s.get("si_cambia"), f"servicio {i}")))
    nombres = {n for s in servicios for n in s.nombres}
    preparar, despues = _pasos(datos, "preparar"), _pasos(datos, "despues")
    for p in (*preparar, *despues):
        if p.si_corre and p.si_corre not in nombres:
            raise ErrorDeDespliegue(f"{DECLARACION}: `si_corre: {p.si_corre}` no es ninguno de `servicios`")
    comprobar = []
    for i, c in enumerate(_lista(datos, "comprobar"), 1):
        if not isinstance(c, dict) or bool(c.get("pagina")) == bool(c.get("comando")):
            raise ErrorDeDespliegue(f"{DECLARACION}: comprobar {i}: o `pagina` (una ruta) o `comando`, uno de los dos")
        pagina = str(c.get("pagina") or "").strip()
        if pagina and not pagina.startswith("/"):
            raise ErrorDeDespliegue(f"{DECLARACION}: comprobar {i}: la ruta de `pagina` empieza con / ({pagina})")
        if c.get("igual") and not pagina:
            raise ErrorDeDespliegue(f"{DECLARACION}: comprobar {i}: `igual` va con `pagina` (un campo de su JSON)")
        try:
            plazo = float(c.get("plazo", 30))
            sigue = float(c.get("sigue", 0))
        except (TypeError, ValueError):
            raise ErrorDeDespliegue(f"{DECLARACION}: comprobar {i}: `plazo` y `sigue` son segundos") from None
        if sigue and not pagina:
            raise ErrorDeDespliegue(f"{DECLARACION}: comprobar {i}: `sigue` va con `pagina`")
        if sigue < 0:
            raise ErrorDeDespliegue(f"{DECLARACION}: comprobar {i}: `sigue` son segundos, 0 o más")
        comprobar.append(Comprobacion(pagina, str(c.get("comando") or "").strip(), str(c.get("igual") or "").strip(),
                                      plazo, sigue))
    rama = str(datos.get("rama") or "main").strip()
    return Declaracion(rama, preparar, tuple(servicios), despues, tuple(comprobar))


def leer_declaracion(repo: Path) -> Declaracion:
    ruta = Path(repo) / DECLARACION
    if not ruta.is_file():
        raise ErrorDeDespliegue(f"este repositorio no dice cómo se despliega: falta {DECLARACION} "
                                "(docs/perfil.md, «El despliegue»)")
    import yaml

    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ErrorDeDespliegue(f"{DECLARACION}: no lo entiendo ({e})") from None
    return interpretar(datos)


def toca(globs: tuple[str, ...], cambios: list[str] | None) -> bool:
    """Si algo de `cambios` calza con `globs`. Sin `globs`, cualquier cambio cuenta; `cambios` None es «todo»."""
    if cambios is None:
        return True
    if not cambios:
        return False
    if not globs:
        return True
    for g in globs:
        for c in cambios:
            if (g.endswith("/") and c.startswith(g)) or fnmatch.fnmatchcase(c, g):
                return True
    return False


# ── las máquinas ──────────────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Hecho:
    """Un paso en una máquina, para el informe: `estado` es pendiente | hecho | fallo | saltado | haria."""

    fase: str
    que: str
    estado: str = "pendiente"
    detalle: str = ""
    #: de `comprobar`: cuál de las declaradas
    indice: int = field(default=-1, repr=False)

    def json(self) -> dict:
        return {"fase": self.fase, "que": self.que, "estado": self.estado, "detalle": self.detalle}


@dataclass
class Maquina:
    nombre: str
    #: el destino de ssh; "" es esta máquina
    destino: str = ""
    #: la raíz del repositorio de trabajo allá (`[remotos] raiz`) y los repositorios que viven en las dos (`repos`)
    raiz: str = ""
    repos: tuple[str, ...] = ()
    # lo que se vio al mirar
    ruta: str = ""
    rama: str = ""
    tiene: str = ""
    corre: str = ""
    sucio: list[str] = field(default_factory=list)
    sistema: str = ""
    instalados: list[str] = field(default_factory=list)
    buscadas: list[str] = field(default_factory=list)
    #: si se alcanzó a mirar (no, si se negó antes por algo de aquí)
    mirada: bool = False
    #: por qué no se puede desplegar aquí (se niega todo)
    problema: str = ""
    #: lo que cambió desde lo que corre; None es «todo» (no se sabe qué corre, o --todo)
    cambios: list[str] | None = None
    pasos: list[Hecho] = field(default_factory=list)
    #: lo que contestó cada comprobación de `pagina`, por su índice en la declaración
    valores: dict[int, object] = field(default_factory=dict)

    @property
    def aqui(self) -> bool:
        return not self.destino

    def shell(self, comando: str, *, carpeta: str = "", timeout: float = PLAZO_PASO) -> tuple[int, str]:
        """Corre `comando` en esta máquina (bash) o allá (bash de login, por ssh: el PATH de una sesión). (código,
        lo que dijo)."""
        if self.aqui:
            argv, cwd = ["bash", "-c", comando], (carpeta or None)
        else:
            dentro = f"cd {shlex.quote(carpeta)} && {comando}" if carpeta else comando
            argv, cwd = [*SSH, self.destino, "bash -lc " + shlex.quote(dentro)], None
        try:
            r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124, f"no terminó en {timeout:g} s"
        except OSError as e:
            return 127, str(e)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()

    def ayudante(self, pedido: dict, *, timeout: float = 90) -> dict:
        """Una acción de `telar.despliegue_alla`, aquí o allá. Lo que contestó; {"error": …} si no contestó."""
        script = AYUDANTE.read_text(encoding="utf-8")
        argumento = json.dumps(pedido)
        argv = [sys.executable, "-", argumento] if self.aqui else [
            *SSH, self.destino, "python3 - " + shlex.quote(argumento)]
        try:
            r = subprocess.run(argv, input=script, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"error": f"no contestó en {timeout:g} s"}
        except OSError as e:
            return {"error": str(e)}
        lineas = [l for l in (r.stdout or "").splitlines() if l.strip()]
        try:
            respuesta = json.loads(lineas[-1]) if lineas else None
        except ValueError:
            respuesta = None
        if not isinstance(respuesta, dict):
            quien = "aquí" if self.aqui else self.destino
            return {"error": ((r.stderr or "").strip() or f"{quien}: salió con {r.returncode}")[-400:]}
        return respuesta

    def donde(self) -> str:
        return f"aquí, {self.ruta}" if self.aqui else f"{self.destino}:{self.ruta}"


def _git(repo: Path, *args: str, timeout: float = 120) -> subprocess.CompletedProcess:
    entorno = dict(os.environ)
    # un push a otra máquina no puede quedarse esperando una clave
    entorno.setdefault("GIT_SSH_COMMAND", " ".join(SSH))
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout,
                              env=entorno)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", f"git {args[0]} no terminó en {timeout:g} s")


def _salida(r: subprocess.CompletedProcess) -> str:
    return ((r.stderr or "") + (r.stdout or "")).strip()[-400:]


def _nombre_de_aqui(config) -> str:
    try:
        from telar import bus

        return bus.maquina(config)
    except Exception:  # noqa: BLE001 - sin nombre del bus, el de la red
        import socket

        return socket.gethostname().split(".")[0]


def candidatas(config, m: Maquina, repo: Path) -> list[str]:
    """Dónde buscar el repositorio en otra máquina, antes de preguntarle a su telar: la misma carpeta relativa a la
    raíz de allá, la misma relativa al hogar, y las de su `repos`."""
    salida: list[str] = []
    try:
        rel = repo.resolve().relative_to(Path(config.raiz).expanduser().resolve())
        salida.append(m.raiz if str(rel) == "." else str(PurePosixPath(m.raiz) / rel.as_posix()))
    except ValueError:
        pass
    try:
        salida.append("~/" + repo.resolve().relative_to(Path.home().resolve()).as_posix())
    except ValueError:
        pass
    salida += list(m.repos)
    return list(dict.fromkeys(s for s in salida if s))


# ── el despliegue ─────────────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Despliegue:
    repo: Path
    decl: Declaracion
    commit: str
    rama: str
    maquinas: list[Maquina]
    #: por qué no se hace nada ("" si se puede)
    negado: str = ""
    ver: bool = False
    #: el primer paso que falló: {maquina, fase, que, detalle}
    fallo: dict | None = None
    #: las comprobaciones de lo que tiene que ser igual en todas: {que, campo, ok, valores: {maquina: valor}}
    iguales: list[dict] = field(default_factory=list)
    #: si lo compilado del commit corresponde a sus fuentes (`comprobar_compilados`): None si no se miró (el
    #: repositorio no declara lo compilado, o nada de lo que cambia lo toca); si no, {desfasados, error}
    compilados: dict | None = None

    @property
    def ok(self) -> bool:
        return not self.negado and self.fallo is None and all(i["ok"] for i in self.iguales)

    def json(self) -> dict:
        return {
            "repo": str(self.repo), "rama": self.rama, "commit": self.commit, "ver": self.ver, "ok": self.ok,
            "negado": self.negado, "fallo": self.fallo, "iguales": self.iguales, "compilados": self.compilados,
            "maquinas": [{
                "nombre": m.nombre, "aqui": m.aqui, "destino": m.destino, "ruta": m.ruta, "sistema": m.sistema,
                "estado": estado_de(self, m), "tenia": m.tiene, "corria": m.corre,
                **dict(zip(("tiene", "corre"), quedo(self, m))),
                "cambios": None if m.cambios is None else len(m.cambios), "problema": m.problema,
                "buscadas": m.buscadas, "pasos": [p.json() for p in m.pasos],
            } for m in self.maquinas],
        }


def _hecho(m: Maquina, fase: str) -> bool:
    return any(p.fase == fase and p.estado == "hecho" for p in m.pasos)


def estado_de(d: Despliegue, m: Maquina) -> str:
    """En qué quedó una máquina:

    - `sin-mirar`: se negó antes de mirarla; `no-vive`: el repositorio no está en esa máquina; `negada`: por ella no
      se desplegó (`problema`); `ver`: --ver.
    - `al-dia`: ya corría este commit; `listo`: lo corre ahora, y contesta lo que se comprueba.
    - `sin-tocar`: no se llegó a ella, o falló al llevarle el código (que no cambia nada allá).
    - `codigo-nuevo`: tiene el commit nuevo y corre el de antes (falló al preparar).
    - `a-medias`: algo se reinició, o falló al reiniciar: puede que no corra nada.
    - `no-comprueba`: corre lo nuevo, pero algo de lo que se comprueba no contesta.
    """
    if m.problema:
        return "negada"
    if not m.mirada:
        return "sin-mirar"
    if not m.ruta:
        return "no-vive"
    if d.ver:
        return "ver"
    fallo = next((p for p in m.pasos if p.estado == "fallo"), None)
    if fallo is None:
        if any(p.estado == "pendiente" for p in m.pasos):
            return "sin-tocar"
        return "listo" if _hecho(m, "anotar") else "al-dia"
    if fallo.fase == "comprobar":
        return "no-comprueba"
    if fallo.fase in ("reiniciar", "despues", "anotar") or _hecho(m, "reiniciar"):
        return "a-medias"
    if fallo.fase == "codigo":
        return "sin-tocar"
    return "codigo-nuevo"


def quedo(d: Despliegue, m: Maquina) -> tuple[str, str]:
    """(el commit que tiene, el que corre) después del despliegue; el que corre es "?" si se reinició algo y no se
    alcanzó a anotar, y "" si no se sabe (nunca se desplegó con telar desplegar)."""
    if not m.ruta:
        return "", ""
    tiene = d.commit if (m.aqui or m.tiene == d.commit or _hecho(m, "codigo")) else m.tiene
    if _hecho(m, "anotar") or m.cambios == []:
        corre = d.commit
    elif estado_de(d, m) == "a-medias":
        corre = "?"
    else:
        corre = m.corre
    return tiene, corre


def repositorio(carpeta: Path) -> Path:
    r = _git(carpeta, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        raise ErrorDeDespliegue(f"{carpeta} no está en un repositorio git")
    return Path(r.stdout.strip())


def preparar(config, carpeta: Path, *, solo: tuple[str, ...] = (), todo: bool = False) -> Despliegue:
    """Mira el repositorio de `carpeta` y cada máquina donde vive, y arma lo que haría en cada una. No toca nada.
    ErrorDeDespliegue si ni siquiera se puede empezar (no es un repositorio, la declaración no se entiende); lo demás
    que impide desplegar queda en `negado`."""
    repo = repositorio(Path(carpeta))
    decl = leer_declaracion(repo)
    commit = _git(repo, "rev-parse", "HEAD").stdout.strip()
    rama = _git(repo, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip()
    aqui = Maquina(_nombre_de_aqui(config))
    otras = [Maquina(r.nombre, r.destino, r.raiz, tuple(r.repos)) for r in getattr(config, "remotos", ()) or ()]
    todas = [*otras, aqui]
    if solo:
        nombres = {m.nombre for m in todas}
        if (desconocidas := [s for s in solo if s not in nombres]):
            raise ErrorDeDespliegue(f"no conozco la máquina {', '.join(desconocidas)} (hay: {', '.join(sorted(nombres))})")
        todas = [m for m in todas if m.nombre in solo]
    d = Despliegue(repo, decl, commit, rama, todas)
    if rama != decl.rama:
        d.negado = f"no estás en {decl.rama} (estás en {rama or 'un commit suelto'}): se despliega {decl.rama}"
        return d
    sucio = [l for l in _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.splitlines() if l.strip()]
    if sucio:
        d.negado = "hay cambios sin commitear aquí, en lo versionado:\n" + "\n".join(f"  {l}" for l in sucio[:20])
        return d
    raices = _git(repo, "rev-list", "--max-parents=0", "HEAD").stdout.split()
    servicios = [{"systemd": s.systemd, "launchd": s.launchd} for s in decl.servicios]
    for m in todas:
        pedido = {"accion": "mirar", "raices": raices, "servicios": servicios,
                  "candidatas": [str(repo)] if m.aqui else candidatas(config, m, repo), "buscar_en_config": not m.aqui}
        r = m.ayudante(pedido)
        if "error" in r:
            m.problema = f"no pude mirarla ({r['error']})"
            continue
        m.mirada = True
        m.ruta, m.buscadas = r.get("ruta") or "", list(r.get("buscadas") or [])
        m.sistema, m.instalados = r.get("sistema") or "", list(r.get("instalados") or [])
        if not m.ruta:
            continue
        m.rama, m.tiene, m.corre, m.sucio = r.get("rama") or "", r.get("tiene") or "", r.get("corre") or "", list(r.get("sucio") or [])
        m.problema = _problema(repo, decl, m, commit)
        m.cambios = None if todo else _cambios(repo, m.corre, commit)
        m.pasos = _plan(repo, decl, m, commit)
    negadas = [m for m in todas if m.problema]
    if negadas:
        d.negado = "\n".join(f"{m.nombre}: {m.problema}" for m in negadas)
    else:
        d.compilados = comprobar_compilados(repo, commit, [m.cambios for m in todas if m.ruta])
    return d


def comprobar_compilados(repo: Path, commit: str, cambios: list[list[str] | None]) -> dict | None:
    """La red de lo compilado: la página viaja compilada, tal como está en el commit, y si una fusión dejó lo
    compilado viejo (cambió la fuente y nadie lo volvió a generar), se despliega lo viejo sin que nadie lo vea. Lo
    vuelve a generar en un worktree temporal de `commit` (`.telar/compilados.yaml`; telar.ramas.desfasados, unos
    segundos) y dice qué salió distinto: {desfasados: [rutas], error: "" o por qué no se pudo mirar}. Solo si lo que
    cambia en alguna máquina (`cambios`, de cada una; None es «no se sabe», y cuenta todo) toca sus fuentes o lo
    compilado; si no, None. No niega el despliegue: avisa."""
    from telar import ramas

    juntos: set[str] | None = set()
    for c in cambios:
        if c is None:
            juntos = None
            break
        juntos |= set(c)
    if juntos is not None and not juntos:
        return None
    try:
        malos = ramas.desfasados(repo, commit, juntos)
    except ramas.ErrorDeRama as e:
        return {"desfasados": [], "error": str(e)}
    return None if malos is None else {"desfasados": malos, "error": ""}


def _problema(repo: Path, decl: Declaracion, m: Maquina, commit: str) -> str:
    if m.aqui:
        return ""
    if m.rama != decl.rama:
        return f"allá no está en {decl.rama} (está en {m.rama or 'un commit suelto'}) en {m.ruta}"
    if m.sucio:
        return f"tiene cambios sin commitear en lo versionado ({m.ruta}):\n" + "\n".join(f"    {l}" for l in m.sucio[:20])
    if m.tiene == commit:
        return ""
    sabe = _git(repo, "cat-file", "-e", f"{m.tiene}^{{commit}}").returncode == 0
    if not sabe or _git(repo, "merge-base", "--is-ancestor", m.tiene, commit).returncode != 0:
        return (f"tiene commits que aquí no están (su {decl.rama} está en {m.tiene[:7]}): tráelos antes, "
                f"git pull {m.destino}:{m.ruta} {decl.rama}")
    return ""


def _cambios(repo: Path, corre: str, commit: str) -> list[str] | None:
    """Lo que cambió desde lo que corre en esa máquina; None si no se sabe qué corre (todo cuenta como cambiado)."""
    if not corre:
        return None
    if corre == commit:
        return []
    r = _git(repo, "diff", "--name-only", corre, commit)
    return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else None


def _plan(repo: Path, decl: Declaracion, m: Maquina, commit: str) -> list[Hecho]:
    pasos: list[Hecho] = []
    if m.aqui:
        pasos.append(Hecho("codigo", f"{commit[:7]}, aquí", "saltado", "ya está"))
    elif m.tiene == commit:
        pasos.append(Hecho("codigo", f"{commit[:7]}, allá", "saltado", "ya está"))
    else:
        n = _git(repo, "rev-list", "--count", f"{m.tiene}..{commit}").stdout.strip()
        pasos.append(Hecho("codigo", f"{m.tiene[:7]} → {commit[:7]}" + (f" ({n} commit{'' if n == '1' else 's'})" if n else "")))
    nada = m.cambios == []
    instalados = set(m.instalados)

    def declarados(lista, fase):
        for p in lista:
            h = Hecho(fase, p.comando)
            servicio = next((s for s in decl.servicios if p.si_corre in s.nombres), None)
            if nada:
                h.estado, h.detalle = "saltado", "ya corre este commit"
            elif servicio is not None and servicio.nombre(m.sistema) not in instalados:
                h.estado, h.detalle = "saltado", f"{p.si_corre} no está instalado aquí"
            elif not toca(p.si_cambia, m.cambios):
                h.estado, h.detalle = "saltado", "no cambió " + ", ".join(p.si_cambia)
            pasos.append(h)

    declarados(decl.preparar, "preparar")
    for s in decl.servicios:
        nombre = s.nombre(m.sistema)
        h = Hecho("reiniciar", nombre or " / ".join(s.nombres))
        if nada:
            h.estado, h.detalle = "saltado", "ya corre este commit"
        elif not nombre or nombre not in instalados:
            h.estado, h.detalle = "saltado", "no está instalado aquí"
        elif not toca(s.si_cambia, m.cambios):
            h.estado, h.detalle = "saltado", "no cambió " + ", ".join(s.si_cambia)
        pasos.append(h)
    declarados(decl.despues, "despues")
    pasos.append(Hecho("anotar", f"corre {commit[:7]}", "saltado" if nada else "pendiente",
                       "ya lo estaba" if nada else ""))
    for i, c in enumerate(decl.comprobar):
        pasos.append(Hecho("comprobar", c.que, indice=i))
    return pasos


def desplegar(d: Despliegue, *, avisar=None) -> Despliegue:
    """Hace lo planeado en cada máquina, en orden, y se detiene en el primer paso que falla (`d.fallo`). Con
    `d.ver`, o si `d.negado`, no toca nada. `avisar(maquina, hecho)` se llama al terminar cada paso."""
    if d.negado:
        return d
    if d.ver:
        for m in d.maquinas:
            for p in m.pasos:
                if p.estado == "pendiente":
                    p.estado = "haria"
        return d
    with _candado(d.repo) as libre:
        if not libre:
            d.negado = "ya hay otro telar desplegar corriendo en este repositorio"
            return d
        for m in d.maquinas:
            if not m.ruta:
                continue
            for p in m.pasos:
                if p.estado != "pendiente":
                    continue
                ok, detalle = _hacer(d, m, p)
                p.estado, p.detalle = ("hecho" if ok else "fallo"), detalle
                if avisar is not None:
                    avisar(m, p)
                if not ok:
                    d.fallo = {"maquina": m.nombre, "fase": p.fase, "que": p.que, "detalle": detalle}
                    return d
    d.iguales = _iguales(d)
    return d


@contextmanager
def _candado(repo: Path):
    """De a un despliegue por repositorio: un candado en su carpeta de git (la común a sus worktrees)."""
    import fcntl

    comun = _git(repo, "rev-parse", "--git-common-dir").stdout.strip() or ".git"
    ruta = (Path(repo) / comun) / "telar-desplegar.lock"
    try:
        f = open(ruta, "w")
    except OSError:
        yield True
        return
    with f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True


def _hacer(d: Despliegue, m: Maquina, p: Hecho) -> tuple[bool, str]:
    if p.fase == "codigo":
        return _llevar(d, m)
    if p.fase in ("preparar", "despues"):
        codigo, salida = m.shell(p.que, carpeta=m.ruta)
        return codigo == 0, "" if codigo == 0 else (salida[-400:] or f"salió con {codigo}")
    if p.fase == "reiniciar":
        r = m.ayudante({"accion": "reiniciar", "servicio": p.que, "sistema": m.sistema}, timeout=200)
        return bool(r.get("ok")), r.get("detalle") or r.get("error") or ""
    if p.fase == "anotar":
        codigo, salida = m.shell(f"git update-ref {DESPLEGADO} {d.commit}", carpeta=m.ruta, timeout=60)
        return codigo == 0, salida if codigo else ""
    if p.fase == "comprobar":
        c = d.decl.comprobar[p.indice]
        if c.pagina:
            r = m.ayudante({"accion": "comprobar", "pagina": c.pagina, "plazo": c.plazo, "sigue": c.sigue},
                           timeout=c.plazo + c.sigue + 60)
            if not r.get("ok"):
                return False, r.get("detalle") or r.get("error") or ""
            valor = m.valores[p.indice] = r.get("valor")
            return True, (f"{c.igual} {valor.get(c.igual)}" if c.igual and isinstance(valor, dict) else "")
        limite = time.monotonic() + c.plazo
        while True:
            codigo, salida = m.shell(c.comando, carpeta=m.ruta, timeout=max(c.plazo, 10))
            if codigo == 0:
                return True, ""
            if time.monotonic() > limite:
                return False, salida[-400:] or f"salió con {codigo}"
            time.sleep(1)
    return False, f"no sé hacer «{p.fase}»"


def _llevar(d: Despliegue, m: Maquina) -> tuple[bool, str]:
    """El commit, a la otra máquina: a una referencia propia (sin forzar nada) y su rama avanza hasta él."""
    ref = f"{LLEGA}-{int(time.time())}-{os.getpid()}"
    r = _git(d.repo, "push", "-q", f"{m.destino}:{m.ruta}", f"{d.commit}:{ref}", timeout=600)
    if r.returncode != 0:
        return False, f"git push: {_salida(r)}"
    rama = shlex.quote(d.decl.rama)
    guion = (f'[ "$(git symbolic-ref --short -q HEAD)" = {rama} ] && [ "$(git rev-parse HEAD)" = {m.tiene} ]'
             f' || {{ echo "cambió mientras se miraba: ya no está en {m.tiene[:7]} de {d.decl.rama}"; git update-ref -d {ref}; exit 3; }}; '
             f"git merge -q --ff-only {d.commit}; r=$?; git update-ref -d {ref}; exit $r")
    codigo, salida = m.shell(guion, carpeta=m.ruta, timeout=300)
    return codigo == 0, "" if codigo == 0 else (salida[-400:] or f"salió con {codigo}")


def _iguales(d: Despliegue) -> list[dict]:
    salida = []
    for i, c in enumerate(d.decl.comprobar):
        if not c.igual:
            continue
        valores = {m.nombre: (m.valores[i].get(c.igual) if isinstance(m.valores.get(i), dict) else None)
                   for m in d.maquinas if i in m.valores}
        salida.append({"que": c.pagina, "campo": c.igual, "ok": len(set(map(str, valores.values()))) <= 1,
                       "valores": valores})
    return salida
