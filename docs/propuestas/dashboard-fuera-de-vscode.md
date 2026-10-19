# El dashboard fuera de VS Code

Propuesta, 16-oct-2026. Estado al 18-oct: **la barra, el dashboard y las terminales ya corren en el
navegador** (`npm run panel` en `vscode/`), pero hay que levantarlo a mano, el celular sigue en `telar
web` y no existe `telar serve`. El estado y lo que sigue están en «Estado y plan», al final: esa sección
manda sobre los pasos de más abajo, que fueron el plan original.

## Por qué

La lógica de telar ya no depende de VS Code: vive en la CLI (`telar … --json`), los hilos son
ventanas de tmux y las máquinas se hablan por el bus. Lo que sí depende es la barra de hilos y el
dashboard, que se dibujan dentro de la extensión (`vscode/src/vistas/`, ~5.400 líneas; `hoy.ts` solo
tiene ~2.600, mezclando dibujo, estado y manejo de mensajes).

Eso cuesta:

- **Hay dos dashboards.** `telar web` tiene su propio calendario y su propia lista, y ya se separan.
- **Iterar es lento.** Cada cambio es compilar, empaquetar el `.vsix`, instalarlo y recargar VS Code.
  En un navegador es guardar y recargar, y se puede probar automáticamente.
- **El panel de VS Code obliga a rodeos.** El lienzo entra como `srcdoc`, cada app servida tiene que
  agregarse al CSP, y una página http fuera de localhost puede quedar en blanco.
- **No hay direcciones.** No se puede guardar ni mandar «este correo» o «esta tarea» como un enlace.
- **Otras personas** (un colega con `telar persona`, alguien del equipo) tendrían que instalar VS
  Code y la extensión.

Los demás administradores de agentes (ver `lo-que-hacen-los-otros.md`) no viven en VS Code: son
apps nativas, terminales o webs. Y quien más usa telar casi no usa el editor.

## Qué se pierde (y qué no)

Fuera de VS Code se pierden la integración de Claude Code con el editor (diffs, selección), el editor
al lado, la terminal integrada y los menús nativos (`showQuickPick`, `showInputBox`). La propuesta
**no** es dejar VS Code: es que el dashboard deje de depender de él. Mientras se use VS Code, se sigue
viendo ahí igual; fuera, se ve en el navegador. La terminal sigue siendo la de siempre (una nativa
con tmux, o la de VS Code).

## La forma

Tres capas, de abajo hacia arriba:

1. **Los datos: la CLI.** Ya existe. Cada vista se arma con el JSON de una orden (`telar hoy`,
   `telar bloque`, `telar tarea`, `telar proyectos`…), y cada acción es una orden.
2. **El servicio: `telar serve`.** Una API HTTP chica sobre la CLI, en cada máquina, solo por
   loopback o Tailscale y con llave (como `telar equipo`). Cada ruta es una orden permitida, con sus
   argumentos validados; nada de un «corre lo que te pidan». Entrega además lo que hoy la extensión
   lee del disco: el HTML de un lienzo, un README (ya convertido a HTML), la memoria de un lienzo.
   `telar web` ya tiene la mitad de esto y se fusiona aquí.
3. **La interfaz: un núcleo y dos anfitriones.**
   - El **núcleo** (`vscode/src/nucleo/`, o un paquete aparte) tiene las vistas como funciones puras
     (JSON → HTML), el estado de cada pantalla y el manejo de las acciones. No importa `vscode` (una
     regla del linter lo impide).
   - Un **anfitrión** le da al núcleo lo que depende de dónde corre, con una interfaz chica:

     ```ts
     interface Anfitrion {
         pedir(orden: string[]): Promise<{ datos?: unknown; error?: string }>;  // la CLI, o HTTP
         elegir(titulo: string, opciones: Opcion[]): Promise<Opcion | undefined>; // QuickPick, o un menú
         preguntar(titulo: string, ayuda?: string): Promise<string | undefined>;  // InputBox, o un campo
         abrir(destino: string, reusar?: string): Promise<void>;                  // URL, archivo, pestaña
         avisar(texto: string, nivel?: 'info' | 'falla'): void;
         progreso<T>(titulo: string, trabajo: () => Promise<T>): Promise<T>;
         guardar(clave: string, valor: unknown): void;                            // globalState, o localStorage
     }
     ```

   - El **anfitrión de VS Code** usa la CLI directo y la API de VS Code: es lo de hoy, reordenado.
   - El **anfitrión web** usa `fetch` contra `telar serve` y sus propios menús y campos (HTML), y se
     instala como app (PWA) en el laptop y el celular.

