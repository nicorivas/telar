"""`telar equipo` — que una persona de confianza vea tus tareas del equipo y te sugiera prioridades.

    telar equipo servir [--host IP] [--puerto N]   la página y la API de la persona (solo lee y sugiere)
    telar equipo sugerencias [--todas] [--json]    la bandeja: lo que falta por decidir
    telar equipo sugerencias --remoto telar        la misma bandeja, leída por ssh desde otra máquina
    telar equipo aceptar ID [--nota "…"]           una sugerencia: sube la prioridad un nivel · un pedido: lo agrega como tarea
    telar equipo rechazar ID [--nota "…"]          cerrarla; la nota la ve quien la hizo
    telar equipo revisando ID [--quien gestion]    anotar que alguien la está revisando (tu lista lo muestra)
    telar equipo existe ID --tarea T123            un pedido que ya existe: quien lo hizo recibe el estado de esa tarea
    telar equipo token PERSONA                     un token nuevo para pegar en `[equipo.personas]`

La página y su API (telar.api_equipo) son otra app y otro puerto que los tuyos, a propósito: el panel y tu
API pueden escribirles a tus agentes; esta no tiene esa fuerza. Las sirve `telar serve --equipo` (o sola,
`telar equipo servir`). Con el token de una persona solo se puede: leer las tareas
marcadas para el equipo (sin su cuerpo), dejar una sugerencia de prioridad, **pedirte una tarea nueva**
y ver cómo salió. Cada una avisa al laptop con una notificación. Ver `telar.equipo`.
"""

from __future__ import annotations

import secrets
import shlex
import shutil
import subprocess

from telar import equipo as mod_equipo
from telar.ordenes import _comun


def ip_de_tailscale() -> str:
    """La IPv4 de esta máquina en Tailscale, o «» si no hay."""
    if not shutil.which("tailscale"):
        return ""
    r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True)
    return r.stdout.split()[0] if r.returncode == 0 and r.stdout.split() else ""

AYUDA = "Que una persona de confianza vea tus tareas del equipo y te sugiera prioridades."



def _cuadro(r: dict) -> str:
    if r.get("tipo") == "tarea":
        parecidas = "".join(f"\n      ¿ya existe? {t['id']} «{t['titulo'][:60]}» ({t['estado']})" for t in r.get("similares") or [])
        return (f"{r['id']}  {r['persona']} pide: {r['titulo'][:80]}" + (f" (para el {r['vence']})" if r.get("vence") else "")
                + (f"\n      «{r['motivo']}»" if r["motivo"] else "") + f"  [{r['estado']}]" + parecidas)
    pri = "?" if r["prioridad"] is None else f"P{r['prioridad']}"
    return f"{r['id']}  {r['persona']} · {r['tarea']} ({pri}) {r['titulo'][:60]}\n      «{r['motivo']}»  [{r['estado']}]"


