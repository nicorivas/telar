# Desarrollar telar

Cómo ver un cambio al tiro mientras se trabaja, y cómo llevarlo a las máquinas cuando está listo.

## La página, mientras se trabaja: `scripts/dev.py`

```
python3 scripts/dev.py                 # http://<ip de tailscale>:18780, con la llave de siempre
```

Corre dos cosas hasta ⌃C:

- **esbuild mirando** `pagina/src` y `pagina/media/css` (`npm run navegador:watch`): rehace
  `src/telar/web/app.js` y `marco.css` en menos de un segundo, con el mismo resultado que `npm run navegador`
  (minificado), así que lo que queda en git es lo que se commitea.
- **un `telar serve --web --dev` aparte**, en el puerto 18780 y su propio socket (uno por puerto): el `serve` de
  siempre (el bus, el nodo, la página en 8780) no se toca. Se reinicia solo cuando cambia un `.py` de `src/telar`.

Con `--dev`, la página se recarga sola cuando cambian sus archivos (`/dev/cambios`, server-sent events) y
cuando el servidor vuelve de reiniciarse. Sin `--dev` esa ruta no existe y la página no la busca de nuevo.

Usa la configuración y los datos de verdad: solo cambia el código. Lo que se aprieta ahí (cerrar una tarea,
escribirle a un hilo, un atajo), pasa. Para probar sin tocar nada, una configuración aparte con
`TELAR_CONFIG` y `XDG_CONFIG_HOME` (su propia llave) y sin `[atajos]`.

