# Fechas: lo que tiene día, venga de donde venga

Estado: **propuesta, nada construido** (28-oct-2026). Decidido: un formato único para una fecha, fuentes
intercambiables con la maquinaria de los proveedores de tareas, mapas en YAML que traducen el formato de cada
documento con patrones de fecha estándar, y que una fecha se edita donde vive, con permisos que sirven también a
otros módulos. Por decidir: la pregunta del final.

## Por qué

Un proyecto tiene fechas en muchas partes: la tabla de cronograma de su documento, un calendario compartido
con otros proyectos (las sesiones de varios cursos en un solo archivo), los hitos de un sistema de gestión, el
cierre esperado de un negocio en el CRM, las tareas que vencen. Hoy cada herramienta que quiere dibujarlas (un
Gantt, el calendario, «ahora») tendría que saber dónde vive cada una y en qué forma, y eso la amarra a la manera
de ordenarse de un equipo.

La idea es separar **la forma de una fecha**, que es una sola, de **dónde salen**, que son varias y se
cambian. Es lo mismo que telar ya hace con las tareas: un proveedor es cualquier cosa que entregue filas con el
contrato, y quien las muestra no sabe de dónde vinieron.

## El formato: una fecha

Un objeto JSON por cosa con día, venga de donde venga:

```json
{
  "id": "faro-entrega-2",
  "titulo": "Segunda entrega del giro",
  "inicio": "2026-11-17", "fin": "2026-11-28", "hora": "",
  "clase": "actividad",
  "proyecto": "proyectos/faro",
  "estado": "en-curso",
  "responsable": "Ana Pérez",
  "depende": ["faro-entrega-1"],
  "fuente": "proyectos/faro/README.md:58",
  "enlace": ""
}
```

| Campo | Qué es |
|---|---|
| `id` | estable dentro de su fuente. Una fila de un documento sin id propio se nombra por su lugar (`<archivo>:<n>`), como una casilla en `telar pendiente`: sirve para el minuto siguiente, no para guardarla |
| `titulo` | lo que se muestra |
| `inicio`, `fin` | `AAAA-MM-DD`. Un día solo va con `inicio` = `fin` (o sin `fin`) |
| `hora` | `HH:MM`, o `""`: lo que ocupa una hora del día es un evento de la agenda, no una fecha de esta lista |
| `clase` | qué es: `actividad` (dura días: una barra), `hito` (un día que marca algo), `sesion` (un día con gente: una clase, un taller), `entrega`, `evento`, `tarea` (vence ese día) |
| `proyecto` | la carpeta de la unidad, la misma que trae una tarea (`docs/contratos.md`, `pendiente`). Si falta, la unidad más honda que contiene la `fuente` |
| `estado` | `pendiente`, `en-curso`, `hecho` o `cancelado` |
| `responsable` | quién, o `""` |
| `depende` | ids de otras fechas de la misma fuente |
| `fuente` | dónde se cambia: `archivo:línea`, o algo como `pmo:98` para lo que vive afuera. La página la abre; un agente sabe qué tocar |
| `enlace` | opcional: dónde verla afuera |
| `editable` | los campos que su fuente sabe escribir (`["inicio", "fin", "estado"]`); `[]`, de solo lectura. Lo pone telar, no quien la escribe (ver «Editarlas donde viven») |
| `version` | para no pisar un cambio ajeno: un cambio que la trae se hace solo si la fecha no cambió desde que se leyó |

Las clases dicen cómo se dibuja cada cosa sin saber de qué equipo es: una actividad es una barra, un hito una
bandera, una sesión o un evento una marca de un día. Los campos calzan uno a uno con iCalendar (`DTSTART`,
`DTEND`, `SUMMARY`, `STATUS`, `RELATED-TO`): exportar las de un proyecto como `.ics` sale casi gratis.

## Las fuentes

### Documentos: secciones que son cronogramas, sin código

Una sección es un cronograma cuando su tabla tiene fechas por columna. Se lee por el **nombre** de cada columna,
no por su lugar: Actividad (o Nombre, Tarea, Hito, Sesión), Inicio y Fin (o Fecha, Desde, Hasta), Responsable,
Depende de, Estado (en palabras o con ✅ 🔄 ⬜), Clase. Las fechas, en las formas que ya entiende el proveedor
`documento` (`AAAA-MM-DD`, `DD-MM-AAAA`, `DD-mes`).

