// Esperas de mentira, una de cada clase, para la ventana de contestar (componentes/contestar.ts): las dibuja el catálogo
// (/componentes#contestar) y las abre el ensayo (`window.telar.ensayoContestar()` en la consola de la página). Inventadas:
// una librería de barrio, sus hilos y su boletín. Nada de aquí es de nadie.

import type { JsonAccionPagina, JsonCambio, JsonEspera, JsonPagina, JsonProyecto, JsonTarea } from '../cli';

/** La hora de esta máquina, sin zona (como la da telar): `2026-11-17T09:30:00`. */
const antes = (ahora: number, min: number): string => {
    const d = new Date(ahora - min * 60000), n = (x: number) => String(x).padStart(2, '0');
    return `${d.getFullYear()}-${n(d.getMonth() + 1)}-${n(d.getDate())}T${n(d.getHours())}:${n(d.getMinutes())}:${n(d.getSeconds())}`;
};

/** Una de cada clase, con su nombre corto (el del ensayo y el del catálogo). `ahora`: desde cuándo esperan. */
export function esperasDeMuestra(ahora = Date.now()): Record<string, JsonEspera> {
    return {
        tarea: {
            direccion: 'tarea:T12', tipo: 'tarea', clase: 'avance:cerrar', desde: antes(ahora, 60 * 26),
            titulo: 'Pedir las bolsas de papel a la imprenta', resumen: 'Llegaron ayer: 500 bolsas con el logo nuevo.',
            enlaces: ['proyecto:casa/compras'],
            campos: {
                avance: 'cerrar:hecha', como: 'hecha', prioridad: 2, vence: '2026-11-20', version: 'v1',
                texto: 'Llegaron ayer: 500 bolsas con el logo nuevo, y la factura quedó en la carpeta de compras. No queda nada por hacer.',
                contexto: 'Las bolsas de plástico se acaban en diciembre. Pedir 500 a la imprenta del barrio, con el logo nuevo, y pagar contra entrega.',
            },
        },
        retenido: {
            direccion: 'mensaje:m-7f3a', tipo: 'mensaje', clase: 'retenido', desde: antes(ahora, 95),
            titulo: '«Vitrina» → «Catálogo»', resumen: 'Te paso la lista de los doce libros de la vitrina…',
            enlaces: ['hilo:Catálogo', 'hilo:Vitrina'],
            campos: {
                de: 'Vitrina', para: 'Catálogo', modo: 'pedido', motivo: 'cadena de 7 mensajes entre los mismos dos hilos',
                texto: 'Te paso la lista de los doce libros de la vitrina de diciembre, para que revises si están en el catálogo:\n\n'
                    + '1. El libro de la feria\n2. Cuentos de la costa\n3. La casa de los mapas\n…\n\n'
                    + 'Si falta alguno, dime y lo pido. Cuando lo tengas, avísame para armar los carteles.',
            },
        },
        'en-vivo': {
            direccion: 'permiso:Vitrina', tipo: 'permiso', clase: 'pregunta', desde: antes(ahora, 4),
            titulo: '¿Qué foto va en la vitrina de diciembre?', resumen: 'La del árbol de libros · La de la feria · Ninguna: un dibujo',
            enlaces: ['hilo:Vitrina', 'proyecto:casa/vitrina'],
            campos: {
                hilo: 'Vitrina', pregunta: 'p-1',
                preguntas: [{ pregunta: '¿Qué foto va en la vitrina de diciembre?', encabezado: 'Foto', varias: false, opciones: [
                    { etiqueta: 'La del árbol de libros', descripcion: 'la que más gustó en el boletín de noviembre' },
                    { etiqueta: 'La de la feria', descripcion: 'con gente: hay que pedirles permiso a dos personas' },
                    { etiqueta: 'Ninguna: un dibujo', descripcion: 'un dibujo a mano en el vidrio, como el año pasado' },
                ] }],
            },
        },
        decide: {
            direccion: 'pregunta:casa/2026-11-14-donde-sale-la-resena', tipo: 'pregunta', clase: 'decide', desde: antes(ahora, 60 * 24 * 3),
            titulo: '¿Dónde sale la reseña de «El libro de la feria»?',
            resumen: 'La reseña está lista y revisada. Puede salir en el boletín de este viernes, o esperar a la página de reseñas.',
            enlaces: ['agente:boletin', 'archivo:casa/preguntas/2026-11-14-donde-sale-la-resena.md'],
            campos: {
                urgencia: 'media', vence: '2026-11-24', de: 'agente:boletin', repo: 'casa', recomendada: 'boletin', version: 'a1b2c3',
                opciones: [
                    { id: 'boletin', texto: 'En el boletín del viernes', accion: '', recomendada: true, marcada: false },
                    { id: 'pagina', texto: 'En la página de reseñas, cuando se rehaga en diciembre', accion: '', recomendada: false, marcada: false },
                    { id: 'no', texto: 'No sale: cerrar la tarea de la reseña', accion: 'tarea:T1 completar', recomendada: false, marcada: false },
                ],
                secciones: {
                    resumen: 'La reseña está lista y revisada. Puede salir en el boletín de este viernes, o esperar a la página de reseñas, '
                        + 'que se rehace en diciembre.',
                    por_que: 'El boletín llega a unas 340 personas y la feria fue hace dos semanas: si espera, se enfría. La página de '
                        + 'reseñas dura más, pero hoy casi nadie entra a ella.',
                    detalle: 'La reseña tiene 600 palabras y dos fotos ([el borrador](https://example.com/resena-feria)); cabe entera en el '
                        + 'boletín.\n\nSi no sale, la tarea `T1` queda '
                        + 'cerrada como hecha y la reseña se guarda en `resenas/`.',
                },
            },
        },
        // las de la ficha (detallesDeMuestra): una decisión con mucha historia, una para aprobar y una sin contexto escrito
        decision: {
            direccion: 'tarea:T70', tipo: 'tarea', clase: 'avance:pregunta', desde: '2026-11-16T16:40:00',
            titulo: 'Colegio del Valle: el pedido del plan lector 2027', resumen: 'el colegio pide 300 ejemplares de los ocho títulos…',
            enlaces: ['proyecto:casa/colegio'],
            campos: {
                avance: 'pregunta 2026-11-16', prioridad: 1, vence: '2026-11-17', version: 'v7',
                texto: 'pide=decidir · peso=alto (el pedido más grande del año) · espera=el colegio · opciones=aceptar el 12%, '
                    + 'que deja el margen en 9% y cierra hoy | contraofertar un 8% por 300 ejemplares, con entrega en marzo y la factura '
                    + 'a 60 días, como el año pasado* | consultarlo con la contadora antes de contestar · 16-nov 16:40: el colegio pide 300 '
                    + 'ejemplares de los ocho títulos y un 12% de descuento; con el 12% el margen queda en 9% · falta: ¿aceptamos el 12% '
                    + '($1,8M en total) o contraofertamos un 8%?',
            },
        },
        aprobar: {
            direccion: 'tarea:T25', tipo: 'tarea', clase: 'avance:preparado', desde: '2026-11-15T11:00:00',
            titulo: 'Feria del Libro: presupuesto del stand', resumen: 'tres escenarios en casa/feria/presupuesto.md…',
            enlaces: ['proyecto:casa/feria'],
            campos: {
                avance: 'preparado 2026-11-15', prioridad: 2, vence: '2026-11-21', version: 'v3',
                texto: 'pide=aprobar · peso=alto (compromete $2,4M) · dura=2026-11-19 · artefacto=casa/feria/presupuesto.md · 15-nov 11:00: '
                    + 'tres escenarios en casa/feria/presupuesto.md; recomiendo el del medio · falta: aprobar el stand doble ($2,4M) antes del Comité',
            },
        },
        'sin-contexto': {
            direccion: 'tarea:T31', tipo: 'tarea', clase: 'avance:pregunta', desde: '2026-11-16T18:20:00',
            titulo: 'Inventario: partirlo en dos', resumen: 'el conteo de diciembre no cabe en un día…',
            enlaces: ['proyecto:casa/inventario'],
            campos: {
                avance: 'pregunta 2026-11-16', prioridad: 2, version: 'v2',
                texto: 'pide=decidir · peso=medio (cambia cómo se cuenta diciembre) · opciones=en dos días* | en uno, cerrando la tienda · '
                    + 'sigue viva: el conteo de diciembre no cabe en un día · falta: ¿parto el inventario en dos, la bodega y la tienda?',
            },
        },
        permiso: {
            direccion: 'permiso:Inventario', tipo: 'permiso', clase: 'permiso', desde: antes(ahora, 2),
            titulo: 'Claude needs your permission to use Bash', resumen: 'Claude needs your permission to use Bash',
            enlaces: ['hilo:Inventario', 'proyecto:casa/inventario'],
            campos: { hilo: 'Inventario', pide: 'Claude needs your permission to use Bash' },
        },
    };
}

