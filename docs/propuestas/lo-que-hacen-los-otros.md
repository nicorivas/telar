# Lo que hacen los otros: qué aprender de otros administradores de agentes

Propuesta, 16-oct-2026. Estado: **el bloque 1 hecho**, y las dos primeras ideas del 2; los avisos al
celular, descartados por ahora (Nico, 16-oct); lo demás, por decidir.

## Por qué

En 2026 aparecieron decenas de programas para operar varios agentes de código a la vez. Se leyó el
código de nueve: OpenHarness, herdr (y su cliente Roamgate), Agent of Empires, claude-squad, happy,
Vibe Kanban, cmux, CLI Agent Orchestrator (AWS) y octomux. La pregunta era qué hacen mejor que telar
y qué no conviene copiar.

La primera respuesta es que la arquitectura de telar es la que eligieron los más serios: un proceso
por máquina, los agentes dentro de tmux, la ventana como un simple visor y los hooks del agente como
fuente principal de su estado. Lo que telar tiene y casi nadie hace: mensajes entre hilos, agentes
residentes con memoria, procesos periódicos propios y un dashboard que no es solo de código. Lo que
se puede aprender está en la solidez del estado y en la atención de la persona.

## Dónde corren

| dónde | quiénes |
| --- | --- |
| app de escritorio nativa | OpenHarness (Flutter), cmux (terminal propia, sobre Ghostty), Conductor, la app de escritorio de Claude Code |
| terminal (TUI) | claude-squad, herdr, Agent of Empires |
| web local o PWA | Vibe Kanban, Agent of Empires (web pensada para el celular), Roamgate, octomux |
| app móvil | happy, Nimbalyst, Remote Control de Anthropic (en la app de Claude) |

Ninguno vive en VS Code: los agentes corren en la terminal y la interfaz es nativa o web. Ver
`dashboard-fuera-de-vscode.md`.

## Qué adoptar

### 1. Que el estado no mienta (hecho)

- **`Notification` no es siempre «espera»** (Agent of Empires solo marca waiting con `permission_prompt`
  o `elicitation_dialog`): el aviso de ocioso (`idle_prompt`) llega un minuto después de cada turno y
  dejaba todo hilo terminado en «espera». Ahora es «terminó».
- **`StopFailure`** (OpenHarness `cli/src/engines/claude/hookContract.ts`; Agent of Empires
  `src/hooks/json_settings.rs`): cuando un turno termina por un error de la API, Claude Code no
  dispara `Stop`, y el hilo queda «trabajando» para siempre. Se engancha como un `termina` más.
- **`UserPromptSubmit` repara un `SessionStart` perdido** (OpenHarness): si el hilo no tiene anotada
  la conversación que trae el aviso, se anota ahí.
- **Un aviso viejo no pisa a uno nuevo** (herdr manda un `--seq` monótono): la atención se escribe
  con la hora del aviso, y un aviso con hora anterior a la anotada no se aplica.
- **Volver a abrir lo que se cayó** (herdr `src/agent_resume.rs`): si tmux muere, los hilos que
  estaban vivos se retoman con su conversación (`claude --resume`): el nodo anota cada 30 s quién está
  vivo, y `telar hilo caidos` los reabre de una vez. Un hilo se anuncia muerto solo si falta dos
  vueltas seguidas (OpenHarness: dos escaneos).

### 2. «Quién me espera» (las dos primeras, hechas)

- **Terminó y no lo viste ≠ terminó y ya lo viste** (herdr: `done` es idle no visto y se limpia con
  el foco; Vibe Kanban: `seen` por turno). telar ya guarda `visto`: «terminó» con el foco anterior al
  fin del turno es «te espera» (`sin_ver` en `telar hilos --json`; la barra apaga el «terminó» ya visto).
- **Una tecla que salta al siguiente que te espera** (OpenHarness ⇧⌘I): primero los que piden algo,
  después los que terminaron sin que los vieras, el más antiguo primero. En VS Code, ⌥S.
- *(Descartado por ahora, 16-oct.)* **Avisos al celular solo en la transición desde «trabajando»**, sin contenido (Roamgate
  `server/src/notifications/task-events.ts`; happy manda solo el nombre de la sesión). Con ntfy
  bastaría una línea en el hook. Falta decidir el servidor de ntfy (el público o uno propio).
- **No avisar «terminó» si quedó una pregunta abierta** (OpenHarness `lib/agentNotifications.ts`).

### 3. Mensajes entre hilos sin teclear

Hoy, a un hilo ocioso se le escribe una línea con `send-keys` para despertarlo; puede caer sobre lo
que la persona está escribiendo.

