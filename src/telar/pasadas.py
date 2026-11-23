"""Las pasadas de un resultado: lo que deja cada vez una skill que corre varias veces al día, una lista por día,
y hasta cuál vio la persona (`pasadas` en su `[vistas.<clave>]`).

    [vistas.pulso]
    carpeta = "~/.local/state/telar/pulso"
    en = "servidor"          # la máquina donde vive: ahí se agrega, se lee y se marca lo visto
    pasadas = "pulso"        # el esquema de cada pasada: «pulso» (ver `validar`) o «libre» (solo su id)

Cada día es un `<prefijo>AAAA-MM-DD.json` en la carpeta, con `{"pasadas": [...]}` en el orden en que llegaron; se
lee como cualquier resultado (`telar resultado pulso [dia|ultimo]`, telar.resultados). El día de una pasada es el
de su `id` («2026-11-18T13:00», la hora local en que empezó), no el de cuando se agregó: la de las 23:30 que termina
pasada la medianoche es del día en que empezó.

- **Agregar** (`telar resultado pulso --agregar`, una pasada por la entrada estándar): se valida contra su esquema
  (lo que el esquema nombra, estricto; lo demás se guarda tal cual) y se agrega al final de su día, de forma
  atómica: bajo un candado de la carpeta, el día se reescribe entero en un temporal que reemplaza al de antes. Un
  id que ya está es un error; nunca se reescribe una pasada que ya está.
- **Importar** (`--agregar --desde archivo.jsonl`, una pasada por línea): todas se validan antes de escribir nada
  (una mala, y no entra ninguna); las que ya están, por id, se saltan. Se puede correr las veces que haga falta.
- **El mundo de cada cosa** (`[mundos]`, telar.mundos): cada tarea, lo que te espera, cada borrador y cada fuente de
  una pasada de pulso puede decir su `mundo`. Al leerlas, telar lo resuelve (`clasificar`): una tarea con dirección
  (`tarea:T580`; en un borrador, su `tarea`) es del mundo de la tarea misma (`mundos.de_tarea`), y ese manda; si no
  tiene dirección o la tarea no se clasifica, vale el que dijo el agente, si es uno declarado; si no, ninguno ("": sin
  clasificar, se ve en todos). Las vencidas sin propuesta, cada una por su tarea. Así se leen también las pasadas de
  antes, que no lo decían. Un mundo que no existe no rechaza la pasada: se avisa al agregarla y queda sin clasificar.
- **Lo visto**: hasta qué pasada vio la persona (su id y su día), en `visto.json` de la misma carpeta, en la máquina
  donde vive: así vale igual desde el laptop y desde el teléfono. Solo avanza: marcar una pasada más vieja que la
  vista no cambia nada (otra página, con lo de hace un rato, no la hace retroceder). Se marca por mundo: con un mundo
  puesto, quedan vistas lo de ese mundo y lo sin clasificar (`mundos` en el archivo); con ambos (sin mundo), todo
  (`id`, que vale para todos).
- **Sin ver**: las pasadas que tienen algo sin ver en algún mundo, de la más nueva a la más vieja (sin nada visto en un
  mundo, las del último día que hay), cada una con lo que no se ha visto (`sin_ver_en`). Lo que se ve de una pasada es
  lo que cambió (tareas nuevas, avanzadas y cerradas, y borradores, cada cosa con su causa: `por`); una que no cambió
  nada es sin clasificar y no cuenta. La página muestra las del mundo puesto (y las de lo sin clasificar); `para_mundo`
  arma lo que se ve de una con un mundo puesto.

Con `en` y bus, todo esto se le pide a esa máquina (pedidos `resultado-agregar`, `resultado-visto` y
`resultado-sin-ver` a su nodo). A diferencia de leer un día (telar.resultados), aquí no hay copia de respaldo: si esa
máquina no responde, se dice y no se escribe nada aquí (dos listas de lo visto se separarían).
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from telar.direcciones import _DIRECCION

#: los esquemas que una vista puede declarar en `pasadas`
ESQUEMAS = ("pulso", "libre")
#: el id de una pasada: la hora local en que empezó (con segundos si hacen falta para que sea única en el día)
ID = re.compile(r"(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}(?::\d{2})?")
DIA = re.compile(r"\d{4}-\d{2}-\d{2}")
#: lo que pesa una pasada como mucho, en JSON (una pasada es un reporte, no un archivo)
MAX_PASADA = 256 * 1024
#: cuántas pasadas sin ver se entregan enteras (`total` dice cuántas hay)
TOPE_SIN_VER = 40
#: cuántos días hacia atrás se miran para lo sin ver
DIAS_SIN_VER = 14
#: el archivo de lo visto y el candado, en la carpeta del resultado (no son días: telar.resultados no los lista)
VISTO = "visto.json"
CANDADO = ".pasadas.lock"

#: los valores que el esquema «pulso» acepta en cada campo con valores fijos
MODOS = ("dia", "noche")
PIDE = ("decidir", "aprobar", "cerrar", "hacer")
COMO = ("hecha", "caduca", "descartada")
#: los grupos de una pasada de pulso cuyas cosas llevan mundo, y el campo con la dirección de su tarea ("" si no tienen)
CON_MUNDO = (("fuentes", ""), ("tareas.nuevas", "id"), ("tareas.avanzadas", "id"), ("tareas.cerradas", "id"),
             ("te_esperan", "id"), ("borradores", "tarea"))
#: los grupos que son lo que cambió en una pasada: lo que muestra la página (cada cosa con su causa, `por`). Lo demás
#: (las fuentes, lo que te espera, las vencidas sin propuesta) se guarda y no es un cambio
CAMBIOS = ("tareas.nuevas", "tareas.avanzadas", "tareas.cerradas", "borradores")


class ErrorDePasada(Exception):
    """Una pasada que no cumple su esquema, o un día que no se pudo leer o escribir."""


# ── validar ───────────────────────────────────────────────────────────────────

class _Revision:
    """Junta lo que falla de una pasada, cada cosa con dónde está («tareas.nuevas[2].linea»)."""

    def __init__(self) -> None:
        self.errores: list[str] = []

    def mal(self, donde: str, que: str) -> None:
        self.errores.append(f"{donde}: {que}")

    def objeto(self, v: object, donde: str) -> dict | None:
        if not isinstance(v, dict):
            self.mal(donde, f"se esperaba un objeto, llegó {_tipo(v)}")
            return None
        return v

    def lista(self, d: dict, campo: str, donde: str) -> list:
        if campo not in d:
            self.mal(f"{donde}{campo}", "falta (una lista, aunque esté vacía)")
            return []
        if not isinstance(d[campo], list):
            self.mal(f"{donde}{campo}", f"se esperaba una lista, llegó {_tipo(d[campo])}")
            return []
        return d[campo]

    def texto(self, d: dict, campo: str, donde: str, *, vacio: bool = True, opcional: bool = False) -> str:
        if campo not in d:
            if not opcional:
                self.mal(f"{donde}{campo}", "falta")
            return ""
        v = d[campo]
        if not isinstance(v, str):
            self.mal(f"{donde}{campo}", f"se esperaba un texto, llegó {_tipo(v)}")
            return ""
        if not vacio and not v.strip():
            self.mal(f"{donde}{campo}", "está vacío")
        return v

    def uno_de(self, d: dict, campo: str, donde: str, valores: tuple[str, ...]) -> None:
        v = self.texto(d, campo, donde)
        if isinstance(d.get(campo), str) and v not in valores:
            self.mal(f"{donde}{campo}", f"{' | '.join(valores)}; llegó {v!r}")

    def entero(self, d: dict, campo: str, donde: str, minimo: int, maximo: int | None = None) -> None:
        if campo not in d:
            self.mal(f"{donde}{campo}", "falta")
            return
        v = d[campo]
        # True es un int en Python: aquí no vale como número
        if not isinstance(v, int) or isinstance(v, bool):
            self.mal(f"{donde}{campo}", f"se esperaba un número entero, llegó {_tipo(v)}")
        elif v < minimo or (maximo is not None and v > maximo):
            self.mal(f"{donde}{campo}", f"de {minimo} a {maximo}; llegó {v}" if maximo is not None else f"desde {minimo}; llegó {v}")

    def booleano(self, d: dict, campo: str, donde: str) -> None:
        if campo in d and not isinstance(d[campo], bool):
            self.mal(f"{donde}{campo}", f"true o false; llegó {_tipo(d[campo])}")


def _tipo(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return {dict: "un objeto", list: "una lista", str: "un texto", int: "un número", float: "un número"}.get(type(v), type(v).__name__)


def _hora(v: str) -> bool:
    """Si es una fecha con hora que se lee (ISO: «2026-11-18T13:12», con segundos o zona si se quiere)."""
    try:
        datetime.fromisoformat(v)
    except ValueError:
        return False
    return "T" in v or " " in v


def dia_de(id_: str) -> str:
    """El día de una pasada, de su id; "" si el id no es uno."""
    m = ID.fullmatch(id_ or "")
    if not m:
        return ""
    try:
        datetime.fromisoformat(id_)
    except ValueError:
        return ""
    return m.group(1)


def _id(r: _Revision, p: dict) -> None:
    v = r.texto(p, "id", "")
    if isinstance(p.get("id"), str) and not dia_de(v):
        r.mal("id", f"la hora en que empezó, AAAA-MM-DDTHH:MM (con :SS si hace falta); llegó {v[:40]!r}")


def _pulso(r: _Revision, p: dict) -> None:
    """El esquema de una pasada de `pulso` (skill /pulso de un agente residente): lo que nombra se revisa estricto; lo que no, pasa."""
    _id(r, p)
    termino = r.texto(p, "termino", "")
    if isinstance(p.get("termino"), str) and not _hora(termino):
        r.mal("termino", f"la hora en que terminó, AAAA-MM-DDTHH:MM; llegó {termino[:40]!r}")
    r.uno_de(p, "modo", "", MODOS)
    r.booleano(p, "pedida", "")
    r.booleano(p, "seco", "")
    r.texto(p, "resumen", "", vacio=False)
    for i, f in enumerate(r.lista(p, "fuentes", "")):
        donde = f"fuentes[{i}]."
        if r.objeto(f, donde.rstrip(".")) is None:
            continue
        r.texto(f, "fuente", donde, vacio=False)
        r.entero(f, "llegaron", donde, 0)
        r.entero(f, "archivados", donde, 0)
        # por qué falló; sin él, o vacío, no falló
        r.texto(f, "error", donde, opcional=True)
        # lo que se dice de una fuente sin que haya fallado (la ventana que se miró, lo que se saltó): tenue
        r.texto(f, "nota", donde, opcional=True)
        r.texto(f, "mundo", donde, opcional=True)
    tareas = p.get("tareas")
    if "tareas" not in p:
        r.mal("tareas", "falta (un objeto con nuevas, avanzadas y cerradas)")
    elif r.objeto(tareas, "tareas") is not None:
        for grupo in ("nuevas", "avanzadas", "cerradas"):
            for i, t in enumerate(r.lista(tareas, grupo, "tareas.")):
                donde = f"tareas.{grupo}[{i}]."
                if r.objeto(t, donde.rstrip(".")) is None:
                    continue
                r.texto(t, "id", donde)
                r.texto(t, "linea", donde, vacio=False)
                _causa(r, t, donde)
                r.texto(t, "enlace", donde, opcional=True)
                r.texto(t, "mundo", donde, opcional=True)
                if grupo == "cerradas":
                    r.uno_de(t, "como", donde, COMO)
    # opcional (desde el 18-nov): se guarda y la página no lo muestra (lo que te espera está en Táctica, `telar esperas`)
    for i, e in enumerate(r.lista(p, "te_esperan", "") if "te_esperan" in p else []):
        donde = f"te_esperan[{i}]."
        if r.objeto(e, donde.rstrip(".")) is None:
            continue
        r.texto(e, "id", donde)
        r.uno_de(e, "pide", donde, PIDE)
        r.texto(e, "linea", donde, vacio=False)
        r.entero(e, "peso", donde, 1, 3)
        vence = r.texto(e, "vence", donde)
        if vence and not _fecha(vence):
            r.mal(f"{donde}vence", f"AAAA-MM-DD o vacío; llegó {vence[:20]!r}")
        r.texto(e, "mundo", donde, opcional=True)
    for i, b in enumerate(r.lista(p, "borradores", "")):
        donde = f"borradores[{i}]."
        if r.objeto(b, donde.rstrip(".")) is None:
            continue
        r.texto(b, "para", donde, vacio=False)
        for campo in ("asunto", "enlace", "tarea"):
            r.texto(b, campo, donde)
        _causa(r, b, donde)
        r.texto(b, "mundo", donde, opcional=True)
    # opcional: el resumen de cada mundo («trabajo»: una línea), para que `resumen` quede neutro (las cuentas) y la página
    # muestre solo los de los mundos que se ven
    if "resumenes" in p:
        res = r.objeto(p["resumenes"], "resumenes")
        for k, v in (res or {}).items():
            if not isinstance(v, str):
                r.mal(f"resumenes.{k}", f"se esperaba un texto, llegó {_tipo(v)}")
            elif not v.strip():
                r.mal(f"resumenes.{k}", "está vacío")
    # opcional: las tareas vencidas que nadie ha propuesto cerrar ni mover (pulso no las toca: solo las nombra), por su
    # dirección, en el orden en que se leen
    if "vencidas_sin_propuesta" in p:
        for i, v in enumerate(r.lista(p, "vencidas_sin_propuesta", "")):
            if not isinstance(v, str) or not _DIRECCION.fullmatch(v):
                que = f"llegó {v[:40]!r}" if isinstance(v, str) else f"llegó {_tipo(v)}"
                r.mal(f"vencidas_sin_propuesta[{i}]", f"una dirección (tarea:T405); {que}")


def _causa(r: _Revision, x: dict, donde: str) -> None:
    """Lo que causó un cambio: `por` (obligatorio, corto: «correo de Beto Soto», «minuta del 17-nov») y, si viene, la
    clave de su `fuente` (para su ícono). El `enlace` de la causa va aparte: en un borrador, `enlace` es el del borrador."""
    r.texto(x, "por", donde, vacio=False)
    r.texto(x, "fuente", donde, opcional=True)


def _fecha(v: str) -> bool:
    if not DIA.fullmatch(v):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


def nombrados(pasada: dict) -> list[tuple[str, str]]:
    """Los mundos que nombra una pasada de pulso, cada uno con dónde («te_esperan[0].mundo», «resumenes.trabajo»)."""
    salida = [(f"{grupo}[{i}].mundo", x["mundo"]) for grupo, i, x, _ in _cosas(pasada)
              if isinstance(x.get("mundo"), str) and x["mundo"].strip()]
    res = pasada.get("resumenes")
    if isinstance(res, dict):
        salida += [(f"resumenes.{k}", k) for k in res if k]
    return salida


def avisos(esquema: str, pasada: object, declarados: tuple[str, ...]) -> list[str]:
    """Lo que no rechaza una pasada pero se le dice a quien la escribe: un mundo que no está en `declarados` (queda sin
    clasificar). Sin mundos declarados, nada: ahí todo es sin clasificar."""
    if esquema != "pulso" or not isinstance(pasada, dict) or not declarados:
        return []
    return [f"{donde}: «{m}» no es un mundo de aquí ({', '.join(declarados)}); queda sin clasificar"
            for donde, m in nombrados(pasada) if m not in declarados]


def validar(esquema: str, pasada: object) -> list[str]:
    """Lo que falla de una pasada según su esquema, cada cosa con dónde está; vacío si sirve."""
    r = _Revision()
    if not isinstance(pasada, dict):
        return [f"una pasada es un objeto JSON; llegó {_tipo(pasada)}"]
    try:
        peso = len(json.dumps(pasada, ensure_ascii=False).encode())
    except (TypeError, ValueError) as e:
        return [f"no se puede escribir como JSON: {e}"]
    if peso > MAX_PASADA:
        return [f"pesa {peso // 1024} KB: una pasada llega hasta {MAX_PASADA // 1024} KB"]
    if esquema == "pulso":
        _pulso(r, pasada)
    elif esquema == "libre":
        _id(r, pasada)
    else:
        return [f"«{esquema}» no es un esquema de pasadas ({', '.join(ESQUEMAS)})"]
    return r.errores


# ── el mundo de cada cosa ─────────────────────────────────────────────────────

def _cosas(p: dict):
    """(grupo, índice, cosa, el campo con la dirección de su tarea) de cada cosa de una pasada que lleva mundo."""
    tareas = p.get("tareas") if isinstance(p.get("tareas"), dict) else {}
    for grupo, campo in CON_MUNDO:
        lista = tareas.get(grupo[len("tareas."):]) if grupo.startswith("tareas.") else p.get(grupo)
        if isinstance(lista, list):
            for i, x in enumerate(lista):
                if isinstance(x, dict):
                    yield grupo, i, x, campo


def _tarea(direccion: object) -> str:
    """El id de la tarea de una dirección (`tarea:T580` → T580); "" si no es la de una tarea."""
    m = _DIRECCION.fullmatch(direccion.strip()) if isinstance(direccion, str) else None
    return m.group("id") if m and m.group("tipo") == "tarea" and not m.group("maquina") else ""


def _vencidas(p: dict) -> list[str]:
    v = p.get("vencidas_sin_propuesta")
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def tareas_de(p: dict) -> set[str]:
    """Los ids de las tareas que nombra una pasada por su dirección (sus cosas y sus vencidas sin propuesta)."""
    ids = {_tarea(x.get(campo)) for _, _, x, campo in _cosas(p) if campo} | {_tarea(v) for v in _vencidas(p)}
    return ids - {""}


def mundos_de_tareas(ctx, ids: set[str]) -> dict[str, str]:
    """{id: mundo} de esas tareas, como las clasifica telar (`mundos.de_tarea`, con la configuración de `ctx`); las que no
    se encuentran o no se leen, fuera. Aquí, del índice (una sola lectura); de otra máquina (`[tipos.tarea] en`), de la
    lista entera de allá."""
    from telar import mundos
    from telar.servicios import ErrorDeServicio
    from telar.servicios import tipos

    if not ids or not mundos.declarados(ctx.config):
        return {}
    try:
        t = tipos._tipo(ctx, "tarea")
        if tipos._alla(ctx, t):
            return {x.id: x.mundo for x in tipos.lista(ctx, "tarea", todas=True).tareas if x.id in ids}
        return {o.id: mundos.de_tarea(ctx.config, o.area, o.proyecto)
                for o, _ in tipos.indice(ctx, "tarea").consultar(lambda o: getattr(o, "id", "") in ids)}
    except (ErrorDeServicio, OSError):
        return {}


def clasificar(pasada: dict, declarados: tuple[str, ...], de_tareas: dict[str, str]) -> dict:
    """La pasada con el mundo de cada cosa resuelto (una copia: la de disco no cambia). Una cosa con la dirección de una
    tarea que se clasifica (`de_tareas`, {id: mundo}) es de ese mundo; si no, del que dijo el agente si es uno de
    `declarados`; si no, "" (sin clasificar). Agrega `mundos_vencidas` ({dirección: mundo}, el de cada vencida sin
    propuesta, por su tarea), `mundos` (los de todas sus cosas, sin repetir, en el orden de `declarados` y "" al final;
    [""] si no trae ninguna: la pasada misma es sin clasificar) y `mundos_cambios` (los de lo que cambió: tareas y
    borradores; [] si no cambió nada)."""
    v = json.loads(json.dumps(pasada))
    vistos: set[str] = set()
    cambios: set[str] = set()
    for grupo, _, x, campo in _cosas(v):
        m = de_tareas.get(_tarea(x.get(campo)), "") if campo else ""
        if not m:
            dijo = x.get("mundo")
            m = dijo if isinstance(dijo, str) and dijo in declarados else ""
        x["mundo"] = m
        vistos.add(m)
        if grupo in CAMBIOS:
            cambios.add(m)
    vencidas = {d: de_tareas.get(_tarea(d), "") for d in _vencidas(v)}
    if vencidas:
        v["mundos_vencidas"] = vencidas
        vistos |= set(vencidas.values())
    orden = lambda c: [m for m in declarados if m in c] + ([""] if "" in c else [])  # noqa: E731
    v["mundos"] = orden(vistos) or [""]
    v["mundos_cambios"] = orden(cambios)
    return v


def hay_cambios(p: dict) -> bool:
    """Si la pasada (o lo que se ve de ella: `para_mundo`) cambió algo: una tarea nueva, avanzada o cerrada, o un borrador."""
    return any(True for grupo, _, _, _ in _cosas(p) if grupo in CAMBIOS)


def _ve(de: str, mundo: str) -> bool:
    """Si una cosa de ese mundo se ve con `mundo` puesto: lo suyo y lo sin clasificar; con ambos (""), todo."""
    return not mundo or not de or de == mundo


def para_mundo(pasada: dict, mundo: str) -> dict:
    """Lo que se ve de una pasada clasificada (`clasificar`) con `mundo` puesto ("" ambos): lo que cambió de ese mundo y sin
    clasificar que todavía no se ha visto (si trae `sin_ver_en`: lo de un mundo ya mirado con él, y lo sin clasificar ya
    visto con cualquiera, no vuelve), sus demás cosas de ese mundo y sin clasificar, y sus resúmenes. Con `resumenes`, los
    de los mundos que se ven, y `resumen` (neutro: cuenta la pasada entera) solo con ambos y si nada de ella se vio. Sin
    `resumenes` (las de antes), el resumen puede nombrar lo de cualquier mundo: con un mundo puesto queda solo si la pasada
    no trae nada de otro. Lo mismo que hace la página (componentes/pulso.ts, `paraMundo`)."""
    sin_ver = pasada.get("sin_ver_en") if isinstance(pasada.get("sin_ver_en"), list) else None
    if not mundo and sin_ver is None:
        return pasada

    def nuevo(m: str) -> bool:
        return _ve(m, mundo) and (sin_ver is None or m in sin_ver)

    def filtrar(lista, ve):
        return [x for x in lista if not isinstance(x, dict) or ve(str(x.get("mundo") or ""))] if isinstance(lista, list) else lista

    v = dict(pasada)
    for grupo, _ in CON_MUNDO:
        if not grupo.startswith("tareas.") and grupo in v:
            v[grupo] = filtrar(v[grupo], nuevo if grupo in CAMBIOS else (lambda m: _ve(m, mundo)))
    if isinstance(v.get("tareas"), dict):
        v["tareas"] = {k: filtrar(l, nuevo) for k, l in v["tareas"].items()}
    de = v.get("mundos_vencidas") if isinstance(v.get("mundos_vencidas"), dict) else {}
    if "vencidas_sin_propuesta" in v:
        v["vencidas_sin_propuesta"] = [d for d in _vencidas(v) if _ve(str(de.get(d) or ""), mundo)]
    if isinstance(v.get("resumenes"), dict):
        v["resumenes"] = {k: t for k, t in v["resumenes"].items() if nuevo(k)}
        entera = sin_ver is None or all(m in sin_ver for m in v.get("mundos_cambios") or ())
        if mundo or not entera:
            v["resumen"] = ""
    elif mundo and any(m and m != mundo for m in v.get("mundos") or ()):
        v["resumen"] = ""
    return v


# ── el día en disco ───────────────────────────────────────────────────────────

def _declarado(config, clave: str):
    """El resultado declarado con pasadas, o el error que lo dice."""
    from telar import resultados

    r = resultados.declarado(config, clave)
    if r is None:
        raise ErrorDePasada(f"no hay un resultado «{clave}» ([vistas.{clave}] con carpeta o en)")
    if not r.pasadas:
        raise ErrorDePasada(f"«{clave}» no lleva pasadas: falta pasadas = \"pulso\" (o \"libre\") en su [vistas.{clave}]")
    return r


def _carpeta(r) -> Path:
    if not r.carpeta:
        raise ErrorDePasada(f"«{r.clave}» no tiene carpeta en esta máquina (carpeta en su [vistas.{r.clave}])")
    return Path(r.carpeta).expanduser()


def _archivo(r, dia: str) -> Path:
    return _carpeta(r) / f"{r.prefijo}{dia}.json"


def _leer_dia(f: Path) -> list[dict]:
    """Las pasadas de un día; [] si todavía no hay. Un archivo que no es una lista de pasadas es un error: no se pisa."""
    if not f.is_file():
        return []
    try:
        datos = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ErrorDePasada(f"{f.name} no se pudo leer ({e}): no lo toco") from None
    lista = datos.get("pasadas") if isinstance(datos, dict) else None
    if not isinstance(lista, list) or not all(isinstance(p, dict) for p in lista):
        raise ErrorDePasada(f"{f.name} no es un día de pasadas ({{\"pasadas\": [...]}}): no lo toco")
    return lista


def _escribir(f: Path, datos: dict) -> None:
    """Entero o nada: a un temporal de la misma carpeta, a disco, y en su lugar de un golpe. Solo para la persona (0600):
    trae nombres, correos y lo que le espera."""
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f".{f.name}.{os.getpid()}.tmp")
    try:
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, f)
    finally:
        tmp.unlink(missing_ok=True)


def _candado(r):
    from telar.estado import _candado as candado

    return candado(_carpeta(r) / CANDADO)


def _dias(r) -> list[str]:
    """Los días que hay, del más nuevo al más viejo."""
    carpeta, pre = _carpeta(r), r.prefijo
    if not carpeta.is_dir():
        return []
    return sorted({f.stem[len(pre):] for f in carpeta.glob(f"{pre}*.json")
                   if f.stem.startswith(pre) and DIA.fullmatch(f.stem[len(pre):])}, reverse=True)


# ── aquí, en la máquina donde vive ───────────────────────────────────────────

def agregar_local(config, clave: str, pasadas: list, *, saltar_repetidas: bool = False, nombres: list | None = None) -> dict:
    """Agregar pasadas a sus días, aquí. Todas se validan antes de escribir nada; una mala, y no entra ninguna. Un
    id que ya está es un error (y no se escribe nada), salvo con `saltar_repetidas` (importar), que la salta. Siempre
    `{"ok": …}`: con `agregadas`, `ya_estaban` (las que se saltaron; `distintas`, las que ya estaban con otro
    contenido), `en_el_dia` (cuántas tiene cada día tocado después de agregar) y `avisos` (lo que no la rechaza pero se
    dice: un mundo que no está declarado aquí). `nombres`: cómo nombrar cada pasada en un error («línea 3», si vienen de
    un archivo); sin ellos, «pasada 3»."""
    try:
        r = _declarado(config, clave)
        _carpeta(r)
    except ErrorDePasada as e:
        return {"ok": False, "error": str(e)}
    if not isinstance(pasadas, list) or not pasadas:
        return {"ok": False, "error": "no llegó ninguna pasada"}
    if not (isinstance(nombres, list) and len(nombres) == len(pasadas) and all(isinstance(n, str) for n in nombres)):
        nombres = [f"pasada {i + 1}" for i in range(len(pasadas))]
    from telar import mundos

    errores, vistos, dichos = [], {}, []
    declarados = mundos.declarados(config)
    for i, p in enumerate(pasadas):
        quien = nombres[i] + (f" ({p['id']})" if isinstance(p, dict) and isinstance(p.get("id"), str) else "")
        errores += [f"{quien}: {e}" if len(pasadas) > 1 else e for e in validar(r.pasadas, p)]
        dichos += [f"{quien}: {a}" if len(pasadas) > 1 else a for a in avisos(r.pasadas, p, declarados)]
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            if p["id"] in vistos:
                errores.append(f"{quien}: el id {p['id']} se repite (también en la {nombres[vistos[p['id']]]})")
            vistos.setdefault(p["id"], i)
    if errores:
        return {"ok": False, "error": errores[0] if len(errores) == 1 else f"{len(errores)} problemas; el primero: {errores[0]}",
                "errores": errores}
    agregadas, ya, distintas, en_el_dia = [], [], [], {}
    try:
        with _candado(r):
            # primero se lee todo lo que se va a tocar: si algo no se puede, no se escribe nada
            dias: dict[str, list[dict]] = {}
            for p in pasadas:
                dia = dia_de(p["id"])
                if dia not in dias:
                    dias[dia] = _leer_dia(_archivo(r, dia))
            nuevas: dict[str, list[dict]] = {}
            for p in pasadas:
                dia = dia_de(p["id"])
                antes = next((x for x in dias[dia] if x.get("id") == p["id"]), None)
                if antes is not None:
                    if not saltar_repetidas:
                        igual = " (igual a esta: ya había llegado)" if antes == p else ""
                        return {"ok": False, "error": f"la pasada {p['id']} ya está en el {dia}{igual}; no se reescribe",
                                "repetida": p["id"]}
                    ya.append(p["id"])
                    if antes != p:
                        distintas.append(p["id"])
                    continue
                nuevas.setdefault(dia, []).append(p)
            for dia, lote in nuevas.items():
                todas = dias[dia] + lote
                _escribir(_archivo(r, dia), {"pasadas": todas})
                agregadas += [p["id"] for p in lote]
                en_el_dia[dia] = len(todas)
    except (ErrorDePasada, OSError) as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "clave": clave, "agregadas": agregadas, "ya_estaban": ya, "distintas": distintas, "en_el_dia": en_el_dia,
            **({"avisos": dichos} if dichos else {})}


def _leer_visto(r) -> dict:
    """`visto.json` como está: `id`, `dia` y `cuando` (lo visto con ambos: vale para todos los mundos) y `mundos` (lo
    visto con un mundo puesto, por mundo; "" es lo sin clasificar). {} si no hay o no se lee."""
    f = _carpeta(r) / VISTO
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _marca(d: object) -> dict:
    """Una marca de lo visto (`{"id", "dia", "cuando"}`), o {} si no es una."""
    if not isinstance(d, dict) or not dia_de(str(d.get("id", ""))):
        return {}
    return {k: str(d.get(k, "")) for k in ("id", "dia", "cuando")}


def _marcas(d: dict) -> dict[str, dict]:
    m = d.get("mundos")
    return {str(k): _marca(v) for k, v in m.items() if _marca(v)} if isinstance(m, dict) else {}


def visto_local(config, clave: str) -> dict:
    """Hasta qué pasada vio la persona con ambos (vale para todos los mundos): `{"id", "dia", "cuando"}`, o `{}`."""
    return _marca(_leer_visto(_declarado(config, clave)))


def vistos_local(config, clave: str) -> dict[str, dict]:
    """Hasta cuál vio con cada mundo puesto: {mundo: {"id", "dia", "cuando"}} ("" es lo sin clasificar)."""
    return _marcas(_leer_visto(_declarado(config, clave)))


def marcar_visto_local(config, clave: str, id_: str = "", mundo: str = "") -> dict:
    """Marcar vistas las pasadas hasta `id_` (vacío, o «ultimo»: hasta la más nueva que hay). Tiene que existir. Con
    `mundo` (uno declarado aquí), lo de ese mundo y lo sin clasificar; sin él (ambos), todo. Solo avanza: si ya se había
    visto una más nueva, queda esa (`movio` en false). Siempre `{"ok": …}`, con `visto` (lo de ambos) y `vistos` (por
    mundo)."""
    from telar import mundos

    mundo = (mundo or "").strip()
    try:
        r = _declarado(config, clave)
        if mundo:
            hay = mundos.declarados(config)
            if mundo not in hay:
                return {"ok": False, "error": f"no hay un mundo «{mundo}» ({', '.join(hay)})" if hay
                        else f"esta máquina no declara mundos ([mundos]): «{mundo}» no se marca aparte"}
        with _candado(r):
            crudo = _leer_visto(r)
            antes, marcas = _marca(crudo), _marcas(crudo)
            if id_ in ("", "ultimo"):
                ultima = next((max((p.get("id", "") for p in _leer_dia(_archivo(r, d))), default="") for d in _dias(r)), "")
                if not ultima:
                    return {"ok": True, "clave": clave, "visto": antes, "vistos": marcas, "movio": False, "dice": "no hay pasadas"}
                id_ = ultima
            dia = dia_de(id_)
            if not dia:
                return {"ok": False, "error": f"«{id_[:40]}» no es el id de una pasada (AAAA-MM-DDTHH:MM)"}
            if not any(p.get("id") == id_ for p in _leer_dia(_archivo(r, dia))):
                return {"ok": False, "error": f"no hay una pasada {id_} en el {dia}"}
            ahora = {"id": id_, "dia": dia, "cuando": datetime.now().astimezone().isoformat(timespec="seconds")}
            if mundo:
                # lo de ese mundo y lo sin clasificar, que se ve con cualquiera
                movidos = [k for k in (mundo, "") if max(antes.get("id", ""), marcas.get(k, {}).get("id", "")) < id_]
                for k in movidos:
                    marcas[k] = ahora
                visto = antes
            else:
                movidos = [""] if antes.get("id", "") < id_ else []
                visto = ahora if movidos else antes
                # lo marcado por mundo que ya quedó atrás no dice nada
                marcas = {k: v for k, v in marcas.items() if v["id"] > visto.get("id", "")}
            if not movidos:
                return {"ok": True, "clave": clave, "visto": antes, "vistos": marcas, "movio": False, "mundo": mundo}
            _escribir(_carpeta(r) / VISTO, {**visto, **({"mundos": marcas} if marcas else {})})
    except (ErrorDePasada, OSError) as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "clave": clave, "visto": visto, "vistos": marcas, "movio": True, "mundo": mundo}


def sin_ver_local(config, clave: str, tope: int = TOPE_SIN_VER, *, ctx=None) -> dict:
    """Las pasadas que tienen algo que la persona no ha visto en algún mundo, de la más nueva a la más vieja (hasta `tope`
    enteras; `total`, cuántas son). Lo que se ve son sus cambios (tareas y borradores); una que no cambió nada es sin
    clasificar. `con_cambios`, cuántas cambiaron algo sin ver; `por_mundo`, cuántas con cambios sin ver se ven con cada
    mundo puesto. Cada una clasificada (`clasificar`, las tareas con la configuración de `ctx`), con `sin_ver_en`: los
    mundos en que tiene algo sin ver ("" lo sin clasificar). Lo de un mundo está visto hasta lo marcado con ambos o con
    ese mundo; sin nada marcado, lo que no es del último día que hay. Siempre `{"ok": …}`, con `visto`, `vistos` y
    `esquema`."""
    from telar import mundos

    declarados = mundos.declarados(config)
    try:
        r = _declarado(config, clave)
        crudo = _leer_visto(r)
        visto, marcas = _marca(crudo), _marcas(crudo)
        dias = _dias(r)[:DIAS_SIN_VER]
        ultimo = dias[0] if dias else ""

        def piso(k: str) -> str:
            # el día solo («2026-11-18») va antes de todos los ids de ese día y después de los del anterior
            return max(visto.get("id", ""), marcas.get(k, {}).get("id", "")) or ultimo

        desde = min(piso(k) for k in ("", *declarados))
        crudas = [p for d in dias if d >= desde[:10] for p in _leer_dia(_archivo(r, d)) if str(p.get("id", "")) > desde]
    except (ErrorDePasada, OSError) as e:
        return {"ok": False, "error": str(e)}
    de_tareas = {}
    if r.pasadas == "pulso" and declarados:
        de_tareas = mundos_de_tareas(ctx or SimpleNamespace(config=config), set().union(*(tareas_de(p) for p in crudas)))
    lista = []
    for p in crudas:
        v = clasificar(p, declarados, de_tareas) if r.pasadas == "pulso" else {**p, "mundos": [""], "mundos_cambios": [""]}
        # lo que no se ha visto es lo que cambió; la que no cambió nada es sin clasificar: se ve («sin cambios») con
        # cualquier mundo y no cuenta
        v["sin_ver_en"] = [k for k in v["mundos_cambios"] or [""] if str(p.get("id", "")) > piso(k)]
        if v["sin_ver_en"]:
            lista.append(v)
    lista.sort(key=lambda p: str(p.get("id", "")), reverse=True)
    con = [p for p in lista if p["mundos_cambios"]]
    por_mundo = {m: sum(1 for p in con if m in p["sin_ver_en"] or "" in p["sin_ver_en"]) for m in declarados}
    return {"ok": True, "clave": clave, "nombre": r.nombre or clave, "esquema": r.pasadas, "visto": visto, "vistos": marcas,
            "total": len(lista), "con_cambios": len(con), "por_mundo": por_mundo, "pasadas": lista[:tope]}


# ── desde cualquier máquina: allá si vive en otra ────────────────────────────

def _alla(config, clave: str):
    """La máquina del bus donde vive el resultado, si es otra; "" si es esta (o no hay bus)."""
    from telar import bus as mod_bus
    from telar import resultados

    r = resultados.declarado(config, clave)
    if r is not None and r.en and mod_bus.hay_bus(config) and r.en != mod_bus.maquina(config):
        return r.en
    return ""


def _pedir(config, maquina: str, verbo: str, datos: dict, espera: float) -> dict:
    """A la máquina donde vive. Si no responde, se dice (el error de `bus.pedir` la nombra) y aquí no se hace nada."""
    from telar import bus as mod_bus

    return {**mod_bus.pedir(config, maquina, verbo, datos, espera=espera), "desde": maquina}


def agregar(config, clave: str, pasadas: list, *, saltar_repetidas: bool = False, nombres: list | None = None) -> dict:
    maquina = _alla(config, clave)
    if maquina:
        return _pedir(config, maquina, "resultado-agregar", {"clave": clave, "pasadas": pasadas,
                                                              "saltar_repetidas": saltar_repetidas, "nombres": nombres}, 30)
    return {**agregar_local(config, clave, pasadas, saltar_repetidas=saltar_repetidas, nombres=nombres), "desde": "aquí"}


def marcar_visto(config, clave: str, id_: str = "", mundo: str = "") -> dict:
    maquina = _alla(config, clave)
    if maquina:
        return _pedir(config, maquina, "resultado-visto", {"clave": clave, "id": id_, **({"mundo": mundo} if mundo else {})}, 15)
    return {**marcar_visto_local(config, clave, id_, mundo), "desde": "aquí"}


def sin_ver(config, clave: str, *, ctx=None) -> dict:
    """Lo sin ver, de la máquina donde vive: allá se clasifica, con su configuración y sus tareas."""
    maquina = _alla(config, clave)
    if maquina:
        return _pedir(config, maquina, "resultado-sin-ver", {"clave": clave}, 15)
    return {**sin_ver_local(config, clave, ctx=ctx), "desde": "aquí"}


def leer_jsonl(texto: str) -> tuple[list, list[str], list[str]]:
    """Las pasadas de un archivo con una por línea (las líneas vacías no cuentan): (las pasadas, el nombre de cada una
    para un error, «línea 3», y lo que no se pudo leer, con su línea)."""
    pasadas, nombres, errores = [], [], []
    for n, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip():
            continue
        try:
            pasadas.append(json.loads(linea))
            nombres.append(f"línea {n}")
        except ValueError as e:
            errores.append(f"línea {n}: no es JSON ({e})")
    return pasadas, nombres, errores
