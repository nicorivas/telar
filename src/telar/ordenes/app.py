"""`telar app` — lo que se abre en el panel y no es un hilo: un juego, un vivero, un atlas.

    telar app                las apps declaradas
    telar app babel          su página, en la terminal
    telar app babel --json   su página, para el panel

Una app se declara en la configuración (`[apps.<clave>]`) con una de tres fuentes:

    pagina = ["/ruta/comando"]       un comando que imprime una página (el contrato de `telar seccion`)
    archivo = "~/ruta/app.html"      un HTML autocontenido, a todo el panel
    url = "http://maquina:8790"      una página servida, en un marco a todo el panel

Las tres salen de aquí como una página del mismo contrato, así el panel dibuja una sola cosa: un
`archivo` es un bloque con un lienzo, una `url` un bloque con un marco (y un botón para abrirla en
el navegador). Ver docs/configuracion.md (`[apps]`) y docs/contratos.md (`telar app`).
"""

from __future__ import annotations

from pathlib import Path

from telar.ordenes import _comun
from telar.ordenes import seccion as mod_seccion

AYUDA = "Las apps del panel (un juego, un vivero): la lista, o la página de una."


def pagina(app) -> tuple[dict | None, str]:
    """La página de una app, sea cual sea su fuente. (página, error o "")."""
    base = {"titulo": app.nombre, **({"subtitulo": app.descripcion} if app.descripcion else {})}
    if app.pagina:
        datos, error = mod_seccion.correr(app.pagina, f"la página de «{app.clave}»")
        if datos is not None:
            datos.setdefault("titulo", app.nombre)
        return datos, error
    if app.archivo:
        if not Path(app.archivo).is_file():
            return None, f"no existe {app.archivo}"
        lienzo = {"archivo": app.archivo, "alto": "lleno", **({"memoria": app.memoria} if app.memoria else {})}
        return {**base, "bloques": [{"lienzo": lienzo}]}, ""
    return {**base, "bloques": [{"marco": {"url": app.url, "alto": "lleno"}}],
            "acciones": [{"nombre": "abrir en el navegador", "tipo": "abrir", "enlace": app.url}]}, ""


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("app", AYUDA)
    p.epilog = __doc__
    p.add_argument("clave", nargs="?", default="", help="cuál; sin ella, la lista")
    p.add_argument("--json", action="store_true", help="la página, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    apps = {a.clave: a for a in ctx.config.apps}
    if not o.clave:
        if o.json:
            return _comun.escribir_json({"apps": [
                {"clave": a.clave, "nombre": a.nombre, "descripcion": a.descripcion, "fuente": a.fuente}
                for a in apps.values()]})
        for a in apps.values():
            print(f"{a.clave}  {a.nombre}  " + _comun.tenue(f"{a.fuente}" + (f" · {a.descripcion}" if a.descripcion else "")))
        if not apps:
            print(_comun.tenue("no hay apps: se declaran en la configuración, [apps.<clave>]"))
        return 0

    a = apps.get(o.clave)
    if a is None:
        return _comun.queja(f"no hay app «{o.clave}»: `telar app` lista las que hay")
    datos, error = pagina(a)
    if datos is None:
        return _comun.queja(error)
    problema = mod_seccion.validar(datos)
    if problema:
        return _comun.queja(f"la página de «{o.clave}» no cumple el contrato: {problema}")
    if o.json:
        return _comun.escribir_json(datos)
    print(datos["titulo"])
    for b in datos.get("bloques", []):
        if b.get("titulo"):
            print(f"\n{b['titulo'].upper()}")
        if b.get("texto"):
            print(b["texto"])
        if b.get("lienzo"):
            print(_comun.tenue(f"  [lienzo] {b['lienzo']['archivo']}"))
        if b.get("marco"):
            print(_comun.tenue(f"  [marco] {b['marco']['url']}"))
        for x in b.get("items", []):
            print(f"  · {x.get('titulo', '')}  " + _comun.tenue((x.get("fecha") or "")[:16]))
    return 0
