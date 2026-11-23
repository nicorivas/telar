"""Lo que espera una decisión de la persona, junto: la bandeja (docs/propuestas/lo-que-espera-a-la-persona.md).

    from telar.servicios import esperas
    r = esperas.esperas(ctx)          # Esperas(esperas=[Espera…], fallas={tipo: por qué})

Cada tipo de objeto dice cuáles de los suyos esperan a la persona (`Tipo.esperando`, telar.objetos): el permiso o
la pregunta en vivo de un hilo (`permiso:`), el `avance` de una tarea (`tarea:`), un mensaje retenido (`mensaje:`)
y lo que declare un módulo. Aquí se juntan, de la más vieja a la más nueva. Es de solo lectura: nada de aquí
contesta, suelta ni toca el `avance` de una tarea. Cada fuente sigue viviendo donde vive.

Las fuentes se leen a la vez (dos de ellas esperan al bus), y una que falla no tira las demás: va en `fallas`, con
su tipo. Lo usan `telar esperas` y `GET /esperas`; la forma está en docs/contratos.md, «telar esperas --json».

Con `[mundos]` en la configuración, cada espera dice a qué parte de la vida pertenece (`mundo`, telar.mundos): la
tarea lo sabe por su área; las demás, por su enlace principal (el hilo que espera, el hilo al que iba un mensaje, el
proyecto de lo que traiga un módulo), y para eso se leen los hilos una vez, a la par con las fuentes.

Del otro lado viene aparte, en `contestadas`: lo que la persona contestó en una tarea y por lo que el agente todavía no
pasa (`Tarea.contestadas`, telar.objetos), de la misma lectura de las tareas. No espera a la persona, así que no es una
espera ni se cuenta con ellas; Táctica lo muestra con la próxima pasada del agente.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from pydantic import BaseModel, Field

from telar.objetos import Contestada, Espera
from telar.servicios import ErrorDeServicio

__all__ = ["Contestada", "Espera", "Esperas", "esperas"]


class Esperas(BaseModel):
    #: de la que espera hace más tiempo a la más nueva; las que no dicen desde cuándo, al final
    esperas: list[Espera] = Field(default_factory=list)
    #: las fuentes que no se pudieron leer (o no enteras): tipo → por qué
    fallas: dict[str, str] = Field(default_factory=dict)
    #: los mundos que declara la configuración, en su orden (el de las tandas); vacío si no declara ninguno, y
    #: entonces ninguna espera dice `mundo`
    mundos: list[str] = Field(default_factory=list)
    #: las tareas que la persona contestó y que esperan al agente, de la contestada hace más tiempo a la más nueva (solo
    #: si se leyeron las tareas: sin `tipos`, o con `tarea` entre ellos). No esperan a la persona: no son esperas
    contestadas: list[Contestada] = Field(default_factory=list)


def _orden(e: Espera) -> tuple:
    try:
        cuando = datetime.fromisoformat(e.desde) if e.desde else None
    except ValueError:
        cuando = None
    return (cuando is None, cuando or datetime.max, e.direccion)


def esperas(ctx, *, tipos: tuple[str, ...] = (), mundos: tuple[str, ...] = ()) -> Esperas:
    """Lo que espera a la persona, de todos los tipos (o solo de `tipos`) y de todos los mundos (o solo de `mundos`:
    sus nombres, o `sin-clasificar`)."""
    from telar import mundos as mod_mundos
    from telar import objetos

    todos = objetos.tipos(ctx)
    if tipos:
        raros = [t for t in tipos if t not in todos]
        if raros:
            raise ErrorDeServicio(f"no hay un tipo «{raros[0]}»: {', '.join(sorted(todos))}", 404)
    filtro = mod_mundos.pedidos(ctx.config, mundos)
    declarados = mod_mundos.declarados(ctx.config)
    # solo los que saben esperar algo: los demás darían [] igual, sin hilo que esperar
    fuentes = {n: t for n, t in todos.items() if (not tipos or n in tipos) and _sabe_esperar(t)}
    salida, fallas = [], {}
    #: las fuentes que no se leyeron nada (las de a medias, sí: lo que se leyó vale)
    rotas: set[str] = set()
    clasificador = mod_mundos.Clasificador(ctx) if declarados else None
    if fuentes:
        with ThreadPoolExecutor(max_workers=len(fuentes) + 1, thread_name_prefix="esperas") as hilos:
            futuros = {n: hilos.submit(t.esperando, ctx) for n, t in fuentes.items()}
            # los hilos, para el mundo de lo que nombra uno: a la par con las fuentes, no después
            if clasificador is not None and set(fuentes) - {"tarea"}:
                hilos.submit(clasificador.preparar)
        for n, f in futuros.items():
            try:
                salida.extend(f.result())
            except objetos.Incompletas as e:
                salida.extend(e.esperas)
                fallas[n] = str(e)
            except ErrorDeServicio as e:
                fallas[n] = str(e)
                rotas.add(n)
            except Exception as e:  # noqa: BLE001 - una fuente rota no tumba la bandeja: se dice cuál y por qué
                fallas[n] = f"{type(e).__name__}: {e}"
                rotas.add(n)
    if clasificador is not None:
        for e in salida:
            if not e.mundo:
                e.mundo = clasificador.de_espera(e)
            elif e.mundo not in declarados:
                e.mundo = ""  # lo que diga una fuente que no es de esta configuración no es un mundo de aquí
            # de qué agente es: lo de uno de otro mundo no se nombra fuera de él, ni en el modo todo de la página
            e.agente = e.agente or clasificador.agente_de_espera(e)
    else:
        for e in salida:
            e.mundo = ""
    salida = [e for e in salida if mod_mundos.calza(e.mundo, filtro)]
    contestadas = _contestadas(ctx, fuentes, rotas, fallas)
    for c in contestadas:
        if c.mundo not in declarados:
            c.mundo = ""  # sin [mundos], o uno que no es de aquí: sin clasificar, como las esperas
    contestadas = [c for c in contestadas if mod_mundos.calza(c.mundo, filtro)]
    return Esperas(esperas=sorted(salida, key=_orden), fallas=fallas, mundos=list(declarados), contestadas=contestadas)


def _contestadas(ctx, fuentes: dict, rotas: set[str], fallas: dict) -> list[Contestada]:
    """Las tareas contestadas que esperan al agente, si se leyeron las tareas: después de sus esperas, así que de otra
    máquina salen de lo que se acaba de traer. Si las tareas no se pudieron leer, ya está en `fallas`; si esto falla
    solo, se dice ahí mismo, como una fuente más."""
    t = fuentes.get("tarea")
    if t is None or "tarea" in rotas or not hasattr(t, "contestadas"):
        return []
    try:
        return t.contestadas(ctx)
    except Exception as e:  # noqa: BLE001 - como una fuente rota: se dice y la bandeja sale igual
        fallas["contestadas"] = str(e) if isinstance(e, ErrorDeServicio) else f"{type(e).__name__}: {e}"
        return []


def _sabe_esperar(t) -> bool:
    from telar import objetos

    if isinstance(t, objetos.DeModulo):
        return bool(t._esperando)
    return type(t).esperando is not objetos.Tipo.esperando
