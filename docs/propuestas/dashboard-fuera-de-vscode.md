# El dashboard fuera de VS Code

Propuesta, 16-oct-2026. Estado: **por hacer**; es el camino para que el dashboard pueda vivir en el
navegador (y en el celular, y en una app propia) sin dejar de verse en VS Code mientras tanto.

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
