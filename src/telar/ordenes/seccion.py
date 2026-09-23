"""`telar seccion` — la página de una sección de la lista de hilos.

    telar seccion              las secciones declaradas
    telar seccion diario       corre su `home` y muestra lo que devuelve
    telar seccion diario --json

Una sección se declara en la configuración (`[secciones.<clave>]`) con los hilos que le
pertenecen y, si quiere, un `home`: un comando que imprime el JSON de su página. telar lo
corre, comprueba que tenga la forma del contrato (docs/contratos.md) y lo entrega; qué
dice la página es asunto de quien escribió el comando.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from telar.ordenes import _comun

AYUDA = "La página de una sección de la lista: corre su `home` y devuelve su JSON."

#: cuánto se le espera al comando: una página que tarda más que esto no es una página.
ESPERA = 30


def validar(datos: object) -> str:
    """"" si `datos` cumple el contrato de una página; si no, qué falla."""
    if not isinstance(datos, dict):
        return "se esperaba un objeto"
    if not isinstance(datos.get("titulo", ""), str):
        return "titulo: se esperaba un texto"
    bloques = datos.get("bloques", [])
    if not isinstance(bloques, list):
        return "bloques: se esperaba una lista"
    for i, b in enumerate(bloques):
        if not isinstance(b, dict):
            return f"bloques[{i}]: se esperaba un objeto"
        items = b.get("items", [])
        if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
            return f"bloques[{i}].items: se esperaba una lista de objetos"
        if "lienzo" in b:
            problema = _lienzo(b["lienzo"])
            if problema:
                return f"bloques[{i}].lienzo: {problema}"
    return ""


def _lienzo(l: object) -> str:
    """Un lienzo es una página HTML local que se muestra en un iframe dentro del panel."""
    if not isinstance(l, dict):
        return "se esperaba un objeto"
    archivo = l.get("archivo")
    if not isinstance(archivo, str) or not archivo.endswith(".html") or not Path(archivo).is_absolute():
        return "archivo: se esperaba la ruta absoluta de un .html"
    if not Path(archivo).is_file():
        return f"no existe {archivo}"
    alto = l.get("alto", 240)
    if not isinstance(alto, int) or isinstance(alto, bool) or not 40 <= alto <= 2000:
        return "alto: se esperaba un número de píxeles entre 40 y 2000"
    params = l.get("params", {})
    if not isinstance(params, dict) or not all(isinstance(k, str) and isinstance(v, (str, int, float)) for k, v in params.items()):
        return "params: se esperaba un objeto de textos"
    return ""


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("seccion", AYUDA)
    p.epilog = __doc__
    p.add_argument("clave", nargs="?", default="", help="cuál; sin ella, la lista")
    p.add_argument("--json", action="store_true", help="la página, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    secciones = {s.clave: s for s in ctx.config.secciones}
    if not o.clave:
        for s in secciones.values():
            print(f"{s.clave}  {s.nombre}  " + _comun.tenue(", ".join(s.hilos) + (" · con home" if s.home else "")))
        if not secciones:
            print(_comun.tenue("no hay secciones: se declaran en la configuración, [secciones.<clave>]"))
        return 0

    s = secciones.get(o.clave)
    if s is None:
        return _comun.queja(f"no hay sección «{o.clave}»: `telar seccion` lista las que hay")
    if not s.home:
        return _comun.queja(f"la sección «{o.clave}» no declara home")
    try:
        r = subprocess.run(list(s.home), capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return _comun.queja(f"el home de «{o.clave}» no corrió: {e}")
    if r.returncode != 0:
        return _comun.queja(f"el home de «{o.clave}» salió con {r.returncode}: {r.stderr.strip()[-300:]}")
    try:
        datos = json.loads(r.stdout)
    except ValueError:
        return _comun.queja(f"el home de «{o.clave}» no devolvió JSON")
    problema = validar(datos)
    if problema:
        return _comun.queja(f"el home de «{o.clave}» no cumple el contrato: {problema}")
    if o.json:
        return _comun.escribir_json(datos)
    print(datos.get("titulo", s.nombre))
    for b in datos.get("bloques", []):
        if b.get("titulo"):
            print(f"\n{b['titulo'].upper()}")
        if b.get("texto"):
            print(b["texto"])
        for x in b.get("items", []):
            print(f"  · {x.get('titulo', '')}  " + _comun.tenue((x.get("fecha") or "")[:16]))
    return 0
