# La configuración

Todo lo que es de esta máquina vive en un TOML. **Sin archivo, telar arranca
igual**: cada clave tiene un valor por defecto razonable, y este documento es el
esquema completo. Si aquí no está, telar no lo lee.

## Dónde

| Orden | Dónde |
|---|---|
| 1 | `$TELAR_CONFIG`, si está definida |
| 2 | `$XDG_CONFIG_HOME/telar/config.toml`, si `XDG_CONFIG_HOME` está definida |
| 3 | `~/.config/telar/config.toml` |

`telar --config RUTA` pisa las tres. Una ruta pedida a mano que no existe es un
error; el archivo por defecto puede faltar sin que pase nada.

## El archivo entero

```toml
# Qué multiplexor de terminal hay debajo: "tmux", el único.
multiplexor = "tmux"

# El nombre de la sesión que telar teje. Una sesión, un telar.
sesion = "telar"

# La raíz del repositorio de trabajo: de ahí sale el perfil, y ahí viven los hilos.
# Por defecto, la carpeta donde se corrió telar.
raiz = "~/trabajo"

# Dónde escribir el estado: vínculos, prioridades, archivo, semáforo, sesiones y el
# registro de foco. Las fichas NO se guardan: se leen del documento cada vez.
# Nunca dentro de `raiz`: el repositorio de trabajo no se ensucia con caché.
# Por defecto, $XDG_STATE_HOME/telar o ~/.local/state/telar.
estado = "~/.local/state/telar"

# El perfil, si no es el de la raíz (.telar/perfil.yaml). Rara vez hace falta.
perfil = "~/trabajo/perfiles/otro.yaml"

[intervalos]
refresco     = 1.0      # cada cuánto se le pregunta al multiplexor, en segundos
ficha        = 60.0     # cada cuánto se recompila la ficha de un hilo
proveedores  = 300.0    # cada cuánto se consulta a los proveedores
foco_maximo  = 3600.0   # tope de un intervalo sin cambio de foco, al contar tiempo

# Ningún proveedor existe hasta que aparece aquí. Sin esta sección, telar no sale
# de la máquina: no hay telemetría, ni informes de uso, ni actualizaciones solas.
[proveedores.calendario]
activo = true
# Las demás claves son del proveedor; telar se las pasa tal cual y no las mira.
# Las de `calendario`: tipo (ics | gws | comando | ninguno), y url o archivo si es ics.
tipo = "ics"
archivo = "~/agenda.ics"

[proveedores.tareas]
activo = false
tipo = "markdown"
rutas = ["proyectos/*/README.md"]
```

Cada proveedor documenta sus propias claves en su módulo: `telar.proveedores.tareas`
y `telar.proveedores.calendario`. De fábrica no hay ninguno encendido, y el único
que sale de red es `calendario` con `url`, que lo dice en su `alcance` antes de
que nadie lo encienda.

Una clave que mira telar en cualquier proveedor: `area`, el área de sus ítems que no traen la suya. Con ella, un
calendario del trabajo es del mundo del trabajo (`[mundos] areas`, más abajo): sus eventos se ven en ese mundo y no en
los demás.

### Las tareas

`[proveedores.tareas]` trae lo que hay que hacer. `markdown` lee las casillas de los
documentos que se le digan; `comando` corre un programa que imprime el JSON del
contrato, y es la salida para cualquier gestor de tareas propio:

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/casa/bin/mis-tareas"]
```

El puente son diez líneas y traduce el dialecto de cada uno: telar escribe las fechas
como `vence:2026-09-30` y la prioridad como `!alta`, y otro gestor usará `due:` y `(P2)`.

Con `detalle`, un clic en una tarea del dashboard abre su **ficha** en vez de ir al hilo:
leerla y decidir, sin abrir un agente (⌘-clic sigue llevándola al hilo).

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/casa/bin/mis-tareas"]
detalle = ["/casa/bin/mis-tareas", "--ver", "{id}"]
```

Con `pestana`, lo del proveedor no son pendientes sino otra cosa (un feed de lecturas, una
cola de revisión): sus ítems no entran a la lista de hoy y tienen su propia pestaña en el
dashboard, con el nombre que se diga, la misma ficha y la navegación con ← →. La pestaña se
abre directo en el primer ítem (no en una lista); ⎋ vuelve a hoy. La `tecla` no puede ser
una del dashboard ni la de un atajo (`telar doctor` lo revisa).

```toml
[proveedores.lecturas]
como    = "tareas"          # de qué clase es; sin `como`, la del nombre
tipo    = "comando"
comando = ["/casa/bin/lecturas"]
detalle = ["/casa/bin/lecturas", "--ver", "{id}"]
pestana = "leer"
tecla   = "l"               # opcional: abre la pestaña, en el primer ítem
vista   = "lectura"         # opcional: la ficha, para leer con calma (abajo)
```