// ───────────────────────── lo que la ventana lee después de abrirla ─────────────────────────

const h = (fecha: string, tipo: string, texto: string, hora = ''): JsonCambio => ({ fecha, hora, tipo, texto });
const otra = (id: string, titulo: string, proyecto: string, vence = '', prioridad = 2): JsonTarea =>
    ({ id, titulo, estado: 'activa', proyecto, vence, prioridad });

/** Lo que la ventana lee de una tarea de mentira después de abrirla (`completar`, en el ensayo): la tarea entera, su
 *  proyecto como lo da `telar proyectos` y las tareas abiertas del proyecto. Por su dirección. */
export function detallesDeMuestra(): Record<string, { tarea: JsonTarea; proyecto?: JsonProyecto; otras?: JsonTarea[] }> {
    const proyecto = (ruta: string, nombre: string, estado: string, fin = '', aviso = ''): JsonProyecto => ({
        ruta, nombre, arquetipo: 'proyecto', modificado: '2026-11-16T10:00:00', hilo: '', vivo: false, estado, estado_completo: estado,
        plazo: fin ? { inicio: '2026-10-01', fin, estado: 'en-curso', etapa: 'desarrollo', aviso } : null,
    });
    const colegio = [otra('T70', 'Colegio del Valle: el pedido del plan lector 2027', 'casa/colegio', '2026-11-17', 1),
        otra('T71', 'Colegio del Valle: firmar la cotización del plan lector', 'casa/colegio', '2026-11-19'),
        otra('T76', 'Colegio del Valle: confirmar la fecha de entrega', 'casa/colegio', '2026-11-28'),
        otra('T77', 'Colegio del Valle: fajas con el nombre del colegio', 'casa/colegio'),
        otra('T78', 'Colegio del Valle: factura a 60 días', 'casa/colegio', '', 3)];
    return {
        'tarea:T70': {
            tarea: {
                id: 'T70', titulo: 'Colegio del Valle: el pedido del plan lector 2027', estado: 'activa', prioridad: 1, vence: '2026-11-17',
                tamano: 'larga', proyecto: 'casa/colegio', etiquetas: ['colegios', 'ventas'], creada: '2026-10-02',
                origen: 'casa/colegio/reuniones/2026-10-02-reunion-plan-lector.md', trabajo: 'casa/colegio/plan-lector.md',
                contexto: 'El Colegio del Valle compra cada año en la librería los libros de su plan lector. Para 2027 son ocho títulos para 300 '
                    + 'alumnos de 5.º a 8.º básico, con entrega en marzo: es el pedido más grande del año (unos $15M a precio de lista).\n\n'
                    + 'El colegio está comparando con otra librería y negocia el descuento por volumen. El margen de los libros escolares '
                    + 'es bajo: con más de un 10% de descuento, el pedido deja poco.',
                conexiones: ['- `bloquea` [T71](T71.md) · la cotización se firma cuando se decida el descuento',
                    '- `depende_de` [T40](T40.md) · el pedido a la distribuidora lleva estos ocho títulos'],
                historia: [
                    h('2026-10-02', 'creada', 'desde la minuta de la reunión con el colegio'),
                    h('2026-10-03', 'nota', 'La lista de los ocho títulos quedó en casa/colegio/plan-lector.md; faltan dos por confirmar con la editorial.'),
                    h('2026-10-07', 'nota', 'La editorial confirmó los ocho títulos; dos llegan recién en enero.'),
                    h('2026-10-09', 'mover', '2026-10-31 → 2026-11-15', '11:20'),
                    h('2026-10-14', 'avance', 'preparado: pide=aprobar · artefacto=casa/colegio/cotizacion.md · la cotización con precio de lista y entrega en marzo', '19:00'),
                    h('2026-10-15', 'respuesta', 'aprobado: envíalo', '09:12'),
                    h('2026-10-15', 'nota', 'apliqué: mandé la cotización al colegio, con precio de lista y entrega en marzo', '09:40'),
                    h('2026-10-28', 'nota', 'El colegio respondió que compara con otra librería y pide condiciones por volumen.'),
                    h('2026-11-04', 'avance', 'pregunta: ¿ofrecemos descuento por volumen? · falta: un número', '19:00'),
                    h('2026-11-05', 'respuesta', 'hasta un 8%, no más: el margen de los libros escolares es bajo', '08:55'),
                    h('2026-11-05', 'nota', 'apliqué: le escribí a la encargada del colegio ofreciendo un 8% por 300 ejemplares', '10:02'),
                    h('2026-11-12', 'mover', '2026-11-15 → 2026-11-17', '16:00'),
                    h('2026-11-16', 'nota', 'El colegio contesta: confirma 300 ejemplares de los ocho títulos y pide un 12%. Con el 12% el margen queda en 9%.', '16:30'),
                    h('2026-11-16', 'avance', 'pregunta: pide=decidir · peso=alto (el pedido más grande del año) · espera=el colegio · 16-nov 16:40: el colegio '
                        + 'pide 300 ejemplares y un 12% · falta: ¿aceptamos el 12% o contraofertamos un 8%?', '16:40'),
                ],
                version: 'v7',
            },
            proyecto: proyecto('casa/colegio', 'Colegio del Valle · Plan lector 2027', 'negociando el descuento', '2027-03-15'),
            otras: colegio,
        },
        'tarea:T25': {
            tarea: {
                id: 'T25', titulo: 'Feria del Libro: presupuesto del stand', estado: 'activa', prioridad: 2, vence: '2026-11-21', tamano: 'larga',
                proyecto: 'casa/feria', etiquetas: ['feria'], creada: '2026-11-03', trabajo: 'casa/feria/README.md',
                contexto: 'La librería tiene stand en la Feria del Libro de diciembre (del 5 al 14). Hay que elegir el tamaño del stand y su '
                    + 'presupuesto antes del Comité: la feria cierra las reservas el 19-nov.',
                conexiones: ['- `bloquea` [T74](T74.md) · la cuota del stand se paga cuando se elija el tamaño'],
                historia: [
                    h('2026-11-03', 'creada', 'desde el correo de la feria'),
                    h('2026-11-05', 'nota', 'La feria mandó los precios: stand simple $1,2M, doble $2,4M, de esquina $3,1M.'),
                    h('2026-11-10', 'avance', 'pregunta: ¿cuántos libros llevamos al stand?', '19:00'),
                    h('2026-11-10', 'respuesta', 'unos 600, y los de la feria aparte', '21:15'),
                    h('2026-11-12', 'nota', 'apliqué: armé tres escenarios con 600 libros en casa/feria/presupuesto.md', '11:30'),
                    h('2026-11-15', 'avance', 'preparado: pide=aprobar · peso=alto (compromete $2,4M) · 15-nov 11:00: tres escenarios; recomiendo el del medio', '11:00'),
                ],
                version: 'v3',
            },
            proyecto: proyecto('casa/feria', 'Feria del Libro · Stand de diciembre', 'reservando el stand', '2026-12-14', 'la reserva cierra el 19-nov'),
            otras: [otra('T74', 'Feria del Libro: pagar la cuota del stand', 'casa/feria', '2026-11-20'),
                otra('T81', 'Feria del Libro: elegir los libros del stand', 'casa/feria', '2026-11-30')],
        },
        'tarea:T31': {
            tarea: {
                id: 'T31', titulo: 'Inventario: partirlo en dos', estado: 'activa', prioridad: 2, proyecto: 'casa/inventario', creada: '2026-11-10',
                historia: [
                    h('2026-11-10', 'creada', 'a mano'),
                    h('2026-11-16', 'avance', 'pregunta: pide=decidir · sigue viva: el conteo de diciembre no cabe en un día', '18:20'),
                ],
                version: 'v2',
            },
            proyecto: proyecto('casa/inventario', 'Inventario', ''),
            otras: [],
        },
        'tarea:T12': {
            tarea: {
                id: 'T12', titulo: 'Pedir las bolsas de papel a la imprenta', estado: 'activa', prioridad: 2, vence: '2026-11-20', tamano: 'rapida',
                proyecto: 'casa/compras', creada: '2026-11-04',
                contexto: 'Las bolsas de plástico se acaban en diciembre. Pedir 500 a la imprenta del barrio, con el logo nuevo, y pagar contra entrega.',
                historia: [
                    h('2026-11-04', 'creada', 'a mano'),
                    h('2026-11-06', 'nota', 'apliqué: pedí 500 bolsas con el logo nuevo; llegan en dos semanas'),
                    h('2026-11-16', 'avance', 'cerrar:hecha: llegaron ayer: 500 bolsas con el logo nuevo', '09:30'),
                ],
                version: 'v1',
            },
            proyecto: proyecto('casa/compras', 'Distribuidora del Sur · Compras', 'pedido de diciembre en curso'),
            otras: [otra('T40', 'Mandar el pedido de diciembre a la distribuidora', 'casa/compras', '2026-11-17'),
                otra('T44', 'Llamar a la imprenta por el papel', 'casa/compras')],
        },
    };
}

