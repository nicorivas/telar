# Cómo está hecho telar

telar junta en un solo lugar los hilos de trabajo de una persona: cada hilo es una terminal con
un agente (Claude Code, por ejemplo) trabajando en una carpeta. Alrededor de los hilos, telar
muestra lo que hay que hacer (tareas, agenda, correo) y deja que los agentes se hablen entre sí,
en una máquina o en varias.

Este documento describe cómo es telar hoy: las piezas, cómo se conectan y por dónde se enchufa lo
propio. Las claves de cada pieza están en [configuracion.md](configuracion.md); lo que falta, en
[propuestas/](propuestas/README.md).

## El dibujo

```
 lo que ves                  un proceso por máquina                 lo que hay debajo
 ──────────                  ──────────────────────                 ─────────────────

 ┌───────────────┐  HTTP    ┌──────────────────────────────┐  tmux  ┌──────────────────────┐
 │ la página     │  WS      │ telar serve (Python)         │───────▶│ una sesión de tmux   │
 │ · barra de    │─────────▶│  · la API (telar.servicios)  │        │ por máquina; cada    │
 │   hilos       │ Tailscale│  · la página                 │        │ hilo es una ventana  │
 │ · dashboard   │          │  · las terminales (PTY)      │◀───────│ con su agente        │
 │ · el hilo:    │          │  · el nodo del bus           │ ganchos└──────────────────────┘
 │   terminal,   │          │  · la página del equipo      │ del agente
 │   lectura…    │          └──┬────────────┬──────────┬───┘
 └───────────────┘             │            │          │ NATS   ┌──────────────────────┐
  navegador o celular          │            │          └───────▶│ las otras máquinas,  │
                               │            │                   │ con su telar serve   │
 ┌───────────────┐  socket     │            │                   └──────────────────────┘
 │ la CLI telar, │─────────────┤            │
 │ agentes,      │             ▼            ▼
 │ scripts       │  ┌───────────────────┐ ┌──────────────────────────────┐
 └───────────────┘  │ tu repositorio    │ │ lo tuyo, enchufado           │
                    │ + telar-perfil    │ │ · proveedores (tareas,       │
                    │ (qué es un        │ │   calendario, lo que sea)    │
                    │ proyecto)         │ │ · tipos (objetos en archivos)│
                    └───────────────────┘ │ · módulos (modulo.toml)      │
                                          └──────────────────────────────┘
```

Tres reglas sostienen el dibujo:

1. **La lógica vive una vez.** Cada orden de la CLI y cada ruta de la API son cáscaras de una misma
   función de `telar.servicios`, que devuelve un modelo (Pydantic): el modelo es el contrato
   ([contratos.md](contratos.md)). La página no tiene lógica de datos propia: pide a la API y dibuja.
   Cualquier cosa que telar muestra, un script o un agente la puede pedir igual (`telar … --json`).
2. **telar no sabe qué es un proyecto, ni cómo son tus tareas.** Lo dice tu repositorio
   (`telar-perfil.yaml`) y lo traen tus proveedores. telar sabe de hilos, de mensajes y de máquinas.
3. **Nada se hace a escondidas.** Los comandos son listas de palabras (sin shell), los proveedores
   no salen a la red salvo que se les pida, y una acción solo corre si el proveedor la ofreció.

## Las piezas

| pieza | qué es | dónde vive |
|---|---|---|
| **hilo** | una ventana de tmux con un agente, vinculada a una carpeta. telar recuerda su conversación, su atención y su prioridad | la sesión de tmux; el estado en `~/.local/state/telar/` ([estado.md](estado.md)) |
| **agente** | el programa que corre dentro del hilo. telar no lo pilota: lo reconoce por sus ganchos | [agentes.md](agentes.md) |
| **agente residente** | un hilo que siempre existe, con su carpeta, su memoria y su casilla; recibe encargos | `[agentes] carpeta` |
| **perfil** | lo que tu repositorio dice de sí mismo: qué carpetas son unidades de trabajo, qué archivo es su cara, qué secciones se leen | `telar-perfil.yaml`, en la raíz del repo ([perfil.md](perfil.md)) |
| **configuración** | lo de esta máquina: dónde está el repo, qué proveedores hay, qué se muestra | `~/.config/telar/config.toml` |
| **proveedor** | un programa que le trae a telar datos de afuera, en un JSON conocido: tareas, agenda, cualquier lista | `[proveedores.*]` |
| **tipo** | objetos guardados como archivos de texto, con un modelo y acciones; telar los lee y los escribe él mismo. Hoy hay uno: `tarea` | `telar.tipos`, `[tipos.*]` |
| **módulo** | una carpeta con un `modulo.toml` que aporta de una vez una pestaña, una app, un proceso periódico o un resultado | `[modulos]` |
| **mensaje** | texto para un hilo o un agente, en cualquier máquina; llega aunque el hilo esté cerrado | `telar mensaje`; viaja por el bus |
| **periódico** | algo que corre solo cada cierto tiempo, a veces abriendo un hilo con un agente | `telar periodicos` (cron) |
| **nodo** | la parte de `telar serve` que habla con el bus: recibe los mensajes, avisa a los hilos, publica qué hay vivo | `telar serve --nodo` |
| **la página** | lo que se ve: la barra de hilos, el dashboard y cada hilo; también es la app del celular | `telar serve --web`; su código, en `pagina/` |

