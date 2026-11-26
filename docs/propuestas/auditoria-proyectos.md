# La vista de proyectos contra el sistema de diseño

Estado: auditoría del 26-nov-2026. La persona la aprobó entera ese día y decidió el menor 9: el README del detalle se
lee con la prosa compartida (`media/css/prosa.css`, la del visor y la lectura de un hilo). Se arregló por etapas, en el
orden de abajo, en la rama `proyectos-vista`: las cinco están hechas (26-nov), y con ellas la sección A del encargo
que la pidió (proyectos › clientes, comercial e interno).

La pregunta fue qué principios del sistema de diseño no cumple la pestaña «proyectos» del dashboard
(`vistas/dashboard/proyectos.ts`, `iniciativas.ts`, `media/css/proyectos.css` y lo que usa de `dia.css`). Se midió en
la página de verdad y cada falta dice el principio que rompe, la medida que lo muestra, el archivo y la línea que lo
causan, y con qué componente de la casa se arregla.

## Cómo se midió

Con `scripts/medir.py` y la página de esta rama, en el modo estrategia (abre en proyectos), sin teclear nada: solo
clics y JavaScript. Cuatro anchos: 1440×900 (el laptop), 1024×700 (dos columnas apretadas), 860×800 (una columna) y
el teléfono (iPhone 14, 390 px). En cada uno, la lista, un proyecto elegido (el que tiene más pendientes) en sus tres
pestañas, la sección de iniciativas y la tabla extendida (↔). Un script recorre todo lo visible de la pantalla y
devuelve los altos de cada clase de fila, dónde empieza y termina cada una respecto del borde de la pantalla, los
tamaños y pesos de letra, los bordes redondeados y cada línea con su largo.

Las capturas, las medidas en JSON y los scripts quedan fuera del repositorio, en
una carpeta del laptop: muestran nombres de clientes, así que aquí no se
copian. Las referencias a capturas de abajo (`ancho-02`, `tel-02`…) son esos archivos.

Las medidas de los tokens, en la densidad compacta: una fila (`--item-alto`) 16,9 px; una fila con línea, del alto de
las barras (`--pantalla-barra-alto`), 26,3 px; el aire de una pantalla (`--pantalla-margen`, `--item-pad-x`) 11,7 px.
En la barra de hilos, al lado, la cabecera de una sección mide 27,3 px y va en el amarillo de las cabeceras.

## Lo grave (se nota al tiro)

### 1. El nombre del proyecto se pierde

- **Principio**: en una fila lo que se estira es el título; lo demás cede (el ítem; en la fila de una tarea, «en una
  columna angosta, código y proyecto se van»). El propio CSS lo dice: «lo que se lee ahí es el nombre».
- **Medida**: a 1024×700 la lista mide unos 416 px y la columna del nombre queda en **una letra** (el encabezado dice
  «p»; `v1024x700-01`). En el teléfono, unas siete letras por nombre (`tel-01`). A 1440×900, en las iniciativas, el
  nombre queda en cuatro o cinco letras («Inter…») mientras la columna de lo próximo tiene espacio vacío (`ancho2-01`).
  La columna estado dice «en ejecución» en las 52 filas de la sección «EN EJECUCIÓN»: 12 letras que repiten la
  cabecera.
- **Causa**: `proyectos.css:6` reparte dos columnas (`minmax(44ch, …) minmax(40ch, …)`) hasta que la pantalla baja de
  620 px; cada fila tiene columnas de ancho fijo (estado 12ch, `:21`; plazo 13ch, `:26`; tareas 6ch, `:28`; tres
  celdas) y solo en la `@container` de 620 px (`:76`), que mide la pantalla y no la lista, se va el estado. En las
  iniciativas, el nombre comparte su `flex` con lo próximo, el dueño (8ch), el estado (12ch) y la fuente (14ch)
  (`:50-65`).
