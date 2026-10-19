# Los tipos: un esquema sobre archivos de texto

Propuesta, 19-oct-2026. Estado: **en construcción**: el tipo `tarea` y sus dos formatos ya leen y
escriben (ver «Lo hecho», al final). Es el paso 2 de
[primitivas.md](primitivas.md) («direcciones y objetos») hecho concreto.

## Por qué

Los archivos markdown del repositorio son, de hecho, la base de datos de telar: las tareas son archivos
con frontmatter, los pendientes de un proyecto son casillas en su README, el estado de un proyecto es una
sección de su documento. Hoy cada uno se lee y se escribe con código propio, sin un contrato común:

- la CLI de tareas del repo de vida lee y escribe sus archivos a su manera;
- un adaptador (`telar-tareas`) los traduce al JSON que telar espera de un proveedor;
- el proveedor `markdown` de telar lee las casillas de los README con sus propias expresiones regulares, y
  marcar una como hecha es otro camino más;
- `telar hoy` vuelve a leer y a interpretar todos esos archivos en cada pedido (536 pendientes; 0,8 s
  solo en decidir a qué hilo va cada uno).

La idea: **cada tipo de objeto declara su forma, sus acciones y cómo se escribe en cada clase de texto**.
Los archivos siguen siendo la única verdad, legibles y editables a mano; telar los lee y los cambia con
el mismo cuidado con que los cambiaría una persona.

## Lo que ya existe, y qué se toma

| referencia | qué hace | qué se toma |
|---|---|---|
| **Augeas**, **Boomerang** | editan archivos de configuración con *lentes*: un par de funciones que leen el texto a una estructura y devuelven la estructura editada al texto **sin tocar lo demás** (comentarios, espacios, orden) | el principio, y la prueba de ida y vuelta |
| **Keystatic**, **TinaCMS**, **Decap CMS** | CMS sobre git: un esquema por colección, y el editor escribe en los `.md` del repositorio y commitea | el esquema por tipo sobre archivos de un repo |
| **Obsidian Bases**, **Dataview**, **Obsidian Tasks** | vistas de base de datos sobre las propiedades de las notas; un formato de tarea en una línea | las vistas y el formato de línea |
| **Backlog.md** | tareas como archivos `.md` con frontmatter, CLI y tablero, pensado para agentes | la confirmación de que esto sirve tal cual |
| **MarkdownDB**, la caché de Obsidian, el índice de git | un índice derivado de los archivos, que se puede borrar y reconstruir | el índice en memoria |
| **ruamel.yaml** | YAML de ida y vuelta: cambia un valor y conserva orden y comentarios | nada, al final: el frontmatter de las tareas no es YAML (ver «Lo hecho») |

**Augeas como referencia, no como librería.** Es una librería en C con un lenguaje propio para escribir
lentes, difícil de escribir y depurar, sin lentes para markdown ni frontmatter, y pensada para la
configuración del sistema. Se toma el principio y se implementa en Python con lo estándar: un motor chico
para formatos de línea, y lentes en código para los formatos con estructura.

## Las piezas de un tipo

Un tipo tiene tres partes, y ninguna sabe de las otras más de lo necesario:

1. **El modelo** (Pydantic): sus campos y sus tipos. De él salen el JSON Schema, el contrato de la API y
   los tipos del panel.
2. **Las acciones**: funciones sobre el modelo, sin texto. Cada una tiene una precondición y un efecto, y
   anota un cambio.
3. **Los formatos** (las lentes): cómo se lee y se escribe el modelo en una clase de texto. Un tipo puede
   tener varios.

La acción cambia el modelo; el formato traduce ese cambio a la edición mínima del texto.

### El modelo de una tarea