## Un proceso por máquina

Cada máquina corre un solo `telar serve`, como servicio (systemd de usuario en Linux, launchd en
macOS), con el mismo código en todas. `telar instalar` deja una máquina andando: la configuración, la
llave de la página, el `[bus]`, el servicio y los ganchos del agente, y al final `telar doctor`. Lo que cambia entre máquinas es la
configuración: el servidor tiene el calendario, las tareas, los periódicos y la página del equipo;
el laptop, sus hilos y lo que solo él puede hacer (un navegador, archivos locales).

- **La API** escucha en un socket Unix (`~/.local/state/telar/serve/telar.sock`, en una carpeta solo
  para su dueño). La CLI, si la encuentra, le pide a ella; si no, hace el trabajo sola.
- **La página** (`--web`) se sirve en la dirección de Tailscale de la máquina (puerto 8780; en el
  servidor, `tailscale serve` le pone HTTPS). Se entra con una llave por máquina
  (`~/.config/telar/panel.llave`), que deja una cookie; además, cada pedido tiene que venir del mismo
  origen.
- **Las terminales**: `/pty` es un WebSocket que corre `telar mirar <hilo>` en un PTY. Con
  `?maquina=<otra>` reenvía a la de esa máquina: la dirección sale de la foto del espejo y se entra
  con el secreto del bus de la persona.
- **Las máquinas**: `/maquinas` lista las del bus que sirven su página; se pasa a otra con un boleto
  firmado que vence en un minuto y sirve una vez.
- **La página del equipo** (`--equipo`) es otra app, en su propio puerto: alguien de confianza ve tus
  tareas y te sugiere prioridades, sin alcanzar nada de tu API.
- **Las tareas de fondo**: refrescar el calendario (una copia que vale 10 minutos), la foto del
  estado.

Algunas órdenes todavía corren la CLI por dentro y leen su salida (`telar.servicios.en_proceso`): los
verbos de `telar hilo` y `telar tejer`. `hilo llevar` y las acciones del perfil quedan en la CLI a
propósito (tardan minutos o heredan la terminal).

## Los hilos y tmux

En cada máquina, todo hilo es una ventana de **una sola sesión** de tmux, la del telar (`sesion` en la
configuración), marcada con `@telar_id`. Los agentes, los periódicos, la página y el laptop cuando
abre un hilo en el servidor abren ventanas en esa sesión, nunca sesiones propias.

Mirar un hilo es engancharse a una **sesión agrupada** con la del telar, fija en su ventana
(`ver-<id>-<máquina>`). Comparte las ventanas pero elige la suya, así que dos pantallas miran hilos
distintos sin moverse una a la otra. Para que sea confiable:

- telar apunta siempre a las ventanas con su sesión delante (`=telar:@3`), nunca un `@3` a secas;
- un gancho (`session-window-changed`) suelta a quien mira si su ventana deja de ser la actual;
- la dirección guardada lleva la marca (`@338/1a2b3c4d`): tmux reusa los `@N` al reiniciarse;
- `destroy-unattached` borra la vista cuando nadie la mira.

La página dimensiona la ventana (`window-size latest`). El tmux de una máquina que se mira desde
otra va sin prefijo ni barra. Pide tmux 3.5 o más: la 3.4 tiene un segfault que se lleva todos los hilos.

Si tmux se cae, el nodo sabe quién estaba vivo (lo anota cada 30 s) y `telar hilo caidos` los reabre
con su conversación.

