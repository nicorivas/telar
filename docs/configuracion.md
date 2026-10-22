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

# El telar-perfil.yaml, si no es el de la raíz. Rara vez hace falta.
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
```

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

Sin `detalle`, el proveedor arma él mismo la **ficha** de cada tarea (la propuesta del agente, el contexto,
los enlaces, la historia) y sus botones son acciones del tipo: se corren sobre el archivo con la versión
que mostraba la ficha, y el archivo se commitea y se sube (`telar commit`). Lo propio de cada casa va en sus
opciones:

```toml
agente           = "Ada"                       # quién deja las propuestas («Ada · lo dejó preparado»)
escribir_a       = "Claude"                    # «↩ escribirle a Claude»: a quién se le escribe en un hilo
mensaje_escribir = "/tarea {id} {texto}"       # qué recibe ese hilo (sin esto, no hay botón)
mensaje_procesar = "/avanzar {id}"             # «✓ hecha y procesar ahora» (sin esto, no hay botón)
equipo           = ["Ana", "Marcelo"]          # a quién se puede asignar (más quien ya sea dueño de alguna)
gmail            = { personal = "yo@gmail.com", "*" = "yo@trabajo.com" }   # cómo se abre un origen gmail:
```

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
| `perfil` | ruta | `raiz/telar-perfil.yaml` | el perfil del repositorio |
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
[`telar-perfil.yaml`](perfil.md), y viaja con él.

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
a quién escribirle hasta que arranca. Marcadores: `{texto}`, `{ref}` y `{id}` (el id del
proveedor, como `T84`); un pendiente sin id, como los de los documentos, usa `{texto}`.
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

Al salir del agente queda una shell, no se cierra el tab. Y el agente arranca sin las
variables de otro multiplexor (`ZELLIJ_*`): si tmux se levantó desde dentro de Zellij,
los ganchos de Zellij creerían que el agente es uno de sus paneles.

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

La tecla es un solo carácter. Si es una que ya usa el dashboard (`n` ahora, `v` tareas, `p` proyectos, `r`
recargar, `o` periódicos, `d` el plan, `a` la agenda, `c` el correo, `/` buscar, o la de un bloque o un
proveedor con pestaña propia), la pestaña gana: el atajo se muestra sin tecla y se lanza con un clic, y
`telar doctor` lo avisa. Las filas de la agenda y de los pendientes no llevan tecla: se
clican.
`telar atajo` lista los declarados y `telar atajo m` hace lo mismo que la tecla.

`en` dice dónde se ve el atajo; la tecla funciona desde cualquier pestaña:

| `en` | dónde |
| --- | --- |
| `"hoy"` | no se muestra: va solo con su tecla (el dashboard ya no tiene barra arriba) |
| `"<clave>"` | el título del bloque `[bloques.<clave>]`, en su pestaña |
| `"seccion:<clave>"` | el título de la pestaña de esa sección |

## `[bloques]` — pestañas del dashboard que llena un comando

```toml
[bloques.correo]
nombre = "correo"
comando = ["/ruta/a/mi-correo", "--json"]
color = "rojo"        # azul, amarillo, verde, rojo, magenta, cian o violeta; cian si falta
tecla = "e"           # opcional: la tecla de su pestaña

