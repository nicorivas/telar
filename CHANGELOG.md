# Changelog

Versions follow [semantic versioning](https://semver.org). The Python package and the
VS Code extension share a version number: a tag `v0.1.0` releases both, and the release
workflow refuses to run if the two disagree.

## [Unreleased]

### Added

- `[agentes] carpeta`: resident agents, one per folder with a `CLAUDE.md`. They show in the thread list under an
  «Agentes» header, each one collapsible with a home and its threads; the home (`telar seccion agente:<folder>`)
  is built by telar from its `CLAUDE.md`, `bitacora.md` and `memoria/MEMORY.md`, with an optional `home` command on
  top. A thread linked to an agent's folder starts its agent there, so it loads that `CLAUDE.md` from the start.
- `telar encargar <agent> "…"`: ask a resident agent for something in its one long-lived thread instead of opening a
  new session — typed in if it is idle, queued if it is working (the `Stop` hook hands it the next one), or its
  session reopened resuming its conversation, or a fresh one once that conversation is over `[agentes] rotar_mb`.
  `[agentes.<folder>] argumentos` are passed to the agent when its session opens. A periodic process with
  `agente = "<folder>"` and a `mensaje` is an encargo.
- An `[atajos.<key>]` with `agente = "<folder>"` hands its message to that resident agent instead of opening a new
  thread, and takes you to the agent's thread. `[agentes] en` (or `telar encargar --en`) makes encargos on that
  remote machine, over ssh, where the agents live.
- `telar pendiente` (the «trabajar en un hilo» of a task, or ⌘-click): a project thread that is asleep (archived or
  without a window) is **resumed** with its conversation and the task as first message — here or on the machine
  where it lives — instead of reopening its name with a new conversation; a task with no project goes, with
  `[agentes] sin_proyecto = "<folder>"`, to that resident agent as an encargo instead of a new thread.
- `[agente] max_vivos`: a cap on live own sessions (periodic, encargos, the phone) on a machine; before opening one,
  telar closes the idle ones nobody is looking at, oldest first, residents last. Their conversations stay on disk.
- `telar remotos traer` closes local windows whose remote session no longer exists (closed by `max_vivos` or from
  the phone): they showed a frozen screen and counted as alive. The thread keeps its conversation and ▶ resumes it.
  Nothing is closed when the other machine does not answer.
- Agents learn the basics: the start-up context names `telar hilo leer` and the resident agents with
  `telar encargar`, and the `/hilos` skill explains both.

## [0.1.11] — 2026-10-05

### Added

- `telar periodicos`: the processes that run on their own, defined in `periodicos.toml` next to `config.toml` on
  the machine that runs them — each with a cron schedule and either a shell command or a prompt that opens a
  thread with the agent (like a remote thread, so other machines pick it up), with `max_abiertos`. `aplicar` writes
  a marked block in the crontab and never touches lines outside it; `correr` records the last run and a capped log;
  `nuevo`, `editar`, `pausar`, `activar`, `borrar`, `zona`, `ahora` and `log`. With `[periodicos] en` another machine
  sees and changes them over ssh.
- VS Code: a «periódicos» tab in the dashboard (key `o`): each process with its schedule, next and last run and how
  it went; its card with the log and run now, pause or resume, edit and delete. `+` and edit open a form in the tab:
  prompt or shell command, a searchable list of the skills available where it runs (picking one makes it the
  prompt), schedule presets with a live preview of the next runs (or why the expression is wrong), the thread's
  name, how many may stay open, the agent's arguments, folder and active. Errors stay in the form with what was
  typed. `telar periodicos horario` and `telar periodicos skills` back it.
- `telar web`: installable on the phone as a PWA when served over https (`tailscale serve`): icon, manifest and a
  service worker that caches nothing; an https `Origin` is accepted only for a host declared with `--tambien`.
- `telar web`: the reply box grows to six lines (Enter is a new line on the phone, sends with a keyboard) and a large
  «enviar» button; tapping a thread that has a conversation goes straight into it.
- `telar web --plan CARPETA`: a «plan» tab that draws the day's plan (`AAAA-MM-DD.json`, or `.md`) as cards — summary,
  results, agenda with each meeting's context folded, pending items, focus, people, missing data. With
  `--plan-comando CMD` a comment box at the end sends the comment to that command on stdin (never on the command
  line), with the same defences as `/api/enviar`, one comment every five seconds and 4,000 characters at most. The
  bottom bar is only the tabs now; theme and refresh moved to a ⋮ menu.
- Threads with their own session (opened from the phone or by a periodic process, `telar-…` sessions) count as
  `propio`: they can be written to (`enviar`, the web) even though they are not tabs.

### Fixed

- `telar web`: a reply box opened by a direct reload stayed read-only; two polls in flight duplicated the last message.
- Calendar: monthly series with an ordinal BYDAY (`1MO`, `-1FR`) fell on the start date's day of the month instead of
  the weekday.

## [0.1.10] — 2026-10-02

### Added

- VS Code: a ✓ on hover in each task row (sidebar and dashboard) marks it done without opening its card. It runs
  the action the provider declares with `"rol": "hecha"`.
- A task action's `mensaje` also takes `{texto}`, so an action can open a new session on the task with what was
  just typed in its card as the first prompt.
- `telar hilo leer [thread] [--ultimos N]`: the last N turns of a thread's conversation (5 by default, 50 at
  most) as readable text — what was asked, what the agent answered, one line per tool call and never its
  output — with per-message and total caps; the pane's scrollback when there is no conversation here.
  `--json` is the contract.
