"""`telar directorio` — los hilos de cada persona en las máquinas compartidas.

    telar directorio                 quién tiene qué hilos en cada máquina de [remotos]
    telar directorio --json
    telar directorio publicar        publica (o actualiza) los hilos propios de esa máquina

Solo en las máquinas que declaran `directorio` en `[remotos.<n>]`. Publicar lo hace telar
solo al crear, renombrar, archivar o cerrar un hilo remoto; a mano sirve para la primera
vez. Ver `telar.directorio`.
"""

from __future__ import annotations

from telar import directorio as mod_directorio
from telar.ordenes import _comun

AYUDA = "Los hilos remotos de cada persona de una máquina compartida: leerlos y publicar los propios."


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("directorio", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", choices=("publicar",), help="publicar: los hilos propios")
    p.add_argument("--remoto", default="", help="solo esa máquina de [remotos]")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    from telar import entre_personas

    remotos = [r for r in ctx.config.remotos if r.directorio and (not o.remoto or r.nombre == o.remoto)]
    por_bus = {} if o.remoto else entre_personas.leer(ctx.config)
    if not remotos and not por_bus:
        return _comun.queja("nadie publica su directorio: ni por el bus ni en una máquina de [remotos] con `directorio`")

    if o.verbo == "publicar":
        if not remotos:
            return _comun.queja("por el bus, el directorio lo publica el nodo solo; aquí no hay [remotos] con `directorio`")
        tel = _comun.tejer(ctx, con_ficha=False)
        salida = {}
        for r in remotos:
            salida[r.nombre] = mod_directorio.publicar(ctx, tel, r)
        if o.json:
            return _comun.escribir_json({"publicado": salida})
        for nombre, problema in salida.items():
            print(f"{nombre}: {problema or 'publicado'}")
        return 1 if any(salida.values()) else 0

    datos = []
    for r in remotos:
        entradas, error = mod_directorio.leer(r)
        datos.append({"remoto": r.nombre, "error": error, "personas": entradas})
    if o.json:
        return _comun.escribir_json({"remotos": datos, "bus": por_bus})
    if por_bus:
        print(_comun.fuerte("por el bus"))
        for persona, maquinas in sorted(por_bus.items()):
            for maquina, d in sorted(maquinas.items()):
                print(f"  {persona}@{maquina}" + _comun.tenue(f" · {str(d.get('publicado', ''))[:16]}"))
                for h in d.get("hilos", []):
                    print(f"    {h['nombre']}  " + _comun.tenue(f"{persona}+{h.get('ext', '')}  {h.get('resumen', '')}"))
    for d in datos:
        print(_comun.fuerte(d["remoto"]))
        if d["error"]:
            print(f"  no se pudo leer: {d['error']}")
        for persona in d["personas"]:
            if persona.get("error"):
                print(_comun.tenue(f"  {persona['usuario']}: {persona['error']}"))
                continue
            print(f"  {persona['usuario']}" + _comun.tenue(f" · {persona.get('actualizado', '')[:16]}"))
            for h in persona.get("hilos", []):
                print(f"    {h['nombre']}  " + _comun.tenue(f"{h['direccion']}  {h.get('resumen', '')}"))
    return 0
