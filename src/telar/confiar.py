"""La pregunta de confiar en una carpeta, vista desde afuera: un hilo que quedó detenido en ella antes de arrancar.

Claude Code (desde la 2.1.326) pregunta antes de arrancar si confía en una carpeta que no conoce: la que se le suma con
`--add-dir` (el worktree de un hijo con rama: «Adding a new directory: … ❯ 1. Yes, add it») y la carpeta donde
arranca («Accessing workspace: … ❯ 1. Yes, I trust this folder»). Mientras la pregunta está en pantalla no corre
ningún gancho, así que el hilo no dice nada: se quedaba parado horas sin que nadie lo viera.

El nodo mira el panel de cada hilo de su máquina cada tanto (`mirar`). Si la pregunta está a la vista, marca al hilo
como que espera a la persona (`Atencion.ESPERA`), con lo que pide y la clase «confiar» (`Estado.anotar_espera`): la
barra lo muestra en «te espera», «te esperan» lo lista y la página lo dice en la franja de avisos
(`pagina/src/web/detenidos.ts`). Cuando la pregunta deja de estar (la persona contestó), lo quita, si los ganchos no
lo cambiaron antes.

telar nunca la contesta ni marca nada como confiado (`hasTrustDialogAccepted` en `~/.claude.json`): esa decisión es
de la persona.

    from telar import confiar
    confiar.en_pantalla(texto_del_panel)    # {"carpeta": "/w/codigo-x", "que": "--add-dir"} o None
    confiar.mirar(config, tel)              # lo que cambió, una línea por hilo
"""

from __future__ import annotations

import re

from telar.modelo import Atencion

#: la clase de la espera que deja (`Estado.anotar_espera`): la página la reconoce por ella
CLASE = "confiar"

#: las preguntas que se reconocen: su encabezado, la opción de decir que sí y qué carpeta es
PREGUNTAS: tuple[tuple[str, str, str], ...] = (
    ("Adding a new directory", "Yes, add it", "--add-dir"),
    ("Accessing workspace", "Yes, I trust this folder", "la carpeta donde arranca"),
)

#: cuántas líneas del final de la pantalla se miran: la pregunta va abajo, donde iría la caja de escribir
FINAL = 30

#: el borde de un recuadro de Claude Code, que se quita de cada línea
_BORDE = " \t│┃|╭╮╰╯─━"


def _opcion(texto: str) -> re.Pattern:
    """La opción dibujada como opción: «❯ 1. Yes, add it» (con el cursor o sin él), sola en su línea."""
    return re.compile(rf"^(?:[❯>›]\s*)?\d+[.)]\s+{re.escape(texto)}\s*$")


def en_pantalla(texto: str | None) -> dict | None:
    """Si el panel muestra una de las preguntas: {"carpeta" (la que pregunta; "" si no se lee), "que" (`--add-dir` o
    la carpeta donde arranca)}; None si no.

    Solo cuenta la pregunta dibujada: su opción de decir que sí como opción numerada, sola en su línea, en las últimas
    líneas de la pantalla, y su encabezado arriba de ella. Una conversación que cita esas palabras no es la pregunta."""
    if not texto:
        return None
    lineas = [x.strip(_BORDE) for x in texto.splitlines()]
    lineas = [x for x in lineas if x][-FINAL:]
    for encabezado, si, que in PREGUNTAS:
        opcion = _opcion(si)
        donde = next((i for i in range(len(lineas) - 1, -1, -1) if opcion.match(lineas[i])), None)
        if donde is None:
            continue
        arriba = next((i for i in range(donde - 1, -1, -1) if lineas[i].startswith(encabezado)), None)
        if arriba is None:
            continue
        # la carpeta: lo que sigue a los dos puntos del encabezado o, si no hay, la línea de abajo, si parece una ruta
        resto = lineas[arriba][len(encabezado):].lstrip(" :").strip()
        if not resto and arriba + 1 < donde:
            resto = lineas[arriba + 1]
        carpeta = resto if resto.startswith(("/", "~")) else ""
        return {"carpeta": carpeta, "que": que}
    return None


def pide(encontrada: dict) -> str:
    """Lo que el hilo espera de la persona, en una línea: lo que se anota como su espera y se lee en «te esperan»."""
    carpeta = encontrada.get("carpeta") or "una carpeta"
    como = f" ({encontrada['que']})" if encontrada.get("que") else ""
    return (f"Claude Code pregunta si confías en {carpeta}{como} antes de arrancar: contéstalo en el hilo "
            f"(telar no lo contesta)")


def mirar(config, tel) -> list[str]:
    """Mira el panel de cada hilo vivo de esta máquina (`tel`, de `_comun.tejer`) y anota en el estado quién quedó
    detenido en la pregunta y quién ya no. Devuelve lo que cambió, una línea por hilo, para el registro del nodo. Sin
    multiplexor que sepa leer un panel, nada."""
    mux, est = getattr(tel, "mux", None), getattr(tel, "estado", None)
    if mux is None or est is None:
        return []
    try:
        paneles = [p for p in mux.panes() if not getattr(p, "flotante", False) and not getattr(p, "terminado", False)]
    except Exception:  # noqa: BLE001 - sin paneles que mirar, nada que decir
        return []
    del_tab: dict[str, str] = {}
    for p in paneles:
        del_tab.setdefault(str(p.tab), str(p.id))
    cambios = []
    for h in tel.hilos:
        if getattr(h, "remoto", "") or not tel.vivo(h) or h.id not in del_tab:
            continue
        try:
            encontrada = en_pantalla(mux.capturar_pane(del_tab[h.id], 1))
        except Exception:  # noqa: BLE001 - un panel que no se deja leer no tumba la vuelta
            continue
        espera = est.espera(h.nombre) or {}
        marcado = espera.get("clase") == CLASE
        if encontrada and not marcado:
            est.anotar_atencion(h.nombre, Atencion.ESPERA)
            est.anotar_espera(h.nombre, pide(encontrada), CLASE)
            cambios.append(f"«{h.nombre}» quedó detenido en la pregunta de confiar en "
                           f"{encontrada.get('carpeta') or 'una carpeta'}: espera a la persona")
        elif not encontrada and marcado:
            # la persona contestó (y los ganchos todavía no dicen nada): ya no espera eso
            est.anotar_atencion(h.nombre, Atencion.NINGUNA)
            cambios.append(f"«{h.nombre}»: ya no está en la pregunta de confiar")
    return cambios