## Entre máquinas: el bus

Las máquinas se unen por un servidor NATS con JetStream (`servidor/telar-bus.service`) en la que no se
apaga. Cada nodo abre una conexión saliente hacia él. Sin `[bus] url`, nada de esto corre y telar
funciona en una sola máquina.

Por el bus viajan:

| qué | dónde | para qué |
|---|---|---|
| los mensajes | stream `TELAR_CASILLAS`, tema `casilla.<persona>.<hilo>` | esperan hasta que los recoja la máquina donde vive el hilo; el mismo id no se guarda dos veces |
| el estado | almacén `TELAR_HILOS`, clave `<persona>.<hilo>` | dónde vive cada hilo y en qué anda; cada máquina publica los suyos y se entera de los demás al instante |
| la foto | almacén `TELAR_ESPEJO`, cada 30 s | los hilos de cada máquina y la dirección de su página |
| los pedidos | `rpc.<persona>.<maquina>.<verbo>` | leer una conversación, las tareas de otra máquina, los periódicos, la bandeja del equipo |
| el registro | `TELAR_REGISTRO`, dos semanas | quién le dijo qué a quién, y los mensajes retenidos |

Las direcciones no dependen de la máquina: mudar un hilo cambia su estado, no su casilla. Cuando un
hilo nace o muere en una máquina, la otra trae o cierra su ventana al instante.

**Cómo llega un mensaje.** El nodo de la máquina del hilo lo deja en su casilla local
(`telar.casilla`). Los ganchos `Stop` y `UserPromptSubmit` del agente (`telar agente casilla`) se lo
entregan entero al terminar el turno. Si el agente está ocioso, hay que despertarlo con una línea de
aviso («↯ mensaje nuevo · …», nunca el contenido), y el gancho `UserPromptSubmit` le agrega los mensajes:

- con **el mod de telar** (`src/telar/mod/`, un mod de Claude Code que cada sesión carga por
  `CLAUDE_CODE_PLUGIN_DIRS`), el aviso lo manda el mod como un mensaje (`$.prompt.submit`) en cuanto la
  sesión queda ociosa, sin pasar por el teclado: no cae sobre lo que la persona está escribiendo. Mientras
  vive, el mod toca un archivo en la casilla (`.mod`) cada pocos segundos;
- sin el mod (o con esa señal vieja de más de 30 s), el nodo teclea el aviso en la terminal del hilo.

Un hilo cerrado se abre retomando su conversación.

**Entre hilos de una misma persona no hay aprobación.** El mensaje de un hilo propio llega como pedido
de un colega; el de otra persona, como mensaje. En lugar de la aprobación hay frenos: cada mensaje
lleva `persona` y `saltos` (la cadena se corta cuando la persona habla), y pasado el tope de saltos (6)
o de mensajes por hora de un hilo (30) se retiene en el registro hasta que la persona lo suelte.

**Una cuenta por persona.** El servidor NATS tiene una cuenta por persona (`telar bus persona`,
`telar.cuentas`): su usuario es su nombre en el bus y su clave, el secreto de `[bus] token`, el mismo en
todas sus máquinas. Una cuenta es un espacio aparte: sus casillas, el estado de sus hilos, la foto de sus
máquinas y los pedidos a sus nodos no los ve otra persona, porque el servidor no lo deja. El mismo secreto
abre la terminal de otra máquina suya (`/pty?maquina=`) y firma los boletos de `/maquinas`, así que una
máquina solo acepta a otra de la misma persona. El servidor guarda solo el hash de cada clave (bcrypt).
Entre cuentas cruza solo lo que cada una exporta (`telar.entre_personas`): `correo.<persona>`, un
servicio con el que otra persona le deja un mensaje a un hilo suyo (su nodo lo guarda en la casilla del
hilo y responde; el servidor dice de qué cuenta vino, así que nadie escribe a nombre de otro), y
`directorio.<persona>`, la lista de sus hilos que publica su nodo cada 30 s. `telar correo enviar
persona+hilo@…` va por ahí si esa persona tiene nodo en el bus; si no, por el correo del servidor (el
`cartero`, en [servidor/](../servidor/README.md)), que sigue mientras otras personas lo usen.

Git sigue siendo para el contenido: los archivos se sincronizan con `pull` y `push`, a su ritmo, y un
hilo vinculado a una carpeta que la otra máquina todavía no tiene se ve sin ficha hasta el próximo pull.

