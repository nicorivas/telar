#!/usr/bin/env bash
# Publicar una versión de telar en GitHub: un solo commit con el árbol de main encima de origin/main, y su etiqueta.
#
#     scripts/publicar.sh                  en seco: revisa y muestra lo que haría
#     scripts/publicar.sh 0.15.0           lo mismo, y además exige que __version__ sea 0.15.0
#     scripts/publicar.sh --de-verdad      revisa y, si todo está bien, sube el commit y la etiqueta
#
# Por qué así: el repositorio de GitHub es público y el historial de trabajo trae nombres privados, así que la rama
# main local nunca sube; sube una foto de su árbol por versión. El detalle, en docs/publicar.md, «Cada versión».
#
# Antes de tocar nada revisa: que se corra desde main; el árbol limpio (lo que se publica es lo commiteado); que
# __version__ sea la versión pedida; que CHANGELOG.md tenga su sección; que la etiqueta no exista ni aquí ni allá; que
# origin/main esté al día (se trae) y que lo que hay allá haya salido de main (su árbol es el de algún commit de main:
# si no, alguien subió algo a GitHub que main no tiene y esta versión lo borraría); y que haya algo nuevo que subir.
# Con --de-verdad, además, instala el gancho pre-push (scripts/pre-push) si falta.
#
# El remoto es `origin`; otro, con PUBLICAR_REMOTO=<nombre>.
set -euo pipefail

de_verdad=0
pedida=""
for a in "$@"; do
  case "$a" in
    --de-verdad) de_verdad=1 ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "publicar: no conozco $a" >&2; exit 2 ;;
    *) [ -z "$pedida" ] || { echo "publicar: una sola versión" >&2; exit 2; }; pedida="${a#v}" ;;
  esac
done

remoto="${PUBLICAR_REMOTO:-origin}"
raiz=$(git rev-parse --show-toplevel)
cd "$raiz"

problemas=""
problema() { problemas="${problemas}  - $1"$'\n'; }

rama=$(git symbolic-ref --quiet --short HEAD || echo "(sin rama)")
[ "$rama" = main ] || problema "se publica desde main, y aquí estás en $rama"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  problema "el árbol no está limpio (git status): lo que se publica es lo commiteado"
fi

version=$(git show main:src/telar/__init__.py 2>/dev/null | sed -n 's/^__version__ = "\(.*\)"$/\1/p')
if [ -z "$version" ]; then
  problema "no encuentro __version__ en src/telar/__init__.py de main"
elif ! printf '%s' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  problema "__version__ es «$version», que no es x.y.z"
fi
if [ -n "$pedida" ] && [ "$pedida" != "$version" ]; then
  problema "pediste $pedida y __version__ dice ${version:-nada}: primero cámbialo y commitéalo"
fi
etiqueta="v${version}"

# (a una variable y no a `grep -q` por tubería: con pipefail, el SIGPIPE de git show haría fallar lo que sí está)
changelog=$(git show main:CHANGELOG.md 2>/dev/null || true)
if [ -n "$version" ] && ! printf '%s\n' "$changelog" | grep "^## \[${version//./\\.}\]" >/dev/null; then
  problema "CHANGELOG.md no tiene la sección «## [$version]»: mueve ahí lo de [Unreleased]"
fi

if [ -n "$version" ]; then
  git rev-parse --quiet --verify "refs/tags/$etiqueta" >/dev/null && problema "la etiqueta $etiqueta ya existe aquí"
fi

if ! git fetch --quiet "$remoto" "+refs/heads/main:refs/remotes/$remoto/main"; then
  problema "no pude traer main de $remoto"
fi
alla=$(git rev-parse --quiet --verify "refs/remotes/$remoto/main" || true)
if [ -z "$alla" ]; then
  problema "$remoto no tiene main: la primera versión no se sube con esto"
else
  if [ -n "$version" ] && [ -n "$(git ls-remote --tags "$remoto" "refs/tags/$etiqueta")" ]; then
    problema "la etiqueta $etiqueta ya está en $remoto"
  fi
  arbol_alla=$(git rev-parse "$alla^{tree}")
  arbol_main=$(git rev-parse "main^{tree}")
  if [ "$arbol_alla" = "$arbol_main" ]; then
    problema "$remoto/main ya tiene exactamente el árbol de main: no hay nada que publicar"
  elif ! git log --format=%T main | grep -x "$arbol_alla" >/dev/null; then
    problema "lo que hay en $remoto/main no salió de main (ningún commit de main tiene su árbol): alguien subió algo allá; tráelo a main antes de publicar"
  fi
fi

gancho=$(git rev-parse --git-path hooks/pre-push)
case "$gancho" in /*) ;; *) gancho="$raiz/$gancho" ;; esac
gancho_falta=0
if [ ! -f "$gancho" ]; then
  gancho_falta=1
elif ! cmp -s "$gancho" scripts/pre-push; then
  echo "aviso: $gancho no es igual a scripts/pre-push (cópialo si el versionado es el bueno)" >&2
fi

if [ -n "$problemas" ]; then
  printf 'publicar: no publico %s:\n%s' "${etiqueta}" "$problemas" >&2
  exit 1
fi

mensaje="telar $version"
echo "Publicar $etiqueta: el árbol de main ($(git rev-parse --short main)) como un commit encima de $remoto/main ($(git rev-parse --short "$alla"))."
[ "$gancho_falta" = 1 ] && echo "  instalar el gancho: cp scripts/pre-push $gancho"
echo "  SNAP=\$(git commit-tree 'main^{tree}' -p $remoto/main -m '$mensaje')"
echo "  git push $remoto \"\${SNAP}:refs/heads/main\""
echo "  git tag -a $etiqueta \"\${SNAP}\" -m '$mensaje'"
echo "  git push $remoto $etiqueta"

if [ "$de_verdad" != 1 ]; then
  echo "En seco: no hice nada. Con --de-verdad, lo hago."
  exit 0
fi

if [ "$gancho_falta" = 1 ]; then
  mkdir -p "$(dirname "$gancho")"
  cp scripts/pre-push "$gancho"
  chmod +x "$gancho"
fi
snap=$(git commit-tree "main^{tree}" -p "$alla" -m "$mensaje")
git push "$remoto" "${snap}:refs/heads/main"
git fetch --quiet "$remoto" "+refs/heads/main:refs/remotes/$remoto/main"
git tag -a "$etiqueta" "$snap" -m "$mensaje"
git push "$remoto" "$etiqueta"
echo "Publicado $etiqueta ($(git rev-parse --short "$snap")). Falta: que el workflow publique en PyPI y probar la instalación (docs/publicar.md)."
