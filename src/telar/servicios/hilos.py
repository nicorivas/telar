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
    #: dónde corre su agente si no es aquí: un `[remotos]`, o "?" si es un ssh que telar no armó; "" es aquí
    remoto: str = ""
    #: en qué máquina vive, con el nombre que le da el bus: la de `remoto` o, si no, esta (`Hilos.maquina`)
    maquina: str = ""
    #: la parte de la vida a la que pertenece (`[mundos]`, telar.mundos): por sus etiquetas, su carpeta, su agente o el
    #: hilo del que cuelga; "" si no calza en ninguna. Sin `[mundos]` no viene
    mundo: str = ""
    #: si duerme (telar.dormir): {desde, conversacion}; None si no
    dormido: dict | None = None
    #: la ventana de aquí de uno que vive en otra máquina (`remoto`) que está fuera de línea (telar.alcance): `False`, y
    #: su atención y si duerme son lo último que publicó. Sin eso, no viene
    alcanzable: bool | None = None
    #: desde cuándo está fuera de línea su máquina (ISO), si `alcanzable` es `False`
    fuera_de_linea_desde: str = ""
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
    #: si duerme allá (telar.dormir): su agente se cerró y su ventana espera
    dormido: bool = False
    residente: str = ""
    actualizado: str = ""
    #: si su máquina contesta (telar.alcance). `False`: está fuera de línea, y `vivo`, `dormido` y `atencion` son lo
    #: último que publicó antes de irse, no lo que pasa ahora
    alcanzable: bool = True
    #: desde cuándo está fuera de línea su máquina (ISO), si `alcanzable` es `False`
    fuera_de_linea_desde: str = ""


class Maquina(BaseModel):
    nombre: str | None = None
    en_linea: bool = False
    edad: float | None = None
    #: desde cuándo no publica (ISO, la hora de su última foto), si está fuera de línea
    desde: str = ""
    #: lo que espera en cola para cuando vuelva (telar.alcance): [{id, hilo, texto, por, cuando, intentos}]
    cola: list[dict] = Field(default_factory=list)
    #: lo que se hizo de su cola en el último día, lo más nuevo primero: [{…, ok, resultado, hecho_en}]
    hechos: list[dict] = Field(default_factory=list)


class Hilos(BaseModel):
    """Los hilos de esta máquina. Con `red`, además los de las demás: `otras_maquinas`, `maquinas` y `aviso_red`."""

    sesion: str
    #: esta máquina, con el nombre que le da el bus (telar.bus.maquina): la de los `hilos` que no dicen otra
    maquina: str = ""
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
    from telar import bus as mod_bus
    from telar import estado as mod_estado
    from telar import perfil
    from telar.ordenes import _comun

    orden = orden or mod_estado.Orden.MUX.value
    tel = _comun.tejer(ctx, con_ficha=con_ficha, todos=not vivos)
    lista = mod_estado.ordenar(tel.hilos, orden)
    aqui = mod_bus.maquina(ctx.config)
    repos = perfil.carpetas_de_repos(ctx.config)
    datos: dict = {
        "sesion": tel.sesion,
        "maquina": aqui,
        "viva": tel.viva,
        "raiz": str(tel.raiz),
        "multiplexor": ctx.config.multiplexor,
        "aviso": tel.aviso,
        "orden": orden,
        "clientes": _clientes(tel),
        "hilos": [_con_maquina(_con_repo(_comun.json_hilo(h, tel, con_ficha=con_ficha), h, ctx.config, repos), aqui)
                  for h in lista],
    }
    _con_mundo(datos["hilos"], ctx)
    _con_alcance(datos["hilos"], ctx)
    if red:
        otras, maquinas, aviso_red = _red(ctx)
        datos.update(otras_maquinas=otras, maquinas=maquinas, aviso_red=aviso_red)
    return Hilos(**datos)