Para probar la terminal con la latencia de una red lejana sin depender de ella:
`localStorage['telar.latencia'] = '500'` en la consola de la página (y recargar) la simula, la mitad a la ida y
la mitad a la vuelta; ahí mismo, `__eco.estado()` dice si el eco de la terminal que se mira se está mostrando
y la latencia que mide. El eco tiene su prueba, contra un Claude Code falso: `npm run prueba:eco` en `pagina/`,
con un reloj de mentira (`setTimeout` y `performance.now`: el tiempo pasa solo cuando la prueba espera), así que lo que
afirma 20 ms después de teclear no depende de la carga de la máquina.
Las rutas y direcciones que se vuelven enlaces en la terminal, también: `npm run prueba:enlaces`.
Un nombre suelto en la terminal (`original.md` debajo de «En `personal/…/x/`:»): las carpetas que nombra su mensaje, lo
que se le pide al backend (`/api/archivos/resolver`), los candidatos que ofrece el visor y una ruta con tilde,
`npm run prueba:nombre-suelto`; dónde lo busca el backend, `pruebas/test_resolver.py`.
Y en lo que ya se dibujó (una respuesta, la vista de un objeto), que se vuelve a enlazar cuando llegan los tipos de los
módulos: `npm run prueba:enlazar`. El ítem:
`npm run prueba:componentes` (también que la lámina nombre todas sus piezas, y la densidad «auto»; y las iniciativas: su
estado con el vocabulario de `[iniciativas]`, un sinónimo, uno fuera del vocabulario y uno de fuente externa, sin el clic
que lo cambia). Lo que escribe en la ficha, `pruebas/test_iniciativas_estado.py`.
Lo que se lee de un archivo arrastrado a la terminal (sus rutas, cómo se citan): `npm run prueba:arrastre`.
La pestaña «te esperan» (sus grupos, sus filas, el número de la barra, soltar y descartar un retenido desde su fila y descartarlos todos desde su grupo): `npm run prueba:esperas`.
La ventana de contestar lo que te espera (cada clase, lo que se manda y adónde, con un fetch de mentira):
`npm run prueba:contestar`, con el ensayo sin sus pausas (`hacerDeEnsayo({ pausa: 0 })`; en la página son de 300 a 900 ms,
para que se vea lo que está en curso); y en la página, con datos inventados y sin tocar nada,
`window.telar.ensayoContestar('decide')` en la consola (también `tarea`, `retenido`, `en-vivo`, `permiso`, y las de la
ficha, `decision`, `aprobar` y `sin-contexto`, que leen su tarea de mentira al abrirse, con la barra de la tarea en el
encabezado: su fecha abre la lista de siempre y queda en la tarea de mentira, y lo demás dice qué haría; con `true` de
segundo argumento, el primer envío responde que cambió mientras se miraba).
El orden de las pestañas del dashboard (lo que `[dashboard] orden` no nombra, dónde va): `npm run prueba:pestanas`.
Quién se ve en la barra de hilos (`vistas/hilos-familia.ts`, y la barra de verdad dibujada en Node con hilos de mentira):
que el hilo que se mira suba con su familia (sus padres y sus descendientes, de aquí y de otras máquinas; el agente de un
hijo suyo) aunque el mundo o el modo lo dejen afuera, que en «de personal» cada hijo vaya bajo su padre, y que un agente
sin hilo abierto vaya por el mundo de su carpeta; y que el único buscador, el de HILOS, filtre también el archivo (se
abre con solo lo que calza y vuelve a como estaba al borrar): `npm run prueba:barra`.
Qué agentes residentes se ven en un modo (`agentes`: vacío, todos; «-», ninguno) y lo que deja un clic en la grilla de
⚙ modos; y qué pestañas ve (`filas`, `web/modos-pestanas.ts`): lo que deja un clic en su fila de ⚙ modos (dónde entra la
que se agrega, cuándo vuelve a lo heredado, nunca ninguna) y las que quedan en un mundo, la unión de las de sus modos:
`npm run prueba:modos`. Que la fila del modo puesto cambie la barra al tiro y mande solo esa línea, en
`npm run prueba:modos-mundo`; lo que la API escribe y lo que niega (una pestaña que no hay), `pruebas/test_modos.py`.
Los modos de cada mundo (`[mundos.<n>] modos`): cuáles tiene el puesto (con ambos, la unión), a cuál se entra y a cuál se
vuelve, que las teclas no pongan otros, la banda solo con los suyos y lo que deja un clic en la fila «modos» de
⚙ mundos, con un reloj y una API de mentira: `npm run prueba:modos-mundo`. Lo que escribe en el archivo,
`pruebas/test_mundos_config.py`.
Los mundos vistos desde la configuración (`web/mundos-agentes.ts`): qué agentes salen con un mundo elegido, por qué un
agente es de su mundo y lo que ⚙ mundos revisa antes de escribir (un área, una ruta o una etiqueta de otro mundo, un
horario que no se entiende, el nombre de uno nuevo): `npm run prueba:mundos`. Lo que escribe en el archivo
(`PATCH /mundos/<n>` y los demás) lo prueba `pruebas/test_mundos_config.py`.
El horario de los mundos en ⚙ mundos (componentes/horario-editor.ts): cómo se escribe un tramo (y que se lea igual), la
semana partida en pedazos, los choques y los huecos, y en la sección, con un DOM, un reloj y una API de mentira, que un clic
en un día o una hora vaya al borrador y se vea en la semana, que un choque se diga y no se guarde, que guardar mande solo
el horario y la banda cambie al tiro si cambia el que rige, y que un 422 deje el borrador: `npm run prueba:horario`. Del
lado de telar (el archivo de la raíz, `.telar/mundos.toml`: precedencia, escritura, el choque como 422, la migración con
respaldo, el commit de solo ese archivo y que otra máquina rija igual), `pruebas/test_mundos_raiz.py`.
La ventana de mundos (componentes/mundos-ventana.ts, web/mundos-ventana.ts) y su arte (componentes/arte.ts; lo vivo,
web/arte-vivo.ts): el contrato del arte y cada uno de fábrica (el lienzo exacto, el mismo cuadro en el mismo instante, más
rápido encima), un arte escrito como archivo, los de la raíz que tapan a uno de fábrica, qué arte lleva cada mundo, lo que
dicen las tarjetas, las teclas (flechas, números, ⏎, h, e, ⎋, ⌘M que abre y cierra), elegir y volver al horario, «reducir
movimiento» sin ningún cuadro pedido, ningún `requestAnimationFrame` con la ventana cerrada o la pestaña escondida, y un arte
que llega con la ventana abierta, con un DOM y un `requestAnimationFrame` de mentira: `npm run prueba:mundos-ventana`. Lo que
entrega telar (`[mundos.<n>] arte`, `GET /arte`), `pruebas/test_arte.py`. En la página, `window.telar.mundos()` la abre (o la
cierra) como ⌘M; cómo hacer un arte, [arte.md](arte.md).
Que una tarea marcada hecha no vuelva (el día que se ve y sus relecturas, `vistas/dashboard/dia.ts`): lo leído antes de
marcarla no la trae, la relectura de después no se pierde tras una que iba desde antes, y si el cierre falla queda y se
dice por qué, con un fetch de mentira que la prueba contesta cuando quiere: `npm run prueba:dia`.
Las confirmaciones (los botones de `componentes/boton.ts`, «la tecla en el pie», y sus teclas, `web/botonera.ts`): que lo
que destruye vaya en el de peligro con ⌘⌫ y abra con el foco en «cancelar», que ⏎ haga el botón que tiene el foco y la tecla
de cada celda la suya, que una sostenida no haga nada, que cada confirmación de la página que dice un verbo que destruye lo
pida (`{ destruye: true }` en `ui.aviso`) y esté en el catastro del catálogo (`CONFIRMACIONES`), y las que no pasan por
`preguntar` (contestar, escribir, la instrucción, la mudanza, soltar en la terminal): `npm run prueba:confirmar`. En la página,
sin tocar nada, `window.telar.ensayoConfirmar('borrar')` en la consola (también `archivar`, `descartar`, `traer`, con
contenido largo, y `permiso`, con tres botones) abre una de verdad y dice qué se apretó; `ensayoMudanza('servidor',
'pregunta')`, la mudanza en su pregunta.
Lo que el lienzo de un módulo pide y la página atiende sola, sin el servidor ni permiso (`menu`, `abrir`,
`instruccion`): `npm run prueba:lienzo`.
La franja de avisos (arriba de la barra de hilos: el estado del sistema y de los hilos; el componente, `componentes/franja.ts`;
lo que se avisa, `web/avisos.ts`; lo que mira la conexión, la sesión y las otras máquinas, `web/vigia.ts`): su orden, lo que
dice tranquila, el «+N», la lista, el punto, lo que se va solo, lo que quedó detenido sin que nada lo diga (un mensaje
retenido o un hilo en la pregunta de confiar, `web/detenidos.ts`) y lo que dice un archivo de aviso (`[avisos]`, y lo visto,
`web/avisos-archivos.ts`), `npm run prueba:avisos`; y en la página, sin que nada falle,
`window.telar.ensayoAvisos('varios')` en la consola (también `sin-conexion`, `fuente` y `ninguno`, que los quita; con `true` de
segundo argumento, la lista abierta).
La línea del pulso, debajo de la franja (la última pasada sin ver de un resultado con `pasadas`; el componente,
`componentes/pulso.ts`; lo que lee y marca visto, `web/pulso.ts`): lo que dice la línea, lo que lleva la ventana y lo que
pide a la API, con un fetch de mentira (lo que cambió y su causa, la pasada sin cambios), y lo mismo con cada mundo puesto
(trabajo, personal, ambos: lo que se ve, las cuentas, el resumen de las de antes y lo visto por mundo),
`npm run prueba:pulso`; y en la página, con pasadas de mentira de los dos mundos, vistas con el mundo puesto, y sin marcar
nada, `window.telar.ensayoPulso()` en la consola (`false`, solo la línea). El mundo de cada cosa y lo visto por mundo, del lado de telar: `pruebas/test_pasadas.py`.
El orden de una pestaña de lectura (lo de la persona, la prioridad, lo más nuevo arriba; sin tope; sin esos campos, el
del proveedor) y cómo se ve la prioridad en su fila y en su ficha: `npm run prueba:leer`. Lo que lee telar de cada fila
(`prioridad`, `de`, `fecha`, también dentro de `campos`): `pruebas/test_tareas.py` (`DeYFecha`) y
`pruebas/test_ordenes.py` (`VistaDeLectura`).
Los hilos dormidos (telar.dormir) en la página (`web/dormidos.ts`): qué hilo es lo que se muestra, cuándo uno que se
abre está dormido (aquí o en la foto de otra máquina), que lo que se muestra se diga al cambiar y cada 30 s, y que abrir
uno dormido pida despertarlo una vez, con su máquina, con un reloj y una API de mentira: `npm run prueba:dormidos`; su
aro tenue en HILOS, AGENTES y los de otra máquina, en `npm run prueba:barra`. Del lado de telar (lo que se lee de la
pantalla, cada regla que lo protege, dormir y despertar con un multiplexor falso y en un tmux de verdad con un agente de
mentira, el ⏎ que lo despierta): `pruebas/test_dormir.py`. En la máquina, sin dormir a nadie, `telar hilo dormir --seco`.
Una máquina fuera de línea en la página (`web/alcance.ts`): desde cuándo en palabras, la nota de la franja con sus hilos
inalcanzables y su cola, lo que se hizo de la cola al volver, la ayuda de un hilo inalcanzable y el cuadro de su terminal
y de su conversación con la banda de botones de la casa, `npm run prueba:alcance`; sus filas en la barra (el aro de «sin
noticias», ni dormido ni trabajando), en `npm run prueba:barra`, y que abrir uno que dormía allá no lo deje en cola, en
`npm run prueba:dormidos`. Del lado de telar, con dos nodos de mentira (en línea, fuera de línea, con un telar de antes):
despertar por el bus y a la cola, la cola al volver, lo que hace el dueño, lo que dicen `telar hilo despertar`, `leer`,
`telar mensaje` y `telar hilos --red`, y `/pty` cerrando con desde cuándo: `pruebas/test_alcance.py`.
El ancho de la barra de hilos y de la ficha de un hilo, arrastrando su línea (`web/anchos.ts`): la franja de agarre, el
arrastre en vivo con pointer events, los topes (el centro nunca con menos de 480 px), el doble clic que vuelve al de
fábrica, lo recordado por pantalla (y sin almacén), plegada y en el teléfono, y que la terminal reciba un solo ajuste al
soltar; y el borde de la terminal (su franja según la posición, el arrastre de columna en columna, 80 columnas a todo el
centro, el doble clic que vuelve a `[terminal] columnas`, que ⚙ terminal olvide lo arrastrado y un solo resize a tmux),
con un DOM que hace la disposición de la página: `npm run prueba:anchos`.
Abrir un hilo con una lectura (el ícono de la instrucción en la barra de su ficha, con su tono y su ayuda, y lo que manda
la ventana: un hilo nuevo llamado como ella, con lo que la ficha tiene como contexto libre, sin fila ni dirección), con
un DOM y un fetch de mentira: `npm run prueba:leer-hilo`.

