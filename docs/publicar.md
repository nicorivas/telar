# Publicar una versión

Publicar es apretar un botón: `scripts/publicar.sh --de-verdad` (abajo, «Cada versión»). Todo lo demás lo hace
`.github/workflows/publicar.yml`. Lo que sigue es lo que hay que preparar **una sola vez**,
porque son cuentas y permisos que solo tiene su dueño, y después el runbook de cada versión.

## Lo que hay que hacer una vez

### 1. Decidir el nombre

El paquete se llama `telar` porque el nombre estaba libre en PyPI el 21-sep-2026, no porque
se haya elegido. Antes de la primera publicación conviene confirmarlo: después de subir una
versión, el nombre queda tomado para siempre aunque se borre el archivo. Si se cambia, hay
dos lugares: `name` en pyproject.toml y el módulo `src/telar/`.

### 2. PyPI sin guardar ningún token

PyPI puede confiar directamente en este workflow, sin que haya una credencial escrita en
ninguna parte. En <https://pypi.org/manage/account/publishing/>, «Add a new pending
publisher»:

| campo | valor |
| --- | --- |
| PyPI Project Name | `telar` |
| Owner | `nicorivas` |
| Repository name | `telar` |
| Workflow name | `publicar.yml` |
| Environment name | `pypi` |

El entorno `pypi` de GitHub ya está creado (Settings › Environments). Se le puede poner
«Required reviewers» = uno mismo: así cada publicación pide una confirmación a mano antes
de salir, que es la última red entre una etiqueta apurada y una versión pública. Hoy no lo
tiene, porque la etiqueta ya es una decisión deliberada.

Para ensayar sin quemar el número de versión, TestPyPI acepta el mismo trámite y se prueba
con `pypa/gh-action-pypi-publish` apuntado a `https://test.pypi.org/legacy/`.

### 3. La extensión de VS Code: ya no

La extensión está deprecada desde el 20-oct-2026 y el workflow ya no la empaqueta ni la publica:
la página que sirve `telar serve --web` hace todo lo que hacía. El código de la página está en
`pagina/` y viaja dentro del paquete de Python (`src/telar/web/`).

### 4. El repositorio es público

Ya está abierto. Lo que se hace público con cada versión es el árbol, no el historial de trabajo: desde 0.14.0 sube
un solo commit por versión («Cada versión», abajo). Lo publicado hasta 0.13.0 sí lleva el historial completo, y ahí
queda. Por eso, antes de cada versión, lo que importa es el árbol: que no haya nada personal en los archivos (rutas de
la máquina, nombres de clientes, correos que no sean el de quien firma; `git grep -inE` sobre main).

## Qué número le toca

