"""Poner el foco en un hilo, y abrirlo si no está vivo (telar.ordenes.ir).

Además de cambiar el foco, lo anota: el registro de foco es lo que `telar tiempo` vuelve horas por proyecto.

Lo usan `telar ir` y `POST /ir`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from telar.servicios import ErrorDeServicio


class Ido(BaseModel):
    hilo: str
    #: «foco» (ya estaba vivo), «nuevo» (se abrió aquí) o «nuevo-remoto» (se abrió en `remoto`)
    hecho: str
    carpeta: str = ""
    remoto: str = ""
    destino: str = ""
    sesion: str = ""
    #: lo que conviene saber aunque haya salido (se abrió sin agente, y por qué)
    aviso: str = ""


def ir(ctx, hilo: str, *, crear: bool = False, remoto: str = "") -> Ido:
    from telar import remoto as mod_remoto
    from telar.agente import ErrorDeAgente, lanzar
    from telar.mux import ErrorDeMux
    from telar.ordenes import _comun

    tel = _comun.tejer(ctx, con_ficha=False)
    if tel.mux is None:
        raise ErrorDeServicio(tel.aviso or "no hay multiplexor con el que hablar", 409)
    h, problema = _comun.resolver(tel, hilo)
    if h is not None and tel.vivo(h):
        try:
            tel.mux.ir(h.id)
        except ErrorDeMux as e:
            raise ErrorDeServicio(str(e), 502) from e
        tel.estado.marcar(h.nombre)
        return Ido(hilo=h.nombre, hecho="foco")
    if not crear:
        pista = "" if h is None else " (está archivado o la sesión no lo muestra)"
        raise ErrorDeServicio(f"{problema or 'ese hilo no está vivo'}{pista}. `--crear` lo abre.", 404)

    nombre = h.nombre if h is not None else hilo
    if remoto:
        r = next((x for x in ctx.config.remotos if x.nombre == remoto), None)
        if r is None:
            nombres = ", ".join(x.nombre for x in ctx.config.remotos) or "ninguno declarado"
            raise ErrorDeServicio(f"no hay remoto «{remoto}» en la configuración ({nombres})", 404)
        try:
            sesion = mod_remoto.abrir(ctx, tel, nombre, r, relativa=tel.estado.vinculos().get(nombre, ""))
        except (ErrorDeMux, ErrorDeAgente) as e:
            raise ErrorDeServicio(f"no pude abrirlo en {r.destino}: {e}", 502) from e
        tel.estado.desarchivar(nombre)
        tel.estado.marcar(nombre)
        from telar import directorio as mod_directorio

        mod_directorio.publicar_callado(ctx, tel, r.nombre)
        return Ido(hilo=nombre, hecho="nuevo-remoto", remoto=r.nombre, destino=r.destino, sesion=str(sesion))
    # sin carpeta, el tab nace donde esté parado el servidor del multiplexor, que suele ser «/»: un hilo en
    # la raíz del disco no sirve para nada. Y nace con su agente, como los que abre `tejer`
    ruta = h.ruta if h is not None and h.ruta is not None else None
    aviso = ""
    try:
        lanz = lanzar.para_hilo(ctx.config, nombre, ruta)
    except ErrorDeAgente as e:
        aviso, lanz = f"sin agente: {e}", None
    carpeta = lanz.carpeta if lanz is not None else (ruta or Path(ctx.config.raiz))
    try:
        nuevo = tel.mux.crear(nombre, ruta=carpeta, comando=lanz.comando if lanz else None)
    except ErrorDeMux as e:
        raise ErrorDeServicio(f"no pude abrirlo: {e}", 502) from e
    tel.estado.desarchivar(nombre)
    tel.estado.marcar(nombre)
    lanzar.anotar(ctx.config, nombre, lanz, tel.mux)
    return Ido(hilo=nuevo.nombre, hecho="nuevo", carpeta=str(carpeta or ""), aviso=aviso)