- `telar enlace leer <thread> [--ultimos N]`: the same, as a sixth door verb. **Off by default**: add `"leer"`
  to `[enlace] verbos`; `[enlace] no_leer` keeps threads out by name or linked folder (glob), and a vetoed
  thread answers like a missing one.
- `telar movil --hoy`: prints the day once (for testing).
- `telar movil`: `h` shows the day on one phone-sized screen — agenda, who is waiting for you, pending
  items, time — from `telar hoy --json`, with the text wrapped instead of cut. Tapping (or ⏎ on) a thread
  that is waiting enters it.
- `servidor/telar-web.service`: `telar web` as a systemd user service that starts at boot (with `loginctl
  enable-linger`), waits for Tailscale to have an IP before listening (so it never falls back to localhost) and
  restarts itself if it dies. See servidor/README.md.
- `telar web`: read a **laptop** thread's conversation too — `GET /api/conversacion?maquina=…` asks the door's
  `leer` verb and returns the same shape, so it is the same screen (with «… N turnos anteriores» instead of
  «anteriores», refreshed every 5 s, and the prompt addressing that machine). Nothing conversed is stored on the
  server; a vetoed thread, a disabled verb or an off laptop show their reason.
- `conversacion.py` is now the only reader of a thread's messages: the web, `telar hilo leer` and the door's
  `leer` (via `historia.py`, which keeps building the turns) share one rule for which conversation is the
  thread's (the first of its own with a file), id validation and the cache. `historia.leer` no longer needs the
  agent to be named in the configuration, like `telar agente conversacion`.
- `telar web`: read a thread's conversation from the page. Open a thread's detail and tap «ver la conversación»: the last
  messages, «… N anteriores» to go back, new ones every 3 s, markdown (code blocks, lists, headings, bold) drawn
  as terminal blocks, tool calls as one dim line each. With `--escribir` a prompt at the bottom answers it. It is
  served in pages by `GET /api/conversacion`, by thread (never by bare id), read-only.
- `telar web --escribir`: write to a live thread from the page, on this machine or on the laptop (through
  `telar enlace`), with a prompt and a `↩ enviar` button in the thread's detail. Off by default; the single
  writing route, `POST /api/enviar`, requires a custom header, the server's own `Host` and `Origin`, size and rate
  limits, and logs every send (never the text) to `web.log`.
- `telar espejo traer`: the server asks the laptop for its photo through the door; `telar web` does it every
  30 s when `[enlaces]` exists, so the mirror stays current with VS Code closed.
- `telar enlace`: a door from the server to the laptop with a single key. sshd ties the key to one command
  (`telar enlace servir`, with `restrict`), and `servir` does five things with size limits — `ping`, `hilos`,
  `archivo` (lands in an input folder, never overwrites or escapes it), `enviar` (types into a live thread) and
  `notificar` — and nothing else: no shell, no commands, no file reads. `telar enlace instalar` makes the key,
  `autorizar`/`revocar` (on the laptop) manage the `authorized_keys` line, and every request is logged.
  Configured with `[enlaces.<n>]` on the caller and `[enlace]` on the callee. See docs/configuracion.md.