## Los agentes residentes

No hay dos clases de hilo. Un hilo es siempre una conversación con una casa (una carpeta), y puede
ser de paso (se abre para algo y se archiva) o **residente**: siempre existe, recibe encargos y rota
su conversación cuando pesa. Un residente vive en una carpeta bajo `[agentes] carpeta`, con su
`CLAUDE.md`, `README.md`, `memoria/` y `bitacora.md`.

Cada agente arranca en su carpeta, para que Claude Code cargue su `CLAUDE.md` desde el comienzo: Claude
lee los `CLAUDE.md` desde la carpeta de arranque hasta la raíz del repositorio, así que lo común a
todos los agentes va en el `CLAUDE.md` de la carpeta que los contiene. Un `@import` fuera de la carpeta
de arranque se ignora sin aviso, y `$CLAUDE_PROJECT_DIR` es la carpeta de arranque, no la raíz: los
ganchos se escriben con ruta fija.

`telar encargar <agente> "…"` (o un periódico con `agente = "…"`):

- sesión viva y libre: se le escribe el encargo;
- viva y trabajando: va a la cola, y el gancho `Stop` le entrega el siguiente al terminar su turno;
- sin sesión: se abre retomando su última conversación, o una nueva si pasó de `[agentes] rotar_mb`.

El resultado se deja en el registro (la tarea, el estado del proyecto, la bitácora), no en la
conversación. `[agente] max_vivos` limita los hilos vivos de una máquina: antes de abrir otro, telar
cierra los ociosos que nadie mira, los residentes al final. Cerrar no pierde nada.

Cada hilo arranca sabiendo de los demás: el gancho `SessionStart` le da su nombre, su casilla y cómo
escribir a otros, y `telar agente instalar` le pone la skill `/hilos`.

## Los tipos: objetos sobre archivos

Un **tipo** es la forma de unos objetos que viven como archivos de texto (`telar.tipos`): un modelo,
sus **acciones** y sus **formatos** (lentes que leen el texto y lo editan al mínimo). El primero es
`tarea`, con dos formatos:

- **el archivo propio**: una tarea por archivo, con líneas `clave: valor`, el contexto,
  `## Conexiones` y `## Historia`;
- **la casilla**: una línea `- [ ]` de un documento, en sus dos dialectos (`@owner(…)`, `@deadline(…)`;
  y `vence:`, `!alta`, `#etiqueta`).

Leer y escribir sin cambios da los mismos bytes; una acción toca solo sus líneas.

- **Las acciones** (`completar`, `cerrar`, `reabrir`, `algun_dia`, `esperar`, `reagendar`, `asignar`,
  `anotar`, `proponer`, `responder`, `editar`, `secuela`, `conectar`) son funciones sobre el modelo,
  cada una con su precondición y su línea en la historia.
- **La carpeta** (`Carpeta`) lee un objeto con su versión (la huella del archivo) y le aplica una
  acción. Con una versión vieja, la acción se rechaza. Hay un escritor a la vez (un candado), la
  escritura es atómica, y lo escrito tiene que releerse igual a lo que se quiso escribir o no se
  escribe. Al crear, el número lo elige quien escribe, con el candado tomado.
- **El índice** (`telar.tipos.indice`) tiene los objetos en la memoria de `telar serve` y se pone al
  día por la fecha y el tamaño de cada archivo: con 300 tareas, mirar si algo cambió cuesta 1 ms. Nadie
  escribe en él: la acción escribe el archivo y el índice lo relee.

Hay dos cáscaras: `telar tipo tarea <verbo>` y las rutas `/tipos/tarea` (una versión vieja es un 409).
Desde una máquina con `[tipos.tarea] en`, la orden va por el bus a la que las tiene: hay un solo
escritor. Quien escribe commitea y sube el archivo (`telar commit`). El proveedor `tipo = "tipo"` le
da esas tareas a `telar hoy` y al dashboard, con su ficha y sus botones.

**Cuando el modelo cambie, ningún archivo lleva un campo `version`: el lector entiende la forma vieja y la
nueva**, y las dos dan la misma tarea. (La versión de la carpeta, de arriba, es otra cosa: la huella del
archivo al leerlo, que nadie escribe en él.) Un campo `version` obligaría a reescribir cientos de archivos (o a
dejarlos a medias), haría que una tarea escrita a mano o por otra herramienta sin el campo no supiera qué es, y
pondría una línea que nadie lee en cada diff. Leer las dos formas no cuesta eso: el archivo de antes sigue
siendo válido tal como está, y se reescribe solo lo que una acción toca. Así ya se lee hoy:

