"""`telar codigos` — los códigos que un hilo nombra (`H3`, `PEN-07`, `T84`) y lo que es cada uno.

    telar codigos [<hilo>]                       los del proyecto, por clase, y los de su conversación
    telar codigos Faro --buscar "acta"           los que calzan con un texto (en el código o en lo que son)
    telar codigos Faro --codigo PEN-07           el detalle de uno: su definición, dónde está y dónde más se nombra
    telar codigos Faro --maquina servidor        los de un hilo de otra máquina, por el bus

Nadie los declara: se reconocen las tres formas en que un documento de la carpeta vinculada del hilo define un código
(un título `### H3 — …`, una fila con el código en la primera columna, una viñeta `- **R2** — …`), y quedan solo los
que se nombran fuera de su archivo: en otro documento o en la conversación (docs/propuestas/codigos.md). Una tarea
(`T84`) que nombra la conversación va como tarea. Sin argumento, el hilo actual. Con `--json`, docs/contratos.md.
"""

from __future__ import annotations

import textwrap

from telar.ordenes import _comun

AYUDA = "Los códigos que un hilo nombra (H3, PEN-07, T84) y lo que es cada uno."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("codigos", AYUDA)
    p.epilog = __doc__
    p.add_argument("hilo", nargs="?", default="", help="id o nombre del hilo (por defecto, este)")
    p.add_argument("--buscar", default="", help="solo los que calzan con este texto")
    p.add_argument("--codigo", default="", help="el detalle de este código")
    p.add_argument("--maquina", default="", help="la máquina donde vive el hilo, si es otra")
    p.add_argument("--json", action="store_true", help="los datos, en una línea (docs/contratos.md)")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    from telar.servicios import ErrorDeServicio
    from telar.servicios import codigos as servicio

    try:
        r = servicio.de_hilo(ctx, o.hilo, maquina=o.maquina, codigo=o.codigo, buscar=o.buscar)
    except ErrorDeServicio as e:
        return _comun.queja(str(e))
    if o.json:
        return _comun.escribir_json(r.model_dump(mode="json"))
    if o.codigo:
        return _detalle(getattr(r, "detalle", {}) or {})

    print(f"{r.hilo}" + (f" · {r.carpeta} ({r.archivos} documentos)" if r.carpeta else ""))
    if r.aviso:
        print(f"  {r.aviso}")
    if r.conversacion:
        print("\nen esta conversación")
        for x in r.conversacion[:20]:
            que = x.get("titulo") or ("tarea" if x["tipo"] == "tarea" else "")
            print(f"  {x['codigo']:<9} {que[:90]}")
    nombres = {k["prefijo"]: k for k in r.clases}
    actual = None
    for f in r.codigos:
        if f["clase"] != actual:
            actual = f["clase"]
            k = nombres.get(actual, {})
            print(f"\n{actual}  {k.get('nombre') or ''}  ({k.get('archivo', '')})")
        print(f"  {f['codigo']:<9} {f['titulo'][:90]}")
    if not r.codigos and not r.conversacion:
        print("  ningún código" + (f" que calce con «{o.buscar}»" if o.buscar else ""))
    return 0


def _detalle(d: dict) -> int:
    print(d.get("codigo", ""))
    if d.get("tipo") == "tarea":
        print(f"  la tarea {d.get('direccion', '')}" + (f": {d['titulo']}" if d.get("titulo") else "")
              + (f" ({d['estado']})" if d.get("estado") else ""))
    for x in d.get("definiciones", []):
        print(f"\n  {x['archivo']}:{x['linea']}  {x['titulo']}")
        for k, v in (x.get("campos") or {}).items():
            print(f"    {k}: {v}")
        if not x.get("campos") and x.get("texto"):
            print(textwrap.indent(x["texto"][:1500], "    "))
    if d.get("nombrado_en"):
        print("\n  se nombra en: " + ", ".join(f"{n['archivo']}:{n['lineas'][0]}" for n in d["nombrado_en"]))
    if d.get("conversacion"):
        print(f"\n  la conversación lo nombra {d['conversacion']['veces']} veces; la última: {d['conversacion']['extracto']}")
    return 0
