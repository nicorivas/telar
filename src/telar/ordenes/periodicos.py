"""`telar periodicos` — los procesos que corren solos cada cierto tiempo: verlos, crearlos, cambiarlos.

    telar periodicos                              la lista: cuándo, qué, la próxima y la última corrida
    telar periodicos log <nombre> [--lineas N]    lo que escribió en sus últimas corridas
    telar periodicos nuevo <nombre> --cuando "0 9 * * 1-5" --comando "~/bin/resumen"
    telar periodicos nuevo <nombre> --cuando "0 */2 * * *" --mensaje "/correo" --hilo "✉ correo" [--max 2]
    telar periodicos editar <nombre> [--cuando …] [--comando …|--mensaje …] [--hilo …] [--descripcion …]
    telar periodicos pausar|activar|borrar <nombre>
    telar periodicos ahora <nombre>               correrlo ya, en segundo plano
    telar periodicos correr <nombre>              correrlo ya y esperar (lo que llama cron)
    telar periodicos aplicar                      escribir el bloque de telar en el crontab
    telar periodicos zona America/Santiago        en qué hora se leen los horarios
    telar periodicos horario "0 9 * * 1-5" [--n 3]   si se entiende, y sus próximas corridas
    telar periodicos skills [--carpeta ~/trabajo]    las skills que tiene a mano el agente allí

Al editar, `--arg` se repite (con `=` si el valor empieza con guion: `--arg=--permission-mode`),
`--sin-args` los quita todos, y `--activo si|no` pausa o activa en la misma orden.

Se definen en `periodicos.toml`, al lado de config.toml, en la máquina que los corre; ver
`telar.periodicos`. Todo cambio hecho por aquí reescribe el crontab al tiro (`aplicar`).

Con `--en <remoto>` (o `[periodicos] en = "<remoto>"` en la config de esta máquina) la orden
corre en esa máquina de [remotos], por ssh: así el laptop ve y cambia los del servidor.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from datetime import datetime

from telar import periodicos as mod
from telar.ordenes import _comun

AYUDA = "Los procesos que corren solos cada cierto tiempo: verlos, crearlos, cambiarlos."

VERBOS = ("ver", "log", "nuevo", "editar", "pausar", "activar", "borrar", "ahora", "correr", "aplicar", "zona",
          "horario", "skills")


def _analizador():
    p = _comun.analizador("periodicos", AYUDA)
    p.epilog = __doc__
    p.add_argument("verbo", nargs="?", default="ver", choices=VERBOS)
    p.add_argument("nombre", nargs="?", default="", help="el proceso (o la zona, con `zona`)")
    p.add_argument("--cuando", default=None, help="el horario, en cron: minuto hora día mes día-semana")
    p.add_argument("--comando", default=None, help="una línea de shell")
    p.add_argument("--mensaje", default=None, help="un prompt: abre un hilo con el agente")
    p.add_argument("--hilo", default=None, help="con --mensaje: el nombre del hilo")
    p.add_argument("--max", type=int, default=None, help="con --mensaje: cuántos abiertos a la vez, como mucho")
    p.add_argument("--arg", action="append", default=None, help="con --mensaje: un argumento más para el agente")
    p.add_argument("--carpeta", default=None, help="dónde corre (por defecto, el hogar)")
    p.add_argument("--descripcion", default=None, help="para qué es, en una línea")
    p.add_argument("--pausado", action="store_true", help="con nuevo: crearlo sin activarlo")
    p.add_argument("--activo", choices=("si", "no"), default=None, help="con editar: activarlo o pausarlo")
    p.add_argument("--sin-args", dest="sin_args", action="store_true", help="con editar: quitarle los argumentos")
    p.add_argument("--n", type=int, default=3, help="con horario: cuántas corridas")
    p.add_argument("--lineas", type=int, default=80, help="con log: cuántas")
    p.add_argument("--en", default=None, metavar="REMOTO", help="hacerlo en esa máquina de [remotos]; «aqui» para esta")
    p.add_argument("--json", action="store_true", help="el resultado, en una línea")
    return p


def main(argv: list[str], ctx) -> int:
    o, codigo = _comun.parsear(_analizador(), argv)
    if o is None:
        return codigo
    en = o.en if o.en is not None else ctx.config.periodicos_en
    if en and en != "aqui":
        return _en_otra(ctx, en, argv)
    try:
        return _aqui(ctx, o)
    except mod.ErrorDePeriodicos as e:
        return _comun.queja(str(e))


def _en_otra(ctx, nombre: str, argv: list[str]) -> int:
    """La misma orden, en la otra máquina. La salida (texto o JSON) llega tal cual."""
    remoto = next((r for r in ctx.config.remotos if r.nombre == nombre), None)
    if remoto is None:
        return _comun.queja(f"no hay un remoto «{nombre}» en [remotos]")
    # sin el --en de aquí (`--en X` o `--en=X`): allá va `--en aqui`, para que no rebote
    resto, saltar = [], False
    for a in argv:
        if saltar:
            saltar = False
        elif a == "--en":
            saltar = True
        elif not a.startswith("--en="):
            resto.append(a)
    linea = "PATH=$HOME/.local/bin:$PATH telar periodicos " + shlex.join([*resto, "--en", "aqui"])
    orden = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remoto.destino, "bash -lc " + shlex.quote(linea)]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return _comun.queja(f"{remoto.destino} no responde: {e}")
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode


def _telar() -> str:
    """La ruta de telar para el crontab: absoluta, porque cron no trae el PATH de nadie."""
    return shutil.which("telar") or sys.argv[0]


def _aqui(ctx, o) -> int:
    destino = mod.ruta()
    archivo = mod.leer(destino)

    if o.verbo == "ver":
        datos = mod.resumen(ctx, archivo)
        if o.json:
            return _comun.escribir_json({"maquina": _maquina(), "archivo": str(destino), "zona": archivo.zona,
                                         "procesos": datos})
        if not datos:
            print(_comun.tenue(f"no hay procesos periódicos en {destino}"))
        for d in datos:
            ult = d["ultima"]
            marca = "⏸" if not d["activo"] else ("✗" if ult.get("codigo") not in (None, 0) else "●")
            que = d["mensaje"] and f"✦ {d['mensaje']}" or d["comando"]
            print(f"{marca} {d['nombre']:<20} {d['cuando']:<18} {que}")
            detalle = [f"próxima {d['proxima'][5:16].replace('T', ' ')}" if d["proxima"] else "pausado"]
            if ult.get("inicio"):
                detalle.append(f"última {ult['inicio'][5:16].replace('T', ' ')} · {ult.get('resultado', 'corriendo')}")
            print(_comun.tenue("    " + " · ".join(detalle)))
        return 0

    if o.verbo == "horario":
        # nunca falla: dice si se entiende y, si no, por qué (el formulario lo muestra al escribir)
        try:
            h = mod.Horario(o.nombre)
            tz = mod.zona_info(archivo.zona)
            proximas, t = [], datetime.now(tz)
            for _ in range(max(1, min(o.n, 20))):
                t = h.proxima(t)
                if t is None:
                    break
                proximas.append(t.isoformat(timespec="minutes"))
            datos = {"valido": True, "cuando": h.texto, "proximas": proximas, "error": ""}
        except mod.ErrorDePeriodicos as e:
            datos = {"valido": False, "cuando": o.nombre, "proximas": [], "error": str(e)}
        if o.json:
            return _comun.escribir_json(datos)
        print("\n".join(x.replace("T", " ") for x in datos["proximas"]) if datos["valido"] else datos["error"])
        return 0 if datos["valido"] else 1

    if o.verbo == "skills":
        from pathlib import Path

        from telar import agente as mod_agente

        if not ctx.config.agente.nombre:
            return _comun.queja("no hay agente: [agente] nombre en config.toml")
        carpeta = Path(o.carpeta or "~").expanduser()
        skills = mod_agente.obtener(ctx.config.agente.nombre, ctx.config).skills(carpeta)
        lista = [{"nombre": x["nombre"], "descripcion": x.get("descripcion", ""), "origen": x.get("origen", "")} for x in skills]
        if o.json:
            return _comun.escribir_json({"carpeta": str(carpeta), "skills": lista})
        for x in lista:
            print(f"/{x['nombre']}  " + _comun.tenue(x["descripcion"][:100]))
        return 0

    if o.verbo == "log":
        _requerir(archivo, o.nombre)
        texto = mod.log(ctx.config, o.nombre, max(1, o.lineas))
        return _comun.escribir_json({"nombre": o.nombre, "log": texto}) if o.json else (print(texto) or 0)

    if o.verbo == "correr":
        p = _requerir(archivo, o.nombre)
        r = mod.correr(ctx, p)
        return _comun.escribir_json({"nombre": p.nombre, **r}) if o.json else (print(f"{p.nombre}: {r['resultado']}") or (0 if r["codigo"] == 0 else 1))

    if o.verbo == "ahora":
        p = _requerir(archivo, o.nombre)
        # suelto: quien pidió (el dashboard) no espera a que termine; lo ve en la última corrida
        subprocess.Popen([_telar(), "periodicos", "correr", p.nombre, "--en", "aqui"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return _hecho(o, f"{p.nombre}: corriendo", nombre=p.nombre)

    if o.verbo == "aplicar":
        mod.aplicar(archivo, _telar())
        activos = sum(1 for p in archivo.procesos if p.activo)
        return _hecho(o, f"crontab al día: {activos} activo(s) de {len(archivo.procesos)}")

    # lo que cambia el archivo
    if o.verbo == "zona":
        archivo.zona = o.nombre.strip()
        mod.zona_info(archivo.zona)
        hecho = f"zona: {archivo.zona or 'la de la máquina'}"
    elif o.verbo == "nuevo":
        if not o.nombre:
            return _comun.queja("¿cómo se llama? telar periodicos nuevo <nombre> --cuando … --comando …")
        if archivo.por_nombre(o.nombre):
            return _comun.queja(f"ya hay un proceso «{o.nombre}»: telar periodicos editar {o.nombre}")
        p = mod.Proceso(nombre=o.nombre, cuando=o.cuando or "", comando=o.comando or "", mensaje=o.mensaje or "",
                        hilo=o.hilo or "", max_abiertos=o.max or 1, argumentos=tuple(o.arg or ()),
                        carpeta=o.carpeta or "", descripcion=o.descripcion or "", activo=not o.pausado)
        p.validar()
        archivo.procesos.append(p)
        hecho = f"{p.nombre}: creado"
    elif o.verbo == "editar":
        _requerir(archivo, o.nombre)
        campos = {k: v for k, v in (("cuando", o.cuando), ("comando", o.comando), ("mensaje", o.mensaje),
                                     ("hilo", o.hilo), ("max_abiertos", o.max), ("argumentos", o.arg),
                                     ("carpeta", o.carpeta), ("descripcion", o.descripcion)) if v is not None}
        if o.sin_args:
            campos["argumentos"] = ()
        if o.activo is not None:
            campos["activo"] = o.activo == "si"
        if not campos:
            return _comun.queja("¿qué cambio? --cuando, --comando, --mensaje, --hilo, --max, --arg, --sin-args, --carpeta, --descripcion, --activo")
        mod.cambiar(archivo, o.nombre, **campos)
        hecho = f"{o.nombre}: cambiado ({', '.join(campos)})"
    elif o.verbo in ("pausar", "activar"):
        _requerir(archivo, o.nombre)
        mod.cambiar(archivo, o.nombre, activo=o.verbo == "activar")
        hecho = f"{o.nombre}: {'activo' if o.verbo == 'activar' else 'pausado'}"
    else:  # borrar
        p = _requerir(archivo, o.nombre)
        archivo.procesos.remove(p)
        hecho = f"{p.nombre}: borrado (el anterior queda en {destino.name}.anterior)"
    mod.escribir(destino, archivo)
    mod.aplicar(archivo, _telar())
    return _hecho(o, hecho, nombre=o.nombre)


def _requerir(archivo: mod.Archivo, nombre: str) -> mod.Proceso:
    p = archivo.por_nombre(nombre) if nombre else None
    if p is None:
        hay = ", ".join(x.nombre for x in archivo.procesos) or "ninguno"
        raise mod.ErrorDePeriodicos(f"no hay un proceso «{nombre}» (hay: {hay})")
    return p


def _hecho(o, texto: str, **extra) -> int:
    if o.json:
        return _comun.escribir_json({"ok": True, "hecho": texto, **extra})
    print(texto)
    return 0


def _maquina() -> str:
    from telar import espejo

    return espejo.nombre_de_esta_maquina()

