"""Los objetos de un tipo (telar.tipos): leerlos, aplicarles una acción, crearlos y borrarlos.

    [tipos.tarea]
    carpeta = "~/notas/tareas"     # donde viven: esta máquina es la que las escribe
    en = "servidor"                # o: viven en otra máquina del bus, y se le pide a ella

Una sola máquina escribe los archivos de un tipo; las demás le piden por el bus (`tipo`), y una acción
nunca se corre sobre la copia de aquí: cambiaría la copia, no los objetos. Quien escribe commitea y sube
el archivo que cambió (`telar commit`), en un proceso aparte.

Lo usan la CLI (`telar tipo tarea …`) y la API (`/tipos/tarea`); el panel, por la API.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, computed_field

from telar import objetos
from telar.servicios import ErrorDeServicio
from telar.tipos import ErrorDeFormato
from telar.tipos import tarea as tipo_tarea
from telar.tipos.carpeta import ErrorDeVersion, NoExiste

#: los tipos que telar conoce, con su formato y su modelo
CONOCIDOS = {"tarea": tipo_tarea}


class TareaConVersion(tipo_tarea.Tarea):
    """Una tarea y la versión de su archivo: la que se devuelve con una acción para no pisar a otro."""

    version: str

    @computed_field
    @property
    def direccion(self) -> str:
        """Su dirección de objeto, `tarea:<id>` (telar.objetos): sale en el JSON, no se guarda en el archivo."""
        return objetos.direccion_de("tarea", self.id)


class Tareas(BaseModel):
    tareas: list[TareaConVersion]
    fallas: dict[str, str] = {}


class Borrada(BaseModel):
    id: str
    #: la dirección que tenía (`tarea:<id>`)
    direccion: str = ""
    borrada: bool = True


def _tipo(ctx, clave: str):
    if clave not in CONOCIDOS:
        raise ErrorDeServicio(f"telar no conoce el tipo «{clave}»: {', '.join(CONOCIDOS)}", 404)
    t = next((x for x in getattr(ctx.config, "tipos", ()) if x.clave == clave), None)
    if t is None:
        raise ErrorDeServicio(f"esta máquina no declara dónde viven los objetos «{clave}» ([tipos.{clave}])", 404)
    return t


def _alla(ctx, t) -> str:
    """La máquina donde viven, si es otra y hay bus; "" si es aquí."""
    from telar import bus as mod_bus

    if not t.en or not mod_bus.hay_bus(ctx.config) or t.en == mod_bus.maquina(ctx.config):
        return ""
    return t.en


def indice(ctx, clave: str = "tarea"):
    """El índice del tipo en esta máquina (uno por proceso: telar.tipos.indice.compartido)."""
    from telar.tipos.indice import compartido

    t = _tipo(ctx, clave)
    if not t.carpeta:
        raise ErrorDeServicio(f"los objetos «{clave}» viven en {t.en}, y {t.en} no está en el bus", 502)
    return compartido(t.carpeta, CONOCIDOS[clave].ARCHIVO)


def _pedir_alla(ctx, en: str, argv: list[str]) -> dict:
    """Corre `telar tipo …` en la máquina donde viven y devuelve su JSON, o su error con su código."""
    from telar import alla
    from telar import bus as mod_bus

    r = mod_bus.pedir(ctx.config, en, "tipo", {"argv": [*argv, "--json"]}, espera=alla.ESPERA * 2 + 10)
    if not r.get("ok"):
        raise ErrorDeServicio(f"viven en {en} y no respondió: {r.get('error', '')}", 502)
    try:
        datos = json.loads(r.get("salida", "") or "null")
    except ValueError:
        datos = None
    if int(r.get("codigo", 1)) != 0:
        linea = (r.get("error_salida", "").strip().splitlines() or [f"{en} no pudo"])[-1]
        extra = datos if isinstance(datos, dict) else {}
        raise ErrorDeServicio(extra.get("error") or linea.removeprefix("telar: "), int(extra.get("codigo", 400)),
                              {k: v for k, v in extra.items() if k not in ("error", "codigo")})
    if datos is None:
        raise ErrorDeServicio(f"{en} no devolvió JSON", 502)
    return datos


def _con_version(par) -> TareaConVersion:
    t, v = par
    return TareaConVersion(**t.model_dump(), version=v)


def subir(archivo, mensaje: str) -> None:
    """Commitea ese archivo y lo sube (`telar commit`), en un proceso aparte que sobrevive a quien llamó:
    quien pidió el cambio no espera el push, y una orden suelta que termina no se lo lleva."""
    try:
        subprocess.Popen([sys.executable, "-m", "telar", "commit", "-m", mensaje, "--", str(archivo)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass  # sin commit, queda en el árbol: /sincronizar lo junta


def _errores(fn, accion: str = ""):
    """Corre `fn` y traduce lo que el tipo dice que no se pudo a un error del servicio, con su código."""
    try:
        return fn()
    except NoExiste as e:
        raise ErrorDeServicio(str(e), 404) from e
    except ErrorDeVersion as e:
        raise ErrorDeServicio(str(e), 409, {"version": e.actual}) from e
    except tipo_tarea.ErrorDeAccion as e:
        raise ErrorDeServicio(str(e), 409) from e
    except TypeError as e:
        raise ErrorDeServicio(f"«{accion}» no lleva esos parámetros: {e}", 422) from e
    except ErrorDeFormato as e:
        raise ErrorDeServicio(str(e), 422) from e


# ── leer ──

def lista(ctx, clave: str = "tarea", *, todas: bool = False, area: str = "", proyecto: str = "",
          dueno: str | None = None, vence_hasta: str = "") -> Tareas:
    """Los objetos, desde el índice. Por defecto las abiertas; `todas`, también las cerradas."""
    t = _tipo(ctx, clave)
    if (en := _alla(ctx, t)):
        argv = [clave, "lista", *(["--todas"] if todas else [])]
        r = Tareas(**_pedir_alla(ctx, en, argv))
        return r.model_copy(update={"tareas": [x for x in r.tareas if _pasa(x, area, proyecto, dueno, vence_hasta)]})
    ind = indice(ctx, clave)
    return Tareas(tareas=[_con_version(x) for x in ind.consultar(
        lambda x: (todas or not x.cerrada_ya) and _pasa(x, area, proyecto, dueno, vence_hasta))],
        fallas=dict(ind.fallas))


def _pasa(t, area, proyecto, dueno, vence_hasta) -> bool:
    return ((not area or t.area == area) and (not proyecto or t.proyecto == proyecto)
            and (dueno is None or t.dueno == dueno) and (not vence_hasta or bool(t.vence and t.vence <= vence_hasta)))


def obtener(ctx, id: str, clave: str = "tarea") -> TareaConVersion:
    t = _tipo(ctx, clave)
    if (en := _alla(ctx, t)):
        return TareaConVersion(**_pedir_alla(ctx, en, [clave, "ver", id]))
    return _errores(lambda: _con_version(indice(ctx, clave).obtener(id)))


# ── escribir ──

def aplicar(ctx, id: str, accion: str, params: dict | None = None, *, version: str | None = None,
            clave: str = "tarea") -> TareaConVersion:
    """Una acción del tipo sobre el objeto (`completar`, `reagendar`, `esperar`…), con la versión que se
    leyó: si el archivo cambió desde entonces, 409 y la versión de ahora."""
    t = _tipo(ctx, clave)
    params = dict(params or {})
    if accion == "unir" and clave == "tarea":
        # dos tareas: se arma con las acciones de cada una, aquí o en la máquina que las escribe
        return unir(ctx, str(params.get("con") or ""), id, version=version)
    if (en := _alla(ctx, t)):
        return TareaConVersion(**_pedir_alla(ctx, en, [clave, accion, id, "--params", json.dumps(params, ensure_ascii=False),
                                                       *(["--version", version] if version else [])]))
    fn = CONOCIDOS[clave].ACCIONES.get(accion)
    if fn is None:
        raise ErrorDeServicio(f"no hay una acción «{accion}»: {', '.join(CONOCIDOS[clave].ACCIONES)}", 422)
    ind = indice(ctx, clave)
    antes = _errores(lambda: ind.obtener(id), accion)[1]
    hecho = _errores(lambda: _con_version(ind.aplicar(id, fn, version=version, **params)), accion)
    if hecho.version != antes:
        subir(ind.carpeta.ruta / f"{id}.md", f"tareas: {id} {accion}")
    return hecho


def unir(ctx, queda: str, se_va: str, *, version: str | None = None) -> TareaConVersion:
    """Dos tareas que son la misma: `se_va` se une a `queda`. La que queda suma su texto (bajo «De T461»), lo que no
    decía (proyecto, tamaño) y una línea en su historia, y la conecta en el grafo (`absorbe`); la otra se descarta
    diciendo adónde fue. `version` es la de `se_va`, la que se estaba mirando."""
    queda, se_va = queda.strip().removeprefix("tarea:"), se_va.strip().removeprefix("tarea:")
    if not queda:
        raise ErrorDeServicio("unir: ¿con cuál? params {\"con\": \"T84\"}", 422)
    if queda == se_va:
        raise ErrorDeServicio("una tarea no se une consigo misma", 422)
    a, b = obtener(ctx, queda), obtener(ctx, se_va)
    for x in (a, b):
        if x.estado in tipo_tarea.TERMINALES:
            raise ErrorDeServicio(f"{x.id} ya está cerrada ({x.estado}): no se une", 409)
    if version and version != b.version:
        raise ErrorDeServicio(f"{b.id} cambió desde que se leyó: reléela y decide", 409, {"version": b.version})
    hoy = f"{_dt.date.today():%Y-%m-%d}"
    texto = "\n\n".join(x for x in [a.contexto.strip(), f"De {b.id} (unida el {hoy}): {b.titulo}"
                                     + (f"\n\n{b.contexto.strip()}" if b.contexto.strip() else "")] if x)
    cambios = {"contexto": texto, **({"proyecto": b.proyecto} if b.proyecto and not a.proyecto else {}),
               **({"tamano": b.tamano} if b.tamano and not a.tamano else {})}
    aplicar(ctx, a.id, "editar", cambios)
    aplicar(ctx, a.id, "anotar", {"texto": f"se le unió {b.id}: {b.titulo}"})
    hecho = aplicar(ctx, a.id, "conectar", {"tipo": "absorbe", "destino": f"[{b.id}]({b.id}.md)", "porque": "era la misma tarea"})
    aplicar(ctx, b.id, "cerrar", {"como": "descartada", "nota": f"unida a {a.id}: sigue allá"}, version=b.version)
    return hecho


def crear(ctx, params: dict, *, clave: str = "tarea") -> TareaConVersion:
    """Un objeto nuevo (`titulo`, y lo que `telar.tipos.tarea.nueva` acepta). El identificador lo elige
    la máquina que escribe: el que sigue al mayor."""
    t = _tipo(ctx, clave)
    if (en := _alla(ctx, t)):
        return TareaConVersion(**_pedir_alla(ctx, en, [clave, "crear", "--params", json.dumps(params, ensure_ascii=False)]))
    mod = CONOCIDOS[clave]
    ind = indice(ctx, clave)
    objeto = _errores(lambda: mod.nueva(**params), "crear")
    hecho = _errores(lambda: _con_version(ind.crear(objeto, prefijo=mod.PREFIJO)), "crear")
    subir(ind.carpeta.ruta / f"{hecho.id}.md", f"tareas: {hecho.id} add · {hecho.titulo[:60]}")
    return hecho


def borrar(ctx, id: str, *, version: str | None = None, clave: str = "tarea") -> Borrada:
    t = _tipo(ctx, clave)
    if (en := _alla(ctx, t)):
        hecho = Borrada(**_pedir_alla(ctx, en, [clave, "borrar", id, *(["--version", version] if version else [])]))
        # la máquina donde viven puede ser de antes de las direcciones
        return hecho.model_copy(update={"direccion": hecho.direccion or objetos.direccion_de(clave, hecho.id)})
    ind = indice(ctx, clave)
    _errores(lambda: ind.borrar(id, version=version), "borrar")
    subir(Path(ind.carpeta.ruta) / f"{id}.md", f"tareas: {id} rm")
    return Borrada(id=id, direccion=objetos.direccion_de(clave, id))