def _con_mundo(hilos: list[dict], ctx) -> None:
    """Le suma a cada hilo su mundo, si la configuración declara `[mundos]`: con la lista misma (sus carpetas, sus
    agentes, sus padres y sus etiquetas), sin volver a leer los hilos."""
    from telar import mundos

    if not mundos.declarados(ctx.config):
        return
    k = mundos.Clasificador(ctx, hilos={(str(h["nombre"]), ""): h for h in hilos})
    for h in hilos:
        h["mundo"] = k.de_hilo(str(h["nombre"]))


def _con_alcance(hilos: list[dict], ctx) -> None:
    """A la ventana de aquí de un hilo que vive en una máquina fuera de línea (telar.alcance), `alcanzable: False`: su
    atención es la que publicó antes de irse. Solo si hay alguna así: lo demás no cambia."""
    remotos = {str(h.get("remoto")) for h in hilos if h.get("remoto") and h.get("remoto") != "?"}
    if not remotos:
        return
    from telar import alcance

    fuera = {m: a for m in remotos if (a := alcance.de(ctx.config, m)).fuera}
    for h in hilos:
        a = fuera.get(str(h.get("remoto") or ""))
        if a is not None:
            h["alcanzable"], h["fuera_de_linea_desde"] = False, a.desde_iso()


def _con_repo(cuerpo: dict, hilo, config, carpetas=None) -> dict:
    """Le suma al hilo el nombre del repo de `[repos]` donde vive su carpeta. Va aquí y no en
    `json_hilo`: es lo que se ve en la lista, y las demás salidas del hilo quedan como estaban. Un
    hilo sin carpeta no es de ningún repo, aunque la raíz misma esté declarada en `[repos]`."""
    from telar import perfil

    cuerpo["repo"] = perfil.repo_de(config, hilo.ruta, carpetas) if hilo.ruta else ""
    return cuerpo


def _con_maquina(cuerpo: dict, aqui: str) -> dict:
    """Le suma al hilo la máquina donde vive: la de su `remoto` (la ventana de un hilo de allá, que el nodo trajo)
    o, si no, esta. Así cada hilo de la lista, de aquí o de `otras_maquinas`, dice su `maquina` con la misma clave:
    `remoto` vacío no quiere decir «de ninguna parte», quiere decir «de aquí». Va aquí y no en `json_hilo`, como
    `repo`: las demás salidas del hilo quedan como estaban."""
    cuerpo["maquina"] = cuerpo.get("remoto") or aqui
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
    se apagó, no pudo decirlo. Por eso cada uno dice si su máquina contesta (`alcanzable`, telar.alcance), y
    `maquinas`, desde cuándo no y lo que le espera en cola.
    """
    from telar import alcance
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
    alcances = alcance.todas(ctx.config)
    fuera = {m: a for m, a in alcances.items() if a.fuera}
    otras = [
        {"nombre": d.get("nombre") or n, "direccion": objetos.direccion_de("hilo", d.get("nombre") or n, d.get("maquina", "")),
         "maquina": d.get("maquina", ""), "vivo": bool(d.get("vivo")),
         "atencion": d.get("atencion", "ninguna"), "atencion_desde": d.get("desde", ""),
         "dormido": d.get("dormido") is True,
         "residente": d.get("residente", ""), "actualizado": d.get("actualizado", ""),
         "alcanzable": d.get("maquina") not in fuera,
         "fuera_de_linea_desde": fuera[d["maquina"]].desde_iso() if d.get("maquina") in fuera else ""}
        for n, d in sorted(registro.items(), key=lambda x: (x[1].get("maquina", ""), x[0].lower()))
        if d.get("maquina") and d.get("maquina") != yo
    ]
    colas, hechos = alcance.cola(ctx.config), alcance.hechos(ctx.config)
    try:
        maquinas = [{"nombre": e.get("nombre"), "en_linea": bool(e.get("en_linea")), "edad": e.get("edad"),
                     "desde": fuera[e["nombre"]].desde_iso() if e.get("nombre") in fuera else "",
                     "cola": colas.get(e.get("nombre") or "", []), "hechos": hechos.get(e.get("nombre") or "", [])}
                    for e in mod_espejo.leer_todos(ctx.config)]
    except Exception:  # noqa: BLE001 - sin espejos, solo falta saber si la máquina sigue encendida
        maquinas = []
    return otras, maquinas, ""
