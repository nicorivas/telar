"""Personas de un servidor: quién entra, con qué permisos, y el plan para dejarlo así.

Una persona es un usuario Linux con un perfil. El perfil es un conjunto de capacidades
(shell, correo hacia ciertos hilos, tope de recursos). Aquí no se ejecuta nada: `plan()` convierte
una persona en una lista de acciones, cada una con el texto que la explica y las líneas de shell
que la hacen. Quien las corre (`telar persona crear`) puede mostrarlas (`--seco`), ejecutarlas si
es root, o entregarlas como un guion para que la persona dueña del servidor las corra con sudo.

La seguridad no vive en telar: vive en lo que el sistema ya hace cumplir (usuarios, sshd, systemd,
permisos de archivo). Telar solo declara y concilia, igual que `telar periodicos aplicar`. Cada
acción es idempotente, y la definición de cada persona queda en `<dir>/<nombre>.toml` (por
defecto /etc/telar/personas.d), que es lo que `ver` lee y `quitar` deshace.
"""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DIRECTORIO = Path("/etc/telar/personas.d")
REPOSITORIO = "git+https://github.com/nicorivas/telar"

NOMBRE = re.compile(r"[a-z][a-z0-9_-]{1,30}")
HILO = re.compile(r"[a-z0-9][a-z0-9_-]*")
LLAVE = re.compile(r"ssh-(ed25519|rsa) [A-Za-z0-9+/=]+( [^\n]*)?")
TOPE = re.compile(r"[1-9][0-9]*[KMG]")
CPU = re.compile(r"[1-9][0-9]*%")


class ErrorDePersona(ValueError):
    """Los datos de la persona no sirven."""


#: Lo que cada perfil da. Los perfiles son punto de partida: cada valor se puede cambiar al crear.
PERFILES: dict[str, dict] = {
    "colega": {
        "descripcion": "shell por ssh con su propio telar y Claude Code; despierta solo a los hilos que se le dicen",
        # ninguno por defecto: los hilos que puede despertar se dicen al crearla (--correo)
        "correo": [],
        "memoria": "2500M",
        "cpu": "100%",
    },
}


@dataclass(frozen=True, slots=True)
class Persona:
    nombre: str
    perfil: str
    llave: str
    dueno: str                      # a quién pertenecen los agentes que esta persona puede despertar
    correo: tuple[str, ...] = ()
    memoria: str = "2500M"
    cpu: str = "100%"

    def a_toml(self) -> str:
        return "\n".join([
            f'perfil = "{self.perfil}"', f'dueno = "{self.dueno}"',
            f"correo = {json.dumps(list(self.correo))}",
            f'memoria = "{self.memoria}"', f'cpu = "{self.cpu}"', f'llave = "{self.llave}"', ""])


@dataclass(frozen=True, slots=True)
class Accion:
    clave: str
    texto: str
    guion: str                      # shell que la hace; idempotente
    como: str = "root"


@dataclass(slots=True)
class Plan:
    persona: str
    acciones: list[Accion] = field(default_factory=list)

    def guion(self) -> str:
        partes = ["#!/bin/bash", "# telar persona: generado, corre con sudo. Cada paso se puede repetir.", "set -euo pipefail", ""]
        for a in self.acciones:
            partes += [f"echo '== {a.texto}'", a.guion.strip(), ""]
        return "\n".join(partes)


def validar(nombre: str, perfil: str, llave: str, dueno: str, correo: list[str], memoria: str, cpu: str) -> Persona:
    if not NOMBRE.fullmatch(nombre):
        raise ErrorDePersona(f"«{nombre}»: el nombre va en minúsculas, sin espacios (2 a 31 letras, cifras, - o _)")
    if perfil not in PERFILES:
        raise ErrorDePersona(f"no hay perfil «{perfil}»: {', '.join(PERFILES)}")
    if not LLAVE.fullmatch(llave.strip()):
        raise ErrorDePersona("la llave debe ser una llave pública ssh en una línea (ssh-ed25519 AAAA… comentario)")
    if not NOMBRE.fullmatch(dueno):
        raise ErrorDePersona(f"«{dueno}» no es un usuario válido")
    for h in correo:
        if not HILO.fullmatch(h):
            raise ErrorDePersona(f"«{h}» no es un nombre de hilo válido")
    if not TOPE.fullmatch(memoria):
        raise ErrorDePersona("la memoria va como 2500M o 3G")
    if not CPU.fullmatch(cpu):
        raise ErrorDePersona("la CPU va como 100% (un núcleo) o 200%")
    return Persona(nombre, perfil, llave.strip(), dueno, tuple(correo), memoria, cpu)


def _q(x: str) -> str:
    return shlex.quote(x)


