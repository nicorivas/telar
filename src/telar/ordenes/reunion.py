"""`telar reunion` — preparar una reunión: un hilo nuevo con el agente ya trabajando en ella.

    telar reunion "Coordinación interna ANASAC" 12:00
    telar reunion "Comité" 15:30 --enlace https://meet.google.com/…
    telar reunion "Comité" 15:30 --donde     solo dice qué haría, sin abrir nada

Abre un tab «◷ HH:MM título» con el agente configurado en `[agente]`, y le dice lo que
diga `[agente] reunion`; de fábrica, la skill de flow:

    /preparar-reunion {titulo} (hoy {hora}) · proyecto: {proyecto}

El proyecto se busca entre las unidades del perfil: la que comparta palabras con el título
(«ANASAC» encuentra la carpeta de Anasac). Si lo encuentra, el hilo queda vinculado a esa
carpeta y su ficha es la del proyecto; si no, la cola «· proyecto:» se quita del mensaje.

Si el tab de esa reunión ya existe, se va a él en vez de abrir otro: dos Claude
preparando la misma reunión es trabajo repetido.

Con un agente que recibe lo sin proyecto (`[agentes] sin_proyecto`), no se abre un tab: se le
encarga la preparación o la minuta a ese agente y se va a su hilo. `--hilo-nuevo` abre el tab igual.

Qué se le dice depende del evento. Si ya empezó, es su minuta (`[agente] minuta`, de
fábrica `/minuta`) en un tab «✎ HH:MM …»; si no, la preparación. Y una regla
`[agenda.<clave>]` cuyo `si` calce con el título cambia cualquiera de los dos: una clase,
un taller, lo que tenga su propia skill. `--antes` y `--despues` fuerzan el momento.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from pathlib import Path

from telar import estado as mod_estado
from telar import lectura
from telar.agente import ErrorDeAgente
from telar.agente import lanzar
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Preparar una reunión: un hilo con el agente ya trabajando en ella."

#: la marca con que se reconoce el tab de una reunión, igual que en flow; y el de su minuta.
MARCA = "◷"
MARCA_DESPUES = "✎"

#: palabras de título de reunión que no dicen de qué proyecto se trata.
VACIAS = frozenset("""
    reunion coordinacion interna interno semanal sesion daily llamada revision seguimiento
    equipo taller actividad recordatorio kickoff presentacion cierre inicio proyecto proyectos
    internos reuniones importante vamos trabajo con para
    sobre entre desde hasta como the and with meeting sync weekly call