Las pruebas de Python se corren como el CI: con telar instalado con `pip install -e '.[serve,bus,pruebas]'`
(sin los extras, las de la API y el bus se saltan), `python -m unittest discover -s pruebas` (escritas como
`unittest`, no como funciones sueltas de pytest: el CI no las vería). El mod de Claude Code tiene las
suyas: `claude plugin test` en `src/telar/mod/`, y `claude plugin validate --strict src/telar/mod`.

Mientras se trabaja, con pytest: `PYTHONPATH=src python3 -m pytest -q pruebas`. La suite completa (la carpeta
`pruebas`, o pytest sin nada desde la raíz) corre en 4 procesos con `--dist loadscope` si está pytest-xdist (viene en el
extra `pruebas`; `pruebas/conftest.py`): 25 s en vez de 74 en un MacBook Air M2. `loadscope` deja cada archivo o clase
entero en un proceso: las de tmux de verdad (`test_mux_tmux_real`) fallan repartidas de a una. `-n` manda (`-n 0`, en
uno); un archivo suelto corre en uno, y sin pytest-xdist todo corre en uno (el encabezado de pytest lo dice). Como mucho
dos suites completas a la vez en la máquina, entre todos los hilos y las cuentas: la tercera espera su turno (`flock`
sobre `/tmp/telar-pruebas.turno.0` y `.1`, `comun.turno`) y dice que espera y quiénes corren (su pid, su hilo y su
carpeta); entra sola cuando una termina, aunque haya muerto. Un archivo suelto no pide turno.

Las pruebas no tocan lo vivo de quien las corre. Un hilo las corre desde su panel, con `TMUX`, `TMUX_PANE` y
`TELAR_HILO` de verdad y con la configuración y el estado de telar en su lugar de siempre: así, un `tmux kill-server`
de una prueba mató el tmux de la persona con todos sus hilos, y una prueba le cerró la ventana a un hijo (18-nov-2026).
Antes de importar una sola prueba (`pruebas/conftest.py` con pytest; con `unittest`, la primera que importa `comun`),
`comun.aislar_sesion` saca del proceso esas tres, las demás `TELAR_*` (menos `TELAR_NATS_SERVER`, que elige las del
bus), las de la sesión de Claude Code y de otro multiplexor (`telar.entorno`), `CLAUDE_CONFIG_DIR`, `HISTFILE` y
`ZDOTDIR`; y deja `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` y `TMUX_TMPDIR` en una
carpeta temporal de la sesión, que se borra al salir junto con el servidor de tmux que alguna prueba haya dejado ahí.
El hogar de la sesión lleva solo el nombre y el correo de git de quien las corre. Sin esto, la suite escribía en el
`commits.log` y el `concesiones.json` de verdad, en la caché de gws y en la historia de bash de la persona. Es una red,
no un permiso: la prueba que usa tmux sigue en su servidor propio (`comun.socket_tmux`) y lo mata con
`comun.matar_tmux`, con `-S`; nunca un `kill-server` a secas. Cada archivo de pruebas importa `comun`, para que correr
uno solo con `unittest` también quede aislado (lo revisa `pruebas/test_sesion_aislada.py`, con lo que ve una prueba
adentro). Que la red aguante se prueba con `python3 scripts/senuelo.py` (o `--unittest`, o con los archivos que se
quieran): corre la suite con `TMUX`, `TMUX_TMPDIR`, `TELAR_HILO` y las carpetas de la persona apuntando a señuelos, y
falla si alguno cambió. Las de la página (`npm run prueba:*`) no lanzan procesos ni leen el entorno: no la necesitan.

Necesita telar instalado editable (`uv tool install --editable '.[serve,bus]'`): así `telar` corre el
código del repositorio. Los tipos de la página: `npm run tipos` en `pagina/`. Lo que se commitea en
`src/telar/web/` es lo que sale de `npm run navegador`, y el CI lo comprueba.

## Comprobar en el navegador: `scripts/medir.py`

Para ver si un cambio de la página quedó como se quería (el alto de una barra, dónde cae un botón, cómo se ve en el
teléfono) sin manejar el navegador a mano. Levanta la página de esta copia con `scripts/dev.py` en un puerto libre
propio, entra con la llave sin imprimirla, abre una sola sesión de agent-browser con nombre propio, recorre las
pantallas pedidas y devuelve, de cada una, lo que se pidió. Al terminar, pase lo que pase (un error, ⌃C, un tope),
cierra el navegador y apaga la página; lo que dejó una corrida que murió sin poder limpiar (un `kill -9`), lo limpia
la siguiente (su archivo de estado, en `$TMPDIR/telar-medir-<uid>/`).