def _por_ssh(ctx, remoto: str, argv: list[str]) -> tuple[str, str]:
    elegido = next((r for r in ctx.config.remotos if r.nombre == remoto), None)
    if elegido is None:
        return "", f"no hay remoto «{remoto}»"
    # `bash -lc`: un ssh sin terminal no trae ~/.local/bin, donde viven telar y uv, en el PATH
    comando = shlex.join(["bash", "-lc", shlex.join(["telar", "equipo", *argv])])
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", elegido.destino, comando],
                           capture_output=True, text=True, timeout=40)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", f"no pude hablar con {elegido.destino}: {e}"
    return r.stdout, "" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip() or f"ssh salió con {r.returncode}")[-300:]


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("equipo", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", choices=("servir", "sugerencias", "aceptar", "rechazar", "existe", "revisando", "token"))
    p.add_argument("valor", nargs="?", default="", help="aceptar/rechazar: el id · token: la persona")
    p.add_argument("--host", default="", help="servir: la IP donde escuchar (por defecto, la de Tailscale)")
    p.add_argument("--puerto", type=int, default=0, help="servir: el puerto (por defecto, [equipo] puerto)")
    p.add_argument("--todas", action="store_true", help="sugerencias: también las ya resueltas")
    p.add_argument("--nota", default="", help="aceptar/rechazar/existe: lo que ve quien la hizo")
    p.add_argument("--quien", default="gestion", help="revisando: quién la revisa")
    p.add_argument("--tarea", default="", help="existe: el número de la tarea que ya existe (T123)")
    p.add_argument("--remoto", default="", help="leer o decidir en otra máquina de [remotos], por ssh")
    p.add_argument("--json", action="store_true", help="los datos, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    if o.verbo == "token":
        if not o.valor:
            return _comun.queja("¿de quién? telar equipo token ramiro")
        print(f'{o.valor.lower()} = "{secrets.token_urlsafe(24)}"   # pégalo en [equipo.personas]')
        return 0
    if o.remoto and o.verbo != "servir":
        from telar import bus as mod_bus

        if mod_bus.hay_bus(ctx.config):
            from telar.servicios import ErrorDeServicio
            from telar.servicios import equipo as servicio

            try:
                if o.verbo == "sugerencias":
                    r = servicio.bandeja(ctx, todas=o.todas, maquina=o.remoto).model_dump(mode="json")
                elif o.verbo == "revisando":
                    r = servicio.revisando(ctx, o.valor, quien=o.quien, maquina=o.remoto).model_dump(mode="json")
                else:
                    r = servicio.decidir(ctx, o.valor, o.verbo, nota=o.nota, tarea=o.tarea, maquina=o.remoto).model_dump(mode="json")
            except ErrorDeServicio as e:
                if e.codigo != 502:
                    return _comun.queja(str(e))
                r = None  # el bus no respondió: por ssh, como antes
            if r is not None:
                if o.json:
                    return _comun.escribir_json(r)
                if "sugerencias" in r:
                    print("\n".join(_cuadro(x) for x in r["sugerencias"]) or "ninguna sugerencia pendiente")
                else:
                    print(f"{r['sugerencia']['id']}: {r['sugerencia']['estado']}")
                return 0
    if o.remoto:
        if o.verbo == "servir":
            return _comun.queja("servir corre en la máquina donde viven las tareas, no por ssh")
        sub = [o.verbo, *([o.valor] if o.valor else []), *(["--todas"] if o.todas else []),
               *(["--nota", o.nota] if o.nota else []), *(["--tarea", o.tarea] if o.tarea else []),
               *(["--quien", o.quien] if o.verbo == "revisando" else []),
               *(["--json"] if o.json else [])]
        salida, problema = _por_ssh(ctx, o.remoto, sub)
        if problema:
            return _comun.queja(problema)
        print(salida, end="")
        return 0
    try:
        eq = mod_equipo.cargar()
    except ValueError as e:
        return _comun.queja(str(e))
    if o.verbo == "servir":
        if not eq.personas:
            return _comun.queja("no hay nadie en [equipo.personas]: `telar equipo token ramiro` da una llave")
        try:
            import uvicorn

            from telar import api_equipo
        except ImportError as e:
            return _comun.queja(f"falta el extra «serve» ({e.name}): pip install 'telar[serve]'")
        host = o.host or ip_de_tailscale() or "127.0.0.1"
        puerto = o.puerto or eq.puerto
        print(f"telar equipo en http://{host}:{puerto}  ·  {', '.join(sorted(eq.personas))}  ·  solo lee tareas «{eq.etiqueta}» y recibe sugerencias", flush=True)
        uvicorn.run(api_equipo.crear(eq), host=host, port=puerto, log_level="warning")
        return 0
    if o.verbo == "sugerencias":
        registros = [r for r in mod_equipo.leer_bandeja(eq) if o.todas or r["estado"] == "pendiente"]
        if o.json:
            return _comun.escribir_json({"sugerencias": registros})
        print("\n".join(_cuadro(r) for r in registros) or "ninguna sugerencia pendiente")
        return 0
    if not o.valor:
        return _comun.queja(f"¿cuál? telar equipo {o.verbo} ID")
    if o.verbo == "revisando":
        r, problema = mod_equipo.marcar_revision(eq, o.valor, o.quien)
        if r is None:
            return _comun.queja(problema)
        return _comun.escribir_json({"sugerencia": r}) if o.json else (print(f"{r['id']}: la revisa {o.quien}") or 0)
    r, problema = mod_equipo.resolver(eq, o.valor, o.verbo, o.nota, o.tarea)
    if r is None:
        return _comun.queja(problema)
    if o.json:
        return _comun.escribir_json({"sugerencia": r})
    print(f"{r['id']}: {r['estado']}" + (f" (ahora P{r['prioridad_nueva']})" if "prioridad_nueva" in r else "")
          + (f" como {r['tarea']}" if r.get("tipo") == "tarea" and r["estado"] == "aceptada" and r.get("tarea") else ""))
    return 0
