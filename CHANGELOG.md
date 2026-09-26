# Changelog

Versions follow [semantic versioning](https://semver.org). The Python package and the
VS Code extension share a version number: a tag `v0.1.0` releases both, and the release
workflow refuses to run if the two disagree.

## [Unreleased]

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

[Unreleased]: https://github.com/nicorivas/telar/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/nicorivas/telar/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/nicorivas/telar/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/nicorivas/telar/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/nicorivas/telar/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/nicorivas/telar/releases/tag/v0.1.0
