"""`telar buscar` — buscar en todo junto: lo que espera, las tareas, las casillas, los hilos, los proyectos, los objetos
de los tipos de un módulo que los lista (los documentos de un grafo) y los bloques.

    telar buscar vitrina                    lo que calza, por fuente: su dirección (o su ref), su título y dónde vive
    telar buscar "foto feria" --json        docs/contratos.md, «telar buscar --json» (también GET /buscar)
    telar buscar vitrina --fuente tareas    solo en una fuente (se repite; un bloque, como bloque:correo; los objetos
                                            de un tipo de un módulo, como objeto:doc)
    telar buscar vitrina --mundo trabajo    solo lo de un mundo de [mundos] (se repite; sin-clasificar, lo que no calza)
    telar buscar vitrina --primero trabajo  lo de ese mundo (y lo sin clasificar) primero en cada fuente, antes del límite
    telar buscar vitrina --limite 0         todas las de cada fuente (por defecto, 50)
    telar buscar vitrina --tope 10          espera hasta 10 s a las fuentes lentas (por defecto, 1,5; sin serve, 5)

Se busca sin tildes ni mayúsculas y tienen que estar todas las palabras, en el título o en lo que lo acompaña. En cada
fuente va primero lo que lo tiene en el título, después lo vigente antes de lo que ya pasó, y lo más nuevo antes. Es
lo que usa Todo, el modo de la página para ver y buscar todo. Solo lee: cada cosa se abre con `telar objeto <dirección>`.

No tarda más que el tope: la fuente que no llega (un bloque que corre un comando, las tareas de otra máquina) sale con
lo que se leyó de ella antes o se omite, y lo dice. Si `telar serve` corre en esta máquina, se le pregunta a él, que
guarda lo leído (el índice de la página): así sale todo, y al tiro. Sin él, o con `--aqui`, se busca en esta orden, que
lee todo de cero y espera hasta 5 s.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from telar import salida
from telar.ordenes import _comun
from telar.servicios import ErrorDeServicio

#: el tope de la búsqueda que se hace en la orden misma, sin `telar serve`: todo se lee de cero (las fuentes de los
#: documentos tardan un segundo; las de otra máquina o un comando, varios)
TOPE_AQUI = 5.0

AYUDA = ("Buscar en todo junto: lo que espera, las tareas, las casillas, los hilos, los proyectos, los objetos de los "
         "módulos que los listan y los bloques del día.")


def main(argv: list[str], ctx) -> int:
    from telar.servicios import buscar as servicio

    p = _comun.analizador("buscar", AYUDA)
    p.epilog = __doc__
    p.add_argument("texto", nargs="+", help="lo que se busca (todas las palabras)")
    p.add_argument("--fuente", action="append", default=[], metavar="FUENTE",
                   help=f"solo en esa fuente ({', '.join(servicio.FUENTES)}, bloque:<clave> u objeto:<tipo>); se repite")
    p.add_argument("--mundo", action="append", default=[], metavar="MUNDO",
                   help="solo lo de ese mundo de [mundos] (sin-clasificar: lo que no calza en ninguno); se repite")
    p.add_argument("--primero", default="", metavar="MUNDO",
                   help="lo de ese mundo y lo sin clasificar, primero en cada fuente (antes de cortar al límite); no filtra")
    p.add_argument("--limite", type=int, default=50, help="cuántas de cada fuente (0: todas); por defecto, 50")
    p.add_argument("--tope", type=float, default=None, metavar="SEGUNDOS",
                   help=f"cuánto se espera a las fuentes lentas; por defecto, {servicio.TOPE:g} con telar serve (que "
                        f"tiene lo leído guardado) y {TOPE_AQUI:g} sin él (todo se lee de cero)")
    p.add_argument("--aqui", action="store_true", help="buscar en esta orden, sin preguntarle a `telar serve`")
    p.add_argument("--json", action="store_true", help="los datos, en una línea (docs/contratos.md)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    q, pedido = " ".join(o.texto), {"fuentes": tuple(o.fuente), "mundos": tuple(o.mundo), "limite": o.limite,
                                    **({"primero": o.primero.strip()} if o.primero.strip() else {})}
    tope = None if o.tope is None else max(0.0, o.tope)
    try:
        r = None if o.aqui or not _el_serve_es_de_aqui(ctx) else del_serve(q, **pedido, tope=servicio.TOPE if tope is None else tope)
        if r is None:
            r = servicio.buscar(ctx, q, **pedido, tope=TOPE_AQUI if tope is None else tope)
            if servicio.leyendo():
                # las fuentes que no llegaron siguen leyéndose aparte: esta orden ya no las espera para salir
                salida.salir_sin_esperar()
    except ErrorDeServicio as e:
        if o.json:
            _comun.escribir_json({"error": str(e), "codigo": e.codigo})
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    ancho = shutil.get_terminal_size((100, 20)).columns
    hubo = False
    for f in r.fuentes:
        hora = f.leida[11:16] if len(f.leida) >= 16 else f.leida
        if f.falla and not f.leida:
            print(_comun.tenue(f"{f.nombre}: {f.falla} (--tope para esperarla)") if f.tarde
                  else _comun.amarillo(f"{f.nombre}: no se pudo leer: {f.falla}"))
            continue
        if f.falla:
            print(_comun.amarillo(f"{f.nombre}: no se pudo leer: {f.falla}; sale lo de las {hora}"))
        elif f.tarde:
            print(_comun.tenue(f"{f.nombre}: sigue leyéndose; sale lo de las {hora}"))
        if not f.total:
            continue
        hubo = True
        print(_comun.fuerte(f.nombre) + _comun.tenue(f"  {f.total}"))
        llave = min(max(len(h.direccion or h.id) for h in f.hallados), 28) if f.hallados else 0
        for h in f.hallados:
            cabeza = f"  {_comun.recortar(h.direccion or h.id, llave):<{llave}}  "
            mundo = f"  [{h.mundo}]" if h.mundo and r.mundos else ""
            donde = f"  · {h.donde}" if h.donde else ""
            linea = _comun.recortar(f"{h.titulo}{donde}{mundo}", max(12, ancho - len(cabeza)))
            print(_comun.tenue(cabeza) + (_comun.tenue(linea) if h.pasada else linea))
        if f.total > len(f.hallados):
            print(_comun.tenue(f"  … y {f.total - len(f.hallados)} más (--limite 0, o --fuente {f.clave})"))
    if not hubo:
        print(f"nada con «{r.q}»" + ("" if not any(f.falla for f in r.fuentes) else ", de lo que se pudo leer"))
    return 0


def _el_serve_es_de_aqui(ctx) -> bool:
    """Si el `telar serve` de esta máquina busca con la misma configuración que esta orden: la de siempre, sin `-c` ni
    `-r` que la cambien."""
    from telar import config as mod_config

    try:
        if ctx.config.origen is None or Path(ctx.config.origen).resolve() != mod_config.ruta_config().resolve():
            return False
        return Path(ctx.config.raiz).resolve() == Path(mod_config.cargar(tolerar_modulos=True).raiz).resolve()
    except Exception:  # noqa: BLE001 - si no se sabe, se busca aquí
        return False


def del_serve(q: str, *, fuentes: tuple[str, ...] = (), mundos: tuple[str, ...] = (), limite: int = 50,
              tope: float = 1.5, socket: Path | None = None, primero: str = ""):
    """La búsqueda del `telar serve` de esta máquina (`GET /buscar`, por su socket), que tiene lo leído guardado.
    None si no está o no contesta a tiempo (uno de antes de este tope tarda lo que tarde su fuente más lenta): entonces
    se busca aquí. Lo que contesta que no (menos de dos letras, una fuente que no hay), tal cual: ErrorDeServicio."""
    import http.client
    import json
    import socket as mod_socket
    from urllib.parse import urlencode

    from telar import config as mod_config
    from telar.servicios import buscar as servicio

    ruta = socket or mod_config.socket_serve()
    if not ruta.exists():
        return None
    plazo = tope + 3

    class _PorSocket(http.client.HTTPConnection):
        def connect(self):
            self.sock = mod_socket.socket(mod_socket.AF_UNIX, mod_socket.SOCK_STREAM)
            self.sock.settimeout(plazo)
            self.sock.connect(str(ruta))

    consulta = urlencode([("q", q), *(("fuente", f) for f in fuentes), *(("mundo", m) for m in mundos),
                          ("limite", str(limite)), ("tope", str(tope)), *((("primero", primero),) if primero else ())])
    try:
        c = _PorSocket("telar", timeout=plazo)
        c.request("GET", f"/buscar?{consulta}")
        r = c.getresponse()
        cuerpo = r.read()
        datos = json.loads(cuerpo or b"null")
    except (OSError, ValueError, http.client.HTTPException):
        return None
    if r.status in (404, 422) and isinstance(datos, dict) and isinstance(datos.get("detail"), str) \
            and datos["detail"] != "Not Found":
        raise ErrorDeServicio(datos["detail"], r.status)
    if r.status != 200 or not isinstance(datos, dict):
        return None
    try:
        return servicio.Busqueda(**datos)
    except ValueError:
        return None