Qué secciones lo son se dice en dos lugares:

- **En el perfil**, para los documentos de las unidades: una sección de tipo `fechas`, como las de tipo `tabla` o
  `casillas` ([perfil.md](../perfil.md#secciones)). Sin declararla, `## Cronograma` lo es.

  ```yaml
  arquetipos:
    proyecto:
      secciones:
        cronograma: { tipo: fechas, encabezado: '^##\s+(Cronograma|Calendario)' }
  ```

- **En el frontmatter**, para un documento que no es una unidad (un calendario compartido) o que quiere nombrar
  las suyas:

  ```yaml
  ---
  fechas: ["## Sesiones", "## Hitos del año"]
  ---
  ```

  Esos documentos se le nombran al proveedor (`rutas`, abajo). Declararlo evita lo falso: muchas tablas con una
  columna «Fecha» son bitácoras o minutas, no planes.

**De qué proyecto es cada fila.** De la unidad a la que apunta un enlace de la propia fila (`[Faro](../faro/README.md)`);
si no tiene, de la columna `Proyecto` si la hay; si no, de la unidad que contiene el documento. Así un calendario
compartido se reparte solo entre sus proyectos, sin columna nueva, porque sus filas ya enlazan al proyecto.

### Mapas: el formato de cada documento, traducido

El formato de una fecha es a dónde se llega, no lo que se le exige a cada documento. Un **mapa** dice cómo se
traduce lo que trae una fuente: un calendario con sus propios nombres de columna, sus fechas sin año, su
vocabulario de estados, un proyecto nombrado por un número. Sin mapa valen los nombres de arriba.

```yaml
# .telar/fechas.yaml del repositorio: los mapas con nombre, del equipo
mapas:
  sesiones:
    secciones: '^##\s+\w+$'            # cada mes (## Junio, ## Julio…)
    clase: sesion                       # una constante: todas las filas son sesiones
    campos:
      inicio:      { columna: Fecha, formato: "EEE d-MMM", idioma: es, año: frontmatter }
      hora:        { columna: Hora, formato: "HH:mm", rango: "–" }
      titulo:      "{Cliente} · {Programa} · {Sesión}"
      responsable: { columna: Relator }
      estado:      { columna: Estado, valores: { dictada: hecho, confirmada: pendiente } }
      proyecto:    { columna: Proyecto, buscar: codigo }   # 70 → la unidad cuyo frontmatter dice codigo: 70
```

| Hace falta | El mapa lo dice con |
|---|---|
| columnas con otro nombre | `columna:` en cada campo |
| un campo hecho de varias columnas | una plantilla: `"{Cliente} · {Programa}"` |
| valores del vocabulario propio | `valores:` en el campo (dictada → hecho, ✔ → hecho) |
| fechas en otra forma | `formato:` con un patrón estándar (abajo), `idioma:`, `rango:` si la celda trae inicio y fin; `año:` cuando no lo traen (un número, o `frontmatter`: el del documento) |
| algo igual en todas las filas | una constante (`clase: sesion`) |
| un proyecto nombrado por un código | `buscar: <clave del frontmatter>`: la unidad que dice ese valor |
| listas en vez de tablas | `patron:` con grupos con nombre: `'^- (?P<inicio>\d+-\w+): (?P<titulo>.+?)(?: \((?P<responsable>.+)\))?$'` |
| archivos YAML, JSON o CSV | `filas:` con un camino (`proyectos[*].hitos[*]`) y los mismos `campos` |

**Los patrones de fecha son los de Unicode** (LDML, el estándar de CLDR, el mismo de ICU, Java y `Intl` del
navegador, y el que usa CSV on the Web del W3C para el mismo problema): `d-MMM` es «17-nov», `EEE d-MMM` «mar
17-nov», `dd/MM/yyyy` «17/11/2026», `HH:mm` «14:00». No hay un lenguaje propio de telar para fechas. Los nombres
de meses y días salen de los datos de CLDR del idioma (con Babel, en Python): «mié», «sept» y sus variantes sin
inventar tablas. El mismo patrón sirve en las dos direcciones: para leer la celda y para escribirla de vuelta
(«mar 17-nov», con el día de la semana recalculado), que es lo que hace editable una fecha.

- **`rango:`** parte una celda que trae dos («10:00–12:00», «17–28 nov») y lee cada lado con el patrón; lo que le
  falta a uno (el mes de «17») lo toma del otro.
- **`formato: auto`** lee lo que venga con un intérprete tolerante (dateparser): sirve para un documento escrito
  a mano sin forma fija. Una fecha leída así es de solo lectura, porque no hay patrón con qué escribirla, y
  `telar fechas probar` dice cuántas filas leyó a ojo.
- Para afuera, telar escribe ISO 8601: `AAAA-MM-DD` y, si hace falta un intervalo en una sola cadena,
  `2026-11-17/2026-11-28`.

**Dónde se declara**, de más a menos precedencia: en el frontmatter del documento
(`fechas: { secciones: "## Sesiones", mapa: sesiones }`, o el mapa entero ahí); en el perfil, por arquetipo
(todos los `proyecto` leen su `## Cronograma` con tal mapa); en `.telar/fechas.yaml`, los mapas con nombre que
viajan con el repositorio, como el perfil; y por defecto, sin mapa. Lo que no cabe en una declaración (lógica,
cálculos, una API) sigue siendo un comando.

**Un mapa se prueba.** `telar fechas probar <archivo>` muestra qué filas leyó y cuáles saltó y por qué («fila 37:
"jue 18-jun" no calza con `D-mmm`», «fila 52: ninguna unidad dice codigo: 140»). Un mapa que pierde filas en
silencio es peor que no tenerlo; `telar doctor` avisa del documento cuyo mapa pierde muchas.

### Comandos: lo que no es un documento

Un programa que imprime fechas con el formato, una por línea en JSON. Es la salida para un sistema de gestión
(sus hitos y las fechas de cada proyecto), un CRM (el cierre esperado), una planilla. Se declara como cualquier
proveedor, o lo trae un módulo en su `modulo.toml`:

```toml
[proveedores.fechas]
tipo  = "markdown"
rutas = ["equipo/calendario-cursos.md"]     # además de los documentos de las unidades

[proveedores.gestion]
como    = "fechas"
tipo    = "comando"
comando = ["bin/fechas-de-la-gestion"]
```

### Lo que telar ya tiene con día

Las tareas con `vence` entran como `clase: "tarea"` y los eventos del calendario como `evento`, sin declarar
nada: son la misma corriente.

## Editarlas donde viven

Una fecha se cambia desde donde se ve (arrastrar una barra del Gantt, estirarla, marcar un hito cumplido) y el
cambio va **a su fuente**: la fila del documento, el sistema del que vino. No hay una copia de telar que después
haya que reconciliar. Es lo que ya hacen las tareas: `telar pendiente <ref> --hecho` cambia una línea de un
documento, y la acción con `rol: fecha` de un proveedor le pasa la fecha nueva a su comando.

**Qué se puede cambiar lo dice cada fecha**: `editable`, la lista de campos que su fuente sabe escribir
(`["inicio", "fin", "estado"]`), y `version`, para no pisar un cambio ajeno. Quien dibuja no adivina: una barra
sin `inicio` en `editable` no se arrastra, y su globo dice dónde se cambia.

**Documentos.** Un campo es editable si su mapa lo lee de una sola columna (`columna:`, con su `formato` y sus
`valores`, que se leen al revés): telar escribe esa celda en el formato de la columna («mar 17-nov», con el día de
la semana recalculado) y ninguna otra cosa de la fila ni del documento. Lo que sale de una plantilla o de
`buscar` es de solo lectura. La primera vez que escribe una fila le pone un id al final
(`<!-- id: f-1a2b3c -->`), como a una casilla, para encontrarla aunque el documento cambie. Si la fila cambió
desde que se leyó, un 409 y nada escrito. El cambio queda sin commitear, a la vista en git.

**Comandos.** La fuente declara cómo escribe: `escribir = ["bin/fechas", "mover"]` recibe por la entrada
`{"id", "version", "inicio", "fin", …}` con solo lo que cambia, y responde con la fecha como quedó o con un error
y su código. Sin `escribir`, la fuente es de solo lectura. Una fuente puede serlo a propósito, porque su sistema
tiene su propio flujo de cambios y aprobación: entonces `editable` va vacío y el globo dice dónde se cambia.

**Las tareas** se mueven con la acción de `rol: fecha` que ya tienen. **Los eventos** del calendario, de solo
lectura por ahora.

**La orden** es `telar fecha <id> [--inicio …] [--fin …] [--estado …] [--version V] --json`, con su ruta en la API
y en el bus. **Desde un lienzo**, que no tiene red: pide el cambio a la página (`window.lienzo.pedir("fecha",
{…})`, como ya pide guardar su memoria), y la página lo hace solo si el módulo lo declaró en sus permisos
(`ordenes = ["fecha"]`) y la persona lo aceptó la primera vez. `pedir` no es de las fechas: es la puerta general
de un lienzo a las órdenes de telar, y cada orden que pase por ella se declara y se acepta igual. Cómo se pide,
se acepta, se recuerda y se revoca un permiso es de [permisos.md](permisos.md), que tiene que crecer para esto: un
módulo pedirá más cosas después. En el Gantt:

- arrastrar una barra mueve su inicio y su fin; estirar un borde cambia solo uno; arrastrar un hito lo mueve;
- lo que depende de ella no se mueve solo: con ⇧ se arrastra con todo lo que depende, a la vista antes de soltar;
- al soltar, el cambio se escribe y aparece «movido · deshacer» unos segundos; si la fuente lo rechaza (un 409, una
  fuente de solo lectura), la barra vuelve a su lugar con el porqué en el globo.

## Quién las usa

`telar fechas [--proyecto <ruta>] [--desde AAAA-MM-DD] [--hasta AAAA-MM-DD] --json` junta todas las fuentes,
como `telar pendientes` junta las tareas:

```json
{ "fechas": [ { "id": "…", "titulo": "…", "inicio": "…", "clase": "…", "proyecto": "…", "fuente": "…" } ],
  "fallas": ["gestion: no contestó en 10 s"] }
```

Una fuente que falla se dice en `fallas` y las demás llegan igual. Lo usan:

- **Un Gantt** que no sabe de nadie: dibuja `telar fechas` agrupado por `telar proyectos`, con los colores de las
  áreas del perfil. Puede ser un módulo general de telar; un equipo solo aporta sus fuentes.
- **El calendario y «ahora»**: ven los hitos y las sesiones, no solo las reuniones.
- **Los agentes**: las fechas de un proyecto con `telar fechas --proyecto`, sin saber en qué archivo o sistema
  está cada una.
- **La ficha** de un documento: su campo `hitos` sale de aquí en vez de buscar fechas en los campos.

## Los pasos

Cada uno deja todo funcionando.

1. **El contrato y `telar fechas` con documentos.** El formato en `docs/contratos.md`, el tipo de sección
   `fechas` en el perfil con `## Cronograma` por defecto, y la orden con la API (`GET /fechas`) y el bus. Lo
   que hoy lee un Gantt por su cuenta pasa a leerlo telar.
2. **Los mapas**: el frontmatter `fechas:`, `.telar/fechas.yaml`, el proyecto por enlace o por `buscar`, `rutas`
   en el proveedor y `telar fechas probar`. Un calendario compartido con su propio formato reparte sus filas entre
   los proyectos.
3. **Las fuentes por comando**, también desde un módulo (`[fechas]` en `modulo.toml`), y las tareas y los eventos
   en la misma corriente.
4. **El Gantt como módulo general**, sobre `telar fechas`: lo propio de cada equipo queda en sus fuentes.
5. **Editar:** `telar fecha` escribe en documentos (la celda, el id de la fila, el 409) y en comandos con
   `escribir`; `window.lienzo.pedir` con su permiso; arrastrar y estirar en el Gantt, con deshacer.
6. **Lo demás, uno a uno:** el calendario y «ahora» con hitos y sesiones; exportar un proyecto como `.ics`;
   arrastrar con lo que depende.

## Por decidir

1. **Si un documento tiene que decir cuáles de sus tablas son cronogramas.** Un README puede tener una tabla
   `## Cronograma` (el plan) y otra `## Bitácora` con una columna «Fecha» (lo que pasó). Si telar leyera toda
   tabla con fechas, la bitácora aparecería en el Gantt como si fueran actividades. Recomendado: que lo diga el
   mismo mapa que lo traduce (sus `secciones:`), con `## Cronograma` leída por defecto, y nada más; así no hay
   una segunda manera de marcarlo.