```
python3 scripts/medir.py todas -s .pantalla-barra -s .franja          # el rectángulo de cada una, en todas
python3 scripts/medir.py calendario proyectos -s .pantalla-barra -e height,padding-top
python3 scripts/medir.py config:modos hilo:Faro/lectura --captura      # y una PNG de cada pantalla
python3 scripts/medir.py todas -s .franja --telefono --json            # como un teléfono, en JSON
python3 scripts/medir.py tactica --js "window.telar.ensayoAvisos('varios')" -s .franja --captura
python3 scripts/medir.py --lista                                        # las pantallas que la página tiene hoy
```

Las pantallas van en orden y el estado pasa de una a la otra (un modo puesto sigue puesto). Se nombran sin que
importen tildes ni mayúsculas:

- **un modo**: `tactica`, `estrategia`, `foco`, `todo` (o `modo:<clave>`): el clic en la banda de modos (estrategia
  abre en proyectos, la primera de sus filas: no tiene pantalla propia);
- **una pestaña del dashboard**, por su nombre, su clave o su acción: `calendario`, `te esperan`, `tareas`, `correo`,
  `bloque:correo` (o `pestana:<x>`). Si el modo puesto no la muestra, pone «todo» primero. `pestanas`: todas las que
  tiene el dashboard ese día (las de los módulos y los proveedores también);
- **la configuración**: `config`, o `config:<sección>` (`config:modos`, `config:mundos`…);
- **un hilo**: `hilo:<nombre>`, en su conversación, o `hilo:<nombre>/lectura|conv|term`. La terminal solo si se pide:
  se engancha a la ventana de tmux del hilo y le da su tamaño (`window-size latest`), así que el hilo de verdad queda
  del ancho del navegador hasta que alguien lo mire de nuevo. Para abrir la conversación en un laptop sin montar la
  terminal, medir angosta la ventana un momento (angosta, la página abre la conversación) y la vuelve al ancho;
- **un archivo**: `arch:<ruta>`; **un objeto**: `obj:<dirección>` (`obj:tarea:T84`); `dashboard`;
- **`todas`**: los cuatro modos, cada pestaña (en el modo todo), config, el README en el visor, la conversación del hilo
  que lo corre (`TELAR_HILO`, si hay) y foco al final (foco muestra lo último que se miró).

Lo que mide: con `-s <css>` (se repite), el rectángulo (`getBoundingClientRect`) del primer elemento que calza y se
ve (`--todos`: hasta 20), cuántos calzan y si se ve; con `-e height,padding-top,--pantalla-barra-alto` (una variable
sola, con `=`: `-e=--x`), sus estilos calculados; con `--captura [carpeta]`, una PNG de la ventana por pantalla; con
`--js <código>`, lo corre en cada pantalla antes de medir y devuelve su resultado (si da una promesa, la espera sin
colgarse); con `--esperar <css>`, espera además a que eso aparezca. La ventana: 1440×900 de fábrica (el laptop),
`--ventana 1024x700`, o `--telefono` (un iPhone 14: angosto y táctil). La salida es texto corto; con `--json`, cada
pantalla con `ok`, `error`, `segundos`, `donde` (modo, pestaña, vista), `medidas`, `espera` y `captura`.

```
modo:tactica  0.7 s  · tactica · táctica
  .franja          0,54.7 315.8×26.3
  .pantalla-barra  316.8,54.7 1123.2×26.3
arch:/…/README.md  0.5 s  · todo · arch:/…/README.md
  .pantalla-barra  0,0 0×0  (oculto)
http://100.x.y.z:18857 · 1440×900 · 19 pantallas en 38.9 s
```

La espera es la justa, nunca un `sleep`: después de cada clic espera a que la pantalla esté (el modo puesto en `body`,
la fila de la pestaña activa, la vista del hilo a la vista) y a que la página se calme (150 ms sin cambios en el DOM y
sin `fetch` en vuelo). Lo que nunca se calma (una terminal, una lista que se relee) se mide a los 2,5 s de estar, y la
línea dice «sin calma». Cada paso tiene su tope (`--paso`, 10 s) y la corrida el suyo (`--total`, 90 s); una pantalla
que no llega se dice y se sigue con la siguiente. Sale con 0 si todas llegaron, 1 si alguna no, 3 si la corrida no
pudo (la página no levantó, el navegador no contestó, el tope total). `todas` con dos selectores tarda unos 40 s (19
pantallas) en un MacBook Air M2: casi todo es la página leyendo sus datos. Con `--url` mide una página que ya corre, sin
levantar otra.

Sin red ni navegador, `pruebas/test_medir.py` prueba sus opciones, los nombres, que lo que da por sabido de la página
siga ahí (los modos, las pestañas de fábrica, las vistas de un hilo y los atributos que aprieta: si cambian, falla ahí
antes que en el ensayo) y que limpie siempre, con un agent-browser y un `dev.py` de mentira que fallan y se cuelgan.

### Navegar la página por JS

Lo que medir usa, para quien maneje la página con agent-browser o desde la consola:

- **`window.telar.mostrar(que)`** (`navegador/app.ts`) pone a la derecha: `'dashboard'`; `'config'` (el ⚙); un hilo de
  aquí por su nombre (`'Faro'`); `'rem:<máquina>:<hilo>'`, uno de otra; `'doc:<hilo>'`, su carpeta; `'arch:<ruta>'`, un
  archivo; `'obj:<dirección>'`, un objeto en su vista de siempre (`obj:tarea:T84` abre su ficha, `obj:pestana:calendario`
  el dashboard en esa pestaña, `obj:hilo:Faro` el hilo); `'compartir'`. Es síncrona; lo que carga después, carga solo.
  En un laptop, un hilo abre su terminal (ver arriba); `?abrir=<dirección>` en la dirección de la página hace lo mismo
  al cargar.
- **`window.telar.ponerMundo(clave)`** pone ese mundo a mano (`''`, ambos), como la ventana de mundos: para ver qué
  deja ver cada uno (la barra, ⌘K, los agentes) sin esperar a su horario.
- **`window.telar.mundos()`** abre la ventana de mundos (o la cierra, si está abierta), como ⌘M; su promesa se cumple al
  cerrarla, así que desde agent-browser va con `void`. Encima de una tarjeta: `.mt-tarjeta[data-mundo="personal"]` y el
  `hover` de agent-browser (el mouse de verdad: :hover, el foco que lo sigue, el arte que se acelera).
- **Las vistas de un hilo**: con el hilo a la vista, `#acciones [data-accion="vista"][data-valor="lectura"]` (o `term`,
  `conv`) y `.click()`. La que se ve es la sección `#vistas > [data-p="<vista>:<hilo>"]` sin `hidden`.