[Semantic Versioning 2.0.0](https://semver.org/lang/es/), y el CHANGELOG en el formato de
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Lo que cuenta como la interfaz pública es lo que
promete `docs/contratos.md` (la CLI y su `--json`, el estado de un hilo, los proveedores), más la configuración
(`telar.toml`), el protocolo del bus y la API HTTP de `telar serve`. La página es la cara, no un contrato.

Mientras telar esté en `0.y.z` (la interfaz todavía se mueve):

| lo que trae «Unreleased» | sube | ejemplo |
| --- | --- | --- |
| algo que rompe: se quita o cambia un verbo, un campo del `--json`, una clave de la configuración, un mensaje del bus | `y` (minor) | 0.9.4 → 0.10.0 |
| algo nuevo (cualquier entrada en **Added**), aunque no rompa nada | `y` (minor) | 0.9.4 → 0.10.0 |
| solo arreglos (**Fixed**) y cambios que no agregan capacidad (aspecto de la página, textos, rendimiento) | `z` (patch) | 0.9.4 → 0.9.5 |

Decide la sección más pesada de lo que se publica, no la última que se escribió. Una versión que rompe lo dice
arriba de su entrada, en **Changed** o **Removed**, con qué hay que hacer para seguir.

`y` pasa de 9 a 10, no a 1.0: el número es un contador, no una fracción. **1.0.0** es una decisión aparte,
cuando los contratos se den por estables; desde ahí, lo que rompe sube `x` (major) y lo nuevo sube `y`.

Los números ya publicados no se reescriben (PyPI no deja reusar uno): de 0.9.1 a 0.9.4 trajeron funciones
nuevas como si fueran parches, y quedan así.

## Cada versión

A GitHub no sube la rama main: sube **un solo commit por versión**, con el árbol de main y de padre lo que ya hay en
`origin/main`, más su etiqueta. Es porque el repositorio de GitHub es público y el historial de trabajo trae nombres
privados. Desde 0.14.0 (23-nov-2026).

1. Elegir el número según «Qué número le toca» (arriba) y cambiarlo: `__version__` en src/telar/\_\_init\_\_.py. El
   primer trabajo del workflow no hace otra cosa que comprobar que la etiqueta y ese número coinciden.
2. Mover lo que corresponda de «Unreleased» a la versión nueva en CHANGELOG.md. Lo que siga en `changelog.d/` es de
   ramas sin fusionar: no entra en esta versión (docs/desarrollar.md, «El CHANGELOG, por fragmentos»).
3. Commitear en main, y publicar desde main:

   ```sh
   scripts/publicar.sh 0.15.0              # en seco: revisa y muestra lo que haría
   scripts/publicar.sh 0.15.0 --de-verdad  # lo hace
   ```

   Antes de tocar nada revisa que se corra desde main con el árbol limpio, que `__version__` sea el número pedido,
   que CHANGELOG.md tenga su sección `## [0.15.0]`, que la etiqueta no exista ni aquí ni en GitHub, y que
   `origin/main` esté al día (lo trae) y haya salido de main: si su árbol no es el de ningún commit de main, alguien
   subió algo allá que esta versión borraría, y se niega. Con `--de-verdad` instala además el gancho, si falta.
   Lo que hace es esto, que también se puede hacer a mano:

   ```sh
   git fetch origin main
   SNAP=$(git commit-tree 'main^{tree}' -p origin/main -m 'telar 0.15.0')
   git push origin "${SNAP}:refs/heads/main"     # en zsh, con llaves: $SNAP:r se come la r
   git tag -a v0.15.0 "$SNAP" -m 'telar 0.15.0'
   git push origin v0.15.0
   ```

4. El workflow construye, corre `twine check`, publica en PyPI (previa confirmación, si el
   entorno tiene revisor) y adjunta el paquete a la Release.
5. Comprobar que se puede instalar de verdad, en una máquina que no sea la de desarrollo:

   ```sh
   uv tool install 'telar[serve,bus]' && telar --version && telar instalar --seco
   ```

Dos cosas cuidan que main no se escape por error. La rama main local no sigue a `origin/main` (`git branch
--unset-upstream main`), así que `telar commit` no integra ni sube a GitHub. Y el gancho `scripts/pre-push`, copiado a
`.git/hooks/pre-push` (los ganchos no viajan con el repositorio: `scripts/publicar.sh` lo instala si falta), niega
subir a GitHub algo que no sea un solo commit encima de `origin/main`, una etiqueta sobre un commit que no esté allá,
otra rama o un borrado. Saltárselo es `git push --no-verify`, solo sabiendo por qué. En un clon nuevo hay que repetir
las dos: `git branch --unset-upstream main` y `cp scripts/pre-push .git/hooks/pre-push`.

## Lo que se verificó a mano antes de la primera versión

- `uv build` produce sdist y wheel; `twine check` pasa las dos.
- El wheel instalado en un venv limpio de Python 3.11 responde `telar --version` y
  `telar --help`.
- El sdist lleva docs/, ejemplo/ y pruebas/ (121 archivos), por MANIFEST.in.
- `vsce package` produce un .vsix de 42 KB con la licencia y el readme adentro.
- Las 579 pruebas pasan en 3.11, 3.12 y 3.13, y en Linux contra un tmux 3.4 de verdad.