```python
class Tarea(BaseModel):            # telar/tipos/tarea.py
    id: str                         # T84
    titulo: str
    estado: str = "activa"          # activa, espera, algun-dia, hecha, caduca, descartada
    en_curso: bool = False          # una casilla [>]
    prioridad: int = 2              # 0 la más alta
    vence: str = ""                 # AAAA-MM-DD
    espera: str = ""                # a quién le toca ahora (solo mientras espera)
    dueno: str = ""                 # "" es la persona dueña del repositorio
    proyecto, area, origen, trabajo, avance: str
    etiquetas: list[str] = []
    creada: str = ""
    cerrada: str = ""               # solo mientras está cerrada
    contexto: str = ""              # el texto libre
    conexiones: list[str] = []
    historia: list[Cambio] = []     # lo que le pasó, una línea por acción
```

### Las acciones

| acción | precondición | efecto |
|---|---|---|
| `completar` | no está cerrada | `estado = hecha`, `cerrada = hoy` |
| `reabrir` | está cerrada | `estado = activa`, `cerrada = None` |
| `reagendar(fecha)` | no está cerrada | `vence = fecha` |
| `asignar(persona)` | — | `dueno = persona` |
| `esperar(a quién)` | no está cerrada | `estado = espera`, `espera = …` |
| `anotar(texto)` | — | una línea más en la historia |

Toda acción agrega a `historia` una línea con la fecha, qué fue y quién la pidió: es el «cambio» de las
primitivas, ya escrito en el archivo (las tareas de hoy ya tienen esa sección).

### Los formatos

**El archivo propio** (la CLI de tareas de hoy): líneas `clave: valor` entre `---` (no es YAML), el contexto, y la historia como sección.

```diff
 ---
 titulo: Medir el alcance real
-estado: activa
+estado: hecha
 prioridad: 2
 vence: 2026-06-30
+cerrada: 2026-10-19
 ---
 Medir el alcance real del giro…

 ## Historia
 - 2026-06-23 [creada] a mano
+- 2026-10-19 09:40 [hecha] desde el panel
```

**La casilla** de un README:

```diff
-- [ ] Medir el alcance  vence:2026-06-30  !alta  #faro  <!-- id: T84 -->
+- [x] Medir el alcance  vence:2026-06-30  !alta  #faro @hecha(2026-10-19) <!-- id: T84 -->
```

**todo.txt**, si alguien lo usa:

```diff
-(A) Medir el alcance due:2026-06-30 +faro
+x 2026-10-19 (A) Medir el alcance due:2026-06-30 +faro
```

Una sola acción; cada formato sabe dónde van `estado` y `cerrada`, y lo demás queda byte por byte.

### Cómo se define un formato

Un formato parte el texto en **piezas con posición** y dice de qué campo es cada una. Leer devuelve el
objeto y dónde está cada campo; escribir recibe los campos que cambiaron y reescribe solo sus piezas (un
campo que no estaba se agrega en su lugar definido).

- **Formatos de línea** (la casilla, todo.txt): declarativos, en el módulo del tipo o en el perfil del
  repositorio. (La casilla, por ahora, está escrita en código —`FormatoCasilla`— con sus dos dialectos;
  pasarla a esta declaración es el paso siguiente cuando haya un segundo formato de línea.)

  ```toml
  [tipos.tarea.formatos.casilla]
  linea = '- [{marca}] {texto}{fichas}<!-- id: {id} -->'

  [tipos.tarea.formatos.casilla.campos]
  estado    = { pieza = "marca", valores = { activa = " ", en_curso = ">", hecha = "x" } }
  vence     = { ficha = "vence:{fecha}" }
  cerrada   = { ficha = "hecha:{fecha}" }
  prioridad = { ficha = "!{valor}" }
  etiquetas = { ficha = "#{valor}", lista = true }
  dueno     = { ficha = "@{valor}" }
  ```

- **Formatos con estructura** (el archivo propio): en código, con dos funciones (`leer`, `escribir`).
  Las claves son configurables: un repositorio en inglés puede decir `status` y `due` donde este dice
  `estado` y `vence`. (El frontmatter de las tareas resultó no ser YAML: son líneas `clave: valor`, y un
  título lleva «:» sin comillas. Una lente por líneas es más simple que YAML de ida y vuelta, y da la
  edición mínima sin librería.)

