"""`telar mensaje` — un mensaje para un hilo o un agente, en la máquina que sea, por el bus.

    telar mensaje Secretaría "¿quedó la nota en T185?"
    telar mensaje secretaria -           el texto por la entrada estándar (sin tope de largo práctico)
    telar mensaje Faro "…" --tipo encargo
    telar mensaje Faro - --tipo persona --de "el panel"   lo escribe la persona, desde otra parte
    telar mensaje Faro@servidor "…"           el hilo Faro de esa máquina (lo mismo que hilo:Faro@servidor)
    telar mensaje Faro "…" --modo aviso      para que lo sepa: espera en su casilla y no lo despierta
    telar mensaje Faro "…" --modo encargo [--plazo 2026-10-24]
                                         un Encargo (`encargo:e-…`) que Faro acepta y cierra con un resultado
    telar mensaje --registro [N]         los últimos mensajes entre hilos, de todas las máquinas
    telar mensaje --retenidos            los que se retuvieron y nadie soltó ni descartó, entre los últimos 500
    telar mensaje --soltar <id>          mandar uno retenido (lo decide la persona)
    telar mensaje --descartar <id>       que uno retenido no salga nunca (lo decide la persona): queda en el registro
                                         como descartado, y a quien lo mandó le llega un aviso que no lo despierta

El mensaje espera en la casilla del hilo hasta que la máquina donde vive lo recoja (`telar nodo`) y
entra a la conversación por sus ganchos, entero, sin teclearlo. Un agente se nombra por su carpeta o
su nombre; cualquier otro nombre es un hilo, viva donde viva. Necesita `[bus] url`. Un nombre que no es de ningún
hilo ni agente, en ninguna máquina, se rechaza con los parecidos: su casilla no la leería nadie.

Entre hilos de una misma persona los mensajes corren sin pedirle permiso, con dos frenos en su lugar:
cada mensaje lleva cuántos saltos lleva su cadena sin que la persona hablara (`telar.casilla`), y
pasado el tope se retiene; y un hilo no manda más de cierto número por hora. Lo retenido queda en el
registro hasta que la persona lo suelte o lo descarte. Entre un padre y su hijo directo la cuenta es de los dos y
aparte (`casilla.cadena_familia`): no suma a la cadena de ninguno, y vuelve a empezar con un commit en
la carpeta del hijo, así el «listo» de un hijo no se retiene por lo que el padre habló con otros.

El modo (`--modo`, docs/propuestas/mensajes-con-modos.md) dice qué espera quien manda: `pedido` (lo de
siempre: despierta), `aviso` (no despierta) o `encargo` (despierta y crea un Encargo, telar.encargo, en la
máquina del destinatario). En qué anda un hilo, sin escribirle: `telar ficha <hilo>` y `telar hilo leer <hilo>`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from telar import bus as mod_bus
from telar.ordenes import _comun

AYUDA = "Un mensaje para un hilo o un agente, en la máquina que sea, por el bus."

#: cuántos mensajes manda un hilo por hora antes de que se retengan
TOPE_HORA = 30


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("mensaje", AYUDA)
    p.epilog = __doc__
    p.add_argument("para", nargs="?", default="", help="el hilo (su nombre) o el agente (su carpeta o su nombre)")
    p.add_argument("texto", nargs="*", help="el mensaje (o «-» para leerlo de la entrada)")
    p.add_argument("--registro", nargs="?", type=int, const=40, default=0, metavar="N", help="los últimos N mensajes")
    p.add_argument("--retenidos", action="store_true", help="los retenidos que nadie ha soltado ni descartado")
    p.add_argument("--soltar", default="", metavar="ID", help="mandar uno retenido")
    p.add_argument("--descartar", default="", metavar="ID",
                   help="que uno retenido no salga: queda como descartado y a quien lo mandó le llega un aviso")
    # persona: lo escribe la persona desde otra parte (el panel en el celular): le llega como suyo, no de un colega
    p.add_argument("--tipo", choices=("mensaje", "encargo", "persona"), default="mensaje")
    p.add_argument("--modo", choices=_Modos(MODOS), default="pedido",
                   help="aviso (no despierta), pedido (lo de siempre) o encargo (un Encargo con resultado)")
    p.add_argument("--plazo", default="", metavar="FECHA", help="con --modo encargo: para cuándo (2026-10-24)")
    p.add_argument("--de", default="", help="quién lo manda (por defecto, este hilo o esta máquina)")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.registro or o.retenidos:
        from telar.servicios import ErrorDeServicio
        from telar.servicios import mensajes as servicio

        try:
            r = servicio.registro(ctx, o.registro, retenidos=bool(o.retenidos))
        except ErrorDeServicio as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r.model_dump(mode="json"))
        lista = r.mensajes
        for m in lista:
            marca = {"retenido": "⏸ ", "descartado": "✕ "}.get(str(m.get("estado")), "")
            print(f"{str(m.get('creado', ''))[:16].replace('T', ' ')}  {marca}{m.get('de', '')} → {m.get('para', '')}"
                  + _comun.tenue(f"  {m.get('tipo', '')}{' · salto ' + str(m['saltos']) if m.get('saltos') else ''}"
                                 f"{' · ' + m['motivo'] if m.get('motivo') else ''} · {m.get('id', '')}"))
            print("    " + " ".join(str(m.get("texto", "")).split())[:160])
        return 0
    if o.soltar:
        from telar.servicios import ErrorDeServicio
        from telar.servicios import mensajes as servicio

        try:
            r = servicio.soltar(ctx, o.soltar).model_dump(mode="json")
        except ErrorDeServicio as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r)
        print(f"«{r['para']}»: soltado, en su casilla · id {r['id']}")
        return 0
    if o.descartar:
        from telar.servicios import ErrorDeServicio
        from telar.servicios import mensajes as servicio

        try:
            r = servicio.descartar(ctx, o.descartar).model_dump(mode="json")
        except ErrorDeServicio as e:
            return _comun.queja(str(e))
        if o.json:
            return _comun.escribir_json(r)
        print(f"«{r['para']}»: descartado, no se entregó · id {r['id']}")
        if r.get("aviso"):
            print(f"  a «{r['de']}» le llegó un aviso (no lo despierta) · id {r['aviso']}")
        elif r.get("sin_aviso"):
            print(f"  el aviso a «{r['de']}» no salió ({r['sin_aviso']}): no sabe que no se entregó", file=sys.stderr)
        return 0
    if not o.para:
        return _comun.queja("¿para quién? telar mensaje <hilo> \"texto\"")
    if o.modo == "consulta":
        return _consulta(ctx, o)
    texto = sys.stdin.read() if o.texto == ["-"] else " ".join(o.texto)
    if not texto.strip():
        return _comun.queja("¿qué le digo? telar mensaje <hilo> \"texto\" (o «-» para la entrada)")
    from telar.servicios import ErrorDeServicio
    from telar.servicios import mensajes as servicio

    try:
        r = servicio.enviar(ctx, o.para, texto, tipo=o.tipo, de=o.de, modo=o.modo, plazo=o.plazo).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    if r.get("estado") == "retenido":
        print(f"«{r['para']}»: RETENIDO, no se entregó ({r['motivo']}). Cuéntale a tu persona qué querías decir "
              f"y a quién; ella lo suelta con: telar mensaje --soltar {r['id']} (o lo descarta, y te llega un aviso)",
              file=sys.stderr)
        return 3
    como = {"aviso": " (un aviso: no lo despierta)"}.get(o.modo, "")
    # la casilla en que quedó es la de `r['para']`, el hilo o agente que se resolvió: si se escribió de otra forma
    # (`Telar@laptop`, `@144`, «telar»), se dice a quién llegó
    a_quien = f"«{r['para']}»" + (f" ({o.para.strip()})" if o.para.strip() != r["para"] else "")
    print(f"{a_quien}: en su casilla{como}" + (" (ya estaba: no se duplicó)" if r.get("duplicado") else "")
          + f" · id {r['id']}")
    if r.get("despertado"):
        print(f"  estaba {r['despertado']}: lo retomé con su conversación, y lo lee ahora")
    elif r.get("en_cola"):
        print(f"  {r['en_cola']}: espera en el bus y le llega cuando vuelva"
              + (" (allá no estaba abierto: retomarlo quedó en cola para entonces)" if r.get("cola") else ""))
    elif r.get("sin_despertar"):
        print(f"  no está abierto y no pude retomarlo ({r['sin_despertar']}): le llega cuando lo retomes", file=sys.stderr)
    if r.get("encargo"):
        print(f"  {r['direccion']}: en qué va, con telar objeto {r['direccion']}")
    return 0


#: lo que dice `--modo consulta`, retirado (lo mismo hacen `telar ficha` y `telar hilo leer`), cada vez que se usa
AVISO_CONSULTA = ("telar: `--modo consulta` se retira: en qué anda un hilo lo dicen `telar ficha <hilo>` y "
                  "`telar hilo leer <hilo>`")


def _consulta(ctx, o) -> int:
    """`--modo consulta`, retirado: la ficha del hilo y lo último de su conversación, sin mandarle nada. Hace lo
    mismo que antes, con una línea por stderr que dice qué usar en su lugar."""
    from telar.servicios import ErrorDeServicio
    from telar.servicios import mensajes as servicio

    print(AVISO_CONSULTA, file=sys.stderr)
    if o.texto:
        return _comun.queja("una consulta no lleva texto: no se le manda nada, se lee su estado (sin --modo consulta, "
                            "se le escribe)")
    try:
        r = servicio.consultar(ctx, o.para).model_dump(mode="json")
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r)
    obj = r["objeto"]
    campos = obj.get("campos") or {}
    donde = " · ".join(x for x in (campos.get("relativa", ""), obj.get("maquina", "")) if x)
    print(f"«{obj['titulo']}»: {obj.get('estado') or 'sin atención'}" + _comun.tenue(f"  {donde}" if donde else ""))
    turnos = (r.get("ultimos") or {}).get("turnos") or []
    for turno in turnos:
        for paso in turno:
            print(f"  {paso.get('quien', '')}: " + " ".join(str(paso.get("texto", "")).split())[:200])
    if r.get("problema"):
        print(_comun.tenue(f"  (su conversación: {r['problema']})"))
    return 0


def _hilo_propio(ctx) -> str:
    """El hilo de quien escribe (`$TELAR_HILO`), con su nombre de hoy si se renombró mientras corría."""
    hilo = os.environ.get("TELAR_HILO", "").strip()
    if not hilo:
        return ""
    from telar import estado as mod_estado

    try:
        return mod_estado.abrir(ctx.config).nombre_actual(hilo)
    except Exception:  # noqa: BLE001 - sin estado legible, el nombre que se heredó
        return hilo


def remitente(ctx, de: str = "") -> str:
    return de or _hilo_propio(ctx) or f"{mod_bus.persona(ctx.config)}@{mod_bus.maquina(ctx.config)}"


_ID_DE_HILO = re.compile(r"^@?\d+$")


def _por_nombre(ctx, para: str) -> str:
    """El nombre del hilo si `para` es un id (`@144`, como lo muestran `telar hilos` y el dashboard).

    La casilla se llama como el hilo, no como su id: un `@144` tal cual iba a una casilla «144» que
    nadie lee, y el mensaje salía como entregado. Un id que no es de un hilo de esta máquina se
    rechaza: el hilo de otra máquina se nombra, no se numera."""
    if para.strip().startswith("hilo:"):
        return _por_direccion(ctx, para.strip())
    if _con_maquina(para):
        return _por_arroba(ctx, para.strip())
    if not _ID_DE_HILO.match(para.strip()):
        return para
    ref = "@" + para.strip().lstrip("@")
    tel = _comun.tejer(ctx, con_ficha=False)
    hilo = next((h for h in tel.hilos if h.id == ref), None)
    if hilo is None:
        raise mod_bus.ErrorDeBus(f"no hay ningún hilo con id {ref} en esta máquina: escribe su nombre")
    return hilo.nombre


#: `nombre@máquina`, como en la dirección `hilo:nombre@máquina` (telar.objetos.leer): el hilo nombre en esa máquina
_CON_MAQUINA = re.compile(r"^(?P<nombre>[^@\s][^@]*?)@(?P<maquina>[a-z0-9][\w-]*)$")


def _con_maquina(para: str):
    """El match de `nombre@máquina` (sin `hilo:`), o None. `Telar@laptop` es el hilo «Telar» en laptop."""
    return _CON_MAQUINA.match(para.strip())


def _por_arroba(ctx, para: str) -> str:
    """`nombre@máquina` sin `hilo:`: lo mismo que `hilo:nombre@máquina`, salvo que un agente se nombra igual con su
    máquina (`Gerencia@telar`: su casilla es la del agente, viva donde viva).

    Antes iba tal cual a la casilla «nombre@máquina» (`telar-laptop`), que no es de nadie, y salía como entregado."""
    from telar import agentes as mod_agentes

    m = _con_maquina(para)
    nombre = m.group("nombre").strip()
    try:
        agente = next((a for a in mod_agentes.descubrir(ctx.config) if nombre in (a.clave, a.nombre)), None)
    except Exception:  # noqa: BLE001 - sin poder leer los agentes, como un hilo
        agente = None
    if agente is not None:
        return agente.nombre
    return _por_direccion(ctx, f"hilo:{nombre}@{m.group('maquina')}")


def _parecidos(nombre: str, nombres, n: int = 4) -> list[str]:
    """Los nombres que se parecen a `nombre` (para sugerirlos): los que lo contienen o empiezan igual, sin mirar
    mayúsculas ni tildes, y los que difflib encuentra cerca."""
    import difflib

    from telar import casilla

    nombres = sorted({x for x in nombres if x})
    llano = casilla.nombre_de_carpeta(nombre)
    por_forma = {casilla.nombre_de_carpeta(x): x for x in nombres}
    salida = [x for x in nombres if llano and (casilla.nombre_de_carpeta(x) in llano or
                                                llano in casilla.nombre_de_carpeta(x))]
    salida += [por_forma[x] for x in difflib.get_close_matches(llano, list(por_forma), n=n, cutoff=0.6)]
    vistos, unicos = set(), []
    for x in salida:
        if x not in vistos:
            vistos.add(x)
            unicos.append(x)
    return unicos[:n]


class NoHayHilo(mod_bus.ErrorDeBus):
    """La máquina de `hilo:X@máquina` no tiene un hilo X: un 404, no una falla del bus."""


class Ambiguo(mod_bus.ErrorDeBus):
    """El nombre se parece a varios hilos vivos y no es exactamente el de ninguno: un 409, no una falla del bus."""


def _exacto(ctx, para: str) -> str:
    """El nombre exacto del hilo al que se le escribe (cada uno tiene su casilla: telar.casilla.ficha). Por id o por
    dirección (`hilo:faro`) no se pasa por aquí: eso ya es exacto.

    Entre los hilos cuyo nombre solo difiere en mayúsculas, tildes o espacios del que se dijo:
    - si uno solo no está archivado, ese, se escriba como se escriba («telar» → «Telar» aunque haya un «telar»
      archivado): antes compartían casilla y le llegaba al vivo, y eso sigue igual. Al archivado se llega por su
      dirección (`hilo:telar`) o su id;
    - si son varios, el de nombre exacto; si ninguno lo es, Ambiguo, con sus nombres (cada uno tiene su casilla, y
      elegir uno a ciegas le entregaría a otro lo que no es suyo);
    - si todos están archivados, el de nombre exacto, o el único.
    También la ficha apartada de uno (`faro_3f9a1c`, la de un correo `persona+faro_3f9a1c`). Un nombre que no se
    parece a ninguno, tal cual."""
    from telar import casilla

    try:
        conocidos = _comun.nombres_conocidos(ctx, preguntar_al_bus=False)
    except Exception:  # noqa: BLE001 - sin poder saber qué hilos hay, el nombre tal cual, como siempre
        return para
    if casilla.es_apartada(para):
        return next((n for n in conocidos if casilla.apartada(n) == para), para)
    grupo = sorted(n for n in conocidos if casilla.mismo_nombre(n, para) or casilla.chocan(n, para))
    if not grupo:
        return para
    exacto = para if para in conocidos else next((n for n in grupo if casilla.mismo_nombre(n, para)), "")
    vivos = [n for n in grupo if not conocidos[n].archivado]
    if len(vivos) == 1:
        return vivos[0]
    candidatos = vivos or grupo
    if exacto in candidatos or len(candidatos) == 1:
        return exacto if exacto in candidatos else candidatos[0]
    cuales = " o ".join(f"«{n}» ({conocidos[n].donde})" for n in candidatos[:4])
    raise Ambiguo(f"«{para}» puede ser {cuales}: son hilos distintos, cada uno con su casilla. Escríbele por su "
                  f"nombre exacto o por su id (telar hilos)")


class NadieLee(NoHayHilo):
    """El nombre no es de ningún hilo ni agente de esta persona, en ninguna de sus máquinas: su casilla no la leería
    nadie. Un 404, como NoHayHilo."""


def _alguien_lee(ctx, nombre: str) -> None:
    """NadieLee si `nombre` no es de un hilo (vivo, dormido o archivado, aquí o en otra máquina) ni de un agente: lo
    que se le mandara quedaría en una casilla huérfana y saldría como entregado. Los nombres que conoce esta máquina
    (`_comun.nombres_conocidos`) y, si no está entre ellos, el estado del bus (un hilo recién abierto en otra máquina).
    Si no se puede saber qué hilos hay, no se rechaza: como antes."""
    from telar import casilla

    if casilla.es_apartada(nombre):
        return
    try:
        conocidos = _comun.nombres_conocidos(ctx, preguntar_al_bus=True)
    except Exception:  # noqa: BLE001 - sin saber qué hilos hay, como siempre
        return
    if nombre in conocidos or any(casilla.mismo_nombre(n, nombre) for n in conocidos):
        return
    if mod_bus.hay_bus(ctx.config) and mod_bus.estado_de(ctx.config, nombre):
        return
    if nombre == _persona(ctx):
        raise NadieLee(f"«{nombre}» es tu persona, no un hilo: no tiene casilla. Lo que es para ella, díselo en tu "
                       "respuesta")
    parecidos = _parecidos(nombre, conocidos)
    cuales = (" ¿Quisiste decir " + " o ".join(f"«{n}» ({conocidos[n].donde})" for n in parecidos) + "?"
              if parecidos else " Los hilos de cada máquina: telar hilos --red; los agentes: telar agentes.")
    raise NadieLee(f"«{nombre}» no es un hilo ni un agente tuyo, en ninguna de tus máquinas: no le mandé nada, "
                   f"porque su casilla no la leería nadie.{cuales}")


def _por_direccion(ctx, para: str) -> str:
    """El nombre del hilo de una dirección (`hilo:Faro`, `hilo:Faro@servidor`). Con `@máquina`, esa máquina
    tiene que tener un hilo así (aquí, o según la foto que publicó en el bus): la casilla es del nombre, y un
    mensaje para un hilo que allá no existe quedaría en una casilla que nadie lee, dado por entregado."""
    from telar import objetos
    from telar.servicios import ErrorDeServicio

    try:
        d = objetos.leer(para)
    except ErrorDeServicio as e:
        raise mod_bus.ErrorDeBus(str(e)) from None
    if not d.maquina or not mod_bus.hay_bus(ctx.config):
        return d.id
    if d.maquina == mod_bus.maquina(ctx.config):
        tel = _comun.tejer(ctx, con_ficha=False)
        alla = [h.nombre for h in tel.hilos if not h.remoto]
        if d.id not in alla:
            raise NoHayHilo(f"{d.maquina} (esta máquina) no tiene un hilo «{d.id}»" + _sugerir(ctx, d, alla))
    elif objetos._hilo_remoto(ctx, d.id, d.maquina) is None:
        from telar import espejo

        fotos = [f for f in espejo.leer_todos(ctx.config) if f.get("nombre")]
        foto = next((f for f in fotos if f["nombre"] == d.maquina), None)
        if foto is None:
            maquinas = sorted({mod_bus.maquina(ctx.config), *(f["nombre"] for f in fotos)})
            raise NoHayHilo(f"no conozco la máquina «{d.maquina}» (las tuyas: {', '.join(maquinas)})"
                            + _sugerir(ctx, d, []))
        alla = [h.get("nombre", "") for h in foto.get("hilos", []) if not h.get("remoto")]
        raise NoHayHilo(f"{d.maquina} no tiene un hilo «{d.id}» (según lo último que publicó en el bus)"
                        + _sugerir(ctx, d, alla))
    return d.id


def _persona(ctx) -> str:
    """La persona del bus, o "" si no se sabe."""
    try:
        return mod_bus.persona(ctx.config)
    except Exception:  # noqa: BLE001 - una configuración a medias
        return ""


def _sugerir(ctx, d, alla: list[str]) -> str:
    """Lo que se le dice a quien nombró un hilo que no está en esa máquina: si es la persona escribiendo desde un
    terminal (`nico@laptop`, el remitente de lo que ella manda), que no tiene casilla; si no, los parecidos de allá."""
    if d.id == _persona(ctx):
        return (f". «{d.id}@{d.maquina}» es tu persona escribiendo desde un terminal: no tiene casilla. Lo que es para "
                "ella, díselo en tu respuesta")
    try:
        conocido = _comun.nombres_conocidos(ctx, preguntar_al_bus=False).get(d.id)
    except Exception:  # noqa: BLE001 - sin saber dónde está, los parecidos de allá
        conocido = None
    if conocido is not None:
        return f". «{d.id}» está {conocido.donde}: escríbele por su nombre solo, sin máquina"
    parecidos = _parecidos(d.id, alla)
    if parecidos:
        return ". ¿Quisiste decir " + " o ".join(f"«{x}@{d.maquina}»" for x in parecidos) + "?"
    return ". Los hilos de cada máquina: telar hilos --red"


#: los modos de `--modo`: los que viajan (telar.casilla.MODOS)
MODOS = ("aviso", "pedido", "encargo")

#: los que se retiraron y se aceptan todavía, sin ofrecerlos: la consulta (lo mismo que `telar ficha` y `telar hilo
#: leer`)
RETIRADOS = ("consulta",)


class _Modos(tuple):
    """Los modos que ofrece `--modo` (la ayuda y el error de uno que no existe los recorren) y, además, los
    retirados, que todavía se aceptan."""

    def __contains__(self, modo) -> bool:
        return tuple.__contains__(self, modo) or modo in RETIRADOS


def enviar(ctx, para: str, texto: str, *, tipo: str = "mensaje", de: str = "", modo: str = "pedido",
           plazo: str = "") -> dict:
    """Publica para `para` (un agente por su carpeta o nombre, o un hilo por su nombre).

    Si lo manda un hilo (`TELAR_HILO`), lleva un salto más que la cadena en la que está ese hilo, y se
    retiene (queda en el registro, sin entregar) si pasa el tope o si el hilo ya mandó demasiados
    esta hora. Lo que manda la persona desde un terminal no tiene freno.

    `modo` (telar.casilla): un `encargo` lleva el id de su Encargo (que se crea al llegar), su `plazo` y el
    hilo que lo pidió (`responder_a`, al que se le avisa al cerrarlo); aquí queda la nota de a quién se mandó
    (telar.encargo), y lo devuelto trae `encargo` y su `direccion`. ValueError si el modo o el plazo no sirven."""
    from telar import agentes as mod_agentes
    from telar import casilla
    from telar import encargo as mod_encargo

    if modo not in casilla.MODOS:
        raise ValueError(f"el modo «{modo}» no se manda: {', '.join(casilla.MODOS)}")
    if plazo and modo != "encargo":
        raise ValueError("el plazo es de un encargo: --modo encargo --plazo …")
    plazo = mod_encargo.plazo_valido(plazo)
    # por id (`@144`) o por dirección (`hilo:Faro`) ya es un hilo exacto; un nombre suelto se busca (`_exacto`)
    # y `nombre@máquina` (`Telar@laptop`), como `hilo:nombre@máquina`: el hilo de esa máquina, que tiene que estar allá
    explicito = para.strip().startswith("hilo:") or bool(_ID_DE_HILO.match(para.strip())) or bool(_con_maquina(para))
    # por id o con su máquina ya se miró que el hilo esté; lo demás se mira abajo (`_alguien_lee`)
    visto = bool(_ID_DE_HILO.match(para.strip()) or _con_maquina(para) or
                 (para.strip().startswith("hilo:") and "@" in para.strip()[5:]))
    para = _por_nombre(ctx, para)
    agentes = mod_agentes.descubrir(ctx.config)
    agente = next((a for a in agentes if para in (a.clave, a.nombre)), None)
    # el nombre exacto: dos hilos que solo difieren en mayúsculas, tildes o espacios tienen casillas distintas
    nombre = agente.nombre if agente is not None else para if explicito else _exacto(ctx, para)
    agente = agente or next((a for a in agentes if a.nombre == nombre), None)
    if agente is None and not visto:
        # a un nombre que no es de ningún hilo ni agente, nadie le leería la casilla: se rechaza, con los parecidos
        _alguien_lee(ctx, nombre)
    hilo = _hilo_propio(ctx)
    saltos, retener, familia = 0, "", None
    if hilo:
        # entre un padre y su hijo, su cuenta propia (casilla.cadena_familia): no suma a la cadena de ninguno
        par = familia_de(ctx, hilo, nombre)
        if par is not None:
            cabeza = cabeza_del_hijo(ctx, par[1])
            familia = {"padre": par[0], "hijo": par[1],
                       "saltos": casilla.cadena_familia(ctx.config, *par, de=hilo, cabeza=cabeza)}
            if familia["saltos"] > casilla.TOPE_SALTOS:
                retener = (f"{familia['saltos']} mensajes seguidos entre «{par[0]}» y su hijo «{par[1]}» sin un commit en "
                           f"la carpeta del hijo ni que hablara la persona (tope {casilla.TOPE_SALTOS})")
        else:
            saltos = casilla.cadena(ctx.config, hilo) + 1
            if saltos > casilla.TOPE_SALTOS:
                retener = f"cadena de {saltos} mensajes entre hilos sin que hablara la persona (tope {casilla.TOPE_SALTOS})"
        if not retener and _enviados_esta_hora(ctx.config, hilo) >= TOPE_HORA:
            retener = f"«{hilo}» ya mandó {TOPE_HORA} mensajes esta hora"
    # el modo y lo suyo, solo cuando no es un pedido: así un pedido se publica exactamente como siempre
    con_modo = {}
    eid = ""
    if modo == "encargo":
        eid = mod_encargo.nuevo_id()
        con_modo = {"modo": modo, "extra": {"encargo": eid, "plazo": plazo, "responder_a": hilo}}
    elif modo != "pedido":
        con_modo = {"modo": modo}
    if familia is not None:
        con_modo["extra"] = {**con_modo.get("extra", {}), "familia": familia}
    r = mod_bus.enviar(ctx.config, nombre, texto.strip(), de=remitente(ctx, de), tipo=tipo, saltos=saltos, retener=retener,
                       **con_modo)
    if hilo and not retener:
        _anotar_envio(ctx.config, hilo)
        if familia is not None:
            casilla.anotar_familia(ctx.config, familia["padre"], familia["hijo"], familia["saltos"], hilo, cabeza)
    # un hilo dormido o archivado no recoge su casilla: lo que le llega esperaría hasta que alguien lo retome. Un
    # mensaje que pide algo (no un aviso) lo despierta: se retoma, con su conversación, en la máquina donde vive. Un
    # agente no: su nodo lo abre al llegarle algo (o espera, si así lo declara)
    if agente is None and modo != "aviso" and r.get("estado") != "retenido":
        r = {**r, **despertar(ctx, nombre)}
    if eid:
        # la máquina donde vive el hilo ahora, que es donde se creará el encargo: si el hilo se muda después o su
        # estado se borra del bus, la nota sigue sabiendo dónde buscarlo
        donde = mod_bus.maquina_de(ctx.config, nombre) if mod_bus.hay_bus(ctx.config) else ""
        try:
            mod_encargo.anotar_enviado(ctx.config, eid, para=nombre, maquina=donde, texto=texto.strip(), plazo=plazo,
                                       de=remitente(ctx, de),
                                       retenido=str(r.get("motivo") or "retenido") if r.get("estado") == "retenido" else "")
        except OSError:
            pass  # sin la nota, se lo busca en la máquina donde vive su hilo
        r = {**r, "encargo": eid, "direccion": f"encargo:{eid}"}
    return r


def familia_de(ctx, hilo: str, otro: str) -> tuple[str, str] | None:
    """(padre, hijo) si `hilo` y `otro` son un padre y su hijo directo (en cualquier orden); None si no, o si no se
    puede leer el estado."""
    if not hilo or not otro or hilo == otro:
        return None
    from telar import estado as mod_estado

    try:
        est = mod_estado.abrir(ctx.config)
        if est.padre(otro) == hilo:
            return hilo, otro
        if est.padre(hilo) == otro:
            return otro, hilo
    except Exception:  # noqa: BLE001 - sin estado legible, la cadena de siempre
        return None
    return None


def cabeza_del_hijo(ctx, hijo: str) -> str:
    """El commit en que está la carpeta donde trabaja `hijo` (su worktree, si tiene rama propia; si no, su carpeta
    vinculada): con uno nuevo entre dos mensajes, la conversación con su padre vuelve a empezar. "" si no se sabe."""
    from telar import estado as mod_estado
    from telar.git import _git

    try:
        est = mod_estado.abrir(ctx.config)
        lugar = est.ramas().get(hijo)
        ruta = (lugar or {}).get("ruta") or est.vinculos().get(hijo, "")
    except Exception:  # noqa: BLE001 - sin estado legible, no se sabe
        return ""
    if not ruta:
        return ""
    carpeta = Path(ruta) if Path(ruta).is_absolute() else Path(ctx.config.raiz) / ruta
    if not carpeta.is_dir():
        return ""
    r = _git(carpeta, "rev-parse", "HEAD", timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


def despertar(ctx, hilo: str) -> dict:
    """Si `hilo` no está vivo (dormido o archivado), retomarlo donde vive para que lea lo que le llegó. Devuelve
    {"despertado": "archivado"|"dormido"} si lo retomó, {"sin_despertar": motivo} si no pudo, {} si estaba vivo o el
    bus no lo conoce. Si vive en una máquina fuera de línea (telar.alcance), el mensaje espera en su casilla del bus y
    lo recoge al volver: {"en_cola": "laptop fuera de línea desde 14:02", "desde"}, y si allá no estaba abierto, su
    retomarlo queda en cola para entonces (`cola: true`), sin esperar el plazo del bus."""
    if not mod_bus.hay_bus(ctx.config):
        return {}
    e = mod_bus.estado_de(ctx.config, hilo)
    if not e or e.get("residente"):
        return {}
    maquina = str(e.get("maquina") or "")
    alla = maquina and maquina != mod_bus.maquina(ctx.config)
    if alla:
        from telar import alcance

        a = alcance.de(ctx.config, maquina)
        if a.fuera:
            fuera = {"en_cola": a.frase(), "desde": a.desde_iso(), "maquina": maquina}
            if e.get("vivo"):
                # abierto allá cuando se fue: al volver, su nodo recoge la casilla y se lo entrega (o lo despierta)
                return fuera
            alcance.encolar(ctx.config, maquina, hilo, por="un mensaje", por_hilo=_hilo_propio(ctx))
            return {**fuera, "cola": True}
    if e.get("vivo"):
        return {}
    como = "archivado" if e.get("archivado") else "dormido"
    if not alla:
        r = despertar_aqui(ctx, hilo)
    else:
        r = mod_bus.pedir(ctx.config, maquina, "hilo-despertar", {"hilo": hilo}, espera=60)
        if r.get("fuera_de_linea"):
            # se fue justo ahora (su foto todavía no envejecía): como arriba
            from telar import alcance

            alcance.encolar(ctx.config, maquina, hilo, por="un mensaje", por_hilo=_hilo_propio(ctx))
            return {"en_cola": alcance.de(ctx.config, maquina).frase(), "desde": r.get("desde", ""), "maquina": maquina,
                    "cola": True}
    return {"despertado": como} if r.get("ok") else {"sin_despertar": str(r.get("error") or "no respondió")}


def despertar_aqui(ctx, hilo: str) -> dict:
    """Retomar aquí un hilo dormido o archivado al que le llegó un mensaje (`telar hilo retomar`)."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from telar.ordenes import hilo as orden_hilo

    salida, errores = io.StringIO(), io.StringIO()
    with redirect_stdout(salida), redirect_stderr(errores):
        codigo = orden_hilo.main(["retomar", "--hilo", hilo], ctx)
    if codigo != 0:
        lineas = (errores.getvalue() or salida.getvalue()).strip().splitlines()
        return {"ok": False, "error": lineas[-1] if lineas else "no se pudo"}
    return {"ok": True}


