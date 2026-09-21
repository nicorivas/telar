"""zellij, hablado por su CLI. Probado contra 0.45.

No hay biblioteca ni socket estable: cada operación es un proceso
(`zellij -s <sesión> action <lo que sea>`), así que todo lo que telar sabe de
zellij vive en este archivo y nada de afuera lo sabe.

Apuntar por id, nunca por foco ni por posición
----------------------------------------------
Toda acción que acepte un id se manda con id: `go-to-tab-by-id`,
`close-tab-by-id`, `rename-tab -t`, `write-chars -p`, `new-pane --pane-id`. Las
acciones que siguen al foco (`rename-tab` sin `-t`, `write-chars` sin `-p`,
`close-pane`, `move-focus`) actúan sobre el tab que esté mirando quien esté
mirando, y quien mira se mueve mientras telar trabaja: basta con eso para
renombrar el hilo equivocado o cerrarle el panel a otro. Las posiciones tampoco
sirven de llave: se corren solas cuando se cierra un tab del medio. El TAB_ID es
estable mientras el tab viva.

Por eso `Hilo.id` es aquí el TAB_ID (un número, como texto) y no el nombre del
tab: es lo único que no cambia bajo los pies. Para no romper a quien tenga a mano
el nombre, todos los métodos que reciben un hilo aceptan las dos cosas —primero se
prueba como id, después como nombre— y `Hilo.nombre` sigue trayendo el nombre.
Si un tab se llama con un número que además es el id de otro, gana el id; el
nombre de ese tab queda inalcanzable, y es un buen momento para renombrarlo.

Dos límites conocidos de zellij 0.45
------------------------------------
1. **No se puede apuntar a un cliente.** Cuando dos terminales están enganchados
   a la misma sesión hay dos clientes, cada uno parado en su tab, y la CLI no
   tiene forma de decir «este cliente». Dos consecuencias que hay que tener en la
   cabeza al leer este archivo:

   - el tab activo se pregunta con `current-tab-info`, no con el primer cliente
     de `list-clients`: ese primero suele ser el del otro terminal;
   - `move-tab` desde la CLI no hace nada útil (actúa sobre el cliente efímero que
     levanta el propio `zellij action`), así que telar no reordena tabs: el orden
     lo pone quien dibuja.

2. **Mover panes entre tabs necesita un plugin wasm.** No existe la acción en la
   CLI. Se puede hacer desde dentro de la sesión, con un plugin que reciba la
   orden por `zellij pipe`, pero eso es un binario que habría que compilar y
   distribuir. telar no lo trae: `mover_panes` levanta `NoSoportado` y lo explica.

`reemplazar` no es parte del protocolo `Multiplexor`: es lo que hace falta para
devolverle vida a un hilo cuyo proceso murió (una shell, un comando terminado)
sin abrirle un panel más al lado. Está aquí porque es puro zellij.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from telar.config import Config
from telar.modelo import Hilo
from telar.mux import ErrorDeMux

__all__ = ["Zellij", "NoSoportado", "construir", "VERSION_PROBADA"]

#: la versión contra la que está escrito y probado esto. Lo de arriba puede cambiar.
VERSION_PROBADA = "0.45"

#: una acción normal contesta en milisegundos; si no contestó en esto, algo se colgó.
ESPERA = 5.0
#: crear un tab o reemplazar un panel levanta un proceso: hay que darle más aire.
ESPERA_LARGA = 15.0

#: variable de entorno para decir dónde está el ejecutable, si no está en el PATH.
VARIABLE_BINARIO = "TELAR_ZELLIJ"


class NoSoportado(ErrorDeMux):
    """zellij no puede hacer esto desde la CLI. El mensaje dice qué haría falta."""


def _primera_linea(texto: str) -> str:
    for linea in (texto or "").splitlines():
        if linea.strip():
            return linea.strip()
    return ""


def _id_de_panel(panel: dict | None) -> str:
    """El id con que la CLI nombra un panel: `terminal_7`, `plugin_3`."""
    if not panel or "id" not in panel:
        return ""
    prefijo = "plugin" if panel.get("is_plugin") else "terminal"
    return f"{prefijo}_{panel['id']}"


def _utiles(paneles: list[dict]) -> list[dict]:
    """Los paneles a los que tiene sentido escribirles o pedirles un `cwd`.

    Fuera los plugins (la barra, el gestor de sesiones: no hay proceso ahí) y los
    que ya terminaron o están suspendidos.
    """
    return [
        p
        for p in paneles
        if not p.get("is_plugin") and not p.get("exited") and not p.get("is_suppressed")
    ]


def _principal(paneles: list[dict]) -> dict | None:
    """El panel que representa al tab: el que tiene el foco del tab, y nunca uno flotante.

    Un panel flotante suele ser algo de paso (un visor, una consulta) puesto encima
    del trabajo; el trabajo es lo de abajo.
    """
    candidatos = sorted(
        _utiles(paneles),
        key=lambda p: (bool(p.get("is_floating")), not p.get("is_focused"), p.get("id", 0)),
    )
    return candidatos[0] if candidatos else None


def _sesiones_vivas(salida: str) -> set[str]:
    """Los nombres de `list-sessions -n`, sin las que zellij guarda muertas.

    Una sesión terminada sigue en la lista marcada `EXITED` para poder resucitarla.
    Para telar eso no está vivo.
    """
    nombres: set[str] = set()
    for linea in (salida or "").splitlines():
        linea = linea.strip()
        if not linea or "EXITED" in linea:
            continue
        nombres.add(linea.split()[0])
    return nombres


class Zellij:
    """El multiplexor zellij, visto por telar.

    `sesion` es la sesión que telar teje; todas las acciones van dirigidas a ella
    con `-s`, para que funcione igual desde adentro de zellij que desde afuera.
    """

    nombre = "zellij"

    def __init__(self, sesion: str, *, binario: str = "zellij", espera: float = ESPERA) -> None:
        self.sesion = sesion
        self.binario = binario
        self.espera = espera

    # ── el único lugar donde telar lanza un proceso ────────────────────────────

    def _entorno(self) -> dict[str, str]:
        """El entorno sin las `ZELLIJ*`.

        Corriendo dentro de un panel, esas variables le dicen a la CLI que ya está
        adentro de una sesión y el `-s` deja de mandar. Quitarlas es lo que hace que
        el mismo código sirva adentro y afuera.
        """
        return {k: v for k, v in os.environ.items() if not k.startswith("ZELLIJ")}

    def _correr(self, argumentos: list[str], *, espera: float | None = None) -> tuple[int, str, str]:
        """Lanza `zellij <argumentos>` y devuelve (código, stdout, stderr).

        Es la única costura con el sistema: quien quiera probar esta clase sin un
        zellij vivo reemplaza este método y nada más.
        """
        limite = espera if espera is not None else self.espera
        try:
            r = subprocess.run(
                [self.binario, *argumentos],
                env=self._entorno(),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=limite,
            )
        except FileNotFoundError as e:
            raise ErrorDeMux(f"no encuentro el ejecutable «{self.binario}»") from e
        except subprocess.TimeoutExpired as e:
            orden = " ".join(argumentos)
            raise ErrorDeMux(f"zellij no respondió en {limite:g} s: {orden}") from e
        return r.returncode, r.stdout or "", r.stderr or ""

    def _accion(self, *argumentos: str, espera: float | None = None) -> str:
        """Una `zellij action` dirigida a la sesión. Falla fuerte: si no se pudo, se dice."""
        rc, salida, err = self._correr(["-s", self.sesion, "action", *argumentos], espera=espera)
        if rc != 0:
            detalle = _primera_linea(err) or f"código {rc}"
            raise ErrorDeMux(f"«zellij action {' '.join(argumentos)}» falló: {detalle}")
        return salida

    # ── la sesión ─────────────────────────────────────────────────────────────

    def viva(self) -> bool:
        rc, salida, _ = self._correr(["list-sessions", "-n"])
        if rc != 0:
            # sin ninguna sesión, `list-sessions` sale con código 1 y lo dice por stderr.
            return False
        return self.sesion in _sesiones_vivas(salida)

    def tejer(self) -> None:
        """Levanta la sesión en segundo plano si no está. Si está, no toca nada."""
        if self.viva():
            return
        rc, _, err = self._correr(
            ["attach", "--create-background", self.sesion], espera=ESPERA_LARGA
        )
        if rc != 0:
            detalle = _primera_linea(err) or f"código {rc}"
            raise ErrorDeMux(f"no pude levantar la sesión «{self.sesion}»: {detalle}")
        # `attach -b` vuelve antes de que el servidor termine de levantarse: se espera
        # a verla en la lista, o se dice que no apareció. Nunca se sigue a ciegas.
        for _ in range(20):
            if self.viva():
                return
            time.sleep(0.15)
        raise ErrorDeMux(f"pedí levantar la sesión «{self.sesion}» y no apareció en la lista")

    # ── los hilos ─────────────────────────────────────────────────────────────

    def paneles(self) -> list[dict]:
        """Todos los paneles de la sesión, tal como los describe zellij.

        Los diccionarios son de zellij, no de telar: los usa quien sepa de zellij
        (esta clase, y quien quiera un dato que el modelo no lleva). Se piden con
        `-t -c -s` porque sin eso no vienen ni el tab, ni el comando, ni el estado.
        """
        salida = self._accion("list-panes", "-t", "-c", "-s", "-j")
        try:
            datos = json.loads(salida or "[]")
        except json.JSONDecodeError as e:
            raise ErrorDeMux(f"«list-panes -j» no devolvió JSON: {e}") from e
        if not isinstance(datos, list):
            raise ErrorDeMux("«list-panes -j» no devolvió una lista de paneles")
        return [p for p in datos if isinstance(p, dict) and "tab_id" in p]

    def _por_tab(self, paneles: list[dict]) -> dict[int, list[dict]]:
        tabs: dict[int, list[dict]] = {}
        for p in paneles:
            try:
                tid = int(p["tab_id"])
            except (KeyError, TypeError, ValueError):
                continue
            tabs.setdefault(tid, []).append(p)
        return tabs

    def _tab_activo(self) -> int | None:
        """El TAB_ID que tiene el foco, según zellij.

        NO sale del primer cliente de `list-clients`: con dos terminales enganchados
        a la misma sesión hay un cliente por terminal, cada uno parado en su tab, y
        el primero de esa lista es tan arbitrario como el otro.

        Devuelve None cuando no hay a quién preguntarle: una sesión levantada en
        segundo plano, sin nadie enganchado, no tiene tab activo («No active tab
        found for current client»). Eso no es una falla.
        """
        rc, salida, _ = self._correr(["-s", self.sesion, "action", "current-tab-info", "-j"])
        if rc == 0:
            try:
                datos = json.loads(salida or "{}")
            except json.JSONDecodeError:
                datos = {}
            if isinstance(datos, dict) and isinstance(datos.get("tab_id"), int):
                return int(datos["tab_id"])
        # respaldo: la misma acción en texto («id: 63»), que es más vieja que `-j`.
        rc, salida, _ = self._correr(["-s", self.sesion, "action", "current-tab-info"])
        if rc == 0:
            m = re.search(r"^id:\s*(\d+)", salida, re.M)
            if m:
                return int(m.group(1))
        return None

    def hilos(self) -> list[Hilo]:
        """Los tabs de la sesión, en el orden de zellij.

        Devuelve solo lo que zellij sabe: id, nombre, si tiene el foco y el `cwd` de
        su panel principal. Un tab sin paneles útiles (todo plugin, todo terminado)
        aparece igual, sin ruta: existe, y esconderlo sería mentir.
        """
        try:
            paneles = self.paneles()
        except ErrorDeMux:
            if self.viva():
                raise
            return []  # la sesión no está: no hay hilos, y eso no es un error.

        activo = self._tab_activo()
        hilos: list[tuple[int, Hilo]] = []
        for tid, ps in self._por_tab(paneles).items():
            cabeza = _principal(ps)
            cwd = (cabeza or {}).get("pane_cwd") or ""
            posicion = int(ps[0].get("tab_position", 0) or 0)
            hilos.append(
                (
                    posicion,
                    Hilo(
                        id=str(tid),
                        nombre=str(ps[0].get("tab_name") or ""),
                        ruta=Path(cwd) if cwd else None,
                        activo=(activo is not None and tid == activo),
                    ),
                )
            )
        hilos.sort(key=lambda par: (par[0], int(par[1].id)))
        return [h for _, h in hilos]

    def activo(self) -> Hilo | None:
        for h in self.hilos():
            if h.activo:
                return h
        return None

    def _tab(self, hilo: str) -> tuple[int, list[dict]]:
        """De lo que traiga la orden (un id o un nombre) al TAB_ID y sus paneles.

        El id gana sobre el nombre: si alguien llama a un tab «7» y además existe el
        tab con id 7, se va al 7. Es raro y se arregla renombrando.
        """
        tabs = self._por_tab(self.paneles())
        clave = str(hilo).strip()
        if clave.isdigit() and int(clave) in tabs:
            return int(clave), tabs[int(clave)]
        por_nombre = [
            (tid, ps) for tid, ps in tabs.items() if str(ps[0].get("tab_name") or "") == clave
        ]
        if por_nombre:
            por_nombre.sort(key=lambda par: int(par[1][0].get("tab_position", 0) or 0))
            return por_nombre[0]
        conocidos = ", ".join(
            f"{tid}:{ps[0].get('tab_name') or ''}" for tid, ps in sorted(tabs.items())
        )
        raise ErrorDeMux(
            f"no hay ningún hilo «{hilo}» en la sesión «{self.sesion}»; hay: {conocidos or '—'}"
        )

    # ── actuar sobre un hilo ──────────────────────────────────────────────────

    def ir(self, hilo: str) -> None:
        tid, _ = self._tab(hilo)
        self._accion("go-to-tab-by-id", str(tid))

    def crear(
        self, nombre: str, ruta: Path | None = None, comando: list[str] | None = None
    ) -> Hilo:
        """Abre un tab nuevo y lo devuelve ya identificado.

        `new-tab` imprime el TAB_ID creado; aun así se vuelve a mirar la sesión,
        porque el tab recién nacido puede tardar un parpadeo en aparecer con su
        `cwd` puesto, y devolver un `Hilo` inventado sería empezar mintiendo.
        """
        # `--clave=valor` y no `--clave valor`: un nombre que empiece con guion
        # («-borrador») lo lee la CLI como bandera y la orden entera se cae.
        argumentos = ["new-tab", f"--name={nombre}"]
        if ruta is not None:
            argumentos += [f"--cwd={ruta}"]
        if comando:
            argumentos += ["--", *comando]
        salida = self._accion(*argumentos, espera=ESPERA_LARGA)

        m = re.search(r"\d+", salida or "")
        tid = m.group(0) if m else None
        for intento in range(4):
            if intento:
                time.sleep(0.25)
            for h in self.hilos():
                if (tid is not None and h.id == tid) or (tid is None and h.nombre == nombre):
                    return h
        if tid is None:
            raise ErrorDeMux(f"creé el tab «{nombre}» pero zellij no me dijo cuál es")
        return Hilo(id=tid, nombre=nombre, ruta=Path(ruta) if ruta else None, activo=True)

    def renombrar(self, hilo: str, nombre: str) -> None:
        # con `-t` renombra ESE tab; sin `-t` renombraría el que tenga el foco, que
        # puede ser cualquiera. (La ayuda de 0.45 dice «renames the focused pane»:
        # es un error de la ayuda, renombra el tab.)
        tid, _ = self._tab(hilo)
        self._accion("rename-tab", "-t", str(tid), "--", nombre)

    def cerrar(self, hilo: str) -> None:
        tid, _ = self._tab(hilo)
        self._accion("close-tab-by-id", str(tid))

    def escribir(
        self, hilo: str, texto: str, *, enviar: bool = False, panel: str | None = None
    ) -> None:
        """Deja `texto` escrito en un panel del hilo, sin ejecutarlo.

        `write-chars -p` apunta al panel por id, así que no hace falta mover el foco
        —y moverlo estaría mal: el foco es de quien esté mirando la pantalla. Quien
        quiera además llevar el teclado ahí, que llame antes a `ir`.

        Con `enviar=True` se manda después un ↩ (el byte 13) al mismo panel.
        """
        tid, ps = self._tab(hilo)
        destino = panel or _id_de_panel(_principal(ps))
        if not destino:
            raise ErrorDeMux(f"el hilo «{hilo}» no tiene ningún panel vivo donde escribir")
        # el `--` protege un texto que empiece con guion: si no, la CLI lo lee como bandera.
        if texto:
            self._accion("write-chars", "-p", destino, "--", texto)
        if enviar:
            self._accion("write", "-p", destino, "--", "13")

    # ── más allá del protocolo, porque es puro zellij ──────────────────────────

    def reemplazar(
        self,
        hilo: str,
        comando: list[str],
        *,
        ruta: Path | None = None,
        panel: str | None = None,
    ) -> str:
        """Pone `comando` a correr EN LUGAR de un panel del hilo, y devuelve el panel nuevo.

        Es lo que hace falta para revivir un hilo apagado —una shell, o un comando
        que ya terminó— sin llenarle el tab de paneles. El panel reemplazado se
        cierra (`--close-replaced-pane`), así que es destructivo: por defecto se
        sacrifica el panel principal del hilo, y quien sepa cuál sobra lo dice con
        `panel`.
        """
        tid, ps = self._tab(hilo)
        victima = panel or _id_de_panel(_principal(ps))
        if not victima:
            # Ningún panel vivo: el caso típico es justamente ese, un tab cuyo comando
            # ya terminó. Se reemplaza ese cadáver —que es lo que se quiere— pero nunca
            # un plugin (ahí no corre nada y el tab perdería su barra).
            cuerpos = [p for p in ps if not p.get("is_plugin")]
            victima = _id_de_panel(cuerpos[0]) if cuerpos else ""
        if not victima:
            raise ErrorDeMux(f"el hilo «{hilo}» no tiene ningún panel de terminal que reemplazar")

        previos = {_id_de_panel(p) for p in ps}
        argumentos = ["new-pane", "--in-place", f"--pane-id={victima}", "--close-replaced-pane"]
        if ruta is not None:
            argumentos += [f"--cwd={ruta}"]
        if comando:
            argumentos += ["--", *comando]
        salida = self._accion(*argumentos, espera=ESPERA_LARGA).strip()
        if salida.startswith("terminal_") or salida.startswith("plugin_"):
            return salida.split()[0]

        # Reemplazar un panel que YA HABÍA TERMINADO no imprime el id (0.45.1): se
        # busca el panel del tab que antes no estaba.
        for _ in range(10):
            time.sleep(0.3)
            try:
                _, ahora = self._tab(str(tid))
            except ErrorDeMux:
                break
            nuevos = [p for p in ahora if _id_de_panel(p) not in previos]
            if nuevos:
                return _id_de_panel(nuevos[0])
        raise ErrorDeMux(
            f"reemplacé un panel de «{hilo}» y no pude saber cuál quedó; míralo antes de escribirle"
        )

    def mover_panes(self, hilo: str, destino: str) -> None:
        """No se puede: en zellij hace falta un plugin. Ver el encabezado del módulo."""
        raise NoSoportado(
            f"no puedo mudar los paneles de «{hilo}» a «{destino}»: zellij {VERSION_PROBADA} no "
            "tiene ninguna acción de CLI que mueva paneles entre tabs, y las que siguen al foco "
            "no sirven porque no se puede apuntar a un cliente. Hacerlo pide un plugin wasm "
            "corriendo dentro de la sesión, al que se le manda la orden con "
            "`zellij pipe --plugin file:<plugin.wasm>`. telar no trae ese plugin: mueve los "
            "paneles a mano, o abre el hilo donde corresponde y cierra el viejo."
        )


def construir(config: Config) -> Zellij:
    """El zellij que pide la configuración.

    El ejecutable se busca en el PATH; `TELAR_ZELLIJ` lo pisa, para una máquina
    donde no esté en el camino de siempre. Ninguna ruta viene escrita aquí.
    """
    pedido = os.environ.get(VARIABLE_BINARIO) or "zellij"
    binario = shutil.which(pedido) or (pedido if Path(pedido).exists() else "")
    if not binario:
        raise ErrorDeMux(
            f"no encuentro «{pedido}» en el PATH; instala zellij o apunta {VARIABLE_BINARIO} "
            "al ejecutable"
        )
    return Zellij(config.sesion, binario=binario)