## Las reglas

1. **Las acciones solo tocan el modelo.** Nunca escriben texto: por eso la misma acción sirve para un
   archivo, una casilla o una línea de todo.txt, y se prueba sin archivos.
2. **Un formato reescribe solo lo que cambió.** Lo que no reconoce (una palabra que la persona agregó, un
   comentario) queda como estaba.
3. **Ida y vuelta.** Leer un archivo y escribirlo sin cambios da los mismos bytes; cambiar un campo y
   releerlo da el valor nuevo. Es la prueba de las lentes, y se corre contra todos los archivos reales.
4. **Leer con tolerancia, escribir con rigor.** Un archivo que no calza con el esquema se lee y se avisa,
   no se descarta: lo editan personas. Lo que telar escribe siempre calza.
5. **Un formato declara lo que no puede guardar.** Una casilla no tiene dónde poner un cuerpo largo; una
   acción que lo necesita lo dice en vez de perderlo.

## El índice

Los archivos son la única verdad; el índice es una copia derivada para consultar rápido («lo que vence
esta semana, por dueño»), y **nadie escribe en él**:

- vive **en la memoria** de `telar serve`: al arrancar lee todos los archivos (las 309 tareas, en menos de
  un segundo); si el proceso se reinicia, lo vuelve a armar;
- se mantiene al día por la fecha de cada archivo (mirar 309 fechas toma milisegundos) y con un vigilante
  del sistema de archivos para que sea inmediato, más una revisión completa de vez en cuando;
- una acción escribe el archivo y **después** el índice relee ese archivo: nunca toma del pedido el valor
  que se quiso escribir. Si algo se cae entre los dos pasos, la siguiente revisión lo arregla.

Sin SQLite: a esta escala, la memoria basta y no hay un segundo almacén que cuidar. Si algún día rearmar
tarda demasiado, el índice pasa a SQLite sin cambiar las reglas.

## Los conflictos

No los hay entre el índice y los archivos (el índice, a lo más, está atrasado y se relee). Los hay entre
quienes escriben un mismo archivo: una persona en su editor, un agente, un `git pull` desde la otra
máquina. Se resuelven con lo estándar:

- **Un solo escritor** para lo que se escribe por telar: la API del servidor. Dos pedidos a la vez se
  ponen en fila.
- **Concurrencia optimista.** Cada objeto tiene una versión (la huella de su archivo). Quien lee una tarea
  recibe su versión, y la devuelve con la acción («completa T84, que leí en la versión X»). Si el archivo
  cambió desde entonces, la acción se rechaza, y quien la pidió relee y decide. Es el `ETag`/`If-Match` de
  HTTP: nadie pisa sin saberlo el cambio de otro.
- **Ediciones mínimas.** Una acción toca solo la línea o el campo que cambia: si alguien editó otra parte
  del mismo archivo, su cambio sobrevive, y git puede juntar los dos sin conflicto.
- **Entre máquinas, git.** Lo que trae un `pull` se relee como cualquier edición; un conflicto de git se
  resuelve en git, como hoy, y el índice relee el resultado. El escritor único termina con los números de
  tarea repetidos: el número nuevo lo da él.

## Dónde vive cada cosa

- **El núcleo de telar**: el motor de tipos (modelo, acciones, formatos, índice, versiones) y el tipo
  `tarea` con sus formatos de fábrica, genérico: nada de un repositorio en particular.
- **El perfil del repositorio o un módulo**: qué formato usa cada lugar (las tareas en
  `proyectos/tareas/*.md`, las casillas en los README de las unidades) y las claves de sus campos.
- **Lo propio de una vida** (cómo se procesa un correo, qué hace un agente con una tarea): sigue en sus
  skills, que pasan a usar las acciones del tipo en vez de editar archivos.

Con esto, quien instala telar conecta su sistema de tareas declarando un formato, no escribiendo un
programa: el «puente» de [arquitectura.md](../arquitectura.md) queda para lo que no es texto (una API, una
base de datos).

