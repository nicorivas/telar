"""Los borradores de un hilo: los próximos prompts que la persona escribe mientras su agente trabaja, para mandárselos
cuando le toque.

A veces un hilo está en medio de un turno y la persona ya quiere escribir lo siguiente, pero no puede hacerlo en la
entrada de Claude Code: primero tiene que ver qué contesta, por si hay que responderle algo antes. Lo escribe aquí, en
una lista corta y en orden, y cuando el agente termina lo manda. Se guardan del lado de telar, en el estado de la
máquina donde vive el hilo (`borradores.json`, telar.estado), no en el navegador: sobreviven a una recarga, se ven desde
el teléfono y viajan con el hilo en la mudanza (telar.mudanza, `registro_de`).

Mandar uno es escribirlo en la entrada del agente por el mismo camino que la terminal de la página y que `telar
pendiente` (`dormir.escribir`: tmux, pegado entre corchetes si tiene varias líneas). Sin ⏎ (`escribir`) queda puesto para
que la persona lo revise; con ⏎ (`enviar`), sale. Al mandarlo, deja la lista.

Si el agente está trabajando (o espera a la persona: un permiso, una pregunta), mandarlo ahora lo mezclaría con su turno:
se niega con 409 y `ocupado`, y la persona puede dejarlo **en espera**: sale solo cuando el agente termine su turno. Eso
lo hace `al_terminar`, que llama el evento de fin de turno (telar.ordenes.agente) y lanza `soltar` aparte, y de
respaldo el nodo cada 30 s (por si un turno terminó sin evento: un Esc sin el mod). Sale uno por turno: el primero en
espera, en el orden de la lista.

    mandar(config, tel, hilo, id, enviar=, esperar=)   escribirlo ya, o dejarlo en espera
    ocupado(est, hilo)                                 "trabajando" | "espera" | "": si mandarlo ahora se mezcla
    soltar(config, tel, hilo)                          el primero en espera, si el agente quedó quieto
    al_terminar(config, hilo)                          lo que hace el evento de fin de turno (no espera nada)
    pendientes(config)                                 los hilos de aquí con alguno en espera
"""

from __future__ import annotations

import subprocess
import sys
import time

from telar import estado as mod_estado
from telar.modelo import Atencion

#: lo más largo que se guarda de un borrador (caracteres): es un prompt, no un documento
TOPE_TEXTO = 100_000
#: cuántos borradores puede tener un hilo
TOPE_POR_HILO = 50
#: cómo sale uno en espera: dejarlo en su entrada, o además apretar ⏎
COMOS = ("escribir", "enviar")
#: lo que espera `soltar` después del fin del turno, antes de escribir: que Claude Code vuelva a dibujar su entrada
PAUSA_SOLTAR = 1.5


class ErrorDeBorrador(Exception):
    """No se pudo: `codigo` es el HTTP que le corresponde (404 no está, 409 ocupado o cerrado, 422 mal pedido)."""

    def __init__(self, texto: str, codigo: int = 422, **datos) -> None:
        super().__init__(texto)
        self.codigo = codigo
        self.datos = datos


def ocupado(est, hilo: str) -> str:
    """Si escribirle ahora se mezcla con lo que hace su agente: "trabajando" (está en su turno), "espera" (le pregunta
    algo a la persona: lo que se escriba caería en el diálogo) o "" (quieto)."""
    atencion = est.atenciones().get(hilo, (Atencion.NINGUNA, None))[0]
    if atencion == Atencion.TRABAJANDO:
        return "trabajando"
    if atencion == Atencion.ESPERA:
        return "espera"
    return ""


def revisar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        raise ErrorDeBorrador("el texto de un borrador es texto")
    if len(texto) > TOPE_TEXTO:
        raise ErrorDeBorrador(f"un borrador tiene a lo más {TOPE_TEXTO} caracteres")
    return texto


def guardar(est, hilo: str, texto: str, id: str = "") -> dict:
    """Uno nuevo al final (sin `id`) o el mismo con su texto nuevo. 404 si el `id` ya no está (se mandó o se borró en
    otra parte); 422 si ya hay `TOPE_POR_HILO`."""
    revisar_texto(texto)
    if not id and len(est.borradores(hilo)) >= TOPE_POR_HILO:
        raise ErrorDeBorrador(f"«{hilo}» ya tiene {TOPE_POR_HILO} borradores: manda o borra alguno")
    try:
        return est.guardar_borrador(hilo, texto, id)
    except KeyError:
        raise ErrorDeBorrador(f"el borrador {id} de «{hilo}» ya no está: se mandó o se borró", 404) from None


def _hilo_de_aqui(tel, hilo: str):
    h = tel.por_nombre(hilo) if tel is not None else None
    if h is None or (getattr(h, "remoto", "") and h.remoto):
        raise ErrorDeBorrador(f"«{hilo}» no vive en esta máquina", 404)
    if not tel.vivo(h):
        raise ErrorDeBorrador(f"«{hilo}» no está abierto: retómalo, y lo guardado sigue aquí", 409, cerrado=True)
    return h


def escribir(config, tel, h, texto: str, *, enviar: bool) -> None:
    """Escribirle `texto` en su entrada (dormido, se despierta). Con varias líneas y sin ⏎, pegado entre corchetes: cada
    salto queda como salto, y nada sale hasta que la persona lo mande."""
    from telar import dormir

    if tel is None or tel.mux is None:
        raise ErrorDeBorrador("no hay multiplexor con el que escribirle", 409)
    varias = "\n" in texto or "\r" in texto
    dormir.escribir(config, tel, h, texto.replace("\r\n", "\n").rstrip("\n") if varias else texto, enviar=enviar,
                    pegar=varias and not enviar)