- `telar espejo`: see the laptop's threads from the server. The laptop pushes a photo of its threads
  (`telar espejo publicar`, once or `--cada N`; the VS Code extension does it every 30 s with the new
  `telar.espejo` setting) and the server keeps it with the time it arrived (`recibir`, `ver`). `telar web`
  shows it as a section per machine — green «en línea», or greyed out with «apagado · hace 3 h» — and adds
  the ones that are waiting to «te esperan». Only names, semaphores and folders travel, no conversation.
  Read-only. See docs/configuracion.md and docs/contratos.md.
- `telar web`: telar in the phone's browser over Tailscale, looking like the VS Code dashboard: a terminal
  with colour (monospace, ANSI palette, sections with a colour bar, keys in inverse video, a tmux-style bottom
  bar, dark and light). Two screens for now — today (agenda, who is waiting, pending by urgency) and threads,
  with a tap to open a row's detail as a tree — read from `telar hoy --json` and `telar hilos --json`, so
  nothing is computed twice. It listens on one interface (Tailscale's, or localhost), only reads, keeps the
  day fresh in the background and reloads the open page when its files change, so editing the interface and
  seeing it on the phone takes seconds. Bundles JetBrains Mono (OFL) — see NOTICE.

### Fixed

- VS Code: clicking a task while the dashboard is hidden behind another tab now brings it to the front.
- Resuming a remote thread failed with «No conversation found» when `/resume` inside it had switched to another
  conversation: `telar hilo retomar` now asks the other machine which of the thread's conversations has a file
  there, the one its own hooks recorded first.
- An `[enlace]` table without `entrada` failed to load (`Puerta.entrada` is a slot, not the default).

## [0.1.9] — 2026-09-29

### Added

- `telar movil`: `n` opens a new thread on the server, with its agent, the same way `telar ir
  --remoto` does from the laptop, and enters it.
- `telar hilo llevar --sesion ID`: move a conversation telar has not recorded, as a way out
  when the hooks missed it.

### Changed

- A thread's label puts the client first: when the title already names the client («Reporting
  with AI — Acme», «… for Acme», even written slightly differently or with a note in
  parentheses), it is taken out of the title instead of dropping the client.

### Fixed

- `telar movil`: Alt+q returns to the thread list. Tapping «◀ telar» never reached tmux from
  Termux over mosh, and F12 is not on a phone keyboard; the bar now shows the key.
- Closing a thread no longer erases what telar knows under its name when another live
  window has the same name: closing a duplicate had left the live one without its
  conversation. `telar doctor` warns about live threads sharing a name.

## [0.1.8] — 2026-09-27

### Added

- A **skills** tab in the thread card: the skills the thread's agent has at hand (from its
  folder and the ones above, from subfolders when working there, the user's and enabled
  plugins'), with their description, and which ones its conversation used and how many
  times. `telar agente skills [--hilo H] [--json]` gives the same. A click opens the skill.

### Changed

- A provider tab opens straight on its first item instead of a list; ⎋ goes back to today.
  The provider can give it a key (`tecla`), checked against the dashboard's keys and the
  shortcuts.
- Cards are fetched ahead: opening a tab or a card loads the next ones in the list (up to
  ten, four at a time) and keeps them for five minutes, so → shows the next card at once even
  when the provider is slow or far away. A card is fetched again after an action on it.

## [0.1.7] — 2026-09-27

### Added

- A provider can declare `pestana`: its items are not tasks but something else (a reading
  feed, a review queue), stay out of today's list and get their own dashboard tab, with
  the same cards, ← → navigation and actions. After an action that runs a command, the
  card moves on to the next item. A task can carry a `color` for its `avance` word.
- `[proveedores.<nombre>] como = "<clase>"`: two providers of the same kind can live side by
  side under different names (a second `tareas` provider for a feed).

### Fixed

- A card's long subtitle wraps instead of running off the panel.

## [0.1.6] — 2026-09-26

### Added

- A task can carry an `area` (work, personal, whatever the provider uses). When there is
  more than one, the task lists in today, the review tab and the sidebar get a filter by
  area, remembered per view.

### Changed

- The sidebar's task list fits its width: the modes are icons with their count (◆
  proposals, ▲ urgent, ≡ all) and the areas are shortened to three letters, with the full
  word in the tooltip.
- The selected mode, order or area is shown by colour only; the underline sat too close
  to the next line.

## [0.1.5] — 2026-09-26