[bloques.retro]
nombre = "retro"
comando = ["/ruta/a/mi-retro"]
en = "plan"           # opcional: arriba de la pestaña del plan, y solo cuando trae algo
```

Cada bloque es una pestaña del dashboard, después de «tareas», con su nombre; con `en = "plan"`
va en cambio arriba del plan del día, y no se muestra mientras no traiga nada (una retro que
aparece a la tarde). El comando imprime
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
Un ítem con `id` muestra además su detalle al abrirlo (el cuerpo de un correo, cinco líneas y «ver
todo»): el dashboard corre `telar bloque <clave> --item <id>`, que llama al comando del bloque con
`--item <id>` al final; el comando imprime `{"texto": "…"}`. Se pide al abrir el ítem, no en cada
lectura del bloque. Con `enlace`, el título del ítem abierto lleva al original, en una pestaña nueva.
(`reusar`, que pedía abrirlo en la pestaña de Chrome ya abierta, se acepta pero ya no hace nada: lo hacía
la extensión de VS Code.)

## `[repos]` — los repositorios de trabajo

```toml
[repos.vida]
ruta = "~/Life"
[repos.brinca]
ruta = "~/Life/brinca"            # puede estar dentro de otro
[repos.telar]
ruta = "~/Life/nico/proyectos/telar"
perfil = "~/notas/telar-perfil.yaml"   # opcional: si su perfil no está en su carpeta
```

Los hilos trabajan en carpetas de uno u otro repositorio, y cada uno trae su perfil (`telar-perfil.yaml` en su
carpeta): qué es ahí una unidad de trabajo. telar los junta en uno (`docs/perfil.md`, «Varios repositorios»).
Si dos perfiles reconocen la misma carpeta, gana el del repo más profundo: el de un repo del equipo dentro del
de vida describe lo suyo. Un repo sin perfil no aporta nada, y uno fuera de `raiz` todavía no se suma. Sin
`[repos]`, solo cuenta `raiz`, como siempre.

## `[remotos]` — máquinas donde pueden vivir hilos

```toml
[remotos.casa]
destino = "usuario@servidor"   # lo que va después de mosh/ssh; puede ser un alias de ~/.ssh/config
transporte = "mosh"            # mosh (por defecto) · ssh
raiz = "~/repo"                # la carpeta del repositorio EN esa máquina
directorio = ""                # opcional: la carpeta común donde cada persona publica sus hilos
repos = ["~/repo", "~/repo/otro"]  # opcional: repositorios que viven en las dos máquinas
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
max_abiertos = 2                     # con tantos sin cerrar, esta vez no abre otro
argumentos = ["--permission-mode", "acceptEdits"]   # para el agente, después del prompt
carpeta = "~/trabajo"                # dónde corre (por defecto, el hogar)
activo = false                       # pausado
```

`telar periodicos` los lista con la próxima y la última corrida; `nuevo`, `editar`, `pausar`,
`activar`, `borrar` y `zona` los cambian y reescriben el crontab al tiro; `ahora` corre uno ya;
`log` muestra su salida. En el crontab, telar maneja **solo un bloque entre marcas** (`# >>> telar
periodicos` … `# <<< telar periodicos`), al final, y no toca lo de afuera. Cada línea llama a
`telar periodicos correr <nombre>`, que anota la corrida en `<estado>/periodicos/`. Un `mensaje`
abre una sesión `telar-…` con `@telar_hilo`, como los hilos remotos, así que otra máquina la trae a
su lista. Cada cambio guarda la versión anterior en `periodicos.toml.anterior`.

En **la otra máquina** (el laptop), `[periodicos] en` dice dónde viven, y la orden y la sección
«periódicos» de ⚙ configuración (tecla `o` en el dashboard) los ven y los cambian allá, por ssh:

```toml
[periodicos]
en = "servidor"                      # el nombre de un [remotos.<nombre>]
```

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
van todos bajo una cabecera **Agentes**, cada uno desplegable con un **home** y sus hilos. El home lo
arma telar (`telar seccion agente:<carpeta>`): el primer párrafo de su `CLAUDE.md`, su bitácora
(`bitacora.md`, la entrada más nueva arriba) y el índice de su memoria (`memoria/MEMORY.md`), con
cada archivo para abrirlo. Un hilo vinculado a la carpeta del agente **arranca ahí**, aunque
`[agente] carpeta` diga otra cosa: así Claude carga el `CLAUDE.md` del agente (y los de las carpetas de
arriba) desde el comienzo.

**Encargos.** A un residente no se le abre una sesión por tarea: `telar encargar <agente> "…"` le escribe
a su hilo de siempre si está libre, lo deja en cola si está trabajando (el gancho `Stop` le entrega el
siguiente al terminar) o abre su sesión retomando su conversación. Si esa conversación pesa más de
`[agentes] rotar_mb` (MB), empieza una nueva. Un proceso periódico con `agente = "<carpeta>"` y un
`mensaje` es un encargo. Los argumentos para el agente al abrir su sesión (permisos, herramientas) van
en `[agentes.<carpeta>] argumentos`.

```toml
[agente]
max_vivos = 4                        # sesiones propias vivas a la vez en esta máquina (0: sin tope)

[agentes]
carpeta = "agentes"
rotar_mb = 8

[agentes.gestion]
argumentos = ["--permission-mode", "acceptEdits"]
```

`max_vivos` cuenta las sesiones propias (las de los periódicos, los encargos y el celular). Antes de
abrir otra, telar cierra las ociosas que nadie está mirando, la más quieta primero y los residentes al
final; su conversación queda en disco y se retoma cuando haga falta.

## `[bus]` — mensajes y estado entre varias máquinas

```toml
[bus]
url = "nats://<IP privada de la máquina que no se apaga>:4222"
token = "~/.config/telar/bus.token"   # tu secreto: el mismo archivo en todas tus máquinas
persona = "nico"                       # tu cuenta en el bus (por defecto, tu usuario del sistema)
maquina = "laptop"                     # cómo se llama esta en el bus (por defecto, su nombre de red)
```