""".split())


def palabras(texto: str) -> set[str]:
    """Las palabras con peso de un texto: sin tildes, en minúscula, de cuatro letras o más."""
    plano = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()
    return {p for p in re.split(r"[^a-z0-9]+", plano) if len(p) >= 4 and p not in VACIAS}


def proyecto_para(titulo: str, unidades: list[str], vivos: set[str] = frozenset()) -> str:
    """La unidad del perfil de la que parece tratar la reunión, o "" si ninguna.

    Cuenta las palabras del título que aparecen en el nombre de la carpeta, pesando cada
    una por lo rara que es: «anasac» en cinco carpetas vale menos que «valgesta» en una.
    Entre empates gana la que tiene un hilo vivo y después la que va primero en `unidades`,
    que viene en el orden del perfil.
    """
    buscadas = palabras(titulo)
    if not buscadas:
        return ""
    de_cada = {u: palabras(Path(u).name.replace("-", " ").replace("_", " ")) for u in unidades}
    frecuencia: dict[str, int] = {}
    for ps in de_cada.values():
        for p in ps:
            frecuencia[p] = frecuencia.get(p, 0) + 1
    mejor, mejor_clave = "", None
    for i, u in enumerate(unidades):
        comunes = buscadas & de_cada[u]
        if not comunes:
            continue
        puntaje = sum(1 / frecuencia[p] for p in comunes)
        clave = (puntaje, Path(u).name in vivos, -i)
        if mejor_clave is None or clave > mejor_clave:
            mejor, mejor_clave = u, clave
    return mejor


def mensaje(plantilla: str, *, titulo: str, hora: str, fecha: str = "", enlace: str = "",
            proyecto: str = "") -> str:
    """La plantilla de `[agente] reunion`, llena. Un marcador desconocido queda tal cual."""
    valores = {"titulo": titulo, "hora": hora, "fecha": fecha, "enlace": enlace, "proyecto": proyecto}
    texto = re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), plantilla)
    if not proyecto:
        texto = re.sub(r"\s*·\s*proyecto:\s*$", "", texto)
    return texto.strip()


def empezo(fecha: str, hora: str, ahora: dt.datetime | None = None) -> bool:
    """Si el evento de `fecha` (AAAA-MM-DD, "" es hoy) a esa `hora` ya empezó."""
    ahora = ahora or dt.datetime.now()
    try:
        dia = dt.date.fromisoformat(fecha) if fecha else ahora.date()
        h, m = (int(x) for x in hora.split(":"))
        return dt.datetime.combine(dia, dt.time(h, m)) <= ahora
    except ValueError:
        return False


def plantilla(config, titulo: str, despues: bool) -> tuple[str, str]:
    """Qué decirle al agente por este evento, y de dónde salió (la clave de la regla, o
    «reunion»/«minuta» si ninguna calzó)."""
    for regla in config.agenda:
        texto = regla.despues if despues else regla.antes
        if texto and re.search(regla.si, titulo, re.IGNORECASE):
            return texto, regla.clave
    return (config.agente.minuta, "minuta") if despues else (config.agente.reunion, "reunion")


def nombre_del_tab(titulo: str, hora: str, marca: str = MARCA) -> str:
    """«◷ HH:MM» y lo que distingue a la reunión: «Coordinación interna ANASAC» es «ANASAC».

    Cortar el título por largo dejaba justo la parte que se repite en todas las reuniones
    («Coordinación interna …») y se comía la que dice cuál es.
    """
    def plano(w: str) -> str:
        return unicodedata.normalize("NFD", w).encode("ascii", "ignore").decode().lower()

    utiles = [w for w in re.split(r"[^\w]+", titulo) if len(w) >= 3 and plano(w) not in VACIAS]
    corto = " ".join(utiles) or titulo
    if len(corto) > 24:
        corto = corto[:23] + "…"
    return f"{marca} {hora} {corto}"


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("reunion", AYUDA)
    p.add_argument("titulo", help="el título de la reunión, como está en el calendario")
    p.add_argument("hora", help="HH:MM")
    p.add_argument("--fecha", default="", help="AAAA-MM-DD, si no es hoy")
    p.add_argument("--enlace", default="", help="la videollamada, para el mensaje")
    p.add_argument("--donde", action="store_true", help="decir qué haría, sin abrir nada")
    momento = p.add_mutually_exclusive_group()
    momento.add_argument("--antes", action="store_true", help="prepararla aunque ya haya empezado")
    momento.add_argument("--despues", action="store_true", help="su minuta aunque no haya empezado")
    p.add_argument("--evento", default="", help="el id del evento en el calendario: va en el mensaje, para que el "
                   "agente le deje su nota (`telar evento nota`)")
    p.add_argument("--asistentes", default="", help="los invitados, separados por comas («Nombre <correo>»): "
                   "ayudan a saber de qué proyecto es")
    p.add_argument("--proyecto", default="", help="a quién va: la ruta de un proyecto, «gestion» (el agente de lo "
                   "sin proyecto) o «nuevo:Nombre». Se recuerda para la serie")
    p.add_argument("--preguntar", action="store_true", help="si no se puede deducir el proyecto, no hacer nada y "
                   "devolver los candidatos (para que el dashboard pregunte)")
    p.add_argument("--hilo-nuevo", dest="hilo_nuevo", action="store_true",
                   help="abrir un hilo propio aunque haya un agente que reciba lo sin proyecto")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    titulo, hora = o.titulo.strip(), o.hora.strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", hora):
        return _comun.queja(f"«{hora}» no es una hora HH:MM")
    if not ctx.config.agente.nombre:
        return _comun.queja(
            "no hay agente configurado: agrega [agente] nombre = \"claude-code\" a la configuración"
        )

    tel = _comun.tejer(ctx, con_ficha=False)
    unidades = list(lectura.indice(ctx.perfil, ctx.config.raiz)) if ctx.perfil else []
    from telar import reuniones
    from telar.ordenes import pendiente

    asistentes = [x.strip() for x in o.asistentes.split(",") if x.strip()]
    cands = reuniones.candidatos(Path(ctx.config.raiz), unidades, titulo, asistentes)
    recordado = reuniones.recordado(ctx.config, titulo)
    eleccion = o.proyecto.strip()
    if eleccion and eleccion != "gestion" and not eleccion.startswith("nuevo:") and eleccion not in unidades:
        return _comun.queja(f"«{eleccion}» no es un proyecto del perfil (telar proyectos), ni «gestion», ni «nuevo:Nombre»")
    destino = eleccion or recordado or reuniones.decidir(cands)
    general = None if o.hilo_nuevo else pendiente._agente_general(ctx)
    if not destino and o.preguntar and not o.hilo_nuevo:
        return _responder({"hecho": "preguntar", "candidatos": cands, "gestion": general.nombre if general else "",
                           "titulo": titulo, "hora": hora}, o)
    # sin deducción ni elección, lo de siempre: el agente general si hay, o un tab con la unidad parecida
    proyecto = destino if destino and destino != "gestion" and not destino.startswith("nuevo:") else (
        "" if destino else proyecto_para(titulo, unidades, set(tel.vivos)))
    despues = o.despues or (not o.antes and empezo(o.fecha, hora))
    molde, regla = plantilla(ctx.config, titulo, despues)
    texto = mensaje(molde, titulo=titulo, hora=hora, fecha=o.fecha or dt.date.today().isoformat(),
                    enlace=o.enlace, proyecto=proyecto)
    if o.evento.strip():
        # con el id del evento, el agente puede dejarle su nota y el dashboard la muestra en él
        texto += f" · evento: {o.evento.strip()}"
    nombre = nombre_del_tab(titulo, hora, MARCA_DESPUES if despues else MARCA)
    resultado = {"hilo": nombre, "proyecto": proyecto, "mensaje": texto, "hecho": "",
                 "momento": "despues" if despues else "antes", "regla": regla, "candidatos": cands,
                 "destino": destino, "recordado": bool(recordado and not eleccion)}
    if eleccion and not eleccion.startswith("nuevo:") and not o.donde:
        reuniones.recordar(ctx.config, titulo, eleccion)

    # un proyecto con su hilo: la reunión se trabaja ahí, donde está el contexto
    if destino and destino not in ("gestion",) and not destino.startswith("nuevo:") and not o.hilo_nuevo:
        fila = {"ref": f"reunion:{titulo[:30]}", "texto": titulo, "ruta": destino, "hilo": "", "url": "", "id": ""}
        resultado["hilo"] = pendiente._destino(tel, fila).nombre if pendiente._destino(tel, fila) else Path(destino).name
        if o.donde:
            resultado["hecho"] = "nada (--donde)"
            return _responder(resultado, o)
        return _al_proyecto(ctx, tel, fila, texto, resultado, o)

    if destino.startswith("nuevo:"):
        nuevo_nombre = destino[6:].strip()
        texto = (f"Proyecto nuevo «{nuevo_nombre}»: créalo con el estándar de su repositorio (el arquetipo de proyecto, "
                 f"su README y su lugar en el índice) y trabaja ahí lo que sigue. {texto}")
        resultado["mensaje"] = texto

    # el agente que recibe lo sin proyecto (`[agentes] sin_proyecto`, Gestión): se le encarga
    if general is not None and (destino in ("gestion", "") or destino.startswith("nuevo:")):
        resultado.update(hilo=general.nombre, agente=general.clave)
        if o.donde:
            resultado["hecho"] = "nada (--donde)"
            return _responder(resultado, o)
        codigo, r = pendiente.encargar_y_ir(ctx, general, texto)
        if codigo != 0:
            return codigo
        resultado["hecho"] = f"encargado a {general.nombre} ({r.get('estado', '')})"
        return _responder(resultado, o)

    if o.donde:
        resultado["hecho"] = "nada (--donde)"
        return _responder(resultado, o)
    if tel.mux is None or not tel.viva:
        return _comun.queja(tel.aviso or "la sesión no está viva: primero telar tejer")

    try:
        if nombre in tel.vivos:
            resultado["hecho"] = "ya estaba"
        else:
            carpeta_hilo = Path(ctx.config.raiz) / proyecto if proyecto else None
            agente = _agente(ctx)
            palabras, sid = agente.nuevo_con_id(texto)
            lanz = lanzar.Lanzamiento(
                comando=lanzar.envolver(palabras, nombre),
                carpeta=lanzar.carpeta(ctx.config, carpeta_hilo),
                nueva=sid,
            )
            tel.mux.crear_tab(nombre, ruta=lanz.carpeta, comando=lanz.comando, foco=True)
            if proyecto:
                mod_estado.abrir(ctx.config).vincular(nombre, proyecto)
            lanzar.anotar(ctx.config, nombre, lanz, tel.mux)
            resultado["hecho"] = "abierto"
        hilo = next((h for h in tel.mux.hilos() if h.nombre == nombre), None)
        if hilo is not None:
            tel.mux.ir(hilo.id)
    except (ErrorDeMux, ErrorDeAgente) as e:
        return _comun.queja(f"no pude abrir la reunión: {e}")
    return _responder(resultado, o)


def _al_proyecto(ctx, tel, fila: dict, texto: str, resultado: dict, o) -> int:
    """La reunión al hilo del proyecto: el que está vivo, el dormido que se retoma, el de otra máquina
    (por el bus) o uno nuevo vinculado a la carpeta."""
    from telar.ordenes import pendiente

    destino = pendiente._destino(tel, fila)
    if destino is None:
        alla = pendiente._destino_remoto(ctx, fila)
        if alla is not None:
            from telar import bus as mod_bus

            nombre, maquina = alla
            try:
                mod_bus.enviar(ctx.config, nombre, texto, de="el dashboard", tipo="persona")
            except mod_bus.ErrorDeBus as e:
                return _comun.queja(f"«{nombre}» vive en {maquina} y el bus no lo llevó: {e}")
            resultado.update(hilo=nombre, hecho=f"en la casilla de «{nombre}» ({maquina})")
            return _responder(resultado, o)
    if tel.mux is None or not tel.viva:
        return _comun.queja(tel.aviso or "la sesión no está viva: primero telar tejer")
    hilo, creado, problema = pendiente._llevar(ctx, tel, destino, fila, nuevo=False, primero=texto)
    if hilo is None:
        return _comun.queja(problema)
    try:
        tel.mux.ir(hilo.id)
        if not (creado and ctx.config.agente.nombre):
            tel.mux.escribir(hilo.id, texto, enviar=True)
    except ErrorDeMux as e:
        return _comun.queja(f"llegué al hilo pero no pude escribirle: {e}")
    resultado.update(hilo=hilo.nombre, hecho="abierto en su proyecto" if creado else "escrito en su proyecto")
    return _responder(resultado, o)


def _agente(ctx):
    from telar import agente as mod_agente

    return mod_agente.obtener(ctx.config.agente.nombre, ctx.config)


def _responder(r: dict, o) -> int:
    if o.json:
        return _comun.escribir_json(r)
    print(f"{r['hilo']} · {r['hecho']}")
    print(_comun.tenue(f"  {r['mensaje']}"))
    if r["proyecto"]:
        print(_comun.tenue(f"  proyecto: {r['proyecto']}"))
    return 0