- **Arreglo**: las filas como `item()` (ver 3): el título se estira, el plazo va en la meta y lo demás en ranuras.
  `container-type` en la lista (`.proy-lista`), para que sus columnas cedan por su propio ancho, en orden, como la
  jornada («lo primero que cede»). La columna estado, fuera de la vista de dos columnas: la dice la cabecera de la
  sección (y lo tenue de «nadie lo confirma» cabe en el globo o en el círculo). Pasar a una columna antes, con el
  detalle como pantalla propia (ver 5).

### 2. Filas, selección y líneas no van de borde a borde

- **Principio**: «Su cuerpo no tiene margen: el aire va dentro de cada fila y las líneas van de borde a borde»
  (`componentes/gramatica.ts:162`, y «La pantalla» en [componentes.md](componentes.md)); los separadores de borde a
  borde (lo pidió la persona el 17-nov).
- **Medida**: a 1440×900 cada fila de la lista empieza a 11,7 px del borde de la pantalla y termina 12 px antes del
  divisor; el fondo de la fila elegida flota entre los dos (`ancho-02`). Las líneas de las secciones, igual: de 11,7 px
  a 12 px antes del divisor. El círculo de la primera columna arranca a 19,5 px del borde, el nombre de la barra a
  11,7: no se alinean. En una columna, filas y líneas quedan a 11,7 px de cada borde. La barra del buscador, en cambio,
  sí va de borde a borde (de 0 al divisor).
- **Causa**: el aire de `#dia` (`dia.css:23`) no se deshace para `.proy-dos` (la clase `.de-borde` de `dia.css:26`
  existe para eso); `.fila` lleva su propio relleno de 1ch (`dia.css:32`) en vez de `--item-pad-x`; y entre la lista y
  el detalle hay un hueco de 1,5ch (`proyectos.css:6`).
- **Arreglo**: `.proy-dos` sale del aire de la pantalla como lo hace la barra del buscador, sin hueco entre columnas
  (el divisor es la línea); las filas, `item()` con su `--item-pad-x`; las secciones, `seccion()`.

### 3. Las filas y las cabeceras están hechas a mano

- **Principio**: las filas de una lista se arman con `item()` y los grupos con `seccion()` (paso 6 de
  [componentes.md](componentes.md)); alto estándar de fila; una sección dentro de una pantalla lleva «una línea arriba,
  de borde a borde, y su cabecera en su tinta, con la cuenta tenue, como las de la barra de hilos»; un grupo dentro
  de otro es un submenú (la carpeta, «Los submenús»).
- **Medida**: las 92 filas de proyectos miden 16,9 o 17,9 px según tengan o no el ícono de la etapa (la letra de íconos
  trae otro interlineado: el mismo píxel que `pantalla.css` ya corrigió en la barra). Las cabeceras de sección
  («EN EJECUCIÓN 52») miden 17,9 o 18,9 px, van en gris (`--dim`) y se apartan con 0,6 líneas; las de la barra de
  hilos miden 27,3 px y van en su amarillo. En las iniciativas, cada programa se aparta con 0,3 líneas (5 px) y
  «sin programa» es un encabezado con otra sangría (su texto a 44,2 px del borde; el de las filas, a 53,3).
- **Causa**: `proyectos.ts:141-148` (`filaProyecto`, un `div.fila` con sus `span`), `:198-199` (la cabecera de
  sección), `iniciativas.ts:237`, `:268` y `:278`; `proyectos.css:39` y `:66`. En toda la pestaña solo se usan dos
  componentes de la casa: `barraBuscar` y `pestanas`.
- **Arreglo**: `filaProyecto` como `item()`: la fase en la ranura del estado, la etapa como ícono en otra ranura, el
  cliente como prefijo, el nombre como título, el plazo como meta, lo que no cuadra como aviso y el ⋯ como menú. Cada
  estado como `seccion({ clave, titulo, cuenta, filas })`, con su plegado. Los programas y «sin programa», submenús
  de la sección de iniciativas.

