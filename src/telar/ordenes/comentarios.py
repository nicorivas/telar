"""`telar comentarios` — los comentarios que la persona dejó sobre un archivo (seleccionando texto en la página), para que
un agente los lea, los atienda, responda y resuelva (telar.comentarios; el formato, docs/contratos.md «Los comentarios de
un archivo»).

    telar comentarios listar [ruta]              los hilos abiertos de los archivos bajo esa ruta (una carpeta, un
                                                 repositorio o un archivo; sin ella, desde aquí)
    telar comentarios ver <archivo>              todos los hilos de un archivo, con dónde están hoy
    telar comentarios responder <ref> <texto>    una respuesta en el hilo
    telar comentarios resolver <ref> [texto]     la respuesta (si va) y el hilo resuelto: «está hecho»
    telar comentarios reabrir <ref> [texto]      volver a abrirlo

`<ref>` es `archivo.md#h3` (o `archivo.md h3`, o la dirección `comentario:archivo.md#h3`). Con «máquina:» delante
(`servidor:docs/x.md#h3`), en esa máquina, por el bus. Las respuestas firman con el nombre del hilo (`TELAR_HILO`) o
`--autor`. El archivo de al lado se commitea y se sube al tiro, solo él (`--sin-subir` lo deja escrito y nada más).

Cada hilo dice en qué línea está hoy, qué se comentó y, si ya no es lo mismo, qué dice hoy ese lugar; y cómo se lo
encontró cuando no fue exacto: «reanclado tras el reflujo de líneas» (fiable), «reanclado por parecido (N%)» (mira antes
de actuar), «la cita ya no existe» (casi siempre, ya se atendió: verifícalo y resuelve) o «⚠ sin ancla» (no adivines:
pregunta). Resolver es decir que está hecho: solo lo que se aplicó, y siempre con una respuesta que diga qué se hizo.
"""

from __future__ import annotations

import os
from pathlib import Path

from telar.ordenes import _comun
from telar.servicios import ErrorDeServicio

AYUDA = "Los comentarios sobre un archivo: encontrarlos, leerlos con su ancla, responder y resolver."
VERBOS = ("listar", "ver", "responder", "resolver", "reabrir")


