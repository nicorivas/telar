# Publicar una versión

Publicar es apretar un botón: `git tag v0.1.0 && git push --tags`. Todo lo demás lo hace
`.github/workflows/publicar.yml`. Lo que sigue es lo que hay que preparar **una sola vez**,
porque son cuentas y permisos que solo tiene su dueño, y después el runbook de cada versión.

## Lo que hay que hacer una vez

### 1. Decidir el nombre

El paquete se llama `telar` porque el nombre estaba libre en PyPI el 21-sep-2026, no porque
se haya elegido. Antes de la primera publicación conviene confirmarlo: después de subir una
versión, el nombre queda tomado para siempre aunque se borre el archivo. Si se cambia, hay
tres lugares: `name` en pyproject.toml, `name` y `publisher` en vscode/package.json, y el
módulo `src/telar/`.

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

### 3. El Marketplace de VS Code

Este sí necesita un secreto, porque Microsoft no tiene trusted publishing.

1. Crear un publisher en <https://marketplace.visualstudio.com/manage>. Tiene que llamarse
   igual que el campo `publisher` de vscode/package.json (hoy, `nicorivas`).

   **El Marketplace tiene un solo espacio de nombres para todo el catálogo**, y eso
   sorprende viniendo de PyPI o npm: no basta con que `publisher.name` sea único, tienen
   que serlo también `name` y `displayName` por separado, contra todas las extensiones de
   todos los publishers. `telar` estaba tomado en los dos (por `davidbc01.telar`), así que
   la extensión se llama `telar-hilos` y se muestra como «telar — threads of work». El
   `displayName` se puede cambiar publicando otra versión; el `name` no, queda para
   siempre.
2. En Azure DevOps (<https://dev.azure.com>), con la misma cuenta Microsoft: User settings ›
   Personal access tokens › New token, organización **All accessible organizations**,
   alcance **Marketplace › Manage** (que está plegado tras «Show all scopes»). Sale una
   sola vez; copiarlo entonces.

   **Esto tiene fecha de caducidad más allá del token.** La propia página avisa que desde
   el **1-dic-2026** Azure DevOps deja de admitir tokens con alcance «all accessible
   organizations», que es justo el que el Marketplace exige. O sea que este camino se
   rompe solo en diciembre, haga uno lo que haga con la fecha de expiración. Cuando pase,
   hay que mirar qué ofrece Microsoft en reemplazo; mientras tanto, subir el `.vsix` a
   mano desde <https://marketplace.visualstudio.com/manage> no necesita token de ninguna
   clase y toma un minuto.
3. En GitHub › Settings › Secrets and variables › Actions, guardarlo como `VSCE_PAT`.

Sin `VSCE_PAT` el workflow no falla: se saltea ese trabajo y deja el `.vsix` adjunto a la
Release, que se instala con `code --install-extension telar-hilos-0.1.0.vsix`.

Open VSX (el registro que usan VSCodium, Cursor y Gitpod) es un trámite aparte: cuenta con
Eclipse, firmar el Publisher Agreement y un token `OVSX_PAT`. Vale la pena, pero no bloquea.

### 4. Abrir el repositorio

Hoy es privado. `gh repo edit nicorivas/telar --visibility public`. Antes conviene mirar
dos cosas: que no haya quedado nada personal **en el historial**, que también se hace
público (`git log -p --all | grep -inE` por rutas de la máquina, nombres de clientes y
correos que no sean el de quien firma), y que la Homepage de pyproject apunte a donde va a
estar. El árbol limpio no alcanza: lo que se borró en un commit sigue ahí.

## Cada versión

1. Cambiar el número **en los dos lados**: `__version__` en src/telar/\_\_init\_\_.py y
   `version` en vscode/package.json. El primer trabajo del workflow no hace otra cosa que
   comprobar que la etiqueta y esos dos coinciden.
2. Mover lo que corresponda de «Unreleased» a la versión nueva en CHANGELOG.md.
3. Commitear, y recién entonces etiquetar:

   ```sh
   git tag -a v0.1.0 -m "telar 0.1.0"
   git push origin main --follow-tags
   ```

4. El workflow construye, corre `twine check`, empaqueta la extensión, publica en PyPI
   (previa confirmación, si el entorno tiene revisor) y en el Marketplace, y adjunta las
   tres cosas a la Release.
5. Comprobar que se puede instalar de verdad, en una máquina que no sea la de desarrollo:

   ```sh
   pipx install telar && telar --version
   ```

## Lo que se verificó a mano antes de la primera versión

- `uv build` produce sdist y wheel; `twine check` pasa las dos.
- El wheel instalado en un venv limpio de Python 3.11 responde `telar --version` y
  `telar --help`.
- El sdist lleva docs/, ejemplo/ y pruebas/ (121 archivos), por MANIFEST.in.
- `vsce package` produce un .vsix de 42 KB con la licencia y el readme adentro.
- Las 579 pruebas pasan en 3.11, 3.12 y 3.13, y en Linux contra un tmux 3.4 de verdad.