### Added

- Day blocks, `[bloques.<clave>]`: a section of the dashboard's today tab filled by a
  command that prints a page (the section contract, plus `marca` and `destacado` per
  item). `telar bloque [clave] [--json]` runs one. Fetched with the network rhythm.
- Each shortcut says where it shows, `[atajos.<k>] en`: `"hoy"` (the general line at the
  top of today), a block's key (its title) or `"seccion:<clave>"` (that tab's title). The
  key works from every tab.
- A block item with `mensaje` is clickable: it opens a new thread with the agent and that
  first prompt (`telar bloque <clave> --abrir <mensaje> [--nombre …]`), so one mail can be
  processed on its own.
- Every agenda event is clickable, past ones too. One that hasn't started opens its
  preparation (`[agente] reunion`); one that has, its minutes in a «✎» tab
  (`[agente] minuta`, `/minuta` by default). `[agenda.<clave>]` rules, a regular expression
  on the title with `antes` and `despues` messages, pick a different skill per kind of event.
  `telar reunion` says which one applies (`momento`, `regla`) and takes `--antes`/`--despues`.

- Task cards. A provider can declare `detalle`, a command that prints a task as a page
  with actions (`telar tarea <id> [--accion N] [--texto T]`). Clicking a task in the
  dashboard or the sidebar opens its card instead of launching an agent: read it and
  decide, with ⏎ for the main action and numbers for the rest; ⌘-click still takes it to
  its thread. Actions run a command, take the task to its thread or open a link; the
  command always comes from the provider, never from the webview.
- `avance` on a task (what an agent working alone left: prepared, close, question,
  conflict) shows as a coloured word and puts the task first. A **revisar** tab (`v`)
  lists them all to review; in a card, ← → moves between them and a decision moves on to
  the next one.
- Page blocks can be `destacado` with a `color`, and items can carry an `enlace`.

### Changed

- The dashboard, redrawn: a header with a flowing colour gradient, each section with its
  own colour, marker and count, rows on aligned grid columns, a pulsing next meeting,
  shortcuts as key buttons, and short copy (just the time, `-39d`, `hoy`). It adapts to the
  panel's width (container queries): secondary columns go, the task text never does.
  Motion is off when the system asks for reduced motion.
- The dashboard's screens are tabs under a fixed top bar (today, projects, mail, each
  section with a page, settings): switching is one click, and there is no «back» to find.
  `p`, `c` and `r` work from every tab.
- Strict terminal look in the dashboard: one font size and no letter spacing anywhere,
  horizontal spacing in whole characters and vertical spacing in whole lines, and nothing
  decorative takes space (outlines and inset shadows instead of borders; keys keep their
  keycap look and take exactly two cells).
- One shortcut component across the dashboard: key and name, and on hover both take the
  colour of their section. Hints that aren't clickable (`1–9 preparar`) use the same look,
  dimmed. The **Atajos** section and the footer are gone; `t` opens the tasks.
- The agent-mail tab is called «agentes», so it isn't confused with a mail block.
- No more key letters on tasks or numbers on agenda rows: rows are clicked. Those keys are
  free for shortcuts; only `r p t c /` stay reserved. A task shows `+` (new thread) or `→`
  (goes to its thread, named in the tooltip) instead of the words, and `●` when it's being
  worked on (the old box glyph is gone).
- Meeting titles like «Revisión Proyectos Internos» no longer guess a project from the
  words «proyectos» or «internos».

## [0.1.4] — 2026-09-25

### Added

- `telar hilo llevar [remote]` (and «Llevar a otra máquina…» in VS Code) moves a local
  thread to another machine with its conversation: closes the agent here, copies the
  conversation there and reopens the thread as remote, resuming it. It warns, and asks,
  when the repository here has work that isn't pushed: the conversation travels, the files
  don't.

- Each thread with a mailbox has an inbox: `telar correo --json` gives, per thread, the
  mail that reached its address and how much of it hasn't been seen (`correos`,
  `no_leidos`), and `telar correo leido <hilo> [--ids …]` marks it seen. «Seen» means seen
  in telar, kept per thread in the state. VS Code: an ✉ right after the priority when a
  thread has unread mail, and a **✉ correo** tab in the card that shows the inbox and
  marks it seen.

### Fixed