#: cuántos mensajes del registro se miran para encontrar los retenidos: los mismos para listarlos (`--retenidos`, la
#: bandeja de `telar esperas`) que para soltarlos (`--soltar`), para que no se vea uno que no se puede soltar ni falte
#: uno que sí
VENTANA_RETENIDOS = 500


def retenidos(lista: list[dict]) -> list[dict]:
    """De un registro, los retenidos que todavía nadie soltó ni descartó."""
    resueltos = {m["id"] for m in lista if m.get("estado") in ("enviado", "descartado")}
    return [m for m in lista if m.get("estado") == "retenido" and m["id"] not in resueltos]


def _retenido(ctx, mid: str) -> dict:
    """El mensaje retenido `mid`, entre los mismos que lista `--retenidos`; ErrorDeBus si no está (o ya se resolvió)."""
    m = next((x for x in retenidos(mod_bus.registro(ctx.config, VENTANA_RETENIDOS)) if x["id"] == mid), None)
    if m is None:
        raise mod_bus.ErrorDeBus(f"no hay un mensaje retenido con id {mid} (¿ya se soltó o se descartó?)")
    return m


def soltar(ctx, mid: str) -> dict:
    """Manda un mensaje retenido, con su mismo id y la cadena en cero: lo decidió la persona."""
    m = _retenido(ctx, mid)
    # con su modo y lo suyo (el id de su encargo, su plazo): el encargo se crea cuando llega
    con_modo = {}
    if m.get("modo") and m["modo"] != "pedido":
        con_modo = {"modo": m["modo"], "extra": {k: m[k] for k in ("encargo", "plazo", "responder_a") if m.get(k)}}
    r = mod_bus.enviar(ctx.config, m["para"], m["texto"], de=m["de"], tipo=m.get("tipo") or "mensaje", mid=m["id"],
                       **con_modo)
    f = m.get("familia")
    if isinstance(f, dict) and f.get("padre") and f.get("hijo"):
        # entre un padre y su hijo: lo soltó la persona, y la conversación de los dos vuelve a empezar
        from telar import casilla

        casilla.anotar_familia(ctx.config, f["padre"], f["hijo"], 0, str(m.get("de") or ""))
    if m.get("encargo"):
        from telar import encargo as mod_encargo

        try:
            mod_encargo.soltado(ctx.config, str(m["encargo"]))
        except (OSError, mod_encargo.ErrorDeEncargo):
            pass  # la nota es de la máquina de quien lo mandó: si no está aquí, allá seguirá diciendo retenido
    return r


