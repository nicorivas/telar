"""Agentes residentes: carpetas de un repositorio donde vive un agente con su memoria y su bitácora.

Con `[agentes] carpeta = "agentes"`, cada subcarpeta de esa carpeta que tenga un `CLAUDE.md` es un
agente (las que empiezan con `_` o `.`, como una plantilla, no). telar lo muestra como una sección
más de la lista, dentro del grupo «agentes»: sus hilos debajo y un home que telar arma solo, sin
que el agente escriba nada:

    quién es     el primer párrafo de su CLAUDE.md
    bitácora     sus entradas, la más nueva arriba («## AAAA-MM-DD HH:MM — título» con su cuerpo,
                 o una línea «AAAA-MM-DD HH:MM — texto» por encargo)
    memoria      el índice memoria/MEMORY.md, cada recuerdo con su archivo
    archivos     CLAUDE.md, README.md, bitácora e índice, para abrirlos

Sus hilos son el que lleva su nombre, los vinculados a su carpeta (no a una subcarpeta) y los que declare
`[agentes.<carpeta>] hilos` (un nombre exacto, o un prefijo si termina en `*`). `[agentes.<carpeta>]
home` es un comando que imprime una página (docs/contratos.md): sus bloques van arriba de los que
arma telar. El nombre del agente es el título del README de su carpeta, o el de la carpeta.

Un agente parte en su carpeta, no donde diga `[agente] carpeta`: así carga su CLAUDE.md al arrancar.

Su definición, si la tiene, es un `agente.toml` al lado de su CLAUDE.md (docs/propuestas/agente-como-definicion.md):

    nombre = "Faro"          pisa el título del README
    para = "…"               cuándo encargarle algo, en una o dos frases
    modelo = "opus"          el modelo de su sesión, si el motor sabe elegirlo (`argumentos_de`)
    residente = false        el nodo no le abre la sesión solo cuando le llega algo (por defecto, true)

`instrucciones`, `memoria`, `capacidades`, `politica` y `lugar` se aceptan y se muestran, todavía sin uso.
Sin el archivo todo es como antes. Uno con errores no apaga al agente: lo que no se lee se ignora y queda
en `problemas`, que muestran `telar agentes` y `telar doctor`.
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

#: el prefijo de la clave de sección de un agente: `agente:gestion`
PREFIJO = "agente:"
#: cuántas entradas de bitácora muestra el home, y cuánto de cada cuerpo
ENTRADAS = 40
CUERPO = 1200

_ENTRADA = re.compile(r"^(?:#{2,3}\s+|-\s+)?(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?\s*[—–-]\s*(.+?)\s*$")
#: el archivo de su definición, al lado de su CLAUDE.md
DEFINICION = "agente.toml"
#: los campos que telar usa hoy, y los que acepta y muestra sin usarlos todavía (primitivas.md, «Qué es un agente»)
USADOS = ("nombre", "para", "modelo", "residente")
SIN_USO = ("instrucciones", "memoria", "capacidades", "politica", "lugar")
#: «una o dos frases»: más que esto se acepta, con aviso
PARA_LARGO = 300

def _con_control(texto: str) -> bool:
    """Si trae caracteres de control (un NUL, un ESC, un tabulador): llegan por los escapes de TOML
    (`\\u0000`) y terminarían en el argv de su sesión, en el nombre de su ventana o crudos en la terminal."""
    return any(unicodedata.category(c) == "Cc" for c in texto)


def ficha(nombre: str) -> str:
    """El nombre como lo ven el bus y la casilla (bus.ficha): «FARO», «Faro.» y «faro» son el mismo."""
    from telar import casilla

    return casilla.nombre_de_carpeta(nombre)


_RECUERDO = re.compile(r"^\s*[-*]\s+\[([^\]]+)\]\(([^)]+)\)\s*(?:[—–-]\s*(.*))?$")


@dataclass(frozen=True)
class Agente:
    clave: str
    nombre: str
    carpeta: Path
    hilos: tuple[str, ...] = ()
    home: tuple[str, ...] = ()
    argumentos: tuple[str, ...] = ()
    #: dónde vive, si no es donde dice `[agentes] en` (ver config.AgenteExtra.en)
    en: str = ""
    # lo que dice su agente.toml (`definicion`, si lo tiene); sin él, los valores de siempre
    para: str = ""
    modelo: str = ""
    residente: bool = True
    definicion: Path | None = None
    #: el nombre que tendría sin agente.toml (el del README o la carpeta): si difiere, se renombró
    nombre_de_antes: str = ""
    #: los campos declarados que telar todavía no usa, tal cual
    sin_uso: dict = field(default_factory=dict, compare=False, hash=False)
    #: lo que no se pudo leer o se ignoró de su agente.toml, una frase por cosa
    problemas: tuple[str, ...] = ()

    @property
    def seccion(self) -> str:
        return PREFIJO + self.clave


def base(config) -> Path | None:
    carpeta = getattr(config, "agentes_carpeta", "")
    if not carpeta:
        return None
    ruta = Path(carpeta).expanduser()
    return ruta if ruta.is_absolute() else Path(config.raiz) / ruta


def _nombre(carpeta: Path) -> str:
    try:
        primera = next((l for l in (carpeta / "README.md").read_text(encoding="utf-8").splitlines() if l.startswith("# ")), "")
    except OSError:
        primera = ""
    nombre = primera[2:].strip().strip("`").rstrip("/").strip()
    return nombre if nombre and nombre.lower() != carpeta.name.lower() else carpeta.name.capitalize()


def leer_definicion(carpeta: Path) -> tuple[dict, tuple[str, ...]]:
    """Lo válido de su agente.toml (campo → valor, solo los que vienen bien) y los problemas. ({}, ()) sin archivo.

    Blando a propósito: esto corre en el nodo, y una coma de más no puede callar al agente en todas las
    máquinas. Un TOML que no se lee se ignora entero; un campo mal, solo; una clave desconocida, con aviso."""
    ruta = carpeta / DEFINICION
    if not ruta.is_file():
        return {}, ()
    try:
        # utf-8-sig: algunos editores lo guardan con BOM, y sin esto el TOML entero no se leería
        datos = tomllib.loads(ruta.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        return {}, (f"{DEFINICION} no se lee ({e}): se ignora entero",)
    valido: dict = {}
    problemas: list[str] = []
    for clave, valor in datos.items():
        if clave == "nombre":
            if isinstance(valor, str) and valor.strip() and not _con_control(valor.strip()) and len(valor.strip()) <= 60:
                valido[clave] = valor.strip()
            else:
                problemas.append(f"nombre: se esperaba un texto de una línea (hasta 60, sin caracteres de control), "
                                 f"llegó {valor!r}: se ignora")
        elif clave == "para":
            if isinstance(valor, str) and _con_control(" ".join(valor.split())):
                # los saltos de línea y los tabuladores ya se volvieron espacios: lo que queda (un ESC) pintaría la terminal
                problemas.append(f"para: trae caracteres de control, llegó {valor!r}: se ignora")
            elif isinstance(valor, str):
                valido[clave] = " ".join(valor.split())
                if len(valido[clave]) > PARA_LARGO:
                    problemas.append(f"para: {len(valido[clave])} caracteres; se pensó para una o dos frases")
            else:
                problemas.append(f"para: se esperaba un texto, llegó {valor!r}: se ignora")
        elif clave == "modelo":
            # libre: los nombres de los modelos cambian más rápido que telar. Solo que no parezca una bandera
            if isinstance(valor, str) and valor.strip() and not valor.strip().startswith("-") \
                    and not re.search(r"\s", valor.strip()) and not _con_control(valor):
                valido[clave] = valor.strip()
            else:
                problemas.append(f"modelo: se esperaba un nombre sin espacios, llegó {valor!r}: se ignora")
        elif clave == "residente":
            if isinstance(valor, bool):
                valido[clave] = valor
            else:
                problemas.append(f"residente: se esperaba true o false, llegó {valor!r}: se ignora")
        elif clave == "instrucciones":
            if isinstance(valor, str) and not _con_control(valor):
                valido[clave] = valor
            else:
                problemas.append(f"instrucciones: se esperaba la ruta de un archivo, llegó {valor!r}: se ignora")
        elif clave in SIN_USO:
            if isinstance(valor, dict):
                valido[clave] = valor
            else:
                problemas.append(f"{clave}: se esperaba una tabla ([{clave}]), llegó {valor!r}: se ignora")
        else:
            problemas.append(f"{clave}: no lo conozco (¿de un telar más nuevo?): se ignora")
    return valido, tuple(problemas)


def descubrir(config, vinculos: dict[str, str] | None = None) -> list[Agente]:
    """Los agentes del repositorio. `vinculos` (hilo → carpeta relativa a la raíz) suma sus hilos."""
    b = base(config)
    if b is None or not b.is_dir():
        return []
    extras = {s.clave: s for s in getattr(config, "agentes_extra", ())}
    raiz = Path(config.raiz)
    salida = []
    carpetas = [d for d in sorted(b.iterdir(), key=lambda x: x.name)
                if d.is_dir() and not d.name.startswith(("_", ".")) and (d / "CLAUDE.md").is_file()]
    de_siempre = {d.name: _nombre(d) for d in carpetas}
    for d in carpetas:
        de_antes = de_siempre[d.name]
        definido, problemas = leer_definicion(d)
        nombre = definido.get("nombre", de_antes)
        # por su ficha, no por el texto: el bus y la casilla ven «FARO», «Faro.» y «faro» como el mismo hilo
        tomados = {ficha(x) for a in salida for x in (a.nombre, a.clave)} | \
                  {ficha(x) for c, n in de_siempre.items() if c != d.name for x in (n, c)}
        if nombre != de_antes and ficha(nombre) in tomados:
            # dos con el mismo nombre serían un solo hilo (una casilla, una clave en el bus): el segundo se
            # queda con el suyo de antes
            problemas = (*problemas, f"nombre: «{nombre}» ya es de otro agente; se queda con «{de_antes}»")
            nombre = de_antes
        extra = extras.get(d.name)
        hilos = [nombre, *(extra.hilos if extra else ())]
        real = d.resolve()
        for hilo, rel in (vinculos or {}).items():
            try:
                destino = (raiz / rel).resolve()
            except OSError:
                continue
            # solo el vínculo a su casa: un proyecto que vive en una subcarpeta suya no es él
            if destino == real and hilo not in hilos:
                hilos.append(hilo)
        salida.append(Agente(clave=d.name, nombre=nombre, carpeta=d, hilos=tuple(hilos),
                             home=tuple(extra.home) if extra else (), argumentos=tuple(extra.argumentos) if extra else (),
                             en=extra.en if extra else "",
                             para=definido.get("para", ""), modelo=definido.get("modelo", ""),
                             residente=definido.get("residente", True),
                             definicion=d / DEFINICION if (d / DEFINICION).is_file() else None,
                             nombre_de_antes=de_antes,
                             sin_uso={k: v for k, v in definido.items() if k in SIN_USO},
                             problemas=problemas))
    return salida


def argumentos_de(a: Agente, motor=None, *, con_config: bool = True) -> list[str]:
    """Lo que va después del prompt al abrir su sesión: el modelo que declara (si el motor sabe elegirlo)
    y los `argumentos` de esta máquina. Donde se pisan gana la máquina: si `argumentos` ya trae la
    bandera del modelo (`--model opus` o `--model=opus`), la del agente.toml no se agrega. Sin `con_config`,
    solo el modelo. Un motor sin `con_modelo` (uno de afuera, que cumple solo el Protocol) no elige modelo."""
    propios = list(a.argumentos) if con_config else []
    con_modelo = getattr(motor, "con_modelo", None) if motor is not None else None
    modelo = list(con_modelo(a.modelo)) if (con_modelo is not None and a.modelo) else []
    if modelo and any(x == modelo[0] or x.startswith(modelo[0] + "=") for x in a.argumentos):
        modelo = []
    return [*modelo, *propios]


def como_json(a: Agente) -> dict:
    """Lo que `telar agentes --json` dice de un agente (docs/contratos.md)."""
    import json

    from telar.objetos import direccion_de

    # lo que no se usa va tal cual, salvo lo que el JSON no tiene (una fecha de TOML): como texto
    sin_uso = json.loads(json.dumps(a.sin_uso, default=str))
    return {"clave": a.clave, "nombre": a.nombre, "direccion": direccion_de("agente", a.clave),
            "carpeta": str(a.carpeta), "definicion": str(a.definicion) if a.definicion else "",
            "para": a.para, "modelo": a.modelo, "residente": a.residente, "hilos": list(a.hilos),
            "en": a.en, "sin_uso": sin_uso, "problemas": list(a.problemas)}


def de_carpeta(config, carpeta: Path | None) -> Agente | None:
    """El agente cuya casa es exactamente esa carpeta, si hay uno (una subcarpeta suya es otra cosa)."""
    if carpeta is None:
        return None
    try:
        real = Path(carpeta).resolve()
    except OSError:
        return None
    for a in descubrir(config):
        if real == a.carpeta.resolve():
            return a
    return None


# ── el home ────────────────────────────────────────────────────────────────────

def _quien(carpeta: Path) -> str:
    """El primer párrafo de su CLAUDE.md: lo que dice de sí mismo antes de cualquier detalle."""
    try:
        lineas = (carpeta / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    parrafo: list[str] = []
    for l in lineas:
        if l.startswith(("#", "@")) or not l.strip():
            if parrafo:
                break
            continue
        parrafo.append(l.strip())
    return " ".join(parrafo)


def bitacora(carpeta: Path) -> list[dict]:
    """Las entradas de su bitácora, la más nueva primero."""
    try:
        lineas = (carpeta / "bitacora.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entradas: list[dict] = []
    for l in lineas:
        m = _ENTRADA.match(l)
        if m:
            fecha = m.group(1) + (f"T{m.group(2)}" if m.group(2) else "")
            entradas.append({"titulo": m.group(3)[:160], "fecha": fecha, "texto": ""})
        elif entradas and not l.startswith("# "):
            entradas[-1]["texto"] += l + "\n"
    for e in entradas:
        cuerpo = e["texto"].strip()
        e["texto"] = cuerpo if len(cuerpo) <= CUERPO else cuerpo[:CUERPO].rstrip() + " […]"
        if not e["texto"]:
            del e["texto"]
    entradas.reverse()
    return entradas[:ENTRADAS]


def memoria(carpeta: Path) -> list[dict]:
    """El índice de su memoria: cada recuerdo con su archivo, para abrirlo."""
    indice = carpeta / "memoria" / "MEMORY.md"
    try:
        lineas = indice.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items = []
    for l in lineas:
        m = _RECUERDO.match(l)
        if not m:
            continue
        destino = m.group(2)
        item = {"titulo": m.group(1)}
        if m.group(3):
            item["texto"] = m.group(3).strip()
        if not re.match(r"^[a-z]+://", destino):
            destino = str((indice.parent / destino).resolve())
        item["enlace"] = destino
        items.append(item)
    return items


def pagina(a: Agente) -> dict:
    """El home de un agente, con la forma del contrato de una página (docs/contratos.md)."""
    from telar.ordenes.seccion import correr

    bloques: list[dict] = []
    subtitulo = ""
    if a.home:
        propia, problema = correr(a.home, f"el home de {a.nombre}")
        if propia:
            subtitulo = propia.get("subtitulo", "")
            bloques.extend(propia.get("bloques", []))
        else:
            bloques.append({"titulo": "su home", "texto": problema, "color": "rojo"})
    quien = _quien(a.carpeta)
    if quien and not a.home:
        bloques.insert(0, {"texto": quien})
    if a.para:
        # lo que declara su agente.toml: cuándo encargarle algo, arriba de todo
        bloques.insert(0, {"titulo": "para", "texto": a.para})
    entradas = bitacora(a.carpeta)
    bloques.append({"titulo": f"bitácora · {len(entradas)}" if entradas else "bitácora",
                    **({"items": entradas} if entradas else {"texto": "todavía nada: una línea por encargo en bitacora.md"})})
    recuerdos = memoria(a.carpeta)
    bloques.append({"titulo": f"memoria · {len(recuerdos)}" if recuerdos else "memoria",
                    **({"items": recuerdos} if recuerdos else {"texto": "su índice, memoria/MEMORY.md, está vacío"})})
    archivos = [(n, a.carpeta / r) for n, r in (("CLAUDE.md: quién es", "CLAUDE.md"), ("README.md: su mapa", "README.md"),
                                                ("bitácora", "bitacora.md"), ("índice de su memoria", "memoria/MEMORY.md"),
                                                ("agente.toml: su definición", DEFINICION))]
    bloques.append({"titulo": "archivos", "items": [{"titulo": n, "enlace": str(r)} for n, r in archivos if r.exists()]})
    return {"titulo": a.nombre, "subtitulo": subtitulo or str(a.carpeta), "bloques": bloques}
