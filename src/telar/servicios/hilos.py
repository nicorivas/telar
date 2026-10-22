"""Los hilos de la sesión, con lo que telar sabe de cada uno (y, con `red`, los de las otras máquinas).

    from telar.servicios import hilos
    r = hilos.hilos(ctx)                          # todos, con su ficha
    r = hilos.hilos(ctx, con_ficha=False)         # rápido: sin leer los documentos
    r = hilos.hilos(ctx, red=True)                # además, el registro del bus

Lo usan `telar hilos` (telar.ordenes.hilos) y `GET /hilos` (telar.api). La forma es la de
docs/contratos.md, «telar hilos --json».
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Hilos", "Hilo", "Ficha", "OtroHilo", "Maquina", "hilos", "ORDENES"]


class Ficha(BaseModel):
    """Lo que el documento de un hilo dice de sí mismo (`telar ficha`)."""

    model_config = ConfigDict(extra="allow")

    documento: str = ""
    relativo: str = ""
    titulo: str = ""
    etiqueta: str = ""
    estado: str = ""
    nota: str = ""
    vacia: bool = False


class Hilo(BaseModel):
    """Un hilo: su tab, su carpeta, su atención y su tiempo. `ficha` está solo si se pidió."""

    model_config = ConfigDict(extra="allow")

    id: str
    nombre: str
    #: su dirección de objeto, `hilo:<nombre>` (telar.objetos)
    direccion: str = ""
    vivo: bool = False
    propio: bool = False
    activo: bool = False
    archivado: bool = False
    vinculado: bool = False
    ruta: str = ""
    relativa: str = ""
    arquetipo: str = ""
    #: el repositorio de `[repos]` al que pertenece su carpeta (telar.perfil.repo_de); "" si ninguno
    repo: str = ""
    prioridad: int | None = None
    atencion: str = "ninguna"
    atencion_desde: str | None = None
    sin_ver: bool = False
    visto: str | None = None
    actividad: str | None = None
    tiempo: float = 0.0
    sesiones: list[str] = Field(default_factory=list)
    remoto: str = ""
    ficha: Ficha | None = None


class OtroHilo(BaseModel):
    """Un hilo de otra máquina, como lo registra el bus."""

    nombre: str
    maquina: str
    #: su dirección de objeto, `hilo:<nombre>`, como la da `telar objeto` (lo busca en el bus por el nombre)
    direccion: str = ""
    vivo: bool = False
    atencion: str = "ninguna"
    atencion_desde: str = ""
    residente: str = ""
    actualizado: str = ""


class Maquina(BaseModel):
    nombre: str | None = None
    en_linea: bool = False
    edad: float | None = None


class Hilos(BaseModel):
    """Los hilos de la sesión. Con `red`, además `otras_maquinas`, `maquinas` y `aviso_red`."""

    sesion: str
    viva: bool
    raiz: str
    multiplexor: str
    aviso: str = ""
    orden: str
    clientes: list[int] = Field(default_factory=list)
    hilos: list[Hilo]
    otras_maquinas: list[OtroHilo] | None = None
    maquinas: list[Maquina] | None = None
    aviso_red: str | None = None


def _ordenes() -> tuple[str, ...]:
    from telar import estado as mod_estado

    return tuple(o.value for o in mod_estado.Orden)


ORDENES = _ordenes()


def hilos(ctx, *, vivos: bool = False, red: bool = False, con_ficha: bool = True, orden: str = "") -> Hilos:
    """Los hilos, ordenados como se pida (por defecto, como los da el multiplexor). `vivos`: solo los
    que el multiplexor muestra ahora. `red`: además, los de las otras máquinas, del registro del bus."""
    from telar import estado as mod_estado
    from telar.ordenes import _comun

    orden = orden or mod_estado.Orden.MUX.value
    tel = _comun.tejer(ctx, con_ficha=con_ficha, todos=not vivos)
    lista = mod_estado.ordenar(tel.hilos, orden)
    datos: dict = {
        "sesion": tel.sesion,
        "viva": tel.viva,
        "raiz": str(tel.raiz),
        "multiplexor": ctx.config.multiplexor,
        "aviso": tel.aviso,
        "orden": orden,
        "clientes": _clientes(tel),
        "hilos": [_con_repo(_comun.json_hilo(h, tel, con_ficha=con_ficha), h, ctx.config) for h in lista],
    }
    if red:
        otras, maquinas, aviso_red = _red(ctx)
        datos.update(otras_maquinas=otras, maquinas=maquinas, aviso_red=aviso_red)
    return Hilos(**datos)


def _con_repo(cuerpo: dict, hilo, config) -> dict:
    """Le suma al hilo el nombre del repo de `[repos]` donde vive su carpeta. Va aquí y no en
    `json_hilo`: es lo que se ve en la lista, y las demás salidas del hilo quedan como estaban. Un
    hilo sin carpeta no es de ningún repo, aunque la raíz misma esté declarada en `[repos]`."""
    from telar import perfil

    cuerpo["repo"] = perfil.repo_de(config, hilo.ruta) if hilo.ruta else ""
    return cuerpo


def _clientes(tel) -> list[int]:
    """Los pids de las terminales que muestran la sesión; vacío si no se puede saber."""
    from telar.mux import ErrorDeMux

    if tel.mux is None or not tel.viva:
        return []
    try:
        return tel.mux.clientes()
    except ErrorDeMux:
        return []


def _red(ctx) -> tuple[list[dict], list[dict], str]:
    """Los hilos de las otras máquinas, como los registra el bus: (hilos, máquinas, aviso).

    El bus tiene un registro de todos los hilos de la persona, de cualquier máquina; cada nodo publica
    los suyos. Un hilo del registro lleva `vivo` según lo último que publicó su máquina: si esa máquina
    se apagó, no pudo decirlo, y `maquinas` trae si su espejo sigue en línea.
    """
    from telar import bus as mod_bus
    from telar import espejo as mod_espejo
    from telar import objetos

    if not ctx.config.bus.url:
        return [], [], "no hay bus ([bus] en la configuración): solo se ven los hilos de esta máquina"
    try:
        registro = mod_bus.estados(ctx.config)
    except mod_bus.ErrorDeBus as e:
        return [], [], f"{e}; se muestran solo los hilos de esta máquina"
    yo = mod_bus.maquina(ctx.config)
    otras = [
        {"nombre": d.get("nombre") or n, "direccion": objetos.direccion_de("hilo", d.get("nombre") or n),
         "maquina": d.get("maquina", ""), "vivo": bool(d.get("vivo")),
         "atencion": d.get("atencion", "ninguna"), "atencion_desde": d.get("desde", ""),
         "residente": d.get("residente", ""), "actualizado": d.get("actualizado", "")}
        for n, d in sorted(registro.items(), key=lambda x: (x[1].get("maquina", ""), x[0].lower()))
        if d.get("maquina") and d.get("maquina") != yo
    ]
    try:
        maquinas = [{"nombre": e.get("nombre"), "en_linea": bool(e.get("en_linea")), "edad": e.get("edad")}
                    for e in mod_espejo.leer_todos(ctx.config)]
    except Exception:  # noqa: BLE001 - sin espejos, solo falta saber si la máquina sigue encendida
        maquinas = []
    return otras, maquinas, ""
