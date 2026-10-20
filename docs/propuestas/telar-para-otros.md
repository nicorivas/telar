# telar para otros: primero un equipo, después cualquiera

Estado: **propuesta, por empezar**. Es el plan maestro: el orden está al final. Decidido: la extensión de VS
Code se depreca (20-oct-2026).

Hoy telar funciona bien para una persona con dos máquinas (un laptop y un servidor) unidas por un bus y
por Tailscale, y con la configuración armada a mano por esa misma persona. Esta propuesta dice qué falta para
que lo use un equipo de trabajo, después cualquiera, y qué queda de las versiones anteriores que conviene
retirar en el camino.

## Lo que bloquea a un equipo: la seguridad entre personas

Hecho: una cuenta del bus por persona, que el servidor NATS hace cumplir; con ella, el reenvío de
terminales y los boletos de `/maquinas` solo valen entre máquinas de la misma persona
([arquitectura](../arquitectura.md), «Entre máquinas: el bus»). Lo que falta para hablarse entre personas:

1. **El correo entre personas y el directorio por el bus.** Hoy van por el servidor: `telar correo enviar` a
   otro usuario, el `cartero` y Postfix, la lista de permitidos de `telar persona --correo`, y `telar
   directorio` (`<servidor>/directorio/<usuario>.json`, la única forma de ver los hilos de otra persona).
   Con un servicio que cada cuenta exporte (su casilla) y las demás importen, se retiran el `cartero`, Postfix y la casilla común. Antes de
   desinstalar Postfix: la salida de cron de `telar periodicos` llega por correo (poner `MAILTO=""` o
   mandarla a un log; con `always_bcc` a una casilla común, la lee todo el grupo). `enlace archivo` y
   `enlace notificar` no tienen pedido en el bus: portarlos al nodo o aceptar perderlos. Es irreversible y
   afecta a las otras personas del servidor: se decide con ellas.
2. **Más de una máquina siempre prendida**, en clúster (NATS de tres), si el equipo crece: hoy el servidor es
   un punto único de falla.

## Lo que falta para que alguien lo instale solo

- **`telar instalar`**, un solo comando para la primera vez: la configuración (lo que hoy hace `telar init`),
  los servicios (`launchd` en macOS, `systemd --user` en Linux; hoy son plantillas en `servidor/` que se
  copian a mano), la llave de la página, unirse al bus si hay uno, la skill y el mod de Claude Code (abajo),
  y al final `telar doctor`. Que se pueda correr de nuevo sin romper nada.
- **Publicar una versión.** La última en PyPI es la 0.1.13; desde entonces hay más de cien cambios sin
  publicar (el bus, la página sin Node, las terminales, los tipos). Corresponde una 0.2.0, con el flujo de
  [publicar.md](../publicar.md).
- **Pedir tmux 3.5 o más.** La 3.4 se cae sola (un segfault del servidor de tmux, que se lleva todos los hilos);
  `telar doctor` debería avisarlo.
- **Un día que funcione con la configuración de fábrica.** El dashboard rinde con los proveedores de quien lo
  armó (sus tareas, su calendario). Una persona nueva necesita un proveedor de tareas por defecto (una
  carpeta de markdown, que el tipo `tarea` ya sabe leer y escribir) y una guía de su primera hora. Los
  ejemplos de la documentación y de algunos docstrings todavía traen rutas de la configuración del autor.

## Un mod de Claude Code dentro de telar

