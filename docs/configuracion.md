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
# Qué multiplexor de terminal hay debajo: "tmux" o "zellij".
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

### El calendario: iCal o gws

La agenda del dashboard sale de una de dos fuentes, y se elige sin editar el archivo:

```sh
telar config --calendario gws                          # Google Workspace, con la CLI gws
telar config --calendario https://…/private-…/basic.ics  # una dirección iCal (o webcal://, o un .ics)
telar config --calendario ninguno                      # sin agenda
```

En VS Code es lo mismo desde el dashboard: **⚙ configuración** dice cuál está en uso,
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
| `multiplexor` | `"tmux"` \| `"zellij"` | `"tmux"` | quién maneja los tabs de verdad |
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
proyecto = "Carga el proyecto {nombre}: lee {documento} y dime en qué está y qué sigue."
pendiente = "{texto}"         # se escribe, sin enviar, al agente de un hilo ya abierto
pendiente_nuevo = "{texto}"   # primer mensaje de un hilo que se abre para el pendiente
contexto = true               # el agente recibe al empezar unas líneas sobre su hilo y los otros
```

`reunion` es lo que se le dice al agente cuando se pincha una reunión en la agenda del
dashboard (o con `telar reunion "<título>" HH:MM`): se abre un tab «◷ hora reunión» con
el agente, y ese es su primer mensaje. Marcadores: `{titulo}`, `{hora}`, `{fecha}`,
`{enlace}` y `{proyecto}`, que es la carpeta del perfil que comparte palabras con el
título; si no hay ninguna, la cola «· proyecto: …» se quita. El de fábrica es el de flow
y supone la skill `/preparar-reunion` instalada; cualquier otra skill o una instrucción
en prosa sirven igual. Se cambia desde **⚙ configuración** en el dashboard, o con
`telar config --reunion "…"` (vacío vuelve al de fábrica).

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
```

Cada atajo es una tecla del dashboard (y un enlace en su sección **Atajos**) que abre un
hilo nuevo con el agente, en `[agente] carpeta`, con `mensaje` como primer prompt. Sirve
para lo que se hace varias veces al día y no es de ningún proyecto: el correo, un chat,
cargar las horas. El hilo se llama `nombre` más la fecha y la hora («⚑ correo 09/23
10:32»), porque la revisión de la mañana y la de la tarde son dos conversaciones.

La tecla es un solo carácter y no puede ser una de las que el dashboard ya usa: las letras
de los pendientes (`a b d e f g h i`), los números de la agenda, `r`, `p`, `t` y `/`.
`telar atajo` lista los declarados y `telar atajo m` hace lo mismo que la tecla.

## `[remotos]` — máquinas donde pueden vivir hilos

```toml
[remotos.casa]
destino = "usuario@servidor"   # lo que va después de mosh/ssh; puede ser un alias de ~/.ssh/config
transporte = "mosh"            # mosh (por defecto) · ssh
raiz = "~/repo"                # la carpeta del repositorio EN esa máquina
correo_archivo = ""            # opcional: la Maildir común con los correos entre agentes
directorio = ""                # opcional: la carpeta común donde cada persona publica sus hilos
```

Un hilo remoto es uno cuyo agente vive en otra máquina, siempre encendida, y sigue
trabajando con el laptop cerrado; la ventana local solo lo mira. telar la arma así:

```
mosh usuario@servidor -- tmux new-session -A -s telar-1a2b3c4d bash -lc 'cd ~/repo/…; <agente>; exec bash -l'
```

Cada hilo remoto tiene su propia sesión tmux allá, con un nombre que telar elige al
crearla y guarda en su estado (`remotos.json`), así que renombrar el hilo no la pierde.
`-A` hace que la misma línea cree la sesión o se enganche a la que ya está: si la ventana
local se cierra sin pasar por telar, la sesión de allá sigue viva y `telar hilo retomar`
vuelve a ella. La carpeta del hilo se traduce: su vínculo relativo a la raíz local es la
misma relativa bajo `raiz` de allá.