- un campo que el archivo no dice vale su valor por defecto, que es lo que significaba no decirlo (`estado:
  activa`, `prioridad: 2`, `area: personal`): un campo nuevo entra así;
- una línea de la historia, con hora o sin ella;
- la casilla, en sus dos dialectos y con los sinónimos de cada clave (`@owner`, `@dueño`, `@responsable`,
  `@para` o «@Ana:» al comienzo);
- el archivo propio, con los sinónimos de sus claves (`dueno`, sin ñ, es `dueño`) y la clave escrita con la
  tilde aparte.

Una clave que cambie de nombre se agrega como sinónimo, en los dos formatos, y una línea se reescribe en el
nombre que ya tenía. Una clave que el formato no conoce (`version: 2`, la de otra herramienta) no entra al
modelo y queda tal cual: leer y escribir no la tocan. Un BOM al comienzo o los finales CRLF tampoco cambian
lo que se lee, y al escribir se conservan. Lo fijan las pruebas de `pruebas/test_tarea_dos_formas.py`.

### Las casillas de los documentos

Un pendiente de un documento (una casilla `- [ ] …` de la sección `pendientes` del perfil) no es una tarea
del tipo: vive en su documento, y telar solo le cambia la marca o el responsable (`telar pendiente
--hecho/--responsable`, `telar.vinetas`). Nace sin id, y su referencia (`faro:2`) es su lugar, que cambia
cuando el documento cambia. Mientras no tenga id se la busca por su texto, y se toca solo si hay una.

La primera vez que telar la **escribe** le agrega un id al final de la línea, `<!-- id: c-1a2b3c -->`: `c-` y
seis cifras hexadecimales, único en ese documento, con una forma que no se confunde con la de una tarea
(`T84`). Desde ahí se la busca por ese id, y su dirección es `pendiente:c-1a2b3c` (`telar objeto`, que la
ve con su texto, su estado, su documento, su línea y su responsable, y le aplica `hecho` y `responsable`).
La lectura (`telar.lectura`) reconoce el id y no lo muestra en el texto. Mirar o llevar una casilla a su hilo
no le pone id: solo escribirla.

Las reglas de esa escritura: un id que ya está (de telar, de una tarea, o puesto a mano) no se reescribe;
solo cuenta como id el comentario que cierra la línea, fuera de un `código` (una casilla que habla de la
sintaxis no lo toma por suyo). Se cambia una línea y el resto del archivo queda byte a byte (`\r\n`, unicode,
el final sin salto, los espacios del final de esa línea); se escribe a un temporal y se renombra, así que si no
se puede escribir el documento queda como estaba, y un archivo de solo lectura no se toca aunque la carpeta
se pueda escribir. Un documento con otro nombre (un enlace duro) se escribe en su lugar, sin temporal, para
no separarlo del otro nombre. La casilla es lo que ve la lectura: si la línea tiene un U+2028 o un salto de
página, la casilla llega hasta ahí, y el id va antes de ese carácter.

Dos casillas con el mismo id no se adivinan: en un documento, se dice, y alguien le borra el id a la copia; en
dos documentos (una línea copiada a otro proyecto, un README de plantilla), la dirección es un 409 que dice
dónde está cada una, y cada una se sigue alcanzando por su `ref`. El id solo, sin `pendiente:`, nombra una
casilla si tiene la forma de telar (`c-1a2b3c`); uno puesto a mano (`T84`) no le gana a la tarea T84 de un
proveedor: se lo nombra con su dirección, `pendiente:T84`. Dos casillas iguales sin id son dos filas en `telar
pendientes`: la lectura dice cuál es cada una entre las que dicen lo mismo (la primera o la segunda de dos, en
el orden del documento; `repetida` en la fila), y se le escribe a esa, que recibe su propio id. Si entretanto
cambió cuántas casillas dicen eso (alguien agregó o borró una igual), no se adivina: un 409, y nada cambia.

## La página

Se escribe en TypeScript (`pagina/src/`) y se empaqueta con esbuild (`pagina/scripts/navegador.mjs`)
en `src/telar/web/`: `app.js` y `marco.css` (los estilos de `pagina/media/css/`). xterm.js va aparte, en
`src/telar/web/xterm/`, y se carga la primera vez que se abre una terminal. Cómo desarrollarla con recarga
sola: [desarrollar.md](desarrollar.md).

