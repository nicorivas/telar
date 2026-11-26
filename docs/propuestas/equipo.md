# Equipo: la vista de las personas del área

Estado: **prototipo** (26-nov-2026), para que la persona lo mire antes de construir. No hay nada construido. Las reglas
de privacidad las propuso un agente de la persona y **todavía esperan la confirmación de la persona**. Aquí van escritas
como requisitos de diseño.

## Qué es

Es una vista de gerencia. Muestra una fila por persona del equipo. Al abrir una persona se ve su ficha:

- **1:1**: el último y el próximo, de la serie del calendario. Si no hay uno agendado, o si ya tocaba según la
  cadencia, sale en el color de cuidado, con «agendar».
- **compromisos**, en las dos direcciones:
  - *te debe*: las tareas en espera a su nombre, y las delegadas aparte, con otro ícono;
  - *le debes*: tus tareas que esa persona espera;
  - *te pide*: lo que pidió en la bandeja del equipo y sigue sin resolver.
- **capacidad**: sus horas de la semana por proyecto, contra las horas que le tocan según su dedicación, y el
  porcentaje de las cuatro semanas anteriores.
- **proyectos**: en cuáles está, con su rol y el plazo.
- **apreciaciones** de los 1:1: van en una pestaña aparte, porque son de la capa privada (más abajo).

Esta vista repite información de otras («tareas › esperando», el calendario, proyectos). Eso es a propósito: aquí se
ordena por persona.

En la fila de cada persona va:

- su carga de la semana, en el círculo: lleno es el 100% de sus horas, y sobre 110% va en rojo;
- cuántos compromisos abiertos hay entre los dos;
- un punto, si le debe algo vencido;
- el próximo 1:1.

## El prototipo

Está en `/componentes#equipo` (`pagina/src/componentes/equipo.ts`, `catalogo-equipo.ts` y `muestras-equipo.ts`;
`media/css/equipo.css`). Usa datos inventados: cinco personas (Ana, Bruno, Carla, Diego y Eva) con fechas alrededor
del 26-nov-2026. Se arma con las piezas de la casa: la barra de la pantalla, `item()`, `seccion()`, las pestañas, las
partes, la tarjeta y el botón. Tiene cinco pestañas:

- **la vista**: el laptop y el teléfono con el mismo estado, y se pueden apretar. «traer del Drive» trae las
  apreciaciones de mentira, y cambiar de persona o de pestaña las olvida.
- **estados**: Bruno (atrasado y sobrecargado), Eva (recién llegada, sin horas cargadas), las apreciaciones sin
  traer y traídas, y la lista en el teléfono.
- **privacidad**: las cinco reglas y cómo se cumplen.
- **de dónde sale** y **dónde vive**: lo mismo que este documento.

La página entera, para las capturas, se abre en `#equipo/ver/<persona|lista>/<ficha|apreciaciones>[/traidas]`.
`npm run prueba:componentes` (sección 22) revisa lo que dibuja. Entre otras cosas, revisa que ninguna apreciación
aparezca en la página antes del clic, ni en la pestaña «ficha».

## Dónde vive: extiende la de hoy

Hoy `vistas/dashboard/equipo.ts` (`PantallaEquipo`) es otra cosa: la página de **un pedido** que llega por la bandeja
del equipo (`telar equipo`). Desde ahí se le pregunta a Gestión, se agrega el pedido o se descarta. Se abre desde la
sección «pedidos» de la barra y no tiene lista de personas.

**Propuesta: extenderla.** «equipo» pasa a ser la vista de las personas, como una pestaña del dashboard en el mundo
trabajo. La página del pedido queda debajo, como el detalle de un «te pide» de la ficha:

- es la misma clase, con su clave de pantalla renombrada a `pedido` (`equipo/pedido/<id>`);
- la sección «pedidos» de la barra sigue igual;
- cada pedido aparece además en la ficha de quien lo pidió.

Así no hay dos cosas que se llamen «equipo», y el pedido se ve junto a todo lo demás que hay con esa persona.

La otra opción es reemplazarla: borrar la página del pedido y resolver los pedidos desde la ficha. Se perdería la
página que hoy abre la barra, y se mezclaría una bandeja que es de todos (cualquiera del bus puede pedir) con una
vista de las personas del área. No la recomiendo.

## De dónde sale cada dato

Nada de esto se leyó para el prototipo. Las fuentes son las de la instalación de hoy, y cada una entraría por un
proveedor, como el resto de telar.

| qué | de dónde | cómo |
| --- | --- | --- |
| la lista | la lista del equipo del área | Nombre, rol y dedicación, de una lista corta declarada en la configuración (decisión 3). No usa fichas de personas. |
| 1:1, el último y el próximo | el calendario de trabajo | La serie recurrente de cada persona («1:1 X / Ana»): la ocurrencia anterior a hoy y la siguiente. La cadencia sale de la regla de la serie. |
| te debe | las tareas, la misma fuente que «tareas › esperando» | Las tareas en estado `espera` con `espera` = la persona. Las que tienen `dueño` = la persona van aparte y con otro ícono (las delegadas). No hay una segunda base de compromisos. |
| le debes | las tareas | Las tuyas abiertas que esa persona espera. Hoy ningún campo lo dice (decisión 4). |
| te pide | la bandeja del equipo (`telar equipo sugerencias`) | Lo que pidió y sigue sin resolver. El clic abre la página del pedido. |
| capacidad | la planilla de horas | Las horas cargadas de la semana, por proyecto, y las de las cuatro semanas anteriores. Solo las horas: el ánimo del sello nunca se lee. |
| proyectos | el PMO (`telar proyectos`, `telar fechas`) | Los proyectos donde la persona está asignada, con su rol y su plazo. |
| apreciaciones | el Drive de la persona (lo privado) | El documento con las notas de los 1:1 de cada persona. Se lee solo al hacer clic. |

