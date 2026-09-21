"""`telar tejer` — levantar la sesión, o reengancharla si ya está viva.

Es la única orden que crea algo sin que se lo pidan dos veces. Si la sesión ya
existe, no toca nada: reengancharse a lo que hay es más seguro que rehacerlo, y un
telar que se rearma solo pierde hilos.
"""

from __future__ import annotations

from pathlib import Path

from telar import estado as mod_estado
from telar import lectura
from telar.mux import ErrorDeMux
from telar.ordenes import _comun

AYUDA = "Levantar la sesión, o reengancharla si ya está viva."

#: Cuántos hilos se abren solos al tejer. Más que esto es una pared de tabs que nadie
#: pidió; el resto se abre a mano, y se dice cuántos quedaron fuera.
TOPE = 8


#: Cómo llama el multiplexor a un tab que nadie nombró. Ninguno dice nada del trabajo.
ANONIMOS = ("zsh", "bash", "fish", "sh", "tmux", "zellij")


def _bautizar(tel, hilos, nombre: str) -> None:
    """Al primer hilo, si el multiplexor lo dejó con el nombre de la shell, el del repo.

    Una sesión recién tejida abre un tab que se llama «zsh» o «Tab #1». No es grave, pero
    es lo primero que se ve, y no dice nada de lo que hay adentro.
    """
    primero = next(iter(hilos), None)
    if primero is None:
        return
    crudo = (primero.nombre or "").strip()
    if crudo and not (crudo.lower() in ANONIMOS or crudo.lower().startswith("tab #")):
        return
    try:
        tel.mux.renombrar_tab(primero.id, nombre)
    except ErrorDeMux:
        pass


def _poblar(ctx, tel, hilos) -> tuple[list[str], int]:
    """Un hilo por unidad del perfil, vinculado. Devuelve los abiertos y los que faltaron.

    Una sesión recién tejida tiene un tab anónimo en cualquier carpeta, y el recién
    llegado no reconoce nada suyo ahí. El perfil ya sabe cuáles son las unidades de
    trabajo: abrirlas es lo único que hace falta para que la primera pantalla sea la
    de su repositorio y no la del multiplexor.
    """
    unidades = lectura.indice(ctx.perfil, ctx.config.raiz)
    if not unidades:
        return [], 0
    _bautizar(tel, hilos, Path(ctx.config.raiz).name or "telar")
    puestos = {h.nombre for h in hilos}
    est = mod_estado.abrir(ctx.config)
    vinculados = set(est.vinculos())
    abiertos: list[str] = []
    for relativa in sorted(unidades)[:TOPE]:
        nombre = Path(relativa).name or relativa
        if nombre in puestos or relativa in vinculados:
            continue
        carpeta = Path(ctx.config.raiz) / relativa
        try:
            tel.mux.crear_tab(nombre, ruta=carpeta if carpeta.is_dir() else None, foco=False)
        except ErrorDeMux:
            continue
        # se vincula solo lo que de verdad quedó abierto: una sesión sin cliente puede
        # tragarse el `new-tab` sin quejarse, y vincular un hilo que no existe deja
        # fantasmas en la lista, que es peor que no abrir nada
        try:
            if nombre not in {h.nombre for h in tel.mux.hilos()}:
                continue
        except ErrorDeMux:
            continue
        est.vincular(nombre, relativa)
        abiertos.append(nombre)
    return abiertos, max(len(unidades) - TOPE, 0)


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("tejer", AYUDA)
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    p.add_argument(
        "--vacia", action="store_true", help="no abrir un hilo por unidad del perfil"
    )
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo

    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None:
        return _comun.queja(tel.aviso or "no hay multiplexor con el que hablar")

    ya_estaba = tel.viva
    if not ya_estaba:
        try:
            tel.mux.tejer()
        except ErrorDeMux as e:
            return _comun.queja(f"no pude levantar la sesión: {e}")

    try:
        hilos = tel.mux.hilos()
    except ErrorDeMux:
        hilos = []

    abiertos: list[str] = []
    faltaron = 0
    if not ya_estaba and not o.vacia:
        abiertos, faltaron = _poblar(ctx, tel, hilos)
        if abiertos:
            try:
                hilos = tel.mux.hilos()
            except ErrorDeMux:
                pass

    if o.json:
        return _comun.escribir_json(
            {
                "sesion": ctx.config.sesion,
                "multiplexor": ctx.config.multiplexor,
                "ya_estaba": ya_estaba,
                "hilos": len(hilos),
                "abiertos": abiertos,
                "sin_abrir": faltaron,
            }
        )

    if ya_estaba:
        print(f"la sesión «{ctx.config.sesion}» ya estaba viva, con {len(hilos)} hilos")
    else:
        print(f"tejida la sesión «{ctx.config.sesion}» ({ctx.config.multiplexor})")
        if abiertos:
            print(f"  {_comun.plural(len(abiertos), 'hilo')} del perfil: {', '.join(abiertos)}")
            if faltaron:
                print(_comun.tenue(f"  y {faltaron} unidades más, que se abren a mano"))
        elif not o.vacia:
            print(_comun.tenue("  sin unidades que abrir: telar doctor dice qué ve el perfil"))
    return 0
