#!/usr/bin/env bash
# Llevar lo commiteado de telar a las máquinas y reiniciar `telar serve`, en un solo comando, al terminar un
# bloque de trabajo (mientras se desarrolla, scripts/dev.py: los cambios se ven al tiro, sin desplegar).
#
#   servidor/desplegar.sh                 al servidor y a esta máquina
#   servidor/desplegar.sh --solo-servidor
#   TELAR_SERVIDOR=yo@otra servidor/desplegar.sh
#
# El servidor es el `destino` del primer [remotos] de la configuración (o TELAR_SERVIDOR). Allá: git pull;
# reinstalar telar si cambió pyproject.toml; npm ci si cambiaron las dependencias de vscode/; compilar la
# extensión si cambió vscode/; reiniciar telar-serve y comprobar que contesta y que los hilos (las ventanas
# de tmux) siguen ahí. Aquí: compilar la extensión y reiniciar el `serve` de esta máquina.
#
# Solo despliega lo que ya está en el remoto de git: si hay commits sin subir, se detiene.
set -euo pipefail

aqui=$(cd "$(dirname "$0")/.." && pwd)
solo_servidor=false
[[ ${1:-} == --solo-servidor ]] && solo_servidor=true

servidor=${TELAR_SERVIDOR:-$(telar config --json 2>/dev/null | python3 -c 'import json,sys; r=json.load(sys.stdin).get("remotos") or [{}]; print(r[0].get("destino",""))' || true)}
if [[ -z $servidor ]]; then
    echo "desplegar: ¿a qué servidor? no hay [remotos] en la configuración; usa TELAR_SERVIDOR=usuario@máquina" >&2
    exit 1
fi
# el repositorio, en el mismo lugar respecto de la casa (o TELAR_REPO_REMOTO)
repo_remoto=${TELAR_REPO_REMOTO:-${aqui#"$HOME"/}}

cd "$aqui"
git fetch -q
if [[ -n $(git log --oneline '@{u}..' 2>/dev/null) ]]; then
    echo "desplegar: hay commits sin subir (git push primero):" >&2
    git log --oneline '@{u}..' >&2
    exit 1
fi
[[ -n $(git status --porcelain --untracked-files=no) ]] && echo "ojo: hay cambios sin commitear aquí; no viajan"

echo "→ $servidor"
ssh "$servidor" bash -l -s -- "$repo_remoto" <<'ALLA'
set -euo pipefail
cd "$HOME/$1"
antes=$(git rev-parse HEAD)
git pull -q --ff-only
cambios=$(git diff --name-only "$antes" HEAD)
echo "  $(git log --oneline -1) ($(printf '%s\n' "$cambios" | grep -c . || true) archivos cambiados)"
if grep -q '^pyproject.toml$' <<<"$cambios"; then
    echo "  pyproject cambió: reinstalo telar"
    uv tool install -q --force --editable "$PWD[serve,bus]"
fi
if grep -q '^vscode/package' <<<"$cambios"; then
    echo "  dependencias de vscode/: npm ci"
    (cd vscode && npm ci -s >/dev/null)
fi
if grep -q '^vscode/' <<<"$cambios"; then
    (cd vscode && npm run -s compile)
fi
ventanas=$(tmux list-windows -a -F '#{window_id}' 2>/dev/null | sort -u | wc -l)
systemctl --user restart telar-serve
for _ in $(seq 30); do
    systemctl --user is-active -q telar-serve && curl -sf --unix-socket "${XDG_STATE_HOME:-$HOME/.local/state}/telar/serve/telar.sock" http://x/salud >/dev/null && break
    sleep 0.5
done
estado=$(systemctl --user is-active telar-serve || true)
salud=$(curl -sf --unix-socket "${XDG_STATE_HOME:-$HOME/.local/state}/telar/serve/telar.sock" http://x/salud >/dev/null && echo contesta || echo "NO contesta")
despues=$(tmux list-windows -a -F '#{window_id}' 2>/dev/null | sort -u | wc -l)
echo "  telar-serve $estado, la API $salud; ventanas de tmux: $ventanas antes, $despues después"
[[ $estado == active && $salud == contesta && $despues -ge $ventanas ]]
ALLA

$solo_servidor && exit 0

echo "→ esta máquina"
(cd vscode && npm run -s compile)
if [[ $(uname) == Darwin ]]; then
    launchctl kickstart -k "gui/$(id -u)/com.telar.serve"
else
    systemctl --user restart telar-serve
fi
for _ in $(seq 30); do
    curl -sf --unix-socket "${XDG_STATE_HOME:-$HOME/.local/state}/telar/serve/telar.sock" http://x/salud >/dev/null && { echo "  telar serve contesta"; exit 0; }
    sleep 0.5
done
echo "  telar serve NO contesta: mira su log" >&2
exit 1
