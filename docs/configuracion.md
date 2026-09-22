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
```

`reunion` es lo que se le dice al agente cuando se pincha una reunión en la agenda del
dashboard (o con `telar reunion "<título>" HH:MM`): se abre un tab «◷ hora reunión» con
el agente, y ese es su primer mensaje. Marcadores: `{titulo}`, `{hora}`, `{fecha}`,
`{enlace}` y `{proyecto}`, que es la carpeta del perfil que comparte palabras con el
título; si no hay ninguna, la cola «· proyecto: …» se quita. El de fábrica es el de flow
y supone la skill `/preparar-reunion` instalada; cualquier otra skill o una instrucción
en prosa sirven igual. Se cambia desde **⚙ configuración** en el dashboard, o con
`telar config --reunion "…"` (vacío vuelve al de fábrica).

Con un agente declarado, `telar tejer` abre cada hilo con el agente adentro, retomando
la conversación que ese hilo ya tenía si su archivo sigue existiendo. En una sesión que
ya estaba tejida, `telar agente abrir --todos` lo pone en los hilos que no lo tengan, y
solo reemplaza **shells ociosas**: una shell sin procesos hijos. Lo que la persona dejó
corriendo no se toca.

`carpeta` decide dónde arranca el agente, no dónde vive el hilo: la ruta del hilo sale
de su vínculo, así que un agente que arranca en otra parte no se la cambia. Existe
porque hay agentes cuya memoria y configuración cuelgan de la carpeta donde arrancan
(Claude Code lee `CLAUDE.md` y `.claude/` desde ahí), y abrirlos en otra carpeta es
abrir a otro, que no recuerda nada.

Al salir del agente queda una shell, no se cierra el tab. Y el agente arranca sin las
variables de otro multiplexor (`ZELLIJ_*`): si tmux se levantó desde dentro de Zellij,
los ganchos de Zellij creerían que el agente es uno de sus paneles.

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

- `telar hilo archivar --cerrar` (⏸ en la lista) cierra el tab y la conversación queda
  guardada; tejer la sesión otra vez no lo reabre.
- `telar hilo retomar` (▶, o pinchar el archivado) reabre el tab en su carpeta con
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
