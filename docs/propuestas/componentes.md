# La librería de componentes

Estado: decidido el rumbo (lo de abajo); hecho el ítem, el círculo, temas, densidades, el catálogo con su lista
jerárquica a la izquierda, la revisión (el inventario), el «+» de nuevo y el componente de orden y el de buscador en la barra; y la
sección de lista entera, con la que se arma la barra (26-nov). El buscador ya está en todas partes. Del orden de trabajo queda, de las
ventanas, la instrucción (de día), la mudanza y la franja de soltar; y la cabecera de tabla.

La página de telar se arma con piezas que hoy están hechas una vez por cada vista: un buscador en la barra de hilos,
otro en el dashboard, otro en ⌘K; los íconos para ordenar, cada grupo a su manera; «+ nuevo» escrito a mano en cada
cabecera. Esta propuesta las junta en una librería: cada componente definido una vez (su función en
`pagina/src/componentes/`, su CSS en `media/css/`, sobre los tokens), con sus partes nombradas, y mostrado en el
catálogo (`/componentes`) en todos sus estados, temas y densidades. Así una vista nueva se arma con piezas, y un
cambio de diseño se hace en un lugar.

Se trabaja de noche, sin nadie mirando (§ «La noche», abajo), y de día se revisa y se lleva a las máquinas.

## Lo que ya está (10-nov-2026)

- **Tokens** en tres capas (`media/css/tokens.css`): primitivos de un tema, semánticos (`--texto-tenue`, `--acento`,
  `--estado-espera`…) y de cada componente (`--item-…`, `--circulo-…`). **Temas** (`temas.css`: telar, latte, riso,
  papel) cambian colores; **densidades** (`densidades.css`: compacta, cómoda, amplia; «auto» en una pantalla táctil)
  cambian medidas.
- **Ítem** (`componentes/item.ts`, `item.css`): la fila de una lista en tres secciones, inicio (ranuras de íconos) ·
  texto (prefijo, título, sufijo) · fin (aviso, meta, fijas, acciones que se despliegan al pasar el mouse, ⋯ al
  último). Toda la barra de hilos se arma con él. Su anatomía, con la intención de cada pieza, en
  `componentes/anatomia.ts`.
- **Orden** (`componentes/orden.ts`, `orden.css`): el grupo de ordenar (ícono padre + opciones entre dos cortes en su púrpura);
  la barra de hilos lo usa y tiene su página en el catálogo. En el dashboard, «tareas» y la lista de proyectos lo llevan en la
  barra de su buscador; la tabla extendida de proyectos ordena todavía por los nombres de sus columnas.
- **Buscador** (`componentes/buscador.ts`, `buscador.css`, tokens `--buscador-…`; 18-nov, a pedido: «no somos consistentes en los
  inputs para buscar… debería ser un componente definido»): uno solo para toda la página, y todos los buscadores lo usan (el inventario,
  con cómo era cada uno, en el catálogo: «buscador › dónde está»). **Una regla**: la lupa delante («aquí se busca»), y el texto de ayuda
  dice **en qué** se busca, sin el verbo («hilos», «tareas», «lo que te espera»; `placeholder` es obligatorio); por qué campos y qué
  hacen ⏎ y ⎋, en la `ayuda`, al pasar el mouse. Al final, la cuenta (`cuenta`, la llena la vista o viene puesta), la tecla que lo
  enfoca (`atajo`, tenue, solo vacío y sin el foco: ya no va en el placeholder) y, con algo escrito, un ✕ que lo borra
  (`web/buscadores.ts` lo atiende en toda la página: vacía el campo y avisa con un `input`). Los estados, solo con color: con el foco
  o con el filtro puesto, la lupa en el acento. **Como fila propia va en su barra** (`barraBuscar`): del alto de las barras
  (`--pantalla-barra-alto`), con el aire de una pantalla (`--buscador-margen`) y su línea abajo de borde a borde, con lo que lo
  acompaña a la derecha (`herramientas`: el orden, un botón). Con esa línea, el campo **no lleva borde**: se probaron cuatro maneras
  (su propia línea, otro fondo, la línea de la barra en el acento con el foco, solo la lupa; «buscador › bordes») y se eligió que la
  línea de la barra tome el acento mientras se escribe. Reemplaza los campos hechos a mano (⌘K, elegir, el menú ⋯, la instrucción,
  compartir, los códigos del lado, la skill de un periódico) y el `«/ buscar»` del placeholder. Quedan fuera las pestañas de los
  módulos (whatsapp…), que viven en sus repositorios.
- **Sección de lista** (`componentes/seccion.ts`, `seccion.css`; paso 6: la banda el 16-nov, el grupo entero el 26-nov): un
  grupo de una lista. `seccion({ clave, titulo, cuenta?, ayuda, abierta, acciones?, nuevo?, herramientas?, filas, vacia? })`
  da la cabecera (el «+» al último) y, abierta, la banda (`herramientas()`: buscador + orden + lo extra, con su fila oculta
  «nada calza») y las filas o la que dice que no hay; `submenu({ …, ancho? })`, la sección dentro de otra; `secciones([…])`
  las junta con el `separador()`. **`filas` es una función**: plegada, no se arma (y en HILOS la cuenta de la cabecera
  depende de lo que AGENTES dibujó antes). Da **HTML plano**, sin un elemento que envuelva el grupo: el CSS del separador y el
  arrastre necesitan que sean hermanos. El **plegado** es `Plegado` (sin DOM: dónde guardar y con qué llave): recuerda solo
  las cabeceras que están al revés de como empiezan. La barra de hilos arma así todas sus secciones, con el mismo HTML de
  antes. En el catálogo, «sección de lista»: el grupo, anatomía, submenú, herramientas. **Fuera**: los grupos de «te esperan»
  (`vistas/dashboard/esperas.ts`, con su plegado propio en `telar.esperas.plegados`) y los bloques del dashboard.
- **Filtros** (`componentes/filtros.ts`, `filtros.css`): los grupos de opciones con su cuenta, en una fila, a la vista o
  plegados en un menú; los usa «tareas» (13-nov, ver «Los filtros»).
- **Círculo** (`componentes/circulo.ts`): la firma de los estados (tamaño y llenado) y de lo que está en curso (se
  vacía, se llena, gira), sin mover nada más.
- **El catálogo** (`/componentes`, `componentes/catalogo.ts`): la lámina del ítem, el círculo, el ítem en cada estado,
  la barra de verdad con hilos de mentira, y los tokens; cada columna es un tema × una densidad.

## Lo que se pidió (10-nov-2026)

1. **El buscador**, estandarizado: hoy está hecho en muchos lugares de maneras distintas.
2. **Ordenar**, estandarizado: qué íconos ordenan por qué, y un ícono «padre» que diga que los que siguen ordenan.
   Todo el grupo de ordenar en un fondo propio (algo como un púrpura tinto) para que se lea como una sola función:
   ordenar la lista.
3. **El botón nuevo**, estandarizado y sin la palabra «nuevo»: se usa en varias partes.
4. **Componentes de sección**: por ejemplo, una sección de la lista de la izquierda, con su fondo y su separador.
5. **Una revisión de toda la interfaz** para identificar componentes (es trabajo de noche: hay tokens para gastar).
6. **El catálogo con una lista de componentes a la izquierda, en orden jerárquico**: pensar qué componentes van dentro
   de cuáles para que queden bien factorizados, y los generales de lo que es para nosotros **una ventana, un modal**.
   Por ejemplo, la tarjeta de comandos (⌘K) es muy buena, y ese tipo de modal debería reutilizarse en otros lugares.

## La pantalla (decidido el 12-nov-2026)

Lo pidió la persona: que las apps del dashboard se vean como un hilo y sigan este sistema. Lo que llena la columna de
la derecha, sea un hilo o una app (ahora, tareas, proyectos, la pestaña de un módulo), es una **pantalla**, con dos
partes y nada más (`componentes/pantalla.ts`, `media/css/pantalla.css`, su página en el catálogo):