### 4. La primera fila del detalle no es una barra

- **Principio**: la primera fila es una barra del alto estándar, con el título a la izquierda y solo botones a la
  derecha (`docs/desarrollar.md:70`; así se hizo la del visor de documentos, «Las ventanas» en
  [componentes.md](componentes.md)). Peso normal: la distinción va por color e ícono, nunca por grosor ni tamaño
  (`--item-cabecera-peso` en `tokens.css`; la regla «el tamaño de la letra no dice qué importa más»). Un botón es un
  ícono en su celda; la palabra, solo donde el ícono no alcanza.
- **Medida**: el nombre va en un `<h3>` de peso 700 y se parte en dos líneas a 1440 px y en cinco a 1024
  (`.det-titulo`: 33,8 y 84,5 px); a su lado, «retomar su hilo» es una palabra en el acento. La cabecera entera
  (`.det-cab`: nombre, cómo va y pestañas) ocupa de 94 a 161 px antes de que empiece el contenido (`ancho-02`,
  `v1024x700-02`).
- **Causa**: `proyectos.ts:386-389`; `proyectos.css:118-125`.
- **Arreglo**: `barra()` de `componentes/pantalla.ts` como primera fila del detalle: el nombre cortado con «…» (entero
  en el globo) y, a la derecha, íconos: ir o retomar su hilo (el del agente, en violeta, el mismo de su ⋯), consolidar,
  abrir el README y el ⋯. «Cómo va» (estado, etapa, fechas, su fuente) queda como primera fila del cuerpo, en una
  línea.

### 5. En una columna, el detalle es una caja con scroll propio; en el teléfono no se ve

- **Principio**: «Cada corte se marca con un solo medio» y «nunca un marco para algo que no se abre aparte»
  (`gramatica.ts:163` y `:168`). Una pantalla a la que se llega desde otra lleva «‹» en su barra (la ficha de una
  tarea vuelve a su lista).
- **Medida**: a 860×800 el detalle sigue con `position: sticky`, alto máximo de 694,7 px y su propio scroll dentro
  de la página, que también corre; lleva línea a la izquierda y arriba (`v860det-01`). En el teléfono, tocar un
  proyecto marca la fila y el detalle aparece debajo de las 92 filas y las 30 iniciativas: no se ve nada (`tel-02`).
- **Causa**: el bloque `@container (max-width: 620px)` que suelta el detalle (`proyectos.css:76-78`: `position:
  static`, sin alto máximo, sin línea izquierda, sin relleno) va **antes** de la regla de `#proy-det`
  (`proyectos.css:116`), con la misma especificidad: gana la de abajo y la de una columna no rige nunca.
- **Arreglo**: ya, mover ese bloque al final del archivo (una línea de diferencia, sin decidir nada). De fondo: en una
  columna, el detalle como pantalla propia, con «‹» en su barra (`EnBarra.volver`, como la ficha de una tarea).

### 6. El divisor entre la lista y el detalle termina donde termina el detalle

- **Principio**: las líneas van de borde a borde.
- **Medida**: el divisor es el borde izquierdo del detalle y mide lo que mide su contenido: 25,3 px con «elige un
  proyecto a la izquierda», 186,8 px en una pestaña de pendientes corta, mientras la lista sigue 1.800 px hacia abajo
  (`ancho-01`, `ancho-03`).
- **Causa**: `align-items: start` en la grilla (`proyectos.css:6`) y la línea en `#proy-det` (`proyectos.css:116-117`).
- **Arreglo**: la línea como borde de la columna de la lista, a toda su altura (o la grilla estirada y el detalle
  `sticky` adentro de su columna).

## Lo menor

1. **El ⋯ siempre a la vista.** Cada fila muestra su ⋯: una columna de 92. En el ítem, las acciones y el ⋯ aparecen al
   pasar el mouse (la barra de hilos no los muestra quietos). `proyectos.ts:148`. Se arregla con el `menu` de `item()`
   (punto 3).
