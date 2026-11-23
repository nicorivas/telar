# Orden por modos: la página según lo que la persona hace

Estado: **decidido en lo grande** (17-nov-2026); se construye por pasos. Cada paso que pide diseño pasa antes por un
prototipo con capturas para la persona.

## Por qué

La página creció de a una pestaña por cada necesidad, sin retirar ninguna. En una instalación de uso diario, medida
sin tocar nada, se veía esto:

- unos 520 números que piden atención, para unas 240 cosas distintas, en seis pantallas;
- 55 de 87 tareas marcadas «arriba de todo» por algún agente, así que esa marca ya no distinguía;
- la misma tarea en hasta 8 lugares, y la misma lista de 55 con tres nombres;
- el 76% de las tareas en la prioridad del medio, y casillas vencidas hace más de 90 días, en rojo junto a lo de hoy;
- modos que solo filtraban hilos y proyectos.

Las señales existen (quién espera, qué vence, qué dice el plan, a qué mundo pertenece cada cosa), pero cada pantalla usa
las suyas. Y los agentes producen más propuestas de las que una persona puede revisar.

## La idea

Ordenar por lo que hace la persona, no por de dónde viene el dato. Son dos ejes que se combinan:

- **El modo**, que es una actitud y no un día:
  - **Táctica**: decidir y hacer, lo de ahora. Es la vista de partida. Arriba va el bloque en curso y cuánto tiempo
    libre hay. Después, **Decidir** (lo que un agente espera de la persona, juntado en lotes, con un tope a la vista)
    y **Hacer** (las reuniones, el bloque del plan y unas pocas tareas). Hay un solo número en toda la página: cuántas
    decisiones esperan.
  - **Estrategia**: mirar con calma. Proyectos, tableros y registros de módulos, encargos de los agentes y la deuda
    (lo vencido hace más de 30 días). Un agente prepara el resumen. El plan lo puede sugerir, pero se entra cuando se
    quiere. (Su pantalla propia se sacó el 19-nov: el modo abre en proyectos; ver el paso 4.)
  - **Foco**: solo la terminal, para concentrarse. Ya existe.
  - **Todo**: ver y buscar todo, sin filtros ni topes: todas las tareas, todos los correos, todas las esperas, con un
    buscador sobre todo junto. **Nunca es la vista de partida, pero siempre está a un paso.**
- **El mundo** (`[mundos]`): trabajo, personal, ambos. Puede cambiar solo según el horario declarado, y a mano. Filtra
  la página entera (la barra, el número, las listas, el día), no solo los hilos.

Los modos de hoy (`[modos]`: disposición, terminal y avisos, más el filtro de hilos por etiqueta) se vuelven estos:
el filtro por etiqueta pasa al mundo, y la disposición y la terminal se quedan en cada modo.

**Las fuentes** (correo, mensajería, lecturas, calendario) las procesan los agentes. Lo que queda llega a Decidir o
a Hacer, y cada fuente sigue entera en Todo.

**Cada cosa vive en un solo lugar.** Una tarea, en su ficha; una decisión, en Decidir. Las demás pantallas la nombran
con un enlace y no la vuelven a listar.

**La urgencia la calcula telar.** El orden es este: alguien espera (un hilo, un mensaje) > vence hoy > el plan lo puso
hoy > vence esta semana > antigüedad. La marca de un agente no salta la fila. *Cambió el 17-nov* (ver el paso 3, «Tras
probarla»): delante va lo que declara el agente al proponer, el peso > una persona espera > una fecha dura, y esto
queda como el orden de cuando no declara nada. Y lo que espera ya no es una lista: va en tres vías y en Hacer.

**Del lado de los agentes** (lo hace su oficio, no telar): un tope diario de propuestas nuevas y propuestas juntadas
en lotes. No van en lote los pagos, lo que sale al mundo, lo que tiene fecha dura ni lo sensible. Lo que no tiene fecha
vence a los 14 días sin efecto y no vuelve a proponerse sin novedad. Las preguntas en lote usan el módulo de
preguntas.

## Los pasos

1. **Poda sin riesgo**, sin diseño nuevo (hecha el 17-nov):
   - «te esperan» con tecla y entre las primeras: la `t`, y tras «ahora». Una pestaña de fábrica que `[dashboard]
     orden` no nombra va junto a su vecina de siempre; las de los módulos que no nombra, al final;
   - las apps fuera de la barra de trabajo: en un menú de la cabecera, a la izquierda del modo;
   - lo vencido hace más de 30 días fuera de «esta semana» y de lo urgente del día («ahora», el orden de foco), con
     un filtro «deuda» en «tareas» (lo con estrella se queda: la estrella la pone la persona);
   - en la lista de tareas, «todas» y el buscador siempre a mano (ya estaban: arriba de la lista, a un clic);
   - «te esperan» muestra la prioridad y el vencimiento de cada fila, como «tareas».