Con `vista = "lectura"`, la ficha de esa pestaña no se ve como la de una tarea: se dibuja para leer con calma y pensar
lo leído. El texto va con serifa, a un ancho de lectura, y arriba, tranquilos, el carril (la palabra de su `avance`, en
su color), los temas, de dónde viene y «leer el original». Al lado va un margen con las notas de la casa que nombra el
texto (las rutas que escribe como código, `docs/x.md`), cada una con su título, su entrada y cuántas conexiones tiene
en el grafo de conocimiento (el módulo «grafo», si está). Un clic abre la nota en el margen, con sus conexiones, y de
ahí se puede seguir a otra sin que el texto se mueva. Al final, «tu lectura»: una caja para escribir el porqué y las
acciones, sin números ni «1/8». Responder no pasa solo al siguiente ítem: la ficha queda con lo anotado, y abajo dice
cuál sigue. En el celular va todo en una columna, con las notas entre el texto y la respuesta, y una nota se despliega
donde se pinchó. Si la ficha propone relaciones para un grafo de conocimiento (`conexiones`), van en el margen, sobre
las notas, cada una como una oración («esta lectura *tensiona* La frontera…»): ninguna entra si no se elige, el tipo y
el porqué se pueden cambiar, y al pasar por una se ilumina en el texto la frase en que se apoya. Lo elegido viaja con la
acción que lo pide («guardar en la biblioteca»). Un ícono en la barra (una acción de solo ícono) sirve para volver a
procesar el ítem; mientras dura, la ficha lo dice y se pone al día sola. El ícono de la instrucción, en la misma
barra, abre un hilo con la lectura: la ventana de siempre, con «un hilo nuevo» elegido y llamado como ella, y lo que
la ficha tiene (el original, de dónde viene, los temas, cada bloque, lo respondido y lo escrito en «tu lectura») como
contexto. Lo que la ficha puede traer para esta vista (temas, fuente, fecha, lo que ya se respondió, las relaciones y
su vocabulario, si se está procesando), en
[contratos](contratos.md#telar-tarea-id---json). `telar doctor` dice si la vista no existe o si falta la `pestana`.

La pestaña muestra todo lo que entrega el proveedor, sin tope ni «ver más». En una de lectura, la lista (y ← →, y
«sigue» en la ficha) va en este orden: primero lo que se mandó la persona misma (`de`, con uno de sus nombres o «yo»),
después por prioridad (alta, media, baja, sin prioridad) y, dentro de cada una, lo más nuevo arriba (`fecha`; lo que no
la dice, al final de la suya). Cada fila del proveedor puede traer `prioridad` (alta, media, baja, o «sin»), `de` y
`fecha` (AAAA-MM-DD) en el nivel de la fila o dentro de `campos`; sin `fecha`, la de su id si empieza con una
(`2026-11-18-algo`). Si ninguna fila dice `de` ni `prioridad`, el orden es el del proveedor, tal cual. La fila y el
encabezado de la ficha muestran la prioridad (el círculo de la de una tarea, en su color) y, lo de la persona, «tuya»
(el ícono de persona).

Con `recibir`, el proveedor además **recibe** lo que el celular le comparte al panel instalado como app
(«guardar en leer»; ver `telar compartir`): una lista de palabras donde `{url}`, `{texto}` y `{titulo}`
se reemplazan, sin shell.

```toml
recibir = ["/casa/bin/lecturas", "dejar", "{url}", "--nota", "{texto}"]
```

`detalle` imprime una página (el contrato de `telar seccion`) con `acciones`, los botones
de la ficha. Ver [contratos](contratos.md#telar-tarea-id---json). Las tareas que traen
`avance` (lo último que dejó un agente trabajando solo) van primero en la lista, con esa
palabra en color, y el modo «propuestas» las junta para revisarlas con ← →.


### Las fechas

Los cronogramas de los documentos de las unidades (`## Cronograma`) se leen siempre, sin declarar nada
(`telar fechas`, [contratos](contratos.md#telar-fechas---json)). Un proveedor con `como = "fechas"` suma otras
fuentes, con la misma maquinaria que las tareas:

```toml
[proveedores.fechas]
tipo  = "markdown"
rutas = ["equipo/calendario.md", "operacion/*/seguimiento.md"]   # globs desde la raíz, sin «..»

[proveedores.hitos]
como          = "fechas"
tipo          = "comando"
comando       = ["bin/fechas-de-los-hitos"]    # corre en la raíz e imprime fechas en JSON
tiempo_maximo = 20
escribir      = ["bin/fechas-de-los-hitos", "mover"]    # opcional: cómo cambia una (telar fecha)
editables     = ["inicio", "fin"]                     # con escribir: qué campos sabe cambiar
```

Las de `markdown` son de la unidad que contiene su documento. Las de un comando, de la que diga su `proyecto`, o
de la que contiene su `fuente`. Un módulo trae la suya en su `modulo.toml` (`[fechas] comando`): es un proveedor
como estos, con el nombre del módulo, que corre en su carpeta. Las tareas con fecha de vencimiento de los proveedores
de tareas entran solas, con `clase = "tarea"`.

### Los tipos: objetos sobre archivos (`[tipos]`)

Dónde viven los objetos de un tipo, un archivo por objeto (ver `docs/arquitectura.md`, «Los tipos»). Por ahora,
el tipo `tarea` en su formato de archivo propio:

```toml
[tipos.tarea]
carpeta = "~/notas/tareas"     # un T84.md por tarea
formato = "archivo"            # el único, por ahora
```

Las escribe una sola máquina, la que declara `carpeta`. En las demás, `en` dice cuál es, y `telar tipo
tarea …` (leer, crear, cambiar) se le pide a ella por el bus: lo que se cambia desde otra máquina cambia
las tareas, no la copia que llega por git.

```toml
[tipos.tarea]
en = "servidor"
```

Para que `telar hoy` y el panel las muestren, el proveedor de tareas las lee del mismo índice:

```toml
[proveedores.tareas]
tipo    = "tipo"
carpeta = "~/notas/tareas"     # la misma de [tipos.tarea]
en      = "servidor"           # opcional: en la máquina donde viven, por el bus
```

Tiene que ser la misma carpeta: sus pendientes llevan la dirección `tarea:<id>`, y `telar objeto` la abre
en la de `[tipos.tarea]`. Si son distintas, o falta `[tipos.tarea]`, `telar doctor` lo avisa.

Sin `detalle`, el proveedor arma él mismo la **ficha** de cada tarea (la propuesta del agente, el contexto,
los enlaces, la historia) y sus botones son acciones del tipo: se corren sobre el archivo con la versión
que mostraba la ficha, y el archivo se commitea y se sube (`telar commit`). Lo propio de cada casa va en sus
opciones:

```toml
agente           = "Ada"                       # quién deja las propuestas («Ada · lo dejó preparado»)
escribir_a       = "Claude"                    # «↩ escribirle a Claude»: a quién se le escribe en un hilo
mensaje_escribir = "/tarea {id} {texto}"       # qué recibe ese hilo (sin esto, no hay botón)
mensaje_procesar = "/avanzar {id}"             # «✓ hecha y procesar ahora» (sin esto, no hay botón)
equipo           = ["Ana", "Beto"]             # a quién se puede asignar (más quien ya sea dueño de alguna)
gmail            = { personal = "yo@gmail.com", "*" = "yo@trabajo.com" }   # cómo se abre un origen gmail:
```

En `mensaje_escribir` y `mensaje_procesar`, `{id}` es el de la tarea (`T84`) y `{direccion}` su dirección
(`tarea:T84`); `{texto}` es lo que se escribe al apretar el botón. En la página, «escribirle a…» no es un botón: es la
ventana de la instrucción (su ícono en la barra de la ficha, «instrucción…» en el ⋯ de una tarea), que manda `/tarea`
con lo escrito y el contexto de la tarea, y lo anota en su historia; `escribir_a` y `mensaje_escribir` quedan para
`telar tarea --accion` y quien corra las acciones del proveedor por su cuenta.

`telar serve` las tiene en memoria (un índice que se mantiene al día con los archivos) y las sirve en
`/tipos/tarea`; las acciones (`POST /tipos/tarea/{id}/completar`, `…/reagendar`…) llevan la versión que se
leyó y las escribe solo ese proceso. Declárala en la máquina donde viven las tareas.

### El calendario: iCal o gws

La agenda del dashboard sale de una de dos fuentes, y se elige sin editar el archivo:

```sh
telar config --calendario gws                          # Google Workspace, con la CLI gws
telar config --calendario https://…/private-…/basic.ics  # una dirección iCal (o webcal://, o un .ics)
telar config --calendario ninguno                      # sin agenda
```

En la página es lo mismo desde **⚙ configuración** (arriba a la derecha): dice cuál está en uso,
si responde, y deja cambiarla.

- **gws** usa la cuenta con la que la CLI `gws` ya está conectada (`gws auth login`).
  No hay dirección que pegar ni secreto que guardar, sirve aunque el administrador del
  dominio haya desactivado iCal, y es la misma herramienta que lee el correo.
- **iCal** es el formato que exporta cualquier calendario. En Google Calendar está en
  Configuración › tu calendario › «Dirección **secreta** en formato iCal». La dirección
  *pública* (`…/public/basic.ics`) solo funciona si el calendario está publicado para
  todo internet; si no, Google responde 404.

Una dirección iCal secreta es una llave: quien la tiene ve la agenda. Por eso
`--calendario` deja el archivo de configuración legible solo por su dueño, y ni
`telar config` ni los mensajes de error la muestran entera.

## Las claves, una por una

| Clave | Tipo | Por defecto | Qué es |
|---|---|---|---|
| `multiplexor` | `"tmux"` | `"tmux"` | quién maneja los tabs de verdad (zellij se dejó de soportar en la 0.3) |
| `sesion` | texto | `"telar"` | la sesión del multiplexor que telar teje |
| `raiz` | ruta | la carpeta actual | el repositorio de trabajo |
| `estado` | ruta | `~/.local/state/telar` | estado derivado; se puede borrar sin perder nada ([qué guarda](estado.md)) |
| `perfil` | ruta | `raiz/.telar/perfil.yaml` | el perfil del repositorio |
| `intervalos.refresco` | segundos > 0 | `1.0` | cada cuánto se relee el multiplexor |
| `intervalos.ficha` | segundos > 0 | `60.0` | cada cuánto se recompila una ficha |
| `intervalos.proveedores` | segundos > 0 | `300.0` | cada cuánto se consulta la red |
| `intervalos.foco_maximo` | segundos > 0 | `3600.0` | tope de un intervalo sin cambio de foco |
| `proveedores.<n>.activo` | `true` \| `false` | `true` | si se consulta o no |
| `proveedores.<n>.*` | lo que sea | — | opciones del proveedor; telar no las interpreta |

`~` se expande. Las rutas relativas quedan relativas a donde se corrió telar, que
casi nunca es lo que alguien quiere: conviene escribirlas absolutas o con `~`.

### `foco_maximo` no es un refresco

El tiempo por hilo se cuenta entre cambios de foco, y nadie avisa "me fui del
computador". Sin tope, salir a almorzar le regala dos horas al hilo que quedó
arriba. `foco_maximo` recorta cualquier intervalo sin cambio: una hora de silencio
cuenta como una hora, no como la noche entera. El número es del usuario porque la
jornada también.

## Variables de entorno

Pisan el archivo, y son para una corrida suelta:

| Variable | Pisa |
|---|---|
| `TELAR_CONFIG` | dónde está el archivo |
| `TELAR_MULTIPLEXOR` | `multiplexor` |
| `TELAR_SESION` | `sesion` |
| `TELAR_RAIZ` | `raiz` |
| `TELAR_ESTADO` | `estado` |
| `TELAR_PERFIL` | `perfil` |

Y `telar --raiz RUTA` pisa a todas para esa corrida.

## Errores

telar prefiere quejarse a adivinar. Una clave que no existe en este documento, un
multiplexor que no conoce, un intervalo negativo o un TOML mal formado son
`ErrorDeConfig` con el nombre de la clave en el mensaje. No hay modo tolerante: una
configuración a medias es peor que ninguna, porque se nota tres días después.

## Qué NO va aquí

Lo que es del **repositorio** y no de la máquina: qué carpetas son proyectos, qué
se lee de un README, qué acciones hay. Eso lo declara el propio repositorio en su
[`.telar/perfil.yaml`](perfil.md), y viaja con él.

## `[agente]` — qué se abre en cada hilo

```toml
[agente]
nombre = "claude-code"   # vacío o ausente: cada hilo es una shell
carpeta = "hilo"         # hilo (por defecto) · raiz · una ruta
reunion = "/preparar-reunion {titulo} (hoy {hora}) · proyecto: {proyecto}"
minuta = "/minuta {titulo} ({fecha} {hora}) · proyecto: {proyecto}"
proyecto = "Carga el proyecto {nombre}: lee {documento} y dime en qué está y qué sigue."
pendiente = "{texto}"         # se escribe, sin enviar, al agente de un hilo ya abierto
pendiente_nuevo = "{texto}"   # primer mensaje de un hilo que se abre para el pendiente
contexto = true               # el agente recibe al empezar unas líneas sobre su hilo y los otros
sordina = true                # en Claude Code, una línea gris por edición y por comando, sin diffs
```

`sordina` decide si `telar agente instalar` carga en Claude Code la sordina (`src/telar/sordina/`), un mod
que baja el volumen de las herramientas: cada archivo editado es una línea gris con sus filas agregadas y
sacadas, y cada comando, una línea gris con lo que hace y cuánto imprimió, sin el diff ni la salida. Un
error, una interrupción o la vista expandida (ctrl+o) se ven enteros. Con `false`, no se carga.

`reunion` es lo que se le dice al agente cuando se pincha una reunión en la agenda del
dashboard (o con `telar reunion "<título>" HH:MM`): se abre un tab «◷ hora reunión» con
el agente, y ese es su primer mensaje. Marcadores: `{titulo}`, `{hora}`, `{fecha}`,
`{enlace}` y `{proyecto}`, que es la carpeta del perfil que comparte palabras con el
título; si no hay ninguna, la cola «· proyecto: …» se quita. El de fábrica es el de flow
y supone la skill `/preparar-reunion` instalada; cualquier otra skill o una instrucción
en prosa sirven igual. Se cambia desde **⚙ configuración** en la página, o con
`telar config --reunion "…"` (vacío vuelve al de fábrica).

`minuta` es lo mismo para una reunión que **ya empezó**: el clic en un evento pasado de la
agenda abre un tab «✎ hora reunión» con esa plantilla, para procesar lo que se dijo. De
fábrica supone la skill `/minuta`. Para otros tipos de evento, ver `[agenda]`.

## `[agenda]` — qué abre cada tipo de evento

```toml
[agenda.clase]
si = "clase|curso"              # expresión regular sobre el título, sin mayúsculas
antes = "/preparar-clase {titulo} ({fecha} {hora})"
despues = "/cerrar-clase {titulo}"   # opcional: sin ella, rige [agente] minuta
```

Cada evento de la agenda se clica. telar mira si ya empezó y busca, en orden, la primera
regla cuyo `si` calce con el título: `antes` si no ha empezado, `despues` si ya. Si ninguna
calza, o la que calza no trae ese momento, rigen las generales, `[agente] reunion` y
`[agente] minuta`. Mismos marcadores. `telar reunion "<título>" HH:MM --donde` dice qué
regla rige sin abrir nada; `--antes` y `--despues` fuerzan el momento.

`proyecto` es lo que se le dice al agente al abrir un proyecto desde la pantalla
**▤ proyectos** del dashboard (o con `telar proyectos abrir <ruta>`): se abre un tab con
el nombre de la carpeta, vinculado a ella, y ese es su primer mensaje. Si la unidad ya
tiene un hilo abierto, se va a él y no se le dice nada. Marcadores: `{nombre}` (el de
pantalla, según la `etiqueta` del perfil), `{ruta}` (relativa a la raíz), `{carpeta}` y
`{documento}` (absolutas). El de fábrica no supone ninguna skill; con una, algo como
`/pm {ruta}`. Se cambia desde **⚙ configuración** o con `telar config --proyecto "…"`.

`pendiente` y `pendiente_nuevo` son lo que se le dice al agente al llevarle un pendiente
(clic en la lista de tareas, o `telar pendiente <ref>`). Si el proyecto ya tiene su hilo,
se le **escribe** `pendiente` y no se envía: Enter es de la persona. Si hay que abrir uno,
el agente nace con `pendiente_nuevo` como primer mensaje, que sí se envía, porque no hay
a quién escribirle hasta que arranca. Marcadores: `{texto}`, `{ref}`, `{id}` (el id del
proveedor, como `T84`) y `{direccion}` (la del objeto, como `tarea:T84`: ver `telar objeto`);
un pendiente sin id, como los de los documentos, usa `{texto}`, y lo mismo con `{direccion}`
uno sin dirección (una casilla que nadie ha escrito, o el ítem de un proveedor que no es del tipo). Una
casilla que ya tiene id llena `{direccion}` con la suya (`pendiente:c-1a2b3c`), que quien recibe el mensaje
abre con `telar objeto`.
Una plantilla con los dos cae entera a `{texto}` si falta cualquiera: `"/tarea {id} ({direccion})"`
con el ítem de un proveedor `comando` (tiene id, no dirección) da su texto, no `/tarea X1 ()`. Una fila
que llega sin dirección (la foto de otra máquina con un telar de antes) la gana aquí solo si su
proveedor está declarado y activo en esta máquina con `tipo = "tipo"`; si no, también cae a `{texto}`.
Con la skill de flow: `pendiente = "Veamos {id}"` y `pendiente_nuevo = "/tarea {id}"`.

Con un agente declarado, `telar tejer` abre cada hilo con el agente adentro, retomando
la conversación que ese hilo ya tenía si su archivo sigue existiendo. En una sesión que
ya estaba tejida, `telar agente abrir --todos` lo pone en los hilos que no lo tengan, y
solo reemplaza **shells ociosas**: una shell sin procesos hijos. Lo que la persona dejó
corriendo no se toca.

Un hilo nuevo (el «+» de la barra, o `telar ir <nombre> --crear`) también nace ahí, con
su agente adentro. Sin esto nacía donde estuviera parado el servidor del multiplexor, que
suele ser «/».

`carpeta` decide dónde arranca el agente, no dónde vive el hilo: la ruta del hilo sale
de su vínculo, así que un agente que arranca en otra parte no se la cambia. Existe
porque hay agentes cuya memoria y configuración cuelgan de la carpeta donde arrancan
(Claude Code lee `CLAUDE.md` y `.claude/` desde ahí), y abrirlos en otra carpeta es
abrir a otro, que no recuerda nada.

Al salir del agente queda una shell, no se cierra el tab. Y el agente arranca sin lo que no
es suyo (`src/telar/entorno.py`): las variables de otro multiplexor (`ZELLIJ_*`: si tmux se
levantó desde dentro de Zellij, los ganchos de Zellij creerían que el agente es uno de sus
paneles), las marcas de la sesión de Claude Code que pidió abrirlo (`CLAUDECODE`,
`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, el socket de sus mensajes…: con ellas, el
Claude Code nuevo se cree su hijo y apaga su transcript) y el `TELAR_HILO` de quien lo pidió.
tmux le da a cada panel el entorno global de su servidor, que es el de quien lo levantó: por eso
el servidor que levanta telar nace sin eso, y `telar tejer` se lo borra al que ya estaba. La
configuración que la persona pone a propósito (`CLAUDE_CODE_USE_BEDROCK`, `ANTHROPIC_API_KEY`…)
pasa.

## `[atajos]` — teclas del dashboard

```toml
[atajos.m]
nombre = "⚑ correo"
mensaje = "/correo"
descripcion = "procesar el correo de hoy"   # opcional: sale al pasar el mouse
en = "correo"                               # opcional: dónde se muestra; "hoy" si falta
```

Cada atajo es una tecla del dashboard (y un enlace, en el lugar que diga `en`) que abre un
hilo nuevo con el agente, en `[agente] carpeta`, con `mensaje` como primer prompt. Sirve
para lo que se hace varias veces al día y no es de ningún proyecto: el correo, un chat,
cargar las horas. El hilo se llama `nombre` más la fecha y la hora («⚑ correo 09/23
10:32»), porque la revisión de la mañana y la de la tarde son dos conversaciones.

La tecla es un solo carácter. Si es una que ya usa el dashboard (`n` ahora, `t` te esperan, `v` tareas, `p`
proyectos, `r` recargar, `o` periódicos, `a` la agenda, `c` el correo, `/` buscar, o la de un bloque o
un proveedor con pestaña propia), la pestaña gana: el atajo se muestra sin tecla y se lanza con un clic, y
`telar doctor` lo avisa. Las filas de la agenda y de los pendientes no llevan tecla: se
clican.
`telar atajo` lista los declarados y `telar atajo m` hace lo mismo que la tecla.

`en` dice dónde se ve el atajo; la tecla funciona desde cualquier pestaña:

| `en` | dónde |
| --- | --- |
| `"hoy"` | no se muestra: va solo con su tecla (el dashboard ya no tiene barra arriba) |
| `"<clave>"` | el título del bloque `[bloques.<clave>]`, en su pestaña |
| `"seccion:<clave>"` | el título de la pestaña de esa sección |

`[atajos]` es la forma de antes: un `[disparadores.x]` con `tecla` da lo mismo (abajo), y `telar doctor` escribe
el que reemplaza a cada atajo. Se sigue leyendo.

## `[instruccion]` — a quién va lo que manda la pestaña de un módulo

```toml
[instruccion]
destino = "agente:vigia"     # o "hilo:<nombre>"; un agente, por su carpeta o por su nombre
```

La pestaña de un módulo (un chat, un correo) puede abrir la ventana de la instrucción con lo que está mostrando como
contexto (`window.lienzo.pedir("instruccion", …)`, [contratos.md](contratos.md), «telar seccion»). Si no dice a quién,
viene elegido `destino`: el agente que procesa lo que se le manda así. Se cambia en la misma ventana, y la instrucción
es opcional: vacía, al agente le llega el contexto con una línea que le pide procesarlo. Sin `destino`, la ventana
abre como sin entidad: con «un hilo nuevo» elegido. Vale para todas las pestañas; una que sabe mejor a quién va lo
dice en su pedido, y gana. Si el agente o el hilo no está, la ventana lo dice y hay que elegir.

## `[disparadores]` — lo que corre o manda algo solo: por un reloj, una tecla o un cambio

```toml
[disparadores.resumen]               # un reloj: como un proceso de periodicos.toml
cuando = "30 8 * * 1-5"
comando = "~/bin/resumen --corto"
descripcion = "el resumen de la mañana"

[disparadores.correo]                # una tecla del dashboard: como un [atajos.m]
tecla = "m"
mensaje = "/correo"
hilo = "⚑ correo"                    # el nombre del hilo; por defecto, el del disparador
aparece = "correo"                   # dónde se muestra: "hoy" (por defecto), la clave de una vista o "seccion:<clave>"

[disparadores.tablero]               # al cambiar: cuando alguna máquina anuncia `telar cambio tareas`
al = "cambio:tareas"
comando = "~/bin/tablero --rehacer"
```

Un disparador dice **cuándo** con una sola de tres claves, y **qué** con un `comando` (una línea de bash) o un
`mensaje` (un prompt: abre un hilo con el agente, o se le encarga a `agente`, un residente):

| cuándo | es | acepta además |
| --- | --- | --- |
| `cuando` | un horario cron, como en `periodicos.toml` | `agente`, `hilo`, `max_abiertos`, `argumentos`, `carpeta`, `descripcion`, `activo` |
| `tecla` | un carácter: la tecla del dashboard, como en `[atajos]` | solo `mensaje`, y `agente`, `hilo`, `descripcion`, `aparece`, `activo` |
| `al` | `"cambio:<tema>"`: un `telar cambio <tema>` de cualquier máquina | lo mismo que `cuando` |

El nombre (la clave de la tabla) va en el crontab y en el archivo de su última corrida: minúsculas, números, `-`
y `_`, y no puede ser el de un proceso de `periodicos.toml` o de un módulo (salvo el de una tecla, que no anota
corridas). Si lo es, el disparador no corre (el proceso sí, y los demás también) y `telar doctor` lo marca como
falla; `telar periodicos nuevo` no acepta el nombre de un disparador.

- **Un reloj** es un proceso más de `telar periodicos`: se lista, corre y anota igual, pero no se escribe en
  `periodicos.toml` ni se cambia con `editar`, `pausar` o `borrar` (se cambia aquí). Después de agregarlo,
  `telar periodicos aplicar` lo pone en el crontab; `telar doctor` avisa si falta ahí.
- **Una tecla** es un atajo: `telar atajo`, `/atajos` y el dashboard la ven igual que un `[atajos.x]`. Una tecla
  en las dos formas, o en dos disparadores, es un error. Con `activo = false` la tecla no existe.
- **Un cambio** lo corre el nodo (`telar serve --nodo` o `telar nodo`), así que pide el bus: sin él no hay quién
  lo oiga, y `telar doctor` lo dice. Corre como un periódico (su última corrida se ve en `telar disparadores` y
  en `<estado>/periodicos/<nombre>.json`), con freno: uno a la vez por disparador, y lo que llega mientras corre
  deja **una** corrida pendiente; 30 s entre corridas; 12 por hora como mucho (pasado eso se frena hasta que la
  hora corra, y el registro del nodo lo dice una vez). El nodo lee los disparadores al arrancar: uno nuevo pide
  reiniciarlo.

Los de reloj y los de cambio corren en la máquina donde corren los periódicos (`[periodicos] en`, o esta si no
dice), con la configuración de esa máquina. `telar disparadores` los lista (`--json`, en
[contratos.md](contratos.md)) y `telar disparadores correr <nombre>` corre uno ya, para probarlo. El diseño y lo
que falta están en [propuestas/disparadores.md](propuestas/disparadores.md).

## `[vistas]` — qué se muestra y dónde aparece

```toml
[vistas.correo]                      # una pestaña del dashboard
aparece = "pestana"
comando = ["/ruta/a/mi-correo", "--json"]
color = "rojo"
tecla = "e"

[vistas.vivero]                      # una app: un HTML autocontenido
archivo = "~/proyectos/plantas/dist-app/vivero.html"
memoria = "~/.local/state/vivero.json"

[vistas.atlas]                       # una app: una página servida
url = "http://servidor:8790"

[vistas.juego]                       # una app que arma un comando
aparece = "apps"
comando = ["/ruta/juego/casa"]

[vistas.diario]                      # un grupo en la lista de hilos, con su página
hilos = ["notas", "◌ rato*"]
comando = ["/ruta/a/mi-home", "--json"]

[vistas.plan]                        # lo que una skill deja por día: táctica y el calendario lo leen
carpeta = "~/notas/planes"
en = "servidor"
comentar = ["~/bin/plan-comentario"]

[vistas.semana]                      # el resumen de la semana, en la misma carpeta: semana-AAAA-MM-DD.md
carpeta = "~/notas/planes"
en = "servidor"
prefijo = "semana-"

[vistas.pulso]                       # una pasada cada hora: la página muestra la última que no has visto
carpeta = "~/.local/state/telar/pulso"
en = "servidor"
pasadas = "pulso"
```

Una vista es una **fuente** y un **lugar**. La fuente es una sola de `comando` (imprime el JSON de una
página, el contrato de `telar seccion`), `archivo` (un `.html` autocontenido), `url` (una página servida) o
`carpeta`/`en` (un `AAAA-MM-DD.json` por día; `en` es la máquina donde vive). El lugar es `aparece`:

| `aparece` | qué es | claves, además de `nombre` | antes era |
|---|---|---|---|
| `pestana` | una pestaña del dashboard | `comando` (obligatorio), `color`, `tecla`, `dentro` | `[bloques.x]` |
| `apps` | una línea del menú de apps, en la cabecera | una de `comando`, `archivo` o `url`; `descripcion`; `memoria` (solo con `archivo`) | `[apps.x]` (`comando` era `pagina`) |
| `hilos` | un grupo en la lista de hilos | `hilos`; `comando` si tiene página | `[secciones.x]` (`comando` era `home`) |
| `dia` | lo que la página pide por su clave (táctica y el calendario piden `plan`; otra, con `telar resultado <clave>`) | `carpeta` y/o `en`, `comentar`, `prefijo`, `pasadas` | `[resultados.x]` |

`aparece` se puede callar cuando las claves dejan un solo lugar: `archivo` o `url` son una app, `hilos` es un
grupo, `carpeta`, `en` o `prefijo` es un resultado por día. `prefijo` es lo que va antes de la fecha en el nombre de
cada archivo (`semana-` lee `semana-AAAA-MM-DD.md`): así dos resultados comparten una carpeta. El día
`ultimo` pide el más reciente que hay (`telar resultado semana ultimo`): el resumen de la semana lleva la fecha
de su lunes, y no hay uno por día. `pasadas` hace de cada día una lista que se va llenando: una skill que corre
varias veces al día (la pasada de Secretaría, cada hora) agrega cada vez una con `telar resultado <clave> --agregar`,
validada contra su esquema (`pulso`, o `libre`, que solo pide su id), y la página muestra debajo de la franja de
avisos la última que la persona no ha visto; un clic la abre entera y al cerrarla queda vista. Hasta cuál vio lo
lleva la máquina donde vive (`en`), así que vale igual en el laptop y en el teléfono. Con `[mundos]`, cada cosa de una
pasada es de un mundo (el de su tarea, o el que dijo el agente) y lo de un mundo solo se ve, y se marca visto, con ese
mundo puesto; el mundo de cada cosa lo decide la configuración de esa máquina, que tiene que declarar los mismos mundos
que la de la página (contratos.md, «`telar resultado <clave> --agregar`»). Con `comando` solo, que sirve en cuatro lugares, hay que
decirlo. Cada valor se valida igual que en su tabla de antes (los colores, la tecla, las rutas), y los errores
nombran la vista: `vistas.correo.color: …`. `en` es siempre la máquina, como en `[tipos]` o `[notas]`.

`aparece = "plan"` (arriba de la pestaña del plan) se retiró con esa pestaña (18-nov-2026): una vista que lo dice
no rompe la configuración, pero se deja fuera, y `telar doctor` lo avisa. Lo mismo un `[bloques.x]` con `en =
"plan"` o `dentro = "plan"`. El plan como dato (`[vistas.plan]`, `telar resultado plan`) sigue: táctica cruza sus
bloques con la agenda y el calendario los dibuja.

La clave es el nombre de siempre: un atajo la nombra igual (`[atajos.m] en = "correo"`, `en =
"seccion:diario"`), y las órdenes también (`telar bloque correo`, `telar app vivero`, `telar seccion diario`,
`telar resultado plan`).

**Las tablas de antes se siguen leyendo.** `[bloques]`, `[apps]`, `[secciones]` y `[resultados]` valen como
siempre, y al leer la configuración cada vista se traduce a la suya, así que lo demás (las órdenes, la API, la
página, `telar config --json`) es lo mismo con una forma que con la otra. Se pueden mezclar mientras se
cambia: en cada lugar van primero las de antes, después las vistas en el orden del archivo, y al final lo que
aportan los módulos. Un mismo nombre en las dos formas (`[vistas.correo]` y `[bloques.correo]`) es un error,
y también un módulo que se llama como una vista, aporte a donde aporte. `telar doctor` dice cuáles quedan de
antes y escribe la vista que las reemplaza, lista para copiar. Una clave declarada en dos tablas de antes
(`[bloques.x]` y `[apps.x]`, como las arma un módulo) no cabe en una vista, que es una sola cosa: se queda
como está. Los módulos siguen declarando `[pestana]`, `[app]` y `[resultado]` en su `modulo.toml`.

El diseño y lo que falta están en [propuestas/vistas.md](propuestas/vistas.md).

## `[bloques]` — pestañas del dashboard que llena un comando

La forma nueva es `[vistas.<clave>]` con `aparece = "pestana"`; esta se sigue leyendo.

```toml
[bloques.correo]
nombre = "correo"
comando = ["/ruta/a/mi-correo", "--json"]
color = "rojo"        # azul, amarillo, verde, rojo, magenta, cian o violeta; cian si falta
tecla = "e"           # opcional: la tecla de su pestaña

[bloques.gantt]
nombre = "gantt"
comando = ["/ruta/a/gantt", "pagina"]
dentro = "proyectos"  # opcional: una subpestaña de «proyectos», no una pestaña propia
```

Cada bloque es una pestaña del dashboard, después de «tareas», con su nombre. Con `dentro = "<pestaña>"` es una
subpestaña de una de las fijas (`ahora`, `tareas`, `proyectos` o `calendario`): arriba de esa pestaña aparece una
fila con su nombre y el de cada subpestaña («proyectos · gantt»), la barra de la izquierda sigue marcando la fija,
y su comando corre solo cuando se abre (un Gantt no se recalcula cada 5 minutos para nadie). `en = "plan"` (arriba
de la pestaña del plan) y `dentro = "plan"` se retiraron con esa pestaña: el bloque se deja fuera y `telar doctor`
lo avisa; otro valor de `en` es un error. El comando imprime
una página con el contrato de `telar seccion` (ver [contratos](contratos.md#telar-bloque-clave---json))
y el dashboard muestra sus ítems como filas: marca, hora, `texto` y `titulo`; los bloques de la
página que traen `lienzo` (un gráfico) o `texto` se muestran arriba de las filas, como en una página. Se pide con el
ritmo de la red (cada 5 minutos, o con `r`), no en cada refresco. Los atajos con
`en = "<clave>"` van en su título: el correo y la tecla que lo procesa, juntos.
Un ítem con `mensaje` o `tareas` se puede clicar: se abre solo, en la misma pestaña, con las
tareas que nacieron de él (`tareas`: `[{"proveedor": "tareas", "id": "T366", "estado": "activa"}]`;
cada una abre su ficha, y al cerrarla se vuelve al ítem) y, si trae `mensaje`, un botón que abre un
hilo nuevo con el agente para esa fila, como un atajo pero para un solo correo.
Los ítems con el mismo `grupo` (los correos de una conversación) van anidados bajo el primero de la
lista, con ▸ y cuántos son; el clic en ▸ despliega los demás.
Con 8 filas o más, el bloque lleva un buscador en una línea bajo su título: filtra mientras se escribe, por `texto`,
`titulo`, los códigos de sus `tareas` y `busca`, un texto que no se muestra (las direcciones y los nombres de quienes
escriben y reciben un correo). Cada palabra tiene que estar; una conversación plegada aparece si alguno de sus ítems
calza.
Un ítem con `id` muestra además su detalle al abrirlo (el cuerpo de un correo, cinco líneas y «ver
todo»): el dashboard corre `telar bloque <clave> --item <id>`, que llama al comando del bloque con
`--item <id>` al final; el comando imprime `{"texto": "…"}`. Se pide al abrir el ítem, no en cada
lectura del bloque. Con `enlace`, el título del ítem abierto lleva al original, en una pestaña nueva.
(`reusar`, que pedía abrirlo en la pestaña de Chrome ya abierta, se acepta pero ya no hace nada: lo hacía
la extensión de VS Code.)

## `[repos]` — los repositorios de trabajo

```toml
[repos.vida]
ruta = "~/vida"
[repos.trabajo]
ruta = "~/vida/trabajo"           # puede estar dentro de otro
[repos.telar]
ruta = "~/vida/proyectos/telar"
perfil = "~/notas/perfil.yaml"   # opcional: si su perfil no está en su carpeta
```

Una `ruta` relativa se lee desde `raiz`, no desde el directorio donde se corre la orden, y así, absoluta, la
dan `telar config --json` y `TELAR_REPOS` (lo que reciben los módulos). Los hilos trabajan en carpetas de uno u otro repositorio, y cada uno trae su perfil (`.telar/perfil.yaml` en su
carpeta): qué es ahí una unidad de trabajo. telar los junta en uno (`docs/perfil.md`, «Varios repositorios»).
Si dos perfiles reconocen la misma carpeta, gana el del repo más profundo: el de un repo del equipo dentro del
de vida describe lo suyo. Un repo sin perfil no aporta nada, y uno fuera de `raiz` todavía no se suma. Sin
`[repos]`, solo cuenta `raiz`, como siempre. `telar doctor` avisa de las dos cosas: el repo que queda fuera de
`raiz`, y las carpetas que reconocen los perfiles de dos repos, con el que gana (el perfil de `raiz` cuenta
solo si `raiz` misma está en `[repos]`: que nombre las carpetas de un repo de adentro es lo previsto).

## `[remotos]` — máquinas donde pueden vivir hilos

```toml
[remotos.casa]
destino = "usuario@servidor"   # lo que va después de mosh/ssh; puede ser un alias de ~/.ssh/config
transporte = "mosh"            # mosh (por defecto) · ssh
raiz = "~/repo"                # la carpeta del repositorio EN esa máquina
directorio = ""                # opcional: la carpeta común donde cada persona publica sus hilos
repos = ["~/repo", "~/repo/otro"]  # opcional: repositorios que viven en las dos máquinas (telar desplegar)
sesion = ""                    # opcional: la sesión del telar EN esa máquina; "" es la misma que aquí
```

Un hilo remoto es uno cuyo agente vive en otra máquina, siempre encendida, y sigue
trabajando con el laptop cerrado; la ventana local solo lo mira.

Allá el hilo es **una ventana de la sesión del telar**, como cualquier hilo de esa máquina,
marcada con un id propio (`@telar_id`). Aquí, una ventana que corre

```
mosh usuario@servidor -- bash -lc '<mirar la ventana @338 con marca 1a2b3c4d>'
```

y lo que corre allá es una **sesión agrupada** con la del telar (`ver-338-<esta máquina>`), fija
en esa ventana: comparte las ventanas pero elige la suya, así que el laptop y el celular pueden
mirar hilos distintos sin moverse uno al otro. Si la ventana muere, la sesión suelta a quien
mira (la ventana local se cierra en vez de mostrar otro hilo); si nadie la mira, desaparece.
La dirección del hilo (`@338/1a2b3c4d`) se guarda en el estado (`remotos.json`): renombrar el
hilo no la pierde, y una marca que no coincide (tmux reusa los `@N` al reiniciarse) no se mira.
La carpeta del hilo se traduce: su vínculo relativo a la raíz local es la misma relativa bajo
`raiz` de allá.

Con bus, el nodo de cada máquina publica la dirección de sus hilos y el de aquí trae las
ventanas que faltan, sigue a un hilo que cambió de dirección o de nombre allá (el nombre lo pone
la máquina donde vive) y cierra la ventana de uno que terminó. Los hilos de antes, con sesión
tmux propia allá (`telar-1a2b3c4d`), se siguen mirando mientras existan.

- Crear: `telar ir <nombre> --crear --remoto casa`, o en la página «+ nuevo», que pregunta
  dónde si hay algún remoto declarado. La ventana queda con la opción tmux `@telar_remoto`.
  Allá el agente arranca donde diga `[agente] carpeta`: «hilo» es la carpeta del hilo
  traducida a la raíz de allá, «raiz» la raíz de allá, y una ruta del hogar de aquí
  (`~/notas`) es la misma bajo el hogar de allá.
- Llevar: `telar hilo llevar [remoto]`, o «Llevar a otra máquina…» en el menú del hilo,
  pasa un hilo local a la otra máquina con su conversación: cierra el agente de aquí, copia
  la conversación allá (a la carpeta de proyecto donde Claude Code la busca) y abre el hilo
  como remoto retomándola. **La conversación viaja, los archivos no**: revisa la raíz, la
  carpeta del agente, la del hilo y cada uno de `repos` (un repo anidado, como uno de la
  empresa dentro del repo personal, no se ve desde el de afuera). Si alguno tiene algo sin
  commitear o sin subir, lo dice y pide confirmar (`--si` para no preguntar). Aquí queda la copia de cómo estaba la conversación al irse.
- Cerrar (✕) y archivar con `--cerrar` terminan también el hilo de allá; retomar un
  archivado lo recrea retomando su conversación.
- `telar doctor` revisa cada remoto: que responda por ssh, que tenga tmux (y mosh-server
  si el transporte es mosh), y avisa si su tmux muestra barra.

Para que no se vean dos barras ni se coma el prefijo, el tmux de la otra máquina va con
`set -g status off` y `set -g prefix None` en su `~/.tmux.conf`. La atención y la ficha del
agente remoto (lo que escriben sus ganchos) todavía no llegan al laptop.

### `telar desplegar`: el repositorio en cada máquina

`telar desplegar` (docs/desarrollar.md, «Llevarlo a las máquinas») lleva la rama principal de un repositorio a esta
máquina y a cada una de `[remotos]`, y reinicia en cada una lo que el repositorio declara en `.telar/despliegue.yaml`
(docs/perfil.md, «El despliegue»). De cada máquina usa solo lo que ya está declarado o lo que se ve allá; no hay
claves nuevas:

- **Cuál es**: esta, con su nombre en el bus (`[bus] maquina`, o el de la red), y cada `[remotos.<nombre>]`, por ssh a
  su `destino` (sin preguntar claves: `BatchMode`). `--maquina <nombre>` despliega solo en esa.
- **Dónde vive allá el repositorio**: en orden, la misma carpeta relativa a la raíz (la de aquí relativa a `raiz`,
  bajo el `raiz` del remoto), la misma relativa al hogar, cada una de su `repos`, y lo que dice el telar de allá
  (`telar config --json`: su raíz, sus `[repos]` y las carpetas de sus módulos). Vale la primera que sea la raíz de un
  repositorio git que comparte sus primeros commits con el de aquí: un módulo que aquí está dentro de la raíz y allá
  en `~/src` se encuentra igual, y una carpeta con otro repositorio no se confunde con este. Una máquina donde no está
  se salta («no vive allá», con dónde buscó).
- **Con qué se cuidan sus servicios**: launchd en macOS (`launchctl kickstart -k gui/<uid>/<etiqueta>`), systemd de
  usuario donde haya `systemctl` (`systemctl --user restart <unidad>`). Un servicio declarado que no está instalado
  en esa máquina no se reinicia allá.
- **La página de cada una**: lo que dice su `telar serve` por su socket (`/salud`, `web`: dónde sirve la página con
  `--web`), con la llave de esa máquina (`~/.config/telar/panel.llave`), que no sale de ella.
- **Lo que corre**: `refs/telar/desplegado`, en la copia del repositorio de cada máquina.

### El correo entre agentes

Si la otra máquina entrega correo local entre agentes (ver
`servidor/README.md`), cada hilo remoto tiene su dirección:
`usuario+<nombre del hilo>@servidor`, con el nombre en minúsculas, sin acentos y con guiones
(«T42 Faro Norte» → `usuario+t42-faro-norte@servidor`). La sesión de allá lleva su nombre
en la opción tmux `@telar_hilo`, que es por donde el servidor sabe a quién entregar.

- Lo que el panel mostraba del correo (✉, la pestaña de la ficha, la Maildir de la pantalla «correo»)
  se retiró, con `telar correo` sin verbo y `correo leido`: entre los hilos de una misma persona habla el
  bus (`telar mensaje`), y la pantalla «correo» del dashboard (tecla `c`) muestra esos mensajes. Queda
  escribirle a otra persona, hasta que el bus cruce personas (docs/propuestas/telar-para-otros.md):

- `telar correo enviar usuario+hilo@servidor -s "asunto" [--responde "<id>"]`, con el cuerpo
  por la entrada estándar, le escribe a un hilo de otra persona u otra máquina: desde el
  laptop por ssh (el remitente queda verificado como el usuario de ssh), en el servidor con
  `mail`. Con `--responde` pone `In-Reply-To` y `References`, y así la respuesta queda en la
  misma conversación.

### El directorio

En el servidor nadie ve las sesiones de los otros. Con `directorio`, cada telar publica ahí
sus hilos de esa máquina (nombre, dirección, carpeta vinculada y el **título** de su
documento; no su estado, que suele traer lo que no se cuenta afuera), un archivo por
persona, al crear, renombrar, archivar o cerrar un hilo remoto. `telar directorio` los lee
todos, y descarta un archivo cuyo dueño no es el usuario de su nombre. `telar directorio
publicar` lo hace a mano. La carpeta la monta quien administra el servidor (ver
`servidor/README.md`).

### Ver los hilos de otra máquina (`telar espejo`)

Un laptop se apaga y un servidor no. Para ver desde una máquina —y desde el panel en el celular— qué
hilos tiene la otra y cuáles esperan algo, **el nodo de cada una** (`telar nodo`) publica una foto de sus
hilos en el bus cada 30 s, y las demás la guardan con la hora en que llegó. Basta con `[bus]`.

```
telar espejo ver                    # qué fotos hay y cuánto hace que llegaron
```

Solo viajan los hilos —nombre, semáforo, carpeta relativa, prioridad, tiempo y el título de su
documento—; ninguna conversación ni el estado del proyecto. Una foto con menos de 2 minutos está
**en línea**; pasado eso la máquina se da por apagada y se sigue mostrando la última, atenuada y con
su edad. Es de solo lectura (para entrar a un hilo de la otra máquina, `telar hilo llevar`). El contrato
está en `docs/contratos.md`.

## Entre máquinas, por el bus: leer un hilo, un aviso, un archivo

Lo que antes hacía «la puerta» (`telar enlace`, una llave ssh atada a un comando) lo hace el bus, y la
puerta se retiró (`[enlaces]` y `[enlace] verbos` se aceptan y no se usan):

| | |
| --- | --- |
| leer los últimos turnos de un hilo de otra máquina | `telar hilo leer <hilo> --maquina <máquina>` |
| escribirle | `telar mensaje <hilo> "…"` |
| encargarle algo a un agente de otra máquina | `telar encargar <agente> "…"` |
| un aviso en su pantalla | `telar aviso "…" [--a <máquina>]` (sin `--a`, a las otras en línea) |
| un archivo a su carpeta de entrada (hasta 25 MB, en trozos) | `telar archivo <ruta> --a <máquina>` |

```toml
[bus]
entrada = "~/telar-entrada"          # dónde caen los archivos que llegan (antes, [enlace] entrada)
no_leer = ["personal", "Diario"]     # hilos que otra máquina no puede leer: por nombre o carpeta (glob)
```

`telar hilo leer [hilo] [--ultimos N]` muestra los últimos N turnos (5 si no se dice, 50 a lo más): lo que se
le pidió y lo que contestó el agente, con cada herramienta en una línea —cuál y sobre qué, sin su salida—. Todo
con tope: 4000 caracteres por mensaje y 60 000 en total. Un patrón de `no_leer` vale contra el nombre del hilo y
contra su carpeta (y una carpeta veta también lo de abajo); un hilo vetado responde igual que uno que no existe.
Un archivo que llega nunca pisa a otro ni escapa de la carpeta de entrada.

## `periodicos.toml` y `[periodicos]` — lo que corre solo cada cierto tiempo

Los procesos periódicos de una máquina (la que no se apaga, normalmente un servidor) viven en
`periodicos.toml`, **al lado de `config.toml`** de esa máquina. Cada uno es una tabla con su nombre
(minúsculas, números, `-` y `_`), un horario cron y **o** un comando de shell **o** un prompt:

```toml
zona = "America/Santiago"            # la hora en que se leen los horarios (por defecto, la de la máquina)

[resumen]
cuando = "30 8 * * 1-5"              # minuto hora día-del-mes mes día-de-la-semana (o @daily, @hourly…)
comando = "~/bin/resumen --corto"    # una línea de bash; su salida va al log
descripcion = "el resumen de la mañana"

[correo]
cuando = "0 9-19/2 * * *"
mensaje = "/correo"                  # abre un hilo con el agente haciendo esto, que se puede mirar
hilo = "✉ correo"                    # su nombre (se le agrega la fecha y la hora)
padre = "Secretaría"                 # cada hilo que abre cuelga de ese en la barra, hereda sus etiquetas y le avisa
max_abiertos = 2                     # con tantos sin cerrar, esta vez no abre otro
argumentos = ["--permission-mode", "acceptEdits"]   # para el agente, después del prompt
carpeta = "~/trabajo"                # dónde corre (por defecto, el hogar)
activo = false                       # pausado

[plan]
cuando = "30 20 * * 0-4"
mensaje = "/planear"
agente = "secretaria"                # se le encarga a ese agente residente: su sesión de siempre, no un hilo nuevo
despues = ["retro"]                  # usa lo que deja otro proceso: se dibuja en el calendario (cron no espera)
```

`telar periodicos` los lista con la próxima y la última corrida; `nuevo`, `editar`, `pausar`,
`activar`, `borrar` y `zona` los cambian y reescriben el crontab al tiro; `ahora` corre uno ya;
`log` muestra su salida; `calendario [--desde AAAA-MM-DD] [--dias 7]`, lo que corrió (con cómo
salió) y lo que viene, día por día. Cada corrida terminada queda en
`<estado>/periodicos/<nombre>.historial.jsonl` (las mil últimas); de antes del historial, el calendario
lee las horas en el log.

Las dependencias son de dos clases. Una se declara, `despues`: los procesos cuyo resultado usa este
(el plan de la noche lee la retrospectiva de la tarde). Es para verla: cron no espera a nadie. La otra
se deduce: los que van a un mismo agente comparten su casilla, y el que llega mientras el agente
trabaja espera su turno. Un comando que encarga (`telar encargar secretaria …`, en la línea o en el
script que corre) cuenta como de ese agente.

En la página, ⚙ configuración › periódicos (tecla `o` en el dashboard) los muestra en un calendario de
un día o de una semana: cada proceso es una fila con su línea, agrupada por a quién le llega, y cada
corrida un círculo en su hora (lleno y tenue, corrió; un aro, viene; rojo, falló; en el color de
cuidado, le tocaba y no corrió, o llega a la casilla de su agente menos de 15 minutos después de otra).
Elegir uno dibuja sus dependencias y dice lo que es; el formulario crea uno con una skill y lo que va
después (una de las dos, o las dos), a quién se le encarga (un agente o un hilo nuevo, y de qué hilo
cuelga ese hilo nuevo), cuándo y qué otros usa. En el crontab, telar maneja **solo un bloque entre marcas** (`# >>> telar
periodicos` … `# <<< telar periodicos`), al final, y no toca lo de afuera. Cada línea llama a
`telar periodicos correr <nombre>`, que anota la corrida en `<estado>/periodicos/`. Un `mensaje`
abre una ventana de la sesión del telar, como cualquier hilo, así que otra máquina la trae a su lista. Cada cambio guarda la versión anterior en `periodicos.toml.anterior`.

Lo mismo se puede declarar en la configuración, `[disparadores.x]` con `cuando` (arriba): se ve y corre aquí
igual, pero se cambia en la configuración. `periodicos.toml` se sigue leyendo y es lo que escriben `telar
periodicos` y la página.

En **la otra máquina** (el laptop), `[periodicos] en` dice dónde viven, y la orden y la sección
«periódicos» de ⚙ configuración (tecla `o` en el dashboard) los ven y los cambian allá, por ssh:

```toml
[periodicos]
en = "servidor"                      # el nombre de un [remotos.<nombre>]
```

## `[avisos]` — lo que un programa dice en un archivo, en la franja de avisos

Un programa que mira algo solo (un agente, un chequeo periódico) deja en un JSON cómo está, y la franja de avisos de la
página (arriba de la barra de hilos) dice su línea mientras no esté bien. Cada fuente, una tabla con el archivo y, si
vive en otra máquina del bus, cuál (`telar.avisos`):

```toml
[avisos.equipo]
archivo = "~/.local/state/chequeo/aviso.json"   # en la máquina donde vive (con ~, el de quien corre telar allá)
en = "laptop"                                   # opcional: la máquina del bus; sin ella, esta
```

El archivo:

```json
{"nivel": "aviso", "linea": "el disco está al 92%", "fecha": "2026-11-18T15:30:00",
 "informe": "/ruta/al/informe.md", "sugerencias": 3, "problemas": ["disco", "swap"]}
```

`nivel` es `ok`, `aviso` o `mal`: `aviso` sale en el color de cuidado y `mal` en rojo (el nivel «problema» de la franja,
que a diferencia de «sin conexión» no calla a los demás), con su `linea` y cuándo se midió (`fecha`; sin ella, cuándo se
escribió el archivo). Un clic abre `informe` (un `.md`) en el visor de documentos, en la máquina donde vive, aunque esté
fuera de la raíz; `sugerencias`, si viene, se cuenta en la lista. Un archivo que dice `ok`, que no está, que no se
entiende o que es de hace más de una hora (el programa dejó de correr) no dice nada. La página los pide cada minuto
(`GET /avisos`); los de otra máquina, a su nodo por el bus (`avisos-archivo`), que solo entrega los archivos que su
propia configuración declara como suyos: en esa máquina, la misma tabla sin `en`.

**Darlo por visto.** Abrir el informe desde la franja, o el ✓ de su línea en la lista, lo da por visto: deja de salir
mientras sea el mismo aviso. Con `problemas` (una lista de ids estables de lo que está mal: los elige el programa, y
tienen que ser los mismos de una vez a la otra), es el mismo mientras los de ahora sean los vistos o menos y el nivel no
suba; sin `problemas`, mientras el nivel no suba (otra `linea` con el mismo nivel es el mismo aviso). Sale de nuevo si
aparece un problema que no estaba, si pasa de `aviso` a `mal`, o si el archivo dijo `ok` entre medio (eso olvida lo
visto; lo nota quien lee el archivo y el nodo de esa máquina, cada 30 s). Lo visto se guarda en la máquina donde vive el
archivo (`<estado>/avisos-vistos.json`; el de otra máquina se marca allá por el bus, `avisos-visto`), así que vale igual
en el laptop y en el teléfono. Se guarda lo que la página mostró: si el archivo agregó un problema entre medio, ese
sigue saliendo.

## `[terminal]` — cómo se ve la terminal de un hilo en la página

```toml
[terminal]
columnas = 130          # hasta cuántas columnas de ancho (40 a 400), o 0: todo lo que quepa
posicion = "centro"     # izquierda, centro o derecha, si sobra espacio
fondo = "ninguno"       # ninguno (el fondo del tema), un color "#11111b", "imagen:~/fondos/a.jpg" o "imagen:https://…",
                        # o el nombre de un módulo que trae [fondo] (docs/modulos.md)
```

Lo mismo, en la página: ⚙ → terminal, que lo escribe aquí y lo aplica al tiro a las terminales abiertas. La ventana
del hilo toma el ancho de la terminal (la vista se lo da a tmux). Es de la máquina que sirve la página.

`columnas` es el ancho de fábrica: en la página, el borde de la terminal (el derecho; el izquierdo si va a la derecha)
se arrastra, y lo arrastrado lo pisa en ese navegador y en esa pantalla (de 80 columnas, o lo que quepa, a todo el
centro; un doble clic en el borde vuelve a `columnas`). Cambiar el ancho en ⚙ → terminal olvida lo arrastrado.

## `[modos]` — modos de la página: táctica, estrategia, foco, todo y los propios

Un modo es una actitud ([propuestas/orden-por-modos.md](propuestas/orden-por-modos.md)): un nombre con valores para la
disposición de la página, la terminal y los avisos, y qué filas de DASHBOARD se ven; cambiar de modo los aplica todos
de una vez. Vienen cuatro de fábrica: «tactica» (decidir y hacer; la de partida), «estrategia» (mirar con calma: abre en
proyectos, con el tablero y las decisiones —módulos tablero y registro— al lado; su pantalla propia se sacó el
19-nov-2026), «foco» (solo la terminal, al centro, sin nada alrededor) y «todo» (ver y buscar todo, sin filtros ni
topes). Una tabla con el nombre de uno de ellos lo cambia, y una con otro nombre suma uno, armado sobre uno de los
cuatro (`base`, «tactica» si no lo dice). Lo que un modo no dice, lo toma de su base y de «tactica»; la terminal de
«tactica», de `[terminal]`. Qué agentes se ven (`agentes`) no se hereda: cada modo dice los suyos. «estandar», el de
antes, sigue valiendo: `[modos.estandar]` se lee como `[modos.tactica]`.

Qué pestañas de DASHBOARD ve cada modo (`filas`) se elige en ⚙ modos › pestañas, una fila por modo: un clic prende o
apaga una y lo escribe al tiro en `[modos.<n>] filas` (si es el modo puesto, la barra cambia sin recargar); «todas» es
`*`, y si lo elegido queda igual a lo de fábrica o de su base, la línea se quita. Se combina con `[dashboard]` (⚙ pestañas)
así: una pestaña oculta ahí no se ve en ningún modo, aunque el modo la nombre; de las demás, cada modo ve las que nombra,
en el orden en que las nombra (la primera es la vista a la que lleva ponerlo), y un modo con `*` las ve todas en el
orden de `[dashboard] orden`. La que se agrega desde la fila entra tras la que la precede en ese orden. La API niega una
clave que no es una pestaña de hoy (salvo una que el modo ya nombraba: la de un módulo desinstalado se conserva).
⚙ mundos dice, bajo los modos de cada mundo, qué pestañas quedan en él: la unión de las de sus modos.

```toml
[modos.tactica]
filas = "tactica, calendario"   # las pestañas de DASHBOARD, por su clave (bloque:correo, pestana:leer…); * todas

[modos.revision]
base = "estrategia"
nombre = "revisión"
barra = "plegada"

[modos.oficina]
mundo = "trabajo"          # al ponerse, pone este mundo de [mundos] (a mano, hasta el próximo cambio del horario)
```

Los ajustes, con lo que vale cada uno:

```toml
[modos.lectura]
nombre = "lectura"
barra = "plegada"          # abierta, plegada u oculta
lado = "abierto"           # la ficha de un agente: abierto, plegado u oculto
cabecera = "visible"       # visible u oculta (oculta: su ícono arriba a la derecha vuelve al modo de antes)
acciones = "visible"       # la barra del hilo: visible u oculta
escribir = "visible"       # la caja bajo la terminal: visible u oculta
pantalla_completa = "no"   # no o si
columnas = 100             # como en [terminal]
posicion = "izquierda"
fondo = "ninguno"
avisos = "urgentes"        # los de abajo a la derecha: todos, urgentes (no los informativos) o ninguno
aviso_version = "oculto"   # la versión y la página nuevas, en la franja de avisos: visible u oculto
tema = "telar"             # los colores: telar (catppuccin mocha), latte (claro), riso, papel, o brasa, rescoldo y ámbar
                           # (los de la noche), o uno propio de [temas]; /componentes los muestra. El de un mundo le
                           # gana ([mundos.<n>] tema), y los colores de un tema se cambian en [temas.<tema>]
densidad = "auto"          # el alto de las filas: compacta, comoda, amplia (para el dedo) o auto (amplia en pantalla táctil)
icono = "bandeja"          # el de su botón en la banda (un ícono de la página por su nombre); vacío, el de su base
etiquetas = ""             # solo los hilos con alguna de estas etiquetas, separadas por coma; "" todos
sin_etiqueta = "se-ven"    # con etiquetas puestas, los hilos sin ninguna: se-ven o no-se-ven
agentes = "vigia, cartero" # los agentes residentes de AGENTES, por su carpeta; "" todos, "-" ninguno (no se hereda)
proyectos = ""             # qué tipos de unidad (arquetipos) lista la pantalla de proyectos; "" todas
negocios = ""              # qué tipos de unidad son negocios: la subvista «comercial» de proyectos; "" ninguno
iniciativas = ""           # qué tipos de unidad son iniciativas internas: la subvista «interno»; "" no hay
agrupar_iniciativas = ""   # con qué campo del frontmatter se agrupan, {frontmatter:<clave>} (o varios, en orden); "" sin agrupar
area = ""                  # sin uso desde que se sacó la pantalla estrategia (19-nov-2026): se lee, no hace nada
```

Un modo puede filtrar los hilos de la barra por sus etiquetas (`telar hilo etiquetas "trabajo, cliente"`; en la
página, ⋯ → etiquetas…). Es lo de antes de `[mundos]`, y sigue andando; lo de ahora es declarar el mundo (con sus
`etiquetas`, si los hilos están etiquetados a mano) y dejar que el mundo filtre la página entera. Si una etiqueta del modo
es el nombre de un mundo declarado, ponerlo pone ese mundo.

```toml
[modos.trabajo]
etiquetas = "trabajo"
sin_etiqueta = "no-se-ven"

[modos.personal]
etiquetas = "personal"
```

Filtra HILOS, las secciones propias y ARCHIVO; el dashboard y las apps se ven siempre, y el hilo que se está mirando
no se esconde. Con un filtro puesto, el ícono del modo en la cabecera va en violeta.

Los agentes residentes (AGENTES, en la barra) no siguen las etiquetas: cada modo dice cuáles se ven con `agentes`, las
carpetas de los que salen, separadas por coma. Sin decirlo, o vacío, salen todos, como antes de que existiera; `"-"`,
ninguno. No se hereda: lo de táctica no pasa a estrategia, ni lo de una base a un modo propio, así que tocar uno no
cambia otro. Un modo que los nombra a todos es lo mismo que uno vacío, salvo con un agente nuevo: el vacío lo muestra
y el que los nombra, no, hasta que se lo agregue. Lo que el modo deja afuera no se esconde sin decirlo: la cabecera dice
cuántos muestra el modo al pasar el mouse, y si no muestra ninguno, una fila lo dice y lleva a elegirlos. Un agente
cuyo hilo (o el de un hijo suyo) se está mirando no se esconde, salvo en el dashboard: ahí se eligen, y lo elegido se
ve al tiro.

```toml
[modos.tactica]
agentes = "vigia, cartero"   # en táctica, solo estos dos

[modos.foco]
agentes = "-"                # en foco, ninguno
```

En la página se eligen en ⚙ modos, en una grilla con un agente por fila y un modo por columna: un clic prende o apaga
uno y lo escribe al tiro en ese modo (solo esa línea: lo demás del modo queda como estaba y lo que no dice lo sigue
heredando), sea o no el puesto, sin pasar por los cambios a mano. Marcarlos todos quita la línea; un modo de fábrica que
se queda sin nada vuelve a ser el de fábrica, y «de fábrica» los vuelve a mostrar todos. En el teléfono la grilla no
cabe: arriba se elige el modo y debajo van sus agentes, uno por fila. Con `[mundos]`, la grilla cruza los dos ejes:
junto a cada agente va la raya del color de su mundo (al pasar el mouse, por qué; uno sin clasificar no lleva), y arriba
se elige con qué mundo se lee (de entrada, el puesto; o ambos): lo que ese mundo deja afuera se apaga, salvo en el modo
todo, donde el mundo no esconde nada. Los agentes se siguen eligiendo por modo; su mundo lo dice su carpeta (⚙ mundos).

La pantalla de proyectos del dashboard también es de cada modo: `proyectos` dice qué tipos de unidad son proyectos (los
nombres de los arquetipos del perfil, separados por coma), `negocios` cuáles son negocios por cerrar e `iniciativas`
cuáles son el trabajo propio, sin cliente. Si el modo declara negocios o iniciativas y el mundo puesto tiene alguno, la
pantalla tiene subvistas, las pestañas de su barra (junto a las de los módulos que van dentro, como gantt): **clientes**
(los proyectos), **comercial** (los negocios) e **interno** (las iniciativas); si no, es una sola lista. Cuenta el mundo
puesto aunque el modo sea todo: en el mundo personal, proyectos es una lista. La tabla extendida (↔: los proyectos a lo
ancho, sin el detalle, con todas sus columnas en palabras) es otra vista de la barra. En media pantalla y en el teléfono,
una columna: elegir uno abre su detalle como una pantalla propia, y «‹» (o ⎋) vuelve a la lista donde estaba. Los proyectos van en secciones por su
estado efectivo (en ejecución, por partir, en cierre, pausados, terminados, cerrados): el que dice la fila Estado de su
documento («Activo», «Por partir», «En cierre», «Pausado», «Terminado», «Cerrado»…) o, si no dice uno de esos, el de su
plazo (`telar fechas`, clase `plazo`); uno cuyo plazo está en su fase de cierre (la etapa «cierre») va aparte, en «en
cierre». Cada uno lleva su fase en un círculo, la etapa en un ícono, el plazo y cuántos pendientes tiene. Los negocios
van en secciones por lo que dice el Estado (o la Etapa) de su documento: en negociación, con propuesta, en diagnóstico
(un POC), prospectos, en pausa, perdidos, ganados; el círculo se llena con lo que avanzaron, y al final de cada uno,
cuándo se tocó su carpeta y cuántos pendientes tiene. En el globo del título, cuántos hay en negociación y con propuesta.

Al elegir uno, la derecha muestra su detalle: arriba, su barra (el nombre, y como íconos ir a su hilo, consolidar sus
pendientes, abrir su README y sus acciones, ⋯) y cómo va en una línea (su estado, la etapa, de cuándo a cuándo, lo que no
cuadra); abajo, tres pestañas, y la elegida se queda al pasar a otro proyecto.
**resumen** pone lo que pide atención antes que lo que explica, y lo saca de los títulos de su README: las secciones que
dicen cómo va (las que empiezan por «Estado», «Foco», «Ahora», «Situación» o «Al» y una fecha, si no las escribe una
máquina), sus tres próximos pendientes, lo que espera de otros («Esperando», «Bloqueos», «Preguntas abiertas», «Por
resolver», «Qué falta», «Próximos pasos»), qué es (lo que va entre el título y la primera sección) y los datos de su
ficha (la primera tabla de dos columnas de «Info general», «Información general», «Ficha» o «Datos», sin los valores
vacíos). Cada texto va cortado a seis líneas enteras, con «más». **pendientes** los muestra todos. **documento** es el
README entero, sin su frontmatter, con la prosa del visor y de la lectura de un hilo, para leerlo de corrido.

```toml
[modos.trabajo]
proyectos = "proyecto, proyecto cerrado"
negocios = "deal"
```

Las **iniciativas** son el trabajo propio, sin cliente: lo que la casa hace para sí. `iniciativas` dice qué tipos de
unidad lo son (como `proyectos`, los arquetipos del perfil) y la pantalla de proyectos las pone en su subvista,
«interno», aparte de los proyectos (aunque `proyectos` también las nombre, o esté vacío). `agrupar_iniciativas` dice con
qué campo del frontmatter de cada una se agrupan, con el selector de `productos.yaml`: `{frontmatter:programa}` (vale
también `frontmatter:programa` o solo `programa`); con varios, separados por coma, se agrupa por el primero que alguna
tenga (`{frontmatter:funcion}, {frontmatter:programa}`: por función cuando las fichas la dicen, y si no, por programa).
De cada iniciativa se lee su frontmatter: quién la lleva (`dueno`), cómo va (`estado`; sin el vocabulario de abajo, si
no lo dice, el Estado de su tabla de campos), lo próximo por decidir (`proxima_decision`) y cuánto importa (`peso`:
alto, medio o bajo, el círculo de Táctica: lleno, a medias o un aro).

La fila dice su peso y su estado (cada uno un círculo), su nombre, su próximo paso (lo próximo por decidir; si no lo
dice, su tarea abierta más urgente; si no tiene, su casilla pendiente más urgente o la primera abierta de su README; si
no tiene ninguno, «sin próximo paso», en el color de cuidado), mi papel (de su dueño: «lo llevo» si es la persona, quién
la lleva si es otro, «sin definir» si no dice) y cuántos pendientes tiene. Cada grupo es una sección que se pliega y se
recuerda; sus ideas van al final, en un submenú que empieza plegado; las terminadas y las descartadas no van (el globo
del título las cuenta). Arriba, el buscador y los filtros «me toca» (las que lleva la persona) y «sin próximo paso».

Cada grupo lo encabeza la iniciativa cuya carpeta se llama como el valor al que apuntan las otras (`programa: club-lectura`
agrupa bajo `…/club-lectura/`), con sus propios datos; ella no lleva programa. Un programa sin la suya va con su nombre. Las
que no dicen programa ni encabezan uno van al final, en «sin programa». Sin `agrupar_iniciativas`, van todas juntas.

Desde todo se llega a ellas con una fila más, tras proyectos. Elegir una muestra su README a la derecha, como un
proyecto, con su estado, su dueño, lo próximo por decidir y su programa arriba.

En Táctica, lo que espera de una iniciativa va en su cuenta, con su nombre («Club de lectura · 2»): una unidad sin
cliente, o con el de la casa (`internos` del perfil), se cuenta por su nombre.

```toml
[modos.tactica]
iniciativas = "iniciativa"
agrupar_iniciativas = "{frontmatter:programa}"
```

**El estado de las iniciativas** tiene un vocabulario cerrado, que declara `[iniciativas]` (es de las fichas, no de un
modo: vale en todos). Con él, cada iniciativa muestra su estado con un círculo y su color (una idea, un punto; en
preparación, un cuarto; en curso, a medias y en azul; en pausa, un aro tenue; terminada, llena y verde; descartada, llena
y apagada), en la pantalla de proyectos. Un
clic en el estado abre el vocabulario, y lo elegido se escribe en su ficha: `estado:` y `estado_desde:` (la fecha de
hoy) de su frontmatter, y nada más del archivo (las comillas, los comentarios y el orden quedan como estaban; si no las
tiene, se agregan al final del frontmatter; sin frontmatter, se le pone uno). No se commitea: el repositorio de la ficha
tiene su propio flujo. Lo mismo hace `telar proyectos estado <ruta> <estado>`.

```toml
[iniciativas]
estados = ["idea", "preparación", "en curso", "en pausa", "terminada", "descartada"]
sinonimos = { activo = "en curso", activa = "en curso" }   # lo escrito que vale como uno del vocabulario
fuentes = { planilla = "Planilla del comité" }            # cómo se muestra cada estado_fuente
clases = { piloto = "curso" }                             # cómo se dibuja uno que su nombre no dice
```

Con vocabulario, el estado de una iniciativa es el `estado:` de su frontmatter y nada más: una ficha sin él está «sin
estado» (y se le pone uno con el mismo clic), aunque su tabla diga otra cosa o cuelgue de un programa que tiene el suyo.
Un **sinónimo** se ve y se cuenta como el estado al que vale, sin reescribir el archivo; lo que no es del vocabulario ni
un sinónimo se ve tal cual, marcado (un aro y la palabra en el color de cuidado), y al cambiarlo se ofrece el
vocabulario. Las palabras se comparan sin tildes ni mayúsculas.

La ficha dice además, si quiere, por qué está en su estado (`estado_nota:`, una línea: va al pasar el mouse y en el
detalle) y de dónde sale (`estado_fuente:`). Una con `estado_fuente` la manda otra fuente (una planilla que la
sincroniza): se ve con «fuente: <nombre>» y sin el menú, y telar se niega a cambiarla; `fuentes` solo dice con qué nombre
se muestra cada una (una que no nombra, tal cual). Cambiar el estado no toca `estado_nota` ni `estado_fuente`.

La **clase** de cada estado (cómo se dibuja) se deduce de su nombre: idea; diseño, preparación, planificación o por
partir; en curso, activo o en ejecución; en pausa, pausada o detenida; terminada, hecha o cerrada; descartada o
cancelada. `clases` la dice para uno que su nombre no deja ver (`idea`, `preparacion`, `curso`, `pausa`, `terminada` o
`descartada`); uno sin clase se dibuja con un punto tenue. Sin `estados`, el estado se ve como lo escribe cada ficha (o
su tabla), con su círculo si su nombre lo dice, y no se cambia desde telar.

Lo dicho en táctica lo heredan estrategia y todo, y los modos propios que no lo cambian (todo menos `agentes`).

Los glifos de risografía también son de cada modo, y vienen apagados: un campo de glifos que cambia de escala, en una
banda arriba o detrás de una pantalla, y un glifo por hilo (calculado de su nombre, con su estado) en la barra.

```toml
[modos.riso]
glifos = "si"              # el interruptor de todo: no deja la página como siempre
estilo = "base"            # cuál de [glifos.<estilo>]
iconos = "glifos"          # en la barra: simbolos (los de siempre) o glifos; con glifos, también el sello en la ficha
campo = "ahora=banda, calendario=fondo 0.15, *=nada"   # por pantalla: banda, fondo o nada, y su intensidad (0.05 a 1)
```

Cómo se ven lo dice su estilo, `[glifos.<estilo>]`: las tintas, la forma y el movimiento del campo (`paleta`, `celda`,
`niveles`, `ciclo`, `transicion`…), su vida (`actividad`, `periodo`, `duracion`, `saltos`, `rueda`), el gesto de cada
pieza (`gesto_cruz = "giro"`), el glifo de cada hilo (`hilo_paleta`, `hilo_tam`, `sello_tam`…) y sus estados
(`trabajando`, `espera`, `tenue`, `ritmo`). «base» viene de fábrica; una tabla con su nombre lo cambia, y una con otro
nombre suma un estilo que toma de «base» lo que no dice. La lista entera, con sus rangos, la da `GET /glifos`.

```toml
[glifos.tenue]
intensidad = 0.4
celda = 12
gesto_cuartos = "brote"
```

Todo esto se cambia también en ⚙ glifos: lo del modo puesto (prendidos, íconos, estilo, el campo pantalla por
pantalla con su intensidad) y el estilo, con una vista previa que se mueve con los controles; «guardar en este modo» y
«guardar el estilo» lo escriben aquí.

Las pantallas son las claves de las pestañas (las de ⚙ pestañas: `ahora`, `revisar`, `proyectos`, `pestana:leer`…) y
las vistas de un hilo, `conversacion` y `lectura`; `*` vale para las que no se nombran. Con «reducir movimiento» en el
sistema, se pintan una vez y no se mueven.

Cuál está puesto es de cada navegador. En la página, los cuatro están a la vista en la cabecera, junto a la marca: el
puesto en violeta (con el nombre del propio que esté puesto, junto a su base; o en su botón, si el mundo puesto lo
nombra en su `modos`); ninguno lleva número. Un clic pone uno y lleva a su vista (la pestaña de su primera fila de DASHBOARD;
foco, a la terminal del último hilo); clic derecho, los propios y «editar los modos…». Teclas: ⌥⇧1–4 (los cuatro, en
su orden), ⌥⇧F (foco y vuelta), ⌥⇧M (el siguiente) y ⌥⇧0 (el mundo siguiente). En ⚙ → modos, un clic cambia un ajuste
a mano en el modo puesto y «guardar en este modo» lo escribe aquí; los agentes de cada modo, en su grilla, se escriben
al tiro. La página abre en el modo que tenía, salvo todo, que vuelve a táctica.

## `[mundos]` — a qué parte de la vida pertenece cada cosa

Lo que espera a la persona y sus tareas pueden ser de partes de la vida que no se quieren ver juntas: el trabajo y lo
personal, por ejemplo. Cada mundo dice qué es suyo, y telar deriva el de cada cosa de eso, nunca de su título:

```toml
[mundos.trabajo]
areas = ["equipo", "cliente"]                 # el campo `area` de una tarea
rutas = ["empresa/", "clientes/", "agentes/oficina/"]   # prefijos de carpetas, relativos a la raíz

[mundos.personal]
areas = ["personal"]
rutas = ["casa/", "~/worktrees/huerta-"]      # también absolutas: lo que vive fuera de la raíz
```

- **Una tarea** es del mundo de su `area` y, si su área no es de ninguno, del de la carpeta de su `proyecto`.
- **Una casilla de un documento o un proyecto**, del de la carpeta de su documento.
- **Lo de un agente que declara su mundo** (`mundo = "…"` en su agente.toml, «Su definición» en `[agentes]`): su hilo,
  los que cuelgan de él y lo que está en su carpeta son de ese mundo, antes que de cualquier ruta o etiqueta.
- **Un hilo** (y su permiso o su pregunta en vivo), del de sus etiquetas si un mundo declara una (`etiquetas`, abajo);
  si no, del de la carpeta de su proyecto. Si no calza (un hilo en la raíz, un worktree fuera de ella), del de la
  carpeta de su agente residente (`[agentes] carpeta` y el agente del hilo) y, si tampoco, del hilo del que cuelga: un
  hijo con rama propia es del mundo de su padre.
- **Un mensaje retenido**, del hilo al que iba.
- **Lo de un módulo**, de su enlace principal (un hilo, un proyecto, un archivo).
- Lo que no calza en ninguno queda **sin clasificar**: se ve aparte, no se adivina.

Una ruta calza con lo que empieza con ella: `empresa/` es esa carpeta y lo que tiene dentro; sin la barra final calza
también con lo que empieza igual (`clientes/acme-` con `clientes/acme-faro/`). Si calzan varias, gana la más larga, sea
del mundo que sea: `rutas = ["empresa/lo-mio/"]` en personal le gana a `empresa/` en trabajo. Una ruta con `~` o `/` es
una carpeta de esta máquina; `./` es la raíz entera (lo que no diga otra cosa). Un área o una ruta en dos mundos es un
error, y un mundo no puede llamarse `sin-clasificar`.

Cada mundo puede decir además cuándo rige, su color, su tema, qué modos tiene, qué etiquetas de hilo son suyas y el arte
de su tarjeta; y `[mundos] fuera`, cuál rige fuera de todo horario:

```toml
[mundos]
fuera = "personal"                            # fuera de todo horario; sin esto, ambos (la página no filtra)

[mundos.trabajo]
rutas = ["empresa/"]
horario = "lun-vie 9:00-19:00"                # o una lista: ["lun-vie 9:00-13:00", "lun-vie 14:00-19:00"]
etiquetas = ["trabajo"]                       # un hilo con esta etiqueta es de trabajo, viva donde viva
color = "cian"                                # una tinta del tema; sin esto, una por orden

[mundos.personal]
rutas = ["casa/"]
tema = "brasa"                                # los colores de la página mientras rige; sin esto, los del modo
modos = ["todo", "foco"]                      # los modos que tiene; el primero, al que entra; sin esto, todos
arte = "cielo"                                # el dibujo de su tarjeta en la ventana de mundos; sin esto, el que le toca
```

- **`horario`**: los tramos en que rige, cada uno con días y horas (cualquiera de los dos puede faltar): `lun-vie
  9:00-19:00`, `sáb-dom` (el día entero), `lun,mié,vie 8:30-12`, `20:00-23:00` (todos los días), `todos`. Un día se
  escribe con sus tres primeras letras o más, con o sin tilde; un tramo que termina antes de empezar pasa la
  medianoche (`vie 22:00-2:00`). La página se pone sola en el mundo cuyo horario contiene la hora de ahora (la del
  navegador); si ninguno, o si dos se pisan, en el de `fuera`, o en ambos. Elegir otro a mano dura hasta el próximo
  cambio del horario: así no se queda puesto sin querer. Sin horarios, el mundo se elige solo a mano. Dos horarios que
  se pisan casi nunca son lo que se quiso: ⚙ mundos no los escribe, y `telar doctor` avisa si ya están escritos. El
  horario y `fuera` van en la raíz, para que rijan igual en todas las máquinas (abajo, «En la raíz»).
- **`fuera`**: el nombre de uno de los mundos declarados.
- **`color`**: una de `azul`, `amarillo`, `verde`, `rojo`, `magenta`, `cian` y `violeta` (las tintas del tema, que
  cada tema pinta a su manera). Los que no dicen el suyo toman, en su orden, el primero libre de `cian`, `magenta`,
  `verde`, `azul`, `violeta`, `amarillo` y `rojo`.
- **`etiquetas`**: las de un hilo (`telar hilo etiquetas`). Le ganan a su carpeta, como el área de una tarea le gana a
  su proyecto: es lo que se declaró de ese hilo en particular. Una etiqueta en dos mundos es un error.
- **`tema`**: uno de los temas de la página (`telar`, `latte`, `riso`, `papel`, `brasa`, `rescoldo` o `ámbar`, que se
  escribe `ambar`), o uno propio de `[temas]` (abajo). La página lo lleva mientras ese mundo rige, sobre el del modo: lo
  pone al entrar al mundo, a su hora o a mano, y lo saca al salir (con ambos, o en un mundo sin tema, el del modo).
  Elegir un tema a mano en ⚙ modos vale en el mundo donde se eligió, hasta cambiar de modo o entrar a otro mundo con
  tema. `brasa`, `rescoldo` y `ambar` son para la noche: oscuros, cálidos y con poca luz azul (el fondo y el texto tiran
  a ámbar; el acento, que en los demás es azul, es una salvia, y el cian va apagado), con el texto y cada tinta a 4,5:1
  o más sobre sus fondos y las tintas con significado distintas entre sí; brasa es el de partida, rescoldo uno más suave
  y ámbar el más cálido. /componentes › tokens › contraste los mide. Los colores principales de un tema se cambian en
  `[temas]` (abajo).
- **`modos`**: los modos de la página que tiene el mundo (sus claves: `tactica`, `estrategia`, `foco`, `todo` o uno
  propio de `[modos]`), al menos uno; sin la línea, todos. Mientras rige, la banda de modos muestra solo esos (con
  ambos, los de todos los mundos juntos), y cada propio que nombra lleva su botón, con el ícono de su `icono`, tras la
  actitud que lo precede en la lista (`modos = ["tactica", "estrategia", "entradas", "foco", "todo"]` pone entradas
  entre estrategia y foco; las actitudes siguen en su orden de siempre). Sin la línea, la banda lleva las cuatro y un
  propio puesto va junto a su base. Solo esos se ponen: un clic, ⌥⇧1–4, ⌥⇧F o ⌥⇧M con otro no hace nada, y el
  siguiente (⌥⇧M) pasa solo por los suyos. Al entrar al mundo (a su hora o a mano) con un modo que no tiene, la página
  pasa al último que se tuvo ahí o, si no, al primero de la lista; y al volver al otro mundo, al que se tenía ahí (o,
  si no se sabe, al que estaba antes). Lo que la persona eligió, si el otro mundo también lo tiene, se queda. En el
  dashboard, la página va además a la vista del modo nuevo; mirando un hilo, no salta. Lo que se tuvo en cada mundo
  es del navegador, como el modo puesto. Un modo que no existe es un error, y un modo propio que un mundo tiene no se
  puede borrar hasta quitárselo.
- **`arte`**: el dibujo de letras animado de su tarjeta en la ventana de mundos (abajo): la clave de uno de fábrica
  (`telar`, el telar tejiendo; `cielo`, el cielo de noche; `orbita`, el planeta con anillo; `binaria`, los dos que giran)
  o de uno propio de la raíz, `<raiz>/.telar/arte/<clave>.txt`. Sin la línea, el que le toca: el que se llama como el
  mundo, si hay uno; si no, uno de fábrica que lo sugiere (el telar para `trabajo`, el cielo para `personal`); si no, la
  órbita. Ambos lleva la binaria. Una clave que no hay no es un error: la tarjeta lleva el que le toca. Cómo se hace uno,
  en [arte.md](arte.md). Va en la configuración de la máquina, como el color y el tema; los artes propios, en la raíz,
  viajan por git.

En la página, el mundo puesto va en la banda bajo la cabecera, a la derecha (los modos, a la izquierda): el planeta y su
nombre en su color (con ambos, en el del texto), y hasta cuándo en su ayuda. La línea bajo la banda es la de siempre, con
o sin mundo. Un clic abre la ventana de mundos, y también ⌘M (Ctrl+M fuera del Mac; otra vez, la cierra) y «cambiar de
mundo» en ⌘K: una tarjeta por mundo y ambos al final, cada una con su arte animado, su nombre en su color, su horario y,
la de ahora, por qué rige y hasta cuándo (la que viene dice desde cuándo). Un clic, su número o ⏎ la pone (← → ↑ ↓ la
eligen; el foco sigue al mouse); «volver al horario» (h) suelta lo elegido a mano; «editar» (e) lleva a ⚙ mundos; ⎋ o un
clic afuera la cierran. Con el mouse encima, la tarjeta se ilumina en su color y el arte se acelera; con «reducir
movimiento», el arte queda quieto. En el teléfono, una bajo otra, y tocar elige. Filtra la página entera: los hilos y los
agentes de la barra (lo que deja afuera se cuenta en una fila plegada al final de HILOS, «de personal 7», que lo abre
ahí mismo), lo que espera y su número, las tareas, los proyectos, el día y la línea del día de la cabecera, y ⌘K (lo de
otro mundo se busca en Todo, donde va al final y dice de cuál es). Un agente residente va por el mundo de su hilo y,
sin hilo abierto, por el que declara su agente.toml, su carpeta o la etiqueta de su hilo, como lo dice ⚙ mundos; así
también en ⌘K, en los destinos de la instrucción y en la vista de agentes. Lo sin clasificar se ve en todos. En el modo
todo, el mundo solo ordena: en las listas, en ⌘K y en las pestañas se ve todo, lo de los otros mundos al final. La barra
de hilos, que está siempre a la vista, obedece al mundo también en todo: lo de otro mundo va a «de personal 7», plegada
al final, y un agente de otro mundo no sale; así una pantalla compartida en el trabajo no muestra lo personal. Un agente puede pedir otra
cosa (`fuera_de_su_mundo` en su agente.toml, «Su definición» en `[agentes]`, o en ⚙ mundos): `esconder`, no salir en
ninguna parte con otro mundo puesto, tampoco en todo, él ni lo suyo; `ver`, salir en todos los mundos. Un
agente que vive en otra máquina y cuya carpeta todavía no llega a esta (el repositorio atrasado) sale igual, por la foto
de su máquina, con el mundo que declara allá su agente.toml, sin casa y con su hilo de allá; `telar doctor` lo avisa y
dice cómo ponerse al día.

En ⚙ → mundos se ven y se cambian, con la misma forma que ⚙ → modos: los declarados y ambos, cuál está puesto y
hasta cuándo («poner» lo pone a mano; «volver al horario»), «borrar» (con su confirmación: lo suyo queda sin
clasificar) y «nuevo mundo…», que agrega `[mundos.<nombre>]` vacío después del último. Debajo, de qué mundo es cada
agente residente, en una grilla de solo lectura (un agente por fila, un mundo por columna) con su porqué al final de la
fila: lo que declara su agente.toml, la ruta que calza con su carpeta o la etiqueta de su hilo que lo pone ahí (sin
ninguna, sin clasificar: sale en todos). Al final, lo que dice cada mundo (color, tema, arte, modos, etiquetas, áreas y
rutas): un clic cambia uno y lo escribe al tiro aquí, solo esa línea.

El horario tiene su parte, justo debajo de los mundos. Arriba, la semana: un renglón por día, de lunes a domingo, cada
uno una franja de 0 a 24 h con el pedazo de cada mundo en su color; donde dos se pisan, rayado en rojo (a esa hora rige
el de fuera), y donde no rige ninguno, el color de `fuera` apagado; la hora de ahora, una línea en el día de hoy; y
debajo, cada choque dicho («trabajo» y «personal» se pisan los lun-vie de 18:00 a 19:00). Después, cuál rige fuera de
todo horario (un clic lo elige) y, por cada mundo, el editor de su horario: un renglón por tramo, con sus días (lun …
dom, un clic prende o apaga uno), de qué hora a qué hora (de a 15 minutos; «hasta» antes que «desde» pasa la
medianoche) y quitarlo; «otro tramo» agrega uno. Lo editado es un borrador que la semana muestra al tiro; el pie dice
lo que se va a escribir (`horario = "lun-vie 9:00-19:00"`) o por qué no se puede (un tramo sin días, uno que empieza y
termina a la misma hora, un choque con el horario guardado de otro mundo), y «guardar» lo escribe; «deshacer» vuelve a
lo guardado. Si con lo guardado cambia el mundo que rige, la banda cambia al tiro. El tema se elige en su fila, de una fila de
temas pintados cada uno con sus colores, y «el del modo» lo quita. El arte, de una fila con cada uno (los de fábrica y
los de la raíz), y «el que le toca» lo quita. Los modos, de una fila con cada modo y su ícono: un
clic agrega uno (al final de la lista) o lo quita; el último no se quita (un mundo tiene al menos uno), y «todos», o
marcarlos todos, quita la línea. Un horario que no se entiende, o un área, una ruta o una
etiqueta que ya es de otro mundo, no se escriben: la ventana lo dice antes de mandarlo («empresa/» ya es de «trabajo»),
y si igual llega (otro cambió el archivo entretanto), lo dice un aviso. En el teléfono la grilla no cabe: arriba se
elige el mundo y debajo van sus agentes, uno por fila. «editar», en la ventana de mundos, lleva ahí.

**En la raíz, para todas las máquinas.** Qué mundo rige no depende de la máquina: si el horario se cambia desde el teléfono
(el servidor), el laptop tiene que regir igual. Por eso el horario de cada mundo y `fuera` van también en
`<raiz>/.telar/mundos.toml` (la raíz de `raiz`, o de `TELAR_RAIZ`), con la misma forma y nada más:

```toml
[mundos]
fuera = "personal"

[mundos.trabajo]
horario = "lun-vie 9:00-19:00"
```

Se lee con la configuración: sin horario, encima la raíz, y encima lo que diga la configuración de la máquina, que pisa
mundo por mundo, solo en esa máquina (un `horario` en `[mundos.<n>]`, aunque sea `[]`, tapa el de la raíz para ese mundo; un
`fuera` en `[mundos]`, el de la raíz). Lo demás de un mundo (rutas, áreas, etiquetas, color, tema, modos) sigue en la
configuración de cada máquina: las rutas son de la máquina, y lo demás no decide qué rige. Un mundo de la raíz que la
máquina no declara no se aplica (no se inventa: un mundo sin sus rutas no sirve), y un `fuera` que no es de los suyos,
tampoco; `telar doctor` lo dice. ⚙ mundos escribe el horario y `fuera` en la raíz y los saca de la configuración de la
máquina si estaban (si no, la taparían); vacío, salen de los dos. Lo escrito en la raíz se commitea solo, unos segundos
después del último cambio, y se sube como `telar commit`: ese archivo y ningún otro. Las otras máquinas lo ven cuando integran
lo de arriba (su próximo `telar commit`, o /sincronizar). Un archivo de la raíz que no se lee (un choque de git a medio
resolver, un horario que no se entiende) no se aplica ni se escribe encima, y `telar doctor` lo dice. Sin `raiz` no hay
raíz, y todo queda en la de la máquina, como antes.

`telar mundos` dice el horario de cada mundo, de dónde sale cada uno y si dos se pisan; `telar mundos migrar` pasa los
horarios y `fuera` de la configuración de una máquina a la raíz sin cambiar lo que rige (lo que la raíz ya dice igual, aunque
escrito de otra forma, sale de la máquina; lo que dice distinto se queda en la máquina, y se lista), con un respaldo de la
configuración al lado (`config.toml.antes-de-mundos-en-raiz-<fecha>`), y lo commitea y lo sube (`--ver`, solo dice qué
haría; `--local`, sin subir). Si la raíz de esa máquina está atrasada respecto de arriba, no migra: hay que traerlo antes.
`telar mundos subir` commitea y sube el archivo ahora.

El orden de las tablas es el orden en que se muestran (las tandas de «te esperan»). Sin `[mundos]`, todo sigue como
antes: nada dice mundo. Lo que se pide por un filtro (`telar esperas --mundo trabajo`, `telar tipo tarea lista --mundo
personal`, `telar pendientes --mundo`; `sin-clasificar` pide lo que no calza) y el campo `mundo` de cada cosa están en
[contratos.md](contratos.md). Cada máquina deriva con su propia configuración: las tareas que viven en otra se
clasifican con los mundos de la que las muestra.

## `[temas]` — los colores principales de un tema, y los temas propios

Cada tema (`telar`, `latte`, `riso`, `papel`, `brasa`, `rescoldo`, `ambar`) trae sus colores de fábrica. Se pueden
cambiar sus colores principales, los que le dan la cara: sus fondos y sus líneas, y sus tintas de letra. Lo que no se
dice queda de fábrica. Van en `<raiz>/.telar/temas.toml`, para que valgan en todas las máquinas que comparten la raíz
(abajo, «En la raíz, para todas las máquinas»), o en esta configuración, para una sola:

```toml
[temas.brasa]
azul = "#9aa982"          # el acento, en oliva gris en vez de la salvia de fábrica
bg = "#1c1510"            # el fondo, un poco más oscuro

[temas.noche-azul]        # uno propio: brasa entero, con otro nombre y lo suyo encima
base = "brasa"
bg = "#141820"
bg-barra = "#0f1218"
linea = "#2a3446"
azul = "#8fb3d9"
```

Los fondos y las líneas, lo mínimo que cambia la cara de un tema; lo demás sale de ellos (la superficie es el fondo, el
hover es el texto apenas, la fila activa es el acento sobre el fondo):

| color | se ve como | qué pinta |
|---|---|---|
| `bg` | fondo | la página, la terminal, las filas |
| `bg-barra` | barras | las barras de arriba, las ventanas, el menú |
| `linea` | líneas | las que parten filas y secciones, el borde de una ventana |
| `sel` | selección | lo elegido en un menú o en una lista |

De fábrica, las líneas y la selección salen del texto, con transparencia; cambiadas, quedan de un color fijo.

Las tintas de letra, por el nombre de su color en el tema (el de `pagina/media/css/temas.css`) y lo que pintan:

| tinta | se ve como | qué pinta |
|---|---|---|
| `fg` | texto | lo que se lee: los hilos, las tareas, la terminal |
| `dim` | tenue | la meta, las horas, lo de al lado |
| `amarillo` | títulos | las cabeceras (HILOS, DECIDIR), los nombres de los agentes, lo que te espera |
| `azul` | acento | los enlaces, las pestañas, la fila activa, lo que trabaja, las reuniones |
| `violeta` | agentes | la letra de un agente, el modo y la vista que se ven |
| `verde` | éxito | lo que terminó, lo libre |
| `cian` | remoto | lo de otra máquina, la conversación de un hilo |
| `magenta` | rosa | un mundo, las decisiones, las carpetas de la carga |
| `rojo` | peligro | lo que falló, lo que borra |

Un color va como `#rrggbb` (o `#rgb`). Cambiar uno lo cambia en todo lo que lo usa con ese tema puesto (los semánticos
que salen de él: el acento, los títulos, la fila activa; y la terminal, que toma sus colores del tema), y también en los
selectores de tema de ⚙ mundos y ⚙ temas; /componentes sigue mostrando los de fábrica. Con un fondo propio, la página
sabe si el tema quedó claro u oscuro (las barras de desplazamiento, el selector de color).

Un **tema propio** tiene un nombre que no es de fábrica (minúsculas, números y guiones, hasta 24, empezando por una
letra) y un `base`, el de fábrica del que parte: es ese tema entero (sus colores y lo que `temas.css` le dice, como la
raya del ítem activo de riso) con lo que diga encima, y su «de fábrica» es el de su base. Se elige donde se elige un
tema (`[modos.<m>] tema`, `[mundos.<n>] tema`, ⚙ modos y ⚙ mundos) y está en la barra de temas de /componentes, con
sus colores. Mientras un modo o un mundo lo tenga puesto, no se borra.

Un tema, un color o una base que no se entienden son un error de la configuración; un color que se lee mal no: la
página lo avisa. Un modo o un mundo que nombra un tema que no hay no se deja escribir; si deja de haberlo después (uno
propio que se borró en la raíz desde otra máquina), la configuración se sigue leyendo, la página pone el del modo y
`telar doctor` lo dice.

En ⚙ → temas se eligen con clics. Arriba, los temas, cada uno con sus colores (los propios, después de los de fábrica):
el que se ve lleva un ojo, el que tiene colores propios un lápiz, y un clic elige cuál se cambia (de entrada, el que se
ve; «colores…», junto al tema de un mundo en ⚙ mundos o al de un modo en ⚙ modos, lleva directo). «ponerte <tema>» lo
pone en el modo puesto, a mano (como ⚙ modos › tema), y «nuevo tema…» arma uno propio: su nombre (los espacios y las
tildes se arreglan solos; uno de fábrica o uno que ya hay no se deja) y de cuál parte (de uno propio se copian también
sus colores). Debajo, la vista previa de ese tema (una barra, filas partidas por sus líneas, la fila activa, la
seleccionada y cada tinta), que queda arriba mientras se bajan sus colores, y cada color sobre el fondo de ese tema: los
fondos y las líneas, y después las tintas, cada uno con su nombre, lo que pinta, cómo se lee (de una letra, su peor
contraste sobre el fondo, las barras y la fila activa; de un fondo, el del texto sobre él; de las líneas, el suyo contra
el fondo) y el de fábrica al lado, con su cuadrado y su número. Para cambiarlo: el selector de color del navegador (la
muestra de la izquierda), un campo para escribir uno y, en las tintas, una paleta corta que combina con el tema (la de
fábrica primero, y tonos con nombre a la misma claridad de esa tinta: terracota, cobre, ámbar, oliva, salvia, agua,
pizarra, lavanda, malva, rosa viejo; para el texto y lo tenue, neutros con un matiz; en los de la noche, apagados). Un
clic en la paleta lo escribe al tiro, solo esa línea; con el selector y el campo se ve mientras se elige (en la vista
previa y, si es el tema que se ve, en toda la página), y se escribe al soltarlo o con ⏎. «volver» deja un color en el de
fábrica; «todo de fábrica», el tema entero (de uno de fábrica quita la tabla; de uno propio, sus colores: queda igual a
su base); «borrar tema» quita uno propio. Lo que se lee mal se avisa y se escribe igual: una letra bajo 4,5:1 sobre
alguno de sus fondos, o que se confunde con otra tinta con significado (o el tenue con el texto, o el acento con lo
tenue); un fondo que deja bajo 4,5:1 letras que sobre el de fábrica se leían bien (lo dice él, y cada letra que dejó
mal); el texto bajo 4,5:1 sobre la selección; una línea que casi no se ve. La fila lo dice en ese momento, en rojo o en
amarillo con su ícono, y al escribirlo un aviso lo repite.

**En la raíz, para todas las máquinas.** `[temas]` va también en `<raiz>/.telar/temas.toml` (la raíz de `raiz`, o de
`TELAR_RAIZ`), con la misma forma y solo tablas `[temas.<tema>]`. Se lee con la configuración: de fábrica, encima la raíz, y
encima los `[temas.<tema>]` de la configuración de la máquina, que pisan color por color (y la `base`), solo en esa
máquina; uno propio de la raíz se puede pisar en una máquina sin repetir su `base`. ⚙ temas escribe en la raíz: un color que
se cambia pasa a la raíz y sale de la configuración de la máquina si estaba (si no, la taparía); uno que vuelve al de
fábrica sale de los dos; un tema nuevo va a la raíz; «borrar tema» lo quita de los dos. Cada tema dice dónde vive («en
<carpeta>», con el nombre de la carpeta raíz, o «solo aquí», al lado de cada color propio, y en palabras bajo su nombre). Sin `raiz` en la configuración no hay
raíz, y todo queda en la de la máquina, como antes.

Lo escrito en la raíz se commitea solo, unos segundos después del último cambio (varios clics seguidos son un commit), y se
sube como `telar commit`: ese archivo y ningún otro, aunque el árbol tenga cambios de otros. Las otras máquinas lo ven cuando
integran lo de arriba (su próximo `telar commit`, o /sincronizar) y la página se vuelve a abrir. Un archivo de la raíz que no
se lee (un choque de git a medio resolver) no se aplica ni se escribe encima, y `telar doctor` lo dice.

`telar temas` dice dónde vive cada tema; `telar temas migrar` pasa los `[temas.*]` de la configuración de una máquina a
la raíz sin cambiar lo que se ve (lo que la raíz ya dice igual sale de la máquina; lo que dice distinto se queda en la máquina, y
se lista), con un respaldo de la configuración al lado (`config.toml.antes-de-temas-en-raiz-<fecha>`), y lo commitea y lo
sube (`--ver`, solo dice qué haría; `--local`, sin subir). Si la raíz de esa máquina está atrasada respecto de arriba, no
migra: hay que traerlo antes. `telar temas subir` commitea y sube el archivo ahora.

Lo mismo por la API, en [contratos.md](contratos.md) («`telar config --json`»): `GET /temas`, `PUT /temas/<nombre>`,
`PATCH /temas/<tema>` y `DELETE /temas/<tema>`; `telar config --json` dice los propios en `temas`.

## `[agentes]` — agentes residentes, cada uno en su carpeta

```toml
[agentes]
carpeta = "agentes"                  # relativa a la raíz: cada subcarpeta con un CLAUDE.md es un agente

[agentes.faro]                       # opcional, por carpeta
hilos = ["◌ guardia*"]               # hilos suyos además del que lleva su nombre y los vinculados a su carpeta
home = ["~/bin/faro-casa", "--json"] # una página propia: sus bloques van arriba de los que arma telar
```

Un agente residente es una carpeta con su `CLAUDE.md` (las que empiezan con `_` o `.`, como una
plantilla, no cuentan). Su nombre es el título del `README.md` de la carpeta. En la lista de hilos
van todos bajo la cabecera **AGENTES**, uno por línea, con su hilo de siempre y sus hijos colgando. Su **home** (su
casa) se abre con el ícono de la casa, que aparece al pasar el mouse por su fila (en el teléfono, en su ⋯). El home lo
arma telar (`telar seccion agente:<carpeta>`): el primer párrafo de su `CLAUDE.md`, su bitácora
(`bitacora.md`, la entrada más nueva arriba) y el índice de su memoria (`memoria/MEMORY.md`), con
cada archivo para abrirlo. Un hilo vinculado a la carpeta del agente **arranca ahí**, aunque
`[agente] carpeta` diga otra cosa: así Claude carga el `CLAUDE.md` del agente (y los de las carpetas de
arriba) desde el comienzo.

El primero se arma con `telar agentes nuevo "Faro" [--para "…"]` (o **+ nuevo** en AGENTES, en la página): crea
su carpeta con `CLAUDE.md`, `agente.toml`, `README.md`, `bitacora.md` y `memoria/MEMORY.md`, y si falta escribe
`[agentes] carpeta`: `agentes` en la raíz o, si la raíz es el repositorio de un equipo (tiene
`.telar/equipo.yaml`), `~/agentes`, para que los agentes de cada persona no vayan al repositorio de todos.

**Su definición: `agente.toml`.** Al lado de su `CLAUDE.md`, opcional (sin él, todo es como se dice arriba).
`telar agentes` muestra lo que declara cada uno.

```toml
# agentes/faro/agente.toml
nombre = "Faro"                      # pisa el título del README: es el nombre de su hilo
para = "La lámpara y el turno de noche: encárgale lo que tenga que ver con la luz."
modelo = "opus"                      # el de su sesión (Claude Code: --model); un motor que no sabe elegirlo lo ignora
residente = false                    # el nodo no le abre la sesión solo cuando le llega algo (por defecto, true)
mundo = "personal"                   # el de [mundos] del que es: fuera de él no se ve (abajo)
fuera_de_su_mundo = "esconder"       # con otro mundo puesto: al-final (el de fábrica), esconder o ver (abajo)
```

`modelo` va al abrir su sesión por un encargo o un periódico, y al abrir su hilo (`telar tejer`, `abrir`);
si `[agentes.<carpeta>] argumentos` ya trae `--model`, gana el de la máquina. `para` sale en su home, en
`telar agentes` y en `agente:<carpeta>`. Con `residente = false`, un mensaje que le llega espera en su casilla
hasta que alguien abra su hilo; un encargo (`telar encargar`, un periódico) lo abre igual, con bus o sin él. `instrucciones`, `memoria`, `capacidades`,
`politica` y `lugar` se aceptan y se muestran, todavía sin uso. `mundo` dice de qué mundo de `[mundos]` es el agente,
con todo lo suyo: su hilo, los que cuelgan de él y lo que está en su carpeta (su memoria, sus registros). Le gana a la
ruta de su carpeta y a las etiquetas de su hilo, y viaja con la carpeta: vale en cada máquina que declare ese mundo (en
una que no, sin clasificar). Es para un agente privado, el de una parte de la vida que no se muestra en la otra: con
otro mundo puesto no sale en la barra, ni en ⌘K, ni entre los destinos de la instrucción, ni en la vista de agentes.
`fuera_de_su_mundo` dice qué pasa con él (y con lo suyo) con otro mundo puesto: `al-final`, el de fábrica (la barra no
lo muestra; en el modo todo, donde el mundo solo ordena, sale al final en ⌘K, la vista de agentes y la instrucción, como
lo demás de otro mundo); `esconder` (no sale en ninguna parte, tampoco en todo: ni él, ni sus hilos y los que cuelgan de
ellos, ni lo que espera de él, ni lo que vive en su carpeta, en ⌘K, Todo, «te esperan», Táctica, la vista de agentes,
los destinos de la instrucción y la franja de avisos; solo ⚙ modos y ⚙ mundos lo nombran, para configurarlo); o `ver`
(sale en todos los mundos, como uno sin clasificar, aunque lo suyo sigue siendo de su mundo). Se elige en ⚙ mundos, en
la grilla de los agentes: escribe la línea en su agente.toml (el de fábrica la quita) y lo commitea y lo sube al rato,
solo ese archivo, para que valga en todas las máquinas. Un archivo con errores no apaga al agente:
lo que no se lee se ignora, y lo dicen `telar agentes` y `telar doctor`. Cambiarle el `nombre` cambia el de su
hilo y su casilla: el nodo sigue recogiendo lo que llegue con el de antes, y doctor avisa si su conversación
quedó anotada con el de antes o si hay mensajes esperando con él.

**Encargos.** A un residente no se le abre una sesión por tarea: `telar encargar <agente> "…"` deja un encargo
(`encargo:e-…`) en la casilla de su hilo de siempre: si está libre se le avisa, si trabaja se lo entrega el gancho
`Stop` al terminar, y si no tiene sesión se abre retomando su conversación. El encargo queda `corriendo` cuando le
llega, el agente lo cierra con su resultado (y si termina el turno sin cerrarlo, se le recuerda una vez), y quien lo
pidió recibe el resultado o lo cancela.

**Presencia.** `residente` en su `agente.toml`: `siempre` (el nodo de su máquina lo mantiene abierto: lo abre al
arrancar y si se cerró, y `max_vivos` nunca lo cierra), `a-pedido` (el de siempre: se abre cuando le llega algo) o
`no` (lo que le llega espera; un encargo explícito lo abre igual). En la página, la conversación de un agente
`siempre` o `a-pedido` que está cerrado (o archivado) deja la caja de escribir: lo escrito va como mensaje, por el bus, y
su nodo lo abre con su conversación y se lo entrega (así se le escribe desde el teléfono sin «retomar» antes). Uno que
duerme (telar.dormir) se despierta al abrirlo, y lo que se le escribe le llega igual.

**Rotar con relevo.** Si la conversación de un residente pasa de `[agentes] rotar_mb` (MB), al terminar un
turno con la casilla vacía telar le pide su **relevo**: que escriba en `<estado>/relevos/<carpeta>.md` en qué
estaba, qué queda y qué tiene que saber la siguiente. Al terminar ese turno, el nodo le teclea `/clear` (otra
conversación, en la misma ventana) y le dice que lea su relevo. Si se la abre en frío (un encargo, `telar
tejer`, `retomar`) con la conversación ya pasada del tope, empieza otra cuyo primer mensaje dice dónde está su
último relevo. Sin `rotar_mb`, no rota (telar.rotacion). El relevo y el peso de su conversación se ven en la
barra de la derecha de la página, al ver su hilo. Un proceso periódico con `agente = "<carpeta>"` y un
`mensaje` es un encargo. Los argumentos para el agente al abrir su sesión (permisos, herramientas) van
en `[agentes.<carpeta>] argumentos`.

```toml
[agente]
max_vivos = 4                        # hilos vivos a la vez en esta máquina, si es un servidor (0: sin tope)

[agentes]
carpeta = "agentes"
rotar_mb = 8

[agentes.secretaria]
argumentos = ["--permission-mode", "acceptEdits"]
```

`max_vivos` cuenta las ventanas de la sesión del telar donde nadie mira esa sesión directo (un servidor: sus
hilos se miran desde otras máquinas); en el laptop, donde la sesión del telar es lo que la persona mira, no
cierra nada. Antes de abrir otro hilo (un periódico, un encargo), telar cierra los ociosos que nadie está
mirando, el más quieto primero y los residentes al final (todos los agentes con `residente = true`, no solo el
que se abre); su conversación queda en disco y se retoma cuando haga falta.

## `[bus]` — mensajes y estado entre varias máquinas

```toml
[bus]
url = "nats://<IP privada de la máquina que no se apaga>:4222"
token = "~/.config/telar/bus.token"   # tu secreto: el mismo archivo en todas tus máquinas
persona = "ana"                        # tu cuenta en el bus (por defecto, tu usuario del sistema)
maquina = "laptop"                     # cómo se llama esta en el bus (por defecto, su nombre de red)
administra = "ana"                     # quién corre el bus, si no eres tú (lo escribe `telar instalar --unirse`)
publicar = "condicionado"              # cómo publica el nodo sus hilos: condicionado (de fábrica) o simple
```

`publicar`: el nodo escribe el registro de sus hilos en el bus condicionado a la revisión que vio (telar.dueno), así
nunca hay dos máquinas dueñas del mismo hilo; `"simple"` es la escritura de antes, sin condición, por si la nueva falla
(igual no publica un hilo que el registro dice de otra máquina).

Con `[bus]`, cada máquina corre `telar nodo` (`servidor/telar-nodo.service` en Linux,
`servidor/telar-nodo.plist` en macOS) y la que no se apaga corre además el bus
(`servidor/telar-bus.service`, nats-server). `telar mensaje <hilo|agente> "…"` le escribe a cualquier
hilo, viva donde viva: el mensaje espera en su casilla hasta que lo recoja la máquina donde vive y entra
a la conversación por los ganchos del agente (`telar agente instalar`), sin teclearse. `telar encargar`
usa el bus si lo hay. El estado de cada hilo (máquina, atención) se publica y se escucha al instante.
Diseño: `docs/arquitectura.md`, «Entre máquinas: el bus».

El servidor del bus tiene **una cuenta por persona**: lo de una no lo ve otra. Alguien nuevo pide la suya
con `telar instalar --unirse` y quien administra la aprueba: en la página (⚙ personas) o con `telar bus
pedidos` y `telar bus aprobar ID`. Cada cuenta tiene un rol: el **dueño** es quien corre el bus; un
**admin** aprueba y rechaza pedidos, quita cuentas y cambia roles como él (salvo lo del dueño); un
**miembro** solo tiene su cuenta. `telar bus personas`, `quitar NOMBRE` y `rol NOMBRE admin|miembro` hacen el
resto, desde cualquier máquina del dueño o de un admin: se le piden al nodo de la máquina del bus, y el
servidor solo deja llegar ahí a esas cuentas (telar.personas). Recargan el bus solas. A mano, en la máquina
del bus, `telar bus persona NOMBRE` da una cuenta o una clave nueva (para ti, con tu `[bus] token`; para otra
persona genera un secreto que hay que pasarle), y después `systemctl --user reload telar-bus`. Sin `[bus]`, todo sigue en una sola máquina, como siempre.

## `[equipo]` — que alguien de confianza vea tus tareas y te sugiera prioridades

```toml
[equipo]
tareas   = "~/vida/tareas"                  # una tarea por archivo con front-matter (T123.md)
todo     = "~/vida/bin/todo"                # el CLI que cambia la prioridad al aceptar
etiqueta = "equipo"                         # solo se comparten las tareas con esta etiqueta
puerto   = 8766
[equipo.personas]
beto     = "…"                              # `telar equipo token beto` da una llave
```

Se comparte solo el título, estado, prioridad, fecha, proyecto y `avance` de cada tarea etiquetada
(y las cerradas en los últimos 14 días). Nunca el cuerpo ni la historia. La página la sirve
`telar serve --equipo` (o sola, `telar equipo servir`), en la IP de Tailscale y en `[equipo] puerto`: es
**otra app** que tu API, en su propio puerto, así que con la llave de una persona no se alcanza ninguna de
tus rutas. Cada persona entra con su llave y puede solo leer y dejar una sugerencia o un pedido (uno cada
5 s). La bandeja la decides tú, desde tu API (`/equipo/bandeja`, `/equipo/{id}/aceptar|rechazar|existe`);
desde otra máquina, se le pide a la que tiene las tareas por el bus. En la página lo dice la configuración
(`/config`, campo `equipo`): `aqui` si esta máquina tiene `[equipo]`, o la de `[equipo] en = "<máquina>"` si la bandeja vive en otra. Ver `telar equipo --help`.

## `[secciones]` — grupos propios en la lista de hilos

La forma nueva es `[vistas.<clave>]` con `hilos` (y `comando` en lugar de `home`); esta se sigue leyendo.

```toml
[secciones.diario]
nombre = "Diario"
hilos = ["notas", "◌ rato*"]          # nombre exacto, o prefijo si termina en *
home = ["/ruta/a/mi-home", "--json"]  # opcional: un comando que imprime su página
```

Una sección es un grupo con cabecera plegable en la barra de hilos, justo debajo de
**HILOS**. Los hilos que reclama (los vivos; un archivado sigue en el archivo)
salen de la lista general y van ahí. Con `home`, la sección tiene además una fila **home**
que abre su página en el panel del dashboard: telar corre el comando, comprueba que el
JSON tenga la forma del contrato (`docs/contratos.md`, `telar seccion`) y lo dibuja. Un
ítem de la página que trae `conversacion` abre esa conversación entera, con la opción de
retomarla en su hilo. `telar seccion` lista las declaradas y `telar seccion <clave>`
muestra la página en la terminal.

## `[apps]` — lo que se abre en el panel y no es un hilo

La forma nueva es `[vistas.<clave>]` con `aparece = "apps"` (`comando` en lugar de `pagina`); esta se sigue
leyendo.

```toml
[apps.babel]
descripcion = "breakout de la biblioteca"     # opcional: el globo de su fila
pagina = ["/ruta/babel/casa"]                 # un comando que imprime una página

[apps.vivero]
nombre = "Vivero"                             # opcional; si falta, la clave
archivo = "~/proyectos/plantas/dist-app/vivero.html"   # un HTML autocontenido
memoria = "~/.local/state/vivero.json"        # opcional, solo con archivo

[apps.atlas]
url = "http://servidor:8790"                  # una página servida
```

Una app es algo que se abre y se usa: un juego, un catálogo, un mapa. No tiene hilos (eso es una
sección) ni es una tarea. No van en la barra, que es la del trabajo: van en un menú de la cabecera (el
ícono de los cuatro cuadrados, a la izquierda del modo, que solo está si hay alguna), una línea cada una, en el
orden del archivo. Elegir una abre su página en el panel del dashboard; mientras se la mira, el ícono va en
el color del acento y ella, marcada en el menú.

Cada app tiene **una sola** de tres fuentes, de la más libre a la más simple:

| fuente | qué es | cómo se ve |
| --- | --- | --- |
| `pagina` | un comando que imprime el JSON de una página (el contrato de `telar seccion`, en `docs/contratos.md`) | lo que diga la página: bloques, ítems, lienzos. El comando puede armar el HTML en cada pedido o leer un estado |
| `archivo` | la ruta de un `.html` **autocontenido** (todo adentro: sin rutas relativas ni red) | un lienzo a todo el panel; con `memoria`, el HTML guarda y recupera con `window.lienzo` |
| `url` | una página servida (`http://` o `https://`) | un marco a todo el panel, y un botón «↗ abrir en el navegador» por si no carga |

Una app también puede venir de un módulo (`[modulos]`, abajo): su `modulo.toml` la declara con
las mismas claves en `[app]`.

Las tres llegan al panel como una página del mismo contrato (`telar app <clave> --json`), así que
una app nueva no toca la extensión: basta declararla. Los límites son los del lienzo (sandbox, sin
red, sin `localStorage`) para `archivo`; una `url` corre con su propio origen, que el panel agrega
a su CSP, y no alcanza al panel. Un proyecto que quiera ser app arma su HTML autocontenido (un
script de build, p. ej. con `vite-plugin-singlefile`) o sirve su página, y se declara aquí.

`telar app` lista las declaradas y `telar app <clave>` muestra su página en la terminal.
Una `[secciones.x]` que solo tenía `home` y ningún hilo era una app con otro nombre: muévela a
`[apps.x]` con `pagina` en lugar de `home`.

## `[modulos]` — lo que se instala de una vez

Lo de siempre es instalarlo de un catálogo: `telar modulos catalogo` muestra lo que hay (el oficial, el de tu
equipo, otros) y `telar modulos instalar <nombre>` lo baja en la versión que dice el catálogo; en la página, ⚙ →
módulos. Encenderlo o apagarlo sin desinstalarlo, `telar modulos activar|desactivar`. Escribir y publicar uno: la
skill `/modulos` y [modulos.md](modulos.md), que es también el formato del manifiesto y del catálogo
(`.telar/catalogo.toml`). Los catálogos que se leen, además del oficial y el de cada repo:

```toml
[catalogos]
oficial = true                                     # false: no leer el de telar
fuentes = ["https://example.org/.telar/catalogo.toml", "~/catalogos/mio.toml"]   # «sin revisar»
```

```toml
[modulos.nino34]
carpeta = "~/proyectos/nino34"     # una carpeta con modulo.toml
activo = false                     # opcional: instalado pero apagado
```

Un **módulo** es una carpeta que trae todo lo que una cosa necesita para estar en telar: una pestaña
del dashboard, una app del panel, procesos periódicos y lo que esos procesos dejan cada día. Sin
módulo, cada pieza se declara aparte (`[bloques]`, `[apps]`, `periodicos.toml`, `[resultados]`) y en
dos máquinas; con módulo, la carpeta lo dice en su `modulo.toml` y la configuración solo la nombra.
Puede vivir en cualquier parte: dentro de otro proyecto, o en un repositorio propio.

```toml
# <carpeta>/modulo.toml
descripcion = "la temperatura del mar en Niño 3.4"

[pestana]                    # como un [bloques.x]: nombre, comando, color, tecla, en o dentro
nombre = "niño 3.4"
comando = ["bin/nino34", "pagina"]

[app]                        # como un [apps.x]: pagina, archivo o url (y nombre, descripcion, memoria)
archivo = "dist/app.html"

[periodicos.bajar]           # como un proceso de periodicos.toml; corre en la carpeta del módulo
cuando = "30 7,15 * * *"
comando = "bin/nino34 bajar"

[resultado]                  # como un [resultados.x]: lo que el periódico deja por día
carpeta = "~/.local/state/nino34"
```

Todas las secciones son opcionales. Lo que aporta toma el nombre del módulo: la pestaña es el bloque
`nino34` (y su pestaña `bloque:nino34`), la app `nino34`, el resultado `nino34`, y cada periódico
`<módulo>-<nombre>` (o `<módulo>` si se llama igual). Las rutas relativas son de la carpeta del
módulo. El resultado se lee donde corren los periódicos (`[periodicos] en`), porque es allá donde
lo escribe. Un nombre que ya está declarado a mano es un error: hay que elegir uno de los dos.

Se instala en **cada máquina que lo usa**: la que muestra la pestaña y la que corre los periódicos.
En esta, después de instalarlo o de cambiar su manifiesto, `telar periodicos aplicar` lo pone en el
crontab. Sus periódicos se ven en `telar periodicos` como los demás, pero no se escriben en
`periodicos.toml` ni se cambian con `editar`, `pausar` o `borrar`: se cambian en su `modulo.toml`.
`telar modulos` lista los instalados y lo que trae cada uno; ⚙ configuración, en la página, también.

### Órdenes y consultas de un módulo

```toml
[ordenes.vecinos]            # telar <modulo> vecinos …
descripcion = "las conexiones de un documento"
comando = ["bin/grafo", "vecinos"]
consulta = true              # también desde la página, la API y otra máquina

[instalar]                   # corre al instalarlo y al actualizarlo, en su carpeta
comando = ["python3", "-m", "venv", ".venv"]
```

Cada `[ordenes.<verbo>]` es una orden de telar: `telar <modulo> <verbo> [args…]` corre su `comando` con
los argumentos detrás, donde estás, con la terminal. Con `consulta = true` también se le pregunta sin
terminal: `GET /modulos/<modulo>/<verbo>?…` (los parámetros de la dirección le llegan como un objeto JSON
por la entrada, con `TELAR_CONSULTA=1`, y devuelve un objeto JSON; corre en la carpeta del módulo, hasta
30 s), y con `&maquina=<m>` la responde el telar de esa máquina, por el bus, con el módulo instalado allá.
Las dos reciben `TELAR_RAIZ`, `TELAR_REPOS` (los de `[repos]`, en JSON), `TELAR_MAQUINA`, `TELAR_MODULO` y
`TELAR_PERSONA` (la del entorno si ya viene, si no la de `[bus] persona`, o el usuario del sistema), y lo mismo los comandos que imprimen sus páginas
(el de su pestaña, también con `--item`, el de su app y el de su `[configurar]`) y sus periódicos. Una pestaña, una
app o un periódico declarado a mano (`[bloques]`, `[apps]`, `[vistas]`, `periodicos.toml`) no los recibe: corre con
el entorno de telar.
Una consulta que no se puede hacer sale con 1 e imprime `{"error": "…", "codigo": 409}`: si el código es un 4xx (404
no está, 409 cambió desde que se leyó, 403 no te toca, 422 el pedido no sirve), quien la pidió recibe ese código y ese
texto (la API, el bus, la acción de un tipo de objeto); cualquier otra salida con error es una falla del módulo (502).
Un módulo corre aparte: si se cae, telar sigue. Lo que sí detiene a telar es un módulo declarado que no se puede
leer (su entrada en `[modulos]` está mal, su carpeta o su `modulo.toml` no están, el manifiesto está mal, o lo
que aporta choca con algo declarado a mano): la configuración es un error y las órdenes no arrancan. `telar doctor` arranca igual, sin él, y dice cuál es y por qué (una falla).

Un módulo también puede decirle algo al agente de cada hilo, al arrancar, junto a lo que telar ya le dice
(qué hilo es, su casilla): `[contexto] texto = "…"`, hasta 600 caracteres, porque entra en cada sesión.
Es lo que hace que un agente sepa que el módulo está y cuándo usarlo.

### Instalar un módulo desde un repositorio

```
telar modulos instalar https://github.com/alguien/telar-grafo   # o la carpeta de un repositorio git
telar modulos actualizar grafo                                  # git pull y su [instalar] de nuevo
telar modulos quitar grafo
```

`instalar` clona el repositorio en `~/.local/share/telar/modulos/<nombre>`, muestra lo que trae y, con tu
sí (`--si` para no preguntar), corre su `[instalar]` y lo anota en `modulos.toml`, al lado de la
configuración. Ese archivo es solo de `telar modulos`; la configuración la sigue escribiendo quien la
escribe, y un mismo nombre en los dos es un error. El nombre sale de `nombre` en el manifiesto, o del
repositorio sin `telar-` (`--nombre` lo cambia). `--enlazar` usa la carpeta donde está, sin copiarla,
para desarrollar un módulo, o para uno que vive dentro de otro repositorio.

Un módulo con periódicos no pide nada más: en la máquina donde corren (`[periodicos] en`), instalarlo,
actualizarlo, adoptarlo o quitarlo deja el crontab al día; en otra, telar dice que allá también hay que
instalarlo. Lo que el módulo necesita en la máquina (un programa en el PATH) lo declara `[requiere]
programas = ["uv"]`, y se mira antes de instalar.

Un módulo puede traer **tipos de objeto** (telar.objetos), que se ven y se actúan por su dirección como los de
fábrica (`telar objeto correo:1a2b`):

```toml
[objetos.correo]
ver = "correo-ver"         # una de sus [ordenes] con consulta = true: recibe {"id": …} y da el objeto
acciones = ["archivar"]    # otras consultas suyas: reciben {"id": …, más los parámetros}
esperando = "correo-esperan"   # opcional: otra consulta, los suyos que esperan a la persona (telar esperas)
listar = "correos"         # opcional: otra consulta, todos los suyos (telar objeto correo --listar)
plural = "correos"         # opcional: cómo se llaman juntos en una lista (su fuente en telar buscar); sin él, el tipo
descripcion = "un correo"
```

El `ver` devuelve un objeto JSON con lo que tenga de `titulo`, `estado`, `resumen`, `campos`, `enlaces` y
`acciones`; telar pone la dirección. Un módulo no puede pisar un tipo de fábrica (tarea, hilo, proyecto,
archivo, pendiente, agente, encargo, permiso, idea, mensaje).

Con `esperando`, los objetos del módulo que esperan una decisión de la persona entran a `telar esperas` (y a `GET
/esperas`) junto a los de fábrica. La consulta recibe `{}` y devuelve `{"esperas": [{"id", "clase", "desde",
"titulo", "resumen", "enlaces", "campos"}]}`: telar pone la dirección (`correo:<id>`) y el tipo, y sin `clase` usa el
nombre del tipo. `desde` es una fecha o fecha y hora ISO; `enlaces`, direcciones. Lo que no trae `id` se deja fuera,
y si la respuesta no tiene esa forma, o la consulta falla, la bandeja lo dice en `fallas` y muestra lo demás (la forma
entera, en [contratos.md](contratos.md), «telar esperas --json»).

Con `listar`, el tipo da la lista de los suyos: `telar objeto correo --listar` y `GET /objetos/correo`. La consulta
recibe `{"tipo": "correo"}` (así una misma orden puede servir a varios tipos del módulo) y devuelve `{"objetos": [{"id",
"titulo", "estado", "resumen", "campos", "enlaces", "acciones", "version"}], "fallas": ["…"]}`, cada objeto con lo que
tenga de lo que da su `ver`: telar pone la dirección (`correo:<id>`) y el tipo, y sin `acciones`, las del tipo.
`fallas` es opcional (lo que el módulo no pudo leer); lo que no trae `id` o no tiene la forma de un objeto se deja
fuera y se suma ahí. Si la respuesta no tiene esa forma, es una falla del módulo (502). Sin `listar`, el tipo dice que
no lista (404). La forma entera, en [contratos.md](contratos.md), «telar objeto».

Un tipo que lista es además una fuente de `telar buscar` y de la búsqueda de Todo (`objeto:<tipo>`, con su `plural` de
nombre): sus objetos calzan por título, id y resumen, y `campos.ruta` dice dónde viven. Si un objeto vive en un
archivo, que lo diga para que caiga en su mundo: `campos.ruta_abs` (la ruta absoluta; con ella, el objeto *es* ese
documento, y un clic en Todo lo abre en el visor) o `campos.archivo` (una dirección `archivo:<ruta>`, y se abre por su
dirección). Lo de cada fuente, en [contratos.md](contratos.md), «telar buscar --json».

### Lo que pide un módulo

```toml
[permisos]                       # lo que pide fuera de su carpeta
leer = ["~/datos/oceano"]        # rutas que lee
escribir = ["~/.local/state/nino34"]
red = ["psl.noaa.gov"]           # los sitios a los que se conecta; true: cualquiera; false o nada: ninguno
ordenes = ["mensaje", "tipo tarea"]   # las órdenes de telar que corre («telar mensaje» vale igual)
```

`telar modulos instalar` lo muestra antes de preguntar («pide: leer ~/datos/oceano; red: psl.noaa.gov; …»),
`telar modulos` lo lista (y `--json`, en `permisos`), y `actualizar` dice si cambió desde lo que se vio al instalarlo
(o en la actualización anterior: queda anotado en `modulos.toml`, también para uno `--enlazar`). Lo que se lee igual
es lo mismo: las rutas en otro orden, o `red = []` y `red = false`. Un carácter de control en lo que pide (un ESC) se
muestra escapado, para que no borre la línea antes del sí.
**telar todavía no lo hace cumplir**: un módulo corre con los permisos de quien lo instaló, lo declare o no, y la
instalación lo dice. Es el primer paso de los permisos ([propuestas/permisos.md](propuestas/permisos.md)): que
quien instala sepa lo que el autor dice que el módulo hace. Sin la tabla, el módulo «no dice qué pide», que no es
lo mismo que no pedir nada (`[permisos]` vacía). Una clave que esta versión no entiende no impide instalarlo: se
muestra tal cual, como no entendida. Un telar anterior a esta tabla no la conoce y no lee el módulo que la trae
(como con cualquier sección nueva del manifiesto).

`telar modulos adoptar <nombre>` pasa uno declarado a mano en la configuración (`[modulos.<nombre>]`) a
`modulos.toml`, enlazado a su carpeta: saca su bloque de la configuración (que queda respaldada al lado) y
desde ahí se actualiza y se quita como los demás.

## `[dashboard]` — qué pestañas se ven y en qué orden

```toml
[dashboard]
orden = ["ahora", "revisar", "bloque:correo", "calendario"]
ocultas = ["periodicos"]
```

Las pestañas son las filas del grupo DASHBOARD, arriba en la barra de la izquierda de la página. Lo escribe
⚙ configuración (✓ para mostrar u ocultar, ↑↓ para mover), o `telar config --pestanas
"ahora,revisar,-periodicos"` (con «-», oculta). Las que `orden` no nombra: una de fábrica (como `esperas`, que
llegó después) va junto a su vecina de siempre, tras la que la precede (`esperas`, tras `ahora`); la de un módulo o
un proveedor va al final, en su orden: así la de un módulo nuevo aparece sola. ⚙ guarda la lista entera, así que eso
solo pasa con lo que llegó después de guardarla o con una lista escrita a mano. Las claves: `ahora`, `esperas` (te
esperan), `revisar` (tareas), `proyectos`, `calendario`, `bloque:<clave>` para cada bloque y
`pestana:<nombre>` para la de un proveedor. Una pestaña oculta sigue respondiendo a su tecla. Esto vale para todos
los modos: una oculta no se ve en ninguno, y este orden es el de un modo que las ve todas; cuáles ve cada modo, y en qué
orden si las nombra, lo dice su `filas` (ver `[modos]`, y ⚙ modos › pestañas). Los periódicos y
los mensajes entre agentes ya no son pestañas: están en ⚙ configuración (teclas `o` y `c`), y `periodicos` y
`correo` en `orden` u `ocultas` se ignoran. La pestaña del plan se sacó (18-nov-2026): `plan` en `orden` u `ocultas`
tampoco cuenta, y `telar doctor` avisa para que se borre.

## `[hilos]` — de qué carpetas salen

```toml
[hilos]
directorios = ["operacion/proyectos", "negocio/pipeline"]   # relativas a la raíz
tope = 8                                                     # cuántos abre `tejer` de una vez
dormir_tras = "30m"                                          # quieto tanto, su agente se cierra (0: nunca)
```

Sin `directorios`, `tejer` abre las unidades del perfil en el orden en que el perfil
declara sus arquetipos. Con directorios, solo las que viven dentro de alguno, repartidas
por turnos —una de cada carpeta por vuelta— para que la segunda aparezca aunque la
primera tenga más unidades que el tope. Las carpetas que empiezan con `_` o `.`
(`_perdidos`) nunca son unidades.

`tejer` solo abre hilos al levantar la sesión. Con la sesión viva, `telar tejer --sumar`
abre los que falten según `[hilos]`, sin tocar los abiertos ni los archivados. Se cambian
con `telar config --directorios "a, b"` y `--tope N`, o desde **⚙ configuración**.

### Dormir: `dormir_tras`

Un agente quieto ocupa lo mismo que uno que trabaja (Claude Code, unos 300 MB). Con `dormir_tras` (de fábrica `"30m"`;
`"1h"`, `"90s"`, `"1h30m"`, o minutos sueltos; `0` o `"nunca"` lo apaga), el nodo de cada máquina duerme a los hilos
de esa máquina que llevan ese tiempo quietos: cierra su agente y deja su ventana en su lugar de la lista, con una línea
que dice desde cuándo duerme (◌ y un aro tenue en la página). Su conversación queda en disco y abrirlo la retoma, en
unos segundos: un clic en la lista o en ⌘K, su terminal, `telar ir`, `telar hilo retomar` o `despertar`, un ⏎ en su
ventana (lo que se escribió antes le llega como primer mensaje), y también un mensaje del bus, un encargo o lo que otro
hilo le escriba. Es por máquina: cada una en su `config.toml`.

Duerme solo lo que está seguro de que está quieto; ante la duda, despierto. Nunca duerme un hilo trabajando o que te
espera (su atención, o lo que dice su pantalla), con texto escrito sin enviar, con una pregunta en pantalla, con algo
en segundo plano (una tarea de Bash, un Monitor, un `/loop` o un cron de la sesión), con mensajes por entregar, el que
se mira (una terminal enganchada a su ventana, lo que muestra una página abierta, o lo que se mira desde otra
máquina), uno residente para siempre (`residente = "siempre"`), ni uno con actividad en `dormir_tras` (su último
prompt, su último foco, lo último escrito en su conversación, cuándo arrancó su agente). `telar hilo dormir --seco`
dice por qué cada hilo de aquí se dormiría o no; `telar hilo dormir` duerme uno ya. Los que duermen no cuentan para
`[agente] max_vivos`.

### Archivar y retomar

Cada agente que telar abre nace con un id de conversación que telar elige
(`claude --session-id <uuid>`) y guarda junto al hilo. Por eso:

- `telar hilo cerrar` (✕ en la lista) cierra el tab y lo que corra adentro, y olvida el
  hilo: sale de la lista. Lo que se quiere guardar se archiva.
- `telar hilo archivar --cerrar` (⏸ en la lista) hace lo mismo y además lo manda al
  archivo: tejer la sesión otra vez no lo reabre.
- `telar hilo retomar` (▶, o pinchar un hilo sin tab) reabre el tab en su carpeta con
  `claude --resume <ese id>`. No hay que buscar el id ni escribirlo.

`/clear` dentro de Claude abre otra conversación con otro id, que telar solo conoce si
están los ganchos (`telar agente instalar`). Sin ellos, retomar vuelve a la de antes del
`/clear`.

## `[ficha]` — quién arma la ficha de un documento

```toml
[ficha]
proveedor = "documento"          # documento (por defecto) · comando
cascada.resumen = ["estado", "campo:Etapa"]
maximo = 6                       # cuántos pendientes se leen; 0 = todos
```

`documento` lee el markdown con lo que declara el perfil; `comando` corre un programa
que imprime el JSON de la ficha (ver `docs/contratos.md`). Es tabla aparte de
`[proveedores.*]`, que son los que traen ítems del día: si declaras `[proveedores.estado]`,
telar te dirá que no conoce ese proveedor, porque ahí no vive.
