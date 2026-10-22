# Disparadores y estado deseado

Estado: **primer paso hecho** (22-oct-2026): la configuración lee `[disparadores.<nombre>]` con un reloj
(`cuando`), una tecla (`tecla`) o un cambio (`al = "cambio:<tema>"`). El reloj y la tecla se traducen al leer a lo
de hoy (un proceso de `periodicos.toml` y un `[atajos.x]`), que se sigue leyendo; el cambio lo despacha el nodo,
con freno. El nodo avisa en su registro (no arregla) cuando un residente declarado no tiene sesión, y `telar
doctor` lo dice. **Por decidir**: las preguntas de abajo, qué filtra un cambio, y si el nodo arregla además de
avisar. Es el paso 7 de [primitivas.md](primitivas.md).

## Por qué

Hoy hay tres maneras de que algo pase sin que nadie lo pida en el momento, y cada una vive en otro lado:

| hoy | qué lo dispara | dónde se declara | qué hace |
|---|---|---|---|
| un proceso periódico | un horario cron | `periodicos.toml`, al lado de la configuración | un comando, o un mensaje que abre un hilo o se le encarga a un residente |
| un atajo | una tecla del dashboard | `[atajos.<tecla>]` en la configuración | un mensaje que abre un hilo o se le encarga a un residente |
| «al cambiar» | `telar cambio <tema>` | ninguna parte: solo el dashboard relee | nada más |

Los tres terminan en lo mismo (correr un comando o mandar un mensaje), con claves que se parecen pero no son
iguales (`hilo` en uno, `nombre` en otro; `en` es el lugar de la tecla en un atajo y la máquina en todo lo
demás). Y el tercero no existe: un cambio de las tareas no puede rehacer nada. primitivas.md lo junta en una
pieza, el **disparador**: lo que emite un mensaje (o corre un comando) solo, por un reloj, una tecla o un cambio.

## Qué es y cómo se declara

Un disparador es **cuándo** (una de tres claves) y **qué** (un `comando` o un `mensaje`). La clave de la tabla es
su nombre: va en el crontab y en `<estado>/periodicos/<nombre>.json`, así que se escribe como el de un periódico
(minúsculas, números, `-` y `_`).

```toml
[disparadores.resumen]               # un reloj: lo de periodicos.toml
cuando = "30 8 * * 1-5"
comando = "~/bin/resumen --corto"

[disparadores.revisar-correo]        # un reloj que abre un hilo
cuando = "0 9-19/2 * * *"
mensaje = "/correo"
hilo = "✉ correo"
max_abiertos = 2

[disparadores.correo]                # una tecla del dashboard: lo de [atajos]
tecla = "m"
mensaje = "/correo"
hilo = "⚑ correo"                    # el nombre del hilo (en [atajos], `nombre`)
aparece = "correo"                   # dónde se muestra la tecla (en [atajos], `en`): hoy, una vista o seccion:<clave>

[disparadores.tablero]               # al cambiar: lo que anuncia `telar cambio tareas`
al = "cambio:tareas"
comando = "~/bin/tablero --rehacer"
```

**Cuándo.** Exactamente una de:

| clave | qué es | lo de hoy |
|---|---|---|
| `cuando` | un horario cron de cinco campos (o `@daily`…) | un proceso de `periodicos.toml` |
| `tecla` | un carácter: la tecla del dashboard | un `[atajos.<tecla>]` |
| `al` | `"cambio:<tema>"`: cuando alguna máquina anuncia `telar cambio <tema>` | nada (es nuevo) |

**Qué.** Un `comando` (una línea de shell) o un `mensaje` (un prompt), uno de los dos. Con `mensaje`, `agente`
se lo encarga a un residente en vez de abrir un hilo nuevo; si no, `hilo` es el nombre del hilo que se abre.
Las demás claves son las de un periódico: `max_abiertos`, `argumentos`, `carpeta`, `descripcion`, `activo`.

| con | acepta, además de `comando`/`mensaje` |
|---|---|
| `cuando` | `agente`, `hilo`, `max_abiertos`, `argumentos`, `carpeta`, `descripcion`, `activo` |
| `al` | las mismas |
| `tecla` | solo `mensaje` (una tecla abre un hilo, no corre un comando), `agente`, `hilo`, `descripcion`, `aparece`, `activo` |

**Qué reemplaza.**

| antes | ahora |
|---|---|
| `[x]` en `periodicos.toml`, con `cuando`, `comando` o `mensaje`… | `[disparadores.x]` con las mismas claves |
| `[atajos.m] nombre`, `mensaje`, `descripcion`, `agente` | `[disparadores.x] tecla = "m"`, `hilo`, `mensaje`, `descripcion`, `agente` |
| `[atajos.m] en` | `[disparadores.x] aparece` |
| — | `[disparadores.x] al = "cambio:<tema>"` |

## Cómo convive con lo de hoy

