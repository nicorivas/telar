"""Llevar un hilo a otra máquina de la persona por el bus: su conversación viaja, y allá se retoma.

Es `telar hilo llevar <hilo> <máquina>` hacia otra máquina del bus (también una de `[remotos]`: por ssh ya no se mudan
hilos si la otra está en el bus), y «traer aquí», que le pide a la dueña que lo lleve.

    mandar(ctx, maquina, sid, archivo, relativa)              de este lado: la conversación y su carpeta, solo lo que
                                                              allá falta (telar.replica), y allá queda donde el
                                                              agente la busca
    detener(config, tel, hilo, a) / reanudar(config, hilo)    su agente se detiene antes de copiar (su ventana espera,
                                                              y no despierta mientras viaja); si se echa atrás, sigue
    abrir_alla(ctx, hilo, maquina, sid, mandada, relativa)    y que allá lo tome y lo abra retomándola
    llegar(ctx, pedido)                                       del otro (el nodo, verbo `hilo-llegar`): lo toma
                                                              (telar.dueno.tomar) y lo abre retomándola
    abrir_tomado(ctx, hilo, registro)                         el nodo, si lo tomó y no alcanzó a abrirlo
    inicio(ctx, relativa)                                     dónde arranca aquí el agente de un hilo que llega
    traer_aqui(ctx, pedido)                                   el dueño del hilo, cuando otra máquina lo pide
                                                              (verbo `hilo-traer`, «traer a esta máquina»): lo
                                                              lleva a la que pide, con `telar hilo llevar` aparte, y
                                                              quien pidió sigue su progreso (`mudanza-progreso`)
    esperar_turno(config, hilo, archivo)                      antes de copiar: que el agente termine su turno
    registro_de(est, hilo) / aplicar_registro(est, hilo, r)   lo que viaja con el hilo: su padre, sus etiquetas, su
                                                              prioridad, su esfuerzo, si es público y sus
                                                              borradores (telar.borradores)
    casilla_de(config, hilo)                                  lo que espera en su casilla local, que viaja con él

**Un dueño, con época** (telar.dueno; docs/propuestas/mudanza-de-hilos.md, etapa 3). El registro del hilo en el bus dice
de qué máquina es. El traspaso: el dueño lo **cede** (el registro dice a cuál, y su agente se detiene: desde ahí su
conversación no cambia), la conversación viaja, y la que recibe lo **toma** escribiendo el registro condicionado a la
época que se le cedió, y lo abre. Si algo falla antes de que lo tome, el dueño se echa atrás (la época sube, así que ya
no se puede tomar) y su agente despierta; si ya lo tomó, vive allá aunque no haya alcanzado a abrirlo (su nodo lo abre).
Nunca dos vivos, y nada se archiva aquí: el hilo vive allá, y aquí se lo ve como de allá.

Antes de copiar se espera siempre a que el agente termine su turno, la pida quien la pida (la página, «traer», la CLI o
el agente mismo). Lo que no es la conversación (la etapa 2): lo sin subir del repositorio del hilo se mira antes
(telar.sin_subir) y se sube o se lleva igual, a elección; allá, el repositorio se pone al día antes de abrir; un hijo
con rama no se muda; su registro y su casilla viajan con él.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

#: el verbo del nodo que recibe
VERBO = "hilo-llegar"
#: el que pregunta antes, sin mover nada, si allá se puede recibir (`revisar`)
VERBO_REVISAR = "hilo-revisar"
#: el que pide a la dueña de un hilo cómo va su mudanza (`progreso_de`): para seguir desde aquí un «traer»
VERBO_PROGRESO = "mudanza-progreso"
#: los pasos de una mudanza, en orden: lo que la página muestra mientras ocurre (`progreso`). `esperar` solo aparece si
#: el agente estaba en medio de un turno, `subir` si se eligió subir lo suyo antes (telar.sin_subir) y `detener` si su
#: agente estaba abierto. Cerrar va después de abrir: aquí no se toca nada hasta que allá lo tomó
PASOS = ("revisar", "esperar", "subir", "detener", "copiar", "abrir", "cerrar", "listo")
#: cuánto espera la respuesta de `hilo-llegar` (sin ella, el registro dice si allá lo tomó)
ESPERA_ABRIR = 60.0


class ErrorDeMudanza(Exception):
    pass


def ruta_progreso(config, hilo: str) -> Path:
    from telar import casilla

    d = Path(config.estado) / "llevar"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{casilla.ficha(config, hilo)}.json"


def progreso(config, hilo: str, paso: str, **datos) -> None:
    """Deja escrito en qué va la mudanza de `hilo` (`<estado>/llevar/<hilo>.json`): el paso (de `PASOS`, o «falla»),
    a qué máquina, cuánto pesa la conversación y lo que haya que decir. Una mudanza nueva empieza en «revisar» con su
    `maquina`; lo demás se suma a lo que había. La página lo lee mientras ocurre (GET
    /hilo/llevar/progreso) para dibujar la transición. Un error al escribirlo no detiene la mudanza."""
    import json
    import time

    try:
        ruta = ruta_progreso(config, hilo)
        # una mudanza nueva empieza en «revisar» con su máquina; lo demás se suma a lo que había
        nueva = paso == "revisar" and "maquina" in datos
        antes = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() and not nueva else {}
        antes.update(datos, paso=paso, hilo=hilo, hora=time.time())
        tmp = ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps(antes, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ruta)
    except (OSError, ValueError):
        pass


def progreso_de(config, hilo: str) -> dict:
    """En qué va la mudanza de `hilo` que corre (o corrió) aquí: lo que dejó `progreso`, {} si ninguna. Lo pide la
    página de aquí (GET /mudanza) y, por el bus, la máquina que pidió traerlo (`mudanza-progreso`)."""
    import json

    try:
        d = json.loads(ruta_progreso(config, hilo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def revisar(ctx, p: dict) -> dict:
    """Del lado que recibiría, sin mover nada: lo que haría fallar la llegada de este hilo (`graves`: no se lleva) y lo
    que haría que llegue a medias (`avisos`: se pregunta). Lo que ya falló en un telar alojado: sin agente declarado,
    sin `claude` en el PATH del servicio, la carpeta del hilo sin clonar."""
    import shutil

    from telar.agente import claude_code
    from telar.ordenes import _comun

    hilo, sid = str(p.get("hilo") or "").strip(), str(p.get("sesion") or "")
    relativa = str(p.get("relativa") or "")
    graves, avisos = [], []
    if sid and ctx.config.agente.nombre != claude_code.NOMBRE:
        graves.append(f"aquí el agente de los hilos es «{ctx.config.agente.nombre or 'ninguno'}»: una conversación de"
                      f" Claude no se retoma ([agente] nombre = \"{claude_code.NOMBRE}\" en su configuración)")
    if sid and not shutil.which("claude"):
        graves.append("aquí el servicio de telar no encuentra `claude` en su PATH (falta ~/.local/bin en su servicio:"
                      " telar instalar lo arregla)")
    tel = _comun.tejer(ctx, con_ficha=False)
    if hilo in tel.vivos and tel.estado.remotos().get(hilo) is None:
        graves.append(f"aquí ya hay un hilo «{hilo}» abierto")
    if relativa and not relativa.startswith("/") and not (Path(ctx.config.raiz) / relativa).is_dir():
        avisos.append(f"su carpeta ({relativa}) no existe aquí: se abriría en la raíz, sin sus archivos"
                      " (¿falta clonar su repositorio?)")
    # la conversación ya escrita aquí no impide nada: es la copia de cuando el hilo se fue de esta máquina (traerlo de
    # vuelta), y al llegar se reemplaza por la de allá (`llegar`). Lo que sí impediría, un hilo vivo con ese nombre,
    # ya se revisó arriba
    from telar import sin_subir

    return {"ok": True, "graves": graves, "avisos": avisos, "repos": sin_subir.en_destino(ctx, p.get("repos") or [])}


#: lo que se manda de la casilla local de un hilo al llevarlo (bytes del JSON): lo que no quepa en un pedido del bus
#: queda aquí, y se dice
TOPE_CASILLA = 600 * 1024


def registro_de(est, hilo: str) -> dict:
    """Lo que viaja con un hilo, de su registro: del que cuelga (el que se le puso o el que lo abrió; "" si de ninguno),
    sus etiquetas, su prioridad (None, la de siempre), el esfuerzo de su agente, si es público y los borradores que la
    persona le guardó (telar.borradores: sus próximos prompts, con su espera). Antes llegaba sin su padre, y no le
    avisaba al terminar."""
    prioridad = est.prioridades().get(hilo)
    return {"padre": est.padre(hilo), "etiquetas": list(est.etiquetas().get(hilo, ())),
            "prioridad": int(prioridad) if prioridad is not None else None, "esfuerzo": est.esfuerzos().get(hilo, ""),
            "publico": hilo in est.publicos(), "borradores": est.borradores(hilo)}


def aplicar_registro(est, hilo: str, r: dict) -> list[str]:
    """Del lado que recibe: el registro que trae el hilo (`registro_de`) queda como el de aquí, entero (lo que allá no
    tenía, aquí tampoco). Lo que no se pudo (un padre que haría un círculo), en una línea cada uno."""
    if not isinstance(r, dict):
        return []
    problemas = []
    if "padre" in r:
        try:
            est.colgar(hilo, str(r.get("padre") or ""))
        except ValueError as e:
            problemas.append(f"no cuelga de «{r.get('padre')}»: {e}")
    if "etiquetas" in r:
        try:
            est.etiquetar(hilo, [str(x) for x in r.get("etiquetas") or []])
        except ValueError as e:
            problemas.append(f"sus etiquetas: {e}")
    if "prioridad" in r:
        try:
            est.prioridad(hilo, None if r.get("prioridad") is None else int(r["prioridad"]))
        except (ValueError, TypeError) as e:
            problemas.append(f"su prioridad: {e}")
    if "esfuerzo" in r:
        est.anotar_esfuerzo(hilo, str(r.get("esfuerzo") or ""))
    if "publico" in r:
        (est.publicar if r.get("publico") else est.privar)(hilo)
    if isinstance(r.get("borradores"), list):
        # los de allá, enteros: un telar de antes no los manda, y entonces los de aquí (si había) quedan
        est.poner_borradores(hilo, r["borradores"])
    return problemas


def casilla_de(config, hilo: str) -> tuple[list[dict], int]:
    """Lo que espera en la casilla local de un hilo (pendiente, avisos y lo que un gancho imprimió sin que se viera
    entrar), para llevarlo con él: allá lo entrega su nodo. (los que van, cuántos quedan aquí por no caber)."""
    import json

    from telar import casilla

    todos = casilla.pendientes(config, hilo) + [casilla._de_vuelta(m) for m in casilla.en_camino(config, hilo)]
    van, peso = [], 0
    for m in todos:
        peso += len(json.dumps(m, ensure_ascii=False).encode())
        if peso > TOPE_CASILLA:
            break
        van.append(m)
    return van, len(todos) - len(van)


def recibir_casilla(config, hilo: str, mensajes) -> int:
    """Del lado que recibe: los mensajes que esperaban al hilo en la otra máquina, en su casilla de aquí (el mismo id
    no se deja dos veces). Cuántos quedaron."""
    from telar import casilla

    n = 0
    for m in mensajes if isinstance(mensajes, list) else []:
        if isinstance(m, dict) and m.get("id"):
            n += casilla.dejar(config, hilo, {**m, "hilo": hilo, "para": hilo})
    return n


def maquinas_del_bus(config) -> list[str]:
    """Las otras máquinas de la persona que se ven en el bus (sus fotos), las que estén en línea."""
    from telar import espejo

    try:
        return [e["nombre"] for e in espejo.leer_todos(config) if e.get("en_linea") and not e.get("error")]
    except Exception:  # noqa: BLE001
        return []


def mandar(ctx, maquina: str, sid: str, archivo: Path | None, relativa: str = "", *, hilo: str = "") -> dict:
    """La conversación `sid` (su `.jsonl` y su carpeta `<sid>/`) a `maquina`: solo lo que allá falta, de a pedazos por
    el bus (telar.replica), y allá queda donde el agente del hilo la busca (`relativa`, la carpeta del hilo). Con
    `hilo`, lo que va mandando queda en su progreso. Devuelve lo que pasó ({replica: true, bytes, mandados, red,
    conversacion, aparte, aviso}). Sin conversación (un hilo sin mensajes todavía), nada: allá se abre con una nueva.
    Aquí no toca nada. ErrorDeMudanza si no llegó, o si allá corre un telar de antes (que no sabe recibirla así ni tomar
    el hilo con su época: hay que actualizarlo)."""
    if archivo is None:
        return {"ruta": "", "bytes": 0}
    from telar import replica

    try:
        r = replica.mandar(ctx.config, maquina, sid, Path(archivo), {"relativa": relativa},
                           al_avanzar=al_copiar(ctx.config, hilo) if hilo else None)
    except replica.SinReplica:
        raise ErrorDeMudanza(f"{maquina} no atiende la copia: su nodo no está, o corre un telar de antes (que no sabe "
                             "recibir un hilo con su dueño: telar desplegar)") from None
    except replica.ErrorDeReplica as e:
        raise ErrorDeMudanza(f"la conversación no llegó a {maquina}: {e}") from None
    return {"replica": True, **r}


def al_copiar(config, hilo: str):
    """Lo que anota en el progreso de la mudanza de `hilo` cuánto va copiado (telar.replica.mandar, `al_avanzar`): lo
    que pesa todo, lo que faltaba allá y lo que ya llegó."""
    def avanza(cuenta: dict) -> None:
        progreso(config, hilo, "copiar", por_mandar=cuenta.get("por_mandar", 0),
                 mandados=cuenta.get("mandados_ahora", 0), total=cuenta.get("total", 0))

    return avanza


def abrir_alla(ctx, hilo: str, maquina: str, sid: str, mandada: dict, relativa: str, *,
               espera: float = ESPERA_ABRIR, extra: dict | None = None) -> dict:
    """Le pide a `maquina` que tome el hilo (con la época que se le cedió, en `extra["dueno"]`) y lo abra retomando la
    conversación que ya le llegó. Devuelve lo que contestó allá: {ok, carpeta, aviso}. Si no contesta a tiempo, el
    registro del bus dice si lo tomó: si sí, llegó (y allá se abre); si no, ErrorDeMudanza. También si allá contestó que
    no (`tomado`: lo tomó pero no pudo abrirlo, y su nodo lo abrirá)."""
    from telar import bus as mod_bus
    from telar import dueno

    llego = bool(mandada.get("ruta") or mandada.get("replica"))
    r = mod_bus.pedir(ctx.config, maquina, VERBO, {"hilo": hilo, "sesion": sid if llego else "",
                                                   "relativa": relativa, **({"replica": True} if llego else {}),
                                                   **(extra or {})},
                      espera=espera + (60 if (extra or {}).get("repos") else 0))
    if r.get("ok"):
        return r
    error = str(r.get("error") or "no respondió")
    if r.get("tomado") or "a tiempo" in error:
        reg = dueno.registro(ctx.config, hilo)
        if dueno.de(reg) == maquina:
            return {"ok": True, "carpeta": "", "tomado": True,
                    "aviso": f"{maquina} lo tomó ({error}): allá se abre (si no alcanzó, lo abre su nodo)"}
    raise ErrorDeMudanza(f"{maquina} recibió la conversación pero no tomó el hilo: {error}")


def esperar_turno(config, hilo: str, archivo: Path | None, *, tope: float = 600.0, quieto: float = 4.0,
                  paso: float = 1.0, al_esperar=None) -> str:
    """Antes de copiar la conversación de un agente: que termine su turno, para que lo que dijo al final viaje con ella
    y no quede escribiendo en una copia que ya se fue. Se pida desde donde se pida (la página, «traer», la CLI, el
    agente mismo desde un proceso aparte). Terminó cuando su atención ya no es «trabajando» (los ganchos la anotan) y
    su conversación lleva `quieto` segundos sin crecer (lo que ya llevaba quieta antes de mirar cuenta). `al_esperar()`
    se llama una vez si hay que esperar. "" cuando terminó; si pasa `tope` sin terminar, por qué no se lleva."""
    import time

    from telar import estado as mod_estado
    from telar.modelo import Atencion

    limite = time.monotonic() + tope
    antes, desde, avisado = None, time.monotonic(), False
    while True:
        try:
            st = Path(archivo).stat() if archivo is not None else None
        except OSError:
            st = None
        ahora_pesa = st.st_size if st is not None else 0
        if ahora_pesa != antes:
            # lo que ya llevaba sin crecer cuando se miró por primera vez, o desde que creció ahora
            ya_quieta = min(quieto, max(0.0, time.time() - st.st_mtime)) if st is not None and antes is None else 0.0
            antes, desde = ahora_pesa, time.monotonic() - ya_quieta
        try:
            trabajando = mod_estado.abrir(config).atencion(hilo) == Atencion.TRABAJANDO
        except Exception:  # noqa: BLE001 - sin poder leer su atención, basta con que la conversación no crezca
            trabajando = False
        if not trabajando and time.monotonic() - desde >= quieto:
            return ""
        if time.monotonic() >= limite:
            return (f"su agente sigue trabajando después de {round(tope / 60)} min: no se movió nada"
                    " (pídelo de nuevo cuando termine su turno)")
        if not avisado and al_esperar is not None:
            avisado = True
            try:
                al_esperar()
            except Exception:  # noqa: BLE001 - avisar no detiene la espera
                pass
        time.sleep(paso)


SID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def inicio(ctx, relativa: str) -> tuple[Path, Path | None, str]:
    """Dónde arranca aquí el agente de un hilo que llega vinculado a `relativa` (su carpeta bajo la raíz de allá, o
    absoluta), y por eso en qué carpeta de proyecto busca Claude su conversación: (inicio, la carpeta del hilo aquí o
    None, aviso). Si la carpeta no existe aquí, el hilo se abre en la raíz y el aviso lo dice."""
    from telar.agente import lanzar

    carpeta_hilo = Path(ctx.config.raiz) / relativa if relativa and not relativa.startswith("/") else (
        Path(relativa) if relativa else None)
    aviso = ""
    if carpeta_hilo is not None and not carpeta_hilo.is_dir():
        aviso = f"su carpeta ({relativa}) no existe aquí: se abre en la raíz, sin esos archivos"
        carpeta_hilo = None
    return (lanzar.carpeta(ctx.config, carpeta_hilo) or Path(ctx.config.raiz)).resolve(), carpeta_hilo, aviso


def llegar(ctx, p: dict) -> dict:
    """Del lado que recibe: toma el hilo (`dueno`: {clave, de, epoca}, la época que se le cedió; telar.dueno.tomar) y lo
    abre retomando su conversación, que ya está donde el agente la busca (la dejó telar.replica.cerrar), con su
    repositorio al día, su registro y lo que esperaba en su casilla. Si allá se echaron atrás, no lo toma ni lo abre. Si
    lo tomó y no pudo abrirlo, lo dice (`tomado`): es de aquí, y el nodo lo abre después (`abrir_tomado`)."""
    from telar import bus as mod_bus
    from telar import dueno, rutas
    from telar.ordenes import _comun

    hilo, sid = str(p.get("hilo") or "").strip(), str(p.get("sesion") or "")
    relativa = str(p.get("relativa") or "")
    cedido = p.get("dueno")
    # sin `sesion`: un hilo sin mensajes todavía, que se abre aquí con una conversación nueva
    if not hilo or (sid and not SID.match(sid)):
        return {"ok": False, "error": "falta el hilo, o su conversación no es un id"}
    if not isinstance(cedido, dict) or not cedido.get("de") or not cedido.get("clave"):
        return {"ok": False, "error": "llegó sin su dueño ni su época: el telar de allá es de antes (telar desplegar)"}
    if sid and not p.get("replica"):
        return {"ok": False, "error": "su conversación no llegó de a pedazos: el telar de allá es de antes (telar desplegar)"}
    from telar.agente import claude_code

    if sid and ctx.config.agente.nombre != claude_code.NOMBRE:
        return {"ok": False, "error": f"aquí el agente es «{ctx.config.agente.nombre or 'ninguno'}»: solo se retoma una de Claude"}

    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None:
        return {"ok": False, "error": tel.aviso or "aquí no hay multiplexor"}
    if not tel.viva:
        # sin sesión (un lugar recién creado en un servidor, que nadie abrió todavía): se levanta vacía, como
        # `telar tejer --vacia`, y el hilo que llega es el primero
        try:
            tel.mux.tejer()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"aquí la sesión no está viva y no pude levantarla: {e}"}
        tel = _comun.tejer(ctx, con_ficha=False)
        if not tel.viva:
            return {"ok": False, "error": tel.aviso or "aquí la sesión no está viva"}
    if hilo in tel.vivos and tel.estado.remotos().get(hilo) is None:
        return {"ok": False, "error": f"aquí ya hay un hilo «{hilo}» abierto"}
    # donde arranca el agente, y ahí la busca Claude: su carpeta de proyecto (telar.rutas)
    inicio_, carpeta_hilo, aviso = inicio(ctx, relativa)
    if sid and not (rutas.proyecto(inicio_) / f"{sid}.jsonl").is_file():
        return {"ok": False, "error": f"la conversación no está donde la dejó la copia ({rutas.proyecto(inicio_)})"}

    # tomarlo: desde aquí es de esta máquina, aunque no alcance a abrirse. Solo si allá sigue cedido a esta, con esa época
    yo, clave = mod_bus.maquina(ctx.config), str(cedido["clave"])
    valor = {"nombre": hilo, "vivo": False, "conversacion": sid, "vinculo": relativa if carpeta_hilo else ""}
    try:
        tomado = dueno.con_almacen(ctx.config, lambda kv: dueno.tomar(kv, clave, yo=yo, de_=str(cedido["de"]),
                                                                     epoca_=int(cedido.get("epoca") or 0), valor=valor))
    except Exception as e:  # noqa: BLE001 - sin el registro no se toma: allá sigue
        return {"ok": False, "error": f"no pude tomarlo en el registro del bus: {type(e).__name__}: {e}"}
    if not tomado:
        return {"ok": False, "error": f"la mudanza ya no vale: en {cedido['de']} se echó atrás (o lo tomó otra)"}

    from telar import sin_subir

    # sus repositorios al día antes de abrirlo: que el agente vea aquí lo que allá se subió
    for x in sin_subir.al_dia(ctx, p.get("repos") or []):
        aviso = (aviso + "; " if aviso else "") + x
    r = _abrir(ctx, tel, hilo, sid, relativa, carpeta_hilo, registro=p.get("registro"))
    if not r.get("ok"):
        return {**r, "tomado": True, "aviso": aviso}
    try:
        dueno.con_almacen(ctx.config, lambda kv: dueno.abierto(kv, clave, yo=yo))
    except Exception:  # noqa: BLE001 - el nodo lo da por abierto al verlo vivo
        pass
    # lo que lo esperaba allá, ya abierto aquí (antes, si no abría, allá lo habría entregado y aquí otra vez)
    n = recibir_casilla(ctx.config, hilo, p.get("casilla") or [])
    aviso = "; ".join(x for x in (aviso, r.get("aviso", "")) if x)
    # cuántos borradores quedaron aquí (telar.borradores): con eso la de allá sabe que llegaron, y suelta los suyos
    try:
        borradores = len(tel.estado.borradores(hilo))
    except Exception:  # noqa: BLE001 - sin poder leerlos, allá se quedan los suyos
        borradores = None
    return {"ok": True, "carpeta": str(inicio_), "conversacion": r.get("conversacion", ""), "aviso": aviso, "casilla": n,
            **({"borradores": borradores} if borradores is not None else {})}


def _abrir(ctx, tel, hilo: str, sid: str, relativa: str, carpeta_hilo: Path | None, *, registro=None) -> dict:
    """Abre aquí un hilo que ya es de esta máquina, retomando su conversación: su vínculo, su conversación anotada, su
    registro, y su ventana con el agente. Si aquí había una ventana que solo lo miraba allá, se cierra después de abrir
    la nueva (nunca queda un momento sin ventana, que el nodo llenaba trayendo otra vez la de allá). {ok, conversacion,
    aviso} o {ok: false, error}."""
    from telar import rutas
    from telar.agente import lanzar

    est = tel.estado
    remoto = est.remotos().get(hilo)
    viejos = [h.id for h in tel.mux.hilos() if h.nombre == hilo] if remoto is not None else []
    inicio_, _, _ = inicio(ctx, relativa)
    ruta = rutas.proyecto(inicio_) / f"{sid}.jsonl" if sid else None
    aviso = ""
    if carpeta_hilo is not None:
        est.vincular(hilo, relativa)
    if sid:
        est.anotar_sesion(hilo, sid)
    est.desarchivar(hilo)
    for x in aplicar_registro(est, hilo, registro) if isinstance(registro, dict) else []:
        aviso = (aviso + "; " if aviso else "") + x
    if remoto is not None:
        est.olvidar_remoto(hilo)
    try:
        lanz = lanzar.para_hilo(ctx.config, hilo, carpeta_hilo)
        if lanz is None:
            tel.mux.crear_tab(hilo, ruta=carpeta_hilo, foco=False)
        else:
            tel.mux.crear_tab(hilo, ruta=lanz.carpeta, comando=lanz.comando, foco=False)
            lanzar.anotar(ctx.config, hilo, lanz, tel.mux)
    except Exception as e:  # noqa: BLE001 - la conversación quedó: el nodo lo intenta de nuevo
        if remoto is not None and remoto.get("remoto"):
            est.anotar_remoto(hilo, remoto["remoto"], remoto.get("sesion", ""))
        return {"ok": False, "error": f"no pude abrir el hilo: {e}" + (f" (la conversación quedó aquí: {ruta})" if ruta else "")}
    for viejo in viejos:
        try:
            tel.mux.cerrar(viejo)
        except Exception:  # noqa: BLE001 - si no se cierra, queda una ventana de más, nada se pierde
            pass
    retoma = getattr(lanz, "retoma", "") if lanz is not None else ""
    if sid and lanz is not None and retoma != sid:
        aviso = (aviso + "; " if aviso else "") + "se abrió, pero no retomando esa conversación"
    return {"ok": True, "conversacion": str(ruta) if ruta else "", "aviso": aviso}


def abrir_tomado(ctx, hilo: str, registro: dict) -> tuple[bool, str]:
    """Lo que hace el nodo con un hilo que esta máquina tomó y no alcanzó a abrir (el nodo se reinició, o abrir falló):
    abrirlo retomando su conversación, con lo que dice su registro, y dar el traspaso por terminado. (True, qué hizo) o
    (False, por qué no)."""
    from telar import bus as mod_bus
    from telar import dueno
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None or not tel.viva:
        return False, tel.aviso or "aquí la sesión no está viva"
    hecho = "ya estaba abierto (la llegada no alcanzó a contestar)"
    if hilo not in tel.vivos:
        relativa = str(registro.get("vinculo") or "")
        _, carpeta_hilo, _ = inicio(ctx, relativa)
        r = _abrir(ctx, tel, hilo, str(registro.get("conversacion") or ""), relativa, carpeta_hilo)
        if not r.get("ok"):
            return False, str(r.get("error"))
        hecho = "lo abrí"
    yo = mod_bus.maquina(ctx.config)
    dueno.con_almacen(ctx.config, lambda kv: dueno.abierto(kv, dueno.clave(ctx.config, hilo), yo=yo))
    return True, hecho


def detener(config, tel, hilo: str, a: str) -> str:
    """Detiene al agente de un hilo que se va a `a`: su panel se reemplaza por uno que espera (como al dormirlo,
    telar.dormir), anotado con `cede`, que no despierta mientras viaja. Desde aquí su conversación no cambia, y lo que se
    copie es la final. "" si se detuvo (o no tenía agente abierto); si no, por qué."""
    from telar import dormir
    from telar import estado as mod_estado
    from telar.agente import lanzar

    try:
        ventana, panel = dormir._panel_de(tel.mux, hilo)
    except Exception as e:  # noqa: BLE001
        return f"no pude ver su ventana: {e}"
    if ventana is None:
        return ""
    if panel is None:
        return "su ventana tiene más de un panel: ciérralos antes de llevarlo"
    est = mod_estado.abrir(config)
    sid = (est.sesiones().get(hilo) or ("",))[0]
    atencion, desde = est.atenciones().get(hilo, (None, None))
    with dormir.candado(config):
        cuando = datetime.now()
        registro = {"desde": cuando.isoformat(timespec="seconds"), "panel": str(panel.id), "ventana": str(ventana),
                    "conversacion": sid, "atencion": atencion.value if atencion else "ninguna",
                    "atencion_desde": desde.isoformat(timespec="seconds") if desde else "", "cede": a}
        est.anotar_dormido(hilo, registro)
        try:
            carpeta = lanzar.carpeta(config, dormir._carpeta_hilo(config, est, hilo))
        except Exception:  # noqa: BLE001
            carpeta = None
        try:
            nuevo = tel.mux.abrir_pane(dormir.programa(hilo, desde=cuando, conversacion=sid, pedido=True,
                                                       motivo=f"se está yendo a {a}"),
                                       reemplaza=str(panel.id), ruta=carpeta if carpeta and Path(carpeta).is_dir() else None,
                                       foco=False)
        except Exception as e:  # noqa: BLE001
            est.olvidar_dormido(hilo)
            return f"no pude detener a su agente: {e}"
        est.anotar_dormido(hilo, {**registro, "panel": str(getattr(nuevo, "id", "") or "")})
    return ""


def reanudar(config, hilo: str) -> str:
    """La mudanza se echó atrás: el agente que se detuvo para irse despierta en su ventana, retomando su conversación.
    Lo que hizo, en una línea."""
    from telar import dormir

    try:
        return dormir.despertar(config, hilo, cesion=True) or f"«{hilo}» sigue aquí"
    except RuntimeError as e:
        return f"«{hilo}» sigue aquí, pero no pude despertarlo: {e} (⏎ en su ventana, o telar hilo retomar)"


def soltar(config, tel, hilo: str) -> None:
    """El hilo ya es de otra máquina: su ventana de aquí (la que esperaba mientras viajaba) se cierra, y se olvida que
    dormía. Lo de aquí (su conversación, su vínculo) queda, sin archivarlo: vive allá, y aquí se lo ve como de allá."""
    from telar import estado as mod_estado

    est = mod_estado.abrir(config)
    # la ventana que esperaba (la anotó `detener`), y no otra con su nombre: la que mira el hilo allá (si esta máquina
    # tiene a aquella en [remotos], el nodo la trae) se queda
    esperaba = str((est.dormidos().get(hilo) or {}).get("ventana") or "")
    try:
        if tel.mux is not None:
            ids = [h.id for h in tel.mux.hilos() if h.nombre == hilo]
            ventana = esperaba if esperaba in ids else (ids[0] if len(ids) == 1 and hilo not in est.remotos() else None)
            if ventana is not None:
                tel.mux.cerrar(ventana)
    except Exception:  # noqa: BLE001 - si no se cierra, la cierra el nodo
        pass
    est.olvidar_dormido(hilo)


MAQUINA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
#: cuánto espera la dueña, al pedirle traer un hilo, antes de contestar que sigue en curso: lo que pide confirmar falla
#: antes
ESPERA_TRAER = 20.0


def traer_aqui(ctx, p: dict) -> dict:
    """Lo que corre el dueño de un hilo cuando otra máquina de la persona lo pide para sí («traer a esta máquina»):
    `telar hilo llevar <la que pide> --hilo <hilo>`, que la manda por el bus como siempre. Corre aparte, en su propio
    proceso (telar.servicios.llevar): esperar el turno del agente y copiar una conversación grande tarda minutos, y
    quien pidió sigue su progreso con `mudanza-progreso`. Lo que falla rápido (lo que pide confirmar) se contesta al
    tiro. `si`: aunque haya trabajo sin subir (sin él, falla diciéndolo, y quien pide pregunta, con el detalle en el
    progreso); `subir`: subirlo antes. Devuelve {ok, codigo, salida, en_curso}."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import llevar as servicio

    hilo, a = str(p.get("hilo") or "").strip(), str(p.get("a") or "").strip()
    if not hilo or not MAQUINA.match(a):
        return {"ok": False, "error": "falta el hilo o a qué máquina"}
    try:
        r = servicio.llevar(ctx, hilo, a, bool(p.get("si")), espera=ESPERA_TRAER, subir=bool(p.get("subir")))
    except ErrorDeServicio as e:
        return {"ok": True, "codigo": int(e.datos.get("codigo") or 1), "salida": str(e.datos.get("salida") or f"telar: {e}")}
    return {"ok": True, "codigo": 0, "salida": r.salida, "en_curso": r.en_curso}