- **La barra**, arriba y siempre: una fila de borde a borde, con el fondo de barra y una línea abajo, la misma del
  hilo. De izquierda a derecha: «‹» si se vino de otra pantalla (la ficha de una tarea vuelve a su lista); el nombre de
  la app, en su tinta y con el peso de una cabecera (el mismo nombre de su fila en la barra de hilos; un hilo no lo
  lleva, lo dice la cabecera de la página); sus **vistas**, las formas de mirar lo mismo (foco y lista, el día y la
  semana, proyectos y gantt; en el hilo, la terminal, la lectura y la conversación), un ícono cada una, la que se ve en
  violeta; lo que **resume**, tenue (una cuenta, la fecha, «1/10»); y a la derecha sus **acciones**, íconos: moverse
  (‹ ›, hoy), filtrar, ⚙, ↻. Una palabra va solo donde un ícono no alcanza (la carpeta de un hilo, una ruta); un atajo
  de `[atajos]` va con su tecla; la vista de un módulo, que no trae ícono, con su nombre.
- **El cuerpo**, sin margen propio: el aire va dentro de cada fila (`--pantalla-margen`, el mismo de las filas de la
  barra de hilos, así el texto de las dos columnas arranca igual), y lo que es una línea va de borde a borde: el
  separador de una sección toca la línea de la columna de la izquierda. Una sección dentro de una pantalla (el foco, la
  agenda del plan) es como las de la barra de hilos: una línea arriba y su cabecera en su tinta, la cuenta tenue al lado.
  La página de un módulo ocupa el cuerpo entero, de borde a borde, y recibe los tokens del tema (docs/contratos.md): no
  dibuja su título (lo dice la barra) ni repite lo que la barra ya resume.

En el dashboard, la barra la pone el núcleo (`panel.ts`, `Tablero.pintar(h, barra)`): el nombre y la tinta de la pestaña
que se ve (`BARRA_DE`), sus vistas (las subpestañas, con su ícono de `ICONO_VISTA`) y ↻; cada pantalla le pasa lo suyo
(`EnBarra`: lo que resume, sus acciones, otro nombre, «‹»). En el hilo, `navegador/app.ts`.

**Hecho (rama `pantallas`):** la barra en todas las pantallas del dashboard y en el hilo; el cuerpo sin margen y las
secciones de borde a borde; las subpestañas, las navegaciones (‹ › hoy del plan, del calendario y de «ahora», ← → de la
ficha) y los títulos de cada pantalla, a la barra; la ficha de una tarea sin recuadro; los tokens a los lienzos; las
páginas de WhatsApp, productos y gantt con la letra y el aire de telar (WhatsApp, sin su ↻ ni el estado repetido).

## Las listas de tareas (decidido el 13-nov-2026)

Lo pidió la persona: que las listas de tareas sigan el sistema. Todas (la pestaña «tareas», las de un correo, el detalle
de un proyecto, «ahora» y la pestaña de un proveedor) usan una sola fila, `vistas/dashboard/fila-tarea.ts`, que es un
**ítem** como un hilo de la barra:

- **inicio**: la prioridad (círculo chico; la urgente, P0, lleno en rojo) y el estado (círculo grande: en curso, lleno
  como un hilo trabajando; te espera, porque un agente dejó algo para decidir, un aro; sin estado, vacía), y dos ranuras
  de texto que alinean como columnas: el código, tenue, y el proyecto (un clic lo abre en proyectos). En una columna
  angosta, código y proyecto se van.
- **texto**: una línea, cortada con «…» (entera al pasar el mouse); antes, la palabra de lo que dejó el agente
  («pregunta», «preparado») y el responsable si no es la persona («→ Ana»). La persona misma no se escribe en cada fila.
- **fin**: la estrella (un aro con un punto, «señalada») y la fecha (vencida en rojo, hoy y mañana en el de cuidado). Al
  pasar el mouse: estrella, otra fecha, compartir, la instrucción y hecha; el ⋯ con el resto (prioridad, responsable,
  lo del proveedor). Nada de eso es un círculo: la prioridad ya no se cambia con un clic en ella, sino desde el ⋯.

La pestaña «tareas» deja de ser una tabla: sin cabecera de columnas, ni recuadro de color a la izquierda. Arriba, sus
herramientas como en la barra de hilos (el buscador con su cuenta y el grupo de ordenar: fecha, prioridad, estrella,
proyecto, responsable, código, alfabético; otra vez en el que rige, la urgencia), y debajo los filtros, en una fila (ver
«Los filtros»). La «cabecera de tabla» queda para la tabla extendida de proyectos (la lista ya es de ítems, como «tareas»).

## Los filtros (decidido el 13-nov-2026)

Lo pidió la persona: que los filtros de «tareas», hasta tres filas de palabras con su cuenta (el modo, el área, el
responsable), fueran un componente y una sola fila. Los tres grupos en palabras ocupan unas 170 letras y la columna del
dashboard tiene unas 135: no caben. Se le mostraron tres maneras en el catálogo, cada una en tres anchos: todo a la vista
(dos renglones en el computador), todo plegado (al lado del buscador) y una mezcla. **Eligió la mezcla**, y sacar
«todas» del área y del responsable.

El componente (`componentes/filtros.ts`, `media/css/filtros.css`, página «filtros» en el catálogo):

- **Qué es**: los grupos de opciones que eligen qué filas de una lista se ven. Cada opción, una palabra con su cuenta:
  cuántas filas dejaría si se la eligiera, con lo demás que está filtrado (los otros grupos y lo buscado). La que rige,
  en el acento; una cuenta en cero, apagada.
- **Una fila** bajo las herramientas de la lista, tras el ícono padre (`I.filtro`, en su celda, como el del orden). Entre
  un grupo y otro, más aire que entre sus opciones, sin cortes: un corte quedaba colgando cuando la fila se parte. Si no
  cabe, baja el grupo entero, y cada renglón empieza donde el primero, después del padre.
- **Soltar**: otro clic en la que rige la suelta, y el grupo vuelve a lo de siempre (el modo, a «esta semana»; el área y
  el responsable, a ninguno), como en el orden. Por eso el área y el responsable no tienen «todas». El modo sí: «todas»
  es un modo, no soltar.
- **Plegado**: el grupo dice solo lo que rige (o su nombre: «área», «responsable») y un ⌄. Un clic abre junto a él el
  menú del ⋯, con las opciones y sus cuentas, y la que rige con ✓ en el acento. Se pliega lo que se elige una vez y se
  deja (el área, el responsable); queda a la vista lo que se cambia seguido (el modo).
- Si lo que rige deja de estar entre las opciones (no queda ninguna tarea de esa área), se suelta solo: si no, la lista
  quedaría filtrada sin que se vea por qué, y sin «todas» no habría cómo soltarlo.

En «tareas», el modo va a la vista y el área y el responsable plegados: una fila en el computador; en media pantalla y en
el teléfono se parte por grupos. Lo elegido se recuerda como antes. El de proyectos pasó el 26-nov (`proyectos.ts`,
`filtrosProyectos`): el área plegada, como en «tareas», con «todas» a la vista cuando no rige ninguna y primera en su menú,
y «cerrados N» a su lado.

## La tarjeta (propuesta, 13-nov-2026)

Lo pidió la persona: ver si el estilo de las tarjetas estaba definido y, si no, definirlo antes de cambiar las de foco.
**No lo estaba**: «tarjeta» aparecía solo como nombre en la jerarquía (entre los contenedores, sin nada más) y en la
gramática como ejemplo de «marco» («una cosa que se abre y se cierra: una ventana, una tarjeta»), lo que chocaba con su
propia regla («nunca un marco para algo que no se abre aparte») y con lo que pide la pantalla (sin marcos). Las de foco
estaban hechas a mano en `dia.css`: un recuadro con el fondo de la barra, la elegida con borde azul y raya, la vencida
con una raya roja.

La definición (`componentes/tarjeta.ts`, `media/css/tarjeta.css`, tokens `--tarjeta-…`, página «tarjeta» en el
catálogo):

- **Qué es**: una cosa entera que se mira y se decide de a una, entre pocas; hoy, las tareas de foco. Un **ítem que no
  se corta**, con sus mismas piezas repartidas en tres partes, como la tarjeta de shadcn/ui (cabecera con su acción,
  contenido, pie). Corregido el 13-nov con la persona: el título y las acciones, arriba.
