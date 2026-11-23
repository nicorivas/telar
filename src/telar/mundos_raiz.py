"""Cuándo rige cada mundo, en la raíz, para todas las máquinas: el horario de cada uno y `fuera` (`<raiz>/.telar/mundos.toml`,
docs/configuracion.md, «[mundos]»).

    # <raiz>/.telar/mundos.toml
    [mundos]
    fuera = "personal"

    [mundos.trabajo]
    horario = "lun-vie 9:00-19:00"

    from telar import mundos_raiz
    mundos_raiz.cambiar(config, "trabajo", {"horario": ["lun-vie 9:00-13:00", "lun-vie 14:00-19:00"]})   # a la raíz
    mundos_raiz.cambiar_fuera(config, "personal")
    mundos_raiz.migrar(config, ver=True)                  # qué pasaría con `telar mundos migrar`

Qué mundo rige ahora no depende de la máquina: si el horario se cambia en el teléfono (el servidor), el laptop tiene que
regir igual. Por eso el horario y `fuera` van en la raíz, con la misma forma que en la configuración y nada más, y se leen
con ella: sin horario < la raíz < la configuración de la máquina, que pisa mundo por mundo (un `horario` en
`[mundos.<n>]` de la máquina, aunque sea `[]`, tapa el de la raíz para ese mundo; un `fuera` en `[mundos]`, el de la raíz),
solo en esa máquina (`juntar`). Lo demás de un mundo (sus rutas, áreas, etiquetas, color, tema y modos) sigue en la
configuración de cada máquina: las rutas son de la máquina (`~/worktrees/`), y el resto no decide qué rige.

Un mundo de la raíz que esta máquina no declara no se aplica (ni se inventa: un mundo sin sus rutas no sirve), y un `fuera`
que no es de los suyos, tampoco: se anota en `mundos_sobran` y doctor lo dice. Un archivo de la raíz que no se lee (un TOML
roto, un choque de git a medio resolver, un horario que no se entiende) no se aplica ni se escribe encima.

⚙ mundos escribe aquí (`cambiar`, `cambiar_fuera`): el horario pasa a la raíz y sale de la máquina, si estaba, para que se
vea; vacío, sale de los dos. Antes de escribir, el horario se lee como lo lee la configuración y se mira contra los de
los otros mundos: si dos se pisan, a esa hora no rige ninguno (rige el de `fuera`), y eso nunca es lo que se quiso: no se
escribe, y el error dice dónde (telar.horario.choques). Lo escrito se commitea solo, ese archivo y nada más, y se sube
(`subir_luego`, como los temas: telar.temas.subir). Sin `raiz` no hay raíz: todo queda en la máquina, como antes.
`migrar` pasa los horarios y `fuera` de la configuración de una máquina a la raíz, con respaldo, sin cambiar lo que rige.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["ARCHIVO", "archivo_de", "leer_raiz", "juntar", "cambiar", "cambiar_fuera", "migrar", "subir", "subir_luego",
           "atrasado", "choques_de"]

#: el horario de los mundos en la raíz, relativo a ella: vale en todas las máquinas que comparten esa raíz por git
ARCHIVO = Path(".telar") / "mundos.toml"
#: la cabeza de ese archivo, cuando ⚙ mundos lo crea
CABEZA = """# Cuándo rige cada mundo de telar, en todas las máquinas de esta raíz: el horario de cada uno y el que rige fuera de
# todo horario (docs/configuracion.md, «[mundos]»). Lo escribe ⚙ mundos, que lo commitea y lo sube solo.
# Lo demás de un mundo (rutas, áreas, etiquetas, color, tema, modos) va en la configuración de cada máquina; lo que diga
# allá `horario` o `fuera` pisa esto, solo en esa máquina.
"""
#: el mensaje del commit de lo que escribe ⚙ mundos
MENSAJE = "mundos: el horario cambiado en ⚙ mundos ({maquina})"


def archivo_de(datos: dict, origen=None) -> Path | None:
    """`<raiz>/.telar/mundos.toml` según esa configuración ya parseada (la raíz de `TELAR_RAIZ` o de `raiz`); None sin
    raíz, o si `origen` es ese mismo archivo."""
    from telar import temas

    return temas.archivo_de(datos, origen, nombre=ARCHIVO)


def _validar(datos: dict) -> dict:
    """El TOML de la raíz ya parseado → {"fuera": str | None, "horarios": {mundo: lo escrito}}. ErrorDeConfig si no sirve."""
    from telar import horario as mod_horario
    from telar.config import ErrorDeConfig

    sobra = sorted(set(datos) - {"mundos"})
    if sobra:
        raise ErrorDeConfig(f"solo lleva [mundos] y tablas [mundos.<nombre>] con su horario; sobra «{sobra[0]}»")
    tabla = datos.get("mundos", {})
    if not isinstance(tabla, dict):
        raise ErrorDeConfig("se esperaban [mundos] y tablas [mundos.<nombre>]")
    fuera = tabla.get("fuera")
    if fuera is not None and not isinstance(fuera, str):
        raise ErrorDeConfig(f"mundos.fuera: el nombre de un mundo; llegó {fuera!r}")
    horarios = {}
    for nombre, cuerpo in tabla.items():
        if nombre == "fuera":
            continue
        if not isinstance(cuerpo, dict):
            raise ErrorDeConfig(f"mundos.{nombre}: no existe (fuera, o una tabla [mundos.<nombre>])")
        sobra = sorted(set(cuerpo) - {"horario"})
        if sobra:
            raise ErrorDeConfig(f"mundos.{nombre}.{sobra[0]}: en la raíz un mundo dice solo su horario; lo demás es de la "
                                "configuración de cada máquina")
        if "horario" not in cuerpo:
            continue
        try:
            mod_horario.leer_horario(cuerpo["horario"])
        except ValueError as e:
            raise ErrorDeConfig(f"mundos.{nombre}.horario: {e}") from None
        horarios[nombre] = cuerpo["horario"]
    return {"fuera": fuera.strip() if isinstance(fuera, str) else None, "horarios": horarios}


def leer_raiz(archivo: Path | None) -> tuple[dict, str]:
    """Lo de la raíz (`_validar`) y ""; o vacío y por qué no se pudo leer: telar sigue sin ello, y doctor lo dice."""
    import tomllib

    from telar.config import ErrorDeConfig

    vacio = {"fuera": None, "horarios": {}}
    if archivo is None or not archivo.exists():
        return vacio, ""
    try:
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        return vacio, f"{archivo}: no se lee ({e})"
    try:
        return _validar(datos), ""
    except ErrorDeConfig as e:
        return vacio, f"{archivo}: {e}"


def juntar(tabla: dict, de_raiz: dict) -> tuple[dict, dict, tuple[str, ...]]:
    """`[mundos]` de la máquina con lo de la raíz debajo: el horario de la raíz de cada mundo que la máquina declara y no dice el
    suyo, y `fuera` de la raíz si la máquina no dice el suyo y es uno de sus mundos. Devuelve la tabla junta, de dónde sale
    cada cosa ({"horario": {mundo: "raiz" | "maquina"}, "fuera": …}) y lo de la raíz que no se aplica."""
    salida = dict(tabla)
    nombres = [k for k, v in tabla.items() if isinstance(v, dict)]
    donde: dict = {"horario": {}, "fuera": ""}
    sobran: list[str] = []
    horarios = (de_raiz or {}).get("horarios") or {}
    for n in nombres:
        if "horario" in tabla[n]:
            donde["horario"][n] = "maquina"
        elif n in horarios:
            salida[n] = {**tabla[n], "horario": horarios[n]}
            donde["horario"][n] = "raiz"
    sobran += [f"el horario de «{n}» (esta máquina no declara [mundos.{n}])" for n in horarios if n not in nombres]
    fuera = (de_raiz or {}).get("fuera")
    if "fuera" in tabla:
        donde["fuera"] = "maquina"
    elif fuera is not None:
        if not fuera or fuera in nombres:
            salida["fuera"] = fuera
            donde["fuera"] = "raiz"
        else:
            sobran.append(f"fuera = «{fuera}» (esta máquina no declara [mundos.{fuera}])")
    return salida, donde, tuple(sobran)


def choques_de(config, nombre: str = "", tramos=None) -> list[dict]:
    """Dónde se pisan los horarios de los mundos de esa configuración (telar.horario.choques); con `nombre` y `tramos`, con
    ese horario en vez del suyo, y solo los choques de ese."""
    from telar import horario as mod_horario

    por_mundo = {m.nombre: m.horario for m in getattr(config, "mundos", ()) or ()}
    if nombre:
        # el que se edita, primero: el choque se dice desde él
        por_mundo = {nombre: tuple(tramos or ()), **{k: v for k, v in por_mundo.items() if k != nombre}}
    salida = mod_horario.choques(por_mundo)
    return [c for c in salida if nombre in c["mundos"]] if nombre else salida


# ── lo que escribe ⚙ mundos: a la raíz (y fuera de la máquina lo que lo taparía) ──────────────────────────────────────


def _maquina(config) -> Path:
    from telar import mundos

    return mundos._destino(getattr(config, "origen", None))


def _archivo_raiz(config) -> Path | None:
    """El archivo de la raíz donde escribir, o None si no hay (sin `raiz`). ErrorDeConfig si está pero no se lee: no se
    escribe encima de un archivo roto."""
    from telar.config import ErrorDeConfig

    archivo_raiz = getattr(config, "mundos_archivo", None)
    if archivo_raiz is not None and getattr(config, "mundos_error", ""):
        raise ErrorDeConfig(f"no escribí nada: {config.mundos_error}")
    return archivo_raiz


def _revisar(antes: str, nuevo: str, destino: Path) -> None:
    """Que lo que se va a escribir en el archivo de la raíz se siga leyendo como tal."""
    import tomllib

    from telar.config import ErrorDeConfig

    try:
        _validar(tomllib.loads(nuevo))
    except (tomllib.TOMLDecodeError, ErrorDeConfig) as e:
        raise ErrorDeConfig(f"no escribí nada: {destino} no se podría leer ({e})") from e


def _escribir(archivo_raiz: Path, tabla: str, clave: str, valor) -> None:
    """Una línea del archivo de la raíz (None la quita); si una tabla de un mundo queda vacía, se quita."""
    import re

    from telar import config as mod_config

    if not archivo_raiz.exists():
        if valor is None:
            return
        archivo_raiz.parent.mkdir(parents=True, exist_ok=True)
        archivo_raiz.write_text(CABEZA, encoding="utf-8")
    mod_config.escribir_clave(tabla, clave, valor, archivo_raiz, revisar=_revisar)
    if valor is None and tabla != "mundos":
        renglones = archivo_raiz.read_text(encoding="utf-8").splitlines()
        cabeza = f"[{tabla}]"
        i = next((n for n, r in enumerate(renglones) if r.strip() == cabeza), -1)
        if i < 0:
            return
        fin = next((n for n in range(i + 1, len(renglones)) if renglones[n].strip().startswith("[")), len(renglones))
        if any(r.strip() and not r.lstrip().startswith("#") for r in renglones[i + 1:fin]):
            return
        del renglones[i:fin]
        texto = re.sub(r"\n{3,}", "\n\n", "\n".join(renglones).rstrip("\n") + "\n")
        archivo_raiz.write_text(texto, encoding="utf-8")


def _de_raiz(archivo_raiz: Path) -> dict:
    return leer_raiz(archivo_raiz)[0] if archivo_raiz.exists() else {"fuera": None, "horarios": {}}


def cambiar(config, nombre: str, valores: dict) -> dict:
    """Lo que hace `PATCH /mundos/<n>`: el horario, revisado (que se lea y que no se pise con el de otro mundo), a la raíz, y
    fuera de la máquina si estaba; vacío (o None), fuera de los dos. Lo demás (color, tema, arte, modos, etiquetas, áreas,
    rutas), a la configuración de la máquina (telar.mundos.ajustar). Sin raíz, todo a la máquina, también el horario
    (revisado igual). Todo se revisa antes de escribir nada. Devuelve lo escrito. KeyError si no hay ese mundo;
    ErrorDeConfig si algo no sirve."""
    from telar import config as mod_config
    from telar import horario as mod_horario
    from telar import mundos

    maquina = _maquina(config)
    if "horario" not in valores:
        return mundos.ajustar(maquina, nombre, valores)
    leidos = mundos._leidos(maquina)
    if not isinstance(leidos.get(nombre), dict):
        raise KeyError(nombre)
    archivo_raiz = _archivo_raiz(config)
    valor = mundos._valor(nombre, "horario", valores["horario"])
    try:
        tramos = mod_horario.leer_horario(valor)
    except ValueError as e:
        raise mod_config.ErrorDeConfig(f"mundos.{nombre}.horario: {e}") from None
    pisan = choques_de(config, nombre, tramos)
    if pisan:
        mas = f" (y {len(pisan) - 1} más)" if len(pisan) > 1 else ""
        raise mod_config.ErrorDeConfig(f"mundos.{nombre}.horario: {mod_horario.decir_choque(pisan[0])}{mas}: a esa hora no "
                                       "regiría ninguno de los dos. Acorta uno de los dos")
    if archivo_raiz is None:
        return mundos.ajustar(maquina, nombre, valores)
    resto = {k: v for k, v in valores.items() if k != "horario"}
    escrito = mundos.ajustar(maquina, nombre, resto) if resto else {}
    tabla = mundos._tabla_de(nombre)
    if valor is not None or nombre in _de_raiz(archivo_raiz)["horarios"]:
        _escribir(archivo_raiz, tabla, "horario", valor)
    if "horario" in leidos[nombre]:
        mod_config.escribir_clave(tabla, "horario", None, maquina)
    return {**escrito, "horario": valor}


def cambiar_fuera(config, valor: str) -> str:
    """`[mundos] fuera` (el que rige fuera de todo horario; vacío, ambos), en la raíz, y fuera de la máquina si estaba. Sin
    raíz, en la máquina (telar.mundos.poner_fuera). Devuelve lo escrito. ErrorDeConfig si no es uno de los declarados."""
    from telar import config as mod_config
    from telar import mundos

    maquina = _maquina(config)
    archivo_raiz = _archivo_raiz(config)
    if archivo_raiz is None:
        return mundos.poner_fuera(maquina, valor)
    valor = str(valor or "").strip()
    leidos = mundos._leidos(maquina)
    nombres = [k for k, v in leidos.items() if isinstance(v, dict)]
    if valor and valor not in nombres:
        raise mod_config.ErrorDeConfig(f"mundos.fuera: el nombre de uno de los mundos declarados "
                                       f"({', '.join(nombres) or 'no hay'}); llegó {valor!r}")
    if valor or _de_raiz(archivo_raiz)["fuera"] is not None:
        _escribir(archivo_raiz, "mundos", "fuera", valor or None)
    if "fuera" in leidos:
        mod_config.escribir_clave("mundos", "fuera", None, maquina)
    return valor


# ── la migración: el horario y `fuera` de la configuración de una máquina, a la raíz ─────────────────────────────────


def _mismo_horario(a, b) -> bool:
    from telar import horario as mod_horario

    def forma(v):
        return sorted((t.dias, t.desde, t.hasta) for t in mod_horario.leer_horario(v))

    try:
        return forma(a) == forma(b)
    except ValueError:
        return False


def _lo_que_rige(config) -> tuple:
    return (tuple((m.nombre, tuple((t.dias, t.desde, t.hasta) for t in m.horario)) for m in config.mundos),
            config.mundos_fuera)


def migrar(config, *, ver: bool = False, ahora=None) -> dict:
    """Pasa el horario de cada mundo y `fuera` de la configuración de esta máquina a la raíz sin cambiar lo que rige. Cada uno:
    si la raíz no lo dice, pasa; si dice lo mismo (los mismos días y horas, aunque escritos de otra forma), sale de la
    máquina; si dice otro, se queda en la máquina, que lo sigue pisando (`quedan`, con lo que dice la raíz: nada se pierde).
    Antes de escribir, un respaldo de la configuración al lado (`config.toml.antes-de-mundos-en-raiz-AAAAMMDD-HHMMSS`);
    después, si la configuración no queda rigiendo igual, lo devuelve todo como estaba y es un error. Con `ver`, solo dice
    qué haría. ErrorDeConfig si no hay raíz (sin `raiz`) o no se lee."""
    import datetime as dt
    import shutil

    from telar import config as mod_config
    from telar import mundos

    archivo_raiz = _archivo_raiz(config)
    if archivo_raiz is None:
        raise mod_config.ErrorDeConfig("la configuración no dice `raiz`: no hay raíz adonde llevar los horarios")
    maquina = _maquina(config)
    aqui = mundos._leidos(maquina)
    alla = _de_raiz(archivo_raiz)
    pasan: list[dict] = []
    iguales: list[dict] = []
    quedan: list[dict] = []
    for nombre, cuerpo in aqui.items():
        if not isinstance(cuerpo, dict) or "horario" not in cuerpo:
            continue
        v = cuerpo["horario"]
        if nombre not in alla["horarios"]:
            pasan.append({"mundo": nombre, "clave": "horario", "valor": v})
        elif _mismo_horario(v, alla["horarios"][nombre]):
            iguales.append({"mundo": nombre, "clave": "horario", "valor": v})
        else:
            quedan.append({"mundo": nombre, "clave": "horario", "aqui": v, "raiz": alla["horarios"][nombre]})
    if isinstance(aqui.get("fuera"), str):
        v = aqui["fuera"]
        if alla["fuera"] is None:
            pasan.append({"mundo": "", "clave": "fuera", "valor": v})
        elif alla["fuera"] == v:
            iguales.append({"mundo": "", "clave": "fuera", "valor": v})
        else:
            quedan.append({"mundo": "", "clave": "fuera", "aqui": v, "raiz": alla["fuera"]})
    plan = {"raiz": str(archivo_raiz), "maquina": str(maquina), "pasan": pasan, "iguales": iguales, "quedan": quedan,
            "respaldo": "", "escrito": False}
    if ver or not (pasan or iguales):
        return plan

    antes = _lo_que_rige(mod_config.cargar(maquina))
    marca = (ahora or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
    respaldo = maquina.with_name(f"{maquina.name}.antes-de-mundos-en-raiz-{marca}")
    shutil.copy2(maquina, respaldo)
    plan["respaldo"] = str(respaldo)
    texto_raiz = archivo_raiz.read_text(encoding="utf-8") if archivo_raiz.exists() else None
    try:
        # primero a la raíz (mientras, la máquina lo sigue diciendo y lo tapa), y después fuera de la máquina
        for p in pasan:
            tabla = "mundos" if p["clave"] == "fuera" else mundos._tabla_de(p["mundo"])
            _escribir(archivo_raiz, tabla, p["clave"], p["valor"])
        for p in (*pasan, *iguales):
            tabla = "mundos" if p["clave"] == "fuera" else mundos._tabla_de(p["mundo"])
            mod_config.escribir_clave(tabla, p["clave"], None, maquina)
        despues = _lo_que_rige(mod_config.cargar(maquina))
        if despues != antes:
            raise mod_config.ErrorDeConfig(f"la configuración no quedó rigiendo igual ({antes} → {despues})")
    except Exception:
        shutil.copy2(respaldo, maquina)
        if texto_raiz is None:
            archivo_raiz.unlink(missing_ok=True)
        else:
            archivo_raiz.write_text(texto_raiz, encoding="utf-8")
        raise
    plan["escrito"] = True
    return plan


# ── que llegue a las otras máquinas: commitear ese archivo, solo ese, y subirlo (como los temas) ──────────────────


def subir(archivo_raiz: Path, *, estado: Path | None = None, empujar: bool = True, mensaje: str = ""):
    """Commitea el archivo de la raíz (solo ese) y, con `empujar`, lo sube (telar.temas.subir)."""
    import socket

    from telar import temas

    return temas.subir(archivo_raiz, estado=estado, empujar=empujar,
                       mensaje=mensaje or MENSAJE.format(maquina=socket.gethostname().split(".")[0]))


def subir_luego(config, **kw) -> None:
    """Después de una escritura de ⚙ mundos: commitear y subir el archivo de la raíz al rato (telar.temas.subir_luego)."""
    import socket

    from telar import temas

    archivo_raiz = getattr(config, "mundos_archivo", None)
    if archivo_raiz is None:
        return
    temas.subir_luego(config, archivo=archivo_raiz, mensaje=MENSAJE.format(maquina=socket.gethostname().split(".")[0]), **kw)


def atrasado(archivo_raiz: Path) -> str:
    """Si el archivo de la raíz de esta máquina no es el último de arriba (telar.temas.atrasado)."""
    from telar import temas

    return temas.atrasado(archivo_raiz)