Todo vive en un solo documento, sin marcos: cada pantalla se dibuja en un elemento de la página, y su CSS va
con `@scope` (`#barra`, `.v-dia`, `.v-terminal`…), para que sus nombres sean solo suyos. Solo van en un iframe
los lienzos y las apps del dashboard, que son páginas de afuera (aisladas con `sandbox`).

- **La barra de hilos**: los de esta máquina y los de las demás en una sola lista, con la máquina en
  una columna (⇄). Un hilo de otra máquina se nombra `máquina:hilo`. «+ nuevo», en la cabecera de HILOS,
  abre uno (`POST /ir` con `crear`). Está en `pagina/src/vistas/hilos.ts`.
- **El dashboard**: las pestañas del día (tareas, agenda, correo, lo que traigan los proveedores y
  los módulos), que son las filas del grupo DASHBOARD de la barra. La configuración es el ⚙ de la cabecera:
  un menú vertical de secciones (pestañas, calendario, hilos, agente, periódicos, agentes, módulos), cada una
  en su archivo de `vistas/dashboard/config/` y nombrada en su registro (`configuracion.ts`): una sección nueva
  es un archivo más.
  `vistas/dashboard/panel.ts` es el núcleo: lee la configuración y el día, lleva las pestañas y las teclas, y le
  pasa cada acción a la pantalla que la declara. Cada pantalla (ahora, tareas, los bloques, proyectos, el plan y
  el calendario, las secciones, el equipo) vive en su archivo con su estado, su HTML y sus acciones, y recibe del
  núcleo lo que dice `vistas/dashboard/pantalla.ts`: una pantalla nueva es un archivo más. Todo se pinta en
  `vistas/dashboard/vista.ts`, que filtra, ordena y atiende los clics y las teclas. Sus atajos valen solo mientras se ve, y nunca mientras se escribe en un campo
  de afuera (el buscador de la barra, una terminal).
- **Un hilo** tiene vistas, en un registro (`pagina/src/web/vistas-hilo.ts`): la terminal (⌥T), la lectura (⌥L,
  solo la respuesta final del agente, con un renderizador por fuente; la conversación la deja el mod de telar en
  la casilla, y sin él se lee del registro del agente) y la conversación (⌥C). Una vista nueva es una entrada del
  registro, con su `montar`: se dibuja en un elemento de la página y se cierra cuando ya no hace falta (de las
  terminales quedan abiertas las ocho últimas). La carpeta de un hilo y «compartir» se dibujan igual
  (`web/carpeta.ts`, `web/compartir.ts`). En las tres vistas, las rutas de archivo que escribe el agente son
  enlaces al visor de documentos (`web/rutas-agente.ts`), en la máquina del hilo. Una relativa es de donde arrancó
  el agente, que según `[agente] carpeta` es la carpeta del hilo o la raíz: se prueba primero la del hilo y
  después la raíz, y se abre la que existe. Una de otra máquina va como `máquina:ruta`, que el visor lee sola por
  `/api/archivos`. Una dirección web (texto, un enlace, o un hipervínculo OSC 8 de la terminal) abre una pestaña
  nueva en el navegador de la persona. En la terminal, una ruta o una dirección que llegó partida en varias filas
  se encuentra entera (`web/enlaces.ts`): Claude Code corta él sus líneas al ancho de su caja, con saltos de
  verdad, así que una fila que llega al borde derecho sigue en la de abajo si lo que cruza el corte es más largo
  que una fila. La dirección de un objeto (`tipo:id[@máquina]`: `tarea:T366`, `hilo:Telar`, y los tipos de los
  módulos, que dice `/api/objetos/tipos`) también es un enlace: `navegador/app.ts` abre una tarea en su ficha, un
  archivo o un proyecto en el visor y un hilo como la barra, y cualquier otra en la vista del objeto
  (`web/objeto.ts`: `/api/objetos/<dirección>`, con sus enlaces y sus acciones). Un `.html` el visor lo muestra
  dibujado, en un iframe aislado (`/api/archivos/ver`, con `sandbox`: sus scripts no ven la llave ni la API de la
  página), con su código a un clic. Al lado del archivo, sus conexiones en el grafo (`/api/modulos/grafo/vecinos`,
  si la máquina del archivo tiene el módulo): se piden después de mostrarlo, porque el grafo lee el repositorio
  entero. Lo que muestra el visor va en el recuadro de `componentes.css`, y arriba «‹ …» vuelve al documento
  anterior (el visor anota por cuáles pasó) y del primero a donde se apretó el enlace, «‹ hilo · vista» o ⎋:
  `navegador/app.ts` recuerda de dónde se vino.
