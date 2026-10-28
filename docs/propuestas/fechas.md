# Fechas: lo que tiene día, venga de donde venga

Estado: **casi todo hecho** (0.8.1, 28-oct-2026): `telar fechas` con los cronogramas de los
documentos, los mapas (`.telar/fechas.yaml`), las fuentes por comando y desde un módulo, las tareas; editar donde
viven (`telar fecha`) y `window.lienzo.pedir` con sus concesiones; un Gantt general como módulo aparte
(`telar-gantt`). Falta lo de «Los pasos», abajo.

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
| `clase` | qué es: `actividad` (dura días: una barra), `plazo` (el del proyecto mismo: su barra), `hito` (un día que marca algo), `sesion` (un día con gente: una clase, un taller), `entrega`, `evento`, `tarea` (vence ese día) |
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

Hecho: la sección `## Cronograma` de cada unidad, por el nombre de cada columna, y otros documentos con un proveedor
`markdown` (ver [contratos.md](../contratos.md#telar-fechas---json)). Lo que falta es que una tabla con otros nombres,
otro formato u otras secciones se lea igual: eso es un mapa. **Qué secciones de un documento son cronogramas lo
dice el mapa que lo traduce (`secciones:`), y nada más**: así no hay una segunda manera de marcarlo, y una bitácora
con una columna «Fecha» no aparece en un Gantt como si fuera un plan.

**De qué proyecto es cada fila.** Hoy, de la unidad que contiene el documento. Falta: de la unidad a la que apunta
un enlace de la propia fila (`[Faro](../faro/README.md)`), o de la que diga su columna de proyecto (`buscar:` en el
mapa). Así un calendario compartido se reparte solo entre sus proyectos.

### Mapas: el formato de cada documento, traducido

Hecho: `.telar/fechas.yaml` con mapas por nombre y `documentos:`, el frontmatter `fechas:`, los patrones de fecha de
Unicode en las dos direcciones, `valores`, plantillas, constantes, `rango`, `año`, el proyecto por enlace o por
`buscar`, listas con `patron:` y `telar fechas probar` (ver [perfil.md](../perfil.md#mapas-de-fechas-telarfechasyaml)).
Falta: leer archivos YAML, JSON o CSV (`filas:` con un camino, `proyectos[*].hitos[*]`, y los mismos `campos`), y
`telar doctor` avisando del documento cuyo mapa pierde muchas filas.

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

1. **Publicar el Gantt**: `telar-gantt` en su repositorio y en el catálogo oficial. Un equipo que tenía su propio
   Gantt se queda solo con lo suyo: su fuente (un módulo con `[fechas]`) y sus mapas.
2. **Los eventos del calendario** en la misma corriente (hoy el calendario se pide por día: hace falta pedir un
   intervalo).
3. **Lo demás, uno a uno:** el calendario y «ahora» con hitos y sesiones; exportar un proyecto como `.ics`;
   arrastrar con lo que depende (⇧); escribir el estado de una fila; mapas para archivos YAML, JSON o CSV
   (`filas:`); `telar doctor` avisando del documento cuyo mapa pierde muchas filas; ⚙ módulos mostrando lo
   concedido a cada uno.
