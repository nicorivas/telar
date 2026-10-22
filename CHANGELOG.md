# Changelog

Versions follow [semantic versioning](https://semver.org). A tag `v0.2.0` releases the Python package; the
release workflow refuses to run if the tag and `telar.__version__` disagree. Up to 0.1.13 the VS Code
extension shared the version number.

## [Unreleased]

### Added

- Addresses and objects (`telar.objetos`). Anything has one address, `type:id[@machine]` (`tarea:T366`,
  `hilo:Telar`, `proyecto:nico/proyectos/telar`, `archivo:telar:docs/x.md`), and `telar objeto <address>
  [action]` (also `GET /objetos/<address>` and `POST /objetos/<address>/acciones/<action>`) shows it, with its
  fields, the addresses it links to and its actions, or runs one of them. Four types ship with telar (task,
  thread, project, file); a module brings its own with `[objetos.<type>]`, whose `ver` and actions are its
  queries. `telar objeto --buscar` finds the addresses in a text.
- The JSON outputs that name an object carry its address in a new `direccion` field: each thread in `telar
  hilos` and `telar ficha` (`hilo:<name>`), each unit in `telar proyectos` (`proyecto:<path>`), each row of
  `telar pendientes` that is a task of the type (`tarea:<id>`, `""` otherwise), a task's page (`telar tarea`,
  `GET /tareas/{id}`) and what `telar tipo tarea` returns. No other field changes.
- An id that would break an address is escaped like a URL (`hilo:Faro%40casa`, `hilo:◌%20a%20solas`), so an
  `@` in a name is not read as the machine and a name with spaces is found in a text.
- Each thread in `telar hilos --json` (and `GET /hilos`) carries `repo`, the name of the `[repos]` repository
  its folder belongs to (`""` if none). The plain `telar hilos` shows it, dimmed, when the threads span more
  than one repo.
- `telar doctor` warns when a repo of `[repos]` does not exist or is outside `raiz` (its profile is not added),
  and when the profiles of two repos recognise the same folders (and says which wins: the deepest). It also
  loads when a declared module cannot be read, which stops every other command, and reports which one and why,
  as a failure in its `módulos` check (so does the `telar doctor` at the end of `telar instalar`).
- A module whose `modulo.toml` brings an invalid `[pestana]`, `[app]` or `[resultado]` is now an error that
  names the module and the section (`modulos.faro: la [pestana] de su modulo.toml no vale: …`).
- `telar doctor` warns when a provider with `tipo = "tipo"` reads another folder than `[tipos.tarea]`, or
  there is no `[tipos.tarea]`: its `tarea:<id>` addresses would open another task, or none.
- Message templates that take `{id}` also take `{direccion}`, the object's address (`tarea:T84`): `[agente]
  pendiente` and `pendiente_nuevo`, and a task provider's `mensaje_procesar` and `mensaje_escribir`. A pending
  item without an address (a checkbox in a document) falls back to `{texto}`, as with `{id}`. Defaults are unchanged.
- Agents know about addresses: the start-up context of each thread's agent has one more line (an object is
  named `type:id`, `telar objeto <address>` opens it and lists its actions, and messages should name things by
  their address), and the `/hilos` skill that telar installs explains it in a new section.
- `telar objeto hilo:<name>@<machine>` opens that machine's thread even when a thread with the same name lives
  here (it used to return the local one). The `/hilos` skill now says that `telar directorio`'s `direccion` is an
  email, not a `type:id` address, and that a `mensaje` goes to the name's mailbox whatever the machine.
- A checkbox in a document gets a stable id the first time telar writes it (`telar pendiente --hecho` or
  `--responsable`): `<!-- id: c-1a2b3c -->` at the end of its line, unique in that document. From then on it is
  found by that id even when the document changes, its row in `telar pendientes` carries `direccion:
  "pendiente:c-1a2b3c"`, and `telar pendiente` takes the id or the address as well as the `ref`. An id already on
  the line is never rewritten, no other line changes (CRLF and unicode included), and a document that cannot be
  written stays as it was. Writing a checkbox also keeps CRLF line endings now (it used to turn them into LF).
  Only a comment that ends the line and is not inside a code span counts as the id; the same id in two documents
  is a 409 that names both (it used to pick one), and a bare id written by hand (`T84`) does not win over a
  provider's task with that id: name it `pendiente:T84`.
- Writing a checkbox no longer replaces a read-only file (renaming used to go around the permission), keeps a
  hard-linked document linked, keeps the line's trailing spaces (a markdown line break), and two writes from
  the same process no longer share a temporary file or overwrite each other.
- A fifth built-in object type, `pendiente` (`pendiente:<id>`, or `pendiente:<ref>` for one without an id): a
  document checkbox with its text, state, document, line and owner, and the actions `hecho` and `responsable`.
- Two identical checkboxes without an id in one document are now two rows in `telar pendientes` (they used to
  be one, and writing it failed), each with a new `repetida` field (`{"cual": 2, "de": 2}`, `null` when the text
  is unique). `telar pendiente` writes the one the row names and gives it its own id; if the number of
  checkboxes with that text changed meanwhile, it is a 409 and nothing is written.
- Documented and tested how the task model evolves: task files never carry a `version` field; the reader
  understands the old form and the new one and both give the same task (an omitted field is its default, the
  checkbox's two dialects and key synonyms), and a key the format does not know is kept byte for byte.
- Task files: `dueno` (without ñ) is read as `dueño` and rewritten under its own name, as is a key written in NFD;
  a leading BOM no longer hides the header (an action used to prepend a second one), CRLF files stay CRLF
  when an action writes them, and a repeated key the format does not know is no longer reported as duplicated.
- `telar config --json` (and `GET /config`) lists the repositories of `[repos]` in a new `repos` field (name,
  path, profile), and each module now says where it came from: `instalado`, `fuente`, `version` and `enlazado`,
  from what `telar modulo` wrote down (empty for one declared by hand). No other field changes.
- A module's `fuente` no longer shows the `user:password@` part of a URL in `telar config` (nor in `GET /config`),
  and `telar config` and `telar modulos` no longer end the line with a dangling `@` when no version was recorded.

## [0.3.0] — 2026-10-21

### Added

- Modules keep their own crontab: installing, updating, adopting or removing one with scheduled jobs updates
  the crontab on the machine where jobs run (and says so on another). `[requiere] programas` is checked before
  installing. `telar modulos adoptar <name>` moves a module declared by hand into `modulos.toml`.
- A module can tell the agent of every thread something when it starts (`[contexto] texto`, up to 600
  characters), after what telar already tells it: how a module makes its agents know it is there and when to use it.
- A task action that sends its message to a thread takes `hilo` (`POST /tareas/{id}/accion`, `telar tarea --hilo`):
  the message goes to that thread or agent, here or on another machine, instead of the task's; a name that is
  no thread is a 404 before anything runs. A multi-line text reaches a thread whole: it is pasted at once
  (bracketed paste) instead of typed, so a line break no longer sends the first line alone.
- `telar archivo` sends files up to 25 MB between machines: anything over 700 KB goes in chunks over the bus and
  the receiving node joins them (both machines need this version; small files work as before).
- Modules as plugins. A module declares its own commands (`[ordenes.<verb>]`: `telar <module> <verb>`) and
  queries (`consulta = true`: JSON in, JSON out, by `GET /modulos/<module>/<verb>` and, with `maquina`, from
  another machine over the bus), and installs from a git repository: `telar modulos instalar <repo>`,
  `actualizar`, `quitar`, with `--enlazar` to develop one in place. Installed modules are recorded in
  `modulos.toml`, next to the configuration, which telar leaves to its author.
- The page reads files on other machines. `GET /archivos` takes `maquina` (or a `machine:path` route), and
  that machine's node reads the file over the bus with its own limits. Files under the `[repos]` folders can be
  read too, not only those under the root.
- File paths an agent writes are links to the document viewer, in the terminal (click), the reading view and the
  conversation, on the thread's machine: absolute, `~/…` or relative, with `:line` ignored. A relative path is
  from where the agent started, which `[agente] carpeta` may make the thread's folder or the root: the page tries
  the thread's folder first and then the root, and opens the one that exists. The viewer opens `machine:path` (a
  file alone, without its folder), and a `README.md` in an answer no longer becomes a link to `http://README.md`.
- The document viewer shows an `.html` file drawn, in an iframe (`GET /archivos/ver`, also `machine:path`) whose
  scripts run in an origin of their own, without the page's key or its API; «código» next to its path shows the
  source, and «dibujado» goes back. What the page loads by a relative path (images, styles) is not resolved: it
  is for self-contained pages, like a slide.
- An object's address (`tarea:T366`, `hilo:Telar`, `proyecto:nico/proyectos/telar`, `archivo:telar:docs/x.md`, and
  the types a module brings, from `/api/objetos/tipos`) is a link wherever an agent writes it: the terminal
  (whole, even split over several rows), the reading view and the conversation. A task opens in its card, whose
  «‹» goes back to where the link was; a file or a project, in the viewer (the project, its folder); a thread, the
  thread, as a click in the bar. Any other type opens in a view of the object, in the same box with «‹»: its
  title, state, summary and fields, its links (addresses too) and its actions, which ask for their parameters (or
  a confirmation, if they take none) and run on the version being looked at.
- The document viewer shows a file's connections in the knowledge graph next to it (below it on a narrow
  screen), when the file's machine has the `grafo` module: the ones that go out (type, where, and why) and the
  ones that come in, grouped by the other document. Each one opens that document in the same viewer. They
  arrive after the file, so they never delay it; without the module, or without connections, nothing shows.