- **La terminal** es xterm.js sobre `/pty`, con un eco predictivo propio (`pagina/src/navegador/eco/`): dibuja
  al tiro lo que se escribe y lo confirma con lo que llega. Se reconecta sola si se corta.
- **Los avisos y diálogos** (un aviso que se va solo, un campo para escribir, un texto largo con a quién va, un
  menú para elegir, un aviso con botones) los pone la página misma, encima de todo (`pagina/src/web/interfaz.ts`):
  se ven mire uno lo que mire, también la lista en el celular. El dashboard, la barra y las órdenes `telar.*` los
  piden a `web/ui.ts`, que también sabe abrir un enlace, mostrar un hilo o una carpeta, y correr una orden.
- **En el celular** es una app instalable (manifiesto y service worker en `web/app/`), y la hoja
  «compartir» del teléfono lleva un enlace o un texto a un hilo (`/compartir`).

## Cómo se mueve una cosa

**Un hilo pide atención.** El agente termina y espera respuesta. El mod de telar (o, sin él, el gancho
clásico; los dos llaman a `telar agente aviso`) anota «te espera» en el estado; el nodo lo publica en el bus y la barra de cada máquina lo pinta.
«Terminó» y no lo viste cuenta como «te espera».

**Un agente le pide algo a otro.** El hilo A corre `telar mensaje B "…"`. El mensaje va al bus, el
nodo de la máquina de B lo deja en su casilla, y el gancho de B se lo entrega al terminar su turno.

**Una tarea se trabaja.** El dashboard pide las tareas (`/hoy`, que consulta al proveedor). Con ▶,
telar busca el hilo de la tarea: el que lleva su id en el nombre, el que tiene su carpeta en el texto
o el que calza con una etiqueta. Si no hay ninguno, abre uno nuevo con el agente y le da la tarea como
primer mensaje. Con ✓, corre la acción «hecha» que el proveedor ofreció.

## Por dónde se enchufa lo propio

| quiero… | se hace con | sin escribir código |
|---|---|---|
| que telar entienda mis proyectos | el perfil (`telar-perfil.yaml`) | sí |
| ver mis tareas | `[proveedores.tareas]`: `markdown`, `tipo` o `comando` | sí, con `markdown` o `tipo` |
| ver mi agenda | `[proveedores.calendario]`: iCal o `gws` | sí |
| una pestaña propia en el dashboard | `[bloques]`: un comando que imprime una página | no: un script |
| una app (un juego, un visor) | `[apps]`: una página, un archivo o una URL | depende |
| algo que corra solo | `telar periodicos crear …` | sí |
| empaquetar todo lo anterior | un módulo con `modulo.toml` | — |
| que otro agente o script use telar | la CLI con `--json` o la API ([contratos.md](contratos.md)) | — |
| integrar otro agente | sus ganchos, con los seis eventos ([agentes.md](agentes.md)) | casi |

## Conectar un sistema de tareas

Hay cuatro niveles. Cada uno agrega algo al anterior, y se puede parar en cualquiera.

### Nivel 1: casillas en tus documentos (sin código)

Si tus tareas ya son casillas de markdown en los README de tus proyectos, basta con decirle a telar
dónde mirar:

```toml
# ~/.config/telar/config.toml
[proveedores.tareas]
tipo  = "markdown"
rutas = ["proyectos/*/README.md"]
encabezado = '^##\s+Pendientes'     # opcional: solo esa sección
```

Cada casilla es una tarea, y entiende unas pocas marcas:

```markdown
## Pendientes
- [ ] Medir el alcance real  vence:2026-06-30  !alta  #faro
- [>] Ajustar el giro  espera:@electricista
- [x] Montar la lámpara
```

`[>]` es «en curso», `espera:` saca la tarea de lo urgente (depende de otro), y como la tarea vive en
la carpeta de un proyecto, telar ya sabe a qué hilo va.

### Nivel 2: una carpeta de tareas, que telar escribe (sin código)

Si quieres una tarea por archivo, con su historia, y que telar las cambie él mismo (✓, reagendar,
anotar), usa el tipo `tarea`:

```toml
[tipos.tarea]
carpeta = "~/notas/tareas"     # un T84.md por tarea

[proveedores.tareas]
tipo    = "tipo"
carpeta = "~/notas/tareas"     # la misma
```

La ficha y sus botones salen de las acciones del tipo; desde la terminal, `telar tipo tarea …`.

### Nivel 3: tu propio gestor, por un puente (un script)

Si tus tareas viven en otra parte (un `todo.txt`, Todoist, una base de datos, una CLI propia),
escribes un **puente**: un programa que las imprime en el JSON que telar espera.

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/ruta/a/mis-tareas"]
```

El programa imprime una lista. Solo `texto` es obligatorio:

```json
[{"id": "T84", "texto": "Medir el alcance", "prioridad": "alta", "vence": "2026-06-30",
  "etiquetas": ["faro"], "espera": "", "en_curso": false, "area": "trabajo"}]
```

Un puente completo para un `todo.txt` (el formato de [todotxt.org](http://todotxt.org)):

```python
#!/usr/bin/env python3
"""Las tareas de ~/todo.txt, en el JSON de telar."""
import json, re
from pathlib import Path

PRIORIDAD = {"A": "alta", "B": "media", "C": "baja"}
tareas = []
for n, linea in enumerate(Path("~/todo.txt").expanduser().read_text().splitlines(), 1):
    if not linea.strip() or linea.startswith("x "):          # vacía o hecha
        continue
    pri = re.match(r"\(([A-Z])\) ", linea)
    vence = re.search(r"\bdue:(\d{4}-\d{2}-\d{2})", linea)
    texto = re.sub(r"^\([A-Z]\) |\s*\bdue:\S+|\s*[+@]\S+", "", linea).strip()
    tareas.append({"id": str(n), "texto": texto,
                   "prioridad": PRIORIDAD.get(pri.group(1)) if pri else None,
                   "vence": vence.group(1) if vence else None,
                   "etiquetas": re.findall(r"\+(\S+)", linea)})   # +faro → el hilo «faro»
print(json.dumps(tareas, ensure_ascii=False))
```

Con eso, tus tareas aparecen en el dashboard ordenadas por urgencia (prioridad y fecha), cada una al
lado del hilo donde se trabaja, y ▶ la lleva a un agente.

### Nivel 4: la ficha y las acciones del puente

Para poder **hacer cosas** sobre una tarea desde telar (marcarla hecha, cambiarle la fecha,
contestarle algo), el puente ofrece además su **ficha**:

```toml
[proveedores.tareas]
tipo    = "comando"
comando = ["/ruta/a/mis-tareas"]
detalle = ["/ruta/a/mis-tareas", "--ver", "{id}"]
```

`--ver T84` imprime una página con la tarea y sus botones:

```json
{ "titulo": "T84 · Medir el alcance", "subtitulo": "alta · vence 2026-06-30",
  "bloques": [{"titulo": "notas", "texto": "falta la cota del lado norte"}],
  "acciones": [
    {"nombre": "✓ hecha", "rol": "hecha", "principal": true, "comando": ["mis-tareas", "hecha", "T84"]},
    {"nombre": "cambiar fecha", "rol": "fecha", "comando": ["mis-tareas", "fecha", "T84", "{texto}"]},
    {"nombre": "anotar", "pide": "qué", "comando": ["mis-tareas", "nota", "T84", "{texto}"]},
    {"nombre": "trabajar en un hilo", "tipo": "hilo"} ] }
```

- El **rol** dice qué es cada acción para quien la corre sin abrir la ficha. `hecha` es la que
  corre el ✓ de la lista, y `fecha` la que corre el selector de fecha al hacer clic en un atraso.
- Una acción solo corre si el proveedor la ofreció: telar vuelve a pedir la ficha y toma el
  comando de ahí, nunca de quien hace clic.
- Un agente usa lo mismo: `telar tarea T84 --json` lee la ficha, y
  `telar tarea T84 --accion 0` corre la primera acción.

### Si tus tareas viven en otra máquina

Si el gestor corre en un servidor (para que el laptop y el servidor vean lo mismo, sin esperar a que
se sincronice una copia), se dice dónde:

```toml
[proveedores.tareas]
tipo = "comando"
en   = "servidor"          # la máquina, por el bus: se leen allá y sus acciones corren allá
comando = ["/ruta/allá/mis-tareas"]
```