def descartar(ctx, mid: str, quien: str = "") -> dict:
    """Que un mensaje retenido no salga nunca: lo decidió la persona. No se borra: queda en el registro otra copia,
    `descartado`, con quién (`quien`; si no, quien corre esto: su hilo, o la persona y su máquina) y cuándo, y deja de
    esperar en «te esperan». A quien lo mandó le llega un aviso que no lo despierta, para que no crea que llegó; si es
    un encargo, su nota dice que se descartó. Devuelve esa copia, con `aviso` (el id del aviso) o `sin_aviso` (por qué
    no salió: lo descartado queda descartado igual)."""
    m = _retenido(ctx, mid)
    copia = {**m, "estado": "descartado", "descartado_por": quien or remitente(ctx),
             "descartado": datetime.now().astimezone().isoformat(timespec="seconds")}
    mod_bus.anotar(ctx.config, copia)
    if m.get("encargo"):
        from telar import encargo as mod_encargo

        try:
            mod_encargo.descartado(ctx.config, str(m["encargo"]), copia["descartado_por"])
        except (OSError, mod_encargo.ErrorDeEncargo):
            pass  # la nota es de la máquina de quien lo mandó: si no está aquí, allá seguirá diciendo retenido
    r = dict(copia)
    de = str(m.get("de") or "")
    if de:
        # de telar y sin saltos: no corta la cadena de quien lo mandó (el freno sigue donde estaba) ni suma a ella
        try:
            r["aviso"] = mod_bus.enviar(ctx.config, de, aviso_descartado(ctx.config, m), de="telar", modo="aviso")["id"]
        except mod_bus.ErrorDeBus as e:
            r["sin_aviso"] = str(e)
    return r


