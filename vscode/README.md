# telar for VS Code

Your work threads in the sidebar, next to the terminal where they actually run.

telar keeps one *thread* per unit of work: a multiplexer tab (tmux or zellij) tied to a
folder of your working repository. This extension is the **view**. The session, the
processes and the state stay in telar; what you see here is read from `telar … --json`,
and every action is another command of the same CLI. Nothing is stored on this side: if
the extension dies, nothing is lost.

```
 3 ● faro           ●   49m    id · priority · name · attention · time today
 4 ◐ molino               7m
 ▸ ARCHIVO 6 hilos         2d
```

## The five views

| View | What it shows |
|---|---|
| **hilos** | Every thread, live or not: priority, the agent's attention (working / waiting for you / done), today's time, and the thread's one-line status in the tooltip. Right-click for the whole menu. |
| **tareas** | Everything the documents declare pending, plus whatever a declared provider adds. Sorted by urgency, searchable with `/`, reachable with a letter. |
| **ficha** | What a thread's document says about itself: status, pending items, the sections your profile declares (fields, waiting-on, milestones, links), and the actions the repository offers. A second tab renders the document itself. |
| **carpeta** | The thread's folder, and only that folder — VS Code's explorer always shows the workspace root and can't be narrowed. |
| **hoy** | The day in one panel: what has an hour, who is waiting for you, what is pending. |

Everything is drawn with the terminal's own font and colors (`terminal.integrated.*` and
the theme's ANSI variables), so the sidebar reads as a continuation of the terminal rather
than as another program.

## Requirements

* [telar](https://github.com/nicorivas/telar) on your `PATH` (`telar --version` should answer).
* A multiplexer telar can talk to: **tmux** or **zellij**.
* A working repository. telar does not decide what a project is — your repository declares
  it in `telar-perfil.yaml` (see [docs/perfil.md](https://github.com/nicorivas/telar/blob/main/docs/perfil.md)). Without one, telar falls back to a
  minimal convention and the views still work, with less to show.

## Install

From the Marketplace, search for **telar**, or install it by id:

```sh
code --install-extension nicorivas.telar-hilos
```

The id says `telar-hilos` because the Marketplace keeps one global namespace for
extension names and `telar` was already taken. Everywhere you see it, it is telar.

From source, inside this folder:

```sh
npm install        # once: TypeScript and the packaging tools
npm run compile    # writes out/
npm run package    # writes telar-<version>.vsix
code --install-extension telar-*.vsix
```

`npm run watch` recompiles while you work; **Run Extension** (F5) opens a second window
with the extension loaded.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `telar.cli` | `telar` | The program. Looked up in your `PATH`; an absolute path also works. |
| `telar.config` | *(empty)* | Config file, passed as `--config`. Empty means telar's own default. |
| `telar.raiz` | *(empty)* | Working repository root, passed as `--raiz`. Prefer an absolute path. |
| `telar.orden` | `mux` | Sort order: `mux`, `alfa`, `reciente`, `prioridad`. `⌥O` changes it. |
| `telar.intervalo` | `2000` | How often (ms) the thread list is refreshed (`--sin-ficha`: cheap). |
| `telar.intervaloFicha` | `60000` | How often (ms) the documents are re-read. This is the only expensive read. |

The extension host does not inherit your login shell's `PATH`, so on first activation it
asks `$SHELL` for it and adds `~/.local/bin`, `/usr/local/bin` and `/opt/homebrew/bin` if
they are missing. Whatever `telar.cli` names has to be reachable that way.

## Keys

`⌥1`…`⌥9` go to the Nth thread · `⌥H` hoy · `⌥T` tareas · `⌥F` ficha · `⌥P` jump to a
thread · `⌥O` sort · `⌥A` fold the archive.

Inside **hoy** and **tareas**: `/` searches, a letter works the pending item next to it,
`⌘`+click forces a new thread, `r` reloads (providers included), `⎋` gives the keyboard
back to the terminal.

Clicking a pending item runs `telar pendiente <ref>`: it finds the thread where that work
already lives, focuses it, and **writes** the line to the agent sitting there without
sending it. Pressing Enter is yours.

## How it works

Two rhythms, because reading documents is the only expensive part:

* every `telar.intervalo`, `telar hilos --json --sin-ficha` — who is alive, who has focus,
  what each agent said, how long today;
* every `telar.intervaloFicha`, `telar hilos --json` — the same plus each thread's status
  line, kept between fast reads.

The day is read from `telar hoy --json --local` (nothing leaves the machine) and, every
five minutes or on `r`, from `telar hoy --json`, which consults the providers your
configuration declares. A provider that fails never takes the view down: it is listed as
down and the rest is drawn.

Actions map one to one onto the CLI: `telar ir`, `telar hilo vincular|renombrar|prioridad|
archivar|desarchivar|olvidar`, `telar pendiente`, `telar accion`, `telar tejer`. Anything
this extension cannot do, you can do in the terminal, and the other way around.

## What it does not do

* **No telemetry**, and no network of its own. The only thing that can reach the network is
  a provider you declared in telar's configuration, and it runs inside telar, not here.
* **It does not write to your repository.** It edits no documents and creates no files;
  what telar remembers about a thread lives in telar's own state directory.
* **It does not decide what a project is.** Archetypes, sections and actions come from your
  `telar-perfil.yaml`. This view only knows how to draw a table, a list, checkboxes and a
  paragraph.
* **It does not press Enter for you.** A pending item is written to the agent, never sent.

## Publishing

`package.json` ships with `TODO-publisher` in `publisher`, `repository`, `bugs` and
`homepage`. Replace those with the real ones, then:

```sh
npx vsce publish       # Visual Studio Marketplace
npx ovsx publish       # Open VSX
```

Both read the `.vsix` built by `npm run package`.

## License

MIT. See [LICENSE](LICENSE).