2. **Modos y mundos**. Pide prototipo. Táctica, Estrategia, Foco y Todo, por un lado; el mundo, por otro, con su
   horario. Reemplaza a los modos de hoy, con alias para la configuración vieja.
   - **Prototipo** (17-nov), para elegir: `/componentes#modos-mundos`, con datos inventados. Tres lugares para los
     controles: **A**, en la cabecera (los cuatro modos junto a la marca, el mundo antes de los botones); **B**, en una
     banda propia bajo la cabecera (en el teléfono, los modos abajo); **C**, arriba de la barra de hilos. Los modos se
     distinguen por su ícono y el puesto va en violeta, como la vista que se ve de una pantalla; el mundo, por su color: su
     nombre y la línea bajo la cabecera. Táctica lleva el único número junto a su ícono cuando no es la que se ve. Lo que
     cambia cada modo (lo que se ve, las filas de DASHBOARD, la barra, la terminal, los avisos), Todo con su buscador
     (`componentes/todo.ts`: lo de los otros mundos se cuenta y va al final, no se esconde), las escenas del mundo y cómo se
     pasa de los modos de hoy. Lo que se queda desde ya es el horario de un mundo (`leerTramo`, `mundoAhora` en
     `componentes/modos-mundos.ts`, con su prueba): `[mundos.<n>] horario = "lun-vie 9:00-19:00"` (o una lista), `[mundos]
     fuera` para lo de fuera de todo horario (sin eso, ambos), y un cambio a mano dura hasta el próximo cambio del
     horario. Lo sin clasificar se ve en todos los mundos, con su marca.
   - **Elegido** (17-nov): A, los controles en la cabecera; en Todo el mundo solo ordena; a mano dura hasta el próximo
     cambio del horario. Se lleva a la página en tres etapas: (a) la configuración, (b) la cabecera, las teclas, la
     migración y el mundo filtrando la página, con Táctica de partida, y (c) Todo con su búsqueda en el servidor.
   - **(a) hecha**: `[mundos]` acepta `horario`, `fuera`, `color` y `etiquetas` (telar.horario, telar.mundos; en
     [../configuracion.md](../configuracion.md)); `telar config` los entrega con el color resuelto y el horario leído, y
     cada hilo de `telar hilos` y de las fotos de las otras máquinas dice su `mundo` ([../contratos.md](../contratos.md)).
   - **(b) hecha** (sin el contenido de estrategia, que entra con su paso 4): los cuatro modos de fábrica en `[modos]`
     (`estandar` es alias de `tactica`; uno propio dice su `base`; `filas` y `mundo` son ajustes nuevos), a la vista en la
     cabecera con ⌥⇧1–4 y ⌥⇧0; poner uno lleva a su vista y la página abre en táctica. El mundo (web/mundo.ts) filtra
     la barra (con «de personal N» al final de HILOS), lo que espera y el número, las tareas, los proyectos, el día y la
     línea del día; los eventos dicen su mundo por su área (`[proveedores.<n>] area`).
   - **La banda** (17-nov, lo pidió la persona: la cabecera tenía demasiado): los modos y el mundo pasan a un segundo
     nivel de la cabecera, de borde a borde (la variante B, con el mundo como botón y su menú, sin las opciones a la
     vista): los modos a la izquierda y el mundo a la derecha con hasta cuándo. La línea bajo la banda iba en el color del
     mundo; desde el 17-nov es la de siempre (todas las líneas del mismo color: la geometría ya dice el nivel). Los
     mismos clics, teclas y menús. En el teléfono también va arriba, en una línea (los íconos, el puesto en palabra y el
     mundo, sin «hasta» si no cabe entero), y la cabecera devuelve parte de su relleno: suma menos que una fila de la
     terminal. La cabecera queda con la marca, la máquina y lo que se ve, el día y los botones.
   - **(c) hecha**: `telar buscar` y `GET /buscar` (telar.servicios.buscar) sobre lo que espera, las tareas, las casillas, los
     hilos, los proyectos y los bloques; la pestaña «todo» (`vistas/dashboard/todo.ts`), la vista del modo todo: sin
     buscar, cada pestaña entera a un clic con sus cuentas por mundo; buscando, lo hallado por fuente, lo del mundo puesto
     primero y lo de los otros al final. «ver todo» de táctica lleva a ese modo. «ahora», el foco de tareas y «te
     esperan» ya no son la entrada: siguen en DASHBOARD en el modo todo, y a un clic desde táctica. En ⌘K, la última
     fila («buscar … en todo») lleva lo escrito al modo todo.
