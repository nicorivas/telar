# Hilos remotos

Propuesta, 23-sep-2026. Estado: **implementada** el mismo día (ver al final qué cambió
respecto de esta propuesta). La referencia viva es `docs/configuracion.md`, `[remotos]`.

## Para qué

Una persona quiere que ciertas conversaciones con su agente sigan trabajando cuando
cierra el laptop. La salida es que el agente viva en otra máquina (un servidor siempre
encendido) y que el hilo local sea solo la ventana desde donde se lo mira. Todo lo demás
de telar —la lista, la ficha, los vínculos, la extensión— sigue en el laptop.

Ya se probó a mano y funciona: una ventana tmux local que corre

```
mosh usuario@servidor -- tmux new -A -s <sesion-remota>
```

muestra un agente que vive en el tmux del servidor. Al cerrar el laptop la ventana local
se congela, el agente remoto sigue; al abrirlo mosh reconecta solo. Lo que falta es que
telar lo sepa hacer, lo sepa reconocer y lo muestre.

## Qué es un hilo remoto

Un hilo cuya ventana local corre un cliente de conexión (mosh o ssh) a una sesión tmux de
otra máquina, **dedicada a ese hilo**: una sesión remota por hilo, no una ventana dentro
de una sesión remota compartida. Así `tmux new -A -s` sirve a la vez para crear y para
reconectar, y cerrar un hilo no toca a los otros.

El tmux del servidor se configura para ser invisible desde dentro del local: sin barra
(`status off`) y sin prefijo (`prefix None`), para que el prefijo llegue solo al tmux del
laptop. Documentarlo; `telar doctor` puede avisar si el remoto tiene barra.

## Configuración

```toml
# Máquinas donde pueden vivir hilos. Sin esta sección, nada cambia: no hay hilos remotos
# y la extensión no pregunta.
[remotos.casa]
destino = "usuario@servidor"   # lo que va después de mosh/ssh; puede ser un alias de ~/.ssh/config
transporte = "mosh"            # mosh (por defecto) · ssh
raiz = "~/repo"                # carpeta del repo EN el servidor: ahí nace el agente
```

El agente remoto usa la misma sección `[agente]` que los locales (nombre, carpeta,
mensajes), resuelta contra `raiz` del remoto en vez de la raíz local. La ruta del hilo
(su vínculo) se traduce: relativa a la raíz local → la misma relativa bajo `raiz` remota.

## Cómo se reconoce

Dos señales, en este orden:

1. **Marca explícita** (fuente de verdad): la opción de ventana tmux `@telar_remoto`, cuyo
   valor es el nombre del remoto (`casa`). La pone telar al crear el hilo. Se guarda
   también en el estado del hilo, para reconstruir la ventana si el tmux local se reinicia.
2. **Detección de respaldo**: si no hay marca y el comando del panel principal
   (`Pane.comando`, de `#{pane_current_command}`) es `mosh-client`, `ssh` o `et`, el hilo
   es remoto con destino desconocido (`remoto = "?"`). Cubre hilos armados a mano. No se
   persiste: un `ssh` pasajero en un hilo local deja de contar cuando termina.

## Modelo y contratos

- `Hilo.remoto: str = ""` — vacío es local; un nombre de `[remotos]` o `"?"`.
- `telar hilos --json` y `telar ficha --json` incluyen `remoto`. Actualizar
  `docs/contratos.md`; es un campo nuevo, no rompe a quien no lo lea.
- Estado persistido del hilo: `remoto` y el nombre de la sesión remota.

## Órdenes

- **Crear**: la orden que hoy crea un hilo (la que usa `irAHilo(nombre, true)` en la
  extensión) acepta `--remoto <nombre>`. Arma la ventana local con
  `<transporte> <destino> -- tmux new -A -s <sesion> -c <ruta-remota> -- <agente>`,
  pone `@telar_remoto` y lo anota en el estado.
  - `<sesion>`: estable ante renombrados, así que sale del **id** del hilo, no de su
    nombre (saneado para tmux: sin `.` ni `:`).
  - `<agente>`: el mismo comando que un hilo local (`claude --session-id <uuid>`, con el
    uuid anotado), envuelto para que la sesión remota no muera si el agente sale:
    `bash -lc '<agente>; exec bash'`.
