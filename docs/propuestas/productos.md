# Productos: la lista, su backlog y su tablero

Estado: **pasos 1 a 3 hechos** (29-oct-2026, sin publicar): `telar productos`, el formato de una idea, `.telar/productos.yaml`
(docs/perfil.md) y el módulo `telar-productos` (lista, backlog, tablero; crear y mover). Decidido: las ideas viven en la
carpeta de su producto; los estados de abajo; una pestaña propia; valor y esfuerzo en tres niveles. Paso 4 también (llevar una tarea al backlog, y tareas desde una idea). Queda el tipo general.

## Por qué

En la lista de tareas se mezclan dos cosas. Unas son **operativas**: hay un compromiso, alguien espera y hay un
paso concreto («mandarle al cliente el acta de ayer»). Otras son **ideas sobre lo que se vende**: una
mejora de un servicio, una expansión, algo que un cliente pidió y podría servir a otros («sección de gestión del
cambio en la página de aterrizaje»). Las segundas no tienen compromiso todavía: llenan la lista de por hacer y
quedan lejos del producto al que mejoran.

Es la distinción estándar entre **acciones comprometidas** y **backlog** (GTD la llama «algún día / quizás»; la
gestión de productos, backlog de oportunidades; Kanban, la columna que todavía no entra al flujo). Una idea pasa
por su propio ciclo (se propone, se evalúa, se prioriza, se hace, se lanza o se descarta) y recién cuando se
compromete nace el trabajo operativo.

## Qué es

Un **módulo** (`telar-productos`, repositorio aparte como `telar-gantt`) con una pestaña en el dashboard y tres
vistas:

1. **Productos**: la lista de lo que se vende (en una consultora, los servicios de su catálogo), con su área, tipo,
   vigencia y cuántas ideas y mejoras tiene cada uno en cada estado.
2. **Backlog**: las ideas sin compromiso, de todos los productos o de uno, para ordenarlas por valor y esfuerzo y
   decidir: priorizar o descartar.
3. **Tablero (kanban)**: lo comprometido, en columnas por estado (priorizada → en curso → lanzada). Arrastrar una
   tarjeta le cambia el estado donde vive, como el Gantt cambia una fecha.

Al abrir un producto se ven sus ideas, sus mejoras en curso y las tareas operativas que nacieron de ellas.

## Sobre qué opera: frontmatter y README, declarados

Nada de esto sabe de un equipo en particular: lo que es un producto y dónde viven sus ideas lo declara cada
repositorio, como `.telar/fechas.yaml` declara sus fechas.

**Un producto** es una unidad del perfil (`.telar/perfil.yaml`) de un arquetipo, por ejemplo `servicio`
(`servicios/*/*/`). Sus campos salen del frontmatter de su README o de su tabla de
información, con los mismos selectores que la etiqueta de un arquetipo (`{campo:Tipo}`).

**Una idea o mejora** es un archivo markdown con frontmatter, un archivo por idea, dentro de la carpeta de su
producto (`<producto>/backlog/<id>.md`). Así vive con el producto, en el repositorio del equipo, la ve quien ve el
servicio y la historia queda en git; no en las tareas personales de nadie.

```markdown
---
titulo: Sección de gestión del cambio en la página de aterrizaje
estado: idea          # idea · evaluando · priorizada · en-curso · lanzada · descartada
valor: alto           # alto · medio · bajo
esfuerzo: medio
origen: retro-comercial-2026-10   # de dónde salió: una reunión, un cliente, un correo
responsable: ""
creada: 2026-10-29
---
Lo que se propone y por qué. Abajo, su historia, como en una tarea.
```

Lo declara `.telar/productos.yaml` en la raíz del repositorio:

```yaml
productos:
  arquetipo: servicio            # las unidades del perfil que son productos
  nombre: servicios              # cómo los llama este equipo (el título de la pestaña)
  campos:                        # lo que se muestra de cada uno
    area: "{ruta:1}"             # la carpeta del área, la primera bajo servicios/
    tipo: "{campo:Tipo}"
    vigencia: "{frontmatter:vigencia}"
ideas:
  carpeta: backlog               # dentro de cada producto
  estados: [idea, evaluando, priorizada, en-curso, lanzada, descartada]
  backlog: [idea, evaluando]     # lo que va en el backlog
  tablero: [priorizada, en-curso, lanzada]   # las columnas del kanban
  campos: [valor, esfuerzo, origen, responsable]
```

Otro equipo lo apunta a sus productos de software, a sus cursos o a sus líneas de negocio, con sus estados.

## Cómo se arma, en telar y en el módulo

- **En telar, un tipo declarable** (lo que `[tipos]` ya hace con `tarea`, pero de cualquier carpeta de markdown
  con frontmatter): `telar tipo idea lista|ver|crear|<acción>`, con dirección (`idea:<producto>/<id>`), versión
  para no pisar cambios, y escritura que se commitea. Es la pieza general: después sirve para cualquier otro
  backlog o registro. El menú de una entidad, «Acción…» y `telar objeto` funcionan con ella sin hacer nada.
- **El módulo** solo dibuja: un lienzo que pide `telar productos --json` (la lista y las ideas) y, al arrastrar o
  editar, `window.lienzo.pedir("idea", {…})` con su permiso en `modulo.toml`, como el Gantt pide `fecha`.

## Ideas y tareas

- **De idea a trabajo**: al pasar a `en-curso`, la idea puede abrir tareas operativas con `proyecto` apuntando al
  producto (y `origen: idea:<…>`). Esas sí van a la lista de tareas; la idea las muestra.
- **De tarea a idea**: en el menú de una tarea, «llevar al backlog de un producto» crea la idea con su texto y su
  historia y descarta la tarea. Con eso se hace la limpieza de la lista, tarea por tarea, cuando se decida.
- La lista de tareas no cambia: queda más corta porque las ideas se van a donde corresponden.

## Los pasos

1. ~~El formato y `telar productos`~~, ~~el módulo~~ y ~~editar desde él~~: hechos. El formato de una idea
   (`telar.tipos.registro`) sirve para cualquier registro con frontmatter; falta declararlo como tipo general
   (`[tipos.<nombre>]`), con dirección propia en `telar objeto` y el menú de una entidad.
4. ~~«Llevar al backlog» desde una tarea, y las tareas que nacen de una idea~~: hecho (docs/perfil.md, «Productos»).
5. En el primer repositorio que lo use: su `.telar/productos.yaml`, y la pasada por las tareas activas para mover
   las que son ideas.
