# Códigos: lo que un hilo nombra con un código, a la vista

Estado: **hecho** (6-nov-2026, sin publicar): `telar codigos`, `GET /codigos` y el verbo `codigos` del bus; la hoja
«códigos» de la barra de la derecha; los códigos como enlaces en la terminal, la lectura y la conversación. Decidido:
sin declarar nada (se reconocen las tres formas de definir un código), solo los códigos que salen del archivo donde se
definen, y en la máquina del hilo. Queda lo de «Después, si hace falta».

## Por qué

Un hilo que lleva un proyecto ordena su trabajo con códigos: `H3` es una hipótesis, `PEN-07` un pendiente,
`REQ-03` un requisito, `T84` una tarea. Los escribe en sus documentos y después los nombra en la conversación («cerré
`PEN-07`, queda `REQ-03` por `H3`»). El agente se acuerda; la persona no: para saber qué es `PEN-07` tiene que ir a
buscarlo. Y lo que una persona no recuerda, no lo puede discutir.

## Qué es

Al lado de la conversación (o de la terminal) de un hilo, en la barra de la derecha, una hoja **«códigos»**:

1. **En esta conversación**: los códigos que la conversación nombró, el último arriba, con lo que son.
2. **Del proyecto**: los de la carpeta del hilo, agrupados por clase (las hipótesis, los pendientes), con el nombre
   de la sección donde se definen.
3. **Una caja para buscar** por código o por texto.
4. **El detalle**, al hacer clic: lo que dice su definición (el texto de su sección, o las columnas de su fila), en
   qué archivo y línea está (se abre en el visor) y dónde más se nombra.

## Qué es un código

Dos a cinco caracteres: una a cuatro letras mayúsculas, quizás un guion y uno a cuatro dígitos (`H3`, `PEN-07`,
`IND-020`, `T458`), solo, sin letras ni guiones pegados. Nadie los declara: se reconocen las tres formas en que un
documento **define** uno.

- **Un título**: `### H3 — El equipo adopta si el piloto le ahorra tiempo`. Su texto es la sección, hasta el próximo
  título de su nivel o más alto.
- **Una fila de tabla** con el código en la primera columna: `| PEN-07 | Mandar el acta | Ana | 12-nov |`. Su texto
  son sus columnas, con los nombres del encabezado de la tabla.
- **Una viñeta en negrita**: `- **R2** — el proveedor no entrega a tiempo`. Su texto es la viñeta, con sus líneas
  de continuación.

Lo que va en un bloque de código no cuenta.

**Solo los que salen de su archivo.** Medido en dos proyectos reales: uno tiene 494 códigos distintos y otro 1.478, y
el mismo `P01` está definido en 18 archivos (cada entrevista numera a su gente desde uno). La mayoría son rótulos de
un documento, no cosas del proyecto. Las que importan son **las que se nombran fuera del archivo donde se definen**
(en otro documento de la carpeta, o en la conversación del hilo): esas son las que se pierden de vista. En el
proyecto grande quedan 500, y 344 con una sola definición: los pendientes, las promesas, los indicadores.

**Su clase** es su prefijo (`PEN-`, `H`). Se nombra con el título de la sección donde están la mayoría de sus
definiciones («Pendientes», «Hipótesis»), y se muestra con su archivo. Así `H` puede ser «Hipótesis» en un proyecto
e «Hitos» en otro sin que nadie lo diga.

**Un código con dos definiciones** (dos versiones de un documento) se muestra con las dos, la del archivo más
reciente primero.

**Las tareas** (`T458`) son objetos de telar (`tarea:T458`): si la conversación nombra un código que el proyecto no
define y que es una tarea, va como tarea, con su título y su estado, y su detalle es el de la tarea. Salen todas las
que la conversación nombra, aunque sea de pasada: lo que importa es poder saber qué es cada código que se lee.

## Dónde se calcula

En la máquina donde vive el hilo, que es donde están su carpeta y su conversación: aquí, `telar.codigos`; en otra, se
le pide a su nodo por el bus (el verbo `codigos`, de solo lectura). Se recorren los `.md` de la **carpeta vinculada**
del hilo, saltando las ocultas y `node_modules`, hasta 5.000 archivos (si hay más, se dice). Cada archivo se lee una
vez y se vuelve a leer solo si cambió su fecha o su tamaño, como el índice de las tareas (telar.tipos.indice).

Un hilo sin carpeta vinculada (un agente que arranca en la raíz) ve solo los códigos de su conversación que son
tareas: recorrer un repositorio entero no tiene sentido.

    telar codigos [<hilo>] [--buscar texto] [--codigo PEN-07] [--json]
    GET /api/codigos?hilo=Faro[&maquina=servidor][&codigo=PEN-07]

## Los pasos

1. ~~**El escáner, la orden y la API**~~: `telar.codigos` (definiciones, menciones, clases, la caché por archivo),
   `telar codigos`, `GET /codigos`, el verbo `codigos` del nodo; con pruebas.
2. ~~**La hoja en la barra de la derecha**~~ (web/codigos.ts): «en esta conversación», «del proyecto» por clase, la
   caja de buscar y el detalle; la barra aparece en cualquier hilo con códigos, y en el de un agente comparte lugar
   con su ficha (dos hojas). Se relee cada 30 s mientras se ve.
3. ~~**Los códigos como enlaces**~~ en la terminal, la lectura y la conversación (web/enlaces.ts, web/rutas-agente.ts):
   un clic en `PEN-07` abre la barra en la hoja de códigos, con ese abierto (en la terminal, ⌘-clic: un código es corto
   y está por todas partes, y un clic para enfocarla no tiene que abrir uno; al pasar encima dice qué es). Solo los
   que la hoja conoce para ese hilo, para no marcar `SHA-256`; y ninguno si el modo oculta la barra o en el celular,
   donde no tendrían dónde abrirse.

Después, si hace falta:

- `.telar/codigos.yaml`, para nombrar una clase o excluir una carpeta (las corridas viejas de una evaluación), si
  adivinar falla en algún repositorio.
- En el teléfono, que no tiene barra de la derecha: una hoja que sube desde abajo.
- Para un hilo sin carpeta: buscar las definiciones en los archivos que su conversación tocó.