- **El reloj se traduce al leer.** `telar periodicos` (y el `correr` que llama cron) suma a lo de
  `periodicos.toml` y a lo de los módulos un proceso por cada `[disparadores.x]` con `cuando`. Corre igual,
  anota igual y se ve igual en la lista; no se escribe en `periodicos.toml`, y `editar`, `pausar` o `borrar` lo
  rechazan diciendo dónde se cambia (como uno de un módulo). Al agregar uno, `telar periodicos aplicar` lo pone
  en el crontab; `telar doctor` avisa si el crontab no está al día con lo declarado.
- **La tecla se traduce al leer.** `telar.config` arma con cada `[disparadores.x]` con `tecla` el `[atajos.<tecla>]`
  equivalente y lo pasa por la misma validación. `cfg.atajos` sale igual, así que `telar atajo`, `/atajos` y
  la página no se enteran. Una tecla en las dos formas es un error claro, y también dos disparadores con la
  misma tecla. `telar doctor` sugiere, por cada `[atajos.x]` declarado a mano, el `[disparadores.x]` que da lo
  mismo, en TOML para copiar.
- **El cambio es nuevo y lo despacha el nodo.** El nodo ya oye `cambio.<persona>.*` (para que el dashboard
  relea). Ahora, además, cuando llega un tema que un `[disparadores.x] al = "cambio:<tema>"` espera, corre su
  comando o manda su mensaje, igual que un periódico (`telar.periodicos.correr`: misma anotación en
  `<estado>/periodicos/<nombre>.json`, mismo log). Con freno (abajo). Sin bus no hay nodo que lo oiga: el
  disparador no corre, y `telar doctor` lo dice.
- **`periodicos.toml` se sigue leyendo y escribiendo**, sin aviso: es lo que editan `telar periodicos nuevo` y la
  página. Sugerir que se mude a `[disparadores]` dejaría a esos procesos sin editor. Se migra cuando
  `telar periodicos` sepa escribir `[disparadores]` (decisión 3).
- **Los módulos siguen igual**: `[periodicos.x]` en `modulo.toml`.
- **Un nombre en dos lados es un error**: un `[disparadores.x]` (de reloj o de cambio) y un proceso `x` de
  `periodicos.toml` o de un módulo comparten el archivo de su última corrida.
- **`telar disparadores [--json]`** los lista todos (cuándo, qué, la última corrida) y `telar disparadores correr
  <nombre>` corre uno de reloj o de cambio ya, para probarlo.

### El freno de «al cambiar»

Un cambio puede llegar en ráfagas (un agente que cierra diez tareas anuncia diez veces), y un disparador puede
anunciar el mismo cambio que lo dispara. Por eso:

- **Uno a la vez por disparador.** Si llega su cambio mientras corre, queda **una** corrida pendiente (no diez),
  que sale cuando termina.
- **Una pausa entre corridas** (`PAUSA`, 30 s): lo que llega antes queda pendiente y sale al cumplirse.
- **Un tope por hora** (`TOPE_POR_HORA`, 12): pasado, el disparador se frena hasta que la hora corra, y el nodo
  lo anota una vez («¿se dispara a sí mismo?»). Lo que llegó mientras tanto no se pierde: sale una vez al
  soltarse.
- **Dos a la vez en todo el nodo**, en un grupo de hilos propio: un comando largo no deja al nodo sin hilos
  para sus vueltas.

Las tres cifras son constantes de `telar.disparadores`, no claves (decisión 5).

## El estado deseado

primitivas.md dice que el nodo «reconcilia el estado deseado»: compara lo declarado con lo que hay y lo iguala.
Lo que reconciliaría, pieza por pieza:

| pieza | lo declarado | lo que hay | arreglar sería |
|---|---|---|---|
| residentes | cada agente de `[agentes] carpeta` que vive aquí, con `residente = true` (su `agente.toml`) | si su hilo tiene sesión viva | abrirle la sesión |
| periódicos | `periodicos.toml`, los de los módulos y los `[disparadores]` de reloj | el bloque de telar en el crontab | `telar periodicos aplicar` |
| disparadores de cambio | los `[disparadores]` con `al` | lo que el nodo despacha (lo leyó al arrancar) | releer la configuración |
| módulos | `modulos.toml` (fuente y versión de cada uno) | la carpeta instalada y su versión | `telar modulos actualizar` |

**Primer paso: avisar, no arreglar.** Hoy `residente = true` quiere decir «se le abre la sesión cuando le llega
algo», no «siempre vivo»: `[agente] max_vivos` cierra a los residentes ociosos para liberar memoria, y abrirlos
de vuelta pelearía con eso. Así que el nodo, cada 30 s, mira qué residentes de aquí no tienen sesión y:

- anota en su registro una línea cuando uno **deja** de estar vivo o cuando, al arrancar, no lo está, y otra
  cuando vuelve. Nunca una por vuelta;
- deja lo que vio en `<estado>/deseado.json` (`{"actualizado", "maquina", "residentes_sin_sesion": [...]}`).

`telar doctor` lo lee en la revisión `deseado` y lo dice sin aviso (`ok`, con los nombres), porque hoy no es una
falla: es el estado que deja `max_vivos`. Si el archivo no está o tiene más de diez minutos, el nodo no corre y
doctor no dice nada de esto. El crontab desfasado sí es un aviso, en la revisión `disparadores` de doctor: es
algo declarado que no está corriendo.