def mandar(config, tel, hilo: str, id: str, *, enviar: bool = False, esperar: bool = False) -> dict:
    """Mandarle un borrador a su hilo: escribirlo ya (`como`: «escrito» o «enviado»), o dejarlo en espera para cuando el
    agente termine su turno (`esperar`; «en espera», o lo escribe al tiro si ya terminó). Escrito, deja la lista.

    Ocupado y sin `esperar`: 409 con `ocupado`. Cerrado: 409 con `cerrado`. Si escribirlo falla, vuelve a su lugar."""
    from telar.mux import ErrorDeMux

    est = tel.estado if tel is not None and tel.estado is not None else mod_estado.abrir(config)
    lista = est.borradores(hilo)
    indice = next((i for i, b in enumerate(lista) if b["id"] == id), None)
    if indice is None:
        raise ErrorDeBorrador(f"el borrador {id} de «{hilo}» ya no está: se mandó o se borró", 404)
    b = lista[indice]
    if not b["texto"].strip():
        raise ErrorDeBorrador("está vacío: no hay qué mandar")
    h = _hilo_de_aqui(tel, hilo)
    if esperar:
        como = "enviar" if enviar else "escribir"
        est.esperar_borrador(hilo, id, como)
        if ocupado(est, hilo):
            return {"hilo": hilo, "id": id, "como": "en espera", "al_terminar": como}
        # ya terminó mientras se decidía: sale ahora, como si hubiera terminado recién
        hecho = soltar(config, tel, hilo, pausa=0)
        return {"hilo": hilo, "id": id, "como": hecho or "en espera", "al_terminar": "" if hecho else como}
    if que := ocupado(est, hilo):
        dice = "está trabajando" if que == "trabajando" else "te está preguntando algo"
        raise ErrorDeBorrador(f"«{hilo}» {dice}: escribirle ahora se mezcla con su turno", 409, ocupado=que)
    # se saca antes de escribir: dos que lo mandan a la vez no lo escriben dos veces
    if est.quitar_borrador(hilo, id) is None:
        raise ErrorDeBorrador(f"el borrador {id} de «{hilo}» ya no está: se mandó o se borró", 404)
    try:
        escribir(config, tel, h, b["texto"], enviar=enviar)
    except (ErrorDeMux, RuntimeError, OSError) as e:
        devolver(est, hilo, b, indice)
        raise ErrorDeBorrador(f"no pude escribirle a «{hilo}»: {e}", 502) from e
    return {"hilo": hilo, "id": id, "como": "enviado" if enviar else "escrito"}


def devolver(est, hilo: str, b: dict, indice: int) -> None:
    """Un borrador que salió de la lista y no se pudo escribir, de vuelta en su lugar (si no volvió ya)."""
    lista = est.borradores(hilo)
    if any(x["id"] == b["id"] for x in lista):
        return
    lista.insert(min(indice, len(lista)), b)
    est.poner_borradores(hilo, lista)


def soltar(config, tel, hilo: str, *, pausa: float = PAUSA_SOLTAR) -> str:
    """El primero que espera el fin del turno, escrito en su entrada si el agente quedó quieto: «escrito» o «enviado»; ""
    si no había ninguno o el agente sigue en lo suyo (un turno nuevo: espera al próximo fin). Si escribirlo falla,
    vuelve a la lista sin la espera, para que la persona lo vea y decida."""
    from telar.mux import ErrorDeMux

    if pausa:
        time.sleep(pausa)
    est = tel.estado if tel is not None and tel.estado is not None else mod_estado.abrir(config)
    if ocupado(est, hilo) or not any(b.get("al_terminar") for b in est.borradores(hilo)):
        return ""
    try:
        h = _hilo_de_aqui(tel, hilo)
    except ErrorDeBorrador:
        return ""  # cerrado o ido: queda en espera, y sale cuando vuelva y termine un turno
    indice = next((i for i, b in enumerate(est.borradores(hilo)) if b.get("al_terminar")), 0)
    b = est.tomar_borrador_en_espera(hilo)
    if b is None:
        return ""  # otro lo tomó
    enviar = b.get("al_terminar") == "enviar"
    try:
        escribir(config, tel, h, b["texto"], enviar=enviar)
    except (ErrorDeBorrador, ErrorDeMux, RuntimeError, OSError):
        b.pop("al_terminar", None)
        devolver(est, hilo, b, indice)
        return ""
    return "enviado" if enviar else "escrito"


def pendientes(config) -> list[str]:
    """Los hilos de aquí con algún borrador en espera."""
    try:
        todos = mod_estado.abrir(config).todos_los_borradores()
    except Exception:  # noqa: BLE001 - sin poder leerlo, ninguno
        return []
    return sorted(h for h, lista in todos.items() if any(b.get("al_terminar") for b in lista))


def al_terminar(config, hilo: str) -> bool:
    """El agente de `hilo` terminó su turno: si tiene un borrador en espera, `telar hilo borradores --soltar` corre
    aparte (no frena al gancho, y espera a que Claude Code vuelva a su entrada antes de escribir). True si lo lanzó."""
    if not hilo or hilo not in pendientes(config):
        return False
    try:
        subprocess.Popen([sys.executable, "-m", "telar", "hilo", "borradores", "--soltar", "--hilo", hilo],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        return False  # el nodo lo suelta en su próxima vuelta
    return True
