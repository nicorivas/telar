"""La conversación de un hilo: el único lector de sus mensajes, y su entrega por páginas a la web.

`telar agente conversacion` ya sabe leer la conversación entera; una conversación larga pesa
decenas de MB y 400 mensajes, y un teléfono no necesita todo. Aquí se sirve por trozos:

    los últimos N            (al abrir)
    los N anteriores a K     (`antes`: «cargar anteriores»)
    los que llegaron desde K (`despues`: seguir la conversación en vivo)

Los mensajes están numerados por su posición y una conversación solo crece, así que un índice
sigue siendo válido mientras el archivo no se reescriba. Se guarda lo leído mientras el archivo no
cambie (fecha y tamaño); si cambia, se relee entero: 0,2 s para 16 MB.

Solo se leen conversaciones **de un hilo que telar conoce**: quien llama dice el hilo, y de ahí sale
la lista de conversaciones permitidas. Un id suelto no abre ningún archivo.

Este módulo es el **único** que lee los mensajes de una conversación: la web (`pagina`), `telar hilo leer`
y el verbo `leer` de la puerta (`telar.historia`, que arma los turnos) pasan por `mensajes_del_hilo`, así que
comparten la regla de cuál conversación es la del hilo (la primera de las suyas que tenga archivo), la
validación de ids y el caché. Lo que cambia entre ellos es solo cuánto entregan: la web, todo por páginas y
hasta 20 000 caracteres por mensaje; la puerta, los últimos turnos con topes más chicos, porque viaja por ssh.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

#: cuánto de un mensaje viaja; más que eso se recorta y se dice
MAX_TEXTO = 20000
#: el tamaño de una página y lo máximo que se entrega de una vez
POR_PAGINA = 60
MAXIMO = 500

ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_cache: dict[str, tuple[int, int, list[dict]]] = {}
_candado = threading.Lock()


class ErrorDeConversacion(LookupError):
    """La conversación pedida no existe, no es de ese hilo o no está en disco."""


def _agente(config):
    from telar.agente import ErrorDeAgente
    from telar.ordenes.agente import _construir

    try:
        return _construir(config.agente.nombre, config)
    except ErrorDeAgente as e:
        raise ErrorDeConversacion(str(e)) from e


def leer(config, sid: str) -> tuple[list[dict], int]:
    """Los mensajes de esa conversación y la fecha de su archivo (ns). Levanta `ErrorDeConversacion`."""
    if not ID.match(sid or ""):
        raise ErrorDeConversacion("ese no es un id de conversación")
    agente = _agente(config)
    archivo: Path | None = agente.archivo_de(sid)
    if archivo is None:
        raise ErrorDeConversacion("esa conversación no está en disco en esta máquina")
    try:
        st = archivo.stat()
    except OSError as e:
        raise ErrorDeConversacion(f"no se pudo leer: {e}") from e
    clave = str(archivo)
    with _candado:
        previo = _cache.get(clave)
        if previo and previo[0] == st.st_mtime_ns and previo[1] == st.st_size:
            return previo[2], st.st_mtime_ns
    mensajes = agente.mensajes(sid)
    if mensajes is None:
        raise ErrorDeConversacion("no se pudo leer esa conversación")
    with _candado:
        _cache[clave] = (st.st_mtime_ns, st.st_size, mensajes)
        if len(_cache) > 8:  # unas pocas abiertas a la vez; las viejas se olvidan
            _cache.pop(next(iter(_cache)))
    return mensajes, st.st_mtime_ns


def mensajes_del_hilo(config, sesiones: list[str], sesion: str = "") -> tuple[str, list[dict], int]:
    """La conversación de un hilo: `(id, mensajes, fecha del archivo)`.

    Con `sesion`, esa (tiene que ser del hilo). Sin ella, la primera de las `sesiones` del hilo que tenga
    archivo en esta máquina: las anteriores pueden haber vivido en otra. Levanta `ErrorDeConversacion`."""
    if not sesiones:
        raise ErrorDeConversacion("este hilo no tiene conversaciones anotadas")
    if sesion:
        if sesion not in sesiones:
            raise ErrorDeConversacion("esa conversación no es de este hilo")
        mensajes, mtime = leer(config, sesion)
        return sesion, mensajes, mtime
    ultimo: ErrorDeConversacion | None = None
    for sid in sesiones:
        try:
            mensajes, mtime = leer(config, sid)
        except ErrorDeConversacion as e:
            ultimo = e
            continue
        return sid, mensajes, mtime
    raise ultimo or ErrorDeConversacion("este hilo no tiene conversaciones en esta máquina")


def aplanar(historia: dict) -> list[dict]:
    """Lo que devuelve el verbo `leer` de la puerta (`telar.historia.leer`) como lista de mensajes, la misma
    forma de la web. Si no había conversación sino el panel, un solo mensaje «panel» con su texto."""
    if historia.get("fuente") == "panel":
        return [{"quien": "panel", "hora": "", "texto": str(historia.get("texto", ""))}]
    return [m for turno in historia.get("turnos", []) for m in turno if isinstance(m, dict)]


def _recortado(m: dict) -> dict:
    texto = m.get("texto", "")
    if len(texto) <= MAX_TEXTO:
        return {"quien": m.get("quien", ""), "hora": m.get("hora", ""), "texto": texto}
    return {"quien": m.get("quien", ""), "hora": m.get("hora", ""), "texto": texto[:MAX_TEXTO],
            "recortado": len(texto) - MAX_TEXTO}


def recortado(m: dict) -> dict:
    """Un mensaje como viaja a la web: con su texto recortado a `MAX_TEXTO` y diciendo cuánto faltó."""
    return _recortado(m)


def pagina(config, sesiones: list[str], *, sesion: str = "", antes: int | None = None,
           despues: int | None = None, n: int = POR_PAGINA) -> dict:
    """Un trozo de la conversación de un hilo. `sesiones` son las de ese hilo (`hilos --json`): la pedida
    tiene que ser una de ellas; sin pedir ninguna, la primera que tenga archivo (ver `mensajes_del_hilo`)."""
    sid, mensajes, mtime = mensajes_del_hilo(config, sesiones, sesion)
    total = len(mensajes)
    n = max(1, min(int(n), MAXIMO))
    if despues is not None:
        ini = min(max(int(despues), 0), total)
        fin = min(total, ini + MAXIMO)
    elif antes is not None:
        fin = min(max(int(antes), 0), total)
        ini = max(0, fin - n)
    else:
        fin = total
        ini = max(0, total - n)
    return {"sesion": sid, "sesiones": list(sesiones), "total": total, "desde": ini, "hasta": fin,
            "mensajes": [_recortado(m) for m in mensajes[ini:fin]], "modificada": mtime}
