# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic
Versioning 2.0.0](https://semver.org). While in 0.y.z, anything new or breaking bumps y, and only fixes and
cosmetic changes bump z; which one, and what counts as the public interface, is in docs/publicar.md. A tag
`v0.2.0` releases the Python package; the release workflow refuses to run if the tag and `telar.__version__`
disagree. Up to 0.1.13 the VS Code extension shared the version number.

## [Unreleased]

## [0.16.0] — 2026-11-26

**The projects screen was rebuilt** with the house pieces: rows and sections from edge to edge, a detail with its own
bar that reads the README in telar's prose, a screen of its own in one column, and three subviews (clients, commercial
and internal) when the mode declares deals or initiatives. **«tareas › esperando»** lists what others owe you, person by
person. **`telar serve` is faster and no longer stays alive and deaf**: `GET /hoy` went from 14 s to 3.7 s, the heavy
reads run in a process of their own, and a part that falls takes the service down so that its supervisor starts it
again. The **bar of every screen holds only its title and its buttons**. **Module canvases can use the page's
components**: tabs, search bar, filters, its menu and telar's prose. **`telar mensaje name@machine`** reaches that
thread on that machine, and a name nobody reads is refused. The component catalog has prototypes of a **team** view and
of **routines**, for review before building them.

**Upgrading from 0.15.** What changes, and what to do:

- **A message to a name that is no thread or agent of yours is refused.** `telar mensaje`, `POST /mensajes` and
  everything that sends through them check the name against the threads every machine knows of (live, asleep or
  archived) and the bus state; an unknown one is refused (a 404 over HTTP) with the names that look alike. It used to
  be left in a mailbox nobody reads and reported as delivered. `name@machine` now means `hilo:name@machine` (it used to
  be the mailbox of `name-machine`). Scripts that wrote to made-up mailbox names must write to a real thread or agent.
  When the threads cannot be read, it sends as before.
- **`telar serve` exits with 1 when one of its parts ends without being asked.** Run it as the service `telar instalar`
  sets up (launchd on macOS, systemd on Linux), which starts it again; a `telar serve` started by hand in a terminal
  now ends instead of staying up without answering.
- **What the service returns can be up to 30 s old.** `telar serve` keeps what the providers return for 30 s. A change
  made through its API forgets it at once; one made elsewhere (the CLI, a file edited by hand) shows within 30 s. The
  CLI always reads fresh.
- **The bar of a module's tab no longer shows its subtitle.** It carries only the name and ↻; the subtitle goes in the
  name's tooltip. A module that showed a count or a state there should show it in its own body (docs/contratos.md).
- **`telar pendientes` lists a project's items once.** With several threads linked to the same folder, its items came
  once per thread; now they come once, with the live thread if there is one. `--hilo` still lists them for every thread
  in that folder.
- **Additions, nothing to do.** The `tarea` provider, and each row of `telar pendientes` that carries `espera`, gain
  `desde` and `ultimo`. New settings: `icono` in `[modos.<n>]`, a custom mode's place from `[mundos.<n>] modos`, several
  fields in `agrupar_iniciativas`, and `sigue` in a `comprobar` check of `.telar/despliegue.yaml`. A canvas gains
  `"componentes": true`, `window.lienzo.pedir("opciones")` and `window.lienzo.pedir("prosa")`. Agents telar starts run
  with `FORCE_HYPERLINK=0`, unless the person set it.

### Added

- **Projects has three subviews: clients, commercial and internal.** When the mode declares deals or initiatives and
  the world that is set has some, the projects screen gets tabs in its bar (before the modules inside it, like gantt):
  **clients** is the projects list; **commercial** lists the deals in sections by how they are going according to their
  document (negotiation, proposal, diagnosis, prospects, paused, lost, won), with a circle filled by how far each got
  and when its folder was last touched; and **internal** lists the initiatives. Each initiative says my role from its
  owner («lo llevo», who leads it, or «sin definir») and its next step: its next decision, else its most urgent open
  task, else its most urgent pending item or the first open checkbox in its README, else «sin próximo paso», marked.
  Each group is a section, its ideas go last in a folded submenu, and finished and discarded ones are left out; the
  filters «me toca» and «sin próximo paso» sit under the search bar. The set world counts even in the «todo» mode, so
  in a world without deals or initiatives projects stays a single list.
- **`agrupar_iniciativas` takes several fields, in order of preference.** With
  `{frontmatter:funcion}, {frontmatter:programa}` it groups by function when the files say it, and by programme
  otherwise.
- **«tareas › esperando»: what others owe you, by person.** A third view of the tasks tab, after focus and list, with
  the standard bar, search bar and filters (`vistas/dashboard/esperando.ts`). It lists the tasks someone else holds:
  those waiting on a person (grouped by who they wait on, with a clock) and those delegated to someone else (grouped
  by their owner, with a person icon in the colour of what belongs to others); the person's own tasks stay out. Each
  person is a folding section, oldest debt first; each row says the deadline and how long the other person has had it,
  and under it, dimmed, the last thing that happened. A click opens the task's card, and ⎋ comes back. Filters:
  waiting, delegated, overdue. It reads the same tasks as the other views: no second store of commitments.
