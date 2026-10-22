"""`telar persona` — quién entra a este servidor y con qué permisos.

    telar persona                          las personas dadas de alta, y el perfil de cada una
    telar persona crear ramiro --llave "ssh-ed25519 AAAA… ramiro@x"
                                           su cuenta, su ssh, su tope de recursos, su correo y su telar propio
    telar persona crear … --seco           el plan, sin escribir nada
    telar persona quitar ramiro           cerrarle el acceso (su home se conserva; --borrar-home lo borra)

Crear y quitar tocan usuarios, sshd y systemd, que son de root. Con sudo se ejecutan; sin él,
telar escribe el plan como un guion (cada paso se puede repetir) y dice cómo correrlo:
`sudo bash <guion>`. Lo que un perfil permite está en telar.persona (PERFILES); lo que cada
persona recibió, en /etc/telar/personas.d/<nombre>.toml.

Esto no abre el puerto 22 en Tailscale ni inicia la sesión de Claude de la persona: lo primero es
de quien administra la red, lo segundo es de ella (`claude login`, con su cuenta).
"""

from __future__ import annotations

import os
import pwd
import subprocess
import tempfile
from pathlib import Path

from telar import persona as mod
from telar.ordenes import _comun

AYUDA = "Las personas de este servidor: darles de alta con un perfil, verlas, cerrarles el acceso."


def _dueno() -> str:
    return os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name


def _llave(valor: str) -> str:
    """La llave pública: el texto, o la ruta de un archivo que la contiene."""
    p = Path(valor).expanduser()
    if len(valor) < 200 and p.is_file():
        return p.read_text(encoding="utf-8").strip().splitlines()[0]
    return valor


def _existe(nombre: str) -> bool:
    try:
        pwd.getpwnam(nombre)
        return True
    except KeyError:
        return False


def _correr(plan: mod.Plan, guion: str) -> int:
    """Con root, el plan se ejecuta; sin él, se deja el guion y se dice cómo correrlo."""
    if os.geteuid() == 0:
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(plan.guion())
        try:
            return subprocess.run(["bash", f.name]).returncode
        finally:
            os.unlink(f.name)
    ruta = Path(guion).expanduser() if guion else Path.home() / ".cache" / "telar" / f"persona-{plan.persona}.sh"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(plan.guion(), encoding="utf-8")
    print(f"\nEso necesita root. El guion quedó en {ruta}; revísalo y córrelo con:\n    sudo bash {ruta}")
    return 0


def main(argv: list[str], ctx) -> int:
    p = _comun.analizador("persona", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", default="ver", choices=["ver", "crear", "quitar"])
    p.add_argument("nombre", nargs="?", default="", help="la persona (su usuario en el servidor)")
    p.add_argument("--llave", default="", help="su llave pública ssh: el texto o un archivo .pub")
    p.add_argument("--perfil", default="colega", help=f"qué puede hacer ({', '.join(mod.PERFILES)})")
    p.add_argument("--correo", default=None, help="a qué hilos tuyos puede despertar por correo, separados por coma")
    p.add_argument("--memoria", default=None, help="tope de memoria de toda su cuenta (2500M, 3G)")
    p.add_argument("--cpu", default=None, help="tope de CPU (100%% es un núcleo)")
    p.add_argument("--dueno", default="", help="de quién son los agentes que puede despertar (por defecto, quien corre sudo)")
    p.add_argument("--dir", default=str(mod.DIRECTORIO), help="dónde se anotan las personas")
    p.add_argument("--guion", default="", help="sin root: dónde dejar el guion")
    p.add_argument("--seco", action="store_true", help="mostrar el plan y no hacer nada")
    p.add_argument("--borrar-home", action="store_true", help="con quitar: borrar también su cuenta y su home")
    p.add_argument("--json", action="store_true", help="con ver: la lista, en una línea")
    o, codigo = _comun.parsear(p, argv)
    if o is None:
        return codigo
    directorio = Path(o.dir)

    if o.verbo == "ver":
        personas = mod.leer(directorio)
        for x in personas:
            x["existe"] = _existe(x["nombre"])
        if o.json:
            return _comun.escribir_json({"personas": personas, "perfiles": {k: v["descripcion"] for k, v in mod.PERFILES.items()}})
        if not personas:
            print(_comun.tenue("no hay personas dadas de alta: `telar persona crear NOMBRE --llave …`"))
        for x in personas:
            if x.get("error"):
                print(f"{x['nombre']}  definición ilegible: {x['error']}")
                continue
            estado = "" if x["existe"] else _comun.tenue("  (su usuario ya no existe)")
            print(f"{x['nombre']}  {x['perfil']}  " + _comun.tenue(
                f"correo: {', '.join(x.get('correo', [])) or 'ninguno'} · {x.get('memoria')} · {x.get('cpu')}") + estado)
        return 0

    if not o.nombre:
        return _comun.queja(f"`telar persona {o.verbo}` necesita el nombre de la persona")
    dueno = o.dueno or _dueno()
    try:
        if o.verbo == "crear":
            if not o.llave:
                return _comun.queja("falta --llave (su llave pública ssh, o el archivo .pub)")
            base = mod.PERFILES.get(o.perfil, {})
            correo = base.get("correo", []) if o.correo is None else [c.strip() for c in o.correo.split(",") if c.strip()]
            persona = mod.validar(o.nombre, o.perfil, _llave(o.llave), dueno, correo,
                                  o.memoria or base.get("memoria", "2500M"), o.cpu or base.get("cpu", "100%"))
            plan = mod.plan(persona, directorio)
        else:
            plan = mod.plan_quitar(o.nombre, dueno, directorio, o.borrar_home)
    except mod.ErrorDePersona as e:
        return _comun.queja(str(e))

    for i, a in enumerate(plan.acciones, 1):
        print(f"{i}. {a.texto}")
    if o.seco:
        return 0
    if o.verbo == "quitar" and o.borrar_home:
        print(_comun.tenue("\n--borrar-home borra todo lo que esa persona tenga en su cuenta."))
    return _correr(plan, o.guion)
