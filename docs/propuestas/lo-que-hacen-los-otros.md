# Lo que hacen los otros: ideas por decidir

Estado: **ideas sueltas, cada una por decidir**. Las que ya se adoptaron (el estado que no miente, «quién
me espera») son parte de telar. Los avisos al celular, descartados por ahora (16-oct-2026).

Salen de leer el código de nueve administradores de agentes (OpenHarness, herdr y Roamgate, Agent of
Empires, claude-squad, happy, Vibe Kanban, cmux, CLI Agent Orchestrator, octomux). La arquitectura de
telar es la que eligieron los más serios: un proceso por máquina, los agentes en tmux, la ventana como
visor y los ganchos del agente como fuente de su estado. Lo que se puede aprender está en la solidez del
estado y en la atención de la persona.

Varias de estas ideas se resuelven mejor con el mod de Claude Code ([telar-para-otros.md](telar-para-otros.md)):
lo dicen donde corresponde.

## Por decidir

1. **No avisar «terminó» si quedó una pregunta abierta** (OpenHarness `lib/agentNotifications.ts`).
2. **Mensajes entre hilos sin teclear.** Hoy a un hilo ocioso se le teclea «↯», que puede caer sobre lo
   que la persona escribe. Con el mod, el mensaje entra por `session.receive` y esto sobra. Sin él:
   - entregar por gancho exactamente una vez (OpenHarness `engines/kit/messagesHook.ts`: reclama cada
     mensaje y lo inyecta como `additionalContext` en `PostToolUse`);
   - despertar con un `Stop` `async: true, asyncRewake: true` que sale con código 2 (cmux
     `docs/agent-messages.md`);
   - mientras quede el tecleo, no escribir si la línea del prompt tiene texto o hay un diálogo abierto
     (cmux `surface.input_state`);
   - estados por mensaje (en cola, entregado, leído, falló) y un barrido de lo pendiente cada 30 s (CAO
     `docs/inbox-delivery.md`).
3. **Responder permisos desde fuera de la terminal.** Un gancho `PermissionRequest` (o `tool.check` en
   el mod) que publica el pedido en el bus y espera hasta ~120 s una respuesta de la página; si no llega,
   queda el diálogo de siempre (cmux `docs/feed.md`, happy `permissionHandler.ts`). Lo benigno con un
   toque, lo destructivo manteniendo presionado (Agent of Empires `ApprovalCard.tsx`).
4. **La conversación por eventos, no leída cada pocos segundos.** Las vistas de lectura y conversación
   piden `/api/hilos/leer` cada 3 s. Mejor: el transcript como eventos chicos por el bus (texto, inicio y
   fin de herramienta, inicio y fin de turno; happy `sessionProtocol.ts`), o del mod.
5. **Módulos más completos** (OpenHarness `cli/src/dsh/manifest.ts`): instrucciones y skills del agente,
   un `doctor` que revisa lo necesario, y un `verdict.json` (listo, fases, resultado) que la página lee.
6. **Tareas y periódicos.**
   - Cada ▶ queda como un intento en la tarea, con el resumen final del agente y una marca de no leído
     (Vibe Kanban `CodingAgentTurn`).
   - El estado de la tarea (cambia por hechos) separado de la atención del agente.
   - Un `Stop` como compuerta: un hilo que trabaja una tarea no cierra el turno sin anotar su avance.
   - Un chequeo previo para los periódicos (CAO `flow_service.py`: un script devuelve `execute:
     true/false`), para no gastar un agente cuando no hay nada que hacer.
7. **Para repos de código**: comentarios sobre un diff que se mandan al agente como un solo prompt (Vibe
   Kanban `ReviewProvider.tsx`). Los worktrees por hilo están en [primitivas.md](primitivas.md), con el
   candado contra `prune` de Agent of Empires (`src/git/worktree/`).

## Qué no copiar

- Un relay propio con cifrado de punta a punta: Tailscale ya lo resuelve.
- Regex sobre la pantalla como fuente principal del estado: frágil con cada versión del agente.
- Aprobar o commitear todo automáticamente.
- Correr el agente sin su interfaz (`-p --output-format=stream-json`, o ACP): se pierde la terminal.
- Reemplazar tmux por un servidor de terminales propio.
- Un backend pesado (Vibe Kanban pasó a Postgres remoto y anunció su cierre).

Código leído con `git clone --depth 1` el 16-oct-2026: `autonomous-ai/openharness`, `herdrdev/herdr`,
`powerfooI/roamgate`, `agent-of-empires/agent-of-empires`, `smtg-ai/claude-squad`, `slopus/happy`,
`BloopAI/vibe-kanban`, `manaflow-ai/cmux`, `awslabs/cli-agent-orchestrator`, octomux.
