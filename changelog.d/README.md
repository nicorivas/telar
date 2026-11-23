# changelog.d

Las entradas del CHANGELOG que todavía no llegan a `CHANGELOG.md`: una por rama, en `changelog.d/<rama>.md`. Las
escribe el hijo que trabaja en esa rama, y `telar hilo fusionar` las pasa a la sección que dicen de `[Unreleased]` y
borra el archivo, en el mismo commit de la fusión. Así dos ramas nunca chocan en el CHANGELOG. Lo declara
`.telar/changelog.yaml`; el porqué y el detalle, en `docs/desarrollar.md`, «El CHANGELOG, por fragmentos».

Un fragmento es un pedazo del CHANGELOG tal cual, en inglés como él, con una o más secciones (Added, Changed,
Deprecated, Removed, Fixed, Security):

```markdown
### Added

- **The first sentence, in bold.** The rest of the entry, with lines of at most 120 characters and the following
  lines indented two spaces.
```

Antes de tocar `main`, `telar hilo fusionar` revisa cada fragmento y se niega si alguno está mal formado (una sección
que no existe, una línea de más de 120, una entrada sin su primera oración en negrita, texto antes de la primera
sección), con el archivo y la línea de cada problema. Este README no es un fragmento.