- Web addresses open in a new tab of the browser being used, wherever the thread lives. In the terminal, an
  `https://…` written as text is a link (without the punctuation that ends the sentence, and whole even when
  Claude Code split it over several rows), and an OSC 8 hyperlink opens without xterm's confirm (a `file://`
  one, in the viewer). In the reading view and the conversation, a link to a web opens a new tab instead of
  taking the page away. New tabs get neither the page (`noopener`) nor its address (`noreferrer`).
- Several working repositories (`[repos.<name>] ruta = "…"`, optional `perfil`). Each brings its own
  `telar-perfil.yaml`, and telar merges them into one (`perfil.cargar_todos`): each repo's archetypes become
  relative to the root and carry which repo they come from; when two profiles match the same folder, the
  deepest repo wins, so a team repo inside a personal one describes its own folders. A repo without a profile
  adds nothing; one outside `raiz` is not merged yet. Without `[repos]`, only `raiz` counts, as before.
- Mail between people over the bus (`telar.entre_personas`). Each bus account exports `correo.<person>`, a
  service another person uses to leave a message for one of their threads (their node puts it in the thread's
  mailbox, durable like any message; the server tells which account it came from, so nobody writes as someone
  else), and `directorio.<person>`, the list of their threads that their node publishes every 30 s. `telar
  correo enviar person+thread@…` goes over the bus when that person has a node there, and falls back to the
  server's mail otherwise; `telar directorio` also shows what arrives over the bus. Run `telar bus persona` again
  on the bus machine to regenerate its accounts with these exports and imports.
- `POST /reunion`: prepare a meeting, or take its minutes, from the API (`telar reunion … --json`), so the web
  page no longer needs the CLI for it.
- `POST /hilo/llevar`: take a thread to another machine from the API. It runs in its own process, since copying
  a large conversation takes minutes: if it ends within 20 s the answer is what it said (409 with its complaint,
  such as unpushed work that needs `si`), otherwise it answers `en_curso` and keeps going, with its output in
  `<estado>/llevar/<hilo>.log`.

### Changed

- In a task's card, «↩ escribirle a Claude» opens a box of several lines (⏎ is a new line, ⌘⏎ sends) with the
  thread it goes to on top: the general agent (Gestión) by default, the task's thread, or any thread in the list,
  also one on another machine (`hilo` in `POST /tareas/{id}/accion`). What was written stays as the task's draft
  until it is sent, so ⎋ or a click outside doesn't lose it, and a send that failed is retried to the same thread.
- A task's actions: «esperar a…» has role `espera` and offers people (`none` stops waiting); a new «prioridad…»
  (role `prioridad`, P0 to P3). The cap of 12 actions counts only those without a role, so «descartar» is no
  longer dropped.
- The dashboard's tabs are a group of the thread bar (DASHBOARD, first and open, a row per tab with its key), and
  the dashboard lost its own top bar (brand, date, shortcuts) and its row of tabs. «telar», with its moving
  colors, sits at the top left of the page; settings are the ⚙ at the top right, next to the version.
- A task's card sits inside a bordered box, with «‹ tareas» (or the tab it was opened from) above it, next to
  «← 1/39 →». The box and that row are shared pieces (`componentes.css`), for other views to use.
- A task's card changes in place what it shows: the star (☆/★) and sharing with the team (○/◉) are icons before
  the title, as in the task list, and «la hace …» (or «sin asignar») opens the people picker. Those four leave the
  card's list of actions, which now fits single-digit keys.
- In a task's card, the priority («P1») and «espera a …» are buttons too: the priority opens a picker with the
  provider's priorities, and «espera a …» the people picker, with «nadie» to stop waiting. Both leave the card's
  list; «esperar a…» stays in it while the task waits for nobody. The task list's ⋯ menu uses the same pickers,
  and the people picker for who does it, where it asked for a name.
- The document viewer (a file, or a thread's folder) sits inside the same bordered box as a task's card, with
  «‹ <thread> · <view>» (or «‹ dashboard») above it: a click on it, or ⎋, goes back to where the link was
  clicked. A file opened from inside another (a link, the folder, a connection) goes back to that one first.
- In a task's card, the due date («vence 2026-10-12») is a button: a click opens the date picker, as the date
  does in the task list. Without a date, «sin fecha» goes at the end of the line, also clickable.
- Settings have a vertical menu of sections, each in its own module: tabs, calendar, threads, agent prompts,
  periodic processes and agents' messages (both moved out of the dashboard's tabs; `o` and `c` still open them),
  and modules.
- One owner per thread, first two steps. Renaming, linking, prioritizing, archiving, closing or forgetting a
  thread that lives on another machine is asked of its owner over the bus (request `hilo` to its node), and this
  machine adjusts its own copy only if that worked. And every 30 s the node reconciles this machine's windows of
  other machines' threads against their state on the bus: it brings back one that is alive there and missing here
  (unless archived), and closes one that no longer lives there.
- An `[atajos]` key the dashboard already uses no longer stops the config from loading: the tab wins, the
  shortcut is shown without its key and runs with a click, and `telar doctor` warns about it.
- The web page no longer carries the shape of the VS Code extension. Every screen (the thread bar, the
  dashboard, a thread's terminal, reading and conversation views, its folder, «compartir») is drawn in one
  document, each with its CSS under `@scope`; only the dashboard's canvases and apps stay in sandboxed iframes,
  canvases with their own content policy (no network), as `docs/contratos.md` promises. Notices and dialogs are
  the page's own, on top of everything. The page talks only to the API (`fetch`), with no CLI fallback, and its
  source moved from `vscode/` to `pagina/` (`npm ci`, `npm run navegador` there).
- The dashboard's keys only act while it is showing, and never while typing in a field outside it (the bar's
  search, a terminal).

### Fixed

- A file path in the terminal that Claude Code split over several rows (a long one, or a narrow screen) is one
  link to the whole path, not to its first piece. Claude Code breaks its lines itself, at the width of its box,
  so the terminal never knew they were one line: now a row that reaches the right edge goes on in the next one,
  when what crosses the break is longer than a row (`pagina/src/web/enlaces.ts`, tested by `npm run
  prueba:enlaces`).
- The dashboard's task table can be sorted by deadline, and now it shows: each column header has its name
  (código, proyecto, responsable, tarea, fecha), «fecha» sits over the dates (it was an unlabeled ↕ at the
  right edge), and the column that sorts is blue. A click on «fecha» puts the most overdue first and the
  undated last; another click goes back to urgency.
- Sharing from a phone shows what was shared (the page opened on the thread list on top of it).
- Preparing a meeting and taking a thread to another machine work from the page (they needed the CLI, which the
  browser cannot run; now `POST /reunion` and `POST /hilo/llevar`).
- A dialog's detail text is shown (it was dropped), and its line breaks are kept.
- A relative link inside a document in a thread's folder opens that file in the folder view; code blocks in it
  no longer wrap.
- A shortcut in `[atajos]` with the key of a dashboard tab no longer takes the key over: «n» launched
  `/sincronizar` instead of opening «ahora». The tab wins; the shortcut shows without its key and a click
  launches it.
- ⎋ in the projects search, with nothing typed, goes back to «ahora». Since the «hoy» tab was removed (0.2.0)
  it did nothing.
- The dashboard no longer shows yesterday after midnight or after the laptop wakes: the saved day and agenda
  remember their date and are reread when it is another day, and a failed read no longer passes yesterday off as
  today.

### Removed

- zellij as a multiplexer. What telar is built on (the terminal in the browser, grouped views, threads on another
  machine, the single session) only works with tmux, so zellij gave a half telar. A config with `multiplexor =
  "zellij"` now fails with a clear message: use tmux.

## [0.2.0] — 2026-10-20

### Deprecated

- The VS Code extension. The web page (`telar serve --web`) does everything it did, and the release no longer
  builds or publishes it. Its own code is gone (`extension.ts`, the VS Code host and surface, the sidebar
  views, its manifest and packaging); `vscode/` is now only the source of the web page (`npm run tipos`,
  `npm run navegador`), and CI checks that `src/telar/web/` matches what it compiles to. Deploying no longer
  compiles anything.

### Added

- The sordina, a second Claude Code mod (`src/telar/sordina/`) that turns tools down so what the model says
  stays in front: a file edit is one grey line with the file and its lines added and removed (`✎ src/a.py
  +2 −1`), with no diff, and a shell command is one grey line with what it does and how much it printed,
  with no output. Errors, interruptions and the expanded view (ctrl+o) show everything as before. `telar
  agente instalar` loads it with the telar mod; `[agente] sordina = false` leaves it out.
