# El dashboard fuera de VS Code

Propuesta, 16-oct-2026. Estado: **la barra y el dashboard ya corren en el navegador** (`npm run panel`
en `vscode/`, ver «Lo hecho» al final); falta el servicio, el celular y fusionar `telar web`.

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