- **Entregar por hook, exactamente una vez** (OpenHarness `engines/kit/messagesHook.ts`: reclama cada
  mensaje renombrándolo a `claimed/` y lo inyecta como `additionalContext` en `PostToolUse`).
- **Despertar sin teclear** (cmux `docs/agent-messages.md`): un hook `Stop` con `async: true,
  asyncRewake: true` espera mensajes y sale con código 2, lo que despierta a la sesión ociosa con el
  texto como recordatorio del sistema. Claude Code 2.1.302 lo conoce (`asyncRewake`, igual que
  `StopFailure` y `PermissionRequest`).
- **Mientras quede `send-keys`, no escribir sobre un borrador** (cmux `surface.input_state`): leer el
  panel y no escribir si la línea del prompt tiene texto o hay un diálogo abierto.
- **Estados por mensaje** (en cola, entregado, leído, fallido) y **un barrido** cada 30 s de lo que
  quedó pendiente (CLI Agent Orchestrator `docs/inbox-delivery.md`).

### 4. Responder permisos desde fuera de la terminal

- **Un hook `PermissionRequest` que espera la respuesta** (cmux `docs/feed.md`, happy
  `claude/utils/permissionHandler.ts`): publica el pedido en el bus y espera hasta ~120 s una
  respuesta del dashboard o del celular; si no llega, queda el diálogo de siempre.
- **Lo benigno con un toque, lo destructivo manteniendo presionado** (Agent of Empires
  `web/src/components/acp/ApprovalCard.tsx`). Opciones como las de happy: sí, sí a todas las
  ediciones, permitir esta herramienta, denegar.

### 5. El celular con la conversación, no con una foto

Leer el transcript de Claude Code a medida que crece y mandarlo por el bus con un esquema chico de
eventos (happy `packages/happy-wire/src/sessionProtocol.ts`: texto, inicio y fin de herramienta,
inicio y fin de turno). Reemplaza la foto de la terminal cada 2 s de `telar web`.

### 6. Módulos más completos

El manifiesto de OpenHarness (`cli/src/dsh/manifest.ts`) confirma el diseño de `modulo.toml` y suma:
las instrucciones y skills del agente, un `doctor` que revisa que lo necesario esté instalado, y un
`verdict.json` (listo, fases, resultado) que la interfaz lee sin depender del agente.

### 7. Tareas y periódicos

- **Cada ▶ queda como un intento en la tarea**, con el resumen final del agente y una marca de no
  leído (Vibe Kanban `CodingAgentTurn`: `prompt`, `summary`, `seen`).
- **Separar el estado de la tarea de la atención del agente**: la tarea cambia por hechos (se abrió,
  se entregó), y trabajando/espera/terminó es otra capa.
- **Un hook `Stop` como compuerta** (Vibe Kanban bloquea el cierre si hay cambios sin commitear): en
  telar, que un hilo que trabaja una tarea no cierre el turno sin anotar su avance.
- **Un chequeo previo para los periódicos** (CLI Agent Orchestrator `services/flow_service.py`: un
  script devuelve `execute: true/false`), para no gastar un agente cuando no hay nada que hacer.

### 8. Para repos de código

Un worktree opcional por hilo, con candado para que otro `prune` no lo borre (Agent of Empires
`src/git/worktree/`), y comentarios sobre un diff que se mandan al agente como un solo prompt (Vibe
Kanban `ReviewProvider.tsx`).

## Qué no copiar

- Un relay propio con cifrado de punta a punta (OpenHarness, happy): Tailscale ya lo resuelve.
- Regex sobre la pantalla como fuente principal del estado (CLI Agent Orchestrator, herdr): frágiles
  con cada versión del agente. Sirven, a lo más, para corregir lo que dicen los hooks.
- Aprobar todo automáticamente (claude-squad), commitear automáticamente (Vibe Kanban, claude-squad).
- Correr el agente sin su interfaz (`-p --output-format=stream-json`, o ACP): se pierde la terminal.
- Reemplazar tmux por un servidor de terminales propio (herdr).
- Un backend pesado: Vibe Kanban pasó a un backend remoto con Postgres y anunció su cierre.

## Fuentes

Código leído con `git clone --depth 1` el 16-oct-2026: `autonomous-ai/openharness`,
`herdrdev/herdr`, `powerfooI/roamgate`, `agent-of-empires/agent-of-empires`, `smtg-ai/claude-squad`,
`slopus/happy`, `BloopAI/vibe-kanban`, `manaflow-ai/cmux`, `awslabs/cli-agent-orchestrator`, octomux.