3. **Táctica**. Pide prototipo. Absorbe «ahora», foco de tareas y «te esperan»: Decidir con lotes y tope, Hacer con
   tope, el número único y la línea del día.
   - **Prototipo** (17-nov): `/componentes#tactica`, con datos inventados; tres disposiciones (en columna, lado a lado,
     Ahora en una franja) y seis estados. La urgencia es una función pura (`pagina/src/vistas/dashboard/urgencia.ts`,
     con su prueba) que no lee la marca de un agente: lo vencido hace 1 a 30 días cuenta como «vence hoy», y la deuda
     entra solo con estrella o si alguien espera.
   - **Decidido** (17-nov, con la persona): lado a lado (Ahora arriba con su ficha; Decidir y Hacer en dos columnas en
     el laptop, una en el teléfono). En Hacer, la próxima reunión ocupa un lugar solo si hay algo que preparar
     (responderla, llevar algo, o se decide algo en ella, según el plan); si no, queda en Ahora y en la línea del día.
     Los lotes son de dos clases: los que arma un agente (las preguntas `decide` de un mismo agente, como las que uno
     arma cada mañana) y los que junta telar de lo suelto, con la misma clase y el mismo origen (los
     retenidos, todos juntos: los retuvo el mismo freno).
   - **En la página** (17-nov): la pestaña «táctica», primera en DASHBOARD, con lo de verdad (`vistas/dashboard/tactica.ts`),
     sin reemplazar todavía a «ahora», foco ni «te esperan»: eso, y que sea la vista de partida, es del paso 2. Para
     mirarla con un día de mentira, sin contestar nada: `window.telar.ensayoTactica('libre')` en la consola de la página.
   - **Tras probarla** (17-nov): a la persona le aportó poco: mezclaba lo largo con lo corto, todo decía «venció hace Nd»
     en el mismo rojo, el orden era solo por fecha (lo sin fecha, lo gerencial, quedaba abajo), las etiquetas eran el
     estado del agente y no lo que ella tenía que hacer, y los títulos cortados no decían la cuenta, la persona ni la plata.
     Y lo que llamábamos Decidir no era una sola cosa: leyendo lo que falta en cada espera salen cuatro clases. Cambios
     (decididos con la persona el 17-nov, y en la página):
     - **Tres vías** en vez de Decidir, cada una con su tecla, que la recorre en «Contestar»: **decidir** (1: las opciones
       cerradas a la vista, la recomendada marcada), **aprobar** (2: lo que el agente dejó hecho, y enviar, editar o
       descartar) y **cerrar** (3: lo ya pasado, con su prueba). La vía la declara el agente (`pide=`); lo que no la trae va
       a **sin clasificar**, al final, sin adivinarla por su clase (un «preparado» suele terminar en una pregunta). Solo lo
       que ya dice qué es por su forma tiene vía sin declararla: un cierre propuesto, y una pregunta del módulo con sus
       opciones.
     - **Hacer** junta lo que un agente pide que haga la persona (`pide=hacer-tu`: un pago, una firma, una llamada; 4),
       primero y por cuenta, porque destraba a alguien; después lo de hoy (la reunión si hay algo que preparar, el plan,
       lo que vence), con su tamaño delante.
     - En cada vía, **por cuenta** (el cliente del proyecto, o el proyecto; lo sin cuenta, al final) y por peso (el
       círculo de la fila, con su porqué en el globo), con la más pesada de cada cuenta a la vista y las demás al
       desplegar. Cada fila dice **lo que hay que decidir** (lo que el agente dice que falta), no el título.
     - **Sin rojo**: el color solo para una fecha dura y una persona que espera hoy. Los mensajes retenidos entre hilos
       salen (una línea al pie, a «te esperan»); los hilos detenidos van arriba, en vivo.
     - Debajo, **lo contestado** y lo que hizo el agente con eso: su nota «apliqué: …», que `telar esperas` trae en la
       tarea (`aplique`) cuando vuelve a esperar.
     - En «Contestar» de una tarea, plegado, **para el agente**: una nota para esta tarea (para la próxima revisión o
       «hazte cargo ya») y cómo trabajar las de este tipo, cada una como una línea `[respuesta]` con su marca
       («instrucción:», «prompt:», «meta:»); con «prompt:», además, un aviso al agente que la propuso (o al que escribe
       los avances: `[agentes] sin_proyecto`). Se manda con la respuesta o solo; si falla, lo escrito queda.
     Lo que declara el agente, en una tarea, va al principio de su línea `[avance]` («pide=aprobar · peso=alto (porqué) ·
     artefacto=… · …»; los nombres en `CAMPOS` de `urgencia.ts`; quién espera, la fecha dura, las opciones y lo hecho,
     provisorios); en una pregunta, «peso: alto (porqué)» en su resumen. El orden: un hilo detenido > el peso > una
     persona espera > la fecha dura > el de antes.
