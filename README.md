# telar

A loom for threads of work.

You keep twenty terminal tabs open. Each one is a different piece of work, each has
an agent running in it, and after a reboot you cannot tell which is which. `telar`
turns those tabs into **threads**: a tab, a folder, and whatever that folder says
about itself, held together across restarts.

**telar does not decide what a project is.** That is the point. Your work
repository declares it, in a `.telar/perfil.yaml` that ships with the repo — which
folders are units of work, which file is their face, which sections of that file
can be read, and which actions the repo offers. Any telar that opens the repo
weaves the same thing.

## Status

Early, but it runs. Configuration, profile, model and state are in place, the
commands are written, and every `--json` output is a documented contract
([docs/contratos.md](docs/contratos.md)). `telar --help` lists what there is, and
says so plainly when you ask for something that isn't written yet.

## Install

```sh
uv tool install 'telar[serve,bus]'   # the CLI, the web page and the bus client (or pip install)
telar instalar                       # config, page key, the `telar serve` service, the agent hooks
```

`telar instalar` shows what it will do and asks first; run it again whenever you like, it only does
what is missing. To join the bus of your other machines: `telar instalar --bus nats://host:4222` (the
secret comes from `telar bus persona` on the bus machine). Then open the page it prints.

To join a team, run it from your clone of the team's repository (the one with a `.telar/equipo.yaml`):
`telar instalar --unirse`. It checks what the team needs, generates your bus secret on your machine, asks the
team's bus to let you in (only a hash travels), and adds the repository and the team's modules to your config;
whoever runs the bus approves you with `telar bus aprobar`.

Python 3.11+ and tmux 3.5+ (3.4 has a server crash that takes every thread with it). The VS Code
extension is deprecated: the web page does everything it did.

## Try it

Two ways in. **From a clone**, an invented workspace ships with the repo, so you can
look at a real profile without using anyone's data:

```sh
git clone https://github.com/nicorivas/telar && cd telar
telar --raiz ejemplo perfil              # what the example workspace declares
telar --raiz ejemplo pendientes --repo   # what those invented projects still owe
```

**From an install**, start in your own repository — `init` writes a profile you can edit
and a config file, and touches nothing else:

```sh
cd ~/work/your-repo
telar init                         # profile + config, both yours to edit
telar doctor                       # what is missing on this machine, and how to fix it
telar --help
```

(`pip install telar` ships the package, not the example; the example travels with the
source distribution and the clone.)

## A day of it

```sh
telar init                 # write the config, find the multiplexer, prepare the state
telar tejer                # raise the session
telar vincular proyectos/faro      # this thread is that folder
telar hilos                # everything open, with the state each folder reports
telar ficha faro           # what that folder says about itself
telar pendientes           # what is left to do, across threads
telar pendiente faro:2     # take that one to the thread where the work lives
telar hoy                  # the day in one screen
telar atajo m              # a dashboard shortcut: a new thread with the agent doing it
telar proyectos            # every unit of work; `abrir <ruta>` opens one with the agent
```

Two of them are meant to be called by other programs, not by you:
`telar tiempo marcar` from the multiplexer whenever the focused tab changes, and
`telar atencion set espera` from the agent when it needs you. `telar doctor` checks
whether either is wired.

## Wiring the agent

The agent working inside a tab can report what it is doing, and telar writes those
hooks into the agent's own configuration — for Claude Code, `~/.claude/settings.json`.
That file belongs to another program, so the command prints the path and the diff and
waits for a yes:

```sh
telar agente instalar                    # show the path and the diff, then ask
telar agente instalar --seco             # what it would write, writing nothing
telar agente instalar --ajustes FILE     # into that file instead of the user's
telar agente instalar --ejecutable PATH  # how the hook should call telar back
telar agente instalar --si               # write without asking (--json skips it too)
telar agente desinstalar                 # take telar's hooks out, leave the rest
```

It merges with the hooks that were already there, keeps a backup beside the file, and
refuses to write a hook that points at a telar which will not outlive it — one running
from a temporary virtualenv, say. The six events are in
[`docs/agentes.md`](docs/agentes.md).

## How it fits together

| Piece | Whose | Where |
|---|---|---|
| Configuration — multiplexer, session, working root, providers | yours, per machine | `~/.config/telar/config.toml` ([docs](docs/configuracion.md)) |
| Profile — what a unit of work is, and what can be read from it | the work repository's, versioned with it | `.telar/perfil.yaml` ([docs](docs/perfil.md)) |
| Threads, fichas, attention | derived, disposable | `~/.local/state/telar` |

## What it will not do

- **No telemetry.** No usage reports, no phone-home, no auto-update.
- **No network** beyond what a provider declares — and no provider exists until
  your configuration names it.
- **No writing to your work repository** unless you ask. Derived state lives
  elsewhere and can be deleted without losing anything.
- **No silent writes anywhere else, either.** One command edits another program's
  configuration — `telar agente instalar` — and it shows the path and the diff and
  waits for a yes. `--si` is how you say it in a script.
- **No guessed commands.** It runs the actions the profile declares, as argument
  lists, without a shell in between.

## Documentation

Docs are in Spanish, the language this is written in.

- [`docs/arquitectura.md`](docs/arquitectura.md) — how the pieces fit, where your own things
  plug in, and connecting a task system end to end (in Spanish).
- [`docs/configuracion.md`](docs/configuracion.md) — the config file, key by key.
- [`docs/perfil.md`](docs/perfil.md) — the profile schema, and the minimal
  convention that applies when there is no profile.
- [`docs/contratos.md`](docs/contratos.md) — the shapes telar passes around, written
  so an outside program can produce them. Today: a thread's state.
- [`docs/agentes.md`](docs/agentes.md) — the six events an agent reports, and what
  another agent would have to do to integrate.
- [`docs/publicar.md`](docs/publicar.md) — how a version gets out: what to set up
  once, and the runbook per release.
- [`docs/desarrollar.md`](docs/desarrollar.md) — seeing a change at once while working
  (`scripts/dev.py`), and deploying it to your machines (`servidor/desplegar.sh`).
- [`ejemplo/`](ejemplo/) — a small invented workspace.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed, version by version.

## License

MIT — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