- **Anatomía** (`componentes/anatomia.ts`, la lámina en el catálogo, «tarjeta › anatomía»; escrita para cualquier cosa
  que vaya en una tarjeta, no solo tareas). Las tres partes son elementos (`.tarjeta-cabecera`, `.tarjeta-cuerpo`,
  `.tarjeta-pie`) que comparten las columnas de la tarjeta (inicio · contenido · acciones, con `subgrid`), y las props
  de `tarjeta()` van agrupadas igual:
  - **cabecera** (¿qué es y qué le hago?): el **inicio**, sus ranuras de círculos (lo que matiza, chico; el estado,
    grande) a la altura de la primera línea; el **prefijo** (de qué clase es o lo que le pasó, en una palabra) y el
    **título**, entero, hasta `--tarjeta-lineas` (tres; «holgada», sin tope), lo único que se estira; y las
    **acciones arriba a la derecha**, en su propia columna, con el ⋯ al último: el título se parte antes de llegar a
    ellas y nunca queda tapado. Se ven al pasar el mouse y en la elegida; en el celular, solo el ⋯.
  - **cuerpo** (¿qué más dice?), si tiene: lo que se lee además del título (un resumen, una nota, lo que dejó quien la
    trabajó), tenue y donde empieza el título.
  - **pie** (¿de dónde es y qué tiene?): sus datos en una línea, tenues, cada uno con su color solo si dice algo (un
    lugar al que se va, en el acento; algo que falta, en el color de su alerta); y pegados a la derecha, bajo las
    acciones, el aviso (una marca) y la meta (un dato que no se aprieta: una fecha, hace cuánto, una cuenta).
- **Cómo se parte**: es una **fila** más alta, no una caja. Sin marco (un marco es de lo que se abre aparte: una
  ventana, un menú) y sin fondo propio; las tarjetas de una lista se apartan con **aire** (`--tarjeta-aire`). La
  elegida lleva el fondo de la selección, como el ítem donde estás; al pasar el mouse, el del hover.
- **Lo que dice**: con las piezas de siempre, nunca con un borde o una raya de color: su estado y lo que lo matiza,
  círculos en sus ranuras; lo que no cuadra, en el color de su alerta (una tarea vencida, su fecha en rojo); señalada,
  un aro con un punto.
- **Holgada** (foco en concentración): más aire y el título entero. El título no va en negrita: el peso es de las
  cabeceras.
- **Medidas**: compacta, medio renglón de aire adentro y entre una y otra; cómoda, tres cuartos; amplia (el dedo), uno.

En la gramática: «tarjeta» entra en «cómo se parte» (una fila que no se corta; su marca, el aire), la regla de los
marcos lo dice, «marco» deja de nombrarla, y una derivada dice qué reemplaza.

**En foco** (13-nov): sus tarjetas son el componente, con las piezas de la fila de una tarea (`fila-tarea.ts`,
`piezasTarea`): en la cabecera la prioridad y el estado, lo que dejó el agente, el título y lo de todos los días (la
estrella, otra fecha, la instrucción, hecha) con el ⋯; en el pie el código, el proyecto (un clic lo abre) o el área,
«sin tamaño», la estrella y la fecha. Concentración usa la holgada. Se elige con un clic y se arrastra a una casilla
como antes. Fuera de `dia.css`: el recuadro, el borde azul de la elegida, la raya roja de la vencida y la negrita.
Las acciones (el resto de la barra de foco), en «Las casillas», abajo.

## Las casillas (decidido el 13-nov-2026)

Lo pidió la persona: que las acciones de foco, cajas punteadas con la palabra en una columna a la derecha, pasaran al
sistema, como íconos con su globo y sin marcos, sin perder arrastrar una tarjeta a una ni los aplazamientos a un clic.
Se le mostraron tres formas en el catálogo (una banda arriba de las tarjetas, un riel de íconos a la derecha, una
columna de filas con ícono y nombre) y **eligió la banda**. El orden de las acciones lo propuso el hilo que la hizo y
quedó así mientras no pida otro.

El componente (`componentes/casillas.ts`, `media/css/casillas.css`, página «casillas» en el catálogo):

- **Qué es**: lo que se le hace a la tarjeta elegida de una lista, que es también donde se suelta una arrastrada. Una
  **banda**, una fila arriba de las tarjetas, como la de herramientas de una lista (buscar, ordenar); si no cabe, sigue
  en la línea de abajo. En un celular, la misma fila, abajo de las tarjetas, siempre a la vista, tras una línea.
- **Cada casilla**: un ícono de la letra en el color de lo que hace (`C` de `web/iconos.ts`: ir azul, cambiar amarillo, el
  agente violeta, hecho verde, quitar rojo, lo demás cian), en su celda cuadrada, sin marco; su nombre y lo que hace, en
  el globo. Al pasar el mouse, el fondo del hover, como un ítem.
- **Grupos**, por lo que hacen, apartados por un corte, y **el mismo orden en los dos modos** (la mano aprende dónde está
  cada una): ver el detalle · hecha · la fecha y el tamaño · pasarla (la instrucción, otra persona) · sacar el primer
  paso (en concentración) y es la misma que… · descartar.
- **Rápidas**: lo que la casilla elegiría casi siempre, en palabras, a un clic y junto a ella, en su color. Junto a nueva
  fecha, «hoy» si venció (antes «va hoy», una casilla aparte) y los aplazamientos (+1, el viernes, el lunes); junto al
  tamaño, el que no tiene («rápida» o «larga», las dos si no tiene ninguno); junto a la instrucción, «trabajarla» (lo
  mismo que «trabajar en un hilo» en la ficha: a su hilo, con «Veamos T84» escrito, y te lleva a él; agregado el 13-nov,
  porque en el celular un ícono sin globo no decía que por ahí se trabajaba en un hilo) y, en concentración, «bloquear
  tiempo», porque es una instrucción hecha (`telar actuar` a su hilo, con `/tarea` y un pedido fijo, de un clic:
  [instruccion.md](instruccion.md)).
- **Padre**: una casilla que solo dice de qué son sus rápidas y no se aprieta, como el ícono padre del orden. El tamaño es
  el reloj de la ficha (`I.tamano`), con «rápida» y «larga» al lado.
- **Arrastrando** no hay globo (el navegador no lo muestra mientras se arrastra): mientras dura, cada casilla dice su
  nombre al lado de su ícono, y la que está debajo se marca como «donde caería», con la marca del ítem (un fondo tenue y
  una línea de un píxel), en el color de la casilla. Si el arrastre sale de las casillas, la marca se va.
- **Haciendo**: mientras una acción va a telar, no se aprietan, y al final de la banda un círculo que gira dice qué pasa.

Lo que se fue: la columna de 34 letras a la derecha (las tarjetas toman el ancho entero), la línea con el título de la
elegida encima de las acciones (ya se ve en su tarjeta), y los íconos repetidos: «es rápida» usaba el ✓ de hecha.

**Falta, pantalla por pantalla** (palabras que un ícono puede decir, marcos que no se abren aparte):

- *tareas · foco*: hecho el 13-nov: las tarjetas son el componente («La tarjeta») y las acciones, una banda de íconos
  arriba de ellas («Las casillas»). El 24-nov la cabecera de los modos pasó a ser pestañas y la banda bajó al pie («Las
  pestañas y la barra de mensaje»).
- *la ficha de una tarea*: hecho el 13-nov (decidido con la persona): las acciones del proveedor con `rol` conocido
  son íconos en la barra de la ficha, con su globo y su número de tecla (esperar a… la pausa, tamaño… el reloj, hecha,
  descartar, y la fecha, la prioridad y el responsable cuando el subtítulo no los muestra), los mismos que en el ⋯; las
  demás siguen con tecla y palabra. «escribirle a Claude» es el ícono de la instrucción.
- *calendario*: «preparar o minuta», «+ nota», «enviar a Secretaría». *ahora*: «procesar la minuta», «entrar ↗», «abrir».
- *proyectos*: «cerrados N» quedó en la fila de filtros; ↔ (la tabla extendida) es una vista de la barra, junto a «gantt»
  (26-nov, la etapa 4 de [la auditoría](auditoria-proyectos.md)).
- *productos*: «+ idea» es el + de crear (sin la palabra); servicios · backlog · tablero son sus vistas, pero viven dentro
  del lienzo: falta que un módulo pueda declarar sus vistas (y el ícono de su pestaña, que hoy va con su nombre: «gantt»).
- *fuera del dashboard*: la vista de un objeto (`web/objeto.ts`) y la de una carpeta (`web/carpeta.ts`) siguen con
  «‹ volver» y recuadro.

## Las pestañas y la barra de mensaje (pedido el 24-nov-2026)

Lo pidió la persona, mirando la ficha de una tarea en foco: «La fila de tabs (gestión, concentración) debería ser del alto
standard de filas, con borde abajo. Este componente de tabs ya debería existir pues lo usamos en varios lugares. La barra
de acciones debería estar abajo, también una fila propia de alto standard. Abajo de ella debería haber un input que
permita enviar un mensaje a un hilo existente o uno nuevo [...] con la capacidad de elegir un destino (hilo nuevo, hilo
existente, o agente); debería también ser standard, pues la vamos a comenzar a utilizar más (en vez del modal que hoy
existe para enviar un mensaje a un agente del contexto actual)».