- **Los modos**: `#modos-fila [data-accion="modos-modo"][data-id="foco"]` y `.click()` (`tactica`, `estrategia`, `foco`,
  `todo`); el puesto lleva `.si`, y `document.body.dataset.modo` dice su base. Poner un modo lleva a su vista; foco, al
  último hilo que se miró.
- **Las pestañas**: son las filas `[data-accion="dash"]` del grupo DASHBOARD de la barra; su `data-id` es
  `JSON.stringify([acción, valor])` (`["calendario",""]`, `["bloque","correo"]`, `["foco",""]` es «tareas») y su `title`
  empieza por el nombre. Un `.click()` la abre y la activa lleva `.activa`. Solo están las del modo puesto: el modo todo
  las muestra todas.
- **Las secciones de config**: `.config-op[data-valor="modos"]` y `.click()`; la que se ve lleva `.activa`.
- **Los ensayos** (`window.telar.ensayoAvisos`, `ensayoPulso`, `ensayoContestar`, `ensayoTactica`, `ensayoMudanza`,
  `ensayoConfirmar`):
  muestran datos de mentira sin tocar nada; están arriba, con lo que prueba cada uno.

Dos reglas. En el dashboard **nunca se teclea**: sus letras son atajos que encargan trabajo de verdad (una pasada,
un correo, cerrar una tarea); solo clics y JS. Y un `agent-browser eval` **nunca devuelve una promesa**: si no se
cumple, agent-browser la espera hasta su corte (minutos, no el tope de `wait`); lo async se lanza, deja su resultado en
`window` y se lee con un `wait --fn` y otro `eval` (es lo que hace `--js`).

## Los componentes, los temas y las densidades: `/componentes`

`http://<ip>:18780/componentes` (también en la página de siempre, sin `--dev`) es el catálogo: cada componente
de la página en todos sus estados, con cada tema y cada densidad al lado del otro. Sin datos de nadie, así que
nada de lo que se aprieta ahí pasa: dice qué haría. A la izquierda va la lista de componentes en orden jerárquico
(fundamentos, piezas, compuestos, secciones, contenedores; `PAGINAS` en `componentes/catalogo.ts`) y cada uno tiene su
página, que la dirección elige (`/componentes#item`); los que faltan por hacer están en la lista, apagados, con su paso
de la propuesta. Cada componente tiene las mismas pestañas: **estados** (él, en cada estado) y **anatomía** (sus partes
nombradas y para qué está cada una), con su dirección (`/componentes#item/anatomia`); la que falta sale apagada. Las
páginas que hay:

- **gramática visual** (fundamentos; `componentes/gramatica.ts`): de qué está hecho el diseño y qué quiere decir cada
  forma. Cuatro clases de signos, cada una con un trabajo: el círculo dice cómo está algo, el rectángulo dónde va, el
  ícono de la letra qué se le hace o qué clase de cosa es, el texto su nombre. Lo redondo y lo recto se describen por
  sus variables, cada una con una sola pregunta (llenado: ¿cuánto hay?; tamaño: ¿qué rango tiene?; relación: ¿con qué
  se relaciona?; movimiento: ¿está cambiando?; color: ¿de qué tipo es?; tono: ¿sigue vigente?; y en lo recto,
  superficie, línea y el lugar del círculo), con valores de un solo concepto cada uno (el aro es «falta»: te espera,
  por hacer, pausado). Sus páginas: **lo redondo**, **lo recto** (con «cómo se parte» un rectángulo en columnas,
  secciones, bandas, grupos, filas y ranuras, cada una con una sola marca) y **derivadas** (lo que telar dice con eso y qué
  usaba antes; las que están en uso salen de `componentes/senales.ts`, de donde las piden la barra, el ítem y el
  dashboard). La prueba revisa que cada variable tenga su pregunta, que ningún concepto se repita, que cada figura del
  círculo tenga el suyo, que cada derivada apunte a conceptos que existen y que nada pida un cuarto tamaño.
- **ítem** (`pagina/src/componentes/item.ts`, `media/css/item.css`): en «estados», la fila de una lista en tres
  secciones (inicio con ranuras de íconos, texto con prefijo, título y sufijo, y fin con aviso, meta y acciones), un
  renglón por estado (trabajando, te espera, activo, con el mouse encima, de otra máquina, hijo, cerrándose…); un
  clic en el nombre de un estado muestra sus props, y «bordes», arriba, dibuja el de cada sección. En «anatomía», la
  lámina: el ítem grande, con un corchete sobre cada sección y una guía desde cada pieza hasta su nombre, la prop de
  `item()` que la pone y para qué está; debajo, la pregunta que responde cada sección (inicio: ¿cómo está y dónde?;
  texto: ¿qué es?; fin: ¿qué tiene y qué le hago?). Lo que dice está en `componentes/anatomia.ts`, y la prueba falla
  si el ítem gana una pieza que la lámina no nombra.
- **círculo** (`componentes/circulo.ts`, `media/css/circulo.css`): la firma de los estados. Sus tamaños (punto,
  chico, grande) y llenados (aro, ¼, ½, ¾, lleno), al lado de los íconos de prioridad que reemplaza o acompaña, los
  tres movimientos de lo que está en curso y las figuras (varios círculos compuestos; lo que dicen, en la gramática).
- **barra de hilos**: la de verdad (`vistas/hilos.ts`), armada con hilos de mentira (`componentes/muestras.ts`).
- **franja de avisos** (`componentes/franja.ts`, `media/css/franja.css`; lo del catálogo en `componentes/catalogo-avisos.ts` y
  sus avisos de mentira en `componentes/muestras-avisos.ts`): la fila de arriba de la barra de hilos, del alto de la barra de
  una pantalla (sus líneas de abajo calzan), con el estado del sistema y de los hilos: sin conexión (rojo, y calla lo que
  necesita a telar), una fuente que falla, una terminal que se cortó, una página o una versión nueva, una máquina sin
  noticias, lo que dice un archivo de aviso (`[avisos]`: en cuidado, o en rojo si dice `mal`, el nivel «problema»). No el
  trabajo: lo que espera a la persona tiene su lugar, salvo lo que sin aviso se queda callado (un mensaje retenido, un hilo
  detenido en la pregunta de confiar en una carpeta). Tranquila dice cuándo se leyó la lista («al día · 18:42»); con avisos, el más grave en
  su color y con su ícono, y «+N»; un clic abre la lista, con qué hacer y adónde lleva cada uno. Con la barra plegada, solo
  el ícono; donde no hay barra a la vista (el teléfono viendo un hilo, foco), un punto en el color del aviso dentro del botón
  que la muestra. En «estados», cada escena en cada tema; en «en la página», `#avisos/ver/<escena>[/abierta|/plegada|/hilo]`
  la muestra como la página entera, al ancho de la ventana (así se sacan las capturas); en «de dónde sale», quién pone cada
  aviso, cuándo se va y dónde se decía antes.