2. **Acciones en palabras dentro del cuerpo**: «retomar su hilo», «consolidar pendientes: un agente revisa…», «abrir
   el README», «los N pendientes» y «más», enlaces en el acento hechos cada uno a mano (`proyectos.ts:301`, `:320`,
   `:344-345`, `:371`, `:387`). Las de la pantalla van a la barra del detalle, como íconos (punto 4); «los N
   pendientes» repite la pestaña de al lado y sobra. «Más» es del texto y puede quedar. [componentes.md](componentes.md)
   ya lo tenía anotado en «Falta, pantalla por pantalla».
3. **↔ es una vista y está como botón suelto.** La tabla extendida es otra forma de mirar lo mismo: según «La
   pantalla», va como ícono de vista en la barra, junto a «gantt» (lista · tabla · gantt). Hoy es un `.modos button`
   dentro de las herramientas del buscador (`proyectos.ts:173`; su estilo, `dia.css:58-62`), y entre él y «cerrados»
   van dos letras de aire, no el espacio de una celda.
4. **Las secciones del resumen son títulos grises sin línea** (ESTADO, PRÓXIMOS, ESPERANDO, QUÉ ES, DATOS: `<h4>`, con
   una línea de aire arriba y 0,3 abajo). Una sección dentro de una pantalla lleva su línea arriba y la cabecera en su
   tinta. `proyectos.ts:313-328`, `proyectos.css:136-137`.
5. **El documento, plegado a mano.** Sus secciones son `<details>` propios, de 17,9 px, con el título en negrita (700)
   al abrirse (`proyectos.ts:350-355`, `proyectos.css:151-162`). Es el submenú del ítem (la carpeta), con su `Plegado`
   para recordar qué quedó abierto.
6. **Las viñetas del documento llevan la ranura del código vacía.** En «próximos» y «pendientes», las que vienen del
   README no tienen código, pero su ranura de 5 letras queda: el texto empieza 82 px dentro de la columna y los títulos
   de sección, en 0 (`ancho-02`). `fila-tarea.ts:166-167` pone el código siempre; el comentario de
   `proyectos.ts:225` dice «sin la columna del proyecto» y la llama sin opciones. La ranura debería ir solo si alguna
   fila de esa lista la usa.
7. **Espacios fuera de los tokens.** `proyectos.css` usa 0,2, 0,3, 0,4, 0,6, 0,7 y 0,9 líneas, rellenos de 1ch y 2ch
   (`dia.css:32`, `:117`), un hueco de 1,5ch y un token propio, `--celda-cuadrada: 1lh` (`proyectos.css:10`, 20 usos),
   paralelo a `--item-ranura` y `--entre-celdas`; varios, asimétricos (los títulos del resumen: una línea arriba, 0,3
   abajo). Los de la casa: `--e-1..3`, `--h-1..2`, `--pantalla-margen`, `--item-pad-x`.
8. **Colores primitivos en vez de semánticos**: `--dim` 21 veces, `--fg` 5, `--azul` 4, `--bg` 1 en `proyectos.css`.
   `tokens.css` pide que las vistas usen los semánticos (`--texto-tenue`, `--texto`, `--acento`, `--superficie`), para
   que un tema (latte, riso) los cambie. Y el cliente va en azul, el color de «un lugar al que se va», sin ser un
   enlace (`proyectos.css:16`).
9. **El markdown del README tiene reglas propias**: interlineado de 1,45 (la grilla es de 1,3), citas con línea de
   2 px (la regla pide líneas de un píxel), tablas con un recuadro por celda y negritas de 700
   (`proyectos.css:164-176`). Es el tercer markdown de la página (con la lectura de un hilo, `.prosa-md`, y el
   visor). **Por decidir con la persona**: si el README se lee con la prosa (con serifa, para leer con calma) o con
   un markdown en la grilla común al visor y a este detalle.