## Pasos

Cada paso deja todo funcionando; se puede parar en cualquiera.

1. **Separar sin cambiar nada.** Crear `nucleo/`, mover ahí las vistas que ya son puras
   (`proyectos.ts`, `ahora.ts`, `plan.ts`, la parte de dibujo de `dia.ts`) y la regla del linter.
2. **El anfitrión.** Definir la interfaz y hacer que `hoy.ts` pase por ella en vez de llamar a
   `vscode.window.*` y `cli.*` directo. Empezar por las pantallas que más se usan: **correo** (los
   bloques y el ítem abierto) y **tareas**. El markdown se convierte con una librería (markdown-it) en
   vez de `markdown.api.render`.
3. **`telar serve`.** La API sobre la CLI, con llave, y las rutas que piden correo y tareas. Fusionar
   las de `telar web`.
4. **El anfitrión web.** Una página que carga el núcleo (empaquetado con esbuild) y habla con
   `telar serve`. Correo y tareas primero; probar en el laptop y en el celular.
5. **Las demás pantallas**, una por una: proyectos, plan, calendario, periódicos, configuración,
   apps. Al pasar el calendario, `telar web` deja de tener el suyo.
6. **La barra de hilos.** La misma idea: núcleo y anfitriones. En la web, un clic en un hilo lo trae
   al frente en tmux (en el laptop) o abre su conversación (en el celular).
7. **Opcional: una app propia** (Tauri) que junte la barra, el dashboard y una terminal (xterm.js
   sobre tmux, local), con atajos globales y notificaciones.

## Lo que hay que resolver

- **La llave.** `telar serve` escribe en los agentes: solo por loopback o Tailscale, con llave por
  dispositivo y nada expuesto a internet. Agent of Empires usa un token de 256 bits en cookie
  HttpOnly y una segunda contraseña para lo delicado; algo así basta.
- **Lo que solo existe en el laptop.** Abrir una pestaña de Chrome por AppleScript, el portapapeles,
  los archivos locales: los hace el `telar serve` del laptop, no el del servidor.
- **Teclas.** En un navegador, ⌘W y ⌘T son del navegador; la app propia (paso 7) lo resuelve.
- **El tamaño del paso 2.** Es el más grande: `hoy.ts` mezcla todo. Por eso va pantalla por pantalla,
  con el dashboard de VS Code funcionando en cada commit.

## Lo hecho (16-oct-2026)

Se tomó un camino más corto que el de arriba: **el núcleo sigue en Node** (ya llamaba a la CLI) y no
se reescribió en el navegador. La dependencia de VS Code resultó concentrada en ~10 clases de llamadas:

- `anfitrion.ts`: la interfaz (avisos, campos, menús, abrir enlaces y archivos, la barra de estado, ir
  a un hilo, órdenes). `anfitrion-vscode.ts` la cumple con la API de VS Code, igual que antes.
- `superficie.ts`: dónde se dibuja el dashboard (el panel de VS Code, o las pestañas de un navegador).
  La barra tiene la suya (`SuperficieBarra`, en `vistas/hilos.ts`).
- El dashboard (`vistas/hoy.ts`), la barra (`vistas/hilos.ts`), `modelo.ts`, `cli.ts`, `estilo.ts` y las
  acciones de tareas ya no importan VS Code. Lo que es solo de VS Code quedó aparte:
  `vistas/hilos-vscode.ts` (la vista lateral) y `vistas/tareas-barra.ts` (la lista de tareas lateral).