- **el día en una línea** (`componentes/jornada.ts`, `media/css/jornada.css`): cuánto libre queda hasta la próxima reunión y
  qué viene después, con la jornada en una barra; en «estados», un día de mentira en cada momento y ancho, y «en la
  cabecera», como se ve arriba de la página en el laptop y en el teléfono. En la página lo pone `web/jornada.ts`.
- **botones** (`componentes/boton.ts`, `media/css/boton.css`; sus teclas en `web/botonera.ts`; lo del catálogo en
  `componentes/catalogo-botones.ts`): «la tecla en el pie», la forma elegida el 22-nov-2026 (docs/propuestas/componentes.md,
  «Los botones»), en las ventanas de confirmar que hay (lo que destruye, con el mouse encima, lo que no, varias acciones,
  contenido largo); en «estados», normal, al pasar, con el foco, apagado, mientras se hace y sin tecla; en «el foco y ⏎», lo
  que hace cada tecla y dónde parte el foco; en «las que destruyen», cada confirmación de la página con su clase y por qué, y
  las tres formas descartadas. «probar» abre una de verdad (`preguntar`) con el tema de la primera columna, y dice qué se
  apretó. Sus pruebas, en `npm run prueba:componentes` y `npm run prueba:confirmar`.
- **tokens**: los colores de cada tema, por lo que significan, y las medidas de cada densidad, con el valor que
  resuelve cada columna.
- **táctica (prototipo)** (`componentes/tactica.ts`, `media/css/tactica.css`, sus días de mentira en
  `componentes/muestras-tactica.ts`, armados por la vista de verdad, `vistas/dashboard/tactica.ts`): la vista de partida
  del orden por modos. En la página es la pestaña «táctica»; ahí, `window.telar.ensayoTactica('<estado>')` en la consola
  la muestra con el mismo día de mentira, sin contestar nada (↻ vuelve a lo de verdad).
  En «disposiciones», las tres maneras de repartir Ahora, las vías y Hacer, en un laptop y un teléfono; en «estados»,
  un día inventado en cada momento (en una reunión, sin nada declarado, libre, en un bloque del plan, nada por
  decidir, muchas cuentas, sin plan); en «la urgencia», el orden que da `vistas/dashboard/urgencia.ts` a cada espera,
  con lo que declaran sus agentes (la vía, el peso, quién espera, la fecha dura, las opciones, lo hecho: `CAMPOS`) y
  sus señales. Un clic en una fila de una vía abre «Contestar» de verdad, en ensayo (lo de bajo una fila, una opción o
  enviar, llega elegido); uno en la cabecera de una cuenta la despliega. Las teclas 1 a 4 recorren decidir, aprobar,
  cerrar y lo que pide hacer. `#tactica/ver/<disposición>/<estado>` la muestra como la página entera (la cabecera con
  su línea del día y, en un laptop, la barra de hilos), al ancho de la ventana: así se sacan las capturas.
  La urgencia tiene su prueba en `npm run prueba:componentes`. Al final de las vías, las contestadas que esperan al
  agente (`telar esperas`, `contestadas`), con la próxima pasada (`telar periodicos`: los de `pulso`, el que corre antes, o `avanzar` si no hay) y «revisar
  ya»: en el estado «en una reunión» (el del ensayo), tres de mentira, una ya encargada; en un ensayo, «revisar ya»
  dice qué haría y no manda nada. Quién entra y sale, en `pruebas/test_esperas.py` (`LasContestadas`); la fila, el
  grupo y la pasada, en `npm run prueba:componentes`.
- **modos y mundos (prototipo)** (`componentes/modos-mundos.ts`, `componentes/todo.ts`, `media/css/modos.css`; lo del
  catálogo en `componentes/catalogo-modos.ts` y sus datos de mentira en `componentes/muestras-modos.ts`): los dos ejes de la
  página, para elegir antes de llevarlos a ella. En «dónde se cambian», las tres variantes (la cabecera, una banda propia,
  la barra de hilos) en un laptop y un teléfono; la elegida, la banda, es la de la página (y con ella se dibujan las demás
  secciones); «qué cambia cada modo», una tabla; «todo», el buscador sobre todo junto
  (sin buscar, buscando y una fuente entera); «el mundo», sus escenas (por horario, fuera de él, a mano, ambos, sin
  `[mundos]`), su menú y su horario; «los modos de hoy», cómo se pasa de `[modos]`. `#modos-mundos/ver/<variante>/<modo>/<escena>[/buscar|/tareas|/lista]`
  la muestra como la página entera, con la barra de verdad (las filas de DASHBOARD del modo, los hilos del mundo), al
  ancho de la ventana: ahí un clic en un modo o en el mundo los cambia, y también ⌥⇧1–4, ⌥⇧F, ⌥⇧M y ⌥⇧0. El horario de
  un mundo tiene su prueba en `npm run prueba:componentes`.
- **ventana de mundos** (`componentes/mundos-ventana.ts`, `media/css/mundos.css`; lo del catálogo en
  `componentes/catalogo-mundos.ts`): la ventana para cambiar de mundo, una tarjeta por mundo con su arte animado. En
  «estados», quieta, con el mouse encima de una, ambos a mano y con más mundos, en cada tema (las tarjetas animadas;
  «probar» la abre de verdad con mundos de mentira y dice qué haría); en «los artes», cada arte registrado (los de fábrica
  y los de la raíz) en su tarjeta, animado; en «probar uno», un arte escrito como un archivo de la raíz y al lado su
  tarjeta, animada mientras se escribe ([arte.md](arte.md)).

Arriba se eligen los temas y las densidades que se comparan (una columna por cada par) y el ancho: el de la barra
en un computador, o el de un teléfono (sin mouse: el ⋯ se ve siempre). Con `scripts/dev.py`, cambiar un token o una
regla y guardar recarga el catálogo.