Desde Claude Code 2.1.287, un *mod* es un plugin con un módulo en JavaScript que corre adentro de Claude Code:
reacciona a eventos (empieza o termina un turno, una herramienta está por correr, llega un mensaje), puede
cambiar prompts y decidir sobre herramientas, dibuja paneles o una franja sobre el prompt, y registra comandos
que corren sin gastar un turno ([referencia](https://code.claude.com/docs/en/plugins/mods/reference)).

telar lo puede llevar adentro: una carpeta con `.claude-plugin/plugin.json`, `hooks/hooks.json` y el módulo,
como parte del paquete. Como telar lanza cada hilo, le basta agregar `--plugin-dir <esa carpeta>`; para las
sesiones que no lanza, `telar instalar` la pone en `CLAUDE_CODE_PLUGIN_DIRS` (en el `env` de
`~/.claude/settings.json`). El mod viaja con la versión de telar.

Lo que reemplazaría, de lo que hoy es frágil, en este orden:

1. **El semáforo de cada hilo**, de los eventos (`turn.start`, `turn.complete`, `tool.check` cuando queda
   esperando un permiso) en vez de deducirlo de los hooks y de la pantalla.
2. **La casilla**: un mensaje entra apenas llega si el agente espera (`session.receive`, `$.prompt.submit`), en
   vez de esperar al final del turno por el hook Stop.
3. **El modo lectura**: la respuesta final de los mensajes ya estructurados, en vez de leer el registro
   JSONL de Claude Code.
4. **Una franja de telar sobre el prompt** (quién espera, los mensajes pendientes) y comandos `/telar …`
   instantáneos.

Es JavaScript en un proyecto de Python, y el mod tiene los mismos poderes que telar (archivos, procesos,
red); `claude plugin validate` y `claude plugin test` lo revisan en el CI.

## Vestigios de versiones anteriores

- **La extensión de VS Code, deprecada (decidido el 20-oct-2026).** VS Code no aporta nada propio: se usaba
  como sustento de la barra, el dashboard y las terminales, no como editor, y hoy la página hace todo eso.
  Lo que queda de ella es un vestigio: el dashboard (`vistas/hoy.ts`, unas 2.500 líneas) corre en el navegador
  con un `acquireVsCodeApi` simulado, cada pantalla en un iframe y mensajes que van y vuelven entre marcos. El
  retiro: avisar en la extensión y en el CHANGELOG que está deprecada (y dejar de publicarla en el Marketplace
  y Open VSX), mover el código que comparte con la página a la página, escribir la página para el navegador
  sin la capa del webview (anfitrión, superficies, `acquireVsCodeApi`), y borrar lo que es solo de VS Code
  (`extension.ts`, `anfitrion-vscode.ts`, las vistas laterales). `vscode/` pasa a ser el código de la página.
- **El correo entre personas y los remotos por ssh y mosh** (`remoto.py`, `movil.py`, `correo.py`,
  `espejo.py`, el `cartero`; unas mil líneas): se van cuando el bus cruce personas (el punto 3 de arriba).
  Quien use dos máquinas sin bus queda sin semáforo ni ventanas remotas: el CHANGELOG lo dice, con el bus
  como requisito para dos máquinas.
- **El puente `en_proceso`**: algunas órdenes (`hilo llevar`, las acciones del perfil) todavía corren la CLI
  por dentro y leen su salida, en vez de ser servicios.
- **Claves viejas que se aceptan sin usarse** en `config.py` (`[enlace] no_leer`, `correo_archivo`): avisar
  primero y retirarlas en una versión.
- **zellij**: un segundo multiplexor que se mantiene sin uso. Decidir si sigue.

## Funcionalidades que faltan para cualquiera

- **Otros asistentes, en serio.** Hoy todo supone Claude Code (sus hooks, su registro, ahora el mod). Hace
  falta una interfaz de adaptador por asistente —su estado, sus mensajes, su conversación— y que Claude Code
  sea un adaptador más. El registro de vistas de un hilo (`vscode/src/web/vistas-hilo.ts`) y los
  renderizadores de la lectura ya van por ahí.
- **Varias personas en una máquina**, cada una con su acceso: hoy la página tiene una llave por máquina; falta
  entrar como persona y poder rotar la llave.
- **Inglés**: la CLI y casi toda la documentación están en español (el README, en inglés).
- **Pruebas de la página**: el CI prueba el Python; de la página solo está la prueba del eco
  (`npm run prueba:eco`).

## El orden

1. El correo y el directorio entre personas por el bus (las cuentas por persona ya están).
2. `telar instalar` y la 0.2.0.
3. El mod de Claude Code: el semáforo y la casilla.
4. Deprecar la extensión de VS Code y escribir la página para el navegador, sin la capa del webview.
5. Para cualquiera: inglés, la configuración de fábrica, otros asistentes.
