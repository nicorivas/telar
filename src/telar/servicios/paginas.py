"""Las páginas que arma un programa de afuera: el home de una sección, el de un agente y una app
(telar.ordenes.seccion, telar.ordenes.app). telar las valida contra el contrato y las entrega como vienen.

    from telar.servicios import paginas
    p = paginas.seccion(ctx, "correo")          # o "agente:Vigía"
    p = paginas.app(ctx, "lecturas")
    r = paginas.apps(ctx)

Lo usan `telar seccion`, `telar app` y `GET /secciones/{clave}`, `/apps`, `/apps/{clave}`.
"""

from __future__ import annotations

import json
import subprocess

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio, Pagina


class App(BaseModel):
    clave: str
    nombre: str
    descripcion: str = ""
    fuente: str = ""


class Apps(BaseModel):
    apps: list[App] = Field(default_factory=list)


def seccion(ctx, clave: str) -> Pagina:
    from telar.ordenes.seccion import ESPERA, validar

    if clave.startswith("agente:"):
        from telar import agentes as mod_agentes

        a = next((x for x in mod_agentes.descubrir(ctx.config) if x.seccion == clave), None)
        if a is None:
            raise ErrorDeServicio(f"no hay un agente «{clave[7:]}» en [agentes] carpeta", 404)
        datos = mod_agentes.pagina(a)
        problema = validar(datos)
        if problema:
            raise ErrorDeServicio(f"el home de {a.nombre} no cumple el contrato: {problema}", 502)
        return Pagina(**datos)

    s = next((x for x in ctx.config.secciones if x.clave == clave), None)
    if s is None:
        raise ErrorDeServicio(f"no hay sección «{clave}»: `telar seccion` lista las que hay", 404)
    if not s.home:
        raise ErrorDeServicio(f"la sección «{clave}» no declara home", 404)
    try:
        r = subprocess.run(list(s.home), capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ErrorDeServicio(f"el home de «{clave}» no corrió: {e}", 502) from e
    if r.returncode != 0:
        raise ErrorDeServicio(f"el home de «{clave}» salió con {r.returncode}: {r.stderr.strip()[-300:]}", 502)
    try:
        datos = json.loads(r.stdout)
    except ValueError as e:
        raise ErrorDeServicio(f"el home de «{clave}» no devolvió JSON", 502) from e
    problema = validar(datos)
    if problema:
        raise ErrorDeServicio(f"el home de «{clave}» no cumple el contrato: {problema}", 502)
    return Pagina(**datos)


def apps(ctx) -> Apps:
    return Apps(apps=[App(clave=a.clave, nombre=a.nombre, descripcion=a.descripcion, fuente=a.fuente)
                      for a in ctx.config.apps])


def app(ctx, clave: str) -> Pagina:
    from telar.ordenes import seccion as mod_seccion
    from telar.ordenes.app import pagina

    a = next((x for x in ctx.config.apps if x.clave == clave), None)
    if a is None:
        raise ErrorDeServicio(f"no hay app «{clave}»: `telar app` lista las que hay", 404)
    datos, error = pagina(a)
    if datos is None:
        raise ErrorDeServicio(error, 502)
    problema = mod_seccion.validar(datos)
    if problema:
        raise ErrorDeServicio(f"la página de «{clave}» no cumple el contrato: {problema}", 502)
    return Pagina(**datos)