Los tokens van en tres capas (`media/css/tokens.css`): los primitivos de un tema (fondo, texto, tintas), los
semánticos (para qué es cada color: `--texto-tenue`, `--acento`, `--estado-espera`…) y los de cada componente
(`--item-…`). Un tema (`media/css/temas.css`) dice sus primitivos y, si quiere, cualquier otro: «riso» marca el ítem
activo con una raya en vez de un fondo, «papel» deja las cabeceras en minúsculas. Lo nuevo usa los semánticos, no
las tintas. Un tema nuevo: su bloque en `temas.css`, su nombre en `componentes/temas.ts` y en `telar.modos.TEMAS`
(una prueba revisa que estén los tres). Se elige con el ajuste `tema` de un modo (⚙ modos). Cada máquina puede cambiar
los colores principales de un tema (⚙ temas, `[temas.<tema>]`: los fondos y las líneas, `FONDOS`, y las tintas de letra,
`EDITABLES`): `web/colores.ts` los pone con una hoja propia (`[data-tema="x"]:not([data-fabrica])`, más específica que la
de `temas.css`), y /componentes muestra los de fábrica como vienen. Y puede tener temas propios (`[temas.<nombre>] base`):
la misma hoja lleva las reglas de su base copiadas de las hojas de la página con su nombre (`temas.reglasDe`), así que uno
propio es su base entera, sin repetir nada de `temas.css`; la página los conoce al llegar de la configuración
(`temas.registrar`) y valen donde vale uno de fábrica (`temas.todos`, `existe`, `queRige`). La paleta, los avisos (de una
letra y de un fondo), la hoja, el nombre de uno nuevo, la copia de su base, la vista previa, los selectores que lo llevan
y lo que hace la página al crearlo, probarlo, volverlo a su base y borrarlo tienen su prueba en `npm run prueba:temas`; la
configuración y la API (crear, cambiar, volver a fábrica, borrar, un nombre que no sirve, uno en uso), en
`pruebas/test_temas.py`.

La densidad es aparte del tema: cuánto aire lleva cada fila, solo medidas, así que cualquier tema va con cualquier
densidad. El alto de una fila es su interlineado (`--item-alto`): todo queda al medio y una acción se aprieta en el
alto entero de la fila. «compacta» (la de fábrica, en `tokens.css`) es una línea por fila, como la terminal;
«cómoda» y «amplia» están en `media/css/densidades.css`, y amplia es para el dedo (filas de unos 40px, acciones más
anchas). El ajuste `densidad` de un modo elige una, o «auto»: amplia en una pantalla táctil y compacta con mouse
(`componentes/densidades.ts`). Una nueva: su bloque en `densidades.css`, su nombre en `componentes/densidades.ts` y
en `telar.modos.DENSIDADES`.

Lo que está en curso (un hilo que se cierra o viaja, una tarea que se marca, una versión que se instala, un mensaje que
se envía, un periódico que corre) se dice con un círculo que se mueve en su lugar, de a cuartos, y nada más se mueve:
ni el texto, ni su ancho, ni su color. Tres movimientos, por cómo termina: se vacía lo que se va (cerrar, archivar,
descartar), se llena lo que se completa o llega (marcar hecha, instalar) y gira, a medias, lo que va en camino (viajar
a otra máquina, enviar, una acción haciéndose). Al lado, si hace falta, la palabra quieta («cerrando», «→ servidor»).
Con «reducir movimiento», el círculo queda a medio llenar. Un componente nuevo:
su función en `pagina/src/componentes/`, su CSS en `media/css/` (en la capa base de `scripts/navegador.mjs`), sus
estados en `muestras.ts` y su sección en `catalogo.ts`.

## Lo nuevo dice qué reemplaza

Cada mecanismo nuevo (una orden, un modo, una pestaña, un archivo de estado) dice en su propuesta o en su commit qué
reemplaza, o por qué no reemplaza nada; lo reemplazado se retira con un alias que avisa, no se deja al lado.

## Varias funcionalidades a la vez: hijos con rama propia

Un hilo reparte funcionalidades a hijos que trabajan cada uno en su worktree (`telar hilo hijo «X» --rama`), y las
fusiona él (`telar hilo fusionar «X»`); el método general está en la skill `/ramas` y lo que hace cada orden en
[contratos.md](contratos.md), «`telar hilo <verbo> --json`». Lo propio de este repositorio:

- **Lo que git no versiona.** En el worktree no está `pagina/node_modules`: `telar hilo hijo --rama` lo enlaza al crearlo,
  a la de la carpeta del padre (`.gitignore` lo ignora, sin barra: un enlace no es una carpeta para git). Si falta (un
  worktree hecho a mano), `ln -s <carpeta principal>/pagina/node_modules pagina/node_modules`. Python no
  necesita nada: las pruebas (`python -m unittest discover -s pruebas`, desde el worktree) ponen su `src/` primero, y
  `scripts/dev.py` sirve el código de su copia. Un `uv run` dentro del worktree crea un `.venv` y un `uv.lock`: con
  `--no-project`, no.
- **Probar la página**: `python3 scripts/dev.py --puerto 187NN`, un puerto por hijo (el 18780 es el de siempre), y
  apagarlo al terminar. Usa los datos de verdad, como siempre. Para medirla o fotografiarla, `scripts/medir.py`
  («Comprobar en el navegador»), que se busca su puerto y apaga todo al terminar.
- **Lo compilado** (`src/telar/web/app.js`, `componentes.js`, `marco.css`) choca cada vez que dos ramas tocan la
  página, y no se resuelve a mano. `.gitattributes` los marca (`merge=telar-compilado`) y `.telar/compilados.yaml` dice
  cómo se generan (`npm run navegador` en `pagina/`) y de qué fuentes (`pagina/src/`, `media/`, `scripts/`…). Así,
  `telar hilo fusionar` no se niega por ellos: si la rama los toca, o toca sus fuentes, fusiona en un árbol aparte,
  los vuelve a generar y commitea la fusión con lo generado. Si choca algo más, se
  niega como siempre, y el hijo resuelve eso en su worktree. Ahí, un `git merge` de la base tampoco se detiene en lo
  compilado (el driver, que `telar hilo hijo --rama` deja puesto solo para los worktrees, se queda con la versión del
  hijo); después, `npm run navegador` y un commit, para probar con lo de los dos. En la carpeta principal siguen
  chocando como siempre: ahí se toma cualquiera de las dos versiones y se vuelve a generar. `media/css/iconos.css`
  (si cambian los íconos, `scripts/iconos.py`) no está marcado: se resuelve a mano.
- **`CHANGELOG.md`** no lo toca el hijo: escribe su entrada en `changelog.d/<rama>.md`, y fusionar la junta (abajo,
  «El CHANGELOG, por fragmentos»).
- **Después de fusionar**, en la carpeta principal: las pruebas juntas (Python y las de la página), y desplegar como
  dice abajo. Nada se sube a GitHub sin que la persona lo pida.

## El CHANGELOG, por fragmentos

Dos ramas que escriben en `CHANGELOG.md` chocan siempre: las dos agregan arriba, en `[Unreleased]`. Y si el hijo manda
su entrada en el mensaje de «listo», el padre la pega a mano después de fusionar: un paso más por hijo. Por eso cada
hijo escribe la suya en un archivo propio, y `telar hilo fusionar` la pone en su lugar.