- The telar mod for Claude Code (`src/telar/mod/`, shipped in the package). `telar agente instalar` loads it
  in every Claude Code session through `CLAUDE_CODE_PLUGIN_DIRS` (and `desinstalar` takes it out). When
  messages reach a thread's mailbox while its session is idle, the mod submits the notice line itself, so
  the node no longer types it into the terminal, where it could land on top of what the person was writing.
  The mod leaves a heartbeat in the mailbox (`.mod`); while it is fresh the node does not type. New verb:
  `telar agente mod` (what the mod asks: the thread, its mailbox, the notice).
  The mod also drives each thread's status light from its own events: `empieza`/`termina` with every turn
  (`turn.complete` also fires when the person interrupts with Esc, which the classic `Stop` hook never saw,
  so the thread no longer stays stuck in «trabajando»), `espera` on a permission dialog, an MCP request or an
  `AskUserQuestion`, and `sigue` once answered. While the mod is alive, the classic hooks skip those four.
  And it keeps the session's last messages, already structured, in the mailbox (`mod/conversacion.json`):
  reading a thread (the page's reading mode, `telar hilo leer`, which now says `origen: mod|registro`) uses
  them when they belong to the thread's main conversation and the mod is alive, instead of parsing Claude
  Code's transcript file.
  The mod has its own tests (`claude plugin test` in `src/telar/mod/`), run by CI along with `claude plugin
  validate --strict`.
- `telar instalar`: one command to get a machine running, and safe to run again. It writes the config
  (`telar init`) if missing, creates the page key, joins the bus with `--bus nats://…` (adds `[bus]`),
  installs the `telar serve` service for this machine (systemd user unit on Linux, launchd agent on macOS,
  with the real path of telar and a PATH that reaches tmux and the agent; `--nodo` with a bus, `--equipo`
  with `[equipo]` people) and restarts it only if it changed, installs the agent hooks and skill, and ends
  with `telar doctor`. It shows what it will do and asks first (`--si`, `--seco`).
- One bus account per person (`telar bus persona|personas|quitar`, `telar.cuentas`): nats-server gets an
  account for each person, with their bus name as user and their `[bus] token` secret as password (only its
  bcrypt hash is stored). What one person has on the bus (mailboxes, thread state, machine snapshots,
  requests to their nodes) is invisible to another, enforced by the server; terminal forwarding and
  `/maquinas` tickets only work between machines of the same person. `servidor/telar-bus.service` now reads
  `~/.config/telar/bus/servidor.conf` and reloads on `systemctl --user reload telar-bus`. A bus with a single
  shared token (`nats-server --auth`) is still accepted until 0.3. To migrate one: stop the bus, run `telar bus
  persona <you>`, move `~/.local/share/telar/bus/jetstream/$G` to `…/jetstream/<you>`, install the new unit,
  start it and restart `telar serve` on every machine. The `bus` extra now needs `bcrypt`.

- `telar.tipos`: types over text files (`docs/arquitectura.md`, «Los tipos»). The first is `tarea`, with two lenses
  that read leniently and write minimally — what did not change stays byte for byte: its own file
  (`clave: valor` lines, context, `## Conexiones`, `## Historia`; keys configurable) and a checkbox in a
  document (both dialects: `@owner(…)`/`@deadline(…)`/`@prioridad(…)` and `vence:`/`!alta`/`#tag`). Checked
  against real data: 308 task files and 4,868 checkboxes, read the same as before and changed thousands of
  times without touching anything else.
- `tarea`'s actions (complete, close, reopen, someday, wait, reschedule, assign, note, propose, answer,
  edit) — functions on the model with a precondition and a history line — and `telar.tipos.carpeta`: read
  a task with its version (the file's hash), apply an action, reject it if the file changed since it was
  read, one writer at a time, atomic writes, and nothing written unless it reads back as intended. On copies
  of 308 real tasks, 1,887 of 1,903 action runs leave the same bytes as the previous task CLI; the rest are
  two files whose history that CLI was corrupting further on every save.
- The in-memory index (`telar.tipos.indice`) and `[tipos.tarea] carpeta`: `telar serve` keeps the tasks in
  memory, up to date with their files by date and size (308 real tasks: 66 ms to build, 1 ms to check), and
  serves them at `/tipos/tarea` (filters), `/tipos/tarea/{id}` (with its version) and
  `POST /tipos/tarea/{id}/{action}` (`{params, version}`; a stale version is a 409 with the current one).
- A `tipo = "tipo"` task provider: `telar hoy` and the panel read the tasks from the type's in-memory index
  (shared with the API in the same process), in the same shape as before. On the same 88 real tasks it gives
  the same items as the previous adapter, field by field, in 2 ms instead of 71 ms. With `en`, another
  machine's node serves them over the bus.
- `telar serve --nodo` runs the bus node in the same process as the API: one process per machine, and the
  API's bus requests go over the node's open connection instead of opening one each (laptop → server:
  1.07 s → 0.34 s). Reading the bus state (`telar nodo estado`, `telar hilos --red`) is one batch instead
  of a request per key (3 s for 107 threads, where it used to time out).
- `telar correo` only sends now (`telar correo enviar`, to another person); reading the Maildir over ssh
  (`telar correo`, `correo leido`, the mail notice when resuming a remote thread) is gone.
- Retired what the bus replaced: the door (`telar enlace`, `[enlaces]`; `[enlace] entrada|no_leer` still
  read, now `[bus] entrada|no_leer`), `telar remotos atencion|traer` (the node does it), and the mirror over
  ssh (`telar espejo publicar|recibir|traer`; the node publishes it). New: `telar aviso` and `telar archivo`,
  a notice and a file to another machine over the bus. The panel no longer polls over ssh or shows agent
  mail. The cron block telar writes sets `MAILTO=""` (each run already logs its output). **Two machines now
  need the bus.**
- The team page is a separate FastAPI app (`telar.api_equipo`) that `telar serve --equipo` runs on its own
  Tailscale port in the same process (or alone, `telar equipo servir`): a person's key reaches none of the
  owner's routes. The owner's inbox has routes in the owner's API (`/equipo/bandeja`,
  `/equipo/{id}/aceptar|rechazar|existe|revisando`) and goes to the machine with the tasks over the bus
  (a new `equipo` request) instead of ssh. The old `http.server` handler is gone.
- `GET /archivos`, `GET /archivos/md` and `PUT /archivos`, so the dashboard in the browser reads what it
  used to read from disk (a project's README, a meeting's preparation and minutes, an app's lienzo and its
  memory): files under the root, those an app declares, and the lienzos of pages the API itself served;
  writing only a lienzo's `.json` memory. The panel reads through a `Disco` interface (fs in Node, the API
  in the browser).
- A browser terminal that is hidden (another view, another thread) no longer measures itself: it measured 0 and
  shrank its thread's tmux window to 20×5 for every screen, so coming back to it showed a crushed terminal
  until a reload. It measures again, and redraws, when shown.
- Views of a thread in the browser, switched from an action bar above it or with ⌥ and a letter (even from
  inside the terminal): the terminal (⌥T), the conversation (⌥C) and a new reading mode (⌥L) that renders the
  agent's final answer for a careful read (only what it wrote after its last tool call: the process before it —
  the notes between tools, the diffs, the calls — stays in the terminal) — serif type, its markdown properly
  drawn, a reading width, the question
  above as an epigraph; ← → walk the answers, ⎋ goes back, and the last one updates while the agent writes.
  The views are a registry (`vscode/src/web/vistas-hilo.ts`): a new way of looking at a thread is one more
  entry; and the reading mode draws each source with its renderer (`conversacion`, `panel`), so a new
  assistant is one more renderer. The header's terminal/conversation button moved into that bar.
- Opening a thread from the browser page: «+ nuevo» on the HILOS header asks for its name (and, with
  `[remotos]`, which machine) and shows the new thread's terminal; a name that already has a thread is refused
  (it would go to that one). In VS Code it stays the + of the view's title bar.
- Connecting the calendar from the browser dashboard (configuration › calendar › iCal): it asks for the private
  iCal address in a hidden field, checks it is an https address, and saves it like VS Code did. With that,
  everything the dashboard asks of its host works in the page too.
- Opening a file or a folder from the browser dashboard (a project's README, its folder, a local link) shows it
  in the page (`arch:<ruta>`, the same view as a thread's folder, based on the repository root and never
  outside it); what is not text (a PDF, an image, a large file) gets a «bajar» link (`GET /archivos/bajar`,
  with `/archivos`' limits). `GET /hilos/documento` works without a thread.
- «Go to a thread» from the browser dashboard shows it in the page (it used to move tmux's focus, which only a
  terminal attached to the session would see), and «back to the terminal» after opening a thread or handing
  it something shows the thread the action left in front.
- The browser terminal sizes its thread's tmux window (the most recently used screen wins, tmux's
  `window-size latest`): it used to defer to any other terminal attached to the session (a VS Code one), so
  the window kept that size and tmux filled the rest of the browser with dots. It takes the full height and at
  most 130 columns (`localStorage['telar.columnas']`), centred, with a very faint loom around it (still when
  the system asks for less motion). `telar mirar --sin-tamano` keeps the old behaviour.
- The thread list has no group per machine any more: threads of other machines go in HILOS with the local
  ones, and the column after the status says where each lives (⇄ for another machine). The ⇄ button next to
  «buscar» widens that column to show each thread's machine by name, this one included; searching by machine
  name filters too.
- `/maquinas`, the mother page («máquinas», top right): your machines in the middle — this one, and those on
  the bus that serve their page (the node's photo carries its address) — over an ASCII loom weaving a twill
  around them. You go into another machine's page without its key: the link carries a ticket signed with the
  bus token (the secret a person's machines share), for that machine only, valid once and for a minute
  (`/entrar`). The «progreso» page is gone.
- The browser page's header says, in the middle, which machine serves it and what you are looking at:
  `telar › Gestión` for a thread of that machine, `telar ⇢ laptop:Telar` for one of another (forwarded). A
  thread of another machine is named `máquina:hilo`, like `scp máquina:ruta` (with the person it would be
  `nico@laptop:Telar`). The machine is its name on the bus, or its hostname without one, from `/salud` (which
  now also returns `maquina` and `host`): every machine serves its own page, so with any number of them you
  know which one you are on.
- Local echo in the browser terminal, like mosh: what you type appears at once, dim, without waiting for the
  round trip. Built for Claude Code, which redraws the whole screen on every key (VS Code's typeahead expects
  each letter echoed alone, so with Claude Code it never confirms a prediction and stays off): after each
  frame, the pending letters already before the cursor count as confirmed and the rest are drawn again. It
  turns on above 40 ms of measured latency, only with a visible cursor at the end of its line (spaces,
  including the non-breaking ones Claude Code pads its input box with, count as the end); each frame and its
  echo are drawn together with synchronized output (DEC 2026), so the cursor doesn't jump between them
  (`vscode/src/navegador/eco`, bundled as `src/telar/web/eco.js`; `npm run prueba:eco` tests it against a fake
  Claude Code). The terminal gets the focus again; the box below stays, a click away.
- The server joins the pieces of a tmux frame (up to 8 ms) before sending them, so the browser draws whole
  frames: the cursor, which each frame hides at its start and shows at its end, no longer flickers.
- A box under each thread's terminal in the browser: you type locally, with no per-key round trip (and no
  flicker from Claude redrawing its input on every letter); ⏎ sends it whole as a paste, ⇧⏎ is a new line;
  with the box empty, ⏎ ⎋ ↑ ↓ go straight to the terminal. A click on the terminal types into it directly.
  The terminal's cursor no longer blinks (Claude Code draws its own).
- A thread's terminal in the browser reconnects by itself when its connection drops (the laptop slept, the
  network changed, telar restarted): after 1 s, then backing off to every 15 s, and at once when the tab or
  the network comes back; it redraws the screen on reconnecting. It used to stay closed until a reload.
- Terminals of threads on another machine in the browser page: `/pty?hilo=…&maquina=…` forwards the
  WebSocket to that machine's own page (its address now travels in the node's photo on the bus, `web`),
  which accepts it with the bus token — the secret a person's machines already share. A thread from another
  machine opens as its real terminal on a wide screen, and as its conversation on a narrow one.