/** La ficha de una tarea de mentira como la da su proveedor (`GET /tareas/<id>`): lo que importa a la barra de Contestar,
 *  sus acciones, con los nombres y los roles que pone el proveedor de las tareas del tipo (telar.proveedores.tareas). */
export function fichaDeMuestra(t: JsonTarea): JsonPagina {
    const estrella = !!t.etiquetas?.includes('estrella'), equipo = !!t.etiquetas?.includes('equipo');
    const acciones: JsonAccionPagina[] = [
        { nombre: 'responder', pide: 'tu respuesta', principal: true },
        { nombre: 'trabajar en un hilo', tipo: 'hilo' },
        { nombre: 'nota', pide: 'la nota' },
        { nombre: 'nueva fecha…', pide: 'la nueva fecha (AAAA-MM-DD o +Nd)', rol: 'fecha' },
        { nombre: 'esperar a…', pide: 'a quién («none»: deja de esperar)', rol: 'espera', opciones: ['Inés', 'Beto'] },
        { nombre: 'prioridad…', pide: 'la prioridad (P0 la más alta, P3)', rol: 'prioridad', opciones: ['P0', 'P1', 'P2', 'P3'] },
        { nombre: 'responsable…', pide: 'quién la hace («none»: sin asignar)', rol: 'dueno', opciones: ['Inés', 'Beto'] },
        { nombre: 'tamaño…', pide: 'rapida (media hora o menos) o larga (horas o días)', rol: 'tamano', opciones: ['rapida', 'larga'] },
        { nombre: estrella ? '★ quitar la estrella' : '☆ marcar con estrella', rol: 'estrella' },
        { nombre: equipo ? '◉ dejar de compartir con el equipo' : '○ compartir con el equipo', rol: 'equipo' },
        { nombre: '✓ hecha', confirmar: true, rol: 'hecha' },
        { nombre: 'descartar', confirmar: true, rol: 'descartar' },
    ];
    return { titulo: `${t.id} · ${t.titulo}`, subtitulo: `${t.estado} · P${t.prioridad ?? 2}${t.vence ? ` · vence ${t.vence}` : ''}`,
        version: t.version ?? 'v1', bloques: [], acciones };
}