- `web/servidor.ts` (`npm run panel`, o `node out/web/servidor.js --puerto 8770 --host …`): sirve en `/`
  una página con la barra y el dashboard, cada uno en su marco, y conecta sus mensajes por WebSocket.
  Lo que el dashboard le pide a la interfaz se dibuja en la página (`web/pagina.ts`). Se entra con una
  llave (`~/.config/telar/panel.llave`): `?k=` la primera vez, después una cookie.

- **Las terminales** (16-oct): un clic en un hilo de la barra abre su terminal en una pestaña al lado
  del dashboard (xterm.js). El servidor corre `telar mirar <hilo>` en un PTY (node-pty): una sesión
  agrupada fija en la ventana del hilo, como las de las otras máquinas y el celular. Escribir ahí es
  escribir en el hilo sin mover lo que ven los demás; cerrar la pestaña borra la vista. En macOS,
  node-pty necesita `chmod +x` a su `spawn-helper` (lo hace el `postinstall`); en Linux se compila.

Lo que falta: `telar panel` como orden y como servicio (launchd en el laptop, systemd en el servidor),
correrlo en el servidor por Tailscale para el celular, fusionar `telar web`, y lo que en la web todavía
es solo de VS Code (la ficha y la carpeta de la barra, el menú contextual de un hilo).

## Estado y plan (18-oct-2026)

Se tomó un atajo respecto de los pasos de arriba: el panel funciona **sin** `telar serve`. Es un
servidor Node (`web/servidor.ts`) que, por cada dato, abre un proceso `telar … --json`; por eso la
primera carga tarda unos 10 s. Así quedó cada pieza:

| pieza | estado |
|---|---|
| dashboard y barra sin VS Code (`anfitrion.ts`, `superficie.ts`) | hecho |
| panel web: barra, dashboard y terminales de los hilos (xterm.js sobre `telar mirar`) | hecho, a mano |
| CSS en archivos, tokens, capas, stylelint, `<dialog>` | hecho |
| `telar panel`, y el panel como servicio (launchd en el laptop, systemd en el servidor) | **paso 1**: la orden y las plantillas hechas (18-oct); corriendo en el laptop |
| el panel en el celular, por Tailscale | **paso 1**: en el servidor por Tailscale (`telar:8770`) desde el 18-oct, con vista angosta (abajo); el celular todavía tiene también `telar web` |
| la vista angosta (hasta 700 px) | hecha (18-oct): una cosa a la vez (la lista, y un toque abre el dashboard o un hilo, con «◀» y el atrás del teléfono); el hilo se lee como conversación (`/conversacion`: `telar hilo leer`, el markdown convertido) con una caja para escribirle y teclas ⏎ ⎋ 1 2 3 ↑ ↓, que van por la vista de la terminal (`/pty`) como un pegado; «terminal» abre la xterm igual. La tabla de tareas deja el código, el texto y debajo la fecha con ✓ ▶ ⋯ |
| (antes) retirar `telar web` | **paso 1**, después de que el panel sirva en un celular. `telar web` es una app para el celular (1.500 líneas): lee la conversación de un hilo por páginas, aprieta teclas en su terminal, deja lecturas, anota eventos, comenta el plan, abre hilos y atajos, y se instala como app. El panel hoy es de pantalla grande (marcos y xterm): le falta una vista angosta y leer la conversación en vez de la terminal |
| lo que en la web es solo de VS Code: la ficha y la carpeta de un hilo, su menú contextual | hecho (19-oct): ⋯ en cada hilo (y clic derecho) abre su menú: ver, renombrar, vincular (entre los proyectos o una ruta), desvincular, prioridad, archivar o desarchivar, cerrar, llevar a otra máquina, olvidar, y ver su carpeta y documento (`/documento`: la carpeta y el archivo elegido, markdown convertido, sin salir de la carpeta del hilo ni por un enlace simbólico) |
| menús y avisos donde se mira | hecho (19-oct): cada página dice cuánto se ve, y el servidor manda el menú o el aviso a la que se está mirando (en un celular, la lista y el dashboard no se ven a la vez) |
| comentar el plan | hecho (19-oct), en el núcleo: `[resultados.plan] comentar` y `telar resultado plan <día> --comentar`; se atiende donde vive el plan (por el bus). El dashboard lo ofrece abajo del plan, en VS Code y en la web |
| compartir desde el teléfono, e instalar el panel como app | hecho (19-oct): manifiesto, íconos y service worker; la hoja «compartir» del teléfono abre `/compartir`, que lleva el enlace o el texto a un hilo o a un proveedor que declara `recibir` (`telar compartir`). La lectura ya no pasa por una ruta fija de un repo. La dirección HTTPS es `https://<servidor>:8443` (`tailscale serve --https=8443`, 19-oct); la de siempre sigue en `telar web` hasta retirarlo |
| ver los hilos de la otra máquina en el panel | hecho (19-oct): la barra suma un grupo por cada máquina cuya foto llega aquí (`telar espejo ver`, cada 30 s) y que la lista no trae ya (en el laptop, los del servidor vienen de `[remotos]` y no se repiten). Un clic lee el hilo como conversación por el bus (`telar hilo leer --maquina`) y la caja le escribe como la persona (`telar mensaje --tipo persona`); sin terminal ni teclas, que no viajan por el bus |
| retirar `telar web` | hecho (19-oct): probado el panel en el celular, `https://<servidor>/` (y `:8443`) apunta al panel, `telar-web.service` apagado y su código fuera (`ordenes/web.py`, `telar/web/`, `webcal.py`, sus pruebas y sus rutas `/api/*` en los contratos). Queda un solo dashboard |
| `telar serve` | **paso 2, empezado (19-oct)**. Medido antes: abrir un proceso cuesta 0,07 s; lo lento era esperar la red (`hoy` bajaba el iCal entero cada vez: 4,5 s en el servidor, 63 s o más en el laptop con mala red; `config` esperaba 10 s a `gws`). Se hizo lo estándar: una API FastAPI con modelos Pydantic en un proceso que se queda (`telar serve`, en un socket Unix dentro de una carpeta solo para su dueño), y cada orden pasa a ser una cáscara de una función de `telar.servicios` que usan la CLI y la API: la lógica vive una vez y el modelo es el contrato. `hoy` es la primera: el calendario se guarda en una copia que vale 10 min, con tope total de descarga y la copia vieja si no hay red (y lo dice); la API lo refresca de fondo. El panel pide `/hoy` a la API y, si no corre, a la CLI. Medido: el dashboard con su agenda en 3,7 s (antes 63 s). Lo que queda de esos segundos: las tareas por el bus (1,5 s), el feed de lecturas (0,6 s) y `enrutar` (0,8 s, resuelve rutas 8.000 veces) |
| las demás órdenes a `telar.servicios` | hechas `hilos` (`GET /hilos`, 0,12 s) y `config` (`GET /config`, 0,03 s; la cuenta de `gws` se guarda 10 min en vez de preguntarse a cada lectura) el 19-oct; también `tarea` (`GET /tareas/{id}`, `POST /tareas/{id}/accion`), `bloque` (`GET /bloques/{clave}`, `…/items/{id}`, `POST …/abrir`) y `resultado` (`GET /resultados/{clave}`, `POST …/comentario`). El panel las pide a la API; si la API contesta con un error, ese es el error (una acción no se reintenta por la CLI: se correría dos veces), y solo si no hay API, o no tiene esa ruta, usa la CLI. Un error del servicio (`ErrorDeServicio`) es una queja en la CLI y su código HTTP en la API, con el mismo mensaje. Siguen las que escriben la configuración y el resto de las ~60 llamadas del panel |
| las primitivas (objetos con dirección, encargos, worktrees, permisos; ver `primitivas.md`) | **paso 3**; hecho solo `telar commit` |