**Las pestañas** (`componentes/pestanas.ts`, `pestanas.css`, `web/pestanas.ts`; página «pestañas» en el catálogo, con
«dónde está»): no existían; había nueve filas hechas cada una a su manera, sin dos iguales (subrayado de acento, violeta,
un chip azul lleno, el fondo de la selección) y ninguna con teclado. Ahora:

- **Una fila del alto de las barras** (`--pantalla-barra-alto`), con su línea abajo de borde a borde: debajo de la barra
  de una pantalla se lee como una segunda barra. Cada pestaña ocupa el alto entero.
- **La abierta, con la superficie de la selección** (la del ítem activo, con la marca de su tema: la gramática ya decía
  «la fila donde estás, la pestaña abierta»); las demás, tenues, y al pasar el mouse el fondo del hover. Ni otra letra ni
  otro peso.
- **Cada una**: un ícono opcional (en su tinta, si la trae), su nombre, su cuenta (tenue, o en el de cuidado si pide), un
  punto en la esquina si hay algo nuevo; apagada si está por hacer. Al otro extremo de la fila, lo suyo (plegar, ↻).
- **El teclado**: un `tablist` de ARIA. ⇥ llega a la abierta; ← → pasan a la de al lado y la abren, Inicio y Fin a la
  primera y la última; solo con el foco en una, así que no le quitan nada a la terminal ni a los atajos.
- **Si no caben**: primero las de ícono quedan en su ícono y su cuenta (el nombre, en el globo), salvo la abierta; si
  aún no, la fila corre de lado sin barra a la vista y la abierta se trae a la vista.
- **Migradas**: foco, las páginas del catálogo, las hojas de un hilo (ficha, códigos, contexto), el detalle de un
  proyecto y el lado del visor abierto. **Faltan**: ⚙ modos en el teléfono y el selector de mundo de ⚙ (cada opción con
  el color de su mundo). **No lo son**: las vistas de una pantalla (íconos en su barra, ya son su componente), la banda de
  modos, el menú de ⚙, día/semana de los periódicos (van a la barra de su pantalla) y los filtros.

**La barra de mensaje** (`componentes/mensaje.ts`, `mensaje.css`, `web/mensaje.ts`; página «barra de mensaje» en el
catálogo, con «la lista» y «dónde va»): la instrucción ([instruccion.md](instruccion.md)) en otra forma, una fila al pie
de una pantalla. Lo que manda es lo mismo (`telar actuar`: la dirección o la fila de la cosa, más lo escrito) y al mismo
destino de fábrica; cambia la forma: sin skill ni «dejarla escrita» (lo escrito llega tal cual; un «/tarea …» empieza con
la skill). El destino es un chip compacto en la misma fila, en la tinta de lo que es (un hilo azul, uno nuevo verde, un
agente violeta); un clic abre `ui.menu` junto a él: su hilo, uno nuevo, y los hilos y los agentes en el orden y con los
íconos de ⌘K (`web/buscador-hilos.ts`, que ⌘K y la barra comparten), solo los del mundo puesto, también en el modo todo, y
nunca los de un agente que pide esconderse. ⏎ envía y ⇧⏎ es una línea nueva, como la caja de la terminal (la regla de una
caja en una fila; ⌘⏎ también envía); ⎋ suelta el campo. No toma el foco sola, y las letras escritas en ella no llegan a los
atajos del dashboard (⌘K sí). Después de enviar, arriba del campo, a quién fue (su nombre abre su hilo) y cómo; si falla,
por qué, y lo escrito vuelve. Lo escrito es el borrador de la cosa, el mismo de la ventana de la instrucción. Recién
abierta la página, o si el destino pedido no aparece, espera en vez de caer en otro (un hilo nuevo, por ejemplo).

**La ficha en foco**, de arriba abajo: la barra de la pantalla, las pestañas (gestión, concentración), las tarjetas que
corren, las acciones de la elegida en su fila (las casillas, ya no arriba) y la barra de mensaje con la elegida como
contexto. Igual en el laptop y en el teléfono.

**Dónde más va la barra** (propuesto; la ventana de la instrucción no se quita todavía): la ficha de una tarea, el
detalle de un proyecto, la ventana de un chat de foco (bajo la caja de responder, con el chat como contexto libre), la
pestaña de un módulo (`window.lienzo.pedir("instruccion")`), una espera en «te esperan» y Táctica, el visor de un
documento y la hoja de un agente («encargar», con el destino fijo). La lista con el porqué de cada uno, en el catálogo.

## Los submenús (decidido el 13-nov-2026)

Lo pidió la persona: que ARCHIVO sea un submenú dentro de HILOS, porque los archivados también son hilos, y antes de
moverlo, que el sistema diga cómo se maneja un submenú. Un **submenú** es una sección dentro de otra, con su cabecera
plegable. Se le mostraron tres maneras de su cabecera en el catálogo, en la barra, la barra angosta y el teléfono: una
carpeta en la lista, una sección adentro (una cabecera como las grandes, en gris, un paso adentro y con una línea corta
arriba) y un pliegue a la derecha (el ícono de lo que es al inicio y la flecha al final). **Eligió la carpeta.**

El componente (la variante `submenu` del ítem: `componentes/item.ts`, `.item.submenu` en `item.css`, el token
`--item-submenu`; la página «sección de lista», pestaña «submenú», en el catálogo, y en la gramática, la parte
«submenú»):

- **Su cabecera es una fila más** de la lista: la flecha de plegar en la última ranura, justo antes de los nombres (si
  esa ranura es ancha, la de las máquinas, la flecha va pegada a su borde derecho), y su nombre en la columna de los
  nombres, en la tinta de las cabeceras, en minúscula y sin negrita. Ni línea ni sangría nuevas: se ve que es parte de
  la sección porque está en su grilla.
- **Sus filas**, en la misma grilla que las de la sección (la prioridad, el estado, dónde vive y el nombre, en las mismas
  columnas): son hilos. No se sangran, porque la sangría con ↳ sigue queriendo decir «hijo de».
- **Su cuenta**, tenue, después del título, como en las cabeceras grandes. La de HILOS sigue siendo la de los abiertos.
- **Se pliega** con un clic en toda su fila, empieza plegado, y se pliega con la sección de afuera. Como toda cabecera
  de la barra, grande o submenú, se recuerda como la dejó la persona, también al recargar (en ese navegador, el del
  teléfono incluido; lo que vuelve a como empieza se olvida).
- **Sin herramientas propias** (19-nov-2026, lo pidió la persona: dos buscadores en la misma sección confundían): el buscar
  y el orden de la sección valen también para él. Con algo escrito, se ve abierto con solo lo que calza, y esa cuenta (si
  nada calza, no sale); plegarlo ahí dura lo que dura lo escrito, y al borrarlo vuelve a como lo dejó la persona.
- **Un solo nivel**: un submenú no lleva submenús adentro.

En la barra, ARCHIVO es el submenú de HILOS, al final, con su ancla (`#archivo`), su cuenta y lo que salta a él
(`telar.archivo`, que abre también HILOS si estaba plegada).

**Pendiente**: una sección propia (un grupo de hilos de `[secciones]`, o una vista con `aparece = "hilos"`) también es
un grupo de hilos, y podría ser un submenú de HILOS, antes de ARCHIVO, con su home como el ícono de la casa en su
cabecera. Queda como sección grande: hoy nadie las usa.

La cabecera de una sección (grande o submenú) deja entre su flecha y su título la misma media celda que las filas dejan
entre sus íconos y su nombre.

## El día en una línea (decidido el 17-nov-2026)

Lo pidió la persona: saber de un vistazo cuánto tiempo libre tiene hasta la próxima reunión y qué viene después, con
un calendario del día en una sola línea, como una barra de carga (la barra entera es el día, con la hora de ahora
marcada), en la cabecera de la página. Se le mostraron tres barras en el catálogo, con el mismo texto: una barra fina
que se llena, una franja del alto de la línea con la hora de cada reunión adentro, y una en letras de terminal (█ ▒ ░ │).
**Eligió la barra fina**, que solo las reuniones con otras personas corten lo libre, que un día sin reuniones no muestre
nada, y las unidades pegadas al número («1h 20», «45min»).

