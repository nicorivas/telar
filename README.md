# telar

A loom for threads of work.

You keep twenty terminal tabs open. Each one is a different piece of work, each has
an agent running in it, and after a reboot you cannot tell which is which. `telar`
turns those tabs into **threads**: a tab, a folder, and whatever that folder says
about itself, held together across restarts.

**telar does not decide what a project is.** That is the point. Your work
repository declares it, in a `telar-perfil.yaml` that ships with the repo — which
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
pip install telar          # once it's published
pip install -e .           # from a clone
telar --version
```

Python 3.11+. Standard library only, except PyYAML for reading the profile. A
terminal multiplexer (tmux 3.0+ or zellij 0.45+) does the actual work of holding tabs.

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
| Profile — what a unit of work is, and what can be read from it | the work repository's, versioned with it | `telar-perfil.yaml` ([docs](docs/perfil.md)) |
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

- [`docs/configuracion.md`](docs/configuracion.md) — the config file, key by key.
- [`docs/perfil.md`](docs/perfil.md) — the profile schema, and the minimal
  convention that applies when there is no profile.
- [`docs/contratos.md`](docs/contratos.md) — the shapes telar passes around, written
  so an outside program can produce them. Today: a thread's state.
- [`docs/agentes.md`](docs/agentes.md) — the six events an agent reports, and what
  another agent would have to do to integrate.
- [`ejemplo/`](ejemplo/) — a small invented workspace.

## License

MIT — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