- **The task provider tells since when someone else holds a task, and what happened last.** For tasks that wait on
  someone or have an owner, the `tarea` type provider adds `desde` (the history line that put it on hold or gave it an
  owner, or its creation) and `ultimo` (the last history line that isn't a bare field edit, cut at 240 characters), and
  each row of `telar pendientes` carries them with `espera`. Other rows don't grow. A page talking to an older telar
  shows only the deadline.
- **A module's canvas can use the page's components.** With `"componentes": true` in its `lienzo`, the page inlines the
  components' stylesheet (with the page's icon font as `telar-iconos` and the theme's tokens) and
  `window.lienzo.componentes`, which builds their HTML with the same props as the page (`pestanas`, `barraBuscar`,
  `filtros`…). Tabs that don't fit go to a «⋯» on their own, the search bar's ✕ clears it, and the «⋯» and a folded
  filter group open the page's menu. `await C.prosa(markdown, { ruta })` gives a document's HTML in telar's prose, the
  same as the document viewer in reading mode: the page draws the markdown, so markdown-it stays out of every canvas,
  and its links work by themselves (a relative one opens that file in the viewer, `#…` scrolls to that heading, an
  outside one is not followed). A telar without it ignores the field and the canvas draws what it drew before
  (docs/modulos.md, «Las pestañas y los filtros de telar»).
- **`window.lienzo.pedir("opciones")` and `pedir("prosa")`.** A module's canvas can open the page's menu with its own
  options (`{opciones: [{nombre, ayuda?, icono?, color?, apagada?}], titulo?, x, y}`) and gets back `{indice}`, or
  `null`; and it can have a markdown drawn as the viewer draws it (`{markdown}` → `{html}`). Neither needs permission,
  since they only show.
- **A custom mode can have its own button in the mode band.** When the current world lists it in `[mundos.<n>] modos`,
  it gets a button after the attitude that precedes it in that list (`["tactica", "estrategia", "entradas", "foco",
  "todo"]` puts it between strategy and focus), with the icon of its new `icono` setting (a page icon by name, such as
  `bandeja`; empty, its base's). Without `modos` in the world, the band keeps the four attitudes, as before.
- **`sigue` in a `comprobar` page check of `.telar/despliegue.yaml`.** After the first good answer, the page is asked
  again that many seconds later and must still answer, or the deploy fails («contestó, pero a los N s ya no»). telar's
  own declaration waits 15 s on `/pagina.json`: a service that started and fell 8 s later used to pass.
- **Prototypes of a team view and of «tareas › rutinas», for review before building them.** In the component catalog,
  with made-up data. **Team** (`/componentes#equipo`): one row per person (weekly load, open commitments, an overdue dot
  and the next 1:1) and, when opened, their card, with the 1:1 notes in a tab of their own, fetched only with a click.
  **Routines** (`/componentes#rutinas`): what repeats (a daily plan, one-on-ones, a weekly review…) and whether it was
  done, computed from the proof each routine declares, in one section per state, with a ✓ by hand only where there is
  no proof. `#…/ver/…` shows each as the whole page, for screenshots. The proposals, with where each piece of data would
  come from and the decisions left, are in `docs/propuestas/equipo.md` and `docs/propuestas/rutinas.md`; nothing of
  them is built.
- **An audit of the projects tab against the design system** (`docs/propuestas/auditoria-proyectos.md`). Measured with
  `scripts/medir.py` at four widths and on a phone: the serious and minor gaps, what already complied and a proposed
  order. The rebuild of the projects screen in this version follows it.

### Changed

- **The projects list is built with the house pieces, edge to edge.** Each row is an `item()` and each state a
  `seccion()`, the same as the thread bar: the header at the bars' height, in the headers' ink, with its count and its
  line; it folds, is remembered, and opens what matches while searching. Rows and lines go from the screen's edge to
  the detail, at the standard row height. The state column is gone (the section header says it); the client leads,
  the name takes what is left, and the due date and the pending count go at the end and give way first, by the list's
  own width, so the name is never lost: at 1024 px it went from one letter to over twenty. The sort moved to the search
  bar (`orden()`, as in tasks), the area and «closed N» to the standard filter row (the area folded, with «all»), and
  the ⋯ only shows on hover. Initiatives too: peso and state in their slots, the next decision after the name, each
  programme a submenu. The wide table (↔) is a view in the projects bar, next to gantt, no longer a button in the
  search bar.
- **The project detail starts with a screen bar, and a full-height line divides it from the list.** The bar is the
  same as every screen's: the project's name as written, on one line and cut with «…» (whole in its tooltip), and on
  the right only icons, each with its tooltip: go to or resume its thread, consolidate its pending items, open its
  README and ⋯. How it is going (state, stage, dates, its source) is the first row of the body, on one line. The
  divider between list and detail is its own line, the whole height of the screen.
- **The project detail reads its README in the shared prose, and its summary uses screen sections.** The document tab
  shows the whole README, without its frontmatter, in the prose of the viewer and of a thread's reading, instead of
  hand-made folding sections. The summary's titles are the sections of a screen, with a line from edge to edge and the
  count dim. The screen's spacing and colours are the design tokens.
- **In one column the project detail is a screen of its own.** On half a screen and on the phone, choosing a project
  shows only its detail, with «‹» in its bar (or ⎋) to go back to the list where it was; it used to sit under the
  whole list, with a scroll of its own. One column now starts earlier, so at 1024 px the list has the whole width.
- **The first row of every screen holds only its title and its buttons.** The bar of each dashboard screen (todo,
  táctica, ahora, te esperan, tareas, correo, calendario, leer, proyectos, the module tabs, a section, a conversation)
  no longer shows a summary or a state next to the title: the title goes on the left, and the views and actions on the
  right. What the summary said goes in the title's tooltip; when to reload, in the ↻ tooltip; which one of how many, in
  the ← → tooltips. What still matters moved into the screen: the day the calendar shows, when it is not today, opens
  the day; a simulated «ahora» and a táctica rehearsal say so in their body; «te esperan» ends with how many wait in
  the other worlds. `npm run prueba:pantalla` checks that no bar carries anything else.
- **The thread bar's groups are built from one list-section component.** `seccion()`, `submenu()` and `secciones()`
  (`componentes/seccion.ts`) draw every group of the thread list (agents, threads, archive, other worlds) with the same
  header, tools, rows, empty row, fold and counts; the bar looks the same as before. The component catalog
  (`/componentes`) shows the group and its anatomy.
- **The service keeps what the providers return for 30 s.** The page, the phone and the service's own refresh asking
  for the day at once share one query (concurrent ones wait for it instead of repeating it); any API request that
  changes something forgets it, and a query with failures is not kept. The CLI always asks.

### Fixed

- **`telar serve` no longer stays alive and deaf when one of its parts falls.** On 26-nov-2026, right after a deploy,
  the bus connection was reset just after connecting, the node's JetStream setup timed out and the node task ended;
  `telar serve` then stopped the other servers, and the page server, which had already closed its listening socket,
  waited forever for the page's `/eventos` stream to close, with nothing in the log. Now whatever ends without being
  asked (an exception or a plain return) is logged with its traceback, the rest is stopped with a bounded wait (5 s per
  server; `/eventos` and `/dev/cambios` end by themselves on shutdown) and the process exits with 1 so launchd or
  systemd starts it again; a guard exits it anyway if it has not managed to in 20 s. The worker process for heavy
  reads is terminated with it, instead of being left orphaned.
- **The bus node retries its JetStream setup instead of falling.** A cut right after connecting (the streams and
  key-value stores not answering) is written in one line and retried with growing waits; `--una-vez` still fails
  fast, and the connection is closed when it does.
- **`telar serve` no longer takes ten times longer than the CLI under load.** Routing the day's tasks resolved every
  thread's folder tens of thousands of times per request (16 of the 21 s of `GET /hoy`); each path is now resolved
  once per request, and so are the agents' links and the repos' folders. `GET /hoy` goes from 14 s to 3.7 s on page
  open, and its CPU from 11.8 s to 0.3 s. Frontmatters are cached by their text, so `GET /proyectos` drops from 4.4 s
  to 0.7 s of CPU.
- **The thread list and the config answer while the heavy reads compute.** In the service, the project list and the
  repository-wide pending items run in a separate process (`telar.aparte`), so their CPU doesn't hold the GIL the
  other requests need. With six heavy requests at once, `/api/hilos` answers in 0.3 s (median, was 0.95 s) and
  `/api/config` in 0.08 s (was 0.43 s).
- **The page asks for what it needs to draw first.** At most three heavy requests (the day, waits, blocks,
  projects…) go out at once, so the thread list never queues behind them in the browser's six connections; the
  first thread read goes without documents, the config is fetched alongside it instead of after it, and the
  `/config` the page asked for six times on load goes out once.
- **A deploy no longer leaves the page blank.** What the page last read (threads, the day, projects, waits) stays in
  the tab's session storage, and after a reload it is shown at once while everything is read again: the sidebar has
  its threads in 50 ms instead of waiting for the restarted service.
- **`telar mensaje Telar@laptop` reaches the thread «Telar» on laptop.** Only the address `hilo:name@machine` split
  off the machine; a bare `name@machine` went to the mailbox of its normalized form (`telar-laptop`), which nobody
  reads, and the command still answered «en su casilla». Now `name@machine` means the same as `hilo:name@machine` (an
  agent is found by its name with or without a machine, also in `telar encargar`), and a machine that does not exist
  or does not have that thread is refused with the threads that look alike, or where that one lives.
- **A message to a name that is no thread or agent of yours is refused instead of left in an orphan mailbox.** `telar
  mensaje`, `POST /mensajes` and everything that sends through them check the name against the threads every machine
  knows of and the bus state; an unknown one is a 404 with the similar names, and `persona@machine` (the sender of what
  the person types in a terminal) says it has no mailbox. The confirmation names the thread it reached when it was
  written another way.
- **A thread opened by a periodic no longer reports each turn to «periódico <name>».** The periodic that opened it
  counted as its parent, so the node left a notice per turn in a mailbox nobody reads; now only a real parent (the one
  the periodic declares) is told.
- **A project's pending items show once, not once per thread.** When several threads were linked to the same folder
  (the project's own and those of a meeting or a topic), `telar pendientes` read its document once per thread: the
  projects view showed every item four times (96 rows for 24), and an item with an id answered 409 as if it had been
  copied. Now each document's items go once, with the live thread if there is one, and `--hilo` still lists them for
  every thread in that folder.
- **A markdown link in the terminal of a thread from another machine opens with a click.** Claude Code writes
  `[Doc](https://…)` as an OSC 8 hyperlink that shows only «Doc», and mosh drops OSC 8 entirely, so a server thread
  watched from the laptop or the phone showed «Doc» with no address behind it. Every agent telar starts now runs with
  `FORCE_HYPERLINK=0` (unless the person set it), so Claude Code writes «Doc (https://…)» and the page finds the
  address however it arrives. Agents already running get it the next time they start.
- **A link the browser refuses to open no longer fails in silence.** Every outside address the page opens in a new tab
  (links in a thread's terminal, OSC 8 hyperlinks and bare URLs, links in the page and in the file viewer) now goes
  through one place that opens it right in the click, and that can tell whether it opened. Before, opening with
  `noopener` made `window.open` return nothing either way. If the browser blocks it (Safari blocks a tab opened after a
  network wait, or when its pop-up setting for the site says so), a notice says so and offers an Open button that opens
  it in its own click. The new tab still gets no `opener` and no `Referer`. On the dashboard, a link no longer waits
  for the settings screen before opening. Tests: `npm run prueba:abrir` (a fake Safari), `prueba:abrir-webkit` (WebKit,
  Chrome and Firefox with xterm.js) and `prueba:abrir-safari` (macOS: Safari's own engine with its pop-up blocker).
- **A long address in the reading view fits on a phone.** It ran off the right edge, and its end could not be tapped;
  links in prose and the question above the answer now break anywhere.
- **The bar headers, the alert strip and the pulse line are the standard row height.** The section headers of the
  thread bar (DASHBOARD, AGENTS, THREADS…), the alert strip on the phone and the pulse line now measure
  `--pantalla-barra-alto` (26.3 px; one pixel more when a header also carries the line above), with the pulse's text in
  the middle, instead of one item line (18.9 px). An extra pixel came from the icon font: its taller line box stretched
  every row with an icon (16.9 px rows became 17.9 px); icons in rows, the strip and the pulse now use their own line
  height. `npm run prueba:barra` and `prueba:pulso` check the rules against the token.
- **A sleeping thread is recognized on Linux again.** `telar.dormir` reads the process table with `ps -ww`: without
  it, the procps-ng `ps` sometimes cut the command lines at 80 columns even with its output going to a pipe, depending
  on the process environment, and the mark of a sleeping pane (at the end of its `sh -c`) was lost.
- **The test suite no longer reads the machine it runs on.** The tests point `/etc/telar/puerta.toml`, the hosted
  and people registries, `/run/telar` and the root helper's spool at a session folder that does not exist: on a
  machine where the gate is installed, 38 hosting tests failed asking for a Tailscale account.

## [0.15.0] — 2026-11-25

**Moving a thread to another machine was rebuilt in four stages**: the conversation travels over the bus in chunks
(only what is missing, resumable, with no size limit), the move looks only at the thread's own unpushed work and offers
to upload it, every thread has one owner with an epoch written in the bus, and a thread whose machine is off can be
continued from the copy left on another. Files get **comments** an agent can work on, in a **document viewer** that
opens as a window over what you were looking at. Modules can open **windows** on the page (a WhatsApp focus chat, to
reply without leaving what you're doing). **Tabs** and a **message bar** are house components, and tabs that don't fit
go to a «⋯» menu. A thread keeps its next prompts in a **notes** tab until it's their turn.

**Upgrading from 0.14.** What breaks, and what to do:

- **Update every machine on the bus together before moving threads.** A move now copies the conversation with new
  node requests (`replica-estado`, `replica-escribir`, `replica-cerrar`) and hands the thread over with its owner and
  epoch (`hilo-llegar` carries `dueno`). A machine on 0.14 can neither receive a thread from 0.15 nor send one to it
  («el telar de allá es de antes»). Update with `telar desplegar`. Over ssh (`[remotos]`), threads now move only to a
  machine that is not on the bus.
- **A thread's record in the bus has an owner and an epoch.** Records in `TELAR_HILOS` carry `dueno` and `epoca` (and
  `cede` and `mudanza` while a move is under way), written conditioned on the revision the node read, and a node no
  longer publishes a thread whose record belongs to another machine. Records written by 0.14 are rewritten once, on
  the node's first round after the update. Anything reading `TELAR_HILOS` should take the owner from `dueno` (`maquina`
  in an older record). If the conditioned write misbehaves, `[bus] publicar = "simple"` brings back the old one.
- **`telar commit` takes paths relative to where it runs, like git, and exits 4 when it committed nothing.** A path that
  neither exists nor is in the repository commits nothing and exits 2 (it used to be dropped silently, with «subido»
  and exit 0). Nothing to commit in the given paths exits 4 with `estado: "nada"`. The JSON gains `subidos`. Scripts
  that pass root-relative paths from a subfolder, or that took exit 0 for «nothing to do», need adjusting.
- **Moving a thread no longer archives it on the source machine, and its progress has new steps.** In
  `<estado>/llevar/<hilo>.json` and `GET /mudanza`, `paso` is one of `revisar`, `esperar`, `subir`, `detener`,
  `copiar`, `abrir`, `cerrar`, `listo` or `falla`, in that order (`cerrar` went from second to last), with new fields
  `total`, `por_mandar`, `mandados`, `pendiente`, `destino` and `subido`. Without a terminal, `telar hilo llevar` now
  fails when the thread has unpushed work, unless given `--subir` or `--si`.
- **`[terminal] fondo = "telar"` now reads as `"ninguno"`.** The animated loom around the terminal is gone, and
  `ninguno` (the theme's background) is the new default. A color, an image or a module's `[fondo]` work as before.
- **New keys in `modulo.toml`.** `[ventanas]` (`consulta`, `acciones`) and `buscador` in `[objetos.<tipo>]` need telar
  0.15; an older telar ignores them. `telar config --json` and `GET /config` give each module's `buscables`, and a
  module's commands receive `TELAR_MUNDOS`.
- **Additions, nothing to do.** `telar hilos --json` gains `borradores` and, for archived threads, `dueno`; a machine's
  photo gains `archivados`, `conv_bytes` and `conv_crecio`. New HTTP routes: `/ventanas`, `/hilo/registro`,
  `/hilo/seguir`, `/hilos/borradores` and `/comentarios`. Run `telar agente instalar` once to get the `/comentarios`
  skill.

### Added

- **Notes: a thread's next prompts, kept until it's their turn.** A «notas» tab in a thread's right column (next to
  ficha, códigos and contexto) keeps an ordered short list of what you want to tell its agent next, each one to send,
  edit, copy or delete. What you write saves itself. Sending one leaves it typed in Claude Code's input without ⏎, for
  you to review (⌥⏎); ⌘⏎ sends it. If the agent is in the middle of a turn, the page offers to wait, and the note goes
  out by itself when the turn ends, even with the page closed. The thread's row shows a faint icon and count, and the
  tab shows a dot when the thread finished with notes waiting. ⌥B opens the tab with the focus in the box; on the
  phone it opens in a window. Notes live in the state of the thread's machine, so they survive a reload, show on the
  phone and travel with the thread. `telar hilo borradores [--agregar|--mandar N [--enviar] [--esperar]|--borrar N]
  [--json]`, `GET|POST|DELETE /hilos/borradores` and `POST /hilos/borradores/mandar`.
- **Comments on a file, for an agent to work on.** In the document viewer, select text and press c (or the button by
  the selection) to write what has to happen there. Comments live next to the file, in `.<name>.marginalia.json`, in
  the format of the editor extension that introduced it (each reads what the other writes), and the file itself is
  never touched. The anchor is the quote, not the line: the commented source text plus 48 characters of context on
  each side, found again by five paths (exact, context, normalized whitespace, approximate by bigram similarity,
  neighbourhood), and «sin ancla» when none fits. A selection on the rendered markdown is mapped back to the source,
  through `**`, links, list markers, tables and code. Plain text files work too; .html does not.
- **`telar comentarios listar|ver|responder|resolver|reabrir [--json]`.** An agent finds the open comments of a file,
  a folder or a repository, reads them with their anchor resolved (line, method, confidence, and what the place says
  today if it changed), replies and resolves; with `máquina:` in front, on that machine through the bus (node request
  `comentarios`). `GET` and `POST /comentarios` do the same for the page, and `comentario:<file>#h1` is its address in
  `telar objeto`. The comments file is committed and pushed alone: from the page and the node 15 seconds after the
  last change, from the command right away. The `/comentarios` skill tells an agent how to attend them. Format and
  contracts in docs/contratos.md, «Los comentarios de un archivo».
- **Continue a thread here while its machine is off, from the copy left here** (`telar hilo seguir <thread> [--si]`,
  `GET`/`POST /hilo/seguir`). It is offered only on a machine that has a copy of the conversation and only while the
  owner is off (its photo expired and its node does not answer); with the owner online it is «traer aquí». Before
  taking it, it says how old the local copy is and how much the owner's weighed when last seen (each photo now carries
  the size of each thread's conversation and when it last grew, nothing of its content). On the page, the menu of a
  thread whose machine is off shows «seguir aquí», with a panel that says what is missing.
- **The returning owner cedes on its own.** On its first round back, a node that finds one of its open threads owned
  by another machine closes its agent, sets its copy aside if it grew after the copy the other continued from
  (`<sid>.de-<machine>-<date>.jsonl.bak`), and says so in the page's notice strip with a short report, until it is
  marked as seen.
- **Archived threads of the other machines, in ARCHIVO.** A machine's photo carries its archived threads apart
  (`archivados`, a few fields each, no conversation or path), and the sidebar lists them after this machine's, with
  their machine and «retomar en M», which opens them there through its node, never from the copy here. A thread
  archived here that the bus says belongs to another machine shows that machine (`dueno` in `telar hilos --json`).
- **Windows a module asks to open on the page (`[ventanas]` in `modulo.toml`).** A module declares a query that says
  which windows it wants open now, and the queries its buttons may run (`POST /ventanas/accion` runs nothing else).
  The first one: a message that arrives in a WhatsApp focus chat, to reply or snooze without going to its tab. The
  page asks `GET /ventanas` every 10 s while visible (3 s with one open, at once when another tab acts), and the window
  shows the last lines, a reply box (⌘⏎, with «enviando…», «enviado» or why not), buttons that run a query, open an
  item of the module's tab (`window.lienzo.item`, the `lienzo-item` event) or open the instruction window, and drafts
  waiting for approval (edit, approve, discard). An action can show an icon (`icono`, `corto`) instead of its word.
  Acting in one page closes the window in the others. Format in docs/modulos.md, «Sus ventanas».
- **Windows stay in their world and don't steal keys.** A module window only shows what belongs to the world on the
  page, and changing worlds closes one of the other. If you are typing, or the focus is in a field, it comes out quiet
  (no backdrop, no focus) until you click it or pause.
- **«No molestar».** A bell in the header band (and in ⌘K) silences module windows on this machine; a meeting in
  progress on the calendar does the same on its own. Meanwhile only the count is shown, and when it ends, what arrived
  comes out.
- **Objects of a module in ⌘K.** `[objetos.<tipo>] buscador = true` (with `listar`) adds its objects to ⌘K in their
  own group, the world on first; WhatsApp chats use it, with an action to mark one as a focus chat. Modules' commands
  get the declared worlds in `TELAR_MUNDOS`, to classify their own things.
- **Tabs are a house component, and the ones that don't fit go to a «⋯» menu.** `componentes/pestanas.ts` draws a tab
  bar one standard row high, with its line edge to edge: the open tab on the selection surface, an icon, a count, a
  dot for something new, disabled tabs. A bar shows the tabs that fit whole and puts the rest in a «⋯» that opens the
  house menu; the open tab is always shown, and a dot or count on a hidden tab shows on the «⋯». ← → Home End move
  between tabs (an ARIA `tablist`). Bars re-fit live as a column is resized. It is used by the thread's right column,
  the document viewer, a project's detail, foco and the /componentes pages.
- **The message bar.** `componentes/mensaje.ts`: a row to write to a thread or an agent about what you're looking at,
  without opening a window. It sends what the instruction window sends (`telar actuar`), to the same default
  destination; a compact chip opens the list of threads and agents, in ⌘K's order and only of the world in place.
  ⏎ sends, ⇧⏎ is a new line, and it never takes the focus by itself. After sending it says to whom (a link to its
  thread), and on failure why, with the text back in the field. Its page is in /componentes.
- **Buttons can show an icon instead of their word.** `boton()` takes `simbolo` (and `corto`): key + icon, with the word
  as the button's name.
- **`scripts/publicar.sh` publishes a version as one commit on GitHub.** It takes main's tree as a single commit on top
  of `origin/main` and pushes it and its tag, after checking a clean tree on main, `__version__`, the CHANGELOG section,
  that the tag is new and that `origin/main` came from main; a dry run unless `--de-verdad`. The `pre-push` hook that
  guards it is versioned in `scripts/pre-push`. docs/publicar.md, «Cada versión».
- **`scripts/probar_mudanza.py` tests a move between two real machines without deploying.** It sets up a separate telar
  on each machine (its own folder, tmux, Claude folder and a fake `claude`) that answers only the move's requests, with
  the record and the photos in separate stores (`TELAR_BUS_HILOS`, `TELAR_BUS_ESPEJO`); it can kill the node at a
  given step (`E1_PARAR`), measure the copy alone (`transporte`) and clean up. Page test: `npm run prueba:mudanza`.

### Changed

- **Moving a thread copies only what is missing, over the bus, with no size limit.** The conversation and its `<sid>/`
  folder (tool results, subagents) travel in chunks of up to 896 KB, zlib when it helps, six in flight, read from disk
  bit by bit (`telar.replica`). The destination says what it already has, the source sends from there, and the chunks
  only reach the place Claude reads from once every file's length and sha256 match, so a move cut halfway (network, a
  closed lid, a killed process) resumes from what arrived. Between a laptop and its server: 115 MB the first time in
  19 s up and 10 s down (it used to take 60 s for 25 MB, and refused anything larger); 1 MB more in 3 s and 1 s.
- **Moving a thread stops it first and passes it after.** It always waits for the agent to finish its turn, whoever
  asks. Then the owner cedes it in the bus, its agent stops, the final conversation travels, and the receiving machine
  takes it with the epoch it was ceded with and opens it; only then does the window here close. If anything fails
  before it is taken, the owner backs off, its agent wakes up, and the thread here is exactly as it was («Aquí sigue
  como estaba»). Every 30 s the node fixes what was left halfway: a cession whose process died is undone, a taken
  thread that was not opened is opened, and a waiting window of a thread now owned elsewhere is closed.
- **Moving a thread looks only at what is the thread's, and offers «subir y llevar».** It looks at the repository of the
  thread's folder and the ones its conversation wrote to (`telar.sin_subir`): uncommitted files its conversation wrote
  are its own; other uncommitted files in its folder are shown but never committed; unpushed commits are listed. If
  there is something, the move's panel shows it per repository and offers to commit only the thread's paths and push
  (`telar hilo llevar --subir`, `subir` in `POST /hilo/llevar` and `/hilo/traer`), to move anyway, or to cancel.
- **The thread arrives with its repository up to date and everything that was its own.** The destination fetches and
  rebases the thread's repositories that are behind (setting aside and restoring what is uncommitted there), or says
  why not. Its parent, labels, priority, effort, public flag, notes and pending messages travel with it. A child with
  its own branch is not moved (its worktree exists only on its machine): its parent moves alone, with a notice.
- **«Traer aquí» runs apart on the owner, and its progress is visible from the machine that asked** (`GET
  /mudanza?hilo=&maquina=`, node request `mudanza-progreso`), in the same panel as a move, with how much is being
  copied and how much was already there. The panel hides the steps that did not happen.
- **A thread's menu offers one row per machine to carry it to, near the top.** «llevar a laptop», «traer a laptop (esta
  máquina)»: every other machine of the person, from `[remotos]` and from the bus, by name. One that does not answer
  stays dimmed, saying why. A thread on another machine can be brought here or sent by its machine to a third one
  (`POST /hilo/traer` takes `a`).
- **The page follows a thread's owner.** `GET /hilo/registro?hilo=` gives the thread's record in the bus, and the page
  uses it to know where a thread lives or that it is travelling, from any machine and the phone. What you were looking
  at, terminal or conversation, follows the thread when it leaves.
- **The document viewer is a window over what you were looking at.** Every place that opens a file (a link, ⌘K, Todo, a
  bare name, an address, a thread's folder) opens it in a window; ✕ or ⎋ closes it and leaves everything as it was. A
  link to another file opens in the same window, and «‹» (or ⌫) goes back. On a phone it takes the whole screen.
- **The document viewer has a sidebar with tabs: comments, connections and data.** A commented passage keeps its type,
  with a faint background and its number; the comments tab lists them in document order, where you reply, resolve,
  reopen, edit and delete, and hovering or clicking links passage and row both ways. The graph connections have their
  own tab, and «datos» shows a `.md`'s frontmatter, key by key. The sidebar folds and resizes like a thread's sheet and
  remembers both; on a phone it is a sheet that rises from the bottom.
- **A reading mode for documents.** In the `foco` mode the viewer opens a .md centered, at reading width, with the same
  serif type as a thread's reading view; elsewhere its icon (or the l key) switches, and each side remembers the last
  choice. The styles are shared (`media/css/prosa.css`). Bold inside a quote keeps the quote's muted color.
- **The task card in foco: tabs on top, actions and the message bar at the bottom.** «gestión» and «concentración» are
  tabs under the screen's own bar; the cards scroll in the middle; the chosen card's actions sit in a row at the
  bottom, with the message bar under them. The same on the laptop and the phone.
- **A thread whose parent is a resident agent hangs under that agent in AGENTES,** with its own children, from this
  machine or another; it no longer shows in HILOS. If the agent is folded or hidden, it goes back to HILOS.
- **The worlds window grows downward for many worlds.** Up to four cards in a row; more go three per row, with the
  window scrolling and the current card in view. With ten or more, a digit that can start another number waits a moment
  for the second. Only the arts in view animate.
- **Hovering a world card sends a wave of characters across its art,** drawn in the art's own character grid, instead
  of the CSS sweep, tilt and glow. It is a generic hover effect of the art module (`registrarEfecto`), so it works on
  any art, built-in or from a `.txt`; an art can declare its own. No wave with reduced motion.
- **The WhatsApp focus window uses icons for what is obvious** (send, postpone, open the chat, hand to an agent, remove
  the focus, a draft's send and discard), with a line edge to edge between the chat and what comes below it.
- **Choosing from a list draws its rows like the ⋯ menu** (`ui.elegir` with `item()`): icon slot, faint description,
  color, disabled rows and the marked row on the active background.

### Removed

- **The animated loom around a thread's terminal.** When the terminal is smaller than its view, the space around it is
  the theme's background, still: no canvas, no timer. ⚙ terminal no longer offers it.

### Fixed

- **`telar commit` no longer says «subido» without a new commit.** Run from a subfolder with paths written from the
  repository root, it committed nothing (the paths did not exist relative to where it ran and were dropped without a
  word) and still said «subido» with exit 0. Now paths are taken like git, relative to where it runs: one that neither
  exists nor is in the repository commits nothing, exits 2 and says how to write it from there. With nothing to
  commit it says so and exits 4; if it pushed commits that were already pending, it says how many.
- **A thread's agent can carry itself to another machine.** When `telar hilo llevar` runs inside the window it is about
  to close, it checks and asks as usual and then continues in a separate process (its output in
  `<estado>/llevar/<hilo>.log`) that waits for the agent's turn to end, so its last words travel too. Before, closing
  the window killed the command halfway, leaving the thread closed here and never opened there.
- **A thread can go back by ssh to the machine it came from.** The copy from when it left was still there and the ssh
  copy refused it. Now the copy is replaced when the arriving conversation continues it, and set aside with its date
  when it went on separately there; the thread is also unarchived there.
- **Arriving, the window that watched the thread from here closes after the new one opens,** not before, so the page
  never takes it for one that lives elsewhere. A thread its owner archived is no longer brought here as a new window.
- **A window that looks at a thread on another machine hangs from the same parent as there.** The owner published only
  the parent set by hand; now the record carries the parent the owner sees, including whoever opened it.
- **The sidebar marks the thread you are looking at again, wherever it lives.** A thread from another machine is shown
  as `rem:<machine>:<thread>`, and the sidebar only compared bare names: windows that watch a server thread, rows from
  another machine's photo and archived ones from there lost the selection background.
- **The sidebar draws «↳» and indentation only under a visible parent.** A thread whose parent was archived, of another
  world or on a machine with no window here looked as if it hung from the row above. Now it goes loose, with who opened
  it and what it hangs from in its tooltip. Two threads with the same visible title each show their own name.
- **Copying a selection from a thread on another machine works in Safari.** The text comes back by OSC 52 after the
  mouse is released, and WebKit only copies inside the event itself; now the release starts a clipboard write with a
  pending ClipboardItem, filled when the text arrives (Safari, Chrome and Firefox over https). Over http, the notice's
  Copy button copies inside its own click. «copiar su dirección» and «Copiar la ruta» fall back the same way.
- **The document viewer no longer draws a Markdown file's frontmatter as text.** YAML between `---` or TOML between
  `+++`, only on the first line, is taken out before drawing; a `---` further down is still a rule. Line numbers stay
  those of the whole file, so comments anchor against the full text.
- **A menu opened next to something inside a modal window shows above it,** instead of falling under the window.

## [0.14.0] — 2026-11-23

The page is now arranged by **modes** (táctica, estrategia, foco, todo) and **worlds** (which part of your life
something belongs to, each ruling on its own schedule). What agents ask of you gathers in «te esperan» and Táctica, and
is answered in one window, «Contestar». **⌘K** and the «todo» view search threads, tasks, projects and documents at
once. **Idle threads sleep** and wake when opened or written to, also from another machine or the phone, and a machine
that is offline is said so. Themes are yours to change, and they and each world's schedule live in the root
repository, the same on every machine. A child thread can work **on its own branch** and its parent merges it, and
`telar desplegar` takes main to every machine.

**Upgrading from 0.13.** What breaks, and what to do:

- **The default mode shows only two dashboard tabs.** The starting mode, `tactica`, has `filas = "tactica,
  calendario"`, and every custom mode is built on it, so «ahora», «revisar», «proyectos», the block and module tabs
  leave its view. Add `[modos.tactica] filas = "*"` (or name the tabs you want), or switch to the «todo» mode (⌥⇧4).
- **`estandar` is now `tactica`, and `tactica`, `estrategia` and `todo` are built-in modes too.** `[modos.estandar]`
  is still read, as `[modos.tactica]`, and writing it from the page renames the table; `GET /modos` gives `tactica`.
  A custom mode with one of those names now sits on the built-in one and can't take a `base`: rename it.
- **The «plan» tab is gone.** A block or module tab with `en`/`dentro = "plan"`, a `[vistas.x]` with `aparece =
  "plan"`, and `plan` in `[dashboard] orden`/`ocultas` are left out, and `telar doctor` lists each one: delete those
  lines, or give the block its own tab. `[resultados.plan]` and `telar resultado plan` are unchanged. `bloques[].en` is
  gone from `telar config --json` and `GET /config`.
- **The key `t` opens «te esperan»** (and `d` is free again). An `[atajos.t]` becomes click-only and a provider with
  `tecla = "t"` makes `telar doctor` fail: give them another letter.
- **Idle threads go to sleep after 30 minutes.** Their agent closes and a placeholder waits in their window, so
  anything that types into the tmux pane directly reaches the placeholder (a ⏎ there wakes the thread, with what
  was typed as its first message). `[hilos] dormir_tras = 0` keeps the old behaviour on that machine.
- **Command providers are checked.** A task's `prioridad`, `de` and `fecha` (in the row or in `campos`) and an event's
  `respuesta` are validated; a value outside what they take makes the provider fail (it shows in `fallas`).
- **`servidor/desplegar.sh` calls `telar desplegar`.** `--solo-servidor` exits 2 (use `--maquina <name>`),
  `TELAR_SERVIDOR` and `TELAR_REPO_REMOTO` are ignored, it deploys to this machine and every `[remotos]`, and it needs
  `.telar/despliegue.yaml`.
- **Upgrade every machine on the bus together.** Threads whose names differ only in case or accents get separate
  mailboxes, which an older telar doesn't know; and a reply over the bus's `max_payload` now goes gzipped, which an
  older telar can't read.
- **`telar commit` can exit 3** (`apartado`): set-aside changes couldn't be put back, and nothing was pushed.
- **Run `telar agente instalar` once.** It replaces the hooks (`telar agente aviso` is now `evento`; the old name keeps
  working), gives the mailbox hooks 30 s, and allows `telar agente casilla --leer`.

### Added

- **Modes and worlds, in a band under the header.** The page is now arranged on two axes
  (`docs/propuestas/orden-por-modos.md`). The header keeps the logo, the machine and what you're looking at, the day
  line and the right-hand buttons; the band below holds the modes on the left and the world on the right.
  - **The mode** is a way of looking: táctica (the starting view), estrategia (projects, with the board and the
    decisions of their modules beside them), foco and todo. Each is its icon and name, the current one in violet.
    Keys: ⌥⇧1–4, ⌥⇧F, ⌥⇧0. A right click lists your own modes and «editar los modos…»; the old ◧ button is gone.
  - `[modos]` gains the four built-ins with their base. `estandar` is an alias of `tactica` in the config and in
    what the browser had stored. A custom mode says its `base`, its DASHBOARD rows (`filas`) and the world it sets
    (`mundo`). An old mode with `etiquetas` still filters as before.
  - **The world** sits on the right in its color, after a planet icon, by its name (when it changes next is in its
    tooltip). A click on it opens the window to change worlds (below), and ⌥⇧M switches it. One chosen by hand lasts
    until the schedule next changes.
  - It filters the whole page: threads, agents and other machines in the bar, what waits and its number, táctica,
    tasks, foco, calendar, projects and the day line. What it leaves out is counted in a folded «de <mundo> N» row at
    the end of HILOS. Unclassified items show in every world.
  - On a phone the band is one line: the mode icons with the current one in words, and the world. A thread's
    terminal loses one row at most.
  - `telar hoy` events and `telar proyectos` units carry their world, and `GET /agentes` each agent's.
    `[proveedores.<n>] area` sets the area of items that don't bring one.
- **A window to change worlds, one card per world with its own animated letter art.** ⌘M (Ctrl+M off the Mac; again, it
  closes), a click on the world in the band, or «cambiar de mundo» in ⌘K open it: each world of `[mundos]` and «ambos»
  as a card with its art, its name in its colour, its schedule in a line and, on the current one, why it rules and until
  when (the next one says from when). A click, its number or ⏎ puts it, like the band did; ← → ↑ ↓ move the focus, which
  follows the mouse; «volver al horario» (h) drops a choice made by hand; «editar» (e) goes to ⚙ mundos. Hovering lights
  the card up in its colour, the art speeds up and tilts slightly towards the pointer, and a sweep crosses it; the lines
  run edge to edge and nothing is rounded. With «reduce motion» the art stays still, and nothing animates while the
  window is closed or the tab hidden (one `requestAnimationFrame` for all cards, only while open). On the phone, the
  cards stack and a tap chooses. It replaces the world menu of the band.
- **Each world's art is its own module, easy to mod.** `[mundos.<n>] arte = "<key>"` (or ⚙ mundos › arte) chooses it;
  without it, the one named like the world, a factory one that suggests itself for it, or the orbit. Four ship: `telar`
  (a loom weaving a kilim), `cielo` (night sky, moon and shooting stars), `orbita` (a ringed planet and its moon) and
  `binaria` (two worlds orbiting each other, for «ambos»). A new one is a text file, `<raiz>/.telar/arte/<key>.txt`,
  with its frames separated by `---` (and an optional header and hover scene), that telar serves (`GET /arte`) and the
  page picks up on its own; or a function of time in `pagina/src/componentes/arte/` (`registrarArte`).
  /componentes#mundos shows the window in every theme, every art animated, and a place to write one and watch it live.
  How to: `docs/arte.md`.
- **Worlds: which part of life something belongs to.** `[mundos.X]` in the configuration lists `areas` (a task's
  `area`) and `rutas` (path prefixes relative to the root; the longest match wins; `./` is the whole root). The order
  of the tables is the order of the worlds. Without `[mundos]` nothing changes.
  - Every wait, every task (its JSON and the `tarea:` object) and the rows of `telar pendientes` and `telar hoy`
    carry `mundo`. It comes from what is declared, never from the title: a task's area, then its project's path; a
    document's path; a thread's folder, then its resident agent's, then its parent thread's; for a held message, the
    thread it was going to. Empty means unclassified.
  - `--mundo X` (repeatable, also `sin-clasificar`) and `?mundo=` filter `telar esperas`, `telar tipo tarea lista`
    and `telar pendientes`. `telar esperas` prints in batches by world. `telar esperas --json` and `telar config
    --json` list the declared worlds.
  - The mirror snapshot now carries each thread's agent, so the other machine can classify it.
  - A world can declare `horario` (a text or a list: «lun-vie 9:00-19:00», «sáb-dom», spans past midnight), `color`
    (a theme ink; the first free one if left out) and `etiquetas` (a thread's tags, which win over its folder).
    `[mundos] fuera` names the world that rules outside every schedule. Errors name the key: a span it can't read,
    a color the theme doesn't have, a tag in two worlds, an unknown key.
  - `telar config --json` and `GET /config` give each world with its tags, resolved color and schedule, plus
    `mundos_fuera`. `telar hilos --json`, `GET /hilos` and `GET /espejos` give each thread's world.
- **Each world says which modes it has.** `[mundos.<n>] modos = ["todo", "foco"]` (the keys of factory or own modes, at
  least one; without the line, all of them). While that world rules, the mode band shows only those (with «ambos», the
  union of every world's), and only those can be put: a click, ⌥⇧1–4 or ⌥⇧F on another does nothing, and ⌥⇧M cycles
  through the world's own. Entering a world (by its schedule or by hand) whose modes don't include the current one, the
  page switches to the last mode it had there or, failing that, the first of its list; going back to the other world
  brings back the mode it had there. A mode the person chose stays if the other world has it too. On the dashboard, the
  page goes to the new mode's view; looking at a thread, it stays there. ⚙ mundos has a «modos» row in each world to
  pick them with clicks (a click adds one at the end or removes it; the last one can't be removed; «todos» drops the
  line). `PATCH /mundos/<n>` takes `modos` (422 with the reason for a mode that doesn't exist); `GET /mundos` lists the
  modes a world can have; `telar config --json` and `GET /config` give each world's `modos` (`[]`: all). Deleting an own
  mode that a world has is refused, saying which world.
- **A world can have its own theme, and three warm themes for the night.** `[mundos.<n>] tema` (any of the page
  themes) colors the page while that world rules: the page puts it on when it enters the world, by its schedule or by
  hand, and takes it off when it leaves (with «ambos», or in a world without a theme, the mode's). It wins over the
  mode's theme; a theme chosen by hand in ⚙ modos holds in the world where it was chosen, until the mode changes or the
  page enters another world with a theme. ⚙ mundos picks it with a click, from a row of the themes painted in their own
  colors (`PATCH /mundos/<n>` takes `tema`; `GET /mundos` lists `temas`; `telar config --json` and `GET /config` give
  each world's `tema`). Reopening the page starts with the theme the world put last time, so the colors don't jump
  while the worlds load. The new themes, `brasa` (the suggested one), `rescoldo` (softer) and `ambar` (the warmest), are
  dark with warm backgrounds and text, muted cyans and, for the accent (`azul`: the links, the tabs, the active row, a
  thread at work, meetings), an earthy gray green instead of a blue, like warm terminal palettes: every text color and
  tint reads at 4.5:1 or more on the page, the bars and the active row, the meaningful tints stay apart from each other
  (red, the danger color, the most), and the background and text give off less blue light than the default. `npm run
  prueba:temas` measures all of that from the CSS (also that the night accent isn't blue and isn't mistaken for the dim
  text, and that every palette color of ⚙ temas reads well), and checks the world's theme on the page with a fake
  clock; /componentes › tokens › contraste shows the same numbers for every theme.
- **⚙ → mundos, shaped like ⚙ → modos.** Each world (and both) says whether it is on and until when, with «poner»,
  «volver al horario», «borrar» (confirmed, focus on cancel) and «nuevo mundo…». Its settings (schedule, color,
  thread tags, areas, paths, and which one rules outside every schedule) change with a click and are written line by
  line in the configuration (`GET`/`PUT`/`PATCH`/`DELETE /mundos`). What already belongs to another world isn't
  written, and the window says whose it is. A grid shows which world each resident agent belongs to and why (its
  folder's path or its thread's tag). In ⚙ → modos the agents grid gets each agent's world as a colored mark and a
  world picker that dims what that world leaves out; agents are still chosen per mode. The sidebar now places an
  agent with no open thread by the world of its folder, as the grids do.
- **⚙ mundos edits each world's schedule with clicks.** A new «horario» part shows the week (one strip per day, each
  world in its color, overlaps hatched in red, gaps in the color of the world that rules outside every schedule, a line
  at the current time) and, per world, its time ranges: the days as toggles (mon…sun) and from–to in 15-minute steps
  (to before from crosses midnight). Edits are a draft the week shows at once; the footer says what will be written or
  why it can't, with the house buttons («guardar», «deshacer»). Saving changes the band at once if the ruling world
  changes. A schedule that overlaps another world's is not written: `PATCH /mundos/<n>` answers 422 saying where
  («trabajo» and «personal» overlap on Monday from 18:00 to 19:00), since at that hour neither would rule. Test:
  `npm run prueba:horario`.
- **The schedule rules the same on every machine.** Each world's `horario` and `[mundos] fuera` also live in the root
  repository, `<raiz>/.telar/mundos.toml`, read under the machine's configuration (no schedule < the root's file < the
  machine's `[mundos]`, per world). ⚙ mundos writes there, removes what would shadow it from the machine, and commits
  and pushes only that file a few seconds later. `telar mundos` says where each schedule lives and whether two overlap;
  `telar mundos migrar` (`--ver`, `--local`) moves a machine's schedules to the root's file with a backup, without
  changing what rules; `telar mundos subir` pushes now. `telar doctor` warns about overlaps, what is only on this
  machine, what the root's file has that this machine doesn't declare, and a root file that can't be read. `GET
  /mundos` adds `horario_vive`, `fuera_vive`, `raiz`, `error_raiz`, `sobran_raiz` and `choques`.
- **An agent can declare its world: `mundo = "personal"` in its `agente.toml`.** It beats the route of its folder and
  the tags of its thread, travels with the folder and holds on every machine that declares that world. Everything of
  the agent belongs to it: its thread, the threads hanging from it and what lives in its folder (its memory, its
  records). With another world set, the agent is not shown in the sidebar, in ⌘K, among the destinations of an
  instruction or in the agents view (which says how many are left out, without naming them); in the `todo` mode, what
  its `fuera_de_su_mundo` says (above). ⚙ worlds says why
  (`por: "agente.toml"`); its section in `telar config` carries its `mundo` and `presencia`, so the page hides it from
  the first paint; `telar agentes --json` shows the declared `mundo`.
- **Each agent chooses what happens to it outside its world: `fuera_de_su_mundo` in its `agente.toml`.** `al-final`
  (the default, as before: the sidebar hides it; in the `todo` mode it shows last in ⌘K, the agents view and the
  instruction's destinations), `esconder` (with another world on it shows nowhere, not even in `todo`: neither it,
  its threads and the ones hanging from them, what waits on it, nor what lives in its folder; not in ⌘K, Todo's search,
  «te esperan», Táctica, the agents view, the instruction's destinations or the warnings strip; only ⚙ modos and
  ⚙ mundos name it) or `ver` (it shows in every world, like an unclassified one). ⚙ mundos sets it per agent, in the
  agents grid: `PUT /mundos/agentes/<clave>` writes that one line and commits and pushes only that file a few seconds
  later. It travels in `telar config`'s sections, `GET /mundos`, `telar agentes --json` and each machine's snapshot.
- **`agente` in `telar esperas --json` and `telar buscar --json`.** The resident agent a thing belongs to: the one of
  its thread (or of the thread it hangs from), the one asking (`agente:<clave>` among its links) or the one whose
  folder holds it, if its `agente.toml` declares its world (`mundos.agente_de_ruta`). The page uses it to hide what
  belongs to an agent that asks to hide.
- **Choose which agents each mode shows, with clicks.** ⚙ modos has a grid: one row per resident agent, one column
  per mode, a ✓ or · in each cell. A click saves it in that mode right away (`agentes` in `[modos.<n>]`: the agents'
  folders, comma-separated; empty shows them all, «-» none) and the sidebar follows if that mode is on. `agentes` is not
  inherited: each mode says its own. On a phone the grid becomes a mode picker with that mode's agents below. New
  `PATCH /modos/<n>` writes only the settings it gets, leaving the rest of the table and what the mode inherits.
- **⚙ modos chooses the DASHBOARD tabs of each mode with clicks.** A «pestañas» row per mode, like the «modos» row of
  ⚙ mundos: every tab with its icon and ✓, «todas» at the end. A click writes `[modos.<n>] filas` at once
  (`PATCH /modos/<n>`) and, on the active mode, the bar changes without reloading. The row says whether the tabs come
  from the factory, from the mode's base or from the mode itself, and «volver a las de fábrica» removes the line; a
  choice equal to the inherited one removes it too. The API refuses a key that is not a dashboard tab today (422), but
  keeps one the mode already named (an uninstalled module's).
- **⚙ mundos shows which tabs each world ends up with.** Under its modes, read-only: the union of its modes' tabs,
  without the ones ⚙ pestañas hides.
- **`GET /modos` says what each mode declares and what it would inherit.** `propios` (the settings in its table) and
  `heredados` (what each of those would be without its line).
- **`window.telar.ponerMundo(clave)`** sets a world by hand from the console, to walk the page in each world.
- **Táctica: a tab that answers «what do I do now?»** It is the first tab in DASHBOARD and the view the táctica mode
  opens on (`docs/propuestas/orden-por-modos.md`).
  - **Ahora**: the meeting in progress with its card, the plan block and its step, or the free time and what fits in
    it.
  - What waits for you splits into three lanes, by what the agent asks: **decidir** (its options, with the
    recommended one marked), **aprobar** (what it left done, with enviar, editar…, descartar) and **cerrar** (how,
    with its proof and «confirmar»). Keys 1–3 walk each lane in «Contestar».
  - A single **Hacer** (4) holds your own work. First what an agent needs you to do, then today's plan and what's
    due, each with its size. The meeting takes a place there only if there's something to prepare.
  - Within a lane, items are grouped by account (the project's client) and sorted by weight. The weight is the row's
    circle, with its reason in the tooltip. Color is kept for what really presses: a person waiting today, a hard
    external date, a stopped thread. Retained messages between threads move to the footer.
  - The lane is what the agent declares, never guessed. It writes it at the start of its progress line:
    `<marca>: pide=decidir|aprobar|hacer-tu|cerrar · peso=alto|medio|bajo (<porqué>) · opciones=a | b* ·
    artefacto=<ruta> · …`. A proposed close and a module question with options place themselves. Anything else
    waits under «sin clasificar».
  - «Contestar» gains «para el agente»: a note for this task (for the next review, or «hazte cargo ya») and «cómo
    trabajar esto». Each one is a `[respuesta]` line marked `instrucción:`, `prompt:` or `meta:`. A `prompt:` also
    notifies the agent that proposed it, or the `[agentes] sin_proyecto` one. If sending fails halfway, the window
    keeps the text, and sending again does only what was missing.
  - `telar esperas` gains `aplique`: what the agent did with your answer, its last «apliqué: …» note after it.
  - Debt (overdue for more than 30 days) enters only if starred, if someone waits, if its weight is high or if its
    date is hard.
  - `window.telar.ensayoTactica('<estado>')` shows a made-up day without answering anything. The catalog has its
    page in `/componentes#tactica`.
- **«te esperan»: one place for what is waiting on your decision.** An inbox that gathers what already
  exists, each source left where it lives.
  - The sources: threads waiting on a permission, a thread's live question with its options, the proposals agents
    leave on tasks (`avance`: question, close, prepared, conflict), and held messages nobody released.
  - Every object type can say which of its objects wait on the person (`esperando(ctx)`), and a module type can too,
    with `[objetos.X] esperando = "<orden>"`. A source that fails goes to `fallas` and doesn't take the others down.
  - `telar esperas [--tipo X] [--json]` and `GET /esperas` list them oldest first.
  - In the page there is a «te esperan» tab in DASHBOARD. It is grouped by kind, with threads waiting right now
    always on top, and has a search box with its count, per-group filters and foldable groups. A click opens the
    task, the thread or the object.
  - Its row in the bar counts only what asks you something (waiting threads plus questions on tasks).
  - New read-only type `mensaje:<id>`. `permiso:<hilo>` now carries the live question and its options when there is
    one.
- **Answer what waits for you from «te esperan», in one window.** A click on a row opens it. It shows the summary,
  a foldable detail, the options as buttons with what each one does, «Otra cosa…» for free text, and «Conversarlo»,
  which opens the instruction with the wait as context. On a phone it sits at the bottom.
  - It takes two clicks: one picks, the other does it. By kind:
    - a task's proposal: `responder`, or close it as proposed;
    - a held message: read it whole and `soltar`;
    - a thread's live question: its options, through `POST /hilos/responder`;
    - a module's question (class `decide`): `responder` with an option or text, on the version it read.
  - A 409 rereads and says so.
  - A permission dialog isn't answered here: the window offers to go to the thread.
  - `abrirVentana(props, …)` (`web/ventana.ts`) is the DOM layer every window will share: the `<dialog>`, modal or
    not by place, focus, ⎋, click outside, and a promise with the choice. `ventana()` stays pure.
- **Contestar shows the whole card, to decide without opening anything else.** The window for a task or a module's
  question was too terse to remember what it was about. Its card, on the left, now answers four questions:
  - **What it's about:** the full context, or «sin contexto escrito».
  - **How we got here:** the history with when, who and what. The creation and the last four show, and the middle
    folds with its count. Who is told by icon and color: you, the agent, what it applied, a meeting.
  - **What's at stake:** weight and why, who waits, the date and whether it's hard, priority, size, and what it
    blocks or depends on.
  - **What's related:** what was left done, where it came from and where it's worked, the project with its status
    line, its other open tasks, and the tags. Links open in place.
  - What's asked stays on the right, with the options in full. The keys and the button stay in the footer. On a
    laptop the window grows to two columns; under 100ch, and on a phone, it's one column that scrolls.
- **Contestar carries the task's bar, and a task's date moves from wherever you are.**
  - The header of a task's Contestar window has the same bar as its card in the tareas view, from shared code
    (`barra-tarea.ts`, `correrAccion`): date, priority, who does it, size, wait for, done and discard, with the star
    and share before the title. Same icons, colors and tooltips, and no keys, so they don't clash with the window's.
  - Each action runs without closing the window: the task is read again, the card and the bar update, and an answer
    goes on the new version. Waiting for someone, done and discard answer the proposal, so the window closes.
  - What Contestar already does another way is left out: done and discard when the lane is cerrar or hacer-tu,
    the instruction («conversarlo») and the note («para el agente»). A hard date says it doesn't move.
  - Táctica's task rows, in the lanes and in Hacer, get the date icon from the task list. The row stays in its lane.
  - Rescheduling a task no longer clears the agent's proposal: moving says when, it doesn't answer what was asked.
    Closing, waiting, reopening, «algún día» and answering still clear it.
- **Táctica shows what you answered and waits on the agent.** A task with an answer after the agent's last mark
  ([avance], [nota], [cierre], [secuela]) and no new proposal goes into the group «contestadas · N esperando al
  agente», read from the task's history, so it survives a reload. It replaces the five «respondido» rows that lived
  only in the page. The group's header says when the next pass runs (from the `avanzar` periodic), and each row has
  «revisar ya», which hands the task to the agent that writes the proposals now, the same way «hazte cargo ya» does;
  a row already handed over says when and can't be handed over twice in a row. `GET /esperas` brings them as
  `contestadas`, and `telar esperas` lists them in a line at the end.
- **What module questions needed from the core.**
  - A module query that exits 1 with `{"error", "codigo"}` and a 4xx code now returns that code, through the API,
    the bus and a type's action, instead of 502.
  - Class `decide` counts in the bar's number and has its own group, «decisiones que te piden».
  - Modules get `TELAR_PERSONA`.
  - A module's scheduled jobs run with the module's environment.
  - Waits carry what answering needs, additively: a live question's `pregunta`, a task's `texto` and `version`, a
    held message's whole `texto`.
- **Passes: a result filled several times a day, and what you haven't seen of it.** A view can declare `pasadas`
  (a schema; the first is `pulso`, an agent's hourly pass over every inbox). `telar resultado <clave> --agregar`
  takes one pass as JSON on stdin, validates it, and appends it atomically to that day's file on the machine where
  it lives; `--desde archivo.jsonl` imports, idempotent by id. `--sin-ver` and `--visto` read and move how far the
  person has seen, kept on that machine so it holds on every device. The page shows the latest unseen pass in one
  line under the notice strip («pulso 15:00 · 4 nuevas · 17 te esperan · +1»); a click opens every unseen pass,
  newest first, with each task linked and the overdue tasks without a proposal apart, and closing it marks them
  seen. Táctica takes its next pass from `pulso`, falling back to `avanzar`.
- **Each thing in a pass has its world, and the report shows only what changed.** A task with an address takes
  its world from the task itself; otherwise the agent's `mundo` counts, else it is unclassified. The line and the
  window show only the world on screen (and the unclassified), with the agent's `resumenes` per world, and what is
  seen is kept per world (`--visto --mundo`), so the personal part of a pass waits for the personal world. The
  window lists only new, advanced and closed tasks and drafts, each with its cause (`por`, required; `fuente` and
  `enlace` optional); `te_esperan` and `vencidas_sin_propuesta` are accepted but not shown. A pass with no changes
  is one line («sin cambios» and what arrived from each source) and doesn't count.
- **A result can be a series of files with a prefix, and the day «ultimo» is the most recent one.**
  `[resultados.<clave>]` (and `[vistas]` with `aparece = "dia"`) take a `prefijo`: its files are
  `<prefijo>AAAA-MM-DD.md`, in a folder it can share with other results. Asking for the day «ultimo» gives the most
  recent file there is, so a weekly summary dated on its Monday is found without writing a path in code.
- **Todo: see and search everything.** `telar buscar <texto>` and `GET /buscar?q=` search waits, tasks, checkboxes,
  threads (archived too), projects and every `[bloques.<clave>]` page together. They ignore accents and need every
  word. Titles rank first, then what is current, then what is newest.
  - Each hit carries its address and world. A source that fails says so and the rest still answer.
  - The «todo» tab is the todo mode. Without a query it lists every tab whole, with counts per world. With one, it
    groups hits by source, with the current world first and the others under «en otros mundos». A click opens the
    thing where it lives.
  - ⌘K gains a last row, «buscar … en todo».
  - A search answers within 1.5 s: each source is read in its own thread and kept in `telar serve` for 30 s (a
    block's page, 120 s, and blocks keep their last page, so search uses it without running the command). What hasn't
    arrived comes marked `tarde` with `leida`, and a slow source with something kept answers at once with that.
    `POST /buscar/preparar` warms the index when Todo opens; `GET /buscar` takes `tope` and `releer`. `telar buscar`
    asks the local `telar serve` through its socket, or searches by itself with `--tope` (5 s) and `--aqui`. Todo
    says «sigue leyéndose…» and asks again.
- **⌘K also finds projects, tasks and the documents of the graph.** Each comes in its own group after what is on the
  page (projects, then tasks, then documents, up to eight each), with its title and a short detail (a task's number,
  project and due date, or its state if it is done; a project's or a document's path). The three share one `GET
  /buscar` per query (the current world as `primero`), not one each; a source that came back late is asked for again
  alone. While a world is set, what belongs to another world is left out (the screen may be shared); with both
  worlds, or in the todo mode, it shows last with its world's name, and Todo always finds it, last and labelled.
  Opening one is what Todo does: the viewer with its connections for a document; both use the same `abrirHallado`
  (`pagina/src/web/hallados.ts`, which also holds each source's icon and colour). `cli.buscar` takes the sources to
  ask for. A tab is found by its visible name and by its key.
- **A ⌘K source can be remote.** `Fuente.resultados(q)` now receives what was typed, and a source marked `remota` is
  asked with it (two letters or more) 200 ms after the last key; an answer to something typed earlier is dropped, and
  what it showed stays on screen until the new answer arrives (its group says «…»), so the window neither empties nor
  jumps. The selected row stays selected when the remote rows arrive. `preparar` lets a source start reading when the
  window opens. Tested in `npm run prueba:buscador`.
- **`GET /buscar` takes `si_hay=true`.** A requested `fuente` this machine does not have (no tasks, no module that
  lists documents) is left out instead of failing the whole search with a 404.
- **The objects of a module that lists them are one more source of the search.** Each object type a module declares
  with `listar` (`[objetos.<tipo>]`) is a source of `telar buscar`, `GET /buscar` and the «todo» view's search:
  `objeto:<tipo>`, named by the type's new optional `plural` (or the type itself). An object matches by its title, its
  id and its summary (searched, not shown); `campos.ruta` says where it lives and its `estado` goes at the end of its
  row («12 conexiones»). An object that lives in a file lands in that file's world: `campos.ruta_abs` (absolute, since a
  nested repository's paths are relative to it) or `campos.archivo` (an `archivo:` address). With `ruta_abs` the object
  is that document: it comes in `datos.ruta_abs` and a click in «todo» opens it in the document viewer. Each source
  runs a module query, so it is kept for two minutes like a block, `preparar` starts it, and a slow one (a large
  knowledge graph without its cache) comes `tarde` and the next search brings it. A `listar` that brings nothing and
  says why is the source's `falla`.
- **Filtering «todo» to one source shows all it found.** Not just the first four. It is how a source with no tab of
  its own (the objects of a module) is seen whole: a click on its header or on its «+N más» filters to it.
- **The search can put one world's things first before cutting to the limit.** `GET /buscar?primero=<mundo>` and
  `telar buscar --primero <mundo>`: within each source, what belongs to that world (and what has no world) goes before
  the rest, and only then is the source cut to `limite`. It hides nothing and doesn't change `total`: it only decides
  what makes the cut, so that a source with much more of another world (the documents of a large work repository)
  doesn't crowd out the matches of the world that rules. «todo» passes its world (none with «ambos») and asks again if
  the world changes while it is open. The answer says which one ruled (`primero`); an undeclared world orders nothing.
- **Idle threads go to sleep: their agent closes and their window stays, in its place in the list.** After
  `[hilos] dormir_tras` without activity (`"30m"` by default; `0` turns it off, per machine) the node closes a
  thread's agent and leaves a one-line waiting program in its window (`telar.dormir`): a Claude Code at rest weighs
  about 300 MB, and most threads rest most of the day. Its conversation stays on disk, and opening the thread resumes
  it in the same window in a few seconds (`claude --resume`, with the same effort and `--add-dir`): a click in the
  list or ⌘K, its terminal (`telar mirar`, the page, another machine, the phone), `telar ir`, `telar hilo retomar` or
  the new `telar hilo despertar [--texto "…"]`, a ⏎ in its window (what was typed before arrives as its first
  message), and also a bus message, an errand or what another thread types to it (the node wakes it with
  «↯ mensaje nuevo», and the hook delivers its mailbox). Only what is certainly idle sleeps: never a thread working or
  waiting for you (its attention or its screen), with unsent text in its prompt, a question on screen, something in
  the background (a Bash task or a Monitor, a `/loop`, a session cron or a pending ScheduleWakeup), messages to
  deliver, a `residente = "siempre"` agent, or one in view (a terminal attached to its window, what an open page
  shows, or what another machine shows). `telar hilo dormir --seco` says why each thread here would sleep or not;
  `telar hilo dormir` puts one to sleep now. Sleeping threads don't count towards `[agente] max_vivos`.
- **A sleeping thread has its own mark: a faint ring.** In HILOS, AGENTES, the phone and the threads of other
  machines, the attention slot shows a ring in the faint tone (like a paused project: stopped, not running); if it
  finished and you haven't seen it, its target, faint. Its tooltip says since when and that opening it wakes it.
  `telar hilos` shows `◌` and «dormido», and `--json` brings `dormido: {desde, conversacion}` (`null` awake; in
  `--red`, `dormido` for the other machines' threads).
- **The page says what it shows.** `POST /mirando` (when it changes and every 30 s while visible): what a page shows
  is not put to sleep, and the terminals it keeps mounted for recently viewed threads, hidden, don't count as viewed.
  The machine photo carries `mirando` and `vista`, so a thread viewed from another machine isn't put to sleep either.
  `POST /despertar` wakes the one the page opens asleep (a mounted terminal doesn't ask telar for anything).
- **Waking a thread on another machine, from the server, the laptop or the phone.** `telar hilo despertar <hilo>
  --maquina M` (or the machine the bus says, when the thread isn't known here), the page's «despertar» in the ⋯ of a
  thread of another machine, and `POST /despertar` with `cola` ask that machine's node (`hilo-despertar`): a sleeping
  thread wakes in its window, a closed or archived one resumes its conversation, an awake one is left alone (and so is
  the focus there). `--texto` is its first message, also for `telar hilo retomar`. An old node is told apart (it
  answers `{ok}` without `hecho`) and the answer says so.
- **A machine that is offline is said so, and what is asked of it waits.** When a machine's snapshot is older than
  120 s and this node is up to date with the bus (`<estado>/espejos/.al-dia`), the strip, the thread bar, the phone
  and `telar hilos --red` say «laptop fuera de línea desde 14:02» and mark its threads unreachable (`alcanzable:
  false`, `fuera_de_linea_desde`) instead of alive or asleep from a stale state. Waking one queues it
  (`<estado>/cola/<máquina>.json`, one per thread, the text added up) and this node does it when the machine's
  snapshot arrives again, up to three tries; what was done stays a day (`hechos`), the strip says it and the thread
  that asked gets an aviso. A message to such a thread waits in the bus as always, now said at once instead of after
  the bus's 60 s timeout, and resuming it is queued if it wasn't open. The terminal of such a thread shows the offline
  box with «despertar al volver», «escribirle» and «reintentar» (the house buttons), its conversation (the phone's
  view) shows «despertar al volver» above the box, and opening one that slept there queues nothing
  (`npm run prueba:alcance`, `pruebas/test_alcance.py`).
- **Writing to a closed resident agent opens it.** The conversation of an agent that is `siempre` or `a-pedido` and
  closed (or archived) keeps its text box: what is written goes as a message over the bus, and its node opens it with
  its conversation and delivers it. From the phone, an agent is written to without "retomar" first.
- **An agent that lives on another machine shows up even if its folder hasn't reached this one.** Each machine's
  snapshot (`telar espejo`) now carries its resident agents (`agentes`: folder, name and the world its `agente.toml`
  declares). `telar config` lists the ones missing here among its sections, with `maquina` and `home: false`; the
  sidebar shows them with their thread over there, without a home, and opens them on their machine. Their world comes
  from that declaration, so their threads are classified right even with this repository behind.
- **`telar doctor` says when agents from other machines are missing here.** «casa atrasado 140 commits: hay agentes
  que esta máquina no tiene: diario (de servidor)», with the `git pull` that fixes it (the count is from the last
  fetch: it doesn't go to the network).
- **A proposal for continuing a thread on another machine while its own is off.** In
  `docs/propuestas/seguir-sin-su-maquina.md`: a per-turn incremental backup of each conversation to the server,
  «seguir aquí» from it, and what the laptop does when it comes back. Not built: what gets copied to the server is
  the person's decision.
- **What a thread's context is made of: the «contexto» sheet.** The right sidebar has a third sheet, next to the
  agent card and the codes, and now appears on every thread. On top: how many tokens the context holds now (measured
  by the model on the last request), since when (the start, the last /clear or the last compaction, with what it held
  before), and a strip with the share of each part. Below, seven folding groups: Claude Code itself (system and tools,
  deduced), what loads at startup (each CLAUDE.md, the memory index, startup hooks, the skills list, each MCP server's
  instructions and tool names, git status), what loads on entering a folder, what the thread read (Read, read-only
  Bash, searches, skills, what's re-attached after compacting), what repeats on every message (per-prompt hooks), what
  came from other threads, and the conversation. Opening a group lists each thing with its short path, its size and
  how many times it came in; a click on a file opens it in the viewer, and what a compaction already summarized is
  set apart. Sizes are estimated from characters; it never shows a file's contents. The conversation is read
  incrementally (`telar.conversacion.carga`: where it left off, then only what's new), so a 180 MB transcript costs
  about 2 s once and nothing after. `telar hilo contexto [hilo] [--maquina M] [--json]`, `GET /contexto` and the bus
  verb `contexto` (read-only, honors `[bus] no_leer`). A thread from an agent that doesn't say what it loads shows
  that instead. New component «partes» (a proportional strip), with its catalog page.
- **Answering the agent's questions from the conversation view.** When the agent asks with options
  (`AskUserQuestion`), the conversation view (the phone's, and on desktop) shows the questions where the input box
  goes, one at a time, with «1 de 2» and ← →. Each option comes with its description, plus «otra respuesta» for your
  own text. In a single-choice question, a tap moves to the next one, and on the last one, with everything answered,
  it sends. With several options or typed text, «responder» sends. The answer goes straight to the agent's dialog:
  the Claude Code mod races it against the terminal, the first answer wins, and the dialog closes as if it had been
  picked there. The conversation keeps a «te pregunta: contesta abajo» line while it waits, then what was asked and
  what you answered.
  - Works for a thread on another machine too, through the new bus request `responder` (it honors `[bus] no_leer`).
    If that machine runs an older telar, the view shows the question and says to answer it in that thread's
    terminal.
  - New: `POST /hilos/responder`, a `pregunta` field in `/hilos/leer` and `telar hilo leer --json`, and «→ answer»
    in `telar hilo leer`.
  - The reading view only says that the agent is asking something and links to the conversation. Permission dialogs
    are not covered yet.
- **Hands-free voice in a thread's conversation view.** A «voz» button, shown when the browser can both dictate and
  speak, lets you talk to the agent: the browser dictates in Spanish, sends after a pause, and reads the answer aloud
  when the turn ends, without code, links or markdown and cut to about 450 characters. Speaking while it reads
  interrupts it. While voice is on, the page keeps the screen awake and doesn't reload itself after a deploy.
- **A thread stuck on Claude Code's trust question waits on you.** Since Claude Code 2.1.326 a child launched with
  `--add-dir` stops before starting on «Adding a new directory… Yes, add it», and no hook runs. The node reads each
  local thread's pane every 30 s (`telar.confiar`): with the question on screen the thread is marked as waiting
  (class `confiar`, with the folder it asks about) and the notice strip says which thread and what to do. telar
  never answers it nor touches `~/.claude.json`.
- **The codes sidebar also reads the project's branches.** A code defined in a deliverable that still lives on a branch
  (a `git worktree` of the same repository, one not yet merged to main) used to be unknown. Now `telar codigos`
  reads, from every worktree that's on a branch, the `.md` that branch changed or added in the thread's folder (commits
  and what isn't committed). The folder wins: a document only the branch has comes in whole; one the folder also has
  adds, as `README.md@branch`, only the codes the folder doesn't define and the mentions its version doesn't make. The
  detail says «· rama entrega-2» and opens the branch's file; the footer counts the branches. New fields `ramas` and
  `de_rama` in `telar codigos --json`.
- **Child threads on their own branch, merged by their parent.** For several agents working at once on different
  features of the same codebase: `telar hilo hijo «Calendario» --rama [name]` opens the child in a git worktree
  (`~/worktrees/<repo>-<branch>`, a new branch off the one the parent's folder has checked out, in the same
  subfolder), and Claude Code gets it as an extra working folder (`--add-dir`). `telar hilo fusionar «Calendario»`
  is the parent's: it refuses if the child has uncommitted work, tries the merge without touching anything
  (`git merge-tree`) and, if it conflicts, names the files and leaves the parent's folder as it was; otherwise it
  merges with `--no-ff` where the base branch is checked out, then closes and archives the child and removes its
  worktree and branch (`--seguir` merges what's committed and keeps the child working). `telar hilo descartar` drops
  them without merging (it refuses to lose work unless `--forzar`). Nothing is pushed. The parent and the child know
  it from their startup context, derived from what they have, not declared: the child, its branch and that it
  doesn't merge; the parent, how many commits each child has unmerged and that merging is its job. The method is a
  new skill, `/ramas`, installed with the others. The sidebar marks such a child with a branch icon; `rama`
  (`{rama, base, ruta}`) is new in a thread's JSON. `scripts/dev.py` now serves the code of its own checkout, so a
  child can try the page from its worktree on its own `--puerto`.
- **A child is born ready.** `telar hilo hijo --rama` links in the worktree every `node_modules` the parent's folder
  has next to a tracked `package.json`. The `/ramas` skill tells the child to run only the affected tests while
  iterating, the full suite once before «listo» with the commit it passed on, and not to ask the parent anything over
  compiled-only conflicts; the parent doesn't rerun the suite if the branch is still on that commit.
- **`telar hilo hijo --esfuerzo low|medium|high|xhigh`** (and `esfuerzo` in `POST /hilo/hijo`): the child's agent
  starts with that effort and keeps it when resumed; without it, the usual one.
- **Each child writes its own CHANGELOG entry, and `telar hilo fusionar` files it.** A repository that declares
  `.telar/changelog.yaml` (`archivo`, `carpeta`, and optionally `ancho`, `negrita`, `secciones`) takes its entries as
  fragments: the child writes `changelog.d/<branch>.md`, a piece of the CHANGELOG with one or more `### Section`
  headings, and merging moves each entry to the top of its section under [Unreleased] (creating the section, in Keep a
  Changelog order, or [Unreleased] itself if missing) and deletes the fragment, in the merge commit itself. Two
  branches never collide in the CHANGELOG any more. A malformed fragment is refused before anything is touched, with
  file and line of each problem; a branch without one merges anyway and says so (`changelog` in `--json`). Without the
  declaration nothing changes. The `/ramas` skill tells the child to write the fragment and the parent not to paste
  it; telar's own repository declares it.
- **`telar hilo fusionar` regenerates compiled files instead of refusing.** A repository marks generated files with
  `merge=telar-compilado` in `.gitattributes` and says in `.telar/compilados.yaml` how to rebuild them and what they
  are built from (`fuentes`, globs like `si_cambia`). When a child's branch touches them or their sources, the merge
  happens in a temporary worktree (with the parent's `node_modules` linked): either version is taken, the commands run,
  and the merge is committed with what they generated (`regenerados` in `--json`); the parent's folder only moves at
  the end, fast-forward. A branch that touches neither is merged as before, without building, and a conflict in
  anything else is refused as before. `telar hilo hijo --rama` defines the `telar-compilado` git driver for the
  repository's worktrees only, so a `git merge` of the base inside a child doesn't stop on them. telar's own
  repository declares `app.js`, `componentes.js` and `marco.css`, built from `pagina/`.
- **`telar desplegar` leaves what is on main running on every machine where the repository lives.** That is this
  machine and each `[remotos]`. Where the repository lives on each one is found without new config: the same path
  relative to `raiz` or home, `[remotos] repos`, or what that machine's telar says (its root, `[repos]` and module
  folders), and it must share its first commits with the one here. The commit goes over ssh, never through GitHub and
  never force-pushed: to a ref of its own, then a `git merge --ff-only` there. Then each machine, the others first,
  runs what the repository declares in `.telar/despliegue.yaml`: commands to prepare, the services to restart (systemd
  or launchd, only where installed), commands for after and the checks (a route of telar's page with that machine's
  own key, which never leaves it, a field that must match on every machine, or a command). What runs is recorded in
  `refs/telar/desplegado`, so `si_cambia` compares against the last deploy and a machine already up to date is not
  restarted again. It refuses without touching anything if you are not on main, tracked files are dirty here or
  there, another machine has commits missing here, or one does not answer. If a step fails it stops there and says
  which one, and what each machine has and runs. `--ver` shows the plan, `--maquina` limits it, `--todo` runs every
  step and `--json` is the contract (docs/contratos.md). Telar's own declaration reinstalls on a `pyproject.toml`
  change, restarts `telar-serve`, runs `telar agente instalar --si` when the skills change, and checks that
  `/pagina.json` has the same `firma` everywhere and that `/api/salud` answers.
- **`telar desplegar` warns when the compiled files in the commit don't match their sources.** If what is being
  deployed touches the sources or the compiled files, it rebuilds them in a temporary worktree of that commit (a few
  seconds) and says which ones came out different (`compilados` in `--json`). It warns and deploys anyway.
- **An open page catches up after a deploy.** Deploying telar from the repository (`git pull` and a restart) left an
  open page running the code it had loaded, sometimes for days, as on a phone. The service now fingerprints the page
  it serves (`indice.html`, `app.js` and `marco.css`) when it starts. The fingerprint is written into `indice.html`
  (`<meta name="telar-pagina">`) and served at `GET /pagina.json`. It is taken at startup, not when the files change,
  so a page never loads new JavaScript against the old API. The page compares it when it is looked at again, when
  the event stream reconnects, and every 30 s.
  - A hidden page reloads right away, or within 5 s of coming back if the phone had frozen it.
  - A page in view shows «↻ página nueva» in the version notice (just the icon on a narrow screen), and one tap
    reloads.
  - A page in use only shows the notice. That means an open dialog, a focused field with text, or a conversation
    with something on its way or a question half answered.
  - A reload keeps what you had typed: the conversation box, the box under the terminal and the instruction drafts
    are kept in `sessionStorage`, and so is a question's «otra respuesta». It also goes back to the same thread and
    view, and to the dashboard tab or the phone's list. F5 now does the same.
  - Pages opened before this version need one last manual reload.
- **`scripts/medir.py` checks the page in a real browser, fast and without hanging.** It starts the page with
  `scripts/dev.py` on a free port of its own, logs in with the key (through stdin, never printed), opens one named
  agent-browser session and walks the screens asked for by name: the modes, each dashboard tab, config and its
  sections, a thread in a given view, a file, an object, or `todas` for all of them. It waits just enough (the screen
  is there and the DOM and fetches have settled, never a fixed sleep), and on each screen returns the bounding rect and
  computed styles of the given selectors and/or a PNG, as short text or `--json`, at laptop size, `--ventana WxH` or
  `--telefono`. Each step and the whole run have time limits, no eval ever returns a promise (`--js` leaves its result
  in `window`), and it always closes the browser and stops the page, cleaning up what a killed run left behind.
  Measuring `.pantalla-barra` and `.franja` on all 19 screens takes about 40 s. Documented in `docs/desarrollar.md`
  («Comprobar en el navegador»), with the page's navigation API (`window.telar.mostrar`, modes, tabs, thread views).
- **Themes.** The page's colors come in three layers of tokens: a theme's primitives (background, text, inks), what
  each color is for (`--texto-tenue`, `--acento`, `--estado-espera`…) and each component's own (`--item-…`). A
  theme says its primitives and, if it wants, any other token. Four: «telar» (catppuccin mocha, as before), «latte»
  (light), «riso» (fluorescent risograph inks on black; the active row gets a pink stripe) and «papel» (the same inks
  on light paper). A mode's `tema` picks one (⚙ modes); open terminals take the new colors without closing.
- **⚙ temas changes a theme's colors and makes themes of your own.** `[temas.<tema>]` sets, as `#rrggbb`, any of the
  four colors that give a theme its face — the background (`bg`), the bars and windows (`bg-barra`), the lines
  (`linea`) and the selection (`sel`) — and any of its text tints: the text, the dim text, the titles (`amarillo`), the
  accent (`azul`), the agents (`violeta`), success, remote, `magenta` and danger. The rest (the hover, the active row,
  the surface) is derived from them, and what it doesn't say stays as shipped. The page lays them over the theme's CSS
  with a sheet of its own, so everything that uses a color follows (the active row, the links, the terminal), and
  remembers them in the browser so a reload starts with them. A theme of your own is `[temas.<name>] base = "<shipped
  theme>"` plus the colors it changes: the whole base theme (its CSS rules, copied under the new name) with those on
  top, and its "shipped" colors are the base's.
  - ⚙ temas (after mundos) shows the themes in their own colors (an eye on the one in view, a pencil on those with
    custom colors) and lists your own with the shipped ones, also in ⚙ mundos, ⚙ modos and the theme bar of
    /componentes. «nuevo tema…» creates one (a name, fixed up to lowercase and hyphens, never a shipped one or one that
    exists, and the theme it starts from; from another custom one, its colors are copied too); it can be deleted
    unless a mode or a world has it on.
  - Every color row shows its name in its color, what it paints, the shipped value next to the current one and
    «volver»; «todo de fábrica» resets the whole theme (for a custom one, its colors only). To change one: a short
    palette that matches the theme (the shipped color first, then named hues at the tint's own lightness, muted for
    the night themes), the browser's color picker and a field for any `#rrggbb`. A palette click writes at once; the
    picker and the field preview it on the whole page and write it on release or ⏎. A live preview (a bar, rows with
    their lines, the active and the selected row, every tint) stays at the top while you scroll.
  - Low contrast is flagged as it's picked and when written, never refused: text that drops below 4.5:1 on the page,
    the bars or the active row, a tint too close to another meaningful one, text on the selection, a line you can
    barely see. «colores…» next to a world's theme in ⚙ mundos and next to a mode's in ⚙ modos goes there.
  - **They live in the root repository, for every machine.** `[temas.<tema>]` is read from `<raiz>/.telar/temas.toml`
    and from the machine's own config: factory < the root's file < the machine, which overrides color by color, only
    there. ⚙ temas writes to the root's file (and drops from the machine config whatever would hide it), commits only
    that file a few seconds after the last change and pushes it like `telar commit`, so the other machines see it on
    their next integration. Each theme says where it lives (next to each color, and in words under its name). Without
    `raiz` everything stays in the machine config.
  - `telar temas` says where each theme lives; `telar temas migrar` moves a machine's `[temas.*]` to the root's file
    without changing what is seen (what the file already says the same leaves the machine; what it says differently
    stays, listed), with a backup of the config next to it (`config.toml.antes-de-temas-en-raiz-<fecha>`), then commits
    and pushes that file (`--ver` only says what it would do, `--local` does not push); it refuses if this machine's
    copy of the file is behind upstream. `telar temas subir` commits and pushes the file now. `telar doctor` reports an
    unreadable file, uncommitted changes to it, missing themes and themes only on this machine.
  - A mode or a world naming a custom theme that no longer exists (deleted on another machine) doesn't break the
    config on load: it is listed in `temas_faltan`, the page falls back to the mode's theme and `telar doctor` says so.
    Writing a new reference to a theme that doesn't exist is refused; an old missing one doesn't block writing
    anything else.
  - `GET /temas` gives each theme's colors, its `base`, `de_fabrica` and where it lives (`vive`, `en_raiz`,
    `en_maquina`, `raiz`), and the colors that can change (`fondos`, `tintas`); `PUT /temas/<name>` creates one,
    `PATCH /temas/<tema>` (`{"valores": {color: "#rrggbb" or null}}`) changes some colors, `DELETE /temas/<name>`
    deletes it (409 while in use). `telar config --json` and `GET /config` give `temas`.
- **Densities.** How much air each row gets, apart from the theme, so any theme goes with any density: «compacta»
  (one line per row, as before), «cómoda» and «amplia» (for a finger: rows about 40px tall, wider actions). A row's
  height is its line height, so everything sits in the middle and an action can be tapped anywhere in the row's
  height. A mode's `densidad` picks one, or «auto» (the default): amplia on a touch screen, compacta with a mouse.
- **A visual grammar, and states said only with circles.** The catalog's foundations describe what the design is
  made of: circles say how something is, rectangles where it goes, letter icons what you do to it, text its name.
  Each visual variable answers one question (fill: how much there is; size: rank; relation: what it relates to;
  motion: whether it is changing; color: of what kind; tone: whether it still holds) and each value has one concept.
  The thread bar follows it: working is a full circle, waiting for you an empty ring, finished a ring with a full
  circle inside (dimmed once seen), the priority a small circle beside the state, another machine a ring with a dot
  outside it (which circles while travelling), public two crossing rings, something new a dot. No more check mark,
  bell, arrows or diamond for a state. It also says how a rectangle is split into parts, each marked one way only:
  columns and sections by a line; a band of another kind inside a section (a list's tools) by nothing of its own (its
  field and icons say it); a group by a short line at each side, in its type's color (`--orden-linea` for sorting).
  In a list, only the selection gets a background.
- **The component catalog, `/componentes`.** A developer page with every state of each component side by side in
  every theme, at the bar's width or a phone's, with each state's props a click away and the outline of each section
  on request; the real thread bar built from made-up threads; and every theme's tokens with their resolved values.
  With `scripts/dev.py` it reloads on every change. Nothing pressed there does anything: it says what it would do.
  It also shows any mode as a full page with made-up data, at `#<modo>/ver/…`.
- **The item's anatomy in the catalog.** A plate with the item drawn large, a bracket over each of its three
  sections and a leader from each piece to its name, the `item()` prop that sets it and what it is for; under it,
  the question each section answers. A test fails if the item gains a piece the plate doesn't name.
- **The notice strip.** Above the threads bar, the same height as the screen's bar and aligned with it, one place
  says the state of the system and the threads.
  - Quiet, it reads «al día · 18:42», the last good read.
  - With notices, the worst shows in its color with its icon, and «+N» the rest. Red is only for «sin conexión». A
    click opens the list: since when, what happened, what to do, its buttons (reintentar, reconectar ahora,
    recargar, instalar, tejerla, leerlo de nuevo) and where it leads. Whoever raises a notice clears it, so what
    fixes itself goes away by itself. Without a connection, whatever depends on it stays quiet.
  - It gathers ten notices that were spread around: no connection to telar, an error reading the threads, a session
    not woven, a thread open on two machines, a cut terminal (after 4 s), a provider down, a failing «te esperan»
    source, an unread dashboard block, a new page, version or rollback, and another machine without news.
  - Toasts that answer a click stay where they are. What waits for you stays in «te esperan» and Táctica, and
    Táctica drops its own failure lines.
  - Folded, the strip keeps just the icon. On a phone it shows only with a notice. Viewing a thread or in focus, a dot
    in the notice's color marks the way back.
  - `window.telar.ensayoAvisos(…)` and `/componentes#avisos` simulate each one.
- **Notices from a file.** `[avisos.<clave>]` declares a JSON a program keeps up to date (`archivo`, and `en` if it
  lives on another machine): `{"nivel": "ok|aviso|mal", "linea", "fecha", "informe", "sugerencias"}`. While it says
  `aviso` or `mal` and is less than an hour old, the notice strip shows its line and when it was measured, in the
  caution color or in red (a new strip level, «problema», which doesn't silence the others); a click opens the report
  in the document viewer, on its machine. `GET /avisos` lists them.
- **A notice from a file can be marked seen.** Opening its report from the notice strip, or its ✓, silences it on
  every machine (kept where the file lives, `POST /avisos/visto`) until it changes: a new id in its `problemas`
  list, a higher level, or a return after saying ok. Without `problemas`, only the level counts. `GET /avisos` says
  which are seen.
- **Held messages show in the notice strip.** Messages the chain brake held in the last 24 h appear there, linking
  to «te esperan»: whoever sent them believes they arrived.
- **Held messages can be discarded.** `telar mensaje --descartar <id>` (`POST /mensajes/{id}/descartar`) drops a
  message the chain brake held: it is never delivered, the bus log keeps it as `descartado` with who and when, and
  the sender gets a notice that doesn't wake it (its message to X was not delivered: the person discarded it). In «te
  esperan» each held message offers release and discard (red, asks first with focus on cancel) and the group offers
  discarding them all; the Contestar window has «Descartarlo» next to «Soltarlo».
- **The day in one line, in the page's header.** How much free time is left until the next meeting, and what comes
  after: «libre 1h 20 → 11:30 Revisión de diseño · 15:00 Comité», or during one, «en Revisión de diseño 45min → 12:30
  libre 2h 30 → 15:00 Comité».
  - A thin bar beside it is the whole working day (8:30 to 18:00, stretched to fit a meeting outside it). What has
    passed is filled, meetings are blue and now is a line. Free time is green, yellow under 10 minutes.
  - Only meetings with other people cut free time. Your own blocks and routines show faintly in the bar but don't
    count as busy.
  - It reads today's agenda from the calendar the page already uses (`telar hoy`, with its five-minute cache) and
    redraws every minute and when you come back to the page. A click opens the calendar. With no calendar declared,
    no meetings, or the day over, nothing shows.
  - It is the first thing to give way when the header narrows, down to «1h 20 → 11:30» on a phone. The buttons on
    the right never do.
  - Units sit next to the number: «1h 20», «45min». The component is `componentes/jornada.ts`, with its page in
    `/componentes`.
- **Your answer to each invitation counts.** Every event in `telar hoy --json` now says how you answered it:
  `respuesta` is `aceptada`, `rechazada`, `tentativa`, `sin_responder`, or empty when there is nothing to answer.
  Empty covers your own events, and one you organize counts as accepted. It comes from the calendar provider: the
  attendee's `PARTSTAT` in an iCal feed (the owner is the feed's `X-WR-CALNAME`), `responseStatus` in gws, or an
  optional field in a `comando` provider.
  - The day line leaves declined events out entirely. An unanswered one still cuts your free time, since it hasn't
    been looked at yet, but is drawn hollow and named «(sin responder)» when it's the current or next one.
  - The dashboard's day and week show a declined event faded and struck through. It no longer overlaps others or adds
    to the day's meeting hours. An unanswered one is marked «sin aceptar» even if the plan doesn't say so.
  - «ahora» no longer takes a declined event as the block in progress.
- **The thread bar and the thread's side panel can be resized by dragging their line.** A 6 px grab strip sits on each
  line (invisible: the line stays one pixel), with the `col-resize` cursor; dragging changes the width live and marks
  the line with the accent, and a double click goes back to the default width. Limits: the bar from 200 px, the side
  panel from 240 px, each up to 45% of the window, and the center never below 480 px. The chosen width is remembered in
  this browser per screen size (a laptop's screen and an external monitor each keep theirs) and comes back when a
  folded bar or panel is unfolded. The terminal is measured once on release, not on every pixel (one resize to tmux).
  No strips on the phone (`web/anchos.ts`, `npm run prueba:anchos`).
- **The width of a thread's terminal can be changed by dragging its edge.** The same 6 px grab strip as the thread bar
  and the side panel sits on the terminal's right edge (its left edge when the terminal sits on the right), reusing
  `web/anchos.ts`: `col-resize` cursor, the frame follows the pointer column by column with its line in the accent
  (centered, it grows on both sides), and the terminal measures itself and resizes the tmux window only once, on
  release. Limits: 80 columns (or what fits) up to the whole center, where it is remembered as "all". A double click
  goes back to `[terminal] columnas` (⚙ terminal), which stays the default: the dragged width overrides it in that
  browser and per screen, next to the bar and side panel widths, and changing the width in ⚙ terminal forgets it
  (⚙ terminal also says when a dragged width is in effect). No strip on the phone (`npm run prueba:anchos`).
- **`window.telar.ensayoConfirmar()` and `ensayoMudanza(máquina, 'pregunta')`.** Real confirmations with sample texts
  (`borrar`, `archivar`, `descartar`, `traer`, `permiso`) and the move in its question, to look at and measure without
  touching anything.
- **`prueba:confirmar` covers every confirmation.** Each way to confirm with its keys, each confirmation of the page
  against the catalog's list (one that says a destroying verb must ask for it, and a file with an unlisted confirmation
  fails), and the ones that don't go through `preguntar`.
- **The projects screen says where things stand.** Projects are a table with their effective state (in progress,
  about to start, closing, paused, finished, closed): the one set by hand in their document, else the one their plazo
  (`telar fechas`, class `plazo`) gives, else the one their document's Estado row says; hovering it says which. A
  project whose plazo is in its closing phase (`etapa` «cierre») goes under «en cierre», below the two that ask for
  direct attention. Each comes with its phase as a circle filled by quarters, its end date («venció 22-oct» once it
  is past), how many pending items it has and, in the warning color, what its source says does not add up. Clicking a
  column's name sorts by it, as in «tareas» (the one sorting, in blue; again, back to the usual order); sorted by
  state, the usual order, the table goes in sections. The stage is an icon for the kind of work in it (prepare, start,
  develop, close, closed), with the word on hover. The ↔ button shows the table extended: full width without the
  detail, every name whole, the stage in words, and the start date, area and what does not add up as columns of their
  own; choosing a project goes back. Between two columns there is one square cell of space, the width of an icon. The
  detail keeps the name, how it is going (phase, start → end, warning, a link to the source), the way to its thread
  and its ⋯ on top, and goes in three tabs:
  «resumen», what asks for attention before what explains (the README's own status sections, the next three pending
  items, what waits on others, what it is, the facts of its card, each cut to six whole lines with «más»), «pendientes»
  and «documento», the README folded by sections, each with a glimpse of what it holds, that open with a click; the
  sections with only the template's hint go last, dimmed. The remembered tab stays when choosing another project.
  What counts as a project and what as a deal is up to the mode (`proyectos`, `negocios`: archetype names,
  ⚙ modes); of the deals it only says how many are in negotiation or with a proposal. The filter rows (folders,
  types, with a thread, with pending items) are gone; search, area and «cerrados» remain. A date can carry `etapa`,
  `avance` (0 to 1) and `aviso`; `telar proyectos --json` brings each unit's `plazo` and the date sources that did
  not answer (`fallas`).
- **Initiatives: your own work, apart from client projects.** The projects screen gains an «iniciativas» section
  under the projects, from the archetypes in `[modos.<m>] iniciativas`, grouped by `agrupar_iniciativas` (for
  example `{frontmatter:programa}`).
  - The initiative whose folder is named after the program heads its group, with its own data. One without
    program or children goes to «sin programa».
  - Each row has the weight circle, owner, state, next decision and tasks.
  - A click on the header shows them alone, and Todo opens them.
  - In Táctica, an initiative's items go under its own name, not «Interno · …». A folder inside a unit belongs to
    that unit.
  - `telar proyectos --json` carries each unit's `frontmatter`. A move between two archetypes doesn't break
    anything while both folders exist.
- **Initiatives show their state and change it from the list.** With a closed vocabulary in `[iniciativas]
  estados`, each initiative shows its `estado:` with its circle and color in the projects tab. A click opens the
  vocabulary and writes `estado:` and `estado_desde:` (today) in the file's frontmatter, only those two lines and
  without committing; also from the detail, with `telar proyectos estado <ruta> <estado>` and `POST /proyectos/estado`.
  `sinonimos` count as their target without rewriting the file, a value outside the vocabulary is marked, and an
  initiative whose file names another source (`estado_fuente`, labelled through `fuentes`) shows «fuente: …» and
  can't be changed here (the server answers 409). `estado_nota` goes in the tooltip.
- **Periodic processes in a calendar.** ⚙ › periódicos shows them in a day or a week: each process is a row with
  its line, grouped by who gets each run (an agent, a new thread each time, or a command), and each run a circle
  at its time: what already ran, filled and faint (red if it failed; in the warning color if it was due and left no
  trace); what is coming, a ring (in the warning color when it reaches its agent's inbox less than 15 minutes after
  another, so it waits its turn). An agent's header line gathers everything that reaches it, so you see where it
  piles up. Picking a process draws its dependencies with right-angle lines, from the run it uses to the run that
  uses it, and says what it is, when it runs, what it uses and who uses it. The list is still there. `telar
  periodicos calendario [--desde] [--dias]` gives the same; each finished run is kept in
  `<estado>/periodicos/<name>.historial.jsonl`, and runs from before that are read from the log.
- **Dependencies between periodic processes.** `despues = ["retro"]` (`--despues`, `--sin-despues`) names the
  processes whose result this one uses; it is for seeing them, cron does not wait. The other kind is deduced:
  processes that go to the same agent share its inbox, and a command that hands work to an agent (`telar encargar
  <agent>`, in its line or in the script it runs) counts as that agent's.
- **A periodic process can open its threads as children of another.** `padre = "Calendario"` (`--padre`, and «cuelga
  de» in the form) hangs each thread it opens under that one in the bar, as `telar hilo hijo` does: it inherits its
  tags, and the parent gets the notice each time the child finishes a turn. Before, they hung from the process
  itself («periódico <name>»), which is not a thread.
- **Creating a periodic process: a skill, a text, an agent.** The form asks for a skill (optional, from the folder
  of whoever does it) and what goes after it (optional; one of the two is required), and shows what the agent will
  get; who does it (a resident agent, in its usual session, or a new thread each time, with its name, folder and
  arguments); when; and which other processes it uses. `telar periodicos ver --json` brings the machine's agents.
- **A module's tab can hand what it shows to an agent.** `window.lienzo.pedir("instruccion", {contexto, destino?,
  texto?})` opens the instruction window with that context: a chat, a record, anything the tab shows.
  - The page handles it alone, and nothing leaves until you press send. The context shows as one row (its name, how
    many lines, which tab it came from) that unfolds whole.
  - The message is optional. Left empty, the agent gets a fixed line asking it to process the context.
  - A default destination for these comes from `[instruccion] destino = "agente:<nombre>"` (or `hilo:<nombre>`); a
    request that names its own destination wins.
  - The context reaches the agent whole, up to 400,000 characters, between two marks that say it is data, not
    instructions.
  - On the server side: `POST /actuar` takes `{contexto: {texto, titulo, origen}}` and
    `telar actuar --contexto - --titulo --origen`, both additive.
- **Three things a module could not do.**
  - **Open an address from its tab.** `window.lienzo.pedir("abrir", {direccion})` opens it in the page, as a click
    on a link would: a task's card, a thread, an object's view. The page handles it alone, without asking permission,
    like «menu». The server answers 400 if it gets one of those two.
  - **Its tab gets its environment.** The command behind a module's `[pestana]`, its `[app]` page and its
    `[configurar]` now receives `TELAR_RAIZ`, `TELAR_REPOS`, `TELAR_MAQUINA` and `TELAR_MODULO`, as its commands
    already did.
  - **A module type can list its objects.** `[objetos.X] listar = "<consulta>"` gets `{"tipo": "X"}` and returns
    `{"objetos": [...]}`. You can list them with `telar objeto <tipo> --listar [--json]` and `GET /objetos/<tipo>`.
    Among the built-in types, tarea, hilo, proyecto and agente list theirs; the others say they don't.
    `telar objeto --tipos` says which can.
- **A module's own settings screen.** `[configurar]` in `modulo.toml` is a command that prints a page, like a tab's
  (usually a canvas). It opens from ⚙ modules (its «configurar») and from a ⚙ in its tab's title; its canvas
  changes the module's settings through the module's own queries, without asking permission. `GET /configurar/<m>`.
- **A dashboard tab as its own app on the phone.** `/pestana/<name>/` is the page with only that tab, without the
  header or the thread list, and with its own manifest: Chrome installs it next to telar, named as the tab shows and
  with the icon of the tab's module (`icono = "icono.png"` in `modulo.toml`, a square PNG; telar's if it has none).
  `<name>` can be the module's name or its tab's (`[pestana] nombre`), so a module that renames its tab keeps the
  installed app's address. On a phone the module's page gets the whole screen, and «back» stays in it.
- **A dot on a dashboard tab with something new.** A block's page can bring `aviso`, a short text («3 chats sin
  leer»): its row in the bar gets a dot, with the text on hover. A block that brings the field is re-read in the
  background every two minutes, whether the dashboard is showing or not; while its tab shows, its canvas keeps the
  dot current with `window.lienzo.aviso(text)`.
- **`?abrir=pestana:<name>` opens a dashboard tab** when the page loads (`pestana:calendario`, or a module's tab by its
  name), and so does `window.telar.mostrar("obj:pestana:<name>")` on a page already open: a phone's home screen can
  have an icon that goes straight to one tab.
- **A reading feed reads calmly: `vista = "lectura"`.** A provider whose tab is a feed of things to read can set
  `vista = "lectura"`, and its card stops looking like a task.
  - The text is serif, about 60 characters per line, while telar's own labels stay in the terminal face and size.
    On top there is only the lane, the topics, the source and date, and «leer el original». The «1/8» counter and
    the numbered keys are gone.
  - Next to the text goes «conexiones» (below it, on a phone). It is described in the next entry.
  - At the end, «tu lectura» is a box for the why. An action that asks for text takes what you wrote there (its
    tooltip says which), and the draft survives a reload. Answering doesn't jump to the next item: the card stays,
    with what you answered, and «sigue» leads on.
  - New optional card fields: `temas` (names, or `{nombre, nota}` so that a topic opens its note), `fuente`,
    `fecha` and `estado`. Without them, the view works them out from the subtitle. `telar doctor` checks the view
    name.
  - Fixed on the way: while typing in a field of the card, ⏎ and ← → are no longer taken as shortcuts.
- **Choosing what a reading adds to the graph.** A card can propose graph relations (`conexiones`: note, type, why
  and an anchor phrase). The reading view shows «conexiones», with one card for each proposed relation and one for
  each other note the text names (paths written as code).
  - Each card is titled with the note it would connect to: its frontmatter `titulo`, its `#` heading, the graph's
    title, or else its file name. Closed, it shows up to three lines of what the note says, in its own words: the
    `>` line under its title, or its first real paragraph (skipping frontmatter, headings, tables, code, images and
    `**Key**: value` metadata lines). The text comes from the document, not from the graph's lede. A proposed
    relation follows on one line, with the type in its color and the why dimmed. At the foot, one dot per
    connection the note already has (up to 30, then «+N»), so a hub shows as one.
  - A click opens the card in place, one at a time, and the others stay in view below. First comes the note to read:
    its path (opens in the viewer), about 180 words of its opening in the reading face, and «seguir leyendo». Then
    five of its connections, plus «las otras N». At the end comes the relation: the type, the why, where it sits in
    the text, and «conectar».
    - The type picker starts at the current type and shows what each type is and what sets it apart, from the card's
      `tipos`, with an optional `color`.
    - The why is a field inside the card, pre-filled for a proposed relation. ⏎ there connects.
    - «conectar» needs a type and a why, and says which is missing. Once connected, the card reads «conectada ·
      quitar».
  - None goes in unless chosen, with «conectar» or the circle (filled in its type's color), and «entran N de M» keeps
    count.
  - A note that can't be read can't be connected, and its card says why. That is a path that isn't in the
    repository (shown in yellow, in the text too), or a folder with no document. A folder's document is its
    README.md, else its index.md, else its only .md.
  - Hovering a relation lights up, in the text, the phrase it rests on, and nothing in the margin moves. A click on
    «en el texto», or a tap on a phone, goes to that phrase. An anchor that isn't in the text is quoted instead.
  - «guardar en la biblioteca · con N relaciones» sends the chosen ones in place of the action's `{conexiones}`
    placeholder, as `[{nota, tipo, porque, titulo}]`, or `[]`. The server checks each one against what the card
    proposed or the notes its text names (worked out the same way as the page, folders by the same rule), and that the
    note exists in the repository. A named one needs a type from the vocabulary and a why, and a folder must be sent
    as its document. Anything else gets a 422. From the CLI:
    `telar tarea <id> --accion N --conexiones '[…]'`.
  - An action can be icon-only in the card's bar (`icono` + `solo_icono`, with `ayuda`). With `procesando`, the card
    says «volviendo a procesar desde las HH:MM» with the spinning circle, and re-reads itself every 10 s until done.
  - The page's common picker (`interfaz.elegir`) gained an `inicial` option, and options can carry a `detail` shown
    in full under the list.
- **Reading tabs in priority order, uncapped.** A `vista = "lectura"` tab lists everything its provider returns,
  ordered by what the person sent themselves (`de`), then priority (high, medium, low, none), newest first (`fecha`,
  or the date its id starts with); each provider row may carry `prioridad`, `de` and `fecha` at its top level or
  inside `campos`. Without `de` or `prioridad` the provider's order stays. The row and the reading card show the
  priority (the task's circle, in its color) and «tuya».

### Changed

- **The starting mode shows only its own tabs, and every custom mode inherits them.** `tactica` (what `estandar` was)
  has `filas = "tactica, calendario"`, and a custom mode is built on it unless it says its `base`, so a 0.13 setup
  loses «ahora», «revisar», «proyectos» and the block and module tabs from its default view. `[modos.tactica] filas =
  "*"` brings them all back, or name the ones you want; the «todo» mode (⌥⇧4) shows every tab. `tactica`,
  `estrategia` and `todo` are now built-in names: a custom table with one of them sits on the built-in mode and can't
  take a `base`.
- **Command providers' fields are checked.** A task provider's `prioridad`, `de` and `fecha` (read from the row or
  from `campos`) and a calendar's `respuesta` are validated: a value outside what they take (a non-ISO date, a
  priority like «urgente») makes the provider fail, and it shows in `fallas`. 0.13 ignored them.
- **Every confirmation and window footer uses one button: "the key in the footer".** The footer of a window is a band,
  one empty line below the content (also when the content scrolls) and behind an edge-to-edge line, split into cells;
  each cell shows the key that presses it and the word, and the whole cell is the button (`componentes/boton.ts`,
  `media/css/boton.css`, tokens `--boton-…`). On the phone the cells share the width and the key is hidden. It is in
  `preguntar` (every `ui.aviso` with buttons), `pieVentana`, `escribir`, contestar, the instruction, the move to
  another machine, the drop strip in the terminal, removing someone's account, the terminal that won't open and
  ⚙ themes. The catalog (`/componentes#botones`) shows it with its states, the rules of focus and ⏎, the other three
  forms that were weighed and why they lost, and an inventory of every confirmation in the page with file:line.
- **What destroys has its own chord, ⌘⌫, never ⏎ alone, and opens with the focus on "cancel".** Deleting a style, a
  mode, a world, a periodic process or a theme; removing a module or an account; discarding held messages or a thread;
  removing an agent; cancelling an errand; and a task or object action whose verb destroys. They are in the danger red
  (the agents' "eliminar" is red now, it looked blue); "cancel" is one: ⎋, in the text color. The full list, with why,
  is in the catalog ("las que destruyen"); "llevar igual" in a move is no longer next to a red "no llevarlo".
- **The key of each cell presses it; ⏎ presses the focused one; a held key presses nothing.** Handled for every window
  by `web/botonera.ts`, which `abrirVentana` installs. The focus is marked with `:focus`, so it shows even when the
  window was opened with a click.
- **One search box and one row of tools in the sidebar: HILOS's, which also searches the archive.** Typing filters the
  live threads and the archived ones: if any archived thread matches, ARCHIVO shows open with only those (and their
  count), and none hides it; folding it while typing lasts as long as the text, and clearing the text puts it back as
  the person left it. ARCHIVO's own search box and sort order are gone (the sort order was the same three options as
  HILOS's, which now applies to both), and so is the submenu variant of the section tools (`enSubmenu`, `.en-submenu`).
  Covered by a new case in `npm run prueba:barra`.
- **Group headers go in normal weight, not bold.** The sidebar's group headers (DASHBOARD, AGENTES, HILOS, EQUIPO) and
  the headers that share their token (`--item-cabecera-peso`: a screen's name, táctica, the day) are told
  apart by their colour and icon, not by weight.
- **⚙ pestañas and ⚙ modos say how they combine.** ⚙ pestañas is the order and what no mode shows; each mode shows the
  ones it names, in the order it names them, and a mode with all of them uses the ⚙ pestañas order. The «filas de
  DASHBOARD» setting left the list of manual changes of the active mode: its row above replaces it.
- **The instruction icon on a reading's card (the «leer» tab) opens a thread with that reading.** It used to send the
  reading as a pending task (to the tasks agent, with `/tarea` and only its title). Now the same instruction window
  comes with «a new thread» chosen, named after the reading, and the card's content as free context: title, original
  link, source and date, topics, each block (summary, why it matters, where it came from), what was answered and what
  is written in «tu lectura» without answering. Its help says so. Tested by `npm run prueba:leer-hilo`.
- **Every search field on the page is now one component, with one rule.** The magnifier goes first and says "search
  here", one character before the first typed one (`--buscador-lupa-hueco`, the grid's space); no placeholder text
  inside: what a field searches («hilos», «tareas») goes to its `aria-label` and to the start of the tooltip, with its
  fields and keys. At the end: the count of what the filter left, the key that focuses it (only while empty and
  unfocused, no longer as "/ buscar" in the placeholder) and, once something is typed, an ✕ that clears it
  (`web/buscadores.ts` handles it for the whole page and fires an `input`, so each view filters with what it already
  listens to). States are told by color only: focused or filtering, the magnifier takes the accent.
  `componentes/buscador.ts`, `media/css/buscador.css`, tokens `--buscador-…`.
  - A search field that is a row of its own is a bar (`barraBuscar()`): the standard bar height
    (`--pantalla-barra-alto`), the screen's padding and a bottom line from edge to edge that separates it from the
    list and takes the accent while typing; what comes with the search (sort, show machines, a button) sits on the
    right, in its square cells. The field itself has no border: four options were compared side by side in the
    catalog (`/componentes#buscador/bordes`) and the bar's line won.
  - Every search field uses it: HILOS in the thread bar, tasks, what waits for you, projects, the inbox, Todo,
    ⚙ modules, the skill filter of a periodic job, ⌘K, the filter of `elegir` and of the ⋯ menu, the two lists of the
    instruction, the palette window, the codes sheet of a thread and the share page. The catalog page shows its
    states, the four borders, its parts and where each one lives. `npm run prueba:buscador` checks the component and
    that every field in that inventory uses it.
- **The folder in a thread's screen bar is dim until hovered.** Word buttons in a screen bar (`.pantalla-boton.palabra`:
  a thread's folder, a view without an icon) go in the bar's dim button color and take their tone, or the hover color,
  only on hover, like the icon buttons; the folder no longer sits in blue.
- **`GET /salud` says where the page is served (`web`).** Checks reach the page on its real port instead of guessing.
- **Parent and child talk outside the hop limit.** A message between a thread and its direct child carries
  `saltos: 0` and its own count, which restarts with a commit in the child's folder, when the person speaks to
  either, or when it's released. The «listo → git merge main → listo» pattern no longer hits the 6-hop limit; the
  limit still stops two agents answering each other without doing anything, and the hourly cap still applies.
- **Lines and icons follow one grammar.**
  - Every line is the same color, the one under the mode band too (the world shows by its name in the band). Foco
    has no line on top.
  - The sidebar's separators run edge to edge: the line is now the top edge of the next section header, on its own
    background, and a folded section no longer leaves two lines with a gap.
  - Between two icons in a row there is always a square space (`--entre-celdas`, `--entre-iconos` in tokens.css): a
    screen's views and actions, a header's fixed actions, hover and card actions, the HILOS band, star and share.
    The rule is written in item.css and gramatica.ts. On a phone, the HILOS band keeps its icons together for now.
  - The ‹ that folds the sidebar moves from DASHBOARD to the right end of the notice strip.
  - The right column (the side panel) gets its own bar with a line, level with the sidebar's and the center's.
- **Asking for a text is a window like the others.** The prompts for a line, a longer text or a question (`campo`,
  `escribir`, `preguntar` in web/interfaz.ts) now open on `abrirVentana`, with its frame, its footer and its keys,
  64ch wide.
- **Choosing from a list is a window too.** `elegir` (which machine to move a thread to, and every other list
  chosen with ↑ ↓ ⏎) opens on `abrirVentana`, 64ch wide, with the shared search box as its filter, rows aligned
  with the title and the selected option's full detail below a line. The old `<dialog>` box (`caja()`) is gone.
- **⌘K is a window too.** The search window opens near the top on `abrirVentana`, 80ch wide with a fixed 16-line
  list, its rows drawn with `item()`; ↑ ↓ ⏎ ⎋, remote sources and ✕ work as before. It no longer snaps to the
  background's character grid.
- **The ⋯ menu is a window too.** `menu()` (right click on a thread, the ⋯ of a row) opens on `abrirVentana` next to
  what opened it, rows drawn with `item()`, with its filter, ↑ ↓ ⏎ ⎋ and a click outside to close; when it doesn't fit
  below, it opens above.
- **The header writes what you see as its address: «laptop:Telar»,** colon and no chevron. Another machine's
  thread still reads «laptop ⇢ servidor:Telar».

- **A first pruning of the dashboard** (step 1 of `docs/propuestas/orden-por-modos.md`).
  - «te esperan» gets the key t and sits right after «ahora». A built-in tab that `[dashboard] orden` doesn't name
    now goes next to its usual neighbor instead of after the modules. The bar and ⚙ pestañas share that rule.
  - Apps (games, viewers) leave the thread bar for a menu in the header, shown only when there are apps.
  - What has been overdue for more than 30 days is debt. Tasks and checkboxes alike leave «esta semana», the
    «si sobra» of «ahora» and the top of foco, and get their own «deuda» filter, with its count. They stay in
    «todas» and «vencidas». A starred task stays in «esta semana».
  - Each row of «te esperan» shows the priority and due date it already carried, as task rows do.

- **The page's header fits its width, and its right-hand buttons are always there.** Only CSS, with a container query
  on the header measured in characters, so it follows the page's font size. As it narrows, what goes first is:
  - the running version, shown only from 120 characters on (still in the logo's tooltip and in ⚙);
  - in the middle, the machine name before what you're looking at; when you're looking at something and space is
    short, only its name stays;
  - under 64 characters (phones), «telar» becomes «T», the new-version notice keeps only its icon and «‹ hilos»
    becomes «‹».

  The buttons on the right keep their column at every width, and now respond across the header's full height, not
  only on the icon.

- **What destroys something asks with the focus on «cancelar», and discarding a live thread asks first.** A
  distracted ⏎ now means «don't».
  - With the focus on «cancelar»: discarding an archived thread, removing a module, deleting a scheduled job, a style
    or a mode (or resetting it), cancelling an errand, an object's actions, a task action that asks to confirm, and
    the permission a module asks for («Permitir siempre» used to be first, and the box can pop up while you type).
    Taking someone's account away starts on «no».
  - Discarding a live thread, by the ✕ on its row or by ⋯, used to happen without a question. Now it asks, says that
    it is alive (and where, and whether it is working), and what is lost: the thread ends, skips ARCHIVO and can't be
    resumed with a click. Its conversation stays on disk. To keep it, archive it.

- **Every thread says which machine it lives on, and `telar hilos` says the list is only this machine's.** Without
  `--red`, `telar hilos` lists only this machine's threads, and nothing said so. An agent on the server looking for a
  laptop thread found 98 threads with an empty `remoto` and concluded it didn't exist, though it was in
  `otras_maquinas` of `--red`.
  - In `telar hilos --json` and `GET /hilos`, there is a new top-level `maquina` (this machine, by its bus name), and
    every thread, here or in `otras_maquinas`, carries its own `maquina`. One command tells where any thread is.
  - The text header names the machine. With a bus and without `--red`, a last line says the other machines need
    `--red`.
  - The agent's start-up context and the threads skill point to `telar hilos --red --json` when there is a bus, and
    explain the two lists. `docs/contratos.md` says what `remoto` is and isn't, and that a name repeated across
    machines can appear in both lists.

- **Two more components: the list section's tools and the window frame.** The thread bar's separator, its tool band
  (search, sort and the machines) and its «nada calza» row now come from `componentes/seccion.ts` instead of being
  written by hand; the bar looks the same. The module search in ⚙ uses the shared search box. `componentes/ventana.ts`
  is the frame of what opens on top of the page: header, field, body and footer, centred, at the top (like ⌘K) or
  next to the click (like the ⋯ menu), with `paleta` for a window with a filterable list. The catalog shows them.

- **Cards are a component, and foco uses it.** A card is an item that doesn't get cut: a header (its circles, the
  whole title over several lines, and its actions top right in their own column, shown on hover and on the selected
  card; on a phone just ⋯), an optional body, and a footer with its data and, on the right, a mark and a meta value.
  No frame or background of its own: cards are separated by space, the selected one gets the selection background,
  and what's wrong is said by the pieces (an overdue date in red), never by a colored border. It has its own tokens
  (`--tarjeta-…`), a page and an anatomy plate in the catalog. Foco's cards are built with it, with the same pieces as
  a task row (priority and state circles, star, new date, the instruction, done, ⋯); concentration uses the roomy
  variant.
- **Task lists follow the design system.** Every list of tasks (the «tareas» tab, an email's tasks, a project's
  detail, «ahora», a provider's tab) uses one row, built on the item like a thread in the sidebar: priority and state
  as circles (in progress filled, waiting for your decision a ring, P0 filled in red), code and project in aligned
  slots, the text on one line (whole on hover) with what the agent left and the owner when it isn't you, the star
  (a ring with a dot) and the date at the end, and on hover star, new date, share, the instruction and done, with ⋯
  for the rest. «tareas» is no longer a table: no column header or colored frame; it gets the sidebar's tools (search
  with its count, and the sort group: date, priority, star, project, owner, code, alphabetical) above its filters.
  Changing a task's priority moved from clicking its icon to ⋯.
- **One way to send something to a thread: the instruction.** Foco's «con Claude» and «empezar ahora», «Acción…» in
  every entity's menu, «encargar» on an agent, «escribirle a <agente> sobre este proyecto…» and the two «Llevarla…»
  items of a README checkbox are now one window, «instrucción», with one icon everywhere: what it is about (the
  entity, sent as context), to whom (its thread, a new one, an agent or any thread), the skill (the recipient's; foco
  and a task's file suggest /tarea) and what you ask, with the exact line it will get at the bottom. A task's file has
  it in its bar. Which thread is «its thread» is telar's call, for any entity: a task's or a checkbox's goes where
  `telar pendiente` takes it (its project's thread, here or on another machine, or the pending-tasks agent), a thread
  is itself, an agent gets an assignment, anything else follows the project or thread it links. `telar actuar` gains
  `--nuevo`, `--donde` (where it would go, sending nothing; `POST /actuar/adonde`) and works without an entity (just
  `--a`). A new thread for a task that has none opens in its project's folder, not the root. Resuming a thread has
  its own icon now; the instruction took the old one (docs/propuestas/instruccion.md).
- **A task's file: its actions are icons, and «escribirle a…» is the instruction.** The provider's actions whose
  role is known (done, discard, «esperar a…» as a pause, «tamaño…» as a wristwatch, and date, priority and owner when
  the subtitle doesn't show them) are icons in the file's bar, each with its tooltip and key number; the rest keep
  their key and word. A task's ⋯ uses the same icons, and its «instrucción…». The file's «escribirle a Claude» button
  and its own draft are gone: the instruction icon does it. The instruction keeps what you wrote and didn't send, per
  entity, with its recipient and skill: opening it again from anywhere (the file, foco, the row) brings it back; it
  goes away when sent. «Procesarlo en un hilo» on a block's item (an email) opens the instruction with the module's
  message written and «un hilo nuevo» picked, instead of opening the thread outright.
- **Delegating can go to an archived thread.** In the instruction window's «a quién», after the open threads and the
  closed ones come the archived ones, folded under an «archivo · N» row (a click opens it; searching finds them
  without opening it). Picking one says what will happen: resumed with its conversation, opened fresh because its
  conversation is gone, or resumed on the machine where it lives. Sending something to a closed or archived thread of
  this machine now takes it out of the archive and resumes it with its conversation, the request as its first
  message, without stealing the focus («retomado»); before, it failed with «can't find window». For a thread on
  another machine the request goes to its inbox and that machine resumes it.
- **What is sent about a task stays in its history.** `telar actuar` (and `POST /actuar`) notes on the task
  «instrucción a «X»: …» (what was asked, without the context); if the note fails, the instruction still went out and
  the new `aviso` field says why. `telar actuar --nuevo --nombre` without an entity opens a new thread in the agent's
  folder (`nombre` in `POST /actuar`).
- **Foco's actions are a band of icons above the cards.** The dotted boxes with words on the right are gone: each
  action is an icon in the color of what it does, its name in the tooltip, in groups separated by a short rule and in
  the same order in both modes (see · done · date and size · hand it on · first step and merge · discard). Shortcuts sit
  in words beside their action: «hoy» (when overdue, replacing «va hoy») and +1/vie/lun beside «nueva fecha»;
  «rápida»/«larga» beside the size clock; beside the instruction, «trabajarla» (the file's «trabajar en un hilo»: to the
  task's thread with «Veamos T84» typed, unsent, and it takes you there; on the phone an icon with no tooltip didn't say
  so) and, in concentration, «bloquear tiempo». While dragging a card, every action shows its name and the one
  underneath is marked (and unmarked when the drag leaves them). On the phone the band goes below the cards. A new
  component, `casillas` (`componentes/casillas.ts`, `casillas.css`), with its page in the catalog; a new icon for «es
  la misma que…».
- **The filters of «tareas» fit in one row.** What to look at (this week, to review, overdue…) stays in sight, each
  option with its count; area and owner are folded: they show what's chosen (or their name) and a ⌄, and a click opens
  a menu with their options and counts. «todas» is gone from area and owner: a second click on the chosen option
  releases it, as in sorting; a remembered area or owner that no longer has tasks is released by itself. On a narrow
  screen the row breaks by groups. A new component, `filtros` (`componentes/filtros.ts`, `filtros.css`), with its page
  in the catalog.
- **The archive is a submenu at the end of HILOS.** Archived threads are threads too: ARCHIVO is no longer a
  section of its own but a folded row at the end of HILOS, «› archivo N», its arrow right before the names and its name
  in their column. Open, its rows sit in the same grid as the threads above; folding HILOS folds it too, and whatever
  jumps to the archive opens HILOS first. The submenu is a new variant of the list item (`variante: 'submenu'`, token
  `--item-submenu`), with its page in the catalog.
- **The sidebar remembers which sections you left open.** Every header (DASHBOARD, AGENTES, HILOS, EQUIPO, APPS and
  the ARCHIVO submenu) stays open or folded as you left it, also after reloading the page. Only what differs from how a
  header starts is kept, in the browser's storage, and the sidebar works the same without it.
- **An agent's home is an icon on hover.** In AGENTES the word «home» no longer sits on every agent's row: a house
  icon appears with the row's other actions when the mouse is over it, and on the phone it is in the row's ⋯. An agent
  with no open thread now has a ⋯ too (its home, open or resume its thread, and what the server offers, like
  «encargar», and last, in red, deleting it with the usual confirmation): a page-registered entity type can now also ask
  for the server's actions (`registrar(…, { conServidor: true })`) and put some after them (`alFinal`). In the menu of
  an agent's thread, what belongs to the agent (its home, open it, delete it) now sits apart, at the end, under «su
  agente», so the thread's red «descartar» and the agent's red «eliminar» no longer touch. Deleting an agent asks with
  the focus on «cancelar» (`ui.aviso(…, { foco: 'cancelar' })`).
- **Each section header in the sidebar leaves room between its fold arrow and its title.** The title now starts in
  the same column as the rows below it, the half cell every row keeps between its icon and its text; the search band
  under a section moves with it.
- **«Bloquear tiempo» is an instruction.** Still one click, it now goes through `telar actuar` (to the task's
  thread, with /tarea and the fixed ask), so it stays in the task's history.
- **Icon buttons are square.** A button with only an icon takes a square cell, the row's height on each side, the
  same for every one; words and odd-width signs no longer stand in for icons (the sort options `!` and `a-z` are now
  icons, the bar's fold `‹` too). A button with a word («home») is a word button and sizes to it.
- **New is a plus.** Creating something in a section is the `+` icon alone, without the word, always the last action
  of its section's header (the right edge, the same column in every header); only the bar's own fold `‹` goes after.
- **Things in progress move only their icon.** A thread closing, archiving or travelling to another machine, a task
  being marked done, a version installing, a message sending, a periodic job running: each shows a circle that moves
  in place, a quarter at a time, while the words beside it stay still. It empties for what is leaving, fills for what
  is completing or arriving, and turns, half full, for what is on its way. The circle (`componentes/circulo.ts`) comes
  in three sizes and any fill, matching the priority icons; the catalog shows the family. Before, «cerrando…» grew its
  dots and shifted the text, and a travelling thread's icon cycled colors.
- **A row's actions unfold from the right on hover**, quick and easing out, each a moment after the one on its
  right, behind a faint rule that sets them apart from the text they cover. The «⋯» (more actions) is always the
  last one, at the edge, here and on the phone.
- **The rows of the thread bar are items** (`pagina/src/componentes/item.ts`): a leading section of fixed-width icon
  slots (priority, attention, where it lives), the text (prefix, title, suffix) and a trailing section (a notice, the
  meta text, fixed actions, and the ones that appear on hover, ⋯ last). Same look as before; a dashboard tab's dot
  moved to the end of its row, and group headers are written in lowercase and uppercased by the theme.

### Deprecated

- **`telar mensaje --modo consulta`.** It wasn't a message: it read a thread's card and last turns, as `telar ficha`
  and `telar hilo leer` do; use those. It still works, with a one-line notice on stderr, but help no longer offers it.
  `GET /mensajes/consulta` still answers but leaves the schema.
- **`telar agente aviso` is now `telar agente evento`**, so «aviso» names one thing less. The old name stays as a
  silent alias, because installed hooks call it. `telar agente instalar` writes `evento` and recognizes the old hooks
  as its own, so it replaces them instead of adding a second set; run it once after upgrading. The mod calls `evento`
  too. From now on, every new mechanism says what it replaces, or why it replaces nothing (`docs/propuestas/README.md`,
  `docs/desarrollar.md`).
- **`servidor/desplegar.sh` is retired in favour of `telar desplegar`.** It warns and calls `telar desplegar`;
  `--solo-servidor` is now `--maquina <name>`.
- **The `estandar` mode is now called `tactica`.** `estandar` stays as an alias, in the config and in what the browser
  had stored.

### Removed

- **The «plan» tab of the dashboard is gone.** Its drawing of the day's plan as text (summary, risk, priority,
  people, gaps, the draft notice, the comment box) and its key `d` (free again for `[atajos]`) went with it, as did
  the «the plan of that day» button in the calendar's bar. The plan stays as data: the planning skill still writes
  it (`[resultados.plan]`), Táctica still crosses it with the agenda and the calendar still draws its blocks. «sin
  plan de hoy» in Táctica is now just a line: it no longer opens the tab. The page's `PantallaPlan` is now
  `PantallaCalendario`.
- **Blocks that went on top of the plan tab (`en = "plan"`) are retired.** A `[bloques.x]` with `en = "plan"` or
  `dentro = "plan"`, or a `[vistas.x]` with `aparece = "plan"`, no longer breaks the configuration: it is left out
  (`Config.retirados`) and `telar doctor` warns about it, as it does for `plan` in `[dashboard] orden` or `ocultas`
  (ignored too): delete those lines, or give the block its own tab. `telar config --json` and `GET /config` no longer
  send a block's `en`.

### Fixed

- **A request to a machine that doesn't answer says why.** `telar.bus.pedir`, with nobody answering, uses the
  machine's snapshot: «laptop fuera de línea desde 14:02» (`fuera_de_linea`, `desde`), or that it is online and its
  telar is older and doesn't serve that verb (`viejo`, `version`). `telar hilo leer --maquina laptop` with the laptop
  off used to say the laptop «no atiende «leer»».
- **A thread's terminal in the page now resizes its tmux window live.** Dragging the terminal's edge (or resizing the
  browser) changed xterm.js and sent the new size, but the tmux window kept the size the view was opened with until
  the page reconnected: `telar mirar` ran in a new session (`start_new_session`) with the PTY only inherited, so the
  PTY was not its controlling terminal and the kernel's SIGWINCH reached nobody. The child now takes the PTY as its
  controlling terminal (`TIOCSCTTY`) before becoming `mirar` (`telar.terminal.con_terminal`).
- **⎋ in a move's question closed the panel and left the move waiting forever.** Now it is "no llevarlo".
- **Reading `ps` and tmux no longer crashes on a line cut mid-character.** `ps` truncates long arguments by bytes,
  so a line could end in half a UTF-8 character and `telar hilo dormir` (and the node, every 30 s) died with
  `UnicodeDecodeError`. The process list and everything telar reads from tmux (captured panes included)
  are now decoded with replacement characters instead.
- **A bare file name an agent writes under a folder it just named opens that folder's file.** An agent writes «In
  `notas/artículos/x/`:» and below it «`original.md` — the full text»; a click on `original.md` (in a
  thread's terminal, conversation or reading) used to resolve it against the root and the viewer said «no existe».
  The page now sends the backend of the thread's machine (`GET /api/archivos/resolver`, `telar.servicios.resolver`;
  another machine's node answers it by the bus, as `archivo-leer` with `resolver`) the path as written, the thread's
  folder and the folders named earlier in the same message, nearest first (in the terminal, up to the message's
  bullet). A bare name is looked for under those folders first, then in the thread's folder and the root; a path with
  folders, as written first. If it is still missing, it is searched by name under the root (and the thread's folder,
  if outside it): one opens, several are offered in the viewer to choose from, the closest to the message first,
  instead of «no existe». Accents don't get in the way: a path with `í` composed or decomposed (NFD) is one link,
  whole, and finds the file either way. An older node that doesn't know how to search falls back to the old lookup.
- **`telar commit` no longer reports «subido» while other people's uncommitted changes sit in a stash.** To rebase
  onto what arrived, git's `--autostash` set aside the dirty files of other threads; when it could not put them back
  (enough that another process held `index.lock` at that instant, as any `git status` does), git stored them in the
  stash list, said so only on stderr and exited 0, so the files stayed out of the working tree with no warning. Now
  telar sets them aside in a stash of its own and puts them back with `git stash apply`, retrying while the lock is
  taken. If someone wrote one of those files meanwhile, or they still can't go back, it does not push: the state is
  `apartado`, the exit code 3, and the message names the stash, its files and the commands that restore them
  (`--json` adds `stash` and `apartados`). A rebase that fails and cannot be aborted is no longer reported as «left
  as it was», and the set-aside changes are not put back on top of it, where the later `git rebase --abort` would
  wipe them.
- **`telar periodicos` writes the crontab from the node too.** The node runs with `NoNewPrivileges`, which voids the
  setgid bit `crontab` needs on Linux: a change asked through the bus or the page wrote `periodicos.toml`, failed with
  «crontabs/<user>/: fopen: Permission denied» and left cron running the old block (a paused process kept running).
  There `crontab` now runs as a transient unit of the user's systemd (`systemd-run --user`), which does not inherit
  the restriction. If the crontab still cannot be written, the order says the file changed but cron did not.
- **Tests can't reach the live tmux, thread or telar state of whoever runs them, and run faster.**
  `pruebas/conftest.py` (`comun.aislar_sesion`) removes `TMUX`, `TMUX_PANE`, `TELAR_*` and the Claude Code session
  markers, and points `HOME`, `XDG_*` and `TMUX_TMPDIR` at a per-session temp folder; before, the suite wrote to the
  real `commits.log`, `concesiones.json`, the gws cache and the shell history, and a run from a thread could close
  that thread's window. The full suite runs in 4 processes with pytest-xdist (`--dist loadscope`, 70 s → 21 s) when
  it is installed (the `pruebas` extra), and at most two full suites run at once per machine (a `flock` turn that
  says whom it waits for). `prueba:contestar` skips its fake pauses (34 s → 0.5 s), `prueba:eco` runs on a fake
  clock, and `scripts/senuelo.py` runs the suite against decoys and fails if any of them changed.
- **Threads no longer inherit the Claude Code session that opened them.** A tmux server started from a Claude Code
  shell kept that session's markers (`CLAUDECODE`, `CLAUDE_CODE_CHILD_SESSION`, its session id and messaging socket)
  in its global environment and handed them to every new pane, so new threads started with transcript saving off.
  telar now starts its tmux server without them, clears them from an existing server on `telar tejer`, and strips
  them from agents, windows opened by periodics and errands, and periodic commands; also the requester's
  `TELAR_HILO`, `ZELLIJ_*`, and Claude Code's `GIT_EDITOR=true`. User settings such as `CLAUDE_CODE_USE_BEDROCK` or
  `ANTHROPIC_API_KEY` still pass. The tests that start tmux use their own socket.
- **A markdown link in a thread's answer opens with a click.** Inside tmux 3.4 or newer, Claude Code writes
  `[Doc](https://…)` as an OSC 8 hyperlink that shows only «Doc», and tmux passes the address only to a terminal that
  says it understands hyperlinks. The page's terminal didn't say so, so «Doc» arrived without its address. The page
  now attaches with `tmux -T hyperlinks` (`telar mirar --enlaces`), on the laptop and the phone.
- **A task marked done stays gone.** In Táctica it vanished for a second and came back until the page was reloaded:
  the dashboard repainted with the day read before closing it, and the reread after it was skipped if another was
  already on its way, so the old read stayed cached for five minutes. Each read now knows which change it started
  after, and one from before a change is dropped. What the provider already closed stays out of every list while the
  day is reread. If closing fails, the row comes back and says why. The ✓ also strikes Táctica's rows at once.
- **Titles lose markdown escapes.** «# 01\. Reconocimiento» reads «01. Reconocimiento» in every view
  (`lectura.sin_escapes`); backslashes inside code and those that escape nothing stay. An escaped `*` or `_` no longer
  opens an italic.
- **⏎ in a picker no longer reaches the page** behind it.
- **A screen's bar is always its height.** An icon in it stretched the line height by a pixel, so its line sat
  one pixel below the sidebar's.
- **The page no longer gets two 404s on load.** It asked for `/dev/cambios` even without `--dev` (now `<meta
  name="telar-dev">` says when), and for a canvas memory that didn't exist yet (now `GET /archivos?si_hay=true`
  answers 204).
- **Bus replies over 1 MB arrive.** NATS carries 1 MB per message, so a node whose answer was bigger (the task list
  from the other machine weighed 1.46 MB) couldn't send it (`MaxPayloadError`) and the asker waited out its timeout. A
  reply larger than `max_payload` now goes gzipped, and if it still doesn't fit, an error comes back at once. Every
  machine on the bus needs this version.

- **Two threads whose names differ only in case or accents no longer share a mailbox.** A mailbox folder, its bus
  subject and its state key all came from the name lowercased and without accents. So «Estrategia» and «estrategia»
  were one mailbox: a message for one reached the other, even when sent by id.
  - Now, when names clash, one keeps the usual mailbox and the others move to `<forma>_<6 hex of the exact name>`,
    the same on every machine, noted in `<estado>/casillas/fichas.json`. The one kept is the one that reads it: alive
    or an agent, never an archived one over a live one. Whatever was pending moves to its exact owner, and nothing
    delivered is lost.
  - By id or address (`@2`, `hilo:X`) a message goes to exactly that thread.
  - A name goes to the live thread, whatever the case. Between two live ones, the exact name wins, and a spelling
    that matches neither is refused, naming both.
  - `telar hilo hijo` and `telar hilo renombrar` refuse a name that clashes with another thread (alive, archived,
    an agent, or on another machine) and suggest another. Renaming carries the pending mail along.
  - Every machine on the bus should run this version at once. An older telar still sends to the shared mailbox.

- **Long text reaches a thread.** tmux refuses any command over about 16 KB («command too long»). That broke sending a
  long text to a thread and opening or resuming a thread with a long first message. Text now goes in through
  `load-buffer -` (stdin), and a command over 12,000 bytes runs from a small script that deletes itself.

- **A module's addresses are links from the first object view.** The page linked addresses with the built-in types
  only until it learned the module types, and didn't go back. So `decision:x/D-001` showed as plain text in the first
  object view after loading. Now what was drawn early is linked again when the types arrive.

- **`telar serve --socket` is more careful.**
  - A path longer than a Unix socket allows (103 bytes on macOS, 107 on Linux) fails in one line before starting,
    instead of with a traceback.
  - Only the default folder, or one it creates, gets closed to 0700. An existing folder (such as `/tmp`) is left
    alone, with a warning if other users can get in.
  - It used to delete whatever was at the path. Now it replaces only a stale socket; anything else is reported and
    left alone.

  `scripts/dev.py` uses one socket per port, so two development servers no longer step on each other.

- **`telar mensaje --retenidos` shows every held message.** It looked at the last 200 messages while `--soltar`
  looked at 500, so it said 1 where there were 14. Both, and the inbox, now use the same window. `telar serve`
  reads the bus log incrementally (only what's new since its last read), so `GET /esperas` takes about a second
  after the first call instead of five every time.

- **⏎ does something in a box with buttons.** Its buttons are links without an address, and the browser doesn't press
  those with ⏎, so the focus decided nothing. Now ⏎ presses the focused button, ⇥ reaches every button, and the ⏎
  stops there instead of reaching the dashboard behind, which would take it as its own once the box closes. Boxes
  that don't destroy anything (installing, archiving, marking done) can now be confirmed with ⏎.

- **A web address between code quotes can be clicked in the conversation view.** Markdown only links bare
  addresses, so one the agent wrote inside inline code (`` `https://…` ``) or a code block showed as text you couldn't
  open. It now opens in another tab, like any other link.

- **A thread that died while its node was down no longer stays alive on the bus.** Nor does its window blink on the
  other machine any more. The node only published as dead a thread it had published alive in the same run, and that
  memory started empty. A thread that died with the machine (a forced server reset) or while `telar serve`
  restarted stayed `vivo: true` in `TELAR_HILOS` for good. The laptop kept reopening its window every ~55 s, the
  window died in ~7 s because it no longer existed over there, and the bar showed it open and closed.
  - On startup the node reads what the bus says is alive on this machine and starts from that, so the usual rule
    (missing two rounds in a row) publishes as dead whatever isn't here. Entries that name another machine are left
    alone. The log says «el bus lo daba vivo aquí desde antes de que arrancara el nodo y aquí no está: lo publico
    muerto». If the bus doesn't answer then, it says so and tries again every 30 s.
  - A thread that another machine already publishes (it moved there) is no longer published as dead from here,
    which used to overwrite its state.
  - On the watching side, a remote thread's window that closes by itself is reopened at most three times in five
    minutes. After that the log says «allá no contesta: no la reabro más» once and stops. The count resets when
    the thread's address changes or it publishes anything new.
- **The viewer opens what a child thread on its own branch names.** A child with `--rama` works in a worktree outside
  the repository root (`~/worktrees/<repo>-<branch>`). A file its agent named, relative or absolute, opened as «ese
  archivo está fuera de la raíz del repositorio». What the page may read is still a closed list, and it now includes
  the folders of this machine's threads: each thread's link and each child's worktree (`telar.ramas`). A thread
  linked to the home folder or above doesn't count, and neither does a symlink that leads out. Writing is still
  only under the root.
  - The viewer without a thread (`arch:`) walks the folder that holds the file (the root, a repo or a thread's
    folder) without leaving it. Paths outside the root come back whole, with `~`.
  - From another machine, the viewer asks that machine's node for the document (`archivo-leer` with `documento`),
    so its folder can be walked there. A node from before answers with the file alone, as before.
  - Fixed on the way: a relative link in a document from another machine lost the machine when the document sat at
    that machine's root.
- **A message between threads is no longer lost, or announced over and over, on a loaded machine.** With the
  machine busy, the mailbox hooks took 4 to 11 s and Claude Code cut them at 5 s. The agent then saw only the
  «↯ mensaje nuevo» line, cut to 70 characters. A message whose hook was cut after marking it delivered never
  arrived at all, and the Claude Code mod queued the same notice every 2 s until the turn started (five or six copies
  in a row).
  - A message now counts as delivered only once the conversation shows it came in. The hook leaves it in
    `<mailbox>/camino/` with the transcript and how far it went. The next hook run (or the mod's poll) looks for its
    header (`id <mid>`) in what was written since: if it's there, the message is delivered. If it isn't, and the hook
    that carried it is gone, it goes back to wait and comes in again, marked «otra vez», so the agent doesn't redo it.
    It may now arrive twice, never zero times; after 5 tries it is delivered anyway, marked `sin_confirmar`.
  - The hooks import only what they use: no pydantic, asyncio, the bus or the services. The address helpers moved to
    `telar.direcciones`, and `telar.objetos` re-exports them. Importing the hook path went from about 1 s to about
    0.1 s. The mailbox and context hooks get 30 s instead of 5 (`casilla.PLAZO_GANCHO`); `telar agente instalar`
    applies it.
  - The mod doesn't send a notice while the previous one (or a prompt from the person) is still waiting for its turn.
    After 120 s it gives up waiting.
  - `telar agente casilla --leer [--hilo H] [--json]` shows what is waiting, in full, and marks it delivered: for an
    agent that got only the notice line. The session context names it, and the installer allows it.
- **Opening an agent's thread from the sidebar works again.** The ▷ of an agent with no open thread sent its address
  (`agente:x`) where the folder was expected, and the server answered that there was no such agent.
- **Releasing a thread releases it from the one that opened it, too.** `telar hilo padre ninguno` (and «soltar» on
  the page) only removed a parent that had been set by hand; a thread opened by another one kept hanging from it in
  the sidebar, in its children and in the turn-end notice. Now it is marked as released (an empty parent in
  `padres.json`), and who opened it is still known; hanging it again works as before.
- **An agent whose folder is only on this machine says so.** When agents live on another machine (`[agentes] en`)
  and that machine doesn't have this one, opening or deleting it answered «no hay un agente». Now it answers 409 with
  what is going on and the two ways out (get its folder there, or `[agentes.<folder>] en = "aqui"` here), and the
  agents view marks it «solo en esta máquina» instead of «sin noticias» (`solo_aqui` in `GET /agentes`).
- **An action in a task's file that hit «changed since it was read» (409)** dropped the cached file under the wrong
  key, so the next try failed again; now it reads the task again.
- **Restarting telar no longer wipes the thread list.** While the page's API didn't answer (every install restarts
  `telar serve` for a few seconds), the whole sidebar turned into the error. Now the list stays (it's the last thing
  known); only after 15 s without an answer does one line on top say since when, with «reintentar». It retries every
  2 s and right when `/eventos` reconnects, and the other machines' threads no longer vanish while it's down. With no
  list ever read, the error still fills the sidebar.
- **A struck-through Estado no longer shows as the state.** `telar proyectos` skips what the Estado row strikes
  through (`~~…~~`, what no longer holds) and a note's leading date («16-oct: activo, …»): «~~Activo, sin
  empezar~~ **16-oct: activo**» is «Activo», not «~~Activo»; `estado_completo` comes without the struck part.
- **A restart no longer shows as «down».** A bus request that nobody hears (`NoResponders`, as while a machine's node
  restarts) is tried once more after 2 s before saying «doesn't serve it»; it never reached anyone, so repeating it
  duplicates nothing.
- **Threads stayed «finished, unseen» for good.** Seen only counted switching tabs in the multiplexor, and nothing
  told telar when the page showed a thread, so almost every finished thread kept its mark. Now showing a thread in
  the page (opening its terminal, and leaving it) counts as seeing it, the thread on screen counts as seen, and a
  thread from another machine takes the newer of both machines' times. Once seen, a finished thread shows nothing:
  there is nothing left to say.
- **What you do in the page shows at once.** Seeing a thread (opening it, or leaving it for another) and changing a
  priority show in the bar right away instead of at the next poll; the page keeps that on top of what it reads until
  the server says the same, for up to a minute (if the change fails, it goes back at once).
- **The server tells the page when something changes.** `/eventos` (server-sent events) says «hilos» as soon as
  telar's state changes (a thread's attention, seen, a priority, an archive, the focus) and «espejos» when another
  machine's snapshot arrives; the page rereads at once instead of at its next poll. Polling stays as a fallback,
  slower while the events arrive (every 10 s instead of 3), for what doesn't go through the state.
- **Seen crosses machines, and tmux tells it too.** A thread seen from the laptop counts as seen on the machine it
  lives on (its snapshot carries it back), threads listed from another machine's snapshot show whether they were
  seen (the snapshot now carries `sin_ver` and `atencion_desde`), and switching tabs in a tmux terminal counts again:
  weaving the session sets hooks that run `telar tiempo marcar` when its window changes with someone attached.
- **A child thread doesn't show its own priority.** It hangs from its parent and takes the parent's; its priority
  slot stays empty, so the column still lines up.
- **A thread's row in the bar shows its tooltip again** (its folder, state, today's time and the first pending
  items); since 0.11 the attribute was broken.

## [0.13.0] — 2026-11-09

### Added

- **A module's page can ask its own module.** `window.lienzo.pedir("consulta", {verbo, params})` runs one of the
  module's own queries (`consulta = true`) and returns what it gives, without asking permission: it is the same
  module's code, reading or changing its own state, not your documents. A page can load what did not fit when it was
  drawn (a chat's messages, a search) or keep what is chosen in it (a chat's label).

## [0.12.0] — 2026-11-09

### Added

- **What a thread's codes mean, beside it.** A thread that runs a project names its work with codes (`H3` a
  hypothesis, `PEN-07` a pending item, `T84` a task) and the person loses track of them. The right-hand bar now has a
  «códigos» sheet for any thread: the codes its conversation named, latest first, and the ones its folder defines,
  grouped by prefix and named after their section («Pendientes»), with a search box and, on click, the definition
  (the section's text or the row's columns), its file (opens in the viewer) and where else it is named. Nobody
  declares them: `telar.codigos` recognises the three ways a document defines a code (a heading, a table row with
  the code in its first column, a bold bullet) and keeps only those named outside their own file. A task is shown
  as the task. Computed on the thread's machine (bus verb `codigos`); also `telar codigos [hilo] [--buscar]
  [--codigo]` and `GET /codigos`. An agent's thread shows its card and its codes as two sheets. The codes the sheet
  knows are links in the thread's terminal (⌘-click), reading and conversation views: a click opens the bar on that
  code.

## [0.11.0] — 2026-11-04

### Added

- **Threads hang from a parent: a project thread with its work streams.** `telar hilo padre Telar` (or drag a thread
  onto another in the sidebar; onto the HILOS header to let it go; or ⋯ › colgar de…) makes it a child: it nests under
  its parent (also across machines), takes its tags if it has none, and its agent knows it (its start context says
  whom it hangs from, and a parent lists its children with their state). **A child that ends a turn leaves its parent
  a notice** (it doesn't wake it) with the last thing it said, at most every 10 minutes, and another when it's
  archived. `telar hilo hijo «Mobile» --texto "…"` (⋯ › hilo hijo nuevo…) opens a child with its agent, in the
  parent's folder unless `--carpeta` says otherwise, with the brief as its first message. Archiving a parent asks
  whether its children go too (`--con-hijos`). `telar hilos --json` gives each thread its `padre`.

- **A message wakes an archived or sleeping thread.** It used to wait in the bus until someone resumed the thread by
  hand. Now a message that asks for something (not `--modo aviso`) resumes it, with its conversation, on the machine
  where it lives (bus verb `hilo-despertar`), and says so: «estaba archivado: lo retomé». Agents are left to their node.

- **Delete an agent, and bring it back.** `telar agentes eliminar faro` (in the page: ⋯ › eliminar el agente, or
  «eliminar» in the agents page) archives its threads, with their conversation, and moves its folder to
  `<agentes>/_eliminados/`, with what this machine's configuration had for it (`[agentes.<clave>]`). Nothing is
  deleted: `telar agentes eliminados` lists them and `telar agentes restaurar faro` (or «traer de vuelta») brings one
  back. It runs on the machine where the agent lives, over the bus (`POST /agentes/eliminar`).
- **Open an agent from the page** (`POST /agentes/abrir`, on its machine): an agent with no thread opens with a click
  (▶ in its row), resuming its conversation. With no engine chosen (`[agente] nombre`) it says so and offers Claude
  Code; ⚙ agente › motor chooses it (`PUT /config/motor`). If its tab was left with a bare shell (opened before the
  engine was chosen), ⋯ › abrir el agente opens it there.

- **Riso glyphs, per mode and off by default.** A field of glyphs printed like a risograph on the dark background
  (each ink on its own layer, with grain, mixed by light) that changes scale by zones, and a glyph per thread computed
  from its name, with its state on top (working turns in 45° steps, waiting fills a ring of yellow dots, done gets a
  green dot, seen goes dim); a big one, the seal, heads an agent's ficha. A mode turns them on (`glifos = "si"`), picks
  a style (`estilo`), puts the glyphs in the sidebar (`iconos = "glifos"`) and places the field per screen (`campo =
  "ahora=banda, plan=fondo 0.15"`). A style (`[glifos.<estilo>]`, `GET|PUT|DELETE /glifos`) holds every parameter:
  inks, shape and motion of the field, its life, each piece's gesture, the thread glyph and its states. **⚙ glifos**
  changes all of it, the mode's part and the style's, with a live preview. Nothing fades: colours change at once and
  things appear by size, with a bounce. It animates only what shows, at 30 fps at most, stops with the tab hidden and
  holds still with reduced motion. The engine is in separate modules under `pagina/src/web/glifos/`.
- **`?abrir=<dirección>` opens something when the page loads** (`/?abrir=hilo:Faro`, `tarea:T84`), instead of
  the dashboard or, on a phone, the list: a thread on a phone opens in its conversation (with the box to write), and
  «◀ hilos» goes back to the list. A sleeping or archived thread is shown, not resumed. For a phone's home screen.

### Changed

- **Every icon is exactly two letters wide.** The icon font is monospaced, but its cell is 1 em, 1.66 letters of the
  page's Menlo: each icon pushed what followed off the grid. `scripts/iconos.py` now gives every glyph the advance of
  two page letters, centred, so text after an icon stays in its column anywhere. A child thread's arrow comes from the
  icon font too, like an agent's children («G ↳ T458»).

- **The page's symbols are icons now.** What was drawn with Unicode symbols (⋯ menus, ✓ done, ↻ reload, ▶ run,
  ⏸ pause, ✎ edit, ★ star, ↗ open outside, ▾▸ fold, ↕ sort, ● ○ ◐ states and priorities, ⇄ elsewhere, ◇ organizer,
  the search's kinds, ◀ back…) uses the icon font, the same everywhere. Native tooltips keep the plain symbols (the
  browser draws them, without the page's letter), and so do the key symbols (⌥ ⇧ ⌘ ⏎ ⎋) and text arrows.

- **The conversation view, redone for the phone.** Room on the sides (and a reading column on a wide screen); one
  letter size everywhere, secondary things only dimmed. The box to write is a real field (square, thin border, blue
  while writing) with a send button beside it that lights up when there's something to send, and grows up to eight
  lines. The keys above (⏎ ⎋ 1 2 3 ↑ ↓) are plain and dim, with what each does on hover. **Sending says how it goes**:
  what you sent shows at the end, dimmed, until it appears in the conversation, and the line below says «enviando…»,
  «llegó», «en su casilla» or why it didn't go (the text stays in the box).

### Fixed

- **Windows that look at a thread on another machine over mosh close right away no more.** mosh hands the server this
  machine's `LANG`/`LC_*`, and macOS's bare `LC_CTYPE=UTF-8` isn't a locale on Linux: `mosh-server` refused to start
  («needs a UTF-8 native locale»), the window closed as it opened and the node reopened it every vuelta. The command
  now sets `LC_ALL=C.UTF-8`, which both sides have. It showed up when tmux was restarted from a shell with that
  variable.
- **A thread from another machine whose window here is being reopened waits for it.** Opening it in the page while
  its window was down said «no tiene ventana abierta en esta máquina: retómalo primero» and stopped there; now it
  says it's waiting and connects as soon as the node brings the window back.

- **Archiving the thread you're looking at isn't an error.** When its window goes away because it was archived or
  closed (also from inside: «archívate»), the page moves to its conversation, with «retomar», instead of «no se pudo
  abrir».

- **The node notices a configuration change** instead of keeping the one it started with: choosing the engine with the
  node running opens the agents that are there for good right away, and replaces a tab of theirs that was only a shell.

- **A number with decimals can be written to the configuration** (`escribir_clave`): it only took text, integers and
  lists.
- **Trading `?k=` for the cookie keeps the rest of the address**: it used to redirect to the bare path.
- **In the conversation view, what came over the bus isn't «tú».** The line the node types to let a message in
  («↯ mensaje nuevo · mensaje de Mobile: …») is labelled with who sent it («↯ Mobile»), in violet; only what the
  person wrote is «tú».

## [0.10.0] — 2026-10-30

### Added

- **Tags on threads, and modes that filter by them.** `telar hilo etiquetas "trabajo, cliente"` (`ninguna` clears
  them; in the page, ⋯ → etiquetas…) tags a thread; a thread on another machine is tagged by its owner, over the bus,
  like archiving. A mode can show only the threads with some of its tags (`etiquetas = "trabajo"`) and hide or keep
  the untagged ones (`sin_etiqueta`): a work mode and a personal one, say. It filters HILOS, custom sections and
  ARCHIVO; agents, the dashboard and apps always show, and the thread you're looking at never hides. `telar hilos
  --json` gives each thread its `etiquetas`.

### Changed

- **A provider's tab without its count.** A feed's tab («leer») is just its name, like «tareas»: how many items a
  feed has isn't something to do.
- **The page header, lighter.** No «dashboard» link (the dashboard is a group of the sidebar). On the right, machines
  and settings are two icons from the icon font, next to the mode. The version that runs sits by the logo, on the
  left, without «telar» before it, and a new version's notice (its icon and number) goes right after it.
- **The mode is an icon too**, and a click opens the list of modes right under it (the one in use checked, and
  «editar los modos…»). With a tag filter on, the icon turns violet.

## [0.9.5] — 2026-10-30

### Changed

- **The bar above a thread, only icons.** Each view (terminal, lectura, conversación) is just its icon from the page's
  icon font, in a 2ch column like the sidebar rows; its name and shortcut show on hover.
- **Version numbers follow SemVer for real.** While in 0.y.z, anything new or breaking bumps y and only fixes and
  cosmetic changes bump z (docs/publicar.md, «Qué número le toca»). 0.9.1 to 0.9.4 brought features as patches;
  they stay as published.

## [0.9.4] — 2026-10-30

### Added

- **`/relevo [tema nuevo]`: clear a conversation without losing the thread.** A skill telar installs (`telar agente
  instalar`): the agent writes the thread's handoff (`HANDOFF.md` in its folder; without a folder, in telar's state),
  moves what must last to its README or CLAUDE.md, and runs `telar hilo relevo "<tema>"`. When that turn ends the
  node types `/clear`, and in the new conversation, that it read the handoff and go on with the topic. It's the
  residents' rotation with a handoff, opened to any thread on demand (`telar.rotacion.pedir_handoff`).
- **After starting or a `/clear`, a thread is told to read its folder's CLAUDE.md and HANDOFF.md** (Claude starts in
  the root, so a project folder's CLAUDE.md wasn't read until a file there was touched), and that `/relevo` exists.

### Changed

- **The thread header shows its folder as a path** (with its icon; a click still opens it), instead of «carpeta».
- **Children sit under their parent in HILOS**, indented, whatever the order chosen: a thread opened by another
  (`abierto_por`) no longer lands far from it because it was born with priority 0. The order applies among the top
  ones and among siblings.

## [0.9.3] — 2026-10-30

### Changed

- **A thread closed on another machine leaves the sidebar in seconds, not a minute.** The node publishes its foto
  (the list of its threads) as soon as which threads exist or are alive changes, not only every 30 s; and the page
  reads the fotos every 6 s (it reads a local file the node keeps) instead of every 30, and every 2 s right after a
  close or an archive until the thread is gone.
- **«cerrando…» while it goes.** From the click until the thread is really gone (here and in its machine's foto, at
  most 90 s), its row shows the name dimmed and «cerrando» (or «archivando») with dots appearing, and no buttons.

## [0.9.2] — 2026-10-30

### Added

- **Child threads of an agent.** A task with no project taken to Claude no longer queues in the agent's one thread
  (where they all mixed): it opens its own, «Agenda › T454 Revisar el contrato», in the agent's folder (its
  instructions and memory), with a fresh conversation, on the machine where the agent lives (over the bus, verb
  `hilo-hijo`). If that task already has a live child, it writes there. In the sidebar the children hang from their
  agent, named without its prefix (↳ T454 …), from this machine or the agent's; they no longer repeat in HILOS. Picking
  an agent by hand in «Acción…» still hands it the task in its own thread.

- **Merge two tasks that are the same.** «es la misma que…» in foco (pick the one that stays), «unir» in a task's
  menu, or `telar tipo tarea unir T461 --params '{"con": "T467"}'`. The one that stays gets the other's text (under
  «De T461»), its project and size if it had none, a line in its history and an `absorbe` connection; the other is
  discarded saying where it went. It's built from each task's own actions, so it works against an older telar where
  the tasks are written.
- **«ver el detalle» in foco**, the first action of the chosen task: its full ficha (context, history, every action),
  and «‹ foco» (or ⎋) comes back with the same task chosen.
- **Quick postpones next to «nueva fecha» in foco**, one above the other: one day more (from its date if it's ahead,
  otherwise from today), this week's Friday (next week's if it's already Friday or the weekend) and next Monday, each
  with its day. They replace the separate «mañana» of an overdue task; «va hoy» stays.

## [0.9.1] — 2026-10-30

### Changed

- **«foco» lives inside «tareas»**, as its first sub-tab: «tareas» (`v`) opens in foco, and the whole list is the
  second sub-tab, «lista». A section can have its own built-in sub-tabs before the ones modules add (`SUBPESTANAS`).
- **In foco, a click on a card shows its actions on the right**, the ones that fit that task: an overdue one gets
  «va hoy» and «mañana» first; one with no size, «es rápida» and «es larga». The first card comes chosen, and the next
  one is chosen when a card leaves. Dragging still works.
- **In foco, «con Claude» no longer makes you wait.** Finding the task's thread and opening or resuming it takes
  seconds (on the server, by ssh), so the card leaves at once, foco goes on with the next one, and the status line
  says when Claude has it (or the card comes back if it couldn't). While any other action runs, it says what it's
  doing and the actions can't be pressed again.
- **Taking a task to its thread skips looking it up** when the caller already has its row (`POST /pendiente/llevar`
  takes `fila`, the one from `telar pendientes`; foco sends it): about 2 s less, the time it took to ask for the
  provider's tasks, sometimes over the bus. A row that isn't that task's is ignored and it's looked up as before.

### Fixed

- **Foco follows changes made elsewhere.** It now repaints with every read of the day (each minute, and when something
  changed), so a task an agent closed leaves by itself; before it stayed until foco was reopened. A ↻ in its header
  reads the tasks again right away.

## [0.9.0] — 2026-10-29

### Added

- **«foco», a dashboard tab to decide tasks one by one** (`f`). Up to five of your own tasks as cards, and boxes on the
  right to drop them on (or click the card, then the box): done, new date (with «hoy» for an overdue one), someone
  else's, with Claude, discard. A card leaves and the next comes in. Overdue ones go first: they get a real date or
  they go. Two modes: **gestión** (quick tasks, up to five) and **concentración** (long ones, two at most), whose boxes
  are start now, block time (Claude finds a 2 to 3 hour slot in your calendar), take out the first step (a quick task
  for today that starts it), plus the usual ones.
- **A task's size** (`tamaño: rapida | larga` in its file, `editar tamano=…`, the ficha's «tamaño…» with role
  `tamano`): quick is half an hour or less, long is hours or days. A task with no size goes to gestión, with
  «¿rápida o larga?» on its card. «descartar» in the ficha now has the role `descartar`.

### Changed

- **Archive or discard a thread.** In the sidebar and its menu a thread has two ways out, with their own icons and
  tooltips: *archivar* keeps it in ARCHIVO with its conversation, to take it back later; *descartar* (a trash can,
  formerly «cerrar» ✕) ends it and drops it from the list. An archived or asleep thread has the trash can too, next to
  «retomar»: after asking, it leaves the archive (what «olvidar» was). The CLI verbs don't change (`telar hilo cerrar`, `olvidar`). (The archive button used to be a ⏸, which read as
  «pause».) While the order runs (by the bus, for a
  thread on another machine) the row shows it with a spinning icon, and says when it's done.
- **The sidebar row, on the icon font.** Priority, attention, where it lives and «busy» are icons from the page's
  icon font, each in a 2ch column (an icon is 1.7 letters wide: in 1ch it ran over the name). The names start in
  the same column on every row. The busy icon no longer spins (it wobbled off center): it cycles colours.
- **An archived or closed thread opens in its conversation**, read-only, with «retomar» instead of the message box:
  clicking it in the sidebar no longer starts the agent. Without a saved conversation it says so plainly.

### Fixed

- **Closing the thread you're looking at leaves its view**: archived, you see its conversation; closed, the
  dashboard. Its terminal is closed too, instead of staying behind trying to reconnect to a window that's gone.
- **Closing a thread that lives on another machine is faster and sure.** Once its owner closed it over the bus, the
  window here closes right away and no longer asks the other machine again by ssh; before, it waited for the node to
  notice, and if that notice was lost the row stayed. The page waits up to 75 s for an order that goes by the bus.

### Added

- **Products and their idea backlog** (`telar productos`, `GET /productos`, docs/propuestas/productos.md). A
  repository declares in `.telar/productos.yaml` which units of its profile are products (what it sells) and what
  its ideas look like. Each idea is a markdown file with frontmatter in its product's folder (`backlog/I03.md`),
  written with a version and a lock, touching only the lines that change plus a line in its history (the new
  `telar.tipos.registro` format). `telar productos crear|cambiar|ver`, and the lienzo order `idea` for a module.
  The module `telar-productos` draws the list, the backlog and a kanban board.
- **Tasks and ideas move between each other.** A task that is really an idea goes to a product's backlog from its
  menu («al_backlog», picking the product) or `telar productos desde-tarea`: the idea is born with its text, its owner
  as `responsable` and the task's history, and the task is discarded saying where it went (both or neither). An idea opens operational tasks (`telar productos
  tarea`, its menu, or the module), which it shows while open. Ideas are objects (`idea:<producto>/I03`), and an
  action of `telar objeto` can bring `opciones` so the page offers a list instead of a text box.

## [0.8.9] — 2026-10-29

### Fixed

- **A thread can come back to the machine it left.** Bringing a thread back (from the server to the laptop where it
  started) was refused: «aquí ya está esa conversación… el hilo ya llegó antes». That copy is the one left behind
  when it went away. Now the check before moving doesn't count it, and on arrival the conversation that comes
  replaces it when it continues it. If the local one was continued separately, it's kept aside
  (`<id>.antes-<fecha>.jsonl.bak`) and the move says so.

### Changed

- **A mail opens to the right of the list.** Clicking an item of a block (a mail) shows it beside the list instead of
  replacing it: the list stays in view with the open one marked, another click switches it, and ✕ or ⎋ closes it.
  On a narrow screen it still opens alone.
- **A search box for the mail.** A block with many rows (the inbox) gets a search box on its own line under the
  title: it filters by sender, subject, task code or the item's new `busca` field (text that isn't shown: the names
  and addresses of who sent and received a mail) as you type (every word must match; a folded conversation matches by any of its
  mails), says how many are left, and survives opening a mail. `/` focuses it, ⎋ clears it.

## [0.8.8] — 2026-10-29

### Fixed

- **A thread moved to a machine in `[remotos]` showed twice in the list.** The window there was born, the node here
  heard of it on the bus and brought its window, and then the move opened another one. Now the move takes the same
  lock and uses the window if it's already there. That path also reports its steps to the page's panel now.
- **A thread's terminal that can't open says so once, instead of blinking.** When `telar mirar` fails (the thread no
  longer exists here, it has no window…), the server closes the connection with code 4001 and the reason, also
  through another machine and the door. The page stops reconnecting and shows a box with the reason and two
  buttons, «reintentar» and «retomar». Before, the error was printed, wiped and printed again every second. An
  older telar that doesn't send the code is detected by two closes in a row right after opening.

## [0.8.7] — 2026-10-29

### Changed

- **Moving a thread to another machine is shown as it happens.** The page opens a panel with the machine's name in
  big letters, a loading bar and the steps (check there, close here, copy the conversation, open there, done); the
  thread's row shows it's travelling. What would make it arrive half-done (its folder not cloned there) is asked in
  the panel; a failure says why there instead of a terminal error. `window.telar.ensayoMudanza()` plays it without
  moving anything.
- **Before closing anything, the other machine is asked whether it can receive the thread** (bus verb
  `hilo-revisar`): no Claude agent, no `claude` on the service's PATH, a thread with that name already open, or the
  conversation already there stop the move with nothing moved.
- **If the thread doesn't open there, it reopens here** with its conversation; it's archived here only once it
  arrived. Progress is in `<estado>/llevar/<hilo>.json` and `GET /mudanza`.
- **One row per thread in the sidebar**: a thread that now lives on another machine no longer shows again in this
  one's ARCHIVO, and one open on both machines is flagged (two conversations that drift apart).

## [0.8.6] — 2026-10-29

### Fixed

- **The service's PATH always has `~/.local/bin`** (where uv and the Claude Code installer put their programs) and the
  folder of the running telar. `telar instalar` run over ssh, without the `.profile`, wrote a PATH without them, and
  the service couldn't find `claude`: a thread moved to that machine arrived but didn't open («no pude abrir el
  hilo»). It happened on a hosted telar.

## [0.8.5] — 2026-10-29

### Fixed

- **`telar instalar` declares the agent of each thread** (`[agente] nombre = "claude-code"`) when Claude Code is
  installed and the configuration names none. Without it, a thread opened a plain shell and a thread moved to that
  machine was refused («aquí el agente es «ninguno»: solo se retoma una de Claude»): it happened on a hosted telar,
  set up with `telar instalar`. An agent already declared is left as it is; `--sin-agente` skips it.

## [0.8.4] — 2026-10-29

### Fixed

- **The terminal of a thread hosted behind a server's door, opened from the person's laptop.** The door passed a
  terminal's WebSocket on with its origin but without its `Authorization`, so the laptop's page (which forwards the
  terminal with the bus key, not as a browser) was refused by the hosted telar: «no pude abrir la terminal en
  telar: InvalidStatus». The door now passes the bus key along, and the hosted telar checks it as without a door.
  The door has to be reinstalled (`servidor/telar-puerta-instalar --version 0.8.4`).

## [0.8.3] — 2026-10-28

### Added

- **«Acción…» and `telar actuar`** (`POST /actuar`, docs/propuestas/acciones.md): at the top of every entity's menu,
  a panel to ask a thread or an agent something about it. It shows the entity's context (from `telar objeto`), a box
  for what you want, an optional skill (searchable, the destination's skills, most used first) and the destination
  (the entity's own thread, already chosen, which opens with the prompt if it isn't open; the resident agents; the
  threads). ⌘⏎ sends one line: the skill, the request, and the context with the entity's address. An agent gets it
  as a task; a local thread in its input (or left written, unsent); a thread on another machine by the bus.
  `GET /skills?carpeta=` lists the skills of a new thread in a folder. The panel opens at once from what the page
  already has (threads and agents); the entity's context and the destination's skills arrive after, and are kept a
  few minutes so opening it again is instant. A click outside closes it.

### Changed

- **One menu for every entity, where you click** (`web/entidades.ts`, docs/propuestas/acciones.md): right-click a
  thread in the sidebar, a project in «proyectos», a task or a checkbox, or press its ⋯, and its menu opens next to
  the pointer (↑ ↓ ⏎ ⎋, type to filter), not as a box in the middle of the screen. Each page registers what it can
  do with a type of entity; a type the page doesn't know (a module's) gets the actions the server gives
  (`telar objeto`); every menu ends with «copiar su dirección». While a menu is open the dashboard's letter
  shortcuts stay off. A module's page opens an entity's menu at its click point with
  `window.lienzo.pedir("menu", {direccion, x, y})`, with no permission asked (it only shows).
- **Icons in the page** (`web/iconos.ts`, `media/css/iconos.css`): Codicons from Nerd Fonts, cut down to the ones
  used (`pagina/scripts/iconos.py`, about 3 KB) and loaded as the page font's fallback. Menu actions carry an icon
  and a color for what they do (go/look blue, change yellow, agent violet, done green, remove red), all at the same
  font size: separators and descriptions are no longer smaller.

## [0.8.2] — 2026-10-28

### Fixed

- **`telar instalar` run again keeps how the page is served.** Without `--web-socket`, `--web-url` or `--web-puerto`, it
  keeps the ones the service already had. Before, it rewrote the service with `--web`: a telar hosted behind a
  server's door then tried to listen on the owner's port and restarted in a loop.
- **The terminal of a thread on another machine** says what is wrong when that machine gives no page: its `telar
  serve` isn't running there (or runs without a page), and where to look.
- **`telar modulos publicar`** writes the full telar version as the minimum (`>=0.8.1`, not `>=0.8`).

## [0.8.1] — 2026-10-28

### Added

- **Dates** (`telar fechas`, `GET /fechas`, `telar.fechas`; docs/contratos.md and docs/propuestas/fechas.md): anything
  with a day (activities, milestones, sessions), in one format, from wherever it lives. Each unit's `## Cronograma`
  table is read by column name with nothing to declare; providers with `como = "fechas"` add other documents
  (`markdown`, with `rutas`) or a program that prints dates (`comando`). Rows that look like a date and can't be
  read are reported with file and line; a source that fails is reported and the rest still arrives.
- **Date maps** (`.telar/fechas.yaml`, `telar.mapas`, docs/perfil.md): read a schedule that doesn't have the default
  shape. A map says which sections are schedules and where each field comes from: a column (with a Unicode date
  pattern such as `EEE d-MMM`, a language, a range separator, the year when the cell has none, its own vocabulary),
  a template over columns, or a constant; `buscar` finds the project by a frontmatter key. A document can name its
  map in its frontmatter (`fechas: <map>`). In a shared document, a row belongs to the unit its link points to.
  `telar fechas probar <file>` shows which rows were read and which were skipped, and why.
- **Dates from modules and tasks**: a module brings a dates source in its `modulo.toml` (`[fechas] comando`, run in
  its folder), and tasks with a due date from the task providers join the stream as `clase: "tarea"`.
- **Editing dates where they live** (`telar fecha <id> --inicio/--fin`, `POST /fecha`): a schedule row changes only
  its date cells, in their own shape (the map's pattern, or the cell's), gets an id comment the first time
  (`<!-- id: f-… -->`) and is found by it afterwards; a task moves with its provider's date action; a program's date
  with its source's `escribir`. `--version` refuses a change over someone else's (409). Each date says what can be
  written (`editable`).
- **A module's page can ask telar to act** (`window.lienzo.pedir(orden, datos)`, `POST /lienzo/pedir`): only orders
  the module declared in `[permisos] ordenes` and the person granted. The page asks the first time (always, just
  this once, no); grants live in telar (`telar.concesiones`, `GET/POST /permisos`) and are listed and revoked with
  `telar modulos permisos`. The first order is `fecha`.
- **The date class `plazo`**: a project's own span, its bar in a Gantt.
- **Unicode date patterns** (`telar.patrones`): read and write a date with an LDML pattern, both ways (the weekday
  is recalculated when writing). Month and day names for Spanish and English are built in; other languages with
  Babel installed.

## [0.8.0] — 2026-10-28

### Added

- **Sub-tabs** (`[bloques.x] dentro`, a module's `[pestana] dentro`, or a view with `aparece = "pestana"`): a block
  can live inside one of the fixed dashboard tabs (ahora, tareas, proyectos, plan, calendario) instead of being a
  tab of its own. That tab gets a row with its name and each sub-tab's («proyectos · gantt»); the sidebar keeps
  marking the fixed tab, and the sub-tab's command runs only when it is opened, not every five minutes. `en` and
  `dentro` don't go together. A module that uses `dentro` needs this version: an older telar refuses the key.
- **Fonts in a lienzo**: its content policy allows `font-src data:`, so a lienzo can carry its own font inline (an
  icon font cut down to the glyphs it uses, a couple of KB). Still no network.
- **Proposal: dates** (docs/propuestas/fechas.md): one format for anything with a day, sources that are documents
  read through declarative maps (Unicode date patterns) or commands, gathered in `telar fechas`, and edited where
  they live (dragging a bar in a Gantt writes the cell it came from).

## [0.7.9] — 2026-10-27

### Added

- **The search bar** (⌘K, Ctrl+K outside the Mac; `web/buscador.ts`): a window over everything, like Spotlight,
  to go anywhere by typing part of its name. It filters as you type, ranked by how well each result matches (the
  name counts more than the detail, the start more than the middle; letters in order also match), grouped by
  source: threads (live, archived and those of your other machines), agents, the dashboard (its tabs and the ⚙
  sections), modes and a few commands (new thread, new agent, machines). ↑↓, ⏎ and ⎋; it works in «foco», where
  there is no sidebar or header. What it searches comes from sources registered from outside, so adding tasks,
  projects or documents is registering another source. Each kind has its color (threads blue, agents violet, the
  dashboard cyan, modes yellow, commands green). Behind it, the page darkens under a faint `░` texture, like a
  text-mode window's shadow; the box sits on that texture's grid (the page font's cell), so its edges never cut a
  cell in half.

## [0.7.8] — 2026-10-27

### Added

- **Modes for the page** (`telar.modos`, `[modos.<n>]`, docs/propuestas/modos.md): a mode is a name with values for
  a fixed catalog of settings: the threads sidebar (open, folded, hidden), an agent's card, the header, the thread's
  action bar, the box under the terminal, full screen, the terminal's width, position and background, and which
  notices show. Two come built in: «estándar» (as before) and «foco» (only the terminal, centered, nothing around
  it; a ◧ at the top right goes back). Switch with «◧» in the header, ⌥⇧F (foco and back), ⌥⇧M (the next one) or
  ⚙ modos. Which mode is on, and changes made by hand while in it (folding the sidebar, another background), belong
  to the browser; «guardar en este modo» writes them into the config, and «nuevo modo…» saves what's on screen
  under a new name. `GET /modos`, `PUT /modos/{clave}`, `DELETE /modos/{clave}`. Folding the sidebar or the card is
  now a change in the current mode (the old per-browser keys are carried over once). The roadmap for the rest
  (font and theme, sidebar sections, automatic modes by device or trigger, a thread's mode, modules bringing
  modes) is in that proposal.

### Changed

- The box under a thread's terminal («escríbele al hilo») is hidden by default, in «estándar» and «foco»: one
  writes in the terminal itself. On a phone it stays, since typing into the terminal doesn't work well there.
- The terminal draws its gray edge line only on the sides where there is background between it and what's next
  to it: centered, on both; against the sidebar or an agent's card, which bring their own line, not.

### Fixed

- The terminal re-measures itself, and tells tmux its size again, when the window changes size (Chrome's bar
  appearing), when the tab becomes visible, on entering or leaving full screen, and after a mode switch once the
  layout settles; before, it relied only on its box's ResizeObserver, which sometimes didn't fire.

- The page: the left sidebar folds, like an agent's card on the right: «‹» at the end of its first header leaves a
  narrow strip with «›» and «hilos» written vertically, and a click on the strip opens it again. It stays as you left
  it (per browser). Not on a phone, where the sidebar is its own screen.

- How a thread's terminal looks is configurable (`[terminal]`, and ⚙ terminal in the page): its maximum width in
  columns (`columnas`, 40–400, or 0 for the full width; it was 130 fixed, or a `localStorage` key), its position
  when there is room (`posicion`: izquierda, centro, derecha; it was always centered) and its background (`fondo`:
  the faint loom as before, none, a color, an image from this machine or a URL, or a module). Changes apply at once
  to the open terminals.
- A module can be a terminal background: `[fondo] archivo = "fondo.html"` in its `modulo.toml`. Its page is drawn
  behind the terminal in a sandboxed iframe (no access to the page or the API, no clicks); its files are served
  from `/api/terminal/fondo/…`. `GET /terminal/fondos`, `PUT /config/terminal/{clave}`, `GET /terminal/imagen`.

## [0.7.7] — 2026-10-27

### Fixed

- Receiving a thread over the bus refused to resume it («aquí el agente es «claude-code»: solo se retoma una de
  Claude»): it compared the agent's name with «claude», but the registered name is `claude-code`
  (`telar.agente.claude_code.NOMBRE`).

## [0.7.6] — 2026-10-27

### Added

- «traer a esta máquina»: from the page of the machine you want it on, a thread that lives on another machine of
  yours (a `[remotos]` one, or one seen on the bus, which now has a ⋯ menu) is brought here. Its owner runs `telar
  hilo llevar` toward the machine asking (node verb `hilo-traer`, `POST /hilo/traer`); if there was a window here
  only watching it, it's closed. With unpushed work over there, it asks first, as when sending.

### Fixed

- A thread sent to a machine whose tmux session isn't up (a new place on a server nobody opened yet) failed with
  «aquí la sesión no está viva»; now the session is raised empty and the thread is its first.

## [0.7.5] — 2026-10-27

### Added

- ⚙ servidor: each hosted person's telar version, and «actualizar a X» when it is behind the server's. The root
  helper installs that exact version as the person, from its git tag (PyPI takes a few minutes to offer a fresh
  release), and restarts their service without rewriting it (it keeps the door socket and address); their threads
  keep running in their tmux. It runs in the background (`actualizando`) and records the resulting `version`, or the
  error. The helper also reports the version when it creates a place. `POST /alojamiento/actualizar`.

## [0.7.4] — 2026-10-27

### Fixed

- `telar hilo llevar` (and «llevar a otra máquina») with a thread that has no messages yet: Claude writes the
  conversation only after the first one, so there was nothing on disk and it refused («no encuentro en disco
  ninguna de sus conversaciones»). Now it closes here and opens there with a new conversation, by ssh and over the
  bus. A conversation named with `--sesion` that doesn't exist is still an error.

## [0.7.3] — 2026-10-27

### Added

- ⚙ servidor (for whoever administers the server): each hosted person with their memory and CPU caps, and the caps
  new places start with; «cambiar» changes them. A hosted person's new caps apply at once (the root helper rewrites
  their slice and runs `systemctl set-property --runtime`), without restarting anything of theirs. Also `telar
  servidor topes [PERSONA] --memoria 4G --cpu 200%`, `GET /alojamiento` and `POST /alojamiento/topes`.
- «máquinas»: **add a server by its address** (its Tailscale IP, its name or its `https://…`). telar asks it who it
  is (`GET /unirse/servidor`, open only from Tailscale, on the bus machine: name, bus, owner, whether it hosts
  people) and keeps it in `~/.config/telar/servidores.json`; «pedir entrar» runs `telar instalar --servidor
  DIRECCION`, which is `--unirse` with the team taken from the server instead of a repo's `equipo.yaml`. The list
  shows each one's state: not asked, asking, pending approval, rejected, in its bus, on another bus. Also `telar
  servidor agregar|agregados`. The door lets `/unirse` through to the owner's telar for people it doesn't know
  yet, so the address can be the door's.
- **Move a thread to another machine of yours over the bus** (`telar.mudanza`): `telar hilo llevar <hilo>
  <máquina>` (and «llevar a otra máquina» in the page) now also takes your machines on the bus, like your place on
  a server, not only `[remotos]` over ssh. The conversation travels compressed (up to 25 MB) and the other machine
  opens the thread resuming it (node verb `hilo-llegar`); here it stays archived. Files don't travel: without the
  thread's folder there, it opens in the root and says so.

## [0.7.2] — 2026-10-26

### Added

- The page tells whoever administers the server's door when it falls behind telar (`↑ puerta X` at the top); a
  click copies the command that updates it. The door is updated by hand, as root, so the page only says how.
  `GET /version` carries it as `puerta` (`telar.puerta.estado`, which reads the version from its venv without
  running it).
- `telar doctor` on a server that hosts people: the root helper and its mailbox, the door (its service, its
  version, and that the owner's telar listens for it) and, for each active hosted person, that the registry has
  their Tailscale account and their socket folder exists.

## [0.7.1] — 2026-10-26

### Fixed

- The page: the HILOS sort now covers the threads of other machines too (the ones that come from their snapshot).
  They were added after the sorted list, so on the server's page the laptop's threads ignored the sort. With the
  priority sort, priority goes first for all of them, live or not, from this machine or another.

## [0.7.0] — 2026-10-26

### Added

- **The door** (`telar.puerta`, `telar puerta servir|tabla|quien`): on a server that hosts several people, everyone
  enters through the server's address (`https://<machine>.<tailnet>.ts.net`), like a normal web server. Tailscale
  says whose device each request comes from (`tailscale whois` of the address `tailscale serve` puts in
  `X-Forwarded-For`, which it overwrites), and the door passes it, HTTP and terminal WebSockets, to that person's
  own `telar serve` over `/run/telar/<user>/web.sock`. No port per person, no page key, no path prefix. Requests
  from the server itself are refused (they would look like the owner's). It runs as the system user
  `telar-puerta`; `servidor/telar-puerta-instalar` sets it up (`/opt/telar-puerta`, `/etc/telar/puerta.toml`,
  tmpfiles, `telar-puerta.service`).
- `telar serve --web-socket PATH [--web-url URL]`: the page also on a socket for the door, without the key (the
  socket's folder, 2750 with the `telar-puerta` group, is what protects it). With `--web-url` the page goes only
  through the door and the node publishes that address. `telar instalar` takes the same two flags.

### Changed

- Hosting with the door installed: approving a place assigns no port. The root helper creates the person's folder
  in `/run/telar` and records their Tailscale account (from their `telar instalar --unirse` request) in
  `/etc/telar/alojados.d/`, which is how the door recognizes them. Without the door, it works as before.
- The `serve` extra now includes `httpx` (the door's client) and needs `websockets>=13`.

## [0.6.3] — 2026-10-26

### Added

- The page: the tasks table shows each task's priority in its own column, with the threads' icons (● P1, ◐ P2,
  ○ P3; P0, urgent, a red ●). A click lowers it one level (● → ◐ → ○ → ●); P0 is set from ⋯. The ● header sorts
  by priority alone. Task rows carry `prioridad` (0–3, or null), from the task's own P0–P3. In-progress tasks now
  show their code in blue, where that column used to show a blue ●.

### Changed

- The page: the tasks table's default order is priority first, with the date only breaking ties (overdue first,
  undated last within each priority). Before, it sorted by date alone. A row without priority, like a bullet in a
  document, counts as P2. What an agent left ready to decide still goes on top.

## [0.6.2] — 2026-10-26

### Added

- `telar agentes nuevo "Faro" [--para "…"] [--icono ☼]` and `POST /agentes/nuevo`: a resident agent's folder
  (`CLAUDE.md` with a starting template, `agente.toml`, `README.md`, `bitacora.md`, `memoria/MEMORY.md`). If
  `[agentes] carpeta` is missing it is written: `agentes` in the root, or `~/agentes` when the root is a team
  repository (`.telar/equipo.yaml`), so a person's agents don't land in the shared repo.

### Changed

- The page: the AGENTES section is always in the sidebar, with **+ nuevo**. Without agents it says so and offers
  to create one; before, it was hidden until `[agentes] carpeta` existed, so nobody learned agents existed.
- ⚙ módulos is one page instead of two tabs: first the modules from the catalogs you don't have (with search
  when there are more than four), then the installed ones. With tabs, the available ones went unseen.

## [0.6.1] — 2026-10-26

### Added

- The page: drag a file onto a thread's terminal and its path lands in the chat, like VS Code's terminal: at the
  cursor if dropped on the box below, pasted without ⏎ if dropped on the terminal (quoted when it has spaces). If
  the drag carries the path (VS Code, a terminal, Safari from the Finder) it is used as is; if it carries only the
  file (Chrome from the Finder, Windows), the page asks before uploading it. The browser no longer navigates to a
  dropped file.
- `POST /archivos/entrada`: a file for a thread, in the inbox folder of the thread's machine. Uploaded
  (multipart) or named by its path on this machine; for a thread on another machine it goes by the bus
  (`telar archivo`, up to 25 MB, to any machine of the person), or over ssh with `telar imagen`'s `subir` for a
  `[remotos]` machine without bus or a bigger file. `subir` no longer overwrites a file with the same name (`-2`,
  `-3`…). Up to 200 MB. The
  `serve` extra now includes `python-multipart`. (Pablo Ferreiro, PR #3)

### Changed

- Sections of type `lista` are now a **fallback** for a thread's pending items, not an addition: they only feed
  `pendientes` when the profile declares no `pendientes` section. A profile that declares one has said where its
  tasks live, and its other lists (notes, a schedule, links) are not tasks. `casillas` sections still count
  everywhere. Before, every note of a deal whose profile listed `notas` as a `lista` showed up among its pending
  items, and a click on one pasted it into the thread. (Pablo Ferreiro, PR #1)

### Fixed

- The server as a mainframe, setting up a place: `useradd` rejected the user's comment (it had a `:`); the person's
  telar was installed from `/` and took it as its root, walking the whole disk; with their home as root, `telar
  doctor` failed because telar's state was inside it. Their root is now `~/trabajo`. A place that failed halfway is
  resumed when approved again (the user carries telar's comment), and the ssh key is not added twice.

- Reopening a remote thread's window no longer opens it several times. When a laptop woke up, the node and the
  page's poll reopened the same thread at once and each one saw «no window» before the other created it: six
  identical windows in five seconds. `remoto.traer` now checks and creates under the state's lock, and counts a
  live window with that name that already runs a mosh/ssh as open. The remote mark goes to the window that was just
  created, by its id, not to the first one with that name. (Pablo Ferreiro, PR #2)

## [0.6.0] — 2026-10-26

### Added

- The module catalog: a file with a fixed name and format, `.telar/catalogo.toml`, in any repository: the official
  one (`nicorivas/telar-modulos`, «revisado»), a team's own (read from each repo of `[repos]`, «del equipo») and
  others in `[catalogos] fuentes` («sin revisar»). Each entry pins a tag or commit, so what installs is what was
  reviewed. `telar modulos catalogo [--buscar]`, `telar modulos instalar <name>` (from the catalog, in its
  version), `actualizar` to the catalog's new version. The format, in `docs/modulos.md`.
- Turn a module off without uninstalling it: `telar modulos activar|desactivar` (`activo = false` in
  `modulos.toml`): the configuration doesn't load it, so it brings nothing until it's turned on again.
- Writing and publishing a module: `telar modulos nuevo <name>` scaffolds one; `telar modulos revisar` says what it
  lacks to be published (`[permisos]`, a description, a name that doesn't clash with a telar command, commands that
  exist, a repository with an origin), and `--catalogo F --resolver` reviews a catalog by fetching each module at its
  version and comparing what it asks for; `telar modulos publicar --version vX.Y.Z` tags, pushes and opens the PR to
  the catalog with `gh`, showing the previous entry if there was one.
- The `/modulos` skill, installed by `telar agente instalar` next to `/hilos`: the judgment for writing, testing,
  publishing and maintaining a module (what to ask for, naming, versions). `telar instalar` adds a skill that's new
  or changed.
- ⚙ módulos in the page: installed (what each brings, its folder, its origin with repository, version and catalog,
  what it asks for; turn on, off, update, remove) and available (search the catalogs and install from the official
  or the team's one; an unreviewed one shows the command to run). `GET /modulos`, `GET /modulos/catalogo`,
  `POST /modulos/<action>`.

### Changed

- `telar modulos --json` gives, for each module, also `activo`, `ref`, `catalogo`, `confianza`, `a_mano`, `pide` and
  the turned-off ones.
- The API rereads the configuration when `modulos.toml` changes, not only `config.toml`.

### Added — the server as a mainframe, and the page

- The server as a mainframe: anyone already on the bus can ask for a place on the server (`telar servidor pedir`),
  whoever administers it approves (`telar servidor pedidos | aprobar | rechazar | quitar`), and the server sets up
  a Linux user with resource limits, its own telar, Claude Code and node on the person's own bus account, so their
  threads live there and show up on their other machines like any machine of theirs. The request goes to a new
  bus service, `alojar.<owner>`, exported to every account (`telar.alojamiento`). What needs root is done by
  `servidor/telar-alojar`, a root systemd service that watches a spool folder: the node never gets sudo. See
  `docs/arquitectura.md`, «El servidor como mainframe».
- The machines view (`/maquinas`) lists the mainframe servers of the bus with the state of your request and a
  «pedir un lugar» button; whoever administers approves, rejects or removes from the same view
  (`GET /alojamiento.json`, `POST /alojamiento/<action>`).
- `telar instalar --web-puerto N`: the page of a machine on a port other than 8780 (a server that hosts several
  people gives each their own).
- The dashboard calendar has two tabs, the day and the week (Monday to Friday; on a weekend, the week ahead). Both
  draw what each thing is: a meeting with other people is filled, a block the person reserved is hatched in the
  color of its class (strategic, commercial, mail, reserve, personal), lunch and travel are a thin line, a meeting
  not yet accepted is only its outline, one the person organizes carries a ◇ (they can move it), and what overlaps
  is marked: a block under an accepted meeting, two accepted meetings, two blocks reserved at once. What a thing is
  comes from the day's plan, or else from the event itself (guests or a call link make it a meeting). On top of the
  week, where its working day (08:30 to 18:00) goes: the hours of meetings, of each class of block and free, and the
  strategic blocks one by one, with what meetings and other blocks take from them. A click on an event opens its
  detail and notes next to it; on a narrow screen the week is a list by day. The tab key of the calendar (`a`)
  switches between the two, and the browser remembers the last one.

### Fixed

- Copying from the terminal of a thread on another machine. There the mouse belongs to that machine's tmux (or to
  Claude Code, which selects by itself and hands the text to tmux): what is selected by dragging stays over there,
  and comes back with OSC 52, which the page ignored. The page now writes it to the person's clipboard. On a page
  served over http the browser allows that only a few seconds after the click that started the drag, and a long
  selection plus the trip to the server can take longer: then a box asks, with a «Copiar» button (a new click, so it
  can), and meanwhile ⌘C in the terminal copies it too. It never answers a query for the clipboard. ⌥ and drag also
  selects in the page itself, even when tmux has the mouse.

### Changed

- `telar.personas.por_el_bus`: the request/response to a bus service, factored out of `personas.pedir` so the new
  service uses it too. Same behavior.

## [0.5.1] — 2026-10-24

### Added

- Who opened a thread: when another thread opens a new one (the command runs with `$TELAR_HILO`), or a periodic
  process does, telar notes it once (`abierto_por` in `telar hilos --json`: the thread or process, and its agent if
  it was an agent's). The sidebar marks it with the agent's icon, dimmed ("it started it", not "it's its"); the
  agents page lists what each agent opened, with a button to archive the live ones at once.

## [0.5.0] — 2026-10-23

### Added

- The whole agent in its `agente.toml`: `hilos`, `lugar` (where it lives; the machine's `en` still wins), `publico`
  (its threads public without publishing them one by one), `icono` (shown next to each of its threads) and a
  `[politica]` (`permite`, `pregunta`, `niega`: permission rules of the engine), passed to its session as
  `--settings` without touching anyone's settings.json. The machine's `[agentes.<folder>]` overrides what it needs.
- `residente` has three values: `siempre` (the node keeps it open: opens it at start and when it closes, and
  `max_vivos` never closes it), `a-pedido` (opened when something arrives: what `true` was) and `no` (what `false`
  was).
- Every errand is an Errand object: `telar encargar` (and a periodic process with `agente`) makes an
  `encargo:e-…`, with or without bus. It turns `corriendo` when its inbox delivers it, the agent is reminded once to
  close it if it ends a turn without doing so, and whoever asked can `cancelar` it (out of the inbox if it hadn't
  arrived; a message to stop if it was running).
- The agents page (≡ in AGENTES, in the sidebar): every agent with its icon, presence, whether it lives and what it
  does, its conversation's weight, its rotation and its errands (cancel the open ones), and buttons to hand it an
  errand, rotate it with a relay now and go to its thread. `GET /agentes`, `POST /agentes/rotar`. The right sidebar
  of an agent's thread gets its errands and the same buttons.
- An agent's thread starts knowing who it is (`para`), where its memory's index is and its last relay.
- Threads carry their agent (`agente`, `icono` in `telar hilos --json`), and the sidebar shows the icon; an agent's
  other threads go in HILOS with it.
- EQUIPO (formerly COLEGAS) lists every person connected to the bus, even without public threads.

### Changed

- ⚙ agentes is now ⚙ mensajes (it was always the bus's message log).

### Removed

- The errand queue (`<estado>/encargos/<agent>.jsonl`, `telar encargar --cola`): errands wait in the agent's inbox.

## [0.4.9] — 2026-10-23

### Added

- Rotating with a relay: when a resident agent's conversation passes `[agentes] rotar_mb`, at the end of a turn
  with its inbox empty telar asks it to write its relay (`<estado>/relevos/<agent>.md`: where it was, what's left,
  what the next conversation needs), then the node types `/clear` in its window and tells the new conversation to
  read it. Opened cold (an errand, `telar tejer`, `retomar`) with a conversation already past the limit, the new
  one starts by reading the last relay. Before, rotation happened only when an errand opened it, and cold.
- The page's right sidebar, when viewing an agent's thread: what it's for, model, whether it's resident, where it
  lives, its conversation's weight against the rotation limit, its last relay and its CLAUDE.md, readable; it
  folds and remembers. `GET /agentes/del-hilo`.
- A thread remembers which agent it belongs to (`de_agente.json`, written when telar opens it for one): renamed,
  it's still the agent's.

### Fixed

- `liberar` (the `[agente] max_vivos` limit) closes the passing threads first and every resident last, not only
  the one being opened: a periodic process no longer closes an agent to make room.
- The docs on agents: seven hooks (with `StopFailure`), and what telar does launch and type for residents.

## [0.4.8] — 2026-10-23

### Added

- A new version in the page's top bar («↑ 0.4.9»): a click installs it from PyPI (that exact version) and restarts
  the service, in a separate process, and the page reloads by itself when the new one answers. Only for an
  installation of `uv tool install`; one from the repository (editable) is told to `git pull`. ⚙ versión shows what
  runs, the latest one and when it was asked, with «buscar ahora» to ask PyPI without waiting (it's asked at most
  once an hour) and how the last update went. `GET /version`, `POST /actualizar`, `GET /actualizar`.

## [0.4.7] — 2026-10-23

### Changed

- Threads are private by default: the directory the other people of the bus see lists only the ones made public
  (`telar hilo publicar`, `privar`; in the page, ⋯ → hacer público, and ◇ marks a public one). A private thread
  receives no mail from other people, and is answered as if it didn't exist. On upgrading, every thread becomes
  private until its person publishes it.
- `/config` says whether there is a bus (`bus`), and the page uses that, not `[remotos]`, for what crosses machines
  and people: COLEGAS, ⚙ agentes and ⚙ personas no longer hide for someone who joined by `--unirse`.
- `telar instalar` restarts the service when the version it runs is not the one installed (after `uv tool install
  --force`, the service kept the old code).

## [0.4.6] — 2026-10-23

### Added

- COLEGAS in the page's sidebar: the threads the other people of the bus publish (name, whether it lives, its
  folder and a line; never its conversation), by person and machine, and a click on one to leave it a message in
  its inbox. `GET /directorio` and `POST /directorio/escribir`.

## [0.4.5] — 2026-10-22

### Fixed

- A node whose first connection to the bus failed (the bus down, or an account not yet approved after `telar
  instalar --unirse`) died quietly while `telar serve` kept running, and never came back. It now retries the first
  connection too, with waits that grow to a minute, and enters as soon as it can.

### Removed

- The single-token bus of before (`nats-server --auth`): telar connects only with the person's account.

## [0.4.4] — 2026-10-22

### Changed

- `telar instalar` ends with the address of this machine's page, with the key to enter the first time (the browser
  keeps it in a cookie) and the plain address for after.

## [0.4.3] — 2026-10-22

### Changed

- `telar instalar --unirse` removes a `[remotos.<name>]` that reaches the team's bus machine by ssh when someone
  else administers it: it belonged to the system of before (an account on the server), and that machine's things
  now arrive by the bus. It keeps a backup (`config.toml.antes-unirse`) and puts the block back if the
  configuration doesn't read without it.
- When the door can't be reached, the message names both causes: not being in the team's Tailscale network, or its
  access rule not opening ports 4222 and 8780 for shared users.

## [0.4.2] — 2026-10-22

### Changed

- `telar instalar` shows its plan as numbered steps and then each step as it runs: a spinner, ✓ or ✗, how long it
  took and, dimmed, what it said; what to do next (an approval to ask for) goes last, after `telar doctor`.
- `telar instalar --unirse` outside the team's repository no longer fails: it looks for the clone where clones
  usually are (`~/Code`, `~/Documents`…) and joins that one if there is exactly one; otherwise it warns and
  installs the rest. A folder given explicitly (`--unirse PATH`) without a team is still an error.

## [0.4.1] — 2026-10-22

### Added

- Roles on the bus: the **owner** (who runs it), **admins** (approve and decline join requests, remove accounts and
  change roles, except the owner's) and **members** (their account, as before). The bus server enforces it: the
  owner's account exports `admin.<owner>` only to admin accounts, and the bus machine's node serves it knowing who
  asks (`Nats-Request-Info`). `telar bus personas|pedidos|aprobar|rechazar|quitar` now work from any machine of the
  owner or of an admin, reload the bus by themselves, and there is `telar bus rol NAME admin|miembro` and `aprobar
  ID --rol admin`. The same in the page, ⚙ personas, and in the API, `GET /personas` and `POST /personas/<action>`.
  `[bus] administra` names the owner on an admin's machines; `telar instalar --unirse` writes it.
- `areas` and `internos` in a profile: the order of areas in the dashboard and the clients that are the house
  itself (shown by the project's name instead). `telar proyectos --json` gives `areas` and marks each project
  `interno`. They used to be fixed in the page's code.

### Changed

- `telar serve --equipo` with nobody in `[equipo.personas]` (or a broken `[equipo]`) warns and starts without the
  team page, instead of not starting at all.

### Removed

- The per-thread tmux sessions of before (`telar-…` with `@telar_hilo`): telar no longer opens, lists, watches or
  writes to them. Every thread is a window of the machine's telar session, addressed `@window/mark`. Gone with
  them: the `propio` field of a thread in `--json`, `sesion_tmux` in what a node publishes, and the `sesiones`
  check of `telar doctor`. A remote thread recorded with an address that is not `@window/mark` (empty, or one of
  before) counts as dead over there: opening it opens a new window. Before upgrading, `telar doctor` of 0.4.0
  should say `sesiones ok` on every machine.

## [0.4.0] — 2026-10-22

### Added

- Joining a team: `telar instalar --unirse`, run from a clone of the team's repository, reads its
  `.telar/equipo.yaml` (bus, who approves, modules, required programs), generates the bus secret locally and asks
  the bus machine to let the person in (`POST /unirse`, the only thing telar accepts without the page key: only on
  the bus machine, only from the Tailscale network, identified by `tailscale whois`, rate limited). Nothing is
  granted until the admin runs `telar bus aprobar` (`telar bus pedidos` lists them, `rechazar` declines).
- A module can declare what it asks for outside its folder in `[permisos]` of its `modulo.toml` (paths it reads
  and writes, network, telar commands it runs). `telar modulos instalar` shows it before asking, and says that telar
  does not enforce it yet; `telar modulos` lists it (`permisos` in `--json`) and `actualizar` says when it changed since what was shown at
  install (noted in `modulos.toml`, so a `--enlazar` module is covered too); control characters in it are shown
  escaped.
  A module without the table installs and runs as before. A thread waiting for its person is now a read-only
  object, `permiso:<thread>` (`telar objeto permiso:Faro`): since when it waits and, if its agent said so, what it
  asks for, taken from Claude Code's notification or from the new `telar agente aviso --evento espera --pide`.
- `[disparadores.<name>]` in the configuration: something that runs a command or sends a message by itself, on a
  clock (`cuando`, a cron schedule), a dashboard key (`tecla`) or a change (`al = "cambio:<topic>"`, announced by
  `telar cambio <topic>` on any machine). A clock trigger becomes one more process of `telar periodicos` (listed
  and run there, but changed in the configuration) and a key trigger one more `[atajos]` entry, both translated
  when read, so `periodicos.toml` and `[atajos]` keep working as before. A change trigger is run by the node of the
  machine where the periodic processes run, like a periodic process, with a brake: one run at a time per trigger,
  one pending run per burst, 30 s between runs and at most 12 an hour. New `telar disparadores [--json]` lists
  them and `telar disparadores correr <name>` runs one. `telar doctor` has a `disparadores` check (the trigger
  that replaces each `[atajos]` entry, clock triggers missing from the crontab, change triggers without a bus)
  and a `deseado` check: the node now notes, without fixing anything, the resident agents of its machine that
  have no session (one log line when that changes, and `<state>/deseado.json`, which also lists the residents so
  doctor can tell "none here" from "all alive"). A clock or change trigger named like a process of
  `periodicos.toml` or of a module does not run, and `telar doctor` reports it as a failure; the other periodic
  processes keep running. `telar periodicos nuevo` (and the dashboard) refuses a trigger's name. The dashboard
  shows no pause, edit or delete buttons for a periodic process that a trigger or a module declares. A change
  trigger runs on a daemon thread, so a long command does not hold up stopping the node.
- `[vistas.<key>]` in the configuration: what is shown (`comando`, `archivo`, `url`, or `carpeta`/`en` for a
  daily result) and where it appears (`aparece = "pestana" | "plan" | "apps" | "hilos" | "dia"`). It replaces
  `[bloques]`, `[apps]`, `[secciones]` and `[resultados]`, which are still read: each view is translated to its
  old table when the configuration is loaded, so nothing else changes. A name declared in both forms is an
  error, and so is a module named like a view. `telar doctor` has a new `vistas` check that writes, as TOML
  ready to paste, the view for each old table; a key declared in two old tables (`[bloques.x]` and
  `[apps.x]`) cannot be one view and is left as it is.
- Messages have a mode: `telar mensaje --modo aviso|pedido|encargo|consulta` (also `modo` in `POST /mensajes`).
  `pedido`, the default, is what a message always was. An `aviso` waits in the thread's inbox without waking
  it (no «↯», no session opened, no longer turn) and comes in with its next turn. An `encargo` creates a task
  object, `encargo:<id>`, kept on the receiver's machine, that it accepts, rejects or closes with a result
  (`telar objeto encargo:<id> aceptar|rechazar|cerrar`); closing it sends the result back to the thread that
  asked, and it can be opened from any machine (a new `encargo` request to that machine's node). A `consulta`
  sends nothing: it returns the thread's card and its last turns (also `GET /mensajes/consulta`). `telar
  encargar` is unchanged.
  An encargo is found after its thread moves: the sender's note keeps the machine the thread lived on, and the
  address the thread receives carries it (`encargo:<id>@<machine>`). Rejecting one needs a reason; two actions
  at once on the same encargo do not overwrite each other; a renamed thread closes it under its new name; a
  held encargo shows `retenido`, not `en_camino`; a basic-format deadline (`20261024`) is stored as
  `2026-10-24`; an `aviso` from the person says it is one; the wake-up line counts the waiting avisos apart.
- Addresses and objects (`telar.objetos`). Anything has one address, `type:id[@machine]` (`tarea:T366`,
  `hilo:Telar`, `proyecto:proyectos/faro`, `archivo:telar:docs/x.md`), and `telar objeto <address>
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
  than one declared repo (a thread outside every repo does not count as one).
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
- The `/hilos` skill says that `telar directorio`'s `direccion` is an email, not a `type:id` address, and that a
  `mensaje` goes to the name's mailbox whatever the machine.
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
- Documented and tested how the task model evolves: task files never carry a `version` field; the reader
  understands the old form and the new one and both give the same task (an omitted field is its default, the
  checkbox's two dialects and key synonyms), and a key the format does not know is kept byte for byte.
- `telar config --json` (and `GET /config`) lists the repositories of `[repos]` in a new `repos` field (name,
  path, profile), and each module now says where it came from: `instalado`, `fuente`, `version` and `enlazado`,
  from what `telar modulo` wrote down (empty for one declared by hand). No other field changes.
- A module's `fuente` no longer shows the `user:password@` part of a URL in `telar config` (nor in `GET /config`),
  and `telar config` and `telar modulos` no longer end the line with a dangling `@` when no version was recorded.
- One owner per thread: the link, the archived flag and the conversation of a thread that lives on another
  machine are read from what its owner publishes, not from a local copy. Each node publishes them with its
  threads' state (new `vinculo` and `archivado` fields in `TELAR_HILOS`), the other nodes keep the latest in
  `ajenos.json` (ignored once the node stops refreshing it for two minutes), and the list and the page read
  them from there; changing them goes to the owner, as before, and `--json` already shows the change. The
  local copy is still written and is what counts while the owner does not publish a field (an older telar
  there, no bus, or the local node off). In `sesiones`, the owner's conversation comes first and the earlier
  ones known here follow. `telar doctor` gains a `sesiones` check that lists the old per-thread tmux sessions
  (`telar-…`) still alive, and warns when it could not ask tmux.
- A resident agent can be defined in an `agente.toml` next to its `CLAUDE.md`: `nombre` (overrides the README
  title), `para` (when to hand it work), `modelo` (passed as `--model` when its session or thread opens; a
  `--model` or `--model=…` in `[agentes.<folder>] argumentos` wins) and `residente` (`false`: the node does not
  open its session by itself when a message arrives, but an `encargo` from `telar encargar` or a periodic job
  still opens it, with or without a bus). Other fields are accepted and shown, not yet used; a broken file or
  field (control characters included) is ignored with a warning, never disabling the agent, and a file saved
  with a BOM reads fine. A declared `nombre` that the bus would see as another agent's (`FARO` next to `Faro`)
  keeps the old one. After a rename the node keeps collecting the old name's mailbox into the new one, and
  `telar doctor` warns about messages waiting under the old name, conversations under both names, and a name
  that is already a project thread's. Without the file nothing changes. New `telar agentes [agent] [--json]`
  lists what each declares, a new `agente:<folder>` object type shows it and hands it work (`encargar`), `telar
  doctor` gains an `agentes` check, and the example workspace has a resident.
- `telar doctor` warns, in its `módulos` check, when a module is named like a telar command (`telar <name>`
  runs the command, not the module) or brings an `[objetos.<type>]` of a type telar already ships (telar's wins).

### Changed

- Nothing of the author's own life ships in telar any more: real people, clients and the resident agent's name
  left the tests, examples and docs for invented ones; the page signs notes and its messages to agents with the
  person's own name instead of a fixed one; the team page names whoever shares the tasks (`[equipo] dueno`, or
  `[persona] nombre`); and a colleague created with `telar persona` wakes no thread by default.
- A repository's profile lives in its `.telar/` folder, `.telar/perfil.yaml`, and `telar-perfil.yaml` is no
  longer read (`telar doctor` says how to move it). `.telar/local.yaml`, per person and out of git, is read on top
  of the profile: a value replaces, a map merges key by key, `null` removes.
- A thread on another machine carries its machine in its address everywhere (`hilo:Faro@servidor`); a message to
  `hilo:X@machine` is refused (404) if that machine has no thread X, instead of waiting in a mailbox nobody reads.
- A `[repos]` path is given absolute everywhere (`telar config --json`, `TELAR_REPOS`): a relative one, read from
  the root.
- A document checkbox with an id is named by it (`faro:c-1a2b3c`) instead of its place, and fills `{direccion}` in
  message templates with its own (`pendiente:c-1a2b3c`); an old place reference still finds it.
- A relative `[repos.<name>].ruta` is read from `raiz`, not from the directory the command runs in, so a
  thread's `repo` no longer depends on where `telar hilos` or the server was started; `telar doctor` suggests
  writing it absolute (modules still get it as written in `TELAR_REPOS`, as does `telar config --json`).
- `telar objeto hilo:<name>@<machine>` opens that machine's thread even when a thread with the same name lives
  here (it used to return the local one).
- Two identical checkboxes without an id in one document are now two rows in `telar pendientes` (they used to
  be one, and writing it failed), each with a new `repetida` field (`{"cual": 2, "de": 2}`, `null` when the text
  is unique). `telar pendiente` writes the one the row names and gives it its own id; if the number of
  checkboxes with that text changed meanwhile, it is a 409 and nothing is written.
- Task files: `dueno` (without ñ) is read as `dueño` and rewritten under its own name, as is a key written in NFD.

### Fixed

- Task files: a leading BOM no longer hides the header (an action used to prepend a second one), CRLF files stay
  CRLF when an action writes them, and a repeated key the format does not know is no longer reported as duplicated.
- The node's log no longer grows without bound: a bus failure (`nats: timeout`, a refused connection, a slow
  consumer) is one line instead of a full traceback, the same failure is written once every ten minutes with a
  count of the ones in between, losing and regaining the bus is one line each (a drop that comes back within a
  minute is counted with the next one written, so a flapping hotspot is not two lines per drop), a clean
  shutdown is no longer logged as a lost connection, and `telar serve` trims its log file to its last half past
  4 MB (only a regular file opened for appending, as launchd does; journald and terminals are left alone).
- A node loop that fails (`vuelta con error`, every 2 s while the bus is down) is written once every ten minutes
  with a count, and the log is trimmed every 30 s even while every loop fails.
- A slow request to a node no longer holds up what arrives behind it: each request runs in its own task, four
  at a time per verb, so slow requests of one verb never delay another; the ones that only read (`leer`,
  `resultado`, `proveedor`, `notas`, `serie`, `archivo-leer`) run side by side, the ones that write (and mail
  from another person) still go one at a time per verb, in order; with 64 of one verb in progress or waiting
  the node answers that verb `{"ok": false, "ocupada": true}` at once. Every request and notice subscription of
  the node has a cap on what can wait (2000 messages, 32 MB) instead of nats-py's half a million (the two
  key-value watchers keep nats-py's own, which telar cannot set).
- The node's watcher of the threads' state no longer opens tmux and files event by event: it keeps the latest
  of each thread and another task handles it, so a burst of attention changes is handled once and the watcher
  keeps up with the bus. A state that cannot be written no longer stops the watcher. The watcher of the other
  machines' snapshots does the same: it only receives, and the latest snapshot of each machine is saved apart.
- Each loop of the node asks all its threads' mailboxes at once, waiting up to 1 s, instead of one after the
  other at 0.3 s each, and stores each message outside the event loop.
- Reading from the bus (`telar mensaje --registro`, `telar nodo estado`, where a thread lives) is retried once
  when a request times out after connecting, and so is sending a message, always within the same deadline as
  before (the retry only uses the time left, at least 1 s): the copy in the log now carries an id too, so a
  retry never stores anything twice, and so does the copy of a mail from another person. A message whose id
  had already been sent is still reported `duplicado` when the first try failed before publishing. The node
  waits 10 s for JetStream instead of 5.

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
- An object's address (`tarea:T366`, `hilo:Telar`, `proyecto:proyectos/faro`, `archivo:telar:docs/x.md`, and
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
  thread it goes to on top: the general agent by default, the task's thread, or any thread in the list,
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
  `telar › Faro` for a thread of that machine, `telar ⇢ laptop:Telar` for one of another (forwarded). A
  thread of another machine is named `máquina:hilo`, like `scp máquina:ruta` (with the person it would be
  `ana@laptop:Faro`). The machine is its name on the bus, or its hostname without one, from `/salud` (which
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
  priority suggestion; clicking one opens its actions — «preguntarle a <agente>» (hands it the request: it checks whether it already
  exists and decides new task / update an existing one / not applicable, using `telar equipo aceptar|existe|rechazar`, and answers in
  one line; the row shows the agent's name while it works), «agregar como tarea», «es T123: contestarle su estado» and «descartar». New
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
  you tap «enviar». New `/api/lectura` (a script that leaves a reading).
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

[Unreleased]: https://github.com/nicorivas/telar/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/nicorivas/telar/compare/v0.3.0...v0.4.0
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
