# La instrucción: mandarle algo a un hilo, con el contexto de donde se pidió

Estado: **decidido y hecho en lo principal** (13-nov-2026, sin publicar). Una sola manera de mandarle algo a un hilo
o a un agente desde la página: la ventana «instrucción», con su ícono (`I.instruccion`, en violeta) en todas partes.
La usan foco (las dos vistas), la ficha de una tarea (también su «escribirle a Claude»), la fila y el ⋯ de una tarea en
toda lista, el menú de toda entidad, el menú de una casilla en proyectos, «procesarlo en un hilo» de un ítem de un
bloque y encargarle a un agente (su hoja y la pantalla de agentes). Falta llevar a ella lo que se lista abajo.

## Por qué

Había cinco maneras de hacer lo mismo, cada una con su ventana y su palabra: «con Claude» y «empezar ahora» en foco
(siempre `/tarea T84` a su hilo, sin preguntar nada), «Acción…» en el menú de una entidad, «encargar» en la hoja de un
agente y «Escribirle a Secretaría sobre este proyecto…». En todas se elige a quién, qué skill y qué pedir, y en todas
va o debería ir el contexto de lo que se estaba mirando. Es una sola acción.

## La ventana

De arriba abajo:

1. **De qué se habla**: la entidad (su título y su dirección, `tarea:T84`). Su contexto va en lo que se manda.
2. **A quién**, a la izquierda: **su hilo** (el de la entidad, que telar busca: ver abajo), **un hilo nuevo** para
   ella, los agentes residentes y los hilos que ya existen. Viene elegido su hilo.
3. **La skill**, a la derecha (opcional): las de quien la recibe, las más usadas primero. Cambia con el destino.
   Quien abre la ventana puede sugerir una (foco y la ficha sugieren `/tarea`): viene elegida si el destino la tiene.
4. **La instrucción**: lo que se le pide, escrito. Hace falta ella o una skill.
5. Abajo, **lo que le llega**, tal cual: la skill, lo escrito y el contexto, en una línea.

⌘⏎ la manda; ⎋ o un clic afuera la cierran. «dejarla escrita, sin mandar» aparece solo cuando el destino es un hilo
de esta máquina que ya existe. En el celular, a quién y la skill van uno sobre otro.

**El borrador** (decidido el 13-nov con la persona): lo escrito y no mandado es de la entidad, no del lugar desde donde
se abrió. Cerrarla (⎋, un clic afuera) lo guarda con a quién y la skill elegidos, y abrirla otra vez sobre la misma
entidad (la ficha, foco, la fila de la lista) lo trae de vuelta; mandarla bien lo borra, y si falla queda. Vive mientras
viva la página.

Lo que se manda es una línea: `/skill lo escrito [contexto: título · dirección · estado; más con telar objeto
<dirección>]`. A un hilo o a un agente no se le manda su propio contexto, solo lo pedido. Lo que se manda sobre una
tarea queda en su historia, como una nota («instrucción a «Faro»: /tarea revisa el índice»; decidido el 13-nov con la
persona: lo hacía «escribirle a Claude», y ahora vale para toda instrucción sobre una tarea, venga de donde venga).

**La barra de mensaje** (24-nov): la misma instrucción en una fila al pie de una pantalla, sin abrir la ventana
(`componentes/mensaje.ts`, `web/mensaje.ts`): manda lo mismo, al mismo destino de fábrica, y comparte el borrador de la
cosa; no tiene skill ni «dejarla escrita». Hoy está en foco; dónde más va, en
[componentes.md](componentes.md), «Las pestañas y la barra de mensaje».

## Su hilo, según la entidad

Lo decide telar (`telar actuar <dirección> --donde`, `POST /actuar/adonde`), no la página:

- **una tarea o una casilla**: el hilo de su proyecto, aquí o en otra máquina (le llega por el bus); si duerme, se
  retoma; sin proyecto, se le encarga al agente de los pendientes en un hilo hijo suyo. Es lo de `telar pendiente`.
- **un proyecto**: su hilo, o se le abre uno que arranca con la instrucción.
- **un hilo**: él mismo. **Un agente**: se le encarga.
- **otra entidad** (una idea, un archivo): el proyecto o el hilo que enlaza (`telar objeto`); si no enlaza ninguno,
  no tiene hilo propio y viene elegido el primer agente.

Un hilo nuevo se abre en la carpeta de la entidad: la de su proyecto (la de una tarea es la que dice su campo
`proyecto` si no tiene hilo); sin carpeta, en la raíz. Sin entidad (un ítem de un bloque, que no tiene dirección), «un
hilo nuevo» se abre en la raíz con el nombre que se le pase, y arranca con lo pedido.

## Cómo se usa en un lugar nuevo