10. **La cabecera de columnas** marca la que ordena en azul, y el orden de la barra de hilos usa `--titulo`. La
    cabecera de tabla todavía no es componente (está pendiente en [componentes.md](componentes.md), con la propuesta
    de un `--orden-activa` común): no se cuenta como falta, se anota para cuando se haga.
11. **CSS duplicado**: `.proy .cuando-p` está en `dia.css:250` (4ch, a la derecha) y en `proyectos.css:26` (13ch); rige
    el de proyectos.

## En curso (no se cuenta)

- **El filtro de área** («todas las áreas» y cada área con su cuenta, `proyectos.ts:82-90`): palabras con su «todas»,
  en su propia fila, a una línea del buscador. Lo pasa el hilo nocturno ◑ componentes a `filtros()` (decisión del
  26-nov). «cerrados N» (`proyectos.ts:172`), al lado del buscador, también elige qué filas se ven: si no entra en ese
  paso, que vaya con él.

## Lo que cumple

- **La barra de la pantalla**: el nombre en su tinta, «gantt» como vista, ↻, y lo que resume (los negocios) en el
  globo; `window.telar.revisarBarra()` no encuentra nada de más.
- **El buscador**: es `barraBuscar`, del alto de las barras (26,3 px), con su línea de borde a borde de su columna y
  en el acento con el foco.
- **Las pestañas del detalle**: son `pestanas()`, de 26,3 px, con su línea abajo y la abierta con el fondo de la
  selección. Su línea queda 11,7 px antes del borde derecho (el punto 2 lo arregla).
- **Un solo tamaño de letra**: 13 px en todo, letra e íconos.
- **Sin esquinas redondeadas**: lo único redondo son los círculos.
- **Todas las líneas del mismo color** (`--linea`), salvo la del buscador con el foco, que es lo decidido.
- **Los círculos**: la fase de un proyecto y el estado de una iniciativa son los de la gramática.
- **La fila elegida** lleva el fondo de la selección (`--item-fondo-activa`), y las tareas del detalle son la fila de
  una tarea (`filaTarea`, un `item()`).

## Fuera del diseño, visto de paso

- **Pendientes repetidos.** El proyecto medido muestra 96 filas en «pendientes» y solo 24 distintas (cada una cuatro
  veces); en otra corrida, 48. Su documento dice «24 abiertas». No venía de la página sino de quien llena `pendRepo`:
  el proyecto tenía cuatro hilos vinculados a su carpeta y `telar pendientes` (`ordenes/pendientes.py`, `juntar`) leía
  su documento una vez por hilo. Arreglado: cada documento va una vez (`pruebas/test_ordenes.py` lo cuenta contra su
  README).
- **El buscador en el teléfono mide 18,9 px**, no 26,3: lo pide el componente (`.angosto .buscador-barra { height:
  auto }`, `buscador.css:95-99`), no proyectos. Si es a propósito, está bien; si es un resto, es de todos los
  buscadores.

## El orden que se propone

1. Mover el `@container` de `proyectos.css` al final (punto 5, inmediato).
2. La lista con `item()` y `seccion()`, de borde a borde (puntos 1, 2 y 3, y de paso los menores 1, 7 y 8 de la
   lista). Es el cambio grande y el que más se nota.
3. La barra del detalle (punto 4 y menor 2) y el divisor a toda altura (punto 6).
4. ↔ como vista en la barra (menor 3) y el detalle como pantalla propia en una columna (fondo del punto 5).
5. El cuerpo del detalle: secciones del resumen, el documento como submenús, la ranura del código (menores 4, 5 y 6).
6. El markdown, cuando la persona decida (menor 9).

## Conexiones

- [Los componentes](componentes.md) — los principios y los componentes contra los que se midió.
- [Modos](modos.md) — estrategia abre en proyectos, donde se midió.
- [README.md](README.md) — el plan de las propuestas.