def aviso_descartado(config, m: dict) -> str:
    """Lo que le llega a quien mandó un mensaje que la persona descartó: a quién iba, su id y que no se entregó, y el
    comienzo de lo que decía, para que lo reconozca."""
    p = mod_bus.persona(config)
    quien = p[:1].upper() + p[1:] if p else "tu persona"
    texto = " ".join(str(m.get("texto", "")).split())
    texto = texto if len(texto) <= 200 else texto[:199] + "…"
    return (f"tu mensaje a «{m.get('para') or '?'}» ({m['id']}) no se entregó: {quien} lo descartó."
            + (f"\nDecía: {texto}" if texto else ""))


def _envios(config) -> Path:
    return Path(config.estado) / "casillas" / "enviados.log"


def _enviados_esta_hora(config, hilo: str) -> int:
    hace = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    try:
        lineas = _envios(config).read_text(encoding="utf-8").splitlines()[-500:]
    except OSError:
        return 0
    n = 0
    for linea in lineas:
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        n += d.get("hilo") == hilo and str(d.get("hora", "")) >= hace
    return n


def _anotar_envio(config, hilo: str) -> None:
    try:
        _envios(config).parent.mkdir(parents=True, exist_ok=True)
        with open(_envios(config), "a", encoding="utf-8") as f:
            f.write(json.dumps({"hilo": hilo, "hora": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
    except OSError:
        pass