El componente es la **jornada** (`componentes/jornada.ts`, `media/css/jornada.css`, tokens `--jornada-…`, página «el día
en una línea» en el catálogo, con «estados» y «en la cabecera»); lo pone en la cabecera `web/jornada.ts`:

- **Qué dice**: lo de ahora y lo que sigue. Libre: «libre 1h 20 → 11:30 Revisión de diseño · 15:00 Comité». En una
  reunión: «en Revisión de diseño 45min → 12:30 libre 2h 30 → 15:00 Comité». Pasada la última, con la jornada andando:
  «libre el resto del día». Lo que dura, en el color de lo que es: lo libre en el de lo bueno (en el del cuidado si
  quedan menos de diez minutos), la reunión en su azul; las palabras que unen, tenues.
- **La barra**: fina, la jornada entera (8:30 a 18:00, la de la semana del calendario, estirada si una reunión cae
  afuera). La pista es lo libre que viene; lo que ya pasó se llena, tenue; las reuniones en su azul y lo propio tenue;
  ahora, una raya del alto de la línea. Su globo lista el día.
- **Qué cuenta**: reunión es lo que es con otras personas (una cita, `clases.ts`); un bloque propio y la rutina (el
  almuerzo) se dibujan, tenues, pero no cortan lo libre. Las que se pisan son un solo rato ocupado.
- **Cuándo no dice nada**: sin calendario declarado, un día sin reuniones, y pasadas la última reunión y la jornada.
  Antes de la jornada sí: lo libre hasta la primera.
- **Los datos**: la agenda de hoy de `telar hoy`, la misma del dashboard (`vistas/dashboard/dia.ts`, con su caché: a los
  proveedores se les pregunta cada cinco minutos). Se repinta al cambiar el minuto y al volver a la página. Un clic
  lleva al calendario.
- **Cómo se aprieta** (es un contenedor): con menos ancho se va lo que viene más tarde, después el nombre de lo que sigue y
  las palabras («1h 20 → 11:30»), después la barra, después hasta cuándo («1h 20»). En la cabecera es lo primero que
  cede: pide su ancho y se resume antes que la máquina, lo que se ve y la marca, hasta quedar en «1h 20», que no suelta;
  los botones, nunca.

## Las ventanas (primera pieza, noche del 17-nov-2026)

El paso 7, solo lo aditivo: **el marco**, sin migrar ninguna ventana (Telar pidió aviso antes de tocar `web/instruccion.ts`,
`web/interfaz.ts` y `web/buscador.ts`). `componentes/ventana.ts` y `media/css/ventana.css`, con tokens `--ventana-…`, y su página
en el catálogo.

- `ventana({ lugar?, titulo?, ayuda?, campo?, cuerpo?, pie? })` da el HTML de lo que va *dentro* de un `<dialog>`: cabecera, campo,
  cuerpo y pie, en ese orden, cada uno solo si se pide. Abrirlo, el foco, ⎋ y el clic fuera siguen siendo de quien la usa.
- Tres lugares, que solo cambian dónde cae y cuánto ocupa: `centrada` (campo, aviso), `arriba` (⌘K) y `junto` al clic (el menú ⋯,
  con su sombra dura). Una ventana es lo único con marco; su fondo es el de las barras.
- `paleta({ placeholder, filas, sel, vacia, detalle })` es la ventana con campo (la barra de un buscador, `barraBuscar()`) y
  filas (`item()`): ⌘K, `elegir` y el menú ⋯ son ese patrón. `pieVentana([...])` arma los botones de abajo, con su tecla.
- **Abrirla** (decidido el 17-nov): `abrirVentana(props, { junto?, foco?, clase?, montar?, puedeCerrar? })`, en `web/ventana.ts`, es
  la pieza de DOM de todas las ventanas: crea el `<dialog>` con lo que da `ventana(props)`, `showModal` si va `centrada` o `arriba` y
  `show` si va `junto` al clic, pone el foco, la cierra con ⎋ y con un clic fuera (salvo que `puedeCerrar` diga que no) y devuelve una
  promesa con lo elegido; un clic en un `[data-accion]` de adentro (`pieVentana`) la cierra con esa acción. `ventana()` sigue pura. La
  primera que la usa es la de contestar lo que te espera (`componentes/contestar.ts`, su página en el catálogo bajo «ventana»).
- **Migradas** (noche del 18-nov): `campo`, `escribir` y `preguntar` (el aviso con botones, `ui.aviso/info/falla`) de `web/interfaz.ts`
  son ventanas sobre `abrirVentana`, con `clase: 'ventana-texto'` (sus campos, en `ventana.css`). Siguen lo de antes: ⏎ en el campo
  no sigue a la página (`stopPropagation`), ⏎ en un botón lo hace, el foco parte en «cancelar» con `foco: 'cancelar'` (`prueba:confirmar`,
  cuyo DOM de mentira ahora lee lo justo de `innerHTML`). `pieVentana` y los botones de `preguntar` llevan `tabindex=0`. Cambia el
  ancho (ahora el de la ventana, 64ch) y el color de línea (el acento).
- **Migrada** (noche del 19-nov): `elegir` de `web/interfaz.ts` es una ventana sobre `abrirVentana` (`clase: 'ventana-elegir'`, en
  `ventana.css`): título, campo (`barraBuscar`) y cuerpo con la lista y el detalle. La lista sigue pintándose con DOM en `montar`
  con las filas `.web-op` de `web.css` (aún no son `item()`: es lo que falta para llamarla `paleta()` de verdad). Se borró `caja()`.
  Igual que antes: ↑ ↓ ⏎ ⎋, ⏎ no sigue a la página, `inicial` a la vista, detalle de la marcada. Cambia: ancho (el de la ventana),
  filas alineadas con el título y línea con `--borde`.
- **Migrada** (noche del 20-nov): ⌘K (`web/buscador.ts`) es una ventana `arriba` sobre `abrirVentana` (`clase: 'ventana-buscador'`, en
  `ventana.css`; se fue `dialog.buscador-k` de `marco.css`). Campo = `barraBuscar`, lista en grupos por fuente con filas `item()` (el
  ícono en la ranura, en el color del grupo; el detalle como sufijo tenue), teclas en el pie. `Remotas`, `puntaje` y las fuentes no
  cambiaron (`prueba:buscador`). Cambia: la caja ya no se ajusta a celdas enteras de la trama (se fue `cuadricula()`; la trama ░ sigue
  de fondo), el ancho es el de la ventana `arriba` (80ch) y el alto de la lista es fijo (16 líneas) en vez de crecer con el contenido.
  **Decidir de día**: si la caja ajustada a la cuadrícula valía la pena (era un detalle de la trama, no de la función).
- **Migrada** (noche del 21-nov): el menú ⋯ (`menu()` de `web/interfaz.ts`) es una ventana `junto` sobre `abrirVentana` (`clase: 'ventana-menu'`,
  en `ventana.css`; se fue `dialog.web-menu` de `web.css`). Título tenue, campo (`barraBuscar`) y filas `item()`: el ícono (o la señal) en la
  ranura, la descripción como sufijo tenue, el color de lo que hace (`--c`) en ranura y título; los separadores, `.m-sep`. Igual que antes:
  ↑ ↓ ⏎ ⎋, escribir filtra, ninguna tecla sigue a la página, un clic fuera o perder el foco de la página la cierra. Cambia: `abrirVentana`
  ahora, si una `junto` no cabe debajo, la pone **encima** del punto (antes la desplazaba sobre él; el menú ya lo hacía a mano), y el
  menú lleva el borde, la sombra y el fondo de una ventana en vez de los suyos.
- **El visor de documentos** (23-nov, a pedido de la persona: «es confuso volver al hilo desde donde lo abriste») es una
  ventana sobre `abrirVentana` (`clase: 'ventana-documento'`, en `documento.css`): ancha para leer (`--documento-ancho`,
  100ch) y del alto de la pantalla, en el teléfono la pantalla entera. Su primera fila es la barra de una pantalla
  (`barra()` de `componentes/pantalla.ts`) con el nombre del archivo en el tenue de su resumen, «‹» en su `volver` y la ✕
  como acción; sus botones (los de la tarjeta de un comentario) son `pieBotones` con `datos` en vez de `accion`, para que
  un clic no cierre la ventana. Un arrastre que empieza adentro y se suelta afuera (seleccionar para comentar) no es un
  clic fuera (`puedeCerrar`). **La prosa** (`media/css/prosa.css`, en la capa base, con `--prosa-…` en `tokens.css`): la
  letra y el markdown para leer con calma, sacados de la lectura de un hilo para que los use también el visor en su
  modo lectura (`.prosa`, el bloque; `.prosa-md`, su markdown).