- The box to write to a thread (its conversation in the browser): ⏎ sends and ⇧⏎ is a new line; it uses the
  page's font (16 px only on touch screens, so the iPhone doesn't zoom) and, instead of a box, a line at the
  left that turns blue while writing.
- `scripts/dev.py` (`docs/desarrollar.md`): esbuild watching the page's TypeScript and CSS, plus a separate
  `telar serve --web --dev` on port 18780 that restarts when the Python changes; with `--dev` the page
  reloads itself when its files change (`/dev/cambios`). And `servidor/desplegar.sh`: pull, reinstall or
  `npm ci` only if needed, restart `telar-serve` and check the API answers and no tmux window was lost.
- The browser page's frame (header, columns, «progreso») and its terminal colors now come from the design
  tokens (`vscode/media/css/tokens.css`) like every other view: the frame's styles live in
  `media/css/marco.css` and the build bundles them with the tokens into `src/telar/web/marco.css`. The frame's
  own palette and its light mode are gone (telar is dark only); the frame now uses the views' font.
  The header now spans the whole width, above the thread list (on a phone it stays on top of the list too).
- The browser page caches what does not change and compresses everything: xterm.js is kept for a week (it
  was downloaded again for every thread opened, ~1.7 s over the laptop–server link), the page's own files
  are revalidated (a 304 when unchanged), API data is never stored, and responses go gzipped.
- What only the Node panel served, now in the Python page: installing it as a phone app (manifest, icons
  and service worker from `web/app`, served without the key), sharing to it from the phone (`/compartir`
  opens the page on the share view, with providers and threads from the API) and a thread's folder and
  document (`doc:<hilo>`, from `GET /hilos/documento`: nothing outside the thread's folder, nothing hidden).
- Thread terminals in the browser page without Node: `/pty` in `telar.api_web` runs `telar mirar <hilo>` in a
  PTY (asyncio) behind the same key and an origin check, and xterm.js is served from `estatico/xterm`. A thread
  of this machine opens as its terminal on a wide screen and as its conversation on a narrow one (the button
  at the top switches); at most 8 terminals stay open. The conversation of a local thread now types into its
  terminal instead of sending a message. Needs `websockets` (in the `serve` extra).
- The team inbox in the browser: `/config` says where it lives (`equipo`: `aqui`, the machine in
  `[equipo] en`, or empty) and the page uses it as its `equipoRemoto` setting; «Ver» on the «N things from
  the team» notice lets you pick one when there are several, as in VS Code.
- `PUT /config/{ajuste}` (directories, meeting and project templates, calendar), `/compartir`,
  `/hilos/leer`, `/skills` and `/periodicos`, one service each. Periodic jobs that live on another machine
  are asked of its node over the bus (a new `periodicos` request); the CLI uses the bus too, and ssh only
  without one.
- `POST /pendiente/llevar` and `/pendiente/casilla`: carrying a pending item to its thread and changing its
  checkbox, as functions that return their result (the CLI, the task actions and meetings use them; no
  more captured output). `POST /hilo/{verbo}` and `POST /tejer` run the same command inside the API
  process with its output captured, one at a time (`telar.servicios.en_proceso`): a bridge until those
  verbs return models. `hilo llevar` (minutes, over ssh) stays on the CLI.
- `GET /atajos`, `POST /atajos/{tecla}`, `POST /encargos`, `POST /proyectos/abrir` and `POST /ir`: the
  calls that open or focus a thread, one service each; the CLI's old paths to another machine without a
  bus (through the door, over ssh) stay in the CLI, and the API says so with a 502.
- `POST /mensajes`, `POST /mensajes/{id}/soltar`, `POST /notas` and `PUT /config/pestanas`: the writes
  that don't open a thread, one service each; the panel asks the API first.
- The bus log is read in batches with an ephemeral consumer instead of one request per message: the last 60
  from the laptop in 3.5 s instead of 17 s, and 200 no longer time out (`telar mensaje --retenidos` works).
- Replacing a pane no longer uses `respawn-pane`, which crashes tmux 3.4 (seen twice on a server, taking
  every thread with it): the new pane opens next to the old one, and the old one is closed.
- A thread finds its agent in `~/.local/bin` when whoever opens it doesn't have it on the PATH.
- A new tmux window or pane inherits the environment of whoever asks tmux for it (a service, an `ssh host
  'cmd'`), not that of the tmux server: telar now opens them with the PATH of the person's login shell,
  read once per process, in front of its own. A thread opened by `telar serve` or the node has Node,
  Homebrew and the agent.
- `GET /secciones/{clave}`, `/apps`, `/apps/{clave}`, `/ficha`, `/notas`, `/mensajes` and
  `/conversaciones/{id}`, one service each behind the CLI and the API; the panel asks the API first.
- `GET /espejos`, `/proyectos` and `/pendientes`: the same JSON as `telar espejo ver`, `telar proyectos`
  and `telar pendientes`, from one service each; the panel asks the API first (the mirror poll every 30 s
  no longer spawns a process).
- Creating tasks and the type's CLI: `telar tipo tarea lista|ver|crear|borrar|<action>` (and `POST`/`DELETE`
  on `/tipos/tarea`), one service behind both. The writer picks a new task's number under its lock; a
  machine with `[tipos.tarea] en` asks the one that has them over the bus (`tipo`), with error codes
  intact. New actions: `secuela`, `conectar`, and clearing a date. The writer commits and pushes the file.
- `telar commit` commits and pushes one at a time per repository: two background commits in a row
  collided on git's `index.lock` and one file stayed uncommitted.
- The `tipo` provider builds each task's card itself (no `detalle`), and its buttons are the type's actions:
  the service applies them to the file with the card's version (a changed task is a 409, and the panel
  re-reads the card), then commits and pushes that file in a separate process. A house's own bits (who
  proposes, whom to write to, the messages for threads, the team, the Gmail account per area) are provider
  options. On 308 real tasks, the card is identical to the previous adapter's.
- `telar serve`: telar's API (FastAPI, Pydantic models) in a process that stays, on a Unix socket inside a
  directory only its owner can enter. Each command becomes a shell around a function in `telar.servicios`,
  used by both the CLI and the API: the logic lives once, and the model is the contract. `hoy` is the first
  (`GET /hoy`); the web panel asks the API first and falls back to the CLI. Install the `serve` extra
  (`pip install 'telar[serve]'`); `servidor/telar-serve.service` and `.plist` start it on their own.
  Pydantic is now a core dependency.
- `telar hilos` and `telar config` moved to `telar.servicios` too (`GET /hilos`, `GET /config`), and the
  panel asks the API for them. `config` keeps `gws`'s account for 10 minutes instead of asking it on every
  read (the question can take 10 s).
- `telar tarea`, `telar bloque` and `telar resultado` moved to `telar.servicios` with their routes: a task's
  card and its actions (`GET /tareas/{id}`, `POST /tareas/{id}/accion`), a day block, an item's detail and
  opening a thread for a row (`/bloques/{clave}`…), a day's result and a comment on it (`/resultados/{clave}`…).
  A service error is a complaint in the CLI and its HTTP status in the API, with the same message. The panel
  uses the API, and falls back to the CLI only when there is no API (or it lacks the route): an action that
  fails in the API is not retried through the CLI, since it would run twice.

### Changed

- `telar doctor` asks for tmux 3.5 or newer (was 3.0): 3.4 has a server crash that takes every thread with it.
- The iCal calendar keeps a copy (`~/.cache/telar/`) valid for `cache` seconds (600 by default) and caps the
  whole download (`tiempo_maximo`, now 20 s), not each read; with no network it uses the last copy and says
  so among the provider failures, instead of an empty agenda. What was read is parsed once and kept.
