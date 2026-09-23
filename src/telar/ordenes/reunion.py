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
"""

from __future__ import annotations

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

#: la marca con que se reconoce el tab de una reunión, igual que en flow.
MARCA = "◷"

#: palabras de título de reunión que no dicen de qué proyecto se trata.
VACIAS = frozenset("""
    reunion coordinacion interna interno semanal sesion daily llamada revision seguimiento
    equipo taller actividad recordatorio kickoff presentacion cierre inicio proyecto con para
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


def nombre_del_tab(titulo: str, hora: str) -> str:
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
    return f"{MARCA} {hora} {corto}"


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("reunion", AYUDA)
    p.add_argument("titulo", help="el título de la reunión, como está en el calendario")
    p.add_argument("hora", help="HH:MM")
    p.add_argument("--fecha", default="", help="AAAA-MM-DD, si no es hoy")
    p.add_argument("--enlace", default="", help="la videollamada, para el mensaje")
    p.add_argument("--donde", action="store_true", help="decir qué haría, sin abrir nada")
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
    proyecto = proyecto_para(titulo, unidades, set(tel.vivos))
    texto = mensaje(ctx.config.agente.reunion, titulo=titulo, hora=hora, fecha=o.fecha,
                    enlace=o.enlace, proyecto=proyecto)
    nombre = nombre_del_tab(titulo, hora)
    resultado = {"hilo": nombre, "proyecto": proyecto, "mensaje": texto, "hecho": ""}

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