- **Dónde**: `changelog.d/<rama>.md`, uno por rama (el nombre de la rama, con `-` en vez de `/`). Lo declara
  `.telar/changelog.yaml` (`archivo: CHANGELOG.md`, `carpeta: changelog.d`, `ancho: 120`, `negrita: true`; la forma
  general, en [perfil.md](perfil.md), «El CHANGELOG por fragmentos»), y el contexto del hijo se lo dice al arrancar.
- **Cómo es**: un pedazo del CHANGELOG tal cual, en inglés como él: una o más secciones (`### Added`, `### Changed`,
  `### Deprecated`, `### Removed`, `### Fixed`, `### Security`) con sus entradas, cada una con su primera oración en
  negrita, líneas de 120 a lo más y las siguientes sangradas en dos espacios. El ejemplo, en `changelog.d/README.md`.
- **Al fusionar**: lee los fragmentos en lo que dejaría la fusión (`git merge-tree`), sin tocar nada. Si uno está mal
  formado se niega, con el archivo y la línea de cada problema, y `main` queda igual: el hijo lo arregla en su
  worktree. Si están bien, la fusión se hace en un árbol aparte (el mismo de lo compilado), cada entrada va arriba de
  su sección en `[Unreleased]` (lo más nuevo, primero; la sección que falta se crea en el orden de Keep a Changelog) y
  el fragmento se borra, todo en el commit de la fusión: un `git revert -m 1` de la funcionalidad se lleva también su
  entrada. Se eligió eso y no un commit aparte justo después por lo mismo: una funcionalidad, un commit.
- **Sin fragmento**, fusiona igual y lo dice (en el texto, y `changelog.fragmentos: []` en `--json`): el padre la
  escribe o se la pide. En un repositorio sin `.telar/changelog.yaml`, nada cambia: un archivo en `changelog.d/` es
  uno más.
- **Con `--seguir`** el fragmento se junta en esa fusión y sale de `main`, pero sigue en la rama del hijo: lo nuevo
  después va en otro fragmento (`changelog.d/<rama>-2.md`), no en el mismo; editar el ya juntado choca al fusionar.
- **El padre** ya no pega entradas: revisa el fragmento como el resto del diff. Lo que se commitea directo en `main`
  (sin rama) escribe en `CHANGELOG.md` como siempre.

## Llevarlo a las máquinas: `telar desplegar`

```
telar desplegar --ver                  # qué haría en cada máquina, sin tocar nada
telar desplegar                        # desde la carpeta principal, en main: a todas las máquinas
telar desplegar --maquina servidor     # solo a esa (las de [remotos] y esta, por su nombre)
```

Deja corriendo en cada máquina lo que está en main **aquí**: no pasa por GitHub, así que se despliega sin haber subido
nada. Las máquinas son esta y las de `[remotos]`; dónde vive el repositorio en cada una lo averigua solo
(docs/configuracion.md, «`telar desplegar`»). Lo que se hace en cada una lo declara el repositorio en
`.telar/despliegue.yaml` (docs/perfil.md, «El despliegue»); el de telar:

- **preparar**: si cambió `pyproject.toml`, reinstala telar (`uv tool install --force --editable '.[serve,bus]'`).
- **reiniciar** `telar-serve` (systemd) o `com.telar.serve` (launchd), donde esté instalado. La página viaja compilada
  (`src/telar/web/`): nadie compila nada al desplegar. Como red, si lo que se despliega toca la página, antes la
  vuelve a generar en un worktree temporal (unos segundos) y avisa si lo commiteado no corresponde a sus fuentes.
- **después**: si cambió lo que escribe las skills y los ganchos (`src/telar/agente/`, `servicios/skills.py`),
  `telar agente instalar --si`.
- **comprobar**: `/pagina.json` en la página de cada máquina (su puerto de verdad, que dice su `/salud`, y su propia
  llave, que nunca sale de ella), con la misma `firma` en todas; y `/api/salud`, la API detrás de la página.

En cada máquina, en orden, las otras primero y esta al final: el **código** (a otra máquina se le manda el commit a
una referencia propia, `refs/telar/llega-…`, con un `git push` que nunca se fuerza, y su main avanza con
`git merge --ff-only`; la referencia se borra), lo de **preparar**, el **reinicio** de cada servicio (y que tmux siga
vivo con sus ventanas, los hilos), lo de **después**, y **anotar** lo que corre en `refs/telar/desplegado`
del repositorio de esa máquina. Así el siguiente despliegue sabe qué cambió desde el último en cada una (`si_cambia`),
y una máquina que ya corre ese commit no se reinicia de nuevo (`--todo` hace todos los pasos igual). La primera vez
no hay nada anotado y se hace todo. Al final, las **comprobaciones** de cada máquina, también en las que ya estaban al
día.

Se niega, sin tocar nada, si no se está en main, si hay cambios sin commitear en lo versionado (aquí o en otra
máquina: lo no versionado no cuenta), si otra máquina tiene commits que aquí no están (hay que traerlos antes:
`git pull <destino>:<ruta> main`) o si una no contesta (`--maquina` despliega en las demás). Si un paso falla se
detiene ahí, dice cuál y en qué quedó cada máquina: qué commit tiene y cuál corre (`--json`, docs/contratos.md).
Reiniciar `serve` corta las terminales abiertas en el navegador: se reconectan solas.

Las pruebas (`pruebas/test_desplegar.py`) no usan la red: la otra máquina es un clon con su propio hogar, `ssh` es
uno de mentira que corre el comando aquí en ese hogar, y `systemctl` y `launchctl` también son de mentira. El
`servidor/desplegar.sh` de antes (que hacía `git pull` del remoto de git) se retiró: avisa y llama a
`telar desplegar`.

Una página que ya estaba abierta se pone al día sola (`pagina/src/web/recarga.ts`): trae escrita la firma de lo que se
le sirvió y la compara con la del `serve` que la sirve (`/pagina.json`, la de cuando arrancó: el contenido de
`indice.html`, `app.js` y `marco.css`), al volver a mirarla, cuando el servicio vuelve de reiniciarse y cada medio
minuto. Si es otra y no se está mirando, recarga sola; si se está mirando, la franja de avisos (arriba de la barra de
hilos) dice «página nueva», y «recargar» la recarga. Lo escrito en las cajas y lo que se miraba vuelven al recargar. Entre
que llega el código y el reinicio no avisa: los archivos ya son nuevos pero el Python que contesta es el de antes.
