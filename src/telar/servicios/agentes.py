"""La ficha de un agente residente para la página (`GET /agentes/del-hilo?hilo=…`): lo que dice su definición, su
CLAUDE.md, su último relevo y cuánto pesa su conversación. La usa la barra de la derecha al ver el hilo de un
agente.

El CLAUDE.md, la definición y la carpeta se leen de aquí (el repositorio está en todas las máquinas); el relevo y el
peso de la conversación, también: son de esta máquina, así que para el hilo de un agente que vive en otra no se
saben todavía (`aqui: false`).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from telar.servicios import ErrorDeServicio

#: lo más que se manda de un CLAUDE.md o de un relevo (caracteres)
MAX_TEXTO = 120_000


class FichaAgente(BaseModel):
    """`agente` (lo de `telar agentes --json`), `claude_md`, `relevo` ({texto, cuando} o null), `conversacion`
    ({id, peso, tope}), `rotacion` (la fase si está rotando, o ""), `aqui` (si vive en esta máquina)."""

    model_config = ConfigDict(extra="allow")


def _texto(ruta: Path) -> str:
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")[:MAX_TEXTO]
    except OSError:
        return ""


def del_hilo(ctx, hilo: str, *, maquina: str = "") -> FichaAgente:
    from telar import agente as mod_agente
    from telar import agentes as mod_agentes
    from telar import bus as mod_bus
    from telar import estado as mod_estado
    from telar import rotacion

    a = mod_agentes.del_hilo(ctx.config, hilo)
    if a is None:
        raise ErrorDeServicio(f"«{hilo}» no es el hilo de un agente", 404)
    aqui = not maquina or maquina in ("aqui", "local") or (mod_bus.hay_bus(ctx.config) and maquina == mod_bus.maquina(ctx.config))
    ficha: dict = {"agente": mod_agentes.como_json(a), "claude_md": _texto(a.carpeta / "CLAUDE.md"),
                   "definicion_texto": _texto(a.definicion) if a.definicion else "", "aqui": aqui,
                   "relevo": None, "conversacion": None, "rotacion": ""}
    if not aqui:
        return FichaAgente(**ficha)
    relevo = rotacion.ruta_relevo(ctx.config, a.clave)
    if relevo.is_file():
        ficha["relevo"] = {"texto": _texto(relevo), "ruta": str(relevo),
                           "cuando": datetime.fromtimestamp(relevo.stat().st_mtime).astimezone().isoformat(timespec="seconds")}
    est = mod_estado.abrir(ctx.config)
    sid = (est.sesiones().get(hilo) or ("",))[0]
    if sid and ctx.config.agente.nombre:
        try:
            archivo = mod_agente.obtener(ctx.config.agente.nombre, ctx.config).archivo_de(sid)
            peso = Path(archivo).stat().st_size if archivo else 0
        except Exception:  # noqa: BLE001 - sin el archivo, no se sabe el peso
            peso = 0
        ficha["conversacion"] = {"id": sid, "peso": peso, "tope": rotacion.tope(ctx.config)}
    ficha["rotacion"] = (rotacion.leer(ctx.config).get(hilo) or {}).get("fase", "")
    return FichaAgente(**ficha)