## Los pasos

1. **El tipo `tarea`, solo leer.** El modelo y los dos formatos de hoy (el archivo propio y la casilla).
   La prueba de ida y vuelta contra **todas** las tareas reales: cada archivo leído y escrito sin cambios
   da los mismos bytes.
2. **Las acciones y la escritura.** `completar`, `reabrir`, `reagendar`, `asignar`, `esperar`, `anotar`,
   con su línea en la historia; los formatos traducen cada cambio a la edición mínima; las versiones.
   Probado sobre copias de los archivos, no sobre los reales.
3. **El índice en `telar serve`**: las tareas desde la memoria, `/tareas` sale del índice, y el servidor
   es el único que escribe. Deja de hacer falta leerlas por el bus (1,5 s de `hoy`).
4. **El cambio.** telar lee las tareas de forma nativa y se retira el adaptador; la CLI de tareas del repo
   de vida pasa a ser una cáscara del tipo (las skills que la usan siguen funcionando), y se retira cuando
   convenga.

## Lo que queda abierto

- **Las casillas sin identificador.** Un pendiente de un README que nunca tuvo `<!-- id: … -->` se
  reconoce por su texto, que cambia. Al escribirlo la primera vez, ¿se le pone un id?
- **Las migraciones.** Cuando el modelo cambie, ¿un campo `version` en cada archivo, o un lector que
  entienda las dos formas?
- ~~**La dependencia.**~~ No hizo falta `ruamel.yaml`: el frontmatter de las tareas son líneas
  `clave: valor`, no YAML.

## Lo hecho (19-oct-2026)

**Paso 1, y la mitad del 2**: `telar/tipos/` con el tipo `tarea` y sus dos lentes, que ya leen y escriben.

- **El archivo propio** (`FormatoArchivo`): líneas `clave: valor` en su orden, el contexto, `## Conexiones`
  y `## Historia`. Verificado contra las 308 tareas reales:
  - leer da lo mismo que la CLI de tareas, campo por campo, en las 308;
  - escribir sin cambios da los mismos bytes;
  - siete cambios por tarea (completar, reagendar, asignar, etiquetas, contexto, conexiones, quitar un
    campo): 2.156 ediciones, todas releídas con el valor nuevo por las dos lecturas (esta y la de la CLI),
    y cada una tocando solo sus líneas.
- **La casilla** (`FormatoCasilla`): lee los dos dialectos (`@owner(…)`, `@deadline(…)`, `@prioridad(…)`,
  «@Nombre:» al comienzo; y `vence:`, `!alta`, `#etiqueta`) y escribe en el de la línea, o como
  `@clave(valor)` antes del identificador. La fecha de cierre es `@hecha(AAAA-MM-DD)`. Verificado contra
  las 4.868 casillas de los documentos: la misma lectura que `telar.lectura` (dueño, fecha, estado), y
  34.076 cambios releídos con el valor nuevo sin tocar otro campo.
- **Las reglas que salieron de los datos**: a quién se espera vale solo mientras la tarea espera; la fecha
  de cierre, solo mientras está cerrada (las dos como la CLI de tareas); una fecha que no es fecha («@vence(YYYY-MM-DD)»,
  una plantilla) no se lee como fecha; una casilla no guarda cuerpo, conexiones ni de dónde salió, y
  cambiarlos es un error; la historia tampoco, y eso está declarado.

**Paso 2: las acciones, las versiones y la escritura** (`telar/tipos/tarea.py`, `telar/tipos/carpeta.py`).

- **Las acciones**: `completar`, `cerrar` (hecha, caduca o descartada), `reabrir`, `algun_dia`, `esperar`,
  `reagendar` (fecha o `+Nd`), `asignar`, `anotar`, `proponer` (lo que deja un agente para decidir),
  `responder` y `editar`. Funciones sobre el modelo, sin texto, cada una con su precondición y su línea en
  la historia. Son las transiciones de la CLI de tareas, con dos diferencias a propósito: cerrar lo cerrado
  o reabrir lo abierto es un error (un doble clic repetía la historia), y asignar o editar dejan su línea.