4. **Estrategia**. Pide prototipo. La revisión y su resumen, con la deuda.
   - **Prototipo** (17-nov): `/componentes#estrategia`, con datos inventados; tres disposiciones (informe, tarjetas,
     recorrido de a un tema) y cinco estados (tranquila, cargada, sin resumen, resumen atrasado, sin los módulos tablero
     ni registro). Cinco temas, cada uno con sus números, lo que pide atención (con tope) y un enlace a su pantalla
     entera: proyectos (vencidos, vivos sin área, por partir y los negocios), tablero (en rojo o amarillo, lo que cambió,
     sin dato, dueños sin confirmar), registro (por revisar, por probar, incompletas), encargos (abiertos por agente, los
     de más de 7 días) y la deuda (lo vencido hace más de 30 días, `esDeuda`). Los números los calcula telar en vivo; el
     resumen del agente (`estrategia-AAAA-MM-DD.md`) va arriba y, lo que dice de cada tema, en el tema. Sin el módulo
     tablero o el de registro, su tema no va.
   - **Decidido** (17-nov, con la persona): el recorrido (primero un índice con el resumen y los números de los cinco
     temas, después de a un tema con «siguiente»). El resumen del agente llevará un párrafo de 2 o 3 líneas arriba de sus
     secciones (se le pide a su formato); mientras no esté, se muestra la primera línea de cada sección.
   - **El mundo** (17-nov): como Táctica, cada tema cuenta lo del mundo puesto y lo sin clasificar: los proyectos por el
     suyo, los encargos por el de su agente (el de su carpeta: `GET /agentes` lo dice) y la deuda por el de cada tarea;
     el resumen de otro mundo se nombra y no se muestra. El tablero y el registro van enteros (no dicen su mundo).
   - **En la página** (17-nov): la pestaña «estrategia», tras «táctica» en DASHBOARD, hasta que el cambio de modo (paso 2)
     la reemplace (`vistas/dashboard/estrategia.ts`, con lo que pide el componente de cada fuente en
     `estrategia-datos.ts`). El resumen se declara en la configuración: `[resultados.estrategia]` con su `carpeta`, su
     `en` y `prefijo = "estrategia-"`; sin eso, solo los números. Cada tema lleva a su pantalla: proyectos, la pestaña
     de su módulo, agentes, «tareas» con el filtro «deuda».
   - **Se sacó** (19-nov, con la persona: «la pestaña proyectos ya me debería decir todo, y junto con registro; el
     tablero resumido es irrelevante, me sirve solo el completo con su pestaña propia»): la pantalla «estrategia» ya no
     está. El modo estrategia sigue y abre en proyectos; sus filas de fábrica son proyectos, el tablero y el registro.
     Lo que solo ella mostraba (el resumen del agente, el resumen del tablero, los encargos abiertos juntos, la tabla
     de proyectos e iniciativas con el área de entrada del modo) no se portó a otra pantalla.
5. **Todo**: el buscador sobre todo junto y la vista sin filtros de cada fuente.
6. **Cada cosa en un solo lugar**, y la barra que muestra solo lo que se mueve: lo que espera o terminó sin verse;
   el resto, en una línea.
7. **Medir qué se usa** (qué pantallas se abren, solo en la máquina) y pasar a «más» lo que nadie abre.

## Conexiones

- [lo-que-espera-a-la-persona.md](lo-que-espera-a-la-persona.md): la bandeja, las preguntas y los mundos. Decidir se
  arma con eso.
- [modos.md](modos.md): los modos de hoy, que este orden reemplaza.
- [componentes.md](componentes.md): las piezas con que se dibuja todo esto.