## Privacidad: las reglas y cómo se cumplen en el código

### 1. Las apreciaciones se traen solo con un clic, sin caché, sin repositorio y sin estado

- **La ruta.** Tienen una ruta propia, `GET /api/equipo/apreciaciones/<persona>`. Lee el Drive en el momento y contesta
  con `Cache-Control: no-store` y `X-Robots-Tag: noindex`. No escribe nada a disco: ni un archivo temporal, ni el
  registro de pedidos (la ruta se excluye del log de acceso), ni el estado de telar.
- **En la página.** Viven en una variable de la ficha (`EstadoApreciaciones`). Nunca pasan por `modelo`, ni por
  `localStorage` o `sessionStorage`, ni por el historial de la página. `Persona` no tiene un campo para ellas, y la
  prueba revisa que no viajen con el modelo.
- **Cuándo se olvidan.** Vuelven a «sin traer» al cambiar de persona, de pestaña o de mundo, cuando la página se
  esconde (`visibilitychange`), a los 10 minutos y con «olvidar ahora».
- **Lo que no se muestra antes del clic.** La pestaña no muestra un número: contarlas ya sería leerlas.

### 2. No salen en `/buscar`, ⌘K, `telar equipo` ni la búsqueda del modo todo

- `/buscar` y ⌘K (`web/hallados.ts`) buscan en lo que telar indexa, y las apreciaciones no se indexan: no tienen tipo
  ni proveedor de búsqueda.
- La búsqueda del modo todo pide lo mismo (`cli.buscar`).
- Su contenedor lleva `data-privado`. Todo lo que junta o copia texto de la página lo salta: copiar la pantalla,
  llevar algo a un hilo, el contexto que se le pasa a un agente.
- `telar equipo` es lo que ve otra persona (`api_equipo.py`) y no lee esta ruta.

### 3. Ninguna orden se las da a un agente

- No hay orden de la CLI para ellas, ni una dirección `tipo:id`: `telar objeto` no las alcanza.
- La ruta no se publica por el bus a otra máquina.
- Pide la llave de la persona en la página. La de un agente (un pedido con `TELAR_HILO`) recibe 403.
- La pestaña de apreciaciones no tiene «llevar a un hilo» ni «instrucción…».

### 4. Solo la persona la ve, y solo en el mundo trabajo

- La pestaña «equipo» se registra solo para el dueño de la máquina. Un alojado del servidor
  (`alojamiento.py`, `puerta.py`) no la tiene.
- Fuera del mundo trabajo se esconde, como las pestañas de un mundo (`web/mundo.ts`).
- La ruta de las apreciaciones contesta 404 a un alojado y cuando el mundo puesto no es trabajo. El mundo lo manda la
  página y el servidor lo comprueba contra el horario.

### 5. Nada se infiere

Todo lo que se ve se cuenta o se lee: fechas, tareas, horas, proyectos y el texto tal como se anotó. No se leen el
ánimo del sello de la planilla de horas, ni los chats, ni los correos, y ningún modelo resume a nadie. Las señales de la lista
(atrasado, vencido, sobrecarga) son cuentas con umbrales escritos en el código (`SOBRECARGA`, la cadencia de la
serie).

## Lo que se construiría, en pasos

1. **La lista y la ficha sin apreciaciones.** El proveedor de la lista del equipo, el 1:1 desde el calendario, los
   compromisos desde las tareas y los pedidos, la capacidad y los proyectos. Es lectura pura.
2. **La extensión de la pantalla de hoy.** La página del pedido pasa a `equipo/pedido/<id>`, y la ficha enlaza cada
   «te pide» a ella.
3. **Las apreciaciones**, con la ruta y las cinco reglas. Este paso va solo después de que la persona confirme las
   reglas.

## Decisiones que quedan para la persona

1. **Las cinco reglas de privacidad**: si se confirman tal cual.
2. **Extender o reemplazar** la pantalla del pedido. Recomiendo extender.
3. **Dónde vive la lista del equipo**. Puede ser una sección `[equipo]` en la configuración (nombre, rol, dedicación,
   la serie del 1:1 y el documento de apreciaciones de cada persona), un archivo del área, o el directorio del bus.
   Recomiendo la configuración, por ser lo más chico y lo más privado.
4. **«Le debes»**: cómo se marca que una tarea tuya la espera alguien. Puede ser un campo nuevo `para` en las tareas,
   una etiqueta `para:<persona>`, o solo lo que nace de la minuta de un 1:1 (`origen`).
5. **Las señales de la fila**: la carga, el número, el punto de lo vencido y el próximo 1:1. Hay que ver si sobra
   alguna, si falta alguna, y si el umbral de sobrecarga es 110%.
6. **Las apreciaciones en el teléfono**: si se pueden traer ahí (alguien podría estar mirando la pantalla) o solo en
   el laptop.
7. **Cómo se guardan las apreciaciones**: un documento por persona, o uno solo con una sección por persona. También
   cómo se reconoce cada 1:1 en el documento (un encabezado con la fecha).
8. **Cuánto duran a la vista** una vez traídas: 10 minutos, o hasta salir de la pestaña.
9. **En qué modo va la pestaña**: Estrategia (mirar con calma) o también Táctica, el día de un 1:1.

## Conexiones

- [Los componentes](componentes.md) — el prototipo se arma con las piezas de la casa y vive en su catálogo.
- [Orden por modos](orden-por-modos.md) — la pestaña va en un modo y se esconde fuera del mundo trabajo.
- [Telar para otros](telar-para-otros.md) — la regla «solo la persona»: un alojado no tiene esta vista.
- [README.md](README.md) — el plan de las propuestas.
