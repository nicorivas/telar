"""Lo que todas las órdenes necesitan: leer el telar, escribirlo y decirlo.

Aquí no hay ninguna orden. Hay cuatro cosas:

  * **argumentos** — un `argparse` que no mata el proceso, porque quien decide el
    código de salida es la orden, no la biblioteca;
  * **el telar** — juntar en un solo lugar lo que dice el multiplexor, lo que
    guarda el estado y lo que dicen los documentos, y que se pueda leer aunque no
    haya multiplexor vivo;
  * **el JSON** — cada `--json` es un contrato con quien lo consuma (una barra, un
    editor, otro agente), y los contratos se escriben en un solo sitio:
    `docs/contratos.md`;
  * **decirlo en la terminal** — con color solo si hay a quién mostrárselo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from telar import estado as mod_estado
from telar import lectura
from telar import salida as mod_salida
from telar.modelo import Atencion, Ficha, Hilo, Item, Pendiente, Prioridad
from telar.mux import ErrorDeMux, Multiplexor
from telar.mux import obtener as obtener_mux
from telar.perfil import Arquetipo

__all__ = [
    "Analizador",
    "ErrorDeUso",
    "Telar",
    "queja",
    "parsear",
    "tejer",
    "hilo_actual",
    "resolver",
    "hilo_o_nombre",
    "enrutar",
    "escribir_json",
    "json_hilo",
    "json_ficha",
    "json_item",
    "json_pendiente",
    "duracion",
    "ruta_relativa",
]

#: La variable con que un hilo se identifica a sí mismo ante telar.
VARIABLE_HILO = "TELAR_HILO"


# ── argumentos ──────────────────────────────────────────────────────────────────

class ErrorDeUso(Exception):
    """Los argumentos de una orden no cuadran. La orden decide qué hacer."""


class _Salir(Exception):
    def __init__(self, codigo: int) -> None:
        self.codigo = codigo


class Analizador(argparse.ArgumentParser):
    """`argparse` que no llama a `sys.exit`: una orden devuelve su código, no lo impone."""

    def error(self, message: str):  # noqa: D102 - el de argparse
        raise ErrorDeUso(message)

    def exit(self, status: int = 0, message: str | None = None):  # noqa: D102
        if message:
            (sys.stdout if status == 0 else sys.stderr).write(message)
        raise _Salir(status)


def analizador(orden: str, descripcion: str) -> Analizador:
    return Analizador(
        prog=f"telar {orden}",
        description=descripcion,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def parsear(p: Analizador, argv: list[str]) -> tuple[argparse.Namespace | None, int]:
    """`(opciones, 0)` si se entendió; `(None, código)` si hay que salir ya."""
    try:
        return p.parse_args(argv), 0
    except ErrorDeUso as e:
        print(f"telar {p.prog.removeprefix('telar ')}: {e}", file=sys.stderr)
        print(f"Prueba: {p.prog} --help", file=sys.stderr)
        return None, 2
    except _Salir as e:
        return None, e.codigo


def queja(mensaje: str, codigo: int = 2) -> int:
    print(f"telar: {mensaje}", file=sys.stderr)
    return codigo


# ── color, solo si hay quién lo vea ─────────────────────────────────────────────

def _color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def tenue(texto: str) -> str:
    return f"\x1b[2m{texto}\x1b[0m" if _color() else texto


def fuerte(texto: str) -> str:
    return f"\x1b[1m{texto}\x1b[0m" if _color() else texto


#: Cómo se dibuja cada atención en una línea de terminal.
SIMBOLO = {
    Atencion.NINGUNA: " ",
    Atencion.TRABAJANDO: "●",
    Atencion.ESPERA: "○",
    Atencion.TERMINO: "✓",
}


def duracion(segundos: float) -> str:
    """`5400.0` → `1h30`. Vacío si no hay nada que decir."""
    minutos = int(segundos // 60)
    if minutos <= 0:
        return ""
    return f"{minutos // 60}h{minutos % 60:02d}" if minutos >= 60 else f"{minutos}m"


def recortar(texto: str, ancho: int, *, minimo: int = 12) -> str:
    """Corta a `ancho` y lo DICE con «…». Nunca deja el ancho en negativo.

    Cortar en silencio es mentir por omisión: quien ve «/private/tmp/…/sc» sabe que
    falta algo, quien ve «/private/tmp/claude-501/-Users» cree que eso es la ruta. Y un
    terminal angosto no debería vaciar la columna: por eso el mínimo.
    """
    tope = max(int(ancho), minimo)
    if len(texto) <= tope:
        return texto
    return texto[: max(tope - 1, 1)] + "…"


def plural(n: int, singular: str, plural_: str = "") -> str:
    """«1 hilo», «2 hilos». La prosa cuidada también cuenta cuando la escribe una máquina."""
    return f"{n} {singular if n == 1 else (plural_ or singular + 's')}"


def ruta_relativa(ruta: Path | None, raiz: Path) -> str:
    """La carpeta del hilo vista desde la raíz. Siempre relativa: es lo que promete el contrato.

    Un tab abierto fuera de la raíz —el caso más común, una shell en cualquier parte— no
    tiene una relativa «hacia abajo»; antes se devolvía la absoluta, y quien la pegaba
    detrás de la raíz terminaba con una ruta inventada. Ahora sale con `../`, que es
    relativa de verdad, y si ni eso se puede (otro volumen), queda vacía: no saber dónde
    está es mejor que decir que está en otro lado.
    """
    if ruta is None:
        return ""
    try:
        aqui, base = Path(ruta).resolve(), Path(raiz).resolve()
    except OSError:
        return ""
    try:
        return aqui.relative_to(base).as_posix()
    except ValueError:
        pass
    try:
        import os.path

        relativa = os.path.relpath(aqui, base)
    except (ValueError, OSError):
        return ""
    return Path(relativa).as_posix()


# ── el telar armado ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class Telar:
    """Todo lo que hay que saber para dibujar o actuar, leído una sola vez."""

    hilos: tuple[Hilo, ...] = ()
    #: nombres de hilos que el multiplexor reporta ahora mismo
    vivos: frozenset[str] = frozenset()
    sesion: str = ""
    viva: bool = False
    raiz: Path = field(default_factory=Path.cwd)
    #: multiplexor construido, o None si no se pudo (y entonces `aviso` dice por qué)
    mux: Multiplexor | None = None
    aviso: str = ""
    estado: mod_estado.Estado | None = None
    #: ruta relativa → (arquetipo, documento) de las unidades que declara el perfil
    unidades: dict[str, tuple[Arquetipo, Path]] = field(default_factory=dict)

    def por_nombre(self, nombre: str) -> Hilo | None:
        return next((h for h in self.hilos if h.nombre == nombre), None)

    def vivo(self, hilo: Hilo) -> bool:
        return hilo.nombre in self.vivos


def _mux(ctx) -> tuple[Multiplexor | None, str]:
    """El multiplexor, o el motivo por el que no lo hay. Nunca revienta."""
    try:
        mux = obtener_mux(ctx.config)
    except ErrorDeMux as e:
        return None, str(e)
    disponible = getattr(mux, "disponible", None)
    try:
        if disponible is not None and not disponible():
            return None, f"no encontré el programa {ctx.config.multiplexor} en el PATH"
    except ErrorDeMux as e:
        return None, str(e)
    return mux, ""


def tejer(ctx, *, con_ficha: bool = True, todos: bool = True) -> Telar:
    """Arma el telar: multiplexor + estado + documentos.

    `todos` agrega los hilos que el estado conoce pero el multiplexor no muestra
    (archivados, o de una sesión que todavía no se levanta): con un multiplexor
    caído la lista sigue sirviendo, y se ve cuál está vivo y cuál no. `con_ficha`
    lee el documento de cada hilo vinculado, que es lo único caro de todo esto.
    """
    config = ctx.config
    est = mod_estado.abrir(config)
    mux, aviso = _mux(ctx)

    crudos: list[Hilo] = []
    viva = False
    if mux is not None:
        try:
            viva = mux.viva()
            crudos = list(mux.hilos()) if viva else []
        except ErrorDeMux as e:
            aviso = str(e)

    # antes de leer nada: si un tab cambió de nombre en el multiplexor, el estado lo sigue
    if crudos:
        try:
            huella = mux.huella() if mux is not None else ""
        except ErrorDeMux:
            huella = ""
        for viejo, nuevo in est.reconciliar(crudos, huella):
            aviso = aviso or f"«{viejo}» ahora se llama «{nuevo}»: moví su vínculo y su estado"

    vivos = frozenset(h.nombre for h in crudos)
    # una sola lectura y bajo candado: si no, se dibuja media lista de antes y media de
    # después mientras otra sesión escribe. Para eso existe `Estado.foto`.
    foto = est.foto(tope=config.intervalos.foco_maximo)
    vinculos = foto["vinculos"]
    archivados = foto["archivados"]

    if todos:
        # un hilo que telar conoce es el que tiene carpeta, el archivado y también el que
        # tiene una conversación anotada: si no, una conversación traída de otra parte
        # queda guardada y sin forma de verla ni de retomarla desde la lista
        conocidos = sorted((set(vinculos) | set(archivados) | set(foto["sesiones"])) - vivos)
        # sin multiplexor, el id es el nombre: es la única llave que hay
        crudos += [Hilo(id=nombre, nombre=nombre) for nombre in conocidos]

    hilos = mod_estado.vestir(crudos, raiz=config.raiz, **foto)

    unidades: dict[str, tuple[Arquetipo, Path]] = {}
    if con_ficha:
        unidades = lectura.indice(ctx.perfil, config.raiz)
        hilos = tuple(_con_ficha(h, ctx, unidades) for h in hilos)

    return Telar(
        hilos=hilos,
        vivos=vivos,
        sesion=config.sesion,
        # con un aviso de por medio no se declara viva: el contrato dice que entonces
        # los hilos son los que telar recuerda, y eso es justo lo que se está dibujando
        viva=viva and not aviso,
        raiz=config.raiz,
        mux=mux,
        aviso=aviso,
        estado=est,
        unidades=unidades,
    )


def _lineas_foco(est: mod_estado.Estado) -> list[str]:
    ruta = est.ruta(mod_estado.FOCO)
    try:
        return ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def asegurar_proveedores(config) -> None:
    """Importa los proveedores declarados que todavía no se han registrado.

    Un proveedor se registra a sí mismo al importarse, y nadie importa un módulo
    que la configuración nombró: sin esto, `[proveedores.calendario]` queda
    declarado y ausente. El que no existe se calla aquí; quien lo pida se encuentra
    con el «no hay un proveedor llamado …» de siempre, que ya lo dice bien.
    """
    import importlib

    from telar import proveedores

    for nombre in config.proveedores:
        if nombre in proveedores.REGISTRO:
            continue
        try:
            importlib.import_module(f"telar.proveedores.{nombre}")
        except ModuleNotFoundError:
            continue
        except Exception:  # noqa: BLE001 - un proveedor ajeno no tiene por qué ser prolijo
            continue


def fuente_ficha(config=None):
    """El proveedor que arma las fichas, según `[ficha]`. None si no se pudo construir.

    Sin configuración, el de siempre: `documento`, con sus opciones por defecto.
    """
    try:
        from telar.proveedores import estado as prov_estado
    except ImportError:  # pragma: no cover - mientras el proveedor no exista
        return None
    cfg = getattr(config, "ficha", None)
    if cfg is None:
        return prov_estado.Documento()
    try:
        return prov_estado.obtener(cfg)
    except Exception:  # noqa: BLE001 - una configuración rota no apaga la ficha
        return prov_estado.Documento()


def leer_ficha(documento: Path, arquetipo: Arquetipo, fuente=None) -> Ficha:
    """La ficha de un documento, por el proveedor de estado que declare `[ficha]`.

    `telar.lectura` cumple lo que el perfil declaró; el proveedor decide además qué
    significa cada sección (el resumen, las esperas, los hitos). `fuente` es el
    proveedor ya construido —`fuente_ficha(config)`— para no rehacerlo por documento.
    Si no está o se cae, se lee lo declarado y el telar sigue: un proveedor nunca
    apaga nada.
    """
    if fuente is None:
        fuente = fuente_ficha()
    if fuente is None:
        return lectura.leer(documento, arquetipo)
    try:
        return fuente.leer(documento, arquetipo).a_ficha()
    except Exception:  # noqa: BLE001 - un proveedor ajeno no tiene por qué ser prolijo
        return lectura.leer(documento, arquetipo)


def ficha_suelta(ruta: Path) -> Ficha | None:
    """La ficha de una carpeta que el perfil no declara: su README y el título que traiga.

    Sin arquetipo no hay secciones que buscar, así que no hay estado ni pendientes; pero
    el documento existe y se puede leer, y eso es mejor que decir «sin ficha».
    """
    ruta = Path(ruta)
    documento = ruta if ruta.is_file() else next(
        (ruta / n for n in ("README.md", "readme.md", "README.markdown", "README") if (ruta / n).is_file()), None)
    if documento is None:
        return None
    try:
        texto = documento.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    titulo = next((l[2:].strip() for l in texto.splitlines() if l.startswith("# ")), "")
    return Ficha(documento=documento, titulo=titulo,
                 nota="fuera del perfil: solo su README, sin estado ni pendientes")


def _con_ficha(hilo: Hilo, ctx, unidades: dict[str, tuple[Arquetipo, Path]]) -> Hilo:
    if hilo.ruta is None:
        return hilo
    arquetipo, documento = lectura.ubicar(ctx.perfil, ctx.config.raiz, hilo.ruta, mapa=unidades)
    if (arquetipo is None or documento is None) and hilo.vinculo is not None:
        suelta = ficha_suelta(hilo.vinculo)
        if suelta is not None:
            return replace(hilo, ficha=suelta)
    if arquetipo is None or documento is None:
        relativa = ruta_relativa(hilo.ruta, ctx.config.raiz)
        return replace(
            hilo,
            ficha=Ficha(nota=f"«{relativa}» no es ninguna unidad que declare el perfil"),
        )
    fuente = fuente_ficha(ctx.config)
    ficha = leer_ficha(documento, arquetipo, fuente)
    if ficha is not None:
        ficha = replace(ficha, etiqueta=lectura.etiqueta(arquetipo.etiqueta, ficha))
    return replace(hilo, arquetipo=arquetipo.nombre, ficha=ficha)


# ── encontrar un hilo ───────────────────────────────────────────────────────────

def sin_hilo(orden: str, tel=None) -> int:
    """La queja de «no sé en qué hilo estoy», con los nombres que hay a mano.

    Decir «usa --hilo» sin decir cuáles existen deja al recién llegado adivinando: los
    nombres los pone el multiplexor y el primero suele ser «Tab #1».
    """
    nombres = [h.nombre for h in getattr(tel, "hilos", ())][:8] if tel is not None else []
    pista = f"\n  los hay: {', '.join(nombres)}" if nombres else ""
    return queja(
        f"no sé en qué hilo estoy. Dime cuál: telar {orden} --hilo <hilo>"
        f"{pista}\n  (dentro de la sesión no hace falta: el hilo se sabe solo)"
    )


def hilo_actual(tel: Telar) -> Hilo | None:
    """El hilo desde donde se está corriendo esto.

    Primero `$TELAR_HILO`, que es el contrato: el multiplexor exporta el nombre del
    hilo al abrirlo y lo hereda todo lo que corra adentro. Recién después, el hilo
    con el foco — que es una suposición, y de las que muerden: el foco lo mueve la
    persona mientras un agente trabaja en otro lado, así que actuar sobre el hilo
    con foco renombra o archiva el hilo equivocado.
    """
    nombre = os.environ.get(VARIABLE_HILO, "").strip()
    if nombre:
        return tel.por_nombre(nombre) or Hilo(id=nombre, nombre=nombre)
    if tel.mux is None:
        return None
    try:
        activo = tel.mux.activo()
    except ErrorDeMux:
        return None
    return tel.por_nombre(activo.nombre) if activo else None


def seguro(tel: Telar) -> bool:
    """¿La identificación del hilo actual es del propio proceso, o es el foco?"""
    return bool(os.environ.get(VARIABLE_HILO, "").strip())


def hilo_o_nombre(tel: Telar, referencia: str) -> tuple[Hilo | None, str]:
    """El hilo que se llama exactamente así, o uno recién nombrado con ese nombre.

    Vale para las órdenes que ANOTAN algo: un hilo puede existir antes de que telar
    lo vea —el multiplexor no está levantado, o el hilo se va a abrir en un minuto— y
    negarse a anotarlo por desconocido es perder justo el primer dato. Devuelve
    además el aviso que corresponde decir, si el hilo no estaba.
    """
    exacto = next((h for h in tel.hilos if h.id == referencia or h.nombre == referencia), None)
    if exacto is not None:
        return exacto, ""
    # a propósito NO se busca por prefijo ni por subcadena: esto lo usan las órdenes que
    # escriben, y un nombre nuevo que resulta ser parte de otro le cambiaría la carpeta al
    # hilo equivocado («Gobernanza» calzaba con «santander-gobernanza-ia»). Para navegar
    # —`ir`, `ficha`— sí vale aproximar: ahí no se anota nada.
    return Hilo(id=referencia, nombre=referencia), f"«{referencia}» no estaba en la lista"


def resolver(tel: Telar, referencia: str) -> tuple[Hilo | None, str]:
    """El hilo que nombra `referencia`: su id, su nombre exacto, o un prefijo único."""
    if not referencia:
        return None, "no dijiste qué hilo"
    exactos = [h for h in tel.hilos if h.id == referencia or h.nombre == referencia]
    if exactos:
        return exactos[0], ""
    ref = referencia.casefold()
    parecidos = [h for h in tel.hilos if h.nombre.casefold().startswith(ref)]
    if not parecidos:
        parecidos = [h for h in tel.hilos if ref in h.nombre.casefold()]
    if len(parecidos) == 1:
        return parecidos[0], ""
    if not parecidos:
        return None, f"no hay ningún hilo que se llame «{referencia}»"
    nombres = ", ".join(h.nombre for h in parecidos[:6])
    return None, f"«{referencia}» calza con varios hilos: {nombres}"


# ── el JSON, que es el contrato ─────────────────────────────────────────────────

def escribir_json(datos) -> int:
    """Una línea de JSON en la salida, y nada más. Documentado en docs/contratos.md.

    Se escribe en UTF-8 mientras la salida lo admita, porque se lee mejor. Si no lo
    admite, se escapa (`\\uXXXX`) en vez de transliterar: al consumidor le llega el
    mismo texto, y un contrato no se degrada para que se vea bonito en la terminal.
    """
    cuerpo = json.dumps(datos, ensure_ascii=False, default=str)
    if not mod_salida.alcanza(cuerpo):
        cuerpo = json.dumps(datos, ensure_ascii=True, default=str)
    print(cuerpo)
    return 0


def _iso(momento: datetime | None) -> str | None:
    return momento.isoformat(timespec="seconds") if momento else None


def json_ficha(ficha: Ficha | None, raiz: Path) -> dict | None:
    if ficha is None:
        return None
    return {
        "documento": str(ficha.documento) if ficha.documento else "",
        "relativo": ruta_relativa(ficha.documento, raiz),
        "titulo": ficha.titulo,
        "etiqueta": ficha.etiqueta,
        "estado": ficha.estado,
        "pendientes": [json_pendiente(p) for p in ficha.pendientes],
        "secciones": {k: _valor_json(v) for k, v in ficha.secciones.items()},
        "leida": _iso(ficha.leida),
        "nota": ficha.nota,
        "vacia": ficha.vacia,
    }


def _valor_json(valor):
    if isinstance(valor, tuple):
        return [_valor_json(v) for v in valor]
    if isinstance(valor, Pendiente):
        return json_pendiente(valor)
    return valor


def json_pendiente(p: Pendiente, *, ref: str = "", hilo: str = "") -> dict:
    cuerpo = {
        "texto": p.texto,
        "hecho": p.hecho,
        "en_curso": p.en_curso,
        "id": p.id,
        "origen": p.origen,
    }
    if ref:
        cuerpo["ref"] = ref
    if hilo:
        cuerpo["hilo"] = hilo
    return cuerpo


def json_hilo(hilo: Hilo, tel: Telar, *, con_ficha: bool = True) -> dict:
    cuerpo = {
        "id": hilo.id,
        "nombre": hilo.nombre,
        "vivo": tel.vivo(hilo),
        "activo": hilo.activo,
        "archivado": hilo.archivado,
        "vinculado": hilo.vinculado,
        "ruta": str(hilo.ruta) if hilo.ruta else "",
        "relativa": ruta_relativa(hilo.ruta, tel.raiz),
        "arquetipo": hilo.arquetipo,
        "prioridad": int(hilo.prioridad) if hilo.prioridad else None,
        "atencion": hilo.atencion.value,
        "visto": _iso(hilo.visto),
        "tiempo": round(hilo.tiempo, 1),
        "sesiones": list(hilo.sesiones),
        "remoto": hilo.remoto,
    }
    if con_ficha:
        cuerpo["ficha"] = json_ficha(hilo.ficha, tel.raiz)
    return cuerpo


def json_item(item: Item) -> dict:
    return {
        "proveedor": item.proveedor,
        "id": item.id,
        "titulo": item.titulo,
        "cuando": _iso(item.cuando),
        "hilo": item.hilo,
        "url": item.url,
        "datos": item.datos,
    }


def json_prioridad(valor: Prioridad | None) -> int | None:
    return int(valor) if valor else None


# ── a qué hilo le toca una cosa ────────────────────────────────────────────────

_PALABRA = re.compile(r"[^0-9a-záéíóúüñ]+")


def _norma(texto: str) -> str:
    return _PALABRA.sub("", texto.casefold())


def _calza_etiqueta(etiqueta: str, nombre: str, relativa: str) -> int:
    """2 si la etiqueta ES el hilo; 1 si es el comienzo de su carpeta; 0 si no.

    `#faro` calza con el hilo «Faro» y con `proyectos/faro`; `#faro-norte` no calza
    con `faro`, y `#faro` no calza con `proyectos/viejo-faro`: una etiqueta que
    empieza donde empieza el nombre es una pista, una que aparece en el medio es una
    coincidencia.
    """
    hoja = relativa.strip("/").rsplit("/", 1)[-1] if relativa else ""
    if _norma(etiqueta) in (_norma(nombre), _norma(hoja)):
        return 2
    partes, partes_hoja = etiqueta.split("-"), hoja.split("-")
    if hoja and len(partes) < len(partes_hoja) and partes_hoja[: len(partes)] == partes:
        return 1
    if "-" not in etiqueta and len(etiqueta) >= 4:
        if _norma(etiqueta) in {_norma(w) for w in re.findall(r"\w+", nombre)}:
            return 1
    return 0


def enrutar(tel: Telar, texto: str, *, hilo: str = "", limite_etiqueta: int = 3) -> Hilo | None:
    """A qué hilo le toca un texto suelto (un pendiente, un ítem de un proveedor).

    Por orden: el hilo que el propio texto declara; el hilo cuya carpeta aparece
    escrita en el texto (la más específica gana); el hilo que una etiqueta `#así`
    nombra. Empates: primero el que está vivo, después el que se miró hace menos.

    Una etiqueta que calza con muchos hilos no decide nada y se descarta: es una
    palabra del vocabulario de la casa, no un destino.
    """
    if hilo:
        elegido, _ = resolver(tel, hilo)
        if elegido is not None:
            return elegido

    etiquetas = [t.casefold() for t in re.findall(r"#([\w-]+)", texto)]
    candidatos: list[tuple[int, int, bool, datetime, Hilo]] = []
    calces: dict[str, int] = {}
    for h in tel.hilos:
        relativa = ruta_relativa(h.ruta, tel.raiz)
        peso_ruta = 0
        if relativa and re.search(rf"(?<![\w/.-]){re.escape(relativa)}(?=[/\s)\],]|$)", texto):
            peso_ruta = len(relativa)
        peso_tag = max((_calza_etiqueta(t, h.nombre, relativa) for t in etiquetas), default=0)
        if peso_tag:
            for t in etiquetas:
                if _calza_etiqueta(t, h.nombre, relativa):
                    calces[t] = calces.get(t, 0) + 1
        if peso_ruta or peso_tag:
            candidatos.append(
                (peso_ruta, peso_tag, tel.vivo(h), h.visto or datetime.min, h)
            )

    genericas = {t for t, cuantos in calces.items() if cuantos > limite_etiqueta}
    if genericas:
        candidatos = [c for c in candidatos if c[0] or not _solo_genericas(c[4], tel, etiquetas, genericas)]
    if not candidatos:
        return None
    return max(candidatos, key=lambda c: (c[0], c[1], c[2], c[3]))[4]


def _solo_genericas(hilo: Hilo, tel: Telar, etiquetas: list[str], genericas: set[str]) -> bool:
    relativa = ruta_relativa(hilo.ruta, tel.raiz)
    utiles = [t for t in etiquetas if t not in genericas and _calza_etiqueta(t, hilo.nombre, relativa)]
    return not utiles