## Las decisiones abiertas

Cada una con la opción que tomé por ahora y por qué.

1. **Tres claves o una.** Elegí tres (`cuando`, `tecla`, `al`), una de ellas obligatoria. Así `cuando` sigue
   siendo exactamente el cron de un periódico, que se copia tal cual, y cada una se valida por su lado. La otra
   opción era una sola (`cuando = "30 8 * * *"`, `cuando = "tecla:m"`, `cuando = "cambio:tareas"`), más
   uniforme pero con un cron que ya no se distingue a simple vista de lo demás.
2. **Dónde viven.** En la configuración (`config.toml`), como las vistas. Un disparador de reloj o de cambio corre
   en la máquina donde corren los periódicos (`[periodicos] en`, o esta si no dice): es la que no se apaga y la
   que ya tiene el crontab. Una configuración copiada en dos máquinas no los corre dos veces: en la otra,
   `[periodicos] en` apunta a la primera, y `telar doctor` lo dice. Falta decidir si se quiere `en` por
   disparador (uno de cambio que corra en el laptop).
3. **`periodicos.toml` y `[disparadores]`.** Conviven, y doctor no sugiere mudar `periodicos.toml`, porque `telar
   periodicos nuevo/editar` y la página escriben ese archivo y no saben escribir la configuración (sí saben
   escribir una clave suelta, `escribir_clave`, pero no una tabla entera conservando los comentarios). ¿Se
   quiere que `telar periodicos` pase a escribir `[disparadores]`, o que `periodicos.toml` quede como el lugar de
   lo que se edita desde la página?
4. **Qué trae un cambio.** Hoy `telar cambio` trae solo el tema y la máquina que lo anunció: no hay «cuando
   llegue un correo de X», porque el cambio no dice qué cambió. Cuando el cambio sea una pieza (primitivas.md,
   «Cambio»: un objeto, qué le pasó y un número de orden), `al` podrá filtrar (`al = "cambio:correo"`,
   `si = "de:ana@…"`) y el disparador recibirá la dirección del objeto en `{direccion}`. Por ahora el comando no
   recibe nada del cambio.
5. **El freno, ¿clave o constante?** Constante (30 s, uno pendiente, 12 por hora). Es lo que evita que un
   disparador que se dispara a sí mismo llene la máquina, y no sé todavía qué valores pediría alguien. Si hace
   falta, `pausa` por disparador es fácil.
6. **Sin bus.** Un disparador de cambio no corre: no hay nodo que oiga. La otra opción era que `telar cambio`,
   sin bus, corriera los disparadores ahí mismo, pero eso lo haría dentro del agente que anunció el cambio,
   esperándolo, y con su entorno.
7. **¿`residente = true` es «siempre vivo»?** Por ahora no: el nodo avisa y nada más. Si se quiere que lo sea, el
   nodo abriría su sesión cuando falte, y `max_vivos` tendría que dejar de cerrar residentes (o cerrarlos solo
   cuando haga falta memoria y no abrirlos de vuelta hasta que les llegue algo). Las dos cosas a la vez no
   pueden ser.
8. **Arreglar el crontab solo.** No: el nodo no reescribe el crontab de nadie, ni al arrancar. Doctor dice el
   arreglo (`telar periodicos aplicar`). Que el nodo lo aplique cuando cambia lo declarado es fácil, pero toca un
   archivo de la persona sin que lo pida.
9. **Releer la configuración.** El nodo lee los disparadores de cambio al arrancar; uno nuevo pide reiniciar el
   servicio (`telar serve`). Que el nodo relea `config.toml` cuando cambie de fecha está en lo que queda.
10. **`activo = false` en una tecla.** La tecla no existe (no se traduce a un atajo). La otra opción era mostrarla
    apagada en el dashboard, pero `[atajos]` no tiene esa idea y la página no sabría qué hacer.

## Lo que queda

- Que `telar periodicos` (y la página) escriban `[disparadores]` (decisión 3), y entonces `telar doctor` sugiera
  mudar `periodicos.toml`.
- `[disparadores]` en `modulo.toml`, en vez de `[periodicos]`.
- El cambio como pieza (un objeto y qué le pasó), y con eso filtros en `al` y `{direccion}` en el mensaje
  (decisión 4). Otros orígenes: `al = "correo:…"`, `al = "hilo:<nombre>:termino"` (el turno de un hilo es un
  cambio, primitivas.md).
- Que el nodo relea la configuración sin reiniciar (decisión 9).
- Arreglar además de avisar: residentes siempre vivos (decisión 7), el crontab al día (decisión 8), los módulos en
  su versión.
- `GET /disparadores` y una vista en la página (hoy la página ve los de reloj en su lista de periódicos, con
  «correr ahora» y dónde se cambian, sin pausar, editar ni borrar).
- Fundir `telar atajo` en `telar mensaje` y los disparadores (primitivas.md, «Cómo quedan las órdenes»).
- Retirar `[atajos]`, con aviso en el CHANGELOG, después de que doctor lleve un tiempo sugiriendo el cambio.