- **24-nov**: `elegir` arma sus filas con `item()` (como el menú ⋯; `.e-lista`, `.e-fila`, `.e-detalle` en `ventana.css`).
- **Falta**: la instrucción
  (`web/instruccion.ts`, última y de día con Telar). `caja()` ya no existe, pero la instrucción aún usa la clase `.web-caja`: cuando se
  vaya, se borra lo de `.web-caja`, `.web-op`, `.web-lista` y `dialog.buscador`.

## Los botones (propuesta del 20-nov-2026; elegida «la tecla en el pie» el 22-nov)

Lo pidió la persona: «los popups para borrar, con borrar y cancelar, deberían ceñirse más al sistema de diseño.
Probablemente el sistema de diseño necesita una definición de botones que no sean simplemente íconos». El catálogo tiene la
página **botones (propuesta)** (`/componentes#botones`, en piezas), con cuatro pestañas: alternativas, estados, el foco y ⏎,
y hoy. Nada de la página cambió todavía: lo usa solo el catálogo, y la persona elige.

**Hoy** (el catastro entero, con archivo:línea, en la pestaña «hoy»; `componentes/catalogo-botones.ts`, `CONFIRMACIONES` y
`FORMAS_HOY`): 31 confirmaciones (26 filas) pasan por `preguntar` (`web/interfaz.ts`, vía `ui.aviso/info/falla` con botones) y cinco
no (la mudanza, soltar en la terminal, quitar una cuenta con `elegir`, la instrucción, contestar). El pie de `preguntar` son
`<a>` en el acento, sin tecla y sin el color de lo que hacen: «Borrar» (con mayúscula) y «cancelar» se ven iguales. El foco
parte en «cancelar» en lo que destruye, pero se marca con un contorno de `:focus-visible`, que Chrome no dibuja si la ventana
se abrió con un clic en un `<button>` o un `<a href>` (probado aquí): ahí no se ve que ⏎ cancela. Los botones con texto
tienen **nueve formas** (palabra en el acento, el pie de una ventana, palabra tenue que se enciende, palabra en el color de
lo que hace, tecla en caja y palabra, botón con borde, chip con fondo, opción con círculo, fila de ancho completo). Lo que
destruye es rojo solo en contestar y en la mudanza (ahí, para *no* hacerlo); «cancelar» va en cuatro colores; la tecla va
delante, detrás, en caja o del color de la palabra; ninguno tiene esquinas redondeadas.

**El componente**, como se propuso (cómo quedó, abajo, en «Lo que se eligió»; `componentes/boton.ts`, `media/css/boton.css`):
`boton(forma, { texto, accion, tono, color?, tecla?, icono?, ayuda?, estado? })` da un `<button type="button">` (⏎ y espacio
lo aprietan solos; `disabled` lo apaga), con la primera letra en minúscula. `tono` es lo que hace: `peligro` (destruye, en el
de peligro), `accion` (en el acento, o en el color de su clase con `color`: archivar es «cambiar», amarillo, como en el menú
⋯) o `callado` (cancelar, en el del texto). `pieBotones(forma, botones)` es el pie de una ventana. Las cuatro formas llevan
las mismas props y cada una dibuja lo suyo:

| forma | cómo es | a favor | en contra |
|---|---|---|---|
| la palabra | la palabra sola en su color; al pasar, una línea tenue abajo; con el foco, la línea en su color | lo más callado; la línea del buscador | se lee como un enlace; mouse y foco se distinguen solo por el color de una línea de 1 px; en el teléfono no hay dónde apretar |
| con borde | un marco de 1 px del color de la acción; al pasar, el hover; con el foco, su color tenue de fondo | inconfundible | marcos dentro del marco (lo único con marco es la ventana); el botón de cualquier otra app |
| la tecla en el pie | el pie es una banda (su línea de borde a borde) partida en celdas: «⌘⌫ borrar · ⎋ cancelar»; al pasar, el hover en la celda; con el foco, su color tenue en la celda entera | enseña la tecla donde ⌘K ya la muestra; la banda partida es la gramática; la celda entera se aprieta (en el teléfono se reparten el ancho) | lo que destruye necesita un acorde (⌘⌫), porque ⏎ es del foco; en el teléfono la tecla sobra (se calla); pesa más que dos palabras |
| ícono y palabra | el ícono de la letra y la palabra, en su color; hover y foco como la anterior | la gramática entera; contestar ya es así | dos signos para lo mismo; cancelar necesita un ícono (✕ ya es «cerrar») |

**Se recomienda la tecla en el pie**: es como la página ya dice qué hace cada tecla (el pie de ⌘K, «⌘⏎ enviar»), parte el
pie como la gramática parte una banda, da al dedo una celda entera y obliga a que lo que destruye tenga su propio acorde. Del
ícono y la palabra se queda con el color de lo que se hace.

**El foco y ⏎**, para la forma que se elija (pestaña «el foco y ⏎»; «probar» abre la ventana de verdad y las sigue):

- ⏎ hace el botón que tiene el foco, y solo ese (como hoy `preguntar`, y `prueba:confirmar`).
- En lo que destruye, el foco parte en cancelar; lo que destruye tiene su acorde, ⌘⌫ (el de macOS para la papelera; ⌘⏎ ya es
  enviar), nunca ⏎ solo. Un ⏎ con `repeat` (sostenido desde antes de abrirse) no aprieta nada.
- El foco se marca con `:focus`, no `:focus-visible`, para que se vea siempre qué hace ⏎.
- El mouse y el foco nunca se ven iguales: al pasar, el gris del hover; con el foco, el color del botón tenue, y cancelar, que no
  tiene color, el del acento (el foco de la página).
- Siempre el mismo orden: lo que hace, y cancelar al último, en el borde derecho; ⇥ pasa de uno al otro.
- Mientras se hace, no se aprieta otra vez: se apaga y, en la forma «tecla», el círculo que gira toma el lugar de la tecla.

**Lo que se eligió (22-nov-2026)**: la forma (c), «la tecla en el pie», con una condición: «cuida bien el espacio
entre la barra inferior con los botones y el contenido: debería haber un espacio». Se hizo en la rama `botones-pie`:

- **El componente** es uno solo: `boton(props)` y `pieBotones(botones, { izq?, clase? })` (`componentes/boton.ts`; las otras
  tres formas se sacaron del código, y el catálogo las nombra como descartadas, con por qué). La banda va a **una línea vacía**
  del contenido (`--boton-pie-aire: var(--e-3)`, en `tokens.css` con los demás `--boton-…`), tras una línea de borde a borde;
  las celdas, a la derecha, cada una con su línea a la izquierda hasta el borde de la ventana; lo que va antes de las celdas
  (contestar: conversarlo, ir al hilo; la instrucción: dejarla escrita) va a la izquierda (`izq`). El aire queda fuera de lo
  que se desplaza: con contenido largo, el cuerpo se desplaza y la banda sigue a una línea de él. En el teléfono las celdas
  se reparten el ancho en una fila (una palabra larga baja dentro de su celda), la tecla se calla y lo de la izquierda sube a
  su propia fila. Medido con `scripts/medir.py` en el laptop y en el teléfono: 16,9 px (1lh) entre el cuerpo y la línea, en
  todas. Un botón sin tecla (de la página) lleva su ícono en el lugar de la tecla; mientras se hace, el círculo que gira.
- **Las teclas** las atiende `web/botonera.ts` (`teclasDeBotones`), que `abrirVentana` pone en cada ventana antes que lo de
  quien la usa (es el único cambio en `web/ventana.ts`); la instrucción, la mudanza y la franja de soltar, que todavía no son
  ventanas, lo ponen ellas. La tecla de cada celda la aprieta, tenga o no el foco; ⏎ aprieta el que tiene el foco; una tecla
  sostenida (`repeat`) no aprieta nada; ⎋ es de la ventana (en una franja, su botón de ⎋). `boton()` no deja que un botón de
  peligro diga ⏎ (pasa a ⌘⌫).