- The web panel shows the threads of other machines (the laptop's, seen from the server): one group per
  machine whose snapshot arrives here and whose threads the list does not already have. A click reads the
  thread as a conversation over the bus, and its box writes to it as the person. Behind it,
  `telar hilo leer <hilo> --maquina <nombre>` (read by that machine's node) and
  `telar mensaje <hilo> - --tipo persona` (it arrives as the person's own words, not a colleague's).
- The web panel's thread menu: ⋯ on each thread (and right-click) opens what VS Code has as its context
  menu — view, rename, link (to one of the profile's units, or a typed path), unlink, priority, archive or
  unarchive, close, take to another machine, forget, and see its folder and document (`/documento`: the
  folder and the chosen file, markdown rendered, never outside the thread's folder, not even through a
  symlink). Menus and notices go to the page being looked at: each page tells the server how much of it is
  visible.
- Comments on a day's result, in the core: `[resultados.<clave>] comentar` (a command, on the machine where
  the result lives) and `telar resultado <clave> <día> --comentar` (the text on stdin), which goes there over
  the bus. The dashboard offers a comment box under the plan, in VS Code and on the web.
- `telar compartir`: takes something from outside (a link, a text) to a thread or agent, as a message, or
  to a provider that declares `recibir` (its words with `{url}`, `{texto}`, `{titulo}`; no shell).
- The web panel installs as an app (manifest, icons, a service worker that caches nothing), and the phone's
  share sheet opens `/compartir`, which uses `telar compartir`. The session cookie is now `SameSite=Lax`, so
  that launch carries it; writes (POSTs and WebSockets) must come from the panel's own pages (`Origin`).
- The web panel on a phone (up to 700 px wide): one thing at a time — the threads list, and a tap opens the
  dashboard or a thread full screen, with «◀» (and the phone's back button) to return. A thread reads as a
  conversation (`/conversacion`: its last turns from `telar hilo leer`, markdown rendered, re-read every few
  seconds) with a box to write to it and keys to answer a question (⏎ ⎋ 1 2 3 ↑ ↓); what is written goes
  through the thread's terminal view as a paste, so a line break does not send it early. «terminal» opens
  the xterm anyway. The tasks table keeps the code and the text, with the date and ✓ ▶ ⋯ below; filter rows
  wrap instead of running off the screen.
- `telar panel`: runs the web panel (the threads bar, the dashboard and the threads' terminals) without
  `npm`: it finds the panel next to telar's code (or `$TELAR_PANEL_DIR`), says what is missing (Node,
  `npm ci`, `npm run compile`; `--verificar` only checks), and becomes the node process. `--tailscale`
  listens on the machine's Tailscale IP, waiting for it at boot; it refuses to listen on every address.
  `servidor/telar-panel.service` (systemd) and `servidor/telar-panel.plist` (launchd) start it on their own.
- The state of the move out of VS Code, and its order (the panel everywhere, then `telar serve`, then the
  primitives), in `docs/propuestas/dashboard-fuera-de-vscode.md`; `docs/arquitectura.md` shows where it goes.
- `docs/arquitectura.md`: how telar is built (the CLI at the center, the surfaces that only draw, the
  repository profile, providers, modules, the bus), where your own things plug in, and a task system
  connected in three levels: checkboxes in markdown, a bridge script (a working `todo.txt` example), and
  the task card with its actions.
- The app's logo (`telar web` icons) is redrawn on an invisible grid of square cells: the «t» has 2-cell strokes,
  the cursor is 3×6 and sits on the same baseline, right under the «t»'s arm, with 1 cell between them. It
  comes in a full-bleed version and a smaller «maskable» one that survives Android's circular crop; there is
  also an `icono.svg` for the tab. `docs/marca/hacer_iconos.py` generates all of them from one list of shapes.
- `telar commit -m "…" -- rutas`: commits only those paths (new and deleted ones too), never touches
  paths marked `skip-worktree`, and pushes. Before pushing it fetches and rebases, unless what comes in
  touches a file that is dirty here (someone else's work in progress): then it does not integrate, says
  so, and the commit stays local; a rebase that conflicts with the own commit is aborted. A push that loses
  a race with another machine («is at … but expected …», «fetch first») is retried with a wait. One push
  at a time per repository (a lock shared by its worktrees), and every run is logged in
  `<state>/commits.log`. `--local` only commits; `--subir` only pushes. The protocol was written by hand
  in several skills; see `docs/propuestas/primitivas.md`.
- `docs/propuestas/primitivas.md`: the primitives telar is built from (object, type, change; subject,
  thread, message, trigger; node, place, view, module; plus addresses and permissions), what an agent is,
  how each of the 44 orders maps onto them, and how telar should live with git (a worktree per thread,
  one writer for hot files, `telar commit`).
- The views' CSS lives in real files (`vscode/media/css/*.css`), read by VS Code and by the web the same
  way: `tokens.css` (the palette — the terminal theme in VS Code, catppuccin mocha outside —, a type scale
  and a spacing scale), `base.css`, and one file per view. They go in cascade layers (`@layer base,
  vistas`), use native CSS nesting, and pass stylelint (`npm run lint:css`); the linter found five rules
  defined twice, now merged. The web dialogs are native `<dialog>` elements (focus kept inside, Escape and
  the backdrop for free).
- The threads bar and the dashboard run in a browser: `npm run panel` (in `vscode/`) serves one page with
  both, the same code as in VS Code. What depended on VS Code goes through a host interface
  (`anfitrion.ts`: notices, input fields, pickers, opening links and files, going to a thread) and a
  surface (`superficie.ts`); VS Code implements them with its API, and the web server with dialogs drawn
  in the page and a WebSocket per view. Entry needs a key (`~/.config/telar/panel.llave`). See
  `docs/propuestas/dashboard-fuera-de-vscode.md`.
- The web panel shows the terminals: the bar is the navigation — its «dashboard» row shows the
  dashboard, a thread shows its terminal (xterm.js) on the right, and its row is marked; terminals already
  open stay alive in the background (the 8 most recent), and a closed browser tab frees its view within
  30 s (a WebSocket heartbeat). Behind
  it, the server runs `telar mirar <hilo>` in a pseudo-terminal (node-pty): a new order that attaches to a
  grouped tmux session pinned to the thread's window — the same as other machines and the phone use —,
  so typing there types in the thread but does not move what anyone else sees, and closing the tab
  removes the view. A thread of another machine is seen through its window on this one.
- The attention of a thread no longer lies (see `docs/propuestas/lo-que-hacen-los-otros.md`, block 1):
  `StopFailure` (a turn that ends on an API error, which does not fire `Stop`) ends the turn;
  `Notification` only means «waiting» when it asks something (`permission_prompt`,
  `elicitation_dialog`) — the idle notice a minute after each turn (`idle_prompt`) now means «done», so
  finished threads stopped piling up as «waiting»; a prompt records the conversation if `SessionStart`
  was lost; and a notice older than the recorded one does not overwrite it. `telar agente instalar --si`
  adds the new hook.
- «Done and not seen» (`sin_ver` in `telar hilos --json`): finished, and not focused since. The threads
  bar dims a done thread you already saw; ⌥S (`telar.siguienteQueEspera`) jumps to the next thread
  waiting on you — those asking something first, then the unseen ones, oldest first — and repeating it
  walks the queue.
- `telar hilo caidos [--horas N] [--seco]` reopens, with their conversation, the threads that were alive
  on this machine and have no window anymore (tmux died, the machine restarted). The node records who is
  alive every 30 s, and only announces a thread dead after missing it in two rounds in a row.
- Dashboard «tareas»: ▶ on a task with a card sends `/tarea <id>` to its thread (its project's, or the
  general agent's), so the agent starts on it with its context loaded; before, in an existing thread it only
  typed «Veamos <id>» without sending it. A document's checkbox is still only typed.
- `telar hilos --red`: además de los hilos de esta máquina, los de todas las demás según el registro del bus
  (`otras_maquinas` y `maquinas` en el JSON; en la terminal, una sección por máquina). Sin la bandera, `telar
  hilos` sigue viendo solo el multiplexor de aquí, que es lo que la extensión necesita. La skill `/hilos` ahora
  manda a `telar hilos --red --json`: antes decía que `remoto` daba la máquina, y un hilo preguntando qué había
  abierto no veía los del laptop.
- `telar persona` (`ver`, `crear`, `quitar`): dar de alta a un colega en el servidor — su usuario (sin el grupo
  `agentes`, que lee el correo archivado), su llave ssh, sshd sin contraseña ni túneles, un tope de memoria y
  CPU para toda su cuenta (slice de systemd), a qué hilos tuyos puede despertar por correo, y su propio uv,
  Claude Code y telar con las skills. Con `--seco` muestra el plan; con root lo ejecuta; sin root deja un
  guion que se corre con `sudo bash`. `quitar` cierra el acceso y conserva el home (`--borrar-home` lo borra).
  Cada persona queda anotada en `/etc/telar/personas.d/<nombre>.toml`. El plan es una función pura
  (`telar.persona`), así que se prueba sin root. Reemplaza al guion `servidor/alta-colega`.
- Threads bar: HILOS and ARCHIVO each get a search box under their header (by name or folder, accents
  ignored; ⏎ opens the first match, ⎋ clears) and three sort orders — ● urgency (priority, then waiting,
  then most recent), a-z name, ◷ last change (the last prompt to its agent). A second click on the
  active order goes back to telar's own. The search survives redraws; the order is remembered per group.
- A thread's last change is now when its agent was last asked something (a prompt or an errand):
  telar records `actividad` whenever an agent starts working, and `telar hilos --json` gives it. The
  threads bar shows and sorts by it (falling back to the agent's last state change); focusing a thread
  (`visto`) no longer counts as a change.
- A block item (an email) opens on its own in its tab instead of starting a thread: what it says, the
  tasks born from it (new item field `tareas`, each opening its card and coming back to the item) and,
  when it has `mensaje`, a «▶ procesarlo en un hilo» button.
  When a block's items carry `tareas`, the list shows them in a column of their own (comma-separated codes,
  «—» when none); closed ones are dimmed — pending means still in the current task list — and a
  «☐ con tareas pendientes» switch in the block's header shows only the items (conversations) with one.
  Items with the same `grupo` (the emails of one conversation) nest under the most recent, like Gmail:
  one row with ▸ and how many, unprocessed if any of them is, with all their tasks; ▸ unfolds the rest.
  In an open item, its title links to the original (`enlace`; for an email, its Gmail conversation). With
  the item field `reusar`, on macOS the link opens in an already open Chrome tab whose title or address
  contains it (the Gmail tab of that account), brought to the front; otherwise in a new tab.
  An open item's tasks use the same row as «tareas» (✓ ◉ ▶ ⋯, date, owner), so a task can be closed
  right after answering the email; the ones no longer pending show in one line that opens their card.
  An open item with `id` shows its detail — an email's body, five lines and «ver todo» — asked for when
  it opens: `telar bloque <clave> --item <id>` runs the block's command with `--item <id>` (it prints
  `{"texto": …}`).
- Dashboard «tareas»: a column of one-click actions before «⋯» — ✓ mark it done (the provider's
  `rol: hecha` action, or the checkbox of a document's item), ◉/○ share it with the team (moved out of the
  text) and ▶ take it to a thread. Dim until the row is hovered.
  ✓ answers at once: the row is struck through and the ✓ spins while the provider works, the row leaves
  the list as soon as it is done, and the list is reread in the background instead of being waited for.
  It costs one trip to the provider instead of two: `telar tarea <id> --rol hecha` runs the action with that
  `rol` without reading the card first (the extension falls back to the card when the other machine's telar
  does not know `--rol` yet).
- Modules (`[modulos.<nombre>] carpeta = "…"`): a folder with a `modulo.toml` that brings everything
  one thing needs — a dashboard tab (`[pestana]`, a block), a panel app (`[app]`), periodic jobs
  (`[periodicos.<x>]`, run in the module's folder) and a daily result (`[resultado]`, read where the
  periodic jobs live). telar adds them to what is declared by hand when reading the configuration, so the
  rest of telar does not tell them apart; a name declared twice is an error. Module jobs show in `telar
  periodicos` but are changed in their manifest, never written to `periodicos.toml`. `telar modulos` lists
  them; `telar config --json` gives `modulos`.
- Dashboard tabs are configurable (`[dashboard] orden` and `ocultas`): ⚙ lists every tab with ✓ to show or
  hide it and ↑↓ to move it, and the installed modules. Unnamed tabs go after, in their usual order, so a new
  module's tab shows up on its own. `telar config --pestanas "ahora,revisar,-plan"` writes it.
- Dashboard: the «hoy» tab is gone — its agenda and tasks had their own tabs. The dashboard opens on
  «ahora». Each `[bloques.<clave>]` is now its own tab (after «tareas», with an optional `tecla`), or sits on
  top of the «plan» tab with `en = "plan"`, shown only when it brings something. Shortcuts with
  `en = "hoy"` and «⎋ terminal» go in the top bar of every tab, and a provider that is down shows as a red
  line under the tabs, in every tab.
  A block's tab also shows the page's `lienzo` and `texto`, not only its rows (a plot), and does not
  rebuild a lienzo on the minute refresh.
- Threads bar: every group has a foldable header, in this order — AGENTES, HILOS (then your own
  `[secciones]`), EQUIPO, ARCHIVO, APPS. AGENTES and HILOS start open; EQUIPO, ARCHIVO and APPS start closed.
- Apps (`[apps.<clave>]`): what opens in the panel and is not a thread — a game, a catalog, a map —
  under an «APPS» header in the threads bar, one row each, marked while it is shown. Each has one source:
  `pagina` (a command that prints a page), `archivo` (a self-contained HTML filling the panel, with
  optional `memoria`) or `url` (a served page in a frame filling the panel, with «↗ abrir en el
  navegador»). `telar app [clave] [--json]` lists them or gives an app's page; the three sources come
  out as one page contract, so a new app needs no extension change. Pages gain a `marco` block (a served
  page in an iframe; the panel only frames the declared apps' origins) and `alto: "lleno"`. A section
  with only a `home` and no threads is an app: move it to `[apps]` with `pagina`.
- VS Code: what the team asks of you is now an **EQUIPO section in the sidebar** (not a dashboard tab): one row per request or
  priority suggestion; clicking one opens its actions — «preguntarle a Gestión» (hands it the request: it checks whether it already
  exists and decides new task / update an existing one / not applicable, using `telar equipo aceptar|existe|rechazar`, and answers in
  one line; the row shows «Gestión» while it works), «agregar como tarea», «es T123: contestarle su estado» and «descartar». New
  `telar equipo revisando ID`. The dashboard keeps only the ○/◉ share toggle in the task list.
- `telar equipo`: «does this request already exist?» now also compares **meaning**, not just words. A small model (`[equipo] semantica`,
  default `haiku`; `""` turns it off) reads the title and short description of the tasks with activity in the last 14 days
  (`dias`, at most 40) plus the ones the keywords matched, and says which already cover the request. It runs with no tools, outside the repo,
  and only the ids it returns count (and only if they were candidates). If the model fails, the keyword check still runs. The page says
  «revisando…» while it thinks (3–6 s).
- `telar equipo`: a request for a new task first checks whether it already exists. If a task the team sees looks like the same
  thing (same words, same numbers: «sesión 5» ≠ «sesión 6»), the person gets its state back (`409` + `existe`) instead of a new
  request, and can insist with `aunque_exista`. A look-alike the team doesn't see is kept for you: the dashboard lists it under
  the request («¿ya existe T123?») and one click (`telar equipo existe ID --tarea T123`) answers with that task's state.
- `telar equipo`: a teammate can also **ask you for a new task** (`POST /api/pedir`, a form on the page): it lands in the same tray
  and notifies the same way; accepting it adds a P2 task (`todo add`, tagged `equipo`, `origen: equipo:<person>`, with the context
  and date) and the person sees its state and number. Max 10 things waiting per person. VS Code shows it as «te pide una tarea»
  with «agregar como tarea» / «descartar».
- `telar imagen`: uploads the clipboard image (or a file) from this computer to `~/telar-entrada/` on a `[remotos]` machine over ssh,
  prints the path it has there and puts it on the clipboard — Claude Code's image paste only reads the clipboard of the machine it runs on,
  so a thread living on the server never saw the laptop's. Paste the path into the thread and Claude reads the image.
  `telar imagen --pegar PANE` is what a local tmux `bind -n C-v` runs so plain Ctrl+V works: it uploads the clipboard image and types
  its path into the pane (no image → exit 1, and the binding sends the usual Ctrl+V).
- `servidor/cartero`: `~/.cartero-permitidos` admite `usuario: hilo, hilo` — ese usuario solo despierta a esos hilos (un correo a otro
  queda en la Maildir, `RETENIDO … no puede despertar a «x»`); `usuario` a secas sigue valiendo para todos.
- `telar equipo`: a person you trust (a teammate) reads the tasks you tag `equipo` — title, state, priority, date, project and
  the `avance` line, never the body or history — and suggests raising a priority. `telar equipo servir` is its own small
  server (own port, own per-person token, no power over your agents); every suggestion lands in a tray, notifies the
  laptop (`telar enlace notificar`), and `telar equipo aceptar|rechazar ID` decides it (accepting raises the priority one
  level with the tasks CLI and leaves a note on the task). VS Code: with `telar.equipoRemoto` set, a warning notification
  (with «Ver» / «Aceptar»), a red row on the dashboard and an «equipo ◆N» tab until each one is decided. Config:
  `[equipo]` (docs/configuracion.md). The task list gets a ○/◉ to share a task from the dashboard; the person's link carries
  their key after the `#`; `servidor/telar-equipo.service` runs it.
- `telar web`: the first launch of each session shows a full-screen ASCII loom that weaves the screen in colour and
  clears a framed «« t e l a r »» in the middle (tap to skip; off with «reduce motion»).
- `telar web`: the installed app is an Android share target (`share_target` in the manifest): «compartir» → telar opens a
  screen to pick which threads receive the link (plus «lecturas», the reading feed) with an optional note; nothing is sent until
  you tap «enviar». New `/api/lectura` (`kichoro/bin/lecturas dejar`).
- A provider can live on another machine (`[proveedores.<x>] en = "<machine>"`): it is queried there over the bus,
  and `telar tarea` runs its card and actions there — the tasks are files on that machine, and reading the copy
  synced by git showed hours-old data while an action run here changed the copy. If that machine doesn't answer,
  the copy here is read and it says so; an action is not run here. `telar cambio <tema>` tells every machine that
  something changed (the tasks): each node marks it and the VS Code dashboard rereads at once; «tareas» shows when
  they were read and a «↻ actualizar».
- `telar web`: a ⌨ button in a thread's conversation shows its terminal (refreshed every 2 s) with keys to press — Enter, Esc,
  arrows, Tab, Ctrl-C — to get an agent out of a dialog that swallows what's typed (`/api/terminal`, `/api/teclas`).
- Dashboard «ahora» (`n`): the day's block in progress (or the next one), crossing the calendar with the day's plan,
  and only what fits it — a strategic block shows the day's focus, its tasks and its project; a meeting, the plan's
  card (decide, bring, ask), the latest preparation, what the previous minutes left «para la próxima» and its project;
  a commercial block, its project; free time, almost nothing; the close, the day's results and the agents' proposals.
  ‹ › move between blocks (and pin the view), «volver a ahora» follows the clock again; «elegir momento» opens the day's calendar
  column (the «calendario» one) to pick a block and see what «ahora» would show then; ‹ › there go to other days,
  with their calendar and plan. A block's class and project
  come from the plan (`clase`, `proyecto`, `tareas`) or are deduced from its title.
- `telar web`: a «× cerrar» button in a thread's conversation (two taps) archives it and ends its session, like
  `telar hilo archivar --cerrar`; resident agents can't be closed from the page. `telar hilo cerrar|archivar --cerrar` now also
  ends a thread that lives in its own session (the phone's, an encargo's), with the phone's sessions grouped to it.
- `telar web`: a «cal» tab with the VS Code dashboard's calendar in one column — day navigation, the plan's blocks merged
  with the events, each event's context and notes, «+ nota», «preparar o minuta» (asks the project when it can't tell) and a
  message to the general agent with the meeting as context. New `telar.webcal`; `/api/calendario`, `/api/evento/{nota,reunion,escribir}`.
- Dashboard: the «revisar» tab is now «tareas» (`v`, `tareas ◆N` when something waits for a decision): every pending
  item, with what an agent proposed on top, filters (all, ◆ to review, overdue, this week, in progress, no date, each
  with how many it would show given the search and the other filters, faded at zero), search, area and owner, and an icon above each column (code, project, responsible, text, date) that sorts
  by it, a second click going back to urgency. Rows without a card go to their thread. A project column (its client, or its
  name when the client is the company itself) says what each task belongs to; a click opens it in «proyectos». A «responsable» column shows who does each task (the person of
  this machine in gray when nobody took it); a click picks someone from the provider's `opciones` (new action
  `rol: dueno`) or a typed name. The owner filter gains «sin asignar», and «mías» counts the ones assigned to
  the person by name. `telar config --json` gives `persona` and
  `persona_nombres` (with git's user.name). A document's checkbox says who does it with `@owner(Name)` anywhere or
  `@Name Surname:` at the start, and when with `@deadline(YYYY-MM-DD)`; the markers (and `@prioridad(…)`) are hidden
  from the text, and pending rows carry `dueno` and that date as `cuando`. Without either, it is «sin responsable»,
  not the person's. `@para(…)` also says who; `@desde(…)` and the arrow before them are hidden. A document's checkbox
  gets its own «⋯» in «tareas» and «proyectos»: take it to its thread or a new one, open the README at its line, mark it
  done, or set who does it — `telar pendiente <ref> --hecho | --responsable NAME|none | --linea`, with `--esperado`
  (the text that was seen): it finds the line by its text and changes only that line, or nothing if it changed.
- Dashboard «proyectos» in two columns, like the calendar: the list on the left (search; sorted by status — active, negotiation,
  proposal, prospect, paused, closed — and then by name; an icon above a column sorts by it, a second click goes back; ↑↓ to move, ⏎ opens it
  with the agent, closed projects hidden behind a toggle; filters by folder, by area — `area:` in the document's frontmatter, shown once there are two —, by type, with a
  thread, with pending items); the client leads each name in color with the rest dimmed, and a status column (`Estado`, or `Etapa`
  for a deal, cut short) colored by kind. `telar proyectos --json` gives `cliente`, `estado` and `estado_completo`. A «⋯» on each row opens its actions: open it with the agent (or go to
  its thread), write to the general agent about it with its context, open the README, show the folder, copy the
  path, archive its thread and the chosen one on the right: its pending items (the
  checkboxes of its document and the provider tasks that name it) and its README, rendered. Provider rows carry
  `proyecto`, the folder the task says it belongs to, whether or not a thread is open there.
- One tmux session per machine: every thread is a window of the telar session, stamped with its own id
  (`@telar_id`), including agents' errands, periodic jobs, the phone, the web, and threads the laptop opens or
  resumes on a server (created over ssh). Another machine or the phone looks at a thread through a grouped
  session pinned to its window (`ver-<id>-<machine>`, `movil-<id>`): it lets go of the viewer if its window
  dies, and disappears when nobody looks. Remote windows are addressed as `@338/<stamp>`, so a window id that
  tmux reuses after a restart is never shown or closed. Threads that still have their own session keep working.
- The node publishes each thread's window address; the other machine follows a thread that changed address (no
  more «name · 2») or was renamed over there. `[agente] max_vivos` counts windows where nobody watches the
  telar session directly (a server). `[remotos.<x>] sesion` names the telar session over there.
- Dashboard calendar: a «‹ day ›» bar above the day column (and «hoy» to come back) moves between days with a
  click, ←/→ or [ ], loading that day's events, plan and notes; `telar hoy --dia AAAA-MM-DD` gives the agenda of
  another day.
- `telar web --escribir --nuevo`: the «hoy» and «hilos» tabs show the dashboard shortcuts (`[atajos.<tecla>]`, e.g.
  «⚑ correo»); one tap opens the thread (or hands it to the resident agent), like the key in VS Code.
- The line typed to wake an idle agent says what arrived («↯ mensaje nuevo · encargo de X: /correo»), so whoever
  looks at its pane sees the request; the content still enters through the hook. The dashboard says who got a
  shortcut's errand and asks before sending the same shortcut twice within two minutes.
- Dashboard «revisar»: each row has a «⋯» menu with the task's provider actions (close, new date, note, wait
  for…), run directly without opening the card; a task with no proposal left leaves the list.
- Dashboard «revisar»: the delay of each task is a button that reschedules it (tomorrow, the day after, next
  Monday, in a week, end of month, or a typed date), through the provider action with the new `rol: "fecha"`;
  the same picker opens from that action in a task's card.
- Dashboard calendar: a text field under the selected event writes to the general agent (`[agentes]
  sin_proyecto`) with the meeting, its project (remembered or deduced), what the plan and the notes say, and
  how to leave a note on the event; the request is kept as a note. `telar config --json` gives
  `agente_general`.

### Removed

- The Node panel: `telar panel`, `vscode/src/web/servidor.ts`, the `telar-panel` service templates
  (`servidor/telar-panel.service`, `.plist`), `vscode/media/app` and the `node-pty`, `ws` and `@types/ws`
  dependencies. The page is served by `telar serve --web` (Python): point `tailscale serve` at its port
  (8780) and an app already installed on the phone keeps working (same paths, key and cookie).
- `telar web`, the phone page: the web panel (`telar panel`) replaced it, and it does all it did — the day,
  the threads of every machine, reading and writing to them, the plan and its comments, opening threads and
  shortcuts, sharing from the phone, installing as an app. Gone with it: `src/telar/web/`, `webcal.py`,
  `servidor/telar-web.service`, its `/api/*` routes in the contracts, and their tests. The icons moved to
  `vscode/media/app/` (`docs/marca/hacer_iconos.py` writes them there).
- `telar movil`, the phone screen over mosh: the web page (`telar web`, and now the panel) replaced it,
  and nothing called it. Its window library (`telar.movil`) stays: `mirar`, the web, periodic jobs and
  other machines use it.

### Fixed

- The browser dashboard was blank (also a thread's folder, a file and «compartir»): with the thread's action bar
  hidden, the views fell into the bar's row of the grid, which measured nothing.
- Tasks from a `tipo = "tipo"` provider came without a card in the lists (`ficha: false`): a click sent the
  task to a thread instead of opening it, and «ahora» lost «lo que dejaron los agentes para decidir». The
  card is now offered for providers that have `detalle` or are of the `tarea` type.
- In the browser, letters typed into a dialog's field also reached the dashboard as shortcuts (and could
  launch one); the dashboard ignores keys while a dialog has them.
- Dim rows that are just text (configuration descriptions) were laid out as flex columns («Lee tu ⎵ gws»)
  and long ones ran off the right edge; they read as paragraphs now, and a long template in a row is cut
  with «…».
- Taking a thread to another machine (`telar hilo llevar`): the conversation travels gzip-compressed, the extension
  waits up to 15 minutes instead of 2 (it reported a failure while the copy kept going), and says what it is doing
  while the thread is visible nowhere.
- Renaming a thread leaves an alias from the old name to the new one: an agent that was already running keeps the
  old `$TELAR_HILO`, and its hooks wrote its attention to a ghost thread (the renamed one stuck on «trabajando»).
- `[ficha] maximo` cut the pending list counting done items: a README with five done checkboxes on top showed one
  of its five open ones. The provider's cap no longer cuts pending items, and a profile section's cap counts only open
  ones.
- `telar hilo olvidar <name>` (and `cerrar`, `archivar`, `retomar`… which take no value) ignored the name and
  acted on the current thread; the bare name is now the thread, and giving both it and `--hilo` is refused.
- telar targets a window with its session (`=telar:@3`): a bare `@3` could resolve to a grouped session someone
  is watching from another machine and move their screen; nor does it `switch-client` a client watching a thread
  through a pinned session.
- Cards: a paragraph that opens in **bold** was taken for a bullet and dropped, and the indented continuation of
  a bullet could be read as a section's paragraph; a bullet now needs a space after its marker.

## [0.1.13] — 2026-10-07

### Added

- `[resultados.<clave>]` and `telar resultado <clave> [day]`: what a skill leaves each day (a
  `YYYY-MM-DD.json` or `.md` in a folder), read from the machine where the skill runs (`en`, through the
  node over the bus), or from the local folder if that machine does not answer.
- `[notas]` and `telar evento nota|notas`: notes that skills and the person leave on the day's calendar
  events, stored on the machine that keeps them.
- Dashboard: a «plan» tab (`d`) with the day plan from `[resultados.plan]`, with arrows to other days, and
  a «calendario» tab (`a`) in two columns: the day with its events and the plan's own blocks on the left,
  the selected event with its notes on the right («+ nota» writes one).
- The day's agenda rows carry `fin`, `lugar` and `todo_el_dia` for calendar events.
- `telar reunion` hands the preparation or the minutes to the agent that receives what has no project
  (`[agentes] sin_proyecto`) and goes to its thread, instead of opening a tab per meeting; `--hilo-nuevo`
  keeps the old behaviour.
- `telar reunion --evento <id>` puts the calendar event's id in the message, so the agent can leave its note on
  it; the dashboard passes it. Paths in an event's notes open the file.
- A meeting goes to its project's thread when telar can tell which project it is: words of the title, the
  attendees' mail domain and attendees named in a project's README, each weighted by how rare it is (the
  own company's domain and the calendar owner do not count). When it cannot tell, the dashboard asks with
  the suggestions and why, every project to search, the general agent and «new project…»; the choice is
  remembered for the meeting series (`telar reunion --asistentes --proyecto --preguntar`, `telar.reuniones`).
- Calendar events carry their attendees (iCal `ATTENDEE`, gws `attendees`), without the calendar's owner.
- A lienzo can declare a `memoria` (an absolute `.json`): the panel hands it what it saved last time and stores
  what it sends back.
- `telar enlace hilos` shows the machine each thread lives on, and `telar enlace enviar` warns when the target
  lives on the calling machine. The `/hilos` skill says which path to use: `telar mensaje` to talk to a thread,
  `telar encargar <agent>` for what only another machine can do.

### Fixed

- A remote thread whose window closed (the laptop slept, the network dropped) is reopened by the node while
  its session lives on the other machine and the thread was not archived on purpose.
- A «trabajando» state unchanged for 45 minutes is treated as stuck: the node nudges the agent instead of
  waiting for a Stop that never comes.
- The notification hook finds its thread through the `@telar_hilo` mark of its own tmux session when the
  agent was started without `$TELAR_HILO`, as the mailbox hook already did.

## [0.1.12] — 2026-10-05

### Fixed

- The mailbox hook no longer depends on `$TELAR_HILO` alone. An agent started without it (a `claude` launched
  by hand inside a thread's tab) got the «↯» and never the messages; now the hook also tries the conversation
  already recorded, the `@telar_hilo` mark of the tmux session the pane lives in, and the multiplexor's tab.

## [0.1.11] — 2026-10-05

### Added

- **The bus** (docs/propuestas/bus.md): with `[bus] url` (NATS with JetStream on the always-on machine) and the
  `bus` extra, `telar nodo` connects each machine outbound, picks up the messages of the threads that live there,
  leaves them in the thread's local mailbox and lets it know; it publishes its threads' state and hears the
  others' at once. `telar mensaje <thread|agent> "…"` sends to any thread on any machine; `telar encargar` uses
  the bus when there is one. Messages wait for a sleeping machine, arrive in order and are not duplicated.
- The mailbox enters the conversation through the agent's hooks, never typed: `Stop` (the agent was working: it
  does not stop and gets the messages) and `UserPromptSubmit` (an idle agent gets a short fixed «↯» typed, and
  the content as context). Installed by `telar agente instalar`.
- `servidor/telar-bus.service`, `servidor/telar-nodo.service` and `servidor/telar-nodo.plist`.
- `telar pendiente` (and the dashboard's «↩ escribirle a Claude» on a task) finds the thread whose folder holds
  the file the item links to (its `url`), the most specific first; a one-level folder is an area and does not
  decide. With no such thread here, it looks in the other machines' mirror snapshots and writes to that thread
  through the bus.
- Threads of the same person talk without asking her. `telar agente instalar` allows, in Claude Code's
  `permissions.allow`, only the commands to talk and read (`telar mensaje`, `encargar`, `hilos`, `ficha`,
  `hilo leer`, `nodo estado`); `desinstalar` removes exactly those. A message from a same-person thread is
  delivered as a colleague's request (do it if it is your trade and reversible; what goes out to the world,
  what cannot be undone and what is not yours still needs the person), one from another person stays a mere
  message. The context and the `/hilos` skill say asking and delegating is expected.
- Brakes instead of approval: each message carries `persona` and `saltos` (how many thread-to-thread hops
  since the person last spoke; her own prompt resets it). Past 6 hops, or past 30 messages an hour from one
  thread, the message is held: it stays only in the bus log (`TELAR_REGISTRO`, two weeks) until the person
  releases it (`telar mensaje --soltar <id>`). `telar mensaje --registro` and `--retenidos` show the log; the
  dashboard's «agentes» tab lists the messages between threads with a «soltar» link on the held ones.
- With a bus, the rest goes through it too: `telar enlace enviar` leaves the message in the thread's mailbox;
  the web writes to a thread on another machine as a `persona` message and reads its conversation with an
  rpc to that machine's node (honoring `[enlace] no_leer`); mail between threads of the same person
  (`usuario+hilo@…`) is a bus message, so Postfix and the cartero stay only for other people. Each node
  publishes its mirror snapshot every 30 s and saves the others' where `telar web` reads them
  (`telar espejo publicar` becomes a no-op), and it publishes when a thread stops living there: the other
  machine opens the window of a thread born remotely and closes the window of one whose session ended, at
  once instead of every three minutes (with a bus, `telar remotos traer --sondeo`
  and `telar remotos atencion` answer `por: bus` and the extension stops both polls). The threads' context and the `/hilos` skill point to `telar mensaje`.
- A periodic process with `agente` hands its prompt to the agent's mailbox through the bus when there is one (the
  node where the agent lives opens or nudges it); if the bus does not answer, it falls back to typing and says so.

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
- `telar pendiente --proveedor`, and providers asked one at a time until the task turns up: taking a task to its
  thread no longer downloads the whole calendar (5 s → under 1 s from the dashboard). VS Code shows a progress
  notification while a task goes to its thread or a shortcut runs.
- `telar remotos atencion`: copies the remote threads' semaphore (working, waiting, done) here, since their hooks run
  over there; VS Code calls it every 20 s, so a remote thread shows when its agent is working. Each thread's JSON
  carries `atencion_desde`.
- VS Code thread list: fixed columns — priority · semaphore · ⇄ · ✉ · name · last activity — each icon in its own
  column whether shown or not, so names line up; the right side is only the last activity (last focus or the agent's
  last change).
- An agent can live somewhere else than the others: `[agentes.<folder>] en` («aqui», a remote, or an enlace). With an
  enlace, `telar encargar` goes through the door's new `encargar` verb (off by default), so the server can hand work
  to an agent that lives on the laptop. `[agentes] abrir = "tab"` opens an agent's thread as a regular thread of the
  list (the laptop) instead of its own tmux session (the server); encargos and their queue work the same.
- A task action with `mensaje` and `al_hilo: true` sends the message to the thread where the task is worked — its
  project's (resumed if asleep) or the `[agentes] sin_proyecto` agent — instead of opening a new thread.
- Task owner: a provider task may carry `dueno` (who does it, if not you); the task lists in VS Code (sidebar, today,
  review) get a «todas · mías · de otros» filter and show «→ Name» before a task someone else owns.
- `[agente] max_vivos`: a cap on live own sessions (periodic, encargos, the phone) on a machine; before opening one,
  telar closes the idle ones nobody is looking at, oldest first, residents last. Their conversations stay on disk.
- `telar remotos traer` closes local windows whose remote session no longer exists (closed by `max_vivos` or from
  the phone): they showed a frozen screen and counted as alive. The thread keeps its conversation and ▶ resumes it.
  Nothing is closed when the other machine does not answer.
- Agents learn the basics: the start-up context names `telar hilo leer` and the resident agents with
  `telar encargar`, and the `/hilos` skill explains both.
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

- The mail carrier (`servidor/cartero`) read a message with no declared charset as us-ascii, so every accented
  letter arrived as «��»; it now tries UTF-8 first. `telar correo enviar` always declares `charset=UTF-8`.
- `telar enlace enviar` and encargos typed a long text into the agent's prompt, which could lose its beginning;
  past 600 characters the text is left as a file and a short line pointing to it is typed instead.
- A task card with ten actions (⏎ plus 1–9) failed the page contract, which allowed nine.
- `telar remotos traer`: a session over there named like a sleeping thread here is that same thread (it moved):
  it is adopted under its name instead of showing up again as «· 2».
- `telar hilo llevar`: a long conversation (tens of MB over a slow uplink) was cut at a fixed 60 s and the other
  machine kept the truncated file. The wait now grows with the size, and the receiving side refuses to store a copy
  whose length does not match.
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

[Unreleased]: https://github.com/nicorivas/telar/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/nicorivas/telar/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/nicorivas/telar/compare/v0.1.13...v0.2.0
[0.1.13]: https://github.com/nicorivas/telar/compare/v0.1.12...v0.1.13
[0.1.12]: https://github.com/nicorivas/telar/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/nicorivas/telar/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/nicorivas/telar/compare/v0.1.9...v0.1.10
[0.1.4]: https://github.com/nicorivas/telar/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/nicorivas/telar/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/nicorivas/telar/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/nicorivas/telar/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/nicorivas/telar/releases/tag/v0.1.0