- **La carpeta** (`Carpeta`): lee una tarea con su versión (la huella del archivo) y le aplica una acción.
  Con una versión vieja, la acción se rechaza (`ErrorDeVersion`); un escritor a la vez (un candado de la
  carpeta); la escritura es atómica; y lo escrito tiene que releerse igual a lo que se quiso escribir, o no
  se escribe. Un identificador es un nombre de archivo, nunca una ruta.
- **Comparado con la CLI de tareas**, sobre copias de las 308 tareas y a la misma hora: nueve acciones,
  1.903 aplicaciones; 1.887 dejan **el mismo archivo, byte por byte**. Las 16 restantes son dos tareas con
  la historia ya dañada (líneas `-  [nota] [nota] [nota]…` con una copia de su propio frontmatter): la CLI
  reescribe el archivo entero y le agrega otro `[nota]` a cada línea en cada guardado; el tipo agrega su
  línea y deja las viejas como están. La red de seguridad («lo escrito tiene que releerse igual») atajó
  además un caso que la comparación no habría visto: pasar a «algún día» una tarea que esperaba a alguien
  dejaba a quién se esperaba en el modelo; ahora se borra, como termina haciéndolo la CLI.

**Paso 3: el índice** (`telar/tipos/indice.py`) y sus rutas en `telar serve`.

- **El índice** tiene los objetos en memoria y se mantiene al día por la fecha y el tamaño de cada archivo:
  antes de cada consulta relee solo lo que cambió y saca lo que ya no está. Nadie escribe en él: una acción
  escribe el archivo y después el índice lo relee. Un archivo roto queda en `fallas`, sin llevarse a los
  demás. Medido con las 308 tareas reales: se arma en 66 ms; mirar si algo cambió, 1 ms; consultar las 93
  abiertas, 1 ms.
- **`[tipos.tarea] carpeta`** dice dónde viven, en la máquina que las tiene.
- **Las rutas**: `GET /tipos/tarea` (filtros: abiertas, área, proyecto, dueño, vence hasta), `GET
  /tipos/tarea/{id}` (con su versión) y `POST /tipos/tarea/{id}/{acción}` con `{params, version}`. Una
  versión vieja es un 409 con la versión de ahora; una acción que no se puede, 409 con su motivo; una que no
  existe o parámetros que no calzan, 422. Solo ese proceso escribe.

**Paso 4, el cambio, en tres partes.**

1. **Leer** (hecha): un proveedor `tipo = "tipo"` da las tareas a `telar hoy` y al panel desde el índice
   del proceso (el mismo de la API), con la forma de siempre. Comparado con el adaptador `telar-tareas`
   sobre las mismas tareas: las 88 activas, idénticas campo por campo, en 2 ms en vez de 71 ms (más el
   viaje por el bus). Desde el laptop, `en = "telar"` las pide al servidor con el reenvío de proveedores
   que ya existe: allá las lee el índice del nodo.
2. **La ficha y sus acciones** (hecha): sin `detalle`, el proveedor del tipo arma la ficha y sus botones
   son acciones del tipo (`accion` y `params`, con `{texto}`), que el servicio corre sobre el archivo con
   la versión que mostraba la ficha; después commitea y sube ese archivo en un proceso aparte (como hacía la
   CLI de tareas), y lleva el mensaje al hilo si el botón lo tiene. Comparada con `telar-tareas --ver` en
   las 308 tareas: título, subtítulo, bloques y el nombre, rol, orden y opciones de cada botón, idénticos.
   Lo propio de una casa (quién propone, a quién se le escribe, los mensajes a los hilos, el equipo, la
   cuenta de Gmail de cada área) son opciones del proveedor. El panel manda la versión de la ficha que
   muestra; si la tarea cambió entretanto, la acción no se hace y la ficha se vuelve a leer.
3. **Crear tareas, y la CLI de tareas como cáscara del tipo**, para que las skills sigan iguales.

