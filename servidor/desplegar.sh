#!/usr/bin/env bash
# Se retiró: lo hace `telar desplegar` (docs/desarrollar.md, «Llevarlo a las máquinas»), que lleva main de aquí a
# cada máquina de [remotos] sin pasar por GitHub, reinicia lo que declara .telar/despliegue.yaml y comprueba que la
# página de cada una sea la misma. Esto avisa y lo llama; --solo-servidor es ahora --maquina <nombre del remoto>.
set -euo pipefail

aqui=$(cd "$(dirname "$0")/.." && pwd)
echo "desplegar.sh se retiró: usa \`telar desplegar\` (ahora lo llamo yo)" >&2
if [[ ${1:-} == --solo-servidor ]]; then
    echo "  --solo-servidor ya no existe: \`telar desplegar --maquina <nombre del remoto>\`" >&2
    exit 2
fi
exec telar desplegar --repo "$aqui" "$@"
