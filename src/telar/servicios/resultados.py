"""Lo que una skill deja por día (`[resultados.<clave>]`), leído de la máquina donde vive, y los
comentarios sobre un día.

    from telar.servicios import resultados
    r = resultados.leer(ctx, "plan")                     # el de hoy
    r = resultados.leer(ctx, "plan", "2026-10-06")
    c = resultados.comentar(ctx, "plan", "2026-10-06", "falta la reunión de las 10")

Y las pasadas de un resultado que las lleva (`pasadas` en su vista; telar.pasadas): agregarlas, las que la persona
no ha visto (cada cosa con su mundo) y marcar hasta cuál las vio, con un mundo puesto o con ambos.

    a = resultados.agregar(ctx, "pulso", [pasada])
    p = resultados.sin_ver(ctx, "pulso")
    v = resultados.marcar_visto(ctx, "pulso", "2026-11-18T13:00", mundo="trabajo")

Lo usan `telar resultado` (telar.ordenes.resultado) y `/resultados/{clave}` (telar.api). Cómo se lee y
se comenta (en la máquina donde vive, por el bus) está en telar.resultados.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

__all__ = ["Resultado", "Comentario", "Agregadas", "SinVer", "Visto", "leer", "comentar", "agregar", "sin_ver", "marcar_visto"]


class Resultado(BaseModel):
    """El resultado de un día. Siempre trae `ok`; si no salió, `error`. `contenido` es lo que escribió la
    skill (JSON o markdown), como venga; `comentable`, si la máquina donde vive atiende comentarios."""

    model_config = ConfigDict(extra="allow")

    ok: bool
    error: str = ""
    aviso: str = ""
    desde: str = ""
    clave: str = ""
    nombre: str = ""
    dia: str = ""
    dias: list[str] = []
    formato: str = ""
    contenido: Any = None
    comentable: bool = False


class Comentario(BaseModel):
    """Lo que pasó con un comentario: lo que abrió (un hilo, normalmente) o por qué no salió."""

    ok: bool
    abrio: str = ""
    error: str = ""


class Agregadas(BaseModel):
    """Lo que pasó al agregar pasadas: las que entraron, las que ya estaban (al importar) o por qué no entró ninguna
    (`errores`, todos; `repetida`, el id que ya estaba). `avisos`: lo que no las rechazó pero se dice (un mundo que no
    está declarado donde viven: queda sin clasificar)."""

    ok: bool
    error: str = ""
    errores: list[str] = []
    repetida: str = ""
    desde: str = ""
    clave: str = ""
    agregadas: list[str] = []
    ya_estaban: list[str] = []
    distintas: list[str] = []
    en_el_dia: dict[str, int] = {}
    avisos: list[str] = []


class SinVer(BaseModel):
    """Las pasadas con algo que la persona no ha visto en algún mundo, de la más nueva a la más vieja (hasta 40 enteras;
    `total`, cuántas son; `con_cambios`, cuántas cambiaron algo; `por_mundo`, cuántas con cambios se ven con cada mundo
    puesto), cada cosa con su mundo y cada pasada con `sin_ver_en`; hasta cuál vio con ambos (`visto`: `{"id", "dia",
    "cuando"}`, vacío si nada) y con cada mundo (`vistos`), y el esquema de cada una."""

    ok: bool
    error: str = ""
    desde: str = ""
    clave: str = ""
    nombre: str = ""
    esquema: str = ""
    visto: dict[str, str] = {}
    vistos: dict[str, dict[str, str]] = {}
    total: int = 0
    con_cambios: int = 0
    por_mundo: dict[str, int] = {}
    pasadas: list[dict[str, Any]] = []


class Visto(BaseModel):
    """Hasta cuál quedó vista, con ambos (`visto`) y con cada mundo (`vistos`): `movio` en false si ya se había visto
    esa o una más nueva. `mundo`, con cuál se marcó ("" ambos)."""

    ok: bool
    error: str = ""
    desde: str = ""
    clave: str = ""
    visto: dict[str, str] = {}
    vistos: dict[str, dict[str, str]] = {}
    movio: bool = False
    mundo: str = ""
    dice: str = ""


def leer(ctx, clave: str, dia: str = "") -> Resultado:
    from telar import resultados as mod

    return Resultado(**mod.leer(ctx.config, clave, dia))


def comentar(ctx, clave: str, dia: str, texto: str) -> Comentario:
    from telar import resultados as mod

    return Comentario(**mod.comentar(ctx.config, clave, dia, texto))


def agregar(ctx, clave: str, pasadas: list, *, saltar_repetidas: bool = False, nombres: list | None = None) -> Agregadas:
    from telar import pasadas as mod

    return Agregadas(**mod.agregar(ctx.config, clave, pasadas, saltar_repetidas=saltar_repetidas, nombres=nombres))


def sin_ver(ctx, clave: str) -> SinVer:
    from telar import pasadas as mod

    return SinVer(**mod.sin_ver(ctx.config, clave, ctx=ctx))


def marcar_visto(ctx, clave: str, id_: str = "", mundo: str = "") -> Visto:
    from telar import pasadas as mod

    return Visto(**mod.marcar_visto(ctx.config, clave, id_, mundo))