- A `claude -p` run from inside a thread (a script, a tool) inherited `$TELAR_HILO` and
  its hooks recorded it as the thread's conversation, ahead of the real one. telar's hooks
  now ignore non-interactive agents (`CLAUDE_CODE_ENTRYPOINT=sdk-…`), and `llevar` takes
  the first recorded conversation that exists on disk.
- `llevar` also checks the work root and each repository in `[remotos.<n>] repos` (a nested
  repository isn't seen from the one around it), and no longer counts nested repositories or a submodule's own changes as unpushed
  work, and says so when the thread's folder (linked outside the root) doesn't exist on
  the other machine.
- A remote agent now starts where `[agente] carpeta` says, as it does here, instead of
  always at the remote root plus the thread's folder.
- The «close» menu item said the thread stays in the list; it leaves it.
- A thread's mail only counts what was addressed to its own person: in the common archive,
  `other+pizza@` is not for your «Pizza».

## [0.1.3] — 2026-09-24

### Added

- Agents that know each other: `telar agente instalar` adds a second `SessionStart` hook,
  `telar agente contexto`, that gives the agent five lines on its thread, its mail address
  (or that it has none) and how to reach other threads; and installs the `/hilos` skill with
  the long version (finding threads, reading what they are about, writing and replying,
  the rules). `[agente] contexto = false` turns the lines off; an existing `/hilos` skill
  that isn't telar's is left alone.
- `telar correo enviar <user+thread@server> -s <subject> [--responde <id>]` (body on stdin),
  over ssh from the laptop or with `mail` on the server; header injection is rejected.
- `telar directorio`: each person's remote threads on a shared machine, published by telar
  into a common folder (`[remotos.<n>] directorio`) when a remote thread is created,
  renamed, archived or closed; files whose owner isn't the user they are named after are
  discarded. The summary is the document's title, not its state.

- `servidor/`: the server half of mail between agents (`cartero`, `archivar`) with a README
  on how it is set up. The cartero only accepts the sender Postfix recorded in the topmost
  `Received` header (lower ones can be forged over SMTP), only wakes the exact thread, and
  its delivery model is watched by a `PreToolUse` guard that allows one `SendMessage`, to
  the chosen session with the exact text, and fails closed.

### Fixed

- `telar correo` with a common archive: the recipient of an archived copy comes from
  To/Cc (its X-Original-To is the archive's); mail to other users is no longer marked
  undelivered, since their delivery log can't be read; replies without In-Reply-To
  (`mail -s "Re: …"`) join their conversation by subject; GNU mail's In-Reply-To text is
  parsed for the id; participants are people, not `user+thread` addresses.

## [0.1.2] — 2026-09-24

### Added

- Mail between agents on a remote machine: each remote thread has an address
  (`user+<thread>@server`) and its remote tmux session carries `@telar_hilo`. `telar correo`
  reads the Maildir, the delivery log and an optional common archive over ssh: undelivered
  mail per thread and conversations grouped by `References`. VS Code shows ✉ N, the
  address in the card and a **✉ correo** dashboard screen. Resuming a thread with
  undelivered mail tells the agent how many and where, without copying them.
- `telar movil`, for a phone: a small-screen list of the machine's threads; entering one
  goes through a grouped tmux session with its own status bar, mouse and key table, so
  «◀ telar» or F12 come back without the laptop seeing any of it.

- Remote threads: `[remotos.<name>]` declares a machine (`destino`, `transporte` mosh or
  ssh, `raiz`). `telar ir <name> --crear --remoto <name>` opens a local window that runs
  mosh/ssh into a tmux session of its own over there, with the agent in it; the window
  carries the `@telar_remoto` option. Closing or archiving ends the remote session too;
  retomar re-attaches (`-A`) or recreates it with `--resume`. Threads are recognised by
  the mark or, without it, by a mosh/ssh/et process (`remoto: "?"`). `telar doctor`
  checks each remote. The VS Code list shows `⇄`, and «new thread» asks local or remote
  when there is any remote.

### Changed

- A thread opened just for a task is named after its code and its topic («T118 Faro
  2026»), not the bare code.
- Tasks: hovering a row shows its whole text in a tooltip of the view's own (the native
  `title` does not always show inside a sidebar view).

## [0.1.1] — 2026-09-23

### Added

- Sections: `[secciones.<key>]` groups threads (exact names, or prefixes ending in `*`)
  under their own collapsible header in the thread list, with an optional `home`
  command whose JSON page opens in the dashboard panel (`telar seccion <key>`).
- Section pages accept a `lienzo` block: a self-contained local HTML page shown in a
  sandboxed iframe (`allow-scripts` only) through `srcdoc`, with the panel's nonce on its
  scripts and `params` in `location.search` and `window.lienzo.params`.
- `telar agente conversacion <id>` reads a whole conversation (what was said, one line
  per tool); a page item with `conversacion` opens it in the dashboard, with ▶ retomar.
- Dashboard shortcuts: `[atajos.<key>]` declares a key that opens a new thread with the
  agent and a first message (flow's `m` → `/correo`), stamped with the time. Also a
  clickable **Atajos** row, and `telar atajo [key]` from the terminal.
- `telar proyectos` lists every unit the profile declares, with its display name and the
  last time anything in its folder changed; `telar proyectos abrir <ruta>` opens a thread
  linked to it with the agent already loading it (or goes to the one already open). The
  first message is `[agente] proyecto`, settable with `telar config --proyecto`.
- Dashboard: a **▤ proyectos** screen (key `p`) with search and a-z / recent ordering;
  click or ⏎ opens the project.

### Fixed

- Taking a task to a thread that has to be opened started a bare shell (in `/` when the
  task had no folder) and typed the task into it. The new thread now starts with the
  agent in `[agente] carpeta`, and the message is its first prompt. What is said is
  `[agente] pendiente` / `pendiente_nuevo` (markers `{texto}`, `{ref}`, `{id}`).
- The task sidebar lost the provider's tasks between network reads: a local read
  replaced the whole list with the documents' ones. They are now kept until the next read.

### Changed

- `telar hilo cerrar` (✕ in the list) now forgets the thread as well as closing its tab,
  so it leaves the list. Archive (⏸) what you want to keep.
- VS Code thread list: no multiplexer id column; a thread without priority shows a dim
  `·`; the row buttons float over the right edge on hover, so the time column stays
  aligned.
- A thread can be linked to a folder outside the work repository (`telar hilo vincular
  /any/path`, or the folder picker). The profile does not know it, so its card is just
  that folder's README: title and document, no state or pending items.
- VS Code thread list: threads with a tab always come before those without one, whatever
  the chosen order.
- Tasks (sidebar and dashboard) can be ordered by urgency, code (descending: T130 before
  T81) or text; the choice is remembered.
- VS Code task sidebar: no `[a]` letters (and no hidden letter shortcuts), and the task id
  no longer sits in a fixed 12-character column.

## [0.1.0] — 2026-09-22

First release. Everything below is new.

### The loom

- `telar init` writes the configuration, detects the multiplexer and, if the work
  repository has no profile, proposes one from what is actually on disk.
- `telar tejer` raises the session and opens one thread per unit of work the profile
  declares, up to eight; `telar hilos`, `telar hilo`, `telar ir` and `telar vincular`
  act on them. State survives restarts, keyed by thread name.
- `telar ficha` reads a thread's document through the profile: title, state, pending
  items, whatever the archetype declares. No section is assumed.
- `telar hoy` and `telar pendientes` gather across the repository.
- `telar doctor` checks multiplexer, session, profile, providers and hooks, and says
  what to do about each failure.
- `telar agente` installs hooks so an agent can report where it is working. Hooks are
  refused when the executable they would call lives somewhere temporary.

### Multiplexers

- tmux (the reference implementation) and Zellij, behind one interface. Both are
  optional: telar reads whichever is installed and says so when neither is.
- Threads are keyed by the multiplexer's own window id, guarded by a session
  fingerprint so recycled ids after a server restart do not migrate state.

### VS Code

- An extension with the threads, the pending items, the day, the thread's document and
  its folder, reading the same `--json` contracts as the terminal.

### Profiles

- `telar-perfil.yaml` declares archetypes (which folders are units of work, which file
  is their face, which sections it has) and actions (what the repository offers to run
  on a thread). An example profile ships in `ejemplo/`.

[Unreleased]: https://github.com/nicorivas/telar/compare/v0.1.11...HEAD
[0.1.11]: https://github.com/nicorivas/telar/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/nicorivas/telar/compare/v0.1.9...v0.1.10
[0.1.4]: https://github.com/nicorivas/telar/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/nicorivas/telar/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/nicorivas/telar/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/nicorivas/telar/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/nicorivas/telar/releases/tag/v0.1.0