def main(argv: list[str], ctx) -> int:
    from telar.servicios import comentarios as servicio

    p = _comun.analizador("comentarios", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", default="listar", choices=VERBOS)
    p.add_argument("args", nargs="*", help="la ruta, o la referencia al hilo y el texto")
    p.add_argument("--todos", action="store_true", help="listar: también los resueltos")
    p.add_argument("--autor", default="", help="quién firma la respuesta (por defecto, el hilo: TELAR_HILO)")
    p.add_argument("--sin-subir", action="store_true", help="no commitear ni subir el archivo de al lado")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    aqui = Path.cwd()
    try:
        if o.verbo == "listar":
            r = servicio.listar_en(ctx, o.args[0] if o.args else str(aqui), todos=o.todos, desde=aqui)
            if o.json:
                return _comun.escribir_json(r.model_dump(mode="json"))
            _listado(r, o.todos)
            return 0
        if o.verbo == "ver":
            if not o.args:
                raise ErrorDeServicio("¿qué archivo? telar comentarios ver <archivo>", 422)
            c = servicio.ver_en(ctx, _sin_direccion(o.args[0]), desde=aqui)
            if o.json:
                return _comun.escribir_json(c.model_dump(mode="json"))
            print(_bloque(_nombre(c.ruta), c.hilos) if c.hilos else f"{_nombre(c.ruta)} no tiene comentarios.", end="")
            if not c.hilos:
                print()
            return 0
        ruta, hilo, resto = _referencia(o.args)
        texto = " ".join(resto).strip()
        if o.verbo == "responder" and not texto:
            raise ErrorDeServicio("¿qué le respondes? telar comentarios responder <archivo>#h1 \"…\"", 422)
        firma = o.autor or os.environ.get("TELAR_HILO", "") or "agente"
        pedido = servicio.Pedido(ruta=ruta, accion=o.verbo, hilo=hilo, texto=texto, autor=firma)
        c = servicio.hacer_en(ctx, pedido, subir="no" if o.sin_subir else "ya", desde=aqui)
    except ErrorDeServicio as e:
        if o.json:
            _comun.escribir_json({"error": str(e), "codigo": e.codigo, **e.datos})
        return _comun.queja(str(e), 1 if e.codigo in (404, 409) else 2)
    if o.json:
        return _comun.escribir_json(c.model_dump(mode="json"))
    verbo = {"responder": "respondido", "resolver": "resuelto", "reabrir": "reabierto"}[o.verbo]
    print(f"{_nombre(c.ruta)}#{hilo} {verbo}.")
    return 0


def _sin_direccion(texto: str) -> str:
    """`comentario:x.md#h1` → `x.md#h1` (la dirección de telar objeto también vale)."""
    return texto[len("comentario:"):] if texto.startswith("comentario:") else texto


def _referencia(args: list[str]) -> tuple[str, str, list[str]]:
    """(archivo, hilo, lo que sigue) de `archivo.md#h3 …` o `archivo.md h3 …`."""
    if not args:
        raise ErrorDeServicio("¿qué hilo? archivo.md#h3 (o archivo.md h3)", 422)
    primero = _sin_direccion(args[0])
    if "#" in primero:
        ruta, _, hilo = primero.rpartition("#")
        return ruta, hilo, args[1:]
    if len(args) < 2:
        raise ErrorDeServicio("¿qué hilo? archivo.md#h3 (o archivo.md h3)", 422)
    return primero, args[1], args[2:]


def _nombre(ruta: str) -> str:
    """Una ruta para leerla: relativa a donde se está, si está adentro; la de otra máquina, tal cual."""
    if not ruta.startswith(("/", "~", ".")) and ":" in ruta:
        return ruta
    try:
        rel = os.path.relpath(Path(ruta).expanduser())
    except ValueError:
        return ruta
    return ruta if rel.startswith("..") else rel


#: cómo se dice que el ancla no fue exacta (cuando lo fue, no se dice nada)
NOTAS = {
    "contexto": " · reanclado entre repeticiones",
    "normalizado": " · reanclado tras el reflujo de líneas",
    "vecindario": " · la cita ya no existe; anclado por lo que la rodeaba",
}


def _nota(h) -> str:
    if h.metodo == "aproximado":
        return f" · reanclado por parecido ({round((h.confianza or 0) * 100)}%), el texto cambió"
    return NOTAS.get(h.metodo or "", "")


def _recorte(s: str, n: int = 120) -> str:
    limpio = " ".join((s or "").split())
    return limpio if len(limpio) <= n else limpio[:n - 1] + "…"


def _bloque(nombre: str, hilos) -> str:
    abiertos = sum(1 for h in hilos if h.estado == "abierto")
    resueltos = len(hilos) - abiertos
    cuenta = ", ".join(x for x in (_comun.plural(abiertos, "abierto") if abiertos else "",
                                   _comun.plural(resueltos, "resuelto") if resueltos else "") if x)
    out = f"{nombre} — {cuenta}\n\n"
    for h in hilos:
        donde = ("⚠ sin ancla" if h.linea is None else f"líneas {h.linea}–{h.linea_fin}" if h.linea_fin and h.linea_fin != h.linea
                 else f"línea {h.linea}")
        out += f"  [{h.id}] {donde}{' · resuelto' if h.estado == 'resuelto' else ''}{_nota(h)}\n"
        out += f"       comentó: «{_recorte(h.cita)}»\n"
        if h.actual is not None and _recorte(h.actual) != _recorte(h.cita):
            out += f"       hoy dice: «{_recorte(h.actual)}»\n"
        for c in h.comentarios:
            out += f"       {c.autor}: " + " ⏎ ".join(x.strip() for x in c.cuerpo.strip().splitlines()) + "\n"
        out += "\n"
    return out


def _listado(r, todos: bool) -> None:
    for e in r.errores:
        print(_comun.tenue(f"no se pudo leer: {e}"))
    if not r.archivos:
        print("No hay comentarios." if todos else "No hay comentarios abiertos.")
        return
    print("".join(_bloque(_nombre(c.ruta), c.hilos) for c in r.archivos), end="")