```ts
const { abrir } = await import('../../web/instruccion');
const r = await abrir({ direccion: 'tarea:T84', fila, skill: 'tarea' }, () => { /* al mandarla, al tiro */ });
```

`direccion` (o `fila`, la de un pendiente que la pantalla ya tiene) es el contexto; `skill` la sugerida; `a` el
destino de entrada (vacío: su hilo; `NUEVO`; o el nombre de un agente o un hilo); `solo` deja solo ese destino;
`texto`, lo que viene escrito (un borrador de la entidad gana); `nombre`, el del hilo nuevo cuando no hay entidad;
`contexto`, un texto del que se habla que no es una entidad (`{texto, titulo, origen}`, un chat: ver abajo). La
promesa termina con lo que pasó, o `undefined` si se canceló o falló.

**Desde la pestaña de un módulo** (17-nov): `window.lienzo.pedir("instruccion", {contexto, destino?, texto?})` abre
la misma ventana con lo que la pestaña muestra como contexto ([contratos.md](../contratos.md), «telar seccion»). Lo
atiende la página sola, sin permiso: nada sale hasta que la persona la manda. Viene elegido el destino que pide, o el
de `[instruccion] destino` ([configuracion.md](../configuracion.md)). El contexto se ve en una fila (su nombre, cuántas
líneas trae y de qué pestaña viene) que un clic despliega entero, y va entero al agente, con sus líneas, debajo de lo
pedido (`telar actuar --contexto`). La instrucción es opcional: vacía, le llega una línea que le pide procesarlo. Lo
escrito queda como borrador de ese contexto (su pestaña y su nombre). Va como cualquier instrucción: a un agente, un
encargo (queda registro de qué hizo con eso); a un hilo, en su entrada. El ícono es siempre `I.instruccion`, en violeta,
y el nombre «instrucción» (en un menú, «instrucción…»). Un tipo de un módulo la tiene sin hacer nada: el menú de
toda entidad la trae.

Del lado de telar es una orden: `telar actuar [<dirección>] [--a X | --nuevo [--nombre N]] [--skill S] [--nota …]
[--escribir] [--donde]`, y `POST /actuar` con `{direccion, a, nuevo, skill, nota, escribir, fila, nombre}`
(docs/contratos.md).

## Lo que falta

1. ~~**Bloquear tiempo**~~ (hecho el 13-nov): en foco (concentración) es una instrucción hecha, de un clic: pasa por
   `telar actuar` (a su hilo, con `/tarea` y el pedido de buscar un hueco de 2 a 3 horas en el calendario y crear el
   bloque), sin abrir la ventana, y queda en la historia de la tarea como cualquier instrucción. Se ve como lo que es:
   «bloquear tiempo», en el violeta de la instrucción y junto a su ícono, en la banda de foco
   ([componentes.md](componentes.md), «Las casillas»).
2. ~~**«Escribirle a Claude» en la ficha de una tarea**~~ (hecho el 13-nov): la acción del proveedor (`al_hilo` con
   `pide`) ya no es un botón en la ficha: la hace el ícono de la instrucción de su barra, con `/tarea` y el borrador de
   la tarea; en el ⋯ de una tarea es «instrucción…». Su anotación en la historia pasó a `telar actuar` (arriba).
3. **Los atajos a su hilo de la lista de tareas**: el ícono de cada fila ya abre la ventana (13-nov, la fila de
   `fila-tarea.ts`, en todas las listas de tareas). Queda ⌘-clic en una tarea (`/tarea T84` a su hilo, sin preguntar)
   y el clic en una casilla sin ficha (`pendiente`): decidir si siguen de atajo. En foco quedó uno a la vista (13-nov):
   «trabajarla», junto a la instrucción, es «trabajar en un hilo» de la ficha (`telar pendiente`, «Veamos T84» escrito
   sin mandar, y se va al hilo).
4. ~~**«procesarlo en un hilo»** de un ítem de un bloque~~ (hecho el 13-nov): abre la ventana con el mensaje que
   trae el módulo escrito y «un hilo nuevo» elegido (en la raíz, con el nombre del ítem); se puede cambiar a quién o
   agregarle algo antes de mandarlo. Si abrió un hilo, se va a él.
5. **Un evento del calendario** («escribirle» en el plan, `plan.ts`; preparar y procesar la minuta): falta un tipo
   `evento` con dirección para que su contexto viaje igual.
6. **El formulario de un periódico** elige lo mismo (a quién, la skill, el mensaje) para mandarlo después: debería
   usar las mismas listas.
7. **Recordar la última skill y el último destino** por tipo de entidad; la plantilla del prompt en la configuración.

## Conexiones

- [Acciones sobre una entidad](acciones.md) — el menú de toda entidad, que trae «instrucción…».
- [Los componentes](componentes.md) — la instrucción es una ventana (paso 7).
- [Primitivas](primitivas.md) — los objetos con dirección, que dan el contexto.