**El orden y por qué.**

1. **El panel en todas partes.** Es corto y es lo que se usa a diario: que arranque solo, que el
   celular lo vea, y que haya un solo dashboard.
2. **`telar serve`.** Lo lento hoy es abrir un proceso por pedido, no el lenguaje. Se hace por
   partes, empezando por lo más pedido (`hilos`, `hoy`, los bloques). Si `telar serve` no corre, el
   panel vuelve a lanzar la CLI, así que cada parte se puede subir sola. Con él, los cambios se avisan
   por WebSocket en vez de preguntar cada pocos segundos.
3. **Las primitivas, encima de `telar serve`.** Hacerlas antes es escribirlas dos veces: para la CLI
   suelta y para la API que se queda corriendo. (`primitivas.md` las ponía antes; se corrigió.)

**Una decisión abierta: uno o dos procesos.** El panel en Node ya sirve la página y dibuja.
`telar serve` daría los datos. Hay dos caminos:

- **Dos procesos** (recomendado por ahora): Node sirve la página y Python los datos. Reusa todo lo que
  funciona.
- **Uno solo**: `telar serve` sirve también la página, y la lógica del dashboard (TypeScript) pasa al
  navegador. Más limpio a la larga, pero es una reescritura.

Se parte con dos, y se fusionan si molesta.

## El estado final (19-oct-2026)

Decidido: **un solo proceso de telar por máquina**, el mismo código en las dos, y NATS entre ellas. Los
agentes siguen corriendo en las dos máquinas (el laptop tiene lo que solo él puede hacer: Chrome,
archivos locales), así que el bus se queda: es la pieza estándar entre máquinas, y su cola durable es
justo lo que hace falta cuando el laptop está cerrado.

En cada máquina, ese proceso (Python) tiene:

- **la API** (FastAPI, modelos Pydantic de `telar.servicios`) y **la página** (archivos estáticos que se
  dibujan en el navegador);
- **las terminales** de sus hilos (PTY por WebSocket, sobre `telar mirar`);
- **la conexión al bus**: lo que hace hoy `telar nodo` (recibir mensajes, avisar a los hilos, publicar el
  estado), como una tarea del mismo proceso;
- **las tareas de fondo**: refrescar el calendario, la foto del estado.

Lo que cambia entre máquinas es configuración: el servidor tiene el calendario, las tareas, los
periódicos y las rutas de quien colabora (hoy `telar-equipo`); el laptop, sus hilos y sus terminales.

| hoy | al final |
|---|---|
| `telar-panel` (Node) | parte del proceso único, cuando las vistas se dibujen en el navegador |
| `telar-serve` | es el proceso único |
| `telar-nodo` | una tarea del proceso único |
| `telar-equipo` | rutas del mismo servidor, con su llave |
| espejo por ssh, la puerta (`enlace`), el correo entre agentes | ya los reemplazó el bus: sale su código |
| `telar-bus` (NATS) | se queda: el broker entre máquinas |

En el servidor quedan telar, NATS, tmux y cron; en el laptop, telar y tmux.

**El orden.**

1. **Las órdenes a `telar.servicios`**, con su ruta en la API (unas 60 llamadas del panel). Hechas `hoy`,
   `hilos`, `config`, `tarea`, `bloque` y `resultado`; siguen las que escriben y el resto.
2. **El nodo, adentro del proceso único**: ya es Python, asyncio y NATS; una máquina queda con un
   proceso menos al tiro.
3. **Las vistas, al navegador**: `cli.ts` llama a la API en vez de abrir procesos; `hoy.ts` e
   `hilos.ts` casi no cambian, porque ya hablan por `anfitrion` y `superficie`.
4. **Las terminales, a Python**, y se retira Node.
5. **`telar-equipo`, como rutas**, y sale el código muerto.