- Crear: `telar ir <nombre> --crear --remoto casa`, o en VS Code «hilo nuevo», que pregunta
  dónde si hay algún remoto declarado. La ventana queda con la opción tmux `@telar_remoto`.
- Cerrar (✕) y archivar con `--cerrar` terminan también la sesión de allá; retomar un
  archivado la recrea retomando su conversación.
- `telar doctor` revisa cada remoto: que responda por ssh, que tenga tmux (y mosh-server
  si el transporte es mosh), y avisa si su tmux muestra barra.

Para que no se vean dos barras ni se coma el prefijo, el tmux de la otra máquina va con
`set -g status off` y `set -g prefix None` en su `~/.tmux.conf`. La atención y la ficha del
agente remoto (lo que escriben sus ganchos) todavía no llegan al laptop.

### El correo entre agentes

Si la otra máquina entrega correo local entre agentes (ver
`docs/propuestas/correo-y-celular.md`), cada hilo remoto tiene su dirección:
`usuario+<nombre del hilo>@servidor`, con el nombre en minúsculas, sin acentos y con guiones
(«T42 Faro Norte» → `usuario+t42-faro-norte@servidor`). La sesión de allá lleva su nombre
en la opción tmux `@telar_hilo`, que es por donde el servidor sabe a quién entregar.

- `telar correo` lee por ssh la Maildir, el registro del cartero y, con `correo_archivo`, la
  casilla común: la dirección y los correos **sin entregar** de cada hilo, y las
  conversaciones entre agentes. En VS Code: **✉ N** junto al hilo, la dirección en su ficha
  y la pantalla **✉ correo** del dashboard (tecla `c`).
- Sin entregar es lo que llegó con el hilo cerrado o quedó retenido. Para saberlo, el
  registro del cartero tiene que anotar `id=<Message-Id>` en cada línea; si no lo hace,
  telar lo dice y no cuenta.
- Retomar un hilo con correos sin entregar le avisa al agente cuántos hay y dónde, **sin
  copiarlos**: ese primer mensaje llega con la voz de la persona, y un correo ajeno no puede
  hablar con esa voz.

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

### En el celular: `telar movil`

`mosh usuario@servidor -- ~/.local/bin/telar movil` (en la otra máquina, con telar instalado
allá) abre una lista de sus hilos para pantalla chica: flechas o números eligen, ⏎ o un toque
entran, `c` el correo, `q` sale. Adentro de un hilo hay una barra arriba, `◀ telar · ✉ 2 ·
nombre`: tocar «◀ telar» (o F12) vuelve a la lista, tocar «✉ N» abre el correo encima.

El celular no se engancha a la sesión del hilo sino a una **sesión agrupada** con ella
(`movil-…`): el mismo agente, con barra, mouse y una tabla de teclas propia (`telar-movil`).
El laptop, enganchado a la sesión original, no ve nada de eso. Al volver, la agrupada se
cierra. Para tener F12 en Termux, en `~/.termux/termux.properties`:

```
extra-keys = [['ESC','TAB','CTRL','ALT','UP','DOWN','F12']]
```

## `[secciones]` — grupos propios en la lista de hilos

```toml
[secciones.diario]
nombre = "Diario"
hilos = ["notas", "◌ rato*"]          # nombre exacto, o prefijo si termina en *
home = ["/ruta/a/mi-home", "--json"]  # opcional: un comando que imprime su página
```

Una sección es un grupo con cabecera plegable en la barra de hilos, entre el dashboard y
la lista general. Los hilos que reclama (los vivos; un archivado sigue en el archivo)
salen de la lista general y van ahí. Con `home`, la sección tiene además una fila **home**
que abre su página en el panel del dashboard: telar corre el comando, comprueba que el
JSON tenga la forma del contrato (`docs/contratos.md`, `telar seccion`) y lo dibuja. Un
ítem de la página que trae `conversacion` abre esa conversación entera, con la opción de
retomarla en su hilo. `telar seccion` lista las declaradas y `telar seccion <clave>`
muestra la página en la terminal.

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