- **Retomar / reconstruir**: si la ventana local no existe pero el estado dice que el
  hilo es remoto, reabrirla con el mismo comando: `-A` reengancha la sesión viva.
- **Cerrar** (la ✕): mata la ventana local **y** la sesión remota
  (`ssh <destino> tmux kill-session -t <sesion>`). Cerrar la ventana por accidente (sin
  pasar por telar) deja viva la remota, que es lo que se quiere.
- **Archivar**: mata la sesión remota después de anotar el id del agente; `retomar`
  la recrea con `--resume <id>`, igual que los locales.
- **`telar doctor`**: por cada remoto, que el destino responda (`ssh -o BatchMode=yes
  <destino> true`), que haya tmux allá y que el transporte exista en las dos puntas.

## Extensión de VS Code

1. **Ícono**: en la lista de hilos, un hilo con `remoto` no vacío muestra el codicon
   `$(remote)` junto al nombre; tooltip «remoto: casa» (o «conectado a otra máquina»
   si es `"?"`).
2. **Crear hilo: local o remoto.** En `nuevo()`, después de pedir el nombre, si la config
   declara al menos un remoto, un `QuickPick`:
   - «Local — en esta máquina» (primero, por defecto)
   - «Remoto: casa — usuario@servidor (mosh)», uno por remoto declarado

   Sin remotos declarados no se pregunta nada: el flujo queda como hoy. La elección viaja
   como `--remoto <nombre>` a la CLI. La extensión no sabe de mosh ni de ssh; todo pasa
   por la CLI, como el resto.

## Fuera de alcance (siguiente paso)

Atención (`trabajando/espera/termino`) y ficha del agente remoto: hoy las escriben ganchos
que corren donde corre el agente, o sea en el servidor, y el laptop no se entera. La
extensión natural es que telar las lea del estado del servidor por ssh en cada refresco
lento, o que los ganchos remotos las empujen. Se decide después de usar los hilos remotos
unos días.

## Pruebas

- Con el mux falso: crear remoto → ventana con el comando esperado y la marca; reconocer
  por marca; reconocer por comando sin marca; renombrar no cambia la sesión remota;
  cerrar llama al kill remoto; sin `[remotos]`, cero cambios de comportamiento.
- Extensión: el QuickPick aparece solo con remotos declarados.
- Antes de publicar: barrer el diff contra `origin/main` buscando nombres propios y rutas
  de máquina (los ejemplos usan `casa` y `usuario@servidor`).

## Lo que cambió al implementarla

- **El nombre de la sesión remota no sale del id del hilo**: el id local lo pone tmux al
  crear la ventana, y el comando de la ventana hay que armarlo antes. Es `telar-<8 hex>`,
  elegido al crear y guardado en `remotos.json`; igual de estable ante renombrados.
- **Sin `-c <ruta>` en el tmux de allá**: la carpeta va dentro de la línea
  (`cd ~/repo/…`), para que la shell remota expanda `~`.
- **El ícono es `⇄` y no el codicon `$(remote)`**: la lista es un webview y no carga la
  fuente de codicons. El QuickPick de «hilo nuevo» sí usa `$(remote)`.
- **Retomar un remoto no mira si la conversación está en disco**: está en el disco de
  allá. Si el hilo tiene conversación anotada, se retoma con `--resume`; si la sesión
  remota sigue viva, `-A` se engancha y el comando no corre.
- Probado contra un servidor real: crear, reconocer por marca, archivar (mata la sesión
  de allá), retomar (la recrea), cerrar la ventana local a mano y retomar (se engancha a
  la misma sesión, con lo que tenía), y cerrar (termina las dos).