Con `[bus]`, cada máquina corre `telar nodo` (`servidor/telar-nodo.service` en Linux,
`servidor/telar-nodo.plist` en macOS) y la que no se apaga corre además el bus
(`servidor/telar-bus.service`, nats-server). `telar mensaje <hilo|agente> "…"` le escribe a cualquier
hilo, viva donde viva: el mensaje espera en su casilla hasta que lo recoja la máquina donde vive y entra
a la conversación por los ganchos del agente (`telar agente instalar`), sin teclearse. `telar encargar`
usa el bus si lo hay. El estado de cada hilo (máquina, atención) se publica y se escucha al instante.
Diseño: `docs/arquitectura.md`, «Entre máquinas: el bus».

El servidor del bus tiene **una cuenta por persona**: lo de una no lo ve otra. Se administran en la
máquina del bus con `telar bus persona NOMBRE` (una cuenta nueva o una clave nueva; para ti, con tu
`[bus] token`; para otra persona genera un secreto que hay que pasarle), `telar bus personas` y `telar bus
quitar NOMBRE`, y después `systemctl --user reload telar-bus`. Un bus de antes, con un solo token para
todos (`nats-server --auth`), se sigue aceptando hasta la 0.3; para pasarlo a cuentas, ver
`servidor/telar-bus.service`. Sin `[bus]`, todo sigue en una sola máquina, como siempre.

## `[equipo]` — que alguien de confianza vea tus tareas y te sugiera prioridades

```toml
[equipo]
tareas   = "~/Life/nico/proyectos/tareas"   # una tarea por archivo con front-matter (T123.md)
todo     = "~/Life/nico/proyectos/todo"     # el CLI que cambia la prioridad al aceptar
etiqueta = "equipo"                         # solo se comparten las tareas con esta etiqueta
puerto   = 8766
[equipo.personas]
marcelo  = "…"                              # `telar equipo token marcelo` da una llave
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
sección) ni es una tarea. Van todas bajo una cabecera **APPS** de la barra, plegable, una fila cada
una, en el orden del archivo; un clic abre su página en el panel del dashboard, y su fila queda
marcada mientras se la mira.

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

[pestana]                    # como un [bloques.x]: nombre, comando, color, tecla, en
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
Las dos reciben `TELAR_RAIZ`, `TELAR_REPOS` (los de `[repos]`, en JSON), `TELAR_MAQUINA` y `TELAR_MODULO`.
Un módulo corre aparte: si se cae, telar sigue.

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
para desarrollar un módulo.

## `[dashboard]` — qué pestañas se ven y en qué orden

```toml
[dashboard]
orden = ["ahora", "revisar", "bloque:correo", "calendario"]
ocultas = ["periodicos"]
```

Las pestañas son las filas del grupo DASHBOARD, arriba en la barra de la izquierda de la página. Lo escribe
⚙ configuración (✓ para mostrar u ocultar, ↑↓ para mover), o `telar config --pestanas
"ahora,revisar,-periodicos"` (con «-», oculta). Las pestañas que `orden` no nombra van después, en su
orden de siempre: así la de un módulo nuevo aparece sola. Las claves:
`ahora`, `revisar` (tareas), `proyectos`, `plan`, `calendario`, `bloque:<clave>` para cada bloque y
`pestana:<nombre>` para la de un proveedor. Una pestaña oculta sigue respondiendo a su tecla. Los periódicos y
los mensajes entre agentes ya no son pestañas: están en ⚙ configuración (teclas `o` y `c`), y `periodicos` y
`correo` en `orden` u `ocultas` se ignoran.

## `[hilos]` — de qué carpetas salen

```toml
[hilos]
directorios = ["operacion/proyectos", "negocio/pipeline"]   # relativas a la raíz
tope = 8                                                     # cuántos abre `tejer` de una vez
```

Sin `directorios`, `tejer` abre las unidades del perfil en el orden en que el perfil
declara sus arquetipos. Con directorios, solo las que viven dentro de alguno, repartidas
por turnos —una de cada carpeta por vuelta— para que la segunda aparezca aunque la
primera tenga más unidades que el tope. Las carpetas que empiezan con `_` o `.`
(`_perdidos`) nunca son unidades.

`tejer` solo abre hilos al levantar la sesión. Con la sesión viva, `telar tejer --sumar`
abre los que falten según `[hilos]`, sin tocar los abiertos ni los archivados. Se cambian
con `telar config --directorios "a, b"` y `--tope N`, o desde **⚙ configuración**.

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
