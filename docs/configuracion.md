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

# Dónde escribir el estado derivado (caché de fichas, semáforo, tiempo por hilo).
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
# Las de `calendario`: tipo (ics | comando | ninguno), y url o archivo.
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