def plan(p: Persona, directorio: Path = DIRECTORIO, repositorio: str = REPOSITORIO) -> Plan:
    """Lo que hay que hacer, en orden, para que `p` exista con su perfil. Nada se ejecuta aquí."""
    u = _q(p.nombre)
    hogar = f'"$(getent passwd {u} | cut -d: -f6)"'
    sshd = f"/etc/ssh/sshd_config.d/60-{p.nombre}.conf"
    rebanada = f"/etc/systemd/system/user-$(id -u {u}).slice.d"
    lista = f'"$(getent passwd {_q(p.dueno)} | cut -d: -f6)/.cartero-permitidos"'
    linea = p.nombre + (": " + ", ".join(p.correo) if p.correo else "")
    a: list[Accion] = [
        Accion("usuario", f"el usuario {p.nombre}, sin grupos extra (nada de «agentes»: da lectura al correo archivado)",
               f"""id {u} >/dev/null 2>&1 || useradd -m -s /bin/bash -c {_q(f'{p.nombre} ({p.perfil})')} {u}
if id -nG {u} | tr ' ' '\\n' | grep -qx agentes; then gpasswd -d {u} agentes; fi"""),
        Accion("llave", "su llave ssh (la única forma de entrar: sin contraseña)",
               f"""install -d -m 700 -o {u} -g {u} {hogar}/.ssh
touch {hogar}/.ssh/authorized_keys && chown {u}:{u} {hogar}/.ssh/authorized_keys && chmod 600 {hogar}/.ssh/authorized_keys
grep -qxF {_q(p.llave)} {hogar}/.ssh/authorized_keys || echo {_q(p.llave)} >> {hogar}/.ssh/authorized_keys"""),
        Accion("ssh", "sshd: sin contraseña, sin túneles ni reenvíos",
               f"""cat > {sshd} <<'EOF'
Match User {p.nombre}
    PasswordAuthentication no
    AllowTcpForwarding no
    X11Forwarding no
    AllowAgentForwarding no
    PermitTunnel no
EOF
sshd -t && systemctl reload ssh"""),
        Accion("recursos", f"tope de recursos: {p.memoria} de memoria y {p.cpu} de CPU para toda su cuenta",
               f"""install -d {rebanada}
cat > {rebanada}/50-telar-persona.conf <<'EOF'
[Slice]
MemoryHigh={p.memoria}
MemoryMax={p.memoria}
CPUQuota={p.cpu}
TasksMax=400
EOF
systemctl daemon-reload
loginctl enable-linger {u}"""),
    ]
    if p.correo:
        a.append(Accion("correo", f"puede despertar por correo solo a: {', '.join(p.correo)} (lista de {p.dueno})",
                        f"""[ -e {lista} ] || install -m 600 -o {_q(p.dueno)} -g {_q(p.dueno)} /dev/null {lista}
t=$(mktemp); {{ grep -v '^{p.nombre}\\(:\\|$\\)' {lista} || true; echo {_q(linea)}; }} > "$t"
cat "$t" > {lista}; rm -f "$t"
"""))
    a.append(Accion("instalar", "su propio uv, Claude Code y telar, con las skills de telar (no usa nada tuyo)",
                    f"""runuser -l {u} -c 'bash -s' <<'EOS'
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
command -v claude >/dev/null || curl -fsSL https://claude.ai/install.sh | bash
uv tool install --force {_q(repositorio)}
grep -q '.local/bin' "$HOME/.profile" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
telar agente instalar --si
EOS""", como="usuario"))
    a.append(Accion("definicion", f"anotar a {p.nombre} en {directorio} (lo que `telar persona ver` lee)",
                    f"""install -d -m 755 {_q(str(directorio))}
cat > {_q(str(directorio / (p.nombre + '.toml')))} <<'EOF'
{p.a_toml()}EOF"""))
    return Plan(p.nombre, a)


def plan_quitar(nombre: str, dueno: str, directorio: Path = DIRECTORIO, borrar_home: bool = False) -> Plan:
    """Cerrar el acceso. El home se conserva: lo que hizo esa persona no se borra sin pedirlo."""
    if not NOMBRE.fullmatch(nombre):
        raise ErrorDePersona(f"«{nombre}» no es un nombre válido")
    u = _q(nombre)
    lista = f'"$(getent passwd {_q(dueno)} | cut -d: -f6)/.cartero-permitidos"'
    a = [
        Accion("cerrar", "bloquear la cuenta y cerrar sus sesiones y procesos",
               f"""usermod -L -s /usr/sbin/nologin {u}
rm -f "$(getent passwd {u} | cut -d: -f6)/.ssh/authorized_keys"
loginctl terminate-user {u} 2>/dev/null || true"""),
        Accion("ssh", "quitar su regla de sshd", f"rm -f /etc/ssh/sshd_config.d/60-{nombre}.conf && sshd -t && systemctl reload ssh"),
        Accion("recursos", "quitar su tope de recursos",
               f"""rm -f /etc/systemd/system/user-$(id -u {u}).slice.d/50-telar-persona.conf
systemctl daemon-reload
loginctl disable-linger {u} 2>/dev/null || true"""),
        Accion("correo", f"sacarla de la lista de {dueno}",
               f"""if [ -f {lista} ]; then t=$(mktemp); {{ grep -v '^{nombre}\\(:\\|$\\)' {lista} || true; }} > "$t"
cat "$t" > {lista}; rm -f "$t"; fi"""),
        Accion("definicion", "borrar su definición", f"rm -f {_q(str(directorio / (nombre + '.toml')))}"),
    ]
    if borrar_home:
        a.append(Accion("home", "BORRAR su cuenta y todo lo que hay en su home", f"userdel -r {u}"))
    return Plan(nombre, a)


def leer(directorio: Path = DIRECTORIO) -> list[dict]:
    """Las personas anotadas: nombre y lo que se les dio. Una definición rota se avisa, no se esconde."""
    salida = []
    if not directorio.is_dir():
        return salida
    for f in sorted(directorio.glob("*.toml")):
        try:
            d = tomllib.loads(f.read_text(encoding="utf-8"))
            salida.append({"nombre": f.stem, **{k: v for k, v in d.items() if k != "llave"},
                           "llave": d.get("llave", "").split(" ")[-1] if d.get("llave") else ""})
        except (OSError, tomllib.TOMLDecodeError) as e:
            salida.append({"nombre": f.stem, "error": str(e)})
    return salida
