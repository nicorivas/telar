"""Las fotos que publican las otras máquinas: sus hilos, como los ve cada una (telar.espejo).

    from telar.servicios import espejos
    r = espejos.ver(ctx)            # una foto por máquina, con su edad y si sigue en línea

Lo usan `telar espejo ver` y `GET /espejos`; el panel lo pide cada 30 s para el grupo de cada máquina. Con `[mundos]`,
cada hilo trae su `mundo`, como los de aquí, y también cada archivado (`archivados`: los de su ARCHIVO).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Espejo(BaseModel):
    """La foto de una máquina, tal como la publicó (docs/contratos.md, «telar espejo ver --json»)."""

    model_config = ConfigDict(extra="allow")


class Espejos(BaseModel):
    espejos: list[Espejo] = Field(default_factory=list)
    vigente: int | float = 0
    #: si el nodo de aquí está al día con el bus (telar.alcance.al_dia): si no, que una foto sea vieja no dice que su
    #: máquina se fue (la que no tiene noticias es esta)
    al_dia: bool = False


def ver(ctx) -> Espejos:
    """Las fotos; con `[mundos]`, cada hilo de cada una con su `mundo`, derivado con la configuración de aquí. Cada
    foto trae además lo que espera en cola para su máquina y lo que se hizo de esa cola en el último día
    (telar.alcance: `cola`, `hechos`)."""
    from telar import alcance
    from telar import espejo as mod
    from telar import mundos

    colas, hechos = alcance.cola(ctx.config), alcance.hechos(ctx.config)
    fotos = [{**f, "cola": colas.get(f.get("nombre") or "", []), "hechos": hechos.get(f.get("nombre") or "", [])}
             for f in mod.leer_todos(ctx.config)]
    if mundos.declarados(ctx.config):
        for f in fotos:
            f["hilos"] = [dict(j) for j in f.get("hilos") or [] if isinstance(j, dict)]
            f["archivados"] = [dict(j) for j in f.get("archivados") or [] if isinstance(j, dict)]
        # (los archivados, después: un nombre que está vivo y archivado en la misma máquina vale por el vivo)
        k = mundos.Clasificador(ctx, hilos={(str(j.get("nombre") or ""), str(f.get("nombre") or "")): j
                                            for f in fotos for j in [*f["archivados"], *f["hilos"]] if j.get("nombre")})
        for f in fotos:
            for j in [*f["hilos"], *f["archivados"]]:
                j["mundo"] = k.de_hilo(str(j.get("nombre") or ""), str(f.get("nombre") or ""))
    return Espejos(espejos=fotos, vigente=mod.VIGENTE, al_dia=alcance.al_dia(ctx.config))
