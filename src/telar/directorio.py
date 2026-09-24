"""El directorio: los hilos remotos de cada persona de una máquina compartida.

En el servidor, el tmux y los registros de Claude Code son de cada usuario: nadie ve las
sesiones de los otros. Para que un agente sepa a quién escribirle, cada telar publica sus
hilos de esa máquina en una carpeta común (`[remotos.<n>] directorio`), un archivo por
persona, `<usuario>.json`:

    {"usuario": "ana", "maquina": "casa", "actualizado": "2026-09-24T17:40:00",
     "hilos": [{"nombre": "Faro", "direccion": "ana+faro@casa",
                "vinculo": "proyectos/faro", "resumen": "Faro: el título de su documento"}]}

La carpeta es del grupo de las personas, con el bit sticky: cada una escribe el suyo y nadie
puede borrar ni reemplazar el de otra. Al leer, un archivo cuyo dueño no es el usuario de su
nombre se descarta: nadie publica en nombre de otro.

El resumen es el **título** del documento del hilo, no su estado: el directorio lo lee todo
el servidor, y el estado de un proyecto suele traer lo que no se cuenta afuera.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime

from telar.config import Remoto

ESPERA = 20

#: lo que corre allá para leer: cada archivo con su dueño real, para descartar suplantaciones.
LEER = r'''
import glob, json, os, pwd, sys
salida = []
for ruta in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    nombre = os.path.basename(ruta)[:-5]
    try:
        dueno = pwd.getpwuid(os.stat(ruta).st_uid).pw_name
        datos = json.load(open(ruta, encoding="utf-8"))
    except Exception as e:
        salida.append({"usuario": nombre, "error": str(e)[:200]}); continue
    if dueno != nombre or datos.get("usuario") != nombre:
        salida.append({"usuario": nombre, "error": f"el archivo es de {dueno}: se descarta"}); continue
    salida.append(datos)
print(json.dumps(salida))
'''


def entrada(ctx, tel, remoto: Remoto, usuario: str, maquina: str) -> dict:
    """Lo que esta persona publica de sus hilos en esa máquina (los no archivados)."""
    from telar import correo as mod_correo
    from telar import lectura

    est = tel.estado
    vinculos = est.vinculos()
    archivados = set(est.archivados())
    hilos = []
    for nombre, dato in sorted(est.remotos().items()):
        if dato.get("remoto") != remoto.nombre or nombre in archivados:
            continue
        vinculo = vinculos.get(nombre, "")
        resumen = ""
        if vinculo and not vinculo.startswith("/"):
            try:
                arquetipo, ficha = lectura.ficha_de(ctx.perfil, ctx.config.raiz, vinculo)
                if ficha is not None:
                    resumen = (lectura.etiqueta(arquetipo.etiqueta, ficha) if arquetipo else "") or ficha.titulo
            except Exception:  # noqa: BLE001 - un perfil roto no impide publicar el nombre
                resumen = ""
        hilos.append({"nombre": nombre, "direccion": mod_correo.direccion(remoto, nombre),
                      "vinculo": "" if vinculo.startswith("/") else vinculo, "resumen": resumen})
    return {"usuario": usuario, "maquina": maquina,
            "actualizado": datetime.now().isoformat(timespec="seconds"), "hilos": hilos}


def publicar(ctx, tel, remoto: Remoto) -> str:
    """Escribe el archivo de esta persona en el directorio de esa máquina. "" si salió bien.

    Se escribe a un temporal en la misma carpeta y se renombra: quien lea nunca ve medio
    archivo. El usuario y el nombre corto de la máquina los dice la máquina misma.
    """
    if not remoto.directorio:
        return "sin directorio declarado"
    usuario, _, servidor = remoto.destino.rpartition("@")
    if not usuario:
        return "el destino no dice el usuario (un alias de ssh): no sé con qué nombre publicar"
    datos = entrada(ctx, tel, remoto, usuario, servidor.split(".")[0])
    d = shlex.quote(remoto.directorio)
    guion = (f"umask 027; u=$(id -un); t=$(mktemp -p {d} .telar.XXXXXX) && cat > \"$t\" "
             f"&& chmod 640 \"$t\" && mv -f \"$t\" {d}/\"$u\".json")
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino, guion],
                           input=json.dumps(datos, ensure_ascii=False), capture_output=True, text=True,
                           timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{remoto.destino} no responde: {e}"
    return "" if r.returncode == 0 else (r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:]


def publicar_callado(ctx, tel, remoto_nombre: str) -> None:
    """Publicar después de crear, renombrar, archivar o cerrar un hilo remoto: sin ruido.

    Si falla, el directorio queda un poco viejo hasta la próxima vez; eso no puede frenar
    lo que se estaba haciendo."""
    remoto = next((r for r in ctx.config.remotos if r.nombre == remoto_nombre), None)
    if remoto is not None and remoto.directorio:
        try:
            publicar(ctx, tel, remoto)
        except Exception:  # noqa: BLE001
            pass


def leer(remoto: Remoto) -> tuple[list[dict], str]:
    """Las entradas de todas las personas en el directorio de esa máquina, y un error o ""."""
    if not remoto.directorio:
        return [], "sin directorio declarado"
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino,
             shlex.join(["python3", "-c", LEER, remoto.directorio])]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=ESPERA)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], f"{remoto.destino} no responde: {e}"
    if r.returncode != 0:
        return [], (r.stderr.strip() or f"ssh salió con {r.returncode}")[-300:]
    try:
        return json.loads(r.stdout), ""
    except ValueError:
        return [], "el servidor no devolvió JSON"
