"""Los hilos de las otras personas del bus y escribirles (telar.entre_personas): `GET /directorio` y
`POST /directorio/escribir`, para la sección «colegas» de la barra de la página.

Lo que se ve de otra persona es lo que su nodo publica (nombre, si vive, su carpeta y una línea), nunca su
conversación; escribirle deja un mensaje en la casilla de ese hilo, como `telar correo enviar`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from telar.servicios import ErrorDeServicio


class Directorio(BaseModel):
    """`personas`: [{persona, maquinas: [{maquina, publicado, visto, al_dia, hilos: [{nombre, ext, vivo, carpeta,
    resumen}]}]}], por nombre; `yo`, quién mira."""

    yo: str = ""
    personas: list[dict] = Field(default_factory=list)


def _al_dia(visto: str, ahora: datetime) -> bool:
    from telar import entre_personas

    try:
        return (ahora - datetime.fromisoformat(visto)).total_seconds() < entre_personas.VIEJO
    except (TypeError, ValueError):
        return False


def ver(ctx, *, ahora: datetime | None = None) -> Directorio:
    from telar import bus as mod_bus
    from telar import entre_personas

    ahora = ahora or datetime.now().astimezone()
    yo = mod_bus.persona(ctx.config) if mod_bus.hay_bus(ctx.config) else ""
    personas = []
    for persona, maquinas in sorted(entre_personas.leer(ctx.config).items()):
        if persona == yo or not isinstance(maquinas, dict):
            continue
        lista = []
        for maquina, d in sorted(maquinas.items()):
            hilos = sorted((h for h in d.get("hilos", []) if isinstance(h, dict) and h.get("nombre")),
                           key=lambda h: (not h.get("vivo"), str(h["nombre"]).casefold()))
            lista.append({"maquina": maquina, "publicado": d.get("publicado", ""), "visto": d.get("visto", ""),
                          "al_dia": _al_dia(str(d.get("visto", "")), ahora), "hilos": hilos})
        personas.append({"persona": persona, "maquinas": lista})
    return Directorio(yo=yo, personas=personas)


class Escrito(BaseModel):
    id: str = ""
    persona: str
    hilo: str


def escribir(ctx, persona: str, hilo: str, texto: str, *, asunto: str = "") -> Escrito:
    from telar import bus as mod_bus
    from telar import cuentas

    if not mod_bus.hay_bus(ctx.config):
        raise ErrorDeServicio("sin bus no se le escribe a otra persona", 404)
    try:
        persona = cuentas.validar(persona.strip())
    except cuentas.ErrorDeCuentas as e:
        raise ErrorDeServicio(str(e), 422) from e
    if persona == mod_bus.persona(ctx.config):
        raise ErrorDeServicio("entre tus hilos se escribe con telar mensaje", 422)
    if not hilo.strip() or not texto.strip():
        raise ErrorDeServicio("¿a qué hilo, y qué le digo?", 422)
    try:
        # de: la persona que escribe, desde la página (no un hilo suyo); quien recibe ve de qué cuenta viene
        r = mod_bus.escribir_a(ctx.config, persona, hilo.strip(), texto.strip(), de="página", asunto=asunto)
    except mod_bus.ErrorDeBus as e:
        raise ErrorDeServicio(str(e), 409 if "no lo aceptó" in str(e) else 502) from e
    return Escrito(id=str(r.get("id", "")), persona=persona, hilo=hilo.strip())