- **Qué destruye** (la lista entera, con por qué, en la pestaña «las que destruyen» del catálogo, `CONFIRMACIONES`): borrar un
  estilo, un modo (o volverlo de fábrica), un mundo, un proceso periódico o un tema propio; quitar un módulo; quitarle la cuenta
  a alguien; descartar mensajes retenidos (desde «te esperan» y desde contestar); descartar un hilo; eliminar un agente;
  cancelar un encargo; y una acción de tarea u objeto que pide confirmar si su verbo destruye (`DESTRUYE`, en `boton.ts`).
  Esas van en el de peligro, con ⌘⌫, y el foco parte en cancelar (`ui.aviso(…, { destruye: true })`). **Pide mirar** (el foco
  en cancelar, sin rojo, con ⌘⏎ o su número): el permiso que pide un módulo, y una acción de afuera que no destruye. **Hace**
  (el foco en lo que hace, con ⏎): rotar (la conversación queda en disco y sigue con su relevo), archivar, marcar hecha,
  consolidar, traer o llevar igual (lo que no viaja sigue en la otra máquina), instalar telar o un módulo, encargar otra vez.
- **Dónde está**: `preguntar` (todas las de `ui.aviso/info/falla` con botones: una sola acción, ⏎; varias, 1 2 3; cancelar al
  último con ⎋), `pieVentana` (el pulso: «⎋ listo»), `escribir` («⌘⏎ enviar»), contestar («⏎ soltarlo», o «⌘⌫ descartarlo» en
  el de peligro, que ⏎ no hace), la instrucción («⌘⏎ mandar»), la mudanza («⏎ llevar igual · ⎋ no llevarlo»: antes «no
  llevarlo» iba en rojo), soltar en la terminal («⏎ guardar · ⎋ no»), quitarle la cuenta a alguien (era un «elegir» con el «no»
  marcado), la terminal que no abre («reintentar · retomar»), ⚙ temas (sus pies y sus botones sueltos) y el «eliminar» de
  agentes, ahora rojo de verdad. Cancelar es uno solo: ⎋, en el color del texto. `prueba:confirmar` lo revisa entero: cada
  forma de confirmar con sus teclas, cada confirmación de la página contra el catastro (la que dice un verbo que destruye tiene
  que pedirlo, y un archivo con una confirmación que no está en el catastro falla), y las que no pasan por `preguntar`.
- **Queda afuera**: los botones con texto que no son de una ventana siguen con su forma (las teclas en caja de la ficha de una
  tarea, de periódicos y de equipo; las palabras de táctica; los enlaces de ⚙; los chips; las opciones con círculo). Las de
  la ficha y periódicos ya son «tecla y palabra» y son las siguientes naturales. La mudanza, la franja de soltar y la
  instrucción no pasaron a `abrirVentana`: eso es del paso 7, del hilo nocturno.

## La jerarquía (primera propuesta; la revisión de la interfaz la corrige)

```
fundamentos     gramática visual (rectángulos y círculos: palabras, composición, modos, con rectángulos,
                derivadas) · círculo · tokens · temas · densidades · letra e íconos
piezas          ícono · acción (botón de ícono o de palabra) · chip / etiqueta · campo · interruptor · nuevo (+)
compuestos      ítem · tarjeta (un ítem que no se corta) · casillas (lo que se le hace a la elegida, donde se suelta
                una tarjeta) · buscador (campo + lo que filtra) · orden (ícono padre + opciones)
                · herramientas (buscador + orden + nuevo, bajo una cabecera)
secciones       sección de lista: cabecera (un ítem) · herramientas · filas · «vacía» · separador; con su fondo
                · cabecera de tabla (encabezados de columna que ordenan; palabras, ancho variable; después de sección)
contenedores    barra (secciones) · pantalla (barra arriba, cuerpo sin margen: un hilo, una app) · ventana (modal: cabecera, campo, lista, pie con las teclas) → paleta de
                comandos (⌘K), elegir (ui.elegir), confirmar (ui.aviso), menú ⋯ · hoja (la ficha y los códigos, a la
                derecha)
vistas          barra de hilos · dashboard (pestañas) · un hilo · configuración
```

Cada componente se arma con los de arriba: el ítem usa íconos, acciones y el círculo; la sección usa ítems y
herramientas; la ventana usa el campo y el ítem. El catálogo los lista así, a la izquierda, y cada uno tiene su
página: su anatomía (como la del ítem), sus estados × temas × densidades, sus props y dónde se usa.

## Dónde están hoy (para empezar la revisión; no es completo)

- **Buscadores**: la barra de hilos (`.herram input`, `vistas/hilos.ts` y `hilos.css`), las tareas del dashboard
  (`#buscar`, `vistas/dashboard/vista.ts`), ⌘K (`web/buscador.ts`, `dialog.buscador` en `marco.css`), y fuera de la
  página, en los lienzos de los módulos (la pestaña de WhatsApp tiene dos: buscar en todo y filtrar chats).
- **Ordenar**: los órdenes de un grupo en la barra (`.ord`: a-z, reciente, prioridad, máquina), y las listas del
  dashboard que ordenan (tareas, proyectos).
- **Nuevo**: «+ nuevo» en las cabeceras HILOS y AGENTES (fijas del ítem cabecera), y en la configuración.
- **Secciones**: las de la barra (cabecera + herramientas + filas + `.sep`), los bloques del dashboard.
- **Ventanas**: ⌘K, `ui.aviso` (confirmar), `ui.elegir` (elegir de una lista), el menú ⋯ (`web/ordenes.ts`), las
  hojas de la derecha (`web/lado.ts`).

Los lienzos de los módulos (WhatsApp, gantt, productos…) tienen su HTML y su CSS propios: no pueden importar los
componentes. Llevarles la librería (una hoja de estilos de telar que se les ofrece, o un `window.lienzo.componentes`)
es un paso aparte, al final.

## El orden de trabajo

1. **La revisión**: recorrer `pagina/src/vistas/`, `pagina/src/web/` y `media/css/`, y llenar el inventario de
   abajo: cada patrón repetido, dónde aparece (archivo:línea), sus variantes, y a qué componente iría. Corrige la
   jerarquía de arriba.
2. **El catálogo con la lista a la izquierda**: la navegación por jerarquía, una página por componente; lo que hoy son
   secciones (anatomía, círculo, ítem, barra, tokens) pasan a ser páginas de esa lista.
3. **Orden**: el componente (ícono padre «ordenar» + opciones, en su fondo; tokens `--orden-…`), en el catálogo y en
   la barra de hilos.
4. **Buscador**: el componente, en el catálogo, en la barra y en las tareas.
5. **Nuevo**: el botón (un «+», con su ayuda), en las cabeceras.
6. **Sección de lista**: cabecera, herramientas, filas, vacía, separador y fondo; la barra de hilos armada con ellas.
7. **Ventana**: el modal de ⌘K como componente general, y `ui.elegir`, `ui.aviso` y el menú ⋯ armados con él.
8. **Los lienzos de los módulos**: cómo les llega la librería.

Cada paso deja la página igual salvo lo que el paso cambia a propósito (medido como el A/B del ítem: alturas y
posiciones de la barra, y capturas antes y después), con su página en el catálogo y sus pruebas.

## La noche

La corre el periódico **componentes-noche** del servidor (01:00), en el hilo «◑ componentes», en esta carpeta. Nadie
está mirando: no se pregunta nada, se deja escrito.

1. **Dónde**: un worktree en `~/worktrees/telar-componentes`, rama `noche/componentes` (si no existe:
   `git worktree add ~/worktrees/telar-componentes -b noche/componentes main`). Al empezar, `git merge main` para
   traer lo del día; si hay conflicto, se para ahí y se reporta. `npm ci` en `pagina/` si cambió el package-lock.
2. **Qué**: lo siguiente del «Orden de trabajo» según la bitácora de abajo; uno o dos pasos bien hechos, no cinco a
   medias. Se pueden usar subagentes para la revisión (hay tokens), pero lo que se escribe en el código se lee
   entero antes de commitearlo.
3. **Verificar**: `npm run tipos`, `npm run lint:css`, `npm run prueba:componentes` (y las demás `prueba:*`),
   `npm run navegador`, y las de Python desde la raíz del repo. Y **mirarlo**: `python3 scripts/dev.py --puerto 18790`
   desde el worktree (antes, `ss -ltnp` para ver que el puerto esté libre), capturas con `agent-browser` de
   `/componentes` y de la página real (`http://<ip de tailscale>:18790/?k=<llave>`), antes y después, en
   `~/worktrees/capturas/<fecha>/`. En el dashboard **nunca se escribe** (cada letra es un atajo que encarga trabajo de
   verdad): solo clics y JavaScript. Al terminar: `agent-browser close` y detener dev.py.
