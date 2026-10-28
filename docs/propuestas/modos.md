# Modos de la página: estándar, foco y los que hagan falta

Estado: **el primer paso, hecho** (27-oct-2026, sin publicar todavía). Lo demás, por hacer, en este orden.

## Por qué

La página tiene varias cosas que se ajustan por separado: la barra de hilos se pliega, la ficha de un agente
también, la terminal tiene su ancho, su posición y su fondo (`[terminal]`). Para cambiar de manera de trabajar —
concentrarse en una terminal, revisar el día con todo a la vista— había que tocar cada una. Un **modo** es un nombre
con valores para un catálogo fijo de ajustes; cambiar de modo los aplica todos de una vez.

## Cómo es

- **El catálogo** está en `telar.modos` (Python): cada ajuste con su clave, su grupo y sus valores. La página lo
  recibe de la API, así que agregar un ajuste es agregarlo ahí y enseñarle a la página a aplicarlo.
- **Un modo** dice valores para algunos ajustes; lo que no dice lo toma de «estándar». Los de fábrica son
  «estándar» (lo de siempre) y «foco» (solo la terminal, al centro, sin nada alrededor). Se definen o se cambian en
  la configuración, `[modos.<nombre>]`; uno de fábrica cambiado vuelve a ser el de fábrica al borrar su tabla.
- **Cuál está puesto** es del navegador (laptop en foco, celular en estándar). **Un cambio a mano** (abrir la barra
  estando en foco) vale hasta cambiar de modo; «guardar en este modo» (⚙ modos) lo deja en él.
- **Se cambia** con el selector de la cabecera («◧ estándar»), con ⌥⇧F (foco y vuelta) y ⌥⇧M (el siguiente), o
  en ⚙ modos. En foco no hay cabecera: un ◧ arriba a la derecha vuelve al modo de antes.

## El catálogo

| Grupo | Ajuste | Valores |
|---|---|---|
| Disposición | `barra` (la de hilos) | abierta · plegada · oculta |
| | `lado` (la ficha de un agente) | abierto · plegado · oculto |
| | `cabecera` | visible · oculta |
| | `acciones` (la barra del hilo) | visible · oculta |
| | `escribir` (la caja bajo la terminal) | visible · oculta |
| | `pantalla_completa` | no · sí |
| Terminal | `columnas` | 40–400, o todo |
| | `posicion` | izquierda · centro · derecha |
| | `fondo` | telar · ninguno · color · imagen · módulo |
| Avisos | `avisos` | todos · urgentes · ninguno |
| | `aviso_version` | visible · oculto |

## Los pasos

1. **El primero (hecho)**: el catálogo de arriba, «estándar» y «foco», el selector, las teclas, los cambios a mano
   y ⚙ modos (ver, crear, guardar, volver a fábrica).
2. **La letra y el tema**: el tamaño de la letra de la terminal (`tam`) y el tema de colores (variantes del de ahora).
   Tocan los tokens de toda la página: van aparte, con cuidado.
3. **Lo que se ve en la barra**: qué secciones empiezan abiertas (DASHBOARD, AGENTES, HILOS, EQUIPO…) y el orden de
   HILOS, como ajustes de un modo.
4. **Modos que se ponen solos**: por dispositivo (el celular en un modo «compacto»), y por un disparador
   (`[disparadores]`: foco a las 9:00, estándar a las 18:00).
5. **El modo de un hilo**: abrir cierto hilo o agente pone un modo (siempre foco con uno), y se vuelve al cerrarlo.
6. **Modos de los módulos**: un módulo trae modos, como trae fondos (`[modos.<n>]` en su `modulo.toml`).
7. **El `viewMode` de Claude Code** (cuánto muestra de sus pasos intermedios): tienta ponerlo con el modo, pero vive
   en `~/.claude/settings.json` y vale para todas las sesiones de la máquina, no para una página. Si se hace, como
   una acción explícita del modo, nunca por debajo.

## Conexiones

- [../configuracion.md](../configuracion.md): `[terminal]` y `[modos]`.
- [README.md](README.md): el plan de las propuestas.