4. **Commits** en la rama, por paso, con mensajes que digan qué cambió. **No** se mergea a main, **no** se despliega,
   **no** se hace push a ningún lado, **no** se reinicia ningún servicio: eso es de día, con la persona.
5. **Al final**: una entrada en `NOCHE.md`, en la raíz del worktree (fuera de git: `.git/info/exclude`; es la
   memoria de una noche a la otra: qué se hizo, qué quedó a medias, qué sigue), y `telar mensaje Telar "…"` con lo
   hecho, lo que se ve distinto, dónde están las capturas, lo que falta decidir y el comando para mirarlo. El
   inventario (paso 1) sí va en este documento, en la rama. Si el plan está completo,
   `telar periodicos pausar componentes-noche` y decirlo.

## Inventario

Revisión de la noche del 11-nov-2026 (paso 1), sobre `pagina/src/vistas/`, `pagina/src/web/` y `media/css/`. Rutas
relativas a `pagina/`. Los números de línea son de ese día.

### Buscador (paso 4)

Cinco buscadores de página, cada uno con su CSS y su manejo del teclado; ninguno comparte código.

| Dónde | Marca | Variante |
|---|---|---|
| barra de hilos, uno por grupo | `src/vistas/hilos.ts:449` (`input.buscar`, `data-grupo`), eventos `:151-157`, `:219-255`; CSS `media/css/hilos.css:19-23` | placeholder «buscar»; ⎋ borra, ⏎ abre el primero; conserva foco y cursor al repintar la lista |
| tareas del dashboard | `src/vistas/dashboard/tareas.ts:556` (`#buscar-t`) y `#buscar` (`dia.css:45-48`) | prefijo «/ buscar», cuenta al lado (`#tareas-t-cuenta`); `/` enfoca |
| proyectos del dashboard | `src/vistas/dashboard/proyectos.ts:88` (`#buscar-p`), CSS `dia.css:322-325` | «/ buscar en los N» |
| bloques de correo | `src/vistas/dashboard/bloques.ts:164` (`.buscar-c`, `.buscar-c-cuenta`), CSS `dia.css:316-320` | color del borde por bloque (`--c`) |
| configuración | `media/css/configuracion.css:73` (`#buscar-mod`) | ancho completo |
| ⌘K | `src/web/buscador.ts`, `dialog.buscador` en `marco.css:275` | es una ventana, ver abajo |

Los cuatro de dashboard repiten lo mismo (input sin borde con línea inferior, `:focus` azul, `::placeholder` tenue) en
`dia.css` con ids distintos; el de hilos, en `hilos.css` con `--acento`. El estado de cada uno se restaura a mano al
repintar (`vista.ts:474-566`). **Componente**: `buscador({ clave, placeholder, cuenta?, atajo? })` — campo + cuenta
+ el manejo de ⎋, ⏎ y `/`, con su estado guardado por clave.

### Orden (paso 3)

- Barra de hilos: `.ord` por grupo, `ORDENES` (a-z, reciente, prioridad, máquina), `hilos.ts:44-85` y `:450`; CSS
  `hilos.css:24-25`. Clic otra vez vuelve al orden de telar.
- Cabecera de proyectos: `proyectos.ts:103-107`, un ícono `I.ordenar` por columna (`data-orden-p`), que cambia a
  `I.asc`/`I.desc` al activarse (`vista.ts:215-218`).
- Cabecera de tareas: `tareas.ts:562` (`data-orden-c`) y los botones `data-orden-t` (`vista.ts:111`, `:192`).

Tres formas de lo mismo (ícono suelto, encabezado de columna que se vuelve texto, botones de modo); ninguna dice «esto
ordena». **Componente**: `orden({ opciones, activa, sentido })` con su ícono padre, entre dos líneas cortas en su púrpura (`--orden-linea`).

### Nuevo (paso 5)

`+ nuevo` como fija del ítem cabecera: `hilos.ts:539` (agente residente, `telar.agenteNuevo`) y `:608` (hilo,
`telar.nuevo`). Fuera de la barra el patrón es otro: «estilo nuevo…» como enlace de texto en configuración
(`config/glifos.ts:141`), «Proyecto nuevo…» como fila de `ui.elegir` (`reuniones.ts:44`). **Componente**: `nuevo({ id,
ayuda })`, un «+» con su ayuda; los enlaces de texto de configuración pasan a usarlo.

### Sección de lista (paso 6)

Hecha para la barra (arriba, «Lo que ya está»); lo de abajo es como era el 11-nov. Solo existe en la barra (`hilos.ts`: `cabecera(...)` + `.herram` + filas + `.sep`, y `hilos.css:15-23`). En el dashboard
los bloques (`bloques.ts`, `vista.ts`) repiten la idea con otras clases (`.sep-pag`, `dia.css:77`; `.tareas-cab`,
`.proy-cab`). **Componente**: `seccion({ cabecera, herramientas, filas, vacia })`; `herramientas` = buscador + orden +
nuevo en una fila.

### Ventanas (paso 7)

Seis `<dialog>` armados cada uno a mano:

| Ventana | Dónde | Forma |
|---|---|---|
| ⌘K | `web/buscador.ts:92`, `marco.css:275` | modal, arriba al centro, trama ░ de fondo, campo + lista + teclas |
| campo / texto / elegir / aviso | `web/interfaz.ts:27-130` (`caja()` común, `web-caja` en `web.css:5`) | modal centrada; `elegir` es campo + lista como ⌘K pero con otro CSS |
| menú ⋯ | `web/interfaz.ts:140-206`, `web.css:99` | `show` sin fondo, junto al clic; campo «filtrar» + lista |
| instrucción | `web/instruccion.ts`, `dialog.web-instruccion` en `web.css` | modal: de qué se habla, a quién y la skill lado a lado, la instrucción y lo que le llega ([instruccion.md](instruccion.md)) |
| mudanza | `web/mudanza.ts:33`, `web.css:146` | panel de progreso |
| hoja (la ficha, los códigos) | `web/lado.ts`, `marco.css:162-186` | no es `<dialog>`: va a la derecha |

⌘K, `elegir` y el menú ⋯ son los tres «campo arriba + lista filtrable + teclas ↑ ↓ ⏎ ⎋» con CSS distinto. **Componente**:
`ventana({ cabecera, campo?, cuerpo, pie })` con las variantes `centrada`, `arriba` (⌘K) y `junto-al-clic` (menú); `paleta`
(campo + lista de ítems) encima de ella.

### Piezas sueltas que se repiten

- **Chip / etiqueta**: hoy solo `.chip` en el catálogo (`catalogo.css:27-29`); falta revisar si las pestañas del dashboard y
  las etiquetas de proyectos son lo mismo (no se miró).
- **Cabeceras de columna** (`.tareas-cab`, `.proy-cab`): una fila con encabezados que ordenan; caen en «orden».
- **Campo con subrayado** (`font: inherit; border: 0; border-bottom: 1px solid var(--linea)`): se repite 6 veces entre
  `dia.css`, `hilos.css`, `configuracion.css`. Es la pieza «campo» del buscador.

### Correcciones a la jerarquía

- «herramientas» no es un compuesto aparte: es la fila de una sección (buscador + orden + nuevo), va en «secciones».
- Las cabeceras de columna del dashboard (`.proy-cab`; la de tareas se fue el 13-nov, ver «Las listas de tareas») son
  otro componente, **cabecera de tabla** (decidido el 12-nov por Telar): sus opciones son los nombres de las columnas, palabras de ancho variable, no `orden()` (un grupo de
  íconos en celdas cuadradas dentro de una banda). Va después de «sección»; no se hace aún. Lo que comparten con `orden()`
  está en la gramática (`REGLAS`): (1) un clic en la que rige vuelve al orden de siempre; (2) un solo color para la que
  rige. Hoy `orden()` usa `--titulo` y las tablas el azul: **propuesta**, un token `--orden-activa` (semántico, en
  `tokens.css`) que ambos lean; las tablas no se tocan hasta hacer su componente.
- La hoja (`web/lado.ts`) no es una ventana: no es `<dialog>` y convive con la página; queda como contenedor propio.
- «paleta» (⌘K) sale de «ventana» como su variante, no como componente aparte.

## Conexiones

- [La UI de telar](../desarrollar.md#los-componentes-los-temas-y-las-densidades-componentes) — cómo se usan hoy el
  catálogo, los temas y las densidades.
- [Modos](modos.md) — el tema y la densidad se eligen en un modo.
